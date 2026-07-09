"""Kategori yönetim dialogu — ekleme, düzenleme, silme."""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QListWidget, QListWidgetItem, QMessageBox,
)
from PySide6.QtCore import Qt
from services.category_service import CategoryService
from models.category import Category


class CategoryManagerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Kategori Yönetimi")
        self.setMinimumSize(400, 350)
        self._svc = CategoryService()
        self._build_ui()
        self._load()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(10)

        title = QLabel("Kategoriler")
        title.setStyleSheet("font-size: 11pt; font-weight: 700;")
        layout.addWidget(title)

        add_row = QHBoxLayout()
        add_row.setSpacing(6)
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("Yeni kategori adı...")
        self._name_edit.setMinimumHeight(34)
        self._name_edit.returnPressed.connect(self._add)
        add_row.addWidget(self._name_edit, 1)
        btn_add = QPushButton("Ekle")
        btn_add.setObjectName("primary")
        btn_add.setFixedHeight(34)
        btn_add.clicked.connect(self._add)
        add_row.addWidget(btn_add)
        layout.addLayout(add_row)

        self._list = QListWidget()
        self._list.setMinimumHeight(150)
        self._list.itemDoubleClicked.connect(self._rename)
        layout.addWidget(self._list)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_rename = QPushButton("Yeniden Adlandır")
        btn_rename.setObjectName("secondary")
        btn_rename.clicked.connect(self._rename)
        btn_row.addWidget(btn_rename)
        btn_delete = QPushButton("Sil")
        btn_delete.setObjectName("danger")
        btn_delete.clicked.connect(self._delete)
        btn_row.addWidget(btn_delete)
        btn_row.addStretch()
        btn_close = QPushButton("Kapat")
        btn_close.setObjectName("secondary")
        btn_close.clicked.connect(self.accept)
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)

    def _load(self):
        self._list.clear()
        for cat in self._svc.get_all():
            item = QListWidgetItem(cat.name)
            item.setData(Qt.ItemDataRole.UserRole, cat.id)
            self._list.addItem(item)

    def _add(self):
        name = self._name_edit.text().strip()
        if not name:
            return
        try:
            self._svc.add(Category(name=name))
            self._name_edit.clear()
            self._load()
        except Exception as e:
            QMessageBox.warning(self, "Hata", f"Kategori eklenemedi:\n{e}")

    def _rename(self, _item=None):
        item = self._list.currentItem()
        if not item:
            QMessageBox.information(self, "Bilgi", "Lütfen bir kategori seçin.")
            return
        from PySide6.QtWidgets import QInputDialog
        new_name, ok = QInputDialog.getText(
            self, "Yeniden Adlandır", "Yeni ad:", text=item.text())
        if ok and new_name.strip():
            try:
                cat_id = item.data(Qt.ItemDataRole.UserRole)
                cat = self._svc.get_by_id(cat_id)
                cat.name = new_name.strip()
                self._svc.update(cat)
                self._load()
            except Exception as e:
                QMessageBox.warning(self, "Hata", f"Ad değiştirilemedi:\n{e}")

    def _delete(self):
        item = self._list.currentItem()
        if not item:
            QMessageBox.information(self, "Bilgi", "Lütfen bir kategori seçin.")
            return
        cat_id = item.data(Qt.ItemDataRole.UserRole)
        ans = QMessageBox.question(
            self, "Kategori Sil",
            f"'{item.text()}' kategorisi silinsin mi?\n\n"
            "Bu kategorideki ürünler 'Kategorisiz' olarak kalacak.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if ans != QMessageBox.StandardButton.Yes:
            return
        try:
            self._svc.delete(cat_id)
            self._load()
        except Exception as e:
            QMessageBox.warning(self, "Hata", f"Kategori silinemedi:\n{e}")
