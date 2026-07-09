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
from PySide6.QtCore import QThread, Signal, Qt

logger = logging.getLogger("updater")

from core.constants import APP_VERSION
GITHUB_REPO = "IzzmooPro/offer_management_system"
GITHUB_URL  = f"https://github.com/{GITHUB_REPO}"


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
    progress  = Signal(int)     # 0-100
    finished  = Signal(str)     # indirilen dosya yolu
    failed    = Signal(str)     # hata mesajı

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
            self.finished.emit(self._dest)
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

        self.setWindowTitle("Güncelleme Mevcut")
        self.setFixedSize(320, 200)
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

        # Geçici dosya yolu
        tmp_dir  = tempfile.mkdtemp(prefix="TeklifUpdate_")
        tmp_exe  = os.path.join(tmp_dir, "TeklifYonetim_new.exe")

        self._downloader = _Downloader(self._download_url, tmp_exe, self)
        self._downloader.progress.connect(self._progress.setValue)
        self._downloader.finished.connect(lambda path: self._on_downloaded(path))
        self._downloader.failed.connect(self._on_download_failed)
        self._downloader.start()

    def _on_downloaded(self, new_exe: str):
        """İndirme tamamlandı → güncelleme scriptini çalıştır ve kapat."""
        self._status.setText("Güncelleme uygulanıyor…")
        logger.info("Yeni sürüm indirildi: %s", new_exe)

        try:
            self._apply_update(new_exe)
        except Exception as e:
            self._on_download_failed(str(e))

    def _apply_update(self, new_exe: str):
        """
        Güncelleme batch scripti oluştur ve çalıştır.
        Script: mevcut EXE'yi bekle → değiştir → yeniden başlat.
        """
        if not getattr(sys, "frozen", False):
            # Kaynak (Python) modda — tarayıcıya yönlendir
            import webbrowser
            webbrowser.open(f"{GITHUB_URL}/releases/latest")
            self._finish()
            return

        current_exe = sys.executable
        current_pid = os.getpid()
        bat_path = os.path.join(tempfile.gettempdir(), "teklif_update.bat")

        bat_content = (
            "@echo off\n"
            f'taskkill /PID {current_pid} /F >nul 2>&1\n'
            "timeout /t 3 /nobreak >nul\n"
            f'move /y "{new_exe}" "{current_exe}"\n'
            "if errorlevel 1 (\n"
            "  timeout /t 2 /nobreak >nul\n"
            f'  move /y "{new_exe}" "{current_exe}"\n'
            ")\n"
            f'start "" "{current_exe}"\n'
            "del /f /q \"%~f0\"\n"
        )

        with open(bat_path, "w", encoding="mbcs") as f:
            f.write(bat_content)

        import subprocess
        subprocess.Popen(
            ["cmd", "/c", bat_path],
            creationflags=subprocess.CREATE_NO_WINDOW
            if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
        )

        logger.info("Güncelleme scripti başlatıldı, program kapatılıyor.")
        self._finish()

    def _on_download_failed(self, err: str):
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
            with urllib.request.urlopen(req, timeout=8) as resp:
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
