"""
游戏状态提供者（单例）
功能：统一管理游戏状态的定时刷新，避免多个 tab 并发查询导致的竞态 bug。

问题背景：
    资源修改页和创造模式页各有一个 3 秒定时刷新，都会调用 execute_lua 查询游戏状态。
    当 A 请求超时释放锁、B 请求立即写入新命令、但 DLL 刚写完 A 的结果时，
    B 会读到 A 的结果误以为是自己的（竞态 bug）。

解决方案：
    用单一的状态刷新 worker，每 3 秒查询一次，所有订阅者从同一个缓存读取结果。
    从根源上消除并发请求，同时也减少了 Lua 执行次数，降低对游戏的影响。

使用方式：
    provider = get_status_provider()
    provider.subscribe("my_tab", my_callback)
    provider.unsubscribe("my_tab")

    callback 签名: def callback(status_dict, success)
"""
import json
import threading
import time

from src.lua_engine import execute_lua_safe, LUA_GET_STATUS
from src.logger import log_error, log_warning


class GameStatusProvider:
    """游戏状态提供者（单例模式）

    统一管理游戏状态刷新，所有订阅者共享同一份数据。
    只有至少有一个订阅者时才会启动刷新，全部取消订阅后停止。
    """

    def __init__(self, interval=3.0):
        self._interval = interval       # 刷新间隔（秒）
        self._subscribers = {}          # 订阅者字典: name -> callback
        self._lock = threading.Lock()
        self._thread = None
        self._running = False
        self._latest_status = None      # 最新状态缓存 (dict)
        self._latest_success = False    # 最新一次是否成功
        self._dll_ready = False         # DLL是否已注入且Hook就绪（未就绪时跳过Lua查询，避免超时刷屏）
        self._force = False             # force_refresh 标志：worker 检测后跳过休眠立即查询

    def subscribe(self, name, callback):
        """订阅状态更新

        参数：
            name: 订阅者名称（唯一标识）
            callback: 状态更新回调函数，参数为 (status_dict, success)
        """
        with self._lock:
            self._subscribers[name] = callback
            # 如果有缓存数据，立即推送给新订阅者
            if self._latest_status is not None:
                try:
                    callback(self._latest_status, self._latest_success)
                except Exception:
                    pass
            # 启动刷新线程（如果还没启动）
            if not self._running:
                self._start()

    def unsubscribe(self, name):
        """取消订阅"""
        with self._lock:
            self._subscribers.pop(name, None)
            # 没有订阅者了，停止刷新
            if not self._subscribers:
                self._stop()

    def set_dll_ready(self, ready):
        """设置DLL就绪状态（由GUI在DLL注入成功/Hook就绪后调用）

        参数：
            ready: True表示DLL已注入且Hook就绪，可以开始Lua查询
                   False表示DLL未就绪，跳过Lua查询避免超时刷屏
        """
        with self._lock:
            if self._dll_ready != ready:
                self._dll_ready = ready
                if ready:
                    # DLL就绪时重置失败计数，让刷新线程立即开始查询
                    self._latest_success = False

    def get_latest(self):
        """获取最新状态（同步）

        返回：
            (status_dict, success) 元组
        """
        return self._latest_status, self._latest_success

    def force_refresh(self):
        """强制立即刷新一次（异步，不等待结果）

        实现：设置 _force 标志，worker 在休眠前检测此标志，
        若为 True 则跳过本次 sleep 立即执行下一轮查询。
        """
        with self._lock:
            self._force = True

    def _start(self):
        """启动刷新线程（必须在持有 _lock 的情况下调用）"""
        self._running = True
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def _stop(self):
        """停止刷新线程（必须在持有 _lock 的情况下调用）"""
        self._running = False

    def _worker(self):
        """刷新线程主循环"""
        consecutive_failures = 0
        _logged_skip = False  # 是否已记录过跳过日志（避免刷屏）

        while True:
            with self._lock:
                if not self._running:
                    return
                dll_ready = self._dll_ready

            # DLL未就绪时跳过Lua查询，避免每次5秒超时刷屏
            if not dll_ready:
                _logged_skip = False
                self._sleep_interruptible(self._interval)
                continue
            else:
                _logged_skip = False  # DLL就绪后重置，下次未就绪时再记录

            try:
                success, result = execute_lua_safe(LUA_GET_STATUS)

                status = {}
                if success and result and isinstance(result, str):
                    try:
                        status = json.loads(result)
                        self._latest_success = True
                        self._latest_status = status
                        consecutive_failures = 0
                    except (json.JSONDecodeError, ValueError) as e:
                        self._latest_success = False
                        consecutive_failures += 1
                        if consecutive_failures <= 3:
                            log_warning(f"[状态刷新] JSON解析失败: {e}")
                else:
                    self._latest_success = False
                    consecutive_failures += 1
                    if consecutive_failures <= 3:
                        log_warning(f"[状态刷新] 查询失败: success={success}, result={str(result)[:50]}")

                # 推送更新给所有订阅者
                self._notify_subscribers()

            except Exception as e:
                log_error(f"[状态刷新] 异常: {e}")
                consecutive_failures += 1

            # 等待下一次刷新（分片等待，快速响应停止信号）
            # 若 force_refresh 被调用（_force=True），跳过本次休眠立即下一轮查询
            with self._lock:
                force_now = self._force
                self._force = False  # 消费标志，避免无限立即查询
            if force_now:
                continue  # 跳过 sleep，立即下一轮
            self._sleep_interruptible(self._interval)

    def _sleep_interruptible(self, duration):
        """可中断的睡眠（分片睡，快速响应停止）"""
        start = time.time()
        while time.time() - start < duration:
            with self._lock:
                if not self._running:
                    return
            time.sleep(min(0.1, duration - (time.time() - start)))

    def _notify_subscribers(self):
        """推送状态更新给所有订阅者（在刷新线程中调用）"""
        with self._lock:
            callbacks = list(self._subscribers.values())

        for cb in callbacks:
            try:
                cb(self._latest_status if self._latest_success else {}, self._latest_success)
            except Exception as e:
                log_warning(f"[状态刷新] 订阅者回调异常: {e}")


# ========== 单例 ==========

_provider_instance = None
_provider_lock = threading.Lock()


def get_status_provider():
    """获取 GameStatusProvider 单例"""
    global _provider_instance
    if _provider_instance is None:
        with _provider_lock:
            if _provider_instance is None:
                _provider_instance = GameStatusProvider()
    return _provider_instance
