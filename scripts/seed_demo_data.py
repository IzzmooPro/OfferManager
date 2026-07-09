"""
Demo verisi — 10 gerçekçi müşteri, 20 ürün ve 10 farklı senaryoda teklif oluşturur.
Doğrudan uygulamanın AppData DB'sine yazar.

Kullanım:
    python scripts/seed_demo_data.py
"""
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database.db_manager import get_db
from services.customer_service import CustomerService
from services.product_service import ProductService
from services.offer_service import OfferService
from services.category_service import CategoryService
from models.customer import Customer
from models.product import Product
from models.category import Category
from models.offer import Offer
from models.offer_item import OfferItem

db = get_db()
csvc = CustomerService()
psvc = ProductService()
osvc = OfferService()
catsvc = CategoryService()

# ═══════════════════════════════════════════════════════════════════════════
# KATEGORİLER
# ═══════════════════════════════════════════════════════════════════════════
print("Kategoriler oluşturuluyor...")
categories = {}
for name in ["Pompalar", "Vanalar", "Sensörler", "Filtreler", "Otomasyon"]:
    try:
        cid = catsvc.add(Category(name=name))
        categories[name] = cid
        print(f"  + {name} (id={cid})")
    except Exception:
        print(f"  ~ {name} zaten var, atlanıyor")

# ═══════════════════════════════════════════════════════════════════════════
# MÜŞTERİLER
# ═══════════════════════════════════════════════════════════════════════════
print("\nMüşteriler oluşturuluyor...")
customers_data = [
    ("Atlas Endüstriyel Çözümler A.Ş.", "Ahmet Yılmaz",
     "İkitelli OSB Mah. Metal İş Sanayi Sitesi No:12 Başakşehir / İstanbul",
     "0212 555 10 01", "ahmet.yilmaz@atlas-endustri.com.tr",
     "Büyük sanayi müşterisi, aylık düzenli sipariş"),
    ("Marmara Makine Sanayi Ltd. Şti.", "Zeynep Kaya",
     "Minareliçavuş OSB Mah. 105. Sokak No:8 Nilüfer / Bursa",
     "0224 555 20 02", "zeynep.kaya@marmara-makine.com",
     "Bursa bölgesi ana bayii"),
    ("Ege Proses Teknolojileri A.Ş.", "Mehmet Demir",
     "Atatürk OSB Mah. 10001 Sokak No:25 Çiğli / İzmir",
     "0232 555 30 03", "mehmet.demir@egeproses.com.tr",
     "Gıda sektörü ekipman tedarikçisi"),
    ("Anadolu Otomasyon Sistemleri Ltd.", "Elif Şahin",
     "Ostim OSB Mah. 1234. Cadde No:16 Yenimahalle / Ankara",
     "0312 555 40 04", "elif.sahin@anadolu-otomasyon.com",
     "PLC ve SCADA projeleri"),
    ("Akdeniz Gıda Ekipmanları A.Ş.", "Burak Çelik",
     "Antalya OSB 2. Kısım Mah. 21. Cadde No:7 Döşemealtı / Antalya",
     "0242 555 50 05", "burak.celik@akdeniz-gida.com",
     "Mevsimsel sipariş, yaz dönemi yoğun"),
    ("Karadeniz Enerji Çözümleri Ltd.", "Selin Aydın",
     "Arsin OSB Mah. Sanayi Caddesi No:34 Arsin / Trabzon",
     "0462 555 60 06", "selin.aydin@karadeniz-enerji.com",
     "Hidroelektrik santral projeleri"),
    ("Trakya Ambalaj Üretim A.Ş.", "Can Öztürk",
     "Velimeşe OSB Mah. 114. Sokak No:19 Ergene / Tekirdağ",
     "0282 555 70 07", "can.ozturk@trakya-ambalaj.com",
     "Ambalaj hattı otomasyon"),
    ("Güneydoğu Pompa ve Vana Ltd.", "Derya Arslan",
     "2. OSB Mah. 83201 Cadde No:41 Şehitkamil / Gaziantep",
     "0342 555 80 08", "derya.arslan@gdpompa.com",
     "Bölge distribütörü"),
    ("İç Anadolu Metal İşleme A.Ş.", "Fatih Yıldız",
     "Kayseri OSB Mah. 8. Cadde No:55 Melikgazi / Kayseri",
     "0352 555 90 09", "fatih.yildiz@icanadolu-metal.com",
     "Çelik konstrüksiyon üretimi"),
    ("Batı Akdeniz Su Teknolojileri Ltd.", "Gizem Koç",
     "Burdur OSB Mah. 3. Sanayi Caddesi No:28 Merkez / Burdur",
     "0248 555 00 10", "gizem.koc@batiakdeniz-su.com",
     "Su arıtma tesisi projeleri"),
]

customer_ids = []
for name, contact, address, phone, email, notes in customers_data:
    existing = db.fetchone("SELECT id FROM customers WHERE company_name=?", (name,))
    if existing:
        customer_ids.append(existing["id"])
        print(f"  ~ {name} zaten var (id={existing['id']})")
    else:
        cid = csvc.add(Customer(
            company_name=name, contact_person=contact,
            address=address, phone=phone, email=email, notes=notes))
        customer_ids.append(cid)
        print(f"  + {name} (id={cid})")

# ═══════════════════════════════════════════════════════════════════════════
# ÜRÜNLER
# ═══════════════════════════════════════════════════════════════════════════
print("\nÜrünler oluşturuluyor...")
products_data = [
    ("SNS-PMP-001", "Santrifüj Pompa 2.2kW", "AISI 316 paslanmaz gövde, mekanik salmastra, IP55", 1850.00, "EUR", 8, "Adet", "Pompalar"),
    ("SNS-PMP-002", "Dalgıç Pompa 4kW", "3 fazlı, krom-nikel gövde, 40m basma yüksekliği", 2400.00, "EUR", 5, "Adet", "Pompalar"),
    ("SNS-PMP-003", "Dozaj Pompası 0.5kW", "Elektromanyetik, PVDF gövde, kimyasal dayanımlı", 980.00, "EUR", 12, "Adet", "Pompalar"),
    ("SNS-VLV-001", "Kelebek Vana DN100", "PN16, EPDM contalı, paslanmaz disk", 320.00, "EUR", 25, "Adet", "Vanalar"),
    ("SNS-VLV-002", "Küresel Vana DN50", "2 parçalı, tam geçişli, 316SS", 185.00, "EUR", 30, "Adet", "Vanalar"),
    ("SNS-VLV-003", "Pnömatik Aktüatörlü Vana DN80", "Çift etkili, limit switch dahil", 890.00, "EUR", 10, "Adet", "Vanalar"),
    ("SNS-SEN-001", "Basınç Transmitteri 0-10bar", "4-20mA çıkış, G1/2 bağlantı, IP67", 275.00, "EUR", 20, "Adet", "Sensörler"),
    ("SNS-SEN-002", "Sıcaklık Sensörü PT100", "3 telli, -50/+200°C, 6mm prob çapı", 145.00, "EUR", 35, "Adet", "Sensörler"),
    ("SNS-SEN-003", "Seviye Şalteri (Yüzer Tip)", "PVC gövde, SPDT kontak, max 3bar", 95.00, "EUR", 40, "Adet", "Sensörler"),
    ("SNS-SEN-004", "Debi Ölçer (Elektromanyetik) DN50", "Dijital gösterge, puls çıkış, flanşlı", 1650.00, "EUR", 6, "Adet", "Sensörler"),
    ("SNS-FLT-001", "Sepet Filtre DN80", "PN16, 316SS elek, 100 mesh", 420.00, "EUR", 15, "Adet", "Filtreler"),
    ("SNS-FLT-002", "Y Filtre DN50", "Dökme demir gövde, paslanmaz elek", 165.00, "EUR", 22, "Adet", "Filtreler"),
    ("SNS-FLT-003", "Otomatik Geri Yıkamalı Filtre", "PLC kontrollü, 50 mikron, 316SS", 4200.00, "EUR", 3, "Adet", "Filtreler"),
    ("SNS-OTO-001", "PLC Kontrol Paneli", "Siemens S7-1200, 24 DI/16 DO, HMI 7 inç", 3500.00, "EUR", 4, "Set", "Otomasyon"),
    ("SNS-OTO-002", "Frekans Konvertör 7.5kW", "3 faz, 380V, vektör kontrol, modbus", 1200.00, "EUR", 7, "Adet", "Otomasyon"),
    ("SNS-OTO-003", "HMI Panel 10 inç", "Dokunmatik, Ethernet, 800x480 çözünürlük", 890.00, "EUR", 9, "Adet", "Otomasyon"),
    ("SNS-ACC-001", "Manometre 0-16bar", "63mm kadran, G1/4 alttan bağlantı, gliserinli", 35.00, "EUR", 50, "Adet", None),
    ("SNS-ACC-002", "Esnek Metal Hortum DN25", "316SS örgülü, EPDM iç, 1 metre", 85.00, "EUR", 30, "Metre", None),
    ("SNS-ACC-003", "Flanş Seti DN50 PN16", "304SS, conta ve cıvata dahil komple", 65.00, "EUR", 40, "Set", None),
    ("SNS-ACC-004", "Montaj ve Devreye Alma Hizmeti", "Saha montajı, test, devreye alma, eğitim", 450.00, "EUR", 0, "Gün", None),
]

product_map = {}
for code, name, desc, price, currency, stock, unit, cat_name in products_data:
    existing = psvc.get_by_code(code)
    if existing:
        product_map[code] = existing
        print(f"  ~ {code} zaten var")
    else:
        cat_id = categories.get(cat_name) if cat_name else None
        p = Product(product_code=code, product_name=name, description=desc,
                    price=price, currency=currency, stock=stock, unit=unit,
                    category_id=cat_id)
        pid = psvc.add(p)
        p.id = pid
        product_map[code] = p
        print(f"  + {code} — {name} (id={pid})")

# ═══════════════════════════════════════════════════════════════════════════
# TEKLİFLER (10 farklı senaryo)
# ═══════════════════════════════════════════════════════════════════════════
print("\nTeklifler oluşturuluyor...")
today = date.today()

def make_items(codes_qtys):
    items = []
    for code, qty in codes_qtys:
        p = product_map[code]
        items.append(OfferItem(
            product_id=p.id, product_code=p.product_code,
            product_name=p.product_name, description=p.description,
            quantity=qty, unit=p.unit, unit_price=p.price,
            total_price=round(qty * p.price, 2),
            delivery_time="2-3 Hafta"))
    return items

offers_data = [
    {
        "desc": "Büyük pompa + vana projesi (yüksek tutar, onaylanmış)",
        "customer_idx": 0, "currency": "EUR",
        "items": [("SNS-PMP-001", 3), ("SNS-PMP-002", 2), ("SNS-VLV-001", 6),
                  ("SNS-VLV-003", 4), ("SNS-ACC-004", 5)],
        "discount_pct": 8, "validity": "15 Gün", "payment": "30 Gün Vadeli",
        "status": "Onaylandı", "days_ago": 45,
    },
    {
        "desc": "Sensör paketi (orta tutar, beklemede, süresi dolmak üzere)",
        "customer_idx": 1, "currency": "EUR",
        "items": [("SNS-SEN-001", 10), ("SNS-SEN-002", 15), ("SNS-SEN-003", 8),
                  ("SNS-ACC-001", 20)],
        "discount_pct": 5, "validity": "10 Gün", "payment": "Peşin",
        "status": "Beklemede", "days_ago": 8,
    },
    {
        "desc": "Otomasyon sistemi (yüksek tutar, beklemede)",
        "customer_idx": 3, "currency": "EUR",
        "items": [("SNS-OTO-001", 2), ("SNS-OTO-002", 4), ("SNS-OTO-003", 2),
                  ("SNS-SEN-004", 3), ("SNS-ACC-004", 3)],
        "discount_pct": 10, "validity": "20 Gün", "payment": "45 Gün Vadeli",
        "status": "Beklemede", "days_ago": 5,
    },
    {
        "desc": "Filtre sistemi (orta tutar, onaylanmış)",
        "customer_idx": 2, "currency": "EUR",
        "items": [("SNS-FLT-001", 4), ("SNS-FLT-002", 8), ("SNS-FLT-003", 1),
                  ("SNS-ACC-003", 12)],
        "discount_pct": 0, "validity": "15 Gün", "payment": "15 Gün Vadeli",
        "status": "Onaylandı", "days_ago": 30,
    },
    {
        "desc": "Küçük vana siparişi (düşük tutar, iptal)",
        "customer_idx": 4, "currency": "EUR",
        "items": [("SNS-VLV-002", 5), ("SNS-ACC-003", 5)],
        "discount_pct": 0, "validity": "7 Gün", "payment": "Peşin",
        "status": "İptal", "days_ago": 60,
    },
    {
        "desc": "Su arıtma projesi (yüksek tutar, TL, beklemede)",
        "customer_idx": 9, "currency": "EUR",
        "items": [("SNS-PMP-003", 6), ("SNS-SEN-004", 2), ("SNS-FLT-003", 2),
                  ("SNS-VLV-003", 8), ("SNS-OTO-001", 1), ("SNS-ACC-004", 10)],
        "discount_pct": 12, "validity": "30 Gün", "payment": "60 Gün Vadeli",
        "status": "Beklemede", "days_ago": 3,
    },
    {
        "desc": "Enerji santrali vanalar (onaylanmış, eski)",
        "customer_idx": 5, "currency": "EUR",
        "items": [("SNS-VLV-001", 20), ("SNS-VLV-002", 30), ("SNS-VLV-003", 10),
                  ("SNS-ACC-002", 50)],
        "discount_pct": 15, "validity": "10 Gün", "payment": "30 Gün Vadeli",
        "status": "Onaylandı", "days_ago": 90,
    },
    {
        "desc": "Ambalaj hattı otomasyon (orta, beklemede, süresi dolmuş)",
        "customer_idx": 6, "currency": "EUR",
        "items": [("SNS-OTO-002", 3), ("SNS-OTO-003", 1), ("SNS-SEN-001", 5)],
        "discount_pct": 3, "validity": "7 Gün", "payment": "Peşin",
        "status": "Beklemede", "days_ago": 20,
    },
    {
        "desc": "Pompa yedek parça (düşük tutar, onaylanmış)",
        "customer_idx": 7, "currency": "EUR",
        "items": [("SNS-ACC-001", 30), ("SNS-ACC-002", 10), ("SNS-ACC-003", 15)],
        "discount_pct": 0, "validity": "5 Gün", "payment": "Peşin",
        "status": "Onaylandı", "days_ago": 15,
    },
    {
        "desc": "Metal işleme komple proje (çok yüksek tutar, beklemede, yeni)",
        "customer_idx": 8, "currency": "EUR",
        "items": [("SNS-PMP-001", 5), ("SNS-PMP-002", 3), ("SNS-VLV-001", 15),
                  ("SNS-VLV-003", 10), ("SNS-SEN-001", 20), ("SNS-SEN-004", 5),
                  ("SNS-FLT-001", 8), ("SNS-OTO-001", 3), ("SNS-OTO-002", 6),
                  ("SNS-ACC-004", 8)],
        "discount_pct": 10, "validity": "30 Gün", "payment": "90 Gün Vadeli",
        "status": "Beklemede", "days_ago": 1,
    },
]

for i, od in enumerate(offers_data, 1):
    items = make_items(od["items"])
    subtotal = sum(it.total_price for it in items)
    disc_pct = od["discount_pct"]
    disc_amt = round(subtotal * disc_pct / 100, 2)
    total = round(subtotal - disc_amt, 2)

    c_idx = od["customer_idx"]
    cust_id = customer_ids[c_idx]
    cust_data = customers_data[c_idx]
    offer_date = today - timedelta(days=od["days_ago"])

    offer = Offer(
        customer_id=cust_id,
        company_name=cust_data[0],
        customer_address=cust_data[2],
        contact_person=cust_data[1],
        customer_phone=cust_data[3],
        customer_email=cust_data[4],
        date=offer_date.strftime("%d.%m.%Y"),
        currency=od["currency"],
        total_amount=total,
        validity=od["validity"],
        payment_term=od["payment"],
        discount_type="percent" if disc_pct > 0 else "amount",
        discount_value=float(disc_pct) if disc_pct > 0 else 0,
        discount_amount=disc_amt,
        show_discount=disc_pct > 0,
        items=items,
    )
    try:
        oid = osvc.save(offer)
        saved = osvc.get_by_id(oid)
        if od["status"] != "Beklemede":
            osvc.update_status(oid, od["status"])
        sym = "€" if od["currency"] == "EUR" else ("₺" if od["currency"] == "TL" else "$")
        print(f"  #{i:2d}  {saved.offer_no}  {cust_data[0][:30]:<30}  "
              f"{total:>10,.2f} {sym}  {od['status']:<10}  ({od['desc'][:40]})")
    except Exception as e:
        print(f"  #{i:2d}  HATA: {e}")

print("\nTamamlandı!")
print(f"    Müşteriler: {csvc.count()}")
print(f"    Ürünler:    {psvc.count()}")
print(f"    Teklifler:  {osvc.count()}")
print(f"    Kategoriler: {catsvc.count()}")
