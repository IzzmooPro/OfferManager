"""Kaydetme/silme hatalarını GÜVENLİ mesaja ve güvenli loga çevirir.

Sözleşme:
  * Kullanıcı mesajında `str(exception)`, traceback, SQL veya dosya yolu
    BULUNMAZ — yalnız sabit, anlaşılır metinler.
  * Logda kişisel/kullanıcı verisi ve ham istisna metni BULUNMAZ; yalnız işlem
    adı, güvenli kayıt id'si, istisna SINIF ADI ve traceback'in dosya/satır
    çerçeveleri yazılır (`exc_info` KULLANILMAZ, çünkü istisna mesajını loga
    taşır).
  * Bu modül UI AÇMAZ; yalnız metin üretir ve loglar.
"""
import logging
import sqlite3
import traceback
from pathlib import Path

logger = logging.getLogger("islem_hatasi")

# Sınıflandırma için istisna metnine BAKILIR ama metin hiçbir yere yazılmaz.
_MESGUL_ISARETLERI = ("locked", "busy")

_CAKISMA = ("Bu kayıt mevcut bir kayıtla çakışıyor. "
            "Bilgileri kontrol edip yeniden deneyin.")
_MESGUL = ("Veritabanı şu anda meşgul. "
           "Birkaç saniye sonra yeniden deneyin.")
# Temel mesaj hem düğmesiz hem düğmeli çağıranlarda kullanılabilir; bu
# nedenle UI kontrolünden söz etmez. Düğmeye özgü ipucu, düğmeyi gerçekten
# ekleyen katmanda eklenir.
_DB_HATASI = ("Veritabanı işlemi tamamlanamadı. Lütfen yeniden deneyin. "
              "Ayrıntılar uygulama loguna kaydedildi.")

# `islem` → kullanıcıya gösterilecek fiil. Bilinmeyen işlem "kaydedilemedi"
# varsayar (geriye uyumlu).
_FIILLER = {
    "kaydet": "kaydedilemedi",
    "ekle": "eklenemedi",
    "ad": "adı değiştirilemedi",
    "sil": "silinemedi",
}


def _urun_cakismasi_mi(exc) -> bool:
    """Yalnız GERÇEK `DuplicateProductCodeError` örneği mi?

    Import döngüsünü önlemek için servis modülü fonksiyon içinde, güvenli
    biçimde yüklenir; yüklenemezse özel mesaj üretilmez.
    """
    try:
        from services.product_service import DuplicateProductCodeError
    except Exception:
        return False
    return isinstance(exc, DuplicateProductCodeError)


def _mesgul_mu(exc) -> bool:
    try:
        metin = str(exc).lower()
    except Exception:
        return False
    return any(a in metin for a in _MESGUL_ISARETLERI)


def guvenli_mesaj(exc, tur: str, islem: str = "kaydet") -> str:
    """Kullanıcıya gösterilecek GÜVENLİ metin.

    tur   : "Müşteri" | "Ürün" | "Kategori"
    islem : "kaydet" | "ekle" | "ad" | "sil"
    """
    # Ürün kod çakışması: O6'da kurulan anlaşılır bilgi korunur. YALNIZ gerçek
    # DuplicateProductCodeError için — duck typing YAPILMAZ, aksi hâlde
    # `existing` alanı taşıyan rastgele bir istisna kullanıcıya veri sızdırır.
    # Metin ham istisnadan değil, istisnanın ALANLARINDAN üretilir.
    if _urun_cakismasi_mi(exc):
        mevcut = exc.existing
        kod = getattr(mevcut, "product_code", "")
        ad = getattr(mevcut, "product_name", "")
        return (f"Bu ürün kodu zaten kayıtlı:\nKod: {kod}\nÜrün: {ad}\n\n"
                "Farklı bir kod girip yeniden deneyin.")
    if isinstance(exc, sqlite3.IntegrityError):
        return _CAKISMA
    if isinstance(exc, sqlite3.OperationalError):
        return _MESGUL if _mesgul_mu(exc) else _DB_HATASI
    fiil = _FIILLER.get(islem, "kaydedilemedi")
    return (f"{tur} {fiil}. Lütfen yeniden deneyin. "
            "Ayrıntılar uygulama loguna kaydedildi.")


def teknik_hata_mi(exc) -> bool:
    """Kullanıcının kendi başına düzeltemeyeceği, beklenmeyen hata mı?

    Çakışma ve "veritabanı meşgul" beklenen, kullanıcının yeniden deneyerek
    aşabileceği durumlardır → log klasörü düğmesi GEREKMEZ. Diğer her şey
    (şema/bilinmeyen istisna) tekniktir.
    """
    if _urun_cakismasi_mi(exc) or isinstance(exc, sqlite3.IntegrityError):
        return False
    if isinstance(exc, sqlite3.OperationalError):
        return not _mesgul_mu(exc)
    return True


def _guvenli_yer(exc) -> str:
    """Traceback'in yalnız dosya/fonksiyon/satır çerçeveleri — mesaj YOK."""
    try:
        cerceveler = traceback.extract_tb(exc.__traceback__)[-3:]
    except Exception:
        return ""
    return " <- ".join(f"{Path(f.filename).name}:{f.lineno} {f.name}"
                       for f in reversed(cerceveler))


def logla(exc, islem: str, kayit_id=None) -> None:
    """Hatayı GÜVENLİ biçimde loglar (kişisel veri ve ham mesaj olmadan)."""
    logger.error("%s başarısız — hata=%s id=%s konum=[%s]",
                 islem, type(exc).__name__,
                 kayit_id if kayit_id is not None else "-",
                 _guvenli_yer(exc))
