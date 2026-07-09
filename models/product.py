"""Ürün modeli."""
from dataclasses import dataclass
from typing import Optional


@dataclass
class Product:
    """Ürün veri modeli."""
    id: Optional[int] = None
    product_code: str = ""
    product_name: str = ""
    description: str = ""
    price: float = 0.0
    currency: str = "EUR"
    stock: float = 0.0
    unit: str = "Adet"
    category_id: Optional[int] = None

    @classmethod
    def from_row(cls, row):
        """Veritabanı satırından Product nesnesi oluşturur."""
        if row is None:
            return None
        d = dict(row)
        return cls(
            id=d["id"],
            product_code=d["product_code"],
            product_name=d["product_name"],
            description=d["description"] or "",
            price=d["price"],
            currency=d["currency"],
            stock=d["stock"],
            unit=d["unit"],
            category_id=d.get("category_id"),
        )
