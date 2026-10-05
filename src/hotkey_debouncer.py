"""
woldvein Trainer v0.4.6 - 热键防抖管理器

防止用户快速连续按热键导致功能重复触发。

原理：
    - 记录每个热键/功能的最后触发时间
    - 如果两次触发间隔小于防抖阈值，忽略第二次触发
    - 不同功能可配置不同的防抖阈值

默认阈值：
    - 普通功能（增加资源、切换开关）：200ms
    - 高危操作（全部作弊、批量修改）：500ms
    - 一次性操作（备份存档、诊断）：1000ms

使用方式：
    from .hotkey_debouncer import HotkeyDebouncer
    debouncer = HotkeyDebouncer()
    if debouncer.can_trigger("add_money"):
        add_money()
        debouncer.mark_triggered("add_money")
"""
import time
import threading

from .logger import log, log_warning

# 默认防抖阈值（毫秒）
DEFAULT_DEBOUNCE_MS = 200

# 不同功能的防抖阈值配置
DEBOUNCE_CONFIG = {
    # 资源增加类：200ms
    "add_resource": 200,
    "add_all_resources": 300,
    "zero_resources": 500,

    # 创造模式切换：200ms
    "toggle_creative": 200,
    "toggle_max_boom": 200,
    "toggle_unlock": 200,
    "toggle_infinite_resource": 200,

    # 时间控制：200ms
    "time_speed_up": 200,
    "time_speed_down": 200,
    "time_pause": 300,

    # 高危批量操作：500ms
    "enable_all_cheats": 500,
    "upgrade_all_buildings": 500,
    "finish_all_buildings": 500,
    "unlock_all_achievements": 500,
    "unlock_all_plots": 500,
    "unlock_all_talents": 500,
    "close_all_disasters": 500,

    # 一次性操作：1000ms
    "backup_save": 1000,
    "diagnose": 1000,
    "inject_dll": 2000,
    "emergency_stop": 500,

    # Overlay 切换：300ms
    "toggle_overlay": 300,

    # 撤销/重做：200ms
    "undo": 200,
    "redo": 200,
}


class HotkeyDebouncer:
    """热键防抖管理器"""

    def __init__(self, default_debounce_ms=DEFAULT_DEBOUNCE_MS):
        """
        参数：
            default_debounce_ms: 默认防抖阈值（毫秒）
        """
        self._default_debounce = default_debounce_ms / 1000.0  # 转换为秒
        self._last_trigger = {}  # {action_name: timestamp}
        self._custom_debounce = {}  # {action_name: seconds}
        self._lock = threading.Lock()
        self._stats = {"total": 0, "blocked": 0}  # 统计

    def set_debounce(self, action_name, debounce_ms):
        """设置特定功能的防抖阈值。

        参数：
            action_name: 功能名称
            debounce_ms: 防抖阈值（毫秒）
        """
        with self._lock:
            self._custom_debounce[action_name] = debounce_ms / 1000.0

    def get_debounce(self, action_name):
        """获取功能的防抖阈值（秒）。"""
        if action_name in self._custom_debounce:
            return self._custom_debounce[action_name]
        if action_name in DEBOUNCE_CONFIG:
            return DEBOUNCE_CONFIG[action_name] / 1000.0
        return self._default_debounce

    def can_trigger(self, action_name):
        """检查功能是否可以触发（未在防抖期内）。

        参数：
            action_name: 功能名称

        返回：
            True 可以触发，False 在防抖期内
        """
        now = time.time()
        with self._lock:
            self._stats["total"] += 1
            last = self._last_trigger.get(action_name, 0)
            debounce = self.get_debounce(action_name)
            if now - last < debounce:
                self._stats["blocked"] += 1
                return False
            return True

    def mark_triggered(self, action_name):
        """标记功能已触发（更新最后触发时间）。"""
        now = time.time()
        with self._lock:
            self._last_trigger[action_name] = now

    def try_trigger(self, action_name, func, *args, **kwargs):
        """尝试触发功能，如果在防抖期内则不执行。

        参数：
            action_name: 功能名称
            func: 要执行的函数
            *args, **kwargs: 函数参数

        返回：
            (executed, result)
            executed: 是否执行了函数
            result: 函数返回值（未执行时为 None）
        """
        if not self.can_trigger(action_name):
            log_warning(f"[防抖] {action_name} 触发过于频繁，已忽略")
            return False, None

        self.mark_triggered(action_name)
        try:
            result = func(*args, **kwargs)
            return True, result
        except Exception as e:
            # 执行失败不影响防抖状态（允许立即重试）
            with self._lock:
                self._last_trigger.pop(action_name, None)
            raise

    def reset(self, action_name=None):
        """重置防抖状态。

        参数：
            action_name: 功能名称，None 表示重置全部
        """
        with self._lock:
            if action_name:
                self._last_trigger.pop(action_name, None)
            else:
                self._last_trigger.clear()

    def get_stats(self):
        """获取防抖统计信息。

        返回：
            {"total": int, "blocked": int, "block_rate": float}
        """
        with self._lock:
            total = self._stats["total"]
            blocked = self._stats["blocked"]
            rate = blocked / total if total > 0 else 0
            return {
                "total": total,
                "blocked": blocked,
                "block_rate": rate,
            }

    def get_wait_time(self, action_name):
        """获取功能还需要等待多少秒才能触发。

        返回：
            等待秒数（0 表示可以立即触发）
        """
        now = time.time()
        with self._lock:
            last = self._last_trigger.get(action_name, 0)
            debounce = self.get_debounce(action_name)
            wait = debounce - (now - last)
            return max(0, wait)


# 全局热键防抖管理器单例
_global_debouncer = None


def get_debouncer():
    """获取全局热键防抖管理器"""
    global _global_debouncer
    if _global_debouncer is None:
        _global_debouncer = HotkeyDebouncer()
    return _global_debouncer


def debounce(action_name):
    """装饰器：为函数添加热键防抖。

    使用方式：
        @debounce("add_money")
        def add_money():
            ...
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            d = get_debouncer()
            if not d.can_trigger(action_name):
                log_warning(f"[防抖] {action_name} 触发过于频繁，已忽略")
                return None
            d.mark_triggered(action_name)
            return func(*args, **kwargs)
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper
    return decorator
