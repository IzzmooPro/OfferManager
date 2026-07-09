"""Müşteri bazlı teklif geçmişi dialogu."""
import logging
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidgetItem, QFrame, QComboBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui  import QColor, QBrush
from ui.widgets._resizable_table import ResizableTable
from services.customer_service import CustomerService
from services.offer_service    import OfferService
from core.constants import SYM_MAP, get_status_config
from core.date_utils import to_display_date

logger = logging.getLogger("customer_history")


class CustomerHistoryDialog(QDialog):
    def __init__(self, parent=None, preselect_customer_id: int = None):
        super().__init__(parent)
        self.setWindowTitle("Müşteri Teklif Geçmişi")
        self.setMinimumSize(780, 500)
        self.svc_c = CustomerService()
        self.svc_o = OfferService()
        self._customers = self.svc_c.get_all()
        self._build_ui()
        if preselect_customer_id:
            for i, c in enumerate(self._customers):
                if c.id == preselect_customer_id:
                    self.combo.setCurrentIndex(i + 1)
                    break

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 16)
        lay.setSpacing(14)

        # Başlık
        title = QLabel("Müşteri Teklif Geçmişi")
        title.setStyleSheet("font-size:11pt;font-weight:700;")
        lay.addWidget(title)

        # Müşteri seçici
        sel_row = QHBoxLayout(); sel_row.setSpacing(10)
        sel_row.addWidget(QLabel("Müşteri:"))
        self.combo = QComboBox()
        self.combo.setMinimumHeight(32)
        self.combo.setMinimumWidth(280)
        self.combo.addItem("— Müşteri Seçin —", None)
        for c in self._customers:
            self.combo.addItem(c.company_name, c.id)
        self.combo.currentIndexChanged.connect(self._load)
        sel_row.addWidget(self.combo)
        sel_row.addStretch()
        lay.addLayout(sel_row)

        # Özet kartları
        self._summary_row = QHBoxLayout(); self._summary_row.setSpacing(10)
        self._sum_total = self._mini_card("Toplam Teklif", "#3a6fd8")
        self._sum_ok    = self._mini_card("Onaylandı",     "#10b981")
        self._sum_wait  = self._mini_card("Beklemede",     "#f59e0b")
        self._sum_val   = self._mini_card("Toplam Tutar",  "#6366f1")
        for w in [self._sum_total, self._sum_ok, self._sum_wait, self._sum_val]:
            self._summary_row.addWidget(w, 1)
        self._summary_row.addStretch(2)
        lay.addLayout(self._summary_row)

        # Tablo
        self.table = ResizableTable()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(
            ["Teklif No", "Tarih", "Para Birimi", "Toplam", "Vade", "Durum"])
        self.table.setup_columns([
            ('interactive', 160),
            ('interactive', 95),
            ('interactive', 80),
            ('interactive', 130),
            ('interactive', 90),
            ('stretch',     None),
        ])
        self.table.setEditTriggers(self.table.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(self.table.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)
        lay.addWidget(self.table)

        # Alt butonlar
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("Kapat")
        close_btn.setObjectName("secondary")
        close_btn.setMinimumHeight(34)
        close_btn.setMinimumWidth(90)
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        lay.addLayout(btn_row)

    def _mini_card(self, label: str, color: str) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        card.setMaximumHeight(70)
        v = QVBoxLayout(card)
        v.setContentsMargins(12, 8, 12, 8)
        v.setSpacing(2)
        val_lbl = QLabel("—")
        val_lbl.setStyleSheet(
            f"font-size:14pt;font-weight:700;color:{color};background:transparent;")
        ttl_lbl = QLabel(label)
        ttl_lbl.setObjectName("card_label")
        v.addWidget(val_lbl)
        v.addWidget(ttl_lbl)
        card._val = val_lbl
        return card

    def _load(self):
        cid = self.combo.currentData()
        if not cid:
            self.table.setRowCount(0)
            for c in [self._sum_total, self._sum_ok, self._sum_wait, self._sum_val]:
                c._val.setText("—")
            return
        try:
            offers = self.svc_o.get_by_customer(cid)
            self.table.setRowCount(len(offers))
            totals_by_currency = {}
            ok_cnt = wait_cnt = 0
            for row, o in enumerate(offers):
                sym    = SYM_MAP.get(o.currency or "", "")
                status = o.status or "Beklemede"
                sc     = get_status_config()
                cfg    = sc.get(status, sc["Beklemede"])
                amt    = o.total_amount or 0
                currency = o.currency or "?"
                totals_by_currency[currency] = totals_by_currency.get(currency, 0.0) + amt
                if status == "Onaylandı": ok_cnt += 1
                elif status == "Beklemede": wait_cnt += 1
                self.table.setRowHeight(row, 32)
                for col, val in enumerate([
                    o.offer_no or "", to_display_date(o.date),
                    o.currency or "",
                ]):
                    self.table.setItem(row, col, QTableWidgetItem(val))
                ti = QTableWidgetItem(fmt_money(amt, sym))
                ti.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(row, 3, ti)
                self.table.setItem(row, 4, QTableWidgetItem(o.validity or ""))
                si = QTableWidgetItem(f"  {status}")
                si.setForeground(QBrush(QColor(cfg["fg"])))
                si.setBackground(QBrush(QColor(cfg["bg"])))
                self.table.setItem(row, 5, si)

            self._sum_total._val.setText(str(len(offers)))
            self._sum_ok._val.setText(str(ok_cnt))
            self._sum_wait._val.setText(str(wait_cnt))
            ordered = [c for c in ("TL", "EUR", "USD") if c in totals_by_currency]
            ordered += sorted(c for c in totals_by_currency if c not in ordered)
            self._sum_val._val.setText(" | ".join(
                fmt_money(totals_by_currency[c], SYM_MAP.get(c, c), 0) for c in ordered
            ) or "—")
        except Exception as e:
            logger.error("Müşteri geçmişi yüklenemedi: %s", e, exc_info=True)
