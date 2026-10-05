"""
woldvein Trainer v0.4.6 - 内存地址合法性校验模块

在写入内存前验证目标地址是否合法，防止写入非法地址导致游戏崩溃。

校验项：
    1. 地址是否在用户空间范围内（64位: 0x000000000000 - 0x7FFFFFFFFFFF）
    2. 地址是否为 NULL / 0
    3. 地址所在内存页是否已提交（MEM_COMMIT）
    4. 内存页是否可写（PAGE_READWRITE / PAGE_EXECUTE_READWRITE 等）
    5. 写入大小是否超出内存区域范围
    6. 地址是否对齐（可选）

使用方式：
    from .address_validator import AddressValidator, validate_write
    validator = AddressValidator(pid)
    is_valid, reason = validator.validate_write(address, size)
    if not is_valid:
        print(f"地址非法: {reason}")
"""
import ctypes
from ctypes import wintypes

from .logger import log, log_success, log_error, log_warning

# Windows API
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

# 常量
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
MEM_COMMIT = 0x1000
MEM_FREE = 0x10000
MEM_RESERVE = 0x2000
PAGE_NOACCESS = 0x01
PAGE_READONLY = 0x02
PAGE_READWRITE = 0x04
PAGE_EXECUTE = 0x10
PAGE_EXECUTE_READ = 0x20
PAGE_EXECUTE_READWRITE = 0x40
PAGE_GUARD = 0x100
PAGE_NOCACHE = 0x200

# 64位用户空间地址范围
USER_SPACE_MIN = 0x000000000000
USER_SPACE_MAX = 0x7FFFFFFFFFFF

# 常见无效地址
INVALID_ADDRESSES = {
    0x000000000000,  # NULL
    0xCCCCCCCCCCCC,  # 未初始化栈内存（Debug模式）
    0xCDCDCDCDCDCD,  # 未初始化堆内存（Debug模式）
    0xDDDDDDDDDDDD,  # 已释放内存（Debug模式）
    0xFEEEFEEEFEEE,  # 已释放内存（Debug模式）
}


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


class AddressValidator:
    """内存地址校验器"""

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

    def _query_memory(self, address):
        """查询内存页信息。

        返回：
            MEMORY_BASIC_INFORMATION 或 None
        """
        mbi = MEMORY_BASIC_INFORMATION()
        kernel32.VirtualQueryEx.argtypes = [
            wintypes.HANDLE, ctypes.c_void_p,
            ctypes.POINTER(MEMORY_BASIC_INFORMATION), ctypes.c_size_t
        ]
        kernel32.VirtualQueryEx.restype = ctypes.c_size_t

        result = kernel32.VirtualQueryEx(
            self._h_process, ctypes.c_void_p(address),
            ctypes.byref(mbi), ctypes.sizeof(mbi)
        )
        if result == 0:
            return None
        return mbi

    def validate_address(self, address):
        """验证地址是否基本合法。

        返回：
            (is_valid, reason)
        """
        # 1. 检查 NULL 和常见无效地址
        if address == 0:
            return False, "地址为 NULL"
        if address in INVALID_ADDRESSES:
            return False, f"地址为常见无效值: 0x{address:X}"

        # 2. 检查用户空间范围
        if address < USER_SPACE_MIN or address > USER_SPACE_MAX:
            return False, f"地址 0x{address:X} 不在用户空间范围内"

        # 3. 查询内存页
        mbi = self._query_memory(address)
        if mbi is None:
            return False, f"无法查询地址 0x{address:X} 的内存信息"

        # 4. 检查内存状态
        if mbi.State == MEM_FREE:
            return False, f"地址 0x{address:X} 所在内存页未分配（MEM_FREE）"
        if mbi.State == MEM_RESERVE:
            return False, f"地址 0x{address:X} 所在内存页仅保留未提交（MEM_RESERVE）"

        # 5. 检查保护属性
        if mbi.Protect == PAGE_NOACCESS:
            return False, f"地址 0x{address:X} 所在内存页不可访问（PAGE_NOACCESS）"
        if mbi.Protect & PAGE_GUARD:
            return False, f"地址 0x{address:X} 所在内存页为保护页（PAGE_GUARD）"

        return True, ""

    def validate_read(self, address, size):
        """验证地址是否可读。

        返回：
            (is_valid, reason)
        """
        is_valid, reason = self.validate_address(address)
        if not is_valid:
            return False, reason

        mbi = self._query_memory(address)
        if mbi is None:
            return False, "无法查询内存信息"

        # 检查是否可读
        readable_protects = (
            PAGE_READONLY, PAGE_READWRITE,
            PAGE_EXECUTE_READ, PAGE_EXECUTE_READWRITE
        )
        if mbi.Protect not in readable_protects:
            return False, f"内存页保护属性 0x{mbi.Protect:X} 不允许读取"

        # 检查读取范围是否在区域内
        region_end = mbi.BaseAddress + mbi.RegionSize
        if address + size > region_end:
            return False, f"读取范围 (0x{address:X}-0x{address+size:X}) 超出内存区域 (0x{mbi.BaseAddress:X}-0x{region_end:X})"

        return True, ""

    def validate_write(self, address, size):
        """验证地址是否可写。

        返回：
            (is_valid, reason)
        """
        is_valid, reason = self.validate_address(address)
        if not is_valid:
            return False, reason

        mbi = self._query_memory(address)
        if mbi is None:
            return False, "无法查询内存信息"

        # 检查是否可写
        writable_protects = (PAGE_READWRITE, PAGE_EXECUTE_READWRITE)
        if mbi.Protect not in writable_protects:
            return False, f"内存页保护属性 0x{mbi.Protect:X} 不允许写入"

        # 检查写入范围是否在区域内
        region_end = mbi.BaseAddress + mbi.RegionSize
        if address + size > region_end:
            return False, f"写入范围 (0x{address:X}-0x{address+size:X}) 超出内存区域 (0x{mbi.BaseAddress:X}-0x{region_end:X})"

        return True, ""

    def validate_alignment(self, address, alignment=4):
        """验证地址是否对齐。

        参数：
            alignment: 对齐字节数（4表示4字节对齐，8表示8字节对齐）

        返回：
            (is_valid, reason)
        """
        if address % alignment != 0:
            return False, f"地址 0x{address:X} 未按 {alignment} 字节对齐（余数 {address % alignment}）"
        return True, ""


def validate_write_address(pid, address, size):
    """便捷函数：验证写入地址合法性。

    返回：
        (is_valid, reason)
    """
    validator = AddressValidator(pid)
    try:
        return validator.validate_write(address, size)
    finally:
        validator.close()


def validate_read_address(pid, address, size):
    """便捷函数：验证读取地址合法性。

    返回：
        (is_valid, reason)
    """
    validator = AddressValidator(pid)
    try:
        return validator.validate_read(address, size)
    finally:
        validator.close()
