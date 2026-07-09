"""Müşteri yönetim sayfası."""
import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidgetItem, QLineEdit, QDialog,
    QFormLayout, QMessageBox, QFrame, QTextEdit
)
from PySide6.QtCore import Qt, QEvent
from services.customer_service import CustomerService
from services.offer_service import OfferService
from models.customer import Customer
from ui.widgets._resizable_table import ResizableTable
from ui.widgets._row_hover_delegate import RowHoverDelegate
from core.date_utils import to_display_date

logger = logging.getLogger("customers")


class CustomerDialog(QDialog):
    def __init__(self, parent=None, customer=None):
        super().__init__(parent)
        self.setWindowTitle("Müşteri Ekle" if not customer else "Müşteri Düzenle")
        self.setMinimumWidth(460)
        self.setMaximumHeight(500)
        self.customer = customer
        self._build_ui()
        if customer:
            self._fill(customer)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel(self.windowTitle())
        title.setStyleSheet("font-size:11pt;font-weight:700;")
        layout.addWidget(title)

        form = QFormLayout()
        form.setSpacing(10)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self.company = QLineEdit(); self.company.setMinimumHeight(34)
        self.contact = QLineEdit(); self.contact.setMinimumHeight(34)
        self.address = QLineEdit(); self.address.setMinimumHeight(34)
        self.phone   = QLineEdit(); self.phone.setMinimumHeight(34)
        self.email   = QLineEdit(); self.email.setMinimumHeight(34)
        self.notes   = QTextEdit(); self.notes.setMaximumHeight(60)
        self.notes.setPlaceholderText("Müşteriye özel not veya açıklama...")

        for lbl, w in [("Firma Adı *:", self.company), ("İlgili Kişi:", self.contact),
                        ("Adres:", self.address), ("Telefon:", self.phone),
                        ("E-posta:", self.email), ("Not:", self.notes)]:
            form.addRow(lbl, w)
        layout.addLayout(form)
        layout.addStretch()

        btns = QHBoxLayout()
        ok = QPushButton("Kaydet");  ok.setObjectName("primary");   ok.clicked.connect(self._save)
        no = QPushButton("İptal");   no.setObjectName("secondary"); no.clicked.connect(self.reject)
        btns.addStretch(); btns.addWidget(no); btns.addWidget(ok)
        layout.addLayout(btns)

    def _fill(self, c):
        self.company.setText(c.company_name)
        self.contact.setText(c.contact_person)
        self.address.setText(c.address)
        self.phone.setText(c.phone)
        self.email.setText(c.email)
        self.notes.setPlainText(c.notes)

    def _save(self):
        if not self.company.text().strip():
            QMessageBox.warning(self, "Hata", "Firma adı zorunludur."); return
        self.accept()

    def get_customer(self) -> Customer:
        c = self.customer or Customer()
        c.company_name   = self.company.text().strip()
        c.contact_person = self.contact.text().strip()
        c.address        = self.address.text().strip()
        c.phone          = self.phone.text().strip()
        c.email          = self.email.text().strip()
        c.notes          = self.notes.toPlainText().strip()
        return c


class CustomersPage(QWidget):
    def __init__(self):
        super().__init__()
        self.service      = CustomerService()
        self.offer_svc    = OfferService()
        self._customers   = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 12)
        layout.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel("Müşteri Yönetimi")
        title.setStyleSheet("font-size:14pt;font-weight:700;")
        header.addWidget(title); header.addStretch()
        add_btn = QPushButton("+ Yeni Müşteri")
        add_btn.setObjectName("primary"); add_btn.clicked.connect(self._add)
        header.addWidget(add_btn)
        layout.addLayout(header)

        toolbar = QFrame(); toolbar.setObjectName("toolbar")
        t = QHBoxLayout(toolbar); t.setContentsMargins(8, 4, 8, 4)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Firma adı veya ilgili kişiyle ara...")
        self.search.textChanged.connect(lambda txt: self._load(txt))
        t.addWidget(self.search)
        for lbl, slot, obj in [("Geçmiş",  self._history, "tab_btn_clone"),
                               ("Düzenle", self._edit,    "tab_btn_edit"),
                               ("Sil",     self._delete,  "tab_btn_delete")]:
            b = QPushButton(lbl); b.setObjectName(obj)
            b.setMinimumHeight(36); b.setMinimumWidth(82)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(slot)
            t.addWidget(b)
        layout.addWidget(toolbar)

        # ResizableTable — Excel benzeri + Türkçe sağ tık
        self.table = ResizableTable()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(
            ["Firma Adı","İlgili Kişi","Adres","Telefon","E-posta","Teklif","Son Teklif"])
        # Firma Adı / Adres / E-posta esner — pencere büyüyünce tablo yayılır
        # (sabit sütun + tek seferlik dağıtım pencere boyutunu takip etmiyordu)
        self.table.setup_columns([
            ('stretch',     None),   # Firma Adı
            ('interactive', 110),    # İlgili Kişi
            ('stretch',     None),   # Adres
            ('interactive', 110),    # Telefon
            ('stretch',     None),   # E-posta
            ('interactive',  60),    # Teklif
            ('interactive',  95),    # Son Teklif
        ])
        self.table.setEditTriggers(self.table.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(self.table.SelectionBehavior.SelectRows)
        # Shift/Ctrl ile çoklu satır seçimi — toplu silme için
        self.table.setSelectionMode(self.table.SelectionMode.ExtendedSelection)
        self.table.setAlternatingRowColors(False)
        self.table.verticalHeader().setVisible(False)
        self.table.doubleClicked.connect(self._edit)
        self.table.on_edit   = self._edit
        self.table.on_delete = self._delete

        self._delegate = RowHoverDelegate(self)
        for col in range(7):
            self.table.setItemDelegateForColumn(col, self._delegate)
        self.table.setMouseTracking(True)
        self.table.viewport().setMouseTracking(True)
        self.table.viewport().installEventFilter(self)

        layout.addWidget(self.table)
        self._load()

    def _load(self, keyword=""):
        logger.debug("Müşteriler yükleniyor, anahtar='%s'", keyword)
        try:
            self._customers = self.service.search(keyword) if keyword else self.service.get_all()
            summaries = self.offer_svc.get_all_customer_summaries()
            self.table.setRowCount(len(self._customers))
            for row, c in enumerate(self._customers):
                self.table.setItem(row, 0, QTableWidgetItem(c.company_name))
                self.table.setItem(row, 1, QTableWidgetItem(c.contact_person))
                self.table.setItem(row, 2, QTableWidgetItem(c.address))
                self.table.setItem(row, 3, QTableWidgetItem(c.phone))
                self.table.setItem(row, 4, QTableWidgetItem(c.email))
                s = summaries.get(c.id)
                if s:
                    cnt_item = QTableWidgetItem(str(s["total"]))
                    cnt_item.setTextAlignment(
                        Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
                    self.table.setItem(row, 5, cnt_item)
                    self.table.setItem(row, 6, QTableWidgetItem(
                        to_display_date(s["last_date"])))
                else:
                    cnt_item = QTableWidgetItem("0")
                    cnt_item.setTextAlignment(
                        Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
                    self.table.setItem(row, 5, cnt_item)
                    self.table.setItem(row, 6, QTableWidgetItem("—"))
        except Exception as e:
            logger.error("Müşteri yükleme hatası: %s", e, exc_info=True)

    def _selected(self):
        row = self.table.currentRow()
        return self._customers[row] if 0 <= row < len(self._customers) else None

    def _selected_all(self):
        """Seçili tüm müşteriler (çoklu seçim)."""
        rows = sorted({i.row() for i in self.table.selectionModel().selectedRows()})
        return [self._customers[r] for r in rows if 0 <= r < len(self._customers)]

    def _add(self):
        dlg = CustomerDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            try:
                self.service.add(dlg.get_customer())
                logger.info("Müşteri eklendi.")
                self._load()
            except Exception as e:
                logger.error("Müşteri ekleme hatası: %s", e, exc_info=True)
                QMessageBox.warning(self, "Hata", f"Müşteri eklenemedi:\n{e}")

    def _history(self):
        c = self._selected()
        if not c:
            QMessageBox.information(self, "Bilgi", "Lütfen bir müşteri seçin."); return
        from ui.dialogs.customer_history_dialog import CustomerHistoryDialog
        CustomerHistoryDialog(self, preselect_customer_id=c.id).exec()

    def _edit(self):
        c = self._selected()
        if not c:
            QMessageBox.information(self, "Bilgi", "Lütfen bir müşteri seçin."); return
        dlg = CustomerDialog(self, c)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            try:
                self.service.update(dlg.get_customer())
                logger.info("Müşteri güncellendi: %s", c.company_name)
                self._load()
            except Exception as e:
                logger.error("Müşteri güncelleme hatası: %s", e, exc_info=True)

    def _delete(self):
        """Seçili müşteri(leri) siler — Shift/Ctrl ile çoklu seçim desteklenir."""
        selected = self._selected_all()
        if not selected:
            QMessageBox.information(
                self, "Bilgi", "Lütfen silinecek müşteri(leri) seçin."); return

        # Müşterilere ait toplam teklif sayısı — veri bütünlüğü uyarısı
        related_total = 0
        for c in selected:
            try:
                related_total += len(self.offer_svc.get_by_customer(c.id))
            except Exception as e:
                logger.warning("Müşteri teklif sayısı alınamadı: %s", e)

        if len(selected) == 1:
            msg = (f"'{selected[0].company_name}' müşterisini silmek "
                   f"istediğinizden emin misiniz?")
        else:
            names = ", ".join(c.company_name for c in selected[:4])
            if len(selected) > 4:
                names += " ..."
            msg = f"Seçili {len(selected)} müşteri silinsin mi?\n({names})"
        if related_total:
            msg += (f"\n\nDikkat: Bu müşteri(lere) ait toplam {related_total} "
                    "teklif kayıtlı.\n"
                    "Müşteri silinirse teklifler korunur, ancak müşteri bağlantısı kopar.\n"
                    "Mevcut teklif adları ve bilgileri değişmeden kalmaya devam eder.")

        if QMessageBox.question(self, "Silme Onayı", msg,
           QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
           QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        errors = []
        for c in selected:
            try:
                self.service.delete(c.id)
                logger.info("Müşteri silindi: %s", c.company_name)
            except Exception as e:
                logger.error("Müşteri silme hatası: %s", e, exc_info=True)
                errors.append(f"{c.company_name}: {e}")
        if errors:
            QMessageBox.warning(self, "Hata",
                                "Bazı müşteriler silinemedi:\n" + "\n".join(errors))
        self._load(self.search.text())

    def eventFilter(self, obj, event):
        if obj is self.table.viewport():
            t = event.type()
            if t == QEvent.Type.MouseMove:
                idx = self.table.indexAt(event.position().toPoint())
                row = idx.row() if idx.isValid() else -1
                if row != self._delegate._hovered_row:
                    self._delegate.set_hovered_row(row)
                    self.table.viewport().update()
            elif t == QEvent.Type.Leave:
                self._delegate.set_hovered_row(-1)
                self.table.viewport().update()
        return super().eventFilter(obj, event)

    def on_enter(self):
        self._load(self.search.text())
