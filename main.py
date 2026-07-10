"""
Teklif Yönetim Sistemi — Ana giriş noktası  (sürüm: core/constants.py → APP_VERSION)

Başlangıç sırası:
  1. app_paths import → AppData klasörleri oluşturulur + eski veri migrasyonu
  2. Loglama yapılandırılır
  3. Veri klasörü boşsa backup kontrolü yapılır
  4. QApplication + MainWindow oluşturulur
  5. Arka planda güncelleme kontrolü başlar (MainWindow içinde)
"""
import sys, os, traceback, logging, ctypes
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

def _ensure_single_instance() -> bool:
    """
    QSharedMemory ile çapraz platform (cross-platform) tek örnek kontrolü.
    Program zaten çalışıyorsa (Windows'ta) mevcut pencereyi öne getirir ve False döner.
    False → çıkış yapılmalı.
    True  → devam edilebilir.
    """
    global _shared_memory, _win_mutex_handle

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
            return False
        if ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS
            kernel32.CloseHandle(ctypes.c_void_p(handle))
            _bring_existing_window_forward()
            return False
        _win_mutex_handle = handle

    _shared_memory = QSharedMemory("TeklifYonetimSistemi_SingleInstance_Mutex")
    
    if _shared_memory.attach():
        # Zaten çalışıyor
        _bring_existing_window_forward()
        return False
        
    if not _shared_memory.create(1):
        return False
        
    return True

# ── app_paths import (AppData klasörleri oluşturulur + migrasyon) ─────────────
# Bu import yan etki olarak:
#   - AppData\Local\OfferManagementSystem\data/ oluşturur
#   - Documents\OfferManagementSystem\backups/ oluşturur
#   - Eski exe yanındaki veriyi AppData'ya kopyalar (tek seferlik)
from core.app_paths import (
    ASSET_ROOT, DATA_DIR, LOG_DIR, DB_PATH, BACKUP_DIR
)

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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.FileHandler(str(log_filename), encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("main")

sys.path.insert(0, str(ASSET_ROOT))


# ── Global exception hook ─────────────────────────────────────────────────────

def exception_hook(exc_type, exc_value, exc_tb):
    error_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    logger.critical("=== UYGULAMA HATASI ===\n%s", error_msg)
    print("\n" + "=" * 60)
    print("HATA OLUŞTU! Detaylar log dosyasında:")
    print(f"  {log_filename}")
    print("=" * 60)
    print("Devam etmek için Enter'a basın...")
    try:
        input()
    except (EOFError, KeyboardInterrupt):
        pass


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
        # Geri yükleme sonrası yeniden başlat
        logger.info("Backup geri yüklendi, program yeniden başlatılıyor.")
        try:
            import subprocess
            subprocess.Popen([sys.executable] + sys.argv)
        except Exception as e:
            logger.warning("Yeniden başlatma başarısız: %s", e)
        return True
    return False


# ── Ana fonksiyon ─────────────────────────────────────────────────────────────

def main():
    # Program zaten açıksa mevcut pencereyi öne getir, yeni örnek açma
    if not _ensure_single_instance():
        sys.exit(0)

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

    # Başlangıç veri kontrolü
    if _check_data_on_startup(app):
        sys.exit(0)

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
    from PySide6.QtWidgets import QWidget, QGraphicsOpacityEffect
    from PySide6.QtGui import (QPixmap, QColor, QPainter, QFont,
                                QLinearGradient, QPen, QPainterPath)
    from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QRectF
    import time as _time

    SW, SH = 520, 280

    class _Splash(QWidget):
        def __init__(self):
            super().__init__()
            self.setFixedSize(SW, SH)
            self.setWindowFlags(
                Qt.WindowType.SplashScreen | Qt.WindowType.FramelessWindowHint)
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            self._progress = 0.0
            self._message = "Başlatılıyor…"
            self._icon = None
            ip = ASSET_ROOT / "assets" / "ico.png"
            if ip.exists():
                from PySide6.QtGui import QImage
                img = QImage(str(ip)).convertToFormat(
                    QImage.Format.Format_ARGB32)
                if not img.isNull():
                    img = img.scaled(
                        64, 64, Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation)
                    for y in range(img.height()):
                        sl = img.scanLine(y)
                        for x in range(img.width()):
                            off = x * 4
                            b, g, r, a = sl[off], sl[off+1], sl[off+2], sl[off+3]
                            luma = r * 0.299 + g * 0.587 + b * 0.114
                            if luma > 180:
                                sl[off+3] = 0
                            elif luma > 120:
                                sl[off+3] = int(a * (1.0 - (luma - 120) / 60.0))
                    self._icon = QPixmap.fromImage(img)

        def set_progress(self, value: float, message: str):
            self._progress = max(0.0, min(1.0, value))
            self._message = message
            self.repaint()
            app.processEvents()

        def paintEvent(self, _event):
            p = QPainter(self)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            grad = QLinearGradient(0, 0, SW, SH)
            grad.setColorAt(0.0, QColor("#0a1628"))
            grad.setColorAt(1.0, QColor("#162040"))
            path = QPainterPath()
            path.addRoundedRect(QRectF(0, 0, SW, SH), 16, 16)
            p.fillPath(path, grad)

            accent = QColor("#3a7bd5")
            p.setPen(QPen(accent.lighter(130), 1))
            p.drawRoundedRect(QRectF(1, 1, SW - 2, SH - 2), 15, 15)

            if self._icon:
                p.drawPixmap((SW - self._icon.width()) // 2, 40, self._icon)

            p.setPen(QColor("#e8eaf6"))
            p.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
            p.drawText(QRectF(0, 115, SW, 36),
                       Qt.AlignmentFlag.AlignCenter, "Teklif Yönetim Sistemi")

            from core.constants import APP_VERSION as _V
            p.setPen(QColor("#6a7a9a"))
            p.setFont(QFont("Segoe UI", 9))
            p.drawText(QRectF(0, 150, SW, 20),
                       Qt.AlignmentFlag.AlignCenter, f"Sürüm {_V}")

            bar_y = SH - 65
            bar_h = 8
            mx = 50
            bar_w = SW - 2 * mx
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#1a2744"))
            p.drawRoundedRect(QRectF(mx, bar_y, bar_w, bar_h), 4, 4)
            p.setBrush(accent)
            p.drawRoundedRect(QRectF(mx, bar_y, bar_w * self._progress, bar_h), 4, 4)

            p.setPen(QColor("#8a9abb"))
            p.setFont(QFont("Segoe UI", 9))
            p.drawText(QRectF(0, SH - 49, SW, 22),
                       Qt.AlignmentFlag.AlignCenter, self._message)
            p.end()

    splash = _Splash()
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
    fade.start()

    logger.info("Ana pencere açıldı.")

    exit_code = app.exec()

    # Uygulama kapanınca DB bağlantısını düzgün kapat
    try:
        from database.db_manager import get_db
        get_db().close()
        logger.info("Veritabanı bağlantısı kapatıldı.")
    except Exception as e:
        logger.warning("DB kapatma hatası: %s", e)

    logger.info("Uygulama kapatıldı. Çıkış kodu: %d", exit_code)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
