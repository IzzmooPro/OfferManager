"""O9 — düz metin SMTP şifresi taşıma + Settings kısmi kayıt bildirimi.

Gerçek `company.cfg`, gerçek Credential Manager ve gerçek SMTP ayarları
KULLANILMAZ: cfg sahte bir sözlük, keyring sınırı mock, `save_company_config`
patch'lidir. Hiçbir çıktıda düz metin parola gösterilmez.
"""
import unittest
from unittest import mock

import keyring

from core import credential_store as cs
from core.credential_store import (
    CredentialStoreError, migrate_plaintext_smtp_password,
    TASIMA_BASARISIZ, TASIMA_CFG_TEMIZLENEMEDI, TASIMA_GEREKSIZ, TASIMA_TAMAM,
)
from ui.settings_page import SettingsPage

GIZLI = "Eski-Duz-Metin-Parola"


def _cfg(**ek):
    d = {"name": "Firma", "smtp_server": "smtp.x.com", "smtp_user": "u@x.com"}
    d.update(ek)
    return d


class MigrationTests(unittest.TestCase):
    """Sıra: önce keyring'e yaz, ANCAK başarılıysa cfg'den kaldır."""

    def test_no_plaintext_password_is_a_noop(self):
        cfg = _cfg()
        parola, durum = migrate_plaintext_smtp_password(cfg)
        self.assertEqual((parola, durum), ("", TASIMA_GEREKSIZ))

    def test_successful_migration_removes_password_from_cfg(self):
        cfg = _cfg(smtp_password=GIZLI)
        yazilan = {}
        with mock.patch.object(cs, "set_smtp_password",
                               side_effect=lambda p: yazilan.update(p=p)), \
             mock.patch("core.config.save_company_config") as kaydet:
            parola, durum = migrate_plaintext_smtp_password(cfg)
        self.assertEqual(durum, TASIMA_TAMAM)
        self.assertEqual(parola, GIZLI)
        self.assertEqual(yazilan["p"], GIZLI)
        self.assertNotIn("smtp_password", cfg, "cfg'den kaldırılmadı")
        yazilan_cfg = kaydet.call_args[0][0]
        self.assertNotIn("smtp_password", yazilan_cfg,
                         "düz metin şifre dosyaya yeniden yazıldı")

    def test_keyring_failure_keeps_password_in_cfg(self):
        cfg = _cfg(smtp_password=GIZLI)
        with mock.patch.object(cs, "set_smtp_password",
                               side_effect=CredentialStoreError("x")), \
             mock.patch("core.config.save_company_config") as kaydet:
            parola, durum = migrate_plaintext_smtp_password(cfg)
        self.assertEqual(durum, TASIMA_BASARISIZ)
        self.assertEqual(cfg.get("smtp_password"), GIZLI,
                         "yazma başarısızken cfg'deki şifre silindi (veri kaybı)")
        kaydet.assert_not_called()
        self.assertEqual(parola, GIZLI)

    def test_failed_migration_is_not_logged_as_success(self):
        cfg = _cfg(smtp_password=GIZLI)
        with mock.patch.object(cs, "set_smtp_password",
                               side_effect=CredentialStoreError("x")):
            with self.assertLogs("credential_store", level="WARNING") as c:
                migrate_plaintext_smtp_password(cfg)
        cikti = "\n".join(c.output)
        self.assertIn("TAŞINAMADI", cikti)
        self.assertNotIn("taşındı ve config", cikti)
        self.assertNotIn(GIZLI, cikti, "düz metin parola log'a sızdı")

    def test_cfg_cleanup_failure_is_reported_not_hidden(self):
        cfg = _cfg(smtp_password=GIZLI)
        with mock.patch.object(cs, "set_smtp_password"), \
             mock.patch("core.config.save_company_config",
                        side_effect=OSError("disk dolu")):
            with self.assertLogs("credential_store", level="WARNING") as c:
                parola, durum = migrate_plaintext_smtp_password(cfg)
        self.assertEqual(durum, TASIMA_CFG_TEMIZLENEMEDI)
        self.assertEqual(cfg.get("smtp_password"), GIZLI,
                         "temizlik başarısızken cfg sessizce değiştirildi")
        cikti = "\n".join(c.output)
        self.assertIn("iki kopya", cikti)
        self.assertNotIn(GIZLI, cikti)

    def test_password_never_logged_on_success(self):
        cfg = _cfg(smtp_password=GIZLI)
        with mock.patch.object(cs, "set_smtp_password"), \
             mock.patch("core.config.save_company_config"):
            with self.assertLogs("credential_store", level="INFO") as c:
                migrate_plaintext_smtp_password(cfg)
        self.assertNotIn(GIZLI, "\n".join(c.output))


class SettingsSaveMessageTests(unittest.TestCase):
    """`_sifreyi_kaydet` — kısmi başarı bildirimi."""

    def setUp(self):
        self.sayfa = SettingsPage.__new__(SettingsPage)   # Qt kurulumu yok

    def test_successful_write_returns_no_warning(self):
        with mock.patch("ui.settings_page.set_smtp_password"):
            self.assertIsNone(self.sayfa._sifreyi_kaydet(GIZLI))

    def test_write_failure_returns_partial_success_message(self):
        with mock.patch("ui.settings_page.set_smtp_password",
                        side_effect=CredentialStoreError("x")):
            uyari = self.sayfa._sifreyi_kaydet(GIZLI)
        self.assertIsNotNone(uyari, "yanlış başarı mesajı gösterilecekti")
        self.assertIn("Ayarlar kaydedildi ancak SMTP şifresi güvenli depoya "
                      "yazılamadı", uyari)
        self.assertNotIn(GIZLI, uyari)
        self.assertNotIn("Traceback", uyari)

    def test_delete_failure_warns_old_password_may_remain(self):
        with mock.patch("ui.settings_page.set_smtp_password",
                        side_effect=CredentialStoreError("x")):
            uyari = self.sayfa._sifreyi_kaydet("")
        self.assertIn("silinemedi", uyari)
        self.assertIn("kalmış olabilir", uyari)


class SettingsReadMessageTests(unittest.TestCase):
    """`_sifreyi_oku` — okuma hatası 'şifre yok' ile karışmamalı."""

    def setUp(self):
        self.sayfa = SettingsPage.__new__(SettingsPage)

    def test_normal_read_returns_password_without_warning(self):
        with mock.patch("ui.settings_page.get_smtp_password",
                        return_value=GIZLI):
            parola, uyari = self.sayfa._sifreyi_oku(_cfg())
        self.assertEqual(parola, GIZLI)
        self.assertIsNone(uyari)

    def test_missing_record_is_not_an_error(self):
        with mock.patch("ui.settings_page.get_smtp_password", return_value=""):
            parola, uyari = self.sayfa._sifreyi_oku(_cfg())
        self.assertEqual(parola, "")
        self.assertIsNone(uyari)

    def test_read_error_produces_explicit_warning(self):
        with mock.patch("ui.settings_page.get_smtp_password",
                        side_effect=CredentialStoreError("x")):
            parola, uyari = self.sayfa._sifreyi_oku(_cfg())
        self.assertEqual(parola, "")
        self.assertIsNotNone(uyari)
        self.assertIn("OKUNAMADI", uyari)
        self.assertIn("silindiği anlamına gelmez", uyari)
        self.assertNotIn("Traceback", uyari)

    def test_failed_migration_warns_user(self):
        cfg = _cfg(smtp_password=GIZLI)
        with mock.patch("ui.settings_page.get_smtp_password", return_value=""), \
             mock.patch("ui.settings_page.migrate_plaintext_smtp_password",
                        return_value=(GIZLI, TASIMA_BASARISIZ)):
            parola, uyari = self.sayfa._sifreyi_oku(cfg)
        self.assertEqual(parola, GIZLI)
        self.assertIn("TAŞINAMADI", uyari)
        self.assertNotIn(GIZLI, uyari)

    def test_cfg_cleanup_failure_warns_about_two_copies(self):
        cfg = _cfg(smtp_password=GIZLI)
        with mock.patch("ui.settings_page.get_smtp_password", return_value=""), \
             mock.patch("ui.settings_page.migrate_plaintext_smtp_password",
                        return_value=(GIZLI, TASIMA_CFG_TEMIZLENEMEDI)):
            _, uyari = self.sayfa._sifreyi_oku(cfg)
        self.assertIn("iki kopya", uyari)


class ReadFailureDoesNotDeleteTests(unittest.TestCase):
    """Okuma hatası sonrası BOŞ alan, 'parolayı sil' isteği SAYILMAZ."""

    def setUp(self):
        self.sayfa = SettingsPage.__new__(SettingsPage)
        self.cagrilar = {"set": 0, "delete": 0}

    def _keyring_izle(self):
        return _KeyringIzleyici(self.cagrilar)

    def test_read_error_then_blank_save_does_not_delete(self):
        with mock.patch("ui.settings_page.get_smtp_password",
                        side_effect=CredentialStoreError("x")):
            self.sayfa._sifreyi_oku(_cfg())
        with self._keyring_izle():
            uyari = self.sayfa._sifreyi_kaydet("")
        self.assertEqual(self.cagrilar["delete"], 0,
                         "okuma hatasından sonra credential SİLİNDİ")
        self.assertEqual(self.cagrilar["set"], 0)
        self.assertIsNotNone(uyari)
        self.assertIn("okunamadığı", uyari)
        self.assertIn("değiştirilmedi", uyari)

    def test_warning_has_no_password_or_backend_detail(self):
        with mock.patch("ui.settings_page.get_smtp_password",
                        side_effect=CredentialStoreError("BACKEND-METNI")):
            self.sayfa._sifreyi_oku(_cfg())
        with self._keyring_izle():
            uyari = self.sayfa._sifreyi_kaydet("")
        self.assertNotIn("BACKEND-METNI", uyari)
        self.assertNotIn(GIZLI, uyari)
        self.assertNotIn("Traceback", uyari)

    def test_read_error_then_new_password_is_written(self):
        with mock.patch("ui.settings_page.get_smtp_password",
                        side_effect=CredentialStoreError("x")):
            self.sayfa._sifreyi_oku(_cfg())
        with self._keyring_izle():
            uyari = self.sayfa._sifreyi_kaydet("YeniParola")
        self.assertEqual(self.cagrilar["set"], 1, "yeni parola yazılmadı")
        self.assertIsNone(uyari)

    def test_successful_write_clears_read_error_state(self):
        with mock.patch("ui.settings_page.get_smtp_password",
                        side_effect=CredentialStoreError("x")):
            self.sayfa._sifreyi_oku(_cfg())
        with self._keyring_izle():
            self.sayfa._sifreyi_kaydet("YeniParola")
            self.sayfa._sifreyi_kaydet("")          # artık bilinçli silme
        self.assertEqual(self.cagrilar["delete"], 1,
                         "yazma sonrası okuma-hatası durumu temizlenmedi")

    def test_normal_read_then_clearing_field_still_deletes(self):
        with mock.patch("ui.settings_page.get_smtp_password",
                        return_value=GIZLI):
            self.sayfa._sifreyi_oku(_cfg())
        with self._keyring_izle():
            uyari = self.sayfa._sifreyi_kaydet("")
        self.assertEqual(self.cagrilar["delete"], 1,
                         "bilinçli silme engellendi")
        self.assertIsNone(uyari)

    def test_delete_error_stays_visible(self):
        with mock.patch("ui.settings_page.get_smtp_password",
                        return_value=GIZLI):
            self.sayfa._sifreyi_oku(_cfg())
        with mock.patch("ui.settings_page.set_smtp_password",
                        side_effect=CredentialStoreError("x")):
            uyari = self.sayfa._sifreyi_kaydet("")
        self.assertIn("silinemedi", uyari)


class _KeyringIzleyici:
    """set/delete çağrılarını sayar; gerçek depoya gitmez."""

    def __init__(self, sayac):
        self.sayac = sayac
        self._eski = {}

    def __enter__(self):
        self._eski = {"set": keyring.set_password,
                      "delete": keyring.delete_password}

        def _set(s, k, v):
            self.sayac["set"] += 1

        def _delete(s, k):
            self.sayac["delete"] += 1

        keyring.set_password = _set
        keyring.delete_password = _delete
        return self

    def __exit__(self, *a):
        keyring.set_password = self._eski["set"]
        keyring.delete_password = self._eski["delete"]
        return False


class CfgCleanupWhenKeyringHasPasswordTests(unittest.TestCase):
    """Keyring'de parola VARKEN cfg'deki düz metin kopya temizlenmeli."""

    def setUp(self):
        self.sayfa = SettingsPage.__new__(SettingsPage)

    def test_same_password_in_both_cleans_cfg_without_writing(self):
        cfg = _cfg(smtp_password=GIZLI)
        yazma = {"n": 0}
        with mock.patch("ui.settings_page.get_smtp_password",
                        return_value=GIZLI), \
             mock.patch.object(cs, "set_smtp_password",
                               side_effect=lambda p: yazma.update(n=1)), \
             mock.patch("core.config.save_company_config") as kaydet:
            parola, uyari = self.sayfa._sifreyi_oku(cfg)
        self.assertEqual(parola, GIZLI)
        self.assertIsNone(uyari)
        self.assertNotIn("smtp_password", cfg, "cfg'deki düz metin kaldı")
        self.assertEqual(yazma["n"], 0, "gereksiz set_password çağrıldı")
        self.assertNotIn("smtp_password", kaydet.call_args[0][0])

    def test_different_password_keeps_keyring_value(self):
        cfg = _cfg(smtp_password="ESKI-FARKLI-PAROLA")
        yazma = {"n": 0}
        with mock.patch("ui.settings_page.get_smtp_password",
                        return_value=GIZLI), \
             mock.patch.object(cs, "set_smtp_password",
                               side_effect=lambda p: yazma.update(n=1)), \
             mock.patch("core.config.save_company_config"):
            parola, uyari = self.sayfa._sifreyi_oku(cfg)
        self.assertEqual(parola, GIZLI,
                         "güvenli depodaki parola cfg değeriyle ezildi")
        self.assertEqual(yazma["n"], 0, "keyring sessizce overwrite edildi")
        self.assertNotIn("smtp_password", cfg)
        self.assertIsNone(uyari)

    def test_cfg_save_failure_keeps_field_and_warns(self):
        cfg = _cfg(smtp_password=GIZLI)
        with mock.patch("ui.settings_page.get_smtp_password",
                        return_value=GIZLI), \
             mock.patch("core.config.save_company_config",
                        side_effect=OSError("disk")):
            parola, uyari = self.sayfa._sifreyi_oku(cfg)
        self.assertEqual(cfg.get("smtp_password"), GIZLI)
        self.assertIsNotNone(uyari)
        self.assertIn("iki kopya", uyari)
        self.assertNotIn(GIZLI, uyari)

    def test_second_load_does_not_migrate_again(self):
        cfg = _cfg(smtp_password=GIZLI)
        with mock.patch("ui.settings_page.get_smtp_password",
                        return_value=GIZLI), \
             mock.patch("core.config.save_company_config") as kaydet:
            self.sayfa._sifreyi_oku(cfg)
            kaydet.reset_mock()
            parola, uyari = self.sayfa._sifreyi_oku(cfg)
        kaydet.assert_not_called()
        self.assertIsNone(uyari)
        self.assertEqual(parola, GIZLI)


class _SahteSayfa:
    """SettingsPage widget'larını taklit eden hafif stand-in.

    Gerçek `_save()` / `_load()` gövdeleri bu nesne üzerinde çalıştırılır;
    Qt kurulmaz. Bilinmeyen her nitelik otomatik olarak bir MagicMock olur.
    """

    def __init__(self, metin=""):
        self._varsayilan_metin = metin
        self.__dict__["_pdf_toggles"] = {}
        self.__dict__["_loaded_prefix"] = "SNS"
        self.__dict__["_sifre_okunamadi"] = False
        self.__dict__["pages"] = {}

    def __getattr__(self, ad):
        if ad.startswith("__"):
            raise AttributeError(ad)
        m = mock.MagicMock()
        m.text.return_value = self._varsayilan_metin
        m.toPlainText.return_value = ""
        m.isChecked.return_value = True
        self.__dict__[ad] = m
        return m

    # Gerçek metotlar sınıftan bağlanır
    _save = SettingsPage._save
    _load = SettingsPage._load
    _sifreyi_kaydet = SettingsPage._sifreyi_kaydet
    _sifreyi_oku = SettingsPage._sifreyi_oku
    acilis_kimlik_uyarisini_goster = SettingsPage.acilis_kimlik_uyarisini_goster
    _current_values = mock.Mock(return_value={})
    _refresh_previews = mock.Mock()
    _sync_person_cards = mock.Mock()


class _Kutular:
    """QMessageBox.information / warning / critical çağrılarını toplar."""

    def __enter__(self):
        self.bilgi, self.uyari, self.kritik = [], [], []
        self._p = [
            mock.patch("ui.settings_page.QMessageBox.information",
                       side_effect=lambda *a, **k: self.bilgi.append(a)),
            mock.patch("ui.settings_page.QMessageBox.warning",
                       side_effect=lambda *a, **k: self.uyari.append(a)),
            mock.patch("ui.settings_page.QMessageBox.critical",
                       side_effect=lambda *a, **k: self.kritik.append(a)),
        ]
        for p in self._p:
            p.start()
        return self

    def __exit__(self, *a):
        for p in self._p:
            p.stop()
        return False


class RealSaveFlowTests(unittest.TestCase):
    """Yardımcılar değil, GERÇEK `SettingsPage._save()` akışı."""

    def _calistir(self, sayfa, sayac=None):
        with _Kutular() as k, \
             mock.patch("ui.settings_page.save_company_config") as kaydet:
            if sayac is None:
                sayfa._save()
            else:
                with _KeyringIzleyici(sayac):
                    sayfa._save()
        return k, kaydet

    def test_success_shows_information(self):
        sayfa = _SahteSayfa(metin="Parola1")
        sayac = {"set": 0, "delete": 0}
        k, kaydet = self._calistir(sayfa, sayac)
        self.assertEqual(len(k.bilgi), 1, "başarı mesajı gösterilmedi")
        self.assertEqual(len(k.uyari), 0)
        kaydet.assert_called_once()
        self.assertEqual(sayac["set"], 1)

    def test_write_failure_shows_warning_not_success(self):
        sayfa = _SahteSayfa(metin="Parola1")
        with mock.patch("ui.settings_page.set_smtp_password",
                        side_effect=CredentialStoreError("x")):
            k, kaydet = self._calistir(sayfa)
        self.assertEqual(len(k.bilgi), 0, "yanlış başarı mesajı gösterildi")
        self.assertEqual(len(k.uyari), 1)
        self.assertIn("yazılamadı", k.uyari[0][2])
        kaydet.assert_called_once()          # diğer ayarlar kaydedildi

    def test_read_error_plus_blank_field_touches_nothing(self):
        sayfa = _SahteSayfa(metin="")
        sayfa._sifre_okunamadi = True
        sayac = {"set": 0, "delete": 0}
        k, kaydet = self._calistir(sayfa, sayac)
        self.assertEqual(sayac["set"], 0)
        self.assertEqual(sayac["delete"], 0, "credential silindi")
        kaydet.assert_called_once()          # diğer ayarlar KAYDEDİLDİ
        self.assertEqual(len(k.uyari), 1)
        self.assertIn("değiştirilmedi", k.uyari[0][2])

    def test_read_error_plus_new_password_writes(self):
        sayfa = _SahteSayfa(metin="YeniParola")
        sayfa._sifre_okunamadi = True
        sayac = {"set": 0, "delete": 0}
        k, kaydet = self._calistir(sayfa, sayac)
        self.assertEqual(sayac["set"], 1)
        self.assertEqual(len(k.bilgi), 1)
        self.assertFalse(sayfa._sifre_okunamadi)

    def test_normal_read_then_cleared_field_deletes(self):
        sayfa = _SahteSayfa(metin="")
        sayac = {"set": 0, "delete": 0}
        k, kaydet = self._calistir(sayfa, sayac)
        self.assertEqual(sayac["delete"], 1, "bilinçli silme yapılmadı")
        self.assertEqual(len(k.bilgi), 1)

    def test_delete_failure_shows_warning(self):
        sayfa = _SahteSayfa(metin="")
        with mock.patch("ui.settings_page.set_smtp_password",
                        side_effect=CredentialStoreError("x")):
            k, _ = self._calistir(sayfa)
        self.assertEqual(len(k.bilgi), 0)
        self.assertIn("silinemedi", k.uyari[0][2])


class RealLoadFlowTests(unittest.TestCase):
    """GERÇEK `SettingsPage._load()` akışı."""

    def _yukle(self, cfg):
        sayfa = _SahteSayfa()
        with _Kutular() as k, \
             mock.patch("ui.settings_page.load_company_config",
                        return_value=cfg):
            sayfa._load()
        return sayfa, k

    def test_read_error_sets_flag_and_defers_warning_until_startup_display(self):
        with mock.patch("ui.settings_page.get_smtp_password",
                        side_effect=CredentialStoreError("x")):
            sayfa, k = self._yukle(_cfg())
        self.assertTrue(sayfa._sifre_okunamadi)
        self.assertEqual(len(k.uyari), 0,
                         "ayar sayfası kurulurken modal açıldı")

        with _Kutular() as gosterim:
            ilk = sayfa.acilis_kimlik_uyarisini_goster(mock.sentinel.ana_pencere)
            ikinci = sayfa.acilis_kimlik_uyarisini_goster(mock.sentinel.ana_pencere)
        self.assertTrue(ilk)
        self.assertFalse(ikinci, "aynı açılış uyarısı ikinci kez gösterildi")
        self.assertEqual(len(gosterim.uyari), 1)
        self.assertIs(gosterim.uyari[0][0], mock.sentinel.ana_pencere)
        self.assertIn("OKUNAMADI", gosterim.uyari[0][2])

    def test_keyring_value_wins_over_cfg_plaintext(self):
        cfg = _cfg(smtp_password="ESKI-FARKLI")
        with mock.patch("ui.settings_page.get_smtp_password",
                        return_value=GIZLI), \
             mock.patch("core.config.save_company_config"):
            sayfa, k = self._yukle(cfg)
        sayfa.f_smtp_pass.setText.assert_called_with(GIZLI)
        self.assertNotIn("smtp_password", cfg)
        self.assertEqual(len(k.uyari), 0)

    def test_second_load_does_not_repeat_migration(self):
        cfg = _cfg(smtp_password=GIZLI)
        with mock.patch("ui.settings_page.get_smtp_password",
                        return_value=GIZLI), \
             mock.patch("core.config.save_company_config") as kaydet:
            self._yukle(cfg)
            kaydet.reset_mock()
            sayfa, k = self._yukle(cfg)
        kaydet.assert_not_called()
        self.assertEqual(len(k.uyari), 0)

    def test_cfg_cleanup_failure_keeps_plaintext_and_warns(self):
        cfg = _cfg(smtp_password=GIZLI)
        with mock.patch("ui.settings_page.get_smtp_password",
                        return_value=GIZLI), \
             mock.patch("core.config.save_company_config",
                        side_effect=OSError("disk")):
            sayfa, k = self._yukle(cfg)
        self.assertEqual(cfg.get("smtp_password"), GIZLI)
        self.assertEqual(len(k.uyari), 0,
                         "taşıma uyarısı ayar sayfası kurulurken modal açtı")
        with _Kutular() as gosterim:
            self.assertTrue(sayfa.acilis_kimlik_uyarisini_goster())
        self.assertEqual(len(gosterim.uyari), 1)
        self.assertIn("iki kopya", gosterim.uyari[0][2])


class EmailDialogReadErrorTests(unittest.TestCase):
    """Okuma hatasında gönderim başlamamalı, worker oluşmamalı."""

    def _dialog(self):
        from ui.dialogs.email_dialog import EmailDialog
        dlg = EmailDialog.__new__(EmailDialog)
        dlg.cfg = {"smtp_server": "s", "smtp_user": "u", "smtp_password": ""}
        dlg.worker = None
        dlg._kimlik_uyarisi = ("SMTP şifresi güvenli depodan okunamadı.\n"
                               "Gönderim başarısız olabilir; …")
        dlg.to_input = mock.MagicMock()
        dlg.to_input.text.return_value = "a@b.com"
        dlg.btn_send = mock.MagicMock()
        return dlg

    def test_send_is_blocked_and_no_worker_created(self):
        from ui.dialogs import email_dialog as ed
        dlg = self._dialog()
        with mock.patch.object(ed.QMessageBox, "warning") as uyar, \
             mock.patch.object(ed, "EmailWorker") as worker:
            ed.EmailDialog._send_email(dlg)
        uyar.assert_called_once()
        worker.assert_not_called()
        self.assertIsNone(dlg.worker)
        dlg.btn_send.setEnabled.assert_not_called()
        self.assertNotIn("Traceback", uyar.call_args[0][2])


class KeyringAvailableProbeTests(unittest.TestCase):
    """Kullanılabilirlik yoklaması credential YAZIP SİLMEMELİ."""

    def test_no_write_or_delete_during_probe(self):
        from core.credential_store import keyring_available
        sayac = {"set": 0, "delete": 0}
        with _KeyringIzleyici(sayac):
            keyring_available()
        self.assertEqual(sayac["set"], 0)
        self.assertEqual(sayac["delete"], 0)


class SaveFlowUsesHelperTests(unittest.TestCase):
    """`_save` koşulsuz başarı mesajı göstermemeli."""

    def test_save_branches_on_password_warning(self):
        import inspect
        kaynak = inspect.getsource(SettingsPage._save)
        self.assertIn("_sifreyi_kaydet", kaynak)
        self.assertIn("if sifre_uyarisi", kaynak)
        self.assertNotIn("set_smtp_password(self.f_smtp_pass", kaynak,
                         "dönüşü kontrol edilmeyen doğrudan yazma kaldı")


if __name__ == "__main__":
    unittest.main()
