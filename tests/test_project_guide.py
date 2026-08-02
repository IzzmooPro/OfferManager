"""PROJECT_GUIDE yapısının ve doğrulama script'inin testleri.

Sözleşme:
  * Zorunlu (tracked) rehber dosyaları bulunmalı ve `verify_project_guide.py`
    normal modu temiz geçmeli.
  * `project_manifest.json` stable/snapshot ayrımını korumalı.
  * INDEX.md yönlendirmeleri var olan belgelere gitmeli.
  * Temiz clone senaryosu: `dist/`, `installer_output/`, `packaging/`, `assets/`
    yokken normal mod KIRILMAZ; `--release` modu ise başarısız olur.
  * Ayırt edici testler: bozuk iç bağlantı, eksik `covers` yolu, eskimiş kaynak,
    yanlış artifact hash'i ve yasak mutlak Windows yolu ayrı ayrı yakalanmalı.

Bu dosya gerçek kullanıcı verisini, gerçek Credential Manager'ı veya ağı
KULLANMAZ; yalnız depo içeriğini ve geçici kopyaları okur.
"""
import json
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

KOK = Path(__file__).resolve().parents[1]
REHBER = KOK / "PROJECT_GUIDE"
SCRIPT = REHBER / "scripts" / "verify_project_guide.py"

ZORUNLU_KOK = ["CLAUDE.md", "AGENTS.md"]
ZORUNLU_BELGE = [
    "INDEX.md", "CURRENT_STATUS.md", "ARCHITECTURE.md", "MODULE_MAP.md",
    "DATA_AND_PATHS.md", "CRITICAL_INVARIANTS.md", "TESTING_GUIDE.md",
    "BUILD_AND_PACKAGING.md", "RELEASE_CHECKLIST.md", "VERIFICATION_GUIDE.md",
    "SECURITY_AND_PRIVACY.md", "AUDIT_HISTORY.md", "KNOWN_RISKS.md",
    "DECISIONS.md", "TROUBLESHOOTING.md", "COLLABORATION_WORKFLOW.md",
    "CHANGE_PROTOCOL.md",
]
ZORUNLU_EK = [
    "project_manifest.json",
    "templates/CLAUDE_RESULT_REPORT.md",
    "templates/CODEX_REVIEW_REPORT.md",
    "templates/TASK_HANDOFF.md",
    "decisions/README.md",
    "scripts/verify_project_guide.py",
]


def _dogrulayici():
    """verify_project_guide modülünü yükler (script konumundan)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("vpg_test", SCRIPT)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


class YapiTests(unittest.TestCase):
    """Zorunlu, Git tarafından izlenen rehber dosyaları."""

    def test_kok_yonlendiriciler_var(self):
        for ad in ZORUNLU_KOK:
            self.assertTrue((KOK / ad).is_file(), f"eksik: {ad}")

    def test_zorunlu_belgeler_var(self):
        for ad in ZORUNLU_BELGE + ZORUNLU_EK:
            self.assertTrue((REHBER / ad).is_file(), f"eksik: PROJECT_GUIDE/{ad}")

    def test_kok_yonlendiriciler_kisa(self):
        for ad in ZORUNLU_KOK:
            satir = (KOK / ad).read_text(encoding="utf-8").splitlines()
            self.assertLessEqual(len(satir), 70,
                                 f"{ad} çok uzun ({len(satir)} satır)")

    def test_kok_yonlendiriciler_indekse_yonlendirir(self):
        for ad in ZORUNLU_KOK:
            metin = (KOK / ad).read_text(encoding="utf-8")
            self.assertIn("PROJECT_GUIDE/INDEX.md", metin,
                          f"{ad} INDEX'e yönlendirmiyor")


class VerifyNormalTests(unittest.TestCase):
    """Script'in normal modu depo üzerinde temiz geçmeli."""

    def test_script_normal_mod_gecer(self):
        sonuc = subprocess.run([sys.executable, str(SCRIPT)],
                               capture_output=True, text=True, timeout=180)
        self.assertEqual(sonuc.returncode, 0,
                         f"normal mod başarısız:\n{sonuc.stdout}\n{sonuc.stderr}")

    def test_script_stale_modu_calisir(self):
        sonuc = subprocess.run([sys.executable, str(SCRIPT), "--stale"],
                               capture_output=True, text=True, timeout=180)
        self.assertIn(sonuc.returncode, (0, 1),
                      "stale modu beklenmeyen çıkış kodu")


class ManifestTests(unittest.TestCase):

    def setUp(self):
        self.veri = json.loads(
            (REHBER / "project_manifest.json").read_text(encoding="utf-8"))

    def test_stable_ve_snapshot_ayri(self):
        self.assertIn("stable", self.veri)
        self.assertIn("snapshot", self.veri)

    def test_stable_alanlari(self):
        s = self.veri["stable"]
        for alan in ("project_name", "entry_point", "test_command",
                     "build_command", "version_sources", "data_safety_boundary",
                     "release_stages"):
            self.assertIn(alan, s, f"stable.{alan} eksik")

    def test_snapshot_alanlari_ve_eskime_uyarisi(self):
        s = self.veri["snapshot"]
        for alan in ("source_commit", "version", "test_result", "dist_exe",
                     "installer", "installed_exe", "signing",
                     "frozen_smoke", "installer_test"):
            self.assertIn(alan, s, f"snapshot.{alan} eksik")
        self.assertTrue(str(self.veri.get("snapshot_notice", "")).strip(),
                        "snapshot alanlarının eskiyebileceği not edilmemiş")

    def test_giris_noktasi_ve_test_komutu_gercek(self):
        s = self.veri["stable"]
        self.assertTrue((KOK / s["entry_point"]).is_file())
        self.assertIn("pytest", s["test_command"])

    def test_kaynak_ve_rehber_test_sonuclari_ayri(self):
        s = self.veri["snapshot"]
        for alan in ("source_baseline_commit", "source_test_result",
                     "guide_integrated_test_result", "live_state_notice"):
            self.assertIn(alan, s, f"snapshot.{alan} eksik")
        self.assertGreater(s["guide_integrated_test_result"]["passed"],
                           s["source_test_result"]["passed"],
                           "rehber dahil test sayısı kaynaktan büyük olmalı")

    def test_snapshot_hash_bicimi(self):
        for anahtar in ("dist_exe", "installer", "installed_exe"):
            h = self.veri["snapshot"][anahtar].get("sha256", "")
            self.assertRegex(h, r"^[0-9A-F]{64}$",
                             f"{anahtar}.sha256 biçimi hatalı")


class IndexYonlendirmeTests(unittest.TestCase):

    def test_index_hedefleri_var(self):
        modul = _dogrulayici()
        hatalar = modul.kontrol_yonlendirme(KOK)
        self.assertEqual(hatalar, [], f"INDEX yönlendirme hatası: {hatalar}")

    def test_index_gorev_turlerini_kapsar(self):
        metin = (REHBER / "INDEX.md").read_text(encoding="utf-8").lower()
        for konu in ("import", "release", "build", "worker", "denetim"):
            self.assertIn(konu, metin, f"INDEX '{konu}' görevini yönlendirmiyor")


class _GeciciRehber(unittest.TestCase):
    """Geçici kopya üzerinde bozma testleri — depoya DOKUNMAZ."""

    def setUp(self):
        self._tmp = TemporaryDirectory(prefix="pg_test_", ignore_cleanup_errors=True)
        self.addCleanup(self._tmp.cleanup)
        self.kok = Path(self._tmp.name) / "proje"
        (self.kok).mkdir()
        shutil.copytree(REHBER, self.kok / "PROJECT_GUIDE")
        for ad in ZORUNLU_KOK:
            shutil.copy2(KOK / ad, self.kok / ad)
        # Temiz clone = TRACKED kaynaklar var, LOCAL-ONLY yollar yok.
        # Bu yüzden `covers` altındaki tracked yollar için iskelet üretilir;
        # packaging/assets/dist/installer_output bilerek oluşturulmaz.
        self.modul = _dogrulayici()
        yerel_only = self.modul.YEREL_ONLY
        yollar = {"main.py", "core/constants.py"}
        for belge in (self.kok / "PROJECT_GUIDE").rglob("*.md"):
            veri = self.modul.frontmatter_oku(belge) or {}
            for kapsam in veri.get("covers") or []:
                if not str(kapsam).startswith(yerel_only):
                    yollar.add(str(kapsam))
        for yol in sorted(yollar):
            hedef = self.kok / yol
            hedef.parent.mkdir(parents=True, exist_ok=True)
            if not hedef.exists():
                hedef.write_text("# test kopyasi\n", encoding="utf-8")

    def _belge(self, ad):
        return self.kok / "PROJECT_GUIDE" / ad


class AyirtEdiciTests(_GeciciRehber):

    def test_bozuk_ic_baglanti_yakalanir(self):
        y = self._belge("INDEX.md")
        y.write_text(y.read_text(encoding="utf-8")
                     + "\n[kırık](OLMAYAN_BELGE.md)\n", encoding="utf-8")
        hatalar = self.modul.kontrol_baglantilar(self.kok)
        self.assertTrue(any("OLMAYAN_BELGE.md" in h for h in hatalar),
                        f"bozuk bağlantı yakalanmadı: {hatalar}")

    def test_eksik_covers_yolu_yakalanir(self):
        y = self._belge("ARCHITECTURE.md")
        metin = y.read_text(encoding="utf-8")
        metin = metin.replace("covers:", "covers:\n  - yok/olmayan_modul.py", 1)
        y.write_text(metin, encoding="utf-8")
        hatalar = self.modul.kontrol_frontmatter(self.kok)
        self.assertTrue(any("olmayan_modul.py" in h for h in hatalar),
                        f"eksik covers yolu yakalanmadı: {hatalar}")

    def test_yasak_mutlak_kullanici_yolu_yakalanir(self):
        y = self._belge("DATA_AND_PATHS.md")
        y.write_text(y.read_text(encoding="utf-8")
                     + "\nVeri: C:\\Users\\GercekKisi\\AppData\\Local\\x\n",
                     encoding="utf-8")
        hatalar = self.modul.kontrol_gizli(self.kok)
        self.assertTrue(any("DATA_AND_PATHS.md" in h for h in hatalar),
                        f"mutlak kullanıcı yolu yakalanmadı: {hatalar}")
        self.assertFalse(any("GercekKisi" in h for h in hatalar),
                         "hata metni gerçek yolu ifşa ediyor")

    def test_acik_gizli_deger_yakalanir(self):
        y = self._belge("SECURITY_AND_PRIVACY.md")
        y.write_text(y.read_text(encoding="utf-8")
                     + "\nsmtp_password = \"Gercek1234Parola\"\n",
                     encoding="utf-8")
        hatalar = self.modul.kontrol_gizli(self.kok)
        self.assertTrue(any("SECURITY_AND_PRIVACY.md" in h for h in hatalar))
        self.assertFalse(any("Gercek1234Parola" in h for h in hatalar),
                         "hata metni gizli değeri ifşa ediyor")

    def test_placeholder_yollar_false_positive_uretmez(self):
        y = self._belge("DATA_AND_PATHS.md")
        y.write_text(y.read_text(encoding="utf-8")
                     + "\nÖrnek: <USER_DATA_ROOT>\\data\\database.db\n",
                     encoding="utf-8")
        hatalar = self.modul.kontrol_gizli(self.kok)
        self.assertEqual([h for h in hatalar if "DATA_AND_PATHS" in h], [])

    def test_yanlis_artifact_hash_yakalanir(self):
        y = self._belge("project_manifest.json")
        veri = json.loads(y.read_text(encoding="utf-8"))
        veri["snapshot"]["dist_exe"]["sha256"] = "A" * 64
        y.write_text(json.dumps(veri, ensure_ascii=False, indent=2),
                     encoding="utf-8")
        hedef = self.kok / veri["snapshot"]["dist_exe"]["path"]
        hedef.parent.mkdir(parents=True, exist_ok=True)
        hedef.write_bytes(b"farkli icerik")
        hatalar, _ = self.modul.kontrol_artifacts(self.kok, zorunlu=True)
        self.assertTrue(any("dist_exe" in h for h in hatalar),
                        f"yanlış hash yakalanmadı: {hatalar}")

    def test_git_yoksa_guvenli_uyari(self):
        hatalar = self.modul.kontrol_stale(self.kok)
        self.assertTrue(all(isinstance(h, str) for h in hatalar))
        self.assertTrue(any("doğrulanamadı" in h.lower() for h in hatalar),
                        "git geçmişi yokken güvenli uyarı üretilmedi")


class TemizCloneTests(_GeciciRehber):
    """Local-only artifact'lar yokken normal mod kırılmaz, --release kırılır."""

    def test_normal_mod_artifact_yokken_gecer(self):
        hatalar, _ = self.modul.calistir(self.kok, artifacts=False,
                                         release=False, stale=False)
        self.assertEqual(hatalar, [], f"temiz clone'da normal mod kırıldı: {hatalar}")

    def test_release_modu_artifact_yokken_kirilir(self):
        hatalar, _ = self.modul.calistir(self.kok, artifacts=True,
                                         release=True, stale=False)
        self.assertTrue(hatalar, "--release eksik yerel girdilerle başarılı sayıldı")


class ArtifactUyariTests(_GeciciRehber):
    """Artifact eksikliği: --artifacts uyarır (exit 0), --release hata verir."""

    def _surumleri_esitle(self):
        """Hedef sürüm = artifact sürümü (sürüm uyuşmazlığı uyarısını kapatır).

        Böylece artifact testleri YALNIZ hash/boyut davranışını ölçer.
        """
        y = self._belge("project_manifest.json")
        veri = json.loads(y.read_text(encoding="utf-8"))
        veri["snapshot"]["artifact_built_for_version"] = \
            veri["snapshot"].get("version")
        veri["snapshot"]["artifact_verification_status"] = "current"
        veri["snapshot"]["release_ready"] = True
        y.write_text(json.dumps(veri, ensure_ascii=False, indent=2),
                     encoding="utf-8")

    def _artifact_yaz(self, dogru: bool):
        veri = json.loads(
            self._belge("project_manifest.json").read_text(encoding="utf-8"))
        bilgi = veri["snapshot"]["dist_exe"]
        hedef = self.kok / bilgi["path"]
        hedef.parent.mkdir(parents=True, exist_ok=True)
        icerik = b"dist exe icerigi"
        hedef.write_bytes(icerik)
        kur = veri["snapshot"]["installer"]
        kurulum = self.kok / kur["path"]
        kurulum.parent.mkdir(parents=True, exist_ok=True)
        kurulum.write_bytes(b"installer icerigi")
        if dogru:
            import hashlib
            bilgi["sha256"] = hashlib.sha256(icerik).hexdigest().upper()
            bilgi["size"] = len(icerik)
            kur["sha256"] = hashlib.sha256(b"installer icerigi").hexdigest().upper()
            kur["size"] = len(b"installer icerigi")
            self._belge("project_manifest.json").write_text(
                json.dumps(veri, ensure_ascii=False, indent=2), encoding="utf-8")

    def test_artifacts_modu_eksikte_uyarir_hata_vermez(self):
        hatalar, uyarilar = self.modul.kontrol_artifacts(self.kok, zorunlu=False)
        self.assertEqual(hatalar, [], "eksik artifact hata sayıldı")
        self.assertTrue(any("yerel doğrulama atlandı" in u for u in uyarilar),
                        f"eksik artifact uyarısı yok: {uyarilar}")

    def test_artifacts_modu_exit_sifir_ve_uyari_dondurur(self):
        hatalar, uyarilar = self.modul.calistir(self.kok, artifacts=True,
                                                release=False, stale=False)
        self.assertEqual(hatalar, [])
        self.assertTrue(any("yerel doğrulama atlandı" in u for u in uyarilar),
                        f"calistir() uyarıyı döndürmedi: {uyarilar}")

    def test_release_modu_eksikte_hata_verir(self):
        hatalar, _ = self.modul.kontrol_artifacts(self.kok, zorunlu=True)
        self.assertTrue(any("dist_exe" in h for h in hatalar))

    def test_dogru_hash_uyari_uretmez(self):
        self._artifact_yaz(dogru=True)
        self._surumleri_esitle()
        hatalar, uyarilar = self.modul.kontrol_artifacts(self.kok, zorunlu=False)
        self.assertEqual(hatalar, [])
        self.assertEqual(uyarilar, [], f"doğru artifact gereksiz uyardı: {uyarilar}")

    def test_hedef_surum_farkliysa_uyarir(self):
        """Sürüm yükseltmesi sonrası eski artifact: uyarı (exit 0 korunur)."""
        self._artifact_yaz(dogru=True)
        y = self._belge("project_manifest.json")
        veri = json.loads(y.read_text(encoding="utf-8"))
        veri["snapshot"]["version"] = "v9.9"
        veri["snapshot"]["artifact_built_for_version"] = "v9.8"
        y.write_text(json.dumps(veri, ensure_ascii=False, indent=2),
                     encoding="utf-8")
        hatalar, uyarilar = self.modul.kontrol_artifacts(self.kok, zorunlu=False)
        self.assertEqual(hatalar, [], "sürüm farkı normal modda hata olmamalı")
        self.assertTrue(any("v9.9" in u and "v9.8" in u for u in uyarilar),
                        f"sürüm farkı uyarısı yok: {uyarilar}")

    def test_hedef_surum_farkliysa_release_hata(self):
        self._artifact_yaz(dogru=True)
        y = self._belge("project_manifest.json")
        veri = json.loads(y.read_text(encoding="utf-8"))
        veri["snapshot"]["version"] = "v9.9"
        veri["snapshot"]["artifact_built_for_version"] = "v9.8"
        veri["snapshot"]["release_candidate_ready"] = False
        y.write_text(json.dumps(veri, ensure_ascii=False, indent=2),
                     encoding="utf-8")
        hatalar, _ = self.modul.kontrol_artifacts(self.kok, zorunlu=True)
        self.assertTrue(any("v9.8" in h for h in hatalar),
                        "release modunda eski artifact hata vermedi")
        self.assertTrue(any("release_candidate_ready" in h for h in hatalar),
                        "release_candidate_ready=false hata olarak raporlanmadı")

    def test_yanlis_hash_her_iki_modda_hata(self):
        self._artifact_yaz(dogru=False)
        self._surumleri_esitle()
        for zorunlu in (False, True):
            hatalar, _ = self.modul.kontrol_artifacts(self.kok, zorunlu=zorunlu)
            self.assertTrue(any("dist_exe" in h for h in hatalar),
                            f"zorunlu={zorunlu} yanlış hash yakalanmadı")


class _GeciciGitDepo(unittest.TestCase):
    """Geçici git deposu — GERÇEK çalışma ağacına dokunulmaz."""

    def setUp(self):
        self.modul = _dogrulayici()
        self._tmp = TemporaryDirectory(prefix="pg_git_", ignore_cleanup_errors=True)
        self.addCleanup(self._tmp.cleanup)
        self.kok = Path(self._tmp.name) / "depo"
        self.kok.mkdir()
        shutil.copytree(REHBER, self.kok / "PROJECT_GUIDE")
        for ad in ZORUNLU_KOK:
            shutil.copy2(KOK / ad, self.kok / ad)
        (self.kok / "tests").mkdir(exist_ok=True)
        (self.kok / "tests" / "test_project_guide.py").write_text(
            "# rehber testi kopyasi\n", encoding="utf-8")
        self.kapsanan = set()
        for belge in (self.kok / "PROJECT_GUIDE").rglob("*.md"):
            for k in (self.modul.frontmatter_oku(belge) or {}).get("covers") or []:
                if not str(k).startswith(self.modul.YEREL_ONLY):
                    self.kapsanan.add(str(k))
        for yol in sorted(self.kapsanan | {"main.py", "core/constants.py"}):
            h = self.kok / yol
            h.parent.mkdir(parents=True, exist_ok=True)
            if not h.exists():
                h.write_text("# kaynak\n", encoding="utf-8")
        self._git("init", "-q")
        self._git("config", "user.email", "test@example.invalid")
        self._git("config", "user.name", "Test")
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "ilk")
        self.temel = self._git("rev-parse", "--short", "HEAD").strip()
        self._frontmatter_sabitle(self.temel)
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "guide-only: rehber metadata")

    def _git(self, *args):
        s = subprocess.run(["git", "-C", str(self.kok), *args],
                           capture_output=True, text=True, timeout=60)
        return s.stdout

    def _frontmatter_sabitle(self, commit):
        for belge in (self.kok / "PROJECT_GUIDE").rglob("*.md"):
            metin = belge.read_text(encoding="utf-8")
            yeni = re.sub(r"last_verified_commit:.*",
                          f"last_verified_commit: {commit}", metin, count=1)
            if yeni != metin:
                belge.write_text(yeni, encoding="utf-8")

    def _kapsanan_bir_dosya(self) -> str:
        return sorted(self.kapsanan)[0]


class StaleCalismaAgaciTests(_GeciciGitDepo):
    """Commit edilmemiş kapsanan değişiklikler de stale sayılmalı."""

    def test_guide_only_commit_stale_uretmez(self):
        uyarilar = self.modul.kontrol_stale(self.kok)
        self.assertEqual(uyarilar, [],
                         f"guide-only commit stale üretti: {uyarilar}")

    def test_unstaged_kapsanan_degisiklik_stale(self):
        yol = self.kok / self._kapsanan_bir_dosya()
        yol.write_text("# degisti\n", encoding="utf-8")
        uyarilar = self.modul.kontrol_stale(self.kok)
        self.assertTrue(uyarilar, "unstaged kapsanan değişiklik stale vermedi")

    def test_staged_kapsanan_degisiklik_stale(self):
        yol = self.kok / self._kapsanan_bir_dosya()
        yol.write_text("# degisti\n", encoding="utf-8")
        self._git("add", "-A")
        uyarilar = self.modul.kontrol_stale(self.kok)
        self.assertTrue(uyarilar, "staged kapsanan değişiklik stale vermedi")

    def test_untracked_kapsanan_dosya_stale(self):
        hedef = self.kok / "core" / "restart.py"
        if hedef.exists():
            self._git("rm", "-q", "--cached", "core/restart.py")
            self._git("commit", "-q", "-m", "kaldir")
        hedef.parent.mkdir(parents=True, exist_ok=True)
        hedef.write_text("# yeni untracked\n", encoding="utf-8")
        uyarilar = self.modul.kontrol_stale(self.kok)
        self.assertTrue(any("ARCHITECTURE.md" in u for u in uyarilar),
                        f"untracked kapsanan dosya stale vermedi: {uyarilar}")

    def test_kapsam_disi_degisiklik_stale_degil(self):
        (self.kok / "OKUBENI_yerel.txt").write_text("x\n", encoding="utf-8")
        uyarilar = self.modul.kontrol_stale(self.kok)
        self.assertEqual(uyarilar, [], f"kapsam dışı değişiklik stale saydı: {uyarilar}")

    def test_yalniz_rehber_degisikligi_stale_degil(self):
        y = self.kok / "PROJECT_GUIDE" / "ARCHITECTURE.md"
        y.write_text(y.read_text(encoding="utf-8") + "\nek satır\n",
                     encoding="utf-8")
        (self.kok / "CLAUDE.md").write_text(
            (self.kok / "CLAUDE.md").read_text(encoding="utf-8") + "\n",
            encoding="utf-8")
        (self.kok / "tests" / "test_project_guide.py").write_text(
            "# guncellendi\n", encoding="utf-8")
        uyarilar = self.modul.kontrol_stale(self.kok)
        self.assertEqual(uyarilar, [],
                         f"rehber altyapısı değişikliği stale saydı: {uyarilar}")

    def test_gercek_kaynak_degisirse_guide_commit_sonrasi_da_stale(self):
        yol = self.kok / self._kapsanan_bir_dosya()
        yol.write_text("# gercek kaynak degisti\n", encoding="utf-8")
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "kaynak + rehber")
        uyarilar = self.modul.kontrol_stale(self.kok)
        self.assertTrue(uyarilar, "commit'lenmiş kaynak değişikliği stale vermedi")

    def test_ayni_dosya_icin_tek_stale_nedeni(self):
        yol = self.kok / self._kapsanan_bir_dosya()
        yol.write_text("# hem staged hem unstaged\n", encoding="utf-8")
        self._git("add", "-A")
        yol.write_text("# tekrar degisti\n", encoding="utf-8")
        uyarilar = self.modul.kontrol_stale(self.kok)
        ilgili = [u for u in uyarilar if "stale:" in u]
        belgeler = [u.split(":")[1].strip().split()[0] for u in ilgili]
        self.assertEqual(len(belgeler), len(set(belgeler)),
                         f"aynı belge için birden fazla stale satırı: {ilgili}")


class SnapshotDiliTests(unittest.TestCase):
    """Commit edildiği anda yanlışlaşacak canlı-durum iddiası olmamalı."""

    def setUp(self):
        self.metin = (REHBER / "CURRENT_STATUS.md").read_text(encoding="utf-8")

    def test_canli_git_iddiasi_yok(self):
        for yasak in ("commit edilmedi", "commit edilmemiş", "çalışma ağacı temiz",
                      "HEAD = origin/main", "ahead/behind 0/0"):
            self.assertNotIn(yasak, self.metin,
                             f"CURRENT_STATUS canlı git iddiası içeriyor: {yasak}")

    def test_canli_durumun_yeniden_olculecegi_yaziyor(self):
        self.assertIn("git rev-parse HEAD", self.metin)
        self.assertIn("yeniden ölçülür", self.metin)

    def test_temel_commit_ve_iki_test_sonucu_yaziyor(self):
        """Baseline ve rehber dahil sonuç ayrı ayrı ve manifest ile tutarlı."""
        self.assertIn("060baf3", self.metin)
        veri = json.loads(
            (REHBER / "project_manifest.json").read_text(encoding="utf-8"))
        kaynak = veri["snapshot"]["source_test_result"]["passed"]
        rehber = veri["snapshot"]["guide_integrated_test_result"]["passed"]
        self.assertIn(str(kaynak), self.metin,
                      "baseline test sayısı CURRENT_STATUS ile uyuşmuyor")
        self.assertIn(str(rehber), self.metin,
                      "rehber dahil test sayısı CURRENT_STATUS ile uyuşmuyor")

    # ── Güncel tam suite sayıları tek kaynaktan okunur ───────────────────
    #
    # Sayılar teste SABİTLENMEZ: manifest ve CURRENT_STATUS'ten okunup
    # karşılaştırılır, böylece suite büyüdükçe test kendiliğinden geçerli
    # kalır ama iki kanonik yer birbirinden ayrışamaz.

    _SUITE_RE = re.compile(
        r"\*\*(\d+)\s+passed,\s*(\d+)\s+skipped,\s*(\d+)\s+subtests\*\*")

    def _manifest_snapshot(self):
        return json.loads(
            (REHBER / "project_manifest.json").read_text(encoding="utf-8")
        )["snapshot"]

    def test_current_status_tam_suite_manifestle_ayni(self):
        m = self._SUITE_RE.search(self.metin)
        self.assertIsNotNone(
            m, "CURRENT_STATUS güncel tam suite satırı "
               "'**N passed, N skipped, N subtests**' biçiminde değil")
        passed, skipped, subtests = (int(x) for x in m.groups())
        rehber = self._manifest_snapshot()["guide_integrated_test_result"]
        self.assertEqual(passed, rehber.get("passed"),
                         "passed CURRENT_STATUS ile manifestte farklı")
        self.assertEqual(skipped, rehber.get("skipped"),
                         "skipped CURRENT_STATUS ile manifestte farklı")
        self.assertEqual(subtests, rehber.get("subtests_passed"),
                         "subtests CURRENT_STATUS ile manifestte farklı")

    def test_manifest_iki_tam_suite_alani_esit(self):
        s = self._manifest_snapshot()
        rehber, genel = s["guide_integrated_test_result"], s["test_result"]
        for alan in ("passed", "skipped", "subtests_passed"):
            self.assertEqual(rehber.get(alan), genel.get(alan),
                             f"test_result.{alan} guide_integrated ile eşit değil")

    def test_kaynak_baseline_ayri_kalir(self):
        """Tarihsel baseline (648/29 · 060baf3) tam suite ile karışmaz."""
        s = self._manifest_snapshot()
        kaynak = s["source_test_result"]
        self.assertEqual(kaynak.get("baseline_commit"), "060baf3")
        self.assertNotEqual(kaynak.get("passed"),
                            s["guide_integrated_test_result"].get("passed"),
                            "baseline sayısı tam suite ile aynı yazılmış")


class ChangelogReleaseKapisiTests(_GeciciRehber):
    """`--release` kapısı: hedef sürümün CHANGELOG bölümü yayına hazır olmalı.

    Tag'in konduğu commit'in kendi içinde "yayınlanmadı" demesi kabul edilemez.
    Kural YALNIZ release kapısında zorunludur; sürüm hazırlığı sırasında
    normal / --stale / --artifacts modları taslak changelog'a izin verir.
    """

    TASLAK = "## [v4.1] — hazırlanıyor (yayınlanmadı)"
    YAYIN = "## [v4.1] — 2026-07-31"
    GOVDE = "\n- Bir değişiklik.\n"
    ESKI = "\n## [v4.0] — 2026-07-10\n\n- Eski sürüm notu.\n"

    def _changelog(self, metin):
        y = self.kok / "docs" / "CHANGELOG.md"
        y.parent.mkdir(parents=True, exist_ok=True)
        y.write_text("# Değişiklik Geçmişi\n\n" + metin, encoding="utf-8")
        return y

    def _hedefi_ayarla(self, surum="v4.1", hazir=True):
        y = self._belge("project_manifest.json")
        veri = json.loads(y.read_text(encoding="utf-8"))
        veri["snapshot"]["version"] = surum
        veri["snapshot"]["release_candidate_ready"] = hazir
        veri["snapshot"].setdefault("release", {})["target_version"] = surum
        y.write_text(json.dumps(veri, ensure_ascii=False, indent=2),
                     encoding="utf-8")

    def _release_hatalari(self):
        return self.modul.kontrol_changelog(self.kok, zorunlu=True)

    # 1 — taslak başlık release kapısını düşürür
    def test_taslak_baslik_release_kapisini_dusurur(self):
        self._hedefi_ayarla()
        self._changelog(self.TASLAK + self.GOVDE + self.ESKI)
        self.assertTrue(self._release_hatalari(),
                        "taslak changelog başlığı release kapısını geçti")

    # 2 — hedef sürüm bölümü yok
    def test_hedef_surum_bolumu_yoksa_kirmizi(self):
        self._hedefi_ayarla()
        self._changelog(self.ESKI.lstrip())
        self.assertTrue(any("v4.1" in h for h in self._release_hatalari()),
                        "eksik sürüm bölümü yakalanmadı")

    # 3 — tarih biçimi yanlış
    def test_bozuk_tarih_bicimi_kirmizi(self):
        self._hedefi_ayarla()
        for kotu in ("31.07.2026", "2026/07/31", "Temmuz 2026", "2026-7-31"):
            with self.subTest(tarih=kotu):
                self._changelog(f"## [v4.1] — {kotu}"
                                + self.GOVDE + self.ESKI)
                self.assertTrue(self._release_hatalari(),
                                f"bozuk tarih kabul edildi: {kotu}")

    # 4 — yayın başlığı geçer
    def test_yayin_basligi_gecer(self):
        self._hedefi_ayarla()
        self._changelog(self.YAYIN + self.GOVDE + self.ESKI)
        self.assertEqual(self._release_hatalari(), [])

    # 5 — eski sürümdeki tarihsel taslak metni hedefi etkilemez
    def test_eski_surumdeki_yayinlanmadi_metni_etkilemez(self):
        self._hedefi_ayarla()
        eski = ("\n## [v4.0] — 2026-07-10\n\n"
                "> Not: Bu sürüm henüz yayınlanmadı; tarih sonra yazılacaktı.\n")
        self._changelog(self.YAYIN + self.GOVDE + eski)
        self.assertEqual(self._release_hatalari(), [],
                         "eski sürümün tarihsel metni hedef bölümü düşürdü")

    # Mod kapısı — hazırlık sırasında taslak changelog serbest
    def test_taslak_yalniz_release_modunda_hata(self):
        self._hedefi_ayarla()
        self._changelog(self.TASLAK + self.GOVDE + self.ESKI)
        self.assertEqual(self.modul.kontrol_changelog(self.kok, zorunlu=False),
                         [], "taslak changelog release DIŞI modda hata üretti")
        for kw in ({}, {"stale": True}, {"artifacts": True}):
            with self.subTest(mod=kw or "normal"):
                hatalar, _ = self.modul.calistir(self.kok, **kw)
                self.assertFalse([h for h in hatalar if "changelog" in h],
                                 f"{kw or 'normal'} modunda changelog hatası")


class KanonikBilgiTests(unittest.TestCase):
    """Legacy belgelerden aktarılan benzersiz bilgiler kanonik yerinde olmalı.

    Kırılgan tam metin karşılaştırması YAPILMAZ; her madde için birkaç ayırt
    edici anahtar aranır.
    """

    def _oku(self, ad):
        return (REHBER / ad).read_text(encoding="utf-8")

    def test_release_checklist_github_release_yolu(self):
        m = self._oku("RELEASE_CHECKLIST.md")
        for anahtar in ("gh release create", "gh release upload", "asset",
                        "read-back"):
            self.assertIn(anahtar, m, f"RELEASE_CHECKLIST '{anahtar}' içermiyor")

    def test_release_checklist_mevcut_release_uzerine_yazma_izni(self):
        m = self._oku("RELEASE_CHECKLIST.md").lower()
        self.assertIn("--clobber", m)
        self.assertIn("açık", m)

    def test_verification_guide_canli_updater_senaryosu(self):
        m = self._oku("VERIFICATION_GUIDE.md")
        for anahtar in ("updater", "asset", "geri dönüş",
                        "updater_end_to_end_verified"):
            self.assertIn(anahtar, m, f"VERIFICATION_GUIDE '{anahtar}' içermiyor")

    def test_dagitim_temizligi_araci_belgelenmis(self):
        m = self._oku("CHANGE_PROTOCOL.md")
        self.assertIn("clear_for_distribution.py", m)
        self.assertIn("--yes", m)
        for anahtar in ("izin", "yedek"):
            self.assertIn(anahtar, m.lower(),
                          f"temizlik aracı '{anahtar}' koşulu yazılmamış")

    def test_veri_dosyasi_envanteri(self):
        m = self._oku("DATA_AND_PATHS.md")
        self.assertIn("theme.txt", m)
        self.assertIn("backup_meta.json", m)

    def test_decisions_kar_sinirini_adr_ye_baglar(self):
        m = self._oku("DECISIONS.md")
        self.assertIn("decisions/0001-profit-data-boundary.md", m,
                      "DECISIONS kâr sınırı ADR'sine bağlantı vermiyor")

    def test_kar_siniri_adr_icerigi(self):
        yol = REHBER / "decisions" / "0001-profit-data-boundary.md"
        self.assertTrue(yol.is_file(), "kâr sınırı ADR'si yok")
        m = yol.read_text(encoding="utf-8")
        self.assertTrue(m.startswith("---"), "ADR frontmatter'ı yok")
        veri = _dogrulayici().frontmatter_oku(yol) or {}
        for alan in ("purpose", "read_when", "covers", "last_verified_commit",
                     "last_verified_date", "volatile"):
            self.assertIn(alan, veri, f"ADR frontmatter '{alan}' eksik")
        for anahtar in ("offer_items", "cost_price", "export"):
            self.assertIn(anahtar, m, f"ADR '{anahtar}' konusunu içermiyor")

    def test_ertelenmis_fikirler_taahhut_degil(self):
        m = self._oku("DECISIONS.md")
        self.assertIn("Ertelenmiş fikirler", m)
        self.assertIn("taahhüt değil", m.lower().replace("i̇", "i")
                      if "taahhüt değil" not in m else m)
        for fikir in ("i18n", "Web", "Inter"):
            self.assertIn(fikir, m, f"ertelenmiş fikir '{fikir}' yok")

    def test_kucuk_teknik_kararlar(self):
        m = self._oku("DECISIONS.md")
        for anahtar in ("pt", "ON DELETE", "F1", "backup_%Y"):
            self.assertIn(anahtar, m, f"teknik karar '{anahtar}' yok")


class ProjeAmaciTests(unittest.TestCase):
    """Yeni bir ajan projenin ne işe yaradığını çıkarım yapmadan bulmalı."""

    ANAHTARLAR = ("müşteri", "ürün", "teklif", "PDF", "Windows masaüstü")
    ANA_KAYNAK = "ARCHITECTURE.md"

    def test_kanonik_amac_ana_kaynakta(self):
        metin = (REHBER / self.ANA_KAYNAK).read_text(encoding="utf-8")
        for anahtar in self.ANAHTARLAR:
            self.assertIn(anahtar, metin,
                          f"{self.ANA_KAYNAK} amaç tanımında '{anahtar}' yok")

    def test_amac_tek_ana_kaynakta_tanimli(self):
        """Aynı tanım paragrafı birden çok belgede kopyalanmamalı."""
        imza = "yaşam döngüsünü güvenli biçimde takip etmek"
        tasiyan = [p.name for p in sorted((REHBER).glob("*.md"))
                   if imza in p.read_text(encoding="utf-8")]
        self.assertEqual(tasiyan, [self.ANA_KAYNAK],
                         f"amaç tanımı birden çok yerde: {tasiyan}")

    def test_index_amaca_yonlendiriyor(self):
        metin = (REHBER / "INDEX.md").read_text(encoding="utf-8")
        self.assertIn("Proje ne yapar", metin,
                      "INDEX amaç tanımına yönlendirmiyor")
        self.assertIn(self.ANA_KAYNAK, metin)


class CanliRemoteIddiaTests(unittest.TestCase):
    """Snapshot belgeleri değişken git durumunu iddia etmemeli."""

    SNAPSHOT_BELGELERI = ("KNOWN_RISKS.md", "CURRENT_STATUS.md")
    # "origin/main geride", "origin/main = <hash>", "N commit önde" gibi
    YASAK = (
        re.compile(r"origin/main[^\n]{0,40}\b(geride|önde|ahead|behind)\b",
                   re.IGNORECASE),
        re.compile(r"origin/main\s*[=:]\s*`?[0-9a-f]{7,40}`?", re.IGNORECASE),
        re.compile(r"\b\d+\s*commit\s*(önde|geride)\b", re.IGNORECASE),
    )

    def test_snapshot_belgelerinde_canli_remote_iddiasi_yok(self):
        for ad in self.SNAPSHOT_BELGELERI:
            metin = (REHBER / ad).read_text(encoding="utf-8")
            for kalip in self.YASAK:
                m = kalip.search(metin)
                self.assertIsNone(
                    m, f"{ad} canlı remote iddiası içeriyor: {kalip.pattern}")

    def test_known_risks_r3_degismez_gercekleri_yaziyor(self):
        metin = (REHBER / "KNOWN_RISKS.md").read_text(encoding="utf-8")
        satir = [s for s in metin.splitlines() if s.startswith("| R3 ")]
        self.assertTrue(satir, "R3 satırı bulunamadı")
        r3 = satir[0]
        for anahtar in ("doğrulandı", "tag", "release", "updater"):
            self.assertIn(anahtar, r3.lower(),
                          f"R3 '{anahtar}' gerçeğini içermiyor")

    # 2026-07-28'de kaldırılan legacy belgeler. Bunlar düz metin olarak geçtiği
    # için Markdown bağlantı denetimi yakalamaz; boş bağlam devir testinde
    # "bu dosya nerede?" çelişkisi üretirler.
    KALDIRILAN_LEGACY = (
        "GITHUB_IS_AKISI_LOCAL.md",
        "docs/README.md",
        "docs/PROJE_GECMISI.md",
        "docs/ROADMAP.md",
        "docs/YOL_HARITASI_KAR_ANALIZI.md",
    )

    def test_kaldirilan_legacy_belgelere_atif_yok(self):
        hatalar = []
        dosyalar = list(REHBER.rglob("*.md")) + [KOK / a for a in ZORUNLU_KOK]
        for yol in dosyalar:
            for satir_no, satir in enumerate(
                    yol.read_text(encoding="utf-8").splitlines(), 1):
                for ad in self.KALDIRILAN_LEGACY:
                    if ad in satir:
                        hatalar.append(f"{yol.name}:{satir_no} → {ad}")
        self.assertEqual(hatalar, [],
                         f"kaldırılmış legacy belgeye atıf: {hatalar}")

    def test_kaldirilan_legacy_belgeler_gercekten_yok(self):
        """Test listesi gerçekle uyumlu kalsın (dosya geri gelirse fark edilir)."""
        for ad in self.KALDIRILAN_LEGACY:
            self.assertFalse((KOK / ad).exists(),
                             f"{ad} yeniden ortaya çıktı — test listesi güncellenmeli")

    def test_current_status_tekil_test_sayisi_iddiasi(self):
        """Aynı belgede çelişen iki tam suite sayısı bulunmamalı."""
        metin = (REHBER / "CURRENT_STATUS.md").read_text(encoding="utf-8")
        veri = json.loads(
            (REHBER / "project_manifest.json").read_text(encoding="utf-8"))
        guncel = str(veri["snapshot"]["guide_integrated_test_result"]["passed"])
        baseline = str(veri["snapshot"]["source_test_result"]["passed"])
        sayilar = set(re.findall(r"\b(\d{3})\s+(?:passed|test)\b", metin))
        # İzin verilen her sayı MANİFESTE dayanmak zorundadır; serbest
        # metinde gerekçesiz bir test sayısı bırakılamaz.
        kapi = veri["snapshot"].get("build_gate_test_result") or {}
        beklenen = {guncel, baseline, "713"}   # 713: tarihsel build sayısı
        if kapi.get("passed"):
            beklenen.add(str(kapi["passed"]))
        fazla = sayilar - beklenen
        self.assertEqual(fazla, set(),
                         f"CURRENT_STATUS eskimiş test sayısı iddia ediyor: {fazla}")

    def test_upstream_dogrulamasi_release_checkliste_yonlendiriyor(self):
        metin = (REHBER / "KNOWN_RISKS.md").read_text(encoding="utf-8")
        self.assertIn("RELEASE_CHECKLIST.md", metin,
                      "upstream doğrulaması için yönlendirme yok")
        kontrol = (REHBER / "RELEASE_CHECKLIST.md").read_text(encoding="utf-8")
        for adim in ("git fetch origin", "rev-parse", "rev-list"):
            self.assertIn(adim, kontrol,
                          f"RELEASE_CHECKLIST '{adim}' adımını içermiyor")


def _bolum(metin: str, bas_kalip: str, bit_kalip: str) -> str:
    """Belgeden YALNIZ ilgili bölümü keser.

    Böylece test, belgenin başka bir yerinde geçen ilgisiz bir kelimeyle
    yanlışlıkla geçemez. Bölüm bulunamazsa boş string döner (test düşer).
    """
    bas = re.search(bas_kalip, metin, re.M)
    if not bas:
        return ""
    kalan = metin[bas.start():]
    bit = re.search(bit_kalip, kalan[len(bas.group(0)):], re.M)
    return kalan if not bit else kalan[:len(bas.group(0)) + bit.start()]


class R4KaliciDogrulamaTests(unittest.TestCase):
    """R4 → kalıcı kural: modal/progress kanıtı PAKETLİ EXE'de alınır.

    Testler belgenin tamamında kelime aramaz; ilgili bölümü başlık/satır
    sınırıyla keser ve yalnız orada ölçer. Sayı gömülmez.
    """

    def setUp(self):
        vg = (REHBER / "VERIFICATION_GUIDE.md").read_text(encoding="utf-8")
        cs = (REHBER / "CURRENT_STATUS.md").read_text(encoding="utf-8")
        kr = (REHBER / "KNOWN_RISKS.md").read_text(encoding="utf-8")
        # B sınıfı 9. senaryo: sonraki numaralı madde veya sonraki başlığa kadar
        self.b9 = _bolum(vg, r"^9\.\s+\*\*Modal\s*/\s*progress", r"^(#{2,3} |\d+\. )")
        self.ders = _bolum(vg, r"^### .*paketli kanıt zorunlu", r"^#{2,3} ")
        self.cs_r4 = _bolum(cs, r"^## R4 ", r"^## ")
        satir = [s for s in kr.splitlines() if s.startswith("| R4 ")]
        self.r4 = satir[0] if satir else ""

    # 1 ─────────────────────────────────────────────────────────────────
    def test_frozen_b9_olcum_sartlari(self):
        self.assertTrue(self.b9, "VERIFICATION_GUIDE B/9 modal/progress bölümü yok")
        self.assertRegex(self.b9, r"(?i)çok sayfal.*XLSX|XLSX",
                         "B/9 çok sayfalı XLSX kontrolünü tanımlamıyor")
        self.assertIn("IsWindowEnabled", self.b9,
                      "B/9 native IsWindowEnabled ölçümünü şart koşmuyor")
        self.assertRegex(self.b9, r"(?is)progress.{0,80}(bulunmamal|a[çc][ıi]k de[ğg]il|yok)",
                         "B/9 'seçim sırasında progress bulunmamalı' şartını içermiyor")
        self.assertRegex(self.b9, r"(?is)iptal.{0,80}olmamal",
                         "B/9 iptalde DB yazımı olmama şartını içermiyor")

    # 2 ─────────────────────────────────────────────────────────────────
    def test_o16_dersi_paketli_kaniti_zorunlu_kiliyor(self):
        self.assertTrue(self.ders, "'Neden paketli kanıt zorunlu' bölümü yok")
        for anahtar in ("mock", "offscreen", "kaynak"):
            self.assertRegex(self.ders, rf"(?i){anahtar}",
                             f"ders bölümü '{anahtar}' sınırını yazmıyor")
        self.assertRegex(self.ders, r"(?i)yerine ge[çc]emez|kan[ıi]tlamaz",
                         "mock/offscreen/kaynak ölçümünün yetersizliği yazılmamış")
        self.assertRegex(self.ders, r"(?is)pozitif kontrol.{0,400}üretilemedi",
                         "pozitif kontrolün üretilemediği yazılmamış")
        self.assertRegex(self.ders, r"(?i)frozen|paketli",
                         "kanıtın paketli EXE'de alınacağı yazılmamış")

    # 3 ─────────────────────────────────────────────────────────────────
    def test_r4_risk_satiri_kalici_kural(self):
        self.assertTrue(self.r4, "KNOWN_RISKS R4 satırı yok")
        self.assertNotRegex(self.r4, r"(?i)taranmal[ıi]",
                            "R4 hâlâ 'taranmalı' diyor — tarama tamamlandı")
        self.assertIn("2026-07-31", self.r4, "R4 tarama tarihi yok")
        self.assertRegex(self.r4, r"(?i)bulunmad",
                         "R4 'ikinci riskli akış bulunmadı' sonucunu yazmıyor")
        self.assertRegex(self.r4, r"\|\s*D[üu][şs][üu]k\s*\|",
                         "R4 şiddeti Düşük değil")
        self.assertRegex(self.r4, r"(?i)(de[ğg]i[şs]irse|yaln[ıi]z).{0,120}(frozen|paketli)",
                         "R4 sonraki adımı koşullu paketli smoke demiyor")

    # 4 ─────────────────────────────────────────────────────────────────
    def test_current_status_ve_rehber_baglantisi_tutarli(self):
        self.assertTrue(self.cs_r4, "CURRENT_STATUS 'R4 …' bölümü yok")
        self.assertRegex(self.cs_r4, r"(?i)kusur bulunmad|envanter",
                         "CURRENT_STATUS R4 sonucunu yazmıyor")
        self.assertRegex(self.cs_r4, r"(?i)frozen|paketli",
                         "CURRENT_STATUS R4 paketli kanıt kuralını yazmıyor")
        self.assertIn("VERIFICATION_GUIDE.md", self.cs_r4,
                      "CURRENT_STATUS R4 doğrulama rehberine bağlanmıyor")
        self.assertIn("VERIFICATION_GUIDE.md", self.r4,
                      "KNOWN_RISKS R4 doğrulama rehberine bağlanmıyor")


class GizlilikTests(unittest.TestCase):
    """Depodaki gerçek rehber içeriği gizli veri barındırmamalı."""

    def test_repo_rehberinde_gizli_veri_yok(self):
        modul = _dogrulayici()
        self.assertEqual(modul.kontrol_gizli(KOK), [])

    def test_gercek_kullanici_yoluna_erisilmiyor(self):
        for ad in ZORUNLU_BELGE:
            metin = (REHBER / ad).read_text(encoding="utf-8")
            self.assertNotIn("OfferManagementSystem\\data\\database.db",
                             metin.replace("<USER_DATA_ROOT>", "<>"))


if __name__ == "__main__":
    unittest.main()
