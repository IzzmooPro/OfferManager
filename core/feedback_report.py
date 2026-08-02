"""Hata / öneri raporunun SAF veri modeli ve metin üreticisi.

Bu modül bilinçli olarak **UI'dan ve yan etkilerden bağımsızdır**: Qt kullanmaz,
diske dokunmaz, ağa çıkmaz, kayıt tutmaz, güvenli depodan parola okumaz.
Yalnız veri toplar ve metin üretir; gösterme, kopyalama ve e-posta taslağı açma
işleri `ui/dialogs/feedback_dialog.py` katmanındadır. Aynı ayrım
`ui/utils/operation_error.py` ile diyalog sarmalayıcısı arasında da vardır.

Rapora YALNIZ şunlar girer:
  * rastgele ve kalıcı olmayan rapor numarası
  * yerel tarih/saat
  * `APP_VERSION` ve paketli/kaynak çalışma modu
  * işletim sistemi sürümü ve mimarisi (bilgisayar/kullanıcı adı YOK)
  * rapor türü ve kullanıcının kendi açıklaması
  * yalnız teknik hata yolunda: güvenli işlem kategorisi, istisna SINIF ADI ve
    `dosya.py:satır fonksiyon` özeti

Rapora ASLA girmez: `str(exception)`, istisna mesajı, traceback metni, SQL,
mutlak dosya yolu, kayıt kimliği, teklif numarası, müşteri/ürün/firma verisi,
parola veya güvenli depo bilgisi.
"""
import platform
import sys
import traceback
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from core.constants import APP_VERSION

TUR_HATA = "Hata bildirimi"
TUR_ONERI = "Sorun veya öneri"
TURLER = (TUR_HATA, TUR_ONERI)

# Traceback'ten alınacak en fazla çerçeve sayısı — yalnız konum, metin değil.
_CERCEVE_SAYISI = 3
_TARIH_BICIMI = "%d.%m.%Y %H:%M"


@dataclass(frozen=True)
class TeknikOzet:
    """Mevcut hatanın GÜVENLİ özeti — ham istisna metni taşımaz.

    Kayıt kimliği, teklif numarası veya müşteri bilgisi için ALAN YOKTUR;
    böyle bir veri rapora yanlışlıkla bile eklenemez.
    """
    islem: str
    hata_sinifi: str
    konum: str


@dataclass(frozen=True)
class RaporVerisi:
    rapor_no: str
    tarih: str
    surum: str
    isletim_sistemi: str
    mimari: str
    calisma_modu: str
    tur: str
    aciklama: str = ""
    teknik: Optional[TeknikOzet] = field(default=None)


def yeni_rapor_no() -> str:
    """Kısa, rastgele, kalıcı olmayan rapor numarası.

    Makineye veya kullanıcıya bağlı hiçbir bilgi içermez (`uuid4` rastgeledir;
    MAC adresi kullanan `uuid1` KULLANILMAZ).
    """
    return uuid.uuid4().hex[:8].upper()


def calisma_modu() -> str:
    """Paketli EXE mi, kaynaktan mı çalışıyor?"""
    return "paketli" if getattr(sys, "frozen", False) else "kaynak"


def guvenli_konum(exc) -> str:
    """Traceback'in yalnız `dosya.py:satır fonksiyon` çerçeveleri.

    Dizin yolu ALINMAZ — yalnız dosya adı; böylece kullanıcı klasörü rapora
    girmez. İstisna mesajı hiçbir biçimde kullanılmaz.
    """
    try:
        cerceveler = traceback.extract_tb(exc.__traceback__)[-_CERCEVE_SAYISI:]
    except Exception:                                          # noqa: BLE001
        return ""
    return " <- ".join(f"{_dosya_adi(c.filename)}:{c.lineno} {c.name}"
                       for c in reversed(cerceveler))


def _dosya_adi(yol) -> str:
    """Yolun yalnız son parçası — `pathlib` kullanılmadan, ayraçtan bağımsız."""
    metin = str(yol or "")
    for ayrac in ("\\", "/"):
        metin = metin.rsplit(ayrac, 1)[-1]
    return metin


def teknik_ozet(exc, islem: str) -> TeknikOzet:
    """İstisnadan GÜVENLİ özet üretir. İstisnayı KAYDETMEZ.

    Kayıt tutma sorumluluğu çağıranındır (`operation_error.logla`); burada
    tekrar kaydedilirse aynı istisna iki kez yazılırdı.
    """
    return TeknikOzet(islem=str(islem or "").strip() or "-",
                      hata_sinifi=type(exc).__name__,
                      konum=guvenli_konum(exc))


def aciklama_gecerli(metin) -> bool:
    """"Ne oldu?" alanı zorunludur; yalnız boşluk yeterli değildir."""
    return bool(str(metin or "").strip())


def rapor_olustur(tur: str, aciklama: str = "", exc=None,
                  islem: str = "") -> RaporVerisi:
    """Rapor verisini toplar. Yan etki üretmez.

    `exc` yalnız teknik hata yolunda verilir; verilmezse teknik özet üretilmez.
    """
    return RaporVerisi(
        rapor_no=yeni_rapor_no(),
        tarih=datetime.now().strftime(_TARIH_BICIMI),
        surum=APP_VERSION,
        # `platform.node()` (bilgisayar adı) ve kullanıcı adı BİLİNÇLİ olarak
        # alınmaz; yalnız sürüm ve mimari tanı için gereklidir.
        isletim_sistemi=f"{platform.system()} {platform.version()}".strip(),
        mimari=platform.machine(),
        calisma_modu=calisma_modu(),
        tur=tur,
        aciklama=str(aciklama or ""),
        teknik=teknik_ozet(exc, islem) if exc is not None else None,
    )


def konu_uret(veri: RaporVerisi) -> str:
    """E-posta konusu — yalnız güvenli alanlardan üretilir."""
    return f"Teklif Yönetim {veri.surum} — {veri.tur} [{veri.rapor_no}]"


def metin_uret(veri: RaporVerisi) -> str:
    """Kullanıcıya ön izlemede AYNEN gösterilen rapor metni.

    Kullanıcı ne göreceğini bilmeden gönderemesin diye, gönderilecek metin ile
    ön izlenen metin tek ve aynı üreticiden gelir.
    """
    satirlar = [
        f"Teklif Yönetim Sistemi — {veri.tur}",
        "",
        f"Rapor no : {veri.rapor_no}",
        f"Tarih    : {veri.tarih}",
        f"Sürüm    : {veri.surum} ({veri.calisma_modu})",
        f"Sistem   : {veri.isletim_sistemi} ({veri.mimari})",
        "",
        "Ne oldu?",
        veri.aciklama.strip() or "(açıklama girilmedi)",
    ]
    if veri.teknik is not None:
        satirlar += [
            "",
            "Teknik özet",
            f"İşlem     : {veri.teknik.islem}",
            f"Hata türü : {veri.teknik.hata_sinifi}",
            f"Konum     : {veri.teknik.konum or '-'}",
        ]
    return "\n".join(satirlar)
