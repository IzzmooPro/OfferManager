---
purpose: Build zinciri, PyInstaller/Inno tanımları ve local-only gerçeği.
read_when: Build alırken, paketleme ayarı incelerken.
covers:
  - packaging/TeklifYonetim.spec
  - packaging/TeklifYonetim.iss
  - packaging/Kurulum-Yap.bat
  - packaging/version_info.txt
  - core/constants.py
  - requirements.txt
last_verified_commit: 9e89370
last_verified_date: 2026-08-02
volatile: false
---

# Build ve paketleme

## Tek komut

```
packaging/Kurulum-Yap.bat --no-pause
```

Adımlar: araç kontrolü → **`python -m pytest tests -q`** → eski `build/`, `dist/`, `installer_output/` temizliği → PyInstaller (onedir) → Inno Setup → dosya doğrulama. Testler kırmızıysa build durur. Sürüm `core/constants.py` içinden okunur, elle yazılmaz.

## PyInstaller (`packaging/TeklifYonetim.spec`)

- **onedir** (onefile değil): onefile her açılışta `Temp\_MEI` altına açılıyordu; antivirüs/Temp temizliği bunu bozduğunda "Failed to load Python DLL" hatası çıkıyordu.
- `console=False` (windowed), `disable_windowed_traceback=False`, ikon `assets/ico.ico`, sürüm kaynağı `packaging/version_info.txt`.
- `datas`: `assets/` ve `database/schema.sql`.
- `hiddenimports`: `PySide6.QtPdf`, `PySide6.QtPdfWidgets`, `keyring.backends.Windows`.
- Yollar `SPECPATH` üzerinden mutlaklaştırılır; hangi dizinden çalışılırsa çalışılsın çözülür.

## Inno Setup (`packaging/TeklifYonetim.iss`)

- Sabit `AppId` (upgrade aynı kaydı günceller), `DefaultDirName={autopf}\Teklif Yönetim`, `PrivilegesRequired=admin`, `ArchitecturesInstallIn64BitMode=x64compatible`.
- `UsePreviousAppDir=yes`, `UsePreviousTasks=yes`.
- `[Files]`: yalnız `dist\TeklifYonetim\*` → `{app}` (`ignoreversion recursesubdirs createallsubdirs`).
- `[Icons]`: grup kısayolu, kaldırma kısayolu, isteğe bağlı masaüstü kısayolu (varsayılan işaretli).
- `[Run]`: kurulum sonrası uygulamayı açar — `skipifsilent` olduğu için sessiz kurulumda açılmaz.
- `[Code]`: `InitializeUninstall` (Inno 7 kaldırıcı hatasını atlatmak için **silinmez**) ve `PrepareToInstall` içinde `taskkill /F /IM TeklifYonetim.exe`.
- `AppMutex` **bilerek yok**; `CloseApplications=yes` + `SetupMutex` kullanılır. Bu denge korunur.
- `[Registry]`, `[UninstallDelete]`, `[UninstallRun]` bölümü yoktur — kaldırma kullanıcı verisine dokunmaz.

## Sürüm alanları (hepsi eşleşmeli)

`core/constants.py:APP_VERSION` ↔ `.iss` `MyAppVersion` ↔ `.iss` `VersionInfoVersion`/`VersionInfoProductVersion` ↔ `packaging/version_info.txt` ↔ installer dosya adı ↔ (yayınlanacaksa) `vX.Y` tag'i.

## Local-only gerçeği

`packaging/`, `assets/`, `dist/`, `installer_output/`, `build/`, `Import_Test/` ve `.bat` başlatıcılar **`.gitignore` ile depo dışındadır**. Bu bilinçli bir karardır ([DECISIONS.md](DECISIONS.md)), ancak sonucu şudur:

> **Temiz bir clone'dan build almak şu an tekrarlanabilir değildir.** Paketleme yalnız bu yerel makinede yapılabilir.

Depoda kalanlar: kaynak kod, `tests/`, `README.md`, `docs/CHANGELOG.md`, `requirements.txt`, `.gitignore`, `CLAUDE.md`, `AGENTS.md`, `PROJECT_GUIDE/`.

## Bilinen zararsız uyarılar

PyInstaller `warn-*.txt` dosyasında yüzlerce "missing module" satırı olur; bunlar platforma özgü (keyring'in Linux arka uçları, `fcntl`, `macfs`) veya isteğe bağlı (reportlab `renderPM`, openpyxl `lxml`) modüllerdir. `win32ctypes.core._common` da statik analiz artefaktıdır; gerçek ctypes arka ucu pakete girer. Ayrıntılı kanıt: [VERIFICATION_GUIDE.md](VERIFICATION_GUIDE.md).

Güncel artifact değerleri: [project_manifest.json](project_manifest.json) ve [CURRENT_STATUS.md](CURRENT_STATUS.md).
