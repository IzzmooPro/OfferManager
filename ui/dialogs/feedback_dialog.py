"""Hata Raporla / Sorun veya Öneri Bildir — tek ortak pencere.

`core/feedback_report.py` üzerine İNCE UI sarmalayıcı; metnin tamamı oradan
gelir. Aynı ayrım `operation_error` / `operation_error_dialog` ikilisindekiyle
aynıdır.

Sözleşme:
  * **Otomatik gönderim YOKTUR.** Program hiçbir koşulda ağa çıkmaz, kullanıcının
    SMTP hesabını veya güvenli depodaki parolasını kullanmaz. Rapor yalnız
    kullanıcının kendi e-posta istemcisinde TASLAK olarak açılır ya da panoya
    kopyalanır.
  * **Tek form:** otomatik toplanan alanların HEPSİ pencerenin üst bölümünde
    kalın etiketlerle görünür; altında tek bir düzenlenebilir açıklama kutusu
    vardır. Ayrı bir salt-okunur ön izleme YOKTUR — gönderilen metin, görünen
    sabit alanlar ile kullanıcının yazdığı açıklamadan oluşur, dolayısıyla
    kullanıcıya gösterilmeyen hiçbir alan e-postaya veya panoya giremez.
  * "Rapor gönderildi" DENMEZ — program gönderimi doğrulayamaz. Yalnız
    "hazırlandı / açıldı / kopyalandı" denir.
  * "Ne oldu?" açıklaması zorunludur; boşken gönderme düğmeleri kapalıdır.
  * Pano YALNIZ kullanıcı düğmeye bastığında yazılır. "Vazgeç" hiçbir yan etki
    üretmez.
  * `mailto:` bağlantısı Qt'nin URL/query API'siyle kurulur ve kullanıcı metni
    yüzde-kodlanır; CRLF, `&` ve `?` ile başlık/query enjeksiyonu yapılamaz.
  * Bu pencerenin kendi hatası ikinci bir hata penceresi veya özyineleme
    üretmez: durum satırında kısa bir metin gösterilir ve yalnız istisna SINIF
    ADI kaydedilir.
"""
import logging

from PySide6.QtCore import Qt, QUrl, QUrlQuery
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication, QDialog, QFormLayout, QHBoxLayout, QLabel, QPlainTextEdit,
    QPushButton, QVBoxLayout,
)

from core import feedback_report as rapor
from core.constants import CONTACT_MAIL

logger = logging.getLogger("geri_bildirim")

RAPOR_DUGME_METNI = "Hata Raporla"

_BASLIK = {rapor.TUR_HATA: "Hata Raporla",
           rapor.TUR_ONERI: "Sorun veya Öneri Bildir"}

_GIRIS = {
    rapor.TUR_HATA: "Ne yapmaya çalışıyordunuz ve ne oldu? Kısaca yazın.",
    rapor.TUR_ONERI: "Yaşadığınız sorunu ya da önerinizi kısaca yazın.",
}

# Not DÜRÜST olmalıdır: program otomatik toplamaz, ama kullanıcının yazdığı
# metni değiştirmez. "Hiçbir kişisel veri gitmez" demek yanlış güven verirdi.
GIZLILIK_NOTU = (
    "Uygulama müşteri, teklif, ürün ve şifre bilgilerini otomatik eklemez. "
    "Yazdığınız açıklama rapora aynen girer; kişisel veya müşteri bilgisi "
    "yazmayın. Rapor kendiliğinden gönderilmez."
)

_DURUM_PANO = "Rapor panoya kopyalandı."
_DURUM_MAIL = "E-posta uygulaması açıldı; göndermek için Gönder'e basın."
_DURUM_MAIL_YOK = ("E-posta uygulaması açılamadı. Raporu \"Panoya Kopyala\" "
                   "ile alıp bize iletebilirsiniz.")


def _yuzde_kodla(metin: str) -> str:
    """Kullanıcı metnini query'ye güvenle koymak için yüzde-kodlar.

    Qt'nin kendi kodlayıcısı kullanılır: satır sonları, `&`, `?`, `=` ve `:`
    dâhil tüm ayraçlar kodlanır, böylece kullanıcı metni yeni bir query alanı
    ya da e-posta başlığı üretemez.
    """
    return bytes(QUrl.toPercentEncoding(metin)).decode("ascii")


def mailto_baglantisi(konu: str, govde: str) -> QUrl:
    """Kanonik iletişim adresine giden güvenli `mailto:` bağlantısı."""
    url = QUrl()
    url.setScheme("mailto")
    url.setPath(CONTACT_MAIL)
    sorgu = QUrlQuery()
    sorgu.addQueryItem("subject", _yuzde_kodla(konu))
    sorgu.addQueryItem("body", _yuzde_kodla(govde))
    url.setQuery(sorgu)
    return url


class FeedbackDialog(QDialog):
    """İki giriş noktasının da kullandığı tek pencere.

    `exc` yalnız güvenli hata kutusundan gelen teknik hata yolunda verilir;
    Yardım menüsü yolunda `None`'dır. İstisna BURADA KAYDEDİLMEZ — çağıran
    (`operation_error.logla`) zaten bir kez kaydetmiştir.
    """

    def __init__(self, parent=None, *, exc=None, islem: str = ""):
        super().__init__(parent)
        self._tur = rapor.TUR_HATA if exc is not None else rapor.TUR_ONERI
        self.setWindowTitle(_BASLIK[self._tur])
        self.setMinimumSize(560, 520)

        # Rapor no ve tarih pencere açılışında BİR KEZ üretilir; her tuşta
        # değişirse kullanıcı ekranda gördüğünden başka bir rapor gönderir.
        self._temel = rapor.rapor_olustur(self._tur, "", exc=exc, islem=islem)
        self._rapor_no = self._temel.rapor_no

        self._build_ui()
        self._durumu_guncelle()

    # ── kurulum ─────────────────────────────────────────────────────────
    @staticmethod
    def _kalin(metin: str) -> QLabel:
        """Kalın etiket — QSS'ten bağımsız olsun diye font'tan işaretlenir."""
        etiket = QLabel(metin)
        yazi = etiket.font()
        yazi.setBold(True)
        etiket.setFont(yazi)
        etiket.setStyleSheet("font-weight:bold;")
        return etiket

    def _build_ui(self):
        duzen = QVBoxLayout(self)
        duzen.setContentsMargins(20, 16, 20, 14)
        duzen.setSpacing(8)

        # ── Otomatik toplanan alanlar — hepsi GÖRÜNÜR ────────────────────
        # Gönderilecek metnin sabit kısmı burada birebir gösterilir; kullanıcıya
        # gösterilmeyen hiçbir alan e-postaya veya panoya giremez.
        v = self._temel
        bilgi = QFormLayout()
        bilgi.setContentsMargins(0, 0, 0, 4)
        bilgi.setHorizontalSpacing(12)
        bilgi.setVerticalSpacing(4)
        satirlar = [("Rapor No", v.rapor_no),
                    ("Tarih", v.tarih),
                    ("Sürüm", f"{v.surum} ({v.calisma_modu})"),
                    ("Sistem", f"{v.isletim_sistemi} ({v.mimari})")]
        if v.teknik is not None:
            satirlar += [("İşlem", v.teknik.islem),
                         ("Hata Türü", v.teknik.hata_sinifi),
                         ("Konum", v.teknik.konum or "-")]
        for etiket, deger in satirlar:
            alan = QLabel(deger)
            alan.setWordWrap(True)
            alan.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse)
            bilgi.addRow(self._kalin(f"{etiket}:"), alan)
        duzen.addLayout(bilgi)

        # ── Tek düzenlenebilir alan ──────────────────────────────────────
        duzen.addWidget(self._kalin("Ne oldu?"))
        self._aciklama = QPlainTextEdit()
        self._aciklama.setPlaceholderText(_GIRIS[self._tur])
        self._aciklama.setMinimumHeight(120)
        self._aciklama.textChanged.connect(self._durumu_guncelle)
        duzen.addWidget(self._aciklama, 1)

        gizlilik = QLabel(GIZLILIK_NOTU)
        gizlilik.setWordWrap(True)
        gizlilik.setObjectName("hint_label")
        duzen.addWidget(gizlilik)

        self._durum = QLabel("")
        self._durum.setWordWrap(True)
        self._durum.setObjectName("hint_label")
        duzen.addWidget(self._durum)

        satir = QHBoxLayout()
        satir.addStretch(1)
        self._btn_mail = QPushButton("E-postayı Aç")
        self._btn_mail.clicked.connect(self._eposta_ac)
        self._btn_pano = QPushButton("Panoya Kopyala")
        self._btn_pano.clicked.connect(self._panoya_kopyala)
        self._btn_iptal = QPushButton("Vazgeç")
        self._btn_iptal.clicked.connect(self.reject)
        for b in (self._btn_mail, self._btn_pano, self._btn_iptal):
            satir.addWidget(b)
        duzen.addLayout(satir)

    # ── rapor metni ─────────────────────────────────────────────────────
    def _veri(self):
        import dataclasses
        return dataclasses.replace(self._temel,
                                   aciklama=self._aciklama.toPlainText())

    def rapor_metni(self) -> str:
        """Gönderilecek metin — penceredeki sabit alanlar + açıklama.

        Tek kaynak: e-posta gövdesi ve pano içeriği bu metindir; kullanıcıya
        gösterilmeyen bir alan buraya eklenemez.
        """
        return rapor.metin_uret(self._veri())

    def _durumu_guncelle(self):
        gecerli = rapor.aciklama_gecerli(self._aciklama.toPlainText())
        self._btn_mail.setEnabled(gecerli)
        self._btn_pano.setEnabled(gecerli)

    # ── eylemler ────────────────────────────────────────────────────────
    def _panoya_kopyala(self):
        """Pano YALNIZ burada, yani gerçek tıklamada yazılır."""
        try:
            QApplication.clipboard().setText(self.rapor_metni())
        except Exception as exc:                               # noqa: BLE001
            self._guvenli_bildir("Rapor panoya kopyalanamadı.", exc)
            return
        self._durum.setText(_DURUM_PANO)

    def _eposta_ac(self):
        """Kullanıcının kendi e-posta istemcisinde TASLAK açar; göndermez."""
        veri = self._veri()
        try:
            acildi = QDesktopServices.openUrl(
                mailto_baglantisi(rapor.konu_uret(veri),
                                  rapor.metin_uret(veri)))
        except Exception as exc:                               # noqa: BLE001
            self._guvenli_bildir(_DURUM_MAIL_YOK, exc)
            return
        self._durum.setText(_DURUM_MAIL if acildi else _DURUM_MAIL_YOK)

    def _guvenli_bildir(self, mesaj: str, exc):
        """İkinci pencere AÇMAZ; yalnız istisna SINIF ADI kaydedilir.

        Bu yol yeni bir hata diyaloğu açmadığı için özyineleme oluşmaz ve
        istisna metni (yol/gizli veri taşıyabilir) hiçbir yere yazılmaz.
        """
        logger.warning("Geri bildirim penceresi işlemi tamamlanamadı — hata=%s",
                       type(exc).__name__)
        self._durum.setText(mesaj)
