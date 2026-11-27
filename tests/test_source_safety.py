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
        self.assertIn("ok = self._paste_text(", body)
        self.assertIn("if ok and self.paste_remove_var.get()", body)
        self.assertLess(body.index("ok = self._paste_text("), body.index("del self.records"))

    def test_paste_reports_failure_for_self_window_and_failed_input(self):
        body = method_text("_paste_text")
        self.assertIn("if self._foreground_is_self(): return False", body)
        self.assertIn("pasted = bool(self._type_text(text))", body)
        self.assertIn("pasted = bool(self._send_combo(0x56))", body)
        self.assertIn("if pasted:", body)
        self.assertIn("return pasted", body)

    def test_copy_requires_command_and_clipboard_change(self):
        body = method_text("multi_copy")
        self.assertIn("self._send_combo(0x58 if cut else 0x43)", body)
        self.assertIn("if seq != before_seq: break", body)
        self.assertIn("if len(self.records) > n:", body)

    def test_sendinput_partial_batch_is_not_success(self):
        body = method_text("_type_text")
        self.assertIn("u.SendInput(", body)
        self.assertIn("!= len(batch[j:j+200]): sent_all = False", body)

    def test_language_loader_checks_root_ini_files(self):
        body = method_text("_load_lang")
        self.assertIn('os.path.join(BUNDLE, "Language", f"{self.lang}.ini")', body)
        self.assertIn('os.path.join(BASE, "Language", f"{self.lang}.ini")', body)

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


# ---- 2026-11-27 全面审查整改的回归测试: 验签/版本/资产挑选/http 护栏/语言键集/备份护栏 ----
import json
import re
import textwrap
import zipfile

_TEST_RSA_N = 162981085384131595251459525080711306882316967772221501910582934700591271823244892151988469393288635764485989919236918997176280652681293961377027012749006280567381591256609187477820361021049637466040029980904342415982933389712807348934301863364505154817915230267915888885833079353119423640699467412558054054879
_TEST_RSA_D = 74533562873610449689205997012283116080533467218536866712880985335175870238406894772224032473049631543973779756007289001089007849634726357880752500100713588806702970794306860085181565143251116193135562181805496122995945349662211249978864149076972199596868672766315627233236149000448649340653718093456957370553


def _load_with_ns(name, extra_ns):
    """load_function 的加强版: 允许给被测函数补它引用的模块级名字 (json/BASE 等)。"""
    tree = ast.parse(SOURCE)
    segment = None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            segment = ast.get_source_segment(SOURCE, node)
            break
    if segment is None: raise AssertionError(f"function not found: {name}")
    ns = {"os": os}
    ns.update(extra_ns)
    exec(textwrap.dedent(segment), ns)
    attr = ns[name]
    return attr.__func__ if isinstance(attr, (staticmethod, classmethod)) else attr


def _test_sign(name, version, sha256_hex):
    import base64, hashlib
    t = bytes.fromhex("3031300d060960864801650304020105000420") + hashlib.sha256(("%s\n%s\n%s" % (name, version, sha256_hex)).encode("utf-8")).digest()
    k = (_TEST_RSA_N.bit_length() + 7) // 8
    em = b"\x00\x01" + b"\xff" * (k - len(t) - 3) + b"\x00" + t
    sig = pow(int.from_bytes(em, "big"), _TEST_RSA_D, _TEST_RSA_N).to_bytes(k, "big")
    return base64.b64encode(sig).decode("ascii")


class HardeningTests(unittest.TestCase):
    def test_ver_tuple_orders_prerelease_before_release(self):
        ver = _load_with_ns("_ver_tuple", {"re": re})
        self.assertLess(ver("v1.5.0-beta1"), ver("1.5.0"))
        self.assertLess(ver("1.5.0-beta1"), ver("1.5.0-beta2"))
        self.assertLess(ver("1.4.30"), ver("v1.5.0-beta1"))
        self.assertEqual(ver("1.4.30"), ver("v1.4.30"))
        self.assertGreater(ver("2.0"), ver("1.9.9"))

    def test_pick_setup_asset_prefers_tag_version(self):
        pick = load_function("_pick_setup_asset")
        data = {"tag_name": "v1.5.0", "assets": [
            {"name": "KIVO-Setup-1.4.0.exe", "browser_download_url": "u-old"},
            {"name": "KIVO-Setup-1.5.0.exe", "browser_download_url": "u-new"},
            {"name": "KIVO.exe", "browser_download_url": "u-single"}]}
        self.assertEqual(pick(data), ("u-new", "KIVO-Setup-1.5.0.exe"))
        data2 = {"tag_name": "v9.9.9", "assets": [{"name": "KIVO-Setup-1.4.0.exe", "browser_download_url": "u-old"}]}
        self.assertEqual(pick(data2), ("u-old", "KIVO-Setup-1.4.0.exe"))  # 没有同名时退回首个匹配
        self.assertEqual(pick({"assets": []}), ("", ""))

    def test_verify_update_sig_genuine_and_tampered(self):
        import types
        verify = _load_with_ns("_verify_update_sig", {})
        fake_cls = types.SimpleNamespace(_UPDATE_PUBKEY_N=_TEST_RSA_N, _UPDATE_PUBKEY_E=65537)
        sha = "a" * 64
        good = _test_sign("KIVO-Setup-1.5.0.exe", "1.5.0", sha)
        self.assertTrue(verify(fake_cls, "KIVO-Setup-1.5.0.exe", "1.5.0", sha, good))
        self.assertFalse(verify(fake_cls, "KIVO-Setup-1.5.0.exe", "1.5.0", "b" * 64, good))  # 改哈希
        self.assertFalse(verify(fake_cls, "KIVO-Setup-9.9.9.exe", "1.5.0", sha, good))       # 改文件名
        self.assertFalse(verify(fake_cls, "KIVO-Setup-1.5.0.exe", "9.9.9", sha, good))       # 改版本
        self.assertFalse(verify(fake_cls, "KIVO-Setup-1.5.0.exe", "1.5.0", sha, "AAAA"))     # 长度不对
        self.assertFalse(verify(fake_cls, "KIVO-Setup-1.5.0.exe", "1.5.0", sha, ""))         # 空签名

    def test_http_base_rejects_public_http(self):
        http_base = load_function("_http_base")
        self.assertEqual(http_base("http://localhost:11434/v1"), "http://localhost:11434/v1")
        self.assertEqual(http_base("http://192.168.1.10:11434/v1"), "http://192.168.1.10:11434/v1")
        self.assertEqual(http_base("https://api.example.com/v1"), "https://api.example.com/v1")
        with self.assertRaises(RuntimeError):
            http_base("http://api.example.com/v1")  # 公网 http 会明文送 API Key, 必须拒绝

    def test_atomic_write_actually_fsyncs(self):
        write = load_module_function("_atomic_write")
        calls = []
        real_fsync = os.fsync
        os.fsync = lambda fd: calls.append(fd)
        try:
            with tempfile.TemporaryDirectory() as td:
                target = os.path.join(td, "data.txt")
                write(target, "payload")
                with open(target, encoding="utf-8") as f: self.assertEqual(f.read(), "payload")
        finally:
            os.fsync = real_fsync
        self.assertTrue(calls, "_atomic_write 必须 fsync 才能兑现断电不丢的承诺")

    def test_language_files_share_ui_key_set(self):
        import configparser
        def ui_keys(fname):
            cp = configparser.ConfigParser(strict=False, interpolation=None)
            cp.optionxform = str
            cp.read(ROOT / fname, encoding="utf-8-sig")
            return set(cp["UI"].keys())
        self.assertEqual(ui_keys("Chinese.ini"), ui_keys("English.ini"))

    def _fake_import(self, td):
        import types
        fn = _load_with_ns("_import_backup", {"json": json, "BASE": td})
        return fn, types.SimpleNamespace(_BACKUP_FILES=["records.json"])

    def test_backup_import_rejects_oversized_entry(self):
        with tempfile.TemporaryDirectory() as td:
            zp = os.path.join(td, "big.zip")
            with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
                z.writestr("kivo_backup.json", json.dumps({"app": "KIVO", "version": "1"}))
                z.writestr("records.json", " " * (65 * 1024 * 1024))  # 声明 65MB: 读之前就该被拒
            fn, fake = self._fake_import(td)
            with self.assertRaises(ValueError):
                fn(fake, zp)

    def test_backup_import_rejects_wrong_marker_app(self):
        with tempfile.TemporaryDirectory() as td:
            zp = os.path.join(td, "fake.zip")
            with zipfile.ZipFile(zp, "w") as z:
                z.writestr("kivo_backup.json", json.dumps({"app": "OTHER"}))
                z.writestr("records.json", "[]")
            fn, fake = self._fake_import(td)
            with self.assertRaises(ValueError):
                fn(fake, zp)

    def test_backup_import_good_package_lands(self):
        with tempfile.TemporaryDirectory() as td:
            zp = os.path.join(td, "good.zip")
            with zipfile.ZipFile(zp, "w") as z:
                z.writestr("kivo_backup.json", json.dumps({"app": "KIVO", "version": "1"}))
                z.writestr("records.json", '[{"text": "x", "locked": false}]')
            fn, fake = self._fake_import(td)
            fn(fake, zp)
            with open(os.path.join(td, "records.json"), encoding="utf-8") as f:
                self.assertIn('"text": "x"', f.read())

    def test_hardening_source_guards(self):
        atomic = ast.get_source_segment(SOURCE, next(n for n in ast.walk(ast.parse(SOURCE)) if isinstance(n, ast.FunctionDef) and n.name == "_atomic_write"))
        self.assertIn("os.fsync", atomic)
        imp = ast.get_source_segment(SOURCE, next(n for n in ast.walk(ast.parse(SOURCE)) if isinstance(n, ast.FunctionDef) and n.name == "_import_backup"))
        self.assertIn("file_size", imp)  # 读之前先查声明大小
        self.assertIn("dt.astimezone()", SOURCE)  # 约时间换算按目标日期取时区偏移



class AiModelCatalogTests(unittest.TestCase):
    def test_model_catalog_filters_invalid_ids_and_deduplicates(self):
        import io
        from unittest.mock import patch
        fetch = load_function("_ai_fetch_models")

        class FakeResponse:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, _limit):
                return b'{"data":[{"id":"gpt-4o"},{"id":"deepseek-chat"},{"id":"gpt-4o"},{"id":""},{"id":7},{"id":"bad\\nmodel"}]}'

        class FakeApp:
            _http_base = staticmethod(lambda value: value.rstrip("/"))

        with patch("urllib.request.urlopen", return_value=FakeResponse()):
            result = fetch(FakeApp(), {"base": "https://api.example.com/v1", "key": "test"})
        self.assertEqual(result, ["deepseek-chat", "gpt-4o"])

    def test_model_catalog_rejects_oversized_response(self):
        from unittest.mock import patch

        fetch = load_function("_ai_fetch_models")

        class FakeResponse:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return b"x" * limit

        class FakeApp:
            _http_base = staticmethod(lambda value: value.rstrip("/"))

        with patch("urllib.request.urlopen", return_value=FakeResponse()):
            with self.assertRaisesRegex(RuntimeError, "响应过大"):
                fetch(FakeApp(), {"base": "https://api.example.com/v1", "key": "test"})

    def test_model_catalog_has_timeout_and_result_cap(self):
        body = method_text("_ai_fetch_models")
        self.assertIn("timeout=max(3, min(int(timeout), 30))", body)
        self.assertIn("items[:500]", body)
        self.assertIn("2 * 1024 * 1024 + 1", body)

    def test_chat_model_switch_only_changes_chat_route(self):
        body = method_text("_build_ai_panel")
        self.assertIn('self.cfg.set("AI", "RouteChat", svc_key)', body)
        self.assertIn("self._ai_cfg_for(\"chat\")", body)
        self.assertIn("chat_model_box.bind(\"<<ComboboxSelected>>\", switch_chat_model)", body)


class AiStreamingTests(unittest.TestCase):
    def test_stream_parser_emits_tokens_and_returns_combined_content(self):
        from unittest.mock import patch
        fetch = load_function("_ai_chat_messages")
        import json

        class FakeResponse:
            def __init__(self):
                self.lines = [
                    b'data: {"choices":[{"delta":{"content":"Hello "}}]}\\n',
                    b'data: {"choices":[{"delta":{"content":"KIVO"}}]}\\n',
                    b'data: [DONE]\\n',
                ]
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def readline(self, _limit): return self.lines.pop(0) if self.lines else b""
            def read(self, _limit): return b""

        class FakeApp:
            _http_base = staticmethod(lambda value: value.rstrip("/"))
            t = staticmethod(lambda _key, fallback: fallback)

        captured = {}
        def fake_open(req, timeout):
            captured["payload"] = json.loads(req.data.decode("utf-8"))
            captured["timeout"] = timeout
            return FakeResponse()

        pieces = []
        with patch("urllib.request.urlopen", side_effect=fake_open):
            result = fetch(FakeApp(), [{"role": "user", "content": "Hi"}],
                           cfg={"key": "test", "base": "https://api.example.com/v1",
                                "model": "test-model", "service": "openai"},
                           stream_callback=pieces.append)
        self.assertEqual(result, "Hello KIVO")
        self.assertEqual(pieces, ["Hello ", "KIVO"])
        self.assertTrue(captured["payload"]["stream"])
        self.assertEqual(captured["timeout"], 90)

    def test_streaming_source_has_cancel_and_response_limits(self):
        body = method_text("_ai_chat_messages")
        self.assertIn('req_payload["stream"] = True', body)
        self.assertIn('data_line == "[DONE]"', body)
        self.assertIn("cancel_event.is_set()", body)
        self.assertIn("1024 * 1024 + 1", body)
        panel = method_text("_build_ai_panel")
        self.assertIn("def stop_reply():", panel)
        self.assertIn('ev.set()', panel)
        self.assertIn('else "停止"', panel)


if __name__ == "__main__":
    unittest.main()
