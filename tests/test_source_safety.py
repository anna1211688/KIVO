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

    def test_chat_image_history_is_persisted_and_restored_for_followups(self):
        save = method_text("_save_ai_chat_image")
        restore = method_text("_ai_chat_history_messages")
        loader = method_text("_load_ai_chats")
        self.assertIn('return os.path.relpath(path, BASE).replace(os.sep, "/")', save)
        self.assertIn('item.get("image_path")', restore)
        self.assertIn('"image_url"', restore)
        self.assertIn('item["image_path"] = m["image_path"]', loader)
        self.assertIn("self._ai_chat_messages(msgs, max_tokens=2048, route=\"chat\")", SOURCE)

    def test_chat_image_restore_rejects_paths_outside_attachment_folder(self):
        restore = method_text("_ai_chat_history_messages")
        self.assertIn('normalized.startswith("ai_chat_images" + os.sep)', restore)
        self.assertIn('os.path.commonpath((image_root, candidate)) == image_root', restore)
        self.assertIn('os.path.getsize(candidate) <= 8 * 1024 * 1024', restore)

    def test_regenerate_uses_saved_image_history(self):
        start = SOURCE.index("        def regenerate():")
        end = SOURCE.index("        def clear():", start)
        body = SOURCE[start:end]
        self.assertIn("request_reply()", body)
        self.assertNotIn("request_reply(img=", body)
 
    def test_chat_images_are_included_in_backup_export_and_import(self):
        export = method_text("_export_backup")
        restore = method_text("_import_backup")
        self.assertIn('"ai_chat_images/" + filename', export)
        self.assertIn('r"ai_chat_images/[0-9a-f]{32}\.jpg"', restore)
        self.assertIn("total_image_bytes > 128 * 1024 * 1024", restore)
        self.assertIn("with Image.open(BytesIO(data)) as _image: _image.verify()", restore)
        self.assertIn("os.makedirs(os.path.dirname(destination), exist_ok=True)", restore)

    def test_chat_image_backup_rejects_unexpected_names_and_excess_count(self):
        restore = method_text("_import_backup")
        self.assertIn('n.startswith("ai_chat_images/")', restore)
        self.assertIn("len(image_names) > 500", restore)

    def test_attachment_reader_rejects_oversized_before_reading(self):
        read_attachment = _load_with_ns("_read_text_attachment", {})
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "large.txt")
            with open(path, "wb") as f:
                f.write(b"x" * 128)
            with self.assertRaises(ValueError):
                read_attachment(path, max_bytes=64)

    def test_attachment_reader_decodes_and_caps_text(self):
        read_attachment = _load_with_ns("_read_text_attachment", {})
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "sample.txt")
            with open(path, "wb") as f:
                f.write("中文内容".encode("utf-8"))
            self.assertEqual(read_attachment(path), "中文内容")
            self.assertTrue(read_attachment(path, max_chars=2).startswith("中文"))

    def test_ai_history_loader_checks_size_before_read(self):
        body = method_text("_load_ai_chats")
        self.assertIn("os.path.getsize(p) > max_file_bytes", body)
        self.assertIn("f.read(max_file_bytes + 1)", body)
        self.assertIn('len(m["content"]) <= max_message_chars', body)


# ---- 2026-11-27 GPT 审计第一批整改的回归测试 ----

class GptAuditBatch1Tests(unittest.TestCase):
    def test_redact_secrets(self):
        redact = _load_with_ns("_redact_secrets", {"re": re})
        self.assertEqual(redact("Authorization: Bearer abcDEF123-._~+/="), "Authorization: Bearer ***")
        self.assertIn("key=***", redact("https://x.test/v2?key=AIzaSy123456&q=hi"))
        self.assertIn("sk-***", redact("token is sk-abcdefgh12345678 ok"))
        self.assertNotIn("AIzaSy123456", redact("https://x.test/v2?key=AIzaSy123456"))
        self.assertEqual(redact("普通报错: 连接超时"), "普通报错: 连接超时")

    def test_hotkey_conflicts_detected(self):
        find = _load_with_ns("_find_hotkey_conflicts", {})
        out = find([("F7", "粘贴下一条"), ("f7", "删除"), ("F2", "唤出主窗"), ("ctrl+alt+k", "截图"), ("Ctrl+Alt+K", "翻译")])
        self.assertEqual(set(out), {"f7", "ctrl+alt+k"})
        self.assertEqual(find([("F7", "a"), ("F2", "b")]), {})

    def test_gif_fit_caps_both_dimensions(self):
        fit = _load_with_ns("_gif_fit", {})
        self.assertEqual(fit(900, 4000), (162, 720))   # 竖长选区: 旧版只卡宽会留 900x4000
        self.assertEqual(fit(1920, 1080), (960, 540))
        self.assertEqual(fit(800, 600), (800, 600))     # 小图不动
        w, h = fit(3840, 2160)
        self.assertLessEqual(w, 960); self.assertLessEqual(h, 720)

    def test_backup_import_rolls_back_on_replace_failure(self):
        import glob, time as _time, types
        with tempfile.TemporaryDirectory() as td:
            with open(os.path.join(td, "records.json"), "w", encoding="utf-8") as f: f.write('[{"text": "old-r"}]')
            with open(os.path.join(td, "phrases.json"), "w", encoding="utf-8") as f: f.write('[{"text": "old-p"}]')
            zp = os.path.join(td, "in.zip")
            with zipfile.ZipFile(zp, "w") as z:
                z.writestr("kivo_backup.json", json.dumps({"app": "KIVO", "version": "1"}))
                z.writestr("records.json", '[{"text": "new-r"}]')
                z.writestr("phrases.json", '[{"text": "new-p"}]')
            ns = {"json": json, "time": _time, "BASE": td, "VERSION": "1.4.30"}
            export = _load_with_ns("_export_backup", ns)
            imp = _load_with_ns("_import_backup", ns)
            fake = types.SimpleNamespace(_BACKUP_FILES=["records.json", "phrases.json"])
            fake._export_backup = lambda p: export(fake, p)
            real_replace = os.replace
            calls = {"n": 0}
            def flaky_replace(a, b):
                calls["n"] += 1
                if calls["n"] == 3: raise OSError("simulated replace failure")  # 1=导入前备份, 2=records, 3=phrases(失败)
                return real_replace(a, b)
            os.replace = flaky_replace
            try:
                with self.assertRaises(OSError):
                    imp(fake, zp)
            finally:
                os.replace = real_replace
            with open(os.path.join(td, "records.json"), encoding="utf-8") as f: self.assertEqual(f.read(), '[{"text": "old-r"}]')
            with open(os.path.join(td, "phrases.json"), encoding="utf-8") as f: self.assertEqual(f.read(), '[{"text": "old-p"}]')
            self.assertTrue(glob.glob(os.path.join(td, "kivo_pre_import_*.zip")), "导入前应留一份自动备份")

    def test_ai_chat_history_caps_stay(self):
        body = method_text("_persist_chat")
        self.assertIn("del self._ai_chats[30:]", body)   # 对话总数封顶 (比 GPT 建议的 100 还严)
        self.assertIn("[-200:]", body)                  # 单对话消息封顶

    def test_ocr_inference_is_serialized(self):
        body = method_text("_ocr_rapid_lines")
        self.assertIn("with cls._ocr_infer_lock", body)

    def test_download_has_filesize_cap(self):
        self.assertIn('"max_filesize"', method_text("_build_dl_panel"))


# ---- 2026-11-27 AI 助手第一批整改 (侧栏/气泡自适应/输入区/品牌色) 的守卫 ----

class AiPanelBatch1Tests(unittest.TestCase):
    def test_brand_accent_unified(self):
        self.assertIn('UI_ACCENT = "#3B82F6"', SOURCE)
        self.assertIn('UI_ACCENT_HOVER = "#60A5FA"', SOURCE)
        self.assertIn('UI_ACCENT_PRESS = "#2563EB"', SOURCE)
        self.assertNotIn('UI_ACCENT = "#287FD1"', SOURCE)

    def test_ai_sidebar_224_blue_gray(self):
        body = method_text("_build_ai_panel")
        self.assertIn('SIDE_BG = "#F2F6FB"', body)
        self.assertIn("width=224", body)

    def test_bubble_width_adaptive(self):
        body = method_text("_build_ai_panel")
        self.assertIn("def _bubble_wrap_w", body)
        self.assertIn("max(348, min(680", body)          # 折行宽夹在 [348, 680], 随聊天区宽度走
        self.assertIn("wrap_px(text, _bubble_wrap_w())", body)
        self.assertNotIn("wrap_px(text, 348)", body)     # 旧写死值不许回来

    def test_input_area_taller(self):
        body = method_text("_build_ai_panel")
        self.assertIn("height=76", body)                 # 输入区画布 62 -> 76
        self.assertIn("height=58", body)                 # 输入框窗口 44 -> 58
        self.assertNotIn('inbox = tk.Canvas(brow, height=62', body)


# ---- 2026-11-27 UI 现代化第一批 (深色边栏) 的一致性守卫 ----

class UiPhase1Tests(unittest.TestCase):
    def test_sidebar_dark_palette_is_consistent(self):
        body = method_text("build_ui")
        self.assertIn('SIDE = "#172235"', body)
        self.assertIn("side = tk.Frame(self, background=SIDE", body)   # 外框必须同色 (PR #6 漏改处)
        self.assertIn("brand = tk.Frame(side, background=SIDE)", body)  # 品牌区框架必须同色 (PR #6 漏改处)
        seg_start = body.find("side = tk.Frame")
        seg = body[seg_start:body.find("body = tk.Frame", seg_start)]
        self.assertNotIn("background=W", seg)  # 边栏内不许再留白色底子元素
        self.assertNotIn("bg=W", seg)

    def test_nav_item_dark_text_colors(self):
        seg = SOURCE[SOURCE.find("class _NavItem"):SOURCE.find("class App")]
        self.assertIn('"#3B82F6"', seg)   # 选中胶囊品牌蓝
        self.assertIn('"#C9D6E8"', seg)   # 未选浅灰蓝字 (旧值 #1C2634 在深底上不可读)
        self.assertNotIn('"#1C2634"', seg)

    def test_primary_button_brand_color(self):
        self.assertIn('"primary": ("#3B82F6", "#3B82F6", "#FFFFFF", "#60A5FA")', SOURCE)


if __name__ == "__main__":
    unittest.main()
