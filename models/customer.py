"""Müşteri modeli."""
from dataclasses import dataclass
from typing import Optional


@dataclass
class Customer:
    """Müşteri veri modeli."""
    id: Optional[int] = None
    company_name: str = ""
    contact_person: str = ""
    address: str = ""
    phone: str = ""
    email: str = ""
    notes: str = ""

    @classmethod
    def from_row(cls, row):
        """Veritabanı satırından Customer nesnesi oluşturur."""
        if row is None:
            return None
        return cls(
            id=row["id"],
            company_name=row["company_name"],
            contact_person=row["contact_person"] or "",
            address=row["address"] or "",
            phone=row["phone"] or "",
            email=row["email"] or "",
            notes=(row["notes"] if "notes" in row.keys() else "") or "",
        )
