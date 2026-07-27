"""O7 — test oturumunun kullanıcı ortamından tam yalıtıldığını sabitler.

`tests/conftest.py` eskiden yalnız LOCALAPPDATA'yı yönlendiriyordu. USERPROFILE
yönlendirilmediği için `core/app_paths.py` içindeki
`BACKUP_DIR = Path.home() / "Documents" / ...` GERÇEK kullanıcı profilinde
çözülüyor ve import yan etkisi olarak orada klasör oluşturuluyordu; `tempfile`
de gerçek %TEMP%'e yazıyordu.

Bu testler yönlendirmenin proje importlarından ÖNCE yapıldığını ve her
kullanıcı yolunun tek bir geçici oturum kökü altında kaldığını doğrular.
Alt süreç kullanan testlerin kendi (daha sıkı) izolasyonu ayrıdır ve buradan
etkilenmez.
"""
import os
import tempfile
import unittest
from pathlib import Path

from tests.conftest import OTURUM_KOKU


def _altinda(yol) -> bool:
    """`yol` oturum kökünün altında mı? (sembolik/8.3 farkları çözülerek)"""
    try:
        return Path(yol).resolve().is_relative_to(OTURUM_KOKU)
    except (OSError, ValueError):
        return False


class EnvIsolationTests(unittest.TestCase):
    """Ortam değişkenlerinin tamamı tek geçici kök altında olmalı."""

    def test_session_root_exists(self):
        self.assertTrue(OTURUM_KOKU.is_dir())

    def test_localappdata_is_redirected(self):
        self.assertTrue(_altinda(os.environ["LOCALAPPDATA"]),
                        os.environ["LOCALAPPDATA"])

    def test_appdata_is_redirected(self):
        self.assertTrue(_altinda(os.environ["APPDATA"]),
                        os.environ["APPDATA"])

    def test_userprofile_is_redirected(self):
        self.assertTrue(_altinda(os.environ["USERPROFILE"]),
                        os.environ["USERPROFILE"])

    def test_home_is_redirected(self):
        self.assertTrue(_altinda(os.environ["HOME"]), os.environ["HOME"])

    def test_tmp_and_temp_are_redirected(self):
        for ad in ("TMP", "TEMP"):
            self.assertTrue(_altinda(os.environ[ad]),
                            f"{ad}={os.environ[ad]}")

    def test_homedrive_homepath_are_consistent(self):
        """HOMEDRIVE + HOMEPATH birleşimi geçici profili vermeli."""
        if os.name != "nt":
            self.skipTest("yalnız Windows")
        birlesim = os.path.join(os.environ["HOMEDRIVE"],
                                os.environ["HOMEPATH"])
        self.assertTrue(os.path.isabs(birlesim), birlesim)
        self.assertEqual(Path(birlesim).resolve(),
                         Path(os.environ["USERPROFILE"]).resolve())


class ResolvedPathTests(unittest.TestCase):
    """Yönlendirmenin gerçekten yol çözümüne yansıdığını doğrular."""

    def test_path_home_under_session_root(self):
        self.assertTrue(_altinda(Path.home()), str(Path.home()))

    def test_expanduser_under_session_root(self):
        self.assertTrue(_altinda(os.path.expanduser("~")),
                        os.path.expanduser("~"))

    def test_gettempdir_under_session_root(self):
        """tempfile.gettempdir() ilk çağrıda önbelleğe alınır; sıfırlanmalı."""
        self.assertTrue(_altinda(tempfile.gettempdir()),
                        tempfile.gettempdir())

    def test_new_tempfile_lands_under_session_root(self):
        with tempfile.TemporaryDirectory(prefix="izolasyon_") as d:
            self.assertTrue(_altinda(d), d)


class AppPathsIsolationTests(unittest.TestCase):
    """Proje yolları import anında sabitlenir — hepsi kök altında olmalı."""

    @classmethod
    def setUpClass(cls):
        from core import app_paths
        cls.ap = app_paths

    def test_data_dir_under_session_root(self):
        self.assertTrue(_altinda(self.ap.DATA_DIR), str(self.ap.DATA_DIR))

    def test_db_and_log_and_pdf_dirs_under_session_root(self):
        for yol in (self.ap.DB_PATH, self.ap.LOG_DIR, self.ap.PDF_DIR):
            self.assertTrue(_altinda(yol), str(yol))

    def test_backup_dir_under_session_root(self):
        """En kritik olan: Documents yedek klasörü GERÇEK profilde olmamalı."""
        self.assertTrue(_altinda(self.ap.BACKUP_DIR),
                        str(self.ap.BACKUP_DIR))

    def test_backup_dir_is_under_documents_of_temp_profile(self):
        self.assertEqual(
            Path(self.ap.BACKUP_DIR).resolve(),
            (Path(os.environ["USERPROFILE"]) / "Documents"
             / "OfferManagementSystem" / "backups").resolve())


class NoDuplicateOverrideTests(unittest.TestCase):
    """Tekil test modülleri ortak izolasyonu geçersiz kılmamalı."""

    def test_regression_module_uses_shared_root(self):
        import tests.test_regressions as tr
        self.assertTrue(_altinda(tr.DB_PATH), str(tr.DB_PATH))

    def test_no_module_level_localappdata_override_in_tests(self):
        kok = Path(__file__).resolve().parent
        suclu = []
        for py in sorted(kok.glob("test_*.py")):
            for i, satir in enumerate(
                    py.read_text(encoding="utf-8").splitlines(), 1):
                s = satir.strip()
                if s.startswith("os.environ[") and "LOCALAPPDATA" in s \
                        and not satir.startswith((" ", "\t")):
                    suclu.append(f"{py.name}:{i}")
        self.assertEqual(suclu, [],
                         f"modül düzeyinde LOCALAPPDATA ezmesi: {suclu}")


if __name__ == "__main__":
    unittest.main()
