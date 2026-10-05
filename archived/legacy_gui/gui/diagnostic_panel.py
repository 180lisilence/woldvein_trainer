"""
通用诊断面板组件

封装诊断按钮 + 输出文本框的组合，支持：
- 自定义标题、描述、按钮文字
- 异步执行诊断函数
- 结果自动显示到文本框
- 运行中按钮禁用并显示"诊断中..."
- 深色主题适配

使用方式：
    panel = self._build_diagnostic_panel(
        parent=tab,
        title="建筑解锁诊断",
        description="诊断当前游戏内建筑解锁状态",
        button_text="🔍 运行诊断",
        button_style="Primary.TButton",
        diag_func=diagnose_unlock_status,
        check_injected=lambda: self.dll_injected,
        output_height=10,
    )

diag_func 签名：() -> (success: bool, result: str)
"""
import tkinter as tk
from tkinter import ttk, scrolledtext
import threading
from .widgets import T
from .theme import FONT_MONO, FONT_SUB


def build_diagnostic_panel(parent, title, description, button_text,
                           diag_func, check_injected=None,
                           button_style="Primary.TButton",
                           output_height=8, expand=True):
    """
    构建一个诊断面板（标题 + 描述 + 按钮 + 输出文本框）。

    参数:
        parent: 父容器
        title: 面板标题
        description: 功能描述文本
        button_text: 按钮显示文字
        diag_func: 诊断函数，返回 (success, result)
        check_injected: 可选，返回bool的函数，用于检查DLL是否已注入
        button_style: 按钮样式名
        output_height: 输出框高度（行数）
        expand: 是否垂直扩展填充满

    返回:
        dict 包含引用：{frame, btn, text_widget, _run_diag}
    """
    frame = ttk.Frame(parent, style="Card.TFrame")
    frame.pack(fill=tk.BOTH if expand else tk.X, expand=expand, padx=15, pady=(0, 15))

    # 标题
    ttk.Label(frame, text=title, style="Card.TLabel",
              font=FONT_SUB).pack(anchor=tk.W, padx=15, pady=(10, 5))

    # 描述
    ttk.Label(frame, text=description, style="Card.TLabel",
              foreground=T("fg_muted")).pack(anchor=tk.W, padx=15, pady=(0, 5))

    # 按钮
    diag_btn = ttk.Button(frame, text=button_text, style=button_style)
    diag_btn.pack(anchor=tk.W, padx=15, pady=(0, 10))

    # 输出文本框
    diag_text = scrolledtext.ScrolledText(frame, height=output_height, wrap=tk.WORD,
                                            bg=T("bg"), fg=T("fg"),
                                            insertbackground=T("fg"),
                                            font=FONT_MONO)
    diag_text.pack(fill=tk.BOTH, expand=expand, padx=15, pady=(0, 15))
    diag_text.insert(tk.END, f'点击上方"{button_text}"按钮，诊断结果将显示在这里...')
    diag_text.config(state=tk.DISABLED)

    # ---- 内部状态 ----
    state = {"running": False}
    original_text = button_text

    def _show_result(text):
        """显示诊断结果到文本框（成功绿色、失败红色高亮）"""
        diag_text.config(state=tk.NORMAL)
        diag_text.delete("1.0", tk.END)
        # 配置标签颜色
        diag_text.tag_configure("success", foreground=T("success"))
        diag_text.tag_configure("error", foreground=T("error"))
        diag_text.tag_configure("warning", foreground=T("warning"))
        diag_text.tag_configure("info", foreground=T("accent"))
        # 逐行着色
        for line in text.split("\n"):
            line_lower = line.lower()
            if any(kw in line_lower for kw in ["成功", "✓", "已解锁", "已开启", "ok", "pass", "正常"]):
                diag_text.insert(tk.END, line + "\n", "success")
            elif any(kw in line_lower for kw in ["失败", "✗", "未解锁", "错误", "error", "fail", "异常", "nil"]):
                diag_text.insert(tk.END, line + "\n", "error")
            elif any(kw in line_lower for kw in ["警告", "⚠", "warning", "注意"]):
                diag_text.insert(tk.END, line + "\n", "warning")
            else:
                diag_text.insert(tk.END, line + "\n", "info")
        diag_text.config(state=tk.DISABLED)

    def _set_busy(busy):
        """设置按钮繁忙状态"""
        if busy:
            diag_btn.config(state=tk.DISABLED, text="诊断中...")
        else:
            diag_btn.config(state=tk.NORMAL, text=original_text)

    def _run_diag():
        """执行诊断（异步）"""
        if state["running"]:
            return
        if check_injected and not check_injected():
            from tkinter import messagebox
            messagebox.showwarning("提示", "请先注入DLL。")
            return

        state["running"] = True
        _set_busy(True)

        def worker():
            try:
                success, result = diag_func()
                # result 可能是字符串，也可能是 -1（失败int）
                text = result if isinstance(result, str) else str(result)
                _safe_after(diag_btn, lambda: _show_result(text))
            except Exception as e:
                _safe_after(diag_btn, lambda: _show_result(f"诊断异常: {e}"))
            finally:
                state["running"] = False
                _safe_after(diag_btn, lambda: _set_busy(False))

        threading.Thread(target=worker, daemon=True).start()

    diag_btn.config(command=_run_diag)

    return {
        "frame": frame,
        "btn": diag_btn,
        "text_widget": diag_text,
        "run_diag": _run_diag,
        "show_result": _show_result,
    }


def _safe_after(widget, callback):
    """线程安全地在主线程调度回调。

    直接调用 widget.after 在 GUI 销毁中可能抛 TclError，
    用 try/except 包裹避免 worker 线程崩溃。
    也兼容 widget 已被销毁的情况。
    """
    try:
        widget.after(0, callback)
    except Exception:
        # GUI 已销毁或主循环已退出，回调丢弃即可
        pass


def attach_diag_to_button(button, diag_func, on_result, check_injected=None, busy_text="诊断中..."):
    """
    给已有按钮附加诊断功能（轻量版，结果通过回调输出）。

    适用场景：按钮已经在某个布局里了，不需要整套面板，
    只需要"点击按钮 → 异步执行诊断 → 结果回调给调用方"。

    参数:
        button: ttk.Button 实例（已创建好的）
        diag_func: 诊断函数，返回 (success, result)
        on_result: 结果回调，签名 on_result(result_str)
        check_injected: 可选，返回bool的函数，用于检查DLL是否已注入
        busy_text: 繁忙时按钮显示的文字

    返回:
        dict: {run_diag, set_busy}
    """
    state = {"running": False}
    original_text = button.cget("text")

    def _set_busy(busy):
        if busy:
            button.config(state=tk.DISABLED, text=busy_text)
        else:
            button.config(state=tk.NORMAL, text=original_text)

    def run_diag():
        if state["running"]:
            return
        if check_injected and not check_injected():
            from tkinter import messagebox
            messagebox.showwarning("提示", "请先注入DLL。")
            return

        state["running"] = True
        _set_busy(True)

        def worker():
            try:
                success, result = diag_func()
                text = result if isinstance(result, str) else str(result)
                _safe_after(button, lambda: on_result(text))
            except Exception as e:
                _safe_after(button, lambda: on_result(f"诊断异常: {e}"))
            finally:
                state["running"] = False
                _safe_after(button, lambda: _set_busy(False))

        threading.Thread(target=worker, daemon=True).start()

    button.config(command=run_diag)

    return {
        "run_diag": run_diag,
        "set_busy": _set_busy,
    }
