"""Hover'da yukarı kayan animasyonlu kart bileşeni."""
from PySide6.QtWidgets import QFrame, QGraphicsOpacityEffect
from PySide6.QtCore import QPropertyAnimation, QEasingCurve, Qt, QObject, Property


class _MarginAnimHelper(QObject):
    """Kart margin animasyonu için yardımcı — layout bozmadan yukarı kayma."""
    def __init__(self, card):
        super().__init__(card)
        self._card = card
        self._offset = 0

    def _get_offset(self):
        return self._offset

    def _set_offset(self, val):
        self._offset = val
        self._card.setContentsMargins(
            self._card._base_margins[0],
            self._card._base_margins[1] - val,
            self._card._base_margins[2],
            self._card._base_margins[3] + val,
        )

    offset = Property(int, _get_offset, _set_offset)


class AnimatedCard(QFrame):
    """
    QFrame#card — hover'da 3px yukarı kayar (layout bozmaz).
    ContentsMargins animasyonu ile toplam yükseklik sabit kalır.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self._base_margins = (0, 0, 0, 0)
        self._helper = _MarginAnimHelper(self)
        self._anim = QPropertyAnimation(self._helper, b"offset")
        self._anim.setDuration(150)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def showEvent(self, event):
        super().showEvent(event)
        m = self.contentsMargins()
        self._base_margins = (m.left(), m.top(), m.right(), m.bottom())

    def enterEvent(self, event):
        self._anim.stop()
        self._anim.setStartValue(self._helper._offset)
        self._anim.setEndValue(3)
        self._anim.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._anim.stop()
        self._anim.setStartValue(self._helper._offset)
        self._anim.setEndValue(0)
        self._anim.start()
        super().leaveEvent(event)
