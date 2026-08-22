---
paths:
  - "database/**/*.py"
  - "database/schema.sql"
  - "core/{app_paths,config,credential_store}.py"
  - "services/**/*.py"
  - "ui/dialogs/backup_manager.py"
  - "scripts/clear_for_distribution.py"
---

# Veri ve iş mantığı güvenliği

- Testleri gerçek `%LOCALAPPDATA%` verisine bağlama; pytest/conftest izolasyonunu koru.
- Migration'lar geriye uyumlu ve idempotent olsun. Yeni tablo/sütunu schema, migration, model, servis, yedek/geri yükleme ve testlerle birlikte düşün.
- Çok satırlı yazma/silme/güncellemede satır başına commit yapma; tek `db.transaction()` kullan. Aynı transaction içinde ikinci writer açma.
- Teklif numarası ve ilişkili kayıtlar atomik kalsın; kısmi hatada rollback davranışını test et.
- Veri klasörü adını ve mevcut kullanıcı dosyalarını koru. Dağıtım temizliği ancak açık izinle, önce yedek alarak çalışsın.
- SMTP parolasını loglama/config'e düz metin yazma; Windows Credential Manager yolunu koru.
