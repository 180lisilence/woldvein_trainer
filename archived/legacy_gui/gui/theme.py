"""
主题管理模块
功能：深色/浅色主题切换，支持动态切换所有UI组件颜色

主题设计：
    - dark：Catppuccin Mocha（当前 v0.3 深色主题）
    - light：Catppuccin Latte（浅色主题，与深色同族系，视觉一致）

使用方式：
    from src.gui.theme import ThemeManager, current_theme
    ThemeManager.apply(style, root, "dark")
    ThemeManager.toggle(style, root)
"""
import tkinter as tk
from tkinter import ttk

# ---------------------------------------------------------------- 字体（唯一定义源）
# GUI 各处的 font=(...) 一律引用这里的常量，避免重复的字体元组散落各处
FONT_TITLE = ("微软雅黑", 14, "bold")
FONT_SUB = ("微软雅黑", 11, "bold")
FONT_BOLD = ("微软雅黑", 10, "bold")
FONT_BODY = ("微软雅黑", 10)
FONT_TINY = ("微软雅黑", 9)
FONT_MONO_LG = ("Consolas", 12, "bold")
FONT_MONO_BOLD = ("Consolas", 10, "bold")
FONT_MONO = ("Consolas", 9)


# 深色主题色板（Catppuccin Mocha）
DARK = {
    "name": "dark",
    # 背景层级（由深到浅）
    "bg":          "#1e1e2e",   # 主背景（Crust）
    "bg_surface":  "#11111b",   # 最深（Mantle，日志区）
    "bg_card":     "#313244",   # 卡片/面板（Surface0）
    "bg_elevated": "#45475a",   # 按钮悬浮（Surface1）
    "bg_selected": "#585b70",   # 选中态（Surface2）
    # 文字
    "fg":          "#cdd6f4",   # 主文字（Text）
    "fg_muted":    "#6c7086",   # 次要文字（Overlay0）
    "fg_bright":   "#f5e0dc",   # 高亮文字（Rosewater）
    # 强调色
    "accent":      "#89b4fa",   # 主强调（Blue）
    "accent_hover":"#74c7ec",   # 悬浮态（Sapphire）
    # 语义色
    "success":     "#a6e3a1",   # 成功（Green）
    "warning":     "#f9e2af",   # 警告（Yellow）
    "error":       "#f38ba8",   # 错误（Red）
    "info":        "#89b4fa",   # 信息（Blue）
}

# 浅色主题色板（Catppuccin Latte）
LIGHT = {
    "name": "light",
    "bg":          "#eff1f5",   # 主背景
    "bg_surface":  "#e6e9ef",   # 日志区
    "bg_card":     "#ffffff",   # 卡片/面板
    "bg_elevated": "#dce0e8",   # 按钮悬浮
    "bg_selected": "#bcc0cc",   # 选中态
    # 文字
    "fg":          "#4c4f69",   # 主文字
    "fg_muted":    "#9ca0b0",   # 次要文字
    "fg_bright":   "#526fe0",   # 高亮文字
    # 强调色
    "accent":      "#1e66f5",   # 主强调
    "accent_hover":"#2ac3de",   # 悬浮态
    # 语义色
    "success":     "#40a02b",   # 成功
    "warning":     "#df8e1d",   # 警告
    "error":       "#d20f39",   # 错误
    "info":        "#1e66f5",   # 信息
}

# 微信风格浅色主题（WeChat Light）
WECHAT = {
    "name": "wechat",
    "bg":          "#f5f5f5",
    "bg_surface":  "#ebebeb",
    "bg_card":     "#ffffff",
    "bg_elevated": "#f0f0f0",
    "bg_selected": "#e8f5e9",
    "bg_sidebar":  "#f7f7f7",
    "bg_sidebar_sel": "#07C160",
    "fg":          "#000000",
    "fg_muted":    "#999999",
    "fg_bright":   "#07C160",
    "fg_sidebar":  "#000000",
    "fg_sidebar_muted": "#666666",
    "accent":      "#07C160",
    "accent_hover":"#06ad56",
    "success":     "#07C160",
    "warning":     "#fa9d3b",
    "error":       "#fa5151",
    "info":        "#10aeff",
    "border":      "#e6e6e6",
}


# 主题映射
THEMES = {"dark": DARK, "light": LIGHT, "wechat": WECHAT}
_current = "wechat"


def get_theme():
    """获取当前主题字典"""
    return THEMES[_current]


def get_theme_name():
    """获取当前主题名称"""
    return _current


class ThemeManager:
    """主题管理器：统一应用和管理深色/浅色主题"""

    @staticmethod
    def apply(style, root, theme_name=None):
        """应用指定主题（或切换当前主题）

        参数：
            style: ttk.Style 实例
            root: tk.Tk 根窗口
            theme_name: "dark" / "light"，None 则切换到另一个主题
        """
        global _current
        if theme_name:
            _current = theme_name
        else:
            _current = "light" if _current == "dark" else "dark"

        t = THEMES[_current]

        # 根窗口背景
        root.configure(bg=t["bg"])

        # 标签页（选中态强化：更亮背景+加粗文字）
        style.configure("TNotebook", background=t["bg"], borderwidth=0)
        style.configure("TNotebook.Tab", background=t["bg_card"], foreground=t["fg_muted"],
                        padding=[18, 10], font=FONT_BODY)
        style.map("TNotebook.Tab",
                  background=[("selected", t["bg_elevated"]), ("active", t["bg_selected"])],
                  foreground=[("selected", t["accent"]), ("active", t["fg"])])

        # 框架
        style.configure("TFrame", background=t["bg"])
        style.configure("Card.TFrame", background=t["bg_card"], relief="flat")

        # 标签
        style.configure("TLabel", background=t["bg"], foreground=t["fg"], font=FONT_BODY)
        style.configure("Card.TLabel", background=t["bg_card"], foreground=t["fg"], font=FONT_BODY)
        style.configure("Title.TLabel", background=t["bg"], foreground=t["accent"],
                        font=FONT_TITLE)
        style.configure("Success.TLabel", background=t["bg"], foreground=t["success"], font=FONT_BODY)
        style.configure("Warning.TLabel", background=t["bg"], foreground=t["warning"], font=FONT_BODY)
        style.configure("Error.TLabel", background=t["bg"], foreground=t["error"], font=FONT_BODY)

        # 按钮（统一高度28px，hover亮度提升，active下沉效果）
        style.configure("TButton", background=t["bg_elevated"], foreground=t["fg"],
                        font=FONT_BODY, padding=[14, 7], borderwidth=0)
        style.map("TButton",
                  background=[("active", t["bg_selected"]), ("hover", t["bg_selected"])],
                  foreground=[("active", t["fg_bright"]), ("hover", t["fg_bright"])])

        style.configure("Primary.TButton", background=t["accent"], foreground="white",
                        font=FONT_BOLD, padding=[16, 8], borderwidth=0)
        style.map("Primary.TButton",
                  background=[("active", t["accent_hover"]), ("hover", t["accent_hover"])])

        style.configure("Success.TButton", background=t["success"], foreground="white",
                        font=FONT_BOLD, padding=[16, 8], borderwidth=0)
        style.map("Success.TButton",
                  background=[("active", "#94d38f"), ("hover", "#94d38f")])

        style.configure("Danger.TButton", background=t["error"], foreground="white",
                        font=FONT_BOLD, padding=[16, 8], borderwidth=0)
        style.map("Danger.TButton",
                  background=[("active", "#e07088"), ("hover", "#e07088")])

        style.configure("Small.TButton", background=t["bg_elevated"], foreground=t["fg"],
                        font=FONT_TINY, padding=[8, 3], borderwidth=0)
        style.map("Small.TButton",
                  background=[("active", t["bg_selected"])],
                  foreground=[("active", t["fg_bright"])])

        # 左侧导航按钮（PCL2 风格：左对齐；选中态强调色）
        style.configure("Nav.TButton", background=t["bg_card"], foreground=t["fg_muted"],
                        font=FONT_BODY, padding=[16, 10], anchor="w", borderwidth=0)
        style.map("Nav.TButton",
                  background=[("active", t["bg_elevated"]), ("hover", t["bg_elevated"])],
                  foreground=[("active", t["accent"]), ("hover", t["accent"])])
        style.configure("NavActive.TButton", background=t["bg_elevated"], foreground=t["accent"],
                        font=FONT_BOLD, padding=[16, 10], anchor="w", borderwidth=0)
        style.map("NavActive.TButton",
                  background=[("active", t["bg_selected"]), ("hover", t["bg_selected"])],
                  foreground=[("active", t["accent"]), ("hover", t["accent"])])

        # 恢复按钮样式（v0.3 新增）
        style.configure("Restore.TButton", background=t["warning"], foreground="white",
                        font=("微软雅黑", 9, "bold"), padding=[8, 3], borderwidth=0)
        style.map("Restore.TButton",
                  background=[("active", t["bg_selected"])])

        # 次要按钮（灰色，v0.3 UI优化新增）
        style.configure("Secondary.TButton", background=t["bg_elevated"], foreground=t["fg_muted"],
                        font=FONT_BODY, padding=[12, 6], borderwidth=0)
        style.map("Secondary.TButton",
                  background=[("active", t["bg_selected"])],
                  foreground=[("active", t["fg"])])

        # 状态指示灯标签（绿点/黄点/红点 + 文字，v0.3 UI优化新增）
        style.configure("Status.TLabel", background=t["bg_card"], foreground=t["fg"],
                        font=FONT_BODY)
        style.configure("StatusSuccess.TLabel", background=t["bg_card"], foreground=t["success"],
                        font=FONT_BOLD)
        style.configure("StatusWarning.TLabel", background=t["bg_card"], foreground=t["warning"],
                        font=FONT_BOLD)
        style.configure("StatusError.TLabel", background=t["bg_card"], foreground=t["error"],
                        font=FONT_BOLD)

        # 禁用状态按钮（置灰，v0.3 UI优化新增）
        style.configure("Disabled.TButton", background=t["bg_card"], foreground=t["fg_muted"],
                        font=FONT_BODY, padding=[12, 6], borderwidth=0)

        # 输入框
        style.configure("TEntry", fieldbackground=t["bg_card"], foreground=t["fg"],
                        insertcolor=t["fg"], borderwidth=0)

        # 组合框
        style.configure("TCombobox", fieldbackground=t["bg_card"], foreground=t["fg"],
                        background=t["bg_elevated"], borderwidth=0)

        # 进度条
        style.configure("Horizontal.TProgressbar", background=t["accent"], troughcolor=t["bg_card"], borderwidth=0)

        # Treeview
        style.configure("Treeview",
                        background=t["bg_card"],
                        foreground=t["fg"],
                        fieldbackground=t["bg_card"],
                        borderwidth=0,
                        rowheight=24,
                        font=FONT_TINY)
        style.configure("Treeview.Heading",
                        background=t["bg_elevated"],
                        foreground=t["fg"],
                        borderwidth=0,
                        font=("微软雅黑", 9, "bold"))
        style.map("Treeview",
                  background=[("selected", t["bg_selected"])],
                  foreground=[("selected", t["fg_bright"])])
        style.map("Treeview.Heading",
                  background=[("active", t["bg_selected"])])

        # 滚动条
        style.configure("TScrollbar",
                        background=t["bg_card"],
                        troughcolor=t["bg"],
                        borderwidth=0,
                        arrowcolor=t["fg"])
        style.map("TScrollbar",
                  background=[("active", t["bg_elevated"])])

    @staticmethod
    def toggle(style, root):
        """切换主题（dark↔light），返回切换后的主题名"""
        ThemeManager.apply(style, root)
        return _current

    @staticmethod
    def get_color(key):
        """获取当前主题中指定键的颜色值"""
        return THEMES[_current].get(key, "#000000")

    @staticmethod
    def get_log_colors():
        """获取日志区颜色配置（bg, fg, insertbg）"""
        t = THEMES[_current]
        return t["bg_surface"], t["fg"], t["fg"]
