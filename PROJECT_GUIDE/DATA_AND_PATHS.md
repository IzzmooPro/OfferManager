---
purpose: Veri yolları, şema/migration düzeni, import/export ve yedek/geri yükleme davranışı.
read_when: Veri, yol, migration, yedek, import/export işleri.
covers:
  - core/app_paths.py
  - database/schema.sql
  - database/db_manager.py
  - ui/utils/excel_import.py
  - services/export_service.py
  - ui/dialogs/backup_manager.py
  - tests/conftest.py
last_verified_commit: 060baf3
last_verified_date: 2026-07-28
volatile: false
---

# Veri ve yollar

Bu belgede **gerçek makine yolu yazılmaz**; temsili kökler kullanılır.

| Sembol | Anlamı |
|---|---|
| `<PROJECT_ROOT>` | Depo kökü (kaynak) |
| `<USER_DATA_ROOT>` | `%LOCALAPPDATA%\OfferManagementSystem` |
| `<BACKUP_ROOT>` | `%USERPROFILE%\Documents\OfferManagementSystem\backups` |
| `<TEMP_ROOT>` | Testlerin ve deneylerin geçici kökü |

## Kalıcı kullanıcı verisi

- `<USER_DATA_ROOT>\data\` — veritabanı, `company.cfg`, logo/imza görselleri, `logs\`, `offers_pdf\`
- `<BACKUP_ROOT>\` — otomatik ve manuel ZIP yedekler (rotasyon: son 20 tutulur)
- Klasör adı `OfferManagementSystem` **değiştirilmez**; kurulum dizininden bağımsızdır ve kaldırma işleminden etkilenmez.
- Program dosyaları (asset, şema, font) kurulum dizininde; frozen'da `sys._MEIPASS` altında çözülür.

## Şema ve migration

- Tablolar: `products`, `customers`, `offers`, `offer_items`, `product_categories`, şablon tabloları.
- Migration'lar `database/db_manager.py` içinde; **geriye uyumlu ve tekrar çalıştırılabilir** olmalı.
- Ürün kodu için iki index: `ux_products_code_nocase` (çakışma yoksa oluşturulan benzersiz index) ve `ix_products_code_nonascii` (ASCII dışı kodlar için kısmi index).
- Çok satırlı yazma/silme/güncelleme tek `db.transaction()` içinde; aynı transaction içinde ikinci writer açılmaz.

## İçe aktarma (CSV / XLSX)

Akış: dosya seç → **(XLSX ve birden fazla uygun sayfa varsa) sayfa seç** → ilerleme penceresi → oku → doğrula → özet onayı → tek transaction ile yaz → sonuç.

- Sayfa adayı ölçütü: **görünür** sayfa + zorunlu başlıkların tamamı + en az bir veri satırı. Gizli sayfalar ne listelenir ne okunur.
- Tek aday varsa otomatik seçilir (ek tıklama yok); birden fazlaysa kullanıcıya sorulur ve **yalnız seçilen sayfa** aktarılır — sayfalar birleştirilmez.
- Sayfa sorusu ilerleme penceresinden **önce** sorulur (bkz. O16, [CRITICAL_INVARIANTS.md](CRITICAL_INVARIANTS.md)).
- Kullanıcı iptal ederse: DB yazımı yok, hata kutusu yok, yarım aktarım yok.
- Aynı dosya içindeki mükerrer satırlar hem ürün hem müşteri yolunda atlanır; hata mesajında kaynak sayfa adı gösterilir.
- "Tümünü İçe Aktar (tek dosya)" ayrı yoldur: `Müşteriler`/`Ürünler`/`Teklifler` adlı sayfaları tanır, sayfa sorusu sormaz.

## Dışa aktarma

`services/export_service.py` içe aktarma şablonuyla uyumlu başlıklar üretir; veri yoksa yalnız başlık satırı yazılır (boş şablon işlevi). **Maliyet/kâr sütunu dışa aktarılmaz.**

## Yedek ve geri yükleme

- ZIP içeriği: veritabanı anlık kopyası + `company.cfg` + varsa logo/imzalar + `backup_info.json`.
- Yedek tetikleyicileri: zamanlayıcı, teklif kaydı, kapanış, manuel.
- Geri yükleme sonrası uygulama **yeniden başlatılır**; kapanışta ikinci bir kapanış yedeği alınmaz.

## Test izolasyonu

`tests/conftest.py` proje importlarından **önce** `LOCALAPPDATA`, `APPDATA`, `USERPROFILE`, `HOME`, `HOMEDRIVE`, `HOMEPATH`, `TMP`, `TEMP` değişkenlerini tek geçici köke yönlendirir ve keyring'i sahte bir uygulamayla değiştirir. Bu yüzden testler **daima** `python -m pytest tests -q` ile çalıştırılır; `unittest discover` kullanılmaz. Ayrıntı: [TESTING_GUIDE.md](TESTING_GUIDE.md).
