"""Ürün servis katmanı."""
import logging
from typing import List, Optional
from database.db_manager import get_db
from models.product import Product

logger = logging.getLogger("product_service")


class ProductService:
    """Ürün CRUD işlemleri."""

    def get_by_code(self, code: str) -> Optional[Product]:
        """Ürün kodu ile ara (büyük/küçük harf duyarsız). Yoksa None döner."""
        db = get_db()
        row = db.fetchone(
            "SELECT * FROM products WHERE UPPER(product_code) = UPPER(?)", (code,))
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

    def add(self, product: Product) -> int:
        if not (product.product_code or "").strip():
            raise ValueError("Ürün kodu boş olamaz.")
        if not (product.product_name or "").strip():
            raise ValueError("Ürün adı boş olamaz.")
        db = get_db()
        cursor = db.execute(
            """INSERT INTO products (product_code, product_name, description,
               price, currency, stock, unit, category_id, cost_price)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (product.product_code, product.product_name, product.description,
             product.price, product.currency, product.stock, product.unit,
             product.category_id, product.cost_price))
        return cursor.lastrowid

    def update(self, product: Product) -> None:
        db = get_db()
        db.execute(
            """UPDATE products SET product_code=?, product_name=?, description=?,
               price=?, currency=?, stock=?, unit=?, category_id=?, cost_price=?
               WHERE id=?""",
            (product.product_code, product.product_name, product.description,
             product.price, product.currency, product.stock, product.unit,
             product.category_id, product.cost_price, product.id))

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
