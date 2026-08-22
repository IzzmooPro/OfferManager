"""Aşama 3 launcher doğrulaması için temel gerçek-widget factory'leri."""

from __future__ import annotations

from ui_preview.registry import ScenarioContext


def make_nav_card(_context: ScenarioContext):
    from ui.main_window import NavCard

    card = NavCard("Dashboard")
    card.setMinimumSize(220, 48)
    return card


def make_plus_button(_context: ScenarioContext):
    from ui.widgets._plus_button import PlusButton

    button = PlusButton()
    button.setObjectName("icon_btn")
    button.setFixedSize(48, 48)
    button.setToolTip("Sentetik preview düğmesi")
    return button


def make_profit_panel(_context: ScenarioContext):
    from ui.widgets._profit_panel import ProfitPanel

    panel = ProfitPanel()
    panel.setMinimumWidth(720)
    panel.set_currency_symbol("€")
    panel.update_values(
        total_cost=6200.0,
        subtotal=10000.0,
        net_total=9500.0,
        row_costs=[1200.0, 2100.0, 2900.0],
    )
    panel._toggle()
    return panel


def make_resizable_table(_context: ScenarioContext):
    from PySide6.QtWidgets import QTableWidgetItem
    from ui.widgets._resizable_table import ResizableTable

    table = ResizableTable(4, 4)
    table.setHorizontalHeaderLabels(["Kod", "Ürün", "Miktar", "Tutar"])
    rows = [
        ("PRD-0001", "Preview Sensör", "2", "184,70 €"),
        ("PRD-0002", "Kontrol Modülü", "1", "249,90 €"),
        ("PRD-0003", "Endüstriyel Haberleşme Birimi", "4", "780,00 €"),
        ("PRD-0004", "Montaj Aksesuarı", "8", "96,00 €"),
    ]
    for row, values in enumerate(rows):
        for column, value in enumerate(values):
            table.setItem(row, column, QTableWidgetItem(value))
    table.setup_columns([
        ("interactive", 130), ("stretch", None),
        ("fixed", 90), ("interactive", 130),
    ])
    return table


def make_step_indicator(_context: ScenarioContext):
    from ui.create_offer_page import StepIndicator

    indicator = StepIndicator(["Müşteri", "Ürünler", "Koşullar"])
    indicator.setMinimumWidth(720)
    indicator.set_step(0)
    return indicator
