"""
woldvein Trainer v0.4.6 - 日志增强模块

增强日志系统功能：
    1. 日志分级（DEBUG/INFO/WARNING/ERROR/CRITICAL）
    2. 日志滚动（按大小分割日志文件）
    3. 日志过滤（按模块/级别/关键词过滤）
    4. 日志搜索
    5. 日志导出
    6. 日志统计

与现有 logger.py 的关系：
    - logger.py 提供基础 log/log_success/log_error 函数
    - log_enhancer.py 在此基础上提供增强功能

使用方式：
    from .log_enhancer import EnhancedLogger, get_enhanced_logger
    logger = get_enhanced_logger()
    logger.debug("调试信息")
    logger.info("普通信息")
    logger.warning("警告")
    logger.error("错误")
    logger.critical("严重错误")
"""
import os
import sys
import re
import time
import json
import threading
import datetime
from collections import deque

from .logger import log, log_success, log_error, log_warning

# 日志级别
DEBUG = 10
INFO = 20
WARNING = 30
ERROR = 40
CRITICAL = 50

LEVEL_NAMES = {
    DEBUG: "DEBUG",
    INFO: "INFO",
    WARNING: "WARNING",
    ERROR: "ERROR",
    CRITICAL: "CRITICAL",
}

# 默认配置
DEFAULT_MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
DEFAULT_BACKUP_COUNT = 5
DEFAULT_MEMORY_LOG_SIZE = 1000  # 内存中保留的日志条数


class LogEntry:
    """单条日志"""

    def __init__(self, level, message, module="", timestamp=None):
        self.level = level
        self.message = message
        self.module = module
        self.timestamp = timestamp or datetime.datetime.now()

    def to_dict(self):
        return {
            "level": LEVEL_NAMES.get(self.level, "UNKNOWN"),
            "level_code": self.level,
            "message": self.message,
            "module": self.module,
            "timestamp": self.timestamp.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
        }

    def format(self, include_timestamp=True, include_level=True):
        """格式化为字符串"""
        parts = []
        if include_timestamp:
            parts.append(self.timestamp.strftime("%H:%M:%S.%f")[:-3])
        if include_level:
            parts.append(f"[{LEVEL_NAMES.get(self.level, '?')}]")
        if self.module:
            parts.append(f"({self.module})")
        parts.append(self.message)
        return " ".join(parts)


class LogFilter:
    """日志过滤器"""

    def __init__(self, min_level=DEBUG, modules=None, keywords=None, exclude_keywords=None):
        """
        参数：
            min_level: 最低日志级别
            modules: 只显示这些模块的日志（None 表示全部）
            keywords: 只显示包含这些关键词的日志（None 表示全部）
            exclude_keywords: 排除包含这些关键词的日志
        """
        self.min_level = min_level
        self.modules = set(modules) if modules else None
        self.keywords = keywords or []
        self.exclude_keywords = exclude_keywords or []

    def matches(self, entry):
        """检查日志是否匹配过滤条件"""
        if entry.level < self.min_level:
            return False
        if self.modules and entry.module not in self.modules:
            return False
        if self.keywords:
            if not any(kw in entry.message for kw in self.keywords):
                return False
        if self.exclude_keywords:
            if any(kw in entry.message for kw in self.exclude_keywords):
                return False
        return True


class EnhancedLogger:
    """增强日志器"""

    def __init__(self, log_dir=None, max_file_size=DEFAULT_MAX_FILE_SIZE,
                 backup_count=DEFAULT_BACKUP_COUNT, memory_size=DEFAULT_MEMORY_LOG_SIZE):
        """
        参数：
            log_dir: 日志目录
            max_file_size: 单个日志文件最大大小（字节）
            backup_count: 保留的备份文件数
            memory_size: 内存中保留的日志条数
        """
        self._log_dir = log_dir or self._default_log_dir()
        self._max_file_size = max_file_size
        self._backup_count = backup_count
        self._memory_logs = deque(maxlen=memory_size)
        self._lock = threading.Lock()
        self._current_file = None
        self._current_file_size = 0
        self._filters = []
        self._stats = {level: 0 for level in LEVEL_NAMES}
        self._listeners = []

        os.makedirs(self._log_dir, exist_ok=True)
        self._open_log_file()

    def _default_log_dir(self):
        """获取默认日志目录"""
        if getattr(sys, "frozen", False):
            base = os.path.dirname(sys.executable)
        else:
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base, "logs")

    def _open_log_file(self):
        """打开当前日志文件"""
        today = datetime.datetime.now().strftime("%Y%m%d")
        filename = f"trainer_{today}.log"
        filepath = os.path.join(self._log_dir, filename)

        if os.path.exists(filepath):
            self._current_file_size = os.path.getsize(filepath)
        else:
            self._current_file_size = 0

        self._current_file = open(filepath, "a", encoding="utf-8")
        self._current_filename = filename

    def _rotate_if_needed(self):
        """如果文件过大，滚动日志"""
        if self._current_file_size < self._max_file_size:
            return

        self._current_file.close()

        # 滚动备份文件
        for i in range(self._backup_count - 1, 0, -1):
            src = os.path.join(self._log_dir, f"{self._current_filename}.{i}")
            dst = os.path.join(self._log_dir, f"{self._current_filename}.{i+1}")
            if os.path.exists(src):
                if os.path.exists(dst):
                    os.remove(dst)
                os.rename(src, dst)

        # 当前文件变为 .1
        src = os.path.join(self._log_dir, self._current_filename)
        dst = os.path.join(self._log_dir, f"{self._current_filename}.1")
        if os.path.exists(src):
            os.rename(src, dst)

        # 打开新文件
        self._current_file = open(src, "w", encoding="utf-8")
        self._current_file_size = 0
        log_warning(f"[日志] 日志文件已滚动: {self._current_filename}")

    def _write(self, entry):
        """写入日志"""
        line = entry.format() + "\n"

        with self._lock:
            # 写入内存
            self._memory_logs.append(entry)
            self._stats[entry.level] = self._stats.get(entry.level, 0) + 1

            # 写入文件
            try:
                self._rotate_if_needed()
                self._current_file.write(line)
                self._current_file.flush()
                self._current_file_size += len(line.encode("utf-8"))
            except Exception as e:
                # 日志写入失败不应该影响主程序
                pass

            # 通知监听器
            for listener in self._listeners:
                try:
                    listener(entry)
                except Exception:
                    pass

    def debug(self, message, module=""):
        """记录 DEBUG 级别日志"""
        entry = LogEntry(DEBUG, message, module)
        self._write(entry)

    def info(self, message, module=""):
        """记录 INFO 级别日志"""
        entry = LogEntry(INFO, message, module)
        self._write(entry)
        log(message)

    def warning(self, message, module=""):
        """记录 WARNING 级别日志"""
        entry = LogEntry(WARNING, message, module)
        self._write(entry)
        log_warning(message)

    def error(self, message, module=""):
        """记录 ERROR 级别日志"""
        entry = LogEntry(ERROR, message, module)
        self._write(entry)
        log_error(message)

    def critical(self, message, module=""):
        """记录 CRITICAL 级别日志"""
        entry = LogEntry(CRITICAL, message, module)
        self._write(entry)
        log_error(f"[CRITICAL] {message}")

    def success(self, message, module=""):
        """记录成功日志（INFO 级别）"""
        entry = LogEntry(INFO, f"[SUCCESS] {message}", module)
        self._write(entry)
        log_success(message)

    def get_recent_logs(self, count=100, filter_obj=None):
        """获取最近的日志。

        参数：
            count: 返回条数
            filter_obj: LogFilter 对象（可选）

        返回：
            [LogEntry, ...]
        """
        with self._lock:
            logs = list(self._memory_logs)

        if filter_obj:
            logs = [e for e in logs if filter_obj.matches(e)]

        return logs[-count:]

    def search_logs(self, keyword, count=100, case_sensitive=False):
        """搜索日志。

        参数：
            keyword: 搜索关键词
            count: 最大返回条数
            case_sensitive: 是否区分大小写

        返回：
            [LogEntry, ...]
        """
        with self._lock:
            logs = list(self._memory_logs)

        if not case_sensitive:
            keyword = keyword.lower()
            results = [e for e in logs if keyword in e.message.lower()]
        else:
            results = [e for e in logs if keyword in e.message]

        return results[-count:]

    def get_stats(self):
        """获取日志统计。

        返回：
            {"DEBUG": int, "INFO": int, ...}
        """
        with self._lock:
            return {LEVEL_NAMES[k]: v for k, v in self._stats.items()}

    def export_logs(self, filepath, filter_obj=None, format="txt"):
        """导出日志到文件。

        参数：
            filepath: 输出文件路径
            filter_obj: 过滤器（可选）
            format: "txt" 或 "json"
        """
        with self._lock:
            logs = list(self._memory_logs)

        if filter_obj:
            logs = [e for e in logs if filter_obj.matches(e)]

        try:
            if format == "json":
                data = [e.to_dict() for e in logs]
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            else:
                with open(filepath, "w", encoding="utf-8") as f:
                    for e in logs:
                        f.write(e.format() + "\n")

            log_success(f"[日志] 已导出 {len(logs)} 条日志到: {filepath}")
            return True
        except Exception as e:
            log_error(f"[日志] 导出失败: {e}")
            return False

    def clear_memory(self):
        """清空内存日志"""
        with self._lock:
            self._memory_logs.clear()
            self._stats = {level: 0 for level in LEVEL_NAMES}

    def add_listener(self, listener):
        """添加日志监听器（新日志到达时回调）。"""
        self._listeners.append(listener)

    def remove_listener(self, listener):
        """移除监听器。"""
        if listener in self._listeners:
            self._listeners.remove(listener)

    def get_log_files(self):
        """获取所有日志文件列表。"""
        if not os.path.exists(self._log_dir):
            return []
        files = []
        for f in os.listdir(self._log_dir):
            if f.endswith(".log") or ".log." in f:
                filepath = os.path.join(self._log_dir, f)
                files.append({
                    "name": f,
                    "path": filepath,
                    "size": os.path.getsize(filepath),
                    "modified": datetime.datetime.fromtimestamp(os.path.getmtime(filepath)),
                })
        return sorted(files, key=lambda x: x["modified"], reverse=True)

    def cleanup_old_logs(self, keep_days=7):
        """清理旧日志文件。

        参数：
            keep_days: 保留天数
        """
        cutoff = datetime.datetime.now() - datetime.timedelta(days=keep_days)
        cleaned = 0
        for f in self.get_log_files():
            if f["modified"] < cutoff:
                try:
                    os.remove(f["path"])
                    cleaned += 1
                except Exception:
                    pass
        if cleaned > 0:
            log(f"[日志] 已清理 {cleaned} 个旧日志文件")
        return cleaned

    def close(self):
        """关闭日志文件"""
        if self._current_file:
            try:
                self._current_file.close()
            except Exception:
                pass


# 全局增强日志器单例
_global_logger = None


def get_enhanced_logger():
    """获取全局增强日志器"""
    global _global_logger
    if _global_logger is None:
        _global_logger = EnhancedLogger()
    return _global_logger
