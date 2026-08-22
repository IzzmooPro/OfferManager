---
paths:
  - "core/{credential_store,feedback_report}.py"
  - "ui/dialogs/{email_dialog,feedback_dialog}.py"
  - "ui/utils/{operation_error,operation_error_dialog,updater}.py"
  - "ui/settings_page.py"
  - "tests/test_{credential_store,feedback_report,smtp_security,windowed_error_reporting,updater_asset_verification}.py"
---

# Güvenlik ve gizlilik

Önce `PROJECT_GUIDE/INDEX.md` üzerinden `SECURITY_AND_PRIVACY.md` ve ilgili
değişmezleri seç; bu rule kanonik belgenin yerine geçmez.

- Parola, token, credential, ham istisna, traceback, SQL, mutlak yol veya müşteri/firma verisini rapor, UI ya da panoya taşıma.
- Kullanıcı e-posta istemcisinde taslak açılmasını "gönderildi" diye raporlama; pano yalnız açık tıklamayla değişsin.
- Updater asset adı, URL/host, boyut ve SHA-256 doğrulamalarından herhangi biri belirsizse fail-closed davran; installer'ı başlatma.
- Gerçek Credential Manager, SMTP, tarayıcı, ağ ve kullanıcı profili yalnız açık yetkiyle kullanılır; kaynak testlerinde sahte/izole sınır kullan.
- Aynı istisnayı katmanlar arasında tekrar loglama ve teknik ayrıntıyı kullanıcı mesajına sızdırma.
