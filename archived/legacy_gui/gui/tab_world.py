"""
世界系统标签页 Mixin

功能：市场物价 / 产业链 / 流民灾害 / 知名度 / 建筑精细 / 蓝图探查 / NPC 详情探查
设计：与高级工具页一致的卡片式折叠面板；每个系统配「探查（probe）」+「动作」按钮，
      探查输出真实对象/字段/方法，便于实机迭代（部分 API 未在游戏源码中完全确认）。
"""
import threading

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox

from src import world_tools
from src.logger import log, log_error
from .scrollable import ScrollableFrame
from .theme import FONT_MONO, FONT_SUB, FONT_TINY, ThemeManager
from .widgets import T


class WorldTabMixin:
    """世界系统标签页 Mixin"""

    def _build_world_tab(self, parent, use_scroll=True):
        """世界系统标签页"""
        tab = parent
        if use_scroll:
            scroll = ScrollableFrame(tab)
            scroll.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
            content_frame = content_frame
        else:
            content_frame = tab

        # === 市场物价 ===
        _, market_frame = self._create_collapsible(content_frame, "市场物价", default_open=True)
        row = tk.Frame(market_frame, bg=T("bg_card"))
        row.pack(fill=tk.X, padx=4, pady=(0, 4))
        ttk.Button(row, text="🔍 探查", style="Warning.TButton",
                   command=lambda: self._world_probe(world_tools.probe_market, "市场探查")).pack(side=tk.LEFT, padx=4)
        self._market_down_btn = ttk.Button(row, text="价格 ×0.5", style="Success.TButton",
                   command=lambda: self._world_with_cooldown(self._market_down_btn, lambda: world_tools.market_price_scale(0.5), "价格×0.5"))
        self._market_down_btn.pack(side=tk.LEFT, padx=4)
        self._market_up_btn = ttk.Button(row, text="价格 ×2", style="Success.TButton",
                   command=lambda: self._world_with_cooldown(self._market_up_btn, lambda: world_tools.market_price_scale(2.0), "价格×2"))
        self._market_up_btn.pack(side=tk.LEFT, padx=4)
        ttk.Button(row, text="↩ 还原价格", style="Restore.TButton",
                   command=lambda: self._run_async(world_tools.market_price_restore)).pack(side=tk.LEFT, padx=4)

        # === 产业链 ===
        _, chain_frame = self._create_collapsible(content_frame, "产业链", default_open=True)
        row = tk.Frame(chain_frame, bg=T("bg_card"))
        row.pack(fill=tk.X, padx=4, pady=(0, 4))
        ttk.Button(row, text="🔍 探查", style="Warning.TButton",
                   command=lambda: self._world_probe(world_tools.probe_industry_chain, "产业链探查")).pack(side=tk.LEFT, padx=4)
        self._chain_btn = ttk.Button(row, text="🔓 全产业链解锁", style="Success.TButton",
                   command=lambda: self._world_with_cooldown(self._chain_btn, world_tools.unlock_industry_chain, "产业链解锁"))
        self._chain_btn.pack(side=tk.LEFT, padx=4)

        # === 流民灾害 ===
        _, refugee_frame = self._create_collapsible(content_frame, "流民灾害", default_open=True)
        row = tk.Frame(refugee_frame, bg=T("bg_card"))
        row.pack(fill=tk.X, padx=4, pady=(0, 4))
        ttk.Button(row, text="🔍 探查", style="Warning.TButton",
                   command=lambda: self._world_probe(world_tools.probe_refugee, "流民探查")).pack(side=tk.LEFT, padx=4)
        self._refugee_btn = ttk.Button(row, text="🧹 清零未接纳流民", style="Success.TButton",
                   command=lambda: self._world_with_cooldown(self._refugee_btn, world_tools.clear_refugee, "流民清零"))
        self._refugee_btn.pack(side=tk.LEFT, padx=4)

        # === 灾害控制（天灾 / 人祸）===
        _, disaster_frame = self._create_collapsible(content_frame, "灾害控制（天灾 / 人祸）", default_open=True)
        row = tk.Frame(disaster_frame, bg=T("bg_card"))
        row.pack(fill=tk.X, padx=4, pady=(0, 4))
        ttk.Button(row, text="🔍 探查", style="Warning.TButton",
                   command=lambda: self._world_probe(world_tools.probe_disaster, "灾害探查")).pack(side=tk.LEFT, padx=4)
        self._nat_btn = ttk.Button(row, text="零天灾", style="Success.TButton",
                   command=lambda: self._world_with_cooldown(self._nat_btn, world_tools.clear_natural_disaster, "零天灾"))
        self._nat_btn.pack(side=tk.LEFT, padx=4)
        self._man_btn = ttk.Button(row, text="零人祸", style="Success.TButton",
                   command=lambda: self._world_with_cooldown(self._man_btn, world_tools.clear_manmade_disaster, "零人祸"))
        self._man_btn.pack(side=tk.LEFT, padx=4)

        # === 知名度 ===
        _, rep_frame = self._create_collapsible(content_frame, "知名度（双存储）", default_open=True)
        row = tk.Frame(rep_frame, bg=T("bg_card"))
        row.pack(fill=tk.X, padx=4, pady=(0, 4))
        ttk.Button(row, text="🔍 探查", style="Warning.TButton",
                   command=lambda: self._world_probe(world_tools.probe_reputation, "知名度探查")).pack(side=tk.LEFT, padx=4)
        self._rep10k_btn = ttk.Button(row, text="知名度 +1万", style="Success.TButton",
                   command=lambda: self._world_with_cooldown(self._rep10k_btn, lambda: world_tools.add_reputation(10000), "知名度+1万"))
        self._rep10k_btn.pack(side=tk.LEFT, padx=4)
        self._rep100k_btn = ttk.Button(row, text="知名度 +10万", style="Success.TButton",
                   command=lambda: self._world_with_cooldown(self._rep100k_btn, lambda: world_tools.add_reputation(100000), "知名度+10万"))
        self._rep100k_btn.pack(side=tk.LEFT, padx=4)

        # === 建筑精细操作 ===
        _, bld_frame = self._create_collapsible(content_frame, "建筑精细操作", default_open=True)
        row = tk.Frame(bld_frame, bg=T("bg_card"))
        row.pack(fill=tk.X, padx=4, pady=(0, 4))
        ttk.Button(row, text="📋 建筑明细", style="Primary.TButton",
                   command=lambda: self._world_probe(world_tools.list_building_detail, "建筑明细")).pack(side=tk.LEFT, padx=4)
        self._bld_top_btn = ttk.Button(row, text="⬆ 升级到顶", style="Success.TButton",
                   command=lambda: self._world_with_cooldown(self._bld_top_btn, world_tools.upgrade_all_to_top, "升级到顶"))
        self._bld_top_btn.pack(side=tk.LEFT, padx=4)
        self._bld_pop_btn = ttk.Button(row, text="👥 全部满人口", style="Success.TButton",
                   command=lambda: self._world_with_cooldown(self._bld_pop_btn, world_tools.full_population_all, "全部满人口"))
        self._bld_pop_btn.pack(side=tk.LEFT, padx=4)

        # === 税收（自动纳税）===
        _, tax_frame = self._create_collapsible(content_frame, "税收（自动纳税）", default_open=True)
        row = tk.Frame(tax_frame, bg=T("bg_card"))
        row.pack(fill=tk.X, padx=4, pady=(0, 4))
        ttk.Button(row, text="🔍 探查", style="Warning.TButton",
                   command=lambda: self._world_probe(world_tools.probe_tax, "税收探查")).pack(side=tk.LEFT, padx=4)
        self._tax_auto_btn = ttk.Button(row, text="🧾 自动纳税（关弹窗）", style="Success.TButton",
                   command=lambda: self._world_with_cooldown(self._tax_auto_btn, world_tools.enable_auto_tax, "自动纳税"))
        self._tax_auto_btn.pack(side=tk.LEFT, padx=4)
        self._tax_restore_btn = ttk.Button(row, text="↩ 恢复弹窗", style="Restore.TButton",
                   command=lambda: self._world_with_cooldown(self._tax_restore_btn, world_tools.disable_auto_tax, "恢复弹窗"))
        self._tax_restore_btn.pack(side=tk.LEFT, padx=4)
        self._tax_pay_btn = ttk.Button(row, text="💰 立即缴税一次", style="Primary.TButton",
                   command=lambda: self._world_with_cooldown(self._tax_pay_btn, world_tools.pay_tax_now, "立即缴税"))
        self._tax_pay_btn.pack(side=tk.LEFT, padx=4)
        ttk.Label(row, text="每年 1 月 1 日默认弹「确认纳税」；开启后自动扣款、不弹窗",
                  style="Card.TLabel", foreground=T("fg_muted"), font=FONT_TINY).pack(side=tk.LEFT, padx=8)

        # === 蓝图（仅探查）===
        _, bp_frame = self._create_collapsible(content_frame, "蓝图（仅探查）", default_open=False)
        row = tk.Frame(bp_frame, bg=T("bg_card"))
        row.pack(fill=tk.X, padx=4, pady=(0, 4))
        ttk.Button(row, text="🔍 蓝图探查", style="Warning.TButton",
                   command=lambda: self._world_probe(world_tools.probe_blueprint, "蓝图探查")).pack(side=tk.LEFT, padx=4)
        ttk.Label(row, text="合成/秒完成 API 未确认，仅探查", style="Card.TLabel",
                  foreground=T("fg_muted"), font=FONT_TINY).pack(side=tk.LEFT, padx=8)

        # === NPC 详情（仅探查）===
        _, npc_frame = self._create_collapsible(content_frame, "NPC 详情（仅探查）", default_open=False)
        row = tk.Frame(npc_frame, bg=T("bg_card"))
        row.pack(fill=tk.X, padx=4, pady=(0, 4))
        ttk.Button(row, text="🔍 NPC 详情探查", style="Warning.TButton",
                   command=lambda: self._world_probe(world_tools.probe_npc_detail, "NPC详情探查")).pack(side=tk.LEFT, padx=4)
        ttk.Label(row, text="字段因版本而异，改属性需按探查结果定制", style="Card.TLabel",
                  foreground=T("fg_muted"), font=FONT_TINY).pack(side=tk.LEFT, padx=8)

        # === 输出区 ===
        out_frame = ttk.Frame(tab, style="Card.TFrame")
        out_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))
        out_header = ttk.Frame(out_frame, style="Card.TFrame")
        out_header.pack(fill=tk.X, padx=15, pady=(10, 5))
        ttk.Label(out_header, text="执行输出", style="Card.TLabel",
                  font=FONT_SUB).pack(side=tk.LEFT)
        ttk.Button(out_header, text="清空", style="Small.TButton",
                   command=self._clear_world_output).pack(side=tk.RIGHT)

        log_bg, log_fg, _ = ThemeManager.get_log_colors()
        self.world_output_text = scrolledtext.ScrolledText(out_frame, height=6, bg=log_bg, fg=log_fg,
                                                           font=FONT_MONO, borderwidth=0)
        self.world_output_text.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 10))
        self.world_output_text.insert(tk.END, "暂无执行日志，点击上方按钮执行操作后将显示结果...")
        self.world_output_text.configure(state=tk.DISABLED)
        self._world_output_has_content = False

    def _world_append_output(self, text):
        """追加输出到世界系统输出区（首次写入时清除占位提示）"""
        if not hasattr(self, "world_output_text"):
            return
        self.world_output_text.configure(state=tk.NORMAL)
        if not getattr(self, "_world_output_has_content", False):
            self.world_output_text.delete("1.0", tk.END)
            self._world_output_has_content = True
        self.world_output_text.insert(tk.END, text + "\n")
        self.world_output_text.see(tk.END)
        self.world_output_text.configure(state=tk.DISABLED)

    def _clear_world_output(self):
        """清空世界系统输出区"""
        self.world_output_text.configure(state=tk.NORMAL)
        self.world_output_text.delete("1.0", tk.END)
        self.world_output_text.insert(tk.END, "暂无执行日志，点击上方按钮执行操作后将显示结果...")
        self.world_output_text.configure(state=tk.DISABLED)
        self._world_output_has_content = False

    def _world_probe(self, func, label):
        """执行探查类函数并把结果写入输出区"""
        if not self.dll_injected:
            messagebox.showwarning("提示", "请先注入DLL。")
            return
        self._run_async(self._world_probe_worker, func, label)

    def _world_probe_worker(self, func, label):
        try:
            success, result = func()
            text = f"[{label}] {result}"
            self._report_probe(label, result)
        except Exception as e:
            log_error(f"{label}异常: {e}")
            text = f"[{label}] 异常: {e}"
        self.root.after(0, lambda: self._world_append_output(text))

    def _world_with_cooldown(self, btn, func, name):
        """世界系统按钮带 3 秒冷却（每按钮独立）"""
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
                self.root.after(0, lambda: self._world_append_output(f"[{name}] {result}"))
            except Exception as e:
                log_error(f"{name}异常: {e}")
            finally:
                def restore():
                    try:
                        if btn and btn.winfo_exists():
                            btn.config(state=tk.NORMAL, text=original_text)
                    except tk.TclError:
                        pass
                self.root.after(3000, restore)

        threading.Thread(target=worker, daemon=True).start()
