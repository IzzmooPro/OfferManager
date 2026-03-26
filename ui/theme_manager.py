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
}

_current = LIGHT


def get_theme() -> dict:
    return _current


def toggle_theme():
    global _current
    _current = DARK if _current["name"] == "light" else LIGHT


def build_stylesheet(t: dict) -> str:
    return f"""
/* ══════════════════════════════════════════════════════
   ANA PENCERE / GENEL
══════════════════════════════════════════════════════ */
QMainWindow, QWidget {{
    background-color: {t['bg_main']};
    color: {t['text_primary']};
    font-family: "Segoe UI", "Arial", sans-serif;
    font-size: 10pt;
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
    min-width: 224px;
    max-width: 224px;
}}
QWidget#sidebar_header {{
    background-color: {t['bg_sidebar_header']};
    border-bottom: 1px solid {t['border']};
}}
QPushButton#nav_card {{
    background: transparent;
    border: 1.5px solid transparent;
    margin: 3px 10px;
    border-radius: 12px;
    text-align: left;
    padding: 0;
}}
QPushButton#nav_card:hover {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 rgba(255,255,255,0.13), stop:1 rgba(255,255,255,0.04));
    border: 1.5px solid rgba(255,255,255,0.18);
}}
QPushButton#nav_card:checked {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 {t['accent_blue']}, stop:1 #2a52a8);
    border: 1.5px solid rgba(255,255,255,0.10);
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
    border: 1px solid {t['border']};
    border-radius: 8px;
    gridline-color: {t['grid_color']};
    alternate-background-color: {t['bg_table_alt']};
    outline: none;
}}
QTableWidget::item {{
    padding: 8px 6px;
    color: {t['text_table']};
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
QHeaderView::section {{
    background-color: {t['bg_table_header']};
    color: {t['text_table_header']};
    padding: 8px 10px;
    font-weight: bold;
    border: none;
    border-right: 1px solid {t['header_divider']};
    border-bottom: 2px solid {t['header_divider']};
    font-size: 9pt;
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
    padding: 7px 10px;
    background: {t['bg_input']};
    color: {t['text_input']};
    min-height: 22px;
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
    padding: 5px 8px;
    background: {t['bg_input']};
    color: {t['text_input']};
    font-size: 10pt;
}}
QComboBox:focus {{
    border: 1.5px solid {t['accent_blue']};
}}
QComboBox::drop-down {{
    border: none;
    width: 20px;
}}
QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {t['text_muted']};
    width: 0; height: 0;
    margin-right: 6px;
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
QComboBox QAbstractItemView::item:selected {{
    background: {t['accent_blue']};
    color: #ffffff;
}}

/* SpinBox — temaya uygun görünür oklar */
QDoubleSpinBox, QSpinBox {{
    border: 1px solid {t['border_input']};
    border-radius: 6px;
    padding: 5px 30px 5px 8px;
    background: {t['bg_input']};
    color: {t['text_input']};
    font-size: 10pt;
    min-height: 30px;
}}
QDoubleSpinBox:focus, QSpinBox:focus {{
    border: 1.5px solid {t['accent_blue']};
}}
QDoubleSpinBox::up-button, QSpinBox::up-button {{
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 26px;
    height: 15px;
    border-left: 1px solid {t['border_input']};
    border-bottom: 1px solid {t['border_input']};
    border-top-right-radius: 5px;
    background: {t['spin_btn_bg']};
}}
QDoubleSpinBox::down-button, QSpinBox::down-button {{
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 26px;
    height: 15px;
    border-left: 1px solid {t['border_input']};
    border-top: none;
    border-bottom-right-radius: 5px;
    background: {t['spin_btn_bg']};
}}
QDoubleSpinBox::up-button:hover, QSpinBox::up-button:hover,
QDoubleSpinBox::down-button:hover, QSpinBox::down-button:hover {{
    background: {t['spin_btn_hover']};
}}
QDoubleSpinBox::up-arrow, QSpinBox::up-arrow {{
    width: 10px; height: 10px;
    image: none;
    border-style: solid;
    border-width: 0 3px 5px 3px;
    border-color: transparent transparent {t['spin_btn_fg']} transparent;
}}
QDoubleSpinBox::down-arrow, QSpinBox::down-arrow {{
    width: 10px; height: 10px;
    image: none;
    border-style: solid;
    border-width: 5px 3px 0 3px;
    border-color: {t['spin_btn_fg']} transparent transparent transparent;
}}
QDoubleSpinBox::up-arrow:disabled, QSpinBox::up-arrow:disabled,
QDoubleSpinBox::down-arrow:disabled, QSpinBox::down-arrow:disabled {{
    border-color: transparent transparent {t['text_muted']} transparent;
}}

/* ══════════════════════════════════════════════════════
   BUTONLAR
══════════════════════════════════════════════════════ */
QPushButton#primary {{
    background: {t['bg_card']};
    color: {t['text_primary']};
    border: 1.5px solid {t['border']};
    border-radius: 20px;
    padding: 9px 24px;
    font-weight: 600;
    font-size: 10pt;
}}
QPushButton#primary:hover {{
    background-color: {t['accent_blue']};
    color: #ffffff;
    border-color: {t['accent_blue']};
}}
QPushButton#primary:pressed {{
    background-color: {t['accent_blue_hover']};
    color: #ffffff;
    border-color: {t['accent_blue_hover']};
    padding: 8px 24px;
}}

QPushButton#green {{
    background: {t['bg_card']};
    color: {t['text_primary']};
    border: 1.5px solid {t['border']};
    border-radius: 6px;
    padding: 9px 20px;
    font-weight: bold;
    font-size: 10pt;
}}
QPushButton#green:hover {{
    background-color: {t['accent_green']};
    color: #ffffff;
    border-color: {t['accent_green']};
}}
QPushButton#green:pressed {{
    background-color: {t['accent_green_hover']};
    color: #ffffff;
    border-color: {t['accent_green_hover']};
}}

QPushButton#danger {{
    background: {t['bg_card']};
    color: {t['accent_red']};
    border: 1.5px solid {t['border']};
    border-radius: 20px;
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
    border-radius: 20px;
    padding: 8px 20px;
    font-weight: 500;
}}
QPushButton#secondary:hover {{
    border-color: {t['accent_blue']};
    color: {t['accent_blue']};
}}
QPushButton#secondary:pressed {{ padding: 7px 20px; }}

QPushButton#small {{
    background: {t['bg_card']};
    color: {t['text_primary']};
    border: 1px solid {t['border']};
    border-radius: 4px;
    padding: 6px 14px;
    font-size: 9pt;
}}
QPushButton#small:hover {{
    background: {t['accent_blue']};
    color: #ffffff;
    border-color: {t['accent_blue']};
}}

/* action_btn — genel nötr buton (tarih temizle vs.) */
QPushButton#action_btn {{
    background: {t['bg_card']};
    color: {t['text_primary']};
    border: 1.5px solid {t['border']};
    border-radius: 20px;
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
   BİTİŞİK EYLEM BUTON GRUBU — düz renk, oval uçlar
══════════════════════════════════════════════════════ */

QPushButton#tab_btn_edit,
QPushButton#tab_btn_status,
QPushButton#tab_btn_pdf,
QPushButton#tab_btn_delete {{
    font-size: 9pt;
    font-weight: 600;
    padding: 0px 18px;
    min-height: 34px;
    border-style: solid;
    border-width: 1.5px;
    border-right-width: 0px;
    margin: 0px;
    border-radius: 0px;
}}

/* Düzenle — nötr, sol oval */
QPushButton#tab_btn_edit {{
    background: {t['bg_card']};
    color: {t['text_primary']};
    border-color: {t['border']};
    border-top-left-radius: 18px;
    border-bottom-left-radius: 18px;
}}
QPushButton#tab_btn_edit:hover {{
    background: {t['accent_blue']};
    color: #ffffff;
    border-color: {t['accent_blue']};
}}
QPushButton#tab_btn_edit:pressed {{
    background: {t['accent_blue_hover']};
    color: #ffffff;
}}

/* Durum — nötr */
QPushButton#tab_btn_status {{
    background: {t['bg_card']};
    color: {t['text_primary']};
    border-color: {t['border']};
}}
QPushButton#tab_btn_status:hover {{
    background: #f59e0b;
    color: #ffffff;
    border-color: #d48000;
}}
QPushButton#tab_btn_status:pressed {{
    background: #c47800;
    color: #ffffff;
}}

/* PDF — nötr */
QPushButton#tab_btn_pdf {{
    background: {t['bg_card']};
    color: {t['text_primary']};
    border-color: {t['border']};
}}
QPushButton#tab_btn_pdf:hover {{
    background: #10b981;
    color: #ffffff;
    border-color: #059669;
}}
QPushButton#tab_btn_pdf:pressed {{
    background: #047857;
    color: #ffffff;
}}

/* Sil — nötr, sağ oval */
QPushButton#tab_btn_delete {{
    background: {t['bg_card']};
    color: {t['text_primary']};
    border-color: {t['border']};
    border-top-right-radius: 18px;
    border-bottom-right-radius: 18px;
    border-right-width: 1.5px;
}}
QPushButton#tab_btn_delete:hover {{
    background: #ef4444;
    color: #ffffff;
    border-color: #dc2626;
}}
QPushButton#tab_btn_delete:pressed {{
    background: #b91c1c;
    color: #ffffff;
}}

/* filter_btn — durum filtre dropdown */
QPushButton#filter_btn {{
    background: {t['bg_card']};
    color: {t['text_secondary']};
    border: 1px solid {t['border']};
    border-radius: 6px;
    padding: 6px 12px;
    font-size: 9pt;
    text-align: left;
}}
QPushButton#filter_btn:hover {{
    border-color: {t['accent_blue']};
    color: {t['text_primary']};
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
    font-size: 11pt;
    font-weight: bold;
    color: {t['accent_red']};
    background: {t['bg_card']};
    border: 1px solid {t['border']};
    border-radius: 6px;
    padding: 6px 12px;
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
"""
