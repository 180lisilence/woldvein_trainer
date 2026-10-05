"""
全部工具标签页 Mixin（合并版 v3）
功能：高级工具 + 世界系统 + 一键作弊，合并到一个可滚动页面
v0.3.1 新增：直接调用原有三个构建方法（use_scroll=False），保证功能完整可用
"""
import tkinter as tk
from tkinter import ttk

from .scrollable import ScrollableFrame
from .theme import FONT_BOLD, FONT_SUB
from .widgets import T


class AllToolsTabMixin:
    """全部工具标签页 Mixin（合并高级/世界/作弊）"""

    def _build_all_tools_tab(self, parent):
        """全部工具标签页（合并版）"""
        tab = parent

        # === 外层可滚动内容区 ===
        scroll = ScrollableFrame(tab)
        scroll.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        content = scroll.inner

        # ================================================================
        # 第一区：🔧 高级工具
        # ================================================================
        section1 = self._make_section(content, "🔧 高级工具")
        self._build_advanced_tab(section1, use_scroll=False)

        # 分隔线
        self._make_separator(content)

        # ================================================================
        # 第二区：🌍 世界系统
        # ================================================================
        section2 = self._make_section(content, "🌍 世界系统")
        self._build_world_tab(section2, use_scroll=False)

        # 分隔线
        self._make_separator(content)

        # ================================================================
        # 第三区：🔥 一键作弊
        # ================================================================
        section3 = self._make_section(content, "🔥 一键作弊")
        self._build_cheat_tab(section3, use_scroll=False)

        # 底部留白
        tk.Frame(content, height=20, bg=T("bg_card")).pack(fill=tk.X)

    # ================================================================
    # 辅助方法
    # ================================================================

    def _make_section(self, parent, title):
        """创建大分类区域（带标题栏）"""
        section = tk.Frame(parent, bg=T("bg_card"))
        section.pack(fill=tk.X, padx=10, pady=5)

        # 标题栏
        header = tk.Frame(section, bg=T("bg_elevated"))
        header.pack(fill=tk.X)
        tk.Label(header, text=title, bg=T("bg_elevated"), fg=T("fg"),
                 font=FONT_BOLD, padx=10, pady=8).pack(side=tk.LEFT)

        # 内容区
        content = tk.Frame(section, bg=T("bg_card"))
        content.pack(fill=tk.X, padx=5, pady=5)
        return content

    def _make_separator(self, parent):
        """创建分隔线"""
        sep = tk.Frame(parent, bg=T("bg_elevated"), height=2)
        sep.pack(fill=tk.X, padx=20, pady=8)
