"""
Excel benzeri yeniden boyutlandırılabilir tablo.
- Stretch + Interactive sütunlar doğru çalışır
- Başlığa çift tıklayınca otomatik sığdırma
- Sağ tık menüsü Türkçe + isteğe bağlı "Düzenle" / "Sil" satır aksiyonları
"""
import logging
from PySide6.QtWidgets import QTableWidget, QMenu, QApplication, QHeaderView
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QAction

logger = logging.getLogger("table")


class ResizableTable(QTableWidget):
    """
    QTableWidget üzeri — Excel benzeri sütun davranışı.

    Satır aksiyonları için callback'ler atanabilir:
        table.on_edit   = lambda: ...
        table.on_delete = lambda: ...
    Bunlar atanınca sağ tık menüsüne otomatik eklenir.
    """

    def __init__(self, rows=0, cols=0, parent=None):
        super().__init__(rows, cols, parent)
        self._stretch_cols: set = set()
        self.on_edit             = None   # callable atanırsa sağ tıkta "Düzenle" çıkar
        self.on_delete           = None   # callable atanırsa sağ tıkta "Sil" çıkar
        self.custom_context_menu = None   # callable(pos) atanırsa kendi menüsünü kullan
        self._setup()

    def _setup(self):
        hh = self.horizontalHeader()
        hh.setSectionsMovable(False)
        # Önce tüm header'ı Interactive yap — sonra bireysel sütunlar override eder
        hh.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        hh.setDefaultSectionSize(100)
        hh.setMinimumSectionSize(40)
        hh.setStretchLastSection(False)
        hh.sectionDoubleClicked.connect(self._auto_fit_column)
        # Tooltip sadece header alanında görünsün
        hh.setToolTip(
            "↔ Kenarı sürükle → genişliği ayarla\n"
            "↔↔ Başlığa çift tıkla → otomatik sığdır\n"
            "Sağ tık → daha fazla seçenek"
        )
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    # ── Sütun modu API ──────────────────────────────────────────────────────

    def set_stretch_column(self, col: int):
        self._stretch_cols.add(col)
        # Stretch yerine Interactive kullan + stretchLastSection mantığını _update_stretch ile sağla
        hh = self.horizontalHeader()
        hh.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
        hh.setMinimumSectionSize(60)

    def set_fixed_column(self, col: int, width: int):
        self.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeMode.Fixed)
        self.setColumnWidth(col, width)

    def set_interactive_column(self, col: int, width: int = 100):
        hh = self.horizontalHeader()
        hh.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
        self.setColumnWidth(col, width)
        # Sürükleme için minimum genişlik garanti et
        if self.columnWidth(col) < 40:
            self.setColumnWidth(col, 40)

    def setup_columns(self, config: list):
        """
        config = [('stretch'|'interactive'|'fixed', width_or_None), ...]
        """
        for col, (mode, width) in enumerate(config):
            if mode == 'stretch':
                self.set_stretch_column(col)
            elif mode == 'fixed':
                self.set_fixed_column(col, width or 80)
            else:
                self.set_interactive_column(col, width or 100)

    # ── Otomatik sığdırma ───────────────────────────────────────────────────

    def _auto_fit_column(self, col: int):
        if col in self._stretch_cols:
            return
        # Interactive moda geç (fixed ise serbest bırak)
        self.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
        self.resizeColumnToContents(col)
        w = self.columnWidth(col)
        self.setColumnWidth(col, max(60, min(w + 24, 500)))
        logger.debug("Sütun %d otomatik sığdırıldı: %dpx", col, self.columnWidth(col))

    def auto_fit_all(self):
        for col in range(self.columnCount()):
            if col not in self._stretch_cols:
                self._auto_fit_column(col)

    # ── Sağ tık menüsü ──────────────────────────────────────────────────────

    def _show_context_menu(self, pos: QPoint):
        # Dışarıdan özel menü tanımlanmışsa onu kullan
        if self.custom_context_menu is not None:
            self.custom_context_menu(pos)
            return
        item      = self.itemAt(pos)
        has_item  = item is not None
        col       = self.columnAt(pos.x())
        menu = QMenu(self)

        # ── Satır aksiyonları (atanmışsa) ──
        if self.on_edit is not None or self.on_delete is not None:
            if self.on_edit is not None:
                act_edit = QAction("Düzenle", self)
                act_edit.setEnabled(has_item)
                act_edit.triggered.connect(self.on_edit)
                menu.addAction(act_edit)

            if self.on_delete is not None:
                act_del = QAction("Sil", self)
                act_del.setEnabled(has_item)
                act_del.triggered.connect(self.on_delete)
                menu.addAction(act_del)

            menu.addSeparator()

        # ── Pano ──
        act_copy = QAction("Kopyala\tCtrl+C", self)
        act_copy.setEnabled(has_item)
        act_copy.triggered.connect(self._copy_selection)
        menu.addAction(act_copy)

        act_all = QAction("Tümünü Seç\tCtrl+A", self)
        act_all.triggered.connect(self.selectAll)
        menu.addAction(act_all)

        menu.addSeparator()

        # ── Sütun işlemleri ──
        act_fit = QAction("Bu Sütunu Otomatik Sığdır", self)
        act_fit.setEnabled(col >= 0 and col not in self._stretch_cols)
        act_fit.triggered.connect(lambda: self._auto_fit_column(col))
        menu.addAction(act_fit)

        act_fit_all = QAction("Tüm Sütunları Sığdır", self)
        act_fit_all.triggered.connect(self.auto_fit_all)
        menu.addAction(act_fit_all)

        menu.exec(self.viewport().mapToGlobal(pos))

    def _copy_selection(self):
        ranges = self.selectedRanges()
        if not ranges:
            return
        r = ranges[0]
        rows = []
        for row in range(r.topRow(), r.bottomRow() + 1):
            cols = []
            for col in range(r.leftColumn(), r.rightColumn() + 1):
                it = self.item(row, col)
                cols.append(it.text() if it else "")
            rows.append("\t".join(cols))
        QApplication.clipboard().setText("\n".join(rows))
        logger.debug("Panoya kopyalandı: %d satır", len(rows))

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_C and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            self._copy_selection()
        else:
            super().keyPressEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._distribute_stretch()

    def showEvent(self, event):
        super().showEvent(event)
        self._distribute_stretch()

    def _distribute_stretch(self):
        """Stretch sütunları mevcut toplam genişliğe göre eşit dağıt."""
        if not self._stretch_cols:
            return
        total = self.viewport().width()
        fixed = sum(
            self.columnWidth(c)
            for c in range(self.columnCount())
            if c not in self._stretch_cols
        )
        remaining = max(60 * len(self._stretch_cols), total - fixed)
        per_col = remaining // len(self._stretch_cols)
        for c in self._stretch_cols:
            self.setColumnWidth(c, max(60, per_col))
