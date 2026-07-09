"""
Ayarlar sayfası — sekmeli düzen: Şirket | Yetkililer | Logo & İmza
"""
import shutil, logging
from pathlib import Path
from ui.widgets._section_card import make_section_card
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit,
    QFileDialog, QMessageBox, QScrollArea, QFrame,
    QTabWidget, QPlainTextEdit
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QPixmap, QPainter, QColor, QPen, QPainterPath, QFont


class _PreviewBox(QWidget):
    """Logo/imza önizleme kutusu — paintEvent ile tema uyumlu arka plan."""
    def __init__(self, text="", parent=None):
        super().__init__(parent)
        self._text = text
        self._pix = None

    def setText(self, t):
        self._text = t
        # Yalnızca gerçek bir yer tutucu metin verildiğinde görseli temizle.
        # Boş metin ("") görseli SİLMEMELİ — setPixmap sonrası çağrılabiliyor.
        if t:
            self._pix = None
        self.update()

    def setPixmap(self, pix):
        self._pix = pix if pix and not pix.isNull() else None
        if self._pix:
            self._text = ""
        self.update()

    def text(self):
        return self._text

    def paintEvent(self, event):
        from ui.utils.theme_manager import get_theme
        ct = get_theme()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.rect().adjusted(1, 1, -1, -1)
        path = QPainterPath()
        path.addRoundedRect(float(r.x()), float(r.y()),
                            float(r.width()), float(r.height()), 6.0, 6.0)
        p.fillPath(path, QColor(ct['bg_input']))
        p.setPen(QPen(QColor(ct['border_input']), 1.0, Qt.PenStyle.DashLine))
        p.drawPath(path)
        if self._pix:
            pw, ph = self._pix.width(), self._pix.height()
            x = (self.width() - pw) // 2
            y = (self.height() - ph) // 2
            p.drawPixmap(x, y, self._pix)
        elif self._text:
            p.setPen(QColor(ct['text_muted']))
            p.setFont(QFont("Segoe UI", 9))
            p.drawText(r, int(Qt.AlignmentFlag.AlignCenter), self._text)
        p.end()

logger = logging.getLogger("settings")
from core.credential_store import get_smtp_password, set_smtp_password, keyring_available
from core.config import load_company_config, save_company_config
from core.app_paths import (
    LOGO_PATH,
    SIG1_PATH,
    SIG2_PATH,
    SIG3_PATH,
    SIG4_PATH,
    DEFAULT_LOGO_PATH,
    LOGO_DISABLED_PATH,
)

SIG_PATHS = (SIG1_PATH, SIG2_PATH, SIG3_PATH, SIG4_PATH)


class SmtpTestWorker(QThread):
    """SMTP bağlantısını arka planda test eder — UI donmaz."""
    result = Signal(bool, str)   # (başarılı, mesaj)

    def __init__(self, cfg: dict):
        super().__init__()
        self.cfg = cfg

    def run(self):
        import smtplib, ssl as _ssl
        from core.credential_store import normalize_smtp_password
        server = self.cfg.get("smtp_server", "").strip()
        port_s = self.cfg.get("smtp_port",   "465").strip()
        user   = self.cfg.get("smtp_user",   "").strip()
        pwd    = normalize_smtp_password(self.cfg.get("smtp_password", ""))

        if not server or not user or not pwd:
            self.result.emit(False, "Sunucu, e-posta ve şifre alanları boş bırakılamaz.")
            return

        port = int(port_s) if port_s.isdigit() else 465
        try:
            if port == 465:
                ctx = _ssl.create_default_context()
                with smtplib.SMTP_SSL(server, port, context=ctx, timeout=10) as smtp:
                    smtp.login(user, pwd)
            else:
                with smtplib.SMTP(server, port, timeout=10) as smtp:
                    smtp.ehlo()
                    smtp.starttls()
                    smtp.login(user, pwd)
            self.result.emit(True, f"Bağlantı başarılı!  ({server}:{port})")
        except smtplib.SMTPAuthenticationError:
            self.result.emit(False,
                "Kimlik doğrulama başarısız.\n"
                "Gmail kullanıyorsanız 'Uygulama Şifresi (App Password)' oluşturun.")
        except TimeoutError:
            self.result.emit(False,
                f"Bağlantı zaman aşımı (10 sn).\nSunucu adresi ve portu kontrol edin.")
        except Exception as e:
            self.result.emit(False, str(e))


def _inp(ph="", tip="", w=None) -> QLineEdit:
    le = QLineEdit()
    le.setPlaceholderText(ph)
    le.setMinimumHeight(34)
    if tip: le.setToolTip(tip)
    if w:   le.setFixedWidth(w)
    return le


def _lbl(text: str) -> QLabel:
    l = QLabel(text)
    l.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    l.setMinimumWidth(90)
    return l


class SettingsPage(QWidget):
    def __init__(self):
        super().__init__()
        self._loaded_prefix = "SNS"
        self._build_ui()
        self._load()
        self._snapshot = self._current_values()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Başlık çubuğu ─────────────────────────────────────────────────
        hdr = QFrame()
        hdr.setObjectName("toolbar")
        hdr.setFixedHeight(64)
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(16, 12, 16, 12)
        t = QLabel("Ayarlar")
        t.setStyleSheet("font-size:14pt;font-weight:700;")
        hl.addWidget(t); hl.addStretch()

        reset_btn = QPushButton("Varsayılana Dön")
        reset_btn.setObjectName("secondary")
        reset_btn.setFixedHeight(40)
        reset_btn.setToolTip("Şirket bilgileri ve PDF metinlerini fabrika ayarlarına sıfırlar")
        reset_btn.clicked.connect(self._reset_to_defaults)
        hl.addWidget(reset_btn)
        hl.addSpacing(8)

        self.save_btn = QPushButton("Kaydet")
        self.save_btn.setObjectName("primary")
        self.save_btn.setFixedHeight(40)
        self.save_btn.setToolTip("Şirket bilgilerini ve teklif önekini kaydeder.\nLogo ve imza görselleri yüklenince otomatik kaydedilir.")
        self.save_btn.clicked.connect(self._save)
        hl.addWidget(self.save_btn)
        root.addWidget(hdr)

        # ── Sekmeler ──────────────────────────────────────────────────────
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        root.addWidget(self.tabs)

        # Sekme sırası: Şirket → Yetkililer → Logo & İmza → PDF Ayarları
        self.tabs.addTab(self._tab_company(),   "Şirket")
        self.tabs.addTab(self._tab_persons(),   "Yetkililer")
        self.tabs.addTab(self._tab_visuals(),   "Logo ve İmza")
        self.tabs.addTab(self._tab_email(),     "E-Posta Ayarları")
        self.tabs.addTab(self._tab_pdf_texts(), "PDF Ayarları")

    # ══════════════════════════════════════════════════════════════════════
    # SEKME 1 — Şirket Bilgileri
    # ══════════════════════════════════════════════════════════════════════
    def _tab_company(self) -> QWidget:
        page, lay = self._scrolled_page()

        box, g = make_section_card("Şirket Bilgileri")
        g.setColumnStretch(1, 1); g.setColumnStretch(3, 1)

        self.f_name    = _inp("")
        self.f_address = _inp("")
        self.f_tel     = _inp("")
        self.f_fax     = _inp("")
        self.f_mail    = _inp("")
        self.f_web     = _inp("")

        g.addWidget(_lbl("Şirket Adı:"),  0, 0); g.addWidget(self.f_name,    0, 1, 1, 3)
        g.addWidget(_lbl("Adres:"),        1, 0); g.addWidget(self.f_address,  1, 1, 1, 3)
        g.addWidget(_lbl("Tel:"),          2, 0); g.addWidget(self.f_tel,      2, 1)
        g.addWidget(_lbl("Fax:"),          2, 2); g.addWidget(self.f_fax,      2, 3)
        g.addWidget(_lbl("E-Posta:"),      3, 0); g.addWidget(self.f_mail,     3, 1)
        g.addWidget(_lbl("Web:"),          3, 2); g.addWidget(self.f_web,      3, 3)
        lay.addWidget(box)

        lay.addStretch()
        return page

    # ══════════════════════════════════════════════════════════════════════
    # SEKME 2 — Yetkili Bilgileri
    # ══════════════════════════════════════════════════════════════════════
    MAX_PERSONS = 4

    def _tab_persons(self) -> QWidget:
        page, lay = self._scrolled_page()

        self._person_cards = []
        for i in range(1, self.MAX_PERSONS + 1):
            box, g = make_section_card(f"{i}. Yetkili")
            g.setColumnStretch(1, 1); g.setColumnStretch(3, 1)
            name_f  = _inp("Ad Soyad")
            title_f = _inp("Unvan / Görev")
            email_f = _inp("ad.soyad@sirket.com.tr")
            setattr(self, f"f_s{i}_name",  name_f)
            setattr(self, f"f_s{i}_title", title_f)
            setattr(self, f"f_s{i}_email", email_f)
            g.addWidget(_lbl("Ad Soyad:"), 0, 0); g.addWidget(name_f,  0, 1)
            g.addWidget(_lbl("Unvan:"),    0, 2); g.addWidget(title_f, 0, 3)
            g.addWidget(_lbl("E-Posta:"),  1, 0); g.addWidget(email_f, 1, 1, 1, 3)
            if i >= 2:
                btn_rm = QPushButton("Bu Yetkiliyi Kaldır")
                btn_rm.setObjectName("danger")
                btn_rm.clicked.connect(lambda _, idx=i: self._remove_person(idx))
                g.addWidget(btn_rm, 2, 3,
                            alignment=Qt.AlignmentFlag.AlignRight)
            lay.addWidget(box)
            self._person_cards.append(box)

        add_row = QHBoxLayout()
        btn_add = QPushButton("+ Yetkili Ekle")
        btn_add.setObjectName("secondary")
        btn_add.setToolTip(f"En fazla {self.MAX_PERSONS} yetkili eklenebilir.")
        btn_add.clicked.connect(self._add_person)
        add_row.addWidget(btn_add); add_row.addStretch()
        lay.addLayout(add_row)

        note = QLabel("Bu bilgiler PDF teklifin imza alanında sırayla görünür — "
                      "1. Yetkili ↔ İmza 1, 2. Yetkili ↔ İmza 2 (Logo ve İmza sekmesi).")
        note.setObjectName("hint_label")
        lay.addWidget(note)
        lay.addStretch()
        return page

    def _person_has_data(self, i: int) -> bool:
        return any(getattr(self, f"f_s{i}_{k}").text().strip()
                   for k in ("name", "title", "email"))

    def _sync_person_cards(self):
        """1. kart hep görünür; 2-4 dolu ise veya elle eklendiyse görünür."""
        for i in range(2, self.MAX_PERSONS + 1):
            card = self._person_cards[i - 1]
            if self._person_has_data(i):
                card.setVisible(True)
            elif not getattr(card, "_user_added", False):
                card.setVisible(False)

    def _add_person(self):
        for i in range(2, self.MAX_PERSONS + 1):
            card = self._person_cards[i - 1]
            if not card.isVisible():
                card._user_added = True
                card.setVisible(True)
                getattr(self, f"f_s{i}_name").setFocus()
                return
        QMessageBox.warning(
            self, "Sınır",
            f"En fazla {self.MAX_PERSONS} yetkili eklenebilir.")

    def _remove_person(self, i: int):
        for k in ("name", "title", "email"):
            getattr(self, f"f_s{i}_{k}").clear()
        card = self._person_cards[i - 1]
        card._user_added = False
        card.setVisible(False)

    def _person_values(self) -> dict:
        vals = {}
        for i in range(1, self.MAX_PERSONS + 1):
            vals[f"sales_person{i}_name"]  = getattr(self, f"f_s{i}_name").text().strip()
            vals[f"sales_person{i}_title"] = getattr(self, f"f_s{i}_title").text().strip()
            vals[f"sales_person{i}_email"] = getattr(self, f"f_s{i}_email").text().strip()
        return vals

    # ══════════════════════════════════════════════════════════════════════
    # SEKME 3 — Logo & İmza Görselleri
    # ══════════════════════════════════════════════════════════════════════
    def _tab_visuals(self) -> QWidget:
        page, lay = self._scrolled_page()

        # ── LOGO KARTI ────────────────────────────────────────────────────
        logo_card = QFrame()
        logo_card.setObjectName("section_card")
        logo_vbox = QVBoxLayout(logo_card)
        logo_vbox.setContentsMargins(0, 0, 0, 0)
        logo_vbox.setSpacing(0)

        logo_hdr = QFrame(logo_card)
        logo_hdr.setFixedHeight(44)
        logo_hdr.setObjectName("transparent_frame")
        logo_hl = QHBoxLayout(logo_hdr)
        logo_hl.setContentsMargins(16, 0, 16, 0)
        logo_title = QLabel("Logo  (PDF sol üst köşe)")
        logo_title.setObjectName("section_card_title")
        logo_title.setStyleSheet("font-size:10pt;font-weight:700;background:transparent;")
        logo_hl.addWidget(logo_title)
        logo_hl.addStretch()
        logo_vbox.addWidget(logo_hdr)

        logo_sep = QFrame(logo_card)
        logo_sep.setObjectName("section_divider")
        logo_sep.setFrameShape(QFrame.Shape.HLine)
        logo_sep.setFixedHeight(2)
        logo_vbox.addWidget(logo_sep)

        logo_body = QFrame(logo_card)
        logo_body.setObjectName("transparent_frame")
        logo_row = QHBoxLayout(logo_body)
        logo_row.setContentsMargins(16, 16, 16, 16)
        logo_row.setSpacing(24)

        self.logo_preview = self._make_preview("Logo Yok\n(Yükleyin)", 240, 110)
        logo_row.addWidget(self.logo_preview)

        logo_btn_frame = QFrame(logo_body)
        logo_btn_frame.setObjectName("transparent_frame")
        logo_btn_col = QVBoxLayout(logo_btn_frame)
        logo_btn_col.setContentsMargins(0, 0, 0, 0)
        logo_btn_col.setSpacing(8)
        logo_btn_col.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.b_logo = QPushButton(logo_btn_frame)
        self.b_logo.setObjectName("secondary")
        self.b_logo.setFixedSize(120, 34)
        self._sync_logo_btn()
        logo_hint = QLabel("PNG / JPG\nÖnerilen: 230 × 50 px", logo_btn_frame)
        logo_hint.setObjectName("hint_label")

        logo_btn_col.addWidget(self.b_logo)
        logo_btn_col.addSpacing(4)
        logo_btn_col.addWidget(logo_hint)

        self.b_logo.clicked.connect(self._toggle_logo)

        logo_row.addWidget(logo_btn_frame)
        logo_row.addStretch()
        logo_vbox.addWidget(logo_body)
        lay.addWidget(logo_card)

        # ── İMZA KARTI ────────────────────────────────────────────────────
        sig_card = QFrame()
        sig_card.setObjectName("section_card")
        sig_vbox = QVBoxLayout(sig_card)
        sig_vbox.setContentsMargins(0, 0, 0, 0)
        sig_vbox.setSpacing(0)

        sig_hdr = QFrame(sig_card)
        sig_hdr.setFixedHeight(44)
        sig_hdr.setObjectName("transparent_frame")
        sig_hl = QHBoxLayout(sig_hdr)
        sig_hl.setContentsMargins(16, 0, 16, 0)
        sig_title = QLabel("İmza Görselleri  (PDF imza alanı, önerilen: 200 × 80 px)")
        sig_title.setObjectName("section_card_title")
        sig_title.setStyleSheet("font-size:10pt;font-weight:700;background:transparent;")
        sig_hl.addWidget(sig_title)
        sig_hl.addStretch()
        sig_vbox.addWidget(sig_hdr)

        sig_sep = QFrame(sig_card)
        sig_sep.setObjectName("section_divider")
        sig_sep.setFrameShape(QFrame.Shape.HLine)
        sig_sep.setFixedHeight(2)
        sig_vbox.addWidget(sig_sep)

        sig_body = QFrame(sig_card)
        sig_body.setObjectName("transparent_frame")
        from PySide6.QtWidgets import QGridLayout
        sig_row = QGridLayout(sig_body)
        sig_row.setContentsMargins(16, 16, 16, 16)
        sig_row.setHorizontalSpacing(40)
        sig_row.setVerticalSpacing(16)

        _sig_defs = [(SIG_PATHS[i - 1], f"sig{i}_preview", f"b_sig{i}",
                      f"İmza {i} Yok") for i in range(1, 5)]
        for _idx, (path, attr, btn_attr, placeholder) in enumerate(_sig_defs):
            cell_frame = QFrame(sig_body)
            cell_frame.setObjectName("transparent_frame")
            cell_col = QVBoxLayout(cell_frame)
            cell_col.setContentsMargins(0, 0, 0, 0)
            cell_col.setSpacing(8)

            prev = self._make_preview(placeholder, 240, 110)
            setattr(self, attr, prev)
            cell_col.addWidget(prev)

            btn_frame = QFrame(cell_frame)
            btn_frame.setObjectName("transparent_frame")
            btn_row = QHBoxLayout(btn_frame)
            btn_row.setContentsMargins(0, 0, 0, 0)
            btn_row.setSpacing(8)

            b = QPushButton(btn_frame)
            b.setObjectName("secondary")
            b.setFixedSize(120, 34)
            self._sync_img_btn(b, path)
            setattr(self, btn_attr, b)
            b.clicked.connect(lambda _, p=path, pv=prev, d=placeholder, bt=b:
                              self._toggle_img(p, pv, d, bt))
            btn_row.addWidget(b)
            btn_row.addStretch()

            cell_col.addWidget(btn_frame)
            sig_row.addWidget(cell_frame, _idx // 2, _idx % 2)

        sig_row.setColumnStretch(2, 1)
        sig_vbox.addWidget(sig_body)
        lay.addWidget(sig_card)

        lay.addStretch()
        return page

    # ══════════════════════════════════════════════════════════════════════
    # SEKME 4 — E-Posta Ayarları
    # ══════════════════════════════════════════════════════════════════════
    def _tab_email(self) -> QWidget:
        page, lay = self._scrolled_page()

        box, g = make_section_card("SMTP Sunucu Ayarları")
        g.setColumnStretch(1, 1); g.setColumnStretch(3, 1)

        self.f_smtp_server = _inp("Örn: smtp.gmail.com")
        self.f_smtp_port   = _inp("Örn: 465 (SSL) veya 587 (TLS)")
        self.f_smtp_user   = _inp("E-Posta Adresiniz")
        self.f_smtp_pass   = _inp("Şifre veya Uygulama Şifresi")
        self.f_smtp_pass.setEchoMode(QLineEdit.EchoMode.Password)

        pwd_row = QHBoxLayout()
        pwd_row.setSpacing(4)
        pwd_row.addWidget(self.f_smtp_pass, 1)
        self._btn_toggle_pwd = QPushButton("Göster")
        self._btn_toggle_pwd.setObjectName("secondary")
        self._btn_toggle_pwd.setFixedHeight(34)
        self._btn_toggle_pwd.setMinimumWidth(72)
        self._btn_toggle_pwd.setToolTip("Şifreyi göster/gizle")
        self._btn_toggle_pwd.setCheckable(True)
        self._btn_toggle_pwd.toggled.connect(self._toggle_password_visibility)
        pwd_row.addWidget(self._btn_toggle_pwd)
        pwd_widget = QWidget()
        pwd_widget.setLayout(pwd_row)

        g.addWidget(_lbl("Sunucu:"),  0, 0); g.addWidget(self.f_smtp_server, 0, 1)
        g.addWidget(_lbl("Port:"),    0, 2); g.addWidget(self.f_smtp_port,   0, 3)
        g.addWidget(_lbl("E-Posta:"), 1, 0); g.addWidget(self.f_smtp_user,   1, 1, 1, 3)
        g.addWidget(_lbl("Şifre:"),   2, 0); g.addWidget(pwd_widget,         2, 1, 1, 3)

        note = QLabel("Gmail veya Outlook gibi servisler üzerinden otomatik PDF yollayabilmek için SMTP ayarlarını girin.\nGüvenlik açısından 'Uygulama Şifresi (App Password)' oluşturarak kullanmanız önerilir.")
        note.setObjectName("hint_label")
        note.setWordWrap(True)
        g.addWidget(note, 3, 1, 1, 3)

        # ── SMTP Test Butonu ──────────────────────────────────────────────
        self.b_smtp_test = QPushButton("Bağlantıyı Test Et")
        self.b_smtp_test.setObjectName("secondary")
        self.b_smtp_test.setFixedHeight(44)
        self.b_smtp_test.setMinimumWidth(180)
        self.b_smtp_test.clicked.connect(self._test_smtp)

        self.lbl_smtp_result = QLabel("")
        self.lbl_smtp_result.setWordWrap(True)
        self.lbl_smtp_result.setMinimumHeight(20)

        g.addWidget(self.b_smtp_test,     4, 1, 1, 1)
        g.addWidget(self.lbl_smtp_result, 5, 1, 1, 3)

        lay.addWidget(box)
        lay.addStretch()
        return page

    # ══════════════════════════════════════════════════════════════════════
    # SEKME 5 — PDF Ayarları (sabit metinler)
    # ══════════════════════════════════════════════════════════════════════
    def _tab_pdf_texts(self) -> QWidget:
        page, lay = self._scrolled_page()

        # ── Teklif Numarası — diğer PDF ayar satırlarıyla aynı kalıp ──────
        no_frame = QFrame()
        no_frame.setObjectName("section_card")
        nl = QVBoxLayout(no_frame)
        nl.setContentsMargins(14, 8, 14, 8)
        nl.setSpacing(4)

        no_header = QHBoxLayout()
        no_header.setSpacing(8)
        no_title = QLabel("Teklif Numarası Öneki (Prefix)")
        no_title.setStyleSheet("font-weight:700; font-size:9pt;")
        no_title.setToolTip("Teklif numarası başı — Örnek: SNS → SNS-000001")
        no_header.addWidget(no_title)
        no_header.addStretch()
        no_note = QLabel("Format:  PREFIX-000001")
        no_note.setObjectName("hint_label")
        no_header.addWidget(no_note)
        nl.addLayout(no_header)

        self.f_prefix = _inp("SNS",
            "Teklif numarası başı — Örnek: SNS → SNS-000001")
        nl.addWidget(self.f_prefix)
        lay.addWidget(no_frame)

        # PDF'deki görünüm sırasına göre: yukarıdan aşağıya
        fields = [
            ("pdf_giris_metni",  "Giriş Metni",
             "Müşteri bilgilerinden hemen sonra görünen açılış paragrafı."),
            ("pdf_iskonto",      "İskonto — Şartlar tablosu",
             "Ürün tablosunun üstündeki şartlar bölümü — iskonto satırı."),
            ("pdf_teslim_yeri",  "Teslim Yeri — Şartlar tablosu",
             "Ürün tablosunun üstündeki şartlar bölümü — teslim yeri satırı."),
            ("pdf_kur_notu",     "Döviz Kur Notu — İmza alanı üstü",
             "İmza alanı üstünde, döviz kuruna dair uyarı metni."),
            ("pdf_kdv_notu",     "KDV Notu — İmza alanı üstü",
             "İmza alanı üstünde, KDV'ye dair uyarı metni."),
            ("pdf_onay_metni",   "Müşteri Onay Metni — İmza alanı altı",
             "İmza alanı altında, müşterinin onayladığını belirten metin."),
            ("pdf_teslim_notu",  "Teslim Süresi Notu — Alt bilgi",
             "PDF'nin en altındaki kırmızı uyarı notu."),
            ("pdf_iptal_notu",   "İptal / İade Notu — Alt bilgi",
             "PDF'nin en altındaki iptal/iade koşulu metni."),
        ]

        from PySide6.QtWidgets import QCheckBox
        self._pdf_toggles = {}

        for attr, title, hint in fields:
            row_frame = QFrame()
            row_frame.setObjectName("section_card")
            rl = QVBoxLayout(row_frame)
            rl.setContentsMargins(14, 8, 14, 8)
            rl.setSpacing(4)

            header = QHBoxLayout()
            header.setSpacing(8)
            title_lbl = QLabel(title)
            title_lbl.setStyleSheet("font-weight:700; font-size:9pt;")
            title_lbl.setToolTip(hint)
            header.addWidget(title_lbl)
            header.addStretch()
            chk = QCheckBox("PDF'de göster")
            chk.setChecked(True)
            chk.setToolTip("Kapalıysa bu metin PDF'de görünmez.")
            self._pdf_toggles[attr] = chk
            header.addWidget(chk)
            rl.addLayout(header)

            te = QPlainTextEdit()
            te.setMinimumHeight(36)
            te.setMaximumHeight(44)
            te.setPlaceholderText(hint)
            te.setToolTip(hint)
            chk.toggled.connect(lambda checked, w=te: w.setEnabled(checked))
            setattr(self, attr, te)
            rl.addWidget(te)

            lay.addWidget(row_frame)
        lay.addStretch()
        return page

    # ── Yardımcılar ──────────────────────────────────────────────────────

    def _scrolled_page(self):
        """Scroll içine sarılmış sayfa + içerik layout'u döner."""
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(scroll)
        w = QWidget(); scroll.setWidget(w)
        lay = QVBoxLayout(w)
        lay.setContentsMargins(16, 20, 16, 16); lay.setSpacing(20)
        return page, lay

    def _make_preview(self, text, w, h):
        box = _PreviewBox(text)
        box.setFixedSize(w, h)
        box._inner_label = box
        return box

    def _upload(self, dest: Path, preview: QLabel, placeholder: str):
        path, _ = QFileDialog.getOpenFileName(
            self, "Görsel Seç", "", "Resim (*.png *.jpg *.jpeg *.bmp)")
        if not path: return
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, str(dest))
            self._set_preview(preview, dest)
            QMessageBox.information(self, "Yüklendi", "Görsel başarıyla yüklendi.")
        except Exception as e:
            QMessageBox.warning(self, "Hata", f"Yüklenemedi:\n{e}")

    def _remove(self, dest: Path, preview, placeholder: str):
        try:
            if dest.exists():
                dest.unlink()
        except Exception as e:
            QMessageBox.warning(self, "Hata", f"Görsel kaldırılamadı:\n{e}")
            return
        self._preview_label(preview).setPixmap(QPixmap())
        self._preview_label(preview).setText(placeholder)
        QMessageBox.information(self, "Kaldırıldı", "Görsel kaldırıldı.")

    def _toggle_img(self, dest: Path, preview: QLabel, placeholder: str, btn: QPushButton):
        """Dosya varsa kaldır, yoksa yükle; ardından butonu güncelle."""
        if dest.exists():
            self._remove(dest, preview, placeholder)
        else:
            self._upload(dest, preview, placeholder)
        self._sync_img_btn(btn, dest)

    def _sync_img_btn(self, btn: QPushButton, dest: Path):
        """Dosya durumuna göre buton metnini günceller."""
        btn.setText("Kaldır" if dest.exists() else "Yükle")

    def _toggle_logo(self):
        """Logo için özel toggle: varsayılan logo desteği + kaldırma işaret dosyası."""
        logo_active = not LOGO_DISABLED_PATH.exists() and (
            LOGO_PATH.exists() or DEFAULT_LOGO_PATH.exists())
        if logo_active:
            # Aktif → kaldır (disabled marker oluştur, özel logo varsa sil)
            if LOGO_PATH.exists():
                try:
                    LOGO_PATH.unlink()
                except Exception as e:
                    QMessageBox.warning(self, "Hata", f"Logo kaldırılamadı:\n{e}")
                    return
            try:
                LOGO_DISABLED_PATH.touch()
            except OSError as e:
                logger.warning("Logo disabled marker oluşturulamadı: %s", e)
            self._preview_label(self.logo_preview).setPixmap(QPixmap())
            self._preview_label(self.logo_preview).setText("Logo Yok\n(Yükleyin)")
            QMessageBox.information(self, "Kaldırıldı", "Logo PDF'den kaldırıldı.")
        else:
            # Kaldırılmış → yükle (disabled marker'ı da temizle)
            self._upload(LOGO_PATH, self.logo_preview, "Logo Yok\n(Yükleyin)")
            if LOGO_PATH.exists() and LOGO_DISABLED_PATH.exists():
                try:
                    LOGO_DISABLED_PATH.unlink()
                except OSError as e:
                    logger.warning("Logo disabled marker silinemedi: %s", e)
        self._sync_logo_btn()

    def _sync_logo_btn(self):
        """Logo butonunun metnini mevcut duruma göre günceller."""
        logo_active = not LOGO_DISABLED_PATH.exists() and (
            LOGO_PATH.exists() or DEFAULT_LOGO_PATH.exists())
        self.b_logo.setText("Kaldır" if logo_active else "Yükle")

    def _set_preview(self, container, path: Path):
        lbl = getattr(container, '_inner_label', container)
        if path.exists():
            pix = QPixmap(str(path))
            if not pix.isNull():
                w = container.width()  or container.minimumWidth()  or 236
                h = container.height() or container.minimumHeight() or 106
                lbl.setPixmap(pix.scaled(
                    max(1, w - 4), max(1, h - 4),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation))
            else:
                lbl.setPixmap(QPixmap())
        else:
            lbl.setPixmap(QPixmap())

    def _preview_label(self, container):
        return getattr(container, '_inner_label', container)

    def _refresh_previews(self):
        # Logo: özel logo > varsayılan logo > yok
        if LOGO_DISABLED_PATH.exists():
            self._preview_label(self.logo_preview).setPixmap(QPixmap())
            self._preview_label(self.logo_preview).setText("Logo Yok\n(Yükleyin)")
        elif LOGO_PATH.exists():
            self._set_preview(self.logo_preview, LOGO_PATH)
        elif DEFAULT_LOGO_PATH.exists():
            self._set_preview(self.logo_preview, DEFAULT_LOGO_PATH)
        else:
            self._preview_label(self.logo_preview).setText("Logo Yok\n(Yükleyin)")
        self._sync_logo_btn()

        for i, sig_path in enumerate(SIG_PATHS, 1):
            prev = getattr(self, f"sig{i}_preview")
            self._set_preview(prev, sig_path)
            if not sig_path.exists():
                self._preview_label(prev).setText(f"İmza {i} Yok")
            self._sync_img_btn(getattr(self, f"b_sig{i}"), sig_path)

    # ── Veri ─────────────────────────────────────────────────────────────

    def _load(self):
        cfg = load_company_config()
        self._loaded_prefix = cfg.get("offer_prefix", "SNS")
        self.f_name.setText(cfg.get("name", ""))
        self.f_address.setText(cfg.get("address", ""))
        self.f_tel.setText(cfg.get("tel", ""))
        self.f_fax.setText(cfg.get("fax", ""))
        self.f_mail.setText(cfg.get("mail", ""))
        self.f_web.setText(cfg.get("web", ""))
        self.f_prefix.setText(cfg.get("offer_prefix", "SNS"))
        for i in range(1, self.MAX_PERSONS + 1):
            getattr(self, f"f_s{i}_name").setText(cfg.get(f"sales_person{i}_name", ""))
            getattr(self, f"f_s{i}_title").setText(cfg.get(f"sales_person{i}_title", ""))
            getattr(self, f"f_s{i}_email").setText(cfg.get(f"sales_person{i}_email", ""))
        self._sync_person_cards()
        self.f_smtp_server.setText(cfg.get("smtp_server", ""))
        self.f_smtp_port.setText(cfg.get("smtp_port", "465"))
        self.f_smtp_user.setText(cfg.get("smtp_user", ""))
        # Şifre: önce güvenli depodan oku
        smtp_pw = get_smtp_password()
        # Eski sürümlerde cfg'ye kaydedilmişse bir kez keyring'e taşı
        if not smtp_pw and cfg.get("smtp_password"):
            smtp_pw = cfg["smtp_password"]
            set_smtp_password(smtp_pw)
            logger.info("SMTP şifresi keyring'e taşındı.")
        self.f_smtp_pass.setText(smtp_pw)
        # PDF metinleri (PDF sırasına göre)
        for key in ("pdf_giris_metni", "pdf_iskonto", "pdf_teslim_yeri",
                    "pdf_kur_notu", "pdf_kdv_notu", "pdf_onay_metni",
                    "pdf_teslim_notu", "pdf_iptal_notu"):
            getattr(self, key).setPlainText(cfg.get(key, ""))
            if key in self._pdf_toggles:
                enabled = cfg.get(f"{key}_enabled", "1") != "0"
                self._pdf_toggles[key].setChecked(enabled)
                getattr(self, key).setEnabled(enabled)
        self._refresh_previews()

    def _save(self):
        new_prefix = self.f_prefix.text().strip() or "SNS"
        try:
            save_company_config({
            "name":    self.f_name.text().strip(),
            "address": self.f_address.text().strip(),
            "tel":     self.f_tel.text().strip(),
            "fax":     self.f_fax.text().strip(),
            "mail":    self.f_mail.text().strip(),
            "web":     self.f_web.text().strip(),
            "offer_prefix": new_prefix,
            **self._person_values(),
            "smtp_server":         self.f_smtp_server.text().strip(),
            "smtp_port":           self.f_smtp_port.text().strip(),
            "smtp_user":           self.f_smtp_user.text().strip(),
            # PDF sabit metinler (PDF sırasına göre)
            "pdf_giris_metni": self.pdf_giris_metni.toPlainText().strip(),
            "pdf_iskonto":     self.pdf_iskonto.toPlainText().strip(),
            "pdf_teslim_yeri": self.pdf_teslim_yeri.toPlainText().strip(),
            "pdf_kur_notu":    self.pdf_kur_notu.toPlainText().strip(),
            "pdf_kdv_notu":    self.pdf_kdv_notu.toPlainText().strip(),
            "pdf_onay_metni":  self.pdf_onay_metni.toPlainText().strip(),
            "pdf_teslim_notu": self.pdf_teslim_notu.toPlainText().strip(),
            "pdf_iptal_notu":  self.pdf_iptal_notu.toPlainText().strip(),
            # PDF görünürlük toggle'ları
            **{f"{k}_enabled": "1" if chk.isChecked() else "0"
               for k, chk in self._pdf_toggles.items()},
        })
        except Exception as e:
            QMessageBox.critical(self, "Kaydetme Hatası", f"Ayarlar kaydedilemedi:\n{e}")
            return
        # SMTP şifresini güvenli depoya kaydet
        set_smtp_password(self.f_smtp_pass.text().strip())
        msg = "Ayarlar kaydedildi.\nBundan sonra oluşturulan PDF tekliflere yansır."
        if self._loaded_prefix and self._loaded_prefix != new_prefix:
            msg += (f"\n\nDikkat: Teklif Öneki '{self._loaded_prefix}' → '{new_prefix}' olarak değiştirildi."
                    "\nMevcut tekliflerin numaraları değişmez, yalnızca yeni tekliflere uygulanır.")
        self._loaded_prefix = new_prefix
        self._snapshot = self._current_values()
        QMessageBox.information(self, "Kaydedildi", msg)

    def on_enter(self):
        # Snapshot burada YENİLENMEZ — kaydedilmemiş değişiklikler
        # sayfadan çıkıp dönünce de "kirli" sayılmaya devam etmeli.
        self._refresh_previews()

    def _toggle_password_visibility(self, checked: bool):
        self.f_smtp_pass.setEchoMode(
            QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password)
        self._btn_toggle_pwd.setText("Gizle" if checked else "Göster")

    def _current_values(self) -> dict:
        """Tüm form alanlarının mevcut değerlerini dict olarak döndür."""
        vals = {
            "name": self.f_name.text().strip(),
            "address": self.f_address.text().strip(),
            "tel": self.f_tel.text().strip(),
            "fax": self.f_fax.text().strip(),
            "mail": self.f_mail.text().strip(),
            "web": self.f_web.text().strip(),
            "offer_prefix": self.f_prefix.text().strip(),
            **self._person_values(),
            "smtp_server": self.f_smtp_server.text().strip(),
            "smtp_port": self.f_smtp_port.text().strip(),
            "smtp_user": self.f_smtp_user.text().strip(),
            "smtp_pass": self.f_smtp_pass.text().strip(),
        }
        for key in ("pdf_giris_metni", "pdf_iskonto", "pdf_teslim_yeri",
                    "pdf_kur_notu", "pdf_kdv_notu", "pdf_onay_metni",
                    "pdf_teslim_notu", "pdf_iptal_notu"):
            vals[key] = getattr(self, key).toPlainText().strip()
        return vals

    def is_dirty(self) -> bool:
        """Kaydedilmemiş değişiklik var mı?"""
        if not hasattr(self, '_snapshot'):
            return False
        return self._current_values() != self._snapshot

    def _reset_to_defaults(self):
        """Tüm ayarları fabrika değerlerine döndür."""
        from core.config import _DEFAULTS
        ans = QMessageBox.question(
            self, "Varsayılana Dön",
            "Tüm şirket bilgileri ve PDF metinleri varsayılan değerlere sıfırlansın mı?\n\n"
            "Logo, imza ve SMTP ayarları etkilenmez.\n"
            "Bu işlem geri alınamaz.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if ans != QMessageBox.StandardButton.Yes:
            return
        self.f_name.setText(_DEFAULTS.get("name", ""))
        self.f_address.setText(_DEFAULTS.get("address", ""))
        self.f_tel.setText(_DEFAULTS.get("tel", ""))
        self.f_fax.setText(_DEFAULTS.get("fax", ""))
        self.f_mail.setText(_DEFAULTS.get("mail", ""))
        self.f_web.setText(_DEFAULTS.get("web", ""))
        self.f_prefix.setText(_DEFAULTS.get("offer_prefix", "SNS"))
        for key in ("pdf_giris_metni", "pdf_iskonto", "pdf_teslim_yeri",
                    "pdf_kur_notu", "pdf_kdv_notu", "pdf_onay_metni",
                    "pdf_teslim_notu", "pdf_iptal_notu"):
            getattr(self, key).setPlainText(_DEFAULTS.get(key, ""))
            if key in self._pdf_toggles:
                self._pdf_toggles[key].setChecked(True)
                getattr(self, key).setEnabled(True)

    # ── SMTP Test ─────────────────────────────────────────────────────────────
    def _test_smtp(self):
        """Mevcut SMTP ayarlarını arka planda test eder."""
        from core.credential_store import get_smtp_password
        cfg = {
            "smtp_server":   self.f_smtp_server.text().strip(),
            "smtp_port":     self.f_smtp_port.text().strip(),
            "smtp_user":     self.f_smtp_user.text().strip(),
            "smtp_password": self.f_smtp_pass.text().strip() or get_smtp_password(),
        }
        if not cfg["smtp_server"] or not cfg["smtp_user"]:
            from ui.utils.theme_manager import get_theme
            self.lbl_smtp_result.setStyleSheet(f"color:{get_theme()['accent_red']};")
            self.lbl_smtp_result.setText("Sunucu ve e-posta adresi girilmeli.")
            return

        self.b_smtp_test.setEnabled(False)
        self.b_smtp_test.setText("Test ediliyor…")
        from ui.utils.theme_manager import get_theme
        self.lbl_smtp_result.setStyleSheet(f"color:{get_theme()['text_muted']};")
        self.lbl_smtp_result.setText("Bağlanıyor…")

        self._smtp_worker = SmtpTestWorker(cfg)
        self._smtp_worker.result.connect(self._on_smtp_test_result)
        self._smtp_worker.start()

    def _on_smtp_test_result(self, success: bool, message: str):
        from ui.utils.theme_manager import get_theme
        t = get_theme()
        self.b_smtp_test.setEnabled(True)
        self.b_smtp_test.setText("Bağlantıyı Test Et")
        if success:
            self.lbl_smtp_result.setStyleSheet(f"color:{t['accent_green']};font-weight:600;")
            self.lbl_smtp_result.setText(message)
        else:
            self.lbl_smtp_result.setStyleSheet(f"color:{t['accent_red']};")
            self.lbl_smtp_result.setText(message)
