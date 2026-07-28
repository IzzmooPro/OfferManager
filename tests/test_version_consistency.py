"""Sürüm alanlarının tek kaynaktan türediğini ve birbiriyle uyuştuğunu doğrular.

Sözleşme:
  * Kullanıcıya gösterilen sürüm tek kaynaktan gelir: `core/constants.py`.
  * Windows sayısal sürümü `X.Y.0.0`, ürün sürümü `vX.Y` biçimindedir.
  * Installer dosya adı `TeklifYonetim_Setup_<sürüm>.exe` kalıbındadır.
  * `packaging/` yerel-only olduğu için TEMİZ CLONE'da bulunmayabilir; bu
    durumda paketleme kontrolleri atlanır (skip) — fakat release doğrulaması
    (`verify_project_guide.py --release`) yine de başarısız kalmalıdır.
  * Tarihsel `v4.0` atıfları (CHANGELOG, eski ölçüm notları) değiştirilmez;
    bu dosya yalnız CANLI sürüm alanlarını denetler.
"""
import importlib.util
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

KOK = Path(__file__).resolve().parents[1]
REHBER = KOK / "PROJECT_GUIDE"
PACKAGING = KOK / "packaging"
ISS = PACKAGING / "TeklifYonetim.iss"
VERSION_INFO = PACKAGING / "version_info.txt"
VERIFY = REHBER / "scripts" / "verify_project_guide.py"

# Hedef sürüm sözleşmesi
HEDEF = "v4.1"
HEDEF_SAYISAL = "4.1.0.0"
HEDEF_INSTALLER = "TeklifYonetim_Setup_v4.1.exe"
# Yeni artifact üretilene kadar mevcut artifact'ların ait olduğu sürüm
ARTIFACT_TEMEL = "v4.0"

_YOK = "packaging/ yerel-only; temiz clone'da bulunmayabilir"


class KaynakSurumTests(unittest.TestCase):
    """Tracked kaynaklar — her ortamda çalışır."""

    def test_app_version_hedefe_esit(self):
        from core.constants import APP_VERSION
        self.assertEqual(APP_VERSION, HEDEF)

    def test_app_version_bicimi(self):
        from core.constants import APP_VERSION
        self.assertRegex(APP_VERSION, r"^v\d+\.\d+$")

    def test_manifest_hedef_surumu(self):
        veri = json.loads(
            (REHBER / "project_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(veri["snapshot"]["version"], HEDEF)

    def test_manifest_artifact_temel_surumu_ayri(self):
        """Mevcut dist/installer hâlâ eski sürümün artifact'ıdır."""
        s = json.loads(
            (REHBER / "project_manifest.json").read_text(encoding="utf-8"))["snapshot"]
        self.assertEqual(s.get("artifact_built_for_version"), ARTIFACT_TEMEL)
        self.assertEqual(s.get("artifact_verification_status"),
                         "stale_for_target_version")
        self.assertIs(s.get("release_ready"), False)

    def test_manifest_installer_yolu_artifact_surumuyle_uyumlu(self):
        s = json.loads(
            (REHBER / "project_manifest.json").read_text(encoding="utf-8"))["snapshot"]
        self.assertIn(ARTIFACT_TEMEL, s["installer"]["path"],
                      "mevcut installer yolu artifact sürümünü göstermeli")

    def test_current_status_hedef_surumu_yaziyor(self):
        metin = (REHBER / "CURRENT_STATUS.md").read_text(encoding="utf-8")
        self.assertIn(HEDEF, metin)

    def test_changelog_hedef_bolumu_var(self):
        metin = (KOK / "docs" / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertRegex(metin, r"##\s*\[?v4\.1\]?",
                         "CHANGELOG'da v4.1 bölümü yok")

    def test_changelog_eski_surum_bolumu_korunmus(self):
        metin = (KOK / "docs" / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertIn("[v4.0]", metin, "tarihsel v4.0 bölümü silinmiş")


class InstallerAdiTests(unittest.TestCase):

    def test_installer_adi_hedef_surumden_turer(self):
        from core.constants import APP_VERSION
        self.assertEqual(f"TeklifYonetim_Setup_{APP_VERSION}.exe",
                         HEDEF_INSTALLER)


class PaketlemeSurumTests(unittest.TestCase):
    """packaging/ yerel-only — yoksa atlanır."""

    def setUp(self):
        if not ISS.is_file() or not VERSION_INFO.is_file():
            self.skipTest(_YOK)

    def test_iss_myappversion(self):
        metin = ISS.read_text(encoding="utf-8")
        m = re.search(r'#define\s+MyAppVersion\s+"([^"]+)"', metin)
        self.assertIsNotNone(m, "MyAppVersion bulunamadı")
        self.assertEqual(m.group(1), HEDEF)

    def test_iss_sayisal_surumler(self):
        metin = ISS.read_text(encoding="utf-8")
        for alan in ("VersionInfoVersion", "VersionInfoProductVersion"):
            m = re.search(rf"{alan}\s*=\s*([0-9.]+)", metin)
            self.assertIsNotNone(m, f"{alan} bulunamadı")
            self.assertEqual(m.group(1), HEDEF_SAYISAL, alan)

    def test_iss_output_adi(self):
        metin = ISS.read_text(encoding="utf-8")
        m = re.search(r"OutputBaseFilename\s*=\s*(.+)", metin)
        self.assertIsNotNone(m)
        cozulen = m.group(1).strip().replace("{#MyAppVersion}", HEDEF)
        self.assertEqual(cozulen + ".exe", HEDEF_INSTALLER)

    def test_version_info_sayisal_alanlar(self):
        metin = VERSION_INFO.read_text(encoding="utf-8")
        sayisal = tuple(int(p) for p in HEDEF_SAYISAL.split("."))
        beklenen = "(" + ", ".join(str(p) for p in sayisal) + ")"
        for alan in ("filevers", "prodvers"):
            m = re.search(rf"{alan}\s*=\s*\(([^)]*)\)", metin)
            self.assertIsNotNone(m, f"{alan} bulunamadı")
            self.assertEqual("(" + m.group(1).strip() + ")", beklenen, alan)

    def test_version_info_string_alanlar(self):
        metin = VERSION_INFO.read_text(encoding="utf-8")
        m = re.search(r"StringStruct\('FileVersion',\s*'([^']+)'\)", metin)
        self.assertIsNotNone(m, "FileVersion bulunamadı")
        self.assertEqual(m.group(1), HEDEF_SAYISAL)
        m = re.search(r"StringStruct\('ProductVersion',\s*'([^']+)'\)", metin)
        self.assertIsNotNone(m, "ProductVersion bulunamadı")
        self.assertEqual(m.group(1), HEDEF)

    def test_iss_ve_constants_ayni_surum(self):
        from core.constants import APP_VERSION
        metin = ISS.read_text(encoding="utf-8")
        m = re.search(r'#define\s+MyAppVersion\s+"([^"]+)"', metin)
        self.assertEqual(m.group(1), APP_VERSION,
                         "Inno sürümü core/constants.py ile uyuşmuyor")


class UpdaterKarsilastirmaTests(unittest.TestCase):
    """Sürüm karşılaştırması 'v' ön ekinden etkilenmemeli."""

    def setUp(self):
        from ui.utils.updater import is_newer_version
        self.yeni_mi = is_newer_version

    def test_hedef_onceki_surumden_yeni(self):
        self.assertTrue(self.yeni_mi("v4.1", "v4.0"))

    def test_hedef_kendisinden_yeni_degil(self):
        self.assertFalse(self.yeni_mi("v4.1", "v4.1"))

    def test_hedef_sonraki_surumden_eski(self):
        self.assertFalse(self.yeni_mi("v4.1", "v4.2"))
        self.assertTrue(self.yeni_mi("v4.2", "v4.1"))

    def test_v_oneki_karsilastirmayi_bozmaz(self):
        for yeni, eski in (("4.1", "v4.0"), ("v4.1", "4.0"), ("4.1", "4.0")):
            self.assertTrue(self.yeni_mi(yeni, eski), f"{yeni} > {eski}")
        self.assertFalse(self.yeni_mi("v4.0", "4.1"))

    def test_canli_surum_yayindaki_eski_tagden_yeni(self):
        from core.constants import APP_VERSION
        self.assertTrue(self.yeni_mi(APP_VERSION, "v4.0"),
                        "canlı sürüm yayındaki v4.0 tag'inden yeni olmalı")


class ReleaseDogrulamaTests(unittest.TestCase):
    """Yeni sürüm artifact'ı üretilene kadar --release BAŞARISIZ olmalı."""

    def test_release_modu_eski_artifact_ile_basarisiz(self):
        sonuc = subprocess.run([sys.executable, str(VERIFY), "--release"],
                               capture_output=True, text=True, timeout=180)
        self.assertEqual(sonuc.returncode, 1,
                         "hedef sürüm için artifact yokken --release geçti")
        self.assertIn("artifact", sonuc.stdout.lower(),
                      f"başarısızlık nedeni artifact değil:\n{sonuc.stdout}")

    def test_artifacts_modu_eski_artifact_uyarisi_verir(self):
        """Uyarı hem hedef hem artifact sürümünü adlandırmalı.

        Metin karşılaştırması konsol kodlamasına bağlı olmasın diye yalnız
        ASCII güvenli parçalar aranır (Türkçe karakterler mojibake olabilir).
        """
        sonuc = subprocess.run([sys.executable, str(VERIFY), "--artifacts"],
                               capture_output=True, text=True, timeout=180)
        self.assertEqual(sonuc.returncode, 0,
                         f"--artifacts exit 0 olmalıydı:\n{sonuc.stdout}")
        cikti = sonuc.stdout.lower()
        self.assertIn("uyari", cikti, f"uyarı satırı yok:\n{sonuc.stdout}")
        self.assertIn("artifact", cikti)
        self.assertIn(ARTIFACT_TEMEL, cikti, "artifact sürümü belirtilmemiş")
        self.assertIn(HEDEF, cikti, "hedef sürüm belirtilmemiş")


if __name__ == "__main__":
    unittest.main()
