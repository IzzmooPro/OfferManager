"""Güvenli kimlik bilgisi saklama — Windows Credential Manager (keyring).

Sözleşme:
  * "kayıt yok" ile "depoya erişilemedi" AYRI durumlardır. Okuma kaydı
    bulamazsa "" döner; depo hata verirse `CredentialStoreError` fırlatır.
  * Yazma/silme başarısızlığı SESSİZCE YUTULMAZ; çağıran hatayı görür.
  * Loglara parola, credential değeri veya backend istisna METNİ yazılmaz —
    yalnız sabit açıklama ve istisna SINIF ADI. Backend mesajı kullanıcıya
    ulaşan zincire de sızmasın diye istisnalar `from None` ile yükseltilir.
"""
import logging
import re

logger = logging.getLogger("credential_store")

_SERVICE = "OfferManagementSystem"
_KEY_SMTP = "smtp_password"


class CredentialStoreError(RuntimeError):
    """Güvenli depoya erişilemedi.

    Mesajı kullanıcıya gösterilebilir; teknik ayrıntı TAŞIMAZ.
    """


def normalize_smtp_password(password: str) -> str:
    """SMTP şifresindeki TÜM boşlukları temizler.

    Gmail Uygulama Şifresi'ni 'abcd efgh ijkl mnop' gibi gruplar halinde
    gösterir; kullanıcı boşluklarıyla yapıştırırsa .strip() ortadaki
    boşlukları bırakır ve Gmail girişi reddeder. Hiçbir yaygın e-posta
    sağlayıcı şifrede boşluğa izin vermediğinden tümünü silmek güvenlidir.
    """
    return re.sub(r"\s+", "", password or "")


def _keyring():
    """keyring modülünü getirir; yoksa CredentialStoreError."""
    try:
        import keyring
        return keyring
    except Exception as exc:
        logger.error("Güvenli depo (keyring) yüklenemedi: %s", type(exc).__name__)
        raise CredentialStoreError("Güvenli depo kullanılamıyor.") from None


def _silme_hatasi_sinifi(kr):
    """keyring.errors.PasswordDeleteError — yoksa None."""
    return getattr(getattr(kr, "errors", None), "PasswordDeleteError", None)


def get_smtp_password() -> str:
    """Kayıtlı SMTP şifresini döndürür.

    "" → kayıt GERÇEKTEN yok.
    CredentialStoreError → depo okunamadı; "şifre girilmemiş" ile
    KARIŞTIRILMAMALIDIR.
    """
    kr = _keyring()
    try:
        return kr.get_password(_SERVICE, _KEY_SMTP) or ""
    except Exception as exc:
        logger.error("SMTP şifresi güvenli depodan okunamadı: %s",
                     type(exc).__name__)
        raise CredentialStoreError("Güvenli depo okunamadı.") from None


def set_smtp_password(password: str) -> None:
    """Şifreyi güvenli depoya yazar; boş şifre kaydı SİLER.

    Başarıda normal döner. Hata durumunda CredentialStoreError fırlatır —
    çağıran `None` dönüşünü başarı sayamaz.
    """
    kr = _keyring()
    password = normalize_smtp_password(password)
    if not password:
        _delete_smtp_password(kr)
        return
    try:
        kr.set_password(_SERVICE, _KEY_SMTP, password)
    except Exception as exc:
        logger.error("SMTP şifresi güvenli depoya yazılamadı: %s",
                     type(exc).__name__)
        raise CredentialStoreError("Güvenli depoya yazılamadı.") from None


def _delete_smtp_password(kr) -> None:
    """Kaydı siler. Kayıt zaten yoksa bu BAŞARIDIR."""
    try:
        kr.delete_password(_SERVICE, _KEY_SMTP)
    except Exception as exc:
        silme_hatasi = _silme_hatasi_sinifi(kr)
        if silme_hatasi is not None and isinstance(exc, silme_hatasi):
            logger.info("Güvenli depoda silinecek SMTP şifresi yoktu.")
            return
        logger.error("SMTP şifresi güvenli depodan silinemedi: %s",
                     type(exc).__name__)
        raise CredentialStoreError("Güvenli depodan silinemedi.") from None


def keyring_available() -> bool:
    """ÖN KONTROL: kullanılabilir bir backend var gibi görünüyor mu.

    True dönmesi işlemin BAŞARILI OLACAĞINI GARANTİ ETMEZ; gerçek okuma/yazma
    yine `CredentialStoreError` verebilir. Yoklama için credential
    YAZILMAZ/SİLİNMEZ — yalnız seçili backend ve önceliği incelenir.
    """
    try:
        import keyring
        backend = keyring.get_keyring()
    except Exception as exc:
        logger.warning("Güvenli depo backend'i belirlenemedi: %s",
                       type(exc).__name__)
        return False
    if backend is None:
        return False
    if type(backend).__module__.endswith("backends.fail"):
        return False
    try:
        return float(getattr(backend, "priority", 0) or 0) > 0
    except Exception:
        return False


# ── Eski düz metin şifrenin güvenli depoya taşınması ─────────────────────────

TASIMA_GEREKSIZ = "gereksiz"                     # cfg'de düz metin şifre yok
TASIMA_TAMAM = "tamam"                           # yazıldı + cfg temizlendi
TASIMA_CFG_TEMIZLENEMEDI = "cfg_temizlenemedi"   # yazıldı ama cfg'de kopya kaldı
TASIMA_BASARISIZ = "basarisiz"                   # yazılamadı; cfg KORUNDU


def migrate_plaintext_smtp_password(cfg: dict, mevcut_parola: str = "") -> tuple:
    """Eski `company.cfg` içindeki düz metin şifreyi güvenli depoya taşır.

    `mevcut_parola` — güvenli depodan OKUNAN değer. Doluysa güvenli depo
    KAYNAK kabul edilir: yazma YAPILMAZ (cfg'deki değer farklı olsa bile
    depodaki parola sessizce ezilmez), yalnız cfg'deki düz metin kopya
    temizlenir.

    Depo boşsa sıra ÖNEMLİ: önce keyring'e yazılır; yalnız yazma KESİN
    başarılı olduktan sonra cfg'deki alan kaldırılır. Yazma başarısızsa
    cfg'deki şifre KORUNUR (veri kaybı yok) ve "başarılı" diye loglanmaz.

    Dönüş: (şifre, durum). Şifre çağırana verilir ama hiçbir log/çıktıya
    yazılmaz. cfg başarıyla temizlenirse sözlükten de düşürülür.
    """
    duz_metin = (cfg or {}).get("smtp_password", "")
    if not duz_metin:
        return mevcut_parola, TASIMA_GEREKSIZ

    if mevcut_parola:
        # Güvenli depoda zaten geçerli bir kayıt var → yalnız cfg temizlenir.
        parola = mevcut_parola
    else:
        parola = duz_metin
        try:
            set_smtp_password(parola)
        except CredentialStoreError:
            logger.warning("Eski SMTP şifresi güvenli depoya TAŞINAMADI; "
                           "config dosyasındaki kopya korundu.")
            return parola, TASIMA_BASARISIZ

    try:
        from core.config import save_company_config
        temiz = {k: v for k, v in cfg.items() if k != "smtp_password"}
        save_company_config(temiz)          # mevcut atomik yazma yolu
    except Exception as exc:
        logger.warning("SMTP şifresi güvenli depoya taşındı ancak config "
                       "dosyasından kaldırılamadı (%s); iki kopya bulunabilir.",
                       type(exc).__name__)
        return parola, TASIMA_CFG_TEMIZLENEMEDI

    cfg.pop("smtp_password", None)
    logger.info("SMTP şifresinin config dosyasındaki düz metin kopyası "
                "kaldırıldı; güvenli depo kaynak olarak kullanılıyor.")
    return parola, TASIMA_TAMAM
