"""
woldvein Trainer v0.4.6 - 系统诊断模块

一键收集系统环境、修改器状态、游戏状态等信息，生成诊断报告。
用于排查问题、用户反馈时附带环境信息。

诊断项：
    1. 系统信息（OS、Python、CPU、内存、磁盘）
    2. 修改器状态（版本、DLL、配置、日志）
    3. 游戏状态（进程、路径、存档、Steam）
    4. 环境检查（依赖库、权限、网络）
"""
import os
import sys
import platform
import datetime


def run_full_diagnosis(game_pid=None, dll_path=None, config=None):
    """运行完整诊断，返回诊断报告文本。

    参数：
        game_pid: 游戏进程PID（可选）
        dll_path: DLL路径（可选）
        config: 配置字典（可选）

    返回：
        诊断报告字符串
    """
    lines = []
    lines.append("=" * 60)
    lines.append("  woldvein Trainer 系统诊断报告")
    lines.append(f"  生成时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("=" * 60)

    # 1. 系统信息
    lines.append("")
    lines.append("【1. 系统信息】")
    lines.extend(_diagnose_system())

    # 2. 修改器状态
    lines.append("")
    lines.append("【2. 修改器状态】")
    lines.extend(_diagnose_trainer(dll_path, config))

    # 3. 游戏状态
    lines.append("")
    lines.append("【3. 游戏状态】")
    lines.extend(_diagnose_game(game_pid, config))

    # 4. 环境检查
    lines.append("")
    lines.append("【4. 环境检查】")
    lines.extend(_diagnose_environment())

    # 总结
    lines.append("")
    lines.append("=" * 60)
    lines.append("  诊断完成")
    lines.append("=" * 60)

    return "\n".join(lines)


def _diagnose_system():
    """诊断系统信息"""
    lines = []
    try:
        lines.append(f"  操作系统: {platform.system()} {platform.release()} ({platform.version()})")
        lines.append(f"  系统架构: {platform.machine()}")
        lines.append(f"  Python版本: {sys.version.split()[0]} ({platform.architecture()[0]})")
        lines.append(f"  处理器: {platform.processor() or '未知'}")

        # CPU核心数
        try:
            import psutil
            lines.append(f"  CPU核心: {psutil.cpu_count(logical=True)} 逻辑 / {psutil.cpu_count(logical=False)} 物理")
            mem = psutil.virtual_memory()
            lines.append(f"  总内存: {mem.total / 1024 / 1024 / 1024:.1f} GB (可用 {mem.available / 1024 / 1024 / 1024:.1f} GB)")
        except ImportError:
            lines.append("  CPU/内存: psutil 未安装")

        # 磁盘空间
        try:
            import psutil
            if getattr(sys, "frozen", False):
                drive = os.path.splitdrive(sys.executable)[0]
            else:
                drive = os.path.splitdrive(os.path.abspath(__file__))[0]
            disk = psutil.disk_usage(drive + "\\")
            lines.append(f"  磁盘({drive}): 总 {disk.total / 1024**3:.1f} GB, 可用 {disk.free / 1024**3:.1f} GB")
        except Exception:
            pass

    except Exception as e:
        lines.append(f"  系统信息获取失败: {e}")
    return lines


def _diagnose_trainer(dll_path=None, config=None):
    """诊断修改器状态"""
    lines = []
    try:
        # 版本
        try:
            from .constants import APP_VERSION
            lines.append(f"  修改器版本: {APP_VERSION}")
        except Exception:
            lines.append("  修改器版本: 未知")

        # 运行模式
        if getattr(sys, "frozen", False):
            lines.append(f"  运行模式: 打包EXE ({sys.executable})")
        else:
            lines.append(f"  运行模式: 源码运行 ({os.path.abspath(__file__)})")

        # DLL
        if dll_path:
            if os.path.exists(dll_path):
                size = os.path.getsize(dll_path)
                lines.append(f"  DLL文件: {dll_path} ({size / 1024:.1f} KB) [OK]")
            else:
                lines.append(f"  DLL文件: {dll_path} [不存在!]")
        else:
            lines.append("  DLL文件: 未指定")

        # 配置文件
        if config:
            lines.append(f"  配置: 已加载 ({len(config)} 个键)")
            game_path = config.get("game_path", "")
            if game_path:
                if os.path.exists(game_path):
                    lines.append(f"  游戏路径: {game_path} [存在]")
                else:
                    lines.append(f"  游戏路径: {game_path} [不存在!]")
        else:
            lines.append("  配置: 未传入")

        # 日志文件
        try:
            from .logger import get_log_path
            log_path = get_log_path()
            if os.path.exists(log_path):
                size = os.path.getsize(log_path)
                lines.append(f"  日志文件: {log_path} ({size / 1024:.1f} KB)")
            else:
                lines.append(f"  日志文件: {log_path} [不存在]")
        except Exception:
            pass

    except Exception as e:
        lines.append(f"  修改器状态获取失败: {e}")
    return lines


def _diagnose_game(game_pid=None, config=None):
    """诊断游戏状态"""
    lines = []
    try:
        # 进程状态
        if game_pid:
            try:
                import psutil
                p = psutil.Process(game_pid)
                lines.append(f"  游戏进程: PID={game_pid}, 名称={p.name()} [运行中]")
                lines.append(f"  进程内存: {p.memory_info().rss / 1024 / 1024:.0f} MB")
                lines.append(f"  进程CPU: {p.cpu_percent():.1f}%")
                lines.append(f"  进程线程: {p.num_threads()}")
            except psutil.NoSuchProcess:
                lines.append(f"  游戏进程: PID={game_pid} [已退出!]")
            except Exception as e:
                lines.append(f"  游戏进程: PID={game_pid} [查询失败: {e}]")
        else:
            lines.append("  游戏进程: 未注入")

        # 游戏路径
        if config:
            game_path = config.get("game_path", "")
            if game_path and os.path.exists(game_path):
                # 检查关键文件
                exe_path = os.path.join(game_path, "bin64", "BalladsOfHongye.exe")
                lua_dll = os.path.join(game_path, "bin64", "Lua5X64.dll")
                save_dir = os.path.join(game_path, "storage", "offlineuser")

                lines.append(f"  游戏主程序: {'[存在]' if os.path.exists(exe_path) else '[缺失!]'} {exe_path}")
                lines.append(f"  Lua DLL: {'[存在]' if os.path.exists(lua_dll) else '[缺失!]'} {lua_dll}")
                lines.append(f"  存档目录: {'[存在]' if os.path.exists(save_dir) else '[不存在]'} {save_dir}")

                # 存档文件数量
                if os.path.exists(save_dir):
                    saves = [f for f in os.listdir(save_dir) if f.endswith(".dat")]
                    lines.append(f"  存档文件: {len(saves)} 个")
    except Exception as e:
        lines.append(f"  游戏状态获取失败: {e}")
    return lines


def _diagnose_environment():
    """诊断环境依赖"""
    lines = []
    try:
        # 检查关键依赖
        deps = [
            ("psutil", "psutil"),
            ("ctypes", "ctypes"),
            ("tkinter", "tkinter"),
        ]
        for name, module in deps:
            try:
                __import__(module)
                lines.append(f"  依赖 {name}: [OK]")
            except ImportError:
                lines.append(f"  依赖 {name}: [缺失!]")

        # 检查写权限（程序目录）
        try:
            if getattr(sys, "frozen", False):
                test_dir = os.path.dirname(sys.executable)
            else:
                test_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            test_file = os.path.join(test_dir, ".write_test")
            with open(test_file, "w") as f:
                f.write("test")
            os.remove(test_file)
            lines.append(f"  目录写权限: [OK] ({test_dir})")
        except Exception as e:
            lines.append(f"  目录写权限: [失败!] {e}")

        # 检查管理员权限
        try:
            import ctypes
            is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
            lines.append(f"  管理员权限: {'[是]' if is_admin else '[否]'}")
        except Exception:
            pass

    except Exception as e:
        lines.append(f"  环境检查失败: {e}")
    return lines


def export_diagnosis_report(report_text, output_path=None):
    """导出诊断报告到文件。

    返回：
        (success, output_path)
    """
    if not output_path:
        if getattr(sys, "frozen", False):
            base = os.path.dirname(sys.executable)
        else:
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(base, f"diagnosis_report_{timestamp}.txt")

    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(report_text)
        return True, output_path
    except Exception as e:
        return False, str(e)
