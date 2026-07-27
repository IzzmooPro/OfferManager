"""Uygulamayı yeniden başlatma — TEK ortak yol.

Neden ayrı bir modül:
  Eskiden iki farklı mekanizma vardı; `backup_manager` `os.execl` çağırıyor,
  `main._check_data_on_startup` ise `subprocess.Popen([sys.executable] +
  sys.argv)` kullanıyordu. İkisi de farklı davranıyordu:

  - `os.execl` Windows'ta süreci YERİNE GEÇİRMEZ (ölçüldü: ardıl YENİ bir PID
    alır, ebeveynin `wait()`'i ardıl çalışırken döner). Dahası `ExitProcess`
    ile ani çıkış yaptığı için Qt kapanışı, çalışan worker'ların beklenmesi
    (K6) ve `get_db().close()` TAMAMEN atlanıyordu.
  - `[sys.executable] + sys.argv` paketlenmiş (frozen) sürümde EXE yolunu İKİ
    KEZ veriyordu; çünkü PyInstaller'da `sys.argv[0] == sys.executable`
    (minik bir test EXE'si ile ölçüldü).

Buradaki akış:
  1. `request_restart()` yalnız İSTEĞİ kaydeder — süreç başlatmaz.
  2. Uygulama NORMAL kapanış yolunu işletir (MainWindow.closeEvent → worker
     bekleme → app.exec() döner → `get_db().close()`).
  3. En sonda `spawn_successor()` ardılı başlatır.

Ardıl süreç `--restarted-from <pid>` işaretiyle açılır. Bu işaret yalnız tek
örnek kilidinin KISA ve SINIRLI süre yeniden denenmesini sağlar; normal
kullanıcı açılışında hiçbir ek bekleme yoktur.
"""
import logging
import subprocess
import sys

logger = logging.getLogger("restart")

# Dahili işaret — kullanıcıya ait bir argüman değildir, QApplication'a
# aktarılmadan önce ayrıştırılıp çıkarılır.
RESTART_FLAG = "--restarted-from"

# Ardıl sürecin tek örnek kilidini beklemek için harcayabileceği TOPLAM süre.
# Ölçümde eski süreç ardıl kilit kontrolüne ulaşmadan ~50 ms önce ölüyordu;
# bu pay makinenin yükü altında daralabileceği için sınırlı bir tampon.
LOCK_WAIT_S = 5.0

# Ayırt edilebilir çıkış kodları — sessiz `sys.exit(0)` YOK.
EXIT_LOCK_TIMEOUT = 4      # ardıl açıldı ama kilidi süresinde alamadı
EXIT_SPAWN_FAILED = 5      # ardıl hiç başlatılamadı

_restart_requested = False


# ── Saf (yan etkisiz) yardımcılar ────────────────────────────────────────────

def strip_restart_flag(args) -> list:
    """`--restarted-from <pid>` çiftini argüman listesinden çıkarır.

    Art arda yeniden başlatmalarda işaretin BİRİKMEMESİ için gereklidir.
    """
    temiz, i = [], 0
    args = list(args or [])
    while i < len(args):
        if args[i] == RESTART_FLAG:
            i += 2                      # işaret + pid değeri
            continue
        if args[i].startswith(RESTART_FLAG + "="):
            i += 1
            continue
        temiz.append(args[i])
        i += 1
    return temiz


def parse_restart_flag(argv):
    """(temiz_argv, ebeveyn_pid | None) döndürür — yan etkisi yoktur."""
    argv = list(argv or [])
    if not argv:
        return [], None
    pid = None
    for i, a in enumerate(argv):
        if a == RESTART_FLAG and i + 1 < len(argv):
            try:
                pid = int(argv[i + 1])
            except ValueError:
                pid = None
            break
        if a.startswith(RESTART_FLAG + "="):
            try:
                pid = int(a.split("=", 1)[1])
            except ValueError:
                pid = None
            break
    return [argv[0]] + strip_restart_flag(argv[1:]), pid


def build_restart_command(executable: str, argv, frozen: bool,
                          parent_pid: int) -> list:
    """Ardıl süreç komutunu üretir — SAF fonksiyon, süreç başlatmaz.

    frozen : `sys.argv[0]` zaten EXE yoludur → yalnız argv[1:] eklenir,
             böylece EXE yolu bir kez geçer.
    kaynak : `sys.argv[0]` betik yoludur → yorumlayıcıdan sonra o da gerekir.

    Her iki durumda da varsa eski `--restarted-from` çifti ÇIKARILIR; yeni
    işaret bir kez eklenir (argümanlar birikmez).
    """
    argv = list(argv or [])
    kuyruk = strip_restart_flag(argv[1:])
    if frozen:
        komut = [executable] + kuyruk
    else:
        komut = [executable] + ([argv[0]] if argv else []) + kuyruk
    return komut + [RESTART_FLAG, str(parent_pid)]


# ── İstek durumu ─────────────────────────────────────────────────────────────

def request_restart() -> None:
    """Yeniden başlatma İSTEĞİNİ kaydeder; süreç başlatmaz."""
    global _restart_requested
    _restart_requested = True
    logger.info("Yeniden başlatma istendi; normal kapanış yolu işletilecek.")


def restart_requested() -> bool:
    return _restart_requested


def reset_restart_request() -> None:
    """Yalnız testler ve tekrar kullanım için durumu sıfırlar."""
    global _restart_requested
    _restart_requested = False


# ── Ardıl süreci başlatma ────────────────────────────────────────────────────

def spawn_successor(parent_pid: int) -> bool:
    """Ardıl süreci başlatır. True = başlatıldı, False = başlatılamadı.

    ASLA istisna fırlatmaz; teknik ayrıntı yalnız log dosyasına yazılır.
    """
    komut = build_restart_command(
        sys.executable, sys.argv, bool(getattr(sys, "frozen", False)),
        parent_pid)
    try:
        subprocess.Popen(komut, close_fds=True)
        logger.info("Ardıl süreç başlatıldı: %s", komut)
        return True
    except Exception:
        logger.exception("Ardıl süreç başlatılamadı. Komut: %s", komut)
        return False
