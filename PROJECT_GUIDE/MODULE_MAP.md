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
  - ui/utils/operation_error_dialog.py
  - core/feedback_report.py
  - ui/dialogs/feedback_dialog.py
  - ui/dashboard_page.py
  - ui/reports_page.py
  - ui/main_window.py
  - ui/dialogs/backup_manager.py
  - ui/dialogs/category_dialog.py
  - pdf/pdf_generator.py
last_verified_commit: 46d4d75
last_verified_date: 2026-08-04
volatile: false
---

# Modül haritası

Çalışma zamanı akışı için [ARCHITECTURE.md](ARCHITECTURE.md); veri yolları için [DATA_AND_PATHS.md](DATA_AND_PATHS.md).

## Giriş ve çekirdek

| Dosya | Sorumluluk |
|---|---|
| `main.py` | Giriş noktası; tek örnek kilidi, loglama, exception hook, splash, restart bayrağı |
| `core/constants.py` | `APP_VERSION` — **sürümün tek kaynağı**; `CONTACT_MAIL` — iletişim adresinin tek kanonik kaynağı (Hakkında ekranı ve geri bildirim penceresi buradan okur) |
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
| `ui/main_window.py` | Navigasyon, sayfa yaşam döngüsü, otomatik/kapanış yedeği, `_shutdown_workers`. Yedek **tüketicisi** sınırı: hata servis katmanında zaten tam bir kez güvenli loglandığı için burada yeniden ve ham biçimde loglanmaz; kapanış/teklif-kaydı yedeği hatası `op_hata.logla` ile güvenli geçilir ve tamamlanmış teklif kaydını inkâr etmez. `trigger_now` hatayı içeride yakaladığı için kapanışta **koşulsuz başarı logu yazılmaz** — başarı logu gerçek başarı noktasında (`AutoBackupService._on_backup_done`) atılır |
| `ui/create_offer_page.py` | 3 adımlı teklif akışı; ürün seçici (sonuç sınırı + debounce), şablondan yükleme, kâr paneli. `_finish_offer` **A) DB kaydı → B) kullanıcının PDF'i → C) program içi arşiv → D) sonraki eylemler** olarak ayrı aşamalarda yürür. Müşteri kaydetme YOLLARI da iki aşamalıdır: **A) servis `add` → B) `_yeni_musteriyi_goster` (liste yenileme + combo seçimi)**. A hatası kaydı engeller ve B'yi çalıştırmaz; B hatası kaydı İNKÂR ETMEZ (`kismi_hata_goster`); yeni kayıt yenilenen listede BULUNAMAZSA da sessizce dönülmez, aynı kısmi başarı sınırına düşer. `_open_add_customer` A hatasında AYNI `CustomerDialog` ile yeniden denemeye izin verir, kayıttan sonra diyaloğu yeniden açmaz |
| `ui/products_page.py` / `ui/customers_page.py` | Liste, arama, ekle/düzenle/sil; hata durumunda diyalog açık kalır (retry döngüsü) |
| `ui/dashboard_page.py` / `ui/reports_page.py` | Özet kartları ve raporlar. Dashboard'da teklif durum/şablon/PDF/dışa aktarma hata yolları güvenli mesaj + güvenli log kullanır; `PdfWorker` sonuçları `(exception, güvenli_id)` çiftleri olarak taşır. `_open_file` korumalıdır: PDF açılamazsa üretim inkâr edilmez, yol ve ham hata sızmaz, çoklu döngü devam eder. `reports_page` tarafında rapor **oluşturma** hatası sabit metinli etikete + güvenli loga, rapor **dışa aktarma** hatası güvenli hata diyaloğuna düşer; modülün kendi `logging`/`logger` kullanımı kaldırılmıştır |
| `ui/settings_page.py` | Firma bilgileri, PDF metinleri, SMTP ayarları, tema. Ayar kaydetme, SMTP testi ve görsel yükleme/kaldırma yolları sabit metin + güvenli log kullanır. `_upload` **açık `True`/`False` döndürür**: iptal ve kopyalama hatası `False`, dosya kaydedildiyse önizleme başarısız olsa bile `True`. Logo devre dışı işareti (`logo.disabled`) YALNIZ gerçek kayıtta silinir — iptal/hata bu işareti korur, aksi hâlde eski logo sessizce etkinleşirdi. İşaret yazılamazsa önizleme **gerçekte aktif olan** logoyu gösterir (varsayılan logo varsa onu, yoksa "Logo Yok") |
| `ui/dialogs/backup_manager.py` | Yedek alma/geri yükleme, `AutoBackupService`, worker yaşam döngüsü. `restore_backup` üç sonucu AYIRIR — `preflight_failed` / `rolled_back` / `rollback_failed` (`RestoreError.durum`, sabit metinler). Yedek DOSYASI ile `backup_meta.json` **ayrı aşamalardır**: metadata hatası oluşmuş yedeği geçersiz kılmaz ve `create_backup` tekrarlanmaz. `_geri_al` ilk hatada durmaz; DB ve tüm optional dosyalar denenir, başlangıçtaki var/yok durumu kurulmaya çalışılır, DB yeniden doğrulanır. `_gecici_temizle` ayrı aşamadır ve sonucu değiştiremez. Yeniden başlatma yalnız tam başarıda ve tam bir kez |
| `ui/dialogs/email_dialog.py` | PDF'i e-posta ile gönderme (SMTP worker) |
| `ui/dialogs/pdf_preview_dialog.py`, `help_dialogs.py`, `category_dialog.py`, `customer_history_dialog.py` | Yardımcı diyaloglar |
| `ui/utils/excel_import.py` | CSV/XLSX içe/dışa aktarma: sayfa adayları, sayfa seçimi, doğrulama, mükerrer kontrolü, toplu yazma. Dosya okuma hataları sabit `DOSYA_OKUMA_HATASI` üretir; satır/grup hatalarında `errors` listesine YALNIZ güvenli sıra numarası girer (firma adı, ürün kodu, teklif no girmez) ve güvenli `kayit_id` de bu sıradır. Kategori başarısızlığı önbelleğe alınır (aynı kategori yeniden denenmez), her FARKLI kategori bir kez loglanır, kullanıcıya tek toplu uyarı gösterilir. Aşama durumu çağırana **yalnız sayısal** `stage_state` (`kategori_yazildi`) ile taşınır; dönüş değeri gerçek DB değişikliğini gösterir. `_workbook_kapat` başarı ve hata yollarında `finally` içinde çalışır, kapatma hatası sonucu maskelemez. İlerleme penceresi hata, iptal ve başarı yollarının hepsinde kapanır |
| `ui/utils/operation_error.py` | İstisna → güvenli kullanıcı METNİ + güvenli log. **UI açmaz, Qt import etmez**; ürettiği metin düğme/pencere ögesine atıf yapmaz |
| `ui/utils/operation_error_dialog.py` | O metni gerçek `QMessageBox` içinde gösteren ince sarmalayıcı: `hata_goster` (tekil), `toplu_hata_goster` (kısmi başarı sayıları), `kismi_hata_goster` (kaydedildi ama sonraki adım başarısız), `dogrulama_goster` (log düğmesi yok) ve "Log Klasörünü Aç" düğmesi ve "Hata Raporla" düğmesi (`rapor_diyalogu_ac`). Rapor düğmesi YALNIZ tek ve belli bir istisna varken eklenir: `hata_goster` (teknik hata) ve `kismi_hata_goster`. `toplu_hata_goster` ve `dogrulama_goster` bu düğmeyi TAŞIMAZ |
| `core/feedback_report.py` | Hata/öneri raporunun SAF veri modeli ve metin üreticisi: `RaporVerisi`, `TeknikOzet`, `rapor_olustur`, `metin_uret`, `konu_uret`, `guvenli_konum`. Qt import etmez, diske/ağa dokunmaz, log yazmaz, istisnayı yeniden kaydetmez |
| `ui/dialogs/feedback_dialog.py` | Tek ortak bildirim penceresi (iki giriş: Yardım menüsü ve "Hata Raporla"). Tek form: görünen otomatik alanlar + tek "Ne oldu?" kutusu; `mailto_baglantisi` Qt URL/query ile kurulur; eylemler E-postayı Aç / Panoya Kopyala / Vazgeç |
| `ui/utils/theme_manager.py` | Açık/koyu tema, QSS üretimi |
| `ui/utils/updater.py` | Sürüm kontrolü, indirme, kurulum başlatma |
| `ui/widgets/*` | Ortak widget'lar (kart, tablo, kâr paneli, hover delegate) |

## PDF

`pdf/pdf_generator.py` — teklif PDF'i (ReportLab). Gömülü fontlar `assets/fonts`, varsayılan logo `assets/logo.png`. **Maliyet/kâr alanı PDF'e yazılmaz.**

## Paketleme

`packaging/TeklifYonetim.spec` (PyInstaller onedir), `packaging/TeklifYonetim.iss` (Inno Setup), `packaging/version_info.txt`, `packaging/Kurulum-Yap.bat`. Ayrıntı: [BUILD_AND_PACKAGING.md](BUILD_AND_PACKAGING.md).
