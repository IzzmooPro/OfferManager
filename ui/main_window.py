"""Ana pencere — sidebar kart tasarımı, üst bar tema butonu, yedekleme servisi."""
import logging
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QLabel, QStackedWidget, QMessageBox, QStatusBar
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QAction, QCloseEvent, QKeySequence, QShortcut

logger = logging.getLogger("main_window")

from core.constants import APP_VERSION

# Sidebar menü kartları — (başlık, sayfa_idx)
NAV_CARDS = [
    ("Yeni Teklif",  4),
    ("Teklifler",    0),
    ("Müşteriler",   2),
    ("Ürünler",      1),
    ("Raporlar",     6),
    ("Ayarlar",      5),
]


def _sidebar_text_color():
    from ui.utils.theme_manager import get_theme
    t = get_theme()
    return t["text_sidebar"] if t["name"] == "light" else "white"


class NavCard(QPushButton):
    """Sidebar için navigasyon butonu."""
    def __init__(self, title: str, parent=None):
        super().__init__(title, parent)
        self._checked = False
        self.setCheckable(True)
        self.setFixedHeight(42)
        self.setObjectName("nav_card")
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def setChecked(self, checked: bool):
        super().setChecked(checked)
        self._checked = checked

    def _apply_state(self):
        pass


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Teklif Yönetim Sistemi")
        self.setMinimumSize(1100, 700)
        self.resize(1300, 800)

        self._help_dialog = None   # F1 toggle için referans

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(self._build_sidebar())

        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(0)
        self.stack = QStackedWidget()
        right.addWidget(self.stack, 1)
        self._status_lbl = QLabel("")
        self._status_lbl.setFixedHeight(0)
        self._status_lbl.setObjectName("status_toast")
        self._status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right.addWidget(self._status_lbl)
        body.addLayout(right, 1)
        root.addLayout(body)

        self._build_menubar()
        self._load_pages()
        self._start_backup_service()
        self._apply_theme()

        # Arka planda güncelleme kontrolü başlat (sessiz)
        self._start_update_check()

    # ── Kapatma olayı ────────────────────────────────────────────────────────

    def closeEvent(self, event: QCloseEvent):
        """Kapatma öncesi kaydedilmemiş form kontrolü + otomatik yedek."""
        page = self.pages.get(4)
        if page and hasattr(page, "is_dirty") and page.is_dirty():
            ans = QMessageBox.question(
                self, "Kaydedilmemiş Değişiklikler",
                "Teklif formunda kaydedilmemiş değişiklikler var.\n"
                "Çıkmak istediğinizden emin misiniz?\n"
                "(Değişiklikler kaybolacak)",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if ans != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        # Ayarlarda kaydedilmemiş değişiklik varsa kaydetmeyi öner
        spage = self.pages.get(5)
        if spage and hasattr(spage, "is_dirty") and spage.is_dirty():
            ans = QMessageBox.question(
                self, "Kaydedilmemiş Ayarlar",
                "Ayarlarda kaydedilmemiş değişiklikler var.\n"
                "Kapatmadan önce kaydedilsin mi?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes)
            if ans == QMessageBox.StandardButton.Yes:
                spage._save()
        # Onay alındıktan SONRA yedek al
        try:
            self._backup_svc.trigger_now(reason="kapanma")
            logger.info("Kapanma yedeği alındı.")
        except Exception as e:
            logger.warning("Kapanma yedeği alınamadı: %s", e)
        event.accept()

    # ── Menü çubuğu ──────────────────────────────────────────────────────────

    def _build_menubar(self):
        mb = self.menuBar()
        mb.setNativeMenuBar(False)
        mb.setMouseTracking(True)

        # ── Dosya menüsü ─────────────────────────────────────────────────
        file_menu = mb.addMenu("Dosya")

        imp_menu = file_menu.addMenu("İçeri Aktar")
        act_all_imp = QAction("Tümünü İçe Aktar (Tek Dosya)...", self)
        act_all_imp.triggered.connect(lambda: self._open_excel_import("all"))
        imp_menu.addAction(act_all_imp)
        imp_menu.addSeparator()
        for text, kind in [("Müşteri İçe Aktar...", "customers"),
                           ("Ürün İçe Aktar...",    "products"),
                           ("Teklif İçe Aktar...",  "offers")]:
            act = QAction(text, self)
            act.triggered.connect(lambda _, k=kind: self._open_excel_import(k))
            imp_menu.addAction(act)

        exp_menu = file_menu.addMenu("Dışarı Aktar")
        act_all_exp = QAction("Tümünü Dışa Aktar (Tek Dosya)...", self)
        act_all_exp.triggered.connect(lambda: self._export_data("all"))
        exp_menu.addAction(act_all_exp)
        exp_menu.addSeparator()
        for text, kind in [("Müşteri Dışa Aktar...", "customers"),
                           ("Ürün Dışa Aktar...",    "products"),
                           ("Teklif Dışa Aktar...",  "offers")]:
            act = QAction(text, self)
            act.triggered.connect(lambda _, k=kind: self._export_data(k))
            exp_menu.addAction(act)

        file_menu.addSeparator()

        act_backup = QAction("Verileri Yedekle / Geri Yükle...\tCtrl+B", self)
        act_backup.setShortcut("Ctrl+B")
        act_backup.triggered.connect(self._open_backup)
        file_menu.addAction(act_backup)

        # ── Görünüm menüsü ───────────────────────────────────────────────
        view_menu = mb.addMenu("Görünüm")

        theme_menu = view_menu.addMenu("Tema Seçin")
        self._theme_actions = {}
        for key, label in [("light", "Açık Tema"), ("dark", "Koyu Tema"), ("system", "Sistem (Otomatik)")]:
            act = QAction(label, self)
            act.setCheckable(True)
            act.triggered.connect(lambda _, k=key: self._set_theme(k))
            theme_menu.addAction(act)
            self._theme_actions[key] = act
        self._sync_theme_menu()

        sc_theme = QShortcut(QKeySequence("Ctrl+T"), self)
        sc_theme.activated.connect(self._cycle_theme)

        # ── Yardım menüsü ────────────────────────────────────────────────
        help_menu = mb.addMenu("Yardım")

        act_how = QAction("Nasıl Kullanılır?", self)
        act_how.triggered.connect(self._toggle_how_to_use)
        help_menu.addAction(act_how)

        # F1 uygulama genelinde çalışsın (dialog açıkken de tetiklensin)
        f1_shortcut = QShortcut(QKeySequence("F1"), self)
        f1_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        f1_shortcut.activated.connect(self._toggle_how_to_use)

        help_menu.addSeparator()

        act_about = QAction("Hakkında\tCtrl+H", self)
        act_about.setShortcut("Ctrl+H")
        act_about.triggered.connect(self._open_about)
        help_menu.addAction(act_about)

    # ── Sidebar ──────────────────────────────────────────────────────────────

    def _build_sidebar(self):
        from PySide6.QtGui import QPixmap
        from core.app_paths import ASSET_ROOT

        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 1, 0)
        layout.setSpacing(0)

        self._sidebar_title_lbl = QLabel("")

        # Logo / İkon alanı
        logo_frame = QWidget()
        logo_frame.setObjectName("sidebar_logo")
        logo_lay = QVBoxLayout(logo_frame)
        logo_lay.setContentsMargins(0, 20, 0, 12)
        logo_lay.setSpacing(6)

        icon_path = ASSET_ROOT / "assets" / "ico.png"
        icon_lbl = QLabel()
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if icon_path.exists():
            pix = QPixmap(str(icon_path)).scaled(
                40, 40, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation)
            icon_lbl.setPixmap(pix)
        logo_lay.addWidget(icon_lbl)

        app_name = QLabel("Teklif Yönetim")
        app_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        app_name.setStyleSheet("font-size:11pt; font-weight:700; background:transparent;")
        logo_lay.addWidget(app_name)

        layout.addWidget(logo_frame)
        layout.addSpacing(8)

        # Navigasyon kartları
        self._btn_map: dict[int, NavCard] = {}
        for title, idx in NAV_CARDS:
            card = NavCard(title)
            card.clicked.connect(lambda checked, i=idx: self._navigate(i, from_sidebar=True))
            layout.addWidget(card)
            self._btn_map[idx] = card

        layout.addStretch(1)

        ver_lbl = QLabel(APP_VERSION)
        ver_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Renk QSS'teki hint_label kuralından gelir — tema değişince otomatik güncellenir
        ver_lbl.setObjectName("hint_label")
        ver_lbl.setStyleSheet("font-weight:700; padding:14px; background:transparent;")
        layout.addWidget(ver_lbl)
        return sidebar

    # ── Sayfalar ─────────────────────────────────────────────────────────────

    def _load_pages(self):
        from ui.dashboard_page    import DashboardPage
        from ui.products_page     import ProductsPage
        from ui.customers_page    import CustomersPage
        from ui.create_offer_page import CreateOfferPage
        from ui.settings_page     import SettingsPage
        from ui.reports_page      import ReportsPage

        self.pages = {
            0: DashboardPage(),
            1: ProductsPage(),
            2: CustomersPage(),
            4: CreateOfferPage(),
            5: SettingsPage(),
            6: ReportsPage(),
        }
        self.pages[0].edit_offer_requested.connect(self._open_edit_offer)
        self.pages[0].clone_offer_requested.connect(self._open_clone_offer)
        self.pages[4].offer_saved.connect(self._on_offer_saved)

        for page in self.pages.values():
            self.stack.addWidget(page)
        self._navigate(0)

    def _navigate(self, index: int, from_sidebar: bool = False):
        # Teklif formundan ayrılırken kaydedilmemiş değişiklik uyarısı
        current_widget = self.stack.currentWidget()
        current_idx    = next(
            (i for i, p in self.pages.items() if p is current_widget), None)
        if current_idx == 4 and index != 4 and from_sidebar:
            page = self.pages.get(4)
            if page and hasattr(page, "is_dirty") and page.is_dirty():
                ans = QMessageBox.question(
                    self, "Kaydedilmemiş Değişiklikler",
                    "Teklif formunda kaydedilmemiş değişiklikler var.\n"
                    "Çıkmak istediğinizden emin misiniz?\n"
                    "(Değişiklikler kaybolacak)",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No)
                if ans != QMessageBox.StandardButton.Yes:
                    # QPushButton tıklama anında kendi checked durumunu değiştirir.
                    # Navigasyon iptal edilirse görsel seçimi gerçek sayfaya geri al.
                    self._sync_sidebar_selection(current_idx)
                    return  # Sayfada kal
                # Onaylandı → formu sıfırla
                if hasattr(page, "_reset_to_new"):
                    page._reset_to_new()

        # Ayarlar sayfasından kaydedilmemiş değişikliklerle ayrılma uyarısı
        if current_idx == 5 and index != 5 and from_sidebar:
            spage = self.pages.get(5)
            if spage and hasattr(spage, "is_dirty") and spage.is_dirty():
                ans = QMessageBox.question(
                    self, "Kaydedilmemiş Ayarlar",
                    "Ayarlarda kaydedilmemiş değişiklikler var.\n"
                    "Kaydedilsin mi?\n"
                    "(Hayır derseniz yazdıklarınız formda kalır ama kaydedilmez)",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes)
                if ans == QMessageBox.StandardButton.Yes:
                    spage._save()

        self._sync_sidebar_selection(index)

        # Yeni Teklif sekmesine SOL MENÜDEN (sidebar) tıklandıysa ve önceden bir teklif varsa formu sıfırla
        # ("Düzenle" butonundan programlanarak gelindiyse sıfırlama YAPMA)
        if index == 4 and from_sidebar:
            page = self.pages.get(4)
            if page and getattr(page, "_current_offer_id", None) is not None:
                if hasattr(page, "_reset_to_new"):
                    page._reset_to_new()

        if index in self.pages:
            self.stack.setCurrentWidget(self.pages[index])
            page = self.pages[index]
            if hasattr(page, "on_enter"):
                page.on_enter()

    def _sync_sidebar_selection(self, active_index):
        """Sol menüde her zaman yalnızca aktif sayfanın seçili kalmasını sağlar."""
        for idx, card in self._btn_map.items():
            card.setChecked(idx == active_index)

    def _open_edit_offer(self, offer_id: int):
        self.pages[4].load_offer(offer_id)
        self._navigate(4)

    def _open_clone_offer(self, offer_id: int):
        self.pages[4].clone_offer(offer_id)
        self._navigate(4)
        self.show_status("Teklif kopyalandı — düzenleyip kaydedebilirsiniz.")

    def _on_offer_saved(self):
        # Teklif kaydedilince yedek al (arka planda)
        try:
            self._backup_svc.trigger_now(reason="teklif kaydı")
        except Exception as e:
            logger.debug("Teklif kaydı yedeği alınamadı: %s", e)
        self.show_status("Teklif başarıyla kaydedildi.")
        self._navigate(0)

    # ── Araçlar ──────────────────────────────────────────────────────────────

    def _open_excel_import(self, import_type: str = "customers"):
        """Penceresiz içe aktarma akışı: dosya seç → özet onayı → aktar."""
        from ui.utils.excel_import import run_import_flow, run_import_all_flow
        if import_type == "all":
            done = run_import_all_flow(self)
        else:
            done = run_import_flow(self, import_type)
        if done:
            page = self.stack.currentWidget()
            if hasattr(page, "on_enter"):
                page.on_enter()

    def _export_data(self, import_type: str):
        """Menüden doğrudan dışa aktarma — ara pencere açılmaz."""
        if import_type == "all":
            from ui.utils.excel_import import export_all_interactive
            export_all_interactive(self)
        else:
            from ui.utils.excel_import import export_data_interactive
            export_data_interactive(self, import_type)

    def _open_backup(self):
        from ui.dialogs.backup_manager import BackupDialog
        dlg = BackupDialog(self)
        dlg.settings_changed.connect(self._backup_svc.reload)
        dlg.exec()

    def _toggle_how_to_use(self):
        """F1: yardım penceresi açık ise kapat, kapalı ise aç (toggle)."""
        if self._help_dialog is not None and self._help_dialog.isVisible():
            self._help_dialog.close()
            self._help_dialog = None
        else:
            from ui.dialogs.help_dialogs import HowToUseDialog
            self._help_dialog = HowToUseDialog(self)
            self._help_dialog.finished.connect(lambda _: setattr(self, "_help_dialog", None))
            self._help_dialog.show()

    def _open_about(self):
        from ui.dialogs.help_dialogs import AboutDialog
        AboutDialog(self).exec()

    # ── Yedekleme servisi ─────────────────────────────────────────────────────

    def _start_backup_service(self):
        from ui.dialogs.backup_manager import AutoBackupService
        self._backup_svc = AutoBackupService(self)
        self._backup_svc.backup_done.connect(self._on_backup_done)
        self._backup_svc.backup_failed.connect(
            lambda e: logger.warning("Otomatik yedek başarısız: %s", e))

    def _on_backup_done(self, path: str):
        from datetime import datetime
        logger.info("Otomatik yedek: %s", path)
        self.show_status(f"Yedek alındı — {datetime.now().strftime('%H:%M')}")

    # ── Güncelleme kontrolü ──────────────────────────────────────────────────

    def _start_update_check(self):
        """Program açılınca arka planda güncelleme kontrolü başlatır."""
        try:
            from ui.utils.updater import start_startup_check
            self._update_checker = start_startup_check(self)
        except Exception as e:
            logger.debug("Güncelleme kontrolü başlatılamadı: %s", e)

    # ── StatusBar ────────────────────────────────────────────────────────────

    def show_status(self, message: str, timeout: int = 6000, level: str = "success"):
        from ui.utils.theme_manager import get_theme
        from core.constants import get_status_config
        t = get_theme()
        if level == "warning":
            warn = get_status_config()["Beklemede"]
            color, border = warn["fg"], warn["dot"]
        else:
            color = border = t['accent_green']
        self._status_lbl.setText(message)
        self._status_lbl.setFixedHeight(40 if message else 0)
        self._status_lbl.setStyleSheet(f"""
            QLabel#status_toast {{
                font-size: 10.5pt;
                font-weight: 500;
                color: {color};
                background: {t['bg_table_alt']};
                border-top: 2px solid {border};
                padding: 6px 16px;
            }}
        """)
        self._status_timer_id = getattr(self, "_status_timer_id", 0) + 1
        current_id = self._status_timer_id
        if timeout > 0:
            QTimer.singleShot(timeout, lambda: self._clear_status(current_id))

    def _clear_status(self, expected_id: int):
        if expected_id != getattr(self, "_status_timer_id", 0):
            return  # daha yeni bir mesaj geldi, bunu kapatma
        self._status_lbl.setText("")
        self._status_lbl.setFixedHeight(0)

    # ── Tema ─────────────────────────────────────────────────────────────────

    def _set_theme(self, mode: str):
        from ui.utils.theme_manager import set_theme_mode, get_theme
        set_theme_mode(mode)
        self._refresh_theme()
        labels = {"light": "Açık", "dark": "Koyu", "system": "Sistem"}
        self.show_status(f"Tema: {labels.get(mode, mode)}")
        logger.info("Tema değiştirildi: %s → %s", mode, get_theme()["name"])

    def _cycle_theme(self):
        from ui.utils.theme_manager import get_theme_mode
        order = ["light", "dark", "system"]
        cur = get_theme_mode()
        nxt = order[(order.index(cur) + 1) % 3] if cur in order else "light"
        self._set_theme(nxt)

    def _refresh_theme(self):
        from ui.utils.theme_manager import get_theme
        self._apply_theme()
        for idx, card in self._btn_map.items():
            card._apply_state()
        page = self.pages.get(4)
        if page:
            if hasattr(page, 'step_indicator'):
                page.step_indicator.set_step(page.stack.currentIndex())
            if hasattr(page, '_refresh_summary'):
                page._refresh_summary()
        if hasattr(self, "_sidebar_title_lbl"):
            self._sidebar_title_lbl.setStyleSheet(
                f"color:{_sidebar_text_color()};font-size:11pt;"
                "font-weight:bold;background:transparent;"
            )
        self._sync_theme_menu()

    def _sync_theme_menu(self):
        from ui.utils.theme_manager import get_theme_mode
        mode = get_theme_mode()
        for key, act in self._theme_actions.items():
            act.setChecked(key == mode)

    def _apply_theme(self):
        from ui.utils.theme_manager import build_stylesheet, get_theme
        self.setStyleSheet(build_stylesheet(get_theme()))
