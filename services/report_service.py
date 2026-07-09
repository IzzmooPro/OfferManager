"""Raporlama servis katmanı — analiz sorguları."""
import logging
from typing import List
from database.db_manager import get_db

logger = logging.getLogger("report_service")


class ReportService:
    """Detaylı raporlama sorguları."""

    def monthly_revenue(self, months: int = 12) -> List[dict]:
        """Son N ay için para birimi bazlı aylık ciro."""
        import datetime
        today = datetime.date.today()
        db = get_db()
        result = []
        for i in range(months - 1, -1, -1):
            y, m = today.year, today.month - i
            while m <= 0:
                m += 12
                y -= 1
            prefix = f"{y:04d}-{m:02d}"
            rows = db.fetchall(
                "SELECT currency, COALESCE(SUM(total_amount),0) as total "
                "FROM offers WHERE date LIKE ? "
                "AND COALESCE(status,'Beklemede')!='İptal' "
                "GROUP BY currency", (f"{prefix}%",))
            entry = {"month": f"{m:02d}/{y}"}
            for r in rows:
                if r["currency"]:
                    entry[r["currency"]] = r["total"]
            result.append(entry)
        return result

    def customer_ranking(self, limit: int = 20) -> List[dict]:
        """Müşteri bazlı ciro sıralaması."""
        db = get_db()
        rows = db.fetchall("""
            SELECT COALESCE(o.company_name, c.company_name, 'Bilinmeyen') as firma,
                   o.currency,
                   COUNT(*) as offer_count,
                   SUM(o.total_amount) as total_revenue,
                   SUM(CASE WHEN COALESCE(o.status,'Beklemede')='Onaylandı' THEN 1 ELSE 0 END) as approved,
                   MAX(o.date) as last_date
            FROM offers o
            LEFT JOIN customers c ON o.customer_id = c.id
            WHERE COALESCE(o.status,'Beklemede') != 'İptal'
            GROUP BY firma, o.currency
            ORDER BY total_revenue DESC
            LIMIT ?
        """, (limit,))
        return [{"company_name": r["firma"], "currency": r["currency"],
                 "offer_count": r["offer_count"], "total_revenue": r["total_revenue"],
                 "approved": r["approved"], "last_date": r["last_date"]}
                for r in rows]

    def product_ranking(self, limit: int = 20) -> List[dict]:
        """En çok teklif edilen ürünler."""
        db = get_db()
        rows = db.fetchall("""
            SELECT oi.product_code, oi.product_name,
                   COUNT(DISTINCT oi.offer_id) as offer_count,
                   SUM(oi.quantity) as total_qty,
                   SUM(oi.total_price) as total_revenue
            FROM offer_items oi
            JOIN offers o ON oi.offer_id = o.id
            WHERE COALESCE(o.status,'Beklemede') != 'İptal'
            GROUP BY oi.product_code, oi.product_name
            ORDER BY offer_count DESC
            LIMIT ?
        """, (limit,))
        return [dict(r) for r in rows]

    def conversion_rate(self) -> dict:
        """Teklif dönüşüm oranı."""
        db = get_db()
        row = db.fetchone("""
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN status='Onaylandı' THEN 1 ELSE 0 END) as approved,
                   SUM(CASE WHEN status='İptal' THEN 1 ELSE 0 END) as cancelled,
                   SUM(CASE WHEN COALESCE(status,'Beklemede')='Beklemede' THEN 1 ELSE 0 END) as pending
            FROM offers
        """)
        total = row["total"] if row else 0
        approved = row["approved"] if row else 0
        return {
            "total": total,
            "approved": approved,
            "cancelled": row["cancelled"] if row else 0,
            "pending": row["pending"] if row else 0,
            "rate": round(approved / total * 100, 1) if total > 0 else 0,
        }

    def average_offer_amount(self) -> dict:
        """Para birimi bazlı ortalama teklif tutarı."""
        db = get_db()
        rows = db.fetchall("""
            SELECT currency, AVG(total_amount) as avg_amount, COUNT(*) as cnt
            FROM offers
            WHERE COALESCE(status,'Beklemede') != 'İptal'
            GROUP BY currency
        """)
        return {r["currency"]: {"avg": round(r["avg_amount"], 2),
                                "count": r["cnt"]}
                for r in rows if r["currency"]}
