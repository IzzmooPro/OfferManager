"""O1 — Arşiv PDF'i gerçek teklif numarasıyla adlandırılmalı.

_collect_data() teklife ÖNİZLEME numarasını koyar; OfferService.save() bunu
gerçek numarayla değiştirir (aynı nesne). Sayfadaki self._offer_no ise eski
önizleme değerinde kalıyordu ve arşiv PDF'i (PDF_DIR) o eski adla
yazılıyordu. Teklif silinince OfferService.delete gerçek numaraya bakıp
dosyayı bulamıyor, arşivde yetim dosya kalıyordu.

Ayrışma, Ayarlar'dan teklif öneki değiştirilip sayfaya sidebar'dan
dönülmediğinde ortaya çıkar.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from core.app_paths import CFG_PATH, PDF_DIR
from core.config import load_company_config, save_company_config
from database.db_manager import get_db
from services.offer_service import OfferService
from ui.create_offer_page import CreateOfferPage


class OfferArchiveNamingTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.db = get_db()
        cls.svc = OfferService()

    def setUp(self):
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM offer_items")
            conn.execute("DELETE FROM offers")
            conn.execute("DELETE FROM offer_counter")

        # Şirket ayarı paylaşımlı; testten sonra aynen geri yüklenir.
        self._cfg_yedegi = (CFG_PATH.read_bytes() if CFG_PATH.exists() else None)
        self.addCleanup(self._cfg_geri_yukle)

        PDF_DIR.mkdir(parents=True, exist_ok=True)
        self._arsiv_yedegi = set(PDF_DIR.glob("*.pdf"))
        self.addCleanup(self._arsiv_temizle)

        self._tmp = tempfile.TemporaryDirectory(prefix="oms_o1_")
        self.addCleanup(self._tmp.cleanup)
        self.cikti_yolu = str(Path(self._tmp.name) / "kullanici_kaydi.pdf")

        # Modal kutular ve dosya diyaloğu testte bloklamasın
        self._patch(QFileDialog, "getSaveFileName",
                    staticmethod(lambda *a, **k: (self.cikti_yolu, "")))
        self._patch(QMessageBox, "exec", lambda self_, *a, **k: 0)
        self._patch(QMessageBox, "warning")
        self._patch(QMessageBox, "information")
        self._patch(QMessageBox, "question")
        # Gerçek PDF üretimi yerine hafif dosya yazımı (odak: dosya ADI)
        self._patch("pdf.pdf_generator.generate_pdf",
                    yeni=lambda offer, out: Path(out).write_bytes(b"%PDF-1.4 test"))

    def _patch(self, hedef, ad=None, yeni=None):
        if isinstance(hedef, str):
            patcher = mock.patch(hedef, yeni) if yeni is not None else mock.patch(hedef)
        else:
            patcher = (mock.patch.object(hedef, ad, yeni) if yeni is not None
                       else mock.patch.object(hedef, ad))
        sahte = patcher.start()
        self.addCleanup(patcher.stop)
        return sahte

    def _cfg_geri_yukle(self):
        if self._cfg_yedegi is None:
            CFG_PATH.unlink(missing_ok=True)
        else:
            CFG_PATH.write_bytes(self._cfg_yedegi)

    def _arsiv_temizle(self):
        for p in PDF_DIR.glob("*.pdf"):
            if p not in self._arsiv_yedegi:
                p.unlink(missing_ok=True)

    # ── yardımcılar ──────────────────────────────────────────────────────

    def _onek_ayarla(self, onek: str):
        cfg = load_company_config()
        cfg["offer_prefix"] = onek
        save_company_config(cfg)

    def _hazir_sayfa(self, eski_onizleme: str) -> CreateOfferPage:
        from models.customer import Customer
        from services.customer_service import CustomerService
        musteri_id = CustomerService().add(Customer(company_name="O1 Test A.Ş."))

        page = CreateOfferPage()
        self.addCleanup(page.deleteLater)
        page._load_customers()
        for i in range(page.customer_combo.count()):
            if page.customer_combo.itemData(i) == musteri_id:
                page.customer_combo.setCurrentIndex(i)
                break
        self.assertNotEqual(page.company_edit.currentText(), "-- Müşteri Seçin --",
                            "test müşterisi seçilemedi")
        page._add_row(code="P-1", name="Ürün 1", qty=2, price=250.0,
                      currency="TL")
        page.validity_edit.setText("10")
        page.payment_edit.setText("30")
        # Sayfa ESKİ önekli önizleme numarasını taşıyor
        page._offer_no = eski_onizleme
        page.offer_no_lbl.setText(eski_onizleme)
        return page

    def _kayitli_teklif(self):
        """En son kaydedilen teklif. (_finish_offer sonunda _reset_to_new()
        çalıştığı için sayfadaki _current_offer_id sıfırlanmış olur.)"""
        teklifler = self.svc.get_all()
        self.assertTrue(teklifler, "teklif kaydedilmedi")
        return teklifler[0]

    def _kayitli_numara(self, page=None) -> str:
        return self._kayitli_teklif().offer_no

    def _reset_aninda_offer_no(self, page) -> list:
        """_reset_to_new() çağrılmadan HEMEN ÖNCEKİ self._offer_no değerini
        yakalar — kaydetme ile sıfırlama arasındaki gerçek durum budur."""
        yakalanan = []
        orijinal = page._reset_to_new

        def _sar():
            yakalanan.append(page._offer_no)
            orijinal()

        page._reset_to_new = _sar
        return yakalanan

    # ── testler ──────────────────────────────────────────────────────────

    def test_archive_uses_real_offer_no_after_prefix_change(self):
        self._onek_ayarla("ESKI")
        page = self._hazir_sayfa("ESKI-000001")
        self._onek_ayarla("YENI")          # kaydetmeden hemen önce değişti

        page._finish_offer()

        gercek = self._kayitli_numara(page)
        self.assertTrue(gercek.startswith("YENI-"),
                        f"kayıtlı numara yeni öneki kullanmıyor: {gercek}")
        self.assertTrue((PDF_DIR / f"{gercek}.pdf").exists(),
                        "arşiv PDF'i gerçek teklif numarasıyla oluşturulmadı")
        self.assertFalse((PDF_DIR / "ESKI-000001.pdf").exists(),
                         "arşiv PDF'i eski önizleme numarasıyla yazılmış")

    def test_page_offer_no_synced_with_saved_offer(self):
        self._onek_ayarla("ESKI")
        page = self._hazir_sayfa("ESKI-000001")
        self._onek_ayarla("YENI")
        yakalanan = self._reset_aninda_offer_no(page)

        page._finish_offer()

        gercek = self._kayitli_numara()
        self.assertEqual(yakalanan, [gercek],
                         "kayıttan sonra sayfa hâlâ eski önizleme "
                         "numarasını taşıyor")

    def test_delete_removes_archive_pdf(self):
        self._onek_ayarla("ESKI")
        page = self._hazir_sayfa("ESKI-000001")
        self._onek_ayarla("YENI")

        page._finish_offer()
        teklif = self._kayitli_teklif()
        arsiv = PDF_DIR / f"{teklif.offer_no}.pdf"
        self.assertTrue(arsiv.exists())

        self.svc.delete(teklif.id)
        self.assertFalse(arsiv.exists(),
                         "teklif silindi ama arşiv PDF'i yetim kaldı")

    def test_unchanged_prefix_flow_still_works(self):
        self._onek_ayarla("SNS")
        page = self._hazir_sayfa("SNS-000001")
        yakalanan = self._reset_aninda_offer_no(page)

        page._finish_offer()

        gercek = self._kayitli_numara()
        self.assertEqual(gercek, "SNS-000001")
        self.assertEqual(yakalanan, [gercek])
        self.assertTrue((PDF_DIR / f"{gercek}.pdf").exists())
        self.assertTrue(Path(self.cikti_yolu).exists(),
                        "kullanıcının seçtiği konuma PDF yazılmadı")

    def test_failed_save_leaves_preview_and_archive_untouched(self):
        self._onek_ayarla("SNS")
        page = self._hazir_sayfa("SNS-000009")
        onceki_arsiv = set(PDF_DIR.glob("*.pdf"))

        with mock.patch.object(OfferService, "save",
                               side_effect=RuntimeError("kayıt hatası")):
            page._finish_offer()

        self.assertEqual(page._offer_no, "SNS-000009",
                         "kayıt başarısızken önizleme numarası değişti")
        self.assertIsNone(page._current_offer_id)
        self.assertEqual(set(PDF_DIR.glob("*.pdf")), onceki_arsiv,
                         "kayıt başarısızken arşive dosya yazıldı")


if __name__ == "__main__":
    unittest.main(verbosity=2)
