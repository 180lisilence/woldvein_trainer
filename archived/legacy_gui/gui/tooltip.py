"""
悬浮提示（Tooltip）组件
功能：鼠标悬停在控件上时显示提示文字，可显示绑定的热键

使用方式：
    from src.gui.tooltip import Tooltip
    Tooltip(button, "增加金钱100万\n快捷键: Ctrl+F1")

特点：
    - 延迟显示（500ms），避免鼠标划过频繁触发
    - 深色主题适配
    - 支持多行文字（\n 换行）
    - 自动定位在控件下方
"""
import tkinter as tk
from .widgets import T
from .theme import FONT_TINY


class Tooltip:
    """悬浮提示：鼠标悬停时显示提示文字"""

    def __init__(self, widget, text, delay=500):
        """
        参数：
            widget: 绑定的控件
            text: 提示文字（支持\n换行）
            delay: 延迟显示时间（毫秒），默认500ms
        """
        self.widget = widget
        self.text = text
        self.delay = delay
        self._tip_window = None
        self._after_id = None

        # 绑定事件
        widget.bind("<Enter>", self._on_enter)
        widget.bind("<Leave>", self._on_leave)
        widget.bind("<ButtonPress>", self._on_leave)  # 点击时隐藏

    def _on_enter(self, event=None):
        """鼠标进入：延迟显示"""
        self._cancel()
        self._after_id = self.widget.after(self.delay, self._show)

    def _on_leave(self, event=None):
        """鼠标离开：隐藏"""
        self._cancel()
        self._hide()

    def _cancel(self):
        """取消延迟显示"""
        if self._after_id:
            self.widget.after_cancel(self._after_id)
            self._after_id = None

    def _show(self):
        """显示提示框"""
        if self._tip_window:
            return

        # 获取控件位置
        x = self.widget.winfo_rootx()
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5

        # 创建提示窗口
        self._tip_window = tk.Toplevel(self.widget)
        self._tip_window.overrideredirect(True)
        self._tip_window.attributes("-topmost", True)

        # 内容
        frame = tk.Frame(self._tip_window, bg=T("bg_elevated"), padx=10, pady=6,
                         highlightbackground=T("bg_selected"), highlightthickness=1)
        frame.pack()

        # 支持多行
        for i, line in enumerate(self.text.split("\n")):
            label = tk.Label(frame, text=line, bg=T("bg_elevated"), fg=T("fg"),
                             font=FONT_TINY, justify=tk.LEFT)
            label.pack(anchor=tk.W)

        # 定位
        self._tip_window.geometry(f"+{x}+{y}")

    def _hide(self):
        """隐藏提示框"""
        if self._tip_window:
            try:
                self._tip_window.destroy()
            except tk.TclError:
                pass
            self._tip_window = None


def bind_tooltip(widget, text, delay=500):
    """便捷函数：为控件绑定Tooltip，返回Tooltip实例"""
    return Tooltip(widget, text, delay)
