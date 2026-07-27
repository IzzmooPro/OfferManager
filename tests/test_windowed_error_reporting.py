"""O8 — windowed (console=False) EXE'de çalışma zamanı hatalarının bildirimi.

Bütün deneyler İZOLE ALT SÜREÇTE çalışır. Alt sürecin LOCALAPPDATA,
USERPROFILE, HOME, TMP ve TEMP değişkenleri proje importlarından ÖNCE geçici
bir dizine yönlendirilir; gerçek kullanıcı veri/log/yedek klasörüne
dokunulmaz. QMessageBox ve Windows MessageBoxW alt süreçte mocklanır —
gerçek hata penceresi açılmaz.

KAPSAM DIŞI: 0xC0000409 gibi native fast-fail çökmeleri (ör. çalışan bir
QThread yok edilirken) Python yorumlayıcısına hiç ulaşmaz; sys.excepthook
onları YAKALAYAMAZ. Bu testler yalnız Python düzeyindeki yakalanmamış
istisnaları kapsar.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROJE_KOKU = Path(__file__).resolve().parent.parent

# ── Alt süreçte çalışan deney betiği ────────────────────────────────────────
# Not: proje importlarından ÖNCE ortam değişkenleri yönlendirilir.
COCUK = r'''
import os, sys, json, io, tempfile, logging, traceback
from pathlib import Path

SONUC = Path(sys.argv[1])
MOD = sys.argv[2]                       # "windowed" | "console"
# Veri koku EBEVEYNIN gecici klasoru icindedir; temizligi ebeveyn yapar,
# boylece her test calistirmasinda %TEMP%'te artik klasor kalmaz.
_tmp = sys.argv[3]
os.makedirs(_tmp, exist_ok=True)
for _ad in ("LOCALAPPDATA", "USERPROFILE", "HOME", "TMP", "TEMP"):
    os.environ[_ad] = _tmp
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, os.environ["O8_PROJE"])

b = {}
_gercek_stderr = sys.stderr

if MOD == "windowed":
    # Paketlenmiş windowed EXE: uc standart akis da yok.
    sys.stdin = sys.stdout = sys.stderr = None

# input() ASLA cagrilmamali — cagrilirsa bu deney patlar.
import builtins
def _yasak_input(*a, **k):
    b["input_cagrildi"] = True
    raise AssertionError("input() cagrildi")
builtins.input = _yasak_input

import main                              # gercek loglama + gercek excepthook

b["mod"] = MOD
b["log_yolu"] = str(main.log_filename)

# ── 13/14: handler listesi ──────────────────────────────────────────────
kok = logging.getLogger()
b["file_handler_var"] = any(isinstance(h, logging.FileHandler)
                            for h in kok.handlers)
b["stream_handler_var"] = any(
    isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
    for h in kok.handlers)

# ── Gercek pencere ACILMASIN: her iki yolu da mockla ─────────────────────
from PySide6.QtWidgets import QMessageBox
import ctypes

cagrilar = {"qt": [], "win": [], "akis": []}
QMessageBox.critical = staticmethod(
    lambda parent, baslik, metin, *a, **k: cagrilar["qt"].append((baslik, metin)))
if sys.platform == "win32":
    ctypes.windll.user32.MessageBoxW = (
        lambda hwnd, metin, baslik, bayrak: cagrilar["win"].append((baslik, metin)) or 1)

_GERCEK_MONOTONIK = main._monotonik

def sifirla():
    main._hook_devrede = False
    main._son_bildirim = (None, 0.0)
    main._monotonik = _GERCEK_MONOTONIK
    cagrilar["qt"].clear(); cagrilar["win"].clear(); cagrilar["akis"].clear()

def tetikle(mesaj="O8-TETIK"):
    try:
        raise ValueError(mesaj)
    except ValueError:
        return sys.exc_info()

# ── 1/2/6: akislar None, QApplication yok ───────────────────────────────
sifirla()
_orj_qt, _orj_win = main._bildir_qt, main._bildir_windows
b["qapp_yok"] = repr(__import__("PySide6.QtWidgets", fromlist=["QApplication"])
                     .QApplication.instance())
try:
    main.exception_hook(*tetikle("GIZLI-DETAY-A"))
    b["hook_hata_verdi"] = False
except BaseException as e:
    b["hook_hata_verdi"] = True
    b["hook_istisna"] = f"{type(e).__name__}: {e}"

log = Path(main.log_filename)
icerik = log.read_text(encoding="utf-8", errors="replace") if log.exists() else ""
b["log_var"] = log.exists()
b["log_traceback_tam"] = ("Traceback" in icerik and "GIZLI-DETAY-A" in icerik
                          and "ValueError" in icerik)
b["log_utf8_turkce"] = "UYGULAMA HATASI" in icerik
b["windows_fallback_kullanildi"] = len(cagrilar["win"]) == 1
b["qt_kullanildi"] = len(cagrilar["qt"])

# ── 4/5: kullanici mesaji ───────────────────────────────────────────────
if cagrilar["win"]:
    _baslik, _metin = cagrilar["win"][0]
    b["mesaj"] = _metin
    b["mesaj_satir_sayisi"] = len(_metin.splitlines())
    b["mesaj_log_yolu_iceriyor"] = str(main.log_filename) in _metin
    b["mesaj_traceback_iceriyor"] = "Traceback" in _metin
    b["mesaj_istisna_metni_iceriyor"] = ("GIZLI-DETAY-A" in _metin
                                         or "ValueError" in _metin)

# ── 7: Qt patlarsa Windows fallback ─────────────────────────────────────
sifirla()
main._bildir_qt = lambda m: (_ for _ in ()).throw(RuntimeError("qt bozuk"))
main.exception_hook(*tetikle("B"))
b["qt_patlayinca_windows"] = len(cagrilar["win"]) == 1

# ── 8: Windows da patlarsa kullanilabilir akisa yaz ──────────────────────
sifirla()
main._bildir_windows = lambda m: (_ for _ in ()).throw(OSError("win bozuk"))
_sahte = io.StringIO()
sys.stderr = _sahte
main.exception_hook(*tetikle("C"))
sys.stderr = None if MOD == "windowed" else _gercek_stderr
b["akis_fallback_yazdi"] = "Beklenmeyen bir uygulama hatası" in _sahte.getvalue()
b["akis_fallback_traceback_icermiyor"] = "Traceback" not in _sahte.getvalue()

# ── 9: hicbir fallback yoksa sessizce bit ────────────────────────────────
sifirla()
if MOD == "windowed":
    sys.stderr = sys.stdout = None
else:
    sys.stderr = sys.stdout = None
try:
    main.exception_hook(*tetikle("D"))
    b["hicbir_fallback_yoksa_hata"] = False
except BaseException as e:
    b["hicbir_fallback_yoksa_hata"] = True
    b["hicbir_fallback_istisna"] = f"{type(e).__name__}: {e}"
sys.stdout = None if MOD == "windowed" else _gercek_stderr
sys.stderr = None if MOD == "windowed" else _gercek_stderr

# ── 10: hook icinde yeni istisna → ozyineleme yok ───────────────────────
main._bildir_windows = _orj_win
sifirla()
derinlik = {"n": 0, "maks": 0}
def _kendini_cagiran(mesaj):
    derinlik["n"] += 1
    derinlik["maks"] = max(derinlik["maks"], derinlik["n"])
    if derinlik["n"] < 20:
        main.exception_hook(*tetikle("ic-ice"))
    derinlik["n"] -= 1
    raise RuntimeError("bildirim patladi")
main._bildir_qt = _kendini_cagiran
try:
    main.exception_hook(*tetikle("E"))
    b["ozyineleme_hata_verdi"] = False
except BaseException as e:
    b["ozyineleme_hata_verdi"] = True
b["ozyineleme_maks_derinlik"] = derinlik["maks"]

# ── 11: AYNI hata icin tek pencere ──────────────────────────────────────
main._bildir_qt = _orj_qt
sifirla()
_ayni = tetikle("AYNI-HATA")
main.exception_hook(*_ayni)
main.exception_hook(*_ayni)
main.exception_hook(*_ayni)
b["ayni_hata_pencere_sayisi"] = len(cagrilar["win"])

# ── Bastirma PENCERESI: suresiz olmamali (sahte monotonik saat) ─────────
sifirla()
saat = {"t": 1000.0}
main._monotonik = lambda: saat["t"]
_ayni = tetikle("PENCERE-TESTI")
main.exception_hook(*_ayni)                     # 1. bildirim
b["pencere_t0"] = len(cagrilar["win"])
saat["t"] += 9.0                                # 9 sn sonra → hala bastirilir
main.exception_hook(*_ayni)
b["pencere_9sn"] = len(cagrilar["win"])
saat["t"] += 1.5                                # 10.5 sn → yeniden bildirilir
main.exception_hook(*_ayni)
b["pencere_10sn_sonra"] = len(cagrilar["win"])
main.exception_hook(*tetikle("FARKLI-HATA"))    # farkli imza → hemen
b["farkli_hata_hemen"] = len(cagrilar["win"])

# ── Bastirilan tekrarlarin HEPSI loglanmali ─────────────────────────────
sifirla()
saat["t"] = 5000.0
main._monotonik = lambda: saat["t"]
_ISARET = "BASTIRILAN-TEKRAR-XYZ"
_ayni = tetikle(_ISARET)
main.exception_hook(*_ayni)
main.exception_hook(*_ayni)
main.exception_hook(*_ayni)
_log2 = Path(main.log_filename).read_text(encoding="utf-8", errors="replace")
b["bastirilan_log_kaydi"] = _log2.count("ValueError: " + _ISARET)
b["bastirilan_pencere"] = len(cagrilar["win"])

# ── 8: bildirim BASARISIZ olursa son bildirim zamani guncellenmemeli ────
sifirla()
_orj_akis = main._bildir_akis
main._bildir_qt = lambda m: False
main._bildir_windows = lambda m: False
main._bildir_akis = lambda m: False
main.exception_hook(*tetikle("BASARISIZ-BILDIRIM"))
b["basarisiz_bildirim_zamani_bos"] = main._son_bildirim == (None, 0.0)
main._bildir_qt, main._bildir_windows = _orj_qt, _orj_win
main._bildir_akis = _orj_akis

# ── 16: _show_startup_error bozulmadi mi ────────────────────────────────
sifirla()
cagrilar["win"].clear()
main._show_startup_error("baslangic hatasi metni")
b["show_startup_error_messagebox"] = len(cagrilar["win"]) == 1

# ── 17: native cokmelerin kapsam disi oldugu belgeli mi ─────────────────
b["native_kapsam_disi_belgeli"] = "0xC0000409" in (main.exception_hook.__doc__ or "")

# ── 3: QApplication VARKEN QMessageBox bir kez ──────────────────────────
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
app = QApplication([])
sifirla()
main.exception_hook(*tetikle("F"))
b["qapp_varken_qt_sayisi"] = len(cagrilar["qt"])
b["qapp_varken_windows_sayisi"] = len(cagrilar["win"])
if cagrilar["qt"]:
    b["qt_mesaji_log_yolu_iceriyor"] = str(main.log_filename) in cagrilar["qt"][0][1]
    b["qt_mesaji_traceback_icermiyor"] = "Traceback" not in cagrilar["qt"][0][1]

# ── 15: Qt ana-thread slot istisnasi sys.excepthook'a ulasiyor mu ───────
sifirla()
ulasan = {"n": 0, "tip": None}
_hook_oncesi = sys.excepthook
def _izleyen(t, v, tb):
    ulasan["n"] += 1
    ulasan["tip"] = t.__name__
sys.excepthook = _izleyen
def _slot_patlat():
    raise RuntimeError("O8 slot hatasi")
QTimer.singleShot(0, _slot_patlat)
QTimer.singleShot(500, app.quit)
app.exec()
sys.excepthook = _hook_oncesi
b["slot_hook_cagrildi"] = ulasan["n"]
b["slot_hook_tipi"] = ulasan["tip"]

b.setdefault("input_cagrildi", False)
SONUC.write_text(json.dumps(b, ensure_ascii=False, indent=2), encoding="utf-8")
'''


def _deney_calistir(mod: str) -> dict:
    """Deney betiğini izole alt süreçte çalıştırıp sonuç sözlüğünü döndürür."""
    with tempfile.TemporaryDirectory(prefix="o8_test_",
                                     ignore_cleanup_errors=True) as tmp:
        betik = Path(tmp) / "o8_cocuk.py"
        betik.write_text(COCUK, encoding="utf-8")
        sonuc = Path(tmp) / "sonuc.json"
        veri_koku = Path(tmp) / "veri"
        # Alt sürecin TÜM kullanıcı dizinleri geçici köke bağlanır; gerçek
        # LOCALAPPDATA/Documents/HOME hiçbir aşamada kullanılmaz.
        env = dict(os.environ, O8_PROJE=str(PROJE_KOKU),
                   PYTHONIOENCODING="utf-8",
                   LOCALAPPDATA=str(veri_koku), USERPROFILE=str(veri_koku),
                   HOME=str(veri_koku), TMP=str(veri_koku), TEMP=str(veri_koku))
        p = subprocess.run(
            [sys.executable, str(betik), str(sonuc), mod, str(veri_koku)],
            capture_output=True, text=True, encoding="utf-8",
            timeout=180, cwd=str(PROJE_KOKU), env=env)
        if not sonuc.exists():
            raise AssertionError(
                f"deney sonucu olusmadi (mod={mod}, kod={p.returncode})\n"
                f"--- stdout ---\n{p.stdout}\n--- stderr ---\n{p.stderr}")
        veri = json.loads(sonuc.read_text(encoding="utf-8"))
        veri["_konsol_ciktisi"] = p.stdout or ""
        veri["_cikis_kodu"] = p.returncode
        return veri


_onbellek: dict = {}


def _sonuc(mod: str) -> dict:
    """Alt süreç mod başına BİR kez çalışır (test başına değil)."""
    if mod not in _onbellek:
        _onbellek[mod] = _deney_calistir(mod)
    return _onbellek[mod]


class WindowedHookTests(unittest.TestCase):
    """console=False EXE koşulları: stdin/stdout/stderr yok."""

    @classmethod
    def setUpClass(cls):
        cls.r = _sonuc("windowed")

    # 1
    def test_hook_returns_without_second_exception(self):
        self.assertFalse(self.r["hook_hata_verdi"],
                         self.r.get("hook_istisna", ""))

    # input() bir daha eklenemez
    def test_input_is_never_called(self):
        self.assertFalse(self.r["input_cagrildi"])

    # 2
    def test_full_traceback_written_to_utf8_file_log(self):
        self.assertTrue(self.r["log_var"])
        self.assertTrue(self.r["log_traceback_tam"])
        self.assertTrue(self.r["log_utf8_turkce"],
                        "Türkçe metin UTF-8 log dosyasına yazılamadı")

    # 13
    def test_no_stream_handler_when_streams_are_none(self):
        self.assertFalse(self.r["stream_handler_var"])

    # 14
    def test_file_handler_always_present(self):
        self.assertTrue(self.r["file_handler_var"])

    # 6
    def test_windows_messagebox_used_when_no_qapplication(self):
        self.assertEqual(self.r["qapp_yok"], "None")
        self.assertTrue(self.r["windows_fallback_kullanildi"])
        self.assertEqual(self.r["qt_kullanildi"], 0)

    # 4
    def test_user_message_is_short_and_has_log_path(self):
        self.assertLessEqual(self.r["mesaj_satir_sayisi"], 6)
        self.assertTrue(self.r["mesaj_log_yolu_iceriyor"])

    # 5
    def test_user_message_hides_technical_detail(self):
        self.assertFalse(self.r["mesaj_traceback_iceriyor"])
        self.assertFalse(self.r["mesaj_istisna_metni_iceriyor"],
                         f"mesaj: {self.r.get('mesaj')!r}")

    # 7
    def test_windows_fallback_when_qt_raises(self):
        self.assertTrue(self.r["qt_patlayinca_windows"])

    # 8
    def test_stream_fallback_when_windows_raises(self):
        self.assertTrue(self.r["akis_fallback_yazdi"])
        self.assertTrue(self.r["akis_fallback_traceback_icermiyor"])

    # 9
    def test_silent_when_no_fallback_available(self):
        self.assertFalse(self.r["hicbir_fallback_yoksa_hata"],
                         self.r.get("hicbir_fallback_istisna", ""))

    # 10
    def test_no_recursion_when_hook_itself_fails(self):
        self.assertFalse(self.r["ozyineleme_hata_verdi"])
        self.assertEqual(self.r["ozyineleme_maks_derinlik"], 1,
                         "hook kendi içinde tekrar bildirim yaptı")

    # 11
    def test_same_error_shows_single_window(self):
        self.assertEqual(self.r["ayni_hata_pencere_sayisi"], 1)

    # Bastırma penceresi — gerçek bekleme yok, monotonik saat mocklandı
    def test_same_error_still_suppressed_within_window(self):
        self.assertEqual(self.r["pencere_t0"], 1)
        self.assertEqual(self.r["pencere_9sn"], 1,
                         "9 sn içindeki tekrar ikinci pencere açtı")

    def test_same_error_notifies_again_after_window(self):
        self.assertEqual(self.r["pencere_10sn_sonra"], 2,
                         "10 sn sonra aynı hata SÜRESİZ bastırıldı")

    def test_different_error_notifies_immediately(self):
        self.assertEqual(self.r["farkli_hata_hemen"], 3)

    def test_suppressed_repeats_are_still_logged(self):
        self.assertEqual(self.r["bastirilan_pencere"], 1)
        self.assertEqual(self.r["bastirilan_log_kaydi"], 3,
                         "bastırılan tekrarlar loga yazılmadı")

    # 8
    def test_failed_notification_does_not_start_window(self):
        self.assertTrue(self.r["basarisiz_bildirim_zamani_bos"],
                        "bildirim başarısızken son bildirim zamanı güncellendi")

    # 3
    def test_qmessagebox_used_once_when_qapplication_exists(self):
        self.assertEqual(self.r["qapp_varken_qt_sayisi"], 1)
        self.assertEqual(self.r["qapp_varken_windows_sayisi"], 0)
        self.assertTrue(self.r["qt_mesaji_log_yolu_iceriyor"])
        self.assertTrue(self.r["qt_mesaji_traceback_icermiyor"])

    # 15
    def test_qt_main_thread_slot_exception_reaches_excepthook(self):
        self.assertEqual(self.r["slot_hook_cagrildi"], 1)
        self.assertEqual(self.r["slot_hook_tipi"], "RuntimeError")

    # 16
    def test_show_startup_error_still_uses_messagebox(self):
        self.assertTrue(self.r["show_startup_error_messagebox"])

    # 17
    def test_native_fastfail_documented_as_out_of_scope(self):
        self.assertTrue(self.r["native_kapsam_disi_belgeli"],
                        "0xC0000409'un kapsam dışı olduğu belgede yok")


class ConsoleModeTests(unittest.TestCase):
    """console=True geliştirme çalıştırması: stdout gerçek."""

    @classmethod
    def setUpClass(cls):
        cls.r = _sonuc("console")

    # 12
    def test_stream_handler_added_when_stdout_usable(self):
        self.assertTrue(self.r["stream_handler_var"])
        self.assertTrue(self.r["file_handler_var"])

    # 12
    def test_console_output_is_preserved(self):
        cikti = self.r["_konsol_ciktisi"]
        self.assertIn("UYGULAMA HATASI", cikti)
        self.assertIn("Traceback", cikti)

    # 12 — Enter beklemesi kalkmalı
    def test_console_run_does_not_wait_for_enter(self):
        self.assertFalse(self.r["input_cagrildi"])
        self.assertNotIn("Enter", self.r["_konsol_ciktisi"])

    def test_full_traceback_still_written_to_file_log(self):
        self.assertTrue(self.r["log_traceback_tam"])


if __name__ == "__main__":
    unittest.main()
