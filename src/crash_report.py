"""
woldvein Trainer v0.4.6 - 崩溃报告自动收集模块

功能：
    1. 全局异常捕获（sys.excepthook）
    2. 崩溃时自动收集系统信息、日志、配置
    3. 生成崩溃报告（文本 + JSON）
    4. 提示用户提交报告
    5. 崩溃报告自动保存到本地

使用方式：
    from .crash_report import CrashReporter, install_crash_handler
    reporter = CrashReporter()
    install_crash_handler(reporter)
"""
import os
import sys
import json
import traceback
import datetime
import platform
import threading

from .logger import log, log_success, log_error, log_warning
from .atomic_file import atomic_write_text, atomic_write_json


class CrashReporter:
    """崩溃报告收集器"""

    def __init__(self, report_dir=None, app_name="woldvein_trainer"):
        """
        参数：
            report_dir: 报告保存目录
            app_name: 应用名称
        """
        self._app_name = app_name
        self._report_dir = report_dir or self._default_report_dir()
        self._crash_count = 0
        self._listeners = []

        os.makedirs(self._report_dir, exist_ok=True)

    def _default_report_dir(self):
        """获取默认报告目录"""
        if getattr(sys, "frozen", False):
            base = os.path.dirname(sys.executable)
        else:
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base, "crash_reports")

    def collect_system_info(self):
        """收集系统信息。

        返回：
            系统信息字典
        """
        try:
            info = {
                "app_name": self._app_name,
                "app_version": self._get_app_version(),
                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "python_version": sys.version,
                "python_executable": sys.executable,
                "platform": platform.platform(),
                "system": platform.system(),
                "system_release": platform.release(),
                "system_version": platform.version(),
                "machine": platform.machine(),
                "processor": platform.processor(),
                "architecture": platform.architecture()[0],
                "hostname": platform.node(),
                "frozen": getattr(sys, "frozen", False),
                "argv": sys.argv,
                "cwd": os.getcwd(),
                "env": self._get_safe_env(),
            }
            return info
        except Exception as e:
            return {"error": f"收集系统信息失败: {e}"}

    def _get_app_version(self):
        """获取应用版本"""
        try:
            from src.constants import APP_VERSION
            return APP_VERSION
        except Exception:
            return "unknown"

    def _get_safe_env(self):
        """获取安全的环境变量（排除敏感信息）"""
        sensitive_keys = {"PASSWORD", "SECRET", "TOKEN", "KEY", "API_KEY"}
        safe_env = {}
        for key, value in os.environ.items():
            if any(s in key.upper() for s in sensitive_keys):
                safe_env[key] = "***REDACTED***"
            else:
                safe_env[key] = value
        return safe_env

    def collect_exception_info(self, exc_type, exc_value, exc_traceback):
        """收集异常信息。

        返回：
            异常信息字典
        """
        try:
            tb_lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
            info = {
                "exception_type": exc_type.__name__ if exc_type else "Unknown",
                "exception_message": str(exc_value),
                "traceback": "".join(tb_lines),
                "exception_module": exc_type.__module__ if exc_type else "",
            }

            # 获取异常发生的文件和行号
            if exc_traceback:
                frame = traceback.extract_tb(exc_traceback)[-1]
                info["crash_file"] = frame.filename
                info["crash_line"] = frame.lineno
                info["crash_function"] = frame.name
                info["crash_code"] = frame.line

            return info
        except Exception as e:
            return {"error": f"收集异常信息失败: {e}"}

    def collect_logs(self, max_lines=500):
        """收集最近的日志。

        返回：
            日志文本
        """
        try:
            log_dir = os.path.join(os.path.dirname(self._report_dir), "logs")
            if not os.path.exists(log_dir):
                return "日志目录不存在"

            # 找到最新的日志文件
            log_files = [f for f in os.listdir(log_dir) if f.endswith(".log")]
            if not log_files:
                return "无日志文件"

            log_files.sort(reverse=True)
            latest_log = os.path.join(log_dir, log_files[0])

            with open(latest_log, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()

            # 只取最后 N 行
            if len(lines) > max_lines:
                lines = lines[-max_lines:]
                lines.insert(0, f"... (省略前 {len(lines) - max_lines} 行) ...\n")

            return "".join(lines)
        except Exception as e:
            return f"收集日志失败: {e}"

    def collect_config(self):
        """收集配置信息（脱敏）。"""
        try:
            config_file = os.path.join(os.path.dirname(self._report_dir), "config.json")
            if not os.path.exists(config_file):
                return "配置文件不存在"

            with open(config_file, "r", encoding="utf-8") as f:
                config = json.load(f)

            # 脱敏
            sensitive_keys = {"password", "secret", "token", "key", "api_key"}
            for key in list(config.keys()):
                if any(s in key.lower() for s in sensitive_keys):
                    config[key] = "***REDACTED***"

            return config
        except Exception as e:
            return f"收集配置失败: {e}"

    def collect_thread_info(self):
        """收集线程信息。"""
        try:
            threads = []
            for thread in threading.enumerate():
                threads.append({
                    "name": thread.name,
                    "ident": thread.ident,
                    "daemon": thread.daemon,
                    "alive": thread.is_alive(),
                })
            return {
                "active_count": threading.active_count(),
                "threads": threads,
            }
        except Exception as e:
            return {"error": f"收集线程信息失败: {e}"}

    def generate_report(self, exc_type=None, exc_value=None, exc_traceback=None):
        """生成完整崩溃报告。

        返回：
            (report_dict, report_text)
        """
        report = {
            "system": self.collect_system_info(),
            "exception": self.collect_exception_info(exc_type, exc_value, exc_traceback) if exc_type else None,
            "threads": self.collect_thread_info(),
            "config": self.collect_config(),
            "logs": self.collect_logs(),
        }

        # 生成文本报告
        text_lines = []
        text_lines.append("=" * 60)
        text_lines.append(f"{self._app_name} 崩溃报告")
        text_lines.append("=" * 60)
        text_lines.append("")

        # 系统信息
        text_lines.append("--- 系统信息 ---")
        sys_info = report["system"]
        text_lines.append(f"应用版本: {sys_info.get('app_version', 'unknown')}")
        text_lines.append(f"时间: {sys_info.get('timestamp', 'unknown')}")
        text_lines.append(f"系统: {sys_info.get('platform', 'unknown')}")
        text_lines.append(f"Python: {sys_info.get('python_version', 'unknown')}")
        text_lines.append(f"运行目录: {sys_info.get('cwd', 'unknown')}")
        text_lines.append("")

        # 异常信息
        if report["exception"]:
            text_lines.append("--- 异常信息 ---")
            exc = report["exception"]
            text_lines.append(f"异常类型: {exc.get('exception_type', 'unknown')}")
            text_lines.append(f"异常消息: {exc.get('exception_message', 'unknown')}")
            if "crash_file" in exc:
                text_lines.append(f"崩溃位置: {exc.get('crash_file')}:{exc.get('crash_line')}")
                text_lines.append(f"崩溃函数: {exc.get('crash_function')}")
            text_lines.append("")
            text_lines.append("--- 堆栈跟踪 ---")
            text_lines.append(exc.get("traceback", ""))
            text_lines.append("")

        # 线程信息
        text_lines.append("--- 线程信息 ---")
        threads = report.get("threads", {})
        text_lines.append(f"活动线程数: {threads.get('active_count', 'unknown')}")
        for t in threads.get("threads", []):
            text_lines.append(f"  - {t['name']} (daemon={t['daemon']}, alive={t['alive']})")
        text_lines.append("")

        # 日志
        text_lines.append("--- 最近日志 ---")
        text_lines.append(report.get("logs", ""))
        text_lines.append("")

        report_text = "\n".join(text_lines)
        return report, report_text

    def save_report(self, report, report_text):
        """保存崩溃报告到文件。

        返回：
            (json_path, txt_path)
        """
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        crash_id = f"crash_{timestamp}_{self._crash_count}"
        self._crash_count += 1

        json_path = os.path.join(self._report_dir, f"{crash_id}.json")
        txt_path = os.path.join(self._report_dir, f"{crash_id}.txt")

        try:
            atomic_write_json(json_path, report)
            atomic_write_text(txt_path, report_text)
            log_error(f"[崩溃报告] 已保存: {txt_path}")
            return json_path, txt_path
        except Exception as e:
            log_error(f"[崩溃报告] 保存失败: {e}")
            return None, None

    def handle_exception(self, exc_type, exc_value, exc_traceback):
        """处理未捕获异常。

        这是 sys.excepthook 的回调函数。
        """
        # 忽略 KeyboardInterrupt
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        log_error(f"[崩溃报告] 捕获未处理异常: {exc_type.__name__}: {exc_value}")

        # 生成报告
        report, report_text = self.generate_report(exc_type, exc_value, exc_traceback)
        json_path, txt_path = self.save_report(report, report_text)

        # 通知监听器
        for listener in self._listeners:
            try:
                listener(report, json_path, txt_path)
            except Exception:
                pass

        # 打印到 stderr
        print(report_text, file=sys.stderr)

    def add_listener(self, listener):
        """添加崩溃监听器。

        参数：
            listener: 回调函数 listener(report, json_path, txt_path)
        """
        self._listeners.append(listener)

    def remove_listener(self, listener):
        """移除监听器。"""
        if listener in self._listeners:
            self._listeners.remove(listener)

    def get_report_dir(self):
        """获取报告目录。"""
        return self._report_dir

    def list_reports(self):
        """列出所有崩溃报告。"""
        if not os.path.exists(self._report_dir):
            return []

        reports = []
        for f in os.listdir(self._report_dir):
            if f.endswith(".json"):
                filepath = os.path.join(self._report_dir, f)
                reports.append({
                    "filename": f,
                    "path": filepath,
                    "size": os.path.getsize(filepath),
                    "modified": datetime.datetime.fromtimestamp(os.path.getmtime(filepath)),
                })
        return sorted(reports, key=lambda x: x["modified"], reverse=True)

    def clear_old_reports(self, keep_days=30):
        """清理旧崩溃报告。"""
        cutoff = datetime.datetime.now() - datetime.timedelta(days=keep_days)
        cleaned = 0
        for report in self.list_reports():
            if report["modified"] < cutoff:
                try:
                    os.remove(report["path"])
                    # 同时删除对应的 txt
                    txt_path = report["path"].replace(".json", ".txt")
                    if os.path.exists(txt_path):
                        os.remove(txt_path)
                    cleaned += 1
                except Exception:
                    pass
        if cleaned > 0:
            log(f"[崩溃报告] 已清理 {cleaned} 个旧报告")
        return cleaned


# 全局崩溃报告器单例
_global_reporter = None


def get_crash_reporter():
    """获取全局崩溃报告器"""
    global _global_reporter
    if _global_reporter is None:
        _global_reporter = CrashReporter()
    return _global_reporter


def install_crash_handler(reporter=None):
    """安装全局崩溃处理器。

    参数：
        reporter: CrashReporter 实例，None 则使用全局单例
    """
    if reporter is None:
        reporter = get_crash_reporter()

    sys.excepthook = reporter.handle_exception
    log("[崩溃报告] 全局崩溃处理器已安装")

    # 也安装线程异常钩子（Python 3.8+）
    if hasattr(threading, "excepthook"):
        def thread_excepthook(args):
            reporter.handle_exception(args.exc_type, args.exc_value, args.exc_traceback)
        threading.excepthook = thread_excepthook

    return reporter


def manual_crash_report(exception=None):
    """手动生成崩溃报告（用于捕获的异常）。

    参数：
        exception: 异常对象，None 则使用当前异常

    返回：
        (json_path, txt_path)
    """
    reporter = get_crash_reporter()

    if exception:
        exc_type = type(exception)
        exc_value = exception
        exc_traceback = exception.__traceback__
    else:
        exc_type, exc_value, exc_traceback = sys.exc_info()

    if exc_type is None:
        log_warning("[崩溃报告] 无当前异常")
        return None, None

    report, report_text = reporter.generate_report(exc_type, exc_value, exc_traceback)
    return reporter.save_report(report, report_text)
