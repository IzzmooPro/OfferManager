---
paths:
  - "core/constants.py"
  - "ui/utils/updater.py"
  - "docs/CHANGELOG.md"
  - "packaging/**"
  - "PROJECT_GUIDE/RELEASE_CHECKLIST.md"
  - "PROJECT_GUIDE/VERIFICATION_GUIDE.md"
  - "PROJECT_GUIDE/project_manifest.json"
---

# Build, güncelleme ve yayın

Önce `PROJECT_GUIDE/INDEX.md` release/build satırını uygula; aşağıdaki
kurallar kanonik akışın yerine geçmez.

- Canlı sürümü dosyalardan oku. `APP_VERSION`, Inno `MyAppVersion`, `VersionInfoVersion`, `version_info.txt`, installer adı ve `vX.Y` tag'i eşleşsin.
- PyInstaller `onedir` ve `SPECPATH` tabanlı yolları koru. Inno bütün `dist/TeklifYonetim/` klasörünü paketlesin.
- Build testleri yalnız pytest ile koşsun. `packaging/Kurulum-Yap.bat` eski build/dist/installer çıktılarını siler; eski artifact'i yeni kanıt sayma.
- Updater release'teki gerçek setup `.exe` asset'ini indirip ShellExecute/`os.startfile` ile çalıştırır. Onefile, exe kopyalama veya `subprocess` ile UAC yükseltmeye dönme.
- `AppMutex` ekleme; `SetupMutex`, `CloseApplications` ve `PrepareToInstall` cleanup dengesini koru. Inno `[Code]` bölümü kaldırıcı uyumluluğu için kalır.
- Build, install/uninstall, commit, push, tag, draft ve public release yetkilerini ayrı ayrı ara. Yayın sonrası tag hedefi ile installer asset adı-boyutu-SHA-256 eşitliğini read-back ile doğrula; mevcut asset'in üzerine yazma.
