"""
woldvein Trainer v0.3 - GUI 主界面
《平野孤鸿》(Ballads of Hongye) 全能修改器

功能说明：
    左侧导航 + 右侧内容页（PCL2 风格）GUI 界面，集成 6 个页面：
    1. 资源修改：9种资源+幸福度+知名度，实时显示当前值（每3秒刷新）
    2. 创造模式：鸿业满级/全建筑解锁/无限资源/无限制升级，子选项独立开关
    3. 游戏监控：进程/内存/日志/崩溃检测，SDK日志黑名单过滤
    4. 高级工具：NPC管理/时间天气/建造升级/SimWorld操作/品阶逐级提升
    5. 世界系统：市场物价/产业链/流民灾害/知名度/建筑精细操作
    6. 应用设置：诊断日志输出/日志路径管理/清空日志/散件MOD

    热键设置已独立为单独工具：hotkey_configurator.py

v0.3 新增：
    - 深色/浅色主题一键切换
    - 面板侧边滚动条（内容超出时可滚动）
    - 城市品阶逐级提升按钮
    - 反向恢复按钮组（每项功能旁加「恢复」）
    - 全地块解锁 / 谋士升满级 / Steam全成就

核心类：
    TrainerApp：主应用类，管理所有UI组件和状态

技术要点：
    - 异步执行：_run_async()避免UI卡死
    - 系统托盘：pystray实现最小化到托盘
    - Hook就绪验证：注入后执行return 1探测Lua通道
    - 按钮冷却：高级工具按钮3秒冷却防连点
    - Treeview深色主题：自定义样式适配深色界面
    - 资源当前值：每3秒通过LUA_GET_STATUS查询并刷新
    - 热键同步：热键切换创造模式后更新GUI状态
    - 进程检测：启动游戏前检测是否已运行，防止重复启动
"""
import os
import sys
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import time
import traceback

# 路径处理：兼容PyInstaller打包环境和源码运行
if getattr(sys, 'frozen', False):
    # PyInstaller打包后，_MEIPASS是临时解压目录
    PROJECT_ROOT = sys._MEIPASS
else:
    # 源码运行：__file__ = 项目根/src/gui/main_gui.py，需要往上3层到项目根
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sys.path.insert(0, PROJECT_ROOT)

from src.config import load_config, save_config
from src.constants import APP_VERSION
from src.logger import init_log, set_log_callback, log, log_success, log_error, log_warning, close_log
from src.injector import find_game_process, inject_dll, is_dll_injected, launch_game
from src.hotkey_manager import hotkey_manager
from src.game_monitor import game_monitor, set_game_root
from src.game_status import get_status_provider
from .widgets import T, build_recolor_map, recolor_widget_tree

# Mixin 标签页模块
from .tab_resource import ResourceTabMixin
from .tab_creative import CreativeTabMixin
from .tab_hotkey import HotkeyTabMixin
from .tab_monitor import MonitorTabMixin
from .tab_advanced import AdvancedTabMixin
from .tab_world import WorldTabMixin
from .tab_cheat import CheatTabMixin
from .tab_all_tools import AllToolsTabMixin
from .tab_settings import SettingsTabMixin
from .theme import FONT_BOLD, FONT_MONO, FONT_TINY, ThemeManager, get_theme, get_theme_name
from .scrollable import ScrollableFrame
from .toast import ToastManager
from .tooltip import Tooltip, bind_tooltip

DLL_NAME = "woldvein_trainer.dll"


def _find_dll_path(config_dll_path=""):
    """
    自动查找DLL文件路径，按优先级：
    1. 配置文件中指定的路径
    2. EXE/脚本 同目录下的 woldvein_trainer.dll （发布版：用户放到EXE旁边）
    3. PROJECT_ROOT 下的 woldvein_trainer.dll （PyInstaller --add-data 内嵌）
    4. dist/ 目录下的 woldvein_trainer.dll （源码开发模式）

    返回找到的路径，都没找到则返回最后一个候选路径。
    """
    # EXE/脚本所在目录（用户放置DLL的预期位置）
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(sys.executable)
    else:
        exe_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    candidates = []
    if config_dll_path:
        candidates.append(config_dll_path)
    candidates.append(os.path.join(exe_dir, DLL_NAME))
    candidates.append(os.path.join(PROJECT_ROOT, DLL_NAME))
    candidates.append(os.path.join(PROJECT_ROOT, "dist", DLL_NAME))

    for p in candidates:
        if os.path.exists(p):
            return p
    return candidates[-1]  # 都不存在时返回最后一个，让后续报错提示显示


class TrainerApp(ResourceTabMixin, CreativeTabMixin, HotkeyTabMixin, MonitorTabMixin, AdvancedTabMixin, WorldTabMixin, CheatTabMixin, AllToolsTabMixin, SettingsTabMixin):
    """
    修改器主应用类。

    管理所有UI组件、游戏状态、DLL注入状态、热键注册等。
    初始化流程：
        1. 加载配置
        2. 初始化日志
        3. 设置窗口样式和主题
        4. 构建顶部栏（进程状态/DLL状态/注入按钮/启动按钮）
        5. 构建 6 个页面（左侧导航）+ 导航按钮
        6. 注册热键
        7. 启用热键（如果配置中启用）
        8. 初始化系统托盘
        9. 启动游戏进程自动检测
        10. 启动资源当前值定时刷新
    """

    def __init__(self, root):
        self.root = root
        self.config = load_config()
        self.game_pid = None
        self.game_process = None
        self.dll_injected = False
        self.monitor_running = False
        self._last_logged_pid = None
        self._current_time_speed = 1  # 当前时间流速（0=暂停, 1=正常, 2/3/4=倍速）

        # DLL路径：自动查找（配置 > 同目录 > dist/）
        cfg_dll = self.config.get("dll_path", "")
        self.dll_path = _find_dll_path(cfg_dll)

        # 设置游戏监控路径
        game_path = self.config.get("game_path", "")
        if game_path:
            set_game_root(game_path)

        # 初始化Toast管理器（全局轻提示）
        self.toast = None  # 将在_build_ui后初始化
        self._setup_window()
        self._setup_styles()
        self._build_ui()
        # Toast需要root可见后初始化
        self.toast = ToastManager(self.root)
        self._setup_log_callback()
        self._register_hotkeys()

        # 配置启用则自动启用热键（先于托盘初始化，避免托盘线程干扰）
        if self.config.get("hotkeys_enabled", True):
            self._enable_hotkeys_silent()

        # 启动后自动检测游戏
        self.root.after(1000, self.auto_detect_game)

        # 系统托盘（热键启用后再初始化）
        self.tray_icon = None
        self.root.after(2000, self._init_tray)
        # 最小化到托盘
        self.root.protocol("WM_DELETE_WINDOW", self._on_close_to_tray)

    def _init_tray(self):
        """初始化系统托盘"""
        try:
            import pystray
            from PIL import Image, ImageDraw

            # 生成一个简单的图标（64x64 蓝色圆形）
            image = Image.new('RGB', (64, 64), color='#1e1e2e')
            draw = ImageDraw.Draw(image)
            draw.ellipse([8, 8, 56, 56], fill='#89b4fa')
            draw.text((20, 18), "W", fill='#1e1e2e')

            menu = pystray.Menu(
                pystray.MenuItem("显示主窗口", self._tray_show_window, default=True),
                pystray.MenuItem("开启/关闭热键", self._tray_toggle_hotkey),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("退出", self._tray_quit)
            )

            self.tray_icon = pystray.Icon("woldvein_trainer", image, "平野孤鸿修改器", menu)
            # 在后台线程运行托盘（顶部已 import threading）
            threading.Thread(target=self.tray_icon.run, daemon=True).start()
        except Exception as e:
            log_warning(f"系统托盘初始化失败: {e}")

    def _tray_show_window(self, icon=None, item=None):
        """托盘菜单：显示主窗口"""
        self.root.after(0, lambda: (self.root.deiconify(), self.root.lift()))

    def _tray_toggle_hotkey(self, icon=None, item=None):
        """托盘菜单：切换热键"""
        self.root.after(0, self._toggle_hotkeys_simple)

    def _tray_quit(self, icon=None, item=None):
        """托盘菜单：退出"""
        self.root.after(0, self._on_quit)

    def _on_close_to_tray(self):
        """关闭按钮：最小化到托盘而不是退出"""
        self.root.withdraw()
        if self.tray_icon:
            try:
                self.tray_icon.notify("已最小化到系统托盘", "平野孤鸿修改器")
            except Exception as e:
                log_warning(f"托盘通知失败: {e}")

    def _on_quit(self):
        """真正退出"""
        # 保存配置（最小化到托盘后winfo_width可能返回1，先deiconify）
        try:
            self.root.deiconify()
        except Exception:
            pass
        w = self.root.winfo_width()
        h = self.root.winfo_height()
        if w and w > 1:
            self.config["window"]["width"] = w
        if h and h > 1:
            self.config["window"]["height"] = h
        # 热键设置已独立为工具，主修改器不再保存热键开关状态
        for key, var in self.creative_vars.items():
            self.config["creative_mode"][key] = var.get()
        self.config["theme"] = self._theme_name
        save_config(self.config)
        # 禁用热键
        hotkey_manager.disable()
        # 停止监控
        game_monitor.stop()
        # 关闭日志
        close_log()
        # 停止托盘
        try:
            if self.tray_icon:
                self.tray_icon.stop()
        except Exception as e:
            log_warning(f"托盘停止失败: {e}")
        self.root.destroy()

    def _setup_window(self):
        """设置窗口（尺寸：配置为空则按屏幕 80% 计算，上限 1280x800）"""
        self.root.title(f"平野孤鸿 全能修改器 v{APP_VERSION}")
        win = self.config.get("window", {}) or {}
        w = win.get("width")
        h = win.get("height")
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        # [FIX 2026-09-14] 旧版默认上限 1280x800，内容放不下 -> 必须最大化才能用全部。
        #   改为默认占屏幕约 92%（上限 1680x1000）；保存尺寸过小(<1400x860)视为不可用，改用默认。
        def_w = min(int(sw * 0.92), 1680)
        def_h = min(int(sh * 0.92), 1000)
        if not w or not h or int(w) < 1400 or int(h) < 860:
            w, h = def_w, def_h
        self.root.geometry(f"{int(w)}x{int(h)}")
        self.root.minsize(1020, 700)
        # 主题：从配置读取，默认深色
        self._theme_name = self.config.get("theme", "wechat")
        ThemeManager.apply(ttk.Style(), self.root, self._theme_name)

    def _setup_styles(self):
        """设置样式（委托给 ThemeManager 统一管理）"""
        style = ttk.Style()
        style.theme_use("clam")
        # 应用当前主题（_setup_window 中已设置）
        ThemeManager.apply(style, self.root, self._theme_name)

    def toggle_theme(self):
        """切换深色/浅色主题"""
        # 切换前记录旧色板，用于重绘 tk 原生控件
        old_palette = dict(get_theme())
        new_theme = ThemeManager.toggle(ttk.Style(), self.root)
        self._theme_name = new_theme
        self.config["theme"] = new_theme
        save_config(self.config)
        # 重绘 tk 原生控件（tk 控件不随 ttk 样式自动变色）
        try:
            recolor_widget_tree(self.root, build_recolor_map(old_palette, dict(get_theme())))
        except Exception as e:
            log_warning(f"主题重绘失败: {e}")
        # 更新日志区颜色
        bg, fg, insertbg = ThemeManager.get_log_colors()
        if hasattr(self, "log_text"):
            self.log_text.configure(bg=bg, fg=fg, insertbackground=insertbg)
        # 更新高级工具输出区颜色
        if hasattr(self, "adv_output_text"):
            self.adv_output_text.configure(bg=bg, fg=fg)
        # 更新主题切换按钮文字
        if hasattr(self, "theme_btn"):
            icon = "🌙" if new_theme == "dark" else "☀️"
            self.theme_btn.config(text=icon)
        log(f"主题已切换为: {new_theme}")

    def _build_ui(self):
        """构建UI：微信三栏布局（左侧导航 + 中间列表 + 右侧功能）"""
        # 主容器
        main_container = tk.Frame(self.root, bg=T("bg"))
        main_container.pack(fill=tk.BOTH, expand=True)

        # === 左侧导航栏（60px，深灰背景）===
        self._build_sidebar(main_container)

        # === 中间列表面板（260px，白色背景）===
        self._build_middle_panel(main_container)

        # === 右侧主功能面板（剩余宽度）===
        self._build_right_panel(main_container)

        # 默认显示主页
        self.root.after(100, lambda: self._switch_nav("home"))

    def _build_sidebar(self, parent):
        """左侧导航栏：深灰背景，图标按钮垂直排列"""
        self.sidebar = tk.Frame(parent, bg=T("bg_sidebar"), width=60)
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y)
        self.sidebar.pack_propagate(False)

        # 导航按钮配置：(key, icon, tooltip)
        nav_items = [
            ("home", "🏠", "主页"),
            ("process", "🎮", "进程"),
            ("modify", "⚡", "修改"),
            ("tools", "🔧", "工具"),
            ("save", "💾", "存档"),
            ("settings", "⚙️", "设置"),
        ]

        self._nav_buttons = {}
        for key, icon, label in nav_items:
            btn = tk.Button(self.sidebar, text=icon, bg=T("bg_sidebar"), fg=T("fg_sidebar"),
                           font=("微软雅黑", 18), bd=0, relief=tk.FLAT,
                           command=lambda k=key: self._switch_nav(k),
                           activebackground=T("bg_sidebar_sel"), activeforeground="white",
                           cursor="hand2")
            btn.pack(fill=tk.X, pady=3)
            try:
                bind_tooltip(btn, label)
            except Exception:
                pass
            self._nav_buttons[key] = btn

        # 底部 logo
        logo_frame = tk.Frame(self.sidebar, bg=T("bg_sidebar"))
        logo_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=15)
        tk.Label(logo_frame, text="🌿", bg=T("bg_sidebar"), fg=T("fg_sidebar_muted"),
                font=("微软雅黑", 22)).pack()

    def _build_middle_panel(self, parent):
        """中间列表面板：搜索框 + 功能列表"""
        self.middle_panel = tk.Frame(parent, bg="white", width=260)
        self.middle_panel.pack(side=tk.LEFT, fill=tk.Y)
        self.middle_panel.pack_propagate(False)

        # 搜索框
        search_frame = tk.Frame(self.middle_panel, bg="white")
        search_frame.pack(fill=tk.X, padx=12, pady=12)
        self.search_entry = tk.Entry(search_frame, font=("微软雅黑", 10), bd=0,
                                    relief=tk.FLAT, bg=T("bg_surface"), fg=T("fg"))
        self.search_entry.pack(fill=tk.X, ipady=7, padx=8, pady=2)
        self.search_entry.insert(0, "🔍 搜索功能...")
        self.search_entry.bind("<FocusIn>", self._on_search_focus)
        self.search_entry.bind("<FocusOut>", self._on_search_blur)

        # 分割线
        tk.Frame(self.middle_panel, bg=T("border"), height=1).pack(fill=tk.X)

        # 功能列表容器
        self.list_container = tk.Frame(self.middle_panel, bg="white")
        self.list_container.pack(fill=tk.BOTH, expand=True)

        self._list_items = {}
        self._current_list_key = None

    def _build_right_panel(self, parent):
        """右侧主功能面板：标题栏 + 功能控件 + 底部日志"""
        self.right_panel = tk.Frame(parent, bg=T("bg"))
        self.right_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 顶部标题栏
        self.title_bar = tk.Frame(self.right_panel, bg="white", height=56)
        self.title_bar.pack(fill=tk.X)
        self.title_bar.pack_propagate(False)
        self.title_label = tk.Label(self.title_bar, text="主页", font=("微软雅黑", 15, "bold"),
                                   bg="white", fg=T("fg"))
        self.title_label.pack(side=tk.LEFT, padx=24)

        # 右侧：主题切换按钮 + 状态指示灯
        self.theme_btn = tk.Button(self.title_bar, text="🌙", font=("微软雅黑", 12),
                                   bg="white", fg=T("fg_muted"), bd=0, relief=tk.FLAT,
                                   command=self.toggle_theme, cursor="hand2")
        self.theme_btn.pack(side=tk.RIGHT, padx=(0, 15))
        # 右侧状态指示灯
        self.status_indicator = tk.Label(self.title_bar, text="● 未检测到游戏",
                                         font=("微软雅黑", 9), bg="white", fg=T("fg_muted"))
        self.status_indicator.pack(side=tk.RIGHT, padx=24)

        # 分割线
        tk.Frame(self.right_panel, bg=T("border"), height=1).pack(fill=tk.X)

        # 功能内容区
        self.content_area = tk.Frame(self.right_panel, bg=T("bg"))
        self.content_area.pack(fill=tk.BOTH, expand=True)

        # 内容页容器
        self._pages = {}
        self._current_page = None

        # 构建所有功能页
        self._build_all_pages()

        # 底部日志区
        self._build_log_panel()

    def _build_all_pages(self):
        """构建所有功能页面"""
        # 主页
        home_page = tk.Frame(self.content_area, bg=T("bg"))
        self._pages["home"] = home_page
        self._build_home_page(home_page)

        # 进程页
        process_page = tk.Frame(self.content_area, bg=T("bg"))
        self._pages["process"] = process_page
        self._build_process_page(process_page)

        # 修改页（资源+创造模式）
        modify_page = tk.Frame(self.content_area, bg=T("bg"))
        self._pages["modify"] = modify_page
        self._build_resource_tab(modify_page)

        # 工具页（高级+世界+作弊合并）
        tools_page = tk.Frame(self.content_area, bg=T("bg"))
        self._pages["tools"] = tools_page
        try:
            self._build_all_tools_tab(tools_page)
        except Exception as e:
            tk.Label(tools_page, text=f"工具页加载失败: {e}", bg=T("bg"), fg=T("error")).pack(pady=20)

        # 存档页
        save_page = tk.Frame(self.content_area, bg=T("bg"))
        self._pages["save"] = save_page
        self._build_save_page(save_page)

        # 设置页
        settings_page = tk.Frame(self.content_area, bg=T("bg"))
        self._pages["settings"] = settings_page
        self._build_settings_tab(settings_page)

    def _build_home_page(self, parent):
        """主页：概览 + 快速操作"""
        # 欢迎区
        welcome = tk.Frame(parent, bg=T("bg"))
        welcome.pack(pady=40)
        tk.Label(welcome, text="平野孤鸿 全能修改器", font=("微软雅黑", 22, "bold"),
                bg=T("bg"), fg=T("fg")).pack()
        tk.Label(welcome, text=f"v{APP_VERSION}", font=("微软雅黑", 11),
                bg=T("bg"), fg=T("fg_muted")).pack(pady=5)

        # 状态卡片
        status_frame = tk.Frame(parent, bg=T("bg"))
        status_frame.pack(pady=20)

        cards = [
            ("游戏状态", "未运行", T("fg_muted")),
            ("DLL状态", "未注入", T("fg_muted")),
            ("Lua通道", "未连接", T("fg_muted")),
        ]
        for i, (title, value, color) in enumerate(cards):
            card = tk.Frame(status_frame, bg="white", width=180, height=100,
                           highlightbackground=T("border"), highlightthickness=1)
            card.pack(side=tk.LEFT, padx=10)
            card.pack_propagate(False)
            tk.Label(card, text=title, font=("微软雅黑", 10), bg="white",
                    fg=T("fg_muted")).pack(pady=(15, 5))
            tk.Label(card, text=value, font=("微软雅黑", 14, "bold"), bg="white",
                    fg=color).pack()

        # 快速操作按钮
        btn_frame = tk.Frame(parent, bg=T("bg"))
        btn_frame.pack(pady=30)
        tk.Button(btn_frame, text="🚀 启动游戏", font=("微软雅黑", 11, "bold"),
                 bg=T("accent"), fg="white", bd=0, relief=tk.FLAT,
                 command=self.on_launch_game, width=16, height=2,
                 cursor="hand2", activebackground=T("accent_hover")).pack(side=tk.LEFT, padx=10)
        tk.Button(btn_frame, text="🔌 注入DLL", font=("微软雅黑", 11, "bold"),
                 bg=T("accent"), fg="white", bd=0, relief=tk.FLAT,
                 command=self.on_inject_dll, width=16, height=2,
                 cursor="hand2", activebackground=T("accent_hover")).pack(side=tk.LEFT, padx=10)

    def _build_process_page(self, parent):
        """进程页：进程检测 + 启动 + 注入"""
        tk.Label(parent, text="进程管理", font=("微软雅黑", 16, "bold"),
                bg=T("bg"), fg=T("fg")).pack(anchor=tk.W, padx=20, pady=(20, 10))

        # 操作按钮区
        btn_frame = tk.Frame(parent, bg=T("bg"))
        btn_frame.pack(fill=tk.X, padx=20, pady=10)
        tk.Button(btn_frame, text="🔍 检测游戏进程", font=("微软雅黑", 10),
                 bg="white", fg=T("fg"), bd=1, relief=tk.SOLID,
                 command=self.auto_detect_game, width=15, height=2,
                 cursor="hand2").pack(side=tk.LEFT, padx=5)
        self.launch_btn = tk.Button(btn_frame, text="🚀 启动游戏", font=("微软雅黑", 10),
                 bg=T("accent"), fg="white", bd=0, relief=tk.FLAT,
                 command=self.on_launch_game, width=15, height=2,
                 cursor="hand2")
        self.launch_btn.pack(side=tk.LEFT, padx=5)
        self.inject_btn = tk.Button(btn_frame, text="🔌 注入DLL", font=("微软雅黑", 10),
                 bg=T("accent"), fg="white", bd=0, relief=tk.FLAT,
                 command=self.on_inject_dll, width=15, height=2,
                 cursor="hand2", state=tk.DISABLED)
        self.inject_btn.pack(side=tk.LEFT, padx=5)

        # 进程信息区
        info_frame = tk.Frame(parent, bg="white", highlightbackground=T("border"),
                             highlightthickness=1)
        info_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        tk.Label(info_frame, text="进程信息", font=("微软雅黑", 12, "bold"),
                bg="white", fg=T("fg")).pack(anchor=tk.W, padx=15, pady=10)
        self.process_info_label = tk.Label(info_frame, text="未检测到游戏进程",
                                          font=("微软雅黑", 10), bg="white", fg=T("fg_muted"),
                                          justify=tk.LEFT)
        self.process_info_label.pack(anchor=tk.W, padx=15, pady=10)

    def _build_save_page(self, parent):
        """存档页"""
        tk.Label(parent, text="存档管理", font=("微软雅黑", 16, "bold"),
                bg=T("bg"), fg=T("fg")).pack(anchor=tk.W, padx=20, pady=(20, 10))
        tk.Label(parent, text="存档功能开发中...", font=("微软雅黑", 11),
                bg=T("bg"), fg=T("fg_muted")).pack(pady=40)

    def _switch_nav(self, key):
        """切换左侧导航，更新中间列表和右侧内容"""
        # 更新导航按钮选中态
        for k, btn in self._nav_buttons.items():
            if k == key:
                btn.config(bg=T("bg_sidebar_sel"))
            else:
                btn.config(bg=T("bg_sidebar"))

        # 更新中间列表
        self._update_middle_list(key)

        # 更新右侧标题
        titles = {"home": "主页", "process": "进程管理", "modify": "修改功能",
                  "tools": "高级工具", "save": "存档管理", "settings": "设置"}
        self.title_label.config(text=titles.get(key, key))

        # 显示对应页面
        self._show_page(key)

    def _update_middle_list(self, nav_key):
        """更新中间功能列表"""
        # 清空列表
        for widget in self.list_container.winfo_children():
            widget.destroy()

        # 各导航对应的功能列表
        lists = {
            "home": ["游戏概览", "快速操作", "状态监控"],
            "process": ["游戏进程", "DLL注入", "启动游戏"],
            "modify": ["资源修改", "创造模式", "数值调整"],
            "tools": ["高级工具", "世界系统", "一键作弊"],
            "save": ["存档列表", "存档备份", "存档恢复"],
            "settings": ["通用设置", "主题设置", "关于"],
        }

        items = lists.get(nav_key, [])
        self._list_items = {}
        for i, item in enumerate(items):
            item_frame = tk.Frame(self.list_container, bg="white", cursor="hand2")
            item_frame.pack(fill=tk.X, padx=8, pady=1)

            label = tk.Label(item_frame, text=item, font=("微软雅黑", 10),
                           bg="white", fg=T("fg"))
            label.pack(side=tk.LEFT, padx=15, pady=10)

            # 状态红点（进程页第一个显示）
            if nav_key == "process" and i == 0:
                dot = tk.Label(item_frame, text="●", font=("微软雅黑", 7),
                              bg="white", fg=T("error"))
                dot.pack(side=tk.RIGHT, padx=10)

            # 悬停效果
            def on_enter(e, f=item_frame, l=label):
                f.config(bg=T("bg_elevated"))
                l.config(bg=T("bg_elevated"))
            def on_leave(e, f=item_frame, l=label):
                f.config(bg="white")
                l.config(bg="white")
            item_frame.bind("<Enter>", on_enter)
            item_frame.bind("<Leave>", on_leave)
            label.bind("<Enter>", on_enter)
            label.bind("<Leave>", on_leave)

            # 点击
            def on_click(e, k=nav_key, idx=i, f=item_frame, l=label):
                self._on_list_item_click(k, idx, f, l)
            item_frame.bind("<Button-1>", on_click)
            label.bind("<Button-1>", on_click)

            self._list_items[i] = (item_frame, label)

    def _on_list_item_click(self, nav_key, index, frame, label):
        """中间列表项点击"""
        # 更新选中态
        for i, (f, l) in self._list_items.items():
            if i == index:
                f.config(bg=T("bg_selected"))
                l.config(bg=T("bg_selected"), fg=T("accent"))
            else:
                f.config(bg="white")
                l.config(bg="white", fg=T("fg"))

    def _show_page(self, key):
        """显示指定页面"""
        if key == self._current_page:
            return
        for k, page in self._pages.items():
            if k == key:
                page.pack(fill=tk.BOTH, expand=True)
            else:
                page.pack_forget()
        self._current_page = key

    def _on_search_focus(self, event):
        if self.search_entry.get() == "🔍 搜索功能...":
            self.search_entry.delete(0, tk.END)

    def _on_search_blur(self, event):
        if not self.search_entry.get():
            self.search_entry.insert(0, "🔍 搜索功能...")

    def _build_topbar(self):
        """顶部栏（三栏布局下不再需要，保留空方法兼容）"""
        pass

    def _make_page(self, key, label):
        """创建内容页（兼容旧代码，三栏布局下不使用）"""
        page = tk.Frame(self.content_area, bg=T("bg"))
        self._pages[key] = page
        return page

    def _build_log_panel(self):
        """底部日志面板：可拖拽调整高度、可展开/收起"""
        self._log_expanded = True
        self._log_height = 160  # 默认高度
        self._log_min_height = 32  # 最小高度（收起时）

        # 日志主容器
        self.log_frame = tk.Frame(self.right_panel, bg="white", height=self._log_height)
        self.log_frame.pack(fill=tk.X, side=tk.BOTTOM)
        self.log_frame.pack_propagate(False)

        # === 顶部可拖拽分隔条 ===
        self.log_splitter = tk.Frame(self.log_frame, bg=T("border"), height=4, cursor="sb_v_double_arrow")
        self.log_splitter.pack(fill=tk.X, side=tk.TOP)
        # 拖拽事件
        self.log_splitter.bind("<Button-1>", self._on_log_splitter_press)
        self.log_splitter.bind("<B1-Motion>", self._on_log_splitter_drag)
        self.log_splitter.bind("<Enter>", lambda e: self.log_splitter.config(bg=T("accent")))
        self.log_splitter.bind("<Leave>", lambda e: self.log_splitter.config(bg=T("border")))

        # === 标题栏 ===
        self.log_header = tk.Frame(self.log_frame, bg="white", height=28)
        self.log_header.pack(fill=tk.X, side=tk.TOP)
        self.log_header.pack_propagate(False)

        # 展开/收起箭头
        self.log_toggle_btn = tk.Label(self.log_header, text="▼", font=("微软雅黑", 9),
                                      bg="white", fg=T("fg_muted"), cursor="hand2")
        self.log_toggle_btn.pack(side=tk.LEFT, padx=(12, 6))
        self.log_toggle_btn.bind("<Button-1>", lambda e: self._toggle_log_panel())

        # 标题
        tk.Label(self.log_header, text="📋 操作日志", font=("微软雅黑", 10, "bold"),
                bg="white", fg=T("fg")).pack(side=tk.LEFT)
        # 点击标题栏也能收起
        self.log_header.bind("<Button-1>", lambda e: self._toggle_log_panel())

        # 右侧按钮
        btn_frame = tk.Frame(self.log_header, bg="white")
        btn_frame.pack(side=tk.RIGHT, padx=10)
        tk.Button(btn_frame, text="清空", font=("微软雅黑", 9),
                 bg="white", fg=T("fg_muted"), bd=0, relief=tk.FLAT,
                 command=self.on_clear_log, cursor="hand2").pack(side=tk.RIGHT, padx=5)

        # === 日志内容区 ===
        self.log_content = tk.Frame(self.log_frame, bg="white")
        self.log_content.pack(fill=tk.BOTH, expand=True, side=tk.TOP)

        log_bg, log_fg, log_insert = ThemeManager.get_log_colors()
        self.log_text = scrolledtext.ScrolledText(self.log_content, bg=log_bg, fg=log_fg,
                                                     font=FONT_MONO, insertbackground=log_insert,
                                                     borderwidth=0)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.log_text.configure(state=tk.DISABLED)

    def _on_log_splitter_press(self, event):
        """拖拽分隔条：记录起始位置"""
        self._splitter_start_y = event.y_root
        self._splitter_start_height = self.log_frame.winfo_height()

    def _on_log_splitter_drag(self, event):
        """拖拽分隔条：调整日志高度"""
        if not hasattr(self, '_splitter_start_y'):
            return
        delta = self._splitter_start_y - event.y_root  # 向上拖=增大高度
        new_height = self._splitter_start_height + delta
        # 限制高度范围
        new_height = max(80, min(new_height, 500))
        self._log_height = new_height
        if self._log_expanded:
            self.log_frame.config(height=new_height)

    def _toggle_log_panel(self):
        """展开/收起日志面板"""
        if self._log_expanded:
            # 收起：只显示标题栏
            self.log_content.pack_forget()
            self.log_frame.config(height=32)
            self.log_toggle_btn.config(text="▶")
            self._log_expanded = False
        else:
            # 展开：恢复内容
            self.log_content.pack(fill=tk.BOTH, expand=True, side=tk.TOP)
            self.log_frame.config(height=self._log_height)
            self.log_toggle_btn.config(text="▼")
            self._log_expanded = True

    def _setup_log_callback(self):
        """设置日志回调"""
        def callback(line, level="INFO"):
            self.root.after(0, lambda: self._append_log(line, level))
        set_log_callback(callback)

    def _append_log(self, line, level="INFO"):
        """追加日志"""
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, line + "\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _run_async(self, func, *args):
        """异步执行函数（薄壳，实现已收敛到 src.gui.async_helper.run_async）

        保留此方法作为兼容壳，避免所有 tab 中的 self._run_async(...) 调用点都要改。
        """
        from src.gui.async_helper import run_async
        run_async(self.root, func, *args)

    def show_toast(self, message, level="info"):
        """显示Toast轻提示（便捷方法）"""
        if self.toast:
            self.toast.show(message, level)

    def update_modify_buttons_state(self):
        """防呆设计：根据DLL注入状态统一置灰/启用所有修改按钮

        游戏未运行或DLL未注入时，资源增加、创造模式开关等修改按钮置灰，
        并通过Tooltip提示"请先启动游戏并注入DLL"。
        """
        enabled = self.dll_injected and getattr(self, '_dll_verified', False)
        state = tk.NORMAL if enabled else tk.DISABLED
        # 资源修改页按钮
        if hasattr(self, 'resource_buttons'):
            for btn in self.resource_buttons:
                btn.config(state=state)
        # 创造模式按钮（tab_creative 中实际属性名为 creative_btn）
        if hasattr(self, 'creative_btn'):
            self.creative_btn.config(state=state)
        # 高级工具按钮各自在点击时有 dll_injected 检查，暂不统一置灰

    # ========== 顶部栏事件 ==========

    def auto_detect_game(self):
        """自动检测游戏"""
        if self.config.get("auto_detect_game", True):
            self.on_detect_game()

    def on_detect_game(self):
        """检测游戏进程（只在PID变化时记录日志）

        僵尸进程识别：游戏正常运行时内存占用应在数百MB以上，
        若检测到 BalladsOfHongye.exe 但内存 < 50MB 且无主窗口，
        判定为僵尸进程（常见于游戏崩溃后进程未完全退出），
        此时显示警告并禁用注入按钮（注入到僵尸进程无意义）。
        """
        pid, proc = find_game_process()
        if pid:
            self.game_pid = pid
            self.game_process = proc

            # 僵尸进程检测：检查内存占用和主窗口
            is_zombie = False
            try:
                if proc is not None:
                    mem_bytes = proc.memory_info().rss
                    mem_mb = mem_bytes / (1024 * 1024)
                    # 内存小于50MB 且 无主窗口标题 → 僵尸进程
                    if mem_mb < 50:
                        try:
                            has_window = bool(proc.status() and proc.memory_info())
                            # 进一步检查：无主窗口的进程
                            import ctypes
                            hwnd = ctypes.windll.user32.FindWindowW(None, "Ballads of Hongye")
                            if not hwnd:
                                is_zombie = True
                        except Exception:
                            is_zombie = True
            except Exception:
                pass  # 无法读取进程信息，不判定为僵尸

            if is_zombie:
                self.dll_injected = False
                self._dll_verified = False
                get_status_provider().set_dll_ready(False)
                self.status_indicator.config(text=f"● 僵尸进程 (PID: {pid})", fg="#fa5151", bg="white")
                pass  # 状态已合并到status_indicator
                self.inject_btn.config(text="注入DLL", state=tk.DISABLED)
                if self._last_logged_pid != pid:
                    log_warning(f"检测到僵尸进程 PID={pid}（内存<50MB无窗口），建议重启电脑后清理")
                    self._last_logged_pid = pid
            else:
                self.status_indicator.config(text=f"● 游戏运行中 (PID: {pid})", fg="#07C160", bg="white")
                # 检查DLL是否已注入
                dll_name = os.path.basename(self.dll_path)
                if is_dll_injected(pid, dll_name):
                    was_injected = self.dll_injected
                    self.dll_injected = True
                    self.status_indicator.config(text=f"● 游戏运行中 | DLL已注入", fg="#07C160", bg="white")
                    self.inject_btn.config(text="已注入", state=tk.DISABLED)
                    # 首次检测到DLL已注入（修改器后打开的情况），先标记已验证再异步确认hook
                    # [FIX 2026-09-14] 原顺序把置位放在 update 之后，导致按钮要多等5秒才可用
                    if not was_injected and not getattr(self, '_dll_verified', False):
                        self._dll_verified = True
                        self._run_async(self._wait_dll_ready_silent)
                    self.update_modify_buttons_state()
                else:
                    self.dll_injected = False
                    self._dll_verified = False
                    # DLL未注入，通知GameStatusProvider停止Lua查询（避免超时刷屏）
                    get_status_provider().set_dll_ready(False)
                    self.status_indicator.config(text=f"● 游戏运行中 | DLL未注入", fg="#fa9d3b", bg="white")
                    self.inject_btn.config(text="注入DLL", state=tk.NORMAL)
                    self.update_modify_buttons_state()
                if self._last_logged_pid != pid:
                    # 不重复日志，game_monitor 已经记录过"游戏启动，PID=xxx"
                    self._last_logged_pid = pid
        else:
            if self._last_logged_pid is not None:
                log("游戏进程已退出")
                self._last_logged_pid = None
            self.game_pid = None
            self.game_process = None
            self._dll_verified = False
            # 游戏未运行，通知GameStatusProvider停止Lua查询
            get_status_provider().set_dll_ready(False)
            self.status_indicator.config(text="● 未检测到游戏", fg="#fa9d3b", bg="white")
            pass  # 状态已合并到status_indicator
            self.inject_btn.config(text="注入DLL", state=tk.DISABLED)
            self.update_modify_buttons_state()

        # 每5秒重新检测
        self.root.after(5000, self.on_detect_game)

    def _wait_dll_ready_silent(self):
        """静默等待DLL hook就绪（不弹窗，只写日志）"""
        from src.lua_engine import execute_lua
        for i in range(10):
            time.sleep(0.5)
            try:
                ok, result = execute_lua("return 1", timeout=2.0)
                if ok and result == 1:
                    # Hook就绪，通知GameStatusProvider可以开始Lua查询
                    self._inject_trainer_lib()
                    get_status_provider().set_dll_ready(True)
                    # [FIX 2026-09-14] 标记DLL已验证，否则创造模式等按钮会被防呆逻辑永久置灰
                    self._dll_verified = True
                    self.root.after(0, lambda: log_success("DLL Hook就绪，Lua执行通道已连通"))
                    self.root.after(0, self.update_modify_buttons_state)
                    return
            except Exception as e:
                log_warning(f"Hook就绪检测异常: {e}")
        self.root.after(0, lambda: log_warning("DLL已注入但Hook未就绪，请进入游戏存档后再使用修改功能"))
        # [FIX 2026-09-14] Hook 未就绪时按钮应保持灰色，避免“点了没反应”
        self._dll_verified = False
        self.root.after(0, self.update_modify_buttons_state)

    def _inject_trainer_lib(self):
        """注入公共 Lua 辅助库（__trainer_emit / __trainer_hook 等）

        在 DLL Hook 就绪、Lua 通道打通后调用一次。失败不影响主流程，
        仅记警告（个别脚本会退化为不刷新UI）。
        """
        try:
            from src.lua_engine import execute_lua
            from src.lua_lib import LUA_TRAINER_LIB
            ok, result = execute_lua(LUA_TRAINER_LIB, timeout=3.0)
            if not ok:
                log_warning(f"Lua 辅助库注入未确认: {result}")
        except Exception as e:
            log_warning(f"Lua 辅助库注入失败: {e}")

    def on_launch_game(self):
        """启动游戏（先检测是否已在运行）"""
        # 先检测是否已有游戏进程
        existing_pid, _ = find_game_process()
        if existing_pid:
            messagebox.showwarning("游戏已在运行",
                                   f"检测到游戏进程已在运行中 (PID: {existing_pid})。\n\n"
                                   "请勿重复启动游戏，如需重启请先关闭现有游戏进程。")
            log_warning(f"启动游戏被拒绝：游戏已在运行 (PID={existing_pid})")
            return

        log("正在启动游戏...")
        launch_game(self.config["steam_app_id"])
        messagebox.showinfo("启动游戏", "已请求通过Steam启动游戏，请等待游戏窗口出现。")

    def on_inject_dll(self):
        """注入DLL"""
        if not self.game_pid:
            messagebox.showwarning("提示", "未检测到游戏进程，请先启动游戏。")
            return

        if not os.path.exists(self.dll_path):
            messagebox.showerror("错误", f"DLL文件不存在: {self.dll_path}")
            return

        log(f"正在注入DLL到 PID={self.game_pid}...")
        success, msg = inject_dll(self.game_pid, self.dll_path)

        if success:
            self.dll_injected = True
            self.status_indicator.config(text=f"● 游戏运行中 | DLL已注入", fg="#07C160", bg="white")
            self.inject_btn.config(text="已注入", state=tk.DISABLED)
            log_success("DLL注入成功，正在等待Hook就绪...")
            self.update_modify_buttons_state()
            # 异步等待DLL hook就绪并验证
            self._run_async(self._wait_dll_ready)
        else:
            log_error(f"DLL注入失败: {msg}")
            messagebox.showerror("失败", f"DLL注入失败:\n{msg}")

    def _wait_dll_ready(self):
        """等待DLL hook安装完成，通过执行简单Lua命令验证"""
        from src.lua_engine import execute_lua
        # 最多等待5秒，每0.5秒尝试一次
        for i in range(10):
            time.sleep(0.5)
            try:
                ok, result = execute_lua("return 1", timeout=2.0)
                if ok and result == 1:
                    # Hook就绪：注入公共Lua辅助库，再通知GameStatusProvider开始Lua查询
                    self._inject_trainer_lib()
                    get_status_provider().set_dll_ready(True)
                    # [FIX 2026-09-14] 标记DLL已验证，否则创造模式等按钮会被防呆逻辑永久置灰
                    self._dll_verified = True
                    self.root.after(0, lambda: log_success("DLL Hook就绪，Lua执行通道已连通"))
                    self.root.after(0, lambda: messagebox.showinfo("成功", "DLL注入成功！Hook已就绪，现在可以使用修改功能。"))
                    self.root.after(0, self.update_modify_buttons_state)
                    return
            except Exception as e:
                log_warning(f"Hook就绪检测异常: {e}")
        # 超时但DLL已注入，可能hook还在重试
        self.root.after(0, lambda: log_warning("DLL已注入但Hook未就绪，Lua执行可能暂时无效，请稍候重试或重新注入"))
        # [FIX 2026-09-14] Hook 未就绪时按钮应保持灰色，避免“点了没反应”
        self._dll_verified = False
        self.root.after(0, self.update_modify_buttons_state)
        self.root.after(0, lambda: messagebox.showwarning("注意", "DLL已注入，但Hook尚未就绪。\n\n可能原因：游戏还在主菜单/加载中。\n请进入游戏存档后再使用修改功能。"))

    # ========== 创造模式事件 ==========

    def on_close(self):
        """关闭应用（调用真正的退出逻辑）"""
        self._on_quit()


def main():
    """主函数"""
    init_log()

    root = tk.Tk()
    app = TrainerApp(root)

    root.mainloop()


if __name__ == "__main__":
    main()




