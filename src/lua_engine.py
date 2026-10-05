"""
woldvein Trainer v0.3 - Lua 执行引擎

功能说明：
    通过命令文件机制与注入游戏进程的DLL通信，在游戏主线程执行Lua代码。
    Python端写入命令文件(lua_cmd.txt)，DLL轮询检测并执行，结果写入
    lua_result.txt，Python端读取结果。

通信机制：
    1. Python端清理旧的命令/结果文件
    2. Python端写入Lua代码到lua_cmd.txt
    3. DLL在游戏主线程轮询检测lua_cmd.txt，读取并执行Lua代码
    4. DLL将执行结果写入lua_result.txt
    5. Python端轮询检测lua_result.txt，读取结果
    6. Python端清理结果文件

核心函数：
    execute_lua(code, timeout)      执行Lua代码，返回(success, result)
    execute_lua_safe(code, timeout) 安全执行（捕获所有异常）

Lua脚本模板：
    LUA_ADD_RESOURCE       增加资源
    LUA_SET_RESOURCE       设置资源
    LUA_MAX_HAPPINESS      幸福度最大
    LUA_ADD_FAME           增加知名度
    LUA_CREATIVE_ENABLE    开启创造模式
    LUA_CREATIVE_DISABLE   关闭创造模式
    LUA_GET_STATUS         获取游戏状态（JSON字符串）

技术要点：
    - 线程锁：_lock防止多线程并发写命令文件
    - 超时处理：默认5秒，创造模式10秒
    - 结果解析：优先解析为整数，失败则返回原始字符串（支持JSON）
    - 超时清理：同时清理命令文件和结果文件，防止残留干扰
    - 通信文件：使用%LOCALAPPDATA%\\woldvein_trainer\\固定路径（避免_MEIPASS每次启动不同）
"""
import os
import time
import uuid
import threading

from .logger import log, log_success, log_error, log_warning
from .constants import LUA_TIMEOUT

# ========== 命名管道通信（v0.4.6 新增，优先于文件轮询） ==========
# 使用 ctypes 直接调用 Windows API，不依赖 pywin32，PyInstaller 打包更干净
import ctypes
from ctypes import wintypes

PIPE_NAME = r"\\.\pipe\woldvein_trainer"
_pipe_handle = None
_pipe_lock = threading.Lock()
_pipe_available = False  # 管道是否已连接成功（缓存状态，避免每次重连）

# Windows API 常量
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
OPEN_EXISTING = 3
PIPE_READMODE_MESSAGE = 0x00000002
ERROR_PIPE_BUSY = 231
ERROR_PIPE_LISTENING = 536
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_kernel32.CreateFileW.restype = wintypes.HANDLE
_kernel32.CreateFileW.argtypes = [
    wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
    wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE
]
_kernel32.WriteFile.restype = wintypes.BOOL
_kernel32.WriteFile.argtypes = [
    wintypes.HANDLE, wintypes.LPCVOID, wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID
]
_kernel32.ReadFile.restype = wintypes.BOOL
_kernel32.ReadFile.argtypes = [
    wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID
]
_kernel32.SetNamedPipeHandleState.restype = wintypes.BOOL
_kernel32.SetNamedPipeHandleState.argtypes = [
    wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD),
    ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD)
]
_kernel32.CloseHandle.restype = wintypes.BOOL
_kernel32.CloseHandle.argtypes = [wintypes.HANDLE]


def _connect_pipe(timeout=3.0):
    """连接命名管道。成功返回True，失败返回False（调用方回退文件轮询）。"""
    global _pipe_handle, _pipe_available
    if _pipe_handle is not None and _pipe_available:
        return True

    deadline = time.time() + timeout
    while time.time() < deadline:
        handle = _kernel32.CreateFileW(
            PIPE_NAME,
            GENERIC_READ | GENERIC_WRITE,
            0,  # 不共享
            None,
            OPEN_EXISTING,
            0,
            None
        )
        if handle != INVALID_HANDLE_VALUE and handle is not None:
            # 设置为消息读取模式
            mode = wintypes.DWORD(PIPE_READMODE_MESSAGE)
            if _kernel32.SetNamedPipeHandleState(handle, ctypes.byref(mode), None, None):
                _pipe_handle = handle
                _pipe_available = True
                log_success(f"[Pipe] 命名管道连接成功: {PIPE_NAME}")
                return True
            else:
                _kernel32.CloseHandle(handle)
        # 管道忙或不存在，等一下重试
        err = ctypes.get_last_error()
        if err == ERROR_PIPE_BUSY:
            time.sleep(0.1)
        else:
            time.sleep(0.2)
    log_warning("[Pipe] 连接超时，回退文件轮询")
    return False


def _close_pipe():
    """关闭管道连接（出错时调用，下次重连）"""
    global _pipe_handle, _pipe_available
    if _pipe_handle is not None:
        try:
            _kernel32.CloseHandle(_pipe_handle)
        except Exception:
            pass
    _pipe_handle = None
    _pipe_available = False


def _pipe_execute(code, timeout=LUA_TIMEOUT):
    """通过命名管道执行Lua代码。返回(success, result)，失败返回None（调用方回退）。

    协议与文件轮询完全一致：
    - 发送：REQ_ID:xxxxxxxx\n + Lua代码
    - 接收：REQ_ID:xxxxxxxx\n + 结果
    """
    global _pipe_handle, _pipe_available
    if _pipe_handle is None or not _pipe_available:
        return None

    req_id = uuid.uuid4().hex[:8]
    payload = f"REQ_ID:{req_id}\n{code}".encode("utf-8")

    try:
        # 发送命令
        written = wintypes.DWORD(0)
        ok = _kernel32.WriteFile(
            _pipe_handle, payload, len(payload), ctypes.byref(written), None
        )
        if not ok:
            raise OSError(f"WriteFile failed: {ctypes.get_last_error()}")

        # 读取结果（消息模式，一次ReadFile读完整条消息）
        buf = ctypes.create_string_buffer(65536)
        start = time.time()
        while time.time() - start < timeout:
            read = wintypes.DWORD(0)
            ok = _kernel32.ReadFile(
                _pipe_handle, buf, 65536, ctypes.byref(read), None
            )
            if ok and read.value > 0:
                data = buf.raw[:read.value]
                break
            err = ctypes.get_last_error()
            if err == ERROR_PIPE_LISTENING:
                time.sleep(0.02)
                continue
            # 其他错误 = 管道断开
            raise OSError(f"ReadFile failed: {err}")
        else:
            log_warning("[Pipe] 读取超时")
            _close_pipe()
            return None

        # 逐行解码（UTF-8/GBK混合，与文件轮询逻辑一致）
        _decoded_lines = []
        for _bl in data.split(b"\n"):
            try:
                _decoded_lines.append(_bl.decode("utf-8"))
            except UnicodeDecodeError:
                _decoded_lines.append(_bl.decode("gbk", errors="replace"))
        raw = "\n".join(_decoded_lines)

        lines = raw.split("\n", 1)
        result_id_line = lines[0].strip()
        result_str = lines[1].strip() if len(lines) > 1 else ""

        # ID不匹配 = 串号，返回None让调用方重试/回退
        if not result_id_line.startswith("REQ_ID:") or result_id_line[7:] != req_id:
            log_warning(f"[Pipe] 请求ID不匹配，期望:{req_id} 实际:{result_id_line[:20]}")
            return None

        if result_str == "":
            return False, -1

        try:
            result = int(result_str)
            return (result > 0), result
        except ValueError:
            return True, result_str

    except Exception as e:
        log_warning(f"[Pipe] 通信异常: {e}，断开管道回退文件轮询")
        _close_pipe()
        return None

# 通信文件路径：使用固定的 %LOCALAPPDATA%\woldvein_trainer\ 目录
# 原因：PyInstaller onefile模式下sys._MEIPASS每次启动都不同，
# DLL注入后驻留游戏进程，重启修改器后旧DLL仍轮询旧_MEIPASS路径，
# 导致第二次之后所有Lua执行超时。改用固定路径解决此问题。
import tempfile
def _get_comm_dir():
    """获取通信文件目录（固定路径，重启修改器后不变）"""
    base = os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()
    d = os.path.join(base, "woldvein_trainer")
    os.makedirs(d, exist_ok=True)
    return d
COMM_DIR = _get_comm_dir()
CMD_FILE = os.path.join(COMM_DIR, "lua_cmd.txt")
RESULT_FILE = os.path.join(COMM_DIR, "lua_result.txt")
# 跨进程通道锁文件（见 _ipc_lock_acquire）：防止多个修改器实例同时写同一份命令文件
LOCK_FILE = os.path.join(COMM_DIR, "lua_channel.lock")

_lock = threading.RLock()


def _execute_lua_inner(code, timeout=LUA_TIMEOUT):
    """
    执行Lua代码，通过命令文件机制与DLL通信。

    参数：
        code: 要执行的Lua代码字符串
        timeout: 超时时间（秒），默认5秒

    返回：
        (success, result) 元组
        - success: True表示执行成功，False表示失败或超时
        - result: 执行结果
            * 整数：Lua返回的布尔值（true→1, false→0）或数字
            * 字符串：Lua返回的字符串（如JSON状态）
            * -1：执行失败

    处理流程：
        1. 生成唯一请求ID（防竞态）
        2. 加锁，清理旧的命令/结果文件
        3. 写入"请求ID + \n + Lua代码"到lua_cmd.txt
        4. 轮询等待lua_result.txt出现，且第一行ID匹配
        5. 读取结果，解析为整数或字符串
        6. 清理结果文件
        7. 超时则清理两个文件，返回失败

    线程安全：
        使用_lock全局锁，防止多线程并发写命令文件导致冲突。
        同时使用请求ID机制，防止超时后新旧结果串号。

    竞态防护（请求ID机制）：
        问题场景：A请求超时释放锁 → B请求写入新命令 → DLL写完A的结果 → B读到A的结果
        解决方案：每次请求带唯一ID，DLL回写时带上相同ID，
                  读取方校验ID，不匹配则跳过继续等（说明是上一个请求的残留）。
    """
    # 生成唯一请求ID（短UUID前8位，足够区分并发请求）
    req_id = uuid.uuid4().hex[:8]
    req_prefix = f"REQ_ID:{req_id}\n"

    # v0.4.6：优先尝试命名管道通信（延迟更低，无文件IO）
    # 管道失败时自动回退到文件轮询，保证兼容性
    with _pipe_lock:
        if _connect_pipe(timeout=2.0):
            pipe_result = _pipe_execute(code, timeout)
            if pipe_result is not None:
                return pipe_result
            # 管道返回None = 通信失败，继续回退文件轮询
            log_warning("[Pipe] 管道执行失败，回退文件轮询")

    with _lock:
        # 清理旧文件
        for f in [CMD_FILE, RESULT_FILE]:
            try:
                if os.path.exists(f):
                    os.remove(f)
            except Exception:
                pass  # 清理失败不影响执行，静默容错

        # 写入命令文件（格式：REQ_ID:xxxxxxxx\n + Lua代码）
        # 原子写入（.tmp + os.replace）：open("w") 会先截断再分片写入，
        # 若同时有第二个实例在写同一份文件，DLL 可能读到「A的请求ID + B的代码」的拼接内容，
        # 表现就是「命令返回了别的命令的结果」（实机事故 2026-09-14：面板注入/品阶升级假失败）。
        try:
            _write_cmd_atomic(req_prefix + code)
        except Exception as e:
            log_error(f"写入命令文件失败: {e}")
            return False, -1

        # 等待结果（校验请求ID，防止串号）
        start = time.time()
        mismatch_skips = 0  # 统计ID不匹配跳过次数（用于诊断）
        while time.time() - start < timeout:
            if os.path.exists(RESULT_FILE):
                try:
                    with open(RESULT_FILE, "rb") as f:
                        _raw_bytes = f.read()
                    # 逐行解码：
                    # 同一份结果里既有我们的 UTF-8 字面量，也有游戏返回的 GBK 字符串。
                    # 若按整段回退（先试 utf-8，失败则整段 gbk），
                    # 会把正常的字面量也变成乱码（如“城市管理器”变成“鍩庡競绠”）。
                    # 逐行判断可两者兼顾。
                    _decoded_lines = []
                    for _bl in _raw_bytes.split(b"\n"):
                        try:
                            _decoded_lines.append(_bl.decode("utf-8"))
                        except UnicodeDecodeError:
                            # 该行是游戏内的 GBK 字符串，单独回退解码
                            _decoded_lines.append(_bl.decode("gbk", errors="replace"))
                    raw = "\n".join(_decoded_lines)
                    # 解析：第一行是请求ID，剩余是结果
                    lines = raw.split("\n", 1)
                    result_id_line = lines[0].strip()
                    result_str = lines[1].strip() if len(lines) > 1 else ""

                    # ID不匹配 = 读到了上一个请求的残留结果，跳过继续等
                    if not result_id_line.startswith("REQ_ID:") or result_id_line[7:] != req_id:
                        mismatch_skips += 1
                        if mismatch_skips <= 3:
                            log_warning(
                                f"[竞态防护] 请求ID不匹配，跳过。"
                                f"期望:{req_id} 实际:{result_id_line[:20]} "
                                f"跳过次数:{mismatch_skips}"
                            )
                        time.sleep(0.05)
                        continue

                    # ID匹配成功，清理结果文件
                    try:
                        os.remove(RESULT_FILE)
                    except Exception:
                        pass  # 清理失败不影响结果返回

                    # 空结果诊断
                    if result_str == "":
                        cmd_exists = os.path.exists(CMD_FILE)
                        cmd_size = 0
                        if cmd_exists:
                            try:
                                cmd_size = os.path.getsize(CMD_FILE)
                            except Exception:
                                pass
                        log_warning(f"[Lua调试] 返回空结果。命令文件是否存在: {cmd_exists}, 大小: {cmd_size}B")
                        return False, -1
                    # 尝试解析为整数，失败则返回原始字符串
                    # 约定：Lua 脚本返回 1=成功, 0=失败（非负数判断会把 0 误判为成功）
                    try:
                        result = int(result_str)
                        return (result > 0), result
                    except ValueError:
                        # 字符串结果（如JSON）
                        return True, result_str
                except Exception as e:
                    log_error(f"读取结果失败: {e}")
                    return False, -1
            time.sleep(0.05)

        log_warning(f"Lua执行超时 ({timeout}s)")
        # 超时后清理命令文件和结果文件，防止残留干扰
        for f in [CMD_FILE, RESULT_FILE]:
            try:
                if os.path.exists(f):
                    os.remove(f)
            except Exception:
                pass  # 超时清理失败不影响返回结果
        return False, -1


def _write_cmd_atomic(payload):
    """原子写入命令文件：先写 .tmp 再 os.replace（同分卷原子）。

    为什么必须原子：直接 open(CMD_FILE,"w") 会先截断再分片写入（Python 文本层默认 8KB 缓冲），
    如果同时存在第二个修改器实例在写同一份文件，DLL 可能读到「A 的请求ID + B 的代码」这种
    拼接内容，于是「某个命令返回了另一个命令的结果」→ 面板注入 / 品阶升级全部假失败。
    """
    tmp = CMD_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        f.write(payload)
        f.flush()
        try:
            os.fsync(f.fileno())
        except Exception:
            pass
    os.replace(tmp, CMD_FILE)


_ipc_handle = None


def _ipc_lock_acquire(timeout=20.0):
    """获取跨进程通道锁（Windows: msvcrt 文件锁）。失败返回 False（仍会继续，仅告警）。

    进程内的 _lock 管不住另一个修改器进程，必须用系统级文件锁，
    否则两个实例的后台状态轮询会互相覆盖 lua_cmd.txt。
    """
    global _ipc_handle
    try:
        import msvcrt
    except ImportError:
        return True  # 非 Windows：退化为仅进程内锁
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            h = open(LOCK_FILE, "a+b")
        except Exception:
            return True
        try:
            msvcrt.locking(h.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            try:
                h.close()
            except Exception:
                pass
            time.sleep(0.02)
            continue
        _ipc_handle = h
        return True
    return False


def _ipc_lock_release():
    """释放跨进程通道锁"""
    global _ipc_handle
    h = _ipc_handle
    _ipc_handle = None
    if h is None:
        return
    try:
        import msvcrt
        h.seek(0)
        msvcrt.locking(h.fileno(), msvcrt.LK_UNLCK, 1)
    except Exception:
        pass
    try:
        h.close()
    except Exception:
        pass


def execute_lua(code, timeout=LUA_TIMEOUT):
    """执行Lua代码（进程内锁 + 跨进程通道锁）。

    具体协议、返回值约定见 _execute_lua_inner 的文档字符串。
    """
    with _lock:
        got = _ipc_lock_acquire()
        try:
            return _execute_lua_inner(code, timeout)
        finally:
            if got:
                _ipc_lock_release()


def execute_lua_retry(code, timeout=LUA_TIMEOUT, attempts=3, tag="", expect=None):
    """关键操作重试包装：拿不到有效结果时自动重发（每次都是全新请求ID）。

    expect: 期望的结果前缀元组；若结果是字符串但不以这些前缀开头，
            说明拿到的可能是别的命令的残留结果（串号），同样重试。
    """
    if expect is None:
        expect = ("[成功]", "[失败]", "[错误]", "[提示]", "[警告]")
    expect = tuple(expect)
    last = (False, -1)
    for i in range(1, max(1, int(attempts)) + 1):
        success, result = execute_lua_safe(code, timeout)
        last = (success, result)
        ok = bool(success)
        if ok and isinstance(result, str):
            ok = result.strip().startswith(expect)
        if ok:
            return success, result
        if i < attempts:
            log_warning(f"[重试] {tag or '关键操作'} 第 {i} 次未拿到有效结果，重发请求 ...")
            time.sleep(0.3)
    return last

def execute_lua_safe(code, timeout=LUA_TIMEOUT):
    """
    安全执行Lua代码，捕获所有异常。

    参数：
        code: 要执行的Lua代码字符串
        timeout: 超时时间（秒），默认5秒

    返回：
        (success, result) 元组，异常时返回(False, -1)

    说明：
        对execute_lua的包装，捕获所有异常并记录日志，
        确保调用方不会因为Lua执行异常而崩溃。
    """
    try:
        return execute_lua(code, timeout)
    except Exception as e:
        log_error(f"Lua执行异常: {e}")
        return False, -1


# ========== 资源修改 Lua 脚本模板 ==========

LUA_ADD_RESOURCE = r"""
local ok, err = pcall(function()
    if not g_camp or not g_camp.m_tbSource then return false end
    local id = %d
    local amt = %d
    local cur = g_camp.m_tbSource[id] or 0
    g_camp.m_tbSource[id] = cur + amt
    return true
end)
return ok and err or false
"""

LUA_SET_RESOURCE = r"""
local ok, err = pcall(function()
    if not g_camp or not g_camp.m_tbSource then return false end
    g_camp.m_tbSource[%d] = %d
    return true
end)
return ok and err or false
"""

LUA_MAX_HAPPINESS = r"""
local ok, err = pcall(function()
    if not g_camp then return false end
    g_camp.m_nHappinessScore = 999
    g_camp.m_nHappinessLevel = 4
    return true
end)
return ok and err or false
"""

LUA_ADD_FAME = r"""
local ok, err = pcall(function()
    local rep = g_LReputationMgr
    if not rep then return "未找到 g_LReputationMgr（请先进入游戏场景）" end
    local delta = %d
    local before = 0
    pcall(function() if rep.GetReputation then before = rep:GetReputation() end end)
    pcall(function() if rep.ChangeReputation then rep:ChangeReputation(delta) end end)
    pcall(function() if rep.ChangeReputationBase then rep:ChangeReputationBase(delta) end end)
    local after = before
    pcall(function() if rep.GetReputation then after = rep:GetReputation() end end)
    return "知名度 +" .. tostring(delta) .. "（" .. tostring(before) .. " -> " .. tostring(after) .. "）"
end)
if not ok then return "[错误] " .. tostring(err) end
return err
"""

# ========== 创造模式 Lua 脚本 ==========

LUA_CREATIVE_ENABLE = r"""
local ok, err = pcall(function()
    g_bCreativeMode = true
    if g_cm_opt_max_boom == nil then g_cm_opt_max_boom = true end
    if g_cm_opt_unlock_buildings == nil then g_cm_opt_unlock_buildings = true end
    if g_cm_opt_infinite_resources == nil then g_cm_opt_infinite_resources = true end
    if g_cm_opt_unlimited_upgrade == nil then g_cm_opt_unlimited_upgrade = true end

    -- 1. 鸿业满级
    if g_cm_opt_max_boom and g_camp and g_camp.GetCampBoomModule then
        local boom = g_camp:GetCampBoomModule()
        if boom then
            -- hook方法，让查询永远返回满级
            local mt = getmetatable(boom)
            if mt and mt.__index and not mt.__index.__cm_boom_hooked then
                local cls = mt.__index
                cls.__cm_boom_orig_is = cls.IsSatisfied
                cls.__cm_boom_orig_get = cls.GetBoom
                cls.IsSatisfied = function() return true end
                cls.GetBoom = function() return 14 end
                cls.__cm_boom_hooked = true
            end
            
            -- 设置鸿业等级为满级（14级）
            pcall(function() boom:setBoom(14) end)
            
            -- 解锁所有鸿业等级奖励（建筑、谋士、功能等）
            pcall(function()
                if boom.UpdateHistoryMaxBoomLevel then
                    -- 先设置历史最高为1，确保从1级到14级所有奖励都能解锁
                    if boom.setHistoryMaxBoomLevel then
                        boom:setHistoryMaxBoomLevel(1)
                    end
                    -- 触发历史最高等级更新，这会遍历解锁所有中间等级的奖励
                    boom:UpdateHistoryMaxBoomLevel()
                end
            end)
            
            -- 直接遍历解锁每一级的奖励（作为兜底）
            pcall(function()
                if boom.UnLockBoomReward then
                    for i = 1, 14 do
                        boom:UnLockBoomReward(i)
                    end
                end
            end)
            
            -- 触发UI刷新事件
            pcall(function()
                -- 鸿业称号更新
                if g_LHBUI and g_LHBUIEvents and boom.GetCurTitle then
                    local title = boom:GetCurTitle()
                    g_LHBUI:Emit(g_LHBUIEvents.S2UI_UpdateCurBoomTitle, title)
                end
                -- 繁荣度UI刷新
                if g_LHBUIProvider and g_LHBUIEvents and boom.GetProsperityLevel then
                    local pl = boom:GetProsperityLevel()
                    g_LHBUIProvider:EmitTo("LProsperityProvider", g_LHBUIEvents.S2UI_OnUpdateBoom, pl)
                end
                -- 建筑卡片UI刷新
                if g_LHBUIProvider and g_LHBUIEvents and g_blockMgr then
                    local campId = 1
                    -- [API-FIX] LBlockMgr 没有 GetCampBlockId；用 GetCampBlock() 再取 ID
                    if g_blockMgr.GetCampBlock then
                        local _cb = g_blockMgr:GetCampBlock()
                        if _cb and _cb.GetBlockID then campId = _cb:GetBlockID() end
                    end
                    g_LHBUIProvider:EmitTo("LBuildingProvider", g_LHBUIEvents.S2UI_OnUpdateBuildingCards, campId)
                end
                -- 大本营信息刷新
                if g_LHBUI and g_LHBUIEvents then
                    g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnUpdateCampInfo, 1)
                end
            end)
        end
    end

    -- 2. 全建筑解锁 + 只显示最高等级建筑
    if g_cm_opt_unlock_buildings then
        local BCM = g_LBuildingCardManager
        if BCM then
            -- 2a. 全建筑解锁
            -- 第1层：hook每个建筑卡片的 GetUnlockState/SetUnlockState
            if BCM.tabBuildingCards then
                for _, c in pairs(BCM.tabBuildingCards) do
                    if type(c) == "table" and not c.__cm_card_hooked then
                        c.__cm_orig_GetUnlockState = c.GetUnlockState
                        c.__cm_orig_SetUnlockState = c.SetUnlockState
                        c.GetUnlockState = function() return true end
                        c.SetUnlockState = function(self, state)
                            -- 忽略外部设置，强制保持解锁
                            if c.__cm_orig_SetUnlockState then
                                c.__cm_orig_SetUnlockState(self, true)
                            end
                        end
                        c.__cm_card_hooked = true
                        -- 立即设为解锁
                        pcall(function()
                            if c.__cm_orig_SetUnlockState then
                                c.__cm_orig_SetUnlockState(c, true)
                            end
                        end)
                    end
                end
            end
            -- 第2层：hook天赋检查，让天赋解锁判断总是返回true
            if g_TalentManager and not g_TalentManager.__cm_talent_hooked then
                g_TalentManager.__cm_orig_CheckTalent = g_TalentManager.CheckTalentIsActive
                g_TalentManager.CheckTalentIsActive = function() return true end
                g_TalentManager.__cm_talent_hooked = true
            end

            -- scheme层解锁
            if g_LOfficeManager and g_LOfficeManager.GetAdviserOfficeInCamp then
                local office = g_LOfficeManager:GetAdviserOfficeInCamp()
                if office then
                    local allCards = {}
                    if BCM.tabBuildingCards then
                        for _, c in pairs(BCM.tabBuildingCards) do
                            if type(c) == "table" then table.insert(allCards, c) end
                        end
                    end
                    if office.GetScheme then
                        local s = office:GetScheme()
                        if s and s.SetBuildingCardState then
                            pcall(function() s:SetBuildingCardState(allCards, true) end)
                        end
                    end
                    if office.GetBaseScheme then
                        local bs = office:GetBaseScheme()
                        if bs then
                            if bs.AddOtherBuildings then pcall(function() bs:AddOtherBuildings() end) end
                            if bs.SetBuildingCardState then pcall(function() bs:SetBuildingCardState(allCards, true) end) end
                        end
                    end
                end
            end

            -- 注：不hook GetBuildingCards/GetTypedBuildingCards
            -- 原因：完全重写这两个方法会破坏UI获取建筑列表的数据结构
            --       导致游戏UI全部消失。只保留卡片解锁hook即可。
        end
    end

    -- 3. 无限资源
    if g_cm_opt_infinite_resources then
        local BWM = g_BuildingWorldModule
        if BWM and BWM.BuildingMgr then
            local mt = getmetatable(BWM.BuildingMgr)
            if mt and mt.__index and not mt.__index.__cm_res_hooked then
                local cls = mt.__index
                cls.__cm_orig_ConsumeResource = cls.ConsumeResource
                cls.__cm_orig__ConsumeResource = cls._ConsumeResource
                cls.__cm_orig_CheckCanCreate = cls.CheckCanCreateBuilding
                cls.__cm_orig_CheckCanUpgrade = cls.CheckCanUpgradeBuilding
                cls.ConsumeResource = function() return true end
                cls._ConsumeResource = function() return true end
                cls.CheckCanCreateBuilding = function() return true end
                cls.CheckCanUpgradeBuilding = function(self, building)
                    -- 先调用原始函数检查
                    local orig_ok, orig_err = pcall(function()
                        return cls.__cm_orig_CheckCanUpgrade(self, building)
                    end)
                    if orig_ok and orig_err == true then
                        return true
                    end
                    -- 原始返回false时，检查建筑是否有多个等级（避免单等级建筑播放升级动画）
                    if building and building.L and building.G and building.D and building.P then
                        local ok, maxLevel = pcall(function()
                            return g_buidlingCfg:GetBuildingMaxLevel(building.G, building.D, building.P)
                        end)
                        if ok and maxLevel and maxLevel > 1 then
                            -- 建筑有多个等级，当前等级<最大等级时允许升级（解锁等级限制）
                            if building.L < maxLevel then
                                return true
                            end
                        end
                    end
                    -- 单等级建筑或已满级，不允许升级
                    return false
                end
                cls.__cm_res_hooked = true
            end
        end
        if g_camp and not g_camp.__cm_msv_hooked then
            local o_msv = g_camp.ModifySourceValue
            g_camp.__cm_orig_msv = o_msv
            g_camp.ModifySourceValue = function(self, sourceId, value, bIsInit)
                if value and value < 0 and not bIsInit then return end
                if o_msv then return o_msv(self, sourceId, value, bIsInit) end
            end
            g_camp.__cm_msv_hooked = true
        end
    end

    -- 4. 升级无限制（解锁全部功能）
    if g_cm_opt_unlimited_upgrade then
        if g_camp and g_FunctionManager and g_functionType and g_functionState then
            if not g_camp.__cm_func_saved then
                g_camp.__cm_orig_func_states = {}
                for key, funcId in pairs(g_functionType) do
                    if type(funcId) == "number" then
                        -- [API-FIX] 没有 GetFucntionState；读取用 CheckFuncIsUnlock（返回 g_functionState.OPEN/CLOSE）
                        local ok, state = pcall(function() return g_FunctionManager:CheckFuncIsUnlock(funcId) end)
                        if ok then g_camp.__cm_orig_func_states[funcId] = state end
                    end
                end
                g_camp.__cm_func_saved = true
            end
            for key, funcId in pairs(g_functionType) do
                if type(funcId) == "number" then
                    pcall(function() g_FunctionManager:SetFucntionState(funcId, g_functionState.OPEN) end)
                end
            end
        end
    end

    -- 5. GM标志：快速建造 + 忽略地块限制 + 可操作所有建筑
    if g_cm_opt_gm_flags ~= false then
        if g_GameWorld then
            g_GameWorld.bGMBuildFast = true
            g_GameWorld.bGMIgnoreTileLimit = true
            g_GameWorld.bGMCanOperateAllBuildingAndRoad = true
        end
    end

    -- 6. 建筑不受灾害伤害
    if g_cm_opt_no_disaster_damage ~= false then
        local BWM = g_BuildingWorldModule
        if BWM and BWM.BuildingMgr then
            local mgr = BWM.BuildingMgr
            local mt = getmetatable(mgr)
            if mt and mt.__index then
                local cls = mt.__index
                -- 建筑类的hook需要通过建筑实例获取
                pcall(function()
                    if g_camp and g_blockMgr then
                        local block = g_camp:GetCampBlock()
                        if block and block.GetAllBuildings then
                            local buildings = block:GetAllBuildings()
                            if buildings and #buildings > 0 then
                                local b = buildings[1]
                                local bmt = getmetatable(b)
                                if bmt and bmt.__index then
                                    local bcls = bmt.__index
                                    if not bcls.__cm_disaster_hooked then
                                        bcls.__cm_orig_DisasterSubHP = bcls.DisasterSubHP
                                        bcls.DisasterSubHP = function(self, nDisasterType, nSub)
                                            -- 创造模式：建筑不受灾害伤害
                                            return
                                        end
                                        bcls.__cm_disaster_hooked = true
                                    end
                                end
                            end
                        end
                    end
                end)
            end
        end
    end

    -- 7. 不触发灾害
    if g_cm_opt_no_disaster ~= false then
        if g_camp and g_blockMgr then
            local block = g_camp:GetCampBlock()
            if block then
                local mt = getmetatable(block)
                if mt and mt.__index then
                    local cls = mt.__index
                    if not cls.__cm_trigger_disaster_hooked then
                        cls.__cm_orig_TriggerDisaster = cls.TriggerDisaster
                        cls.TriggerDisaster = function(self, type, nLevel)
                            -- 创造模式：不触发灾害
                            return
                        end
                        cls.__cm_trigger_disaster_hooked = true
                    end
                end
            end
        end
    end

    -- 8. 道路连接豁免（行人不必经过道路，可直接到达建筑）
    if g_cm_opt_road_bypass ~= false then
        local BWM = g_BuildingWorldModule
        if BWM and BWM.BuildingMgr then
            local mgr = BWM.BuildingMgr
            local mt = getmetatable(mgr)
            if mt and mt.__index then
                local cls = mt.__index
                if not cls.__cm_road_hooked then
                    cls.__cm_orig_ModifyCheckRoadFlag = cls.ModifyCheckRoadFlag
                    cls.ModifyCheckRoadFlag = function(self, tbwo, bSelf, tbWo2, bCheckFull)
                        local tbVisited = {}
                        for k, wo in pairs(tbwo or {}) do
                            local uuid = wo:GetWOUUID()
                            if not tbVisited[uuid] then
                                tbVisited[uuid] = true
                                local building = wo:GetBuilding()
                                if building then
                                    building.m_bIsCheckRoadAdd = false
                                    pcall(function() building:UpdateIsConnectedToPost() end)
                                end
                            end
                        end
                    end
                    cls.__cm_road_hooked = true
                end
            end
        end
    end

    -- 9. 人口不分类别（工人/匠人/学者通用）
    if g_cm_opt_population_universal ~= false then
        if g_camp and g_blockMgr then
            local block = g_camp:GetCampBlock()
            if block then
                local mt = getmetatable(block)
                if mt and mt.__index then
                    local cls = mt.__index
                    if not cls.__cm_pop_hooked then
                        cls.__cm_orig_GetPopulation = cls.GetPopulation
                        cls.GetPopulation = function(self, tbPSource)
                            if not tbPSource then return 0 end
                            local total = 0
                            pcall(function()
                                total = total + self:GetSourceValue(block_define.SOURCE.CURRENT_POPULATION)
                                total = total + self:GetSourceValue(block_define.SOURCE.CRAFTSMAN)
                                total = total + self:GetSourceValue(block_define.SOURCE.SCHOOLER)
                                total = total + self:GetSourceValue(block_define.SOURCE.REFUGEE_POPULATION)
                                total = total + self:GetSourceValue(block_define.SOURCE.TEMPORARY_POPULATION)
                            end)
                            return total
                        end
                        cls.__cm_pop_hooked = true
                    end
                end
            end
        end
    end

    -- 10. 统一刷新UI
    pcall(function()
        if g_LHBUI and g_LHBUIEvents then
            g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnUpdateCampInfo, 1)
            g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnUpdateBuildingCards, 1)
        end
    end)

    return true
end)
return ok and err or false
"""

LUA_CREATIVE_DISABLE = r"""
local ok, err = pcall(function()
    g_bCreativeMode = false

    -- 1. 还原建筑卡片hook（遍历所有卡片恢复原始方法）
    local BCM = g_LBuildingCardManager
    if BCM and BCM.tabBuildingCards then
        for _, c in pairs(BCM.tabBuildingCards) do
            if type(c) == "table" and c.__cm_card_hooked then
                if c.__cm_orig_SetUnlockState ~= nil then
                    c.SetUnlockState = c.__cm_orig_SetUnlockState
                else
                    c.SetUnlockState = nil
                end
                if c.__cm_orig_GetUnlockState ~= nil then
                    c.GetUnlockState = c.__cm_orig_GetUnlockState
                else
                    c.GetUnlockState = nil
                end
                c.__cm_orig_SetUnlockState = nil
                c.__cm_orig_GetUnlockState = nil
                c.__cm_card_hooked = nil
            end
        end
    end

    -- 1b. 还原天赋检查 CheckTalentIsActive
    if g_TalentManager and g_TalentManager.__cm_talent_hooked then
        if g_TalentManager.__cm_orig_CheckTalent ~= nil then
            g_TalentManager.CheckTalentIsActive = g_TalentManager.__cm_orig_CheckTalent
        else
            g_TalentManager.CheckTalentIsActive = nil
        end
        g_TalentManager.__cm_orig_CheckTalent = nil
        g_TalentManager.__cm_talent_hooked = nil
    end

    -- 1c. 还原建筑列表过滤hook（旧版本残留，新版本已移除但需清理）
    local BCM = g_LBuildingCardManager
    if BCM and BCM.__cm_filter_hooked then
        if BCM.__cm_orig_GetBuildingCards ~= nil then
            BCM.GetBuildingCards = BCM.__cm_orig_GetBuildingCards
        end
        if BCM.__cm_orig_GetTypedBuildingCards ~= nil then
            BCM.GetTypedBuildingCards = BCM.__cm_orig_GetTypedBuildingCards
        end
        BCM.__cm_orig_GetBuildingCards = nil
        BCM.__cm_orig_GetTypedBuildingCards = nil
        BCM.__cm_filter_hooked = nil
        BCM.__cm_max_level = nil
        BCM.__cm_has_level = nil
    end

    -- 2. 还原资源hook
    local BWM = g_BuildingWorldModule
    if BWM and BWM.BuildingMgr then
        local mgr = BWM.BuildingMgr
        local mt = getmetatable(mgr)
        if mt and mt.__index then
            local cls = mt.__index
            if cls.__cm_res_hooked then
                if cls.__cm_orig_ConsumeResource ~= nil then cls.ConsumeResource = cls.__cm_orig_ConsumeResource else cls.ConsumeResource = nil end
                if cls.__cm_orig__ConsumeResource ~= nil then cls._ConsumeResource = cls.__cm_orig__ConsumeResource else cls._ConsumeResource = nil end
                if cls.__cm_orig_CheckCanCreate ~= nil then cls.CheckCanCreateBuilding = cls.__cm_orig_CheckCanCreate else cls.CheckCanCreateBuilding = nil end
                if cls.__cm_orig_CheckCanUpgrade ~= nil then cls.CheckCanUpgradeBuilding = cls.__cm_orig_CheckCanUpgrade else cls.CheckCanUpgradeBuilding = nil end
                cls.__cm_orig_ConsumeResource = nil
                cls.__cm_orig__ConsumeResource = nil
                cls.__cm_orig_CheckCanCreate = nil
                cls.__cm_orig_CheckCanUpgrade = nil
                cls.__cm_res_hooked = nil
            end
        end
    end

    -- 还原GM标志
    if g_GameWorld then
        g_GameWorld.bGMBuildFast = false
        g_GameWorld.bGMIgnoreTileLimit = false
        g_GameWorld.bGMCanOperateAllBuildingAndRoad = false
    end

    -- 还原建筑灾害伤害hook
    pcall(function()
        if g_camp and g_blockMgr then
            local block = g_camp:GetCampBlock()
            if block and block.GetAllBuildings then
                local buildings = block:GetAllBuildings()
                if buildings and #buildings > 0 then
                    local b = buildings[1]
                    local bmt = getmetatable(b)
                    if bmt and bmt.__index then
                        local bcls = bmt.__index
                        if bcls.__cm_disaster_hooked then
                            if bcls.__cm_orig_DisasterSubHP ~= nil then
                                bcls.DisasterSubHP = bcls.__cm_orig_DisasterSubHP
                            else
                                bcls.DisasterSubHP = nil
                            end
                            bcls.__cm_orig_DisasterSubHP = nil
                            bcls.__cm_disaster_hooked = nil
                        end
                    end
                end
            end
        end
    end)

    -- 还原不触发灾害hook
    if g_camp and g_blockMgr then
        local block = g_camp:GetCampBlock()
        if block then
            local mt = getmetatable(block)
            if mt and mt.__index then
                local cls = mt.__index
                if cls.__cm_trigger_disaster_hooked then
                    if cls.__cm_orig_TriggerDisaster ~= nil then
                        cls.TriggerDisaster = cls.__cm_orig_TriggerDisaster
                    else
                        cls.TriggerDisaster = nil
                    end
                    cls.__cm_orig_TriggerDisaster = nil
                    cls.__cm_trigger_disaster_hooked = nil
                end
            end
        end
    end

    -- 还原道路连接豁免hook
    local BWM2 = g_BuildingWorldModule
    if BWM2 and BWM2.BuildingMgr then
        local mgr2 = BWM2.BuildingMgr
        local mt2 = getmetatable(mgr2)
        if mt2 and mt2.__index then
            local cls2 = mt2.__index
            if cls2.__cm_road_hooked then
                if cls2.__cm_orig_ModifyCheckRoadFlag ~= nil then
                    cls2.ModifyCheckRoadFlag = cls2.__cm_orig_ModifyCheckRoadFlag
                else
                    cls2.ModifyCheckRoadFlag = nil
                end
                cls2.__cm_orig_ModifyCheckRoadFlag = nil
                cls2.__cm_road_hooked = nil
            end
        end
    end

    -- 还原人口不分类别hook
    if g_camp and g_blockMgr then
        local block2 = g_camp:GetCampBlock()
        if block2 then
            local mt3 = getmetatable(block2)
            if mt3 and mt3.__index then
                local cls3 = mt3.__index
                if cls3.__cm_pop_hooked then
                    if cls3.__cm_orig_GetPopulation ~= nil then
                        cls3.GetPopulation = cls3.__cm_orig_GetPopulation
                    else
                        cls3.GetPopulation = nil
                    end
                    cls3.__cm_orig_GetPopulation = nil
                    cls3.__cm_pop_hooked = nil
                end
            end
        end
    end

    -- 3. 还原ModifySourceValue
    if g_camp and g_camp.__cm_msv_hooked then
        if g_camp.__cm_orig_msv ~= nil then
            g_camp.ModifySourceValue = g_camp.__cm_orig_msv
        else
            g_camp.ModifySourceValue = nil
        end
        g_camp.__cm_orig_msv = nil
        g_camp.__cm_msv_hooked = nil
    end

    -- 4. 还原鸿业hook
    if g_camp and g_camp.GetCampBoomModule then
        local boom = g_camp:GetCampBoomModule()
        if boom then
            local mt = getmetatable(boom)
            if mt and mt.__index then
                local cls = mt.__index
                if cls.__cm_boom_hooked then
                    if cls.__cm_boom_orig_is ~= nil then cls.IsSatisfied = cls.__cm_boom_orig_is else cls.IsSatisfied = nil end
                    if cls.__cm_boom_orig_get ~= nil then cls.GetBoom = cls.__cm_boom_orig_get else cls.GetBoom = nil end
                    cls.__cm_boom_orig_is = nil
                    cls.__cm_boom_orig_get = nil
                    cls.__cm_boom_hooked = nil
                end
            end
        end
    end

    -- 5. 还原全部游戏功能状态
    if g_camp and g_camp.__cm_func_saved and g_camp.__cm_orig_func_states then
        if g_FunctionManager then
            pcall(function()
                for funcId, state in pairs(g_camp.__cm_orig_func_states) do
                    pcall(function() g_FunctionManager:SetFucntionState(funcId, state) end)
                end
            end)
        end
        g_camp.__cm_orig_func_states = nil
        g_camp.__cm_func_saved = nil
    end

    return true
end)
return ok and err or false
"""

LUA_GET_STATUS = r"""
local ok, err = pcall(function()
    local status = {}
    status.creative_mode = g_bCreativeMode or false
    -- 鸿业等级
    if g_camp and g_camp.GetCampBoomModule then
        local boom = g_camp:GetCampBoomModule()
        if boom and boom.GetBoom then
            status.boom_level = boom:GetBoom()
        end
        -- 鸿业称号
        if boom and boom.GetCurTitle then
            local ok2, title = pcall(function() return boom:GetCurTitle() end)
            if ok2 and title then status.boom_title = title end
        end
        -- 繁荣度等级
        if boom and boom.GetProsperityLevel then
            local ok2, pl = pcall(function() return boom:GetProsperityLevel() end)
            if ok2 and pl then status.prosperity_level = pl end
        end
    end
    -- 资源（全部资源类型，注意id=2矿产 id=3木料）
    if g_camp and g_camp.m_tbSource then
        status.money = g_camp.m_tbSource[1] or 0
        status.mineral = g_camp.m_tbSource[2] or 0
        status.wood = g_camp.m_tbSource[3] or 0
        status.cloth = g_camp.m_tbSource[4] or 0
        status.food = g_camp.m_tbSource[5] or 0
        status.water = g_camp.m_tbSource[6] or 0
        status.population = g_camp.m_tbSource[7] or 0
        status.salt = g_camp.m_tbSource[19] or 0
        status.wine = g_camp.m_tbSource[20] or 0
        status.essence = g_camp.m_tbSource[25] or 0
    end
    -- 幸福度（知名度字段名不固定，暂不查询）
    if g_camp then
        if g_camp.GetHappiness then
            local h = g_camp:GetHappiness()
            if h then status.happiness = h end
        end
    end
    -- 建筑卡片统计
    if g_LBuildingCardManager and g_LBuildingCardManager.tabBuildingCards then
        local count = 0
        local unlocked = 0
        for _, c in pairs(g_LBuildingCardManager.tabBuildingCards) do
            count = count + 1
            if c.GetUnlockState and c:GetUnlockState() then
                unlocked = unlocked + 1
            end
        end
        status.card_count = count
        status.card_unlocked = unlocked
    end
    -- 时间速度
    if g_Time and g_Time.GetTimeSpeed then
        local ok2, spd = pcall(function() return g_Time:GetTimeSpeed() end)
        if ok2 and spd then status.time_speed = spd end
    end
    -- 当前季节
    if g_Time and g_Time.GetSeason then
        local ok2, s = pcall(function() return g_Time:GetSeason() end)
        if ok2 then status.season = s end
    end
    -- 序列化为JSON字符串（手动序列化，不依赖cjson）
    local function escape_str(s)
        -- JSON字符串转义：处理双引号、反斜杠、换行、回车、制表符
        local r = string.gsub(s, '\\', '\\\\')
        r = string.gsub(r, '"', '\\"')
        r = string.gsub(r, '\n', '\\n')
        r = string.gsub(r, '\r', '\\r')
        r = string.gsub(r, '\t', '\\t')
        return r
    end
    local function val(v)
        if type(v) == "boolean" then return v and "true" or "false" end
        if type(v) == "number" then return tostring(v) end
        if type(v) == "string" then return '"' .. escape_str(v) .. '"' end
        return "null"
    end
    local json = "{"
    local first = true
    for k, v in pairs(status) do
        if not first then json = json .. "," end
        first = false
        json = json .. '"' .. k .. '":' .. val(v)
    end
    json = json .. "}"
    return json
end)
if not ok then return '{"error":true}' end
return err
"""

# ========== 建筑解锁诊断 Lua 脚本 ==========

LUA_DIAGNOSE_UNLOCK = r"""
local ok, err = pcall(function()
    local lines = {}
    table.insert(lines, "========== 建筑解锁诊断报告 ==========")
    
    local BCM = g_LBuildingCardManager
    if not BCM then
        table.insert(lines, "[错误] g_LBuildingCardManager 不存在")
        return table.concat(lines, "\n")
    end
    
    -- 1. 统计全局卡片解锁状态
    table.insert(lines, "")
    table.insert(lines, "【1. 全局建筑卡片统计】")
    local total = 0
    local unlocked = 0
    local locked = 0
    local locked_list = {}
    local level1_count = 0
    local level1_unlocked = 0
    
    if BCM.tabBuildingCards then
        for key, card in pairs(BCM.tabBuildingCards) do
            total = total + 1
            local isUnlocked = false
            if card.GetUnlockState then
                isUnlocked = card:GetUnlockState()
            end
            if isUnlocked then
                unlocked = unlocked + 1
            else
                locked = locked + 1
                if #locked_list < 20 then
                    local name = "unknown"
                    if card.GetName then name = card:GetName() end
                    local g, d, p, l = 0, 0, 0, 0
                    if card.GetGDPL then
                        g, d, p, l = card:GetGDPL()
                    elseif card.G then g, d, p, l = card.G, card.D, card.P, card.L end
                    table.insert(locked_list, string.format("  %s (G=%d,D=%d,P=%d,L=%d)", name, g, d, p, l))
                end
            end
            if card.L and card.L == 1 then
                level1_count = level1_count + 1
                if isUnlocked then level1_unlocked = level1_unlocked + 1 end
            end
        end
    end
    
    table.insert(lines, string.format("  总卡片数: %d", total))
    table.insert(lines, string.format("  已解锁: %d", unlocked))
    table.insert(lines, string.format("  未解锁: %d", locked))
    table.insert(lines, string.format("  Lv.1卡片: %d (已解锁: %d)", level1_count, level1_unlocked))
    
    if #locked_list > 0 then
        table.insert(lines, "  未解锁卡片（前20个）:")
        for _, s in ipairs(locked_list) do
            table.insert(lines, s)
        end
    end
    
    -- 2. 天赋管理器状态
    table.insert(lines, "")
    table.insert(lines, "【2. 天赋管理器】")
    local TM = g_TalentManager
    if not TM then
        table.insert(lines, "  [错误] g_TalentManager 不存在")
    else
        table.insert(lines, "  g_TalentManager 存在")
        -- 检查方法类型
        if TM.CheckTalentIsActive then
            table.insert(lines, string.format("  CheckTalentIsActive 类型: %s", type(TM.CheckTalentIsActive)))
        else
            table.insert(lines, "  [警告] CheckTalentIsActive 方法不存在")
        end
        if TM.CheckIsUnlockBuildingCard then
            table.insert(lines, string.format("  CheckIsUnlockBuildingCard 类型: %s", type(TM.CheckIsUnlockBuildingCard)))
        end
        if TM.CheckUnlockBuildingCardTalentIdIsUnlock then
            table.insert(lines, string.format("  CheckUnlockBuildingCardTalentIdIsUnlock 类型: %s", type(TM.CheckUnlockBuildingCardTalentIdIsUnlock)))
        end
        -- 测试hook
        table.insert(lines, "  --- hook测试 ---")
        local orig = TM.CheckTalentIsActive
        TM.CheckTalentIsActive = function() return true end
        local test_result = TM:CheckTalentIsActive(1,1,1,1)
        table.insert(lines, string.format("  hook后CheckTalentIsActive返回: %s", tostring(test_result)))
        -- 还原
        TM.CheckTalentIsActive = orig
        table.insert(lines, "  已还原原始方法")
    end
    
    -- 3. 方案卡状态
    table.insert(lines, "")
    table.insert(lines, "【3. 当前方案卡】")
    local OM = g_LOfficeManager
    if not OM then
        table.insert(lines, "  [错误] g_LOfficeManager 不存在")
    else
        local office = nil
        if OM.GetAdviserOfficeInCamp then
            office = OM:GetAdviserOfficeInCamp()
        elseif OM.GetAdviserOfficeByBlockGDPL and g_blockMgr then
            local block = g_blockMgr:GetSelectedBlock()
            if block then
                office = OM:GetAdviserOfficeByBlockGDPL(block.nId, 0, 0, 0)
            end
        end
        
        if not office then
            table.insert(lines, "  [警告] 未找到当前区块的事务所/方案卡")
        else
            local scheme = nil
            if office.GetScheme then
                scheme = office:GetScheme()
            end
            if not scheme then
                table.insert(lines, "  [警告] 方案卡不存在")
            else
                local scheme_buildings = nil
                if scheme.GetSchemeBuildings then
                    scheme_buildings = scheme:GetSchemeBuildings()
                end
                if scheme_buildings then
                    local s_total = #scheme_buildings
                    local s_unlocked = 0
                    local s_locked = 0
                    for _, card in ipairs(scheme_buildings) do
                        if card.GetUnlockState and card:GetUnlockState() then
                            s_unlocked = s_unlocked + 1
                        else
                            s_locked = s_locked + 1
                        end
                    end
                    table.insert(lines, string.format("  方案卡建筑数: %d", s_total))
                    table.insert(lines, string.format("  已解锁: %d", s_unlocked))
                    table.insert(lines, string.format("  未解锁: %d", s_locked))
                    
                    -- 列出前10个未解锁的
                    local s_locked_list = {}
                    for _, card in ipairs(scheme_buildings) do
                        if not (card.GetUnlockState and card:GetUnlockState()) then
                            if #s_locked_list < 10 then
                                local name = "unknown"
                                if card.GetName then name = card:GetName() end
                                table.insert(s_locked_list, "    " .. name)
                            end
                        end
                    end
                    if #s_locked_list > 0 then
                        table.insert(lines, "  方案中未解锁建筑（前10个）:")
                        for _, s in ipairs(s_locked_list) do
                            table.insert(lines, s)
                        end
                    end
                else
                    table.insert(lines, "  [警告] GetSchemeBuildings 返回空")
                end
            end
        end
    end
    
    -- 4. 卡片方法hook测试
    table.insert(lines, "")
    table.insert(lines, "【4. 卡片方法hook测试】")
    if BCM.tabBuildingCards then
        -- 找第一张卡片测试
        local test_card = nil
        for _, card in pairs(BCM.tabBuildingCards) do
            test_card = card
            break
        end
        if test_card then
            local name = "unknown"
            if test_card.GetName then name = test_card:GetName() end
            table.insert(lines, string.format("  测试卡片: %s", name))
            table.insert(lines, string.format("  GetUnlockState 类型: %s", type(test_card.GetUnlockState)))
            table.insert(lines, string.format("  SetUnlockState 类型: %s", type(test_card.SetUnlockState)))
            
            -- 测试 hook SetUnlockState
            local orig_set = test_card.SetUnlockState
            local hook_called = false
            test_card.SetUnlockState = function(self, state)
                hook_called = true
                if orig_set then orig_set(self, true) end
            end
            test_card:SetUnlockState(false)
            table.insert(lines, string.format("  hook SetUnlockState后调用SetUnlockState(false): hook被调用=%s, 实际状态=%s", 
                tostring(hook_called), tostring(test_card:GetUnlockState())))
            -- 还原
            test_card.SetUnlockState = orig_set
            table.insert(lines, "  已还原原始SetUnlockState")
        end
    end
    
    -- 5. 检测当前创造模式hook状态
    table.insert(lines, "")
    table.insert(lines, "【5. 创造模式hook状态】")
    table.insert(lines, string.format("  g_bCreativeMode = %s", tostring(g_bCreativeMode or false)))
    
    local hooked_count = 0
    if BCM.tabBuildingCards then
        for _, card in pairs(BCM.tabBuildingCards) do
            if card.__cm_card_hooked then
                hooked_count = hooked_count + 1
            end
        end
    end
    table.insert(lines, string.format("  已hook的卡片数: %d", hooked_count))
    
    if TM and TM.__cm_talent_hooked then
        table.insert(lines, "  天赋管理器: 已hook")
    else
        table.insert(lines, "  天赋管理器: 未hook")
    end
    
    if BCM and BCM.__cm_filter_hooked then
        table.insert(lines, "  建筑过滤器: 已hook（只显示最高等级）")
    else
        table.insert(lines, "  建筑过滤器: 未hook")
    end
    
    table.insert(lines, "")
    table.insert(lines, "========== 诊断结束 ==========")
    
    return table.concat(lines, "\\n")
end)
if not ok then return "诊断失败: " .. tostring(err) end
return err
"""


