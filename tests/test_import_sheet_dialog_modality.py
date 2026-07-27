"""O16 — çok sayfalı XLSX'te sayfa seçim diyaloğu ilerleme penceresince bloklanıyor.

Paketli v4.0 EXE üzerinde ölçüm (manuel D turu, PID 17452):

    hwnd=723424   enabled=1  'İçe Aktarma'          (QProgressDialog, WindowModal)
    hwnd=4459322  enabled=0  'Çalışma Sayfası Seç'  (QInputDialog — TIKLANAMIYOR)
    hwnd=1707316  enabled=0  'Teklif Yönetim Sistemi'

`run_import_flow` ilerleme penceresini `_read_file`'tan ÖNCE açıyor; `_read_file`
içindeki `_sayfa_sordur` ise aynı parent'a yeni bir modal pencere açıyor. Windows
tarafında bu pencere devre dışı bırakılıyor: kullanıcı soruyu görüyor ama
yanıtlayamıyor, `getItem` kendi olay döngüsünde beklediği için içe aktarma
süresiz kilitleniyor.

Bu dosya O15 testlerinden FARKLI olarak `QInputDialog.getItem`'i MOCK'LAMAZ;
gerçek `QApplication`, gerçek modal pencereler ve gerçek olay döngüsü kullanır.
Diyaloglar bir `QTimer` sürücüsüyle denetlenir; her testte güvenlik zaman aşımı
vardır, akış takılırsa test açıkça BAŞARISIZ olur (asılı kalmaz).

Sözleşme:
  * Sayfa seçim diyaloğu açıkken BAŞKA görünür modal pencere OLMAMALI.
  * Kullanıcı sayfayı seçebilmeli; yalnız seçilen sayfa aktarılmalı.
  * İptalde DB yazımı, hata kutusu ve yarım aktarım OLMAMALI.
  * Tek sayfalı XLSX ve CSV akışında diyalog hiç açılmamalı.
"""
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from openpyxl import Workbook
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (QApplication, QComboBox, QDialogButtonBox,
                               QInputDialog, QMessageBox, QWidget)

from database.db_manager import get_db
from ui.utils import excel_import as ei

U_BAS = ["Ürün Kodu", "Ürün Adı", "Fiyat"]
M_BAS = ["Firma Adı", "Telefon"]

ZAMAN_ASIMI_MS = 15000     # güvenlik: akış takılırsa test başarısız olsun
SURUCU_ARALIK_MS = 25


class _Sonuc:
    """Sürücünün topladığı gözlemler."""

    def __init__(self):
        self.sayfa_diyalogu_gorundu = False
        self.engelleyen_modaller = None     # sayfa diyaloğu anındaki ölçüm
        self.sunulan_secenekler = []
        self.mesaj_kutulari = []            # (baslik, metin)
        self.zaman_asimi = False


class _Temel(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.db = get_db()
        self._tmp = TemporaryDirectory(prefix="o16t_", ignore_cleanup_errors=True)
        self.addCleanup(self._tmp.cleanup)
        self.kok = Path(self._tmp.name)
        self._sayac = 0
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM products")
            conn.execute("DELETE FROM customers")
        self.parent = QWidget()
        self.parent.setWindowTitle("Test Ana Pencere")
        self.parent.show()
        self.addCleanup(self._parent_kapat)

    def _parent_kapat(self):
        self.parent.close()
        self.parent.deleteLater()
        QApplication.processEvents()

    # ── yardımcılar ─────────────────────────────────────────────────────────
    def _xlsx(self, sayfalar, gizli=()):
        self._sayac += 1
        wb = Workbook()
        wb.remove(wb.active)
        for ad, satirlar in sayfalar:
            ws = wb.create_sheet(ad)
            for s in satirlar:
                ws.append(s)
            if ad in gizli:
                ws.sheet_state = "hidden"
        yol = self.kok / f"o16_{self._sayac}.xlsx"
        wb.save(yol)
        return yol

    def _iki_sayfali_urun(self):
        return self._xlsx([
            ("SECILEN", [U_BAS, ["SEC-1", "Secilen Bir", 10],
                         ["SEC-2", "Secilen Iki", 20]]),
            ("SECILMEYEN", [U_BAS, ["ATLA-1", "Atlanan Bir", 30]]),
        ])

    def _iki_sayfali_musteri(self):
        return self._xlsx([
            ("SECILEN", [M_BAS, ["Secilen Firma", "111"]]),
            ("SECILMEYEN", [M_BAS, ["Atlanan Firma", "222"]]),
        ])

    @staticmethod
    def _gorunur_modaller(haric):
        """`haric` dışındaki GÖRÜNÜR ve modal üst düzey pencereler."""
        return [w for w in QApplication.topLevelWidgets()
                if w is not haric and w.isVisible() and w.isModal()]

    def _akisi_calistir(self, yol, tur, sayfa_secimi="SECILEN",
                        iptal=False, onayla=True):
        """`run_import_flow`'u GERÇEK diyaloglarla çalıştırır.

        Yalnız dosya seçme diyaloğu yamalanır (sayfa diyaloğu DEĞİL).
        """
        sonuc = _Sonuc()
        durum = {"bitti": False}

        def _surucu():
            if durum["bitti"]:
                return
            for w in QApplication.topLevelWidgets():
                if not w.isVisible():
                    continue
                if isinstance(w, QInputDialog):
                    if not sonuc.sayfa_diyalogu_gorundu:
                        sonuc.sayfa_diyalogu_gorundu = True
                        # KRİTİK ÖLÇÜM: bu anda başka modal pencere var mı?
                        sonuc.engelleyen_modaller = [
                            x.windowTitle() for x in self._gorunur_modaller(w)]
                        kutu = w.findChild(QComboBox)
                        if kutu is not None:
                            sonuc.sunulan_secenekler = [
                                kutu.itemText(i) for i in range(kutu.count())]
                            if not iptal:
                                for i in range(kutu.count()):
                                    if kutu.itemText(i).startswith(sayfa_secimi):
                                        kutu.setCurrentIndex(i)
                                        break
                        if iptal:
                            w.reject()
                        else:
                            w.accept()
                    return
                if isinstance(w, QMessageBox):
                    sonuc.mesaj_kutulari.append((w.windowTitle(), w.text()))
                    hedef = None
                    for d in w.buttons():
                        if d.text() == "Aktar":
                            hedef = d
                    if hedef is not None and onayla:
                        hedef.click()
                    else:
                        w.reject()
                    return

        def _zaman_asimi():
            if durum["bitti"]:
                return
            sonuc.zaman_asimi = True
            # Akışı KİLİTLİ bırakmamak için açık modal pencereleri kapat.
            for w in QApplication.topLevelWidgets():
                if w.isVisible() and (isinstance(w, (QInputDialog, QMessageBox))
                                      or w.isModal()):
                    w.reject() if hasattr(w, "reject") else w.close()

        surucu = QTimer()
        surucu.timeout.connect(_surucu)
        surucu.start(SURUCU_ARALIK_MS)
        koruma = QTimer()
        koruma.setSingleShot(True)
        koruma.timeout.connect(_zaman_asimi)
        koruma.start(ZAMAN_ASIMI_MS)
        try:
            with mock.patch.object(ei.QFileDialog, "getOpenFileName",
                                   return_value=(str(yol), "")):
                sonuc.donen = ei.run_import_flow(self.parent, tur)
        finally:
            durum["bitti"] = True
            surucu.stop()
            koruma.stop()
            QApplication.processEvents()
        self.assertFalse(sonuc.zaman_asimi,
                         "İçe aktarma akışı zaman aşımına uğradı — diyalog "
                         "yanıtlanamadı (modal kilitlenme).")
        return sonuc

    def _urun_kodlari(self):
        return sorted(r["product_code"] for r in
                      self.db.fetchall("SELECT product_code FROM products"))

    def _firma_adlari(self):
        return sorted(r["company_name"] for r in
                      self.db.fetchall("SELECT company_name FROM customers"))


class SayfaDiyaloguModaliteTests(_Temel):
    """Sayfa sorusu açıkken başka modal pencere OLMAMALI (asıl O16 kanıtı)."""

    def test_urun_akisinda_sayfa_diyalogu_bloklanmamali(self):
        sonuc = self._akisi_calistir(self._iki_sayfali_urun(), "products")
        self.assertTrue(sonuc.sayfa_diyalogu_gorundu,
                        "Sayfa seçim diyaloğu hiç açılmadı.")
        self.assertEqual(
            sonuc.engelleyen_modaller, [],
            "Sayfa seçim diyaloğu açıkken başka modal pencere var; "
            "kullanıcı soruyu yanıtlayamaz.")

    def test_musteri_akisinda_sayfa_diyalogu_bloklanmamali(self):
        sonuc = self._akisi_calistir(self._iki_sayfali_musteri(), "customers")
        self.assertTrue(sonuc.sayfa_diyalogu_gorundu,
                        "Sayfa seçim diyaloğu hiç açılmadı.")
        self.assertEqual(
            sonuc.engelleyen_modaller, [],
            "Sayfa seçim diyaloğu açıkken başka modal pencere var; "
            "kullanıcı soruyu yanıtlayamaz.")

    def test_ilerleme_penceresi_sayfa_sorusundan_once_gorunmemeli(self):
        """İlerleme penceresi soru anında hiç yaratılmamış olmalı."""
        sonuc = self._akisi_calistir(self._iki_sayfali_urun(), "products")
        self.assertNotIn("İçe Aktarma", sonuc.engelleyen_modaller or [])


class SayfaSecimiIslevTests(_Temel):
    """Gerçek diyalogla seçim/iptal işlevi."""

    def test_secilen_sayfa_aktarilir_digeri_aktarilmaz(self):
        self._akisi_calistir(self._iki_sayfali_urun(), "products",
                             sayfa_secimi="SECILEN")
        self.assertEqual(self._urun_kodlari(), ["SEC-1", "SEC-2"])

    def test_digeri_secilirse_yalniz_o_sayfa_aktarilir(self):
        self._akisi_calistir(self._iki_sayfali_urun(), "products",
                             sayfa_secimi="SECILMEYEN")
        self.assertEqual(self._urun_kodlari(), ["ATLA-1"])

    def test_musteri_akisinda_secilen_sayfa_aktarilir(self):
        self._akisi_calistir(self._iki_sayfali_musteri(), "customers",
                             sayfa_secimi="SECILEN")
        self.assertEqual(self._firma_adlari(), ["Secilen Firma"])

    def test_secenekler_her_iki_sayfayi_listeler(self):
        sonuc = self._akisi_calistir(self._iki_sayfali_urun(), "products")
        self.assertEqual(len(sonuc.sunulan_secenekler), 2)
        self.assertTrue(any(s.startswith("SECILEN")
                            for s in sonuc.sunulan_secenekler))
        self.assertTrue(any(s.startswith("SECILMEYEN")
                            for s in sonuc.sunulan_secenekler))


class SayfaSecimiIptalTests(_Temel):
    """İptalde DB yazımı, hata kutusu ve yarım aktarım OLMAMALI."""

    def test_iptalde_urun_yazilmaz(self):
        sonuc = self._akisi_calistir(self._iki_sayfali_urun(), "products",
                                     iptal=True)
        self.assertFalse(sonuc.donen)
        self.assertEqual(self._urun_kodlari(), [])

    def test_iptalde_musteri_yazilmaz(self):
        sonuc = self._akisi_calistir(self._iki_sayfali_musteri(), "customers",
                                     iptal=True)
        self.assertFalse(sonuc.donen)
        self.assertEqual(self._firma_adlari(), [])

    def test_iptalde_hata_kutusu_gosterilmez(self):
        sonuc = self._akisi_calistir(self._iki_sayfali_urun(), "products",
                                     iptal=True)
        self.assertEqual(sonuc.mesaj_kutulari, [])


class DosyaKilidiTests(_Temel):
    """Çok adaylı XLSX iki kez açılıyor: hiçbir yolda workbook açık kalmamalı.

    Windows'ta açık bir dosya tanıtıcısı silmeyi engeller; bu yüzden akıştan
    sonra dosyayı SİLEBİLMEK, workbook'un kapandığının doğrudan kanıtıdır.
    """

    def _silinebiliyor_mu(self, yol: Path) -> bool:
        try:
            yol.unlink()
            return True
        except OSError:
            return False

    def test_basarili_aktarimdan_sonra_dosya_kilitli_kalmaz(self):
        yol = self._iki_sayfali_urun()
        self._akisi_calistir(yol, "products")
        self.assertTrue(self._silinebiliyor_mu(yol),
                        "XLSX hâlâ kilitli — workbook kapatılmamış.")

    def test_iptalden_sonra_dosya_kilitli_kalmaz(self):
        yol = self._iki_sayfali_urun()
        self._akisi_calistir(yol, "products", iptal=True)
        self.assertTrue(self._silinebiliyor_mu(yol),
                        "İptalden sonra XLSX kilitli kaldı.")

    def test_bozuk_xlsx_gercek_hata_verir_ve_kilit_birakmaz(self):
        yol = self.kok / "bozuk.xlsx"
        yol.write_bytes(b"PK\x03\x04 bu gecerli bir xlsx degil")
        sonuc = self._akisi_calistir(yol, "products")
        self.assertFalse(sonuc.sayfa_diyalogu_gorundu)
        self.assertTrue(sonuc.mesaj_kutulari, "Bozuk dosya için uyarı yok.")
        self.assertEqual(sonuc.mesaj_kutulari[0][0], "Dosya Hatası")
        self.assertEqual(self._urun_kodlari(), [])
        self.assertTrue(self._silinebiliyor_mu(yol),
                        "Bozuk dosya okuma denemesi kilit bıraktı.")


class TekKezSormaTests(_Temel):
    """Sayfa sorusu akış boyunca YALNIZ BİR KEZ sorulmalı."""

    def _sayimli_calistir(self, yol, tur, **kw):
        sayac = {"n": 0}
        orjinal = ei._sayfa_sordur

        def _sayan(*a, **k):
            sayac["n"] += 1
            return orjinal(*a, **k)

        with mock.patch.object(ei, "_sayfa_sordur", _sayan):
            self._akisi_calistir(yol, tur, **kw)
        return sayac["n"]

    def test_urun_akisinda_bir_kez_sorulur(self):
        self.assertEqual(
            self._sayimli_calistir(self._iki_sayfali_urun(), "products"), 1)

    def test_musteri_akisinda_bir_kez_sorulur(self):
        self.assertEqual(
            self._sayimli_calistir(self._iki_sayfali_musteri(), "customers"), 1)

    def test_iptalde_de_bir_kez_sorulur(self):
        self.assertEqual(
            self._sayimli_calistir(self._iki_sayfali_urun(), "products",
                                   iptal=True), 1)

    def test_tek_sayfali_dosyada_hic_sorulmaz(self):
        yol = self._xlsx([("TEK", [U_BAS, ["T-1", "Tek", 1]])])
        self.assertEqual(self._sayimli_calistir(yol, "products"), 0)


class DiyalogsuzAkisTests(_Temel):
    """Tek sayfalı XLSX ve CSV davranışı DEĞİŞMEMELİ."""

    def test_tek_sayfali_xlsx_diyalog_acmaz(self):
        yol = self._xlsx([("TEK", [U_BAS, ["TEK-1", "Tek Urun", 5]])])
        sonuc = self._akisi_calistir(yol, "products")
        self.assertFalse(sonuc.sayfa_diyalogu_gorundu)
        self.assertEqual(self._urun_kodlari(), ["TEK-1"])

    def test_csv_diyalog_acmaz(self):
        yol = self.kok / "urun.csv"
        yol.write_text("Ürün Kodu,Ürün Adı,Fiyat\nCSV-1,Csv Urun,7\n",
                       encoding="utf-8-sig")
        sonuc = self._akisi_calistir(yol, "products")
        self.assertFalse(sonuc.sayfa_diyalogu_gorundu)
        self.assertEqual(self._urun_kodlari(), ["CSV-1"])

    def test_gizli_sayfa_tek_aday_birakirsa_diyalog_acilmaz(self):
        yol = self._xlsx([
            ("GORUNUR", [U_BAS, ["G-1", "Gorunur", 1]]),
            ("GIZLI", [U_BAS, ["H-1", "Gizli", 2]]),
        ], gizli=("GIZLI",))
        sonuc = self._akisi_calistir(yol, "products")
        self.assertFalse(sonuc.sayfa_diyalogu_gorundu)
        self.assertEqual(self._urun_kodlari(), ["G-1"])


if __name__ == "__main__":
    unittest.main()
