"""Ürün yönetim sayfası."""
import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidgetItem, QLineEdit, QDialog,
    QFormLayout, QComboBox, QDoubleSpinBox, QMessageBox,
    QTextEdit, QFrame, QHeaderView
)
from PySide6.QtCore import Qt, QTimer, QEvent
from services.product_service import ProductService
from models.product import Product
from ui.widgets._resizable_table import ResizableTable
from ui.widgets._row_hover_delegate import RowHoverDelegate
from ui.widgets._plus_button import PlusButton
from core.constants import UNIT_LIST, CURRENCY_LIST
from core.formatting import fmt_number

logger = logging.getLogger("products")


class ProductDialog(QDialog):
    def __init__(self, parent=None, product=None):
        super().__init__(parent)
        self.setWindowTitle("Ürün Ekle" if not product else "Ürün Düzenle")
        self.setMinimumWidth(480)
        self.setMaximumHeight(520)
        self.product  = product          # None = yeni ürün
        self._svc     = ProductService()
        self._build_ui()
        if product:
            self._fill(product)

    # ── UI ───────────────────────────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(22, 20, 22, 20)

        title = QLabel(self.windowTitle())
        title.setStyleSheet("font-size:11pt;font-weight:700;")
        layout.addWidget(title)

        form = QFormLayout()
        form.setSpacing(10)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        # ── Ürün Kodu ──
        self.code = QLineEdit(); self.code.setMinimumHeight(34)
        self.code.setPlaceholderText("")

        # Duplicate uyarısı — kod alanının altında
        self.code_warn = QLabel("")
        self.code_warn.setStyleSheet(
            "color: #e94560; font-size: 8pt; padding: 2px 0; background: transparent;")
        self.code_warn.setVisible(False)

        code_col = QVBoxLayout(); code_col.setSpacing(2)
        code_col.setContentsMargins(0, 0, 0, 0)
        code_col.addWidget(self.code)
        code_col.addWidget(self.code_warn)

        code_wrap = QWidget(); code_wrap.setLayout(code_col)
        form.addRow("Ürün Kodu *:", code_wrap)

        # Gerçek zamanlı duplicate kontrolü — 400ms debounce
        self._check_timer = QTimer(self)
        self._check_timer.setSingleShot(True)
        self._check_timer.timeout.connect(self._check_duplicate)
        self.code.textChanged.connect(lambda: self._check_timer.start(400))

        # ── Diğer alanlar ──
        self.name = QLineEdit(); self.name.setMinimumHeight(34)
        self.desc = QTextEdit(); self.desc.setMaximumHeight(70)
        form.addRow("Ürün Adı *:", self.name)
        form.addRow("Açıklama:", self.desc)

        # ── Fiyat ──
        self.price = QDoubleSpinBox()
        self.price.setMaximum(9_999_999)
        self.price.setDecimals(2)
        self.price.setMinimumHeight(36)
        self.price.setGroupSeparatorShown(True)
        self.price.setStepType(QDoubleSpinBox.StepType.AdaptiveDecimalStepType)
        form.addRow("Fiyat:", self.price)

        # ── Alış Fiyatı (Maliyet) — yalnızca dahili kâr hesabı için ──
        self.cost_price = QDoubleSpinBox()
        self.cost_price.setMaximum(9_999_999)
        self.cost_price.setDecimals(2)
        self.cost_price.setMinimumHeight(36)
        self.cost_price.setGroupSeparatorShown(True)
        self.cost_price.setStepType(QDoubleSpinBox.StepType.AdaptiveDecimalStepType)

        cost_hint = QLabel(
            "Bu bilgi tekliflerde ve PDF'te görünmez, yalnızca sizin "
            "kâr hesabınız içindir.")
        cost_hint.setObjectName("hint_label")
        cost_hint.setWordWrap(True)

        cost_col = QVBoxLayout(); cost_col.setSpacing(2)
        cost_col.setContentsMargins(0, 0, 0, 0)
        cost_col.addWidget(self.cost_price)
        cost_col.addWidget(cost_hint)
        cost_wrap = QWidget(); cost_wrap.setLayout(cost_col)
        form.addRow("Alış Fiyatı:", cost_wrap)

        # ── Para Birimi ──
        self.currency = QComboBox()
        self.currency.addItems(CURRENCY_LIST)
        self.currency.setMinimumHeight(34)
        form.addRow("Para Birimi:", self.currency)

        # ── Stok — tam sayıysa ondalık gösterme ──
        self.stock = QDoubleSpinBox()
        self.stock.setMaximum(999_999)
        self.stock.setMinimumHeight(36)
        self.stock.setDecimals(0)          # ← ondalık basamak kaldırıldı
        self.stock.setSingleStep(1)
        self.stock.setStepType(QDoubleSpinBox.StepType.DefaultStepType)
        form.addRow("Stok:", self.stock)

        # ── Birim ──
        self.unit = QComboBox()
        self.unit.addItems(UNIT_LIST)
        self.unit.setEditable(True)
        self.unit.setMinimumHeight(34)
        self.unit.setMinimumWidth(120)
        form.addRow("Birim:", self.unit)

        # ── Kategori ──
        cat_row = QHBoxLayout()
        cat_row.setContentsMargins(0, 0, 0, 0)
        cat_row.setSpacing(6)
        self.category_combo = QComboBox()
        self.category_combo.setMinimumHeight(34)
        self._load_categories()
        cat_row.addWidget(self.category_combo, 1)
        cat_manage_btn = PlusButton()
        cat_manage_btn.setObjectName("icon_btn")
        cat_manage_btn.setFixedSize(34, 34)
        cat_manage_btn.setToolTip("Kategori ekle / düzenle / sil")
        cat_manage_btn.clicked.connect(self._open_category_manager)
        cat_row.addWidget(cat_manage_btn)
        cat_wrap = QWidget()
        cat_wrap.setLayout(cat_row)
        form.addRow("Kategori:", cat_wrap)

        layout.addLayout(form)
        layout.addStretch()

        btns = QHBoxLayout()
        ok = QPushButton("Kaydet");  ok.setObjectName("primary");   ok.clicked.connect(self._save)
        no = QPushButton("İptal");   no.setObjectName("secondary"); no.clicked.connect(self.reject)
        btns.addStretch(); btns.addWidget(no); btns.addWidget(ok)
        layout.addLayout(btns)

    # ── Doldur ───────────────────────────────────────────────────────────────

    def _load_categories(self):
        from services.category_service import CategoryService
        prev = self.category_combo.currentData()
        self.category_combo.blockSignals(True)
        self.category_combo.clear()
        self.category_combo.addItem("— Kategorisiz —", None)
        try:
            for cat in CategoryService().get_all():
                self.category_combo.addItem(cat.name, cat.id)
        except (ImportError, Exception) as e:
            logger.debug("Kategori yükleme atlandı: %s", e)
        if prev is not None:
            for i in range(self.category_combo.count()):
                if self.category_combo.itemData(i) == prev:
                    self.category_combo.setCurrentIndex(i)
                    break
        self.category_combo.blockSignals(False)

    def _open_category_manager(self):
        from ui.dialogs.category_dialog import CategoryManagerDialog
        dlg = CategoryManagerDialog(self)
        dlg.exec()
        self._load_categories()

    def _fill(self, p):
        self.code.setText(p.product_code)
        self.name.setText(p.product_name)
        # Uzun ürün adlarında imleci başa al — sonu değil başı görünsün.
        self.code.setCursorPosition(0)
        self.name.setCursorPosition(0)
        self.desc.setPlainText(p.description or "")
        self.price.setValue(p.price)
        self.cost_price.setValue(p.cost_price or 0.0)
        idx = self.currency.findText(p.currency)
        if idx >= 0: self.currency.setCurrentIndex(idx)
        self.stock.setValue(int(p.stock) if p.stock == int(p.stock) else p.stock)
        u = self.unit.findText(p.unit)
        if u >= 0: self.unit.setCurrentIndex(u)
        else: self.unit.setCurrentText(p.unit)
        if p.category_id is not None:
            for i in range(self.category_combo.count()):
                if self.category_combo.itemData(i) == p.category_id:
                    self.category_combo.setCurrentIndex(i)
                    break

    # ── Duplicate kontrolü ───────────────────────────────────────────────────

    def _check_duplicate(self):
        code = self.code.text().strip().upper()
        if not code:
            self._hide_warn(); return

        # Düzenleme modunda kendi kodunu kontrol etme
        if self.product and self.product.product_code.upper() == code:
            self._hide_warn(); return

        try:
            existing = self._svc.get_by_code(code)
            if existing:
                self.code_warn.setText(
                    f"'{existing.product_code}' kodu zaten kayıtlı: {existing.product_name}")
                self.code_warn.setVisible(True)
                # Kod alanını kırmızı border ile işaretle
                self.code.setStyleSheet(
                    "QLineEdit { border: 1.5px solid #e94560; border-radius: 6px; "
                    "padding: 8px 12px; }")
            else:
                self._hide_warn()
        except (Exception) as e:
            logger.debug("Ürün kodu kontrol hatası: %s", e)
            self._hide_warn()

    def _hide_warn(self):
        self.code_warn.setVisible(False)
        self.code.setStyleSheet("")  # Temaya bırak

    # ── Kaydet ───────────────────────────────────────────────────────────────

    def _save(self):
        if not self.code.text().strip() or not self.name.text().strip():
            QMessageBox.warning(self, "Hata", "Ürün kodu ve adı zorunludur."); return

        # Duplicate son kontrol — hız farkı olabilir
        code = self.code.text().strip().upper()
        if not (self.product and self.product.product_code.upper() == code):
            try:
                existing = self._svc.get_by_code(code)
                if existing:
                    ans = QMessageBox.warning(
                        self, "Aynı Kod Mevcut",
                        f"'{existing.product_code}' kodu zaten kayıtlı:\n"
                        f"Ürün: {existing.product_name}\n\n"
                        f"Yine de kaydetmek istiyor musunuz?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No)
                    if ans != QMessageBox.StandardButton.Yes:
                        return
            except Exception as e:
                logger.debug("Duplicate kontrol hatası: %s", e)

        self.accept()

    def get_product(self) -> Product:
        p = self.product or Product()
        p.product_code = self.code.text().strip()
        p.product_name = self.name.text().strip()
        p.description  = self.desc.toPlainText().strip()
        p.price        = self.price.value()
        p.cost_price   = self.cost_price.value()
        p.currency     = self.currency.currentText()
        p.stock        = self.stock.value()
        p.unit         = self.unit.currentText()
        p.category_id  = self.category_combo.currentData()
        return p


# ── Sayfa ─────────────────────────────────────────────────────────────────────

class ProductsPage(QWidget):
    def __init__(self):
        super().__init__()
        self.service   = ProductService()
        self._products = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 12)
        layout.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel("Ürün Yönetimi")
        title.setStyleSheet("font-size:14pt;font-weight:700;")
        header.addWidget(title); header.addStretch()
        add_btn = QPushButton("+ Yeni Ürün")
        add_btn.setObjectName("primary"); add_btn.clicked.connect(self._add)
        header.addWidget(add_btn)
        layout.addLayout(header)

        toolbar = QFrame(); toolbar.setObjectName("toolbar")
        t = QHBoxLayout(toolbar); t.setContentsMargins(8, 4, 8, 4)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Ürün kodu veya adıyla ara...")
        self.search.textChanged.connect(lambda _: self._load_filtered())
        t.addWidget(self.search)
        # Kategori filtresi
        self.cat_filter = QComboBox()
        self.cat_filter.setMinimumHeight(32)
        self.cat_filter.setMinimumWidth(150)
        self._load_category_filter()
        self.cat_filter.currentIndexChanged.connect(lambda _: self._load_filtered())
        t.addWidget(self.cat_filter)
        for lbl, slot, obj in [("Düzenle", self._edit, "tab_btn_edit"),
                               ("Sil", self._delete, "tab_btn_delete")]:
            b = QPushButton(lbl); b.setObjectName(obj)
            b.setMinimumHeight(36); b.setMinimumWidth(82)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(slot)
            t.addWidget(b)
        layout.addWidget(toolbar)

        self.table = ResizableTable()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(
            ["Ürün Kodu","Ürün Adı","Fiyat","Para Birimi","Stok","Birim","Açıklama"])
        self.table.setup_columns([
            ('interactive', 120),
            ('stretch',     None),
            ('interactive', 130),
            ('interactive', 105),
            ('interactive',  75),
            ('interactive',  85),
            ('stretch',     None),
        ])
        self.table.setEditTriggers(self.table.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(self.table.SelectionBehavior.SelectRows)
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

    def _load_category_filter(self):
        """Kategori filtre combo'sunu doldurur."""
        from services.category_service import CategoryService
        self.cat_filter.blockSignals(True)
        self.cat_filter.clear()
        self.cat_filter.addItem("Tüm Kategoriler", -1)
        self.cat_filter.addItem("Kategorisiz", None)
        try:
            for cat in CategoryService().get_all():
                self.cat_filter.addItem(cat.name, cat.id)
        except Exception as e:
            logger.debug("Kategori filtre yükleme atlandı: %s", e)
        self.cat_filter.blockSignals(False)

    def _load_filtered(self):
        """Arama kutusu ve kategori filtresini birlikte uygular."""
        keyword = self.search.text().strip()
        cat_id = self.cat_filter.currentData() if hasattr(self, 'cat_filter') else -1
        self._load(keyword, cat_id)

    def _load(self, keyword="", category_id=-1):
        logger.debug("Ürünler yükleniyor, anahtar='%s', kategori=%s", keyword, category_id)
        try:
            if keyword:
                self._products = self.service.search(keyword, category_id)
            else:
                self._products = self.service.get_all(category_id)
            self.table.setRowCount(len(self._products))
            for row, p in enumerate(self._products):
                self.table.setItem(row, 0, QTableWidgetItem(p.product_code))
                self.table.setItem(row, 1, QTableWidgetItem(p.product_name))
                pi = QTableWidgetItem(fmt_number(p.price))
                pi.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(row, 2, pi)
                self.table.setItem(row, 3, QTableWidgetItem(p.currency))
                # Stok: tam sayıysa ondalık gösterme
                stock_val = int(p.stock) if p.stock == int(p.stock) else p.stock
                si = QTableWidgetItem(str(stock_val))
                si.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(row, 4, si)
                self.table.setItem(row, 5, QTableWidgetItem(p.unit))
                self.table.setItem(row, 6, QTableWidgetItem(p.description or ""))
            self.table.resizeColumnToContents(2)
            self.table.resizeColumnToContents(0)
        except Exception as e:
            logger.error("Ürün yükleme hatası: %s", e, exc_info=True)

    def _selected(self):
        row = self.table.currentRow()
        return self._products[row] if 0 <= row < len(self._products) else None

    def _add(self):
        dlg = ProductDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            try:
                self.service.add(dlg.get_product())
                self._load()
            except Exception as e:
                QMessageBox.warning(self, "Hata", f"Ürün eklenemedi:\n{e}")

    def _edit(self):
        p = self._selected()
        if not p:
            QMessageBox.information(self, "Bilgi", "Lütfen bir ürün seçin."); return
        dlg = ProductDialog(self, p)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            try:
                self.service.update(dlg.get_product())
                self._load()
            except Exception as e:
                QMessageBox.warning(self, "Hata", f"Ürün güncellenemedi:\n{e}")

    def _delete(self):
        p = self._selected()
        if not p:
            QMessageBox.information(self, "Bilgi", "Lütfen bir ürün seçin."); return
        if QMessageBox.question(self, "Onay", f"'{p.product_name}' silinsin mi?",
           QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) \
           == QMessageBox.StandardButton.Yes:
            try:
                self.service.delete(p.id)
                self._load()
            except Exception as e:
                QMessageBox.warning(self, "Hata", f"Ürün silinemedi:\n{e}")

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
        self._load_category_filter()
        self._load_filtered()
