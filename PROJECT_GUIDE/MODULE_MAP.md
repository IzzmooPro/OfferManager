---
purpose: Dosya → sorumluluk eşlemesi; doğru dosyayı az token ile bulmak için.
read_when: Kod düzeltmesi, yeni özellik, "bu davranış nerede?" sorusu.
covers:
  - core/constants.py
  - core/config.py
  - core/credential_store.py
  - core/profit.py
  - services/offer_service.py
  - services/product_service.py
  - services/export_service.py
  - ui/create_offer_page.py
  - ui/products_page.py
  - ui/customers_page.py
  - ui/settings_page.py
  - ui/utils/excel_import.py
  - ui/utils/operation_error.py
  - pdf/pdf_generator.py
last_verified_commit: 060baf3
last_verified_date: 2026-07-28
volatile: false
---

# Modül haritası

Çalışma zamanı akışı için [ARCHITECTURE.md](ARCHITECTURE.md); veri yolları için [DATA_AND_PATHS.md](DATA_AND_PATHS.md).

## Giriş ve çekirdek

| Dosya | Sorumluluk |
|---|---|
| `main.py` | Giriş noktası; tek örnek kilidi, loglama, exception hook, splash, restart bayrağı |
| `core/constants.py` | `APP_VERSION` — **sürümün tek kaynağı** |
| `core/app_paths.py` | Asset kökü (frozen'da `sys._MEIPASS`) ve kullanıcı veri/yedek yolları |
| `core/config.py` | `company.cfg` okuma/yazma (firma bilgileri, PDF metinleri, SMTP ayarları) |
| `core/credential_store.py` | SMTP parolası → Windows Credential Manager; hata yutmaz, `CredentialStoreError` fırlatır |
| `core/restart.py` | Yeniden başlatma isteği, `--restarted-from` bayrağı, ardıl süreç |
| `core/profit.py`, `core/formatting.py`, `core/date_utils.py` | Kâr hesabı, biçimleme, tarih yardımcıları |

## Veri ve servisler

| Dosya | Sorumluluk |
|---|---|
| `database/schema.sql` | Tablo tanımları (products, customers, offers, offer_items, product_categories, templates) |
| `database/db_manager.py` | Bağlantı, `transaction()`, geriye uyumlu ve tekrar çalıştırılabilir migration'lar, index'ler |
| `services/offer_service.py` | Teklif numarası üretimi, teklif + kalem kaydı (atomik), listeleme, durum |
| `services/product_service.py` | Ürün CRUD, kod normalizasyonu (`normalize_code`), `get_by_code`, toplu `get_by_codes` |
| `services/customer_service.py`, `category_service.py`, `template_service.py` | İlgili CRUD |
| `services/export_service.py` | Excel/CSV dışa aktarma (içe aktarma şablonuyla uyumlu) |
| `services/document_service.py`, `report_service.py` | Belge üretim yardımcıları ve raporlar |
| `models/*.py` | `Offer`, `OfferItem`, `Product`, `Customer`, `Category`, `Template` veri sınıfları |

## UI

| Dosya | Sorumluluk |
|---|---|
| `ui/main_window.py` | Navigasyon, sayfa yaşam döngüsü, otomatik/kapanış yedeği, `_shutdown_workers` |
| `ui/create_offer_page.py` | 3 adımlı teklif akışı; ürün seçici (sonuç sınırı + debounce), şablondan yükleme, kâr paneli |
| `ui/products_page.py` / `ui/customers_page.py` | Liste, arama, ekle/düzenle/sil; hata durumunda diyalog açık kalır (retry döngüsü) |
| `ui/dashboard_page.py` / `ui/reports_page.py` | Özet kartları ve raporlar |
| `ui/settings_page.py` | Firma bilgileri, PDF metinleri, SMTP ayarları, tema |
| `ui/dialogs/backup_manager.py` | Yedek alma/geri yükleme, `AutoBackupService`, worker yaşam döngüsü |
| `ui/dialogs/email_dialog.py` | PDF'i e-posta ile gönderme (SMTP worker) |
| `ui/dialogs/pdf_preview_dialog.py`, `help_dialogs.py`, `category_dialog.py`, `customer_history_dialog.py` | Yardımcı diyaloglar |
| `ui/utils/excel_import.py` | CSV/XLSX içe aktarma: sayfa adayları, sayfa seçimi, doğrulama, mükerrer kontrolü, toplu yazma |
| `ui/utils/operation_error.py` | Kaydetme/silme hatası → güvenli kullanıcı mesajı + güvenli log |
| `ui/utils/theme_manager.py` | Açık/koyu tema, QSS üretimi |
| `ui/utils/updater.py` | Sürüm kontrolü, indirme, kurulum başlatma |
| `ui/widgets/*` | Ortak widget'lar (kart, tablo, kâr paneli, hover delegate) |

## PDF

`pdf/pdf_generator.py` — teklif PDF'i (ReportLab). Gömülü fontlar `assets/fonts`, varsayılan logo `assets/logo.png`. **Maliyet/kâr alanı PDF'e yazılmaz.**

## Paketleme

`packaging/TeklifYonetim.spec` (PyInstaller onedir), `packaging/TeklifYonetim.iss` (Inno Setup), `packaging/version_info.txt`, `packaging/Kurulum-Yap.bat`. Ayrıntı: [BUILD_AND_PACKAGING.md](BUILD_AND_PACKAGING.md).
