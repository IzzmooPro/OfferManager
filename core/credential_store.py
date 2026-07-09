"""Güvenli kimlik bilgisi saklama — Windows Credential Manager (keyring)."""
import logging
import re

logger = logging.getLogger("credential_store")

_SERVICE = "OfferManagementSystem"
_KEY_SMTP = "smtp_password"


def normalize_smtp_password(password: str) -> str:
    """SMTP şifresindeki TÜM boşlukları temizler.

    Gmail Uygulama Şifresi'ni 'abcd efgh ijkl mnop' gibi gruplar halinde
    gösterir; kullanıcı boşluklarıyla yapıştırırsa .strip() ortadaki
    boşlukları bırakır ve Gmail girişi reddeder. Hiçbir yaygın e-posta
    sağlayıcı şifrede boşluğa izin vermediğinden tümünü silmek güvenlidir.
    """
    return re.sub(r"\s+", "", password or "")


def get_smtp_password() -> str:
    try:
        import keyring
        return keyring.get_password(_SERVICE, _KEY_SMTP) or ""
    except Exception as e:
        logger.debug("Keyring okuma hatası: %s", e)
        return ""


def set_smtp_password(password: str) -> None:
    try:
        import keyring
        password = normalize_smtp_password(password)
        if password:
            keyring.set_password(_SERVICE, _KEY_SMTP, password)
        else:
            try:
                keyring.delete_password(_SERVICE, _KEY_SMTP)
            except keyring.errors.PasswordDeleteError:
                logger.debug("Keyring'de silinecek şifre bulunamadı")
    except Exception as e:
        logger.debug("Keyring yazma hatası: %s", e)


def keyring_available() -> bool:
    try:
        import keyring  # noqa: F401
        return True
    except ImportError:
        return False
