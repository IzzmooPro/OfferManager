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
    SIG3_PATH   as _SIG3_PATH,
    SIG4_PATH   as _SIG4_PATH,
    LOGO_DISABLED_PATH as _LOGO_DISABLED_PATH,
    BACKUP_DIR  as _DEFAULT_BACKUP_DIR,
    DATA_ROOT   as _BASE,
)
from core.constants import APP_VERSION
from ui.utils import operation_error as op_hata
from ui.utils import operation_error_dialog as hata_diyalogu

_META_PATH = _DATA_DIR / "backup_meta.json"


# ── Geri yükleme durum sözleşmesi ────────────────────────────────────────
PREFLIGHT_FAILED = "preflight_failed"   # hedef veriler HİÇ değişmedi
ROLLED_BACK = "rolled_back"             # yazma başladı, önceki durum geri geldi
ROLLBACK_FAILED = "rollback_failed"     # geri alma tamamlanamadı → BELİRSİZ

_RESTORE_METINLERI = {
    # Preflight yalnız yedek dosyası yüzünden değil, mevcut verinin rollback
    # anlık görüntüsü hazırlanamadığı için de düşebilir. Metin bu yüzden
    # nedeni tek bir sebebe indirgemez; yalnız GARANTİYİ söyler.
    PREFLIGHT_FAILED: (
        "Geri yükleme başlatılamadı. Mevcut verileriniz değiştirilmedi."),
    ROLLED_BACK: (
        "Geri yükleme tamamlanamadı. Önceki durumunuz geri getirildi; "
        "verileriniz geri yükleme öncesindeki hâliyle duruyor."),
    ROLLBACK_FAILED: (
        "Geri yükleme tamamlanamadı ve önceki duruma dönüş de tamamlanamadı. "
        "Veri durumu doğrulanamadı: programda işlem yapmayın ve sağlam "
        "yedeğinizi koruyun."),
}


class RestoreError(ValueError):
    """Geri yükleme hatası — metni SABİTTİR.

    Ham istisnalar yalnız `nedenler` alanında iç kullanım için tutulur;
    `__str__` hiçbir koşulda yol, SQL veya istisna metni döndürmez.

    `ValueError` türevidir: geçersiz yedek için `ValueError` bekleyen mevcut
    çağıran ve test sözleşmesi (`test_regressions`) aynen korunur; durum
    makinesi bunun ÜSTÜNE eklenir.
    """

    def __init__(self, durum: str, nedenler=None):
        self.durum = durum
        self.nedenler = list(nedenler or [])
        super().__init__(durum)

    def __str__(self):
        return _RESTORE_METINLERI.get(self.durum, _RESTORE_METINLERI[ROLLBACK_FAILED])


# Yedekleme tarafı sabit metinleri
YEDEK_OLUSTURULDU = (
    "Yedek oluşturuldu. Seçtiğiniz klasörde backup_ ile başlayan bir dosya "
    "olarak saklanır."
)
YEDEK_META_UYARISI =(
    "Yedek dosyası oluşturuldu, ancak yedek bilgisi kaydedilemedi. "
    "Yedeğiniz klasörde duruyor; ayar bilgisi bir sonraki yedekte güncellenir.")
OTOMATIK_YEDEK_HATASI = (
    "Otomatik yedekleme tamamlanamadı. Ayrıntılar uygulama loguna kaydedildi.")

# Güncelleme sistemi bu yolların içine asla yazamaz (güvenlik)
_PROTECTED_DIRS = [str(_DATA_DIR), str(_DEFAULT_BACKUP_DIR)]


def _load_meta() -> dict:
    if _META_PATH.exists():
        try:
            return json.loads(_META_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            op_hata.logla(exc, "Yedek bilgisi oku")
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
    except Exception:                                          # noqa: BLE001
        # Sessizce yutulmaz ama BURADA LOGLANMAZ: aşama ayrımını ve güvenli
        # loglamayı ÇAĞIRAN yapar (`_manual`, `_save_auto`, `_on_backup_done`).
        # Burada da loglamak aynı istisnayı iki satıra çıkarırdı.
        raise


def _ts() -> str:
    """Aynı saniyedeki yedeklerin çakışmaması için mikrosaniyeli ad üret."""
    return datetime.now().strftime("backup_%Y_%m_%d_%H%M%S_%f")


_OPTIONAL_BACKUP_FILES = [
    (_CFG_PATH, "company.cfg"),
    (_LOGO_PATH, "logo.png"),
    (_SIG1_PATH, "signature1.png"),
    (_SIG2_PATH, "signature2.png"),
    # 3. ve 4. yetkilinin imzaları da kullanıcı verisidir (Ayarlar 4 yetkili
    # destekler, PDF imza bloğu dördünü de kullanır) — yedeğe dahil edilmezse
    # geri yüklemeden sonra kalıcı olarak kaybolur.
    (_SIG3_PATH, "signature3.png"),
    (_SIG4_PATH, "signature4.png"),
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
        # Ham SQLite metni taşınmaz; asıl istisna yalnız zincirde kalır ve
        # `op_hata.logla` tarafından sınıf/konum olarak güvenli loglanır.
        raise ValueError("Geçersiz SQLite veritabanı") from exc


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

    logger.info("Yedek oluşturuldu.")
    return str(zip_path)


def _geri_al(destinations, rollback_dir: Path, onceki_varlik: dict) -> list:
    """Rollback — İLK HATADA DURMAZ, tüm öğeler denenir.

    Geri yükleme öncesindeki var/yok durumu birebir kurulur: başlangıçta
    bulunmayan dosyalar (DB dâhil) silinir. Sonunda DB yeniden doğrulanır.
    Toplanan istisnalar **çağırana** döner; her biri TAM BİR KEZ güvenli
    loglanır. Rollback hatası ASIL geri yükleme hatasını gizlemez.
    """
    hatalar = []
    for destination, arcname in destinations:
        try:
            previous = rollback_dir / arcname
            if previous.exists():
                if arcname == "database.db":
                    _restore_database_snapshot(previous)
                else:
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(str(previous), str(destination))
            elif not onceki_varlik.get(arcname, False):
                # Başlangıçta YOKTU → geri yüklemede oluşmuşsa kaldırılır.
                if destination.exists():
                    destination.unlink()
                if arcname == "database.db":
                    for ek in ("-wal", "-shm"):
                        yan = Path(str(destination) + ek)
                        if yan.exists():
                            yan.unlink()
        except Exception as exc:                               # noqa: BLE001
            hatalar.append(exc)                                # devam edilir
    try:
        if onceki_varlik.get("database.db") and _DB_PATH.exists():
            _validate_database(_DB_PATH)
    except Exception as exc:                                   # noqa: BLE001
        hatalar.append(exc)
    for exc in hatalar:
        op_hata.logla(exc, "Geri yukleme geri alma")
    return hatalar


def _gecici_temizle(gecici):
    """Geçici çalışma klasörünü siler; DIŞARI HİÇ HATA SIZDIRMAZ.

    Temizlik, asıl işin sonucundan sonra gelen ayrı bir aşamadır: tamamlanmış
    bir geri yüklemeyi "başarısız" yapamaz ve oluşmuş `RestoreError.durum`
    değerini (ör. `rolled_back`) `rollback_failed`e dönüştüremez. Hata yalnız
    SABİT işlem adıyla tam bir kez güvenli loglanır.
    """
    if gecici is None:
        return
    try:
        gecici.cleanup()
    except Exception as exc:                                   # noqa: BLE001
        op_hata.logla(exc, "Geri yukleme gecici temizle")


def restore_backup(zip_path: str) -> bool:
    """
    ZIP yedeği geri yükler.
    Hedefe yazma hatasında önceki durumu geri almaya çalışır; sonuç
    `RestoreError.durum` ile bildirilir.
    """
    zp = Path(zip_path)
    destinations = [(Path(_DB_PATH), "database.db")] + [
        (Path(path), arcname) for path, arcname in _OPTIONAL_BACKUP_FILES
    ]

    # ── AŞAMA 0: ÇALIŞMA ALANI — hedef verilere dokunulmadan oluşan her
    #    başlangıç hatası (eksik dosya, geçici kök veya alt klasör
    #    açılamaması) preflight sözleşmesindedir.
    #    `with` KULLANILMAZ: `with` çıkışındaki temizlik hatası asıl sonucu
    #    maskeler; temizlik aşağıda `finally` içinde ayrıca ele alınır.
    gecici = None
    try:
        if not zp.exists():
            raise FileNotFoundError("Yedek dosyası bulunamadı")
        gecici = tempfile.TemporaryDirectory(prefix="oms_restore_")
        tmp_root = Path(gecici.name)
        incoming = tmp_root / "incoming"
        rollback = tmp_root / "rollback"
        incoming.mkdir(); rollback.mkdir()
    except Exception as exc:                                   # noqa: BLE001
        _gecici_temizle(gecici)
        op_hata.logla(exc, "Geri yukleme on kontrol")
        raise RestoreError(PREFLIGHT_FAILED, [exc]) from None

    try:
        # ── AŞAMA 1: ÖN KONTROL — hedef verilere HİÇ dokunulmaz ─────────
        try:
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

            # Geri yükleme ÖNCESİ var/yok durumu — rollback bunu birebir kurar.
            onceki_varlik = {arcname: destination.exists()
                             for destination, arcname in destinations}
            # Mevcut durumun tam rollback kopyasını oluştur.
            if _DB_PATH.exists():
                _create_database_snapshot(_DB_PATH, rollback / "database.db")
            for path, arcname in _OPTIONAL_BACKUP_FILES:
                if path.exists():
                    shutil.copy2(str(path), str(rollback / arcname))
        except Exception as exc:                               # noqa: BLE001
            op_hata.logla(exc, "Geri yukleme on kontrol")
            raise RestoreError(PREFLIGHT_FAILED, [exc]) from None

        # ── AŞAMA 2: UYGULAMA — buradan sonra hedefler değişebilir ──────
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
        except Exception as exc:                               # noqa: BLE001
            op_hata.logla(exc, "Geri yukleme")
            hatalar = _geri_al(destinations, rollback, onceki_varlik)
            if hatalar:
                raise RestoreError(ROLLBACK_FAILED, [exc] + hatalar) from None
            raise RestoreError(ROLLED_BACK, [exc]) from None
    finally:
        # Sonucu (True / RestoreError.durum) DEĞİŞTİRMEZ.
        _gecici_temizle(gecici)


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
    except RestoreError as exc:
        # Nedenleri alt katman zaten TAM BİR KEZ logladı; tekrarlanmaz.
        QMessageBox.critical(parent, "Geri Yükleme Hatası", str(exc))
        return False
    except Exception as exc:                                   # noqa: BLE001
        # Beklenmeyen kaçak: burada güvenli biçimde TAM BİR KEZ loglanır.
        op_hata.logla(exc, "Acilista geri yukleme")
        QMessageBox.critical(parent, "Geri Yükleme Hatası",
                             _RESTORE_METINLERI[ROLLBACK_FAILED])
        return False
    QMessageBox.information(
        parent, "Geri Yükleme Tamamlandı", "Veriler başarıyla geri yüklendi.")
    return True


# ── Otomatik Yedekleme Servisi ───────────────────────────────────────────────

class _BackupWorker(QThread):
    completed = Signal(str, str)
    # Ham metin DEĞİL, istisna NESNESİ taşınır: sınıf bilgisi korunur ve
    # güvenli loglama servis katmanında TAM BİR KEZ yapılır (invariant 18).
    failed = Signal(object, str)

    def __init__(self, destination: str, reason: str = "", parent=None):
        super().__init__(parent)
        self.destination = destination
        self.reason = reason

    def run(self):
        try:
            self.completed.emit(create_backup(self.destination), self.reason)
        except Exception as exc:                               # noqa: BLE001
            self.failed.emit(exc, self.reason)


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
                logger.info("Otomatik yedekleme etkin: her %d dk.",
                            m.get("auto_interval", 30))

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
        worker = _BackupWorker(d, reason, self)
        worker.completed.connect(self._on_backup_done)
        worker.failed.connect(self._on_backup_failed)
        # Temizlik, sonuç sinyaline DEĞİL, QThread'in YERLEŞİK finished()
        # sinyaline bağlanır: completed/failed run() içinden, thread hâlâ
        # çalışırken emit edilir. deleteLater olmadan worker servise parent
        # olarak bağlı kaldığı için uygulama ömrü boyunca birikiyordu.
        worker.finished.connect(self._on_worker_finished)
        worker.finished.connect(worker.deleteLater)
        self._worker = worker
        worker.start()

    def _on_worker_finished(self):
        """Thread GERÇEKTEN bitti — güçlü referansı bırak.

        Eski bir worker'ın gecikmiş sinyali yeni worker'ın referansını
        silmemeli; bu yüzden kimlik karşılaştırması yapılır.
        """
        biten = self.sender()
        if biten is self._worker:
            self._worker = None

    def active_worker(self):
        """ÇALIŞAN yedek thread'i döndürür; yoksa None.

        MainWindow kapanışta (K6) bu worker'ı da beklemek zorundadır. Salt
        okunurdur ve silinmiş C++ nesnesinde istisna sızdırmaz.
        """
        worker = self._worker
        if worker is None:
            return None
        try:
            if worker.isRunning():
                return worker
        except RuntimeError:
            # C++ nesnesi deleteLater ile silinmiş.
            self._worker = None
        return None

    def _run_sync(self, reason: str = ""):
        d = self._meta.get("auto_backup_dir", str(_DEFAULT_BACKUP_DIR)) or str(
            _DEFAULT_BACKUP_DIR)
        try:
            p = create_backup(d)
            self._on_backup_done(p, reason)
        except Exception as exc:                               # noqa: BLE001
            self._on_backup_failed(exc, reason)

    def _on_backup_done(self, path: str, reason: str = ""):
        self._meta["last_backup"] = datetime.now().strftime("%d.%m.%Y %H:%M")
        self._meta["backup_count"] = self._meta.get("backup_count", 0) + 1
        try:
            _save_meta(self._meta)
        except Exception as exc:                               # noqa: BLE001
            # Yedek DOSYASI oluştu; metadata yazımı ayrı bir aşamadır ve
            # başarısızlığı yedeği geçersiz kılmaz (invariant 18b).
            # Bu yolda diyalog yok: güvenli log TAM BİR KEZ burada yazılır,
            # `backup_done` ve `_cleanup` normal şekilde devam eder.
            op_hata.logla(exc, "Yedek bilgisi kaydet")
        self.backup_done.emit(path)
        self._cleanup(str(Path(path).parent))
        if reason == "kapanma":
            # GERÇEK başarı noktası. `closeEvent` bunu bilemez (trigger_now
            # hatayı içeride yakalar), bu yüzden kapanma yedeğinin başarı logu
            # koşulsuz olarak orada değil, burada yazılır.
            logger.info("Kapanma yedeği alındı.")
        elif reason:
            logger.info("Yedek alındı (%s).", reason)
        # `self._worker` BURADA bırakılmaz: bu slot çağrıldığında thread hâlâ
        # çalışıyor olabilir. Bırakma _on_worker_finished'de yapılır.

    def _on_backup_failed(self, exc, reason: str = ""):
        """Güvenli tek hat: TEK güvenli log + SABİT dışa sinyal."""
        op_hata.logla(exc, "Otomatik yedek olustur")
        self.backup_failed.emit(OTOMATIK_YEDEK_HATASI)

    def _cleanup(self, d: str, keep: int = 20):
        """En fazla `keep` adet yedek tut, eskilerini sil."""
        try:
            bkps = sorted(Path(d).glob("backup_*.zip"))
            for old in bkps[:-keep]:
                old.unlink()
        except OSError as exc:
            op_hata.logla(exc, "Eski yedek temizle")


# ── Dialog ───────────────────────────────────────────────────────────────────

class BackupDialog(QDialog):
    settings_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Veri Yedekleme & Geri Yükleme")
        self.setMinimumSize(540, 380)
        self._meta = _load_meta()
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        # NOT: İçeride ayrı bir başlık etiketi yok — pencere başlık çubuğu
        # zaten aynı metni taşıyor, tekrarı dikey alan israfıydı.
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
        # Kompakt düzen (kullanıcı isteği): açıklama metinleri ekrandan
        # kaldırıldı, bilgi kaybolmasın diye TOOLTIP'lere taşındı.
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(12, 12, 12, 10)
        layout.setSpacing(10)

        # Manuel yedekleme — tek satır: buton + son yedek bilgisi
        r = QHBoxLayout()
        r.setSpacing(10)
        btn = QPushButton("Yedek Al")
        btn.setObjectName("primary")
        btn.setMinimumHeight(36)
        btn.setToolTip(
            "Tüm verilerinizin bir kopyasını bilgisayarınıza kaydeder.\n"
            "(Müşteriler, teklifler, ürünler, ayarlar, logo ve imzalar)")
        btn.clicked.connect(self._manual)
        r.addWidget(btn)
        last = self._meta.get("last_backup", "")
        self.lbl_last = QLabel(f"Son yedek: {last or 'Henüz alınmadı'}")
        self.lbl_last.setObjectName("hint_label")
        r.addWidget(self.lbl_last)
        r.addStretch()
        layout.addLayout(r)

        # Otomatik yedekleme
        aut = QGroupBox("Otomatik Yedekleme")
        ag = QGridLayout(aut)
        ag.setContentsMargins(12, 6, 12, 10)
        ag.setSpacing(8)
        ag.setColumnStretch(1, 1)

        self.chk_auto = QCheckBox("Otomatik yedeklemeyi etkinleştir")
        self.chk_auto.setChecked(self._meta.get("auto_enabled", True))
        self.chk_auto.setToolTip(
            "Program açıkken arka planda otomatik yedek alınır.\n"
            "En fazla 20 yedek tutulur, eskiler otomatik silinir.")
        self.chk_auto.stateChanged.connect(self._auto_toggle)
        ag.addWidget(self.chk_auto, 0, 0, 1, 2)

        # Aralık combo'su checkbox'la aynı satırda — ayrı "Aralık:" etiketi
        # gereksizdi; anlamı tooltip'te.
        self.iv_combo = QComboBox()
        self.iv_combo.addItems(["15 Dakika", "30 Dakika", "1 Saat", "2 Saat"])
        self.iv_combo.setToolTip("Otomatik yedekleme aralığı")
        iv_map = {15: 0, 30: 1, 60: 2, 120: 3}
        self.iv_combo.setCurrentIndex(
            iv_map.get(self._meta.get("auto_interval", 30), 1)
        )
        ag.addWidget(self.iv_combo, 0, 2)

        ag.addWidget(QLabel("Yedek Klasörü:"), 1, 0)
        # Tek satır + ortadan kısaltma: yol içinde boşluk olmadığından
        # WordWrap "C:" gibi çirkin kırılmalar üretiyordu. Tam yol tooltip'te.
        # Renk nötr (accent_blue link sanılıyordu — tıklanabilir değil).
        self.lbl_dir = QLabel()
        self.lbl_dir.setObjectName("hint_label")
        ag.addWidget(self.lbl_dir, 1, 1)
        dir_val = self._meta.get("auto_backup_dir", str(_DEFAULT_BACKUP_DIR))
        self._set_dir_text(dir_val or str(_DEFAULT_BACKUP_DIR))

        btn_dir = QPushButton("Değiştir")
        btn_dir.setObjectName("secondary")
        btn_dir.setMinimumHeight(34)
        btn_dir.clicked.connect(self._pick_dir)
        ag.addWidget(btn_dir, 1, 2)

        r2 = QHBoxLayout()
        btn_sv = QPushButton("Ayarları Kaydet")
        btn_sv.setObjectName("primary")
        btn_sv.setMinimumHeight(34)
        btn_sv.clicked.connect(self._save_auto)
        r2.addWidget(btn_sv)
        r2.addStretch()
        ag.addLayout(r2, 2, 0, 1, 3)

        layout.addWidget(aut)
        layout.addStretch()
        return w

    # ── Sekme 2: Geri Yükleme ────────────────────────────────────────────────

    def _tab_restore(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(12, 12, 12, 10)
        layout.setSpacing(10)

        warn = QLabel(
            "Dikkat: Bu işlem mevcut tüm verilerinizi seçtiğiniz yedekle değiştirir.\n\n"
            "Önce yukarıdaki 'Yedekleme' sekmesinden güncel bir yedek almanızı öneririz.\n"
            "Yazma sırasında bir hata olursa program önceki durumu geri getirmeyi "
            "dener; bu her koşulda garanti edilemez."
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
        il.setContentsMargins(12, 6, 12, 10)
        il.setSpacing(6)
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

    def _set_dir_text(self, path: str):
        """Klasör yolunu tek satırda, ortadan kısaltarak gösterir; tam yol tooltip'te."""
        fm = self.lbl_dir.fontMetrics()
        self.lbl_dir.setText(fm.elidedText(path, Qt.TextElideMode.ElideMiddle, 300))
        self.lbl_dir.setToolTip(path)

    def _manual(self):
        d = QFileDialog.getExistingDirectory(
            self, "Yedek Klasörü Seç", str(_DEFAULT_BACKUP_DIR)
        )
        if not d:
            return
        # A) Yedek DOSYASINI oluştur.
        try:
            create_backup(d)
        except Exception as exc:                               # noqa: BLE001
            hata_diyalogu.hata_goster(self, "Hata", exc, "Yedek", "olustur")
            return

        # B) Metadata AYRI bir aşamadır: hatası oluşmuş yedeği geçersiz kılmaz
        #    ve `create_backup` TEKRARLANMAZ (invariant 18b).
        self._meta["last_backup"] = datetime.now().strftime("%d.%m.%Y %H:%M")
        try:
            _save_meta(self._meta)
        except Exception as exc:                               # noqa: BLE001
            hata_diyalogu.kismi_hata_goster(
                self, "Yedekleme Tamamlandı", exc,
                YEDEK_META_UYARISI, "Yedek bilgisi kaydet")
            return
        self.lbl_last.setText(f"Son yedek: {self._meta['last_backup']}")
        QMessageBox.information(self, "Yedekleme Tamamlandı", YEDEK_OLUSTURULDU)

    def _pick_dir(self):
        d = QFileDialog.getExistingDirectory(
            self, "Otomatik Yedek Klasörü", str(_DEFAULT_BACKUP_DIR)
        )
        if d:
            self._meta["auto_backup_dir"] = d
            self._set_dir_text(d)

    def _auto_toggle(self, state):
        enabled = bool(state)
        if enabled and not self._meta.get("auto_backup_dir"):
            d = QFileDialog.getExistingDirectory(
                self, "Otomatik Yedek Klasörü", str(_DEFAULT_BACKUP_DIR)
            )
            if d:
                self._meta["auto_backup_dir"] = d
                self._set_dir_text(d)
            else:
                self.chk_auto.setChecked(False)

    def _save_auto(self):
        iv_map = {0: 15, 1: 30, 2: 60, 3: 120}
        self._meta["auto_enabled"]  = self.chk_auto.isChecked()
        self._meta["auto_interval"] = iv_map.get(self.iv_combo.currentIndex(), 30)
        if not self._meta.get("auto_backup_dir"):
            self._meta["auto_backup_dir"] = str(_DEFAULT_BACKUP_DIR)
            self._set_dir_text(str(_DEFAULT_BACKUP_DIR))
        try:
            _save_meta(self._meta)
        except Exception as exc:                               # noqa: BLE001
            # Ayar KALICI OLMADI: başarı bildirilmez, diyalog açık kalır.
            # `tur` kısa KATEGORİ, `islem` kısa EYLEM olmalıdır; aksi hâlde
            # üretilen metin "…kaydedilemedi" ifadesini tekrar eder.
            hata_diyalogu.hata_goster(
                self, "Hata", exc, "Otomatik yedekleme ayarı", "kaydet")
            return
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
        except RestoreError as exc:
            # `rollback_failed` dahil HER hata durumunda yeniden başlatma
            # YAPILMAZ. Nedenler alt katmanda loglandı; tekrarlanmaz.
            QMessageBox.critical(self, "Geri Yükleme Hatası", str(exc))
            return
        except Exception as exc:                               # noqa: BLE001
            # Beklenmeyen kaçak: güvenli biçimde TAM BİR KEZ loglanır.
            op_hata.logla(exc, "Geri yukleme")
            QMessageBox.critical(self, "Geri Yükleme Hatası",
                                 _RESTORE_METINLERI[ROLLBACK_FAILED])
            return
        QMessageBox.information(
            self, "Geri Yükleme Tamamlandı",
            "Veriler başarıyla geri yüklendi.\nProgram şimdi yeniden başlatılıyor."
        )
        self._restart_app()

    def _restart_app(self):
        """Programı yeniden başlatır (geri yükleme sonrası DB'yi taze açmak için).

        Burada süreç BAŞLATILMAZ. Yalnız istek kaydedilir ve uygulamanın
        NORMAL kapanış yolu işletilir: MainWindow.closeEvent çalışan
        worker'ları bekler (K6), ardından main() `get_db().close()` yapar ve
        ardıl süreci ortak `core.restart` mekanizmasıyla açar.

        Eski `os.execl` çağrısı KALDIRILDI: Windows'ta süreci yerine
        geçirmiyor, `ExitProcess` ile ani çıkış yaptığı için Qt kapanışını,
        worker beklemesini ve DB kapanışını tamamen atlıyordu.
        """
        from PySide6.QtWidgets import QApplication
        from core import restart
        restart.request_restart()
        self.accept()                     # yedek penceresini kapat
        # Tüm üst düzey pencereleri normal yoldan kapat; MainWindow kapanışı
        # ertelerse (worker sürüyorsa) süreç iş bitene kadar yaşamaya devam
        # eder ve ardıl ancak ondan sonra açılır.
        QApplication.closeAllWindows()
