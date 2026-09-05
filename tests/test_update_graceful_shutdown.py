"""Güncelleme, ana pencerenin veri koruyan kapanışını atlamaz."""
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMainWindow

import ui.utils.updater as updater
from ui.utils.updater import UpdateDialog


class UpdateGracefulShutdownTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        updater._pending_installer_path = None
        self.main = QMainWindow()
        self.main.show()
        self.dialog = UpdateDialog("v9.9", "https://example.test/setup", self.main,
                                   expected_sha256="a" * 64, expected_size=1)
        self.dialog.show()
        self.startfile = mock.patch.object(os, "startfile", create=True).start()
        self.quit = mock.patch.object(QApplication, "quit").start()
        self.error_box = mock.patch.object(
            UpdateDialog, "_hata_kutusu_goster").start()
        self.frozen = mock.patch.object(sys, "frozen", True, create=True).start()
        self.addCleanup(mock.patch.stopall)
        self.addCleanup(self.main.close)
        self.addCleanup(self.dialog.close)

    def _pump(self):
        for _ in range(5):
            self.app.processEvents()

    def test_cancelled_main_close_never_starts_installer(self):
        with mock.patch.object(self.main, "close", return_value=False):
            self.dialog._apply_update("C:/temp/update.exe")
        self._pump()
        self.startfile.assert_not_called()
        self.quit.assert_not_called()
        self.assertTrue(self.dialog.isVisible())
        self.assertTrue(self.dialog._btn_update.isEnabled())

    def test_installer_starts_only_after_main_window_closed(self):
        self.dialog._apply_update("C:/temp/update.exe")
        self._pump()
        self.assertFalse(self.main.isVisible())
        self.startfile.assert_not_called()
        self.quit.assert_called_once()
        self.assertTrue(updater.launch_pending_installer())
        self.startfile.assert_called_once_with("C:/temp/update.exe")

    def test_deferred_shutdown_waits_before_starting_installer(self):
        callbacks = []

        def _defer_close():
            self.main._shutdown_prepared = True
            return False

        with mock.patch.object(self.main, "close", side_effect=_defer_close), \
             mock.patch.object(updater.QTimer, "singleShot",
                               side_effect=lambda _ms, cb: callbacks.append(cb)):
            self.dialog._apply_update("C:/temp/update.exe")
            self.startfile.assert_not_called()
            self.assertEqual(len(callbacks), 1)
            self.main.hide()
            callbacks.pop()()

        self.startfile.assert_not_called()
        self.quit.assert_called_once()
        self.assertTrue(updater.launch_pending_installer())
        self.startfile.assert_called_once_with("C:/temp/update.exe")

    def test_installer_start_failure_is_reported_and_app_exits_cleanly(self):
        self.startfile.side_effect = OSError("C:/secret/path")
        self.dialog._apply_update("C:/temp/update.exe")
        self._pump()
        self.quit.assert_called_once()
        with self.assertLogs("updater", level="WARNING") as logs:
            self.assertFalse(updater.launch_pending_installer())
        combined = " ".join(logs.output)
        self.assertNotIn("C:/secret/path", combined)
        self.assertNotIn("Traceback", combined)

    def test_no_pending_installer_is_a_noop(self):
        self.assertIsNone(updater.launch_pending_installer())
        self.startfile.assert_not_called()

    def test_main_closes_database_before_launching_installer(self):
        source = (Path(__file__).parents[1] / "main.py").read_text(encoding="utf-8")
        self.assertLess(source.index("_veritabanini_kapat()"),
                        source.index("launch_pending_installer()"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
