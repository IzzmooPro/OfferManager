---
purpose: Yayın öncesi zorunlu sıra ve GitHub yayın akışı.
read_when: Release hazırlığı ve yayın anı.
covers:
  - core/constants.py
  - packaging/TeklifYonetim.iss
  - packaging/version_info.txt
  - packaging/Kurulum-Yap.bat
  - ui/utils/updater.py
last_verified_commit: 060baf3
last_verified_date: 2026-07-28
volatile: false
---

# Yayın kontrol listesi

Sıra atlanmaz. Her adım kanıtla kapatılır; kanıt sınıfları [VERIFICATION_GUIDE.md](VERIFICATION_GUIDE.md).

## 1. Kaynak hazır

- [ ] `git status` temiz, `HEAD == origin/main`
- [ ] `python -m pytest tests -q` yeşil
- [ ] `py_compile` tüm proje dosyalarında temiz
- [ ] Açık riskler gözden geçirildi ([KNOWN_RISKS.md](KNOWN_RISKS.md))

## 2. Sürüm eşleşmesi

- [ ] `core/constants.py:APP_VERSION` hedef sürüm
- [ ] `.iss` `MyAppVersion` aynı; `VersionInfoVersion` / `VersionInfoProductVersion` sayısal karşılığı
- [ ] `packaging/version_info.txt` `filevers`/`prodvers`/`ProductVersion` aynı
- [ ] Installer dosya adı `TeklifYonetim_Setup_<sürüm>.exe`
- [ ] Yayınlanacak tag `vX.Y` aynı sürümü gösteriyor

## 3. Temiz build

- [ ] `packaging/Kurulum-Yap.bat --no-pause` → exit 0 (testler + PyInstaller + Inno)
- [ ] Yeni EXE/installer SHA256'ları eskisinden farklı
- [ ] `dist/TeklifYonetim` içinde `dist` dışı artık dosya yok
- [ ] Pakette gerçek kullanıcı verisi (DB, log, yedek, PDF), `tests/`, `Import_Test/`, `.git` yok
- [ ] `project_manifest.json` snapshot alanları güncellendi

## 4. Paketli doğrulama (kanıt sınıfı B)

- [ ] İzole frozen smoke geçti ([VERIFICATION_GUIDE.md](VERIFICATION_GUIDE.md))

## 5. Installer doğrulaması (kanıt sınıfı C)

- [ ] Rollback yedeği alındı ve doğrulandı
- [ ] Upgrade → uygulama smoke → kaldırma → temiz yeniden kurulum geçti
- [ ] Kaldırmada kullanıcı verisi korundu

## 6. Yayın

- [ ] Commit (yalnız açık istek üzerine)
- [ ] Push → `origin/main` ile senkron doğrulandı
- [ ] Tag `vX.Y` oluşturuldu ve push edildi
- [ ] GitHub Release oluşturuldu; **setup `.exe` asset olarak yüklendi** (updater ilk `.exe` asset'ini indirir)
- [ ] Yayın sonrası read-back: tag, release ve indirilebilir asset doğrulandı
- [ ] `docs/CHANGELOG.md` güncellendi

## Depo gerçeği

GitHub'da yalnız kaynak kod, `tests/`, `README.md`, `docs/CHANGELOG.md`, `requirements.txt`, `.gitignore`, `CLAUDE.md`, `AGENTS.md` ve `PROJECT_GUIDE/` bulunur. `packaging/`, `assets/`, `dist/`, `installer_output/`, `build/`, `Import_Test/` ve `.bat` başlatıcılar yereldir; bu yüzden **release yalnız bu makinede üretilebilir** ([BUILD_AND_PACKAGING.md](BUILD_AND_PACKAGING.md)).

## Açık kararlar

- Kod imzası yok → SmartScreen uyarısı sürer.
- `060baf3` için sürüm numarası/tag/release kararı **henüz verilmedi** ([CURRENT_STATUS.md](CURRENT_STATUS.md)).
