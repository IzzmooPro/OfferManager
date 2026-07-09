"""Teklif şablon servis katmanı."""
import logging
from typing import List, Optional
from database.db_manager import get_db
from models.template import OfferTemplate, TemplateItem

logger = logging.getLogger("template_service")


class TemplateService:
    """Teklif şablonu CRUD işlemleri."""

    def get_all(self) -> List[OfferTemplate]:
        db = get_db()
        rows = db.fetchall(
            "SELECT * FROM offer_templates ORDER BY template_name")
        return [OfferTemplate.from_row(r) for r in rows]

    def get_by_id(self, template_id: int) -> Optional[OfferTemplate]:
        db = get_db()
        row = db.fetchone(
            "SELECT * FROM offer_templates WHERE id = ?", (template_id,))
        return OfferTemplate.from_row(row) if row else None

    def save(self, template: OfferTemplate) -> int:
        if not (template.template_name or "").strip():
            raise ValueError("Şablon adı boş olamaz.")
        if not template.items:
            raise ValueError("Şablon en az bir ürün içermelidir.")
        db = get_db()
        items_json = template.items_to_json()
        if template.id:
            db.execute(
                "UPDATE offer_templates SET template_name=?, currency=?, "
                "items_json=? WHERE id=?",
                (template.template_name.strip(), template.currency,
                 items_json, template.id))
            return template.id
        else:
            cursor = db.execute(
                "INSERT INTO offer_templates (template_name, currency, items_json) "
                "VALUES (?, ?, ?)",
                (template.template_name.strip(), template.currency, items_json))
            logger.info("Şablon kaydedildi: %s", template.template_name)
            return cursor.lastrowid

    def delete(self, template_id: int) -> None:
        db = get_db()
        db.execute("DELETE FROM offer_templates WHERE id=?", (template_id,))
        logger.info("Şablon silindi: id=%d", template_id)

    def rename(self, template_id: int, new_name: str) -> None:
        if not (new_name or "").strip():
            raise ValueError("Şablon adı boş olamaz.")
        db = get_db()
        db.execute(
            "UPDATE offer_templates SET template_name=? WHERE id=?",
            (new_name.strip(), template_id))

    def count(self) -> int:
        db = get_db()
        row = db.fetchone("SELECT COUNT(*) as cnt FROM offer_templates")
        return row["cnt"] if row else 0

    def create_from_offer(self, template_name: str, currency: str,
                          items: list) -> int:
        """Mevcut bir teklifin kalemlerinden şablon oluşturur."""
        template_items = []
        for item in items:
            template_items.append(TemplateItem(
                product_code=getattr(item, "product_code", "") or "",
                product_name=getattr(item, "product_name", "") or "",
                description=getattr(item, "description", "") or "",
                quantity=getattr(item, "quantity", 1.0),
                unit=getattr(item, "unit", "Adet") or "Adet",
                delivery_time=getattr(item, "delivery_time", "2-3 Hafta") or "2-3 Hafta",
                unit_price=getattr(item, "unit_price", 0.0),
            ))
        tmpl = OfferTemplate(
            template_name=template_name,
            currency=currency,
            items=template_items,
        )
        return self.save(tmpl)
