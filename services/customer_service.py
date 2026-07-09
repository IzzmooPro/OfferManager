"""Müşteri servis katmanı."""
import logging
from typing import List, Optional
from database.db_manager import get_db
from models.customer import Customer

logger = logging.getLogger("customer_service")


class CustomerService:
    """Müşteri CRUD işlemleri."""

    def get_all(self) -> List[Customer]:
        db = get_db()
        rows = db.fetchall("SELECT * FROM customers ORDER BY company_name")
        return [Customer.from_row(r) for r in rows]

    def search(self, keyword: str) -> List[Customer]:
        db = get_db()
        kw = f"%{keyword}%"
        rows = db.fetchall(
            "SELECT * FROM customers WHERE company_name LIKE ? OR contact_person LIKE ? ORDER BY company_name",
            (kw, kw)
        )
        return [Customer.from_row(r) for r in rows]

    def get_by_id(self, customer_id: int) -> Optional[Customer]:
        db = get_db()
        row = db.fetchone("SELECT * FROM customers WHERE id = ?", (customer_id,))
        return Customer.from_row(row) if row else None

    def add(self, customer: Customer) -> int:
        if not (customer.company_name or "").strip():
            raise ValueError("Firma adı boş olamaz.")
        db = get_db()
        cursor = db.execute(
            """INSERT INTO customers (company_name, contact_person, address, phone, email, notes)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (customer.company_name, customer.contact_person, customer.address,
             customer.phone, customer.email, customer.notes)
        )
        return cursor.lastrowid

    def update(self, customer: Customer) -> None:
        db = get_db()
        db.execute(
            """UPDATE customers SET company_name=?, contact_person=?, address=?,
               phone=?, email=?, notes=? WHERE id=?""",
            (customer.company_name, customer.contact_person, customer.address,
             customer.phone, customer.email, customer.notes, customer.id)
        )

    def delete(self, customer_id: int) -> None:
        db = get_db()
        db.execute("DELETE FROM customers WHERE id=?", (customer_id,))

    def count(self) -> int:
        db = get_db()
        row = db.fetchone("SELECT COUNT(*) as cnt FROM customers")
        return row["cnt"] if row else 0
