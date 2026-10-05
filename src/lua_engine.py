"""
woldvein_trainer v0.4.9 — Lua 脚本层（业务侧）

职责边界（v0.4.8 拆分后，沿用至 v0.4.9）：
    本模块**不再实现**任何进程注入与通路逻辑 —— 那些已全部下沉到独立的
    woldvein_injector v0.4.7。这里只做两件事：

        1) 提供一批玩法 Lua 模板常量（加资源、创造模式、城市繁荣度 …）
        2) 通过 injector_client 向 v0.4.7 要一条通道，把脚本投进游戏主线程

    返回值语义与 v0.4.6 完全一致，业务模块无需任何修改：
        (success, result)
        - result 为整数：Lua 返回布尔/数字，success = (result > 0)
        - result 为字符串：Lua 返回字符串（如 JSON）
        - -1：执行失败或超时
"""
import time

from .logger import log_error, log_warning
from .constants import LUA_TIMEOUT
from .injector_client import get_client

DEFAULT_EXPECT = ("[成功]", "[失败]", "[错误]", "[提示]", "[警告]")


def execute_lua(code, timeout=LUA_TIMEOUT):
    """把一段 Lua 投递到游戏主线程执行。"""
    try:
        return get_client().execute(code, timeout)
    except RuntimeError as e:
        # 注入器没找到 / 版本不匹配：一次性说清楚，不要吞掉
        log_error(f"注入器不可用: {e}")
        return False, -1


def execute_lua_safe(code, timeout=LUA_TIMEOUT):
    """安全执行，捕获所有异常，失败返回 (False, -1)。"""
    try:
        return execute_lua(code, timeout)
    except Exception as e:
        log_error(f"Lua执行异常: {e}")
        return False, -1


def execute_lua_retry(code, timeout=LUA_TIMEOUT, attempts=3, tag="", expect=None):
    """关键操作重试包装：拿不到有效结果时自动重发。

    expect: 期望的结果前缀元组；若结果字符串不以这些前缀开头，
            说明拿到的可能是别的命令的残留结果（串号），同样重试。
    """
    expect = tuple(expect) if expect is not None else DEFAULT_EXPECT
    last = (False, -1)
    for i in range(1, max(1, int(attempts)) + 1):
        success, result = execute_lua_safe(code, timeout)
        last = (success, result)
        ok = bool(success)
        if ok and isinstance(result, str):
            ok = result.strip().startswith(expect)
        if ok:
            return success, result
        if i < attempts:
            log_warning(f"[重试] {tag or '关键操作'} 第 {i} 次未拿到有效结果，重发请求 ...")
            time.sleep(0.3)
    return last

# ========== 资源修改 Lua 脚本模板 ==========

LUA_ADD_RESOURCE = r"""
local ok, err = pcall(function()
    if not g_camp or not g_camp.m_tbSource then return false end
    local id = %d
    local amt = %d
    local cur = g_camp.m_tbSource[id] or 0
    g_camp.m_tbSource[id] = cur + amt
    return true
end)
return ok and err or false
"""

LUA_SET_RESOURCE = r"""
local ok, err = pcall(function()
    if not g_camp or not g_camp.m_tbSource then return false end
    g_camp.m_tbSource[%d] = %d
    return true
end)
return ok and err or false
"""

LUA_MAX_HAPPINESS = r"""
local ok, err = pcall(function()
    if not g_camp then return false end
    g_camp.m_nHappinessScore = 999
    g_camp.m_nHappinessLevel = 4
    return true
end)
return ok and err or false
"""

LUA_ADD_FAME = r"""
local ok, err = pcall(function()
    local rep = g_LReputationMgr
    if not rep then return "未找到 g_LReputationMgr（请先进入游戏场景）" end
    local delta = %d
    local before = 0
    pcall(function() if rep.GetReputation then before = rep:GetReputation() end end)
    pcall(function() if rep.ChangeReputation then rep:ChangeReputation(delta) end end)
    pcall(function() if rep.ChangeReputationBase then rep:ChangeReputationBase(delta) end end)
    local after = before
    pcall(function() if rep.GetReputation then after = rep:GetReputation() end end)
    return "知名度 +" .. tostring(delta) .. "（" .. tostring(before) .. " -> " .. tostring(after) .. "）"
end)
if not ok then return "[错误] " .. tostring(err) end
return err
"""

# ========== 创造模式 Lua 脚本 ==========

LUA_CREATIVE_ENABLE = r"""
local ok, err = pcall(function()
    g_bCreativeMode = true
    if g_cm_opt_max_boom == nil then g_cm_opt_max_boom = true end
    if g_cm_opt_unlock_buildings == nil then g_cm_opt_unlock_buildings = true end
    if g_cm_opt_infinite_resources == nil then g_cm_opt_infinite_resources = true end
    if g_cm_opt_unlimited_upgrade == nil then g_cm_opt_unlimited_upgrade = true end

    -- 1. 鸿业满级
    if g_cm_opt_max_boom and g_camp and g_camp.GetCampBoomModule then
        local boom = g_camp:GetCampBoomModule()
        if boom then
            -- hook方法，让查询永远返回满级
            local mt = getmetatable(boom)
            if mt and mt.__index and not mt.__index.__cm_boom_hooked then
                local cls = mt.__index
                cls.__cm_boom_orig_is = cls.IsSatisfied
                cls.__cm_boom_orig_get = cls.GetBoom
                cls.IsSatisfied = function() return true end
                cls.GetBoom = function() return 14 end
                cls.__cm_boom_hooked = true
            end
            
            -- 设置鸿业等级为满级（14级）
            pcall(function() boom:setBoom(14) end)
            
            -- 解锁所有鸿业等级奖励（建筑、谋士、功能等）
            pcall(function()
                if boom.UpdateHistoryMaxBoomLevel then
                    -- 先设置历史最高为1，确保从1级到14级所有奖励都能解锁
                    if boom.setHistoryMaxBoomLevel then
                        boom:setHistoryMaxBoomLevel(1)
                    end
                    -- 触发历史最高等级更新，这会遍历解锁所有中间等级的奖励
                    boom:UpdateHistoryMaxBoomLevel()
                end
            end)
            
            -- 直接遍历解锁每一级的奖励（作为兜底）
            pcall(function()
                if boom.UnLockBoomReward then
                    for i = 1, 14 do
                        boom:UnLockBoomReward(i)
                    end
                end
            end)
            
            -- 触发UI刷新事件
            pcall(function()
                -- 鸿业称号更新
                if g_LHBUI and g_LHBUIEvents and boom.GetCurTitle then
                    local title = boom:GetCurTitle()
                    g_LHBUI:Emit(g_LHBUIEvents.S2UI_UpdateCurBoomTitle, title)
                end
                -- 繁荣度UI刷新
                if g_LHBUIProvider and g_LHBUIEvents and boom.GetProsperityLevel then
                    local pl = boom:GetProsperityLevel()
                    g_LHBUIProvider:EmitTo("LProsperityProvider", g_LHBUIEvents.S2UI_OnUpdateBoom, pl)
                end
                -- 建筑卡片UI刷新
                if g_LHBUIProvider and g_LHBUIEvents and g_blockMgr then
                    local campId = 1
                    -- [API-FIX] LBlockMgr 没有 GetCampBlockId；用 GetCampBlock() 再取 ID
                    if g_blockMgr.GetCampBlock then
                        local _cb = g_blockMgr:GetCampBlock()
                        if _cb and _cb.GetBlockID then campId = _cb:GetBlockID() end
                    end
                    g_LHBUIProvider:EmitTo("LBuildingProvider", g_LHBUIEvents.S2UI_OnUpdateBuildingCards, campId)
                end
                -- 大本营信息刷新
                if g_LHBUI and g_LHBUIEvents then
                    g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnUpdateCampInfo, 1)
                end
            end)
        end
    end

    -- 2. 全建筑解锁 + 只显示最高等级建筑
    if g_cm_opt_unlock_buildings then
        local BCM = g_LBuildingCardManager
        if BCM then
            -- 2a. 全建筑解锁
            -- 第1层：hook每个建筑卡片的 GetUnlockState/SetUnlockState
            if BCM.tabBuildingCards then
                for _, c in pairs(BCM.tabBuildingCards) do
                    if type(c) == "table" and not c.__cm_card_hooked then
                        c.__cm_orig_GetUnlockState = c.GetUnlockState
                        c.__cm_orig_SetUnlockState = c.SetUnlockState
                        c.GetUnlockState = function() return true end
                        c.SetUnlockState = function(self, state)
                            -- 忽略外部设置，强制保持解锁
                            if c.__cm_orig_SetUnlockState then
                                c.__cm_orig_SetUnlockState(self, true)
                            end
                        end
                        c.__cm_card_hooked = true
                        -- 立即设为解锁
                        pcall(function()
                            if c.__cm_orig_SetUnlockState then
                                c.__cm_orig_SetUnlockState(c, true)
                            end
                        end)
                    end
                end
            end
            -- 第2层：hook天赋检查，让天赋解锁判断总是返回true
            if g_TalentManager and not g_TalentManager.__cm_talent_hooked then
                g_TalentManager.__cm_orig_CheckTalent = g_TalentManager.CheckTalentIsActive
                g_TalentManager.CheckTalentIsActive = function() return true end
                g_TalentManager.__cm_talent_hooked = true
            end

            -- scheme层解锁
            if g_LOfficeManager and g_LOfficeManager.GetAdviserOfficeInCamp then
                local office = g_LOfficeManager:GetAdviserOfficeInCamp()
                if office then
                    local allCards = {}
                    if BCM.tabBuildingCards then
                        for _, c in pairs(BCM.tabBuildingCards) do
                            if type(c) == "table" then table.insert(allCards, c) end
                        end
                    end
                    if office.GetScheme then
                        local s = office:GetScheme()
                        if s and s.SetBuildingCardState then
                            pcall(function() s:SetBuildingCardState(allCards, true) end)
                        end
                    end
                    if office.GetBaseScheme then
                        local bs = office:GetBaseScheme()
                        if bs then
                            if bs.AddOtherBuildings then pcall(function() bs:AddOtherBuildings() end) end
                            if bs.SetBuildingCardState then pcall(function() bs:SetBuildingCardState(allCards, true) end) end
                        end
                    end
                end
            end

            -- 注：不hook GetBuildingCards/GetTypedBuildingCards
            -- 原因：完全重写这两个方法会破坏UI获取建筑列表的数据结构
            --       导致游戏UI全部消失。只保留卡片解锁hook即可。
        end
    end

    -- 3. 无限资源
    if g_cm_opt_infinite_resources then
        local BWM = g_BuildingWorldModule
        if BWM and BWM.BuildingMgr then
            local mt = getmetatable(BWM.BuildingMgr)
            if mt and mt.__index and not mt.__index.__cm_res_hooked then
                local cls = mt.__index
                cls.__cm_orig_ConsumeResource = cls.ConsumeResource
                cls.__cm_orig__ConsumeResource = cls._ConsumeResource
                cls.__cm_orig_CheckCanCreate = cls.CheckCanCreateBuilding
                cls.__cm_orig_CheckCanUpgrade = cls.CheckCanUpgradeBuilding
                cls.ConsumeResource = function() return true end
                cls._ConsumeResource = function() return true end
                cls.CheckCanCreateBuilding = function() return true end
                cls.CheckCanUpgradeBuilding = function(self, building)
                    -- 先调用原始函数检查
                    local orig_ok, orig_err = pcall(function()
                        return cls.__cm_orig_CheckCanUpgrade(self, building)
                    end)
                    if orig_ok and orig_err == true then
                        return true
                    end
                    -- 原始返回false时，检查建筑是否有多个等级（避免单等级建筑播放升级动画）
                    if building and building.L and building.G and building.D and building.P then
                        local ok, maxLevel = pcall(function()
                            return g_buidlingCfg:GetBuildingMaxLevel(building.G, building.D, building.P)
                        end)
                        if ok and maxLevel and maxLevel > 1 then
                            -- 建筑有多个等级，当前等级<最大等级时允许升级（解锁等级限制）
                            if building.L < maxLevel then
                                return true
                            end
                        end
                    end
                    -- 单等级建筑或已满级，不允许升级
                    return false
                end
                cls.__cm_res_hooked = true
            end
        end
        if g_camp and not g_camp.__cm_msv_hooked then
            local o_msv = g_camp.ModifySourceValue
            g_camp.__cm_orig_msv = o_msv
            g_camp.ModifySourceValue = function(self, sourceId, value, bIsInit)
                if value and value < 0 and not bIsInit then return end
                if o_msv then return o_msv(self, sourceId, value, bIsInit) end
            end
            g_camp.__cm_msv_hooked = true
        end
    end

    -- 4. 升级无限制（解锁全部功能）
    if g_cm_opt_unlimited_upgrade then
        if g_camp and g_FunctionManager and g_functionType and g_functionState then
            if not g_camp.__cm_func_saved then
                g_camp.__cm_orig_func_states = {}
                for key, funcId in pairs(g_functionType) do
                    if type(funcId) == "number" then
                        -- [API-FIX] 没有 GetFucntionState；读取用 CheckFuncIsUnlock（返回 g_functionState.OPEN/CLOSE）
                        local ok, state = pcall(function() return g_FunctionManager:CheckFuncIsUnlock(funcId) end)
                        if ok then g_camp.__cm_orig_func_states[funcId] = state end
                    end
                end
                g_camp.__cm_func_saved = true
            end
            for key, funcId in pairs(g_functionType) do
                if type(funcId) == "number" then
                    pcall(function() g_FunctionManager:SetFucntionState(funcId, g_functionState.OPEN) end)
                end
            end
        end
    end

    -- 5. GM标志：快速建造 + 忽略地块限制 + 可操作所有建筑
    if g_cm_opt_gm_flags ~= false then
        if g_GameWorld then
            g_GameWorld.bGMBuildFast = true
            g_GameWorld.bGMIgnoreTileLimit = true
            g_GameWorld.bGMCanOperateAllBuildingAndRoad = true
        end
    end

    -- 6. 建筑不受灾害伤害
    if g_cm_opt_no_disaster_damage ~= false then
        local BWM = g_BuildingWorldModule
        if BWM and BWM.BuildingMgr then
            local mgr = BWM.BuildingMgr
            local mt = getmetatable(mgr)
            if mt and mt.__index then
                local cls = mt.__index
                -- 建筑类的hook需要通过建筑实例获取
                pcall(function()
                    if g_camp and g_blockMgr then
                        local block = g_camp:GetCampBlock()
                        if block and block.GetAllBuildings then
                            local buildings = block:GetAllBuildings()
                            if buildings and #buildings > 0 then
                                local b = buildings[1]
                                local bmt = getmetatable(b)
                                if bmt and bmt.__index then
                                    local bcls = bmt.__index
                                    if not bcls.__cm_disaster_hooked then
                                        bcls.__cm_orig_DisasterSubHP = bcls.DisasterSubHP
                                        bcls.DisasterSubHP = function(self, nDisasterType, nSub)
                                            -- 创造模式：建筑不受灾害伤害
                                            return
                                        end
                                        bcls.__cm_disaster_hooked = true
                                    end
                                end
                            end
                        end
                    end
                end)
            end
        end
    end

    -- 7. 不触发灾害
    if g_cm_opt_no_disaster ~= false then
        if g_camp and g_blockMgr then
            local block = g_camp:GetCampBlock()
            if block then
                local mt = getmetatable(block)
                if mt and mt.__index then
                    local cls = mt.__index
                    if not cls.__cm_trigger_disaster_hooked then
                        cls.__cm_orig_TriggerDisaster = cls.TriggerDisaster
                        cls.TriggerDisaster = function(self, type, nLevel)
                            -- 创造模式：不触发灾害
                            return
                        end
                        cls.__cm_trigger_disaster_hooked = true
                    end
                end
            end
        end
    end

    -- 8. 道路连接豁免（行人不必经过道路，可直接到达建筑）
    if g_cm_opt_road_bypass ~= false then
        local BWM = g_BuildingWorldModule
        if BWM and BWM.BuildingMgr then
            local mgr = BWM.BuildingMgr
            local mt = getmetatable(mgr)
            if mt and mt.__index then
                local cls = mt.__index
                if not cls.__cm_road_hooked then
                    cls.__cm_orig_ModifyCheckRoadFlag = cls.ModifyCheckRoadFlag
                    cls.ModifyCheckRoadFlag = function(self, tbwo, bSelf, tbWo2, bCheckFull)
                        local tbVisited = {}
                        for k, wo in pairs(tbwo or {}) do
                            local uuid = wo:GetWOUUID()
                            if not tbVisited[uuid] then
                                tbVisited[uuid] = true
                                local building = wo:GetBuilding()
                                if building then
                                    building.m_bIsCheckRoadAdd = false
                                    pcall(function() building:UpdateIsConnectedToPost() end)
                                end
                            end
                        end
                    end
                    cls.__cm_road_hooked = true
                end
            end
        end
    end

    -- 9. 人口不分类别（工人/匠人/学者通用）
    if g_cm_opt_population_universal ~= false then
        if g_camp and g_blockMgr then
            local block = g_camp:GetCampBlock()
            if block then
                local mt = getmetatable(block)
                if mt and mt.__index then
                    local cls = mt.__index
                    if not cls.__cm_pop_hooked then
                        cls.__cm_orig_GetPopulation = cls.GetPopulation
                        cls.GetPopulation = function(self, tbPSource)
                            if not tbPSource then return 0 end
                            local total = 0
                            pcall(function()
                                total = total + self:GetSourceValue(block_define.SOURCE.CURRENT_POPULATION)
                                total = total + self:GetSourceValue(block_define.SOURCE.CRAFTSMAN)
                                total = total + self:GetSourceValue(block_define.SOURCE.SCHOOLER)
                                total = total + self:GetSourceValue(block_define.SOURCE.REFUGEE_POPULATION)
                                total = total + self:GetSourceValue(block_define.SOURCE.TEMPORARY_POPULATION)
                            end)
                            return total
                        end
                        cls.__cm_pop_hooked = true
                    end
                end
            end
        end
    end

    -- 10. 统一刷新UI
    pcall(function()
        if g_LHBUI and g_LHBUIEvents then
            g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnUpdateCampInfo, 1)
            g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnUpdateBuildingCards, 1)
        end
    end)

    return true
end)
return ok and err or false
"""

LUA_CREATIVE_DISABLE = r"""
local ok, err = pcall(function()
    g_bCreativeMode = false

    -- 1. 还原建筑卡片hook（遍历所有卡片恢复原始方法）
    local BCM = g_LBuildingCardManager
    if BCM and BCM.tabBuildingCards then
        for _, c in pairs(BCM.tabBuildingCards) do
            if type(c) == "table" and c.__cm_card_hooked then
                if c.__cm_orig_SetUnlockState ~= nil then
                    c.SetUnlockState = c.__cm_orig_SetUnlockState
                else
                    c.SetUnlockState = nil
                end
                if c.__cm_orig_GetUnlockState ~= nil then
                    c.GetUnlockState = c.__cm_orig_GetUnlockState
                else
                    c.GetUnlockState = nil
                end
                c.__cm_orig_SetUnlockState = nil
                c.__cm_orig_GetUnlockState = nil
                c.__cm_card_hooked = nil
            end
        end
    end

    -- 1b. 还原天赋检查 CheckTalentIsActive
    if g_TalentManager and g_TalentManager.__cm_talent_hooked then
        if g_TalentManager.__cm_orig_CheckTalent ~= nil then
            g_TalentManager.CheckTalentIsActive = g_TalentManager.__cm_orig_CheckTalent
        else
            g_TalentManager.CheckTalentIsActive = nil
        end
        g_TalentManager.__cm_orig_CheckTalent = nil
        g_TalentManager.__cm_talent_hooked = nil
    end

    -- 1c. 还原建筑列表过滤hook（旧版本残留，新版本已移除但需清理）
    local BCM = g_LBuildingCardManager
    if BCM and BCM.__cm_filter_hooked then
        if BCM.__cm_orig_GetBuildingCards ~= nil then
            BCM.GetBuildingCards = BCM.__cm_orig_GetBuildingCards
        end
        if BCM.__cm_orig_GetTypedBuildingCards ~= nil then
            BCM.GetTypedBuildingCards = BCM.__cm_orig_GetTypedBuildingCards
        end
        BCM.__cm_orig_GetBuildingCards = nil
        BCM.__cm_orig_GetTypedBuildingCards = nil
        BCM.__cm_filter_hooked = nil
        BCM.__cm_max_level = nil
        BCM.__cm_has_level = nil
    end

    -- 2. 还原资源hook
    local BWM = g_BuildingWorldModule
    if BWM and BWM.BuildingMgr then
        local mgr = BWM.BuildingMgr
        local mt = getmetatable(mgr)
        if mt and mt.__index then
            local cls = mt.__index
            if cls.__cm_res_hooked then
                if cls.__cm_orig_ConsumeResource ~= nil then cls.ConsumeResource = cls.__cm_orig_ConsumeResource else cls.ConsumeResource = nil end
                if cls.__cm_orig__ConsumeResource ~= nil then cls._ConsumeResource = cls.__cm_orig__ConsumeResource else cls._ConsumeResource = nil end
                if cls.__cm_orig_CheckCanCreate ~= nil then cls.CheckCanCreateBuilding = cls.__cm_orig_CheckCanCreate else cls.CheckCanCreateBuilding = nil end
                if cls.__cm_orig_CheckCanUpgrade ~= nil then cls.CheckCanUpgradeBuilding = cls.__cm_orig_CheckCanUpgrade else cls.CheckCanUpgradeBuilding = nil end
                cls.__cm_orig_ConsumeResource = nil
                cls.__cm_orig__ConsumeResource = nil
                cls.__cm_orig_CheckCanCreate = nil
                cls.__cm_orig_CheckCanUpgrade = nil
                cls.__cm_res_hooked = nil
            end
        end
    end

    -- 还原GM标志
    if g_GameWorld then
        g_GameWorld.bGMBuildFast = false
        g_GameWorld.bGMIgnoreTileLimit = false
        g_GameWorld.bGMCanOperateAllBuildingAndRoad = false
    end

    -- 还原建筑灾害伤害hook
    pcall(function()
        if g_camp and g_blockMgr then
            local block = g_camp:GetCampBlock()
            if block and block.GetAllBuildings then
                local buildings = block:GetAllBuildings()
                if buildings and #buildings > 0 then
                    local b = buildings[1]
                    local bmt = getmetatable(b)
                    if bmt and bmt.__index then
                        local bcls = bmt.__index
                        if bcls.__cm_disaster_hooked then
                            if bcls.__cm_orig_DisasterSubHP ~= nil then
                                bcls.DisasterSubHP = bcls.__cm_orig_DisasterSubHP
                            else
                                bcls.DisasterSubHP = nil
                            end
                            bcls.__cm_orig_DisasterSubHP = nil
                            bcls.__cm_disaster_hooked = nil
                        end
                    end
                end
            end
        end
    end)

    -- 还原不触发灾害hook
    if g_camp and g_blockMgr then
        local block = g_camp:GetCampBlock()
        if block then
            local mt = getmetatable(block)
            if mt and mt.__index then
                local cls = mt.__index
                if cls.__cm_trigger_disaster_hooked then
                    if cls.__cm_orig_TriggerDisaster ~= nil then
                        cls.TriggerDisaster = cls.__cm_orig_TriggerDisaster
                    else
                        cls.TriggerDisaster = nil
                    end
                    cls.__cm_orig_TriggerDisaster = nil
                    cls.__cm_trigger_disaster_hooked = nil
                end
            end
        end
    end

    -- 还原道路连接豁免hook
    local BWM2 = g_BuildingWorldModule
    if BWM2 and BWM2.BuildingMgr then
        local mgr2 = BWM2.BuildingMgr
        local mt2 = getmetatable(mgr2)
        if mt2 and mt2.__index then
            local cls2 = mt2.__index
            if cls2.__cm_road_hooked then
                if cls2.__cm_orig_ModifyCheckRoadFlag ~= nil then
                    cls2.ModifyCheckRoadFlag = cls2.__cm_orig_ModifyCheckRoadFlag
                else
                    cls2.ModifyCheckRoadFlag = nil
                end
                cls2.__cm_orig_ModifyCheckRoadFlag = nil
                cls2.__cm_road_hooked = nil
            end
        end
    end

    -- 还原人口不分类别hook
    if g_camp and g_blockMgr then
        local block2 = g_camp:GetCampBlock()
        if block2 then
            local mt3 = getmetatable(block2)
            if mt3 and mt3.__index then
                local cls3 = mt3.__index
                if cls3.__cm_pop_hooked then
                    if cls3.__cm_orig_GetPopulation ~= nil then
                        cls3.GetPopulation = cls3.__cm_orig_GetPopulation
                    else
                        cls3.GetPopulation = nil
                    end
                    cls3.__cm_orig_GetPopulation = nil
                    cls3.__cm_pop_hooked = nil
                end
            end
        end
    end

    -- 3. 还原ModifySourceValue
    if g_camp and g_camp.__cm_msv_hooked then
        if g_camp.__cm_orig_msv ~= nil then
            g_camp.ModifySourceValue = g_camp.__cm_orig_msv
        else
            g_camp.ModifySourceValue = nil
        end
        g_camp.__cm_orig_msv = nil
        g_camp.__cm_msv_hooked = nil
    end

    -- 4. 还原鸿业hook
    if g_camp and g_camp.GetCampBoomModule then
        local boom = g_camp:GetCampBoomModule()
        if boom then
            local mt = getmetatable(boom)
            if mt and mt.__index then
                local cls = mt.__index
                if cls.__cm_boom_hooked then
                    if cls.__cm_boom_orig_is ~= nil then cls.IsSatisfied = cls.__cm_boom_orig_is else cls.IsSatisfied = nil end
                    if cls.__cm_boom_orig_get ~= nil then cls.GetBoom = cls.__cm_boom_orig_get else cls.GetBoom = nil end
                    cls.__cm_boom_orig_is = nil
                    cls.__cm_boom_orig_get = nil
                    cls.__cm_boom_hooked = nil
                end
            end
        end
    end

    -- 5. 还原全部游戏功能状态
    if g_camp and g_camp.__cm_func_saved and g_camp.__cm_orig_func_states then
        if g_FunctionManager then
            pcall(function()
                for funcId, state in pairs(g_camp.__cm_orig_func_states) do
                    pcall(function() g_FunctionManager:SetFucntionState(funcId, state) end)
                end
            end)
        end
        g_camp.__cm_orig_func_states = nil
        g_camp.__cm_func_saved = nil
    end

    return true
end)
return ok and err or false
"""

LUA_GET_STATUS = r"""
local ok, err = pcall(function()
    local status = {}
    status.creative_mode = g_bCreativeMode or false
    -- 鸿业等级
    if g_camp and g_camp.GetCampBoomModule then
        local boom = g_camp:GetCampBoomModule()
        if boom and boom.GetBoom then
            status.boom_level = boom:GetBoom()
        end
        -- 鸿业称号
        if boom and boom.GetCurTitle then
            local ok2, title = pcall(function() return boom:GetCurTitle() end)
            if ok2 and title then status.boom_title = title end
        end
        -- 繁荣度等级
        if boom and boom.GetProsperityLevel then
            local ok2, pl = pcall(function() return boom:GetProsperityLevel() end)
            if ok2 and pl then status.prosperity_level = pl end
        end
    end
    -- 资源（全部资源类型，注意id=2矿产 id=3木料）
    if g_camp and g_camp.m_tbSource then
        status.money = g_camp.m_tbSource[1] or 0
        status.mineral = g_camp.m_tbSource[2] or 0
        status.wood = g_camp.m_tbSource[3] or 0
        status.cloth = g_camp.m_tbSource[4] or 0
        status.food = g_camp.m_tbSource[5] or 0
        status.water = g_camp.m_tbSource[6] or 0
        status.population = g_camp.m_tbSource[7] or 0
        status.salt = g_camp.m_tbSource[19] or 0
        status.wine = g_camp.m_tbSource[20] or 0
        status.essence = g_camp.m_tbSource[25] or 0
    end
    -- 幸福度（知名度字段名不固定，暂不查询）
    if g_camp then
        if g_camp.GetHappiness then
            local h = g_camp:GetHappiness()
            if h then status.happiness = h end
        end
    end
    -- 建筑卡片统计
    if g_LBuildingCardManager and g_LBuildingCardManager.tabBuildingCards then
        local count = 0
        local unlocked = 0
        for _, c in pairs(g_LBuildingCardManager.tabBuildingCards) do
            count = count + 1
            if c.GetUnlockState and c:GetUnlockState() then
                unlocked = unlocked + 1
            end
        end
        status.card_count = count
        status.card_unlocked = unlocked
    end
    -- 时间速度
    if g_Time and g_Time.GetTimeSpeed then
        local ok2, spd = pcall(function() return g_Time:GetTimeSpeed() end)
        if ok2 and spd then status.time_speed = spd end
    end
    -- 当前季节
    if g_Time and g_Time.GetSeason then
        local ok2, s = pcall(function() return g_Time:GetSeason() end)
        if ok2 then status.season = s end
    end
    -- 序列化为JSON字符串（手动序列化，不依赖cjson）
    local function escape_str(s)
        -- JSON字符串转义：处理双引号、反斜杠、换行、回车、制表符
        local r = string.gsub(s, '\\', '\\\\')
        r = string.gsub(r, '"', '\\"')
        r = string.gsub(r, '\n', '\\n')
        r = string.gsub(r, '\r', '\\r')
        r = string.gsub(r, '\t', '\\t')
        return r
    end
    local function val(v)
        if type(v) == "boolean" then return v and "true" or "false" end
        if type(v) == "number" then return tostring(v) end
        if type(v) == "string" then return '"' .. escape_str(v) .. '"' end
        return "null"
    end
    local json = "{"
    local first = true
    for k, v in pairs(status) do
        if not first then json = json .. "," end
        first = false
        json = json .. '"' .. k .. '":' .. val(v)
    end
    json = json .. "}"
    return json
end)
if not ok then return '{"error":true}' end
return err
"""

# ========== 建筑解锁诊断 Lua 脚本 ==========

LUA_DIAGNOSE_UNLOCK = r"""
local ok, err = pcall(function()
    local lines = {}
    table.insert(lines, "========== 建筑解锁诊断报告 ==========")
    
    local BCM = g_LBuildingCardManager
    if not BCM then
        table.insert(lines, "[错误] g_LBuildingCardManager 不存在")
        return table.concat(lines, "\n")
    end
    
    -- 1. 统计全局卡片解锁状态
    table.insert(lines, "")
    table.insert(lines, "【1. 全局建筑卡片统计】")
    local total = 0
    local unlocked = 0
    local locked = 0
    local locked_list = {}
    local level1_count = 0
    local level1_unlocked = 0
    
    if BCM.tabBuildingCards then
        for key, card in pairs(BCM.tabBuildingCards) do
            total = total + 1
            local isUnlocked = false
            if card.GetUnlockState then
                isUnlocked = card:GetUnlockState()
            end
            if isUnlocked then
                unlocked = unlocked + 1
            else
                locked = locked + 1
                if #locked_list < 20 then
                    local name = "unknown"
                    if card.GetName then name = card:GetName() end
                    local g, d, p, l = 0, 0, 0, 0
                    if card.GetGDPL then
                        g, d, p, l = card:GetGDPL()
                    elseif card.G then g, d, p, l = card.G, card.D, card.P, card.L end
                    table.insert(locked_list, string.format("  %s (G=%d,D=%d,P=%d,L=%d)", name, g, d, p, l))
                end
            end
            if card.L and card.L == 1 then
                level1_count = level1_count + 1
                if isUnlocked then level1_unlocked = level1_unlocked + 1 end
            end
        end
    end
    
    table.insert(lines, string.format("  总卡片数: %d", total))
    table.insert(lines, string.format("  已解锁: %d", unlocked))
    table.insert(lines, string.format("  未解锁: %d", locked))
    table.insert(lines, string.format("  Lv.1卡片: %d (已解锁: %d)", level1_count, level1_unlocked))
    
    if #locked_list > 0 then
        table.insert(lines, "  未解锁卡片（前20个）:")
        for _, s in ipairs(locked_list) do
            table.insert(lines, s)
        end
    end
    
    -- 2. 天赋管理器状态
    table.insert(lines, "")
    table.insert(lines, "【2. 天赋管理器】")
    local TM = g_TalentManager
    if not TM then
        table.insert(lines, "  [错误] g_TalentManager 不存在")
    else
        table.insert(lines, "  g_TalentManager 存在")
        -- 检查方法类型
        if TM.CheckTalentIsActive then
            table.insert(lines, string.format("  CheckTalentIsActive 类型: %s", type(TM.CheckTalentIsActive)))
        else
            table.insert(lines, "  [警告] CheckTalentIsActive 方法不存在")
        end
        if TM.CheckIsUnlockBuildingCard then
            table.insert(lines, string.format("  CheckIsUnlockBuildingCard 类型: %s", type(TM.CheckIsUnlockBuildingCard)))
        end
        if TM.CheckUnlockBuildingCardTalentIdIsUnlock then
            table.insert(lines, string.format("  CheckUnlockBuildingCardTalentIdIsUnlock 类型: %s", type(TM.CheckUnlockBuildingCardTalentIdIsUnlock)))
        end
        -- 测试hook
        table.insert(lines, "  --- hook测试 ---")
        local orig = TM.CheckTalentIsActive
        TM.CheckTalentIsActive = function() return true end
        local test_result = TM:CheckTalentIsActive(1,1,1,1)
        table.insert(lines, string.format("  hook后CheckTalentIsActive返回: %s", tostring(test_result)))
        -- 还原
        TM.CheckTalentIsActive = orig
        table.insert(lines, "  已还原原始方法")
    end
    
    -- 3. 方案卡状态
    table.insert(lines, "")
    table.insert(lines, "【3. 当前方案卡】")
    local OM = g_LOfficeManager
    if not OM then
        table.insert(lines, "  [错误] g_LOfficeManager 不存在")
    else
        local office = nil
        if OM.GetAdviserOfficeInCamp then
            office = OM:GetAdviserOfficeInCamp()
        elseif OM.GetAdviserOfficeByBlockGDPL and g_blockMgr then
            local block = g_blockMgr:GetSelectedBlock()
            if block then
                office = OM:GetAdviserOfficeByBlockGDPL(block.nId, 0, 0, 0)
            end
        end
        
        if not office then
            table.insert(lines, "  [警告] 未找到当前区块的事务所/方案卡")
        else
            local scheme = nil
            if office.GetScheme then
                scheme = office:GetScheme()
            end
            if not scheme then
                table.insert(lines, "  [警告] 方案卡不存在")
            else
                local scheme_buildings = nil
                if scheme.GetSchemeBuildings then
                    scheme_buildings = scheme:GetSchemeBuildings()
                end
                if scheme_buildings then
                    local s_total = #scheme_buildings
                    local s_unlocked = 0
                    local s_locked = 0
                    for _, card in ipairs(scheme_buildings) do
                        if card.GetUnlockState and card:GetUnlockState() then
                            s_unlocked = s_unlocked + 1
                        else
                            s_locked = s_locked + 1
                        end
                    end
                    table.insert(lines, string.format("  方案卡建筑数: %d", s_total))
                    table.insert(lines, string.format("  已解锁: %d", s_unlocked))
                    table.insert(lines, string.format("  未解锁: %d", s_locked))
                    
                    -- 列出前10个未解锁的
                    local s_locked_list = {}
                    for _, card in ipairs(scheme_buildings) do
                        if not (card.GetUnlockState and card:GetUnlockState()) then
                            if #s_locked_list < 10 then
                                local name = "unknown"
                                if card.GetName then name = card:GetName() end
                                table.insert(s_locked_list, "    " .. name)
                            end
                        end
                    end
                    if #s_locked_list > 0 then
                        table.insert(lines, "  方案中未解锁建筑（前10个）:")
                        for _, s in ipairs(s_locked_list) do
                            table.insert(lines, s)
                        end
                    end
                else
                    table.insert(lines, "  [警告] GetSchemeBuildings 返回空")
                end
            end
        end
    end
    
    -- 4. 卡片方法hook测试
    table.insert(lines, "")
    table.insert(lines, "【4. 卡片方法hook测试】")
    if BCM.tabBuildingCards then
        -- 找第一张卡片测试
        local test_card = nil
        for _, card in pairs(BCM.tabBuildingCards) do
            test_card = card
            break
        end
        if test_card then
            local name = "unknown"
            if test_card.GetName then name = test_card:GetName() end
            table.insert(lines, string.format("  测试卡片: %s", name))
            table.insert(lines, string.format("  GetUnlockState 类型: %s", type(test_card.GetUnlockState)))
            table.insert(lines, string.format("  SetUnlockState 类型: %s", type(test_card.SetUnlockState)))
            
            -- 测试 hook SetUnlockState
            local orig_set = test_card.SetUnlockState
            local hook_called = false
            test_card.SetUnlockState = function(self, state)
                hook_called = true
                if orig_set then orig_set(self, true) end
            end
            test_card:SetUnlockState(false)
            table.insert(lines, string.format("  hook SetUnlockState后调用SetUnlockState(false): hook被调用=%s, 实际状态=%s", 
                tostring(hook_called), tostring(test_card:GetUnlockState())))
            -- 还原
            test_card.SetUnlockState = orig_set
            table.insert(lines, "  已还原原始SetUnlockState")
        end
    end
    
    -- 5. 检测当前创造模式hook状态
    table.insert(lines, "")
    table.insert(lines, "【5. 创造模式hook状态】")
    table.insert(lines, string.format("  g_bCreativeMode = %s", tostring(g_bCreativeMode or false)))
    
    local hooked_count = 0
    if BCM.tabBuildingCards then
        for _, card in pairs(BCM.tabBuildingCards) do
            if card.__cm_card_hooked then
                hooked_count = hooked_count + 1
            end
        end
    end
    table.insert(lines, string.format("  已hook的卡片数: %d", hooked_count))
    
    if TM and TM.__cm_talent_hooked then
        table.insert(lines, "  天赋管理器: 已hook")
    else
        table.insert(lines, "  天赋管理器: 未hook")
    end
    
    if BCM and BCM.__cm_filter_hooked then
        table.insert(lines, "  建筑过滤器: 已hook（只显示最高等级）")
    else
        table.insert(lines, "  建筑过滤器: 未hook")
    end
    
    table.insert(lines, "")
    table.insert(lines, "========== 诊断结束 ==========")
    
    return table.concat(lines, "\\n")
end)
if not ok then return "诊断失败: " .. tostring(err) end
return err
"""


