#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
woldvein Trainer v0.3 - 高级工具模块

功能说明：
    提供高级游戏修改功能，包括NPC管理、时间天气控制、
    资源人口重算、建造升级细粒度控制、SimWorld级操作。

子模块：
    1. NPC管理：获取NPC列表、添加NPC（名士/幕僚）、移除所有NPC
    2. 时间/天气控制：获取时间状态、设置时间速度、设置季节、跳过天数/月数
    3. 资源/人口重算：重新计算游戏内资源和人口
    4. 建造/升级控制：获取建筑列表、升级全部建筑、立即完成建造
    5. SimWorld操作：获取SimWorld状态、人口状态

关键技术事实：
    - LTimeManager是Lua脚本层类（非C++绑定），位于time_manager.lua
    - MIN_TIME_SPEED=1, MAX_TIME_SPEED=50
    - 暂停游戏用直接修改m_tb.m_nTimeSpeed=0实现（LogicPause是空函数）
    - SetBlockTimeToDaysLater是挑战区块专用，不是全局时间跳过
    - NPC删除先收集到临时表再销毁（避免在pairs迭代中修改表）

按钮冷却：
    升级全部和立即完成各自独立3秒冷却，防止频繁点击导致游戏失控
"""
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.lua_engine import execute_lua_safe, execute_lua_retry
from src.logger import log, log_success, log_error, log_warning

# 代码重构：从 cheat_tools 导入重复函数，消除重复定义
from src.cheat_tools import max_all_talents as _cheat_max_all_talents

from src.constants import (
    APP_VERSION,
    BOOM_MAX_LEVEL,
    ACHIEVEMENT_ID_SCAN_LIMIT,
    LUA_TIMEOUT,
    LUA_TIMEOUT_LONG,
)

# ============================================================
# 共享 Lua 片段
#   同一段 Lua 逻辑只写一次，由多个脚本用 + 拼接复用（避免复制粘贴）
# ============================================================

# 时间管理器解析
_LUA_TM_HEAD = r"""
    local tm = g_Time  -- 时间管理器全局变量名是 g_Time
    if not tm or not tm.m_tb then
        return "[失败] TimeManager 不存在（请先进入游戏场景）"
    end
"""

# 历法推算（依赖已定义的局部变量 days）
_LUA_CALENDAR = r"""    -- 历法常量（游戏 360 天历法：12 月 × 30 天）
    local DM = 30
    local DY = 360
    local SPD = 86400
    local MAX_SKIP = 3600
    -- 【关键】m_nDayStamp 是“累计天数”（游戏 _updateDay 逐日累加、跨年不重置）。
    --   证据：GetDayStamp() 在游戏里只被灾害调度用作差值
    --   （如 LBaseDisaster:DisasterReliefEvent 的 `GetDayStamp() - m_nProbTime < IntervalDay`），
    --   必须单调递增；故回写一律用“天数增量”，见下方 newStamp。
    local curDay = tm.m_tb.m_nDay or 1
    local curMonth = tm.m_tb.m_nMonth or 1
    local curYear = tm.m_tb.m_nYear or 1
    local curTime = tm.m_tb.m_nCurTime or 0
    local curStamp = tm.m_tb.m_nDayStamp or 0
    local season = tm.m_tb.m_nSeason
    -- 安全上限：单次最多跳 MAX_SKIP 天（10 年）
    if days > MAX_SKIP then days = MAX_SKIP end
    if days < -MAX_SKIP then days = -MAX_SKIP end

    local dayOfYear = (curMonth - 1) * DM + curDay + days
    local addYears = math.floor((dayOfYear - 1) / DY)
    local remain = dayOfYear - addYears * DY
    local newYear = curYear + addYears
    local newMonth = math.floor((remain - 1) / DM) + 1
    local newDay = remain - (newMonth - 1) * DM
    -- [FIX 2026-09-14] 按“天数增量”累加，保持 m_nDayStamp 单调累计语义
    local newStamp = curStamp + days
    if newYear < 1 then newYear = 1 end

    if tm.UpdateSpecialTime then
        tm:UpdateSpecialTime(newYear, newMonth, newDay, season, curTime + days * SPD, newStamp)
    else
        tm.m_tb.m_nYear = newYear
        tm.m_tb.m_nMonth = newMonth
        tm.m_tb.m_nDay = newDay
        tm.m_tb.m_nDayStamp = newStamp
        tm.m_tb.m_nCurTime = curTime + days * SPD
    end
"""

# 建筑管理器 + 当前选中区块 解析
_LUA_BUILDINGMGR_HEAD = r"""    local BWM = g_BuildingWorldModule
    if not BWM or not BWM.BuildingMgr then
        return "BuildingMgr 不存在"
    end
    local block = g_blockMgr and g_blockMgr:GetSelectedBlock()
    if not block then
        return "未选择区块"
    end
"""

# NPC 管理器解析（城市NPC管理器）
# [FIX 2026-09-14] 实机确认 g_CityManager 上只有 m_lsCityInfo、没有 m_lActiveCity；
#   且 GetActiveCity() 在无活跃城市时返回 nil。改为「GetActiveCity() 优先 + 旧字段兜底」。
_LUA_NPC_MGR_HEAD = r"""    local city = nil
    if g_CityManager and g_CityManager.GetActiveCity then
        local okc, c = pcall(function() return g_CityManager:GetActiveCity() end)
        if okc then city = c end
    end
    if not city and g_CityManager then city = g_CityManager.m_lActiveCity end
    local mgr = city and city.m_lCityNpcMgr or nil
    if not mgr then
        return "[失败] 城市NPC管理器不可用（GetActiveCity=" .. tostring(city) .. "，需进入有活跃城市的存档）"
    end
"""

# 表格 → 可读文本（游戏 Lua 环境常缺 cjson；替代 cjson.encode）
_LUA_TB2TEXT = r"""local function __tb2text(tb)
    local out = {}
    local n = #tb
    if n > 0 then
        for i = 1, n do
            local v = tb[i]
            if type(v) == "table" then
                local sub = {}
                for k, vv in pairs(v) do table.insert(sub, tostring(k) .. "=" .. tostring(vv)) end
                table.sort(sub)
                table.insert(out, "  " .. i .. ". " .. table.concat(sub, ", "))
            else
                table.insert(out, "  " .. i .. ". " .. tostring(v))
            end
        end
    else
        local keys = {}
        for k in pairs(tb) do table.insert(keys, k) end
        table.sort(keys, function(a, b) return tostring(a) < tostring(b) end)
        for _, k in ipairs(keys) do
            table.insert(out, "  " .. tostring(k) .. " = " .. tostring(tb[k]))
        end
    end
    return table.concat(out, "\n")
end
"""

# 倍速基准解析（只认游戏权威值；SET_SPEED / RESTORE_TIME_SPEED 共用）
_LUA_TIME_BASE_RESOLVE = r"""    -- 【v0.3 修复】原始值只认游戏权威值 define.DAY_TIME_REAL / define.DAY_TICK_COUNT
    --   绝不再用"当前值"当基准：否则游戏自己改动后会导致倍速滚雪球（越点越快）
    local base = nil
    local d = _G.define
    if d and d.DAY_TIME_REAL and d.DAY_TICK_COUNT and d.DAY_TICK_COUNT ~= 0 then
        base = d.DAY_TIME_REAL / d.DAY_TICK_COUNT
    end
    if not base or base <= 0 then base = g_trainer_base_delta end"""

# 繁荣度对象解析（BOOM_LEVEL_UP / BOOM_GET_CURRENT 共用）
_LUA_BOOM_RESOLVE = r"""    -- 获取当前繁荣度对象
    local boom = nil
    if g_camp and g_camp.boom then
        boom = g_camp.boom
    elseif g_CityManager and g_CityManager.m_lActiveCity then
        local city = g_CityManager.m_lActiveCity
        if city.boom then boom = city.boom end
    end
    if not boom then
        return "[失败] g_camp.boom 不存在（请先进入游戏场景）"
    end"""

# 把 __BOOM_MAX__ 占位符替换为鸿业上限常量（Lua 模板与常量解耦）
def _boom_lua(template):
    """注入鸿业上限到 Lua 模板。"""
    return template.replace("__BOOM_MAX__", str(BOOM_MAX_LEVEL))


def _log_result(success, result, fail_msg):
    """统一处理 execute_lua_safe 的返回：按结果前缀分级打日志，并原样返回 (success, result)。

    各脚本返回值前缀约定：[成功] / [警告] / [提示] / 其它（视为失败）。
        fail_msg: 失败时的上下文短语，如 "跳过天数失败"
    """
    if success and isinstance(result, str):
        if result.startswith("[成功]"):
            log_success(result)
        elif result.startswith("[警告]") or result.startswith("[提示]"):
            log_warning(result)
        else:
            log_error(result)
    else:
        log_error(f"{fail_msg}: {result}")
    return success, result


# ============================================================
# 1. NPC 管理
# ============================================================

LUA_NPC_LIST = _LUA_TB2TEXT + (r"""
local ok, err = pcall(function()
    -- [FIX 2026-09-14] 城市NPC管理器在无活跃城市时不可用（实机 GetActiveCity()=nil），
    --   改为多来源探测：城市NPC管理器 → 全局 LNPCManager → 观光NPC管理器
    local mgr, tbl, src = nil, nil, nil
    if g_CityManager and g_CityManager.GetActiveCity then
        local okc, city = pcall(function() return g_CityManager:GetActiveCity() end)
        if okc and city and city.m_lCityNpcMgr then
            mgr, src = city.m_lCityNpcMgr, "CityNpcMgr"
        end
    end
    if not mgr and g_LNPCManager then
        mgr, tbl, src = g_LNPCManager, g_LNPCManager.npcs, "LNPCManager"
    end
    if not mgr and g_LSightSeeingNPCMgr then
        mgr, tbl, src = g_LSightSeeingNPCMgr, g_LSightSeeingNPCMgr.tbRoles, "SightSeeingNPCMgr"
    end
    if not mgr then
        return "[失败] 未找到可用 NPC 管理器（CityNpcMgr / LNPCManager / SightSeeingNPCMgr 均不可用）"
    end
    if not tbl then tbl = mgr.tabNpcs end
    local lines = {}
    local count = 0
    if tbl then
        for id, npc in pairs(tbl) do
            count = count + 1
            if count <= 50 then
                local parts = {"id=" .. tostring(id)}
                -- [FIX 2026-09-14] LNPC 的名字/性别/年龄在 tabMateData（实机实测确认）
                do
                    local md = nil
                    if type(npc) == "table" then
                        md = npc.tabMateData
                        if md == nil and npc.GetMetaData then
                            local okm, v = pcall(function() return npc:GetMetaData() end)
                            if okm then md = v end
                        end
                    end
                    if md == nil and g_LNPCManager and type(g_LNPCManager.NpcRes) == "table" then
                        local res = g_LNPCManager.NpcRes[id]
                        if type(res) == "table" then md = res.tabMateData end
                    end
                    if type(md) == "table" then
                        if md.Name ~= nil then table.insert(parts, "name=" .. tostring(md.Name)) end
                        if md.Gender ~= nil then table.insert(parts, "gender=" .. tostring(md.Gender)) end
                        if md.Age ~= nil then table.insert(parts, "age=" .. tostring(md.Age)) end
                    end
                end
                if type(npc) == "table" then
                    if npc.GetName then local okn, n = pcall(function() return npc:GetName() end); if okn then table.insert(parts, "name=" .. tostring(n)) end end
                    if npc.GetCareer then local okc2, ca = pcall(function() return npc:GetCareer() end); if okc2 then table.insert(parts, "career=" .. tostring(ca)) end end
                    if npc.GetLevel then local okl, lv = pcall(function() return npc:GetLevel() end); if okl then table.insert(parts, "level=" .. tostring(lv)) end end
                end
                table.insert(lines, "  " .. table.concat(parts, ", "))
            end
        end
    end
    table.insert(lines, 1, "NPC总数: " .. tostring(count) .. " (显示前50个)  来源=" .. tostring(src))
    return table.concat(lines, "\n")
end)
if not ok then return "[错误] " .. tostring(err) end
return err
""")

LUA_NPC_ADD = (r"""
local ok, err = pcall(function()
    local career = "%s"
""" + _LUA_NPC_MGR_HEAD + r"""    if mgr.CreateMainNpcWithCareer then
        local npc = mgr:CreateMainNpcWithCareer(career, {}, false)
        if npc then
            return "NPC创建成功: " .. career
        end
    end
    return "NPC创建失败"
end)
return ok and err or "执行失败: " .. tostring(err)
""")

LUA_NPC_REMOVE_ALL = (r"""
local ok, err = pcall(function()
""" + _LUA_NPC_MGR_HEAD + r"""    local count = 0
    if mgr.tabNpcs then
        -- 先收集到临时表，避免在pairs迭代中修改表
        local tmp = {}
        for _, npc in pairs(mgr.tabNpcs) do table.insert(tmp, npc) end
        for _, npc in ipairs(tmp) do
            if mgr.DestroyNpc then
                mgr:DestroyNpc(npc)
                count = count + 1
            end
        end
    end
    return string.format("已销毁 %d 个NPC", count)
end)
return ok and err or "执行失败: " .. tostring(err)
""")

# ============================================================
# 2. 时间/天气控制
# ============================================================

LUA_TIME_GET_STATUS = _LUA_TB2TEXT + r"""
local ok, err = pcall(function()
    local tm = g_Time  -- 时间管理器全局变量名是g_Time，不是g_TimeManager
    if not tm then
        return "TimeManager 不存在"
    end
    local info = {}
    if tm.GetYear then info.year = tm:GetYear() end
    if tm.GetMonth then info.month = tm:GetMonth() end
    if tm.GetDay then info.day = tm:GetDay() end
    if tm.GetHour then info.hour = tm:GetHour() end
    if tm.GetSeason then info.season = tm:GetSeason() end
    if tm.GetCurSeason then info.cur_season = tm:GetCurSeason() end
    if tm.GetTimeSpeed then info.speed = tm:GetTimeSpeed() end
    if tm.GetDayStamp then info.day_stamp = tm:GetDayStamp() end
    -- 纯文本输出（游戏 Lua 环境无 cjson）
    return __tb2text(info)
end)
return ok and err or "执行失败: " .. tostring(err)
"""

LUA_TIME_SET_SPEED = (r"""
local ok, err = pcall(function()
    local speed = %d
    if speed <= 0 then
        if g_Game and g_Game.LogicTickPause then
            g_Game:LogicTickPause()
            return "[成功] 游戏已暂停（LogicTickPause）"
        end
        return "[失败] 暂停失败：g_Game:LogicTickPause 不存在"
    end
    if g_Game and g_Game.LogicTickResume then g_Game:LogicTickResume() end
    local gw = g_GameWorld
    if not gw then return "[失败] g_GameWorld 不存在（请先进入游戏场景）" end
    local cur = tonumber(gw.TICK_DELTA_TIMES) or 0
""" + _LUA_TIME_BASE_RESOLVE + r"""

    if not base or base <= 0 then base = cur end
    if not base or base <= 0 then return "[失败] 无法确定原始 TICK_DELTA_TIMES" end

    local newDelta = base / speed
    -- 安全钳制：等效超过 50x 或慢过 1/60 视为异常，直接中止
    if newDelta < 0.05 then
        return "[失败] 计算结果异常（" .. tostring(newDelta) .. "），已中止。请先点「↩ 恢复速度」"
    end
    if newDelta > 60 then
        return "[失败] 计算结果异常（" .. tostring(newDelta) .. "），已中止"
    end

    gw.TICK_DELTA_TIMES = newDelta
    g_trainer_base_delta = base
    g_trainer_last_delta = newDelta
    if g_Time and g_Time.m_tb then g_Time.m_tb.m_nTimeSpeed = 1 end
    return "[成功] 速度设为 " .. tostring(speed) .. "x（原始 " .. tostring(base) .. " -> 当前 " .. tostring(newDelta) .. "）"
end)
if not ok then return "[错误] " .. tostring(err) end
return err
""")

LUA_TIME_SET_SEASON = r"""
local ok, err = pcall(function()
    local season = %d
    local tm = g_Time  -- 时间管理器全局变量名是g_Time，不是g_TimeManager
    if not tm then
        return "[失败] TimeManager 不存在（请先进入游戏场景）"
    end
    -- 1. 直接设置内部季节字段（用于显示）
    if tm.m_tb then
        tm.m_tb.m_nSeason = season
    end
    -- 1b.【修复】同步日期到该季节区间，避免“7月的冬天”
    --     季节区间：春=1~3月, 夏=4~6月, 秋=7~9月, 冬=10~12月
    local synced = false
    if tm.m_tb then
        local startMonth = (season - 1) * 3 + 1
        local endMonth = season * 3
        local oldMonth = tm.m_tb.m_nMonth or 1
        local oldDay = tm.m_tb.m_nDay or 1
        local curMonth = oldMonth
        local curDay = oldDay
        if curMonth < startMonth or curMonth > endMonth then
            curMonth = startMonth
            if curDay > 30 then curDay = 30 end
            tm.m_tb.m_nMonth = curMonth
            tm.m_tb.m_nDay = curDay
            -- [FIX 2026-09-14] m_nDayStamp 是累计天数：按“日序差值”保持单调，
            --   不能再写成 (月-1)*30+日（会把累计值拉回年内值，破坏灾害计时）
            if tm.m_tb.m_nDayStamp then
                local oldDoy = (oldMonth - 1) * 30 + oldDay
                local newDoy = (curMonth - 1) * 30 + curDay
                tm.m_tb.m_nDayStamp = tm.m_tb.m_nDayStamp + (newDoy - oldDoy)
            end
            synced = true
        end
    end
    if tm.SetSeason then
        pcall(function() tm:SetSeason(season) end)
    end
    -- 2. 核心：Hook GetCurSeason / GetSeason，防止游戏根据日期重算覆盖
    --    游戏的 GetCurSeason 会根据 m_nMonth 重新计算季节，导致 SetSeason 无效
    --    保存原始方法（只保存一次），然后替换为返回固定季节
    if not g_trainer_orig_GetCurSeason then
        g_trainer_orig_GetCurSeason = tm.GetCurSeason
    end
    if not g_trainer_orig_GetSeason then
        g_trainer_orig_GetSeason = tm.GetSeason
    end
    tm.GetCurSeason = function(self) return season end
    tm.GetSeason = function(self) return season end
    -- 3. 尝试触发季节环境刷新（树木变色、下雪等视觉效果）
    pcall(function()
        if tm._whenTimeGoOn then
            tm:_whenTimeGoOn(true)
        end
    end)
    pcall(function()
        -- [API-FIX] LGameWorld 没有 RefreshSeason；季节刷新走 GameWorldAudio:OnNewSeason
        if g_GameWorld and g_GameWorld.GameWorldAudio and g_GameWorld.GameWorldAudio.OnNewSeason then
            pcall(function() g_GameWorld.GameWorldAudio:OnNewSeason(season) end)
        end
    end)
    -- 4. 触发UI刷新
    pcall(function()
        if g_LHBUIProvider and g_LHBUIEvents then
            g_LHBUIProvider:EmitTo("LSystemProvider", g_LHBUIEvents.S2UI_OnSeasonChange, season)
        end
    end)
    local dateInfo = ""
    if tm.m_tb then
        dateInfo = "，日期=" .. tostring(tm.m_tb.m_nYear) .. "年" .. tostring(tm.m_tb.m_nMonth) .. "月" .. tostring(tm.m_tb.m_nDay) .. "日"
    end
    return "[成功] 季节已设为 " .. tostring(season) .. "（日期同步=" .. tostring(synced) .. dateInfo .. "）"
end)
return ok and err or "执行失败: " .. tostring(err)
"""

LUA_TIME_SKIP_DAYS = (r"""
local ok, err = pcall(function()
    local days = %d
""" + _LUA_TM_HEAD + _LUA_CALENDAR + r"""    return string.format("[成功] 跳过 %%d 天：%%d年%%d月%%d日 -> %%d年%%d月%%d日", days, curYear, curMonth, curDay, newYear, newMonth, newDay)
end)
if not ok then return "[错误] " .. tostring(err) end
return err
""")

LUA_TIME_SKIP_MONTHS = (r"""
local ok, err = pcall(function()
    local months = %d
""" + _LUA_TM_HEAD + r"""    local days = months * 30
""" + _LUA_CALENDAR + r"""    return string.format("[成功] 跳过 %%d 个月(%%d天)：%%d年%%d月%%d日 -> %%d年%%d月%%d日", months, days, curYear, curMonth, curDay, newYear, newMonth, newDay)
end)
if not ok then return "[错误] " .. tostring(err) end
return err
""")

# ============================================================
# 3. 资源/人口重算
# ============================================================

LUA_RESOURCE_RECALC = r"""
local ok, err = pcall(function()
    -- 触发资源重算
    local camp = g_camp
    if not camp then
        return "g_camp 不存在"
    end
    local count = 0
    -- 遍历所有资源类型，触发更新
    local resourceIds = {1,2,3,4,5,6,7,19,20}
    for _, id in ipairs(resourceIds) do
        if camp.ModifySourceValue then
            camp:ModifySourceValue(id, 0, true)
            count = count + 1
        end
    end
    -- [API-FIX] camp 没有 UpdatePopulation；人口重算在 LPopulationManager
    pcall(function()
        if g_LPopulationManager and g_LPopulationManager._forceAllocatePopulation then
            g_LPopulationManager:_forceAllocatePopulation()
        end
    end)
    return string.format("资源重算完成: %d 种资源", count)
end)
return ok and err or "执行失败: " .. tostring(err)
"""

LUA_POPULATION_STATUS = _LUA_TB2TEXT + r"""
local ok, err = pcall(function()
    local camp = g_camp
    if not camp then
        return "g_camp 不存在"
    end
    local info = {}
    -- [FIX 2026-09-14] LBaseBlock:GetPopulation(tbPSource) 必须带参数：无参会直接 return 0（并打 Traceback）。
    --   人口改读资源档：CURRENT_POPULATION=7；上限 = MAX_POPULATION[8] + MAX_REFUGEE_POPULATION[14]
    if camp.GetSourceValue and block_define and block_define.SOURCE then
        local S = block_define.SOURCE
        local ok1, pop = pcall(function() return camp:GetSourceValue(S.CURRENT_POPULATION) end)
        if ok1 then info.population = pop end
        local ok2, mx = pcall(function()
            return camp:GetSourceValue(S.MAX_POPULATION) + camp:GetSourceValue(S.MAX_REFUGEE_POPULATION)
        end)
        if ok2 then info.pop_max = mx end
    end
    if camp.GetDemilitarizedPopulation then
        local ok3, d = pcall(function() return camp:GetDemilitarizedPopulation() end)
        if ok3 then info.demilitarized = d end
    end
    if camp.GetMaxPopulation then
        local ok4, m = pcall(function() return camp:GetMaxPopulation() end)
        if ok4 then info.max_population = m end
    end
    if camp.GetHappiness then info.happiness = camp:GetHappiness() end
    -- [API-FIX] LCamp 没有 GetMoney；金钱在 LBaseBlock:GetSourceValue(SOURCE.MONEY)
    if camp.GetSourceValue and block_define and block_define.SOURCE then
        info.money = camp:GetSourceValue(block_define.SOURCE.MONEY)
    end
    return __tb2text(info)
end)
return ok and err or "执行失败: " .. tostring(err)
"""

# ============================================================
# 4. 建造/升级细粒度控制
# ============================================================

LUA_BUILDING_LIST = _LUA_TB2TEXT + (r"""
local ok, err = pcall(function()
""" + _LUA_BUILDINGMGR_HEAD + r"""    local result = {}
    local count = 0
    -- 遍历所有GDP组合
    for g = 0, 10 do
        for d = 0, 10 do
            for p = 0, 10 do
                local list = BWM.BuildingMgr:GetBlockBuildingListByGDP(block.nId, g, d, p)
                if list then
                    for _, building in ipairs(list) do
                        count = count + 1
                        if count <= 30 then
                            local info = {}
                            if building.GetName then info.name = building:GetName() end
                            if building.GetLevel then info.level = building:GetLevel() end
                            if building.GetStatus then info.status = building:GetStatus() end
                            info.g = g
                            info.d = d
                            info.p = p
                            table.insert(result, info)
                        end
                    end
                end
            end
        end
    end
    return string.format("建筑总数: %d (显示前30个)", count) .. "\n" .. __tb2text(result)
end)
return ok and err or "执行失败: " .. tostring(err)
""")

LUA_BUILDING_UPGRADE_ALL = (r"""
local ok, err = pcall(function()
""" + _LUA_BUILDINGMGR_HEAD + r"""    local upgraded = 0
    local failed = 0
    for g = 0, 10 do
        for d = 0, 10 do
            for p = 0, 10 do
                local list = BWM.BuildingMgr:GetBlockBuildingListByGDP(block.nId, g, d, p)
                if list then
                    for _, building in ipairs(list) do
                        local canUpgrade = BWM.BuildingMgr:CheckCanUpgradeBuilding(building)
                        if canUpgrade then
                            local bOK, szErr = BWM.BuildingMgr:UpgradeBuilding(building)
                            if bOK then
                                upgraded = upgraded + 1
                            else
                                failed = failed + 1
                            end
                        end
                    end
                end
            end
        end
    end
    return string.format("升级完成: 成功%d, 失败%d", upgraded, failed)
end)
return ok and err or "执行失败: " .. tostring(err)
""")

LUA_BUILDING_FINISH_ALL = (r"""
local ok, err = pcall(function()
""" + _LUA_BUILDINGMGR_HEAD + r"""    local finished = 0
    for g = 0, 10 do
        for d = 0, 10 do
            for p = 0, 10 do
                local list = BWM.BuildingMgr:GetBlockBuildingListByGDP(block.nId, g, d, p)
                if list then
                    for _, building in ipairs(list) do
                        -- 直接设置建筑状态为完成
                        if building.SetStatus then
                            pcall(function() building:SetStatus(0) end)  -- BS_FINISHED
                            finished = finished + 1
                        end
                    end
                end
            end
        end
    end
    return string.format("已完成 %d 个建筑", finished)
end)
return ok and err or "执行失败: " .. tostring(err)
""")

# ============================================================
# 5. SimWorld 级操作
# ============================================================

LUA_SIMWORLD_STATUS = _LUA_TB2TEXT + r"""
local ok, err = pcall(function()
    local info = {}
    -- 游戏世界状态
    if g_GameWorld then
        -- [API-FIX] LGameWorld 没有 GetName/GetFrameCount/IsPaused；
        --   帧数在 BuildingMgr:GetFrameTotalCount()，暂停在 g_Game:IsPaused()
        local _bm = g_BuildingWorldModule and g_BuildingWorldModule.BuildingMgr
        if _bm and _bm.GetFrameTotalCount then info.frame_count = _bm:GetFrameTotalCount() end
        if g_Game and g_Game.IsPaused then info.paused = g_Game:IsPaused() end
    end
    -- 区块信息
    if g_blockMgr then
        if g_blockMgr.GetSelectedBlock then
            local block = g_blockMgr:GetSelectedBlock()
            if block then
                info.block_id = block.nId
                if block.GetName then info.block_name = block:GetName() end
            end
        end
    end
    return __tb2text(info)
end)
return ok and err or "执行失败: " .. tostring(err)
"""

LUA_SIMWORLD_PAUSE = r"""
local ok, err = pcall(function()
    -- 暂停游戏：调用 g_Game:LogicTickPause（真正停止逻辑Tick，建筑/NPC全部停止）
    if g_Game and g_Game.LogicTickPause then
        g_Game:LogicTickPause()
        return "[成功] 游戏已暂停（LogicTickPause）"
    end
    -- 备选：g_GameWorld.LogicPause
    if g_GameWorld and g_GameWorld.LogicPause then
        g_GameWorld:LogicPause()
        return "[成功] 游戏已暂停（LogicPause）"
    end
    return "[失败] 暂停失败：g_Game:LogicTickPause 不存在（请先进入游戏场景）"
end)
return ok and err or "执行失败: " .. tostring(err)
"""

LUA_SIMWORLD_RESUME = r"""
local ok, err = pcall(function()
    -- 继续游戏：调用 g_Game:LogicTickResume
    if g_Game and g_Game.LogicTickResume then
        g_Game:LogicTickResume()
        return "[成功] 游戏已继续（LogicTickResume）"
    end
    return "[失败] 继续失败：g_Game:LogicTickResume 不存在（请先进入游戏场景）"
end)
return ok and err or "执行失败: " .. tostring(err)
"""

# ============================================================
# 6. 时间系统诊断
# ============================================================

LUA_TIME_DIAGNOSE = r"""
local ok, err = pcall(function()
    local lines = {}
    table.insert(lines, "========== 时间系统诊断报告 ==========")
    
    local tm = g_Time
    if not tm then
        table.insert(lines, "[错误] g_Time 不存在（请先进入游戏场景）")
        return table.concat(lines, "\n")
    end
    
    table.insert(lines, "")
    table.insert(lines, "【1. 基本信息】")
    table.insert(lines, string.format("  g_Time 类型: %s", type(tm)))
    table.insert(lines, string.format("  SetTimeSpeed 方法: %s", type(tm.SetTimeSpeed)))
    table.insert(lines, string.format("  GetTimeSpeed 方法: %s", type(tm.GetTimeSpeed)))
    table.insert(lines, string.format("  SetSeason 方法: %s", type(tm.SetSeason)))
    table.insert(lines, string.format("  GetSeason 方法: %s", type(tm.GetSeason)))
    table.insert(lines, string.format("  Tick 方法: %s", type(tm.Tick)))
    
    table.insert(lines, "")
    table.insert(lines, "【2. 当前时间状态】")
    if tm.GetYear then table.insert(lines, string.format("  年: %d", tm:GetYear())) end
    if tm.GetMonth then table.insert(lines, string.format("  月: %d", tm:GetMonth())) end
    if tm.GetDay then table.insert(lines, string.format("  日: %d", tm:GetDay())) end
    if tm.GetHour then table.insert(lines, string.format("  时: %d", tm:GetHour())) end
    if tm.GetSeason then table.insert(lines, string.format("  季节(GetSeason): %s", tostring(tm:GetSeason()))) end
    if tm.GetCurSeason then
        local s, sid = tm:GetCurSeason()
        table.insert(lines, string.format("  当前季节(GetCurSeason): %s (id=%s)", tostring(s), tostring(sid)))
    end
    if tm.GetTimeSpeed then table.insert(lines, string.format("  时间速度: %s", tostring(tm:GetTimeSpeed()))) end
    if tm.GetDayStamp then table.insert(lines, string.format("  日戳: %d", tm:GetDayStamp())) end
    
    table.insert(lines, "")
    table.insert(lines, "【3. 内部字段 (m_tb)】")
    if tm.m_tb then
        table.insert(lines, string.format("  m_nTimeSpeed: %s", tostring(tm.m_tb.m_nTimeSpeed)))
        table.insert(lines, string.format("  m_nSeason: %s", tostring(tm.m_tb.m_nSeason)))
        table.insert(lines, string.format("  m_nYear: %s", tostring(tm.m_tb.m_nYear)))
        table.insert(lines, string.format("  m_nMonth: %s", tostring(tm.m_tb.m_nMonth)))
        table.insert(lines, string.format("  m_nDay: %s", tostring(tm.m_tb.m_nDay)))
        table.insert(lines, string.format("  m_nCurTime: %s", tostring(tm.m_tb.m_nCurTime)))
        table.insert(lines, string.format("  m_nDayStamp: %s", tostring(tm.m_tb.m_nDayStamp)))
    else
        table.insert(lines, "  [警告] m_tb 不存在")
    end
    
    table.insert(lines, "")
    table.insert(lines, "【4. SetTimeSpeed 测试】")
    if tm.SetTimeSpeed and tm.GetTimeSpeed then
        local orig_speed = tm:GetTimeSpeed()
        table.insert(lines, string.format("  原始速度: %s", tostring(orig_speed)))
        -- 测试设置为3（用 pcall 保护，失败时跳过，避免异常中断诊断且不残留副作用）
        local ok_set, _ = pcall(function() tm:SetTimeSpeed(3) end)
        if ok_set then
            local after_set = tm:GetTimeSpeed()
            table.insert(lines, string.format("  SetTimeSpeed(3) 后: %s", tostring(after_set)))
            table.insert(lines, string.format("  m_tb.m_nTimeSpeed 实际值: %s", tostring(tm.m_tb and tm.m_tb.m_nTimeSpeed)))
            -- 恢复原始速度（也用 pcall 保护，防止恢复失败导致游戏卡在3x）
            pcall(function() tm:SetTimeSpeed(orig_speed) end)
            table.insert(lines, string.format("  已恢复为: %s", tostring(tm:GetTimeSpeed())))
        else
            -- SetTimeSpeed 调用异常，尝试恢复原值以防万一
            pcall(function() tm:SetTimeSpeed(orig_speed) end)
            table.insert(lines, "  [警告] SetTimeSpeed(3) 调用异常，已尝试恢复原值")
        end
    else
        table.insert(lines, "  无法测试：SetTimeSpeed 或 GetTimeSpeed 不存在")
    end

    table.insert(lines, "")
    table.insert(lines, "【5. SetSeason 测试】")
    if tm.SetSeason and tm.GetSeason then
        local orig_season = tm:GetSeason()
        table.insert(lines, string.format("  原始季节: %s", tostring(orig_season)))
        -- 测试设置季节（先测试2=夏天，用 pcall 保护，避免异常中断且不残留副作用）
        local ok_set, _ = pcall(function() tm:SetSeason(2) end)
        if ok_set then
            local after_set = tm:GetSeason()
            table.insert(lines, string.format("  SetSeason(2) 后 GetSeason(): %s", tostring(after_set)))
            table.insert(lines, string.format("  m_tb.m_nSeason 实际值: %s", tostring(tm.m_tb and tm.m_tb.m_nSeason)))
            -- 恢复原始季节（也用 pcall 保护，防止恢复失败导致游戏卡在错误季节）
            pcall(function() tm:SetSeason(orig_season) end)
            table.insert(lines, string.format("  已恢复为: %s", tostring(tm:GetSeason())))
        else
            -- SetSeason 调用异常，尝试恢复原值
            pcall(function() tm:SetSeason(orig_season) end)
            table.insert(lines, "  [警告] SetSeason(2) 调用异常，已尝试恢复原值")
        end
    else
        table.insert(lines, "  无法测试：SetSeason 或 GetSeason 不存在")
    end
    
    table.insert(lines, "")
    table.insert(lines, "【6. 时间速度常量】")
    -- [FIX 2026-09-14] 实际全局是 g_TimeDefine（time_define.lua 定义）；旧代码查的是 TimeDefine → 恒报"不存在"
    local TD = g_TimeDefine or TimeDefine
    if TD then
        table.insert(lines, string.format("  MIN_TIME_SPEED: %s", tostring(TD.MIN_TIME_SPEED)))
        table.insert(lines, string.format("  MAX_TIME_SPEED: %s", tostring(TD.MAX_TIME_SPEED)))
        table.insert(lines, string.format("  SECONDS_PER_DAY: %s", tostring(TD.SECONDS_PER_DAY)))
    else
        table.insert(lines, "  g_TimeDefine / TimeDefine 均不存在")
    end
    if _G.define then
        table.insert(lines, string.format("  define.DAY_TIME_REAL: %s", tostring(_G.define.DAY_TIME_REAL)))
        table.insert(lines, string.format("  define.DAY_TICK_COUNT: %s", tostring(_G.define.DAY_TICK_COUNT)))
    end

    table.insert(lines, "")
    table.insert(lines, "【7. 游戏速度核心：g_GameWorld.TICK_DELTA_TIMES】")
    if g_GameWorld then
        table.insert(lines, string.format("  TICK_DELTA_TIMES: %s", tostring(g_GameWorld.TICK_DELTA_TIMES)))
        table.insert(lines, string.format("  基准 g_trainer_base_delta: %s", tostring(g_trainer_base_delta)))
    table.insert(lines, string.format("  上次写入 g_trainer_last_delta: %s", tostring(g_trainer_last_delta)))
        if g_Game and g_Game.IsPaused then
            table.insert(lines, string.format("  g_Game:IsPaused(): %s", tostring(g_Game:IsPaused())))
        end
    else
        table.insert(lines, "  g_GameWorld 不存在")
    end
    if g_Game then
        table.insert(lines, string.format("  g_Game.LogicTickPause: %s", type(g_Game.LogicTickPause)))
        table.insert(lines, string.format("  g_Game.LogicTickResume: %s", type(g_Game.LogicTickResume)))
    else
        table.insert(lines, "  g_Game 不存在")
    end

    table.insert(lines, "")
    table.insert(lines, "【8. 全局变量名验证】")
    table.insert(lines, string.format("  g_Time 存在: %s", tostring(g_Time ~= nil)))
    table.insert(lines, string.format("  g_TimeManager 存在: %s", tostring(g_TimeManager ~= nil)))
    table.insert(lines, string.format("  g_TimeMgr 存在: %s", tostring(g_TimeMgr ~= nil)))
    table.insert(lines, string.format("  g_Game 存在: %s", tostring(g_Game ~= nil)))
    table.insert(lines, string.format("  g_GameWorld 存在: %s", tostring(g_GameWorld ~= nil)))
    
    table.insert(lines, "")
    table.insert(lines, "========== 诊断结束 ==========")
    return table.concat(lines, "\n")
end)
if not ok then return "诊断失败: " .. tostring(err) end
return err
"""

# ============================================================
# Python 封装函数
# ============================================================

def get_npc_list():
    """获取NPC列表"""
    return execute_lua_safe(LUA_NPC_LIST)

def add_npc(career):
    """添加NPC，转义特殊字符防止Lua代码注入"""
    safe_career = career.replace("\\", "\\\\").replace('"', '\\"')
    return execute_lua_safe(LUA_NPC_ADD % safe_career)

def remove_all_npcs():
    """移除所有NPC"""
    return execute_lua_safe(LUA_NPC_REMOVE_ALL)

def get_time_status():
    """获取时间状态"""
    return execute_lua_safe(LUA_TIME_GET_STATUS)

def set_time_speed(speed):
    """
    设置游戏速度 (0=暂停, 1=正常, 2=2倍, 3=3倍, 4=4倍)

    实现原理：
        通过修改 g_GameWorld.TICK_DELTA_TIMES 控制 LogicTick 触发频率。
        TICK_DELTA_TIMES = 原始值 / speed，间隔越小游戏越快。
        （原方案 g_Time:SetTimeSpeed 只影响日历，不影响建筑/NPC产出）
        speed=0 时调用 g_Game:LogicTickPause() 暂停逻辑Tick。

    返回：
        (success, result) 元组，result 为带 [成功]/[失败] 前缀的结果字符串
    """
    log(f"设置时间速度为 {speed}x ...")
    success, result = execute_lua_safe(LUA_TIME_SET_SPEED % speed)
    return _log_result(success, result, "设置时间速度失败")

def set_season(season):
    """
    设置季节 (1=春, 2=夏, 3=秋, 4=冬)

    实现：
        执行 LUA_TIME_SET_SEASON 脚本，脚本内部会调用 GetSeason 回读验证。

    返回：
        (success, result) 元组，result 为带前缀的结果字符串
    """
    # 支持字符串和数字两种输入
    season_map = {"春": 1, "夏": 2, "秋": 3, "冬": 4,
                  "spring": 1, "summer": 2, "autumn": 3, "winter": 4}
    if isinstance(season, str):
        season = season_map.get(season.strip(), 1)
    season_names = {1: "春", 2: "夏", 3: "秋", 4: "冬"}
    name = season_names.get(season, str(season))
    log(f"设置季节为 {name} ...")
    success, result = execute_lua_safe(LUA_TIME_SET_SEASON % season)
    return _log_result(success, result, "设置季节失败")

def skip_days(days):
    """
    跳过指定天数

    实现：
        执行 LUA_TIME_SKIP_DAYS 脚本，直接修改 m_tb 日期字段。
        已修复 newMonth 可能为 0 的边界 bug。

    返回：
        (success, result) 元组
    """
    log(f"跳过 {days} 天 ...")
    success, result = execute_lua_safe(LUA_TIME_SKIP_DAYS % days)
    return _log_result(success, result, "跳过天数失败")

def skip_months(months):
    """
    跳过指定月数

    实现：
        执行 LUA_TIME_SKIP_MONTHS 脚本，通过跳天实现跳月（months*30天），
        绕开 SetTimeToMonthsLater 的 challengeblock nil 错误。

    返回：
        (success, result) 元组
    """
    log(f"跳过 {months} 个月 ...")
    success, result = execute_lua_safe(LUA_TIME_SKIP_MONTHS % months)
    return _log_result(success, result, "跳过月数失败")

def recalc_resources():
    """重算资源"""
    return execute_lua_safe(LUA_RESOURCE_RECALC)

def get_population_status():
    """获取人口状态"""
    return execute_lua_safe(LUA_POPULATION_STATUS)

def get_building_list():
    """获取建筑列表"""
    return execute_lua_safe(LUA_BUILDING_LIST)

def upgrade_all_buildings():
    """升级所有可升级建筑"""
    return execute_lua_safe(LUA_BUILDING_UPGRADE_ALL)

def finish_all_buildings():
    """立即完成所有建筑"""
    return execute_lua_safe(LUA_BUILDING_FINISH_ALL)

def get_simworld_status():
    """获取SimWorld状态"""
    return execute_lua_safe(LUA_SIMWORLD_STATUS)

def pause_game():
    """
    暂停游戏（设置时间速度为0，绕过 MIN_TIME_SPEED 限制）

    返回：
        (success, result) 元组
    """
    log("暂停游戏 ...")
    success, result = execute_lua_safe(LUA_SIMWORLD_PAUSE)
    return _log_result(success, result, "暂停游戏失败")

def resume_game():
    """
    继续游戏（恢复原时间速度）

    返回：
        (success, result) 元组
    """
    log("继续游戏 ...")
    success, result = execute_lua_safe(LUA_SIMWORLD_RESUME)
    return _log_result(success, result, "继续游戏失败")

def diagnose_time_system():
    """时间系统诊断"""
    return execute_lua_safe(LUA_TIME_DIAGNOSE, timeout=8.0)


# ============================================================
# 天赋系统
# ============================================================

LUA_TALENT_DIAGNOSE = r"""
local ok, err = pcall(function()
    local lines = {}
    local TM = g_TalentManager
    if not TM then
        return "[失败] g_TalentManager 不存在"
    end
    table.insert(lines, "=== 天赋管理器方法列表 ===")
    -- 遍历所有方法，找出解锁相关的
    local unlock_methods = {}
    local all_methods = {}
    for k, v in pairs(TM) do
        if type(v) == "function" then
            table.insert(all_methods, k)
            local lk = string.lower(k)
            if string.find(lk, "unlock") or string.find(lk, "open") or string.find(lk, "active")
               or string.find(lk, "upmax") or string.find(lk, "addtalent") then
                table.insert(unlock_methods, k .. " (function)")
            end
        end
    end
    table.sort(all_methods)
    for _, name in ipairs(all_methods) do
        table.insert(lines, "  " .. name)
    end
    table.insert(lines, "")
    table.insert(lines, "=== 关键方法（解锁/满级/点数）===")
    for _, m in ipairs(unlock_methods) do
        table.insert(lines, "  " .. m)
    end
    -- 检查天赋数据
    table.insert(lines, "")
    table.insert(lines, "=== 天赋数据统计 ===")
    local total = 0
    local actived = 0
    local maxed = 0
    if TM.talentList then
        for typeIdx, typeList in ipairs(TM.talentList) do
            local typeCount = 0
            for _, tData in ipairs(typeList) do
                if tData and tData.TalentBaseData and tData.TalentUiKey ~= "" then
                    total = total + 1
                    typeCount = typeCount + 1
                    if tData.TalentActiveState and g_TalentActiveState
                       and tData.TalentActiveState == g_TalentActiveState.ACTIVED then
                        actived = actived + 1
                    end
                    if tData.MaxLevel and tData.TalentLevel and tData.TalentLevel >= tData.MaxLevel then
                        maxed = maxed + 1
                    end
                end
            end
            table.insert(lines, string.format("  类型%d: %d 个天赋", typeIdx, typeCount))
        end
    end
    table.insert(lines, string.format("  总计: %d 个天赋，已激活 %d，已满级 %d", total, actived, maxed))
    -- 天赋点数
    if TM.GetLeftTalentPoint then
        local pts = TM:GetLeftTalentPoint()
        table.insert(lines, string.format("  可用天赋点数: %s", tostring(pts)))
    end
    return table.concat(lines, "\n")
end)
return ok and err or "执行失败: " .. tostring(err)
"""

LUA_MAX_TALENT = r"""
local ok, err = pcall(function()
    local TM = g_TalentManager
    if not TM then
        -- 兜底：全局搜索天赋管理器（g_TalentManager 为 Lua 类 LTalentManager 实例，卸载场景时会被置 nil）
        for k, v in pairs(_G) do
            if type(v) == "table" and string.find(k, "Talent") then
                TM = v
                break
            end
        end
    end
    if not TM then
        return "[失败] 未找到天赋管理器（g_TalentManager / *Talent*，请先进入游戏场景）"
    end
    local result = {}

    -- ===== 第1层（核心）：调用官方 GM 方法，解锁所有天赋并升满级 =====
    -- UpMaxAllTalent() 内部遍历 self.talentList，设置：
    --   tData.TalentActiveState = g_TalentActiveState.ACTIVED  （激活）
    --   tData.TalentLevel = tData.MaxLevel                     （满级）
    if TM.UpMaxAllTalent then
        TM:UpMaxAllTalent()
        table.insert(result, "UpMaxAllTalent() 解锁+满级")
    end

    -- ===== 第2层：额外调用 UnlockAllTalent 确保全部解锁（设为1级） =====
    if TM.UnlockAllTalent then
        TM:UnlockAllTalent()
        table.insert(result, "UnlockAllTalent() 全解锁")
    end

    -- ===== 第3层：天赋点数拉满 =====
    if TM.AddTalentPoint then
        TM:AddTalentPoint(99999)
        table.insert(result, "天赋点+99999")
    end
    -- 直接设置可用天赋点数字段（备用方案）
    pcall(function()
        if TM.m_tbTalentPointInfo and TalentDefine then
            TM.m_tbTalentPointInfo[TalentDefine.TALENT_POINT_TYPE.CANUSE] = 99999
        end
    end)

    -- ===== 第4层（保底）：Hook 天赋判定方法，确保建筑解锁等判定通过 =====
    local hook_count = 0
    if not TM.__max_talent_hooked then
        if TM.CheckTalentIsActive then
            TM.__orig_CheckTalentIsActive = TM.CheckTalentIsActive
            TM.CheckTalentIsActive = function() return true end
            hook_count = hook_count + 1
        end
        if TM.CheckUnlockBuildingCardTalentIdIsUnlock then
            TM.__orig_CheckUnlockTalent = TM.CheckUnlockBuildingCardTalentIdIsUnlock
            TM.CheckUnlockBuildingCardTalentIdIsUnlock = function() return true end
            hook_count = hook_count + 1
        end
        if TM.CheckIsUnlockBuildingCard then
            TM.__orig_CheckIsUnlock = TM.CheckIsUnlockBuildingCard
            TM.CheckIsUnlockBuildingCard = function() return true end
            hook_count = hook_count + 1
        end
        TM.__max_talent_hooked = true
    end

    -- ===== 第5层：刷新 UI =====
    pcall(function()
        if TM.EmitTalentData and TM.talentList then
            for _, typeList in ipairs(TM.talentList) do
                for _, tData in ipairs(typeList) do
                    TM:EmitTalentData(tData)
                end
            end
        end
        if TM.EmitPointData then
            TM:EmitPointData()
        end
    end)
    -- 刷新建筑卡片（天赋影响建筑解锁状态）
    pcall(function()
        g_LHBUI:EmitTo("LBuildingProvider", g_LHBUIEvents.S2UI_OnUpdateBuildingCards)
    end)

    local msg = "[成功] 满天赋：" .. table.concat(result, "，")
    if hook_count > 0 then
        msg = msg .. "，Hook " .. hook_count .. " 个判定方法"
    end
    return msg
end)
return ok and err or "执行失败: " .. tostring(err)
"""


def diagnose_talent():
    """天赋系统诊断（列出 g_TalentManager 所有方法）

    注：当前 GUI 未接入调用（tab_advanced.py 只调用 diagnose_time_system，
    tab_creative.py 只调用 diagnose_unlock_status）。保留供未来扩展或
    通过 execute_lua 直接调用。删除会丢失诊断能力，故保留。
    """
    return execute_lua_safe(LUA_TALENT_DIAGNOSE, timeout=8.0)


def max_all_talents():
    """
    满天赋：解锁所有天赋节点

    实现：
        1. hook CheckTalentIsActive / CheckUnlockBuildingCardTalentIdIsUnlock / CheckIsUnlockBuildingCard
           让所有天赋判定返回 true（保底生效）
        2. 尝试调用真实的解锁方法（如 UnlockAllTalents），让 UI 也显示已解锁
        3. 如有天赋点数字段，设为 99999

    返回：
        (success, result) 元组
    """
    log("正在激活满天赋...")
    success, result = execute_lua_safe(LUA_MAX_TALENT, timeout=10.0)
    return _log_result(success, result, "满天赋激活失败")


# ============================================================
# 城市品阶（鸿业）条件完成
# ============================================================

LUA_BOOM_DIAGNOSE = r"""
local ok, err = pcall(function()
    local lines = {}
    local camp = g_camp
    if not camp then
        return "[失败] g_camp 不存在"
    end
    local boom = camp.GetCampBoomModule and camp:GetCampBoomModule()
    if not boom then
        return "[失败] Boom 模块不存在"
    end

    table.insert(lines, "=== Boom 模块方法列表 ===")
    local mt = getmetatable(boom)
    if mt and mt.__index then
        local cls = mt.__index
        local methods = {}
        for k, v in pairs(cls) do
            if type(v) == "function" then
                table.insert(methods, k)
            end
        end
        table.sort(methods)
        for _, m in ipairs(methods) do
            table.insert(lines, "  " .. m)
        end
    end

    table.insert(lines, "")
    table.insert(lines, "=== Boom 模块字段 ===")
    for k, v in pairs(boom) do
        if type(v) ~= "function" then
            local sv = tostring(v)
            if #sv > 80 then sv = sv:sub(1, 80) .. "..." end
            table.insert(lines, string.format("  %s = %s (%s)", tostring(k), sv, type(v)))
        end
    end

    table.insert(lines, "")
    table.insert(lines, "=== 条件管理器状态 ===")
    if g_ConditionMgr then
        local cfg_count = 0
        if g_ConditionMgr.m_tbCfg then
            for _ in pairs(g_ConditionMgr.m_tbCfg) do cfg_count = cfg_count + 1 end
        end
        table.insert(lines, "  条件配置数: " .. cfg_count)
    else
        table.insert(lines, "  g_ConditionMgr 不存在")
    end

    return table.concat(lines, "\n")
end)
return ok and err or "执行失败: " .. tostring(err)
"""


LUA_COMPLETE_CITY_RANK = r"""
local ok, err = pcall(function()
    local camp = g_camp
    if not camp then
        return "[失败] g_camp 不存在（请先进入游戏场景）"
    end
    local boom = (camp.GetCampBoomModule and camp:GetCampBoomModule()) or camp.boom
    if not boom then
        return "[失败] Boom 模块不存在（GetCampBoomModule / camp.boom 都拿不到）"
    end

    local steps = {}

    -- 最大品阶：优先读游戏配置，兜底 14
    local maxLevel = __BOOM_MAX__
    pcall(function()
        local n = #g_blocksLogicCfg:GetBoomLevelCfg()
        if n and n > 0 then maxLevel = n end
    end)

    local oldBoom = 0
    pcall(function() oldBoom = boom:GetBoom() or 0 end)

    -- 【关键修复】先把“历史最高品阶”归零，强制 UpdateHistoryMaxBoomLevel 重跑 1..max 的解锁循环。
    --   游戏原逻辑：for i = GetHistoryMaxBoom()+1, GetBoom() do UnLockBoomReward(i) end
    --   旧实现直接把 historyMaxBoomLevel 设成 14 -> 循环为空 -> 只改了数字(任务系统条件判定通过)，
    --   但建筑卡/谋士卡/天赋/载具/功能/地块扩张/灾害解锁等奖励全都没执行 -> “只是UI看着解锁”。
    pcall(function() boom:setHistoryMaxBoomLevel(0) end)

    local okSet = pcall(function() boom:setBoom(maxLevel) end)
    if not okSet then
        return "[失败] setBoom 调用失败"
    end
    table.insert(steps, "setBoom(" .. tostring(maxLevel) .. ")")

    -- 【核心】真正执行每一级的奖励解锁
    local okUnlock = pcall(function() boom:UpdateHistoryMaxBoomLevel() end)
    table.insert(steps, okUnlock and "奖励解锁循环OK" or "奖励解锁循环失败")

    -- 通知 / UI 刷新
    pcall(function() boom:BoomLevelChange(oldBoom, maxLevel) end)
    pcall(function() boom:_syncUI(false) end)
    pcall(function()
        g_LHBUIProvider:EmitTo("LBlockProvider", g_LHBUIEvents.S2UI_UpdateBoomConditionState)
    end)

    local newHistory = 0
    pcall(function() newHistory = boom:GetHistoryMaxBoom() or 0 end)
    return string.format("[成功] 城市品阶 %d -> %d，已执行全等级奖励解锁（historyMax=%d，max=%d）：%s",
        oldBoom, maxLevel, newHistory, maxLevel, table.concat(steps, "，"))
end)
if not ok then return "[错误] " .. tostring(err) end
return err
"""


def diagnose_boom():
    """鸿业（城市品阶）系统诊断

    注：当前 GUI 未接入调用（tab_advanced.py 只调用 diagnose_time_system，
    tab_creative.py 只调用 diagnose_unlock_status）。保留供未来扩展或
    通过 execute_lua 直接调用。删除会丢失诊断能力，故保留。
    """
    return execute_lua_safe(LUA_BOOM_DIAGNOSE, timeout=8.0)


def complete_city_rank_conditions():
    """
    提升城市品阶（鸿业）到满级，并真正执行各等级奖励解锁

    实现（走游戏自身流程，而非只改数字）：
        1. historyMaxBoomLevel 归零（否则 UpdateHistoryMaxBoomLevel 的解锁循环为空）
        2. setBoom(maxLevel)
        3. UpdateHistoryMaxBoomLevel() —— 逐级 UnLockBoomReward，真正解锁
           建筑卡/谋士卡/天赋/载具/功能/地块扩张/灾害解锁等
        4. BoomLevelChange + _syncUI + UI 事件，刷新表现层
    """
    log("正在完成所有城市品阶条件...")
    success, result = execute_lua_safe(_boom_lua(LUA_COMPLETE_CITY_RANK), timeout=LUA_TIMEOUT_LONG)
    return _log_result(success, result, "城市品阶条件完成失败")


# ============================================================
# v0.3 新增：城市品阶逐级提升
# ============================================================

LUA_BOOM_LEVEL_UP = (r"""
local ok, err = pcall(function()
""" + _LUA_BOOM_RESOLVE + r"""

    -- 获取当前品阶
    local cur_level = 0
    if boom.GetBoom then   -- [API-FIX] 游戏里是 GetBoom，没有 getBoom
        cur_level = boom:GetBoom() or 0
    end

    local max_level = __BOOM_MAX__  -- 鸿业最高品阶
    if cur_level >= max_level then
        return string.format("[提示] 当前品阶已满级 (%d/%d)，无法继续提升", cur_level, max_level)
    end

    -- 逐级+1
    local new_level = cur_level + 1
    boom:setBoom(new_level)

    -- 验证是否生效
    local after_level = 0
    if boom.GetBoom then   -- [API-FIX] 同上
        after_level = boom:GetBoom() or 0
    end

    if after_level >= new_level then
        return string.format("[成功] 品阶提升 %d → %d（最高 %d）", cur_level, after_level, max_level)
    else
        -- 尝试触发UI刷新
        pcall(function() S2UI_UpdateBoomConditionState() end)
        return string.format("[部分成功] 品阶尝试提升到 %d，当前 %d（UI可能需要刷新）", new_level, after_level)
    end
end)
if not ok then return "[错误] " .. tostring(err) end
return err
""")

LUA_BOOM_GET_CURRENT = (r"""
local ok, err = pcall(function()
""" + _LUA_BOOM_RESOLVE + r"""
    local cur = 0
    if boom.GetBoom then   -- [API-FIX] 游戏里是 GetBoom
        cur = boom:GetBoom() or 0
    end
    return string.format("[成功] 当前品阶: %d / __BOOM_MAX__", cur)
end)
if not ok then return "[错误] " .. tostring(err) end
return err
""")


def boom_level_up():
    """城市品阶逐级提升 +1

    实现：
        执行 LUA_BOOM_LEVEL_UP 脚本，每次调用将繁荣度 +1，
        直到达到满级 14。用户可以一层一层升。
    """
    log("正在提升城市品阶 +1 ...")
    success, result = execute_lua_safe(_boom_lua(LUA_BOOM_LEVEL_UP))
    return _log_result(success, result, "品阶提升失败")


def boom_get_current():
    """获取当前城市品阶"""
    return execute_lua_safe(_boom_lua(LUA_BOOM_GET_CURRENT))


# ============================================================
# v0.3 新增：全地块解锁
# ============================================================

LUA_PLOT_PROBE = r"""
local ok, err = pcall(function()
    local lines = {}
    table.insert(lines, "=== 地块对象探查 ===")

    -- 搜索可能的地块管理器
    local candidates = {
        "g_PlotManager", "g_LandManager", "g_TerrainManager",
        "g_MapManager", "g_BlockManager", "g_ZoneManager",
        "g_CityManager.m_lActiveCity.m_lPlotMgr",
        "g_CityManager.m_lActiveCity.m_lBlockMgr",
        "g_CityManager.m_lActiveCity.m_lLandMgr",
    }

    for _, path in ipairs(candidates) do
        local obj = _G
        -- 逐级访问路径
        for part in string.gmatch(path, "[^%.]+") do
            if type(obj) == "table" then
                obj = obj[part]
            else
                obj = nil
                break
            end
        end
        if obj then
            table.insert(lines, string.format("[找到] %s (type=%s)", path, type(obj)))
            -- 列出方法
            if type(obj) == "table" then
                local methods = {}
                for k, v in pairs(obj) do
                    if type(v) == "function" then
                        table.insert(methods, k)
                    end
                end
                table.sort(methods)
                for _, m in ipairs(methods) do
                    local lm = string.lower(m)
                    if string.find(lm, "unlock") or string.find(lm, "open")
                       or string.find(lm, "add") or string.find(lm, "active")
                       or string.find(lm, "plot") or string.find(lm, "land")
                       or string.find(lm, "block") or string.find(lm, "zone") then
                        table.insert(lines, "  [方法] " .. m)
                    end
                end
            end
        end
    end

    -- 搜索全局变量中包含 plot/land/block 的
    table.insert(lines, "")
    table.insert(lines, "=== 全局变量搜索 ===")
    for k, v in pairs(_G) do
        local lk = string.lower(k)
        if (string.find(lk, "plot") or string.find(lk, "land")
           or string.find(lk, "block") or string.find(lk, "zone")
           or string.find(lk, "terrain")) and type(v) == "table" then
            table.insert(lines, "  " .. k .. " (type=table)")
        end
    end

    table.insert(lines, "")
    table.insert(lines, "=== g_blockMgr 导出 ===")
    if g_blockMgr then pcall(function() __trainer_dump(g_blockMgr, lines) end) end

    return table.concat(lines, "\n")
end)
if not ok then return "[错误] " .. tostring(err) end
return err
"""

LUA_PLOT_UNLOCK_ALL = r"""
local ok, err = pcall(function()
    local mgr = g_blockMgr
    if not mgr then
        return "[失败] g_blockMgr 不存在（请先进入游戏场景）"
    end
    if not block_define or not block_define.STATE then
        return "[失败] 无法取得 block_define.STATE 枚举"
    end
    local STATE = block_define.STATE
    local target = STATE.COMBINED
    if target == nil then
        return "[失败] block_define.STATE.COMBINED 为空"
    end

    local blocks = nil
    pcall(function() blocks = mgr:GetAllBlocks() end)
    if type(blocks) ~= "table" then
        return "[失败] GetAllBlocks 无返回"
    end

    -- 游戏内部“已拥有”的判定就是  m_nState == STATE.COMBINED / STATE.WORKING
    --   （见 LBlockMgr:GetAllOwnedBlocks）。旧实现乱设 m_nState=2 / state / unlocked 等字段，
    --   与游戏枚举不匹配，所以只有 UI 表象变了、内部状态没变。
    local changed, already, skipped = 0, 0, 0
    for id, block in pairs(blocks) do
        if type(block) == "table" and block.SetState and block.GetState then
            local cur = block:GetState()
            if cur == target or cur == STATE.WORKING then
                already = already + 1
            else
                pcall(function() block:SetState(target) end)
                changed = changed + 1
                pcall(function() mgr:UpdateFinishedPeaceBlock(block:GetBlockID()) end)
            end
        else
            skipped = skipped + 1
        end
    end

    pcall(function() g_LHBUIProvider:EmitTo("LBlockProvider", g_LHBUIEvents.S2UI_UpdateBoomConditionState) end)
    pcall(function() if g_camp and g_camp.boom then g_camp.boom:SetUpgradeLock(false) end end)

    return string.format("[成功] 地块解锁（按游戏内部状态 SetState(COMBINED)）：新解锁 %d，原已拥有 %d，跳过 %d",
        changed, already, skipped)
end)
if not ok then return "[错误] " .. tostring(err) end
return err
"""


def probe_plots():
    """地块对象探查（诊断用）"""
    return execute_lua_safe(LUA_PLOT_PROBE, timeout=8.0)


def unlock_all_plots():
    """解锁全地块

    实现：
        对 g_blockMgr:GetAllBlocks() 中每个地块调用 SetState(block_define.STATE.COMBINED)，
        与游戏内部“已拥有”的判定（LBlockMgr:GetAllOwnedBlocks）保持一致；
        并触发 UpdateFinishedPeaceBlock / UI 刷新。
    """
    log("正在解锁全地块...")
    success, result = execute_lua_safe(LUA_PLOT_UNLOCK_ALL, timeout=8.0)
    return _log_result(success, result, "地块解锁失败")


# ============================================================
# v0.3 新增：谋士升满级
# ============================================================

LUA_ADVISOR_PROBE = r"""
local ok, err = pcall(function()
    local lines = {}
    table.insert(lines, "=== 谋士对象探查 ===")

    -- 搜索谋士管理器
    local candidates = {
        -- [API-FIX] 真实：g_LFamousAdviserMgr / g_LAdviserManager（前两行旧名不存在）
        "g_LFamousAdviserMgr", "g_LAdviserManager", "g_LAdviserCardManager",
        "g_CityManager.m_lActiveCity.m_lAdvisorMgr",
        "g_CityManager.m_lActiveCity.m_lAdviserMgr",
        "g_CityManager.m_lActiveCity.m_lMoulinMgr",
    }

    for _, path in ipairs(candidates) do
        local obj = _G
        for part in string.gmatch(path, "[^%.]+") do
            if type(obj) == "table" then
                obj = obj[part]
            else
                obj = nil
                break
            end
        end
        if obj then
            table.insert(lines, string.format("[找到] %s (type=%s)", path, type(obj)))
            if type(obj) == "table" then
                local methods = {}
                for k, v in pairs(obj) do
                    if type(v) == "function" then
                        table.insert(methods, k)
                    end
                end
                table.sort(methods)
                for _, m in ipairs(methods) do
                    table.insert(lines, "  [方法] " .. m)
                end
                -- 检查谋士列表
                for _, listName in ipairs({"tabAdvisors", "advisorList", "tabMoulins", "moulinList", "tabAdvisers"}) do
                    if obj[listName] and type(obj[listName]) == "table" then
                        local count = 0
                        for id, adv in pairs(obj[listName]) do
                            count = count + 1
                            if count <= 3 then
                                table.insert(lines, string.format("  [%s] id=%s", listName, tostring(id)))
                                -- 列出谋士属性
                                if type(adv) == "table" then
                                    for k2, v2 in pairs(adv) do
                                        if type(v2) ~= "function" and type(v2) ~= "table" then
                                            table.insert(lines, string.format("    %s = %s", k2, tostring(v2)))
                                        end
                                    end
                                end
                            end
                        end
                        table.insert(lines, string.format("  %s 总数: %d", listName, count))
                    end
                end
            end
        end
    end

    -- 搜索全局变量
    table.insert(lines, "")
    table.insert(lines, "=== 全局变量搜索 ===")
    for k, v in pairs(_G) do
        local lk = string.lower(k)
        if (string.find(lk, "advisor") or string.find(lk, "adviser")
           or string.find(lk, "moulin")) and type(v) == "table" then
            table.insert(lines, "  " .. k .. " (type=table)")
        end
    end

    table.insert(lines, "")
    table.insert(lines, "=== 谋士管理器导出 ===")
    local mgrs = {g_LAdviserManager, g_LFamousAdviserMgr, g_LOfficeAdviserActionManager, g_LOfficeManager}
    local mnames = {"g_LAdviserManager", "g_LFamousAdviserMgr", "g_LOfficeAdviserActionManager", "g_LOfficeManager"}
    for i, mg in ipairs(mgrs) do
        table.insert(lines, "-- " .. mnames[i] .. " (" .. type(mg) .. ")")
        if mg then pcall(function() __trainer_dump(mg, lines) end) end
    end

    return table.concat(lines, "\n")
end)
if not ok then return "[错误] " .. tostring(err) end
return err
"""

LUA_ADVISOR_MAX_ALL = r"""
local ok, err = pcall(function()
    local lines = {}

    -- 正确全局变量：g_LOfficeManager（交接文档v4.0已验证：谋士/官职管理器）
    local mgr = g_LOfficeManager
    if not mgr then
        -- 备选：搜索全局
        -- [API-FIX] 旧备选名 g_AdvisorManager/g_AdviserManager 不存在；改为真实管理器
        for _, name in ipairs({"g_LOfficeManager", "g_LFamousAdviserMgr", "g_LAdviserManager"}) do
            if _G[name] and type(_G[name]) == "table" then
                mgr = _G[name]
                table.insert(lines, "找到谋士管理器(备选): " .. name)
                break
            end
        end
    else
        table.insert(lines, "找到谋士管理器: g_LOfficeManager")
    end

    if not mgr then
        return "[失败] 未找到谋士管理器（请先进入游戏场景并招募谋士）"
    end

    -- 知识库确认：g_LOfficeManager 通过 GetAllIDLEAdvisers/GetAllBUSYAdvisers/GetAllSABBATICAdvisers 获取谋士
    local advisers = {}
    local seen = {}
    local function collect(list)
        if list and type(list) == "table" then
            for _, adv in pairs(list) do
                if adv and type(adv) == "table" and not seen[adv] then
                    seen[adv] = true
                    advisers[#advisers + 1] = adv
                end
            end
        end
    end

    pcall(function() collect(mgr:GetCampAdviserOfficeAdvisers()) end)
    pcall(function() collect(mgr:GetAllIDLEAdvisers()) end)
    pcall(function() collect(mgr:GetAllBUSYAdvisers()) end)
    pcall(function() collect(mgr:GetAllSABBATICAdvisers()) end)

    if #advisers == 0 then
        return "[失败] 未找到任何谋士（请先招募谋士）\n" .. table.concat(lines, "\n")
    end
    table.insert(lines, string.format("找到 %d 名谋士", #advisers))

    local upgraded = 0
    for _, adv in ipairs(advisers) do
        -- 等级满：加经验后循环升级（知识库确认 AddExp/Upgrade/CanUpgrade/IsMaxLevel）
        pcall(function() adv:AddExp(999999) end)
        for _ = 1, 200 do
            local canUp = false
            pcall(function()
                if adv.CanUpgrade and adv.IsMaxLevel then
                    canUp = adv:CanUpgrade() and not adv:IsMaxLevel()
                elseif adv.CanUpgrade then
                    canUp = adv:CanUpgrade()
                end
            end)
            if canUp then
                local okUp = pcall(function() adv:Upgrade() end)
                if not okUp then break end
            else
                break
            end
        end
        -- 薪资归零（知识库确认 SetSalary）
        pcall(function() adv:SetSalary(0) end)
        -- 忠诚度/满意度满（薪资满意度拉满，对应"忠诚度"）
        pcall(function() adv:SetSalaryToSatisfy() end)
        -- 能力满：训练各维度能力（知识库确认 AddTrainAbility）
        for d = 1, 8 do
            pcall(function() adv:AddTrainAbility(d, 999999) end)
        end
        -- 兜底字段设置
        for _, f in ipairs({"loyalty", "m_nLoyalty", "m_loyalty"}) do
            pcall(function() adv[f] = 100 end)
        end
        for _, f in ipairs({"ability", "m_nAbility", "m_ability"}) do
            pcall(function() adv[f] = 999 end)
        end
        upgraded = upgraded + 1
    end

    return string.format("[成功] 已升级 %d 名谋士（等级/能力满，薪资=0，忠诚度满）\n%s", upgraded, table.concat(lines, "\n"))
end)
if not ok then return "[错误] " .. tostring(err) end
return err
"""


def probe_advisors():
    """谋士对象探查（诊断用）"""
    return execute_lua_safe(LUA_ADVISOR_PROBE, timeout=8.0)


def max_all_advisors():
    """谋士升满级（忠诚度满、能力满、薪资0）

    实现：
        执行 LUA_ADVISOR_MAX_ALL 脚本，自动搜索谋士管理器，
        遍历所有谋士设置忠诚度=100、能力=999、薪资=0。
    """
    log("正在升级全部谋士...")
    success, result = execute_lua_safe(LUA_ADVISOR_MAX_ALL, timeout=8.0)
    return _log_result(success, result, "谋士升级失败")


# ============================================================
# v0.3 新增：Steam 全成就解锁
# ============================================================

LUA_STEAM_ACHIEVEMENT_PROBE = r"""
local ok, err = pcall(function()
    local lines = {}
    table.insert(lines, "=== Steam成就对象探查 ===")

    -- 搜索成就管理器
    for _, name in ipairs({"g_AchievementManager", "g_SteamManager",
                          "g_SteamAchievementManager", "g_AchManager",
                          "g_GameAchievementManager"}) do
        if _G[name] and type(_G[name]) == "table" then
            table.insert(lines, string.format("[找到] %s", name))
            local methods = {}
            for k, v in pairs(_G[name]) do
                if type(v) == "function" then
                    table.insert(methods, k)
                end
            end
            table.sort(methods)
            for _, m in ipairs(methods) do
                table.insert(lines, "  [方法] " .. m)
            end
        end
    end

    -- 搜索全局变量
    table.insert(lines, "")
    table.insert(lines, "=== 全局变量搜索 ===")
    for k, v in pairs(_G) do
        local lk = string.lower(k)
        if (string.find(lk, "ach") or string.find(lk, "steam")) and type(v) == "table" then
            table.insert(lines, "  " .. k .. " (type=table)")
        end
    end

    -- 检查 steam_api64.dll 是否被替换
    table.insert(lines, "")
    table.insert(lines, "=== Steam API 检查 ===")
    if g_SteamAPI then
        table.insert(lines, "g_SteamAPI 存在")
        if type(g_SteamAPI) == "table" then
            for k, v in pairs(g_SteamAPI) do
                if type(v) == "function" then
                    table.insert(lines, "  [方法] " .. k)
                end
            end
        end
    else
        table.insert(lines, "g_SteamAPI 不存在")
    end

    table.insert(lines, "")
    table.insert(lines, "=== 成就管理器导出 ===")
    if g_LAchievementMgr then pcall(function() __trainer_dump(g_LAchievementMgr, lines) end) end
    if g_LAchieveCardManager then pcall(function() __trainer_dump(g_LAchieveCardManager, lines) end) end
    table.insert(lines, "")
    table.insert(lines, "=== 成就清单（1..300）===")
    local mgr2 = g_LAchievementMgr
    local cm2 = g_LAchieveCardManager
    if mgr2 and cm2 and cm2.GetGDPLById then
        local unlocked, locked = 0, {}
        for achId = 1, 300 do
            local okG, bRet, g, d, p, l = pcall(function() return cm2:GetGDPLById(achId) end)
            if okG and bRet then
                if type(mgr2.unlockState) == "table" and mgr2.unlockState[achId] then
                    unlocked = unlocked + 1
                else
                    locked[#locked + 1] = tostring(achId) .. "(gdp=" .. tostring(g)
                        .. "_" .. tostring(d) .. "_" .. tostring(p) .. "_" .. tostring(l) .. ")"
                end
            end
        end
        table.insert(lines, "已解锁 = " .. tostring(unlocked) .. "，未解锁 = " .. tostring(#locked))
        table.insert(lines, "未解锁列表: " .. table.concat(locked, ", "))
    else
        table.insert(lines, "（GetGDPLById 不可用，无法枚举）")
    end

    -- 额外：成就 config / 计数器（很可能含 achId 与 Steam 映射）
    if mgr2 then
        table.insert(lines, "UnlockAchievement 绑定 = " .. tostring(type(mgr2.UnlockAchievement)) .. "，UnlockAchievementBase = " .. tostring(type(mgr2.UnlockAchievementBase)))
        table.insert(lines, "unlockAchNumber = " .. tostring(mgr2.unlockAchNumber) .. "，direct = " .. tostring(mgr2.direct))
        if type(mgr2.config) == "table" then
            local keys = {}
            for kk in pairs(mgr2.config) do keys[#keys + 1] = kk end
            table.sort(keys, function(a, b) return tostring(a) < tostring(b) end)
            table.insert(lines, "=== 成就 config（共 " .. tostring(#keys) .. " 条，前 100）===")
            for idx2, kk in ipairs(keys) do
                if idx2 <= 100 then
                    table.insert(lines, "  " .. tostring(kk) .. " = " .. tostring(mgr2.config[kk]))
                end
            end
            if keys[1] then
                table.insert(lines, "=== config[" .. tostring(keys[1]) .. "] 内容 ===")
                pcall(function() __trainer_dump(mgr2.config[keys[1]], lines) end)
            end
            if keys[#keys] and #keys > 1 then
                table.insert(lines, "=== config[" .. tostring(keys[#keys]) .. "] 内容 ===")
                pcall(function() __trainer_dump(mgr2.config[keys[#keys]], lines) end)
            end
        end
    end

    return table.concat(lines, "\n")
end)
if not ok then return "[错误] " .. tostring(err) end
return err
"""

LUA_UNLOCK_BLOCK_CHALLENGE_ACH = r"""
local ok, err = pcall(function()
    local mgr = g_LAchievementMgr
    if not mgr then return "[失败] 未找到 g_LAchievementMgr（请先进入游戏场景）" end
    local xg = g_LXGAgentManager
    if not xg or type(xg.UnlockAchievement) ~= "function" then
        return "[失败] g_LXGAgentManager:UnlockAchievement 不可用（Steam/XGSDK 未就绪？）"
    end
    local D = LAchDefine
    if not D then return "[失败] LAchDefine 不存在（请先进入游戏场景）" end

    -- 月落峡 = 地块 9；100=通关，101=超甲（BLOCK_BESTSCORE），102=三金牌（BLOCK_SPEED，3 项评级全金）
    local BLOCK_ID = 9
    local targets = {
        { id = D.BLOCK_FINISHED_ACHIEVEMENT and D.BLOCK_FINISHED_ACHIEVEMENT[BLOCK_ID], name = "月落峡通关" },
        { id = D.BLOCK_BESTSCORE_ACH and D.BLOCK_BESTSCORE_ACH[BLOCK_ID],               name = "月落峡超甲通关" },
        { id = D.BLOCK_SPEED_ACH and D.BLOCK_SPEED_ACH[BLOCK_ID],                       name = "月落峡三金牌通关" },
    }

    if not mgr.unlockState then mgr.unlockState = {} end
    local lines, pushed = {}, 0
    for _, t in ipairs(targets) do
        if t.id then
            local okX, ret = pcall(function() return xg:UnlockAchievement(t.id) end)
            if okX and ret then
                pushed = pushed + 1
                mgr.unlockState[t.id] = true
                lines[#lines + 1] = string.format("%s(ID %s)=推送成功", t.name, tostring(t.id))
            else
                lines[#lines + 1] = string.format("%s(ID %s)=%s", t.name, tostring(t.id),
                    okX and "平台返回false" or ("异常:" .. tostring(ret)))
            end
        else
            lines[#lines + 1] = t.name .. "=未找到成就ID"
        end
    end

    -- 顺带走一遍游戏自身的挑战成就入口（BestScore 无条件；BestSpeed 需 3 项全金；BlockMerged 需已合并）
    pcall(function() mgr:BestScore(BLOCK_ID) end)
    pcall(function() mgr:BlockMerged(BLOCK_ID) end)
    pcall(function() mgr:BestSpeed(BLOCK_ID) end)
    pcall(function() mgr:UnLockCallBack() end)

    return string.format("[成功] 地块%d 挑战成就：推送 %d/%d —— %s",
        BLOCK_ID, pushed, #targets, table.concat(lines, "；"))
end)
if not ok then return "[错误] " .. tostring(err) end
return err
"""

LUA_STEAM_ACHIEVEMENT_UNLOCK_ALL = r"""
local ok, err = pcall(function()
    local mgr = g_LAchievementMgr
    if not mgr then return "[失败] 未找到 g_LAchievementMgr（请先进入游戏场景）" end
    local cm = g_LAchieveCardManager
    local xg = g_LXGAgentManager
    if not xg or type(xg.UnlockAchievement) ~= "function" then
        return "[失败] g_LXGAgentManager:UnlockAchievement 不可用（Steam/XGSDK 未就绪？）"
    end
    if not mgr.unlockState then mgr.unlockState = {} end

    local MAXID = __MAX__
    if MAXID < 200 then MAXID = 200 end

    -- 收集“权威”成就ID：
    --   1) mgr.config（achieve.txt 加载的权威表，item[1]=AchId）
    --   2) 地块挑战表（含没有卡片的 100/101/102）
    --   3) 成就卡映射兜底
    local ids, seen = {}, {}
    local function add(id)
        if type(id) == "number" and not seen[id] then
            seen[id] = true
            ids[#ids + 1] = id
        end
    end
    if type(mgr.config) == "table" then
        for _, item in ipairs(mgr.config) do
            if type(item) == "table" then add(item[1]) end
        end
    end
    local D = LAchDefine
    if D then
        for _, m in ipairs({D.BLOCK_FINISHED_ACHIEVEMENT, D.BLOCK_BESTSCORE_ACH, D.BLOCK_SPEED_ACH}) do
            if type(m) == "table" then
                for _, id in pairs(m) do add(id) end
            end
        end
        add(D.BLOCK_ALL_FINISHED_ACHID)
        add(D.ALL_ACH_ACH)
    end
    for id = 1, MAXID do
        local okG, bRet = pcall(function() return cm:GetGDPLById(id) end)
        if okG and bRet then add(id) end
    end

    -- 逐条：解锁成就卡 + 直接推送平台（用返回布尔判定是否真被接受）
    local pushed, newCard, failed = 0, 0, {}
    for _, id in ipairs(ids) do
        local okG, bRet, g, d, p, l = pcall(function() return cm:GetGDPLById(id) end)
        if okG and bRet then
            pcall(function() cm:UnlockAchieveCard(g, d, p, l) end)
            newCard = newCard + 1
        end
        local okX, ret = pcall(function() return xg:UnlockAchievement(id) end)
        if okX and ret then
            pushed = pushed + 1
            if not mgr.unlockState[id] then
                mgr.unlockState[id] = true
                pcall(function() mgr:UnLockCallBack() end)
            end
        elseif #failed < 10 then
            failed[#failed + 1] = tostring(id) .. (okX and "" or "!")
        end
    end

    local msg = string.format("[成功] 成就ID %d 个，推送平台 %d 次，图鉴 %d 个", #ids, pushed, newCard)
    if #failed > 0 then msg = msg .. "；平台未接受: " .. table.concat(failed, ",") end
    return msg
end)
if not ok then return "[错误] " .. tostring(err) end
return err
"""


def probe_steam_achievements():
    """Steam成就对象探查（诊断用）"""
    return execute_lua_safe(LUA_STEAM_ACHIEVEMENT_PROBE, timeout=8.0)


def unlock_all_steam_achievements():
    """解锁全部 Steam 成就

    实现：
        执行 LUA_STEAM_ACHIEVEMENT_UNLOCK_ALL 脚本，
        自动搜索成就管理器并尝试解锁所有成就。
    """
    log("正在解锁全部 Steam 成就...")
    code = LUA_STEAM_ACHIEVEMENT_UNLOCK_ALL.replace("__MAX__", str(ACHIEVEMENT_ID_SCAN_LIMIT))
    success, result = execute_lua_safe(code, timeout=40.0)
    return _log_result(success, result, "成就解锁失败")

def unlock_block_challenge_achievements():
    """解锁地块挑战成就（月落峡：通关 / 超甲 / 三金牌）

    月落峡 = 地块 9；这三条没有成就卡映射，旧的“按卡片ID遍历”方式会漏掉，
    所以单独走 g_LXGAgentManager:UnlockAchievement 直接推送。
    """
    log("正在解锁月落峡挑战成就（超甲 / 三金牌）...")
    success, result = execute_lua_safe(LUA_UNLOCK_BLOCK_CHALLENGE_ACH, timeout=20.0)
    return _log_result(success, result, "挑战成就解锁失败")


# ============================================================
# v0.3 新增：恢复原版功能
# ============================================================

LUA_RESTORE_TIME_SPEED = (r"""
local ok, err = pcall(function()
    local gw = g_GameWorld
    if not gw then return "[失败] g_GameWorld 不存在（请先进入游戏场景）" end
""" + _LUA_TIME_BASE_RESOLVE + r"""

    if not base or base <= 0 then
        return "[失败] 无法确定原始速度，未改动（当前 TICK_DELTA_TIMES=" .. tostring(gw.TICK_DELTA_TIMES) .. "）"
    end
    local before = tostring(gw.TICK_DELTA_TIMES)
    gw.TICK_DELTA_TIMES = base
    g_trainer_base_delta = base
    g_trainer_last_delta = base
    return "[成功] 已恢复原速（" .. before .. " -> " .. tostring(base) .. "）"
end)
if not ok then return "[错误] " .. tostring(err) end
return err
""")

LUA_TIME_SPEED_STATUS = r"""
local ok, err = pcall(function()
    local gw = g_GameWorld
    local lines = {"=== 速度状态 ==="}
    local cur = 0
    if gw then
        cur = tonumber(gw.TICK_DELTA_TIMES) or 0
        table.insert(lines, "当前 TICK_DELTA_TIMES = " .. tostring(gw.TICK_DELTA_TIMES))
    else
        table.insert(lines, "g_GameWorld 不存在")
    end
    local d = _G.define
    local authorBase = nil
    if d and d.DAY_TIME_REAL and d.DAY_TICK_COUNT and d.DAY_TICK_COUNT ~= 0 then
        authorBase = d.DAY_TIME_REAL / d.DAY_TICK_COUNT
        table.insert(lines, "游戏权威原始值 = " .. tostring(authorBase) .. "（DAY_TIME_REAL=" .. tostring(d.DAY_TIME_REAL) .. " / DAY_TICK_COUNT=" .. tostring(d.DAY_TICK_COUNT) .. "）")
    else
        table.insert(lines, "游戏权威原始值 = 不可得（define 缺失）")
    end
    table.insert(lines, "记录基准 g_trainer_base_delta = " .. tostring(g_trainer_base_delta))
    table.insert(lines, "上次写入 g_trainer_last_delta = " .. tostring(g_trainer_last_delta))
    local base = authorBase or tonumber(g_trainer_base_delta) or 0
    if base > 0 and cur > 0 then
        table.insert(lines, "推导倍率 = " .. tostring(base / cur) .. "x")
    end
    if type(g_trainer_base_delta) == "number" and authorBase and math.abs(g_trainer_base_delta - authorBase) > 0.001 then
        table.insert(lines, "⚠ 记录的基准与游戏权威值不一致，可能已被错误基准污染 → 请点「↩ 恢复速度」")
    end
    if g_Time and g_Time.m_tb then
        table.insert(lines, "m_nTimeSpeed = " .. tostring(g_Time.m_tb.m_nTimeSpeed))
    end
    return table.concat(lines, "\n")
end)
if not ok then return "[错误] " .. tostring(err) end
return err
"""

LUA_RESTORE_SEASON = r"""
local ok, err = pcall(function()
    -- 移除季节 hook（恢复原始 GetCurSeason/GetSeason）
    if _G._orig_GetCurSeason then
        GetCurSeason = _G._orig_GetCurSeason
        _G._orig_GetCurSeason = nil
    end
    if _G._orig_GetSeason then
        GetSeason = _G._orig_GetSeason
        _G._orig_GetSeason = nil
    end
    return "[成功] 季节已恢复原版（hook 已移除）"
end)
if not ok then return "[错误] " .. tostring(err) end
return err
"""

LUA_RESTORE_GAME_SPEED = r"""
local ok, err = pcall(function()
    -- 恢复游戏逻辑运行（如果之前暂停了）
    if g_Game and g_Game.LogicTickResume then
        g_Game:LogicTickResume()
        return "[成功] 游戏已恢复运行（LogicTick 已恢复）"
    end
    return "[失败] g_Game 不存在或 LogicTickResume 不可用"
end)
if not ok then return "[错误] " .. tostring(err) end
return err
"""


def get_time_speed_status():
    """时间速度状态（基准/当前/倍率）"""
    return execute_lua_safe(LUA_TIME_SPEED_STATUS)


def restore_time_speed():
    """恢复时间速度为 1x"""
    log("正在恢复时间速度...")
    success, result = execute_lua_safe(LUA_RESTORE_TIME_SPEED)
    return _log_result(success, result, "恢复时间速度失败")


def restore_season():
    """恢复季节为原版（移除 hook）"""
    log("正在恢复季节...")
    success, result = execute_lua_safe(LUA_RESTORE_SEASON)
    return _log_result(success, result, "恢复季节失败")


def restore_game_speed():
    """恢复游戏运行（取消暂停）"""
    log("正在恢复游戏运行...")
    success, result = execute_lua_safe(LUA_RESTORE_GAME_SPEED)
    return _log_result(success, result, "恢复游戏运行失败")


# ============================================================
# 时间流速实测（判断时间倍速是否真的生效）
# ============================================================
# 游戏机制（源码 time_define.lua / LTimeManager.lua / game_world.lua）：
#   SECONDS_PER_DAY = define.DAY_TICK_COUNT；DAY_TIME_REAL = 原版「一游戏日 = 多少实时秒」
#   LTimeManager:Tick() 使 m_nCurTime += 1 * m_nTimeSpeed（每逻辑 Tick 一次）
#   逻辑 Tick 触发周期 = g_GameWorld.TICK_DELTA_TIMES
#   -> 原版：1 游戏日 = SECONDS_PER_DAY * TICK_DELTA_TIMES = DAY_TIME_REAL 实时秒
#   本函数用「两次读 m_nCurTime 的差值 / 实时时间差」直接测当前实际倍率，不依赖任何假设。

LUA_TIME_MEASURE_SAMPLE = r"""
local ok, err = pcall(function()
    local tm = g_Time
    if not tm then return "[失败] g_Time 不存在（请先进入游戏场景）" end
    local cur = nil
    if tm.GetCurTime then cur = tm:GetCurTime() end
    if cur == nil and tm.m_tb then cur = tm.m_tb.m_nCurTime end
    if cur == nil then return "[失败] 无法读取 m_nCurTime" end
    local d = _G.define
    local secPerDay = nil
    if g_TimeDefine then secPerDay = g_TimeDefine.SECONDS_PER_DAY end
    if secPerDay == nil and d then secPerDay = d.DAY_TICK_COUNT end
    local dayReal = d and d.DAY_TIME_REAL or nil
    local dayTick = d and d.DAY_TICK_COUNT or nil
    return string.format("cur=%.6f;secPerDay=%s;dayReal=%s;dayTick=%s",
        cur, tostring(secPerDay), tostring(dayReal), tostring(dayTick))
end)
if not ok then return "[错误] " .. tostring(err) end
return err
"""


def measure_time_speed(interval=1.0, samples=5):
    """实测游戏时间流速（阻塞约 (samples-1)*interval 秒，须在异步线程调用）。

    返回 (success, 多行文本)。多次采样 m_nCurTime 后做线性回归求斜率，
    避开「两点取样」因整数步进（每逻辑 Tick 整数 +1）造成的量化误差。
    """
    import time as _time

    def parse(s):
        d = {}
        for kv in s.split(";"):
            if "=" in kv:
                k, v = kv.split("=", 1)
                d[k.strip()] = v.strip()
        return d

    pts = []
    for i in range(max(2, samples)):
        ok, r = execute_lua_safe(LUA_TIME_MEASURE_SAMPLE, timeout=LUA_TIMEOUT)
        now = _time.monotonic()
        if not ok or not isinstance(r, str) or not r.startswith("cur="):
            if not pts:
                return False, f"[失败] 采样失败：{r}"
            break
        d = parse(r)
        try:
            pts.append((now, float(d["cur"]), d))
        except Exception:
            if not pts:
                return False, f"[失败] 解析采样值失败：{r}"
            break
        if i < samples - 1:
            _time.sleep(interval)

    if len(pts) < 2:
        return False, "[失败] 有效采样点不足"

    n = len(pts)
    mt = sum(p[0] for p in pts) / n
    mc = sum(p[1] for p in pts) / n
    num = sum((p[0] - mt) * (p[1] - mc) for p in pts)
    den = sum((p[0] - mt) ** 2 for p in pts)
    if den <= 0:
        return False, "[失败] 采样时间窗口异常"
    rate = num / den                              # 回归斜率：模拟秒 / 实时秒
    ds = pts[-1][1] - pts[0][1]
    dt = pts[-1][0] - pts[0][0]

    d2 = pts[-1][2]

    def fnum(k):
        try:
            return float(d2.get(k))
        except Exception:
            return None

    sec_per_day = fnum("secPerDay")
    day_real = fnum("dayReal")
    day_tick = fnum("dayTick")

    lines = ["=== 时间流速实测（多点回归）==="]
    lines.append(f"采样 {n} 点，窗口 {dt:.2f} 实时秒；模拟时间前进 {ds:.2f} 秒")
    lines.append(f"实测流速 {rate:.3f} 模拟秒 / 实时秒（回归斜率）")
    if sec_per_day and rate > 0:
        real_per_day = sec_per_day / rate
        lines.append(f"实测 1 游戏日 ≈ {real_per_day:.1f} 实时秒")
    if day_real and sec_per_day and rate > 0.0001:
        real_per_day = sec_per_day / rate
        lines.append(f"原版 1 游戏日 = {day_real:.1f} 实时秒 -> 实测等效倍率 ≈ {day_real / real_per_day:.2f}x")
    if rate <= 0.0001:
        lines.append("当前几乎静止（游戏暂停 / 未进入场景 / 窗口未激活？）")
    lines.append(f"游戏常量：SECONDS_PER_DAY={sec_per_day} DAY_TIME_REAL={day_real} DAY_TICK_COUNT={day_tick}")
    return True, "\n".join(lines)


# ============================================================
# 城市品阶：逐级晋升（含解锁流程）
# ============================================================
# 源码事实（camp_boom.lua）：
#   setBoom(level)  只改数字；真正的「升级奖励/解锁」在
#   UI2S_BoomUpgradeCallback(level)：按该级 Rewards 解锁 buildingCard / adviserCard /
#   talent / vehicleCard / unlock(功能) / customFunc(AdviserSlot/Council)，并触发剧情(DemoStory 等)；
#   BoomLevelChange(old,new) 派发 BOOM_LEVEL_CHANED（工作坊/谋士/风水/声望监听）。
#   -> 旧的“品阶+1”只调 setBoom，故解锁项全被跳过。

LUA_BOOM_UPGRADE_STEP = (r"""
local ok, err = pcall(function()
""" + _LUA_BOOM_RESOLVE + r"""
    local function step(target)
    local cur = 0
    if boom.GetBoom then cur = boom:GetBoom() or 0 end

    target = target or 0              -- 0 = 只升一级
    local maxLevel = 14
    if block_define and block_define.CITY_MAX_LEVEL then maxLevel = block_define.CITY_MAX_LEVEL end
    if g_blocksLogicCfg and g_blocksLogicCfg.GetBoomLevelCfg then
        local n = 0
        for _ in pairs(g_blocksLogicCfg:GetBoomLevelCfg() or {}) do n = n + 1 end
        if n > 0 then maxLevel = math.min(maxLevel, n) end
    end
    if target <= 0 then target = cur + 1 end
    if target > maxLevel then target = maxLevel end
    if target <= cur then
        return string.format("[提示] 当前品阶 %d 已达目标 %d（上限 %d），无需晋升", cur, target, maxLevel)
    end

    local lines = {}
    local totalRewards = 0
    local failItems = 0
    for lv = cur + 1, target do
        boom:setBoom(lv)
        pcall(function() boom:BoomLevelChange(lv - 1, lv) end)   -- 派发品阶变更事件

        local cnt = 0
        if g_blocksLogicCfg and g_blocksLogicCfg.GetBoomLevelCfgByBoomLevel then
            local okc, cfg = pcall(function() return g_blocksLogicCfg:GetBoomLevelCfgByBoomLevel(lv) end)
            if okc and type(cfg) == "table" and type(cfg.Rewards) == "table" then cnt = #cfg.Rewards end
        end
        -- 关键：走游戏自身的升级奖励流程
        local okU, eU = pcall(function() boom:UI2S_BoomUpgradeCallback(lv) end)
        if not okU then
            failItems = failItems + 1
            table.insert(lines, string.format("  Lv%d 奖励流程异常：%s", lv, tostring(eU)))
        end
        pcall(function() boom:UpdateHistoryMaxBoomLevel() end)
        totalRewards = totalRewards + cnt
        table.insert(lines, string.format("  Lv%d 晋升完成（该级解锁项 %d）", lv, cnt))
    end

    pcall(function() boom:UpdateBoom() end)
    pcall(function() boom:_syncUI() end)

    local tail = ""
    if failItems > 0 then tail = string.format("，其中 %d 级奖励流程报错（见下方明细）", failItems) end
    return string.format("[成功] 城市品阶 %d → %d（逐级晋升，含解锁，共处理奖励 %d 项%s）\n%s",
        cur, target, totalRewards, tail, table.concat(lines, "\n"))
    end
    _G.g_trainer_boom_step = step
    return step(__TARGET__)
end)
if not ok then return "[错误] " .. tostring(err) end
return err
""")


def boom_upgrade_step(target=0):
    """逐级晋升城市品阶（含解锁流程）

    target=0 表示只升一级；否则升到 target（上限取 block_define.CITY_MAX_LEVEL）。
    每级都会调用 UI2S_BoomUpgradeCallback 发放该级解锁项（建筑卡/谋士/天赋/载具/功能/剧情）。
    """
    log("正在逐级晋升城市品阶（含解锁流程）...")
    from .input_validator import clamp_int
    if target != 0:
        target = clamp_int(target, 1, 14)
    code = _boom_lua(LUA_BOOM_UPGRADE_STEP).replace("__TARGET__", str(int(target)))
    success, result = execute_lua_retry(code, timeout=30.0, attempts=2, tag="品阶晋升")
    return _log_result(success, result, "品阶晋升失败")


def boom_upgrade_to_max():
    """逐级晋升到顶级（含解锁）"""
    return boom_upgrade_step(9999)


# ============================================================
# 任务（激活 / 完成）
# ============================================================
# 源码事实（task_mgr.lua）：任务按 GDPL 分桶 tbUnStartTasks / tbCurTasks / tbReceivedTasks / tbFinishedTasks；
#   UnlockPrecondition(G,D,P,L) 把「未开始」激活为「进行中」；
#   FinishAllTask() 逐个置 FINISHED + RecieveReward + OnFinished。
#   注意：task_mgr 并不监听 BOOM_LEVEL_CHANED（品阶变更不会自动解锁任务）。

LUA_TASK_PROBE = r"""
local ok, err = pcall(function()
    local lines = {"=== 任务状态 ==="}
    local tm = g_LTaskManager
    if not tm then
        table.insert(lines, "[失败] g_LTaskManager 不存在（请先进入游戏场景）")
        return table.concat(lines, "\n")
    end
    local function cnt(t)
        local c = 0
        if type(t) == "table" then for _ in pairs(t) do c = c + 1 end end
        return c
    end
    table.insert(lines, string.format("未开始=%d 进行中=%d 已接=%d 已完成=%d",
        cnt(tm.tbUnStartTasks), cnt(tm.tbCurTasks), cnt(tm.tbReceivedTasks), cnt(tm.tbFinishedTasks)))
    local okA, all = pcall(function() return tm:GetAllTasks() end)
    local total = 0
    if okA and type(all) == "table" then for _ in pairs(all) do total = total + 1 end end
    table.insert(lines, "任务总数 = " .. tostring(total))
    table.insert(lines, "方法：FinishAllTask=" .. tostring(tm.FinishAllTask)
        .. " / UnlockPrecondition=" .. tostring(tm.UnlockPrecondition)
        .. " / FinishTaskByGDPL=" .. tostring(tm.FinishTaskByGDPL))
    if okA and type(all) == "table" then
        local shown = 0
        for _, task in pairs(all) do
            if shown >= 30 then break end
            local okn, nm = pcall(function() return task.tabMateData and task.tabMateData.Name end)
            local okS, st = pcall(function() return task:GetTaskStatus() end)
            table.insert(lines, string.format("  %s | 状态=%s", tostring(okn and nm or "?"), tostring(okS and st or "?")))
            shown = shown + 1
        end
    end
    return table.concat(lines, "\n")
end)
if not ok then return "[错误] " .. tostring(err) end
return err
"""

LUA_TASK_UNLOCK_ALL = r"""
local ok, err = pcall(function()
    local tm = g_LTaskManager
    if not tm then return "[失败] g_LTaskManager 不存在（请先进入游戏场景）" end
    if not tm.UnlockPrecondition then return "[失败] LTaskManager:UnlockPrecondition 不存在" end
    local all = tm:GetAllTasks() or {}
    local n, fail = 0, 0
    for _, task in pairs(all) do
        local okG, G, D, P, L = pcall(function() return task:GetGDPL() end)
        if okG and G then
            local okU = pcall(function() tm:UnlockPrecondition(G, D, P, L) end)
            if okU then n = n + 1 else fail = fail + 1 end
        else
            fail = fail + 1
        end
    end
    local function cnt(t)
        local c = 0
        if type(t) == "table" then for _ in pairs(t) do c = c + 1 end end
        return c
    end
    return string.format("[成功] 已激活 %d 个任务（失败 %d）；现在 未开始=%d 进行中=%d",
        n, fail, cnt(tm.tbUnStartTasks), cnt(tm.tbCurTasks))
end)
if not ok then return "[错误] " .. tostring(err) end
return err
"""

LUA_TASK_FINISH_ALL = r"""
local ok, err = pcall(function()
    local tm = g_LTaskManager
    if not tm then return "[失败] g_LTaskManager 不存在（请先进入游戏场景）" end
    if not tm.FinishAllTask then return "[失败] LTaskManager:FinishAllTask 不存在" end
    tm:FinishAllTask()
    local function cnt(t)
        local c = 0
        if type(t) == "table" then for _ in pairs(t) do c = c + 1 end end
        return c
    end
    return string.format("[成功] 已调用 FinishAllTask；现在 已完成=%d 进行中=%d 未开始=%d",
        cnt(tm.tbFinishedTasks), cnt(tm.tbCurTasks), cnt(tm.tbUnStartTasks))
end)
if not ok then return "[错误] " .. tostring(err) end
return err
"""


LUA_TASK_DATA_UNLOCK = r"""
-- 【直接改数据解锁任务】不依赖 LTaskManager:UnlockPrecondition 的内部流程（它依赖 GetTaskByGDPL、
-- NPC 建筑 KMSC 等一堆前置）——直接把任务对象的数据改成「条件已满足」的样子：
--   依据源码 task.lua:254 LTask:CheckPreConditions：
--       第一句就是 `if self.unlockPre then retBool = true; break; end`  ← 游戏自己的 GM 短路分支
--   所以把 unlockPre 写成 true，游戏自己就会认定「前置触发条件已满足」。
--   status：1=未激活 2=激活中 3=待确认 4=已完成（task_define.lua LTaskDefine.STATUS）
--   分桶：tbUnStartTasks / tbCurTasks / tbReceivedTasks / tbFinishedTasks（键 = GDPL 字符串）
local function _unlock()
    local tm = g_LTaskManager
    if not tm then return "[失败] g_LTaskManager 不存在（请先进入游戏场景）" end
    local TD  = _G.TaskDefine or _G.g_LTaskDefine
    local ACT = (TD and TD.STATUS and TD.STATUS.ACTIVATED) or 2
    local FIN = (TD and TD.STATUS and TD.STATUS.FINISHED) or 4
    local passedDay = nil
    if g_camp and g_camp.GetPassedDay then
        local okD, d = pcall(function() return g_camp:GetPassedDay() end)
        if okD then passedDay = d end
    end
    tm.tbUnStartTasks  = tm.tbUnStartTasks  or {}
    tm.tbCurTasks      = tm.tbCurTasks      or {}
    tm.tbReceivedTasks = tm.tbReceivedTasks or {}
    tm.tbFinishedTasks = tm.tbFinishedTasks or {}
    tm.m_tTaskConfig   = tm.m_tTaskConfig   or {}

    local all = tm:GetAllTasks() or {}
    local n, done = 0, 0
    for key, task in pairs(all) do
        local okS, st = pcall(function() return task:GetTaskStatus() end)
        st = (okS and st) or 1
        if st == FIN or tm.tbFinishedTasks[key] then
            done = done + 1                     -- 已完成的保持不动
        else
            task.unlockPre = true               -- ★ 直接改数据：判定前置已满足
            pcall(function() task:SetTaskUnlockPre(true) end)
            task.status = ACT                   -- ★ 直接改数据：激活中
            pcall(function() task:SetTaskStatus(ACT) end)
            if passedDay ~= nil and task.timeLog == nil then task.timeLog = passedDay end
            tm.tbUnStartTasks[key]  = nil
            tm.tbReceivedTasks[key] = nil
            tm.tbCurTasks[key]      = task
            tm.m_tTaskConfig[key]   = task
            pcall(function() task:SetOtherBuildingState(1) end)
            n = n + 1
        end
    end
    pcall(function() tm:_syncUI() end)
    local function cnt(x)
        local c = 0
        if type(x) == "table" then for _ in pairs(x) do c = c + 1 end end
        return c
    end
    return string.format(
        "[成功] 已直接改数据解锁 %d 个任务（原本已完成 %d 个）；现在 未开始=%d 进行中=%d 已接=%d 已完成=%d",
        n, done, cnt(tm.tbUnStartTasks), cnt(tm.tbCurTasks),
        cnt(tm.tbReceivedTasks), cnt(tm.tbFinishedTasks))
end
_G.g_trainer_task_unlock = _unlock
local ok, ret = pcall(_unlock)
if not ok then return "[错误] " .. tostring(ret) end
return ret
"""

LUA_TASK_DATA_FINISH = r"""
-- 【直接改数据完成任务】status=4(FINISHED) + isNextTaskFinished=true + 移入 tbFinishedTasks，
-- 并按任务配置发放奖励（建筑卡/谋士卡/资源/天赋点）。
-- 依据源码：task.lua:480 LTask:CheckPreviousTask 读的是「前置任务的 status」，
-- 所以把任务真实置为 FINISHED 后，后续任务的前置链判定自然通过（= 解锁后续）。
local function _finish()
    local tm = g_LTaskManager
    if not tm then return "[失败] g_LTaskManager 不存在（请先进入游戏场景）" end
    local TD  = _G.TaskDefine or _G.g_LTaskDefine
    local FIN = (TD and TD.STATUS and TD.STATUS.FINISHED) or 4
    tm.tbUnStartTasks  = tm.tbUnStartTasks  or {}
    tm.tbCurTasks      = tm.tbCurTasks      or {}
    tm.tbReceivedTasks = tm.tbReceivedTasks or {}
    tm.tbFinishedTasks = tm.tbFinishedTasks or {}

    local all = tm:GetAllTasks() or {}
    local n, skip, rw, rwFail = 0, 0, 0, 0
    for key, task in pairs(all) do
        local okS, st = pcall(function() return task:GetTaskStatus() end)
        st = (okS and st) or 1
        if st == FIN then
            skip = skip + 1
        else
            task.unlockPre = true
            task.isNextTaskFinished = true      -- ★ 让后续任务的前置链判定通过
            task.status = FIN                   -- ★ 直接改数据：已完成
            pcall(function() task:SetTaskStatus(FIN) end)
            if task.converseCount == nil then task.converseCount = 0 end
            tm.tbUnStartTasks[key]  = nil
            tm.tbCurTasks[key]      = nil
            tm.tbFinishedTasks[key] = task
            local okR = pcall(function() task:RecieveReward() end)   -- 按配置发奖
            if okR then rw = rw + 1 else rwFail = rwFail + 1 end
            pcall(function() task:OnFinished() end)
            n = n + 1
        end
    end
    pcall(function() tm:_syncUI() end)
    local function cnt(x)
        local c = 0
        if type(x) == "table" then for _ in pairs(x) do c = c + 1 end end
        return c
    end
    return string.format(
        "[成功] 已直接改数据完成 %d 个任务（跳过已完成 %d；发奖成功 %d / 失败 %d）；现在 已完成=%d 进行中=%d 未开始=%d",
        n, skip, rw, rwFail, cnt(tm.tbFinishedTasks), cnt(tm.tbCurTasks), cnt(tm.tbUnStartTasks))
end
_G.g_trainer_task_finish = _finish
local ok, ret = pcall(_finish)
if not ok then return "[错误] " .. tostring(ret) end
return ret
"""


def task_data_unlock():
    """任务：直接改数据解锁（unlockPre + status + 分桶；不经 UnlockPrecondition）"""
    log("正在直接改数据解锁全部任务 ...")
    success, result = execute_lua_retry(
        LUA_TASK_DATA_UNLOCK, timeout=LUA_TIMEOUT_LONG, attempts=3, tag="任务解锁")
    return _log_result(success, result, "任务解锁失败")


def task_data_finish():
    """任务：直接改数据完成（status=FINISHED + 发奖 + 打通前置链）"""
    log("正在直接改数据完成全部任务 ...")
    success, result = execute_lua_retry(
        LUA_TASK_DATA_FINISH, timeout=30.0, attempts=3, tag="任务完成")
    return _log_result(success, result, "任务完成失败")


def probe_tasks():
    """任务状态探查"""
    return execute_lua_safe(LUA_TASK_PROBE, timeout=LUA_TIMEOUT)


def unlock_all_tasks():
    """激活全部未开始任务"""
    log("正在激活全部任务 ...")
    success, result = execute_lua_retry(
        LUA_TASK_UNLOCK_ALL, timeout=LUA_TIMEOUT_LONG, attempts=2, tag="激活全部任务")
    return _log_result(success, result, "任务激活失败")


def finish_all_tasks():
    """完成全部任务"""
    log("正在完成全部任务 ...")
    success, result = execute_lua_safe(LUA_TASK_FINISH_ALL, timeout=30.0)
    return _log_result(success, result, "任务完成失败")


# ============================================================
# 游戏内折叠面板（ImGui）
# ============================================================
# 源码事实：游戏 UI 基于 Dear ImGui，Lua 侧直接暴露全局 ImGui / ImVec2 / KLImGui；
#   game_base.lua:96 里 g_LUiPageManager:GameDraw(dt) 由 LGameBase:GameDraw 每帧调用一次，
#   所以只要「包装 g_LUiPageManager.GameDraw」，就能在游戏画面内画自己的窗口 ——
#   引擎渲染，不开外部覆盖窗口，所以不像旧版外部悬浮窗那样卡。
#
# 【文字编码 —— 上一版乱码的根因】
#   注入的 Lua 代码本身是 UTF-8（Python 端 lua_cmd.txt 用 utf-8 写入），ImGui 也直接吃 UTF-8，
#   所以字符串必须「原样直传」。绝不能再调 util.a2u8：
#     util.a2u8 = ANSI/GBK → UTF-8（游戏自己的 .lua 是 GBK，才需要它转换）。
#     对已经是 UTF-8 的中文再转一次 = 乱码；且该函数对非法输入每帧可能产出不同字节，
#     会让 ImGui 控件 ID 每帧变化 → 折叠头永远展不开、面板内容一直闪。
#
# 【每帧只画一次】同一个 ImGui 帧里重复 Begin/End 同一个窗口，窗口状态（含折叠状态）
#   会被反复重置，表现也是「展不开 + 一直刷新」，故用 ImGui.GetFrameCount() 去重。
#
# 【默认展开】折叠头一律带 ImGuiTreeNodeFlags_DefaultOpen —— 万一鼠标被游戏抢走点不动，
#   内容也能直接看见。

LUA_INGAME_PANEL_INSTALL = r"""
local ok, err = pcall(function()
    if not g_LUiPageManager or not g_LUiPageManager.GameDraw then
        return "[失败] g_LUiPageManager.GameDraw 不存在（请先进入游戏场景）"
    end
    if type(ImGui) ~= "table" or not ImGui.Begin then
        return "[失败] ImGui 全局不可用"
    end
    if not _G.g_wt_orig_GameDraw then
        _G.g_wt_orig_GameDraw = g_LUiPageManager.GameDraw
    end
    _G.g_wt_panel_open  = true
    _G.g_wt_panel_err   = nil
    _G.g_wt_panel_err_n = 0
    _G.g_wt_draw_count  = 0
    _G.g_wt_last_frame  = nil
    _G.g_wt_last_msg    = nil

    -- 文字：原样直传（不要再走 util.a2u8，见文件头说明）
    local function T(s) return tostring(s) end

    -- 折叠头：优先带 DefaultOpen；签名不兼容时逐级降级
    local function Section(label)
        local f = ImGuiTreeNodeFlags_ and ImGuiTreeNodeFlags_.ImGuiTreeNodeFlags_DefaultOpen
        if f then
            local okH, ret = pcall(ImGui.CollapsingHeader, label, f)
            if okH and ret ~= nil then return ret end
        end
        local ok2, ret2 = pcall(ImGui.CollapsingHeader, label)
        if ok2 and ret2 ~= nil then return ret2 end
        ImGui.Text(label)
        ImGui.Separator()
        return true
    end

    local function SetupWindow()
        local pos  = ImVec2:new_local(24, 92)
        local size = ImVec2:new_local(380, 470)
        local cond = ImGuiCond_ and ImGuiCond_.ImGuiCond_FirstUseEver
        if cond then
            pcall(ImGui.SetNextWindowPos, pos, cond)
            pcall(ImGui.SetNextWindowSize, size, cond)
        else
            pcall(ImGui.SetNextWindowPos, pos, 4)
            pcall(ImGui.SetNextWindowSize, size, 4)
        end
    end

    local M = {}

    function M.set_speed(mult)
        local d = _G.define
        if d and d.DAY_TIME_REAL and d.DAY_TICK_COUNT and g_GameWorld then
            g_GameWorld.TICK_DELTA_TIMES = (d.DAY_TIME_REAL / d.DAY_TICK_COUNT) / mult
            _G.g_wt_speed = mult
            _G.g_wt_last_msg = "时间倍速 → " .. tostring(mult) .. "x"
        else
            _G.g_wt_last_msg = "倍速设置失败（define / g_GameWorld 不可用）"
        end
    end

    function M.boom_up()
        -- 优先复用 Python 侧「逐级晋升」注册的全局函数（同一套解锁流程）
        if type(_G.g_trainer_boom_step) == "function" then
            local okS, ret = pcall(_G.g_trainer_boom_step, 0)
            _G.g_wt_last_msg = okS and tostring(ret) or ("品阶晋升异常: " .. tostring(ret))
            return
        end
        local b = (g_camp and g_camp.boom) or _G.boom
        if not b or not b.setBoom then
            _G.g_wt_last_msg = "找不到城市品阶对象（请先进入游戏场景）"
            return
        end
        local cur = (b.GetBoom and b:GetBoom()) or 0
        local mx  = (block_define and block_define.CITY_MAX_LEVEL) or 14
        if cur + 1 > mx then
            _G.g_wt_last_msg = "已达最高品阶 " .. tostring(mx)
            return
        end
        local lv = cur + 1
        b:setBoom(lv)
        pcall(function() b:BoomLevelChange(cur, lv) end)          -- 派发 BOOM_LEVEL_CHANED
        pcall(function() b:UI2S_BoomUpgradeCallback(lv) end)      -- 真正发放该级解锁项
        pcall(function() b:UpdateHistoryMaxBoomLevel() end)
        pcall(function() b:UpdateBoom() end)
        pcall(function() b:_syncUI() end)
        _G.g_wt_last_msg = string.format("品阶 %d → %d（含解锁）", cur, lv)
    end

    local function TaxClass()
        local tm = g_TaxManager
        if not tm then return nil, nil end
        local mt = getmetatable(tm)
        local C = _G.g_trainer_tax_cls
        if not C and type(mt) == "table" and type(mt.__index) == "table" then C = mt.__index end
        if not C or C.SendTaxPage == nil then return tm, nil end
        return tm, C
    end

    function M.tax_toggle()
        local tm, C = TaxClass()
        if not tm then _G.g_wt_last_msg = "g_TaxManager 不存在" return end
        if not C then _G.g_wt_last_msg = "无法定位纳税类方法表" return end
        if not _G.g_trainer_tax_orig_SendTaxPage then
            _G.g_trainer_tax_cls = C
            _G.g_trainer_tax_orig_SendTaxPage = C.SendTaxPage
            _G.g_trainer_tax_orig_OnDay = C.OnDay
        end
        if not _G.g_trainer_tax_auto_pay then
            local function auto_pay(self)
                if self.PayForTax then pcall(function() self:PayForTax() end) end
                return 1
            end
            _G.g_trainer_tax_auto_pay = auto_pay
            C.SendTaxPage = auto_pay
            tm.SendTaxPage = auto_pay
            _G.g_wt_last_msg = "自动纳税：已开启（不弹面板，到期自动扣款）"
        else
            if _G.g_trainer_tax_orig_SendTaxPage then
                C.SendTaxPage = _G.g_trainer_tax_orig_SendTaxPage
                tm.SendTaxPage = _G.g_trainer_tax_orig_SendTaxPage
            end
            if _G.g_trainer_tax_orig_OnDay then
                C.OnDay = _G.g_trainer_tax_orig_OnDay
                tm.OnDay = _G.g_trainer_tax_orig_OnDay
            end
            _G.g_trainer_tax_auto_pay = nil
            _G.g_trainer_tax_ours_OnDay = nil
            _G.g_trainer_tax_cls = nil
            _G.g_wt_last_msg = "自动纳税：已关闭（恢复原版弹窗）"
        end
    end

    function M.tax_pay_now()
        local tm = g_TaxManager
        if not tm or not tm.PayForTax then
            _G.g_wt_last_msg = "g_TaxManager:PayForTax 不可用"
            return
        end
        local okP, eP = pcall(function() tm:PayForTax() end)
        if okP then
            _G.g_wt_last_msg = "已按当前税率缴一次（累计 " .. tostring(tm.taxCount) .. "）"
        else
            _G.g_wt_last_msg = "缴税异常: " .. tostring(eP)
        end
    end

    function M.task_unlock()
        if type(_G.g_trainer_task_unlock) == "function" then
            local okT, ret = pcall(_G.g_trainer_task_unlock)
            _G.g_wt_last_msg = okT and tostring(ret) or ("任务解锁异常: " .. tostring(ret))
        else
            _G.g_wt_last_msg = "请先在修改器「任务」块点一次『直接改数据解锁』注册"
        end
    end

    function M.task_finish()
        if type(_G.g_trainer_task_finish) == "function" then
            local okT, ret = pcall(_G.g_trainer_task_finish)
            _G.g_wt_last_msg = okT and tostring(ret) or ("任务完成异常: " .. tostring(ret))
        else
            _G.g_wt_last_msg = "请先在修改器「任务」块点一次『直接改数据完成』注册"
        end
    end

    local function DrawPanel()
        SetupWindow()
        -- 标题用 ASCII（避免字体风险），### 后的 ID 恒定，折叠/移动状态才稳定
        local open = ImGui.Begin("woldvein Trainer " .. __VER__ .. "###wt_panel")
        if not open then
            ImGui.End()
            return
        end

        local b = g_camp and g_camp.boom
        if Section(T("状态")) then
            local mx = (block_define and block_define.CITY_MAX_LEVEL) or 14
            ImGui.Text(T("城市品阶: " .. tostring((b and b.GetBoom and b:GetBoom()) or -1)
                .. " / " .. tostring(mx)))
            local gt = g_Time
            ImGui.Text(T("游戏天数: " .. tostring((gt and gt.GetDayStamp and gt:GetDayStamp()) or -1)))
            ImGui.Text(T("时间倍速: " .. tostring(_G.g_wt_speed or 1) .. "x"))
            ImGui.Text(T("自动纳税: " .. (_G.g_trainer_tax_auto_pay and "开" or "关")))
            ImGui.Text(T("绘制次数: " .. tostring(_G.g_wt_draw_count)))
        end

        if Section(T("快捷操作")) then
            if ImGui.Button(T("品阶+1（含解锁）")) then M.boom_up() end
            ImGui.SameLine()
            if ImGui.Button(T("自动纳税 开/关")) then M.tax_toggle() end
            ImGui.SameLine()
            if ImGui.Button(T("立即缴税")) then M.tax_pay_now() end
        end

        if Section(T("时间倍速")) then
            if ImGui.Button(T("1x")) then M.set_speed(1) end
            ImGui.SameLine()
            if ImGui.Button(T("2x")) then M.set_speed(2) end
            ImGui.SameLine()
            if ImGui.Button(T("4x")) then M.set_speed(4) end
        end

        if Section(T("任务")) then
            if ImGui.Button(T("任务全解锁（改数据）")) then M.task_unlock() end
            ImGui.SameLine()
            if ImGui.Button(T("任务全完成（改数据）")) then M.task_finish() end
        end

        if Section(T("诊断 / 字体测试")) then
            ImGui.Text(T("字体直传测试：中文 ABC 123 平野孤鸿修改器"))
            local io = ImGui.GetIO and ImGui.GetIO() or nil
            if io then
                local mp = io.MousePos
                ImGui.Text(T(string.format("鼠标 %.0f,%.0f   捕获鼠标=%s   悬停本面板=%s",
                    (mp and mp.x) or -1, (mp and mp.y) or -1,
                    tostring(io.WantCaptureMouse), tostring(ImGui.IsWindowHovered()))))
            end
            if _G.g_wt_last_msg then
                ImGui.Text(T("最近操作: " .. _G.g_wt_last_msg))
            end
            if _G.g_wt_panel_err then
                ImGui.Text(T("最近错误: " .. _G.g_wt_panel_err))
            end
        end

        ImGui.Separator()
        if ImGui.Button(T("隐藏面板")) then _G.g_wt_panel_open = false end
        ImGui.SameLine()
        ImGui.Text(T("（用修改器可重新注入）"))

        ImGui.End()
    end

    g_LUiPageManager.GameDraw = function(self, dt)
        local ok1, e1 = pcall(_G.g_wt_orig_GameDraw, self, dt)
        if not _G.g_wt_panel_open then return ok1, e1 end
        _G.g_wt_draw_count = _G.g_wt_draw_count + 1

        -- 同一个 ImGui 帧只画一次（重复画同窗口会重置折叠状态 -> 展不开 / 闪）
        local fc = ImGui.GetFrameCount and ImGui.GetFrameCount() or nil
        if fc ~= nil then
            if fc == _G.g_wt_last_frame then return ok1, e1 end
            _G.g_wt_last_frame = fc
        end

        local ok2, e2 = pcall(DrawPanel)
        if not ok2 then
            _G.g_wt_panel_err = tostring(e2)
            _G.g_wt_panel_err_n = (_G.g_wt_panel_err_n or 0) + 1
            if _G.g_wt_panel_err_n >= 5 then
                _G.g_wt_panel_open = false     -- 连续 5 帧报错才自动关闭，避免刷屏
            end
        else
            _G.g_wt_panel_err_n = 0
        end
        return ok1, e1
    end
    return "[成功] 游戏内面板已注入（UTF-8 直传 / 默认展开 / 每帧只画一次）"
end)
if not ok then return "[错误] " .. tostring(err) end
return err
"""

LUA_INGAME_PANEL_REMOVE = r"""
local ok, err = pcall(function()
    if _G.g_wt_orig_GameDraw and g_LUiPageManager then
        g_LUiPageManager.GameDraw = _G.g_wt_orig_GameDraw
        _G.g_wt_orig_GameDraw = nil
    end
    _G.g_wt_panel_open  = false
    _G.g_wt_panel_err   = nil
    _G.g_wt_panel_err_n = 0
    _G.g_wt_last_frame  = nil
    return "[成功] 游戏内面板已移除（GameDraw 已还原）"
end)
if not ok then return "[错误] " .. tostring(err) end
return err
"""

LUA_INGAME_PANEL_STATUS = r"""
local ok, err = pcall(function()
    return string.format("已注入=%s 显示中=%s 绘制次数=%s 最近错误=%s 最近操作=%s",
        tostring(_G.g_wt_orig_GameDraw ~= nil), tostring(_G.g_wt_panel_open),
        tostring(_G.g_wt_draw_count), tostring(_G.g_wt_panel_err or "无"),
        tostring(_G.g_wt_last_msg or "无"))
end)
if not ok then return "[错误] " .. tostring(err) end
return err
"""


def install_ingame_panel():
    """注入游戏内 ImGui 面板"""
    log("正在注入游戏内面板 ...")
    code = LUA_INGAME_PANEL_INSTALL.replace("__VER__", "v" + APP_VERSION)
    success, result = execute_lua_retry(
        code, timeout=LUA_TIMEOUT_LONG, attempts=3, tag="注入游戏内面板")
    return _log_result(success, result, "游戏内面板注入失败")


def remove_ingame_panel():
    """移除游戏内面板（还原 GameDraw）"""
    log("正在移除游戏内面板 ...")
    success, result = execute_lua_retry(
        LUA_INGAME_PANEL_REMOVE, timeout=LUA_TIMEOUT_LONG, attempts=3, tag="移除游戏内面板")
    return _log_result(success, result, "游戏内面板移除失败")


def get_ingame_panel_status():
    """游戏内面板状态"""
    return execute_lua_safe(LUA_INGAME_PANEL_STATUS, timeout=LUA_TIMEOUT)

