"""
woldvein Trainer v0.5.0 - 离线化模块（绕开金山 XG SDK 渠道登录）

功能说明：
    让《平野孤鸿》在**完全没有 Steam** 的情况下启动，并以本地离线账号 `offlineuser`
    直接进入主菜单。属于**启动前配置**，与 Lua 注入（运行期改内存）是两条独立通道。

两层方案，缺一不可（顺序也不能反）：
    ① Lua 散文件覆盖 —— 把 `LXGAgentManager:TryLogin()` 短路，登录根本不走 SDK。
       这一层保证伪造票据永远不会被送到服务器。
    ② 本地 steam_api64.dll 模拟器 —— `SteamAPI_RestartAppIfNecessary` 返回 0，
       让游戏不再顺着 `steam://run/2656540` 去唤醒 Steam 客户端。

    只做 ② 不做 ① 的后果（已实测）：伪造票据被送去金山服务器校验，
    服务器判定为假并下发 toast「第三方验证过期，请重启后再试」。
    该文案在 exe / 本地配置 / 所有 lua 里都搜不到，100% 由服务器下发。

为什么散文件能覆盖 pak（实证方法）：
    日志里 `user init` 的行号会随部署文件内容变化（pak 版 173 行，
    往文件头插 2 行后变 175 行），说明游戏确实优先加载
    `游戏根\\sim_common\\script\\...` 下的散文件。

启动工作目录必须是 bin64（踩过的坑）：
    用 `start /D "<游戏根>"` 启动 → 秒退，core 日志只有 98 字节；
    用 `start /D "<游戏根>\\bin64"` 或双击 bin64 里的 exe → 正常。

核心函数：
    status()            读一次当前状态（破解是否装好 / 游戏与 Steam 是否在跑）
    install()           安装（自动备份原 dll 与 config.cfg）
    uninstall()         卸载（还原 dll 与 config.cfg，删散文件）
    launch()            以 bin64 为工作目录、脱离父进程启动游戏
    last_login()        解析最新 core 日志，看本次登录到底是谁
    payload_ready()     payload 是否随包带齐

技术要点：
    - 所有公开 API **不抛异常**，失败返回 `{"ok": False, "msg": ...}`，UI 可直接消费
    - dll 替换会失败于「文件被占用」，此时给出「请先关闭游戏」的明确提示
    - config.cfg 只在没有 `publish=0` 时追加一行，卸载时只删我们自己加的那一行
    - payload 随包放 `assets/offline_crack/`，不联网、不依赖 pojieexe 目录
"""
import os
import io
import re
import time
import shutil
import subprocess

try:
    import ctypes
except Exception:      # 非 Windows 或受限环境
    ctypes = None

try:
    import platform
except Exception:
    platform = None

from .logger import log, log_success, log_error, log_warning
from .constants import (
    DEFAULT_GAME_PATH, GAME_EXE_REL, SIM_COMMON_REL, PROJECT_ROOT,
)

# ---------------------------------------------------------------- 常量
MODULE_VERSION = "1.0.0"

# payload（随包携带）
PAYLOAD_DIRNAME = "offline_crack"
EMU_DLL_NAME = "steam_api64.dll"
EMU_DLL_BACKUP = "steam_api64.dll.orig"

# 期望装到游戏里的散文件（相对 payload 根 / 相对游戏根，路径一致）
LUA_PAYLOADS = [
    "sim_common/script/core/xgagent/xgagent_manager.lua",
    "sim_common/script/core/archive/archive_mgr.lua",
    "sim_common/script/gameplay/game_state/welcome_state.lua",
    "sim_common/script/provider/common_provider.lua",
]
# 这四个里，决定「破解是否生效」的关键文件
LUA_CORE = "sim_common/script/core/xgagent/xgagent_manager.lua"

CONFIG_REL = "configs/config.cfg"
CONFIG_BACKUP_REL = "configs/config.cfg.offline_bak"
PUBLISH_LINE = "publish=0"

GAME_PROCESS = "BalladsOfHongye.exe"
STEAM_PROCESS = "steam.exe"

# 已验证的 payload 指纹（用于 status 里提示「payload 与验证过的版本一致」）
KNOWN_MD5 = {
    "steam_api64.dll": "e00311beb969c907d6710d384bf43ca0",
    "sim_common/script/core/xgagent/xgagent_manager.lua": "4ac58ef38e69025f0ce719ce01d998c0",
    "sim_common/script/provider/common_provider.lua": "e41d43f354df85e7407d48696233b402",
    "sim_common/script/gameplay/game_state/welcome_state.lua": "7058c90d2451a43e401b6b1076dc7ab2",
}


def _md5(path):
    import hashlib
    h = hashlib.md5()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None


def _fail(msg, **extra):
    d = {"ok": False, "msg": msg}
    d.update(extra)
    return d


# ---------------------------------------------------------------- 路径
def payload_dir():
    """随包 payload 目录（assets/offline_crack）"""
    return os.path.join(PROJECT_ROOT, "assets", PAYLOAD_DIRNAME)


def payload_ready():
    """payload 是否齐备。返回 (bool, 说明)"""
    p = payload_dir()
    if not os.path.isdir(p):
        return False, "payload 目录不存在：%s" % p
    miss = []
    if not os.path.isfile(os.path.join(p, EMU_DLL_NAME)):
        miss.append(EMU_DLL_NAME)
    for rel in LUA_PAYLOADS:
        if not os.path.isfile(os.path.join(p, rel)):
            miss.append(rel)
    if miss:
        return False, "payload 缺 %d 个文件：%s" % (len(miss), ", ".join(os.path.basename(m) for m in miss))
    return True, "payload 齐备（模拟器 dll + %d 个 lua 散文件）" % len(LUA_PAYLOADS)


def resolve_game_path(game_path=None):
    """优先入参，其次 config.json，最后 constants 默认值"""
    if game_path:
        return game_path
    try:
        from .config import load_config
        p = (load_config() or {}).get("game_path")
        if p and os.path.isdir(p):
            return p
    except Exception:
        pass
    return DEFAULT_GAME_PATH


def _bin_dir(game_path):
    return os.path.join(game_path, os.path.dirname(GAME_EXE_REL))


# ---------------------------------------------------------------- 进程检测
def _running_names():
    """返回当前正在跑的进程名集合（小写）。不依赖第三方库。"""
    if ctypes is None or platform is None or platform.system() != "Windows":
        return set()
    names = set()
    try:
        psapi = ctypes.windll.psapi
        kernel = ctypes.windll.kernel32
        arr = (ctypes.c_ulong * 8192)()
        needed = ctypes.c_ulong()
        if not psapi.EnumProcesses(ctypes.byref(arr), ctypes.sizeof(arr), ctypes.byref(needed)):
            return names
        count = min(needed.value // ctypes.sizeof(ctypes.c_ulong), 8192)
        PROCESS_QUERY_INFORMATION = 0x0400
        PROCESS_VM_READ = 0x0010
        for i in range(count):
            pid = arr[i]
            if not pid:
                continue
            h = kernel.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
            if not h:
                continue
            try:
                buf = (ctypes.c_char * 260)()
                if psapi.GetModuleBaseNameA(h, None, buf, 260):
                    names.add(buf.value.decode("gbk", "ignore").lower())
            finally:
                kernel.CloseHandle(h)
    except Exception:
        pass
    return names


def is_running(process_name):
    return process_name.lower() in _running_names()


def game_running():
    return is_running(GAME_PROCESS)


def steam_running():
    return is_running(STEAM_PROCESS)


# ---------------------------------------------------------------- 状态
def status(game_path=None):
    """
    读一次当前状态。永远返回 dict，ok=True 表示「查询成功」（不代表已安装）。
    """
    gp = resolve_game_path(game_path)
    out = {
        "ok": True,
        "game_path": gp,
        "installed": False,
        "payload_ready": False,
        "payload_msg": "",
        "exe_exists": False,
        "lua_present": [],
        "lua_missing": [],
        "dll_state": "missing",     # emulator / original / unknown / missing
        "dll_backup": False,
        "config_exists": False,
        "publish_zero": False,
        "game_running": False,
        "steam_running": False,
        "summary": "",
        "msg": "",
    }
    try:
        okp, pmsg = payload_ready()
        out["payload_ready"], out["payload_msg"] = okp, pmsg

        exe = os.path.join(gp, GAME_EXE_REL)
        out["exe_exists"] = os.path.isfile(exe)
        if not out["exe_exists"]:
            out["msg"] = "找不到游戏主程序：%s" % exe
            out["summary"] = "游戏路径无效"
            return out

        # 散文件
        for rel in LUA_PAYLOADS:
            (out["lua_present"] if os.path.isfile(os.path.join(gp, rel)) else out["lua_missing"]).append(rel)

        # dll
        dll = os.path.join(_bin_dir(gp), EMU_DLL_NAME)
        bak = os.path.join(_bin_dir(gp), EMU_DLL_BACKUP)
        out["dll_backup"] = os.path.isfile(bak)
        if os.path.isfile(dll):
            m = _md5(dll)
            if m == KNOWN_MD5.get(EMU_DLL_NAME):
                out["dll_state"] = "emulator"
            elif out["dll_backup"] and m == _md5(bak):
                out["dll_state"] = "original"
            else:
                out["dll_state"] = "unknown"
        else:
            out["dll_state"] = "missing"

        # config
        cfg = os.path.join(gp, CONFIG_REL)
        out["config_exists"] = os.path.isfile(cfg)
        if out["config_exists"]:
            try:
                with io.open(cfg, encoding="utf-8", errors="ignore") as f:
                    txt = f.read()
                out["publish_zero"] = bool(re.search(r"^\s*publish\s*=\s*0\s*$", txt, re.M))
            except Exception:
                pass

        out["game_running"] = game_running()
        out["steam_running"] = steam_running()

        core_ok = os.path.isfile(os.path.join(gp, LUA_CORE))
        out["installed"] = bool(core_ok and out["dll_state"] == "emulator")
        out["summary"] = "已安装（离线可用）" if out["installed"] else "未安装"
        out["msg"] = "查询完成"
        return out
    except Exception as e:
        out["ok"] = False
        out["msg"] = "%s: %s" % (type(e).__name__, e)
        return out


# ---------------------------------------------------------------- 安装 / 卸载
def _ensure_dir(path):
    d = os.path.dirname(path)
    if d and not os.path.isdir(d):
        os.makedirs(d, exist_ok=True)


def _backup_dll(game_path):
    """备份原 dll。已存在备份则跳过；当前已是模拟器则拒绝备份。"""
    src = os.path.join(_bin_dir(game_path), EMU_DLL_NAME)
    dst = os.path.join(_bin_dir(game_path), EMU_DLL_BACKUP)
    if os.path.isfile(dst):
        return True, "备份已存在，跳过"
    if not os.path.isfile(src):
        return False, "原 dll 不存在，无从备份"
    try:
        if os.path.getsize(src) == os.path.getsize(os.path.join(payload_dir(), EMU_DLL_NAME)):
            return False, "当前 dll 看起来已经是模拟器，拒绝把它备份成原件"
        shutil.copy2(src, dst)
        return True, "已备份原 dll -> %s" % EMU_DLL_BACKUP
    except Exception as e:
        return False, "备份失败：%s" % e


def _set_publish(game_path, enable=True):
    """在 config.cfg 的 [Misc] 段加/删 publish=0。只动这一行。"""
    cfg = os.path.join(game_path, CONFIG_REL)
    if not os.path.isfile(cfg):
        return False, "config.cfg 不存在：%s" % cfg
    try:
        with open(cfg, "rb") as f:
            raw = f.read()
        txt = raw.decode("utf-8", errors="ignore")
        has = bool(re.search(r"^\s*publish\s*=\s*0\s*$", txt, re.M))
        if enable and not has:
            bak = os.path.join(game_path, CONFIG_BACKUP_REL)
            if not os.path.isfile(bak):
                with open(bak, "wb") as f:
                    f.write(raw)
            nl = "\r\n" if b"\r\n" in raw else "\n"
            # 整行连同行尾一起捕获，替换时原样拼回，避免把 CRLF 拆成 \r\r\n
            pat = re.compile(r"(^[ \t]*channel[ \t]*=[ \t]*\d+[ \t]*\r?\n)", re.M)
            if pat.search(txt):
                txt = pat.sub(lambda m: m.group(1) + PUBLISH_LINE + nl, txt, count=1)
            else:
                txt = txt.rstrip("\r\n") + nl + PUBLISH_LINE + nl
            with open(cfg, "wb") as f:
                f.write(txt.encode("utf-8"))
            return True, "已写入 %s" % PUBLISH_LINE
        if (not enable) and has:
            txt = re.sub(r"^[ \t]*publish[ \t]*=[ \t]*0[ \t]*\r?\n", "", txt, flags=re.M)
            with open(cfg, "wb") as f:
                f.write(txt.encode("utf-8"))
            return True, "已移除 %s" % PUBLISH_LINE
        return True, "无需改动"
    except Exception as e:
        return False, "改 config.cfg 失败（游戏运行中可能被占用）：%s" % e


def install(game_path=None, with_publish=True):
    """安装离线破解。返回 dict。"""
    gp = resolve_game_path(game_path)
    try:
        okp, pmsg = payload_ready()
        if not okp:
            return _fail(pmsg)
        exe = os.path.join(gp, GAME_EXE_REL)
        if not os.path.isfile(exe):
            return _fail("找不到游戏主程序：%s" % exe)
        if game_running():
            return _fail("游戏正在运行，dll 会被占用 —— 请先关闭游戏再安装。")

        steps = []
        ok, m = _backup_dll(gp)
        steps.append(m)
        if not ok:
            return _fail(m, steps=steps)

        # dll
        src = os.path.join(payload_dir(), EMU_DLL_NAME)
        dst = os.path.join(_bin_dir(gp), EMU_DLL_NAME)
        try:
            shutil.copy2(src, dst)
            steps.append("已安装模拟器 steam_api64.dll")
        except Exception as e:
            return _fail("写入 dll 失败（被占用？）：%s" % e, steps=steps)

        # lua 散文件
        n = 0
        for rel in LUA_PAYLOADS:
            s = os.path.join(payload_dir(), rel)
            d = os.path.join(gp, rel)
            try:
                _ensure_dir(d)
                shutil.copy2(s, d)
                n += 1
            except Exception as e:
                return _fail("写入 %s 失败：%s" % (os.path.basename(rel), e), steps=steps)
        steps.append("已部署 %d 个 lua 散文件" % n)

        if with_publish:
            ok, m = _set_publish(gp, True)
            steps.append(m)

        log_success("[离线] 安装完成：%s" % gp)
        return {"ok": True, "msg": "离线化已安装，用「启动游戏（离线）」进入。", "steps": steps}
    except Exception as e:
        return _fail("%s: %s" % (type(e).__name__, e))


def uninstall(game_path=None):
    """卸载并还原。返回 dict。"""
    gp = resolve_game_path(game_path)
    try:
        if game_running():
            return _fail("游戏正在运行，dll 会被占用 —— 请先关闭游戏再卸载。")
        steps = []

        # 还原 dll
        dll = os.path.join(_bin_dir(gp), EMU_DLL_NAME)
        bak = os.path.join(_bin_dir(gp), EMU_DLL_BACKUP)
        if os.path.isfile(bak):
            try:
                shutil.copy2(bak, dll)
                steps.append("已还原原版 steam_api64.dll")
            except Exception as e:
                steps.append("还原 dll 失败（被占用？）：%s" % e)
        else:
            steps.append("无 dll 备份，跳过还原")

        # 删散文件（只删我们部署的那 4 个）
        n = 0
        for rel in LUA_PAYLOADS:
            p = os.path.join(gp, rel)
            if os.path.isfile(p):
                try:
                    os.remove(p)
                    n += 1
                except Exception:
                    pass
        steps.append("已删除 %d 个 lua 散文件" % n)

        # 清掉空目录（只碰 sim_common 这一棵）
        root = os.path.join(gp, SIM_COMMON_REL)
        if os.path.isdir(root):
            for cur, dirs, files in os.walk(root, topdown=False):
                if cur == root:
                    continue
                try:
                    if not os.listdir(cur):
                        os.rmdir(cur)
                except Exception:
                    pass
            try:
                if not os.listdir(root):
                    os.rmdir(root)
            except Exception:
                pass
        steps.append("已清理空的 sim_common 目录")

        ok, m = _set_publish(gp, False)
        steps.append(m)

        log_success("[离线] 已卸载并还原：%s" % gp)
        return {"ok": True, "msg": "已还原为纯净游戏（可从 Steam 正常启动）。", "steps": steps}
    except Exception as e:
        return _fail("%s: %s" % (type(e).__name__, e))


# ---------------------------------------------------------------- 启动
def launch(game_path=None):
    """
    以 bin64 为工作目录、脱离父进程启动游戏。
    工作目录必须是 bin64 —— 用游戏根目录启动会秒退（core 日志只有 98 字节）。
    """
    gp = resolve_game_path(game_path)
    try:
        exe = os.path.join(gp, GAME_EXE_REL)
        if not os.path.isfile(exe):
            return _fail("找不到游戏主程序：%s" % exe)
        if game_running():
            return _fail("游戏已经在运行了。")
        cwd = _bin_dir(gp)
        flags = 0
        if os.name == "nt":
            flags = 0x00000008 | 0x00000200   # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
        p = subprocess.Popen([exe], cwd=cwd, close_fds=True, creationflags=flags)
        log_success("[离线] 已启动游戏，pid=%s，cwd=%s" % (p.pid, cwd))
        return {"ok": True, "pid": p.pid, "msg": "已启动（pid=%s）。Steam 不会被唤醒。" % p.pid}
    except Exception as e:
        return _fail("%s: %s" % (type(e).__name__, e))


def kill_game():
    """关掉游戏进程（安装/卸载前用）。"""
    try:
        r = subprocess.run(["taskkill", "/F", "/IM", GAME_PROCESS],
                           capture_output=True, text=True, timeout=30)
        return {"ok": True, "msg": "已尝试结束 %s" % GAME_PROCESS, "raw": (r.stdout or "")[:200]}
    except Exception as e:
        return _fail("%s: %s" % (type(e).__name__, e))


# ---------------------------------------------------------------- 登录校验
def _newest_core_log(game_path):
    """找最新一份 logs/core/**/core_*.log"""
    base = os.path.join(game_path, "logs", "core")
    if not os.path.isdir(base):
        return None
    best, best_t = None, -1.0
    for cur, _dirs, files in os.walk(base):
        for f in files:
            if not (f.startswith("core_") and f.endswith(".log")):
                continue
            p = os.path.join(cur, f)
            try:
                t = os.path.getmtime(p)
            except Exception:
                continue
            if t > best_t:
                best, best_t = p, t
    return best


def last_login(game_path=None):
    """
    解析最新 core 日志，看本次登录结果。
    返回 {ok, found, login, username, account, online, expired_toast, sdk_login, log}
    """
    gp = resolve_game_path(game_path)
    out = {"ok": True, "found": False, "login": None, "username": None, "account": None,
           "online": None, "expired_toast": False, "sdk_login": False, "log": None, "msg": "无日志"}
    try:
        p = _newest_core_log(gp)
        if not p:
            return out
        out["log"] = os.path.basename(p)
        with io.open(p, encoding="utf-8", errors="ignore") as f:
            try:
                f.seek(max(0, os.path.getsize(p) - 65536))
            except Exception:
                pass
            tail = f.read()
        m = re.search(r"Login callback,\s*login:(\w+)\s*username:([^,]*),\s*account:([^,]*),\s*online:(\w+)", tail)
        if m:
            out.update(found=True, login=(m.group(1) == "true"), username=m.group(2).strip(),
                       account=m.group(3).strip(), online=(m.group(4) == "true"),
                       msg="已读到登录回调")
        else:
            out["msg"] = "日志里还没有登录回调（游戏可能还在加载）"
        out["expired_toast"] = ("第三方验证过期" in tail) or ("重启后再试" in tail)
        out["sdk_login"] = "Start login by steam token" in tail
        return out
    except Exception as e:
        out.update(ok=False, msg="%s: %s" % (type(e).__name__, e))
        return out


def self_check(game_path=None):
    """模块自检：payload + 游戏路径 + 状态三项。返回 (通过数, 总数, 明细列表)"""
    items = []

    def add(name, fn):
        try:
            ok, detail = fn()
        except Exception as e:
            ok, detail = False, "%s: %s" % (type(e).__name__, e)
        items.append((bool(ok), name, detail))

    add("payload 齐备", lambda: (payload_ready()[0], payload_ready()[1]))
    add("游戏路径有效", lambda: (os.path.isfile(os.path.join(resolve_game_path(game_path), GAME_EXE_REL)),
                                 resolve_game_path(game_path)))
    add("状态可查询", lambda: (status(game_path)["ok"], status(game_path)["summary"]))
    add("登录日志可解析", lambda: (True, (last_login(game_path).get("msg") or "")))
    return sum(1 for ok, _, _ in items if ok), len(items), items


if __name__ == "__main__":
    n, t, items = self_check()
    for ok, name, detail in items:
        print("[%s] %s: %s" % ("PASS" if ok else "FAIL", name, detail))
    print("\n===== %d/%d 通过 =====" % (n, t))
