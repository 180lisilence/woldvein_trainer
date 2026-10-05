#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
平野孤鸿 全能修改器 v0.4.3
主程序入口

功能说明：
    本程序是《平野孤鸿》(Ballads of Hongye, Steam AppID 2656540)的全能修改器。
    通过DLL注入 + inline-hook lua_pcall的方式，在游戏进程内部执行Lua脚本，
    实现资源修改、创造模式、热键、游戏监控、高级工具、世界系统等功能。

架构说明：
    main.py          → 程序入口，异常捕获
    trainer_ui_tk.py → tkinter GUI界面（微信三栏布局）
    src/injector/    → DLL注入核心 + trainer.c源码
    src/lua_engine.py → Lua脚本执行引擎（命令文件通信）
    src/*.py         → 各功能模块
"""
import os
import sys

_SINGLE_INSTANCE_HANDLE = None


def _ensure_single_instance():
    global _SINGLE_INSTANCE_HANDLE
    if os.name != "nt":
        return True
    try:
        import ctypes
        from src.constants import APP_VERSION
        kernel32 = ctypes.windll.kernel32
        _SINGLE_INSTANCE_HANDLE = kernel32.CreateMutexW(
            None, False, f"woldvein_trainer_mutex_v{APP_VERSION.replace('.', '')}"
        )
        if kernel32.GetLastError() == 183:
            ctypes.windll.user32.MessageBoxW(
                None,
                "检测到修改器已经在运行。\n\n多开会让两个实例互相覆盖游戏通信文件。\n请先关闭其它修改器窗口再启动。",
                "woldvein Trainer",
                0x00000040,
            )
            return False
    except Exception:
        return True
    return True

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from trainer_ui_tk import main

if __name__ == "__main__":
    if not _ensure_single_instance():
        sys.exit(0)
    try:
        main()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        try:
            from src.logger import log_error
            log_error(f"未捕获异常: {e}")
        except Exception as log_err:
            print(f"[FATAL] 日志记录失败: {log_err}", file=sys.stderr)
        raise
