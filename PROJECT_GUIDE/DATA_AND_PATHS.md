---
purpose: Veri yolları, şema/migration düzeni, import/export ve yedek/geri yükleme davranışı.
read_when: Veri, yol, migration, yedek, import/export işleri.
covers:
  - core/app_paths.py
  - core/offer_files.py
  - database/schema.sql
  - database/db_manager.py
  - ui/utils/excel_import.py
  - services/export_service.py
  - ui/dialogs/backup_manager.py
  - tests/conftest.py
last_verified_commit: efcfdcb
last_verified_date: 2026-09-05
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
- `<BACKUP_ROOT>\` — otomatik ve manuel ZIP yedekler (rotasyon: son 20 tutulur), dosya adı `backup_%Y_%m_%d_%H%M%S_%f.zip`

### `<USER_DATA_ROOT>\data\` envanteri

| Dosya | Sınıf | Kim oluşturur / okur |
|---|---|---|
| `database.db` | **Gerçek kullanıcı verisi** | `database/db_manager.py`; yedeğe girer |
| `company.cfg` | Ayar | `core/config.py` — firma bilgileri, PDF metinleri, SMTP ayarları (parola **burada değil**); yedeğe girer |
| `logo.png`, `signature1..4.png` | Kullanıcı varlığı | `ui/settings_page.py`; yedeğe girer |
| `logo.disabled` | İşaret dosyası | Kullanıcı logoyu tamamen kaldırınca oluşur |
| `theme.txt` | **Ayar/metadata** | `ui/utils/theme_manager.py` yazar ve okur; açık/koyu tema tercihi. Kullanıcı verisi değildir, yedeğe girmez |
| `backup_meta.json` | **Ayar/metadata** | `ui/dialogs/backup_manager.py` yazar ve okur; otomatik yedek açık mı, aralık (varsayılan 30 dk), hedef klasör, son yedek zamanı. Yedeğin kendi içeriğine dahil değildir |
| `.migrated` | İşaret dosyası | `core/app_paths.py` — eski konumdan tek seferlik veri taşımasının yapıldığını işaretler |
| `logs\app_YYYYMMDD.log` | Günlük | `main.py`; 30 günden eskiler silinir |
| `offers_pdf\<teklif_no>.pdf` | Arşiv çıktısı | Teklif kaydında üretilir, teklif silinince kaldırılır |

**Test izolasyonu:** bu dosyaların tamamı `<USER_DATA_ROOT>` altında olduğundan, `tests/conftest.py` ortam değişkenlerini geçici köke yönlendirdiğinde testler kendi `theme.txt` ve `backup_meta.json` dosyalarını üretir; gerçek kullanıcı tercihleri okunmaz ve değiştirilmez.
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
- "Tümünü İçe Aktar (tek dosya)" ayrı yoldur: `Müşteriler`/`Ürünler`/`Teklifler` adlı sayfaları tanır, sayfa sorusu sormaz. Bu yol gizli sayfaları da okur ([KNOWN_RISKS.md](KNOWN_RISKS.md) **R8 açık**).
- **Dosya tanıtıcısı yaşam döngüsü:** okunan çalışma kitabı hem başarı hem hata yolunda `finally` içinde kapatılır — aksi hâlde Windows'ta kaynak dosya kilitli kalırdı. Kapatma hatası ayrı aşamadır; başarılı okumayı geçersiz kılmaz ve asıl okuma hatasını maskelemez.
- **Kategori yazımı ürün transaction'ından ÖNCE ve ondan bağımsız yapılır.** Transaction geri dönse bile oluşturulmuş kategoriler veritabanında kalır; bu bilgi çağırana yalnız **sayısal** aşama durumu olarak taşınır (kategori adı taşınmaz) ve dönüş değeri gerçek veritabanı değişikliğini yansıtır.
- **Teklif içe aktarma miktarı:** boş değer varsayılan `1` olabilir; açık `0`, negatif veya bozuk değer hata üretir ve aynı teklifin tamamını dışarıda bırakır. Teklif numarası Windows dosya adı olarak doğrulanır; geçersiz numara hiçbir teklif kaydı oluşturmaz.

## Dışa aktarma

`services/export_service.py` içe aktarma şablonuyla uyumlu başlıklar üretir; veri yoksa yalnız başlık satırı yazılır (boş şablon işlevi). **Maliyet/kâr sütunu dışa aktarılmaz.** Excel/CSV hücresine yazılan kullanıcı metni, baştaki boşluklar atıldığında `=`, `+`, `-` veya `@` ile başlıyorsa başına tek tırnak eklenerek formül çalıştırması engellenir; sayısal değerler sayısal kalır.

## Yedek ve geri yükleme

- ZIP içeriği: veritabanı anlık kopyası + `company.cfg` + varsa logo/imzalar + `backup_info.json`.
- Yedek tetikleyicileri: zamanlayıcı, teklif kaydı, kapanış, manuel.
- Kapanış başlarken zamanlayıcı susturulur ve yeni asenkron yedek istekleri engellenir. Zaten çalışan yedek 30 saniyede bitmezse aynı veritabanı için paralel kapanış yedeği açılmaz; pencere kapanışı worker'ın yerleşik `finished` sinyaline kadar ertelenir, ardından kapanış yedeği tam bir kez alınır.
- Yedek **dosyası** ile `backup_meta.json` ayrı aşamalardır: metadata yazılamazsa oluşmuş yedek geçersiz sayılmaz ve yeniden alınmaz.
- Geri yükleme **üç sonucu ayırır** (`RestoreError.durum`):

| Durum | Hedef verilerin hâli |
|---|---|
| `preflight_failed` | Hedef verilere **hiç dokunulmadı** (ZIP doğrulanamadı, geçici çalışma alanı açılamadı veya rollback anlık görüntüsü hazırlanamadı) |
| `rolled_back` | Yazma başlamıştı; önceki durum geri getirildi |
| `rollback_failed` | Geri alma **tamamlanamadı**; veri durumu belirsizdir |

- Geri alma ilk hatada durmaz: veritabanı ve tüm optional dosyalar tek tek denenir, geri yükleme öncesindeki **var/yok durumu birebir kurulmaya çalışılır** (baştan bulunmayan dosyalar `-wal`/`-shm` ile birlikte silinir) ve sonunda veritabanı yeniden doğrulanır.
- Geçici çalışma klasörünün temizlenmesi **ayrı aşamadır** ve işin sonucunu değiştirmez: tamamlanmış bir geri yükleme "başarısız" olmaz, oluşmuş durum `rollback_failed`e dönüşmez.
- Bu davranış **"verileriniz kesin korundu" güvencesi değildir**: `rollback_failed` durumunda program bunu açıkça söyler ve yeniden başlatma **yapılmaz**. Geri yükleme sonrası yeniden başlatma yalnız **tam başarıda** ve tam bir kez olur; kapanışta ikinci bir kapanış yedeği alınmaz.
- Yukarıdakiler **kaynak testi** kanıtıdır. Paketli sürümde gerçek geri yükleme → restart zinciri hâlâ denenmemiştir ([KNOWN_RISKS.md](KNOWN_RISKS.md) **R6 açık**).

## Test izolasyonu

`tests/conftest.py` proje importlarından **önce** `LOCALAPPDATA`, `APPDATA`, `USERPROFILE`, `HOME`, `HOMEDRIVE`, `HOMEPATH`, `TMP`, `TEMP` değişkenlerini tek geçici köke yönlendirir ve keyring'i sahte bir uygulamayla değiştirir. Bu yüzden testler **daima** `python -m pytest tests -q` ile çalıştırılır; `unittest discover` kullanılmaz. Ayrıntı: [TESTING_GUIDE.md](TESTING_GUIDE.md).
