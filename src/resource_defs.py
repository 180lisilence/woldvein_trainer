"""
woldvein Trainer v0.3 - 资源唯一定义源

功能说明：
    全项目资源列表的唯一定义源。resource_editor.py（业务）与 tab_resource.py（GUI）
    原先各维护一份资源定义，新增资源或调整ID时需要同步改多处，易漏。

    资源ID映射（游戏内实际值，**实机验证于 2026-09-13**：点矿产=矿产、点木料=木料）：
        id=1  金钱(money)
        id=2  矿产(mineral)
        id=3  木料(wood)
        id=4  衣物(cloth)
        id=5  食物(food)
        id=6  水(water)
        id=7  人口(population) ← 不提供一键修改
        id=19 盐(salt)
        id=20 酒(wine)
        id=25 精华(essence)   ← 七阶目标资源，与酒同类（实机验证 2026-09-13）

    注：知识库部分文档记为 2=木料/3=矿产，与实机结果相反，以实机为准（本项目映射正确）。
"""

RESOURCES = [
    {"id": 1,  "name": "金钱", "key": "money",      "icon": "💰", "hotkey_key": "money"},
    {"id": 2,  "name": "矿产", "key": "mineral",    "icon": "⛏️", "hotkey_key": "mineral"},
    {"id": 3,  "name": "木料", "key": "wood",       "icon": "🪵", "hotkey_key": "wood"},
    {"id": 4,  "name": "衣物", "key": "cloth",      "icon": "👕", "hotkey_key": "cloth"},
    {"id": 5,  "name": "食物", "key": "food",       "icon": "🍞", "hotkey_key": "food"},
    {"id": 6,  "name": "水",   "key": "water",      "icon": "💧", "hotkey_key": "water"},
    {"id": 7,  "name": "人口", "key": "population", "icon": "👥", "hotkey_key": None},
    {"id": 19, "name": "盐",   "key": "salt",       "icon": "🧂", "hotkey_key": "salt"},
    {"id": 20, "name": "酒",   "key": "wine",       "icon": "🍶", "hotkey_key": "wine"},
    {"id": 25, "name": "精华", "key": "essence",    "icon": "✨", "hotkey_key": "essence"},
]


def get_by_id(resource_id):
    """按ID查询资源定义，未找到返回 None"""
    for r in RESOURCES:
        if r["id"] == resource_id:
            return r
    return None


def get_id_to_field():
    """返回 {资源ID: 状态JSON字段名} 映射（供GUI显示用）"""
    return {r["id"]: r["key"] for r in RESOURCES}
