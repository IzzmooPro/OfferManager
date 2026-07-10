"""ProductService birim testleri."""
import unittest

from database.db_manager import get_db
from models.product import Product
from services.product_service import ProductService


class TestProductService(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = get_db()
        cls.svc = ProductService()

    @classmethod
    def tearDownClass(cls):
        pass

    def setUp(self):
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM offer_items")
            conn.execute("DELETE FROM offers")
            conn.execute("DELETE FROM products")

    def _make(self, code="TST-001", name="Test Ürün", price=100.0, **kw):
        return Product(product_code=code, product_name=name, price=price, **kw)

    # ── add ──────────────────────────────────────────────────────────────

    def test_add_returns_id(self):
        pid = self.svc.add(self._make())
        self.assertIsInstance(pid, int)
        self.assertGreater(pid, 0)

    def test_add_with_all_fields(self):
        p = Product(
            product_code="FULL-01",
            product_name="Tam Ürün",
            description="Açıklama satırı",
            price=250.50,
            currency="USD",
            stock=42.0,
            unit="Kutu",
        )
        pid = self.svc.add(p)
        stored = self.svc.get_by_id(pid)
        self.assertEqual(stored.product_code, "FULL-01")
        self.assertEqual(stored.product_name, "Tam Ürün")
        self.assertEqual(stored.description, "Açıklama satırı")
        self.assertAlmostEqual(stored.price, 250.50)
        self.assertEqual(stored.currency, "USD")
        self.assertAlmostEqual(stored.stock, 42.0)
        self.assertEqual(stored.unit, "Kutu")

    # ── cost_price (alış fiyatı / kâr analizi) ──────────────────────────────

    def test_add_default_cost_price_is_zero(self):
        pid = self.svc.add(self._make("COST-DEF"))
        stored = self.svc.get_by_id(pid)
        self.assertAlmostEqual(stored.cost_price, 0.0)

    def test_add_with_cost_price(self):
        pid = self.svc.add(self._make("COST-01", cost_price=75.0))
        stored = self.svc.get_by_id(pid)
        self.assertAlmostEqual(stored.cost_price, 75.0)

    def test_update_cost_price(self):
        pid = self.svc.add(self._make("COST-UPD", cost_price=50.0))
        p = self.svc.get_by_id(pid)
        p.cost_price = 90.0
        self.svc.update(p)
        updated = self.svc.get_by_id(pid)
        self.assertAlmostEqual(updated.cost_price, 90.0)

    def test_add_empty_code_raises(self):
        with self.assertRaises(ValueError):
            self.svc.add(self._make(code="", name="Ürün"))

    def test_add_empty_name_raises(self):
        with self.assertRaises(ValueError):
            self.svc.add(self._make(code="X-01", name=""))

    def test_add_duplicate_code_raises(self):
        self.svc.add(self._make("UNIQUE-01"))
        with self.assertRaises(Exception):
            self.svc.add(self._make("UNIQUE-01"))

    # ── get_by_code ──────────────────────────────────────────────────────

    def test_get_by_code_case_insensitive(self):
        self.svc.add(self._make("ABC-123", "Ürün A"))
        result = self.svc.get_by_code("abc-123")
        self.assertIsNotNone(result)
        self.assertEqual(result.product_name, "Ürün A")

    def test_get_by_code_not_found(self):
        result = self.svc.get_by_code("NONEXISTENT")
        self.assertIsNone(result)

    # ── get_by_id ────────────────────────────────────────────────────────

    def test_get_by_id_existing(self):
        pid = self.svc.add(self._make("GBI-01"))
        found = self.svc.get_by_id(pid)
        self.assertIsNotNone(found)
        self.assertEqual(found.product_code, "GBI-01")

    def test_get_by_id_nonexistent(self):
        self.assertIsNone(self.svc.get_by_id(999999))

    # ── get_all ──────────────────────────────────────────────────────────

    def test_get_all_empty(self):
        self.assertEqual(self.svc.get_all(), [])

    def test_get_all_sorted_by_name(self):
        self.svc.add(self._make("Z-01", "Zebra Ürün"))
        self.svc.add(self._make("A-01", "Alfa Ürün"))
        result = self.svc.get_all()
        names = [p.product_name for p in result]
        self.assertEqual(names, sorted(names))

    # ── search ───────────────────────────────────────────────────────────

    def test_search_by_code(self):
        self.svc.add(self._make("SNS-VALVE-01", "Vana"))
        result = self.svc.search("SNS-VALVE")
        self.assertEqual(len(result), 1)

    def test_search_by_name(self):
        self.svc.add(self._make("X-01", "Hidrolik Pompa"))
        result = self.svc.search("Hidrolik")
        self.assertEqual(len(result), 1)

    def test_search_by_description(self):
        self.svc.add(self._make("D-01", "Ürün", description="paslanmaz çelik gövdeli"))
        result = self.svc.search("paslanmaz")
        self.assertEqual(len(result), 1)

    def test_search_no_match(self):
        self.svc.add(self._make("X-01", "Ürün"))
        self.assertEqual(self.svc.search("olmayan_xyz"), [])

    # ── update ───────────────────────────────────────────────────────────

    def test_update_price(self):
        pid = self.svc.add(self._make("UPD-01", price=100.0))
        p = self.svc.get_by_id(pid)
        p.price = 200.0
        self.svc.update(p)
        updated = self.svc.get_by_id(pid)
        self.assertAlmostEqual(updated.price, 200.0)

    def test_update_stock(self):
        pid = self.svc.add(self._make("STK-01", stock=10.0))
        p = self.svc.get_by_id(pid)
        p.stock = 5.0
        self.svc.update(p)
        updated = self.svc.get_by_id(pid)
        self.assertAlmostEqual(updated.stock, 5.0)

    # ── delete ───────────────────────────────────────────────────────────

    def test_delete_removes_product(self):
        pid = self.svc.add(self._make("DEL-01"))
        self.svc.delete(pid)
        self.assertIsNone(self.svc.get_by_id(pid))

    # ── count ────────────────────────────────────────────────────────────

    def test_count_empty(self):
        self.assertEqual(self.svc.count(), 0)

    def test_count_after_operations(self):
        self.svc.add(self._make("CNT-01"))
        self.svc.add(self._make("CNT-02"))
        self.assertEqual(self.svc.count(), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
