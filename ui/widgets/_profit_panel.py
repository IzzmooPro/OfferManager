"""
Kâr Analizi paneli — yalnızca teklif oluşturma ekranında, dahili kullanım.

Bu widget'ın gösterdiği hiçbir veri (alış fiyatı, kâr, marj) PDF'e,
Excel export'una, e-postaya veya teklif özetine aktarılmaz — yalnızca
ekranda, teklifi hazırlayan kişiye gösterilir. Varsayılan kapalıdır,
tek tıkla açılır/kapanır.
"""
from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QWidget

from core.profit import calculate_margin, max_discount, margin_status, count_items_missing_cost
from core.formatting import fmt_money

_YELLOW = "#f59e0b"  # "Beklemede" durumu ile aynı amber ton — tutarlı palet


class ProfitPanel(QFrame):
    """Katlanabilir, varsayılan kapalı kâr analizi kartı."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("step_card")
        self._expanded = False
        self._sym = "€"
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 8, 16, 10)
        outer.setSpacing(6)

        header = QHBoxLayout()
        title = QLabel("🔒 Kâr Analizi — yalnızca sizde görünür")
        title.setObjectName("step_card_title")
        header.addWidget(title)
        header.addStretch()
        self._toggle_btn = QPushButton("Göster ▾")
        self._toggle_btn.setObjectName("secondary")
        # setFixedHeight DEĞİL — "secondary" stilinin kendi padding'i (8px+8px)
        # sabit 28px'e sığmayıp metni kırpıyordu. Diğer secondary butonlar
        # (btn_back vb.) gibi setMinimumHeight kullanılır — doğal boyuta izin verir.
        self._toggle_btn.setMinimumHeight(30)
        self._toggle_btn.clicked.connect(self._toggle)
        header.addWidget(self._toggle_btn)
        outer.addLayout(header)

        self._body = QWidget()
        body_l = QVBoxLayout(self._body)
        body_l.setContentsMargins(0, 6, 0, 0)
        body_l.setSpacing(4)

        self._totals_lbl = QLabel("")
        self._totals_lbl.setWordWrap(True)
        body_l.addWidget(self._totals_lbl)

        self._margin_lbl = QLabel("")
        self._margin_lbl.setWordWrap(True)
        body_l.addWidget(self._margin_lbl)

        self._max_disc_lbl = QLabel("")
        self._max_disc_lbl.setWordWrap(True)
        body_l.addWidget(self._max_disc_lbl)

        self._warn_lbl = QLabel("")
        self._warn_lbl.setObjectName("hint_label")
        self._warn_lbl.setWordWrap(True)
        self._warn_lbl.setVisible(False)
        body_l.addWidget(self._warn_lbl)

        self._body.setVisible(False)
        outer.addWidget(self._body)

    def _toggle(self):
        self._expanded = not self._expanded
        self._body.setVisible(self._expanded)
        self._toggle_btn.setText("Gizle ▴" if self._expanded else "Göster ▾")

    def set_currency_symbol(self, sym: str):
        self._sym = sym or "€"

    def update_values(self, total_cost: float, subtotal: float,
                       net_total: float, row_costs: list):
        """Panelin tüm satırlarını günceller.

        total_cost : tüm kalemlerin toplam alış maliyeti
        subtotal   : iskonto ÖNCESİ ürünler toplamı (maks. iskonto buna göre)
        net_total  : iskonto SONRASI toplam (şu anki gerçek kâr buna göre)
        row_costs  : her kalemin birim maliyeti (eksik-maliyet uyarısı için)
        """
        from ui.utils.theme_manager import get_theme
        t = get_theme()
        sym = self._sym

        margin = calculate_margin(total_cost, net_total)
        disc = max_discount(total_cost, subtotal)
        status = margin_status(margin["margin_pct"])
        missing = count_items_missing_cost(row_costs)

        color = {"green": t["accent_green"], "yellow": _YELLOW,
                 "red": t["accent_red"]}.get(status, t["text_primary"])

        self._totals_lbl.setText(
            f"Toplam Alış: <b>{fmt_money(total_cost, sym)}</b>"
            f"&nbsp;&nbsp;&nbsp;Toplam Satış: <b>{fmt_money(subtotal, sym)}</b>"
        )

        note = ""
        if status == "red":
            note = "  —  bu fiyatla zarar ediyorsunuz"
        elif status == "yellow":
            note = "  —  marj ince, dikkatli olun"
        self._margin_lbl.setText(
            f"Şu anki kârınız: <b style='color:{color};'>"
            f"{fmt_money(margin['profit'], sym)} (%{margin['margin_pct']:g})</b>{note}"
        )

        self._max_disc_lbl.setText(
            "Maliyetine düşmeden en fazla "
            f"<b>%{disc['max_discount_pct']:g} "
            f"({fmt_money(disc['max_discount_amount'], sym)})</b> "
            "iskonto verebilirsiniz."
        )

        if missing > 0:
            self._warn_lbl.setText(
                f"⚠ {missing} ürünün alış fiyatı girilmemiş, kâr hesabı eksik olabilir."
            )
            self._warn_lbl.setVisible(True)
        else:
            self._warn_lbl.setVisible(False)
