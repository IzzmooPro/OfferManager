"""U17 — Updater güven zinciri: asset seçimi, URL ve içerik doğrulaması.

Kanıtlanan sözleşme:

* Yalnız `TeklifYonetim_Setup_<tag>.exe` adlı TEK asset kabul edilir;
  "listedeki ilk .exe" yaklaşımı kaldırılmıştır.
* `browser_download_url` şema / host / repo yolu / dosya adı bakımından
  birebir doğrulanır; suffix hilesi (`github.com.evil.example`) reddedilir.
* API `size` ve `digest` alanları zorunludur; eksikse fail-closed.
* İndirme, SHA-256 ve gerçek bayt sayısı doğrulanmadan `download_finished`
  emit etmez; hata hâlinde yarım dosya silinir ve kullanıcıya teknik ayrıntı
  içermeyen tek bir mesaj verilir.

Gerçek ağ, gerçek indirme, tarayıcı ve kurulum başlatma bu dosyada bloklanır.
"""
import hashlib
import io
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import tempfile
import unittest
import urllib.request
import webbrowser
from pathlib import Path
from unittest import mock

from PySide6.QtWidgets import QApplication, QMessageBox

import ui.utils.updater as updater

TAG = "v9.9"
ASSET = f"TeklifYonetim_Setup_{TAG}.exe"
INDIRME_KOKU = f"https://github.com/IzzmooPro/OfferManager/releases/download/{TAG}/"
GECERLI_URL = INDIRME_KOKU + ASSET
GOVDE = b"MZ" + b"\x00" * 1022
OZET = hashlib.sha256(GOVDE).hexdigest()
BOYUT = len(GOVDE)


_VARSAYILAN = object()          # None gerçek bir test girdisidir; sentinel şart


def asset(ad=ASSET, url=_VARSAYILAN, digest=_VARSAYILAN, size=_VARSAYILAN,
          **ekstra):
    """GitHub Releases API asset nesnesinin ilgili alanları."""
    kayit = {
        "name": ad,
        "browser_download_url": (INDIRME_KOKU + ad if url is _VARSAYILAN
                                 else url),
        "digest": f"sha256:{OZET}" if digest is _VARSAYILAN else digest,
        "size": BOYUT if size is _VARSAYILAN else size,
    }
    kayit.update(ekstra)
    return kayit


def release(assets, tag=TAG):
    return {"tag_name": tag, "assets": assets}


# ── 1. Asset seçimi ───────────────────────────────────────────────────────────

class AssetSeciminiTests(unittest.TestCase):
    """`select_update_asset` — tam ad eşleşmesi ve fail-closed davranışı."""

    def secilen(self, data):
        secim, neden = updater.select_update_asset(data)
        return secim, neden

    def test_beklenen_ad_ikinci_sirada_olsa_bile_secilir(self):
        secim, _ = self.secilen(release([asset("yanlis_ilk.exe"), asset()]))
        self.assertIsNotNone(secim, "beklenen asset bulunamadı")
        self.assertEqual(secim.name, ASSET)
        self.assertEqual(secim.url, GECERLI_URL)
        self.assertEqual(secim.sha256, OZET)
        self.assertEqual(secim.size, BOYUT)

    def test_ilk_exe_yaklasimi_kaldirildi(self):
        """Sıra değişse de aynı asset seçilir."""
        ileri = release([asset(), asset("payload.exe")])
        geri = release([asset("payload.exe"), asset()])
        self.assertEqual(self.secilen(ileri)[0], self.secilen(geri)[0])

    def test_yalniz_yanlis_exe_varsa_fail_closed(self):
        secim, neden = self.secilen(release([asset("payload.exe"),
                                             asset("debug_tool.exe")]))
        self.assertIsNone(secim)
        self.assertTrue(neden, "reddetme nedeni loglanmak üzere döndürülmedi")

    def test_beklenen_ad_iki_kez_varsa_fail_closed(self):
        secim, _ = self.secilen(release([asset(), asset()]))
        self.assertIsNone(secim, "aynı adlı iki asset kabul edildi")

    def test_hic_asset_yoksa_fail_closed(self):
        self.assertIsNone(self.secilen(release([]))[0])

    def test_bos_tag_fail_closed(self):
        self.assertIsNone(self.secilen(release([asset()], tag=""))[0])

    def test_benzer_adlar_reddedilir(self):
        for ad in (ASSET.upper(), ASSET.lower(), ASSET + ".exe",
                   " " + ASSET, ASSET + " ", ASSET.replace("_Setup_", "_setup_"),
                   "TeklifYonetim_Setup_v9.90.exe", "TeklifYonetim_Setup.exe"):
            with self.subTest(ad=ad):
                if ad == ASSET:
                    continue
                self.assertIsNone(self.secilen(release([asset(ad)]))[0],
                                  f"benzer ad kabul edildi: {ad!r}")

    def test_beklenen_ad_uretimi(self):
        self.assertEqual(updater.expected_asset_name("v4.2"),
                         "TeklifYonetim_Setup_v4.2.exe")


# ── 2. URL doğrulaması ────────────────────────────────────────────────────────

class IndirmeUrlTests(unittest.TestCase):

    RED = [
        ("http şeması", "http://github.com/IzzmooPro/OfferManager/releases/"
                        f"download/{TAG}/{ASSET}"),
        ("file şeması", f"file:///C:/tmp/{ASSET}"),
        ("UNC yolu", f"\\\\sunucu\\pay\\{ASSET}"),
        ("başka host", f"https://evil.example.com/{ASSET}"),
        ("suffix hilesi", "https://github.com.evil.example/IzzmooPro/"
                          f"OfferManager/releases/download/{TAG}/{ASSET}"),
        ("prefix hilesi", "https://evilgithub.com/IzzmooPro/OfferManager/"
                          f"releases/download/{TAG}/{ASSET}"),
        ("userinfo hilesi", "https://github.com@evil.example/IzzmooPro/"
                            f"OfferManager/releases/download/{TAG}/{ASSET}"),
        ("beklenmeyen port", "https://github.com:8443/IzzmooPro/OfferManager/"
                             f"releases/download/{TAG}/{ASSET}"),
        ("başka repo", "https://github.com/baska/Repo/releases/download/"
                       f"{TAG}/{ASSET}"),
        ("başka tag klasörü", "https://github.com/IzzmooPro/OfferManager/"
                              f"releases/download/v1.0/{ASSET}"),
        ("dosya adı farklı", INDIRME_KOKU + "payload.exe"),
        ("boş", ""),
        ("bozuk şema", "htp:/bozuk"),
        ("None", None),
    ]

    def test_gecerli_url_kabul_edilir(self):
        self.assertTrue(updater.is_release_download_url(GECERLI_URL, TAG))

    def test_gecersiz_urller_reddedilir(self):
        for ad, url in self.RED:
            with self.subTest(ad=ad):
                self.assertFalse(updater.is_release_download_url(url, TAG),
                                 f"kabul edilmemeliydi: {ad}")

    def test_gecersiz_url_asset_secimini_de_dusurur(self):
        for ad, url in self.RED:
            with self.subTest(ad=ad):
                secim, _ = updater.select_update_asset(
                    release([asset(url=url)]))
                self.assertIsNone(secim, f"asset seçimi {ad} URL'sini geçirdi")


class YonlendirmeHostTests(unittest.TestCase):
    """Redirect sonrası son URL kontrolü — CDN host'u dâhil."""

    def test_izinli_hostlar(self):
        for url in ("https://github.com/x/y",
                    "https://objects.githubusercontent.com/github-production-"
                    "release-asset/1/2",
                    "https://release-assets.githubusercontent.com/github-"
                    "production-release-asset/1/2"):
            with self.subTest(url=url):
                self.assertTrue(updater.is_allowed_download_host(url))

    def test_reddedilen_hostlar(self):
        for url in ("http://objects.githubusercontent.com/x",
                    "https://objects.githubusercontent.com.evil.example/x",
                    "https://evilobjects.githubusercontent.com/x",
                    "https://githubusercontent.com/x",
                    "https://evil.example/x",
                    "file:///C:/tmp/x.exe", "", None):
            with self.subTest(url=url):
                self.assertFalse(updater.is_allowed_download_host(url))


# ── 3. digest / size alanları ─────────────────────────────────────────────────

class MetadataAlanTests(unittest.TestCase):

    def _red(self, **alanlar):
        secim, neden = updater.select_update_asset(release([asset(**alanlar)]))
        self.assertIsNone(secim, f"kabul edilmemeliydi: {alanlar}")
        self.assertTrue(neden)

    def test_digest_bozuksa_reddedilir(self):
        for d in ("", None, "sha256:", OZET, f"md5:{OZET}", f"sha1:{OZET}",
                  "sha256:" + OZET[:63], "sha256:" + OZET + "a",
                  "sha256:" + "z" * 64, f"SHA256::{OZET}", 12345):
            with self.subTest(digest=str(d)[:24]):
                self._red(digest=d)

    def test_digest_alani_yoksa_reddedilir(self):
        kayit = asset()
        del kayit["digest"]
        self.assertIsNone(updater.select_update_asset(release([kayit]))[0])

    def test_size_bozuksa_reddedilir(self):
        for s in (None, 0, -1, "52496621", 12.5, True, False, [BOYUT]):
            with self.subTest(size=repr(s)):
                self._red(size=s)

    def test_size_alani_yoksa_reddedilir(self):
        kayit = asset()
        del kayit["size"]
        self.assertIsNone(updater.select_update_asset(release([kayit]))[0])

    def test_dogru_metadata_kabul_edilir(self):
        secim, _ = updater.select_update_asset(release([asset()]))
        self.assertIsNotNone(secim)
        self.assertEqual(secim.sha256, OZET.lower())


# ── 4. İndirme doğrulaması ────────────────────────────────────────────────────

class _Yanit:
    """urlopen yerine: içerik, başlık ve son URL kontrol edilebilir yanıt."""

    def __init__(self, govde, content_length="auto", son_url=None,
                 erken_eof=None):
        self._buf = io.BytesIO(govde)
        self._erken_eof = erken_eof
        self._okunan = 0
        self._son_url = son_url or GECERLI_URL
        if content_length == "auto":
            self.headers = {"Content-Length": str(len(govde))}
        elif content_length is None:
            self.headers = {}
        else:
            self.headers = {"Content-Length": str(content_length)}

    def geturl(self):
        return self._son_url

    def read(self, n=-1):
        if self._erken_eof is not None:
            kalan = self._erken_eof - self._okunan
            if kalan <= 0:
                return b""              # sunucu erken ve "normal" EOF verir
            n = kalan if n is None or n < 0 else min(n, kalan)
        veri = self._buf.read(n)
        self._okunan += len(veri)
        return veri

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class IndirmeDogrulamaTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="oms_u17_")
        self.addCleanup(self._tmp.cleanup)
        self.hedef = Path(self._tmp.name) / "TeklifYonetim_Setup.exe"

    def indir(self, yanit_factory, sha=None, size=None):
        dl = updater._Downloader(GECERLI_URL, str(self.hedef),
                                 expected_sha256=OZET if sha is None else sha,
                                 expected_size=BOYUT if size is None else size)
        sonuc = {"bitti": [], "hata": []}
        dl.download_finished.connect(sonuc["bitti"].append)
        dl.failed.connect(sonuc["hata"].append)
        with mock.patch.object(urllib.request, "urlopen",
                               lambda *a, **k: yanit_factory()):
            updater._Downloader.run(dl)
        return sonuc

    def test_dogru_icerik_bir_kez_bitti_emit_eder(self):
        s = self.indir(lambda: _Yanit(GOVDE))
        self.assertEqual(s["hata"], [])
        self.assertEqual(len(s["bitti"]), 1, "download_finished bir kez gelmeli")
        self.assertEqual(self.hedef.read_bytes(), GOVDE)

    def test_content_length_yoksa_da_calisir(self):
        s = self.indir(lambda: _Yanit(GOVDE, content_length=None))
        self.assertEqual(len(s["bitti"]), 1)

    def test_bos_icerik_basarisiz(self):
        s = self.indir(lambda: _Yanit(b"", content_length=BOYUT))
        self.assertEqual(s["bitti"], [])
        self.assertEqual(len(s["hata"]), 1)

    def test_erken_eof_basarisiz(self):
        s = self.indir(lambda: _Yanit(GOVDE, erken_eof=100))
        self.assertEqual(s["bitti"], [])
        self.assertEqual(len(s["hata"]), 1)

    def test_fazla_byte_basarisiz(self):
        s = self.indir(lambda: _Yanit(GOVDE + b"EK", content_length=BOYUT))
        self.assertEqual(s["bitti"], [])

    def test_yanlis_hash_basarisiz(self):
        bozuk = b"XZ" + GOVDE[2:]                  # aynı boyut, farklı içerik
        self.assertEqual(len(bozuk), BOYUT)
        s = self.indir(lambda: _Yanit(bozuk))
        self.assertEqual(s["bitti"], [])
        self.assertEqual(len(s["hata"]), 1)

    def test_html_hata_sayfasi_basarisiz(self):
        s = self.indir(lambda: _Yanit(b"<html>404 Not Found</html>"))
        self.assertEqual(s["bitti"], [])

    def test_content_length_uyusmazligi_basarisiz(self):
        s = self.indir(lambda: _Yanit(GOVDE, content_length=BOYUT + 1))
        self.assertEqual(s["bitti"], [])

    def test_bozuk_content_length_basarisiz(self):
        s = self.indir(lambda: _Yanit(GOVDE, content_length="abc"))
        self.assertEqual(s["bitti"], [])

    def test_izinli_cdn_yonlendirmesi_kabul(self):
        s = self.indir(lambda: _Yanit(
            GOVDE, son_url="https://objects.githubusercontent.com/a/b"))
        self.assertEqual(len(s["bitti"]), 1)

    def test_beklenmeyen_yonlendirme_hostu_basarisiz(self):
        s = self.indir(lambda: _Yanit(
            GOVDE, son_url="https://github.com.evil.example/a/b"))
        self.assertEqual(s["bitti"], [])
        self.assertEqual(len(s["hata"]), 1)

    def test_http_yonlendirmesi_basarisiz(self):
        s = self.indir(lambda: _Yanit(GOVDE, son_url="http://github.com/a/b"))
        self.assertEqual(s["bitti"], [])

    def test_yarim_dosya_temizlenir(self):
        self.indir(lambda: _Yanit(GOVDE, erken_eof=100))
        self.assertFalse(self.hedef.exists(), "yarım dosya diskte bırakıldı")

    # ── Geçici indirme klasörü ───────────────────────────────────────────

    def _indirme_klasoru(self):
        """Uygulamadaki gibi ayrı bir TeklifUpdate_* klasörü."""
        d = Path(self._tmp.name) / "TeklifUpdate_test"
        d.mkdir()
        self.hedef = d / "TeklifYonetim_Setup.exe"
        return d

    def test_bos_kalan_klasor_kaldirilir(self):
        d = self._indirme_klasoru()
        self.indir(lambda: _Yanit(GOVDE, erken_eof=100))
        self.assertFalse(self.hedef.exists())
        self.assertFalse(d.exists(), "boş kalan geçici indirme klasörü kaldırılmadı")

    def test_klasordeki_baska_dosya_korunur(self):
        d = self._indirme_klasoru()
        baska = d / "kullanicinin_dosyasi.txt"
        baska.write_text("dokunma", encoding="utf-8")
        self.indir(lambda: _Yanit(GOVDE, erken_eof=100))
        self.assertFalse(self.hedef.exists(), "yarım installer silinmedi")
        self.assertTrue(d.exists(), "dolu klasör kaldırıldı")
        self.assertEqual(baska.read_text(encoding="utf-8"), "dokunma")

    def test_rmdir_hatasi_ana_hatayi_bozmaz(self):
        self._indirme_klasoru()
        with mock.patch.object(Path, "rmdir", side_effect=OSError("kilitli")):
            s = self.indir(lambda: _Yanit(GOVDE, erken_eof=100))
        self.assertEqual(s["bitti"], [])
        self.assertEqual(s["hata"], [updater.VERIFY_FAILED_MESSAGE])

    def test_basarili_indirmede_klasor_korunur(self):
        d = self._indirme_klasoru()
        s = self.indir(lambda: _Yanit(GOVDE))
        self.assertEqual(len(s["bitti"]), 1)
        self.assertTrue(d.exists() and self.hedef.exists(),
                        "başarılı indirmede dosya/klasör silindi")

    def test_silme_hatasi_asil_hatayi_gizlemez(self):
        with mock.patch.object(Path, "unlink", side_effect=OSError("kilitli")):
            s = self.indir(lambda: _Yanit(GOVDE, erken_eof=100))
        self.assertEqual(s["bitti"], [])
        self.assertEqual(len(s["hata"]), 1,
                         "silme hatası asıl doğrulama hatasını gizledi")
        self.assertEqual(s["hata"][0], updater.VERIFY_FAILED_MESSAGE)

    def test_kullaniciya_giden_mesaj_teknik_ayrinti_icermez(self):
        s = self.indir(lambda: _Yanit(GOVDE, erken_eof=100))
        mesaj = s["hata"][0]
        self.assertEqual(mesaj, updater.VERIFY_FAILED_MESSAGE)
        for sizinti in ("http", "github", str(self.hedef), "sha256", OZET):
            self.assertNotIn(sizinti.lower(), mesaj.lower(),
                             f"kullanıcı mesajında sızıntı: {sizinti}")

    def test_ag_hatasi_ayri_mesaj_verir(self):
        def _patlat():
            raise OSError("baglanti sifirlandi")
        s = self.indir(lambda: _patlat())
        self.assertEqual(s["bitti"], [])
        self.assertEqual(s["hata"], [updater.DOWNLOAD_FAILED_MESSAGE])
        self.assertNotIn("baglanti", s["hata"][0])


# ── 5. Diyalog: doğrulama hatasında kurulum başlatılmaz ──────────────────────

class DiyalogFailClosedTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="oms_u17d_")
        self.addCleanup(self._tmp.cleanup)
        self._dizinler = []
        self._patch(updater.tempfile, "mkdtemp", self._mkdtemp)
        self.web_open = self._patch(webbrowser, "open")
        self.os_startfile = self._patch(os, "startfile", olustur=True)
        self.os_exit = self._patch(os, "_exit")
        self.msg_warning = self._patch(QMessageBox, "warning")
        # Modal kutu testi kilitlemesin — hata kutusu örnek exec()'i kullanır.
        self.kutu_exec = self._patch(
            QMessageBox, "exec",
            lambda kutu, *a, **k: QMessageBox.StandardButton.Close)

    def _mkdtemp(self, *a, **k):
        d = Path(self._tmp.name) / f"TeklifUpdate_{len(self._dizinler)}"
        d.mkdir()
        self._dizinler.append(d)
        return str(d)

    def _patch(self, hedef, ad, yeni=None, olustur=False):
        kw = {"create": True} if olustur else {}
        p = (mock.patch.object(hedef, ad, yeni, **kw) if yeni is not None
             else mock.patch.object(hedef, ad, **kw))
        sahte = p.start()
        self.addCleanup(p.stop)
        return sahte

    def _yasak_yollar_cagrilmadi(self):
        self.assertEqual(self.os_startfile.call_count, 0, "os.startfile çağrıldı")
        self.assertEqual(self.os_exit.call_count, 0, "os._exit çağrıldı")
        self.assertEqual(self.web_open.call_count, 0,
                         "tarayıcı kullanıcıya sorulmadan açıldı")

    def test_metadata_yoksa_indirme_baslamaz(self):
        dlg = updater.UpdateDialog(TAG, GECERLI_URL)
        self.addCleanup(dlg.deleteLater)
        dlg._start_update()
        self.assertIsNone(dlg._downloader, "doğrulama verisi olmadan indirildi")
        self._yasak_yollar_cagrilmadi()

    def test_dogrulama_hatasinda_kurulum_baslatilmaz(self):
        dlg = updater.UpdateDialog(TAG, GECERLI_URL, expected_sha256=OZET,
                                   expected_size=BOYUT)
        self.addCleanup(dlg.deleteLater)
        with mock.patch.object(urllib.request, "urlopen",
                               lambda *a, **k: _Yanit(GOVDE, erken_eof=64)):
            dlg._start_update()
            dlg._downloader.wait(20000)
        self.app.processEvents()
        self._yasak_yollar_cagrilmadi()
        self.assertEqual(self.msg_warning.call_count, 0,
                         "eski ham hata kutusu hâlâ kullanılıyor")

    def test_dogrulama_hatasi_mesaji_gosterilir(self):
        dlg = updater.UpdateDialog(TAG, GECERLI_URL, expected_sha256=OZET,
                                   expected_size=BOYUT)
        self.addCleanup(dlg.deleteLater)
        gorulen = []
        self._patch(updater.UpdateDialog, "_hata_kutusu_goster",
                    lambda self, mesaj: gorulen.append(mesaj))
        dlg._on_download_failed(updater.VERIFY_FAILED_MESSAGE)
        self.assertEqual(gorulen, [updater.VERIFY_FAILED_MESSAGE])
        self._yasak_yollar_cagrilmadi()


# ── 6. Checker'lar aynı yardımcıyı kullanır ──────────────────────────────────

class CheckerSozlesmeTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _urlopen(self, data):
        govde = __import__("json").dumps(data).encode()
        return lambda *a, **k: _Yanit(govde)

    def test_update_available_dort_alan_tasir(self):
        ch = updater.UpdateChecker()
        alinan = []
        ch.update_available.connect(lambda *a: alinan.append(a))
        with mock.patch.object(urllib.request, "urlopen",
                               self._urlopen(release([asset()]))):
            updater.UpdateChecker.run(ch)
        self.assertEqual(len(alinan), 1)
        self.assertEqual(alinan[0], (TAG, GECERLI_URL, OZET, BOYUT))

    def test_update_found_dort_alan_tasir(self):
        ch = updater.StartupUpdateChecker()
        alinan = []
        ch.update_found.connect(lambda *a: alinan.append(a))
        with mock.patch.object(urllib.request, "urlopen",
                               self._urlopen(release([asset()]))):
            updater.StartupUpdateChecker.run(ch)
        self.assertEqual(alinan, [(TAG, GECERLI_URL, OZET, BOYUT)])

    def test_checker_fail_closed(self):
        """Yeni sürüm VAR ama asset doğrulanamıyor → "güncel" DENMEZ.

        no_update, AboutDialog'da "Uygulama güncel ✓" olarak görünür; bu
        durumda bu yanlış bir sonuçtur. Doğru davranış: tek bir güvenli
        check_failed mesajı.
        """
        ch = updater.UpdateChecker()
        alinan, guncel, hatalar = [], [], []
        ch.update_available.connect(lambda *a: alinan.append(a))
        ch.no_update.connect(lambda: guncel.append(1))
        ch.check_failed.connect(hatalar.append)
        with mock.patch.object(urllib.request, "urlopen",
                               self._urlopen(release([asset("payload.exe")]))):
            updater.UpdateChecker.run(ch)
        self.assertEqual(alinan, [], "doğrulanamayan asset güncelleme olarak sunuldu")
        self.assertEqual(guncel, [], "doğrulanamayan asset 'uygulama güncel' sayıldı")
        self.assertEqual(hatalar, [updater.ASSET_VERIFY_FAILED_MESSAGE])

    def test_guncelse_no_update_yayilir(self):
        """Gerçekten güncelken davranış değişmedi."""
        ch = updater.UpdateChecker()
        guncel, hatalar = [], []
        ch.no_update.connect(lambda: guncel.append(1))
        ch.check_failed.connect(hatalar.append)
        with mock.patch.object(urllib.request, "urlopen",
                               self._urlopen(release([asset()], tag="v0.1"))):
            updater.UpdateChecker.run(ch)
        self.assertEqual(len(guncel), 1)
        self.assertEqual(hatalar, [])

    def test_ham_ag_hatasi_kullaniciya_sizmaz(self):
        GIZLI = "GIZLI-URL C:/secret/token"
        ch = updater.UpdateChecker()
        hatalar = []
        ch.check_failed.connect(hatalar.append)

        def _patlat(*a, **k):
            raise RuntimeError(GIZLI)

        with mock.patch.object(urllib.request, "urlopen", _patlat):
            with self.assertLogs("updater", level="WARNING") as kayit:
                updater.UpdateChecker.run(ch)

        self.assertEqual(hatalar, [updater.CHECK_FAILED_MESSAGE])
        self.assertNotIn(GIZLI, hatalar[0])
        for parca in ("secret", "token", "C:/", "RuntimeError"):
            self.assertNotIn(parca.lower(), hatalar[0].lower(),
                             f"kullanıcı mesajında sızıntı: {parca}")
        self.assertTrue(any(GIZLI in satir for satir in kayit.output),
                        "teknik neden loga yazılmadı")

    def test_startup_checker_fail_closed(self):
        ch = updater.StartupUpdateChecker()
        alinan = []
        ch.update_found.connect(lambda *a: alinan.append(a))
        with mock.patch.object(urllib.request, "urlopen",
                               self._urlopen(release([asset("payload.exe")]))):
            updater.StartupUpdateChecker.run(ch)
        self.assertEqual(alinan, [])

    def test_iki_checker_ayni_yardimciyi_kullanir(self):
        cagri = []
        gercek = updater.select_update_asset
        with mock.patch.object(updater, "select_update_asset",
                               lambda d: (cagri.append(d), gercek(d))[1]):
            for sinif in (updater.UpdateChecker, updater.StartupUpdateChecker):
                ch = sinif()
                with mock.patch.object(urllib.request, "urlopen",
                                       self._urlopen(release([asset()]))):
                    sinif.run(ch)
        self.assertEqual(len(cagri), 2,
                         "checker'lardan biri ortak yardımcıyı kullanmıyor")

    def test_qthread_finished_sinyali_golgelenmiyor(self):
        for sinif in (updater.UpdateChecker, updater.StartupUpdateChecker,
                      updater._Downloader):
            with self.subTest(sinif=sinif.__name__):
                self.assertNotIn("finished", vars(sinif),
                                 "yerleşik finished() sinyali gölgelendi")


if __name__ == "__main__":
    unittest.main(verbosity=2)
