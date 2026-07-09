"""Ürün kategorisi servis katmanı."""
import logging
from typing import List, Optional
from database.db_manager import get_db
from models.category import Category

logger = logging.getLogger("category_service")


class CategoryService:
    """Ürün kategorisi CRUD işlemleri."""

    def get_all(self) -> List[Category]:
        db = get_db()
        rows = db.fetchall(
            "SELECT * FROM product_categories ORDER BY sort_order, name")
        return [Category.from_row(r) for r in rows]

    def get_by_id(self, category_id: int) -> Optional[Category]:
        db = get_db()
        row = db.fetchone(
            "SELECT * FROM product_categories WHERE id = ?", (category_id,))
        return Category.from_row(row) if row else None

    def add(self, category: Category) -> int:
        if not (category.name or "").strip():
            raise ValueError("Kategori adı boş olamaz.")
        db = get_db()
        cursor = db.execute(
            "INSERT INTO product_categories (name, parent_id, sort_order) "
            "VALUES (?, ?, ?)",
            (category.name.strip(), category.parent_id, category.sort_order))
        logger.info("Kategori eklendi: %s", category.name)
        return cursor.lastrowid

    def update(self, category: Category) -> None:
        if not (category.name or "").strip():
            raise ValueError("Kategori adı boş olamaz.")
        db = get_db()
        db.execute(
            "UPDATE product_categories SET name=?, parent_id=?, sort_order=? "
            "WHERE id=?",
            (category.name.strip(), category.parent_id,
             category.sort_order, category.id))

    def delete(self, category_id: int) -> None:
        db = get_db()
        with db.transaction() as conn:
            conn.execute(
                "UPDATE products SET category_id=NULL WHERE category_id=?",
                (category_id,))
            conn.execute(
                "UPDATE product_categories SET parent_id=NULL WHERE parent_id=?",
                (category_id,))
            conn.execute(
                "DELETE FROM product_categories WHERE id=?", (category_id,))
        logger.info("Kategori silindi: id=%d", category_id)

    def count(self) -> int:
        db = get_db()
        row = db.fetchone(
            "SELECT COUNT(*) as cnt FROM product_categories")
        return row["cnt"] if row else 0

    def get_products_by_category(self, category_id: Optional[int]) -> list:
        """Belirli kategorideki ürünleri döndürür. None → kategorisiz ürünler."""
        from models.product import Product
        db = get_db()
        if category_id is None:
            rows = db.fetchall(
                "SELECT * FROM products WHERE category_id IS NULL "
                "ORDER BY product_name")
        else:
            rows = db.fetchall(
                "SELECT * FROM products WHERE category_id = ? "
                "ORDER BY product_name", (category_id,))
        return [Product.from_row(r) for r in rows]
