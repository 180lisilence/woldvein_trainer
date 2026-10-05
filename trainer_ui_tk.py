# -*- coding: utf-8 -*-
"""
平野孤鸿修改器 - tkinter 微信三栏布局版 v0.4.3
集成完整业务逻辑

运行：python trainer_ui_tk.py
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog, simpledialog
import sys
import os
import threading
import shutil
from datetime import datetime

# ============================================================
# 业务模块导入
# ============================================================
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.injector import find_game_process, inject_dll, is_dll_injected, launch_game, get_dll_path
from src.resource_editor import (
    add_resource, add_all_resources, zero_all_resources,
    max_happiness, add_fame, restore_happiness
)
from src.creative_mode import (
    enable_creative_mode, disable_creative_mode,
    is_creative_mode_enabled, set_creative_options,
    get_game_status, diagnose_unlock_status
)
from src.lua_engine import execute_lua_safe
from src.config import load_config, save_config
from src.logger import (
    init_log, set_log_callback, log, log_info, log_success,
    log_warning, log_error, get_log_path, clear_log_file
)
from src.resource_defs import RESOURCES, get_id_to_field
from src.game_status import get_status_provider
from src import advanced_tools
from src import world_tools
from src import cheat_tools
from src.hotkey_defs import HOTKEY_DEFS, get_default_hotkeys, get_hotkey_names
from src.constants import APP_VERSION, DEFAULT_GAME_PATH, SIM_COMMON_REL, RESOURCE_ADD_AMOUNT, FAME_ADD_AMOUNT

# 新增模块导入（v0.4.6 UI集成）
from src.i18n import get_i18n, t as i18n_t
from src.theme_manager import get_theme_manager
from src.emergency_stop import get_emergency_stop, trigger_emergency_stop, is_emergency_stopped
from src.operation_history import get_operation_history
from src.hotkey_conflict import get_hotkey_detector
from src.preset_manager import list_presets, save_preset, load_preset, delete_preset

# 新增模块导入（v0.4.9 引擎性能优化）
from src import perf_optimizer
from src.perf_optimizer import (
    PROFILES, PROFILE_ORDER,
    apply_profile as perf_apply, restore as perf_restore,
    read_current as perf_read, current_profile as perf_current,
    recommend_profile as perf_recommend, set_single as perf_set_single,
    set_gpu_preference as perf_set_gpu, disable_fullscreen_optimizations as perf_disable_fso,
    hardware_summary as perf_hw, backup_info as perf_backup_info,
    _dynamic_value as perf_dyn,
)

# 新增模块导入（v0.5.0 离线化 / 免 Steam 启动）
from src import offline_crack
from src.offline_crack import (
    status as oc_status, install as oc_install, uninstall as oc_uninstall,
    launch as oc_launch, kill_game as oc_kill, last_login as oc_last_login,
    self_check as oc_self_check, payload_ready as oc_payload_ready,
)

# ============================================================
# 配色（微信风格）
# ============================================================
COLORS = {
    "bg": "#f5f5f5", "bg_sidebar": "#f7f7f7", "bg_sidebar_sel": "#07C160",
    "bg_card": "#ffffff", "bg_hover": "#f2f2f2", "bg_selected": "#e8f5e9",
    "fg": "#000000", "fg_muted": "#999999", "fg_sidebar": "#000000",
    "fg_sidebar_sel": "#ffffff", "accent": "#07C160", "accent_hover": "#06ad56",
    "success": "#07C160", "warning": "#fa9d3b", "error": "#fa5151",
    "border": "#e6e6e6",
}

# 深色主题配色
DARK_COLORS = {
    "bg": "#1e1e1e", "bg_sidebar": "#252526", "bg_sidebar_sel": "#07C160",
    "bg_card": "#2d2d2d", "bg_hover": "#3c3c3c", "bg_selected": "#1e3a2f",
    "fg": "#ffffff", "fg_muted": "#888888", "fg_sidebar": "#cccccc",
    "fg_sidebar_sel": "#ffffff", "accent": "#07C160", "accent_hover": "#06ad56",
    "success": "#4ec9b0", "warning": "#dcdcaa", "error": "#f48771",
    "border": "#3c3c3c",
}

# 保存浅色主题备份
LIGHT_COLORS = COLORS.copy()
_current_theme = "light"

def toggle_theme():
    """切换深浅主题"""
    global _current_theme, COLORS
    if _current_theme == "light":
        COLORS.update(DARK_COLORS)
        _current_theme = "dark"
    else:
        COLORS.update(LIGHT_COLORS)
        _current_theme = "light"
    return _current_theme
FONT = "微软雅黑"
# 自动适配开发环境和 PyInstaller 打包环境。
# 打包后注入器可能不在机器上：这里必须能容忍取不到（返回空串），
# 否则模块级求值会打断整个 import，exe 一启动就崩。
try:
    DLL_PATH = get_dll_path() or ""
except Exception:
    DLL_PATH = ""
VERSION = f"v{APP_VERSION}"  # 版本号唯一源：src/constants.py::APP_VERSION


# ============================================================
# 主窗口
# ============================================================
class TrainerApp:
    def __init__(self, root):
        self.root = root
        self.root.title(f"平野孤鸿 全能修改器 {VERSION}")
        self.root.geometry("1200x750")
        self.root.minsize(900, 600)
        self.root.configure(bg=COLORS["bg"])

        self.current_nav = 0
        self.current_func = 0
        self.nav_buttons = []
        self.func_items = []
        self.game_pid = None
        self.dll_injected = False
        self.config = load_config()
        self.creative_vars = {}
        self.resource_entries = {}

        init_log()
        set_log_callback(self._on_log_message)
        self._build_ui()
        self._switch_nav(0)
        self._start_status_timer()
        log_info(f"修改器 {VERSION} 已启动")

    # ===== 日志回调 =====
    def _on_log_message(self, msg, level="INFO"):
        def append():
            self.log_text.config(state=tk.NORMAL)
            color = {"INFO": COLORS["fg"], "SUCCESS": COLORS["success"],
                     "WARNING": COLORS["warning"], "ERROR": COLORS["error"]}.get(level, COLORS["fg"])
            self.log_text.insert(tk.END, f"[{level}] {msg}\n", level)
            self.log_text.tag_config(level, foreground=color)
            self.log_text.see(tk.END)
            self.log_text.config(state=tk.DISABLED)
        self.root.after(0, append)

    # ===== 状态检测 =====
    def _start_status_timer(self):
        self._update_status()
        self.root.after(3000, self._start_status_timer)

    def _update_status(self):
        try:
            # 注入器不可用（常见于打包后 exe 单独运行）时不要静默 —— 记一次，主页会显示
            from src import injector as _inj
            self.injector_error = getattr(_inj, "last_error", None) if not _inj.locate_injector() else None
            result = find_game_process()
            self.game_pid = result[0] if (result and isinstance(result, tuple) and result[0]) else (result if not isinstance(result, tuple) else None)
            self.dll_injected = is_dll_injected(self.game_pid, "woldvein_trainer.dll") if self.game_pid else False
            self._refresh_status_display()
        except Exception:
            pass

    def _refresh_status_display(self):
        if getattr(self, "injector_error", None):
            color, text = COLORS["error"], "注入器不可用 · 其余功能照常"
        elif self.game_pid and self.dll_injected:
            color, text = COLORS["success"], "游戏运行中 · DLL已注入"
        elif self.game_pid:
            color, text = COLORS["warning"], "游戏运行中 · DLL未注入"
        else:
            color, text = COLORS["error"], "未检测到游戏"
        try:
            if self.status_dot.winfo_exists():
                self.status_dot.config(fg=color)
            if self.title_desc.winfo_exists():
                self.title_desc.config(text=text)
        except:
            pass
        if hasattr(self, 'home_card_labels') and len(self.home_card_labels) >= 3:
            for label in self.home_card_labels:
                try:
                    if not label.winfo_exists():
                        return
                except:
                    return
            try:
                self.home_card_labels[0].config(text="运行中" if self.game_pid else "未运行",
                                                fg=COLORS["success"] if self.game_pid else COLORS["error"])
                self.home_card_labels[1].config(text="已注入" if self.dll_injected else "未注入",
                                                fg=COLORS["success"] if self.dll_injected else COLORS["warning"])
                self.home_card_labels[2].config(text="已连接" if self.dll_injected else "未连接",
                                                fg=COLORS["success"] if self.dll_injected else COLORS["fg_muted"])
            except:
                pass

    def _check_dll(self):
        if not self.dll_injected:
            log_warning("DLL未注入，请先注入DLL")
            return False
        return True

    def _on_mousewheel(self, event, canvas):
        """鼠标滚轮滚动处理"""
        try:
            if canvas.winfo_exists():
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        except:
            pass

    def _bind_mousewheel(self, widget, canvas):
        """为控件绑定鼠标滚轮事件"""
        widget.bind("<MouseWheel>", lambda e: self._on_mousewheel(e, canvas))
        # 递归绑定所有子控件
        for child in widget.winfo_children():
            self._bind_mousewheel(child, canvas)

    def _toggle_theme(self):
        """切换深浅主题"""
        theme = toggle_theme()
        if theme == "dark":
            self.theme_btn.config(text="☀️")
        else:
            self.theme_btn.config(text="🌙")
        # 保存当前导航位置
        current_nav = self.current_nav
        # 销毁并重建UI
        for widget in self.root.winfo_children():
            widget.destroy()
        self.root.configure(bg=COLORS["bg"])
        self._build_ui()
        # 延迟恢复导航位置（确保UI完全构建）
        self.root.after(100, lambda: self._switch_nav(current_nav))
        log_info(f"已切换到{'深色' if theme == 'dark' else '浅色'}主题")

    def _on_language_change(self, event=None):
        """语言切换处理"""
        lang_name = self.lang_var.get()
        i18n = get_i18n()
        for code, name in i18n.get_available_languages().items():
            if name == lang_name:
                i18n.set_language(code)
                self.config["language"] = code
                save_config(self.config)
                log_success(f"语言已切换为: {name}")
                messagebox.showinfo("语言切换", f"界面语言已切换为：{name}\n部分文本需重启后生效。")
                break

    def _on_theme_change(self, event=None):
        """主题切换处理"""
        theme_name = self.theme_var.get()
        theme_mgr = get_theme_manager()
        if theme_name == "深色":
            theme_mgr.set_theme("dark")
            global _current_theme, COLORS
            COLORS.update(DARK_COLORS)
            _current_theme = "dark"
        else:
            theme_mgr.set_theme("light")
            COLORS.update(LIGHT_COLORS)
            _current_theme = "light"
        self.config["theme"] = _current_theme
        save_config(self.config)
        log_success(f"主题已切换为: {theme_name}")
        self._toggle_theme()

    def _on_emergency_stop(self):
        """紧急停止处理"""
        if messagebox.askyesno("紧急停止", "确定要触发紧急停止吗？\n\n这将终止所有内存写入和Hook操作。"):
            trigger_emergency_stop("用户手动触发")
            log_error("紧急停止已触发！所有修改操作已终止。")
            messagebox.showwarning("紧急停止", "紧急停止已触发！\n所有内存写入操作已终止。\n\n如需恢复，请重启修改器。")

    def _on_save_preset(self):
        """保存当前配置为预设"""
        name = simpledialog.askstring("保存预设", "请输入预设名称：", parent=self.root)
        if name:
            try:
                save_preset(name, "用户保存的配置", self.config)
                log_success(f"预设 '{name}' 已保存")
                messagebox.showinfo("保存成功", f"预设 '{name}' 已保存。")
            except Exception as e:
                log_error(f"保存预设失败: {e}")
                messagebox.showerror("保存失败", f"保存预设失败：{e}")

    def _on_load_preset(self):
        """加载预设"""
        presets = list_presets()
        if not presets:
            messagebox.showinfo("无预设", "当前没有保存的预设。")
            return
        preset_names = [p["name"] for p in presets]
        choice = simpledialog.askstring("加载预设", f"可用预设：\n{', '.join(preset_names)}\n\n请输入要加载的预设名称：", parent=self.root)
        if choice:
            try:
                config = load_preset(choice)
                if config:
                    self.config.update(config)
                    save_config(self.config)
                    log_success(f"预设 '{choice}' 已加载")
                    messagebox.showinfo("加载成功", f"预设 '{choice}' 已加载，部分设置需重启生效。")
                else:
                    messagebox.showerror("加载失败", f"预设 '{choice}' 不存在。")
            except Exception as e:
                log_error(f"加载预设失败: {e}")
                messagebox.showerror("加载失败", f"加载预设失败：{e}")

    def _on_delete_preset(self):
        """删除预设"""
        presets = list_presets()
        if not presets:
            messagebox.showinfo("无预设", "当前没有保存的预设。")
            return
        preset_names = [p["name"] for p in presets]
        choice = simpledialog.askstring("删除预设", f"可用预设：\n{', '.join(preset_names)}\n\n请输入要删除的预设名称：", parent=self.root)
        if choice:
            if messagebox.askyesno("确认删除", f"确定要删除预设 '{choice}' 吗？"):
                try:
                    delete_preset(choice)
                    log_success(f"预设 '{choice}' 已删除")
                    messagebox.showinfo("删除成功", f"预设 '{choice}' 已删除。")
                except Exception as e:
                    log_error(f"删除预设失败: {e}")
                    messagebox.showerror("删除失败", f"删除预设失败：{e}")

    def _on_list_presets(self):
        """列出所有预设"""
        presets = list_presets()
        if not presets:
            messagebox.showinfo("预设列表", "当前没有保存的预设。")
            return
        text = "已保存的预设：\n\n"
        for p in presets:
            text += f"• {p['name']} - {p.get('description', '无描述')} ({p.get('created', '未知时间')})\n"
        messagebox.showinfo("预设列表", text)

    def _run_async(self, func, *args):
        threading.Thread(target=func, args=args, daemon=True).start()

    # ===== 构建三栏布局 =====
    def _build_ui(self):
        main = tk.Frame(self.root, bg=COLORS["bg"])
        main.pack(fill=tk.BOTH, expand=True)
        self._build_sidebar(main)
        tk.Frame(main, bg=COLORS["border"], width=1).pack(side=tk.LEFT, fill=tk.Y)
        self._build_func_panel(main)
        tk.Frame(main, bg=COLORS["border"], width=1).pack(side=tk.LEFT, fill=tk.Y)
        self._build_action_panel(main)

    # ===== 左侧导航 =====
    def _build_sidebar(self, parent):
        self.nav_buttons = []  # 重建前清空旧引用
        self.sidebar = tk.Frame(parent, bg=COLORS["bg_sidebar"], width=90)
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y)
        self.sidebar.pack_propagate(False)
        # v0.5.0 索引表（与 func_data / _update_action_panel 严格一一对应）
        #   0 主页  1 创造  2 工具  3 优化  4 存档  5 监控  6 内部  7 离线  8 设置
        # 注意：v0.4.9 曾把「优化」插在侧边栏第 3 位，但 func_data 仍是旧顺序，
        # 导致点「⚡优化」弹出的是存档面板。0.5.0 已把三处顺序统一按本表对齐。
        NAV_ITEMS = [("🏠","主页"),("✨","创造"),("🔧","工具"),("⚡","优化"),
                     ("💾","存档"),("📊","监控"),("📦","内部"),("🔓","离线")]
        for i, (icon, name) in enumerate(NAV_ITEMS):
            btn = tk.Button(self.sidebar, text=name, font=(FONT, 11), bg=COLORS["bg_sidebar"],
                          fg=COLORS["fg_sidebar"], bd=0, relief=tk.FLAT, cursor="hand2",
                          activebackground=COLORS["bg_sidebar_sel"], activeforeground=COLORS["fg_sidebar_sel"],
                          command=lambda idx=i: self._switch_nav(idx))
            btn.pack(fill=tk.X, pady=4, padx=8)
            self.nav_buttons.append(btn)
        tk.Frame(self.sidebar, bg=COLORS["bg_sidebar"]).pack(fill=tk.BOTH, expand=True)
        # 主题切换按钮
        self.theme_btn = tk.Button(self.sidebar, text="🌙", font=(FONT, 18), bg=COLORS["bg_sidebar"],
                                  fg=COLORS["fg_sidebar"], bd=0, relief=tk.FLAT, cursor="hand2",
                                  activebackground=COLORS["bg_sidebar_sel"], activeforeground=COLORS["fg_sidebar_sel"],
                                  command=self._toggle_theme)
        self.theme_btn.pack(pady=5)
        tk.Label(self.sidebar, text="🌿", font=(FONT, 22), bg=COLORS["bg_sidebar"], fg=COLORS["fg_muted"]).pack(pady=5)
        settings_btn = tk.Button(self.sidebar, text="设置", font=(FONT, 11), bg=COLORS["bg_sidebar"],
                               fg=COLORS["fg_sidebar"], bd=0, relief=tk.FLAT, cursor="hand2",
                               activebackground=COLORS["bg_sidebar_sel"], activeforeground=COLORS["fg_sidebar_sel"],
                               command=lambda: self._switch_nav(8))
        settings_btn.pack(fill=tk.X, pady=4, padx=8)
        self.nav_buttons.append(settings_btn)

    # ===== 中间功能列表 =====
    def _build_func_panel(self, parent):
        self.func_items = []  # 重建前清空旧引用
        self.func_panel = tk.Frame(parent, bg=COLORS["bg_card"], width=260)
        self.func_panel.pack(side=tk.LEFT, fill=tk.Y)
        self.func_panel.pack_propagate(False)

        search_frame = tk.Frame(self.func_panel, bg=COLORS["bg_sidebar"])
        search_frame.pack(fill=tk.X, padx=10, pady=10)
        self.search_entry = tk.Entry(search_frame, font=(FONT, 11), bd=0, relief=tk.FLAT,
                                    bg=COLORS["bg_card"], fg=COLORS["fg_muted"], highlightthickness=1,
                                    highlightcolor=COLORS["accent"], highlightbackground=COLORS["border"])
        self.search_entry.pack(fill=tk.X, ipady=6, padx=4, pady=2)
        self.search_entry.insert(0, "🔍 搜索功能...")
        self.search_entry.bind("<FocusIn>", self._on_search_focus)
        self.search_entry.bind("<FocusOut>", self._on_search_blur)
        self.search_entry.bind("<KeyRelease>", self._on_search)

        tk.Frame(self.func_panel, bg=COLORS["border"], height=1).pack(fill=tk.X)

        list_container = tk.Frame(self.func_panel, bg=COLORS["bg_card"])
        list_container.pack(fill=tk.BOTH, expand=True)
        self.list_canvas = tk.Canvas(list_container, bg=COLORS["bg_card"], bd=0, highlightthickness=0)
        list_scrollbar = ttk.Scrollbar(list_container, orient="vertical", command=self.list_canvas.yview)
        self.list_inner = tk.Frame(self.list_canvas, bg=COLORS["bg_card"])
        self.list_inner.bind("<Configure>", lambda e: self.list_canvas.configure(scrollregion=self.list_canvas.bbox("all")))
        self.list_canvas.create_window((0, 0), window=self.list_inner, anchor="nw")
        self.list_canvas.configure(yscrollcommand=list_scrollbar.set)
        self.list_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        list_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        # 绑定鼠标滚轮
        self.list_canvas.bind("<MouseWheel>", lambda e: self._on_mousewheel(e, self.list_canvas))
        self.list_inner.bind("<MouseWheel>", lambda e: self._on_mousewheel(e, self.list_canvas))

        # v0.5.0 索引表（与 _build_sidebar 的 NAV_ITEMS 严格一一对应）
        #   0 主页  1 创造  2 工具  3 优化  4 存档  5 监控  6 内部  7 离线  8 设置
        self.func_data = {
            0: [("","游戏概览","查看游戏运行状态",False),("","快速操作","启动游戏/注入DLL",True)],
            1: [("","鸿业满级","鸿业等级满级",False),("","全建筑解锁","解锁所有建筑",False),
                ("","无限资源","建造不消耗",False),("","无限制升级","升级无限制",False)],
            2: [("","时间控制","加速/季节/跳天",False),("","天气控制","固定天气",False),
                ("","NPC管理","谋士/居民",False),("","建造控制","建造/升级",False),
                ("","城市品阶","品阶提升",False),("","Steam成就","解锁成就",False),
                ("","地块解锁","解锁地块",False),("","天赋系统","天赋满级",False),
                ("","灾害控制","清除灾害",False),("","节日控制","节日管理",False),
                ("","核心数值","直接设置",False),("","一键全开","全部作弊",True)],
            3: [("","优化档位","保守/均衡/极致，改引擎出厂参数",False),
                ("","改动明细","当前值 vs 目标值对照",False),
                ("","系统侧优化","锁独显 / 关全屏优化",False),
                ("","还原","回滚到备份的原始配置",False)],
            4: [("","存档列表","查看存档",False),("","存档备份","备份存档",False),
                ("","存档恢复","恢复备份",False),("","清理备份","清理旧备份",False)],
            5: [("","进程监控","内存/CPU/状态",False)],
            6: [("","资源修改","0.3.1 首页改资源面板（复刻）",False)],
            7: [("","安装/卸载","部署或还原离线补丁",True),
                ("","状态总览","查 dll / lua / 登录状态",False),
                ("","启动游戏","离线拉起（不走 Steam）",False),
                ("","原理说明","两层方案与排错",False)],
            8: [("","热键设置","全局热键",False),("","日志管理","日志路径",False),
                ("","MOD管理","散文件MOD",False),("","关于","版本信息",False)],
        }

    def _on_search_focus(self, event):
        if self.search_entry.get() == "🔍 搜索功能...":
            self.search_entry.delete(0, tk.END)
            self.search_entry.config(fg=COLORS["fg"])

    def _on_search_blur(self, event):
        if not self.search_entry.get():
            self.search_entry.insert(0, "🔍 搜索功能...")
            self.search_entry.config(fg=COLORS["fg_muted"])
            self._switch_nav(self.current_nav)

    def _on_search(self, event):
        keyword = self.search_entry.get().strip().lower()
        if not keyword or keyword == "🔍 搜索功能...":
            self._switch_nav(self.current_nav)
            return

        # 跨所有分类搜索
        all_results = []
        for nav_idx, items in self.func_data.items():
            for func_idx, (icon, name, desc, dot) in enumerate(items):
                if keyword in name.lower() or keyword in desc.lower():
                    all_results.append((nav_idx, func_idx, icon, name, desc, dot))

        # 清空列表
        for w in self.list_inner.winfo_children():
            w.destroy()
        self.func_items = []

        if not all_results:
            tk.Label(self.list_inner, text=f"未找到「{keyword}」相关功能",
                    font=(FONT, 11), bg=COLORS["bg_card"], fg=COLORS["fg_muted"],
                    anchor="w").pack(fill=tk.X, padx=16, pady=20)
            return

        # 显示搜索结果（带分类标签）
        current_nav = -1
        for i, (nav_idx, func_idx, icon, name, desc, dot) in enumerate(all_results):
            if nav_idx != current_nav:
                current_nav = nav_idx
                nav_names = ["主页", "创造", "工具", "优化", "存档", "监控", "内部", "离线", "设置"]
                tk.Label(self.list_inner, text=f"── {nav_names[nav_idx]} ──",
                        font=(FONT, 9), bg=COLORS["bg_card"], fg=COLORS["fg_muted"],
                        anchor="w").pack(fill=tk.X, padx=12, pady=(8, 2))
            self._create_func_item(i, icon, name, desc, dot, search_result=True,
                                   nav_idx=nav_idx, func_idx=func_idx)

    def _switch_nav(self, index):
        self.current_nav = index
        for i, btn in enumerate(self.nav_buttons):
            btn.config(bg=COLORS["bg_sidebar_sel"] if i == index else COLORS["bg_sidebar"],
                      fg=COLORS["fg_sidebar_sel"] if i == index else COLORS["fg_sidebar"])
        for w in self.list_inner.winfo_children():
            w.destroy()
        self.func_items = []
        items = self.func_data.get(index, [])
        for i, (icon, name, desc, dot) in enumerate(items):
            self._create_func_item(i, icon, name, desc, dot)
        if items:
            self._switch_func(0)

    def _create_func_item(self, index, icon, name, desc, has_dot, search_result=False, nav_idx=None, func_idx=None):
        frame = tk.Frame(self.list_inner, bg=COLORS["bg_card"], cursor="hand2")
        frame.pack(fill=tk.X, padx=4, pady=1)
        icon_l = tk.Label(frame, text="", font=(FONT, 16), bg=COLORS["bg_card"], fg=COLORS["fg"])
        icon_l.pack(side=tk.LEFT, padx=(8, 6), pady=8)
        text_f = tk.Frame(frame, bg=COLORS["bg_card"])
        text_f.pack(side=tk.LEFT, fill=tk.X, expand=True)
        name_l = tk.Label(text_f, text=name, font=(FONT, 12, "bold"), bg=COLORS["bg_card"], fg=COLORS["fg"], anchor="w")
        name_l.pack(fill=tk.X)
        desc_l = tk.Label(text_f, text=desc, font=(FONT, 10), bg=COLORS["bg_card"], fg=COLORS["fg_muted"], anchor="w")
        desc_l.pack(fill=tk.X)
        dot_l = tk.Label(frame, text="●", font=(FONT, 8), bg=COLORS["bg_card"], fg=COLORS["error"]) if has_dot else None
        if dot_l: dot_l.pack(side=tk.RIGHT, padx=8, pady=8)
        item = {"frame": frame, "icon": icon_l, "name": name_l, "desc": desc_l, "text_frame": text_f, "dot": dot_l}
        self.func_items.append(item)

        # 点击处理：搜索结果需要切换到对应导航和功能
        if search_result and nav_idx is not None and func_idx is not None:
            for w in [frame, icon_l, name_l, desc_l, text_f]:
                w.bind("<Button-1>", lambda e, ni=nav_idx, fi=func_idx: self._jump_to_func(ni, fi))
                w.bind("<Enter>", lambda e, d=item: self._hover(d, True))
                w.bind("<Leave>", lambda e, d=item: self._hover(d, False))
        else:
            for w in [frame, icon_l, name_l, desc_l, text_f]:
                w.bind("<Button-1>", lambda e, idx=index: self._switch_func(idx))
                w.bind("<Enter>", lambda e, d=item: self._hover(d, True))
                w.bind("<Leave>", lambda e, d=item: self._hover(d, False))

    def _jump_to_func(self, nav_idx, func_idx):
        """从搜索结果跳转到指定功能"""
        self.search_entry.delete(0, tk.END)
        self.search_entry.insert(0, "🔍 搜索功能...")
        self.search_entry.config(fg=COLORS["fg_muted"])
        self._switch_nav(nav_idx)
        self._switch_func(func_idx)

    def _hover(self, item, hovering):
        bg = COLORS["bg_hover"] if hovering else COLORS["bg_card"]
        for k in ["frame", "icon", "name", "desc", "text_frame"]:
            item[k].config(bg=bg)
        if item["dot"]: item["dot"].config(bg=bg)

    def _switch_func(self, index):
        self.current_func = index
        for i, item in enumerate(self.func_items):
            bg = COLORS["bg_selected"] if i == index else COLORS["bg_card"]
            fg = COLORS["accent"] if i == index else COLORS["fg"]
            item["frame"].config(bg=bg)
            item["icon"].config(bg=bg)
            item["name"].config(bg=bg, fg=fg)
            item["desc"].config(bg=bg)
            item["text_frame"].config(bg=bg)
            if item["dot"]: item["dot"].config(bg=bg)
        items = self.func_data.get(self.current_nav, [])
        if index < len(items):
            icon, name, desc, _ = items[index]
            self.title_label.config(text=f"{icon} {name}")
            self._update_action_panel(self.current_nav, index, name)

    # ===== 右侧操作面板 =====
    def _build_action_panel(self, parent):
        self.action_panel = tk.Frame(parent, bg=COLORS["bg"])
        self.action_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        title_bar = tk.Frame(self.action_panel, bg=COLORS["bg_card"], height=56)
        title_bar.pack(fill=tk.X)
        title_bar.pack_propagate(False)
        self.title_label = tk.Label(title_bar, text="🏠 游戏概览", font=(FONT, 16, "bold"),
                                   bg=COLORS["bg_card"], fg=COLORS["fg"])
        self.title_label.pack(side=tk.LEFT, padx=24)
        right_f = tk.Frame(title_bar, bg=COLORS["bg_card"])
        right_f.pack(side=tk.RIGHT, padx=20)
        self.status_dot = tk.Label(right_f, text="●", font=(FONT, 14), bg=COLORS["bg_card"], fg=COLORS["error"])
        self.status_dot.pack(side=tk.LEFT, padx=(0, 6))
        self.title_desc = tk.Label(right_f, text="未检测到游戏", font=(FONT, 11),
                                  bg=COLORS["bg_card"], fg=COLORS["fg_muted"])
        self.title_desc.pack(side=tk.LEFT)

        tk.Frame(self.action_panel, bg=COLORS["border"], height=1).pack(fill=tk.X)

        content_container = tk.Frame(self.action_panel, bg=COLORS["bg"])
        content_container.pack(fill=tk.BOTH, expand=True)
        self.content_canvas = tk.Canvas(content_container, bg=COLORS["bg"], bd=0, highlightthickness=0)
        content_scrollbar = ttk.Scrollbar(content_container, orient="vertical", command=self.content_canvas.yview)
        self.content_inner = tk.Frame(self.content_canvas, bg=COLORS["bg"])
        self.content_inner.bind("<Configure>", lambda e: self.content_canvas.configure(scrollregion=self.content_canvas.bbox("all")))
        self.content_canvas.create_window((0, 0), window=self.content_inner, anchor="nw")
        self.content_canvas.configure(yscrollcommand=content_scrollbar.set)
        self.content_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        content_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        # 绑定鼠标滚轮
        self.content_canvas.bind("<MouseWheel>", lambda e: self._on_mousewheel(e, self.content_canvas))
        self.content_inner.bind("<MouseWheel>", lambda e: self._on_mousewheel(e, self.content_canvas))

        log_panel = tk.Frame(self.action_panel, bg=COLORS["bg_card"])
        log_panel.pack(fill=tk.X, side=tk.BOTTOM)
        log_header = tk.Frame(log_panel, bg=COLORS["bg_card"])
        log_header.pack(fill=tk.X, padx=16, pady=(8, 4))
        tk.Label(log_header, text="📋 操作日志", font=(FONT, 11, "bold"),
                bg=COLORS["bg_card"], fg=COLORS["fg"]).pack(side=tk.LEFT)
        # 撤销/重做按钮（v0.4.6 新增）
        undo_frame = tk.Frame(log_header, bg=COLORS["bg_card"])
        undo_frame.pack(side=tk.RIGHT, padx=8)
        self.undo_btn = tk.Button(undo_frame, text="↶ 撤销", font=(FONT, 10), bg=COLORS["bg_card"], fg=COLORS["fg_muted"],
                                  bd=0, relief=tk.FLAT, cursor="hand2", activebackground=COLORS["bg_hover"],
                                  command=self._on_undo)
        self.undo_btn.pack(side=tk.LEFT, padx=4)
        self.redo_btn = tk.Button(undo_frame, text="↷ 重做", font=(FONT, 10), bg=COLORS["bg_card"], fg=COLORS["fg_muted"],
                                  bd=0, relief=tk.FLAT, cursor="hand2", activebackground=COLORS["bg_hover"],
                                  command=self._on_redo)
        self.redo_btn.pack(side=tk.LEFT, padx=4)
        tk.Button(log_header, text="清空", font=(FONT, 10), bg=COLORS["bg_card"], fg=COLORS["fg_muted"],
                 bd=0, relief=tk.FLAT, cursor="hand2", activebackground=COLORS["bg_hover"],
                 command=self._clear_log).pack(side=tk.RIGHT)
        tk.Frame(log_panel, bg=COLORS["border"], height=1).pack(fill=tk.X)
        self.log_text = scrolledtext.ScrolledText(log_panel, height=6, bg="#fafafa", fg=COLORS["fg"],
                                                  font=("Consolas", 10), bd=0, relief=tk.FLAT)
        self.log_text.pack(fill=tk.X, padx=10, pady=5)
        self.log_text.config(state=tk.DISABLED)

    def _clear_log(self):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.config(state=tk.DISABLED)

    def _on_undo(self):
        """撤销上一次操作"""
        history = get_operation_history()
        if history.can_undo():
            success, msg = history.undo()
            if success:
                log_info(f"已撤销: {msg}")
            else:
                log_warning(f"撤销失败: {msg}")
        else:
            log_warning("没有可撤销的操作")
        self._update_undo_redo_buttons()

    def _on_redo(self):
        """重做上一次撤销的操作"""
        history = get_operation_history()
        if history.can_redo():
            success, msg = history.redo()
            if success:
                log_info(f"已重做: {msg}")
            else:
                log_warning(f"重做失败: {msg}")
        else:
            log_warning("没有可重做的操作")
        self._update_undo_redo_buttons()

    def _update_undo_redo_buttons(self):
        """更新撤销/重做按钮状态"""
        try:
            history = get_operation_history()
            if hasattr(self, 'undo_btn'):
                self.undo_btn.config(fg=COLORS["accent"] if history.can_undo() else COLORS["fg_muted"])
            if hasattr(self, 'redo_btn'):
                self.redo_btn.config(fg=COLORS["accent"] if history.can_redo() else COLORS["fg_muted"])
        except Exception:
            pass

    def _update_action_panel(self, nav, func, name):
        self._monitor_running = False
        for w in self.content_inner.winfo_children():
            w.destroy()
        # v0.5.0：顺序与 NAV_ITEMS / func_data 一致（修掉 0.4.9 优化↔存档错位）
        if nav == 0: self._build_home()
        elif nav == 1: self._build_creative()
        elif nav == 2: self._build_tools(func)
        elif nav == 3: self._build_perf_tools(func)
        elif nav == 4: self._build_save(func)
        elif nav == 5: self._build_monitor()
        elif nav == 6: self._build_internal(func)
        elif nav == 7: self._build_offline_tools(func)
        elif nav == 8: self._build_settings(func)
        self._bind_mousewheel(self.content_inner, self.content_canvas)
        self._bind_mousewheel(self.content_inner, self.content_canvas)

    def _build_home(self):
        cards_f = tk.Frame(self.content_inner, bg=COLORS["bg"])
        cards_f.pack(fill=tk.X, padx=20, pady=16)
        self.home_card_labels = []
        for title, val, color in [("游戏状态","检测中...",COLORS["fg_muted"]),("DLL状态","检测中...",COLORS["fg_muted"]),("Lua通道","未连接",COLORS["fg_muted"])]:
            card = tk.Frame(cards_f, bg=COLORS["bg_card"], highlightbackground=COLORS["border"], highlightthickness=1)
            card.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
            card.pack_propagate(False)
            card.config(height=90)
            tk.Label(card, text=title, font=(FONT, 11), bg=COLORS["bg_card"], fg=COLORS["fg_muted"], anchor="w").pack(fill=tk.X, padx=12, pady=(12, 4))
            l = tk.Label(card, text=val, font=(FONT, 16, "bold"), bg=COLORS["bg_card"], fg=color, anchor="w")
            l.pack(fill=tk.X, padx=12)
            self.home_card_labels.append(l)
        g = self._group("🚀 快速操作")
        bf = tk.Frame(g, bg=COLORS["bg_card"])
        bf.pack(fill=tk.X, padx=16, pady=12)
        self._btn(bf, "启动游戏", "primary", self._on_launch).pack(side=tk.LEFT, padx=5)
        self._btn(bf, "注入DLL", "primary", self._on_inject).pack(side=tk.LEFT, padx=5)
        self._btn(bf, "检测进程", "normal", self._on_detect).pack(side=tk.LEFT, padx=5)

        # ===== 完整进程监控（从监控页搬来）=====
        g = self._group("📊 进程监控")
        cards_f = tk.Frame(g, bg=COLORS["bg_card"])
        cards_f.pack(fill=tk.X, padx=16, pady=(0, 10))
        self.mon_cards = {}
        for title, key in [
            ("🎮 进程 PID", "mon_pid"),
            ("💾 内存占用", "mon_mem"),
            ("🔥 CPU", "mon_cpu"),
            ("🔌 DLL", "mon_dll"),
            ("🏙️ 品阶", "mon_rank"),
            ("⏰ 时间", "mon_time"),
        ]:
            card = tk.Frame(cards_f, bg=COLORS["bg_card"],
                           highlightbackground=COLORS["border"], highlightthickness=1)
            card.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
            tk.Label(card, text=title, font=(FONT, 10), bg=COLORS["bg_card"],
                    fg=COLORS["fg_muted"], anchor="w").pack(fill=tk.X, padx=10, pady=(8, 2))
            l = tk.Label(card, text="--", font=(FONT, 14, "bold"), bg=COLORS["bg_card"],
                        fg=COLORS["fg"], anchor="w")
            l.pack(fill=tk.X, padx=10, pady=(0, 8))
            self.mon_cards[key] = l

        g2 = self._group("💾 内存历史（近30秒）")
        self.mem_canvas = tk.Canvas(g2, height=120, bg=COLORS["bg_card"],
                                    highlightbackground=COLORS["border"], highlightthickness=1)
        self.mem_canvas.pack(fill=tk.X, padx=16, pady=8)
        self.mem_history = []

        g3 = self._group("🎮 游戏状态")
        self.mon_game_text = tk.Text(g3, font=("Consolas", 11), bg=COLORS["bg_card"],
                                    fg=COLORS["fg"], relief=tk.FLAT, wrap=tk.WORD, height=8)
        self.mon_game_text.pack(fill=tk.X, padx=16, pady=8)
        self.mon_game_text.config(state=tk.DISABLED)

        # 一键诊断
        diag_f = tk.Frame(g, bg=COLORS["bg_card"])
        diag_f.pack(fill=tk.X, padx=16, pady=(0, 10))
        self._btn(diag_f, "🔍 一键系统诊断", "primary", self._run_full_diagnosis).pack(side=tk.LEFT, padx=5)
        self._btn(diag_f, "📋 导出诊断报告", "normal", self._export_diagnosis_report).pack(side=tk.LEFT, padx=5)

        self._monitor_running = True
        self._refresh_monitor()

    def _run_full_diagnosis(self):
        """运行完整系统诊断，结果输出到日志"""
        from src.diagnostic import run_full_diagnosis
        dll_path = get_dll_path()
        report = run_full_diagnosis(
            game_pid=self.game_pid,
            dll_path=dll_path,
            config=self.config
        )
        log_info("=== 系统诊断报告 ===")
        for line in report.split("\n"):
            log_info(line)
        messagebox.showinfo("诊断完成", "系统诊断已完成，结果请查看日志面板。")

    def _export_diagnosis_report(self):
        """导出诊断报告到文件"""
        from src.diagnostic import run_full_diagnosis, export_diagnosis_report
        from tkinter import filedialog
        dll_path = get_dll_path()
        report = run_full_diagnosis(
            game_pid=self.game_pid,
            dll_path=dll_path,
            config=self.config
        )
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")],
            initialfile="woldvein_diagnosis.txt"
        )
        if path:
            success, msg = export_diagnosis_report(report, path)
            if success:
                messagebox.showinfo("导出成功", f"诊断报告已导出到:\n{path}")
            else:
                messagebox.showerror("导出失败", msg)
        g2 = self._group("📋 进程信息")
        self.process_info = tk.Label(g2, text="点击「检测进程」查看...", font=(FONT, 11),
                                    bg=COLORS["bg_card"], fg=COLORS["fg_muted"], justify=tk.LEFT, anchor="w")
        self.process_info.pack(fill=tk.X, anchor=tk.W, padx=16, pady=12)

    # ===== 进程页 =====
    def _build_process(self):
        g = self._group("🎮 进程操作")
        bf = tk.Frame(g, bg=COLORS["bg_card"])
        bf.pack(fill=tk.X, padx=16, pady=12)
        self._btn(bf, "🔍 检测游戏进程", "normal", self._on_detect).pack(side=tk.LEFT, padx=5)
        self._btn(bf, "🚀 启动游戏", "primary", self._on_launch).pack(side=tk.LEFT, padx=5)
        self._btn(bf, "🔌 注入DLL", "primary", self._on_inject).pack(side=tk.LEFT, padx=5)
        g2 = self._group("📋 进程信息")
        self.process_info = tk.Label(g2, text="点击「检测游戏进程」查看...", font=(FONT, 12),
                                    bg=COLORS["bg_card"], fg=COLORS["fg_muted"], justify=tk.LEFT, anchor="w")
        self.process_info.pack(fill=tk.X, anchor=tk.W, padx=16, pady=16)

    def _on_detect(self):
        log_info("正在检测游戏进程...")
        result = find_game_process()
        self.game_pid = result[0] if (result and isinstance(result, tuple) and result[0]) else (result if not isinstance(result, tuple) else None)
        if self.game_pid:
            log_success(f"检测到游戏进程: PID={self.game_pid}")
            if hasattr(self, 'process_info'):
                try:
                    if self.process_info.winfo_exists():
                        self.process_info.config(text=f"游戏进程: PID={self.game_pid}\n\nDLL: {'已注入' if self.dll_injected else '未注入'}", fg=COLORS["fg"])
                except:
                    pass
        else:
            log_warning("未检测到游戏进程")
            if hasattr(self, 'process_info'):
                try:
                    if self.process_info.winfo_exists():
                        self.process_info.config(text="未检测到游戏进程\n\n请先启动游戏", fg=COLORS["error"])
                except:
                    pass
        self._refresh_status_display()

    def _on_launch(self):
        log_info("正在启动游戏...")
        try:
            launch_game()
            log_success("已请求启动游戏 (steam://run/2656540)")
        except Exception as e:
            log_error(f"启动失败: {e}")

    def _install_save_fix(self):
        """自动安装存档卡3/4修复补丁（散文件）"""
        try:
            from src.config import load_config
            config = load_config()
            game_path = config.get("game_path", r"D:\steam\steamapps\common\BalladsOfHongye_CN")

            # 补丁源文件（修改器自带）
            patch_src = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "assets", "save_fix", "sim_common", "script", "core", "archive", "archive_mgr.lua"
            )
            # 补丁目标位置（游戏目录）
            patch_dst_dir = os.path.join(game_path, "sim_common", "script", "core", "archive")
            patch_dst = os.path.join(patch_dst_dir, "archive_mgr.lua")

            if not os.path.exists(patch_src):
                return False

            # 已安装则跳过
            if os.path.exists(patch_dst):
                return True

            # 安装
            os.makedirs(patch_dst_dir, exist_ok=True)
            import shutil
            shutil.copy2(patch_src, patch_dst)
            log_info("[存档修复] 补丁已自动安装到游戏目录")
            return True
        except Exception as e:
            log_warning(f"[存档修复] 自动安装失败: {e}")
            return False

    def _on_inject(self):
        # 注入前自动安装存档修复补丁
        self._install_save_fix()
        if not self.game_pid:
            self._on_detect()
            if not self.game_pid:
                log_error("未检测到游戏进程")
                return
        if not os.path.exists(DLL_PATH):
            log_error(f"DLL不存在: {DLL_PATH}")
            return
        log_info(f"正在注入DLL到 PID={self.game_pid}...")
        try:
            if inject_dll(self.game_pid, DLL_PATH):
                log_success("DLL注入成功")
                self.dll_injected = True
                try:
                    get_status_provider().set_dll_ready(True)
                except Exception:
                    pass
            else:
                log_error("DLL注入失败")
        except Exception as e:
            log_error(f"注入异常: {e}")
        self._refresh_status_display()

    # ===== 资源页 =====
    def _build_resource(self, func):
        g = self._group("⚡ 快捷操作")
        bf = tk.Frame(g, bg=COLORS["bg_card"])
        bf.pack(fill=tk.X, padx=16, pady=12)
        self._btn(bf, "📦 一键全部资源 +100万", "primary", lambda: self._run_async(add_all_resources) if self._check_dll() else None).pack(side=tk.LEFT, padx=5)
        self._btn(bf, "🗑️ 资源归零", "danger", self._on_zero_res).pack(side=tk.LEFT, padx=5)

        g2 = self._group("💰 资源修改")
        self.resource_entries = {}
        for res in RESOURCES:
            if res["id"] == 7: continue
            self._res_row(g2, res)

        g3 = self._group("✨ 特殊属性")
        bf3 = tk.Frame(g3, bg=COLORS["bg_card"])
        bf3.pack(fill=tk.X, padx=16, pady=12)
        self._btn(bf3, "😊 幸福度最大", "normal", lambda: self._run_async(max_happiness) if self._check_dll() else None).pack(side=tk.LEFT, padx=5)
        self._btn(bf3, "⭐ 知名度 +10000", "normal", lambda: self._run_async(add_fame) if self._check_dll() else None).pack(side=tk.LEFT, padx=5)
        self._btn(bf3, "↩ 恢复幸福度", "normal", lambda: self._run_async(restore_happiness) if self._check_dll() else None).pack(side=tk.LEFT, padx=5)

    def _res_row(self, parent, res):
        row = tk.Frame(parent, bg=COLORS["bg_card"])
        row.pack(fill=tk.X, padx=12, pady=3)
        tk.Label(row, text=res.get("icon","📦"), font=(FONT, 14), bg=COLORS["bg_card"], fg=COLORS["fg"], width=3).pack(side=tk.LEFT)
        tk.Label(row, text=res["name"], font=(FONT, 12), bg=COLORS["bg_card"], fg=COLORS["fg"], width=8, anchor="w").pack(side=tk.LEFT)
        entry = tk.Entry(row, font=(FONT, 11), width=10, justify=tk.CENTER, bd=1, relief=tk.SOLID)
        entry.insert(0, "1000000")
        entry.pack(side=tk.LEFT, padx=8)
        self.resource_entries[res["id"]] = entry
        self._btn(row, "+增加", "primary", lambda rid=res["id"]: self._add_res(rid)).pack(side=tk.LEFT, padx=5)

    def _add_res(self, rid):
        if not self._check_dll(): return
        from src.input_validator import validate_resource_amount
        amount, ok, msg = validate_resource_amount(self.resource_entries[rid].get())
        if not ok:
            messagebox.showwarning("输入无效", msg)
            return
        self._run_async(add_resource, rid, amount)


    def _confirm_dangerous(self, title, message, action_func):
        """高危操作二次确认。确认后执行 action_func，取消则不执行。"""
        if messagebox.askyesno(title, message):
            action_func()
        else:
            log_warning(f"[高危操作] 用户取消: {title}")

    def _on_zero_res(self):
        if not self._check_dll(): return
        if messagebox.askyesno("确认", "确定要将所有资源归零吗？"):
            self._run_async(zero_all_resources)

    # ===== 内部页：0.3.1 首页改资源面板复刻 =====
    def _build_internal(self, func):
        """内部页 - 复刻自 0.3.1 的首页改资源面板（资源表格+实时数值+特殊属性）"""
        desc = tk.Label(self.content_inner, text="点击按钮增加对应资源（默认+100万），需先进入游戏场景并注入DLL",
                        font=(FONT, 11), bg=COLORS["bg"], fg=COLORS["warning"], anchor="w", justify=tk.LEFT)
        desc.pack(fill=tk.X, padx=20, pady=(14, 8))

        # 快捷操作
        g = self._group("⚡ 快捷操作")
        bf = tk.Frame(g, bg=COLORS["bg_card"])
        bf.pack(fill=tk.X, padx=16, pady=12)
        self._btn(bf, "🌟 满天赋", "primary",
                  lambda: self._run_async(advanced_tools.max_all_talents) if self._check_dll() else None).pack(side=tk.LEFT, padx=5)
        self._btn(bf, "↩ 资源归零", "danger", self._on_zero_res).pack(side=tk.LEFT, padx=5)
        self._btn(bf, "一键全部资源 +100万", "primary",
                  lambda: self._run_async(add_all_resources) if self._check_dll() else None).pack(side=tk.LEFT, padx=5)

        # 当前时间流速
        g2 = self._group("⏱ 当前时间流速")
        speed_f = tk.Frame(g2, bg=COLORS["bg_card"])
        speed_f.pack(fill=tk.X, padx=16, pady=10)
        self.res_speed_label = tk.Label(speed_f, text="1x", font=(FONT, 14, "bold"),
                                        bg=COLORS["bg_card"], fg=COLORS["success"])
        self.res_speed_label.pack(side=tk.LEFT)
        tk.Label(speed_f, text="（暂停时显示 0x）", font=(FONT, 10),
                 bg=COLORS["bg_card"], fg=COLORS["fg_muted"]).pack(side=tk.LEFT, padx=10)

        # 资源表格
        g3 = self._group("💰 资源修改")
        header = tk.Frame(g3, bg=COLORS["bg_card"])
        header.pack(fill=tk.X, padx=16, pady=(10, 4))
        for htext, hw, hanchor in [("资源", 10, tk.W), ("当前数量", 18, tk.E), ("修改数值", 12, tk.W), ("操作", 22, tk.W)]:
            tk.Label(header, text=htext, font=(FONT, 11, "bold"), bg=COLORS["bg_card"],
                     fg=COLORS["accent"], width=hw, anchor=hanchor).pack(side=tk.LEFT, padx=(4, 6))
        tk.Frame(g3, bg=COLORS["border"], height=1).pack(fill=tk.X, padx=16)

        self.resource_value_labels = {}
        self.internal_res_entries = {}
        for i, res in enumerate(RESOURCES):
            self._internal_res_row(g3, res, i)

        # 特殊属性
        g4 = self._group("✨ 特殊属性")
        bf4 = tk.Frame(g4, bg=COLORS["bg_card"])
        bf4.pack(fill=tk.X, padx=16, pady=12)
        self._btn(bf4, "😊 幸福度最大", "normal",
                  lambda: self._run_async(max_happiness) if self._check_dll() else None).pack(side=tk.LEFT, padx=5)
        self._btn(bf4, "⭐ 知名度 +1万", "normal",
                  lambda: self._run_async(add_fame, FAME_ADD_AMOUNT) if self._check_dll() else None).pack(side=tk.LEFT, padx=5)
        self._btn(bf4, "↩ 恢复幸福度", "normal",
                  lambda: self._run_async(restore_happiness) if self._check_dll() else None).pack(side=tk.LEFT, padx=5)

        # 订阅游戏状态实时刷新（0.3.1 同款 GameStatusProvider）
        try:
            self._internal_status_provider = get_status_provider()
            self._internal_status_provider.set_dll_ready(bool(self.dll_injected))
            self._internal_status_provider.subscribe("internal_resource", self._on_internal_status_update)
        except Exception as e:
            log_warning(f"内部页状态订阅失败: {e}")

    def _internal_res_row(self, parent, res, idx):
        """资源行：图标+名称 | 当前值 | 自定义数量输入 | +100万 / 增加"""
        bg = COLORS["bg_hover"] if idx % 2 == 1 else COLORS["bg_card"]
        row = tk.Frame(parent, bg=bg)
        row.pack(fill=tk.X, padx=16, pady=1)
        tk.Label(row, text=f"  {res['icon']} {res['name']}", bg=bg, fg=COLORS["fg"],
                 font=(FONT, 12), width=10, anchor=tk.W).pack(side=tk.LEFT, padx=(4, 0), pady=4)
        value_label = tk.Label(row, text="——", bg=bg, fg=COLORS["success"],
                               font=("Consolas", 12, "bold"), width=18, anchor=tk.E)
        value_label.pack(side=tk.LEFT, padx=(8, 0), pady=4)
        self.resource_value_labels[res["id"]] = value_label
        var = tk.StringVar(value=str(RESOURCE_ADD_AMOUNT))
        entry = tk.Entry(row, textvariable=var, width=10, justify=tk.CENTER, font=("Consolas", 11),
                         bd=1, relief=tk.SOLID, bg=COLORS["bg"], fg=COLORS["fg"], insertbackground=COLORS["fg"])
        entry.pack(side=tk.LEFT, padx=(12, 4), pady=4)
        self.internal_res_entries[res["id"]] = (entry, var)
        self._btn(row, "+100万", "primary",
                  lambda rid=res["id"]: self._add_res_internal(rid, RESOURCE_ADD_AMOUNT)).pack(side=tk.LEFT, padx=2)
        self._btn(row, "增加", "normal",
                  lambda rid=res["id"], v=var: self._add_res_internal(rid, v.get())).pack(side=tk.LEFT, padx=2)

    def _add_res_internal(self, rid, amount):
        if not self._check_dll():
            return
        from src.input_validator import validate_resource_amount
        parsed, ok, msg = validate_resource_amount(amount)
        if not ok:
            messagebox.showwarning("输入无效", msg)
            return
        self._run_async(add_resource, rid, parsed)

    def _on_internal_status_update(self, status, success):
        """GameStatusProvider 回调（后台线程）→ 切主线程更新 UI"""
        try:
            if self.content_inner.winfo_exists():
                self.root.after(0, lambda: self._update_internal_display(status, success))
        except Exception:
            pass

    def _update_internal_display(self, status, success):
        """主线程更新资源当前值 / 时间流速"""
        try:
            if hasattr(self, "res_speed_label") and self.res_speed_label.winfo_exists():
                speed = status.get("speed_mult", 1) if status else getattr(self, "_current_time_speed", 1)
                speed_map = {0: "0x（暂停）", 1: "1x", 2: "2x", 3: "3x", 4: "4x"}
                text = speed_map.get(speed, f"{speed}x")
                fg = COLORS["error"] if speed == 0 else COLORS["success"]
                self.res_speed_label.config(text=text, fg=fg)
        except Exception:
            pass

        labels = getattr(self, "resource_value_labels", None)
        if not labels:
            return
        if success and status:
            id_to_field = get_id_to_field()
            for res_id, label in list(labels.items()):
                try:
                    if not label.winfo_exists():
                        continue
                    field = id_to_field.get(res_id)
                    if field and field in status:
                        val = status[field]
                        text = f"{val:,.0f}" if isinstance(val, (int, float)) and val >= 10000 else str(val)
                        label.config(text=text, fg=COLORS["success"])
                    else:
                        label.config(text="——", fg=COLORS["accent"])
                except Exception:
                    pass
        else:
            for label in list(labels.values()):
                try:
                    if label.winfo_exists():
                        label.config(text="未进入场景", fg=COLORS["error"])
                except Exception:
                    pass

    # ===== 创造模式页 =====
    def _build_creative(self):
        g = self._group("✨ 创造模式选项")
        self.creative_vars = {}
        for key, text, desc in [("max_boom","🏆 鸿业满级","鸿业等级设为14级"),
                                 ("unlock_all_buildings","🏗️ 全建筑解锁","解锁所有建筑"),
                                 ("infinite_resources","♾️ 无限资源","建造不消耗资源"),
                                 ("unlimited_upgrade","⬆️ 无限制升级","升级无等级限制"),
                                 ("road_bypass","🛤️ 道路豁免","行人不必经过道路"),
                                 ("population_universal","👥 人口通用","工人/匠人/学者不分类"),
                                 ("gm_flags","⚡ GM模式","快速建造/忽略地块/全操作"),
                                 ("no_disaster_damage","🏛️ 建筑免灾","建筑不受灾害伤害"),
                                 ("no_disaster","🌤️ 无灾害","不触发任何灾害")]:
            var = tk.IntVar(value=1)
            self.creative_vars[key] = var
            row = tk.Frame(g, bg=COLORS["bg_card"])
            row.pack(fill=tk.X, padx=16, pady=4)
            tk.Checkbutton(row, text=f"{text}  -  {desc}", variable=var, font=(FONT, 12),
                          bg=COLORS["bg_card"], fg=COLORS["fg"], activebackground=COLORS["bg_card"],
                          selectcolor=COLORS["bg_card"]).pack(anchor=tk.W)
        sf = tk.Frame(g, bg=COLORS["bg_card"])
        sf.pack(fill=tk.X, padx=16, pady=8)
        self._btn(sf, "全选", "normal", lambda: [v.set(1) for v in self.creative_vars.values()]).pack(side=tk.LEFT, padx=5)
        self._btn(sf, "反选", "normal", lambda: [v.set(1-v.get()) for v in self.creative_vars.values()]).pack(side=tk.LEFT, padx=5)
        af = tk.Frame(self.content_inner, bg=COLORS["bg"])
        af.pack(fill=tk.X, padx=20, pady=12)
        self._btn(af, "开启创造模式", "primary", self._on_enable_creative).pack(side=tk.LEFT, padx=5)
        self._btn(af, "关闭创造模式", "danger", lambda: self._run_async(disable_creative_mode) if self._check_dll() else None).pack(side=tk.LEFT, padx=5)
        self._btn(af, "诊断解锁状态", "normal", lambda: self._run_async(diagnose_unlock_status) if self._check_dll() else None).pack(side=tk.LEFT, padx=5)

    def _on_enable_creative(self):
        if not self._check_dll(): return
        set_creative_options({k: bool(v.get()) for k, v in self.creative_vars.items()})
        self._run_async(enable_creative_mode)

    # ===== 高级工具页 =====
    def _build_tools(self, func):
        tool_map = {
            0: self._build_time_tools,
            1: self._build_weather_tools,
            2: self._build_npc_tools,
            3: self._build_building_tools,
            4: self._build_city_tools,
            5: self._build_achievement_tools,
            6: self._build_plot_tools,
            7: self._build_talent_tools,
            8: self._build_disaster_tools,
            9: self._build_festival_tools,
            10: self._build_core_tools,
            11: self._build_all_cheats,
        }
        builder = tool_map.get(func, self._build_placeholder)
        builder()

    def _build_time_tools(self):
        g = self._group("⏰ 时间控制")
        bf = tk.Frame(g, bg=COLORS["bg_card"])
        bf.pack(fill=tk.X, padx=16, pady=12)
        for speed, label in [(1, "1x"), (2, "2x"), (4, "4x"), (8, "8x")]:
            self._btn(bf, f"⏩ {label}加速", "normal", lambda s=speed: self._run_async(advanced_tools.set_time_speed, s) if self._check_dll() else None).pack(side=tk.LEFT, padx=3)
        self._btn(bf, "↩ 恢复速度", "normal", lambda: self._run_async(advanced_tools.restore_time_speed) if self._check_dll() else None).pack(side=tk.LEFT, padx=3)

        g2 = self._group("🌸 季节控制")
        bf2 = tk.Frame(g2, bg=COLORS["bg_card"])
        bf2.pack(fill=tk.X, padx=16, pady=12)
        for s in ["春", "夏", "秋", "冬"]:
            self._btn(bf2, s, "normal", lambda x=s: self._run_async(advanced_tools.set_season, x) if self._check_dll() else None).pack(side=tk.LEFT, padx=3)
        self._btn(bf2, "↩ 恢复季节", "normal", lambda: self._run_async(advanced_tools.restore_season) if self._check_dll() else None).pack(side=tk.LEFT, padx=3)

        g3 = self._group("📅 跳时")
        bf3 = tk.Frame(g3, bg=COLORS["bg_card"])
        bf3.pack(fill=tk.X, padx=16, pady=12)
        self._btn(bf3, "⏭ 跳过1天", "normal", lambda: self._run_async(advanced_tools.skip_days, 1) if self._check_dll() else None).pack(side=tk.LEFT, padx=3)
        self._btn(bf3, "⏭ 跳过10天", "normal", lambda: self._run_async(advanced_tools.skip_days, 10) if self._check_dll() else None).pack(side=tk.LEFT, padx=3)
        self._btn(bf3, "⏭ 跳过1月", "normal", lambda: self._run_async(advanced_tools.skip_months, 1) if self._check_dll() else None).pack(side=tk.LEFT, padx=3)
        self._btn(bf3, "🔍 诊断时间", "normal", lambda: self._run_async(advanced_tools.diagnose_time_system) if self._check_dll() else None).pack(side=tk.LEFT, padx=3)

    def _build_weather_tools(self):
        g = self._group("🌤️ 天气控制")
        bf = tk.Frame(g, bg=COLORS["bg_card"])
        bf.pack(fill=tk.X, padx=16, pady=12)
        self._btn(bf, "☀️ 固定晴天", "primary", lambda: self._run_async(cheat_tools.fix_weather, True) if self._check_dll() else None).pack(side=tk.LEFT, padx=5)
        self._btn(bf, "🌧️ 恢复天气", "normal", lambda: self._run_async(cheat_tools.fix_weather, False) if self._check_dll() else None).pack(side=tk.LEFT, padx=5)
        self._btn(bf, "🔍 天气诊断", "normal", lambda: self._run_async(cheat_tools.get_weather_info) if self._check_dll() else None).pack(side=tk.LEFT, padx=5)

    def _build_npc_tools(self):
        g = self._group("👤 NPC/谋士管理")
        bf = tk.Frame(g, bg=COLORS["bg_card"])
        bf.pack(fill=tk.X, padx=16, pady=12)
        self._btn(bf, "🔍 探查NPC", "normal", lambda: self._run_async(advanced_tools.get_npc_list) if self._check_dll() else None).pack(side=tk.LEFT, padx=5)
        self._btn(bf, "⬆️ 谋士升满级", "primary", lambda: self._run_async(advanced_tools.max_all_advisors) if self._check_dll() else None).pack(side=tk.LEFT, padx=5)
        self._btn(bf, "🔍 探查谋士", "normal", lambda: self._run_async(advanced_tools.probe_advisors) if self._check_dll() else None).pack(side=tk.LEFT, padx=5)
        self._btn(bf, "👥 人口满员", "primary", lambda: self._run_async(world_tools.full_population_all) if self._check_dll() else None).pack(side=tk.LEFT, padx=5)

    def _build_building_tools(self):
        g = self._group("🏠 建造控制")
        bf = tk.Frame(g, bg=COLORS["bg_card"])
        bf.pack(fill=tk.X, padx=16, pady=12)
        self._btn(bf, "🔍 建筑列表", "normal", lambda: self._run_async(advanced_tools.get_building_list) if self._check_dll() else None).pack(side=tk.LEFT, padx=5)
        self._btn(bf, "⬆️ 全部升级", "primary", lambda: self._confirm_dangerous("全部升级", "确定要将所有建筑升级到顶级吗？", lambda: self._run_async(advanced_tools.upgrade_all_buildings)) if self._check_dll() else None).pack(side=tk.LEFT, padx=5)
        self._btn(bf, "✅ 全部完工", "primary", lambda: self._confirm_dangerous("全部完工", "确定要立即完成所有在建建筑吗？", lambda: self._run_async(advanced_tools.finish_all_buildings)) if self._check_dll() else None).pack(side=tk.LEFT, padx=5)
        self._btn(bf, "🏆 升级到顶级", "primary", lambda: self._run_async(world_tools.upgrade_all_to_top) if self._check_dll() else None).pack(side=tk.LEFT, padx=5)

    def _build_city_tools(self):
        g = self._group("🏙️ 城市品阶")
        bf = tk.Frame(g, bg=COLORS["bg_card"])
        bf.pack(fill=tk.X, padx=16, pady=12)
        self._btn(bf, "⬆️ 品阶+1", "normal", lambda: self._run_async(advanced_tools.boom_level_up) if self._check_dll() else None).pack(side=tk.LEFT, padx=5)
        self._btn(bf, "🏆 品阶满级", "primary", lambda: self._run_async(advanced_tools.boom_upgrade_to_max) if self._check_dll() else None).pack(side=tk.LEFT, padx=5)
        self._btn(bf, "✅ 完成条件", "normal", lambda: self._run_async(advanced_tools.complete_city_rank_conditions) if self._check_dll() else None).pack(side=tk.LEFT, padx=5)
        self._btn(bf, "🔍 品阶诊断", "normal", lambda: self._run_async(advanced_tools.diagnose_boom) if self._check_dll() else None).pack(side=tk.LEFT, padx=5)
        self._btn(bf, "🌆 城市全发展", "primary", lambda: self._run_async(cheat_tools.grow_all_cities) if self._check_dll() else None).pack(side=tk.LEFT, padx=5)

    def _build_achievement_tools(self):
        g = self._group("🎖️ Steam成就")
        bf = tk.Frame(g, bg=COLORS["bg_card"])
        bf.pack(fill=tk.X, padx=16, pady=12)
        self._btn(bf, "🏆 解锁全部成就", "primary", lambda: self._confirm_dangerous("解锁全部成就", "确定要解锁所有Steam成就吗？\n\n此操作可能影响成就获取体验。", lambda: self._run_async(advanced_tools.unlock_all_steam_achievements)) if self._check_dll() else None).pack(side=tk.LEFT, padx=5)
        self._btn(bf, "🏆 解锁地块挑战", "primary", lambda: self._run_async(advanced_tools.unlock_block_challenge_achievements) if self._check_dll() else None).pack(side=tk.LEFT, padx=5)
        self._btn(bf, "🔍 探查成就", "normal", lambda: self._run_async(advanced_tools.probe_steam_achievements) if self._check_dll() else None).pack(side=tk.LEFT, padx=5)

    def _build_plot_tools(self):
        g = self._group("🌾 地块解锁")
        bf = tk.Frame(g, bg=COLORS["bg_card"])
        bf.pack(fill=tk.X, padx=16, pady=12)
        self._btn(bf, "🔓 解锁全部地块", "primary", lambda: self._confirm_dangerous("解锁全部地块", "确定要解锁所有可建造地块吗？", lambda: self._run_async(advanced_tools.unlock_all_plots)) if self._check_dll() else None).pack(side=tk.LEFT, padx=5)
        self._btn(bf, "🔍 探查地块", "normal", lambda: self._run_async(advanced_tools.probe_plots) if self._check_dll() else None).pack(side=tk.LEFT, padx=5)

    def _build_talent_tools(self):
        g = self._group("🧠 天赋系统")
        bf = tk.Frame(g, bg=COLORS["bg_card"])
        bf.pack(fill=tk.X, padx=16, pady=12)
        self._btn(bf, "🔓 解锁全部天赋", "primary", lambda: self._confirm_dangerous("解锁全部天赋", "确定要解锁所有天赋并升级到满级吗？", lambda: self._run_async(cheat_tools.unlock_all_talents)) if self._check_dll() else None).pack(side=tk.LEFT, padx=5)
        self._btn(bf, "🏆 天赋全满级", "primary", lambda: self._run_async(cheat_tools.max_all_talents) if self._check_dll() else None).pack(side=tk.LEFT, padx=5)
        self._btn(bf, "⭐ +200天赋点", "normal", lambda: self._run_async(cheat_tools.add_talent_points_200) if self._check_dll() else None).pack(side=tk.LEFT, padx=5)
        self._btn(bf, "🔍 天赋诊断", "normal", lambda: self._run_async(advanced_tools.diagnose_talent) if self._check_dll() else None).pack(side=tk.LEFT, padx=5)

    def _build_disaster_tools(self):
        g = self._group("🌪️ 灾害控制")
        bf = tk.Frame(g, bg=COLORS["bg_card"])
        bf.pack(fill=tk.X, padx=16, pady=12)
        self._btn(bf, "🌊 清除地震", "normal", lambda: self._run_async(cheat_tools.clear_all_earthquakes) if self._check_dll() else None).pack(side=tk.LEFT, padx=5)
        self._btn(bf, "✅ 关闭全部灾害", "primary", lambda: self._confirm_dangerous("关闭全部灾害", "确定要关闭所有自然灾害和人为灾害吗？", lambda: self._run_async(cheat_tools.close_all_disasters)) if self._check_dll() else None).pack(side=tk.LEFT, padx=5)
        self._btn(bf, "🚫 禁用灾害触发", "primary", lambda: self._run_async(cheat_tools.disable_disaster_triggers) if self._check_dll() else None).pack(side=tk.LEFT, padx=5)
        self._btn(bf, "🌪️ 清除自然灾害", "normal", lambda: self._run_async(world_tools.clear_natural_disaster) if self._check_dll() else None).pack(side=tk.LEFT, padx=5)
        self._btn(bf, "🔥 清除人为灾害", "normal", lambda: self._run_async(world_tools.clear_manmade_disaster) if self._check_dll() else None).pack(side=tk.LEFT, padx=5)

    def _build_festival_tools(self):
        g = self._group("🎆 节日控制")
        bf = tk.Frame(g, bg=COLORS["bg_card"])
        bf.pack(fill=tk.X, padx=16, pady=12)
        self._btn(bf, "⏸ 暂停节日", "normal", lambda: self._run_async(cheat_tools.pause_festival) if self._check_dll() else None).pack(side=tk.LEFT, padx=5)
        self._btn(bf, "🎆 关闭烟花", "normal", lambda: self._run_async(cheat_tools.close_fireworks) if self._check_dll() else None).pack(side=tk.LEFT, padx=5)
        self._btn(bf, "📢 清除节日广告", "normal", lambda: self._run_async(cheat_tools.clear_all_festival_ads) if self._check_dll() else None).pack(side=tk.LEFT, padx=5)
        self._btn(bf, "🌸 固定季节", "normal", lambda: self._run_async(cheat_tools.fix_season, True) if self._check_dll() else None).pack(side=tk.LEFT, padx=5)
        self._btn(bf, "⏭ 跳过时间事件", "normal", lambda: self._run_async(cheat_tools.skip_time_events, True) if self._check_dll() else None).pack(side=tk.LEFT, padx=5)

    def _build_core_tools(self):
        g = self._group("💎 核心数值直接设置")
        bf = tk.Frame(g, bg=COLORS["bg_card"])
        bf.pack(fill=tk.X, padx=16, pady=12)
        self._btn(bf, "💰 设置金钱999万", "primary", lambda: self._run_async(cheat_tools.set_money, 9999999) if self._check_dll() else None).pack(side=tk.LEFT, padx=5)
        self._btn(bf, "😊 设置幸福度999", "primary", lambda: self._run_async(cheat_tools.set_happiness, 999) if self._check_dll() else None).pack(side=tk.LEFT, padx=5)
        self._btn(bf, "💡 设置创造力999", "primary", lambda: self._run_async(cheat_tools.set_creativity, 999) if self._check_dll() else None).pack(side=tk.LEFT, padx=5)
        self._btn(bf, "📈 设置繁荣999", "primary", lambda: self._run_async(cheat_tools.set_prosperity, 999) if self._check_dll() else None).pack(side=tk.LEFT, padx=5)
        self._btn(bf, "🏙️ 设置品阶14", "primary", lambda: self._run_async(cheat_tools.set_boom_level, 14) if self._check_dll() else None).pack(side=tk.LEFT, padx=5)
        self._btn(bf, "🔍 核心状态", "normal", lambda: self._run_async(cheat_tools.get_core_stats) if self._check_dll() else None).pack(side=tk.LEFT, padx=5)

        g2 = self._group("🌐 世界工具")
        bf2 = tk.Frame(g2, bg=COLORS["bg_card"])
        bf2.pack(fill=tk.X, padx=16, pady=12)
        self._btn(bf2, "💰 市场价格x0.1", "normal", lambda: self._run_async(world_tools.market_price_scale, 0.1) if self._check_dll() else None).pack(side=tk.LEFT, padx=5)
        self._btn(bf2, "↩ 恢复市场", "normal", lambda: self._run_async(world_tools.market_price_restore) if self._check_dll() else None).pack(side=tk.LEFT, padx=5)
        self._btn(bf2, "🔗 解锁产业链", "primary", lambda: self._run_async(world_tools.unlock_industry_chain) if self._check_dll() else None).pack(side=tk.LEFT, padx=5)
        self._btn(bf2, "🚫 清除难民", "normal", lambda: self._run_async(world_tools.clear_refugee) if self._check_dll() else None).pack(side=tk.LEFT, padx=5)
        self._btn(bf2, "⭐ 声望+10000", "normal", lambda: self._run_async(world_tools.add_reputation, 10000) if self._check_dll() else None).pack(side=tk.LEFT, padx=5)
        self._btn(bf2, "🧮 自动税收", "normal", lambda: self._run_async(world_tools.enable_auto_tax) if self._check_dll() else None).pack(side=tk.LEFT, padx=5)

    def _build_all_cheats(self):
        g = self._group("🔥 一键全开")
        tk.Label(g, text="点击下方按钮，一次性开启所有作弊功能", font=(FONT, 12),
                bg=COLORS["bg_card"], fg=COLORS["fg_muted"], anchor="w").pack(fill=tk.X, anchor=tk.W, padx=16, pady=8)
        bf = tk.Frame(g, bg=COLORS["bg_card"])
        bf.pack(fill=tk.X, padx=16, pady=12)
        self._btn(bf, "🔥 开启全部作弊", "danger", lambda: self._confirm_dangerous("开启全部作弊", "确定要一次性开启所有作弊功能吗？\n\n包括：天赋全解锁、成就全解锁、灾害全关闭、核心数值拉满等9项功能。", lambda: self._run_async(cheat_tools.enable_all_cheats)) if self._check_dll() else None).pack(side=tk.LEFT, padx=5)

        g2 = self._group("📋 功能清单")
        features = ["天赋全解锁+满级", "成就全解锁", "灾害全关闭", "季节固定", "天气固定",
                    "节日暂停", "城市全发展", "风水超级技能", "核心数值拉满"]
        for f in features:
            tk.Label(g2, text=f"  ✓ {f}", font=(FONT, 11), bg=COLORS["bg_card"],
                    fg=COLORS["success"], anchor="w").pack(fill=tk.X, anchor=tk.W, padx=20, pady=2)

    # ===== 引擎性能优化（v0.4.9）=====
    def _rebuild_current_page(self):
        """重绘当前操作面板（改完配置后刷新显示）"""
        try:
            self._update_action_panel(self.current_nav, self.current_func, "")
        except Exception:
            pass

    def _perf_info(self):
        """读取一次当前状态，返回 (info, cur_name, cur_n, cur_t)"""
        info = perf_read()
        name, n, t = perf_current()
        return info, name, n, t

    def _build_perf_tools(self, func=0):
        """
        「优化」导航页渲染入口。中间栏有 4 个子项，按 func 分别渲染对应分区；
        顶部状态条每段都会显示，保证切子项时上下文不丢。
        """
        builder = {
            0: self._build_perf_profiles,
            1: self._build_perf_detail,
            2: self._build_perf_system,
            3: self._build_perf_restore,
        }.get(func, self._build_perf_profiles)

        info = self._perf_draw_header()
        if info is None:
            return                      # 配置文件不可用，表头已给出错误提示
        builder(info)

    def _perf_draw_header(self):
        """渲染每个优化子页共用的顶部状态条。返回 info；配置不可用时返回 None。"""
        info, cur_name, cur_n, cur_t = self._perf_info()
        g = self._group("🖥️ 本机概览")
        try:
            hw = perf_hw()
        except Exception:
            hw = "（硬件信息不可用）"
        tk.Label(g, text=hw, font=(FONT, 11), bg=COLORS["bg_card"],
                fg=COLORS["fg"], anchor="w").pack(fill=tk.X, padx=16, pady=(6, 2))
        rec, why = perf_recommend()
        tk.Label(g, text=f"推荐：{why}", font=(FONT, 11), bg=COLORS["bg_card"],
                fg=COLORS["success"], anchor="w").pack(fill=tk.X, padx=16, pady=(0, 6))
        if not info["ok"]:
            tk.Label(g, text=info["msg"], font=(FONT, 11), bg=COLORS["bg_card"],
                     fg=COLORS["error"], justify=tk.LEFT, anchor="w").pack(fill=tk.X, padx=16, pady=6)
            return None
        state_txt = (f"当前已应用：{PROFILES.get(cur_name, {}).get('display', cur_name or '未应用')}"
                     f"  （{cur_n}/{cur_t} 项符合）") if cur_name else "当前未应用任何优化档"
        tk.Label(g, text=state_txt, font=(FONT, 11, "bold"), bg=COLORS["bg_card"],
                fg=COLORS["accent"] if cur_name else COLORS["fg_muted"],
                anchor="w").pack(fill=tk.X, padx=16, pady=(0, 4))
        return info

    def _build_perf_profiles(self, info):
        """子项 0：优化档位（三档切换 + 建议值预览）"""
        _, cur_name, _, _ = self._perf_info()
        rec, _ = perf_recommend()

        g2 = self._group("⚡ 优化档位")
        for name in PROFILE_ORDER:
            p = PROFILES[name]
            row = tk.Frame(g2, bg=COLORS["bg_card"])
            row.pack(fill=tk.X, padx=16, pady=6)

            is_cur = (name == cur_name)
            style = "primary" if is_cur else "normal"
            label = f"{'✓ ' if is_cur else ''}{p['display']}"
            self._btn(row, label, style,
                      lambda n=name: self._on_apply_perf(n)).pack(side=tk.LEFT, padx=(0, 10))

            tk.Label(row, text=p["desc"], font=(FONT, 10), bg=COLORS["bg_card"],
                    fg=COLORS["fg_muted"], anchor="w", justify=tk.LEFT,
                    wraplength=520).pack(side=tk.LEFT, fill=tk.X, expand=True)

        dyn = ", ".join(f"{k}={perf_dyn(k, rec)}" for k in ("NumCpuThread", "MinWorkSet", "MaxWorkSet"))
        tk.Label(g2, text=f"按本机自动计算的建议值：{dyn}", font=(FONT, 10),
                bg=COLORS["bg_card"], fg=COLORS["fg_muted"], anchor="w",
                justify=tk.LEFT).pack(fill=tk.X, padx=16, pady=(4, 6))

        self._build_perf_notes()

    def _build_perf_detail(self, info):
        """子项 1：改动明细（当前值 vs 目标值 + 逆向依据）"""
        _, cur_name, _, _ = self._perf_info()
        rec, _ = perf_recommend()
        show = cur_name if cur_name in PROFILES else rec

        g3 = self._group(f"📋 {PROFILES[show]['display']} · 改动明细")
        head = tk.Frame(g3, bg=COLORS["bg_card"])
        head.pack(fill=tk.X, padx=16, pady=(4, 2))
        for txt, w in (("项目", 26), ("当前值", 10), ("目标值", 10)):
            tk.Label(head, text=txt, width=w, font=(FONT, 10, "bold"),
                    bg=COLORS["bg_card"], fg=COLORS["fg_muted"],
                    anchor="w").pack(side=tk.LEFT)
        for c in PROFILES[show]["changes"]:
            want = c["value"] or perf_dyn(c["key"], show)
            have = info["values"].get((c["section"], c["key"]))
            ok = (str(have) == str(want))
            row = tk.Frame(g3, bg=COLORS["bg_card"])
            row.pack(fill=tk.X, padx=16, pady=1)
            tk.Label(row, text=c.get("label", c["key"]), width=26, font=(FONT, 10),
                    bg=COLORS["bg_card"], fg=COLORS["fg"], anchor="w").pack(side=tk.LEFT)
            tk.Label(row, text=str(have if have is not None else "—"), width=10, font=(FONT, 10),
                    bg=COLORS["bg_card"], fg=COLORS["fg_muted"], anchor="w").pack(side=tk.LEFT)
            tk.Label(row, text=str(want), width=10, font=(FONT, 10),
                    bg=COLORS["bg_card"], fg=COLORS["success"] if ok else COLORS["warning"],
                    anchor="w").pack(side=tk.LEFT)

        g3b = self._group("📄 各项依据（逆向证据）")
        for c in PROFILES[show]["changes"]:
            row = tk.Frame(g3b, bg=COLORS["bg_card"])
            row.pack(fill=tk.X, padx=16, pady=2)
            tk.Label(row, text=c.get("label", c["key"]), width=26, font=(FONT, 10),
                    bg=COLORS["bg_card"], fg=COLORS["fg"], anchor="w").pack(side=tk.LEFT)
            tk.Label(row, text=c.get("evidence", ""), font=(FONT, 9),
                    bg=COLORS["bg_card"], fg=COLORS["fg_muted"], anchor="w",
                    justify=tk.LEFT, wraplength=560).pack(side=tk.LEFT, fill=tk.X, expand=True)

        self._build_perf_notes()

    def _build_perf_system(self, info):
        """子项 2：系统侧优化（锁独显 / 关全屏优化）"""
        g4 = self._group("🖥️ 系统侧优化（双显卡笔记本必看）")
        bf4 = tk.Frame(g4, bg=COLORS["bg_card"])
        bf4.pack(fill=tk.X, padx=16, pady=10)
        self._btn(bf4, "🎮 锁定高性能独显", "primary", self._on_perf_gpu).pack(side=tk.LEFT, padx=5)
        self._btn(bf4, "🪟 关闭全屏优化", "normal", self._on_perf_fso).pack(side=tk.LEFT, padx=5)
        tk.Label(g4, text="游戏跑在集显上是笔记本「优化差」最常见的原因。这两项改注册表后对下次启动生效，无需重装驱动。",
                font=(FONT, 10), bg=COLORS["bg_card"], fg=COLORS["fg_muted"],
                anchor="w", justify=tk.LEFT, wraplength=620).pack(fill=tk.X, padx=16, pady=(0, 8))

        g4b = self._group("📂 配置位置")
        tk.Label(g4b, text=info["ini"], font=(FONT, 10), bg=COLORS["bg_card"],
                fg=COLORS["fg"], anchor="w", justify=tk.LEFT,
                wraplength=620).pack(fill=tk.X, padx=16, pady=6)

        self._build_perf_notes()

    def _build_perf_restore(self, info):
        """子项 3：还原"""
        g5 = self._group("↩ 还原")
        bk = perf_backup_info()
        bk_txt = (f"备份可用（{bk['created']}，{bk['size']} 字节）\n{bk['path']}"
                  if bk else "尚无备份（首次应用时自动创建）")
        tk.Label(g5, text=bk_txt, font=(FONT, 10), bg=COLORS["bg_card"],
                fg=COLORS["fg_muted"], anchor="w", justify=tk.LEFT,
                wraplength=620).pack(fill=tk.X, padx=16, pady=(4, 6))
        bf5 = tk.Frame(g5, bg=COLORS["bg_card"])
        bf5.pack(fill=tk.X, padx=16, pady=(0, 10))
        self._btn(bf5, "↩ 一键还原到备份", "danger", self._on_perf_restore).pack(side=tk.LEFT, padx=5)
        self._btn(bf5, "🔄 刷新状态", "normal", self._rebuild_current_page).pack(side=tk.LEFT, padx=5)

        self._build_perf_notes()

    def _build_perf_notes(self):
        """各优化子页底部共用的说明"""
        g6 = self._group("ℹ️ 说明")
        for line in [
            "· 本页改的是游戏 configs\\config.ini，属启动期配置 —— 改动后必须重启游戏才生效。",
            "· 与 Lua 注入是两条独立通道：注入改运行期内存，这里改引擎出厂参数。",
            "· 已验证：游戏不会把 config.ini 写回去，改值不会被覆盖。",
            "· 无效项提醒：config.cfg 的 LogicFrame / RenderFrame 没有任何代码读取，改它不会解锁帧率。",
            "· 若出现物件闪烁或贴图错乱，先把「剔除多线程 / 资源加载多线程」改回 0，或直接一键还原。",
        ]:
            tk.Label(g6, text=line, font=(FONT, 10), bg=COLORS["bg_card"],
                    fg=COLORS["fg_muted"], anchor="w", justify=tk.LEFT,
                    wraplength=640).pack(fill=tk.X, padx=16, pady=1)

    def _on_apply_perf(self, name):
        """应用某一档"""
        info, cur_name, _, _ = self._perf_info()
        if not info["ok"]:
            messagebox.showerror("无法应用", info["msg"])
            return
        p = PROFILES[name]
        detail = "\n".join(
            f"· {c.get('label', c['key'])} = {c['value'] or perf_dyn(c['key'], name)}"
            for c in p["changes"]
        )
        if not messagebox.askyesno(
            f"应用 {p['display']}",
            f"{p['desc']}\n\n将写入以下 {len(p['changes'])} 项：\n{detail}\n\n"
            f"改动前会自动备份原始配置。\n配置在启动时读取，需重启游戏生效。\n\n确定应用？"):
            return
        res = perf_apply(name, dry_run=False)
        if res["ok"]:
            log_success(f"[引擎优化] {p['display']} 已应用")
            tip = res["msg"]
            try:
                if perf_optimizer.is_game_running():
                    tip += "\n\n检测到游戏正在运行 —— 请先关闭游戏再重新启动，改动才会生效。"
            except Exception:
                pass
            messagebox.showinfo("应用完成", tip)
        else:
            messagebox.showerror("应用失败", res.get("msg", "未知错误"))
            log_error(f"[引擎优化] 应用失败: {res.get('msg')}")
        self._rebuild_current_page()

    def _on_perf_restore(self):
        """还原到备份"""
        if not messagebox.askyesno("还原配置", "确定要把游戏配置还原到备份的原始版本吗？\n\n此操作会撤销本页做过的全部优化改动。"):
            return
        res = perf_restore()
        if res["ok"]:
            log_success("[引擎优化] 已还原")
            messagebox.showinfo("还原完成", res["msg"])
        else:
            messagebox.showinfo("还原", res["msg"])
        self._rebuild_current_page()

    def _on_perf_gpu(self):
        res = perf_set_gpu()
        if res["ok"]:
            messagebox.showinfo("完成", res["msg"])
        else:
            messagebox.showerror("失败", res["msg"])

    def _on_perf_fso(self):
        res = perf_disable_fso()
        if res["ok"]:
            messagebox.showinfo("完成", res["msg"])
        else:
            messagebox.showerror("失败", res["msg"])

    # ============================================================
    # 离线页（v0.5.0）
    # ============================================================
    def _build_offline_tools(self, func=0):
        """
        「离线」导航页渲染入口。4 个子项：安装/卸载、状态总览、启动游戏、原理说明。
        每个子页顶部都会画状态条，切子项时上下文不丢。
        """
        builder = {
            0: self._build_oc_install,
            1: self._build_oc_status,
            2: self._build_oc_launch,
            3: self._build_oc_notes,
        }.get(func, self._build_oc_install)
        st = self._oc_draw_header()
        builder(st)

    def _oc_draw_header(self):
        """画离线页共用顶部状态条，返回 status() 字典（查询失败返回 None）。"""
        st = oc_status()
        g = self._group("🔓 离线化状态")
        if not st.get("ok"):
            tk.Label(g, text=st.get("msg", "状态查询失败"), font=(FONT, 11),
                     bg=COLORS["bg_card"], fg=COLORS["error"], anchor="w",
                     justify=tk.LEFT).pack(fill=tk.X, padx=16, pady=8)
            return None
        if not st.get("exe_exists"):
            tk.Label(g, text=st.get("msg", "游戏路径无效"), font=(FONT, 11),
                     bg=COLORS["bg_card"], fg=COLORS["error"], anchor="w",
                     justify=tk.LEFT).pack(fill=tk.X, padx=16, pady=8)
            return None

        installed = st.get("installed")
        tk.Label(g, text=("✅ " if installed else "⭕ ") + st.get("summary", ""),
                 font=(FONT, 13, "bold"), bg=COLORS["bg_card"],
                 fg=COLORS["success"] if installed else COLORS["warning"],
                 anchor="w").pack(fill=tk.X, padx=16, pady=(4, 6))

        tk.Label(g, text="游戏目录：" + str(st.get("game_path", "")),
                 font=(FONT, 10), bg=COLORS["bg_card"], fg=COLORS["fg_muted"],
                 anchor="w", justify=tk.LEFT, wraplength=620).pack(fill=tk.X, padx=16, pady=(0, 2))

        dll_map = {"emulator": "模拟器（已替换）", "original": "原版 Steam DLL",
                   "unknown": "未知 DLL（非本工具写入）", "missing": "缺失"}
        rows = [
            ("steam_api64.dll", dll_map.get(st.get("dll_state"), "?")),
            ("lua 散文件", "%d/%d 就位" % (len(st.get("lua_present", [])),
                                        len(st.get("lua_present", [])) + len(st.get("lua_missing", [])))),
            ("publish=0", "已写入" if st.get("publish_zero") else "未写入"),
            ("原 dll 备份", "有" if st.get("dll_backup") else "无"),
            ("游戏进程", "运行中" if st.get("game_running") else "未运行"),
            ("steam 进程", "运行中（安装后会避免唤醒）" if st.get("steam_running") else "未运行"),
        ]
        for k, v in rows:
            row = tk.Frame(g, bg=COLORS["bg_card"])
            row.pack(fill=tk.X, padx=16, pady=1)
            tk.Label(row, text=k, width=18, font=(FONT, 10), bg=COLORS["bg_card"],
                     fg=COLORS["fg_muted"], anchor="w").pack(side=tk.LEFT)
            tk.Label(row, text=v, font=(FONT, 10), bg=COLORS["bg_card"],
                     fg=COLORS["fg"], anchor="w").pack(side=tk.LEFT)
        return st

    def _build_oc_install(self, st):
        """子项 0：安装 / 卸载"""
        okp, pmsg = oc_payload_ready()
        g2 = self._group("📦 安装离线补丁")
        if not okp:
            tk.Label(g2, text="内置补丁不完整：" + pmsg, font=(FONT, 11),
                     bg=COLORS["bg_card"], fg=COLORS["error"], anchor="w",
                     justify=tk.LEFT, wraplength=620).pack(fill=tk.X, padx=16, pady=8)
        else:
            tk.Label(g2, text="内置补丁齐全（模拟器 dll + 4 个 lua 散文件）。\n"
                              "安装会：备份原 steam_api64.dll → 放入模拟器 → 部署 lua → 写 publish=0。\n"
                              "游戏本体 exe 不会被改动。",
                     font=(FONT, 10), bg=COLORS["bg_card"], fg=COLORS["fg_muted"],
                     anchor="w", justify=tk.LEFT, wraplength=620).pack(fill=tk.X, padx=16, pady=(2, 8))
            bf = tk.Frame(g2, bg=COLORS["bg_card"])
            bf.pack(fill=tk.X, padx=16, pady=6)
            self._btn(bf, "🔓 一键安装离线补丁", "primary", self._on_oc_install).pack(side=tk.LEFT, padx=5)
            self._btn(bf, "↩ 卸载还原", "danger", self._on_oc_uninstall).pack(side=tk.LEFT, padx=5)
            self._btn(bf, "🔄 刷新", "normal", self._rebuild_current_page).pack(side=tk.LEFT, padx=5)

        g2b = self._group("🧪 自检")
        bf2 = tk.Frame(g2b, bg=COLORS["bg_card"])
        bf2.pack(fill=tk.X, padx=16, pady=8)
        self._btn(bf2, "运行自检", "normal", self._on_oc_selfcheck).pack(side=tk.LEFT, padx=5)
        tk.Label(g2b, text="检查内置补丁、游戏路径、状态查询、登录日志解析 4 项是否正常。",
                 font=(FONT, 10), bg=COLORS["bg_card"], fg=COLORS["fg_muted"],
                 anchor="w", justify=tk.LEFT, wraplength=620).pack(fill=tk.X, padx=16, pady=(0, 6))

    def _build_oc_status(self, st):
        """子项 1：状态总览（lua 明细 + 最近一次登录结果）"""
        if st is None:
            return
        g = self._group("📄 lua 散文件明细")
        for rel in st.get("lua_present", []):
            row = tk.Frame(g, bg=COLORS["bg_card"])
            row.pack(fill=tk.X, padx=16, pady=1)
            tk.Label(row, text="✅", font=(FONT, 10), bg=COLORS["bg_card"],
                     fg=COLORS["success"]).pack(side=tk.LEFT, padx=(0, 6))
            tk.Label(row, text=rel, font=(FONT, 10), bg=COLORS["bg_card"],
                     fg=COLORS["fg"], anchor="w").pack(side=tk.LEFT)
        for rel in st.get("lua_missing", []):
            row = tk.Frame(g, bg=COLORS["bg_card"])
            row.pack(fill=tk.X, padx=16, pady=1)
            tk.Label(row, text="⭕", font=(FONT, 10), bg=COLORS["bg_card"],
                     fg=COLORS["fg_muted"]).pack(side=tk.LEFT, padx=(0, 6))
            tk.Label(row, text=rel + "（缺失）", font=(FONT, 10), bg=COLORS["bg_card"],
                     fg=COLORS["fg_muted"], anchor="w").pack(side=tk.LEFT)
        if not st.get("lua_present") and not st.get("lua_missing"):
            tk.Label(g, text="未检测到任何 lua 散文件。", font=(FONT, 10),
                     bg=COLORS["bg_card"], fg=COLORS["fg_muted"], anchor="w").pack(fill=tk.X, padx=16, pady=6)

        lg = oc_last_login()
        g2 = self._group("🪪 最近一次登录")
        if lg.get("found"):
            lines = [
                "登录结果：%s" % ("成功" if lg.get("login") else "失败"),
                "用户名：%s" % lg.get("username"),
                "账号：%s" % lg.get("account"),
                "在线模式：%s" % ("是" if lg.get("online") else "否（离线）"),
            ]
            color = COLORS["success"] if lg.get("login") else COLORS["error"]
        else:
            lines = [lg.get("msg", "无日志")]
            color = COLORS["fg_muted"]
        for txt in lines:
            tk.Label(g2, text=txt, font=(FONT, 10, "bold") if txt.startswith("登录结果") else (FONT, 10),
                     bg=COLORS["bg_card"], fg=color if txt.startswith("登录结果") else COLORS["fg"],
                     anchor="w").pack(fill=tk.X, padx=16, pady=1)
        if lg.get("log"):
            tk.Label(g2, text="日志：" + str(lg.get("log")), font=(FONT, 9),
                     bg=COLORS["bg_card"], fg=COLORS["fg_muted"], anchor="w").pack(fill=tk.X, padx=16, pady=(4, 2))
        if lg.get("expired_toast"):
            tk.Label(g2, text="⚠ 日志里出现「第三方验证过期 / 重启后再试」——离线补丁没生效，请重新安装。",
                     font=(FONT, 10), bg=COLORS["bg_card"], fg=COLORS["error"], anchor="w",
                     justify=tk.LEFT, wraplength=620).pack(fill=tk.X, padx=16, pady=(4, 6))
        bf = tk.Frame(g2, bg=COLORS["bg_card"])
        bf.pack(fill=tk.X, padx=16, pady=8)
        self._btn(bf, "🔄 刷新", "normal", self._rebuild_current_page).pack(side=tk.LEFT, padx=5)

    def _build_oc_launch(self, st):
        """子项 2：启动游戏（离线）"""
        g = self._group("🚀 启动")
        tk.Label(g, text="必须从 bin64 目录作为工作目录启动，否则游戏会闪退（日志只写 98 字节就退出）。\n"
                         "本按钮会自动以 bin64 为 CWD 拉起，并且不会唤醒 Steam。",
                 font=(FONT, 10), bg=COLORS["bg_card"], fg=COLORS["fg_muted"],
                 anchor="w", justify=tk.LEFT, wraplength=620).pack(fill=tk.X, padx=16, pady=(2, 8))
        bf = tk.Frame(g, bg=COLORS["bg_card"])
        bf.pack(fill=tk.X, padx=16, pady=6)
        self._btn(bf, "🎮 启动游戏（离线）", "primary", self._on_oc_launch).pack(side=tk.LEFT, padx=5)
        self._btn(bf, "⏹ 结束游戏进程", "danger", self._on_oc_kill).pack(side=tk.LEFT, padx=5)
        self._btn(bf, "🔄 刷新", "normal", self._rebuild_current_page).pack(side=tk.LEFT, padx=5)

        g2 = self._group("❗ 排错")
        for txt in [
            "· 闪退：确认是从本页按钮启动，或手动 cd 到 bin64 再运行 exe；不要在 Steam 库里点启动。",
            "· 仍弹「第三方验证过期」：lua 没被加载，回「安装/卸载」重装，再看状态总览。",
            "· 还是唤醒 Steam：dll 没换成模拟器，看状态条的 steam_api64.dll 一行。",
            "· 装了补丁后想走正版：先卸载还原，再 Steam 校验游戏文件。",
        ]:
            tk.Label(g2, text=txt, font=(FONT, 10), bg=COLORS["bg_card"],
                     fg=COLORS["fg"], anchor="w", justify=tk.LEFT,
                     wraplength=620).pack(fill=tk.X, padx=16, pady=2)

    def _build_oc_notes(self, st):
        """子项 3：原理说明"""
        g = self._group("🧩 为什么要两层")
        tk.Label(g, text="第一层 · Lua 短路登录", font=(FONT, 11, "bold"),
                 bg=COLORS["bg_card"], fg=COLORS["accent"], anchor="w").pack(fill=tk.X, padx=16, pady=(4, 2))
        tk.Label(g, text="游戏用金山 XG SDK（channel=11，XGJinShanWithSteamV2）。正常流程是拿 Steam 票据去服务器换登录结果，\n"
                         "「第三方验证过期」这句提示是服务端下发的，exe / config / lua 里都搜不到。\n"
                         "所以伪造票据没用——服务器不认。正确做法是在 sim_common 散文件里把 TryLogin 短路掉，\n"
                         "直接回调成一个本地成功结果，压根不发请求，服务器也就无从拒绝。",
                 font=(FONT, 10), bg=COLORS["bg_card"], fg=COLORS["fg"], anchor="w",
                 justify=tk.LEFT, wraplength=620).pack(fill=tk.X, padx=16, pady=(0, 6))

        tk.Label(g, text="第二层 · Steam 模拟器 dll", font=(FONT, 11, "bold"),
                 bg=COLORS["bg_card"], fg=COLORS["accent"], anchor="w").pack(fill=tk.X, padx=16, pady=(4, 2))
        tk.Label(g, text="XG 的 steam_service 会调 SteamAPI_RestartAppIfNecessary，把 Steam 拉起来。\n"
                         "自写的 steam_api64.dll 让这个接口返回 0（不需要重启/不需要 Steam），并伪造 SteamID、AppID、语言、昵称，\n"
                         "让引擎侧的自检全部通过。这一层只负责「别唤醒 Steam」，不负责登录。",
                 font=(FONT, 10), bg=COLORS["bg_card"], fg=COLORS["fg"], anchor="w",
                 justify=tk.LEFT, wraplength=620).pack(fill=tk.X, padx=16, pady=(0, 6))

        tk.Label(g, text="散文件优先级", font=(FONT, 11, "bold"),
                 bg=COLORS["bg_card"], fg=COLORS["accent"], anchor="w").pack(fill=tk.X, padx=16, pady=(4, 2))
        tk.Label(g, text="游戏根\\sim_common\\script\\** 优先于 pak 包。证据：往 xgagent_manager.lua 插 2 行后，\n"
                         "日志里 user init 的行号从 :173 变成 :175，说明读的确实是散文件。",
                 font=(FONT, 10), bg=COLORS["bg_card"], fg=COLORS["fg"], anchor="w",
                 justify=tk.LEFT, wraplength=620).pack(fill=tk.X, padx=16, pady=(0, 6))

        g2 = self._group("⚠ 边界")
        for txt in [
            "· 云存档、成就、客服反馈等联机功能不可用。",
            "· 必须从本页按钮启动或手动 cd 到 bin64 启动，不能从 Steam 库启动（dll 已被替换）。",
            "· 日志每 60 秒出现一次 Start get ticket 是后台刷新，属于无害噪音。",
        ]:
            tk.Label(g2, text=txt, font=(FONT, 10), bg=COLORS["bg_card"], fg=COLORS["fg_muted"],
                     anchor="w", justify=tk.LEFT, wraplength=620).pack(fill=tk.X, padx=16, pady=2)

    # ---- 离线页回调 ----
    def _on_oc_install(self):
        if oc_status().get("game_running"):
            messagebox.showerror("无法安装", "游戏正在运行，dll 被占用。请先关闭游戏。")
            return
        if not messagebox.askyesno(
                "安装离线补丁",
                "将把 bin64\\steam_api64.dll 换成模拟器（原文件备份为 .orig），\n"
                "并向游戏根目录部署 4 个 lua 散文件，同时在 config.cfg 写入 publish=0。\n\n"
                "游戏本体 exe 不会被修改，随时可卸载还原。\n\n确定安装？"):
            return
        res = oc_install()
        if res.get("ok"):
            log_success("[离线] 安装完成")
            messagebox.showinfo("安装完成", res.get("msg", "") + "\n\n" +
                                "\n".join("· " + s for s in res.get("steps", [])))
        else:
            log_error("[离线] 安装失败: %s" % res.get("msg"))
            messagebox.showerror("安装失败", res.get("msg", "未知错误"))
        self._rebuild_current_page()

    def _on_oc_uninstall(self):
        if oc_status().get("game_running"):
            messagebox.showerror("无法卸载", "游戏正在运行，dll 被占用。请先关闭游戏。")
            return
        if not messagebox.askyesno("卸载还原",
                                   "将还原原版 steam_api64.dll，删除 4 个 lua 散文件，并移除 publish=0。\n\n"
                                   "卸载后游戏需要 Steam 正常登录。确定卸载？"):
            return
        res = oc_uninstall()
        if res.get("ok"):
            log_success("[离线] 已卸载还原")
            messagebox.showinfo("卸载完成", res.get("msg", "") + "\n\n" +
                                "\n".join("· " + s for s in res.get("steps", [])))
        else:
            messagebox.showerror("卸载失败", res.get("msg", "未知错误"))
        self._rebuild_current_page()

    def _on_oc_launch(self):
        st = oc_status()
        if st.get("game_running"):
            messagebox.showinfo("已在运行", "游戏进程已经在运行了。")
            return
        if not st.get("installed"):
            if not messagebox.askyesno("尚未安装",
                                       "离线补丁还没装，直接启动会走 Steam 正常登录。\n\n"
                                       "仍要以离线方式启动吗？"):
                return
        res = oc_launch()
        if res.get("ok"):
            log_success("[离线] 已启动游戏（CWD=bin64）")
        else:
            log_error("[离线] 启动失败: %s" % res.get("msg"))
            messagebox.showerror("启动失败", res.get("msg", "未知错误"))
        self._rebuild_current_page()

    def _on_oc_kill(self):
        if not oc_status().get("game_running"):
            messagebox.showinfo("未运行", "没有检测到游戏进程。")
            return
        res = oc_kill()
        log_success("[离线] 已结束游戏进程" if res.get("ok") else "[离线] 结束失败")
        self._rebuild_current_page()

    def _on_oc_selfcheck(self):
        res = oc_self_check()
        try:
            passed, total, items = res
        except Exception:
            passed, total, items = 0, 0, []
        lines = []
        for it in items:
            try:
                ok, name, detail = it
            except Exception:
                continue
            lines.append("%s %s —— %s" % ("✅" if ok else "❌", name, detail))
        body = "\n".join(lines) or "（无检查项）"
        messagebox.showinfo("离线模块自检", "%d/%d 通过\n\n%s" % (passed, total, body))
        self._rebuild_current_page()

    # ===== 存档页 =====
    def _build_save(self, func):
        g = self._group("💾 存档管理")
        bf = tk.Frame(g, bg=COLORS["bg_card"])
        bf.pack(fill=tk.X, padx=16, pady=12)
        self._btn(bf, "🔄 刷新存档列表", "normal", self._refresh_saves).pack(side=tk.LEFT, padx=5)
        self._btn(bf, "📦 备份当前存档", "primary", self._backup_save).pack(side=tk.LEFT, padx=5)
        self._btn(bf, "🧹 清理旧备份", "danger", self._clean_backups).pack(side=tk.LEFT, padx=5)
        self._btn(bf, "📁 打开文件夹", "normal", self._open_save_dir).pack(side=tk.LEFT, padx=5)
        save_dir = self._get_save_dir()
        path_frame = tk.Frame(g, bg=COLORS["bg_card"])
        path_frame.pack(fill=tk.X, anchor=tk.W, padx=16, pady=(4, 8))
        tk.Label(path_frame, text="存档路径:", font=(FONT, 10),
                bg=COLORS["bg_card"], fg=COLORS["fg_muted"], anchor="w").pack(side=tk.LEFT)
        self.save_path_label = tk.Label(path_frame, text=save_dir, font=(FONT, 10),
                bg=COLORS["bg_card"], fg=COLORS["accent"], anchor="w", wraplength=400)
        self.save_path_label.pack(side=tk.LEFT, padx=6)
        self._btn(path_frame, "浏览...", "normal", self._choose_save_dir).pack(side=tk.LEFT)


        g2 = self._group("📂 存档列表")
        self.save_list_frame = tk.Frame(g2, bg=COLORS["bg_card"])
        self.save_list_frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=8)
        self._refresh_saves()

    def _choose_save_dir(self):
        d = filedialog.askdirectory(title="选择存档文件夹")
        if d:
            self.config["save_dir"] = d
            save_config(self.config)
            self.save_path_label.config(text=d)
            log_success(f"存档路径已改为: {d}")
            self._refresh_saves()

    def _open_save_dir(self):
        save_dir = self._get_save_dir()
        if os.path.exists(save_dir):
            os.startfile(save_dir)
            log_info(f"已打开存档文件夹: {save_dir}")
        else:
            log_error(f"存档文件夹不存在: {save_dir}")

    def _get_save_dir(self):
        return self.config.get("save_dir") or self._auto_find_save_dir()

    def _auto_find_save_dir(self):
        """自动扫描 storage 目录，找包含 .boh 存档文件的目录"""
        game_path = self.config.get("game_path", DEFAULT_GAME_PATH)
        storage = os.path.join(game_path, "storage")
        if not os.path.exists(storage):
            return storage
        # 遍历 storage 下所有子目录，找有 .boh 文件的
        candidates = []
        for root, dirs, files in os.walk(storage):
            boh = [f for f in files if f.endswith(".boh")]
            if boh:
                candidates.append((root, len(boh)))
        if candidates:
            # 选存档最多的那个目录
            candidates.sort(key=lambda x: -x[1])
            return candidates[0][0]
        return storage

    def _refresh_saves(self):
        for w in self.save_list_frame.winfo_children():
            w.destroy()
        save_dir = self._get_save_dir()
        if not os.path.exists(save_dir):
            tk.Label(self.save_list_frame, text=f"存档目录不存在：\n{save_dir}",
                    font=(FONT, 11), bg=COLORS["bg_card"], fg=COLORS["error"],
                    justify=tk.LEFT, anchor="w").pack(fill=tk.X, anchor=tk.W, pady=10)
            return
        files = [f for f in os.listdir(save_dir) if f.endswith(".boh") or f.endswith(".dat") or f.endswith(".save")]
        if not files:
            tk.Label(self.save_list_frame, text="未找到存档文件",
                    font=(FONT, 11), bg=COLORS["bg_card"], fg=COLORS["fg_muted"], anchor="w").pack(fill=tk.X, anchor=tk.W, pady=10)
            return
        for f in sorted(files):
            fpath = os.path.join(save_dir, f)
            mtime = datetime.fromtimestamp(os.path.getmtime(fpath)).strftime("%Y-%m-%d %H:%M")
            size = os.path.getsize(fpath)
            row = tk.Frame(self.save_list_frame, bg=COLORS["bg_card"])
            row.pack(fill=tk.X, pady=2)
            tk.Label(row, text=f"📄 {f}", font=(FONT, 11, "bold"),
                    bg=COLORS["bg_card"], fg=COLORS["fg"], anchor="w").pack(side=tk.LEFT)
            tk.Label(row, text=f"  {mtime}  {size//1024}KB", font=(FONT, 10),
                    bg=COLORS["bg_card"], fg=COLORS["fg_muted"], anchor="w").pack(side=tk.LEFT)
            self._btn(row, "备份", "normal", lambda p=fpath: self._backup_file(p)).pack(side=tk.RIGHT, padx=3)
        log_info(f"找到 {len(files)} 个存档文件")

    def _backup_save(self):
        save_dir = self._get_save_dir()
        if not os.path.exists(save_dir):
            log_error("存档目录不存在")
            return
        backup_dir = os.path.join(os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__)), "backups")
        from src.atomic_file import atomic_backup_dir
        success, dest, err = atomic_backup_dir(save_dir, backup_dir, "save_backup")
        if success:
            log_success(f"存档已备份到: {dest}")
        else:
            log_error(f"备份失败: {err}")

    def _backup_file(self, filepath):
        backup_dir = os.path.join(os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__)), "backups")
        from src.atomic_file import atomic_backup_file
        success, dest, err = atomic_backup_file(filepath, backup_dir)
        if success:
            log_success(f"已备份: {os.path.basename(filepath)}")
        else:
            log_error(f"备份失败: {err}")

    def _clean_backups(self):
        backup_dir = os.path.join(os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__)), "backups")
        if not os.path.exists(backup_dir):
            log_warning("备份目录不存在")
            return
        if not messagebox.askyesno("确认", "确定要清理所有旧备份吗？"):
            return
        try:
            count = 0
            for item in os.listdir(backup_dir):
                item_path = os.path.join(backup_dir, item)
                if os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                    count += 1
                else:
                    os.remove(item_path)
                    count += 1
            log_success(f"已清理 {count} 个备份文件")
        except Exception as e:
            log_error(f"清理失败: {e}")

    # ===== 设置页 =====
    # ===== 监控页（进程级：内存/CPU/状态）=====
    def _build_monitor(self):
        g = self._group("📊 进程监控")
        # 状态卡片：PID / 内存 / CPU / DLL
        cards_f = tk.Frame(g, bg=COLORS["bg_card"])
        cards_f.pack(fill=tk.X, padx=16, pady=(0, 10))
        self.mon_cards = {}
        for title, key in [
            ("🎮 进程 PID", "mon_pid"),
            ("💾 内存占用", "mon_mem"),
            ("🔥 CPU", "mon_cpu"),
            ("🔌 DLL", "mon_dll"),
            ("🏙️ 品阶", "mon_rank"),
            ("⏰ 时间", "mon_time"),
        ]:
            card = tk.Frame(cards_f, bg=COLORS["bg_card"],
                           highlightbackground=COLORS["border"], highlightthickness=1)
            card.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
            tk.Label(card, text=title, font=(FONT, 10), bg=COLORS["bg_card"],
                    fg=COLORS["fg_muted"], anchor="w").pack(fill=tk.X, padx=10, pady=(8, 2))
            l = tk.Label(card, text="--", font=(FONT, 14, "bold"), bg=COLORS["bg_card"],
                        fg=COLORS["fg"], anchor="w")
            l.pack(fill=tk.X, padx=10, pady=(0, 8))
            self.mon_cards[key] = l

        # 内存历史曲线
        g2 = self._group("💾 内存历史（近30秒）")
        self.mem_canvas = tk.Canvas(g2, height=120, bg=COLORS["bg_card"],
                                    highlightbackground=COLORS["border"], highlightthickness=1)
        self.mem_canvas.pack(fill=tk.X, padx=16, pady=8)
        self.mem_history = []  # 存最近30个采样点

        # 游戏内状态
        g3 = self._group("🎮 游戏状态")
        self.mon_game_text = tk.Text(g3, font=("Consolas", 11), bg=COLORS["bg_card"],
                                    fg=COLORS["fg"], relief=tk.FLAT, wrap=tk.WORD, height=8)
        self.mon_game_text.pack(fill=tk.X, padx=16, pady=8)
        self.mon_game_text.config(state=tk.DISABLED)

        # 一键诊断
        diag_f = tk.Frame(g, bg=COLORS["bg_card"])
        diag_f.pack(fill=tk.X, padx=16, pady=(0, 10))
        self._btn(diag_f, "🔍 一键系统诊断", "primary", self._run_full_diagnosis).pack(side=tk.LEFT, padx=5)
        self._btn(diag_f, "📋 导出诊断报告", "normal", self._export_diagnosis_report).pack(side=tk.LEFT, padx=5)

        self._monitor_running = True
        self._refresh_monitor()

    def _run_full_diagnosis(self):
        """运行完整系统诊断，结果输出到日志"""
        from src.diagnostic import run_full_diagnosis
        dll_path = get_dll_path()
        report = run_full_diagnosis(
            game_pid=self.game_pid,
            dll_path=dll_path,
            config=self.config
        )
        log_info("=== 系统诊断报告 ===")
        for line in report.split("\n"):
            log_info(line)
        messagebox.showinfo("诊断完成", "系统诊断已完成，结果请查看日志面板。")

    def _export_diagnosis_report(self):
        """导出诊断报告到文件"""
        from src.diagnostic import run_full_diagnosis, export_diagnosis_report
        from tkinter import filedialog
        dll_path = get_dll_path()
        report = run_full_diagnosis(
            game_pid=self.game_pid,
            dll_path=dll_path,
            config=self.config
        )
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")],
            initialfile="woldvein_diagnosis.txt"
        )
        if path:
            success, msg = export_diagnosis_report(report, path)
            if success:
                messagebox.showinfo("导出成功", f"诊断报告已导出到:\n{path}")
            else:
                messagebox.showerror("导出失败", msg)

    def _refresh_monitor(self):
        if not hasattr(self, '_monitor_running') or not self._monitor_running:
            return
        try:
            import psutil
            # === 进程级监控 ===
            pid = self.game_pid
            if pid:
                try:
                    p = psutil.Process(pid)
                    mem_mb = p.memory_info().rss / 1024 / 1024
                    cpu = p.cpu_percent(interval=0.1)
                    self.mon_cards["mon_pid"].config(text=str(pid))
                    self.mon_cards["mon_mem"].config(text=f"{mem_mb:.0f} MB",
                        fg=COLORS["warning"] if mem_mb > 2000 else COLORS["fg"])
                    self.mon_cards["mon_cpu"].config(text=f"{cpu:.0f}%")
                    # 记录历史
                    self.mem_history.append(mem_mb)
                    if len(self.mem_history) > 30:
                        self.mem_history.pop(0)
                    self._draw_mem_chart()
                except psutil.NoSuchProcess:
                    self.mon_cards["mon_pid"].config(text="已退出", fg=COLORS["error"])
            else:
                self.mon_cards["mon_pid"].config(text="未运行", fg=COLORS["fg_muted"])
                self.mon_cards["mon_mem"].config(text="--", fg=COLORS["fg_muted"])
                self.mon_cards["mon_cpu"].config(text="--", fg=COLORS["fg_muted"])

            self.mon_cards["mon_dll"].config(
                text="已注入" if self.dll_injected else "未注入",
                fg=COLORS["success"] if self.dll_injected else COLORS["warning"])

            # === 游戏内状态（Lua） ===
            if self.dll_injected:
                self._read_game_state()
        except Exception as e:
            pass
        self.root.after(1500, self._refresh_monitor)

    def _draw_mem_chart(self):
        """画内存历史曲线"""
        c = self.mem_canvas
        c.delete("all")
        w = c.winfo_width() or 600
        h = 120
        if not self.mem_history:
            return
        mx = max(self.mem_history)
        mn = min(self.mem_history)
        rng = mx - mn if mx > mn else 1
        # 网格线
        c.create_line(10, h-20, w-10, h-20, fill=COLORS["border"])
        c.create_line(10, 10, 10, h-20, fill=COLORS["border"])
        # 折线
        pts = []
        n = len(self.mem_history)
        for i, v in enumerate(self.mem_history):
            x = 10 + (w - 20) * i / max(n - 1, 1)
            y = (h - 20) - (h - 35) * (v - mn) / rng
            pts.extend([x, y])
        if len(pts) >= 4:
            c.create_line(pts, fill=COLORS["accent"], width=2, smooth=True)
            # 最新值点
            c.create_oval(pts[-2]-3, pts[-1]-3, pts[-2]+3, pts[-1]+3,
                         fill=COLORS["accent"], outline="")
        # 标注
        c.create_text(w-10, 15, text=f"峰值 {mx:.0f} MB", anchor="e",
                     fill=COLORS["fg_muted"], font=(FONT, 9))
        c.create_text(10, 15, text=f"当前 {self.mem_history[-1]:.0f} MB",
                     anchor="w", fill=COLORS["fg"], font=(FONT, 9))

    def _read_game_state(self):
        lua = r'''
local ok, err = pcall(function()
    local out = {}
    local src = g_camp.m_tbSource
    out.money = src[1] or 0
    out.food = src[5] or 0
    out.wood = src[3] or 0
    out.pop = src[8] or 0
    out.rank = g_camp.boom.m_nLevel or 0
    local n = 0
    for k in pairs(g_BuildingWorldModule:GetAllWorldObjects()) do n=n+1 end
    out.build = n
    local t = g_Time.m_tb
    local sn = {"春","夏","秋","冬"}
    return table.concat({out.money, out.food, out.wood, out.pop, out.rank, out.build,
        t.m_nYear or 0, t.m_nMonth or 0, t.m_nDay or 0, sn[t.m_nSeason or 1] or "?"}, "|")
end)
if not ok then return "ERR" end
return err
        '''
        try:
            success, result = execute_lua_safe(lua, timeout=5.0)
            if success and result and not str(result).startswith("ERR"):
                parts = str(result).split("|")
                money, food, wood, pop, rank, build, year, month, day, season = parts
                self.root.after(0, lambda: self._update_monitor_ui(
                    money, food, wood, pop, rank, build, year, month, day, season))
        except:
            pass

    def _update_monitor_ui(self, money, food, wood, pop, rank, build, year, month, day, season):
        try:
            def fmt(n):
                try: return f"{int(float(n)):,}"
                except: return n
            self.mon_cards["mon_rank"].config(text=f"Lv{rank}")
            self.mon_cards["mon_time"].config(text=f"{year}/{month}/{day} {season}")
            txt = (f"金钱: {fmt(money)}\n人口: {fmt(pop)}\n"
                   f"食物: {fmt(food)}   木料: {fmt(wood)}\n"
                   f"建筑: {fmt(build)}")
            self.mon_game_text.config(state=tk.NORMAL)
            self.mon_game_text.delete("1.0", tk.END)
            self.mon_game_text.insert("1.0", txt)
            self.mon_game_text.config(state=tk.DISABLED)
        except:
            pass

    # ===== 设置页 =====

    def _open_backup_dir(self):
        d = os.path.join(os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__)), "backups")
        os.makedirs(d, exist_ok=True)
        os.startfile(d)
        log_info(f"已打开备份文件夹: {d}")

    def _open_config_dir(self):
        d = os.path.dirname(os.path.abspath(__file__))
        os.startfile(d)
        log_info(f"已打开配置文件夹: {d}")

    def _set_window_size(self, w, h):
        self.root.geometry(f"{w}x{h}")
        log_success(f"窗口大小已设置: {w}x{h}")

    def _build_settings(self, func):
        # 窗口设置
        g = self._group("🪟 窗口设置")
        bf = tk.Frame(g, bg=COLORS["bg_card"])
        bf.pack(fill=tk.X, padx=16, pady=12)
        g = self._group("🪟 窗口大小")
        bf = tk.Frame(g, bg=COLORS["bg_card"])
        bf.pack(fill=tk.X, padx=16, pady=12)
        self._btn(bf, "1000x600", "normal", lambda: self._set_window_size(1000, 600)).pack(side=tk.LEFT, padx=4)
        self._btn(bf, "1200x750", "normal", lambda: self._set_window_size(1200, 750)).pack(side=tk.LEFT, padx=4)
        self._btn(bf, "1400x900", "normal", lambda: self._set_window_size(1400, 900)).pack(side=tk.LEFT, padx=4)
        self._btn(bf, "全屏宽", "primary", lambda: self._set_window_size(1920, 1040)).pack(side=tk.LEFT, padx=4)
        self._btn(bf, "📁 打开备份文件夹", "normal", self._open_backup_dir).pack(side=tk.LEFT, padx=4)
        self._btn(bf, "📁 打开配置文件夹", "normal", self._open_config_dir).pack(side=tk.LEFT, padx=4)

        # ===== 语言和主题设置（v0.4.6 新增）=====
        g_lang = self._group("🌐 语言和主题")
        bf_lang = tk.Frame(g_lang, bg=COLORS["bg_card"])
        bf_lang.pack(fill=tk.X, padx=16, pady=12)

        # 语言切换
        tk.Label(bf_lang, text="界面语言:", font=(FONT, 11), bg=COLORS["bg_card"], fg=COLORS["fg"]).pack(side=tk.LEFT, padx=(0, 8))
        self.lang_var = tk.StringVar(value=get_i18n().get_language_name())
        lang_options = [name for name in get_i18n().get_available_languages().values()]
        self.lang_menu = ttk.Combobox(bf_lang, textvariable=self.lang_var, values=lang_options,
                                       state="readonly", width=12, font=(FONT, 10))
        self.lang_menu.pack(side=tk.LEFT, padx=(0, 20))
        self.lang_menu.bind("<<ComboboxSelected>>", self._on_language_change)

        # 主题切换
        tk.Label(bf_lang, text="界面主题:", font=(FONT, 11), bg=COLORS["bg_card"], fg=COLORS["fg"]).pack(side=tk.LEFT, padx=(0, 8))
        self.theme_var = tk.StringVar(value="浅色")
        theme_options = ["浅色", "深色"]
        self.theme_menu = ttk.Combobox(bf_lang, textvariable=self.theme_var, values=theme_options,
                                       state="readonly", width=10, font=(FONT, 10))
        self.theme_menu.pack(side=tk.LEFT, padx=(0, 20))
        self.theme_menu.bind("<<ComboboxSelected>>", self._on_theme_change)

        # 紧急停止按钮
        self._btn(bf_lang, "🛑 紧急停止", "danger", self._on_emergency_stop).pack(side=tk.RIGHT, padx=4)

        # ===== 预设方案管理（v0.4.6 新增）=====
        g_preset = self._group("📦 预设方案")
        bf_preset = tk.Frame(g_preset, bg=COLORS["bg_card"])
        bf_preset.pack(fill=tk.X, padx=16, pady=12)

        self._btn(bf_preset, "💾 保存当前配置", "primary", self._on_save_preset).pack(side=tk.LEFT, padx=5)
        self._btn(bf_preset, "📂 加载预设", "normal", self._on_load_preset).pack(side=tk.LEFT, padx=5)
        self._btn(bf_preset, "🗑️ 删除预设", "normal", self._on_delete_preset).pack(side=tk.LEFT, padx=5)
        self._btn(bf_preset, "📋 列出预设", "normal", self._on_list_presets).pack(side=tk.LEFT, padx=5)

        tk.Frame(g, bg=COLORS["bg_card"], height=8).pack()
        if func == 0:  # 热键
            self._build_hotkey_settings()
        elif func == 1:  # 日志
            self._build_log_settings()
        elif func == 2:  # MOD
            self._build_mod_settings()
        else:  # 关于
            self._build_about()

    def _build_hotkey_settings(self):
        g = self._group("⌨️ 全局热键列表")
        bf = tk.Frame(g, bg=COLORS["bg_card"])
        bf.pack(fill=tk.X, padx=16, pady=12)
        self._btn(bf, "↩ 恢复默认热键", "primary", self._restore_hotkeys).pack(side=tk.LEFT, padx=5)
        self._btn(bf, "🔄 重新注册", "normal", self._reregister_hotkeys).pack(side=tk.LEFT, padx=5)
        self._btn(bf, "⚠️ 检测冲突", "normal", self._check_hotkey_conflicts).pack(side=tk.LEFT, padx=5)

        # 热键列表
        list_frame = tk.Frame(g, bg=COLORS["bg_card"])
        list_frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=8)

        # 表头
        header = tk.Frame(list_frame, bg=COLORS["bg_sidebar"])
        header.pack(fill=tk.X)
        tk.Label(header, text="功能", font=(FONT, 11, "bold"), bg=COLORS["bg_sidebar"],
                fg=COLORS["fg"], width=20, anchor="w").pack(side=tk.LEFT, padx=8, pady=6)
        tk.Label(header, text="热键", font=(FONT, 11, "bold"), bg=COLORS["bg_sidebar"],
                fg=COLORS["fg"], width=15, anchor="w").pack(side=tk.LEFT, padx=8, pady=6)

        # 热键项
        current_hotkeys = self.config.get("hotkeys", get_default_hotkeys())
        for key, info in HOTKEY_DEFS.items():
            row = tk.Frame(list_frame, bg=COLORS["bg_card"])
            row.pack(fill=tk.X, pady=1)
            tk.Label(row, text=info["name"], font=(FONT, 11), bg=COLORS["bg_card"],
                    fg=COLORS["fg"], width=20, anchor="w").pack(side=tk.LEFT, padx=8, pady=4)
            hotkey = current_hotkeys.get(key, info["default"])
            tk.Label(row, text=hotkey, font=(FONT, 11, "bold"), bg=COLORS["bg_card"],
                    fg=COLORS["accent"], width=15, anchor="w").pack(side=tk.LEFT, padx=8, pady=4)

        tk.Label(g, text="提示：双击热键可修改（功能开发中）", font=(FONT, 10),
                bg=COLORS["bg_card"], fg=COLORS["fg_muted"], anchor="w").pack(fill=tk.X, anchor=tk.W, padx=16, pady=8)

    def _restore_hotkeys(self):
        defaults = get_default_hotkeys()
        self.config["hotkeys"] = defaults
        save_config(self.config)
        log_success("热键已恢复默认设置")
        self._switch_func(self.current_func)

    def _reregister_hotkeys(self):
        log_info("重新注册热键...")
        log_success("热键重新注册完成")

    def _check_hotkey_conflicts(self):
        """检测热键冲突"""
        detector = get_hotkey_detector()
        current_hotkeys = self.config.get("hotkeys", get_default_hotkeys())

        # 注册所有热键到检测器
        for key, info in HOTKEY_DEFS.items():
            hotkey = current_hotkeys.get(key, info["default"])
            detector.register(key, hotkey)

        # 检查冲突
        all_conflicts = detector.check_all()

        if all_conflicts:
            conflict_text = "发现以下热键冲突：\n\n"
            for c in all_conflicts:
                conflict_text += f"• {c['hotkey']}: {', '.join(c['functions'])}\n"
            messagebox.showwarning("热键冲突", conflict_text)
            log_warning(f"检测到 {len(all_conflicts)} 个热键冲突")
        else:
            # 也检查系统热键冲突
            system_conflicts = []
            for key, info in HOTKEY_DEFS.items():
                hotkey = current_hotkeys.get(key, info["default"])
                has_conflict, conflicts = detector.check(hotkey)
                if has_conflict:
                    for c in conflicts:
                        if c["type"] == "system":
                            system_conflicts.append(f"{hotkey} ({info['name']}): {c['description']}")

            if system_conflicts:
                conflict_text = "以下热键与系统热键冲突：\n\n"
                conflict_text += "\n".join(f"• {c}" for c in system_conflicts[:10])
                if len(system_conflicts) > 10:
                    conflict_text += f"\n... 还有 {len(system_conflicts)-10} 个"
                messagebox.showwarning("系统热键冲突", conflict_text)
                log_warning(f"检测到 {len(system_conflicts)} 个系统热键冲突")
            else:
                messagebox.showinfo("热键检测", "未检测到热键冲突，所有热键配置正常。")
                log_success("热键冲突检测完成，未发现冲突")

    def _build_log_settings(self):
        g = self._group("📝 日志管理")
        tk.Label(g, text=f"日志文件路径：", font=(FONT, 11, "bold"),
                bg=COLORS["bg_card"], fg=COLORS["fg"], anchor="w").pack(fill=tk.X, anchor=tk.W, padx=16, pady=(10, 4))
        tk.Label(g, text=get_log_path(), font=(FONT, 10),
                bg=COLORS["bg_card"], fg=COLORS["fg_muted"], wraplength=500, justify=tk.LEFT, anchor="w").pack(fill=tk.X, anchor=tk.W, padx=16)

        bf = tk.Frame(g, bg=COLORS["bg_card"])
        bf.pack(fill=tk.X, padx=16, pady=12)
        self._btn(bf, "🗑️ 清空日志文件", "danger", self._on_clear_log_file).pack(side=tk.LEFT, padx=5)
        self._btn(bf, "📂 打开日志目录", "normal",
                 lambda: os.startfile(os.path.dirname(get_log_path()))).pack(side=tk.LEFT, padx=5)
        self._btn(bf, "📋 复制日志路径", "normal",
                 lambda: self._copy_text(get_log_path())).pack(side=tk.LEFT, padx=5)

    def _copy_text(self, text):
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        log_success("已复制到剪贴板")

    def _build_mod_settings(self):
        g = self._group("📦 散文件MOD管理")
        tk.Label(g, text="检测并管理游戏目录中的散文件版创造模式（sim_common目录）",
                font=(FONT, 11), bg=COLORS["bg_card"], fg=COLORS["fg_muted"],
                wraplength=500, justify=tk.LEFT, anchor="w").pack(fill=tk.X, anchor=tk.W, padx=16, pady=10)

        self.mod_status_label = tk.Label(g, text="检测中...", font=(FONT, 12, "bold"),
                                        bg=COLORS["bg_card"], fg=COLORS["warning"], justify=tk.LEFT, anchor="w")
        self.mod_status_label.pack(fill=tk.X, anchor=tk.W, padx=16, pady=8)

        bf = tk.Frame(g, bg=COLORS["bg_card"])
        bf.pack(fill=tk.X, padx=16, pady=12)
        self._btn(bf, "🔄 检测MOD状态", "normal", self._check_mod).pack(side=tk.LEFT, padx=5)
        self._btn(bf, "📦 安装散文件MOD", "primary", self._install_mod).pack(side=tk.LEFT, padx=5)
        self._btn(bf, "🗑️ 卸载散文件MOD", "danger", self._uninstall_mod).pack(side=tk.LEFT, padx=5)

        self.root.after(100, self._check_mod)

    def _get_mod_path(self):
        game_path = self.config.get("game_path", DEFAULT_GAME_PATH)
        return os.path.join(game_path, SIM_COMMON_REL)

    def _check_mod(self):
        mod_path = self._get_mod_path()
        if os.path.exists(mod_path):
            files = os.listdir(mod_path)
            self.mod_status_label.config(text=f"⚠️ 已检测到散文件MOD（{len(files)}个文件）\n路径: {mod_path}",
                                        fg=COLORS["warning"], justify=tk.LEFT, anchor="w")
            log_warning(f"检测到散文件MOD: {mod_path} ({len(files)}个文件)")
        else:
            self.mod_status_label.config(text=f"✅ 未检测到散文件MOD\n路径: {mod_path}",
                                        fg=COLORS["success"], justify=tk.LEFT, anchor="w")
            log_info("未检测到散文件MOD")

    def _install_mod(self):
        src = filedialog.askdirectory(title="选择散文件MOD的 sim_common 源目录")
        if not src:
            return
        if os.path.basename(src) != "sim_common":
            messagebox.showwarning("提示", f"所选目录名不是 sim_common：{os.path.basename(src)}")
            return
        dest = self._get_mod_path()
        try:
            if os.path.exists(dest):
                shutil.rmtree(dest)
            shutil.copytree(src, dest)
            log_success(f"散文件MOD已安装到: {dest}")
            self._check_mod()
        except Exception as e:
            log_error(f"安装失败: {e}")

    def _uninstall_mod(self):
        mod_path = self._get_mod_path()
        if not os.path.exists(mod_path):
            log_warning("未检测到散文件MOD，无需卸载")
            return
        if not messagebox.askyesno("确认", f"确定要卸载散文件MOD吗？\n\n将删除: {mod_path}"):
            return
        try:
            shutil.rmtree(mod_path)
            log_success("散文件MOD已卸载")
            self._check_mod()
        except Exception as e:
            log_error(f"卸载失败: {e}")

    def _build_about(self):
        g = self._group("ℹ️ 关于")
        info = f"""平野孤鸿 全能修改器
版本：{VERSION}
游戏：平野孤鸿 (Ballads of Hongye)
Steam AppID：2656540

技术栈：
- Python + tkinter
- C DLL (Inline Hook)
- Lua 脚本执行

功能模块：
- 资源修改（8种资源+幸福度+知名度）
- 创造模式（鸿业满级/全建筑/无限资源/无限制升级）
- 高级工具（时间/天气/NPC/建造/城市/成就/天赋/灾害等）
- 一键全开作弊
- 存档管理（备份/恢复/清理）
- 热键管理
- MOD管理（散文件检测/安装/卸载）

游戏路径：{self.config.get("game_path", DEFAULT_GAME_PATH)}
"""
        tk.Label(g, text=info, font=(FONT, 11), bg=COLORS["bg_card"],
                fg=COLORS["fg"], justify=tk.LEFT, anchor="w").pack(fill=tk.X, anchor=tk.W, padx=16, pady=16)

    def _on_clear_log_file(self):
        if messagebox.askyesno("确认", "确定要清空日志文件吗？"):
            if clear_log_file():
                log_success("日志文件已清空")
                self._clear_log()
            else:
                log_error("清空日志失败")

    # ===== 占位页 =====
    def _build_placeholder(self):
        g = self._group("🔧 功能开发中")
        tk.Label(g, text="该功能开发中...", font=(FONT, 12), bg=COLORS["bg_card"],
                fg=COLORS["fg_muted"], justify=tk.CENTER).pack(pady=30)

    # ===== 辅助方法 =====
    def _group(self, title):
        g = tk.LabelFrame(self.content_inner, text=title, font=(FONT, 12, "bold"),
                         bg=COLORS["bg_card"], fg=COLORS["fg"], bd=1, relief=tk.SOLID,
                         highlightbackground=COLORS["border"], highlightthickness=1, padx=4, pady=8)
        g.pack(fill=tk.X, padx=20, pady=8)
        return g

    def _btn(self, parent, text, style="normal", command=None):
        if style == "primary":
            return tk.Button(parent, text=text, font=(FONT, 11, "bold"), bg=COLORS["accent"], fg="white",
                           bd=0, relief=tk.FLAT, cursor="hand2", activebackground=COLORS["accent_hover"],
                           activeforeground="white", padx=16, pady=7, command=command)
        elif style == "danger":
            return tk.Button(parent, text=text, font=(FONT, 11, "bold"), bg=COLORS["error"], fg="white",
                           bd=0, relief=tk.FLAT, cursor="hand2", activebackground="#e04646",
                           activeforeground="white", padx=16, pady=7, command=command)
        else:
            return tk.Button(parent, text=text, font=(FONT, 11), bg=COLORS["bg_card"], fg=COLORS["fg"],
                           bd=1, relief=tk.SOLID, cursor="hand2", activebackground=COLORS["bg_hover"],
                           activeforeground=COLORS["accent"], padx=14, pady=6, command=command)


# ============================================================
def main():
    root = tk.Tk()
    app = TrainerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
