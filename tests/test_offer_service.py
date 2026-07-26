"""OfferService birim testleri."""
import threading
import unittest
import unittest.mock
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

    # Süresi dolan teklifler artık KENDİLİĞİNDEN iptal edilmez: listelenir,
    # yalnızca kullanıcı onayıyla (cancel_expired) güncellenir.

    def test_expired_pending_is_listed_without_writing(self):
        oid = self._offer_with_validity(days_ago=30, validity="10 Gün")
        expired = self.svc.get_expired_pending()
        self.assertEqual([o.id for o in expired], [oid])
        self.assertEqual(self.svc.get_by_id(oid).status, "Beklemede",
                         "listeleme veritabanına yazdı")

    def test_cancel_expired_updates_only_requested_pending(self):
        oid = self._offer_with_validity(days_ago=30, validity="10 Gün")
        self.assertEqual(self.svc.cancel_expired([oid]), 1)
        self.assertEqual(self.svc.get_by_id(oid).status, "İptal")

    def test_valid_pending_not_listed(self):
        oid = self._offer_with_validity(days_ago=5, validity="30 Gün")
        self.assertEqual(self.svc.get_expired_pending(), [])
        self.assertEqual(self.svc.get_by_id(oid).status, "Beklemede")

    def test_expired_approved_not_listed_and_not_cancelled(self):
        oid = self._offer_with_validity(days_ago=30, validity="10 Gün",
                                        status="Onaylandı")
        self.assertEqual(self.svc.get_expired_pending(), [])
        # Doğrudan istense bile Beklemede olmayan teklif değiştirilmemeli
        self.assertEqual(self.svc.cancel_expired([oid]), 0)
        self.assertEqual(self.svc.get_by_id(oid).status, "Onaylandı")

    def test_unparseable_validity_not_listed(self):
        oid = self._offer_with_validity(days_ago=90, validity="Belirtilmemiş")
        self.assertEqual(self.svc.get_expired_pending(), [])
        self.assertEqual(self.svc.get_by_id(oid).status, "Beklemede")

    def test_expiry_boundary_last_day_still_valid(self):
        # Tam son gün (kalan 0 gün) hâlâ geçerlidir — süresi dolmuş sayılmaz
        oid = self._offer_with_validity(days_ago=10, validity="10 Gün")
        self.assertEqual(self.svc.get_expired_pending(), [])
        self.assertEqual(self.svc.get_by_id(oid).status, "Beklemede")

    def test_cancel_expired_uses_single_transaction(self):
        ids = [self._offer_with_validity(days_ago=30, validity="10 Gün")
               for _ in range(3)]
        from database import db_manager
        sayac = {"n": 0}
        gercek = db_manager.DB.transaction

        def _sayan(self_db, *a, **k):
            sayac["n"] += 1
            return gercek(self_db, *a, **k)

        with unittest.mock.patch.object(db_manager.DB, "transaction", _sayan):
            self.assertEqual(self.svc.cancel_expired(ids), 3)
        self.assertEqual(sayac["n"], 1,
                         f"satır başına ayrı transaction açıldı ({sayac['n']})")
        for oid in ids:
            self.assertEqual(self.svc.get_by_id(oid).status, "İptal")

    def test_cancel_expired_rolls_back_on_failure(self):
        ids = [self._offer_with_validity(days_ago=30, validity="10 Gün")
               for _ in range(3)]
        import sqlite3
        from database import db_manager

        gercek_transaction = db_manager.DB.transaction

        class _PatlayanConn:
            """3. execute çağrısında hata veren sarmalayıcı."""
            def __init__(self, gercek):
                self._g = gercek
                self._n = 0

            def execute(self, *a, **k):
                self._n += 1
                if self._n == 3:
                    raise sqlite3.OperationalError("test: güncelleme hatası")
                return self._g.execute(*a, **k)

            def __getattr__(self, ad):
                return getattr(self._g, ad)

        from contextlib import contextmanager

        @contextmanager
        def _sarmalayan(self_db, *a, **k):
            with gercek_transaction(self_db, *a, **k) as conn:
                yield _PatlayanConn(conn)

        with unittest.mock.patch.object(db_manager.DB, "transaction", _sarmalayan):
            with self.assertRaises(sqlite3.OperationalError):
                self.svc.cancel_expired(ids)

        for oid in ids:
            self.assertEqual(self.svc.get_by_id(oid).status, "Beklemede",
                             "hata sonrası değişiklikler geri alınmadı")


# ── İçe aktarılan teklif numarası ↔ sayaç senkronizasyonu ──────────────────

class TestImportedOfferNumberCounter(unittest.TestCase):
    """keep_offer_no=True ile kaydedilen teklifler sayacı ileri taşımalı.

    Aksi hâlde sonraki yeni teklif aynı numarayı üretip
    `UNIQUE constraint failed: offers.offer_no` ile kalıcı olarak
    başarısız oluyordu.
    """

    @classmethod
    def setUpClass(cls):
        cls.db = get_db()
        cls.svc = OfferService()

    def setUp(self):
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM offer_items")
            conn.execute("DELETE FROM offers")
            conn.execute("DELETE FROM offer_counter")

    def _imported(self, offer_no: str) -> Offer:
        o = _valid_offer()
        o.offer_no = offer_no
        return o

    def _last_number(self):
        row = self.db.fetchone(
            "SELECT last_number FROM offer_counter WHERE year = 0")
        return row["last_number"] if row else None

    def test_new_offer_after_import_does_not_collide(self):
        self.svc.save(_valid_offer())                      # SNS-000001
        self.svc.save(self._imported("SNS-000002"), keep_offer_no=True)
        oid = self.svc.save(_valid_offer())                # çakışmamalı
        self.assertEqual(self.svc.get_by_id(oid).offer_no, "SNS-000003")

    def test_import_advances_counter(self):
        self.svc.save(self._imported("SNS-000042"), keep_offer_no=True)
        self.assertEqual(self._last_number(), 42)
        self.assertEqual(self.svc.preview_offer_no(), "SNS-000043")

    def test_import_never_rewinds_counter(self):
        # Silinmiş bir teklifin yedekten geri aktarılması: numara sayacın
        # gerisinde kalır, sayaç geriye çekilmemelidir.
        first = self.svc.save(_valid_offer())              # SNS-000001
        self.svc.save(_valid_offer())                      # SNS-000002
        self.svc.save(_valid_offer())                      # sayaç = 3
        self.svc.delete(first)
        self.svc.save(self._imported("SNS-000001"), keep_offer_no=True)
        self.assertEqual(self._last_number(), 3)
        oid = self.svc.save(_valid_offer())
        self.assertEqual(self.svc.get_by_id(oid).offer_no, "SNS-000004")

    def test_unparseable_offer_no_leaves_counter_untouched(self):
        self.svc.save(_valid_offer())                      # sayaç = 1
        self.svc.save(self._imported("ELDEN-GIRILDI"), keep_offer_no=True)
        self.assertEqual(self._last_number(), 1)
        oid = self.svc.save(_valid_offer())
        self.assertEqual(self.svc.get_by_id(oid).offer_no, "SNS-000002")

    def test_foreign_prefix_leaves_counter_untouched(self):
        self.svc.save(_valid_offer())                      # sayaç = 1
        self.svc.save(self._imported("ABC-000900"), keep_offer_no=True)
        self.assertEqual(self._last_number(), 1)
        oid = self.svc.save(_valid_offer())
        self.assertEqual(self.svc.get_by_id(oid).offer_no, "SNS-000002")

    def test_probe_limit_fails_loudly_without_touching_counter(self):
        # Tarama penceresindeki TÜM numaralar doluysa üretici kontrol edilmemiş
        # bir numara döndürmemeli; açık bir hatayla durmalı ve sayacı
        # değiştirmemeli (hata transaction ile birlikte geri alınır).
        from services.offer_service import _MAX_OFFER_NO_PROBES
        rows = [(f"SNS-{n:06d}", "2026-01-01", "TL", 0.0)
                for n in range(1, _MAX_OFFER_NO_PROBES + 1)]
        with self.db.transaction() as conn:
            conn.executemany(
                "INSERT INTO offers (offer_no, date, currency, total_amount) "
                "VALUES (?,?,?,?)", rows)
            conn.execute("INSERT INTO offer_counter (year, last_number) VALUES (0, 0)")

        with self.assertRaises(RuntimeError):
            self.svc.save(_valid_offer())

        self.assertEqual(self._last_number(), 0, "sayaç değişmiş")
        remaining = self.db.fetchone("SELECT COUNT(*) AS cnt FROM offers")["cnt"]
        self.assertEqual(remaining, _MAX_OFFER_NO_PROBES, "yarım kayıt kalmış")

    def test_free_number_just_inside_probe_limit_still_works(self):
        # Sınırın son adımındaki boş numara normal biçimde bulunmalı —
        # tarama davranışı daraltılmamalı.
        from services.offer_service import _MAX_OFFER_NO_PROBES
        rows = [(f"SNS-{n:06d}", "2026-01-01", "TL", 0.0)
                for n in range(1, _MAX_OFFER_NO_PROBES)]
        with self.db.transaction() as conn:
            conn.executemany(
                "INSERT INTO offers (offer_no, date, currency, total_amount) "
                "VALUES (?,?,?,?)", rows)
            conn.execute("INSERT INTO offer_counter (year, last_number) VALUES (0, 0)")

        oid = self.svc.save(_valid_offer())
        self.assertEqual(self.svc.get_by_id(oid).offer_no,
                         f"SNS-{_MAX_OFFER_NO_PROBES:06d}")
        self.assertEqual(self._last_number(), _MAX_OFFER_NO_PROBES)

    def test_generator_skips_existing_number_when_counter_is_behind(self):
        # Sayaç geride kalmış bir DB (eski sürümden gelen kayıt) — üretici
        # mevcut numaranın üstüne yazmak yerine boş numaraya ilerlemeli.
        self.svc.save(self._imported("SNS-000001"), keep_offer_no=True)
        with self.db.transaction() as conn:
            conn.execute("UPDATE offer_counter SET last_number=0 WHERE year=0")
        oid = self.svc.save(_valid_offer())
        self.assertEqual(self.svc.get_by_id(oid).offer_no, "SNS-000002")


if __name__ == "__main__":
    unittest.main(verbosity=2)
