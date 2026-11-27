"""Source-level regression guards for the Windows app's safety-critical paths.

These tests intentionally avoid importing the Tk application so they can run on
CI hosts without a desktop session or the optional Windows dependencies.
"""
import ast
import json
import os
import re
import time
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


# 纯函数依赖 (不联网): 附件解析的上限常量/异常/读条目封装, 供被单独 exec 的函数使用
PURE_MODULE_HELPERS = (
    "_ATTACH_INFLATE_LIMIT", "_ATTACH_TEXT_LIMIT", "_ATTACH_ENTRY_LIMIT",
    "_AttachLimit", "_zip_read_bytes", "MAX_RECORDS",
)


def _helper_nodes():
    out = []
    for node in TREE.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in PURE_MODULE_HELPERS:
            out.append(node)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in PURE_MODULE_HELPERS:
                    out.append(node)
    return out


def _base_ns():
    ns = {"os": os, "re": re, "json": json, "time": time}
    for node in _helper_nodes():
        exec(ast.get_source_segment(SOURCE, node), ns)
    return ns


def module_text(name):
    node = next(n for n in TREE.body if isinstance(n, ast.FunctionDef) and n.name == name)
    return ast.get_source_segment(SOURCE, node)


def load_function(name):
    node = app_method(name)
    ns = _base_ns()
    exec(ast.get_source_segment(SOURCE, node), ns)
    fn = ns[name]
    return fn.__func__ if isinstance(fn, staticmethod) else fn


def load_module_function(name):
    node = next(n for n in TREE.body if isinstance(n, ast.FunctionDef) and n.name == name)
    ns = _base_ns()
    exec(ast.get_source_segment(SOURCE, node), ns)
    return ns[name]


class SafetyRegressionTests(unittest.TestCase):
    def test_main_module_parses(self):
        compile(SOURCE, str(ROOT / "main.py"), "exec")

    def test_paste_queue_only_consumes_after_success(self):
        # 粘贴本身有 30ms+150ms 固定等待, 已移到后台线程: 判定"粘成功才消费"的不变量在 _paste_next_apply 里
        body = method_text("paste_next")
        self.assertIn("ok = self._paste_text(", body)
        self.assertIn("_paste_next_apply(", body)
        apply_body = method_text("_paste_next_apply")
        self.assertIn("if ok and self.paste_remove_var.get()", apply_body)
        self.assertLess(apply_body.index("if ok and self.paste_remove_var.get()"), apply_body.index("del self.records"))

    def test_paste_reports_failure_for_self_window_and_failed_input(self):
        body = method_text("_paste_text")
        self.assertIn("if self._foreground_is_self(): return False", body)
        self.assertIn("pasted = bool(self._type_text(text))", body)
        self.assertIn("pasted = bool(self._send_combo(0x56))", body)
        self.assertIn("if pasted:", body)
        self.assertIn("return pasted", body)

    def test_copy_requires_command_and_clipboard_change(self):
        # 抓取等待已移到后台线程, 入队部分在 _multi_copy_apply 里
        body = method_text("multi_copy") + method_text("_multi_copy_apply")
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
import textwrap  # json/re 文件头已导入, 这里不重复 (ruff F811); textwrap 只有本节用得到
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
        self.assertIn("self._ai_chat_messages(msgs, max_tokens=2048, route=\"chat\",", SOURCE)

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
        self.assertIn('UI_ACCENT = "#007AFF"', SOURCE)
        self.assertIn('UI_ACCENT_HOVER = "#409CFF"', SOURCE)
        self.assertIn('UI_ACCENT_PRESS = "#0062CC"', SOURCE)
        self.assertNotIn('UI_ACCENT = "#287FD1"', SOURCE)

    def test_ai_sidebar_224_blue_gray(self):
        body = method_text("_build_ai_panel")
        self.assertIn('SIDE_BG = "#F5F5F7"', body)   # Sonoma: 会话列用苹果灰, 与主内容底分层
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
        self.assertIn("SIDE = self.UI_SIDE", body)          # 2026-11-28: 边栏底色收敛到令牌
        self.assertIn('UI_SIDE = "#F5F5F7"', SOURCE)
        self.assertIn("side = tk.Frame(self, background=SIDE", body)   # 外框必须同色 (PR #6 漏改处)
        self.assertIn("brand = tk.Frame(side, background=SIDE)", body)  # 品牌区框架必须同色 (PR #6 漏改处)
        seg_start = body.find("side = tk.Frame")
        seg = body[seg_start:body.find("body = tk.Frame", seg_start)]
        self.assertNotIn("background=W", seg)  # 边栏内不许再留白色底子元素
        self.assertNotIn("bg=W", seg)

    def test_nav_item_light_palette(self):
        seg = SOURCE[SOURCE.find("class _NavItem"):SOURCE.find("class App")]
        self.assertIn('"#D1D1D6"', seg)   # 选中=中性灰圆角块
        self.assertIn('"#E8E8ED"', seg)   # 悬停浅灰
        self.assertNotIn('"#C9D6E8"', seg)  # 旧深栏配色不许回来

    def test_primary_button_brand_color(self):
        self.assertIn('"primary": ("#007AFF", "#007AFF", "#FFFFFF", "#409CFF")', SOURCE)



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
            def t(self, _key, default=""): return default  # _ai_fetch_models 的报错文案走 t() (2026-11-27 i18n 修正后)

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
                    b'data: {"choices":[{"delta":{"content":"Hello "}}]}\n',
                    b'data: {"choices":[{"delta":{"content":"KIVO"}}]}\n',
                    b'data: [DONE]\n',
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
        self.assertEqual(captured["timeout"], 45)  # 流式打开超时封顶 45s: 服务端静默时「停止」不必等满 90s

    def test_streaming_source_has_cancel_and_response_limits(self):
        body = method_text("_ai_chat_messages")
        self.assertIn('req_payload["stream"] = True', body)
        self.assertIn('data_line == "[DONE]"', body)
        self.assertIn("cancel_event.is_set()", body)
        self.assertIn("1024 * 1024 + 1", body)
        panel = method_text("_build_ai_panel")
        self.assertIn("def stop_reply():", panel)
        self.assertIn('ev.set()', panel)
        self.assertIn('self.t("ai_stop", "停止")', panel)


class AiTaskModelRoutingTests(unittest.TestCase):
    def test_task_route_can_select_a_specific_enabled_model_profile(self):
        body = method_text("_ai_cfg_for")
        self.assertIn('rk + "Model"', body)
        self.assertIn('"ModelProfiles"', body)
        self.assertIn('if allowed: c["model"] = model', body)

    def test_chat_quick_switch_persists_provider_and_model(self):
        body = method_text("_build_ai_panel")
        self.assertIn('self.cfg.set("AI", "RouteChatModel", model_id)', body)
        self.assertIn('chat_model_map[label] = (svc_key, model_id)', body)

    def test_task_model_routes_and_optional_same_provider_fallback(self):
        form = method_text("_build_ai_form")
        self.assertIn('route_choice_maps[label] = (svc_key, profile["model"])', form)
        self.assertIn('routes[rk], routes[rk + "Model"] = route_choice_maps[choice]', form)
        self.assertIn('"AutoFallback"', form)
        self.assertIn("time.monotonic()", form)
        self.assertIn("连接正常 · 响应", form)
        self.assertIn("连接失败 ·", form)
        chat = method_text("_ai_chat_messages")
        self.assertIn("Optional same-provider failover", chat)
        self.assertIn('profile.get("enabled", True)', chat)
        self.assertIn("stream_callback is not None", chat)


class AiModelCenterLayoutTests(unittest.TestCase):
    def test_model_center_uses_top_horizontal_tabs(self):
        body = method_text("_build_ai_form")
        self.assertIn("ttk.Notebook(parent)", body)
        self.assertIn('notebook.add(model_tab, text=self.t("ai_mc_tab_models", "模型列表"))', body)
        self.assertIn('notebook.add(provider_tab, text=self.t("ai_mc_tab_providers", "服务商配置"))', body)
        self.assertIn('notebook.add(route_tab, text=self.t("ai_mc_tab_routes", "任务分配"))', body)
        self.assertIn('notebook.add(test_tab, text=self.t("ai_mc_tab_test", "连接测试"))', body)

    def test_model_center_lists_every_provider_and_keeps_separate_settings(self):
        body = method_text("_build_ai_form")
        self.assertIn("for svc_key in self._AI_PRESETS:", body)
        self.assertIn('columns = ("provider", "model", "status", "default")', body)
        self.assertIn("store[svc_key]", body)
        self.assertIn("self._save_ai_settings(cur[\"service\"], store, routes)", body)

    def test_model_center_persists_multi_model_profiles_and_management_actions(self):
        body = method_text("_build_ai_form")
        self.assertIn('"ModelProfiles"', body)
        self.assertIn("json.loads", body)
        self.assertIn("def add_current_model():", body)
        self.assertIn("def set_selected_default():", body)
        self.assertIn("def toggle_selected_model():", body)
        self.assertIn("def delete_selected_model():", body)
        self.assertIn('json.dumps(profiles', body)


# ---- 2026-11-27 PR #13 审查修正 (模型中心 i18n/候选刷新/切换器/脱敏) 的守卫 ----

class ModelCenterFixTests(unittest.TestCase):
    def test_model_center_uses_i18n(self):
        body = method_text("_build_ai_form")
        self.assertIn('ai_mc_tab_models', body)
        self.assertIn('ai_mc_tab_providers', body)
        self.assertIn('ai_mc_fallback', body)
        self.assertNotIn('notebook.add(model_tab, text="模型列表")', body)
        self.assertNotIn('text="连接测试")', body)
        self.assertNotIn('text="测试当前服务商"', body)

    def test_route_choices_rebuild_on_tab(self):
        body = method_text("_build_ai_form")
        self.assertIn("def rebuild_route_choices", body)
        self.assertIn("<<NotebookTabChanged>>", body)

    def test_chat_switcher_no_fake_current(self):
        self.assertNotIn("chat_model_var.set(values[0])", SOURCE)

    def test_fetch_models_error_redacted(self):
        body = method_text("_ai_fetch_models")
        self.assertIn("_redact_ai_detail(", body)

    def test_ai_http_error_diagnostics_redact_secrets_and_bound_output(self):
        body = method_text("_ai_chat_messages")
        self.assertIn('e.read(2048)', body)
        self.assertIn('_redact_ai_detail(detail, cfg.get("key") or "")', body)
        self.assertNotIn('_redact_ai_detail(detail, secret)', body)  # 曾有先用后赋值 secret 的真 bug (合并 #13 时抓到)
        self.assertIn('[:160]', body)
        self.assertIn('err._kivo_status = e.code', body)


# ---- 2026-11-27 GPT 审查批 (PR #13 后续): 脱敏补漏/错误分类/故障切换上限/流式停滞上限 ----

class AiEngineHardeningTests(unittest.TestCase):
    def test_redact_ai_detail_blocks_known_leak_shapes(self):
        fn = load_module_function("_redact_ai_detail")
        fn.__globals__["re"] = re
        cases = [
            ('Bearer KEYVAL1', 'KEYVAL1'),
            ('{"api_key": "KEYVAL2"}', 'KEYVAL2'),
            ('{"error": "bad key sk-plain777 in request"}', 'sk-plain777'),
            ('x-api-key: KEYVAL4', 'KEYVAL4'),
            ('GET https://h/v1?key=AIzaSyD1234567890x failed', 'AIzaSyD1234567890x'),
            ('Authorization: Bearer KEYVAL6 rest', 'KEYVAL6'),
            ('token=KEYVAL7&other=1', 'KEYVAL7'),
            ('access_token: KEYVAL8', 'KEYVAL8'),
        ]
        for raw, leaked in cases:
            self.assertNotIn(leaked, fn(raw, "mine"), raw)
        # 正常报错文案不许误伤
        plain = '{"error": {"code": 1210, "message": "max_tokens=1024 exceeded"}}'
        self.assertEqual(fn(plain, "mine"), plain)

    def test_failover_classification_and_caps(self):
        body = method_text("_ai_chat_messages")
        self.assertIn('getattr(primary_error, "_kivo_status", None) in (401, 403)', body)
        self.assertIn("tried >= 2", body)
        self.assertIn("open_timeout = min(timeout, 45)", body)


# ---- 2026-11-27 AI 第二批: 长期记忆 + PDF/Word/Excel 附件解析 ----

class AiMemoryAndFilesTests(unittest.TestCase):
    def test_memory_system_text(self):
        fn = load_function("_memory_system_text")
        self.assertEqual(fn([], "HEAD"), "")
        self.assertEqual(fn([{"text": "喜欢简洁回复"}], "HEAD"), "HEAD\n- 喜欢简洁回复")
        big = fn([{"text": "x" * 600}] * 20, "HEAD")
        self.assertLessEqual(len(big), 4000)

    def test_memory_wiring(self):
        self.assertIn('"ai_memory.json"', SOURCE)                       # 进备份清单
        panel = method_text("_build_ai_panel")
        self.assertIn("_memory_system_text", panel)                     # 聊天时注入
        self.assertIn('"role": "system"', panel)
        self.assertIn("_open_ai_memory_window", panel)                  # 顶栏有管理入口

    def test_pdf_extract(self):
        import zlib
        fn = load_module_function("_extract_pdf_text")
        fn.__globals__["_pdf_decode_text"] = load_module_function("_pdf_decode_text")
        fn.__globals__["_pdf_unescape_literal"] = load_module_function("_pdf_unescape_literal")
        content = b"BT /F1 12 Tf (Hello KIVO) Tj ET\n<FEFF4F60> Tj"
        pdf = b"%PDF-1.4\nstream\n" + zlib.compress(content) + b"\nendstream\n%%EOF"
        text = fn(pdf)
        self.assertIn("Hello KIVO", text)
        self.assertIn("你", text)                                       # UTF-16BE 十六进制串
        self.assertEqual(fn(b"not a pdf at all"), "")

    def test_docx_extract(self):
        import io, zipfile
        fn = load_module_function("_extract_docx_text")
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("word/document.xml",
                       '<w:document><w:body>'
                       '<w:p><w:r><w:t>第一段</w:t></w:r></w:p>'
                       '<w:p><w:r><w:t>Second &amp; para</w:t></w:r></w:p>'
                       '</w:body></w:document>')
        text = fn(buf.getvalue())
        self.assertIn("第一段", text)
        self.assertIn("Second & para", text)

    def test_xlsx_extract(self):
        import io, zipfile
        fn = load_module_function("_extract_xlsx_text")
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("xl/sharedStrings.xml",
                       '<sst><si><t>名称</t></si><si><t>数量</t></si></sst>')
            z.writestr("xl/worksheets/sheet1.xml",
                       '<worksheet><sheetData><row>'
                       '<c t="s"><v>0</v></c><c t="s"><v>1</v></c><c><v>42</v></c>'
                       '</row></sheetData></worksheet>')
        text = fn(buf.getvalue())
        self.assertIn("名称\t数量\t42", text)

    def test_attach_dispatch(self):
        body = method_text("_read_attach_text")
        self.assertIn("_extract_pdf_text", body)
        self.assertIn("_extract_docx_text", body)
        self.assertIn("_extract_xlsx_text", body)
        self.assertIn("12 * 1024 * 1024", body)

    def test_docx_zip_bomb_rejected(self):
        """0.5MB 的 docx 能解出几百 MB: 必须在解压前用元数据拦下 (v1.5.1)"""
        import io, zipfile
        fn = load_module_function("_extract_docx_text")
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("word/document.xml", "<w:p>" + "<w:t>x</w:t>" * (9 * 1024 * 1024 // 12) + "</w:p>")
        self.assertLess(len(buf.getvalue()), 1024 * 1024)  # 压缩后很小, 走"元数据拦截"路径
        with self.assertRaises(fn.__globals__["_AttachLimit"]):
            fn(buf.getvalue())

    def test_zip_entry_bomb_rejected(self):
        import io, zipfile
        fn = load_module_function("_extract_docx_text")
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            for i in range(2100):
                z.writestr(f"junk{i}.bin", "")
            z.writestr("word/document.xml", "<w:p><w:t>x</w:t></w:p>")
        with self.assertRaises(fn.__globals__["_AttachLimit"]):
            fn(buf.getvalue())

    def test_pdf_stream_limit(self):
        body = module_text("_extract_pdf_text")
        self.assertIn("decompressobj()", body)
        self.assertIn("_ATTACH_INFLATE_LIMIT", body)

    def test_redirect_guard_on_ai_paths(self):
        """302 到别的域名时 urllib 会把 Authorization 一起带过去: AI 请求必须走同主机校验的封装"""
        for name in ("_ai_chat_messages", "_ai_fetch_models", "_baidu_translate", "_google_translate"):
            self.assertIn('globals().get("_open_url")', method_text(name), name)
        # 同主机跳转防护已收进统一 opener 工厂 (strict=True 时挂载), _open_url 走 strict 分支
        guard = module_text("_build_net_opener")
        self.assertIn("HTTPRedirectHandler", guard)
        self.assertIn("hostname", guard)
        self.assertIn("_build_net_opener(True)", module_text("_open_url"))


class RecordQueueTests(unittest.TestCase):
    """记录队列: 批量导入与单条上限 (v1.5.1 去 O(n²) + 防超长条)"""

    class _Case:
        def __init__(self, v=""): self.v = v
        def get(self): return self.v

    def _app(self, n=0, case=""):
        class Stub: pass
        s = Stub()
        s.records = [{"text": f"旧记录 {i}", "locked": False} for i in range(n)]
        s.case_var = self._Case(case); s.paste_index = 0
        s.save_records = lambda *a, **k: None
        s._RECORD_MAX_CHARS = 200000
        return s

    def test_bulk_import_matches_add_record_rules(self):
        fn = load_function("_merge_import_lines")
        s = self._app(3)
        self.assertEqual(fn(s, ["旧记录 0", "", "   ", "新条目", "新条目"]), 1)
        self.assertEqual(s.records[-1]["text"], "新条目")
        self.assertEqual(len(s.records), 4)

    def test_bulk_import_respects_case_switch(self):
        fn = load_function("_merge_import_lines")
        s = self._app(0, "转大写")
        fn(s, ["abc"])
        self.assertEqual(s.records[-1]["text"], "ABC")
        self.assertEqual(fn(s, ["ABC"]), 0)  # 转大写后与已有重复, 不重复入队

    def test_bulk_import_caps_total_records(self):
        fn = load_function("_merge_import_lines")
        s = self._app(1990)
        fn(s, [f"新 {i}" for i in range(50)])
        self.assertEqual(len(s.records), 2000)

    def test_record_length_capped(self):
        fn = load_function("add_record")
        s = self._app(0)
        fn(s, "长" * 300000)
        self.assertLessEqual(len(s.records[-1]["text"]), 200000 + 20)
        self.assertIn("已截断", s.records[-1]["text"])

    def test_bulk_import_keeps_locked_records(self):
        fn = load_function("_merge_import_lines")
        s = self._app(0)
        s.records = [{"text": f"锁 {i}", "locked": True} for i in range(2000)]
        fn(s, ["新的一条"])
        self.assertEqual(len(s.records), 2000)  # 全锁定: 上限是硬线, 新条不入队
        self.assertTrue(all(r["locked"] for r in s.records))


class RoundThreePolishTests(unittest.TestCase):
    """第三轮 (2026-11-28): 版本号比较、备份导出非阻塞、截图目录自愈、长对话分帧"""

    def test_patch_release_beats_base(self):
        f = load_function("_ver_tuple")
        self.assertGreater(f("1.5.0.1"), f("1.5.0"))          # 旧版 [:3] 截断会把补丁版判成相等 -> 不提示更新
        self.assertGreater(f("v1.5.1"), f("1.5.0"))
        self.assertGreater(f("1.10.0"), f("1.9.9"))           # 字符串比较会错, 逐位数字比较才对
        self.assertEqual(f("1.5.0"), f("v1.5.0"))
        self.assertEqual(f("1.5"), f("1.5.0"))

    def test_prerelease_sorts_before_release(self):
        f = load_function("_ver_tuple")
        self.assertLess(f("1.5.0-beta1"), f("1.5.0"))
        self.assertGreater(f("1.6.0"), f("1.5.0-beta9"))

    def test_version_compare_used_by_update_check(self):
        self.assertIn("self._ver_tuple(tag) > self._ver_tuple(VERSION)", SOURCE)

    def test_backup_export_is_off_main_thread(self):
        text = method_text("_backup_export_dialog")
        self.assertIn("threading.Thread", text)
        self.assertIn("_bak_busy", text)
        self.assertIn("save_records(immediate=True)", text)   # 打包前仍要把最新数据刷盘

    def test_backup_import_guards_and_prepaints(self):
        text = method_text("_backup_import_dialog")
        self.assertIn("update_idletasks()", text)
        self.assertIn("_bak_busy", text)
        self.assertEqual(text.count("askyesno"), 1)           # 只问一次

    def test_refresh_shots_recreates_missing_dir(self):
        text = method_text("refresh_shots")
        self.assertIn("FileNotFoundError", text)
        self.assertIn("makedirs", text)

    def test_prune_shots_tolerates_vanished_files(self):
        self.assertIn("getmtime", method_text("_prune_shots"))
        self.assertIn("def _mtime", method_text("_prune_shots"))

    def test_chat_history_renders_in_frames(self):
        text = SOURCE.split("def render_all():", 1)[1][:2600]   # 嵌套在 AI 面板里, 不是 App 的直接方法
        self.assertIn("_chat_render_gen", text)               # 代次守卫: 切对话时丢弃上一轮
        self.assertIn("self.after(1", text)
        self.assertIn("len(hist) <= 20", text)                 # 短对话仍同步一次画完
        self.assertIn("pending_render", text)                  # 发送新消息前先冲刷, 保证气泡顺序


class ChatImageGcTests(unittest.TestCase):
    """孤儿聊天图片清理: 只删本程序命名、24 小时前、无对话引用的 jpg"""

    def _run(self, refs, files):
        fn = load_function("_gc_chat_images")
        td = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(td, ignore_errors=True))
        folder = os.path.join(td, "ai_chat_images"); os.makedirs(folder)
        chats = os.path.join(td, "ai_chats.json")
        with open(chats, "w", encoding="utf-8") as f:
            json.dump(refs, f)
        old = time.time() - 30 * 3600
        for name, age in files.items():
            p = os.path.join(folder, name)
            with open(p, "wb") as f: f.write(b"x")
            os.utime(p, (time.time() - age, time.time() - age))
        fn.__globals__["BASE"] = td
        fn.__globals__["AI_CHATS_PATH"] = chats
        removed = fn(None)  # 方法里没用到 self: 传 None 即可
        return removed, sorted(os.listdir(folder))

    def test_orphan_old_image_removed(self):
        kept, orphan = "a" * 32 + ".jpg", "b" * 32 + ".jpg"
        n, left = self._run([{"messages": [{"image_path": "ai_chat_images/" + kept}]}],
                            {kept: 30 * 3600, orphan: 30 * 3600})
        self.assertEqual(n, 1)
        self.assertEqual(left, [kept])

    def test_recent_orphan_kept_as_grace(self):
        orphan = "c" * 32 + ".jpg"
        n, left = self._run([], {orphan: 60})
        self.assertEqual((n, left), (0, [orphan]))

    def test_foreign_files_untouched(self):
        n, left = self._run([], {"note.txt": 30 * 3600, "README": 30 * 3600})
        self.assertEqual((n, left), (0, ["README", "note.txt"]))


class UiRedesignPhase1Tests(unittest.TestCase):
    """2026-11-28 整套 UI 重设计 P1: 令牌层 + 信息层级 (一屏一个主按钮)"""

    def test_design_tokens_exist(self):
        for token in ("UI_TEXT_2", "UI_BORDER_STRONG", "UI_ACCENT_TINT", "UI_ACCENT_LINE",
                      "UI_DANGER", "UI_DANGER_BG", "UI_SIDE", "UI_SIDE_TEXT", "UI_SIDE_ACTIVE_BG"):
            self.assertIn(token + " = \"#", SOURCE, token)
        for token in ("SP_1, SP_2, SP_3, SP_4, SP_5, SP_6 = 4, 8, 12, 16, 24, 32",
                      "R_CARD, R_BTN, R_INPUT, R_PILL = 12, 8, 8, 999",
                      "DUR_FAST, DUR_BASE = 120, 180"):
            self.assertIn(token, SOURCE)

    def test_type_scale_is_single_source(self):
        self.assertIn('TYPE = {"brand": 18, "page": 15, "card": 11, "body": 10, "caption": 9, "micro": 8}', SOURCE)

    def test_sidebar_selection_uses_neutral_gray(self):
        seg = SOURCE[SOURCE.find("class _NavItem"):SOURCE.find("class App")]
        self.assertIn('fill=self._pal["active"]', seg)   # 选中=中性灰圆角块 (苹果侧栏)
        self.assertNotIn('create_rectangle(0, 10, 3, 30', seg)  # 旧深色栏的蓝色指示条已移除
        self.assertNotIn('fill = "#3B82F6" if self._selected', seg)

    def test_records_header_has_one_menu_for_destructive_actions(self):
        body = method_text("build_ui")
        self.assertNotIn('for txt, cmd in [(self.t("lock_unlock"', body)  # 六按钮平铺已移除
        self.assertIn("def _record_more(btn)", body)
        self.assertIn('self.t("delete_all", "删除全部")', body)          # 功能仍可达
        self.assertIn('"color": self.UI_DANGER', body)                      # 危险项用文字色区分

    def test_action_row_keeps_one_primary(self):
        body = method_text("build_ui")
        row = body[body.find("act = tk.Frame(body"):body.find("def card_section")]
        self.assertEqual(row.count("Accent.TButton"), 1)
        for key in ("paste_selected", "import_txt", "export_txt"):
            self.assertIn("self." + key, row)   # 收进「更多操作」后命令仍在

    def test_list_rows_taller_and_softer_stripes(self):
        self.assertIn("rowheight=34", SOURCE)
        self.assertIn('UI_STRIPE = "#FAFAFC"', SOURCE)


class UiRedesignPhase15Tests(unittest.TestCase):
    """2026-11-28 全面统一 (P1.5): 行状态、空状态、旧色值清零"""

    def test_list_rows_have_locked_and_hover_states(self):
        body = method_text("build_ui")
        self.assertIn('tag_configure("locked", foreground=self.UI_MUTED_2)', body)
        self.assertIn('tag_configure("hover", background=self.UI_ACCENT_TINT)', body)
        self.assertIn("self._bind_list_hover()", body)

    def test_row_tags_helper_used_everywhere(self):
        self.assertNotIn('tags=("odd",) if row % 2 else ()', SOURCE)   # 三处插入点都必须走 helper
        self.assertIn("def _row_tags(self, row, locked):", SOURCE)
        self.assertEqual(SOURCE.count("tags=self._row_tags("), 3)

    def test_hover_does_not_touch_selection(self):
        seg = SOURCE[SOURCE.find("def _bind_list_hover"):SOURCE.find("def _update_empty_state")]
        self.assertIn('self.listbox.bind("<Motion>"', seg)
        self.assertIn('t != "hover"', seg)          # 只摘 hover, 不动 odd/locked
        self.assertNotIn("selection_set", seg)

    def test_empty_state_created_and_toggled(self):
        self.assertIn("self._empty_state = tk.Frame(mid, background=W)", method_text("build_ui"))
        self.assertIn('empty_rec_title', SOURCE)
        body = method_text("refresh_list")
        self.assertEqual(body.count("self._update_empty_state()"), 2)   # 隐藏分支 + 正常分支都要刷新

    def test_old_palette_literals_gone(self):
        for legacy in ('"#5B6B7C"', '"#1C2634"', '"#1E90FF"', '"#0B3556"', '"#2F4B73"'):
            self.assertNotIn(legacy, SOURCE, legacy)

    def test_check_indicator_uses_brand_blue(self):
        self.assertIn("(59, 130, 246, 255)", SOURCE)   # 勾选圆点 = 品牌蓝, 不再是绿色第二主色
        self.assertNotIn("(34, 181, 115, 255)", SOURCE)


if __name__ == "__main__":
    unittest.main()


class UiPhase2Tests(unittest.TestCase):
    """UI P2 (2026-11-28): toast/撤销、主窗口真圆角卡片、常用语与画廊空状态。
    仍是源码级断言: 无 GUI 环境下要保证「只动外观, 不动功能」。"""

    @classmethod
    def setUpClass(cls):
        cls.src = open(os.path.join(ROOT, "main.py"), encoding="utf-8").read()

    def test_toast_overlay_exists_and_does_not_steal_focus(self):
        self.assertIn("def toast(self, text, action=None, action_text=None, ms=2400):", self.src)
        self.assertIn("def _hide_toast(self, seq=None):", self.src)
        i = self.src.index("def toast(self, text, action=None")
        body = self.src[i:i + 2200]
        self.assertIn('place(relx=0.5, rely=1.0, anchor="s"', body)  # 叠在主窗口底部, 不新开窗口
        self.assertNotIn("grab_set", body)  # 不抢焦点
        self.assertNotIn("wait_window", body)  # 不阻塞主线程
        self.assertIn("self._toast_seq", body)  # 序号防旧定时器关掉新提示

    def test_delete_has_undo_and_restores_paste_index(self):
        i = self.src.index("def delete_sel(self):")
        body = self.src[i:i + 1200]
        self.assertIn("rec = self.records.pop(i)", body)
        self.assertIn("self.records.insert(pos, rec)", body)
        self.assertIn("self.paste_index = max(0, min(old_pi, len(self.records)))", body)
        self.assertIn("action=_undo", body)
        self.assertIn("save_records(); self.refresh_list()", body)
        # 锁定记录仍然不许删
        self.assertIn("msg_locked", body)

    def test_main_cards_use_rounded_backing(self):
        self.assertIn("card = tk.Frame(body, background=self.UI_BG)\n        self._rounded_backing(card, radius=self.R_CARD)", self.src)
        self.assertIn("outer = tk.Frame(body, background=self.UI_BG)\n            self._rounded_backing(outer, radius=self.R_CARD)", self.src)
        # 旧的方角描边卡片不能残留
        self.assertNotIn('highlightbackground=self.UI_BORDER, highlightcolor=self.UI_BORDER)\n        card.pack', self.src)

    def test_empty_states_present(self):
        self.assertIn("gal_empty_title", self.src)
        self.assertIn("self.t(\"empty_rec_btn\"", self.src)  # 画廊空态直接给「截一张图」入口
        self.assertIn("phr_empty_title", self.src)
        self.assertIn("_phr_empty.place_forget()", self.src)
        self.assertIn("else: _phr_empty.place(relx=0.5, rely=0.34, anchor=\"center\")", self.src)

    def test_ui_tokens_for_p2(self):
        self.assertIn('UI_ACCENT_LINE = "#99C2FF"', self.src)
        self.assertIn("R_CARD", self.src)


class UiPhase3Tests(unittest.TestCase):
    """UI P3 (2026-11-28): 全局控件交互态令牌化 + 旧灰文字收口 + 迷你窗口重排。"""

    @classmethod
    def setUpClass(cls):
        cls.src = open(os.path.join(ROOT, "main.py"), encoding="utf-8").read()

    def test_interaction_tokens_defined(self):
        for tok, val in (("UI_HOVER", "#E5F0FF"), ("UI_PRESS", "#CCE4FF"),
                         ("UI_DANGER_LINE", "#FFB4B0"), ("UI_DANGER_HOVER", "#FFDCD9"), ("UI_DANGER_PRESS", "#FFC9C5")):
            self.assertIn(f'{tok} = "{val}"', self.src)

    def test_theme_maps_use_tokens_not_old_tints(self):
        self.assertNotIn('"#E3EEFF"', self.src)  # 旧 hover 底
        self.assertNotIn('"#CFE2FF"', self.src)  # 旧按下底
        self.assertNotIn('"#FDECEC"', self.src)  # 旧危险底
        self.assertNotIn('bordercolor="#BCD6FF"', self.src)
        self.assertIn('st.map("TButton", background=[("active", self.UI_HOVER), ("pressed", self.UI_PRESS)]', self.src)
        self.assertIn('st.configure("Danger.TButton", background=self.UI_DANGER_BG, foreground=self.UI_DANGER', self.src)

    def test_old_muted_gray_replaced(self):
        self.assertNotIn('foreground="#888888"', self.src)

    def test_mini_window_layout(self):
        self.assertIn('w.geometry(f"320x400+', self.src)
        self.assertIn('w.configure(background=self.UI_BG)', self.src)
        self.assertIn('self.t("mini_hint", "双击一行 = 从这行开始粘贴")', self.src)
        # 5 个按钮全部小号样式 (命令与文案没动)
        for label in ("set_mini_lock", "cmn_delete", "set_mini_delall"):
            line = [l for l in self.src.splitlines() if f'self.t("{label}"' in l and "ttk.Button(bar" in l and "width=" in l]
            self.assertTrue(line and 'style="Small.TButton"' in line[0], label)


class UiPhase4Tests(unittest.TestCase):
    """UI P4 (2026-11-28): 全窗口底色统一 + toast 上滑微交互。"""

    @classmethod
    def setUpClass(cls):
        cls.src = open(os.path.join(ROOT, "main.py"), encoding="utf-8").read()

    def test_titled_dialogs_follow_page_bg(self):
        # 7 个带标题栏的对话框都在创建语句后紧跟一行底色设置; 只数 Toplevel 行, 避开菜单里的同名文案
        n = self.src.count("configure(background=self.UI_BG)")
        self.assertGreaterEqual(n, 7)

    def test_toast_slide_up(self):
        i = self.src.index("def toast(self, text, action=None")
        body = self.src[i:i + 2600]
        self.assertIn("def _slide(step=0):", body)
        self.assertIn("place_configure(y=-16 - 6 * step)", body)
        self.assertIn('box.place(relx=0.5, rely=1.0, anchor="s", y=-16)', body)

    def test_special_overlay_windows_kept(self):
        # 复制即译的 1px 描边窗与透明翻译覆盖层是有意设计, 不能被"统一底色"误伤
        self.assertIn("win.configure(background=self.UI_BORDER)", self.src)
        self.assertIn('MAGIC = "#FF00FE"', self.src)


class CleanupRoundTests(unittest.TestCase):
    """2026-11-28 全量审查清理: 死方法移除、冗余转换去除、旧色收口、接口签名标注。"""

    @classmethod
    def setUpClass(cls):
        cls.src = open(os.path.join(ROOT, "main.py"), encoding="utf-8").read()

    def test_dead_method_removed(self):
        self.assertNotIn("def snip_ai_translate", self.src)

    def test_redundant_int_casts_removed(self):
        self.assertNotIn("str(int(round(v)))", self.src)
        self.assertNotIn('int(round(float(cc["temp_C"])))', self.src)

    def test_baidu_md5_documented(self):
        self.assertIn("# nosec B324", self.src)

    def test_old_swatch_color_gone(self):
        self.assertNotIn('"#D7DFEA"', self.src)


class ProxyNetworkTests(unittest.TestCase):
    """v1.6.1 统一网络代理: 三档模式、手动地址规整、回环绕过、代理变化自动重建、全量走代理 helper。"""

    @classmethod
    def setUpClass(cls):
        ns = {}
        wanted = {"_PROXY_CFG", "_PROXY_CACHE", "_LOOPBACK_HOSTS"}
        for node in TREE.body:
            if (isinstance(node, ast.Assign)
                    and any(isinstance(t, ast.Name) and t.id in wanted for t in node.targets)):
                exec(ast.get_source_segment(SOURCE, node), ns)
        fnames = ("_normalize_manual_proxy", "_resolve_proxies", "_proxy_signature",
                  "_build_net_opener", "_open_url", "_open_url_loose",
                  "_set_proxy_config", "_active_proxy_url")
        for name in fnames:
            node = next(n for n in TREE.body if isinstance(n, ast.FunctionDef) and n.name == name)
            exec(ast.get_source_segment(SOURCE, node), ns)
        cls.ns = ns

    def test_manual_normalize(self):
        n = self.ns["_normalize_manual_proxy"]
        self.assertEqual(n("127.0.0.1:7890"), "http://127.0.0.1:7890")
        self.assertEqual(n("http://127.0.0.1:7890"), "http://127.0.0.1:7890")
        self.assertEqual(n("https://proxy.local:8443"), "https://proxy.local:8443")
        self.assertEqual(n(""), "")
        self.assertEqual(n("127.0.0.1"), "")          # 缺端口
        self.assertEqual(n("ftp://127.0.0.1:21"), "")  # 不支持的协议

    def test_off_mode(self):
        self.ns["_set_proxy_config"]("off")
        self.assertEqual(self.ns["_resolve_proxies"](), {})
        self.assertIsNone(self.ns["_active_proxy_url"]())

    def test_manual_mode(self):
        self.ns["_set_proxy_config"]("manual", "127.0.0.1:7890")
        px = self.ns["_resolve_proxies"]()
        self.assertEqual(px, {"http": "http://127.0.0.1:7890", "https": "http://127.0.0.1:7890"})
        self.assertEqual(self.ns["_active_proxy_url"](), "http://127.0.0.1:7890")

    def test_system_mode_follows_getproxies(self):
        import urllib.request
        original = urllib.request.getproxies
        urllib.request.getproxies = lambda: {"https": "http://127.0.0.1:7890"}
        try:
            self.ns["_set_proxy_config"]("system")
            self.assertEqual(self.ns["_resolve_proxies"](), {"https": "http://127.0.0.1:7890"})
        finally:
            urllib.request.getproxies = original

    def test_opener_rebuilds_when_proxy_changes(self):
        self.ns["_set_proxy_config"]("off")
        first = self.ns["_build_net_opener"](False)
        self.ns["_set_proxy_config"]("manual", "127.0.0.1:7890")
        second = self.ns["_build_net_opener"](False)
        self.assertIsNot(first, second)
        # 再次相同签名应复用缓存
        self.assertIs(second, self.ns["_build_net_opener"](False))
        # strict 版带重定向防护 handler
        strict = self.ns["_build_net_opener"](True)
        kinds = [type(h).__name__ for h in strict.handlers]
        self.assertIn("_SameHostRedirect", kinds)

    def test_loopback_bypasses_proxy(self):
        import urllib.request
        self.ns["_set_proxy_config"]("manual", "127.0.0.1:7890")
        opener = self.ns["_build_net_opener"](False)
        handler = next(h for h in opener.handlers if isinstance(h, urllib.request.ProxyHandler))
        local_req = urllib.request.Request("http://127.0.0.1:11434/v1/models")
        self.assertIsNone(handler.proxy_open(local_req, "http://127.0.0.1:7890", "http"))
        self.assertEqual(local_req.host, "127.0.0.1:11434")
        self.assertIsNone(getattr(local_req, "_tunnel_host", None))
        remote_req = urllib.request.Request("https://generativelanguage.googleapis.com/v1beta/openai/models")
        self.assertIsNone(handler.proxy_open(remote_req, "http://127.0.0.1:7890", "https"))
        self.assertEqual(remote_req.host, "127.0.0.1:7890")
        self.assertEqual(remote_req._tunnel_host, "generativelanguage.googleapis.com")

    def test_no_raw_urlopen_left(self):
        # 所有请求都必须经过代理感知的 helper (AI 代码里的 or 兜底除外)
        self.assertNotIn("with urllib.request.urlopen", SOURCE)
        self.assertIn('opts["proxy"]', SOURCE)
        self.assertIn("def _open_url_loose", SOURCE)


class UpdateFallbackTests(unittest.TestCase):
    """v1.6.1 更新检查加固: 网页 302 备用通道、版本号解析、重试与友好报错。"""

    def test_tag_from_location(self):
        f = load_function("_tag_from_location")
        self.assertEqual(f("https://github.com/anna1211688/KIVO/releases/tag/v1.6.1"), "v1.6.1")
        self.assertEqual(f("https://github.com/anna1211688/KIVO/releases/tag/v1.6.1?x=1"), "v1.6.1")
        self.assertEqual(f("https://github.com/anna1211688/KIVO/releases/tag/v1.6.1/"), "v1.6.1")
        self.assertEqual(f("https://example.com/nope"), "")
        self.assertEqual(f(""), "")

    def test_probe_via_local_redirect(self):
        import http.server, threading
        loc = "https://github.com/anna1211688/KIVO/releases/tag/v1.6.1"

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(302)
                self.send_header("Location", loc)
                self.end_headers()
            def log_message(self, *args): pass

        srv = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        port = srv.server_address[1]
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        tag_fn = load_function("_tag_from_location")
        fn = _load_with_ns("_probe_latest_tag",
                           {"_resolve_proxies": lambda: {}, "VERSION": "1.6.1"})
        try:
            class Stub:
                _RELEASE_PAGE = f"http://127.0.0.1:{port}/latest"
                _tag_from_location = staticmethod(tag_fn)
            self.assertEqual(fn(Stub()), "v1.6.1")
        finally:
            srv.shutdown()

    def test_fetch_has_retry_and_fallback(self):
        seg = method_text("_fetch_latest_release")
        self.assertIn("_probe_latest_tag", seg)
        self.assertIn("upd_fail_hint", seg)
        self.assertIn("for attempt_timeout in (10, 12)", seg)


class ClipboardWatchTests(unittest.TestCase):
    """v1.6.1 后台剪贴板历史: 外部复制入队、去重、本程序自写跳过、开关与续排。"""

    @classmethod
    def setUpClass(cls):
        app_node = next(n for n in TREE.body if isinstance(n, ast.ClassDef) and n.name == "App")
        ns = {}
        wanted = ("_mark_self_clip", "_init_clipboard_watch", "_start_clipboard_watch",
                  "_stop_clipboard_watch", "_toggle_clip_watch", "_clipboard_tick")
        for name in wanted:
            node = next(n for n in app_node.body if isinstance(n, ast.FunctionDef) and n.name == name)
            exec(ast.get_source_segment(SOURCE, node), ns)
        cls.ns = ns

    def _make_stub(self, enabled=True):
        holder = {"clip": ""}
        added, after_calls, saved = [], [], []

        class Stub:
            _CLIP_POLL_MS = 800
        for _name, _fn in self.ns.items():
            if callable(_fn): setattr(Stub, _name, _fn)
        s = Stub()
        s._clip_watch_on = enabled
        s._clip_tick_scheduled = False
        s._last_clip_sig = None
        s._last_self_clip = None
        s.clip_get = lambda: holder["clip"]
        s.add_record = lambda text: added.append(text)
        s.after = lambda ms, fn: after_calls.append((ms, fn))
        return s, holder, added, after_calls

    def test_external_copy_recorded_and_rescheduled(self):
        s, holder, added, after_calls = self._make_stub()
        holder["clip"] = "hello world"
        self.ns["_clipboard_tick"](s)
        self.assertEqual(added, ["hello world"])
        self.assertEqual(s._last_clip_sig, "hello world")
        self.assertTrue(s._clip_tick_scheduled)
        self.assertEqual(len(after_calls), 1)

    def test_same_content_not_duplicated(self):
        s, holder, added, _ = self._make_stub()
        holder["clip"] = "same text"
        self.ns["_clipboard_tick"](s)
        self.ns["_clipboard_tick"](s)
        self.assertEqual(added, ["same text"])

    def test_self_clip_is_skipped_then_marker_consumed(self):
        s, holder, added, _ = self._make_stub()
        holder["clip"] = "internal copy"
        self.ns["_mark_self_clip"](s, "internal copy")
        self.ns["_clipboard_tick"](s)
        self.assertEqual(added, [])
        self.assertEqual(s._last_clip_sig, "internal copy")  # 签名仍记住, 后续不再处理
        self.assertIsNone(s._last_self_clip)
        self.ns["_clipboard_tick"](s)
        self.assertEqual(added, [])

    def test_empty_clipboard_no_record(self):
        s, holder, added, after_calls = self._make_stub()
        self.ns["_clipboard_tick"](s)
        self.assertEqual(added, [])
        self.assertEqual(len(after_calls), 1)  # 仍续排

    def test_disabled_tick_does_not_reschedule(self):
        s, holder, added, after_calls = self._make_stub(enabled=False)
        holder["clip"] = "text while off"
        self.ns["_clipboard_tick"](s)
        self.assertEqual(added, [])
        self.assertEqual(after_calls, [])

    def test_start_guard_and_stop(self):
        s, _, _, after_calls = self._make_stub()
        self.ns["_start_clipboard_watch"](s)
        self.assertTrue(s._clip_watch_on)
        self.assertTrue(s._clip_tick_scheduled)
        self.ns["_start_clipboard_watch"](s)  # 不重复排
        self.assertEqual(len(after_calls), 1)
        self.ns["_stop_clipboard_watch"](s)
        self.assertFalse(s._clip_watch_on)

    def test_toggle_persists_and_switches(self):
        import configparser
        s, _, _, _ = self._make_stub()
        cfg = configparser.ConfigParser()
        cfg.add_section("Config")
        s.cfg = cfg
        s.save_config = lambda: None
        s.status = type("S", (), {"set": staticmethod(lambda *_a: None)})()
        s.t = lambda key, zh: zh

        class Var:
            def __init__(self, v): self.v = v
            def get(self): return self.v
        s._clip_watch_var = Var(True)
        self.ns["_toggle_clip_watch"](s)
        self.assertEqual(cfg.get("Config", "ClipWatch"), "1")
        self.assertTrue(s._clip_watch_on)
        s._clip_watch_var = Var(False)
        self.ns["_toggle_clip_watch"](s)
        self.assertEqual(cfg.get("Config", "ClipWatch"), "0")
        self.assertFalse(s._clip_watch_on)

    def test_init_uses_config(self):
        import configparser
        s, _, _, after_calls = self._make_stub()
        cfg = configparser.ConfigParser()
        cfg.add_section("Config")
        cfg.set("Config", "ClipWatch", "0")
        s.cfg = cfg
        self.ns["_init_clipboard_watch"](s)
        self.assertFalse(s._clip_watch_on)
        self.assertEqual(after_calls, [])
        cfg.set("Config", "ClipWatch", "1")
        self.ns["_init_clipboard_watch"](s)
        self.assertTrue(s._clip_watch_on)
        self.assertEqual(len(after_calls), 1)

    def test_settings_checkbox_in_source(self):
        self.assertIn('self.t("clip_watch",', SOURCE)
        self.assertIn("def _toggle_clip_watch", SOURCE)


class QuickPanelTests(unittest.TestCase):
    """v1.6.2 全局快捷面板: 安全算术、结果收集与过滤、热键注册。"""

    @classmethod
    def setUpClass(cls):
        app_node = next(n for n in TREE.body if isinstance(n, ast.ClassDef) and n.name == "App")
        cls.ns = {"re": re}
        wanted = ("_safe_eval_math", "open_quick_panel", "_build_quick_panel",
                  "_quick_collect", "_quick_refresh", "_quick_pick")
        for name in wanted:
            node = next(n for n in app_node.body if isinstance(n, ast.FunctionDef) and n.name == name)
            exec(ast.get_source_segment(SOURCE, node), cls.ns)

    def test_safe_math(self):
        f = self.ns["_safe_eval_math"]
        self.assertEqual(f("1+2*3"), 7)
        self.assertEqual(f("(8-2)/4"), 1.5)
        self.assertEqual(f("10%3"), 1)
        self.assertEqual(f("-5+2"), -3)
        self.assertIsNone(f(""))
        self.assertIsNone(f("1+__import__('os')"))
        self.assertIsNone(f("a+b"))
        self.assertIsNone(f("1 and 2"))

    def test_collect_filters_and_caps(self):
        class Stub:
            _QUICK_MAX_RESULTS = 12
            records = [{"text": "hello world"}, {"text": "goodbye"}, {"text": "HELLO again"}]
            phrases = [{"text": "phrase one"}]
        Stub._safe_eval_math = staticmethod(self.ns["_safe_eval_math"])
        s = Stub()
        out = self.ns["_quick_collect"]
        all_rows = out(s, "")
        self.assertEqual(len(all_rows), 4)  # 3 records + 1 phrase
        hello_rows = out(s, "hello")
        self.assertEqual([v for _k, v in hello_rows], ["hello world", "HELLO again"])
        math_rows = out(s, "6*7")
        self.assertEqual(math_rows[0][1], "42")

    def test_hotkey_registered(self):
        self.assertIn('"QuickPanelKey"', SOURCE)
        self.assertIn('"QuickPanelKey": "F12"', SOURCE)
        self.assertIn("def open_quick_panel", SOURCE)


class SelectAiTests(unittest.TestCase):
    """v1.6.2 划词 AI: 提示词构造、动作集与热键注册。"""

    @classmethod
    def setUpClass(cls):
        app_node = next(n for n in TREE.body if isinstance(n, ast.ClassDef) and n.name == "App")
        cls.ns = {}
        for name in ("_select_ai_prompt", "select_ai_hotkey", "_select_ai_capture",
                     "_select_ai_show", "_select_ai_run"):
            node = next(n for n in app_node.body if isinstance(n, ast.FunctionDef) and n.name == name)
            exec(ast.get_source_segment(SOURCE, node), cls.ns)

    def test_prompts(self):
        f = self.ns["_select_ai_prompt"]
        p_zh = f(object(), "trans", "你好世界")
        self.assertIn("英文", p_zh); self.assertIn("你好世界", p_zh)
        p_en = f(object(), "trans", "hello world")
        self.assertIn("中文", p_en)
        for action in ("polish", "summary", "explain", "tone"):
            p = f(object(), action, "测试内容")
            self.assertIn("测试内容", p)

    def test_actions_and_hotkey(self):
        self.assertEqual(len(AppStub()._SELECT_AI_ACTIONS), 5)
        self.assertIn('"SelectAiKey": "ctrl+alt+a"', SOURCE)
        self.assertIn("def select_ai_hotkey", SOURCE)


class AppStub:
    _SELECT_AI_ACTIONS = (("trans", "翻译"), ("polish", "润色"), ("summary", "总结"),
                          ("explain", "解释"), ("tone", "换语气"))
