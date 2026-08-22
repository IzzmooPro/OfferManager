"""O12 — otomatik yedek worker'ının yaşam döngüsü ve kapanış güvenliği.

Ölçüm: her tetikleme servise parent'lı bir QThread oluşturuyor, hiç
`deleteLater` edilmiyordu → 500 tetikleme = 500 canlı worker, 0 `destroyed`.
Ayrıca restart kapanışında (O5) kapanma yedeği atlandığı için ÇALIŞAN yedek
thread'i beklenmiyor ve süreç 0xC0000409 (3221226505) ile fast-fail veriyordu.

Gerçek ZIP/DB/ayar KULLANILMAZ: `create_backup`, `_save_meta` ve `_cleanup`
mocklanır; kullanıcı ortamı `tests/conftest.py` tarafından yalıtılır.
"""
import gc
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QDeadlineTimer, QEvent
from PySide6.QtWidgets import QApplication

import ui.dialogs.backup_manager as bm
from ui.main_window import MainWindow

PROJE_KOKU = Path(__file__).resolve().parent.parent


def _olay_isle(ms=250):
    """Qt olaylarını işle; DeferredDelete'i AÇIKÇA teslim et.

    `processEvents()` tek başına DeferredDelete olaylarını her zaman teslim
    etmez; nesne yaşamı ölçülürken bu şart.
    """
    son = QDeadlineTimer(ms)
    while not son.hasExpired():
        QCoreApplication.processEvents()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    gc.collect()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


class _ServisTemeli(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="o12t_",
                                                ignore_cleanup_errors=True)
        self.addCleanup(self._tmp.cleanup)
        self.hedef = Path(self._tmp.name)
        self.yikilan = []
        self._orj_create = bm.create_backup
        self._orj_meta = bm._save_meta
        self._orj_cleanup = bm.AutoBackupService._cleanup
        bm.create_backup = lambda d: str(Path(d) / "sahte.zip")
        bm._save_meta = lambda m: None
        bm.AutoBackupService._cleanup = lambda s, d, keep=20: None
        self.addCleanup(self._geri_al)

        self.svc = bm.AutoBackupService()
        self.svc._meta = {"auto_enabled": False,
                          "auto_backup_dir": str(self.hedef),
                          "auto_interval": 30}
        self.svc._timer.stop()
        self.addCleanup(self._servisi_kapat)

    def _geri_al(self):
        bm.create_backup = self._orj_create
        bm._save_meta = self._orj_meta
        bm.AutoBackupService._cleanup = self._orj_cleanup

    def _worker_bitene_kadar_bekle(self):
        """Çalışan worker'ı bekle — test DÜŞSE bile teardown güvenli olsun."""
        try:
            w = self.svc._worker
        except RuntimeError:
            return
        while w is not None:
            try:
                if not w.isRunning():
                    break
            except RuntimeError:
                break
            QCoreApplication.processEvents()
        _olay_isle(150)

    def _servisi_kapat(self):
        self._worker_bitene_kadar_bekle()
        try:
            self.svc.deleteLater()
        except RuntimeError:
            pass
        _olay_isle(100)

    def _tetikle_ve_bekle(self, adet, reason="test"):
        for _ in range(adet):
            self.svc._run(reason)
            w = self.svc._worker
            if w is not None:
                w.destroyed.connect(
                    lambda _=None: self.yikilan.append(1))
                while w.isRunning():
                    QCoreApplication.processEvents()
            _olay_isle(30)
        _olay_isle(200)

    def _canli_workerlar(self):
        return self.svc.findChildren(bm._BackupWorker)


class WorkerLifecycleTests(_ServisTemeli):

    def _dogrula(self, adet):
        canli = self._canli_workerlar()
        bitmis = [w for w in canli if not w.isRunning()]
        self.assertIsNone(self.svc._worker, "_worker referansı bırakılmadı")
        self.assertEqual(bitmis, [], f"{len(bitmis)} bitmiş worker tutuluyor")
        self.assertEqual(len(self.yikilan), adet,
                         f"{adet} tetikleme için {len(self.yikilan)} destroyed")

    def test_one_trigger_releases_worker(self):
        self._tetikle_ve_bekle(1)
        self._dogrula(1)

    def test_ten_triggers_release_all(self):
        self._tetikle_ve_bekle(10)
        self._dogrula(10)

    def test_hundred_triggers_release_all(self):
        self._tetikle_ve_bekle(100)
        self._dogrula(100)

    def test_five_hundred_triggers_release_all(self):
        self._tetikle_ve_bekle(500)
        self._dogrula(500)
        self.assertEqual(len(self._canli_workerlar()), 0,
                         "500 tetikleme sonrası nesne birikimi var")

    def test_failure_path_also_releases(self):
        bm.create_backup = lambda d: (_ for _ in ()).throw(OSError("disk"))
        self._tetikle_ve_bekle(50, reason="hata")
        self._dogrula(50)

    def test_object_count_does_not_grow_linearly(self):
        self._tetikle_ve_bekle(20)
        yirmi = len(self._canli_workerlar())
        self._tetikle_ve_bekle(180)
        iki_yuz = len(self._canli_workerlar())
        self.assertEqual((yirmi, iki_yuz), (0, 0),
                         "nesne sayısı tetiklemeyle büyüyor")


class StaleCleanupTests(_ServisTemeli):

    def test_stale_worker_does_not_clear_new_reference(self):
        """Eski worker'ın gecikmiş finished'ı yeni referansı silmemeli."""
        self.svc._run("ilk")
        eski = self.svc._worker
        while eski.isRunning():
            QCoreApplication.processEvents()
        _olay_isle(50)
        self.svc._run("ikinci")
        yeni = self.svc._worker
        self.assertIsNotNone(yeni)
        self.assertIsNot(yeni, eski)
        # Eski worker'ın temizlik slotunu ELLE, geç gelmiş gibi çalıştır
        with mock.patch.object(self.svc, "sender", return_value=eski,
                               create=True):
            self.svc._on_worker_finished()
        self.assertIs(self.svc._worker, yeni,
                      "gecikmiş cleanup yeni worker'ı sildi")
        while yeni.isRunning():
            QCoreApplication.processEvents()
        _olay_isle(100)

    def test_reference_not_cleared_while_thread_still_running(self):
        """Sonuç sinyali gelse de thread bitmeden referans bırakılmaz."""
        self.svc._run("t")
        w = self.svc._worker
        self.svc._on_backup_done(str(self.hedef / "x.zip"), "t")
        if w.isRunning():
            self.assertIs(self.svc._worker, w,
                          "thread çalışırken referans bırakıldı")
        while w.isRunning():
            QCoreApplication.processEvents()
        _olay_isle(100)
        self.assertIsNone(self.svc._worker)


class ActiveWorkerApiTests(_ServisTemeli):

    def test_returns_running_worker(self):
        bm.create_backup = lambda d: (time.sleep(0.4) or str(Path(d) / "s.zip"))
        self.svc._run("uzun")
        self.assertIsNotNone(self.svc.active_worker())
        self.assertTrue(self.svc.active_worker().isRunning())
        while self.svc._worker and self.svc._worker.isRunning():
            QCoreApplication.processEvents()
        _olay_isle(150)

    def test_returns_none_when_idle(self):
        self.assertIsNone(self.svc.active_worker())

    def test_returns_none_after_worker_finished(self):
        self._tetikle_ve_bekle(1)
        self.assertIsNone(self.svc.active_worker())

    def test_no_exception_when_cpp_object_deleted(self):
        self.svc._run("t")
        w = self.svc._worker
        while w.isRunning():
            QCoreApplication.processEvents()
        _olay_isle(150)
        # C++ nesnesi silinmiş olsa bile istisna sızmamalı
        self.assertIsNone(self.svc.active_worker())


class SingleBackupPolicyTests(_ServisTemeli):

    def test_second_and_third_trigger_are_skipped(self):
        cagri = {"n": 0}

        def yavas(d):
            cagri["n"] += 1
            time.sleep(0.5)
            return str(Path(d) / "s.zip")

        bm.create_backup = yavas
        self.svc._run("ilk")
        time.sleep(0.08)
        QCoreApplication.processEvents()
        self.svc._run("ikinci")
        self.svc._run("ucuncu")
        calisan = [w for w in self._canli_workerlar() if w.isRunning()]
        self.assertEqual(len(calisan), 1, "paralel yedek başlatıldı")
        while self.svc._worker and self.svc._worker.isRunning():
            QCoreApplication.processEvents()
        _olay_isle(200)
        self.assertEqual(cagri["n"], 1, "ikinci/üçüncü tetikleme atlanmadı")


class ShutdownGateTests(_ServisTemeli):
    """Kapanış başlarken timer susmalı ve yeni worker üretilememeli."""

    def test_begin_shutdown_stops_timer_and_blocks_queued_timeout(self):
        cagrilar = []
        bm.create_backup = lambda d: cagrilar.append(d) or str(Path(d) / "s.zip")
        self.svc._timer.start(60_000)

        self.svc.begin_shutdown()
        # Timer.stop() öncesinde kuyruğa girmiş bir timeout'u temsil eder.
        self.svc._run()

        self.assertFalse(self.svc._timer.isActive())
        self.assertEqual(cagrilar, [], "kapanış başladıktan sonra yedek başlatıldı")
        self.assertIsNone(self.svc.active_worker())

    def test_closing_backup_does_not_overlap_long_running_worker(self):
        cagrilar = []
        bm.create_backup = lambda d: cagrilar.append(d) or str(Path(d) / "s.zip")
        worker = mock.Mock()
        worker.isRunning.return_value = True
        worker.wait.return_value = False
        self.svc._worker = worker
        try:
            tamamlandi = self.svc.trigger_now(reason="kapanma")
        finally:
            self.svc._worker = None

        self.assertIs(tamamlandi, False)
        worker.wait.assert_called_once_with(30_000)
        self.assertEqual(cagrilar, [], "çalışan worker ile paralel kapanma yedeği başladı")
        self.assertFalse(self.svc._timer.isActive())


class TimerAfterDeleteTests(_ServisTemeli):

    def test_no_worker_started_after_service_deleted(self):
        from shiboken6 import Shiboken
        self.svc._timer.setInterval(30)
        self.svc._timer.start()
        _olay_isle(150)
        self.svc.deleteLater()
        _olay_isle(250)
        self.assertFalse(Shiboken.isValid(self.svc))
        oncesi = len(self.yikilan)
        _olay_isle(250)
        self.assertEqual(len(self.yikilan), oncesi,
                         "servis silindikten sonra yeni worker başladı")


class ShutdownInclusionTests(_ServisTemeli):
    """K6 kapanış listesi çalışan yedek worker'ını içermeli."""

    def _pencere(self):
        p = MainWindow.__new__(MainWindow)
        p._shutdown_prepared = False
        p._close_deferred = False
        p._close_connected_workers = []
        p.pages = {}
        p._backup_svc = self.svc
        p._SHUTDOWN_WAIT_MS = 50
        p.hide = lambda: None
        p.close = lambda: None
        return p

    def test_running_backup_is_in_shutdown_workers(self):
        bm.create_backup = lambda d: (time.sleep(0.5) or str(Path(d) / "s.zip"))
        self.svc._run("uzun")
        p = self._pencere()
        self.assertIn(self.svc.active_worker(), p._shutdown_workers(),
                      "çalışan yedek K6 bekleme listesinde yok")
        while self.svc._worker and self.svc._worker.isRunning():
            QCoreApplication.processEvents()
        _olay_isle(200)

    def test_idle_service_adds_nothing(self):
        p = self._pencere()
        self.assertEqual(p._shutdown_workers(), [])

    def test_restart_close_defers_while_backup_runs(self):
        from core import restart
        restart.reset_restart_request()
        self.addCleanup(restart.reset_restart_request)
        bm.create_backup = lambda d: (time.sleep(1.0) or str(Path(d) / "s.zip"))
        self.svc._run("uzun")
        restart.request_restart()
        p = self._pencere()
        olay = mock.Mock()
        with mock.patch.object(self.svc, "trigger_now") as kapanma_yedegi:
            MainWindow.closeEvent(p, olay)
        # Kapanış ERTELENDİ ve restart yolunda kapanma yedeği ALINMADI (O5).
        olay.ignore.assert_called_once()
        olay.accept.assert_not_called()
        kapanma_yedegi.assert_not_called()
        while self.svc._worker and self.svc._worker.isRunning():
            QCoreApplication.processEvents()
        _olay_isle(300)

    def test_finished_close_connection_is_made_once(self):
        bm.create_backup = lambda d: (time.sleep(0.6) or str(Path(d) / "s.zip"))
        self.svc._run("uzun")
        p = self._pencere()
        p._await_running_workers()
        p._await_running_workers()
        self.assertEqual(len(p._close_connected_workers), 1,
                         "finished→close bağlantısı tekrarlandı")
        while self.svc._worker and self.svc._worker.isRunning():
            QCoreApplication.processEvents()
        _olay_isle(200)


class SignalContractTests(_ServisTemeli):
    """Sonuç sinyalleri QThread.finished'i gölgelememeli."""

    def test_finished_is_builtin_qthread_signal(self):
        from PySide6.QtCore import QThread
        self.assertNotIn("finished", vars(bm._BackupWorker),
                         "finished sinyali yeniden tanımlanmış (gölgeleme)")
        self.assertIn("finished", dir(QThread))

    def test_result_signals_have_distinct_names(self):
        self.assertIn("completed", vars(bm._BackupWorker))
        self.assertIn("failed", vars(bm._BackupWorker))


class SlotExceptionTests(_ServisTemeli):
    """Sonuç slot'u patlasa da yerleşik finished temizliği çalışmalı."""

    def test_completed_slot_exception_still_cleans_up(self):
        def patlayan(path, reason=""):
            raise RuntimeError("slot patladı")

        with mock.patch.object(bm.AutoBackupService, "_on_backup_done",
                               patlayan):
            self._tetikle_ve_bekle(20)
        self.assertIsNone(self.svc._worker)
        self.assertEqual([w for w in self._canli_workerlar()
                          if not w.isRunning()], [],
                         "slot hatasında worker birikti")
        self.assertEqual(len(self.yikilan), 20)

    def test_failed_slot_exception_still_cleans_up(self):
        bm.create_backup = lambda d: (_ for _ in ()).throw(OSError("disk"))

        def patlayan(error, reason=""):
            raise RuntimeError("slot patladı")

        with mock.patch.object(bm.AutoBackupService, "_on_backup_failed",
                               patlayan):
            self._tetikle_ve_bekle(20, reason="hata")
        self.assertIsNone(self.svc._worker)
        self.assertEqual([w for w in self._canli_workerlar()
                          if not w.isRunning()], [])
        self.assertEqual(len(self.yikilan), 20)


class ActiveWorkerStateTests(_ServisTemeli):
    """active_worker dört durumda da güvenli olmalı."""

    def test_finished_but_deferred_delete_pending(self):
        self.svc._run("t")
        w = self.svc._worker
        while w.isRunning():
            QCoreApplication.processEvents()
        # DeferredDelete HENÜZ teslim edilmedi
        QCoreApplication.processEvents()
        self.assertIsNone(self.svc.active_worker(),
                          "biten worker aktif sayıldı")
        _olay_isle(150)

    def test_new_worker_after_previous_cleanup(self):
        self._tetikle_ve_bekle(1)
        self.assertIsNone(self.svc.active_worker())
        bm.create_backup = lambda d: (time.sleep(0.4) or str(Path(d) / "s.zip"))
        self.svc._run("yeni")
        aktif = self.svc.active_worker()
        self.assertIsNotNone(aktif)
        self.assertIs(aktif, self.svc._worker)
        while self.svc._worker and self.svc._worker.isRunning():
            QCoreApplication.processEvents()
        _olay_isle(200)

    def test_repeated_calls_are_stable(self):
        self._tetikle_ve_bekle(1)
        for _ in range(5):
            self.assertIsNone(self.svc.active_worker())


class ShutdownDedupeTests(_ServisTemeli):
    """Aynı worker iki yoldan görünse de tek kez beklenmeli."""

    def _pencere_ve_worker(self):
        bm.create_backup = lambda d: (time.sleep(0.8) or str(Path(d) / "s.zip"))
        self.svc._run("uzun")
        # Test düşse bile çalışan thread'i beklemeden servisi yok etme
        # (aksi hâlde teardown'da 0xC0000409 fast-fail oluşur).
        self.addCleanup(self._worker_bitene_kadar_bekle)
        p = MainWindow.__new__(MainWindow)
        p._shutdown_prepared = False
        p._close_deferred = False
        p._close_connected_workers = []
        p._backup_svc = self.svc
        p._SHUTDOWN_WAIT_MS = 50
        p.hide = lambda: None
        p.close = lambda: None
        w = self.svc.active_worker()
        # Aynı worker'ı ikinci bir yoldan da görünür kıl
        sahte_sayfa = mock.Mock()
        sahte_sayfa._pdf_worker = w
        p.pages = {0: sahte_sayfa}
        return p, w

    def test_duplicate_worker_listed_once(self):
        p, w = self._pencere_ve_worker()
        liste = p._shutdown_workers()
        self.assertEqual(sum(1 for x in liste if x is w), 1,
                         "aynı worker iki kez bekleme listesinde")
        while self.svc._worker and self.svc._worker.isRunning():
            QCoreApplication.processEvents()
        _olay_isle(300)

    def test_duplicate_worker_connected_once(self):
        p, w = self._pencere_ve_worker()
        p._await_running_workers()
        self.assertEqual(sum(1 for x in p._close_connected_workers if x is w),
                         1, "finished→close bağlantısı çift kuruldu")
        while self.svc._worker and self.svc._worker.isRunning():
            QCoreApplication.processEvents()
        _olay_isle(300)


class CloseBackupCountTests(_ServisTemeli):
    """Normal kapanış TAM bir kez yedek alır; restart kapanışı almaz."""

    def _pencere(self):
        p = MainWindow.__new__(MainWindow)
        p._shutdown_prepared = False
        p._close_deferred = False
        p._close_connected_workers = []
        p.pages = {}
        p._backup_svc = self.svc
        p._SHUTDOWN_WAIT_MS = 50
        p.hide = lambda: None
        p.close = lambda: None
        return p

    def test_normal_close_triggers_backup_exactly_once(self):
        p = self._pencere()
        with mock.patch.object(self.svc, "trigger_now") as tetik:
            MainWindow.closeEvent(p, mock.Mock())
        tetik.assert_called_once_with(reason="kapanma")

    def test_restart_close_skips_backup_but_waits_worker(self):
        from core import restart
        restart.reset_restart_request()
        self.addCleanup(restart.reset_restart_request)
        bm.create_backup = lambda d: (time.sleep(0.8) or str(Path(d) / "s.zip"))
        self.svc._run("uzun")
        restart.request_restart()
        p = self._pencere()
        olay = mock.Mock()
        with mock.patch.object(self.svc, "trigger_now") as tetik:
            MainWindow.closeEvent(p, olay)
        tetik.assert_not_called()
        self.assertTrue(self.svc._shutdown_started)
        self.assertFalse(self.svc._timer.isActive())
        olay.ignore.assert_called_once()       # çalışan worker BEKLENDİ
        while self.svc._worker and self.svc._worker.isRunning():
            QCoreApplication.processEvents()
        _olay_isle(300)

    def test_long_worker_then_closing_backup_completes_before_accept(self):
        p = self._pencere()
        p._await_running_workers = mock.Mock(side_effect=[False, True, True])
        olay1 = mock.Mock()
        olay2 = mock.Mock()
        with mock.patch.object(self.svc, "trigger_now",
                               side_effect=[False, True]) as tetik:
            MainWindow.closeEvent(p, olay1)
            MainWindow.closeEvent(p, olay2)

        self.assertEqual(tetik.call_count, 2)
        tetik.assert_has_calls([mock.call(reason="kapanma")] * 2)
        olay1.ignore.assert_called_once()
        olay1.accept.assert_not_called()
        olay2.accept.assert_called_once()
        self.assertFalse(getattr(p, "_shutdown_backup_pending", False))


# ── İzole alt süreç: gerçek Windows çıkış kodu ──────────────────────────────

COCUK = r'''
import os, sys, time, json
sys.path.insert(0, os.environ["O12_PROJE"])
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from unittest import mock
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QCoreApplication, QDeadlineTimer, QEvent
app = QApplication([])

import ui.dialogs.backup_manager as bm
from core import restart
from ui.main_window import MainWindow

SURE = float(os.environ["O12_SURE"])
YOL = os.environ["O12_YOL"]
sira = []

def yedek(d):
    time.sleep(SURE)
    sira.append("yedek_bitti")
    return d + "/sahte.zip"

bm.create_backup = yedek
bm._save_meta = lambda m: None
bm.AutoBackupService._cleanup = lambda s, d, keep=20: None

svc = bm.AutoBackupService()
svc._meta = {"auto_enabled": False, "auto_backup_dir": os.environ["O12_YEDEK"],
             "auto_interval": 30}
svc._timer.stop()
svc._run("arka-plan")

p = MainWindow.__new__(MainWindow)
p._shutdown_prepared = False
p._close_deferred = False
p._close_connected_workers = []
p.pages = {}
p._backup_svc = svc
p._SHUTDOWN_WAIT_MS = 300
p.hide = lambda: None
_kapali = {"n": 0}
def _close():
    _kapali["n"] += 1
    olay = mock.Mock()
    MainWindow.closeEvent(p, olay)
    if olay.accept.called:
        sira.append("kapanis_kabul")
p.close = _close

if YOL == "restart":
    restart.request_restart()

olay = mock.Mock()
MainWindow.closeEvent(p, olay)
if olay.accept.called:
    sira.append("kapanis_kabul")

# main() kuyruğu: olay döngüsü -> DB kapat -> ardıl başlat
son = QDeadlineTimer(15000)
while not son.hasExpired() and not any(s == "kapanis_kabul" for s in sira):
    QCoreApplication.processEvents()
QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
sira.append("db_kapatildi")
if restart.restart_requested():
    sira.append("ardil_baslatildi")

open(os.environ["O12_SONUC"], "w", encoding="utf-8").write(json.dumps({
    "sira": sira,
    "ilk_ignore": olay.ignore.called,
    "worker_calisiyor": bool(svc.active_worker()),
}, ensure_ascii=False))
sys.exit(0)
'''


class ExitCodeTests(unittest.TestCase):
    """Gerçek süreç çıkış kodu: 0xC0000409 olmamalı."""

    def _calistir(self, yol, sure):
        with tempfile.TemporaryDirectory(prefix="o12x_",
                                         ignore_cleanup_errors=True) as tmp:
            kok = Path(tmp)
            (kok / "yedek").mkdir()
            betik = kok / "c.py"
            betik.write_text(COCUK, encoding="utf-8")
            sonuc = kok / "sonuc.json"
            veri = kok / "veri"
            env = dict(os.environ, O12_PROJE=str(PROJE_KOKU),
                       O12_YEDEK=str(kok / "yedek"), O12_YOL=yol,
                       O12_SURE=str(sure), O12_SONUC=str(sonuc),
                       PYTHONIOENCODING="utf-8",
                       LOCALAPPDATA=str(veri), USERPROFILE=str(veri),
                       HOME=str(veri), TMP=str(veri), TEMP=str(veri))
            p = subprocess.run([sys.executable, str(betik)], env=env,
                               capture_output=True, text=True,
                               encoding="utf-8", timeout=180)
            veri_json = (json.loads(sonuc.read_text(encoding="utf-8"))
                         if sonuc.exists() else {})
            return p.returncode, veri_json, p.stderr

    def test_restart_close_with_short_backup_exits_cleanly(self):
        kod, d, hata = self._calistir("restart", 1.0)
        self.assertNotEqual(kod, 3221226505, f"0xC0000409 fast-fail: {hata}")
        self.assertEqual(kod, 0, hata)
        self.assertIn("yedek_bitti", d.get("sira", []))
        sira = d["sira"]
        self.assertLess(sira.index("yedek_bitti"), sira.index("db_kapatildi"),
                        "DB, yedek bitmeden kapatıldı")
        self.assertLess(sira.index("db_kapatildi"),
                        sira.index("ardil_baslatildi"),
                        "ardıl DB kapanmadan başlatıldı")

    def test_restart_close_with_long_backup_defers_and_exits_cleanly(self):
        kod, d, hata = self._calistir("restart", 2.0)
        self.assertNotEqual(kod, 3221226505, f"0xC0000409 fast-fail: {hata}")
        self.assertEqual(kod, 0, hata)
        self.assertTrue(d.get("ilk_ignore"),
                        "uzun yedekte kapanış ertelenmedi")
        self.assertIn("yedek_bitti", d.get("sira", []))

    def test_normal_close_still_exits_cleanly(self):
        kod, d, hata = self._calistir("normal", 1.0)
        self.assertEqual(kod, 0, hata)


if __name__ == "__main__":
    unittest.main()
