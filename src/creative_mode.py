"""
woldvein Trainer v0.3 - 创造模式模块

功能说明：
    实现游戏的创造模式功能，包括鸿业满级、全建筑解锁、无限资源、无限制升级。
    通过执行Lua脚本在游戏进程内部修改游戏状态，关闭时尝试还原。

创造模式子选项（可独立开关）：
    max_boom              鸿业等级满级（14级）
    unlock_all_buildings  全建筑解锁（只显示最高等级建筑，隐藏低等级）
    infinite_resources    无限资源（建造不消耗资源）
    unlimited_upgrade     无限制升级（遍历g_functionType全部设为OPEN）
    road_bypass           道路连接豁免（行人不必经过道路，直接到达建筑）
    population_universal  人口不分类别（工人/匠人/学者通用）

核心设计：
    - _creative_mode_enabled：Python端状态标记
    - _creative_options：用户勾选的子选项
    - _apply_options_to_lua()：把选项写入Lua全局变量（g_cm_opt_*）
    - enable_creative_mode()：执行LUA_CREATIVE_ENABLE脚本
    - disable_creative_mode()：执行LUA_CREATIVE_DISABLE脚本，尝试还原

技术要点：
    - 开启前先把选项写入Lua全局变量，再执行启用脚本
    - 关闭时执行还原脚本，恢复所有原始状态（建筑卡片hook、功能状态等）
    - 所有操作通过execute_lua_safe执行，异常不崩溃
    - 启用/禁用脚本超时10秒（创造模式脚本较重，需要遍历建筑卡片）
    - 选项应用超时3秒，状态查询超时5秒
"""
from .lua_engine import execute_lua_safe, LUA_CREATIVE_ENABLE, LUA_CREATIVE_DISABLE, LUA_GET_STATUS, LUA_DIAGNOSE_UNLOCK
from . import advanced_tools
from .logger import log, log_success, log_error, log_warning
from .constants import BOOM_MAX_LEVEL

# Python端创造模式状态标记
# 注意：这只是Python端的状态，游戏内实际状态以Lua全局g_bCreativeMode为准
_creative_mode_enabled = False

# 创造模式子选项（默认全部启用）
# 用户在GUI中勾选/取消后，通过set_creative_options更新
_creative_options = {
    "max_boom": True,              # 鸿业等级满级
    "unlock_all_buildings": True,  # 全建筑解锁（只显示最高等级）
    "infinite_resources": True,    # 无限资源
    "unlimited_upgrade": True,     # 无限制升级
    "road_bypass": True,           # 道路连接豁免
    "population_universal": True,  # 人口不分类别
    "gm_flags": True,              # GM标志（快速建造/忽略地块/操作所有建筑）
    "no_disaster_damage": True,    # 建筑不受灾害伤害
    "no_disaster": True,           # 不触发灾害
}


def set_creative_options(options):
    """
    设置创造模式子选项。

    参数：
        options: 字典，包含要更新的选项（如 {"max_boom": False}）
                 只更新传入的键，未传入的键保持不变
    """
    global _creative_options
    _creative_options.update(options)


def _apply_options_to_lua():
    """
    把Python端的选项写入Lua全局变量。

    在执行创造模式启用脚本之前调用，让Lua脚本知道哪些子功能需要启用。
    写入的全局变量：
        g_cm_opt_max_boom
        g_cm_opt_unlock_buildings
        g_cm_opt_infinite_resources
        g_cm_opt_unlimited_upgrade
    """
    opts_lua = f"""
    g_cm_opt_max_boom = {'true' if _creative_options['max_boom'] else 'false'}
    g_cm_opt_unlock_buildings = {'true' if _creative_options['unlock_all_buildings'] else 'false'}
    g_cm_opt_infinite_resources = {'true' if _creative_options['infinite_resources'] else 'false'}
    g_cm_opt_unlimited_upgrade = {'true' if _creative_options['unlimited_upgrade'] else 'false'}
    g_cm_opt_road_bypass = {'true' if _creative_options['road_bypass'] else 'false'}
    g_cm_opt_population_universal = {'true' if _creative_options['population_universal'] else 'false'}
    g_cm_opt_gm_flags = {'true' if _creative_options['gm_flags'] else 'false'}
    g_cm_opt_no_disaster_damage = {'true' if _creative_options['no_disaster_damage'] else 'false'}
    g_cm_opt_no_disaster = {'true' if _creative_options['no_disaster'] else 'false'}
    return 1
    """
    execute_lua_safe(opts_lua, timeout=3.0)


def enable_creative_mode():
    """
    开启创造模式。

    处理流程：
        1. 把用户勾选的子选项写入Lua全局变量
        2. 执行LUA_CREATIVE_ENABLE脚本（10秒超时）
        3. 成功则更新Python端状态，输出各子功能启用日志
        4. 失败则输出错误和提示（需进入游戏场景）

    返回：
        True表示开启成功，False表示失败
    """
    global _creative_mode_enabled

    log("正在开启创造模式...")
    # 先把选项写入Lua，让启用脚本知道哪些子功能需要启用
    _apply_options_to_lua()
    success, result = execute_lua_safe(LUA_CREATIVE_ENABLE, timeout=10.0)

    if success and result > 0:
        _creative_mode_enabled = True
        log_success("创造模式已开启！")
        # 输出各子功能启用状态
        if _creative_options["max_boom"]:
            log_success(f"  ✓ 鸿业等级 = {BOOM_MAX_LEVEL}（满级）")
            # 鸿业满级时，同时完成所有城市品阶解锁条件（0/1 → 1/1）
            advanced_tools.complete_city_rank_conditions()
        if _creative_options["unlock_all_buildings"]:
            log_success("  ✓ 所有建筑已解锁")
        if _creative_options["infinite_resources"]:
            log_success("  ✓ 建造不消耗资源")
        if _creative_options["unlimited_upgrade"]:
            log_success("  ✓ 建筑升级无限制")
        return True
    else:
        log_error("创造模式开启失败")
        log_warning("请确保已进入游戏场景（g_camp已初始化）")
        return False


def disable_creative_mode():
    """
    关闭创造模式，恢复原版逻辑。

    执行LUA_CREATIVE_DISABLE脚本，还原所有修改：
        - 还原建筑卡片hook（SetUnlockState/GetUnlockState）
        - 还原功能状态（遍历g_functionType）
        - 还原资源消耗hook
        - 还原鸿业等级

    返回：
        True表示关闭成功，False表示失败
    """
    global _creative_mode_enabled

    log("正在关闭创造模式...")
    success, result = execute_lua_safe(LUA_CREATIVE_DISABLE, timeout=10.0)

    if success and result > 0:
        _creative_mode_enabled = False
        log_success("创造模式已关闭，游戏恢复原版逻辑")
        return True
    else:
        log_error("创造模式关闭失败")
        return False


def is_creative_mode_enabled():
    """
    获取创造模式状态（Python端标记）。

    注意：这只是Python端的状态标记，游戏内实际状态以Lua全局为准。
    用于GUI显示按钮状态和热键切换后的界面更新。
    """
    return _creative_mode_enabled


def get_game_status():
    """
    获取游戏当前状态（资源、等级等）。

    执行LUA_GET_STATUS脚本，返回JSON字符串，包含：
        - creative_mode: 创造模式标记
        - boom_level: 鸿业等级
        - money/mineral/wood/...: 9种资源当前值
        - happiness: 幸福度
        - card_count: 建筑卡片数

    返回：
        (success, result) 元组，result为JSON字符串
    """
    success, result = execute_lua_safe(LUA_GET_STATUS)
    return success, result


def toggle_creative_mode():
    """
    切换创造模式（开启→关闭，关闭→开启）。

    返回：
        enable_creative_mode()或disable_creative_mode()的返回值
        （True表示操作成功，False表示失败）
    """
    if _creative_mode_enabled:
        return disable_creative_mode()
    else:
        return enable_creative_mode()


def diagnose_unlock_status():
    """
    建筑解锁状态诊断。

    执行LUA_DIAGNOSE_UNLOCK脚本，返回详细的诊断报告，包括：
    - 全局建筑卡片统计（总数/已解锁/未解锁）
    - 天赋管理器状态和hook测试
    - 当前方案卡中的建筑解锁状态
    - 卡片方法hook测试
    - 创造模式hook状态

    返回：
        (success, result) 元组，result为诊断报告字符串
    """
    log("正在执行建筑解锁诊断...")
    success, result = execute_lua_safe(LUA_DIAGNOSE_UNLOCK, timeout=10.0)
    if success and result and result != -1:
        log_success("诊断完成")
        return True, result
    else:
        log_error("诊断失败")
        return False, "诊断失败，请确保已进入游戏场景"
