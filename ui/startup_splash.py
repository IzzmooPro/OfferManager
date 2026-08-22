"""Uygulama açılışında kullanılan gerçek splash widget'ı."""

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import (
    QColor, QFont, QImage, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap,
)
from PySide6.QtWidgets import QApplication, QWidget

from core.app_paths import ASSET_ROOT


class StartupSplash(QWidget):
    WIDTH, HEIGHT = 520, 280

    def __init__(self):
        super().__init__()
        self.setFixedSize(self.WIDTH, self.HEIGHT)
        self.setWindowFlags(Qt.WindowType.SplashScreen | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._progress = 0.0
        self._message = "Başlatılıyor…"
        self._icon = None
        icon_path = ASSET_ROOT / "assets" / "ico.png"
        if icon_path.exists():
            image = QImage(str(icon_path)).convertToFormat(QImage.Format.Format_ARGB32)
            if not image.isNull():
                image = image.scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio,
                                     Qt.TransformationMode.SmoothTransformation)
                for y in range(image.height()):
                    scanline = image.scanLine(y)
                    for x in range(image.width()):
                        offset = x * 4
                        blue, green, red, alpha = (scanline[offset], scanline[offset + 1],
                                                   scanline[offset + 2], scanline[offset + 3])
                        luma = red * 0.299 + green * 0.587 + blue * 0.114
                        if luma > 180:
                            scanline[offset + 3] = 0
                        elif luma > 120:
                            scanline[offset + 3] = int(alpha * (1.0 - (luma - 120) / 60.0))
                self._icon = QPixmap.fromImage(image)

    def set_progress(self, value: float, message: str):
        self._progress = max(0.0, min(1.0, value))
        self._message = message
        self.repaint()
        QApplication.processEvents()

    def paintEvent(self, _event):
        width, height = self.WIDTH, self.HEIGHT
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        gradient = QLinearGradient(0, 0, width, height)
        gradient.setColorAt(0.0, QColor("#0a1628"))
        gradient.setColorAt(1.0, QColor("#162040"))
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, width, height), 16, 16)
        painter.fillPath(path, gradient)
        accent = QColor("#3a7bd5")
        painter.setPen(QPen(accent.lighter(130), 1))
        painter.drawRoundedRect(QRectF(1, 1, width - 2, height - 2), 15, 15)
        if self._icon:
            painter.drawPixmap((width - self._icon.width()) // 2, 40, self._icon)
        painter.setPen(QColor("#e8eaf6"))
        painter.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        painter.drawText(QRectF(0, 115, width, 36), Qt.AlignmentFlag.AlignCenter,
                         "Teklif Yönetim Sistemi")
        from core.constants import APP_VERSION
        painter.setPen(QColor("#6a7a9a"))
        painter.setFont(QFont("Segoe UI", 9))
        painter.drawText(QRectF(0, 150, width, 20), Qt.AlignmentFlag.AlignCenter,
                         f"Sürüm {APP_VERSION}")
        bar_y, bar_height, margin = height - 65, 8, 50
        bar_width = width - 2 * margin
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#1a2744"))
        painter.drawRoundedRect(QRectF(margin, bar_y, bar_width, bar_height), 4, 4)
        painter.setBrush(accent)
        painter.drawRoundedRect(
            QRectF(margin, bar_y, bar_width * self._progress, bar_height), 4, 4)
        painter.setPen(QColor("#8a9abb"))
        painter.setFont(QFont("Segoe UI", 9))
        painter.drawText(QRectF(0, height - 49, width, 22), Qt.AlignmentFlag.AlignCenter,
                         self._message)
        painter.end()
