"""R10a — teklif ekranındaki İKİ müşteri kaydetme yolunun aşama sınırları.

Kapsam: `ui/create_offer_page.py`
  * `_check_customer_registration` — "kayıtlı değil, kaydedelim mi?" yolu
  * `_open_add_customer`           — "+ Yeni Müşteri" diyaloğu yolu

Sözleşme:
  * Servis `add` hatası: kullanıcı mesajında ve logda ham istisna, traceback,
    SQL, yerel yol ve firma/müşteri adı BULUNMAZ; güvenli hata altyapısı
    (`operation_error_dialog`) kullanılır; istisna TAM BİR KEZ loglanır;
    `_load_customers` ve combo seçimi ÇALIŞMAZ; form verisi silinmez.
  * `add` BAŞARILI, sonraki yenileme/seçim başarısız: "Müşteri kaydedilemedi"
    DENMEZ. Sabit kısmi başarı mesajı gösterilir, `kismi_hata_goster`
    kullanılır, `add` tam bir kez çağrılır (mükerrer kayıt riski yok).
  * `_open_add_customer` hata sonrası AYNI `CustomerDialog` nesnesiyle yeniden
    denemeye izin verir; kullanıcı vazgeçerse biter; `add` başarılı olduktan
    sonra oluşan yenileme hatası diyaloğu YENİDEN AÇAMAZ ve `add`'i
    TEKRARLAYAMAZ.
  * Tam başarı: liste yenilenir, yeni id seçilir, başarı logunda yalnız
    güvenli kayıt kimliği bulunur — firma adı/iletişim/adres/telefon/e-posta
    loglanmaz.

Gerçek kullanıcı verisi, gerçek DB, yedekler ve Credential Manager
KULLANILMAZ; servisler sahtedir.
"""
import contextlib
import inspect
import logging
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sqlite3
import unittest
from unittest import mock

from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from ui.utils import operation_error_dialog as hata_diyalogu

# Kullanıcı verisi — hiçbir mesajda/logda görünmemeli
FIRMA = "Gizli Müşteri Sanayi A.Ş."
KISI = "Ahmet Yetkili"
ADRES = "Gizli Mah. 5. Sok. No:7"
TEL = "0532 000 11 22"
EPOSTA = "gizli@ornek.com"

GIZLI_HATA = ("UNIQUE constraint failed: customers.company_name "
              "C:/Users/Universe/AppData/Local/gizli.db "
              "INSERT INTO customers SELECT * FROM customers")

HATALAR = {
    "integrity": sqlite3.IntegrityError(GIZLI_HATA),
    "operational": sqlite3.OperationalError("no such table: customers " + GIZLI_HATA),
    "generic": RuntimeError("beklenmeyen " + GIZLI_HATA),
}

SIZINTI = (FIRMA, KISI, ADRES, TEL, EPOSTA, "C:/Users", "SELECT", "INSERT",
           "UNIQUE constraint", "no such table", "Traceback")


def _hata(anahtar):
    try:
        raise HATALAR[anahtar]
    except Exception as exc:                                   # noqa: BLE001
        return exc


class _LogYakala(logging.Handler):
    def __init__(self):
        super().__init__()
        self.satirlar = []

    def emit(self, kayit):
        metin = str(kayit.getMessage())
        if kayit.exc_info:
            import traceback
            metin += "".join(traceback.format_exception(*kayit.exc_info))
        self.satirlar.append(metin)

    @property
    def birlesik(self):
        return "\n".join(self.satirlar)


class _SahteMusteri:
    def __init__(self, id_, ad):
        self.id = id_
        self.company_name = ad


class _Temel(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.log = _LogYakala()
        kok = logging.getLogger()
        kok.addHandler(self.log)
        self._eski = kok.level
        kok.setLevel(logging.DEBUG)
        self.addCleanup(lambda: (kok.removeHandler(self.log),
                                 kok.setLevel(self._eski)))
        mock.patch.object(os, "startfile", create=True).start()
        self.addCleanup(mock.patch.stopall)

        # Açılan tüm kutular kaydedilir; hiçbiri gerçekten modal beklemez.
        self.kutular = []

        def _sahte_exec(kutu, *a, **k):
            self.kutular.append(kutu)
            return QMessageBox.StandardButton.Ok

        mock.patch.object(QMessageBox, "exec", _sahte_exec).start()
        self.uyarilar = []
        mock.patch.object(
            QMessageBox, "warning",
            staticmethod(lambda p, b, m, *a, **k: self.uyarilar.append((b, m)))).start()

    # ── yardımcılar ─────────────────────────────────────────────────────
    def _sayfa(self, add_hatasi=None, load_hatasi=None,
               musteriler=None, secim_hatasi=None):
        """Gerçek sayfa yerine YALNIZ hedef metotları taşıyan hafif nesne.

        Tam `CreateOfferPage` kurulumu DB ve onlarca widget ister; burada
        sınanan şey iki metodun AŞAMA SINIRLARIDIR. Metotlar sınıftan
        alındığı için gerçek üretim kodu çalışır.
        """
        from ui.create_offer_page import CreateOfferPage
        from PySide6.QtWidgets import QWidget

        sayfa = QWidget()
        self.addCleanup(sayfa.deleteLater)

        svc = mock.MagicMock()
        svc.search.return_value = []
        svc.add.side_effect = add_hatasi if add_hatasi else (lambda c: 42)
        liste = [_SahteMusteri(42, FIRMA)] if musteriler is None else musteriler
        svc.get_all.return_value = liste
        sayfa.customer_svc = svc
        sayfa._customers = liste

        sayfa.yenileme = 0
        sayfa.secilen = []

        def _load():
            sayfa.yenileme += 1
            if load_hatasi:
                raise load_hatasi

        sayfa._load_customers = _load

        class _Combo:
            def __init__(self, kayit):
                self._kayit = kayit

            def currentData(self):
                return None

            def currentText(self):
                return FIRMA

            def setCurrentIndex(self, i):
                if secim_hatasi is not None:
                    raise secim_hatasi
                self._kayit.append(i)

        sayfa.customer_combo = _Combo(sayfa.secilen)
        sayfa.company_edit = _Combo(sayfa.secilen)

        class _Alan:
            def __init__(self, deger):
                self._d = deger
                self.temizlendi = False

            def text(self):
                return self._d

            def clear(self):
                self.temizlendi = True

        sayfa.contact_edit = _Alan(KISI)
        sayfa.address_edit = _Alan(ADRES)
        sayfa.phone_edit = _Alan(TEL)
        sayfa.email_edit = _Alan(EPOSTA)

        sayfa._check_customer_registration = (
            CreateOfferPage._check_customer_registration.__get__(sayfa))
        sayfa._open_add_customer = (
            CreateOfferPage._open_add_customer.__get__(sayfa))
        if hasattr(CreateOfferPage, "_yeni_musteriyi_goster"):
            sayfa._yeni_musteriyi_goster = (
                CreateOfferPage._yeni_musteriyi_goster.__get__(sayfa))
        return sayfa, svc

    def _evet_de(self):
        """'Kaydetmek ister misiniz?' kutusunda Evet'e basılmış say."""
        def _exec(kutu, *a, **k):
            self.kutular.append(kutu)
            evet = next((b for b in kutu.buttons() if b.text() == "Evet"), None)
            if evet is not None:
                kutu.setDefaultButton(evet)
                kutu.done(0)
                # clickedButton() yalnız gerçek tıklamada dolar; testte
                # doğrudan sahteleriz.
                kutu.clickedButton = lambda _b=evet: _b
            return QMessageBox.StandardButton.Ok
        mock.patch.object(QMessageBox, "exec", _exec).start()

    def _sizinti_yok(self, metin, nerede):
        for parca in SIZINTI:
            self.assertNotIn(parca, metin, f"{nerede} içinde sızıntı: {parca}")

    def _tum_kutu_metni(self):
        """HATA/kısmi başarı kutularının metni.

        "Müşteri Kaydı" onay sorusu BİLİNÇLİ olarak dışarıda bırakılır: o kutu
        bir hata yolu değildir ve kullanıcının KENDİ YAZDIĞI firma adını
        ("'X' sistemde kayıtlı değil") geri gösterir — bu mevcut ve istenen
        davranıştır. Sızıntı sözleşmesi istisna kaynaklı metinler içindir.
        Yanlışlıkla bir hata kutusunu elemeyelim diye, elenen kutunun gerçekten
        Question ikonlu olduğu doğrulanır.
        """
        metinler = []
        for k in self.kutular:
            if k.windowTitle() == "Müşteri Kaydı":
                self.assertEqual(k.icon(), QMessageBox.Icon.Question,
                                 "onay kutusu sanılan kutu aslında hata kutusu")
                continue
            metinler.append((k.text() or "") + (k.informativeText() or ""))
        return "\n".join(metinler)


# ── A) Kaynak koruması ──────────────────────────────────────────────────

class KaynakKorumasiTests(_Temel):
    """Ham istisna gösterimi kaynaktan da yasaklanır."""

    def _kaynak(self, ad):
        from ui.create_offer_page import CreateOfferPage
        return inspect.getsource(getattr(CreateOfferPage, ad))

    def test_ham_istisna_gosterimi_yok(self):
        for ad in ("_check_customer_registration", "_open_add_customer"):
            kaynak = self._kaynak(ad)
            for yasak in ("{e}", "str(e)", "str(exc)", "exc_info=True",
                          "{exc}", "{err}"):
                with self.subTest(fonksiyon=ad, yasak=yasak):
                    self.assertNotIn(yasak, kaynak,
                                     f"{ad} ham istisna gösteriyor: {yasak}")

    def test_guvenli_altyapi_kullaniliyor(self):
        for ad in ("_check_customer_registration", "_open_add_customer"):
            with self.subTest(fonksiyon=ad):
                self.assertIn("hata_diyalogu", self._kaynak(ad),
                              f"{ad} güvenli hata altyapısını kullanmıyor")

    def test_basari_logunda_firma_adi_yok(self):
        kaynak = self._kaynak("_check_customer_registration")
        self.assertNotIn('logger.info("Yeni müşteri kaydedildi: %s", company)',
                         kaynak, "başarı logunda firma adı var")


# ── B) Servis add hatası — iki yol ──────────────────────────────────────

class ServisHatasiTests(_Temel):

    def test_check_yolu_guvenli(self):
        for ad in HATALAR:
            with self.subTest(hata=ad):
                self.log.satirlar.clear(); self.kutular.clear()
                sayfa, svc = self._sayfa(add_hatasi=_hata(ad))
                self._evet_de()
                sayfa._check_customer_registration()

                self.assertEqual(svc.add.call_count, 1)
                self.assertEqual(sayfa.yenileme, 0,
                                 "add hatasında liste yenilendi")
                self.assertEqual(sayfa.secilen, [],
                                 "add hatasında combo seçimi yapıldı")
                self._sizinti_yok(self._tum_kutu_metni(), "kullanıcı mesajı")
                self._sizinti_yok(self.log.birlesik, "log")
                self.assertEqual(
                    len([s for s in self.log.satirlar if "başarısız" in s]), 1,
                    "istisna tam bir kez güvenli loglanmadı")
                self.assertEqual(self.uyarilar, [],
                                 "ham QMessageBox.warning kullanıldı")

    def test_open_add_yolu_guvenli(self):
        for ad in HATALAR:
            with self.subTest(hata=ad):
                self.log.satirlar.clear(); self.kutular.clear()
                sayfa, svc = self._sayfa(add_hatasi=_hata(ad))
                with _dialog_ortami(self, [True, False], svc):
                    sayfa._open_add_customer()

                self.assertGreaterEqual(svc.add.call_count, 1)
                self.assertEqual(sayfa.yenileme, 0,
                                 "add hatasında liste yenilendi")
                self.assertEqual(sayfa.secilen, [])
                self._sizinti_yok(self._tum_kutu_metni(), "kullanıcı mesajı")
                self._sizinti_yok(self.log.birlesik, "log")
                self.assertEqual(self.uyarilar, [])

    def test_form_verisi_silinmiyor(self):
        sayfa, _ = self._sayfa(add_hatasi=_hata("generic"))
        self._evet_de()
        sayfa._check_customer_registration()
        for alan in ("contact_edit", "address_edit", "phone_edit", "email_edit"):
            self.assertFalse(getattr(sayfa, alan).temizlendi,
                             f"{alan} hata sonrası temizlendi")


def _dialog_ortami(test, kabul, svc):
    """`CustomerDialog` + `CustomerService` sahteleri.

    `_open_add_customer` servisini KENDİ İÇİNDE kurar (`CustomerService()`);
    bu yüzden sınıf da sahtelenir ve testteki tek sahte servise bağlanır.
    """
    durum = {"nesne": None, "exec": 0, "olusturma": 0}
    test.dialog_durum = durum
    sonuc = list(kabul)

    class _SahteDialog:
        def __init__(_s, *a, **k):
            durum["olusturma"] += 1
            durum["nesne"] = _s

        def exec(_s):
            durum["exec"] += 1
            kabul_mu = sonuc.pop(0) if sonuc else False
            return (QDialog.DialogCode.Accepted if kabul_mu
                    else QDialog.DialogCode.Rejected)

        def get_customer(_s):
            m = mock.MagicMock()
            m.company_name = FIRMA
            return m

    yigin = contextlib.ExitStack()
    yigin.enter_context(mock.patch("ui.customers_page.CustomerDialog", _SahteDialog))
    yigin.enter_context(mock.patch("services.customer_service.CustomerService",
                                   lambda *a, **k: svc))
    return yigin


# ── C) add başarılı, sonraki aşama başarısız ────────────────────────────

class KismiBasariTests(_Temel):

    def _kismi_yakala(self):
        cagrilar = []
        gercek = hata_diyalogu.kismi_hata_goster
        mock.patch.object(
            hata_diyalogu, "kismi_hata_goster",
            lambda parent, baslik, exc, mesaj, islem, kayit_id=None:
                cagrilar.append({"baslik": baslik, "exc": type(exc).__name__,
                                 "mesaj": mesaj, "islem": islem,
                                 "kayit_id": kayit_id})
            or gercek(parent, baslik, exc, mesaj, islem, kayit_id=kayit_id)).start()
        return cagrilar

    def test_check_yolu_kismi_basari(self):
        cagrilar = self._kismi_yakala()
        sayfa, svc = self._sayfa(load_hatasi=_hata("generic"))
        self._evet_de()
        sayfa._check_customer_registration()

        self.assertEqual(svc.add.call_count, 1, "add tam bir kez çağrılmadı")
        self.assertEqual(len(cagrilar), 1, "kismi_hata_goster kullanılmadı")
        c = cagrilar[0]
        self.assertEqual(c["kayit_id"], 42, "yalnız new_id geçirilmeli")
        self.assertNotIn("kaydedilemedi", c["mesaj"].lower(),
                         "kaydedilmiş müşteri için 'kaydedilemedi' denmiş")
        self.assertRegex(c["mesaj"], r"(?i)kaydedildi")
        self.assertRegex(c["mesaj"], r"(?i)müşteriler")
        self._sizinti_yok(c["mesaj"], "kısmi başarı mesajı")
        self._sizinti_yok(self._tum_kutu_metni(), "kutu metni")
        self._sizinti_yok(self.log.birlesik, "log")
        self.assertEqual(
            len([s for s in self.log.satirlar if "başarısız" in s]), 1,
            "teknik istisna tam bir kez loglanmadı")

    def test_open_add_yolu_kismi_basari(self):
        cagrilar = self._kismi_yakala()
        sayfa, svc = self._sayfa(load_hatasi=_hata("generic"))
        with _dialog_ortami(self, [True], svc):
            sayfa._open_add_customer()
            olusturma = self.dialog_durum["olusturma"]
            calisan_exec = self.dialog_durum["exec"]

        self.assertEqual(svc.add.call_count, 1,
                         "yenileme hatası add'i tekrarlattı")
        self.assertEqual(olusturma, 1, "diyalog yeniden oluşturuldu")
        self.assertEqual(calisan_exec, 1,
                         "yenileme hatasından sonra diyalog yeniden açıldı")
        self.assertEqual(len(cagrilar), 1)
        self.assertEqual(cagrilar[0]["kayit_id"], 42)
        self.assertNotIn("kaydedilemedi", cagrilar[0]["mesaj"].lower())


class SecimSinirTests(_Temel):
    """Kayıt sonrası aşamanın SESSİZ dönmediği sınır.

    `_load_customers` başarılı olsa bile müşteri ekranda seçilemeyebilir:
    ya yeni id listede yoktur, ya da combo seçimi istisna fırlatır. Her iki
    durumda da kullanıcı "kaydedildi ama ekranda seçilemedi" bilgisini
    ALMALIDIR — sessiz dönüş kaydı görünmez kılar.
    """

    def _kismi_yakala(self):
        cagrilar = []
        gercek = hata_diyalogu.kismi_hata_goster
        mock.patch.object(
            hata_diyalogu, "kismi_hata_goster",
            lambda parent, baslik, exc, mesaj, islem, kayit_id=None:
                cagrilar.append({"exc": type(exc).__name__, "mesaj": mesaj,
                                 "islem": islem, "kayit_id": kayit_id})
            or gercek(parent, baslik, exc, mesaj, islem, kayit_id=kayit_id)).start()
        return cagrilar

    def _dogrula(self, cagrilar, svc, sayfa):
        self.assertEqual(len(cagrilar), 1,
                         "kismi_hata_goster tam bir kez çağrılmadı")
        c = cagrilar[0]
        self.assertEqual(c["kayit_id"], 42, "güvenli kayıt kimliği new_id değil")
        self.assertNotIn("kaydedilemedi", c["mesaj"].lower(),
                         "kaydedilmiş müşteri için 'kaydedilemedi' denmiş")
        self.assertRegex(c["mesaj"], r"(?i)kaydedildi")
        self.assertRegex(c["mesaj"], r"(?i)seçilemedi")
        self._sizinti_yok(c["mesaj"], "kısmi başarı mesajı")
        self._sizinti_yok(self._tum_kutu_metni(), "kutu metni")
        self._sizinti_yok(self.log.birlesik, "log")
        self.assertEqual(svc.add.call_count, 1, "add yeniden çağrıldı")
        self.assertEqual(sayfa.yenileme, 1)
        self.assertEqual(
            len([s for s in self.log.satirlar if "başarısız" in s]), 1,
            "teknik istisna tam bir kez güvenli loglanmadı")

    # ── 1) yeni id listede YOK ──────────────────────────────────────────
    def test_yeni_id_listede_yoksa_kismi_basari(self):
        cagrilar = self._kismi_yakala()
        sayfa, svc = self._sayfa(musteriler=[_SahteMusteri(99, "Başka Firma")])
        self._evet_de()
        sayfa._check_customer_registration()

        self.assertEqual(sayfa.secilen, [], "yanlış müşteri seçildi")
        self._dogrula(cagrilar, svc, sayfa)

    def test_yeni_id_listede_yoksa_open_add_diyalogu_acmaz(self):
        cagrilar = self._kismi_yakala()
        sayfa, svc = self._sayfa(musteriler=[_SahteMusteri(99, "Başka Firma")])
        with _dialog_ortami(self, [True], svc):
            sayfa._open_add_customer()
            durum = dict(self.dialog_durum)

        self.assertEqual(durum["exec"], 1, "diyalog yeniden açıldı")
        self.assertEqual(durum["olusturma"], 1)
        self._dogrula(cagrilar, svc, sayfa)

    # ── 2) combo seçimi istisna fırlatıyor ──────────────────────────────
    def test_combo_secim_istisnasi_kismi_basari(self):
        cagrilar = self._kismi_yakala()
        sayfa, svc = self._sayfa(secim_hatasi=_hata("generic"))
        self._evet_de()
        sayfa._check_customer_registration()

        self._dogrula(cagrilar, svc, sayfa)

    def test_combo_secim_istisnasi_open_add_diyalogu_acmaz(self):
        cagrilar = self._kismi_yakala()
        sayfa, svc = self._sayfa(secim_hatasi=_hata("generic"))
        with _dialog_ortami(self, [True], svc):
            sayfa._open_add_customer()
            durum = dict(self.dialog_durum)

        self.assertEqual(durum["exec"], 1, "diyalog yeniden açıldı")
        self._dogrula(cagrilar, svc, sayfa)

    # ── 3) üretilen teknik hata kullanıcı verisi taşımaz ────────────────
    def test_bulunamadi_hatasi_kullanici_verisi_tasimaz(self):
        cagrilar = self._kismi_yakala()
        sayfa, svc = self._sayfa(musteriler=[_SahteMusteri(99, FIRMA)])
        self._evet_de()
        sayfa._check_customer_registration()

        self.assertEqual(len(cagrilar), 1)
        # İstisnanın KENDİ metni de sabit olmalı: firma adı / id taşımamalı.
        from ui.create_offer_page import CreateOfferPage
        kaynak = inspect.getsource(CreateOfferPage._yeni_musteriyi_goster)
        satirlar = [l for l in kaynak.splitlines() if "raise" in l]
        self.assertTrue(satirlar, "bulunamadı durumu için istisna üretilmiyor")
        for l in satirlar:
            for yasak in ("new_id", "company", "c.id", "%s", "f\""):
                self.assertNotIn(yasak, l,
                                 f"üretilen istisna kullanıcı verisi taşıyor: {l}")


# ── D) _open_add_customer yeniden deneme ────────────────────────────────

class YenidenDenemeTests(_Temel):

    def test_hata_sonrasi_ayni_diyalogla_yeniden_denenebilir(self):
        sayfa, svc = self._sayfa()
        svc.add.side_effect = [_hata("generic"), 42]
        with _dialog_ortami(self, [True, True], svc):
            sayfa._open_add_customer()
            durum = dict(self.dialog_durum)

        self.assertEqual(svc.add.call_count, 2, "yeniden deneme yapılmadı")
        self.assertEqual(durum["olusturma"], 1,
                         "yeniden denemede YENİ diyalog nesnesi üretildi")
        self.assertEqual(durum["exec"], 2)
        self.assertEqual(sayfa.yenileme, 1, "başarılı denemede liste yenilenmedi")

    def test_hata_sonrasi_vazgecince_biter(self):
        sayfa, svc = self._sayfa()
        svc.add.side_effect = [_hata("generic"), 42]
        with _dialog_ortami(self, [True, False], svc):
            sayfa._open_add_customer()

        self.assertEqual(svc.add.call_count, 1, "vazgeçmeye rağmen ikinci kayıt")
        self.assertEqual(sayfa.yenileme, 0)

    def test_basarili_retry_tek_kayit_uretir(self):
        sayfa, svc = self._sayfa()
        svc.add.side_effect = [_hata("generic"), _hata("generic"), 42]
        with _dialog_ortami(self, [True, True, True], svc):
            sayfa._open_add_customer()

        self.assertEqual(svc.add.call_count, 3)
        basarili = [s for s in self.log.satirlar if "kaydedildi" in s]
        self.assertLessEqual(len(basarili), 1,
                             "birden fazla başarılı kayıt logu")


# ── E) Tam başarı ───────────────────────────────────────────────────────

class TamBasariTests(_Temel):

    def test_check_yolu_tam_basari(self):
        sayfa, svc = self._sayfa()
        self._evet_de()
        sayfa._check_customer_registration()

        self.assertEqual(svc.add.call_count, 1)
        self.assertEqual(sayfa.yenileme, 1, "liste yenilenmedi")
        self.assertEqual(sayfa.secilen, [1],
                         "yeni müşteri combo'da seçilmedi (index 0 + 1)")
        self._sizinti_yok(self.log.birlesik, "başarı logu")
        self.assertTrue(any("42" in s for s in self.log.satirlar
                            if "kaydedildi" in s),
                        "başarı logunda güvenli kayıt kimliği yok")

    def test_open_add_yolu_tam_basari(self):
        sayfa, svc = self._sayfa()
        with _dialog_ortami(self, [True], svc):
            sayfa._open_add_customer()

        self.assertEqual(svc.add.call_count, 1)
        self.assertEqual(sayfa.yenileme, 1)
        self.assertEqual(sayfa.secilen, [1])
        self._sizinti_yok(self.log.birlesik, "log")


if __name__ == "__main__":
    unittest.main(verbosity=2)
