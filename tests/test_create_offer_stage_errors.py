"""R10-C — `_finish_offer` / `_preview_pdf` aşama sınırları.

Kural: **bir aşamanın hatası önceki başarılı aşamayı inkâr etmez.**

  A — DB kaydı            → hata: hiçbir şey değişmedi
  B — kullanıcının PDF'i  → hata: teklif KAYDEDİLDİ, PDF yok
  C — program içi arşiv   → hata: A ve B başarılı sayılır
  D — sonraki eylemler    → hata: A/B/C başarısını düşürmez

Gerçek slot gövdeleri offscreen çalıştırılır; servis, PDF, dosya ve e-posta
aşamaları ayrı ayrı bozulur. Gerçek kullanıcı DB'si, PDF klasörü, Credential
Manager, SMTP ve Explorer KULLANILMAZ.
"""
import logging
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import mock

from PySide6.QtWidgets import (QApplication, QFileDialog, QMessageBox,
                               QWidget)

from ui.utils import operation_error_dialog as ohd
import ui.create_offer_page as cop

GIZLI = "C:/Users/Universe/AppData/Local/gizli.db token=SECRET123 SELECT * FROM offers"
FIRMA = "Gizli Firma A.Ş."
HATALAR = {
    "integrity": sqlite3.IntegrityError(f"UNIQUE constraint failed {GIZLI}"),
    "locked": sqlite3.OperationalError("database is locked"),
    "operational": sqlite3.OperationalError(f"no such table: offers {GIZLI}"),
    "generic": RuntimeError(f"beklenmeyen {GIZLI}"),
}
SIZINTI = ("SECRET123", "SELECT", "UNIQUE constraint", "no such table", FIRMA)
YASAK_MESAJ = ("İşlem tamamlanamadı", "Teklif kaydedilemedi")


class _Log(logging.Handler):
    def __init__(self):
        super().__init__()
        self.satir = []

    def emit(self, kayit):
        m = str(kayit.getMessage())
        if kayit.exc_info:
            import traceback
            m += "".join(traceback.format_exception(*kayit.exc_info))
        self.satir.append(m)

    @property
    def birlesik(self):
        return "\n".join(self.satir)

    @property
    def guvenli_sayisi(self):
        return len([s for s in self.satir if "başarısız — hata=" in s])


class _Temel(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self._tmp = TemporaryDirectory(prefix="r10c_")
        self.addCleanup(self._tmp.cleanup)
        self.kok = Path(self._tmp.name)
        self.out = self.kok / "kullanici.pdf"

        self.log = _Log()
        kok_log = logging.getLogger()
        kok_log.addHandler(self.log)
        self._eski = kok_log.level
        kok_log.setLevel(logging.DEBUG)
        self.addCleanup(lambda: (kok_log.removeHandler(self.log),
                                 kok_log.setLevel(self._eski)))

        self.kutular = []
        self.startfile = mock.patch.object(os, "startfile", create=True).start()
        self.addCleanup(mock.patch.stopall)
        for ad in ("warning", "information", "critical"):
            mock.patch.object(
                QMessageBox, ad,
                staticmethod(lambda p, b, m, *a, **k:
                             (self.kutular.append((b, m, [])),
                              QMessageBox.StandardButton.Ok)[1])).start()
        mock.patch.object(QFileDialog, "getSaveFileName",
                          staticmethod(lambda *a, **k: (str(self.out), ""))).start()
        # Varsayılan: hiçbir modal beklemez. `_calistir` gerektiğinde kendi
        # exec yamasını başlatır ve sonradan başlayan yama üstün gelir.
        mock.patch.object(
            QMessageBox, "exec",
            lambda kutu, *a, **k: (
                self.kutular.append((kutu.windowTitle(), kutu.text(),
                                     [b.text() for b in kutu.buttons()])),
                QMessageBox.StandardButton.Ok)[1]).start()
        from core.app_paths import LOG_DIR
        LOG_DIR.mkdir(parents=True, exist_ok=True)

    # ── sahne ───────────────────────────────────────────────────────────
    def _sayfa(self):
        d = cop.CreateOfferPage.__new__(cop.CreateOfferPage)
        QWidget.__init__(d)
        self.addCleanup(d.deleteLater)
        d.offer_svc = mock.MagicMock()
        d.offer_svc.save.return_value = 55
        d.offer_svc.preview_offer_no.return_value = "PRE-0001"
        d._current_offer_id = None
        d._is_new = True
        d._offer_no = "PRE-0001"
        d.offer_no_lbl = mock.MagicMock()
        d._validate_step1 = lambda: True
        d._validate_products = lambda: True
        d._validate_pdf_requirements = lambda: True
        d._collect_data = lambda: SimpleNamespace(
            id=d._current_offer_id, offer_no="GERCEK-0009",
            company_name=FIRMA, customer_email="a@b.c", items=[1])
        self.reset = {"n": 0}
        d._reset_to_new = lambda: self.reset.__setitem__("n", self.reset["n"] + 1)
        self.emit = {"n": 0}
        d.offer_saved = SimpleNamespace(
            emit=lambda: self.emit.__setitem__("n", self.emit["n"] + 1))
        return d

    def _calistir(self, d, *, pdf_hatasi=None, copy_hatasi=None,
                  kutu_hatasi=None, startfile_hatasi=None, cfg_hatasi=None,
                  email_hatasi=None, dugme=None):
        pdf = {"n": 0}

        def _pdf(data, yol):
            pdf["n"] += 1
            if pdf_hatasi:
                raise pdf_hatasi
            Path(yol).write_bytes(b"%PDF-1.4")

        def _copy2(a, b):
            if copy_hatasi:
                raise copy_hatasi
            Path(b).write_bytes(Path(a).read_bytes())

        def _exec(kutu, *a, **k):
            self.kutular.append((kutu.windowTitle(), kutu.text(),
                                 [b.text() for b in kutu.buttons()]))
            if kutu_hatasi:
                raise kutu_hatasi
            if dugme:
                hedef = next((b for b in kutu.buttons() if b.text() == dugme), None)
                if hedef is not None:
                    hedef.click()
            return QMessageBox.StandardButton.Ok

        # `os.startfile` ÖLÇÜLEBİLİR: kaç kez ve hangi yolla çağrıldı.
        # Hata senaryosunda da önce sayılır, sonra fırlatılır — böylece
        # "denendi mi?" ile "başarılı mı?" ayrışır.
        self.startfile_acilan = 0
        self.startfile_yollari = []

        def _startfile(yol, *a, **k):
            self.startfile_acilan += 1
            self.startfile_yollari.append(yol)
            if startfile_hatasi:
                raise startfile_hatasi

        def _cfg():
            if cfg_hatasi:
                raise cfg_hatasi
            return {"smtp_server": "s", "smtp_user": "u"}

        self.email_acilan = 0
        test = self

        class _Email:
            def __init__(self, **k):
                test.email_acilan += 1
                if email_hatasi:
                    raise email_hatasi

            def exec(self):
                return 0

        with mock.patch("pdf.pdf_generator.generate_pdf", _pdf), \
             mock.patch("shutil.copy2", _copy2), \
             mock.patch.object(QMessageBox, "exec", _exec), \
             mock.patch.object(os, "startfile", _startfile, create=True), \
             mock.patch("core.config.load_company_config", _cfg), \
             mock.patch("ui.dialogs.email_dialog.EmailDialog", _Email):
            cop.CreateOfferPage._finish_offer(d)
        return pdf["n"]

    # ── ortak iddialar ──────────────────────────────────────────────────
    @property
    def metin(self):
        return " | ".join(m for _b, m, _d in self.kutular)

    def _sizinti_yok(self):
        for parca in SIZINTI:
            self.assertNotIn(parca, self.metin, f"mesajda sızıntı: {parca}")
            self.assertNotIn(parca, self.log.birlesik, f"logda sızıntı: {parca}")

    def _inkar_yok(self):
        for yasak in YASAK_MESAJ:
            self.assertNotIn(yasak, self.metin,
                             f"kaydedilmiş işlem inkâr edildi: {yasak}")

    def _dugme_ipucu_tutarli(self):
        for _b, metin, dugmeler in self.kutular:
            self.assertEqual(ohd.LOG_DUGME_METNI in metin,
                             ohd.LOG_DUGME_METNI in dugmeler,
                             f"ipucu/düğme tutarsız: {metin!r} {dugmeler}")


# ── AŞAMA A ─────────────────────────────────────────────────────────────────

class AsamaA_DbKaydiTests(_Temel):

    def test_save_hatasinda_hicbir_sey_degismez(self):
        for ad, exc in HATALAR.items():
            with self.subTest(hata=ad):
                self.kutular.clear(); self.log.satir.clear()
                d = self._sayfa()
                d.offer_svc.save.side_effect = exc
                pdf_sayisi = self._calistir(d)
                self.assertEqual(d.offer_svc.save.call_count, 1)
                self.assertEqual(pdf_sayisi, 0, "kayıt yokken PDF üretildi")
                self.assertIsNone(d._current_offer_id)
                self.assertTrue(d._is_new)
                self.assertEqual(d._offer_no, "PRE-0001")
                self.assertEqual(self.reset["n"], 0)
                self.assertEqual(self.emit["n"], 0)
                self.assertEqual(self.log.guvenli_sayisi, 1)
                self._sizinti_yok()
                self._dugme_ipucu_tutarli()
                self.assertNotIn("kaydedildi ancak", self.metin)


# ── AŞAMA B ─────────────────────────────────────────────────────────────────

class AsamaB_AnaPdfTests(_Temel):

    def test_pdf_hatasi_kaydi_inkar_etmez(self):
        for ad, exc in HATALAR.items():
            with self.subTest(hata=ad):
                self.kutular.clear(); self.log.satir.clear()
                d = self._sayfa()
                self._calistir(d, pdf_hatasi=exc)
                self.assertEqual(d.offer_svc.save.call_count, 1)
                self.assertEqual(d._current_offer_id, 55,
                                 "kaydedilen teklif kimliği kayboldu")
                self.assertFalse(d._is_new)
                self.assertEqual(d._offer_no, "GERCEK-0009")
                self.assertEqual(self.reset["n"], 0, "form sıfırlandı")
                self.assertEqual(self.emit["n"], 0,
                                 "PDF yokken offer_saved yayıldı")
                self.assertEqual(self.log.guvenli_sayisi, 1)
                self._sizinti_yok()
                self._inkar_yok()
                self._dugme_ipucu_tutarli()
                self.assertIn("kaydedildi", self.metin)
                self.assertIn("PDF oluşturulamadı", self.metin)
                self.assertRegex(self.metin, r"(?i)tekrar deneyin")

    def test_yeniden_denemede_duplicate_olusmuyor(self):
        d = self._sayfa()
        gonderilen = []
        d.offer_svc.save.side_effect = lambda data: (
            gonderilen.append(getattr(data, "id", "YOK")), 55)[1]
        self._calistir(d, pdf_hatasi=HATALAR["generic"])
        self._calistir(d, pdf_hatasi=HATALAR["generic"])
        self.assertEqual(gonderilen, [None, 55],
                         "ikinci denemede INSERT yapılıyor (duplicate riski)")


# ── AŞAMA C ─────────────────────────────────────────────────────────────────

class AsamaC_ArsivTests(_Temel):

    def test_arsiv_hatasi_basariyi_dusurmez(self):
        d = self._sayfa()
        self._calistir(d, copy_hatasi=HATALAR["generic"])
        self.assertEqual(d._current_offer_id, 55)
        self.assertEqual(self.reset["n"], 1, "başarı finalizasyonu çalışmadı")
        self.assertEqual(self.emit["n"], 1)
        self.assertTrue(self.out.exists(), "kullanıcının PDF'i kayboldu")
        self._sizinti_yok()
        self._inkar_yok()

    def test_arsiv_hatasi_tek_modalda_durustce_bildirilir(self):
        d = self._sayfa()
        self._calistir(d, copy_hatasi=HATALAR["generic"])
        self.assertEqual(len(self.kutular), 1,
                         f"peş peşe fazladan modal: {self.kutular}")
        self.assertRegex(self.metin, r"(?i)ar[sş]iv",
                         f"arşiv eksikliği bildirilmiyor: {self.metin!r}")
        self._dugme_ipucu_tutarli()
        self.assertIn(ohd.LOG_DUGME_METNI, self.kutular[0][2],
                      "teknik arşiv hatasında log düğmesi yok")

    def test_arsiv_hatasi_guvenli_loglanir(self):
        d = self._sayfa()
        self._calistir(d, copy_hatasi=HATALAR["generic"])
        self.assertEqual(self.log.guvenli_sayisi, 1,
                         "arşiv hatası güvenli biçimde tam bir kez loglanmalı")
        self._sizinti_yok()
        self.assertNotIn(str(self.out), self.log.birlesik,
                         "tam kullanıcı yolu loglandı")

    def test_basarida_tam_yol_loglanmiyor(self):
        d = self._sayfa()
        self._calistir(d)
        self.assertNotIn(str(self.out), self.log.birlesik,
                         "başarı logunda tam kullanıcı yolu var")


# ── AŞAMA D ─────────────────────────────────────────────────────────────────

class AsamaD_SonrakiEylemlerTests(_Temel):

    def test_basari_kutusu_hatasi_finalizasyonu_engellemez(self):
        d = self._sayfa()
        self._calistir(d, kutu_hatasi=HATALAR["generic"])
        self._inkar_yok()
        self.assertEqual(self.reset["n"], 1, "reset çalışmadı")
        self.assertEqual(self.emit["n"], 1, "offer_saved yayılmadı")
        self.assertEqual(self.log.guvenli_sayisi, 1)
        self._sizinti_yok()

    def test_onizle_acilamazsa_eylemli_mesaj(self):
        d = self._sayfa()
        self._calistir(d, startfile_hatasi=HATALAR["generic"], dugme="Önizle")
        self.assertEqual(self.startfile_acilan, 1,
                         "startfile hiç denenmedi")
        self._inkar_yok()
        self.assertRegex(self.metin, r"(?i)a[çc][ıi]lamad",
                         f"açılamadı bilgisi yok: {self.metin!r}")
        self.assertRegex(self.metin, r"(?i)konumdan a[çc]",
                         f"sonraki adım yok: {self.metin!r}")
        self.assertEqual(self.reset["n"], 1)
        self.assertEqual(self.emit["n"], 1)
        self.assertEqual(self.log.guvenli_sayisi, 1)
        self._sizinti_yok()

    def test_eposta_asamasi_hatasi(self):
        for ad, kw in (("config", {"cfg_hatasi": HATALAR["generic"]}),
                       ("email", {"email_hatasi": HATALAR["generic"]})):
            with self.subTest(asama=ad):
                self.kutular.clear(); self.log.satir.clear()
                d = self._sayfa()
                self._calistir(d, dugme="Mail Gönder", **kw)
                self._inkar_yok()
                self.assertRegex(self.metin, r"(?i)e-posta",
                                 f"e-posta bilgisi yok: {self.metin!r}")
                self.assertEqual(self.reset["n"], 1)
                self.assertEqual(self.emit["n"], 1)
                self.assertEqual(self.log.guvenli_sayisi, 1)
                self._sizinti_yok()

    def test_reset_hatasi_emit_i_engellemez(self):
        """A) Form hazırlanamadı → sessiz kalınmaz, kayıt inkâr edilmez."""
        for ad, exc in HATALAR.items():
            with self.subTest(hata=ad):
                self.kutular.clear(); self.log.satir.clear()
                d = self._sayfa()
                d._reset_to_new = mock.MagicMock(side_effect=exc)
                self._calistir(d)
                self.assertEqual(self.emit["n"], 1,
                                 "reset hatası offer_saved'i engelledi")
                self.assertEqual(self.log.guvenli_sayisi, 1)
                self._inkar_yok()
                self._sizinti_yok()
                self._dugme_ipucu_tutarli()
                self.assertRegex(self.metin, r"(?i)kaydedildi",
                                 f"kayıt söylenmiyor: {self.metin!r}")
                self.assertRegex(self.metin, r"(?i)form(u)? haz[ıi]rlanamad",
                                 f"form sorunu belirtilmiyor: {self.metin!r}")
                self.assertRegex(self.metin, r"(?i)teklifler ekran",
                                 f"sonraki adım yok: {self.metin!r}")
                self.assertIn(ohd.LOG_DUGME_METNI,
                              [b for _t, _m, dl in self.kutular for b in dl],
                              "log düğmesi yok")

    def test_emit_hatasi_reset_i_engellemez(self):
        """B) Dashboard yenilenemedi → sessiz kalınmaz."""
        for ad, exc in HATALAR.items():
            with self.subTest(hata=ad):
                self.kutular.clear(); self.log.satir.clear()
                d = self._sayfa()
                d.offer_saved = SimpleNamespace(emit=mock.MagicMock(side_effect=exc))
                self._calistir(d)
                self.assertEqual(self.reset["n"], 1,
                                 "emit hatası reset'i engelledi")
                self.assertEqual(self.log.guvenli_sayisi, 1)
                self._inkar_yok()
                self._sizinti_yok()
                self._dugme_ipucu_tutarli()
                self.assertRegex(self.metin, r"(?i)kaydedildi")
                self.assertRegex(self.metin, r"(?i)yenilenemed",
                                 f"yenileme sorunu belirtilmiyor: {self.metin!r}")
                self.assertRegex(self.metin, r"(?i)teklifler",
                                 f"sonraki adım yok: {self.metin!r}")

    def test_iki_finalizasyon_hatasi_bagimsiz(self):
        """C) İkisi de patlasa bile ikisi de DENENİR; özyineleme olmaz."""
        d = self._sayfa()
        d._reset_to_new = mock.MagicMock(side_effect=HATALAR["generic"])
        emit = mock.MagicMock(side_effect=HATALAR["operational"])
        d.offer_saved = SimpleNamespace(emit=emit)
        self._calistir(d)
        self.assertEqual(d._reset_to_new.call_count, 1)
        self.assertEqual(emit.call_count, 1, "ikinci adım denenmedi")
        self.assertEqual(self.log.guvenli_sayisi, 2,
                         "her istisna tam bir kez loglanmalı")
        self._inkar_yok()
        self._sizinti_yok()
        self._dugme_ipucu_tutarli()
        # Sonuç kutusu + iki kısmi uyarı; özyinelemeli kutu seli YOK
        self.assertLessEqual(len(self.kutular), 3,
                             f"özyinelemeli hata kutusu: {self.kutular}")

    # ── D) Buton yönlendirmesi ──────────────────────────────────────────
    def test_onizle_dugmesi_dosyayi_acar(self):
        d = self._sayfa()
        self._calistir(d, dugme="Önizle")
        self.assertEqual(self.startfile_acilan, 1,
                         "Önizle dosyayı açmadı")
        self.assertEqual(self.startfile_yollari, [str(self.out)],
                         "yanlış dosya açıldı")
        self.assertEqual(self.email_acilan, 0, "Önizle e-posta penceresi açtı")
        self.assertEqual(self.reset["n"], 1)
        self.assertEqual(self.emit["n"], 1)

    def test_mail_dugmesi_eposta_penceresini_acar(self):
        d = self._sayfa()
        self._calistir(d, dugme="Mail Gönder")
        self.assertEqual(self.email_acilan, 1,
                         "Mail Gönder e-posta penceresini açmadı")
        self.assertEqual(self.startfile_acilan, 0,
                         "Mail Gönder dosyayı da açtı")
        self.assertEqual(self.reset["n"], 1)
        self.assertEqual(self.emit["n"], 1)

    def test_kapat_dugmesi_ek_eylem_baslatmaz(self):
        d = self._sayfa()
        self._calistir(d, dugme="Kapat")
        self.assertEqual(self.email_acilan, 0, "Kapat e-posta penceresi açtı")
        self.assertEqual(self.startfile_acilan, 0, "Kapat dosya açtı")
        self.assertEqual(self.reset["n"], 1)
        self.assertEqual(self.emit["n"], 1)
        self.assertEqual(self.log.guvenli_sayisi, 0)

    def test_buton_karsilastirmasi_kimlik_bagimsiz(self):
        """`clickedButton()` farklı bir Python proxy'si dönse de çalışmalı."""
        import inspect
        govde = inspect.getsource(cop.CreateOfferPage._finish_offer)
        for yasak in ("clicked is btn_preview", "clicked is btn_mail",
                      "clicked is btn_close"):
            self.assertNotIn(yasak, govde,
                             f"`is` kimlik karşılaştırması kullanılıyor: {yasak}")

    def test_tam_basari_degismedi(self):
        d = self._sayfa()
        self._calistir(d)
        self.assertEqual(self.reset["n"], 1)
        self.assertEqual(self.emit["n"], 1)
        self.assertEqual(self.log.guvenli_sayisi, 0, "başarıda hata loglandı")
        self.assertEqual(len(self.kutular), 1)
        self.assertNotIn(ohd.LOG_DUGME_METNI, self.kutular[0][1])
        self._inkar_yok()
        self._sizinti_yok()


# ── _preview_pdf ────────────────────────────────────────────────────────────

class OnizlemeTests(_Temel):

    def _onizle(self, d, *, pdf_hatasi=None, dialog_hatasi=None):
        acilan = {"n": 0}

        def _pdf(data, yol):
            if pdf_hatasi:
                raise pdf_hatasi
            Path(yol).write_bytes(b"%PDF-1.4")

        class _Dlg:
            def __init__(self, **k):
                acilan["n"] += 1
                if dialog_hatasi:
                    raise dialog_hatasi

            def exec(self):
                return 0

        with mock.patch("pdf.pdf_generator.generate_pdf", _pdf), \
             mock.patch("ui.dialogs.pdf_preview_dialog.PdfPreviewDialog", _Dlg):
            cop.CreateOfferPage._preview_pdf(d)
        return acilan["n"]

    def test_pdf_hatasinda_dialog_acilmaz(self):
        for ad, exc in HATALAR.items():
            with self.subTest(hata=ad):
                self.kutular.clear(); self.log.satir.clear()
                d = self._sayfa()
                acilan = self._onizle(d, pdf_hatasi=exc)
                self.assertEqual(acilan, 0, "PDF yokken önizleme açıldı")
                self.assertEqual(self.log.guvenli_sayisi, 1)
                self._sizinti_yok()
                self._dugme_ipucu_tutarli()

    def test_dialog_hatasi_pdf_basarisini_inkar_etmez(self):
        d = self._sayfa()
        self._onizle(d, dialog_hatasi=HATALAR["generic"])
        self.assertEqual(self.log.guvenli_sayisi, 1)
        self._sizinti_yok()
        self.assertNotIn("PDF oluşturulamadı", self.metin,
                         f"üretilen PDF inkâr edildi: {self.metin!r}")

    def test_basarida_mesaj_yok(self):
        d = self._sayfa()
        acilan = self._onizle(d)
        self.assertEqual(acilan, 1)
        self.assertEqual(self.kutular, [])
        self.assertEqual(self.log.guvenli_sayisi, 0)


# ── Kaynak temizliği ────────────────────────────────────────────────────────

class KaynakTemizligiTests(unittest.TestCase):

    def test_ana_kapsamda_ham_hata_yok(self):
        import inspect
        for ad in ("_finish_offer", "_preview_pdf"):
            govde = inspect.getsource(getattr(cop.CreateOfferPage, ad))
            with self.subTest(slot=ad):
                for yasak in ("{e}", "{exc}", "str(e)", "str(exc)",
                              "exc_info=True"):
                    self.assertNotIn(yasak, govde, f"{ad}: {yasak}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
