"""Deterministik ve yalnız sentetik UI preview fixture'ları."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path

from ui_preview.sandbox import PreviewSandbox, SandboxViolation


_PROFILES = {"empty", "populated", "dense"}
_FIXED_DATE = "2026-08-15"


def _ensure_inside(path: Path, root: Path) -> None:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise SandboxViolation("Fixture yolu preview sandbox dışına çıktı") from exc


def _write_config(path: Path) -> None:
    values = {
        "name": "PREVIEW TEKNOLOJİ A.Ş.",
        "address": "Örnek Mahallesi, Tasarım Caddesi No: 42",
        "tel": "+90 212 000 00 00",
        "fax": "",
        "mail": "teklif@example.invalid",
        "web": "https://example.invalid",
        "offer_prefix": "PRV",
        "sales_person1_name": "Deniz Örnek",
        "sales_person1_title": "Satış Uzmanı",
        "sales_person1_email": "deniz@example.invalid",
        "sales_person2_name": "",
        "sales_person2_title": "",
        "sales_person2_email": "",
        "sales_person3_name": "",
        "sales_person3_title": "",
        "sales_person3_email": "",
        "sales_person4_name": "",
        "sales_person4_title": "",
        "sales_person4_email": "",
        "smtp_server": "smtp.example.invalid",
        "smtp_port": "465",
        "smtp_user": "preview@example.invalid",
        "pdf_giris_metni": "Bu belge yalnız UI önizleme amacıyla üretilmiştir.",
        "pdf_iskonto": "Örnek iskonto açıklaması.",
        "pdf_teslim_yeri": "Örnek teslimat adresi.",
        "pdf_kur_notu": "Sentetik döviz kuru açıklaması.",
        "pdf_kdv_notu": "Sentetik KDV açıklaması.",
        "pdf_onay_metni": "Sentetik teklif onay metni.",
        "pdf_teslim_notu": "Sentetik teslim süresi notu.",
        "pdf_iptal_notu": "Sentetik iptal ve iade notu.",
    }
    path.write_text(
        "\n".join(f"{key}={value}" for key, value in values.items()),
        encoding="utf-8",
    )


def _write_image(path: Path, label: str, color: tuple[int, int, int]) -> None:
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (480, 180), color)
    draw = ImageDraw.Draw(image)
    draw.rectangle((8, 8, 471, 171), outline=(255, 255, 255), width=4)
    draw.text((24, 72), label, fill=(255, 255, 255))
    image.save(path, format="PNG", optimize=False, compress_level=9)


def _write_pdf(path: Path) -> None:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    path.parent.mkdir(parents=True, exist_ok=True)
    pdf = canvas.Canvas(str(path), pagesize=A4, invariant=1, pageCompression=0)
    pdf.setTitle("OMS UI Preview Fixture")
    pdf.setAuthor("OMS UI Preview Lab")
    pdf.setSubject("Synthetic preview data")
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(72, 780, "OMS UI PREVIEW")
    pdf.setFont("Helvetica", 11)
    pdf.drawString(72, 750, "Synthetic fixture - no real customer data")
    pdf.drawString(72, 730, "Offer: PRV-2026-0001")
    pdf.showPage()
    pdf.save()


def _seed_database(path: Path, profile: str) -> dict[str, int]:
    schema_path = Path(__file__).resolve().parents[1] / "database" / "schema.sql"
    customer_count, product_count, offer_count = {
        "empty": (0, 0, 0),
        "populated": (4, 8, 5),
        "dense": (40, 80, 60),
    }[profile]

    with closing(sqlite3.connect(path)) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(schema_path.read_text(encoding="utf-8"))

        if profile != "empty":
            categories = [
                (1, "Sensörler", None, 10),
                (2, "Kontrol Sistemleri", None, 20),
                (3, "Endüstriyel Haberleşme", None, 30),
                (4, "Aksesuarlar", None, 40),
            ]
            conn.executemany(
                "INSERT INTO product_categories(id,name,parent_id,sort_order) VALUES(?,?,?,?)",
                categories,
            )

            customers = []
            for index in range(1, customer_count + 1):
                long_name = (
                    "Çok Uzun Ünvanlı Örnek Endüstriyel Otomasyon ve Teknoloji "
                    "Çözümleri Anonim Şirketi"
                    if index == customer_count else f"Preview Müşteri {index:02d} A.Ş."
                )
                customers.append((
                    index,
                    long_name,
                    f"Yetkili Kişi {index:02d}",
                    f"Örnek Mah. Test Sok. No:{index}",
                    f"+90 212 000 {index:04d}",
                    f"musteri{index:02d}@example.invalid",
                    "Yalnız sentetik UI önizleme kaydı.",
                ))
            conn.executemany(
                "INSERT INTO customers(id,company_name,contact_person,address,phone,email,notes) "
                "VALUES(?,?,?,?,?,?,?)",
                customers,
            )

            products = []
            for index in range(1, product_count + 1):
                description = (
                    "Uzun açıklama: yüksek hassasiyetli, dayanıklı gövdeli, çoklu "
                    "bağlantı seçenekli sentetik preview ürünü"
                    if index == product_count else f"Sentetik ürün açıklaması {index:03d}"
                )
                price = round(25.0 + index * 7.35, 2)
                products.append((
                    index,
                    f"PRD-{index:04d}",
                    f"Preview Ürün {index:03d}",
                    description,
                    price,
                    "EUR" if index % 3 else "USD",
                    float(index * 2),
                    "Adet",
                    ((index - 1) % 4) + 1,
                    round(price * 0.62, 2),
                ))
            conn.executemany(
                "INSERT INTO products(id,product_code,product_name,description,price,currency,stock,unit,category_id,cost_price) "
                "VALUES(?,?,?,?,?,?,?,?,?,?)",
                products,
            )

            statuses = ["Beklemede", "Onaylandı", "Reddedildi", "Süresi Doldu"]
            item_count = 0
            for index in range(1, offer_count + 1):
                customer_id = ((index - 1) % customer_count) + 1
                company_name = customers[customer_id - 1][1]
                month = ((index - 1) % 8) + 1
                day = ((index - 1) % 25) + 1
                total = round(400 + index * 83.75, 2)
                conn.execute(
                    "INSERT INTO offers(id,offer_no,customer_id,company_name,customer_address,contact_person,customer_phone,customer_email,date,currency,total_amount,validity,validity_note,payment_term,status,discount_amount,discount_type,discount_value,show_discount) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        index,
                        f"PRV-2026-{index:04d}",
                        customer_id,
                        company_name,
                        customers[customer_id - 1][3],
                        customers[customer_id - 1][2],
                        customers[customer_id - 1][4],
                        customers[customer_id - 1][5],
                        f"2026-{month:02d}-{day:02d}",
                        "EUR",
                        total,
                        "30 Gün",
                        "Sentetik geçerlilik notu",
                        "15 Gün",
                        statuses[(index - 1) % len(statuses)],
                        25.0,
                        "amount",
                        25.0,
                        1,
                    ),
                )
                for offset in range(2):
                    product_id = ((index + offset - 1) % product_count) + 1
                    product = products[product_id - 1]
                    item_count += 1
                    quantity = float(offset + 1)
                    unit_price = float(product[4])
                    conn.execute(
                        "INSERT INTO offer_items(id,offer_id,product_id,product_code,product_name,description,quantity,unit,delivery_time,unit_price,total_price) "
                        "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                        (
                            item_count,
                            index,
                            product_id,
                            product[1],
                            product[2],
                            product[3],
                            quantity,
                            "Adet",
                            "2-3 Hafta",
                            unit_price,
                            round(quantity * unit_price, 2),
                        ),
                    )

            templates = [
                (1, "Standart Preview Şablonu", "EUR", "[]", _FIXED_DATE),
                (2, "Uzun İsimli Endüstriyel Sistem Preview Şablonu", "USD", "[]", _FIXED_DATE),
            ]
            conn.executemany(
                "INSERT INTO offer_templates(id,template_name,currency,items_json,created_at) VALUES(?,?,?,?,?)",
                templates,
            )
            conn.execute(
                "INSERT INTO offer_counter(id,year,last_number) VALUES(1,2026,?)",
                (offer_count,),
            )

        conn.commit()
        counts = {}
        for table in (
            "product_categories", "customers", "products", "offers",
            "offer_items", "offer_templates",
        ):
            counts[table] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    return counts


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def build_fixture_profile(sandbox: PreviewSandbox, profile: str) -> dict:
    """Fresh sandbox içinde sentetik preview veri seti oluştur."""
    if profile not in _PROFILES:
        raise ValueError(f"Bilinmeyen preview fixture profili: {profile}")
    if os_preview := __import__("os").environ.get("OMS_UI_PREVIEW"):
        if os_preview != "1":
            raise SandboxViolation("Preview ortam işareti geçersiz")
    else:
        raise SandboxViolation("Fixture yalnız aktif preview sandbox içinde üretilebilir")

    data = sandbox.paths.data.resolve()
    _ensure_inside(data, sandbox.paths.root)
    db_path = data / "database.db"
    config_path = data / "company.cfg"
    logo_path = data / "logo.png"
    signature_paths = [data / f"signature{index}.png" for index in range(1, 5)]
    pdf_path = data / "offers_pdf" / "PRV-2026-0001.pdf"
    manifest_path = data / "preview_fixture_manifest.json"

    reserved = [db_path, config_path, logo_path, pdf_path, manifest_path, *signature_paths]
    if any(path.exists() for path in reserved):
        raise SandboxViolation("Fixture profili yalnız boş preview sandbox'a kurulabilir")

    counts = _seed_database(db_path, profile)
    _write_config(config_path)
    _write_image(logo_path, "OMS PREVIEW LOGO", (28, 78, 121))
    signature_colors = [(92, 61, 46), (51, 96, 70), (85, 64, 128), (120, 74, 30)]
    for index, (path, color) in enumerate(zip(signature_paths, signature_colors), 1):
        _write_image(path, f"PREVIEW SIGNATURE {index}", color)
    _write_pdf(pdf_path)

    relative_paths = {
        "database": "database.db",
        "config": "company.cfg",
        "logo": "logo.png",
        "signature1": "signature1.png",
        "signature2": "signature2.png",
        "signature3": "signature3.png",
        "signature4": "signature4.png",
        "sample_pdf": "offers_pdf/PRV-2026-0001.pdf",
        "manifest": "preview_fixture_manifest.json",
    }
    hash_paths = {
        key: data / relative
        for key, relative in relative_paths.items()
        if key != "manifest"
    }
    manifest = {
        "schema_version": 1,
        "profile": profile,
        "synthetic_only": True,
        "fixed_date": _FIXED_DATE,
        "counts": counts,
        "relative_paths": relative_paths,
        "sha256": {key: _sha256(path) for key, path in hash_paths.items()},
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest
