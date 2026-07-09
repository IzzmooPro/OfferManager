"""
Yardım pencereleri:
  - HowToUseDialog  : Nasıl Kullanılır
  - AboutDialog     : Hakkında
"""
import logging, threading, urllib.request, json
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QWidget, QFrame, QTabWidget, QMessageBox
)
from PySide6.QtCore import Qt, QThread, Signal
logger = logging.getLogger("help")
from core.constants import APP_VERSION
from ui.utils.updater import is_newer_version

# ── Uygulama sabitleri ────────────────────────────────────────────────────────
GITHUB_REPO  = "IzzmooPro/offer_management_system"
GITHUB_URL   = f"https://github.com/{GITHUB_REPO}"
CONTACT_MAIL = "IzzmooPro@gmail.com"

# ── Ortak yardımcılar ────────────────────────────────────────────────────────

def _title(text: str, size=11) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(f"font-size:{size}pt;font-weight:700;")
    lbl.setWordWrap(True)
    return lbl


def _body(text: str, size=10) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(f"font-size:{size}pt;")
    lbl.setWordWrap(True)
    lbl.setTextFormat(Qt.TextFormat.RichText)
    lbl.setOpenExternalLinks(True)
    lbl.setContentsMargins(0, 2, 0, 6)
    return lbl


def _sep() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setFrameShadow(QFrame.Shadow.Sunken)
    return f


def _step(num: str, title: str, desc: str) -> QWidget:
    """Numaralı adım widget'ı."""
    w = QWidget()
    row = QHBoxLayout(w)
    row.setContentsMargins(0, 4, 0, 4)
    row.setSpacing(14)

    from ui.utils.theme_manager import get_theme
    badge = QLabel(num)
    badge.setFixedSize(32, 32)
    badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
    badge.setStyleSheet(
        f"background-color: {get_theme()['accent_blue']}; color: white; "
        "border-radius: 16px; font-weight: bold; font-size: 10pt;"
    )
    row.addWidget(badge)

    right = QVBoxLayout()
    right.setSpacing(2)
    t = QLabel(title)
    t.setStyleSheet("font-size:10pt;font-weight:700;")
    t.setWordWrap(True)
    d = QLabel(desc)
    d.setWordWrap(True)
    d.setStyleSheet(f"color: {get_theme()['text_secondary']}; font-size: 10pt;")
    right.addWidget(t)
    right.addWidget(d)
    row.addLayout(right)
    return w


# ── Nasıl Kullanılır ─────────────────────────────────────────────────────────

class HowToUseDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Nasıl Kullanılır?  [F1 → kapat]")
        self.setMinimumSize(760, 680)
        self.resize(820, 720)
        self._build_ui()

    def keyPressEvent(self, event):
        """F1 ile aç/kapat toggle — dialog odakta olsa bile çalışır."""
        from PySide6.QtCore import Qt as _Qt
        if event.key() == _Qt.Key.Key_F1:
            self.close()
        else:
            super().keyPressEvent(event)

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        tabs = QTabWidget()
        tabs.setDocumentMode(True)
        tabs.setMovable(False)
        tabs.setUsesScrollButtons(False)
        tabs.setTabPosition(QTabWidget.TabPosition.North)
        outer.addWidget(tabs)

        tabs.addTab(self._tab_quickstart(),  "Hızlı Başlangıç")
        tabs.addTab(self._tab_offers(),      "Teklif Oluşturma")
        tabs.addTab(self._tab_products(),    "Ürün ve Müşteri")
        tabs.addTab(self._tab_pdf(),         "PDF ve Ayarlar")
        tabs.addTab(self._tab_tips(),        "İpuçları")

        close_btn = QPushButton("Kapat")
        close_btn.setObjectName("secondary")
        close_btn.setFixedWidth(120)
        close_btn.clicked.connect(self.accept)
        row = QHBoxLayout()
        row.addStretch(); row.addWidget(close_btn)
        row.setContentsMargins(16, 8, 16, 12)
        outer.addLayout(row)

    @staticmethod
    def _scroll(content_widget) -> QScrollArea:
        sa = QScrollArea()
        sa.setWidgetResizable(True)
        sa.setWidget(content_widget)
        sa.setFrameShape(QFrame.Shape.NoFrame)
        return sa

    def _tab_quickstart(self):
        w = QWidget(); layout = QVBoxLayout(w)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(10)

        layout.addWidget(_title("Programa Hoş Geldiniz!", 15))
        layout.addWidget(_body(
            "Bu program ile müşterilerinize <b>profesyonel PDF teklifler</b> oluşturabilir, "
            "ürün kataloğunuzu ve müşteri listenizi yönetebilirsiniz. "
            "Açık ve koyu tema desteği, otomatik yedekleme, Excel'den veri aktarma gibi "
            "özellikler içerir."
        ))
        layout.addWidget(_sep())
        layout.addWidget(_title("İlk Kullanım — 4 Adımda Hazır", 13))
        layout.addSpacing(4)

        steps = [
            ("1", "Ayarları Yapılandırın",
             "Sol menüden Ayarlar'a gidin. Şirket adı, adres, telefon, logo ve "
             "imza bilgilerini doldurun. Bu bilgiler tüm PDF tekliflerin başlığına otomatik eklenir."),
            ("2", "Ürünleri Ekleyin",
             "Ürünler sayfasından Yeni Ürün butonu ile ürün kodları, fiyatlar ve "
             "stok bilgilerini girin. Teklif oluştururken bu listeden hızlıca seçim yapabilirsiniz."),
            ("3", "Müşterileri Ekleyin",
             "Müşteriler sayfasından müşteri firma, iletişim ve adres bilgilerini girin. "
             "Teklif oluştururken açılır listeden seçerek otomatik doldurulur. "
             "Kayıtlı olmayan müşteriler için otomatik kayıt önerisi de sunulur."),
            ("4", "Teklif Oluşturun ve PDF Alın",
             "Yeni Teklif sayfasından müşteri seçin, ürün ekleyin, "
             "<b>Teklifi Tamamla</b> butonuna basın. PDF oluşturulur ve dilerseniz e-posta ile gönderilir."),
        ]
        for num, title, desc in steps:
            layout.addWidget(_step(num, title, desc))

        layout.addStretch()
        return self._scroll(w)

    def _tab_offers(self):
        w = QWidget(); layout = QVBoxLayout(w)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(10)

        layout.addWidget(_title("Teklif Oluşturma", 14))
        layout.addWidget(_body(
            "<b>Yeni Teklif</b> sayfasında teklif numarası otomatik üretilir (FORMAT: PREFIX-000001). "
            "Sadece müşteri seçip ürün eklemek yeterlidir."
        ))
        layout.addWidget(_sep())

        sections = [
            ("Müşteri Seçimi",
             "Açılır listeden kayıtlı müşteriyi seçin — firma adı, adres ve ilgili kişi "
             "otomatik dolar. İstediğiniz alanı elle düzenleyebilirsiniz. "
             "Kayıtlı olmayan bir firma adı girerseniz, sistem otomatik olarak kaydetmeyi önerir."),
            ("Ürün Ekleme",
             "<b>Ürün Ekle</b> butonuna tıklayın, çıkan pencereden arama yaparak ürün seçin. "
             "Shift/Ctrl ile çoklu seçim yapabilirsiniz. "
             "Adet ve birim fiyatı değiştirince toplam otomatik hesaplanır."),
            ("Satır Kaldırma",
             "Tabloda satıra tıklayıp <b>Ürün Çıkart</b> butonuna basın."),
            ("Teklif Koşulları",
             "Son adımda teklif geçerlilik süresi, ödeme vadesi ve ek not girebilirsiniz. "
             "Bu bilgiler hem özette hem PDF'te görüntülenir."),
            ("Kaydetme ve PDF",
             "<b>Teklifi Tamamla (Kaydet & PDF)</b> butonuna basarak tüm süreci tek adımda halledebilirsiniz. "
             "Sistem önce teklifi veritabanına kaydeder, ardından PDF dosyasını nereye "
             "kaydedeceğinizi sorar ve en sonunda bu PDF'i müşterinize e-posta olarak atıp atmayacağınızı sorar."),
            ("Düzenleme",
             "Teklifler sayfasında satıra <b>çift tıklayın</b> veya seçip "
             "<b>Düzenle</b> butonuna basın. Teklif formu o teklif ile açılır. "
             "Düzenlemeden çıkıp tamamen yepyeni bir teklif oluşturmak için sol menüden "
             "<b>Yeni Teklif</b> tuşuna basmanız yeterlidir; form otomatik sıfırlanır."),
        ]
        for title, desc in sections:
            layout.addWidget(_title(f"  {title}", 11))
            layout.addWidget(_body(desc))

        layout.addStretch()
        return self._scroll(w)

    def _tab_products(self):
        w = QWidget(); layout = QVBoxLayout(w)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(10)

        layout.addWidget(_title("Ürün Yönetimi", 14))
        layout.addWidget(_body(
            "<b>Ürünler</b> sayfasında ürün kataloğunuzu oluşturun. "
            "Her ürünün kodu, adı, fiyatı, para birimi, stok ve birimi girilir."
        ))
        layout.addWidget(_sep())

        for title, desc in [
            ("Ürün Kodu", "Benzersiz olmalıdır. Teklif tablosunda 'Malzeme Kodu' sütununda görünür."),
            ("Para Birimi", "Her ürünün kendi para birimi olabilir (EUR, USD, TL). "
                           "Teklif oluştururken genel para birimi, listeye eklediğiniz ilk üründen otomatik olarak belirlenir."),
            ("Arama", "Üst arama kutusuna yazınca hem kod hem ada göre anlık filtreleme yapılır."),
            ("Düzenleme", "Satıra çift tıklayın veya seçip Düzenle'ye basın."),
            ("Excel'den İçe Aktarma", "Araçlar menüsünden Excel/CSV dosyasından toplu ürün "
             "aktarımı yapabilirsiniz. Sütun isimleri otomatik eşleştirilir."),
        ]:
            layout.addWidget(_title(f"  {title}", 11))
            layout.addWidget(_body(desc))

        layout.addWidget(_sep())
        layout.addWidget(_title("Müşteri Yönetimi", 14))
        layout.addWidget(_body(
            "<b>Müşteriler</b> sayfasında firma bilgilerini kayıt altına alın."
        ))
        for title, desc in [
            ("Zorunlu Alan", "Sadece <b>Firma Adı</b> zorunludur. Diğer alanlar opsiyoneldir."),
            ("Otomatik Kayıt", "Teklif oluştururken kayıtlı olmayan müşteriyi otomatik "
             "kaydetmeniz önerilir."),
            ("Sütun Genişliği",
             "Tablo başlığına <b>çift tıklayarak</b> sütunu otomatik sığdırabilirsiniz."),
        ]:
            layout.addWidget(_title(f"  {title}", 11))
            layout.addWidget(_body(desc))

        layout.addStretch()
        return self._scroll(w)

    def _tab_pdf(self):
        w = QWidget(); layout = QVBoxLayout(w)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(10)

        layout.addWidget(_title("PDF ve Ayarlar", 14))
        layout.addWidget(_sep())

        for title, desc in [
            ("Şirket Bilgileri",
             "Ayarlar sayfasındaki bilgiler PDF başlığına yansır. "
             "Bir kez doldurun, tüm tekliflerde otomatik kullanılır."),
            ("Logo Yükleme",
             "PNG veya JPG formatında logo yükleyin. PDF'in sol üst köşesinde görünür. "
             "Boyut: yaklaşık 230x115 piksel önerilir."),
            ("Teklif Numarası",
             "Ayarlar'dan <b>Teklif Prefix</b> alanını değiştirerek teklif numarasının "
             "başını özelleştirin. Format: PREFIX-000001. Varsayılan prefix: SNS."),
            ("İmza Alanı",
             "1. ve 2. kişi bilgileri PDF'in alt kısmındaki imza bölümünde görünür. "
             "İmza görseli de yüklenebilir."),
            ("PDF Konumu",
             "Oluşturulan PDF'ler <code>data/offers_pdf/</code> klasörüne kaydedilir."),
            ("Arşivden PDF",
             "Teklifler sayfasında kayıtlı tekliflerin PDF'ini istediğiniz zaman "
             "tekrar oluşturabilirsiniz."),
            ("Yedekleme",
             "Araçlar menüsünden manuel yedekleme yapabilir veya otomatik yedekleme "
             "özelliğini etkinleştirebilirsiniz."),
        ]:
            layout.addWidget(_title(f"  {title}", 11))
            layout.addWidget(_body(desc))

        layout.addStretch()
        return self._scroll(w)

    def _tab_tips(self):
        w = QWidget(); layout = QVBoxLayout(w)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(10)

        layout.addWidget(_title("İpuçları ve Kısayollar", 14))
        layout.addWidget(_sep())
        layout.addSpacing(4)

        tips = [
            ("Çift Tıklama",
             "Tüm tablolarda satıra çift tıklayınca düzenleme penceresi açılır."),
            ("Sütun Genişliği",
             "Tablo başlığının <b>kenarını sürükleyin</b> veya başlığa <b>çift tıklayın</b> "
             "— içeriğe göre otomatik sığar."),
            ("Sağ Tık Menüsü",
             "Herhangi bir tabloda sağ tıklayınca Kopyala, Tümünü Seç, "
             "Sütunu Sığdır seçenekleri çıkar."),
            ("Anlık Arama",
             "Ürünler, Müşteriler ve Teklifler sayfalarındaki arama kutusu "
             "siz yazarken anlık filtreleme yapar."),
            ("Tema Değiştirme",
             "Araçlar menüsünden veya Ctrl+T kısayolu ile açık/koyu tema arasında "
             "geçiş yapılabilir."),
            ("Otomatik Kayıt Yok",
             "Teklif formu kapanınca kaydedilmez. PDF almadan önce mutlaka "
             "<b>Teklifi Kaydet</b> veya <b>Teklifi PDF'e Dönüştür</b> butonuna basın."),
            ("Veri Yedeği",
             "Araçlar > Yedekle/Geri Yükle menüsünden veya Ctrl+B kısayolu ile "
             "yedekleme yapabilirsiniz. Otomatik yedekleme de ayarlanabilir."),
            ("Geçerlilik Takibi",
             "Geçerlilik süresi dolan <b>Beklemede</b> teklifler, Teklifler "
             "sayfası her açıldığında <b>otomatik olarak İptal</b> edilir ve "
             "alt bantta bilgi gösterilir. Onaylandı teklifler etkilenmez.<br>"
             "<b>⚠️</b> Süresi 3 gün içinde dolacak teklifler, teklif "
             "numarasının yanında bu ikonla işaretlenir."),
            ("Kısayollar",
             "Ctrl+T: Tema değiştir, Ctrl+B: Yedekleme, Ctrl+F: Arama, "
             "Ctrl+P: PDF oluştur, Ctrl+E: Düzenle, Ctrl+D: Kopyala, "
             "Delete: Sil, F1: Yardım, Ctrl+H: Hakkında"),
        ]
        for icon_title, desc in tips:
            layout.addWidget(_title(f"{icon_title}", 11))
            layout.addWidget(_body(desc))
            layout.addSpacing(2)

        layout.addStretch()
        return self._scroll(w)


# ── Güncelleme denetleyici (arka plan thread) ─────────────────────────────────

class _UpdateChecker(QThread):
    finished = Signal(str, str)   # (latest_version, error_msg)

    def run(self):
        try:
            url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
            req = urllib.request.Request(url, headers={"User-Agent": f"TeklifApp/{APP_VERSION}"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data   = json.loads(resp.read())
                latest = data.get("tag_name", "").strip()
            self.finished.emit(latest, "")
        except Exception as e:
            self.finished.emit("", str(e))


# ── Hakkında ─────────────────────────────────────────────────────────────────

class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Hakkında")
        self.setFixedSize(520, 480)
        self._checker = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 20)
        layout.setSpacing(10)

        # ── Başlık ────────────────────────────────────────────────────────────
        title = QLabel("Teklif Yönetim Sistemi")
        title.setStyleSheet("font-size:13pt;font-weight:700;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        version_lbl = QLabel(f"Version: {APP_VERSION}")
        version_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_lbl.setObjectName("hint_label")
        layout.addWidget(version_lbl)

        layout.addWidget(_sep())

        # ── Uygulama bilgileri ────────────────────────────────────────────────
        from ui.utils.theme_manager import get_theme
        _t = get_theme()
        _link_color = _t["accent_blue"]

        def _row(label, value, is_link=False, href=None):
            row = QHBoxLayout()
            lbl = QLabel(f"{label}:")
            lbl.setFixedWidth(100)
            lbl.setStyleSheet("font-weight:bold;font-size:9pt;")
            if is_link:
                link_target = href if href else value
                val = QLabel(
                    f'<a style="color:{_link_color};text-decoration:underline;" '
                    f'href="{link_target}">{value}</a>'
                )
                val.setOpenExternalLinks(True)
                val.setTextFormat(Qt.TextFormat.RichText)
                val.setStyleSheet(f"font-size:9pt; color:{_link_color}; text-decoration:underline;")
            else:
                val = QLabel(value)
                val.setStyleSheet("font-size:9pt;")
            val.setWordWrap(True)
            row.addWidget(lbl); row.addWidget(val)
            layout.addLayout(row)

        _row("Geliştirici", "IzzmooPro")
        _row("E-posta",  CONTACT_MAIL, is_link=True, href=f"mailto:{CONTACT_MAIL}")
        _row("GitHub",   GITHUB_URL,   is_link=True)
        _row("Platform", "Windows")
        _row("Teknoloji","Python 3.13 · PySide6 · SQLite · ReportLab")
        _row("Veri",     "Yerel — tüm veriler bilgisayarınızda saklanır")

        layout.addWidget(_sep())

        features = QLabel(
            "<b>Özellikler:</b> 3 adımlı teklif sihirbazı, profesyonel PDF çıktısı, "
            "ürün ve müşteri yönetimi, Excel/CSV içe aktarma, otomatik yedekleme, "
            "açık/koyu tema desteği, teklif numarası özelleştirme (PREFIX-000001)"
        )
        features.setWordWrap(True)
        features.setObjectName("hint_label")
        layout.addWidget(features)

        layout.addStretch()
        layout.addWidget(_sep())

        # ── Alt butonlar ──────────────────────────────────────────────────────
        btn_row = QHBoxLayout()

        self.update_btn = QPushButton("Güncelleme Kontrol Et")
        self.update_btn.setObjectName("secondary")
        self.update_btn.clicked.connect(self._check_update)
        btn_row.addWidget(self.update_btn)

        btn_row.addStretch()

        close_btn = QPushButton("Kapat")
        close_btn.setObjectName("secondary")
        close_btn.setFixedWidth(100)
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)

        layout.addLayout(btn_row)

    def _check_update(self):
        self.update_btn.setEnabled(False)
        self.update_btn.setText("Kontrol ediliyor…")
        self._checker = _UpdateChecker()
        self._checker.finished.connect(self._on_update_result)
        self._checker.start()

    def _on_update_result(self, latest: str, error: str):
        self.update_btn.setEnabled(True)
        self.update_btn.setText("Güncelleme Kontrol Et")
        if error:
            QMessageBox.warning(self, "Bağlantı Hatası",
                                f"Güncelleme kontrol edilemedi:\n{error}")
        elif not latest:
            QMessageBox.information(self, "Bilgi",
                                    "GitHub'da henüz yayınlanmış sürüm bulunamadı.")
        elif not is_newer_version(latest, APP_VERSION):
            QMessageBox.information(self, "Güncel",
                                    f"Uygulama güncel  ({APP_VERSION}) ✓")
        else:
            reply = QMessageBox.question(
                self, "Güncelleme Mevcut",
                f"Yeni sürüm mevcut: {latest}\nMevcut sürümünüz: {APP_VERSION}\n\n"
                f"GitHub'a gitmek ister misiniz?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                import webbrowser
                webbrowser.open(f"{GITHUB_URL}/releases/latest")
