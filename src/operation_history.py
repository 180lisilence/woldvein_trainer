"""
woldvein Trainer v0.4.6 - 操作日志与撤销机制

记录所有用户操作，支持撤销（Undo）和重做（Redo）。

核心概念：
    - Operation: 一次可撤销的操作，包含操作类型、描述、旧值、新值、执行函数、撤销函数
    - UndoStack: 撤销栈，保存已执行的操作
    - RedoStack: 重做栈，保存已撤销的操作

使用方式：
    from .operation_history import OperationHistory, Operation
    history = OperationHistory()
    history.execute(Operation(
        name="修改资源",
        description="金钱 +1000000",
        do_func=lambda: add_resource(1, 1000000),
        undo_func=lambda: add_resource(1, -1000000)
    ))
    history.undo()  # 撤销
    history.redo()  # 重做
"""
import os
import json
import datetime
import threading

from .logger import log, log_success, log_error, log_warning


class Operation:
    """一次可撤销的操作"""

    def __init__(self, name, description="", do_func=None, undo_func=None, data=None):
        """
        参数：
            name: 操作名称（如"修改资源"、"备份存档"）
            description: 操作描述（如"金钱 +1000000"）
            do_func: 执行函数（调用时执行操作）
            undo_func: 撤销函数（调用时撤销操作）
            data: 附加数据（如地址、旧值、新值）
        """
        self.name = name
        self.description = description
        self.do_func = do_func
        self.undo_func = undo_func
        self.data = data or {}
        self.timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.executed = False

    def execute(self):
        """执行操作"""
        if self.do_func:
            result = self.do_func()
            self.executed = True
            return result
        self.executed = True
        return None

    def undo(self):
        """撤销操作"""
        if self.undo_func:
            return self.undo_func()
        return None

    def to_dict(self):
        """序列化为字典（用于日志记录）"""
        return {
            "name": self.name,
            "description": self.description,
            "timestamp": self.timestamp,
            "data": self.data,
        }


class OperationHistory:
    """操作历史管理器（撤销/重做）"""

    def __init__(self, max_stack_size=100):
        """
        参数：
            max_stack_size: 撤销栈最大长度（防止内存无限增长）
        """
        self.undo_stack = []
        self.redo_stack = []
        self.max_stack_size = max_stack_size
        self._lock = threading.Lock()
        self._listeners = []

    def add_listener(self, listener):
        """添加状态变更监听器（用于UI更新撤销/重做按钮状态）"""
        self._listeners.append(listener)

    def _notify_listeners(self):
        """通知所有监听器"""
        for listener in self._listeners:
            try:
                listener(self.can_undo(), self.can_redo(), len(self.undo_stack))
            except Exception:
                pass

    def execute(self, operation):
        """执行操作并压入撤销栈。

        返回：
            (success, result, error_msg)
        """
        with self._lock:
            try:
                result = operation.execute()
                self.undo_stack.append(operation)
                # 限制栈大小
                if len(self.undo_stack) > self.max_stack_size:
                    self.undo_stack.pop(0)
                # 执行新操作后清空重做栈
                self.redo_stack.clear()
                log(f"[操作] {operation.name}: {operation.description}")
                self._notify_listeners()
                return True, result, ""
            except Exception as e:
                log_error(f"[操作失败] {operation.name}: {e}")
                return False, None, str(e)

    def undo(self):
        """撤销上一次操作。

        返回：
            (success, operation, error_msg)
        """
        with self._lock:
            if not self.undo_stack:
                return False, None, "没有可撤销的操作"

            operation = self.undo_stack.pop()
            try:
                result = operation.undo()
                self.redo_stack.append(operation)
                log_warning(f"[撤销] {operation.name}: {operation.description}")
                self._notify_listeners()
                return True, operation, ""
            except Exception as e:
                # 撤销失败，把操作放回撤销栈
                self.undo_stack.append(operation)
                log_error(f"[撤销失败] {operation.name}: {e}")
                return False, operation, str(e)

    def redo(self):
        """重做上一次撤销的操作。

        返回：
            (success, operation, error_msg)
        """
        with self._lock:
            if not self.redo_stack:
                return False, None, "没有可重做的操作"

            operation = self.redo_stack.pop()
            try:
                result = operation.execute()
                self.undo_stack.append(operation)
                log(f"[重做] {operation.name}: {operation.description}")
                self._notify_listeners()
                return True, operation, ""
            except Exception as e:
                self.redo_stack.append(operation)
                log_error(f"[重做失败] {operation.name}: {e}")
                return False, operation, str(e)

    def can_undo(self):
        """是否可以撤销"""
        return len(self.undo_stack) > 0

    def can_redo(self):
        """是否可以重做"""
        return len(self.redo_stack) > 0

    def get_history(self, limit=50):
        """获取操作历史列表（最近的在前）。

        返回：
            [{"name": str, "description": str, "timestamp": str, "index": int}, ...]
        """
        history = []
        for i, op in enumerate(reversed(self.undo_stack)):
            history.append({
                "index": len(self.undo_stack) - 1 - i,
                "name": op.name,
                "description": op.description,
                "timestamp": op.timestamp,
            })
            if len(history) >= limit:
                break
        return history

    def clear(self):
        """清空所有历史（切换存档/重启时调用）"""
        with self._lock:
            self.undo_stack.clear()
            self.redo_stack.clear()
            log("[操作历史] 已清空")
            self._notify_listeners()

    def undo_count(self):
        """可撤销操作数量"""
        return len(self.undo_stack)

    def redo_count(self):
        """可重做操作数量"""
        return len(self.redo_stack)


# 全局操作历史单例
_global_history = None


def get_operation_history():
    """获取全局操作历史管理器"""
    global _global_history
    if _global_history is None:
        _global_history = OperationHistory(max_stack_size=100)
    return _global_history


def record_operation(name, description, do_func, undo_func, data=None):
    """便捷函数：执行操作并记录到全局历史。

    返回：
        (success, result, error_msg)
    """
    history = get_operation_history()
    op = Operation(
        name=name,
        description=description,
        do_func=do_func,
        undo_func=undo_func,
        data=data,
    )
    return history.execute(op)


def undo_last():
    """便捷函数：撤销全局历史的上一次操作"""
    return get_operation_history().undo()


def redo_last():
    """便捷函数：重做全局历史的上一次撤销操作"""
    return get_operation_history().redo()
