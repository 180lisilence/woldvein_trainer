"""
woldvein Trainer v0.3 - 游戏进程检测与DLL注入模块

功能说明：
    检测游戏进程、注入DLL到游戏进程、验证DLL是否已注入、启动游戏。
    使用Windows API实现进程操作和DLL注入。

核心函数：
    find_game_process()   查找游戏进程，返回(pid, process)元组
    inject_dll(pid, dll_path)  注入DLL到指定进程
    is_dll_injected(pid, dll_name)  检查DLL是否已注入
    launch_game(app_id)   通过Steam启动游戏
    get_process_modules(pid)  获取进程已加载的模块列表

DLL注入原理：
    1. OpenProcess打开目标进程，获取进程句柄
    2. VirtualAllocEx在目标进程中分配内存
    3. WriteProcessMemory写入DLL路径到目标进程内存
    4. GetProcAddress获取LoadLibraryW函数地址
    5. CreateRemoteThread在目标进程中创建远程线程，调用LoadLibraryW加载DLL
    6. WaitForSingleObject等待线程结束
    7. CloseHandle关闭句柄

技术要点：
    - 使用LoadLibraryW（Unicode），支持中文路径
    - ctypes函数原型已设置argtypes/restype，避免64位句柄截断
    - WriteProcessMemory使用create_string_buffer包装bytes
    - 游戏必须通过steam://run/2656540启动，直启EXE报XGSDK code=1000黑屏
"""
import os
import ctypes
from ctypes import wintypes

from ..logger import log, log_success, log_error, log_warning

# Windows API
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
psapi = ctypes.WinDLL("psapi", use_last_error=True)

# === 显式设置 ctypes 函数原型（64位下防止句柄/指针被截断为c_int）===
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE

kernel32.VirtualAllocEx.argtypes = [wintypes.HANDLE, wintypes.LPVOID, ctypes.c_size_t, wintypes.DWORD, wintypes.DWORD]
kernel32.VirtualAllocEx.restype = wintypes.LPVOID

kernel32.VirtualFreeEx.argtypes = [wintypes.HANDLE, wintypes.LPVOID, ctypes.c_size_t, wintypes.DWORD]
kernel32.VirtualFreeEx.restype = wintypes.BOOL

kernel32.WriteProcessMemory.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.LPCVOID, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
kernel32.WriteProcessMemory.restype = wintypes.BOOL

kernel32.CreateRemoteThread.argtypes = [wintypes.HANDLE, wintypes.LPVOID, ctypes.c_size_t, wintypes.LPVOID, wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
kernel32.CreateRemoteThread.restype = wintypes.HANDLE

kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
kernel32.WaitForSingleObject.restype = wintypes.DWORD

kernel32.GetExitCodeThread.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
kernel32.GetExitCodeThread.restype = wintypes.BOOL

kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL

kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
kernel32.GetModuleHandleW.restype = wintypes.HMODULE

kernel32.GetProcAddress.argtypes = [wintypes.HMODULE, wintypes.LPCSTR]
kernel32.GetProcAddress.restype = wintypes.LPVOID

kernel32.LoadLibraryW.argtypes = [wintypes.LPCWSTR]
kernel32.LoadLibraryW.restype = wintypes.HMODULE

# 常量
PROCESS_ALL_ACCESS = 0x1F0FFF
MEM_COMMIT = 0x1000
MEM_RESERVE = 0x2000
MEM_RELEASE = 0x8000
PAGE_READWRITE = 0x04
WAIT_OBJECT_0 = 0x00000000
WAIT_TIMEOUT = 0x00000102
WAIT_FAILED = 0xFFFFFFFF
STILL_ACTIVE = 259

GAME_PROCESS_NAME = "BalladsOfHongye.exe"

# 进程白名单：只允许注入到这些进程（防止误注入其他程序）
PROCESS_WHITELIST = [
    "balladsofhongye.exe",  # 平野孤鸿 主程序
]


def validate_process_pid(pid):
    """验证PID对应的进程是否在白名单中。

    返回 (is_valid, process_name, error_msg)
    """
    import psutil
    try:
        proc = psutil.Process(pid)
        name = proc.name()
        if name.lower() in PROCESS_WHITELIST:
            return True, name, ""
        return False, name, f"进程 {name} (PID={pid}) 不在白名单中，拒绝注入"
    except psutil.NoSuchProcess:
        return False, None, f"PID={pid} 对应的进程不存在"
    except psutil.AccessDenied:
        return False, None, f"无法访问 PID={pid} 的进程信息（权限不足）"
    except Exception as e:
        return False, None, f"验证进程 PID={pid} 时异常: {e}"



def _toolhelp_processes():
    """不依赖 psutil 的进程枚举（Windows Toolhelp32）。返回 [(pid, name), ...]

    psutil 未安装或导入失败时的降级路径，纯 ctypes 实现。
    """
    import os
    results = []
    if os.name != "nt":
        return results
    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        TH32CS_SNAPPROCESS = 0x00000002
        INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

        class PROCESSENTRY32W(ctypes.Structure):
            _fields_ = [
                ("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
                ("th32ProcessID", wintypes.DWORD),
                ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
                ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                ("th32ParentProcessID", wintypes.DWORD),
                ("pcPriClassBase", ctypes.c_long), ("dwFlags", wintypes.DWORD),
                ("szExeFile", wintypes.WCHAR * 260),
            ]

        snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
        if snap == INVALID_HANDLE_VALUE or not snap:
            return results
        try:
            entry = PROCESSENTRY32W()
            entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
            kernel32.Process32FirstW.argtypes = [wintypes.HANDLE,
                                                 ctypes.POINTER(PROCESSENTRY32W)]
            kernel32.Process32FirstW.restype = wintypes.BOOL
            kernel32.Process32NextW.argtypes = [wintypes.HANDLE,
                                                ctypes.POINTER(PROCESSENTRY32W)]
            kernel32.Process32NextW.restype = wintypes.BOOL
            if kernel32.Process32FirstW(snap, ctypes.byref(entry)):
                while True:
                    results.append((entry.th32ProcessID, entry.szExeFile))
                    if not kernel32.Process32NextW(snap, ctypes.byref(entry)):
                        break
        finally:
            kernel32.CloseHandle(snap)
    except Exception:
        pass
    return results


def find_game_process():
    """查找游戏进程，返回 (pid, process) 或 (None, None)"""
    try:
        import psutil  # 懒加载：仅在查找进程时导入，加速启动
        for proc in psutil.process_iter(["pid", "name", "exe"]):
            try:
                if proc.info["name"] and proc.info["name"].lower() == GAME_PROCESS_NAME.lower():
                    return proc.info["pid"], proc
            except Exception:
                continue
    except Exception:
        pass  # psutil 不可用（未安装/导入失败）→ 走下面的 Toolhelp32 降级

    target = GAME_PROCESS_NAME.lower()
    for pid, name in _toolhelp_processes():
        if name.lower() == target:
            return pid, None
    return None, None


def get_process_modules(pid):
    """
    获取进程已加载的模块列表。
    使用EnumProcessModulesEx+GetModuleFileNameExW（psapi.dll），
    替代psutil.memory_maps()（Windows上权限要求高且不可靠）。
    """
    modules = []
    try:
        PROCESS_QUERY_INFORMATION = 0x0400
        PROCESS_VM_READ = 0x0010
        LIST_MODULES_ALL = 0x03
        MAX_PATH = 260

        # 设置psapi函数原型
        psapi.EnumProcessModulesEx.argtypes = [
            wintypes.HANDLE, ctypes.POINTER(wintypes.HMODULE),
            wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), wintypes.DWORD
        ]
        psapi.EnumProcessModulesEx.restype = wintypes.BOOL
        psapi.GetModuleFileNameExW.argtypes = [
            wintypes.HANDLE, wintypes.HMODULE, wintypes.LPWSTR, wintypes.DWORD
        ]
        psapi.GetModuleFileNameExW.restype = wintypes.DWORD

        from ..process_handle_cache import get_process_handle
        h, err = get_process_handle(pid, PROCESS_QUERY_INFORMATION | PROCESS_VM_READ)
        if not h:
            return modules
        try:
            arr = (wintypes.HMODULE * 1024)()
            needed = wintypes.DWORD(0)
            if psapi.EnumProcessModulesEx(h, arr, ctypes.sizeof(arr), ctypes.byref(needed), LIST_MODULES_ALL):
                count = needed.value // ctypes.sizeof(wintypes.HMODULE)
                buf = ctypes.create_unicode_buffer(MAX_PATH)
                for i in range(count):
                    if psapi.GetModuleFileNameExW(h, arr[i], buf, MAX_PATH):
                        modules.append(os.path.basename(buf.value))
        except Exception as e:
            log_error(f"获取进程模块失败: {e}")
    except Exception as e:
        log_error(f"获取进程模块失败: {e}")
    return modules


def get_dll_path():
    """
    获取 DLL 文件路径，自动适配开发环境和 PyInstaller 打包环境。

    优先级：
    1. PyInstaller onefile 模式：sys._MEIPASS/dist/woldvein_trainer.dll
    2. 开发环境：项目根目录/dist/woldvein_trainer.dll
    3. EXE 同目录：dist/woldvein_trainer.dll（兼容 onedir 模式）

    返回：
        DLL 文件的绝对路径
    """
    import sys
    dll_name = "woldvein_trainer.dll"

    # 1. PyInstaller onefile 模式：从 _MEIPASS 临时目录查找
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        meipass_path = os.path.join(sys._MEIPASS, "dist", dll_name)
        if os.path.exists(meipass_path):
            return meipass_path

    # 2. 开发环境：项目根目录/dist/
    # __file__ = src/injector/__init__.py，需要往上3层到项目根
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    dev_path = os.path.join(project_root, "dist", dll_name)
    if os.path.exists(dev_path):
        return dev_path

    # 3. EXE 同目录（onedir 模式或手动放置）
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(sys.executable)
    else:
        exe_dir = project_root
    exe_path = os.path.join(exe_dir, "dist", dll_name)
    if os.path.exists(exe_path):
        return exe_path

    # 4. 直接同目录
    same_dir = os.path.join(exe_dir, dll_name)
    if os.path.exists(same_dir):
        return same_dir

    # 都找不到，返回默认路径（调用方会检查存在性）
    return dev_path


def is_dll_injected(pid, dll_name):
    """检查DLL是否已注入"""
    modules = get_process_modules(pid)
    return dll_name.lower() in [m.lower() for m in modules]


def inject_dll(pid, dll_path):
    """
    注入DLL到目标进程
    返回 (success, message)

    安全：注入前验证目标进程是否在白名单中，防止误注入其他程序。
    """
    # 进程白名单验证（防止误注入）
    is_valid, proc_name, err_msg = validate_process_pid(pid)
    if not is_valid:
        log_error(f"[安全] 注入被拒绝: {err_msg}")
        return False, err_msg
    log(f"[安全] 进程白名单验证通过: {proc_name} (PID={pid})")

    dll_path = os.path.abspath(dll_path)
    if not os.path.exists(dll_path):
        return False, f"DLL文件不存在: {dll_path}"

    dll_name = os.path.basename(dll_path)

    # 检查是否已注入
    if is_dll_injected(pid, dll_name):
        return True, f"DLL已注入: {dll_name}"

    log(f"开始注入DLL: {dll_path} -> PID={pid}")

    try:
        # 打开进程
        h_process = kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)
        if not h_process:
            error = ctypes.get_last_error()
            return False, f"OpenProcess失败，错误码: {error}"

        # 在目标进程分配内存（使用UTF-16-LE编码，支持Unicode路径）
        dll_path_bytes = dll_path.encode("utf-16-le") + b"\x00\x00"
        path_size = len(dll_path_bytes)
        remote_mem = kernel32.VirtualAllocEx(
            h_process, None, path_size,
            MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE
        )
        if not remote_mem:
            error = ctypes.get_last_error()
            kernel32.CloseHandle(h_process)
            return False, f"VirtualAllocEx失败，错误码: {error}"

        # 写入DLL路径（用 create_string_buffer 包装，避免 c_void_p 不接受 bytes）
        dll_path_buf = ctypes.create_string_buffer(dll_path_bytes)
        written = ctypes.c_size_t(0)
        result = kernel32.WriteProcessMemory(
            h_process, remote_mem, dll_path_buf,
            path_size, ctypes.byref(written)
        )
        if not result or written.value != path_size:
            error = ctypes.get_last_error()
            kernel32.VirtualFreeEx(h_process, remote_mem, 0, MEM_RELEASE)
            kernel32.CloseHandle(h_process)
            return False, f"WriteProcessMemory失败，错误码: {error}"

        # 获取LoadLibraryW地址（Unicode版本，支持中文路径）
        # 用GetProcAddress从kernel32.dll获取，确保地址正确
        h_kernel32 = kernel32.GetModuleHandleW("kernel32.dll")
        load_lib_addr = kernel32.GetProcAddress(h_kernel32, b"LoadLibraryW")
        if not load_lib_addr:
            error = ctypes.get_last_error()
            kernel32.VirtualFreeEx(h_process, remote_mem, 0, MEM_RELEASE)
            kernel32.CloseHandle(h_process)
            return False, f"获取LoadLibraryW地址失败，错误码: {error}"

        # 创建远程线程执行LoadLibraryW
        thread_id = ctypes.c_ulong(0)
        h_thread = kernel32.CreateRemoteThread(
            h_process, None, 0,
            load_lib_addr,
            remote_mem, 0, ctypes.byref(thread_id)
        )
        if not h_thread:
            error = ctypes.get_last_error()
            kernel32.VirtualFreeEx(h_process, remote_mem, 0, MEM_RELEASE)
            kernel32.CloseHandle(h_process)
            return False, f"CreateRemoteThread失败，错误码: {error}"

        # 等待线程结束（最长5秒）
        wait_ret = kernel32.WaitForSingleObject(h_thread, 5000)
        if wait_ret == WAIT_TIMEOUT:
            # 超时：DLL可能仍在加载中，不清理远程内存（否则DLL加载会崩溃）
            # 注意：游戏进程中会泄漏 path_size 字节内存（约几百字节），可忽略
            kernel32.CloseHandle(h_thread)
            kernel32.CloseHandle(h_process)
            return False, f"等待远程线程超时（5秒），DLL可能仍在加载中，请稍后重试（游戏进程泄漏约{path_size}字节，可忽略）"
        elif wait_ret == WAIT_FAILED:
            error = ctypes.get_last_error()
            kernel32.CloseHandle(h_thread)
            kernel32.VirtualFreeEx(h_process, remote_mem, 0, MEM_RELEASE)
            kernel32.CloseHandle(h_process)
            return False, f"WaitForSingleObject失败，错误码: {error}"

        # 检查退出码
        exit_code = ctypes.c_ulong(0)
        if not kernel32.GetExitCodeThread(h_thread, ctypes.byref(exit_code)):
            error = ctypes.get_last_error()
            kernel32.CloseHandle(h_thread)
            kernel32.VirtualFreeEx(h_process, remote_mem, 0, MEM_RELEASE)
            kernel32.CloseHandle(h_process)
            return False, f"GetExitCodeThread失败，错误码: {error}"

        # 清理
        kernel32.CloseHandle(h_thread)
        kernel32.VirtualFreeEx(h_process, remote_mem, 0, MEM_RELEASE)
        kernel32.CloseHandle(h_process)

        if exit_code.value == 0:
            return False, "LoadLibraryW返回0，DLL加载失败（可能DLL依赖缺失或版本不匹配）"
        if exit_code.value == STILL_ACTIVE:
            return False, "远程线程仍在运行中，DLL加载未完成"

        # 验证DLL是否加载
        if is_dll_injected(pid, dll_name):
            log_success(f"DLL注入成功: {dll_name}")
            return True, f"DLL注入成功: {dll_name}"
        else:
            return False, "DLL注入后未在进程模块列表中找到"

    except Exception as e:
        log_error(f"DLL注入异常: {e}")
        return False, f"DLL注入异常: {e}"


def launch_game(steam_app_id="2656540"):
    """通过Steam协议启动游戏"""
    import subprocess
    try:
        subprocess.Popen(f"start steam://run/{steam_app_id}", shell=True)
        log(f"已请求启动游戏 (steam://run/{steam_app_id})")
        return True
    except Exception as e:
        log_error(f"启动游戏失败: {e}")
        return False

