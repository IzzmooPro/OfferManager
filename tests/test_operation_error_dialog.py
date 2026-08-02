"""R10-A — güvenli hata diyaloğu ve kategori işlemleri.

Sözleşme:
  * `ui/utils/operation_error.py` UI AÇMAZ ve **hiçbir Qt modülü import etmez**.
  * `ui/utils/operation_error_dialog.py` ince sarmalayıcıdır: güvenli log +
    güvenli mesaj + gerçek `QMessageBox`.
  * "Log Klasörünü Aç" düğmesi YALNIZ beklenmeyen/teknik hatalarda görünür;
    doğrulama mesajlarında görünmez.
  * `os.startfile` YALNIZ kullanıcı düğmeye bastığında çağrılır; hata verirse
    istisna sızmaz, ikinci kutu açılmaz, yalnız güvenli sınıf adı loglanır.
  * Kullanıcı mesajında ham istisna, SQL, traceback, yerel yol veya kategori
    adı bulunmaz; tam `LOG_DIR` yolu da gösterilmez.

Gerçek Explorer, gerçek kullanıcı verisi, Credential Manager ve ağ
KULLANILMAZ; `os.startfile` tamamen mock'lanır.
"""
import logging
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sqlite3
import unittest
from unittest import mock

from PySide6.QtWidgets import QApplication, QMessageBox

from ui.utils import operation_error as oh
from ui.utils import operation_error_dialog as ohd

GIZLI = "C:/Users/Universe/AppData/Local/gizli.db token=SECRET123 SELECT * FROM customers"
KATEGORI_ADI = "Gizli Müşteri Kategorisi"

HATALAR = {
    "integrity": sqlite3.IntegrityError(f"UNIQUE constraint failed: categories.name {GIZLI}"),
    "locked": sqlite3.OperationalError("database is locked"),
    "operational": sqlite3.OperationalError(f"no such table: categories {GIZLI}"),
    "generic": RuntimeError(f"beklenmeyen {GIZLI}"),
}
# Log düğmesi beklenen (teknik/beklenmeyen) hatalar
TEKNIK = ("operational", "generic")

SIZINTI = ("SECRET123", "C:/Users", "SELECT", "UNIQUE constraint",
           "no such table", KATEGORI_ADI)


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
        # Gerçek Explorer ASLA açılmaz
        self.startfile = mock.patch.object(os, "startfile", create=True).start()
        self.addCleanup(mock.patch.stopall)
        # Modal exec testte beklemesin
        mock.patch.object(QMessageBox, "exec",
                          lambda kutu, *a, **k: QMessageBox.StandardButton.Ok).start()
        # Log klasörü İZOLE profilde (conftest) oluşturulur; gerçek kullanıcı
        # yoluna dokunulmaz. "klasör yok" senaryosu ayrıca patch ile kurulur.
        from core.app_paths import LOG_DIR
        LOG_DIR.mkdir(parents=True, exist_ok=True)

    def _log_dugmesi(self, kutu):
        return next((b for b in kutu.buttons()
                     if b.text() == ohd.LOG_DUGME_METNI), None)

    def _sizinti_yok(self, metin, nerede):
        for parca in SIZINTI:
            self.assertNotIn(parca, metin, f"{nerede} içinde sızıntı: {parca}")


# ── 1. Yardımcı sözleşmesi ──────────────────────────────────────────────────

class YardimciSozlesmeTests(_Temel):

    def test_operation_error_qt_import_etmiyor(self):
        import inspect
        kaynak = inspect.getsource(oh)
        for yasak in ("PySide6", "QtWidgets", "QMessageBox", "QtCore"):
            self.assertNotIn(yasak, kaynak,
                             f"operation_error Qt bağımlılığı içeriyor: {yasak}")

    def test_kategori_turu_ve_fiilleri(self):
        beklenen = {"ekle": "eklenemedi", "ad": "adı değiştirilemedi",
                    "sil": "silinemedi"}
        for islem, fiil in beklenen.items():
            m = oh.guvenli_mesaj(RuntimeError(GIZLI), "Kategori", islem)
            self.assertIn(fiil, m, f"'{islem}' fiili yanlış: {m!r}")
            self._sizinti_yok(m, f"guvenli_mesaj({islem})")

    # ── UI bağımsızlığı: temel mesaj DÜĞMEDEN söz edemez ─────────────────
    # Temel mesaj hem düğmesiz hem düğmeli çağıranlarda kullanılabilir.
    # Düğmeyi anarsa, düğmesiz bir kutuda kullanıcı var olmayan bir denetime
    # yönlendirilir. Hangi sayfanın hangi yolu kullandığı bir IMPLEMENTASYON
    # ayrıntısıdır ve burada sabitlenmez; sözleşme metnin kendisidir.

    def test_temel_mesaj_dugmeden_soz_etmiyor(self):
        for ad, exc in HATALAR.items():
            for tur in ("Kategori", "Müşteri", "Ürün"):
                with self.subTest(hata=ad, tur=tur):
                    m = oh.guvenli_mesaj(exc, tur, "kaydet")
                    self.assertNotIn(ohd.LOG_DUGME_METNI, m,
                                     "temel mesaj UI düğmesine atıf yapıyor")

    def test_operation_error_ui_modulunu_bilmiyor(self):
        import inspect
        kaynak = inspect.getsource(oh)
        for yasak in ("operation_error_dialog", "LOG_DUGME_METNI",
                      ohd.LOG_DUGME_METNI):
            self.assertNotIn(yasak, kaynak,
                             f"operation_error UI'ı biliyor: {yasak}")

    def test_dialog_teknik_hatada_ipucu_ekliyor(self):
        for anahtar in TEKNIK:
            with self.subTest(hata=anahtar):
                m = ohd.kullanici_mesaji(HATALAR[anahtar], "Kategori", "ekle")
                self.assertIn(ohd.LOG_DUGME_METNI, m,
                              "sarmalayıcı teknik hatada ipucu eklemiyor")
                self.assertIn(oh.guvenli_mesaj(HATALAR[anahtar], "Kategori",
                                               "ekle"), m,
                              "sarmalayıcı temel mesajı korumuyor")

    def test_dialog_beklenen_hatada_ipucu_eklemiyor(self):
        for anahtar in ("integrity", "locked"):
            with self.subTest(hata=anahtar):
                m = ohd.kullanici_mesaji(HATALAR[anahtar], "Kategori", "ekle")
                self.assertNotIn(ohd.LOG_DUGME_METNI, m)

    def test_beklenen_hatalar_dogru_mesaji_veriyor(self):
        self.assertIn("çakışıyor",
                      oh.guvenli_mesaj(HATALAR["integrity"], "Kategori", "ekle"))
        self.assertIn("meşgul",
                      oh.guvenli_mesaj(HATALAR["locked"], "Kategori", "ekle"))

    def test_hicbir_mesajda_sizinti_yok(self):
        for ad, exc in HATALAR.items():
            for islem in ("ekle", "ad", "sil"):
                with self.subTest(hata=ad, islem=islem):
                    self._sizinti_yok(oh.guvenli_mesaj(exc, "Kategori", islem),
                                      f"{ad}/{islem}")


# ── 2. Diyalog sarmalayıcısı ────────────────────────────────────────────────

class DiyalogTests(_Temel):

    def _goster(self, anahtar, islem="ekle"):
        return ohd.hata_goster(None, "Hata", HATALAR[anahtar],
                               "Kategori", islem)

    def test_mesaj_ve_log_guvenli(self):
        for ad in HATALAR:
            with self.subTest(hata=ad):
                self.log.satirlar.clear()
                kutu = self._goster(ad)
                self._sizinti_yok(kutu.text(), "kullanıcı mesajı")
                self._sizinti_yok(self.log.birlesik, "log")

    def test_guvenli_log_tam_bir_kez(self):
        for ad in HATALAR:
            with self.subTest(hata=ad):
                self.log.satirlar.clear()
                self._goster(ad)
                basarisiz = [s for s in self.log.satirlar if "başarısız" in s]
                self.assertEqual(len(basarisiz), 1,
                                 f"güvenli log 1 kez değil: {basarisiz}")

    def test_log_dugmesi_yalniz_teknik_hatalarda(self):
        for ad in HATALAR:
            with self.subTest(hata=ad):
                kutu = self._goster(ad)
                dugme = self._log_dugmesi(kutu)
                if ad in TEKNIK:
                    self.assertIsNotNone(dugme, f"{ad}: log düğmesi yok")
                else:
                    self.assertIsNone(dugme, f"{ad}: log düğmesi olmamalıydı")

    def test_mesaj_ile_dugme_varligi_tutarli(self):
        """Mesaj düğmeyi ANIYORSA kutuda o düğme GERÇEKTEN olmalı."""
        for ad in HATALAR:
            with self.subTest(hata=ad):
                kutu = self._goster(ad)
                dugme_var = self._log_dugmesi(kutu) is not None
                ipucu_var = ohd.LOG_DUGME_METNI in kutu.text()
                self.assertEqual(dugme_var, ipucu_var,
                                 f"{ad}: düğme={dugme_var} ipucu={ipucu_var}")

    def test_dogrulama_mesajinda_ipucu_yok(self):
        kutu = ohd.dogrulama_goster(None, "Bilgi", "Lütfen bir kategori seçin.")
        self.assertNotIn(ohd.LOG_DUGME_METNI, kutu.text())

    def test_dogrulama_mesajinda_log_dugmesi_yok(self):
        kutu = ohd.dogrulama_goster(None, "Bilgi", "Lütfen bir kategori seçin.")
        self.assertIsNone(self._log_dugmesi(kutu))
        self.assertEqual(self.startfile.call_count, 0)

    def test_mesajda_tam_log_yolu_gorunmuyor(self):
        from core.app_paths import LOG_DIR
        for ad in HATALAR:
            with self.subTest(hata=ad):
                kutu = self._goster(ad)
                metin = kutu.text() + (kutu.informativeText() or "")
                self.assertNotIn(str(LOG_DIR), metin)
                self.assertNotIn(str(LOG_DIR.parent), metin)

    # ── os.startfile davranışı ──────────────────────────────────────────
    def test_dugmeye_basilmazsa_explorer_acilmaz(self):
        for ad in TEKNIK:
            with self.subTest(hata=ad):
                self._goster(ad)
        self.assertEqual(self.startfile.call_count, 0,
                         "düğmeye basılmadan Explorer açıldı")

    def test_dugmeye_basilinca_log_dizini_acilir(self):
        from core.app_paths import LOG_DIR
        kutu = self._goster("generic")
        self._log_dugmesi(kutu).click()
        self.assertEqual(self.startfile.call_count, 1)
        self.assertEqual(self.startfile.call_args.args[0], str(LOG_DIR))

    def test_startfile_hatasi_disari_sizmaz(self):
        self.startfile.side_effect = OSError("ERROR_FILE_NOT_FOUND " + GIZLI)
        kutu = self._goster("generic")
        acilan = []
        with mock.patch.object(QMessageBox, "exec",
                               lambda k, *a, **kw: acilan.append(k)):
            self.log.satirlar.clear()
            self._log_dugmesi(kutu).click()          # istisna SIZMAMALI
        self.assertEqual(acilan, [], "startfile hatasında ikinci kutu açıldı")
        self._sizinti_yok(self.log.birlesik, "startfile hata logu")
        self.assertIn("OSError", self.log.birlesik,
                      "hata sınıf adı loglanmadı")

    def test_klasor_yoksa_guvenli_davranir(self):
        from pathlib import Path
        kutu = self._goster("generic")
        with mock.patch.object(Path, "exists", return_value=False):
            self.log.satirlar.clear()
            self._log_dugmesi(kutu).click()
        self.assertEqual(self.startfile.call_count, 0,
                         "olmayan klasör için startfile çağrıldı")
        self._sizinti_yok(self.log.birlesik, "eksik klasör logu")


# ── 3. Kategori işlemleri ───────────────────────────────────────────────────

class KategoriHataYoluTests(_Temel):

    def _diyalog(self, **yan_etki):
        from ui.dialogs.category_dialog import CategoryManagerDialog
        svc = mock.MagicMock()
        svc.get_all.return_value = []
        for ad, exc in yan_etki.items():
            getattr(svc, ad).side_effect = exc
        with mock.patch("ui.dialogs.category_dialog.CategoryService",
                        return_value=svc):
            d = CategoryManagerDialog()
        self.addCleanup(d.deleteLater)
        d._yenileme = 0
        gercek = d._load

        def sayan():
            d._yenileme += 1
            return gercek()

        d._load = sayan
        return d, svc

    def _kutular(self):
        return [c for c in getattr(ohd, "_SON_KUTULAR", [])]

    def _secili_item(self, d):
        from PySide6.QtWidgets import QListWidgetItem
        from PySide6.QtCore import Qt
        it = QListWidgetItem(KATEGORI_ADI)
        it.setData(Qt.ItemDataRole.UserRole, 7)
        d._list.addItem(it)
        d._list.setCurrentItem(it)
        return it

    # ── ekleme ──────────────────────────────────────────────────────────
    def test_ekleme_hatasi_guvenli(self):
        for ad, exc in HATALAR.items():
            with self.subTest(hata=ad):
                d, svc = self._diyalog(add=exc)
                d._name_edit.setText(KATEGORI_ADI)
                self.log.satirlar.clear()
                d._add()
                self.assertEqual(svc.add.call_count, 1)
                self.assertEqual(d._yenileme, 0, "hatada liste yenilendi")
                self.assertEqual(d._name_edit.text(), KATEGORI_ADI,
                                 "hata sonrası girilen ad korunmadı")
                self._sizinti_yok(self.log.birlesik, "ekleme logu")
                self.assertEqual(
                    len([s for s in self.log.satirlar if "başarısız" in s]), 1)

    def test_ekleme_basarisi_korunuyor(self):
        d, svc = self._diyalog()
        d._name_edit.setText("Yeni")
        d._add()
        self.assertEqual(svc.add.call_count, 1)
        self.assertEqual(d._yenileme, 1, "başarıda liste yenilenmedi")
        self.assertEqual(d._name_edit.text(), "", "başarıda alan temizlenmedi")

    # ── silme ───────────────────────────────────────────────────────────
    def test_silme_hatasi_guvenli(self):
        for ad, exc in HATALAR.items():
            with self.subTest(hata=ad):
                d, svc = self._diyalog(delete=exc)
                self._secili_item(d)
                self.log.satirlar.clear()
                with mock.patch.object(
                        QMessageBox, "question",
                        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)):
                    d._delete()
                self.assertEqual(svc.delete.call_count, 1)
                self.assertEqual(d._yenileme, 0, "hatada liste yenilendi")
                self._sizinti_yok(self.log.birlesik, "silme logu")
                self.assertEqual(
                    len([s for s in self.log.satirlar if "başarısız" in s]), 1)

    # ── yeniden adlandırma ──────────────────────────────────────────────
    def test_rename_hatasi_guvenli(self):
        from PySide6.QtWidgets import QInputDialog
        for ad, exc in HATALAR.items():
            with self.subTest(hata=ad):
                d, svc = self._diyalog(update=exc)
                self._secili_item(d)
                self.log.satirlar.clear()
                with mock.patch.object(
                        QInputDialog, "getText",
                        staticmethod(lambda *a, **k: ("Yeni Ad", True))):
                    d._rename()
                self.assertEqual(svc.update.call_count, 1)
                self.assertEqual(d._yenileme, 0, "hatada liste yenilendi")
                self._sizinti_yok(self.log.birlesik, "rename logu")
                self.assertEqual(
                    len([s for s in self.log.satirlar if "başarısız" in s]), 1)

    # ── doğrulama yolları ───────────────────────────────────────────────
    def test_secim_yok_mesajinda_log_dugmesi_yok(self):
        d, _ = self._diyalog()
        for slot in (d._delete, d._rename):
            with self.subTest(slot=slot.__name__):
                self.log.satirlar.clear()
                slot()
                self.assertEqual(self.startfile.call_count, 0)
                self.assertEqual(
                    [s for s in self.log.satirlar if "başarısız" in s], [],
                    "doğrulama mesajı hata olarak loglandı")


if __name__ == "__main__":
    unittest.main(verbosity=2)
