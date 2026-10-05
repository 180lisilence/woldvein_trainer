"""
woldvein Trainer v0.4.6 - 事务批量操作模块

将多个操作打包成一个事务，要么全部成功，要么全部回滚。

使用场景：
    - 批量修改多个资源（金钱+粮食+木材）
    - 批量解锁多个功能
    - 一键全开（包含9个子操作）

核心概念：
    - Transaction: 事务，包含多个 Operation
    - Operation: 单个操作，包含 do_func 和 undo_func
    - 提交: 依次执行所有操作，任何失败则回滚已执行的操作
    - 回滚: 逆序执行所有已执行操作的 undo_func

使用方式：
    from .transaction import Transaction, Operation
    tx = Transaction("批量增加资源")
    tx.add(Operation("增加金钱", do=lambda: add_resource(1, 1000000), undo=lambda: add_resource(1, -1000000)))
    tx.add(Operation("增加粮食", do=lambda: add_resource(2, 500000), undo=lambda: add_resource(2, -500000)))
    success, results = tx.commit()
    if not success:
        tx.rollback()
"""
import threading
import datetime

from .logger import log, log_success, log_error, log_warning


class Operation:
    """事务中的单个操作"""

    def __init__(self, name, do_func=None, undo_func=None, description="", data=None):
        """
        参数：
            name: 操作名称
            do_func: 执行函数
            undo_func: 撤销函数
            description: 操作描述
            data: 附加数据
        """
        self.name = name
        self.description = description
        self.do_func = do_func
        self.undo_func = undo_func
        self.data = data or {}
        self.executed = False
        self.result = None
        self.error = None

    def execute(self):
        """执行操作"""
        if self.do_func:
            try:
                self.result = self.do_func()
                self.executed = True
                return True, self.result
            except Exception as e:
                self.error = str(e)
                return False, str(e)
        self.executed = True
        return True, None

    def undo(self):
        """撤销操作"""
        if not self.executed:
            return True, None
        if self.undo_func:
            try:
                result = self.undo_func()
                self.executed = False
                return True, result
            except Exception as e:
                self.error = f"撤销失败: {e}"
                return False, str(e)
        return True, None


class Transaction:
    """事务管理器"""

    def __init__(self, name="", description=""):
        """
        参数：
            name: 事务名称
            description: 事务描述
        """
        self.name = name
        self.description = description
        self.operations = []
        self._executed_ops = []  # 已执行的操作（用于回滚）
        self._lock = threading.Lock()
        self._committed = False
        self._rolled_back = False
        self.start_time = None
        self.end_time = None

    def add(self, operation):
        """添加操作到事务。

        参数：
            operation: Operation 对象

        返回：
            self（支持链式调用）
        """
        if self._committed or self._rolled_back:
            raise RuntimeError("事务已结束，不能再添加操作")
        self.operations.append(operation)
        return self

    def add_operation(self, name, do_func=None, undo_func=None, description=""):
        """便捷方法：添加操作。

        返回：
            self
        """
        op = Operation(name, do_func=do_func, undo_func=undo_func, description=description)
        return self.add(op)

    def commit(self):
        """提交事务：依次执行所有操作。

        任何操作失败则自动回滚已执行的操作。

        返回：
            (success, results, error_msg)
            success: 是否全部成功
            results: 所有操作的结果列表
            error_msg: 失败时的错误信息
        """
        with self._lock:
            if self._committed:
                return False, [], "事务已提交"
            if self._rolled_back:
                return False, [], "事务已回滚"

            self.start_time = datetime.datetime.now()
            log(f"[事务] 开始提交: {self.name} ({len(self.operations)} 个操作)")

            results = []
            for i, op in enumerate(self.operations):
                log(f"[事务] 执行操作 {i+1}/{len(self.operations)}: {op.name}")
                success, result = op.execute()
                results.append(result)

                if not success:
                    error_msg = f"操作 '{op.name}' 失败: {op.error}"
                    log_error(f"[事务] {error_msg}")
                    # 回滚已执行的操作
                    self._rollback_executed()
                    self._rolled_back = True
                    self.end_time = datetime.datetime.now()
                    return False, results, error_msg

                self._executed_ops.append(op)

            self._committed = True
            self.end_time = datetime.datetime.now()
            duration = (self.end_time - self.start_time).total_seconds()
            log_success(f"[事务] 提交成功: {self.name} ({duration:.2f}s, {len(self.operations)} 个操作)")
            return True, results, ""

    def _rollback_executed(self):
        """回滚已执行的操作（逆序）"""
        log_warning(f"[事务] 开始回滚 {len(self._executed_ops)} 个已执行操作")
        for op in reversed(self._executed_ops):
            log(f"[事务] 回滚操作: {op.name}")
            success, result = op.undo()
            if not success:
                log_error(f"[事务] 回滚操作 '{op.name}' 失败: {op.error}")
                # 回滚失败继续回滚其他操作，不中断
        self._executed_ops.clear()

    def rollback(self):
        """手动回滚事务。

        返回：
            (success, error_msg)
        """
        with self._lock:
            if self._rolled_back:
                return True, "已回滚"
            if not self._executed_ops and not self._committed:
                return True, "无操作可回滚"

            self._rollback_executed()
            self._rolled_back = True
            self._committed = False
            self.end_time = datetime.datetime.now()
            log_warning(f"[事务] 已手动回滚: {self.name}")
            return True, ""

    def is_committed(self):
        """是否已提交"""
        return self._committed

    def is_rolled_back(self):
        """是否已回滚"""
        return self._rolled_back

    def get_duration(self):
        """获取事务执行时长（秒）"""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0

    def get_status(self):
        """获取事务状态。

        返回：
            {
                "name": str,
                "operation_count": int,
                "executed_count": int,
                "committed": bool,
                "rolled_back": bool,
                "duration": float
            }
        """
        return {
            "name": self.name,
            "operation_count": len(self.operations),
            "executed_count": len(self._executed_ops),
            "committed": self._committed,
            "rolled_back": self._rolled_back,
            "duration": self.get_duration(),
        }


class TransactionManager:
    """事务管理器（全局管理多个事务）"""

    def __init__(self):
        self._transactions = []
        self._lock = threading.Lock()
        self._active_transaction = None

    def begin(self, name="", description=""):
        """开始一个新事务。

        返回：
            Transaction 对象
        """
        with self._lock:
            tx = Transaction(name, description)
            self._transactions.append(tx)
            self._active_transaction = tx
            log(f"[事务管理] 开始事务: {name}")
            return tx

    def commit_active(self):
        """提交当前活动事务。"""
        if self._active_transaction:
            result = self._active_transaction.commit()
            self._active_transaction = None
            return result
        return False, [], "无活动事务"

    def rollback_active(self):
        """回滚当前活动事务。"""
        if self._active_transaction:
            result = self._active_transaction.rollback()
            self._active_transaction = None
            return result
        return True, "无活动事务"

    def get_history(self, limit=20):
        """获取事务历史。

        返回：
            [status_dict, ...]
        """
        with self._lock:
            history = [tx.get_status() for tx in self._transactions[-limit:]]
            return list(reversed(history))

    def clear_history(self):
        """清空事务历史。"""
        with self._lock:
            self._transactions.clear()


# 全局事务管理器单例
_global_tx_manager = None


def get_transaction_manager():
    """获取全局事务管理器"""
    global _global_tx_manager
    if _global_tx_manager is None:
        _global_tx_manager = TransactionManager()
    return _global_tx_manager


def begin_transaction(name="", description=""):
    """便捷函数：开始事务"""
    return get_transaction_manager().begin(name, description)
