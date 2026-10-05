#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
woldvein Trainer v0.3 - 一键作弊工具模块

功能说明：
    基于深度探针发现的游戏内部对象和函数，提供一键作弊功能。
    包括天赋、成就、灾害、时间、天气、节日、城市、风水、建筑、核心数值等。

关键技术事实：
    - g_TalentManager:UnlockAllTalent() - 解锁所有天赋
    - g_TalentManager:UpMaxAllTalent() - 所有天赋升满级
    - g_TalentManager:GM_TalentPoint200_Add() - GM命令加200天赋点
    - g_LAchievementMgr:GM_UnlockAllAchievement() - GM命令解锁所有成就
    - g_earthquakeDisaster:ClearAll() - 清除所有地震
    - g_Time.DEBUG_SEASON_FIXED = true - 固定季节
    - g_WeatherLogicMgr.DEBUG_FIXED = true - 固定天气
    - g_FestivalManager:FestivalPause() - 节日暂停
    - g_CityRankManager:AllCitiesGrow() - 所有城市成长
    - g_LFengshuiManager:_GM_ShowSelectBlockFs() - GM显示地块风水
    - g_camp.boomLevel = 14 - 鸿业等级直接赋值
"""

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.lua_engine import execute_lua_safe, execute_lua_retry
from src.logger import log, log_success, log_error, log_warning
from src.constants import LUA_TIMEOUT, LUA_TIMEOUT_LONG


# ============================================================
# 天赋系统
# ============================================================

def unlock_all_talents():
    """解锁所有天赋"""
    lua = """
    local result = {}
    if g_TalentManager then
        local ok, err = pcall(function()
            g_TalentManager:UnlockAllTalent()
        end)
        if ok then
            table.insert(result, "所有天赋已解锁")
        else
            table.insert(result, "解锁失败: " .. tostring(err))
        end
    else
        table.insert(result, "错误: g_TalentManager 不存在")
    end
    return table.concat(result, "\\n")
    """
    return execute_lua_safe(lua)


def max_all_talents():
    """所有天赋升满级"""
    lua = """
    local result = {}
    if g_TalentManager then
        local ok, err = pcall(function()
            g_TalentManager:UpMaxAllTalent()
        end)
        if ok then
            table.insert(result, "所有天赋已升满级")
        else
            table.insert(result, "升级失败: " .. tostring(err))
        end
    else
        table.insert(result, "错误: g_TalentManager 不存在")
    end
    return table.concat(result, "\\n")
    """
    return execute_lua_safe(lua)


def add_talent_points_200():
    """加200天赋点（GM命令）"""
    lua = """
    local result = {}
    if g_TalentManager then
        local ok, err = pcall(function()
            g_TalentManager:GM_TalentPoint200_Add()
        end)
        if ok then
            table.insert(result, "已增加200天赋点")
        else
            table.insert(result, "增加失败: " .. tostring(err))
        end
    else
        table.insert(result, "错误: g_TalentManager 不存在")
    end
    return table.concat(result, "\\n")
    """
    return execute_lua_safe(lua)


def get_talent_info():
    """获取天赋信息"""
    lua = """
    local result = {}
    if g_TalentManager then
        local left = g_TalentManager.GetLeftTalentPoint and g_TalentManager:GetLeftTalentPoint() or "未知"
        local used = g_TalentManager.GetUsedTalentPoint and g_TalentManager:GetUsedTalentPoint() or "未知"
        local active = g_TalentManager.GetActiveTalentNum and g_TalentManager:GetActiveTalentNum() or "未知"
        local full = g_TalentManager.GetFullLevelTalentNum and g_TalentManager:GetFullLevelTalentNum() or "未知"
        table.insert(result, "剩余天赋点: " .. tostring(left))
        table.insert(result, "已用天赋点: " .. tostring(used))
        table.insert(result, "已激活天赋数: " .. tostring(active))
        table.insert(result, "满级天赋数: " .. tostring(full))
    else
        table.insert(result, "错误: g_TalentManager 不存在")
    end
    return table.concat(result, "\\n")
    """
    return execute_lua_safe(lua)


# ============================================================
# 成就系统
# ============================================================

def unlock_all_achievements():
    """解锁所有成就（GM命令）"""
    lua = """
    local result = {}
    if g_LAchievementMgr then
        local ok, err = pcall(function()
            g_LAchievementMgr:GM_UnlockAllAchievement()
        end)
        if ok then
            table.insert(result, "所有成就已解锁")
        else
            table.insert(result, "解锁失败: " .. tostring(err))
        end
    else
        table.insert(result, "错误: g_LAchievementMgr 不存在")
    end
    return table.concat(result, "\\n")
    """
    return execute_lua_safe(lua)


def get_achievement_info():
    """获取成就信息"""
    lua = """
    local result = {}
    if g_LAchievementMgr then
        table.insert(result, "已解锁成就数: " .. tostring(g_LAchievementMgr.unlockAchNumber or "未知"))
        table.insert(result, "天赋解锁数: " .. tostring(g_LAchievementMgr.talentUnLockCount or "未知"))
        table.insert(result, "天赋满级数: " .. tostring(g_LAchievementMgr.talentFullCount or "未知"))
        table.insert(result, "议会会议数: " .. tostring(g_LAchievementMgr.councilMeetingCount or "未知"))
        table.insert(result, "购买别墅数: " .. tostring(g_LAchievementMgr.buyVillaCount or "未知"))
    else
        table.insert(result, "错误: g_LAchievementMgr 不存在")
    end
    return table.concat(result, "\\n")
    """
    return execute_lua_safe(lua)


# ============================================================
# 灾害系统
# ============================================================

def clear_all_earthquakes():
    """清除所有地震"""
    lua = """
    local result = {}
    if g_earthquakeDisaster then
        local ok, err = pcall(function()
            g_earthquakeDisaster:ClearAll()
        end)
        if ok then
            table.insert(result, "所有地震已清除")
        else
            table.insert(result, "清除失败: " .. tostring(err))
        end
    else
        table.insert(result, "错误: g_earthquakeDisaster 不存在")
    end
    return table.concat(result, "\\n")
    """
    return execute_lua_safe(lua)


def close_all_disasters():
    """关闭所有当前灾害（4种）"""
    lua = """
    local result = {}
    local disasters = {
        {"洪水", g_DelugeDisaster},
        {"沙尘暴", g_SandstormDisaster},
        {"龙卷风", g_tornadoDisaster},
        {"地震", g_earthquakeDisaster},
    }
    for _, d in ipairs(disasters) do
        local name, obj = d[1], d[2]
        if obj then
            local ok, err = pcall(function()
                if obj.Close then obj:Close() end
            end)
            if ok then
                table.insert(result, name .. " 已关闭")
            else
                table.insert(result, name .. " 关闭失败: " .. tostring(err))
            end
        else
            table.insert(result, name .. " 对象不存在")
        end
    end
    -- 同时清除活跃灾害计数
    if g_camp then
        g_camp.m_nActiveDisasters = 0
        table.insert(result, "活跃灾害计数已清零")
    end
    return table.concat(result, "\\n")
    """
    return execute_lua_safe(lua)


def disable_disaster_triggers():
    """禁用灾害触发（把触发概率设为0）"""
    lua = """
    local result = {}
    if g_SandstormDisaster and g_SandstormDisaster.class then
        g_SandstormDisaster.class.BaseTriggerProbability = 0
        table.insert(result, "沙尘暴触发概率已设为0")
    end
    if g_camp then
        g_camp.m_nActiveDisasters = 0
        table.insert(result, "活跃灾害计数已清零")
    end
    table.insert(result, "注意: 部分灾害的触发概率在class表中，可能需要重新进入游戏生效")
    return table.concat(result, "\\n")
    """
    return execute_lua_safe(lua)


def get_disaster_info():
    """获取灾害信息"""
    lua = """
    local result = {}
    if g_camp then
        table.insert(result, "活跃灾害数: " .. tostring(g_camp.m_nActiveDisasters or "未知"))
    end
    local disasters = {
        {"洪水", g_DelugeDisaster},
        {"沙尘暴", g_SandstormDisaster},
        {"龙卷风", g_tornadoDisaster},
        {"地震", g_earthquakeDisaster},
    }
    for _, d in ipairs(disasters) do
        local name, obj = d[1], d[2]
        if obj then
            local active = obj.m_bActive and "活跃" or "未活跃"
            table.insert(result, name .. ": " .. active)
        end
    end
    return table.concat(result, "\\n")
    """
    return execute_lua_safe(lua)


# ============================================================
# 时间系统
# ============================================================

def fix_season(enable):
    """固定/取消固定季节

    Args:
        enable: True=固定季节, False=取消固定
    """
    lua = """
    local result = {}
    if g_Time then
        g_Time.DEBUG_SEASON_FIXED = %s
        table.insert(result, "季节固定: %s")
    else
        table.insert(result, "错误: g_Time 不存在")
    end
    return table.concat(result, "\\n")
    """ % ("true" if enable else "false", "已开启" if enable else "已关闭")
    return execute_lua_safe(lua)


def skip_time_events(enable):
    """跳过/恢复时间事件

    Args:
        enable: True=跳过时间事件, False=恢复
    """
    val = "true" if enable else "false"
    status = "已开启" if enable else "已关闭"
    lua = """
    local result = {}
    if g_Time and g_Time.DEBUG_SKIP_TIME_EVENT then
        g_Time.DEBUG_SKIP_TIME_EVENT.ON_DAY = %s
        g_Time.DEBUG_SKIP_TIME_EVENT.ON_MONTH = %s
        g_Time.DEBUG_SKIP_TIME_EVENT.ON_SEASON = %s
        g_Time.DEBUG_SKIP_TIME_EVENT.ON_YEAR = %s
        table.insert(result, "时间事件跳过: %s")
    else
        table.insert(result, "错误: g_Time 或 DEBUG_SKIP_TIME_EVENT 不存在")
    end
    return table.concat(result, "\\n")
    """ % (val, val, val, val, status)
    return execute_lua_safe(lua)


def get_time_info():
    """获取时间信息"""
    lua = """
    local result = {}
    if g_Time then
        table.insert(result, "季节固定: " .. tostring(g_Time.DEBUG_SEASON_FIXED or false))
        if g_Time.DEBUG_SKIP_TIME_EVENT then
            table.insert(result, "跳过日事件: " .. tostring(g_Time.DEBUG_SKIP_TIME_EVENT.ON_DAY or false))
            table.insert(result, "跳过月事件: " .. tostring(g_Time.DEBUG_SKIP_TIME_EVENT.ON_MONTH or false))
            table.insert(result, "跳过季节事件: " .. tostring(g_Time.DEBUG_SKIP_TIME_EVENT.ON_SEASON or false))
            table.insert(result, "跳过年事件: " .. tostring(g_Time.DEBUG_SKIP_TIME_EVENT.ON_YEAR or false))
        end
    end
    if g_camp then
        table.insert(result, "已过天数: " .. tostring(g_camp.m_nPassedDays or "未知"))
        table.insert(result, "已过秒数: " .. tostring(g_camp.m_nPassedSeconds or "未知"))
    end
    return table.concat(result, "\\n")
    """
    return execute_lua_safe(lua)


# ============================================================
# 天气系统
# ============================================================

def fix_weather(enable):
    """固定/取消固定天气

    Args:
        enable: True=固定天气, False=取消固定
    """
    lua = """
    local result = {}
    if g_WeatherLogicMgr then
        g_WeatherLogicMgr.DEBUG_FIXED = %s
        table.insert(result, "天气固定: %s")
    else
        table.insert(result, "错误: g_WeatherLogicMgr 不存在")
    end
    return table.concat(result, "\\n")
    """ % ("true" if enable else "false", "已开启" if enable else "已关闭")
    return execute_lua_safe(lua)


def get_weather_info():
    """获取天气信息"""
    lua = """
    local result = {}
    if g_WeatherLogicMgr then
        table.insert(result, "天气固定: " .. tostring(g_WeatherLogicMgr.DEBUG_FIXED or false))
        table.insert(result, "可切换天气: " .. tostring(g_WeatherLogicMgr.bCanCutWeather or "未知"))
        if g_WeatherLogicMgr.GetCurrentWeather then
            local w = g_WeatherLogicMgr:GetCurrentWeather()
            table.insert(result, "当前天气: " .. tostring(w))
        end
        if g_WeatherLogicMgr.GetCurrentWind then
            local wind = g_WeatherLogicMgr:GetCurrentWind()
            table.insert(result, "当前风: " .. tostring(wind))
        end
    end
    return table.concat(result, "\\n")
    """
    return execute_lua_safe(lua)


# ============================================================
# 节日系统
# ============================================================

def pause_festival():
    """节日暂停"""
    lua = """
    local result = {}
    if g_FestivalManager then
        local ok, err = pcall(function()
            g_FestivalManager:FestivalPause()
        end)
        if ok then
            table.insert(result, "节日已暂停")
        else
            table.insert(result, "暂停失败: " .. tostring(err))
        end
    else
        table.insert(result, "错误: g_FestivalManager 不存在")
    end
    return table.concat(result, "\\n")
    """
    return execute_lua_safe(lua)


def close_fireworks():
    """关闭烟花"""
    lua = """
    local result = {}
    if g_FestivalManager then
        local ok, err = pcall(function()
            g_FestivalManager:CloseFireWorks()
        end)
        if ok then
            table.insert(result, "烟花已关闭")
        else
            table.insert(result, "关闭失败: " .. tostring(err))
        end
    else
        table.insert(result, "错误: g_FestivalManager 不存在")
    end
    return table.concat(result, "\\n")
    """
    return execute_lua_safe(lua)


def clear_all_festival_ads():
    """清除所有节日建筑广告记录"""
    lua = """
    local result = {}
    if g_FestivalManager then
        local ok, err = pcall(function()
            g_FestivalManager:ClearAllBuildingAdRecord()
        end)
        if ok then
            table.insert(result, "所有节日广告记录已清除")
        else
            table.insert(result, "清除失败: " .. tostring(err))
        end
    else
        table.insert(result, "错误: g_FestivalManager 不存在")
    end
    return table.concat(result, "\\n")
    """
    return execute_lua_safe(lua)


# ============================================================
# 城市系统
# ============================================================

def grow_all_cities():
    """所有城市成长"""
    lua = """
    local result = {}
    if g_CityRankManager then
        local ok, err = pcall(function()
            g_CityRankManager:AllCitiesGrow()
        end)
        if ok then
            table.insert(result, "所有城市已成长")
        else
            table.insert(result, "成长失败: " .. tostring(err))
        end
    else
        table.insert(result, "错误: g_CityRankManager 不存在")
    end
    return table.concat(result, "\\n")
    """
    return execute_lua_safe(lua)


def get_city_info():
    """获取城市信息"""
    lua = """
    local result = {}
    if g_CityRankManager then
        if g_CityRankManager.GetAllCities then
            local cities = g_CityRankManager:GetAllCities()
            if cities then
                local count = 0
                for _ in pairs(cities) do count = count + 1 end
                table.insert(result, "城市总数: " .. count)
            end
        end
    end
    if g_FamousCityMgr then
        table.insert(result, "名城系统: 已加载")
    end
    return table.concat(result, "\\n")
    """
    return execute_lua_safe(lua)


# ============================================================
# 风水系统
# ============================================================

def gm_show_block_fengshui():
    """GM命令：显示选择地块风水"""
    lua = """
    local result = {}
    if g_LFengshuiManager then
        local ok, err = pcall(function()
            g_LFengshuiManager:_GM_ShowSelectBlockFs()
        end)
        if ok then
            table.insert(result, "已显示选择地块风水（GM命令）")
        else
            table.insert(result, "执行失败: " .. tostring(err))
        end
    else
        table.insert(result, "错误: g_LFengshuiManager 不存在")
    end
    return table.concat(result, "\\n")
    """
    return execute_lua_safe(lua)


def cast_super_fengshui_skill():
    """施放超级风水技能"""
    lua = """
    local result = {}
    if g_LFengshuiManager then
        local ok, err = pcall(function()
            g_LFengshuiManager:_CastSuperFsSkill()
        end)
        if ok then
            table.insert(result, "超级风水技能已施放")
        else
            table.insert(result, "施放失败: " .. tostring(err))
        end
    else
        table.insert(result, "错误: g_LFengshuiManager 不存在")
    end
    return table.concat(result, "\\n")
    """
    return execute_lua_safe(lua)


def get_fengshui_info():
    """获取风水信息"""
    lua = """
    local result = {}
    if g_LFengshuiManager then
        table.insert(result, "手动解锁: " .. tostring(g_LFengshuiManager.bManualUnlock or "未知"))
    end
    return table.concat(result, "\\n")
    """
    return execute_lua_safe(lua)


# ============================================================
# 核心数值（直接赋值）
# ============================================================

def set_boom_level(level):
    """设置鸿业等级

    Args:
        level: 等级（1-14或更高）
    """
    lua = """
    local result = {}
    if g_camp then
        g_camp.boomLevel = %d
        table.insert(result, "鸿业等级已设为: %d")
    else
        table.insert(result, "错误: g_camp 不存在")
    end
    return table.concat(result, "\\n")
    """ % (level, level)
    return execute_lua_safe(lua)


def set_happiness(score):
    """设置幸福度分数

    Args:
        score: 分数（0-100或更高）
    """
    lua = """
    local result = {}
    if g_camp then
        g_camp.m_nHappinessScore = %d
        table.insert(result, "幸福度分数已设为: %d")
    else
        table.insert(result, "错误: g_camp 不存在")
    end
    return table.concat(result, "\\n")
    """ % (score, score)
    return execute_lua_safe(lua)


def set_creativity(value):
    """设置创造力

    Args:
        value: 创造力值
    """
    lua = """
    local result = {}
    if g_camp then
        g_camp.creativity = %d
        table.insert(result, "创造力已设为: %d")
    else
        table.insert(result, "错误: g_camp 不存在")
    end
    return table.concat(result, "\\n")
    """ % (value, value)
    return execute_lua_safe(lua)


def set_money(value):
    """设置金钱

    Args:
        value: 金钱值
    """
    lua = """
    local result = {}
    if g_camp then
        g_camp.m_nMoneyRecord = %d
        table.insert(result, "金钱已设为: %d")
    else
        table.insert(result, "错误: g_camp 不存在")
    end
    return table.concat(result, "\\n")
    """ % (value, value)
    return execute_lua_safe(lua)


def set_prosperity(value):
    """设置昌盛值

    Args:
        value: 昌盛值
    """
    lua = """
    local result = {}
    if g_camp then
        g_camp.prosperity = %d
        table.insert(result, "昌盛值已设为: %d")
    else
        table.insert(result, "错误: g_camp 不存在")
    end
    return table.concat(result, "\\n")
    """ % (value, value)
    return execute_lua_safe(lua)


def get_core_stats():
    """获取核心数值状态"""
    lua = """
    local result = {}
    if g_camp then
        table.insert(result, "鸿业等级: " .. tostring(g_camp.boomLevel or "未知"))
        table.insert(result, "昌盛值: " .. tostring(g_camp.prosperity or "未知"))
        table.insert(result, "昌盛等级: " .. tostring(g_camp.prosperityLevel or "未知"))
        table.insert(result, "幸福度分数: " .. tostring(g_camp.m_nHappinessScore or "未知"))
        table.insert(result, "幸福度等级: " .. tostring(g_camp.m_nHappinessLevel or "未知"))
        table.insert(result, "创造力: " .. tostring(g_camp.creativity or "未知"))
        table.insert(result, "创造力上限: " .. tostring(g_camp.creativityLimit or "未知"))
        table.insert(result, "金钱: " .. tostring(g_camp.m_nMoneyRecord or "未知"))
        table.insert(result, "活跃灾害: " .. tostring(g_camp.m_nActiveDisasters or "未知"))
        table.insert(result, "已过天数: " .. tostring(g_camp.m_nPassedDays or "未知"))
    else
        table.insert(result, "错误: g_camp 不存在")
    end
    return table.concat(result, "\\n")
    """
    return execute_lua_safe(lua)


# ============================================================
# 一键全开（所有作弊功能）
# ============================================================

def enable_all_cheats():
    """一键开启所有作弊功能"""
    results = []

    # 天赋
    ok, msg = unlock_all_talents()
    results.append(f"[天赋] {msg}")

    ok, msg = max_all_talents()
    results.append(f"[天赋] {msg}")

    # 成就
    ok, msg = unlock_all_achievements()
    results.append(f"[成就] {msg}")

    # 灾害
    ok, msg = close_all_disasters()
    results.append(f"[灾害] {msg}")

    # 时间
    ok, msg = fix_season(True)
    results.append(f"[时间] {msg}")

    # 天气
    ok, msg = fix_weather(True)
    results.append(f"[天气] {msg}")

    # 核心数值
    ok, msg = set_boom_level(14)
    results.append(f"[核心] {msg}")

    ok, msg = set_happiness(100)
    results.append(f"[核心] {msg}")

    ok, msg = set_creativity(99999)
    results.append(f"[核心] {msg}")

    ok, msg = set_money(99999999)
    results.append(f"[核心] {msg}")

    return True, "\\n".join(results)
