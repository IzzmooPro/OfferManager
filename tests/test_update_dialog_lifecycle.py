"""K6-B — UpdateDialog: kapatma istendiğinde kurulum başlatılmamalı.

_Downloader.download_finished sinyali run() İÇİNDE emit edilir; QThread'in
yerleşik finished() sinyali ise run() döndükten SONRA gelir. Bu yüzden
ertelenmiş kapanış tamamlanmadan önce _on_downloaded() çalışır ve
_apply_update() kurulumu başlatır (frozen modda os.startfile + os._exit).
Kullanıcı X / "Daha sonra" / Esc demişse bu OLMAMALIDIR.

Gerçek ağ, gerçek indirme, tarayıcı ve kurulum başlatma testte bloklanır.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import tempfile
import time
import unittest
import urllib.request
import webbrowser
from pathlib import Path
from unittest import mock

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox

import ui.utils.updater as updater
from ui.utils.updater import UpdateDialog


class _SahteYanit:
    """urlopen yerine: yavaş yanıt veren dosya benzeri nesne."""

    headers = {"Content-Length": "1024"}

    def __init__(self, blok, hata=False):
        self._kalan = 2
        self._blok = blok
        self._hata = hata

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self, n=None):
        if self._kalan <= 0:
            return b""
        self._kalan -= 1
        time.sleep(self._blok / 2)
        if self._hata:
            raise OSError("sahte indirme hatasi")
        return b"x" * 512


class UpdateDialogCloseDuringDownloadTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="oms_upd_")
        self.addCleanup(self._tmp.cleanup)

        # İndirme geçici dizini kontrol altında olsun. Uygulama bu klasörü
        # boşsa kaldırabildiği için DIŞ geçici dizin ayrı tutulur; aksi hâlde
        # testin kendi temizliği bozulur.
        self._indirme_dizinleri = []
        self._patch(updater.tempfile, "mkdtemp", self._sahte_mkdtemp)

        # Kurulum/tarayıcı/süreç sonlandırma yolları: sayılır ama ASLA çalışmaz
        self.apply_update = self._patch(UpdateDialog, "_apply_update")
        self.web_open = self._patch(webbrowser, "open")
        self.os_startfile = self._patch(os, "startfile", olustur=True)
        self.os_exit = self._patch(os, "_exit")

        # Modal kutular testi kilitlemesin
        self.msg_warning = self._patch(QMessageBox, "warning")
        self._patch(QMessageBox, "information")
        self._patch(QMessageBox, "critical")

    def _sahte_mkdtemp(self, *a, **k):
        dizin = Path(self._tmp.name) / f"TeklifUpdate_{len(self._indirme_dizinleri)}"
        dizin.mkdir()
        self._indirme_dizinleri.append(dizin)
        return str(dizin)

    @property
    def indirme_dizini(self) -> Path:
        self.assertTrue(self._indirme_dizinleri, "indirme dizini oluşturulmadı")
        return self._indirme_dizinleri[-1]

    @property
    def installer_yolu(self) -> Path:
        return self.indirme_dizini / "TeklifYonetim_Setup.exe"

    def _patch(self, hedef, ad, yeni=None, olustur=False):
        kw = {"create": True} if olustur else {}
        patcher = (mock.patch.object(hedef, ad, yeni, **kw) if yeni is not None
                   else mock.patch.object(hedef, ad, **kw))
        sahte = patcher.start()
        self.addCleanup(patcher.stop)
        return sahte

    # ── yardımcılar ──────────────────────────────────────────────────────

    def _pump(self, saniye):
        bitis = time.monotonic() + saniye
        while time.monotonic() < bitis:
            self.app.processEvents()
            time.sleep(0.005)

    def _pump_until(self, kosul, timeout=20.0):
        bitis = time.monotonic() + timeout
        while time.monotonic() < bitis:
            self.app.processEvents()
            if kosul():
                return True
            time.sleep(0.01)
        return False

    def _indirme_baslat(self, blok=1.2, hata=False):
        self._patch(urllib.request, "urlopen",
                    lambda *a, **k: _SahteYanit(blok, hata))
        dlg = UpdateDialog("v9.9", "https://ornek.invalid/Setup.exe")
        self.addCleanup(self._join, dlg)
        dlg.show()
        dlg._start_update()
        self.assertTrue(
            self._pump_until(lambda: dlg._downloader is not None
                             and dlg._downloader.isRunning(), 5.0),
            "indirme başlamadı")
        return dlg

    def _join(self, dlg):
        w = getattr(dlg, "_downloader", None)
        if w is not None:
            try:
                if w.isRunning():
                    w.wait(20000)
            except RuntimeError:
                pass
        self._pump(0.05)

    def _indirme_bitene_kadar(self, dlg):
        self.assertTrue(
            self._pump_until(lambda: not dlg._downloader.isRunning(), 20.0),
            "indirme bitmedi")
        self._pump(0.4)          # kuyruklanmış sinyaller işlensin

    def _yasak_yollar_cagrilmadi(self):
        self.assertEqual(self.web_open.call_count, 0, "webbrowser.open çağrıldı")
        self.assertEqual(self.os_startfile.call_count, 0, "os.startfile çağrıldı")
        self.assertEqual(self.os_exit.call_count, 0, "os._exit çağrıldı")

    # ── testler ──────────────────────────────────────────────────────────

    def test_close_request_prevents_installer_launch(self):
        dlg = self._indirme_baslat()
        dlg.close()                                   # X
        self.assertTrue(dlg.isVisible(), "kapatma ertelenmedi")

        self._indirme_bitene_kadar(dlg)
        self.assertEqual(self.apply_update.call_count, 0,
                         "kapatma istendiği hâlde kurulum başlatıldı")
        self._yasak_yollar_cagrilmadi()

    def test_later_button_path_prevents_installer_launch(self):
        dlg = self._indirme_baslat()
        dlg.reject()                                  # "Daha sonra" / Esc ortak yolu
        self.assertTrue(dlg.isVisible(), "kapatma ertelenmedi")

        self._indirme_bitene_kadar(dlg)
        self.assertEqual(self.apply_update.call_count, 0)
        self._yasak_yollar_cagrilmadi()

    def test_escape_prevents_installer_launch(self):
        dlg = self._indirme_baslat()
        QTest.keyClick(dlg, Qt.Key.Key_Escape)
        self.assertTrue(dlg.isVisible(), "kapatma ertelenmedi")

        self._indirme_bitene_kadar(dlg)
        self.assertEqual(self.apply_update.call_count, 0)
        self._yasak_yollar_cagrilmadi()

    def test_dialog_closes_after_worker_finishes(self):
        dlg = self._indirme_baslat()
        dlg.close()
        self.assertTrue(dlg.isVisible())

        self.assertTrue(self._pump_until(lambda: not dlg.isVisible(), 20.0),
                        "worker bitmesine rağmen dialog kapanmadı")
        self.assertFalse(dlg._downloader.isRunning())

    def test_no_error_box_when_download_fails_during_close(self):
        dlg = self._indirme_baslat(hata=True)
        dlg.close()

        self._indirme_bitene_kadar(dlg)
        self.assertEqual(self.msg_warning.call_count, 0,
                         "kapanış sırasında indirme hatası kutusu açıldı")
        self.assertEqual(self.apply_update.call_count, 0)
        self._yasak_yollar_cagrilmadi()

    def test_normal_download_still_applies_update(self):
        dlg = self._indirme_baslat(blok=0.2)
        self._indirme_bitene_kadar(dlg)               # kapatma İSTENMEDİ
        self.assertEqual(self.apply_update.call_count, 1,
                         "normal indirmede kurulum akışı çalışmadı")

    # ── Kullanılmayan kurulum dosyasının temizliği ───────────────────────

    def test_downloaded_installer_removed_when_close_requested(self):
        dlg = self._indirme_baslat()
        dlg.close()
        self._indirme_bitene_kadar(dlg)

        self.assertFalse(self.installer_yolu.exists(),
                         "kullanılmayacak kurulum dosyası silinmedi")

    def test_empty_download_folder_removed(self):
        dlg = self._indirme_baslat()
        dizin = self.indirme_dizini
        dlg.close()
        self._indirme_bitene_kadar(dlg)

        self.assertFalse(dizin.exists(),
                         "boş kalan geçici indirme klasörü kaldırılmadı")

    def test_other_files_in_download_folder_are_preserved(self):
        dlg = self._indirme_baslat()
        dizin = self.indirme_dizini
        baska = dizin / "kullanicinin_dosyasi.txt"
        baska.write_text("dokunma", encoding="utf-8")

        dlg.close()
        self._indirme_bitene_kadar(dlg)

        self.assertFalse(self.installer_yolu.exists(), "kurulum dosyası silinmedi")
        self.assertTrue(dizin.exists(), "dolu klasör kaldırılmış")
        self.assertTrue(baska.exists(), "klasördeki başka dosya silinmiş")
        self.assertEqual(baska.read_text(encoding="utf-8"), "dokunma")

    def test_close_is_safe_when_delete_fails(self):
        dlg = self._indirme_baslat()
        dlg.close()

        with mock.patch.object(Path, "unlink",
                               side_effect=OSError("dosya kilitli")):
            self._indirme_bitene_kadar(dlg)
            kapandi = self._pump_until(lambda: not dlg.isVisible(), 20.0)

        self.assertTrue(kapandi, "silme hatası kapanışı engelledi")
        self.assertEqual(self.apply_update.call_count, 0,
                         "silme hatasında kurulum başlatıldı")
        self._yasak_yollar_cagrilmadi()
        self.assertTrue(self.installer_yolu.exists(),
                        "silinemeyen dosya beklenmedik şekilde yok")

    def test_normal_download_keeps_installer_file(self):
        dlg = self._indirme_baslat(blok=0.2)
        self._indirme_bitene_kadar(dlg)               # kapatma İSTENMEDİ

        self.assertEqual(self.apply_update.call_count, 1)
        self.assertTrue(self.installer_yolu.exists(),
                        "normal güncelleme yolunda kurulum dosyası silinmiş")


if __name__ == "__main__":
    unittest.main(verbosity=2)
