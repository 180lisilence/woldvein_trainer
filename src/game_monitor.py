"""
woldvein Trainer v0.3 - 游戏监控模块

功能说明：
    实时监控游戏进程状态、内存CPU占用、运行模式、存档状态、
    Lua错误日志、崩溃检测和自动分析。

核心功能：
    - 进程监控：检测游戏是否运行，获取PID
    - 内存CPU：读取游戏进程的内存和CPU占用
    - 模式检测：判断原版模式/创造模式
    - 存档状态：扫描存档文件，检测加密标记
    - Lua错误检测：实时分析游戏日志，提取Lua错误
    - 崩溃检测：检测游戏进程异常退出，分析崩溃原因
    - SDK日志过滤：18项黑名单过滤XGSDK/Steam网络日志

技术要点：
    - 游戏未运行时检测间隔5秒，运行时1秒
    - 日志尾部读取（不全量读取大文件）
    - TRANSLATE_V标记分块搜索
    - set_game_root()动态设置游戏路径
"""
import os
import sys
import time
import re
import threading
from datetime import datetime

from .logger import log, log_success, log_error, log_warning
from .constants import DEFAULT_GAME_PATH, GAME_EXE_REL, SIM_COMMON_REL

# 路径变量读写锁：保护 set_game_root 与监控线程的并发读写
# 避免监控线程读到写了一半的全局变量（GAME_ROOT 已更新但 SCATTER_DIR 还是旧的）
_path_lock = threading.Lock()

# 游戏路径配置（可通过 set_game_root() 动态更新）
GAME_ROOT = DEFAULT_GAME_PATH
GAME_BIN = os.path.join(GAME_ROOT, "bin64")
GAME_PROCESS_NAME = os.path.basename(GAME_EXE_REL)
STEAM_API_DLL = os.path.join(GAME_BIN, "steam_api64.dll")
SAVE_DIR = os.path.join(GAME_ROOT, "storage", "offlineuser")
LOG_DIR = os.path.join(GAME_ROOT, "logs", "core")
SCATTER_DIR = os.path.join(GAME_ROOT, SIM_COMMON_REL)


def set_game_root(root):
    """动态设置游戏根目录（从配置传入）

    线程安全：用 _path_lock 保护，确保监控线程不会读到写了一半的路径变量。
    建议在监控启动前调用，避免运行中修改导致监控状态错乱。
    """
    global GAME_ROOT, GAME_BIN, STEAM_API_DLL, SAVE_DIR, LOG_DIR, SCATTER_DIR
    if not root or not os.path.isdir(root):
        log_warning(f"游戏路径无效，使用默认: {root}")
        return False
    # 先在新值中计算好所有派生路径，再一次性持锁赋值，缩短锁持有时间
    new_bin = os.path.join(root, "bin64")
    new_steam = os.path.join(new_bin, "steam_api64.dll")
    new_save = os.path.join(root, "storage", "offlineuser")
    new_log = os.path.join(root, "logs", "core")
    new_scatter = os.path.join(root, "sim_common")
    with _path_lock:
        GAME_ROOT = root
        GAME_BIN = new_bin
        STEAM_API_DLL = new_steam
        SAVE_DIR = new_save
        LOG_DIR = new_log
        SCATTER_DIR = new_scatter
    log(f"游戏路径已设置: {GAME_ROOT}")
    return True


def _get_paths():
    """线程安全地读取当前所有路径变量（监控线程使用）"""
    with _path_lock:
        return (GAME_ROOT, GAME_BIN, STEAM_API_DLL, SAVE_DIR, LOG_DIR, SCATTER_DIR)


class GameMonitor:
    """游戏监控器"""

    def __init__(self):
        self.running = False
        self._thread = None
        self._callbacks = {}
        self._game_start_time = None
        self._was_running = False
        self._current_pid = None
        self.crash_history = []
        self._last_log_size = 0
        self._find_pid_warned = False  # 进程查找失败是否已警告（避免每轮刷屏）

    def set_callback(self, event, callback):
        """设置事件回调"""
        self._callbacks[event] = callback

    def _emit(self, event, data=None):
        """触发事件"""
        if event in self._callbacks:
            try:
                self._callbacks[event](data)
            except Exception as e:
                log_error(f"监控回调异常: {e}")

    def start(self):
        """启动监控"""
        if self.running:
            return
        self.running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        log_success("游戏监控已启动")

    def stop(self):
        """停止监控"""
        self.running = False
        if self._thread:
            self._thread.join(timeout=2)
        log("游戏监控已停止")

    def _monitor_loop(self):
        """监控主循环"""
        while self.running:
            try:
                # 检测进程
                pid = self._find_game_pid()

                if pid:
                    if not self._was_running:
                        # 游戏刚启动
                        self._current_pid = pid
                        self._game_start_time = datetime.now()
                        self._was_running = True
                        self._last_log_size = 0
                        log_success(f"游戏启动，PID={pid}")
                        self._emit("game_start", {"pid": pid})

                    # 实时状态（游戏运行时每秒更新）
                    status = self._get_running_status(pid)
                    self._emit("status_update", status)
                    time.sleep(1)
                else:
                    if self._was_running:
                        # 游戏刚崩溃/退出
                        self._was_running = False
                        elapsed = (datetime.now() - self._game_start_time).total_seconds() if self._game_start_time else 0
                        log_warning(f"游戏进程消失（运行了 {self._format_duration(elapsed)}）")

                        # 分析崩溃原因
                        crash_info = self._analyze_crash()
                        crash_info["pid"] = self._current_pid
                        crash_info["elapsed"] = elapsed
                        self.crash_history.append(crash_info)
                        if len(self.crash_history) > 10:
                            self.crash_history.pop(0)

                        self._emit("game_crash", crash_info)
                        self._current_pid = None
                        self._game_start_time = None
                    else:
                        # 游戏未运行，降低检测频率到5秒，减少CPU占用
                        self._emit("waiting", None)
                        time.sleep(5)
                        continue

            except Exception as e:
                log_error(f"监控循环异常: {e}")
                time.sleep(2)

    def _find_game_pid(self):
        """查找游戏进程PID"""
        try:
            import psutil
            for proc in psutil.process_iter(["pid", "name"]):
                if proc.info["name"] and proc.info["name"].lower() == GAME_PROCESS_NAME.lower():
                    return proc.info["pid"]
        except Exception as e:
            if not self._find_pid_warned:
                log_warning(f"查找游戏进程失败: {e}（psutil不可用或权限不足）")
                self._find_pid_warned = True
        return None

    def _get_running_status(self, pid):
        """获取运行中状态"""
        status = {
            "pid": pid,
            "running": True,
            "memory_mb": 0,
            "cpu_percent": 0,
            "elapsed": 0,
            "mode": "未知",
            "lua_errors": [],
            "latest_log": "",
        }

        # 内存/CPU
        try:
            import psutil
            proc = psutil.Process(pid)
            try:
                status["memory_mb"] = proc.memory_full_info().uss / (1024 * 1024)
            except Exception:
                status["memory_mb"] = proc.memory_info().rss / (1024 * 1024)
            status["cpu_percent"] = proc.cpu_percent(interval=None)  # 非阻塞，首次返回0
        except Exception:
            pass

        # 运行时长
        if self._game_start_time:
            status["elapsed"] = (datetime.now() - self._game_start_time).total_seconds()

        # 模式
        status["mode"] = self._detect_mode()

        # 日志
        log_path = self._get_latest_log()
        if log_path:
            try:
                current_size = os.path.getsize(log_path)
                if current_size != self._last_log_size:
                    self._last_log_size = current_size
                    lines = self._read_log_tail(log_path, 30)
                    status["lua_errors"] = self._find_lua_errors(lines)
                    status["latest_log"] = lines[-1].strip() if lines else ""
            except Exception:
                pass

        return status

    def _detect_mode(self):
        """检测当前模式（线程安全读取全局路径）"""
        _, _, steam_api_dll, _, _, scatter_dir = _get_paths()
        if not os.path.exists(steam_api_dll):
            return "未知（steam_api64.dll 缺失）"
        size = os.path.getsize(steam_api_dll)
        if size > 1024 * 1024:
            scatter_exists = os.path.exists(scatter_dir)
            if scatter_exists:
                return "创造模式（Goldberg）"
            return "创造模式（Goldberg，散文件缺失）"
        else:
            return "原版模式"

    def _get_latest_log(self):
        """获取最新日志文件（线程安全读取 LOG_DIR）"""
        _, _, _, _, log_dir, _ = _get_paths()
        if not os.path.exists(log_dir):
            return None
        latest_log = None
        latest_mtime = 0
        try:
            for entry in os.listdir(log_dir):
                entry_path = os.path.join(log_dir, entry)
                if os.path.isdir(entry_path):
                    for f in os.listdir(entry_path):
                        if f.endswith(".log"):
                            fpath = os.path.join(entry_path, f)
                            mtime = os.path.getmtime(fpath)
                            if mtime > latest_mtime:
                                latest_mtime = mtime
                                latest_log = fpath
                elif entry.endswith(".log"):
                    mtime = os.path.getmtime(entry_path)
                    if mtime > latest_mtime:
                        latest_mtime = mtime
                        latest_log = entry_path
        except Exception:
            pass
        return latest_log

    def _read_log_tail(self, log_path, lines=50):
        """读取日志最后N行（从文件末尾反向读取，避免全量加载）"""
        if not log_path or not os.path.exists(log_path):
            return []
        try:
            file_size = os.path.getsize(log_path)
            # 估算每行平均长度，读取足够的尾部字节
            block_size = min(file_size, max(lines * 200, 8192))
            with open(log_path, "rb") as f:
                f.seek(-block_size, 2)
                data = f.read()
            text = data.decode("utf-8", errors="replace")
            all_lines = text.splitlines()
            return all_lines[-lines:]
        except Exception:
            return []

    def _find_lua_errors(self, lines):
        """查找Lua错误（过滤SDK/网络日志）"""
        errors = []
        error_keywords = ["LUA ERROR", "lua error", "ERROR]", "Exception",
                          "attempt to", "nil value", "fatal", "FATAL", "Traceback", "OnCrash"]
        # 黑名单：SDK/网络/更新相关日志，不视为错误
        blacklist = ["XGSDK", "steam_service", "Get ticket", "steam_api",
                     "network", "http", "tcp", "udp", "socket", "connect",
                     "download", "update", "version", "login", "auth",
                     "XGLogCallback", "OnXGLog", "Steamworks"]
        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                continue
            # 黑名单过滤
            line_lower = line_stripped.lower()
            skip = False
            for bl in blacklist:
                if bl.lower() in line_lower:
                    skip = True
                    break
            if skip:
                continue
            for kw in error_keywords:
                if kw.lower() in line_lower:
                    errors.append(line_stripped[:200])
                    break
        return errors

    def _extract_lua_stacktrace(self, lines):
        """提取Lua调用栈"""
        stacktrace = []
        in_stacktrace = False
        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                continue
            if "stack traceback:" in line_stripped.lower():
                in_stacktrace = True
                stacktrace.append(line_stripped)
                continue
            if in_stacktrace:
                if (".lua:" in line_stripped or "[C]:" in line_stripped or
                    "in function" in line_stripped or "in main chunk" in line_stripped):
                    stacktrace.append(line_stripped)
                else:
                    if len(stacktrace) > 1:
                        break
        return stacktrace

    def _analyze_stacktrace(self, stacktrace):
        """分析调用栈"""
        if not stacktrace:
            return {"crash_location": "未知", "crash_phase": "未知", "key_files": [], "key_functions": []}

        key_files = []
        key_functions = []
        for frame in stacktrace:
            file_match = re.search(r"[\w/]+\.lua", frame)
            if file_match:
                fname = file_match.group(0).split("/")[-1]
                if fname not in key_files:
                    key_files.append(fname)
            func_match = re.search(r"in function '([^']+)'", frame)
            if func_match:
                fname = func_match.group(1)
                if fname not in key_functions:
                    key_functions.append(fname)

        crash_location = stacktrace[1][:150] if len(stacktrace) >= 2 else "未知"

        all_text = " ".join(stacktrace).lower()
        if "ingame_state" in all_text or "createscene" in all_text or "scene.lua" in all_text:
            crash_phase = "进入游戏场景时"
        elif "archive" in all_text or "storage" in all_text or "save" in all_text:
            crash_phase = "存档读写时"
        elif "game_world" in all_text or "gameworld" in all_text:
            crash_phase = "游戏世界逻辑更新时"
        elif "building" in all_text:
            crash_phase = "建筑系统逻辑时"
        elif "xgagent" in all_text:
            crash_phase = "XGAgent系统时"
        elif "ui" in all_text or "coui" in all_text:
            crash_phase = "UI渲染时"
        else:
            crash_phase = "游戏运行时"

        return {
            "crash_location": crash_location,
            "crash_phase": crash_phase,
            "key_files": key_files[:5],
            "key_functions": key_functions[:5],
        }

    def _get_suggestions(self, stack_analysis):
        """获取修复建议"""
        suggestions = []
        phase = stack_analysis.get("crash_phase", "")
        all_keywords = " ".join(stack_analysis.get("key_files", []) + stack_analysis.get("key_functions", [])).lower()

        if "进入游戏场景" in phase or "createscene" in all_keywords:
            suggestions.extend([
                "可能是存档数据不完整，删除旧存档重新新建",
                "检查散文件是否与当前游戏版本兼容",
            ])
        elif "存档" in phase or "archive" in all_keywords:
            suggestions.extend([
                "存档可能已损坏，删除损坏存档重新新建",
                "运行存档修复功能",
            ])
        elif "游戏世界" in phase or "game_world" in all_keywords:
            suggestions.extend([
                "检查game_world.lua散文件是否与游戏版本兼容",
                "查看游戏日志logs/core/中的详细Lua错误",
            ])
        elif "建筑" in phase or "building" in all_keywords:
            suggestions.extend([
                "检查building.lua散文件是否与游戏版本兼容",
            ])
        elif "ui" in phase or "coui" in all_keywords:
            suggestions.extend([
                "可能是游戏资源问题，验证游戏文件完整性",
            ])

        if not suggestions:
            suggestions.extend([
                "查看游戏日志logs/core/获取详细错误信息",
                "尝试恢复原版模式确认是否为散文件问题",
            ])

        return suggestions[:5]

    def _analyze_crash(self):
        """分析崩溃原因"""
        log_path = self._get_latest_log()
        if not log_path:
            return {"reason": "未找到日志文件", "errors": [], "stacktrace": [], "stack_analysis": {}, "suggestions": []}

        lines = self._read_log_tail(log_path, 200)
        if not lines:
            return {"reason": "日志目录为空或文件大小为0（请检查 game_path 配置）", "errors": [], "stacktrace": [], "stack_analysis": {}, "suggestions": []}

        errors = self._find_lua_errors(lines)
        stacktrace = self._extract_lua_stacktrace(lines)
        stack_analysis = self._analyze_stacktrace(stacktrace)
        suggestions = self._get_suggestions(stack_analysis)

        if errors:
            reason = errors[-1][:200]
        else:
            last_lines = [l.strip() for l in lines[-10:] if l.strip()]
            reason = f"日志中未发现明显错误，最后一行：{last_lines[-1][:150]}" if last_lines else "可能是系统级崩溃"

        return {
            "time": datetime.now(),
            "reason": reason,
            "errors": errors[-3:],
            "stacktrace": stacktrace,
            "stack_analysis": stack_analysis,
            "suggestions": suggestions,
        }

    def get_save_files(self):
        """获取存档列表（线程安全读取 SAVE_DIR）"""
        _, _, _, save_dir, _, _ = _get_paths()
        saves = []
        if not os.path.exists(save_dir):
            return saves
        try:
            for f in os.listdir(save_dir):
                if f.endswith(".boh"):
                    path = os.path.join(save_dir, f)
                    size = os.path.getsize(path)
                    mtime = os.path.getmtime(path)
                    has_translate = False
                    try:
                        with open(path, "rb") as fh:
                            # 分块搜索整个文件（避免大文件内存问题）
                            marker = b"TRANSLATE_V"
                            chunk_size = 65536
                            overlap = len(marker) - 1
                            prev = b""
                            while True:
                                chunk = fh.read(chunk_size)
                                if not chunk:
                                    break
                                data = prev + chunk
                                if marker in data:
                                    has_translate = True
                                    break
                                prev = chunk[-overlap:] if len(chunk) >= overlap else chunk
                    except Exception:
                        pass
                    saves.append({
                        "name": f,
                        "size_kb": size / 1024,
                        "mtime": datetime.fromtimestamp(mtime),
                        "has_translate": has_translate,
                        "status": "正常" if (size > 700 * 1024 and has_translate) else ("缺标记" if not has_translate else "偏小"),
                    })
            saves.sort(key=lambda x: x["mtime"], reverse=True)
        except Exception:
            pass
        return saves

    @staticmethod
    def _format_duration(seconds):
        """格式化运行时长"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        if hours > 0:
            return f"{hours}时{minutes}分{secs}秒"
        elif minutes > 0:
            return f"{minutes}分{secs}秒"
        else:
            return f"{secs}秒"


# 全局监控器实例
game_monitor = GameMonitor()

