"""
woldvein Trainer v0.4.6 - 紧急停止管理器

一键终止全部内存写入、Hook、异步任务，恢复游戏到安全状态。

使用场景：
    - 游戏出现异常/崩溃前兆
    - 修改器功能导致游戏卡死
    - 用户需要立即停止所有修改

功能：
    1. 设置全局紧急停止标志
    2. 所有异步任务检查标志，收到信号后立即停止
    3. 停止所有内存写入操作
    4. 记录紧急停止日志和原因
    5. 提供恢复功能（解除紧急停止状态）

使用方式：
    from .emergency_stop import EmergencyStop
    estop = EmergencyStop()
    estop.trigger("用户手动触发")  # 紧急停止
    estop.is_triggered()  # 检查是否已触发
    estop.reset()  # 解除紧急停止
"""
import threading
import time
import datetime

from .logger import log, log_success, log_error, log_warning


class EmergencyStop:
    """紧急停止管理器"""

    def __init__(self):
        self._triggered = False
        self._trigger_time = None
        self._trigger_reason = ""
        self._lock = threading.Lock()
        self._callbacks = []  # 紧急停止时的回调函数列表
        self._stats = {
            "trigger_count": 0,
            "last_trigger_time": None,
            "last_reason": "",
        }

    def trigger(self, reason="手动触发"):
        """触发紧急停止。

        参数：
            reason: 触发原因

        返回：
            True 表示首次触发，False 表示已经在紧急停止状态
        """
        with self._lock:
            if self._triggered:
                log_warning(f"[紧急停止] 已在紧急停止状态，重复触发被忽略")
                return False

            self._triggered = True
            self._trigger_time = datetime.datetime.now()
            self._trigger_reason = reason
            self._stats["trigger_count"] += 1
            self._stats["last_trigger_time"] = self._trigger_time.strftime("%Y-%m-%d %H:%M:%S")
            self._stats["last_reason"] = reason

        log_error(f"[紧急停止] 已触发！原因: {reason}")
        log_error(f"[紧急停止] 时间: {self._trigger_time.strftime('%Y-%m-%d %H:%M:%S')}")

        # 执行所有回调
        self._execute_callbacks(reason)
        return True

    def reset(self):
        """解除紧急停止状态。

        返回：
            True 表示成功解除，False 表示未在紧急停止状态
        """
        with self._lock:
            if not self._triggered:
                return False
            self._triggered = False
            self._trigger_time = None
            self._trigger_reason = ""

        log_success("[紧急停止] 已解除，恢复正常操作")
        return True

    def is_triggered(self):
        """检查是否已触发紧急停止。"""
        return self._triggered

    def check(self):
        """检查是否应停止操作（供异步任务循环调用）。

        返回：
            True 表示应停止，False 表示继续
        """
        return self._triggered

    def wait_for_reset(self, timeout=None):
        """等待紧急停止解除。

        参数：
            timeout: 超时时间（秒），None 表示无限等待

        返回：
            True 表示已解除，False 表示超时
        """
        start = time.time()
        while self._triggered:
            if timeout and (time.time() - start) > timeout:
                return False
            time.sleep(0.1)
        return True

    def register_callback(self, callback):
        """注册紧急停止回调函数。

        参数：
            callback: 回调函数 callback(reason)
        """
        self._callbacks.append(callback)

    def unregister_callback(self, callback):
        """注销回调函数。"""
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def _execute_callbacks(self, reason):
        """执行所有回调函数。"""
        for callback in self._callbacks:
            try:
                callback(reason)
            except Exception as e:
                log_error(f"[紧急停止] 回调执行异常: {e}")

    def get_status(self):
        """获取紧急停止状态。

        返回：
            {
                "triggered": bool,
                "trigger_time": str,
                "reason": str,
                "stats": {...}
            }
        """
        with self._lock:
            return {
                "triggered": self._triggered,
                "trigger_time": self._trigger_time.strftime("%Y-%m-%d %H:%M:%S") if self._trigger_time else None,
                "reason": self._trigger_reason,
                "stats": dict(self._stats),
            }

    def get_elapsed(self):
        """获取紧急停止已持续时间（秒）。"""
        if not self._triggered or not self._trigger_time:
            return 0
        return (datetime.datetime.now() - self._trigger_time).total_seconds()


# 全局紧急停止管理器单例
_global_estop = None


def get_emergency_stop():
    """获取全局紧急停止管理器"""
    global _global_estop
    if _global_estop is None:
        _global_estop = EmergencyStop()
    return _global_estop


def trigger_emergency_stop(reason="手动触发"):
    """便捷函数：触发全局紧急停止"""
    return get_emergency_stop().trigger(reason)


def is_emergency_stopped():
    """便捷函数：检查全局紧急停止是否已触发"""
    return get_emergency_stop().is_triggered()


def reset_emergency_stop():
    """便捷函数：解除全局紧急停止"""
    return get_emergency_stop().reset()
