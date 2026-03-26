"""Dashboard — istatistikler + teklifler tablosu."""
import logging, os
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidgetItem, QFrame, QLineEdit, QMessageBox, QMenu, QFileDialog
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QBrush
from services.product_service  import ProductService
from services.customer_service import CustomerService
from services.offer_service    import OfferService
from ui._resizable_table import ResizableTable
from ui._animated_card   import AnimatedCard

logger  = logging.getLogger("dashboard")
from constants import SYM_MAP, STATUS_CONFIG, STATUS_ORDER


# ── Basit İstatistik Kartı ───────────────────────────────────────────────────
class StatCard(AnimatedCard):
    def __init__(self, title: str, accent: str):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 14, 20, 14)
        lay.setSpacing(4)
        self.value_lbl = QLabel("0")
        self.value_lbl.setObjectName("card_value")
        self.value_lbl.setStyleSheet(
            f"font-size:21pt;font-weight:bold;color:{accent};background:transparent;")
        title_lbl = QLabel(title)
        title_lbl.setObjectName("card_label")
        lay.addWidget(self.value_lbl)
        lay.addWidget(title_lbl)

    def set_value(self, v): self.value_lbl.setText(str(v))


# ── Teklif Durum Kartı ───────────────────────────────────────────────────────
class OfferStatCard(AnimatedCard):
    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 14, 20, 14)
        lay.setSpacing(6)

        title = QLabel("Teklifler")
        title.setObjectName("card_label")
        lay.addWidget(title)

        row = QHBoxLayout(); row.setSpacing(16)
        self._cells = {}
        for status, color in [("Beklemede","#f59e0b"),("Onaylandı","#10b981"),("İptal","#ef4444")]:
            col = QVBoxLayout(); col.setSpacing(1)
            val = QLabel("0")
            val.setStyleSheet(f"font-size:15pt;font-weight:700;color:{color};background:transparent;")
            lbl = QLabel(status)
            lbl.setStyleSheet("font-size:8pt;color:#999;background:transparent;")
            col.addWidget(val); col.addWidget(lbl)
            row.addLayout(col)
            self._cells[status] = val
        row.addStretch()
        lay.addLayout(row)

    def set_values(self, counts: dict):
        for s, lbl in self._cells.items():
            lbl.setText(str(counts.get(s, 0)))


# ── Dashboard ────────────────────────────────────────────────────────────────
class DashboardPage(QWidget):
    edit_offer_requested = Signal(int)

    def __init__(self):
        super().__init__()
        self.svc_p  = ProductService()
        self.svc_c  = CustomerService()
        self.svc_o  = OfferService()
        self._offers = []
        self._active_filter = "Tümü"
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 20, 16, 16)
        lay.setSpacing(20)

        # Başlık
        title = QLabel("Teklifler")
        title.setStyleSheet("font-size:14pt;font-weight:700;")
        lay.addWidget(title)

        # ── Stat kartları ─────────────────────────────────────────────────
        cards = QHBoxLayout(); cards.setSpacing(14)
        self.card_c = StatCard("Toplam Müşteri", "#e94560")
        self.card_p = StatCard("Toplam Ürün",    "#3a6fd8")
        self.card_offers = OfferStatCard()
        for c in [self.card_c, self.card_p, self.card_offers]:
            cards.addWidget(c, 1)  # stretch=1 → eşit genişlik
        lay.addLayout(cards)

        # ── Teklifler başlığı ─────────────────────────────────────────────
        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("border:none;background:#e8eef4;max-height:1px;")
        lay.addWidget(sep)

        hdr = QHBoxLayout()
        tl = QLabel("Teklifler")
        tl.setStyleSheet("font-size:10pt;font-weight:700;")
        hdr.addWidget(tl)
        hdr.addStretch()
        lay.addLayout(hdr)

        # ── Toolbar ───────────────────────────────────────────────────────
        tb_lay = QHBoxLayout(); tb_lay.setSpacing(8)

        # Arama
        self.search = QLineEdit()
        self.search.setPlaceholderText("Ara: teklif no veya firma...")
        self.search.setMinimumHeight(32)
        self.search.setMinimumWidth(220)
        self.search.textChanged.connect(lambda t: self._load(t))
        tb_lay.addWidget(self.search)

        # Durum filtre dropdown butonu
        self.filter_btn = QPushButton("Durum: Tümü  ▾")
        self.filter_btn.setObjectName("filter_btn")
        self.filter_btn.setMinimumHeight(32)
        self.filter_btn.setFixedWidth(180)
        self.filter_btn.clicked.connect(self._show_filter_menu)
        tb_lay.addWidget(self.filter_btn)

        tb_lay.addStretch()

        # Eylem butonları — Chrome sekme tarzı, bitişik grup (spacing=0)
        btn_group = QHBoxLayout()
        btn_group.setSpacing(0)
        btn_group.setContentsMargins(0, 0, 0, 0)
        _btn_defs = [
            ("Düzenle", self._edit,          "tab_btn_edit"),
            ("Durum",   self._change_status, "tab_btn_status"),
            ("PDF",     self._gen_pdf,       "tab_btn_pdf"),
            ("Sil",     self._delete,        "tab_btn_delete"),
        ]
        for i, (text, slot, obj) in enumerate(_btn_defs):
            b = QPushButton(text)
            b.setObjectName(obj)
            b.setMinimumHeight(34)
            b.setMinimumWidth(76)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(slot)
            btn_group.addWidget(b)
            if text == "Durum": self._status_btn = b
        tb_lay.addLayout(btn_group)

        lay.addLayout(tb_lay)

        # ── Tablo ─────────────────────────────────────────────────────────
        self.table = ResizableTable()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(
            ["Teklif No", "Firma", "Tarih", "Para Birimi", "Toplam", "Durum"])
        self.table.setup_columns([
            ('interactive', 155),
            ('stretch',     None),
            ('interactive', 95),
            ('interactive', 85),
            ('interactive', 140),
            ('interactive', 115),
        ])
        self.table.setEditTriggers(self.table.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(self.table.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(self.table.SelectionMode.ExtendedSelection)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.doubleClicked.connect(self._edit)
        self.table.on_edit   = self._edit
        self.table.on_delete = self._delete
        self.table.custom_context_menu = self._context_menu
        lay.addWidget(self.table)

    # ── Filtre dropdown ──────────────────────────────────────────────────────

    def _show_filter_menu(self):
        menu = QMenu(self)
        for s in ["Tümü"] + STATUS_ORDER:
            act = menu.addAction(s)
            act.setCheckable(True)
            act.setChecked(s == self._active_filter)
            act.triggered.connect(lambda _, st=s: self._set_filter(st))
        menu.exec(self.filter_btn.mapToGlobal(
            self.filter_btn.rect().bottomLeft()))

    def _set_filter(self, status):
        self._active_filter = status
        self.filter_btn.setText(f"Durum: {status}  ▾")
        self._load(self.search.text())

    # ── Veri ────────────────────────────────────────────────────────────────

    def _load(self, keyword=""):
        logger.debug("Dashboard yenileniyor...")
        try:
            all_offers = self.svc_o.get_all()
            if keyword:
                kw = keyword.lower()
                all_offers = [o for o in all_offers
                              if kw in (o.get("offer_no") or "").lower()
                              or kw in (o.get("company_name") or "").lower()]
            if self._active_filter != "Tümü":
                all_offers = [o for o in all_offers
                              if (o.get("status") or "Beklemede") == self._active_filter]
            self._fill_table(all_offers)
        except Exception as e:
            logger.error("Dashboard yenileme hatası: %s", e, exc_info=True)

    def _fill_table(self, offers: list):
        self._offers = offers
        self.table.setRowCount(len(self._offers))
        for row, o in enumerate(self._offers):
            sym    = SYM_MAP.get(o.get("currency", "EUR"), "€")
            status = o.get("status") or "Beklemede"
            cfg    = STATUS_CONFIG.get(status, STATUS_CONFIG["Beklemede"])
            self.table.setRowHeight(row, 34)
            for col, val in enumerate([
                o.get("offer_no", ""),
                o.get("company_name") or "",
                o.get("date", ""),
                o.get("currency", ""),
            ]):
                self.table.setItem(row, col, QTableWidgetItem(val))
            ti = QTableWidgetItem(f"{o.get('total_amount', 0):,.2f} {sym}")
            ti.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row, 4, ti)
            # Durum badge — renkli arka plan
            si = QTableWidgetItem(f"  {status}")
            si.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            si.setForeground(QBrush(QColor(cfg["fg"])))
            si.setBackground(QBrush(QColor(cfg["bg"])))
            self.table.setItem(row, 5, si)

    def on_enter(self):
        try:
            all_o = self.svc_o.get_all()
            counts = {s: 0 for s in STATUS_ORDER}
            for o in all_o:
                st = o.get("status") or "Beklemede"
                if st in counts: counts[st] += 1
            self.card_p.set_value(self.svc_p.count())
            self.card_c.set_value(self.svc_c.count())
            self.card_offers.set_values(counts)
            # Tabloyu aynı veriyle doldur — ikinci DB sorgusu gereksiz
            kw = self.search.text()
            if kw:
                kw_l = kw.lower()
                filtered = [o for o in all_o
                            if kw_l in (o.get("offer_no") or "").lower()
                            or kw_l in (o.get("company_name") or "").lower()]
            else:
                filtered = all_o
            if self._active_filter != "Tümü":
                filtered = [o for o in filtered
                            if (o.get("status") or "Beklemede") == self._active_filter]
            self._fill_table(filtered)
        except Exception as e:
            logger.error("Dashboard yenileme hatası: %s", e, exc_info=True)

    # ── Yardımcılar ──────────────────────────────────────────────────────────

    def _selected(self):
        """Tek seçili teklif (durum değiştirme, düzenleme için).
        Birden fazla satır seçiliyse işlem yapmaz — kullanıcıyı uyarır."""
        rows = sorted(set(idx.row() for idx in self.table.selectedIndexes()))
        if len(rows) == 1:
            r = rows[0]
            return self._offers[r] if 0 <= r < len(self._offers) else None
        return None  # 0 veya 2+ satır → None

    def _selected_all(self):
        """Tüm seçili teklifler (toplu işlemler için)."""
        rows = sorted(set(idx.row() for idx in self.table.selectedIndexes()))
        return [self._offers[r] for r in rows if 0 <= r < len(self._offers)]

    def _context_menu(self, pos):
        o = self._selected()
        if not o: return
        menu = QMenu(self)
        menu.addAction("Düzenle",     self._edit)
        sub = menu.addMenu("Durum")
        for s in STATUS_ORDER:
            act = sub.addAction(s)
            act.setCheckable(True)
            act.setChecked((o.get("status") or "Beklemede") == s)
            act.triggered.connect(lambda _, st=s: self._set_status(st))
        menu.addSeparator()
        menu.addAction("PDF Oluştur", self._gen_pdf)
        menu.addSeparator()
        menu.addAction("Sil",         self._delete)
        menu.exec(self.table.viewport().mapToGlobal(pos))

    # ── Eylemler ─────────────────────────────────────────────────────────────

    def _edit(self):
        o = self._selected()
        if not o:
            QMessageBox.information(self, "Bilgi", "Lütfen bir teklif seçin."); return
        self.edit_offer_requested.emit(o["id"])

    def _change_status(self):
        o = self._selected()
        if not o:
            QMessageBox.information(self, "Bilgi", "Lütfen bir teklif seçin."); return
        current = o.get("status") or "Beklemede"
        menu = QMenu(self)
        for s in STATUS_ORDER:
            if s == current:
                continue  # Mevcut durumu gösterme
            act = menu.addAction(s)
            act.triggered.connect(lambda _, st=s: self._set_status(st))
        menu.exec(self._status_btn.mapToGlobal(
            self._status_btn.rect().bottomLeft()))

    def _set_status(self, new_status):
        o = self._selected()
        if not o: return
        try:
            self.svc_o.update_status(o["id"], new_status)
            self.on_enter()
        except Exception as e:
            QMessageBox.warning(self, "Hata", f"Durum güncellenemedi:\n{e}")

    # ── Export ────────────────────────────────────────────────────────────────
    def _do_export(self, fmt: str):
        offers = self._offers
        if not offers:
            QMessageBox.information(self, "Bilgi", "Dışa aktarılacak teklif yok."); return
        import datetime
        default_name = f"teklifler_{datetime.date.today().strftime('%Y%m%d')}.{'xlsx' if fmt=='excel' else 'csv'}"
        filt = "Excel Dosyası (*.xlsx)" if fmt == "excel" else "CSV Dosyası (*.csv)"
        path, _ = QFileDialog.getSaveFileName(self, "Kaydet", default_name, filt)
        if not path: return
        try:
            from services.export_service import export_excel, export_csv
            out = export_excel(offers, path) if fmt == "excel" else export_csv(offers, path)
            QMessageBox.information(self, "Tamamlandı",
                f"{len(offers)} teklif dışa aktarıldı.\n{out}")
        except Exception as e:
            QMessageBox.warning(self, "Hata", f"Export hatası:\n{e}")

    def _gen_pdf(self):
        offers = self._selected_all()
        if not offers:
            QMessageBox.information(self, "Bilgi", "Lütfen en az bir teklif seçin."); return
        from pdf.pdf_generator import generate_pdf
        from app_paths import PDF_DIR
        out_dir = PDF_DIR
        out_dir.mkdir(parents=True, exist_ok=True)
        generated, errors = [], []
        for o in offers:
            try:
                offer_data = self.svc_o.get_by_id(o["id"])
                out_path   = str(out_dir / f"{offer_data['offer_no']}.pdf")
                generate_pdf(offer_data, out_path)
                generated.append(out_path)
            except Exception as e:
                errors.append(f"{o.get('offer_no','?')}: {e}")
        if errors:
            QMessageBox.warning(self, "Hata", "Bazı PDF'ler oluşturulamadı:\n" + "\n".join(errors))
        if generated:
            n = len(generated)
            if n == 1:
                box = QMessageBox(self)
                box.setWindowTitle("PDF Oluşturuldu")
                box.setText(f"PDF kaydedildi:\n{generated[0]}")
                btn_preview = box.addButton("Önizle",   QMessageBox.ButtonRole.AcceptRole)
                btn_open    = box.addButton("Aç",       QMessageBox.ButtonRole.ActionRole)
                btn_close   = box.addButton("Kapat",    QMessageBox.ButtonRole.RejectRole)
                box.exec()
                clicked = box.clickedButton()
                if clicked == btn_preview:
                    from ui.pdf_preview_dialog import PdfPreviewDialog
                    dlg = PdfPreviewDialog(generated[0], self)
                    dlg.exec()
                elif clicked == btn_open:
                    self._open_file(generated[0])
            else:
                if QMessageBox.information(self, "PDF Oluşturuldu",
                        f"{n} PDF oluşturuldu.\n\nHepsini açmak ister misiniz?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                ) == QMessageBox.StandardButton.Yes:
                    for p in generated:
                        self._open_file(p)

    def _delete(self):
        offers = self._selected_all()
        if not offers:
            QMessageBox.information(self, "Bilgi", "Lütfen en az bir teklif seçin."); return
        n = len(offers)
        msg = (f"Seçili {n} teklif silinsin mi?" if n > 1
               else f"'{offers[0]['offer_no']}' silinsin mi?")
        if QMessageBox.question(self, "Onay", msg,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) == QMessageBox.StandardButton.Yes:
            errors = []
            for o in offers:
                try: self.svc_o.delete(o["id"])
                except Exception as e: errors.append(str(e))
            if errors:
                QMessageBox.warning(self, "Hata", "Bazı teklifler silinemedi:\n" + "\n".join(errors))
            self.on_enter()

    def _open_file(self, path):
        os.startfile(path)
