"""Gerçek üretim pencere ve sayfaları için durum-aware preview factory'leri."""

from __future__ import annotations

from unittest.mock import patch

from ui_preview.registry import ScenarioContext


_LONG = (
    "Çok Uzun Ünvanlı Örnek Endüstriyel Otomasyon ve Teknoloji "
    "Çözümleri Anonim Şirketi"
)


def make_main_window(context: ScenarioContext):
    from ui.main_window import MainWindow

    class _PreviewBackupService:
        def trigger_now(self, reason=""):
            return None

        def stop(self):
            return None

    with (
        patch.object(MainWindow, "_start_backup_service", autospec=True),
        patch.object(MainWindow, "_start_update_check", autospec=True),
    ):
        window = MainWindow()
    window._backup_svc = _PreviewBackupService()
    page_index = {
        "dashboard": 0,
        "products": 1,
        "customers": 2,
        "create_offer": 4,
        "settings": 5,
        "reports": 6,
        "minimum_size": 0,
        "status_toast": 0,
    }[context.state]
    window._navigate(page_index)
    if context.state == "minimum_size":
        window.resize(window.minimumSize())
    elif context.state == "status_toast":
        window.show_status("Sentetik preview: ayarlar başarıyla kaydedildi.", timeout=0)
    return window


def make_dashboard(context: ScenarioContext):
    from ui.dashboard_page import DashboardPage

    page = DashboardPage()
    page._load()
    if context.state == "filtered":
        page._active_filter = "Onaylandı"
        page.filter_btn.setText("Durum: Onaylandı  ▾")
        page._load()
    elif context.state == "selected" and page._model.rowCount():
        page.table.selectRow(0)
    elif context.state == "long_text":
        page.search.setText(_LONG)
    return page


def make_customers(context: ScenarioContext):
    from ui.customers_page import CustomersPage

    page = CustomersPage()
    page._load()
    if context.state == "selected" and page.table.rowCount():
        page.table.selectRow(0)
    elif context.state == "long_text":
        page.search.setText(_LONG)
        page._load(_LONG)
    return page


def make_products(context: ScenarioContext):
    from ui.products_page import ProductsPage

    page = ProductsPage()
    page._load_category_filter()
    page._load()
    if context.state == "selected" and page.table.rowCount():
        page.table.selectRow(0)
    elif context.state == "long_text":
        page.search.setText("Uzun açıklama: yüksek hassasiyetli dayanıklı gövdeli")
        page._load(page.search.text())
    return page


def make_create_offer(context: ScenarioContext):
    from ui.create_offer_page import CreateOfferPage

    page = CreateOfferPage()
    page.on_enter()
    state = context.state
    if state in {"step_customer_selected", "step_products_populated", "step_products_dense", "step_conditions", "long_text"}:
        if page.customer_combo.count() > 1:
            page.customer_combo.setCurrentIndex(page.customer_combo.count() - 1 if state == "long_text" else 1)
            page._on_customer_selected(page.customer_combo.currentIndex())
    if state in {"step_products_populated", "step_products_dense", "step_conditions", "long_text"}:
        rows = 14 if state == "step_products_dense" else 2
        for index in range(rows):
            page._add_row(
                code=f"PRV-{index + 1:04d}",
                name=_LONG if state == "long_text" else f"Preview Ürün {index + 1}",
                desc="Uzun sentetik ürün açıklaması" if state == "long_text" else "Sentetik açıklama",
                qty=index + 1,
                price=125.50 + index,
                currency="EUR",
                cost=72.25,
            )
    step = {
        "step_customer_empty": 0,
        "step_customer_selected": 0,
        "step_products_empty": 1,
        "step_products_populated": 1,
        "step_products_dense": 1,
        "step_conditions": 2,
        "long_text": 2,
        "validation_error": 0,
    }[state]
    page._set_step(step)
    if state == "long_text":
        page.validity_note.setText(_LONG)
    elif state == "validation_error":
        page.company_edit.setStyleSheet("border: 2px solid #dc2626;")
        page.title_lbl.setText("Yeni Teklif — zorunlu alan eksik")
    return page


def make_reports(context: ScenarioContext):
    from ui.reports_page import ReportsPage

    page = ReportsPage()
    page._generate()
    if context.state == "dense":
        page._report_combo.setCurrentIndex(2)
        page._generate()
    elif context.state == "error":
        page._reset_table()
        page._summary_label.setText(
            "Rapor oluşturulamadı. Ayrıntılar uygulama loguna kaydedildi."
        )
    return page


def make_settings(context: ScenarioContext):
    from PySide6.QtWidgets import QLineEdit
    from ui.settings_page import SettingsPage

    page = SettingsPage()
    page._load()
    if context.state == "empty_assets":
        page.logo_preview.setText("Logo Yok\n(Yükleyin)")
    elif context.state == "long_company_data":
        page.f_name.setText(_LONG)
        page.f_address.setText(_LONG + " Örnek Mahallesi Tasarım Caddesi No: 42")
    elif context.state == "smtp_password_hidden":
        page.tabs.setCurrentIndex(page.tabs.count() - 1)
        page.f_smtp_pass.setText("preview-secret-not-real")
        page.f_smtp_pass.setEchoMode(QLineEdit.EchoMode.Password)
    elif context.state == "dirty":
        page.f_name.setText(page.f_name.text() + " — Düzenleniyor")
        page.save_btn.setText("Kaydet *")
    elif context.state == "save_error":
        page.lbl_smtp_result.setText("Ayarlar kaydedilemedi. Ayrıntılar uygulama loguna kaydedildi.")
        page.lbl_smtp_result.setStyleSheet("color:#dc2626;font-weight:600;")
    return page
