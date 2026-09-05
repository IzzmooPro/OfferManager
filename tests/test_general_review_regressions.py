"""2026-09-05 genel incelemede bulunan veri güvenliği regresyonları."""
import csv
import math
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from core.offer_files import validate_offer_number
from database.db_manager import get_db
from models.offer import Offer
from models.offer_item import OfferItem
from services.export_service import export_csv, export_excel
from services.offer_service import OfferService, remaining_days
from services.report_service import ReportService
from ui.utils.excel_import import _validate_offer_rows


def _offer(*, offer_no="", currency="EUR", quantity=1, unit_price=100,
           total_price=100, total_amount=100):
    return Offer(
        offer_no=offer_no,
        company_name="Test Firma",
        date=date.today().isoformat(),
        currency=currency,
        total_amount=total_amount,
        items=[OfferItem(
            product_code="P-1", product_name="Test Ürün",
            quantity=quantity, unit_price=unit_price, total_price=total_price,
        )],
    )


class GeneralReviewRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = get_db()
        cls.offers = OfferService()

    def setUp(self):
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM offer_items")
            conn.execute("DELETE FROM offers")
            conn.execute("DELETE FROM offer_counter")

    def test_import_rejects_path_like_offer_number_without_partial_save(self):
        with self.assertRaises(ValueError):
            self.offers.save(_offer(offer_no="../outside"), keep_offer_no=True)
        self.assertEqual(self.db.fetchone("SELECT COUNT(*) AS n FROM offers")["n"], 0)
        self.assertIsNone(self.db.fetchone("SELECT 1 FROM offer_counter WHERE year=0"))

    def test_offer_number_rejects_windows_path_and_device_forms(self):
        for value in ("..\\outside", "C:\\outside", "\\\\server\\share", "CON", "LPT1.txt", "SNS-1."):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    validate_offer_number(value)

    def test_delete_legacy_path_like_offer_number_never_unlinks_outside_archive(self):
        with self.db.transaction() as conn:
            cur = conn.execute(
                "INSERT INTO offers (offer_no, date, currency, total_amount) VALUES (?,?,?,?)",
                ("../outside", "2026-09-05", "EUR", 0),
            )
        with mock.patch.object(Path, "unlink", autospec=True) as unlink:
            self.offers.delete(cur.lastrowid)
        unlink.assert_not_called()

    def test_offer_item_total_must_match_quantity_times_unit_price(self):
        with self.assertRaises(ValueError):
            self.offers.save(_offer(quantity=2, unit_price=100, total_price=1,
                                    total_amount=1))
        self.assertEqual(self.db.fetchone("SELECT COUNT(*) AS n FROM offers")["n"], 0)

    def test_non_finite_offer_numbers_are_rejected(self):
        for value in (math.nan, math.inf, -math.inf):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    self.offers.save(_offer(total_price=value, total_amount=value))

    def test_oversized_validity_is_unparseable_not_an_exception(self):
        offer = _offer()
        offer.validity = "999999999 Gün"
        self.assertIsNone(remaining_days(offer))

    def test_offer_import_rejects_explicit_zero_and_invalid_quantity(self):
        for quantity in (0, "0", "0,0", -1, "bozuk"):
            with self.subTest(quantity=quantity):
                valid, duplicates, invalid = _validate_offer_rows([{
                    "Teklif No": "IMP-001", "Firma Adı": "Test Firma",
                    "Ürün Adı": "Test Ürün", "Miktar": quantity,
                    "Birim Fiyat": 100,
                }])
                self.assertEqual(valid, [])
                self.assertEqual(duplicates, [])
                self.assertTrue(invalid)

    def test_offer_import_rejects_the_whole_offer_after_one_invalid_item(self):
        valid, duplicates, invalid = _validate_offer_rows([
            {"Teklif No": "IMP-001", "Firma Adı": "Test Firma",
             "Ürün Adı": "Bozuk", "Miktar": 0, "Birim Fiyat": 100},
            {"Teklif No": "IMP-001", "Firma Adı": "Test Firma",
             "Ürün Adı": "Geçerli", "Miktar": 2, "Birim Fiyat": 100},
        ])
        self.assertEqual(valid, [])
        self.assertEqual(duplicates, [])
        self.assertTrue(invalid)

    def test_offer_import_keeps_blank_quantity_default_of_one(self):
        valid, duplicates, invalid = _validate_offer_rows([{
            "Teklif No": "IMP-001", "Firma Adı": "Test Firma",
            "Ürün Adı": "Test Ürün", "Miktar": "", "Birim Fiyat": 100,
        }])
        self.assertEqual(duplicates, [])
        self.assertEqual(invalid, [])
        self.assertEqual(valid[0]["items"][0]["quantity"], 1)

    def test_exports_keep_formula_like_text_literal(self):
        offer = _offer()
        offer.company_name = "=1+1"
        with tempfile.TemporaryDirectory() as temp_dir:
            xlsx = Path(temp_dir) / "offers.xlsx"
            csv_path = Path(temp_dir) / "offers.csv"
            export_excel([offer], str(xlsx))
            export_csv([offer], str(csv_path))

            from openpyxl import load_workbook
            cell = load_workbook(xlsx, data_only=False).active["B2"]
            self.assertNotEqual(cell.data_type, "f")
            with csv_path.open(encoding="utf-8-sig", newline="") as handle:
                csv_row = list(csv.reader(handle, delimiter=";"))[1]
            self.assertNotEqual(csv_row[1], "=1+1")

    def test_product_ranking_separates_currency(self):
        self.offers.save(_offer(offer_no="EUR-001", currency="EUR"), keep_offer_no=True)
        self.offers.save(_offer(offer_no="USD-001", currency="USD"), keep_offer_no=True)
        rows = ReportService().product_ranking()
        self.assertEqual({row["currency"] for row in rows}, {"EUR", "USD"})
        self.assertEqual({row["total_revenue"] for row in rows}, {100})


if __name__ == "__main__":
    unittest.main(verbosity=2)
