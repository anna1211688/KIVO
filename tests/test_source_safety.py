"""Source-level regression guards for the Windows app's safety-critical paths.

These tests intentionally avoid importing the Tk application so they can run on
CI hosts without a desktop session or the optional Windows dependencies.
"""
import ast
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "main.py").read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)


def app_method(name):
    app = next(
        node for node in TREE.body
        if isinstance(node, ast.ClassDef) and node.name == "App"
    )
    return next(
        node for node in app.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == name
    )


def method_text(name):
    return ast.get_source_segment(SOURCE, app_method(name))


class SafetyRegressionTests(unittest.TestCase):
    def test_main_module_parses(self):
        compile(SOURCE, str(ROOT / "main.py"), "exec")

    def test_paste_queue_only_consumes_after_success(self):
        body = method_text("paste_next")
        self.assertIn("if not self._paste_text(", body)
        self.assertLess(body.index("if not self._paste_text("), body.index("del self.records"))

    def test_paste_reports_failure_for_self_window_and_failed_input(self):
        body = method_text("_paste_text")
        self.assertIn("if self._foreground_is_self():", body)
        self.assertIn("pasted = bool(self._type_text(text))", body)
        self.assertIn("pasted = bool(self._send_combo(0x56))", body)
        self.assertIn("if not pasted:", body)
        self.assertIn("return False", body)

    def test_copy_requires_command_and_clipboard_change(self):
        body = method_text("multi_copy")
        self.assertIn("if not self._send_combo(", body)
        self.assertIn("if not changed:", body)
        self.assertIn("if not text.strip():", body)

    def test_sendinput_partial_batch_is_not_success(self):
        body = method_text("_type_text")
        self.assertIn("sent = u.SendInput(", body)
        self.assertIn("if sent != len(part):", body)

    def test_language_loader_checks_root_ini_files(self):
        body = method_text("_load_lang")
        self.assertIn('os.path.join(BUNDLE, f"{self.lang}.ini")', body)
        self.assertIn('os.path.join(BASE, f"{self.lang}.ini")', body)


if __name__ == "__main__":
    unittest.main()
