"""Teklif şablonu modeli."""
import json
from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class TemplateItem:
    """Şablon kalemi — ürün bilgisi + varsayılan miktar/fiyat."""
    product_code: str = ""
    product_name: str = ""
    description: str = ""
    quantity: float = 1.0
    unit: str = "Adet"
    delivery_time: str = "2-3 Hafta"
    unit_price: float = 0.0


@dataclass
class OfferTemplate:
    """Teklif şablonu — sık kullanılan ürün kombinasyonları."""
    id: Optional[int] = None
    template_name: str = ""
    currency: str = "EUR"
    items: List[TemplateItem] = field(default_factory=list)
    created_at: str = ""

    def items_to_json(self) -> str:
        return json.dumps(
            [vars(item) for item in self.items],
            ensure_ascii=False,
        )

    @staticmethod
    def items_from_json(data: str) -> List[TemplateItem]:
        try:
            raw_list = json.loads(data)
        except (json.JSONDecodeError, TypeError):
            return []
        result = []
        valid_fields = {f.name for f in TemplateItem.__dataclass_fields__.values()}
        for raw in raw_list:
            if not isinstance(raw, dict):
                continue
            filtered = {k: v for k, v in raw.items() if k in valid_fields}
            result.append(TemplateItem(**filtered))
        return result

    @classmethod
    def from_row(cls, row) -> Optional["OfferTemplate"]:
        if row is None:
            return None
        d = dict(row)
        tmpl = cls(
            id=d["id"],
            template_name=d["template_name"],
            currency=d["currency"],
            created_at=d.get("created_at", ""),
        )
        tmpl.items = cls.items_from_json(d.get("items_json", "[]"))
        return tmpl
