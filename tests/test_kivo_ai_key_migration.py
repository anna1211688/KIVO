import unittest
from unittest.mock import patch
from kivo_ai_key_migration import decode_config_key, encode_config_key, migrate_key_value

class MigrationFacadeTests(unittest.TestCase):
    def test_legacy_plaintext_reads_without_dpapi(self):
        self.assertEqual(decode_config_key("legacy"), "legacy")
    def test_marked_value_calls_decrypt(self):
        with patch("kivo_ai_key_migration.unprotect_secret", return_value="secret") as dec:
            self.assertEqual(decode_config_key("dpapi:v1:opaque"), "secret")
            dec.assert_called_once_with("dpapi:v1:opaque")
    def test_nonempty_key_encrypts(self):
        with patch("kivo_ai_key_migration.protect_secret", return_value="dpapi:v1:cipher") as enc:
            self.assertEqual(encode_config_key("secret"), "dpapi:v1:cipher")
            enc.assert_called_once_with("secret")
    def test_empty_key_is_not_encrypted(self):
        with patch("kivo_ai_key_migration.protect_secret") as enc:
            self.assertEqual(encode_config_key(""), "")
            enc.assert_not_called()
    def test_migration_is_facade(self):
        with patch("kivo_ai_key_migration.protect_secret", return_value="dpapi:v1:cipher"):
            self.assertEqual(migrate_key_value("legacy"), "dpapi:v1:cipher")

if __name__ == "__main__":
    unittest.main()
