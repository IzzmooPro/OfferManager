"""O13 — müşteri içe aktarmada dosya içi mükerrer satırlar.

Ölçüm: aynı firma adı dosyada N kez geçtiğinde N ayrı müşteri kaydı sessizce
oluşuyordu (4 tekrar → 4 kayıt, hiçbir uyarı yok). Ürün tarafı O6'da
kapatılmıştı; müşteri dalı bilinçli olarak dışarıda bırakılmıştı.

KİMLİK SÖZLEŞMESİ (bu turda DEĞİŞMEZ): müşteri anahtarı DB eşleşmesiyle
birebir aynı, yani `(company_name or "").strip()`. Casefold/NFKC UYGULANMAZ;
`Acme` ile `ACME` farklı müşteri sayılır. Aynı isimli farklı gerçek müşteriler
olabileceği için yeni UNIQUE constraint eklenmez.

SAYAÇ SÖZLEŞMESİ: dosya içi tekrarlar mevcut `invalid` kategorisine YALNIZ BİR
KEZ yazılır; `duplicate` (DB'de zaten var) ile `invalid` (dosya içi tekrar)
ayrı kategorilerdir ve örtüşmez.
"""
import csv
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from database.db_manager import get_db
from ui.utils import excel_import as ei

TEKRAR_MESAJI = "Bu firma adı dosyada birden fazla kez var"


def _m(ad, tel="", eposta=""):
    return {"Firma Adı": ad, "Telefon": tel, "E-Posta": eposta}


class _Temel(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.db = get_db()

    def setUp(self):
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM customers")

    def _aktar(self, satirlar, update_dups=False):
        valid, dup, invalid = ei._validate_rows("customers", satirlar)
        rows = list(valid) + (list(dup) if update_dups else [])
        eklendi, guncellendi, atlandi, hatalar = ei._perform_import(
            "customers", rows, update_dups)
        kayit = self.db.fetchall(
            "SELECT company_name, phone, email FROM customers ORDER BY id")
        return {
            "valid": len(valid), "duplicate": len(dup), "invalid": len(invalid),
            "eklendi": eklendi, "guncellendi": guncellendi,
            "atlandi": atlandi, "hata": len(hatalar), "hatalar": hatalar,
            "kayit": [dict(k) for k in kayit],
            "invalid_mesaj": [r.get("_error", "") for r in invalid],
        }


class InFileDuplicateTests(_Temel):
    """İlk geçerli satır adı sahiplenir; sonrakiler atlanır."""

    def test_two_identical_rows_create_one_record(self):
        s = self._aktar([_m("Acme Ltd", "111"), _m("Acme Ltd", "222")])
        self.assertEqual(len(s["kayit"]), 1, "dosya içi tekrar kayıt oluşturdu")
        self.assertEqual(s["kayit"][0]["phone"], "111", "ilk satır kazanmadı")
        self.assertEqual(s["invalid"], 1)
        self.assertIn(TEKRAR_MESAJI, s["invalid_mesaj"][0])

    def test_four_repeats_create_one_record(self):
        s = self._aktar([_m("Beta AS", f"tel{i}") for i in range(4)])
        self.assertEqual(len(s["kayit"]), 1)
        self.assertEqual(s["kayit"][0]["phone"], "tel0")
        self.assertEqual(s["invalid"], 3)

    def test_five_repeats_create_one_record(self):
        s = self._aktar([_m("Gama AS", f"t{i}") for i in range(5)])
        self.assertEqual(len(s["kayit"]), 1)
        self.assertEqual(s["eklendi"], 1)
        self.assertEqual(s["invalid"], 4)

    def test_non_adjacent_repeats(self):
        s = self._aktar([_m("A AS", "1"), _m("B AS", "2"),
                         _m("C AS", "3"), _m("A AS", "4")])
        adlar = [k["company_name"] for k in s["kayit"]]
        self.assertEqual(adlar, ["A AS", "B AS", "C AS"])
        self.assertEqual(s["kayit"][0]["phone"], "1")
        self.assertEqual(s["invalid"], 1)

    def test_leading_trailing_whitespace_is_same_key(self):
        s = self._aktar([_m("Delta AS", "1"), _m("  Delta AS  ", "2")])
        self.assertEqual(len(s["kayit"]), 1, "boşluk varyantı tekrar sayılmadı")
        self.assertEqual(s["kayit"][0]["phone"], "1")

    def test_error_message_has_no_traceback(self):
        s = self._aktar([_m("Eps AS", "1"), _m("Eps AS", "2")])
        for mesaj in s["invalid_mesaj"]:
            self.assertNotIn("Traceback", mesaj)


class IdentityContractTests(_Temel):
    """Bu turda DEĞİŞMEYEN kimlik sözleşmesi."""

    def test_case_difference_stays_separate(self):
        s = self._aktar([_m("Acme", "1"), _m("ACME", "2")])
        self.assertEqual(len(s["kayit"]), 2,
                         "harf duyarsızlık bu turda EKLENMEMELİ")
        self.assertEqual(s["invalid"], 0)

    def test_unicode_variant_stays_separate(self):
        s = self._aktar([_m("Acme Ltd", "1"), _m("Ａcme Ltd", "2")])
        self.assertEqual(len(s["kayit"]), 2,
                         "NFKC normalizasyonu bu turda EKLENMEMELİ")

    def test_no_unique_index_added(self):
        idx = self.db.fetchall(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND tbl_name='customers'")
        self.assertEqual([r["name"] for r in idx], [],
                         "customers tablosuna index eklenmiş")


class FirstRowOwnershipTests(_Temel):

    def test_invalid_first_row_does_not_claim_name(self):
        """İlk satır zorunlu alanı geçemiyorsa adı sahiplenmemeli."""
        s = self._aktar([{"Telefon": "1"},              # Firma Adı YOK
                         _m("Zeta AS", "2")])
        self.assertEqual(len(s["kayit"]), 1)
        self.assertEqual(s["kayit"][0]["company_name"], "Zeta AS")
        self.assertEqual(s["kayit"][0]["phone"], "2")
        self.assertEqual(s["invalid"], 1)
        self.assertNotIn(TEKRAR_MESAJI, s["invalid_mesaj"][0])

    def test_first_row_insert_failure_does_not_promote_second(self):
        """İlk satır DB'de patlasa da ikinci tekrar İŞLENMEZ (deterministik)."""
        from contextlib import contextmanager
        orj = self.db.transaction

        class _Sarmal:
            def __init__(self, c):
                self._c = c
                self.n = 0

            def execute(self, sql, params=()):
                if sql.strip().upper().startswith("INSERT INTO CUSTOMERS"):
                    self.n += 1
                    if self.n == 1:
                        raise RuntimeError("ilk satır hatası")
                return self._c.execute(sql, params)

            def __getattr__(self, ad):
                return getattr(self._c, ad)

        @contextmanager
        def sahte(exclusive=False):
            with orj(exclusive) as c:
                yield _Sarmal(c)

        self.db.transaction = sahte
        # ÖRNEK niteliğini tamamen kaldır: setattr ile geri yazmak sınıf
        # metodunu kalıcı olarak gölgeler ve sonraki testleri bozar.
        self.addCleanup(self.db.__dict__.pop, "transaction", None)
        s = self._aktar([_m("Hata AS", "1"), _m("Hata AS", "2")])
        self.assertEqual(len(s["kayit"]), 0,
                         "ilk satır hatasında ikinci tekrar işlendi")
        self.assertEqual(s["hata"], 1)
        self.assertEqual(s["invalid"], 1)


class ExistingRecordTests(_Temel):

    def _db_ye_ekle(self, ad="Acme Ltd", tel="eski"):
        with self.db.transaction() as conn:
            conn.execute("INSERT INTO customers (company_name, phone) "
                         "VALUES (?, ?)", (ad, tel))

    def test_update_disabled_keeps_existing_and_skips_repeat(self):
        self._db_ye_ekle()
        s = self._aktar([_m("Acme Ltd", "yeni1"), _m("Acme Ltd", "yeni2")],
                        update_dups=False)
        self.assertEqual(len(s["kayit"]), 1)
        self.assertEqual(s["kayit"][0]["phone"], "eski")
        self.assertEqual(s["duplicate"], 1, "dosya içi tekrar da dup sayıldı")
        self.assertEqual(s["invalid"], 1)
        self.assertIn(TEKRAR_MESAJI, s["invalid_mesaj"][0])

    def test_update_enabled_updates_target_once(self):
        self._db_ye_ekle()
        s = self._aktar([_m("Acme Ltd", "yeni1"), _m("Acme Ltd", "yeni2")],
                        update_dups=True)
        self.assertEqual(len(s["kayit"]), 1)
        self.assertEqual(s["kayit"][0]["phone"], "yeni1",
                         "ilk dosya satırı kazanmadı")
        self.assertEqual(s["guncellendi"], 1,
                         "aynı hedef birden çok kez güncellendi")

    def test_counters_have_no_overlap(self):
        self._db_ye_ekle()
        s = self._aktar([_m("Acme Ltd", "a"), _m("Acme Ltd", "b"),
                         _m("Yeni AS", "c")], update_dups=True)
        toplam = s["eklendi"] + s["guncellendi"] + s["atlandi"] + s["invalid"]
        self.assertEqual(toplam, 3, f"sayaç toplamı satır sayısıyla uyuşmuyor: {s}")
        self.assertEqual(s["duplicate"], 1)


class FileFormatParityTests(_Temel):
    """CSV ve XLSX aynı sonucu vermeli."""

    def _dosyadan(self, yol):
        satirlar, hata = ei._read_file(str(yol))
        self.assertEqual(hata, "")
        return self._aktar(satirlar)

    def test_csv_and_xlsx_agree(self):
        with TemporaryDirectory(prefix="o13_", ignore_cleanup_errors=True) as t:
            kok = Path(t)
            csv_yol = kok / "m.csv"
            with open(csv_yol, "w", encoding="utf-8-sig", newline="") as f:
                w = csv.writer(f)
                w.writerow(["Firma Adı", "Telefon"])
                w.writerow(["Ortak AS", "1"])
                w.writerow(["Ortak AS", "2"])
            csv_sonuc = self._dosyadan(csv_yol)

            with self.db.transaction() as conn:
                conn.execute("DELETE FROM customers")

            from openpyxl import Workbook
            wb = Workbook()
            s = wb.active
            s.append(["Firma Adı", "Telefon"])
            s.append(["Ortak AS", "1"])
            s.append(["Ortak AS", "2"])
            xlsx_yol = kok / "m.xlsx"
            wb.save(xlsx_yol)
            xlsx_sonuc = self._dosyadan(xlsx_yol)

        for ad, s in (("csv", csv_sonuc), ("xlsx", xlsx_sonuc)):
            with self.subTest(bicim=ad):
                self.assertEqual(len(s["kayit"]), 1)
                self.assertEqual(s["kayit"][0]["phone"], "1")
                self.assertEqual(s["invalid"], 1)


class ProductContractUnchangedTests(_Temel):
    """Ürün tarafının O6 davranışı bu turda değişmemeli."""

    def setUp(self):
        super().setUp()
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM products")

    def test_product_duplicate_message_unchanged(self):
        rows = [{"Ürün Kodu": "abc", "Ürün Adı": "Bir"},
                {"Ürün Kodu": "ABC", "Ürün Adı": "İki"}]
        valid, dup, invalid = ei._validate_rows("products", rows)
        self.assertEqual(len(valid), 1)
        self.assertEqual(len(invalid), 1)
        self.assertIn("ürün kodu", invalid[0]["_error"].lower())

    def test_product_normalize_still_case_insensitive(self):
        rows = [{"Ürün Kodu": "ürün-1", "Ürün Adı": "A"},
                {"Ürün Kodu": "ÜRÜN-1", "Ürün Adı": "B"}]
        valid, dup, invalid = ei._validate_rows("products", rows)
        self.assertEqual(len(valid), 1)
        self.assertEqual(len(invalid), 1)


if __name__ == "__main__":
    unittest.main()
