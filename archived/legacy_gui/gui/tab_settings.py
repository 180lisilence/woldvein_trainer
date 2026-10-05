"""
应用设置标签页 Mixin
功能：诊断日志输出/日志路径管理/清空日志/散文件MOD管理
"""
import os
import sys
import json
import threading
import shutil

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from src.logger import log, log_error, log_warning, get_log_path, get_log_dir, clear_log_file
from src.hotkey_manager import hotkey_manager, is_admin
from .scrollable import ScrollableFrame
from .widgets import T
from .theme import FONT_MONO, FONT_SUB, FONT_TINY
from src.constants import APP_VERSION
from src.constants import DEFAULT_GAME_PATH, SIM_COMMON_REL


class SettingsTabMixin:
    """应用设置标签页 Mixin"""

    def _build_settings_tab(self, parent):
        """应用设置标签页"""
        scroll = ScrollableFrame(parent)
        scroll.pack(fill=tk.BOTH, expand=True)
        tab = scroll.inner

        # === 诊断工具 ===
        diag_frame = ttk.Frame(tab, style="Card.TFrame")
        diag_frame.pack(fill=tk.X, padx=15, pady=15)

        ttk.Label(diag_frame, text="诊断工具", style="Card.TLabel",
                  font=FONT_SUB).pack(anchor=tk.W, padx=15, pady=(10, 5))

        ttk.Label(diag_frame, text="输出当前修改器全部状态到日志区，用于检验功能是否生效",
                  style="Card.TLabel", foreground=T("fg_muted")).pack(anchor=tk.W, padx=15, pady=(0, 10))

        btn_row = ttk.Frame(diag_frame, style="Card.TFrame")
        btn_row.pack(fill=tk.X, padx=15, pady=(0, 15))

        ttk.Button(btn_row, text="📋 输出诊断日志", style="Primary.TButton",
                   command=self._output_diagnostic_log).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_row, text="🗑️ 清空日志", style="Warning.TButton",
                   command=self.on_clear_log).pack(side=tk.LEFT, padx=3)

        # 日志路径显示（脱敏：长路径缩写）
        log_path = get_log_path()
        log_frame = ttk.Frame(diag_frame, style="Card.TFrame")
        log_frame.pack(fill=tk.X, padx=15, pady=(0, 15))

        ttk.Label(log_frame, text="日志文件路径:", style="Card.TLabel",
                  foreground=T("fg_muted")).pack(anchor=tk.W)
        # 路径脱敏：保留最后两级目录，前面用...代替
        def _shorten_path(p, max_parts=3):
            parts = p.replace("\\", "/").split("/")
            if len(parts) > max_parts:
                return ".../" + "/".join(parts[-max_parts:])
            return p
        self.log_path_var = tk.StringVar(value=_shorten_path(log_path))
        # 只读样式：背景更暗，无边框，区别于可编辑输入框
        log_entry = tk.Entry(log_frame, textvariable=self.log_path_var, state="readonly",
                             font=FONT_MONO, bg=T("bg_surface"), fg=T("fg_muted"),
                             readonlybackground=T("bg_surface"), relief=tk.FLAT, borderwidth=0)
        log_entry.pack(fill=tk.X, pady=(2, 5), ipady=4)
        # 绑定Tooltip显示完整路径
        from .tooltip import bind_tooltip
        bind_tooltip(log_entry, f"完整路径:\n{log_path}")

        log_btn_row = ttk.Frame(log_frame, style="Card.TFrame")
        log_btn_row.pack(fill=tk.X)
        ttk.Button(log_btn_row, text="📂 打开日志文件夹", style="Primary.TButton",
                   command=lambda: os.startfile(get_log_dir())).pack(side=tk.LEFT, padx=3)
        ttk.Button(log_btn_row, text="📄 打开日志文件", style="Primary.TButton",
                   command=lambda: os.startfile(get_log_path())).pack(side=tk.LEFT, padx=3)
        ttk.Button(log_btn_row, text="📋 复制路径", style="Warning.TButton",
                   command=lambda: self._copy_to_clipboard(get_log_path())).pack(side=tk.LEFT, padx=3)

        # === 探查报告（一键全量探查，便于一次性复制）===
        rep_frame = ttk.Frame(tab, style="Card.TFrame")
        rep_frame.pack(fill=tk.X, padx=15, pady=(0, 15))

        ttk.Label(rep_frame, text="探查报告", style="Card.TLabel",
                  font=FONT_SUB).pack(anchor=tk.W, padx=15, pady=(10, 5))
        ttk.Label(rep_frame, text="一键跑完全部探查/诊断，结果汇总到 probe_report.txt，直接打开复制（需先注入DLL并进入存档）",
                  style="Card.TLabel", foreground=T("fg_muted"),
                  font=FONT_TINY).pack(anchor=tk.W, padx=15, pady=(0, 10))

        rep_btn_row = ttk.Frame(rep_frame, style="Card.TFrame")
        rep_btn_row.pack(fill=tk.X, padx=15, pady=(0, 15))
        ttk.Button(rep_btn_row, text="🧪 一键全量探查", style="Primary.TButton",
                   command=self._run_full_probe).pack(side=tk.LEFT, padx=3)
        ttk.Button(rep_btn_row, text="📄 打开报告文件", style="Success.TButton",
                   command=self._open_probe_report).pack(side=tk.LEFT, padx=3)
        ttk.Button(rep_btn_row, text="🗑 清空报告", style="Warning.TButton",
                   command=self._clear_probe_report).pack(side=tk.LEFT, padx=3)

        # === MOD管理 ===
        mod_frame = ttk.Frame(tab, style="Card.TFrame")
        mod_frame.pack(fill=tk.X, padx=15, pady=(0, 15))

        ttk.Label(mod_frame, text="散文件MOD管理", style="Card.TLabel",
                  font=FONT_SUB).pack(anchor=tk.W, padx=15, pady=(10, 5))

        ttk.Label(mod_frame, text="检测并卸载游戏目录中的散文件版创造模式（sim_common目录），避免与DLL注入版冲突",
                  style="Card.TLabel", foreground=T("fg_muted")).pack(anchor=tk.W, padx=15, pady=(0, 10))

        mod_btn_row = ttk.Frame(mod_frame, style="Card.TFrame")
        mod_btn_row.pack(fill=tk.X, padx=15, pady=(0, 15))

        self.mod_status_var = tk.StringVar(value="未检测")
        self.mod_status_label = ttk.Label(mod_btn_row, textvariable=self.mod_status_var, style="Card.TLabel",
                                          foreground=T("fg_muted"))
        self.mod_status_label.pack(side=tk.LEFT, padx=5)

        ttk.Button(mod_btn_row, text="🔍 检测MOD", style="Primary.TButton",
                   command=self._check_mod_status).pack(side=tk.RIGHT, padx=3)
        ttk.Button(mod_btn_row, text="📦 安装散文件MOD", style="Success.TButton",
                   command=self._install_mod).pack(side=tk.RIGHT, padx=3)
        ttk.Button(mod_btn_row, text="🗑️ 卸载散文件MOD", style="Danger.TButton",
                   command=self._uninstall_mod).pack(side=tk.RIGHT, padx=3)

        # === 热键配置（独立工具入口）===
        hotkey_frame = ttk.Frame(tab, style="Card.TFrame")
        hotkey_frame.pack(fill=tk.X, padx=15, pady=(0, 15))

        ttk.Label(hotkey_frame, text="热键配置", style="Card.TLabel",
                  font=FONT_SUB).pack(anchor=tk.W, padx=15, pady=(10, 5))

        ttk.Label(hotkey_frame, text="热键设置已独立为单独工具，点击下方按钮打开配置。修改后重启修改器生效。",
                  style="Card.TLabel", foreground=T("fg_muted")).pack(anchor=tk.W, padx=15, pady=(0, 10))

        hotkey_btn_row = ttk.Frame(hotkey_frame, style="Card.TFrame")
        hotkey_btn_row.pack(fill=tk.X, padx=15, pady=(0, 15))

        ttk.Button(hotkey_btn_row, text="⚙️ 打开热键配置工具", style="Primary.TButton",
                   command=self._open_hotkey_configurator).pack(side=tk.LEFT, padx=3)
        ttk.Label(hotkey_btn_row, text="（需 Python 环境，源码模式下可用）",
                  style="Card.TLabel", foreground=T("fg_muted"),
                  font=FONT_TINY).pack(side=tk.LEFT, padx=10)

        # === 关于 ===
        about_frame = ttk.Frame(tab, style="Card.TFrame")
        about_frame.pack(fill=tk.X, padx=15, pady=(0, 15))

        ttk.Label(about_frame, text="关于", style="Card.TLabel",
                  font=FONT_SUB).pack(anchor=tk.W, padx=15, pady=(10, 5))

        about_text = (
            f"平野孤鸿修改器 v{APP_VERSION}  |  Ballads of Hongye (Steam 2656540)\n"
            "DLL注入 + inline-hook lua_pcall  |  纯内存操作，不修改游戏文件"
        )
        ttk.Label(about_frame, text=about_text, style="Card.TLabel",
                  justify=tk.LEFT, foreground=T("fg_muted"),
                  font=("微软雅黑", 8)).pack(anchor=tk.W, padx=15, pady=(0, 12))

    def _open_hotkey_configurator(self):
        """打开独立热键配置工具"""
        import subprocess
        import sys
        script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "hotkey_configurator.py")
        if not os.path.exists(script_path):
            messagebox.showerror("错误", f"热键配置工具不存在：\n{script_path}")
            return
        try:
            subprocess.Popen([sys.executable, script_path], cwd=os.path.dirname(script_path))
            log("已启动热键配置工具")
        except Exception as e:
            messagebox.showerror("错误", f"启动热键配置工具失败：{e}")
            log_error(f"启动热键配置工具失败: {e}")

    def _copy_to_clipboard(self, text):
        """复制文本到剪贴板"""
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.root.update()
            log("已复制到剪贴板")
        except Exception as e:
            log_error(f"复制到剪贴板失败: {e}")

    def _output_diagnostic_log(self):
        """输出诊断日志：收集修改器全部状态"""
        log("========== 诊断日志开始 ==========")

        # 1. 基本状态
        log(f"[基本] 修改器版本: v{APP_VERSION}")
        log(f"[基本] 游戏进程PID: {self.game_pid or '未检测到'}")
        log(f"[基本] DLL注入状态: {'已注入' if self.dll_injected else '未注入'}")
        log(f"[基本] DLL路径: {self.dll_path}")
        log(f"[基本] 热键状态: {'已启用' if hotkey_manager.is_enabled() else '未启用'}")
        log(f"[基本] 管理员权限: {'是' if is_admin() else '否（热键可能失效）'}")

        # 2. 创造模式状态
        from src.creative_mode import is_creative_mode_enabled
        cm_enabled = is_creative_mode_enabled()
        log(f"[创造模式] 状态: {'已开启' if cm_enabled else '未开启'}")
        if hasattr(self, 'creative_vars'):
            for name, var in self.creative_vars.items():
                log(f"[创造模式] 选项 {name}: {'开启' if var.get() else '关闭'}")

        # 3. 游戏内状态（通过Lua查询）
        if self.dll_injected:
            log("[游戏内] 正在查询游戏内状态...")
            def query_game_status():
                try:
                    from src.creative_mode import get_game_status
                    success, result = get_game_status()
                    if success and result:
                        try:
                            status = json.loads(result) if isinstance(result, str) else result
                            log(f"[游戏内] 鸿业等级: {status.get('boom_level', '未知')}")
                            log(f"[游戏内] 幸福度: {status.get('happiness', '未知')}")
                            # 知名度字段不在LUA_GET_STATUS返回中，此处不显示
                            log(f"[游戏内] 创造模式标记(g_bCreativeMode): {status.get('creative_mode', '未知')}")
                            # 资源
                            res_map = {'money': '金钱', 'mineral': '矿产', 'wood': '木料',
                                       'cloth': '衣物', 'food': '食物', 'water': '水',
                                       'population': '人口', 'salt': '盐', 'wine': '酒',
                                       'essence': '精华'}
                            for key, name in res_map.items():
                                val = status.get(key, '未知')
                                log(f"[游戏内] 资源-{name}: {val}")
                        except Exception as e:
                            log(f"[游戏内] 状态解析失败: {e}, 原始: {result}")
                    else:
                        log(f"[游戏内] 状态查询失败: {result}")
                except Exception as e:
                    log_error(f"[游戏内] 查询异常: {e}")

            threading.Thread(target=query_game_status, daemon=True).start()
        else:
            log("[游戏内] DLL未注入，跳过游戏内状态查询")

        # 4. 配置信息
        log(f"[配置] 游戏路径: {self.config.get('game_path', '默认')}")
        log(f"[配置] 热键配置: {len(self.config.get('hotkeys', {}))} 个")

        log("========== 诊断日志结束 ==========")

    def on_clear_log(self):
        """清空日志（同时清空GUI显示和日志文件）"""
        # 清空GUI显示
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state=tk.DISABLED)
        # 清空日志文件
        try:
            # clear_log_file 已在文件顶部导入
            if clear_log_file():
                messagebox.showinfo("成功", "日志已清空")
                log("日志已清空")
            else:
                messagebox.showerror("失败", "清空日志文件失败，请检查文件权限")
        except Exception as e:
            messagebox.showerror("错误", f"清空日志时出错: {e}")

    def _report_probe(self, section, result):
        """把探查结果追加到统一报告文件（便于一次性复制）"""
        try:
            from src.logger import append_report
            append_report(section, str(result))
        except Exception as e:
            log_error(f"写入探查报告失败: {e}")

    def _run_full_probe(self):
        """一键全量探查：跑完所有探查/诊断并写入报告文件"""
        if not self.dll_injected:
            messagebox.showwarning("提示", "请先注入DLL并进入游戏存档。")
            return
        from src.logger import append_report
        append_report("— 全量探查开始 —", "")
        self._run_async(self._full_probe_worker)

    def _full_probe_worker(self):
        """全量探查工作线程（逐个执行并写入报告）"""
        from src.logger import append_report
        import src.world_tools as world_tools
        import src.advanced_tools as advanced_tools

        probes = [
            ("世界-市场物价", world_tools.probe_market),
            ("世界-产业链", world_tools.probe_industry_chain),
            ("世界-税收", world_tools.probe_tax),
            ("世界-流民灾害", world_tools.probe_refugee),
            ("世界-灾害控制", world_tools.probe_disaster),
            ("世界-知名度", world_tools.probe_reputation),
            ("世界-蓝图", world_tools.probe_blueprint),
            ("世界-NPC详情", world_tools.probe_npc_detail),
            ("世界-建筑明细", world_tools.list_building_detail),
            ("高级-时间系统", advanced_tools.diagnose_time_system),
            ("高级-速度状态", advanced_tools.get_time_speed_status),
            ("高级-天赋系统", advanced_tools.diagnose_talent),
            ("高级-城市品阶", advanced_tools.diagnose_boom),
            ("高级-地块", advanced_tools.probe_plots),
            ("高级-谋士", advanced_tools.probe_advisors),
            ("高级-Steam成就", advanced_tools.probe_steam_achievements),
            ("高级-时间流速实测", advanced_tools.measure_time_speed),
            ("基础-时间状态", advanced_tools.get_time_status),
            ("基础-人口状态", advanced_tools.get_population_status),
            ("基础-建筑列表", advanced_tools.get_building_list),
            ("基础-SimWorld", advanced_tools.get_simworld_status),
            ("基础-NPC列表", advanced_tools.get_npc_list),
        ]

        ok = 0
        for label, fn in probes:
            try:
                success, result = fn()
                append_report(label, str(result))
                ok += 1
                log(f"[全量探查] {label} 完成")
            except Exception as e:
                append_report(label, f"[异常] {e}")
                log_error(f"[全量探查] {label} 异常: {e}")

        append_report("— 全量探查结束 —", f"共 {ok}/{len(probes)} 项有输出")
        self.root.after(0, lambda: self.show_toast("全量探查完成，已写入 probe_report.txt", "success"))

    def _open_probe_report(self):
        """打开探查报告文件"""
        from src.logger import get_report_path
        path = get_report_path()
        if not os.path.exists(path):
            messagebox.showinfo("提示", "报告还不存在，先点「一键全量探查」。")
            return
        try:
            os.startfile(path)
        except Exception as e:
            messagebox.showerror("错误", f"打开报告失败：{e}")

    def _clear_probe_report(self):
        """清空探查报告"""
        from src.logger import clear_report
        if clear_report():
            messagebox.showinfo("成功", "探查报告已清空")
        else:
            messagebox.showerror("失败", "清空失败（文件可能被占用）")

    def _get_mod_path(self):
        """获取散文件MOD的路径（游戏目录下的sim_common）"""
        try:
            game_path = self.config.get("game_path", DEFAULT_GAME_PATH)
            return os.path.join(game_path, SIM_COMMON_REL)
        except Exception:
            return os.path.join(DEFAULT_GAME_PATH, SIM_COMMON_REL)

    def _check_mod_status(self):
        """检测散文件MOD是否已安装（冲突时红色高亮提示）"""
        mod_path = self._get_mod_path()
        if os.path.exists(mod_path):
            file_count = 0
            for root, dirs, files in os.walk(mod_path):
                file_count += len(files)
            self.mod_status_var.set(f"⚠ 冲突MOD已安装 ({file_count}个文件)")
            self.mod_status_label.config(foreground=T("error"))  # 红色高亮
            log(f"散文件MOD检测: 已安装，路径: {mod_path}，共{file_count}个文件")
            log_warning("检测到散文件MOD，可能与DLL注入版冲突，建议卸载")
        else:
            self.mod_status_var.set("✓ 未安装（无冲突）")
            self.mod_status_label.config(foreground=T("success"))  # 绿色
            log("散文件MOD检测: 未安装")

    def _get_mod_source_path(self):
        """获取散文件MOD的源路径

        查找顺序：
            1. PyInstaller 打包时通过 --add-data 打入 _MEIPASS/creative_mode_v1.0/sim_common
            2. 源码运行时项目根目录下的 creative_mode_v1.0/sim_common
            3. 以上都找不到时返回 None，调用方应弹出文件对话框让用户选择
        """
        # 1. 打包环境：_MEIPASS 下查找（需打包时 --add-data "creative_mode_v1.0;creative_mode_v1.0"）
        if getattr(sys, "frozen", False):
            base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
            src = os.path.join(base, "creative_mode_v1.0", "sim_common")
            if os.path.exists(src):
                return src
        # 2. 源码运行：项目根目录（src/gui/tab_settings.py 上溯三层）
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        src = os.path.join(project_dir, "creative_mode_v1.0", "sim_common")
        if os.path.exists(src):
            return src
        # 3. 找不到，返回 None，调用方应让用户手动选择
        return None

    def _install_mod(self):
        """安装散件MOD（复制sim_common目录到游戏目录）"""
        mod_path = self._get_mod_path()
        src_path = self._get_mod_source_path()
        if not src_path:
            # 自动查找失败，让用户手动选择散件MOD所在的 sim_common 目录
            messagebox.showinfo("选择源目录",
                "未自动找到散件MOD源目录。\n\n请在接下来的对话框中选择 creative_mode_v1.0\\sim_common 目录。")
            selected = filedialog.askdirectory(title="选择散件MOD的 sim_common 源目录")
            if not selected:
                self.mod_status_var.set("未安装")
                return
            # 校验所选目录名是否为 sim_common
            if os.path.basename(selected) != "sim_common":
                messagebox.showerror("错误",
                    f"所选目录名不是 sim_common：{os.path.basename(selected)}\n\n请选择 creative_mode_v1.0\\sim_common 目录。")
                return
            if not os.path.isdir(selected):
                messagebox.showerror("错误", "所选路径不是目录")
                return
            src_path = selected
        if os.path.exists(mod_path):
            messagebox.showinfo("提示", "散件MOD已安装，无需重复安装。\n\n如需重新安装，请先卸载。")
            self.mod_status_var.set("已安装")
            return
        try:
            # shutil 已在文件顶部导入
            shutil.copytree(src_path, mod_path)
            # 统计文件数
            file_count = sum(len(files) for _, _, files in os.walk(mod_path))
            self.mod_status_var.set(f"已安装 ({file_count}个文件)")
            messagebox.showinfo("成功", f"散件MOD已安装！\n\n路径: {mod_path}\n文件数: {file_count}\n\n请重启游戏后生效。")
            log(f"散件MOD已安装: {mod_path} (来源: {src_path})")
        except PermissionError:
            messagebox.showerror("错误", "安装失败：权限不足。\n\n请以管理员身份运行修改器。")
            log_error("安装散件MOD失败: 权限不足")
        except Exception as e:
            messagebox.showerror("错误", f"安装失败：{e}")
            log_error(f"安装散件MOD失败: {e}")

    def _uninstall_mod(self):
        """卸载散文件MOD（删除sim_common目录）"""
        mod_path = self._get_mod_path()
        if not os.path.exists(mod_path):
            messagebox.showinfo("提示", "未检测到散文件MOD，无需卸载")
            self.mod_status_var.set("未安装")
            return

        result = messagebox.askyesno("确认卸载",
            f"检测到散文件MOD位于：\n{mod_path}\n\n"
            f"卸载将删除整个sim_common目录。\n"
            f"建议先关闭游戏再卸载。\n\n"
            f"确定要卸载吗？")
        if not result:
            return

        try:
            # shutil 已在文件顶部导入
            shutil.rmtree(mod_path)
            self.mod_status_var.set("已卸载")
            messagebox.showinfo("成功", "散文件MOD已卸载！\n\n请重启游戏后再使用DLL注入版修改器。")
            log(f"散文件MOD已卸载: {mod_path}")
        except PermissionError:
            messagebox.showerror("失败", "删除失败，文件可能被游戏进程占用。\n请先关闭游戏后再试。")
            log_error("卸载散文件MOD失败: 权限不足或文件被占用")
        except Exception as e:
            messagebox.showerror("错误", f"卸载失败: {e}")
            log_error(f"卸载散文件MOD失败: {e}")
