"""Gerçek üretim diyalogları için sentetik preview factory'leri."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from ui_preview.registry import ScenarioContext


_LONG = (
    "Çok Uzun Ünvanlı Örnek Endüstriyel Otomasyon ve Teknoloji "
    "Çözümleri Anonim Şirketi"
)


def _sample_pdf(context: ScenarioContext) -> Path:
    return context.sandbox.paths.data / context.manifest["relative_paths"]["sample_pdf"]


def make_customer_dialog(context: ScenarioContext):
    from ui.customers_page import CustomerDialog

    dialog = CustomerDialog()
    if context.state in {"edit", "long_text", "save_error"}:
        dialog.company.setText(_LONG if context.state == "long_text" else "Preview Müşteri A.Ş.")
        dialog.contact.setText("Deniz Örnek")
        dialog.address.setText(_LONG if context.state == "long_text" else "Örnek Mah. No: 42")
        dialog.phone.setText("+90 212 000 00 00")
        dialog.email.setText("musteri@example.invalid")
    elif context.state == "validation_error":
        dialog.company.setPlaceholderText("Firma adı zorunludur")
        dialog.company.setStyleSheet("border:2px solid #dc2626;")
    if context.state == "save_error":
        dialog.notes.setPlainText("Kayıt başarısız oldu; güvenli hata mesajı preview durumu.")
    return dialog


def make_product_dialog(context: ScenarioContext):
    from ui.products_page import ProductDialog

    dialog = ProductDialog()
    if context.state in {"edit", "long_text", "duplicate", "save_error"}:
        dialog.code.setText("PRD-0001")
        dialog.name.setText(_LONG if context.state == "long_text" else "Preview Sensör")
        dialog.desc.setPlainText(_LONG if context.state == "long_text" else "Sentetik ürün açıklaması")
        dialog.price.setValue(1250.75)
        dialog.cost_price.setValue(720.25)
        dialog.stock.setValue(42)
    elif context.state == "validation_error":
        dialog.code.setStyleSheet("border:2px solid #dc2626;")
        dialog.name.setStyleSheet("border:2px solid #dc2626;")
    if context.state == "duplicate":
        dialog.code_warn.setText("Bu ürün kodu zaten kullanılıyor.")
    elif context.state == "save_error":
        dialog.code_warn.setText("Ürün kaydedilemedi. Ayrıntılar uygulama loguna kaydedildi.")
    return dialog


def make_product_select(context: ScenarioContext):
    from ui.create_offer_page import ProductSelectDialog

    dialog = ProductSelectDialog()
    if context.state == "filtered":
        dialog._search_edit.setText("Preview Ürün 001")
        dialog._load(dialog._search_edit.text(), -1)
    elif context.state == "multi_selected" and dialog.table.rowCount():
        dialog.table.selectRow(0)
        if dialog.table.rowCount() > 1:
            dialog.table.selectRow(1)
    elif context.state == "long_text":
        dialog._search_edit.setText("yüksek hassasiyetli dayanıklı gövdeli")
        dialog._load(dialog._search_edit.text(), -1)
    return dialog


def make_category_manager(context: ScenarioContext):
    from ui.dialogs.category_dialog import CategoryManagerDialog

    dialog = CategoryManagerDialog()
    if context.state == "selected" and dialog._list.count():
        dialog._list.setCurrentRow(0)
    elif context.state == "long_text":
        dialog._name_edit.setText(_LONG)
    elif context.state == "error":
        dialog._name_edit.setPlaceholderText("Kategori kaydedilemedi")
        dialog._name_edit.setStyleSheet("border:2px solid #dc2626;")
    return dialog


def make_customer_history(context: ScenarioContext):
    from ui.dialogs.customer_history_dialog import CustomerHistoryDialog

    dialog = CustomerHistoryDialog()
    if context.state != "empty" and dialog.combo.count() > 1:
        index = dialog.combo.count() - 1 if context.state == "long_text" else 1
        dialog.combo.setCurrentIndex(index)
        if dialog._sum_total._val.text() == "—":
            raise RuntimeError("Müşteri geçmişi populated durumu yüklenemedi")
    return dialog


def make_email(context: ScenarioContext):
    from ui.dialogs.email_dialog import EmailDialog

    dialog = EmailDialog(
        str(_sample_pdf(context)),
        customer_email="musteri@example.invalid",
        offer_no="PRV-2026-0001",
    )
    state = context.state
    if state == "sending":
        dialog.btn_send.setText("Gönderiliyor…")
        dialog.btn_send.setEnabled(False)
    elif state == "success":
        dialog._closing_lbl.setText("E-posta başarıyla gönderildi.")
        dialog._closing_lbl.setVisible(True)
    elif state == "validation_error":
        dialog.to_input.clear()
        dialog.to_input.setPlaceholderText("Geçerli bir alıcı e-posta adresi girin")
        dialog.to_input.setStyleSheet("border:2px solid #dc2626;")
    elif state == "send_error":
        dialog._closing_lbl.setText("E-posta gönderilemedi. Ayarları kontrol edin.")
        dialog._closing_lbl.setVisible(True)
    elif state == "closing":
        dialog._closing = True
        dialog._closing_lbl.setVisible(True)
        dialog.btn_send.setEnabled(False)
    return dialog


def make_feedback(context: ScenarioContext):
    from ui.dialogs.feedback_dialog import FeedbackDialog

    technical = context.state == "technical_error"
    dialog = FeedbackDialog(
        exc=RuntimeError("sentetik preview hatası") if technical else None,
        islem="Preview arayüz doğrulaması" if technical else "",
    )
    descriptions = {
        "suggestion": "Arayüz için sentetik bir öneri açıklaması.",
        "problem": "Bir iş akışında yaşanan sentetik problem açıklaması.",
        "technical_error": "Teknik hata sonrası görülen sentetik açıklama.",
        "long_description": (_LONG + " ") * 8,
        "mailto_unavailable": "E-posta uygulaması açılamadığında pano alternatifi görünür.",
    }
    dialog._aciklama.setPlainText(descriptions[context.state])
    if context.state == "mailto_unavailable":
        dialog._durum.setText("E-posta uygulaması açılamadı. Panoya Kopyala'yı kullanın.")
    return dialog


def make_backup(context: ScenarioContext):
    from PySide6.QtWidgets import QTabWidget
    from ui.dialogs.backup_manager import BackupDialog

    dialog = BackupDialog()
    tabs = dialog.findChild(QTabWidget)
    if context.state.startswith("restore") or context.state in {"preflight_error", "rollback_error"}:
        tabs.setCurrentIndex(1)
    messages = {
        "backup_progress": "Yedek oluşturuluyor… %60",
        "restore_progress": "Yedek geri yükleniyor… %45",
        "success": "Son yedek: 15.08.2026 12:00 — tamamlandı",
        "preflight_error": "Geri yükleme başlatılamadı: yedek ön denetimi geçmedi.",
        "rollback_error": "Geri yükleme tamamlanamadı; önceki duruma dönüş de tamamlanamadı.",
    }
    if context.state in messages:
        dialog.lbl_last.setText(messages[context.state])
    return dialog


def make_pdf_preview(context: ScenarioContext):
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from ui.dialogs.pdf_preview_dialog import PdfPreviewDialog

    path = _sample_pdf(context)
    if context.state == "multi_page":
        path = context.sandbox.paths.data / "offers_pdf" / "multi-page-preview.pdf"
        pdf = canvas.Canvas(str(path), pagesize=A4, invariant=1)
        for page_no in range(1, 4):
            pdf.drawString(72, 780, f"OMS UI PREVIEW — PAGE {page_no}")
            pdf.showPage()
        pdf.save()
    elif context.state == "load_error":
        path = context.sandbox.paths.data / "offers_pdf" / "missing-preview.pdf"
    offer_no = _LONG if context.state == "long_offer_number" else "PRV-2026-0001"
    return PdfPreviewDialog(str(path), offer_no=offer_no, customer_email="musteri@example.invalid")


def make_how_to_use(context: ScenarioContext):
    from PySide6.QtWidgets import QScrollArea
    from ui.dialogs.help_dialogs import HowToUseDialog

    dialog = HowToUseDialog()
    if context.state == "minimum_size":
        dialog.resize(dialog.minimumSize())
    elif context.state == "scrolled":
        area = dialog.findChild(QScrollArea)
        if area:
            area.verticalScrollBar().setValue(area.verticalScrollBar().maximum())
    return dialog


def make_about(context: ScenarioContext):
    from ui.dialogs.help_dialogs import AboutDialog

    dialog = AboutDialog()
    labels = {
        "update_checking": ("Kontrol ediliyor…", False),
        "up_to_date": ("Uygulama güncel ✓", True),
        "update_error": ("Güncelleme kontrol edilemedi", True),
    }
    if context.state in labels:
        text, enabled = labels[context.state]
        dialog.update_btn.setText(text)
        dialog.update_btn.setEnabled(enabled)
    return dialog


def make_update(context: ScenarioContext):
    from ui.utils.updater import UpdateDialog

    dialog = UpdateDialog(
        "v9.9-preview", "https://example.invalid/preview.exe",
        expected_sha256="A" * 64, expected_size=123456,
    )
    state = context.state
    if state != "available":
        dialog._progress.setVisible(True)
        dialog._status.setVisible(True)
    values = {
        "downloading": (42, "İndiriliyor…"),
        "verifying": (100, "Doğrulanıyor…"),
        "ready": (100, "Güncelleme kuruluma hazır."),
        "download_error": (18, "Güncelleme indirilemedi."),
        "verification_error": (100, "Güncelleme dosyası doğrulanamadı."),
        "closing": (73, "İndirme tamamlanıyor — pencere işlem bitince kapanacak."),
    }
    if state in values:
        value, text = values[state]
        dialog._progress.setValue(value)
        dialog._status.setText(text)
        dialog._btn_update.setEnabled(False)
    return dialog


def make_import_progress(context: ScenarioContext):
    from ui.utils.excel_import import _ImportProgress

    label = (
        "Çok uzun sentetik içe aktarma açıklaması ile kayıtlar denetleniyor…"
        if context.state == "long_label" else "Kayıtlar içe aktarılıyor…"
    )
    progress = _ImportProgress(None, label)
    value = {"start": 0, "middle": 50, "complete": 100, "long_label": 35}[context.state]
    progress(value, 100)
    return progress._dlg


def make_date_picker(context: ScenarioContext):
    from PySide6.QtCore import QDate
    from PySide6.QtWidgets import QCalendarWidget, QDialog
    from ui.create_offer_page import CreateOfferPage

    page = CreateOfferPage()
    captured = []

    def _capture(dialog):
        captured.append(dialog)
        return QDialog.DialogCode.Rejected

    with patch.object(QDialog, "exec", _capture):
        page._pick_date()
    dialog = captured[0]
    dialog.setParent(None)
    calendar = dialog.findChild(QCalendarWidget)
    if context.state == "selected_date" and calendar:
        calendar.setSelectedDate(QDate(2026, 8, 15))
    page.deleteLater()
    return dialog
