"""Source-level regression guards for the Windows app's safety-critical paths.

These tests intentionally avoid importing the Tk application so they can run on
CI hosts without a desktop session or the optional Windows dependencies.
"""
import ast
import os
import pathlib
import tempfile
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


def load_function(name):
    node = app_method(name)
    ns = {"os": os}
    exec(ast.get_source_segment(SOURCE, node), ns)
    fn = ns[name]
    return fn.__func__ if isinstance(fn, staticmethod) else fn


def load_module_function(name):
    node = next(n for n in TREE.body if isinstance(n, ast.FunctionDef) and n.name == name)
    ns = {"os": os}
    exec(ast.get_source_segment(SOURCE, node), ns)
    return ns[name]


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

    def test_config_parser_does_not_interpolate_percent(self):
        self.assertGreaterEqual(SOURCE.count("interpolation=None"), 3)

    def test_clipboard_lock_failure_frees_handle(self):
        body = method_text("_win32_set_clipboard_text")
        self.assertLess(body.index("if not ptr:"), body.index("ctypes.memmove"))
        self.assertIn("GlobalFree", body[body.index("if not ptr:"):body.index("ctypes.memmove")])

    def test_atomic_write_fsyncs_and_cleans_temp(self):
        write = load_module_function("_atomic_write")
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "records.json")
            write(path, '{"ok": true}\n')
            with open(path, encoding="utf-8") as f:
                self.assertEqual(f.read(), '{"ok": true}\n')
            self.assertEqual(list(pathlib.Path(tmp).glob("*.tmp")), [])

    def test_ini_scalar_stays_one_line(self):
        clean = load_module_function("_ini_scalar")
        self.assertEqual(clean("sk-a%b\nEvil=1"), "sk-a%b Evil=1")

    def test_download_url_strips_share_text_and_keeps_parentheses(self):
        clean = load_function("_dl_clean_url")
        self.assertEqual(
            clean("复制打开抖音 https://v.douyin.com/abc/ ，看看"),
            "https://v.douyin.com/abc/",
        )
        self.assertEqual(clean("(https://youtu.be/xyz)."), "https://youtu.be/xyz")
        self.assertEqual(
            clean("https://en.wikipedia.org/wiki/Foo_(bar)"),
            "https://en.wikipedia.org/wiki/Foo_(bar)",
        )
        self.assertEqual(clean("没有链接"), "没有链接")

    def test_merged_ocr_box_includes_higher_fragment(self):
        merge = load_function("_merge_line_fragments")
        lines = [
            {"t": "Hello", "x": 0, "y": 10, "w": 40, "h": 10},
            {"t": "world", "x": 46, "y": 8, "w": 36, "h": 14},
        ]
        merged = merge(lines)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["t"], "Hello world")
        self.assertEqual(merged[0]["y"], 8)
        self.assertEqual(merged[0]["h"], 14)
        self.assertEqual(merged[0]["x"], 0)
        self.assertEqual(merged[0]["w"], 82)

    def test_type_units_keep_emoji_surrogate_pair(self):
        units = load_function("_type_units")
        emoji = units("👍")
        scans = [scan for scan, _vk, up, unicode_ in emoji if unicode_ and not up]
        self.assertEqual(scans, [0xD83D, 0xDC4D])

    def test_ai_base_url_rejects_non_http(self):
        check = load_function("_http_base")
        self.assertEqual(check("https://example.com/v1/"), "https://example.com/v1")
        self.assertEqual(check("http://127.0.0.1:11434/v1"), "http://127.0.0.1:11434/v1")
        for bad in ("file:///etc/passwd", "javascript:alert(1)", "https://", "http://bad host"):
            with self.assertRaises(RuntimeError):
                check(bad)


if __name__ == "__main__":
    unittest.main()
