"""Yeniden kullanılabilir gerçek üretim bileşeni senaryoları."""

from __future__ import annotations

from ui_preview.registry import ScenarioContext


def make_nav_card(context: ScenarioContext):
    from ui.main_window import NavCard

    title = (
        "Çok Uzun Navigasyon Başlığı ile Taşma Kontrolü"
        if context.state == "long_title" else "Dashboard"
    )
    card = NavCard(title)
    card.setMinimumSize(240, 52)
    card.setChecked(context.state == "checked")
    card.setDisabled(context.state == "disabled")
    return card


def make_table_combo(context: ScenarioContext):
    from ui.create_offer_page import _TableComboBox

    combo = _TableComboBox()
    combo.setMinimumWidth(360)
    combo.addItems([
        "",
        "Adet",
        "Metre",
        "Çok Uzun Birim Açıklaması — Endüstriyel Paket",
    ])
    if context.state == "selected":
        combo.setCurrentText("Adet")
    elif context.state == "long_text":
        combo.setCurrentIndex(3)
    elif context.state == "focused":
        combo.setCurrentText("Metre")
        combo.setFocus()
    return combo


def make_table_spin(context: ScenarioContext):
    from ui.create_offer_page import _TableSpinBox

    spin = _TableSpinBox(empty_value=1)
    spin.setRange(0, 9_999_999)
    spin.setMinimumWidth(220)
    if context.state == "value":
        spin.setValue(1250.75)
    elif context.state == "focused":
        spin.setValue(42)
        spin.setFocus()
        spin.selectAll()
    elif context.state == "disabled":
        spin.setValue(18)
        spin.setDisabled(True)
    else:
        spin.clear()
    return spin


def make_step_indicator(context: ScenarioContext):
    from ui.create_offer_page import StepIndicator

    steps = ["Müşteri", "Ürünler", "Koşullar"]
    if context.state == "long_titles":
        steps = [
            "Müşteri ve İletişim Bilgileri",
            "Ürün, Miktar ve Fiyatlandırma",
            "Teklif Koşulları ve Son Kontrol",
        ]
    indicator = StepIndicator(steps)
    indicator.setMinimumWidth(780)
    index = {"first": 0, "middle": 1, "last": 2, "long_titles": 1}[context.state]
    indicator.set_step(index)
    return indicator


def make_settings_preview_box(context: ScenarioContext):
    from PySide6.QtGui import QPixmap
    from ui.settings_page import _PreviewBox

    box = _PreviewBox("Görsel seçilmedi")
    box.setFixedSize(480, 180)
    if context.state == "image":
        path = context.sandbox.paths.data / context.manifest["relative_paths"]["logo"]
        box.setPixmap(QPixmap(str(path)).scaled(420, 150))
    elif context.state == "disabled":
        box.setText("Logo devre dışı")
        box.setDisabled(True)
    return box


def make_animated_card(context: ScenarioContext):
    from PySide6.QtWidgets import QLabel, QVBoxLayout
    from ui.widgets._animated_card import AnimatedCard

    card = AnimatedCard()
    card.setMinimumSize(360, 140)
    layout = QVBoxLayout(card)
    title = QLabel("Animasyonlu Preview Kartı")
    title.setObjectName("section_card_title")
    detail = QLabel(f"Durum: {context.state}")
    detail.setObjectName("card_label")
    layout.addWidget(title)
    layout.addWidget(detail)
    card.setDisabled(context.state == "disabled")
    return card


def make_dashboard_stat_card(context: ScenarioContext):
    from ui.dashboard_page import StatCard

    title = (
        "Çok Uzun Dashboard İstatistik Başlığı"
        if context.state == "long_title" else "Toplam Müşteri"
    )
    card = StatCard(title, "#3a7bd5")
    card.setMinimumWidth(360)
    card.set_value("9.999.999" if context.state == "large_value" else 128)
    return card


def make_dashboard_offer_stat_card(context: ScenarioContext):
    from ui.dashboard_page import OfferStatCard

    card = OfferStatCard()
    card.setMinimumWidth(440)
    values = {
        "empty": {},
        "normal": {"Beklemede": 12, "Onaylandı": 28, "İptal": 4},
        "large_counts": {"Beklemede": 98765, "Onaylandı": 123456, "İptal": 8765},
    }[context.state]
    card.set_values(values)
    return card


def make_dashboard_revenue_card(context: ScenarioContext):
    from ui.dashboard_page import RevenueCard

    card = RevenueCard()
    card.setMinimumWidth(520)
    if context.state == "empty":
        card.set_revenue({}, {})
    elif context.state == "large_values":
        card.set_revenue(
            {"EUR": 9_876_543.21, "USD": 8_765_432.10},
            {"EUR": 98_765_432.10, "USD": 87_654_321.09, "TL": 765_432_100},
        )
    else:
        card.set_revenue({"EUR": 18450, "USD": 9200}, {"EUR": 128400})
    return card


def make_plus_button(context: ScenarioContext):
    from ui.widgets._plus_button import PlusButton

    button = PlusButton()
    button.setObjectName("icon_btn")
    button.setFixedSize(48, 48)
    button.setToolTip(f"Artı düğmesi — {context.state}")
    button.setDisabled(context.state == "disabled")
    return button


def make_profit_panel(context: ScenarioContext):
    from ui.widgets._profit_panel import ProfitPanel

    panel = ProfitPanel()
    panel.setMinimumWidth(760)
    panel.set_currency_symbol("€")
    values = {
        "hidden": (6200, 10000, 9500, [1200, 2100, 2900]),
        "positive": (6200, 10000, 9500, [1200, 2100, 2900]),
        "negative": (11200, 10000, 9000, [5200, 6000, 0]),
        "large_values": (62_000_000, 100_000_000, 95_000_000, [12_000_000, 21_000_000, 29_000_000]),
    }[context.state]
    panel.update_values(*values)
    if context.state != "hidden":
        panel._toggle()
    return panel


def make_resizable_table(context: ScenarioContext):
    from PySide6.QtWidgets import QTableWidgetItem
    from ui.widgets._resizable_table import ResizableTable

    row_count = {"empty": 0, "populated": 4, "dense": 80, "narrow": 8, "wide": 8}[context.state]
    table = ResizableTable(row_count, 4)
    table.setHorizontalHeaderLabels(["Kod", "Ürün", "Miktar", "Tutar"])
    for row in range(row_count):
        values = (
            f"PRD-{row + 1:04d}",
            f"Preview Endüstriyel Ürün {row + 1:03d}",
            str((row % 9) + 1),
            f"{(row + 1) * 83.75:,.2f} €",
        )
        for column, value in enumerate(values):
            table.setItem(row, column, QTableWidgetItem(value))
    table.setup_columns([
        ("interactive", 130), ("stretch", None),
        ("fixed", 90), ("interactive", 140),
    ])
    if context.state == "narrow":
        table.setMinimumWidth(420)
    elif context.state == "wide":
        table.setMinimumWidth(1200)
    return table
