"""Ürün kategorisi modeli."""
from dataclasses import dataclass
from typing import Optional


@dataclass
class Category:
    """Ürün kategorisi veri modeli."""
    id: Optional[int] = None
    name: str = ""
    parent_id: Optional[int] = None
    sort_order: int = 0

    @classmethod
    def from_row(cls, row) -> Optional["Category"]:
        if row is None:
            return None
        d = dict(row)
        return cls(
            id=d["id"],
            name=d["name"],
            parent_id=d.get("parent_id"),
            sort_order=d.get("sort_order", 0),
        )
