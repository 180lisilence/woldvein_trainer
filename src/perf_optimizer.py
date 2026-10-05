"""
woldvein Trainer v0.4.9 - 引擎性能优化模块

功能说明：
    针对《平野孤鸿》使用的西山居 KG3D 引擎，改写游戏 configs\\config.ini 里
    **出厂被锁死**的性能参数，并把隐藏开关打开。属于**启动前配置**（改完需重启游戏生效），
    与 Lua 注入（运行期改内存）是两条独立通道，互不依赖。

为什么需要这个模块（全部有二进制逆向证据）：
    KG3DEngineX64.dll 的 GetInt(section, key, default) 调用现场里，默认值明确写成：

        MinWorkSet=600           进程工作集被压到 600MB，常用页反复换出 -> 硬缺页卡顿
        MaxWorkSet=1400          上限 1400MB，16G+ 内存也吃不满
        NumCpuThread=1           多核机器上只给 1 条线程做 CPU 侧工作
        UseMultiThreadCull=0     可见性剔除不并行
        bMultiThreadLoadAnimation=0
        bEnableModelLod=0        模型 LOD 关闭，远景全是高模
        UseProgressMeshLOD=0

    另外有一个隐藏开关 bDisableDynamicScale，exe 在 0x371123 处用
    GetPrivateProfileIntA 从 [KG3DENGINE] 真实读取，但 config.ini 里**没有这一项**，
    于是引擎按默认 0 处理 = 动态分辨率缩放常开，负载一高画面就糊。

安全性前提（已验证）：
    没有任何模块对 configs\\config.ini 执行 WritePrivateProfileStringA，
    改值不会被游戏写回覆盖。有 Write 的只有 KG3DEngineDX11EX64.dll（点云/baked_hash ini）
    和 Adapter 的通用封装，与这里无关。

已知无效项（不要改，无人读取）：
    config.cfg 的 LogicFrame / RenderFrame —— DX11 模块里出现的 RenderFrame 全是函数名
    （StaticRenderFrame / PushRenderFrame / RenderFrameStruct），exe 里的是遥测指标名。
    ColorDepth / UseMultiThreadAni / NumMultiThreadAni / MDLRenderLimit 同为遗留字段。

核心函数：
    read_current()          读取当前生效值
    apply_profile()         应用某一档（自动备份，支持预演）
    restore()               一键回滚到备份
    set_gpu_preference()    注册表锁定高性能独显（双显卡笔记本必备）
    recommend_profile()     按本机硬件推荐档位
    is_game_running()       辅助判断是否需要重启才能生效

技术要点：
    - ini 写入为**字节级最小侵入**：按行切分并保留行尾符，latin-1 解码处理，
      保证注释/缩进/非 ASCII 字节一字不动
    - 备份索引记录在 perf_backup/_backup_index.json，多次改动共用同一时间戳批次
    - 所有公开 API 都不抛异常，失败返回带 "ok": False 的字典，便于 UI 直接消费
"""
import os
import json
import time
import shutil
import platform

try:
    import ctypes
except Exception:      # 非 Windows 或受限环境
    ctypes = None

from .logger import log, log_success, log_error, log_warning

try:
    from .constants import DEFAULT_GAME_PATH
except Exception:      # 单独导入本模块时的兜底
    DEFAULT_GAME_PATH = r"D:\steam\steamapps\common\BalladsOfHongye_CN"

try:
    from .config import load_config
except Exception:
    load_config = None

import threading

_print_lock = threading.Lock()


def _safe_print(*a):
    try:
        with _print_lock:
            print(*a)
    except Exception:
        pass


# ---------------------------------------------------------------- 常量
CONFIG_INI_REL = os.path.join("configs", "config.ini")
BACKUP_DIRNAME = "perf_backup"
BACKUP_INDEX_NAME = "_backup_index.json"

STATE_NAME = "_applied_state.json"
# 三档 profile。value 为 None 表示"由 dynamic 策略按本机硬件算出"。
# evidence 字段记录该项的逆向依据，直接展示给使用者。
PROFILES = {
    "safe": {
        "name": "safe",
        "display": "保守档",
        "desc": "只动零崩溃风险的纯增益项。画面不再被动态缩放压糊，远景纹理清晰度提升。",
        "changes": [
            {
                "section": "KG3DENGINE", "key": "bDisableDynamicScale", "value": "1",
                "label": "锁定原生分辨率",
                "evidence": "exe 0x371123 GetPrivateProfileIntA 读取，配置里缺失 -> 默认 0",
                "why": "关闭动态分辨率缩放，重载场景时画面不再变糊。",
                "risk": "无。代价是帧率波动不再被自动掩盖。",
            },
            {
                "section": "KG3DENGINE", "key": "MaxAnisotropy", "value": "16",
                "label": "16x 各向异性过滤",
                "evidence": "KG3DEngineX64.dll 出厂默认 1（等于关闭）",
                "why": "现代 GPU 上几乎零开销，显著改善斜视地面与远景贴图糊化。",
                "risk": "极低",
            },
            {
                "section": "KG3DENGINE", "key": "TripleBuffering", "value": "1",
                "label": "三重缓冲",
                "evidence": "KG3DEngineX64.dll 默认 0",
                "why": "平滑帧输出，减少突发掉帧。",
                "risk": "无。约增加 1 帧输入延迟。",
            },
        ],
    },
    "balanced": {
        "name": "balanced",
        "display": "均衡档（推荐）",
        "desc": "保守档基础上，放开被锁死的内存工作集与多线程开关。线程数与内存按本机硬件自动计算。",
        "changes": [
            {
                "section": "KG3DENGINE", "key": "bDisableDynamicScale", "value": "1",
                "label": "锁定原生分辨率",
                "evidence": "exe 0x371123 GetPrivateProfileIntA 读取",
                "why": "不让动态缩放偷偷降分辨率。",
                "risk": "无",
            },
            {
                "section": "KG3DENGINE", "key": "MaxAnisotropy", "value": "16",
                "label": "16x 各向异性过滤",
                "evidence": "KG3DEngineX64.dll 默认 1",
                "why": "零开销换清晰度。",
                "risk": "极低",
            },
            {
                "section": "KG3DENGINE", "key": "TripleBuffering", "value": "1",
                "label": "三重缓冲",
                "evidence": "KG3DEngineX64.dll 默认 0",
                "why": "平滑帧输出。",
                "risk": "无",
            },
            {
                "section": "ENGINEOPTION", "key": "MinWorkSet", "value": None,
                "label": "内存常驻下限 (MB)",
                "evidence": "KG3DEngineX64.dll 0x128DC3 mov r9d,0x258 -> 出厂 600MB",
                "why": "工作集太小导致常用页被换出，走两步卡一下的根因。",
                "risk": "低。物理内存 <12GB 时自动下调。",
            },
            {
                "section": "ENGINEOPTION", "key": "MaxWorkSet", "value": None,
                "label": "内存常驻上限 (MB)",
                "evidence": "KG3DEngineX64.dll 0x128DEC mov r9d,0x578 -> 出厂 1400MB",
                "why": "允许引擎真正用上大内存，减少流加载抖动。",
                "risk": "低。后台程序多时自动下调。",
            },
            {
                "section": "KG3DENGINE", "key": "NumCpuThread", "value": None,
                "label": "CPU 处理线程数",
                "evidence": "KG3DEngineX64.dll 默认 1",
                "why": "多核机器上只给 1 条线程，主线程包揽全部 CPU 侧工作。",
                "risk": "低。默认取物理核心的一半。",
            },
            {
                "section": "ENGINEOPTION", "key": "UseMultiThreadCull", "value": "1",
                "label": "剔除多线程",
                "evidence": "KG3DEngineX64.dll 0x1289D0 xor r9d,r9d -> 默认 0",
                "why": "场景密集时剔除是纯 CPU 热点，并行化直接减负主线程。",
                "risk": "中低。若物件闪烁/凭空消失，改回 0。",
            },
            {
                "section": "ENGINEOPTION", "key": "bMultiThreadLoadAnimation", "value": "1",
                "label": "动画加载多线程",
                "evidence": "KG3DEngineX64.dll 0x128D4E xor r9d,r9d -> 默认 0",
                "why": "动画加载不再阻塞主线程。",
                "risk": "中低",
            },
            {
                "section": "ENGINEOPTION", "key": "UseMultiThreadLoad", "value": "1",
                "label": "资源加载多线程",
                "evidence": "KG3DEngineX64.dll 0x12899D xor r9d,r9d -> 默认 0",
                "why": "地图区块/模型加载不再卡顿主线程。",
                "risk": "中低。若贴图错乱，改回 0。",
            },
            {
                "section": "KG3DENGINE", "key": "bEnableModelLod", "value": "1",
                "label": "启用模型 LOD",
                "evidence": "KG3DEngineX64.dll 0x12827C xor r9d,r9d -> 默认 0",
                "why": "远景物件切低模，减少顶点与绘制提交压力。",
                "risk": "低。远景切换有轻微弹出感。",
            },
            {
                "section": "ENGINEOPTION", "key": "UseProgressMeshLOD", "value": "1",
                "label": "渐进式网格 LOD",
                "evidence": "KG3DEngineX64.dll 0x128977 xor r9d,r9d -> 默认 0",
                "why": "LOD 平滑过渡，取代一次性切换。",
                "risk": "低",
            },
            {
                "section": "KG3DENGINE", "key": "UseTerrainLOD", "value": "1",
                "label": "地形 LOD（固化）",
                "evidence": "默认已是 1，此处仅防止被其它流程改写",
                "why": "保持开启。",
                "risk": "无",
            },
        ],
    },
    "aggressive": {
        "name": "aggressive",
        "display": "极致档",
        "desc": "CPU 线程与内存常驻拉到本机上限。收益最大，但稳定性未经长时间验证，出问题立刻还原。",
        "changes": [
            {
                "section": "KG3DENGINE", "key": "bDisableDynamicScale", "value": "1",
                "label": "锁定原生分辨率", "evidence": "exe 0x371123", "why": "同均衡档。",
                "risk": "无",
            },
            {
                "section": "KG3DENGINE", "key": "MaxAnisotropy", "value": "16",
                "label": "16x 各向异性过滤", "evidence": "默认 1", "why": "同均衡档。",
                "risk": "极低",
            },
            {
                "section": "KG3DENGINE", "key": "TripleBuffering", "value": "1",
                "label": "三重缓冲", "evidence": "默认 0", "why": "同均衡档。",
                "risk": "无",
            },
            {
                "section": "ENGINEOPTION", "key": "MinWorkSet", "value": None,
                "label": "内存常驻下限 (MB)", "evidence": "出厂 600MB",
                "why": "极致取值，需保证后台不占内存。", "risk": "中",
            },
            {
                "section": "ENGINEOPTION", "key": "MaxWorkSet", "value": None,
                "label": "内存常驻上限 (MB)", "evidence": "出厂 1400MB",
                "why": "极致取值。", "risk": "中",
            },
            {
                "section": "KG3DENGINE", "key": "NumCpuThread", "value": None,
                "label": "CPU 处理线程数", "evidence": "默认 1",
                "why": "吃满全部物理核心。", "risk": "中。锁竞争可能反而拉低最低帧。",
            },
            {
                "section": "ENGINEOPTION", "key": "UseMultiThreadCull", "value": "1",
                "label": "剔除多线程", "evidence": "默认 0", "why": "同均衡档。", "risk": "中低",
            },
            {
                "section": "ENGINEOPTION", "key": "bMultiThreadLoadAnimation", "value": "1",
                "label": "动画加载多线程", "evidence": "默认 0", "why": "同均衡档。", "risk": "中低",
            },
            {
                "section": "ENGINEOPTION", "key": "UseMultiThreadLoad", "value": "1",
                "label": "资源加载多线程", "evidence": "默认 0", "why": "同均衡档。", "risk": "中低",
            },
            {
                "section": "KG3DENGINE", "key": "bEnableModelLod", "value": "1",
                "label": "启用模型 LOD", "evidence": "默认 0", "why": "同均衡档。", "risk": "低",
            },
            {
                "section": "ENGINEOPTION", "key": "UseProgressMeshLOD", "value": "1",
                "label": "渐进式网格 LOD", "evidence": "默认 0", "why": "同均衡档。", "risk": "低",
            },
            {
                "section": "KG3DENGINE", "key": "UseTerrainLOD", "value": "1",
                "label": "地形 LOD（固化）", "evidence": "默认 1", "why": "固化。", "risk": "无",
            },
        ],
    },
}

# UI 遍历顺序
PROFILE_ORDER = ["safe", "balanced", "aggressive"]


# ---------------------------------------------------------------- 硬件探测
def get_cpu_count():
    """返回逻辑 CPU 数（失败返回 4）"""
    try:
        n = os.cpu_count()
        return n if n and n > 0 else 4
    except Exception:
        return 4


def get_total_memory_gb():
    """返回物理内存总容量 (GB)。Windows 用 GlobalMemoryStatusEx，其它平台返回 0。"""
    if ctypes is None or platform.system() != "Windows":
        return 0.0
    try:
        class MEMSTAT(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]
        ms = MEMSTAT()
        ms.dwLength = ctypes.sizeof(MEMSTAT)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(ms))
        return round(ms.ullTotalPhys / (1024.0 ** 3), 1)
    except Exception:
        return 0.0


def _dynamic_value(key, profile_name):
    """
    对 value 为 None 的项，按本机硬件算出具体数值。

    策略：
        NumCpuThread   balanced -> ceil(logic/2) 上限 8   aggressive -> logic 上限 16
        MinWorkSet     balanced -> 物理内存的 1/12，钳制 [800, 3072]
                       aggressive -> 物理内存的 1/6，钳制 [1024, 6144]
        MaxWorkSet     balanced -> 物理内存的 1/4，钳制 [2048, 8192]
                       aggressive -> 物理内存的 2/5，钳制 [4096, 16384]
    内存未知时退回保守值。
    """
    logic = get_cpu_count()
    mem_gb = get_total_memory_gb()
    mem_mb = mem_gb * 1024.0
    aggressive = (profile_name == "aggressive")

    if key == "NumCpuThread":
        n = logic if aggressive else max(2, (logic + 1) // 2)
        return str(max(2, min(n, 16)))

    if mem_mb <= 0:
        # 探测失败，给保守值
        return {"MinWorkSet": "1024", "MaxWorkSet": "3072"}.get(key, "1024")

    if key == "MinWorkSet":
        v = mem_mb / (6.0 if aggressive else 12.0)
        return str(int(max(1024 if aggressive else 800, min(v, 6144 if aggressive else 3072))))

    if key == "MaxWorkSet":
        v = mem_mb * (0.4 if aggressive else 0.25)
        return str(int(max(4096 if aggressive else 2048, min(v, 16384 if aggressive else 8192))))

    return "1"


def recommend_profile():
    """
    按本机硬件推荐档位。

    返回：
        (profile_name, 理由字符串)
    """
    mem_gb = get_total_memory_gb()
    logic = get_cpu_count()
    if mem_gb >= 16 and logic >= 8:
        return "balanced", f"{logic} 线程 / {mem_gb}GB 内存，适合均衡档"
    if mem_gb >= 8:
        return "safe", f"内存 {mem_gb}GB 偏紧，先上保守档更稳妥"
    return "safe", "硬件信息探测不完整，保守起见用保守档"


# ---------------------------------------------------------------- 路径
def get_game_root():
    """
    取得游戏根目录。

    优先 config.json 的 game_path，其次 constants.DEFAULT_GAME_PATH。
    """
    try:
        if load_config is not None:
            cfg = load_config()
            p = cfg.get("game_path")
            if p and os.path.isdir(p):
                return p
    except Exception:
        pass
    return DEFAULT_GAME_PATH


def get_ini_path(game_root=None):
    return os.path.join(game_root or get_game_root(), CONFIG_INI_REL)


def get_backup_root(game_root=None):
    # 备份放在修改器自己的运行目录，避免污染游戏目录
    from .constants import runtime_config_dir
    try:
        base = runtime_config_dir()
    except Exception:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, BACKUP_DIRNAME)


# ---------------------------------------------------------------- ini 最小侵入编辑
def _split_lines_eol(raw: bytes):
    """按行切分并保留每行结尾符，返回 [(line_without_eol, eol_bytes), ...]"""
    out, i = [], 0
    n = len(raw)
    while i < n:
        j = raw.find(b"\n", i)
        if j < 0:
            out.append((raw[i:], b""))
            break
        line = raw[i:j]
        eol = b"\n"
        if line.endswith(b"\r"):
            line = line[:-1]
            eol = b"\r\n"
        out.append((line, eol))
        i = j + 1
    return out


def _join_lines(lines):
    return b"".join(line + eol for line, eol in lines)


def _match_section(line: bytes, want: bytes):
    s = line.strip()
    return s.startswith(b"[") and s.endswith(b"]") and s[1:-1].strip() == want


def _match_key(line: bytes, want: bytes):
    s = line.strip()
    if not s or s[:1] in (b";", b"#", b"/"):
        return False
    return b"=" in s and s.split(b"=", 1)[0].strip() == want


def _edit_ini(raw: bytes, section: str, key: str, value: str):
    """
    在 raw 里把 [section] 的 key 改成 value。

    返回：
        (new_bytes, old_value_or_None, action)
        action ∈ {"update", "insert", "append-section"}
    """
    lines = _split_lines_eol(raw)
    sec_b = section.encode("latin-1")
    key_b = key.encode("latin-1")
    val_b = value.encode("latin-1")

    cur_sec = None
    sec_end = None        # 目标段内最后一个有内容的行
    found = None
    old = None
    for i, (line, eol) in enumerate(lines):
        if _match_section(line, sec_b):
            cur_sec = sec_b
            sec_end = i
            continue
        s = line.strip()
        if s.startswith(b"[") and s.endswith(b"]"):
            cur_sec = s[1:-1].strip()
            continue
        if cur_sec == sec_b:
            if s or sec_end == i:
                sec_end = i
            if _match_key(line, key_b):
                found = i
                old = line.split(b"=", 1)[1].strip().decode("latin-1")

    if found is not None:
        line, eol = lines[found]
        head = line.split(b"=", 1)[0]
        lines[found] = (head + b"=" + val_b, eol)
        return _join_lines(lines), old, "update"

    if sec_end is not None:
        line, eol = lines[sec_end]
        if not eol:
            lines[sec_end] = (line, b"\r\n")
        lines.insert(sec_end + 1, (key_b + b"=" + val_b, lines[sec_end][1]))
        return _join_lines(lines), None, "insert"

    if lines and lines[-1][0].strip():
        lines.append((b"", b"\r\n"))
    lines.append((b"[" + sec_b + b"]", b"\r\n"))
    lines.append((key_b + b"=" + val_b, b"\r\n"))
    return _join_lines(lines), None, "append-section"


def read_ini_value(path, section, key):
    """读取 ini 里 [section] 的 key 值，不存在返回 None"""
    if not os.path.exists(path):
        return None
    try:
        with open(path, "rb") as f:
            raw = f.read()
    except Exception:
        return None
    cur = None
    for line in raw.split(b"\n"):
        s = line.strip()
        if not s or s[:1] in (b";", b"#"):
            continue
        if s.startswith(b"[") and s.endswith(b"]"):
            cur = s[1:-1].strip().decode("latin-1")
            continue
        if cur == section and b"=" in s:
            k, v = s.split(b"=", 1)
            if k.strip().decode("latin-1") == key:
                return v.strip().decode("latin-1")
    return None


# ---------------------------------------------------------------- 备份
def _load_index():
    p = os.path.join(get_backup_root(), BACKUP_INDEX_NAME)
    if os.path.exists(p):
        try:
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _save_index(idx):
    root = get_backup_root()
    os.makedirs(root, exist_ok=True)
    p = os.path.join(root, BACKUP_INDEX_NAME)
    try:
        with open(p, "w", encoding="utf-8") as f:
            json.dump(idx, f, ensure_ascii=False, indent=1)
    except Exception as e:
        log_error(f"备份索引写入失败: {e}")


def ensure_backup(game_root=None):
    """
    备份游戏 config.ini。已备份过则返回既有记录。

    返回：
        (ok, backup_path_or_None)
    """
    root = get_backup_root()
    ini = get_ini_path(game_root)
    if not os.path.exists(ini):
        return False, None
    idx = _load_index()
    if idx.get("path") and os.path.exists(idx["path"]):
        return True, idx["path"]
    try:
        ts = idx.get("ts") or time.strftime("%Y%m%d_%H%M%S")
        dst = os.path.join(root, ts, "config.ini")
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(ini, dst)
        idx["path"] = dst.replace("\\", "/")
        idx["ts"] = ts
        idx["origin_ini"] = ini
        idx["created"] = time.strftime("%Y-%m-%d %H:%M:%S")
        _save_index(idx)
        log_success(f"已备份原始配置 -> {dst}")
        return True, dst
    except Exception as e:
        log_error(f"备份失败: {e}")
        return False, None


def has_backup():
    idx = _load_index()
    return bool(idx.get("path") and os.path.exists(idx["path"]))


def backup_info():
    """返回备份信息字典，无备份时返回 None"""
    idx = _load_index()
    p = idx.get("path")
    if not p or not os.path.exists(p):
        return None
    return {
        "path": p.replace("/", os.sep),
        "created": idx.get("created", "未知"),
        "size": os.path.getsize(p),
    }


def restore(game_root=None):
    """
    一键还原到备份。

    返回：
        {"ok": bool, "msg": str}
    """
    idx = _load_index()
    p = idx.get("path")
    ini = get_ini_path(game_root)
    if not p or not os.path.exists(p):
        return {"ok": False, "msg": "没有找到备份，无需还原。"}
    try:
        shutil.copy2(p.replace("/", os.sep), ini)
        clear_state()
        log_success("配置已还原到备份版本")
        return {"ok": True, "msg": f"已还原。备份时间：{idx.get('created', '未知')}\n重启游戏后生效。"}
    except Exception as e:
        log_error(f"还原失败: {e}")
        return {"ok": False, "msg": f"还原失败：{e}"}


# ---------------------------------------------------------------- 应用状态
def _state_path():
    return os.path.join(get_backup_root(), STATE_NAME)


def load_state():
    """读取已应用档位的状态记录，无记录返回 {}"""
    p = _state_path()
    if not os.path.exists(p):
        return {}
    try:
        with open(p, "r", encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _save_state(profile_name, changes):
    """记录本次应用的档位与实际写入的键值"""
    try:
        root = get_backup_root()
        os.makedirs(root, exist_ok=True)
        written = {}
        for c in changes:
            written["%s.%s" % (c["section"], c["key"])] = str(c["new"])
        with open(_state_path(), "w", encoding="utf-8") as f:
            json.dump({
                "profile": profile_name,
                "written": written,
                "applied_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            }, f, ensure_ascii=False, indent=1)
    except Exception as e:
        log_warning(f"应用状态记录失败（不影响实际改动）: {e}")


def clear_state():
    """清除应用状态（还原后调用）"""
    try:
        p = _state_path()
        if os.path.exists(p):
            os.remove(p)
    except Exception:
        pass


# ---------------------------------------------------------------- 读当前值
def _iter_all_changes():
    """遍历三档涉及的全部 ( section, key )，去重"""
    seen, out = set(), []
    for name in PROFILE_ORDER:
        for c in PROFILES[name]["changes"]:
            sig = (c["section"], c["key"])
            if sig in seen:
                continue
            seen.add(sig)
            out.append(sig)
    return out


def read_current(game_root=None):
    """
    读取当前 config.ini 里所有优化相关项的现值。

    返回：
        {"ok": bool, "ini": str, "values": {(section,key): value}, "msg": str}
    """
    ini = get_ini_path(game_root)
    if not os.path.exists(ini):
        return {"ok": False, "ini": ini, "values": {},
                "msg": f"找不到配置文件：{ini}\n请先在设置里填写正确的游戏路径。"}
    vals = {}
    for sec, key in _iter_all_changes():
        vals[(sec, key)] = read_ini_value(ini, sec, key)
    return {"ok": True, "ini": ini, "values": vals, "msg": ""}


def current_profile(game_root=None):
    """
    判断当前应用的档位。

    优先读应用状态文件（精确）；状态文件缺失时（例如用别的方式改过配置）
    退化为按值比对，返回最接近的档位。

    返回：
        (profile_name_or_None, matched_count, total_count)
    """
    st = load_state()
    if st.get("profile"):
        # 状态在，但要确认配置没被外部改回：按当时写入的值复核
        cur = read_current(game_root)
        if cur["ok"]:
            written = st.get("written", {})
            n = t = 0
            for k, want in written.items():
                t += 1
                sec, _, key = k.partition(".")
                if str(cur["values"].get((sec, key))) == str(want):
                    n += 1
            return st["profile"], n, t
        return st["profile"], 0, 0

    cur = read_current(game_root)
    if not cur["ok"]:
        return None, 0, 0
    values = cur["values"]
    best, best_n, total = None, -1, 0
    for name in PROFILE_ORDER:
        n = tot = 0
        for c in PROFILES[name]["changes"]:
            tot += 1
            want = c["value"] or _dynamic_value(c["key"], name)
            have = values.get((c["section"], c["key"]))
            if str(have) == str(want):
                n += 1
        total = tot
        if n > best_n:
            best, best_n = name, n
    return best, best_n, total


# ---------------------------------------------------------------- 应用
def apply_profile(profile_name, game_root=None, dry_run=False, dynamic=True):
    """
    应用某一档优化配置。

    参数：
        profile_name: "safe" / "balanced" / "aggressive"
        game_root:    游戏根目录，None 时自动取
        dry_run:      True 只预演不落盘
        dynamic:      True 时对 value=None 的项按本机硬件算值

    返回：
        {
          "ok": bool, "profile": str, "dry_run": bool,
          "changes": [{"section","key","old","new","action","label","why"}...],
          "ini": str, "msg": str, "need_restart": bool
        }
    """
    if profile_name not in PROFILES:
        return {"ok": False, "msg": f"未知档位：{profile_name}", "changes": []}

    prof = PROFILES[profile_name]
    ini = get_ini_path(game_root)
    result = {"ok": False, "profile": profile_name, "dry_run": dry_run,
              "changes": [], "ini": ini, "msg": "", "need_restart": True}

    if not os.path.exists(ini):
        result["msg"] = f"找不到配置文件：{ini}"
        log_error(result["msg"])
        return result

    if not dry_run:
        ok, _ = ensure_backup(game_root)
        if not ok:
            result["msg"] = "备份失败，已中止（不会改动你的配置）。"
            log_error(result["msg"])
            return result

    try:
        with open(ini, "rb") as f:
            raw = f.read()
    except Exception as e:
        result["msg"] = f"读取配置失败：{e}"
        log_error(result["msg"])
        return result

    origin = raw
    for c in prof["changes"]:
        want = c["value"] if (c["value"] is not None or not dynamic) else _dynamic_value(c["key"], profile_name)
        new_raw, old, act = _edit_ini(raw, c["section"], c["key"], want)
        raw = new_raw
        result["changes"].append({
            "section": c["section"], "key": c["key"],
            "old": old, "new": want, "action": act,
            "label": c.get("label", c["key"]), "why": c.get("why", ""),
        })

    if raw == origin:
        result["ok"] = True
        result["msg"] = "所有项已是目标值，无需改动。"
        return result

    if dry_run:
        result["ok"] = True
        result["msg"] = "预演完成，未写入磁盘。"
        return result

    try:
        with open(ini, "wb") as f:
            f.write(raw)
    except Exception as e:
        result["msg"] = f"写入失败：{e}（备份未受影响）"
        log_error(result["msg"])
        return result

    n = len([c for c in result["changes"] if c["action"] != "update" or str(c["old"]) != str(c["new"])])
    log_success(f"已应用 {prof['display']}，改动 {n} 项")
    _save_state(profile_name, result["changes"])
    result["ok"] = True
    result["msg"] = (f"已写入 {n} 项改动。\n"
                     f"配置在启动时读取 —— 需要重启游戏才生效。")
    return result


def set_single(section, key, value, game_root=None):
    """
    单项改写（供 UI 的高级开关使用）。

    返回：
        {"ok": bool, "msg": str, "old": old_value}
    """
    ini = get_ini_path(game_root)
    if not os.path.exists(ini):
        return {"ok": False, "msg": f"找不到配置文件：{ini}", "old": None}
    ok, _ = ensure_backup(game_root)
    if not ok:
        return {"ok": False, "msg": "备份失败，已中止。", "old": None}
    try:
        with open(ini, "rb") as f:
            raw = f.read()
    except Exception as e:
        return {"ok": False, "msg": f"读取失败：{e}", "old": None}
    new_raw, old, act = _edit_ini(raw, section, key, str(value))
    try:
        with open(ini, "wb") as f:
            f.write(new_raw)
    except Exception as e:
        return {"ok": False, "msg": f"写入失败：{e}", "old": old}
    log_success(f"{section}.{key}: {old} -> {value} ({act})")
    _save_state("custom", [{
        "section": section, "key": key, "old": old, "new": value, "action": act,
        "label": key, "why": "单项调整",
    }])
    return {"ok": True, "msg": f"{key} 已设为 {value}，重启游戏生效。", "old": old}


# ---------------------------------------------------------------- Windows 侧优化
def set_gpu_preference(game_root=None, exe_rel=None):
    """
    注册表锁定高性能独显（双显卡笔记本最重要的一步）。

    写 HKCU\\Software\\Microsoft\\DirectX\\UserGpuPreferences
       键名 = 游戏 exe 完整路径，值 = "GpuPreference=2;"（2 = 高性能）

    返回：
        {"ok": bool, "msg": str}
    """
    if platform.system() != "Windows":
        return {"ok": False, "msg": "仅支持 Windows。"}
    try:
        import winreg
    except Exception as e:
        return {"ok": False, "msg": f"无法访问注册表：{e}"}

    try:
        from .constants import GAME_EXE_REL
    except Exception:
        GAME_EXE_REL = r"bin64\BalladsOfHongye.exe"
    exe_rel = exe_rel or GAME_EXE_REL
    exe = os.path.join(game_root or get_game_root(), exe_rel)

    key_path = r"Software\Microsoft\DirectX\UserGpuPreferences"
    try:
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_WRITE) as k:
            winreg.SetValueEx(k, exe, 0, winreg.REG_SZ, "GpuPreference=2;")
        log_success("已锁定高性能 GPU（重启生效）")
        return {"ok": True, "msg": f"已写入 GPU 偏好：\n{exe}\nGpuPreference=2（高性能）"}
    except Exception as e:
        log_error(f"GPU 偏好写入失败: {e}")
        return {"ok": False, "msg": f"写入失败：{e}\n可手动在「Windows 设置 → 显示 → 图形」里指定。"}


def disable_fullscreen_optimizations(game_root=None, exe_rel=None):
    """关闭 Windows 全屏优化。返回 {"ok": bool, "msg": str}"""
    if platform.system() != "Windows":
        return {"ok": False, "msg": "仅支持 Windows。"}
    try:
        import winreg
    except Exception as e:
        return {"ok": False, "msg": f"无法访问注册表：{e}"}
    try:
        from .constants import GAME_EXE_REL
    except Exception:
        GAME_EXE_REL = r"bin64\BalladsOfHongye.exe"
    exe = os.path.join(game_root or get_game_root(), exe_rel or GAME_EXE_REL)
    key_path = r"Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers"
    try:
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_WRITE) as k:
            winreg.SetValueEx(k, exe, 0, winreg.REG_SZ, "DISABLEDXMAXIMIZEDWINDOWEDMODE")
        log_success("已关闭全屏优化")
        return {"ok": True, "msg": "已关闭该程序的全屏优化。"}
    except Exception as e:
        return {"ok": False, "msg": f"写入失败：{e}"}


def is_game_running(process_names=None):
    """
    检测游戏进程是否在运行（用于提示「需要重启才生效」）。
    不依赖第三方库：Windows 走 ctypes EnumProcesses + 进程名比对，其它平台降级返回 False。
    """
    names = process_names or ["BalladsOfHongye.exe"]
    if ctypes is None or platform.system() != "Windows":
        return False
    try:
        psapi = ctypes.windll.psapi
        kernel = ctypes.windll.kernel32
        arr = (ctypes.c_ulong * 4096)()
        needed = ctypes.c_ulong()
        if not psapi.EnumProcesses(ctypes.byref(arr), ctypes.sizeof(arr), ctypes.byref(needed)):
            return False
        count = min(needed.value // ctypes.sizeof(ctypes.c_ulong), 4096)
        target = {n.lower() for n in names}
        for i in range(count):
            pid = arr[i]
            if not pid:
                continue
            h = kernel.OpenProcess(0x1000, False, pid)   # PROCESS_QUERY_LIMITED_INFORMATION
            if not h:
                continue
            try:
                buf = (ctypes.c_char * 260)()
                psapi.GetProcessImageFileNameA(h, buf, 260)
                name = buf.value.decode("latin-1", "ignore").split("\\")[-1]
                if name.lower() in target:
                    return True
            finally:
                kernel.CloseHandle(h)
    except Exception:
        pass
    return False


def hardware_summary():
    """返回一行本机硬件摘要，给 UI 显示"""
    try:
        _p = platform.processor() or ""
    except Exception:
        _p = ""
    cpu = _p.strip() or "未知处理器"
    return f"{cpu} | {get_cpu_count()} 线程 | 内存 {get_total_memory_gb() or '未知'} GB"


# ============================================================
# 模块自检
# ============================================================
def _selftest():
    """
    不碰真实游戏文件，只对内嵌的 ini 编辑器做正确性验证。

    返回：
        0 = 全部通过
    """
    print("=" * 72)
    print("perf_optimizer 自检")
    print("=" * 72)

    sample = (
        b"[KG3DENGINE]\r\n"
        b"MaxAnisotropy=1\r\n"
        b"NumCpuThread=1\r\n"
        b"\r\n"
        b"[ENGINEOPTION]\r\n"
        b"MinWorkSet=600\r\n"
        b"MaxWorkSet=1400\r\n"
        b"UseMultiThreadCull=0\r\n"
    )
    fails = []

    def check(name, cond, extra=""):
        print(("  [ OK ] " if cond else "  [FAIL] ") + name + ("  " + extra if extra else ""))
        if not cond:
            fails.append(name)

    # 1. update 已有键
    out, old, act = _edit_ini(sample, "KG3DENGINE", "MaxAnisotropy", "16")
    check("update 已有键保留格式", act == "update" and old == "1"
          and b"MaxAnisotropy=16\r\n" in out and b"NumCpuThread=1\r\n" in out)

    # 2. 段落递推正确（同名 key 不跨段覆盖）
    out2, old2, act2 = _edit_ini(sample, "ENGINEOPTION", "MinWorkSet", "2048")
    check("只改目标段的同名键", old2 == "600" and b"MinWorkSet=2048\r\n" in out2)

    # 3. 新增键插到段末，且用段本身的换行风格
    out3, old3, act3 = _edit_ini(sample, "KG3DENGINE", "bDisableDynamicScale", "1")
    check("insert 新键到段末", act3 == "insert" and b"bDisableDynamicScale=1\r\n" in out3)
    check("insert 不破坏后随段落", b"[ENGINEOPTION]\r\n" in out3)

    # 4. 段不存在时追加
    out4, _, act4 = _edit_ini(sample, "NEWSECTION", "Foo", "1")
    check("append-section", act4 == "append-section" and out4.rstrip().endswith(b"[NEWSECTION]\r\nFoo=1"))

    # 5. 字节级：除目标行外其它字节不变
    outs = _edit_ini(sample, "KG3DENGINE", "MaxAnisotropy", "16")[0]
    check("CRLF 数量守恒", outs.count(b"\r\n") == sample.count(b"\r\n") + 0)

    # 6. 注释行不被误判为 key
    sample2 = b"[S]\r\n;MaxAnisotropy=99\r\nMaxAnisotropy=1\r\n"
    ov = read_ini_value_from_bytes(sample2, "S", "MaxAnisotropy")
    check("跳过注释行", ov == "1", f"(读到 {ov})")

    # 7. 动态值在合理范围
    for prof in PROFILE_ORDER:
        for k in ("NumCpuThread", "MinWorkSet", "MaxWorkSet"):
            v = int(_dynamic_value(k, prof))
            if v <= 0:
                fails.append(f"dynamic {prof}.{k}={v}")
    check("动态值均为正整数", True)

    # 8. 读已知文件（若游戏在）
    info = read_current()
    if info["ok"]:
        p, n, t = current_profile()
        check(f"读取游戏配置 {n}/{t} 项匹配 {(p or '未应用')}", True)
    else:
        check("读取游戏配置（本机未安装，跳过）", True)

    print("-" * 72)
    hw = hardware_summary()
    rec, why = recommend_profile()
    print(f"  硬件: {hw}")
    print(f"  推荐档位: {rec}  ({why})")
    print(f"  建议值: NumCpuThread={_dynamic_value('NumCpuThread', rec)} "
          f"MinWorkSet={_dynamic_value('MinWorkSet', rec)} "
          f"MaxWorkSet={_dynamic_value('MaxWorkSet', rec)}")
    print("-" * 72)
    if fails:
        print(f"失败 {len(fails)} 项: {fails}")
        return 1
    print("全部通过")
    return 0


def read_ini_value_from_bytes(raw: bytes, section: str, key: str):
    """与 read_ini_value 同语义，但接受字节内容（自检用）"""
    cur = None
    for line in raw.split(b"\n"):
        s = line.strip()
        if not s or s[:1] in (b";", b"#"):
            continue
        if s.startswith(b"[") and s.endswith(b"]"):
            cur = s[1:-1].strip().decode("latin-1")
            continue
        if cur == section and b"=" in s:
            k, v = s.split(b"=", 1)
            if k.strip().decode("latin-1") == key:
                return v.strip().decode("latin-1")
    return None


if __name__ == "__main__":
    import sys as _sys
    _sys.exit(_selftest())
