"""K6-B — worker'lar çalışırken uygulama kapanışı.

Çalışan bir QThread, sahibi yok edilirken birlikte imha edilirse Qt süreci
0xC0000409 (fast-fail) ile abort eder; log'a hiçbir şey düşmez. Bu testler
PdfWorker, SmtpTestWorker ve _Downloader için kapanışın güvenli olduğunu
alt süreçte, GERÇEK main() akışıyla doğrular.

Testte kesinlikle YASAK olanlar (hepsi alt süreçte bloklanır):
  webbrowser.open · UpdateDialog._apply_update · os._exit ·
  gerçek ağ (urlopen + socket.connect) · gerçek SMTP
Bloklayan işler sahte sunucu/sleep ile temsil edilir.
"""
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


SCRIPT = textwrap.dedent(
    '''
    import os, sys, time
    from pathlib import Path

    TEMP_ROOT = Path(os.environ["OMS_TEMP_ROOT"]).resolve()
    # Kullanıcı ortamı SÜREÇ İÇİNDE yönlendirilir (dışarıdan LOCALAPPDATA
    # vermek Python Install Manager'ı tetikliyor).
    os.environ["LOCALAPPDATA"] = str(TEMP_ROOT / "AppData" / "Local")
    os.environ["USERPROFILE"] = str(TEMP_ROOT)
    os.environ["HOME"] = str(TEMP_ROOT)
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    sys.path.insert(0, os.environ["OMS_PROJECT"])

    SENARYO = os.environ["OMS_SENARYO"]
    BLOK = float(os.environ["OMS_BLOK"])

    from core.app_paths import DATA_DIR, BACKUP_DIR
    for _p in (DATA_DIR, BACKUP_DIR):
        assert _p.resolve().is_relative_to(TEMP_ROOT), _p

    def iz(m):
        print(m, flush=True)

    # ── YASAK YOLLAR: dışa dönük / süreç sonlandıran / gerçek ağ ────────────
    def _yasak(ad):
        def _f(*a, **k):
            iz("YASAK_CAGRI " + ad)
            raise AssertionError("testte yasak: " + ad)
        return _f

    import webbrowser, socket, smtplib, urllib.request, hashlib
    webbrowser.open = _yasak("webbrowser.open")
    webbrowser.open_new = _yasak("webbrowser.open_new")
    webbrowser.open_new_tab = _yasak("webbrowser.open_new_tab")
    os._exit = _yasak("os._exit")
    os.startfile = _yasak("os.startfile")
    urllib.request.urlopen = _yasak("urllib.request.urlopen")
    socket.socket.connect = _yasak("socket.connect")
    socket.create_connection = _yasak("socket.create_connection")
    smtplib.SMTP_SSL = _yasak("smtplib.SMTP_SSL")

    class SahteSMTP:
        def __init__(self, host, port, timeout=None): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def ehlo(self, *a): return (250, b"ok")
        def starttls(self, *, context=None): return (220, b"ok")
        def login(self, u, p):
            time.sleep(BLOK); iz("WORKER_ISI_BITTI"); return (235, b"ok")
        def send_message(self, m): return {}

    GOVDE = b"x" * 1024
    OZET = hashlib.sha256(GOVDE).hexdigest()
    INDIRME_URL = ("https://github.com/IzzmooPro/OfferManager/releases/"
                   "download/v9.9/TeklifYonetim_Setup_v9.9.exe")

    class SahteYanit:
        headers = {"Content-Length": str(len(GOVDE))}
        def __init__(self): self._kalan = 2
        def geturl(self): return INDIRME_URL
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self, n=None):
            if self._kalan <= 0:
                iz("WORKER_ISI_BITTI"); return b""
            self._kalan -= 1
            time.sleep(BLOK / 2)
            return b"x" * 512

    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

    # Cevapsız modal kutular kapanışı bloklar → hepsi otomatik yanıtlanır.
    # Statik yardımcıların yanı sıra ÖRNEK exec()'i de yamalanır: uygulama
    # bazı yerlerde QMessageBox nesnesi kurup box.exec() çağırıyor.
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.No)
    QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    QMessageBox.warning = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    QMessageBox.critical = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    QMessageBox.exec = lambda self, *a, **k: QMessageBox.StandardButton.Ok

    import ui.utils.updater as updater
    updater.start_startup_check = lambda parent=None: None      # K6-A kapsam dışı
    # _apply_update GERÇEK işi (kurulum başlatma, os.startfile, os._exit,
    # webbrowser) yapmasın diye zararsız stub ile değiştirilir. Başarılı
    # indirmede uygulama bunu meşru olarak çağırır; hata fırlatmak yerine
    # izlenir. Alttaki sert bloklar yine de son güvenlik ağıdır.
    updater.UpdateDialog._apply_update = (
        lambda self, installer_path: iz("APPLY_UPDATE_STUB"))

    # PdfWorker senaryosu için tek teklif tohumla
    from models.offer import Offer
    from models.offer_item import OfferItem
    from services.offer_service import OfferService
    OfferService().save(Offer(
        company_name="K6B A.Ş.", date="2026-07-26", currency="TL",
        total_amount=100.0, validity="10 Gün", payment_term="30 Gün Vadeli",
        items=[OfferItem(product_code="P1", product_name="Ürün", quantity=1,
                         unit_price=100.0, total_price=100.0)]))

    _tut = {}

    def _win():
        from ui.main_window import MainWindow
        for w in QApplication.topLevelWidgets():
            if isinstance(w, MainWindow):
                return w
        return None

    def _calisiyor(w):
        if w is None:
            return None
        try:
            return w.isRunning()
        except RuntimeError:
            return "SILINDI"

    def senaryo_pdf():
        win = _win()
        page = win.pages[0]
        import pdf.pdf_generator as pg
        def _yavas(offer, out):
            time.sleep(BLOK); Path(out).write_bytes(b"%PDF-1.4")
            iz("WORKER_ISI_BITTI"); return out
        pg.generate_pdf = _yavas
        hedef = str(TEMP_ROOT / "cikti.pdf")
        QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (hedef, ""))
        page.on_enter(); page.table.selectRow(0); page._gen_pdf()
        _tut["worker"] = page._pdf_worker

    def senaryo_smtp():
        smtplib.SMTP = SahteSMTP
        win = _win()
        page = win.pages[5]
        page.f_smtp_server.setText("smtp.example.com")
        page.f_smtp_port.setText("587")
        page.f_smtp_user.setText("u@e.com")
        page.f_smtp_pass.setText("x")
        page._test_smtp()
        _tut["worker"] = page._smtp_worker

    def senaryo_downloader():
        urllib.request.urlopen = lambda *a, **k: SahteYanit()
        win = _win()
        dlg = updater.UpdateDialog("v9.9", INDIRME_URL, win,
                                   expected_sha256=OZET,
                                   expected_size=len(GOVDE))
        dlg.show(); dlg._start_update()
        _tut["dlg"] = dlg
        _tut["worker"] = dlg._downloader
        def _dialog_kapat():
            dlg.close()
            iz("UPDATE_DIALOG_GORUNUR " + str(dlg.isVisible()))
            iz("UPDATE_WORKER_CALISIYOR " + str(_calisiyor(dlg._downloader)))
        QTimer.singleShot(600, _dialog_kapat)

    SENARYOLAR = {"pdf": senaryo_pdf, "smtp": senaryo_smtp,
                  "downloader": senaryo_downloader}

    def _kapat():
        win = _win()
        w = _tut.get("worker")
        iz("KAPATMA_BASLIYOR worker_calisiyor=" + str(_calisiyor(w)))
        t0 = time.perf_counter()
        win.close()
        iz("KAPATMA_BITTI sure=%.2f worker_calisiyor=%s gorunur=%s"
           % (time.perf_counter() - t0, _calisiyor(w), win.isVisible()))

    _orig_exec = QApplication.exec

    def _exec(*_a):
        QTimer.singleShot(300, lambda: SENARYOLAR[SENARYO]())
        QTimer.singleShot(1500, _kapat)
        QTimer.singleShot(45000, lambda: (iz("GUVENLIK_CIKISI"), QApplication.quit()))
        return _orig_exec()

    QApplication.exec = staticmethod(_exec)

    import main
    try:
        main.main()
    except SystemExit as exc:
        iz("SYSTEMEXIT " + str(exc.code))
    iz("TEARDOWN_ONCESI worker_calisiyor=" + str(_calisiyor(_tut.get("worker"))))
    iz("TEARDOWN_BASLIYOR")
    '''
)


class ShutdownWithRunningWorkersTests(unittest.TestCase):

    def _run(self, senaryo: str, blok: float):
        with tempfile.TemporaryDirectory(prefix="oms_k6b_") as tmp:
            script = Path(tmp) / "kapanis.py"
            script.write_text(SCRIPT, encoding="utf-8")
            env = os.environ.copy()
            env.update({
                "OMS_PROJECT": str(PROJECT_ROOT),
                "OMS_TEMP_ROOT": tmp,
                "OMS_SENARYO": senaryo,
                "OMS_BLOK": str(blok),
                "PYTHONIOENCODING": "utf-8",
                "PYTHONUNBUFFERED": "1",
                # İndirme senaryosu gerçek _start_update()'i çalıştırıyor ve
                # tempfile.mkdtemp kullanıyor; kullanıcının gerçek %TEMP%
                # klasörü kirlenmesin diye test dizinine yönlendirilir.
                "TMP": tmp,
                "TEMP": tmp,
            })
            return subprocess.run(
                [sys.executable, str(script)], env=env, timeout=180,
                capture_output=True, encoding="utf-8", errors="replace")

    def _assert_temiz(self, proc, etiket: str):
        self.assertNotIn("YASAK_CAGRI", proc.stdout,
                         f"{etiket}: testte yasak bir yol çağrıldı\n{proc.stdout[-1500:]}")
        self.assertNotIn("GUVENLIK_CIKISI", proc.stdout,
                         f"{etiket}: uygulama kendi kapanamadı")
        self.assertIn("TEARDOWN_BASLIYOR", proc.stdout, etiket)
        self.assertEqual(
            proc.returncode, 0,
            f"{etiket}: süreç temiz kapanmadı (kod={proc.returncode}); "
            f"0xC0000409 = çalışan QThread yok edildi.\n{proc.stdout[-1800:]}")

    def _assert_worker_once_bitti(self, proc, etiket: str):
        self.assertIn("WORKER_ISI_BITTI", proc.stdout,
                      f"{etiket}: worker bitmeden süreç kapanmış")
        self.assertLess(proc.stdout.index("WORKER_ISI_BITTI"),
                        proc.stdout.index("TEARDOWN_BASLIYOR"),
                        f"{etiket}: teardown worker'dan önce başlamış")

    # ── PdfWorker ────────────────────────────────────────────────────────

    def test_pdf_worker_running_at_shutdown(self):
        proc = self._run("pdf", 6.0)
        self._assert_temiz(proc, "PdfWorker")
        self._assert_worker_once_bitti(proc, "PdfWorker")

    def test_pdf_worker_control_group(self):
        proc = self._run("pdf", 0.2)
        self._assert_temiz(proc, "PdfWorker kontrol")

    # ── SmtpTestWorker ───────────────────────────────────────────────────

    def test_smtp_worker_running_at_shutdown(self):
        proc = self._run("smtp", 6.0)
        self._assert_temiz(proc, "SmtpTestWorker")
        self._assert_worker_once_bitti(proc, "SmtpTestWorker")

    def test_smtp_worker_control_group(self):
        proc = self._run("smtp", 0.2)
        self._assert_temiz(proc, "SmtpTestWorker kontrol")

    # ── _Downloader ──────────────────────────────────────────────────────

    def test_downloader_running_at_shutdown(self):
        proc = self._run("downloader", 6.0)
        self._assert_temiz(proc, "_Downloader")
        self._assert_worker_once_bitti(proc, "_Downloader")

    def test_update_dialog_close_is_deferred_while_downloading(self):
        proc = self._run("downloader", 6.0)
        self.assertIn("UPDATE_DIALOG_GORUNUR True", proc.stdout,
                      f"indirme sürerken UpdateDialog kapandı\n{proc.stdout[-1500:]}")
        self.assertIn("UPDATE_WORKER_CALISIYOR True", proc.stdout)

    def test_downloader_control_group(self):
        proc = self._run("downloader", 0.2)
        self._assert_temiz(proc, "_Downloader kontrol")


if __name__ == "__main__":
    unittest.main(verbosity=2)
