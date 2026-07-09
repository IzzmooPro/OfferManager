"""Teklif modeli."""
from dataclasses import dataclass, field
from typing import Optional, List
from models.offer_item import OfferItem


def calculate_discount(subtotal: float, discount_type: str,
                       discount_value: float) -> float:
    """KDV hariç ara toplam için parasal iskonto tutarını hesapla."""
    subtotal = float(subtotal or 0)
    value = float(discount_value or 0)
    kind = (discount_type or "amount").strip().lower()
    if value < 0:
        raise ValueError("İskonto değeri negatif olamaz.")
    if kind == "percent":
        if value > 100:
            raise ValueError("Yüzde iskonto 100'den fazla olamaz.")
        return round(subtotal * value / 100.0, 2)
    if kind == "amount":
        return round(value, 2)
    raise ValueError("İskonto türü yüzde veya sabit tutar olmalıdır.")


@dataclass
class Offer:
    """Teklif veri modeli — DB şemasıyla senkronize."""
    id: Optional[int] = None
    offer_no: str = ""
    customer_id: Optional[int] = None
    company_name: str = ""
    customer_address: str = ""
    contact_person: str = ""
    customer_phone: str = ""
    customer_email: str = ""
    date: str = ""
    currency: str = "EUR"
    total_amount: float = 0.0
    validity: str = ""
    validity_note: str = ""
    payment_term: str = ""
    status: str = "Beklemede"
    discount_amount: float = 0.0
    discount_type: str = "amount"
    discount_value: float = 0.0
    show_discount: bool = True
    items: List[OfferItem] = field(default_factory=list)

    @classmethod
    def from_row(cls, row):
        """Veritabanı satırından Offer nesnesi oluşturur."""
        if row is None:
            return None
        return cls(
            id=row["id"],
            offer_no=row["offer_no"],
            customer_id=row.get("customer_id"),
            company_name=row.get("company_name") or "",
            customer_address=row.get("customer_address") or "",
            contact_person=row.get("contact_person") or "",
            customer_phone=row.get("customer_phone") or "",
            customer_email=row.get("customer_email") or "",
            date=row["date"],
            currency=row["currency"],
            total_amount=row["total_amount"],
            validity=row.get("validity") or "",
            validity_note=row.get("validity_note") or "",
            payment_term=row.get("payment_term") or "",
            status=row.get("status") or "Beklemede",
            discount_amount=row.get("discount_amount") or 0.0,
            discount_type=row.get("discount_type") or "amount",
            discount_value=row.get("discount_value") or 0.0,
            show_discount=bool(row.get("show_discount", 1)),
        )
