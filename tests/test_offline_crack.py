# -*- coding: utf-8 -*-
"""
woldvein Trainer v0.5.0 - 离线化模块测试

运行：
    python tests/test_offline_crack.py

覆盖：
    1. 内置补丁完整性（模拟器 dll + 4 个 lua 散文件，含 MD5 指纹比对）
    2. 公开 API 契约：所有函数返回 dict、不抛异常
    3. config.cfg 的 publish=0 读写是最小侵入（不破坏 channel、不破坏换行符）
    4. 安装 / 卸载在临时假游戏目录里跑通，且能互相抵消
    5. UI 离线页四个子项能渲染出来（tk 冒烟）

安全边界：
    全部安装/卸载测试都在 tempfile 建的假目录里做，绝不碰真实游戏目录。
"""
import os
import sys
import shutil
import tempfile
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, _ROOT)

from src import offline_crack as oc

PY = sys.executable


def _read_bytes(path):
    with open(path, "rb") as f:
        return f.read()


class TestPayload(unittest.TestCase):
    """内置补丁必须齐备且指纹正确 —— 否则装上去是半残状态"""

    def test_payload_ready(self):
        ok, msg = oc.payload_ready()
        self.assertTrue(ok, f"内置补丁不完整：{msg}")

    def test_payload_files_exist(self):
        pd = oc.payload_dir()
        self.assertTrue(os.path.isdir(pd), f"补丁目录不存在：{pd}")
        self.assertTrue(os.path.isfile(os.path.join(pd, oc.EMU_DLL_NAME)), "缺模拟器 dll")
        for rel in oc.LUA_PAYLOADS:
            self.assertTrue(os.path.isfile(os.path.join(pd, rel)), f"缺 lua：{rel}")

    def test_known_md5_match(self):
        """内嵌的已知指纹必须和实际文件对得上（防止补丁被换过）"""
        pd = oc.payload_dir()
        for name, want in oc.KNOWN_MD5.items():
            p = os.path.join(pd, name)
            if not os.path.isfile(p):
                continue
            self.assertEqual(oc._md5(p), want, f"{name} 指纹不匹配")

    def test_lua_payloads_under_sim_common(self):
        for rel in oc.LUA_PAYLOADS:
            self.assertTrue(rel.replace("\\", "/").startswith("sim_common/"),
                            f"lua 载荷必须落在 sim_common 下：{rel}")


class TestApiContract(unittest.TestCase):
    """所有公开函数都返回 dict，永远不抛异常"""

    def test_status_returns_dict(self):
        r = oc.status()
        self.assertIsInstance(r, dict)
        self.assertIn("ok", r)
        self.assertIn("installed", r)
        self.assertIn("dll_state", r)
        self.assertIn("summary", r)

    def test_status_invalid_path_no_raise(self):
        r = oc.status(r"Z:\definitely\not\a\game")
        self.assertIsInstance(r, dict)
        self.assertFalse(r.get("exe_exists"), "不存在的路径不应判定为有效")

    def test_last_login_returns_dict(self):
        r = oc.last_login()
        self.assertIsInstance(r, dict)
        for k in ("ok", "found", "login", "expired_toast"):
            self.assertIn(k, r)

    def test_self_check_shape(self):
        passed, total, items = oc.self_check()
        self.assertIsInstance(passed, int)
        self.assertIsInstance(total, int)
        self.assertGreaterEqual(total, 1)
        self.assertEqual(len(items), total)
        for it in items:
            self.assertEqual(len(it), 3, f"检查项结构异常：{it}")

    def test_install_never_raises_on_bad_path(self):
        r = oc.install(r"Z:\definitely\not\a\game")
        self.assertIsInstance(r, dict)
        self.assertFalse(r.get("ok"), "无效路径必须返回失败而不是抛异常")

    def test_uninstall_never_raises_on_bad_path(self):
        r = oc.uninstall(r"Z:\definitely\not\a\game")
        self.assertIsInstance(r, dict)


class TestConfigEdit(unittest.TestCase):
    """publish=0 的读写：最小侵入"""

    def _make_cfg(self, text):
        d = tempfile.mkdtemp(prefix="oc_cfg_")
        self.addCleanup(shutil.rmtree, d, True)
        os.makedirs(os.path.join(d, "configs"), exist_ok=True)
        p = os.path.join(d, "configs", "config.cfg")
        with open(p, "wb") as f:
            f.write(text)
        return d

    def test_add_publish_after_channel(self):
        d = self._make_cfg(b"[Misc]\r\nchannel=11\r\nfoo=bar\r\n")
        ok, msg = oc._set_publish(d, True)
        self.assertTrue(ok, msg)
        out = _read_bytes(os.path.join(d, "configs", "config.cfg"))
        self.assertIn(b"channel=11\r\n", out, "channel 行不能被破坏")
        self.assertIn(b"publish=0", out)
        self.assertIn(b"foo=bar\r\n", out, "其它行不能丢")

    def test_idempotent(self):
        d = self._make_cfg(b"[Misc]\r\nchannel=11\r\n")
        oc._set_publish(d, True)
        before = _read_bytes(os.path.join(d, "configs", "config.cfg"))
        oc._set_publish(d, True)
        after = _read_bytes(os.path.join(d, "configs", "config.cfg"))
        self.assertEqual(before, after, "重复写入不应产生第二行 publish=0")

    def test_remove_publish(self):
        d = self._make_cfg(b"[Misc]\r\nchannel=11\r\npublish=0\r\nfoo=bar\r\n")
        ok, msg = oc._set_publish(d, False)
        self.assertTrue(ok, msg)
        out = _read_bytes(os.path.join(d, "configs", "config.cfg"))
        self.assertNotIn(b"publish=0", out)
        self.assertIn(b"channel=11\r\n", out)
        self.assertIn(b"foo=bar\r\n", out, "删 publish 不能误删邻居")

    def test_keeps_lf_when_source_is_lf(self):
        d = self._make_cfg(b"[Misc]\nchannel=11\n")
        oc._set_publish(d, True)
        out = _read_bytes(os.path.join(d, "configs", "config.cfg"))
        self.assertNotIn(b"\r\n", out, "源文件是 LF 就不该引入 CRLF")

    def test_backup_created(self):
        d = self._make_cfg(b"[Misc]\r\nchannel=11\r\n")
        oc._set_publish(d, True)
        self.assertTrue(os.path.isfile(os.path.join(d, oc.CONFIG_BACKUP_REL)), "改前应先备份")


class TestInstallUninstall(unittest.TestCase):
    """在假游戏目录里跑完整安装 / 卸载，验证可互相抵消"""

    def _fake_game(self):
        d = tempfile.mkdtemp(prefix="oc_game_")
        self.addCleanup(shutil.rmtree, d, True)
        # bin64 + 主程序 + 一份"原版" dll
        os.makedirs(os.path.join(d, "bin64"), exist_ok=True)
        with open(os.path.join(d, "bin64", oc.GAME_PROCESS), "wb") as f:
            f.write(b"MZ fake")
        with open(os.path.join(d, "bin64", oc.EMU_DLL_NAME), "wb") as f:
            f.write(b"ORIGINAL STEAM DLL")
        os.makedirs(os.path.join(d, "configs"), exist_ok=True)
        with open(os.path.join(d, "configs", "config.cfg"), "wb") as f:
            f.write(b"[Misc]\r\nchannel=11\r\n")
        return d

    def test_install_then_status(self):
        ok, msg = oc.payload_ready()
        if not ok:
            self.skipTest(f"内置补丁不完整：{msg}")
        d = self._fake_game()
        res = oc.install(d)
        self.assertTrue(res.get("ok"), res.get("msg"))
        st = oc.status(d)
        self.assertTrue(st.get("installed"), f"安装后应判定为已安装：{st}")
        self.assertEqual(st.get("dll_state"), "emulator")
        self.assertEqual(len(st.get("lua_missing", [])), 0, f"lua 有缺失：{st.get('lua_missing')}")
        self.assertTrue(st.get("publish_zero"), "publish=0 未写入")
        self.assertTrue(st.get("dll_backup"), "原 dll 未备份")

    def test_uninstall_restores(self):
        ok, msg = oc.payload_ready()
        if not ok:
            self.skipTest(f"内置补丁不完整：{msg}")
        d = self._fake_game()
        orig = _read_bytes(os.path.join(d, "bin64", oc.EMU_DLL_NAME))
        self.assertTrue(oc.install(d).get("ok"))
        res = oc.uninstall(d)
        self.assertTrue(res.get("ok"), res.get("msg"))
        # dll 还原成原件
        self.assertEqual(_read_bytes(os.path.join(d, "bin64", oc.EMU_DLL_NAME)), orig,
                         "卸载后 dll 未还原成原件")
        # lua 全部删除
        st = oc.status(d)
        self.assertEqual(len(st.get("lua_present", [])), 0, f"lua 未清干净：{st.get('lua_present')}")
        self.assertFalse(st.get("installed"), "卸载后不应再判定为已安装")

    def test_install_rejects_when_backup_is_emulator(self):
        """当前 dll 已经是模拟器时，不能把它备份成原件（否则卸载永远还原不回来）"""
        ok, msg = oc.payload_ready()
        if not ok:
            self.skipTest(f"内置补丁不完整：{msg}")
        d = tempfile.mkdtemp(prefix="oc_game2_")
        self.addCleanup(shutil.rmtree, d, True)
        os.makedirs(os.path.join(d, "bin64"), exist_ok=True)
        with open(os.path.join(d, "bin64", "BalladsOfHongye.exe"), "wb") as f:
            f.write(b"MZ fake")
        shutil.copy2(os.path.join(oc.payload_dir(), oc.EMU_DLL_NAME),
                     os.path.join(d, "bin64", oc.EMU_DLL_NAME))
        ok_b, msg_b = oc._backup_dll(d)
        self.assertFalse(ok_b, "把模拟器备份成原件是严重错误，必须拒绝")
        self.assertIn("模拟器", msg_b)


class TestOfflineUi(unittest.TestCase):
    """离线页面冒烟"""

    def _make_app(self):
        try:
            import tkinter as tk
        except Exception as e:
            self.skipTest(f"no tkinter: {e}")
        try:
            root = tk.Tk()
        except Exception as e:
            self.skipTest(f"无法显示 tk 窗口: {e}")
        root.withdraw()
        try:
            import trainer_ui_tk as ui
            app = ui.TrainerApp(root)
        except Exception:
            try:
                root.destroy()
            except Exception:
                pass
            raise
        return root, app

    def _texts(self, widget, out=None):
        out = [] if out is None else out
        try:
            t = widget.cget("text")
        except Exception:
            t = None
        if t:
            out.append(str(t))
        for ch in widget.winfo_children():
            self._texts(ch, out)
        return out

    def test_offline_nav_exists(self):
        root, app = self._make_app()
        try:
            names = [b.cget("text") for b in app.nav_buttons]
            self.assertIn("离线", names, f"侧边栏缺少「离线」：{names}")
            self.assertEqual(names.index("离线"), 7, f"离线应在索引 7，实际：{names}")
            self.assertIn(7, app.func_data)
            self.assertTrue(app.func_data[7])
        finally:
            try:
                root.destroy()
            except Exception:
                pass

    def test_offline_subpages_render(self):
        root, app = self._make_app()
        try:
            app._switch_nav(7)
            seen = {}
            for func, must in ((0, "安装离线补丁"), (1, "最近一次登录"),
                               (2, "启动游戏"), (3, "为什么要两层")):
                app._switch_func(func)
                texts = "\n".join(self._texts(app.content_inner))
                seen[func] = texts
                self.assertIn(must, texts, f"离线子项 {func} 缺少：{must}")
            self.assertNotEqual(seen[0], seen[2], "离线子项 0 与 2 内容相同，分区未生效")
        finally:
            try:
                root.destroy()
            except Exception:
                pass

    def test_offline_callbacks_exist(self):
        root, app = self._make_app()
        try:
            for name in ("_on_oc_install", "_on_oc_uninstall", "_on_oc_launch",
                         "_on_oc_kill", "_on_oc_selfcheck"):
                self.assertTrue(hasattr(app, name), f"缺少回调 {name}")
        finally:
            try:
                root.destroy()
            except Exception:
                pass


if __name__ == "__main__":
    unittest.main(verbosity=2)
