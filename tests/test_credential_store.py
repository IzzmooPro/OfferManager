"""Credential store birim testleri."""
import unittest

from core.credential_store import (
    get_smtp_password, keyring_available, normalize_smtp_password)


class TestCredentialStore(unittest.TestCase):

    def test_keyring_available_returns_bool(self):
        result = keyring_available()
        self.assertIsInstance(result, bool)

    def test_get_smtp_password_returns_string(self):
        result = get_smtp_password()
        self.assertIsInstance(result, str)

    def test_get_smtp_password_no_crash_without_keyring(self):
        result = get_smtp_password()
        self.assertIsNotNone(result)


class TestNormalizeSmtpPassword(unittest.TestCase):

    def test_gmail_app_password_with_spaces(self):
        # Gmail 16 haneli uygulama şifresi gruplar halinde yapıştırılırsa
        self.assertEqual(
            normalize_smtp_password("abcd efgh ijkl mnop"),
            "abcdefghijklmnop")

    def test_leading_trailing_and_tabs(self):
        self.assertEqual(
            normalize_smtp_password("  ab cd\tef\n "), "abcdef")

    def test_plain_password_unchanged(self):
        self.assertEqual(normalize_smtp_password("S3cret!"), "S3cret!")

    def test_empty_and_none(self):
        self.assertEqual(normalize_smtp_password(""), "")
        self.assertEqual(normalize_smtp_password(None), "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
