"""
全局 Toast 轻提示组件
功能：在窗口右上角或顶部显示短暂的操作反馈提示

使用方式：
    from src.gui.toast import ToastManager
    self.toast = ToastManager(root)
    self.toast.show("操作成功", "success")
    self.toast.show("操作失败", "error")

样式：
    - success：绿色背景，用于成功操作
    - error：红色背景，用于失败操作
    - warning：黄色背景，用于警告
    - info：蓝色背景，用于信息提示
"""
import tkinter as tk
from tkinter import ttk
from .widgets import T
from .theme import FONT_BOLD


class ToastManager:
    """全局Toast管理器：在窗口右上角显示短暂提示"""

    def __init__(self, root):
        self.root = root
        self._toasts = []
        self._offset_y = 10  # 初始Y偏移

    def show(self, message, level="info", duration=2500):
        """显示Toast提示

        参数：
            message: 提示文字
            level: success / error / warning / info
            duration: 显示时长（毫秒），默认2500ms
        """
        # 颜色配置
        colors = {
            "success": (T("success"), T("bg")),
            "error":   (T("error"), T("bg")),
            "warning": (T("warning"), T("bg")),
            "info":    (T("accent"), T("bg")),
        }
        bg, fg = colors.get(level, colors["info"])

        # 创建Toast窗口（无边框顶层窗口）
        toast = tk.Toplevel(self.root)
        toast.overrideredirect(True)  # 无边框
        toast.attributes("-topmost", True)

        # 内容框架
        frame = tk.Frame(toast, bg=bg, padx=15, pady=8)
        frame.pack()

        label = tk.Label(frame, text=message, bg=bg, fg=fg,
                         font=FONT_BOLD)
        label.pack()

        # 计算位置：右上角，多个Toast纵向堆叠
        self.root.update_idletasks()
        root_x = self.root.winfo_x()
        root_y = self.root.winfo_y()
        root_w = self.root.winfo_width()
        toast_w = frame.winfo_reqwidth() + 30

        x = root_x + root_w - toast_w - 15
        y = root_y + 10 + self._offset_y

        toast.geometry(f"+{x}+{y}")
        self._offset_y += 50  # 下一个Toast往下移

        self._toasts.append(toast)

        # 淡入效果
        toast.attributes("-alpha", 0.0)
        self._fade_in(toast, 0)

        # 定时消失
        toast.after(duration, lambda: self._fade_out(toast))

    def _fade_in(self, toast, alpha):
        """淡入动画"""
        if alpha < 1.0:
            alpha += 0.1
            try:
                toast.attributes("-alpha", alpha)
                toast.after(20, lambda: self._fade_in(toast, alpha))
            except tk.TclError:
                pass  # 窗口已销毁

    def _fade_out(self, toast):
        """淡出动画并销毁"""
        def fade(alpha):
            if alpha > 0:
                alpha -= 0.1
                try:
                    toast.attributes("-alpha", alpha)
                    toast.after(20, lambda: fade(alpha))
                except tk.TclError:
                    self._remove(toast)
            else:
                self._remove(toast)
        fade(1.0)

    def _remove(self, toast):
        """移除Toast并重置偏移"""
        try:
            toast.destroy()
        except tk.TclError:
            pass
        if toast in self._toasts:
            self._toasts.remove(toast)
        self._offset_y = max(10, self._offset_y - 50)
