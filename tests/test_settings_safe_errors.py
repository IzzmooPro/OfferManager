"""R10c-2 — ayarlar sayfasının güvenli hata ve aşama doğruluğu yolları.

Kapsam: `ui/settings_page.py`
  * `SmtpTestWorker.run` genel catch
  * `_upload` / `_remove` (görsel + imza)
  * `_toggle_logo` — logo silme ve **disabled marker** aşamaları
  * `_save` — config kaydetme

Sözleşme:
  * Ham istisna, SMTP sunucu/port/kullanıcı/parola, TLS-sertifika ayrıntısı,
    SQL ve yerel yol ne kullanıcıya ne loga ne de worker sinyaline girer.
  * Tam başarısızlıkta `hata_goster`; ÖNCEKİ AŞAMA tamamlandıysa
    `kismi_hata_goster` (invariant 18b) — tamamlanan iş inkâr edilmez.
  * Her istisna TAM BİR KEZ güvenli loglanır (elle log + diyalog logu birlikte
    kullanılmaz).
  * Korunan davranışlar: başarı yolları, `SMTPAuthenticationError` ve
    `TimeoutError` mesajları, "Kısmi Kayıt" credential sözleşmesi.

Gerçek `assets/`, gerçek config, gerçek logo/imza, gerçek SMTP, ağ, DB ve
Credential Manager KULLANILMAZ. Tüm yollar `TemporaryDirectory` altındadır.
"""
import inspect
import logging
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PySide6.QtWidgets import QApplication, QLabel, QMessageBox, QWidget

from ui.utils import operation_error_dialog as ohd
import ui.settings_page as sp

# Hiçbir yere sızmaması gereken içerik
SUNUCU = "smtp.gizlifirma.com"
KULLANICI = "muhasebe@gizlifirma.com"
PAROLA = "GizliParola123!"
GIZLI_YOL = "C:/Users/Universe/AppData/Local/OfferManagementSystem/data/logo.png"
GIZLI = (f"[SSL: CERTIFICATE_VERIFY_FAILED] {SUNUCU}:465 user={KULLANICI} "
         f"{GIZLI_YOL}")

SIZINTI = (SUNUCU, KULLANICI, PAROLA, "CERTIFICATE_VERIFY_FAILED", "C:/Users",
           "Traceback", "SELECT", ":465")


def _hata(sinif=RuntimeError, metin=None):
    try:
        raise sinif(metin if metin is not None else GIZLI)
    except Exception as exc:                                   # noqa: BLE001
        return exc


class _LogYakala(logging.Handler):
    def __init__(self):
        super().__init__()
        self.kayitlar = []

    def emit(self, k):
        metin = str(k.getMessage())
        if k.exc_info:
            import traceback
            metin += "".join(traceback.format_exception(*k.exc_info))
        self.kayitlar.append(metin)

    @property
    def birlesik(self):
        return "\n".join(self.kayitlar)

    @property
    def guvenli_log_sayisi(self):
        return len([s for s in self.kayitlar if "başarısız" in s])


class _Temel(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.log = _LogYakala()
        kok = logging.getLogger()
        kok.addHandler(self.log)
        self._eski = kok.level
        kok.setLevel(logging.DEBUG)
        self.addCleanup(lambda: (kok.removeHandler(self.log),
                                 kok.setLevel(self._eski)))
        mock.patch.object(os, "startfile", create=True).start()
        self.addCleanup(mock.patch.stopall)

        # TÜM görsel yolları geçici köke taşınır — gerçek assets'e dokunulmaz.
        self.tmp = tempfile.TemporaryDirectory(prefix="oms_settings_")
        self.addCleanup(self.tmp.cleanup)
        self.kok = Path(self.tmp.name)
        self.logo = self.kok / "logo.png"
        self.marker = self.kok / "logo.disabled"
        self.varsayilan = self.kok / "default_logo.png"
        self.varsayilan.write_bytes(b"PNG")
        for ad, deger in (("LOGO_PATH", self.logo),
                          ("LOGO_DISABLED_PATH", self.marker),
                          ("DEFAULT_LOGO_PATH", self.varsayilan)):
            mock.patch.object(sp, ad, deger).start()

        self.kutular = []            # (baslik, metin)

        def _exec(kutu, *a, **k):
            self.kutular.append((kutu.windowTitle(), kutu.text() or ""))
            return QMessageBox.StandardButton.Ok

        mock.patch.object(QMessageBox, "exec", _exec).start()
        for ad in ("warning", "information", "critical"):
            mock.patch.object(
                QMessageBox, ad,
                staticmethod(lambda p, b, m, *a, **k:
                             (self.kutular.append((b, m)),
                              QMessageBox.StandardButton.Ok)[1])).start()
        from core.app_paths import LOG_DIR
        LOG_DIR.mkdir(parents=True, exist_ok=True)

    # ── sahne ───────────────────────────────────────────────────────────
    def _sayfa(self):
        """Ağır `__init__` çalıştırılmaz; gerçek metot gövdeleri bağlanır."""
        s = sp.SettingsPage.__new__(sp.SettingsPage)
        QWidget.__init__(s)
        self.addCleanup(s.deleteLater)
        s.logo_preview = QLabel()
        s.b_logo = mock.MagicMock()
        return s

    def _metinler(self):
        return "\n".join(m for _b, m in self.kutular)

    def _sizinti_yok(self, nerede=""):
        for parca in SIZINTI:
            self.assertNotIn(parca, self._metinler(),
                             f"kullanıcı mesajında sızıntı{nerede}: {parca}")
            self.assertNotIn(parca, self.log.birlesik,
                             f"logda sızıntı{nerede}: {parca}")

    def _kismi_yakala(self):
        cagrilar = []
        gercek = ohd.kismi_hata_goster
        mock.patch.object(
            ohd, "kismi_hata_goster",
            lambda parent, baslik, exc, mesaj, islem, kayit_id=None:
                cagrilar.append({"baslik": baslik, "mesaj": mesaj,
                                 "islem": islem, "kayit_id": kayit_id})
            or gercek(parent, baslik, exc, mesaj, islem, kayit_id=kayit_id)).start()
        return cagrilar

    def _hata_yakala(self):
        cagrilar = []
        gercek = ohd.hata_goster
        mock.patch.object(
            ohd, "hata_goster",
            lambda parent, baslik, exc, tur, islem="kaydet", kayit_id=None:
                cagrilar.append({"baslik": baslik, "tur": tur, "islem": islem,
                                 "kayit_id": kayit_id})
            or gercek(parent, baslik, exc, tur, islem, kayit_id=kayit_id)).start()
        return cagrilar


# ── A) SMTP generic hata ────────────────────────────────────────────────

class SmtpGenericHataTests(_Temel):

    def _calistir(self, hata):
        cfg = {"smtp_server": SUNUCU, "smtp_port": "465",
               "smtp_user": KULLANICI, "smtp_password": PAROLA}
        w = sp.SmtpTestWorker(cfg)
        sonuc = []
        w.result.connect(lambda ok, msg: sonuc.append((ok, msg)))
        # `smtplib` fonksiyon içinde import ediliyor; modülün kendisi patch'lenir.
        import smtplib as _s
        with mock.patch.object(_s, "SMTP_SSL", side_effect=hata), \
             mock.patch.object(_s, "SMTP", side_effect=hata):
            w.run()
        return sonuc

    def test_generic_hatada_sabit_mesaj(self):
        sonuc = self._calistir(_hata())
        self.assertEqual(len(sonuc), 1)
        ok, msg = sonuc[0]
        self.assertFalse(ok)
        self.assertRegex(msg, r"(?i)tamamlanamad")
        self.assertRegex(msg, r"(?i)sunucu bilgilerini kontrol")
        self.assertRegex(msg, r"(?i)loguna kaydedildi")
        for parca in SIZINTI:
            self.assertNotIn(parca, msg, f"signal mesajında sızıntı: {parca}")

    def test_generic_hata_tam_bir_kez_guvenli_loglanir(self):
        self._calistir(_hata())
        self.assertEqual(self.log.guvenli_log_sayisi, 1,
                         f"güvenli log 1 kez değil: {self.log.kayitlar}")
        for parca in SIZINTI:
            self.assertNotIn(parca, self.log.birlesik, f"logda sızıntı: {parca}")

    def test_parola_hicbir_ciktiya_yazilmaz(self):
        sonuc = self._calistir(_hata())
        self.assertNotIn(PAROLA, sonuc[0][1])
        self.assertNotIn(PAROLA, self.log.birlesik)

    def test_ozel_hata_mesajlari_korunuyor(self):
        import smtplib
        sonuc = self._calistir(smtplib.SMTPAuthenticationError(535, b"bad"))
        self.assertRegex(sonuc[0][1], r"(?i)kimlik do[ğg]rulama")
        self.assertRegex(sonuc[0][1], r"(?i)uygulama [ŞS]ifresi")
        sonuc = self._calistir(TimeoutError())
        self.assertRegex(sonuc[0][1], r"(?i)zaman a[şs][ıi]m")

    def test_dogrulama_mesaji_ve_signal_sozlesmesi_korunuyor(self):
        w = sp.SmtpTestWorker({"smtp_server": "", "smtp_user": "",
                               "smtp_password": ""})
        sonuc = []
        w.result.connect(lambda ok, msg: sonuc.append((ok, msg)))
        w.run()
        self.assertEqual(sonuc, [(False, "Sunucu, e-posta ve şifre alanları "
                                         "boş bırakılamaz.")])
        self.assertEqual(self.log.guvenli_log_sayisi, 0,
                         "doğrulama mesajı hata olarak loglandı")


# ── B) Görsel yükleme ───────────────────────────────────────────────────

class GorselYuklemeTests(_Temel):

    def _upload(self, kaynak="C:/gecici/secilen.png", copy_hatasi=None,
                preview_hatasi=None):
        s = self._sayfa()
        onizleme = QLabel()
        with mock.patch.object(sp.QFileDialog, "getOpenFileName",
                               staticmethod(lambda *a, **k: (kaynak, ""))), \
             mock.patch.object(sp.shutil, "copy2",
                               side_effect=copy_hatasi or (lambda *a, **k: None)), \
             mock.patch.object(sp.SettingsPage, "_set_preview",
                               side_effect=preview_hatasi or (lambda *a: None)):
            s._upload(self.logo, onizleme, "Logo Yok")
        return s

    def test_copy_hatasinda_guvenli_hata(self):
        cagrilar = self._hata_yakala()
        self._upload(copy_hatasi=_hata(OSError))
        self.assertEqual(len(cagrilar), 1, "hata_goster kullanılmadı")
        self.assertEqual(cagrilar[0]["tur"], "Görsel")
        self.assertEqual(cagrilar[0]["islem"], "yukle")
        self.assertIsNone(cagrilar[0]["kayit_id"])
        self._sizinti_yok(" (copy)")
        self.assertEqual(self.log.guvenli_log_sayisi, 1)

    def test_copy_hatasinda_basari_denmez(self):
        self._upload(copy_hatasi=_hata(OSError))
        for baslik, metin in self.kutular:
            self.assertNotIn("Yüklendi", baslik)
            self.assertNotRegex(metin, r"(?i)ba[şs]ar[ıi]yla y[üu]klendi")

    def test_kopyalama_basarili_preview_hatasi_kismi_basari(self):
        """Dosya KAYDEDİLDİ; preview hatası bunu inkâr edemez."""
        cagrilar = self._kismi_yakala()
        kopyalama = []
        s = self._sayfa()
        with mock.patch.object(sp.QFileDialog, "getOpenFileName",
                               staticmethod(lambda *a, **k: ("C:/g/x.png", ""))), \
             mock.patch.object(sp.shutil, "copy2",
                               side_effect=lambda *a, **k: kopyalama.append(a)), \
             mock.patch.object(sp.SettingsPage, "_set_preview",
                               side_effect=_hata()):
            s._upload(self.logo, QLabel(), "Logo Yok")

        self.assertEqual(len(kopyalama), 1, "kopyalama tekrarlandı veya yapılmadı")
        self.assertEqual(len(cagrilar), 1, "kismi_hata_goster kullanılmadı")
        mesaj = cagrilar[0]["mesaj"]
        self.assertNotRegex(mesaj, r"(?i)y[üu]klenemedi",
                            "kaydedilmiş görsel inkâr edildi")
        self.assertRegex(mesaj, r"(?i)y[üu]klendi")
        self._sizinti_yok(" (preview)")
        self.assertEqual(self.log.guvenli_log_sayisi, 1)

    def test_basarili_yukleme_degismedi(self):
        self._upload()
        self.assertTrue(any(b == "Yüklendi" for b, _m in self.kutular),
                        "başarı mesajı kayboldu")
        self.assertEqual(self.log.guvenli_log_sayisi, 0)

    def test_dosya_secimi_iptalinde_sessiz(self):
        s = self._sayfa()
        with mock.patch.object(sp.QFileDialog, "getOpenFileName",
                               staticmethod(lambda *a, **k: ("", ""))):
            s._upload(self.logo, QLabel(), "Logo Yok")
        self.assertEqual(self.kutular, [])
        self.assertEqual(self.log.kayitlar, [])


# ── C) Görsel kaldırma ──────────────────────────────────────────────────

class GorselKaldirmaTests(_Temel):

    def test_unlink_hatasinda_guvenli_hata_ve_preview_korunur(self):
        cagrilar = self._hata_yakala()
        self.logo.write_bytes(b"PNG")
        s = self._sayfa()
        onizleme = QLabel("ONCEKI")
        with mock.patch.object(Path, "unlink", side_effect=_hata(OSError)):
            s._remove(self.logo, onizleme, "Logo Yok")
        self.assertEqual(len(cagrilar), 1)
        self.assertEqual(cagrilar[0]["tur"], "Görsel")
        self.assertEqual(cagrilar[0]["islem"], "sil")
        self.assertEqual(onizleme.text(), "ONCEKI",
                         "silme başarısızken önizleme temizlendi")
        for baslik, _m in self.kutular:
            self.assertNotIn("Kaldırıldı", baslik)
        self._sizinti_yok(" (unlink)")
        self.assertEqual(self.log.guvenli_log_sayisi, 1)

    def test_silme_basarili_preview_hatasi_kismi_basari(self):
        """Dosya SİLİNDİ; önizleme hatası korumasız sızmamalı ve silmeyi
        inkâr etmemeli."""
        cagrilar = self._kismi_yakala()
        self.logo.write_bytes(b"PNG")
        s = self._sayfa()
        bozuk = mock.MagicMock()
        bozuk.setPixmap.side_effect = _hata()
        with mock.patch.object(sp.SettingsPage, "_preview_label",
                               return_value=bozuk):
            s._remove(self.logo, QLabel(), "Logo Yok")   # SIZMAMALI
        self.assertFalse(self.logo.exists(), "dosya gerçekten silinmedi")
        self.assertEqual(len(cagrilar), 1, "kismi_hata_goster kullanılmadı")
        self.assertNotRegex(cagrilar[0]["mesaj"], r"(?i)kald[ıi]r[ıi]lamad",
                            "silinmiş dosya inkâr edildi")
        self._sizinti_yok(" (remove preview)")

    def test_basarili_kaldirma_degismedi(self):
        self.logo.write_bytes(b"PNG")
        s = self._sayfa()
        onizleme = QLabel()
        s._remove(self.logo, onizleme, "Logo Yok")
        self.assertFalse(self.logo.exists())
        self.assertEqual(onizleme.text(), "Logo Yok")
        self.assertTrue(any(b == "Kaldırıldı" for b, _m in self.kutular))
        self.assertEqual(self.log.guvenli_log_sayisi, 0)


# ── D) Logo disabled marker ─────────────────────────────────────────────

class LogoMarkerTests(_Temel):

    def test_marker_olusturulamazsa_kaldirildi_denmez(self):
        cagrilar = self._kismi_yakala()
        self.logo.write_bytes(b"PNG")          # özel logo var → aktif
        s = self._sayfa()
        with mock.patch.object(Path, "touch", side_effect=_hata(OSError)):
            s._toggle_logo()
        self.assertFalse(self.logo.exists(), "özel logo silinmedi")
        for baslik, metin in self.kutular:
            self.assertNotIn("Kaldırıldı", baslik)
            self.assertNotRegex(metin, r"(?i)^Logo PDF'den kaldırıldı")
        self.assertEqual(len(cagrilar), 1, "kismi_hata_goster kullanılmadı")
        mesaj = cagrilar[0]["mesaj"]
        # Tamamlanan aşama (özel logo silindi) inkâr edilmez
        self.assertRegex(mesaj, r"(?i)silindi|kald[ıi]r[ıi]ld")
        # Varsayılan logonun PDF'de kullanılmaya devam edebileceği söylenir
        self.assertRegex(mesaj, r"(?i)varsay[ıi]lan|PDF")
        self._sizinti_yok(" (marker touch)")
        self.assertEqual(self.log.guvenli_log_sayisi, 1)

    def test_marker_silinemezse_kismi_basari(self):
        cagrilar = self._kismi_yakala()
        self.marker.write_bytes(b"")           # logo devre dışı
        s = self._sayfa()

        def _sahte_upload(dest, preview, placeholder):
            Path(dest).write_bytes(b"PNG")     # görsel yüklendi
            return True                        # `_upload` sözleşmesi: kaydedildi

        with mock.patch.object(sp.SettingsPage, "_upload",
                               side_effect=_sahte_upload), \
             mock.patch.object(Path, "unlink", side_effect=_hata(OSError)):
            s._toggle_logo()
        self.assertTrue(self.logo.exists(), "görsel yüklenmedi")
        self.assertEqual(len(cagrilar), 1, "kismi_hata_goster kullanılmadı")
        mesaj = cagrilar[0]["mesaj"]
        self.assertRegex(mesaj, r"(?i)y[üu]klendi")
        self.assertRegex(mesaj, r"(?i)PDF")
        self.assertNotRegex(mesaj, r"(?i)tamamen etkinle[şs]tirildi")
        self._sizinti_yok(" (marker unlink)")
        self.assertEqual(self.log.guvenli_log_sayisi, 1)

    def test_basarili_logo_kaldirma_degismedi(self):
        self.logo.write_bytes(b"PNG")
        s = self._sayfa()
        s._toggle_logo()
        self.assertTrue(self.marker.exists(), "marker oluşmadı")
        self.assertTrue(any(b == "Kaldırıldı" for b, _m in self.kutular))
        self.assertEqual(self.log.guvenli_log_sayisi, 0)


class LogoSinirTests(_Temel):
    """Logo devre dışıyken ESKİ `LOGO_PATH` dosyası marker ile birlikte durur.

    Bu durumda yükleme akışının başarısız/iptal edilmesi marker'ı silip eski
    logoyu SESSİZCE yeniden etkinleştirmemelidir. Ayrıca marker yazılamazsa
    önizleme, gerçekte hâlâ aktif olan logoyu göstermelidir.
    """

    def _sayfa_logo(self):
        s = self._sayfa()
        s.logo_preview = QLabel()
        return s

    def _devre_disi_eski_logo_ile(self):
        """Logo devre dışı; ESKİ logo dosyası hâlâ diskte."""
        self.logo.write_bytes(b"ESKI")
        self.marker.write_bytes(b"")
        return self._sayfa_logo()

    def _sec(self, yol="C:/gecici/secilen.png"):
        return mock.patch.object(sp.QFileDialog, "getOpenFileName",
                                 staticmethod(lambda *a, **k: (yol, "")))

    # ── 1) `_upload` dönüş sözleşmesi ───────────────────────────────────
    def test_upload_iptalde_false_doner(self):
        s = self._sayfa()
        with self._sec(""):
            self.assertIs(s._upload(self.logo, QLabel(), "x"), False)

    def test_upload_copy_hatasinda_false_doner(self):
        s = self._sayfa()
        with self._sec(), mock.patch.object(sp.shutil, "copy2",
                                            side_effect=_hata(OSError)):
            self.assertIs(s._upload(self.logo, QLabel(), "x"), False)

    def test_upload_basarida_true_doner(self):
        s = self._sayfa()
        with self._sec(), \
             mock.patch.object(sp.shutil, "copy2", side_effect=lambda *a, **k: None), \
             mock.patch.object(sp.SettingsPage, "_set_preview",
                               side_effect=lambda *a: None):
            self.assertIs(s._upload(self.logo, QLabel(), "x"), True)

    def test_upload_preview_hatasinda_da_true_doner(self):
        """Dosya KAYDEDİLDİ; önizleme hatası kaydı geçersiz kılmaz."""
        s = self._sayfa()
        with self._sec(), \
             mock.patch.object(sp.shutil, "copy2", side_effect=lambda *a, **k: None), \
             mock.patch.object(sp.SettingsPage, "_set_preview", side_effect=_hata()):
            self.assertIs(s._upload(self.logo, QLabel(), "x"), True)

    # ── 2) marker korunması ─────────────────────────────────────────────
    def test_iptalde_marker_korunur(self):
        s = self._devre_disi_eski_logo_ile()
        with self._sec(""):
            s._toggle_logo()
        self.assertTrue(self.marker.exists(),
                        "iptalde marker silindi → eski logo sessizce etkinleşti")
        self.assertEqual(self.logo.read_bytes(), b"ESKI")
        self.assertEqual(self.log.guvenli_log_sayisi, 0)

    def test_copy_hatasinda_marker_korunur(self):
        s = self._devre_disi_eski_logo_ile()
        with self._sec(), mock.patch.object(sp.shutil, "copy2",
                                            side_effect=_hata(OSError)):
            s._toggle_logo()
        self.assertTrue(self.marker.exists(),
                        "copy hatasında marker silindi → eski logo etkinleşti")
        self.assertEqual(self.logo.read_bytes(), b"ESKI")
        self._sizinti_yok(" (copy + marker)")
        self.assertEqual(self.log.guvenli_log_sayisi, 1)

    def test_copy_basarili_preview_hatasinda_marker_silinir(self):
        s = self._devre_disi_eski_logo_ile()
        with self._sec(), \
             mock.patch.object(sp.shutil, "copy2",
                               side_effect=lambda *a, **k: self.logo.write_bytes(b"YENI")), \
             mock.patch.object(sp.SettingsPage, "_set_preview", side_effect=_hata()):
            s._toggle_logo()
        self.assertFalse(self.marker.exists(),
                         "kaydedilen görsel için marker silinmedi")
        self.assertEqual(self.logo.read_bytes(), b"YENI")

    def test_basarili_yuklemede_marker_silinir(self):
        s = self._devre_disi_eski_logo_ile()
        with self._sec(), \
             mock.patch.object(sp.shutil, "copy2",
                               side_effect=lambda *a, **k: self.logo.write_bytes(b"YENI")):
            s._toggle_logo()
        self.assertFalse(self.marker.exists(), "başarılı yüklemede marker kaldı")
        self.assertEqual(self.log.guvenli_log_sayisi, 0)

    # ── 3) marker yazılamadığında önizleme gerçeği yansıtır ─────────────
    def test_marker_yazilamadiginda_varsayilan_logo_gosterilir(self):
        cagrilar = self._kismi_yakala()
        self.logo.unlink(missing_ok=True)
        self.marker.unlink(missing_ok=True)          # varsayılan logo aktif
        s = self._sayfa_logo()
        onizlemeler = []
        with mock.patch.object(Path, "touch", side_effect=_hata(OSError)), \
             mock.patch.object(sp.SettingsPage, "_set_preview",
                               side_effect=lambda p, yol: onizlemeler.append(yol)):
            s._toggle_logo()
        self.assertFalse(self.marker.exists())
        self.assertNotIn("Logo Yok", s.logo_preview.text(),
                         "varsayılan logo aktifken 'Logo Yok' gösterildi")
        self.assertEqual(onizlemeler, [self.varsayilan],
                         "önizleme varsayılan logoya dönmedi")
        self.assertEqual(len(cagrilar), 1)
        self._sizinti_yok(" (marker/default)")
        self.assertEqual(self.log.guvenli_log_sayisi, 1)

    def test_ozel_logo_silinip_marker_yazilamazsa_varsayilana_doner(self):
        cagrilar = self._kismi_yakala()
        self.logo.write_bytes(b"OZEL")
        self.marker.unlink(missing_ok=True)
        s = self._sayfa_logo()
        onizlemeler = []
        with mock.patch.object(Path, "touch", side_effect=_hata(OSError)), \
             mock.patch.object(sp.SettingsPage, "_set_preview",
                               side_effect=lambda p, yol: onizlemeler.append(yol)):
            s._toggle_logo()
        self.assertFalse(self.logo.exists(), "özel logo silinmedi")
        self.assertEqual(onizlemeler, [self.varsayilan],
                         "varsayılan logoya dönülmedi")
        self.assertRegex(cagrilar[0]["mesaj"], r"(?i)silindi",
                         "tamamlanan silme aşaması inkâr edildi")
        for baslik, metin in self.kutular:
            self.assertNotIn("Kaldırıldı", baslik)

    def test_varsayilan_logo_yoksa_logo_yok_gosterilebilir(self):
        self._kismi_yakala()
        self.varsayilan.unlink()                     # varsayılan da yok
        self.logo.write_bytes(b"OZEL")
        self.marker.unlink(missing_ok=True)
        s = self._sayfa_logo()
        with mock.patch.object(Path, "touch", side_effect=_hata(OSError)):
            s._toggle_logo()
        self.assertIn("Logo Yok", s.logo_preview.text(),
                      "hiç logo yokken önizleme boş bırakılmadı")


# ── E) Ayar kaydetme ────────────────────────────────────────────────────

class AyarKaydetmeTests(_Temel):

    def _sayfa_kaydet(self, save_hatasi=None):
        s = self._sayfa()
        alanlar = ("f_prefix", "f_name", "f_address", "f_tel", "f_fax",
                   "f_mail", "f_web", "f_smtp_server", "f_smtp_port",
                   "f_smtp_user", "f_smtp_pass")
        for ad in alanlar:
            m = mock.MagicMock(); m.text.return_value = "x"
            setattr(s, ad, m)
        for ad in ("pdf_giris_metni", "pdf_iskonto", "pdf_teslim_yeri",
                   "pdf_kur_notu", "pdf_kdv_notu", "pdf_onay_metni",
                   "pdf_teslim_notu", "pdf_iptal_notu"):
            m = mock.MagicMock(); m.toPlainText.return_value = "x"
            setattr(s, ad, m)
        s._pdf_toggles = {}
        s._person_values = lambda: {}
        s._loaded_prefix = "x"
        s._current_values = lambda: {}
        s._snapshot = {}
        self.sifre_cagrisi = []
        s._sifreyi_kaydet = lambda p: (self.sifre_cagrisi.append(1), "")[1]
        with mock.patch.object(sp, "save_company_config",
                               side_effect=save_hatasi or (lambda *a, **k: None)):
            s._save()
        return s

    def test_kaydetme_hatasinda_guvenli_hata(self):
        cagrilar = self._hata_yakala()
        self._sayfa_kaydet(save_hatasi=_hata(OSError))
        self.assertEqual(len(cagrilar), 1, "hata_goster kullanılmadı")
        self.assertEqual(cagrilar[0]["tur"], "Ayarlar")
        self.assertEqual(cagrilar[0]["islem"], "kaydet")
        self._sizinti_yok(" (save)")
        self.assertEqual(self.log.guvenli_log_sayisi, 1)

    def test_kaydetme_hatasinda_sifre_kaydedilmez(self):
        self._sayfa_kaydet(save_hatasi=_hata(OSError))
        self.assertEqual(self.sifre_cagrisi, [],
                         "config kaydedilemediği hâlde parola yazıldı")

    def test_basarili_kayit_degismedi(self):
        self._sayfa_kaydet()
        self.assertEqual(self.sifre_cagrisi, [1])
        self.assertTrue(any(b == "Kaydedildi" for b, _m in self.kutular))
        self.assertEqual(self.log.guvenli_log_sayisi, 0)


# ── F) Kaynak koruması ──────────────────────────────────────────────────

class KaynakKorumasiTests(unittest.TestCase):

    HEDEFLER = ("_upload", "_remove", "_toggle_logo", "_save")

    def _kaynak(self, ad):
        return inspect.getsource(getattr(sp.SettingsPage, ad))

    def test_ham_istisna_gosterimi_yok(self):
        kaynaklar = {ad: self._kaynak(ad) for ad in self.HEDEFLER}
        kaynaklar["SmtpTestWorker.run"] = inspect.getsource(sp.SmtpTestWorker.run)
        for ad, kaynak in kaynaklar.items():
            for yasak in ("{e}", "{exc}", "str(e)", "str(exc)", "exc_info=True"):
                with self.subTest(fonksiyon=ad, yasak=yasak):
                    self.assertNotIn(yasak, kaynak,
                                     f"{ad} ham istisna gösteriyor: {yasak}")

    def test_ham_logger_warning_kalmadi(self):
        kaynak = self._kaynak("_toggle_logo")
        for satir in kaynak.splitlines():
            if "logger." in satir:
                self.assertNotIn(", e)", satir, f"ham log: {satir}")
                self.assertNotIn(", exc)", satir, f"ham log: {satir}")

    def test_yol_guvenli_log_argumani_degil(self):
        for ad in self.HEDEFLER:
            for satir in self._kaynak(ad).splitlines():
                if "logla" in satir or "hata_goster" in satir or "kismi_hata" in satir:
                    for yasak in ("dest", "path", "LOGO_PATH", "LOGO_DISABLED_PATH"):
                        self.assertNotIn(yasak, satir,
                                         f"{ad}: yol argüman olarak geçiyor — {satir}")

    def test_guvenli_altyapi_kullaniliyor(self):
        for ad in self.HEDEFLER:
            with self.subTest(fonksiyon=ad):
                self.assertIn("hata_diyalogu", self._kaynak(ad),
                              f"{ad} güvenli altyapıyı kullanmıyor")
        self.assertIn("op_hata.logla", inspect.getsource(sp.SmtpTestWorker.run))


if __name__ == "__main__":
    unittest.main(verbosity=2)
