"""
Otomatik Güncelleme Sistemi — ui/updater.py

Program her açıldığında arka planda GitHub'u kontrol eder.
• Güncelleme yoksa → hiçbir şey gösterilmez (sessiz)
• Güncelleme varsa → "Yeni bir sürüm bulundu." diyalogu açılır
  - Güncelle  → indir, kapat, yükle, aç
  - Daha sonra → diyalogu kapat, program devam eder

GÜVENLİK NOTU:
  Güncelleme sistemi yalnızca EXE/program dosyasını değiştirebilir.
  AppData veri klasörüne ve Documents yedek klasörüne kesinlikle dokunmaz.
"""
import logging, json, os, sys, tempfile
import hashlib
import re
from collections import namedtuple
from pathlib import Path
from urllib.parse import urlsplit

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QMessageBox
)
from PySide6.QtCore import QThread, QTimer, Signal, Qt

logger = logging.getLogger("updater")

from core.constants import APP_VERSION
GITHUB_REPO = "IzzmooPro/OfferManager"
GITHUB_URL  = f"https://github.com/{GITHUB_REPO}"

# Başlangıç güncelleme kontrolünün ağ zaman aşımı (saniye).
# Program kapanırken MainWindow bu thread'in bitmesini SINIRLI süre bekler
# (MainWindow._SHUTDOWN_WAIT_MS); iki değer birlikte ayarlanmalıdır —
# bekleme sınırı bu zaman aşımından belirgin şekilde büyük olmalıdır.
STARTUP_CHECK_TIMEOUT = 3


def _version_parts(value: str) -> tuple:
    numbers = [int(part) for part in re.findall(r"\d+", value or "")]
    while len(numbers) < 3:
        numbers.append(0)
    return tuple(numbers)


def is_newer_version(latest: str, current: str = APP_VERSION) -> bool:
    return _version_parts(latest) > _version_parts(current)


# ── Güven zinciri: asset seçimi ve URL doğrulaması (Qt'den bağımsız) ─────────
#
# Eski davranış "release'teki İLK .exe asset'ini indir" idi. Bu, release
# hazırlığında ikinci bir .exe unutulduğunda veya release metadata'sı
# değiştirildiğinde yanlış dosyanın yönetici hakkıyla çalıştırılmasına yol
# açıyordu. Artık YALNIZ beklenen ada birebir uyan TEK asset kabul edilir ve
# indirilen içerik API'nin bildirdiği size + sha256 digest'iyle doğrulanır.
#
# SINIR: digest de release metadata'sından gelir. Bozuk/eksik CDN indirmesini
# ve yanlış asset seçimini engeller; ele geçirilmiş GitHub release
# metadata'sına karşı BAĞIMSIZ güven kökü DEĞİLDİR. Bunun için kod imzası
# (Authenticode) gerekir — bilinçli olarak bu turun dışındadır.

ASSET_NAME_TEMPLATE = "TeklifYonetim_Setup_{tag}.exe"

# API'nin verdiği browser_download_url her zaman github.com üzerindedir;
# istek buradan CDN'e yönlendirilir. Redirect sonrası son URL bu kümeye göre
# denetlenir (tam hostname eşleşmesi — suffix/prefix hilesi kabul edilmez).
_RELEASE_HOST = "github.com"
_ALLOWED_DOWNLOAD_HOSTS = frozenset({
    _RELEASE_HOST,
    "objects.githubusercontent.com",
    "release-assets.githubusercontent.com",
})

_DIGEST_RE = re.compile(r"^sha256:([0-9a-fA-F]{64})$")

# Kullanıcıya gösterilen SABİT metinler. Ham istisna, URL, dosya yolu veya
# backend metni bu mesajlara ASLA girmez; teknik neden yalnız log'a yazılır.
VERIFY_FAILED_MESSAGE = (
    "Güncelleme dosyası doğrulanamadı. Otomatik kurulum başlatılmadı.")
DOWNLOAD_FAILED_MESSAGE = "Güncelleme indirilemedi."
ASSET_VERIFY_FAILED_MESSAGE = (
    "Güncelleme bilgisi doğrulanamadı. Otomatik güncelleme başlatılmadı.")
CHECK_FAILED_MESSAGE = "Güncelleme kontrol edilemedi."

#: Doğrulanmış güncelleme asset'i. `size` ve `sha256` indirmede zorunludur.
UpdateAsset = namedtuple("UpdateAsset", "name url sha256 size")


class VerificationError(Exception):
    """İçerik/metadata doğrulaması başarısız — kullanıcıya ayrıntı verilmez."""


def expected_asset_name(tag: str) -> str:
    return ASSET_NAME_TEMPLATE.format(tag=(tag or "").strip())


def _parts(url) -> tuple:
    """(scheme, hostname, port, path) — ayrıştırılamazsa hepsi None."""
    if not isinstance(url, str) or not url:
        return (None, None, None, None)
    try:
        p = urlsplit(url)
        return (p.scheme, p.hostname, p.port, p.path)
    except ValueError:
        return (None, None, None, None)


def is_allowed_download_host(url) -> bool:
    """Redirect sonrası son URL: HTTPS + tam hostname eşleşmesi."""
    scheme, host, port, _ = _parts(url)
    if scheme != "https" or host is None:
        return False
    if port not in (None, 443):
        return False
    return host.lower() in _ALLOWED_DOWNLOAD_HOSTS


def is_release_download_url(url, tag: str) -> bool:
    """API'den gelen indirme URL'i: şema, host, repo/tag yolu ve dosya adı."""
    ad = expected_asset_name(tag)
    if not (tag or "").strip():
        return False
    scheme, host, port, path = _parts(url)
    if scheme != "https" or host is None or port not in (None, 443):
        return False
    if host.lower() != _RELEASE_HOST:
        return False
    beklenen = f"/{GITHUB_REPO}/releases/download/{tag.strip()}/{ad}"
    return path == beklenen


def _digest_hex(deger):
    if not isinstance(deger, str):
        return None
    m = _DIGEST_RE.match(deger.strip())
    return m.group(1).lower() if m else None


def _pozitif_boyut(deger):
    # bool int'in alt sınıfıdır; True/False boyut sayılmaz.
    if isinstance(deger, bool) or not isinstance(deger, int) or deger <= 0:
        return None
    return deger


def select_update_asset(data: dict):
    """Release JSON'undan doğrulanmış tek asset'i seçer.

    Dönüş: ``(UpdateAsset, "")`` veya ``(None, reddetme_nedeni)``. Neden yalnız
    log içindir; kullanıcıya gösterilmez.
    """
    tag = str((data or {}).get("tag_name", "") or "").strip()
    if not tag:
        return None, "tag_name boş"

    beklenen = expected_asset_name(tag)
    assets = (data or {}).get("assets") or []
    if not isinstance(assets, list):
        return None, "assets listesi okunamadı"

    eslesen = [a for a in assets
               if isinstance(a, dict) and a.get("name") == beklenen]
    if not eslesen:
        return None, f"beklenen asset yok: {beklenen}"
    if len(eslesen) > 1:
        return None, f"aynı adlı {len(eslesen)} asset var: {beklenen}"

    kayit = eslesen[0]
    url = kayit.get("browser_download_url")
    if not is_release_download_url(url, tag):
        return None, "indirme URL'i beklenen release yoluna uymuyor"

    ozet = _digest_hex(kayit.get("digest"))
    if ozet is None:
        return None, "digest alanı sha256:<64 hex> biçiminde değil"

    boyut = _pozitif_boyut(kayit.get("size"))
    if boyut is None:
        return None, "size alanı pozitif tam sayı değil"

    return UpdateAsset(beklenen, url, ozet, boyut), ""


def _dogrulanmis_asset(data: dict, kaynak: str):
    """Ortak checker yolu: seçim + fail-closed loglama."""
    secim, neden = select_update_asset(data)
    if secim is None:
        logger.warning("%s: güncelleme asset'i doğrulanamadı (%s); "
                       "otomatik güncelleme sunulmuyor.", kaynak, neden)
    return secim


# ── Güncelleme kontrolü (arka plan thread) ────────────────────────────────────

class UpdateChecker(QThread):
    """
    GitHub API'sini sorgular.
    Sinyal: update_available(version, download_url, expected_sha256,
                             expected_size)
            no_update()
            check_failed(error_msg)

    Asset doğrulanamazsa (beklenen ad yok, çift asset, bozuk URL/digest/size)
    güncelleme SUNULMAZ — fail-closed. Bu durumda `no_update` DEĞİL,
    `check_failed` yayılır: kullanıcıya "uygulama güncel" demek yanlış olur.
    `check_failed` her zaman SABİT bir metin taşır; ham istisna log'da kalır.
    """
    update_available = Signal(str, str, str, int)
    no_update        = Signal()
    check_failed     = Signal(str)

    def run(self):
        try:
            import urllib.request
            url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
            req = urllib.request.Request(
                url,
                headers={"User-Agent": f"TeklifApp/{APP_VERSION}"},
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read())

            latest_tag = data.get("tag_name", "").strip()  # örn: "v2" veya "v1.1"
            if not latest_tag:
                self.no_update.emit()
                return

            if is_newer_version(latest_tag):
                secim = _dogrulanmis_asset(data, "UpdateChecker")
                if secim is None:
                    # Yeni sürüm VAR ama doğrulanamıyor: "uygulama güncel"
                    # DEMEK yanlış olur. Güvenli sabit mesajla bildirilir.
                    self.check_failed.emit(ASSET_VERIFY_FAILED_MESSAGE)
                    return
                self.update_available.emit(latest_tag, secim.url,
                                           secim.sha256, secim.size)
            else:
                self.no_update.emit()

        except Exception as e:
            # Ham istisna metni (URL, yol, backend ayrıntısı) kullanıcıya
            # gösterilmez; yalnız log'a yazılır.
            logger.warning("Güncelleme kontrolü başarısız: %s", e)
            self.check_failed.emit(CHECK_FAILED_MESSAGE)


# ── İndirici (arka plan thread) ───────────────────────────────────────────────

class _Downloader(QThread):
    """EXE dosyasını geçici dizine indirir ve DOĞRULAR.

    `download_finished` yalnız şu koşulların TAMAMI sağlandığında yayılır:
    redirect sonrası host izinli ve HTTPS · yazılan bayt sayısı API `size`
    değerine birebir eşit · varsa `Content-Length` aynı değer · SHA-256
    beklenen digest ile birebir aynı. Aksi hâlde yarım dosya silinir ve
    `failed` yayılır; kullanıcıya giden metin teknik ayrıntı içermez.
    """
    # QThread'in yerleşik finished() sinyali GÖLGELENMEZ — aksi hâlde
    # "thread.finished.connect(...)" standart temizlik deyimi sessizce
    # yanlış sinyale bağlanır.
    progress          = Signal(int)     # 0-100
    download_finished = Signal(str)     # doğrulanmış dosya yolu
    failed            = Signal(str)     # kullanıcıya gösterilebilir kısa mesaj

    def __init__(self, url: str, dest: str, expected_sha256: str,
                 expected_size: int, parent=None):
        super().__init__(parent)
        self._url  = url
        self._dest = dest
        self._expected_sha256 = (expected_sha256 or "").lower()
        self._expected_size   = expected_size

    def run(self):
        try:
            self._indir_ve_dogrula()
        except VerificationError as e:
            logger.warning("Güncelleme doğrulaması başarısız: %s", e)
            self._yarim_dosyayi_sil()
            self.failed.emit(VERIFY_FAILED_MESSAGE)
        except Exception as e:
            logger.warning("Güncelleme indirilemedi: %s", e)
            self._yarim_dosyayi_sil()
            self.failed.emit(DOWNLOAD_FAILED_MESSAGE)
        else:
            self.download_finished.emit(self._dest)

    def _indir_ve_dogrula(self):
        import urllib.request
        beklenen = _pozitif_boyut(self._expected_size)
        if beklenen is None or not _DIGEST_RE.match(
                f"sha256:{self._expected_sha256}"):
            raise VerificationError("beklenen boyut/özet eksik veya bozuk")

        ozet = hashlib.sha256()
        yazilan = 0
        with urllib.request.urlopen(self._url, timeout=60) as resp:
            # Redirect zinciri sonundaki GERÇEK hedef denetlenir.
            if not is_allowed_download_host(resp.geturl()):
                raise VerificationError("indirme beklenmeyen hedefe yönlendirildi")
            bildirilen = resp.headers.get("Content-Length")
            if bildirilen is not None:
                try:
                    if int(bildirilen) != beklenen:
                        raise VerificationError("Content-Length beklenen boyuta uymuyor")
                except (TypeError, ValueError):
                    raise VerificationError("Content-Length okunamadı")
            with open(self._dest, "wb") as f:
                while True:
                    parca = resp.read(8192)
                    if not parca:
                        break
                    yazilan += len(parca)
                    if yazilan > beklenen:
                        raise VerificationError("beklenenden fazla veri geldi")
                    ozet.update(parca)
                    f.write(parca)
                    self.progress.emit(int(yazilan * 100 / beklenen))

        if yazilan != beklenen:
            raise VerificationError(
                f"eksik indirme: {yazilan}/{beklenen} bayt")
        if ozet.hexdigest() != self._expected_sha256:
            raise VerificationError("SHA-256 beklenen değerle uyuşmuyor")

    def _yarim_dosyayi_sil(self):
        """Doğrulanmamış dosyayı ve boş kalan geçici klasörü kaldırır.

        Yalnızca indirilen DOSYA silinir; özyinelemeli klasör silme YOKTUR.
        Üst klasör ancak TAMAMEN boşsa kaldırılır (`rmdir` dolu klasörde hata
        verir), böylece kullanıcının TEMP içindeki başka dosyaları korunur.
        Hiçbir silme hatası ASIL doğrulama/indirme hatasını gizlemez.
        """
        dosya = Path(self._dest)
        try:
            dosya.unlink(missing_ok=True)
        except OSError as exc:
            logger.warning("Doğrulanmamış indirme dosyası silinemedi: %s", exc)
            return
        try:
            dosya.parent.rmdir()          # yalnız klasör tamamen boşsa başarılı
        except OSError as exc:
            logger.debug("Geçici indirme klasörü kaldırılmadı: %s", exc)


# ── Güncelleme diyalogu ───────────────────────────────────────────────────────

class UpdateDialog(QDialog):
    """
    "Yeni bir sürüm bulundu." diyalogu.
    Butonlar: Güncelle | Daha sonra
    """
    def __init__(self, version: str, download_url: str, parent=None, *,
                 expected_sha256: str = "", expected_size: int = 0):
        super().__init__(parent)
        self._version      = version
        self._download_url = download_url
        # Doğrulama verisi API asset'inden gelir. Eksikse indirme BAŞLAMAZ —
        # yerel manifest hash'i buraya sabitlenmez (eski istemci gelecekteki
        # artifact'ın hash'ini bilemez).
        self._expected_sha256 = expected_sha256
        self._expected_size   = expected_size
        self._downloader   = None
        # İndirme sürerken gelen kapatma isteği ertelenir; finished->close
        # bağlantısı yalnız BİR kez kurulmalıdır.
        self._close_after_download_connected = False
        self._quit_suppressed = False
        # Kullanıcı kapatmayı istedi mi? _Downloader.download_finished sinyali
        # run() İÇİNDE, yerleşik finished() ise run() döndükten SONRA gelir;
        # yani sonuç callback'i ertelenmiş kapanıştan ÖNCE çalışır. Bu bayrak
        # olmadan, kullanıcı X/Daha sonra/Esc demesine rağmen kurulum başlar.
        self._close_requested = False

        self.setWindowTitle("Güncelleme Mevcut")
        # Sabit boyut YOK — progress + durum satırı görününce metin ezilip
        # okunmaz oluyordu. Genişlik sabit, yükseklik içeriğe göre büyür.
        self.setFixedWidth(400)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        msg = QLabel(
            f"Yeni bir sürüm bulundu.\n\n"
            f"Mevcut sürüm : {APP_VERSION}\n"
            f"Yeni sürüm   : {self._version}"
        )
        msg.setStyleSheet("font-size:10pt;")
        msg.setWordWrap(True)
        layout.addWidget(msg)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        self._status = QLabel("")
        self._status.setObjectName("hint_label")
        self._status.setVisible(False)
        layout.addWidget(self._status)

        layout.addStretch()

        btn_row = QHBoxLayout()
        self._btn_later = QPushButton("Daha sonra")
        self._btn_later.setObjectName("secondary")
        self._btn_later.clicked.connect(self.reject)

        self._btn_update = QPushButton("Güncelle")
        self._btn_update.setObjectName("primary")
        self._btn_update.clicked.connect(self._start_update)

        btn_row.addWidget(self._btn_later)
        btn_row.addStretch()
        btn_row.addWidget(self._btn_update)
        layout.addLayout(btn_row)

    def _start_update(self):
        """Güncelleme sürecini başlat."""
        if (not self._download_url
                or not self._expected_sha256
                or _pozitif_boyut(self._expected_size) is None):
            # Fail-closed: doğrulama verisi olmadan indirme YAPILMAZ ve
            # tarayıcı kendiliğinden AÇILMAZ; manuel yol kullanıcı seçimidir.
            logger.warning("Güncelleme doğrulama verisi eksik; "
                           "otomatik indirme başlatılmadı.")
            self._hata_kutusu_goster(VERIFY_FAILED_MESSAGE)
            return

        # UI'yi indirme moduna al
        self._btn_update.setEnabled(False)
        self._btn_later.setEnabled(False)
        self._progress.setVisible(True)
        self._progress.setValue(0)
        self._status.setVisible(True)
        self._status.setText("İndiriliyor…")
        self.adjustSize()   # yeni görünen satırlar için pencereyi büyüt

        # Geçici dosya yolu — indirilen asset Inno Setup kurulumudur
        tmp_dir  = tempfile.mkdtemp(prefix="TeklifUpdate_")
        tmp_exe  = os.path.join(tmp_dir, "TeklifYonetim_Setup.exe")

        self._downloader = _Downloader(self._download_url, tmp_exe,
                                       self._expected_sha256,
                                       self._expected_size, self)
        self._downloader.progress.connect(self._progress.setValue)
        self._downloader.download_finished.connect(lambda path: self._on_downloaded(path))
        self._downloader.failed.connect(self._on_download_failed)
        self._downloader.start()

    def _on_downloaded(self, new_exe: str):
        """İndirme tamamlandı → güncelleme scriptini çalıştır ve kapat."""
        if self._close_requested:
            # Kullanıcı indirme sürerken pencereyi kapatmak istedi: kurulum
            # BAŞLATILMAZ (os.startfile / webbrowser / os._exit çalışmaz).
            # Ertelenmiş kapanış, thread'in yerleşik finished() sinyaliyle
            # tamamlanır.
            logger.info("İndirme tamamlandı ancak kapatma istendi; "
                        "kurulum başlatılmıyor: %s", new_exe)
            self._discard_downloaded_installer(new_exe)
            return
        self._status.setText("Güncelleme uygulanıyor…")
        logger.info("Yeni sürüm indirildi: %s", new_exe)

        try:
            self._apply_update(new_exe)
        except Exception as e:
            self._on_download_failed(str(e))

    def _apply_update(self, installer_path: str):
        """
        İndirilen Inno Setup kurulumunu çalıştırır ve programı kapatır.

        Kurulum, .iss'teki CloseApplications=yes (Restart Manager) sayesinde
        çalışan uygulamayı kendisi nazikçe kapatıp mevcut kurulumun üzerine
        yazar ve yeniden başlatır. (AppMutex bilerek kaldırıldı — çalışan
        uygulama için manuel "kapatın" uyarısı çıkarıyordu.) EXE'yi elle
        "taşımaya" gerek yoktur; installer yönetici iznini kendisi ister.
        """
        if not getattr(sys, "frozen", False):
            # Kaynak (Python) modda — tarayıcıya yönlendir
            import webbrowser
            webbrowser.open(f"{GITHUB_URL}/releases/latest")
            self._finish()
            return

        # Kurulumu başlat. os.startfile → ShellExecute "open"; Inno kurulumunun
        # yönetici manifestini görüp UAC yükseltmesini tetikler. (subprocess/
        # CreateProcess manifestli kurulumu YÜKSELTEMEZ ve başlatamaz.)
        # Program kapanınca installer üzerine kurar ve /Run ile yeniden açar.
        os.startfile(installer_path)

        logger.info("Kurulum başlatıldı (%s), program kapatılıyor.", installer_path)
        # Süreci KESİN sonlandır. QApplication.quit() bazen arka plandaki
        # indirici/kontrolcü QThread yüzünden süreci asılı bırakıyor (dosya
        # kilitleri serbest kalmıyor → installer uygulamayı kapatamıyordu).
        # os._exit kilitleri anında bırakır. (Veriler her işlemde kaydedilir,
        # installer veriye dokunmaz → güvenli.) Installer ayrı süreç, ölmez.
        self.accept()
        os._exit(0)

    def closeEvent(self, event):
        """İndirme sürerken gelen kapatma isteğini ERTELER.

        Çalışan _Downloader bu dialog'un çocuğudur; dialog (ve dolayısıyla
        thread) iş bitmeden yok edilirse Qt süreci abort eder. UI thread'inde
        bekleme yapılmaz: thread'in YERLEŞİK finished() sinyaline tek
        seferlik bağlanılır, indirme bitince pencere kendiliğinden kapanır.
        """
        if self._downloader is not None and self._downloader.isRunning():
            # Sonuç callback'i kurulumu BAŞLATMASIN.
            self._close_requested = True
            if not self._close_after_download_connected:
                from PySide6.QtWidgets import QApplication
                self._downloader.finished.connect(self.close)
                self._close_after_download_connected = True
                self._status.setVisible(True)
                self._status.setText(
                    "İndirme tamamlanıyor — pencere işlem bitince kapanacak.")
                self.adjustSize()
                # Bu dialog ana pencereye parent'lı olduğu için Qt onu
                # "transient" sayar: ana pencere kapanırsa uygulama, burada
                # iş sürerken bile çıkmak ister. İndirme bitene kadar
                # otomatik çıkış kapatılır.
                self._quit_suppressed = True
                QApplication.setQuitOnLastWindowClosed(False)
            if not self._downloader.isRunning():
                # Kontrol ile bağlantı arasında bitmiş olabilir; sinyal artık
                # gelmeyeceğinden kapanışı elle sürdür.
                QTimer.singleShot(0, self.close)
            event.ignore()
            return
        event.accept()
        self._finish_deferred_close()

    def _finish_deferred_close(self):
        """Ertelenmiş kapanış bittiğinde otomatik çıkışı geri açar.

        Erteleme sırasında ana pencere kapanmış olabilir; görünür birincil
        pencere kalmadıysa süreç kendiliğinden sonlanmalıdır.
        """
        if not self._quit_suppressed:
            return
        from PySide6.QtWidgets import QApplication
        self._quit_suppressed = False
        QApplication.setQuitOnLastWindowClosed(True)
        birincil_acik = any(
            w is not self and w.parent() is None and w.isVisible()
            for w in QApplication.topLevelWidgets())
        if not birincil_acik:
            logger.info("İndirme bitti; açık pencere kalmadı, uygulama kapanıyor.")
            QApplication.quit()

    def reject(self):
        """"Daha sonra" düğmesi ve Esc de aynı güvenli kapanış yolunu kullanır.

        QDialog.reject() closeEvent göndermeden pencereyi kapatır; indirme
        sürerken bu, erteleme mekanizmasını atlayıp thread'i sahipsiz
        bırakırdı.
        """
        if self._downloader is not None and self._downloader.isRunning():
            self.close()
            return
        super().reject()

    def _discard_downloaded_installer(self, installer_path: str) -> None:
        """Kapatma istendiği için kullanılmayacak kurulum dosyasını siler.

        Yalnızca indirilen DOSYA silinir — özyinelemeli klasör silme YOKTUR.
        Üst klasör ancak TAMAMEN boşsa kaldırılır (rmdir dolu klasörde hata
        verir), böylece kullanıcının TEMP içindeki başka dosyaları korunur.
        Silme başarısız olursa kapanış ENGELLENMEZ; yalnız log'a yazılır.
        """
        dosya = Path(installer_path)
        try:
            dosya.unlink(missing_ok=True)
        except OSError as exc:
            logger.warning("Kullanılmayan kurulum dosyası silinemedi (%s): %s",
                           dosya, exc)
            return
        try:
            dosya.parent.rmdir()          # yalnız klasör tamamen boşsa başarılı
        except OSError as exc:
            logger.debug("Geçici indirme klasörü kaldırılmadı (%s): %s",
                         dosya.parent, exc)

    def _on_download_failed(self, err: str):
        if self._close_requested:
            # Pencere kapanıyor: kullanıcıyı hata kutusuyla rahatsız etme ve
            # dialogu yeniden kullanılabilir hâle getirme.
            logger.info("Güncelleme indirmesi başarısız oldu (kapanış "
                        "istendiği için bildirilmiyor): %s", err)
            return
        self._progress.setVisible(False)
        self._status.setVisible(False)
        self._btn_update.setEnabled(True)
        self._btn_later.setEnabled(True)
        # `err` worker tarafından zaten kullanıcıya uygun hâle getirilmiştir;
        # teknik neden yalnız logdadır.
        self._hata_kutusu_goster(err)

    def _hata_kutusu_goster(self, mesaj: str):
        """Kısa hata + AYRI kullanıcı seçimi olarak manuel GitHub sayfası.

        Tarayıcı yalnız kullanıcı düğmeye basarsa açılır; doğrulama hatası
        hiçbir otomatik eylemi (indirme, os.startfile, os._exit) tetiklemez.
        """
        kutu = QMessageBox(self)
        kutu.setIcon(QMessageBox.Icon.Warning)
        kutu.setWindowTitle("Güncelleme")
        kutu.setText(mesaj)
        kutu.setInformativeText(
            "İsterseniz güncellemeyi GitHub sayfasından elle indirebilirsiniz.")
        manuel = kutu.addButton("GitHub sayfasını aç",
                                QMessageBox.ButtonRole.ActionRole)
        kutu.addButton("Kapat", QMessageBox.ButtonRole.RejectRole)
        kutu.exec()
        if kutu.clickedButton() is manuel:
            import webbrowser
            webbrowser.open(f"{GITHUB_URL}/releases/latest")

    def _finish(self):
        """Programı güvenli şekilde kapat."""
        from PySide6.QtWidgets import QApplication
        self.accept()
        QApplication.quit()


# ── Başlangıç güncelleyici ────────────────────────────────────────────────────

class StartupUpdateChecker(QThread):
    """
    Program açıldığında arka planda çalışır.
    Güncelleme bulunursa ana thread'e sinyal gönderir.
    Güncelleme yoksa sessizce kapanır.
    """
    update_found = Signal(str, str, str, int)   # (version, url, sha256, size)

    def __init__(self, parent=None):
        super().__init__(parent)

    def run(self):
        try:
            import urllib.request
            url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
            req = urllib.request.Request(
                url,
                headers={"User-Agent": f"TeklifApp/{APP_VERSION}"},
            )
            with urllib.request.urlopen(req, timeout=STARTUP_CHECK_TIMEOUT) as resp:
                data = json.loads(resp.read())

            latest_tag = data.get("tag_name", "").strip()
            if not latest_tag:
                return

            if is_newer_version(latest_tag):
                secim = _dogrulanmis_asset(data, "StartupUpdateChecker")
                if secim is None:
                    return                      # fail-closed: sessiz geç
                logger.info("Güncelleme mevcut: %s", latest_tag)
                self.update_found.emit(latest_tag, secim.url,
                                       secim.sha256, secim.size)
            else:
                logger.debug("Uygulama güncel (%s)", APP_VERSION)

        except Exception as e:
            # Başlangıç kontrolü sessizce başarısız olabilir
            logger.warning("Güncelleme kontrol hatası: %s", e)


def start_startup_check(parent=None) -> StartupUpdateChecker:
    """
    Başlangıç güncelleme kontrolünü başlatır.
    Güncelleme bulunursa UpdateDialog otomatik açılır.
    Kullanım: main_window.__init__ içinde çağrılır.
    """
    checker = StartupUpdateChecker(parent)

    def _show_dialog(version: str, dl_url: str, sha256: str, size: int):
        dlg = UpdateDialog(version, dl_url, parent,
                           expected_sha256=sha256, expected_size=size)
        dlg.exec()

    checker.update_found.connect(_show_dialog, Qt.ConnectionType.QueuedConnection)
    checker.start()
    return checker
