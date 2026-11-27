"""KIVO 2.0 security baseline: static checks for critical guardrails."""
import ast
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "main.py").read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)


def find_text(fragment):
    i = SOURCE.find(fragment)
    if i < 0:
        raise AssertionError(f"Missing source marker: {fragment}")
    return SOURCE[i:i + 5000]


class Stage2SecurityBaseline(unittest.TestCase):
    def test_config_save_uses_atomic_write(self):
        body = find_text("def _save_config_inner")
        self.assertIn("_atomic_write(", body)

    def test_api_keys_are_config_values_not_hardcoded_defaults(self):
        body = find_text("def _ai_cfg(self")
        self.assertIn('g(pre + "Key")', body)
        self.assertIn('g("ApiKey")', body)

    def test_ai_base_url_scheme_validation(self):
        body = find_text("def _http_base")
        self.assertIn('("http", "https")', body)
        self.assertIn("p.netloc", body)

    def test_ai_request_has_timeout(self):
        body = find_text("def _send(pl)")
        self.assertRegex(body, r"urlopen\(req, timeout=timeout\)")

    def test_update_download_requires_signature_asset(self):
        body = find_text("no signature asset")
        self.assertIn("no signature asset", body)
        self.assertIn("hash mismatch", body)
        self.assertIn("_verify_update_sig", body)

    def test_update_signature_verification_is_constant_time_compare(self):
        body = find_text("def _verify_update_sig")
        self.assertIn("hmac.compare_digest", body)

    def test_media_download_has_timeout_and_retries(self):
        body = find_text('opts = {"quiet": True')
        self.assertIn('"socket_timeout": 20', body)
        self.assertIn('"retries": 3', body)
        self.assertIn('"noplaylist": True', body)

    def test_media_download_filename_template_limits_title_length(self):
        body = find_text('opts = {"quiet": True')
        self.assertIn("%(title).80s", body)


if __name__ == "__main__":
    unittest.main()
