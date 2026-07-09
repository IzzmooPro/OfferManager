"""Tam satır hover/seçim boyaması için paylaşılan delegate."""
from PySide6.QtWidgets import QStyledItemDelegate, QStyle
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor


class RowHoverDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._hovered_row = -1

    def set_hovered_row(self, row: int):
        self._hovered_row = row

    def paint(self, painter, option, index):
        from ui.utils.theme_manager import get_theme
        t = get_theme()

        is_selected = bool(option.state & QStyle.StateFlag.State_Selected)
        is_hovered  = (index.row() == self._hovered_row) and not is_selected

        if is_selected:
            bg = QColor(t["table_row_selected"])
        elif is_hovered:
            bg = QColor(t["table_row_hover"])
        else:
            bg = QColor(t["bg_card"])

        painter.fillRect(option.rect, bg)

        painter.save()
        painter.setPen(QColor(t["grid_color"]))
        painter.drawLine(option.rect.bottomLeft(), option.rect.bottomRight())
        painter.restore()

        text_color = QColor("#ffffff") if is_selected else QColor(t["text_table"])
        text      = index.data(Qt.ItemDataRole.DisplayRole) or ""
        align_raw = index.data(Qt.ItemDataRole.TextAlignmentRole)
        align     = Qt.AlignmentFlag(int(align_raw)) if align_raw else (
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)

        painter.save()
        painter.setFont(option.font)
        painter.setPen(text_color)
        painter.drawText(option.rect.adjusted(6, 0, -6, 0), int(align), text)
        painter.restore()
