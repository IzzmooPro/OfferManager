---
purpose: Gizlilik sınırları, credential yönetimi ve güvenli hata/log davranışı.
read_when: Credential, SMTP, log, hata mesajı, çıktı (PDF/Excel/e-posta) işleri.
covers:
  - core/credential_store.py
  - core/config.py
  - ui/utils/operation_error.py
  - ui/utils/operation_error_dialog.py
  - core/feedback_report.py
  - ui/dialogs/feedback_dialog.py
  - core/app_paths.py
  - ui/dialogs/email_dialog.py
  - main.py
  - services/export_service.py
last_verified_commit: efcfdcb
last_verified_date: 2026-09-05
volatile: false
---

# Güvenlik ve gizlilik

## Sınırlar

- **Gerçek kullanıcı verisi** (veritabanı, yedekler, ayarlar, Credential Manager) yalnız kullanıcının açık izniyle ve yalnız belirtilen kapsamda değiştirilir. Testler ve deneyler daima izole kökte çalışır ([DATA_AND_PATHS.md](DATA_AND_PATHS.md)).
- Bu rehberde ve kodda **gerçek kişisel veri, firma bilgisi, parola veya kullanıcıya özel mutlak Windows yolu yazılmaz**; yalnız `<PROJECT_ROOT>`, `<USER_DATA_ROOT>`, `<BACKUP_ROOT>`, `<TEMP_ROOT>` kullanılır. Bunu `scripts/verify_project_guide.py` denetler.

## Credential

- SMTP parolası **yalnız Windows Credential Manager**'da tutulur (`keyring.backends.Windows`). Config dosyasına düz metin yazılmaz.
- Depoda düz metin parola bulunursa güvenli depoya taşınır ve config alanı temizlenir; taşıma başarısızsa config **temizlenmez**.
- Okuma hatası **sessizce yutulmaz**: `CredentialStoreError` fırlatılır ve kullanıcıya kısa bir uyarı gösterilir ("kayıtlı şifre okunamadı; boş görünen alan silindiği anlamına gelmez").
- Okuma hatasından doğan boş değer **silme işlemine dönüştürülmez**.
- Loglara yalnız istisna **sınıf adı** yazılır; parola, kullanıcı adı veya arka uç ayrıntısı yazılmaz.

## Hata mesajı ve log

- Kullanıcıya gösterilen hata sabit metinlerden seçilir; `str(exception)`, traceback, SQL, yerel dosya yolu ya da müşteri/firma/teklif adı içermez. Ürün kodu çakışmasında mesaj istisnanın **alanlarından** üretilir (duck typing yok, `isinstance` kontrolü).
- **"Log Klasörünü Aç" düğmesi** (`ui/utils/operation_error_dialog.py`): yalnız beklenmeyen/teknik hatalarda eklenir. Tıklanmadıkça `os.startfile` **çağrılmaz**; tıklanınca yalnız kanonik `core.app_paths.LOG_DIR` açılır — yol istisnadan veya kullanıcı girdisinden türetilmez ve **mesaj metninde gösterilmez**. Klasör yoksa ya da açma başarısız olursa ikinci pencere açılmaz, istisna sızmaz, yalnız istisna **sınıf adı** warning olarak loglanır (özyineleme yok). → `tests/test_operation_error_dialog.py`
- Log satırı: işlem adı + istisna sınıf adı + güvenli kayıt id'si + traceback'in yalnız `dosya:satır fonksiyon` çerçeveleri. `exc_info` kullanılmaz. Toplu işlemlerde her istisna **tam bir kez** ayrı ayrı loglanır; ham metinler birleştirilmez. Başarı loglarında tam kullanıcı dosya yolu yazılmaz — yalnız güvenli kayıt id'si.
- Paketlenmiş windowed derlemede yakalanmamış `Exception` sessizce kaybolmaz: ana giriş hatayı ortak hook'a tam bir kez aktarır; kullanıcıya tek güvenli Türkçe hata penceresi + log dosyası yolu gösterilir ve süreç exit code 1 ile biter. Ham traceback PyInstaller bootloader'a kaçmadığı için ikinci teknik hata penceresi açılmaz; teknik traceback yalnız uygulama logunda tam bir kez bulunur. Aynı hata kısa süre içinde tekrar ederse bastırılır. `SystemExit` ve `KeyboardInterrupt` bu sarmalayıcı tarafından yakalanmaz. → `tests/test_windowed_error_reporting.py`
- Güncelleme installer'ı DB kapandıktan sonra başlatılamazsa kullanıcıya yalnız sabit güvenli mesaj gösterilir; installer yolu ve ham istisna sızmaz, log yalnız istisna sınıfını taşır. → `tests/test_update_graceful_shutdown.py`

## Hata/öneri raporu (R11)

- **Otomatik gönderim ve otomatik veri toplama yoktur.** Rapor yalnız kullanıcının kendi e-posta istemcisinde TASLAK olarak açılır ya da panoya kopyalanır; program ağa çıkmaz, SMTP hesabını ve Credential Manager'daki parolayı kullanmaz. "Rapor gönderildi" **denmez**.
- Rapora giren alanların **tamamı pencerede görünür**: rastgele rapor no, yerel tarih/saat, `APP_VERSION`, paketli/kaynak modu, işletim sistemi sürümü + mimari, rapor türü, kullanıcının açıklaması ve (yalnız teknik hata yolunda) güvenli işlem adı, istisna **sınıf adı** ve `dosya.py:satır fonksiyon` özeti.
- Rapora **girmez**: `str(exception)`, istisna mesajı, traceback, SQL, mutlak yol, bilgisayar/kullanıcı adı, kayıt id'si, teklif no, müşteri/ürün/firma verisi, parola, tam log dosyası, ekran görüntüsü. `platform.node()` bilinçli olarak okunmaz; rapor no `uuid4`'tür (MAC taşıyan `uuid1` değil).
- Kullanıcının yazdığı açıklama rapora **aynen** girer — bu tek gerçek sızıntı kanalıdır ve pencerede açıkça uyarılır ("Yazdığınız açıklama rapora aynen girer; kişisel veya müşteri bilgisi yazmayın").
- `mailto:` bağlantısı Qt `QUrl`/`QUrlQuery` ile kurulur ve kullanıcı metni yüzde-kodlanır; CRLF, `&`, `?` ile başlık/query enjeksiyonu yapılamaz. Pencerenin kendi hatası ikinci pencere veya özyineleme üretmez, yalnız istisna **sınıf adı** loglanır. İstisna rapor yolunda **yeniden kaydedilmez**. → `tests/test_feedback_report.py`

## Çıktı gizliliği

- **Maliyet (alış fiyatı) ve kâr bilgisi** PDF, Excel, CSV ve e-posta çıktılarına dahil edilmez; yalnız uygulama içi kâr panelinde görünür.
- Müşteriye ait alanlar çıktıya yazılırken escape/normalize edilir.
- Excel/CSV dışa aktarımında `=`, `+`, `-`, `@` ile başlayan kullanıcı metinleri literal hücre değerine çevrilir; spreadsheet formülü olarak çalıştırılmaz.

## Ağ

- Uygulamanın tek dış bağlantısı GitHub Releases sürüm kontrolüdür. Testlerde ve smoke turlarında ağ proxy ile kapatılır; gerçek SMTP gönderimi yapılmaz.

## Kod imzası

Üretilen EXE ve installer **imzasızdır**; SmartScreen "bilinmeyen yayımcı" uyarısı beklenir. Bu açık bir risktir ([KNOWN_RISKS.md](KNOWN_RISKS.md)).
