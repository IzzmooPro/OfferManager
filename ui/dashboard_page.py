"""Dashboard — istatistikler + teklifler tablosu (QAbstractTableModel, QTableView)."""
import json, logging, os, re
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QLineEdit, QMessageBox, QMenu, QFileDialog,
    QApplication, QTableView, QAbstractItemView, QHeaderView,
    QStyledItemDelegate, QStyle, QDateEdit,
)
from PySide6.QtCore import (
    Qt, Signal, QThread, QTimer, QModelIndex, QAbstractTableModel, QEvent,
)
from PySide6.QtGui import QColor, QShortcut, QKeySequence, QTextDocument

from services.product_service  import ProductService
from services.customer_service import CustomerService
from services.offer_service    import OfferService
from ui.widgets._animated_card import AnimatedCard

logger = logging.getLogger("dashboard")
from core.constants import SYM_MAP, STATUS_ORDER, get_status_config
from core.formatting import fmt_money
from core.date_utils import to_display_date


# ── PDF Worker (QThread) ──────────────────────────────────────────────────────
class PdfWorker(QThread):
    """PDF üretimini arka planda yürütür — UI donmasını önler."""
    finished = Signal(list, list)   # (generated: [(path, meta)], errors: [str])

    def __init__(self, tasks: list):
        super().__init__()
        self.tasks = tasks

    def run(self):
        from pdf.pdf_generator import generate_pdf
        generated, errors = [], []
        for offer_data, out_path, meta in self.tasks:
            try:
                generate_pdf(offer_data, out_path)
                generated.append((out_path, meta))
            except Exception as e:
                errors.append(f"{getattr(offer_data, 'offer_no', '?')}: {e}")
        self.finished.emit(generated, errors)


# ── Teklif Tablosu Modeli (MVC) ───────────────────────────────────────────────
class OfferTableModel(QAbstractTableModel):
    """Veriyi QTableView'e sağlar; renk, hizalama ve sıralama içerir."""
    HEADERS = ["Teklif No", "Firma", "Tarih", "Para Birimi", "Toplam", "Durum"]
    _FIELDS = ["offer_no", "company_name", "date", "currency", "total_amount", "status"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._offers: list = []
        # Hover boyaması HighlightDelegate'te — model yalnızca veri sağlar
        self._hovered_row: int = -1

    def set_offers(self, offers: list):
        self.beginResetModel()
        self._offers = offers
        self.endResetModel()

    # ── Zorunlu override'lar ─────────────────────────────────────────────────
    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._offers)

    def columnCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else 6

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._offers)):
            return None
        offer = self._offers[index.row()]
        col   = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:
                text = offer.offer_no or ""
                remaining = getattr(offer, '_remaining_days', None)
                if remaining is not None and remaining < 0:
                    text += "  ⛔"
                elif remaining is not None and remaining <= 3:
                    text += "  ⚠️"
                return text
            if col == 1: return offer.company_name or ""
            if col == 2: return to_display_date(offer.date)
            if col == 3: return offer.currency or ""
            if col == 4:
                sym = SYM_MAP.get(offer.currency or "EUR", "€")
                return fmt_money(offer.total_amount, sym)
            if col == 5:
                return f"  {offer.status or 'Beklemede'}"

        row = index.row()

        if role == Qt.ItemDataRole.BackgroundRole:
            if row == self._hovered_row:
                from ui.utils.theme_manager import get_theme
                return QColor(get_theme()["table_row_hover"])
            if col == 5:
                sc  = get_status_config()
                cfg = sc.get(offer.status or "Beklemede", sc["Beklemede"])
                return QColor(cfg["bg"])

        if role == Qt.ItemDataRole.ForegroundRole and col == 5:
            if row == self._hovered_row:
                return None  # Hover'da varsayılan metin rengi — okunabilir
            sc  = get_status_config()
            cfg = sc.get(offer.status or "Beklemede", sc["Beklemede"])
            return QColor(cfg["fg"])

        if role == Qt.ItemDataRole.TextAlignmentRole:
            if col == 4:
                return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter

        if role == Qt.ItemDataRole.UserRole:
            return offer

        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.HEADERS[section] if 0 <= section < len(self.HEADERS) else None
        return None

    def sort(self, column: int, order=Qt.SortOrder.AscendingOrder):
        if not self._offers:
            return
        self.beginResetModel()
        field   = self._FIELDS[column] if 0 <= column < len(self._FIELDS) else None
        reverse = (order == Qt.SortOrder.DescendingOrder)
        if field:
            def key_fn(o):
                val = getattr(o, field, None)
                if field == "total_amount":
                    return float(val or 0)
                if field == "date":
                    return str(val or "0000-00-00")
                return str(val or "").lower()
            self._offers.sort(key=key_fn, reverse=reverse)
        self.endResetModel()

    # ── Yardımcılar ──────────────────────────────────────────────────────────
    def offer_at(self, row: int):
        return self._offers[row] if 0 <= row < len(self._offers) else None

    def offers_at_rows(self, rows: list):
        return [self._offers[r] for r in rows if 0 <= r < len(self._offers)]

    def update_offer_status(self, row: int, status: str):
        """Tek satırın durumunu model reset olmadan günceller."""
        if 0 <= row < len(self._offers):
            self._offers[row].status = status
            idx = self.index(row, 5)
            self.dataChanged.emit(idx, idx, [
                Qt.ItemDataRole.DisplayRole,
                Qt.ItemDataRole.ForegroundRole,
                Qt.ItemDataRole.BackgroundRole,
            ])


# ── Tablo Delegate ────────────────────────────────────────────────────────────
class HighlightDelegate(QStyledItemDelegate):
    """Tüm hücre boyamasını üstlenir: hover, seçim, durum rengi, arama vurgusu.

    QSS QTableView::item kuralları BackgroundRole'u eziyor; bu yüzden tüm
    arka plan + metin çizimi delegate'de painter.fillRect + drawText ile yapılır.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._keyword     = ""
        self._hovered_row = -1

    def set_keyword(self, kw: str):
        self._keyword = kw.strip()

    def set_hovered_row(self, row: int):
        self._hovered_row = row

    def paint(self, painter, option, index):
        from ui.utils.theme_manager import get_theme
        t           = get_theme()
        is_selected = bool(option.state & QStyle.StateFlag.State_Selected)
        is_hovered  = (index.row() == self._hovered_row) and not is_selected
        col         = index.column()
        offer       = index.data(Qt.ItemDataRole.UserRole)

        # ── 1. Arka plan ─────────────────────────────────────────────────────
        if is_selected:
            bg = QColor(t["table_row_selected"])
        elif is_hovered:
            bg = QColor(t["table_row_hover"])
        elif col == 5 and offer:
            sc  = get_status_config()
            cfg = sc.get(offer.status or "Beklemede", sc["Beklemede"])
            bg  = QColor(cfg["bg"])
        else:
            bg = QColor(t["bg_card"])

        painter.fillRect(option.rect, bg)

        # ── 2. Alt çizgi ─────────────────────────────────────────────────────
        painter.save()
        painter.setPen(QColor(t["grid_color"]))
        painter.drawLine(option.rect.bottomLeft(), option.rect.bottomRight())
        painter.restore()

        # ── 3. Metin rengi ───────────────────────────────────────────────────
        if is_selected:
            text_color = QColor("#ffffff")
        elif col == 5 and offer and not is_hovered:
            sc  = get_status_config()
            cfg = sc.get(offer.status or "Beklemede", sc["Beklemede"])
            text_color = QColor(cfg["fg"])
        else:
            text_color = QColor(t["text_table"])

        # ── 4. Metin içeriği ─────────────────────────────────────────────────
        text = index.data(Qt.ItemDataRole.DisplayRole) or ""
        align_raw = index.data(Qt.ItemDataRole.TextAlignmentRole)
        align = Qt.AlignmentFlag(int(align_raw)) if align_raw else (
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        text_rect = option.rect.adjusted(6, 0, -6, 0)

        # Arama vurgusu: sadece seçili/hover olmayan col 0-1 hücreler
        if self._keyword and col in (0, 1) and not is_selected and not is_hovered:
            safe = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            html = re.sub(
                re.escape(self._keyword),
                lambda m: f'<span style="background:#FFF176;color:#111;">{m.group()}</span>',
                safe,
                flags=re.IGNORECASE,
            )
            doc = QTextDocument()
            doc.setDefaultFont(option.font)
            doc.setHtml(f"<body style='color:{text_color.name()};'>{html}</body>")
            offset_y = max(0, (text_rect.height() - int(doc.size().height())) // 2)
            painter.save()
            painter.translate(text_rect.x() + 2, text_rect.y() + offset_y)
            doc.drawContents(painter)
            painter.restore()
        else:
            painter.save()
            painter.setFont(option.font)
            painter.setPen(text_color)
            painter.drawText(text_rect, int(align), text)
            painter.restore()


# ── Basit İstatistik Kartı ────────────────────────────────────────────────────
class StatCard(AnimatedCard):
    def __init__(self, title: str, accent: str):
        super().__init__()
        from PySide6.QtWidgets import QSizePolicy
        self.setMaximumHeight(82)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 8, 14, 8)
        lay.setSpacing(2)
        self.value_lbl = QLabel("0")
        self.value_lbl.setObjectName("card_value")
        self.value_lbl.setStyleSheet(
            f"font-size:18pt;font-weight:bold;color:{accent};background:transparent;")
        title_lbl = QLabel(title)
        title_lbl.setObjectName("card_label")
        lay.addWidget(self.value_lbl)
        lay.addWidget(title_lbl)

    def set_value(self, v): self.value_lbl.setText(str(v))


# ── Teklif Durum Kartı ────────────────────────────────────────────────────────
class OfferStatCard(AnimatedCard):
    def __init__(self):
        super().__init__()
        from PySide6.QtWidgets import QSizePolicy
        self.setMaximumHeight(105)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 7, 14, 7)
        lay.setSpacing(4)

        title = QLabel("Teklifler")
        title.setObjectName("card_label")
        lay.addWidget(title)

        self.bar_lay = QHBoxLayout()
        self.bar_lay.setSpacing(0)
        self.bar_lay.setContentsMargins(0, 0, 0, 0)
        self.b1 = QLabel(); self.b1.setStyleSheet("background:#f59e0b;")
        self.b2 = QLabel(); self.b2.setStyleSheet("background:#10b981;")
        self.b3 = QLabel(); self.b3.setStyleSheet("background:#ef4444;")
        self.b1.setToolTip("Beklemede")
        self.b2.setToolTip("Onaylandı")
        self.b3.setToolTip("İptal/Red")
        self.bar_lay.addWidget(self.b1, 1)
        self.bar_lay.addWidget(self.b2, 1)
        self.bar_lay.addWidget(self.b3, 1)

        bar_frame = QFrame()
        bar_frame.setLayout(self.bar_lay)
        bar_frame.setMinimumHeight(5)
        bar_frame.setMaximumHeight(5)
        from ui.utils.theme_manager import get_theme as _gt2
        bar_frame.setStyleSheet(f"border-radius:2px; background:{_gt2()['border']};")
        lay.addWidget(bar_frame)

        row = QHBoxLayout(); row.setSpacing(12)
        self._cells = {}
        for status, color in [("Beklemede","#f59e0b"),("Onaylandı","#10b981"),("İptal","#ef4444")]:
            col = QVBoxLayout(); col.setSpacing(0)
            val = QLabel("0")
            val.setStyleSheet(
                f"font-size:11pt;font-weight:700;color:{color};background:transparent;")
            lbl = QLabel(status)
            lbl.setObjectName("card_label")
            col.addWidget(val); col.addWidget(lbl)
            row.addLayout(col)
            self._cells[status] = val
        row.addStretch()
        lay.addLayout(row)

    def set_values(self, counts: dict):
        for s, lbl in self._cells.items():
            lbl.setText(str(counts.get(s, 0)))
        wait = counts.get("Beklemede", 0)
        appr = counts.get("Onaylandı", 0)
        canc = counts.get("İptal",     0)
        tot  = wait + appr + canc
        from ui.utils.theme_manager import get_theme
        _empty_bar = get_theme()["border"]
        self.b1.setStyleSheet("background:#f59e0b;" if wait else f"background:{_empty_bar};")
        self.b2.setStyleSheet("background:#10b981;")
        self.b3.setStyleSheet("background:#ef4444;")
        if tot > 0:
            self.b1.setVisible(wait > 0)
            self.b2.setVisible(appr > 0)
            self.b3.setVisible(canc > 0)
            self.bar_lay.setStretch(0, max(1, int((wait/tot)*100)) if wait > 0 else 0)
            self.bar_lay.setStretch(1, max(1, int((appr/tot)*100)) if appr > 0 else 0)
            self.bar_lay.setStretch(2, max(1, int((canc/tot)*100)) if canc > 0 else 0)
        else:
            self.b1.setVisible(True); self.b2.setVisible(False); self.b3.setVisible(False)
            self.b1.setStyleSheet(f"background:{_empty_bar};")
            self.bar_lay.setStretch(0, 1)


# ── Ciro Özet Kartı ───────────────────────────────────────────────────────────
class RevenueCard(AnimatedCard):
    """Bu ay ve bu yıl para birimi bazlı ciro (iptal hariç)."""
    def __init__(self):
        super().__init__()
        from PySide6.QtWidgets import QSizePolicy
        self.setMaximumHeight(82)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 8, 14, 8)
        lay.setSpacing(3)

        title = QLabel("Ciro (İptal hariç)")
        title.setObjectName("card_label")
        lay.addWidget(title)

        from ui.utils.theme_manager import get_theme
        self._monthly = QLabel("Bu Ay: —")
        self._monthly.setStyleSheet(
            f"font-size:9pt;font-weight:600;color:{get_theme()['accent_blue']};background:transparent;")
        self._yearly = QLabel("Bu Yıl: —")
        self._yearly.setObjectName("card_label")
        self._yearly.setWordWrap(True)

        lay.addWidget(self._monthly)
        lay.addWidget(self._yearly)

    @staticmethod
    def _fmt(d: dict) -> str:
        if not d:
            return "—"
        parts = [fmt_money(v, SYM_MAP.get(k, k), 0) for k, v in sorted(d.items()) if v]
        return "  |  ".join(parts) if parts else "—"

    def set_revenue(self, monthly: dict, yearly: dict):
        self._monthly.setText(f"Bu Ay: {self._fmt(monthly)}")
        self._yearly.setText(f"Bu Yıl: {self._fmt(yearly)}")


# ── Dashboard ─────────────────────────────────────────────────────────────────
class DashboardPage(QWidget):
    edit_offer_requested  = Signal(int)
    clone_offer_requested = Signal(int)

    def __init__(self):
        super().__init__()
        self.svc_p = ProductService()
        self.svc_c = CustomerService()
        self.svc_o = OfferService()
        self._active_filter  = "Tümü"
        self._date_from      = ""
        self._date_to        = ""
        self._pdf_worker     = None

        # Debounce — 350 ms sessizlik sonrası _load() çalışır
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(350)
        self._search_timer.timeout.connect(self._load)

        self._build_ui()
        self._setup_shortcuts()

    # ── Arayüz ───────────────────────────────────────────────────────────────
    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 12)
        lay.setSpacing(10)

        title_lbl = QLabel("Teklifler")
        title_lbl.setStyleSheet("font-size:14pt;font-weight:700;")
        lay.addWidget(title_lbl)

        # ── Stat Kartları ─────────────────────────────────────────────────
        from ui.utils.theme_manager import get_theme
        t = get_theme()
        cards = QHBoxLayout(); cards.setSpacing(10)
        self.card_c      = StatCard("Toplam Müşteri", t["accent_red"])
        self.card_p      = StatCard("Toplam Ürün",    t["accent_blue"])
        self.card_offers = OfferStatCard()
        self.card_rev    = RevenueCard()
        for c in [self.card_c, self.card_p, self.card_offers, self.card_rev]:
            cards.addWidget(c, 1)
        lay.addLayout(cards)

        # ── Toolbar ──────────────────────────────────────────────────────
        tb = QHBoxLayout(); tb.setSpacing(8)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Teklif no veya firma ara...  (Ctrl+F)")
        self.search.setMinimumHeight(32)
        self.search.setMinimumWidth(220)
        self.search.textChanged.connect(lambda: self._search_timer.start())
        tb.addWidget(self.search)

        self.filter_btn = QPushButton("Durum: Tümü  ▾")
        self.filter_btn.setObjectName("secondary")
        self.filter_btn.setMinimumHeight(32)
        self.filter_btn.clicked.connect(self._show_filter_menu)
        tb.addWidget(self.filter_btn)

        self.btn_date_toggle = QPushButton("Tarih ▾")
        self.btn_date_toggle.setObjectName("secondary")
        self.btn_date_toggle.setMinimumHeight(32)
        self.btn_date_toggle.setCheckable(True)
        self.btn_date_toggle.clicked.connect(self._toggle_date_filter)
        tb.addWidget(self.btn_date_toggle)

        tb.addStretch()

        btn_group = QHBoxLayout()
        btn_group.setSpacing(4)
        btn_group.setContentsMargins(0, 0, 0, 0)
        _btns = [
            ("Kopyala", self._clone,         "tab_btn_clone"),
            ("Düzenle", self._edit,          "tab_btn_edit"),
            ("Durum",   self._change_status, "tab_btn_status"),
            ("PDF",     self._gen_pdf,       "tab_btn_pdf"),
            ("Sil",     self._delete,        "tab_btn_delete"),
        ]
        for text, slot, obj in _btns:
            b = QPushButton(text)
            b.setObjectName(obj)
            b.setMinimumHeight(36)
            b.setMinimumWidth(82)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(slot)
            btn_group.addWidget(b)
            if text == "Durum": self._status_btn = b
            if text == "PDF":   self._pdf_btn    = b
        tb.addLayout(btn_group)
        lay.addLayout(tb)

        # ── Tarih Filtre Satırı (gizlenebilir) ──────────────────────────
        from PySide6.QtCore import QDate
        self._date_bar = QFrame()
        self._date_bar.setObjectName("toolbar")
        self._date_bar.setVisible(False)
        db = QHBoxLayout(self._date_bar)
        db.setContentsMargins(14, 6, 14, 6)
        db.setSpacing(8)

        lbl1 = QLabel("Başlangıç:")
        db.addWidget(lbl1)
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDisplayFormat("dd.MM.yyyy")
        self.date_from.setDate(QDate.currentDate().addMonths(-1))
        self.date_from.setFixedWidth(135)
        self.date_from.dateChanged.connect(lambda: self._apply_adv_filter())
        db.addWidget(self.date_from)

        lbl2 = QLabel("Bitiş:")
        db.addWidget(lbl2)
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDisplayFormat("dd.MM.yyyy")
        self.date_to.setDate(QDate.currentDate())
        self.date_to.setFixedWidth(135)
        self.date_to.dateChanged.connect(lambda: self._apply_adv_filter())
        db.addWidget(self.date_to)

        db.addSpacing(4)

        btn_clear = QPushButton("Temizle")
        btn_clear.setObjectName("secondary")
        btn_clear.clicked.connect(self._clear_adv_filter)
        db.addWidget(btn_clear)
        db.addStretch()

        lay.addWidget(self._date_bar)

        # ── Tablo (QAbstractTableModel + QTableView) ──────────────────────
        self._model    = OfferTableModel(self)
        self._delegate = HighlightDelegate(self)

        self.table = QTableView()
        self.table.setModel(self._model)
        self.table.setSortingEnabled(True)
        self.table.setAlternatingRowColors(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(34)
        self.table.setShowGrid(False)
        self.table.setMouseTracking(True)
        self.table.viewport().setMouseTracking(True)
        for _c in range(6):
            self.table.setItemDelegateForColumn(_c, self._delegate)

        # Satır bazlı hover takibi — model üzerinden BackgroundRole ile
        self.table.entered.connect(self._on_hover_enter)
        self.table.viewport().installEventFilter(self)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._context_menu)
        self.table.doubleClicked.connect(lambda _: self._edit())
        self.table.clicked.connect(self._on_cell_clicked)

        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        hh.setSectionResizeMode(4, QHeaderView.ResizeMode.Interactive)
        hh.setSectionResizeMode(5, QHeaderView.ResizeMode.Interactive)
        hh.resizeSection(0, 155)
        hh.resizeSection(2, 95)
        hh.resizeSection(3, 110)
        hh.resizeSection(4, 140)
        hh.resizeSection(5, 115)

        self._empty_label = QLabel("Henüz teklif oluşturulmamış.\nSol menüden 'Yeni Teklif' ile başlayın.")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setObjectName("card_label")
        self._empty_label.setStyleSheet("font-size:11pt;")
        self._empty_label.setVisible(False)
        lay.addWidget(self._empty_label, 1)
        lay.addWidget(self.table, 1)

        self._restore_column_widths()
        hh.sectionResized.connect(self._on_column_resized)

    def _setup_shortcuts(self):
        """Dashboard klavye kısayolları."""
        def sc(key, fn):
            s = QShortcut(QKeySequence(key), self)
            s.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            s.activated.connect(fn)
        sc("Ctrl+F", lambda: (self.search.setFocus(), self.search.selectAll()))
        sc("Delete", self._delete)
        sc("Ctrl+P", self._gen_pdf)
        sc("Ctrl+E", self._edit)
        sc("Ctrl+D", self._clone)

    # ── Gelişmiş Filtre ─────────────────────────────────────────────────────
    def _toggle_date_filter(self, checked: bool):
        self._date_bar.setVisible(checked)
        if checked:
            self._apply_adv_filter()
        else:
            self._date_from = ""
            self._date_to = ""
            self._load()

    def _apply_adv_filter(self):
        self._date_from = self.date_from.date().toString("yyyy-MM-dd")
        self._date_to = self.date_to.date().toString("yyyy-MM-dd")
        self._load()

    def _clear_adv_filter(self):
        from PySide6.QtCore import QDate
        self.date_from.setDate(QDate.currentDate().addMonths(-1))
        self.date_to.setDate(QDate.currentDate())
        self._date_from = ""
        self._date_to = ""
        self._load()

    # ── Filtre Dropdown ───────────────────────────────────────────────────────
    def _show_filter_menu(self):
        menu = QMenu(self)
        for s in ["Tümü"] + STATUS_ORDER:
            act = menu.addAction(s)
            act.setCheckable(True)
            act.setChecked(s == self._active_filter)
            act.triggered.connect(lambda _, st=s: self._set_filter(st))
        menu.exec(self.filter_btn.mapToGlobal(self.filter_btn.rect().bottomLeft()))

    def _set_filter(self, status: str):
        self._active_filter = status
        self.filter_btn.setText(f"Durum: {status}  ▾")
        self._load()

    # ── Veri ─────────────────────────────────────────────────────────────────
    # ── Hover takibi ──────────────────────────────────────────────────────────
    def _on_hover_enter(self, index: QModelIndex):
        self._delegate.set_hovered_row(index.row())
        self.table.viewport().update()

    def eventFilter(self, obj, event):
        if obj is self.table.viewport() and event.type() == QEvent.Type.Leave:
            self._delegate.set_hovered_row(-1)
            self.table.viewport().update()
        return super().eventFilter(obj, event)

    # ── Veri yükleme ──────────────────────────────────────────────────────────
    def _load(self):
        """SQL filtreli veri yükle — her debounce timeout'ta çalışır."""
        kw = self.search.text().strip()
        try:
            offers = self.svc_o.get_filtered(
                keyword=kw, status=self._active_filter,
                date_from=self._date_from, date_to=self._date_to)
        except Exception as e:
            logger.error("Dashboard yenileme hatası: %s", e, exc_info=True)
            return
        self._enrich_expiry(offers)
        self._delegate.set_keyword(kw)
        self._model.set_offers(offers)
        self.table.clearSelection()
        self.table.viewport().update()
        empty = len(offers) == 0
        self._empty_label.setVisible(empty)
        self.table.setVisible(not empty)
        if empty and kw:
            self._empty_label.setText(f"'{kw}' aramasına uygun teklif bulunamadı.")
        elif empty:
            self._empty_label.setText("Henüz teklif oluşturulmamış.\nSol menüden 'Yeni Teklif' ile başlayın.")

    def on_enter(self):
        """Sayfaya her geçişte çalışır — istatistik + tablo güncellenir."""
        cancelled_any = self._auto_cancel_expired()
        scroll_pos = self.table.verticalScrollBar().value()

        try:
            counts  = self.svc_o.get_status_counts()
            revenue = self.svc_o.get_revenue_summary()
            self.card_p.set_value(self.svc_p.count())
            self.card_c.set_value(self.svc_c.count())
            self.card_offers.set_values(counts)
            self.card_rev.set_revenue(revenue["monthly"], revenue["yearly"])
        except Exception as e:
            logger.error("Dashboard istatistik hatası: %s", e, exc_info=True)

        self.search.blockSignals(True)
        self.search.clear()
        self.search.blockSignals(False)
        self._active_filter = "Tümü"
        self._date_from = ""
        self._date_to = ""
        self.btn_date_toggle.setChecked(False)
        self._date_bar.setVisible(False)
        self.filter_btn.setText("Durum: Tümü  ▾")
        self._load()
        self.table.verticalScrollBar().setValue(scroll_pos)

        # Otomatik iptal mesajı varsa onu ezme; yoksa yaklaşan süre uyarısı göster
        if not cancelled_any:
            self._check_expiring_offers()

    @staticmethod
    def _enrich_expiry(offers: list):
        """Her offer'a _remaining_days atar (geçerlilik süresi kalan gün)."""
        import datetime as _dt
        today = _dt.date.today()
        for o in offers:
            o._remaining_days = None
            if (o.status or "Beklemede") != "Beklemede":
                continue
            validity = (o.validity or "").strip()
            match = re.fullmatch(r"(\d+)\s*(?:g[üu]n|ay)?", validity, flags=re.IGNORECASE)
            if not match:
                continue
            try:
                offer_date = _dt.date.fromisoformat(o.date)
            except (ValueError, TypeError):
                continue
            days = int(match.group(1))
            if "ay" in validity.lower():
                days *= 30
            expiry = offer_date + _dt.timedelta(days=days)
            o._remaining_days = (expiry - today).days

    def _auto_cancel_expired(self) -> bool:
        """Geçerlilik süresi dolan Beklemede teklifleri otomatik İptal eder."""
        try:
            cancelled = self.svc_o.auto_cancel_expired()
        except Exception as e:
            logger.debug("Otomatik iptal atlandı: %s", e)
            return False
        if not cancelled:
            return False
        nos = ", ".join(cancelled[:5]) + (" ..." if len(cancelled) > 5 else "")
        main_win = self.window()
        if hasattr(main_win, 'show_status'):
            main_win.show_status(
                f"Geçerlilik süresi dolan {len(cancelled)} teklif otomatik "
                f"İptal edildi: {nos}", level="warning")
        return True

    def _check_expiring_offers(self):
        """Süresi 3 gün içinde dolacak teklifler varsa bildirim gösterir.

        Süresi dolmuş olanlar _auto_cancel_expired ile zaten İptal edilir."""
        try:
            expiring = self.svc_o.get_expiring_offers(days=3)
        except Exception as e:
            logger.debug("Geçerlilik kontrolü atlandı: %s", e)
            return
        soon = [o for o in expiring if 0 <= getattr(o, '_remaining_days', 0) <= 3]
        if soon:
            main_win = self.window()
            if hasattr(main_win, 'show_status'):
                main_win.show_status(
                    f"Uyarı: {len(soon)} teklifin süresi 3 gün içinde dolacak",
                    level="warning")

    # ── Sütun genişliği hafıza ─────────────────────────────────────────────────
    def _col_widths_path(self) -> Path:
        from core.app_paths import DATA_DIR
        return DATA_DIR / "column_widths.json"

    def _save_column_widths(self):
        widths = {}
        hh = self.table.horizontalHeader()
        for i in range(hh.count()):
            if hh.sectionResizeMode(i) != QHeaderView.ResizeMode.Stretch:
                widths[str(i)] = hh.sectionSize(i)
        try:
            self._col_widths_path().write_text(
                json.dumps(widths), encoding="utf-8")
        except OSError:
            pass

    def _restore_column_widths(self):
        path = self._col_widths_path()
        if not path.exists():
            return
        try:
            widths = json.loads(path.read_text(encoding="utf-8"))
            hh = self.table.horizontalHeader()
            for col_str, width in widths.items():
                col = int(col_str)
                if 0 <= col < hh.count() and isinstance(width, int) and width > 20:
                    hh.resizeSection(col, width)
        except (OSError, json.JSONDecodeError, ValueError):
            pass

    def _on_column_resized(self, _col: int, _old: int, _new: int):
        if not hasattr(self, '_col_save_timer'):
            self._col_save_timer = QTimer(self)
            self._col_save_timer.setSingleShot(True)
            self._col_save_timer.setInterval(500)
            self._col_save_timer.timeout.connect(self._save_column_widths)
        self._col_save_timer.start()

    def _refresh_stats(self):
        """Tam sayfa yenilemeden sadece istatistik kartlarını günceller."""
        try:
            self.card_offers.set_values(self.svc_o.get_status_counts())
            rev = self.svc_o.get_revenue_summary()
            self.card_rev.set_revenue(rev["monthly"], rev["yearly"])
        except Exception as e:
            logger.debug("İstatistik kartı güncelleme hatası: %s", e)

    # ── Seçim Yardımcıları ────────────────────────────────────────────────────
    def _selected(self):
        """Tek seçili teklif; 0 veya 2+ seçiliyse None."""
        rows = sorted(set(idx.row() for idx in self.table.selectedIndexes()))
        return self._model.offer_at(rows[0]) if len(rows) == 1 else None

    def _selected_all(self):
        """Tüm seçili teklifler."""
        rows = sorted(set(idx.row() for idx in self.table.selectedIndexes()))
        return self._model.offers_at_rows(rows)

    # ── Inline Durum Toggle ───────────────────────────────────────────────────
    def _on_cell_clicked(self, index: QModelIndex):
        """Durum sütununa tıklanınca bir sonraki duruma geçer."""
        if index.column() != 5:
            return
        offer = self._model.offer_at(index.row())
        if not offer:
            return
        current  = offer.status or "Beklemede"
        next_idx = (STATUS_ORDER.index(current) + 1) % len(STATUS_ORDER) \
                   if current in STATUS_ORDER else 0
        self._apply_status(index.row(), offer, STATUS_ORDER[next_idx])

    def _apply_status(self, row: int, offer, new_status: str):
        """DB güncelle + modeli in-place yenile (tam reload yok)."""
        try:
            self.svc_o.update_status(offer.id, new_status)
            self._model.update_offer_status(row, new_status)
            self._refresh_stats()
        except Exception as e:
            QMessageBox.warning(self, "Hata", f"Durum güncellenemedi:\n{e}")

    # ── Context Menu ──────────────────────────────────────────────────────────
    def _context_menu(self, pos):
        o = self._selected()
        if not o:
            return
        menu = QMenu(self)
        menu.addAction("Kopyala\tCtrl+D",  self._clone)
        menu.addAction("Düzenle\tCtrl+E",  self._edit)
        sub = menu.addMenu("Durum Değiştir")
        for s in STATUS_ORDER:
            act = sub.addAction(s)
            act.setCheckable(True)
            act.setChecked((o.status or "Beklemede") == s)
            act.triggered.connect(lambda _, st=s: self._set_status_bulk(st))
        menu.addSeparator()
        menu.addAction("Şablon Olarak Kaydet", self._save_as_template)
        menu.addSeparator()
        menu.addAction("PDF Önizle", self._preview_pdf)
        menu.addAction("PDF Oluştur\tCtrl+P", self._gen_pdf)
        menu.addAction("E-posta Gönder", self._email_selected)
        exp = menu.addMenu("Dışa Aktar")
        exp.addAction("Excel (.xlsx)", self._export_excel)
        exp.addAction("CSV (.csv)",    self._export_csv)
        if o.customer_id:
            menu.addSeparator()
            menu.addAction("Müşteri Geçmişi", lambda: self._show_customer_history_for(o.customer_id))
        menu.addSeparator()
        menu.addAction("Sil\tDelete",  self._delete)
        menu.exec(self.table.viewport().mapToGlobal(pos))

    # ── Eylemler ─────────────────────────────────────────────────────────────
    def _edit(self):
        o = self._selected()
        if not o:
            QMessageBox.information(self, "Bilgi", "Lütfen bir teklif seçin.")
            return
        self.edit_offer_requested.emit(o.id)

    def _clone(self):
        o = self._selected()
        if not o:
            QMessageBox.information(self, "Bilgi", "Lütfen kopyalanacak teklifi seçin.")
            return
        self.clone_offer_requested.emit(o.id)

    def _change_status(self):
        offers = self._selected_all()
        if not offers:
            QMessageBox.information(self, "Bilgi", "Lütfen en az bir teklif seçin.")
            return
        menu = QMenu(self)
        for s in STATUS_ORDER:
            act = menu.addAction(s)
            act.triggered.connect(lambda _, st=s: self._set_status_bulk(st))
        menu.exec(self._status_btn.mapToGlobal(self._status_btn.rect().bottomLeft()))

    def _set_status_bulk(self, new_status: str):
        rows = sorted(set(idx.row() for idx in self.table.selectedIndexes()))
        for row in rows:
            offer = self._model.offer_at(row)
            if offer:
                self._apply_status(row, offer, new_status)

    # ── Şablon ───────────────────────────────────────────────────────────────
    def _save_as_template(self):
        """Seçili teklifin kalemlerini şablon olarak kaydeder."""
        o = self._selected()
        if not o:
            QMessageBox.information(self, "Bilgi", "Lütfen bir teklif seçin.")
            return
        try:
            offer_data = self.svc_o.get_by_id(o.id)
        except Exception as e:
            QMessageBox.warning(self, "Hata", f"Teklif yüklenemedi:\n{e}")
            return
        if not offer_data or not offer_data.items:
            QMessageBox.warning(self, "Hata", "Teklifte ürün kalemi bulunamadı.")
            return
        from PySide6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(
            self, "Şablon Adı",
            f"Şablon adı girin ({len(offer_data.items)} kalem kaydedilecek):",
            text=f"{offer_data.company_name or offer_data.offer_no} Şablonu",
        )
        if not ok or not name.strip():
            return
        try:
            from services.template_service import TemplateService
            svc = TemplateService()
            svc.create_from_offer(name.strip(), offer_data.currency, offer_data.items)
            QMessageBox.information(
                self, "Kaydedildi",
                f"'{name.strip()}' şablonu {len(offer_data.items)} kalemle kaydedildi.\n\n"
                "Yeni teklif oluştururken 'Şablondan Yükle' ile kullanabilirsiniz.")
        except Exception as e:
            QMessageBox.warning(self, "Hata", f"Şablon kaydedilemedi:\n{e}")

    # ── PDF Önizleme ──────────────────────────────────────────────────────────
    def _preview_pdf(self):
        """Seçili teklifin PDF'ini uygulama içinde önizler."""
        o = self._selected()
        if not o:
            QMessageBox.information(self, "Bilgi", "Lütfen bir teklif seçin.")
            return
        try:
            offer_data = self.svc_o.get_by_id(o.id)
        except Exception as e:
            QMessageBox.warning(self, "Hata", f"Teklif yüklenemedi:\n{e}")
            return
        import tempfile
        from pdf.pdf_generator import generate_pdf
        preview_dir = Path(tempfile.gettempdir()) / "TeklifOnizleme"
        preview_dir.mkdir(exist_ok=True)
        out_path = str(preview_dir / f"{offer_data.offer_no or 'Teklif'}.pdf")
        try:
            generate_pdf(offer_data, out_path)
        except Exception as e:
            QMessageBox.warning(self, "Hata", f"PDF oluşturulamadı:\n{e}")
            return
        self._show_preview_dialog(out_path, offer_data)

    def _show_preview_dialog(self, pdf_path: str, offer_data=None):
        from ui.dialogs.pdf_preview_dialog import PdfPreviewDialog
        dlg = PdfPreviewDialog(
            pdf_path=pdf_path,
            parent=self,
            offer_no=getattr(offer_data, "offer_no", "") or "",
            customer_email=getattr(offer_data, "customer_email", "") or "",
        )
        dlg.exec()

    def _email_selected(self):
        """Seçili teklifin PDF'ini e-posta ile gönderir."""
        o = self._selected()
        if not o:
            QMessageBox.information(self, "Bilgi", "Lütfen bir teklif seçin.")
            return
        try:
            offer_data = self.svc_o.get_by_id(o.id)
        except Exception as e:
            QMessageBox.warning(self, "Hata", f"Teklif yüklenemedi:\n{e}")
            return
        import tempfile
        from pdf.pdf_generator import generate_pdf
        preview_dir = Path(tempfile.gettempdir()) / "TeklifOnizleme"
        preview_dir.mkdir(exist_ok=True)
        out_path = str(preview_dir / f"{offer_data.offer_no or 'Teklif'}.pdf")
        try:
            generate_pdf(offer_data, out_path)
        except Exception as e:
            QMessageBox.warning(self, "Hata", f"PDF oluşturulamadı:\n{e}")
            return
        self._send_email(out_path, {
            "offer_no": offer_data.offer_no or "",
            "customer_email": offer_data.customer_email or "",
        })

    # ── PDF Üretimi (QThread) ─────────────────────────────────────────────────
    def _gen_pdf(self):
        """PDF üretimini QThread'e taşır — tek teklif veya toplu klasör."""
        offers = self._selected_all()
        if not offers:
            QMessageBox.information(self, "Bilgi", "Lütfen en az bir teklif seçin.")
            return

        desktop = Path(os.path.expanduser("~")) / "Desktop"
        desktop.mkdir(parents=True, exist_ok=True)
        tasks = []

        if len(offers) == 1:
            try:
                offer_data = self.svc_o.get_by_id(offers[0].id)
            except Exception as e:
                QMessageBox.warning(self, "Hata", f"Teklif yüklenemedi:\n{e}")
                return
            out_path, _ = QFileDialog.getSaveFileName(
                self, f"PDF Kaydet — {offer_data.offer_no}",
                str(desktop / f"{offer_data.offer_no}.pdf"),
                "PDF Dosyaları (*.pdf)",
            )
            if not out_path:
                return
            tasks.append((offer_data, out_path, {
                "offer_no":       offer_data.offer_no or "",
                "customer_email": offer_data.customer_email or "",
            }))
        else:
            folder = QFileDialog.getExistingDirectory(
                self, f"{len(offers)} PDF'in Kaydedileceği Klasörü Seçin", str(desktop))
            if not folder:
                return
            load_errors = []
            for o in offers:
                try:
                    offer_data = self.svc_o.get_by_id(o.id)
                    tasks.append((offer_data, str(Path(folder) / f"{offer_data.offer_no}.pdf"), {
                        "offer_no":       offer_data.offer_no or "",
                        "customer_email": offer_data.customer_email or "",
                    }))
                except Exception as e:
                    load_errors.append(f"{o.offer_no or '?'}: {e}")
            if load_errors:
                QMessageBox.warning(self, "Yükleme Hatası",
                                    "Bazı teklifler yüklenemedi:\n" + "\n".join(load_errors))
            if not tasks:
                return

        self._pdf_btn.setEnabled(False)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        self._pdf_worker = PdfWorker(tasks)
        self._pdf_worker.finished.connect(self._on_pdf_finished)
        self._pdf_worker.start()

    def _on_pdf_finished(self, generated: list, errors: list):
        QApplication.restoreOverrideCursor()
        self._pdf_btn.setEnabled(True)
        if self._pdf_worker:
            self._pdf_worker.deleteLater()
            self._pdf_worker = None

        if errors:
            QMessageBox.warning(self, "Hata",
                                "Bazı PDF'ler oluşturulamadı:\n" + "\n".join(errors))
        if len(generated) == 1:
            out_path, meta = generated[0]
            box = QMessageBox(self)
            box.setWindowTitle("PDF Oluşturuldu")
            box.setText(f"PDF kaydedildi:\n{out_path}")
            btn_preview = box.addButton("Önizle",      QMessageBox.ButtonRole.AcceptRole)
            btn_mail    = box.addButton("Mail Gönder", QMessageBox.ButtonRole.ActionRole)
            btn_close   = box.addButton("Kapat",       QMessageBox.ButtonRole.RejectRole)
            btn_preview.setMinimumWidth(90)
            btn_mail.setMinimumWidth(130)
            btn_close.setMinimumWidth(80)
            box.exec()
            clicked = box.clickedButton()
            if clicked == btn_preview:
                from ui.dialogs.pdf_preview_dialog import PdfPreviewDialog
                dlg = PdfPreviewDialog(
                    pdf_path=out_path, parent=self,
                    offer_no=meta.get("offer_no", ""),
                    customer_email=meta.get("customer_email", ""),
                )
                dlg.exec()
            elif clicked == btn_mail:
                self._send_email(out_path, meta)
        elif len(generated) > 1:
            if QMessageBox.information(
                self, "PDF Oluşturuldu",
                f"{len(generated)} PDF oluşturuldu.\n\nHepsini açmak ister misiniz?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            ) == QMessageBox.StandardButton.Yes:
                for path, _ in generated:
                    self._open_file(path)

    # ── Silme ─────────────────────────────────────────────────────────────────
    def _delete(self):
        offers = self._selected_all()
        if not offers:
            QMessageBox.information(self, "Bilgi", "Silmek için önce bir teklif seçin.")
            return
        n   = len(offers)
        msg = (f"Seçili {n} teklif kalıcı olarak silinsin mi?" if n > 1
               else f"'{offers[0].offer_no}' kalıcı olarak silinsin mi?\n\nBu işlem geri alınamaz.")
        if QMessageBox.question(
            self, "Silme Onayı", msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return
        errors = []
        for o in offers:
            try:
                self.svc_o.delete(o.id)
            except Exception as e:
                errors.append(str(e))
        if errors:
            QMessageBox.warning(self, "Hata", "Bazı teklifler silinemedi:\n" + "\n".join(errors))
        self.on_enter()

    # ── E-Posta ───────────────────────────────────────────────────────────────
    def _send_email(self, pdf_path: str, meta: dict):
        from ui.dialogs.email_dialog import EmailDialog
        from core.config import load_company_config
        cfg = load_company_config()
        if not cfg.get("smtp_server") or not cfg.get("smtp_user"):
            QMessageBox.warning(
                self, "E-Posta Ayarı Eksik",
                "E-posta göndermek için önce:\n"
                "Ayarlar → E-Posta Ayarları\n"
                "bölümünden SMTP bilgilerinizi girin.")
            return
        EmailDialog(
            pdf_path=pdf_path,
            customer_email=meta.get("customer_email", ""),
            offer_no=meta.get("offer_no", ""),
            parent=self,
        ).exec()

    # ── Müşteri Geçmişi ───────────────────────────────────────────────────────
    def _show_customer_history_for(self, customer_id: int):
        from ui.dialogs.customer_history_dialog import CustomerHistoryDialog
        CustomerHistoryDialog(self, preselect_customer_id=customer_id).exec()

    # ── Export (sağ tık menüsünden — listelenen özet görünüm) ─────────────────
    def _export_excel(self): self._do_export("excel")
    def _export_csv(self):   self._do_export("csv")

    def _do_export(self, fmt: str):
        offers = self._model.offers_at_rows(list(range(self._model.rowCount())))
        if not offers:
            QMessageBox.information(self, "Bilgi", "Dışa aktarılacak teklif yok.")
            return
        import datetime
        default = f"teklifler_{datetime.date.today().strftime('%Y%m%d')}.{'xlsx' if fmt=='excel' else 'csv'}"
        filt    = "Excel Dosyası (*.xlsx)" if fmt == "excel" else "CSV Dosyası (*.csv)"
        path, _ = QFileDialog.getSaveFileName(self, "Kaydet", default, filt)
        if not path:
            return
        try:
            from services.export_service import export_excel, export_csv
            out = export_excel(offers, path) if fmt == "excel" else export_csv(offers, path)
            QMessageBox.information(self, "Tamamlandı",
                                    f"{len(offers)} teklif dışa aktarıldı.\n{out}")
        except Exception as e:
            QMessageBox.warning(self, "Hata", f"Export hatası:\n{e}")

    # ── Dosya Aç ──────────────────────────────────────────────────────────────
    def _open_file(self, path: str):
        os.startfile(path)
