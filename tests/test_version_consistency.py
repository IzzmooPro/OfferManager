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
HEDEF = "v4.2"
HEDEF_SAYISAL = "4.2.0.0"
HEDEF_INSTALLER = "TeklifYonetim_Setup_v4.2.exe"
# Upgrade testinin başlangıç noktası (yalnız tarihsel bilgi)
UPGRADE_TEMEL = "v4.0"
# Yayımlanmış (tarihsel) sürüm — kanıtı korunur, hedef sürümle karıştırılmaz
YAYIMLANMIS = "v4.1"

# `artifact_verification_status` için izin verilen tüm değerler
DURUMLAR = ("verified",                 # hedef sürüm için build + B + C geçti
            "installer_pending",        # build + B geçti, installer (C) bekliyor
            "stale_source_changed",     # artifact güncel, kaynak ilerledi
            "stale_for_target_version") # hedef sürüm yükseltildi, build eski

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

    def test_artifact_surumu_ve_durumu_tutarli(self):
        """Artifact sürümü ile hedef sürüm ayrı tutulur; sahte "verified" yok.

        Sürüm yükseltmesinin ARA DURUMUNDA (`RELEASE_CHECKLIST.md`) hedef sürüm
        yükseltilmiş ama yeni build alınmamıştır. O zaman
        `artifact_built_for_version` ESKİ sürümdür ve bu bir kusur değil,
        dürüst kayıttır. Sınanan şey durumun tutarlılığıdır:

          * eski artifact  → durum `stale_for_target_version`, rc_ready False
          * güncel artifact → `verified` / `stale_source_changed` /
            `installer_pending`
          * rc_ready True  → YALNIZ `verified`
          * eski v4.1 hash'leri yeni sürüm gibi ETİKETLENEMEZ: üç artifact
            kaydının `built_for_version` değeri artifact sürümüyle aynıdır.
        """
        s = json.loads(
            (REHBER / "project_manifest.json").read_text(encoding="utf-8"))["snapshot"]
        hedef = s.get("version")
        artifact = s.get("artifact_built_for_version")
        durum = s.get("artifact_verification_status")
        self.assertEqual(hedef, HEDEF, "snapshot.version hedef sürüm değil")
        self.assertIn(durum, DURUMLAR, f"bilinmeyen artifact durumu: {durum}")

        if artifact != hedef:
            self.assertEqual(durum, "stale_for_target_version",
                             "artifact hedef sürümden eski ama durum bunu "
                             f"söylemiyor: {durum}")
            self.assertIs(s.get("release_candidate_ready"), False,
                          "eski artifact ile release adaylığı iddia edilemez")
            self.assertTrue(str(s.get("artifact_stale_reason", "")).strip(),
                            "artifact eskidi ama gerekçe yazılmamış")
        else:
            self.assertIn(durum, ("verified", "stale_source_changed",
                                  "installer_pending"))

        if s.get("release_candidate_ready") is True:
            self.assertEqual(durum, "verified",
                             "doğrulanmamış artifact release adayı olamaz")

        # Yerel derleme çıktıları artifact sürümünü taşımak ZORUNDADIR.
        for anahtar in ("dist_exe", "installer"):
            self.assertEqual(s[anahtar].get("built_for_version"), artifact,
                             f"{anahtar}.built_for_version artifact sürümüyle "
                             "uyuşmuyor — eski hash yeni sürüm gibi etiketlenmiş")
        # `installed_exe` MAKİNEDE KURULU olanı anlatır ve derleme çıktısı
        # değildir: installer doğrulaması yapılana kadar bir ÖNCEKİ sürümde
        # kalır. Sahte ilerletmeye karşı, farklıysa gerekçe zorunludur.
        kurulu = s["installed_exe"].get("built_for_version")
        self.assertRegex(str(kurulu), r"^v\d+\.\d+$",
                         "installed_exe.built_for_version yazılmamış")
        if kurulu != artifact:
            self.assertTrue(str(s["installed_exe"].get("note", "")).strip(),
                            "kurulu sürüm derlemeden farklı ama gerekçe yok")
            self.assertIs(s.get("release_candidate_ready"), False,
                          "kurulu sürüm henüz hedef değilken release adaylığı "
                          "iddia edilemez")

    def test_installer_pending_durumu_dogru_kullaniliyor(self):
        """`installer_pending`: build + frozen smoke geçti, installer BEKLİYOR."""
        s = json.loads(
            (REHBER / "project_manifest.json").read_text(encoding="utf-8"))["snapshot"]
        if s.get("artifact_verification_status") != "installer_pending":
            self.skipTest("artifact installer_pending durumunda değil")
        hedef = s["version"]
        self.assertEqual(s["artifact_built_for_version"], hedef)
        self.assertEqual(s["frozen_smoke"].get("verified_for_version"), hedef,
                         "installer_pending ama frozen smoke hedef sürüm için değil")
        self.assertEqual(s["frozen_smoke"].get("result"), "GECTI")
        self.assertNotEqual(s["installer_test"].get("verified_for_version"), hedef,
                            "installer hedef sürüm için doğrulandıysa durum "
                            "installer_pending olamaz")
        self.assertEqual(s["installer_test"].get("pending_for_version"), hedef,
                         "installer testinin hangi sürüm için beklediği yazılmamış")
        self.assertIs(s.get("release_candidate_ready"), False)

    def test_manifest_release_candidate_durumu_durust(self):
        s = json.loads(
            (REHBER / "project_manifest.json").read_text(encoding="utf-8"))["snapshot"]
        hazir = s.get("release_candidate_ready")
        self.assertIsInstance(hazir, bool)
        # Yayın bayrakları artık SABİT false değildir (v4.1 yayımlandı);
        # sınanan şey bool olmaları ve yayın sırasının tutarlılığıdır.
        for alan in ("tag_created", "github_release_created"):
            self.assertIsInstance(s["release"].get(alan), bool, f"release.{alan} bool değil")
        if s["release"].get("github_release_created") is True:
            self.assertIs(s["release"].get("tag_created"), True,
                          "release var ama tag yok — tutarsız yayın durumu")
        self.assertTrue(str(s.get("release_readiness_note", "")).strip(),
                        "release_candidate_ready'nin anlamı yazılmamış")
        if hazir:
            self.assertEqual(s.get("artifact_verification_status"), "verified",
                             "doğrulanmamış artifact ile release adaylığı iddia edilemez")

    def test_manifest_commit_ayrimi_durust(self):
        """Üçlü provenance ayrı ayrı tutulur ve birbirine karıştırılmaz.

        * `version_prepare_commit` — sürüm alanlarının hazırlandığı commit
        * `source_commit`          — güncel işlevsel kaynak
        * `built_from_commit`      — eldeki artifact'ın alındığı gerçek HEAD

        Hash'ler burada LİTERAL olarak sabitlenmez (her turda değişir);
        sınanan şey biçim, ayrım ve gerekçenin yazılmış olmasıdır.
        """
        s = json.loads(
            (REHBER / "project_manifest.json").read_text(encoding="utf-8"))["snapshot"]
        for alan in ("version_prepare_commit", "source_commit",
                     "built_from_commit"):
            self.assertRegex(str(s.get(alan, "")).strip(), r"^[0-9a-f]{7,40}$",
                             f"{alan} gerçek bir commit hash'i değil")
        for alan in ("version_prepare_commit_note", "source_commit_note",
                     "built_from_commit_note"):
            self.assertTrue(str(s.get(alan, "")).strip(),
                            f"{alan} boş — provenance açıklanmamış")
        durum = s.get("artifact_verification_status")
        if durum in ("stale_source_changed", "stale_for_target_version"):
            self.assertNotEqual(s.get("source_commit"), s.get("built_from_commit"),
                                "artifact eski deniyor ama kaynak ve build "
                                "commit'i aynı yazılmış")
        elif durum in ("verified", "installer_pending"):
            self.assertEqual(s.get("source_commit"), s.get("built_from_commit"),
                             "artifact güncel deniyor ama build commit'i "
                             "kaynak commit'inden farklı")

    def test_artifact_eskiyken_gerekce_ve_hashler_korunuyor(self):
        """Eski artifact'ın hash'leri DEĞİŞTİRİLMEZ; yalnız tazelik iddiası düşer."""
        s = json.loads(
            (REHBER / "project_manifest.json").read_text(encoding="utf-8"))["snapshot"]
        durum = s.get("artifact_verification_status")
        if durum not in ("stale_source_changed", "stale_for_target_version"):
            self.skipTest("artifact eski değil")
        self.assertIs(s.get("release_candidate_ready"), False)
        gerekce = str(s.get("artifact_stale_reason", "")).strip()
        self.assertTrue(gerekce, "artifact_stale_reason boş")
        if durum == "stale_for_target_version":
            # Hedef sürüm yükseltildi, build eski: v4.1 değerleri korunmalı
            self.assertEqual(s["dist_exe"]["size"], 9437741)
            self.assertTrue(s["dist_exe"]["sha256"].startswith("872DF3C1"))
            self.assertEqual(s["installer"]["size"], 52501243)
            self.assertTrue(s["installer"]["sha256"].startswith("DE590641"))
            self.assertIn(s["artifact_built_for_version"], gerekce,
                          "gerekçe, eldeki derlemenin hangi sürüm olduğunu "
                          "söylemiyor")

    def test_built_from_commit_notu_stale_durumu_aciklar(self):
        s = json.loads(
            (REHBER / "project_manifest.json").read_text(encoding="utf-8"))["snapshot"]
        if s.get("artifact_verification_status") not in (
                "stale_source_changed", "stale_for_target_version"):
            self.skipTest("artifact stale değil")
        not_metni = str(s.get("built_from_commit_note", ""))
        self.assertRegex(not_metni, r"(?i)i[çc]ermez|dahil de[ğg]il|eskidir",
                         "not, artifact'ın güncel kaynağı içermediğini "
                         f"söylemiyor: {not_metni!r}")

    def test_manifest_installer_yolu_artifact_surumunu_gosterir(self):
        """Installer yolu ARTIFACT sürümünü gösterir — sahte etiket yok."""
        s = json.loads(
            (REHBER / "project_manifest.json").read_text(encoding="utf-8"))["snapshot"]
        self.assertIn(s["artifact_built_for_version"], s["installer"]["path"],
                      "installer yolu eldeki derlemenin sürümüyle uyuşmuyor")
        self.assertNotIn(UPGRADE_TEMEL, s["installer"]["path"],
                         "aktif installer yolu hâlâ v4.0'ı gösteriyor")

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

    def test_dogrulama_kanitlari_hangi_surume_ait_belli(self):
        """B ve C kanıtları HANGİ sürüm için alındıysa onu söyler.

        Hedef sürüm yükseltildiğinde eski kanıt yeni sürüme DEVREDİLMEZ:
        `verified_for_version` hedeften farklıysa release adaylığı düşer.
        """
        s = json.loads(
            (REHBER / "project_manifest.json").read_text(encoding="utf-8"))["snapshot"]
        hedef = s["version"]
        for anahtar in ("frozen_smoke", "installer_test"):
            kanit = s[anahtar]
            self.assertEqual(kanit.get("result"), "GECTI",
                             f"{anahtar} sonucu GECTI değil")
            surum = kanit.get("verified_for_version")
            self.assertRegex(str(surum), r"^v\d+\.\d+$",
                             f"{anahtar}.verified_for_version yazılmamış")
            if surum != hedef:
                self.assertIs(s.get("release_candidate_ready"), False,
                              f"{anahtar} kanıtı {surum} için ama {hedef} "
                              "release adayı sayılmış")

    def test_current_status_hedef_surumu_yaziyor(self):
        metin = (REHBER / "CURRENT_STATUS.md").read_text(encoding="utf-8")
        self.assertIn(HEDEF, metin)

    def test_changelog_hedef_bolumu_var(self):
        metin = (KOK / "docs" / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertRegex(metin, rf"##\s*\[{re.escape(HEDEF)}\]\s*[—–-]\s*\d{{4}}-\d{{2}}-\d{{2}}",
                         f"CHANGELOG'da tarihli {HEDEF} bölümü yok")
        for taslak in ("TASLAK", "DRAFT", "TBD", "YYYY-MM-DD"):
            self.assertNotIn(taslak, metin,
                             f"CHANGELOG'da taslak işareti kalmış: {taslak}")

    def test_changelog_eski_surum_bolumleri_korunmus(self):
        metin = (KOK / "docs" / "CHANGELOG.md").read_text(encoding="utf-8")
        for eski in ("[v4.0]", f"[{YAYIMLANMIS}]"):
            self.assertIn(eski, metin, f"tarihsel {eski} bölümü silinmiş")

    def test_changelog_hedef_bolumu_en_ustte(self):
        """Yeni sürüm bölümü eskilerin ÜSTÜNDE olmalı."""
        metin = (KOK / "docs" / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertLess(metin.index(f"[{HEDEF}]"), metin.index(f"[{YAYIMLANMIS}]"),
                        "hedef sürüm bölümü eski sürümün altında kalmış")


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
        artifact = self.snapshot["artifact_built_for_version"]
        self.assertEqual(self.snapshot["dist_exe"].get("file_version"),
                         artifact.lstrip("v") + ".0.0",
                         "dist EXE dosya sürümü artifact sürümüyle uyuşmuyor")
        self.assertEqual(self.snapshot["dist_exe"].get("product_version"),
                         artifact)


class ReleaseDogrulamaTests(unittest.TestCase):
    """Artifact hedef sürüm için doğrulandığında --release geçmeli."""

    def test_release_modu_provenance_ile_tutarli(self):
        """`--release` sonucu BUILD SONRASI PROVENANCE gerçeğiyle tutarlı olmalı.

        Eski varsayım ("artifact sürümü eşitse --release her zaman geçer")
        yanlıştı: artifact `built_from_commit`'ten sonra kaynak/test değişmiş
        olabilir. R12c ile kapı bunu görür. Sözleşme:

          * provenance temizse  → `--release` **geçmeli** (exit 0)
          * provenance yasak değişiklik buluyorsa → `--release` **başarısız**
            olmalı ve çıktıda provenance nedeni **görünmeli**

        Kaynak, yayımlanmış artifact'tan ileriyken kırmızı olması TASARIM
        GEREĞİDİR; yeni build alınmadan kapı yeşile dönmemelidir.
        """
        s = json.loads(
            (REHBER / "project_manifest.json").read_text(encoding="utf-8"))["snapshot"]
        if s.get("release_candidate_ready") is not True:
            self.skipTest("release adayı değil: artifact yeniden build bekliyor")

        import importlib.util
        spec = importlib.util.spec_from_file_location("vpg_rel", VERIFY)
        modul = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modul)
        prov = modul.kontrol_build_sonrasi_provenance(KOK)

        sonuc = subprocess.run([sys.executable, str(VERIFY), "--release"],
                               capture_output=True, text=True, timeout=180)
        if prov:
            self.assertNotEqual(
                sonuc.returncode, 0,
                "provenance yasak değişiklik bulduğu hâlde --release geçti:\n"
                + sonuc.stdout)
            self.assertIn("provenance", sonuc.stdout.lower(),
                          f"--release provenance nedenini göstermedi:\n{sonuc.stdout}")
        else:
            self.assertEqual(sonuc.returncode, 0,
                             f"provenance temizken --release başarısız:\n{sonuc.stdout}")

    def test_artifacts_modu_gecer(self):
        """`--artifacts` her durumda exit 0'dır; uyarı hedef duruma bağlıdır.

        ARA DURUMDA (hedef sürüm yükseltildi, build eski) uyarı **beklenir** ve
        eldeki derlemenin sürümünü söylemek zorundadır — sessizce geçmesi
        gerçeği gizlerdi (RELEASE_CHECKLIST, "Sürüm yükseltmesinin üç durumu").
        """
        s = json.loads(
            (REHBER / "project_manifest.json").read_text(encoding="utf-8"))["snapshot"]
        sonuc = subprocess.run([sys.executable, str(VERIFY), "--artifacts"],
                               capture_output=True, text=True, timeout=180)
        self.assertEqual(sonuc.returncode, 0,
                         f"--artifacts exit 0 olmalıydı:\n{sonuc.stdout}")
        if s["artifact_built_for_version"] != s["version"]:
            self.assertIn("uyari", sonuc.stdout.lower(),
                          "ara durumda eski artifact uyarısı verilmedi:\n"
                          + sonuc.stdout)
            self.assertIn(s["artifact_built_for_version"], sonuc.stdout,
                          "uyarı eldeki derlemenin sürümünü söylemiyor")
        else:
            self.assertNotIn("uyari", sonuc.stdout.lower(),
                             f"beklenmeyen uyarı:\n{sonuc.stdout}")


class YayinKanitiTests(unittest.TestCase):
    """YAYIMLANMIŞ sürümün (v4.1) kanıt sözleşmesi — TARİHSEL blok.

    Yayın kanıtı `snapshot.published_releases[<sürüm>]` altında saklanır ve
    hedef sürüm yükseltildiğinde **taşınmaz, silinmez, yeni sürüme
    devredilmez**. `snapshot.release` ise GÜNCEL hedef sürümün durumudur.

    Sayılar ve hash'ler burada tekrar sabitlenmez; sınanan şey kanıtın
    eksiksiz, tutarlı ve sınırı korunmuş olmasıdır.
    """

    @classmethod
    def setUpClass(cls):
        cls.s = json.loads(
            (REHBER / "project_manifest.json").read_text(encoding="utf-8"))["snapshot"]
        cls.yayinlar = cls.s.get("published_releases") or {}
        cls.r = cls.yayinlar.get(YAYIMLANMIS) or {}

    def test_yayimlanmis_surum_kaydi_duruyor(self):
        self.assertIn(YAYIMLANMIS, self.yayinlar,
                      f"{YAYIMLANMIS} yayın kanıtı kaybolmuş")
        self.assertEqual(self.r.get("target_version"), YAYIMLANMIS)
        self.assertIs(self.r.get("tag_created"), True)
        self.assertIs(self.r.get("github_release_created"), True)

    def test_e2e_yalniz_tag_ve_release_ile_dogru_sayilir(self):
        """updater_end_to_end_verified, tag+release olmadan true olamaz."""
        for surum, blok in list(self.yayinlar.items()) + [("guncel", self.s["release"])]:
            with self.subTest(surum=surum):
                if blok.get("updater_end_to_end_verified") is True:
                    self.assertIs(blok.get("tag_created"), True,
                                  "E2E true ama tag oluşturulmamış")
                    self.assertIs(blok.get("github_release_created"), True,
                                  "E2E true ama GitHub Release yok")

    def test_e2e_true_ise_iki_kanit_da_gecmis(self):
        if self.r.get("updater_end_to_end_verified") is not True:
            self.skipTest("E2E henüz doğrulanmadı")
        d = self.r.get("live_updater_verification") or {}
        for anahtar in ("D1_source_trust_chain", "D2_real_delivery_e2e"):
            self.assertIn(anahtar, d, f"{anahtar} kanıt nesnesi yok")
            self.assertEqual(d[anahtar].get("result"), "GECTI",
                             f"{anahtar} sonucu GECTI değil")
            self.assertTrue(str(d[anahtar].get("date", "")).strip(),
                            f"{anahtar} tarihi yok")

    def test_d1_ve_d2_ayrimi_korunuyor(self):
        d = self.r.get("live_updater_verification") or {}
        d1, d2 = d.get("D1_source_trust_chain", {}), d.get("D2_real_delivery_e2e", {})
        self.assertNotEqual(d1.get("scope"), d2.get("scope"),
                            "D1 ve D2 kapsamları ayrışmıyor")
        self.assertIn("release-assets.githubusercontent.com",
                      json.dumps(d1, ensure_ascii=False),
                      "D1 canlı redirect host kanıtı yok")
        self.assertIn(UPGRADE_TEMEL, json.dumps(d2, ensure_ascii=False),
                      "D2 gerçek public v4.0 istemci kanıtı yok")

    def test_release_read_back_alanlari_dolu(self):
        for alan in ("tag_commit", "release_url", "published_at"):
            self.assertTrue(str(self.r.get(alan, "")).strip(), f"{alan} boş")
        self.assertRegex(self.r["tag_commit"], r"^[0-9a-f]{40}$",
                         "tag_commit tam hash değil")
        self.assertIn(f"/releases/tag/{YAYIMLANMIS}", self.r["release_url"])
        a = self.r.get("asset_readback") or {}
        self.assertEqual(a.get("name"), f"TeklifYonetim_Setup_{YAYIMLANMIS}.exe")
        self.assertIsInstance(a.get("size"), int)
        self.assertGreater(a.get("size", 0), 0)
        self.assertRegex(str(a.get("digest", "")), r"^sha256:[0-9a-f]{64}$",
                         "asset digest sha256:<64 hex> biçiminde değil")

    def test_yayimlanmis_asset_kendi_artifactiyla_tutarli(self):
        """Asset read-back değerleri, O SÜRÜMÜN artifact'ıyla karşılaştırılır.

        Yerel `installer` alanı hedef sürümle birlikte değiştiğinde bu kontrol
        sessizce anlamını yitirmemeli: karşılaştırma yalnız yerel artifact hâlâ
        yayımlanmış sürüme aitken yapılır, aksi hâlde açıkça atlanır.
        """
        a = self.r.get("asset_readback") or {}
        if self.s.get("artifact_built_for_version") != YAYIMLANMIS:
            self.skipTest(f"yerel artifact artık {YAYIMLANMIS} değil")
        self.assertEqual(a.get("size"), self.s["installer"]["size"],
                         "yayınlanan asset boyutu yerel installer ile uyuşmuyor")
        self.assertEqual(a.get("digest", "").split(":")[-1].upper(),
                         self.s["installer"]["sha256"],
                         "yayınlanan asset digest'i yerel installer ile uyuşmuyor")

    def test_kanit_siniri_metni_korunuyor(self):
        """'U17 paketli E2E geçti' genellemesine karşı açık sınır."""
        metin = str(self.r.get("evidence_scope_limit", ""))
        self.assertTrue(metin.strip(), "evidence_scope_limit boş")
        for anahtar in ("v4.2", UPGRADE_TEMEL):
            self.assertIn(anahtar, metin, f"sınır metninde {anahtar} geçmiyor")
        self.assertRegex(metin, r"(?i)paketli",
                         "paketli U17 istemci sınırı yazılmamış")

    def test_kod_imzasi_ve_guven_zinciri_korunuyor(self):
        """YAYINLANMIŞ v4.1'in güvenlik kanıtı — hedef sürüm ilerlese de durur."""
        self.assertIs(self.s["signing"]["signed"], False)
        self.assertIs(self.r["updater_trust_chain"]["code_signing"], False)
        for alan in ("asset_name_pinned", "url_host_allowlisted",
                     "sha256_and_size_verified",
                     "fail_closed_when_metadata_missing"):
            self.assertIs(self.r["updater_trust_chain"][alan], True,
                          f"updater güven zinciri kanıtı zayıfladı: {alan}")

    def test_yayin_gecerliligi_ile_hedef_tazeligi_ayrilir(self):
        """'v4.1 yayınlandı' ≠ 'hedef sürüm build edildi'."""
        self.assertIs(self.r["tag_created"], True)
        self.assertIs(self.r["github_release_created"], True)
        self.assertIs(self.r["updater_end_to_end_verified"], True)
        self.assertIn(self.s["artifact_verification_status"], DURUMLAR)
        self.assertIsInstance(self.s["release_candidate_ready"], bool)
        if self.s["artifact_verification_status"] != "verified":
            self.assertIs(self.s["release_candidate_ready"], False,
                          "doğrulanmamış artifact ile release adaylığı denemez")

    def test_guncel_hedef_yayin_blogu_durust(self):
        """Hedef sürümün yayın bayrakları KANIT olmadan true olamaz.

        `snapshot.release` GÜNCEL hedef sürümün canlı durumudur;
        `published_releases` yalnız ÖNCEKİ sürümlerin tarihsel kaydını tutar.
        Bir sürüm ancak yeni bir hedefe geçilirken oraya taşınır — bu yüzden
        hedef sürüm iki yerde birden bulunamaz.
        """
        r = self.s["release"]
        self.assertEqual(r.get("target_version"), HEDEF,
                         "release bloğu hedef sürümü göstermiyor")
        self.assertNotIn(HEDEF, self.yayinlar,
                         f"{HEDEF} hem güncel release bloğunda hem tarihsel "
                         "kayıtta — çift kayıt")
        self.assertTrue(str(r.get("note", "")).strip(),
                        "hedef sürüm yayın durumunun anlamı yazılmamış")
        bayraklar = [r.get(a) for a in ("tag_created", "github_release_created",
                                        "updater_end_to_end_verified")]
        for b in bayraklar:
            self.assertIsInstance(b, bool)
        if not all(bayraklar):
            # Henüz yayımlanmadı: hiçbir bayrak kanıtsız true olamaz.
            self.assertFalse(any(bayraklar),
                             "yayın bayrakları kısmen true — tutarsız durum")
            return
        # Yayımlandı: read-back kanıtı ZORUNLU.
        for alan in ("tag_commit", "release_url", "published_at"):
            self.assertTrue(str(r.get(alan, "")).strip(),
                            f"{HEDEF} yayımlandı deniyor ama {alan} boş")
        self.assertRegex(r["tag_commit"], r"^[0-9a-f]{40}$")
        self.assertIn(f"/releases/tag/{HEDEF}", r["release_url"])
        a = r.get("asset_readback") or {}
        self.assertEqual(a.get("name"), HEDEF_INSTALLER)
        self.assertEqual(a.get("size"), self.s["installer"]["size"],
                         "yayınlanan asset boyutu yerel installer ile uyuşmuyor")
        self.assertEqual(a.get("digest", "").split(":")[-1].upper(),
                         self.s["installer"]["sha256"],
                         "yayınlanan asset digest'i yerel installer ile uyuşmuyor")
        self.assertIs(r.get("draft"), False)
        self.assertIs(r.get("prerelease"), False)

    def test_yayimlanan_tag_build_commitini_gosterir(self):
        """Tag, artifact'ın build edildiği commit'i göstermeli.

        Tag metadata/kanıt commit'lerine TAŞINMAZ; aksi hâlde yayımlanan
        installer ile tag'in işaret ettiği ağaç ayrışır.
        """
        r = self.s["release"]
        if r.get("tag_created") is not True:
            self.skipTest("tag henüz oluşturulmadı")
        self.assertTrue(r["tag_commit"].startswith(self.s["built_from_commit"]),
                        f"tag {r['tag_commit'][:7]} build commit "
                        f"{self.s['built_from_commit']} ile aynı değil")

    def test_r3d_gelecek_host_riski_acik_kaliyor(self):
        m = (REHBER / "KNOWN_RISKS.md").read_text(encoding="utf-8")
        self.assertIn("R3d", m)
        satir = [s for s in m.splitlines() if s.startswith("| R3d")]
        self.assertTrue(satir, "R3d satırı yok")
        self.assertIn("release-assets.githubusercontent.com", satir[0])
        self.assertRegex(satir[0], r"(?i)fail-closed")
        self.assertNotRegex(satir[0], r"(?i)kapand[ıi]",
                            "R3d 'kapandı' olarak yazılmış")

    def test_v42_paketli_u17_takip_maddesi_var(self):
        m = (REHBER / "KNOWN_RISKS.md").read_text(encoding="utf-8")
        self.assertRegex(m, r"(?i)v4\.2",
                         "v4.2'de paketli U17 E2E takip maddesi yok")
        self.assertRegex(m, r"(?i)paketli")


if __name__ == "__main__":
    unittest.main()
