"""
woldvein Trainer v0.4.6 - 游戏内 Overlay 控制模块

Python 端负责：
    - 向 Overlay DLL 发送修改器状态（通过命名管道）
    - 控制 Overlay 显示/隐藏
    - 管理 Overlay DLL 的注入和卸载

Overlay DLL（src/injector/overlay.c）负责：
    - Hook DX11 Present，渲染 ImGui 界面
    - 接收 Python 端状态并显示

注意：Overlay 功能为框架实现，完整 ImGui 渲染需要编译 overlay.c 并引入 ImGui 源码。
"""
import os
import sys
import ctypes
from ctypes import wintypes

from .logger import log, log_success, log_error, log_warning

# Overlay DLL 名称
OVERLAY_DLL_NAME = "woldvein_overlay.dll"

# 命名管道名称（与 overlay.c 中一致）
OVERLAY_PIPE_NAME = r"\\.\pipe\woldvein_overlay"


class OverlayController:
    """游戏内 Overlay 控制器"""

    def __init__(self):
        self._dll_loaded = False
        self._overlay_dll = None
        self._pipe_handle = None
        self._visible = False

    def get_dll_path(self):
        """获取 Overlay DLL 路径"""
        if getattr(sys, "frozen", False):
            base = os.path.dirname(sys.executable)
        else:
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base, "dist", OVERLAY_DLL_NAME)

    def is_dll_available(self):
        """检查 Overlay DLL 是否存在"""
        return os.path.exists(self.get_dll_path())

    def inject(self, pid):
        """注入 Overlay DLL 到游戏进程。

        返回：
            (success, message)
        """
        if not self.is_dll_available():
            return False, f"Overlay DLL 不存在: {self.get_dll_path()}"

        try:
            from .injector import inject_dll
            dll_path = self.get_dll_path()
            success, msg = inject_dll(pid, dll_path)
            if success:
                self._dll_loaded = True
                log_success("Overlay DLL 已注入")
            return success, msg
        except Exception as e:
            log_error(f"注入 Overlay DLL 失败: {e}")
            return False, str(e)

    def toggle(self):
        """切换 Overlay 显示/隐藏"""
        self._visible = not self._visible
        self._send_state(f"visible={self._visible}")
        return self._visible

    def show(self):
        """显示 Overlay"""
        self._visible = True
        self._send_state("visible=true")

    def hide(self):
        """隐藏 Overlay"""
        self._visible = False
        self._send_state("visible=false")

    def update_status(self, status_text):
        """向 Overlay 发送状态文本。

        参数：
            status_text: 状态文本（如"资源: 金钱=1000000, 粮食=500000"）
        """
        self._send_state(status_text)

    def _send_state(self, message):
        """通过命名管道向 Overlay DLL 发送消息。

        注意：Overlay DLL 是管道客户端，Python 端需要创建管道服务器。
        当前实现为框架，实际管道服务器需要在 Python 端创建。
        """
        # TODO: 实现命名管道服务器，向 Overlay DLL 推送状态
        # 当前仅记录日志
        log(f"[Overlay] 状态更新: {message[:100]}")

    def is_visible(self):
        """Overlay 是否可见"""
        return self._visible

    def is_loaded(self):
        """Overlay DLL 是否已加载"""
        return self._dll_loaded


# 全局 Overlay 控制器单例
_overlay_controller = None


def get_overlay_controller():
    """获取全局 Overlay 控制器"""
    global _overlay_controller
    if _overlay_controller is None:
        _overlay_controller = OverlayController()
    return _overlay_controller
