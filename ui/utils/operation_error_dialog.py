"""Güvenli hata diyaloğu — `operation_error` üzerine İNCE UI sarmalayıcı.

Neden ayrı modül: `ui/utils/operation_error.py` bilinçli olarak **UI açmaz ve
Qt import etmez** (metin üretir + güvenli loglar). Bu modül yalnız o metni
gerçek `QMessageBox` içinde gösterir.

Sözleşme:
  * Kullanıcı mesajı `operation_error.guvenli_mesaj()`ten gelir; ham istisna,
    SQL, traceback, yerel yol veya kayıt adı içermez.
  * Güvenli log `operation_error.logla()` ile TAM BİR KEZ yazılır.
  * "Log Klasörünü Aç" düğmesi YALNIZ beklenmeyen/teknik hatalarda eklenir
    (`operation_error.teknik_hata_mi`); doğrulama mesajlarında eklenmez.
  * Düğme `clicked` sinyaline bağlıdır: kullanıcı basmadıkça `os.startfile`
    ÇAĞRILMAZ. Tam `LOG_DIR` yolu mesaj metninde GÖSTERİLMEZ.
  * `LOG_DIR` sabit kanonik yoldan (`core.app_paths`) okunur; istisnadan veya
    kullanıcı girdisinden yol üretilmez.
  * Klasör yoksa ya da `os.startfile` hata verirse: ikinci pencere açılmaz,
    istisna dışarı sızmaz, yalnız istisna SINIF ADI warning olarak loglanır.
    Bu yol yeniden hata diyaloğu açmadığı için özyineleme oluşmaz.
"""
import logging
import os

from PySide6.QtWidgets import QMessageBox

from ui.utils import operation_error as op_hata

logger = logging.getLogger("islem_hatasi_ui")

LOG_DUGME_METNI = "Log Klasörünü Aç"
_IPUCU = f'Sorun sürerse "{LOG_DUGME_METNI}" düğmesini kullanın.'


def kullanici_mesaji(exc, tur: str, islem: str = "kaydet") -> str:
    """Temel güvenli mesaj + (yalnız düğme eklenecekse) düğme ipucu.

    Düğme ipucu BURADA eklenir; `operation_error` UI'dan bağımsız kalır ve
    statik `QMessageBox.warning` kullanan sayfalar (customers/products)
    olmayan bir düğmeye yönlendirilmez.
    """
    temel = op_hata.guvenli_mesaj(exc, tur, islem)
    return f"{temel} {_IPUCU}" if op_hata.teknik_hata_mi(exc) else temel


def _log_dizini():
    """Kanonik log klasörü — istisnadan/kullanıcıdan yol türetilmez."""
    from core.app_paths import LOG_DIR
    return LOG_DIR


def log_klasorunu_ac() -> bool:
    """Yalnız kullanıcı düğmeye bastığında çağrılır. Hata YUKARI SIZMAZ."""
    try:
        yol = _log_dizini()
        if not yol.exists():
            logger.warning("Log klasörü açılamadı — neden=klasör yok")
            return False
        os.startfile(str(yol))
        return True
    except Exception as exc:                                   # noqa: BLE001
        # Yalnız SINIF ADI loglanır; istisna metni yol/gizli veri taşıyabilir.
        logger.warning("Log klasörü açılamadı — hata=%s", type(exc).__name__)
        return False


def _kutu(parent, baslik: str, mesaj: str, ikon, log_dugmesi: bool):
    kutu = QMessageBox(parent)
    kutu.setIcon(ikon)
    kutu.setWindowTitle(baslik)
    kutu.setText(mesaj)
    if log_dugmesi:
        dugme = kutu.addButton(LOG_DUGME_METNI,
                               QMessageBox.ButtonRole.ActionRole)
        # Explorer YALNIZ gerçek tıklamada açılır.
        dugme.clicked.connect(log_klasorunu_ac)
    kutu.addButton(QMessageBox.StandardButton.Ok)
    kutu.exec()
    return kutu


def hata_goster(parent, baslik: str, exc, tur: str, islem: str = "kaydet",
                kayit_id=None):
    """Güvenli log + güvenli mesaj + (gerekliyse) log klasörü düğmesi."""
    op_hata.logla(exc, f"{tur} {islem}", kayit_id=kayit_id)
    # Mesajdaki ipucu ile kutudaki düğme AYNI koşula bağlıdır: biri varsa
    # diğeri de vardır (tests: test_mesaj_ile_dugme_varligi_tutarli).
    return _kutu(parent, baslik, kullanici_mesaji(exc, tur, islem),
                 QMessageBox.Icon.Warning,
                 log_dugmesi=op_hata.teknik_hata_mi(exc))


def dogrulama_goster(parent, baslik: str, mesaj: str):
    """Kullanıcı hatası (eksik seçim/alan): log YOK, log düğmesi YOK."""
    return _kutu(parent, baslik, mesaj, QMessageBox.Icon.Information,
                 log_dugmesi=False)
