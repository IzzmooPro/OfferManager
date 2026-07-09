"""Uygulama içi PDF önizleme dialog'u — QPdfView tabanlı."""
import logging
import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QMessageBox, QWidget,
)
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPdfWidgets import QPdfView

logger = logging.getLogger("pdf_preview")


class PdfPreviewDialog(QDialog):
    """PDF dosyasını uygulama içinde görüntüler."""

    def __init__(self, pdf_path: str, parent=None,
                 offer_no: str = "", customer_email: str = ""):
        super().__init__(parent)
        self._pdf_path = pdf_path
        self._offer_no = offer_no
        self._customer_email = customer_email

        self.setWindowTitle(f"PDF Önizleme — {offer_no or Path(pdf_path).stem}")
        self.setMinimumSize(700, 850)
        self.resize(780, 950)
        self.setWindowFlags(
            self.windowFlags() | Qt.WindowType.WindowMaximizeButtonHint)

        self._doc = QPdfDocument(self)
        self._build_ui()
        self._load_pdf()
        self._apply_theme()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Toolbar ──────────────────────────────────────────────────────
        toolbar = QWidget()
        toolbar.setObjectName("pdf_toolbar")
        toolbar.setFixedHeight(44)
        tb_lay = QHBoxLayout(toolbar)
        tb_lay.setContentsMargins(10, 4, 10, 4)
        tb_lay.setSpacing(6)

        self._page_lbl = QLabel("Sayfa: 0 / 0")
        self._page_lbl.setObjectName("hint_label")
        tb_lay.addWidget(self._page_lbl)

        tb_lay.addStretch()

        btn_style = "QPushButton { padding: 5px 14px; border-radius: 5px; }"

        btn_zoom_out = QPushButton("−")
        btn_zoom_out.setToolTip("Küçült")
        btn_zoom_out.setFixedWidth(36)
        btn_zoom_out.setStyleSheet(btn_style)
        btn_zoom_out.clicked.connect(self._zoom_out)
        tb_lay.addWidget(btn_zoom_out)

        self._zoom_lbl = QLabel("100%")
        self._zoom_lbl.setFixedWidth(48)
        self._zoom_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tb_lay.addWidget(self._zoom_lbl)

        btn_zoom_in = QPushButton("+")
        btn_zoom_in.setToolTip("Büyüt")
        btn_zoom_in.setFixedWidth(36)
        btn_zoom_in.setStyleSheet(btn_style)
        btn_zoom_in.clicked.connect(self._zoom_in)
        tb_lay.addWidget(btn_zoom_in)

        btn_fit = QPushButton("Sığdır")
        btn_fit.setToolTip("Sayfayı pencereye sığdır")
        btn_fit.setStyleSheet(btn_style)
        btn_fit.clicked.connect(self._zoom_fit)
        tb_lay.addWidget(btn_fit)

        tb_lay.addStretch()

        btn_folder = QPushButton("Klasörde Göster")
        btn_folder.setStyleSheet(btn_style)
        btn_folder.clicked.connect(self._show_in_folder)
        tb_lay.addWidget(btn_folder)

        btn_print = QPushButton("Yazdır")
        btn_print.setStyleSheet(btn_style)
        btn_print.clicked.connect(self._print_pdf)
        tb_lay.addWidget(btn_print)

        btn_email = QPushButton("E-posta Gönder")
        btn_email.setStyleSheet(btn_style)
        btn_email.clicked.connect(self._send_email)
        tb_lay.addWidget(btn_email)

        layout.addWidget(toolbar)

        # ── PDF Görüntüleyici ────────────────────────────────────────────
        self._view = QPdfView(self)
        self._view.setDocument(self._doc)
        self._view.setPageMode(QPdfView.PageMode.MultiPage)
        self._view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        layout.addWidget(self._view, 1)

        # ── Kısayollar ───────────────────────────────────────────────────
        QShortcut(QKeySequence("Ctrl++"), self, self._zoom_in)
        QShortcut(QKeySequence("Ctrl+-"), self, self._zoom_out)
        QShortcut(QKeySequence("Ctrl+0"), self, self._zoom_fit)
        QShortcut(QKeySequence("Escape"), self, self.close)

    def _load_pdf(self):
        self._doc.load(self._pdf_path)
        page_count = self._doc.pageCount()
        if page_count < 1:
            self._page_lbl.setText("PDF yüklenemedi")
            logger.warning("PDF yüklenemedi: %s", self._pdf_path)
            return
        self._page_lbl.setText(
            f"{'Sayfa: 1 / ' + str(page_count) if page_count > 1 else '1 sayfa'}")
        self._view.pageNavigator().currentPageChanged.connect(self._on_page_changed)

    def _on_page_changed(self, page: int):
        total = self._doc.pageCount()
        self._page_lbl.setText(f"Sayfa: {page + 1} / {total}")

    # ── Zoom ─────────────────────────────────────────────────────────────
    _ZOOM_FACTOR = 1.25

    def _zoom_in(self):
        self._view.setZoomMode(QPdfView.ZoomMode.Custom)
        factor = self._view.zoomFactor() * self._ZOOM_FACTOR
        self._view.setZoomFactor(min(factor, 5.0))
        self._update_zoom_label()

    def _zoom_out(self):
        self._view.setZoomMode(QPdfView.ZoomMode.Custom)
        factor = self._view.zoomFactor() / self._ZOOM_FACTOR
        self._view.setZoomFactor(max(factor, 0.2))
        self._update_zoom_label()

    def _zoom_fit(self):
        self._view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        self._update_zoom_label()

    def _update_zoom_label(self):
        pct = int(self._view.zoomFactor() * 100)
        self._zoom_lbl.setText(f"{pct}%")

    # ── Aksiyonlar ───────────────────────────────────────────────────────
    def _show_in_folder(self):
        path = Path(self._pdf_path)
        if not path.exists():
            QMessageBox.warning(self, "Hata", "PDF dosyası bulunamadı.")
            return
        if sys.platform == "win32":
            subprocess.Popen(["explorer", "/select,", str(path)])
        else:
            from PySide6.QtGui import QDesktopServices
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.parent)))

    def _print_pdf(self):
        path = Path(self._pdf_path)
        if not path.exists():
            QMessageBox.warning(self, "Hata", "PDF dosyası bulunamadı.")
            return
        try:
            os.startfile(str(path))
        except OSError:
            from PySide6.QtGui import QDesktopServices
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _send_email(self):
        from ui.dialogs.email_dialog import EmailDialog
        from core.config import load_company_config
        cfg = load_company_config()
        if not cfg.get("smtp_server") or not cfg.get("smtp_user"):
            QMessageBox.warning(
                self, "E-Posta Ayarı Eksik",
                "Önce Ayarlar → E-Posta sekmesinden SMTP bilgilerinizi girin.")
            return
        dlg = EmailDialog(
            pdf_path=self._pdf_path,
            to_email=self._customer_email,
            offer_no=self._offer_no,
            parent=self,
        )
        dlg.exec()

    # ── Tema ─────────────────────────────────────────────────────────────
    def _apply_theme(self):
        from ui.utils.theme_manager import get_theme
        t = get_theme()
        self.setStyleSheet(f"""
            QDialog {{
                background: {t['bg_main']};
            }}
            #pdf_toolbar {{
                background: {t['bg_card']};
                border-bottom: 1px solid {t['border']};
            }}
            #pdf_toolbar QPushButton {{
                background: {t['bg_input']};
                color: {t['text_primary']};
                border: 1px solid {t['border']};
            }}
            #pdf_toolbar QPushButton:hover {{
                background: {t['bg_sidebar_hover']};
                border-color: {t['accent_blue']};
            }}
            #hint_label {{
                color: {t['text_secondary']};
                font-size: 12px;
            }}
            QLabel {{
                color: {t['text_primary']};
            }}
        """)
