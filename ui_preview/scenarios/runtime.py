"""Metot içinde üretilen gerçek runtime modal preview factory'leri."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from ui_preview.registry import ScenarioContext


def _capture_message_boxes(action):
    from PySide6.QtWidgets import QDialog, QMessageBox

    captured = []

    def _capture(box):
        captured.append(box)
        return QDialog.DialogCode.Rejected

    with patch.object(QMessageBox, "exec", _capture):
        action()
    if not captured:
        raise RuntimeError("Runtime modal üretilemedi")
    box = captured[-1]
    box.setParent(None)
    for previous in captured[:-1]:
        previous.deleteLater()
    return box


def make_startup_splash(context: ScenarioContext):
    from PySide6.QtWidgets import QGraphicsOpacityEffect
    from ui.startup_splash import StartupSplash

    splash = StartupSplash()
    progress, message = {
        "visible": (0.35, "Ayarlar okunuyor…"),
        "fading": (1.0, "Hazır!"),
        "handoff": (1.0, "Arayüz açılıyor…"),
    }[context.state]
    splash.set_progress(progress, message)
    if context.state == "fading":
        opacity = QGraphicsOpacityEffect(splash)
        opacity.setOpacity(0.45)
        splash.setGraphicsEffect(opacity)
    return splash


def make_expired_offers(context: ScenarioContext):
    from ui.dashboard_page import DashboardPage

    page = DashboardPage()
    count = 1 if context.state == "single" else 7
    offers = [
        SimpleNamespace(
            id=index + 1,
            offer_no=("PRV-2026-0001-" + "UZUN-" * 8)
            if context.state == "long_customer_name" else f"PRV-2026-{index + 1:04d}",
        )
        for index in range(count)
    ]
    page.svc_o.get_expired_pending = lambda: offers
    box = _capture_message_boxes(page._prompt_expired_offers)
    page.deleteLater()
    return box


def make_pdf_created(context: ScenarioContext):
    from ui.dashboard_page import DashboardPage

    page = DashboardPage()
    generated = []
    errors = []
    if context.state in {"success", "partial_success"}:
        generated = [("PRV-2026-0001.pdf", {
            "offer_no": "PRV-2026-0001", "customer_email": "musteri@example.invalid",
        })]
    if context.state in {"partial_success", "error"}:
        errors = [(RuntimeError("sentetik preview hatası"), 1)]
    box = _capture_message_boxes(lambda: page._on_pdf_finished(generated, errors))
    page.deleteLater()
    return box


def make_customer_registration(context: ScenarioContext):
    from ui.create_offer_page import CreateOfferPage
    from ui.utils import operation_error_dialog

    page = CreateOfferPage()
    if context.state == "save_error":
        box = _capture_message_boxes(
            lambda: operation_error_dialog.hata_goster(
                page, "Hata", RuntimeError("sentetik"), "Müşteri", "kaydet")
        )
    else:
        page.customer_combo.setEditable(True)
        page.customer_combo.setCurrentText("Preview Yeni Müşteri A.Ş.")
        page.customer_svc.search = lambda _name: []
        box = _capture_message_boxes(page._check_customer_registration)
    page.deleteLater()
    return box


def make_existing_offer_items(context: ScenarioContext):
    from PySide6.QtWidgets import QInputDialog
    from services.template_service import TemplateService
    from ui.create_offer_page import CreateOfferPage

    page = CreateOfferPage()
    page._add_row(code="PRD-0001", name="Preview Ürün", price=125, currency="EUR")
    template = SimpleNamespace(template_name="Preview Şablonu", items=[], currency="EUR")
    with (
        patch.object(TemplateService, "get_all", return_value=[template]),
        patch.object(QInputDialog, "getItem", return_value=("Preview Şablonu  (0 kalem, EUR)", True)),
    ):
        box = _capture_message_boxes(page._load_from_template)
    page.deleteLater()
    return box


def make_offer_saved(context: ScenarioContext):
    from pathlib import Path
    from PySide6.QtWidgets import QFileDialog
    from pdf import pdf_generator
    from ui.create_offer_page import CreateOfferPage

    page = CreateOfferPage()
    output = context.sandbox.paths.data / "preview-offer-result.pdf"
    output.write_bytes(b"%PDF-1.4\n% preview\n")
    data = SimpleNamespace(offer_no="PRV-2026-0001")

    page._validate_step1 = lambda: True
    page._validate_products = lambda: True
    page._validate_pdf_requirements = lambda: True
    page._collect_data = lambda: data
    page.offer_svc.preview_offer_no = lambda: "PRV-2026-0001"
    page.offer_svc.save = lambda _data: 1
    page._reset_to_new = lambda: None
    if context.state == "error":
        page.offer_svc.save = lambda _data: (_ for _ in ()).throw(RuntimeError("sentetik"))

    def _generate(_data, path):
        Path(path).write_bytes(b"%PDF-1.4\n% preview\n")

    patches = [
        patch.object(QFileDialog, "getSaveFileName", return_value=(str(output), "PDF")),
        patch.object(pdf_generator, "generate_pdf", _generate),
    ]
    if context.state == "partial_success":
        import shutil
        patches.append(patch.object(shutil, "copy2", side_effect=OSError("sentetik")))
    with patches[0], patches[1]:
        if len(patches) == 3:
            with patches[2]:
                box = _capture_message_boxes(page._finish_offer)
        else:
            box = _capture_message_boxes(page._finish_offer)
    page.deleteLater()
    return box


def make_import_confirmation(context: ScenarioContext):
    from PySide6.QtWidgets import QFileDialog
    from ui.utils import excel_import

    kind = "products" if context.state == "products" else "customers"
    valid = [{"company_name": "Preview Müşteri"}]
    duplicates = ([{"company_name": "Mükerrer Preview"}]
                  if context.state in {"warnings", "long_summary"} else [])
    invalid = ([{"_error": "Satır 3: zorunlu alan eksik"}]
               if context.state in {"warnings", "long_summary"} else [])
    if context.state == "long_summary":
        invalid *= 8
    with (
        patch.object(QFileDialog, "getOpenFileName", return_value=("preview-import.xlsx", "")),
        patch.object(excel_import, "_sayfa_sec_onceden", return_value=(None, "")),
        patch.object(excel_import, "_read_file", return_value=([{}], "")),
        patch.object(excel_import, "_validate_rows", return_value=(valid, duplicates, invalid)),
    ):
        return _capture_message_boxes(lambda: excel_import.run_import_flow(None, kind))


def make_offer_import_confirmation(context: ScenarioContext):
    from ui.utils import excel_import

    group = {"items": [{"x": 1}], "offer_no": "PRV-2026-0001"}
    dups = ["PRV-2026-0002"] if context.state != "normal" else []
    invalid = ["Satır 7: teklif numarası eksik"] if context.state != "normal" else []
    if context.state == "long_summary":
        invalid *= 8
    with patch.object(excel_import, "_validate_offer_rows", return_value=([group], dups, invalid)):
        return _capture_message_boxes(
            lambda: excel_import._run_offer_import_flow(None, "preview-offers.xlsx", [{}]))


def make_import_all_confirmation(context: ScenarioContext):
    from PySide6.QtWidgets import QFileDialog
    from ui.utils import excel_import

    sheets = {"Müşteriler": [{}], "Ürünler": [{}], "Teklifler": [{}]}
    duplicates = [{}] if context.state in {"warnings", "long_summary"} else []
    invalid = [{"_error": "Satır 4: geçersiz"}] if context.state != "normal" else []
    if context.state == "long_summary":
        invalid *= 8
    offer = {"items": [{"x": 1}]}
    with (
        patch.object(QFileDialog, "getOpenFileName", return_value=("preview-all.xlsx", "")),
        patch.object(excel_import, "_read_xlsx_sheets", return_value=(sheets, "")),
        patch.object(excel_import, "_validate_rows", return_value=([{}], duplicates, invalid)),
        patch.object(excel_import, "_validate_offer_rows", return_value=([offer], [], [])),
    ):
        return _capture_message_boxes(lambda: excel_import.run_import_all_flow(None))


def make_operation_error(context: ScenarioContext):
    import sqlite3
    from PySide6.QtWidgets import QMessageBox
    from ui.utils import operation_error_dialog

    messages = {
        "validation": ("Eksik Bilgi", "Lütfen zorunlu alanları doldurun.", QMessageBox.Icon.Information, False),
        "conflict": ("Çakışma", "Bu kayıt başka bir işlem tarafından değiştirildi.", QMessageBox.Icon.Warning, False),
        "database_busy": ("Veritabanı Meşgul", "Veritabanı meşgul. Lütfen yeniden deneyin.", QMessageBox.Icon.Warning, False),
        "technical_with_actions": ("Hata", "İşlem tamamlanamadı. Ayrıntılar uygulama loguna kaydedildi.", QMessageBox.Icon.Warning, True),
        "long_safe_message": ("Kısmi Sonuç", "Teklif kaydedildi ancak ekran yenilenemedi. " * 5, QMessageBox.Icon.Warning, True),
    }
    title, message, icon, actions = messages[context.state]
    report = (sqlite3.OperationalError("sentetik"), "Preview işlemi") if actions else None
    return _capture_message_boxes(
        lambda: operation_error_dialog._kutu(None, title, message, icon, actions, report)
    )
