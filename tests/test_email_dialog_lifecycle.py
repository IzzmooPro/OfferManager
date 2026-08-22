"""K6-C — EmailDialog gönderim sırasında kapatılırsa worker yaşam döngüsü.

Eski davranış: closeEvent, etkisiz quit() sonrası UI thread'inde 4 sn
wait() yapıyor, süre dolunca dialog çalışan worker'la birlikte kapanıyordu.
Beklenen: kapatma isteği ERTELENİR (event.ignore), UI donmaz, worker
gerçekten bitince pencere kendiliğinden kapanır.

Gerçek e-posta gönderilmez; smtplib sahte bir sunucuyla değiştirilir.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import smtplib
import tempfile
import time
import unittest
import warnings
from pathlib import Path
from unittest import mock

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox, QPushButton

from ui.dialogs.email_dialog import EmailDialog, EmailWorker


def _fake_smtp(block_seconds: float):
    """send_message'ta `block_seconds` bloklayan sahte SMTP sunucusu."""

    class _FakeSMTP:
        def __init__(self, host, port, timeout=None):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def ehlo(self, *a):
            return (250, b"ok")

        def starttls(self, *, context=None):
            return (220, b"ready")

        def login(self, user, password):
            return (235, b"ok")

        def send_message(self, message):
            time.sleep(block_seconds)      # smtplib'in bloklayan işi
            return {}

    return _FakeSMTP


class EmailDialogCloseWhileSendingTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="oms_k6c_")
        self.addCleanup(self._tmp.cleanup)
        self.pdf = Path(self._tmp.name) / "SNS-000001.pdf"
        self.pdf.write_bytes(b"%PDF-1.4 test")
        # Modal mesaj kutuları testte sonsuza kadar bloklar; hepsi baştan
        # yakalanır. Temizlikleri EN SON çalışır (LIFO), böylece worker
        # birleştirilirken de aktif kalırlar.
        self.msg_info = self._patch(QMessageBox, "information")
        self.msg_critical = self._patch(QMessageBox, "critical")
        self.msg_warning = self._patch(QMessageBox, "warning")

    def _patch(self, hedef, ad):
        patcher = mock.patch.object(hedef, ad)
        sahte = patcher.start()
        self.addCleanup(patcher.stop)
        return sahte

    # ── yardımcılar ──────────────────────────────────────────────────────

    def _dialog(self):
        dlg = EmailDialog(pdf_path=str(self.pdf), customer_email="m@n.com",
                          offer_no="SNS-000001")
        # Gerçek SMTP ayarına dokunmadan gönderim ön koşullarını sağla
        dlg.cfg.update({"smtp_server": "smtp.example.com", "smtp_port": "587",
                        "smtp_user": "gonderen@example.com",
                        "smtp_password": "sahte"})
        return dlg

    def _join_worker(self, dlg):
        """Worker'ı bitir — SMTP yaması hâlâ aktifken (temizlik sırası önemli)."""
        worker = getattr(dlg, "worker", None)
        if worker is not None and worker.isRunning():
            worker.wait(20000)
        self._pump(0.05)

    def _pump(self, seconds: float):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(0.005)

    def _pump_until(self, kosul, timeout=25.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.app.processEvents()
            if kosul():
                return True
            time.sleep(0.01)
        return False

    def _start_send(self, dlg, block_seconds):
        patcher = mock.patch.object(smtplib, "SMTP", _fake_smtp(block_seconds))
        patcher.start()
        self.addCleanup(patcher.stop)
        # LIFO: worker birleştirme, yama kaldırılmadan ÖNCE çalışmalı — aksi
        # hâlde çalışan worker gerçek smtplib'e düşüp DNS'e gider.
        self.addCleanup(self._join_worker, dlg)
        dlg.show()
        dlg._send_email()
        if block_seconds == 0.0:
            # Sıfır gecikmeli sahte SMTP, event loop worker'ı isRunning()
            # durumunda gözlemlemeden tamamlayabilir. Bu başarı testi için
            # worker'ın oluşturulması yeterlidir; sonucu aşağıda ayrıca
            # mesaj kutusu + dialog kabulüyle doğrulanır.
            self.assertIsNotNone(dlg.worker, "worker oluşturulmadı")
            return
        self.assertTrue(self._pump_until(lambda: dlg.worker is not None
                                         and dlg.worker.isRunning(), 5.0),
                        "worker başlamadı")

    # ── testler ──────────────────────────────────────────────────────────

    def test_close_while_sending_does_not_block_ui(self):
        dlg = self._dialog()
        self._start_send(dlg, block_seconds=6.0)

        t0 = time.monotonic()
        dlg.close()
        gecen = time.monotonic() - t0

        self.assertLess(gecen, 1.0,
                        f"closeEvent UI thread'ini {gecen:.2f} sn dondurdu "
                        f"(uzun wait() olmamalı)")

    def test_close_while_sending_is_deferred_and_dialog_survives(self):
        dlg = self._dialog()
        self._start_send(dlg, block_seconds=4.0)

        dlg.close()
        # Kapatma ertelenmeli: worker çalışırken pencere kapanmamalı
        self.assertTrue(dlg.worker.isRunning(), "worker beklenmedik şekilde bitti")
        self.assertTrue(dlg.isVisible(),
                        "çalışan worker'a rağmen dialog kapandı")

    def test_dialog_closes_itself_after_worker_finishes(self):
        dlg = self._dialog()
        self._start_send(dlg, block_seconds=1.5)

        dlg.close()
        self.assertTrue(dlg.isVisible(), "kapatma ertelenmedi")
        kapandi = self._pump_until(lambda: not dlg.isVisible(), timeout=20.0)
        self.assertTrue(kapandi, "worker bitmesine rağmen dialog kapanmadı")
        self.assertFalse(dlg.worker.isRunning())

    def test_no_result_messagebox_while_closing(self):
        dlg = self._dialog()
        self._start_send(dlg, block_seconds=1.5)

        dlg.close()
        self._pump_until(lambda: not dlg.isVisible(), timeout=20.0)
        self._pump(0.2)
        self.assertEqual(self.msg_info.call_count, 0,
                         "kapanış sırasında sonuç mesaj kutusu açıldı")
        self.assertEqual(self.msg_critical.call_count, 0,
                         "kapanış sırasında hata mesaj kutusu açıldı")

    def test_repeated_close_requests_create_single_connection(self):
        dlg = self._dialog()
        self._start_send(dlg, block_seconds=3.0)

        for _ in range(3):
            dlg.close()
        self.assertTrue(dlg.isVisible())

        # Bağlantı sayısı: her başarılı disconnect bir bağlantıyı kaldırır.
        # Bağlantı bitince PySide uyarı üretir — sayım yönteminin parçası.
        sayi = 0
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            for _ in range(5):
                try:
                    if dlg.worker.finished.disconnect(dlg.close):
                        sayi += 1
                    else:
                        break
                except (RuntimeError, TypeError):
                    break
        self.assertEqual(sayi, 1,
                         f"finished->close bağlantı sayısı {sayi} (1 olmalı)")

    # ── İptal / Esc de aynı güvenli yolu kullanmalı ─────────────────────

    def _cancel_button(self, dlg) -> QPushButton:
        butonlar = [b for b in dlg.findChildren(QPushButton) if b.text() == "İptal"]
        self.assertEqual(len(butonlar), 1, "İptal butonu bulunamadı")
        return butonlar[0]

    def test_cancel_button_while_sending_defers_close(self):
        dlg = self._dialog()
        self._start_send(dlg, block_seconds=1.5)

        self._cancel_button(dlg).click()
        self.assertTrue(dlg.worker.isRunning(), "worker beklenmedik şekilde bitti")
        self.assertTrue(dlg.isVisible(),
                        "İptal, çalışan worker'a rağmen dialogu kapattı")

        self.assertTrue(self._pump_until(lambda: not dlg.isVisible(), timeout=20.0),
                        "worker bitmesine rağmen dialog kapanmadı")
        self.assertFalse(dlg.worker.isRunning())

    def test_escape_while_sending_defers_close(self):
        dlg = self._dialog()
        self._start_send(dlg, block_seconds=1.5)

        QTest.keyClick(dlg, Qt.Key.Key_Escape)
        self.assertTrue(dlg.worker.isRunning(), "worker beklenmedik şekilde bitti")
        self.assertTrue(dlg.isVisible(),
                        "Esc, çalışan worker'a rağmen dialogu kapattı")

        self.assertTrue(self._pump_until(lambda: not dlg.isVisible(), timeout=20.0),
                        "worker bitmesine rağmen dialog kapanmadı")
        self.assertFalse(dlg.worker.isRunning())

    def test_cancel_without_sending_closes_normally(self):
        dlg = self._dialog()
        dlg.show()
        self._pump(0.05)
        self._cancel_button(dlg).click()
        self._pump(0.05)
        self.assertFalse(dlg.isVisible(), "gönderim yokken İptal kapatmadı")
        self.assertEqual(dlg.result(), QDialog.DialogCode.Rejected)

    def test_escape_without_sending_closes_normally(self):
        dlg = self._dialog()
        dlg.show()
        self._pump(0.05)
        QTest.keyClick(dlg, Qt.Key.Key_Escape)
        self._pump(0.05)
        self.assertFalse(dlg.isVisible(), "gönderim yokken Esc kapatmadı")
        self.assertEqual(dlg.result(), QDialog.DialogCode.Rejected)

    def test_mixed_close_requests_create_single_connection(self):
        dlg = self._dialog()
        self._start_send(dlg, block_seconds=3.0)

        dlg.close()                                    # X
        self._cancel_button(dlg).click()               # İptal
        QTest.keyClick(dlg, Qt.Key.Key_Escape)         # Esc
        dlg.close()
        self.assertTrue(dlg.isVisible())

        sayi = 0
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            for _ in range(5):
                try:
                    if dlg.worker.finished.disconnect(dlg.close):
                        sayi += 1
                    else:
                        break
                except (RuntimeError, TypeError):
                    break
        self.assertEqual(sayi, 1,
                         f"X/İptal/Esc karışık istekler {sayi} bağlantı kurdu")

    def test_successful_send_still_reports_and_accepts(self):
        dlg = self._dialog()
        self._start_send(dlg, block_seconds=0.0)
        bitti = self._pump_until(
            lambda: dlg.worker is not None and not dlg.worker.isRunning(),
            timeout=20.0)
        self.assertTrue(bitti, "gönderim bitmedi")
        self._pump(0.3)
        self.assertEqual(self.msg_info.call_count, 1,
                         "başarılı gönderim bildirimi gösterilmedi")
        self.assertFalse(dlg.isVisible(), "başarılı gönderimde dialog kapanmadı")


if __name__ == "__main__":
    unittest.main(verbosity=2)
