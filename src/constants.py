"""
woldvein Trainer v0.3 - 全局常量

集中存放**跨模块共享**的常量，杜绝散落各处的硬编码：
    - 游戏路径 / Steam AppID
    - 鸿业（城市品阶）上限
    - 成就 ID 扫描上限
    - 时间系统权威值
    - Lua 执行超时

注意：本模块不得 import 项目内其它模块（避免循环依赖）。
"""
import os
import sys

# ---------------------------------------------------------------- 版本（唯一版本源）
APP_NAME = "woldvein Trainer"
APP_VERSION = "0.4.9"

# ---------------------------------------------------------------- 游戏环境
STEAM_APP_ID = "2656540"
STEAM_RUN_URL = "steam://run/" + STEAM_APP_ID

# 游戏安装目录（默认值；运行时可被 config.json 的 game_path 覆盖）
DEFAULT_GAME_PATH = r"D:\steam\steamapps\common\BalladsOfHongye_CN"
# 游戏主程序（相对 game_path）
GAME_EXE_REL = r"bin64\BalladsOfHongye.exe"
# Lua 散文件目录（Mod 核心通道，相对 game_path）
SIM_COMMON_REL = "sim_common"

# ---------------------------------------------------------------- 项目路径
# src/ 的上一级 = 项目根目录
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST_DIR = os.path.join(PROJECT_ROOT, "dist")
LOGS_DIR = os.path.join(PROJECT_ROOT, "logs")


def runtime_config_dir():
    """运行期可写目录：统一用程序所在目录（D盘），不写C盘。"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return PROJECT_ROOT


# ---------------------------------------------------------------- 游戏数值
# 鸿业（城市品阶）上限兜底值；优先用 g_blocksLogicCfg:GetBoomLevelCfg() 读游戏配置
BOOM_MAX_LEVEL = 14
# 成就 ID 扫描上限（游戏成就 ID 实测 ≤ 100，留足余量）
ACHIEVEMENT_ID_SCAN_LIMIT = 400
# 单次跳天的安全上限（天；10 年）
MAX_SKIP_DAYS = 3600

# 时间系统权威值（define.DAY_TIME_REAL / define.DAY_TICK_COUNT）
DAY_TIME_REAL = 5
DAY_TICK_COUNT = 2
TICK_DELTA_BASE = float(DAY_TIME_REAL) / float(DAY_TICK_COUNT)   # = 2.5
# 倍速钳制范围
TIME_SPEED_MIN = 0.05
TIME_SPEED_MAX = 60.0

# 历法
DAYS_PER_MONTH = 30
MONTHS_PER_YEAR = 12
DAYS_PER_YEAR = DAYS_PER_MONTH * MONTHS_PER_YEAR   # 360
SECONDS_PER_DAY = 86400

# 一键增加资源/知名度 的默认数值
RESOURCE_ADD_AMOUNT = 1000000
FAME_ADD_AMOUNT = 10000

# ---------------------------------------------------------------- 执行
# execute_lua_safe 默认超时（秒）
LUA_TIMEOUT = 5.0
# 长耗时脚本（如一步到位的大批量操作）超时
LUA_TIMEOUT_LONG = 10.0
