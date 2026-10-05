"""
woldvein Trainer v0.3 - 全局热键管理模块

功能说明：
    管理全局热键的注册、启用、禁用。使用keyboard库实现全局钩子，
    用户在任何界面（包括游戏内）按下热键组合即可触发对应功能。

核心设计：
    HotkeyManager类：
        - hotkeys: 热键映射字典（key_combo -> callback）
        - _handlers: keyboard库返回的handler对象（用于注销）
        - enabled: 是否已启用
        - register(): 注册单个热键
        - unregister(): 注销单个热键
        - enable(): 启用所有热键（部分失败时回滚）
        - disable(): 禁用所有热键（只移除自己注册的）

技术要点：
    - 热键格式统一小写（keyboard库要求）
    - 启用失败时回滚已注册的热键，避免部分注册状态
    - disable()不调用keyboard.unhook_all()，只移除自己注册的handler
    - 全局热键需要管理员权限，非管理员时警告
    - keyboard库缺失时优雅降级（HAS_KEYBOARD=False）

热键列表（默认）：
    Ctrl+F1  金钱+100万
    Ctrl+F2  食物+100万
    Ctrl+F3  水+100万
    Ctrl+F4  衣物+100万
    Ctrl+F5  木料+100万
    Ctrl+F6  矿产+100万
    Ctrl+F7  盐+100万
    Ctrl+F8  酒+100万
    Ctrl+F9  知名度+10000
    Ctrl+F10 切换创造模式
    Ctrl+F12 幸福度满级
"""
import sys
from .logger import log, log_success, log_warning

# 尝试导入keyboard库
# 缺失时HAS_KEYBOARD=False，热键功能不可用但不影响其他功能
try:
    import keyboard
    HAS_KEYBOARD = True
except ImportError:
    HAS_KEYBOARD = False
    log_warning("keyboard库未安装，热键功能不可用（pip install keyboard）")


def is_admin():
    """
    检查当前进程是否以管理员身份运行。

    返回：
        True表示管理员权限，False表示普通权限

    说明：
        全局热键（keyboard库的全局钩子）在Windows下通常需要管理员权限。
        非管理员时热键可能注册失败或不生效。
    """
    try:
        if sys.platform == 'win32':
            import ctypes
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        pass  # 权限检测失败默认返回False
    return False


class HotkeyManager:
    """
    全局热键管理器。

    管理热键的注册、启用、禁用，支持失败回滚。
    """

    def __init__(self):
        """初始化热键管理器"""
        self.hotkeys = {}       # key_combo -> callback 映射
        self._handlers = {}     # key_combo -> keyboard handler 对象（用于注销）
        self.enabled = False    # 是否已启用全局热键
        self._admin_warned = False  # 管理员权限警告是否已显示（避免重复警告）

    def register(self, key_combo, callback):
        """
        注册一个热键。

        参数：
            key_combo: 热键组合字符串（如 "Ctrl+F1"）
            callback: 热键触发时的回调函数

        说明：
            - 热键格式转换为小写（keyboard库要求）
            - 如果已启用，立即注册到keyboard库
            - 注册失败只记录警告，不影响其他热键
        """
        # 转换为keyboard库兼容的格式（小写）
        normalized = key_combo.lower()
        # 先注销旧的（防止重复注册导致handler泄漏）
        if normalized in self._handlers:
            self.unregister(key_combo)
        self.hotkeys[normalized] = callback
        if self.enabled and HAS_KEYBOARD:
            try:
                handler = keyboard.add_hotkey(normalized, callback)
                self._handlers[normalized] = handler
                log(f"热键已注册: {key_combo}")
            except Exception as e:
                log_warning(f"热键注册失败 {key_combo}: {e}")

    def unregister(self, key_combo):
        """
        注销一个热键。

        参数：
            key_combo: 热键组合字符串
        """
        # 统一小写（与register保持一致）
        normalized = key_combo.lower()
        if normalized in self.hotkeys:
            del self.hotkeys[normalized]
        if normalized in self._handlers:
            if HAS_KEYBOARD:
                try:
                    keyboard.remove_hotkey(self._handlers[normalized])
                except Exception:
                    pass  # 注销失败不影响状态
            del self._handlers[normalized]

    def enable(self):
        """
        启用所有已注册的热键。

        返回：
            True表示启用成功，False表示失败

        处理逻辑：
            1. 检查keyboard库是否可用
            2. 检查管理员权限（首次警告）
            3. 遍历所有热键，逐个注册
            4. 任一注册失败 → 回滚已注册的，返回False
            5. 全部成功 → 设置enabled=True，返回True

        注意：
            失败时回滚已注册的热键，避免部分注册的不一致状态。
        """
        if not HAS_KEYBOARD:
            log_warning("热键功能不可用（缺少keyboard库，请执行: pip install keyboard）")
            return False

        # 检查管理员权限（只警告一次）
        if not is_admin() and not self._admin_warned:
            self._admin_warned = True
            log_warning("警告：全局热键可能需要管理员权限才能正常工作，请以管理员身份运行修改器")

        if self.enabled:
            return True

        if not self.hotkeys:
            log_warning("没有已注册的热键")
            return False

        added = []  # 记录已成功注册的热键，用于失败回滚
        try:
            for key_combo, callback in self.hotkeys.items():
                handler = keyboard.add_hotkey(key_combo, callback)
                self._handlers[key_combo] = handler
                added.append(key_combo)
            self.enabled = True
            log_success(f"全局热键已启用 ({len(self.hotkeys)} 个)")
            return True
        except Exception as e:
            # 回滚已注册的热键
            for key in added:
                try:
                    keyboard.remove_hotkey(self._handlers[key])
                except Exception:
                    pass  # 回滚时注销失败不影响
                self._handlers.pop(key, None)
            log_warning(f"热键启用失败，已回滚: {e}")
            return False

    def disable(self):
        """
        禁用所有热键。

        说明：
            只移除自己注册的handler，不调用keyboard.unhook_all()
            （unhook_all会移除进程内所有钩子，可能误伤其他模块）
        """
        if not self.enabled:
            return
        if HAS_KEYBOARD:
            for key_combo, handler in list(self._handlers.items()):
                try:
                    keyboard.remove_hotkey(handler)
                except Exception:
                    pass  # 批量禁用时单个失败不影响整体
        self._handlers.clear()
        self.enabled = False
        log("全局热键已禁用")

    def is_enabled(self):
        """返回热键是否已启用"""
        return self.enabled


# 全局热键管理器实例（单例）
hotkey_manager = HotkeyManager()
