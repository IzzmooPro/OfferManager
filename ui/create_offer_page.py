"""
Teklif oluşturma — 3 adımlı wizard.
Adım 1: Müşteri  |  Adım 2: Ürünler  |  Adım 3: Özet + PDF Önizleme
"""
import logging, datetime, os
from pathlib import Path

from ui._section_card import make_section_card
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QLineEdit, QComboBox,
    QMessageBox, QHeaderView, QFrame, QDialog, QDoubleSpinBox,
    QGridLayout, QGroupBox, QAbstractItemView, QStackedWidget,
    QScrollArea, QFileDialog
)
from PySide6.QtCore import Qt, Signal
from services.customer_service import CustomerService
from services.product_service import ProductService
from services.offer_service import OfferService
from models.customer import Customer

logger = logging.getLogger("create_offer")
from constants import SYM_MAP

UNITS = ["Adet", "Metre", "Kg", "Litre", "Paket", "Kutu", "Set", "Takım",
         "Rulo", "Ton", "M²", "M³", "Cm", "Mm"]
DELIVERIES = ["Stokta Var", "1-2 Gün", "3-5 Gün", "1 Hafta",
              "2-3 Hafta", "3-4 Hafta", "4-6 Hafta", "Sipariş Üzerine"]

# Satır yüksekliği 34px — tüm widget'lar aynı fixed yükseklikte
ROW_H = 34


def _table_styles():
    """Tema-aware tablo içi widget stilleri — her çağrıda güncel tema rengini alır."""
    from ui.theme_manager import get_theme
    t = get_theme()
    bg    = t["bg_input"]
    fg    = t["text_primary"]
    bdr   = t["border_input"]
    acc   = t["accent_blue"]
    spin = (
        f"QDoubleSpinBox{{border:1px solid {bdr};border-radius:4px;"
        f"padding:0px 4px;font-size:8pt;background:{bg};color:{fg};"
        f"min-height:{ROW_H-2}px;max-height:{ROW_H-2}px;}}"
        "QDoubleSpinBox::up-button,QDoubleSpinBox::down-button{width:0;height:0;border:none;}"
    )
    combo = (
        f"QComboBox{{border:1px solid {bdr};border-radius:4px;"
        f"padding:0px 4px;font-size:8pt;background:{bg};color:{fg};"
        f"min-height:{ROW_H-2}px;max-height:{ROW_H-2}px;}}"
        "QComboBox::drop-down{width:14px;border:none;}"
        f"QComboBox::down-arrow{{image:none;border-left:3px solid transparent;"
        "border-right:3px solid transparent;border-top:4px solid #888;"
        "width:0;height:0;margin-right:4px;}"
        f"QComboBox QAbstractItemView{{background:{bg};color:{fg};"
        f"border:1px solid {bdr};selection-background-color:{acc};selection-color:#fff;}}"
    )
    return spin, combo



def _wrap(widget):
    """Widget'ı QWidget sarmalayıcıya koy — hücre içi dikey hizalama için."""
    WH = ROW_H - 4          # widget iç yüksekliği (padding için -4)
    widget.setFixedHeight(WH)
    wrapper = QWidget()
    wrapper.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
    wrapper.setFixedHeight(ROW_H)
    lay = QHBoxLayout(wrapper)
    lay.setContentsMargins(3, 0, 3, 0)
    lay.setSpacing(0)
    lay.addWidget(widget)
    lay.setAlignment(widget, Qt.AlignmentFlag.AlignVCenter)
    return wrapper


def _unwrap(cw):
    """_wrap() ile sarılmış wrapper'dan iç widget'ı çıkar."""
    if cw and cw.layout() and cw.layout().count():
        return cw.layout().itemAt(0).widget()
    return cw

# ─────────────────────────────────────────────────────────────────────────────
# Ürün seçim diyalogu — çoklu seçim (Shift/Ctrl)
# ─────────────────────────────────────────────────────────────────────────────

class ProductSelectDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ürün Seç")
        self.setMinimumSize(720, 520)
        self.selected_products = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(10)

        hdr = QHBoxLayout()
        title = QLabel("Ürün Seç")
        title.setStyleSheet("font-size:10pt;font-weight:700;")
        hdr.addWidget(title)
        hint = QLabel("Shift veya Ctrl ile çoklu seçim yapabilirsiniz")
        hint.setStyleSheet("color:#888;font-size:8pt;")
        hdr.addStretch(); hdr.addWidget(hint)
        layout.addLayout(hdr)

        search = QLineEdit()
        search.setPlaceholderText("Ürün kodu, adı veya açıklaması ile ara...")
        search.setMinimumHeight(34)
        search.textChanged.connect(self._search)
        layout.addWidget(search)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Kod","Ürün Adı","Fiyat","Para Birimi","Birim"])
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(0, 110); self.table.setColumnWidth(2, 90)
        self.table.setColumnWidth(3, 80);  self.table.setColumnWidth(4, 70)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        # Çoklu satır seçimi
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.doubleClicked.connect(self._select)
        layout.addWidget(self.table)

        sel_lbl = QLabel("")
        sel_lbl.setObjectName("sel_lbl")
        sel_lbl.setStyleSheet("color:#0f3460;font-size:8pt;")
        self.table.itemSelectionChanged.connect(
            lambda: sel_lbl.setText(
                f"{len(self.table.selectionModel().selectedRows())} satır seçili"
                if self.table.selectionModel().selectedRows() else ""
            )
        )
        layout.addWidget(sel_lbl)

        btns = QHBoxLayout()
        btns.addStretch()
        no = QPushButton("İptal"); no.setObjectName("secondary"); no.clicked.connect(self.reject)
        ok = QPushButton("Seçilenleri Ekle"); ok.setObjectName("primary"); ok.clicked.connect(self._select)
        btns.addWidget(no); btns.addWidget(ok)
        layout.addLayout(btns)

        self._svc = ProductService(); self._products = []
        self._load()

    def _load(self, keyword=""):
        self._products = self._svc.search(keyword) if keyword else self._svc.get_all()
        self.table.setRowCount(len(self._products))
        for row, p in enumerate(self._products):
            self.table.setItem(row, 0, QTableWidgetItem(p.product_code))
            self.table.setItem(row, 1, QTableWidgetItem(p.product_name))
            pi = QTableWidgetItem(f"{p.price:,.2f}")
            pi.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row, 2, pi)
            self.table.setItem(row, 3, QTableWidgetItem(p.currency))
            self.table.setItem(row, 4, QTableWidgetItem(p.unit))

    def _search(self, txt): self._load(txt)

    def _select(self):
        rows = sorted(set(idx.row() for idx in self.table.selectionModel().selectedRows()))
        if not rows: return
        self.selected_products = [self._products[r] for r in rows if r < len(self._products)]
        if self.selected_products:
            logger.debug("Ürün(ler) seçildi: %s", [p.product_code for p in self.selected_products])
            self.accept()


# ─────────────────────────────────────────────────────────────────────────────
# Adım göstergesi
# ─────────────────────────────────────────────────────────────────────────────

class _StepItem(QWidget):
    """Tek bir adım: yuvarlak rozet + etiket, yatay hizalı."""
    def __init__(self, number: int, label: str, parent=None):
        super().__init__(parent)
        self._number = str(number)
        self._label  = label
        self.setFixedHeight(48)

        row = QHBoxLayout(self)
        row.setContentsMargins(14, 0, 14, 0)
        row.setSpacing(10)
        row.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Yuvarlak sayı rozeti
        self._badge = QLabel(self._number)
        self._badge.setFixedSize(30, 30)
        self._badge.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Adım adı
        self._text = QLabel(label)
        self._text.setAlignment(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
        )

        row.addWidget(self._badge)
        row.addWidget(self._text)

    def apply_state(self, state: str):
        """state: 'done' | 'active' | 'pending'"""
        if state == "done":
            self._badge.setText("✓")
            self._badge.setStyleSheet(
                "background:#16a085;color:white;border-radius:15px;"
                "font-size:11pt;font-weight:700;"
            )
            self._text.setStyleSheet(
                "font-size:11pt;font-weight:600;color:#16a085;"
            )
            self.setStyleSheet("background:transparent;")
        elif state == "active":
            self._badge.setText(self._number)
            self._badge.setStyleSheet(
                "background:#0f3460;color:white;border-radius:15px;"
                "font-size:11pt;font-weight:700;"
            )
            self._text.setStyleSheet(
                "font-size:11pt;font-weight:700;color:#0f3460;"
            )
            self.setStyleSheet(
                "background:#e8f0fe;border-radius:8px;"
            )
        else:  # pending
            self._badge.setText(self._number)
            self._badge.setStyleSheet(
                "background:#cccccc;color:#777;border-radius:15px;"
                "font-size:11pt;font-weight:600;"
            )
            self._text.setStyleSheet(
                "font-size:11pt;font-weight:500;color:#999;"
            )
            self.setStyleSheet("background:transparent;")


class StepIndicator(QWidget):
    def __init__(self, steps: list):
        super().__init__()
        self._steps   = steps
        self._current = 0
        self.setFixedHeight(48)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._items = []
        self._lines = []

        for i, label in enumerate(steps):
            item = _StepItem(i + 1, label)
            self._items.append(item)
            layout.addWidget(item, 3)

            if i < len(steps) - 1:
                line = QFrame()
                line.setFrameShape(QFrame.Shape.HLine)
                line.setFixedHeight(2)
                self._lines.append(line)
                layout.addWidget(line, 1)

        self._refresh()

    def set_step(self, idx: int):
        self._current = idx
        self._refresh()

    def _refresh(self):
        for i, item in enumerate(self._items):
            if i < self._current:
                item.apply_state("done")
            elif i == self._current:
                item.apply_state("active")
            else:
                item.apply_state("pending")

        for i, line in enumerate(self._lines):
            color = "#16a085" if i < self._current else "#ddd"
            line.setStyleSheet(f"background:{color};border:none;")


# ─────────────────────────────────────────────────────────────────────────────
# Ana sayfa
# ─────────────────────────────────────────────────────────────────────────────

class CreateOfferPage(QWidget):
    offer_saved = Signal()

    def __init__(self):
        super().__init__()
        self.customer_svc      = CustomerService()
        self.offer_svc         = OfferService()
        self._customers        = []
        self._current_offer_id = None
        self._current_status   = "Beklemede"
        self._offer_no         = ""
        self._original_date    = ""
        self._is_new           = True
        self._build_ui()

    # ──────────────────────────────────────────────────────── UI inşa ────────

    def _build_ui(self):
        main = QVBoxLayout(self)
        main.setContentsMargins(16, 14, 16, 12)
        main.setSpacing(8)

        # Başlık
        hdr = QHBoxLayout()
        self.title_lbl = QLabel("Yeni Teklif")
        self.title_lbl.setStyleSheet("font-size:13pt;font-weight:700;")
        hdr.addWidget(self.title_lbl); hdr.addStretch()
        self.offer_no_lbl = QLabel("")
        self.offer_no_lbl.setStyleSheet(
            "font-size:10pt;font-weight:bold;color:#0f3460;padding:4px 10px;"
            "background:#e8f0fe;border-radius:6px;")
        hdr.addWidget(self.offer_no_lbl)
        main.addLayout(hdr)

        # Adım göstergesi
        self.step_indicator = StepIndicator(["Müşteri", "Ürünler", "Özet & PDF"])
        main.addWidget(self.step_indicator)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color:#ddd;"); main.addWidget(sep)

        # Sayfa yığını
        self.stack = QStackedWidget()
        self.stack.setContentsMargins(0, 4, 0, 0)
        main.addWidget(self.stack, 1)
        self.stack.addWidget(self._build_step1())
        self.stack.addWidget(self._build_step2())
        self.stack.addWidget(self._build_step3())

        # Alt navigasyon — Geri ile İleri yan yana, sağda
        nav = QHBoxLayout()
        nav.addStretch()

        self.btn_back = QPushButton("Geri")
        self.btn_back.setObjectName("secondary")
        self.btn_back.setMinimumHeight(36); self.btn_back.setFixedWidth(110)
        self.btn_back.clicked.connect(self._go_back)

        self.btn_next = QPushButton("İleri")
        self.btn_next.setObjectName("secondary")
        self.btn_next.setMinimumHeight(36); self.btn_next.setFixedWidth(150)
        self.btn_next.clicked.connect(self._go_next)

        nav.addWidget(self.btn_back)
        nav.addWidget(self.btn_next)
        main.addLayout(nav)
        self._set_step(0)

    # ──────────────────────────────────────────────────── Adım 1: Müşteri ───

    def _build_step1(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0); layout.setSpacing(10)

        # Kart 1: Müşteri Seç
        box, g = make_section_card("Müşteri Seç")
        g.setColumnStretch(1, 1)

        self.customer_combo = QComboBox()
        self.customer_combo.setMinimumHeight(34)
        self.customer_combo.setMaxVisibleItems(8)
        self.customer_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.customer_combo.currentIndexChanged.connect(self._on_customer_selected)

        self.currency_combo = QComboBox()
        self.currency_combo.addItems(["EUR","USD","TL"])
        self.currency_combo.setMinimumHeight(34)
        self.currency_combo.setFixedWidth(90)
        self.currency_combo.currentTextChanged.connect(self._update_total)

        g.addWidget(QLabel("Müşteri:"),     0, 0); g.addWidget(self.customer_combo, 0, 1)
        g.addWidget(QLabel("Para Birimi:"), 0, 2); g.addWidget(self.currency_combo, 0, 3)
        layout.addWidget(box)

        # Kart 2: Müşteri Bilgileri
        info_box, mg = make_section_card("Müşteri Bilgileri")
        info_box.setToolTip("Listeden müşteri seçince otomatik dolar. Elle de düzenleyebilirsiniz.")

        self.company_edit = QLineEdit(); self.company_edit.setPlaceholderText("Firma adı *")
        self.address_edit = QLineEdit(); self.address_edit.setPlaceholderText("Adres")
        self.contact_edit = QLineEdit(); self.contact_edit.setPlaceholderText("İlgili kişi")
        for le in [self.company_edit, self.address_edit, self.contact_edit]:
            le.setMinimumHeight(32)

        mg.addWidget(QLabel("Firma Adı:"),   0, 0); mg.addWidget(self.company_edit, 0, 1, 1, 3)
        mg.addWidget(QLabel("Adres:"),       1, 0); mg.addWidget(self.address_edit, 1, 1, 1, 3)
        mg.addWidget(QLabel("İlgili Kişi:"), 2, 0); mg.addWidget(self.contact_edit, 2, 1, 1, 3)
        mg.setColumnStretch(1, 3)
        layout.addWidget(info_box)

        layout.addStretch()
        return w

    # ──────────────────────────────────────────────────── Adım 2: Ürünler ───

    def _build_step2(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 8, 0, 4); layout.setSpacing(6)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("＋  Ürün Ekle")
        add_btn.setObjectName("primary"); add_btn.setMinimumHeight(34)
        add_btn.clicked.connect(self._add_product)

        rem_btn = QPushButton("−  Ürün Çıkart")
        rem_btn.setObjectName("danger"); rem_btn.setMinimumHeight(34)
        rem_btn.clicked.connect(self._remove_selected_row)

        btn_row.addWidget(add_btn); btn_row.addWidget(rem_btn); btn_row.addStretch()
        layout.addLayout(btn_row)

        self.prod_table = QTableWidget()
        self.prod_table.setColumnCount(8)
        self.prod_table.setHorizontalHeaderLabels(
            ["Malzeme Kodu","Ürün Adı","Açıklama","Adet","Birim","Teslim Süresi","Birim Fiyat","Toplam"])

        hh = self.prod_table.horizontalHeader()
        # Önce tümünü Interactive yap, sonra Stretch olanları override et
        hh.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        hh.setMinimumSectionSize(40)
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        hh.setSectionResizeMode(4, QHeaderView.ResizeMode.Interactive)
        hh.setSectionResizeMode(5, QHeaderView.ResizeMode.Interactive)
        hh.setSectionResizeMode(6, QHeaderView.ResizeMode.Interactive)
        hh.setSectionResizeMode(7, QHeaderView.ResizeMode.Interactive)
        # Başlangıç genişlikleri
        self.prod_table.setColumnWidth(0, 110)  # Malzeme Kodu
        self.prod_table.setColumnWidth(3,  72)  # Adet
        self.prod_table.setColumnWidth(4,  80)  # Birim
        self.prod_table.setColumnWidth(5, 110)  # Teslim Süresi
        self.prod_table.setColumnWidth(6, 115)  # Birim Fiyat
        self.prod_table.setColumnWidth(7, 115)  # Toplam

        self.prod_table.setAlternatingRowColors(True)
        self.prod_table.verticalHeader().setVisible(False)
        self.prod_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.prod_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        layout.addWidget(self.prod_table)

        total_row = QHBoxLayout(); total_row.addStretch()
        self.total_lbl = QLabel("Genel Toplam: 0,00 €")
        self.total_lbl.setStyleSheet(
            "font-size:11pt;font-weight:bold;padding:5px 14px;"
            "background:#0f3460;color:white;border-radius:6px;")
        total_row.addWidget(self.total_lbl)
        layout.addLayout(total_row)
        return w

    # ──────────────────────────────────────────── Adım 3: Özet & PDF ────────

    def _build_step3(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 8, 0, 4); layout.setSpacing(10)

        # Vade + Ödeme kartı
        vade_box = QGroupBox("Teklif Koşulları")
        vg = QGridLayout(vade_box)
        vg.setContentsMargins(14, 12, 14, 12); vg.setSpacing(10)
        vg.setColumnStretch(1, 1); vg.setColumnStretch(3, 1)

        self.validity_combo = QComboBox(); self.validity_combo.setMinimumHeight(32)
        self.validity_combo.addItems([
            "15 Gün", "30 Gün", "45 Gün", "60 Gün", "90 Gün",
            "120 Gün", "6 Ay", "Belirtilmemiş"
        ])
        self.validity_combo.setCurrentText("Belirtilmemiş")
        self.validity_combo.currentTextChanged.connect(lambda _: self._refresh_summary())

        self.payment_combo = QComboBox(); self.payment_combo.setMinimumHeight(32)
        self.payment_combo.addItems([
            "Peşin", "30 Gün Vadeli", "45 Gün Vadeli", "60 Gün Vadeli",
            "90 Gün Vadeli", "120 Gün Vadeli", "Sipariş Avansı %30",
            "Sipariş Avansı %50", "Akreditif", "Belirtilmemiş"
        ])
        self.payment_combo.setCurrentText("Belirtilmemiş")
        self.payment_combo.currentTextChanged.connect(lambda _: self._refresh_summary())

        self.validity_note = QLineEdit()
        self.validity_note.setPlaceholderText("Ek not: ör. 'Hammadde fiyatlarına bağlıdır'")
        self.validity_note.setMinimumHeight(32)
        self.validity_note.textChanged.connect(lambda _: self._refresh_summary())

        vg.addWidget(QLabel("Teklif Geçerlilik:"), 0, 0)
        vg.addWidget(self.validity_combo,           0, 1)
        vg.addWidget(QLabel("Ödeme Vadesi:"),       0, 2)
        vg.addWidget(self.payment_combo,            0, 3)
        vg.addWidget(QLabel("Not:"),                1, 0)
        vg.addWidget(self.validity_note,            1, 1, 1, 3)
        layout.addWidget(vade_box)

        # Özet — scrollable
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        self.summary_label.setTextFormat(Qt.TextFormat.RichText)
        self.summary_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.summary_label.setStyleSheet(
            "border:1px solid #dee2e6;border-radius:8px;"
            "padding:14px;font-size:9pt;")
        scroll.setWidget(self.summary_label)
        layout.addWidget(scroll, 1)

        # Eylem butonları
        action_row = QHBoxLayout(); action_row.setSpacing(12)
        btn_save = QPushButton("Teklifi Kaydet")
        btn_save.setObjectName("secondary"); btn_save.setMinimumHeight(42)
        btn_save.clicked.connect(self._save)

        btn_pdf = QPushButton("Teklifi PDF'e Dönüştür")
        btn_pdf.setObjectName("secondary"); btn_pdf.setMinimumHeight(42)

        btn_pdf.clicked.connect(self._save_and_pdf)

        btn_save.setMaximumWidth(240)
        btn_pdf.setMaximumWidth(280)
        action_row.addStretch()
        action_row.addWidget(btn_save); action_row.addWidget(btn_pdf)
        action_row.addStretch()
        layout.addLayout(action_row)
        return w

    # ──────────────────────────────────────────────── Wizard navigasyon ──────

    def _set_step(self, idx: int):
        self.stack.setCurrentIndex(idx)
        self.step_indicator.set_step(idx)
        self.btn_back.setEnabled(idx > 0)
        if idx == 2:
            self.btn_next.setVisible(False)
            self._refresh_summary()
        else:
            self.btn_next.setVisible(True)
            self.btn_next.setText("İleri" if idx == 0 else "Özete Git")

    def _go_next(self):
        cur = self.stack.currentIndex()
        if cur == 0:
            if not self._validate_step1(): return
            self._check_customer_registration()
            self._set_step(1)
        elif cur == 1:
            self._set_step(2)

    def _check_customer_registration(self):
        """Müşteri kayıtlı değilse kaydetmeyi öner."""
        company = self.company_edit.text().strip()
        if not company:
            return
        # Combo'dan seçim yapıldıysa zaten kayıtlıdır
        if self.customer_combo.currentData() is not None:
            return
        # Firma adı ile arama yap
        existing = self.customer_svc.search(company)
        for c in existing:
            if c.company_name.lower() == company.lower():
                return  # Kayıtlı
        # Kayıtlı değil, sor
        reply = QMessageBox.question(
            self, "Müşteri Kaydı",
            f"'{company}' sistemde kayıtlı değil.\nKaydetmek ister misiniz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                new_id = self.customer_svc.add(Customer(
                    company_name=company,
                    contact_person=self.contact_edit.text().strip(),
                    address=self.address_edit.text().strip(),
                    phone="",
                    email="",
                ))
                self._load_customers()
                # Yeni kaydedilen müşteriyi seç
                for i, c in enumerate(self._customers):
                    if c.id == new_id:
                        self.customer_combo.setCurrentIndex(i + 1)
                        break
                logger.info("Yeni müşteri kaydedildi: %s", company)
            except Exception as e:
                QMessageBox.warning(self, "Hata", f"Müşteri kaydedilemedi:\n{e}")

    def _go_back(self):
        cur = self.stack.currentIndex()
        if cur > 0: self._set_step(cur - 1)

    def _validate_step1(self) -> bool:
        if not self.company_edit.text().strip():
            QMessageBox.warning(self, "Eksik Bilgi",
                "Firma adı zorunludur.\n"
                "Listeden müşteri seçin veya firma adını elle girin.")
            return False
        return True

    # ──────────────────────────────────────────────────── Özet paneli ────────

    def _refresh_summary(self):
        company  = self.company_edit.text().strip() or "—"
        address  = self.address_edit.text().strip() or "—"
        contact  = self.contact_edit.text().strip() or "—"
        currency = self.currency_combo.currentText()
        sym      = SYM_MAP.get(currency, "€")
        total    = self._calc_total()
        date_str = self._original_date if (not self._is_new and self._original_date) \
                   else datetime.date.today().strftime("%d.%m.%Y")
        validity = self.validity_combo.currentText()
        payment  = self.payment_combo.currentText()
        note     = self.validity_note.text().strip()

        rows_html = ""
        for r in range(self.prod_table.rowCount()):
            code  = self.prod_table.item(r,0).text() if self.prod_table.item(r,0) else ""
            name  = self.prod_table.item(r,1).text() if self.prod_table.item(r,1) else ""
            desc  = self.prod_table.item(r,2).text() if self.prod_table.item(r,2) else ""
            qty_w = _unwrap(self.prod_table.cellWidget(r,3))
            unit_w= _unwrap(self.prod_table.cellWidget(r,4))
            del_w = _unwrap(self.prod_table.cellWidget(r,5))
            prc_w = _unwrap(self.prod_table.cellWidget(r,6))
            qty   = qty_w.value()  if qty_w  else 0
            prc   = prc_w.value()  if prc_w  else 0
            unit  = unit_w.currentText()  if unit_w  else ""
            delv  = del_w.currentText()   if del_w   else ""
            bg = "#f8f8f8" if r % 2 == 0 else "#ffffff"
            rows_html += (
                f"<tr style='background:{bg};'>"
                f"<td style='padding:3px 6px;font-size:8pt;color:#555;'>{r+1}</td>"
                f"<td style='padding:3px 6px;'><b>{code}</b></td>"
                f"<td style='padding:3px 6px;'>{name}"
                f"{'<br><span style=\"color:#888;font-size:8pt;\">'+desc+'</span>' if desc else ''}</td>"
                f"<td style='padding:3px 6px;text-align:right;'>{qty:g} {unit}</td>"
                f"<td style='padding:3px 6px;text-align:right;'>{prc:,.2f} {sym}</td>"
                f"<td style='padding:3px 6px;text-align:right;font-weight:bold;'>{qty*prc:,.2f} {sym}</td>"
                f"<td style='padding:3px 6px;font-size:8pt;color:#666;text-align:center;'>{delv}</td>"
                f"</tr>"
            )

        validity_row = (
            f"<tr style='background:#fff8e8;'>"
            f"<td colspan='2' style='padding:4px 6px;'><b>Teklif Geçerliliği:</b></td>"
            f"<td colspan='3' style='padding:4px 6px;color:#c05500;font-weight:bold;'>{validity}"
            f"{'  — ' + note if note else ''}</td>"
            f"<td colspan='2'></td></tr>"
            f"<tr style='background:#f0f8ff;'>"
            f"<td colspan='2' style='padding:4px 6px;'><b>Ödeme Vadesi:</b></td>"
            f"<td colspan='5' style='padding:4px 6px;color:#0055aa;font-weight:bold;'>{payment}</td>"
            f"</tr>"
        )

        html = f"""
        <b style='font-size:10pt;'>Teklif Özeti</b><br><br>
        <table width='100%' style='margin-bottom:6px;'>
        <tr><td width='110'><b>Teklif No:</b></td><td>{self._offer_no}</td>
            <td width='60'><b>Tarih:</b></td><td>{date_str}</td></tr>
        <tr><td><b>Firma:</b></td><td><b>{company}</b></td>
            <td><b>İlgili:</b></td><td>{contact}</td></tr>
        <tr><td><b>Adres:</b></td><td colspan='3'>{address}</td></tr>
        </table>
        <hr style='margin:8px 0;'>
        <table width='100%' cellspacing='0'>
        <tr style='background:#0f3460;color:white;'>
            <th style='padding:4px 6px;text-align:center;width:24px;'>#</th>
            <th style='padding:4px 6px;text-align:left;'>Kod</th>
            <th style='padding:4px 6px;text-align:left;'>Ürün</th>
            <th style='padding:4px 6px;text-align:right;'>Miktar</th>
            <th style='padding:4px 6px;text-align:right;'>Birim Fiyat</th>
            <th style='padding:4px 6px;text-align:right;'>Toplam</th>
            <th style='padding:4px 6px;text-align:center;'>Teslim</th>
        </tr>
        {rows_html}
        <tr style='background:#e8f0fe;'>
            <td colspan='5' style='padding:5px 6px;text-align:right;font-weight:bold;'>
            Genel Toplam:</td>
            <td colspan='2' style='padding:5px 6px;text-align:right;font-size:11pt;
            font-weight:bold;color:#0f3460;'>{total:,.2f} {sym}</td>
        </tr>
        {validity_row}
        </table>
        """
        self.summary_label.setText(html)

    # ──────────────────────────────────────────────────── Müşteri ────────────

    def _load_customers(self):
        prev_id = self.customer_combo.currentData()
        self._customers = self.customer_svc.get_all()
        self.customer_combo.blockSignals(True)
        self.customer_combo.clear()
        self.customer_combo.addItem("-- Müşteri Seçin --", None)
        restore_idx = 0
        for i, c in enumerate(self._customers):
            self.customer_combo.addItem(c.company_name, c.id)
            if prev_id and c.id == prev_id:
                restore_idx = i + 1
        self.customer_combo.setCurrentIndex(restore_idx)
        self.customer_combo.blockSignals(False)

    def _on_customer_selected(self, index):
        if index <= 0:
            # Boş seçim: alanları temizle
            self.company_edit.clear()
            self.address_edit.clear()
            self.contact_edit.clear()
            return
        c = self._customers[index - 1]
        self.company_edit.setText(c.company_name)
        self.address_edit.setText(c.address)
        self.contact_edit.setText(c.contact_person)
        logger.debug("Müşteri seçildi: %s", c.company_name)

    # ──────────────────────────────────────────────────── Ürün tablosu ───────

    def _add_product(self):
        dlg = ProductSelectDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted: return
        low_stock = []
        for p in dlg.selected_products:
            self._add_row(code=p.product_code, name=p.product_name,
                          desc=p.description, unit=p.unit, price=p.price)
            # Stok uyarısı — 0 veya düşükse bildir
            if p.stock is not None and p.stock <= 0:
                low_stock.append(f"{p.product_code} — {p.product_name} (Stok: {p.stock:.0f})")
        if low_stock:
            QMessageBox.warning(
                self, "⚠ Stok Uyarısı",
                "Aşağıdaki ürünlerin stoğu yetersiz veya sıfır:\n\n"
                + "\n".join(f"• {s}" for s in low_stock)
                + "\n\nTeklif oluşturmaya devam edebilirsiniz."
            )

    def _add_row(self, code="", name="", desc="", qty=1.0,
                 unit="Adet", delivery="2-3 Hafta", price=0.0):
        SPIN_STYLE, COMBO_STYLE = _table_styles()
        row = self.prod_table.rowCount()
        self.prod_table.insertRow(row)
        self.prod_table.setRowHeight(row, ROW_H + 4)

        def item(text, user_data=None):
            it = QTableWidgetItem(str(text))
            if user_data is not None: it.setData(Qt.ItemDataRole.UserRole, user_data)
            return it

        self.prod_table.setItem(row, 0, item(code))
        self.prod_table.setItem(row, 1, item(name))
        self.prod_table.setItem(row, 2, item(desc))

        qty_spin = QDoubleSpinBox()
        qty_spin.setMaximum(999999); qty_spin.setDecimals(2); qty_spin.setValue(qty)
        qty_spin.setStyleSheet(SPIN_STYLE)
        qty_spin.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        qty_spin.setStepType(QDoubleSpinBox.StepType.AdaptiveDecimalStepType)
        qty_spin.valueChanged.connect(lambda _, w=qty_spin: self._recalc_by_widget(w, 3))
        self.prod_table.setCellWidget(row, 3, _wrap(qty_spin))

        unit_cb = QComboBox(); unit_cb.addItems(UNITS); unit_cb.setStyleSheet(COMBO_STYLE)
        u_idx = unit_cb.findText(unit)
        if u_idx >= 0: unit_cb.setCurrentIndex(u_idx)
        else: unit_cb.setCurrentText(unit)
        self.prod_table.setCellWidget(row, 4, _wrap(unit_cb))

        del_cb = QComboBox(); del_cb.addItems(DELIVERIES); del_cb.setStyleSheet(COMBO_STYLE)
        d_idx = del_cb.findText(delivery)
        if d_idx >= 0: del_cb.setCurrentIndex(d_idx)
        self.prod_table.setCellWidget(row, 5, _wrap(del_cb))

        price_spin = QDoubleSpinBox()
        price_spin.setMaximum(9_999_999); price_spin.setDecimals(2); price_spin.setValue(price)
        price_spin.setStyleSheet(SPIN_STYLE)
        price_spin.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        price_spin.setGroupSeparatorShown(True)
        price_spin.valueChanged.connect(lambda _, w=price_spin: self._recalc_by_widget(w, 6))
        self.prod_table.setCellWidget(row, 6, _wrap(price_spin))

        total_item = QTableWidgetItem(f"{qty * price:,.2f}")
        total_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        total_item.setFlags(total_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.prod_table.setItem(row, 7, total_item)
        self._update_total()

    def _recalc_by_widget(self, widget, col: int):
        for r in range(self.prod_table.rowCount()):
            cw = self.prod_table.cellWidget(r, col)
            # wrapper ise içindeki widget'ı karşılaştır
            actual = _unwrap(cw)
            if actual is widget:
                self._recalc_row(r); return

    def _recalc_row(self, row):
        qty_w = _unwrap(self.prod_table.cellWidget(row, 3))
        prc_w = _unwrap(self.prod_table.cellWidget(row, 6))
        if qty_w and prc_w:
            ti = self.prod_table.item(row, 7)
            if ti: ti.setText(f"{qty_w.value() * prc_w.value():,.2f}")
        self._update_total()

    def _remove_selected_row(self):
        rows = sorted(set(idx.row() for idx in
                         self.prod_table.selectionModel().selectedRows()), reverse=True)
        if not rows:
            QMessageBox.information(self, "Bilgi", "Lütfen kaldırılacak satırı seçin.")
            return
        for r in rows:
            self.prod_table.removeRow(r)
        self._update_total()

    def _update_total(self):
        sym = SYM_MAP.get(self.currency_combo.currentText(), "€")
        self.total_lbl.setText(f"Genel Toplam: {self._calc_total():,.2f} {sym}")

    def _calc_total(self) -> float:
        return sum(
            (_unwrap(self.prod_table.cellWidget(r,3)).value()
             if _unwrap(self.prod_table.cellWidget(r,3)) else 0) *
            (_unwrap(self.prod_table.cellWidget(r,6)).value()
             if _unwrap(self.prod_table.cellWidget(r,6)) else 0)
            for r in range(self.prod_table.rowCount())
        )

    # ──────────────────────────────────────────────── Veri toplama & kayıt ───

    def _collect_data(self):
        company = self.company_edit.text().strip()
        if not company:
            QMessageBox.warning(self, "Eksik Bilgi", "Firma adı zorunludur."); return None

        items = []
        for row in range(self.prod_table.rowCount()):
            code_i = self.prod_table.item(row, 0)
            name_i = self.prod_table.item(row, 1)
            desc_i = self.prod_table.item(row, 2)
            qty_w  = _unwrap(self.prod_table.cellWidget(row, 3))
            unit_w = _unwrap(self.prod_table.cellWidget(row, 4))
            del_w  = _unwrap(self.prod_table.cellWidget(row, 5))
            prc_w  = _unwrap(self.prod_table.cellWidget(row, 6))
            if not (qty_w and prc_w): continue
            qty = qty_w.value(); price = prc_w.value()
            items.append({
                "product_id":    code_i.data(Qt.ItemDataRole.UserRole) if code_i else None,
                "product_code":  code_i.text() if code_i else "",
                "product_name":  name_i.text() if name_i else "",
                "description":   desc_i.text() if desc_i else "",
                "quantity":      qty,
                "unit":          unit_w.currentText() if unit_w else "Adet",
                "delivery_time": del_w.currentText()  if del_w  else "2-3 Hafta",
                "unit_price":    price,
                "total_price":   qty * price,
            })

        date_str = self._original_date if (not self._is_new and self._original_date) \
                   else datetime.date.today().strftime("%d.%m.%Y")

        return {
            "id":               self._current_offer_id,
            "offer_no":         self._offer_no,
            "customer_id":      self.customer_combo.currentData(),
            "company_name":     company,
            "customer_address": self.address_edit.text().strip(),
            "contact_person":   self.contact_edit.text().strip(),
            "date":             date_str,
            "currency":         self.currency_combo.currentText(),
            "total_amount":     self._calc_total(),
            "items":            items,
            "validity":         self.validity_combo.currentText(),
            "validity_note":    self.validity_note.text().strip(),
            "payment_term":     self.payment_combo.currentText(),
            "status":           self._current_status,
        }

    def _save(self):
        data = self._collect_data()
        if not data: return
        try:
            oid = self.offer_svc.save(data)
            logger.info("Teklif kaydedildi: %s", self._offer_no)
            QMessageBox.information(self, "Kaydedildi", f"'{self._offer_no}' kaydedildi.")
            self._reset_to_new()
            self.offer_saved.emit()
        except Exception as e:
            logger.error("Kaydetme hatası: %s", e, exc_info=True)
            QMessageBox.warning(self, "Hata", f"Kaydedilemedi:\n{e}")

    def _save_and_pdf(self):
        # Teklif koşulları — uyarı ver ama engelleme
        missing = []
        if self.validity_combo.currentText() == "Belirtilmemiş":
            missing.append("• Teklif Geçerlilik Süresi")
        if self.payment_combo.currentText() == "Belirtilmemiş":
            missing.append("• Ödeme Vadesi")
        if missing:
            reply = QMessageBox.question(
                self, "Eksik Bilgi",
                "Aşağıdaki alanlar belirtilmemiş:\n" + "\n".join(missing) +
                "\n\nYine de PDF oluşturulsun mu?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if reply != QMessageBox.StandardButton.Yes:
                return
        data = self._collect_data()
        if not data: return

        # ── Kayıt konumunu kullanıcıya sor (varsayılan: Masaüstü) ──────────
        desktop = Path.home() / "Desktop"
        if not desktop.exists():
            desktop = Path.home()
        default_file = str(desktop / f"{self._offer_no}.pdf")
        out_path, _ = QFileDialog.getSaveFileName(
            self, "PDF Kaydet", default_file,
            "PDF Dosyası (*.pdf)")
        if not out_path:
            return   # kullanıcı iptal etti

        try:
            oid = self.offer_svc.save(data)
            self._current_offer_id = oid; self._is_new = False
            from pdf.pdf_generator import generate_pdf
            from app_paths import PDF_DIR
            # Orijinal konuma da yedek kopyası
            PDF_DIR.mkdir(parents=True, exist_ok=True)
            backup = str(PDF_DIR / f"{self._offer_no}.pdf")
            generate_pdf(data, out_path)
            if out_path != backup:
                import shutil as _shutil
                try: _shutil.copy2(out_path, backup)
                except Exception: pass
            logger.info("PDF oluşturuldu: %s", out_path)
            reply = QMessageBox.information(
                self, "PDF Oluşturuldu",
                f"Teklif kaydedildi ve PDF oluşturuldu.\n\nAçmak ister misiniz?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                os.startfile(out_path)
            self._reset_to_new()
            self.offer_saved.emit()
        except Exception as e:
            logger.error("PDF hatası: %s", e, exc_info=True)
            QMessageBox.warning(self, "Hata", f"PDF oluşturulamadı:\n{e}")

    # ──────────────────────────────────────────────────── Sıfırla / Yükle ───

    def _reset_to_new(self):
        self._current_offer_id = None; self._original_date = ""
        self._is_new = True
        self._offer_no = self.offer_svc.generate_offer_no()
        self.offer_no_lbl.setText(self._offer_no)
        self.title_lbl.setText("Yeni Teklif")
        self._load_customers()
        self.customer_combo.setCurrentIndex(0)
        self.company_edit.clear(); self.address_edit.clear(); self.contact_edit.clear()
        self.currency_combo.setCurrentIndex(0)
        self.prod_table.setRowCount(0)
        self.validity_combo.setCurrentText("Belirtilmemiş")
        self.payment_combo.setCurrentText("Belirtilmemiş")
        self.validity_note.clear()
        self._update_total(); self._set_step(0)

    def on_enter(self):
        self._load_customers()
        if self._is_new and not self._offer_no:
            self._offer_no = self.offer_svc.generate_offer_no()
            logger.info("İlk teklif numarası: %s", self._offer_no)
            self.offer_no_lbl.setText(self._offer_no)

    def load_offer(self, offer_id: int):
        offer = self.offer_svc.get_by_id(offer_id)
        if not offer: return
        self._current_offer_id = offer_id
        self._offer_no         = offer["offer_no"]
        self._original_date    = offer.get("date","")
        self._is_new           = False
        self.offer_no_lbl.setText(self._offer_no)
        self.title_lbl.setText("Teklif Düzenle")

        # Müşteri listesini yükle — sinyalleri tamamen blokla
        self.customer_combo.blockSignals(True)
        self._load_customers()
        self.customer_combo.blockSignals(False)

        self._current_status = offer.get("status", "Beklemede") or "Beklemede"

        # DB'den gelen company_name, address, contact_person — her zaman bunları kullan
        self.company_edit.setText(offer.get("company_name","") or "")
        self.address_edit.setText(offer.get("customer_address","") or "")
        self.contact_edit.setText(offer.get("contact_person","") or "")

        # Müşteri combo'yu seç (sinyal tetiklemeden)
        cid = offer.get("customer_id")
        self.customer_combo.blockSignals(True)
        for i, c in enumerate(self._customers):
            if c.id == cid:
                self.customer_combo.setCurrentIndex(i + 1)
                break
        self.customer_combo.blockSignals(False)

        ci = self.currency_combo.findText(offer.get("currency","EUR"))
        if ci >= 0: self.currency_combo.setCurrentIndex(ci)

        self.prod_table.setRowCount(0)
        for item in offer.get("items",[]):
            self._add_row(
                code=item.get("product_code",""), name=item.get("product_name",""),
                desc=item.get("description",""),  qty=item.get("quantity",1),
                unit=item.get("unit","Adet"),      delivery=item.get("delivery_time","2-3 Hafta"),
                price=item.get("unit_price",0),
            )

        # Vade bilgilerini yükle (varsa)
        v = offer.get("validity","30 Gün")
        vi = self.validity_combo.findText(v)
        if vi >= 0: self.validity_combo.setCurrentIndex(vi)
        pt = offer.get("payment_term","Peşin")
        pi = self.payment_combo.findText(pt)
        if pi >= 0: self.payment_combo.setCurrentIndex(pi)
        self.validity_note.setText(offer.get("validity_note",""))

        self._update_total(); self._set_step(0)
