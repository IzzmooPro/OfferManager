---
purpose: Uygulamanın çalışma zamanı mimarisi — akış, katmanlar, thread ve kapanış düzeni.
read_when: Genel yönelim, worker/kapanış/restart işi, yeni özellik tasarımı.
covers:
  - main.py
  - core/restart.py
  - core/app_paths.py
  - database/db_manager.py
  - ui/main_window.py
  - ui/dialogs/backup_manager.py
  - ui/utils/updater.py
last_verified_commit: 060baf3
last_verified_date: 2026-07-28
volatile: false
---

# Mimari

Windows masaüstü uygulaması: **PySide6 (Qt6) + SQLite**, tek süreç, tek pencere + modal diyaloglar. Dağıtım **PyInstaller onedir + Inno Setup**. Dosya→sorumluluk eşlemesi: [MODULE_MAP.md](MODULE_MAP.md).

## Katmanlar

```
main.py  →  ui/  →  services/  →  database/db_manager.py  →  SQLite
                     ↘ models/ (veri sınıfları)
                     ↘ pdf/, core/ (yol, config, credential, restart, kâr)
```

- **UI** iş kuralı barındırmaz; servis çağırır ve sonucu gösterir.
- **Servis** doğrulama + transaction sahibidir. Çok satırlı yazma tek `db.transaction()` içinde yapılır.
- **models/** yalın veri taşıyıcılarıdır.
- **core/** UI'dan bağımsızdır (yol çözümü, config, credential, restart, kâr hesabı).

## Başlangıç sırası (`main.py`)

1. Kaynak modda bağımlılık kontrolü (frozen'da atlanır).
2. **Tek örnek kilidi**: Windows named mutex `TeklifYonetimSistemi_AppMutex` + `QSharedMemory`. İkisi de alınmadan globaller kirletilmez; kısmi edinim bırakılır. Yeniden başlatma ardılında kilit sınırlı süre (`core/restart.LOCK_WAIT_S`) beklenir.
3. `core/app_paths` import edilir → veri/yedek klasörleri oluşur ([DATA_AND_PATHS.md](DATA_AND_PATHS.md)).
4. Loglama kurulur; 30 günden eski log dosyaları silinir.
5. `exception_hook` kurulur — windowed derlemede de görünür hata penceresi + log yolu ([SECURITY_AND_PRIVACY.md](SECURITY_AND_PRIVACY.md)).
6. `QApplication`, Türkçe locale/çeviri, ikon, font, splash.
7. Veri yoksa yedekten geri yükleme sorulur; geri yükleme yapıldıysa **ardıl süreç** başlatılır.
8. `MainWindow` açılır; otomatik yedek zamanlayıcısı ve güncelleme kontrolü başlar.

## Thread / worker düzeni

- Uzun iş (yedek alma, e-posta, güncelleme indirme) `QThread` worker'ında çalışır; widget'a yalnız ana thread'den dokunulur.
- Biten worker'lar `deleteLater` ile serbest bırakılır; çalışan worker referansı `AutoBackupService.active_worker()` üzerinden dışarı verilir.
- `MainWindow.closeEvent` → `_shutdown_workers()` çalışan tüm worker'ları toplar (kimlik tekilleştirmesiyle), kapanışı erteler ve **worker bitmeden teardown yapmaz**. Böylece çalışan `QThread` yok edilmesinden doğan `0xC0000409` oluşmaz.

## Kapanış ve yeniden başlatma

- **Normal kapanış:** kapanış yedeği → DB kapatılır → çıkış kodu 0.
- **Restart (geri yükleme sonrası):** `core/restart.request_restart()` yalnız istek kaydeder. Kapanışta yeni kapanış yedeği **alınmaz**; normal Qt/DB kapanışı işletilir, ardıl süreç `spawn_successor` ile başlatılır ve `--restarted-from <pid>` bayrağı taşınır. Ardıl, tek örnek kilidini sınırlı süre bekler. `os.execl` kullanılmaz.
- Komut satırı üretimi saf fonksiyondur (`build_restart_command`); frozen'da EXE yolu bir kez geçer.

## Güncelleme

`ui/utils/updater.py` GitHub Releases API'sinden son tag'i okur, `.exe` asset'ini indirir ve `os.startfile` ile Inno kurulumunu başlatır (UAC yükseltmesi installer manifestinden gelir). Kaynak modda tarayıcıya yönlendirir. Onefile veya EXE üzerine kopyalama yoluna dönülmez.

## Hata bildirimi

Kaydetme/silme hataları `ui/utils/operation_error.py` üzerinden **güvenli mesaja** ve kişisel veri içermeyen loga çevrilir; diyalog kapanmaz, kullanıcı düzeltip yeniden dener. Ayrıntı: [CRITICAL_INVARIANTS.md](CRITICAL_INVARIANTS.md).
