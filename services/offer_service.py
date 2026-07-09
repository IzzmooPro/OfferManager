"""Teklif servis katmanı."""
import datetime, logging
from core.app_paths import PDF_DIR
from typing import List, Optional
from database.db_manager import get_db
from models.offer import Offer, calculate_discount
from models.offer_item import OfferItem
from core.date_utils import to_storage_date

logger = logging.getLogger("offer_service")


def _get_offer_prefix() -> str:
    from core.config import load_company_config
    return load_company_config().get("offer_prefix", "SNS") or "SNS"





class OfferService:
    def preview_offer_no(self) -> str:
        """Yeni teklif numarası tahmin et — sayacı GÜNCELLEMEZ (sadece arayüzde göstermek için)."""
        db = get_db()
        prefix = _get_offer_prefix()
        row = db.fetchone("SELECT last_number FROM offer_counter WHERE year = 0")
        if row:
            next_num = row["last_number"] + 1
        else:
            max_row = db.fetchone("SELECT MAX(id) as max_id FROM offers")
            next_num = (max_row["max_id"] or 0) + 1 if max_row else 1
        return f"{prefix}-{next_num:06d}"

    def generate_and_commit_offer_no(self, conn) -> str:
        """Yeni numarayı üret ve sayacı GÜNCELLE. (Sadece veritabanına kayıt sırasında çağrılır)."""
        prefix = _get_offer_prefix()
        row = conn.execute("SELECT last_number FROM offer_counter WHERE year = 0").fetchone()
        if row:
            next_num = row["last_number"] + 1
            conn.execute("UPDATE offer_counter SET last_number=? WHERE year=0", (next_num,))
        else:
            max_row = conn.execute("SELECT MAX(id) as max_id FROM offers").fetchone()
            next_num = (max_row["max_id"] or 0) + 1 if max_row else 1
            conn.execute("DELETE FROM offer_counter")
            conn.execute("INSERT INTO offer_counter (year, last_number) VALUES (0, ?)", (next_num,))
        return f"{prefix}-{next_num:06d}"

    def get_all(self) -> List[Offer]:
        db = get_db()
        rows = db.fetchall("""
            SELECT o.*,
                   COALESCE(o.company_name, c.company_name, '') AS company_name,
                   COALESCE(o.customer_address, c.address,  '') AS customer_address,
                   COALESCE(o.contact_person,  c.contact_person, '') AS contact_person
            FROM offers o
            LEFT JOIN customers c ON o.customer_id = c.id
            ORDER BY o.id DESC
        """)
        return [Offer.from_row(dict(r)) for r in rows]

    def get_recent(self, limit=10) -> List[Offer]:
        db = get_db()
        rows = db.fetchall("""
            SELECT o.*,
                   COALESCE(o.company_name, c.company_name, '') AS company_name
            FROM offers o
            LEFT JOIN customers c ON o.customer_id = c.id
            ORDER BY o.id DESC LIMIT ?
        """, (limit,))
        return [Offer.from_row(dict(r)) for r in rows]

    def get_by_id(self, offer_id: int) -> Optional[Offer]:
        db = get_db()
        row = db.fetchone("""
            SELECT o.*,
                   COALESCE(o.company_name, c.company_name, '') AS company_name,
                   COALESCE(o.customer_address, c.address,  '') AS customer_address,
                   COALESCE(o.contact_person,  c.contact_person, '') AS contact_person
            FROM offers o
            LEFT JOIN customers c ON o.customer_id = c.id
            WHERE o.id = ?
        """, (offer_id,))
        if not row: return None
        offer = Offer.from_row(dict(row))
        items = db.fetchall("SELECT * FROM offer_items WHERE offer_id=? ORDER BY id", (offer_id,))
        offer.items = [OfferItem.from_row(dict(i)) for i in items]
        return offer

    def save(self, offer: Offer, keep_offer_no: bool = False) -> int:
        """Teklif ve kalemlerini atomik olarak kaydet — hata olursa tümü geri alınır.

        keep_offer_no=True: yeni teklifte offer.offer_no doluysa numara
        üretilmez, verilen numara korunur (Excel içe aktarma için).
        """
        if not offer.customer_id and not (offer.company_name or "").strip():
            raise ValueError("Teklif için müşteri seçilmeli veya firma adı girilmelidir.")
        if not offer.items:
            raise ValueError("Teklif en az bir ürün içermelidir.")
        if any(item.quantity <= 0 for item in offer.items):
            raise ValueError("Ürün miktarı sıfırdan büyük olmalıdır.")
        if any(item.unit_price < 0 or item.total_price < 0 for item in offer.items):
            raise ValueError("Ürün fiyatı negatif olamaz.")

        subtotal = sum(item.total_price for item in offer.items)
        discount_type = (offer.discount_type or "amount").strip().lower()
        discount_value = float(offer.discount_value or 0)
        if discount_type == "amount" and discount_value == 0:
            # Eski çağrılar yalnız discount_amount gönderiyordu.
            discount_value = float(offer.discount_amount or 0)
        discount = calculate_discount(subtotal, discount_type, discount_value)

        if discount > subtotal:
            raise ValueError("İskonto, ürünler toplamından fazla olamaz.")
        offer.discount_type = discount_type
        offer.discount_value = discount_value
        offer.discount_amount = discount
        offer.show_discount = bool(offer.show_discount)
        expected_total = subtotal - discount
        if abs(float(offer.total_amount or 0) - expected_total) > 0.01:
            raise ValueError("Teklif toplamı ürün kalemleriyle uyuşmuyor.")

        offer.date = to_storage_date(offer.date)
        db = get_db()
        offer_id = offer.id

        # Yeni teklif → sayaç güncellemesi için EXCLUSIVE kilit (race condition önlemi)
        with db.transaction(exclusive=not bool(offer_id)) as conn:
            if offer_id:
                conn.execute("""
                    UPDATE offers SET
                      customer_id=?, company_name=?, customer_address=?, contact_person=?,
                      customer_phone=?, customer_email=?,
                      date=?, currency=?, total_amount=?,
                      validity=?, validity_note=?, payment_term=?, status=?, discount_amount=?,
                      discount_type=?, discount_value=?, show_discount=?
                    WHERE id=?
                """, (offer.customer_id, offer.company_name, offer.customer_address, offer.contact_person,
                      offer.customer_phone, offer.customer_email,
                      offer.date, offer.currency, offer.total_amount,
                      offer.validity, offer.validity_note, offer.payment_term, offer.status,
                      offer.discount_amount, offer.discount_type, offer.discount_value,
                      int(offer.show_discount), offer_id))
                conn.execute("DELETE FROM offer_items WHERE offer_id=?", (offer_id,))
            else:
                if keep_offer_no and (offer.offer_no or "").strip():
                    offer.offer_no = offer.offer_no.strip()
                else:
                    offer.offer_no = self.generate_and_commit_offer_no(conn)
                
                cursor = conn.execute("""
                    INSERT INTO offers
                      (offer_no, customer_id, company_name, customer_address, contact_person,
                       customer_phone, customer_email,
                       date, currency, total_amount, validity, validity_note, payment_term, status,
                       discount_amount, discount_type, discount_value, show_discount)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (offer.offer_no, offer.customer_id, offer.company_name, offer.customer_address, offer.contact_person,
                      offer.customer_phone, offer.customer_email,
                      offer.date, offer.currency, offer.total_amount,
                      offer.validity, offer.validity_note, offer.payment_term, offer.status,
                      offer.discount_amount, offer.discount_type, offer.discount_value,
                      int(offer.show_discount)))
                offer_id = cursor.lastrowid

            for item in offer.items:
                conn.execute("""
                    INSERT INTO offer_items
                      (offer_id, product_id, product_code, product_name, description,
                       quantity, unit, delivery_time, unit_price, total_price)
                    VALUES (?,?,?,?,?,?,?,?,?,?)
                """, (offer_id, item.product_id, item.product_code,
                      item.product_name, item.description,
                      item.quantity, item.unit,
                      item.delivery_time,
                      item.unit_price, item.total_price))

        logger.info("Teklif kaydedildi: id=%d, no=%s", offer_id, offer.offer_no)
        return offer_id

    def update_status(self, offer_id: int, status: str) -> None:
        """Teklif durumunu güncelle: Beklemede / Onaylandı / İptal."""
        db = get_db()
        db.execute("UPDATE offers SET status=? WHERE id=?", (status, offer_id))
        logger.info("Teklif durumu güncellendi: id=%d → %s", offer_id, status)

    def delete(self, offer_id: int) -> None:
        """Teklifi sil — DB kaydı + varsa PDF dosyası."""
        db = get_db()
        # PDF dosyasını sil (offer_no gerekli — önce al)
        row = db.fetchone("SELECT offer_no FROM offers WHERE id=?", (offer_id,))
        if row:
            pdf_path = PDF_DIR / f"{row['offer_no']}.pdf"
            try:
                if pdf_path.exists():
                    pdf_path.unlink()
                    logger.info("PDF silindi: %s", pdf_path.name)
            except Exception as e:
                logger.warning("PDF silinemedi: %s", e)
        with db.transaction() as conn:
            conn.execute("DELETE FROM offer_items WHERE offer_id=?", (offer_id,))
            conn.execute("DELETE FROM offers WHERE id=?", (offer_id,))


    def get_by_date_range(self, date_from: str, date_to: str) -> List[Offer]:
        """Tarih aralığına göre teklifler. Format: YYYY-MM-DD"""
        db = get_db()
        rows = db.fetchall("""
            SELECT o.*,
                   COALESCE(o.company_name, c.company_name, '') AS company_name
            FROM offers o
            LEFT JOIN customers c ON o.customer_id = c.id
            WHERE o.date >= ? AND o.date <= ?
            ORDER BY o.date DESC
        """, (date_from, date_to))
        return [Offer.from_row(dict(r)) for r in rows]

    def get_by_customer(self, customer_id: int) -> List[Offer]:
        """Müşteriye ait tüm teklifler."""
        db = get_db()
        rows = db.fetchall("""
            SELECT o.*,
                   COALESCE(o.company_name, c.company_name, '') AS company_name
            FROM offers o
            LEFT JOIN customers c ON o.customer_id = c.id
            WHERE o.customer_id = ?
            ORDER BY o.id DESC
        """, (customer_id,))
        return [Offer.from_row(dict(r)) for r in rows]

    def count(self) -> int:
        row = get_db().fetchone("SELECT COUNT(*) as cnt FROM offers")
        return row["cnt"] if row else 0

    def get_expiring_offers(self, days: int = 3) -> List[Offer]:
        """Geçerlilik süresi 'days' gün içinde dolacak veya dolmuş Beklemede teklifler."""
        import re
        all_pending = self.get_filtered(status="Beklemede")
        today = datetime.date.today()
        result = []
        for o in all_pending:
            validity = (o.validity or "").strip()
            match = re.fullmatch(r"(\d+)\s*(?:g[üu]n|ay)?", validity, flags=re.IGNORECASE)
            if not match:
                continue
            try:
                offer_date = datetime.date.fromisoformat(o.date)
            except (ValueError, TypeError):
                continue
            validity_days = int(match.group(1))
            if "ay" in validity.lower():
                validity_days *= 30
            expiry_date = offer_date + datetime.timedelta(days=validity_days)
            remaining = (expiry_date - today).days
            o._expiry_date = expiry_date
            o._remaining_days = remaining
            if remaining <= days:
                result.append(o)
        return result

    def auto_cancel_expired(self) -> List[str]:
        """Geçerlilik süresi dolan 'Beklemede' teklifleri otomatik İptal eder.

        Yalnızca Beklemede olanlar etkilenir (Onaylandı dokunulmaz);
        geçerliliği çözümlenemeyen teklifler atlanır.
        İptal edilen tekliflerin numaralarını döndürür.
        """
        expired = [o for o in self.get_expiring_offers(days=-1)
                   if getattr(o, "_remaining_days", 0) < 0]
        cancelled = []
        for o in expired:
            try:
                self.update_status(o.id, "İptal")
                cancelled.append(o.offer_no or f"#{o.id}")
            except Exception as e:
                logger.warning("Süresi dolan teklif iptal edilemedi (id=%s): %s",
                               o.id, e)
        if cancelled:
            logger.info("Süresi dolan %d teklif otomatik İptal edildi: %s",
                        len(cancelled), ", ".join(cancelled))
        return cancelled

    def get_all_customer_summaries(self) -> dict:
        """Tüm müşterilerin özet istatistiklerini tek sorguda çeker. {customer_id: summary}"""
        db = get_db()
        rows = db.fetchall("""
            SELECT customer_id,
                   COUNT(*) as total,
                   MAX(date) as last_date
            FROM offers
            WHERE customer_id IS NOT NULL
            GROUP BY customer_id
        """)
        result = {}
        for r in rows:
            cid = r["customer_id"]
            result[cid] = {
                "total": r["total"],
                "last_date": r["last_date"] or "",
            }
        return result

    def get_customer_summary(self, customer_id: int) -> dict:
        """Müşteri bazlı özet istatistik."""
        db = get_db()
        total_row = db.fetchone(
            "SELECT COUNT(*) as cnt FROM offers WHERE customer_id=?",
            (customer_id,))
        total = total_row["cnt"] if total_row else 0

        status_rows = db.fetchall(
            "SELECT COALESCE(status,'Beklemede') as status, COUNT(*) as cnt "
            "FROM offers WHERE customer_id=? "
            "GROUP BY COALESCE(status,'Beklemede')", (customer_id,))
        statuses = {r["status"]: r["cnt"] for r in status_rows}

        revenue_rows = db.fetchall(
            "SELECT currency, COALESCE(SUM(total_amount),0) as total "
            "FROM offers WHERE customer_id=? AND COALESCE(status,'Beklemede')!='İptal' "
            "GROUP BY currency", (customer_id,))
        revenue = {r["currency"]: r["total"] for r in revenue_rows if r["currency"]}

        last_row = db.fetchone(
            "SELECT date FROM offers WHERE customer_id=? ORDER BY date DESC LIMIT 1",
            (customer_id,))
        last_date = last_row["date"] if last_row else ""

        return {
            "total": total,
            "statuses": statuses,
            "revenue": revenue,
            "last_date": last_date,
        }

    def get_status_counts(self) -> dict:
        """Durum bazlı teklif sayıları — GROUP BY, Python döngüsü yok."""
        db   = get_db()
        rows = db.fetchall(
            "SELECT COALESCE(status,'Beklemede') as status, COUNT(*) as cnt "
            "FROM offers GROUP BY COALESCE(status,'Beklemede')"
        )
        result = {s: 0 for s in ["Beklemede", "Onaylandı", "İptal"]}
        for row in rows:
            st = row["status"]
            if st in result:
                result[st] = row["cnt"]
        return result

    def get_filtered(self, keyword: str = "", status: str = "Tümü",
                     date_from: str = "", date_to: str = "",
                     currency: str = "", amount_min: float = 0,
                     amount_max: float = 0) -> List[Offer]:
        """SQL tarafında filtreli teklif listesi — Python filtresi yok."""
        db         = get_db()
        conditions: list = []
        params:     list = []

        if keyword:
            like = f"%{keyword}%"
            conditions.append(
                "(o.offer_no LIKE ? "
                "OR COALESCE(o.company_name, c.company_name, '') LIKE ?)"
            )
            params.extend([like, like])

        if status and status != "Tümü":
            conditions.append("COALESCE(o.status,'Beklemede') = ?")
            params.append(status)

        if date_from:
            conditions.append("o.date >= ?")
            params.append(date_from)
        if date_to:
            conditions.append("o.date <= ?")
            params.append(date_to)
        if currency and currency != "Tümü":
            conditions.append("o.currency = ?")
            params.append(currency)
        if amount_min > 0:
            conditions.append("o.total_amount >= ?")
            params.append(amount_min)
        if amount_max > 0:
            conditions.append("o.total_amount <= ?")
            params.append(amount_max)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        sql   = f"""
            SELECT o.*,
                   COALESCE(o.company_name, c.company_name, '')  AS company_name,
                   COALESCE(o.customer_address, c.address,  '')  AS customer_address,
                   COALESCE(o.contact_person,  c.contact_person,'') AS contact_person
            FROM offers o
            LEFT JOIN customers c ON o.customer_id = c.id
            {where}
            ORDER BY o.id DESC
        """
        rows = db.fetchall(sql, tuple(params))
        return [Offer.from_row(dict(r)) for r in rows]

    def get_revenue_summary(self) -> dict:
        """Bu ay ve bu yıl para birimi bazlı ciro (iptal hariç)."""
        import datetime
        today      = datetime.date.today()
        this_month = today.strftime("%Y-%m")
        this_year  = today.strftime("%Y")
        db         = get_db()

        def _fetch(prefix: str) -> dict:
            rows = db.fetchall(
                "SELECT currency, COALESCE(SUM(total_amount),0) AS total "
                "FROM offers "
                "WHERE date LIKE ? AND COALESCE(status,'Beklemede') != 'İptal' "
                "GROUP BY currency",
                (f"{prefix}%",),
            )
            return {r["currency"]: r["total"] for r in rows if r["currency"]}

        return {"monthly": _fetch(this_month), "yearly": _fetch(this_year)}

    def get_monthly_stats(self, months: int = 12) -> List[dict]:
        """Son N ay için aylık teklif sayısı ve ciro. [{month, count, revenue}]"""
        today = datetime.date.today()
        db = get_db()
        result = []
        for i in range(months - 1, -1, -1):
            y = today.year
            m = today.month - i
            while m <= 0:
                m += 12
                y -= 1
            prefix = f"{y:04d}-{m:02d}"
            label = f"{m:02d}/{y}"
            row = db.fetchone(
                "SELECT COUNT(*) as cnt, COALESCE(SUM(total_amount),0) as total "
                "FROM offers WHERE date LIKE ? AND COALESCE(status,'Beklemede')!='İptal'",
                (f"{prefix}%",))
            result.append({
                "month": label,
                "count": row["cnt"] if row else 0,
                "revenue": row["total"] if row else 0,
            })
        return result

    def get_top_customers(self, limit: int = 10) -> List[dict]:
        """En çok ciro yapılan müşteriler. [{company_name, total, count}]"""
        db = get_db()
        rows = db.fetchall("""
            SELECT COALESCE(o.company_name, c.company_name, 'Bilinmeyen') as company_name,
                   SUM(o.total_amount) as total, COUNT(*) as cnt
            FROM offers o
            LEFT JOIN customers c ON o.customer_id = c.id
            WHERE COALESCE(o.status,'Beklemede') != 'İptal'
            GROUP BY company_name
            ORDER BY total DESC
            LIMIT ?
        """, (limit,))
        return [{"company_name": r["company_name"], "total": r["total"],
                 "count": r["cnt"]} for r in rows]
