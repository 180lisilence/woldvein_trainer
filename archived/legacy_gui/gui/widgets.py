"""
统一控件工厂 + 主题色取用

功能说明：
    GUI 中大量 tk.Frame / tk.Label 直接硬编码颜色（"#313244"、"#45475a"、
    "#11111b" 等），导致浅色主题下颜色错乱。本模块提供：

        T(key)              取当前主题色（见 theme.ThemeManager.get_color）
        card_frame(parent)  卡片底色的 tk.Frame
        card_label(...)     卡片底色的 tk.Label
        section_header(...) 小节标题 label

    新代码应优先使用本模块；改造旧代码时按需替换硬编码色值。
"""
import tkinter as tk

from .theme import FONT_BOLD, FONT_TINY, ThemeManager


def T(key):
    """取当前主题色值"""
    return ThemeManager.get_color(key)


def card_frame(parent, **kw):
    """卡片底色的 tk.Frame"""
    kw.setdefault("bg", T("bg_card"))
    return tk.Frame(parent, **kw)


def card_label(parent, text, **kw):
    """卡片底色的 tk.Label（默认字体与前景色统一）"""
    kw.setdefault("bg", T("bg_card"))
    kw.setdefault("fg", T("fg"))
    kw.setdefault("font", FONT_TINY)
    return tk.Label(parent, text=text, **kw)


def section_header(parent, text, **kw):
    """小节标题 label（略深背景 + 加粗）"""
    kw.setdefault("bg", T("bg_elevated"))
    kw.setdefault("fg", T("fg"))
    kw.setdefault("font", FONT_BOLD)
    return tk.Label(parent, text=text, **kw)


# ============================================================
# 主题切换重绘（tk 原生控件不随 ttk 样式自动变色，需手动重绘）
# ============================================================

# tk / ttk 控件的颜色选项名（覆盖 Frame/Label/Entry/Text/Canvas 等）
_COLOR_OPTIONS = (
    "background", "foreground", "bg", "fg",
    "activebackground", "activeforeground",
    "insertbackground", "readonlybackground",
    "selectbackground", "selectforeground",
    "highlightbackground", "highlightcolor", "troughcolor",
)


def build_recolor_map(old_palette, new_palette):
    """构建 {旧色值: 新色值} 映射（仅含 #RRGGBB 且两侧都有的键）"""
    m = {}
    for k, v in (old_palette or {}).items():
        if isinstance(v, str) and v.startswith("#") and k in (new_palette or {}):
            m[v.lower()] = new_palette[k]
    return m


def recolor_widget_tree(widget, mapping):
    """递归重绘整棵控件树的颜色选项

    用 T("key") 上色的 tk 控件（Frame/Label/Entry/Text）只在上色那一刻取色，
    主题切换后颜色会残留；本函数在切换时按 {旧色值: 新色值} 映射重绘回去。
    ttk 控件由样式负责（显式设了 foreground/background 的也会一并修正）。
    """
    if not mapping:
        return
    try:
        new_opts = {}
        for opt in _COLOR_OPTIONS:
            try:
                val = widget.cget(opt)
            except Exception:
                continue
            if isinstance(val, str) and val.lower() in mapping:
                new_opts[opt] = mapping[val.lower()]
        if new_opts:
            widget.configure(**new_opts)
    except Exception:
        # 控件正在销毁 / 不支持该选项：跳过，不影响其他控件
        pass
    try:
        children = widget.winfo_children()
    except Exception:
        return
    for child in children:
        recolor_widget_tree(child, mapping)


# ============================================================
# 教室座位式网格布局（按钮矩阵）
# ============================================================

def button_grid(parent, buttons, per_row=4, btn_width=12, padx=4, pady=4,
                default_style="Primary.TButton"):
    """创建教室座位式网格布局的按钮组（每行固定 N 个，整齐排列）

    像教室座位一样，每行固定 per_row 个按钮，填满一行自动换行，
    所有按钮大小一致，间距统一，视觉整齐划一。

    Args:
        parent: 父容器
        buttons: 按钮配置列表，每个元素可以是：
                 - 元组 (text, command)
                 - 元组 (text, command, style)
                 - 字典 {"text": ..., "command": ..., "style": ..., "width": ...}
        per_row: 每行按钮数（教室每排座位数），默认 4
        btn_width: 按钮默认宽度（字符数），默认 12
        padx: 按钮水平间距，默认 4
        pady: 按钮垂直间距，默认 4
        default_style: 默认按钮样式，默认 "Primary.TButton"

    Returns:
        包含按钮网格的 tk.Frame
    """
    from tkinter import ttk

    container = tk.Frame(parent, bg=T("bg_card"))

    for i, btn_config in enumerate(buttons):
        row = i // per_row
        col = i % per_row

        # 解析按钮配置
        if isinstance(btn_config, dict):
            text = btn_config.get("text", "")
            command = btn_config.get("command", None)
            style = btn_config.get("style", default_style)
            width = btn_config.get("width", btn_width)
        elif isinstance(btn_config, (tuple, list)):
            if len(btn_config) >= 3:
                text, command, style = btn_config[0], btn_config[1], btn_config[2]
            elif len(btn_config) == 2:
                text, command = btn_config[0], btn_config[1]
                style = default_style
            else:
                text = str(btn_config[0]) if btn_config else ""
                command = None
                style = default_style
            width = btn_width
        else:
            text = str(btn_config)
            command = None
            style = default_style
            width = btn_width

        # 创建按钮（左对齐，保持原始大小，避免拉伸导致点击异常）
        btn = ttk.Button(container, text=text, style=style, command=command, width=width)
        btn.grid(row=row, column=col, padx=padx, pady=pady, sticky="w")

    return container
