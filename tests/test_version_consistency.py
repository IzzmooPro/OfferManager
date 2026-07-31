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
  * Artifact'lar hedef sürüm için üretilip doğrulandığında manifest
    `artifact_built_for_version == version` olur ve `--release` geçer. Temiz
    clone'da yerel artifact bulunmadığında `--artifacts` uyarıyla exit 0,
    `--release` ise exit 1 kalır (bkz. `tests/test_project_guide.py`).
"""
import hashlib
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
# Upgrade testinin başlangıç noktası (yalnız tarihsel bilgi)
UPGRADE_TEMEL = "v4.0"

_YOK = "packaging/ yerel-only; temiz clone'da bulunmayabilir"
_ARTIFACT_YOK = "dist/ ve installer_output/ yerel-only; temiz clone'da yok"


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

    def test_manifest_artifact_hedef_surumle_ayni(self):
        """Artifact hedef sürüm için üretildi; durumu dürüstçe yazıldı.

        `artifact_verification_status` sabit "verified" olmak ZORUNDA değildir:
        kaynak artifact üretildikten sonra değişirse doğru değer
        "stale_source_changed"dır. Sınanan şey, durumun tutarlı ve gerekçeli
        olmasıdır — sahte "verified" yazılamaz.
        """
        s = json.loads(
            (REHBER / "project_manifest.json").read_text(encoding="utf-8"))["snapshot"]
        self.assertEqual(s.get("artifact_built_for_version"), HEDEF)
        durum = s.get("artifact_verification_status")
        self.assertIn(durum, ("verified", "stale_source_changed"))
        if durum == "stale_source_changed":
            self.assertTrue(str(s.get("artifact_stale_reason", "")).strip(),
                            "artifact eskidi ama gerekçe yazılmamış")
            self.assertIs(s.get("release_candidate_ready"), False,
                          "artifact eskimişken release adayı sayılamaz")
        for anahtar in ("dist_exe", "installer", "installed_exe"):
            self.assertEqual(s[anahtar].get("built_for_version"), HEDEF,
                             f"{anahtar}.built_for_version hedef sürüm değil")

    def test_manifest_release_candidate_durumu_durust(self):
        s = json.loads(
            (REHBER / "project_manifest.json").read_text(encoding="utf-8"))["snapshot"]
        hazir = s.get("release_candidate_ready")
        self.assertIsInstance(hazir, bool)
        self.assertIs(s["release"].get("tag_created"), False)
        self.assertIs(s["release"].get("github_release_created"), False)
        self.assertTrue(str(s.get("release_readiness_note", "")).strip(),
                        "release_candidate_ready'nin anlamı yazılmamış")
        if hazir:
            self.assertEqual(s.get("artifact_verification_status"), "verified",
                             "doğrulanmamış artifact ile release adaylığı iddia edilemez")

    def test_manifest_commit_ayrimi_durust(self):
        """Üçlü provenance ayrı ayrı tutulur ve birbirine karıştırılmaz.

        * `version_prepare_commit` — v4.1 sürüm alanlarının hazırlandığı commit
        * `source_commit`         — güncel işlevsel kaynak (U17 dâhil)
        * `built_from_commit`     — eldeki artifact'ın alındığı gerçek HEAD
        """
        s = json.loads(
            (REHBER / "project_manifest.json").read_text(encoding="utf-8"))["snapshot"]
        self.assertEqual(s.get("version_prepare_commit"), "a63f981",
                         "v4.1 sürüm hazırlığı commit'i (tarihsel, sabit)")
        # v4.1 release artifact'ı DEĞİŞMEZ biçimde d359137 ağacından üretildi;
        # bu alan sabittir. Yeni bir build alınırsa bilinçli olarak güncellenir.
        self.assertEqual(s.get("built_from_commit"), "d359137",
                         "v4.1 artifact'ının build edildiği gerçek HEAD")
        self.assertRegex(str(s.get("source_commit", "")).strip(),
                         r"^[0-9a-f]{7,40}$",
                         "source_commit gerçek bir commit hash'i değil")
        for alan in ("version_prepare_commit_note", "source_commit_note",
                     "built_from_commit_note"):
            self.assertTrue(str(s.get(alan, "")).strip(),
                            f"{alan} boş — provenance açıklanmamış")
        self.assertIn(str(s.get("source_commit", "")).strip(),
                      str(s.get("built_from_commit_note", "")),
                      "built_from_commit_note, kaynak commit'in bu build ağacında "
                      "bulunduğunu açıklamıyor")

    def test_artifact_staleyken_kaynak_ve_build_commiti_farkli(self):
        s = json.loads(
            (REHBER / "project_manifest.json").read_text(encoding="utf-8"))["snapshot"]
        if s.get("artifact_verification_status") != "stale_source_changed":
            self.skipTest("artifact stale değil")
        self.assertNotEqual(s.get("source_commit"), s.get("built_from_commit"),
                            "artifact stale iddiası var ama kaynak ve build "
                            "commit'i aynı yazılmış")
        self.assertIs(s.get("release_candidate_ready"), False)

    def test_manifest_installer_yolu_hedef_surumu_gosterir(self):
        s = json.loads(
            (REHBER / "project_manifest.json").read_text(encoding="utf-8"))["snapshot"]
        self.assertIn(HEDEF, s["installer"]["path"])
        self.assertNotIn(UPGRADE_TEMEL, s["installer"]["path"],
                         "aktif installer yolu hâlâ eski sürümü gösteriyor")

    def test_eski_surum_yalniz_upgrade_baseline_alaninda(self):
        """v4.0 hash'leri aktif artifact alanlarında kalmamalı."""
        s = json.loads(
            (REHBER / "project_manifest.json").read_text(encoding="utf-8"))["snapshot"]
        eski = "4679D76842D3F1E16E670623105F209673E726C9EDABF6DD298FDEAB76AFFC2D"
        for anahtar in ("dist_exe", "installer", "installed_exe"):
            self.assertNotEqual(s[anahtar].get("sha256"), eski,
                                f"{anahtar} hâlâ v4.0 hash'i taşıyor")
        temel = s.get("upgrade_baseline") or {}
        self.assertEqual(temel.get("from_version"), UPGRADE_TEMEL)


class BaselineProvenanceTests(unittest.TestCase):
    """v4.0 baseline'ın hangi commit'te ÜRETİLDİĞİ ile hangi depo durumunda
    KOPYALANDIĞI ayrı tutulmalı; tek muğlak alan kullanılmamalı."""

    def setUp(self):
        self.temel = json.loads(
            (REHBER / "project_manifest.json").read_text(
                encoding="utf-8"))["snapshot"]["upgrade_baseline"]

    def test_artifact_build_commiti(self):
        self.assertEqual(self.temel.get("artifact_built_from_commit"), "060baf3")

    def test_kopya_alinan_depo_commiti(self):
        self.assertEqual(self.temel.get("captured_from_repo_commit"), "746da84")

    def test_iki_alan_farkli_anlamda(self):
        self.assertNotEqual(self.temel["artifact_built_from_commit"],
                            self.temel["captured_from_repo_commit"],
                            "iki alan aynı değeri taşıyorsa ayrım anlamsız")
        self.assertIn("060baf3", self.temel.get("note", ""))
        self.assertIn("746da84", self.temel.get("note", ""))

    def test_mugalak_alan_kaldirildi(self):
        self.assertNotIn("from_source_commit", self.temel,
                         "muğlak from_source_commit alanı hâlâ duruyor")


class CanliUpstreamTests(unittest.TestCase):
    """Canlı remote durumu snapshot'ta sabit tutulmamalı."""

    def setUp(self):
        self.veri = json.loads(
            (REHBER / "project_manifest.json").read_text(encoding="utf-8"))

    def test_remote_main_commit_alani_yok(self):
        self.assertNotIn("remote_main_commit", self.veri["snapshot"]["release"],
                         "manifest sabit remote hash tutuyor")

    def test_upstream_canli_dogrulama_bayragi(self):
        self.assertIs(
            self.veri["snapshot"]["release"].get(
                "upstream_sync_must_be_verified_live"), True)

    def test_current_status_sabit_remote_hash_iddiasi_yok(self):
        metin = (REHBER / "CURRENT_STATUS.md").read_text(encoding="utf-8")
        self.assertIsNone(
            re.search(r"origin/main[^\n]{0,20}(hâlâ|=)\s*`?[0-9a-f]{7,40}`?",
                      metin),
            "CURRENT_STATUS sabit origin/main hash'i iddia ediyor")

    def test_release_checklist_canli_git_kontrolu_iceriyor(self):
        metin = (REHBER / "RELEASE_CHECKLIST.md").read_text(encoding="utf-8")
        for beklenen in ("git fetch origin", "rev-parse", "left-right",
                         "ahead/behind"):
            self.assertIn(beklenen, metin,
                          f"RELEASE_CHECKLIST '{beklenen}' adımını içermiyor")

    def test_dogrulama_kanitlari_hedef_surume_ait(self):
        s = json.loads(
            (REHBER / "project_manifest.json").read_text(encoding="utf-8"))["snapshot"]
        self.assertEqual(s["frozen_smoke"].get("verified_for_version"), HEDEF)
        self.assertEqual(s["installer_test"].get("verified_for_version"), HEDEF)
        self.assertEqual(s["frozen_smoke"].get("result"), "GECTI")
        self.assertEqual(s["installer_test"].get("result"), "GECTI")

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


class ArtifactGercekDosyaTests(unittest.TestCase):
    """Manifest hash/boyutları gerçek yerel dosyalarla eşleşmeli."""

    def setUp(self):
        self.snapshot = json.loads(
            (REHBER / "project_manifest.json").read_text(encoding="utf-8"))["snapshot"]

    def _dogrula(self, anahtar):
        bilgi = self.snapshot[anahtar]
        yol = KOK / bilgi["path"]
        if not yol.is_file():
            self.skipTest(_ARTIFACT_YOK)
        h = hashlib.sha256(yol.read_bytes()).hexdigest().upper()
        self.assertEqual(h, bilgi["sha256"], f"{anahtar} hash uyuşmuyor")
        self.assertEqual(yol.stat().st_size, bilgi["size"],
                         f"{anahtar} boyut uyuşmuyor")

    def test_dist_exe_gercek_dosyayla_esit(self):
        self._dogrula("dist_exe")

    def test_installer_gercek_dosyayla_esit(self):
        self._dogrula("installer")

    def test_dist_exe_surum_alanlari(self):
        yol = KOK / self.snapshot["dist_exe"]["path"]
        if not yol.is_file():
            self.skipTest(_ARTIFACT_YOK)
        self.assertEqual(self.snapshot["dist_exe"].get("file_version"),
                         HEDEF_SAYISAL)
        self.assertEqual(self.snapshot["dist_exe"].get("product_version"), HEDEF)


class ReleaseDogrulamaTests(unittest.TestCase):
    """Artifact hedef sürüm için doğrulandığında --release geçmeli."""

    def test_release_modu_gecer(self):
        # --release yalnız gerçek yayın kapısıdır: artifact hedef sürüm için
        # doğrulanmış VE çalışma ağacı temiz olmalıdır. Kaynak değişikliği
        # sürerken kırmızı olması TASARIM GEREĞİDİR, regresyon değil.
        s = json.loads(
            (REHBER / "project_manifest.json").read_text(encoding="utf-8"))["snapshot"]
        if s.get("release_candidate_ready") is not True:
            self.skipTest("release adayı değil: artifact yeniden build bekliyor")
        kirli = subprocess.run(["git", "status", "--porcelain",
                                "--untracked-files=all"], cwd=str(KOK),
                               capture_output=True, text=True, timeout=60)
        if kirli.returncode == 0 and kirli.stdout.strip():
            self.skipTest("çalışma ağacı temiz değil: commit öncesi stale beklenir")
        sonuc = subprocess.run([sys.executable, str(VERIFY), "--release"],
                               capture_output=True, text=True, timeout=180)
        self.assertEqual(sonuc.returncode, 0,
                         f"--release başarısız:\n{sonuc.stdout}")

    def test_artifacts_modu_uyarisiz_gecer(self):
        sonuc = subprocess.run([sys.executable, str(VERIFY), "--artifacts"],
                               capture_output=True, text=True, timeout=180)
        self.assertEqual(sonuc.returncode, 0,
                         f"--artifacts exit 0 olmalıydı:\n{sonuc.stdout}")
        self.assertNotIn("uyari", sonuc.stdout.lower(),
                         f"beklenmeyen uyarı:\n{sonuc.stdout}")


if __name__ == "__main__":
    unittest.main()
