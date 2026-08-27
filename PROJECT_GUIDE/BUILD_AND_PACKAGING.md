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
last_verified_commit: 2fbb931
last_verified_date: 2026-08-27
volatile: false
---

# Build ve paketleme

## Tek komut

```
packaging/Kurulum-Yap.bat --no-pause
```

Adımlar: araç kontrolü → **`python -m pytest tests -q`** → eski `build/`, `dist/`, `installer_output/` temizliği → PyInstaller (onedir) → Inno Setup → dosya doğrulama. Testler kırmızıysa build durur. Sürüm `core/constants.py` içinden okunur, elle yazılmaz.

Build betiği gerçek Python executable yolunu başta sabitler; sürümü tırnaklı
Python yolunu bozmadan benzersiz geçici dosya üzerinden okur. PyInstaller adımında
`PATH`, yalnız Python ve Windows sistem klasörlerinden oluşan kontrollü listeye
daraltılır. Böylece Codex/ofis araçlarının eklediği Poppler, libheif veya
başka native DLL klasörleri pakete yanlış bağımlılık olarak girmez.

## PyInstaller (`packaging/TeklifYonetim.spec`)

- **onedir** (onefile değil): onefile her açılışta `Temp\_MEI` altına açılıyordu; antivirüs/Temp temizliği bunu bozduğunda "Failed to load Python DLL" hatası çıkıyordu.
- `console=False` (windowed), `disable_windowed_traceback=True`; beklenmeyen ana-akış hatası önce uygulamanın güvenli hata penceresine/loguna aktarılır ve `SystemExit(1)` olur, bootloader ham traceback göstermez. İkon `assets/ico.ico`, sürüm kaynağı `packaging/version_info.txt`.
- `datas`: `assets/` ve `database/schema.sql`.
- `hiddenimports`: `PySide6.QtPdf`, `PySide6.QtPdfWidgets`, `keyring.backends.Windows`.
- Yollar `SPECPATH` üzerinden mutlaklaştırılır; hangi dizinden çalışılırsa çalışılsın çözülür.

## Inno Setup (`packaging/TeklifYonetim.iss`)

- Sabit `AppId` (upgrade aynı kaydı günceller), `DefaultDirName={autopf}\Teklif Yönetim`, `PrivilegesRequired=admin`, `ArchitecturesInstallIn64BitMode=x64compatible`.
- `UsePreviousAppDir=yes`, `UsePreviousTasks=yes`.
- `[Files]`: yalnız `dist\TeklifYonetim\*` → `{app}` (`ignoreversion recursesubdirs createallsubdirs`).
- `[InstallDelete]`: yalnız yeni pakette artık bulunmayan iki eski OpenSSL adı
  (`_internal\libcrypto-3-x64.dll`, `_internal\libssl-3-x64.dll`) yerinde
  yükseltmede silinir. Joker, klasör veya kullanıcı verisi temizliği yoktur.
- `[Icons]`: grup kısayolu, kaldırma kısayolu, isteğe bağlı masaüstü kısayolu (varsayılan işaretli).
- `[Run]`: kurulum sonrası uygulamayı açar — `skipifsilent` olduğu için sessiz kurulumda açılmaz.
- `[Code]`: `InitializeUninstall` (Inno 7 kaldırıcı hatasını atlatmak için **silinmez**) ve `PrepareToInstall` içinde `taskkill /F /IM TeklifYonetim.exe`.
- `AppMutex` **bilerek yok**; `CloseApplications=yes` + `SetupMutex` kullanılır. Bu denge korunur.
- `[Registry]`, `[UninstallDelete]`, `[UninstallRun]` bölümü yoktur — kaldırma kullanıcı verisine dokunmaz.

## Sürüm alanları (hepsi eşleşmeli)

`core/constants.py:APP_VERSION` ↔ `.iss` `MyAppVersion` ↔ `.iss` `VersionInfoVersion`/`VersionInfoProductVersion` ↔ `packaging/version_info.txt` ↔ installer dosya adı ↔ (yayınlanacaksa) `vX.Y` tag'i.

## Local-only gerçeği

`packaging/TeklifYonetim.iss` D21 kararıyla izlenir; güvenli upgrade reçetesi ve
dar eski-dosya temizliği böylece Git geçmişinde kalır. `packaging/` altındaki
diğer girdiler (`.spec`, `version_info`, build BAT'ları ve kaynak görseller),
`assets/`, `dist/`, `installer_output/`, `build/`, `Import_Test/` ve diğer `.bat`
başlatıcılar **`.gitignore` ile depo dışındadır**. Bu bilinçli sınırın sonucu:

> **Temiz bir clone'dan build almak şu an tekrarlanabilir değildir.** Paketleme yalnız bu yerel makinede yapılabilir.

Depoda kalan paketleme istisnası yalnız `packaging/TeklifYonetim.iss` dosyasıdır;
bu istisna tek başına temiz clone build'ini mümkün kılmaz.

## Bilinen zararsız uyarılar

PyInstaller `warn-*.txt` dosyasında yüzlerce "missing module" satırı olur; bunlar platforma özgü (keyring'in Linux arka uçları, `fcntl`, `macfs`) veya isteğe bağlı (reportlab `renderPM`, openpyxl `lxml`) modüllerdir. `win32ctypes.core._common` da statik analiz artefaktıdır; gerçek ctypes arka ucu pakete girer. Ayrıntılı kanıt: [VERIFICATION_GUIDE.md](VERIFICATION_GUIDE.md).

Güncel artifact değerleri: [project_manifest.json](project_manifest.json) ve [CURRENT_STATUS.md](CURRENT_STATUS.md).
