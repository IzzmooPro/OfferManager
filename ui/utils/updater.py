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
import re
from pathlib import Path

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


# ── Güncelleme kontrolü (arka plan thread) ────────────────────────────────────

class UpdateChecker(QThread):
    """
    GitHub API'sini sorgular.
    Sinyal: update_available(latest_version, download_url)
            no_update()
            check_failed(error_msg)
    """
    update_available = Signal(str, str)  # (version, download_url)
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
                # İlk .exe asset'ini bul
                dl_url = ""
                for asset in data.get("assets", []):
                    name = asset.get("name", "").lower()
                    if name.endswith(".exe"):
                        dl_url = asset.get("browser_download_url", "")
                        break
                self.update_available.emit(latest_tag, dl_url)
            else:
                self.no_update.emit()

        except Exception as e:
            self.check_failed.emit(str(e))


# ── İndirici (arka plan thread) ───────────────────────────────────────────────

class _Downloader(QThread):
    """EXE dosyasını geçici dizine indirir."""
    # QThread'in yerleşik finished() sinyali GÖLGELENMEZ — aksi hâlde
    # "thread.finished.connect(...)" standart temizlik deyimi sessizce
    # yanlış sinyale bağlanır.
    progress          = Signal(int)     # 0-100
    download_finished = Signal(str)     # indirilen dosya yolu
    failed            = Signal(str)     # hata mesajı

    def __init__(self, url: str, dest: str, parent=None):
        super().__init__(parent)
        self._url  = url
        self._dest = dest

    def run(self):
        try:
            import urllib.request
            with urllib.request.urlopen(self._url, timeout=60) as resp:
                total   = int(resp.headers.get("Content-Length", 0) or 0)
                downloaded = 0
                chunk   = 8192
                with open(self._dest, "wb") as f:
                    while True:
                        data = resp.read(chunk)
                        if not data:
                            break
                        f.write(data)
                        downloaded += len(data)
                        if total > 0:
                            pct = int(downloaded * 100 / total)
                            self.progress.emit(pct)
            self.download_finished.emit(self._dest)
        except Exception as e:
            self.failed.emit(str(e))


# ── Güncelleme diyalogu ───────────────────────────────────────────────────────

class UpdateDialog(QDialog):
    """
    "Yeni bir sürüm bulundu." diyalogu.
    Butonlar: Güncelle | Daha sonra
    """
    def __init__(self, version: str, download_url: str, parent=None):
        super().__init__(parent)
        self._version      = version
        self._download_url = download_url
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
        if not self._download_url:
            # İndirme URL'i yoksa tarayıcıda aç
            import webbrowser
            webbrowser.open(f"{GITHUB_URL}/releases/latest")
            self.accept()
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

        self._downloader = _Downloader(self._download_url, tmp_exe, self)
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
        QMessageBox.warning(
            self, "İndirme Hatası",
            f"Güncelleme indirilemedi:\n{err}\n\n"
            f"GitHub sayfasına giderek manuel güncelleme yapabilirsiniz."
        )

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
    update_found = Signal(str, str)   # (version, download_url)

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
                dl_url = ""
                for asset in data.get("assets", []):
                    if asset.get("name", "").lower().endswith(".exe"):
                        dl_url = asset.get("browser_download_url", "")
                        break
                logger.info("Güncelleme mevcut: %s", latest_tag)
                self.update_found.emit(latest_tag, dl_url)
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

    def _show_dialog(version: str, dl_url: str):
        dlg = UpdateDialog(version, dl_url, parent)
        dlg.exec()

    checker.update_found.connect(_show_dialog, Qt.ConnectionType.QueuedConnection)
    checker.start()
    return checker
