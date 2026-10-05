# woldvein_trainer v0.4.8 — 拆分说明（v0.4.9 沿用此结构）

本版本最大的变化：**修改器不再自己注入。**

## 变了什么

| 模块 | v0.4.6 及以前 | v0.4.8 |
|---|---|---|
| `src/injector/` | 真正的注入实现 + `trainer.c` + DLL | **转发 shim**，内部调注入器服务 |
| `src/lua_engine.py` | 传输实现 + Lua 模板混在一起 | 只留 Lua 玩法模板 + 三个 `execute_*` 外壳 |
| 注入、管道、文件轮询、双重锁 | 在这里 | 全部搬到 woldvein_injector v0.4.7 |
| 玩法模块（30+ 个） | 在这里 | 原样保留，**零改动** |

## 现在怎么调注入

```python
from src.injector_client import get_client

client = get_client()
client.ensure_injected()                    # 幂等，已注入直接成功
ok, res = client.execute("return g_camp ~= nil")
```

老代码不用动，下面这些写法继续有效：

```python
from src.injector import find_game_process, inject_dll, is_dll_injected, get_dll_path
from src.lua_engine import execute_lua_safe, execute_lua_retry
```

## 注入器在哪

按以下顺序找 `injector_api.py`：

1. 环境变量 `WOLDVEIN_INJECTOR_HOME`
2. `trainers/injector/woldvein_injector0.4.7`（当前归集布局）
3. 本项目 `vendor/woldvein_injector0.4.7`

找不到时错误信息会列出所有查过的路径和三种解决办法，不会静默失败。
要求注入器版本严格等于 `0.4.7`，否则拒绝加载。

## 如果拿到了新版本注入器

改 `src/injector_client.py` 顶部的 `REQUIRED_INJECTOR_VERSION` 即可，
其余代码一行不用动 —— 这就是拆开的意义。

## 自检

```
python trainers/tools/check_split.py
```
