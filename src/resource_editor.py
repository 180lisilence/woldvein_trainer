"""
woldvein Trainer v0.3 - 资源修改模块

功能说明：
    修改游戏内的各种资源数值，包括9种基础资源、幸福度、知名度。
    通过执行Lua脚本直接修改g_camp.m_tbSource数组中的资源值。

资源ID映射（与游戏内一致）：
    id=1   金钱(money)
    id=2   矿产(mineral)    ← 注意：不是木料
    id=3   木料(wood)       ← 注意：不是矿产
    id=4   衣物(cloth)
    id=5   食物(food)
    id=6   水(water)
    id=7   人口(population)
    id=19  盐(salt)
    id=20  酒(wine)

核心函数：
    add_resource()     增加指定资源（默认+100万）
    max_happiness()    幸福度设为最大（999）
    add_fame()         增加知名度（默认+10000）
    add_all_resources() 一键增加所有资源（跳过人口）

技术要点：
    - 所有操作通过execute_lua_safe执行，异常不崩溃
    - 返回值类型检查：isinstance(result, int)，避免字符串比较报错
    - 人口资源(id=7)不自动增加（可能导致游戏异常）
"""
from .lua_engine import (
    execute_lua_safe, LUA_ADD_RESOURCE,
    LUA_MAX_HAPPINESS, LUA_ADD_FAME
)
from .logger import log, log_success, log_error, log_warning

# 资源定义来自唯一来源 src/resource_defs.py（含 hotkey_key 字段，供热键自动生成）
from .resource_defs import RESOURCES
from .constants import RESOURCE_ADD_AMOUNT, FAME_ADD_AMOUNT


def add_resource(resource_id, amount=RESOURCE_ADD_AMOUNT):
    """
    增加指定资源的数量。

    参数：
        resource_id: 资源ID（1-7, 19, 20）
        amount: 增加数量（默认100万）

    返回：
        True表示成功，False表示失败

    实现：
        执行LUA_ADD_RESOURCE脚本，直接修改g_camp.m_tbSource[id]
    """
    res_info = next((r for r in RESOURCES if r["id"] == resource_id), None)
    name = res_info["name"] if res_info else f"ID{resource_id}"

    # 人口资源特殊处理：人口由游戏系统自动管理，手动增加可能导致异常
    if resource_id == 7:
        log_warning("注意：人口资源由游戏系统管理，手动增加可能导致人口与建筑/工作不匹配")

    code = LUA_ADD_RESOURCE % (resource_id, amount)
    success, result = execute_lua_safe(code)

    # 检查返回值类型：Lua返回布尔→C转数字1/0
    if success and isinstance(result, int) and result > 0:
        log_success(f"{name} +{amount:,}")
        return True
    else:
        log_error(f"{name} 增加失败（可能g_camp未就绪，请先进入游戏场景）")
        return False


def max_happiness():
    """
    幸福度设为最大（999）。

    执行LUA_MAX_HAPPINESS脚本，设置：
        g_camp.m_nHappinessScore = 999
        g_camp.m_nHappinessLevel = 4

    返回：
        True表示成功，False表示失败
    """
    success, result = execute_lua_safe(LUA_MAX_HAPPINESS)
    if success and isinstance(result, int) and result > 0:
        log_success("幸福度已设为最大 (999)")
        return True
    else:
        log_error("幸福度设置失败")
        return False


def add_fame(amount=FAME_ADD_AMOUNT):
    """
    增加知名度。

    执行LUA_ADD_FAME脚本，遍历多个可能的知名度字段：
        m_nFame, m_nReputation, m_nFameScore, m_nPublicity, m_nFameValue
    找到第一个存在的字段并增加。

    参数：
        amount: 增加数量（默认10000）

    返回：
        True表示成功，False表示失败（未找到知名度字段）
    """
    code = LUA_ADD_FAME % amount
    success, result = execute_lua_safe(code)
    if success and isinstance(result, str) and result.startswith("知名度"):
        log_success(result)
        return True
    else:
        log_error(f"知名度增加失败: {result}")
        return False


def add_all_resources(amount=RESOURCE_ADD_AMOUNT):
    """
    一键增加所有资源（跳过人口）。

    参数：
        amount: 每种资源增加数量（默认100万）

    返回：
        成功增加的资源种类数

    注意：
        人口资源(id=7)不自动增加，可能导致游戏异常
    """
    log("开始一键增加所有资源...")
    success_count = 0
    for res in RESOURCES:
        if res["id"] == 7:  # 人口不自动加
            continue
        if add_resource(res["id"], amount):
            success_count += 1
    log_success(f"资源增加完成: {success_count}/{len(RESOURCES)-1} 项成功")
    return success_count


# ============================================================
# v0.3 新增：资源恢复功能
# ============================================================

LUA_ZERO_RESOURCES = r"""
local ok, err = pcall(function()
    if not g_camp or not g_camp.m_tbSource then
        return 0
    end
    -- 将所有资源归零（跳过人口 id=7）
    local ids = {1, 2, 3, 4, 5, 6, 19, 20}
    for _, id in ipairs(ids) do
        if g_camp.m_tbSource[id] then
            g_camp.m_tbSource[id] = 0
        end
    end
    -- 触发资源刷新
    pcall(function() g_camp:OnResourceChange() end)
    pcall(function() S2UI_UpdateSource() end)
    return 1
end)
if not ok then return 0 end
return err
"""

LUA_RESTORE_HAPPINESS = r"""
local ok, err = pcall(function()
    if not g_camp then return 0 end
    -- 恢复幸福度为初始值
    g_camp.m_nHappinessScore = 60
    g_camp.m_nHappinessLevel = 1
    pcall(function() S2UI_UpdateHappiness() end)
    return 1
end)
if not ok then return 0 end
return err
"""


def zero_all_resources():
    """资源归零（将所有资源设为0，跳过人口）"""
    from .lua_engine import execute_lua_safe
    from .logger import log, log_success, log_error
    log("正在归零所有资源...")
    success, result = execute_lua_safe(LUA_ZERO_RESOURCES)
    if success and isinstance(result, int) and result > 0:
        log_success("所有资源已归零")
    else:
        log_error("资源归零失败")
    return success


def restore_happiness():
    """恢复幸福度为初始值"""
    from .lua_engine import execute_lua_safe
    from .logger import log, log_success, log_error
    log("正在恢复幸福度...")
    success, result = execute_lua_safe(LUA_RESTORE_HAPPINESS)
    if success and isinstance(result, int) and result > 0:
        log_success("幸福度已恢复为初始值 (60)")
    else:
        log_error("幸福度恢复失败")
    return success
