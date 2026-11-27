"""Tests for the standalone DPAPI secret helper; Windows round-trip is gated."""
import unittest
import os
from unittest import mock
import kivo_security


class SecretHelperTests(unittest.TestCase):
    def test_prefix_format(self):
        self.assertEqual(kivo_security._PREFIX, "dpapi:v1:")

    def test_rejects_unmarked_value(self):
        with self.assertRaises(ValueError):
            kivo_security.unprotect_secret("plaintext")

    def test_rejects_invalid_base64(self):
        with mock.patch.object(kivo_security.os, "name", "nt"):
            with self.assertRaises(Exception):
                kivo_security.unprotect_secret("dpapi:v1:%%%")

    @unittest.skipUnless(os.name == "nt", "DPAPI requires Windows")
    def test_windows_round_trip(self):
        secret = "kivo-test-secret"
        self.assertEqual(kivo_security.unprotect_secret(kivo_security.protect_secret(secret)), secret)


if __name__ == "__main__":
    unittest.main()
