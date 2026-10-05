"""
可滚动框架组件
功能：为内容超出可视区域的面板提供水平+垂直滚动条

使用方式：
    from src.gui.scrollable import ScrollableFrame

    frame = ScrollableFrame(parent)
    frame.pack(fill=tk.BOTH, expand=True)
    # 往 frame.inner 中添加子组件
    ttk.Button(frame.inner, text="按钮").pack()
"""
import tkinter as tk
from tkinter import ttk


class ScrollableFrame(ttk.Frame):
    """可滚动框架

    内部使用 Canvas + Scrollbar 实现滚动，
    子组件应添加到 self.inner 而非 self。
    支持水平+垂直双向滚动，自动响应鼠标滚轮。

    属性：
        inner: 实际放置子组件的 ttk.Frame
    """

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)

        # 创建 Canvas（透明背景，让它看起来像直接在父容器中）
        self._canvas = tk.Canvas(self, highlightthickness=0, bd=0)
        self._canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 垂直滚动条
        self._vscroll = ttk.Scrollbar(self, orient=tk.VERTICAL,
                                      command=self._canvas.yview)
        self._vscroll.pack(side=tk.RIGHT, fill=tk.Y)

        # 水平滚动条
        self._hscroll = ttk.Scrollbar(self, orient=tk.HORIZONTAL,
                                      command=self._canvas.xview)
        self._hscroll.pack(side=tk.BOTTOM, fill=tk.X)

        # 配置 Canvas 滚动
        self._canvas.configure(yscrollcommand=self._vscroll.set,
                               xscrollcommand=self._hscroll.set)

        # 内部框架（子组件放在这里）
        self.inner = ttk.Frame(self._canvas)
        self._inner_id = self._canvas.create_window((0, 0), window=self.inner, anchor=tk.NW)

        # 绑定滚动区域更新
        self.inner.bind("<Configure>", self._on_inner_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)

        # 鼠标滚轮支持
        self._canvas.bind("<Enter>", self._on_enter)
        self._canvas.bind("<Leave>", self._on_leave)

    def _on_inner_configure(self, event):
        """内部内容变化时更新滚动区域"""
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        """Canvas 大小变化时调整内部框架宽度（跟随宽度）"""
        # 只在没有水平滚动需求时让 inner 跟随 canvas 宽度
        # 有水平滚动需求时 inner 保持内容自然宽度
        inner_width = self.inner.winfo_reqwidth()
        canvas_width = event.width
        if inner_width <= canvas_width:
            # 内容比 canvas 窄，inner 跟随 canvas 宽度
            self._canvas.itemconfig(self._inner_id, width=canvas_width)

    def _on_enter(self, event):
        """鼠标进入时绑定滚轮"""
        self._canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self._canvas.bind_all("<Shift-MouseWheel>", self._on_shift_mousewheel)

    def _on_leave(self, event):
        """鼠标离开时解绑滚轮"""
        self._canvas.unbind_all("<MouseWheel>")
        self._canvas.unbind_all("<Shift-MouseWheel>")

    def _on_mousewheel(self, event):
        """鼠标滚轮垂直滚动"""
        # Windows: delta 是 120 的倍数，Linux: delta 是 1
        delta = -1 * (event.delta // 120)
        self._canvas.yview_scroll(delta, "units")

    def _on_shift_mousewheel(self, event):
        """Shift+滚轮水平滚动"""
        delta = -1 * (event.delta // 120)
        self._canvas.xview_scroll(delta, "units")
