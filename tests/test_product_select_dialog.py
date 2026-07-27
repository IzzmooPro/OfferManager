"""O10 — ProductSelectDialog sonuç sınırı, debounce ve sonuç bilgisi.

Ölçüm: 10.096 ürünle dialog açılışı 417,7 ms sürüyordu ve arama kutusuna
yazılan her karakter ayrı bir DB sorgusu + tam tablo doldurma tetikliyordu.
Bu testler sınırı (500), debounce'u (~200 ms) ve bilgi etiketini sabitler.

Servis `get_all/search/count` metotları ProductsPage ve Dashboard tarafından
da kullanılıyor; sıralamanın deterministik hâle gelmesi dışında davranışları
değişmemeli — o da ayrıca test edilir.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest
from unittest import mock

from PySide6.QtWidgets import QApplication

from database.db_manager import get_db
from models.product import Product
from services.product_service import ProductService
from ui.create_offer_page import ProductSelectDialog, _URUN_SATIR_SINIRI


def _app():
    return QApplication.instance() or QApplication([])


class _DialogTemeli(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = _app()
        cls.db = get_db()
        cls.svc = ProductService()

    def setUp(self):
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM products")

    def _urun_ekle(self, adet, onek="URN"):
        with self.db.transaction() as conn:
            conn.executemany(
                "INSERT INTO products (product_code, product_name, price, "
                "currency, stock, unit) VALUES (?, ?, ?, ?, ?, ?)",
                [(f"{onek}-{i:05d}", f"Ürün {i:05d}", 10.0 + i, "EUR", 5, "Adet")
                 for i in range(adet)])

    def _dialog(self):
        dlg = ProductSelectDialog(None)
        self.addCleanup(dlg.deleteLater)
        return dlg


class RowLimitTests(_DialogTemeli):

    def test_initial_load_passes_limit(self):
        self._urun_ekle(10)
        with mock.patch.object(ProductService, "get_all",
                               return_value=[]) as g:
            self._dialog()
        self.assertEqual(g.call_args.kwargs.get("limit"), _URUN_SATIR_SINIRI)

    def test_limit_is_500(self):
        self.assertEqual(_URUN_SATIR_SINIRI, 500)

    def test_more_products_than_cap_shows_only_cap_rows(self):
        self._urun_ekle(620)
        dlg = self._dialog()
        self.assertEqual(dlg.table.rowCount(), _URUN_SATIR_SINIRI)
        self.assertEqual(len(dlg._products), _URUN_SATIR_SINIRI)

    def test_search_also_respects_limit(self):
        self._urun_ekle(620)
        dlg = self._dialog()
        with mock.patch.object(ProductService, "search",
                               return_value=[]) as s:
            dlg._load("Ürün", -1)
        self.assertEqual(s.call_args.kwargs.get("limit"), _URUN_SATIR_SINIRI)

    def test_category_filtered_load_respects_limit(self):
        self._urun_ekle(10)
        dlg = self._dialog()
        with mock.patch.object(ProductService, "get_all",
                               return_value=[]) as g:
            dlg._load("", None)
        self.assertEqual(g.call_args.kwargs.get("limit"), _URUN_SATIR_SINIRI)


class ResultInfoLabelTests(_DialogTemeli):

    def test_label_shown_when_more_than_cap(self):
        self._urun_ekle(620)
        dlg = self._dialog()
        metin = dlg._sonuc_bilgisi.text()
        self.assertTrue(dlg._sonuc_bilgisi.isVisibleTo(dlg))
        self.assertIn("500", metin)
        self.assertIn("620", metin)
        self.assertIn("arama", metin.lower())

    def test_no_misleading_label_when_below_cap(self):
        self._urun_ekle(120)
        dlg = self._dialog()
        self.assertEqual(dlg._sonuc_bilgisi.text(), "")

    def test_no_label_at_exactly_cap(self):
        self._urun_ekle(_URUN_SATIR_SINIRI)
        dlg = self._dialog()
        self.assertEqual(dlg._sonuc_bilgisi.text(), "")

    def test_filtered_label_uses_filtered_total(self):
        self._urun_ekle(620, onek="AAA")
        self._urun_ekle(30, onek="BBB")
        dlg = self._dialog()
        dlg._load("AAA", -1)
        metin = dlg._sonuc_bilgisi.text()
        self.assertIn("500", metin)
        self.assertIn("620", metin)
        self.assertNotIn("650", metin)

    def test_label_wraps_and_has_no_fixed_width(self):
        self._urun_ekle(620)
        dlg = self._dialog()
        self.assertTrue(dlg._sonuc_bilgisi.wordWrap())
        self.assertEqual(dlg._sonuc_bilgisi.minimumWidth(), 0)
        self.assertGreater(dlg._sonuc_bilgisi.maximumWidth(), 10000)


class DebounceTests(_DialogTemeli):

    def test_fast_typing_triggers_single_load(self):
        self._urun_ekle(30)
        dlg = self._dialog()
        with mock.patch.object(dlg, "_load") as yukle:
            for metin in ("a", "ab", "abc", "abcd", "abcde"):
                dlg._search_edit.setText(metin)
            self.assertEqual(yukle.call_count, 0, "debounce beklemeden sorgu")
            self._zamanlayiciyi_bekle(dlg)
        self.assertEqual(yukle.call_count, 1, "tek yükleme olmalı")

    def _zamanlayiciyi_bekle(self, dlg, ms=600):
        from PySide6.QtCore import QDeadlineTimer, QCoreApplication
        son = QDeadlineTimer(ms)
        while not son.hasExpired() and dlg._arama_timer.isActive():
            QCoreApplication.processEvents()
        QCoreApplication.processEvents()

    def test_debounce_interval_is_about_200ms(self):
        self._urun_ekle(5)
        dlg = self._dialog()
        self.assertTrue(dlg._arama_timer.isSingleShot())
        self.assertGreaterEqual(dlg._arama_timer.interval(), 150)
        self.assertLessEqual(dlg._arama_timer.interval(), 400)

    def test_return_applies_search_immediately(self):
        self._urun_ekle(30)
        dlg = self._dialog()
        with mock.patch.object(dlg, "_load") as yukle:
            dlg._search_edit.setText("abc")
            self.assertEqual(yukle.call_count, 0)
            dlg._search_edit.returnPressed.emit()
            self.assertEqual(yukle.call_count, 1, "Enter anında uygulamadı")
        self.assertFalse(dlg._arama_timer.isActive(), "timer durdurulmadı")

    def test_category_change_cancels_timer_and_loads_once(self):
        self._urun_ekle(30)
        dlg = self._dialog()
        with mock.patch.object(dlg, "_load") as yukle:
            dlg._search_edit.setText("abc")          # timer başlar
            dlg._cat_filter.setCurrentIndex(1)       # kategori değişti
            self.assertFalse(dlg._arama_timer.isActive())
            self.assertEqual(yukle.call_count, 1)
            self.assertEqual(yukle.call_args[0][0], "abc",
                             "kategori değişiminde arama metni kaybedildi")

    def test_closed_dialog_does_not_load_later(self):
        self._urun_ekle(30)
        dlg = self._dialog()
        with mock.patch.object(dlg, "_load") as yukle:
            dlg._search_edit.setText("abc")
            dlg.reject()
            self.assertFalse(dlg._arama_timer.isActive(),
                             "kapanışta timer durdurulmadı")
            dlg._aramayi_uygula()                    # gecikmiş tetikleme
            yukle.assert_not_called()

    def test_selection_with_pending_filter_does_not_use_stale_rows(self):
        self._urun_ekle(30)
        dlg = self._dialog()
        eski = list(dlg._products)
        dlg.table.selectRow(0)
        dlg._search_edit.setText("Ürün 00025")       # timer bekliyor
        dlg._select()
        self.assertEqual(dlg.selected_products, [],
                         "bekleyen filtre varken eski satır seçildi")
        self.assertFalse(dlg._arama_timer.isActive())
        self.assertNotEqual(len(dlg._products), len(eski),
                            "bekleyen filtre uygulanmadı")


class SelectionContractTests(_DialogTemeli):

    def test_selected_product_fields_are_unchanged(self):
        self.svc.add(Product(product_code="ABC-1", product_name="Test Ürün",
                             price=123.45, currency="USD", stock=7,
                             unit="Kutu", cost_price=99.0,
                             description="Açıklama"))
        dlg = self._dialog()
        dlg.table.selectRow(0)
        dlg._select()
        self.assertEqual(len(dlg.selected_products), 1)
        p = dlg.selected_products[0]
        self.assertEqual(p.product_code, "ABC-1")
        self.assertEqual(p.product_name, "Test Ürün")
        self.assertEqual(p.price, 123.45)
        self.assertEqual(p.currency, "USD")
        self.assertEqual(p.cost_price, 99.0)
        self.assertEqual(p.stock, 7)
        self.assertEqual(p.unit, "Kutu")

    def test_row_index_matches_products_list(self):
        self._urun_ekle(20)
        dlg = self._dialog()
        for satir in (0, 5, 19):
            self.assertEqual(dlg.table.item(satir, 0).text(),
                             dlg._products[satir].product_code)


class DeterministicOrderTests(_DialogTemeli):
    """Eş adlı ürünlerde LIMIT altında sıra sabit olmalı."""

    def _ayni_isimli_ekle(self, adet=40):
        with self.db.transaction() as conn:
            conn.executemany(
                "INSERT INTO products (product_code, product_name, price, "
                "currency, stock, unit) VALUES (?, ?, ?, ?, ?, ?)",
                [(f"AYNI-{i:04d}", "Aynı Ürün", 1.0, "EUR", 0, "Adet")
                 for i in range(adet)])

    def test_get_all_order_is_stable_under_limit(self):
        self._ayni_isimli_ekle()
        ilk = [p.product_code for p in self.svc.get_all(-1, limit=10)]
        for _ in range(4):
            self.assertEqual(
                [p.product_code for p in self.svc.get_all(-1, limit=10)], ilk)
        self.assertEqual(ilk, sorted(ilk), "id sırası korunmadı")

    def test_search_order_is_stable_under_limit(self):
        self._ayni_isimli_ekle()
        ilk = [p.product_code for p in self.svc.search("Aynı", -1, limit=10)]
        for _ in range(4):
            self.assertEqual(
                [p.product_code for p in self.svc.search("Aynı", -1, limit=10)],
                ilk)


class CapBoundaryTests(_DialogTemeli):
    """Tam 499 / 500 / 501 sonuç sınırları."""

    def test_499_total_shows_no_label(self):
        self._urun_ekle(499)
        dlg = self._dialog()
        self.assertEqual(dlg.table.rowCount(), 499)
        self.assertEqual(dlg._sonuc_bilgisi.text(), "")

    def test_exactly_500_total_shows_no_label(self):
        self._urun_ekle(500)
        dlg = self._dialog()
        self.assertEqual(dlg.table.rowCount(), 500)
        self.assertEqual(dlg._sonuc_bilgisi.text(), "",
                         "sınıra tam oturan listede yanıltıcı uyarı")

    def test_501_total_shows_500_of_501(self):
        self._urun_ekle(501)
        dlg = self._dialog()
        self.assertEqual(dlg.table.rowCount(), 500)
        metin = dlg._sonuc_bilgisi.text()
        self.assertIn("500", metin)
        self.assertIn("501", metin)


class FilterAgreementTests(_DialogTemeli):
    """count() ile search()/get_all() aynı kayıt kümesini görmeli."""

    def _kategori_olustur(self, ad):
        with self.db.transaction() as conn:
            cur = conn.execute(
                "INSERT INTO product_categories (name) VALUES (?)", (ad,))
            return cur.lastrowid

    def _kategorili_ekle(self, adet, kategori_id, onek):
        with self.db.transaction() as conn:
            conn.executemany(
                "INSERT INTO products (product_code, product_name, price, "
                "currency, stock, unit, category_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                [(f"{onek}-{i:04d}", f"{onek} Ürün {i:04d}", 1.0, "EUR", 0,
                  "Adet", kategori_id) for i in range(adet)])

    def setUp(self):
        super().setUp()
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM product_categories")
        self.kat_a = self._kategori_olustur("KatA")
        self.kat_b = self._kategori_olustur("KatB")
        self._kategorili_ekle(12, self.kat_a, "AAA")
        self._kategorili_ekle(7, self.kat_b, "BBB")
        self._urun_ekle(5, onek="ZZZ")          # kategorisiz

    def test_empty_search_all_categories(self):
        self.assertEqual(self.svc.count(-1, ""), 24)
        self.assertEqual(len(self.svc.get_all(-1)), 24)

    def test_text_search_all_categories(self):
        self.assertEqual(self.svc.count(-1, "AAA"), 12)
        self.assertEqual(len(self.svc.search("AAA", -1)), 12)

    def test_category_only(self):
        self.assertEqual(self.svc.count(self.kat_b, ""), 7)
        self.assertEqual(len(self.svc.get_all(self.kat_b)), 7)
        self.assertEqual(self.svc.count(None, ""), 5)      # kategorisiz
        self.assertEqual(len(self.svc.get_all(None)), 5)

    def test_category_plus_text(self):
        self.assertEqual(self.svc.count(self.kat_a, "AAA"), 12)
        self.assertEqual(len(self.svc.search("AAA", self.kat_a)), 12)
        self.assertEqual(self.svc.count(self.kat_b, "AAA"), 0,
                         "kategori+metin koşulları uyuşmuyor")
        self.assertEqual(len(self.svc.search("AAA", self.kat_b)), 0)

    def test_dialog_label_uses_same_filter_as_query(self):
        self._kategorili_ekle(600, self.kat_a, "CCC")
        dlg = self._dialog()
        dlg._load("CCC", self.kat_a)
        self.assertEqual(dlg.table.rowCount(), _URUN_SATIR_SINIRI)
        self.assertIn("600", dlg._sonuc_bilgisi.text())


class PendingFilterSelectionTests(_DialogTemeli):
    """Debounce beklerken hiçbir seçim yolu eski satırı kabul etmemeli."""

    def _bekleyen_filtreli_dialog(self):
        self._urun_ekle(30)
        dlg = self._dialog()
        dlg.table.selectRow(0)
        dlg._search_edit.setText("Ürün 00025")     # timer bekliyor
        self.assertTrue(dlg._arama_timer.isActive())
        return dlg

    def test_double_click_path_is_safe(self):
        dlg = self._bekleyen_filtreli_dialog()
        dlg.table.doubleClicked.emit(dlg.table.model().index(0, 0))
        self.assertEqual(dlg.selected_products, [])
        self.assertFalse(dlg._arama_timer.isActive())

    def test_add_button_path_is_safe(self):
        dlg = self._bekleyen_filtreli_dialog()
        dlg._select()
        self.assertEqual(dlg.selected_products, [])

    def test_return_path_applies_filter_without_selecting(self):
        dlg = self._bekleyen_filtreli_dialog()
        dlg._search_edit.returnPressed.emit()
        self.assertFalse(dlg._arama_timer.isActive())
        self.assertEqual(dlg.selected_products, [])
        self.assertEqual(dlg.table.rowCount(), len(dlg._products))

    def test_selecting_after_filter_applied_accepts_normally(self):
        dlg = self._bekleyen_filtreli_dialog()
        dlg._aramayi_hemen_uygula()                # filtre uygulandı
        self.assertGreater(dlg.table.rowCount(), 0)
        dlg.table.selectRow(0)
        with mock.patch.object(dlg, "accept") as kabul:
            dlg._select()
        kabul.assert_called_once()
        self.assertEqual(len(dlg.selected_products), 1)
        p = dlg.selected_products[0]
        self.assertEqual(p.product_code, dlg._products[0].product_code)
        self.assertEqual(p.price, dlg._products[0].price)
        self.assertEqual(p.currency, dlg._products[0].currency)

    def test_category_change_does_not_leave_a_second_query(self):
        self._urun_ekle(30)
        dlg = self._dialog()
        with mock.patch.object(dlg, "_load") as yukle:
            dlg._search_edit.setText("abc")
            dlg._cat_filter.setCurrentIndex(1)
            self.assertEqual(yukle.call_count, 1)
            # eski timer sonradan İKİNCİ sorgu üretmemeli
            from PySide6.QtCore import QCoreApplication, QDeadlineTimer
            son = QDeadlineTimer(500)
            while not son.hasExpired():
                QCoreApplication.processEvents()
            self.assertEqual(yukle.call_count, 1, "gecikmiş ikinci sorgu")


class SharedServiceContractTests(_DialogTemeli):
    """ProductsPage / Dashboard davranışı bozulmamalı."""

    def test_get_all_without_limit_returns_everything(self):
        self._urun_ekle(30)
        self.assertEqual(len(self.svc.get_all(-1)), 30)

    def test_get_all_sorted_by_name(self):
        with self.db.transaction() as conn:
            conn.executemany(
                "INSERT INTO products (product_code, product_name, price, "
                "currency, stock, unit) VALUES (?, ?, ?, ?, ?, ?)",
                [("C1", "Cc", 1.0, "EUR", 0, "Adet"),
                 ("A1", "Aa", 1.0, "EUR", 0, "Adet"),
                 ("B1", "Bb", 1.0, "EUR", 0, "Adet")])
        self.assertEqual([p.product_name for p in self.svc.get_all(-1)],
                         ["Aa", "Bb", "Cc"])

    def test_search_matches_code_name_and_description(self):
        self.svc.add(Product(product_code="XYZ-9", product_name="Kablo",
                             price=1.0, currency="EUR", stock=0, unit="Adet",
                             description="özel açıklama"))
        for anahtar in ("XYZ", "Kablo", "özel"):
            with self.subTest(anahtar=anahtar):
                self.assertEqual(len(self.svc.search(anahtar, -1)), 1)

    def test_count_matches_search_filter(self):
        self._urun_ekle(620, onek="AAA")
        self._urun_ekle(30, onek="BBB")
        self.assertEqual(self.svc.count(-1, "AAA"), 620)
        self.assertEqual(len(self.svc.search("AAA", -1)), 620)
        self.assertEqual(self.svc.count(-1, ""), 650)


if __name__ == "__main__":
    unittest.main()
