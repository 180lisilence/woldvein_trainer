# -*- coding: utf-8 -*-
"""
woldvein Trainer v0.4.9 - 引擎优化模块测试

运行：
    python tests/test_perf_optimizer.py

覆盖：
    1. ini 编辑器字节级最小侵入（不碰真实游戏文件）
    2. 三档 profile 数据完整性
    3. 动态值在合理范围
    4. UI 面板能否真正构造出来（tk 冒烟）
"""
import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, _ROOT)

from src import perf_optimizer as po


def _read_bytes(path):
    """读取文件内容并保证句柄关闭（Windows 上裸 open().read() 会短暂锁文件）"""
    with open(path, "rb") as f:
        return f.read()


class TestIniEditor(unittest.TestCase):
    """ini 编辑器：必须字节级最小侵入"""

    SAMPLE = (
        b"[KG3DENGINE]\r\n"
        b"MaxAnisotropy=1\r\n"
        b"NumCpuThread=1\r\n"
        b"\r\n"
        b"[ENGINEOPTION]\r\n"
        b"MinWorkSet=600\r\n"
        b"MaxWorkSet=1400\r\n"
        b"UseMultiThreadCull=0\r\n"
    )

    def test_update_existing_key(self):
        out, old, act = po._edit_ini(self.SAMPLE, "KG3DENGINE", "MaxAnisotropy", "16")
        self.assertEqual(act, "update")
        self.assertEqual(old, "1")
        self.assertIn(b"MaxAnisotropy=16\r\n", out)
        # 兄弟行不受影响
        self.assertIn(b"NumCpuThread=1\r\n", out)

    def test_no_cross_section_override(self):
        # 同名 key 在不同段必须各自独立
        _, old, _ = po._edit_ini(self.SAMPLE, "ENGINEOPTION", "MinWorkSet", "2048")
        self.assertEqual(old, "600")

    def test_insert_new_key_into_section(self):
        out, old, act = po._edit_ini(self.SAMPLE, "KG3DENGINE", "bDisableDynamicScale", "1")
        self.assertIsNone(old)
        self.assertEqual(act, "insert")
        self.assertIn(b"bDisableDynamicScale=1\r\n", out)
        # 后续段落仍在
        self.assertIn(b"[ENGINEOPTION]\r\n", out)

    def test_append_missing_section(self):
        out, _, act = po._edit_ini(self.SAMPLE, "BRANDNEW", "Foo", "1")
        self.assertEqual(act, "append-section")
        self.assertTrue(out.rstrip().endswith(b"[BRANDNEW]\r\nFoo=1"))

    def test_crlf_preserved(self):
        out = po._edit_ini(self.SAMPLE, "KG3DENGINE", "MaxAnisotropy", "16")[0]
        self.assertEqual(out.count(b"\r\n"), self.SAMPLE.count(b"\r\n"))

    def test_comment_lines_skipped(self):
        raw = b"[S]\r\n;MaxAnisotropy=99\r\nMaxAnisotropy=1\r\n"
        self.assertEqual(po.read_ini_value_from_bytes(raw, "S", "MaxAnisotropy"), "1")

    def test_lf_only_file(self):
        raw = b"[S]\nFoo=1\nBar=2\n"
        out, old, act = po._edit_ini(raw, "S", "Foo", "9")
        self.assertEqual(act, "update")
        self.assertIn(b"Foo=9\n", out)
        self.assertNotIn(b"\r\n", out)


class TestProfiles(unittest.TestCase):
    """三档 profile 数据完整、值合法"""

    def test_order_covers_all(self):
        self.assertEqual(set(po.PROFILE_ORDER), set(po.PROFILES.keys()))

    def test_each_change_has_required_fields(self):
        for name in po.PROFILE_ORDER:
            for c in po.PROFILES[name]["changes"]:
                for f in ("section", "key", "label", "why", "risk"):
                    self.assertIn(f, c, f"{name}.{c.get('key')} 缺字段 {f}")

    def test_static_values_are_strings(self):
        for name in po.PROFILE_ORDER:
            for c in po.PROFILES[name]["changes"]:
                if c["value"] is not None:
                    self.assertIsInstance(c["value"], str)

    def test_balanced_superset_of_safe(self):
        safe = {(c["section"], c["key"]) for c in po.PROFILES["safe"]["changes"]}
        bal = {(c["section"], c["key"]) for c in po.PROFILES["balanced"]["changes"]}
        self.assertTrue(safe.issubset(bal), "均衡档应包含保守档的全部项")

    def test_dynamic_values_in_range(self):
        for prof in po.PROFILE_ORDER:
            for k in ("NumCpuThread", "MinWorkSet", "MaxWorkSet"):
                v = int(po._dynamic_value(k, prof))
                self.assertGreater(v, 0, f"{prof}.{k}={v}")

    def test_recommend_returns_valid_profile(self):
        name, why = po.recommend_profile()
        self.assertIn(name, po.PROFILE_ORDER)
        self.assertIsInstance(why, str)


class TestPublicApi(unittest.TestCase):
    """公开 API 不得抛异常，且始终返回 ok 字段"""

    def test_read_current_returns_ok_flag(self):
        r = po.read_current()
        self.assertIn("ok", r)
        if not r["ok"]:
            self.assertTrue(r["msg"])   # 失败必须带 msg

    def test_current_profile_shape(self):
        name, n, t = po.current_profile()
        self.assertIsInstance(n, int)
        self.assertIsInstance(t, int)
        if name is not None:
            self.assertIn(name, list(po.PROFILE_ORDER) + ["custom"])

    def test_apply_dry_run_never_writes(self):
        if not po.read_current()["ok"]:
            self.skipTest("本机未安装游戏")
        before = _read_bytes(po.get_ini_path())
        r = po.apply_profile("balanced", dry_run=True)
        self.assertTrue(r["ok"])
        after = _read_bytes(po.get_ini_path())
        self.assertEqual(before, after, "预演绝不允许改动磁盘")

    def test_hardware_summary_safe(self):
        s = po.hardware_summary()
        self.assertIsInstance(s, str)


def _collect_texts(widget, out):
    """递归收集 widget 树里所有能显示的文本"""
    try:
        t = widget.cget("text")
        if isinstance(t, str) and t.strip():
            out.append(t.strip())
    except Exception:
        pass
    for ch in widget.winfo_children():
        _collect_texts(ch, out)
    return out


class TestUiPanel(unittest.TestCase):
    """UI 面板冒烟：能构造出来且真的渲染出内容"""

    def _make_app(self):
        try:
            import tkinter as tk
        except Exception as e:
            self.skipTest(f"no tkinter: {e}")
        if not po.read_current()["ok"]:
            self.skipTest("本机未安装游戏，跳过 UI 构造")
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

    def test_sidebar_has_optimize_nav(self):
        """优化必须是侧边栏独立导航项，而不是工具页的子项"""
        root, app = self._make_app()
        try:
            # v0.5.0：侧边栏有 9 个导航按钮（8 个主项 + 设置）
            self.assertGreaterEqual(len(app.nav_buttons), 9,
                                    f"侧边栏只有 {len(app.nav_buttons)} 个按钮")
            names = [b.cget("text") for b in app.nav_buttons]
            self.assertIn("优化", names, f"侧边栏缺少「优化」，现有：{names}")
            # 优化必须在「工具」之后
            self.assertGreater(names.index("优化"), names.index("工具"))
            # v0.5.0 重排：优化 = 3（0.4.9 侧边栏已是第 3 位，但 func_data 仍是旧顺序，已修正）
            self.assertIn(3, app.func_data)
            self.assertEqual([t[1] for t in app.func_data[3]][0], "优化档位")
            # 引擎优化不应再挂在工具页下
            tool_names = [t[1] for t in app.func_data[2]]
            self.assertNotIn("引擎优化", tool_names, "工具页不应再保留引擎优化")
        finally:
            try:
                root.destroy()
            except Exception:
                pass

    def test_nav_index_alignment(self):
        """v0.5.0：侧边栏顺序 / func_data 键 / _update_action_panel 分支必须一致"""
        root, app = self._make_app()
        try:
            names = [b.cget("text") for b in app.nav_buttons]
            # 侧边栏第 3 位是「优化」，那么 func_data[3] 的首项必须是优化档位
            self.assertEqual(names[3], "优化")
            self.assertEqual([t[1] for t in app.func_data[3]][0], "优化档位")
            # 侧边栏第 4 位是「存档」，func_data[4] 首项必须是存档列表
            self.assertEqual(names[4], "存档")
            self.assertEqual([t[1] for t in app.func_data[4]][0], "存档列表")
            # 切到「优化」不能渲染出存档面板
            app._switch_nav(3)
            texts = "\n".join(_collect_texts(app.content_inner, []))
            self.assertIn("优化档位", texts)
            self.assertNotIn("存档管理", texts, "点「优化」却渲染出存档面板 —— 索引又错位了")
            # 切到「存档」不能渲染出优化面板
            app._switch_nav(4)
            texts = "\n".join(_collect_texts(app.content_inner, []))
            self.assertIn("存档管理", texts)
            self.assertNotIn("优化档位", texts, "点「存档」却渲染出优化面板 —— 索引又错位了")
        finally:
            try:
                root.destroy()
            except Exception:
                pass

    def test_perf_nav_renders(self):
        root, app = self._make_app()
        try:
            app._switch_nav(3)          # 侧边栏「优化」
            self.assertTrue(hasattr(app, "_build_perf_tools"))
            texts = _collect_texts(app.content_inner, [])
            self.assertIn("优化档位", "\n".join(texts))
            self.assertIn("均衡档", "\n".join(texts))
        finally:
            try:
                root.destroy()
            except Exception:
                pass

    def test_perf_subpages_render(self):
        """四个子项各自渲染出对应分区，内容不能都一样"""
        root, app = self._make_app()
        try:
            app._switch_nav(3)
            seen = {}
            for func, must in ((0, "优化档位"), (1, "改动明细"),
                               (2, "锁定高性能独显"), (3, "一键还原到备份")):
                app._switch_func(func)
                texts = "\n".join(_collect_texts(app.content_inner, []))
                seen[func] = texts
                self.assertIn(must, texts, f"子项 {func} 缺少：{must}")
            # 子项之间内容必须有差异，否则等于没分区
            self.assertNotEqual(seen[0], seen[2], "子项 0 与 2 内容相同，分区未生效")
        finally:
            try:
                root.destroy()
            except Exception:
                pass

    def test_no_empty_nav_page(self):
        """每个导航索引都要有内容 —— 否则点进去是白屏（重排索引时最容易踩）"""
        root, app = self._make_app()
        try:
            for nav in sorted(app.func_data):
                self.assertTrue(app.func_data[nav], f"nav {nav} 没有任何功能项")
                app._switch_nav(nav)
                texts = _collect_texts(app.content_inner, [])
                self.assertGreater(len(texts), 3,
                                   f"nav {nav} 渲染后几乎空白（{len(texts)} 条文本）")
        finally:
            try:
                root.destroy()
            except Exception:
                pass

    def test_settings_nav_shifted(self):
        """v0.5.0：新增「离线」后设置顺延到 8，不能被新导航项挤掉"""
        root, app = self._make_app()
        try:
            app._switch_nav(8)
            texts = "\n".join(_collect_texts(app.content_inner, []))
            self.assertTrue(any(k in texts for k in ("热键", "日志", "MOD", "版本")),
                            f"nav 8 未渲染设置页，实际内容：{texts[:120]}")
        finally:
            try:
                root.destroy()
            except Exception:
                pass


if __name__ == "__main__":
    unittest.main(verbosity=2)
