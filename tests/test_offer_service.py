"""OfferService birim testleri."""
import threading
import unittest
from datetime import date
from pathlib import Path

from core.app_paths import PDF_DIR
from database.db_manager import get_db
from models.offer import Offer
from models.offer_item import OfferItem
from services.offer_service import OfferService


def _valid_offer(currency="TL", amount=90.0):
    return Offer(
        company_name="Test Firma",
        date=date.today().strftime("%d.%m.%Y"),
        currency=currency,
        total_amount=amount,
        discount_amount=10.0,
        discount_type="percent",
        discount_value=10.0,
        items=[OfferItem(
            product_name="Test Ürün",
            quantity=1,
            unit_price=100.0,
            total_price=100.0,
        )],
    )


class TestOfferService(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = get_db()
        cls.svc = OfferService()
        PDF_DIR.mkdir(parents=True, exist_ok=True)

    @classmethod
    def tearDownClass(cls):
        pass

    def setUp(self):
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM offer_items")
            conn.execute("DELETE FROM offers")
            conn.execute("DELETE FROM offer_counter")

    # ── save — başarılı ─────────────────────────────────────────────────

    def test_save_returns_id(self):
        oid = self.svc.save(_valid_offer())
        self.assertIsInstance(oid, int)
        self.assertGreater(oid, 0)

    def test_save_generates_offer_no(self):
        oid = self.svc.save(_valid_offer())
        offer = self.svc.get_by_id(oid)
        self.assertTrue(offer.offer_no)
        self.assertIn("-", offer.offer_no)

    def test_save_stores_all_fields(self):
        o = _valid_offer()
        o.company_name = "Kayıt Testi"
        o.contact_person = "Ali"
        o.customer_phone = "0555"
        o.customer_email = "ali@test.com"
        o.validity = "10 Gün"
        o.payment_term = "Peşin"
        oid = self.svc.save(o)
        stored = self.svc.get_by_id(oid)
        self.assertEqual(stored.company_name, "Kayıt Testi")
        self.assertEqual(stored.contact_person, "Ali")
        self.assertEqual(stored.customer_phone, "0555")
        self.assertEqual(stored.customer_email, "ali@test.com")
        self.assertEqual(stored.discount_type, "percent")
        self.assertAlmostEqual(stored.discount_value, 10.0)

    def test_save_persists_items(self):
        o = _valid_offer()
        o.items = [
            OfferItem(product_name="A", quantity=2, unit_price=50, total_price=100),
            OfferItem(product_name="B", quantity=1, unit_price=50, total_price=50),
        ]
        o.total_amount = 135.0
        o.discount_amount = 15.0
        o.discount_value = 10.0
        oid = self.svc.save(o)
        stored = self.svc.get_by_id(oid)
        self.assertEqual(len(stored.items), 2)
        self.assertEqual(stored.items[0].product_name, "A")
        self.assertEqual(stored.items[1].product_name, "B")

    def test_save_converts_date_to_iso(self):
        oid = self.svc.save(_valid_offer())
        stored = self.svc.get_by_id(oid)
        self.assertEqual(stored.date, date.today().isoformat())

    # ── save — doğrulama hataları ────────────────────────────────────────

    def test_save_no_customer_info_raises(self):
        o = _valid_offer()
        o.company_name = ""
        o.customer_id = None
        with self.assertRaises(ValueError):
            self.svc.save(o)

    def test_save_empty_items_raises(self):
        o = Offer(company_name="Boş", date=date.today().isoformat())
        with self.assertRaises(ValueError):
            self.svc.save(o)

    def test_save_zero_quantity_raises(self):
        o = _valid_offer()
        o.items[0].quantity = 0
        with self.assertRaises(ValueError):
            self.svc.save(o)

    def test_save_negative_quantity_raises(self):
        o = _valid_offer()
        o.items[0].quantity = -1
        with self.assertRaises(ValueError):
            self.svc.save(o)

    def test_save_negative_price_raises(self):
        o = _valid_offer()
        o.items[0].unit_price = -10
        with self.assertRaises(ValueError):
            self.svc.save(o)

    def test_save_discount_exceeds_subtotal_raises(self):
        o = _valid_offer()
        o.discount_type = "amount"
        o.discount_value = 999
        o.discount_amount = 999
        o.total_amount = -899
        with self.assertRaises(ValueError):
            self.svc.save(o)

    def test_save_total_mismatch_raises(self):
        o = _valid_offer()
        o.total_amount = 12345.0
        with self.assertRaises(ValueError):
            self.svc.save(o)

    # ── generate_and_commit_offer_no ─────────────────────────────────────

    def test_offer_numbers_are_sequential(self):
        id1 = self.svc.save(_valid_offer())
        id2 = self.svc.save(_valid_offer())
        o1 = self.svc.get_by_id(id1)
        o2 = self.svc.get_by_id(id2)
        num1 = int(o1.offer_no.split("-")[-1])
        num2 = int(o2.offer_no.split("-")[-1])
        self.assertEqual(num2, num1 + 1)

    def test_concurrent_saves_no_duplicate_numbers(self):
        results = []
        errors = []

        def save_one():
            try:
                oid = self.svc.save(_valid_offer())
                results.append(oid)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=save_one) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        offer_nos = set()
        for oid in results:
            o = self.svc.get_by_id(oid)
            if o:
                offer_nos.add(o.offer_no)
        self.assertEqual(len(offer_nos), len(results))

    # ── get_all / get_recent ─────────────────────────────────────────────

    def test_get_all_returns_list(self):
        self.svc.save(_valid_offer())
        self.svc.save(_valid_offer())
        result = self.svc.get_all()
        self.assertEqual(len(result), 2)

    def test_get_recent_limits(self):
        for _ in range(5):
            self.svc.save(_valid_offer())
        result = self.svc.get_recent(limit=3)
        self.assertEqual(len(result), 3)

    # ── get_by_id ────────────────────────────────────────────────────────

    def test_get_by_id_nonexistent(self):
        self.assertIsNone(self.svc.get_by_id(999999))

    # ── update_status ────────────────────────────────────────────────────

    def test_update_status(self):
        oid = self.svc.save(_valid_offer())
        self.svc.update_status(oid, "Onaylandı")
        updated = self.svc.get_by_id(oid)
        self.assertEqual(updated.status, "Onaylandı")

    def test_update_status_to_cancelled(self):
        oid = self.svc.save(_valid_offer())
        self.svc.update_status(oid, "İptal")
        updated = self.svc.get_by_id(oid)
        self.assertEqual(updated.status, "İptal")

    # ── delete ───────────────────────────────────────────────────────────

    def test_delete_removes_offer_and_items(self):
        oid = self.svc.save(_valid_offer())
        self.svc.delete(oid)
        self.assertIsNone(self.svc.get_by_id(oid))

    def test_delete_removes_pdf_file(self):
        oid = self.svc.save(_valid_offer())
        offer = self.svc.get_by_id(oid)
        pdf_path = PDF_DIR / f"{offer.offer_no}.pdf"
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        pdf_path.write_text("dummy pdf")
        self.svc.delete(oid)
        self.assertFalse(pdf_path.exists())

    # ── get_filtered ─────────────────────────────────────────────────────

    def test_get_filtered_by_keyword(self):
        o = _valid_offer()
        o.company_name = "Sensoryum Teknik"
        self.svc.save(o)
        self.svc.save(_valid_offer())
        result = self.svc.get_filtered(keyword="Sensoryum")
        self.assertEqual(len(result), 1)

    def test_get_filtered_by_status(self):
        oid = self.svc.save(_valid_offer())
        self.svc.update_status(oid, "Onaylandı")
        self.svc.save(_valid_offer())
        result = self.svc.get_filtered(status="Onaylandı")
        self.assertEqual(len(result), 1)

    def test_get_filtered_by_currency(self):
        self.svc.save(_valid_offer("TL"))
        self.svc.save(_valid_offer("EUR"))
        result = self.svc.get_filtered(currency="EUR")
        self.assertEqual(len(result), 1)

    def test_get_filtered_by_amount_range(self):
        self.svc.save(_valid_offer(amount=90))
        o2 = _valid_offer(amount=450)
        o2.items = [OfferItem(product_name="X", quantity=1, unit_price=500, total_price=500)]
        o2.discount_amount = 50
        o2.discount_value = 10
        self.svc.save(o2)
        result = self.svc.get_filtered(amount_min=100, amount_max=500)
        self.assertEqual(len(result), 1)

    def test_get_filtered_no_filters(self):
        self.svc.save(_valid_offer())
        self.svc.save(_valid_offer())
        result = self.svc.get_filtered()
        self.assertEqual(len(result), 2)

    # ── get_revenue_summary ──────────────────────────────────────────────

    def test_revenue_excludes_cancelled(self):
        oid = self.svc.save(_valid_offer("TL", 90))
        self.svc.update_status(oid, "İptal")
        self.svc.save(_valid_offer("TL", 90))
        summary = self.svc.get_revenue_summary()
        self.assertAlmostEqual(summary["monthly"].get("TL", 0), 90.0)

    def test_revenue_separates_currencies(self):
        self.svc.save(_valid_offer("TL", 90))
        self.svc.save(_valid_offer("EUR", 90))
        summary = self.svc.get_revenue_summary()
        self.assertIn("TL", summary["monthly"])
        self.assertIn("EUR", summary["monthly"])

    # ── get_status_counts ────────────────────────────────────────────────

    def test_status_counts(self):
        oid1 = self.svc.save(_valid_offer())
        oid2 = self.svc.save(_valid_offer())
        self.svc.update_status(oid1, "Onaylandı")
        self.svc.update_status(oid2, "İptal")
        self.svc.save(_valid_offer())
        counts = self.svc.get_status_counts()
        self.assertEqual(counts["Onaylandı"], 1)
        self.assertEqual(counts["İptal"], 1)
        self.assertEqual(counts["Beklemede"], 1)

    # ── count ────────────────────────────────────────────────────────────

    def test_count(self):
        self.assertEqual(self.svc.count(), 0)
        self.svc.save(_valid_offer())
        self.assertEqual(self.svc.count(), 1)

    # ── get_by_customer ──────────────────────────────────────────────────

    def test_get_by_customer(self):
        from services.customer_service import CustomerService
        from models.customer import Customer
        csvc = CustomerService()
        cid = csvc.add(Customer(company_name="Müşteri A"))
        o = _valid_offer()
        o.customer_id = cid
        o.company_name = "Müşteri A"
        self.svc.save(o)
        self.svc.save(_valid_offer())
        result = self.svc.get_by_customer(cid)
        self.assertEqual(len(result), 1)


class TestAutoCancelExpired(unittest.TestCase):
    """Geçerlilik süresi dolan tekliflerin otomatik İptal edilmesi."""

    @classmethod
    def setUpClass(cls):
        cls.db = get_db()
        cls.svc = OfferService()

    def setUp(self):
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM offer_items")
            conn.execute("DELETE FROM offers")
            conn.execute("DELETE FROM offer_counter")

    def _offer_with_validity(self, days_ago: int, validity: str,
                             status: str = "Beklemede") -> int:
        from datetime import timedelta
        o = _valid_offer()
        o.date = (date.today() - timedelta(days=days_ago)).strftime("%d.%m.%Y")
        o.validity = validity
        o.status = status
        return self.svc.save(o)

    def test_expired_pending_becomes_cancelled(self):
        oid = self._offer_with_validity(days_ago=30, validity="10 Gün")
        cancelled = self.svc.auto_cancel_expired()
        self.assertEqual(len(cancelled), 1)
        self.assertEqual(self.svc.get_by_id(oid).status, "İptal")

    def test_valid_pending_untouched(self):
        oid = self._offer_with_validity(days_ago=5, validity="30 Gün")
        cancelled = self.svc.auto_cancel_expired()
        self.assertEqual(cancelled, [])
        self.assertEqual(self.svc.get_by_id(oid).status, "Beklemede")

    def test_expired_approved_untouched(self):
        oid = self._offer_with_validity(days_ago=30, validity="10 Gün",
                                        status="Onaylandı")
        cancelled = self.svc.auto_cancel_expired()
        self.assertEqual(cancelled, [])
        self.assertEqual(self.svc.get_by_id(oid).status, "Onaylandı")

    def test_unparseable_validity_skipped(self):
        oid = self._offer_with_validity(days_ago=90, validity="Belirtilmemiş")
        cancelled = self.svc.auto_cancel_expired()
        self.assertEqual(cancelled, [])
        self.assertEqual(self.svc.get_by_id(oid).status, "Beklemede")

    def test_expiry_boundary_last_day_still_valid(self):
        # Tam son gün (kalan 0 gün) hâlâ geçerlidir — iptal edilmez
        oid = self._offer_with_validity(days_ago=10, validity="10 Gün")
        cancelled = self.svc.auto_cancel_expired()
        self.assertEqual(cancelled, [])
        self.assertEqual(self.svc.get_by_id(oid).status, "Beklemede")


if __name__ == "__main__":
    unittest.main(verbosity=2)
