"""R10c-3 — yedekleme/geri yükleme güvenli hata ve rollback sözleşmesi.

Kapsam: `ui/dialogs/backup_manager.py` (+ `ui/main_window.py` tüketicileri)

Sözleşme:
  * Ham istisna metni, traceback, SQL, mutlak yol ve kullanıcı verisi hiçbir
    kullanıcı mesajına, loga veya **sinyale** girmez; `exc_info` kullanılmaz.
  * Her teknik istisna `operation_error.logla` ile **en fazla bir kez**
    güvenli loglanır; tüketici (main_window) aynı hatayı yeniden loglamaz.
  * Yedek dosyası oluştuktan sonra metadata yazımı başarısızsa "yedekleme
    başarısız" DENMEZ (invariant 18b) ve `create_backup` tekrarlanmaz.
  * `restore_backup` üç durumu AYIRIR:
      - `preflight_failed`  → hedef veriler HİÇ değiştirilmedi
      - `rolled_back`       → yazma başladı, önceki durum geri getirildi
      - `rollback_failed`   → geri alma tamamlanamadı, veri durumu BELİRSİZ
    `rollback_failed` durumunda "verileriniz korundu" DENMEZ ve restart YAPILMAZ.
  * Rollback ilk hatada durmaz; DB ve tüm optional dosyalar denenir, sonunda
    DB yeniden doğrulanır ve başlangıçtaki var/yok durumu birebir kurulur.

Gerçek kullanıcı DB'si, yedekleri, ayarları ve log klasörü KULLANILMAZ:
tüm yollar `TemporaryDirectory` altına patch'lenir.
"""
import inspect
import json
import logging
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sqlite3
import tempfile
from contextlib import closing
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from PySide6.QtWidgets import (
    QApplication, QDialog, QMainWindow, QMessageBox, QWidget)

import ui.dialogs.backup_manager as bm
from ui.utils import operation_error as op_hata_mod

# Hiçbir yere sızmaması gereken içerik
FIRMA = "Gizli Müşteri A.Ş."
GIZLI = (f"no such table: offers SELECT * FROM customers WHERE company_name='{FIRMA}' "
         "C:/Users/Universe/AppData/Local/OfferManagementSystem/data/database.db")
SIZINTI = (FIRMA, "SELECT", "no such table", "C:/Users", "Traceback",
           "sqlite3", "database.db", "Permission denied")

_TABLOLAR = ("products", "customers", "offers", "offer_items", "offer_counter")


def _hata(sinif=RuntimeError, metin=None):
    try:
        raise sinif(metin if metin is not None else GIZLI)
    except Exception as exc:                                   # noqa: BLE001
        return exc


def _db_isaret(yol: Path):
    """DB'nin MANTIKSAL kimliği. SQLite backup API'si dosyayı yeniden yazdığı
    için byte karşılaştırması güvenilir değildir; işaretçi satırı kullanılır."""
    with closing(sqlite3.connect(str(yol))) as con:
        return [r[0] for r in con.execute("SELECT id FROM offer_counter")]


def _db_yaz(yol: Path, isaret: int = 1):
    """Geçerli, doğrulamayı geçen küçük bir SQLite veritabanı üretir.

    `with sqlite3.connect(...)` bağlantıyı KAPATMAZ (yalnız transaction
    yönetir); Windows'ta dosya kilitli kalır ve geçici klasör silinemez.
    """
    yol.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(str(yol))) as con:
        for t in _TABLOLAR:
            con.execute(f"CREATE TABLE IF NOT EXISTS {t} (id INTEGER PRIMARY KEY)")
        con.execute("INSERT OR REPLACE INTO offer_counter (id) VALUES (?)", (isaret,))
        con.commit()
    return yol


class _LogYakala(logging.Handler):
    def __init__(self):
        super().__init__()
        self.kayitlar = []

    def emit(self, k):
        metin = str(k.getMessage())
        if k.exc_info:
            import traceback
            metin += "".join(traceback.format_exception(*k.exc_info))
        self.kayitlar.append(metin)

    @property
    def birlesik(self):
        return "\n".join(self.kayitlar)

    @property
    def guvenli_log_sayisi(self):
        return len([s for s in self.kayitlar if "başarısız" in s])


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

        # TÜM veri yolları geçici köke taşınır.
        self.tmp = tempfile.TemporaryDirectory(prefix="oms_backup_")
        self.addCleanup(self.tmp.cleanup)
        self.kok = Path(self.tmp.name)
        self.veri = self.kok / "data"; self.veri.mkdir()
        self.yedek_dir = self.kok / "backups"; self.yedek_dir.mkdir()
        self.db = self.veri / "database.db"
        self.cfg = self.veri / "company.cfg"
        self.logo = self.veri / "logo.png"
        self.sig1 = self.veri / "signature1.png"
        self.marker = self.veri / "logo.disabled"
        self.meta = self.veri / "backup_meta.json"

        for ad, deger in (("_DATA_DIR", self.veri), ("_DB_PATH", self.db),
                          ("_CFG_PATH", self.cfg), ("_LOGO_PATH", self.logo),
                          ("_SIG1_PATH", self.sig1),
                          ("_LOGO_DISABLED_PATH", self.marker),
                          ("_DEFAULT_BACKUP_DIR", self.yedek_dir),
                          ("_META_PATH", self.meta)):
            mock.patch.object(bm, ad, deger).start()
        mock.patch.object(bm, "_OPTIONAL_BACKUP_FILES", [
            (self.cfg, "company.cfg"), (self.logo, "logo.png"),
            (self.sig1, "signature1.png"), (self.marker, "logo.disabled")]).start()

        self.kutular = []

        def _exec(kutu, *a, **k):
            self.kutular.append((kutu.windowTitle(), kutu.text() or ""))
            return QMessageBox.StandardButton.Ok

        mock.patch.object(QMessageBox, "exec", _exec).start()
        for ad in ("warning", "information", "critical"):
            mock.patch.object(
                QMessageBox, ad,
                staticmethod(lambda p, b, m, *a, **k:
                             (self.kutular.append((b, m)),
                              QMessageBox.StandardButton.Yes)[1])).start()
        mock.patch.object(
            QMessageBox, "question",
            staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)).start()
        from core.app_paths import LOG_DIR
        LOG_DIR.mkdir(parents=True, exist_ok=True)

    # ── yardımcılar ─────────────────────────────────────────────────────
    def _metinler(self):
        return "\n".join(m for _b, m in self.kutular)

    def _sizinti_yok(self, nerede="", ekstra=()):
        hedefler = SIZINTI + tuple(ekstra)
        for parca in hedefler:
            self.assertNotIn(parca, self._metinler(),
                             f"kullanıcı mesajında sızıntı{nerede}: {parca}")
            self.assertNotIn(parca, self.log.birlesik,
                             f"logda sızıntı{nerede}: {parca}")

    def _zip_yap(self, ad="backup_test.zip", ekler=("company.cfg", "logo.png")):
        """Geçerli bir yedek ZIP'i üretir."""
        kaynak = self.kok / "kaynak.db"
        _db_yaz(kaynak, isaret=22)               # YEDEK içindeki işaretçi
        yol = self.yedek_dir / ad
        with zipfile.ZipFile(str(yol), "w") as zf:
            zf.write(str(kaynak), "database.db")
            for arc in ekler:
                gecici = self.kok / arc
                gecici.write_bytes(b"YEDEK-" + arc.encode())
                zf.write(str(gecici), arc)
        return yol

    def _hedefleri_kur(self, db=True, cfg=True, logo=False):
        """Geri yükleme ÖNCESİ hedef veriler (işaretçi 11 = ÖNCEKİ)."""
        if db:
            _db_yaz(self.db, isaret=11)
        if cfg:
            self.cfg.write_bytes(b"ONCEKI-CFG")
        if logo:
            self.logo.write_bytes(b"ONCEKI-LOGO")

    def _servis(self):
        with mock.patch.object(bm.AutoBackupService, "_apply", lambda s: None):
            return bm.AutoBackupService()


# ── 1. Ham veri taşınması ───────────────────────────────────────────────

class HamVeriTests(_Temel):

    def test_worker_failed_sinyali_ham_metin_tasimaz(self):
        w = bm._BackupWorker(str(self.yedek_dir), "test")
        alinan = []
        w.failed.connect(lambda *a: alinan.append(a))
        with mock.patch.object(bm, "create_backup", side_effect=_hata()):
            w.run()
        self.assertEqual(len(alinan), 1)
        ilk = alinan[0][0]
        self.assertNotIsInstance(ilk, str,
                                 "failed sinyali ham string taşıyor")
        self.assertIsInstance(ilk, BaseException,
                              "failed sinyali istisna NESNESİ taşımalı")

    def test_backup_failed_sinyali_sabit_guvenli_metin(self):
        svc = self._servis()
        disari = []
        svc.backup_failed.connect(lambda m: disari.append(m))
        svc._on_backup_failed(_hata(), "test")
        self.assertEqual(len(disari), 1)
        for parca in SIZINTI:
            self.assertNotIn(parca, disari[0],
                             f"backup_failed sinyalinde sızıntı: {parca}")
        self.assertLess(len(disari[0]), 200, "sinyal metni sabit olmalı")

    def test_async_ve_sync_ayni_guvenli_hatti_kullanir(self):
        for ad, calistir in (("async", lambda s: s._run("t")),
                             ("sync", lambda s: s._run_sync("t"))):
            with self.subTest(yol=ad):
                self.log.kayitlar.clear()
                svc = self._servis()
                disari = []
                svc.backup_failed.connect(lambda m: disari.append(m))
                with mock.patch.object(bm, "create_backup", side_effect=_hata()):
                    if ad == "sync":
                        calistir(svc)
                    else:
                        w = bm._BackupWorker(str(self.yedek_dir), "t")
                        w.failed.connect(svc._on_backup_failed)
                        with mock.patch.object(bm, "create_backup",
                                               side_effect=_hata()):
                            w.run()
                self.assertEqual(len(disari), 1, "güvenli sinyal üretilmedi")
                self._sizinti_yok(f" ({ad})")
                self.assertEqual(self.log.guvenli_log_sayisi, 1,
                                 f"{ad}: güvenli log 1 kez değil")

    def test_meta_ve_cleanup_loglari_ham_veri_tasimaz(self):
        # bozuk meta → okuma hatası
        self.meta.write_text("{bozuk", encoding="utf-8")
        bm._load_meta()
        # yazma hatası
        # `_save_meta` LOGLAMADAN yeniden fırlatır; güvenli logu ve aşama
        # ayrımını çağıran yapar (`_manual` / `_save_auto` / `_on_backup_done`).
        with mock.patch.object(Path, "write_text", side_effect=_hata(OSError)):
            with self.assertRaises(OSError):
                bm._save_meta({"x": 1})
        # cleanup hatası
        with mock.patch.object(Path, "glob", side_effect=_hata(OSError)):
            self._servis()._cleanup(str(self.yedek_dir))
        self._sizinti_yok(" (meta/cleanup)")
        self.assertNotIn("exc_info", self.log.birlesik)

    def test_main_window_tuketicisi_yeniden_loglamaz(self):
        import ui.main_window as mw
        kaynak = inspect.getsource(mw.MainWindow)
        satirlar = [s for s in kaynak.splitlines() if "backup_failed" in s]
        self.assertTrue(satirlar, "backup_failed tüketicisi yok")
        for s in satirlar:
            self.assertNotIn("logger", s,
                             f"tüketici hatayı yeniden logluyor: {s}")

    def test_main_window_yedek_yolunu_loglamaz(self):
        import ui.main_window as mw
        kaynak = inspect.getsource(mw.MainWindow._on_backup_done)
        for satir in kaynak.splitlines():
            if "logger" in satir:
                self.assertNotIn("path", satir,
                                 f"yedek yolu loglanıyor: {satir}")


# ── 2. Manuel yedek ve metadata aşamaları ───────────────────────────────

class MetadataAsamaTests(_Temel):

    def _dialog(self):
        d = bm.BackupDialog.__new__(bm.BackupDialog)
        QDialog.__init__(d)          # BackupDialog QDialog türevidir
        self.addCleanup(d.deleteLater)
        d._meta = dict(bm._load_meta())
        d.lbl_last = mock.MagicMock()
        d.chk_auto = mock.MagicMock(); d.chk_auto.isChecked.return_value = True
        d.iv_combo = mock.MagicMock(); d.iv_combo.currentIndex.return_value = 1
        d.iv_combo.currentText.return_value = "30 dk"
        d._set_dir_text = mock.MagicMock()
        d.settings_changed = mock.MagicMock()
        return d

    def test_manuel_yedek_hatasi_guvenli(self):
        d = self._dialog()
        with mock.patch.object(bm.QFileDialog, "getExistingDirectory",
                               staticmethod(lambda *a, **k: str(self.yedek_dir))), \
             mock.patch.object(bm, "create_backup", side_effect=_hata(OSError)):
            d._manual()
        self._sizinti_yok(" (manuel)")
        self.assertEqual(self.log.guvenli_log_sayisi, 1)

    def test_yedek_olustu_metadata_hatasi_kismi_basari(self):
        d = self._dialog()
        cagri = []
        with mock.patch.object(bm.QFileDialog, "getExistingDirectory",
                               staticmethod(lambda *a, **k: str(self.yedek_dir))), \
             mock.patch.object(bm, "create_backup",
                               side_effect=lambda dd: cagri.append(dd) or "x.zip"), \
             mock.patch.object(bm, "_save_meta", side_effect=_hata(OSError)):
            d._manual()
        self.assertEqual(len(cagri), 1, "create_backup tekrarlandı")
        metin = self._metinler()
        self.assertNotRegex(metin, r"(?i)yedekleme ba[şs]ar[ıi]s[ıi]z",
                            "oluşturulmuş yedek inkâr edildi")
        self.assertRegex(metin, r"(?i)yedek (dosyas[ıi] )?olu[şs]turuldu|yedek al[ıi]nd",
                         "tamamlanan yedekleme aşaması kullanıcıya söylenmedi")
        self._sizinti_yok(" (meta)")

    def test_otomatik_ayar_metadata_hatasinda_basari_yok(self):
        d = self._dialog()
        with mock.patch.object(bm, "_save_meta", side_effect=_hata(OSError)):
            d._save_auto()
        self.assertEqual(d.settings_changed.emit.call_count, 0,
                         "metadata yazılamadığı hâlde settings_changed yayıldı")
        for baslik, _m in self.kutular:
            self.assertNotIn("Kaydedildi", baslik)
        self._sizinti_yok(" (auto ayar)")

    def test_arka_plan_yedek_metadata_hatasinda_basari_korunur(self):
        svc = self._servis()
        tamam = []
        svc.backup_done.connect(lambda p: tamam.append(p))
        zip_yolu = self.yedek_dir / "backup_x.zip"
        zip_yolu.write_bytes(b"z")
        with mock.patch.object(bm, "_save_meta", side_effect=_hata(OSError)):
            svc._on_backup_done(str(zip_yolu), "test")
        self.assertEqual(len(tamam), 1, "metadata hatası yedek başarısını iptal etti")
        self._sizinti_yok(" (arka plan meta)")


# ── 3-4. Geri yükleme durum sözleşmesi ve rollback ──────────────────────

class RestoreDurumTests(_Temel):

    def test_preflight_hatasinda_hedefe_yazilmaz(self):
        self._hedefleri_kur()
        once_db = self.db.read_bytes()
        once_cfg = self.cfg.read_bytes()
        bozuk = self.yedek_dir / "bozuk.zip"
        bozuk.write_bytes(b"bu bir zip degil")
        with self.assertRaises(Exception) as ctx:
            bm.restore_backup(str(bozuk))
        self.assertEqual(getattr(ctx.exception, "durum", None), "preflight_failed",
                         "preflight durumu ayrılmıyor")
        self.assertEqual(self.db.read_bytes(), once_db, "DB değişti")
        self.assertEqual(self.cfg.read_bytes(), once_cfg, "cfg değişti")

    def test_yazma_hatasinda_rollback_ve_durum(self):
        self._hedefleri_kur(logo=True)
        once = {p: p.read_bytes() for p in (self.cfg, self.logo)}
        db_once = _db_isaret(self.db)
        z = self._zip_yap()
        # DB yazıldıktan SONRA optional kopyalamada hata
        gercek_copy = bm.shutil.copy2
        veri_kok = str(self.veri)

        bozuldu = {"bir_kez": False}

        def _bozuk_copy(src, dst, *a, **k):
            # YALNIZ apply aşamasında ve TEK KEZ boz: preflight'taki rollback
            # kopyalaması ve rollback'in kendisi etkilenmemeli.
            if str(dst).startswith(veri_kok) and not bozuldu["bir_kez"]:
                bozuldu["bir_kez"] = True
                raise OSError(13, "Permission denied", str(dst))
            return gercek_copy(src, dst, *a, **k)

        with mock.patch.object(bm.shutil, "copy2", _bozuk_copy):
            with self.assertRaises(Exception) as ctx:
                bm.restore_backup(str(z))
        self.assertEqual(getattr(ctx.exception, "durum", None), "rolled_back")
        for p, icerik in once.items():
            self.assertEqual(p.read_bytes(), icerik,
                             f"{p.name} rollback sonrası eski hâline dönmedi")
        self.assertEqual(_db_isaret(self.db), db_once,
                         "DB rollback sonrası ÖNCEKİ veriye dönmedi")
        self.assertEqual(db_once, [11], "test kurulumu bozuk")

    def test_baslangicta_db_yoksa_rollback_yeni_dbyi_siler(self):
        self.assertFalse(self.db.exists())
        z = self._zip_yap(ekler=("company.cfg",))

        def _bozuk_copy(src, dst, *a, **k):
            raise OSError(13, "Permission denied", str(dst))

        with mock.patch.object(bm.shutil, "copy2", _bozuk_copy):
            with self.assertRaises(Exception):
                bm.restore_backup(str(z))
        self.assertFalse(self.db.exists(),
                         "başlangıçta olmayan DB rollback ile silinmedi")

    def test_baslangicta_olmayan_optional_dosyalar_geri_gelmez(self):
        _db_yaz(self.db)
        self.assertFalse(self.logo.exists())
        z = self._zip_yap(ekler=("company.cfg", "logo.png"))
        gercek = bm.shutil.copy2
        veri_kok = str(self.veri)
        yazilan = {"n": 0}

        def _bozuk(src, dst, *a, **k):
            if str(dst).startswith(veri_kok):
                yazilan["n"] += 1
                if yazilan["n"] >= 2:      # logo yazıldıktan SONRA boz
                    raise OSError(13, "Permission denied", str(dst))
            return gercek(src, dst, *a, **k)

        with mock.patch.object(bm.shutil, "copy2", _bozuk):
            with self.assertRaises(Exception):
                bm.restore_backup(str(z))
        self.assertFalse(self.logo.exists(),
                         "başlangıçta olmayan logo rollback sonrası kaldı")

    def test_rollback_ilk_hatada_durmaz(self):
        self._hedefleri_kur(logo=True)
        z = self._zip_yap()
        denenen = []
        gercek = bm.shutil.copy2
        veri_kok = str(self.veri)
        durum = {"apply_bozuldu": False}

        def _izle(src, dst, *a, **k):
            if str(dst).startswith(veri_kok):
                denenen.append(str(dst))
                if not durum["apply_bozuldu"]:
                    durum["apply_bozuldu"] = True     # apply aşamasını boz
                    raise OSError(13, "Permission denied", str(dst))
            return gercek(src, dst, *a, **k)

        with mock.patch.object(bm.shutil, "copy2", _izle):
            with self.assertRaises(Exception):
                bm.restore_backup(str(z))
        geri = [d for d in denenen if str(self.veri) in d]
        self.assertGreaterEqual(len(geri), 2,
                                "rollback ilk hatadan sonra durdu")

    def test_rollback_basarisiz_durumu(self):
        self._hedefleri_kur()
        z = self._zip_yap()

        def _her_zaman_hata(*a, **k):
            raise OSError(13, "Permission denied", "x")

        # Preflight ETKİLENMEZ: yalnız DB YAZMA (apply + rollback) bozulur,
        # böylece rollback'in kendisi de tamamlanamaz.
        with mock.patch.object(bm, "_restore_database_snapshot",
                               side_effect=_her_zaman_hata):
            with self.assertRaises(Exception) as ctx:
                bm.restore_backup(str(z))
        self.assertEqual(getattr(ctx.exception, "durum", None), "rollback_failed",
                         f"nedenler={[type(n).__name__ for n in getattr(ctx.exception,'nedenler',[])]}")

    def test_ozel_hata_metni_sabit_ve_guvenli(self):
        self._hedefleri_kur()
        bozuk = self.yedek_dir / "bozuk.zip"
        bozuk.write_bytes(b"degil")
        try:
            bm.restore_backup(str(bozuk))
        except Exception as exc:                               # noqa: BLE001
            metin = str(exc)
        for parca in SIZINTI:
            self.assertNotIn(parca, metin,
                             f"istisna __str__ sızıntı içeriyor: {parca}")
        self.assertLess(len(metin), 200)

    def test_tam_basarida_dogru_veri(self):
        self._hedefleri_kur(logo=True)
        z = self._zip_yap()
        self.assertIs(bm.restore_backup(str(z)), True)
        self.assertEqual(self.cfg.read_bytes(), b"YEDEK-company.cfg")
        self.assertEqual(_db_isaret(self.db), [22], "DB yedekten gelmedi")
        self.assertEqual(self.log.guvenli_log_sayisi, 0)


# ── 5. Kullanıcı mesajları ve restart ───────────────────────────────────

class KullaniciMesajTests(_Temel):

    def _dialog(self):
        d = bm.BackupDialog.__new__(bm.BackupDialog)
        QDialog.__init__(d)          # BackupDialog QDialog türevidir
        self.addCleanup(d.deleteLater)
        d._meta = dict(bm._load_meta())
        self.restart_sayisi = []
        d._restart_app = lambda: self.restart_sayisi.append(1)
        return d

    def _restore_et(self, hata):
        d = self._dialog()
        z = self.yedek_dir / "backup_x.zip"
        z.write_bytes(b"z")
        with mock.patch.object(bm.QFileDialog, "getOpenFileName",
                               staticmethod(lambda *a, **k: (str(z), ""))), \
             mock.patch.object(bm, "restore_backup", side_effect=hata):
            d._restore()
        return d

    def test_rollback_basarisizda_veri_korundu_denmez(self):
        h = bm.RestoreError("rollback_failed") if hasattr(bm, "RestoreError") \
            else _hata()
        self._restore_et(h)
        metin = self._metinler()
        self.assertNotRegex(metin, r"(?i)verileriniz korundu|geri geldi|geri getirildi",
                            "belirsiz durumda veri güvencesi verildi")
        self.assertRegex(metin, r"(?i)do[ğg]rulanamad|belirsiz")
        self.assertEqual(self.restart_sayisi, [], "belirsiz durumda restart yapıldı")

    def test_rollback_basarilida_durum_dogru_anlatilir(self):
        h = bm.RestoreError("rolled_back") if hasattr(bm, "RestoreError") else _hata()
        self._restore_et(h)
        metin = self._metinler()
        self.assertRegex(metin, r"(?i)geri getirildi|[öo]nceki durum")
        self.assertEqual(self.restart_sayisi, [])

    def test_preflight_hatasinda_baslamadigi_soylenir(self):
        h = bm.RestoreError("preflight_failed") if hasattr(bm, "RestoreError") \
            else _hata()
        self._restore_et(h)
        self.assertRegex(self._metinler(),
                         r"(?i)ba[şs]lamad|de[ğg]i[şs]tirilmedi")
        self.assertEqual(self.restart_sayisi, [])

    def test_tam_basarida_restart_tam_bir_kez(self):
        d = self._dialog()
        z = self.yedek_dir / "backup_x.zip"; z.write_bytes(b"z")
        with mock.patch.object(bm.QFileDialog, "getOpenFileName",
                               staticmethod(lambda *a, **k: (str(z), ""))), \
             mock.patch.object(bm, "restore_backup", return_value=True):
            d._restore()
        self.assertEqual(self.restart_sayisi, [1], "restart tam bir kez değil")

    def test_startup_yolu_ayni_semantik(self):
        h = bm.RestoreError("rollback_failed") if hasattr(bm, "RestoreError") \
            else _hata()
        self.yedek_dir.mkdir(parents=True, exist_ok=True)
        (self.yedek_dir / "backup_a.zip").write_bytes(b"z")
        with mock.patch.object(bm, "restore_backup", side_effect=h):
            bm.check_and_restore_on_startup(None)
        metin = self._metinler()
        self.assertNotRegex(metin, r"(?i)verileriniz korundu|geri geldi")
        self._sizinti_yok(" (startup)")

    def test_arayuzdeki_mutlak_iddia_kaldirildi(self):
        kaynak = inspect.getsource(bm)
        self.assertNotIn("Bir sorun olursa orijinal verileriniz otomatik olarak geri gelir.",
                         kaynak, "koşulsuz veri güvencesi metni duruyor")


# ── 7. TEK LOG sözleşmesi ───────────────────────────────────────────────

class _SayacKarisimi:
    """`op_hata.logla` çağrılarını sayar — diyalog katmanı da bunu kullanır."""

    def _log_sayaci(self):
        cagrilar = []
        gercek = op_hata_mod.logla

        def _sar(exc, islem, **k):
            cagrilar.append((type(exc).__name__, islem))
            return gercek(exc, islem, **k)

        mock.patch.object(op_hata_mod, "logla", _sar).start()
        return cagrilar


class TekLogTests(_Temel, _SayacKarisimi):
    """Aynı istisna TAM BİR KEZ güvenli loglanır.

    `_save_meta` loglayıp sonra çağıran diyalog altyapısı yeniden loglarsa
    aynı hata iki satır üretir; log gürültüsü gerçek arızayı gizler.
    """

    def _dialog(self):
        d = bm.BackupDialog.__new__(bm.BackupDialog)
        QDialog.__init__(d)
        self.addCleanup(d.deleteLater)
        d._meta = dict(bm._load_meta())
        d.lbl_last = mock.MagicMock()
        d.chk_auto = mock.MagicMock(); d.chk_auto.isChecked.return_value = True
        d.iv_combo = mock.MagicMock(); d.iv_combo.currentIndex.return_value = 1
        d.iv_combo.currentText.return_value = "30 dk"
        d._set_dir_text = mock.MagicMock()
        d.settings_changed = mock.MagicMock()
        d._restart_app = mock.MagicMock()
        return d

    def test_save_meta_kendisi_loglamaz(self):
        """Aşama ayrımını ÇAĞIRAN yapar; `_save_meta` yalnız fırlatır."""
        cagrilar = self._log_sayaci()
        with mock.patch.object(Path, "write_text", side_effect=_hata(OSError)):
            with self.assertRaises(OSError):
                bm._save_meta({"x": 1})
        self.assertEqual(len(cagrilar), 0, f"_save_meta kendisi logladı: {cagrilar}")

    def test_manuel_metadata_hatasi_tek_log(self):
        cagrilar = self._log_sayaci()
        d = self._dialog()
        with mock.patch.object(bm.QFileDialog, "getExistingDirectory",
                               staticmethod(lambda *a, **k: str(self.yedek_dir))), \
             mock.patch.object(bm, "create_backup", side_effect=lambda dd: "x.zip"), \
             mock.patch.object(Path, "write_text", side_effect=_hata(OSError)):
            d._manual()
        self.assertEqual(len(cagrilar), 1, f"tek log değil: {cagrilar}")

    def test_otomatik_ayar_metadata_hatasi_tek_log(self):
        cagrilar = self._log_sayaci()
        d = self._dialog()
        with mock.patch.object(Path, "write_text", side_effect=_hata(OSError)):
            d._save_auto()
        self.assertEqual(len(cagrilar), 1, f"tek log değil: {cagrilar}")

    def test_arka_plan_metadata_hatasi_tek_log(self):
        cagrilar = self._log_sayaci()
        svc = self._servis()
        tamam, temizlik = [], []
        svc.backup_done.connect(lambda p: tamam.append(p))
        mock.patch.object(bm.AutoBackupService, "_cleanup",
                          lambda s, d, keep=20: temizlik.append(d)).start()
        z = self.yedek_dir / "backup_x.zip"; z.write_bytes(b"z")
        with mock.patch.object(Path, "write_text", side_effect=_hata(OSError)):
            svc._on_backup_done(str(z), "test")
        self.assertEqual(len(cagrilar), 1, f"tek log değil: {cagrilar}")
        self.assertEqual(len(tamam), 1, "backup_done yayılmadı")
        self.assertEqual(len(temizlik), 1, "cleanup çalışmadı")

    # ── `_save_auto` mesaj parametreleri ────────────────────────────────
    def test_otomatik_ayar_mesaji_tekrar_etmiyor(self):
        d = self._dialog()
        with mock.patch.object(Path, "write_text", side_effect=_hata(OSError)):
            d._save_auto()
        metin = self._metinler()
        self.assertEqual(metin.lower().count("kaydedilemedi"), 1,
                         f"mesaj tekrar ediyor: {metin!r}")
        self._sizinti_yok(" (auto ayar mesajı)")

    def test_otomatik_ayar_kategori_sozlesmesi(self):
        """`tur` kısa KATEGORİ, `islem` kısa EYLEM olmalı."""
        yakalanan = {}

        def _sahte(parent, baslik, exc, tur, islem="kaydet", **k):
            yakalanan["tur"] = tur
            yakalanan["islem"] = islem

        d = self._dialog()
        with mock.patch.object(bm.hata_diyalogu, "hata_goster", _sahte), \
             mock.patch.object(Path, "write_text", side_effect=_hata(OSError)):
            d._save_auto()
        self.assertEqual(yakalanan.get("tur"), "Otomatik yedekleme ayarı")
        self.assertEqual(yakalanan.get("islem"), "kaydet")


# ── 8. Preflight sınırı ve beklenmeyen UI fallback'leri ─────────────────

class PreflightVeFallbackTests(_Temel, _SayacKarisimi):

    def test_olmayan_zip_preflight_durumu(self):
        cagrilar = self._log_sayaci()
        self._hedefleri_kur()
        yok = self.yedek_dir / "hic_yok.zip"
        with self.assertRaises(bm.RestoreError) as ctx:
            bm.restore_backup(str(yok))
        self.assertEqual(ctx.exception.durum, bm.PREFLIGHT_FAILED)
        self.assertEqual(len(cagrilar), 1, f"tek güvenli log değil: {cagrilar}")
        self.assertNotIn(str(yok), str(ctx.exception))
        self.assertNotIn("hic_yok.zip", self.log.birlesik)

    def test_gecici_klasor_hatasi_da_preflight(self):
        """Hedef verilere DOKUNULMADAN oluşan başlangıç hatası da preflight'tır."""
        self._hedefleri_kur()
        z = self._zip_yap()
        db_once = _db_isaret(self.db)
        with mock.patch.object(bm.tempfile, "TemporaryDirectory",
                               side_effect=_hata(OSError)):
            with self.assertRaises(bm.RestoreError) as ctx:
                bm.restore_backup(str(z))
        self.assertEqual(ctx.exception.durum, bm.PREFLIGHT_FAILED)
        self.assertEqual(_db_isaret(self.db), db_once, "hedef DB değişti")

    def test_preflight_metni_dosyaya_indirgemiyor(self):
        """Preflight, ROLLBACK SNAPSHOT hazırlığında da düşebilir."""
        metin = bm._RESTORE_METINLERI[bm.PREFLIGHT_FAILED].lower()
        self.assertNotIn("yedek dosyası doğrulanamadı", metin,
                         "preflight nedeni yalnız dosyaya indirgeniyor")
        self.assertIn("mevcut verileriniz değiştirilmedi", metin)

    def test_snapshot_hatasi_preflight_ve_veri_dokunulmaz(self):
        self._hedefleri_kur()
        db_once = _db_isaret(self.db)
        cfg_once = self.cfg.read_bytes()
        z = self._zip_yap()
        with mock.patch.object(bm, "_create_database_snapshot",
                               side_effect=_hata(OSError)):
            with self.assertRaises(bm.RestoreError) as ctx:
                bm.restore_backup(str(z))
        self.assertEqual(ctx.exception.durum, bm.PREFLIGHT_FAILED)
        self.assertEqual(_db_isaret(self.db), db_once)
        self.assertEqual(self.cfg.read_bytes(), cfg_once)

    # ── beklenmeyen UI fallback'leri ────────────────────────────────────
    def test_acilis_fallback_guvenli_loglar(self):
        cagrilar = self._log_sayaci()
        self.db.unlink(missing_ok=True)
        self._zip_yap("backup_a.zip")
        with mock.patch.object(bm, "restore_backup", side_effect=_hata()):
            self.assertIs(bm.check_and_restore_on_startup(None), False)
        self.assertEqual(len(cagrilar), 1, f"tek güvenli log değil: {cagrilar}")
        self._sizinti_yok(" (açılış fallback)")

    def test_acilis_restore_error_yeniden_loglanmaz(self):
        cagrilar = self._log_sayaci()
        self.db.unlink(missing_ok=True)
        self._zip_yap("backup_a.zip")
        hata = bm.RestoreError(bm.ROLLED_BACK, [])
        with mock.patch.object(bm, "restore_backup", side_effect=hata):
            self.assertIs(bm.check_and_restore_on_startup(None), False)
        self.assertEqual(len(cagrilar), 0,
                         f"RestoreError alt katmandan sonra tekrar loglandı: {cagrilar}")

    def _restore_diyalogu(self):
        d = bm.BackupDialog.__new__(bm.BackupDialog)
        QDialog.__init__(d)
        self.addCleanup(d.deleteLater)
        d._restart_app = mock.MagicMock()
        return d

    def test_diyalog_restore_fallback_guvenli_loglar(self):
        cagrilar = self._log_sayaci()
        d = self._restore_diyalogu()
        z = self._zip_yap()
        with mock.patch.object(bm.QFileDialog, "getOpenFileName",
                               staticmethod(lambda *a, **k: (str(z), ""))), \
             mock.patch.object(bm, "restore_backup", side_effect=_hata()):
            d._restore()
        self.assertEqual(len(cagrilar), 1, f"tek güvenli log değil: {cagrilar}")
        self.assertEqual(d._restart_app.call_count, 0, "hatada yeniden başlatıldı")
        self._sizinti_yok(" (diyalog fallback)")

    def test_diyalog_restore_error_yeniden_loglanmaz(self):
        cagrilar = self._log_sayaci()
        d = self._restore_diyalogu()
        z = self._zip_yap()
        hata = bm.RestoreError(bm.ROLLBACK_FAILED, [])
        with mock.patch.object(bm.QFileDialog, "getOpenFileName",
                               staticmethod(lambda *a, **k: (str(z), ""))), \
             mock.patch.object(bm, "restore_backup", side_effect=hata):
            d._restore()
        self.assertEqual(len(cagrilar), 0, f"tekrar loglandı: {cagrilar}")
        self.assertEqual(d._restart_app.call_count, 0)


TEMIZLIK_ISLEMI = "Geri yukleme gecici temizle"


class _PatlayanGecici:
    """`__enter__` ve `.name` erişimi hata veren sahte TemporaryDirectory.

    Uygulama ister `with` ile ister `.name` ile kullansın, geçici kökün hiç
    elde edilememesi HER DURUMDA preflight sözleşmesine girmelidir.
    """

    def __init__(self, *a, **k):
        pass

    @property
    def name(self):
        raise OSError(13, "Permission denied", "x")

    def __enter__(self):
        raise OSError(13, "Permission denied", "x")

    def __exit__(self, *a):
        return False

    def cleanup(self):
        pass


class GeciciKlasorTests(_Temel, _SayacKarisimi):
    """Geçici çalışma klasörünün kendisi kaynaklı hatalar.

    * Kök veya alt klasör HİÇ oluşturulamadıysa hedef verilere dokunulmamıştır
      → `preflight_failed`.
    * Temizleme (cleanup) hatası İŞİN SONUCUNU maskelemez: tamamlanmış geri
      yükleme "başarısız" olmaz, oluşmuş `RestoreError.durum` değişmez.
    """

    def _temizlik_loglari(self, cagrilar):
        return [c for c in cagrilar if c[1] == TEMIZLIK_ISLEMI]

    def _patlayan_temizlik(self, gercek_sinif):
        """Gerçek geçici klasörü kullanır ama TEMİZLİKTE hata verir."""

        class _Sinif(gercek_sinif):
            def cleanup(inner):
                super().cleanup()
                raise OSError(13, "Permission denied", "x")

            def __exit__(inner, *a):
                inner.cleanup()
                return False

        return _Sinif

    # ── 1) context girişi / kök oluşturma hatası ────────────────────────
    def test_gecici_kok_girisi_hatasi_preflight(self):
        cagrilar = self._log_sayaci()
        self._hedefleri_kur()
        db_once = _db_isaret(self.db)
        cfg_once = self.cfg.read_bytes()
        z = self._zip_yap()
        with mock.patch.object(bm.tempfile, "TemporaryDirectory", _PatlayanGecici):
            with self.assertRaises(bm.RestoreError) as ctx:
                bm.restore_backup(str(z))
        self.assertEqual(ctx.exception.durum, bm.PREFLIGHT_FAILED)
        self.assertEqual(len(cagrilar), 1, f"güvenli log tam 1 değil: {cagrilar}")
        self.assertEqual(_db_isaret(self.db), db_once, "hedef DB değişti")
        self.assertEqual(self.cfg.read_bytes(), cfg_once, "hedef cfg değişti")
        self._sizinti_yok(" (gecici kok)")

    # ── 2) alt klasör oluşturma hatası ──────────────────────────────────
    def test_alt_klasor_hatasi_preflight(self):
        cagrilar = self._log_sayaci()
        self._hedefleri_kur()
        db_once = _db_isaret(self.db)
        cfg_once = self.cfg.read_bytes()
        z = self._zip_yap()
        with mock.patch.object(Path, "mkdir", side_effect=_hata(OSError)):
            with self.assertRaises(bm.RestoreError) as ctx:
                bm.restore_backup(str(z))
        self.assertEqual(ctx.exception.durum, bm.PREFLIGHT_FAILED)
        self.assertEqual(len(cagrilar), 1, f"güvenli log tam 1 değil: {cagrilar}")
        self.assertEqual(_db_isaret(self.db), db_once, "hedef DB değişti")
        self.assertEqual(self.cfg.read_bytes(), cfg_once, "hedef cfg değişti")
        self._sizinti_yok(" (alt klasor)")

    # ── 3) başarılı restore + cleanup hatası ────────────────────────────
    def test_basarili_restore_cleanup_hatasini_yutmaz(self):
        cagrilar = self._log_sayaci()
        self._hedefleri_kur()
        z = self._zip_yap()
        sinif = self._patlayan_temizlik(bm.tempfile.TemporaryDirectory)
        with mock.patch.object(bm.tempfile, "TemporaryDirectory", sinif):
            self.assertIs(bm.restore_backup(str(z)), True,
                          "temizlik hatası tamamlanmış geri yüklemeyi iptal etti")
        self.assertEqual(_db_isaret(self.db), [22], "yeni veri yerinde değil")
        self.assertEqual(self.cfg.read_bytes(), b"YEDEK-company.cfg")
        self.assertEqual(len(self._temizlik_loglari(cagrilar)), 1,
                         f"temizlik hatası tam bir kez loglanmadı: {cagrilar}")
        self._sizinti_yok(" (basarili cleanup)")

    def test_basarili_yolda_restart_tam_bir_kez(self):
        d = bm.BackupDialog.__new__(bm.BackupDialog)
        QDialog.__init__(d)
        self.addCleanup(d.deleteLater)
        d._restart_app = mock.MagicMock()
        self._hedefleri_kur()
        z = self._zip_yap()
        sinif = self._patlayan_temizlik(bm.tempfile.TemporaryDirectory)
        with mock.patch.object(bm.QFileDialog, "getOpenFileName",
                               staticmethod(lambda *a, **k: (str(z), ""))), \
             mock.patch.object(bm.tempfile, "TemporaryDirectory", sinif):
            d._restore()
        self.assertEqual(d._restart_app.call_count, 1,
                         "başarı yolunda restart tam bir kez yapılmadı")

    # ── 4) RestoreError + cleanup hatası ────────────────────────────────
    def test_cleanup_hatasi_restore_durumunu_degistirmez(self):
        cagrilar = self._log_sayaci()
        self._hedefleri_kur()
        z = self._zip_yap()
        db_once = _db_isaret(self.db)
        gercek_copy = bm.shutil.copy2
        veri_kok = str(self.veri)
        bozuldu = {"bir_kez": False}

        def _bozuk_copy(src, dst, *a, **k):
            if str(dst).startswith(veri_kok) and not bozuldu["bir_kez"]:
                bozuldu["bir_kez"] = True
                raise OSError(13, "Permission denied", str(dst))
            return gercek_copy(src, dst, *a, **k)

        sinif = self._patlayan_temizlik(bm.tempfile.TemporaryDirectory)
        with mock.patch.object(bm.tempfile, "TemporaryDirectory", sinif), \
             mock.patch.object(bm.shutil, "copy2", _bozuk_copy):
            with self.assertRaises(bm.RestoreError) as ctx:
                bm.restore_backup(str(z))
        self.assertEqual(ctx.exception.durum, bm.ROLLED_BACK,
                         "temizlik hatası asıl durumu değiştirdi")
        self.assertEqual(_db_isaret(self.db), db_once, "rollback tamamlanmadı")
        self.assertEqual(len(self._temizlik_loglari(cagrilar)), 1,
                         f"temizlik hatası tam bir kez loglanmadı: {cagrilar}")
        self._sizinti_yok(" (rollback + cleanup)")

    def test_cleanup_hatasinda_restart_yok(self):
        d = bm.BackupDialog.__new__(bm.BackupDialog)
        QDialog.__init__(d)
        self.addCleanup(d.deleteLater)
        d._restart_app = mock.MagicMock()
        z = self._zip_yap()
        hata = bm.RestoreError(bm.ROLLED_BACK, [])
        with mock.patch.object(bm.QFileDialog, "getOpenFileName",
                               staticmethod(lambda *a, **k: (str(z), ""))), \
             mock.patch.object(bm, "restore_backup", side_effect=hata):
            d._restore()
        self.assertEqual(d._restart_app.call_count, 0)


# ── 9. main_window içindeki kalan backup ham logları ────────────────────

class AnaPencereBackupTests(_Temel, _SayacKarisimi):

    def _pencere(self, patlat=None):
        import ui.main_window as mw
        w = mw.MainWindow.__new__(mw.MainWindow)
        QMainWindow.__init__(w)          # MainWindow QMainWindow türevidir
        self.addCleanup(w.deleteLater)
        w.pages = {}
        w._shutdown_prepared = False
        w.show_status = mock.MagicMock()
        w._navigate = mock.MagicMock()
        w._await_running_workers = mock.MagicMock(return_value=True)
        w._backup_svc = mock.MagicMock()
        if patlat is not None:
            w._backup_svc.trigger_now.side_effect = patlat
        return w

    def _kapat(self, w):
        import core.restart as restart
        with mock.patch.object(restart, "restart_requested",
                               staticmethod(lambda: False)):
            w.closeEvent(mock.MagicMock())

    def test_kapanma_yedegi_ham_loglamaz(self):
        cagrilar = self._log_sayaci()
        self._kapat(self._pencere(patlat=_hata()))
        self._sizinti_yok(" (kapanma yedeği)")
        self.assertEqual(len(cagrilar), 1, f"güvenli log tam 1 değil: {cagrilar}")

    def test_kapanma_yedegi_basarisizken_basari_yazilmaz(self):
        self._kapat(self._pencere(patlat=_hata()))
        self.assertNotIn("Kapanma yedeği alındı", self.log.birlesik,
                         "başarısız yedeğe başarı dendi")

    def test_kapanma_kosulsuz_basari_logu_yok(self):
        """`trigger_now` hatayı İÇERİDE yakalar; dışarıda başarı BİLİNEMEZ."""
        import ui.main_window as mw
        self.assertNotIn("Kapanma yedeği alındı",
                         inspect.getsource(mw.MainWindow.closeEvent),
                         "koşulsuz başarı logu duruyor")

    def test_teklif_kaydi_yedek_hatasi_ham_loglamaz(self):
        cagrilar = self._log_sayaci()
        self._pencere(patlat=_hata())._on_offer_saved()
        self._sizinti_yok(" (teklif kaydı yedeği)")
        self.assertEqual(len(cagrilar), 1, f"güvenli log tam 1 değil: {cagrilar}")

    def test_teklif_kaydi_basarisi_inkar_edilmiyor(self):
        w = self._pencere(patlat=_hata())
        w._on_offer_saved()
        metinler = " ".join(str(c.args[0]) for c in w.show_status.call_args_list)
        self.assertIn("Teklif başarıyla kaydedildi", metinler,
                      "yedek hatası tamamlanmış teklif kaydını inkâr etti")
        self.assertEqual(w._navigate.call_count, 1)

    def test_main_window_backup_ham_log_kalmadi(self):
        import ui.main_window as mw
        for fn in (mw.MainWindow.closeEvent, mw.MainWindow._on_offer_saved):
            for satir in inspect.getsource(fn).splitlines():
                if "logger." in satir and "%s" in satir:
                    for yasak in (", e)", ", exc)"):
                        self.assertNotIn(yasak, satir, f"ham log argümanı: {satir}")


# ── 6. Kaynak koruması ──────────────────────────────────────────────────

class KaynakKorumasiTests(unittest.TestCase):

    def test_ham_istisna_gosterimi_yok(self):
        kaynak = inspect.getsource(bm)
        for yasak in ("{e}", "{exc}", "exc_info=True"):
            self.assertNotIn(yasak, kaynak, f"ham istisna gösterimi: {yasak}")

    def test_ham_logger_cagrilari_kalmadi(self):
        for satir in inspect.getsource(bm).splitlines():
            if "logger." in satir and "%s" in satir:
                for yasak in (", e)", ", exc)", ", error)"):
                    self.assertNotIn(satir[-8:], yasak,
                                     f"ham log argümanı: {satir}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
