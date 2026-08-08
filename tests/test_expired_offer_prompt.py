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


class _TeklifTemel(unittest.TestCase):
    """Ortak fikstür: izole DB, sahte onay kutusu ve teklif yardımcıları."""

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


class ExpiredOfferPromptTests(_TeklifTemel):
    """O2 — onaysız iptal yok; toplu onay sözleşmesi."""

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


class AcilisSirasiTests(_TeklifTemel):
    """Açılış bildirimleri SPLASH ÜZERİNDE değil, ana pencere görünürken.

    Kök neden: `MainWindow.__init__ → _load_pages → _navigate(0) →
    DashboardPage.on_enter → _prompt_expired_offers` zinciri `main.py`
    içindeki `window.show()` çağrısından ÖNCE çalışıyordu; modal kutu
    "Arayüz oluşturuluyor…" splash'inin üzerinde açılıyordu.

    Sözleşme: veri yüklemesi açılışta yapılır, **bildirimler ertelenir** ve
    ana pencere görünür olduktan sonra TAM BİR KEZ gösterilir.
    """

    def setUp(self):
        super().setUp()
        # `MainWindow` gerçek updater ağ thread'i ve otomatik yedek
        # zamanlayıcısı başlatır. Bu testler AÇILIŞ BİLDİRİM SIRASINI ölçer;
        # o yan etkiler kapatılmazsa arka planda kalan thread'ler test
        # oturumunu askıda bırakır (ölçüldü: tam paket ~4 dk yerine kilitlendi).
        from ui.dialogs import backup_manager as bm
        import ui.utils.updater as upd
        for hedef, ad, yeni in (
                (bm.AutoBackupService, "_apply", lambda s: None),
                (bm.AutoBackupService, "trigger_now",
                 lambda s, reason="": None),
                (upd, "start_startup_check", staticmethod(lambda parent: None))):
            p = mock.patch.object(hedef, ad, yeni)
            p.start()
            self.addCleanup(p.stop)

    def _ana_pencere(self):
        """Gerçek `MainWindow` — açılış zincirini olduğu gibi çalıştırır.

        Pencere KENDİ testimizin içinde yok edilir. `deleteLater`'ı kuyrukta
        bırakmak, yok etme işini BAŞKA bir testin `processEvents()` turuna
        sarkıtır; ölçüldü: tam paket o noktada kilitleniyordu.
        """
        from ui.main_window import MainWindow
        w = MainWindow()

        def _yok_et():
            from PySide6.QtCore import QCoreApplication, QEvent
            w.hide()
            w._acilis_bildirim_zamanlayici.stop()
            w.deleteLater()
            # Normal processEvents(), DeferredDelete olayını tek başına
            # tüketme garantisi vermez. Pencereyi ve sahip olduğu timer'ları
            # bu testin sınırında kesin olarak yok et; sonraki testin olay
            # döngüsüne hiçbir UI nesnesi sarkmasın.
            QCoreApplication.sendPostedEvents(
                w, QEvent.Type.DeferredDelete)
            self.app.processEvents()

        self.addCleanup(_yok_et)
        return w

    # ── 1-2: oluşturma sırasında modal yok, veri yüklemesi var ──────────
    def test_pencere_olusturulurken_modal_acilmaz(self):
        self._teklif(60, "30 Gün")
        self.secim["buton"] = "cancel"
        w = self._ana_pencere()
        self.assertEqual(len(self.acilan), 0,
                         "modal ana pencere görünmeden açıldı (splash üzerinde)")

    def test_pencere_olusturulurken_dashboard_verisi_yuklenir(self):
        self._teklif(2, "30 Gün")
        self._teklif(2, "30 Gün")
        w = self._ana_pencere()
        self.assertEqual(w.pages[0]._model.rowCount(), 2,
                         "açılışta Dashboard verisi yüklenmedi")

    # ── 3-4: görünürlük sırası ──────────────────────────────────────────
    def test_pencere_gorunmeden_bildirim_gosterilmez(self):
        self._teklif(60, "30 Gün")
        self.secim["buton"] = "cancel"
        w = self._ana_pencere()
        # show() ÇAĞRILMADI → açılış bildirimi çalışsa bile kutu açılmamalı
        w.acilis_bildirimlerini_goster()
        self.assertEqual(len(self.acilan), 0,
                         "pencere görünür değilken modal açıldı")

    def test_pencere_gorununce_bildirim_gosterilir(self):
        oid = self._teklif(60, "30 Gün")
        self.secim["buton"] = "cancel"
        w = self._ana_pencere()
        w.show()
        self.assertEqual(len(self.acilan), 0, "show() modalı erken tetikledi")
        w.acilis_bildirimlerini_goster()
        self.assertEqual(len(self.acilan), 1,
                         "ana pencere görünürken açılış bildirimi gelmedi")
        self.assertEqual(self._durum(oid), "İptal")

    # ── 5: idempotent ───────────────────────────────────────────────────
    def test_acilis_bildirimi_iki_cagride_tek_kutu(self):
        self._teklif(60, "30 Gün")
        self.secim["buton"] = "leave"
        w = self._ana_pencere()
        w.show()
        w.acilis_bildirimlerini_goster()
        w.acilis_bildirimlerini_goster()
        self.assertEqual(len(self.acilan), 1,
                         "açılış bildirimi iki kez kutu açtı")

    # ── 6: kapanıyorsa açma ─────────────────────────────────────────────
    def test_kapanan_pencerede_bildirim_gosterilmez(self):
        self._teklif(60, "30 Gün")
        self.secim["buton"] = "cancel"
        w = self._ana_pencere()
        w.show()
        w._shutdown_prepared = True          # kapanış hazırlığı başladı
        w.acilis_bildirimlerini_goster()
        self.assertEqual(len(self.acilan), 0,
                         "kapanan pencerede modal açıldı")

    # ── 7: süresi dolan yoksa kutu yok ──────────────────────────────────
    def test_suresi_dolan_yoksa_kutu_acilmaz(self):
        self._teklif(2, "30 Gün")
        w = self._ana_pencere()
        w.show()
        w.acilis_bildirimlerini_goster()
        self.assertEqual(len(self.acilan), 0)

    # ── 8: reddetme DB'ye yazmaz ────────────────────────────────────────
    def test_acilista_dokunma_db_yazmaz(self):
        oid = self._teklif(60, "30 Gün")
        for secim in ("leave", "esc"):
            with self.subTest(secim=secim):
                self.secim["buton"] = secim
                w = self._ana_pencere()
                w.show()
                w.acilis_bildirimlerini_goster()
                self.assertEqual(self._durum(oid), "Beklemede",
                                 f"{secim} sonrası DB değişti")

    # ── 9: onay sonrası tablo/istatistik yenilenir ──────────────────────
    def test_acilis_onayi_sonrasi_tablo_yenilenir(self):
        self._teklif(60, "30 Gün")
        self.secim["buton"] = "cancel"
        w = self._ana_pencere()
        w.show()
        w.acilis_bildirimlerini_goster()
        sayfa = w.pages[0]
        durumlar = {sayfa._model.data(sayfa._model.index(r, 6))
                    for r in range(sayfa._model.rowCount())}
        self.assertNotIn("Beklemede", durumlar,
                         "onay sonrası tablo yenilenmedi")

    # ── 10-12: sonraki gezinmeler mevcut davranışı korur ────────────────
    def test_sonraki_gezinme_normal_davranisi_korur(self):
        self._teklif(60, "30 Gün")
        self.secim["buton"] = "leave"
        w = self._ana_pencere()
        w.show()
        w.acilis_bildirimlerini_goster()
        self.assertEqual(len(self.acilan), 1)
        # Aynı küme: oturumda tekrar sorulmaz
        w._navigate(0)
        self.assertEqual(len(self.acilan), 1,
                         "aynı teklif kümesi oturumda tekrar soruldu")
        # Yeni süresi dolmuş teklif: tekrar sorulur
        self._teklif(90, "30 Gün")
        w._navigate(0)
        self.assertEqual(len(self.acilan), 2,
                         "yeni süresi dolan teklif için tekrar sorulmadı")

    # ── 13: yakında dolacak bildirimi de görünür pencere sonrasında ─────
    def test_yakinda_dolacak_bildirimi_pencere_sonrasinda(self):
        self._teklif(28, "30 Gün")           # 2 gün kaldı
        mesajlar = []
        w = self._ana_pencere()
        w.show_status = lambda m, level=None: mesajlar.append(m)
        self.assertEqual(mesajlar, [],
                         "yaklaşan süre bildirimi splash arkasında gösterildi")
        w.show()
        w.acilis_bildirimlerini_goster()
        self.assertTrue(any("3 gün içinde dolacak" in m for m in mesajlar),
                        f"yaklaşan süre bildirimi hiç gösterilmedi: {mesajlar}")

    # ── 14: sabit gecikme/sleep hilesi yok ──────────────────────────────
    def test_sabit_gecikme_kullanilmiyor(self):
        import inspect
        from pathlib import Path
        from ui.main_window import MainWindow
        # `main` import edilmez: modül importta global sys.excepthook'u gerçek
        # modal hata penceresine bağlar ve sonraki Qt testlerini kilitleyebilir.
        ana_kaynak = (Path(__file__).resolve().parents[1] / "main.py").read_text(
            encoding="utf-8")
        pencere_kaynak = inspect.getsource(MainWindow.acilis_bildirimlerini_planla)
        self.assertIn("fade.finished", ana_kaynak,
                      "splash kapanışı gerçek `finished` sinyaline bağlı değil")
        self.assertIn("window.acilis_bildirimlerini_planla", ana_kaynak)
        self.assertIn(".start(0)", pencere_kaynak.replace(" ", ""),
                      "bildirim sonraki event-loop turuna bırakılmamış")
        self.assertNotIn("singleShot", ana_kaynak,
                         "sahipsiz callback ana olay kuyruğuna bırakılmamalı")


if __name__ == "__main__":
    unittest.main(verbosity=2)
