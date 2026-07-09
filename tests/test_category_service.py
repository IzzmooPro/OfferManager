"""CategoryService birim testleri."""
import unittest

from database.db_manager import get_db
from models.category import Category
from services.category_service import CategoryService


class TestCategoryService(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = get_db()
        cls.svc = CategoryService()

    @classmethod
    def tearDownClass(cls):
        pass

    def setUp(self):
        with self.db.transaction() as conn:
            conn.execute("UPDATE products SET category_id=NULL")
            conn.execute("DELETE FROM product_categories")

    def _make(self, name="Test Kategori", **kw):
        return Category(name=name, **kw)

    def test_add_returns_id(self):
        cid = self.svc.add(self._make("Vanalar"))
        self.assertIsInstance(cid, int)
        self.assertGreater(cid, 0)

    def test_add_empty_name_raises(self):
        with self.assertRaises(ValueError):
            self.svc.add(self._make(""))

    def test_get_all_sorted(self):
        self.svc.add(self._make("Zebra"))
        self.svc.add(self._make("Alfa"))
        result = self.svc.get_all()
        names = [c.name for c in result]
        self.assertEqual(names, sorted(names))

    def test_get_by_id(self):
        cid = self.svc.add(self._make("Pompalar"))
        cat = self.svc.get_by_id(cid)
        self.assertIsNotNone(cat)
        self.assertEqual(cat.name, "Pompalar")

    def test_get_by_id_nonexistent(self):
        self.assertIsNone(self.svc.get_by_id(999999))

    def test_update(self):
        cid = self.svc.add(self._make("Eski"))
        cat = self.svc.get_by_id(cid)
        cat.name = "Yeni"
        self.svc.update(cat)
        self.assertEqual(self.svc.get_by_id(cid).name, "Yeni")

    def test_delete_clears_products(self):
        from services.product_service import ProductService
        from models.product import Product
        psvc = ProductService()
        cid = self.svc.add(self._make("Silinecek"))
        pid = psvc.add(Product(
            product_code="CAT-DEL-01", product_name="Ürün",
            category_id=cid))
        self.svc.delete(cid)
        self.assertIsNone(self.svc.get_by_id(cid))
        p = psvc.get_by_id(pid)
        self.assertIsNone(p.category_id)

    def test_count(self):
        self.assertEqual(self.svc.count(), 0)
        self.svc.add(self._make("A"))
        self.assertEqual(self.svc.count(), 1)

    def test_parent_child_relationship(self):
        parent_id = self.svc.add(self._make("Ana Kategori"))
        child_id = self.svc.add(self._make("Alt Kategori", parent_id=parent_id))
        child = self.svc.get_by_id(child_id)
        self.assertEqual(child.parent_id, parent_id)


if __name__ == "__main__":
    unittest.main(verbosity=2)
