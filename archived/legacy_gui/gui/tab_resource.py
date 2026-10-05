"""
资源修改标签页 Mixin
功能：9种资源+幸福度+知名度，实时显示当前值（每3秒刷新）
v0.3 新增：资源归零恢复、幸福度恢复、天赋恢复
"""
import tkinter as tk
from tkinter import ttk

from src.resource_editor import RESOURCES, add_resource, add_all_resources, max_happiness, add_fame, zero_all_resources, restore_happiness
from src import advanced_tools
from src.game_status import get_status_provider
from .scrollable import ScrollableFrame
from .widgets import T
from src.constants import RESOURCE_ADD_AMOUNT, FAME_ADD_AMOUNT
from .theme import FONT_MONO_LG, FONT_MONO, FONT_BOLD, FONT_BODY, FONT_TINY


class ResourceTabMixin:
    """资源修改标签页 Mixin"""

    def _build_resource_tab(self, parent):
        """资源修改标签页"""
        scroll = ScrollableFrame(parent)
        scroll.pack(fill=tk.BOTH, expand=True)
        tab = scroll.inner

        # 说明
        desc = ttk.Label(tab, text="点击按钮增加对应资源（默认+100万），需先进入游戏场景并注入DLL",
                         style="Warning.TLabel")
        desc.pack(anchor=tk.W, padx=15, pady=(15, 10))

        # 一键全部
        all_frame = ttk.Frame(tab, style="Card.TFrame")
        all_frame.pack(fill=tk.X, padx=15, pady=(0, 15))
        ttk.Label(all_frame, text="快捷操作", style="Card.TLabel").pack(side=tk.LEFT, padx=15, pady=10)
        # 满天赋按钮
        ttk.Button(all_frame, text="🌟 满天赋", style="Success.TButton",
                   command=lambda: self._run_async(advanced_tools.max_all_talents)).pack(side=tk.RIGHT, padx=(5, 15), pady=10)
        # v0.3 新增：资源归零按钮
        ttk.Button(all_frame, text="↩ 资源归零", style="Restore.TButton",
                   command=lambda: self._run_async(zero_all_resources)).pack(side=tk.RIGHT, padx=5, pady=10)
        ttk.Button(all_frame, text="一键全部资源 +100万", style="Primary.TButton",
                   command=lambda: self._run_async(add_all_resources)).pack(side=tk.RIGHT, padx=5, pady=10)

        # 当前时间流速显示
        speed_frame = ttk.Frame(tab, style="Card.TFrame")
        speed_frame.pack(fill=tk.X, padx=15, pady=(0, 15))
        ttk.Label(speed_frame, text="当前时间流速：", style="Card.TLabel",
                  font=FONT_BOLD).pack(side=tk.LEFT, padx=(15, 5), pady=10)
        self.res_speed_label = ttk.Label(speed_frame, text="1x", style="Card.TLabel",
                                         foreground=T("success"), font=FONT_MONO_LG)
        self.res_speed_label.pack(side=tk.LEFT, pady=10)
        ttk.Label(speed_frame, text="（暂停时显示 0x）", style="Card.TLabel",
                  foreground=T("fg_muted"), font=FONT_TINY).pack(side=tk.LEFT, padx=10, pady=10)

        # 资源表格（紧凑列表布局，一屏展示所有资源）
        table_frame = ttk.Frame(tab, style="Card.TFrame")
        table_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))

        # 表头（视觉层级：加粗+主色）
        header_frame = ttk.Frame(table_frame, style="Card.TFrame")
        header_frame.pack(fill=tk.X, padx=12, pady=(10, 4))
        ttk.Label(header_frame, text="资源", style="Card.TLabel",
                  font=FONT_BOLD, foreground=T("accent"), width=12).pack(side=tk.LEFT, padx=(4, 0))
        ttk.Label(header_frame, text="当前数量", style="Card.TLabel",
                  font=FONT_BOLD, foreground=T("accent"), width=16).pack(side=tk.LEFT, padx=(16, 0))
        ttk.Label(header_frame, text="修改数值", style="Card.TLabel",
                  font=FONT_BOLD, foreground=T("accent"), width=12).pack(side=tk.LEFT, padx=(16, 0))
        ttk.Label(header_frame, text="操作", style="Card.TLabel",
                  font=FONT_BOLD, foreground=T("accent")).pack(side=tk.LEFT, padx=(16, 0))

        ttk.Separator(table_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=12)

        # 保存资源当前值标签引用和按钮引用
        self.resource_value_labels = {}
        self.resource_buttons = []

        for i, res in enumerate(RESOURCES):
            # 每行容器（斑马纹：偶数行略深）
            row_bg = T("bg_surface") if i % 2 == 1 else T("bg_card")
            row_frame = tk.Frame(table_frame, bg=row_bg)
            row_frame.pack(fill=tk.X, padx=12, pady=1)

            # 资源名称（左对齐）
            name_label = tk.Label(row_frame, text=f"  {res['icon']} {res['name']}", bg=row_bg,
                                  fg=T("fg"), font=FONT_BODY, width=14, anchor=tk.W)
            name_label.pack(side=tk.LEFT, padx=(4, 0), pady=4)

            # 当前值（突出：Consolas 12号加粗+绿色，右对齐形成整齐边缘）
            value_label = tk.Label(row_frame, text="——", bg=row_bg,
                                   fg=T("success"), font=FONT_MONO_LG, width=16, anchor=tk.E)
            value_label.pack(side=tk.LEFT, padx=(8, 0), pady=4)
            self.resource_value_labels[res["id"]] = value_label

            # 自定义数量输入（统一宽度80px）
            var = tk.StringVar(value=str(RESOURCE_ADD_AMOUNT))
            entry = tk.Entry(row_frame, textvariable=var, width=10, bg=T("bg"),
                             fg=T("fg"), insertbackground=T("fg"), font=FONT_MONO,
                             relief=tk.FLAT, highlightthickness=1, highlightbackground=T("bg_elevated"))
            entry.pack(side=tk.LEFT, padx=(12, 4), pady=4)

            # 按钮组（右侧对齐，统一间距）
            btn_group = tk.Frame(row_frame, bg=row_bg)
            btn_group.pack(side=tk.RIGHT, padx=(0, 8), pady=2)

            add_btn = ttk.Button(btn_group, text="+100万", style="Success.TButton",
                                 command=lambda rid=res["id"], rn=res["name"]: self._run_async(add_resource, rid, RESOURCE_ADD_AMOUNT))
            add_btn.pack(side=tk.LEFT, padx=(0, 4))
            self.resource_buttons.append(add_btn)

            custom_btn = ttk.Button(btn_group, text="增加", style="Small.TButton",
                                    command=lambda rid=res["id"], v=var: self._add_resource_validated(rid, v.get()))
            custom_btn.pack(side=tk.LEFT)
            self.resource_buttons.append(custom_btn)

            # 绑定Tooltip显示热键
            from .tooltip import bind_tooltip
            hotkey_map = {1: "Ctrl+F1", 2: "Ctrl+F2", 3: "Ctrl+F3", 4: "Ctrl+F4",
                          5: "Ctrl+F5", 6: "Ctrl+F6", 19: "Ctrl+F9", 20: "Ctrl+F10"}
            hk = hotkey_map.get(res["id"], "")
            if hk:
                bind_tooltip(add_btn, f"增加{res['name']}\n快捷键: {hk}")

        # 特殊属性模块（独立视觉区隔：标题栏+内容区）
        special_frame = ttk.Frame(tab, style="Card.TFrame")
        special_frame.pack(fill=tk.X, padx=15, pady=(0, 15))

        # 标题栏（略深背景）
        special_header = tk.Frame(special_frame, bg=T("bg_elevated"))
        special_header.pack(fill=tk.X)
        tk.Label(special_header, text="  ✨ 特殊属性", bg=T("bg_elevated"), fg=T("warning"),
                 font=FONT_BOLD).pack(anchor=tk.W, padx=12, pady=6)

        btn_row = ttk.Frame(special_frame, style="Card.TFrame")
        btn_row.pack(fill=tk.X, padx=12, pady=10)

        ttk.Button(btn_row, text="幸福度最大", style="Primary.TButton",
                   command=lambda: self._run_async(max_happiness)).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_row, text="知名度 +1万", style="Primary.TButton",
                   command=lambda: self._run_async(add_fame, FAME_ADD_AMOUNT)).pack(side=tk.LEFT, padx=5)
        # v0.3 新增：恢复按钮
        ttk.Button(btn_row, text="↩ 恢复幸福度", style="Restore.TButton",
                   command=lambda: self._run_async(restore_happiness)).pack(side=tk.LEFT, padx=5)

        # 订阅游戏状态刷新（统一管理，避免多 tab 并发竞态）
        self._res_status_provider = get_status_provider()
        self._res_status_provider.subscribe("resource_tab", self._on_status_update)

    def _add_resource_validated(self, rid, value):
        """资源增加前校验数值范围，非法输入弹窗提示不执行"""
        from src.input_validator import validate_resource_amount
        from tkinter import messagebox
        amount, ok, msg = validate_resource_amount(value)
        if not ok:
            messagebox.showwarning("输入无效", msg)
            return
        self._run_async(add_resource, rid, amount)

    def _on_status_update(self, status, success):
        """游戏状态更新回调（从 GameStatusProvider 推送）

        在刷新线程中调用，需要切到主线程更新UI。
        """
        self.root.after(0, lambda: self._update_resource_display(status, success))

    def _update_resource_display(self, status, success):
        """在主线程更新资源显示"""
        if not self.dll_injected:
            return

        # 更新时间流速显示
        speed = getattr(self, "_current_time_speed", 1)
        speed_map = {0: "0x（暂停）", 1: "1x", 2: "2x", 3: "3x", 4: "4x"}
        speed_text = speed_map.get(speed, f"{speed}x")
        speed_color = T("error") if speed == 0 else T("success")
        if hasattr(self, "res_speed_label"):
            self.res_speed_label.config(text=speed_text, foreground=speed_color)

        if success and status:
            # 资源ID到JSON字段名映射（来自唯一资源定义源）
            from src.resource_defs import get_id_to_field
            id_to_field = get_id_to_field()
            for res_id, label in self.resource_value_labels.items():
                field = id_to_field.get(res_id)
                if field and field in status:
                    val = status[field]
                    # 格式化大数字
                    if isinstance(val, (int, float)) and val >= 10000:
                        text = f"{val:,.0f}"
                    else:
                        text = f"{val}"
                    label.config(text=text, foreground=T("success"))
                else:
                    label.config(text="——", foreground=T("accent"))
        else:
            for label in self.resource_value_labels.values():
                label.config(text="未进入场景", fg=T("error"))
