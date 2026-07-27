"""O5 — geri yükleme sonrası yeniden başlatma akışı.

O5'in ÖZGÜN yarış iddiası (yeniden başlatma ↔ tek örnek kilidinin bırakılması)
ölçümle YANLIŞ POZİTİF olarak kapatıldı: eski süreç, ardıl kilit kontrolüne
ulaşmadan ~50 ms önce ölüyordu (24/24 tur). Bu dosya, aynı akışta DOĞRULANAN
kesin kusurları sabitler:

  * frozen'da `[sys.executable] + sys.argv` EXE yolunu İKİ KEZ veriyordu,
  * iki farklı yeniden başlatma mekanizması (os.execl / Popen) vardı,
  * `os.execl` Qt kapanışını, worker beklemesini (K6) ve DB kapanışını
    tamamen atlıyordu,
  * yeniden başlatma başarısız olsa bile kullanıcıya hiçbir şey
    gösterilmiyor, uygulama sessizce `sys.exit(0)` yapıyordu.

Kilit davranışını ölçen testler İZOLE ALT SÜREÇTE, gerçek uygulamanınkinden
FARKLI bir mutex adıyla ve geçici LOCALAPPDATA/USERPROFILE/HOME/TMP/TEMP ile
çalışır; gerçek DB, yedek, geri yükleme ve kullanıcı logları kullanılmaz.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from core import restart

PROJE_KOKU = Path(__file__).resolve().parent.parent


# ── 1, 2, 3, 14: saf komut üreticisi ────────────────────────────────────────

class RestartCommandTests(unittest.TestCase):
    """Komut üretimi YAN ETKİSİZ saf fonksiyondur — süreç başlatmaz."""

    PY = r"C:\Python\python.exe"
    EXE = r"C:\Program Files\Teklif\TeklifYonetim.exe"

    def test_source_mode_command(self):
        komut = restart.build_restart_command(
            self.PY, [r"C:\proj\main.py", "--foo"], frozen=False, parent_pid=42)
        self.assertEqual(
            komut, [self.PY, r"C:\proj\main.py", "--foo",
                    restart.RESTART_FLAG, "42"])

    def test_frozen_mode_uses_exe_path_once(self):
        # PyInstaller'da sys.argv[0] == sys.executable (minik test EXE'si ile
        # ölçüldü); bu yüzden argv[0] TEKRAR eklenmemeli.
        komut = restart.build_restart_command(
            self.EXE, [self.EXE, "--foo"], frozen=True, parent_pid=7)
        self.assertEqual(komut,
                         [self.EXE, "--foo", restart.RESTART_FLAG, "7"])
        self.assertEqual(komut.count(self.EXE), 1,
                         f"EXE yolu birden fazla kez geçti: {komut}")
        # Eski formül ([sys.executable] + sys.argv) frozen'da EXE yolunu İKİ
        # KEZ veriyordu; kusurun geri gelmemesi için karşıtı da sabitlenir.
        eski = [self.EXE] + [self.EXE, "--foo"]
        self.assertEqual(eski.count(self.EXE), 2,
                         "eski kusurun tarifi değişti — testi güncelle")

    def test_frozen_command_without_extra_args(self):
        komut = restart.build_restart_command(
            self.EXE, [self.EXE], frozen=True, parent_pid=7)
        self.assertEqual(komut, [self.EXE, restart.RESTART_FLAG, "7"])

    def test_internal_flag_is_parsed_out_of_argv(self):
        temiz, pid = restart.parse_restart_flag(
            [r"C:\proj\main.py", "--foo", restart.RESTART_FLAG, "999", "--bar"])
        self.assertEqual(temiz, [r"C:\proj\main.py", "--foo", "--bar"])
        self.assertEqual(pid, 999)

    def test_missing_flag_gives_none_pid(self):
        temiz, pid = restart.parse_restart_flag([r"C:\proj\main.py", "--foo"])
        self.assertEqual(temiz, [r"C:\proj\main.py", "--foo"])
        self.assertIsNone(pid)

    def test_flag_does_not_accumulate_across_restarts(self):
        """14 — art arda yeniden başlatmalarda argümanlar birikmemeli."""
        for frozen, argv0 in ((False, r"C:\proj\main.py"), (True, self.EXE)):
            calisan = [argv0, "--foo"]
            calistirici = self.PY if not frozen else self.EXE
            for tur in range(4):
                komut = restart.build_restart_command(
                    calistirici, calisan, frozen=frozen, parent_pid=tur)
                self.assertEqual(
                    komut.count(restart.RESTART_FLAG), 1,
                    f"frozen={frozen} tur={tur} işaret birikti: {komut}")
                self.assertEqual(
                    komut.count("--foo"), 1,
                    f"frozen={frozen} tur={tur} argüman birikti: {komut}")
                if frozen:
                    self.assertEqual(komut.count(self.EXE), 1, komut)
                # Ardıl sürecin göreceği sys.argv: frozen'da komutun tamamı
                # (argv[0] = EXE), kaynakta yorumlayıcı sonrası kısım.
                calisan, _ = restart.parse_restart_flag(
                    komut if frozen else komut[1:])


# ── 9: os.execl hiçbir çağrı yolunda kullanılmıyor ──────────────────────────

class NoExeclTests(unittest.TestCase):

    def test_no_execl_call_in_source(self):
        import re
        desen = re.compile(r"^[^#]*\bos\.execl\w*\s*\(", re.MULTILINE)
        suclu = []
        for py in PROJE_KOKU.rglob("*.py"):
            if "tests" in py.parts or ".venv" in py.parts:
                continue
            if desen.search(py.read_text(encoding="utf-8", errors="replace")):
                suclu.append(str(py.relative_to(PROJE_KOKU)))
        self.assertEqual(suclu, [], f"os.execl hâlâ çağrılıyor: {suclu}")


# ── 7, 8: spawn hatası → kullanıcı mesajı + log + kontrollü kapanış ────────

class SpawnFailureTests(unittest.TestCase):
    """`main` içe aktarılmadan, davranış doğrudan modül üzerinde sınanır."""

    def setUp(self):
        restart.reset_restart_request()
        self.addCleanup(restart.reset_restart_request)

    def test_spawn_failure_is_logged_and_returns_false(self):
        with mock.patch("core.restart.subprocess.Popen",
                        side_effect=OSError("spawn yok")):
            with self.assertLogs("restart", level="ERROR") as kayit:
                sonuc = restart.spawn_successor(1234)
        self.assertFalse(sonuc)
        birlesik = "\n".join(kayit.output)
        self.assertIn("Ardıl süreç başlatılamadı", birlesik)
        self.assertIn("Traceback", birlesik, "teknik ayrıntı loga yazılmadı")

    def test_spawn_success_returns_true(self):
        with mock.patch("core.restart.subprocess.Popen") as po:
            self.assertTrue(restart.spawn_successor(1234))
        self.assertEqual(po.call_count, 1)

    def test_request_is_only_a_flag(self):
        """İstek kaydı hiçbir süreç başlatmaz (kapanış yolu işletilmeli)."""
        with mock.patch("core.restart.subprocess.Popen") as po:
            restart.request_restart()
        self.assertTrue(restart.restart_requested())
        po.assert_not_called()


# ── İzole alt süreç deneyleri (4, 5, 6, 8, 10, 11, 12, 13) ─────────────────

COCUK = r'''
import os, sys, json, time, tempfile
SONUC = sys.argv[1]
SENARYO = sys.argv[2]
_tmp = sys.argv[3]
os.makedirs(_tmp, exist_ok=True)
for _ad in ("LOCALAPPDATA", "USERPROFILE", "HOME", "TMP", "TEMP"):
    os.environ[_ad] = _tmp
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, os.environ["O5_PROJE"])

b = {}
import main
from core import restart

# Gercek pencere ACILMASIN
from PySide6.QtWidgets import QMessageBox
import ctypes
bildirimler = []
QMessageBox.critical = staticmethod(
    lambda p, bas, met, *a, **k: bildirimler.append(("qt", bas, met)))
if sys.platform == "win32":
    ctypes.windll.user32.MessageBoxW = (
        lambda h, met, bas, bayrak: bildirimler.append(("win", bas, met)) or 1)

# Gercek tek ornek adini KULLANMA: main'in fonksiyonlarini deney adiyla sar.
DENEY_AD = sys.argv[4] if len(sys.argv) > 4 else "O5TEST"
_orj_try = main._try_acquire_single_instance
_tut = {"handle": None, "shm": None}

def _deney_try():
    from PySide6.QtCore import QSharedMemory
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.CreateMutexW.argtypes = (ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p)
    k.CreateMutexW.restype = ctypes.c_void_p
    h = k.CreateMutexW(None, False, DENEY_AD + "_AppMutex")
    if not h:
        return False
    if ctypes.get_last_error() == 183:
        k.CloseHandle(ctypes.c_void_p(h))
        return False
    _tut["handle"] = h
    shm = QSharedMemory(DENEY_AD + "_SingleInstance_Mutex")
    if shm.attach():
        return False
    if not shm.create(1):
        return False
    _tut["shm"] = shm
    return True

main._try_acquire_single_instance = _deney_try
main._bring_existing_window_forward = lambda: None

if SENARYO == "normal_hizli":
    # 4 — normal acilista kilit doluysa BEKLEMEDEN False donmeli
    tutan = _deney_try()                      # bu surec kilidi alir
    b["ilk_alindi"] = tutan
    t0 = time.monotonic()
    ikinci = main._ensure_single_instance()   # bekleme_s = 0 (varsayilan)
    b["ikinci_alindi"] = ikinci
    b["gecen_ms"] = (time.monotonic() - t0) * 1000

elif SENARYO == "bekleyip_acilir":
    # 5 — kilit KISA sure tutulup birakilirsa ardil bekleyip acilmali
    import threading
    serbest = threading.Event()
    def birak_sonra():
        time.sleep(1.0)
        _tut["handle"] = None
        _tut["shm"] = None
        serbest.set()
    # Kilidi baska bir "surec" gibi tutan sahte durum: sayaci kullan
    durum = {"dolu": True}
    def _sahte_try():
        if durum["dolu"]:
            return False
        return True
    main._try_acquire_single_instance = _sahte_try
    threading.Timer(1.0, lambda: durum.update(dolu=False)).start()
    t0 = time.monotonic()
    b["alindi"] = main._ensure_single_instance(bekleme_s=restart.LOCK_WAIT_S)
    b["bekleme_ms"] = (time.monotonic() - t0) * 1000

elif SENARYO == "sure_dolar":
    # 6 — sure dolarsa SESSIZ cikis YOK: bildirim + log
    main._try_acquire_single_instance = lambda: False
    t0 = time.monotonic()
    alindi = main._ensure_single_instance(bekleme_s=0.5)
    b["alindi"] = alindi
    b["bekleme_ms"] = (time.monotonic() - t0) * 1000
    b["bildirim_gonderildi"] = main._kullaniciya_bildir(
        main._KILIT_ALINAMADI.format(log=main.log_filename))
    b["bildirimler"] = bildirimler[:]
    b["mesaj_log_yolu_iceriyor"] = any(
        str(main.log_filename) in m for _t, _b, m in bildirimler)
    b["mesaj_traceback_icermiyor"] = all(
        "Traceback" not in m for _t, _b, m in bildirimler)

elif SENARYO == "spawn_hatasi_bildirim":
    # 7 — spawn hatasinda kullanici mesaji + log
    import unittest.mock as mk
    with mk.patch("core.restart.subprocess.Popen", side_effect=OSError("yok")):
        kod = main._yeniden_baslat()
    b["cikis_kodu"] = kod
    b["beklenen_kod"] = restart.EXIT_SPAWN_FAILED
    b["bildirimler"] = bildirimler[:]
    b["mesaj_elle_ac_diyor"] = any("elle yeniden açın" in m
                                   for _t, _b, m in bildirimler)
    b["mesaj_log_yolu_iceriyor"] = any(str(main.log_filename) in m
                                       for _t, _b, m in bildirimler)
    b["mesaj_traceback_icermiyor"] = all("Traceback" not in m
                                         for _t, _b, m in bildirimler)
    log = __import__("pathlib").Path(main.log_filename)
    icerik = log.read_text(encoding="utf-8", errors="replace") if log.exists() else ""
    b["log_traceback_var"] = "Traceback" in icerik

elif SENARYO == "kismi_edinim":
    # Windows mutex ALINIR ama paylasimli bellek ALINAMAZ.
    main._try_acquire_single_instance = _orj_try          # gercek fonksiyon
    durum = {"shm_dolu": True, "kapatilan": [], "detach": 0,
             "olusturulan_handle": []}

    class SahteSHM:
        def __init__(self, ad):
            self.ad = ad
            self._attached = False
        def attach(self):
            if durum["shm_dolu"]:
                self._attached = True
                return True
            return False
        def isAttached(self):
            return self._attached
        def detach(self):
            durum["detach"] += 1
            self._attached = False
            return True
        def create(self, n):
            return not durum["shm_dolu"]
        def errorString(self):
            return "sahte"

    main.QSharedMemory = SahteSHM

    # GERCEKCI named-mutex taklidi: ayni ad icin ACIK handle varsa
    # CreateMutexW yine bir handle dondurur ama ERROR_ALREADY_EXISTS kurar.
    # Boylece "kendi acik handle'imiza takilma" belirtisi gercekten olusur.
    kayit = {"acik": {}, "son_hata": 0}

    class SahteK32:
        def __init__(self):
            def _create(a, b, ad):
                h = 1000 + len(durum["olusturulan_handle"])
                durum["olusturulan_handle"].append(h)
                kayit["son_hata"] = 183 if kayit["acik"].get(ad) else 0
                kayit["acik"][ad] = kayit["acik"].get(ad, 0) + 1
                durum["son_ad"] = ad
                return h
            def _close(h):
                durum["kapatilan"].append(getattr(h, "value", h))
                ad = durum.get("son_ad")
                if ad and kayit["acik"].get(ad):
                    kayit["acik"][ad] -= 1
                return 1
            self.CreateMutexW = _create
            self.CloseHandle = _close

    sahte_hata = {"kod": None}      # None = gercekci taklit, sayi = zorla
    ctypes.WinDLL = lambda *a, **k: SahteK32()
    ctypes.get_last_error = lambda: (kayit["son_hata"]
                                     if sahte_hata["kod"] is None
                                     else sahte_hata["kod"])

    main._win_mutex_handle = None
    main._shared_memory = None

    # 1-3: mutex alinir, SHM alinamaz -> False + handle KAPATILMIS
    b["ilk_sonuc"] = main._try_acquire_single_instance()
    b["ilk_kapatilan"] = list(durum["kapatilan"])
    b["ilk_detach"] = durum["detach"]
    b["global_handle_bos"] = main._win_mutex_handle is None
    b["global_shm_bos"] = main._shared_memory is None

    # 4: SHM serbest kalinca sonraki deneme BASARILI olmali
    durum["shm_dolu"] = False
    b["ikinci_sonuc"] = main._try_acquire_single_instance()
    # 5: basarida global referanslar korunur
    b["global_handle_dolu"] = main._win_mutex_handle is not None
    b["global_shm_dolu"] = main._shared_memory is not None
    b["toplam_kapatilan"] = list(durum["kapatilan"])

    # 6: mutex BASKA surece aitse globaldeki kendi handle'imiza dokunulmaz
    onceki = main._win_mutex_handle
    onceki_shm = main._shared_memory
    sahte_hata["kod"] = 183
    b["ucuncu_sonuc"] = main._try_acquire_single_instance()
    b["global_handle_korundu"] = main._win_mutex_handle is onceki
    b["global_shm_korundu"] = main._shared_memory is onceki_shm

    # 8: temizlik hata verse bile istisna sizmamali
    sahte_hata["kod"] = 0
    kayit["acik"].clear()
    durum["shm_dolu"] = True
    class PatlayanSHM(SahteSHM):
        def isAttached(self):
            raise RuntimeError("isAttached patladi")
    main.QSharedMemory = PatlayanSHM
    class PatlayanK32(SahteK32):
        def __init__(self):
            super().__init__()
            def _close(h):
                raise OSError("CloseHandle patladi")
            self.CloseHandle = _close
    ctypes.WinDLL = lambda *a, **k: PatlayanK32()
    try:
        b["temizlik_hatasinda_sonuc"] = main._try_acquire_single_instance()
        b["temizlik_hatasi_sizdi"] = False
    except BaseException as e:
        b["temizlik_hatasi_sizdi"] = True
        b["temizlik_istisnasi"] = f"{type(e).__name__}: {e}"

elif SENARYO == "main_timeout":
    # GERCEK main() ardil-timeout dali
    main._try_acquire_single_instance = lambda: False
    restart.LOCK_WAIT_S = 0.4
    sys.argv = ["main.py", restart.RESTART_FLAG, "4242"]
    try:
        main.main()
        b["sistem_exit"] = None
    except SystemExit as e:
        b["sistem_exit"] = e.code
    b["beklenen"] = restart.EXIT_LOCK_TIMEOUT
    b["bildirimler"] = bildirimler[:]
    b["bildirim_var"] = bool(bildirimler)
    log = __import__("pathlib").Path(main.log_filename)
    icerik = log.read_text(encoding="utf-8", errors="replace") if log.exists() else ""
    b["log_kilit_hatasi"] = "tek örnek kilidini" in icerik

elif SENARYO == "main_restore_spawn_hatasi":
    # GERCEK main(): restore yolu + spawn hatasi -> EXIT_SPAWN_FAILED
    import unittest.mock as mk
    main._try_acquire_single_instance = lambda: True
    main._check_data_on_startup = lambda app: True
    sys.argv = ["main.py"]
    with mk.patch("core.restart.subprocess.Popen", side_effect=OSError("yok")):
        try:
            main.main()
            b["sistem_exit"] = None
        except SystemExit as e:
            b["sistem_exit"] = e.code
    b["beklenen"] = restart.EXIT_SPAWN_FAILED
    b["sifir_donmedi"] = b["sistem_exit"] not in (0, None)
    b["bildirim_var"] = bool(bildirimler)
    b["mesaj_elle_ac_diyor"] = any("elle yeniden açın" in m
                                   for _t, _b, m in bildirimler)

elif SENARYO == "bozuk_pid":
    # Malformed PID: isaret TEMIZLENIR, pid None -> normal acilis davranisi
    ham = ["main.py", "--foo", restart.RESTART_FLAG, "abc", "--bar"]
    temiz, pid = restart.parse_restart_flag(ham)
    b["temiz"] = temiz
    b["pid"] = pid
    b["isaret_kaldi"] = restart.RESTART_FLAG in temiz
    b["bozuk_deger_kaldi"] = "abc" in temiz
    # Art arda: isaret birikmemeli
    komut = restart.build_restart_command("py.exe", ham, frozen=False,
                                          parent_pid=7)
    b["komut_isaret_sayisi"] = komut.count(restart.RESTART_FLAG)
    b["komut_bozuk_deger"] = "abc" in komut
    # Normal acilis dali: pid None oldugu icin bekleme YOK
    main._try_acquire_single_instance = lambda: False
    sys.argv = list(ham)
    t0 = time.time()
    try:
        main.main()
        b["sistem_exit"] = None
    except SystemExit as e:
        b["sistem_exit"] = e.code
    b["gecen_ms"] = (time.time() - t0) * 1000

elif SENARYO == "db_kapaniyor":
    # 11 — restart kapanisinda DB baglantisi kapaniyor
    import database.db_manager as dbm
    dbm.get_db()
    b["once_acik"] = dbm._instance is not None
    main._veritabanini_kapat()
    b["sonra_kapali"] = dbm._instance is None

json.dump(b, open(SONUC, "w", encoding="utf-8"), ensure_ascii=False, default=str)
'''


def _alt_surec(senaryo: str, ad: str = "O5TEST") -> dict:
    with tempfile.TemporaryDirectory(prefix="o5_test_",
                                     ignore_cleanup_errors=True) as tmp:
        betik = Path(tmp) / "cocuk.py"
        betik.write_text(COCUK, encoding="utf-8")
        sonuc = Path(tmp) / "sonuc.json"
        veri = Path(tmp) / "veri"
        env = dict(os.environ, O5_PROJE=str(PROJE_KOKU),
                   PYTHONIOENCODING="utf-8",
                   LOCALAPPDATA=str(veri), USERPROFILE=str(veri),
                   HOME=str(veri), TMP=str(veri), TEMP=str(veri))
        p = subprocess.run(
            [sys.executable, str(betik), str(sonuc), senaryo, str(veri), ad],
            capture_output=True, text=True, encoding="utf-8",
            timeout=180, cwd=str(PROJE_KOKU), env=env)
        if not sonuc.exists():
            raise AssertionError(
                f"alt süreç sonucu yok (senaryo={senaryo}, kod={p.returncode})\n"
                f"--- stdout ---\n{p.stdout}\n--- stderr ---\n{p.stderr}")
        return json.loads(sonuc.read_text(encoding="utf-8"))


class SingleInstanceWaitTests(unittest.TestCase):

    # 4
    def test_normal_startup_keeps_fast_single_instance(self):
        r = _alt_surec("normal_hizli", "O5NORMAL")
        self.assertTrue(r["ilk_alindi"])
        self.assertFalse(r["ikinci_alindi"])
        self.assertLess(r["gecen_ms"], 250,
                        "normal açılışa gereksiz bekleme eklendi")

    # 5
    def test_successor_waits_and_opens_when_lock_released(self):
        r = _alt_surec("bekleyip_acilir", "O5BEKLE")
        self.assertTrue(r["alindi"], "kilit bırakıldığı hâlde açılmadı")
        self.assertGreater(r["bekleme_ms"], 800, "hiç beklemedi")
        self.assertLess(r["bekleme_ms"], restart.LOCK_WAIT_S * 1000 + 500)

    # 6
    def test_timeout_notifies_instead_of_silent_exit(self):
        r = _alt_surec("sure_dolar", "O5SURE")
        self.assertFalse(r["alindi"])
        self.assertGreater(r["bekleme_ms"], 400)
        self.assertTrue(r["bildirim_gonderildi"], "sessizce kapanıyor")
        self.assertTrue(r["bildirimler"], "hiçbir bildirim üretilmedi")
        self.assertTrue(r["mesaj_log_yolu_iceriyor"])
        self.assertTrue(r["mesaj_traceback_icermiyor"])

    def test_timeout_exit_code_is_distinct(self):
        self.assertNotEqual(restart.EXIT_LOCK_TIMEOUT, 0)
        self.assertNotEqual(restart.EXIT_LOCK_TIMEOUT,
                            restart.EXIT_SPAWN_FAILED)


class SpawnFailureUserMessageTests(unittest.TestCase):

    # 7, 8
    def test_spawn_failure_shows_message_and_nonzero_exit(self):
        r = _alt_surec("spawn_hatasi_bildirim", "O5SPAWN")
        self.assertEqual(r["cikis_kodu"], r["beklenen_kod"])
        self.assertNotEqual(r["cikis_kodu"], 0,
                            "spawn hatası başarı gibi raporlandı")
        self.assertTrue(r["mesaj_elle_ac_diyor"])
        self.assertTrue(r["mesaj_log_yolu_iceriyor"])
        self.assertTrue(r["mesaj_traceback_icermiyor"],
                        "teknik ayrıntı kullanıcı mesajına sızdı")
        self.assertTrue(r["log_traceback_var"],
                        "teknik ayrıntı log dosyasına yazılmadı")


class RestartShutdownTests(unittest.TestCase):

    # 11
    def test_database_is_closed_on_restart_shutdown(self):
        r = _alt_surec("db_kapaniyor", "O5DB")
        self.assertTrue(r["once_acik"])
        self.assertTrue(r["sonra_kapali"], "restart kapanışında DB kapanmadı")


class PartialAcquisitionTests(unittest.TestCase):
    """Mutex alınıp paylaşımlı bellek alınamazsa handle SIZMAMALI."""

    @classmethod
    def setUpClass(cls):
        cls.r = _alt_surec("kismi_edinim", "O5KISMI")

    def test_partial_acquisition_returns_false(self):
        self.assertFalse(self.r["ilk_sonuc"])

    def test_partial_acquisition_closes_its_own_handle(self):
        self.assertEqual(len(self.r["ilk_kapatilan"]), 1,
                         "başarısız denemede handle kapatılmadı (sızıntı)")

    def test_partial_acquisition_detaches_shared_memory(self):
        self.assertEqual(self.r["ilk_detach"], 1,
                         "yarım edinilmiş paylaşımlı bellek bırakılmadı")

    def test_globals_stay_clean_after_failure(self):
        self.assertTrue(self.r["global_handle_bos"],
                        "başarısız denemede global handle kirletildi")
        self.assertTrue(self.r["global_shm_bos"])

    def test_next_attempt_succeeds_when_shm_is_free(self):
        self.assertTrue(self.r["ikinci_sonuc"],
                        "kilit serbest kaldığı hâlde ikinci deneme başarısız "
                        "(kendi handle'ımıza takıldık)")

    def test_success_keeps_strong_global_references(self):
        self.assertTrue(self.r["global_handle_dolu"])
        self.assertTrue(self.r["global_shm_dolu"])
        self.assertEqual(len(self.r["toplam_kapatilan"]), 1,
                         "başarılı edinimde handle kapatıldı")

    def test_other_process_mutex_does_not_touch_our_globals(self):
        self.assertFalse(self.r["ucuncu_sonuc"])
        self.assertTrue(self.r["global_handle_korundu"],
                        "başka sürecin mutex'i bizim handle'ımızı sildi")
        self.assertTrue(self.r["global_shm_korundu"])

    def test_cleanup_failure_does_not_escape(self):
        self.assertFalse(self.r["temizlik_hatasi_sizdi"],
                         self.r.get("temizlik_istisnasi", ""))
        self.assertFalse(self.r["temizlik_hatasinda_sonuc"])


class MainEntryPointTests(unittest.TestCase):
    """Yardımcıları tek tek değil, GERÇEK main() dallarını doğrular."""

    def test_successor_timeout_exits_with_lock_timeout_code(self):
        r = _alt_surec("main_timeout", "O5MAINTO")
        self.assertEqual(r["sistem_exit"], r["beklenen"])
        self.assertTrue(r["bildirim_var"], "kullanıcıya bildirim üretilmedi")
        self.assertTrue(r["log_kilit_hatasi"], "kilit hatası loglanmadı")

    def test_restore_spawn_failure_exits_with_spawn_failed_code(self):
        r = _alt_surec("main_restore_spawn_hatasi", "O5MAINSP")
        self.assertEqual(r["sistem_exit"], r["beklenen"])
        self.assertTrue(r["sifir_donmedi"],
                        "spawn hatası başarı gibi 0 döndürdü")
        self.assertTrue(r["bildirim_var"])
        self.assertTrue(r["mesaj_elle_ac_diyor"])

    def test_malformed_pid_falls_back_to_normal_startup(self):
        r = _alt_surec("bozuk_pid", "O5BOZUK")
        self.assertEqual(r["temiz"], ["main.py", "--foo", "--bar"])
        self.assertIsNone(r["pid"])
        self.assertFalse(r["isaret_kaldi"])
        self.assertFalse(r["bozuk_deger_kaldi"],
                         "bozuk pid değeri argümanlarda kaldı")
        self.assertEqual(r["komut_isaret_sayisi"], 1, "işaret birikti")
        self.assertFalse(r["komut_bozuk_deger"])
        # pid None → normal açılış: kilit doluysa BEKLEMEDEN 0 ile çık
        self.assertEqual(r["sistem_exit"], 0)
        self.assertLess(r["gecen_ms"], 1000, "normal açılışa bekleme eklendi")


# ── 3 (UI tarafı), 10, 12, 13: kapanış davranışı ───────────────────────────

class CloseBackupDecisionTests(unittest.TestCase):
    """12/13 — kapanış yedeği kararı.

    Normal kullanıcı kapanışında yedek ALINIR (davranış değişmedi).
    Yeniden başlatma kapanışında ATLANIR: yeni geri yüklenen veriden hemen
    yeni bir yedek üretmek 20 yedeklik saklama penceresinden (AutoBackupService
    ._cleanup keep=20) EN ESKİ yedeği düşürür — kullanıcı tam da geri yüklemek
    istediği yedeği kaybedebilir.
    """

    def setUp(self):
        restart.reset_restart_request()
        self.addCleanup(restart.reset_restart_request)

    def _sahte_pencere(self):
        from ui.main_window import MainWindow
        pencere = MainWindow.__new__(MainWindow)      # __init__ çalıştırmadan
        pencere._shutdown_prepared = False
        pencere._close_deferred = False
        pencere._close_connected_workers = []
        pencere.pages = {}
        pencere._backup_svc = mock.Mock()
        pencere._shutdown_workers = lambda: []
        # __init__ çalıştırılmadığı için C++ tarafı yok; kapanış ertelenirse
        # çağrılan Qt metotlarını zararsız yerine koy.
        pencere.hide = lambda: None
        pencere.close = lambda: None
        return pencere

    def _kapat(self):
        from ui.main_window import MainWindow
        pencere = self._sahte_pencere()
        olay = mock.Mock()
        MainWindow.closeEvent(pencere, olay)
        return pencere, olay

    def test_normal_close_still_takes_backup(self):
        pencere, olay = self._kapat()
        pencere._backup_svc.trigger_now.assert_called_once_with(reason="kapanma")
        olay.accept.assert_called_once()

    def test_restart_close_skips_backup(self):
        restart.request_restart()
        pencere, olay = self._kapat()
        pencere._backup_svc.trigger_now.assert_not_called()
        olay.accept.assert_called_once()

    # 10
    def test_worker_wait_is_preserved_on_restart_close(self):
        """K6 davranışı: çalışan worker varsa kapanış ERTELENİR."""
        from ui.main_window import MainWindow
        restart.request_restart()
        pencere = self._sahte_pencere()
        worker = mock.Mock()
        worker.isRunning.return_value = True
        pencere._shutdown_workers = lambda: [worker]
        pencere._SHUTDOWN_WAIT_MS = 10
        olay = mock.Mock()
        MainWindow.closeEvent(pencere, olay)
        olay.ignore.assert_called_once()
        olay.accept.assert_not_called()
        worker.wait.assert_called()
        worker.finished.connect.assert_called_once_with(pencere.close)


class RestartAppUsesCommonPathTests(unittest.TestCase):
    """2/3 — BackupDialog artık süreç başlatmıyor, ortak yolu kullanıyor."""

    def setUp(self):
        restart.reset_restart_request()
        self.addCleanup(restart.reset_restart_request)

    def test_restart_app_only_requests_and_closes_windows(self):
        from ui.dialogs.backup_manager import BackupDialog
        dlg = BackupDialog.__new__(BackupDialog)
        dlg.accept = mock.Mock()
        with mock.patch("PySide6.QtWidgets.QApplication.closeAllWindows") as kapat, \
             mock.patch("subprocess.Popen") as po, \
             mock.patch("os.execl", create=True) as ex:
            BackupDialog._restart_app(dlg)
        self.assertTrue(restart.restart_requested())
        dlg.accept.assert_called_once()
        kapat.assert_called_once()
        po.assert_not_called()
        ex.assert_not_called()

    def test_successor_not_started_while_workers_still_running(self):
        """closeAllWindows sonrası kapanış ERTELENİRSE ardıl başlamamalı."""
        from ui.dialogs.backup_manager import BackupDialog
        from ui.main_window import MainWindow

        dlg = BackupDialog.__new__(BackupDialog)
        dlg.accept = mock.Mock()

        pencere = MainWindow.__new__(MainWindow)
        pencere._shutdown_prepared = False
        pencere._close_deferred = False
        pencere._close_connected_workers = []
        pencere.pages = {}
        pencere._backup_svc = mock.Mock()
        pencere._SHUTDOWN_WAIT_MS = 10
        pencere.hide = lambda: None
        pencere.close = lambda: None
        worker = mock.Mock()
        worker.isRunning.return_value = True
        pencere._shutdown_workers = lambda: [worker]

        with mock.patch("PySide6.QtWidgets.QApplication.closeAllWindows"), \
             mock.patch("core.restart.subprocess.Popen") as po:
            BackupDialog._restart_app(dlg)
            olay = mock.Mock()
            MainWindow.closeEvent(pencere, olay)

        # Kapanış ertelendi → main() henüz app.exec()'ten dönmedi → ardıl YOK
        olay.ignore.assert_called_once()
        olay.accept.assert_not_called()
        po.assert_not_called()
        self.assertTrue(restart.restart_requested(),
                        "istek kayboldu; iş bitince ardıl açılamaz")
        # Restart kapanışı olduğu için kapanma yedeği de alınmamalı
        pencere._backup_svc.trigger_now.assert_not_called()


if __name__ == "__main__":
    unittest.main()
