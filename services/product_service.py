"""Ürün servis katmanı."""
import logging
import sqlite3
import unicodedata
from typing import List, Optional
from database.db_manager import get_db
from models.product import Product

logger = logging.getLogger("product_service")


def normalize_code(code: str) -> str:
    """Ürün kodunun KARŞILAŞTIRMA anahtarı — yazımı DEĞİŞTİRMEZ.

    strip → NFKC → casefold. Uygulamanın tamamı (servis, arayüz, içe aktarma)
    bu tek anahtarı kullanır; böylece 'abc'/'ABC', 'ürün'/'ÜRÜN' ve tam
    genişlik/ligatür yazımları aynı ürüne eşlenir. Kullanıcının girdiği
    product_code olduğu gibi saklanır — otomatik BÜYÜTME yapılmaz.

    casefold Unicode'un DİLDEN BAĞIMSIZ katlamasıdır; Türkçe'ye özgü
    I/İ/ı/i eşitliği İDDİA EDİLMEZ (davranış testlerle sabitlenmiştir).
    """
    return unicodedata.normalize("NFKC", (code or "").strip()).casefold()


class DuplicateProductCodeError(ValueError):
    """Aynı koda sahip başka bir ürün var (büyük/küçük harf duyarsız)."""

    def __init__(self, existing: Product):
        self.existing = existing
        super().__init__(
            f"Bu ürün kodu zaten kayıtlı:\n"
            f"Kod: {existing.product_code}\nÜrün: {existing.product_name}")


# Yalnız yazdırılabilir ASCII DIŞI karakter içeren kodları seçen GLOB deseni.
# NFKC/casefold ile SQLite'ın ASCII-only NOCASE karşılaştırması yalnız bu
# satırlarda ayrışabilir; yedek tarama böylece küçük bir kümeyle sınırlanır.
#
# Sorguya PARAMETRE olarak değil, birebir metin olarak gömülür: SQLite kısmi
# index'i (ix_products_code_nonascii) ancak WHERE koşulu index'in koşuluyla
# METİN olarak eşleştiğinde kullanır; bağlı parametre kullanılırsa plan tüm
# tabloyu taramaya düşer. Sabit bir modül değeri olduğundan kullanıcı girdisi
# içermez — SQL enjeksiyonu söz konusu değildir.
_NON_ASCII_GLOB = "*[^ -~]*"


class ProductService:
    """Ürün CRUD işlemleri."""

    def get_by_code(self, code: str, exclude_id: Optional[int] = None) -> Optional[Product]:
        """Ürün kodu ile ara (NFKC + casefold; büyük/küçük harf duyarsız).

        Sonuç GİRİŞ SIRASINDAN BAĞIMSIZDIR: 'ABC' varken 'ＡＢＣ' de, 'ＡＢＣ'
        varken 'ABC' de aynı kayda eşleşir. Adaylar TEK sorguda, üç ölçütün
        birleşimi olarak toplanır:
          1) `= ham_kod COLLATE NOCASE` — kullanıcının yazdığı hâl,
          2) `= normalize_code(code) COLLATE NOCASE` — normalize anahtar; ASCII
             saklanmış bir kaydın tam genişlik/ligatür yazımıyla aranmasını da
             yakalar (tek yönlü eşleşme sorununun kaynağı buydu),
          3) ASCII dışı karakter içeren satırlar — NFKC ve harf katlaması
             yalnız bu (küçük) kümede NOCASE'ten farklılaşabilir.

        Adaylar HER ZAMAN birlikte toplanır: hızlı ölçütlerden birinin eşleşmesi
        diğerlerinin değerlendirilmesini atlatmaz. exclude_id tüm adaylar
        toplandıktan SONRA uygulanır; böylece kendi kaydını güncelleyen bir ürün,
        başka kayıttaki eşdeğeri kaçırmaz. Tekilleştirme ve `ORDER BY id` ile
        eski DB'den kalma çakışmalarda sonuç DETERMİNİSTİKTİR: en düşük id
        seçilir ve uyarı loglanır.

        Maliyet: (1) ve (2) index araması; (3) ise ix_products_code_nonascii
        KISMİ index'i üzerinden yalnız ASCII dışı kodları tarar (gerçek veride
        10.096 satır yerine 66 girdi). İki ölçüt AYRI ifade olarak çalıştırılır,
        çünkü tek bir OR sorgusunda SQLite kısmi index'i kullanamayıp tüm
        tabloyu tarıyor. Index yoksa sonuç yine DOĞRUDUR, yalnız yavaşlar.
        Tam satır yalnız gerçekten eşleşen kayıt için çekilir.
        """
        key = normalize_code(code)
        if not key:
            return None
        db = get_db()
        # COLLATE, SAĞ tarafa değil SÜTUNA yazılır: `product_code = ? COLLATE
        # NOCASE` biçimi tek başına doğru çalışsa da birden çok adayla
        # birleştirildiğinde SQLite planı BINARY autoindex'e düşürüp HİÇBİR
        # eşleşme döndürmüyor (ölçüldü). Bu biçim ux_products_code_nocase
        # index'ini kullanır ve her iki yönde de doğru sonuç verir.
        # Index araması az satır döndürdüğünden tam satır burada çekilir;
        # böylece eşleşme bulunduğunda ek sorgu gerekmez.
        hizli = {r["id"]: r for r in db.fetchall(
            "SELECT * FROM products WHERE product_code COLLATE NOCASE IN (?, ?)",
            ((code or "").strip(), key))}
        adaylar = {pid: r["product_code"] for pid, r in hizli.items()}
        # Yedek tarama yalnız (id, product_code) seçer → kısmi index'i kapsayan
        # tarama; 1,7 MB'lık ürün tablosu okunmaz.
        adaylar.update({r["id"]: r["product_code"] for r in db.fetchall(
            f"SELECT id, product_code FROM products "
            f"WHERE product_code GLOB '{_NON_ASCII_GLOB}'")})
        eslesen = sorted(pid for pid, kod in adaylar.items()
                         if normalize_code(kod) == key and pid != exclude_id)
        if not eslesen:
            return None
        if len(eslesen) > 1:
            logger.warning(
                "Aynı ürün kodu (%r) %d kayıtta bulundu; en düşük id (%s) "
                "kullanılıyor: %s", key, len(eslesen), eslesen[0], eslesen)
        row = hizli.get(eslesen[0])
        if row is None:          # kazanan yalnız yedek taramada bulundu
            row = db.fetchone("SELECT * FROM products WHERE id = ?", (eslesen[0],))
        return Product.from_row(row) if row else None

    def _category_clause(self, category_id):
        """(sql_parça, params) — kategori filtresi. -1=yok, None=kategorisiz."""
        if category_id == -1:
            return "", []
        if category_id is None:
            return "category_id IS NULL", []
        return "category_id = ?", [category_id]

    def get_all(self, category_id: Optional[int] = -1,
                limit: Optional[int] = None) -> List[Product]:
        """Tüm ürünleri döndürür. category_id verilirse kategoriye göre filtreler.
        -1 = filtre yok, None = kategorisiz ürünler. limit verilirse ilk N kayıt."""
        db = get_db()
        cat_sql, params = self._category_clause(category_id)
        sql = "SELECT * FROM products"
        if cat_sql:
            sql += " WHERE " + cat_sql
        sql += " ORDER BY product_name"
        if limit:
            sql += " LIMIT ?"; params.append(limit)
        rows = db.fetchall(sql, tuple(params))
        return [Product.from_row(r) for r in rows]

    def search(self, keyword: str, category_id: Optional[int] = -1,
               limit: Optional[int] = None) -> List[Product]:
        """Kod, ad veya açıklamaya göre ara (büyük/küçük harf duyarsız).
        category_id ile kategoriye, limit ile ilk N kayda göre de daraltır."""
        db = get_db()
        kw = f"%{keyword}%"
        cat_sql, params = self._category_clause(category_id)
        where = ["(product_code LIKE ? OR product_name LIKE ? OR description LIKE ?)"]
        search_params = [kw, kw, kw]
        if cat_sql:
            where.insert(0, cat_sql)
        sql = "SELECT * FROM products WHERE " + " AND ".join(where) + \
              " ORDER BY product_name"
        params = params + search_params
        if limit:
            sql += " LIMIT ?"; params.append(limit)
        rows = db.fetchall(sql, tuple(params))
        return [Product.from_row(r) for r in rows]


    def get_by_id(self, product_id: int) -> Optional[Product]:
        db = get_db()
        row = db.fetchone("SELECT * FROM products WHERE id = ?", (product_id,))
        return Product.from_row(row) if row else None

    def _ensure_code_free(self, product: Product, exclude_id=None) -> str:
        """Kodu doğrular, boşlukları kırpar ve çakışma varsa hata fırlatır."""
        code = (product.product_code or "").strip()
        if not code:
            raise ValueError("Ürün kodu boş olamaz.")
        existing = self.get_by_code(code, exclude_id=exclude_id)
        if existing is not None:
            raise DuplicateProductCodeError(existing)
        return code

    def add(self, product: Product) -> int:
        code = self._ensure_code_free(product)
        if not (product.product_name or "").strip():
            raise ValueError("Ürün adı boş olamaz.")
        db = get_db()
        try:
            cursor = db.execute(
                """INSERT INTO products (product_code, product_name, description,
                   price, currency, stock, unit, category_id, cost_price)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (code, product.product_name, product.description,
                 product.price, product.currency, product.stock, product.unit,
                 product.category_id, product.cost_price))
        except sqlite3.IntegrityError as exc:
            raise self._duplicate_error(code, exc) from exc
        product.product_code = code
        return cursor.lastrowid

    def update(self, product: Product) -> None:
        code = self._ensure_code_free(product, exclude_id=product.id)
        db = get_db()
        try:
            db.execute(
                """UPDATE products SET product_code=?, product_name=?, description=?,
                   price=?, currency=?, stock=?, unit=?, category_id=?, cost_price=?
                   WHERE id=?""",
                (code, product.product_name, product.description,
                 product.price, product.currency, product.stock, product.unit,
                 product.category_id, product.cost_price, product.id))
        except sqlite3.IntegrityError as exc:
            raise self._duplicate_error(code, exc, exclude_id=product.id) from exc
        product.product_code = code

    def _duplicate_error(self, code: str, exc: Exception, exclude_id=None) -> ValueError:
        """DB'den gelen ham IntegrityError'ı anlaşılır uygulama hatasına çevirir.

        Yarış durumu: kontrol ile yazma arasında aynı kod eklenmiş olabilir.
        """
        logger.info("Ürün kodu çakışması (%r) veritabanı düzeyinde yakalandı: %s",
                    code, exc)
        existing = self.get_by_code(code, exclude_id=exclude_id)
        if existing is not None:
            return DuplicateProductCodeError(existing)
        return ValueError(f"Ürün kaydedilemedi — '{code}' kodu kullanılamıyor.")

    def delete(self, product_id: int) -> None:
        db = get_db()
        db.execute("DELETE FROM products WHERE id=?", (product_id,))

    def delete_many(self, product_ids: list) -> None:
        """Birden fazla ürünü TEK transaction'da siler — toplu silmede
        satır başına ayrı commit (yavaş) yerine tek diske-yazma."""
        ids = [i for i in (product_ids or []) if i is not None]
        if not ids:
            return
        db = get_db()
        with db.transaction() as conn:
            conn.executemany("DELETE FROM products WHERE id=?",
                             [(i,) for i in ids])

    def count(self, category_id: Optional[int] = -1, keyword: str = "") -> int:
        """Ürün sayısı — kategori ve/veya arama filtresiyle (limit'ten bağımsız
        toplam; 'X / Y gösteriliyor' bilgisi için)."""
        db = get_db()
        cat_sql, params = self._category_clause(category_id)
        where = []
        if cat_sql:
            where.append(cat_sql)
        if keyword:
            kw = f"%{keyword}%"
            where.append(
                "(product_code LIKE ? OR product_name LIKE ? OR description LIKE ?)")
            params += [kw, kw, kw]
        sql = "SELECT COUNT(*) as cnt FROM products"
        if where:
            sql += " WHERE " + " AND ".join(where)
        row = db.fetchone(sql, tuple(params))
        return row["cnt"] if row else 0
