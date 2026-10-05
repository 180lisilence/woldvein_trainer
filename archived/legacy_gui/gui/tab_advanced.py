"""
高级工具标签页 Mixin
功能：NPC管理/时间天气/建造升级/SimWorld操作/品阶提升/地块解锁/谋士升级/Steam成就/恢复原版
v0.3 新增：品阶逐级提升、全地块解锁、谋士升满级、Steam全成就、恢复原版按钮组
"""
import threading

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox

from src import advanced_tools
from src.logger import log, log_error
from .diagnostic_panel import attach_diag_to_button
from .scrollable import ScrollableFrame
from .theme import FONT_BOLD, FONT_MONO, FONT_SUB, FONT_TINY, ThemeManager
from .widgets import T


class AdvancedTabMixin:
    """高级工具标签页 Mixin"""

    def _create_collapsible(self, parent, title, default_open=True):
        """创建可折叠面板（Accordion）

        返回 (header_frame, content_frame)，调用方将内容放入content_frame。
        点击标题可展开/折叠。
        使用 tk.Frame + 深色背景，避免 ttk 默认白色边框。
        """
        # 容器：深色背景，无边框
        container = tk.Frame(parent, bg=T("bg_card"), highlightthickness=1,
                             highlightbackground=T("bg_elevated"), highlightcolor=T("bg_elevated"))
        container.pack(fill=tk.X, padx=15, pady=(0, 8))

        # 标题栏（可点击）：略深背景区分
        header = tk.Frame(container, bg=T("bg_elevated"))
        header.pack(fill=tk.X)
        header.bind("<Button-1>", lambda e: self._toggle_collapsible(container))

        arrow = "▼" if default_open else "▶"
        self._collapsible_arrows = getattr(self, '_collapsible_arrows', {})
        arrow_label = tk.Label(header, text=arrow, bg=T("bg_elevated"), fg=T("fg"),
                               font=FONT_BOLD, width=3)
        arrow_label.pack(side=tk.LEFT, padx=(10, 5), pady=8)
        arrow_label.bind("<Button-1>", lambda e: self._toggle_collapsible(container))

        title_label = tk.Label(header, text=title, bg=T("bg_elevated"), fg=T("fg"),
                               font=FONT_SUB)
        title_label.pack(side=tk.LEFT, pady=8)
        title_label.bind("<Button-1>", lambda e: self._toggle_collapsible(container))

        # 内容区：与容器同色背景
        content_frame = tk.Frame(container, bg=T("bg_card"))
        if default_open:
            content_frame.pack(fill=tk.X, padx=8, pady=(8, 8))
        else:
            content_frame.pack_forget()

        # 保存引用
        self._collapsible_content = getattr(self, '_collapsible_content', {})
        self._collapsible_content[id(container)] = (content_frame, arrow_label)
        return container, content_frame

    def _toggle_collapsible(self, container):
        """切换折叠面板的展开/折叠状态"""
        content_frame, arrow_label = self._collapsible_content[id(container)]
        if content_frame.winfo_ismapped():
            content_frame.pack_forget()
            arrow_label.config(text="▶")
        else:
            content_frame.pack(fill=tk.X, padx=8, pady=(8, 8))
            arrow_label.config(text="▼")

    def _build_advanced_tab(self, parent, use_scroll=True):
        """高级工具标签页"""
        tab = parent
        if use_scroll:
            scroll = ScrollableFrame(tab)
            scroll.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
            content_frame = content_frame
        else:
            content_frame = tab

        # === 时间/天气控制（折叠面板，默认展开）===
        time_container, time_frame = self._create_collapsible(content_frame, "时间/天气控制", default_open=True)
        time_row = tk.Frame(time_frame, bg=T("bg_card"))
        time_row.pack(fill=tk.X, padx=4, pady=(0, 4))

        # 教室座位式网格布局：每行5个按钮
        _time_btns = [
            ("获取时间", "Primary.TButton", lambda: self._run_async(self._adv_get_time)),
            ("暂停(0x)", "Warning.TButton", lambda: self._run_async(self._adv_set_time_speed, 0)),
            ("1x", "Primary.TButton", lambda: self._run_async(self._adv_set_time_speed, 1)),
            ("2x", "Primary.TButton", lambda: self._run_async(self._adv_set_time_speed, 2)),
            ("3x", "Primary.TButton", lambda: self._run_async(self._adv_set_time_speed, 3)),
            ("4x", "Primary.TButton", lambda: self._run_async(self._adv_set_time_speed, 4)),
            ("↩ 恢复速度", "Restore.TButton", lambda: self._run_async(advanced_tools.restore_time_speed)),
            ("🔍 速度状态", "Warning.TButton", lambda: self._run_async(self._adv_time_speed_status)),
            ("📏 实测倍率", "Warning.TButton", lambda: self._run_async(self._adv_measure_time_speed)),
        ]
        for _i, (_text, _style, _cmd) in enumerate(_time_btns):
            _r, _c = divmod(_i, 5)
            ttk.Button(time_row, text=_text, style=_style, command=_cmd, width=12).grid(row=_r, column=_c, padx=4, pady=4, sticky="w")

        season_row = tk.Frame(time_frame, bg=T("bg_card"))
        season_row.pack(fill=tk.X, padx=4, pady=(0, 4))

        ttk.Button(season_row, text="春", style="Success.TButton",
                   command=lambda: self._run_async(self._adv_set_season, 1)).pack(side=tk.LEFT, padx=4)
        ttk.Button(season_row, text="夏", style="Success.TButton",
                   command=lambda: self._run_async(self._adv_set_season, 2)).pack(side=tk.LEFT, padx=4)
        ttk.Button(season_row, text="秋", style="Success.TButton",
                   command=lambda: self._run_async(self._adv_set_season, 3)).pack(side=tk.LEFT, padx=4)
        ttk.Button(season_row, text="冬", style="Success.TButton",
                   command=lambda: self._run_async(self._adv_set_season, 4)).pack(side=tk.LEFT, padx=4)
        ttk.Separator(season_row, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=8)
        ttk.Button(season_row, text="跳过1天", style="Primary.TButton",
                   command=lambda: self._run_async(self._adv_skip_days, 1)).pack(side=tk.LEFT, padx=4)
        ttk.Button(season_row, text="跳过7天", style="Primary.TButton",
                   command=lambda: self._run_async(self._adv_skip_days, 7)).pack(side=tk.LEFT, padx=4)
        ttk.Button(season_row, text="跳过1月", style="Primary.TButton",
                   command=lambda: self._run_async(self._adv_skip_months, 1)).pack(side=tk.LEFT, padx=4)
        ttk.Button(season_row, text="跳过3月", style="Primary.TButton",
                   command=lambda: self._run_async(self._adv_skip_months, 3)).pack(side=tk.LEFT, padx=4)
        ttk.Separator(season_row, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=8)
        self._time_diag_btn = ttk.Button(season_row, text="🔍 时间诊断", style="Warning.TButton")
        self._time_diag_btn.pack(side=tk.LEFT, padx=4)
        # v0.3 新增：恢复季节
        ttk.Button(season_row, text="↩ 恢复季节", style="Restore.TButton",
                   command=lambda: self._run_async(advanced_tools.restore_season)).pack(side=tk.LEFT, padx=4)

        # === 城市品阶（折叠面板，默认展开）===
        boom_container, boom_frame = self._create_collapsible(content_frame, "城市品阶", default_open=True)
        boom_row = tk.Frame(boom_frame, bg=T("bg_card"))
        boom_row.pack(fill=tk.X, padx=4, pady=(0, 4))

        # 「逐级晋升」= setBoom + BoomLevelChange + UI2S_BoomUpgradeCallback（发放该级全部解锁项）
        self._boom_up_btn = ttk.Button(boom_row, text="⬆ 逐级晋升（含解锁）", style="Success.TButton",
                   command=lambda: self._adv_with_cooldown(self._boom_up_btn, advanced_tools.boom_upgrade_step, "逐级晋升"))
        self._boom_up_btn.pack(side=tk.LEFT, padx=4)
        self._boom_max_btn = ttk.Button(boom_row, text="⏩ 晋升到顶级", style="Success.TButton",
                   command=lambda: self._adv_with_cooldown(self._boom_max_btn, advanced_tools.boom_upgrade_to_max, "晋升到顶级"))
        self._boom_max_btn.pack(side=tk.LEFT, padx=4)
        ttk.Button(boom_row, text="当前品阶", style="Primary.TButton",
                   command=lambda: self._run_async(self._adv_boom_current)).pack(side=tk.LEFT, padx=4)
        ttk.Button(boom_row, text="🔍 品阶诊断", style="Warning.TButton",
                   command=lambda: self._run_async(self._adv_boom_diagnose)).pack(side=tk.LEFT, padx=4)

        # === 任务（解锁 / 完成）===
        task_container, task_frame = self._create_collapsible(content_frame, "任务（解锁 / 完成）", default_open=True)
        task_row = tk.Frame(task_frame, bg=T("bg_card"))
        task_row.pack(fill=tk.X, padx=4, pady=(0, 4))
        ttk.Button(task_row, text="🔍 探查", style="Warning.TButton",
                   command=lambda: self._run_async(self._adv_task_probe)).pack(side=tk.LEFT, padx=4)
        self._task_unlock_btn = ttk.Button(task_row, text="🔓 激活全部任务", style="Success.TButton",
                   command=lambda: self._adv_with_cooldown(self._task_unlock_btn, advanced_tools.unlock_all_tasks, "激活全部任务"))
        self._task_unlock_btn.pack(side=tk.LEFT, padx=4)
        self._task_finish_btn = ttk.Button(task_row, text="✅ 完成全部任务", style="Success.TButton",
                   command=lambda: self._adv_with_cooldown(self._task_finish_btn, advanced_tools.finish_all_tasks, "完成全部任务"))
        self._task_finish_btn.pack(side=tk.LEFT, padx=4)
        # 直接改数据（unlockPre + status + 分桶），不依赖 UnlockPrecondition/FinishAllTask 的内部流程
        self._task_dunlock_btn = ttk.Button(task_row, text="🔧 改数据解锁", style="Success.TButton",
                   command=lambda: self._adv_with_cooldown(self._task_dunlock_btn, advanced_tools.task_data_unlock, "改数据解锁"))
        self._task_dunlock_btn.pack(side=tk.LEFT, padx=4)
        self._task_dfinish_btn = ttk.Button(task_row, text="🔧 改数据完成", style="Success.TButton",
                   command=lambda: self._adv_with_cooldown(self._task_dfinish_btn, advanced_tools.task_data_finish, "改数据完成"))
        self._task_dfinish_btn.pack(side=tk.LEFT, padx=4)
        ttk.Label(task_row, text="品阶与任务无自动绑定；「改数据」= 直接把任务数据写成已满足（unlockPre/status/分桶），不依赖游戏内部流程",
                  style="Card.TLabel", foreground=T("fg_muted"), font=FONT_TINY).pack(side=tk.LEFT, padx=8)

        # === 游戏内面板（ImGui，引擎渲染，不卡）===
        panel_container, panel_frame = self._create_collapsible(content_frame, "游戏内面板（ImGui）", default_open=True)
        panel_row = tk.Frame(panel_frame, bg=T("bg_card"))
        panel_row.pack(fill=tk.X, padx=4, pady=(0, 4))
        self._ingame_on_btn = ttk.Button(panel_row, text="🎮 注入游戏内面板", style="Success.TButton",
                   command=lambda: self._adv_with_cooldown(self._ingame_on_btn, advanced_tools.install_ingame_panel, "注入面板"))
        self._ingame_on_btn.pack(side=tk.LEFT, padx=4)
        self._ingame_off_btn = ttk.Button(panel_row, text="🛑 移除面板", style="Restore.TButton",
                   command=lambda: self._adv_with_cooldown(self._ingame_off_btn, advanced_tools.remove_ingame_panel, "移除面板"))
        self._ingame_off_btn.pack(side=tk.LEFT, padx=4)
        ttk.Button(panel_row, text="🔍 状态", style="Warning.TButton",
                   command=lambda: self._run_async(self._adv_ingame_panel_status)).pack(side=tk.LEFT, padx=4)
        ttk.Label(panel_row, text="在游戏画面内用 ImGui 画可折叠面板（引擎渲染，不开外部窗口 → 不卡）；中文为 UTF-8 直传，折叠头默认展开。若仍异常请先「移除面板」再重新「注入」",
                  style="Card.TLabel", foreground=T("fg_muted"), font=FONT_TINY).pack(side=tk.LEFT, padx=8)

        # === NPC管理（折叠面板，默认展开）===
        npc_container, npc_frame = self._create_collapsible(content_frame, "NPC管理", default_open=True)
        npc_row = tk.Frame(npc_frame, bg=T("bg_card"))
        npc_row.pack(fill=tk.X, padx=4, pady=(0, 4))

        ttk.Button(npc_row, text="列出NPC", style="Primary.TButton",
                   command=lambda: self._run_async(self._adv_list_npcs)).pack(side=tk.LEFT, padx=4)
        ttk.Button(npc_row, text="添加名士", style="Success.TButton",
                   command=lambda: self._run_async(lambda: advanced_tools.add_npc("celebrity"))).pack(side=tk.LEFT, padx=4)
        ttk.Button(npc_row, text="添加幕僚", style="Success.TButton",
                   command=lambda: self._run_async(lambda: advanced_tools.add_npc("adviser"))).pack(side=tk.LEFT, padx=4)
        ttk.Button(npc_row, text="清除所有NPC", style="Danger.TButton",
                   command=lambda: self._run_async(advanced_tools.remove_all_npcs)).pack(side=tk.LEFT, padx=4)

        # === 谋士管理（折叠面板，默认折叠）===
        advisor_container, advisor_frame = self._create_collapsible(content_frame, "谋士管理（忠诚/能力/薪资）", default_open=False)
        advisor_row = tk.Frame(advisor_frame, bg=T("bg_card"))
        advisor_row.pack(fill=tk.X, padx=4, pady=(0, 4))

        self._advisor_btn = ttk.Button(advisor_row, text="⬆ 谋士升满级", style="Success.TButton",
                   command=lambda: self._adv_with_cooldown(self._advisor_btn, advanced_tools.max_all_advisors, "谋士升满级"))
        self._advisor_btn.pack(side=tk.LEFT, padx=4)
        ttk.Button(advisor_row, text="🔍 谋士探查", style="Warning.TButton",
                   command=lambda: self._run_async(self._adv_probe_advisors)).pack(side=tk.LEFT, padx=4)

        # === 建造/升级控制（折叠面板，默认展开）===
        build_container, build_frame = self._create_collapsible(content_frame, "建造/升级控制", default_open=True)
        build_row = tk.Frame(build_frame, bg=T("bg_card"))
        build_row.pack(fill=tk.X, padx=4, pady=(0, 4))

        ttk.Button(build_row, text="列出建筑", style="Primary.TButton",
                   command=lambda: self._run_async(self._adv_list_buildings)).pack(side=tk.LEFT, padx=4)
        self._adv_upgrade_btn = ttk.Button(build_row, text="升级全部", style="Success.TButton",
                   command=lambda: self._adv_with_cooldown(self._adv_upgrade_btn, advanced_tools.upgrade_all_buildings, "升级全部"))
        self._adv_upgrade_btn.pack(side=tk.LEFT, padx=4)
        self._adv_finish_btn = ttk.Button(build_row, text="立即完成", style="Success.TButton",
                   command=lambda: self._adv_with_cooldown(self._adv_finish_btn, advanced_tools.finish_all_buildings, "立即完成"))
        self._adv_finish_btn.pack(side=tk.LEFT, padx=4)
        ttk.Button(build_row, text="重算资源", style="Warning.TButton",
                   command=lambda: self._run_async(advanced_tools.recalc_resources)).pack(side=tk.LEFT, padx=4)
        ttk.Button(build_row, text="人口状态", style="Primary.TButton",
                   command=lambda: self._run_async(self._adv_population_status)).pack(side=tk.LEFT, padx=4)

        # === 地块管理（折叠面板，默认折叠）===
        plot_container, plot_frame = self._create_collapsible(content_frame, "地块管理", default_open=False)
        plot_row = tk.Frame(plot_frame, bg=T("bg_card"))
        plot_row.pack(fill=tk.X, padx=4, pady=(0, 4))

        self._plot_btn = ttk.Button(plot_row, text="🔓 全地块解锁", style="Success.TButton",
                   command=lambda: self._adv_with_cooldown(self._plot_btn, advanced_tools.unlock_all_plots, "全地块解锁"))
        self._plot_btn.pack(side=tk.LEFT, padx=4)
        ttk.Button(plot_row, text="🔍 地块探查", style="Warning.TButton",
                   command=lambda: self._run_async(self._adv_probe_plots)).pack(side=tk.LEFT, padx=4)

        # === Steam 成就（折叠面板，默认折叠）===
        ach_container, ach_frame = self._create_collapsible(content_frame, "Steam 成就", default_open=False)
        ach_row = tk.Frame(ach_frame, bg=T("bg_card"))
        ach_row.pack(fill=tk.X, padx=4, pady=(0, 4))

        self._ach_btn = ttk.Button(ach_row, text="🏆 全成就解锁", style="Success.TButton",
                   command=lambda: self._adv_with_cooldown(self._ach_btn, advanced_tools.unlock_all_steam_achievements, "全成就解锁"))
        self._ach_btn.pack(side=tk.LEFT, padx=4)
        ttk.Button(ach_row, text="🔍 成就探查", style="Warning.TButton",
                   command=lambda: self._run_async(self._adv_probe_ach)).pack(side=tk.LEFT, padx=4)
        self._ach_challenge_btn = ttk.Button(ach_row, text="🎯 月落峡挑战成就", style="Primary.TButton",
                   command=lambda: self._adv_with_cooldown(self._ach_challenge_btn, advanced_tools.unlock_block_challenge_achievements, "月落峡挑战成就"))
        self._ach_challenge_btn.pack(side=tk.LEFT, padx=4)

        # === SimWorld 控制（折叠面板，默认折叠）===
        sim_container, sim_frame = self._create_collapsible(content_frame, "SimWorld 控制", default_open=False)
        sim_row = tk.Frame(sim_frame, bg=T("bg_card"))
        sim_row.pack(fill=tk.X, padx=4, pady=(0, 4))

        ttk.Button(sim_row, text="世界状态", style="Primary.TButton",
                   command=lambda: self._run_async(self._adv_simworld_status)).pack(side=tk.LEFT, padx=4)
        ttk.Button(sim_row, text="暂停游戏", style="Danger.TButton",
                   command=lambda: self._run_async(self._adv_pause_game)).pack(side=tk.LEFT, padx=4)
        ttk.Button(sim_row, text="继续游戏", style="Success.TButton",
                   command=lambda: self._run_async(self._adv_resume_game)).pack(side=tk.LEFT, padx=4)
        # v0.3 新增：恢复游戏运行
        ttk.Button(sim_row, text="↩ 恢复运行", style="Restore.TButton",
                   command=lambda: self._run_async(advanced_tools.restore_game_speed)).pack(side=tk.LEFT, padx=4)

        # === 输出区域（优化：清空按钮 + 占位提示）===
        out_frame = ttk.Frame(tab, style="Card.TFrame")
        out_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))

        out_header = ttk.Frame(out_frame, style="Card.TFrame")
        out_header.pack(fill=tk.X, padx=15, pady=(10, 5))
        ttk.Label(out_header, text="执行输出", style="Card.TLabel",
                  font=FONT_SUB).pack(side=tk.LEFT)
        ttk.Button(out_header, text="清空", style="Small.TButton",
                   command=self._clear_adv_output).pack(side=tk.RIGHT)

        # 输出区颜色从主题获取
        log_bg, log_fg, _ = ThemeManager.get_log_colors()
        self.adv_output_text = scrolledtext.ScrolledText(out_frame, height=6, bg=log_bg, fg=log_fg,
                                                          font=FONT_MONO, borderwidth=0)
        self.adv_output_text.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 10))
        # 占位提示
        self.adv_output_text.insert(tk.END, "暂无执行日志，点击上方按钮执行操作后将显示结果...")
        self.adv_output_text.configure(state=tk.DISABLED)
        self._adv_output_has_content = False

        # 绑定时间诊断按钮（结果同时写入高级工具输出区和主日志）
        self._time_diag_binding = attach_diag_to_button(
            button=self._time_diag_btn,
            diag_func=advanced_tools.diagnose_time_system,
            on_result=lambda r: (
                self._adv_append_output(f"[时间诊断]\n{r}"),
                log(f"[时间诊断]\n{r}"),
            ),
            check_injected=lambda: self.dll_injected,
            busy_text="诊断中...",
        )

    def _adv_append_output(self, text):
        """追加输出到高级工具输出区（首次写入时清除占位提示）"""
        self.adv_output_text.configure(state=tk.NORMAL)
        if not getattr(self, '_adv_output_has_content', False):
            self.adv_output_text.delete("1.0", tk.END)
            self._adv_output_has_content = True
        self.adv_output_text.insert(tk.END, text + "\n")
        self.adv_output_text.see(tk.END)
        self.adv_output_text.configure(state=tk.DISABLED)

    def _clear_adv_output(self):
        """清空高级工具输出区"""
        self.adv_output_text.configure(state=tk.NORMAL)
        self.adv_output_text.delete("1.0", tk.END)
        self.adv_output_text.insert(tk.END, "暂无执行日志，点击上方按钮执行操作后将显示结果...")
        self.adv_output_text.configure(state=tk.DISABLED)
        self._adv_output_has_content = False

    def _adv_get_time(self):
        """获取时间状态"""
        success, result = advanced_tools.get_time_status()
        self.root.after(0, lambda: self._adv_append_output(f"[时间] {result}"))

    def _adv_set_time_speed(self, speed):
        """设置时间速度，并把结果写入输出区"""
        self._current_time_speed = speed
        success, result = advanced_tools.set_time_speed(speed)
        self.root.after(0, lambda: self._adv_append_output(f"[时间速度] {result}"))

    def _adv_set_season(self, season):
        """设置季节，并把结果写入输出区"""
        success, result = advanced_tools.set_season(season)
        self.root.after(0, lambda: self._adv_append_output(f"[季节] {result}"))

    def _adv_skip_days(self, days):
        """跳过指定天数"""
        success, result = advanced_tools.skip_days(days)
        self.root.after(0, lambda: self._adv_append_output(f"[跳过天数] {result}"))

    def _adv_skip_months(self, months):
        """跳过指定月数"""
        success, result = advanced_tools.skip_months(months)
        self.root.after(0, lambda: self._adv_append_output(f"[跳过月数] {result}"))

    # === v0.3 新增方法 ===

    def _adv_boom_current(self):
        """查看当前城市品阶"""
        success, result = advanced_tools.boom_get_current()
        self.root.after(0, lambda: self._adv_append_output(f"[品阶] {result}"))

    def _adv_time_speed_status(self):
        """时间速度状态（诊断：基准/当前/倍率）"""
        success, result = advanced_tools.get_time_speed_status()
        self._report_probe("高级-速度状态", result)
        self.root.after(0, lambda: self._adv_append_output(f"[速度状态]\n{result}"))

    def _adv_measure_time_speed(self):
        """实测游戏时间流速（阻塞约 2 秒，异步执行）"""
        success, result = advanced_tools.measure_time_speed(2.0)
        self._report_probe("高级-时间流速实测", result)
        self.root.after(0, lambda: self._adv_append_output(f"[时间流速实测]\n{result}"))

    def _adv_ingame_panel_status(self):
        """游戏内面板状态"""
        success, result = advanced_tools.get_ingame_panel_status()
        self._report_probe("高级-游戏内面板", result)
        self.root.after(0, lambda: self._adv_append_output(f"[游戏内面板]\n{result}"))

    def _adv_task_probe(self):
        """任务状态探查"""
        success, result = advanced_tools.probe_tasks()
        self._report_probe("高级-任务", result)
        self.root.after(0, lambda: self._adv_append_output(f"[任务探查]\n{result}"))

    def _adv_boom_diagnose(self):
        """品阶诊断"""
        success, result = advanced_tools.diagnose_boom()
        self._report_probe("高级-品阶诊断", result)
        self.root.after(0, lambda: self._adv_append_output(f"[品阶诊断]\n{result}"))

    def _adv_probe_plots(self):
        """地块探查"""
        success, result = advanced_tools.probe_plots()
        self._report_probe("高级-地块", result)
        self.root.after(0, lambda: self._adv_append_output(f"[地块探查]\n{result}"))

    def _adv_probe_advisors(self):
        """谋士探查"""
        success, result = advanced_tools.probe_advisors()
        self._report_probe("高级-谋士", result)
        self.root.after(0, lambda: self._adv_append_output(f"[谋士探查]\n{result}"))

    def _adv_probe_ach(self):
        """Steam成就探查"""
        success, result = advanced_tools.probe_steam_achievements()
        self._report_probe("高级-Steam成就", result)
        self.root.after(0, lambda: self._adv_append_output(f"[成就探查]\n{result}"))

    def _adv_list_npcs(self):
        """列出NPC"""
        success, result = advanced_tools.get_npc_list()
        self.root.after(0, lambda: self._adv_append_output(f"[NPC] {result}"))

    def _adv_with_cooldown(self, btn, func, name):
        """高级工具按钮带冷却（3秒），防止频繁点击导致游戏失控

        每个按钮独立冷却，互不影响。
        """
        if not self.dll_injected:
            messagebox.showwarning("提示", "请先注入DLL。")
            return
        try:
            if not btn or not btn.winfo_exists():
                return
            original_text = btn.cget("text")
            btn.config(state=tk.DISABLED, text=f"{name} (冷却中...)")
        except tk.TclError:
            return

        def worker():
            try:
                success, result = func()
                self.root.after(0, lambda: self._adv_append_output(f"[{name}] {result}"))
            except Exception as e:
                log_error(f"{name}异常: {e}")
            finally:
                def restore():
                    try:
                        if btn and btn.winfo_exists():
                            btn.config(state=tk.NORMAL, text=original_text)
                    except tk.TclError:
                        pass
                def schedule_restore():
                    self.root.after(3000, restore)
                self.root.after(0, schedule_restore)

        threading.Thread(target=worker, daemon=True).start()

    def _adv_list_buildings(self):
        """列出建筑"""
        success, result = advanced_tools.get_building_list()
        self.root.after(0, lambda: self._adv_append_output(f"[建筑] {result}"))

    def _adv_population_status(self):
        """人口状态"""
        success, result = advanced_tools.get_population_status()
        self.root.after(0, lambda: self._adv_append_output(f"[人口] {result}"))

    def _adv_simworld_status(self):
        """SimWorld状态"""
        success, result = advanced_tools.get_simworld_status()
        self.root.after(0, lambda: self._adv_append_output(f"[世界] {result}"))

    def _adv_pause_game(self):
        """暂停游戏"""
        self._current_time_speed = 0
        success, result = advanced_tools.pause_game()
        self.root.after(0, lambda: self._adv_append_output(f"[暂停] {result}"))

    def _adv_resume_game(self):
        """继续游戏"""
        self._current_time_speed = 1
        success, result = advanced_tools.resume_game()
        self.root.after(0, lambda: self._adv_append_output(f"[继续] {result}"))
