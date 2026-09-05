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
  - ui/startup_splash.py
last_verified_commit: efcfdcb
last_verified_date: 2026-09-05
volatile: false
---

# Mimari

## Proje ne yapar (kanonik tanım)

> **Teklif Yönetim Sistemi; müşteri ve ürün kataloğunu yönetmek, fiyatlandırılmış teklifler oluşturmak, PDF/e-posta çıktıları üretmek ve tekliflerin yaşam döngüsünü güvenli biçimde takip etmek için geliştirilmiş Windows masaüstü uygulamasıdır.**

Bu tanım **yalnız burada** tutulur; diğer belgeler tekrar etmez, bu bölüme bağlantı verir.

## Teknoloji ve dağıtım

**PySide6 (Qt6) + SQLite**, tek süreç, tek pencere + modal diyaloglar. Dağıtım **PyInstaller onedir + Inno Setup**. Dosya→sorumluluk eşlemesi: [MODULE_MAP.md](MODULE_MAP.md).

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
2. **Tek örnek kilidi**: Windows named mutex `TeklifYonetimSistemi_AppMutex` + `QSharedMemory`. İkisi de alınmadan globaller kirletilmez; kısmi edinim bırakılmaz. Yeniden başlatma ardılında kilit sınırlı süre (`core/restart.LOCK_WAIT_S`) beklenir.
3. `core/app_paths` import edilir → veri/yedek klasörleri oluşur ([DATA_AND_PATHS.md](DATA_AND_PATHS.md)).
4. Loglama kurulur; 30 günden eski log dosyaları silinir.
5. `exception_hook` kurulur — windowed derlemede de görünür hata penceresi + log yolu ([SECURITY_AND_PRIVACY.md](SECURITY_AND_PRIVACY.md)).
6. `QApplication`, Türkçe locale/çeviri, ikon ve font hazırlanır; splash bileşeni `ui/startup_splash.py` içinden oluşturulur.
7. Veri yoksa yedekten geri yükleme sorulur; **yalnız tam başarıda** ardıl süreç başlatılır. Geri yükleme üç sonucu ayırır (`preflight_failed` / `rolled_back` / `rollback_failed`) ve başarısız hiçbir durumda yeniden başlatma yapılmaz — ayrıntı [DATA_AND_PATHS.md](DATA_AND_PATHS.md).
8. `MainWindow` açılır; otomatik yedek zamanlayıcısı ve güncelleme kontrolü başlar.
9. **Açılış bildirimleri splash'ten SONRAYA ertelenir.** `MainWindow` oluşturulurken `_navigate(0)` Dashboard verisini **yükler**, ama süresi dolan/dolacak teklif bildirimleri gösterilmez — o an ekranda yalnız splash vardır. Ayarlar sayfasındaki güvenli depo okuma hatası da yalnız güvenli metin olarak saklanır; modalı burada açılmaz. Splash fade'i **gerçekten tamamlanınca** (`finished`) `window.acilis_bildirimlerini_planla()` çağrılır; bu, pencereye ait tek atımlık zamanlayıcıyla bildirimleri **bir sonraki event-loop turuna** bırakır. Pencere görünür değilse veya kapanış hazırlığı başladıysa modal **açılmaz**; her açılış bildirimi en fazla **bir kez** gösterilir. Sabit gecikme kullanılmaz.

## Thread / worker düzeni

- Uzun iş (yedek alma, e-posta, güncelleme indirme) `QThread` worker'ında çalışır; widget'a yalnız ana thread'den dokunulur.
- Biten worker'lar `deleteLater` ile serbest bırakılır; çalışan worker referansı `AutoBackupService.active_worker()` üzerinden dışarı verilir.
- `MainWindow.closeEvent` önce otomatik yedek zamanlayıcısını susturur. Çalışan yedek varsa onun bitmesini bekler; aynı veritabanı için paralel ikinci yedek başlatmaz. Normal kapanış yedeği tamamlandıktan sonra `_shutdown_workers()` kalan çalışan worker'ları toplar (kimlik tekilleştirmesiyle), kapanışı erteler ve **worker bitmeden teardown yapmaz**. Böylece çalışan `QThread` yok edilmesinden doğan `0xC0000409` oluşmaz.

## Kapanış ve yeniden başlatma

- **Normal kapanış:** yeni otomatik yedek istekleri durdurulur → varsa aktif yedek bitirilir → kapanış yedeği tam bir kez alınır → kalan worker'lar bitirilir → DB kapatılır → çıkış kodu 0.
- **Restart (geri yükleme sonrası):** `core/restart.request_restart()` yalnız istek kaydeder. Kapanışta yeni kapanış yedeği **alınmaz**; normal Qt/DB kapanışı işletilir, ardıl süreç `spawn_successor` ile başlatılır ve `--restarted-from <pid>` bayrağı taşınır. Ardıl, tek örnek kilidini sınırlı süre bekler. `os.execl` kullanılmaz.
- Komut satırı üretimi saf fonksiyondur (`build_restart_command`); frozen'da EXE yolu bir kez geçer.

## Güncelleme

`ui/utils/updater.py` GitHub Releases API'sinden son tag'i okur, **yalnız `TeklifYonetim_Setup_<tag>.exe` adına birebir uyan tek asset'i** seçer, indirir ve `os.startfile` ile Inno kurulumunu başlatır (UAC yükseltmesi installer manifestinden gelir). Kaynak modda tarayıcıya yönlendirir. Onefile veya EXE üzerine kopyalama yoluna dönülmez.

**Veri güvenli güncelleme kapanışı.** Paketli modda doğrulanmış installer hemen çalıştırılmaz. `UpdateDialog` ana pencerenin normal `closeEvent` akışını çağırır; kaydedilmemiş işlem onayı, kapanış yedeği ve worker bekleme tamamlanır. Kullanıcı kapanışı iptal ederse indirilen installer silinir ve başlatılmaz. Kapanış kabul edilirse installer yolu kuyruğa alınır; `main.py` olay döngüsü döndükten ve `_veritabanini_kapat()` tamamlandıktan sonra `os.startfile` çağrılır. Başlatma hatası yalnız istisna sınıfıyla loglanır ve sabit güvenli mesaj gösterilir.

**Güven zinciri (fail-closed).** Seçim ve doğrulama Qt'den bağımsız saf yardımcılardadır (`select_update_asset`, `is_release_download_url`, `is_allowed_download_host`); `UpdateChecker` ve `StartupUpdateChecker` aynı yardımcıyı kullanır. İndirme yalnız şu koşulların tamamı sağlanırsa çalıştırılır:

- URL `https://github.com/IzzmooPro/OfferManager/releases/download/<tag>/<beklenen ad>` ile birebir aynı (tam hostname eşleşmesi; suffix/prefix/userinfo/port hilesi reddedilir)
- Aynı beklenen ada sahip **tek** asset var; başka `.exe`'ler **seçilmez**
- API `size` pozitif tam sayı, `digest` tam olarak `sha256:<64 hex>`
- Redirect sonrası son URL HTTPS ve `github.com` / `objects.githubusercontent.com` / `release-assets.githubusercontent.com`
- Yazılan gerçek bayt sayısı = `size`, varsa `Content-Length` = `size`, SHA-256 = `digest`

Doğrulama başarısızsa yarım dosya silinir, `os.startfile` / `os._exit` / tarayıcı **çalışmaz**, kullanıcıya tek kısa mesaj gösterilir; manuel GitHub sayfası ayrı bir kullanıcı seçimidir. Teknik neden yalnız log'a yazılır.

**Sınır:** digest de release metadata'sından gelir → bozuk/eksik CDN indirmesini ve yanlış asset seçimini engeller, **ele geçirilmiş GitHub release metadata'sına karşı bağımsız güven kökü değildir** (kod imzası yok — [KNOWN_RISKS.md](KNOWN_RISKS.md) R5).

## Hata bildirimi

Teknik hatalar `ui/utils/operation_error.py` üzerinden **güvenli mesaja** ve kişisel veri içermeyen loga çevrilir; kullanıcıya gösterim `ui/utils/operation_error_dialog.py` ince sarmalayıcısıyla yapılır. Diyalog kapanmaz, kullanıcı düzeltip yeniden dener.

Ana girişteki beklenmeyen `Exception`, `_run_entrypoint()` tarafından ortak `exception_hook`'a tam bir kez aktarılır ve sayısal çıkış kodu 1'e çevrilir. Böylece windowed PyInstaller bootloader'a ham istisna kaçmaz; güvenli uygulama penceresine ek ikinci traceback penceresi oluşmaz. `SystemExit` ve `KeyboardInterrupt` bilinçli çıkış davranışlarını korur.

Bu ortak altyapı yalnız kaydetme/silme yollarında değil; teklif, kategori, dashboard, rapor, ayarlar, yedekleme/geri yükleme ve içe/dışa aktarma yollarında da kullanılır. Değişmeyen iki sınır: **aynı istisna en fazla bir kez** güvenli loglanır (loglama sorumluluğu tek katmandadır) ve **çok aşamalı akışlarda sonraki aşamanın hatası tamamlanmış aşamayı inkâr etmez** — uzun işlem penceresi hata, iptal ve başarı yollarının hepsinde kapanır. Ayrıntı ve koruyan testler: [CRITICAL_INVARIANTS.md](CRITICAL_INVARIANTS.md) 18 / 18-1 / 18b.

Bu davranışlar **kaynak testi** ile doğrulanmıştır; paketli EXE veya installer kanıtı değildir ([VERIFICATION_GUIDE.md](VERIFICATION_GUIDE.md) kanıt sınıfları).
