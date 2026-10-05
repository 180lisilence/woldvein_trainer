"""
woldvein Trainer v0.4.6 - 热键冲突检测模块

检测用户配置的热键是否与其他功能或系统热键冲突。

功能：
    1. 维护所有已注册的热键
    2. 检测新配置的热键是否与已有热键冲突
    3. 检测是否与系统常用热键冲突
    4. 提供冲突警告和替代建议
    5. 热键组合规范化（统一格式）

使用方式：
    from .hotkey_conflict import HotkeyConflictDetector
    detector = HotkeyConflictDetector()
    detector.register("add_money", "Ctrl+F1")
    detector.register("add_food", "Ctrl+F2")
    has_conflict, conflicts = detector.check("Ctrl+F1")
"""
import re
import json

from .logger import log, log_success, log_error, log_warning

# 系统常用热键（可能与修改器冲突）
SYSTEM_HOTKEYS = {
    "Ctrl+C": "复制",
    "Ctrl+V": "粘贴",
    "Ctrl+X": "剪切",
    "Ctrl+Z": "撤销",
    "Ctrl+Y": "重做",
    "Ctrl+A": "全选",
    "Ctrl+S": "保存",
    "Ctrl+O": "打开",
    "Ctrl+N": "新建",
    "Ctrl+W": "关闭",
    "Ctrl+F": "查找",
    "Ctrl+H": "替换",
    "Ctrl+P": "打印",
    "Ctrl+Tab": "切换标签",
    "Ctrl+Shift+Esc": "任务管理器",
    "Alt+Tab": "切换窗口",
    "Alt+F4": "关闭窗口",
    "Alt+Enter": "全屏",
    "Win+D": "显示桌面",
    "Win+E": "文件资源管理器",
    "Win+R": "运行",
    "Win+L": "锁定",
    "Win+Tab": "任务视图",
    "F1": "帮助",
    "F5": "刷新",
    "F11": "全屏",
    "F12": "开发者工具",
    "Esc": "取消/退出",
    "PrintScreen": "截图",
}

# 游戏常用热键（可能与修改器冲突）
GAME_COMMON_HOTKEYS = {
    "W": "前进",
    "A": "左移",
    "S": "后退",
    "D": "右移",
    "Space": "跳跃/确认",
    "Esc": "菜单/暂停",
    "I": "物品栏",
    "M": "地图",
    "J": "任务",
    "K": "技能",
    "B": "背包",
    "C": "角色",
    "E": "交互",
    "F": "交互",
    "Q": "技能",
    "R": "技能/装弹",
    "Tab": "切换",
    "1-9": "快捷栏",
}

# 修饰键
MODIFIER_KEYS = {"Ctrl", "Alt", "Shift", "Win"}


def normalize_hotkey(hotkey_str):
    """规范化热键字符串。

    将各种格式统一为 "Ctrl+Alt+Shift+Key" 格式。

    参数：
        hotkey_str: 热键字符串，如 "ctrl+f1", "Ctrl + F1", "F1+Ctrl"

    返回：
        规范化后的热键字符串
    """
    if not hotkey_str:
        return ""

    # 分割
    parts = re.split(r'[+\-]', hotkey_str)
    parts = [p.strip().capitalize() for p in parts if p.strip()]

    # 分离修饰键和主键
    modifiers = []
    main_key = ""

    for part in parts:
        if part in MODIFIER_KEYS:
            modifiers.append(part)
        else:
            main_key = part

    # 修饰键排序（Ctrl, Alt, Shift, Win）
    modifier_order = {"Ctrl": 0, "Alt": 1, "Shift": 2, "Win": 3}
    modifiers.sort(key=lambda x: modifier_order.get(x, 99))

    # 组合
    if modifiers and main_key:
        return "+".join(modifiers + [main_key])
    elif main_key:
        return main_key
    elif modifiers:
        return "+".join(modifiers)
    return ""


def parse_hotkey(hotkey_str):
    """解析热键为 (modifiers, key)。

    返回：
        (set_of_modifiers, main_key)
    """
    normalized = normalize_hotkey(hotkey_str)
    if not normalized:
        return set(), ""

    parts = normalized.split("+")
    modifiers = set()
    main_key = ""

    for part in parts:
        if part in MODIFIER_KEYS:
            modifiers.add(part)
        else:
            main_key = part

    return modifiers, main_key


class HotkeyConflictDetector:
    """热键冲突检测器"""

    def __init__(self):
        self._registered = {}  # {hotkey: [function_names]}
        self._function_hotkeys = {}  # {function_name: hotkey}
        self._check_system = True
        self._check_game = True

    def register(self, function_name, hotkey_str):
        """注册热键。

        参数：
            function_name: 功能名称
            hotkey_str: 热键字符串

        返回：
            (success, conflicts)
            success: 是否注册成功（无冲突）
            conflicts: 冲突列表
        """
        normalized = normalize_hotkey(hotkey_str)
        if not normalized:
            return False, ["无效热键"]

        # 检查冲突
        has_conflict, conflicts = self.check(normalized)

        if has_conflict:
            log_warning(f"[热键冲突] {function_name} 尝试注册 {normalized}，存在冲突: {conflicts}")
            return False, conflicts

        # 注册
        if normalized not in self._registered:
            self._registered[normalized] = []
        self._registered[normalized].append(function_name)
        self._function_hotkeys[function_name] = normalized

        log(f"[热键冲突] 已注册: {function_name} -> {normalized}")
        return True, []

    def unregister(self, function_name):
        """注销热键。"""
        if function_name in self._function_hotkeys:
            hotkey = self._function_hotkeys.pop(function_name)
            if hotkey in self._registered:
                if function_name in self._registered[hotkey]:
                    self._registered[hotkey].remove(function_name)
                if not self._registered[hotkey]:
                    del self._registered[hotkey]

    def check(self, hotkey_str):
        """检查热键是否有冲突。

        参数：
            hotkey_str: 热键字符串

        返回：
            (has_conflict, conflicts)
            conflicts: [{"type": "internal"/"system"/"game", "hotkey": str, "description": str}, ...]
        """
        normalized = normalize_hotkey(hotkey_str)
        if not normalized:
            return True, [{"type": "invalid", "hotkey": hotkey_str, "description": "无效热键"}]

        conflicts = []

        # 1. 内部冲突
        if normalized in self._registered and self._registered[normalized]:
            for func in self._registered[normalized]:
                conflicts.append({
                    "type": "internal",
                    "hotkey": normalized,
                    "description": f"已被功能 '{func}' 占用",
                })

        # 2. 系统热键冲突
        if self._check_system and normalized in SYSTEM_HOTKEYS:
            conflicts.append({
                "type": "system",
                "hotkey": normalized,
                "description": f"系统热键: {SYSTEM_HOTKEYS[normalized]}",
            })

        # 3. 游戏常用热键冲突（仅单键）
        if self._check_game:
            modifiers, main_key = parse_hotkey(normalized)
            if not modifiers and main_key in GAME_COMMON_HOTKEYS:
                conflicts.append({
                    "type": "game",
                    "hotkey": normalized,
                    "description": f"游戏常用键: {GAME_COMMON_HOTKEYS[main_key]}",
                })

        return len(conflicts) > 0, conflicts

    def check_all(self):
        """检查所有已注册热键，返回所有冲突。

        返回：
            [{"hotkey": str, "functions": [str], "conflicts": [...]}, ...]
        """
        all_conflicts = []
        for hotkey, funcs in self._registered.items():
            if len(funcs) > 1:
                all_conflicts.append({
                    "hotkey": hotkey,
                    "functions": funcs,
                    "conflicts": [{"type": "internal", "description": f"多个功能共用: {', '.join(funcs)}"}],
                })
        return all_conflicts

    def suggest_alternative(self, hotkey_str):
        """建议替代热键。

        参数：
            hotkey_str: 冲突的热键

        返回：
            [suggested_hotkey, ...]
        """
        modifiers, main_key = parse_hotkey(hotkey_str)
        suggestions = []

        # 尝试添加修饰键
        if "Ctrl" not in modifiers:
            alt = normalize_hotkey("Ctrl+" + hotkey_str)
            if not self.check(alt)[0]:
                suggestions.append(alt)
        if "Alt" not in modifiers:
            alt = normalize_hotkey("Alt+" + hotkey_str)
            if not self.check(alt)[0]:
                suggestions.append(alt)
        if "Shift" not in modifiers:
            alt = normalize_hotkey("Shift+" + hotkey_str)
            if not self.check(alt)[0]:
                suggestions.append(alt)

        # 尝试 F 键
        for f_key in [f"F{i}" for i in range(1, 13)]:
            alt = normalize_hotkey("Ctrl+" + f_key)
            if not self.check(alt)[0]:
                suggestions.append(alt)
                if len(suggestions) >= 5:
                    break

        return suggestions[:5]

    def get_registered(self):
        """获取所有已注册热键。

        返回：
            {function_name: hotkey}
        """
        return dict(self._function_hotkeys)

    def set_check_system(self, enabled):
        """设置是否检测系统热键冲突。"""
        self._check_system = enabled

    def set_check_game(self, enabled):
        """设置是否检测游戏常用键冲突。"""
        self._check_game = enabled

    def export_config(self, filepath):
        """导出热键配置到文件。"""
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(self._function_hotkeys, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            log_error(f"[热键冲突] 导出配置失败: {e}")
            return False

    def import_config(self, filepath):
        """从文件导入热键配置。"""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                config = json.load(f)
            self._registered.clear()
            self._function_hotkeys.clear()
            for func, hotkey in config.items():
                self.register(func, hotkey)
            return True
        except Exception as e:
            log_error(f"[热键冲突] 导入配置失败: {e}")
            return False


# 全局热键冲突检测器单例
_global_detector = None


def get_hotkey_detector():
    """获取全局热键冲突检测器"""
    global _global_detector
    if _global_detector is None:
        _global_detector = HotkeyConflictDetector()
    return _global_detector
