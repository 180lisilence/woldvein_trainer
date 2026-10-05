"""
woldvein Trainer v0.4.6 - 主题增强模块

提供多种预设主题和自定义主题功能。

预设主题：
    - dark: 暗色主题（默认）
    - light: 亮色主题
    - midnight: 午夜蓝主题
    - forest: 森林绿主题
    - sunset: 日落橙主题
    - high_contrast: 高对比度主题

功能：
    - 切换预设主题
    - 自定义主题颜色
    - 主题保存/加载
    - 获取主题颜色值

使用方式：
    from .theme_manager import ThemeManager, get_theme
    theme = ThemeManager()
    theme.set_theme("dark")
    bg_color = theme.get_color("background")
"""
import os
import sys
import json
import copy

from .logger import log, log_success, log_error, log_warning
from .atomic_file import atomic_write_json


# 预设主题定义
PRESET_THEMES = {
    "dark": {
        "name": "暗色主题",
        "description": "经典暗色主题，护眼舒适",
        "colors": {
            "background": "#1e1e1e",
            "surface": "#252526",
            "surface_hover": "#2d2d30",
            "border": "#3c3c3c",
            "text": "#e0e0e0",
            "text_secondary": "#a0a0a0",
            "text_disabled": "#606060",
            "accent": "#007acc",
            "accent_hover": "#1e8ad8",
            "success": "#4ec9b0",
            "warning": "#dcdcaa",
            "error": "#f44747",
            "info": "#569cd6",
            "sidebar_bg": "#252526",
            "sidebar_text": "#cccccc",
            "sidebar_active": "#094771",
            "statusbar_bg": "#007acc",
            "statusbar_text": "#ffffff",
            "button_bg": "#3c3c3c",
            "button_hover": "#505050",
            "button_text": "#e0e0e0",
            "input_bg": "#3c3c3c",
            "input_text": "#e0e0e0",
            "input_border": "#505050",
            "scrollbar_bg": "#2d2d30",
            "scrollbar_thumb": "#5a5a5a",
        },
        "fonts": {
            "family": "Microsoft YaHei UI",
            "size": 10,
            "title_size": 14,
            "mono_family": "Consolas",
        },
    },
    "light": {
        "name": "亮色主题",
        "description": "清爽亮色主题，适合白天使用",
        "colors": {
            "background": "#f5f5f5",
            "surface": "#ffffff",
            "surface_hover": "#f0f0f0",
            "border": "#d0d0d0",
            "text": "#333333",
            "text_secondary": "#666666",
            "text_disabled": "#999999",
            "accent": "#0078d4",
            "accent_hover": "#106ebe",
            "success": "#107c10",
            "warning": "#ff8c00",
            "error": "#d13438",
            "info": "#0078d4",
            "sidebar_bg": "#ffffff",
            "sidebar_text": "#333333",
            "sidebar_active": "#deecf9",
            "statusbar_bg": "#0078d4",
            "statusbar_text": "#ffffff",
            "button_bg": "#ffffff",
            "button_hover": "#f0f0f0",
            "button_text": "#333333",
            "input_bg": "#ffffff",
            "input_text": "#333333",
            "input_border": "#d0d0d0",
            "scrollbar_bg": "#f0f0f0",
            "scrollbar_thumb": "#c0c0c0",
        },
        "fonts": {
            "family": "Microsoft YaHei UI",
            "size": 10,
            "title_size": 14,
            "mono_family": "Consolas",
        },
    },
    "midnight": {
        "name": "午夜蓝",
        "description": "深邃午夜蓝主题，科技感强",
        "colors": {
            "background": "#0d1117",
            "surface": "#161b22",
            "surface_hover": "#1f2937",
            "border": "#30363d",
            "text": "#c9d1d9",
            "text_secondary": "#8b949e",
            "text_disabled": "#484f58",
            "accent": "#58a6ff",
            "accent_hover": "#79b8ff",
            "success": "#3fb950",
            "warning": "#d29922",
            "error": "#f85149",
            "info": "#58a6ff",
            "sidebar_bg": "#161b22",
            "sidebar_text": "#c9d1d9",
            "sidebar_active": "#1f6feb",
            "statusbar_bg": "#1f6feb",
            "statusbar_text": "#ffffff",
            "button_bg": "#21262d",
            "button_hover": "#30363d",
            "button_text": "#c9d1d9",
            "input_bg": "#0d1117",
            "input_text": "#c9d1d9",
            "input_border": "#30363d",
            "scrollbar_bg": "#161b22",
            "scrollbar_thumb": "#30363d",
        },
        "fonts": {
            "family": "Microsoft YaHei UI",
            "size": 10,
            "title_size": 14,
            "mono_family": "Consolas",
        },
    },
    "forest": {
        "name": "森林绿",
        "description": "自然森林绿主题，清新护眼",
        "colors": {
            "background": "#1a2f1a",
            "surface": "#243424",
            "surface_hover": "#2d422d",
            "border": "#3d5a3d",
            "text": "#d4e8d4",
            "text_secondary": "#a0c0a0",
            "text_disabled": "#608060",
            "accent": "#4caf50",
            "accent_hover": "#66bb6a",
            "success": "#81c784",
            "warning": "#ffb74d",
            "error": "#e57373",
            "info": "#64b5f6",
            "sidebar_bg": "#243424",
            "sidebar_text": "#d4e8d4",
            "sidebar_active": "#2e7d32",
            "statusbar_bg": "#2e7d32",
            "statusbar_text": "#ffffff",
            "button_bg": "#3d5a3d",
            "button_hover": "#4a6b4a",
            "button_text": "#d4e8d4",
            "input_bg": "#1a2f1a",
            "input_text": "#d4e8d4",
            "input_border": "#3d5a3d",
            "scrollbar_bg": "#243424",
            "scrollbar_thumb": "#4a6b4a",
        },
        "fonts": {
            "family": "Microsoft YaHei UI",
            "size": 10,
            "title_size": 14,
            "mono_family": "Consolas",
        },
    },
    "sunset": {
        "name": "日落橙",
        "description": "温暖日落橙主题，活力满满",
        "colors": {
            "background": "#2d1f1a",
            "surface": "#3d2a22",
            "surface_hover": "#4d352a",
            "border": "#6b4a3a",
            "text": "#f0e0d4",
            "text_secondary": "#c0a090",
            "text_disabled": "#806050",
            "accent": "#ff6b35",
            "accent_hover": "#ff8c5a",
            "success": "#4caf50",
            "warning": "#ffc107",
            "error": "#f44336",
            "info": "#2196f3",
            "sidebar_bg": "#3d2a22",
            "sidebar_text": "#f0e0d4",
            "sidebar_active": "#e65100",
            "statusbar_bg": "#e65100",
            "statusbar_text": "#ffffff",
            "button_bg": "#6b4a3a",
            "button_hover": "#8b5a4a",
            "button_text": "#f0e0d4",
            "input_bg": "#2d1f1a",
            "input_text": "#f0e0d4",
            "input_border": "#6b4a3a",
            "scrollbar_bg": "#3d2a22",
            "scrollbar_thumb": "#8b5a4a",
        },
        "fonts": {
            "family": "Microsoft YaHei UI",
            "size": 10,
            "title_size": 14,
            "mono_family": "Consolas",
        },
    },
    "high_contrast": {
        "name": "高对比度",
        "description": "高对比度主题，适合视力障碍用户",
        "colors": {
            "background": "#000000",
            "surface": "#000000",
            "surface_hover": "#1a1a1a",
            "border": "#ffffff",
            "text": "#ffffff",
            "text_secondary": "#ffff00",
            "text_disabled": "#808080",
            "accent": "#00ffff",
            "accent_hover": "#80ffff",
            "success": "#00ff00",
            "warning": "#ffff00",
            "error": "#ff0000",
            "info": "#00ffff",
            "sidebar_bg": "#000000",
            "sidebar_text": "#ffffff",
            "sidebar_active": "#0000ff",
            "statusbar_bg": "#0000ff",
            "statusbar_text": "#ffffff",
            "button_bg": "#000000",
            "button_hover": "#1a1a1a",
            "button_text": "#ffffff",
            "input_bg": "#000000",
            "input_text": "#ffffff",
            "input_border": "#ffffff",
            "scrollbar_bg": "#000000",
            "scrollbar_thumb": "#ffffff",
        },
        "fonts": {
            "family": "Microsoft YaHei UI",
            "size": 12,
            "title_size": 16,
            "mono_family": "Consolas",
        },
    },
}


class ThemeManager:
    """主题管理器"""

    def __init__(self, config_dir=None):
        """
        参数：
            config_dir: 配置目录，用于保存自定义主题
        """
        self._current_theme = "dark"
        self._custom_themes = {}
        self._listeners = []
        self._config_dir = config_dir or self._default_config_dir()

        # 加载自定义主题
        self._load_custom_themes()

    def _default_config_dir(self):
        """获取默认配置目录"""
        if getattr(sys, "frozen", False):
            base = os.path.dirname(sys.executable)
        else:
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base, "themes")

    def _load_custom_themes(self):
        """加载自定义主题"""
        custom_file = os.path.join(self._config_dir, "custom_themes.json")
        if os.path.exists(custom_file):
            try:
                with open(custom_file, "r", encoding="utf-8") as f:
                    self._custom_themes = json.load(f)
                log(f"[主题] 已加载 {len(self._custom_themes)} 个自定义主题")
            except Exception as e:
                log_error(f"[主题] 加载自定义主题失败: {e}")

    def _save_custom_themes(self):
        """保存自定义主题"""
        os.makedirs(self._config_dir, exist_ok=True)
        custom_file = os.path.join(self._config_dir, "custom_themes.json")
        try:
            atomic_write_json(custom_file, self._custom_themes)
        except Exception as e:
            log_error(f"[主题] 保存自定义主题失败: {e}")

    def get_available_themes(self):
        """获取所有可用主题。

        返回：
            {theme_id: {"name": str, "description": str, "is_custom": bool}, ...}
        """
        themes = {}
        for tid, theme in PRESET_THEMES.items():
            themes[tid] = {
                "name": theme["name"],
                "description": theme["description"],
                "is_custom": False,
            }
        for tid, theme in self._custom_themes.items():
            themes[tid] = {
                "name": theme.get("name", tid),
                "description": theme.get("description", "自定义主题"),
                "is_custom": True,
            }
        return themes

    def set_theme(self, theme_id):
        """切换主题。

        参数：
            theme_id: 主题ID

        返回：
            True 成功，False 失败
        """
        if theme_id in PRESET_THEMES or theme_id in self._custom_themes:
            old_theme = self._current_theme
            self._current_theme = theme_id
            log_success(f"[主题] 已切换到: {self.get_theme_name()}")
            self._notify_listeners(old_theme, theme_id)
            return True
        log_error(f"[主题] 未知主题: {theme_id}")
        return False

    def get_theme(self):
        """获取当前主题完整配置。

        返回：
            主题配置字典
        """
        if self._current_theme in self._custom_themes:
            return copy.deepcopy(self._custom_themes[self._current_theme])
        return copy.deepcopy(PRESET_THEMES.get(self._current_theme, PRESET_THEMES["dark"]))

    def get_color(self, color_name):
        """获取当前主题的颜色值。

        参数：
            color_name: 颜色名称，如 "background", "accent"

        返回：
            颜色十六进制字符串，如 "#1e1e1e"
        """
        theme = self.get_theme()
        return theme.get("colors", {}).get(color_name, "#000000")

    def get_font(self, font_name):
        """获取当前主题的字体配置。

        参数：
            font_name: 字体名称，如 "family", "size"

        返回：
            字体配置值
        """
        theme = self.get_theme()
        return theme.get("fonts", {}).get(font_name)

    def get_current_theme_id(self):
        """获取当前主题ID。"""
        return self._current_theme

    def get_theme_name(self):
        """获取当前主题显示名称。"""
        theme = self.get_theme()
        return theme.get("name", self._current_theme)

    def create_custom_theme(self, theme_id, name, description, colors, fonts=None):
        """创建自定义主题。

        参数：
            theme_id: 主题ID
            name: 主题名称
            description: 主题描述
            colors: 颜色字典
            fonts: 字体字典（可选）

        返回：
            True 成功，False 失败
        """
        if theme_id in PRESET_THEMES:
            log_error(f"[主题] 主题ID '{theme_id}' 与预设主题冲突")
            return False

        self._custom_themes[theme_id] = {
            "name": name,
            "description": description,
            "colors": colors,
            "fonts": fonts or PRESET_THEMES["dark"]["fonts"],
        }
        self._save_custom_themes()
        log_success(f"[主题] 已创建自定义主题: {name}")
        return True

    def delete_custom_theme(self, theme_id):
        """删除自定义主题。

        返回：
            True 成功，False 失败
        """
        if theme_id not in self._custom_themes:
            return False
        if self._current_theme == theme_id:
            self.set_theme("dark")
        del self._custom_themes[theme_id]
        self._save_custom_themes()
        log(f"[主题] 已删除自定义主题: {theme_id}")
        return True

    def export_theme(self, theme_id, filepath):
        """导出主题到文件。"""
        theme = None
        if theme_id in PRESET_THEMES:
            theme = PRESET_THEMES[theme_id]
        elif theme_id in self._custom_themes:
            theme = self._custom_themes[theme_id]

        if not theme:
            return False

        try:
            atomic_write_json(filepath, theme)
            log_success(f"[主题] 已导出主题到: {filepath}")
            return True
        except Exception as e:
            log_error(f"[主题] 导出主题失败: {e}")
            return False

    def import_theme(self, filepath):
        """从文件导入主题。"""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                theme = json.load(f)

            theme_id = theme.get("id", f"custom_{int(time.time())}")
            if theme_id not in PRESET_THEMES:
                self._custom_themes[theme_id] = theme
                self._save_custom_themes()
                log_success(f"[主题] 已导入主题: {theme.get('name', theme_id)}")
                return theme_id
            return None
        except Exception as e:
            log_error(f"[主题] 导入主题失败: {e}")
            return None

    def add_listener(self, listener):
        """添加主题切换监听器。

        参数：
            listener: 回调函数 listener(old_theme, new_theme)
        """
        self._listeners.append(listener)

    def remove_listener(self, listener):
        """移除监听器。"""
        if listener in self._listeners:
            self._listeners.remove(listener)

    def _notify_listeners(self, old_theme, new_theme):
        """通知所有监听器。"""
        for listener in self._listeners:
            try:
                listener(old_theme, new_theme)
            except Exception as e:
                log_error(f"[主题] 监听器异常: {e}")

    def apply_to_tkinter(self, root):
        """将主题应用到 tkinter 窗口。

        参数：
            root: tkinter 根窗口
        """
        try:
            theme = self.get_theme()
            colors = theme["colors"]

            root.configure(bg=colors["background"])

            # 配置 ttk 样式（如果使用 ttk）
            try:
                from tkinter import ttk
                style = ttk.Style()
                style.theme_use("default")

                style.configure(".",
                    background=colors["background"],
                    foreground=colors["text"],
                    fieldbackground=colors["input_bg"],
                    bordercolor=colors["border"],
                )
                style.configure("TFrame", background=colors["background"])
                style.configure("TLabel", background=colors["background"], foreground=colors["text"])
                style.configure("TButton",
                    background=colors["button_bg"],
                    foreground=colors["button_text"],
                    bordercolor=colors["border"],
                )
                style.map("TButton",
                    background=[("active", colors["button_hover"])],
                )
                style.configure("TEntry",
                    fieldbackground=colors["input_bg"],
                    foreground=colors["input_text"],
                    bordercolor=colors["input_border"],
                )
            except Exception:
                pass

            log(f"[主题] 已应用到 tkinter 窗口")
        except Exception as e:
            log_error(f"[主题] 应用到 tkinter 失败: {e}")


# 全局主题管理器单例
_global_theme_manager = None


def get_theme_manager():
    """获取全局主题管理器"""
    global _global_theme_manager
    if _global_theme_manager is None:
        _global_theme_manager = ThemeManager()
    return _global_theme_manager


def get_theme():
    """便捷函数：获取当前主题"""
    return get_theme_manager().get_theme()


def get_color(color_name):
    """便捷函数：获取当前主题颜色"""
    return get_theme_manager().get_color(color_name)
