"""
Paylaşılan UI yardımcıları — section card widget.
"""
from PySide6.QtWidgets import (QFrame, QVBoxLayout, QHBoxLayout,
                                QLabel, QGridLayout)
from PySide6.QtCore import Qt


def make_section_card(title: str, use_grid: bool = True):
    """
    Üstte kalın başlık + 2px lacivert ayırıcı çizgi + içerik alanı.

    Döner: (outer_frame, content_layout)
      - content_layout: QGridLayout (use_grid=True) veya QVBoxLayout
    """
    outer = QFrame()
    outer.setObjectName("section_card")

    vbox = QVBoxLayout(outer)
    vbox.setContentsMargins(0, 0, 0, 0)
    vbox.setSpacing(0)

    # ── Başlık çubuğu ────────────────────────────────────────────────────
    hdr = QFrame()
    hdr.setFixedHeight(44)
    hdr.setStyleSheet("background:transparent;")
    hl = QHBoxLayout(hdr)
    hl.setContentsMargins(16, 0, 16, 0)
    lbl = QLabel(title)
    lbl.setObjectName("section_card_title")
    lbl.setStyleSheet(
        "font-size:10pt;font-weight:700;background:transparent;"
    )
    hl.addWidget(lbl)
    hl.addStretch()
    vbox.addWidget(hdr)

    # ── Ayırıcı çizgi: 2 px lacivert ─────────────────────────────────────
    sep = QFrame()
    sep.setObjectName("section_divider")
    sep.setFrameShape(QFrame.Shape.HLine)
    sep.setFixedHeight(2)
    vbox.addWidget(sep)

    # ── İçerik alanı ─────────────────────────────────────────────────────
    body = QFrame()
    body.setStyleSheet("background:transparent;")
    if use_grid:
        lay = QGridLayout(body)
        lay.setContentsMargins(16, 14, 16, 16)
        lay.setSpacing(10)
    else:
        lay = QVBoxLayout(body)
        lay.setContentsMargins(16, 14, 16, 16)
        lay.setSpacing(10)
    vbox.addWidget(body)

    return outer, lay
