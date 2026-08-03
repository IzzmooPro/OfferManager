"""R10c-1 — raporlar sayfasının güvenli hata yolları.

Kapsam: `ui/reports_page.py`
  * `_generate` — rapor üretimi teknik hatası
  * `_export`   — Excel dışa aktarma teknik hatası

Sözleşme:
  * Ham istisna metni, traceback, SQL, mutlak yol ve müşteri/firma/teklif
    verisi ne kullanıcı arayüzüne ne loga girer; `exc_info` KULLANILMAZ.
  * `_generate` hatasında özet etiketi SABİT metne düşer ve istisna
    `operation_error.logla` ile TAM BİR KEZ güvenli loglanır.
  * `_export` hatasında `operation_error_dialog.hata_goster` kullanılır
    (`tur="Rapor"`, `islem="aktar"`); `path` hiçbir alana geçmez,
    `kayit_id` None kalır ve "kaydedildi" DENMEZ.
  * Korunan davranışlar: dosya seçimi iptali sessizdir, boş tablo doğrulama
    mesajı loglanmaz, başarılı üretim/tablo/özet değişmez ve başarı mesajında
    kullanıcının KENDİ seçtiği hedef yolun görünmesi bilinçlidir.

Gerçek kullanıcı verisi, gerçek DB, dosya sistemi çıktısı, SMTP, ağ ve
Credential Manager KULLANILMAZ; servis ve dosya diyalogları sahtedir.
"""
import inspect
import logging
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sqlite3
import unittest
from unittest import mock

from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox, QWidget

from ui.utils import operation_error_dialog as ohd
import ui.reports_page as rp

# Hiçbir yere sızmaması gereken içerik
GIZLI = ("no such table: offers SELECT c.company_name FROM customers c "
         "C:/Users/Universe/AppData/Local/OfferManagementSystem/data/database.db")
FIRMA = "Gizli Müşteri A.Ş."
TEKLIF_NO = "SNS-000042"
HEDEF_YOL = "C:/Users/Universe/Documents/rapor_20260803.xlsx"

HATALAR = {
    "operational": sqlite3.OperationalError(GIZLI),
    "izin": PermissionError(13, "Access is denied", HEDEF_YOL),
    "generic": RuntimeError(f"beklenmeyen {GIZLI} {FIRMA} {TEKLIF_NO}"),
}

SIZINTI = ("SELECT", "no such table", "C:/Users", "Access is denied",
           FIRMA, TEKLIF_NO, "Traceback", "sqlite3", "database.db")


def _hata(anahtar):
    try:
        raise HATALAR[anahtar]
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
    def _sayfa(self, uretim_hatasi=None):
        """Gerçek `ReportsPage` — yalnız servis sahte.

        `__init__` ağır DB kurulumu yapmaz; `ReportService` sahtelenir.
        """
        svc = mock.MagicMock()
        if uretim_hatasi is not None:
            svc.monthly_revenue.side_effect = uretim_hatasi
            svc.customer_ranking.side_effect = uretim_hatasi
            svc.product_ranking.side_effect = uretim_hatasi
            svc.conversion_rate.side_effect = uretim_hatasi
        else:
            svc.monthly_revenue.return_value = []
            svc.customer_ranking.return_value = []
            svc.product_ranking.return_value = []
            svc.conversion_rate.return_value = {"total": 0, "approved": 0,
                                                "cancelled": 0, "pending": 0,
                                                "rate": 0.0}
        with mock.patch.object(rp, "ReportService", return_value=svc):
            sayfa = rp.ReportsPage()
        self.addCleanup(sayfa.deleteLater)
        return sayfa, svc

    def _metinler(self):
        return "\n".join(m for _b, m in self.kutular)

    def _sizinti_yok(self, nerede=""):
        for parca in SIZINTI:
            self.assertNotIn(parca, self._metinler(),
                             f"kullanıcı mesajında sızıntı{nerede}: {parca}")
            self.assertNotIn(parca, self.log.birlesik,
                             f"logda sızıntı{nerede}: {parca}")


# ── A) _generate teknik hatası ──────────────────────────────────────────

class GenerateHataTests(_Temel):

    def test_label_sabit_ve_guvenli(self):
        for ad in HATALAR:
            with self.subTest(hata=ad):
                self.kutular.clear(); self.log.kayitlar.clear()
                sayfa, _ = self._sayfa(uretim_hatasi=_hata(ad))
                sayfa._generate()                    # İSTİSNA SIZMAMALI
                etiket = sayfa._summary_label.text()
                self.assertIn("Rapor oluşturulamadı", etiket)
                self.assertRegex(etiket, r"(?i)loguna kaydedildi",
                                 "kullanıcıya nereye bakacağı söylenmiyor")
                for parca in SIZINTI:
                    self.assertNotIn(parca, etiket,
                                     f"özet etiketinde sızıntı: {parca}")

    def test_istisna_tam_bir_kez_guvenli_loglanir(self):
        for ad in HATALAR:
            with self.subTest(hata=ad):
                self.log.kayitlar.clear()
                sayfa, _ = self._sayfa(uretim_hatasi=_hata(ad))
                sayfa._generate()
                self.assertEqual(self.log.guvenli_log_sayisi, 1,
                                 f"güvenli log 1 kez değil: {self.log.kayitlar}")
                self._sizinti_yok(f" ({ad})")

    def test_log_yalniz_guvenli_alanlari_icerir(self):
        sayfa, _ = self._sayfa(uretim_hatasi=_hata("operational"))
        sayfa._generate()
        satir = [s for s in self.log.kayitlar if "başarısız" in s][0]
        self.assertIn("OperationalError", satir, "istisna sınıfı yok")
        self.assertRegex(satir, r"konum=\[[\w.\-]+\.py:\d+",
                         "güvenli kaynak çerçevesi yok")
        self.assertNotIn("Traceback", satir)


# ── B) _export teknik hatası ────────────────────────────────────────────

class ExportHataTests(_Temel):

    def _export_calistir(self, yazma_hatasi, satir_sayisi=1):
        sayfa, _ = self._sayfa()
        sayfa._table.setRowCount(satir_sayisi)
        sayfa._table.setColumnCount(1)
        yakalanan = []
        gercek = ohd.hata_goster
        mock.patch.object(
            ohd, "hata_goster",
            lambda parent, baslik, exc, tur, islem="kaydet", kayit_id=None:
                yakalanan.append({"baslik": baslik, "tur": tur, "islem": islem,
                                  "kayit_id": kayit_id,
                                  "exc": type(exc).__name__})
            or gercek(parent, baslik, exc, tur, islem, kayit_id=kayit_id)).start()
        with mock.patch.object(QFileDialog, "getSaveFileName",
                               staticmethod(lambda *a, **k: (HEDEF_YOL, ""))), \
             mock.patch("openpyxl.Workbook",
                        side_effect=lambda *a, **k: (_ for _ in ()).throw(yazma_hatasi)):
            sayfa._export()                          # İSTİSNA SIZMAMALI
        return sayfa, yakalanan

    def test_hata_goster_dogru_parametrelerle(self):
        _sayfa, yakalanan = self._export_calistir(_hata("izin"))
        self.assertEqual(len(yakalanan), 1, "hata_goster kullanılmadı")
        c = yakalanan[0]
        self.assertEqual(c["tur"], "Rapor")
        self.assertEqual(c["islem"], "aktar")
        self.assertIsNone(c["kayit_id"], "kayit_id None kalmalı")
        # `path` hiçbir alana geçmemeli
        for alan in ("baslik", "tur", "islem"):
            self.assertNotIn("rapor_", str(c[alan]).lower(),
                             f"{alan} içinde hedef yol var")
            self.assertNotIn("C:/Users", str(c[alan]))

    def test_export_hatasinda_sizinti_yok(self):
        for ad in ("izin", "generic", "operational"):
            with self.subTest(hata=ad):
                self.kutular.clear(); self.log.kayitlar.clear()
                self._export_calistir(_hata(ad))
                self._sizinti_yok(f" ({ad})")
                self.assertNotIn(".xlsx", self._metinler(),
                                 "hedef yol hata mesajında")
                self.assertNotIn(".xlsx", self.log.birlesik,
                                 "hedef yol logda")

    def test_export_hatasinda_kaydedildi_denmez(self):
        self._export_calistir(_hata("izin"))
        for baslik, metin in self.kutular:
            self.assertNotIn("Kaydedildi", baslik)
            self.assertNotRegex(metin, r"(?i)rapor kaydedildi")

    def test_export_hatasi_tam_bir_kez_loglanir(self):
        self._export_calistir(_hata("generic"))
        self.assertEqual(self.log.guvenli_log_sayisi, 1,
                         f"güvenli log 1 kez değil: {self.log.kayitlar}")


# ── C) Korunan davranışlar ──────────────────────────────────────────────

class KorunanDavranisTests(_Temel):

    def test_dosya_secimi_iptalinde_sessiz(self):
        sayfa, _ = self._sayfa()
        sayfa._table.setRowCount(1)
        with mock.patch.object(QFileDialog, "getSaveFileName",
                               staticmethod(lambda *a, **k: ("", ""))):
            sayfa._export()
        self.assertEqual(self.kutular, [], "iptalde kutu açıldı")
        self.assertEqual(self.log.kayitlar, [], "iptalde log üretildi")

    def test_bos_tablo_dogrulama_mesaji_degismedi(self):
        sayfa, _ = self._sayfa()
        sayfa._table.setRowCount(0)
        with mock.patch.object(QFileDialog, "getSaveFileName",
                               staticmethod(lambda *a, **k: (HEDEF_YOL, ""))):
            sayfa._export()
        self.assertEqual(len(self.kutular), 1)
        baslik, metin = self.kutular[0]
        self.assertEqual(baslik, "Bilgi")
        self.assertIn("Dışa aktarılacak veri yok", metin)
        self.assertEqual(self.log.guvenli_log_sayisi, 0,
                         "doğrulama mesajı hata olarak loglandı")

    def test_basarili_uretimde_ozet_ve_log_degismedi(self):
        sayfa, svc = self._sayfa()
        sayfa._generate()
        self.assertEqual(svc.monthly_revenue.call_count, 1)
        self.assertEqual(self.log.guvenli_log_sayisi, 0)
        self.assertNotIn("Rapor oluşturulamadı", sayfa._summary_label.text())

    def test_basarili_export_mesajinda_kullanici_yolu_korunur(self):
        """Kullanıcının KENDİ seçtiği hedef yol — bilinçli davranış."""
        sayfa, _ = self._sayfa()
        sayfa._table.setRowCount(1)
        sayfa._table.setColumnCount(1)
        with mock.patch.object(QFileDialog, "getSaveFileName",
                               staticmethod(lambda *a, **k: (HEDEF_YOL, ""))), \
             mock.patch("openpyxl.Workbook") as wb:
            wb.return_value.active = mock.MagicMock()
            sayfa._export()
        self.assertTrue(any(HEDEF_YOL in m for _b, m in self.kutular),
                        "başarı mesajından kullanıcının seçtiği yol kaldırılmış")
        self.assertEqual(self.log.guvenli_log_sayisi, 0)


# ── D) Kaynak koruması ──────────────────────────────────────────────────

class KaynakKorumasiTests(unittest.TestCase):

    def _kaynak(self, ad):
        return inspect.getsource(getattr(rp.ReportsPage, ad))

    def test_hedef_catchlerde_ham_istisna_yok(self):
        for ad in ("_generate", "_export"):
            kaynak = self._kaynak(ad)
            for yasak in ("{e}", "{exc}", "str(e)", "str(exc)", "exc_info=True"):
                with self.subTest(fonksiyon=ad, yasak=yasak):
                    self.assertNotIn(yasak, kaynak,
                                     f"{ad} ham istisna gösteriyor: {yasak}")

    def test_guvenli_altyapi_kullaniliyor(self):
        self.assertIn("op_hata.logla", self._kaynak("_generate"))
        self.assertIn("hata_diyalogu", self._kaynak("_export"))

    def test_ham_logger_error_kalmadi(self):
        """`logger.error(..., exception)` biçimi hedef catch'lerde kalmamalı."""
        for ad in ("_generate", "_export"):
            for satir in self._kaynak(ad).splitlines():
                if "logger." in satir:
                    self.assertNotIn(", e)", satir, f"{ad}: ham log — {satir}")
                    self.assertNotIn(", exc)", satir, f"{ad}: ham log — {satir}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
