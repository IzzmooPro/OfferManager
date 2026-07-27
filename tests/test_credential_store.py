"""Credential store birim testleri.

O9: keyring hatalarının sessizce yutulması düzeltildi. Bu testler üç yolu
(okuma / yazma / silme) ayrı ayrı, dört backend hata türüyle ve log/mesaj
sızıntısı açısından sabitler.

Gerçek Windows Credential Manager'a HİÇ dokunulmaz: `tests/conftest.py`
sınırdaki üç fonksiyonu bellek içi sahte depoyla değiştirir; buradaki testler
kendi senaryoları için o sahteleri geçici olarak değiştirir.
"""
import logging
import unittest
from unittest import mock

import keyring

from core.credential_store import (
    CredentialStoreError, get_smtp_password, keyring_available,
    normalize_smtp_password, set_smtp_password,
)
from tests import conftest

GIZLI = "P4rola-GIZLI-DEGER"


class _KeyringSenaryosu:
    """keyring sınırını geçici olarak istenen davranışa ayarlar."""

    def __init__(self, get=None, set_=None, delete=None):
        self._yeni = {"get_password": get, "set_password": set_,
                      "delete_password": delete}
        self._eski = {}

    def __enter__(self):
        for ad, islev in self._yeni.items():
            self._eski[ad] = getattr(keyring, ad)
            if islev is not None:
                setattr(keyring, ad, islev)
        return self

    def __exit__(self, *a):
        for ad, islev in self._eski.items():
            setattr(keyring, ad, islev)
        return False


def _firlat(hata):
    def _f(*a, **k):
        raise hata
    return _f


class GetPasswordTests(unittest.TestCase):

    def test_missing_record_returns_empty_string(self):
        with _KeyringSenaryosu(get=lambda s, k: None):
            self.assertEqual(get_smtp_password(), "")

    def test_existing_record_is_returned(self):
        with _KeyringSenaryosu(get=lambda s, k: GIZLI):
            self.assertEqual(get_smtp_password(), GIZLI)

    def test_backend_error_raises_instead_of_empty_string(self):
        with _KeyringSenaryosu(get=_firlat(RuntimeError("backend"))):
            with self.assertRaises(CredentialStoreError):
                get_smtp_password()

    def test_read_error_is_not_confused_with_missing_record(self):
        """En kritik ayrım: hata 'şifre girilmemiş' gibi görünmemeli."""
        with _KeyringSenaryosu(get=lambda s, k: None):
            yok = get_smtp_password()
        with _KeyringSenaryosu(get=_firlat(RuntimeError("backend"))):
            with self.assertRaises(CredentialStoreError):
                get_smtp_password()
        self.assertEqual(yok, "")


class SetPasswordTests(unittest.TestCase):

    def test_success_writes_value(self):
        yazilan = {}
        with _KeyringSenaryosu(set_=lambda s, k, v: yazilan.update(v=v)):
            set_smtp_password("  ab cd  ")
        self.assertEqual(yazilan["v"], "abcd")

    def test_backend_error_raises(self):
        with _KeyringSenaryosu(set_=_firlat(OSError("kilitli"))):
            with self.assertRaises(CredentialStoreError):
                set_smtp_password(GIZLI)

    def test_caller_cannot_mistake_failure_for_success(self):
        """Eskiden None dönüyordu; artık istisna fırlatıyor."""
        with _KeyringSenaryosu(set_=_firlat(OSError("kilitli"))):
            basarili = True
            try:
                set_smtp_password(GIZLI)
            except CredentialStoreError:
                basarili = False
        self.assertFalse(basarili)


class DeletePasswordTests(unittest.TestCase):

    def test_empty_password_deletes_record(self):
        silinen = {}
        with _KeyringSenaryosu(delete=lambda s, k: silinen.update(ok=True)):
            set_smtp_password("")
        self.assertTrue(silinen.get("ok"))

    def test_missing_record_on_delete_is_success(self):
        with _KeyringSenaryosu(
                delete=_firlat(keyring.errors.PasswordDeleteError("yok"))):
            set_smtp_password("")          # istisna FIRLATMAMALI

    def test_real_delete_error_is_visible(self):
        with _KeyringSenaryosu(delete=_firlat(OSError("erişim reddedildi"))):
            with self.assertRaises(CredentialStoreError):
                set_smtp_password("")


class BackendErrorMatrixTests(unittest.TestCase):
    """Dört backend hata türü güvenli ve TUTARLI davranmalı."""

    def _hatalar(self):
        return {
            "backend_yok": keyring.errors.NoKeyringError("yok"),
            "kilitli": keyring.errors.KeyringLocked("kilitli"),
            "erisim_reddedildi": PermissionError("reddedildi"),
            "baslatma": keyring.errors.InitError("başlatılamadı"),
        }

    def test_all_backend_errors_raise_credential_store_error(self):
        for ad, hata in self._hatalar().items():
            with self.subTest(ad=ad):
                with _KeyringSenaryosu(get=_firlat(hata), set_=_firlat(hata)):
                    with self.assertRaises(CredentialStoreError):
                        get_smtp_password()
                    with self.assertRaises(CredentialStoreError):
                        set_smtp_password(GIZLI)

    def test_error_message_carries_no_backend_detail(self):
        for ad, hata in self._hatalar().items():
            with self.subTest(ad=ad):
                with _KeyringSenaryosu(get=_firlat(hata)):
                    try:
                        get_smtp_password()
                    except CredentialStoreError as e:
                        self.assertNotIn(str(hata), str(e))
                        self.assertIsNone(e.__cause__,
                                          "backend istisnası zincire sızdı")


class LoggingTests(unittest.TestCase):
    """INFO'da görünür kayıt olmalı; parola/exception metni OLMAMALI."""

    def _yakala(self, calistir):
        with self.assertLogs("credential_store", level=logging.INFO) as c:
            calistir()
        return "\n".join(c.output)

    def test_write_failure_is_logged_at_info_or_higher(self):
        def calistir():
            with _KeyringSenaryosu(set_=_firlat(OSError(f"deneme {GIZLI}"))):
                with self.assertRaises(CredentialStoreError):
                    set_smtp_password(GIZLI)
        cikti = self._yakala(calistir)
        self.assertIn("yazılamadı", cikti)

    def test_password_never_appears_in_logs(self):
        def calistir():
            with _KeyringSenaryosu(set_=_firlat(OSError(f"deneme {GIZLI}"))):
                with self.assertRaises(CredentialStoreError):
                    set_smtp_password(GIZLI)
        cikti = self._yakala(calistir)
        self.assertNotIn(GIZLI, cikti, "parola log'a sızdı")

    def test_backend_exception_message_not_logged(self):
        ozel = "BACKEND-OZEL-METIN"

        def calistir():
            with _KeyringSenaryosu(get=_firlat(OSError(ozel))):
                with self.assertRaises(CredentialStoreError):
                    get_smtp_password()
        cikti = self._yakala(calistir)
        self.assertNotIn(ozel, cikti, "backend hata metni log'a sızdı")
        self.assertIn("OSError", cikti, "istisna sınıf adı yok")


class KeyringAvailableTests(unittest.TestCase):

    def test_returns_bool(self):
        self.assertIsInstance(keyring_available(), bool)

    def test_false_when_backend_lookup_fails(self):
        with mock.patch.object(keyring, "get_keyring",
                               side_effect=RuntimeError("yok")):
            self.assertFalse(keyring_available())

    def test_false_for_fail_backend(self):
        from keyring.backends import fail
        with mock.patch.object(keyring, "get_keyring",
                               return_value=fail.Keyring()):
            self.assertFalse(keyring_available())

    def test_false_for_zero_priority_backend(self):
        sahte = mock.Mock()
        sahte.priority = 0
        with mock.patch.object(keyring, "get_keyring", return_value=sahte):
            self.assertFalse(keyring_available())

    def test_true_for_positive_priority_backend(self):
        sahte = mock.Mock()
        sahte.priority = 5
        with mock.patch.object(keyring, "get_keyring", return_value=sahte):
            self.assertTrue(keyring_available())

    def test_availability_is_only_a_precheck(self):
        """Sözleşme: True olması işlemin başarısını GARANTİ ETMEZ."""
        self.assertIn("GARANTİ ETMEZ", keyring_available.__doc__)


class RealBackendIsolationTests(unittest.TestCase):
    """Suite gerçek Credential Manager sınırına 0 çağrı yapmalı."""

    def test_boundary_functions_are_mocked(self):
        for kisa, tam in (("get", "get_password"), ("set", "set_password"),
                          ("delete", "delete_password")):
            with self.subTest(ad=tam):
                self.assertIsNot(getattr(keyring, tam),
                                 conftest.GERCEK_KEYRING.get(kisa),
                                 f"{tam} gerçek keyring fonksiyonuna bağlı")

    def test_real_functions_were_captured(self):
        self.assertEqual(set(conftest.GERCEK_KEYRING),
                         {"get", "set", "delete"})


class TestNormalizeSmtpPassword(unittest.TestCase):

    def test_gmail_app_password_with_spaces(self):
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
