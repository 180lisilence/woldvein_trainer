"""
woldvein Trainer v0.4.6 - 启动优化模块

优化修改器启动速度：
    1. 懒加载：模块只在首次使用时导入
    2. 并行初始化：独立模块并行初始化
    3. 延迟初始化：非关键功能延迟到后台线程
    4. 启动性能分析：记录各阶段耗时

使用方式：
    from .startup_optimizer import lazy_import, parallel_init, StartupProfiler
    # 懒加载
    psutil = lazy_import("psutil")
    # 并行初始化
    results = parallel_init([init_a, init_b, init_c])
"""
import os
import sys
import time
import threading
import importlib

from .logger import log, log_success, log_error, log_warning


class LazyModule:
    """懒加载模块包装器。

    首次访问属性时才真正导入模块。
    """

    def __init__(self, module_name):
        self._module_name = module_name
        self._module = None

    def _load(self):
        if self._module is None:
            self._module = importlib.import_module(self._module_name)
        return self._module

    def __getattr__(self, name):
        return getattr(self._load(), name)

    def __call__(self, *args, **kwargs):
        return self._load()(*args, **kwargs)


def lazy_import(module_name):
    """懒加载模块。

    参数：
        module_name: 模块名，如 "psutil"

    返回：
        LazyModule 对象，首次使用时才导入
    """
    return LazyModule(module_name)


class StartupProfiler:
    """启动性能分析器。

    记录各初始化阶段的耗时，帮助定位启动瓶颈。
    """

    def __init__(self):
        self._phases = []
        self._start_time = None
        self._current_phase = None

    def start(self):
        """开始计时。"""
        self._start_time = time.time()
        log("[启动优化] 启动性能分析开始")

    def begin_phase(self, name):
        """开始一个阶段。"""
        if self._current_phase:
            self.end_phase()
        self._current_phase = {
            "name": name,
            "start": time.time(),
            "end": None,
            "duration": None,
        }

    def end_phase(self):
        """结束当前阶段。"""
        if self._current_phase:
            self._current_phase["end"] = time.time()
            self._current_phase["duration"] = self._current_phase["end"] - self._current_phase["start"]
            self._phases.append(self._current_phase)
            log(f"[启动优化] 阶段 '{self._current_phase['name']}' 耗时: {self._current_phase['duration']:.3f}s")
            self._current_phase = None

    def finish(self):
        """结束计时，输出报告。"""
        if self._current_phase:
            self.end_phase()

        total = time.time() - self._start_time if self._start_time else 0
        log_success(f"[启动优化] 总启动耗时: {total:.3f}s")

        # 输出各阶段耗时
        if self._phases:
            log("[启动优化] 各阶段耗时:")
            for phase in self._phases:
                pct = (phase["duration"] / total * 100) if total > 0 else 0
                log(f"  {phase['name']}: {phase['duration']:.3f}s ({pct:.1f}%)")

        return total

    def get_report(self):
        """获取性能报告。"""
        total = sum(p["duration"] for p in self._phases)
        return {
            "total_time": total,
            "phases": [
                {
                    "name": p["name"],
                    "duration": p["duration"],
                    "percentage": (p["duration"] / total * 100) if total > 0 else 0,
                }
                for p in self._phases
            ],
        }


def parallel_init(funcs, timeout=10.0):
    """并行初始化多个独立模块。

    参数：
        funcs: 初始化函数列表 [func1, func2, ...]
        timeout: 超时时间（秒）

    返回：
        [result1, result2, ...] 按顺序返回各函数结果
    """
    results = [None] * len(funcs)
    errors = [None] * len(funcs)
    threads = []

    def worker(index, func):
        try:
            results[index] = func()
        except Exception as e:
            errors[index] = e

    for i, func in enumerate(funcs):
        t = threading.Thread(target=worker, args=(i, func), daemon=True)
        threads.append(t)
        t.start()

    for t in threads:
        t.join(timeout=timeout)

    # 检查错误
    for i, err in enumerate(errors):
        if err:
            log_error(f"[启动优化] 并行初始化函数 {i} 失败: {err}")

    return results


class DelayedInit:
    """延迟初始化器。

    将非关键功能的初始化放到后台线程，不阻塞启动。
    """

    def __init__(self):
        self._tasks = []
        self._thread = None
        self._started = False

    def add_task(self, func, *args, **kwargs):
        """添加延迟初始化任务。

        参数：
            func: 初始化函数
            *args, **kwargs: 函数参数
        """
        self._tasks.append((func, args, kwargs))

    def start(self):
        """启动后台初始化线程。"""
        if self._started:
            return
        self._started = True

        def worker():
            for func, args, kwargs in self._tasks:
                try:
                    func(*args, **kwargs)
                except Exception as e:
                    log_error(f"[启动优化] 延迟初始化任务失败: {e}")

        self._thread = threading.Thread(target=worker, daemon=True)
        self._thread.start()
        log(f"[启动优化] 已启动 {len(self._tasks)} 个延迟初始化任务")

    def wait(self, timeout=None):
        """等待所有延迟任务完成。"""
        if self._thread:
            self._thread.join(timeout=timeout)


def preload_common_modules():
    """预加载常用模块（在后台线程）。

    提前导入常用模块，避免首次使用时的延迟。
    """
    def _preload():
        modules = [
            "json", "os", "sys", "time", "threading",
            "ctypes", "re", "datetime", "shutil",
        ]
        for mod in modules:
            try:
                importlib.import_module(mod)
            except Exception:
                pass
        log("[启动优化] 常用模块预加载完成")

    t = threading.Thread(target=_preload, daemon=True)
    t.start()
    return t


def optimize_python_path():
    """优化 Python 模块搜索路径。

    移除不存在的路径，减少模块搜索时间。
    """
    original_count = len(sys.path)
    sys.path = [p for p in sys.path if os.path.exists(p) or p == ""]
    removed = original_count - len(sys.path)
    if removed > 0:
        log(f"[启动优化] 已移除 {removed} 个无效的 sys.path 条目")


def disable_verbose_imports():
    """禁用详细导入日志（如果有）。"""
    # Python 默认没有详细导入日志，这里预留扩展点
    pass


class StartupOptimizer:
    """启动优化器（整合所有优化功能）。"""

    def __init__(self):
        self.profiler = StartupProfiler()
        self.delayed_init = DelayedInit()
        self._optimizations_applied = []

    def apply_basic_optimizations(self):
        """应用基础优化。"""
        optimize_python_path()
        disable_verbose_imports()
        preload_common_modules()
        self._optimizations_applied = ["path", "preload"]

    def begin_phase(self, name):
        """开始一个阶段（代理到 profiler）。"""
        self.profiler.begin_phase(name)

    def end_phase(self):
        """结束当前阶段。"""
        self.profiler.end_phase()

    def add_delayed_task(self, func, *args, **kwargs):
        """添加延迟初始化任务。"""
        self.delayed_init.add_task(func, *args, **kwargs)

    def start_delayed_init(self):
        """启动延迟初始化。"""
        self.delayed_init.start()

    def finish(self):
        """完成启动优化，输出报告。"""
        total = self.profiler.finish()
        self.start_delayed_init()
        return total


# 全局启动优化器单例
_global_optimizer = None


def get_startup_optimizer():
    """获取全局启动优化器"""
    global _global_optimizer
    if _global_optimizer is None:
        _global_optimizer = StartupOptimizer()
    return _global_optimizer
