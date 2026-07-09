"""CustomerService birim testleri."""
import unittest

from database.db_manager import get_db
from models.customer import Customer
from services.customer_service import CustomerService


class TestCustomerService(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = get_db()
        cls.svc = CustomerService()

    @classmethod
    def tearDownClass(cls):
        pass

    def setUp(self):
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM offer_items")
            conn.execute("DELETE FROM offers")
            conn.execute("DELETE FROM customers")

    def _make(self, name="Test Firma", **kw):
        return Customer(company_name=name, **kw)

    # ── add ──────────────────────────────────────────────────────────────

    def test_add_returns_id(self):
        cid = self.svc.add(self._make("Firma A"))
        self.assertIsInstance(cid, int)
        self.assertGreater(cid, 0)

    def test_add_empty_name_raises(self):
        with self.assertRaises(ValueError):
            self.svc.add(self._make(""))

    def test_add_with_all_fields(self):
        c = Customer(
            company_name="Tam Firma",
            contact_person="Ali Veli",
            address="İstanbul",
            phone="0555-111-2233",
            email="ali@firma.com",
            notes="VIP müşteri",
        )
        cid = self.svc.add(c)
        stored = self.svc.get_by_id(cid)
        self.assertEqual(stored.company_name, "Tam Firma")
        self.assertEqual(stored.contact_person, "Ali Veli")
        self.assertEqual(stored.address, "İstanbul")
        self.assertEqual(stored.phone, "0555-111-2233")
        self.assertEqual(stored.email, "ali@firma.com")
        self.assertEqual(stored.notes, "VIP müşteri")

    # ── get_by_id ────────────────────────────────────────────────────────

    def test_get_by_id_existing(self):
        cid = self.svc.add(self._make("Mevcut"))
        found = self.svc.get_by_id(cid)
        self.assertIsNotNone(found)
        self.assertEqual(found.company_name, "Mevcut")
        self.assertEqual(found.id, cid)

    def test_get_by_id_nonexistent(self):
        result = self.svc.get_by_id(999999)
        self.assertIsNone(result)

    # ── get_all ──────────────────────────────────────────────────────────

    def test_get_all_empty(self):
        self.assertEqual(self.svc.get_all(), [])

    def test_get_all_sorted_by_name(self):
        self.svc.add(self._make("Zebra"))
        self.svc.add(self._make("Alfa"))
        self.svc.add(self._make("Metro"))
        result = self.svc.get_all()
        names = [c.company_name for c in result]
        self.assertEqual(names, sorted(names))

    # ── search ───────────────────────────────────────────────────────────

    def test_search_by_company_name(self):
        self.svc.add(self._make("Sensoryum Teknik"))
        self.svc.add(self._make("Başka Firma"))
        result = self.svc.search("Sensoryum")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].company_name, "Sensoryum Teknik")

    def test_search_by_contact_person(self):
        self.svc.add(self._make("Firma X", contact_person="Ahmet Yılmaz"))
        result = self.svc.search("Ahmet")
        self.assertEqual(len(result), 1)

    def test_search_case_insensitive_ascii(self):
        self.svc.add(self._make("ABC Firma"))
        result = self.svc.search("abc")
        self.assertEqual(len(result), 1)

    def test_search_turkish_case_known_limitation(self):
        self.svc.add(self._make("BÜYÜK HARF"))
        result = self.svc.search("BÜYÜK")
        self.assertEqual(len(result), 1)

    def test_search_turkish_characters(self):
        self.svc.add(self._make("Şişecam Çelik Özel Ürün"))
        for kw in ["Şişecam", "Çelik", "Özel", "Ürün"]:
            result = self.svc.search(kw)
            self.assertGreaterEqual(len(result), 1, f"'{kw}' araması sonuç vermedi")

    def test_search_no_match(self):
        self.svc.add(self._make("Firma A"))
        result = self.svc.search("olmayan_kelime_xyz")
        self.assertEqual(result, [])

    # ── update ───────────────────────────────────────────────────────────

    def test_update_changes_fields(self):
        cid = self.svc.add(self._make("Eski Ad"))
        customer = self.svc.get_by_id(cid)
        customer.company_name = "Yeni Ad"
        customer.phone = "0533-000-0000"
        self.svc.update(customer)
        updated = self.svc.get_by_id(cid)
        self.assertEqual(updated.company_name, "Yeni Ad")
        self.assertEqual(updated.phone, "0533-000-0000")

    # ── delete ───────────────────────────────────────────────────────────

    def test_delete_removes_customer(self):
        cid = self.svc.add(self._make("Silinecek"))
        self.svc.delete(cid)
        self.assertIsNone(self.svc.get_by_id(cid))

    def test_delete_nonexistent_no_error(self):
        self.svc.delete(999999)

    # ── count ────────────────────────────────────────────────────────────

    def test_count_empty(self):
        self.assertEqual(self.svc.count(), 0)

    def test_count_after_add(self):
        self.svc.add(self._make("Bir"))
        self.svc.add(self._make("İki"))
        self.assertEqual(self.svc.count(), 2)

    def test_count_after_delete(self):
        cid = self.svc.add(self._make("Geçici"))
        self.svc.delete(cid)
        self.assertEqual(self.svc.count(), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
