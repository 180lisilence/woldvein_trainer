"""
热键设置标签页 Mixin
功能：Ctrl+F1~F12，可双击编辑，管理员权限检查
"""
import threading

import tkinter as tk
from tkinter import ttk, messagebox

from src.hotkey_manager import hotkey_manager
from src.config import save_config
from src.hotkey_defs import get_hotkey_names, get_default_hotkeys
from src.resource_editor import add_resource, add_fame, max_happiness
from src.logger import log, log_success, log_warning
from .widgets import T
from .theme import FONT_TINY


class HotkeyTabMixin:
    """热键设置标签页 Mixin"""

    def _on_hotkey_double_click(self, event):
        """双击热键列表项，弹出捕获窗口"""
        item = self.hotkey_tree.identify_row(event.y)
        if not item:
            return
        func_key = self.hotkey_key_to_func.get(item)
        if not func_key:
            return
        self._show_hotkey_capture(item, func_key)

    def _show_hotkey_capture(self, item_id, func_key):
        """显示热键捕获窗口"""
        capture = tk.Toplevel(self.root)
        capture.title("捕获热键")
        capture.geometry("300x150")
        capture.resizable(False, False)
        capture.transient(self.root)
        capture.grab_set()

        # 居中
        capture.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 300) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 150) // 2
        capture.geometry(f"+{x}+{y}")

        ttk.Label(capture, text="请按下新的热键组合", font=("微软雅黑", 11)).pack(pady=20)
        key_label = ttk.Label(capture, text="等待按键...", font=("Consolas", 14, "bold"),
                              foreground=T("accent"))
        key_label.pack(pady=5)
        ttk.Label(capture, text="按 Esc 取消", font=FONT_TINY, foreground=T("fg_muted")).pack(pady=10)

        captured = {"done": False}

        def on_key_press(event):
            if captured["done"]:
                return
            if event.keysym == "Escape":
                capture.destroy()
                return
            # 收集修饰键和主键
            key = event.keysym
            if key in ("Control_L", "Control_R", "Shift_L", "Shift_R", "Alt_L", "Alt_R"):
                return  # 修饰键在释放时处理
            # 构建组合键字符串
            parts = []
            if event.state & 0x4:  # Ctrl
                parts.append("Ctrl")
            if event.state & 0x1:  # Shift
                parts.append("Shift")
            if event.state & 0x20000:  # Alt (Windows Tk的Alt位是0x20000)
                parts.append("Alt")
            # 主键格式化
            main_key = key
            if key.startswith("F") and key[1:].isdigit():
                main_key = key  # F1-F12
            elif len(key) == 1:
                main_key = key.upper()
            parts.append(main_key)
            combo = "+".join(parts)

            captured["done"] = True
            key_label.config(text=combo, foreground=T("success"))

            # 保存配置
            self.config["hotkeys"][func_key] = combo
            save_config(self.config)
            # 更新Treeview
            self.hotkey_tree.item(item_id, values=(self.hotkey_tree.item(item_id, "values")[0], combo))
            # 重新注册热键
            self._re_register_hotkeys()
            capture.after(500, capture.destroy)

        capture.bind("<KeyPress>", on_key_press)
        capture.focus_set()

    def _re_register_hotkeys(self):
        """重新注册所有热键（用户修改热键后调用，修改即生效）"""
        from src.hotkey_manager import hotkey_manager
        hotkey_manager.disable()
        # 清空旧热键
        hotkey_manager.hotkeys.clear()
        self._register_hotkeys()
        # 用户修改热键后期望立即生效，无条件启用
        # 同时同步UI开关状态
        hotkey_manager.enable()
        if hasattr(self, 'hotkey_enabled_var'):
            self.hotkey_enabled_var.set(True)
        if hasattr(self, 'hotkey_status'):
            self.hotkey_status.config(text="热键：已启用", style="Success.TLabel")

    def _register_hotkeys(self):
        """注册全局热键回调"""
        # 资源类热键从 RESOURCES 定义自动生成，避免与资源列表脱节
        from src.resource_defs import RESOURCES
        hotkey_map = {}
        for res in RESOURCES:
            if res["hotkey_key"]:
                hotkey_map[res["hotkey_key"]] = (
                    lambda rid=res["id"]: self._run_async(add_resource, rid, 1000000)
                )
        hotkey_map["fame"] = lambda: self._run_async(add_fame, 10000)
        hotkey_map["happiness"] = lambda: self._run_async(max_happiness)
        hotkey_map["creative_mode"] = self._hotkey_toggle_creative
        for key, callback in hotkey_map.items():
            combo = self.config["hotkeys"].get(key, "")
            if combo:
                hotkey_manager.register(combo, callback)
        log(f"已注册 {len(hotkey_map)} 个全局热键")

    def _enable_hotkeys_silent(self):
        """静默启用热键（热键设置已独立为工具，仅记录日志）"""
        if hotkey_manager.enable():
            log_success("全局热键已启用")
        else:
            log_warning("热键启用失败（可能缺少keyboard库或权限不足）")

    def on_toggle_hotkeys(self):
        """切换热键（兼容无热键标签页的情况）

        主界面已不再构建热键标签页，hotkey_enabled_var / hotkey_status
        可能不存在，因此所有控件访问均做存在性判断。
        """
        if hotkey_manager.is_enabled():
            hotkey_manager.disable()
            if hasattr(self, 'hotkey_status'):
                self.hotkey_status.config(text="热键：未启用", style="Warning.TLabel")
            if hasattr(self, 'hotkey_enabled_var'):
                self.hotkey_enabled_var.set(False)
        else:
            if hotkey_manager.enable():
                if hasattr(self, 'hotkey_status'):
                    self.hotkey_status.config(text="热键：已启用", style="Success.TLabel")
                if hasattr(self, 'hotkey_enabled_var'):
                    self.hotkey_enabled_var.set(True)
            else:
                if hasattr(self, 'hotkey_status'):
                    self.hotkey_status.config(text="热键：启用失败（缺少keyboard库）", style="Error.TLabel")

    def _reset_hotkeys(self):
        """恢复默认热键"""
        from tkinter import messagebox
        if not messagebox.askyesno("确认", "确定要恢复所有热键为默认值吗？"):
            return
        default_hotkeys = get_default_hotkeys()
        self.config["hotkeys"] = default_hotkeys.copy()
        save_config(self.config)
        # 更新Treeview
        for item_id, func_key in self.hotkey_key_to_func.items():
            combo = default_hotkeys.get(func_key, "")
            self.hotkey_tree.item(item_id, values=(self.hotkey_tree.item(item_id, "values")[0], combo))
        self._re_register_hotkeys()
        log("热键已恢复为默认值")

    def _clear_all_hotkeys(self):
        """清空所有热键"""
        from tkinter import messagebox
        if not messagebox.askyesno("确认", "确定要清空所有热键吗？"):
            return
        for key in self.config["hotkeys"]:
            self.config["hotkeys"][key] = ""
        save_config(self.config)
        # 更新Treeview
        for item_id in self.hotkey_key_to_func:
            self.hotkey_tree.item(item_id, values=(self.hotkey_tree.item(item_id, "values")[0], ""))
        self._re_register_hotkeys()
        log("所有热键已清空")
