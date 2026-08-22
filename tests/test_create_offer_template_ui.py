"""Teklif ekranı — 'Şablondan Yükle' arayüz regresyon testleri.

Şablon yükleme mantığı (_load_from_template) yazılmıştı ancak hiçbir butona
bağlı değildi; kullanıcı dashboard'da şablon kaydedip yeni teklifte
yükleyemiyordu. Bu testler butonun VARLIĞINI ve bağlı olduğunu, ayrıca
şablon yokken / seçim iptal edilince / tablo doluyken beklenen davranışı
korur.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest
from unittest import mock

from PySide6.QtWidgets import (
    QApplication, QInputDialog, QMessageBox, QPushButton,
)

from database.db_manager import get_db
from models.offer_item import OfferItem
from services.template_service import TemplateService
from ui.create_offer_page import CreateOfferPage

TEMPLATE_BUTTON_TEXT = "Şablondan Yükle"


class TemplateButtonTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.db = get_db()

    def setUp(self):
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM offer_templates")
        self.page = CreateOfferPage()

    def tearDown(self):
        self.page.deleteLater()
        QApplication.processEvents()

    # ── yardımcılar ──────────────────────────────────────────────────────

    def _template_button(self) -> QPushButton:
        matches = [b for b in self.page.findChildren(QPushButton)
                   if b.text() == TEMPLATE_BUTTON_TEXT]
        self.assertEqual(len(matches), 1,
                         f"'{TEMPLATE_BUTTON_TEXT}' butonu bulunamadı")
        return matches[0]

    def _save_template(self, name="Standart Paket", currency="TL"):
        items = [
            OfferItem(product_code="SBL-1", product_name="Şablon Ürün 1",
                      quantity=2, unit="Adet", delivery_time="1 Hafta",
                      unit_price=150.0, total_price=300.0),
            OfferItem(product_code="SBL-2", product_name="Şablon Ürün 2",
                      quantity=1, unit="Kg", delivery_time="Stoktan",
                      unit_price=75.0, total_price=75.0),
        ]
        TemplateService().create_from_offer(name, currency, items)
        return items

    @staticmethod
    def _accept_first_item(*args, **kwargs):
        """QInputDialog.getItem yerine: ilk şablonu seçip onayla."""
        return args[3][0], True

    # ── testler ──────────────────────────────────────────────────────────

    def test_button_is_visible_and_matches_button_style(self):
        button = self._template_button()
        self.assertEqual(button.objectName(), "secondary",
                         "buton komşularıyla aynı tema üslubunu kullanmalı")
        self.assertGreaterEqual(button.minimumHeight(), 38)
        self.assertTrue(button.toolTip(), "buton için ipucu metni yok")
        # Adım 2 (Ürünler) sayfasında, ürün tablosuyla aynı ekranda olmalı
        step2 = self.page.stack.widget(1)
        self.assertIn(button, step2.findChildren(QPushButton))

    def test_click_without_templates_shows_clear_message(self):
        with mock.patch.object(QMessageBox, "information") as info:
            self._template_button().click()
        self.assertEqual(info.call_count, 1, "buton _load_from_template'e bağlı değil")
        title = info.call_args.args[1]
        self.assertEqual(title, "Şablon Yok")
        self.assertEqual(self.page.prod_table.rowCount(), 0)

    def test_cancelled_selection_leaves_offer_untouched(self):
        self._save_template()
        self.page._add_row(code="MEVCUT", name="Mevcut Ürün", qty=3,
                           price=500.0, currency="EUR")
        before = self.page.prod_table.rowCount()

        with mock.patch.object(QInputDialog, "getItem",
                               staticmethod(lambda *a, **k: ("", False))):
            self._template_button().click()

        self.assertEqual(self.page.prod_table.rowCount(), before)
        self.assertEqual(self.page.prod_table.item(0, 0).text(), "MEVCUT")
        self.assertEqual(self.page.current_currency, "EUR")

    def test_selected_template_loads_items_into_empty_table(self):
        items = self._save_template()

        with mock.patch.object(QInputDialog, "getItem",
                               staticmethod(self._accept_first_item)):
            self._template_button().click()

        table = self.page.prod_table
        self.assertEqual(table.rowCount(), len(items))
        self.assertEqual([table.item(r, 0).text() for r in range(table.rowCount())],
                         [i.product_code for i in items])
        self.assertEqual(table.item(1, 1).text(), "Şablon Ürün 2")
        self.assertEqual(self.page.current_currency, "TL")

    def test_non_empty_table_requires_confirmation_before_loading(self):
        self._save_template()
        self.page._add_row(code="MEVCUT", name="Mevcut Ürün", qty=1,
                           price=100.0, currency="TL")
        exec_calls = []

        with mock.patch.object(QInputDialog, "getItem",
                               staticmethod(self._accept_first_item)), \
             mock.patch.object(QMessageBox, "exec",
                               lambda box: exec_calls.append(box) or 0):
            self._template_button().click()

        self.assertEqual(len(exec_calls), 1, "dolu tabloda onay sorulmadı")
        box = exec_calls[0]
        labels = {b.text() for b in box.buttons()}
        self.assertIn("Listeyi Temizle ve Yükle", labels)
        self.assertIn("Mevcut Listeye Ekle", labels)
        for button in box.buttons():
            if button.text() in {"Listeyi Temizle ve Yükle", "Mevcut Listeye Ekle"}:
                required = button.fontMetrics().horizontalAdvance(button.text()) + 32
                self.assertGreaterEqual(
                    button.minimumWidth(), required,
                    f"Onay düğmesi metni kırpılabilir: {button.text()}",
                )
                self.assertEqual(
                    button.maximumWidth(), button.minimumWidth(),
                    f"QMessageBox düğme genişliğini yeniden daraltabilir: {button.text()}",
                )
        box.show()
        QApplication.processEvents()
        for button in box.buttons():
            if button.text() in {"Listeyi Temizle ve Yükle", "Mevcut Listeye Ekle"}:
                required = button.fontMetrics().horizontalAdvance(button.text()) + 32
                self.assertGreaterEqual(button.width(), required)
        box.close()
        # Onay verilmediği (hiçbir düğmeye basılmadığı) sürece tablo korunur
        self.assertEqual(self.page.prod_table.rowCount(), 1)
        self.assertEqual(self.page.prod_table.item(0, 0).text(), "MEVCUT")


if __name__ == "__main__":
    unittest.main(verbosity=2)
