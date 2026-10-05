"""
woldvein Trainer v0.3 - 日志系统模块

功能说明：
    提供线程安全的日志记录功能，支持同时输出到控制台、文件和GUI回调。
    日志文件按日期命名（trainer_YYYYMMDD.log），追加写入。

核心设计：
    - _log_file：日志文件句柄（全局单例）
    - _log_lock：多线程写文件锁（防止GUI线程、监控线程、热键线程并发写文件交错）
    - _log_callback：GUI日志回调函数（用于实时显示日志到界面）

日志级别：
    INFO    普通信息（默认）
    SUCCESS 操作成功
    WARNING 警告信息
    ERROR   错误信息

技术要点：
    - print()在windowed打包下sys.stdout可能为None，已加try/except保护
    - 写文件时检查和写入都在锁内，避免close_log并发空窗
    - GUI回调异常不影响主流程
"""
import os
import sys
import threading
from datetime import datetime
from src.constants import APP_VERSION

# 日志目录：兼容PyInstaller打包环境
# 打包后：EXE所在目录/logs/
# 开发环境：项目根目录/logs/
if getattr(sys, 'frozen', False):
    # 打包后用EXE所在目录/logs（D盘），不写C盘
    LOG_DIR = os.path.join(os.path.dirname(sys.executable), "logs")
else:
    LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

# 全局状态
_log_file = None           # 日志文件句柄
_log_callback = None       # GUI日志回调函数（用于实时显示到界面）
_log_lock = threading.Lock()  # 多线程写文件锁


def init_log():
    """
    初始化日志文件。

    处理逻辑：
        1. 先关闭旧的日志文件句柄（防止重复初始化泄漏句柄）
        2. 按当前日期创建日志文件名
        3. 以追加模式打开文件
        4. 写入启动分隔线和启动信息
    """
    global _log_file
    close_log()
    date_str = datetime.now().strftime("%Y%m%d")
    log_path = os.path.join(LOG_DIR, f"trainer_{date_str}.log")
    _log_file = open(log_path, "a", encoding="utf-8")
    log(f"{'='*60}")
    log(f"woldvein Trainer v{APP_VERSION} 启动")
    log(f"{'='*60}")


def get_log_dir():
    """获取日志目录路径（用于"打开日志文件夹"按钮）"""
    return LOG_DIR


def get_log_path():
    """获取当前日志文件路径（用于"打开日志文件"和"复制路径"按钮）"""
    date_str = datetime.now().strftime("%Y%m%d")
    return os.path.join(LOG_DIR, f"trainer_{date_str}.log")


def set_log_callback(callback):
    """
    设置GUI日志回调函数。

    参数：
        callback: 回调函数，签名为 callback(line: str, level: str)
                  每次有日志时会被调用，用于实时更新GUI日志显示区
    """
    global _log_callback
    _log_callback = callback


def log(msg, level="INFO"):
    """
    记录一条日志（线程安全）。

    参数：
        msg: 日志消息内容
        level: 日志级别（INFO/SUCCESS/WARNING/ERROR）

    处理流程：
        1. 生成带时间戳和级别的日志行
        2. 输出到控制台（windowed打包下可能失败，已保护）
        3. 加锁写入日志文件
        4. 调用GUI回调（如果已设置）

    线程安全说明：
        - 文件写入在_log_lock保护下进行
        - 检查_log_file和写入都在锁内，避免close_log并发空窗
        - GUI回调异常不影响主流程
    """
    timestamp = datetime.now().strftime("%H:%M:%S")
    line = f"[{timestamp}] [{level}] {msg}"
    # 控制台输出（PyInstaller --windowed打包后sys.stdout可能为None）
    try:
        print(line)
    except Exception:
        pass
    # 写文件（检查和写入都在锁内）
    with _log_lock:
        if _log_file:
            try:
                _log_file.write(line + "\n")
                _log_file.flush()
            except Exception:
                pass  # 日志写文件失败不抛异常（logger自身不能再log）
    # GUI回调（实时显示到界面）
    if _log_callback:
        try:
            _log_callback(line, level)
        except Exception:
            pass  # GUI回调失败不影响主流程


def log_info(msg):
    """记录INFO级别日志（普通信息）"""
    log(msg, "INFO")


def log_success(msg):
    """记录SUCCESS级别日志（操作成功）"""
    log(msg, "SUCCESS")


def log_warning(msg):
    """记录WARNING级别日志（警告信息）"""
    log(msg, "WARNING")


def log_error(msg):
    """记录ERROR级别日志（错误信息）"""
    log(msg, "ERROR")


def close_log():
    """
    关闭日志文件句柄。

    处理逻辑：
        1. 加锁
        2. 关闭文件句柄（异常忽略）
        3. 置为None
    """
    global _log_file
    if _log_file:
        with _log_lock:
            try:
                _log_file.close()
            except Exception:
                pass  # 关闭文件失败静默（logger自身不能再log）
            _log_file = None


def clear_log_file():
    """
    清空日志文件内容（保留文件，只清空内容）。

    处理逻辑：
        1. 关闭当前日志文件句柄
        2. 以写入模式打开文件（会清空内容）
        3. 立即关闭，再以追加模式重新打开
        4. 返回是否成功
    """
    global _log_file
    log_path = get_log_path()
    try:
        with _log_lock:
            # 关闭当前句柄
            if _log_file:
                try:
                    _log_file.close()
                except Exception:
                    pass  # 关闭失败静默（logger自身不能再log）
                _log_file = None
            # 清空文件
            with open(log_path, "w", encoding="utf-8") as f:
                pass
            # 重新以追加模式打开
            _log_file = open(log_path, "a", encoding="utf-8")
        return True
    except Exception as e:
        # 失败时尝试重新打开
        try:
            _log_file = open(log_path, "a", encoding="utf-8")
        except Exception:
            pass  # 重新打开失败静默（logger自身不能再log）
        return False


def get_report_path():
    """获取探查报告文件路径（所有探查/诊断结果汇总，便于一次性复制）"""
    return os.path.join(LOG_DIR, "probe_report.txt")


def append_report(section, text):
    """把探查/诊断结果追加到统一报告文件

    背景：逐个按钮复制探查输出很麻烦，统一落到 probe_report.txt，
    用户打开该文件一次性复制即可。
    """
    try:
        path = get_report_path()
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with _log_lock:
            with open(path, "a", encoding="utf-8") as f:
                f.write(f"\n{'=' * 70}\n[{ts}] {section}\n{'=' * 70}\n{text}\n")
        return True
    except Exception as e:
        # 报告写入失败不影响主流程
        log(f"写入探查报告失败: {e}", "ERROR")
        return False


def clear_report():
    """清空探查报告文件"""
    try:
        with open(get_report_path(), "w", encoding="utf-8"):
            pass
        return True
    except Exception:
        return False


def read_report():
    """读取探查报告全文（供复制/展示）"""
    try:
        with open(get_report_path(), "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""
