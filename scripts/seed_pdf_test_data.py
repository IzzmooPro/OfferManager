"""PDF denemeleri için 10 tam müşteri, 20 ürün ve 10 teklif oluşturur."""
from datetime import date, timedelta
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database.db_manager import get_db
from services.offer_service import OfferService


CUSTOMERS = [
    ("Atlas Endüstriyel Çözümler A.Ş.", "Ahmet Yılmaz", "İkitelli OSB Mah. Metal İş Sanayi Sitesi No:12 Başakşehir / İstanbul", "0212 555 10 01", "ahmet.yilmaz@atlas-test.com"),
    ("Marmara Makine Sanayi Ltd. Şti.", "Zeynep Kaya", "Minareliçavuş OSB Mah. 105. Sokak No:8 Nilüfer / Bursa", "0224 555 20 02", "zeynep.kaya@marmara-test.com"),
    ("Ege Proses Teknolojileri A.Ş.", "Mehmet Demir", "Atatürk OSB Mah. 10001 Sokak No:25 Çiğli / İzmir", "0232 555 30 03", "mehmet.demir@egeproses-test.com"),
    ("Anadolu Otomasyon Sistemleri Ltd.", "Elif Şahin", "Ostim OSB Mah. 1234. Cadde No:16 Yenimahalle / Ankara", "0312 555 40 04", "elif.sahin@anadolu-test.com"),
    ("Akdeniz Gıda Ekipmanları A.Ş.", "Burak Çelik", "Antalya OSB 2. Kısım Mah. 21. Cadde No:7 Döşemealtı / Antalya", "0242 555 50 05", "burak.celik@akdeniz-test.com"),
    ("Karadeniz Enerji Çözümleri Ltd.", "Selin Aydın", "Arsin OSB Mah. Sanayi Caddesi No:34 Arsin / Trabzon", "0462 555 60 06", "selin.aydin@karadeniz-test.com"),
    ("Trakya Ambalaj Üretim A.Ş.", "Can Öztürk", "Velimeşe OSB Mah. 114. Sokak No:19 Ergene / Tekirdağ", "0282 555 70 07", "can.ozturk@trakya-test.com"),
    ("Güneydoğu Pompa ve Vana Ltd.", "Derya Arslan", "2. OSB Mah. 83201 Cadde No:41 Şehitkamil / Gaziantep", "0342 555 80 08", "derya.arslan@guneydogu-test.com"),
    ("İç Anadolu Kimya Sistemleri A.Ş.", "Emre Koç", "Konya OSB Mah. Büyük Kayacık Caddesi No:52 Selçuklu / Konya", "0332 555 90 09", "emre.koc@icanadolu-test.com"),
    ("Boğaziçi Teknik Malzeme Ltd. Şti.", "Ayşe Kurt", "Dudullu OSB Mah. Nato Yolu Caddesi No:63 Ümraniye / İstanbul", "0216 555 00 10", "ayse.kurt@bogazici-test.com"),
]

CURRENCIES = ["TL", "EUR", "USD", "TL", "EUR", "USD", "TL", "EUR", "USD", "TL"]
VALIDITIES = ["30 Gün", "45 Gün", "60 Gün", "10 Gün", "90 Gün", "45 Gün", "3 Ay", "30 Gün", "90 Gün", "31.12.2026"]
PAYMENTS = ["Peşin", "30 Gün Vadeli", "Sipariş Avansı %30", "45 Gün Vadeli", "Sipariş Avansı %50", "60 Gün Vadeli", "Peşin", "30 Gün Vadeli", "Akreditif", "45 Gün Vadeli"]
STATUSES = ["Beklemede", "Onaylandı", "Beklemede", "Onaylandı", "Beklemede", "Beklemede", "Onaylandı", "Beklemede", "Onaylandı", "Beklemede"]
UNITS = ["Adet", "Set", "Adet", "Paket", "Kutu", "Takım", "Adet", "Set", "Adet", "Kutu"]


def seed():
    db = get_db()
    offer_service = OfferService()
    created = []
    with db.transaction(exclusive=True) as conn:
        existing = conn.execute(
            "SELECT COUNT(*) FROM offers WHERE company_name LIKE 'PDF Test Müşteri %'"
        ).fetchone()[0]
        if existing:
            raise RuntimeError(f"{existing} PDF test teklifi zaten mevcut; tekrar eklenmedi.")

        for i, (company, contact, address, phone, email) in enumerate(CUSTOMERS, 1):
            display_company = f"PDF Test Müşteri {i:02d} — {company}"
            customer_id = conn.execute(
                "INSERT INTO customers(company_name,contact_person,address,phone,email) VALUES(?,?,?,?,?)",
                (display_company, contact, address, phone, email),
            ).lastrowid
            currency = CURRENCIES[i - 1]
            specs = [
                (f"PDFTEST-{i:02d}-A", f"Endüstriyel Test Ürünü {i:02d}-A", f"Paslanmaz gövdeli, yüksek performanslı test ürünü; model {i:02d}A.", 850.0 + i * 137.5, UNITS[i - 1], 12 + i),
                (f"PDFTEST-{i:02d}-B", f"Yardımcı Ekipman Seti {i:02d}-B", "Montaj aksesuarları, bağlantı elemanları ve kullanım dokümanları dahil komple set.", 420.0 + i * 83.25, "Set", 8 + i),
            ]
            products = []
            for code, name, description, price, unit, stock in specs:
                product_id = conn.execute(
                    "INSERT INTO products(product_code,product_name,description,price,currency,stock,unit) VALUES(?,?,?,?,?,?,?)",
                    (code, name, description, price, currency, stock, unit),
                ).lastrowid
                products.append((product_id, code, name, description, price, unit))

            quantities = (i % 4 + 1, (i + 1) % 3 + 1)
            subtotal = sum(quantities[j] * products[j][4] for j in range(2))
            discount = round(subtotal * (0.05 if i % 2 == 0 else 0.03), 2)
            total = round(subtotal - discount, 2)
            offer_no = offer_service.generate_and_commit_offer_no(conn)
            offer_id = conn.execute(
                """INSERT INTO offers(offer_no,customer_id,company_name,customer_address,contact_person,
                customer_phone,customer_email,date,currency,total_amount,validity,validity_note,payment_term,status,discount_amount)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (offer_no, customer_id, display_company, address, contact, phone, email,
                 (date(2026, 6, 1) + timedelta(days=i)).isoformat(), currency, total,
                 VALIDITIES[i - 1], "Fiyatlar teklif geçerlilik süresi boyunca sabittir.",
                 PAYMENTS[i - 1], STATUSES[i - 1], discount),
            ).lastrowid

            for j, (product_id, code, name, description, price, unit) in enumerate(products):
                quantity = quantities[j]
                conn.execute(
                    """INSERT INTO offer_items(offer_id,product_id,product_code,product_name,description,
                    quantity,unit,delivery_time,unit_price,total_price) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                    (offer_id, product_id, code, name, description, quantity, unit,
                     "Stokta Var" if j == 0 else f"{i + 1} Hafta", price, round(quantity * price, 2)),
                )
            created.append((offer_id, offer_no, display_company))
    return created


if __name__ == "__main__":
    for row in seed():
        print(" | ".join(map(str, row)))
