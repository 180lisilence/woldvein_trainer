"""
游戏监控标签页 Mixin
功能：进程/内存/日志/崩溃检测，SDK日志黑名单过滤
"""
from datetime import datetime

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox

from src.game_monitor import game_monitor
from src.logger import log_error, log_warning
from .scrollable import ScrollableFrame
from .widgets import T
from .theme import FONT_MONO, FONT_TITLE, FONT_SUB, FONT_BOLD, FONT_TINY


class MonitorTabMixin:
    """游戏监控标签页 Mixin"""

    def _build_monitor_tab(self, parent):
        """游戏监控标签页（卡片式网格布局）"""
        scroll = ScrollableFrame(parent)
        scroll.pack(fill=tk.BOTH, expand=True)
        tab = scroll.inner

        # 顶部说明
        title_frame = ttk.Frame(tab)
        title_frame.pack(fill=tk.X, padx=15, pady=(15, 10))
        ttk.Label(title_frame, text="游戏运行监控",
                  font=FONT_TITLE, foreground=T("fg")).pack(side=tk.LEFT)
        self.monitor_status_label = ttk.Label(title_frame, text="● 运行中", style="Success.TLabel")
        self.monitor_status_label.pack(side=tk.RIGHT)

        # 卡片网格（2列 x 2行，占据主要空间）
        grid_frame = ttk.Frame(tab)
        grid_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 10))

        for col in range(2):
            grid_frame.grid_columnconfigure(col, weight=1, uniform="mon_col")
        for row in range(2):
            grid_frame.grid_rowconfigure(row, weight=1, uniform="mon_row")

        # ===== 卡片1：进程状态 =====
        proc_card = ttk.Frame(grid_frame, style="Card.TFrame")
        proc_card.grid(row=0, column=0, padx=6, pady=6, sticky="nsew")

        ttk.Label(proc_card, text="🎮 游戏进程", style="Card.TLabel",
                  font=FONT_SUB).pack(anchor=tk.W, padx=12, pady=(12, 4))

        proc_body = ttk.Frame(proc_card, style="Card.TFrame")
        proc_body.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))

        self.mon_proc_state = ttk.Label(proc_body, text="● 未运行", style="Warning.TLabel",
                                         font=FONT_BOLD)
        self.mon_proc_state.pack(anchor=tk.W, pady=(0, 6))

        info_grid = ttk.Frame(proc_body, style="Card.TFrame")
        info_grid.pack(fill=tk.X)
        info_grid.grid_columnconfigure(1, weight=1)

        # 进程数据：名称靠左（灰色），数值靠右（等宽字体+高亮色），形成整齐视觉边缘
        labels = [
            ("PID:", "mon_pid", "-", T("fg")),
            ("内存:", "mon_memory", "- MB", T("accent")),
            ("CPU:", "mon_cpu", "-%", T("warning")),
            ("时长:", "mon_elapsed", "-", T("fg")),
            ("模式:", "mon_mode", "-", T("success")),
        ]
        for i, (name, attr, default, color) in enumerate(labels):
            ttk.Label(info_grid, text=name, style="Card.TLabel",
                      foreground=T("fg_muted")).grid(row=i, column=0, sticky=tk.W, pady=3)
            setattr(self, attr, ttk.Label(info_grid, text=default, style="Card.TLabel",
                                           foreground=color, font=("Consolas", 10)))
            getattr(self, attr).grid(row=i, column=1, sticky=tk.E, padx=(8, 4), pady=3)

        # 创造模式状态
        self.mon_creative = ttk.Label(proc_body, text="创造模式: 未开启", style="Card.TLabel",
                                      foreground=T("warning"))
        self.mon_creative.pack(anchor=tk.W, pady=(8, 0))

        # ===== 卡片2：监控控制 =====
        ctrl_card = ttk.Frame(grid_frame, style="Card.TFrame")
        ctrl_card.grid(row=0, column=1, padx=6, pady=6, sticky="nsew")

        ttk.Label(ctrl_card, text="⚙ 监控设置", style="Card.TLabel",
                  font=FONT_SUB).pack(anchor=tk.W, padx=12, pady=(12, 4))

        ctrl_body = ttk.Frame(ctrl_card, style="Card.TFrame")
        ctrl_body.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))

        self.monitor_enabled_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(ctrl_body, text="启用实时监控",
                        variable=self.monitor_enabled_var,
                        command=self.on_toggle_monitor).pack(anchor=tk.W, pady=(0, 10))

        ttk.Label(ctrl_body, text="监控内容：", style="Card.TLabel",
                  foreground=T("fg_muted"), font=FONT_TINY).pack(anchor=tk.W, pady=(5, 3))

        features = [
            "✓ 进程状态实时检测",
            "✓ 内存/CPU 占用监控",
            "✓ 游戏日志实时读取",
            "✓ Lua 错误自动检测",
            "✓ 游戏崩溃自动分析",
        ]
        for f in features:
            ttk.Label(ctrl_body, text=f"  {f}", style="Card.TLabel",
                      font=FONT_TINY).pack(anchor=tk.W, pady=1)

        # ===== 卡片3：日志监控 =====
        log_card = ttk.Frame(grid_frame, style="Card.TFrame")
        log_card.grid(row=1, column=0, padx=6, pady=6, sticky="nsew")

        log_header = ttk.Frame(log_card, style="Card.TFrame")
        log_header.pack(fill=tk.X, padx=12, pady=(12, 4))
        ttk.Label(log_header, text="📋 日志监控", style="Card.TLabel",
                  font=FONT_SUB).pack(side=tk.LEFT)
        # 自动滚动复选框
        self.mon_auto_scroll = tk.BooleanVar(value=True)
        ttk.Checkbutton(log_header, text="自动滚动", variable=self.mon_auto_scroll,
                        style="Card.TCheckbutton").pack(side=tk.RIGHT, padx=(10, 0))
        self.mon_log_state = ttk.Label(log_header, text="暂无错误", style="Success.TLabel",
                                       font=FONT_TINY)
        self.mon_log_state.pack(side=tk.RIGHT)

        self.mon_log_text = scrolledtext.ScrolledText(log_card, bg=T("bg_surface"), fg=T("fg"),
                                                         font=FONT_MONO, borderwidth=0)
        self.mon_log_text.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))
        self.mon_log_text.configure(state=tk.DISABLED)

        # ===== 卡片4：存档状态 =====
        save_card = ttk.Frame(grid_frame, style="Card.TFrame")
        save_card.grid(row=1, column=1, padx=6, pady=6, sticky="nsew")

        save_header = ttk.Frame(save_card, style="Card.TFrame")
        save_header.pack(fill=tk.X, padx=12, pady=(12, 4))
        ttk.Label(save_header, text="💾 存档状态", style="Card.TLabel",
                  font=FONT_SUB).pack(side=tk.LEFT)
        ttk.Button(save_header, text="刷新", command=self.on_refresh_monitor_saves,
                   style="Small.TButton").pack(side=tk.RIGHT)

        save_cols = ("name", "size", "status")
        save_container = ttk.Frame(save_card, style="Card.TFrame")
        save_container.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))
        self.mon_save_tree = ttk.Treeview(save_container, columns=save_cols, show="headings", height=3)
        self.mon_save_tree.heading("name", text="存档名")
        self.mon_save_tree.heading("size", text="大小")
        self.mon_save_tree.heading("status", text="状态")
        self.mon_save_tree.column("name", width=140)
        self.mon_save_tree.column("size", width=60, anchor=tk.CENTER)
        self.mon_save_tree.column("status", width=60, anchor=tk.CENTER)
        self.mon_save_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        save_scroll = ttk.Scrollbar(save_container, orient=tk.VERTICAL, command=self.mon_save_tree.yview)
        save_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.mon_save_tree.configure(yscrollcommand=save_scroll.set)

        # ===== 底部：崩溃历史（跨2列） =====
        crash_frame = ttk.Frame(tab, style="Card.TFrame")
        crash_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))

        crash_header = ttk.Frame(crash_frame, style="Card.TFrame")
        crash_header.pack(fill=tk.X, padx=15, pady=(10, 5))
        ttk.Label(crash_header, text="💥 崩溃历史（自动分析崩溃原因）", style="Card.TLabel",
                  font=FONT_SUB).pack(side=tk.LEFT)
        ttk.Button(crash_header, text="📋 复制错误信息", style="Warning.TButton",
                   command=self._copy_crash_info).pack(side=tk.RIGHT, padx=5)

        self.mon_crash_text = scrolledtext.ScrolledText(crash_frame, height=5, bg=T("bg_surface"), fg=T("error"),
                                                           font=FONT_MONO, borderwidth=0)
        self.mon_crash_text.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 10))
        self.mon_crash_text.configure(state=tk.DISABLED)
        self.mon_crash_text.insert(tk.END, "暂无崩溃记录\n")
        self.mon_crash_text.configure(state=tk.DISABLED)

        # 设置监控回调
        game_monitor.set_callback("status_update", self._on_monitor_status)
        game_monitor.set_callback("game_crash", self._on_monitor_crash)
        game_monitor.set_callback("game_start", self._on_monitor_start)
        game_monitor.set_callback("waiting", self._on_monitor_waiting)

        # 启动监控
        game_monitor.start()
        # 初始刷新存档
        self.root.after(1000, self.on_refresh_monitor_saves)

    def _on_monitor_status(self, status):
        """监控状态更新回调"""
        self.root.after(0, lambda: self._update_monitor_status(status))

    def _update_monitor_status(self, status):
        """更新监控状态显示"""
        if status.get("running"):
            self.mon_proc_state.config(text="● 运行中", style="Success.TLabel")
            self.mon_pid.config(text=f"{status.get('pid', '-')}")
            self.mon_memory.config(text=f"{status.get('memory_mb', 0):.0f} MB")
            self.mon_cpu.config(text=f"{status.get('cpu_percent', 0):.1f}%")
            elapsed = status.get("elapsed", 0)
            hours = int(elapsed // 3600)
            minutes = int((elapsed % 3600) // 60)
            secs = int(elapsed % 60)
            if hours > 0:
                self.mon_elapsed.config(text=f"{hours}时{minutes}分{secs}秒")
            elif minutes > 0:
                self.mon_elapsed.config(text=f"{minutes}分{secs}秒")
            else:
                self.mon_elapsed.config(text=f"{secs}秒")
            self.mon_mode.config(text=f"{status.get('mode', '-')}")

            # 日志错误
            errors = status.get("lua_errors", [])
            if errors:
                self.mon_log_state.config(text=f"⚠ {len(errors)}条错误", style="Warning.TLabel")
                self.mon_log_text.configure(state=tk.NORMAL)
                self.mon_log_text.delete("1.0", tk.END)
                for err in errors[-5:]:
                    self.mon_log_text.insert(tk.END, err + "\n")
                if self.mon_auto_scroll.get():
                    self.mon_log_text.see(tk.END)
                self.mon_log_text.configure(state=tk.DISABLED)
            else:
                latest = status.get("latest_log", "")
                if latest:
                    self.mon_log_state.config(text="运行正常", style="Success.TLabel")
                    self.mon_log_text.configure(state=tk.NORMAL)
                    self.mon_log_text.delete("1.0", tk.END)
                    self.mon_log_text.insert(tk.END, latest + "\n")
                    if self.mon_auto_scroll.get():
                        self.mon_log_text.see(tk.END)
                    self.mon_log_text.configure(state=tk.DISABLED)
        else:
            self.mon_proc_state.config(text="● 未运行", style="Warning.TLabel")
            self.mon_pid.config(text="-")
            self.mon_memory.config(text="- MB")
            self.mon_cpu.config(text="-%")
            self.mon_elapsed.config(text="-")
            # 游戏未运行时，创造模式状态重置
            self.mon_creative.config(text="创造模式: 未开启", style="Card.TLabel")

    def _on_monitor_crash(self, crash_info):
        """监控崩溃回调"""
        self.root.after(0, lambda: self._update_monitor_crash(crash_info))

    def _update_monitor_crash(self, crash_info):
        """更新崩溃显示"""
        self.mon_crash_text.configure(state=tk.NORMAL)
        self.mon_crash_text.delete("1.0", tk.END)

        crash_time = crash_info.get("time", datetime.now())
        self.mon_crash_text.insert(tk.END, f"【崩溃时间】{crash_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        self.mon_crash_text.insert(tk.END, f"【崩溃PID】{crash_info.get('pid', '-')}\n")

        phase = crash_info.get("stack_analysis", {}).get("crash_phase", "")
        if phase:
            self.mon_crash_text.insert(tk.END, f"【崩溃阶段】{phase}\n")

        self.mon_crash_text.insert(tk.END, f"【崩溃原因】{crash_info.get('reason', '未知')[:200]}\n\n")

        stacktrace = crash_info.get("stacktrace", [])
        if stacktrace:
            self.mon_crash_text.insert(tk.END, "【Lua调用栈】\n")
            for i, frame in enumerate(stacktrace[-5:]):
                self.mon_crash_text.insert(tk.END, f"  {i+1}. {frame.strip()[:120]}\n")
            self.mon_crash_text.insert(tk.END, "\n")

        suggestions = crash_info.get("suggestions", [])
        if suggestions:
            self.mon_crash_text.insert(tk.END, "【建议操作】\n")
            for i, sug in enumerate(suggestions):
                self.mon_crash_text.insert(tk.END, f"  {i+1}. {sug}\n")

        self.mon_crash_text.configure(state=tk.DISABLED)
        log_warning(f"检测到游戏崩溃: {crash_info.get('reason', '未知')[:80]}")

    def _on_monitor_start(self, data):
        """游戏启动回调"""
        self.root.after(0, lambda: self.mon_proc_state.config(text="● 运行中", style="Success.TLabel"))

    def _on_monitor_waiting(self, data):
        """等待游戏启动回调"""
        self.root.after(0, lambda: self.mon_proc_state.config(text="● 等待中...", style="Warning.TLabel"))

    def on_toggle_monitor(self):
        """切换监控开关"""
        if self.monitor_enabled_var.get():
            game_monitor.start()
            self.monitor_status_label.config(text="● 运行中", style="Success.TLabel")
        else:
            game_monitor.stop()
            self.monitor_status_label.config(text="● 已停止", style="Warning.TLabel")

    def on_refresh_monitor_saves(self):
        """刷新监控存档列表"""
        saves = game_monitor.get_save_files()
        self.mon_save_tree.delete(*self.mon_save_tree.get_children())
        for save in saves[:5]:
            self.mon_save_tree.insert("", tk.END, values=(
                save["name"][:40],
                f"{save['size_kb']:.0f} KB",
                save["status"]
            ))

    def _copy_crash_info(self):
        """复制崩溃历史信息到剪贴板"""
        try:
            self.mon_crash_text.configure(state=tk.NORMAL)
            text = self.mon_crash_text.get("1.0", tk.END)
            self.mon_crash_text.configure(state=tk.DISABLED)
            if text and text.strip() and text.strip() != "暂无崩溃记录":
                self._copy_to_clipboard(text)
                messagebox.showinfo("复制成功", "崩溃历史信息已复制到剪贴板。")
            else:
                messagebox.showinfo("提示", "暂无崩溃历史信息可复制。")
        except Exception as e:
            log_error(f"复制崩溃信息失败: {e}")
