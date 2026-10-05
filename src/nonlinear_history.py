"""
woldvein Trainer v0.4.6 - 非线性历史跳转模块

支持直接跳转到任意历史快照点，而不是只能一步步撤销/重做。

核心概念：
    - Snapshot: 历史快照，包含操作记录和状态数据
    - HistoryTree: 历史树，支持分支
    - Jump: 跳转到任意历史点

与 operation_history 的区别：
    - operation_history: 线性撤销/重做（只能一步步来）
    - nonlinear_history: 支持直接跳转到任意点，支持分支历史

使用方式：
    from .nonlinear_history import NonlinearHistory
    history = NonlinearHistory()
    history.add_snapshot("修改金钱", data={"money": 1000000})
    history.add_snapshot("修改粮食", data={"food": 500000})
    history.jump_to(0)  # 直接跳回第一个快照
"""
import os
import json
import copy
import datetime
import threading

from .logger import log, log_success, log_error, log_warning
from .atomic_file import atomic_write_json


class Snapshot:
    """历史快照"""

    def __init__(self, name, description="", data=None, parent_id=None):
        """
        参数：
            name: 快照名称
            description: 快照描述
            data: 状态数据（字典）
            parent_id: 父快照ID（用于分支历史）
        """
        self.id = None  # 由 HistoryTree 分配
        self.name = name
        self.description = description
        self.data = data or {}
        self.parent_id = parent_id
        self.children = []  # 子快照ID列表
        self.timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.index = 0  # 在线性序列中的索引

    def to_dict(self):
        """序列化为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "data": self.data,
            "parent_id": self.parent_id,
            "children": self.children,
            "timestamp": self.timestamp,
            "index": self.index,
        }

    @classmethod
    def from_dict(cls, d):
        """从字典反序列化"""
        snap = cls(
            name=d.get("name", ""),
            description=d.get("description", ""),
            data=d.get("data", {}),
            parent_id=d.get("parent_id"),
        )
        snap.id = d.get("id")
        snap.children = d.get("children", [])
        snap.timestamp = d.get("timestamp", "")
        snap.index = d.get("index", 0)
        return snap


class NonlinearHistory:
    """非线性历史管理器"""

    def __init__(self, max_snapshots=200):
        """
        参数：
            max_snapshots: 最大快照数量
        """
        self._snapshots = {}  # {id: Snapshot}
        self._linear_history = []  # 线性历史（当前分支）
        self._current_index = -1  # 当前位置
        self._root_id = None
        self._next_id = 0
        self._max_snapshots = max_snapshots
        self._lock = threading.Lock()
        self._listeners = []

        # 创建初始快照
        self._init_root()

    def _init_root(self):
        """初始化根快照"""
        root = Snapshot("初始状态", "修改器启动时的初始状态", data={})
        root.id = self._next_id
        root.index = 0
        self._next_id += 1
        self._snapshots[root.id] = root
        self._root_id = root.id
        self._linear_history.append(root.id)
        self._current_index = 0

    def add_snapshot(self, name, description="", data=None):
        """添加快照。

        如果当前不在历史末尾，会创建分支（丢弃后续重做栈）。

        参数：
            name: 快照名称
            description: 快照描述
            data: 状态数据

        返回：
            快照ID
        """
        with self._lock:
            # 如果当前不在末尾，截断后续历史（创建分支）
            if self._current_index < len(self._linear_history) - 1:
                log_warning(f"[历史] 在旧节点上创建新分支，丢弃 {len(self._linear_history) - self._current_index - 1} 个后续快照")
                # 截断线性历史
                self._linear_history = self._linear_history[:self._current_index + 1]

            # 创建新快照
            current_id = self._linear_history[self._current_index] if self._current_index >= 0 else self._root_id
            snap = Snapshot(name, description, data=copy.deepcopy(data) if data else {}, parent_id=current_id)
            snap.id = self._next_id
            snap.index = len(self._linear_history)
            self._next_id += 1

            # 添加到父节点的子列表
            if current_id in self._snapshots:
                self._snapshots[current_id].children.append(snap.id)

            self._snapshots[snap.id] = snap
            self._linear_history.append(snap.id)
            self._current_index = len(self._linear_history) - 1

            # 限制最大快照数
            self._trim_old_snapshots()

            log(f"[历史] 添加快照: {name} (ID={snap.id}, 索引={snap.index})")
            self._notify_listeners()
            return snap.id

    def _trim_old_snapshots(self):
        """修剪过旧的快照（保留根节点和最近的 max_snapshots 个）"""
        if len(self._linear_history) <= self._max_snapshots:
            return

        # 保留根节点 + 最近的 max_snapshots-1 个
        keep_count = self._max_snapshots - 1
        remove_count = len(self._linear_history) - 1 - keep_count
        if remove_count <= 0:
            return

        removed_ids = self._linear_history[1:1 + remove_count]
        self._linear_history = [self._linear_history[0]] + self._linear_history[1 + remove_count:]

        # 重新计算索引
        for i, sid in enumerate(self._linear_history):
            if sid in self._snapshots:
                self._snapshots[sid].index = i

        self._current_index = len(self._linear_history) - 1

        # 删除旧快照数据
        for sid in removed_ids:
            self._snapshots.pop(sid, None)

        log_warning(f"[历史] 已修剪 {remove_count} 个旧快照")

    def jump_to(self, index):
        """跳转到指定索引的快照。

        参数：
            index: 快照索引（0 为初始状态）

        返回：
            (success, snapshot, error_msg)
        """
        with self._lock:
            if index < 0 or index >= len(self._linear_history):
                return False, None, f"索引 {index} 超出范围 (0-{len(self._linear_history)-1})"

            sid = self._linear_history[index]
            snap = self._snapshots.get(sid)
            if not snap:
                return False, None, f"快照 {sid} 不存在"

            self._current_index = index
            log(f"[历史] 跳转到快照: {snap.name} (索引={index})")
            self._notify_listeners()
            return True, snap, ""

    def jump_to_id(self, snapshot_id):
        """跳转到指定ID的快照。

        返回：
            (success, snapshot, error_msg)
        """
        # 找到该快照在当前线性历史中的索引
        for i, sid in enumerate(self._linear_history):
            if sid == snapshot_id:
                return self.jump_to(i)
        return False, None, f"快照 {snapshot_id} 不在当前历史分支中"

    def undo(self):
        """撤销一步（跳转到上一个快照）。"""
        if self._current_index > 0:
            return self.jump_to(self._current_index - 1)
        return False, None, "已是初始状态"

    def redo(self):
        """重做一步（跳转到下一个快照）。"""
        if self._current_index < len(self._linear_history) - 1:
            return self.jump_to(self._current_index + 1)
        return False, None, "已是最新状态"

    def get_current(self):
        """获取当前快照。"""
        if self._current_index >= 0 and self._current_index < len(self._linear_history):
            sid = self._linear_history[self._current_index]
            return self._snapshots.get(sid)
        return None

    def get_history(self, limit=None):
        """获取线性历史列表。

        参数：
            limit: 返回最近的 N 个快照

        返回：
            [Snapshot, ...]（从旧到新）
        """
        if limit and limit < len(self._linear_history):
            ids = self._linear_history[-limit:]
        else:
            ids = self._linear_history
        return [self._snapshots[sid] for sid in ids if sid in self._snapshots]

    def get_branches(self, snapshot_id=None):
        """获取指定快照的分支（子快照）。

        参数：
            snapshot_id: 快照ID，None 表示当前快照

        返回：
            [Snapshot, ...]
        """
        if snapshot_id is None:
            current = self.get_current()
            if current:
                snapshot_id = current.id
            else:
                return []

        snap = self._snapshots.get(snapshot_id)
        if not snap:
            return []
        return [self._snapshots[cid] for cid in snap.children if cid in self._snapshots]

    def can_undo(self):
        """是否可以撤销"""
        return self._current_index > 0

    def can_redo(self):
        """是否可以重做"""
        return self._current_index < len(self._linear_history) - 1

    def get_current_index(self):
        """获取当前索引"""
        return self._current_index

    def get_history_length(self):
        """获取历史长度"""
        return len(self._linear_history)

    def clear(self):
        """清空历史（保留根节点）"""
        with self._lock:
            self._snapshots.clear()
            self._linear_history.clear()
            self._current_index = -1
            self._next_id = 0
            self._init_root()
            log("[历史] 已清空")
            self._notify_listeners()

    def add_listener(self, listener):
        """添加历史变更监听器。"""
        self._listeners.append(listener)

    def remove_listener(self, listener):
        """移除监听器。"""
        if listener in self._listeners:
            self._listeners.remove(listener)

    def _notify_listeners(self):
        """通知所有监听器。"""
        for listener in self._listeners:
            try:
                listener(self._current_index, len(self._linear_history))
            except Exception:
                pass

    def export_to_file(self, filepath):
        """导出历史到文件。"""
        data = {
            "current_index": self._current_index,
            "linear_history": self._linear_history,
            "snapshots": {str(k): v.to_dict() for k, v in self._snapshots.items()},
            "next_id": self._next_id,
        }
        try:
            atomic_write_json(filepath, data)
            log_success(f"[历史] 已导出到: {filepath}")
            return True
        except Exception as e:
            log_error(f"[历史] 导出失败: {e}")
            return False

    def import_from_file(self, filepath):
        """从文件导入历史。"""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            self._snapshots = {}
            for k, v in data.get("snapshots", {}).items():
                snap = Snapshot.from_dict(v)
                self._snapshots[int(k)] = snap

            self._linear_history = data.get("linear_history", [])
            self._current_index = data.get("current_index", -1)
            self._next_id = data.get("next_id", 0)
            self._root_id = self._linear_history[0] if self._linear_history else None

            log_success(f"[历史] 已从 {filepath} 导入 ({len(self._linear_history)} 个快照)")
            self._notify_listeners()
            return True
        except Exception as e:
            log_error(f"[历史] 导入失败: {e}")
            return False


# 全局非线性历史管理器单例
_global_history = None


def get_nonlinear_history():
    """获取全局非线性历史管理器"""
    global _global_history
    if _global_history is None:
        _global_history = NonlinearHistory()
    return _global_history
