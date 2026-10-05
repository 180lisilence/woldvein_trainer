"""
兼容 shim — 保持 `from src.injector import ...` 的旧写法继续可用

v0.4.8 起实现已迁到独立的注入器产品 v0.4.7（v0.5.0 沿用），这里只做转发，不含任何注入逻辑。
新代码请直接用 src.injector_client。

⚠ 打包后（frozen）注入器可能不在机器上。这里的每个函数都做了**降级**：
拿不到注入器时返回安全的空结果（None / False / ""）而不是抛异常。
否则 trainer_ui_tk 模块级的 `DLL_PATH = get_dll_path()` 会把整个导入打断，
打包出来的 exe 会一启动就弹「Unhandled exception」然后秒退。
"""
import os

from ..injector_client import get_client, try_get_client, locate_injector

GAME_PROCESS_NAME = "BalladsOfHongye.exe"
PROCESS_WHITELIST = ["balladsofhongye.exe"]

# 最近一次降级原因，UI 可读取后提示用户（不致命）
last_error = None


def _safe(default):
    """取不到注入器客户端就返回 default，并记下原因。"""
    global last_error
    client, err = try_get_client()
    if client is None:
        last_error = err
        return None, default
    last_error = None
    return client, None


def _toolhelp_processes():
    """不依赖 psutil 的进程枚举（Windows Toolhelp32）。返回 [(pid, name), ...]"""
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


def _local_find_game_process():
    """
    纯本地进程检测（只用进程名，不需要注入器、不需要任何注入能力）。

    注入器只负责「注入」，「游戏在不在跑」是本机就能回答的问题。
    把它也外包给注入器会导致注入器一缺失就显示「未检测到游戏」，掩盖真实原因。

    两级实现：psutil 优先（信息更全），不可用时降级到 Toolhelp32（纯 ctypes）。
    """
    try:
        import psutil
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                name = proc.info.get("name")
                if name and name.lower() == GAME_PROCESS_NAME.lower():
                    return proc.info["pid"], proc
            except Exception:
                continue
    except Exception:
        pass

    target = GAME_PROCESS_NAME.lower()
    for pid, name in _toolhelp_processes():
        if name.lower() == target:
            return pid, None
    return None, None


def find_game_process():
    client, fallback = _safe(None)
    if client is None:
        # 注入器不可用：仍然如实回答「游戏在不在跑」，UI 另行提示注入器状态
        return _local_find_game_process()
    try:
        return client.find_game_process()
    except Exception as e:
        global last_error
        last_error = str(e)
        return _local_find_game_process()


def inject_dll(pid, dll_path=None):
    """幂等注入。已注入则直接成功，不会重复注入。注入器不可用时返回 False。"""
    client, fallback = _safe(False)
    if client is None:
        return fallback
    try:
        return client.ensure_injected(pid=pid, dll_path=dll_path)
    except Exception:
        return False


def is_dll_injected(pid, dll_name=None):
    """dll_name 参数保留以兼容旧调用，实际按注入器固定的通道 DLL 判定。"""
    client, fallback = _safe(False)
    if client is None:
        return fallback
    try:
        return client.is_injected(pid)
    except Exception:
        return False


def get_dll_path():
    """通道 DLL 路径。注入器不可用时返回空串（调用方需能容忍空串）。"""
    client, fallback = _safe("")
    if client is None:
        return fallback
    try:
        return client.get_dll_path()
    except Exception:
        return ""


def get_process_modules(pid):
    client, fallback = _safe([])
    if client is None:
        return fallback
    try:
        return client.get_process_modules(pid)
    except Exception:
        return []


def launch_game(steam_app_id="2656540"):
    client, fallback = _safe(None)
    if client is None:
        return fallback
    try:
        return client.launch_game(steam_app_id)
    except Exception:
        return None


__all__ = [
    "find_game_process", "inject_dll", "is_dll_injected", "get_dll_path",
    "get_process_modules", "launch_game", "get_client", "try_get_client",
    "locate_injector", "last_error",
    "GAME_PROCESS_NAME", "PROCESS_WHITELIST",
]
