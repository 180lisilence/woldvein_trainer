"""
一键作弊标签页 Mixin
功能：天赋/成就/灾害/时间/天气/节日/城市/风水/核心数值 一键修改
v0.3 新增：基于深度探针发现的游戏内部对象和函数
"""
import threading

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox

from src import cheat_tools
from src.logger import log, log_error
from .scrollable import ScrollableFrame
from .theme import FONT_BOLD, FONT_MONO, FONT_SUB, FONT_TINY, ThemeManager
from .widgets import T, button_grid


class CheatTabMixin:
    """一键作弊标签页 Mixin"""

    def _build_cheat_tab(self, parent, use_scroll=True):
        """一键作弊标签页"""
        tab = parent
        if use_scroll:
            scroll = ScrollableFrame(tab)
            scroll.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
            content_frame = content_frame
        else:
            content_frame = tab

        # === 一键全开（顶部醒目按钮）===
        top_frame = tk.Frame(content_frame, bg=T("bg_card"))
        top_frame.pack(fill=tk.X, padx=15, pady=(10, 8))

        ttk.Button(top_frame, text="🔥 一键全开（所有作弊功能）", style="Danger.TButton",
                   command=self._cheat_enable_all).pack(fill=tk.X, pady=5)

        tk.Label(top_frame, text="警告：一键开开会同时修改天赋、成就、灾害、时间、天气、核心数值等所有功能，请谨慎使用！",
                  bg=T("bg_card"), fg=T("fg_warning"), font=FONT_TINY, wraplength=600, justify=tk.LEFT).pack(anchor=tk.W, pady=(0, 5))

        # === 天赋系统（折叠面板，默认展开）===
        _, talent_frame = self._create_collapsible(content_frame, "🎯 天赋系统", default_open=True)

        talent_row1 = tk.Frame(talent_frame, bg=T("bg_card"))
        talent_row1.pack(fill=tk.X, padx=4, pady=(0, 4))
        ttk.Button(talent_row1, text="解锁所有天赋", style="Success.TButton",
                   command=lambda: self._run_async(cheat_tools.unlock_all_talents)).pack(side=tk.LEFT, padx=4)
        ttk.Button(talent_row1, text="所有天赋升满级", style="Success.TButton",
                   command=lambda: self._run_async(cheat_tools.max_all_talents)).pack(side=tk.LEFT, padx=4)
        ttk.Button(talent_row1, text="加200天赋点(GM)", style="Primary.TButton",
                   command=lambda: self._run_async(cheat_tools.add_talent_points_200)).pack(side=tk.LEFT, padx=4)
        ttk.Button(talent_row1, text="获取天赋信息", style="Info.TButton",
                   command=lambda: self._run_async(cheat_tools.get_talent_info)).pack(side=tk.LEFT, padx=4)

        # === 成就系统（折叠面板，默认展开）===
        _, achieve_frame = self._create_collapsible(content_frame, "🏆 成就系统", default_open=True)

        achieve_row = tk.Frame(achieve_frame, bg=T("bg_card"))
        achieve_row.pack(fill=tk.X, padx=4, pady=(0, 4))
        ttk.Button(achieve_row, text="解锁所有成就(GM)", style="Success.TButton",
                   command=lambda: self._run_async(cheat_tools.unlock_all_achievements)).pack(side=tk.LEFT, padx=4)
        ttk.Button(achieve_row, text="获取成就信息", style="Info.TButton",
                   command=lambda: self._run_async(cheat_tools.get_achievement_info)).pack(side=tk.LEFT, padx=4)

        # === 灾害系统（折叠面板，默认展开）===
        _, disaster_frame = self._create_collapsible(content_frame, "🌪️ 灾害系统", default_open=True)

        disaster_row1 = tk.Frame(disaster_frame, bg=T("bg_card"))
        disaster_row1.pack(fill=tk.X, padx=4, pady=(0, 4))
        ttk.Button(disaster_row1, text="关闭所有灾害", style="Success.TButton",
                   command=lambda: self._run_async(cheat_tools.close_all_disasters)).pack(side=tk.LEFT, padx=4)
        ttk.Button(disaster_row1, text="清除所有地震", style="Success.TButton",
                   command=lambda: self._run_async(cheat_tools.clear_all_earthquakes)).pack(side=tk.LEFT, padx=4)
        ttk.Button(disaster_row1, text="禁用灾害触发", style="Warning.TButton",
                   command=lambda: self._run_async(cheat_tools.disable_disaster_triggers)).pack(side=tk.LEFT, padx=4)
        ttk.Button(disaster_row1, text="获取灾害信息", style="Info.TButton",
                   command=lambda: self._run_async(cheat_tools.get_disaster_info)).pack(side=tk.LEFT, padx=4)

        # === 时间系统（折叠面板，默认折叠）===
        _, time_frame = self._create_collapsible(content_frame, "⏰ 时间系统", default_open=False)

        time_row1 = tk.Frame(time_frame, bg=T("bg_card"))
        time_row1.pack(fill=tk.X, padx=4, pady=(0, 4))
        ttk.Button(time_row1, text="固定季节", style="Warning.TButton",
                   command=lambda: self._run_async(lambda: cheat_tools.fix_season(True))).pack(side=tk.LEFT, padx=4)
        ttk.Button(time_row1, text="取消固定季节", style="Restore.TButton",
                   command=lambda: self._run_async(lambda: cheat_tools.fix_season(False))).pack(side=tk.LEFT, padx=4)
        ttk.Button(time_row1, text="跳过时间事件", style="Warning.TButton",
                   command=lambda: self._run_async(lambda: cheat_tools.skip_time_events(True))).pack(side=tk.LEFT, padx=4)
        ttk.Button(time_row1, text="恢复时间事件", style="Restore.TButton",
                   command=lambda: self._run_async(lambda: cheat_tools.skip_time_events(False))).pack(side=tk.LEFT, padx=4)
        ttk.Button(time_row1, text="获取时间信息", style="Info.TButton",
                   command=lambda: self._run_async(cheat_tools.get_time_info)).pack(side=tk.LEFT, padx=4)

        # === 天气系统（折叠面板，默认折叠）===
        _, weather_frame = self._create_collapsible(content_frame, "🌤️ 天气系统", default_open=False)

        weather_row = tk.Frame(weather_frame, bg=T("bg_card"))
        weather_row.pack(fill=tk.X, padx=4, pady=(0, 4))
        ttk.Button(weather_row, text="固定天气", style="Warning.TButton",
                   command=lambda: self._run_async(lambda: cheat_tools.fix_weather(True))).pack(side=tk.LEFT, padx=4)
        ttk.Button(weather_row, text="取消固定天气", style="Restore.TButton",
                   command=lambda: self._run_async(lambda: cheat_tools.fix_weather(False))).pack(side=tk.LEFT, padx=4)
        ttk.Button(weather_row, text="获取天气信息", style="Info.TButton",
                   command=lambda: self._run_async(cheat_tools.get_weather_info)).pack(side=tk.LEFT, padx=4)

        # === 节日系统（折叠面板，默认折叠）===
        _, festival_frame = self._create_collapsible(content_frame, "🎊 节日系统", default_open=False)

        festival_row = tk.Frame(festival_frame, bg=T("bg_card"))
        festival_row.pack(fill=tk.X, padx=4, pady=(0, 4))
        ttk.Button(festival_row, text="节日暂停", style="Warning.TButton",
                   command=lambda: self._run_async(cheat_tools.pause_festival)).pack(side=tk.LEFT, padx=4)
        ttk.Button(festival_row, text="关闭烟花", style="Warning.TButton",
                   command=lambda: self._run_async(cheat_tools.close_fireworks)).pack(side=tk.LEFT, padx=4)
        ttk.Button(festival_row, text="清除节日广告", style="Warning.TButton",
                   command=lambda: self._run_async(cheat_tools.clear_all_festival_ads)).pack(side=tk.LEFT, padx=4)

        # === 城市系统（折叠面板，默认折叠）===
        _, city_frame = self._create_collapsible(content_frame, "🏙️ 城市系统", default_open=False)

        city_row = tk.Frame(city_frame, bg=T("bg_card"))
        city_row.pack(fill=tk.X, padx=4, pady=(0, 4))
        ttk.Button(city_row, text="所有城市成长", style="Success.TButton",
                   command=lambda: self._run_async(cheat_tools.grow_all_cities)).pack(side=tk.LEFT, padx=4)
        ttk.Button(city_row, text="获取城市信息", style="Info.TButton",
                   command=lambda: self._run_async(cheat_tools.get_city_info)).pack(side=tk.LEFT, padx=4)

        # === 风水系统（折叠面板，默认折叠）===
        _, fengshui_frame = self._create_collapsible(content_frame, "☯️ 风水系统", default_open=False)

        fengshui_row = tk.Frame(fengshui_frame, bg=T("bg_card"))
        fengshui_row.pack(fill=tk.X, padx=4, pady=(0, 4))
        ttk.Button(fengshui_row, text="GM显示地块风水", style="Primary.TButton",
                   command=lambda: self._run_async(cheat_tools.gm_show_block_fengshui)).pack(side=tk.LEFT, padx=4)
        ttk.Button(fengshui_row, text="施放超级风水技能", style="Primary.TButton",
                   command=lambda: self._run_async(cheat_tools.cast_super_fengshui_skill)).pack(side=tk.LEFT, padx=4)
        ttk.Button(fengshui_row, text="获取风水信息", style="Info.TButton",
                   command=lambda: self._run_async(cheat_tools.get_fengshui_info)).pack(side=tk.LEFT, padx=4)

        # === 核心数值（折叠面板，默认展开）===
        _, core_frame = self._create_collapsible(content_frame, "💎 核心数值（直接赋值）", default_open=True)

        # 鸿业等级
        core_row1 = tk.Frame(core_frame, bg=T("bg_card"))
        core_row1.pack(fill=tk.X, padx=4, pady=(0, 4))
        tk.Label(core_row1, text="鸿业等级:", bg=T("bg_card"), fg=T("fg")).pack(side=tk.LEFT, padx=(4, 2))
        self.cheat_boom_level = tk.IntVar(value=14)
        tk.Spinbox(core_row1, from_=1, to=20, textvariable=self.cheat_boom_level, width=8).pack(side=tk.LEFT, padx=2)
        ttk.Button(core_row1, text="设置", style="Primary.TButton",
                   command=self._cheat_set_boom_level).pack(side=tk.LEFT, padx=4)

        # 幸福度
        core_row2 = tk.Frame(core_frame, bg=T("bg_card"))
        core_row2.pack(fill=tk.X, padx=4, pady=(0, 4))
        tk.Label(core_row2, text="幸福度:", bg=T("bg_card"), fg=T("fg")).pack(side=tk.LEFT, padx=(4, 2))
        self.cheat_happiness = tk.IntVar(value=100)
        tk.Spinbox(core_row2, from_=0, to=200, textvariable=self.cheat_happiness, width=8).pack(side=tk.LEFT, padx=2)
        ttk.Button(core_row2, text="设置", style="Primary.TButton",
                   command=self._cheat_set_happiness).pack(side=tk.LEFT, padx=4)

        # 创造力
        core_row3 = tk.Frame(core_frame, bg=T("bg_card"))
        core_row3.pack(fill=tk.X, padx=4, pady=(0, 4))
        tk.Label(core_row3, text="创造力:", bg=T("bg_card"), fg=T("fg")).pack(side=tk.LEFT, padx=(4, 2))
        self.cheat_creativity = tk.IntVar(value=99999)
        tk.Spinbox(core_row3, from_=0, to=999999, textvariable=self.cheat_creativity, width=10).pack(side=tk.LEFT, padx=2)
        ttk.Button(core_row3, text="设置", style="Primary.TButton",
                   command=self._cheat_set_creativity).pack(side=tk.LEFT, padx=4)

        # 金钱
        core_row4 = tk.Frame(core_frame, bg=T("bg_card"))
        core_row4.pack(fill=tk.X, padx=4, pady=(0, 4))
        tk.Label(core_row4, text="金钱:", bg=T("bg_card"), fg=T("fg")).pack(side=tk.LEFT, padx=(4, 2))
        self.cheat_money = tk.IntVar(value=99999999)
        tk.Spinbox(core_row4, from_=0, to=999999999, textvariable=self.cheat_money, width=12).pack(side=tk.LEFT, padx=2)
        ttk.Button(core_row4, text="设置", style="Primary.TButton",
                   command=self._cheat_set_money).pack(side=tk.LEFT, padx=4)

        # 昌盛值
        core_row5 = tk.Frame(core_frame, bg=T("bg_card"))
        core_row5.pack(fill=tk.X, padx=4, pady=(0, 4))
        tk.Label(core_row5, text="昌盛值:", bg=T("bg_card"), fg=T("fg")).pack(side=tk.LEFT, padx=(4, 2))
        self.cheat_prosperity = tk.IntVar(value=99999)
        tk.Spinbox(core_row5, from_=0, to=999999, textvariable=self.cheat_prosperity, width=10).pack(side=tk.LEFT, padx=2)
        ttk.Button(core_row5, text="设置", style="Primary.TButton",
                   command=self._cheat_set_prosperity).pack(side=tk.LEFT, padx=4)

        # 获取核心状态
        core_row6 = tk.Frame(core_frame, bg=T("bg_card"))
        core_row6.pack(fill=tk.X, padx=4, pady=(4, 0))
        ttk.Button(core_row6, text="📊 获取核心数值状态", style="Info.TButton",
                   command=lambda: self._run_async(cheat_tools.get_core_stats)).pack(side=tk.LEFT, padx=4)

        # === 输出区域 ===
        output_frame = tk.Frame(content_frame, bg=T("bg_card"))
        output_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=(8, 10))

        tk.Label(output_frame, text="执行输出:", bg=T("bg_card"), fg=T("fg_sub"), font=FONT_SUB).pack(anchor=tk.W, pady=(0, 4))

        self.cheat_output = scrolledtext.ScrolledText(
            output_frame, height=10, wrap=tk.WORD,
            bg=T("bg_input"), fg=T("fg"), insertbackground=T("fg"),
            font=FONT_MONO, relief=tk.FLAT, padx=8, pady=6
        )
        self.cheat_output.pack(fill=tk.BOTH, expand=True)
        self.cheat_output.configure(state=tk.DISABLED)

    # ============================================================
    # 回调函数
    # ============================================================

    def _cheat_append_output(self, text):
        """追加输出到作弊输出框"""
        self.cheat_output.configure(state=tk.NORMAL)
        self.cheat_output.insert(tk.END, text + "\n")
        self.cheat_output.see(tk.END)
        self.cheat_output.configure(state=tk.DISABLED)

    def _cheat_enable_all(self):
        """一键开启所有作弊功能"""
        def worker():
            try:
                ok, msg = cheat_tools.enable_all_cheats()
                self.root.after(0, lambda: self._cheat_append_output(msg))
                self.root.after(0, lambda: log("一键全开执行完成"))
            except Exception as e:
                self.root.after(0, lambda: self._cheat_append_output(f"[错误] {e}"))
                log_error(f"一键全开失败: {e}")
        threading.Thread(target=worker, daemon=True).start()

    def _cheat_set_boom_level(self):
        """设置鸿业等级"""
        level = self.cheat_boom_level.get()
        self._run_async(lambda: cheat_tools.set_boom_level(level))

    def _cheat_set_happiness(self):
        """设置幸福度"""
        score = self.cheat_happiness.get()
        self._run_async(lambda: cheat_tools.set_happiness(score))

    def _cheat_set_creativity(self):
        """设置创造力"""
        value = self.cheat_creativity.get()
        self._run_async(lambda: cheat_tools.set_creativity(value))

    def _cheat_set_money(self):
        """设置金钱"""
        value = self.cheat_money.get()
        self._run_async(lambda: cheat_tools.set_money(value))

    def _cheat_set_prosperity(self):
        """设置昌盛值"""
        value = self.cheat_prosperity.get()
        self._run_async(lambda: cheat_tools.set_prosperity(value))
