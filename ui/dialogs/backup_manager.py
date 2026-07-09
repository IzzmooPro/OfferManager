"""
Veri yedekleme & geri yükleme sistemi.

Özellikler:
  - Manuel yedekleme (klasör sor → backup_YYYY_MM_DD_HHMMSS.zip)
  - Otomatik yedekleme (arka plan, varsayılan Documents/OfferManagementSystem/backups)
  - Program kapanışında otomatik yedek
  - Teklif kaydedilince otomatik yedek
  - Geri yükleme (.zip seç, overwrite-safe)
  - Test butonu (otomatik yedeklemeyi anında tetikle)
  - Max 20 yedek tutulur (eskiler silinir)
"""
import logging, shutil, zipfile, json, sqlite3, tempfile
from contextlib import closing
from pathlib import Path
from datetime import datetime

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QGridLayout, QFileDialog, QMessageBox, QComboBox,
    QCheckBox, QWidget, QTabWidget
)
from PySide6.QtCore import Qt, QTimer, Signal, QObject, QThread
logger = logging.getLogger("backup")

from core.app_paths import (
    DATA_DIR    as _DATA_DIR,
    DB_PATH     as _DB_PATH,
    CFG_PATH    as _CFG_PATH,
    LOGO_PATH   as _LOGO_PATH,
    SIG1_PATH   as _SIG1_PATH,
    SIG2_PATH   as _SIG2_PATH,
    LOGO_DISABLED_PATH as _LOGO_DISABLED_PATH,
    BACKUP_DIR  as _DEFAULT_BACKUP_DIR,
    DATA_ROOT   as _BASE,
)
from core.constants import APP_VERSION

_META_PATH = _DATA_DIR / "backup_meta.json"

# Güncelleme sistemi bu yolların içine asla yazamaz (güvenlik)
_PROTECTED_DIRS = [str(_DATA_DIR), str(_DEFAULT_BACKUP_DIR)]


def _load_meta() -> dict:
    if _META_PATH.exists():
        try:
            return json.loads(_META_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, ValueError) as e:
            logger.warning("Yedek meta dosyası okunamadı: %s", e)
    return {
        "auto_backup_dir": str(_DEFAULT_BACKUP_DIR),
        "auto_interval":   30,
        "auto_enabled":    True,
        "last_backup":     "",
        "backup_count":    0,
    }


def _save_meta(meta: dict):
    try:
        _META_PATH.write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception as e:
        logger.warning("Meta kayıt hatası: %s", e)


def _ts() -> str:
    """Aynı saniyedeki yedeklerin çakışmaması için mikrosaniyeli ad üret."""
    return datetime.now().strftime("backup_%Y_%m_%d_%H%M%S_%f")


_OPTIONAL_BACKUP_FILES = [
    (_CFG_PATH, "company.cfg"),
    (_LOGO_PATH, "logo.png"),
    (_SIG1_PATH, "signature1.png"),
    (_SIG2_PATH, "signature2.png"),
    (_LOGO_DISABLED_PATH, "logo.disabled"),
]

_REQUIRED_TABLES = {"products", "customers", "offers", "offer_items", "offer_counter"}


def _validate_database(path: Path):
    try:
        with closing(sqlite3.connect(str(path))) as conn:
            result = conn.execute("PRAGMA integrity_check").fetchone()
            if not result or result[0] != "ok":
                raise ValueError(f"SQLite bütünlük kontrolü başarısız: {result}")
            tables = {
                row[0] for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'")
            }
            missing = _REQUIRED_TABLES - tables
            if missing:
                raise ValueError(
                    "Yedek veritabanında zorunlu tablolar eksik: "
                    + ", ".join(sorted(missing)))
    except sqlite3.DatabaseError as exc:
        raise ValueError(f"Geçersiz SQLite veritabanı: {exc}") from exc


def _create_database_snapshot(source: Path, destination: Path):
    destination.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(str(source), timeout=30)) as src:
        with closing(sqlite3.connect(str(destination))) as dst:
            src.backup(dst)
    _validate_database(destination)


def _restore_database_snapshot(source: Path):
    """Doğrulanmış snapshot'ı SQLite kilit/WAL kurallarına uygun geri yükle."""
    with closing(sqlite3.connect(str(source), timeout=30)) as src:
        with closing(sqlite3.connect(str(_DB_PATH), timeout=30)) as dst:
            src.backup(dst)


def create_backup(dest_dir: str) -> str:
    """
    ZIP yedek oluşturur.
    İçerik: database.db + company.cfg + logo/imzalar (varsa)
    Format : backup_YYYY_MM_DD_HHMMSS.zip
    """
    if not _DB_PATH.exists():
        raise FileNotFoundError(f"Veritabanı bulunamadı: {_DB_PATH}")

    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    zip_path = dest / f"{_ts()}.zip"

    with tempfile.TemporaryDirectory(prefix="oms_backup_") as tmp_dir:
        snapshot = Path(tmp_dir) / "database.db"
        _create_database_snapshot(_DB_PATH, snapshot)

        with zipfile.ZipFile(str(zip_path), "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(str(snapshot), "database.db")
            for path, arcname in _OPTIONAL_BACKUP_FILES:
                if path.exists():
                    zf.write(str(path), arcname)
            zf.writestr("backup_info.json", json.dumps({
                "backup_date": datetime.now().isoformat(),
                "app":         "Teklif Yönetim Sistemi",
                "version":     APP_VERSION,
            }, ensure_ascii=False, indent=2))

    logger.info("Yedek oluşturuldu: %s", zip_path)
    return str(zip_path)


def restore_backup(zip_path: str) -> bool:
    """
    ZIP yedeği geri yükler.
    Hata durumunda orijinal veriyi korur (tmp dosyası mekanizması).
    """
    zp = Path(zip_path)
    if not zp.exists():
        raise FileNotFoundError(f"Dosya bulunamadı: {zip_path}")

    destinations = [(Path(_DB_PATH), "database.db")] + [
        (Path(path), arcname) for path, arcname in _OPTIONAL_BACKUP_FILES
    ]

    with tempfile.TemporaryDirectory(prefix="oms_restore_") as tmp_dir:
        tmp_root = Path(tmp_dir)
        incoming = tmp_root / "incoming"
        rollback = tmp_root / "rollback"
        incoming.mkdir(); rollback.mkdir()

        with zipfile.ZipFile(str(zp), "r") as zf:
            bad_member = zf.testzip()
            if bad_member:
                raise ValueError(f"ZIP bütünlük kontrolü başarısız: {bad_member}")
            names = set(zf.namelist())
            if "database.db" not in names:
                raise ValueError("Geçersiz yedek — database.db içermiyor.")
            for _, arcname in destinations:
                if arcname in names:
                    target = incoming / arcname
                    with zf.open(arcname) as src, target.open("wb") as dst:
                        shutil.copyfileobj(src, dst)

        _validate_database(incoming / "database.db")

        # Mevcut durumun tam rollback kopyasını oluştur.
        if _DB_PATH.exists():
            _create_database_snapshot(_DB_PATH, rollback / "database.db")
        for path, arcname in _OPTIONAL_BACKUP_FILES:
            if path.exists():
                shutil.copy2(str(path), str(rollback / arcname))

        try:
            for destination, arcname in destinations:
                source = incoming / arcname
                if arcname == "database.db":
                    _restore_database_snapshot(source)
                    continue
                if source.exists():
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(str(source), str(destination))
                elif destination.exists():
                    destination.unlink()
            _validate_database(_DB_PATH)
            return True
        except (OSError, sqlite3.Error, ValueError, zipfile.BadZipFile) as exc:
            logger.error("Geri yükleme hatası, rollback yapılıyor: %s", exc)
            for destination, arcname in destinations:
                previous = rollback / arcname
                if arcname == "database.db" and previous.exists():
                    _restore_database_snapshot(previous)
                    continue
                if previous.exists():
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(str(previous), str(destination))
                elif destination.exists():
                    destination.unlink()
            raise


def check_and_restore_on_startup(parent=None) -> bool:
    """
    Veri klasörü boşsa (database.db yok) yedek klasörünü kontrol eder.
    Yedek bulunursa kullanıcıya sorar; onay gelirse geri yükler.
    True döner → geri yükleme yapıldı, False → yapılmadı.
    """
    if _DB_PATH.exists():
        return False

    # Yedek klasöründe backup_*.zip ara
    backups = sorted(_DEFAULT_BACKUP_DIR.glob("backup_*.zip"), reverse=True)
    if not backups:
        return False

    latest = backups[0]
    from PySide6.QtWidgets import QMessageBox
    reply = QMessageBox.question(
        parent,
        "Yedek Bulundu",
        f"Önceden oluşturulmuş bir yedek bulundu.\n"
        f"Dosya: {latest.name}\n\n"
        "Verileri geri yüklemek ister misiniz?",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.Yes,
    )
    if reply != QMessageBox.StandardButton.Yes:
        return False

    try:
        restore_backup(str(latest))
        QMessageBox.information(
            parent, "Geri Yükleme Tamamlandı",
            "Veriler başarıyla geri yüklendi."
        )
        return True
    except Exception as e:
        QMessageBox.critical(
            parent, "Geri Yükleme Hatası",
            f"Geri yükleme başarısız:\n{e}"
        )
        return False


# ── Otomatik Yedekleme Servisi ───────────────────────────────────────────────

class _BackupWorker(QThread):
    completed = Signal(str, str)
    failed = Signal(str, str)

    def __init__(self, destination: str, reason: str = "", parent=None):
        super().__init__(parent)
        self.destination = destination
        self.reason = reason

    def run(self):
        try:
            self.completed.emit(create_backup(self.destination), self.reason)
        except Exception as exc:
            self.failed.emit(str(exc), self.reason)


class AutoBackupService(QObject):
    backup_done   = Signal(str)
    backup_failed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._run)
        self._meta = _load_meta()
        self._worker = None
        self._apply()

    def _apply(self):
        self._timer.stop()
        m = self._meta
        if m.get("auto_enabled"):
            d = m.get("auto_backup_dir", str(_DEFAULT_BACKUP_DIR))
            if d:
                ms = int(m.get("auto_interval", 30)) * 60 * 1000
                self._timer.start(ms)
                logger.info("Otomatik yedekleme: her %ddk → %s",
                            m.get("auto_interval", 30), d)

    def reload(self):
        self._meta = _load_meta()
        self._apply()

    def trigger_now(self, reason: str = ""):
        """Anında yedek al (kapatma, kaydetme veya test için)."""
        if reason == "kapanma":
            # Uygulama kapanırken yarım kalan thread bırakma; veri güvenliği UI
            # akıcılığından daha önemlidir.
            if self._worker and self._worker.isRunning():
                self._worker.wait(30_000)
            self._run_sync(reason)
        else:
            self._run(reason)

    def _run(self, reason: str = ""):
        if self._worker and self._worker.isRunning():
            logger.info("Yedekleme zaten devam ediyor; yeni istek atlandı (%s).", reason)
            return
        d = self._meta.get("auto_backup_dir", str(_DEFAULT_BACKUP_DIR))
        if not d:
            d = str(_DEFAULT_BACKUP_DIR)
        self._worker = _BackupWorker(d, reason, self)
        self._worker.completed.connect(self._on_backup_done)
        self._worker.failed.connect(self._on_backup_failed)
        self._worker.start()

    def _run_sync(self, reason: str = ""):
        d = self._meta.get("auto_backup_dir", str(_DEFAULT_BACKUP_DIR)) or str(
            _DEFAULT_BACKUP_DIR)
        try:
            p = create_backup(d)
            self._on_backup_done(p, reason)
        except Exception as e:
            self._on_backup_failed(str(e), reason)

    def _on_backup_done(self, path: str, reason: str = ""):
        self._meta["last_backup"] = datetime.now().strftime("%d.%m.%Y %H:%M")
        self._meta["backup_count"] = self._meta.get("backup_count", 0) + 1
        _save_meta(self._meta)
        self.backup_done.emit(path)
        self._cleanup(str(Path(path).parent))
        if reason:
            logger.info("Yedek alındı (%s): %s", reason, path)
        self._worker = None

    def _on_backup_failed(self, error: str, reason: str = ""):
        self.backup_failed.emit(error)
        logger.error("Otomatik yedek hatası (%s): %s", reason, error)
        self._worker = None

    def _cleanup(self, d: str, keep: int = 20):
        """En fazla `keep` adet yedek tut, eskilerini sil."""
        try:
            bkps = sorted(Path(d).glob("backup_*.zip"))
            for old in bkps[:-keep]:
                old.unlink()
        except OSError as e:
            logger.debug("Eski yedek temizleme hatası: %s", e)


# ── Dialog ───────────────────────────────────────────────────────────────────

class BackupDialog(QDialog):
    settings_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Veri Yedekleme & Geri Yükleme")
        self.setMinimumSize(580, 520)
        self._meta = _load_meta()
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        title = QLabel("Veri Yedekleme ve Geri Yükleme")
        title.setStyleSheet("font-size:10pt;font-weight:700;")
        layout.addWidget(title)

        tabs = QTabWidget()
        tabs.setDocumentMode(True)
        layout.addWidget(tabs, 1)

        tabs.addTab(self._tab_backup(),  "Yedekleme")
        tabs.addTab(self._tab_restore(), "Geri Yükleme")

        row = QHBoxLayout()
        row.addStretch()
        btn_close = QPushButton("Kapat")
        btn_close.setObjectName("secondary")
        btn_close.clicked.connect(self.accept)
        row.addWidget(btn_close)
        layout.addLayout(row)

    # ── Sekme 1: Yedekleme ───────────────────────────────────────────────────

    def _tab_backup(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(14)

        # Manuel yedekleme
        man = QGroupBox("Şimdi Yedek Al")
        ml = QVBoxLayout(man)
        ml.setContentsMargins(14, 12, 14, 12)
        ml.setSpacing(8)
        ml.addWidget(QLabel(
            "Tüm verilerinizin bir kopyasını bilgisayarınıza kaydeder.\n"
            "(Müşteriler, teklifler, ürünler, ayarlar, logo ve imzalar)"
        ))
        last = self._meta.get("last_backup", "")
        self.lbl_last = QLabel(f"Son yedek: {last or 'Henüz alınmadı'}")
        self.lbl_last.setObjectName("hint_label")
        ml.addWidget(self.lbl_last)
        r = QHBoxLayout()
        btn = QPushButton("Yedek Al")
        btn.setObjectName("primary")
        btn.setMinimumHeight(36)
        btn.clicked.connect(self._manual)
        r.addWidget(btn)
        r.addStretch()
        ml.addLayout(r)
        layout.addWidget(man)

        # Otomatik yedekleme
        aut = QGroupBox("Otomatik Yedekleme")
        ag = QGridLayout(aut)
        ag.setContentsMargins(14, 12, 14, 12)
        ag.setSpacing(10)
        ag.setColumnStretch(1, 1)

        self.chk_auto = QCheckBox("Otomatik yedeklemeyi etkinleştir")
        self.chk_auto.setChecked(self._meta.get("auto_enabled", True))
        self.chk_auto.stateChanged.connect(self._auto_toggle)
        ag.addWidget(self.chk_auto, 0, 0, 1, 3)

        ag.addWidget(QLabel("Aralık:"), 1, 0)
        self.iv_combo = QComboBox()
        self.iv_combo.addItems(["15 Dakika", "30 Dakika", "1 Saat", "2 Saat"])
        iv_map = {15: 0, 30: 1, 60: 2, 120: 3}
        self.iv_combo.setCurrentIndex(
            iv_map.get(self._meta.get("auto_interval", 30), 1)
        )
        ag.addWidget(self.iv_combo, 1, 1)

        ag.addWidget(QLabel("Yedek Klasörü:"), 2, 0)
        dir_val = self._meta.get("auto_backup_dir", str(_DEFAULT_BACKUP_DIR))
        self.lbl_dir = QLabel(dir_val or str(_DEFAULT_BACKUP_DIR))
        from ui.utils.theme_manager import get_theme as _gt
        self.lbl_dir.setStyleSheet(f"color:{_gt()['accent_blue']};font-size:8pt;")
        self.lbl_dir.setWordWrap(True)
        ag.addWidget(self.lbl_dir, 2, 1)

        btn_dir = QPushButton("Değiştir")
        btn_dir.setObjectName("secondary")
        btn_dir.setMinimumHeight(34)
        btn_dir.clicked.connect(self._pick_dir)
        ag.addWidget(btn_dir, 2, 2)

        info = QLabel(
            "Program açıkken arka planda otomatik yedek alınır.\nEn fazla 20 yedek tutulur, eskiler otomatik silinir."
        )
        info.setObjectName("hint_label")
        info.setWordWrap(True)
        ag.addWidget(info, 3, 0, 1, 3)

        r2 = QHBoxLayout()
        btn_sv = QPushButton("Ayarları Kaydet")
        btn_sv.setObjectName("primary")
        btn_sv.setMinimumHeight(34)
        btn_sv.clicked.connect(self._save_auto)
        r2.addWidget(btn_sv)
        r2.addStretch()
        ag.addLayout(r2, 4, 0, 1, 3)

        layout.addWidget(aut)
        layout.addStretch()
        return w

    # ── Sekme 2: Geri Yükleme ────────────────────────────────────────────────

    def _tab_restore(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(14)

        warn = QLabel(
            "Dikkat: Bu işlem mevcut tüm verilerinizi seçtiğiniz yedekle değiştirir.\n\n"
            "Önce yukarıdaki 'Yedekleme' sekmesinden güncel bir yedek almanızı öneririz.\n"
            "Bir sorun olursa orijinal verileriniz otomatik olarak geri gelir."
        )
        warn.setWordWrap(True)
        from ui.utils.theme_manager import get_theme
        _t = get_theme()
        if _t["name"] == "dark":
            warn.setStyleSheet(
                f"background:#3d2800;border:1px solid #b45309;border-radius:6px;"
                f"padding:12px;color:#fbbf24;font-size:9pt;")
        else:
            warn.setStyleSheet(
                "background:#fff3cd;border:1px solid #ffc107;border-radius:6px;"
                "padding:12px;color:#856404;font-size:9pt;")
        layout.addWidget(warn)

        info_box = QGroupBox("Yedeği Geri Yükle")
        il = QVBoxLayout(info_box)
        il.setContentsMargins(14, 12, 14, 12)
        il.setSpacing(8)
        il.addWidget(QLabel(
            "Daha önce aldığınız yedek dosyasını (.zip) seçin.\n"
            "Tüm verileriniz o yedeğe geri döner."
        ))
        r = QHBoxLayout()
        btn_rest = QPushButton("Yedek Dosyası Seç...")
        btn_rest.setObjectName("primary")
        btn_rest.setMinimumHeight(38)
        btn_rest.clicked.connect(self._restore)
        r.addWidget(btn_rest)
        r.addStretch()
        il.addLayout(r)
        layout.addWidget(info_box)

        layout.addStretch()
        return w

    # ── İşlemler ─────────────────────────────────────────────────────────────

    def _manual(self):
        d = QFileDialog.getExistingDirectory(
            self, "Yedek Klasörü Seç", str(_DEFAULT_BACKUP_DIR)
        )
        if not d:
            return
        try:
            p = create_backup(d)
            self._meta["last_backup"] = datetime.now().strftime("%d.%m.%Y %H:%M")
            _save_meta(self._meta)
            self.lbl_last.setText(f"Son yedek: {self._meta['last_backup']}")
            QMessageBox.information(
                self, "Yedekleme Tamamlandı",
                f"Yedek oluşturuldu:\n{p}"
            )
        except Exception as e:
            QMessageBox.warning(self, "Hata", f"Yedekleme başarısız:\n{e}")

    def _pick_dir(self):
        d = QFileDialog.getExistingDirectory(
            self, "Otomatik Yedek Klasörü", str(_DEFAULT_BACKUP_DIR)
        )
        if d:
            self._meta["auto_backup_dir"] = d
            self.lbl_dir.setText(d)

    def _auto_toggle(self, state):
        enabled = bool(state)
        if enabled and not self._meta.get("auto_backup_dir"):
            d = QFileDialog.getExistingDirectory(
                self, "Otomatik Yedek Klasörü", str(_DEFAULT_BACKUP_DIR)
            )
            if d:
                self._meta["auto_backup_dir"] = d
                self.lbl_dir.setText(d)
            else:
                self.chk_auto.setChecked(False)

    def _save_auto(self):
        iv_map = {0: 15, 1: 30, 2: 60, 3: 120}
        self._meta["auto_enabled"]  = self.chk_auto.isChecked()
        self._meta["auto_interval"] = iv_map.get(self.iv_combo.currentIndex(), 30)
        if not self._meta.get("auto_backup_dir"):
            self._meta["auto_backup_dir"] = str(_DEFAULT_BACKUP_DIR)
            self.lbl_dir.setText(str(_DEFAULT_BACKUP_DIR))
        _save_meta(self._meta)
        self.settings_changed.emit()
        QMessageBox.information(
            self, "Kaydedildi",
            f"Otomatik yedekleme ayarlandı.\n"
            f"Aralık: {self.iv_combo.currentText()}\n"
            f"Klasör: {self._meta.get('auto_backup_dir', '—')}"
        )

    def _restore(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Yedek Dosyası Seç", str(_DEFAULT_BACKUP_DIR),
            "Yedek Dosyaları (backup_*.zip);;ZIP (*.zip)"
        )
        if not path:
            return
        c = QMessageBox.warning(
            self, "Onay Gerekli",
            f"Bu işlem mevcut verilerin üzerine yazacaktır. Devam etmek istiyor musunuz?\n\n"
            f"Yedek: {Path(path).name}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if c != QMessageBox.StandardButton.Yes:
            return
        try:
            restore_backup(path)
            QMessageBox.information(
                self, "Geri Yükleme Tamamlandı",
                "Veriler başarıyla geri yüklendi.\nProgram şimdi yeniden başlatılıyor."
            )
            self._restart_app()
        except Exception as e:
            QMessageBox.critical(self, "Geri Yükleme Hatası", f"Başarısız:\n{e}")

    def _restart_app(self):
        """Programı yeniden başlatır (geri yükleme sonrası DB bağlantısını taze açmak için)."""
        import sys, os
        from PySide6.QtWidgets import QApplication
        try:
            if getattr(sys, "frozen", False):
                # PyInstaller EXE
                os.execl(sys.executable, sys.executable)
            else:
                # Python kaynak modu
                os.execl(sys.executable, sys.executable, *sys.argv)
        except OSError as e:
            logger.warning("Yeniden başlatma başarısız, uygulama kapatılıyor: %s", e)
            QApplication.quit()
