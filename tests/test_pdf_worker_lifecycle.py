"""PdfWorker yaşam döngüsü — `result_ready` ≠ `finished`.

`result_ready`, `PdfWorker.run()` İÇİNDE yayılır; QThread'in yerleşik
`finished()` sinyali ise `run()` DÖNDÜKTEN SONRA gelir. Bu yüzden sonuç
slot'u worker'ı temizlerse, thread hâlâ çalışırken referans kaybolur ve
`MainWindow._shutdown_workers()` onu göremez → kapanışta çalışan QThread yok
edilir (Windows'ta `0xC0000409` fast-fail sınıfı).

Sözleşme:
  * Sonuç slot'u YALNIZ sonuçları ve güvenli hata mesajlarını işler.
  * `deleteLater`, referans temizliği ve UI geri alma YALNIZ yerleşik
    `finished` yolunda yapılır.
  * Gecikmiş ESKİ worker'ın `finished` sinyali YENİ worker referansını
    temizlemez.
  * Yerleşik `finished` gölgelenmez.

Gerçek kullanıcı verisi, ağ ve dosya sistemi çıktısı KULLANILMAZ.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import subprocess
import sys
import textwrap
import unittest
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import mock

from PySide6.QtWidgets import QApplication, QMessageBox, QWidget

import ui.dashboard_page as dp

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _teklif(oid=1):
    return SimpleNamespace(id=oid, offer_no=f"T-{oid}", company_name="Firma",
                           customer_email="", currency="TL", items=[])


class _SahteThread:
    """Gerçek QThread yerine: isRunning() kontrol edilebilir."""

    def __init__(self, calisiyor=True):
        self._calisiyor = calisiyor
        self.deleteLater_sayisi = 0

    def isRunning(self):
        return self._calisiyor

    def deleteLater(self):
        self.deleteLater_sayisi += 1

    def bitir(self):
        self._calisiyor = False


class _Temel(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.kutular = []
        mock.patch.object(
            QMessageBox, "exec",
            lambda kutu, *a, **k: (self.kutular.append(kutu.text()),
                                   QMessageBox.StandardButton.Ok)[1]).start()
        for ad in ("warning", "information", "critical"):
            mock.patch.object(
                QMessageBox, ad,
                staticmethod(lambda p, b, m, *a, **k:
                             (self.kutular.append(m),
                              QMessageBox.StandardButton.Ok)[1])).start()
        self.addCleanup(mock.patch.stopall)
        from core.app_paths import LOG_DIR
        LOG_DIR.mkdir(parents=True, exist_ok=True)

    def _sayfa(self):
        d = dp.DashboardPage.__new__(dp.DashboardPage)
        QWidget.__init__(d)
        self.addCleanup(d.deleteLater)
        d.svc_o = mock.MagicMock()
        d._model = mock.MagicMock()
        d._pdf_btn = mock.MagicMock()
        d._pdf_worker = None
        d._send_email = mock.MagicMock()
        d._show_preview_dialog = mock.MagicMock()
        return d


# ── 1. Sonuç slot'u çalışan worker'ı bırakmaz ───────────────────────────────

class SonucSlotuTests(_Temel):

    def test_calisan_worker_referansi_korunur(self):
        d = self._sayfa()
        w = _SahteThread(calisiyor=True)
        d._pdf_worker = w
        dp.DashboardPage._on_pdf_finished(d, [], [])
        self.assertIs(d._pdf_worker, w,
                      "worker HÂLÂ ÇALIŞIRKEN referans temizlendi")
        self.assertEqual(w.deleteLater_sayisi, 0,
                         "çalışan worker'a deleteLater çağrıldı")

    def test_shutdown_workers_calisan_worker_i_gorebiliyor(self):
        """MainWindow sözleşmesi: sayfa `_pdf_worker` alanından okur."""
        from ui.main_window import MainWindow
        d = self._sayfa()
        w = _SahteThread(calisiyor=True)
        d._pdf_worker = w
        dp.DashboardPage._on_pdf_finished(d, [], [])

        mw = MainWindow.__new__(MainWindow)
        mw.pages = {0: d}
        calisan = MainWindow._shutdown_workers(mw)
        self.assertIn(w, calisan,
                      "sonuç slot'undan sonra çalışan worker görünmüyor")

    def test_sonuc_slotu_hata_kutusunu_yine_gosterir(self):
        d = self._sayfa()
        d._pdf_worker = _SahteThread(calisiyor=True)
        dp.DashboardPage._on_pdf_finished(d, [], [(RuntimeError("x"), 5)])
        self.assertTrue(self.kutular, "güvenli hata mesajı gösterilmedi")


# ── 2. Temizlik yalnız yerleşik finished yolunda ────────────────────────────

class FinishedTemizligiTests(_Temel):

    def _temizlik_slotu(self, d):
        ad = next((a for a in ("_on_pdf_worker_finished", "_pdf_worker_bitti")
                   if hasattr(dp.DashboardPage, a)), None)
        self.assertIsNotNone(
            ad, "yerleşik finished için ayrı temizlik slot'u yok")
        return getattr(dp.DashboardPage, ad)

    def test_finished_temizligi_tam_bir_kez(self):
        d = self._sayfa()
        w = _SahteThread(calisiyor=False)
        d._pdf_worker = w
        slot = self._temizlik_slotu(d)
        slot(d, w)
        self.assertIsNone(d._pdf_worker, "finished sonrası referans kalmadı")
        self.assertEqual(w.deleteLater_sayisi, 1, "deleteLater 1 kez olmalı")
        self.assertEqual(d._pdf_btn.setEnabled.call_count, 1,
                         "PDF düğmesi tam bir kez etkinleştirilmeli")

    def test_gecikmis_eski_worker_yeni_referansi_temizlemez(self):
        d = self._sayfa()
        eski, yeni = _SahteThread(False), _SahteThread(True)
        d._pdf_worker = yeni
        self._temizlik_slotu(d)(d, eski)
        self.assertIs(d._pdf_worker, yeni,
                      "eski worker'ın gecikmiş finished'ı yeni referansı sildi")
        self.assertEqual(eski.deleteLater_sayisi, 1,
                         "eski worker yine de serbest bırakılmalı")

    def test_gecikmis_eski_worker_yeni_ui_durumunu_bozmaz(self):
        """Eski `finished`, YENİ worker'ın çalışma durumunu ELLEMEZ.

        Aksi hâlde yeni iş sürerken bekleme imleci kalkar ve PDF düğmesi
        erkenden etkinleşir (kullanıcı ikinci kez başlatabilir).
        """
        from PySide6.QtWidgets import QApplication as _QApp
        d = self._sayfa()
        eski, yeni = _SahteThread(False), _SahteThread(True)
        d._pdf_worker = yeni
        with mock.patch.object(_QApp, "restoreOverrideCursor") as imlec:
            self._temizlik_slotu(d)(d, eski)
        self.assertEqual(eski.deleteLater_sayisi, 1,
                         "eski worker serbest bırakılmalı")
        self.assertIs(d._pdf_worker, yeni, "yeni referans korunmalı")
        self.assertEqual(imlec.call_count, 0,
                         "eski worker yeni işin bekleme imlecini kaldırdı")
        self.assertEqual(d._pdf_btn.setEnabled.call_count, 0,
                         "eski worker PDF düğmesini erken etkinleştirdi")
        self.assertTrue(yeni.isRunning(), "yeni worker etkilenmemeli")

    def test_guncel_worker_finished_ui_yi_geri_alir(self):
        from PySide6.QtWidgets import QApplication as _QApp
        d = self._sayfa()
        w = _SahteThread(calisiyor=False)
        d._pdf_worker = w
        with mock.patch.object(_QApp, "restoreOverrideCursor") as imlec:
            self._temizlik_slotu(d)(d, w)
        self.assertEqual(imlec.call_count, 1, "imleç tam bir kez geri alınmalı")
        self.assertEqual(d._pdf_btn.setEnabled.call_count, 1)
        self.assertEqual(d._pdf_btn.setEnabled.call_args.args, (True,))
        self.assertEqual(w.deleteLater_sayisi, 1)
        self.assertIsNone(d._pdf_worker)

    def test_sonuc_slotu_patlasa_da_temizlik_calisir(self):
        """İki bağlantı AYRI olmalı: sonuç hatası temizliği engellememeli."""
        d = self._sayfa()
        w = _SahteThread(calisiyor=False)
        d._pdf_worker = w
        with mock.patch.object(dp.DashboardPage, "_on_pdf_finished",
                               side_effect=RuntimeError("slot patladı")):
            with self.assertRaises(RuntimeError):
                dp.DashboardPage._on_pdf_finished(d, [], [])
        self._temizlik_slotu(d)(d, w)
        self.assertIsNone(d._pdf_worker)
        self.assertEqual(w.deleteLater_sayisi, 1)

    def test_gen_pdf_finished_baglantisi_kuruyor(self):
        """`_gen_pdf` hem result_ready hem yerleşik finished'a bağlanmalı."""
        import inspect
        govde = inspect.getsource(dp.DashboardPage._gen_pdf)
        self.assertIn("result_ready.connect", govde)
        self.assertIn(".finished.connect", govde,
                      "yerleşik finished sinyaline bağlanılmıyor")

    def test_qthread_finished_golgelenmiyor(self):
        self.assertNotIn("finished", vars(dp.PdfWorker))


# ── 3. Zorlanmış gerçek Qt yarışı (izole alt süreç) ─────────────────────────

class GercekYarisTests(unittest.TestCase):
    """result_ready yayıldıktan sonra run() bir kapıda bekler."""

    BETIK = textwrap.dedent('''
        import os, sys, time
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        kok = sys.argv[1]
        gecici = sys.argv[2]
        for k in ("LOCALAPPDATA", "APPDATA", "USERPROFILE", "HOME", "TMP", "TEMP"):
            os.environ[k] = gecici
        os.environ["PYTHON_KEYRING_BACKEND"] = "keyring.backends.null.Keyring"
        sys.path.insert(0, kok)
        from PySide6.QtCore import QThread, QTimer
        from PySide6.QtWidgets import QApplication, QMessageBox, QWidget
        from unittest import mock
        app = QApplication([])
        import ui.dashboard_page as dp
        from ui.main_window import MainWindow

        kapi = {"acik": False}

        class KapiliWorker(dp.PdfWorker):
            def run(self):
                self.result_ready.emit([], [])       # run() İÇİNDE
                while not kapi["acik"]:
                    time.sleep(0.01)

        d = dp.DashboardPage.__new__(dp.DashboardPage)
        QWidget.__init__(d)
        d.svc_o = d._model = mock.MagicMock()
        d._pdf_btn = mock.MagicMock()
        d._pdf_worker = None
        mw = MainWindow.__new__(MainWindow)
        mw.pages = {0: d}

        iz = []
        w = KapiliWorker([])
        d._pdf_worker = w
        w.result_ready.connect(lambda g, e: dp.DashboardPage._on_pdf_finished(d, g, e))
        temizlik = getattr(dp.DashboardPage, "_on_pdf_worker_finished", None)
        if temizlik is not None:
            w.finished.connect(lambda: temizlik(d, w))
        w.start()

        def olc():
            app.processEvents()
            calisan = MainWindow._shutdown_workers(mw)
            iz.append(("calisirken_gorunur", any(x is w for x in calisan),
                       w.isRunning()))
            kapi["acik"] = True
            w.wait(20000)
            app.processEvents(); app.processEvents()
            iz.append(("bitince_referans", d._pdf_worker is None))
            for satir in iz:
                print("IZ", satir)
            app.quit()

        QTimer.singleShot(600, olc)
        QTimer.singleShot(25000, app.quit)          # watchdog
        sys.exit(app.exec())
    ''')

    def test_calisirken_gorunur_bitince_temizlenir(self):
        with TemporaryDirectory(prefix="pdfwlc_") as gecici:
            betik = os.path.join(gecici, "yaris.py")
            with open(betik, "w", encoding="utf-8") as f:
                f.write(self.BETIK)
            sonuc = subprocess.run(
                [sys.executable, betik, KOK, gecici],
                capture_output=True, text=True, timeout=120)
        cikti = sonuc.stdout
        self.assertEqual(sonuc.returncode, 0,
                         f"alt süreç temiz çıkmadı:\n{cikti}\n{sonuc.stderr[-800:]}")
        self.assertIn("IZ ('calisirken_gorunur', True, True)", cikti,
                      f"worker çalışırken görünmüyor:\n{cikti}")
        self.assertIn("IZ ('bitince_referans', True)", cikti,
                      f"finished sonrası referans temizlenmedi:\n{cikti}")
        for yasak in ("QThread: Destroyed while thread is still running",
                      "0xC0000409"):
            self.assertNotIn(yasak, sonuc.stderr, f"native uyarı: {yasak}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
