"""O14 — müşteri/ürün kaydetme ve silme hatalarının kullanıcıya bildirimi.

Ölçüm: `CustomersPage._edit` hatayı tamamen sessiz yutuyordu (0 mesaj, tablo
yenilenmiyor, yalnız ERROR log). Diğer yollarda mesaj vardı ama ham
`str(exception)` kullanıcıya gösteriliyordu; ürün sayfasında ise hiç log
yoktu. Ayrıca hata anında dialog zaten kapalı olduğu için kullanıcı girdisi
kayboluyordu.

Gerçek DB ve gerçek kişisel veri KULLANILMAZ: mock servis + sahte veri.
"""
import logging
import os
import sqlite3
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

import ui.customers_page as cp
import ui.products_page as pp
from models.customer import Customer
from models.product import Product
from ui.utils import operation_error as oh

GIZLI = "GIZLI-MUSTERI-VERISI"
SAHTE_AD = "TEST-FIRMA-XYZ"


def _hata(sinif=RuntimeError, metin=None):
    return sinif(metin if metin is not None else f"detay {GIZLI}")


class _LogYakala(logging.Handler):
    def __init__(self):
        super().__init__()
        self.satirlar = []

    def emit(self, r):
        try:
            self.satirlar.append(f"{r.levelname}:{r.name}:{r.getMessage()}")
            if r.exc_info:
                import traceback
                self.satirlar.append("".join(
                    traceback.format_exception(*r.exc_info)))
        except Exception:
            pass


class _Temel(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.kutular = {"warning": [], "information": [], "critical": []}
        self.log = _LogYakala()
        kok = logging.getLogger()
        kok.addHandler(self.log)
        eski = kok.level
        kok.setLevel(logging.DEBUG)
        self.addCleanup(kok.setLevel, eski)
        self.addCleanup(kok.removeHandler, self.log)

    # ── ortak yardımcılar ────────────────────────────────────────────────

    def _kutulari_yakala(self, modul):
        return [
            mock.patch.object(modul.QMessageBox, "warning",
                              side_effect=lambda p, b, m, *a, **k:
                              self.kutular["warning"].append((b, m))),
            mock.patch.object(modul.QMessageBox, "information",
                              side_effect=lambda p, b, m, *a, **k:
                              self.kutular["information"].append((b, m))),
            mock.patch.object(modul.QMessageBox, "critical",
                              side_effect=lambda p, b, m, *a, **k:
                              self.kutular["critical"].append((b, m))),
            mock.patch.object(modul.QMessageBox, "question",
                              return_value=QMessageBox.StandardButton.Yes),
        ]

    def _musteri_sayfasi(self):
        s = cp.CustomersPage.__new__(cp.CustomersPage)
        s.service = mock.Mock()
        s.service.add.return_value = 7
        s.offer_svc = mock.Mock()
        s.offer_svc.get_by_customer.return_value = []
        s._customers = [Customer(id=1, company_name=SAHTE_AD)]
        s._load = mock.Mock()
        s.search = mock.Mock()
        s.search.text.return_value = ""
        s._selected = lambda: s._customers[0]
        s._selected_all = lambda: s._customers
        return s

    def _urun_sayfasi(self):
        s = pp.ProductsPage.__new__(pp.ProductsPage)
        s.service = mock.Mock()
        s.service.add.return_value = 9
        s._products = [Product(id=1, product_code="T-1", product_name="Test")]
        s._load = mock.Mock()
        s._load_filtered = mock.Mock()
        s._selected = lambda: s._products[0]
        s._selected_all = lambda: s._products
        return s

    def _sahte_dialog(self, sonuclar):
        """exec() sırayla `sonuclar` döndürür; aynı NESNE korunur."""
        dlg = mock.MagicMock()
        dlg.exec.side_effect = list(sonuclar)
        dlg.get_customer.return_value = Customer(id=1, company_name=SAHTE_AD)
        dlg.get_product.return_value = Product(id=1, product_code="T-1",
                                               product_name="Test")
        return dlg

    def _calistir(self, modul, sayfa, slot, dialog_adi, dlg):
        yamalar = self._kutulari_yakala(modul)
        yamalar.append(mock.patch.object(modul, dialog_adi, return_value=dlg))
        for y in yamalar:
            y.start()
        try:
            getattr(type(sayfa), slot)(sayfa)
        finally:
            for y in yamalar:
                y.stop()

    # ── ortak doğrulamalar ───────────────────────────────────────────────

    def _mesaj_guvenli(self):
        self.assertTrue(self.kutular["warning"], "kullanıcıya mesaj yok")
        for _b, m in self.kutular["warning"]:
            self.assertNotIn(GIZLI, m, "ham istisna metni kullanıcıya gösterildi")
            self.assertNotIn("Traceback", m)
            self.assertNotIn("SELECT", m.upper())

    def _log_guvenli(self):
        birlesik = "\n".join(self.log.satirlar)
        self.assertNotIn(GIZLI, birlesik, "ham istisna metni log'a yazıldı")
        self.assertNotIn(SAHTE_AD, birlesik, "kişisel veri log'a yazıldı")


class HelperMessageTests(_Temel):
    """`operation_error` sözleşmesi."""

    def test_integrity_error_message(self):
        m = oh.guvenli_mesaj(sqlite3.IntegrityError(f"UNIQUE {GIZLI}"),
                             "Müşteri")
        self.assertIn("çakışıyor", m)
        self.assertNotIn(GIZLI, m)

    def test_locked_operational_error_message(self):
        m = oh.guvenli_mesaj(sqlite3.OperationalError("database is locked"),
                             "Müşteri")
        self.assertIn("meşgul", m)

    def test_other_operational_error_message(self):
        m = oh.guvenli_mesaj(sqlite3.OperationalError("no such column x"),
                             "Müşteri")
        self.assertIn("tamamlanamadı", m)
        self.assertNotIn("no such column", m)

    def test_generic_save_and_delete_messages(self):
        self.assertIn("kaydedilemedi",
                      oh.guvenli_mesaj(RuntimeError(GIZLI), "Müşteri", "kaydet"))
        self.assertIn("silinemedi",
                      oh.guvenli_mesaj(RuntimeError(GIZLI), "Ürün", "sil"))

    def test_duplicate_product_code_message_is_preserved(self):
        from services.product_service import DuplicateProductCodeError
        mevcut = Product(id=3, product_code="ABC-1", product_name="Var Olan")
        m = oh.guvenli_mesaj(DuplicateProductCodeError(mevcut), "Ürün")
        self.assertIn("ABC-1", m)
        self.assertIn("Var Olan", m)

    def test_foreign_exception_with_existing_field_gets_generic_message(self):
        """Duck typing YOK: `existing` taşıyan yabancı istisna veri sızdırmamalı."""
        class _Sahte(RuntimeError):
            pass

        sahte = _Sahte(f"detay {GIZLI}")
        sahte.existing = Product(id=9, product_code=GIZLI,
                                 product_name=f"AD-{GIZLI}")
        m = oh.guvenli_mesaj(sahte, "Ürün")
        self.assertNotIn(GIZLI, m, "yabancı istisnadan veri sızdı")
        self.assertIn("kaydedilemedi", m)

    def test_duplicate_values_are_not_logged(self):
        from services.product_service import DuplicateProductCodeError
        mevcut = Product(id=3, product_code="ABC-1", product_name="Var Olan")
        try:
            raise DuplicateProductCodeError(mevcut)
        except Exception as e:
            with self.assertLogs("islem_hatasi", level="ERROR") as c:
                oh.logla(e, "Ürün ekleme", kayit_id=3)
        cikti = "\n".join(c.output)
        self.assertNotIn("ABC-1", cikti, "ürün kodu log'a yazıldı")
        self.assertNotIn("Var Olan", cikti, "ürün adı log'a yazıldı")

    def test_log_has_no_raw_message_or_traceback_text(self):
        try:
            raise sqlite3.IntegrityError(f"UNIQUE {GIZLI}")
        except Exception as e:
            with self.assertLogs("islem_hatasi", level="ERROR") as c:
                oh.logla(e, "Müşteri güncelleme", kayit_id=5)
        cikti = "\n".join(c.output)
        self.assertNotIn(GIZLI, cikti)
        self.assertIn("IntegrityError", cikti)
        self.assertIn("id=5", cikti)


class CustomerEditTests(_Temel):

    def _senaryo(self, hata, exec_sonuclari, servis_yan_etki):
        sayfa = self._musteri_sayfasi()
        sayfa.service.update.side_effect = servis_yan_etki
        dlg = self._sahte_dialog(exec_sonuclari)
        self._calistir(cp, sayfa, "_edit", "CustomerDialog", dlg)
        return sayfa, dlg

    def test_error_shows_message_and_reopens_same_dialog(self):
        for sinif in (sqlite3.IntegrityError, sqlite3.OperationalError,
                      RuntimeError):
            with self.subTest(hata=sinif.__name__):
                self.kutular["warning"].clear()
                sayfa, dlg = self._senaryo(
                    sinif,
                    [QDialog.DialogCode.Accepted, QDialog.DialogCode.Rejected],
                    [_hata(sinif)])
                self._mesaj_guvenli()
                self.assertEqual(dlg.exec.call_count, 2,
                                 "aynı dialog yeniden açılmadı")
                sayfa._load.assert_not_called()

    def test_retry_success_refreshes_once(self):
        sayfa = self._musteri_sayfasi()
        sayfa.service.update.side_effect = [_hata(), None]
        dlg = self._sahte_dialog([QDialog.DialogCode.Accepted,
                                  QDialog.DialogCode.Accepted])
        self._calistir(cp, sayfa, "_edit", "CustomerDialog", dlg)
        self.assertEqual(sayfa.service.update.call_count, 2)
        sayfa._load.assert_called_once()
        self.assertEqual(dlg.exec.call_count, 2)

    def test_cancel_after_error_stops_without_write_or_refresh(self):
        sayfa, dlg = self._senaryo(
            RuntimeError,
            [QDialog.DialogCode.Accepted, QDialog.DialogCode.Rejected],
            [_hata()])
        self.assertEqual(sayfa.service.update.call_count, 1,
                         "iptalden sonra ikinci servis çağrısı yapıldı")
        sayfa._load.assert_not_called()

    def test_success_does_not_reopen_dialog(self):
        sayfa = self._musteri_sayfasi()
        sayfa.service.update.side_effect = None
        dlg = self._sahte_dialog([QDialog.DialogCode.Accepted])
        self._calistir(cp, sayfa, "_edit", "CustomerDialog", dlg)
        self.assertEqual(dlg.exec.call_count, 1)
        sayfa._load.assert_called_once()
        self.assertEqual(self.kutular["warning"], [])

    def test_plain_cancel_unchanged(self):
        sayfa = self._musteri_sayfasi()
        dlg = self._sahte_dialog([QDialog.DialogCode.Rejected])
        self._calistir(cp, sayfa, "_edit", "CustomerDialog", dlg)
        sayfa.service.update.assert_not_called()
        sayfa._load.assert_not_called()

    def test_log_is_safe(self):
        self._senaryo(RuntimeError,
                      [QDialog.DialogCode.Accepted, QDialog.DialogCode.Rejected],
                      [_hata()])
        self._log_guvenli()

    def test_success_log_uses_id_not_company_name(self):
        sayfa = self._musteri_sayfasi()
        sayfa.service.update.side_effect = None
        dlg = self._sahte_dialog([QDialog.DialogCode.Accepted])
        self._calistir(cp, sayfa, "_edit", "CustomerDialog", dlg)
        birlesik = "\n".join(self.log.satirlar)
        self.assertNotIn(SAHTE_AD, birlesik, "başarı logunda firma adı var")
        self.assertTrue(any("id=1" in s for s in self.log.satirlar),
                        f"başarı logunda id yok: {self.log.satirlar}")


class CustomerAddTests(_Temel):

    def test_error_reopens_dialog_then_cancel(self):
        sayfa = self._musteri_sayfasi()
        sayfa.service.add.side_effect = [_hata(sqlite3.IntegrityError)]
        dlg = self._sahte_dialog([QDialog.DialogCode.Accepted,
                                  QDialog.DialogCode.Rejected])
        self._calistir(cp, sayfa, "_add", "CustomerDialog", dlg)
        self._mesaj_guvenli()
        self._log_guvenli()
        self.assertEqual(dlg.exec.call_count, 2)
        sayfa._load.assert_not_called()

    def test_retry_success_refreshes_once(self):
        sayfa = self._musteri_sayfasi()
        sayfa.service.add.side_effect = [_hata(), 7]
        dlg = self._sahte_dialog([QDialog.DialogCode.Accepted,
                                  QDialog.DialogCode.Accepted])
        self._calistir(cp, sayfa, "_add", "CustomerDialog", dlg)
        sayfa._load.assert_called_once()
        self.assertEqual(sayfa.service.add.call_count, 2)


class ProductSaveTests(_Temel):

    def test_edit_error_reopens_dialog(self):
        sayfa = self._urun_sayfasi()
        sayfa.service.update.side_effect = [_hata(sqlite3.OperationalError,
                                                  "database is locked")]
        dlg = self._sahte_dialog([QDialog.DialogCode.Accepted,
                                  QDialog.DialogCode.Rejected])
        self._calistir(pp, sayfa, "_edit", "ProductDialog", dlg)
        self._mesaj_guvenli()
        self.assertIn("meşgul", self.kutular["warning"][0][1])
        self.assertEqual(dlg.exec.call_count, 2)
        sayfa._load.assert_not_called()

    def test_add_retry_success(self):
        sayfa = self._urun_sayfasi()
        sayfa.service.add.side_effect = [_hata(), 9]
        dlg = self._sahte_dialog([QDialog.DialogCode.Accepted,
                                  QDialog.DialogCode.Accepted])
        self._calistir(pp, sayfa, "_add", "ProductDialog", dlg)
        sayfa._load.assert_called_once()
        self.assertEqual(sayfa.service.add.call_count, 2)

    def test_product_errors_are_logged(self):
        sayfa = self._urun_sayfasi()
        sayfa.service.update.side_effect = [_hata()]
        dlg = self._sahte_dialog([QDialog.DialogCode.Accepted,
                                  QDialog.DialogCode.Rejected])
        self._calistir(pp, sayfa, "_edit", "ProductDialog", dlg)
        self.assertTrue(any("islem_hatasi" in s for s in self.log.satirlar),
                        "ürün hatası loglanmadı")
        self._log_guvenli()

    def test_duplicate_code_message_preserved(self):
        from services.product_service import DuplicateProductCodeError
        mevcut = Product(id=3, product_code="ABC-1", product_name="Var Olan")
        sayfa = self._urun_sayfasi()
        sayfa.service.add.side_effect = [DuplicateProductCodeError(mevcut)]
        dlg = self._sahte_dialog([QDialog.DialogCode.Accepted,
                                  QDialog.DialogCode.Rejected])
        self._calistir(pp, sayfa, "_add", "ProductDialog", dlg)
        self.assertIn("ABC-1", self.kutular["warning"][0][1])


class DeleteTests(_Temel):

    def test_customer_delete_error_does_not_refresh(self):
        sayfa = self._musteri_sayfasi()
        sayfa.service.delete_many.side_effect = _hata()
        for y in self._kutulari_yakala(cp):
            y.start()
        try:
            cp.CustomersPage._delete(sayfa)
        finally:
            for y in self._kutulari_yakala(cp):
                y.stop()
        self._mesaj_guvenli()
        self._log_guvenli()
        sayfa._load.assert_not_called()
        self.assertEqual(self.kutular["information"], [])

    def test_customer_delete_success_refreshes_once(self):
        sayfa = self._musteri_sayfasi()
        sayfa.service.delete_many.side_effect = None
        for y in self._kutulari_yakala(cp):
            y.start()
        try:
            cp.CustomersPage._delete(sayfa)
        finally:
            for y in self._kutulari_yakala(cp):
                y.stop()
        sayfa._load.assert_called_once()
        self.assertEqual(self.kutular["warning"], [])

    def test_product_delete_error_does_not_refresh(self):
        sayfa = self._urun_sayfasi()
        sayfa.service.delete_many.side_effect = _hata()
        for y in self._kutulari_yakala(pp):
            y.start()
        try:
            pp.ProductsPage._delete(sayfa)
        finally:
            for y in self._kutulari_yakala(pp):
                y.stop()
        self._mesaj_guvenli()
        sayfa._load_filtered.assert_not_called()

    def test_product_delete_success_refreshes_once(self):
        sayfa = self._urun_sayfasi()
        sayfa.service.delete_many.side_effect = None
        for y in self._kutulari_yakala(pp):
            y.start()
        try:
            pp.ProductsPage._delete(sayfa)
        finally:
            for y in self._kutulari_yakala(pp):
                y.stop()
        sayfa._load_filtered.assert_called_once()

    def test_delete_confirmation_rejection_unchanged(self):
        sayfa = self._musteri_sayfasi()
        with mock.patch.object(cp.QMessageBox, "question",
                               return_value=QMessageBox.StandardButton.No):
            cp.CustomersPage._delete(sayfa)
        sayfa.service.delete_many.assert_not_called()
        sayfa._load.assert_not_called()


class RealQtRetryTests(_Temel):
    """GERÇEK dialog örnekleriyle retry: alanlar korunuyor mu?

    `exec()` modal olduğu için yamalanır; yerine gerçek `show()` + değer
    okuma yapılır. Takılmaya karşı güvenlik sayacı vardır: beklenenden çok
    `exec()` çağrılırsa test açıkça düşer.
    """

    GUVENLIK_SINIRI = 5

    def _exec_yamasi(self, dlg, sonuclar, gozlem):
        """`exec()` yerine: dialogu göster, alan değerlerini kaydet, sonucu dön."""
        sonuclar = list(sonuclar)

        def sahte_exec():
            gozlem["cagri"] += 1
            if gozlem["cagri"] > self.GUVENLIK_SINIRI:
                raise AssertionError(
                    "exec() güvenlik sınırını aştı — sonsuz retry döngüsü")
            dlg.show()
            self.app.processEvents()
            gozlem["anlik"].append(gozlem["oku"](dlg))
            gozlem["gecerli"].append(_gecerli_mi(dlg))
            dlg.hide()
            self.app.processEvents()
            return sonuclar[gozlem["cagri"] - 1]

        dlg.exec = sahte_exec
        return dlg

    def test_customer_dialog_keeps_fields_across_retry(self):
        musteri = Customer(id=1, company_name=SAHTE_AD, contact_person="Kişi A",
                           address="Adres A", phone="555", email="a@b.c")
        dlg = cp.CustomerDialog(None, musteri)
        self.addCleanup(dlg.deleteLater)
        # Kullanıcı alanları DEĞİŞTİRİYOR
        dlg.company.setText("YENI-FIRMA")
        dlg.contact.setText("Yeni Kişi")
        dlg.phone.setText("444")
        dlg.email.setText("yeni@x.y")

        gozlem = {"cagri": 0, "anlik": [], "gecerli": [],
                  "oku": lambda d: (d.company.text(), d.contact.text(),
                                    d.phone.text(), d.email.text())}
        self._exec_yamasi(dlg, [QDialog.DialogCode.Accepted,
                                QDialog.DialogCode.Accepted], gozlem)

        sayfa = self._musteri_sayfasi()
        sayfa.service.update.side_effect = [_hata(sqlite3.IntegrityError), None]
        yamalar = self._kutulari_yakala(cp)
        yamalar.append(mock.patch.object(cp, "CustomerDialog",
                                         return_value=dlg))
        for y in yamalar:
            y.start()
        try:
            cp.CustomersPage._edit(sayfa)
        finally:
            for y in yamalar:
                y.stop()

        self.assertEqual(gozlem["cagri"], 2, "aynı dialog yeniden açılmadı")
        self.assertEqual(gozlem["anlik"][0], gozlem["anlik"][1],
                         "ikinci açılışta alan değerleri kayboldu")
        self.assertEqual(gozlem["anlik"][1],
                         ("YENI-FIRMA", "Yeni Kişi", "444", "yeni@x.y"))
        self.assertTrue(all(gozlem["gecerli"]),
                        "dialogun C++ nesnesi silinmiş")
        self.assertEqual(len(self.kutular["warning"]), 1)
        sayfa._load.assert_called_once()
        self._log_guvenli()

    def test_customer_dialog_cancel_after_error(self):
        dlg = cp.CustomerDialog(None, Customer(id=1, company_name=SAHTE_AD))
        self.addCleanup(dlg.deleteLater)
        dlg.company.setText("KORUNAN")
        gozlem = {"cagri": 0, "anlik": [], "gecerli": [],
                  "oku": lambda d: d.company.text()}
        self._exec_yamasi(dlg, [QDialog.DialogCode.Accepted,
                                QDialog.DialogCode.Rejected], gozlem)

        sayfa = self._musteri_sayfasi()
        sayfa.service.update.side_effect = [_hata()]
        yamalar = self._kutulari_yakala(cp)
        yamalar.append(mock.patch.object(cp, "CustomerDialog", return_value=dlg))
        for y in yamalar:
            y.start()
        try:
            cp.CustomersPage._edit(sayfa)
        finally:
            for y in yamalar:
                y.stop()

        self.assertEqual(sayfa.service.update.call_count, 1,
                         "iptalden sonra ikinci servis çağrısı")
        sayfa._load.assert_not_called()
        self.assertEqual(gozlem["anlik"][-1], "KORUNAN")

    def test_product_dialog_keeps_fields_across_retry(self):
        urun = Product(id=1, product_code="T-1", product_name="Test",
                       price=10.0, currency="EUR", stock=3, unit="Adet")
        dlg = pp.ProductDialog(None, urun)
        self.addCleanup(dlg.deleteLater)
        dlg.code.setText("YENI-KOD")
        dlg.name.setText("Yeni Ad")
        dlg.price.setValue(123.45)
        dlg.currency.setCurrentText("USD")

        gozlem = {"cagri": 0, "anlik": [], "gecerli": [],
                  "oku": lambda d: (d.code.text(), d.name.text(),
                                    round(d.price.value(), 2),
                                    d.currency.currentText())}
        self._exec_yamasi(dlg, [QDialog.DialogCode.Accepted,
                                QDialog.DialogCode.Accepted], gozlem)

        sayfa = self._urun_sayfasi()
        sayfa.service.update.side_effect = [
            _hata(sqlite3.OperationalError, "database is locked"), None]
        yamalar = self._kutulari_yakala(pp)
        yamalar.append(mock.patch.object(pp, "ProductDialog", return_value=dlg))
        for y in yamalar:
            y.start()
        try:
            pp.ProductsPage._edit(sayfa)
        finally:
            for y in yamalar:
                y.stop()

        self.assertEqual(gozlem["cagri"], 2)
        self.assertEqual(gozlem["anlik"][0], gozlem["anlik"][1],
                         "ürün alanları ikinci açılışta kayboldu")
        self.assertEqual(gozlem["anlik"][1],
                         ("YENI-KOD", "Yeni Ad", 123.45, "USD"))
        self.assertTrue(all(gozlem["gecerli"]))
        self.assertIn("meşgul", self.kutular["warning"][0][1])
        sayfa._load.assert_called_once()

    def test_product_dialog_cancel_after_error(self):
        dlg = pp.ProductDialog(None, Product(id=1, product_code="T-1",
                                             product_name="Test"))
        self.addCleanup(dlg.deleteLater)
        dlg.code.setText("KALICI-KOD")
        gozlem = {"cagri": 0, "anlik": [], "gecerli": [],
                  "oku": lambda d: d.code.text()}
        self._exec_yamasi(dlg, [QDialog.DialogCode.Accepted,
                                QDialog.DialogCode.Rejected], gozlem)

        sayfa = self._urun_sayfasi()
        sayfa.service.update.side_effect = [_hata()]
        yamalar = self._kutulari_yakala(pp)
        yamalar.append(mock.patch.object(pp, "ProductDialog", return_value=dlg))
        for y in yamalar:
            y.start()
        try:
            pp.ProductsPage._edit(sayfa)
        finally:
            for y in yamalar:
                y.stop()

        self.assertEqual(sayfa.service.update.call_count, 1)
        sayfa._load.assert_not_called()
        self.assertEqual(gozlem["anlik"][-1], "KALICI-KOD")


def _gecerli_mi(nesne) -> bool:
    from shiboken6 import Shiboken
    return Shiboken.isValid(nesne)


if __name__ == "__main__":
    unittest.main()
