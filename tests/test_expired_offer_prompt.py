"""O2 — Süresi dolan teklifler onaysız İptal edilmemeli.

Dashboard'a her girişte `auto_cancel_expired()` çalışıp süresi dolmuş
"Beklemede" teklifleri sessizce "İptal" yapıyordu: geri alınamaz, kullanıcıya
sorulmayan bir veri değişikliği. Yeni davranış: tek toplu onay sorusu,
onaysız hiçbir yazma yok, onay sonrası tek transaction'da güncelleme.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest
from datetime import date, timedelta
from unittest import mock

from PySide6.QtWidgets import QApplication, QMessageBox

from database.db_manager import get_db
from models.offer import Offer
from models.offer_item import OfferItem
from services.offer_service import OfferService
from ui.dashboard_page import DashboardPage


class ExpiredOfferPromptTests(unittest.TestCase):

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
        # Sorulan kutuyu yakala: hangi düğmeye basıldığını test belirler
        self.secim = {"buton": "leave", "yan_etki": None}   # leave|cancel|esc
        self.acilan = []
        self._patch_messagebox()

    def _patch_messagebox(self):
        secim, acilan = self.secim, self.acilan

        def sahte_exec(box, *a, **k):
            # YALNIZ toplu onay sorusu sayılır. Aynı akışta açılabilen güvenli
            # hata diyaloğu (R10-B) ayrı bir kutudur ve bu sayacı kirletmemeli.
            if box.windowTitle() != "Süresi Dolan Teklifler":
                return 0
            acilan.append(box)
            # Soru ile onay arasında dünya değişebilir (yarış senaryoları)
            if secim.get("yan_etki"):
                secim["yan_etki"]()
            butonlar = {b.text(): b for b in box.buttons()}
            if secim["buton"] == "cancel":
                box._secilen = butonlar.get("İptal Olarak İşaretle")
            elif secim["buton"] == "leave":
                box._secilen = butonlar.get("Şimdilik Dokunma")
            else:                              # Esc / X → hiçbir düğme
                box._secilen = None
            return 0

        p1 = mock.patch.object(QMessageBox, "exec", sahte_exec)
        p2 = mock.patch.object(QMessageBox, "clickedButton",
                               lambda box: getattr(box, "_secilen", None))
        for p in (p1, p2):
            p.start()
            self.addCleanup(p.stop)
        # Bilgi/uyarı kutuları da bloklamasın
        for ad in ("information", "warning", "critical", "question"):
            p = mock.patch.object(QMessageBox, ad)
            p.start()
            self.addCleanup(p.stop)

    # ── yardımcılar ──────────────────────────────────────────────────────

    def _teklif(self, gun_once: int, validity: str, status="Beklemede") -> int:
        o = Offer(
            company_name="O2 Test",
            date=(date.today() - timedelta(days=gun_once)).isoformat(),
            currency="TL", total_amount=100.0, validity=validity,
            payment_term="Peşin", status=status,
            items=[OfferItem(product_name="Ürün", quantity=1,
                             unit_price=100.0, total_price=100.0)])
        return self.svc.save(o)

    def _sayfa(self) -> DashboardPage:
        page = DashboardPage()
        self.addCleanup(page.deleteLater)
        return page

    def _durum(self, oid: int) -> str:
        return self.svc.get_by_id(oid).status

    # ── testler ──────────────────────────────────────────────────────────

    def test_entering_dashboard_does_not_change_status_silently(self):
        oid = self._teklif(30, "10 Gün")
        page = self._sayfa()
        self.secim["buton"] = "leave"

        page.on_enter()

        self.assertEqual(self._durum(oid), "Beklemede",
                         "dashboard açılışı teklifi onaysız değiştirdi")
        self.assertEqual(len(self.acilan), 1, "toplu onay sorusu gösterilmedi")

    def test_no_prompt_when_nothing_expired(self):
        oid = self._teklif(2, "30 Gün")
        page = self._sayfa()

        page.on_enter()

        self.assertEqual(self.acilan, [], "süresi dolan yokken soru çıktı")
        self.assertEqual(self._durum(oid), "Beklemede")

    def test_leave_alone_writes_nothing(self):
        oid = self._teklif(30, "10 Gün")
        page = self._sayfa()
        self.secim["buton"] = "leave"

        page.on_enter()

        self.assertEqual(self._durum(oid), "Beklemede")

    def test_escape_or_close_writes_nothing(self):
        oid = self._teklif(30, "10 Gün")
        page = self._sayfa()
        self.secim["buton"] = "esc"          # hiçbir düğmeye basılmadı

        page.on_enter()

        self.assertEqual(self._durum(oid), "Beklemede",
                         "Esc/X sonrası veritabanına yazıldı")

    def test_confirm_cancels_only_expired_pending(self):
        suresi_dolan = self._teklif(30, "10 Gün")
        gecerli = self._teklif(2, "30 Gün")
        onayli = self._teklif(30, "10 Gün", status="Onaylandı")
        bozuk = self._teklif(90, "Belirtilmemiş")
        page = self._sayfa()
        self.secim["buton"] = "cancel"

        page.on_enter()

        self.assertEqual(self._durum(suresi_dolan), "İptal")
        self.assertEqual(self._durum(gecerli), "Beklemede")
        self.assertEqual(self._durum(onayli), "Onaylandı")
        self.assertEqual(self._durum(bozuk), "Beklemede",
                         "geçerliliği çözümlenemeyen teklif iptal edildi")

    def test_prompt_message_mentions_count_and_offer_numbers(self):
        ids = [self._teklif(30, "10 Gün") for _ in range(3)]
        page = self._sayfa()
        self.secim["buton"] = "leave"

        page.on_enter()

        metin = self.acilan[0].text()
        self.assertIn("3", metin, f"teklif sayısı mesajda yok: {metin!r}")
        ilk_no = self.svc.get_by_id(ids[0]).offer_no
        self.assertIn(ilk_no, metin, f"teklif numarası mesajda yok: {metin!r}")

    def test_same_set_is_not_asked_again_in_session(self):
        self._teklif(30, "10 Gün")
        page = self._sayfa()
        self.secim["buton"] = "leave"

        page.on_enter()
        page.on_enter()
        page.on_enter()

        self.assertEqual(len(self.acilan), 1,
                         "aynı teklif kümesi için tekrar soruldu")

    def test_new_expired_offer_triggers_prompt_again(self):
        self._teklif(30, "10 Gün")
        page = self._sayfa()
        self.secim["buton"] = "leave"
        page.on_enter()
        self.assertEqual(len(self.acilan), 1)

        self._teklif(45, "5 Gün")            # sonradan süresi dolan yeni teklif
        page.on_enter()

        self.assertEqual(len(self.acilan), 2,
                         "yeni süresi dolmuş teklif için tekrar sorulmadı")

    def test_dashboard_refreshes_after_confirmation(self):
        oid = self._teklif(30, "10 Gün")
        page = self._sayfa()
        self.secim["buton"] = "cancel"

        page.on_enter()

        durumlar = [page._model.offer_at(r).status
                    for r in range(page._model.rowCount())]
        self.assertIn("İptal", durumlar,
                      f"tablo onay sonrası yenilenmedi: {durumlar}")
        self.assertEqual(self._durum(oid), "İptal")

    # ── Onay ile uygulama arasındaki yarış: servis yeniden doğrulamalı ──

    def _guncelle(self, oid: int, **alanlar):
        with self.db.transaction() as conn:
            for ad, deger in alanlar.items():
                conn.execute(f"UPDATE offers SET {ad}=? WHERE id=?", (deger, oid))

    def test_offer_not_cancelled_if_validity_extended_after_prompt(self):
        oid = self._teklif(30, "10 Gün")
        page = self._sayfa()
        self.secim["buton"] = "cancel"
        # Kullanıcı onaylarken geçerlilik ileri alınıyor (artık dolmamış)
        self.secim["yan_etki"] = lambda: self._guncelle(oid, validity="90 Gün")

        page.on_enter()

        self.assertEqual(self._durum(oid), "Beklemede",
                         "geçerliliği uzatılmış teklif yine de iptal edildi")

    def test_offer_not_cancelled_if_status_changed_after_prompt(self):
        oid = self._teklif(30, "10 Gün")
        page = self._sayfa()
        self.secim["buton"] = "cancel"
        self.secim["yan_etki"] = lambda: self._guncelle(oid, status="Onaylandı")

        page.on_enter()

        self.assertEqual(self._durum(oid), "Onaylandı",
                         "arada Onaylandı yapılan teklif iptal edildi")

    def test_service_ignores_ids_that_are_not_expired(self):
        # UI'dan gelen listeye körü körüne güvenilmemeli
        gecerli = self._teklif(2, "30 Gün")
        onayli = self._teklif(30, "10 Gün", status="Onaylandı")
        bozuk = self._teklif(90, "Belirtilmemiş")

        self.assertEqual(self.svc.cancel_expired([gecerli, onayli, bozuk]), 0)

        self.assertEqual(self._durum(gecerli), "Beklemede")
        self.assertEqual(self._durum(onayli), "Onaylandı")
        self.assertEqual(self._durum(bozuk), "Beklemede")

    # ── Yalnız YENİ teklifler sorulmalı ─────────────────────────────────

    def test_previously_declined_offer_is_excluded_from_new_prompt(self):
        a = self._teklif(30, "10 Gün")
        page = self._sayfa()
        self.secim["buton"] = "leave"
        page.on_enter()                       # A soruldu → reddedildi
        a_no = self.svc.get_by_id(a).offer_no

        b = self._teklif(45, "5 Gün")         # sonradan B'nin süresi doldu
        b_no = self.svc.get_by_id(b).offer_no
        self.secim["buton"] = "cancel"
        page.on_enter()

        metin = self.acilan[1].text()
        self.assertIn(b_no, metin, f"yeni teklif mesajda yok: {metin!r}")
        self.assertNotIn(a_no, metin,
                         f"daha önce reddedilen teklif yeniden soruldu: {metin!r}")
        self.assertIn("1", metin, f"sayı yalnız yeni kümeden olmalı: {metin!r}")
        self.assertEqual(self._durum(b), "İptal")
        self.assertEqual(self._durum(a), "Beklemede",
                         "reddedilen teklif toplu iptale dâhil edildi")

    # ── Hata sonrası yeniden deneme ─────────────────────────────────────

    def test_failed_cancel_can_be_retried_on_next_entry(self):
        oid = self._teklif(30, "10 Gün")
        page = self._sayfa()
        self.secim["buton"] = "cancel"

        with mock.patch.object(OfferService, "cancel_expired",
                               side_effect=RuntimeError("veritabanı hatası")):
            page.on_enter()
        self.assertEqual(len(self.acilan), 1)
        self.assertEqual(self._durum(oid), "Beklemede")

        page.on_enter()                       # aynı küme yeniden sorulmalı
        self.assertEqual(len(self.acilan), 2,
                         "hatadan sonra aynı küme tekrar sorulmadı")
        self.assertEqual(self._durum(oid), "İptal")

    def test_successful_cancel_is_not_asked_again(self):
        self._teklif(30, "10 Gün")
        page = self._sayfa()
        self.secim["buton"] = "cancel"

        page.on_enter()
        page.on_enter()

        self.assertEqual(len(self.acilan), 1,
                         "başarıyla iptal edilen küme tekrar soruldu")

    def test_existing_filter_behaviour_still_works(self):
        self._teklif(2, "30 Gün")
        self._teklif(2, "30 Gün")
        page = self._sayfa()
        page.on_enter()
        self.assertEqual(page._model.rowCount(), 2)

        page._set_filter("Onaylandı")
        self.assertEqual(page._model.rowCount(), 0)
        page._set_filter("Tümü")
        self.assertEqual(page._model.rowCount(), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
