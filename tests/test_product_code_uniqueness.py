"""O6 — Ürün kodu benzersizliği büyük/küçük harf duyarsız olmalı.

`products.product_code UNIQUE` BINARY collation kullandığı için 'abc' ve
'ABC' ayrı kayıt olabiliyordu; UI ise "aynı kod var, yine de kaydet?" diye
UYGULANAMAZ bir seçenek sunuyordu (Evet → her zaman IntegrityError).
İçe aktarma Python .upper(), get_by_code ise SQLite UPPER() kullandığı için
Türkçe kodlarda iki katman farklı ürüne eşleşiyordu.

Ortak anahtar: NFKC + casefold (yazım KORUNUR, yalnız karşılaştırma normalize).
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sqlite3
import time
import unittest
from unittest import mock

from database.db_manager import get_db
from models.product import Product
from services.product_service import ProductService


class ProductCodeNormalizationTests(unittest.TestCase):
    """Ortak karşılaştırma anahtarı — tek kaynak."""

    def setUp(self):
        from services.product_service import normalize_code
        self.norm = normalize_code

    def test_strips_and_casefolds(self):
        self.assertEqual(self.norm("  abc  "), self.norm("ABC"))
        self.assertEqual(self.norm("AbC"), "abc")

    def test_nfkc_compatibility_forms_match(self):
        # Tam genişlik (full-width) ve ligatür formları NFKC ile katlanır
        self.assertEqual(self.norm("ＡＢＣ"), self.norm("abc"))
        self.assertEqual(self.norm("ﬀ1"), self.norm("FF1"))

    def test_turkish_dotted_and_dotless_are_pinned(self):
        # casefold DİLDEN BAĞIMSIZDIR: Türkçe dilbilgisel eşitlik İDDİA EDİLMEZ.
        # Aşağıdaki davranış bilinçli olarak sabitlenmiştir.
        self.assertEqual(self.norm("ürün-1"), self.norm("ÜRÜN-1"))
        self.assertEqual(self.norm("adaptör"), self.norm("ADAPTÖR"))
        self.assertEqual(self.norm("İ"), self.norm("i̇"))   # İ -> i + birleşik nokta
        self.assertNotEqual(self.norm("I"), self.norm("ı"))  # I ve ı EŞİT DEĞİL
        self.assertNotEqual(self.norm("İ"), self.norm("i"))  # İ ve i EŞİT DEĞİL

    def test_empty_key_for_blank_code(self):
        self.assertEqual(self.norm("   "), "")
        self.assertEqual(self.norm(None), "")

    def test_does_not_change_user_spelling(self):
        # Fonksiyon yalnız ANAHTAR üretir; kaydedilen yazımı değiştirmez
        self.assertNotEqual(self.norm("AbC"), "AbC")


class ProductCodeUniquenessTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.db = get_db()
        cls.svc = ProductService()

    def setUp(self):
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM products")

    def _kodlar(self):
        return [r["product_code"] for r in
                self.db.fetchall("SELECT product_code FROM products ORDER BY id")]

    # ── add / update engelleme ───────────────────────────────────────────

    def test_ascii_case_variant_add_is_blocked(self):
        self.svc.add(Product(product_code="abc", product_name="İlk ürün"))
        with self.assertRaises(ValueError) as ctx:
            self.svc.add(Product(product_code="ABC", product_name="İkinci"))
        self.assertEqual(self._kodlar(), ["abc"])
        self.assertNotIsInstance(ctx.exception, sqlite3.IntegrityError)

    def test_turkish_case_variant_add_is_blocked(self):
        self.svc.add(Product(product_code="ürün-1", product_name="Küçük"))
        with self.assertRaises(ValueError):
            self.svc.add(Product(product_code="ÜRÜN-1", product_name="Büyük"))
        self.assertEqual(self._kodlar(), ["ürün-1"])

    def test_whitespace_variant_add_is_blocked(self):
        self.svc.add(Product(product_code="TRIM-1", product_name="İlk"))
        with self.assertRaises(ValueError):
            self.svc.add(Product(product_code="  trim-1  ", product_name="İkinci"))
        self.assertEqual(self._kodlar(), ["TRIM-1"])

    def test_saved_code_is_stripped(self):
        pid = self.svc.add(Product(product_code="  SPACED-1  ",
                                   product_name="Boşluklu"))
        self.assertEqual(self.svc.get_by_id(pid).product_code, "SPACED-1")

    def test_update_to_other_products_case_variant_is_blocked(self):
        self.svc.add(Product(product_code="XYZ-1", product_name="A"))
        bid = self.svc.add(Product(product_code="QWE-9", product_name="B"))
        p = self.svc.get_by_id(bid)
        p.product_code = "xyz-1"
        with self.assertRaises(ValueError):
            self.svc.update(p)
        self.assertEqual(sorted(self._kodlar()), ["QWE-9", "XYZ-1"])

    def test_update_can_change_own_code_spelling(self):
        pid = self.svc.add(Product(product_code="abc-9", product_name="Ürün"))
        p = self.svc.get_by_id(pid)
        p.product_code = "ABC-9"                  # yalnız yazım değişiyor
        self.svc.update(p)
        self.assertEqual(self.svc.get_by_id(pid).product_code, "ABC-9")

    def test_error_message_shows_existing_code_and_name(self):
        self.svc.add(Product(product_code="KOD-7", product_name="Mevcut Ürün"))
        with self.assertRaises(ValueError) as ctx:
            self.svc.add(Product(product_code="kod-7", product_name="Yeni"))
        mesaj = str(ctx.exception)
        self.assertIn("KOD-7", mesaj)
        self.assertIn("Mevcut Ürün", mesaj)

    def test_integrity_error_is_converted_to_domain_error(self):
        # Yarış durumu: kontrol geçti ama INSERT UNIQUE'e takıldı
        self.svc.add(Product(product_code="RACE-1", product_name="Var olan"))
        with mock.patch.object(ProductService, "get_by_code", return_value=None):
            with self.assertRaises(ValueError) as ctx:
                self.svc.add(Product(product_code="RACE-1", product_name="Yeni"))
        self.assertNotIsInstance(ctx.exception, sqlite3.IntegrityError)
        self.assertIn("RACE-1", str(ctx.exception))

    def test_empty_code_still_rejected(self):
        with self.assertRaises(ValueError):
            self.svc.add(Product(product_code="   ", product_name="Boş kod"))

    # ── get_by_code: ortak anahtar + determinizm ─────────────────────────

    def test_get_by_code_matches_case_and_unicode_variants(self):
        pid = self.svc.add(Product(product_code="ürün-2", product_name="T"))
        for sorgu in ("ürün-2", "ÜRÜN-2", "  Ürün-2  "):
            p = self.svc.get_by_code(sorgu)
            self.assertIsNotNone(p, f"{sorgu!r} eşleşmedi")
            self.assertEqual(p.id, pid)

    def test_get_by_code_picks_lowest_id_on_legacy_collision(self):
        # Eski DB'den kalma çakışma: index YOKKEN oluşabilir. Servis KATMANI
        # bu durumda da deterministik olmalı (en düşük id).
        self.db.execute("DROP INDEX IF EXISTS ux_products_code_nocase")
        self.addCleanup(self.db.execute,
                        "CREATE UNIQUE INDEX IF NOT EXISTS ux_products_code_nocase "
                        "ON products(product_code COLLATE NOCASE)")
        self.addCleanup(lambda: self.db.execute("DELETE FROM products"))
        with self.db.transaction() as conn:
            conn.execute("INSERT INTO products (id, product_code, product_name) "
                         "VALUES (7, 'dup', 'Kucuk')")
            conn.execute("INSERT INTO products (id, product_code, product_name) "
                         "VALUES (3, 'DUP', 'Buyuk')")
        with self.assertLogs("product_service", level="WARNING"):
            p = self.svc.get_by_code("Dup")
        self.assertEqual(p.id, 3, "en düşük id seçilmedi")


class ProductCodeSymmetryTests(unittest.TestCase):
    """Eşleşme GİRİŞ SIRASINDAN bağımsız olmalı (NFKC her iki yönde)."""

    @classmethod
    def setUpClass(cls):
        cls.db = get_db()
        cls.svc = ProductService()

    def setUp(self):
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM products")

    def _ham_ekle(self, kod, ad, pid=None):
        """Servisi atlayarak doğrudan ekler (eski/çakışmalı veri kurmak için)."""
        with self.db.transaction() as conn:
            if pid is None:
                conn.execute("INSERT INTO products (product_code, product_name) "
                             "VALUES (?, ?)", (kod, ad))
            else:
                conn.execute("INSERT INTO products (id, product_code, product_name) "
                             "VALUES (?, ?, ?)", (pid, kod, ad))

    def _kodlar(self):
        return [r["product_code"] for r in
                self.db.fetchall("SELECT product_code FROM products ORDER BY id")]

    # ── iki yönlü engelleme ──────────────────────────────────────────────

    def test_ascii_then_fullwidth_is_blocked(self):
        self.svc.add(Product(product_code="ABC", product_name="ASCII"))
        with self.assertRaises(ValueError):
            self.svc.add(Product(product_code="ＡＢＣ", product_name="Tam genişlik"))
        self.assertEqual(self._kodlar(), ["ABC"])

    def test_fullwidth_then_ascii_is_blocked(self):
        self.svc.add(Product(product_code="ＡＢＣ", product_name="Tam genişlik"))
        with self.assertRaises(ValueError):
            self.svc.add(Product(product_code="ABC", product_name="ASCII"))
        self.assertEqual(self._kodlar(), ["ＡＢＣ"])

    def test_ligature_both_orders_are_blocked(self):
        self.svc.add(Product(product_code="FF1", product_name="Duz"))
        with self.assertRaises(ValueError):
            self.svc.add(Product(product_code="ﬀ1", product_name="Ligatur"))
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM products")
        self.svc.add(Product(product_code="ﬀ1", product_name="Ligatur"))
        with self.assertRaises(ValueError):
            self.svc.add(Product(product_code="FF1", product_name="Duz"))

    def test_turkish_both_orders_are_blocked(self):
        self.svc.add(Product(product_code="ÜRÜN-9", product_name="Büyük"))
        with self.assertRaises(ValueError):
            self.svc.add(Product(product_code="ürün-9", product_name="Küçük"))
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM products")
        self.svc.add(Product(product_code="ürün-9", product_name="Küçük"))
        with self.assertRaises(ValueError):
            self.svc.add(Product(product_code="ÜRÜN-9", product_name="Büyük"))

    # ── exclude_id: kendi kaydı hariç tutulurken diğerleri kaçmamalı ────

    def test_exclude_id_still_finds_other_equivalent_record(self):
        # Kendi kaydı ASCII, başka kayıt tam genişlik eşdeğeri
        self._ham_ekle("ABC", "Kendi kaydi", pid=1)
        self._ham_ekle("ＡＢＣ", "Baska kayit", pid=2)
        bulunan = self.svc.get_by_code("ABC", exclude_id=1)
        self.assertIsNotNone(
            bulunan, "kendi kaydı bulundu diye diğer eşdeğer kayıt atlandı")
        self.assertEqual(bulunan.id, 2)

    def test_update_own_ascii_code_detects_fullwidth_conflict(self):
        self._ham_ekle("ABC", "Kendi kaydi", pid=1)
        self._ham_ekle("ＡＢＣ", "Baska kayit", pid=2)
        p = self.svc.get_by_id(1)
        p.product_name = "Yeni ad"
        with self.assertRaises(ValueError):
            self.svc.update(p)

    # ── determinizm: sıra değişse de aynı en düşük id ───────────────────

    def test_lowest_id_is_returned_in_both_insert_orders(self):
        self._ham_ekle("ＡＢＣ", "Once tam genislik", pid=2)
        self._ham_ekle("ABC", "Sonra ascii", pid=9)
        with self.assertLogs("product_service", level="WARNING"):
            self.assertEqual(self.svc.get_by_code("abc").id, 2)

        with self.db.transaction() as conn:
            conn.execute("DELETE FROM products")
        self._ham_ekle("ABC", "Once ascii", pid=2)
        self._ham_ekle("ＡＢＣ", "Sonra tam genislik", pid=9)
        with self.assertLogs("product_service", level="WARNING"):
            self.assertEqual(self.svc.get_by_code("ＡＢＣ").id, 2)


class NonAsciiPartialIndexTests(unittest.TestCase):
    """Yedek taramayı hızlandıran kısmi index — varlığı ve YOKLUĞU."""

    @classmethod
    def setUpClass(cls):
        cls.db = get_db()
        cls.svc = ProductService()

    def setUp(self):
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM products")

    def _index_var(self):
        return self.db.fetchone(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND name='ix_products_code_nonascii'") is not None

    def test_partial_index_exists_after_migration(self):
        self.assertTrue(self._index_var())

    def test_partial_index_is_not_unique(self):
        """Benzersiz OLMAMALI: aksi hâlde eski veride oluşturulamazdı."""
        row = self.db.fetchone(
            "SELECT sql FROM sqlite_master WHERE name='ix_products_code_nonascii'")
        self.assertNotIn("UNIQUE", (row["sql"] or "").upper())

    def test_lookup_is_correct_without_the_nocase_index(self):
        """NOCASE index'i olmayan eski DB'de de büyük/küçük harf eşleşmeli.

        Sorgunun index'e bağımlı OLMADIĞINI sabitler: collation sütuna
        yazılmazsa plan BINARY autoindex'e düşüp hiç eşleşme döndürmüyordu.
        """
        with self.db.transaction() as conn:
            conn.execute("DROP INDEX IF EXISTS ux_products_code_nocase")
        self.addCleanup(self.db.execute,
                        "CREATE UNIQUE INDEX IF NOT EXISTS ux_products_code_nocase "
                        "ON products(product_code COLLATE NOCASE)")
        self.svc.add(Product(product_code="KOD-77", product_name="Bir"))
        self.assertIsNotNone(self.svc.get_by_code("kod-77"))
        self.assertIsNotNone(self.svc.get_by_code("Kod-77"))

    def test_lookup_is_correct_without_the_index(self):
        """Index düşürülse bile sonuç DEĞİŞMEZ — yalnız yavaşlar."""
        with self.db.transaction() as conn:
            conn.execute("DROP INDEX IF EXISTS ix_products_code_nonascii")
        self.addCleanup(self.db.execute,
                        "CREATE INDEX IF NOT EXISTS ix_products_code_nonascii "
                        "ON products(product_code) "
                        "WHERE product_code GLOB '*[^ -~]*'")
        self.assertFalse(self._index_var())
        self.svc.add(Product(product_code="ＸＹＺ", product_name="Tam genişlik"))
        self.assertIsNotNone(self.svc.get_by_code("xyz"))
        with self.assertRaises(ValueError):
            self.svc.add(Product(product_code="XYZ", product_name="ASCII"))


class ImportDuplicateScopeTests(unittest.TestCase):
    """Dosya içi tekrar kontrolü YALNIZ ürün dalında çalışmalı."""

    @classmethod
    def setUpClass(cls):
        cls.db = get_db()

    def setUp(self):
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM products")
            conn.execute("DELETE FROM customers")

    def test_duplicate_customer_rows_get_no_product_message(self):
        from ui.utils.excel_import import _validate_rows
        rows = [{"Firma Adı": "Aynı Firma"}, {"Firma Adı": "Aynı Firma"}]
        valid, dups, invalid = _validate_rows("customers", rows)
        for r in invalid:
            self.assertNotIn("ürün kodu", r.get("_error", "").lower(),
                             f"müşteri satırına ürün mesajı verildi: {r}")
        self.assertEqual(len(valid) + len(dups), 2,
                         "müşteri davranışı O6 kapsamında değişti")

    def test_duplicate_product_rows_are_still_flagged(self):
        from ui.utils.excel_import import _validate_rows
        rows = [
            {"Ürün Kodu": "abc", "Ürün Adı": "Bir"},
            {"Ürün Kodu": "ABC", "Ürün Adı": "İki"},
            {"Ürün Kodu": "ürün-1", "Ürün Adı": "Üç"},
            {"Ürün Kodu": "ÜRÜN-1", "Ürün Adı": "Dört"},
        ]
        valid, dups, invalid = _validate_rows("products", rows)
        self.assertEqual(len(valid), 2, "normalize tekrarlar ayrı ürün sayıldı")
        self.assertEqual(len(invalid), 2)
        for r in invalid:
            self.assertIn("birden fazla", r.get("_error", "").lower())


class ProductCodeMigrationTests(unittest.TestCase):
    """Koşullu UNIQUE INDEX: veriyi asla değiştirmez, çakışmada atlanır."""

    def setUp(self):
        import tempfile
        from pathlib import Path
        from database import db_manager
        self.db_manager = db_manager
        self._tmp = tempfile.TemporaryDirectory(prefix="oms_o6mig_")
        self.addCleanup(self._tmp.cleanup)
        self.path = Path(self._tmp.name) / "test.db"
        self._onceki = db_manager._schema_initialized
        self.addCleanup(setattr, db_manager, "_schema_initialized", self._onceki)

    def _db_kur(self):
        """Gerçek DB.__init__ akışıyla şema + migration çalıştırır."""
        self.db_manager._schema_initialized = False
        with mock.patch.object(self.db_manager, "DB_PATH", self.path):
            return self.db_manager.DB()

    def _indexler(self):
        con = sqlite3.connect(str(self.path))
        try:
            return {r[0] for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='index'")}
        finally:
            con.close()

    def _ekle(self, *kodlar):
        con = sqlite3.connect(str(self.path))
        try:
            for i, k in enumerate(kodlar, 1):
                con.execute("INSERT INTO products (product_code, product_name) "
                            "VALUES (?, ?)", (k, f"Urun {i}"))
            con.commit()
        finally:
            con.close()

    def test_index_created_on_clean_database(self):
        self._db_kur()
        self.assertIn("ux_products_code_nocase", self._indexler())

    def test_migration_is_idempotent(self):
        self._db_kur()
        self._db_kur()                     # ikinci kez — hata vermemeli
        self.assertIn("ux_products_code_nocase", self._indexler())

    def test_index_blocks_case_variant_after_migration(self):
        self._db_kur()
        self._ekle("abc")
        with self.assertRaises(sqlite3.IntegrityError):
            self._ekle("ABC")

    def test_legacy_collision_skips_index_without_touching_data(self):
        self._db_kur()
        # Index'i kaldırıp çakışmalı eski veriyi kur
        con = sqlite3.connect(str(self.path))
        con.execute("DROP INDEX IF EXISTS ux_products_code_nocase")
        con.commit(); con.close()
        self._ekle("abc", "ABC")

        with self.assertLogs("db_manager", level="WARNING"):
            self._db_kur()                 # uygulama AÇILABİLMELİ

        self.assertNotIn("ux_products_code_nocase", self._indexler(),
                         "çakışma varken index oluşturuldu")
        con = sqlite3.connect(str(self.path))
        try:
            kodlar = [r[0] for r in con.execute(
                "SELECT product_code FROM products ORDER BY id")]
        finally:
            con.close()
        self.assertEqual(kodlar, ["abc", "ABC"], "eski veri değişti")


class GetByCodePerformanceTests(unittest.TestCase):
    """10 bin ürün ölçeğinde get_by_code kabul edilebilir kalmalı."""

    ADET = 10_000
    SINIR_MS = 60

    @classmethod
    def setUpClass(cls):
        cls.db = get_db()
        cls.svc = ProductService()
        with cls.db.transaction() as conn:
            conn.execute("DELETE FROM products")
            conn.executemany(
                "INSERT INTO products (product_code, product_name) VALUES (?,?)",
                [(f"PERF-{i:06d}", f"Ürün {i}") for i in range(cls.ADET)])
            conn.execute("INSERT INTO products (product_code, product_name) "
                         "VALUES ('PERF-ÜRÜN', 'Türkçe kod')")

    @classmethod
    def tearDownClass(cls):
        with cls.db.transaction() as conn:
            conn.execute("DELETE FROM products")

    def _sure_ms(self, kod, tekrar=20):
        t0 = time.perf_counter()
        for _ in range(tekrar):
            self.svc.get_by_code(kod)
        return (time.perf_counter() - t0) / tekrar * 1000

    def test_existing_ascii_code_is_fast(self):
        ms = self._sure_ms("perf-005000")
        self.assertLess(ms, self.SINIR_MS, f"mevcut ASCII kod: {ms:.1f} ms")

    def test_missing_code_is_fast(self):
        # add() sırasındaki SICAK YOL: kod henüz yok
        ms = self._sure_ms("PERF-YOK-999999")
        self.assertLess(ms, self.SINIR_MS, f"olmayan kod: {ms:.1f} ms")

    def test_non_ascii_code_is_acceptable(self):
        ms = self._sure_ms("perf-ürün")
        self.assertLess(ms, self.SINIR_MS, f"ASCII dışı kod: {ms:.1f} ms")


if __name__ == "__main__":
    unittest.main(verbosity=2)
