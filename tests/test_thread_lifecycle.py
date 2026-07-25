"""K6 — QThread yaşam döngüsü sözleşme ve kapanış regresyon testleri.

Çalışan bir QThread, sahibi yok edilirken birlikte yok edilirse Qt süreci
0xC0000409 (fast-fail) ile abort eder; log'a hiçbir şey düşmez. Bu testler:
  1. Worker sınıflarının QThread.finished sinyalini gölgelemediğini,
  2. Güncelleme kontrolü sürerken kapatılan uygulamanın temiz çıktığını
korur. Ağ erişimi ve gerçek indirme YOKTUR — yavaş yanıt time.sleep ile
temsil edilir.
"""
import importlib
import inspect
import os
import pkgutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from PySide6.QtCore import QThread

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class SignalShadowingContractTests(unittest.TestCase):
    """Hiçbir worker QThread'in yerleşik finished() sinyalini gölgelememeli."""

    def _qthread_subclasses(self):
        import ui
        for info in pkgutil.walk_packages(ui.__path__, prefix="ui."):
            module = importlib.import_module(info.name)
            for name, obj in vars(module).items():
                if (inspect.isclass(obj) and issubclass(obj, QThread)
                        and obj is not QThread
                        and obj.__module__ == info.name):
                    yield info.name, name, obj

    def test_no_worker_shadows_qthread_finished(self):
        golgeleyen, taranan = [], 0
        for module_name, name, cls in self._qthread_subclasses():
            taranan += 1
            if "finished" in vars(cls):
                golgeleyen.append(f"{module_name}.{name}")
            elif str(cls.finished) != "finished()":
                golgeleyen.append(f"{module_name}.{name} -> {cls.finished}")
        self.assertGreaterEqual(taranan, 4, "worker sınıfları taranamadı")
        self.assertEqual(
            golgeleyen, [],
            "QThread.finished gölgelenmiş; 'thread.finished.connect(...)' "
            "temizlik deyimi bu sınıflarda yanlış sinyale bağlanır")

    def test_workers_expose_renamed_result_signals(self):
        from ui.dashboard_page import PdfWorker
        from ui.dialogs.email_dialog import EmailWorker
        from ui.utils.updater import _Downloader
        self.assertEqual(str(PdfWorker.result_ready), "result_ready(QVariantList,QVariantList)")
        self.assertEqual(str(EmailWorker.send_finished), "send_finished(bool,QString)")
        self.assertEqual(str(_Downloader.download_finished), "download_finished(QString)")


class UpdateCheckerShutdownTests(unittest.TestCase):
    """Güncelleme kontrolü sürerken kapanan uygulama çökmemeli."""

    SCRIPT = textwrap.dedent(
        """
        import os, sys, time
        from pathlib import Path

        TEMP_ROOT = Path(os.environ["OMS_TEMP_ROOT"]).resolve()
        # Kullanıcı ortamı SÜREÇ İÇİNDE yönlendirilir; dışarıdan LOCALAPPDATA
        # vermek Python Install Manager'ı tetikliyor.
        os.environ["LOCALAPPDATA"] = str(TEMP_ROOT / "AppData" / "Local")
        os.environ["USERPROFILE"] = str(TEMP_ROOT)
        os.environ["HOME"] = str(TEMP_ROOT)
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        sys.path.insert(0, os.environ["OMS_PROJECT"])

        from core.app_paths import DATA_DIR, BACKUP_DIR
        for path in (DATA_DIR, BACKUP_DIR):
            assert path.resolve().is_relative_to(TEMP_ROOT), path

        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QApplication
        import ui.utils.updater as updater

        BEKLEME = float(os.environ["OMS_CHECK_SLEEP"])

        def _yavas_run(self):
            time.sleep(BEKLEME)          # ağ erişimi YOK — yavaş yanıt temsili

        def _yavas_run_izli(self):
            _yavas_run(self)
            print("CHECKER_BITTI", flush=True)

        updater.StartupUpdateChecker.run = _yavas_run_izli

        _orig_exec = QApplication.exec

        def _guvenlik_cikisi():
            # Yalnız uygulama gerçekten takılırsa devreye girer; normalde
            # kapanışı UYGULAMA kendi mantığıyla tamamlar.
            print("GUVENLIK_CIKISI", flush=True)
            QApplication.quit()

        def _exec(*_a):
            # Kullanıcı pencereyi kontrol bitmeden kapatıyor
            QTimer.singleShot(400, lambda: QApplication.instance().closeAllWindows())
            QTimer.singleShot(30000, _guvenlik_cikisi)
            return _orig_exec()

        QApplication.exec = staticmethod(_exec)

        import main
        try:
            main.main()
        except SystemExit as exc:
            print("SYSTEMEXIT", exc.code)
        print("TEARDOWN_BASLIYOR")
        """
    )

    def _run_shutdown(self, sleep_seconds: float):
        with tempfile.TemporaryDirectory(prefix="oms_k6_") as tmp:
            script = Path(tmp) / "kapanis.py"
            script.write_text(self.SCRIPT, encoding="utf-8")
            env = os.environ.copy()
            env.update({
                "OMS_PROJECT": str(PROJECT_ROOT),
                "OMS_TEMP_ROOT": tmp,
                "OMS_CHECK_SLEEP": str(sleep_seconds),
                "PYTHONIOENCODING": "utf-8",
                "PYTHONUNBUFFERED": "1",
            })
            # LOCALAPPDATA alt süreçte, proje importlarından ÖNCE ayarlanır.
            # encoding açıkça verilir: alt süreç UTF-8 yazar, varsayılan
            # çözümleme ise sistem yerel ayarını (cp1254) kullanırdı.
            return subprocess.run(
                [sys.executable, str(script)], env=env, timeout=180,
                capture_output=True, encoding="utf-8", errors="replace")

    def _assert_temiz_cikis(self, proc, senaryo: str):
        self.assertIn("TEARDOWN_BASLIYOR", proc.stdout, senaryo)
        self.assertNotIn("GUVENLIK_CIKISI", proc.stdout,
                         f"{senaryo}: uygulama kendi kapanamadı, güvenlik "
                         f"zamanlayıcısı devreye girdi")
        self.assertEqual(
            proc.returncode, 0,
            f"{senaryo}: süreç temiz kapanmadı (kod={proc.returncode}); "
            f"0xC0000409 = çalışan QThread yok edildi.\n"
            f"stdout kuyruğu:\n{proc.stdout[-1500:]}")

    def _assert_checker_once_bitti(self, proc, senaryo: str):
        """Süreç, checker gerçekten bitmeden sonlanmamalı."""
        self.assertIn("CHECKER_BITTI", proc.stdout,
                      f"{senaryo}: checker bitmeden süreç kapanmış")
        self.assertLess(
            proc.stdout.index("CHECKER_BITTI"),
            proc.stdout.index("TEARDOWN_BASLIYOR"),
            f"{senaryo}: teardown checker'dan önce başlamış")

    def test_shutdown_while_update_check_running_does_not_crash(self):
        # Kontrol, pencere kapandığında hâlâ çalışıyor (bekleme sınırı içinde).
        proc = self._run_shutdown(3.0)
        self._assert_temiz_cikis(proc, "3 sn")
        self._assert_checker_once_bitti(proc, "3 sn")

    def test_pathological_slow_check_still_exits_cleanly(self):
        # Bekleme sınırını (5 sn) AŞAN kontrol: kapanış ertelenmeli, süreç
        # checker bitmeden sonlanmamalı ve yine 0 ile çıkmalı.
        proc = self._run_shutdown(8.0)
        self._assert_temiz_cikis(proc, "8 sn patolojik")
        self._assert_checker_once_bitti(proc, "8 sn patolojik")
        self.assertIn("SYSTEMEXIT 0", proc.stdout)

    def test_closing_backup_taken_only_once_when_close_deferred(self):
        # Kapanış ertelenip closeEvent ikinci kez çalışsa bile yedek tektir.
        proc = self._run_shutdown(8.0)
        self.assertEqual(
            proc.stdout.count("Kapanma yedeği alındı"), 1,
            f"kapanma yedeği birden fazla alınmış:\n{proc.stdout[-2000:]}")

    def test_normal_shutdown_still_clean(self):
        # Kontrol grubu: güncelleme kontrolü kapanmadan çok önce bitiyor.
        proc = self._run_shutdown(0.05)
        self.assertIn("SYSTEMEXIT 0", proc.stdout)
        self.assertIn("Uygulama kapatıldı", proc.stdout)
        self.assertEqual(proc.returncode, 0, proc.stdout[-1500:])
        self.assertNotIn("ertelendi", proc.stdout,
                         "normal kapanışta gecikme/erteleme olmamalı")
        self.assertEqual(proc.stdout.count("Kapanma yedeği alındı"), 1)


class DeferredCloseGuardTests(unittest.TestCase):
    """Erteleme tekrarlansa da finished→close bağlantısı bir kez kurulmalı."""

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_finished_close_connected_only_once(self):
        import time
        from PySide6.QtWidgets import QApplication
        from ui.main_window import MainWindow

        class _Checker(QThread):
            def run(self):
                time.sleep(1.0)

        class _SahtePencere:
            _UPDATE_CHECK_WAIT_MS = 50          # hemen zaman aşımına uğrasın
            def __init__(self, checker):
                self._update_checker = checker
                self._close_after_checker_connected = False
                self._close_deferred = False
                self.hide_sayisi = 0
            def hide(self):
                self.hide_sayisi += 1
            def close(self):
                pass

        checker = _Checker()
        pencere = _SahtePencere(checker)
        # Erteleme otomatik çıkışı kapatıyor — testten sonra geri al.
        self.addCleanup(QApplication.setQuitOnLastWindowClosed, True)
        checker.start()
        try:
            self.assertFalse(MainWindow._await_update_checker(pencere))
            self.assertFalse(MainWindow._await_update_checker(pencere))
            self.assertTrue(pencere._close_after_checker_connected)
            self.assertEqual(pencere.hide_sayisi, 1,
                             "erteleme bloğu birden fazla kez çalışmış")
        finally:
            checker.wait(5000)


class TimeoutAlignmentTests(unittest.TestCase):
    """Ağ zaman aşımı ile kapanış bekleme sınırı birbiriyle uyumlu olmalı."""

    def test_close_wait_bound_covers_network_timeout(self):
        from ui.main_window import MainWindow
        from ui.utils.updater import STARTUP_CHECK_TIMEOUT
        self.assertGreater(
            MainWindow._UPDATE_CHECK_WAIT_MS, STARTUP_CHECK_TIMEOUT * 1000,
            "kapanış beklemesi ağ zaman aşımını kapsamıyor")
        self.assertLessEqual(
            MainWindow._UPDATE_CHECK_WAIT_MS, 10_000,
            "kapanışta kabul edilemez uzunlukta bekleme")
        self.assertGreater(STARTUP_CHECK_TIMEOUT, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
