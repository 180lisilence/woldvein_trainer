"""
woldvein Trainer v0.3 - 热键唯一定义源

功能说明：
    全项目热键的唯一定义源。config.py / tab_hotkey.py / hotkey_configurator.py /
    tab_resource.py（Tooltip）五处原先各自硬编码一份热键表，曾出现 F10/F12 写反、
    资源 Tooltip 映射错位等问题。统一收敛到本模块后，任何热键调整只需改一处。

设计：
    HOTKEY_DEFS: 功能键名 -> {显示名, 默认组合键, 关联资源ID}
    resource_id 为 None 表示非资源类热键（知名度/创造模式/幸福度）
"""

HOTKEY_DEFS = {
    "money":         {"name": "金钱 +100万",   "default": "Ctrl+F1",  "resource_id": 1},
    "food":          {"name": "食物 +100万",   "default": "Ctrl+F2",  "resource_id": 5},
    "water":         {"name": "水 +100万",     "default": "Ctrl+F3",  "resource_id": 6},
    "cloth":         {"name": "衣物 +100万",   "default": "Ctrl+F4",  "resource_id": 4},
    "wood":          {"name": "木料 +100万",   "default": "Ctrl+F5",  "resource_id": 3},
    "mineral":       {"name": "矿产 +100万",   "default": "Ctrl+F6",  "resource_id": 2},
    "salt":          {"name": "盐 +100万",     "default": "Ctrl+F7",  "resource_id": 19},
    "wine":          {"name": "酒 +100万",     "default": "Ctrl+F8",  "resource_id": 20},
    "essence":       {"name": "精华 +100万",   "default": "Ctrl+F11", "resource_id": 25},
    "fame":          {"name": "知名度 +1万",   "default": "Ctrl+F9",  "resource_id": None},
    "creative_mode": {"name": "创造模式开关",  "default": "Ctrl+F10", "resource_id": None},
    "happiness":     {"name": "幸福度最大",    "default": "Ctrl+F12", "resource_id": None},
}


def get_default_hotkeys():
    """返回 {功能键名: 默认组合键} 字典"""
    return {k: v["default"] for k, v in HOTKEY_DEFS.items()}


def get_hotkey_names():
    """返回 {功能键名: 显示名} 字典"""
    return {k: v["name"] for k, v in HOTKEY_DEFS.items()}


def get_resource_hotkey(resource_id):
    """按资源ID查询默认热键组合，未找到返回 None"""
    for v in HOTKEY_DEFS.values():
        if v["resource_id"] == resource_id:
            return v["default"]
    return None
