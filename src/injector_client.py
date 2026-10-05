"""
woldvein_trainer v0.5.0 — 注入器客户端

修改器 **不再自己注入**。它只负责一件事：找到 v0.4.7 注入器，向它要一条通道。

    from src.injector_client import get_client
    client = get_client()
    client.ensure_injected()
    ok, res = client.execute("return g_camp ~= nil")

定位顺序：
    1) 环境变量 WOLDVEIN_INJECTOR_HOME
    2) 同级归集目录：trainers/injector/woldvein_injector0.4.7
    3) 本项目内嵌：woldvein_trainer0.4.9/vendor/woldvein_injector0.4.7

这样做的收益：注入器改 DLL、换通信协议、加绕检测都不需要动修改器一行代码，
只要 PROTOCOL_VERSION 不变。
"""
import os
import sys

from src.constants import APP_VERSION

REQUIRED_INJECTOR_VERSION = "0.4.7"
INJECTOR_DIR_NAME = "woldvein_injector0.4.7"

_client = None
_load_error = None


def _candidate_paths():
    """
    返回注入器的候选根目录，按优先级排列。

    打包（frozen / onefile）后 __file__ 指向 _MEIxxxx 临时目录，
    只按 __file__ 推断会全部落空 —— 所以额外按「exe 实际所在目录」逐级向上找
    trainers/injector/<name>，让它无论从工作区还是从拷贝出去的 dist 启动都能找到。
    """
    here = os.path.dirname(os.path.abspath(__file__))          # .../src
    trainer_root = os.path.dirname(here)                        # .../woldvein_trainer0.4.9
    paths = []

    env = os.environ.get("WOLDVEIN_INJECTOR_HOME")
    if env:
        paths.append(env)

    # 并列布局（本机实际目录结构）：
    #   trainers/woldvein_trainer/woldvein_trainer0.4.9
    #     ←→  trainers/woldvein_trainer/woldvein_injector0.4.7
    paths.append(os.path.join(os.path.dirname(trainer_root), INJECTOR_DIR_NAME))

    # 归集布局：trainers/woldvein_trainer/0.5.0  ←→  trainers/injector/0.4.7
    paths.append(os.path.join(
        os.path.dirname(os.path.dirname(trainer_root)), "injector", INJECTOR_DIR_NAME))

    # 兜底：同级目录下任意 woldvein_injector*（注入器版本号升级后仍可命中）
    try:
        parent = os.path.dirname(trainer_root)
        for name in sorted(os.listdir(parent), reverse=True):
            if name.startswith("woldvein_injector"):
                paths.append(os.path.join(parent, name))
    except Exception:
        pass

    # 内嵌布局（打包时 datas 打进 _MEIPASS 的 vendor/）
    paths.append(os.path.join(trainer_root, "vendor", INJECTOR_DIR_NAME))

    # ---- 以下为打包场景补充 ----
    # exe 所在目录（dist）及其逐级向上：找 trainers/injector/<name> 与 injector/<name>
    frozen = getattr(sys, "frozen", False)
    if frozen:
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        cur = exe_dir
        for _ in range(6):                       # 向上最多 6 级，够覆盖 dist→工作区根
            paths.append(os.path.join(cur, "injector", INJECTOR_DIR_NAME))
            paths.append(os.path.join(cur, "trainers", "injector", INJECTOR_DIR_NAME))
            parent = os.path.dirname(cur)
            if parent == cur:
                break
            cur = parent
    return paths


def locate_injector():
    """找到可用的注入器根目录，找不到返回 None。"""
    for p in _candidate_paths():
        if not p or not os.path.isdir(p):
            continue
        if os.path.exists(os.path.join(p, "injector_api.py")):
            return os.path.abspath(p)
    return None


def load_injector():
    """加载注入器并做版本/协议校验。返回 (module, error_msg)。"""
    global _load_error
    home = locate_injector()
    if not home:
        searched = "\n  - ".join(str(p) for p in _candidate_paths())
        return None, (
            "未找到 woldvein_injector v0.4.7。\n"
            f"已在这些位置查找：\n  - {searched}\n\n"
            "解决办法（任选其一）：\n"
            "  1) 设置环境变量 WOLDVEIN_INJECTOR_HOME 指向注入器根目录\n"
            "  2) 把注入器放到 trainers/injector/woldvein_injector0.4.7\n"
            "  3) 把注入器目录拷到本项目 vendor/woldvein_injector0.4.7"
        )

    if home not in sys.path:
        sys.path.insert(0, home)
    try:
        import injector_api
    except Exception as e:
        return None, f"加载注入器失败: {e}"

    ver = getattr(injector_api, "VERSION", "?")
    if ver != REQUIRED_INJECTOR_VERSION:
        return None, f"注入器版本不匹配：需要 v{REQUIRED_INJECTOR_VERSION}，实际 v{ver}"

    return injector_api, None


class InjectorClient:
    """修改器侧唯一的注入/通道入口。薄封装，不含任何注入实现。"""

    def __init__(self, injector_api_module=None):
        if injector_api_module is None:
            injector_api_module, err = load_injector()
            if err:
                raise RuntimeError(err)
        self._api = injector_api_module
        self._svc = self._api.InjectorService()

    # ---------- 元信息 ----------
    @property
    def injector_version(self):
        return self._api.VERSION

    @property
    def injector_home(self):
        return os.path.dirname(os.path.abspath(self._api.__file__))

    # ---------- 进程 ----------
    def find_game_process(self):
        return self._svc.find_game_process()

    def is_injected(self, pid=None):
        return self._svc.is_injected(pid)

    def ensure_injected(self, pid=None, dll_path=None):
        return self._svc.ensure_injected(pid=pid, dll_path=dll_path)

    # ---------- 通道 ----------
    def execute(self, code, timeout=None):
        """这是修改器唯一的"手"，伸进游戏进程就靠它。"""
        return self._svc.execute(code, timeout)

    def execute_safe(self, code, timeout=None):
        return self._svc.execute_safe(code, timeout)

    # ---------- 兼容旧 API ----------
    def inject_dll(self, pid, dll_path=None):
        return self._svc.ensure_injected(pid=pid, dll_path=dll_path)

    def get_dll_path(self):
        return self._svc.dll_path

    def get_process_modules(self, pid):
        return self._api.get_process_modules(pid)

    def launch_game(self, steam_app_id="2656540"):
        return self._api.launch_game(steam_app_id)

    def status(self):
        st = self._svc.status()
        st["injector_home"] = self.injector_home
        st["trainer_version"] = APP_VERSION
        return st


def try_get_client():
    """
    安全版：拿不到注入器时返回 (None, 错误原因)，**绝不抛异常**。

    打包后的 exe 可能在没放注入器的机器上运行，此时修改器应当照常打开
    （离线、优化、存档等页面与注入无关），只是注入类功能不可用 —— 不能秒退。
    """
    global _client, _load_error
    try:
        if _client is None:
            if _load_error:
                return None, _load_error
            _client = InjectorClient()
        return _client, None
    except Exception as e:
        _load_error = str(e)
        return None, _load_error


def get_client():
    """惰性单例。注入器不可用时抛 RuntimeError（保留旧语义，供明确要报错的场合用）。"""
    global _client, _load_error
    if _client is None:
        if _load_error:
            raise RuntimeError(_load_error)
        _client = InjectorClient()
    return _client


def reset_client():
    global _client, _load_error
    _client = None
    _load_error = None


__all__ = [
    "InjectorClient", "get_client", "try_get_client", "reset_client",
    "locate_injector", "load_injector", "REQUIRED_INJECTOR_VERSION",
]
