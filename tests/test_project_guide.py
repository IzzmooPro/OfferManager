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
        hatalar, uyarilar = self.modul.kontrol_artifacts(self.kok, zorunlu=False)
        self.assertEqual(hatalar, [])
        self.assertEqual(uyarilar, [], f"doğru artifact gereksiz uyardı: {uyarilar}")

    def test_yanlis_hash_her_iki_modda_hata(self):
        self._artifact_yaz(dogru=False)
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
