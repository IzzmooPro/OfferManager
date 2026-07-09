# 📋 Teklif Yönetim Sistemi — Proje Geçmişi & Teknik Dokümantasyon

> Son güncelleme: Mart 2026  |  Version: v1

---

## 🏗️ Proje Yapısı

```
offer_management_system/
├── main.py                    # Uygulama giriş noktası (v1)
├── app_paths.py               # Merkezi path yönetimi — AppData + EXE mod
├── constants.py               # SYM_MAP, STATUS_CONFIG, STATUS_ORDER
├── build_exe.bat              # PyInstaller ile tek EXE oluşturma
├── clear_for_distribution.py  # Dağıtım öncesi test verisi temizleme
├── requirements.txt
├── README.md
├── ROADMAP.md
├── PROJE_GECMISI.md
│
├── database/
│   ├── db_manager.py          # SQLite singleton, transaction() context manager
│   └── schema.sql             # Tablolar + ON DELETE CASCADE/SET NULL
│
├── models/
│   ├── product.py
│   ├── customer.py
│   ├── offer.py
│   └── offer_item.py
│
├── services/
│   ├── offer_service.py       # Atomik save(), race-safe generate_offer_no()
│   ├── product_service.py     # search() — kod+ad+açıklama arar
│   ├── customer_service.py    # CRUD
│   └── export_service.py      # Excel/CSV export
│
├── pdf/
│   └── pdf_generator.py       # ReportLab, DejaVu font, Türkçe karakter
│
├── assets/
│   └── fonts/
│       ├── DejaVuSans.ttf
│       └── DejaVuSans-Bold.ttf
│   (logo.png, signature1.png, signature2.png, company.cfg → AppData'da)
│
└── ui/
    ├── updater.py             # Otomatik güncelleme sistemi (yeni — v1)
    ├── theme_manager.py       # Açık/Koyu tema, tüm QSS
    ├── main_window.py         # Ana pencere, sidebar, closeEvent, F1 toggle
    ├── dashboard_page.py      # İstatistik kartları + teklif tablosu
    ├── create_offer_page.py   # 3 adımlı wizard
    ├── products_page.py       # Ürün CRUD
    ├── customers_page.py      # Müşteri CRUD
    ├── settings_page.py       # 4 sekme: Şirket / Yetkililer / Logo&İmza / PDF
    ├── backup_manager.py      # Yedekleme/geri yükleme (genişletilmiş v1)
    ├── help_dialogs.py        # Yardım + Hakkında (v1 versiyonu, siyah linkler)
    └── ...
```

---

## 🗄️ Veri Mimarisi (v1)

```
Program Dosyaları  →  Proje klasörü / Program Files
Kullanıcı Verisi   →  %LOCALAPPDATA%\OfferManagementSystem\data\
Yedekler           →  %USERPROFILE%\Documents\OfferManagementSystem\backups\
```

app_paths.py tüm path'leri merkezi yönetir:
- `ASSET_ROOT`  → salt okunur assets (fonts, schema.sql)
- `DATA_DIR`    → AppData kullanıcı verisi
- `BACKUP_DIR`  → Documents yedek klasörü
- `CFG_PATH`, `LOGO_PATH`, `SIG1_PATH`, `SIG2_PATH` → AppData'da

İlk çalıştırmada `_migrate_old_data()` eski exe yanındaki veriyi AppData'ya kopyalar (tek seferlik).

---

## 🗄️ Veritabanı Şeması

```sql
products       — id, product_code(UNIQUE), product_name, description,
                 price, currency, stock, unit

customers      — id, company_name, contact_person, address, phone, email

offers         — id, offer_no(UNIQUE), customer_id(→customers SET NULL),
                 company_name, customer_address, contact_person,
                 date, currency, total_amount,
                 validity, validity_note, payment_term,
                 status(Beklemede/Onaylandı/İptal)

offer_items    — id, offer_id(→offers CASCADE), product_id(→products SET NULL),
                 product_code, product_name, description,
                 quantity, unit, delivery_time, unit_price, total_price

offer_counter  — id, year, last_number
```

---

## 💾 Yedekleme Sistemi (v1)

Yedek formatı: `backup_YYYY_MM_DD_HHMMSS.zip`
Yedek içeriği: database.db + company.cfg + logo.png + signature1.png + signature2.png

Otomatik yedekleme tetikleyicileri:
1. Program kapanırken (closeEvent)
2. Yeni teklif kaydedildiğinde
3. Zamanlı aralık (15dk / 30dk / 1sa / 2sa)

Restore güvenliği: hata durumunda tmp dosyası mekanizması ile orijinal korunur.

Startup algılama: database.db yoksa → backups/ kontrol → kullanıcıya sor.

---

## 🔄 Güncelleme Sistemi (v1)

`ui/updater.py` → `StartupUpdateChecker(QThread)`
- Program açılışında arka planda GitHub API sorgular
- `APP_VERSION = "v1"`, GitHub tag ile karşılaştırır
- Güncelleme yoksa → sessiz
- Güncelleme varsa → `UpdateDialog` ("Yeni bir sürüm bulundu.")
  - Güncelle → `_Downloader` thread, temp'e indir, bat script çalıştır, kapat
  - Daha sonra → diyalogu kapat

Güvenlik: veri klasörleri ve backup klasörü değiştirilmez.

---

## 📦 EXE Derleme

```bat
build_exe.bat
→ dist\TeklifYonetim.exe  (tek dosya)
```

EXE'de:
- ASSET_ROOT → sys._MEIPASS (gömülü dosyalar)
- DATA_ROOT  → AppData\Local\OfferManagementSystem\data (kalıcı)

---

## 🎨 Tema Sistemi

- `theme_manager.py` → `get_theme()` + `build_stylesheet()`
- İki tema: `light` / `dark`
- Font yönetimi tamamen QSS'de (pt birimi)

---

## ⚙️ Önemli Teknik Kararlar

| Konu | Karar | Neden |
|---|---|---|
| Veri konumu | AppData\Local | Program/veri ayrımı, güncelleme güvenliği |
| Yedek konumu | Documents | Kullanıcı erişimi, yedek güvenliği |
| Yedek format | backup_YYYY_MM_DD_HHMMSS.zip | Standart, sortlanabilir |
| Güncelleme | GitHub Releases API | Merkezi, güvenilir |
| F1 yardım | Toggle (show/hide) | UX kolaylığı |
| Kapanış yedeği | closeEvent | Veri kaybı önleme |
| Font birimi | pt | px+QFont çakışınca Qt -1 point size üretir |
| DB transaction | context manager | Atomik save |
| ON DELETE | CASCADE/SET NULL | Orphan kayıt bırakmaz |
| Log rotasyonu | 30 gün | Disk alanı kontrolü |

---

## 🐛 Çözülen Kritik Hatalar

1. **QFont::setPointSize <= 0** — pt'ye geçildi
2. **PDF Türkçe karakter** — DejaVu font embed edildi
3. **Offer save transaction** — atomik hale getirildi
4. **generate_offer_no race** — tek transaction
5. **ON DELETE eksikliği** — CASCADE/SET NULL eklendi
6. **AnimatedCard titreme** — QTimer.singleShot(0)
7. **QComboBox popup şeffaf** — ::item background eklendi
8. **Adres/iletişim sıfırlanması** — blockSignals ile düzeltildi
9. **Log birikimi** — 30 günden eski loglar siliniyor
10. **Settings Logo/İmza butonları** — inline setStyleSheet
11. **on_enter() form sıfırlama** — artık sadece önizleme yenileniyor
12. **PDF geçerlilik süresi hizalaması** — TA_LEFT → TA_RIGHT düzeltildi (v1)
13. **Veri/program ayrımı eksikliği** — AppData mimarisine geçildi (v1)
14. **Backup format tutarsızlığı** — backup_YYYY_MM_DD_HHMMSS.zip standardize edildi (v1)
15. **Email link görünümü** — mailto: prefix kaldırıldı, sade adres gösteriliyor (v1)
16. **Link stilleri** — siyah (#000000) + altı çizgili + tıklanabilir (v1)

---

## 🔧 Yapılacaklar (Pending)

- [ ] Teklif kopyalama (duplicate/clone)
- [ ] Inter font — `assets/fonts/Inter-Regular.ttf` konulursa aktif olur
- [ ] PDF önizleme — PyMuPDF gerektirir (`pip install pymupdf`)
- [ ] Teklif tarihi düzenleme modunda değiştirilebilir olsun

---

## 🌐 Gelecek: Web Versiyonu

Detaylar için `ROADMAP.md` dosyasına bak.
