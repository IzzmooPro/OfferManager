"""R11 — "Hata Raporla / Sorun veya Öneri Bildir" v1.

Sözleşme:
  * `core/feedback_report.py` SAF'tır: Qt import etmez, dosya yazmaz/okumaz,
    ağ kullanmaz, loglamaz, credential okumaz.
  * Rapora YALNIZ şunlar girer: rastgele rapor no, yerel tarih/saat,
    `APP_VERSION`, Windows sürümü + mimari, paketli/kaynak modu, rapor türü,
    kullanıcının kendi açıklaması ve (yalnız teknik hata yolunda) mevcut
    hatanın güvenli işlem kategorisi + istisna SINIF ADI + `basename:satır
    fonksiyon` özeti.
  * Rapora GİRMEZ: `str(exc)`, traceback, SQL, mutlak yol, bilgisayar/kullanıcı
    adı, kayıt id'si, teklif no, müşteri/ürün/firma verisi, credential.
  * "Hata Raporla" düğmesi YALNIZ `operation_error.teknik_hata_mi(exc) is True`
    olan kutularda görünür; doğrulama/çakışma/meşgul hatalarında görünmez.
  * Diyalog YALNIZ gerçek düğme tıklamasıyla açılır.
  * Otomatik gönderim YOKTUR: pano yalnız tıklamayla yazılır, e-posta yalnız
    kullanıcının kendi istemcisinde TASLAK olarak açılır, "Rapor gönderildi"
    DENMEZ. Vazgeç hiçbir yan etki üretmez.
  * `mailto:` Qt URL/query API'siyle üretilir; kullanıcı metnindeki CRLF, `&`,
    `?` ve Türkçe karakterler başlık/query enjeksiyonu yapamaz.
  * Feedback penceresinin kendi hatası ikinci hata penceresi veya özyineleme
    üretmez; yalnız istisna SINIF ADI loglanır.
  * Aynı istisna ikinci kez loglanmaz.

Gerçek e-posta istemcisi, gerçek SMTP, gerçek ağ, gerçek kullanıcı verisi ve
Credential Manager KULLANILMAZ.
"""
import logging
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import inspect
import re
import sqlite3
import unittest
from pathlib import Path
from unittest import mock

from PySide6.QtCore import QUrl, QUrlQuery
from PySide6.QtWidgets import QApplication, QMessageBox

from core import feedback_report as fr
from ui.utils import operation_error as oh
from ui.utils import operation_error_dialog as ohd

# Rapora ASLA girmemesi gereken örnek sırlar/veriler
GIZLI_METIN = ("no such table: customers SELECT * FROM offers "
               "token=SECRET123 smtp_password=hunter2 "
               "C:/Users/Universe/AppData/Local/gizli.db")
FIRMA = "Örnek Müşteri A.Ş."
TEKLIF_NO = "TKF-2026-0042"

YASAK = ("SECRET123", "hunter2", "smtp_password", "SELECT", "no such table",
         "C:/Users", "C:\\Users", FIRMA, TEKLIF_NO)

HATALAR = {
    "integrity": sqlite3.IntegrityError("UNIQUE constraint failed " + GIZLI_METIN),
    "locked": sqlite3.OperationalError("database is locked"),
    "operational": sqlite3.OperationalError(GIZLI_METIN),
    "generic": RuntimeError("beklenmeyen " + GIZLI_METIN),
}
TEKNIK = ("operational", "generic")      # rapor düğmesi BEKLENEN hatalar
BEKLENEN = ("integrity", "locked")       # rapor düğmesi OLMAMASI gerekenler


def _hata_uret(anahtar):
    """Gerçek traceback'i olan bir istisna örneği döndürür."""
    try:
        raise HATALAR[anahtar]
    except Exception as exc:            # noqa: BLE001
        return exc


class _LogYakala(logging.Handler):
    def __init__(self):
        super().__init__()
        self.satirlar = []

    def emit(self, kayit):
        metin = str(kayit.getMessage())
        if kayit.exc_info:
            import traceback
            metin += "".join(traceback.format_exception(*kayit.exc_info))
        self.satirlar.append(metin)

    @property
    def birlesik(self):
        return "\n".join(self.satirlar)


class _Temel(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.log = _LogYakala()
        kok = logging.getLogger()
        kok.addHandler(self.log)
        self._eski_seviye = kok.level
        kok.setLevel(logging.DEBUG)
        self.addCleanup(lambda: (kok.removeHandler(self.log),
                                 kok.setLevel(self._eski_seviye)))
        # Gerçek Explorer / e-posta istemcisi ASLA açılmaz
        self.startfile = mock.patch.object(os, "startfile", create=True).start()
        self.addCleanup(mock.patch.stopall)
        mock.patch.object(QMessageBox, "exec",
                          lambda kutu, *a, **k: QMessageBox.StandardButton.Ok).start()

    def _yasak_yok(self, metin, nerede):
        for parca in YASAK:
            self.assertNotIn(parca, metin, f"{nerede} içinde sızıntı: {parca}")


# ── 1. Saf formatlayıcı sözleşmesi ──────────────────────────────────────────

class SafModulTests(_Temel):

    def test_qt_import_etmiyor(self):
        kaynak = inspect.getsource(fr)
        for yasak in ("PySide6", "QtWidgets", "QtCore", "QtGui", "QMessageBox",
                      "QUrl", "QApplication"):
            self.assertNotIn(yasak, kaynak,
                             f"feedback_report Qt bağımlılığı içeriyor: {yasak}")

    def test_disk_ag_log_credential_kullanmiyor(self):
        kaynak = inspect.getsource(fr)
        for yasak in ("open(", "urllib", "requests", "socket", "smtplib",
                      "keyring", "credential_store", "startfile",
                      "write_text", "read_text", "subprocess"):
            self.assertNotIn(yasak, kaynak,
                             f"saf modül yasaklı bağımlılık içeriyor: {yasak}")

    def test_modulun_logger_i_yok(self):
        self.assertFalse(hasattr(fr, "logger"),
                         "saf formatlayıcı log yazıyor")
        self.assertNotIn("logging", inspect.getsource(fr))

    def test_hicbir_dosya_acilmiyor(self):
        """Rapor üretimi çalışma anında GERÇEKTEN dosyaya dokunmaz."""
        import builtins
        gercek_open = builtins.open
        acilanlar = []

        def izleyen(*a, **k):
            acilanlar.append(a[0] if a else None)
            return gercek_open(*a, **k)

        with mock.patch.object(builtins, "open", izleyen):
            veri = fr.rapor_olustur(fr.TUR_HATA, "bir şey oldu",
                                    exc=_hata_uret("generic"),
                                    islem="Kategori ekle")
            fr.metin_uret(veri)
            fr.konu_uret(veri)
        self.assertEqual(acilanlar, [], f"rapor üretimi dosya açtı: {acilanlar}")


# ── 2. Rapor içeriği: girenler ──────────────────────────────────────────────

class RaporIcerigiTests(_Temel):

    def _veri(self, tur=fr.TUR_HATA, aciklama="Kategori eklerken hata aldım",
              anahtar="generic", islem="Kategori ekle"):
        exc = _hata_uret(anahtar) if anahtar else None
        return fr.rapor_olustur(tur, aciklama, exc=exc, islem=islem)

    def test_rapor_no_rastgele_ve_kisa(self):
        nolar = {fr.yeni_rapor_no() for _ in range(50)}
        self.assertEqual(len(nolar), 50, "rapor no rastgele değil")
        for n in nolar:
            self.assertRegex(n, r"^[0-9A-F]{6,12}$", f"biçim: {n!r}")

    def test_zorunlu_alanlar_metinde(self):
        from core.constants import APP_VERSION
        import platform
        veri = self._veri()
        metin = fr.metin_uret(veri)
        for beklenen in (veri.rapor_no, APP_VERSION, platform.machine(),
                         fr.TUR_HATA, "Kategori eklerken hata aldım"):
            self.assertIn(beklenen, metin, f"raporda eksik: {beklenen!r}")
        self.assertRegex(metin, r"\d{2}[.\-/]\d{2}[.\-/]\d{4}",
                         "raporda yerel tarih yok")

    def test_calisma_modu_yaziyor(self):
        metin = fr.metin_uret(self._veri())
        self.assertRegex(metin, r"(?i)kaynak|paketli",
                         "paketli/kaynak modu raporda yok")

    def test_teknik_ozet_yalniz_guvenli_alanlar(self):
        veri = self._veri(anahtar="generic")
        self.assertIsNotNone(veri.teknik, "teknik hatada özet üretilmedi")
        self.assertEqual(veri.teknik.hata_sinifi, "RuntimeError")
        self.assertEqual(veri.teknik.islem, "Kategori ekle")
        self.assertRegex(veri.teknik.konum,
                         r"^[\w.\-]+\.py:\d+ \w+",
                         f"konum güvenli biçimde değil: {veri.teknik.konum!r}")
        self.assertNotIn("/", veri.teknik.konum)
        self.assertNotIn("\\", veri.teknik.konum)

    def test_oneri_yolunda_teknik_ozet_yok(self):
        veri = fr.rapor_olustur(fr.TUR_ONERI, "şöyle bir özellik olsa")
        self.assertIsNone(veri.teknik, "öneri raporuna teknik özet girdi")
        metin = fr.metin_uret(veri)
        self.assertNotIn("RuntimeError", metin)
        self.assertIn("şöyle bir özellik olsa", metin)

    def test_konu_rapor_no_ve_turu_tasiyor(self):
        veri = self._veri()
        konu = fr.konu_uret(veri)
        self.assertIn(veri.rapor_no, konu)
        self.assertIn(fr.TUR_HATA, konu)
        self._yasak_yok(konu, "konu")

    def test_aciklama_zorunlulugu(self):
        for bos in ("", "   ", "\n\t "):
            self.assertFalse(fr.aciklama_gecerli(bos), f"{bos!r} geçerli sayıldı")
        self.assertTrue(fr.aciklama_gecerli("bir şey oldu"))


# ── 3. Gizlilik negatif testleri ────────────────────────────────────────────

class GizlilikTests(_Temel):

    def test_ham_istisna_ve_sirlar_rapora_girmiyor(self):
        for ad in HATALAR:
            with self.subTest(hata=ad):
                veri = fr.rapor_olustur(fr.TUR_HATA, "hata aldım",
                                        exc=_hata_uret(ad), islem="Kategori ekle")
                self._yasak_yok(fr.metin_uret(veri), f"rapor/{ad}")

    def test_mutlak_yol_rapora_girmiyor(self):
        veri = fr.rapor_olustur(fr.TUR_HATA, "hata", exc=_hata_uret("generic"),
                                islem="Kategori ekle")
        metin = fr.metin_uret(veri)
        self.assertNotIn(str(Path.home()), metin)
        self.assertNotIn(str(Path.cwd()), metin)
        self.assertIsNone(re.search(r"[A-Za-z]:[\\/]", metin),
                          f"raporda mutlak Windows yolu var:\n{metin}")

    def test_bilgisayar_ve_kullanici_adi_rapora_girmiyor(self):
        import platform
        veri = fr.rapor_olustur(fr.TUR_ONERI, "öneri")
        metin = fr.metin_uret(veri)
        for gizli in (platform.node(), os.environ.get("USERNAME", ""),
                      os.environ.get("COMPUTERNAME", "")):
            if gizli and len(gizli) > 2:
                self.assertNotIn(gizli, metin, f"raporda {gizli!r} var")

    def test_kayit_id_ve_teklif_no_alani_yok(self):
        """Veri modeli kayıt kimliği taşıyacak bir alan SUNMAZ."""
        import dataclasses
        alanlar = {f.name for f in dataclasses.fields(fr.TeknikOzet)}
        self.assertEqual(alanlar, {"islem", "hata_sinifi", "konum"},
                         f"teknik özet fazladan alan taşıyor: {alanlar}")

    def test_kullanici_aciklamasi_aynen_korunuyor(self):
        aciklama = "Ürün eklerken program dondu. Türkçe: ığüşöçİĞÜŞÖÇ"
        veri = fr.rapor_olustur(fr.TUR_HATA, aciklama)
        self.assertIn(aciklama, fr.metin_uret(veri))


# ── 4. Hata kutusundaki "Hata Raporla" düğmesi ──────────────────────────────

class HataKutusuDugmeTests(_Temel):

    def _goster(self, anahtar, islem="ekle"):
        return ohd.hata_goster(None, "Hata", _hata_uret(anahtar),
                               "Kategori", islem)

    def _rapor_dugmesi(self, kutu):
        from ui.dialogs.feedback_dialog import RAPOR_DUGME_METNI
        return next((b for b in kutu.buttons()
                     if b.text() == RAPOR_DUGME_METNI), None)

    def test_teknik_hatada_dugme_var(self):
        for ad in TEKNIK:
            with self.subTest(hata=ad):
                self.assertIsNotNone(self._rapor_dugmesi(self._goster(ad)),
                                     f"{ad}: 'Hata Raporla' düğmesi yok")

    def test_normal_hatada_dugme_yok(self):
        for ad in BEKLENEN:
            with self.subTest(hata=ad):
                self.assertIsNone(self._rapor_dugmesi(self._goster(ad)),
                                  f"{ad}: rapor düğmesi olmamalıydı")
                self.assertFalse(oh.teknik_hata_mi(HATALAR[ad]))

    def test_dogrulama_mesajinda_dugme_yok(self):
        kutu = ohd.dogrulama_goster(None, "Bilgi", "Lütfen bir kategori seçin.")
        self.assertIsNone(self._rapor_dugmesi(kutu))

    def test_log_dugmesi_davranisi_bozulmadi(self):
        """Mevcut 'Log Klasörünü Aç' sözleşmesi aynen sürüyor."""
        for ad in TEKNIK:
            with self.subTest(hata=ad):
                kutu = self._goster(ad)
                log_dugme = next((b for b in kutu.buttons()
                                  if b.text() == ohd.LOG_DUGME_METNI), None)
                self.assertIsNotNone(log_dugme, "log düğmesi kayboldu")
        self.assertEqual(self.startfile.call_count, 0,
                         "tıklanmadan Explorer açıldı")

    def test_kismi_basari_kutusunda_rapor_dugmesi_var(self):
        """Tek ve belli bir istisna var → raporlanabilir."""
        exc = _hata_uret("generic")
        self.log.satirlar.clear()
        sahte = mock.MagicMock()
        with mock.patch("ui.dialogs.feedback_dialog.FeedbackDialog", sahte):
            kutu = ohd.kismi_hata_goster(
                None, "Kaydedildi",
                exc, "Teklif kaydedildi ancak PDF oluşturulamadı.",
                "Teklif PDF", kayit_id=42)
            dugme = self._rapor_dugmesi(kutu)
            self.assertIsNotNone(dugme, "kısmi başarı kutusunda rapor düğmesi yok")
            self.assertEqual(sahte.call_count, 0, "tıklamadan pencere açıldı")
            dugme.click()
        self.assertEqual(sahte.call_count, 1)
        self.assertEqual(sahte.call_args.kwargs.get("islem"), "Teklif PDF",
                         "güvenli işlem adı raporlayıcıya geçmedi")
        basarisiz = [s for s in self.log.satirlar if "başarısız" in s]
        self.assertEqual(len(basarisiz), 1,
                         f"istisna {len(basarisiz)} kez loglandı: {basarisiz}")

    def test_toplu_hata_kutusunda_rapor_dugmesi_yok(self):
        """Birden fazla istisnadan yalnız ilkini raporlamak yanıltıcı olur."""
        hatalar = [(_hata_uret("generic"), 1), (_hata_uret("operational"), 2)]
        self.log.satirlar.clear()
        kutu = ohd.toplu_hata_goster(None, "Sonuç",
                                     "3 teklif silindi, 2 teklif silinemedi.",
                                     hatalar, islem="Teklif sil")
        self.assertIsNone(self._rapor_dugmesi(kutu),
                          "toplu hata kutusunda rapor düğmesi olmamalı")
        self.assertIsNotNone(
            next((b for b in kutu.buttons() if b.text() == ohd.LOG_DUGME_METNI),
                 None), "log düğmesi kayboldu")
        basarisiz = [s for s in self.log.satirlar if "başarısız" in s]
        self.assertEqual(len(basarisiz), 2,
                         "her istisna tam bir kez loglanmadı")

    def test_diyalog_yalniz_gercek_tiklamayla_aciliyor(self):
        sahte = mock.MagicMock()
        with mock.patch("ui.dialogs.feedback_dialog.FeedbackDialog", sahte):
            kutu = self._goster("generic")
            self.assertEqual(sahte.call_count, 0,
                             "düğmeye basılmadan rapor penceresi açıldı")
            self._rapor_dugmesi(kutu).click()
            self.assertEqual(sahte.call_count, 1,
                             "tıklamada rapor penceresi açılmadı")
            sahte.return_value.exec.assert_called_once()

    def test_ayni_istisna_ikinci_kez_loglanmiyor(self):
        sahte = mock.MagicMock()
        with mock.patch("ui.dialogs.feedback_dialog.FeedbackDialog", sahte):
            self.log.satirlar.clear()
            kutu = self._goster("generic")
            self._rapor_dugmesi(kutu).click()
        basarisiz = [s for s in self.log.satirlar if "başarısız" in s]
        self.assertEqual(len(basarisiz), 1,
                         f"istisna {len(basarisiz)} kez loglandı: {basarisiz}")

    def test_rapor_penceresi_hatasi_disari_sizmiyor(self):
        patlayan = mock.MagicMock(side_effect=RuntimeError(GIZLI_METIN))
        acilan = []
        with mock.patch("ui.dialogs.feedback_dialog.FeedbackDialog", patlayan):
            kutu = self._goster("generic")
            with mock.patch.object(QMessageBox, "exec",
                                   lambda k, *a, **kw: acilan.append(k)):
                self.log.satirlar.clear()
                self._rapor_dugmesi(kutu).click()      # SIZMAMALI
        self.assertEqual(acilan, [], "rapor hatasında ikinci kutu açıldı")
        self.assertIn("RuntimeError", self.log.birlesik,
                      "hata sınıf adı loglanmadı")
        self._yasak_yok(self.log.birlesik, "rapor hatası logu")


# ── 5. Diyalog davranışı ────────────────────────────────────────────────────

class FeedbackDialogTests(_Temel):

    def _diyalog(self, anahtar=None, islem="Kategori ekle"):
        from ui.dialogs.feedback_dialog import FeedbackDialog
        exc = _hata_uret(anahtar) if anahtar else None
        d = FeedbackDialog(None, exc=exc, islem=islem)
        self.addCleanup(d.deleteLater)
        return d

    def _acilan_urller(self):
        from PySide6.QtGui import QDesktopServices
        cagrilar = []
        yama = mock.patch.object(QDesktopServices, "openUrl",
                                 staticmethod(lambda u: cagrilar.append(u) or True))
        yama.start()
        self.addCleanup(yama.stop)
        return cagrilar

    # ── tek form: otomatik alanlar + tek açıklama kutusu ────────────────
    def _etiketler(self, d):
        from PySide6.QtWidgets import QLabel
        return [l for l in d.findChildren(QLabel)]

    def _gorunur_metin(self, d):
        """Kullanıcının pencerede GERÇEKTEN gördüğü tüm metin."""
        from ui.dialogs.feedback_dialog import GIZLILIK_NOTU
        return "\n".join([d.windowTitle(), GIZLILIK_NOTU,
                          d._aciklama.toPlainText()]
                         + [l.text() for l in self._etiketler(d)])

    def test_ikinci_onizleme_alani_kaldirildi(self):
        from PySide6.QtWidgets import QPlainTextEdit
        d = self._diyalog("generic")
        self.assertFalse(hasattr(d, "_onizleme"),
                         "salt-okunur ön izleme alanı hâlâ duruyor")
        kutular = d.findChildren(QPlainTextEdit)
        self.assertEqual(len(kutular), 1,
                         f"tek metin kutusu bekleniyordu, {len(kutular)} var")
        self.assertIs(kutular[0], d._aciklama)
        self.assertFalse(kutular[0].isReadOnly(),
                         "tek kutu düzenlenebilir olmalı")
        self.assertNotIn("Gönderilecek raporun tamamı",
                         self._gorunur_metin(d),
                         "eski ön izleme başlığı hâlâ gösteriliyor")

    def test_otomatik_alanlar_pencerede_gorunuyor(self):
        d = self._diyalog("generic")
        gorunur = self._gorunur_metin(d)
        v = d._temel
        for etiket in ("Rapor No", "Tarih", "Sürüm", "Sistem"):
            self.assertIn(etiket, gorunur, f"'{etiket}' etiketi yok")
        for deger in (v.rapor_no, v.tarih, v.surum, v.calisma_modu,
                      v.isletim_sistemi, v.mimari):
            self.assertIn(deger, gorunur, f"'{deger}' değeri gösterilmiyor")

    def test_etiketler_kalin(self):
        d = self._diyalog("generic")
        kalinlar = {l.text().rstrip(":").strip()
                    for l in self._etiketler(d) if l.font().bold()}
        for etiket in ("Rapor No", "Tarih", "Sürüm", "Sistem", "İşlem",
                       "Hata Türü", "Konum", "Ne oldu?"):
            self.assertIn(etiket, kalinlar, f"'{etiket}' kalın değil")

    def test_teknik_alanlar_yalniz_hata_yolunda(self):
        hata = self._gorunur_metin(self._diyalog("generic"))
        for etiket in ("İşlem", "Hata Türü", "Konum"):
            self.assertIn(etiket, hata, f"hata yolunda '{etiket}' yok")
        self.assertIn("RuntimeError", hata, "istisna sınıf adı gösterilmiyor")

        oneri = self._gorunur_metin(self._diyalog(None))
        for etiket in ("İşlem", "Hata Türü", "Konum", "RuntimeError"):
            self.assertNotIn(etiket, oneri,
                             f"Yardım menüsü yolunda '{etiket}' görünüyor")

    def test_rapor_no_yazdikca_degismiyor(self):
        d = self._diyalog("generic")
        ilk = d._temel.rapor_no
        d._aciklama.setPlainText("a")
        d._aciklama.setPlainText("ab")
        self.assertIn(ilk, self._gorunur_metin(d),
                      "her tuşta yeni rapor no üretiliyor")
        self.assertIn(ilk, d.rapor_metni())

    def test_gonderilecek_metinde_gizli_metadata_yok(self):
        """Gönderilen metnin HER değeri kullanıcıya gösterilmiş olmalı.

        Kullanıcının görmediği hiçbir otomatik alan e-postaya veya panoya
        giremez: metnin her satırı ya sabit bir başlıktır ya da penceredeki
        bir alanın değeridir.
        """
        SABIT_BASLIKLAR = ("Ne oldu?", "Teknik özet")
        for anahtar in ("generic", None):
            with self.subTest(yol=anahtar or "yardim_menusu"):
                d = self._diyalog(anahtar)
                d._aciklama.setPlainText("program dondu")
                gorunur = self._gorunur_metin(d)
                for satir in d.rapor_metni().splitlines():
                    satir = satir.strip()
                    if (not satir or satir in SABIT_BASLIKLAR
                            or satir.startswith("Teklif Yönetim Sistemi")):
                        continue
                    deger = satir.split(":", 1)[1].strip() if ":" in satir else satir
                    self.assertIn(deger, gorunur,
                                  f"kullanıcıya gösterilmeyen alan gönderiliyor: "
                                  f"{satir!r}")

    def test_gonderilen_metinde_sizinti_yok(self):
        d = self._diyalog("operational")
        d._aciklama.setPlainText("hata aldım")
        self._yasak_yok(d.rapor_metni(), "gönderilecek metin")
        self._yasak_yok(self._gorunur_metin(d), "pencere")

    # ── açıklama zorunluluğu ────────────────────────────────────────────
    def test_aciklama_bosken_dugmeler_kapali(self):
        d = self._diyalog("generic")
        self.assertFalse(d._btn_mail.isEnabled())
        self.assertFalse(d._btn_pano.isEnabled())
        self.assertTrue(d._btn_iptal.isEnabled(), "Vazgeç kapatılamaz")
        d._aciklama.setPlainText("bir şey oldu")
        self.assertTrue(d._btn_mail.isEnabled())
        self.assertTrue(d._btn_pano.isEnabled())
        d._aciklama.setPlainText("   ")
        self.assertFalse(d._btn_pano.isEnabled(), "boşluk geçerli sayıldı")

    def test_gizlilik_notu_durust(self):
        """Not, kullanıcının YAZDIĞI metnin aynen gittiğini SÖYLEMELİDİR.

        "Bilgileriniz rapora eklenmez" tek başına yanlış güven verirdi:
        program otomatik toplamaz ama açıklama alanı olduğu gibi gider.
        """
        from PySide6.QtWidgets import QLabel
        from ui.dialogs.feedback_dialog import GIZLILIK_NOTU
        for parca in ("otomatik eklemez", "aynen girer",
                      "kişisel veya müşteri bilgisi", "yazmayın",
                      "kendiliğinden gönderilmez"):
            self.assertIn(parca, GIZLILIK_NOTU,
                          f"gizlilik notu eksik: {parca!r}")
        # Yanlış güven veren mutlak iddia bulunmamalı
        self.assertNotIn("rapora eklenmez.", GIZLILIK_NOTU)
        d = self._diyalog("generic")
        metinler = [l.text() for l in d.findChildren(QLabel)]
        self.assertIn(GIZLILIK_NOTU, metinler,
                      "gizlilik notu pencerede gösterilmiyor")

    def test_yalniz_uc_eylem_var(self):
        from PySide6.QtWidgets import QPushButton
        d = self._diyalog("generic")
        metinler = {b.text() for b in d.findChildren(QPushButton)}
        self.assertEqual(metinler, {"E-postayı Aç", "Panoya Kopyala", "Vazgeç"},
                         f"beklenmeyen düğme kümesi: {metinler}")

    # ── pano ────────────────────────────────────────────────────────────
    def test_pano_yalniz_tiklamayla_yaziliyor(self):
        pano = QApplication.clipboard()
        pano.setText("ONCEKI_PANO")
        d = self._diyalog("generic")
        d._aciklama.setPlainText("program dondu")
        self.assertEqual(pano.text(), "ONCEKI_PANO",
                         "tıklamadan pano değiştirildi")
        d._btn_pano.click()
        self.assertIn("program dondu", pano.text())
        self._yasak_yok(pano.text(), "pano")

    def test_pano_mesaji_gonderildi_demiyor(self):
        d = self._diyalog("generic")
        d._aciklama.setPlainText("x")
        d._btn_pano.click()
        self.assertNotIn("gönderildi", d._durum.text().lower())
        self.assertRegex(d._durum.text(), r"(?i)kopyaland")

    # ── e-posta ─────────────────────────────────────────────────────────
    def test_eposta_taslak_aciliyor_ve_gonderildi_denmiyor(self):
        cagrilar = self._acilan_urller()
        d = self._diyalog("generic")
        d._aciklama.setPlainText("program dondu")
        d._btn_mail.click()
        self.assertEqual(len(cagrilar), 1, "e-posta istemcisi açılmadı")
        durum = d._durum.text()
        self.assertNotIn("gönderildi", durum.lower(),
                         f"otomatik gönderim iddiası: {durum!r}")
        self.assertRegex(durum, r"(?i)aç[ıi]ld")
        self.assertRegex(durum, r"(?i)gönder")

    def test_mailto_kanonik_adrese_gidiyor(self):
        from core.constants import CONTACT_MAIL
        cagrilar = self._acilan_urller()
        d = self._diyalog("generic")
        d._aciklama.setPlainText("x")
        d._btn_mail.click()
        url = cagrilar[0]
        self.assertEqual(url.scheme(), "mailto")
        self.assertIn(CONTACT_MAIL, url.path())

    def test_mailto_enjeksiyona_kapali(self):
        """CRLF, &, ? ve Türkçe karakterler query'yi bozmaz."""
        kotu = ("satır1\r\nBcc: kurban@example.com\r\n"
                "&subject=SAHTE&cc=x@example.com?to=y@example.com "
                "Türkçe: ığüşöçİĞÜŞÖÇ")
        cagrilar = self._acilan_urller()
        d = self._diyalog("generic")
        d._aciklama.setPlainText(kotu)
        d._btn_mail.click()
        url = cagrilar[0]
        ham = url.toString()
        # Çiğ satır sonu veya başlık ayracı URL'ye giremez. ("SAHTE" gibi düz
        # harfler kullanıcı metninin parçasıdır ve kodlanmış gövdede görünmesi
        # NORMALDİR; enjeksiyonun ölçüsü aşağıdaki query yapısıdır.)
        for bozan in ("\r", "\n", "Bcc:"):
            self.assertNotIn(bozan, ham,
                             f"mailto URL'sinde çiğ {bozan!r} var")
        sorgu = QUrlQuery(url.query())
        anahtarlar = [k for k, _ in sorgu.queryItems()]
        self.assertEqual(sorted(anahtarlar), ["body", "subject"],
                         f"query'ye fazladan alan enjekte edildi: {anahtarlar}")
        konu = sorgu.queryItemValue(
            "subject", QUrl.ComponentFormattingOption.FullyDecoded)
        self.assertNotIn("SAHTE", konu, "kullanıcı metni konuyu ele geçirdi")
        self.assertIn(d._rapor_no, konu, "konu güvenli alanlardan üretilmemiş")
        govde = sorgu.queryItemValue(
            "body", QUrl.ComponentFormattingOption.FullyDecoded)
        self.assertIn("ığüşöçİĞÜŞÖÇ", govde, "Türkçe karakter bozuldu")
        self.assertIn("Bcc: kurban@example.com", govde,
                      "kullanıcı metni gövdede korunmadı")

    def test_eposta_acilamazsa_pano_onerilir_ve_sizmaz(self):
        from PySide6.QtGui import QDesktopServices
        acilan_kutular = []
        for davranis in (lambda u: False,
                         mock.MagicMock(side_effect=OSError(GIZLI_METIN))):
            with self.subTest(davranis=str(davranis)):
                with mock.patch.object(QDesktopServices, "openUrl",
                                       staticmethod(davranis)):
                    d = self._diyalog("generic")
                    d._aciklama.setPlainText("x")
                    self.log.satirlar.clear()
                    with mock.patch.object(
                            QMessageBox, "exec",
                            lambda k, *a, **kw: acilan_kutular.append(k)):
                        d._btn_mail.click()          # istisna SIZMAMALI
                    self.assertRegex(d._durum.text(), r"(?i)panoya kopyala")
                    self.assertNotIn("gönderildi", d._durum.text().lower())
                    self._yasak_yok(self.log.birlesik, "e-posta hata logu")
        self.assertEqual(acilan_kutular, [],
                         "e-posta hatasında ikinci pencere açıldı")

    # ── vazgeç ──────────────────────────────────────────────────────────
    def test_vazgec_yan_etki_uretmiyor(self):
        pano = QApplication.clipboard()
        pano.setText("DOKUNULMADI")
        cagrilar = self._acilan_urller()
        d = self._diyalog("generic")
        d._aciklama.setPlainText("bir şey oldu")
        self.log.satirlar.clear()
        d._btn_iptal.click()
        self.assertEqual(pano.text(), "DOKUNULMADI", "Vazgeç panoyu değiştirdi")
        self.assertEqual(cagrilar, [], "Vazgeç e-posta açtı")
        self.assertEqual(self.startfile.call_count, 0)
        self.assertEqual(self.log.satirlar, [], "Vazgeç log üretti")
        self.assertFalse(d.isVisible())


# ── 6. Giriş noktaları ──────────────────────────────────────────────────────

class GirisNoktalariTests(_Temel):

    def test_yardim_menusunde_eylem_var(self):
        import ui.main_window as mw
        kaynak = inspect.getsource(mw)
        self.assertIn("Sorun veya Öneri Bildir", kaynak,
                      "Yardım menüsünde bildirim eylemi yok")
        self.assertTrue(hasattr(mw.MainWindow, "_open_feedback"),
                        "MainWindow._open_feedback yok")

    def test_yardim_menusu_yolu_oneri_turu_aciyor(self):
        import ui.main_window as mw
        sahte = mock.MagicMock()
        with mock.patch("ui.dialogs.feedback_dialog.FeedbackDialog", sahte):
            mw.MainWindow._open_feedback(mock.MagicMock())
        self.assertEqual(sahte.call_count, 1)
        self.assertIsNone(sahte.call_args.kwargs.get("exc"),
                          "Yardım menüsü yoluna istisna sızdı")
        sahte.return_value.exec.assert_called_once()

    def test_contact_mail_tek_kanonik_sabit(self):
        from core.constants import CONTACT_MAIL
        import ui.dialogs.help_dialogs as hd
        self.assertEqual(hd.CONTACT_MAIL, CONTACT_MAIL)
        kaynak = inspect.getsource(hd)
        self.assertNotIn(f'"{CONTACT_MAIL}"', kaynak,
                         "help_dialogs adresi hâlâ kendi içinde sabitliyor")
        kaynak_dialog = inspect.getsource(
            __import__("ui.dialogs.feedback_dialog", fromlist=["x"]))
        self.assertNotIn(f'"{CONTACT_MAIL}"', kaynak_dialog,
                         "feedback_dialog adresi kendi içinde sabitliyor")


if __name__ == "__main__":
    unittest.main(verbosity=2)
