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

    def get_all(self, category_id: Optional[int] = -1) -> List[Product]:
        """Tüm ürünleri döndürür. category_id verilirse kategoriye göre filtreler.
        -1 = filtre yok, None = kategorisiz ürünler."""
        db = get_db()
        if category_id == -1:
            rows = db.fetchall("SELECT * FROM products ORDER BY product_name")
        elif category_id is None:
            rows = db.fetchall(
                "SELECT * FROM products WHERE category_id IS NULL "
                "ORDER BY product_name")
        else:
            rows = db.fetchall(
                "SELECT * FROM products WHERE category_id = ? "
                "ORDER BY product_name", (category_id,))
        return [Product.from_row(r) for r in rows]

    def search(self, keyword: str, category_id: Optional[int] = -1) -> List[Product]:
        """Kod, ad veya açıklamaya göre ara (büyük/küçük harf duyarsız).
        category_id ile kategoriye göre de filtreler."""
        db = get_db()
        kw = f"%{keyword}%"
        if category_id == -1:
            rows = db.fetchall(
                """SELECT * FROM products
                   WHERE product_code LIKE ? OR product_name LIKE ? OR description LIKE ?
                   ORDER BY product_name""",
                (kw, kw, kw))
        elif category_id is None:
            rows = db.fetchall(
                """SELECT * FROM products
                   WHERE category_id IS NULL
                     AND (product_code LIKE ? OR product_name LIKE ? OR description LIKE ?)
                   ORDER BY product_name""",
                (kw, kw, kw))
        else:
            rows = db.fetchall(
                """SELECT * FROM products
                   WHERE category_id = ?
                     AND (product_code LIKE ? OR product_name LIKE ? OR description LIKE ?)
                   ORDER BY product_name""",
                (category_id, kw, kw, kw))
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

    def count(self) -> int:
        db = get_db()
        row = db.fetchone("SELECT COUNT(*) as cnt FROM products")
        return row["cnt"] if row else 0
