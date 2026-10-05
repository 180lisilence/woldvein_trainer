"""
woldvein Trainer v0.4.6 - 单元测试

测试核心模块功能。

运行方式：
    python -m pytest tests/ -v
    或
    python tests/run_tests.py
"""
import os
import sys
import json
import tempfile
import unittest

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestInputValidator(unittest.TestCase):
    """测试输入校验模块"""

    def setUp(self):
        from src.input_validator import validate_int, clamp_int
        self.validate_int = validate_int
        self.clamp_int = clamp_int

    def test_validate_int_valid(self):
        parsed, is_valid, msg = self.validate_int(100, 0, 1000)
        self.assertTrue(is_valid)
        self.assertEqual(parsed, 100)

    def test_validate_int_below_min(self):
        parsed, is_valid, msg = self.validate_int(-1, 0, 1000)
        self.assertFalse(is_valid)

    def test_validate_int_above_max(self):
        parsed, is_valid, msg = self.validate_int(2000, 0, 1000)
        self.assertFalse(is_valid)

    def test_validate_int_non_numeric(self):
        parsed, is_valid, msg = self.validate_int("abc", 0, 1000)
        self.assertFalse(is_valid)

    def test_clamp_int(self):
        self.assertEqual(self.clamp_int(150, 0, 100), 100)
        self.assertEqual(self.clamp_int(-50, 0, 100), 0)
        self.assertEqual(self.clamp_int(50, 0, 100), 50)


class TestAtomicFile(unittest.TestCase):
    """测试原子文件操作模块"""

    def setUp(self):
        from src.atomic_file import atomic_write_text, atomic_write_json
        self.atomic_write_text = atomic_write_text
        self.atomic_write_json = atomic_write_json
        self.temp_dir = tempfile.mkdtemp()

    def test_atomic_write_text(self):
        filepath = os.path.join(self.temp_dir, "test.txt")
        self.atomic_write_text(filepath, "hello world")
        with open(filepath, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "hello world")

    def test_atomic_write_json(self):
        filepath = os.path.join(self.temp_dir, "test.json")
        data = {"key": "value", "number": 42}
        self.atomic_write_json(filepath, data)
        with open(filepath, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        self.assertEqual(loaded, data)

    def test_atomic_write_overwrite(self):
        filepath = os.path.join(self.temp_dir, "test.txt")
        self.atomic_write_text(filepath, "first")
        self.atomic_write_text(filepath, "second")
        with open(filepath, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "second")


class TestOperationHistory(unittest.TestCase):
    """测试操作历史模块"""

    def setUp(self):
        from src.operation_history import OperationHistory, Operation
        self.OperationHistory = OperationHistory
        self.Operation = Operation
        self.history = OperationHistory(max_stack_size=10)

    def test_execute_and_undo(self):
        state = {"value": 0}

        def do():
            state["value"] = 10
            return True

        def undo():
            state["value"] = 0
            return True

        op = self.Operation("test", do_func=do, undo_func=undo)
        self.history.execute(op)
        self.assertEqual(state["value"], 10)

        self.history.undo()
        self.assertEqual(state["value"], 0)

    def test_redo(self):
        state = {"value": 0}

        def do():
            state["value"] = 10

        def undo():
            state["value"] = 0

        op = self.Operation("test", do_func=do, undo_func=undo)
        self.history.execute(op)
        self.history.undo()
        self.assertEqual(state["value"], 0)

        self.history.redo()
        self.assertEqual(state["value"], 10)

    def test_can_undo_redo(self):
        self.assertFalse(self.history.can_undo())
        self.assertFalse(self.history.can_redo())

        op = self.Operation("test", do_func=lambda: None, undo_func=lambda: None)
        self.history.execute(op)
        self.assertTrue(self.history.can_undo())
        self.assertFalse(self.history.can_redo())

        self.history.undo()
        self.assertFalse(self.history.can_undo())
        self.assertTrue(self.history.can_redo())

    def test_max_size(self):
        for i in range(15):
            op = self.Operation(f"op_{i}", do_func=lambda: None, undo_func=lambda: None)
            self.history.execute(op)
        self.assertEqual(len(self.history.get_history()), 10)


class TestHotkeyDebouncer(unittest.TestCase):
    """测试热键防抖模块"""

    def setUp(self):
        from src.hotkey_debouncer import HotkeyDebouncer
        self.debouncer = HotkeyDebouncer(default_debounce_ms=100)

    def test_can_trigger_initially(self):
        self.assertTrue(self.debouncer.can_trigger("test"))

    def test_debounce_blocks(self):
        self.debouncer.mark_triggered("test")
        self.assertFalse(self.debouncer.can_trigger("test"))

    def test_debounce_expires(self):
        import time
        self.debouncer.mark_triggered("test")
        time.sleep(0.15)  # 等待超过 100ms
        self.assertTrue(self.debouncer.can_trigger("test"))

    def test_custom_debounce(self):
        self.debouncer.set_debounce("custom", 500)
        self.debouncer.mark_triggered("custom")
        import time
        time.sleep(0.1)
        self.assertFalse(self.debouncer.can_trigger("custom"))

    def test_try_trigger(self):
        call_count = [0]

        def func():
            call_count[0] += 1
            return "result"

        executed, result = self.debouncer.try_trigger("test", func)
        self.assertTrue(executed)
        self.assertEqual(result, "result")
        self.assertEqual(call_count[0], 1)

        executed, result = self.debouncer.try_trigger("test", func)
        self.assertFalse(executed)
        self.assertEqual(call_count[0], 1)


class TestEmergencyStop(unittest.TestCase):
    """测试紧急停止模块"""

    def setUp(self):
        from src.emergency_stop import EmergencyStop
        self.estop = EmergencyStop()

    def test_initial_state(self):
        self.assertFalse(self.estop.is_triggered())

    def test_trigger(self):
        result = self.estop.trigger("test reason")
        self.assertTrue(result)
        self.assertTrue(self.estop.is_triggered())

    def test_double_trigger(self):
        self.estop.trigger("first")
        result = self.estop.trigger("second")
        self.assertFalse(result)  # 重复触发返回 False

    def test_reset(self):
        self.estop.trigger("test")
        result = self.estop.reset()
        self.assertTrue(result)
        self.assertFalse(self.estop.is_triggered())

    def test_callback(self):
        called = [False]

        def callback(reason):
            called[0] = True

        self.estop.register_callback(callback)
        self.estop.trigger("test")
        self.assertTrue(called[0])

    def test_status(self):
        self.estop.trigger("test reason")
        status = self.estop.get_status()
        self.assertTrue(status["triggered"])
        self.assertEqual(status["reason"], "test reason")


class TestTransaction(unittest.TestCase):
    """测试事务批量操作模块"""

    def setUp(self):
        from src.transaction import Transaction, Operation
        self.Transaction = Transaction
        self.Operation = Operation

    def test_successful_commit(self):
        state = {"a": 0, "b": 0}
        tx = self.Transaction("test")

        tx.add(self.Operation("a", do_func=lambda: state.update(a=1), undo_func=lambda: state.update(a=0)))
        tx.add(self.Operation("b", do_func=lambda: state.update(b=2), undo_func=lambda: state.update(b=0)))

        success, results, error = tx.commit()
        self.assertTrue(success)
        self.assertEqual(state["a"], 1)
        self.assertEqual(state["b"], 2)

    def test_failed_commit_rollback(self):
        state = {"a": 0, "b": 0}

        def fail_op():
            raise RuntimeError("fail")

        tx = self.Transaction("test")
        tx.add(self.Operation("a", do_func=lambda: state.update(a=1), undo_func=lambda: state.update(a=0)))
        tx.add(self.Operation("b", do_func=fail_op, undo_func=lambda: state.update(b=0)))

        success, results, error = tx.commit()
        self.assertFalse(success)
        self.assertEqual(state["a"], 0)  # 已回滚
        self.assertEqual(state["b"], 0)

    def test_manual_rollback(self):
        state = {"a": 0}
        tx = self.Transaction("test")
        tx.add(self.Operation("a", do_func=lambda: state.update(a=1), undo_func=lambda: state.update(a=0)))
        tx.commit()
        self.assertEqual(state["a"], 1)

        tx.rollback()
        self.assertEqual(state["a"], 0)


class TestI18n(unittest.TestCase):
    """测试多语言模块"""

    def setUp(self):
        from src.i18n import I18nManager
        self.i18n = I18nManager(language="zh-CN")

    def test_default_language(self):
        self.assertEqual(self.i18n.get_language(), "zh-CN")

    def test_translate_existing_key(self):
        result = self.i18n.translate("app.name")
        self.assertIsInstance(result, str)
        self.assertTrue(len(result) > 0)

    def test_translate_missing_key(self):
        result = self.i18n.translate("nonexistent.key")
        self.assertEqual(result, "nonexistent.key")

    def test_switch_language(self):
        success = self.i18n.set_language("en-US")
        self.assertTrue(success)
        self.assertEqual(self.i18n.get_language(), "en-US")

    def test_available_languages(self):
        langs = self.i18n.get_available_languages()
        self.assertIn("zh-CN", langs)
        self.assertIn("en-US", langs)


class TestHotkeyConflict(unittest.TestCase):
    """测试热键冲突检测模块"""

    def setUp(self):
        from src.hotkey_conflict import HotkeyConflictDetector, normalize_hotkey
        self.detector = HotkeyConflictDetector()
        self.normalize = normalize_hotkey

    def test_normalize_hotkey(self):
        self.assertEqual(self.normalize("ctrl+f1"), "Ctrl+F1")
        self.assertEqual(self.normalize("F1+Ctrl"), "Ctrl+F1")
        self.assertEqual(self.normalize("alt + shift + a"), "Alt+Shift+A")

    def test_register_and_check(self):
        success, _ = self.detector.register("func1", "Ctrl+F1")
        self.assertTrue(success)

        has_conflict, conflicts = self.detector.check("Ctrl+F1")
        self.assertTrue(has_conflict)
        self.assertEqual(conflicts[0]["type"], "internal")

    def test_system_hotkey_conflict(self):
        has_conflict, conflicts = self.detector.check("Ctrl+C")
        self.assertTrue(has_conflict)
        self.assertEqual(conflicts[0]["type"], "system")

    def test_no_conflict(self):
        has_conflict, _ = self.detector.check("Ctrl+Alt+Shift+F12")
        self.assertFalse(has_conflict)

    def test_unregister(self):
        self.detector.register("func1", "Ctrl+F1")
        self.detector.unregister("func1")
        has_conflict, _ = self.detector.check("Ctrl+F1")
        # 可能还有系统冲突，但内部冲突应该没有了
        internal_conflicts = [c for c in self.detector.check("Ctrl+F1")[1] if c["type"] == "internal"]
        self.assertEqual(len(internal_conflicts), 0)


def run_all_tests():
    """运行所有测试"""
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
