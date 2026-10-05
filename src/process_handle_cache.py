"""
woldvein Trainer v0.4.6 - 进程句柄缓存管理器

缓存 OpenProcess 返回的进程句柄，避免频繁打开/关闭句柄，减少系统调用开销。

特点：
    - 按 PID + 访问权限 缓存句柄
    - 句柄失效时（进程退出）自动重新获取
    - 线程安全
    - 程序退出时自动关闭所有缓存句柄

使用方式：
    from .process_handle_cache import get_process_handle, release_process_handle, close_all_handles
    h = get_process_handle(pid, PROCESS_QUERY_INFORMATION | PROCESS_VM_READ)
    # 使用 h ...
    # 不需要手动 release，缓存会复用
"""
import ctypes
from ctypes import wintypes
import threading
import atexit

from .logger import log, log_error, log_warning

# Windows API
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL

# 缓存：{(pid, access): handle}
_handle_cache = {}
_cache_lock = threading.Lock()

# 进程退出检测：缓存句柄时记录PID，使用前检查进程是否还在
_pid_alive_cache = {}  # {pid: last_check_time}


def _is_process_alive(pid):
    """检查进程是否还在运行（轻量检查，不打开句柄）"""
    import psutil
    try:
        return psutil.pid_exists(pid)
    except Exception:
        return False


def get_process_handle(pid, access):
    """获取进程句柄（带缓存）。

    如果缓存中有有效句柄则直接返回，否则 OpenProcess 并缓存。

    参数：
        pid: 进程PID
        access: 访问权限（如 PROCESS_ALL_ACCESS, PROCESS_QUERY_INFORMATION | PROCESS_VM_READ）

    返回：
        (handle, error_msg)
        成功时 handle 非零，error_msg 为空
        失败时 handle 为 0，error_msg 为错误描述
    """
    if not pid:
        return 0, "PID为空"

    key = (pid, access)

    with _cache_lock:
        # 检查缓存
        if key in _handle_cache:
            h = _handle_cache[key]
            # 验证进程是否还在
            if _is_process_alive(pid):
                return h, ""
            else:
                # 进程已退出，关闭旧句柄并移除缓存
                try:
                    kernel32.CloseHandle(h)
                except Exception:
                    pass
                del _handle_cache[key]
                log_warning(f"[句柄缓存] 进程 {pid} 已退出，移除缓存句柄")

        # 打开新句柄
        h = kernel32.OpenProcess(access, False, pid)
        if not h:
            error = ctypes.get_last_error()
            return 0, f"OpenProcess失败，错误码: {error}"

        _handle_cache[key] = h
        return h, ""


def release_process_handle(pid, access=None):
    """释放并关闭缓存的进程句柄。

    参数：
        pid: 进程PID
        access: 访问权限（None 表示关闭该PID的所有缓存句柄）
    """
    with _cache_lock:
        if access is not None:
            key = (pid, access)
            if key in _handle_cache:
                try:
                    kernel32.CloseHandle(_handle_cache[key])
                except Exception:
                    pass
                del _handle_cache[key]
        else:
            # 关闭该PID的所有缓存句柄
            keys_to_remove = [k for k in _handle_cache if k[0] == pid]
            for key in keys_to_remove:
                try:
                    kernel32.CloseHandle(_handle_cache[key])
                except Exception:
                    pass
                del _handle_cache[key]


def close_all_handles():
    """关闭所有缓存的进程句柄（程序退出时调用）"""
    with _cache_lock:
        count = 0
        for key, h in list(_handle_cache.items()):
            try:
                kernel32.CloseHandle(h)
                count += 1
            except Exception:
                pass
        _handle_cache.clear()
        if count > 0:
            log(f"[句柄缓存] 已关闭 {count} 个缓存句柄")


def get_cache_stats():
    """获取缓存统计信息。

    返回：
        {"cached_count": int, "pids": [int, ...]}
    """
    with _cache_lock:
        pids = list(set(k[0] for k in _handle_cache.keys()))
        return {
            "cached_count": len(_handle_cache),
            "pids": pids,
        }


def invalidate_cache(pid=None):
    """使缓存失效（进程重启、游戏切换时调用）。

    参数：
        pid: 指定PID，None 表示清空全部缓存
    """
    if pid is None:
        close_all_handles()
    else:
        release_process_handle(pid, access=None)


# 程序退出时自动关闭所有句柄
atexit.register(close_all_handles)
