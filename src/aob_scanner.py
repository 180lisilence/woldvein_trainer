"""
woldvein Trainer v0.4.6 - AOB（Array of Bytes）特征码扫描模块

在游戏进程内存中搜索特定的字节模式，用于定位函数或数据地址。

特征码格式：
    - 十六进制字节，空格分隔："48 8B C4 48 89 58 08"
    - 通配符 ?? 表示任意字节："48 8B ?? ?? 48 89 58"
    - 支持大小写："48 8b c4" 等同于 "48 8B C4"

使用方式：
    from .aob_scanner import AOBScaner, parse_pattern
    scanner = AOBScaner(pid)
    results = scanner.scan("48 8B C4 48 89 58 08")
    for addr in results:
        print(f"找到: 0x{addr:X}")
"""
import ctypes
from ctypes import wintypes
import struct

from .logger import log, log_success, log_error, log_warning

# Windows API
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

# 常量
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
MEM_COMMIT = 0x1000
PAGE_READONLY = 0x02
PAGE_READWRITE = 0x04
PAGE_EXECUTE_READ = 0x20
PAGE_EXECUTE_READWRITE = 0x40
PAGE_GUARD = 0x100

# 内存信息结构
class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_void_p),
        ("AllocationBase", ctypes.c_void_p),
        ("AllocationProtect", wintypes.DWORD),
        ("RegionSize", ctypes.c_size_t),
        ("State", wintypes.DWORD),
        ("Protect", wintypes.DWORD),
        ("Type", wintypes.DWORD),
    ]


def parse_pattern(pattern_str):
    """解析特征码字符串为字节列表。

    参数：
        pattern_str: 特征码字符串，如 "48 8B ?? ?? 48 89"

    返回：
        (pattern_bytes, mask)
        pattern_bytes: 字节列表，通配符位置为 0
        mask: 布尔列表，True 表示需要匹配，False 表示通配符
    """
    pattern_bytes = []
    mask = []
    tokens = pattern_str.strip().split()
    for token in tokens:
        token = token.strip()
        if token == "??" or token == "?":
            pattern_bytes.append(0)
            mask.append(False)
        else:
            try:
                byte_val = int(token, 16)
                if 0 <= byte_val <= 255:
                    pattern_bytes.append(byte_val)
                    mask.append(True)
                else:
                    raise ValueError(f"字节值超出范围: {token}")
            except ValueError:
                raise ValueError(f"无效的特征码字节: {token}")
    return pattern_bytes, mask


class AOBScaner:
    """AOB 特征码扫描器"""

    def __init__(self, pid):
        """
        参数：
            pid: 目标进程PID
        """
        self.pid = pid
        self._h_process = None
        self._open_process()

    def _open_process(self):
        """打开进程句柄"""
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        self._h_process = kernel32.OpenProcess(
            PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, self.pid
        )
        if not self._h_process:
            error = ctypes.get_last_error()
            raise RuntimeError(f"OpenProcess失败，错误码: {error}")

    def close(self):
        """关闭进程句柄"""
        if self._h_process:
            kernel32.CloseHandle(self._h_process)
            self._h_process = None

    def __del__(self):
        self.close()

    def _enum_memory_regions(self):
        """枚举进程内存区域。

        返回：
            [(base_address, size, protect), ...]
        """
        regions = []
        address = 0
        mbi = MEMORY_BASIC_INFORMATION()

        kernel32.VirtualQueryEx.argtypes = [
            wintypes.HANDLE, ctypes.c_void_p,
            ctypes.POINTER(MEMORY_BASIC_INFORMATION), ctypes.c_size_t
        ]
        kernel32.VirtualQueryEx.restype = ctypes.c_size_t

        while True:
            result = kernel32.VirtualQueryEx(
                self._h_process, ctypes.c_void_p(address),
                ctypes.byref(mbi), ctypes.sizeof(mbi)
            )
            if result == 0:
                break

            # 只扫描已提交、可读、非Guard页的内存
            if (mbi.State == MEM_COMMIT and
                mbi.Protect not in (PAGE_GUARD, 0) and
                mbi.Protect & (PAGE_READONLY | PAGE_READWRITE | PAGE_EXECUTE_READ | PAGE_EXECUTE_READWRITE)):
                regions.append((mbi.BaseAddress, mbi.RegionSize, mbi.Protect))

            address = mbi.BaseAddress + mbi.RegionSize
            if address >= 0x7FFFFFFFFFFF:  # 64位用户空间上限
                break

        return regions

    def _read_memory(self, address, size):
        """读取进程内存。

        返回：
            bytes 对象，失败返回 None
        """
        kernel32.ReadProcessMemory.argtypes = [
            wintypes.HANDLE, ctypes.c_void_p,
            ctypes.c_void_p, ctypes.c_size_t,
            ctypes.POINTER(ctypes.c_size_t)
        ]
        kernel32.ReadProcessMemory.restype = wintypes.BOOL

        buffer = ctypes.create_string_buffer(size)
        bytes_read = ctypes.c_size_t(0)
        result = kernel32.ReadProcessMemory(
            self._h_process, ctypes.c_void_p(address),
            buffer, size, ctypes.byref(bytes_read)
        )
        if result and bytes_read.value == size:
            return buffer.raw
        return None

    def scan(self, pattern_str, max_results=100):
        """扫描特征码。

        参数：
            pattern_str: 特征码字符串，如 "48 8B ?? ?? 48 89"
            max_results: 最大结果数（防止扫描到过多结果）

        返回：
            [address, ...] 匹配的地址列表
        """
        pattern_bytes, mask = parse_pattern(pattern_str)
        pattern_len = len(pattern_bytes)
        if pattern_len == 0:
            return []

        log(f"[AOB扫描] 开始扫描: {pattern_str} (长度={pattern_len})")
        results = []
        regions = self._enum_memory_regions()
        log(f"[AOB扫描] 扫描 {len(regions)} 个内存区域")

        for base, size, protect in regions:
            if len(results) >= max_results:
                break

            # 读取整个内存区域
            data = self._read_memory(base, size)
            if data is None:
                continue

            # 在数据中搜索模式
            for i in range(len(data) - pattern_len + 1):
                match = True
                for j in range(pattern_len):
                    if mask[j] and data[i + j] != pattern_bytes[j]:
                        match = False
                        break
                if match:
                    found_addr = base + i
                    results.append(found_addr)
                    log(f"[AOB扫描] 找到匹配: 0x{found_addr:X}")
                    if len(results) >= max_results:
                        break

        log(f"[AOB扫描] 完成，共找到 {len(results)} 个匹配")
        return results

    def scan_module(self, module_name, pattern_str, max_results=50):
        """在指定模块内扫描特征码。

        参数：
            module_name: 模块名，如 "GameAssembly.dll"
            pattern_str: 特征码字符串
            max_results: 最大结果数

        返回：
            [address, ...]
        """
        from .injector import get_process_modules
        modules = get_process_modules(self.pid)
        # TODO: 需要获取模块的基址和大小，当前 get_process_modules 只返回名称
        # 完整实现需要 EnumProcessModulesEx 获取模块基址
        log_warning(f"[AOB扫描] scan_module 需要模块基址信息，当前使用全内存扫描")
        return self.scan(pattern_str, max_results)


def quick_scan(pid, pattern_str, max_results=100):
    """便捷函数：快速扫描特征码。

    返回：
        [address, ...]
    """
    scanner = AOBScaner(pid)
    try:
        return scanner.scan(pattern_str, max_results)
    finally:
        scanner.close()
