"""
Teklif Yönetim Sistemi — Ana giriş noktası  (sürüm: core/constants.py → APP_VERSION)

Başlangıç sırası:
  1. app_paths import → AppData klasörleri oluşturulur + eski veri migrasyonu
  2. Loglama yapılandırılır
  3. Veri klasörü boşsa backup kontrolü yapılır
  4. QApplication + MainWindow oluşturulur
  5. Arka planda güncelleme kontrolü başlar (MainWindow içinde)
"""
import sys, os, time, traceback, logging, ctypes
import importlib.util
from datetime import datetime
from importlib import metadata
from pathlib import Path


# ── Tek örnek kontrolü (Single Instance) ─────────────────────────────────────

_MIN_PYTHON = (3, 12)
_RUNTIME_DEPENDENCIES = (
    # (import adı, dağıtım adı, minimum sürüm)
    ("PySide6", "PySide6", "6.8.0"),
    ("reportlab", "reportlab", "4.0.0"),
    ("PIL", "Pillow", "10.0.0"),
    ("openpyxl", "openpyxl", "3.1.0"),
    ("keyring", "keyring", "23.0.0"),
)


def _version_tuple(value: str):
    """Paket sürümünü karşılaştırılabilir sayısal bir demete çevir."""
    parts = []
    for part in value.split("."):
        digits = "".join(ch for ch in part if ch.isdigit())
        if not digits:
            break
        parts.append(int(digits))
    return tuple(parts)


def _show_startup_error(message: str):
    """Konsol görünmese bile başlangıç hatasını Windows'ta kullanıcıya göster."""
    print(f"\nBAŞLATMA HATASI:\n{message}")
    if sys.platform == "win32":
        try:
            ctypes.windll.user32.MessageBoxW(
                None, message, "Teklif Yönetim Sistemi - Başlatma Hatası", 0x10
            )
        except OSError:
            pass


def _check_runtime_dependencies():
    """Kaynak modunda gerekli paketlerin VARLIĞINI doğrular.

    Eksik/eski paket varsa kullanıcıyı bilgilendirip programı durdurur —
    hiçbir şey İNDİRMEZ / KURMAZ. Paketlenmiş EXE'de her şey gömülü
    olduğundan bu kontrol atlanır.
    """
    if getattr(sys, "frozen", False):
        return

    if sys.version_info < _MIN_PYTHON:
        required = ".".join(map(str, _MIN_PYTHON))
        current = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        raise RuntimeError(
            f"Python {required} veya üzeri gerekiyor (mevcut: {current})."
        )

    missing = []
    for import_name, distribution_name, minimum_version in _RUNTIME_DEPENDENCIES:
        try:
            installed_version = metadata.version(distribution_name)
            import_exists = importlib.util.find_spec(import_name) is not None
        except (metadata.PackageNotFoundError, ImportError, ValueError):
            installed_version = ""
            import_exists = False

        if (
            not import_exists
            or _version_tuple(installed_version) < _version_tuple(minimum_version)
        ):
            missing.append(f"{distribution_name}>={minimum_version}")

    if missing:
        raise RuntimeError(
            "Gerekli Python paketleri eksik veya eski:\n  - "
            + "\n  - ".join(missing)
            + "\n\nKurmak için proje klasöründe şu komutu çalıştırın:\n"
            "    pip install -r requirements.txt"
        )


try:
    _check_runtime_dependencies()
except (OSError, RuntimeError) as exc:
    _show_startup_error(str(exc))
    raise SystemExit(1)


from PySide6.QtCore import QSharedMemory

_shared_memory = None
_win_mutex_handle = None


def _bring_existing_window_forward():
    if sys.platform != "win32":
        return
    hwnd = ctypes.windll.user32.FindWindowW(None, "Teklif Yönetim Sistemi")
    if hwnd:
        ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        ctypes.windll.user32.SetForegroundWindow(hwnd)

def _kismi_edinimi_birak(kernel32, handle, shm) -> None:
    """Başarısız denemede YALNIZ o denemede edinilen kaynakları bırakır.

    Kritik: mutex alınıp paylaşımlı bellek alınamazsa handle açık kalırsa,
    aynı süreç bir sonraki denemede KENDİ handle'ıyla karşılaşıp
    ERROR_ALREADY_EXISTS alır; kilit gerçekten serbest kalsa bile bir daha
    asla edinemez ve yeniden başlatılan süreç 5 sn sonunda başarısız olur.

    Temizlik hatası dışarı SIZDIRILMAZ; yalnız loglanır.
    """
    if shm is not None:
        try:
            if shm.isAttached():
                shm.detach()
        except Exception as e:
            logger.debug("Paylaşımlı bellek bırakılamadı: %s", e)
    if handle and kernel32 is not None:
        try:
            kernel32.CloseHandle(ctypes.c_void_p(handle))
        except Exception as e:
            logger.debug("Mutex handle kapatılamadı: %s", e)


def _try_acquire_single_instance() -> bool:
    """Kilidi BİR kez almayı dener. Pencere öne getirme YAPMAZ.

    Edinim YEREL değişkenlerle yapılır; globallere ancak HER İKİ kaynak da
    (Windows mutex + paylaşımlı bellek) alındıktan sonra aktarılır. Böylece
    kısmi edinim geride açık handle bırakmaz.
    """
    global _shared_memory, _win_mutex_handle

    kernel32 = None
    yerel_handle = None

    # Inno Setup'ın AppMutex denetimiyle ortak Windows mutex'i. Böylece
    # hem ikinci uygulama örneği hem de çalışan uygulama üzerine kurulum engellenir.
    if sys.platform == "win32":
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.argtypes = (
            ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p)
        kernel32.CreateMutexW.restype = ctypes.c_void_p
        kernel32.CloseHandle.argtypes = (ctypes.c_void_p,)
        kernel32.CloseHandle.restype = ctypes.c_int
        handle = kernel32.CreateMutexW(
            None, False, "TeklifYonetimSistemi_AppMutex")
        if not handle:
            return False                    # hiçbir kaynak edinilmedi
        if ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS
            # Mutex BAŞKA sürece ait; yalnız kendi handle'ımız kapatılır,
            # globaldeki (varsa) kendi kilidimize DOKUNULMAZ.
            kernel32.CloseHandle(ctypes.c_void_p(handle))
            return False
        yerel_handle = handle

    yerel_shm = QSharedMemory("TeklifYonetimSistemi_SingleInstance_Mutex")
    if yerel_shm.attach() or not yerel_shm.create(1):
        # Zaten çalışıyor ya da segment oluşturulamadı → bu denemede
        # edinilen her şeyi bırak, globalleri kirletme.
        _kismi_edinimi_birak(kernel32, yerel_handle, yerel_shm)
        return False

    # Yalnız tam başarıda globallere aktar (güçlü referans burada tutulur).
    _win_mutex_handle = yerel_handle
    _shared_memory = yerel_shm
    return True


def _ensure_single_instance(bekleme_s: float = 0.0) -> bool:
    """
    QSharedMemory ile çapraz platform (cross-platform) tek örnek kontrolü.
    Program zaten çalışıyorsa (Windows'ta) mevcut pencereyi öne getirir ve False döner.
    False → çıkış yapılmalı.
    True  → devam edilebilir.

    `bekleme_s` YALNIZ dahili yeniden başlatma işaretiyle açılan ardıl süreç
    için verilir; eski süreç kilidini bırakana kadar SINIRLI süre yeniden
    denenir. Normal kullanıcı açılışında varsayılan 0'dır ve tek denemeyle
    eskisiyle birebir aynı hızlı davranış korunur.

    Başarı ölçütü kilidin GERÇEKTEN alınmasıdır; eski PID'in yaşayıp
    yaşamadığına bakılmaz (PID yeniden kullanımı güvenlik sınırı değildir).
    """
    bitis = time.monotonic() + max(0.0, bekleme_s)
    while True:
        if _try_acquire_single_instance():
            return True
        if time.monotonic() >= bitis:
            _bring_existing_window_forward()
            return False
        time.sleep(0.1)

# ── app_paths import (AppData klasörleri oluşturulur + migrasyon) ─────────────
# Bu import yan etki olarak:
#   - AppData\Local\OfferManagementSystem\data/ oluşturur
#   - Documents\OfferManagementSystem\backups/ oluşturur
#   - Eski exe yanındaki veriyi AppData'ya kopyalar (tek seferlik)
from core.app_paths import (
    ASSET_ROOT, DATA_DIR, LOG_DIR, DB_PATH, BACKUP_DIR
)
# Yeniden başlatma: iki eski yol (os.execl + Popen) TEK ortak mekanizmada.
from core import restart

# ── Loglama ──────────────────────────────────────────────────────────────────
LOG_DIR.mkdir(parents=True, exist_ok=True)
log_filename = LOG_DIR / f"app_{datetime.now().strftime('%Y%m%d')}.log"


def _clean_old_logs(log_dir: Path, keep_days: int = 30):
    """30 günden eski log dosyalarını temizle."""
    cutoff = datetime.now().timestamp() - keep_days * 86400
    for f in log_dir.glob("app_*.log"):
        try:
            if f.stat().st_mtime < cutoff:
                f.unlink()
        except OSError:
            pass


_clean_old_logs(LOG_DIR)


def _kullanilabilir_akis(akis):
    """Yazılabilir bir standart akış mı?

    console=False ile paketlenmiş EXE'de sys.stdin/stdout/stderr None olur
    (ayrık konsolsuz süreçte ölçüldü). Böyle bir akışa bağlanan
    StreamHandler'ın stream'i de None kalır ve her log kaydında sessizce
    handleError'a düşer — kayıt hiçbir yere yazılmaz, yalnız boşa iş yapılır.
    """
    if akis is None:
        return False
    try:
        if getattr(akis, "closed", False):
            return False
        return callable(getattr(akis, "write", None))
    except Exception:
        return False


# Dosya logu HER ZAMAN kurulur; konsol handler'ı yalnız gerçekten yazılabilir
# bir akış varsa eklenir (geliştirmede stdout, o yoksa stderr).
_log_handlers = [logging.FileHandler(str(log_filename), encoding="utf-8")]
_konsol_akisi = next(
    (a for a in (sys.stdout, sys.stderr) if _kullanilabilir_akis(a)), None)
if _konsol_akisi is not None:
    _log_handlers.append(logging.StreamHandler(_konsol_akisi))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
    handlers=_log_handlers,
)
logger = logging.getLogger("main")

sys.path.insert(0, str(ASSET_ROOT))


# ── Global exception hook ─────────────────────────────────────────────────────

_HATA_BASLIGI = "Teklif Yönetim Sistemi - Hata"

# Kullanıcıya gösterilen metin BİLEREK kısadır: istisna metni, traceback,
# dosya yolları ve müşteri/SMTP verisi yalnız log dosyasına yazılır.
_HATA_METNI = (
    "Beklenmeyen bir uygulama hatası oluştu.\n"
    "İşlem tamamlanamamış olabilir.\n\n"
    "Ayrıntılar şu log dosyasına kaydedildi:\n"
    "{log}"
)

_hook_devrede = False        # hook kendi içindeyken tekrar girilmesini engeller

# Aynı hata için pencere selini önleyen KISA bastırma penceresi. Süresiz
# bastırma yapılmaz: kullanıcı 10 saniye sonra aynı işlemi tekrar denerse
# yeniden bilgilendirilmelidir. Bastırılan tekrarlar yine de loglanır.
_AYNI_HATA_BASTIRMA_SN = 10.0
_son_bildirim = (None, 0.0)  # (traceback imzası, _monotonik() zamanı)


def _monotonik() -> float:
    """Geri gitmeyen saat — sistem saati değişse bile bastırma bozulmaz."""
    return time.monotonic()


def _log_handlerlarini_bosalt():
    """Kullanıcıya bir şey göstermeden ÖNCE traceback diske insin."""
    for h in list(logging.getLogger().handlers):
        try:
            h.flush()
        except Exception:
            pass


def _bildir_qt(mesaj: str) -> bool:
    """QApplication varsa ve ANA UI thread'indeysek QMessageBox göster."""
    from PySide6.QtWidgets import QApplication, QMessageBox
    from PySide6.QtCore import QThread
    app = QApplication.instance()
    if app is None:
        return False
    if getattr(app, "closingDown", None) and app.closingDown():
        return False                      # kapanış sırasında widget oluşturma
    if QThread.currentThread() is not app.thread():
        return False                      # widget'a yalnız ana thread dokunur
    QMessageBox.critical(None, _HATA_BASLIGI, mesaj)
    return True


def _bildir_windows(mesaj: str) -> bool:
    """Qt kullanılamıyorsa doğrudan Windows MessageBoxW (konsol gerektirmez)."""
    if sys.platform != "win32":
        return False
    ctypes.windll.user32.MessageBoxW(None, mesaj, _HATA_BASLIGI, 0x10)
    return True


def _bildir_akis(mesaj: str) -> bool:
    """Son çare: yazılabilir bir standart akış varsa oraya yaz."""
    for akis in (sys.stderr, sys.stdout):
        if _kullanilabilir_akis(akis):
            akis.write("\n" + mesaj + "\n")
            try:
                akis.flush()
            except Exception:
                pass
            return True
    return False


def _kullaniciya_bildir(mesaj: str) -> bool:
    """Kısa bir mesajı kullanıcıya ulaştırır — geri düşüş zinciriyle.

    QMessageBox → Windows MessageBoxW → yazılabilir akış. Her adım kendi
    try/except'i içindedir; hiçbir yol çalışmazsa False döner ve İSTİSNA
    FIRLATMAZ. Hem exception_hook hem yeniden başlatma hataları bunu kullanır.
    """
    for bildir in (_bildir_qt, _bildir_windows, _bildir_akis):
        try:
            if bildir(mesaj):
                return True
        except BaseException:
            continue          # bu yol tıkalı → sıradaki geri düşüşü dene
    return False


def exception_hook(exc_type, exc_value, exc_tb):
    """Yakalanmamış Python istisnalarını logla ve kullanıcıya kısaca bildir.

    Windowed EXE'de stdin/stdout/stderr bulunmayabilir; bu yüzden burada
    ASLA input() çağrılmaz ve koşulsuz print yapılmaz. Bildirim sırası:
    QMessageBox → Windows MessageBoxW → yazılabilir akış. Hiçbiri
    çalışmazsa hook sessizce biter; hiçbir koşulda dışarı istisna sızdırmaz.

    Aynı hata art arda tekrarlarsa (ör. her karede patlayan bir paintEvent)
    pencere yalnız _AYNI_HATA_BASTIRMA_SN boyunca bastırılır — süresiz
    DEĞİL. Süre dolduktan sonra kullanıcı aynı hatayı tekrar tetiklerse
    yeniden bilgilendirilir. Farklı bir hata her zaman hemen bildirilir ve
    HER oluşum, bildirim bastırılsa bile log dosyasına yazılır.

    KAPSAM DIŞI: 0xC0000409 gibi native fast-fail çökmeleri (ör. çalışan bir
    QThread yok edilirken) Python'a hiç ulaşmaz ve bu hook tarafından
    YAKALANAMAZ. Onlar iş parçacığı yaşam döngüsü tarafında çözülür.
    """
    global _hook_devrede, _son_bildirim

    try:
        imza = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    except BaseException:
        imza = repr(exc_type)

    # Loglama her zaman ve bildirimden ÖNCE yapılır.
    try:
        logger.critical("=== UYGULAMA HATASI ===\n%s", imza)
        _log_handlerlarini_bosalt()
    except BaseException:
        pass

    if _hook_devrede:
        return
    _onceki_imza, _onceki_zaman = _son_bildirim
    if (imza == _onceki_imza
            and _monotonik() - _onceki_zaman < _AYNI_HATA_BASTIRMA_SN):
        return                    # aynı hata az önce bildirildi (log yazıldı)

    _hook_devrede = True
    try:
        if _kullaniciya_bildir(_HATA_METNI.format(log=log_filename)):
            # Zaman bildirimden SONRA alınır: modal pencere açık kaldığı
            # sürece bastırma süresi işlemeye başlamaz. Hiçbir yol başarılı
            # olmazsa son bildirim zamanı GÜNCELLENMEZ.
            _son_bildirim = (imza, _monotonik())
    except BaseException:
        pass                      # hook dışarı istisna sızdırmaz
    finally:
        _hook_devrede = False


sys.excepthook = exception_hook


# ── Başlangıç veri kontrolü ───────────────────────────────────────────────────

def _check_data_on_startup(app) -> bool:
    """
    Veri klasörü boşsa (database.db yok) yedek klasörünü kontrol eder.
    Yedek bulunursa kullanıcıya sorar, onay gelirse geri yükler.
    True → uygulama yeniden başlatılmalı (geri yükleme yapıldı)
    """
    if DB_PATH.exists():
        return False

    # database.db yok → backup klasörünü kontrol et
    from ui.dialogs.backup_manager import check_and_restore_on_startup
    restored = check_and_restore_on_startup(parent=None)
    if restored:
        # Geri yükleme sonrası yeniden başlat. Süreç BURADA başlatılmaz;
        # yalnız istek kaydedilir, ardıl ortak yoldan (_yeniden_baslat)
        # DB kapatıldıktan sonra açılır.
        logger.info("Backup geri yüklendi, program yeniden başlatılacak.")
        restart.request_restart()
        return True
    return False


_YENIDEN_BASLATILAMADI = (
    "Program yeniden başlatılamadı.\n"
    "Lütfen programı elle yeniden açın.\n\n"
    "Ayrıntılar şu log dosyasına kaydedildi:\n"
    "{log}"
)

_KILIT_ALINAMADI = (
    "Programın önceki kopyası hâlâ kapanmadı.\n"
    "Lütfen birkaç saniye sonra elle yeniden açın.\n\n"
    "Ayrıntılar şu log dosyasına kaydedildi:\n"
    "{log}"
)


def _veritabanini_kapat():
    """Ardıl süreç açılmadan ÖNCE bağlantıyı düzgün kapat."""
    try:
        from database.db_manager import get_db
        get_db().close()
        logger.info("Veritabanı bağlantısı kapatıldı.")
    except Exception as e:
        logger.warning("DB kapatma hatası: %s", e)


def _yeniden_baslat() -> int:
    """Ardıl süreci başlatır ve bu sürecin çıkış kodunu döndürür.

    Yalnız DB kapatıldıktan sonra çağrılır. Başlatma başarısız olursa
    kullanıcıya kısa bir mesaj gösterilir (teknik ayrıntı yalnız logda) ve
    SIFIR OLMAYAN bir kodla çıkılır — geri yükleme yapılmış olsa bile
    uygulama eski/açık bağlantılarla çalışmaya DEVAM ETTİRİLMEZ.
    """
    if restart.spawn_successor(os.getpid()):
        return 0
    _kullaniciya_bildir(_YENIDEN_BASLATILAMADI.format(log=log_filename))
    return restart.EXIT_SPAWN_FAILED


# ── Ana fonksiyon ─────────────────────────────────────────────────────────────

def main():
    # Dahili yeniden başlatma işareti QApplication'a ve uygulamanın normal
    # argümanlarına AKTARILMADAN önce ayrıştırılıp çıkarılır.
    sys.argv, _ebeveyn_pid = restart.parse_restart_flag(sys.argv)

    # Program zaten açıksa mevcut pencereyi öne getir, yeni örnek açma.
    # Yalnız yeniden başlatma ardılıysa eski süreç kilidi bırakana kadar
    # SINIRLI süre yeniden denenir; normal açılışta ek bekleme yoktur.
    if _ebeveyn_pid is None:
        if not _ensure_single_instance():
            sys.exit(0)
    else:
        logger.info("Yeniden başlatma ardılı (eski pid=%s); tek örnek kilidi "
                    "en fazla %.1f sn beklenecek.", _ebeveyn_pid,
                    restart.LOCK_WAIT_S)
        if not _ensure_single_instance(bekleme_s=restart.LOCK_WAIT_S):
            logger.error(
                "Yeniden başlatma ardılı tek örnek kilidini %.1f sn içinde "
                "alamadı (eski pid=%s); açılış iptal edildi.",
                restart.LOCK_WAIT_S, _ebeveyn_pid)
            _kullaniciya_bildir(_KILIT_ALINAMADI.format(log=log_filename))
            sys.exit(restart.EXIT_LOCK_TIMEOUT)

    logger.info("=" * 50)
    from core.constants import APP_VERSION
    logger.info("Teklif Yönetim Sistemi başlatılıyor...  (Version: %s)", APP_VERSION)
    logger.info("Python: %s", sys.version)
    logger.info("Veri klasörü: %s", DATA_DIR)
    logger.info("Yedek klasörü: %s", BACKUP_DIR)

    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QFontDatabase, QIcon
    from PySide6.QtCore import QTranslator, QLibraryInfo, QLocale

    app = QApplication(sys.argv)
    app.setApplicationName("Teklif Yönetim Sistemi")
    app.setOrganizationName("TeklifApp")

    # Uygulama genelinde varsayılan pencere ikonu — QApplication üzerinde
    # tek seferde ayarlanır, açıkça kendi ikonunu vermeyen TÜM pencere ve
    # dialoglara (Qt tarafından) otomatik miras kalır. Başlık çubuğu/görev
    # çubuğu/alt-tab için çoklu çözünürlüklü .ico tercih edilir.
    _icon_path = ASSET_ROOT / "assets" / "ico.ico"
    if _icon_path.exists():
        app.setWindowIcon(QIcon(str(_icon_path)))

    # Sayı biçimi her makinede Türk düzeni olsun (SpinBox: 1.234,56)
    QLocale.setDefault(QLocale(QLocale.Language.Turkish, QLocale.Country.Turkey))

    # Qt arayüz çevirisi — sağ tık menüleri ve sistem dialogları Türkçe olur
    _translator = QTranslator(app)
    _tr_path = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    if _translator.load(
            QLocale(QLocale.Language.Turkish, QLocale.Country.Turkey),
            "qtbase", "_", _tr_path):
        app.installTranslator(_translator)
        logger.info("Qt Türkçe çevirisi yüklendi.")

    # Başlangıç veri kontrolü — geri yükleme yapıldıysa ardıl süreci ortak
    # yoldan başlat. Spawn başarısızsa sessiz sys.exit(0) YOK.
    if _check_data_on_startup(app):
        _veritabanini_kapat()
        sys.exit(_yeniden_baslat())

    # Font yükleme — Inter varsa Inter, yoksa Segoe UI
    inter_path = ASSET_ROOT / "assets" / "fonts" / "Inter-Regular.ttf"
    font_family = "Segoe UI"
    if inter_path.exists():
        fid = QFontDatabase.addApplicationFont(str(inter_path))
        if fid >= 0:
            families = QFontDatabase.applicationFontFamilies(fid)
            if families:
                font_family = families[0]

    if font_family != "Segoe UI":
        os.environ["APP_FONT_FAMILY"] = font_family

    # ── Splash Screen ────────────────────────────────────────────────────────
    from PySide6.QtWidgets import QGraphicsOpacityEffect
    from PySide6.QtCore import QPropertyAnimation, QEasingCurve
    import time as _time

    from ui.startup_splash import StartupSplash
    splash = StartupSplash()
    splash.show()
    splash.set_progress(0.05, "Başlatılıyor…")

    def _step(val, msg, work=None):
        """İlerlemeyi güncelle, iş varsa çalıştır, kısa bekle."""
        splash.set_progress(val, msg)
        if work:
            work()
        _deadline = _time.monotonic() + 0.30
        while _time.monotonic() < _deadline:
            app.processEvents()
            _time.sleep(0.015)

    _step(0.15, "Veritabanı hazırlanıyor…",
          lambda: __import__('database.db_manager', fromlist=['get_db']).get_db())
    _step(0.30, "Ayarlar okunuyor…",
          lambda: __import__('core.config', fromlist=['load_company_config']).load_company_config())
    _step(0.45, "Tema uygulanıyor…",
          lambda: __import__('ui.utils.theme_manager', fromlist=['get_theme']).get_theme())
    _step(0.60, "Arayüz oluşturuluyor…")

    from ui.main_window import MainWindow
    window = MainWindow()

    _step(0.80, "Veriler yükleniyor…")
    _step(0.95, "Neredeyse hazır…")
    _step(1.00, "Hazır!")

    _deadline = _time.monotonic() + 0.3
    while _time.monotonic() < _deadline:
        app.processEvents()
        _time.sleep(0.015)

    window.show()

    opacity = QGraphicsOpacityEffect(splash)
    splash.setGraphicsEffect(opacity)
    fade = QPropertyAnimation(opacity, b"opacity")
    fade.setDuration(500)
    fade.setStartValue(1.0)
    fade.setEndValue(0.0)
    fade.setEasingCurve(QEasingCurve.Type.InQuad)
    fade.finished.connect(splash.close)
    fade.finished.connect(window.acilis_bildirimlerini_planla)
    fade.start()

    logger.info("Ana pencere açıldı.")

    exit_code = app.exec()

    # Uygulama kapanınca DB bağlantısını düzgün kapat
    _veritabanini_kapat()

    # Yeniden başlatma istendiyse ardıl süreç ANCAK burada başlatılır:
    # MainWindow.closeEvent worker'ları bekledi (K6) ve DB kapandı.
    if restart.restart_requested():
        kod = _yeniden_baslat()
        if kod:
            exit_code = kod

    logger.info("Uygulama kapatıldı. Çıkış kodu: %d", exit_code)
    sys.exit(exit_code)


def _run_entrypoint():
    """Beklenmeyen ana-akış hatasını PyInstaller'a kaçırmadan bitir.

    ``sys.excepthook`` tek başına yeterli değildir: windowed PyInstaller
    bootloader, hook döndükten sonra ham istisna ve traceback içeren ikinci
    bir pencere açar. Burada hata güvenli ortak hook'a tam bir kez aktarılır
    ve ardından normal, sayısal bir süreç çıkışına dönüştürülür.

    ``SystemExit`` / ``KeyboardInterrupt`` gibi ``BaseException`` türleri
    bilinçli çıkış davranışlarını korumak için yakalanmaz.
    """
    try:
        main()
    except Exception:
        exception_hook(*sys.exc_info())
        raise SystemExit(1) from None


if __name__ == "__main__":
    _run_entrypoint()
