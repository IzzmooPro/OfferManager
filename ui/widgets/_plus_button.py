"""
Paylaşılan UI yardımcısı — kendi kendini merkezleyen "+" ikon butonu.

QSS padding ile elle "göz kararı" merkezleme YAPMAZ (platforma/yazı
tipi motoruna göre değişip kırılgan olur) — glifin gerçek sınır
kutusunu çalışma anında ölçüp tam merkeze çizer. Hangi platformda/
yazı tipinde çalışırsa çalışsın doğru sonuç verir.
"""
from PySide6.QtWidgets import QPushButton
from PySide6.QtGui import QPainter, QFont, QColor


class PlusButton(QPushButton):
    """Artı ikonunu QPainter ile tam merkeze çizen özel buton."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setText("")

    def paintEvent(self, event):
        super().paintEvent(event)          # arka plan + border (tema CSS'i)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        from ui.utils.theme_manager import get_theme
        p.setPen(QColor(get_theme()["text_primary"]))
        f = QFont()
        f.setPointSize(15)
        f.setWeight(QFont.Weight.Light)
        p.setFont(f)
        fm = p.fontMetrics()
        br = fm.boundingRect("+")
        x = (self.width()  - br.width())  // 2 - br.x()
        y = (self.height() - br.height()) // 2 - br.y()
        p.drawText(x, y, "+")
        p.end()
