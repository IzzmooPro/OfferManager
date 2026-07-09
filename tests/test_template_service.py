"""TemplateService birim testleri."""
import unittest

from database.db_manager import get_db
from models.template import OfferTemplate, TemplateItem
from services.template_service import TemplateService


class TestTemplateService(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = get_db()
        cls.svc = TemplateService()

    @classmethod
    def tearDownClass(cls):
        pass

    def setUp(self):
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM offer_templates")

    def _make(self, name="Test Şablon", currency="EUR", items=None):
        if items is None:
            items = [TemplateItem(
                product_code="TST-01",
                product_name="Test Ürün",
                quantity=2,
                unit_price=100.0,
            )]
        return OfferTemplate(template_name=name, currency=currency, items=items)

    # ── save ─────────────────────────────────────────────────────────────

    def test_save_returns_id(self):
        tid = self.svc.save(self._make())
        self.assertIsInstance(tid, int)
        self.assertGreater(tid, 0)

    def test_save_empty_name_raises(self):
        with self.assertRaises(ValueError):
            self.svc.save(self._make(name=""))

    def test_save_no_items_raises(self):
        with self.assertRaises(ValueError):
            self.svc.save(self._make(items=[]))

    def test_save_persists_items(self):
        items = [
            TemplateItem(product_code="A", product_name="Ürün A", quantity=3, unit_price=50),
            TemplateItem(product_code="B", product_name="Ürün B", quantity=1, unit_price=200),
        ]
        tid = self.svc.save(self._make(items=items))
        loaded = self.svc.get_by_id(tid)
        self.assertEqual(len(loaded.items), 2)
        self.assertEqual(loaded.items[0].product_code, "A")
        self.assertEqual(loaded.items[1].product_code, "B")
        self.assertAlmostEqual(loaded.items[0].quantity, 3.0)

    def test_save_update_existing(self):
        tid = self.svc.save(self._make("Eski Ad"))
        tmpl = self.svc.get_by_id(tid)
        tmpl.template_name = "Yeni Ad"
        self.svc.save(tmpl)
        updated = self.svc.get_by_id(tid)
        self.assertEqual(updated.template_name, "Yeni Ad")

    # ── get_all ──────────────────────────────────────────────────────────

    def test_get_all_empty(self):
        self.assertEqual(self.svc.get_all(), [])

    def test_get_all_sorted(self):
        self.svc.save(self._make("Zebra"))
        self.svc.save(self._make("Alfa"))
        result = self.svc.get_all()
        names = [t.template_name for t in result]
        self.assertEqual(names, sorted(names))

    # ── get_by_id ────────────────────────────────────────────────────────

    def test_get_by_id_nonexistent(self):
        self.assertIsNone(self.svc.get_by_id(999999))

    # ── delete ───────────────────────────────────────────────────────────

    def test_delete_removes(self):
        tid = self.svc.save(self._make())
        self.svc.delete(tid)
        self.assertIsNone(self.svc.get_by_id(tid))

    # ── rename ───────────────────────────────────────────────────────────

    def test_rename(self):
        tid = self.svc.save(self._make("Eski"))
        self.svc.rename(tid, "Yeni")
        self.assertEqual(self.svc.get_by_id(tid).template_name, "Yeni")

    def test_rename_empty_raises(self):
        tid = self.svc.save(self._make())
        with self.assertRaises(ValueError):
            self.svc.rename(tid, "")

    # ── count ────────────────────────────────────────────────────────────

    def test_count(self):
        self.assertEqual(self.svc.count(), 0)
        self.svc.save(self._make("A"))
        self.svc.save(self._make("B"))
        self.assertEqual(self.svc.count(), 2)

    # ── create_from_offer ────────────────────────────────────────────────

    def test_create_from_offer_items(self):
        from models.offer_item import OfferItem
        items = [
            OfferItem(product_code="X", product_name="Ürün X",
                      quantity=5, unit_price=10, unit="Kg"),
        ]
        tid = self.svc.create_from_offer("Teklif Şablonu", "TL", items)
        loaded = self.svc.get_by_id(tid)
        self.assertEqual(loaded.template_name, "Teklif Şablonu")
        self.assertEqual(loaded.currency, "TL")
        self.assertEqual(len(loaded.items), 1)
        self.assertEqual(loaded.items[0].product_code, "X")
        self.assertAlmostEqual(loaded.items[0].quantity, 5.0)

    # ── JSON roundtrip ───────────────────────────────────────────────────

    def test_items_json_roundtrip(self):
        items = [
            TemplateItem(product_code="ÖZL", product_name="Özel Ürün",
                         description="Türkçe açıklama: şçğüıö",
                         quantity=1.5, unit="Metre", unit_price=99.99),
        ]
        tmpl = self._make(items=items)
        json_str = tmpl.items_to_json()
        parsed = OfferTemplate.items_from_json(json_str)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0].product_code, "ÖZL")
        self.assertEqual(parsed[0].description, "Türkçe açıklama: şçğüıö")
        self.assertAlmostEqual(parsed[0].unit_price, 99.99)


if __name__ == "__main__":
    unittest.main(verbosity=2)
