# Proje haritası

Bu dosya hızlı yönlendirme içindir; canlı kodun yerine geçmez.

## Çalışma ve veri akışı

- Giriş/tek örnek/splash: `main.py`
- Ana navigasyon ve sayfa yaşam döngüsü: `ui/main_window.py`
- Teklif akışı: `ui/create_offer_page.py` -> `services/offer_service.py` -> `models/offer.py`, `models/offer_item.py` -> `database/db_manager.py`
- Müşteri/ürün/kategori: `ui/{customers,products}_page.py` -> ilgili `services/*_service.py` -> `models/`
- Dashboard/rapor: `ui/{dashboard,reports}_page.py` -> `services/{offer,report}_service.py`
- PDF: `pdf/pdf_generator.py`; önizleme: `ui/dialogs/pdf_preview_dialog.py`
- Excel/CSV: `ui/utils/excel_import.py`, `services/export_service.py`
- Ayarlar/SMTP: `ui/settings_page.py`, `core/config.py`, `core/credential_store.py`, `ui/dialogs/email_dialog.py`
- Tema/ortak widget: `ui/utils/theme_manager.py`, `ui/widgets/`
- Yedekleme: `ui/dialogs/backup_manager.py`; veri yolları: `core/app_paths.py`
- Güncelleme: `ui/utils/updater.py`; sürüm: `core/constants.py`

## Kalıcı veri

- DB/config/logo/imza/PDF/log: `%LOCALAPPDATA%\OfferManagementSystem\data`
- Yedek: `%USERPROFILE%\Documents\OfferManagementSystem\backups`
- DB şeması: `database/schema.sql`; geriye uyumlu migration: `database/db_manager.py`
- Test izolasyonu: `tests/conftest.py` importlardan önce geçici `LOCALAPPDATA/USERPROFILE` kurar ve modülleri yeniden yükler.

## Dağıtım

- Kaynak sürümü: `core/constants.py:APP_VERSION`
- Yerel build: `packaging/Kurulum-Yap.bat` -> pytest -> PyInstaller onedir -> Inno Setup
- Paketleme kaynakları: `packaging/TeklifYonetim.spec`, `.iss`, `version_info.txt`
- Çıktı: `dist/TeklifYonetim/` ve `installer_output/TeklifYonetim_Setup_vX.Y.exe`
- Yayın akışı: `PROJECT_GUIDE/INDEX.md` release satırı; repo: `IzzmooPro/OfferManager`

## Test seçimi

- Konu -> test dosyası için kanonik `PROJECT_GUIDE/TESTING_GUIDE.md` matrisini kullan.
- Değişiklik etkisine göre önce hedefli test; release/shared altyapı tetiklenirse tam `python -m pytest tests -q`.
- UI için offscreen render yararlıdır; platforma bağlı glif/native davranışta gerçek Windows görsel kanıtı gerekir.

## Token ve güncellik kuralları

- Güncel durum ve risk için INDEX'in yönlendirdiği kanonik PROJECT_GUIDE belgelerini, sonra canlı Git/kod/test durumunu kullan.
- Kullanıcı metni `README.md`, sürüm geçmişi `docs/CHANGELOG.md`; snapshot değerleri canlı kanıtla yeniden ölçülür.
- `docs/local/SORUN_COZUM_NOTLARI.md` bütünü okunmaz. Önce `known-problems-index.md`, sonra yalnızca eşleşen numaralı bölüm okunur.
