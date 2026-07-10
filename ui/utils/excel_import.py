"""
Excel / CSV veri aktarımı — penceresiz akış.

İçe aktarma:  Dosya → İçeri Aktar → dosya seç → özet onayı → aktar.
Dışa aktarma: Dosya → Dışarı Aktar → kayıt yeri seç → yaz.

Şablon sütun isimleri esnek eşleşir (Türkçe/İngilizce, büyük-küçük harf).
Dışa aktarılan dosyalar içe aktarmayla birebir uyumludur (roundtrip).
"""
import logging, csv, io, re
from pathlib import Path
from PySide6.QtWidgets import QFileDialog, QMessageBox, QCheckBox
from core.constants import normalize_currency

logger = logging.getLogger("excel_import")

# Sütun eşleştirme haritaları (olası başlık → alan adı)
CUSTOMER_MAP = {
    "firma adı": "company_name",  "firma": "company_name",
    "şirket adı": "company_name", "şirket": "company_name",
    "company": "company_name",    "company name": "company_name",
    "ilgili kişi": "contact_person", "ilgili": "contact_person",
    "kişi": "contact_person",     "contact": "contact_person",
    "adres": "address",           "address": "address",
    "telefon": "phone",           "tel": "phone",
    "phone": "phone",             "gsm": "phone",
    "e-posta": "email",           "eposta": "email",
    "email": "email",             "mail": "email",
    "not": "notes",               "notes": "notes",
    "müşteri notu": "notes",
}
PRODUCT_MAP = {
    "ürün kodu": "product_code",  "kod": "product_code",
    "code": "product_code",       "product code": "product_code",
    "ürün adı": "product_name",   "ürün": "product_name",
    "ad": "product_name",         "name": "product_name",
    "açıklama": "description",    "aciklama": "description",
    "description": "description", "detay": "description",
    "fiyat": "price",             "price": "price",
    "birim fiyat": "price",       "unit price": "price",
    "para birimi": "currency",    "currency": "currency",
    "döviz": "currency",
    "stok": "stock",              "stock": "stock",
    "miktar": "stock",            "quantity": "stock",
    "birim": "unit",              "unit": "unit",
    "kategori": "category",       "category": "category",
}


class _ImportProgress:
    """İçe aktarma sırasında gerçek ilerlemeyi gösteren modal pencere.

    Yüzde satır sayımından hesaplanır (sahte animasyon değil). Çağrılabilir:
    `prog(current, total)` → çubuğu günceller. İşlemler tek transaction'da hızlı
    olduğundan iptal butonu yok — pencere yalnız durumu doğru yansıtır.
    """

    def __init__(self, parent, label: str):
        from PySide6.QtWidgets import QProgressDialog
        from PySide6.QtCore import Qt
        dlg = QProgressDialog(label, "", 0, 100, parent)
        dlg.setWindowTitle("İçe Aktarma")
        dlg.setWindowModality(Qt.WindowModality.WindowModal)
        dlg.setCancelButton(None)          # yarım kalırsa veri tutarsız olmasın
        dlg.setMinimumWidth(360)
        dlg.setMinimumDuration(0)          # hemen görün
        dlg.setAutoClose(False)
        dlg.setAutoReset(False)
        dlg.setValue(0)
        self._dlg = dlg
        self._last = -1

    def set_label(self, text: str):
        self._dlg.setLabelText(text)
        self._dlg.setValue(0)
        self._last = -1
        from PySide6.QtWidgets import QApplication
        QApplication.processEvents()

    def __call__(self, current: int, total: int):
        pct = int(current * 100 / total) if total else 100
        pct = min(max(pct, 0), 100)
        if pct != self._last:               # yalnız değişince yeniden çiz
            self._last = pct
            self._dlg.setValue(pct)
            from PySide6.QtWidgets import QApplication
            QApplication.processEvents()

    def close(self):
        self._dlg.close()


def _norm(s: str) -> str:
    """Başlığı eşleştirme için normalize et — Türkçe İ/I harflerine dikkat.

    Python'da "İ".lower() sonucu "i" + birleşik nokta (U+0307) çıkar; bu
    yüzden "İlgili Kişi" gibi başlıklar haritayla eşleşemiyordu. Türkçe
    kurala göre önce İ→i ve I→ı çevrilir, sonra küçültülür.
    """
    s = s.strip().replace("İ", "i").replace("I", "ı")
    return s.lower().replace("̇", "").replace("_", " ")


def _read_file(path: str, progress=None) -> tuple[list, str]:
    """Dosyayı okur, (rows, error) döndürür. rows = list of dicts.

    `progress(current, total)` verilirse xlsx okurken satır ilerlemesi bildirilir.
    """
    p = Path(path)
    ext = p.suffix.lower()
    rows = []
    try:
        if ext in (".xlsx", ".xls", ".xlsm"):
            try:
                import openpyxl
                wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
                ws = wb.active
                # Satır satır akış — büyük dosyada belleğe komple almak yerine
                # okurken ilerleme bildir (toplam ws.max_row'dan tahmin edilir).
                total = ws.max_row or 0
                headers = None
                for idx, row in enumerate(ws.iter_rows(values_only=True)):
                    if idx == 0:
                        headers = [str(c or "").strip() for c in row]
                        continue
                    if all(c is None for c in row): continue
                    rows.append({headers[i]: (str(v) if v is not None else "")
                                 for i, v in enumerate(row) if i < len(headers)})
                    if progress and total and (idx & 0x3FF) == 0:
                        progress(idx, total)
                if headers is None:
                    wb.close(); return [], "Dosya boş."
                wb.close()
            except ImportError:
                return [], ("openpyxl kütüphanesi bulunamadı.\n"
                            "Lütfen dosyayı CSV olarak kaydedin veya\n"
                            "komut satırında: pip install openpyxl")
        elif ext == ".csv":
            # BOM ve encoding denemesi
            for enc in ("utf-8-sig", "utf-8", "cp1254", "latin-1"):
                try:
                    text = p.read_text(encoding=enc)
                    dialect = csv.Sniffer().sniff(text[:2048], delimiters=",;\t")
                    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
                    rows = [dict(r) for r in reader]
                    break
                except Exception:
                    continue
        else:
            return [], f"Desteklenmeyen dosya türü: {ext}\nDesteklenen: .xlsx, .csv"
    except Exception as e:
        return [], str(e)
    return rows, ""


def _map_row(row: dict, col_map: dict) -> dict:
    """Ham satırı alan adlarına çevirir."""
    result = {}
    for raw_key, value in row.items():
        norm_key = _norm(raw_key)
        field = col_map.get(norm_key)
        if field:
            result[field] = value.strip() if isinstance(value, str) else (value or "")
    return result


def _parse_number(value, default: float = 0.0) -> float:
    """Türkçe ve uluslararası binlik/ondalık biçimlerini güvenli ayrıştır."""
    if value is None or value == "":
        return default
    if isinstance(value, (int, float)):
        return float(value)
    text = re.sub(r"[^0-9,\.\-+]", "", str(value).strip())
    if not text:
        return default
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        text = text.replace(",", ".")
    elif text.count(".") > 1:
        text = text.replace(".", "")
    try:
        return float(text)
    except ValueError:
        return default


# ── Doğrulama ─────────────────────────────────────────────────────────────────

def _validate_rows(import_type: str, raw_rows: list,
                   progress=None) -> tuple[list, list, list]:
    """Ham satırları eşleştirir ve (geçerli, mükerrer, hatalı) olarak ayırır.

    Mükerrer kontrolü mevcut anahtarları TEK sorguda belleğe alıp orada yapılır
    (satır başına ayrı DB sorgusu on binlerce satırda ~1600x daha yavaştı).
    `progress(current, total)` verilirse aşama ilerlemesi bildirilir.
    """
    from database.db_manager import get_db
    db = get_db()
    col_map = CUSTOMER_MAP if import_type == "customers" else PRODUCT_MAP
    required = ("company_name",) if import_type == "customers" else (
        "product_code", "product_name")

    # Mevcut anahtarlar → id (TEK sorgu). Müşteri: firma adı (harfi harfine),
    # Ürün: UPPER(ürün kodu) — eski sorgu davranışıyla birebir.
    if import_type == "customers":
        existing = {(r["company_name"] or "").strip(): r["id"]
                    for r in db.fetchall("SELECT id, company_name FROM customers")}
    else:
        existing = {(r["product_code"] or "").strip().upper(): r["id"]
                    for r in db.fetchall("SELECT id, product_code FROM products")}

    valid, duplicates, invalid = [], [], []
    total = len(raw_rows)
    for i, raw in enumerate(raw_rows):
        r = _map_row(raw, col_map)
        missing = [k for k in required if not str(r.get(k, "")).strip()]
        if missing:
            r["_error"] = f"Zorunlu alan eksik: {', '.join(missing)}"
            invalid.append(r)
        else:
            if import_type == "customers":
                key = r.get("company_name", "").strip()
            else:
                key = r.get("product_code", "").strip().upper()
            ex_id = existing.get(key)
            if ex_id is not None:
                r["_duplicate"] = True
                r["_existing_id"] = ex_id
                duplicates.append(r)
            else:
                valid.append(r)
        if progress and (i & 0x3FF) == 0:   # ~her 1024 satırda bir güncelle
            progress(i + 1, total)
    if progress:
        progress(total, total)
    return valid, duplicates, invalid


# ── Veritabanına yazma ────────────────────────────────────────────────────────

def _perform_import(import_type: str, rows_to_process: list,
                    update_dups: bool, progress=None) -> tuple[int, int, int, list]:
    """Satırları veritabanına yazar. (eklenen, güncellenen, atlanan, hatalar)

    `progress(current, total)` verilirse kaydetme ilerlemesi bildirilir.
    """
    from database.db_manager import get_db
    db = get_db()
    added = updated = skipped = 0
    errors = []
    total = len(rows_to_process)

    # Tüm satırlar TEK transaction'da yazılır — satır başına ayrı commit
    # (her biri diske fsync) yerine tek diske-yazma. Binlerce satırda ~1000x
    # hız farkı. Satır-içi try/except korunur: bir bozuk satır tüm aktarımı
    # iptal etmez, sadece o satır atlanır (başarısız INSERT atomik geri alınır,
    # transaction açık kalır).
    if import_type == "customers":
        with db.transaction() as conn:
            for i, row in enumerate(rows_to_process):
                company = row.get("company_name", "").strip()
                if not company:
                    skipped += 1
                    continue
                is_dup = row.get("_duplicate", False)
                try:
                    if is_dup and update_dups:
                        conn.execute(
                            "UPDATE customers SET contact_person=?, address=?, "
                            "phone=?, email=?, notes=? WHERE id=?",
                            (row.get("contact_person", ""), row.get("address", ""),
                             row.get("phone", ""), row.get("email", ""),
                             row.get("notes", ""), row["_existing_id"]))
                        updated += 1
                    else:
                        conn.execute(
                            "INSERT INTO customers (company_name,contact_person,"
                            "address,phone,email,notes) VALUES (?,?,?,?,?,?)",
                            (company, row.get("contact_person", ""),
                             row.get("address", ""), row.get("phone", ""),
                             row.get("email", ""), row.get("notes", "")))
                        added += 1
                except Exception as e:
                    errors.append(f"Satır {i+1} ({company}): {e}")
                    skipped += 1
                if progress and (i & 0xFF) == 0:
                    progress(i + 1, total)
    else:
        # Kategoriler transaction'dan ÖNCE çözülür (yoksa oluşturulur) — böylece
        # tek yazıcı kuralı gereği iç içe yazma kilidi (SQLITE_BUSY) oluşmaz.
        from services.category_service import CategoryService
        from models.category import Category
        cat_svc = CategoryService()
        cat_cache = {c.name.strip().casefold(): c.id for c in cat_svc.get_all()}
        for row in rows_to_process:
            nm = (row.get("category", "") or "").strip()
            if nm and nm.casefold() not in cat_cache:
                try:
                    cat_cache[nm.casefold()] = cat_svc.add(Category(name=nm))
                except Exception as e:
                    logger.warning("Kategori oluşturulamadı (%s): %s", nm, e)

        def _category_id(raw_name: str):
            nm = (raw_name or "").strip()
            return cat_cache.get(nm.casefold()) if nm else None

        with db.transaction() as conn:
            for i, row in enumerate(rows_to_process):
                code = row.get("product_code", "").strip()
                name = row.get("product_name", "").strip()
                if not code or not name:
                    skipped += 1
                    continue
                price = _parse_number(row.get("price", 0))
                stock = _parse_number(row.get("stock", 0))
                # TRY/₺ gibi yaygın yazımlar sistemin "TL" koduna eşlenir;
                # tanınmayan/boş → EUR (bkz. core.constants.normalize_currency).
                currency = normalize_currency(row.get("currency", ""), default="EUR")
                unit = row.get("unit", "Adet") or "Adet"
                is_dup = row.get("_duplicate", False)
                try:
                    cat_id = _category_id(row.get("category", ""))
                    if is_dup and update_dups:
                        conn.execute(
                            "UPDATE products SET product_name=?, description=?, "
                            "price=?, currency=?, stock=?, unit=?, category_id=? "
                            "WHERE id=?",
                            (name, row.get("description", ""), price, currency,
                             stock, unit, cat_id, row["_existing_id"]))
                        updated += 1
                    else:
                        conn.execute(
                            "INSERT INTO products (product_code,product_name,"
                            "description,price,currency,stock,unit,category_id) "
                            "VALUES (?,?,?,?,?,?,?,?)",
                            (code, name, row.get("description", ""),
                             price, currency, stock, unit, cat_id))
                        added += 1
                except Exception as e:
                    errors.append(f"Satır {i+1} ({code}): {e}")
                    skipped += 1
                if progress and (i & 0xFF) == 0:
                    progress(i + 1, total)

    if progress:
        progress(total, total)
    return added, updated, skipped, errors


# ── Kullanıcı akışları ────────────────────────────────────────────────────────

def run_import_flow(parent, import_type: str) -> bool:
    """Dosya seç → özet onayı → aktar. Aktarım yapıldıysa True döner."""
    label = {"customers": "müşteri", "products": "ürün",
             "offers": "teklif"}[import_type]
    path, _ = QFileDialog.getOpenFileName(
        parent, f"{label.capitalize()} Verisi İçe Aktar", "",
        "Excel & CSV (*.xlsx *.xls *.xlsm *.csv);;Tüm Dosyalar (*)")
    if not path:
        return False

    prog = _ImportProgress(parent, "Dosya okunuyor…")
    raw_rows, err = _read_file(path, progress=prog)
    if err:
        prog.close()
        QMessageBox.warning(parent, "Dosya Hatası", err)
        return False
    if not raw_rows:
        prog.close()
        QMessageBox.warning(parent, "Boş Dosya", "Dosyada veri bulunamadı.")
        return False

    if import_type == "offers":
        # Teklifler satır-bazlı değil grup-bazlı doğrulanır (kalemli format)
        prog.close()
        return _run_offer_import_flow(parent, path, raw_rows)

    prog.set_label("Kayıtlar denetleniyor…")
    valid, duplicates, invalid = _validate_rows(import_type, raw_rows, progress=prog)
    prog.close()
    if not valid and not duplicates:
        msg = f"Dosyada aktarılabilir {label} kaydı bulunamadı."
        if invalid:
            msg += "\n\nHatalı satırlar:\n" + "\n".join(
                r.get("_error", "?") for r in invalid[:5])
            if len(invalid) > 5:
                msg += f"\n... ve {len(invalid) - 5} satır daha"
        QMessageBox.warning(parent, "Aktarılacak Veri Yok", msg)
        return False

    # Özet + onay — mükerrer güncelleme seçeneği onay kutusunun içinde
    parts = [f"{len(valid)} yeni {label}"]
    if duplicates:
        parts.append(f"{len(duplicates)} mükerrer kayıt")
    if invalid:
        parts.append(f"{len(invalid)} hatalı satır (atlanacak)")
    text = Path(path).name + "\n\n" + "\n".join(f"• {p}" for p in parts)
    if invalid:
        text += "\n\nHatalı satır örnekleri:\n" + "\n".join(
            f"  - {r.get('_error', '?')}" for r in invalid[:3])
    text += "\n\nAktarım başlatılsın mı?"

    box = QMessageBox(parent)
    box.setWindowTitle("İçe Aktarma Onayı")
    box.setIcon(QMessageBox.Icon.Question)
    box.setText(text)
    chk = None
    if duplicates:
        chk = QCheckBox("Mükerrer kayıtları dosyadaki verilerle güncelle")
        chk.setToolTip("İşaretlenmezse mükerrer kayıtlar olduğu gibi bırakılır.")
        box.setCheckBox(chk)
    btn_ok = box.addButton("Aktar", QMessageBox.ButtonRole.AcceptRole)
    box.addButton("İptal", QMessageBox.ButtonRole.RejectRole)
    box.setDefaultButton(btn_ok)
    box.exec()
    if box.clickedButton() is not btn_ok:
        return False

    update_dups = bool(chk and chk.isChecked())
    rows = list(valid) + (list(duplicates) if update_dups else [])
    prog = _ImportProgress(parent, f"{label.capitalize()} kaydediliyor…")
    added, updated, skipped, errors = _perform_import(
        import_type, rows, update_dups, progress=prog)
    prog.close()

    parts = []
    if added:
        parts.append(f"{added} {label} eklendi")
    if updated:
        parts.append(f"{updated} {label} güncellendi")
    dup_skipped = len(duplicates) if not update_dups else 0
    if dup_skipped:
        parts.append(f"{dup_skipped} mükerrer atlandı")
    if skipped or invalid:
        parts.append(f"{skipped + len(invalid)} satır atlandı")
    if not parts:
        parts.append("İşlem yapılmadı.")
    msg = "\n".join(parts)
    if errors:
        msg += "\n\nHatalar:\n" + "\n".join(errors[:10])
        if len(errors) > 10:
            msg += f"\n... ve {len(errors) - 10} hata daha"
    QMessageBox.information(parent, "İçe Aktarma Tamamlandı", msg)
    logger.info("Excel import: type=%s added=%d updated=%d skipped=%d errors=%d",
                import_type, added, updated, skipped, len(errors))
    return True


def export_data_interactive(parent, import_type: str):
    """Kayıtlı verileri içe aktarmayla birebir uyumlu Excel'e yazar.

    Veri yoksa yalnızca başlık satırı yazılır — boş şablon işlevi görür.
    """
    import datetime
    today = datetime.date.today().strftime('%Y%m%d')
    try:
        if import_type == "customers":
            from services.customer_service import CustomerService
            records = CustomerService().get_all()
            default = f"musteriler_{today}.xlsx"
            label = "müşteri"
        elif import_type == "offers":
            from services.offer_service import OfferService
            svc = OfferService()
            # Kalemler dahil tam veri — roundtrip için get_by_id ile yüklenir
            records = [svc.get_by_id(o.id) for o in svc.get_all()]
            records = [o for o in records if o]
            default = f"teklifler_{today}.xlsx"
            label = "teklif"
        else:
            from services.product_service import ProductService
            records = ProductService().get_all()
            default = f"urunler_{today}.xlsx"
            label = "ürün"
    except Exception as e:
        QMessageBox.warning(parent, "Hata", f"Veriler okunamadı:\n{e}")
        return

    path, _ = QFileDialog.getSaveFileName(
        parent, "Veriyi Dışa Aktar", default, "Excel Dosyası (*.xlsx)")
    if not path:
        return
    try:
        if import_type == "customers":
            from services.export_service import export_customers_excel
            out = export_customers_excel(records, path)
        elif import_type == "offers":
            from services.export_service import export_offers_full_excel
            out = export_offers_full_excel(records, path)
        else:
            from services.export_service import export_products_excel
            from services.category_service import CategoryService
            cats = {c.id: c.name for c in CategoryService().get_all()}
            out = export_products_excel(records, path, cats)
        QMessageBox.information(
            parent, "Tamamlandı",
            f"{len(records)} {label} dışa aktarıldı.\n{out}\n\n"
            "Bu dosya 'Dosya → İçeri Aktar' ile olduğu gibi geri yüklenebilir.")
    except Exception as e:
        QMessageBox.warning(parent, "Hata", f"Export hatası:\n{e}")


# ── Teklif içe aktarma (kalemli format) ───────────────────────────────────────
# export_offers_full_excel çıktısıyla birebir uyumlu: her satır bir kalem,
# satırlar "Teklif No"ya göre gruplanıp teklif yeniden kurulur.

OFFER_MAP = {
    "teklif no": "offer_no",
    "firma": "company_name",         "firma adı": "company_name",
    "ilgili kişi": "contact_person",
    "adres": "address",
    "telefon": "phone",
    "e-posta": "email",              "eposta": "email",
    "tarih": "date",
    "para birimi": "currency",
    "durum": "status",
    "geçerlilik": "validity",
    "geçerlilik notu": "validity_note",
    "ödeme": "payment_term",         "ödeme vadesi": "payment_term",
    "iskonto (%)": "discount_percent", "iskonto": "discount_percent",
    "ürün kodu": "product_code",     "kod": "product_code",
    "ürün adı": "product_name",      "ürün": "product_name",
    "ürün açıklama": "item_description", "açıklama": "item_description",
    "adet": "quantity",              "miktar": "quantity",
    "birim": "unit",
    "teslim süresi": "delivery_time", "teslim": "delivery_time",
    "birim fiyat": "unit_price",     "fiyat": "unit_price",
}


def _validate_offer_rows(raw_rows: list) -> tuple[list, list, list]:
    """Satırları teklife gruplar. (yeni_teklifler, mükerrer_nolar, hatalar)"""
    from database.db_manager import get_db
    from core.constants import STATUS_ORDER
    db = get_db()

    groups, order, invalid = {}, [], []
    for idx, raw in enumerate(raw_rows, 2):   # 1. satır başlık
        r = _map_row(raw, OFFER_MAP)
        no = str(r.get("offer_no", "")).strip()
        if not no:
            invalid.append(f"Satır {idx}: Teklif No eksik")
            continue
        g = groups.get(no)
        if g is None:
            company = str(r.get("company_name", "")).strip()
            if not company:
                invalid.append(f"Satır {idx}: Firma adı eksik ({no})")
                continue
            status = str(r.get("status", "")).strip()
            g = {
                "offer_no": no,
                "company_name": company,
                "contact_person": str(r.get("contact_person", "")).strip(),
                "address": str(r.get("address", "")).strip(),
                "phone": str(r.get("phone", "")).strip(),
                "email": str(r.get("email", "")).strip(),
                "date": str(r.get("date", "")).strip(),
                "currency": normalize_currency(r.get("currency", ""),
                                               default="EUR"),
                "status": status if status in STATUS_ORDER else "Beklemede",
                "validity": str(r.get("validity", "")).strip(),
                "validity_note": str(r.get("validity_note", "")).strip(),
                "payment_term": str(r.get("payment_term", "")).strip(),
                "discount_percent": _parse_number(r.get("discount_percent"), 0),
                "items": [],
            }
            groups[no] = g
            order.append(no)
        pname = str(r.get("product_name", "")).strip()
        pcode = str(r.get("product_code", "")).strip()
        if not (pname or pcode):
            invalid.append(f"Satır {idx}: Ürün bilgisi eksik ({no})")
            continue
        qty = _parse_number(r.get("quantity"), 0) or 1
        price = _parse_number(r.get("unit_price"), 0)
        g["items"].append({
            "product_code": pcode,
            "product_name": pname or pcode,
            "description": str(r.get("item_description", "")).strip(),
            "quantity": qty,
            "unit": str(r.get("unit", "")).strip() or "Adet",
            "delivery_time": str(r.get("delivery_time", "")).strip() or "2-3 Hafta",
            "unit_price": price,
        })

    new_offers, dups = [], []
    for no in order:
        if db.fetchone("SELECT id FROM offers WHERE offer_no = ?", (no,)):
            dups.append(no)
        elif not groups[no]["items"]:
            invalid.append(f"{no}: hiç geçerli ürün kalemi yok")
        else:
            new_offers.append(groups[no])
    return new_offers, dups, invalid


def _perform_offer_import(offer_groups: list) -> tuple[int, list]:
    """Gruplanmış teklifleri kaydeder. (eklenen, hatalar) döner."""
    import datetime as _dt
    from services.offer_service import OfferService
    from models.offer import Offer, calculate_discount
    from models.offer_item import OfferItem

    svc = OfferService()
    added, errors = 0, []
    for g in offer_groups:
        try:
            items = [OfferItem(
                product_code=i["product_code"], product_name=i["product_name"],
                description=i["description"], quantity=i["quantity"],
                unit=i["unit"], delivery_time=i["delivery_time"],
                unit_price=i["unit_price"],
                total_price=i["quantity"] * i["unit_price"],
            ) for i in g["items"]]
            subtotal = sum(it.total_price for it in items)
            pct = float(g["discount_percent"] or 0)
            discount = calculate_discount(subtotal, "percent", pct)
            offer = Offer(
                offer_no=g["offer_no"], company_name=g["company_name"],
                contact_person=g["contact_person"],
                customer_address=g["address"], customer_phone=g["phone"],
                customer_email=g["email"],
                date=g["date"] or _dt.date.today().strftime("%d.%m.%Y"),
                currency=g["currency"], status=g["status"],
                validity=g["validity"], validity_note=g["validity_note"],
                payment_term=g["payment_term"],
                discount_type="percent", discount_value=pct,
                discount_amount=discount, show_discount=pct > 0,
                total_amount=subtotal - discount, items=items,
            )
            svc.save(offer, keep_offer_no=True)
            added += 1
        except Exception as e:
            errors.append(f"{g.get('offer_no', '?')}: {e}")
    return added, errors


def _run_offer_import_flow(parent, path: str, raw_rows: list) -> bool:
    """Teklif dosyası için onay + aktarım."""
    new_offers, dups, invalid = _validate_offer_rows(raw_rows)
    if not new_offers:
        msg = "Dosyada aktarılabilir yeni teklif bulunamadı."
        if dups:
            ekstra = ", ".join(dups[:5]) + (" ..." if len(dups) > 5 else "")
            msg += f"\n\n{len(dups)} teklif zaten kayıtlı (atlandı):\n{ekstra}"
        if invalid:
            msg += "\n\nHatalı satırlar:\n" + "\n".join(invalid[:5])
        QMessageBox.warning(parent, "Aktarılacak Veri Yok", msg)
        return False

    item_count = sum(len(g["items"]) for g in new_offers)
    parts = [f"{len(new_offers)} yeni teklif ({item_count} kalem)"]
    if dups:
        parts.append(f"{len(dups)} teklif zaten kayıtlı (atlanacak)")
    if invalid:
        parts.append(f"{len(invalid)} hatalı satır (atlanacak)")
    text = Path(path).name + "\n\n" + "\n".join(f"• {p}" for p in parts)
    if invalid:
        text += "\n\nHatalı satır örnekleri:\n" + "\n".join(
            f"  - {e}" for e in invalid[:3])
    text += "\n\nAktarım başlatılsın mı?"

    box = QMessageBox(parent)
    box.setWindowTitle("Teklif İçe Aktarma Onayı")
    box.setIcon(QMessageBox.Icon.Question)
    box.setText(text)
    btn_ok = box.addButton("Aktar", QMessageBox.ButtonRole.AcceptRole)
    box.addButton("İptal", QMessageBox.ButtonRole.RejectRole)
    box.setDefaultButton(btn_ok)
    box.exec()
    if box.clickedButton() is not btn_ok:
        return False

    added, errors = _perform_offer_import(new_offers)
    msg = f"{added} teklif eklendi"
    if dups:
        msg += f"\n{len(dups)} mevcut teklif atlandı"
    if invalid:
        msg += f"\n{len(invalid)} hatalı satır atlandı"
    if errors:
        msg += "\n\nHatalar:\n" + "\n".join(errors[:10])
    QMessageBox.information(parent, "İçe Aktarma Tamamlandı", msg)
    logger.info("Teklif import: added=%d dup=%d invalid=%d errors=%d",
                added, len(dups), len(invalid), len(errors))
    return added > 0


# ── Tümünü içe / dışa aktar (tek dosya, 3 sayfa) ─────────────────────────────

def _read_xlsx_sheets(path: str) -> tuple[dict, str]:
    """Çok sayfalı Excel okur: ({sayfa_adı: satırlar}, hata)."""
    try:
        import openpyxl
    except ImportError:
        return {}, "openpyxl kütüphanesi bulunamadı."
    try:
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        result = {}
        for ws in wb.worksheets:
            all_rows = list(ws.iter_rows(values_only=True))
            if not all_rows:
                continue
            headers = [str(c or "").strip() for c in all_rows[0]]
            rows = []
            for row in all_rows[1:]:
                if all(c is None for c in row):
                    continue
                rows.append({headers[i]: (str(v) if v is not None else "")
                             for i, v in enumerate(row) if i < len(headers)})
            result[ws.title] = rows
        wb.close()
        return result, ""
    except Exception as e:
        return {}, str(e)


def run_import_all_flow(parent) -> bool:
    """Tek dosyadan Müşteri + Ürün + Teklif verisini birlikte içe aktarır.

    Dosyadaki 'Müşteriler', 'Ürünler', 'Teklifler' sayfaları tanınır;
    eksik sayfalar atlanır. Sıra: müşteriler → ürünler → teklifler.
    """
    path, _ = QFileDialog.getOpenFileName(
        parent, "Tümünü İçe Aktar (Tek Dosya)", "",
        "Excel Dosyası (*.xlsx *.xlsm)")
    if not path:
        return False

    sheets, err = _read_xlsx_sheets(path)
    if err:
        QMessageBox.warning(parent, "Dosya Hatası", err)
        return False

    def _find(keyword):
        for name, rows in sheets.items():
            if keyword in _norm(name):
                return rows
        return None

    cust_rows = _find("müşteri")
    prod_rows = _find("ürün")
    off_rows  = _find("teklif")
    if cust_rows is None and prod_rows is None and off_rows is None:
        QMessageBox.warning(
            parent, "Sayfa Bulunamadı",
            "Bu dosyada 'Müşteriler', 'Ürünler' veya 'Teklifler' adlı sayfa "
            "bulunamadı.\n\nTek türlü bir dosya aktarmak istiyorsanız "
            "Dosya → İçeri Aktar menüsündeki ilgili seçeneği kullanın.")
        return False

    # ── Doğrulama ────────────────────────────────────────────────────────
    prog = _ImportProgress(parent, "Kayıtlar denetleniyor…")
    c_valid = c_dup = p_valid = p_dup = []
    o_new, o_dup, all_invalid = [], [], []
    if cust_rows:
        prog.set_label("Müşteriler denetleniyor…")
        c_valid, c_dup, c_inv = _validate_rows("customers", cust_rows, progress=prog)
        all_invalid += [f"Müşteri: {r.get('_error','?')}" for r in c_inv]
    if prod_rows:
        prog.set_label("Ürünler denetleniyor…")
        p_valid, p_dup, p_inv = _validate_rows("products", prod_rows, progress=prog)
        all_invalid += [f"Ürün: {r.get('_error','?')}" for r in p_inv]
    if off_rows:
        o_new, o_dup, o_inv = _validate_offer_rows(off_rows)
        all_invalid += [f"Teklif: {e}" for e in o_inv]
    prog.close()

    if not (c_valid or c_dup or p_valid or p_dup or o_new):
        QMessageBox.warning(parent, "Aktarılacak Veri Yok",
                            "Dosyada aktarılabilir yeni kayıt bulunamadı.")
        return False

    # ── Özet + onay ──────────────────────────────────────────────────────
    parts = []
    if cust_rows is not None:
        parts.append(f"{len(c_valid)} yeni müşteri"
                     + (f", {len(c_dup)} mükerrer" if c_dup else ""))
    if prod_rows is not None:
        parts.append(f"{len(p_valid)} yeni ürün"
                     + (f", {len(p_dup)} mükerrer" if p_dup else ""))
    if off_rows is not None:
        item_count = sum(len(g["items"]) for g in o_new)
        parts.append(f"{len(o_new)} yeni teklif ({item_count} kalem)"
                     + (f", {len(o_dup)} zaten kayıtlı" if o_dup else ""))
    if all_invalid:
        parts.append(f"{len(all_invalid)} hatalı satır (atlanacak)")
    text = Path(path).name + "\n\n" + "\n".join(f"• {p}" for p in parts)
    text += "\n\nAktarım başlatılsın mı?"

    box = QMessageBox(parent)
    box.setWindowTitle("Tümünü İçe Aktarma Onayı")
    box.setIcon(QMessageBox.Icon.Question)
    box.setText(text)
    chk = None
    if c_dup or p_dup:
        chk = QCheckBox("Mükerrer müşteri/ürün kayıtlarını dosyayla güncelle")
        box.setCheckBox(chk)
    btn_ok = box.addButton("Aktar", QMessageBox.ButtonRole.AcceptRole)
    box.addButton("İptal", QMessageBox.ButtonRole.RejectRole)
    box.setDefaultButton(btn_ok)
    box.exec()
    if box.clickedButton() is not btn_ok:
        return False

    update_dups = bool(chk and chk.isChecked())

    # ── Aktarım: müşteri → ürün → teklif ─────────────────────────────────
    prog = _ImportProgress(parent, "Kaydediliyor…")
    summary, errors = [], []
    if cust_rows:
        prog.set_label("Müşteriler kaydediliyor…")
        rows = list(c_valid) + (list(c_dup) if update_dups else [])
        a, u, s, e = _perform_import("customers", rows, update_dups, progress=prog)
        summary.append(f"Müşteri: {a} eklendi"
                       + (f", {u} güncellendi" if u else ""))
        errors += e
    if prod_rows:
        prog.set_label("Ürünler kaydediliyor…")
        rows = list(p_valid) + (list(p_dup) if update_dups else [])
        a, u, s, e = _perform_import("products", rows, update_dups, progress=prog)
        summary.append(f"Ürün: {a} eklendi"
                       + (f", {u} güncellendi" if u else ""))
        errors += e
    if off_rows:
        prog.set_label("Teklifler kaydediliyor…")
        a, e = _perform_offer_import(o_new)
        summary.append(f"Teklif: {a} eklendi"
                       + (f", {len(o_dup)} mevcut atlandı" if o_dup else ""))
        errors += e
    prog.close()

    msg = "\n".join(summary)
    if all_invalid:
        msg += f"\n{len(all_invalid)} hatalı satır atlandı"
    if errors:
        msg += "\n\nHatalar:\n" + "\n".join(errors[:10])
    QMessageBox.information(parent, "İçe Aktarma Tamamlandı", msg)
    logger.info("Tumunu import: %s | hatalar=%d", " / ".join(summary), len(errors))
    return True


def export_all_interactive(parent):
    """Müşteri + Ürün + Teklif verisini tek dosyada dışa aktarır."""
    import datetime
    try:
        from services.customer_service import CustomerService
        from services.product_service import ProductService
        from services.offer_service import OfferService
        from services.category_service import CategoryService
        customers = CustomerService().get_all()
        products = ProductService().get_all()
        svc = OfferService()
        offers_full = [o for o in (svc.get_by_id(x.id) for x in svc.get_all()) if o]
        cats = {c.id: c.name for c in CategoryService().get_all()}
    except Exception as e:
        QMessageBox.warning(parent, "Hata", f"Veriler okunamadı:\n{e}")
        return

    default = f"teklif_yonetim_verileri_{datetime.date.today().strftime('%Y%m%d')}.xlsx"
    path, _ = QFileDialog.getSaveFileName(
        parent, "Tümünü Dışa Aktar (Tek Dosya)", default,
        "Excel Dosyası (*.xlsx)")
    if not path:
        return
    try:
        from services.export_service import export_all_excel
        out = export_all_excel(path, customers, products, offers_full, cats)
        QMessageBox.information(
            parent, "Tamamlandı",
            f"{len(customers)} müşteri, {len(products)} ürün, "
            f"{len(offers_full)} teklif tek dosyaya aktarıldı.\n{out}\n\n"
            "Bu dosya 'Dosya → İçeri Aktar → Tümünü İçe Aktar' ile "
            "olduğu gibi geri yüklenebilir.")
    except Exception as e:
        QMessageBox.warning(parent, "Hata", f"Export hatası:\n{e}")
