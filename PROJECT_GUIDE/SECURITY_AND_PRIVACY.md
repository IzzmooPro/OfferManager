---
purpose: Gizlilik sınırları, credential yönetimi ve güvenli hata/log davranışı.
read_when: Credential, SMTP, log, hata mesajı, çıktı (PDF/Excel/e-posta) işleri.
covers:
  - core/credential_store.py
  - core/config.py
  - ui/utils/operation_error.py
  - ui/dialogs/email_dialog.py
  - main.py
last_verified_commit: 060baf3
last_verified_date: 2026-07-28
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

- Kullanıcıya gösterilen kaydetme/silme hatası sabit metinlerden seçilir; `str(exception)`, traceback, SQL veya dosya yolu içermez. Ürün kodu çakışmasında mesaj istisnanın **alanlarından** üretilir (duck typing yok, `isinstance` kontrolü).
- Log satırı: işlem adı + istisna sınıf adı + güvenli kayıt id'si + traceback'in yalnız `dosya:satır fonksiyon` çerçeveleri. `exc_info` kullanılmaz.
- Paketlenmiş windowed derlemede yakalanmamış istisna sessizce kaybolmaz: görünür hata penceresi + log dosyası yolu gösterilir; aynı hata kısa süre içinde tekrar ederse bastırılır.

## Çıktı gizliliği

- **Maliyet (alış fiyatı) ve kâr bilgisi** PDF, Excel, CSV ve e-posta çıktılarına dahil edilmez; yalnız uygulama içi kâr panelinde görünür.
- Müşteriye ait alanlar çıktıya yazılırken escape/normalize edilir.

## Ağ

- Uygulamanın tek dış bağlantısı GitHub Releases sürüm kontrolüdür. Testlerde ve smoke turlarında ağ proxy ile kapatılır; gerçek SMTP gönderimi yapılmaz.

## Kod imzası

Üretilen EXE ve installer **imzasızdır**; SmartScreen "bilinmeyen yayımcı" uyarısı beklenir. Bu açık bir risktir ([KNOWN_RISKS.md](KNOWN_RISKS.md)).
