"""
Teklif oluşturma — 3 adımlı wizard.
Adım 1: Müşteri  |  Adım 2: Ürünler  |  Adım 3: Özet + PDF Önizleme
"""
import logging, datetime, os, re
from pathlib import Path
from PySide6.QtGui import QPainter, QFont, QColor, QIntValidator, QShortcut, QKeySequence

from ui.widgets._section_card import make_section_card
from ui.widgets._row_hover_delegate import RowHoverDelegate
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QLineEdit, QComboBox,
    QMessageBox, QHeaderView, QFrame, QDialog, QDoubleSpinBox,
    QGridLayout, QGroupBox, QAbstractItemView, QStackedWidget,
    QScrollArea, QFileDialog, QDateEdit, QCheckBox,
    QStyle, QStyleOptionComboBox
)
from PySide6.QtCore import Qt, Signal, QDate, QEvent
from services.customer_service import CustomerService
from services.product_service import ProductService
from services.offer_service import OfferService
from models.customer import Customer
from models.offer import calculate_discount

logger = logging.getLogger("create_offer")
from core.constants import SYM_MAP, UNIT_LIST, DELIVERY_LIST
from core.formatting import fmt_money, fmt_number

UNITS      = UNIT_LIST + ["Rulo", "Ton", "M²", "M³", "Cm", "Mm"]
# "2-3 Hafta" satır eklemede varsayılan değer — listede mutlaka bulunmalı
DELIVERIES = ["Stokta Var", "1-2 Gün", "3-5 Gün", "2-3 Hafta"] + DELIVERY_LIST

# Satır yüksekliği — tüm hücre widget'ları bu fixed yüksekliği kullanır
ROW_H = 36


def _normalize_validity_text(value: str) -> str:
    """Manuel geçerlilik girişini PDF'de anlaşılır, etiketsiz biçime getir."""
    text = re.sub(r"\s*\(\s*manuel\s*\)\s*", "", (value or "").strip(),
                  flags=re.IGNORECASE).strip()
    if re.fullmatch(r"\d+", text):
        return f"{int(text)} Gün"
    match = re.fullmatch(r"(\d+)\s*g[üu]n", text, flags=re.IGNORECASE)
    if match:
        return f"{int(match.group(1))} Gün"
    match = re.fullmatch(r"(\d+)\s*ay", text, flags=re.IGNORECASE)
    if match:
        return f"{int(match.group(1))} Ay"
    return text


def _validity_days_for_input(value: str) -> str:
    """Kayıtlı geçerlilik değerinden yalnızca gün sayısını forma taşı."""
    text = (value or "").strip()
    match = re.fullmatch(r"(\d+)\s*(?:g[üu]n)?", text, flags=re.IGNORECASE)
    return str(int(match.group(1))) if match else ""


def _normalize_payment_text(value: str) -> str:
    """Sadece gün sayısı girildiyse ödeme metnini PDF için tamamla."""
    text = (value or "").strip()
    if re.fullmatch(r"\d+", text):
        return f"{int(text)} Gün Vadeli"
    match = re.fullmatch(
        r"(\d+)\s*g[üu]n(?:\s*vadeli)?", text, flags=re.IGNORECASE)
    if match:
        return f"{int(match.group(1))} Gün Vadeli"
    return text


def _payment_days_for_input(value: str) -> str:
    """Kayıtlı ödeme vadesinden yalnızca gün sayısını forma taşı."""
    text = (value or "").strip()
    match = re.fullmatch(
        r"(\d+)\s*(?:g[üu]n)?(?:\s*vadeli)?", text, flags=re.IGNORECASE)
    return str(int(match.group(1))) if match else ""


class _PlusButton(QPushButton):
    """Artı ikonunu QPainter ile tam merkeze çizen özel buton."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setText("")

    def paintEvent(self, event):
        super().paintEvent(event)          # arka plan + border (tema CSS'i)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        from ui.utils.theme_manager import get_theme
        p.setPen(QColor(get_theme()["text_primary"]))
        f = QFont()
        f.setPointSize(15)
        f.setWeight(QFont.Weight.Light)
        p.setFont(f)
        fm   = p.fontMetrics()
        br   = fm.boundingRect("+")
        x    = (self.width()  - br.width())  // 2 - br.x()
        y    = (self.height() - br.height()) // 2 - br.y()
        p.drawText(x, y, "+")
        p.end()


class _TableComboBox(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("table_combo")
        self.setEditable(True)
        self.lineEdit().setReadOnly(True)
        self.lineEdit().setObjectName("table_combo_editor")
        self.lineEdit().setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lineEdit().setCursor(Qt.CursorShape.PointingHandCursor)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.setFixedHeight(ROW_H)
        # Salt-seçim modunda yazıya tıklamak da listeyi açsın (sadece ok değil)
        self.lineEdit().installEventFilter(self)

    def eventFilter(self, obj, event):
        if (obj is self.lineEdit()
                and event.type() == QEvent.Type.MouseButtonPress
                and self.lineEdit().isReadOnly()):
            self.showPopup()
            return True
        return super().eventFilter(obj, event)


class _TableSpinBox(QDoubleSpinBox):
    """Tablo içi sayı girişi.

    - Tıklayınca/odaklanınca mevcut rakam otomatik seçilir → doğrudan
      üstüne yazılabilir, elle seçmeye gerek kalmaz.
    - empty_value verilirse: alan boş bırakılıp Enter'lanınca veya dışarı
      tıklanınca o değere döner (Adet için 1).
    """
    def __init__(self, empty_value=None, parent=None):
        super().__init__(parent)
        self.setObjectName("table_spin")
        self.setFixedHeight(ROW_H)
        self._empty_value = empty_value
        self._select_on_click = False

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self._select_on_click = True
        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, self.selectAll)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        # İlk tıklamada tümünü seç; sonraki tıklamalar normal imleç davranışı
        if self._select_on_click:
            self.selectAll()
            self._select_on_click = False

    def fixup(self, text: str) -> str:
        # Boş bırakıldıysa varsayılana dön (Enter veya odak kaybında çalışır)
        if self._empty_value is not None and not text.strip():
            return str(self._empty_value)
        return super().fixup(text)


def _wrap(widget):
    """Widget'ı doğrudan döndür — Qt setCellWidget hücreyi otomatik doldurur."""
    return widget


def _unwrap(cw):
    """Hücre widget'ını döndür."""
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
        from ui.utils.theme_manager import get_theme
        t = get_theme()
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(10)

        hdr = QHBoxLayout()
        title = QLabel("Ürün Seç")
        title.setStyleSheet("font-size:10pt;font-weight:700;")
        hdr.addWidget(title)
        hint = QLabel("Shift veya Ctrl ile çoklu seçim yapabilirsiniz")
        # Okunabilirlik için font artırımı (8pt -> 11pt) ve renk düzeltme
        hint.setStyleSheet(f"color:{t['text_secondary']}; font-size:11pt; font-weight:500;")
        hdr.addStretch(); hdr.addWidget(hint)
        layout.addLayout(hdr)

        search = QLineEdit()
        search.setPlaceholderText("Ürün kodu, adı veya açıklaması ile ara...")
        search.setMinimumHeight(34)
        search.textChanged.connect(self._on_filter_changed)
        self._search_edit = search

        # Kategori filtre combo
        self._cat_filter = QComboBox()
        self._cat_filter.setMinimumHeight(34)
        self._cat_filter.setMinimumWidth(150)
        self._load_category_filter()
        self._cat_filter.currentIndexChanged.connect(lambda _: self._on_filter_changed())

        filter_row = QHBoxLayout()
        filter_row.addWidget(search, 1)
        filter_row.addWidget(self._cat_filter)
        layout.addLayout(filter_row)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Kod","Ürün Adı","Fiyat","Para Birimi","Birim","Stok"])
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(0, 110); self.table.setColumnWidth(2, 90)
        self.table.setColumnWidth(3, 100); self.table.setColumnWidth(4, 70)
        self.table.setColumnWidth(5, 70)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        # Çoklu satır seçimi
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(False)
        self.table.doubleClicked.connect(self._select)
        # Diğer sayfalarla aynı tam satır hover davranışı
        self._hover_delegate = RowHoverDelegate(self)
        self.table.setItemDelegate(self._hover_delegate)
        self.table.setMouseTracking(True)
        self.table.viewport().setMouseTracking(True)
        self.table.viewport().installEventFilter(self)
        layout.addWidget(self.table)

        sel_lbl = QLabel("")
        sel_lbl.setObjectName("sel_lbl")
        sel_lbl.setStyleSheet(f"color:{t['accent_blue']}; font-size:11pt; font-weight:600;")
        self.table.itemSelectionChanged.connect(
            lambda: sel_lbl.setText(
                f"{len(self.table.selectedItems() and self.table.selectionModel().selectedRows() or [])} "
                f"satır seçili" if self.table.selectionModel().selectedRows() else ""
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

    def _load_category_filter(self):
        from services.category_service import CategoryService
        self._cat_filter.blockSignals(True)
        self._cat_filter.clear()
        self._cat_filter.addItem("Tüm Kategoriler", -1)
        self._cat_filter.addItem("Kategorisiz", None)
        try:
            for cat in CategoryService().get_all():
                self._cat_filter.addItem(cat.name, cat.id)
        except Exception as e:
            logger.debug("Kategori filtre yükleme atlandı: %s", e)
        self._cat_filter.blockSignals(False)

    def _on_filter_changed(self, _=None):
        keyword = self._search_edit.text().strip()
        cat_id = self._cat_filter.currentData()
        self._load(keyword, cat_id)

    def _load(self, keyword="", category_id=-1):
        if keyword:
            self._products = self._svc.search(keyword, category_id)
        else:
            self._products = self._svc.get_all(category_id)
        self.table.setRowCount(len(self._products))
        for row, p in enumerate(self._products):
            self.table.setItem(row, 0, QTableWidgetItem(p.product_code))
            self.table.setItem(row, 1, QTableWidgetItem(p.product_name))
            pi = QTableWidgetItem(fmt_number(p.price))
            pi.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row, 2, pi)
            self.table.setItem(row, 3, QTableWidgetItem(p.currency))
            self.table.setItem(row, 4, QTableWidgetItem(p.unit))
            stock_val = int(p.stock) if p.stock == int(p.stock) else p.stock
            si = QTableWidgetItem(str(stock_val))
            si.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row, 5, si)


    def eventFilter(self, obj, event):
        if obj is self.table.viewport():
            if event.type() == QEvent.Type.MouseMove:
                idx = self.table.indexAt(event.position().toPoint())
                row = idx.row() if idx.isValid() else -1
                if row != self._hover_delegate._hovered_row:
                    self._hover_delegate.set_hovered_row(row)
                    self.table.viewport().update()
            elif event.type() == QEvent.Type.Leave:
                self._hover_delegate.set_hovered_row(-1)
                self.table.viewport().update()
        return super().eventFilter(obj, event)

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

class _StepItem(QFrame):
    def __init__(self, number, text):
        super().__init__()
        self._number = number
        self.setObjectName("step_item")
        self.setFixedHeight(30)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 0, 8, 0)
        layout.setSpacing(7)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._badge = QLabel(number)
        self._badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._badge.setFixedSize(22, 22)
        self._badge.setObjectName("step_badge")

        self._text = QLabel(text)
        self._text.setObjectName("step_text")

        layout.addWidget(self._badge)
        layout.addWidget(self._text)

    def apply_state(self, state: str):
        """state: 'done' | 'active' | 'pending'"""
        from ui.utils.theme_manager import get_theme
        t = get_theme()

        base = "background: transparent; border: none;"

        if state == "done":
            self._badge.setText("✓")
            self._badge.setStyleSheet(
                f"background: {t['accent_green']}; color: white;"
                f"border-radius: 11px; font-weight: 700; font-size: 9.5pt;")
            self._text.setStyleSheet(
                f"{base} color: {t['text_primary']}; font-weight: 500; font-size: 10pt;")
            self.setStyleSheet("QFrame#step_item { background: transparent; border: none; }")
        elif state == "active":
            self._badge.setText(self._number)
            self._badge.setStyleSheet(
                f"background: {t['accent_blue']}; color: white;"
                f"border-radius: 11px; font-weight: 700; font-size: 9pt;")
            self._text.setStyleSheet(
                f"{base} color: {t['text_primary']}; font-weight: 500; font-size: 10pt;")
            self.setStyleSheet("QFrame#step_item { background: transparent; border: none; }")
        else:
            self._badge.setText(self._number)
            self._badge.setStyleSheet(
                f"background: transparent; color: {t['text_muted']};"
                f"border: 1px solid {t['border']}; border-radius: 11px; font-size: 9pt;")
            self._text.setStyleSheet(
                f"{base} color: {t['text_muted']}; font-weight: 400; font-size: 10pt;")
            self.setStyleSheet("QFrame#step_item { background: transparent; border: none; }")

class StepIndicator(QWidget):
    def __init__(self, steps):
        super().__init__()
        self.setFixedHeight(36)
        from ui.utils.theme_manager import get_theme
        t = get_theme()
        self.setStyleSheet(
            f"background: {t['bg_main']}; border: 1px solid {t['border']}; border-radius: 12px;")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(0)

        self._items = []
        self._lines = []
        for i, text in enumerate(steps):
            item = _StepItem(str(i + 1), text)
            layout.addWidget(item)
            self._items.append(item)

            if i < len(steps) - 1:
                line = QFrame()
                line.setFrameShape(QFrame.Shape.HLine)
                line.setFixedHeight(1)
                line.setObjectName("step_connector")
                layout.addWidget(line, 1)
                self._lines.append(line)

    def set_step(self, index):
        from ui.utils.theme_manager import get_theme
        t = get_theme()
        for i, item in enumerate(self._items):
            if i < index: state = "done"
            elif i == index: state = "active"
            else: state = "pending"
            item.apply_state(state)
        for j, line in enumerate(self._lines):
            done = j < index
            line.setStyleSheet(
                f"background: {t['accent_green'] if done else t['border']}; border: none;")


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
        self.current_currency  = "EUR"
        self._undo_stack       = []
        self._build_ui()

    # ──────────────────────────────────────────────────────── UI inşa ────────

    def _build_ui(self):
        main = QVBoxLayout(self)
        main.setContentsMargins(16, 10, 16, 12)
        main.setSpacing(6)

        # Başlık
        hdr = QHBoxLayout()
        self.title_lbl = QLabel("Yeni Teklif")
        self.title_lbl.setStyleSheet("font-size:14pt;font-weight:700;")
        hdr.addWidget(self.title_lbl)
        hdr.addStretch()

        # Tarih seçici — header içinde, teklif no'nun solunda
        self._selected_date = QDate.currentDate()
        self.date_display = QLineEdit()
        self.date_display.setReadOnly(True)
        self.date_display.setFixedWidth(90)
        self.date_display.setFixedHeight(28)
        self.date_display.setText(self._selected_date.toString("dd.MM.yyyy"))
        self.date_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.date_display.setObjectName("header_date_display")

        self.date_display.setCursor(Qt.CursorShape.PointingHandCursor)
        self.date_display.setToolTip("Teklif tarihini değiştir")
        self.date_display.mousePressEvent = lambda _e: self._pick_date()

        hdr.addWidget(self.date_display)
        hdr.addSpacing(12)

        self.offer_no_lbl = QLabel("")
        self.offer_no_lbl.setObjectName("offer_no_label")
        hdr.addWidget(self.offer_no_lbl)
        main.addLayout(hdr)

        # Adım göstergesi
        self.step_indicator = StepIndicator(["Müşteri", "Ürünler", "Özet & PDF"])
        main.addWidget(self.step_indicator)

        from ui.utils.theme_manager import get_theme as _gt
        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color:{_gt()['border']};"); main.addWidget(sep)

        # Sayfa yığını
        self.stack = QStackedWidget()
        self.stack.setContentsMargins(0, 4, 0, 0)
        main.addWidget(self.stack, 1)
        self.stack.addWidget(self._build_step1())
        self.stack.addWidget(self._build_step2())
        self.stack.addWidget(self._build_step3())

        # Alt navigasyon — Geri sol, eylemler + İleri sağ
        nav = QHBoxLayout()
        nav.setContentsMargins(0, 8, 0, 8); nav.setSpacing(12)

        self.btn_back = QPushButton("← Geri")
        self.btn_back.setObjectName("secondary")
        self.btn_back.setMinimumHeight(40); self.btn_back.setFixedWidth(120)
        self.btn_back.clicked.connect(self._go_back)
        nav.addWidget(self.btn_back)

        nav.addStretch()

        self.btn_preview = QPushButton("Önizleme")
        self.btn_preview.setObjectName("secondary")
        self.btn_preview.setMinimumHeight(40); self.btn_preview.setFixedWidth(130)
        self.btn_preview.clicked.connect(self._preview_pdf)
        self.btn_preview.setVisible(False)
        nav.addWidget(self.btn_preview)

        self.btn_finish = QPushButton("Teklifi Kaydet")
        self.btn_finish.setObjectName("primary")
        self.btn_finish.setMinimumHeight(40); self.btn_finish.setFixedWidth(140)
        self.btn_finish.clicked.connect(self._finish_offer)
        self.btn_finish.setVisible(False)
        nav.addWidget(self.btn_finish)

        self.btn_next = QPushButton("İleri →")
        self.btn_next.setObjectName("secondary")
        self.btn_next.setMinimumHeight(40); self.btn_next.setFixedWidth(140)
        self.btn_next.clicked.connect(self._go_next)
        nav.addWidget(self.btn_next)

        main.addLayout(nav)

        undo_sc = QShortcut(QKeySequence("Ctrl+Z"), self)
        undo_sc.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        undo_sc.activated.connect(self._undo_remove)

        self._set_step(0)

    # ──────────────────────────────────────────────────── Adım 1: Müşteri ───

    def _build_step1(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 10, 0, 0); layout.setSpacing(20)

        # --- Birleştirilmiş Kart: Müşteri Bilgileri ---
        card = QFrame(); card.setObjectName("step_card")
        l2 = QVBoxLayout(card)
        l2.setContentsMargins(20, 16, 20, 20); l2.setSpacing(12)

        t2 = QLabel("Müşteri Bilgileri"); t2.setObjectName("step_card_title")
        l2.addWidget(t2)

        # Form Grid
        fg = QGridLayout()
        fg.setSpacing(15)

        # 1. Satır: Firma Adı (Yeni/Eski) + İlgili Kişi
        lbl_co = QLabel("Firma Adı *"); lbl_co.setObjectName("step_form_label")
        self.customer_combo = QComboBox()
        self.customer_combo.setMinimumHeight(38)
        self.customer_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        self.customer_combo.currentIndexChanged.connect(self._on_customer_selected)
        self.company_edit = self.customer_combo

        # "+ Müşteri Ekle" butonu — combo ile aynı satırda
        self.btn_add_customer = _PlusButton()
        self.btn_add_customer.setObjectName("icon_btn")
        self.btn_add_customer.setFixedSize(38, 38)
        self.btn_add_customer.setToolTip("Yeni müşteri oluştur ve kaydet.")
        self.btn_add_customer.clicked.connect(self._open_add_customer)

        combo_row = QHBoxLayout()
        combo_row.setSpacing(8)
        combo_row.addWidget(self.customer_combo, 1)
        combo_row.addWidget(self.btn_add_customer)
        combo_wrap = QWidget()
        combo_wrap.setObjectName("combo_wrap")
        combo_wrap.setLayout(combo_row)
        combo_wrap.setStyleSheet("QWidget#combo_wrap { background: transparent; border: none; }")

        fg.addWidget(lbl_co, 0, 0)
        fg.addWidget(combo_wrap, 1, 0)

        # Gizli alanlar — müşteri seçilince otomatik doluyor, UI'da gösterilmiyor
        self.contact_edit = QLineEdit(); self.contact_edit.setVisible(False)
        self.address_edit = QLineEdit(); self.address_edit.setVisible(False)
        self.email_edit = QLineEdit(); self.email_edit.setVisible(False)
        self.phone_edit = QLineEdit(); self.phone_edit.setVisible(False)

        l2.addLayout(fg)
        layout.addWidget(card)

        layout.addStretch()
        return w

    # ──────────────────────────────────────────────────── Adım 2: Ürünler ───

    def _build_step2(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 10, 0, 4); layout.setSpacing(12)

        # Buton Çubuğu: Modern Pill Butonlar
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        add_btn = QPushButton("Ürün Ekle")
        add_btn.setObjectName("secondary")
        add_btn.setMinimumHeight(38)
        add_btn.clicked.connect(self._add_product)

        rem_btn = QPushButton("Ürün Çıkart")
        rem_btn.setObjectName("secondary")
        rem_btn.setMinimumHeight(38)
        rem_btn.clicked.connect(self._remove_selected_row)

        btn_row.addWidget(add_btn)
        btn_row.addWidget(rem_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        # Tablo
        self.prod_table = QTableWidget()
        self.prod_table.setColumnCount(8)
        self.prod_table.setHorizontalHeaderLabels(
            ["Malzeme Kodu","Ürün Adı","Açıklama","Adet","Birim","Teslim Süresi","Birim Fiyat","Toplam"])

        hh = self.prod_table.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        hh.setMinimumSectionSize(40)
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        hh.setSectionResizeMode(4, QHeaderView.ResizeMode.Interactive)
        hh.setSectionResizeMode(5, QHeaderView.ResizeMode.Interactive)
        hh.setSectionResizeMode(6, QHeaderView.ResizeMode.Interactive)
        hh.setSectionResizeMode(7, QHeaderView.ResizeMode.Interactive)

        self.prod_table.setColumnWidth(0, 110)
        self.prod_table.setColumnWidth(1, 180)
        self.prod_table.setColumnWidth(3,  72)
        self.prod_table.setColumnWidth(4,  80)
        self.prod_table.setColumnWidth(5, 110)
        self.prod_table.setColumnWidth(6, 115)
        self.prod_table.setColumnWidth(7, 115)

        self.prod_table.setAlternatingRowColors(False)
        self.prod_table.verticalHeader().setVisible(False)
        self.prod_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.prod_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        # Tam satır hover/seçim boyaması — diğer sayfalarla aynı görünüm.
        # Widget hücreleri (Adet/Birim/Teslim/Fiyat) transparan olduğundan
        # delegate'in boyadığı satır rengi altlarından kesintisiz görünür.
        self._row_delegate = RowHoverDelegate(self)
        for _c in range(8):
            self.prod_table.setItemDelegateForColumn(_c, self._row_delegate)
        self.prod_table.itemSelectionChanged.connect(self._on_prod_selection_changed)
        self.prod_table.setMouseTracking(True)
        self.prod_table.viewport().setMouseTracking(True)
        self.prod_table.viewport().installEventFilter(self)
        self.prod_table.installEventFilter(self)
        self._hovered_row = -1
        layout.addWidget(self.prod_table)

        # Toplam Satırı: Modern Badge
        total_row = QHBoxLayout()
        total_row.addStretch()
        self.total_lbl = QLabel("Genel Toplam: 0,00 €")
        self.total_lbl.setObjectName("total_badge")
        total_row.addWidget(self.total_lbl)
        layout.addLayout(total_row)
        return w

    # ──────────────────────────────────────────── Adım 3: Özet & PDF ────────

    def _build_step3(self):
        from ui.utils.theme_manager import get_theme
        t = get_theme()

        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 10, 0, 4); layout.setSpacing(15)

        # --- Kart: Teklif Koşulları ---
        card = QFrame(); card.setObjectName("step_card")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(16, 8, 16, 10); cl.setSpacing(6)

        title = QLabel("Teklif Koşulları"); title.setObjectName("step_card_title")
        cl.addWidget(title)

        # "condition_input": tema genelindeki 38px min-height yerine kompakt stil
        self.validity_edit = QLineEdit(); self.validity_edit.setObjectName("condition_input")
        self.validity_edit.setValidator(QIntValidator(1, 9999, self.validity_edit))
        self.validity_edit.setPlaceholderText("Örn. 10")
        self.validity_edit.textChanged.connect(lambda _: self._refresh_summary())

        self.payment_edit = QLineEdit(); self.payment_edit.setObjectName("condition_input")
        self.payment_edit.setValidator(QIntValidator(1, 9999, self.payment_edit))
        self.payment_edit.setPlaceholderText("Örn. 15")
        self.payment_edit.textChanged.connect(lambda _: self._refresh_summary())

        self.discount_spin = QLineEdit(); self.discount_spin.setObjectName("condition_input")
        self.discount_spin.setPlaceholderText("% 0")
        self.discount_spin.setValidator(QIntValidator(0, 100, self.discount_spin))
        self.discount_spin.setMaxLength(3)

        self.discount_visible_check = QCheckBox("PDF'de göster")
        self.discount_visible_check.setChecked(True)
        self.discount_visible_check.setEnabled(False)
        self.discount_spin.textChanged.connect(self._on_discount_value_changed)
        self.discount_visible_check.toggled.connect(lambda _: self._refresh_summary())

        self.validity_note = QLineEdit(); self.validity_note.setObjectName("condition_input")
        self.validity_note.setPlaceholderText("Ek not (opsiyonel)")
        self.validity_note.textChanged.connect(lambda _: self._refresh_summary())

        vg = QGridLayout()
        vg.setSpacing(8)
        vg.setColumnStretch(2, 1)

        l_val = QLabel("Geçerlilik (Gün) *"); l_val.setObjectName("step_form_label")
        l_pay = QLabel("Ödeme Vadesi (Gün) *"); l_pay.setObjectName("step_form_label")
        l_not = QLabel("Not"); l_not.setObjectName("step_form_label")
        l_dis = QLabel("İskonto (%)"); l_dis.setObjectName("step_form_label")

        vg.addWidget(l_val, 0, 0); vg.addWidget(self.validity_edit, 1, 0)
        vg.addWidget(l_pay, 0, 1); vg.addWidget(self.payment_edit, 1, 1)
        vg.addWidget(l_not, 0, 2); vg.addWidget(self.validity_note, 1, 2)
        vg.addWidget(l_dis, 0, 3); vg.addWidget(self.discount_spin, 1, 3)
        vg.addWidget(self.discount_visible_check, 2, 3)

        cl.addLayout(vg)
        layout.addWidget(card)

        # Özet — Modern Panel
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent;")
        
        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        self.summary_label.setTextFormat(Qt.TextFormat.RichText)
        self.summary_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        # Dinamik özet stili
        sum_bg = t['bg_card']
        sum_fg = t['text_primary']
        self.summary_label.setStyleSheet(f"""
            background-color: {sum_bg}; color: {sum_fg};
            border: 1px solid {t['border']};
            border-radius: 12px;
            padding: 18px;
            font-size: 10pt;
            line-height: 1.4;
        """)
        scroll.setWidget(self.summary_label)
        layout.addWidget(scroll, 1)

        return w

    # ──────────────────────────────────────────────── Wizard navigasyon ──────

    def _set_step(self, idx: int):
        self.stack.setCurrentIndex(idx)
        self.step_indicator.set_step(idx)
        self.btn_back.setEnabled(idx > 0)
        
        # Son Adım (2) Ayarları: Önizleme ve Kaydet göster, İleri gizle
        is_last = (idx == 2)
        self.btn_preview.setVisible(is_last)
        self.btn_finish.setVisible(is_last)
        self.btn_next.setVisible(not is_last)
        
        if is_last:
            self._refresh_summary()
        else:
            self.btn_next.setText("İleri →" if idx == 0 else "Özete Git →")

    def _go_next(self):
        cur = self.stack.currentIndex()
        if cur == 0:
            if not self._validate_step1(): return
            self._check_customer_registration()
            self._set_step(1)
        elif cur == 1:
            if not self._validate_products():
                return
            self._set_step(2)

    def _validate_products(self) -> bool:
        if self.prod_table.rowCount() == 0:
            QMessageBox.warning(self, "Eksik Ürün", "Teklife en az bir ürün ekleyin.")
            return False
        subtotal = self._calc_total()
        discount = self._discount_amount() if hasattr(self, "discount_spin") else 0.0
        if subtotal <= 0:
            QMessageBox.warning(self, "Geçersiz Toplam", "Teklif toplamı sıfırdan büyük olmalıdır.")
            return False
        if discount > subtotal:
            QMessageBox.warning(
                self, "Geçersiz İskonto",
                "İskonto tutarı ürünlerin toplam tutarından fazla olamaz.")
            return False
        return True

    def _validate_pdf_requirements(self) -> bool:
        """PDF için zorunlu manuel teklif koşullarını kontrol et."""
        missing = []
        if not _validity_days_for_input(self.validity_edit.text()):
            missing.append("• Teklif Geçerlilik Gün Sayısı (ör. 10)")
        if not _payment_days_for_input(self.payment_edit.text()):
            missing.append("• Ödeme Vadesi Gün Sayısı (ör. 45)")
        if not missing:
            return True

        QMessageBox.warning(
            self,
            "Zorunlu Alanları Doldurun",
            "PDF oluşturabilmek için aşağıdaki alanları manuel olarak doldurun:\n\n"
            + "\n".join(missing),
        )
        if not _validity_days_for_input(self.validity_edit.text()):
            self.validity_edit.setFocus()
        else:
            self.payment_edit.setFocus()
        return False

    def _check_customer_registration(self):
        """Müşteri kayıtlı değilse kaydetmeyi öner."""
        company = self.company_edit.currentText().strip()
        if not company or company == "-- Müşteri Seçin --":
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
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle("Müşteri Kaydı")
        box.setText(f"'{company}' sistemde kayıtlı değil.\nKaydetmek ister misiniz?")
        yes_btn = box.addButton("Evet", QMessageBox.ButtonRole.YesRole)
        no_btn = box.addButton("Hayır", QMessageBox.ButtonRole.NoRole)
        box.setDefaultButton(yes_btn)
        box.exec()
        if box.clickedButton() == yes_btn:
            try:
                new_id = self.customer_svc.add(Customer(
                    company_name=company,
                    contact_person=self.contact_edit.text().strip(),
                    address=self.address_edit.text().strip(),
                    phone=self.phone_edit.text().strip(),
                    email=self.email_edit.text().strip(),
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

    def _open_add_customer(self):
        """Yeni müşteri oluştur — combo'daki mevcut yazı prefill olarak gelir."""
        from ui.customers_page import CustomerDialog
        from services.customer_service import CustomerService

        # Varsa combo'da yazılı firma adını prefill et
        typed = self.company_edit.currentText().strip()
        if typed == "-- Müşteri Seçin --":
            typed = ""

        from models.customer import Customer as _C
        prefill = _C()
        prefill.company_name   = typed
        prefill.contact_person = self.contact_edit.text().strip()
        prefill.address        = self.address_edit.text().strip()
        prefill.phone          = self.phone_edit.text().strip()
        prefill.email          = self.email_edit.text().strip()

        dlg = CustomerDialog(self, prefill)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            svc = CustomerService()
            new_id = svc.add(dlg.get_customer())
            self._load_customers()
            # Yeni müşteriyi combo'da seç
            for i, c in enumerate(self._customers):
                if c.id == new_id:
                    self.customer_combo.setCurrentIndex(i + 1)  # +1: ilk "-- seçin --" öğesi
                    break
        except Exception as e:
            QMessageBox.warning(self, "Hata", f"Müşteri kaydedilemedi:\n{e}")

    def _validate_step1(self) -> bool:
        company = self.company_edit.currentText().strip()
        if not company or company == "-- Müşteri Seçin --":
            QMessageBox.warning(self, "Eksik Bilgi",
                "Firma adı zorunludur.\n"
                "Listeden müşteri seçin veya firma adını elle girin.")
            return False
        return True

    # ──────────────────────────────────────────────────── Özet paneli ────────

    def _refresh_summary(self):
        from ui.utils.theme_manager import get_theme
        t = get_theme()
        self.summary_label.setStyleSheet(f"""
            background-color: {t['bg_card']}; color: {t['text_primary']};
            border: 1px solid {t['border']};
            border-radius: 12px; padding: 18px; font-size: 10pt;
        """)
        offer = self._collect_data()
        if not offer:
            self.summary_label.setText(
                f"<p style='color:{t['text_muted']};'>Lütfen firma adı gibi zorunlu alanları doldurun.</p>")
            return

        from services.document_service import DocumentService
        html = DocumentService.generate_offer_summary_html(offer)
        self.summary_label.setText(html)

    # ──────────────────────────────────────────────────── Müşteri ────────────

    def eventFilter(self, obj, event):
        if hasattr(self, "prod_table"):
            if obj in (self.prod_table, self.prod_table.viewport()):
                if event.type() == QEvent.Type.Leave:
                    self._set_hovered_row(-1)
                elif event.type() == QEvent.Type.MouseMove:
                    pos = event.position().toPoint()
                    if obj is self.prod_table:
                        pos = self.prod_table.viewport().mapFromParent(pos)
                    idx = self.prod_table.indexAt(pos)
                    self._set_hovered_row(idx.row() if idx.isValid() else -1)
            elif (event.type() == QEvent.Type.Enter
                  and isinstance(obj, (QDoubleSpinBox, QComboBox))):
                # İmleç hücre widget'ının üzerine geldi — viewport MouseMove almaz,
                # satırı widget'ın konumundan bul
                from PySide6.QtCore import QPoint
                pos = obj.mapTo(self.prod_table.viewport(), QPoint(1, 1))
                idx = self.prod_table.indexAt(pos)
                self._set_hovered_row(idx.row() if idx.isValid() else -1)
        return super().eventFilter(obj, event)

    def _set_hovered_row(self, row: int):
        if row != self._hovered_row:
            self._hovered_row = row
            self._row_delegate.set_hovered_row(row)
            self.prod_table.viewport().update()

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
            # Boş seçim: alanları temizle (Firma adı hariç, kullanıcı bir şey yazıyor olabilir)
            self.address_edit.clear()
            self.contact_edit.clear()
            self.email_edit.clear()
            self.phone_edit.clear()
            return
        c = self._customers[index - 1]
        self.address_edit.setText(c.address)
        self.contact_edit.setText(c.contact_person)
        self.email_edit.setText(c.email)
        self.phone_edit.setText(c.phone)
        logger.debug("Müşteri seçildi: %s", c.company_name)

    # ──────────────────────────────────────────────────── Ürün tablosu ───────

    def _add_product(self):
        dlg = ProductSelectDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted: return
        low_stock = []
        incompatible_currency = []
        for p in dlg.selected_products:
            product_currency = (p.currency or "EUR").strip().upper()
            if (self.prod_table.rowCount() > 0
                    and product_currency != self.current_currency):
                incompatible_currency.append(
                    f"{p.product_code} — {p.product_name} ({product_currency})")
                continue
            self._add_row(code=p.product_code, name=p.product_name,
                          desc=p.description, unit=p.unit, price=p.price,
                          currency=product_currency)
            # Stok uyarısı — 0 veya düşükse bildir
            if p.stock is not None and p.stock <= 0:
                low_stock.append(f"{p.product_code} — {p.product_name} (Stok: {p.stock:.0f})")
        if incompatible_currency:
            QMessageBox.warning(
                self, "Para Birimi Uyuşmazlığı",
                "Bir teklifte yalnızca tek para birimi kullanılabilir.\n\n"
                f"Bu teklifin para birimi: {self.current_currency}\n\n"
                "Aşağıdaki ürünler farklı para biriminde kayıtlı olduğu için eklenmedi:\n"
                + "\n".join(f"• {item}" for item in incompatible_currency)
            )
        if low_stock:
            QMessageBox.warning(
                self, "Stok Uyarısı",
                "Aşağıdaki ürünlerin stoğu yetersiz veya sıfır:\n\n"
                + "\n".join(f"• {s}" for s in low_stock)
                + "\n\nTeklif oluşturmaya devam edebilirsiniz."
            )

    def _add_row(self, code="", name="", desc="", qty=1.0,
                 unit="Adet", delivery="2-3 Hafta", price=0.0,
                 currency=None):
        row = self.prod_table.rowCount()
        if row == 0 and currency:
            self.current_currency = currency
        self.prod_table.insertRow(row)
        self.prod_table.setRowHeight(row, ROW_H)

        def item(text, user_data=None, editable=True):
            it = QTableWidgetItem(str(text))
            it.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            if user_data is not None: it.setData(Qt.ItemDataRole.UserRole, user_data)
            if not editable:
                it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
            return it

        self.prod_table.setItem(row, 0, item(code, editable=False))
        self.prod_table.setItem(row, 1, item(name, editable=False))
        self.prod_table.setItem(row, 2, item(desc, editable=False))

        qty_spin = _TableSpinBox(empty_value=1)
        qty_spin.setMinimum(1)
        qty_spin.setMaximum(999999)
        qty_spin.setDecimals(0)
        qty_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        qty_spin.setKeyboardTracking(False)
        qty_spin.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        qty_spin.setStepType(QDoubleSpinBox.StepType.AdaptiveDecimalStepType)
        qty_spin.setValue(int(round(qty)) if qty == int(qty) else qty)
        qty_spin.valueChanged.connect(lambda _, w=qty_spin: self._recalc_by_widget(w, 3))
        self.prod_table.setCellWidget(row, 3, _wrap(qty_spin))

        unit_cb = _TableComboBox()
        unit_cb.addItems(UNITS)
        u_idx = unit_cb.findText(unit)
        if u_idx >= 0: unit_cb.setCurrentIndex(u_idx)
        else: unit_cb.setCurrentText(unit)
        unit_cb.currentTextChanged.connect(
            lambda *_: self._fit_combo_column(4, 80))
        self.prod_table.setCellWidget(row, 4, _wrap(unit_cb))

        del_cb = _TableComboBox()
        del_cb.addItems(DELIVERIES)
        # Teslim süresi serbest metin de olabilir: "2 Gün", "1 Ay" gibi
        # değerler elle yazılabilir (listeden seçmek zorunlu değil)
        del_cb.lineEdit().setReadOnly(False)
        del_cb.lineEdit().setCursor(Qt.CursorShape.IBeamCursor)
        del_cb.setToolTip("Listeden seçin veya elle yazın (örn. 2 Gün, 1 Ay)")
        d_idx = del_cb.findText(delivery)
        if d_idx >= 0: del_cb.setCurrentIndex(d_idx)
        else: del_cb.setCurrentText(delivery)
        del_cb.editTextChanged.connect(
            lambda *_: self._fit_combo_column(5, 110))
        self.prod_table.setCellWidget(row, 5, _wrap(del_cb))

        price_spin = _TableSpinBox()
        price_spin.setMaximum(9_999_999); price_spin.setDecimals(2); price_spin.setValue(price)
        price_spin.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        price_spin.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        price_spin.setGroupSeparatorShown(True)
        price_spin.valueChanged.connect(lambda _, w=price_spin: self._recalc_by_widget(w, 6))
        self.prod_table.setCellWidget(row, 6, _wrap(price_spin))

        sym = SYM_MAP.get(self.current_currency, "€")
        total_item = QTableWidgetItem(fmt_money(qty * price, sym))
        total_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        total_item.setFlags(total_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.prod_table.setItem(row, 7, total_item)
        self.prod_table.setRowHeight(row, ROW_H)
        # Widget üzerindeyken hover satırını takip edebilmek için
        for w in (qty_spin, unit_cb, del_cb, price_spin):
            w.installEventFilter(self)
        self._fit_combo_column(4, 80)
        self._fit_combo_column(5, 110)
        self._update_total()
        self._on_prod_selection_changed()

    def _fit_combo_column(self, col: int, minimum: int):
        """Combo sütununu içerideki en geniş seçime göre boyutlandırır.

        'Metre' gibi uzun değerler seçilince metin kesilmesin; ok için
        pay bırakılır."""
        need = minimum
        for r in range(self.prod_table.rowCount()):
            w = _unwrap(self.prod_table.cellWidget(r, col))
            if w is not None:
                text_w = w.fontMetrics().horizontalAdvance(w.currentText())
                need = max(need, text_w + 54)   # dolgu + açılır ok payı
        if self.prod_table.columnWidth(col) != need:
            self.prod_table.setColumnWidth(col, need)

    def _on_prod_selection_changed(self):
        self._update_prod_row_states()

    def _update_prod_row_states(self):
        """Seçili satırın combo/spin hücrelerine beyaz metin rengini yansıt.

        Hover ve seçim arka planını RowHoverDelegate boyar; widget'lar
        transparan kaldığı için burada yalnızca metin rengi yönetilir."""
        selected_rows = set(idx.row() for idx in self.prod_table.selectionModel().selectedRows())
        for r in range(self.prod_table.rowCount()):
            is_selected = r in selected_rows
            for col in (3, 4, 5, 6):
                w = _unwrap(self.prod_table.cellWidget(r, col))
                if w is None:
                    continue
                w.setProperty("rowSelected", is_selected)
                w.style().unpolish(w)
                w.style().polish(w)

    def _recalc_by_widget(self, widget, col: int):
        for r in range(self.prod_table.rowCount()):
            cw = self.prod_table.cellWidget(r, col)
            actual = _unwrap(cw)
            if actual is widget:
                self._recalc_row(r); return

    def _recalc_row(self, row):
        qty_w = _unwrap(self.prod_table.cellWidget(row, 3))
        prc_w = _unwrap(self.prod_table.cellWidget(row, 6))
        if qty_w and prc_w:
            ti = self.prod_table.item(row, 7)
            sym = SYM_MAP.get(self.current_currency, "€")
            if ti: ti.setText(fmt_money(qty_w.value() * prc_w.value(), sym))
        self._update_total()

    def _remove_selected_row(self):
        rows = sorted(set(idx.row() for idx in
                         self.prod_table.selectionModel().selectedRows()), reverse=True)
        if not rows:
            QMessageBox.information(self, "Bilgi", "Lütfen kaldırılacak satırı seçin.")
            return
        batch = []
        for r in rows:
            code_i = self.prod_table.item(r, 0)
            name_i = self.prod_table.item(r, 1)
            desc_i = self.prod_table.item(r, 2)
            qty_w  = _unwrap(self.prod_table.cellWidget(r, 3))
            unit_w = _unwrap(self.prod_table.cellWidget(r, 4))
            del_w  = _unwrap(self.prod_table.cellWidget(r, 5))
            prc_w  = _unwrap(self.prod_table.cellWidget(r, 6))
            batch.append({
                "code": code_i.text() if code_i else "",
                "name": name_i.text() if name_i else "",
                "desc": desc_i.text() if desc_i else "",
                "qty":  qty_w.value() if qty_w else 1,
                "unit": unit_w.currentText() if unit_w else "Adet",
                "delivery": del_w.currentText() if del_w else "2-3 Hafta",
                "price": prc_w.value() if prc_w else 0,
            })
            self.prod_table.removeRow(r)
        if batch:
            self._undo_stack.append(batch)
        self._update_total()
        main_win = self.window()
        if hasattr(main_win, 'show_status'):
            main_win.show_status(f"{len(batch)} satır kaldırıldı — Ctrl+Z ile geri al")

    def _undo_remove(self):
        if not self._undo_stack:
            return
        batch = self._undo_stack.pop()
        for item in reversed(batch):
            self._add_row(
                code=item["code"], name=item["name"], desc=item["desc"],
                qty=item["qty"], unit=item["unit"], delivery=item["delivery"],
                price=item["price"], currency=self.current_currency)
        self._update_total()

    def _read_row(self, row: int) -> dict:
        """Belirtilen satırdaki tüm değerleri dict olarak oku."""
        code_i = self.prod_table.item(row, 0)
        name_i = self.prod_table.item(row, 1)
        desc_i = self.prod_table.item(row, 2)
        qty_w  = _unwrap(self.prod_table.cellWidget(row, 3))
        unit_w = _unwrap(self.prod_table.cellWidget(row, 4))
        del_w  = _unwrap(self.prod_table.cellWidget(row, 5))
        prc_w  = _unwrap(self.prod_table.cellWidget(row, 6))
        return {
            "code": code_i.text() if code_i else "",
            "name": name_i.text() if name_i else "",
            "desc": desc_i.text() if desc_i else "",
            "qty":  qty_w.value() if qty_w else 1,
            "unit": unit_w.currentText() if unit_w else "Adet",
            "delivery": del_w.currentText() if del_w else "2-3 Hafta",
            "price": prc_w.value() if prc_w else 0,
        }

    def _swap_rows(self, row_a: int, row_b: int):
        """İki satırın verilerini takas eder."""
        if row_a < 0 or row_b < 0:
            return
        if row_a >= self.prod_table.rowCount() or row_b >= self.prod_table.rowCount():
            return
        a = self._read_row(row_a)
        b = self._read_row(row_b)
        self._write_row(row_a, b)
        self._write_row(row_b, a)
        self.prod_table.selectRow(row_b)

    def _write_row(self, row: int, data: dict):
        """Belirtilen satıra dict verilerini yazar."""
        if self.prod_table.item(row, 0):
            self.prod_table.item(row, 0).setText(data["code"])
        if self.prod_table.item(row, 1):
            self.prod_table.item(row, 1).setText(data["name"])
        if self.prod_table.item(row, 2):
            self.prod_table.item(row, 2).setText(data["desc"])
        qty_w = _unwrap(self.prod_table.cellWidget(row, 3))
        if qty_w:
            qty_w.setValue(data["qty"])
        unit_w = _unwrap(self.prod_table.cellWidget(row, 4))
        if unit_w:
            idx = unit_w.findText(data["unit"])
            if idx >= 0:
                unit_w.setCurrentIndex(idx)
            else:
                unit_w.setCurrentText(data["unit"])
        del_w = _unwrap(self.prod_table.cellWidget(row, 5))
        if del_w:
            idx = del_w.findText(data["delivery"])
            if idx >= 0:
                del_w.setCurrentIndex(idx)
            else:
                del_w.setCurrentText(data["delivery"])
        prc_w = _unwrap(self.prod_table.cellWidget(row, 6))
        if prc_w:
            prc_w.setValue(data["price"])
        self._recalc_row(row)

    def _move_row_up(self):
        """Seçili satırı bir üst satırla takas eder."""
        rows = sorted(set(idx.row() for idx in
                         self.prod_table.selectionModel().selectedRows()))
        if not rows:
            return
        if len(rows) == 1:
            r = rows[0]
            if r > 0:
                self._swap_rows(r, r - 1)
                self.prod_table.selectRow(r - 1)

    def _move_row_down(self):
        """Seçili satırı bir alt satırla takas eder."""
        rows = sorted(set(idx.row() for idx in
                         self.prod_table.selectionModel().selectedRows()))
        if not rows:
            return
        if len(rows) == 1:
            r = rows[0]
            if r < self.prod_table.rowCount() - 1:
                self._swap_rows(r, r + 1)
                self.prod_table.selectRow(r + 1)

    def _load_from_template(self):
        """Kayıtlı şablondan ürün kalemlerini tabloya yükler."""
        from services.template_service import TemplateService
        svc = TemplateService()
        templates = svc.get_all()
        if not templates:
            QMessageBox.information(
                self, "Şablon Yok",
                "Henüz kayıtlı şablon bulunmuyor.\n\n"
                "Dashboard'da bir teklife sağ tıklayıp 'Şablon Olarak Kaydet' "
                "ile şablon oluşturabilirsiniz.")
            return
        from PySide6.QtWidgets import QInputDialog
        names = [f"{t.template_name}  ({len(t.items)} kalem, {t.currency})"
                 for t in templates]
        chosen, ok = QInputDialog.getItem(
            self, "Şablon Seç", "Yüklenecek şablonu seçin:", names, 0, False)
        if not ok:
            return
        idx = names.index(chosen)
        tmpl = templates[idx]
        if self.prod_table.rowCount() > 0:
            box = QMessageBox(self)
            box.setWindowTitle("Mevcut Kalemler")
            box.setText("Tabloda zaten ürün var.\nŞablon kalemleri nasıl eklensin?")
            btn_add = box.addButton("Mevcut Listeye Ekle", QMessageBox.ButtonRole.AcceptRole)
            btn_replace = box.addButton("Listeyi Temizle ve Yükle", QMessageBox.ButtonRole.DestructiveRole)
            box.addButton("İptal", QMessageBox.ButtonRole.RejectRole)
            box.exec()
            clicked = box.clickedButton()
            if clicked == btn_replace:
                while self.prod_table.rowCount() > 0:
                    self.prod_table.removeRow(0)
            elif clicked != btn_add:
                return
        if (self.prod_table.rowCount() > 0
                and tmpl.currency != self.current_currency):
            QMessageBox.warning(
                self, "Para Birimi Uyuşmazlığı",
                f"Şablonun para birimi ({tmpl.currency}) tablodaki mevcut "
                f"ürünlerin para birimiyle ({self.current_currency}) uyuşmuyor.\n\n"
                "Bir teklifte yalnızca tek para birimi kullanılabilir.")
            return
        for item in tmpl.items:
            self._add_row(
                code=item.product_code, name=item.product_name,
                desc=item.description, qty=item.quantity,
                unit=item.unit, delivery=item.delivery_time,
                price=item.unit_price, currency=tmpl.currency)

    def _update_total(self, *_):
        sym = SYM_MAP.get(self.current_currency, "€")
        subtotal = self._calc_total()
        disc_val = self._discount_amount() if hasattr(self, 'discount_spin') else 0.0
        net = subtotal - disc_val
        self.total_lbl.setText(f"Genel Toplam: {fmt_money(net, sym)}")

    def _discount_type(self) -> str:
        return "percent"

    def _discount_value(self) -> float:
        return float(self.discount_spin.text() or 0)

    def _discount_amount(self) -> float:
        return calculate_discount(
            self._calc_total(), self._discount_type(), self._discount_value())

    def _on_discount_value_changed(self, text: str):
        val = float(text or 0)
        self.discount_visible_check.setEnabled(val > 0)
        try:
            self._update_total()
        except ValueError:
            pass
        self._refresh_summary()

    def _calc_total(self) -> float:
        return sum(
            (_unwrap(self.prod_table.cellWidget(r,3)).value()
             if _unwrap(self.prod_table.cellWidget(r,3)) else 0) *
            (_unwrap(self.prod_table.cellWidget(r,6)).value()
             if _unwrap(self.prod_table.cellWidget(r,6)) else 0)
            for r in range(self.prod_table.rowCount())
        )

    # ──────────────────────────────────────────────── Veri toplama & kayıt ───

    def _collect_data(self) -> 'Optional[Offer]':
        company = self.company_edit.currentText().strip()
        if not company: return None
        from models.offer import Offer
        from models.offer_item import OfferItem
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
            items.append(OfferItem(
                id=None, offer_id=self._current_offer_id,
                product_id=code_i.data(Qt.ItemDataRole.UserRole) if code_i else None,
                product_code=code_i.text() if code_i else "",
                product_name=name_i.text() if name_i else "",
                description=desc_i.text() if desc_i else "",
                quantity=qty, unit=unit_w.currentText() if unit_w else "Adet",
                delivery_time=del_w.currentText()  if del_w  else "2-3 Hafta",
                unit_price=price, total_price=qty * price,
            ))
        date_str = self._selected_date.toString("yyyy-MM-dd")
        return Offer(
            id=self._current_offer_id, offer_no=self._offer_no,
            customer_id=self.customer_combo.currentData(), company_name=company,
            customer_address=self.address_edit.text().strip(),
            contact_person=self.contact_edit.text().strip(),
            customer_phone=self.phone_edit.text().strip(),
            customer_email=self.email_edit.text().strip(),
            date=date_str, currency=self.current_currency,
            total_amount=self._calc_total() - self._discount_amount(),
            discount_amount=self._discount_amount(),
            discount_type=self._discount_type(),
            discount_value=self._discount_value(),
            show_discount=self.discount_visible_check.isChecked(),
            items=items, validity=_normalize_validity_text(
                self.validity_edit.text()),
            validity_note=self.validity_note.text().strip(),
            payment_term=_normalize_payment_text(self.payment_edit.text()),
            status=self._current_status,
        )

    def _pick_date(self):
        """Takvim dialogı açarak tarih seçtirir."""
        from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout,
                                        QDialogButtonBox, QCalendarWidget as _Cal,
                                        QPushButton as _Btn)
        from PySide6.QtCore import Qt as _Qt
        from ui.utils.theme_manager import get_theme

        t = get_theme()
        is_dark = t["name"] == "dark"
        _bg = t["bg_dialog"]; _bg_cell = t["bg_card"]; _fg = t["text_primary"]
        _fg_muted = t["text_muted"]; _accent = t["accent_blue"]
        _nav_bg = "#0f3460" if not is_dark else "#162040"
        _hover_cell = t["bg_sidebar_hover"]; _grid = t["grid_color"]
        _border = t["border_input"]; _sel_border = "#3a7bd5" if not is_dark else "#5a9bf5"

        dlg = QDialog(self)
        dlg.setWindowTitle("Tarih Seçin")
        dlg.setFixedSize(400, 320)
        vlay = QVBoxLayout(dlg)
        cal = _Cal(dlg)
        cal.setSelectedDate(self._selected_date)
        cal.setVerticalHeaderFormat(_Cal.VerticalHeaderFormat.NoVerticalHeader)
        cal.setNavigationBarVisible(True)
        # ─── Takvim stili ───
        cal.setStyleSheet(f"""
            QCalendarWidget {{
                background: {_bg};
            }}
            QCalendarWidget QWidget#qt_calendar_navigationbar {{
                background: {_nav_bg};
                min-height: 40px;
            }}
            QCalendarWidget QToolButton {{
                background: transparent;
                color: #ffffff;
                border: none;
                border-radius: 4px;
                font-size: 10pt;
                font-weight: 600;
                padding: 4px 8px;
            }}
            QCalendarWidget QToolButton:hover {{
                background: rgba(255,255,255,0.18);
            }}
            QCalendarWidget QToolButton:pressed {{
                background: rgba(255,255,255,0.30);
            }}
            QCalendarWidget QToolButton#qt_calendar_prevmonth,
            QCalendarWidget QToolButton#qt_calendar_nextmonth {{
                font-size: 13pt;
                padding: 4px 10px;
            }}
            QCalendarWidget QAbstractItemView {{
                background: {_bg_cell};
                color: {_fg};
                selection-background-color: {_accent};
                selection-color: #ffffff;
                gridline-color: {_grid};
                outline: none;
            }}
            QCalendarWidget QAbstractItemView::item:selected {{
                background: {_accent};
                color: #ffffff;
                border: 2px solid {_sel_border};
                border-radius: 4px;
            }}
            QCalendarWidget QAbstractItemView::item:hover {{
                background: {_hover_cell};
                border-radius: 4px;
            }}
            QCalendarWidget QSpinBox {{
                background: transparent;
                color: #ffffff;
                border: none;
                font-size: 10pt;
                font-weight: 600;
            }}
            QCalendarWidget QSpinBox::up-button,
            QCalendarWidget QSpinBox::down-button {{ width: 0; }}
            QCalendarWidget QMenu {{
                background: {_bg_cell};
                color: {_fg};
                border: 1px solid {_border};
            }}
        """)
        # Ay dropdown menüsü top-level QMenu — direkt stil uygula
        from PySide6.QtWidgets import QToolButton as _TB
        _MENU_SS = (
            f"QMenu {{ background:{_bg_cell}; color:{_fg}; border:1px solid {_border}; }}"
            f"QMenu::item {{ padding:5px 20px; color:{_fg}; background:transparent; }}"
            f"QMenu::item:selected {{ background:{_accent}; color:#ffffff; }}"
        )
        for _tb in cal.findChildren(_TB):
            if _tb.menu(): _tb.menu().setStyleSheet(_MENU_SS)

        btn_ok = _Btn("Seç"); btn_cancel = _Btn("İptal")
        btn_ok.setMinimumHeight(32); btn_cancel.setMinimumHeight(32)
        btn_ok.setObjectName("primary"); btn_cancel.setObjectName("secondary")
        btn_ok.clicked.connect(dlg.accept); btn_cancel.clicked.connect(dlg.reject)

        btn_row = QHBoxLayout()
        btn_row.addStretch(); btn_row.addWidget(btn_cancel); btn_row.addWidget(btn_ok)
        vlay.addWidget(cal); vlay.addLayout(btn_row)

        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._selected_date = cal.selectedDate()
            self.date_display.setText(self._selected_date.toString("dd.MM.yyyy"))


    def _preview_pdf(self):
        if not self._validate_step1():
            return
        if not self._validate_products():
            return
        if not self._validate_pdf_requirements():
            return
        data = self._collect_data()
        if not data:
            QMessageBox.warning(self, "Eksik Bilgi", "Lütfen zorunlu alanları doldurun.")
            return

        import tempfile
        import os
        from pdf.pdf_generator import generate_pdf

        preview_dir = Path(tempfile.gettempdir()) / "TeklifOnizleme"
        preview_dir.mkdir(exist_ok=True)
        for old in preview_dir.glob("*.pdf"):
            try:
                old.unlink()
            except OSError:
                pass
        temp_path = str(preview_dir / f"{data.offer_no or 'Teklif'}.pdf")

        try:
            generate_pdf(data, temp_path)
            from ui.dialogs.pdf_preview_dialog import PdfPreviewDialog
            dlg = PdfPreviewDialog(
                pdf_path=temp_path, parent=self,
                offer_no=data.offer_no or "",
                customer_email=data.customer_email or "",
            )
            dlg.exec()
        except Exception as e:
            QMessageBox.warning(self, "Hata", f"PDF Önizleme oluşturulamadı:\n{e}")

    def _finish_offer(self):
        if not self._validate_step1():
            return
        if not self._validate_products():
            return
        if not self._validate_pdf_requirements():
            return

        data = self._collect_data()
        if not data: return

        # 2. Kayıt konumu sor
        from pathlib import Path as _Path
        desktop = _Path.home() / "Desktop"
        if not desktop.exists(): desktop = _Path.home()
        default_file = str(desktop / f"{self._offer_no}.pdf")
        
        out_path, _ = QFileDialog.getSaveFileName(
            self, "PDF Kaydet", default_file, "PDF Dosyası (*.pdf)")
        
        if not out_path:
            # Kullanıcı iptal etti
            return
            
        # 3. DB'ye kaydet ve PDF'i üret
        try:
            oid = self.offer_svc.save(data)
            self._current_offer_id = oid
            self._is_new = False
            
            from pdf.pdf_generator import generate_pdf
            from core.app_paths import PDF_DIR
            
            PDF_DIR.mkdir(parents=True, exist_ok=True)
            backup = str(PDF_DIR / f"{self._offer_no}.pdf")
            generate_pdf(data, out_path)
            
            if out_path != backup:
                import shutil as _shutil
                try:
                    _shutil.copy2(out_path, backup)
                except Exception as e:
                    logger.warning("PDF yedegi kopyalanamadi: %s", e)
                
            logger.info("PDF oluşturuldu ve kaydedildi: %s", out_path)

            box = QMessageBox(self)
            box.setWindowTitle("Teklif Kaydedildi")
            box.setText(f"Teklif kaydedildi ve PDF oluşturuldu.\n{out_path}")
            btn_preview = box.addButton("Önizle",      QMessageBox.ButtonRole.AcceptRole)
            btn_mail    = box.addButton("Mail Gönder", QMessageBox.ButtonRole.ActionRole)
            btn_close   = box.addButton("Kapat",       QMessageBox.ButtonRole.RejectRole)
            btn_preview.setMinimumWidth(90)
            btn_mail.setMinimumWidth(130)
            btn_close.setMinimumWidth(80)
            box.exec()
            clicked = box.clickedButton()
            if clicked == btn_preview:
                import os as _os
                _os.startfile(out_path)
            elif clicked == btn_mail:
                from ui.dialogs.email_dialog import EmailDialog
                from core.config import load_company_config
                from core.credential_store import get_smtp_password
                cfg = load_company_config()
                if not cfg.get("smtp_server") or not cfg.get("smtp_user"):
                    QMessageBox.warning(self, "E-Posta Ayarı Eksik",
                        "E-posta göndermek için önce:\n"
                        "Ayarlar → E-Posta Ayarları\n"
                        "bölümünden SMTP bilgilerinizi girin.")
                else:
                    dlg = EmailDialog(
                        pdf_path=out_path,
                        customer_email=data.customer_email or "",
                        offer_no=self._offer_no,
                        parent=self,
                    )
                    dlg.exec()

            self._reset_to_new()
            self.offer_saved.emit()
            
        except Exception as e:
            logger.error("Tamamlama hatası: %s", e, exc_info=True)
            QMessageBox.warning(self, "Hata", f"İşlem tamamlanamadı:\n{e}")

    # ──────────────────────────────────────────────────── Sıfırla / Yükle ───

    def _reset_to_new(self):
        self._current_offer_id = None; self._original_date = ""
        self._is_new = True; self._undo_stack = []
        self._offer_no = self.offer_svc.preview_offer_no()
        self.offer_no_lbl.setText(self._offer_no)
        self.title_lbl.setText("Yeni Teklif")
        self._load_customers()
        self.company_edit.setCurrentIndex(0); self.address_edit.clear(); self.contact_edit.clear()
        self.email_edit.clear(); self.phone_edit.clear()
        self._selected_date = QDate.currentDate()
        self.date_display.setText(self._selected_date.toString("dd.MM.yyyy"))
        self.current_currency = "EUR"
        self.prod_table.setRowCount(0)
        self.validity_edit.clear()
        self.payment_edit.clear()
        self.validity_note.clear()
        if hasattr(self, 'discount_spin'):
            self.discount_spin.blockSignals(True)
            self.discount_spin.setText("")
            self.discount_spin.blockSignals(False)
            self.discount_visible_check.setChecked(True)
            self.discount_visible_check.setEnabled(False)
        self._update_total(); self._set_step(0)

    def is_dirty(self) -> bool:
        """Kullanıcı form üzerinde kaydedilmemiş değişiklik yaptı mı?"""
        company = self.company_edit.currentText().strip()
        if company and company != "-- Müşteri Seçin --":
            return True
        if hasattr(self, "prod_table") and self.prod_table.rowCount() > 0:
            return True
        return False

    def on_enter(self):
        self._load_customers()
        if self._is_new and not self._offer_no:
            self._offer_no = self.offer_svc.preview_offer_no()
            logger.info("İlk teklif numarası: %s", self._offer_no)
            self.offer_no_lbl.setText(self._offer_no)

    def clone_offer(self, offer_id: int):
        """Mevcut teklifi kopyalayarak yeni bir teklif oluşturur."""
        self.load_offer(offer_id)
        self._current_offer_id = None
        self._is_new = True
        self._offer_no = self.offer_svc.preview_offer_no()
        self.offer_no_lbl.setText(self._offer_no)
        self.title_lbl.setText("Kopyalanan Yeni Teklif")
        self._selected_date = QDate.currentDate()
        self.date_display.setText(self._selected_date.toString("dd.MM.yyyy"))
        # Kopya da yeni tekliftir; koşullar eski tekliften taşınmaz.
        self.validity_edit.clear()
        self.payment_edit.clear()
        self._set_step(0)

    def load_offer(self, offer_id: int):
        offer = self.offer_svc.get_by_id(offer_id)
        if not offer: return
        self._current_offer_id = offer_id
        self._offer_no         = offer.offer_no
        self._is_new           = False
        self.offer_no_lbl.setText(self._offer_no)
        self.title_lbl.setText("Teklif Düzenle")

        if offer.date:
            d = QDate.fromString(offer.date, "yyyy-MM-dd")
            if not d.isValid():
                d = QDate.fromString(offer.date, "dd.MM.yyyy")
            if d.isValid():
                self._selected_date = d
                self.date_display.setText(d.toString("dd.MM.yyyy"))
        else:
            self._selected_date = QDate.currentDate()
            self.date_display.setText(self._selected_date.toString("dd.MM.yyyy"))

        # Müşteri listesini yükle — sinyalleri tamamen blokla
        self.customer_combo.blockSignals(True)
        self._load_customers()
        self.customer_combo.blockSignals(False)

        self._current_status = offer.status or "Beklemede"

        # DB'den gelen company_name, address, contact_person — her zaman bunları kullan
        self.address_edit.setText(offer.customer_address)
        self.contact_edit.setText(offer.contact_person)
        self.email_edit.setText(offer.customer_email or "")
        self.phone_edit.setText(offer.customer_phone or "")

        # Müşteri combo'yu seç (sinyal tetiklemeden)
        cid = offer.customer_id
        self.customer_combo.blockSignals(True)
        for i, c in enumerate(self._customers):
            if c.id == cid:
                self.customer_combo.setCurrentIndex(i + 1)
                break
        self.customer_combo.blockSignals(False)

        self.current_currency = offer.currency or "EUR"

        self.prod_table.setRowCount(0)
        for item in offer.items:
            self._add_row(
                code=item.product_code or "", name=item.product_name or "",
                desc=item.description or "",  qty=item.quantity or 1,
                unit=item.unit or "Adet",      delivery=item.delivery_time or "2-3 Hafta",
                price=item.unit_price or 0,    currency=self.current_currency,
            )

        # Teklif koşullarını DB'den gelen değerlerle doldur
        self.validity_edit.setText(_validity_days_for_input(offer.validity))
        self.payment_edit.setText(_payment_days_for_input(offer.payment_term))
        self.validity_note.setText(offer.validity_note or "")
        subtotal = self._calc_total()
        if offer.discount_type == "percent":
            discount_rate = float(offer.discount_value or 0)
        elif subtotal > 0:
            discount_rate = round(float(offer.discount_amount or 0) / subtotal * 100, 2)
        else:
            discount_rate = 0.0
        self.discount_spin.setText(str(int(discount_rate)) if discount_rate else "")
        self.discount_visible_check.setChecked(bool(offer.show_discount))

        self._update_total(); self._set_step(0)
