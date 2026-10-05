"""
异步执行 + 按钮冷却辅助

功能说明：
    run_async()        在后台线程执行函数，异常统一写日志（不吞异常、不崩溃UI）
    CooldownButton     给按钮加冷却：点击后禁用 N 秒并改文字，到时自动恢复

    原先 main_gui._run_async / tab_advanced._adv_with_cooldown /
    tab_creative.on_toggle_creative 各自手写一份 threading.Thread 逻辑，
    现统一收敛到本模块（main_gui._run_async 保留为薄壳以兼容既有调用点）。
"""
import threading
import traceback
import tkinter as tk

from src.logger import log_error


def run_async(widget, func, *args):
    """后台线程执行 func(*args)，异常写日志。

    参数：
        widget: 任意 tkinter 控件（保留用于后续扩展 after 调度；当前仅作占位）
        func:   被执行的函数
        args:   传给 func 的位置参数
    """
    def worker():
        try:
            func(*args)
        except Exception as e:
            func_name = getattr(func, '__name__', str(func))
            tb = traceback.format_exc()
            log_error(f"执行异常 [{func_name} args={args}]: {e}\n{tb}")
    threading.Thread(target=worker, daemon=True).start()


class CooldownButton:
    """给按钮加冷却：点击后禁用 N 秒，冷却期间按钮显示提示文字"""

    def __init__(self, button, seconds=3, cooldown_text="{name} (冷却中...)"):
        self.button = button
        self.seconds = seconds
        self.cooldown_text = cooldown_text
        self._running = False

    def run(self, func, name="操作"):
        """触发一次操作（冷却期间重复调用被忽略）"""
        if self._running:
            return
        self._running = True
        try:
            original_text = self.button.cget("text")
        except tk.TclError:
            self._running = False
            return
        try:
            self.button.config(state=tk.DISABLED,
                               text=self.cooldown_text.format(name=name))
        except tk.TclError:
            self._running = False
            return

        def worker():
            try:
                func()
            except Exception as e:
                log_error(f"{name}异常: {e}")
            finally:
                def restore():
                    try:
                        if self.button.winfo_exists():
                            self.button.config(state=tk.NORMAL, text=original_text)
                    except tk.TclError:
                        pass
                    self._running = False
                try:
                    self.button.after(self.seconds * 1000, restore)
                except tk.TclError:
                    self._running = False

        threading.Thread(target=worker, daemon=True).start()
