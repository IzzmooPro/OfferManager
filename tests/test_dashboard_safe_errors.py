"""R10-B — dashboard teklif/şablon/PDF/dışa aktarma hata yolları.

Sözleşme:
  * Kullanıcı mesajında ve logda ham istisna, SQL, traceback, dosya yolu veya
    gizli veri BULUNMAZ.
  * Her istisna `operation_error.logla` ile **tam bir kez** güvenli loglanır.
  * Teknik hatada mesajdaki "Log Klasörünü Aç" ipucu ile kutudaki GERÇEK düğme
    birebir eşleşir; doğrulama mesajlarında düğme yoktur.
  * Toplu işlemlerde (çoklu yükleme / PDF / silme) yanlış genelleme yapılmaz:
    yalnız güvenli sayılar gösterilir.

Gerçek slot gövdeleri çalıştırılır; servisler ve dosya diyalogları mock'lanır.
Gerçek kullanıcı verisi, Credential Manager, ağ ve Explorer KULLANILMAZ.
"""
import logging
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sqlite3
import unittest
from types import SimpleNamespace
from unittest import mock

from PySide6.QtWidgets import (QApplication, QFileDialog, QInputDialog,
                               QMessageBox, QWidget)

from ui.utils import operation_error as oh
from ui.utils import operation_error_dialog as ohd
import ui.dashboard_page as dp

GIZLI = "C:/Users/Universe/AppData/Local/gizli.db token=SECRET123 SELECT * FROM offers"
FIRMA = "Gizli Firma A.Ş."
TEKLIF_NO = "SNS-000042"

HATALAR = {
    "integrity": sqlite3.IntegrityError(f"UNIQUE constraint failed: offers.offer_no {GIZLI}"),
    "locked": sqlite3.OperationalError("database is locked"),
    "operational": sqlite3.OperationalError(f"no such table: offers {GIZLI}"),
    "generic": RuntimeError(f"beklenmeyen {GIZLI}"),
}
TEKNIK = ("operational", "generic")

SIZINTI = ("SECRET123", "C:/Users", "SELECT", "UNIQUE constraint",
           "no such table", "database is locked", FIRMA)
# Yanlış genelleme yasağı (kısmi başarı kuralı)
YANLIS_GENELLEME = ("hiçbir değişiklik yapılmadı", "Tüm işlem başarısız",
                    "Bütün kayıtlar silinemedi", "hiçbir teklif")


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

    @property
    def guvenli_log_sayisi(self):
        return len([s for s in self.satirlar if "başarısız — hata=" in s])


def _teklif(oid=7, no=TEKLIF_NO, firma=FIRMA):
    return SimpleNamespace(id=oid, offer_no=no, company_name=firma,
                           customer_email="a@b.c", currency="TL",
                           items=[SimpleNamespace(product_code="P1")],
                           status="Beklemede")


class _Temel(unittest.TestCase):
    """Gerçek slot gövdeleri; ağır `__init__` çalıştırılmaz."""

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
        self.startfile = mock.patch.object(os, "startfile", create=True).start()
        self.addCleanup(mock.patch.stopall)

        self.kutular = []          # (baslik, metin, dugmeler)

        def _kaydet(kutu, *a, **k):
            self.kutular.append((kutu.windowTitle(), kutu.text(),
                                 [b.text() for b in kutu.buttons()]))
            return QMessageBox.StandardButton.Ok

        mock.patch.object(QMessageBox, "exec", _kaydet).start()
        for ad in ("warning", "information", "critical"):
            mock.patch.object(
                QMessageBox, ad,
                staticmethod(lambda p, b, m, *a, _t=ad, **k:
                             (self.kutular.append((b, m, [])),
                              QMessageBox.StandardButton.Ok)[1])).start()
        mock.patch.object(
            QMessageBox, "question",
            staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)).start()
        from core.app_paths import LOG_DIR
        LOG_DIR.mkdir(parents=True, exist_ok=True)

    # ── sahne kurulumu ──────────────────────────────────────────────────
    def _sayfa(self, **ozellik):
        d = dp.DashboardPage.__new__(dp.DashboardPage)
        QWidget.__init__(d)
        self.addCleanup(d.deleteLater)
        d.svc_o = mock.MagicMock()
        d._model = mock.MagicMock()
        d._refresh_stats = mock.MagicMock()
        d.on_enter = mock.MagicMock()
        d._refresh = mock.MagicMock()
        d._pdf_btn = mock.MagicMock()
        d._pdf_worker = None
        d._show_preview_dialog = mock.MagicMock()
        d._send_email = mock.MagicMock()
        d._expiry_asked_ids = set()
        for k, v in ozellik.items():
            setattr(d, k, v)
        return d

    # ── ortak iddialar ──────────────────────────────────────────────────
    @property
    def son_kutu(self):
        return self.kutular[-1] if self.kutular else (None, "", [])

    def _sizinti_yok(self):
        for _b, metin, _d in self.kutular:
            for parca in SIZINTI:
                self.assertNotIn(parca, metin, f"mesajda sızıntı: {parca}")
        for parca in SIZINTI:
            self.assertNotIn(parca, self.log.birlesik, f"logda sızıntı: {parca}")

    def _tam_bir_kez_loglandi(self, adet=1):
        self.assertEqual(self.log.guvenli_log_sayisi, adet,
                         f"güvenli log {adet} kez olmalıydı: {self.log.satirlar}")

    def _dugme_ipucu_tutarli(self):
        for _b, metin, dugmeler in self.kutular:
            ipucu = ohd.LOG_DUGME_METNI in metin
            dugme = ohd.LOG_DUGME_METNI in dugmeler
            self.assertEqual(ipucu, dugme,
                             f"ipucu={ipucu} düğme={dugme} · {metin!r}")

    def _yanlis_genelleme_yok(self):
        for _b, metin, _d in self.kutular:
            for yasak in YANLIS_GENELLEME:
                self.assertNotIn(yasak, metin, f"yanlış genelleme: {yasak}")


# ── 1. Tekil hata yolları ───────────────────────────────────────────────────

class TekilHataYollariTests(_Temel):

    def _dogrula(self, log_adedi=1):
        self._sizinti_yok()
        self._tam_bir_kez_loglandi(log_adedi)
        self._dugme_ipucu_tutarli()
        self._yanlis_genelleme_yok()

    def test_prompt_expired_offers_guncelleme_hatasi(self):
        for ad, exc in HATALAR.items():
            with self.subTest(hata=ad):
                self.kutular.clear(); self.log.satirlar.clear()
                d = self._sayfa()
                d.svc_o.cancel_expired.side_effect = exc
                d.svc_o.get_expired_pending.return_value = [_teklif()]

                def _onayla(kutu, *a, **k):
                    """Onay kutusunda 'İptal Olarak İşaretle'ye basılmış say."""
                    self.kutular.append((kutu.windowTitle(), kutu.text(),
                                         [b.text() for b in kutu.buttons()]))
                    kabul = next((b for b in kutu.buttons()
                                  if kutu.buttonRole(b)
                                  == QMessageBox.ButtonRole.AcceptRole), None)
                    if kabul is not None:
                        kabul.click()
                    return QMessageBox.StandardButton.Ok

                with mock.patch.object(QMessageBox, "exec", _onayla):
                    sonuc = dp.DashboardPage._prompt_expired_offers(d)
                self.assertFalse(sonuc, "hata sonrası True döndü")
                self._dogrula()

    def test_apply_status_hatasi(self):
        for ad, exc in HATALAR.items():
            with self.subTest(hata=ad):
                self.kutular.clear(); self.log.satirlar.clear()
                d = self._sayfa()
                d.svc_o.update_status.side_effect = exc
                dp.DashboardPage._apply_status(d, 0, _teklif(), "Onaylandı")
                self.assertEqual(d._model.update_offer_status.call_count, 0,
                                 "hatada model güncellendi")
                self.assertEqual(d._refresh_stats.call_count, 0,
                                 "hatada gereksiz refresh")
                metin = " ".join(m for _b, m, _d in self.kutular)
                # Genel istisnada işlem fiili görünür; sqlite hatalarında
                # sınıflandırılmış mesaj (çakışma/meşgul/tamamlanamadı) gelir.
                if ad == "generic":
                    self.assertIn("güncellenemedi", metin,
                                  f"servis hatasında yanlış fiil: {metin!r}")
                self.assertNotIn("durumu kaydedildi", metin,
                                 f"yazılmayan işlem kaydedildi sanıldı: {metin!r}")
                self._dogrula()

    def test_apply_status_ui_yenileme_hatasi_kaydi_inkar_etmiyor(self):
        """DB YAZILDI, yalnız ekran yenilenemedi → 'güncellenemedi' DENMEZ."""
        for ad, exc in HATALAR.items():
            with self.subTest(hata=ad):
                self.kutular.clear(); self.log.satirlar.clear()
                d = self._sayfa()
                d.svc_o.update_status.return_value = None
                d._model.update_offer_status.side_effect = exc
                dp.DashboardPage._apply_status(d, 0, _teklif(), "Onaylandı")

                self.assertEqual(d.svc_o.update_status.call_count, 1,
                                 "servis tam bir kez çağrılmalıydı")
                self.assertEqual(d._refresh_stats.call_count, 0,
                                 "UI hatasından sonra istatistik yenilendi")
                metin = " ".join(m for _b, m, _d in self.kutular)
                self.assertNotIn("güncellenemedi", metin,
                                 f"kaydedilen işlem inkâr edildi: {metin!r}")
                self.assertIn("durumu kaydedildi", metin,
                              f"kaydın yapıldığı söylenmiyor: {metin!r}")
                self.assertIn("yenilene", metin,
                              f"yenileme sorunu belirtilmiyor: {metin!r}")
                self.assertRegex(metin, r"(?i)sayfay[ıi] yeniden a",
                                 f"sonraki adım verilmemiş: {metin!r}")
                self._dogrula()

    def test_save_as_template_yukleme_hatasi(self):
        for ad, exc in HATALAR.items():
            with self.subTest(hata=ad):
                self.kutular.clear(); self.log.satirlar.clear()
                d = self._sayfa(_selected=lambda: _teklif())
                d.svc_o.get_by_id.side_effect = exc
                dp.DashboardPage._save_as_template(d)
                self._dogrula()

    def test_save_as_template_kaydetme_hatasi(self):
        for ad, exc in HATALAR.items():
            with self.subTest(hata=ad):
                self.kutular.clear(); self.log.satirlar.clear()
                d = self._sayfa(_selected=lambda: _teklif())
                d.svc_o.get_by_id.return_value = _teklif()
                svc = mock.MagicMock()
                svc.create_from_offer.side_effect = exc
                with mock.patch("services.template_service.TemplateService",
                                return_value=svc), \
                     mock.patch.object(QInputDialog, "getText",
                                       staticmethod(lambda *a, **k: ("Şablon", True))):
                    dp.DashboardPage._save_as_template(d)
                self._dogrula()

    def test_preview_pdf_yukleme_hatasi(self):
        for ad, exc in HATALAR.items():
            with self.subTest(hata=ad):
                self.kutular.clear(); self.log.satirlar.clear()
                d = self._sayfa(_selected=lambda: _teklif())
                d.svc_o.get_by_id.side_effect = exc
                dp.DashboardPage._preview_pdf(d)
                self.assertEqual(d._show_preview_dialog.call_count, 0)
                self._dogrula()

    def test_preview_pdf_uretim_hatasi(self):
        for ad, exc in HATALAR.items():
            with self.subTest(hata=ad):
                self.kutular.clear(); self.log.satirlar.clear()
                d = self._sayfa(_selected=lambda: _teklif())
                d.svc_o.get_by_id.return_value = _teklif()
                with mock.patch("pdf.pdf_generator.generate_pdf",
                                side_effect=exc):
                    dp.DashboardPage._preview_pdf(d)
                self.assertEqual(d._show_preview_dialog.call_count, 0)
                self._dogrula()

    def test_email_selected_hatalari(self):
        for ad, exc in HATALAR.items():
            for asama in ("yukle", "pdf"):
                with self.subTest(hata=ad, asama=asama):
                    self.kutular.clear(); self.log.satirlar.clear()
                    d = self._sayfa(_selected=lambda: _teklif())
                    if asama == "yukle":
                        d.svc_o.get_by_id.side_effect = exc
                        dp.DashboardPage._email_selected(d)
                    else:
                        d.svc_o.get_by_id.return_value = _teklif()
                        with mock.patch("pdf.pdf_generator.generate_pdf",
                                        side_effect=exc):
                            dp.DashboardPage._email_selected(d)
                    self.assertEqual(d._send_email.call_count, 0)
                    self._dogrula()

    def test_gen_pdf_tek_teklif_yukleme_hatasi(self):
        for ad, exc in HATALAR.items():
            with self.subTest(hata=ad):
                self.kutular.clear(); self.log.satirlar.clear()
                d = self._sayfa(_selected_all=lambda: [_teklif()])
                d.svc_o.get_by_id.side_effect = exc
                dp.DashboardPage._gen_pdf(d)
                self.assertIsNone(d._pdf_worker, "hatada worker başlatıldı")
                self._dogrula()

    def test_do_export_hatasi(self):
        for ad, exc in HATALAR.items():
            with self.subTest(hata=ad):
                self.kutular.clear(); self.log.satirlar.clear()
                d = self._sayfa()
                d._model.rowCount.return_value = 1
                d._model.offers_at_rows.return_value = [_teklif()]
                with mock.patch.object(
                        QFileDialog, "getSaveFileName",
                        staticmethod(lambda *a, **k: ("C:/tmp/x.xlsx", ""))), \
                     mock.patch("services.export_service.export_excel",
                                side_effect=exc):
                    dp.DashboardPage._do_export(d, "excel")
                self._dogrula()


# ── 2. Toplu / kısmi başarı yolları ─────────────────────────────────────────

class TopluHataTests(_Temel):

    def _sayilar_var(self, *sayilar):
        metin = " ".join(m for _b, m, _d in self.kutular)
        for s in sayilar:
            self.assertIn(str(s), metin, f"güvenli sayı yok: {s} · {metin!r}")

    def test_delete_kismi_basari(self):
        d = self._sayfa(_selected_all=lambda: [_teklif(1, "A"), _teklif(2, "B"),
                                               _teklif(3, "C")])
        d.svc_o.delete.side_effect = [None, HATALAR["generic"], None]
        dp.DashboardPage._delete(d)
        self._sizinti_yok()
        self._tam_bir_kez_loglandi(1)
        self._yanlis_genelleme_yok()
        self._dugme_ipucu_tutarli()
        self._sayilar_var(2, 1)          # 2 silindi, 1 silinemedi
        self.assertEqual(d.on_enter.call_count, 1, "başarılılar için refresh yok")

    def test_delete_tumu_basarisiz(self):
        d = self._sayfa(_selected_all=lambda: [_teklif(1), _teklif(2)])
        d.svc_o.delete.side_effect = [HATALAR["operational"], HATALAR["generic"]]
        dp.DashboardPage._delete(d)
        self._sizinti_yok()
        self._tam_bir_kez_loglandi(2)
        self._yanlis_genelleme_yok()
        self._sayilar_var(0, 2)

    def test_delete_tek_hata(self):
        d = self._sayfa(_selected_all=lambda: [_teklif(1)])
        d.svc_o.delete.side_effect = HATALAR["locked"]
        dp.DashboardPage._delete(d)
        self._sizinti_yok()
        self._tam_bir_kez_loglandi(1)
        self._dugme_ipucu_tutarli()

    def test_gen_pdf_coklu_yuklemede_kismi_hata(self):
        d = self._sayfa(_selected_all=lambda: [_teklif(1, "A"), _teklif(2, "B")])
        d.svc_o.get_by_id.side_effect = [_teklif(1, "A"), HATALAR["generic"]]
        with mock.patch.object(QFileDialog, "getExistingDirectory",
                               staticmethod(lambda *a, **k: str(
                                   __import__("tempfile").gettempdir()))), \
             mock.patch.object(dp, "PdfWorker") as sahte:
            dp.DashboardPage._gen_pdf(d)
        self._sizinti_yok()
        self._tam_bir_kez_loglandi(1)
        self._yanlis_genelleme_yok()
        self.assertEqual(sahte.call_count, 1,
                         "başarılı görevler için worker başlatılmadı")

    def test_on_pdf_finished_hata_listesi_guvenli(self):
        d = self._sayfa()
        hatalar = [(HATALAR["generic"], 11), (HATALAR["operational"], 12)]
        dp.DashboardPage._on_pdf_finished(d, [], hatalar)
        self._sizinti_yok()
        self._tam_bir_kez_loglandi(2)
        self._yanlis_genelleme_yok()
        self._dugme_ipucu_tutarli()

    def test_pdf_worker_ham_metin_uretmiyor(self):
        """Worker `errors` listesine str(exception) KOYMAZ."""
        gorev = [(_teklif(9), "C:/tmp/a.pdf", {})]
        w = dp.PdfWorker(gorev)
        alinan = {}
        w.result_ready.connect(lambda g, e: alinan.update(g=g, e=e))
        with mock.patch("pdf.pdf_generator.generate_pdf",
                        side_effect=HATALAR["generic"]):
            dp.PdfWorker.run(w)
        self.assertEqual(alinan["g"], [])
        self.assertEqual(len(alinan["e"]), 1)
        for oge in alinan["e"]:
            self.assertNotIsInstance(oge, str,
                                     "worker ham metin üretiyor")
            exc, kayit_id = oge
            self.assertIsInstance(exc, BaseException)
            self.assertNotIn(FIRMA, str(kayit_id))

    def test_qthread_finished_golgelenmiyor(self):
        self.assertNotIn("finished", vars(dp.PdfWorker))


# ── 3. Doğrulama mesajları ──────────────────────────────────────────────────

class DogrulamaMesajTests(_Temel):

    def test_secim_yok_mesajlarinda_log_dugmesi_yok(self):
        d = self._sayfa(_selected=lambda: None, _selected_all=lambda: [])
        for slot in ("_save_as_template", "_preview_pdf", "_email_selected",
                     "_gen_pdf", "_delete"):
            with self.subTest(slot=slot):
                self.kutular.clear(); self.log.satirlar.clear()
                getattr(dp.DashboardPage, slot)(d)
                for _b, metin, dugmeler in self.kutular:
                    self.assertNotIn(ohd.LOG_DUGME_METNI, metin)
                    self.assertNotIn(ohd.LOG_DUGME_METNI, dugmeler)
                self.assertEqual(self.log.guvenli_log_sayisi, 0,
                                 "doğrulama mesajı hata olarak loglandı")
        self.assertEqual(self.startfile.call_count, 0)


# ── 4. Kaynak temizliği ─────────────────────────────────────────────────────

class KaynakTemizligiTests(unittest.TestCase):

    def test_ham_hata_gosterimi_kalmadi(self):
        import inspect
        kaynak = inspect.getsource(dp)
        hedefler = ("_prompt_expired_offers", "_apply_status",
                    "_save_as_template", "_preview_pdf", "_email_selected",
                    "_gen_pdf", "_on_pdf_finished", "_delete", "_do_export")
        for ad in hedefler:
            govde = inspect.getsource(getattr(dp.DashboardPage, ad))
            with self.subTest(slot=ad):
                for yasak in ("{e}", "{exc}", "str(e)", "str(exc)",
                              "exc_info=True"):
                    self.assertNotIn(yasak, govde,
                                     f"{ad} hâlâ ham hata kullanıyor: {yasak}")
        worker = inspect.getsource(dp.PdfWorker)
        for yasak in ("{e}", "str(e)"):
            self.assertNotIn(yasak, worker, f"PdfWorker ham metin: {yasak}")
        del kaynak


if __name__ == "__main__":
    unittest.main(verbosity=2)
