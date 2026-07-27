"""O11 — teklif/şablon yüklemede N+1 `get_by_code` yerine batch arama.

Ölçüm: kalem başına 2 SQL sorgusu yapılıyordu (100 kalem → 200 sorgu / 201 ms,
500 kalem → 1000 sorgu / 1038 ms). Aynı kod tekrarlansa bile yeniden
sorgulanıyordu.

Bu testler `ProductService.get_by_codes()` sözleşmesini ve iki UI yolunun tek
batch çağrısı yaptığını sabitler. O6 eşleşme sözleşmesi (NFKC + casefold, ham +
normalize NOCASE adayları, ASCII dışı fallback, çakışmada en düşük id + uyarı)
aynen korunmalıdır.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest
from unittest import mock

from PySide6.QtWidgets import QApplication

import database.db_manager as dbm
from database.db_manager import get_db
from models.offer_item import OfferItem
from models.product import Product
from services.product_service import ProductService, normalize_code
from services.template_service import TemplateService
from ui.create_offer_page import CreateOfferPage


class _SorguSayaci:
    """DB katmanındaki SQL çağrılarını sayar."""

    def __enter__(self):
        self.n = 0
        self._orj = (dbm.DB.fetchall, dbm.DB.fetchone, dbm.DB.execute)
        sayac = self

        def sar(orj):
            def _f(kendisi, sql, params=()):
                sayac.n += 1
                return orj(kendisi, sql, params)
            return _f

        dbm.DB.fetchall, dbm.DB.fetchone, dbm.DB.execute = (
            sar(self._orj[0]), sar(self._orj[1]), sar(self._orj[2]))
        return self

    def __exit__(self, *a):
        dbm.DB.fetchall, dbm.DB.fetchone, dbm.DB.execute = self._orj
        return False


class _Temel(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.db = get_db()
        cls.svc = ProductService()

    def setUp(self):
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM products")

    def _urun_ekle(self, adet, onek="URN", maliyet_taban=1.0):
        with self.db.transaction() as conn:
            conn.executemany(
                "INSERT INTO products (product_code, product_name, price, "
                "currency, stock, unit, cost_price, description) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [(f"{onek}-{i:05d}", f"Ürün {i:05d}", 10.0 + i, "EUR", 3,
                  "Adet", maliyet_taban + i, f"Açıklama {i}")
                 for i in range(adet)])
        return [f"{onek}-{i:05d}" for i in range(adet)]


class BatchApiTests(_Temel):

    def test_returns_mapping_keyed_by_normalized_code(self):
        kodlar = self._urun_ekle(3)
        sonuc = self.svc.get_by_codes(kodlar)
        self.assertEqual(set(sonuc), {normalize_code(k) for k in kodlar})
        for k in kodlar:
            self.assertEqual(sonuc[normalize_code(k)].product_code, k)

    def test_missing_codes_are_absent(self):
        kodlar = self._urun_ekle(2)
        sonuc = self.svc.get_by_codes(kodlar + ["YOK-1", "YOK-2"])
        self.assertEqual(len(sonuc), 2)
        self.assertNotIn(normalize_code("YOK-1"), sonuc)

    def test_empty_and_blank_input(self):
        self._urun_ekle(2)
        self.assertEqual(self.svc.get_by_codes([]), {})
        self.assertEqual(self.svc.get_by_codes(["", "   ", None]), {})

    def test_returned_product_has_all_contract_fields(self):
        self.svc.add(Product(product_code="ABC-1", product_name="Test",
                             price=12.5, currency="USD", stock=4, unit="Kutu",
                             cost_price=7.5, description="Açıklama"))
        p = self.svc.get_by_codes(["ABC-1"])[normalize_code("ABC-1")]
        self.assertIsNotNone(p.id)
        self.assertEqual(p.product_code, "ABC-1")
        self.assertEqual(p.product_name, "Test")
        self.assertEqual(p.description, "Açıklama")
        self.assertEqual(p.unit, "Kutu")
        self.assertEqual(p.price, 12.5)
        self.assertEqual(p.currency, "USD")
        self.assertEqual(p.cost_price, 7.5)
        self.assertEqual(p.stock, 4)

    def test_o6_matching_contract_is_preserved(self):
        self.svc.add(Product(product_code="ABC", product_name="A", price=1.0,
                             currency="EUR", stock=0, unit="Adet"))
        for varyant in ("ABC", "abc", "  ABC  ", "ＡＢＣ"):
            with self.subTest(varyant=varyant):
                sonuc = self.svc.get_by_codes([varyant])
                self.assertIn(normalize_code(varyant), sonuc)
                self.assertEqual(sonuc[normalize_code(varyant)].product_code,
                                 "ABC")

    def test_turkish_case_contract_matches_get_by_code(self):
        self.svc.add(Product(product_code="ÜRÜN-1", product_name="A", price=1.0,
                             currency="EUR", stock=0, unit="Adet"))
        for varyant in ("ürün-1", "ÜRÜN-1"):
            with self.subTest(varyant=varyant):
                tekil = self.svc.get_by_code(varyant)
                toplu = self.svc.get_by_codes([varyant]).get(
                    normalize_code(varyant))
                self.assertIsNotNone(toplu)
                self.assertEqual(tekil.id, toplu.id)

    def test_legacy_collision_uses_lowest_id_and_warns(self):
        with self.db.transaction() as conn:
            conn.execute("DROP INDEX IF EXISTS ux_products_code_nocase")
            conn.execute(
                "INSERT INTO products (id, product_code, product_name, price,"
                " currency, stock, unit) VALUES (11, 'ＣＬＳＨ', 'A', 1,"
                " 'EUR', 0, 'Adet')")
            conn.execute(
                "INSERT INTO products (id, product_code, product_name, price,"
                " currency, stock, unit) VALUES (22, 'CLSH', 'B', 1,"
                " 'EUR', 0, 'Adet')")
        self.addCleanup(
            self.db.execute,
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_products_code_nocase "
            "ON products(product_code COLLATE NOCASE)")
        with self.assertLogs("product_service", level="WARNING"):
            sonuc = self.svc.get_by_codes(["clsh"])
        self.assertEqual(sonuc[normalize_code("clsh")].id, 11)


class QueryCountTests(_Temel):
    """Sorgu sayısı kalem sayısıyla DOĞRUSAL büyümemeli."""

    SABIT_UST_SINIR = 6      # chunk + fallback + eksik satır çekimi

    def test_100_items_query_count_is_constant(self):
        kodlar = self._urun_ekle(100)
        with _SorguSayaci() as s:
            self.svc.get_by_codes(kodlar)
        self.assertLessEqual(s.n, self.SABIT_UST_SINIR,
                             f"100 kalem için {s.n} sorgu (doğrusal büyüme)")

    def test_500_items_query_count_does_not_grow_linearly(self):
        kodlar = self._urun_ekle(500)
        with _SorguSayaci() as yuz:
            self.svc.get_by_codes(kodlar[:100])
        with _SorguSayaci() as bes_yuz:
            self.svc.get_by_codes(kodlar)
        self.assertLessEqual(bes_yuz.n, yuz.n + 2,
                             f"100→{yuz.n}, 500→{bes_yuz.n} sorgu")

    def test_repeated_code_is_queried_once(self):
        kodlar = self._urun_ekle(1)
        with _SorguSayaci() as s:
            sonuc = self.svc.get_by_codes(kodlar * 100)
        self.assertLessEqual(s.n, self.SABIT_UST_SINIR)
        self.assertEqual(len(sonuc), 1)

    def test_chunking_handles_more_than_sqlite_param_limit(self):
        kodlar = self._urun_ekle(1200)
        sonuc = self.svc.get_by_codes(kodlar)
        self.assertEqual(len(sonuc), 1200,
                         "SQLite parametre sınırı aşıldı veya kayıp var")


class InputShapeTests(_Temel):
    """Girdi türleri: tuple, generator, tek kullanımlık iterable, None/boşluk."""

    def test_tuple_input(self):
        kodlar = self._urun_ekle(3)
        self.assertEqual(len(self.svc.get_by_codes(tuple(kodlar))), 3)

    def test_generator_input_is_consumed_once_safely(self):
        kodlar = self._urun_ekle(3)
        sonuc = self.svc.get_by_codes(k for k in kodlar)
        self.assertEqual(len(sonuc), 3)

    def test_single_use_iterator_input(self):
        kodlar = self._urun_ekle(4)
        sonuc = self.svc.get_by_codes(iter(kodlar))
        self.assertEqual(len(sonuc), 4)

    def test_none_blank_and_whitespace_codes_are_ignored(self):
        kodlar = self._urun_ekle(2)
        sonuc = self.svc.get_by_codes([kodlar[0], None, "", "   ", "\t\n",
                                       kodlar[1]])
        self.assertEqual(set(sonuc),
                         {normalize_code(kodlar[0]), normalize_code(kodlar[1])})

    def test_none_input_returns_empty(self):
        self._urun_ekle(2)
        self.assertEqual(self.svc.get_by_codes(None), {})


class ChunkBoundaryTests(_Temel):
    """400 / 401 / 800 / 1200 farklı aday — chunk sınırları."""

    def _hepsi_bulunmali(self, adet):
        kodlar = self._urun_ekle(adet)
        sonuc = self.svc.get_by_codes(kodlar)
        self.assertEqual(len(sonuc), adet, f"{adet} kodda kayıp var")
        for k in kodlar:
            self.assertIn(normalize_code(k), sonuc)
        return kodlar

    def test_400_codes(self):
        self._hepsi_bulunmali(400)

    def test_401_codes(self):
        self._hepsi_bulunmali(401)

    def test_800_codes(self):
        self._hepsi_bulunmali(800)

    def test_1200_codes(self):
        self._hepsi_bulunmali(1200)

    def test_same_key_candidates_merge_across_chunks(self):
        """Ham ve normalize aday ayrı chunk'lara düşse de tek anahtar kalır."""
        self._urun_ekle(500, onek="AAA")
        # Her kod için 2 aday (ham + normalize) üretilir → 1000 aday, 3 chunk
        kodlar = [f"AAA-{i:05d}" for i in range(500)]
        buyuk = [k.upper() for k in kodlar]          # ham ≠ normalize
        sonuc = self.svc.get_by_codes(buyuk)
        self.assertEqual(len(sonuc), 500)
        for k in kodlar:
            self.assertEqual(sonuc[normalize_code(k)].product_code, k)


class QueryContractTests(_Temel):
    """SQL sorgu sayısının KESİN sözleşmesi."""

    def _sorgu_sayisi(self, kodlar):
        with _SorguSayaci() as s:
            self.svc.get_by_codes(kodlar)
        return s.n

    def test_small_fast_set_uses_two_queries(self):
        kodlar = self._urun_ekle(5)
        self.assertEqual(self._sorgu_sayisi(kodlar), 2,
                         "hızlı IN + non-ASCII taraması bekleniyordu")

    def test_chunked_set_uses_ceil_plus_one(self):
        import math
        kodlar = self._urun_ekle(500)
        aday = len({k for k in kodlar} | {normalize_code(k) for k in kodlar})
        beklenen = math.ceil(aday / 400) + 1
        self.assertEqual(self._sorgu_sayisi(kodlar), beklenen,
                         f"{aday} aday için ceil/400 + 1 bekleniyordu")

    def test_fallback_winners_are_fetched_in_one_extra_query(self):
        """Yalnız non-ASCII fallback'ten gelen kazananlar TEK sorguda çekilir."""
        with self.db.transaction() as conn:
            conn.executemany(
                "INSERT INTO products (product_code, product_name, price, "
                "currency, stock, unit) VALUES (?, ?, ?, ?, ?, ?)",
                [(f"ＦＷ{i:03d}", f"Tam Genişlik {i}", 1.0, "EUR", 0, "Adet")
                 for i in range(12)])
        # ASCII yazımla aranırsa hızlı IN bulmaz; fallback bulur.
        aranan = [f"FW{i:03d}" for i in range(12)]
        with _SorguSayaci() as s:
            sonuc = self.svc.get_by_codes(aranan)
        self.assertEqual(len(sonuc), 12, "fallback kazananları bulunamadı")
        self.assertEqual(s.n, 3, "12 kazanan için 12 ayrı SELECT üretildi")

    def test_single_fallback_winner_still_three_queries(self):
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO products (product_code, product_name, price, "
                "currency, stock, unit) VALUES ('ＳＯＬＯ', 'Tek', 1.0, "
                "'EUR', 0, 'Adet')")
        with _SorguSayaci() as s:
            sonuc = self.svc.get_by_codes(["SOLO"])
        self.assertEqual(len(sonuc), 1)
        self.assertEqual(s.n, 3)


class CrossChunkCollisionTests(_Temel):
    """Legacy çakışma farklı chunk'lara dağılsa da en düşük id kazanmalı."""

    def test_lowest_id_wins_across_chunks(self):
        with self.db.transaction() as conn:
            conn.execute("DROP INDEX IF EXISTS ux_products_code_nocase")
            # Dolgu: adayların birden çok chunk'a yayılması için
            conn.executemany(
                "INSERT INTO products (product_code, product_name, price, "
                "currency, stock, unit) VALUES (?, ?, ?, ?, ?, ?)",
                [(f"DLG-{i:05d}", f"Dolgu {i}", 1.0, "EUR", 0, "Adet")
                 for i in range(500)])
            conn.execute(
                "INSERT INTO products (id, product_code, product_name, price,"
                " currency, stock, unit) VALUES (700001, 'ＸＣＨＫ', 'A', 1,"
                " 'EUR', 0, 'Adet')")
            conn.execute(
                "INSERT INTO products (id, product_code, product_name, price,"
                " currency, stock, unit) VALUES (700002, 'XCHK', 'B', 1,"
                " 'EUR', 0, 'Adet')")
        self.addCleanup(
            self.db.execute,
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_products_code_nocase "
            "ON products(product_code COLLATE NOCASE)")
        kodlar = [f"DLG-{i:05d}" for i in range(500)] + ["xchk"]
        with self.assertLogs("product_service", level="WARNING"):
            sonuc = self.svc.get_by_codes(kodlar)
        self.assertEqual(sonuc[normalize_code("xchk")].id, 700001)
        self.assertEqual(len(sonuc), 501)


class UnicodeParityTests(_Temel):
    """get_by_code ve get_by_codes aynı varyantta AYNI id'yi vermeli."""

    def test_same_id_for_all_variants(self):
        self.svc.add(Product(product_code="PRT-Ü1", product_name="A", price=1.0,
                             currency="EUR", stock=0, unit="Adet"))
        varyantlar = ["PRT-Ü1", "prt-ü1", "  PRT-Ü1  ", "ＰＲＴ-Ü1"]
        for v in varyantlar:
            with self.subTest(varyant=v):
                tekil = self.svc.get_by_code(v)
                toplu = self.svc.get_by_codes([v]).get(normalize_code(v))
                self.assertEqual(tekil is None, toplu is None)
                if tekil is not None:
                    self.assertEqual(tekil.id, toplu.id)


class TemplateLoadTests(_Temel):
    """Şablon yükleme yolu tek batch çağrısı yapmalı."""

    def setUp(self):
        super().setUp()
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM offer_templates")
        self.page = CreateOfferPage()
        self.addCleanup(self.page.deleteLater)

    def _sablon_yukle(self, kodlar, para="EUR"):
        """Şablonu kaydeder ve GERÇEK `_load_from_template()` akışını çalıştırır."""
        items = [OfferItem(product_code=k, product_name=f"Ürün {i}",
                           quantity=1, unit="Adet", delivery_time="1 Hafta",
                           unit_price=10.0, total_price=10.0)
                 for i, k in enumerate(kodlar)]
        TemplateService().create_from_offer("Test Şablon", para, items)
        with mock.patch("PySide6.QtWidgets.QInputDialog.getItem",
                        side_effect=lambda *a, **k: (a[3][0], True)):
            self.page._load_from_template()

    def test_single_batch_call_and_no_per_item_lookup(self):
        kodlar = self._urun_ekle(25)
        with mock.patch.object(ProductService, "get_by_codes",
                               wraps=ProductService().get_by_codes) as toplu, \
             mock.patch.object(ProductService, "get_by_code") as tekil:
            self._sablon_yukle(kodlar)
        self.assertEqual(toplu.call_count, 1, "tek batch çağrısı olmalı")
        tekil.assert_not_called()

    def test_row_order_and_repeats_preserved(self):
        kodlar = self._urun_ekle(3)
        sirali = [kodlar[0], kodlar[2], kodlar[0], kodlar[1]]
        self._sablon_yukle(sirali)
        self.assertEqual(self.page.prod_table.rowCount(), 4)
        gorunen = [self.page.prod_table.item(r, 0).text()
                   for r in range(self.page.prod_table.rowCount())]
        self.assertEqual(gorunen, sirali)

    def test_missing_product_yields_zero_cost(self):
        kodlar = self._urun_ekle(1, maliyet_taban=42.0)
        self._sablon_yukle([kodlar[0], "SILINMIS-KOD"])
        self.assertEqual(self.page._row_costs()[0], 42.0)
        self.assertEqual(self.page._row_costs()[1], 0.0)

    def test_cost_matches_single_lookup(self):
        kodlar = self._urun_ekle(4, maliyet_taban=5.0)
        self._sablon_yukle(kodlar)
        for i, k in enumerate(kodlar):
            self.assertEqual(self.page._row_costs()[i],
                             self.svc.get_by_code(k).cost_price)


class OfferLoadTests(_Temel):
    """Teklif düzenleme yolu da tek batch çağrısı yapmalı."""

    def setUp(self):
        super().setUp()
        self.page = CreateOfferPage()
        self.addCleanup(self.page.deleteLater)

    def _teklif(self, kodlar):
        from models.offer import Offer
        from services.offer_service import OfferService
        items = [OfferItem(product_code=k, product_name=f"Ürün {i}",
                           quantity=2, unit="Adet", delivery_time="1 Hafta",
                           unit_price=20.0, total_price=40.0)
                 for i, k in enumerate(kodlar)]
        teklif = Offer(company_name="Firma", currency="EUR", items=items,
                       total_amount=sum(it.total_price for it in items))
        return OfferService().save(teklif)      # load_offer id bekler

    def test_single_batch_call_on_offer_load(self):
        kodlar = self._urun_ekle(15)
        teklif_id = self._teklif(kodlar)
        with mock.patch.object(ProductService, "get_by_codes",
                               wraps=ProductService().get_by_codes) as toplu, \
             mock.patch.object(ProductService, "get_by_code") as tekil:
            self.page.load_offer(teklif_id)
        self.assertEqual(toplu.call_count, 1)
        tekil.assert_not_called()

    def test_offer_rows_keep_order_and_costs(self):
        kodlar = self._urun_ekle(3, maliyet_taban=100.0)
        teklif_id = self._teklif([kodlar[1], kodlar[0], kodlar[1]])
        self.page.load_offer(teklif_id)
        self.assertEqual(self.page.prod_table.rowCount(), 3)
        gorunen = [self.page.prod_table.item(r, 0).text() for r in range(3)]
        self.assertEqual(gorunen, [kodlar[1], kodlar[0], kodlar[1]])
        self.assertEqual(self.page._row_costs()[0], self.page._row_costs()[2])


class SingleLookupUnchangedTests(_Temel):
    """`get_by_code` sözleşmesi bu turda değişmemeli."""

    def test_single_lookup_still_works(self):
        self.svc.add(Product(product_code="TEK-1", product_name="A",
                             price=1.0, currency="EUR", stock=0, unit="Adet",
                             cost_price=9.0))
        p = self.svc.get_by_code("tek-1")
        self.assertIsNotNone(p)
        self.assertEqual(p.cost_price, 9.0)

    def test_single_lookup_exclude_id_still_works(self):
        pid = self.svc.add(Product(product_code="TEK-2", product_name="A",
                                   price=1.0, currency="EUR", stock=0,
                                   unit="Adet"))
        self.assertIsNone(self.svc.get_by_code("TEK-2", exclude_id=pid))


if __name__ == "__main__":
    unittest.main()
