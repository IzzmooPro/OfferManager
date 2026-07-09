"""Tema yöneticisi — açık ve koyu tema renkleri + stylesheet üretimi."""

LIGHT = {
    "name":              "light",
    "bg_main":           "#f0f2f5",
    "bg_card":           "#ffffff",
    # Açık temada sidebar tamamen açık
    "bg_sidebar":        "#ffffff",
    "bg_sidebar_header": "#f0f2f5",
    "bg_sidebar_hover":  "#e8eef8",
    "bg_sidebar_active": "#ddeeff",
    "bg_table_header":   "#e8eef8",
    "bg_table_alt":      "#f5f7fa",
    "bg_input":          "#ffffff",
    "bg_toolbar":        "#f0f2f5",
    "bg_dialog":         "#ffffff",
    "grid_color":        "#eaecef",
    "text_primary":      "#1a1a2e",
    "text_secondary":    "#555555",
    "text_muted":        "#888888",
    "text_sidebar":      "#334466",
    "text_sidebar_active":"#0f3460",
    "text_input":        "#1a1a2e",
    "text_table":        "#1a1a2e",
    "text_card_value":   "#1a1a2e",
    "border":            "#e0e3e8",
    "border_input":      "#d0d4da",
    "header_divider":    "#9ab0cc",
    "accent_blue":       "#0f3460",
    "accent_blue_hover": "#16213e",
    "accent_red":        "#e94560",
    "accent_red_hover":  "#c73652",
    "accent_green":      "#16a085",
    "accent_green_hover":"#1abc9c",
    "accent_indicator":  "#0f3460",
    "text_total":        "#ffffff",
    # SpinBox up/down buton renkleri
    "spin_btn_bg":       "#e8ecf0",
    "spin_btn_hover":    "#d0d6de",
    "spin_btn_fg":       "#333333",
    # Tablo header yazı rengi
    "text_table_header": "#1a1a2e",
    # QTableView satır hover / seçim renkleri
    "table_row_hover":    "#dbeafe",   # soluk gök mavisi — göz yormaz
    "table_row_selected": "#1d6fa4",   # çelik mavisi — okunabilir beyaz metin ile
}

DARK = {
    "name":              "dark",
    "bg_main":           "#12131a",
    "bg_card":           "#1e2130",
    "bg_sidebar":        "#0d0e17",
    "bg_sidebar_header": "#0a0b12",
    "bg_sidebar_hover":  "#1a1a2e",
    "bg_sidebar_active": "#0f3460",
    "bg_table_header":   "#0f3460",
    "bg_table_alt":      "#242840",
    "bg_input":          "#252840",
    "bg_toolbar":        "#1a1d2e",
    "bg_dialog":         "#1e2130",
    "grid_color":        "#2a3050",
    "text_primary":      "#e8eaf6",
    "text_secondary":    "#b0b8d0",
    "text_muted":        "#6a7a9a",
    "text_sidebar":      "#8899bb",
    "text_sidebar_active":"#ffffff",
    "text_input":        "#e8eaf6",
    "text_table":        "#e8eaf6",
    "text_card_value":   "#e8eaf6",
    "border":            "#2a3050",
    "border_input":      "#3a4060",
    "header_divider":    "#5a8fc8",
    "accent_blue":       "#3a7bd5",
    "accent_blue_hover": "#2e6bc4",
    "accent_red":        "#e94560",
    "accent_red_hover":  "#c73652",
    "accent_green":      "#16a085",
    "accent_green_hover":"#1abc9c",
    "accent_indicator":  "#e94560",
    "text_total":        "#ffffff",
    "spin_btn_bg":       "#2e3350",
    "spin_btn_hover":    "#3a4060",
    "spin_btn_fg":       "#e8eaf6",
    # Tablo header yazı rengi
    "text_table_header": "#ffffff",
    # QTableView satır hover / seçim renkleri
    "table_row_hover":    "#1e3a6e",   # koyu çelik mavisi — gözü yormaz
    "table_row_selected": "#1d6fa4",   # aynı çelik mavisi — tutarlı görünüm
}

def _theme_file():
    from core.app_paths import DATA_DIR
    return DATA_DIR / "theme.txt"


def _detect_system_theme() -> dict:
    """Windows koyu tema aktifse DARK, değilse LIGHT döner."""
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
        val, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        winreg.CloseKey(key)
        return DARK if val == 0 else LIGHT
    except (ImportError, OSError, FileNotFoundError):
        return LIGHT


def _load_saved_mode() -> str:
    """Kayıtlı tema modunu oku: 'light', 'dark' veya 'system'."""
    try:
        mode = _theme_file().read_text(encoding="utf-8").strip()
        if mode in ("light", "dark", "system"):
            return mode
    except OSError:
        pass
    return "system"


def _resolve_theme(mode: str) -> dict:
    if mode == "dark":
        return DARK
    if mode == "light":
        return LIGHT
    return _detect_system_theme()


_current_mode = _load_saved_mode()
_current = _resolve_theme(_current_mode)


def get_theme() -> dict:
    return _current


def get_theme_mode() -> str:
    return _current_mode


def set_theme_mode(mode: str):
    global _current, _current_mode
    _current_mode = mode
    _current = _resolve_theme(mode)
    try:
        _theme_file().write_text(mode, encoding="utf-8")
    except OSError:
        pass


def toggle_theme():
    set_theme_mode("dark" if _current["name"] == "light" else "light")


def _get_arrow_path(color: str, direction: str) -> str:
    from PySide6.QtGui import QPixmap, QPainter, QColor, QPen, QPainterPath
    from PySide6.QtCore import Qt, QPointF
    from core.app_paths import DATA_DIR

    color_hex = color.replace('#', '')
    filename = f"chevron_{direction}_{color_hex}.png"
    filepath = DATA_DIR / filename

    if not filepath.exists():
        pix = QPixmap(16, 16)
        pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(color))
        pen.setWidthF(1.6)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        path = QPainterPath()
        if direction == "down":
            path.moveTo(QPointF(4, 6))
            path.lineTo(QPointF(8, 10.5))
            path.lineTo(QPointF(12, 6))
        else:
            path.moveTo(QPointF(4, 10.5))
            path.lineTo(QPointF(8, 6))
            path.lineTo(QPointF(12, 10.5))
        p.drawPath(path)
        p.end()
        pix.save(str(filepath), "PNG")

    path_str = filepath.as_posix()
    return f"url('{path_str}')"

def _get_checkmark_path() -> str:
    from PySide6.QtGui import QPixmap, QPainter, QColor, QPen, QPainterPath
    from PySide6.QtCore import Qt, QPointF
    from core.app_paths import DATA_DIR

    filepath = DATA_DIR / "checkmark_white.png"
    if not filepath.exists():
        pix = QPixmap(14, 14)
        pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor("#ffffff"))
        pen.setWidthF(2.0)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        path = QPainterPath()
        path.moveTo(QPointF(2.5, 7))
        path.lineTo(QPointF(5.5, 10.5))
        path.lineTo(QPointF(11.5, 3.5))
        p.drawPath(path)
        p.end()
        pix.save(str(filepath), "PNG")
    return f"url('{filepath.as_posix()}')"


def build_stylesheet(t: dict) -> str:
    return f"""
/* ══════════════════════════════════════════════════════
   ANA PENCERE / GENEL
══════════════════════════════════════════════════════ */
QMainWindow, QWidget {{
    background-color: {t['bg_main']};
    color: {t['text_primary']};
    font-family: "Segoe UI", "Arial", sans-serif;
    font-size: 11pt;
}}
/* Açık tema: stacked widget ve içindeki sayfalar bg_card olsun */
QStackedWidget {{
    background-color: {t['bg_main']};
}}
QStackedWidget > QWidget {{
    background-color: {t['bg_main']};
}}
QWidget#sidebar {{
    background-color: {t['bg_sidebar']};
    border-right: 1px solid {t['border']};
    min-width: 200px;
    max-width: 200px;
}}
QWidget#sidebar > QWidget, QWidget#sidebar QLabel {{
    background: {t['bg_sidebar']};
}}
QWidget#sidebar_logo {{
    background: {t['bg_sidebar']};
    border-bottom: 1px solid {t['border']};
}}

QPushButton#nav_card {{
    background: transparent;
    border: none;
    margin: 2px 10px;
    border-radius: 8px;
    text-align: left;
    padding: 11px 16px;
    font-size: 10pt;
    font-weight: 600;
    color: {'#c0ccdd' if t['name'] == 'dark' else '#334466'};
}}
QPushButton#nav_card:hover {{
    background: {'#1e2545' if t['name'] == 'dark' else '#dde5f0'};
    color: {'#e8eef6' if t['name'] == 'dark' else '#1a1a2e'};
}}
QPushButton#nav_card:checked {{
    background: {t['accent_blue']};
    color: #ffffff;
    font-weight: 700;
}}

/* ── Sidebar alt sekme çubuğu ── */
QFrame#sidebar_tab_bar {{
    background: {t['bg_sidebar_header']};
    border-top: 1px solid {t['border']};
    border-radius: 0;
}}

QPushButton#sidebar_tab {{
    background: transparent;
    color: {t['text_sidebar']};
    border: none;
    border-right: 1px solid {t['border']};
    border-radius: 0;
    font-size: 8pt;
    font-weight: 500;
    padding: 0 10px;
    text-align: center;
}}
QPushButton#sidebar_tab:hover {{
    background: {t['bg_sidebar_hover']};
    color: {t['text_primary']};
    border-bottom: 2px solid {t['header_divider']};
}}
QPushButton#sidebar_tab:pressed {{
    background: {t['accent_blue']};
    color: #ffffff;
}}

QPushButton#sidebar_tab_right {{
    background: transparent;
    color: {t['text_sidebar']};
    border: none;
    border-radius: 0;
    font-size: 8pt;
    font-weight: 500;
    padding: 0 10px;
    text-align: center;
}}
QPushButton#sidebar_tab_right:hover {{
    background: {t['bg_sidebar_hover']};
    color: {t['text_primary']};
    border-bottom: 2px solid {t['accent_blue']};
}}
QPushButton#sidebar_tab_right:pressed {{
    background: {t['accent_blue']};
    color: #ffffff;
}}

/* ══════════════════════════════════════════════════════
   KARTLAR
══════════════════════════════════════════════════════ */
QFrame#card {{
    background: {t['bg_card']};
    border-radius: 14px;
    border: none;
    border-top: 3px solid {t['accent_blue']};
}}
QFrame#section_card {{
    background: {t['bg_card']};
    border-radius: 10px;
    border: 1px solid {t['border']};
}}
QFrame#section_divider {{
    background: {t['accent_blue']};
    border: none;
    max-height: 2px;
    min-height: 2px;
}}
QLabel#section_card_title {{
    color: {t['text_primary']};
    background: transparent;
    font-size: 10pt;
    font-weight: 700;
}}
QLabel#card_value {{
    font-size: 24pt;
    font-weight: bold;
    color: {t['text_card_value']};
    background: transparent;
}}
QLabel#card_label {{
    font-size: 9pt;
    color: {t['text_muted']};
    background: transparent;
}}
QLabel#section_title {{
    font-size: 12pt;
    font-weight: bold;
    color: {t['text_primary']};
}}

/* ══════════════════════════════════════════════════════
   TABLOLAR
══════════════════════════════════════════════════════ */
QTableWidget {{
    background: {t['bg_card']};
    color: {t['text_table']};
    font-size: 9.5pt;
    border: 1px solid {t['border']};
    border-radius: 8px;
    gridline-color: {t['grid_color']};
    alternate-background-color: {t['bg_table_alt']};
    outline: none;
}}
QTableWidget::item {{
    padding: 2px 6px;
    color: {t['text_table']};
    font-size: 9.5pt;
    border: none;
    border-bottom: 1px solid {t['grid_color']};
}}
QTableWidget::item:hover {{
    background-color: {t['bg_sidebar_hover']};
}}
QTableWidget::item:selected {{
    background-color: {t['accent_blue']};
    color: #ffffff;
    border-radius: 4px;
}}
QTableView {{
    background-color: {t['bg_card']};
    alternate-background-color: {t['bg_table_alt']};
    outline: none;
}}
QTableView::item {{
    padding: 8px 6px;
    color: {t['text_table']};
    border: none;
    border-bottom: 1px solid {t['grid_color']};
}}
QHeaderView::section {{
    background-color: {t['bg_table_header']};
    color: {t['text_table_header']};
    padding: 8px 10px;
    font-weight: 600;
    border: none;
    border-right: 1px solid {t['header_divider']};
    border-bottom: 2px solid {t['header_divider']};
    font-size: 9.5pt;
}}
QHeaderView::section:last {{
    border-right: none;
}}
QHeaderView {{
    background-color: {t['bg_table_header']};
}}
QTableCornerButton::section {{
    background-color: {t['bg_table_header']};
    border-bottom: 2px solid {t['header_divider']};
}}

/* ══════════════════════════════════════════════════════
   GİRİŞ ALANLARI
══════════════════════════════════════════════════════ */
QLineEdit, QTextEdit, QPlainTextEdit {{
    border: 1px solid {t['border_input']};
    border-radius: 6px;
    padding: 8px 12px;
    background: {t['bg_input']};
    color: {t['text_input']};
    font-size: 11pt;
    min-height: 38px;
}}
QLineEdit:focus, QTextEdit:focus {{
    border: 1.5px solid {t['accent_blue']};
    background: {t['bg_input']};
}}
QLineEdit:disabled {{
    background: {t['bg_table_alt']};
    color: {t['text_muted']};
}}
QComboBox {{
    border: 1px solid {t['border_input']};
    border-radius: 6px;
    padding: 6px 12px;
    background: {t['bg_input']};
    color: {t['text_input']};
    font-size: 11pt;
    min-height: 38px;
}}
QComboBox:focus {{
    border: 1.5px solid {t['accent_blue']};
}}
QComboBox::drop-down {{
    border: none;
    width: 20px;
}}
QComboBox::down-arrow {{
    image: {_get_arrow_path(t['text_muted'], 'down')};
    width: 16px; height: 16px;
    margin-right: 2px;
}}
QComboBox QAbstractItemView {{
    background: {t['bg_input']};
    color: {t['text_primary']};
    border: 1px solid {t['border_input']};
    selection-background-color: {t['accent_blue']};
    selection-color: #ffffff;
    outline: 0;
    show-decoration-selected: 1;
}}
QComboBox QAbstractItemView::item {{
    background: {t['bg_input']};
    color: {t['text_primary']};
    min-height: 26px;
    padding: 3px 8px;
}}
QComboBox QAbstractItemView::item:hover {{
    background: {t['accent_blue']};
    color: #ffffff;
}}
QComboBox QAbstractItemView::item:selected {{
    background: {t['accent_blue']};
    color: #ffffff;
}}

/* SpinBox — temaya uygun görünür oklar */
QDoubleSpinBox, QSpinBox {{
    border: 1px solid {t['border_input']};
    border-radius: 6px;
    padding: 6px 30px 6px 10px;
    background: {t['bg_input']};
    color: {t['text_input']};
    font-size: 11pt;
    min-height: 38px;
}}
QDoubleSpinBox:focus, QSpinBox:focus {{
    border: 1.5px solid {t['accent_blue']};
}}
QDoubleSpinBox::up-button, QSpinBox::up-button {{
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 22px;
    height: 16px;
    border-left: 1px solid {t['border_input']};
    border-bottom: none;
    border-top-right-radius: 5px;
    background: transparent;
}}
QDoubleSpinBox::down-button, QSpinBox::down-button {{
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 22px;
    height: 16px;
    border-left: 1px solid {t['border_input']};
    border-top: none;
    border-bottom-right-radius: 5px;
    background: transparent;
}}
QDoubleSpinBox::up-button:hover, QSpinBox::up-button:hover,
QDoubleSpinBox::down-button:hover, QSpinBox::down-button:hover {{
    background: {t['spin_btn_hover']};
}}
QDoubleSpinBox::up-arrow, QSpinBox::up-arrow {{
    image: {_get_arrow_path(t['spin_btn_fg'], 'up')};
    width: 12px; height: 12px;
}}
QDoubleSpinBox::down-arrow, QSpinBox::down-arrow {{
    image: {_get_arrow_path(t['spin_btn_fg'], 'down')};
    width: 12px; height: 12px;
}}
QDoubleSpinBox::up-arrow:disabled, QSpinBox::up-arrow:disabled {{
    image: {_get_arrow_path(t['text_muted'], 'up')};
}}
QDoubleSpinBox::down-arrow:disabled, QSpinBox::down-arrow:disabled {{
    image: {_get_arrow_path(t['text_muted'], 'down')};
}}

/* Teklif Koşulları — kompakt form girişleri (genel 38px kuralını ezer) */
QLineEdit#condition_input {{
    min-height: 0px;
    padding: 5px 10px;
    font-size: 10pt;
}}

/* Hücre içi widget sarmalayıcı — sayıdam arka plan (satır seçim rengi görünsün) */
QWidget#table_cell_wrapper {{
    background: transparent;
    border: none;
}}

/* Table specific spin & combo */
QDoubleSpinBox#table_spin, QSpinBox#table_spin {{
    border: none;
    border-radius: 4px;
    padding: 0px 4px;
    font-size: 9.5pt;
    /* Genel kuralın 38px min-height'i hücre yüksekliğini (36px) aşıyordu */
    min-height: 0px;
    background: transparent;
    color: {t['text_table']};
    selection-background-color: {t['accent_blue']};
    selection-color: #ffffff;
    outline: none;
}}
QDoubleSpinBox#table_spin:hover, QSpinBox#table_spin:hover,
QDoubleSpinBox#table_spin:focus, QSpinBox#table_spin:focus {{
    background: transparent;
    border: none;
    outline: none;
}}
QDoubleSpinBox#table_spin::up-button, QSpinBox#table_spin::up-button,
QDoubleSpinBox#table_spin::down-button, QSpinBox#table_spin::down-button {{
    width: 0;
    height: 0;
    border: none;
}}
QDoubleSpinBox#table_spin[rowSelected="true"], QSpinBox#table_spin[rowSelected="true"] {{
    background: transparent;
    color: #ffffff;
}}
/* Spin'in İÇİNDEKİ QLineEdit — genel QLineEdit kuralının 38px min-height ve
   8px dolgusu 36px'lik hücrede metni aşağı itiyordu; burada sıfırlanır */
QDoubleSpinBox#table_spin QLineEdit, QSpinBox#table_spin QLineEdit {{
    border: none;
    padding: 0px;
    margin: 0px;
    min-height: 0px;
    background: transparent;
    color: {t['text_table']};
    selection-background-color: {t['accent_blue']};
    selection-color: #ffffff;
}}
QDoubleSpinBox#table_spin[rowSelected="true"] QLineEdit,
QSpinBox#table_spin[rowSelected="true"] QLineEdit {{
    color: #ffffff;
}}

QComboBox#table_combo {{
    border: none;
    border-radius: 4px;
    padding: 0px 4px;
    font-size: 9.5pt;
    /* min-width verilmez: dar sütunda (Birim) widget hücreden taşıp
       ok simgesini komşu sütun sınırına bindiriyordu */
    min-width: 0px;
    /* Genel kuralın 38px min-height'i hücre yüksekliğini (36px) aşıyordu */
    min-height: 0px;
    background: transparent;
    color: {t['text_table']};
    outline: none;
}}
QComboBox#table_combo:hover, QComboBox#table_combo:focus,
QComboBox#table_combo:on {{
    background: transparent;
    border: none;
    outline: none;
}}
QComboBox#table_combo[rowSelected="true"] {{
    background: transparent;
    color: #ffffff;
}}
QComboBox#table_combo QLineEdit#table_combo_editor {{
    border: none;
    padding: 0px 2px;
    margin: 0px;
    min-height: 0px;
    background: transparent;
    color: {t['text_table']};
    selection-background-color: {t['accent_blue']};
    selection-color: #ffffff;
}}
QComboBox#table_combo[rowSelected="true"] QLineEdit#table_combo_editor {{
    color: #ffffff;
}}
QComboBox#table_combo::drop-down {{
    width: 16px;
    border: none;
}}
QComboBox#table_combo::down-arrow {{
    image: {_get_arrow_path(t['text_muted'], 'down')};
    width: 14px; height: 14px;
    margin-right: 2px;
}}

/* ══════════════════════════════════════════════════════
   BUTONLAR
══════════════════════════════════════════════════════ */
/* primary — asıl eylem butonu: kalıcı dolgulu, ilk bakışta ayırt edilir */
QPushButton#primary {{
    background: {t['accent_blue']};
    color: #ffffff;
    border: 1.5px solid {t['accent_blue']};
    border-radius: 8px;
    padding: 9px 24px;
    font-weight: 600;
    font-size: 10.5pt;
}}
QPushButton#primary:hover {{
    background-color: {t['accent_blue_hover']};
    border-color: {t['accent_blue_hover']};
}}
QPushButton#primary:pressed {{
    background-color: {t['accent_blue_hover']};
    border-color: {t['accent_blue_hover']};
    padding: 10px 24px 8px 24px;
}}
QPushButton#primary:disabled {{
    background: {t['border']};
    border-color: {t['border']};
    color: {t['text_muted']};
}}

QPushButton#danger {{
    background: {t['bg_card']};
    color: {t['accent_red']};
    border: 1.5px solid {t['border']};
    border-radius: 8px;
    padding: 8px 20px;
    font-weight: 600;
}}
QPushButton#danger:hover {{
    background-color: {t['accent_red']};
    color: #ffffff;
    border-color: {t['accent_red']};
}}
QPushButton#danger:pressed {{
    background-color: {t['accent_red_hover']};
    color: #ffffff;
    padding: 7px 20px;
}}

QPushButton#secondary {{
    background: {t['bg_card']};
    color: {t['text_primary']};
    border: 1.5px solid {t['border']};
    border-radius: 8px;
    padding: 8px 20px;
    font-weight: 500;
}}
QPushButton#secondary:hover {{
    border-color: {t['accent_blue']};
    color: {t['accent_blue']};
}}
QPushButton#secondary:checked {{
    background: {t['accent_blue']};
    color: #ffffff;
    border-color: {t['accent_blue']};
}}
QPushButton#secondary:pressed {{ padding: 7px 20px; }}

/* Kare ikon butonu — "+" gibi tek karakter için */
QPushButton#icon_btn {{
    background: transparent;
    color: {t['text_primary']};
    border: 1.5px solid {t['border']};
    border-radius: 8px;
    padding: 0px 0px 2px 0px;
    font-size: 20pt;
    font-weight: 300;
}}
QPushButton#icon_btn:hover {{
    border-color: {t['accent_blue']};
    color: {t['accent_blue']};
    background: {t['bg_sidebar_hover']};
}}
QPushButton#icon_btn:pressed {{
    background: {t['bg_table_alt']};
}}

/* action_btn — genel nötr buton (tarih temizle vs.) */
QPushButton#action_btn {{
    background: {t['bg_card']};
    color: {t['text_primary']};
    border: 1.5px solid {t['border']};
    border-radius: 8px;
    padding: 6px 16px;
    font-size: 9pt;
    font-weight: 600;
}}
QPushButton#action_btn:hover {{
    background: {t['accent_blue']};
    border-color: {t['accent_blue']};
    color: #ffffff;
}}
QPushButton#action_btn:pressed {{
    background: {t['accent_blue_hover']};
    color: #ffffff;
    border-color: {t['accent_blue_hover']};
}}

/* ══════════════════════════════════════════════════════
   EYLEM BUTON GRUBU — bağımsız, modern, renkli
══════════════════════════════════════════════════════ */

QPushButton#tab_btn_clone,
QPushButton#tab_btn_edit,
QPushButton#tab_btn_status,
QPushButton#tab_btn_pdf,
QPushButton#tab_btn_delete {{
    font-size: 9.5pt;
    font-weight: 600;
    padding: 0px 16px;
    min-height: 34px;
    border: none;
    border-radius: 8px;
    margin: 0px 2px;
}}

QPushButton#tab_btn_clone {{
    background: {t['accent_blue']};
    color: #ffffff;
}}
QPushButton#tab_btn_clone:hover {{
    background: {t['accent_blue_hover']};
}}
QPushButton#tab_btn_clone:pressed {{
    background: {t['accent_blue_hover']};
    padding-top: 1px;
}}

QPushButton#tab_btn_edit {{
    background: {t['accent_blue']};
    color: #ffffff;
}}
QPushButton#tab_btn_edit:hover {{
    background: {t['accent_blue_hover']};
}}
QPushButton#tab_btn_edit:pressed {{
    background: {t['accent_blue_hover']};
    padding-top: 1px;
}}

QPushButton#tab_btn_status {{
    background: #f59e0b;
    color: #ffffff;
}}
QPushButton#tab_btn_status:hover {{
    background: #d48000;
}}
QPushButton#tab_btn_status:pressed {{
    background: #c47800;
    padding-top: 1px;
}}

QPushButton#tab_btn_pdf {{
    background: #10b981;
    color: #ffffff;
}}
QPushButton#tab_btn_pdf:hover {{
    background: #059669;
}}
QPushButton#tab_btn_pdf:pressed {{
    background: #047857;
    padding-top: 1px;
}}

QPushButton#tab_btn_delete {{
    background: #ef4444;
    color: #ffffff;
}}
QPushButton#tab_btn_delete:hover {{
    background: #dc2626;
}}
QPushButton#tab_btn_delete:pressed {{
    background: #b91c1c;
    padding-top: 1px;
}}

/* ══════════════════════════════════════════════════════
   GROUPBOX
══════════════════════════════════════════════════════ */
QGroupBox {{
    background: {t['bg_card']};
    border: 1px solid {t['border']};
    border-radius: 10px;
    font-weight: 700;
    font-size: 9pt;
    color: {t['text_primary']};
    margin-top: 14px;
    padding-top: 16px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 14px;
    top: 0px;
    padding: 0px 6px;
    color: {t['text_primary']};
    background: transparent;
    font-size: 9pt;
    font-weight: 700;
}}

/* ══════════════════════════════════════════════════════
   TOOLBAR FRAME
══════════════════════════════════════════════════════ */
QFrame#toolbar {{
    background: {t['bg_toolbar']};
    border-radius: 8px;
    border: 1px solid {t['border']};
}}

/* ══════════════════════════════════════════════════════
   LABEL
══════════════════════════════════════════════════════ */
QLabel {{
    color: {t['text_primary']};
    background: transparent;
}}
QLabel#total_label {{
    font-size: 13pt;
    font-weight: bold;
    color: {t['accent_blue']};
}}
QLabel#offer_no_label {{
    font-size: 10pt;
    font-weight: 700;
    color: {t['accent_blue']};
    background: {t['bg_card']};
    border: 1.5px solid {t['border']};
    border-radius: 6px;
    padding: 2px 12px;
    min-height: 20px;
    max-height: 22px;
}}

/* Teklif oluşturma header — tarih kutusu */
QLineEdit#header_date_display {{
    font-size: 10pt;
    font-weight: 600;
    color: {t['accent_blue']};
    background: {t['bg_card']};
    border: 1.5px solid {t['border']};
    border-radius: 6px;
    padding: 2px 8px;
    min-height: 0px;
}}
QLineEdit#header_date_display:hover {{
    border-color: {t['accent_blue']};
}}

/* ══════════════════════════════════════════════════════
   MODERN WIZARD KARTLARI
══════════════════════════════════════════════════════ */
QFrame#step_card {{
    background: {t['bg_card']};
    border: 1px solid {t['border']};
    border-radius: 12px;
}}
QLabel#step_card_title {{
    font-size: 10.5pt;
    font-weight: 500;
    color: {t['text_primary']};
    background: transparent;
    padding-bottom: 2px;
}}
QLabel#step_form_label {{
    font-size: 8.5pt;
    font-weight: 500;
    color: {t['text_muted']};
    background: transparent;
    margin-top: 4px;
}}
QFrame#step_connector {{
    background: {t['border']};
    border: none;
}}
QLabel#hint_label {{
    color: {t['text_muted']};
    background: transparent;
    font-size: 9pt;
}}
/* ══════════════════════════════════════════════════════
   CHECKBOX
══════════════════════════════════════════════════════ */
QCheckBox {{
    spacing: 8px;
    color: {t['text_primary']};
    font-size: 9pt;
}}
QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border: 2px solid {t['border_input']};
    border-radius: 4px;
    background: {t['bg_input']};
}}
QCheckBox::indicator:hover {{
    border-color: {t['accent_blue']};
}}
QCheckBox::indicator:checked {{
    background: {t['accent_blue']};
    border-color: {t['accent_blue']};
    image: {_get_checkmark_path()};
}}

QFrame#transparent_frame {{
    background: transparent;
    border: none;
}}
QWidget#img_preview_frame {{
    border: 1px dashed {t['border_input']};
    border-radius: 6px;
    background-color: {t['bg_input']};
}}
QLabel#img_preview_label {{
    color: {t['text_muted']};
    background: transparent;
    border: none;
}}

/* ══════════════════════════════════════════════════════
   TOPLAM ROZETİ
══════════════════════════════════════════════════════ */
QLabel#total_badge {{
    background: {t['accent_blue']};
    color: white;
    border-bottom: 3px solid {t['accent_blue']}cc;
    border-radius: 8px;
    font-size: 10.5pt;
    font-weight: 700;
    padding: 6px 16px;
}}

/* ══════════════════════════════════════════════════════
   DİYALOG
══════════════════════════════════════════════════════ */
QDialog {{
    background: {t['bg_dialog']};
    color: {t['text_primary']};
}}
QDialog QWidget {{
    background: {t['bg_dialog']};
    color: {t['text_primary']};
}}
QDialog QLabel {{
    color: {t['text_primary']};
    background: transparent;
}}
QDialog QGroupBox {{
    background: {t['bg_dialog']};
    border: 1px solid {t['border']};
    border-radius: 10px;
    margin-top: 14px;
    padding-top: 16px;
}}
QDialog QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 14px;
    top: 0px;
    padding: 0px 6px;
    background: transparent;
    color: {t['text_primary']};
    font-size: 9pt;
    font-weight: 700;
}}

/* ══════════════════════════════════════════════════════
   TAB WIDGET — Chrome/Edge sekmeler
══════════════════════════════════════════════════════ */
/* ══ TABS — Chrome/Edge style ══ */
QTabWidget::pane {{
    border: 1px solid {t['border']};
    border-top: none;
    background: {t['bg_card']};
    border-bottom-left-radius: 10px;
    border-bottom-right-radius: 10px;
}}
QTabWidget::tab-bar {{
    alignment: left;
}}
QTabBar {{
    background: transparent;
    border: none;
    qproperty-drawBase: 0;
}}
QTabBar::tab {{
    background: {t['bg_table_alt']};
    color: {t['text_muted']};
    border: 1px solid {t['border']};
    border-bottom: none;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    padding: 8px 24px;
    margin-right: 0px;
    margin-bottom: -1px;
    font-size: 9pt;
    font-weight: 600;
    min-width: 100px;
}}
QTabBar::tab:hover {{
    background: {t['bg_card']};
    color: {t['text_primary']};
}}
QTabBar::tab:selected {{
    background: {t['bg_card']};
    color: {t['accent_blue']};
    border-bottom: 2px solid {t['accent_blue']};
    font-weight: 700;
    padding-bottom: 9px;
}}
QTabBar::tab:!selected {{
    margin-top: 3px;
}}

/* ══════════════════════════════════════════════════════
   SCROLLBAR — Chrome/Edge ince
══════════════════════════════════════════════════════ */
QScrollBar:vertical {{
    border: none; background: transparent;
    width: 8px; margin: 0;
}}
QScrollBar::handle:vertical {{
    background: rgba(120,120,120,0.40);
    border-radius: 4px; min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{ background: rgba(80,80,80,0.65); }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; border: none; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
QScrollBar:horizontal {{
    border: none; background: transparent;
    height: 8px; margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: rgba(120,120,120,0.40);
    border-radius: 4px; min-width: 30px;
}}
QScrollBar::handle:horizontal:hover {{ background: rgba(80,80,80,0.65); }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; border: none; }}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: none; }}

QScrollArea {{ border: none; background: transparent; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}

/* ══════════════════════════════════════════════════════
   MESAJ KUTUSU
══════════════════════════════════════════════════════ */
QMessageBox {{
    background: {t['bg_dialog']};
    color: {t['text_primary']};
}}
QMessageBox QLabel {{
    color: {t['text_primary']};
    background: transparent;
}}
QMessageBox QPushButton {{
    background: {t['bg_card']};
    color: {t['text_primary']};
    border: 1.5px solid {t['border']};
    border-radius: 4px;
    padding: 6px 18px;
    min-width: 70px;
}}
QMessageBox QPushButton:hover {{
    background: {t['accent_blue']};
    color: white;
    border-color: {t['accent_blue']};
}}

/* ══════════════════════════════════════════════════════
   SAĞ TIK MENÜSÜ
══════════════════════════════════════════════════════ */
QMenu {{
    background-color: {t['bg_dialog']};
    color: {t['text_primary']};
    border: 1px solid {t['border']};
    border-radius: 6px;
    padding: 4px 0px;
}}
QMenu::item {{
    padding: 7px 28px 7px 28px;
    font-size: 9pt;
    color: {t['text_primary']};
    background: transparent;
}}
QMenu::item:selected {{
    background-color: {t['accent_blue']};
    color: #ffffff;
    border-radius: 3px;
}}
QMenu::item:disabled {{ color: {t['text_muted']}; }}
QMenu::separator {{ height: 1px; background: {t['border']}; margin: 3px 8px; }}

/* ══════════════════════════════════════════════════════
   ÜST BAR + MENÜ ÇUBUĞU
══════════════════════════════════════════════════════ */
QWidget#topbar {{
    background-color: {t['bg_toolbar']};
    border-bottom: 1px solid {t['border']};
}}
QMenuBar {{
    background-color: {t['bg_toolbar']};
    color: {t['text_primary']};
    padding: 2px 4px;
    font-size: 9pt;
    border-bottom: 1px solid {t['border']};
}}
QMenuBar::item {{
    padding: 5px 12px;
    border-radius: 4px;
    background: transparent;
    color: {t['text_primary']};
}}
QMenuBar::item:selected {{
    background-color: {t['bg_sidebar_hover']};
    color: {t['text_primary']};
}}
QMenuBar::item:pressed {{
    background-color: {t['accent_blue']};
    color: #ffffff;
}}

/* ══════════════════════════════════════════════════════
   TABLO İÇİ WIDGET'LAR — inline stil yönetilir
   (QFont -1 hatasını önlemek için buraya eklenmedi)
══════════════════════════════════════════════════════ */

/* ══════════════════════════════════════════════════════
   TAKVİM (QDateEdit popup / QCalendarWidget)
══════════════════════════════════════════════════════ */
QDateEdit {{
    border: 1px solid {t['border_input']};
    border-radius: 6px;
    padding: 0px 10px;
    background: {t['bg_input']};
    color: {t['text_input']};
    font-size: 10pt;
    min-height: 34px;
}}
QDateEdit:focus {{
    border: 1.5px solid {t['accent_blue']};
}}
QDateEdit::drop-down {{
    border: none;
    width: 24px;
}}
QCalendarWidget {{
    min-width: 300px;
    min-height: 250px;
}}
QCalendarWidget QWidget {{
    background-color: {t['bg_dialog']};
    color: {t['text_primary']};
}}
QCalendarWidget QToolButton {{
    background: {t['accent_blue']};
    color: #ffffff;
    border: none;
    border-radius: 4px;
    padding: 6px 12px;
    font-weight: bold;
    font-size: 9pt;
    min-width: 30px;
}}
QCalendarWidget QToolButton:hover {{
    background: {t['accent_blue_hover']};
}}
QCalendarWidget QToolButton::menu-indicator {{
    image: none;
}}
QCalendarWidget QToolButton#qt_calendar_prevmonth,
QCalendarWidget QToolButton#qt_calendar_nextmonth {{
    min-width: 24px;
    padding: 6px;
}}
QCalendarWidget QSpinBox {{
    background: {t['bg_input']};
    color: {t['text_input']};
    border: 1px solid {t['border_input']};
    border-radius: 4px;
    padding: 2px 4px;
    min-width: 60px;
    selection-background-color: {t['accent_blue']};
}}
QCalendarWidget QMenu {{
    background-color: {t['bg_dialog']};
    color: {t['text_primary']};
    border: 1px solid {t['border']};
}}
QCalendarWidget QWidget#qt_calendar_navigationbar {{
    background-color: {t['accent_blue']};
    min-height: 36px;
}}
QCalendarWidget QAbstractItemView {{
    background-color: {t['bg_dialog']};
    color: {t['text_primary']};
    selection-background-color: {t['accent_blue']};
    selection-color: #ffffff;
    font-size: 9pt;
    outline: none;
    gridline-color: {t['grid_color']};
}}
QCalendarWidget QAbstractItemView:disabled {{
    color: {t['text_muted']};
}}
"""
