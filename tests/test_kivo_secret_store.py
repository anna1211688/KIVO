import unittest
from kivo_secret_store import read_secret, write_secret, is_protected

def fake_encrypt(s):
    return "dpapi:v1:ENC:" + s

def fake_decrypt(s):
    if not s.startswith("dpapi:v1:ENC:"):
        raise ValueError("bad ciphertext")
    return s.removeprefix("dpapi:v1:ENC:")

class SecretStoreTests(unittest.TestCase):
    def test_plaintext_legacy_read(self):
        self.assertEqual(read_secret("legacy-key", fake_decrypt), "legacy-key")
    def test_marked_read_decrypts(self):
        self.assertEqual(read_secret("dpapi:v1:ENC:secret", fake_decrypt), "secret")
    def test_encrypt_nonempty_plaintext(self):
        self.assertEqual(write_secret("secret", fake_encrypt), "dpapi:v1:ENC:secret")
    def test_empty_remains_empty(self):
        self.assertEqual(write_secret("", fake_encrypt), "")
    def test_marked_value_not_double_encrypted(self):
        value = "dpapi:v1:ENC:secret"
        self.assertEqual(write_secret(value, fake_encrypt), value)
    def test_encryptor_marker_required(self):
        with self.assertRaises(ValueError):
            write_secret("secret", lambda s: "oops")
    def test_corrupt_ciphertext_no_plaintext_fallback(self):
        with self.assertRaises(ValueError):
            read_secret("dpapi:v1:bad", fake_decrypt)
    def test_marker_detection(self):
        self.assertTrue(is_protected("dpapi:v1:x"))
        self.assertFalse(is_protected(""))

if __name__ == "__main__":
    unittest.main()
