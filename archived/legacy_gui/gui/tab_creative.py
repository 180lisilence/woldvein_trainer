"""
创造模式标签页 Mixin
功能：鸿业满级/全建筑解锁/无限资源/无限制升级，子选项独立开关
"""
import threading

import tkinter as tk
from tkinter import ttk, messagebox

from src.creative_mode import enable_creative_mode, disable_creative_mode, is_creative_mode_enabled, toggle_creative_mode, set_creative_options, diagnose_unlock_status
from src.game_status import get_status_provider
from src.config import save_config
from src.logger import log, log_error
from .diagnostic_panel import build_diagnostic_panel
from .scrollable import ScrollableFrame
from .widgets import T
from .theme import FONT_MONO_BOLD, FONT_SUB, FONT_BODY, FONT_TINY


class CreativeTabMixin:
    """创造模式标签页 Mixin"""

    def _build_creative_tab(self, parent):
        """创造模式标签页（卡片式网格布局）"""
        scroll = ScrollableFrame(parent)
        scroll.pack(fill=tk.BOTH, expand=True)
        tab = scroll.inner

        # ===== 顶部：总开关大卡片 =====
        switch_card = ttk.Frame(tab, style="Card.TFrame")
        switch_card.pack(fill=tk.X, padx=15, pady=15)

        switch_inner = ttk.Frame(switch_card, style="Card.TFrame")
        switch_inner.pack(fill=tk.X, padx=20, pady=15)

        title_col = ttk.Frame(switch_inner, style="Card.TFrame")
        title_col.pack(side=tk.LEFT, fill=tk.Y)

        ttk.Label(title_col, text="✨ 创造模式", style="Card.TLabel",
                  font=("微软雅黑", 16, "bold")).pack(anchor=tk.W)
        ttk.Label(title_col, text="开启后：鸿业满级 + 全建筑解锁 + 无限资源 + 升级无限制",
                  style="Card.TLabel", foreground=T("fg_muted")).pack(anchor=tk.W, pady=(5, 0))

        btn_col = ttk.Frame(switch_inner, style="Card.TFrame")
        btn_col.pack(side=tk.RIGHT)

        self.creative_btn = ttk.Button(btn_col, text="▶ 开启创造模式", style="Success.TButton",
                                        command=self.on_toggle_creative, width=18)
        self.creative_btn.pack()

        self.creative_status = ttk.Label(btn_col, text="状态：未开启", style="Warning.TLabel",
                                         font=FONT_BODY)
        self.creative_status.pack(pady=(8, 0))

        # ===== 中部：2列卡片网格 =====
        grid_frame = ttk.Frame(tab)
        grid_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 10))

        grid_frame.grid_columnconfigure(0, weight=1, uniform="crt_col")
        grid_frame.grid_columnconfigure(1, weight=1, uniform="crt_col")
        grid_frame.grid_rowconfigure(0, weight=1, uniform="crt_row")

        # ===== 左卡片：功能选项 =====
        options_card = ttk.Frame(grid_frame, style="Card.TFrame")
        options_card.grid(row=0, column=0, padx=6, pady=6, sticky="nsew")

        opt_header = ttk.Frame(options_card, style="Card.TFrame")
        opt_header.pack(fill=tk.X, padx=12, pady=(12, 4))
        ttk.Label(opt_header, text="⚙ 功能选项", style="Card.TLabel",
                  font=FONT_SUB).pack(side=tk.LEFT)
        # 全选/反选按钮
        ttk.Button(opt_header, text="全选", style="Small.TButton",
                   command=lambda: self._set_all_creative_opts(True)).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(opt_header, text="全不选", style="Small.TButton",
                   command=lambda: self._set_all_creative_opts(False)).pack(side=tk.RIGHT)
        ttk.Label(options_card, text="创造模式开启时全部生效，可独立勾选",
                  style="Card.TLabel", foreground=T("fg_muted"),
                  font=FONT_TINY).pack(anchor=tk.W, padx=12, pady=(0, 8))

        options_body = ttk.Frame(options_card, style="Card.TFrame")
        options_body.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))

        options = [
            ("鸿业满级", "max_boom", "鸿业等级直接设为14级（满级），解锁所有等级奖励"),
            ("全建筑解锁", "unlock_all_buildings", "所有建筑卡片解锁，UI只显示最高级建筑"),
            ("无限资源", "infinite_resources", "建造建筑消耗资源，每3秒自动重置（散件机制）"),
            ("升级无限制", "unlimited_upgrade", "建筑可升级到最高级，无等级/条件限制"),
        ]

        self.creative_vars = {}
        self._creative_opt_rows = {}
        for name, key, desc in options:
            # 用tk.Frame包裹以支持背景色变化
            opt_row = tk.Frame(options_body, bg=T("bg_card"))
            opt_row.pack(fill=tk.X, pady=2)

            var = tk.BooleanVar(value=self.config["creative_mode"].get(key, True))
            self.creative_vars[key] = var

            # Checkbutton绑定选中状态变化回调
            cb = ttk.Checkbutton(opt_row, text=name, variable=var,
                                  command=lambda k=key: self._on_creative_opt_change(k))
            cb.pack(side=tk.LEFT, anchor=tk.W, padx=(8, 0), pady=6)
            tk.Label(opt_row, text=desc, bg=T("bg_card"), fg=T("fg_muted"),
                     font=FONT_TINY, wraplength=200, justify=tk.LEFT).pack(
                side=tk.LEFT, padx=(10, 8), pady=6, fill=tk.X, expand=True)

            self._creative_opt_rows[key] = opt_row
            # 初始设置背景色
            self._on_creative_opt_change(key)

        # ===== 右卡片：实时状态 =====
        status_card = ttk.Frame(grid_frame, style="Card.TFrame")
        status_card.grid(row=0, column=1, padx=6, pady=6, sticky="nsew")

        ttk.Label(status_card, text="📊 游戏内实时状态", style="Card.TLabel",
                  font=FONT_SUB).pack(anchor=tk.W, padx=12, pady=(12, 4))
        ttk.Label(status_card, text="每 3 秒自动刷新",
                  style="Card.TLabel", foreground=T("fg_muted"),
                  font=FONT_TINY).pack(anchor=tk.W, padx=12, pady=(0, 8))

        status_body = ttk.Frame(status_card, style="Card.TFrame")
        status_body.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))

        # 第一行状态（Badge风格：带浅色背景的标签）
        row1 = ttk.Frame(status_body, style="Card.TFrame")
        row1.pack(fill=tk.X, pady=6)

        # 鸿业等级Badge
        boom_badge = tk.Frame(row1, bg=T("bg"), highlightthickness=1, highlightbackground=T("accent"))
        boom_badge.pack(side=tk.LEFT, padx=(0, 8))
        tk.Label(boom_badge, text=" 鸿业等级 ", bg=T("bg"), fg=T("accent"),
                 font=FONT_TINY).pack(side=tk.LEFT, pady=3)
        self.cs_boom_label = tk.Label(boom_badge, text="——", bg=T("bg"), fg=T("fg"),
                                       font=FONT_MONO_BOLD)
        self.cs_boom_label.pack(side=tk.LEFT, padx=(0, 8), pady=3)

        # 称号Badge
        title_badge = tk.Frame(row1, bg=T("bg"), highlightthickness=1, highlightbackground=T("warning"))
        title_badge.pack(side=tk.LEFT, padx=(0, 8))
        tk.Label(title_badge, text=" 称号 ", bg=T("bg"), fg=T("warning"),
                 font=FONT_TINY).pack(side=tk.LEFT, pady=3)
        self.cs_title_label = tk.Label(title_badge, text="——", bg=T("bg"), fg=T("fg"),
                                        font=FONT_TINY)
        self.cs_title_label.pack(side=tk.LEFT, padx=(0, 8), pady=3)

        # 建筑解锁Badge
        cards_badge = tk.Frame(row1, bg=T("bg"), highlightthickness=1, highlightbackground=T("success"))
        cards_badge.pack(side=tk.LEFT)
        tk.Label(cards_badge, text=" 建筑解锁 ", bg=T("bg"), fg=T("success"),
                 font=FONT_TINY).pack(side=tk.LEFT, pady=3)
        self.cs_cards_label = tk.Label(cards_badge, text="——", bg=T("bg"), fg=T("fg"),
                                        font=FONT_MONO_BOLD)
        self.cs_cards_label.pack(side=tk.LEFT, padx=(0, 8), pady=3)

        # 分隔线
        ttk.Separator(status_body, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)

        # 第二行状态（Badge风格）
        row2 = ttk.Frame(status_body, style="Card.TFrame")
        row2.pack(fill=tk.X, pady=6)

        # 时间速度Badge
        speed_badge = tk.Frame(row2, bg=T("bg"), highlightthickness=1, highlightbackground=T("accent"))
        speed_badge.pack(side=tk.LEFT, padx=(0, 8))
        tk.Label(speed_badge, text=" 时间速度 ", bg=T("bg"), fg=T("accent"),
                 font=FONT_TINY).pack(side=tk.LEFT, pady=3)
        self.cs_speed_label = tk.Label(speed_badge, text="——", bg=T("bg"), fg=T("fg"),
                                        font=FONT_MONO_BOLD)
        self.cs_speed_label.pack(side=tk.LEFT, padx=(0, 8), pady=3)

        # 季节Badge
        season_badge = tk.Frame(row2, bg=T("bg"), highlightthickness=1, highlightbackground=T("warning"))
        season_badge.pack(side=tk.LEFT, padx=(0, 8))
        tk.Label(season_badge, text=" 季节 ", bg=T("bg"), fg=T("warning"),
                 font=FONT_TINY).pack(side=tk.LEFT, pady=3)
        self.cs_season_label = tk.Label(season_badge, text="——", bg=T("bg"), fg=T("fg"),
                                         font=FONT_TINY)
        self.cs_season_label.pack(side=tk.LEFT, padx=(0, 8), pady=3)

        # 幸福度Badge
        happy_badge = tk.Frame(row2, bg=T("bg"), highlightthickness=1, highlightbackground=T("success"))
        happy_badge.pack(side=tk.LEFT)
        tk.Label(happy_badge, text=" 幸福度 ", bg=T("bg"), fg=T("success"),
                 font=FONT_TINY).pack(side=tk.LEFT, pady=3)
        self.cs_happy_label = tk.Label(happy_badge, text="——", bg=T("bg"), fg=T("fg"),
                                        font=FONT_MONO_BOLD)
        self.cs_happy_label.pack(side=tk.LEFT, padx=(0, 8), pady=3)

        # 状态提示
        self.cs_status_hint = ttk.Label(status_body, text="💡 进入游戏存档后自动开始刷新",
                                         style="Card.TLabel", foreground=T("fg_muted"),
                                         font=FONT_TINY)
        self.cs_status_hint.pack(anchor=tk.W, pady=(15, 0))

        # ===== 底部：诊断工具 =====
        self._creative_diag = build_diagnostic_panel(
            parent=tab,
            title="🔍 建筑解锁诊断",
            description="诊断当前游戏内建筑解锁状态，帮助定位解锁不完整的问题",
            button_text="运行诊断",
            button_style="Primary.TButton",
            diag_func=diagnose_unlock_status,
            check_injected=lambda: self.dll_injected,
            output_height=8,
            expand=True,
        )

        # 订阅游戏状态刷新（统一管理，避免多 tab 并发竞态）
        self._crt_status_provider = get_status_provider()
        self._crt_status_provider.subscribe("creative_tab", self._on_creative_status_update)

    def _update_creative_gui(self, enabled):
        """更新创造模式GUI状态（同步监控页创造模式显示）"""
        if enabled:
            self.creative_btn.config(text="■ 关闭创造模式", style="Danger.TButton")
            self.creative_status.config(text="状态：已开启", style="Success.TLabel")
            # 同步更新监控页创造模式标签（不覆盖游戏模式标签）
            if hasattr(self, 'mon_creative'):
                self.mon_creative.config(text="创造模式: 已开启（修改器）", style="Success.TLabel")
        else:
            self.creative_btn.config(text="▶ 开启创造模式", style="Success.TButton")
            self.creative_status.config(text="状态：未开启", style="Warning.TLabel")
            # 同步更新监控页创造模式标签
            if hasattr(self, 'mon_creative'):
                self.mon_creative.config(text="创造模式: 未开启", style="Card.TLabel")

    def _hotkey_toggle_creative(self):
        """热键切换创造模式（同步GUI）"""
        toggle_creative_mode()
        self.root.after(0, lambda: self._update_creative_gui(is_creative_mode_enabled()))

    def on_toggle_creative(self):
        """切换创造模式（异步完成后更新GUI）"""
        if not self.dll_injected:
            messagebox.showwarning("提示", "请先注入DLL。")
            return

        will_enable = not is_creative_mode_enabled()

        # 在主线程先收集 tkinter BooleanVar 值，避免跨线程读取
        opts_snapshot = {}
        if will_enable:
            for key, var in self.creative_vars.items():
                opts_snapshot[key] = var.get()

        def worker():
            try:
                if will_enable:
                    # 使用主线程已收集的快照
                    set_creative_options(opts_snapshot)
                    # 保存到配置
                    self.config["creative_mode"].update(opts_snapshot)
                    save_config(self.config)
                    enable_creative_mode()
                else:
                    disable_creative_mode()
                # 异步完成后在主线程更新GUI
                # 只依据游戏内真实状态更新GUI（关闭失败时仍显示"已开启"）
                self.root.after(0, lambda: self._update_creative_gui(is_creative_mode_enabled()))
            except Exception as e:
                log_error(f"切换创造模式异常: {e}")
                self.root.after(0, lambda: self._update_creative_gui(is_creative_mode_enabled()))

        threading.Thread(target=worker, daemon=True).start()
        log(f"正在{'开启' if will_enable else '关闭'}创造模式...")

    def _on_creative_status_update(self, status, success):
        """游戏状态更新回调（从 GameStatusProvider 推送）"""
        self.root.after(0, lambda: self._update_creative_status_display(status, success))

    def _update_creative_status_display(self, status, success):
        """在主线程更新创造模式页状态显示"""
        if not self.dll_injected or not success or not status:
            return

        # 鸿业等级
        boom = status.get("boom_level", "——")
        self.cs_boom_label.config(text=f"鸿业等级: {boom}")
        # 鸿业称号
        title = status.get("boom_title", "——")
        if title and title != "——":
            # 修复HTML解析Bug：去除<span class='...'>标签
            import re
            clean_title = re.sub(r"<[^>]+>", "", str(title))
            self.cs_title_label.config(text=f"称号: {clean_title}")
        # 建筑解锁
        card_count = status.get("card_count", 0)
        card_unlocked = status.get("card_unlocked", 0)
        if card_count > 0:
            self.cs_cards_label.config(text=f"建筑解锁: {card_unlocked}/{card_count}")
        # 时间速度
        speed = status.get("time_speed", None)
        if speed is not None:
            self.cs_speed_label.config(text=f"时间速度: {speed}x")
        # 季节
        season = status.get("season", None)
        if season is not None:
            season_map = {1: "春", 2: "夏", 3: "秋", 4: "冬"}
            s_name = season_map.get(season, f"未知({season})")
            self.cs_season_label.config(text=f"当前季节: {s_name}")
        # 幸福度
        happy = status.get("happiness", None)
        if happy is not None:
            self.cs_happy_label.config(text=f"幸福度: {happy}")

    def _set_all_creative_opts(self, value):
        """全选/全不选创造模式功能选项"""
        for key, var in self.creative_vars.items():
            var.set(value)
        # 更新所有行背景色
        for key in self.creative_vars:
            self._on_creative_opt_change(key)
        # 保存到配置
        opts = {k: v.get() for k, v in self.creative_vars.items()}
        self.config["creative_mode"].update(opts)
        from src.config import save_config
        save_config(self.config)

    def _on_creative_opt_change(self, key):
        """功能选项勾选状态变化：整行背景变色反馈"""
        if not hasattr(self, '_creative_opt_rows') or key not in self._creative_opt_rows:
            return
        row = self._creative_opt_rows[key]
        var = self.creative_vars[key]
        if var.get():
            # 选中：略亮背景
            row.config(bg=T("bg_selected"))
            for child in row.winfo_children():
                if isinstance(child, tk.Label):
                    child.config(bg=T("bg_selected"))
        else:
            # 未选中：默认背景
            row.config(bg=T("bg_card"))
            for child in row.winfo_children():
                if isinstance(child, tk.Label):
                    child.config(bg=T("bg_card"))
