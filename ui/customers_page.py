"""Müşteri yönetim sayfası."""
import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidgetItem, QLineEdit, QDialog,
    QFormLayout, QMessageBox, QFrame
)
from PySide6.QtCore import Qt
from services.customer_service import CustomerService
from services.offer_service import OfferService
from models.customer import Customer
from ui._resizable_table import ResizableTable

logger = logging.getLogger("customers")


class CustomerDialog(QDialog):
    def __init__(self, parent=None, customer=None):
        super().__init__(parent)
        self.setWindowTitle("Müşteri Ekle" if not customer else "Müşteri Düzenle")
        self.setMinimumWidth(460)
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

        for lbl, w in [("Firma Adı *:", self.company), ("İlgili Kişi:", self.contact),
                        ("Adres:", self.address), ("Telefon:", self.phone), ("E-posta:", self.email)]:
            form.addRow(lbl, w)
        layout.addLayout(form)

        btns = QHBoxLayout()
        ok = QPushButton("Kaydet");  ok.setObjectName("primary");   ok.clicked.connect(self._save)
        no = QPushButton("İptal");   no.setObjectName("secondary"); no.clicked.connect(self.reject)
        btns.addWidget(no); btns.addWidget(ok)
        layout.addLayout(btns)

    def _fill(self, c):
        self.company.setText(c.company_name)
        self.contact.setText(c.contact_person)
        self.address.setText(c.address)
        self.phone.setText(c.phone)
        self.email.setText(c.email)

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
        layout.setContentsMargins(16, 20, 16, 16)
        layout.setSpacing(16)

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
        for lbl, slot in [("Düzenle", self._edit), ("Sil", self._delete)]:
            b = QPushButton(lbl); b.setObjectName("action_btn")
            b.setMinimumHeight(32); b.clicked.connect(slot)
            t.addWidget(b)
        layout.addWidget(toolbar)

        # ResizableTable — Excel benzeri + Türkçe sağ tık
        self.table = ResizableTable()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Firma Adı","İlgili Kişi","Adres","Telefon","E-posta"])
        self.table.setup_columns([
            ('stretch',     None),  # Firma Adı
            ('interactive', 140),   # İlgili Kişi
            ('stretch',     None),  # Adres
            ('interactive', 120),   # Telefon
            ('interactive', 180),   # E-posta
        ])
        self.table.setEditTriggers(self.table.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(self.table.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.doubleClicked.connect(self._edit)
        self.table.on_edit   = self._edit
        self.table.on_delete = self._delete
        layout.addWidget(self.table)
        self._load()

    def _load(self, keyword=""):
        logger.debug("Müşteriler yükleniyor, anahtar='%s'", keyword)
        try:
            self._customers = self.service.search(keyword) if keyword else self.service.get_all()
            self.table.setRowCount(len(self._customers))
            for row, c in enumerate(self._customers):
                self.table.setItem(row, 0, QTableWidgetItem(c.company_name))
                self.table.setItem(row, 1, QTableWidgetItem(c.contact_person))
                self.table.setItem(row, 2, QTableWidgetItem(c.address))
                self.table.setItem(row, 3, QTableWidgetItem(c.phone))
                self.table.setItem(row, 4, QTableWidgetItem(c.email))
        except Exception as e:
            logger.error("Müşteri yükleme hatası: %s", e, exc_info=True)

    def _selected(self):
        row = self.table.currentRow()
        return self._customers[row] if 0 <= row < len(self._customers) else None

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
        c = self._selected()
        if not c:
            QMessageBox.information(self, "Bilgi", "Lütfen bir müşteri seçin."); return

        # Müşteriye ait teklif sayısını kontrol et — veri bütünlüğü uyarısı
        try:
            related = self.offer_svc.get_by_customer(c.id)
        except Exception:
            related = []

        msg = f"'{c.company_name}' müşterisini silmek istediğinizden emin misiniz?"
        if related:
            msg += (f"\n\n⚠️  Bu müşteriye ait {len(related)} teklif kayıtlı.\n"
                    "Müşteri silinirse teklifler korunur, ancak müşteri bağlantısı kopar.\n"
                    "Mevcut teklif adları ve bilgileri değişmeden kalmaya devam eder.")

        if QMessageBox.question(self, "Silme Onayı", msg,
           QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            try:
                self.service.delete(c.id)
                logger.info("Müşteri silindi: %s", c.company_name)
                self._load()
            except Exception as e:
                logger.error("Müşteri silme hatası: %s", e, exc_info=True)

    def on_enter(self):
        self._load(self.search.text())
