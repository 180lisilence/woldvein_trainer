# 归档说明 - legacy_gui

## 归档时间
2026-09-27

## 归档原因
src/gui/ 目录下的 PyQt/PySide GUI 实现已被 trainer_ui_tk.py (tkinter) 替代。
经检查，该目录下的文件仅内部互相引用，无任何外部模块引用，属于死代码。

## 归档内容
- main_gui.py - 主GUI窗口（45KB）
- tab_*.py - 各功能标签页（11个文件）
- theme.py - 主题管理
- widgets.py - 自定义控件
- toast.py - 通知弹窗
- tooltip.py - 工具提示
- scrollable.py - 可滚动区域
- async_helper.py - 异步辅助
- diagnostic_panel.py - 诊断面板

## 恢复方法
如需恢复，将 archived/legacy_gui/gui/ 目录移回 src/ 即可。

## 注意
- 这些文件依赖 PyQt5/PySide，当前项目已不再使用
- trainer_ui_tk.py 是当前活跃的GUI实现
