"""
Ortak test yapılandırması — tüm test dosyaları aynı izole ortamı kullanır.
Bu dosya pytest tarafından, test modülleri import edilmeden ÖNCE yüklenir.

Neden tüm değişkenler:
    Eskiden yalnız LOCALAPPDATA yönlendiriliyordu. `core/app_paths.py` içindeki
    `BACKUP_DIR = Path.home() / "Documents" / ...` USERPROFILE'a baktığı ve
    import anında `mkdir()` yaptığı için testler GERÇEK kullanıcı profilinde
    klasör oluşturuyordu; `tempfile` de gerçek %TEMP%'e yazıp artık bırakıyordu.

Yönlendirme MODÜL DÜZEYİNDE ve hiçbir proje modülü import edilmeden yapılır;
app_paths gibi modüller yollarını import anında sabitlediği için sıra kritiktir.
Alt süreç kullanan testler kendi (daha sıkı) izolasyonlarını kurmaya devam eder.
"""
import atexit
import os
import shutil
import sys
import tempfile
from pathlib import Path

# ── Tek oturum kökü ──────────────────────────────────────────────────────────
OTURUM_KOKU = Path(tempfile.mkdtemp(prefix="oms_test_shared_")).resolve()

_PROFIL   = OTURUM_KOKU / "profil"
_LOCAL    = _PROFIL / "AppData" / "Local"
_ROAMING  = _PROFIL / "AppData" / "Roaming"
_BELGELER = _PROFIL / "Documents"
_TEMP     = OTURUM_KOKU / "Temp"
for _dizin in (_LOCAL, _ROAMING, _BELGELER, _TEMP):
    _dizin.mkdir(parents=True, exist_ok=True)

os.environ["USERPROFILE"]  = str(_PROFIL)
os.environ["HOME"]         = str(_PROFIL)
os.environ["LOCALAPPDATA"] = str(_LOCAL)
os.environ["APPDATA"]      = str(_ROAMING)
os.environ["TMP"]          = str(_TEMP)
os.environ["TEMP"]         = str(_TEMP)

# HOMEDRIVE + HOMEPATH birleşimi profille TUTARLI olmalı; ntpath.expanduser
# USERPROFILE yoksa bu ikiliye düşer, tutarsız bırakılırsa göreli/geçersiz bir
# ev dizini üretir.
_surucu, _kalan = os.path.splitdrive(str(_PROFIL))
os.environ["HOMEDRIVE"] = _surucu
os.environ["HOMEPATH"]  = _kalan or os.sep

# tempfile.gettempdir() ilk çağrıda önbelleğe alınır; ortam değişkenini
# değiştirmek tek başına yetmez.
tempfile.tempdir = str(_TEMP)


# ── Güvenli depo (keyring) yalıtımı ──────────────────────────────────────────
# Suite GERÇEK Windows Credential Manager'a okuma/yazma/silme YAPMAZ.
# Sınırdaki üç fonksiyon bellek içi sahte bir depoyla değiştirilir; gerçek
# fonksiyonlar `GERCEK_KEYRING` altında saklanır ve hiç çağrılmaz.
# Credential testleri kendi senaryoları için bu sahteleri kendileri değiştirir.
SAHTE_KEYRING = {}
KEYRING_CAGRILARI = {"get": 0, "set": 0, "delete": 0}
GERCEK_KEYRING = {}


def _sahte_kur():
    try:
        import keyring
    except Exception:
        return
    GERCEK_KEYRING.update({
        "get": keyring.get_password,
        "set": keyring.set_password,
        "delete": keyring.delete_password,
    })

    def _get(servis, kullanici):
        KEYRING_CAGRILARI["get"] += 1
        return SAHTE_KEYRING.get((servis, kullanici))

    def _set(servis, kullanici, deger):
        KEYRING_CAGRILARI["set"] += 1
        SAHTE_KEYRING[(servis, kullanici)] = deger

    def _delete(servis, kullanici):
        KEYRING_CAGRILARI["delete"] += 1
        if (servis, kullanici) not in SAHTE_KEYRING:
            raise keyring.errors.PasswordDeleteError("kayıt yok")
        del SAHTE_KEYRING[(servis, kullanici)]

    keyring.get_password = _get
    keyring.set_password = _set
    keyring.delete_password = _delete


_sahte_kur()


def _oturum_kokunu_temizle():
    """Oturum sonunda geçici kökü sil.

    Windows'ta açık kalan bir dosya tutamacı silmeyi engelleyebilir. Böyle bir
    durumda suite sonucu GİZLENMEZ; uyarı yazılır ve kalan yol raporlanır.
    """
    shutil.rmtree(OTURUM_KOKU, ignore_errors=True)
    if OTURUM_KOKU.exists():
        sys.stderr.write(
            f"\n[uyarı] Test oturum kökü silinemedi (dosya kilidi olabilir): "
            f"{OTURUM_KOKU}\n")


atexit.register(_oturum_kokunu_temizle)
