"""PROJECT_GUIDE tutarlılık denetimi.

Modlar:
    (yok)        yapı, manifest, frontmatter, bağlantı, yönlendirme, gizlilik
    --stale      `covers` altındaki kaynaklar belge doğrulamasından sonra değişti mi
    --artifacts  mevcut artifact'ların SHA256'sı manifest ile uyuşuyor mu
    --release    yukarıdakilerin tamamı ZORUNLU (eksik yerel girdi hata sayılır)

Çıkış kodu 0 = temiz, 1 = hata. Uyarılar çıkışı etkilemez (yalnız --release'te
bazıları hataya dönüşür).

Gizlilik: bulunan gizli değer veya gerçek yol ASLA çıktıya yazılmaz; yalnız
dosya adı, satır numarası ve kural adı raporlanır.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

# ── Sabitler ────────────────────────────────────────────────────────────────

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

FRONTMATTER_ALANLARI = ("purpose", "read_when", "covers",
                        "last_verified_commit", "last_verified_date", "volatile")

MANIFEST_STABLE = ("project_name", "entry_point", "test_command",
                   "build_command", "version_sources", "data_safety_boundary",
                   "release_stages")
MANIFEST_SNAPSHOT = ("source_commit", "version", "test_result", "dist_exe",
                     "installer", "installed_exe", "signing", "frozen_smoke",
                     "installer_test")
HASHLI_ARTIFACT = ("dist_exe", "installer")

# Yalnız yerelde bulunan, temiz clone'da olmayabilecek yollar
YEREL_ONLY = ("packaging/", "assets/", "dist/", "installer_output/",
              "build/", "Import_Test/")

# Yer tutucular — gerçek yol sayılmaz
YER_TUTUCU = ("<PROJECT_ROOT>", "<USER_DATA_ROOT>", "<BACKUP_ROOT>",
              "<TEMP_ROOT>", "<INSTALL_DIR>", "<KULLANICI>", "<version>")

# Gerçek kullanıcı profili yolu: C:\Users\<isim>\  — <...> yer tutucusu serbest
MUTLAK_YOL = re.compile(r"[A-Za-z]:[\\/]Users[\\/](?!<)[^\\/\s\"'`|]+")
# Açık gizli değer kalıpları
# NOT: `smtp_password` gibi ön ekli adları da yakalamak için sol tarafta \b
# KULLANILMAZ; alt çizgi bir kelime karakteri olduğundan sınır oluşmaz.
GIZLI_KALIPLAR = (
    ("parola_atamasi",
     re.compile(r"(?i)(password|parola|passwd|pwd)\s*[:=]\s*[\"'][^\"'<>\s]{4,}")),
    ("api_key",
     re.compile(r"(?i)(api[_-]?key|secret|client[_-]?secret)\s*[:=]\s*[\"'][^\"'<>\s]{8,}")),
    ("token",
     re.compile(r"(?i)token\s*[:=]\s*[\"'][A-Za-z0-9_\-]{16,}")),
)
# Bu kelimeler satırdaysa örnek/politika metnidir → gizli sayılmaz
GUVENLI_ISARET = ("örnek", "ornek", "placeholder", "yer tutucu", "asla",
                  "yazılmaz", "yazilmaz", "tutulmaz", "<")

MD_LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")


# ── Yardımcılar ─────────────────────────────────────────────────────────────

def proje_kokunu_bul() -> Path:
    return Path(__file__).resolve().parents[2]


def _rehber(kok: Path) -> Path:
    return kok / "PROJECT_GUIDE"


def _md_dosyalari(kok: Path):
    r = _rehber(kok)
    if not r.is_dir():
        return []
    return sorted(p for p in r.rglob("*.md") if p.is_file())


def frontmatter_oku(yol: Path) -> dict | None:
    """Basit YAML frontmatter çözümleyici (liste + skaler)."""
    metin = yol.read_text(encoding="utf-8")
    if not metin.startswith("---"):
        return None
    son = metin.find("\n---", 3)
    if son == -1:
        return None
    govde = metin[3:son].strip("\n")
    veri, anahtar = {}, None
    for satir in govde.splitlines():
        if not satir.strip():
            continue
        if satir.lstrip().startswith("- ") and anahtar:
            # `covers:` gibi boş bırakılmış anahtar önce "" olur; ilk liste
            # öğesinde listeye çevrilir, aksi hâlde öğeler sessizce yutulur.
            if not isinstance(veri.get(anahtar), list):
                veri[anahtar] = []
            veri[anahtar].append(satir.lstrip()[2:].strip())
            continue
        if ":" in satir:
            anahtar, _, deger = satir.partition(":")
            anahtar = anahtar.strip()
            deger = deger.strip()
            if deger in ("[]", ""):
                veri[anahtar] = [] if deger == "[]" else ""
            else:
                veri[anahtar] = deger
    return veri


def _git(kok: Path, *args) -> tuple[int, str]:
    try:
        s = subprocess.run(["git", "-C", str(kok), *args],
                           capture_output=True, text=True, timeout=60)
        return s.returncode, s.stdout.strip()
    except Exception:
        return 1, ""


def _sha256(yol: Path) -> str:
    h = hashlib.sha256()
    with open(yol, "rb") as f:
        for blok in iter(lambda: f.read(1 << 20), b""):
            h.update(blok)
    return h.hexdigest().upper()


# ── Kontroller ──────────────────────────────────────────────────────────────

def kontrol_yapi(kok: Path) -> list[str]:
    hatalar = []
    for ad in ZORUNLU_KOK:
        if not (kok / ad).is_file():
            hatalar.append(f"yapi: eksik kök dosya {ad}")
    r = _rehber(kok)
    if not r.is_dir():
        return hatalar + ["yapi: PROJECT_GUIDE klasörü yok"]
    for ad in ZORUNLU_BELGE + ZORUNLU_EK:
        if not (r / ad).is_file():
            hatalar.append(f"yapi: eksik PROJECT_GUIDE/{ad}")
    return hatalar


def kontrol_manifest(kok: Path) -> list[str]:
    yol = _rehber(kok) / "project_manifest.json"
    if not yol.is_file():
        return ["manifest: project_manifest.json yok"]
    try:
        veri = json.loads(yol.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return [f"manifest: geçersiz JSON (satır {e.lineno})"]
    hatalar = []
    if not str(veri.get("snapshot_notice", "")).strip():
        hatalar.append("manifest: snapshot_notice eksik")
    stable = veri.get("stable") or {}
    snapshot = veri.get("snapshot") or {}
    for alan in MANIFEST_STABLE:
        if alan not in stable:
            hatalar.append(f"manifest: stable.{alan} eksik")
    for alan in MANIFEST_SNAPSHOT:
        if alan not in snapshot:
            hatalar.append(f"manifest: snapshot.{alan} eksik")
    giris = stable.get("entry_point")
    if giris and not (kok / giris).is_file():
        hatalar.append(f"manifest: entry_point bulunamadı ({giris})")
    for anahtar in ("dist_exe", "installer", "installed_exe"):
        h = (snapshot.get(anahtar) or {}).get("sha256", "")
        if not re.fullmatch(r"[0-9A-F]{64}", str(h)):
            hatalar.append(f"manifest: snapshot.{anahtar}.sha256 biçimi hatalı")
    return hatalar


def kontrol_frontmatter(kok: Path) -> list[str]:
    hatalar = []
    for yol in _md_dosyalari(kok):
        ad = yol.relative_to(_rehber(kok)).as_posix()
        if ad.startswith("templates/") or ad == "decisions/README.md":
            continue                     # şablon/açıklama dosyaları muaf
        veri = frontmatter_oku(yol)
        if veri is None:
            hatalar.append(f"frontmatter: {ad} frontmatter yok")
            continue
        for alan in FRONTMATTER_ALANLARI:
            if alan not in veri:
                hatalar.append(f"frontmatter: {ad} '{alan}' alanı eksik")
        for kapsam in veri.get("covers") or []:
            if not (kok / kapsam).exists():
                if kapsam.startswith(YEREL_ONLY):
                    continue             # temiz clone'da olmayabilir
                hatalar.append(f"covers: {ad} → bulunamayan yol {kapsam}")
    return hatalar


def kontrol_baglantilar(kok: Path) -> list[str]:
    hatalar = []
    hedefler = [(p, p.parent) for p in _md_dosyalari(kok)]
    hedefler += [(kok / ad, kok) for ad in ZORUNLU_KOK if (kok / ad).is_file()]
    for yol, taban in hedefler:
        ad = yol.relative_to(kok).as_posix()
        for satir_no, satir in enumerate(
                yol.read_text(encoding="utf-8").splitlines(), 1):
            for hedef in MD_LINK.findall(satir):
                if hedef.startswith(("http://", "https://", "#", "mailto:")):
                    continue
                temiz = hedef.split("#", 1)[0].strip()
                if not temiz:
                    continue
                if not (taban / temiz).exists():
                    hatalar.append(
                        f"baglanti: {ad}:{satir_no} → {temiz} bulunamadı")
    return hatalar


def kontrol_yonlendirme(kok: Path) -> list[str]:
    """INDEX.md içindeki her göreli bağlantı var olan bir belgeye gitmeli."""
    yol = _rehber(kok) / "INDEX.md"
    if not yol.is_file():
        return ["yonlendirme: INDEX.md yok"]
    hatalar = []
    for hedef in MD_LINK.findall(yol.read_text(encoding="utf-8")):
        if hedef.startswith(("http://", "https://", "#")):
            continue
        temiz = hedef.split("#", 1)[0].strip()
        if temiz and not (yol.parent / temiz).exists():
            hatalar.append(f"yonlendirme: INDEX → {temiz} bulunamadı")
    return hatalar


def kontrol_gizli(kok: Path) -> list[str]:
    """Gerçek mutlak kullanıcı yolu ve açık gizli değer taraması.

    Bulunan değerin KENDİSİ raporlanmaz; yalnız dosya, satır ve kural adı.
    """
    hatalar = []
    dosyalar = _md_dosyalari(kok)
    dosyalar += [kok / ad for ad in ZORUNLU_KOK if (kok / ad).is_file()]
    manifest = _rehber(kok) / "project_manifest.json"
    if manifest.is_file():
        dosyalar.append(manifest)
    for yol in dosyalar:
        try:
            ad = yol.relative_to(kok).as_posix()
        except ValueError:
            ad = yol.name
        for satir_no, satir in enumerate(
                yol.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if any(y in satir for y in YER_TUTUCU):
                devam = MUTLAK_YOL.search(satir) is None
                if devam:
                    continue
            if MUTLAK_YOL.search(satir):
                hatalar.append(f"gizli: {ad}:{satir_no} mutlak kullanıcı yolu")
            dusuk = satir.lower()
            if any(i in dusuk for i in GUVENLI_ISARET):
                continue
            for kural, kalip in GIZLI_KALIPLAR:
                if kalip.search(satir):
                    hatalar.append(f"gizli: {ad}:{satir_no} kural={kural}")
    return hatalar


def _calisma_agaci_degisiklikleri(kok: Path) -> dict[str, str]:
    """Commit edilmemiş değişiklikler: yol → neden.

    Aynı dosya birden çok kaynakta görünürse TEK neden üretilir (öncelik:
    staged > unstaged > untracked).
    """
    sonuc: dict[str, str] = {}
    for args, neden in ((("diff", "--cached", "--name-only"), "staged"),
                        (("diff", "--name-only"), "çalışma ağacı"),
                        (("ls-files", "--others", "--exclude-standard"),
                         "untracked")):
        kod, cikti = _git(kok, *args)
        if kod != 0 or not cikti:
            continue
        for satir in cikti.splitlines():
            yol = satir.strip()
            if yol and yol not in sonuc:
                sonuc[yol] = neden
    return sonuc


def _kapsiyor_mu(kapsam: str, yol: str) -> bool:
    kapsam = kapsam.strip("/")
    return yol == kapsam or yol.startswith(kapsam + "/")


def kontrol_stale(kok: Path) -> list[str]:
    """`covers` kaynakları belge doğrulamasından sonra değişti mi?

    Bakılan kaynaklar: commit geçmişi (`last_verified_commit..HEAD`) **ve**
    çalışma ağacı (staged / unstaged / untracked). Böylece henüz commit
    edilmemiş kaynak değişiklikleri de yakalanır.

    Rehber altyapısı (`PROJECT_GUIDE/`, `CLAUDE.md`, `AGENTS.md`,
    `tests/test_project_guide.py`) hiçbir belgenin `covers` alanında yer
    almadığı için, rehberi oluşturan/güncelleyen commit hiçbir belgeyi
    eskitmez. Git okunamıyorsa güvenli "doğrulanamadı" uyarısı üretilir.

    Belge başına en fazla BİR satır üretilir.
    """
    kod, _ = _git(kok, "rev-parse", "--git-dir")
    if kod != 0:
        return ["stale: git geçmişi okunamadı — doğrulanamadı"]
    calisma = _calisma_agaci_degisiklikleri(kok)
    uyarilar = []
    for yol in _md_dosyalari(kok):
        ad = yol.relative_to(_rehber(kok)).as_posix()
        veri = frontmatter_oku(yol) or {}
        kapsam_tum = [str(k) for k in (veri.get("covers") or [])]
        kapsam = [k for k in kapsam_tum if (kok / k).exists()]
        # Untracked bir dosya diskte vardır; silinmiş/taşınmış kapsam ise
        # `kontrol_frontmatter` tarafından zaten hata olarak raporlanır.
        if not kapsam_tum:
            continue                      # süreç/politika belgesi
        nedenler: dict[str, str] = {}

        commit = str(veri.get("last_verified_commit", "")).strip()
        if not commit:
            uyarilar.append(f"stale: {ad} last_verified_commit boş")
            continue
        kod, _ = _git(kok, "cat-file", "-e", f"{commit}^{{commit}}")
        if kod != 0:
            uyarilar.append(f"stale: {ad} commit bulunamadı — doğrulanamadı")
            continue
        if kapsam:
            kod, cikti = _git(kok, "log", "--name-only", "--pretty=format:",
                              f"{commit}..HEAD", "--", *kapsam)
            if kod != 0:
                uyarilar.append(f"stale: {ad} karşılaştırılamadı — doğrulanamadı")
                continue
            for satir in cikti.splitlines():
                d = satir.strip()
                if d and any(_kapsiyor_mu(k, d) for k in kapsam):
                    nedenler.setdefault(d, "commit")

        for d, neden in calisma.items():
            if any(_kapsiyor_mu(k, d) for k in kapsam_tum):
                nedenler.setdefault(d, neden)

        if nedenler:
            ozet = sorted({v for v in nedenler.values()})
            uyarilar.append(
                f"stale: {ad} kapsadığı {len(nedenler)} dosya değişti "
                f"({', '.join(ozet)}) — yeniden doğrula")
    return uyarilar


def kontrol_artifacts(kok: Path, zorunlu: bool = False) -> tuple[list[str],
                                                                list[str]]:
    """Mevcut artifact'ları manifest hash'leriyle karşılaştırır.

    Döner: `(hatalar, uyarilar)`.
      * Dosya yoksa → `zorunlu=False` ise **uyarı** ("yerel doğrulama
        atlandı"), `zorunlu=True` (release) ise **hata**.
      * Dosya varsa yanlış hash/boyut her iki modda da **hata**.
      * Dosya varsa ve doğruysa hiçbir çıktı üretilmez.
    Yol ve hash değerleri çıktıya yazılmaz; yalnız artifact adı.
    """
    yol = _rehber(kok) / "project_manifest.json"
    if not yol.is_file():
        return ["artifact: project_manifest.json yok"], []
    try:
        veri = json.loads(yol.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return ["artifact: manifest okunamadı"], []
    hatalar: list[str] = []
    uyarilar: list[str] = []
    snapshot = veri.get("snapshot") or {}

    # Hedef sürüm ile artifact'ın derlendiği sürüm ayrı olabilir: sürüm
    # yükseltmesinden sonra, yeni build alınana kadar eldeki dist/installer
    # ESKİ sürüme aittir. Bu durum `--artifacts` için uyarı, `--release` için
    # hatadır; eski artifact ASLA yeni sürüm gibi kabul edilmez.
    hedef = str(snapshot.get("version", "")).strip()
    artifact_surum = str(snapshot.get("artifact_built_for_version", "")).strip()
    eski_artifact = bool(hedef and artifact_surum and hedef != artifact_surum)
    if eski_artifact:
        mesaj = (f"artifact: eldeki derleme {artifact_surum} sürümüne ait, "
                 f"hedef sürüm {hedef} — hedef sürüm için yeniden build gerekli")
        if zorunlu:
            hatalar.append(mesaj)
        else:
            uyarilar.append(mesaj)
    # `release_candidate_ready` teknik kapıların (build + frozen smoke +
    # installer) geçtiğini söyler; YAYINLANDI anlamına gelmez. Eski sözleşme
    # `release_ready` da desteklenir.
    hazir = snapshot.get("release_candidate_ready")
    if hazir is None:
        hazir = snapshot.get("release_ready")
    if zorunlu and hazir is False:
        hatalar.append("artifact: manifest release_candidate_ready=false "
                       "(hedef sürüm için doğrulama tamamlanmadı)")

    for anahtar in HASHLI_ARTIFACT:
        bilgi = snapshot.get(anahtar) or {}
        hedef = kok / str(bilgi.get("path", ""))
        if not hedef.is_file():
            mesaj = f"artifact: {anahtar} bulunamadı — yerel doğrulama atlandı"
            if zorunlu:
                hatalar.append(f"artifact: {anahtar} bulunamadı "
                               f"(release için yerel girdi zorunlu)")
            else:
                uyarilar.append(mesaj)
            continue
        if _sha256(hedef) != str(bilgi.get("sha256", "")).upper():
            hatalar.append(f"artifact: {anahtar} SHA256 manifest ile uyuşmuyor")
        boyut = bilgi.get("size")
        if isinstance(boyut, int) and hedef.stat().st_size != boyut:
            hatalar.append(f"artifact: {anahtar} boyutu manifest ile uyuşmuyor")
    return hatalar, uyarilar


# ── R12c: build sonrası provenance kapısı ────────────────────────────────────
# Artifact üretildikten SONRA değişmesine izin verilen TAM yollar (exact match;
# klasör/prefix izni YOKTUR — "docs/" veya "PROJECT_GUIDE/" yetki vermez).
IZINLI_BUILD_SONRASI = (
    "PROJECT_GUIDE/project_manifest.json",
    "PROJECT_GUIDE/CURRENT_STATUS.md",
    "PROJECT_GUIDE/KNOWN_RISKS.md",
    "docs/CHANGELOG.md",
)


def kontrol_build_sonrasi_provenance(kok: Path) -> list[str]:
    """`--release` kapısı: artifact'ın build commit'inden SONRA Git'in gördüğü
    değişiklikler yalnız `IZINLI_BUILD_SONRASI` yollarında olabilir.

    Commit edilmiş, staged, unstaged ve untracked (gitignore dışı) değişiklikler
    birlikte denetlenir; add/modify/delete/rename kapsanır. Aynı dosya için tek
    hata üretilir. Manifest veya Git okunamıyorsa **fail-closed** davranılır.

    **SINIR — gizlenmemeli.** Bu kapı YALNIZ Git'in görebildiği provenance'ı
    kanıtlar. `packaging/` ve `assets/` gibi gitignore/local-only build
    girdilerinin içerik geçmişi Git commit diff'iyle kanıtlanamaz; onlar
    `kontrol_yerel_girdiler`, artifact hash ve installer doğrulamalarıyla
    AYRI kanıt sınıfında kalır. "Bütün build girdileri kriptografik olarak
    kanıtlandı" DENEMEZ.

    **GÜVEN SINIRI.** `snapshot.built_from_commit` bu kapının GÜVENDİĞİ
    girdidir; kapı artifact ile o commit arasında kriptografik bağ kurmaz.
    Manifest'in kendisi build sonrası değişmesine izin verilen yollardandır,
    yani yanlış veya ileri bir commit yazmak kapıyı sessizce gevşetir.
    `built_from_commit`'in gerçek build logu/ölçümüyle eşleştiği **release
    incelemesinde ayrıca** doğrulanmalıdır.
    """
    on = "provenance: "
    yol = _rehber(kok) / "project_manifest.json"
    try:
        veri = json.loads(yol.read_text(encoding="utf-8"))
    except Exception:                                          # noqa: BLE001
        return [on + "manifest okunamadı — build sonrası provenance "
                     "doğrulanamadı"]

    commit = str((veri.get("snapshot") or {}).get("built_from_commit", "")).strip()
    if not commit:
        return [on + "manifest built_from_commit boş — build sonrası "
                     "provenance doğrulanamadı"]

    kod, _c = _git(kok, "rev-parse", "--verify", "--quiet", commit + "^{commit}")
    if kod != 0:
        return [on + "built_from_commit Git geçmişinde bulunamadı — build "
                     "sonrası provenance doğrulanamadı"]

    kod, _c = _git(kok, "merge-base", "--is-ancestor", commit, "HEAD")
    if kod != 0:
        return [on + "built_from_commit HEAD'in atası değil — build sonrası "
                     "provenance doğrulanamadı"]

    # Öncelik sırası: aynı dosya birden çok kaynakta görünse de TEK neden.
    kaynaklar = (
        (("diff", "--name-only", "--no-renames", f"{commit}..HEAD"), "commit"),
        (("diff", "--cached", "--name-only", "--no-renames"), "staged"),
        (("diff", "--name-only", "--no-renames"), "çalışma ağacı"),
        (("ls-files", "--others", "--exclude-standard"), "untracked"),
    )
    bulunan: dict[str, str] = {}
    for args, neden in kaynaklar:
        kod, cikti = _git(kok, "-c", "core.quotepath=false", *args)
        if kod != 0:
            return [on + f"Git çıktısı okunamadı ({neden}) — build sonrası "
                         "provenance doğrulanamadı"]
        for satir in cikti.splitlines():
            p = satir.strip().replace("\\", "/")
            if p and p not in bulunan and p not in IZINLI_BUILD_SONRASI:
                bulunan[p] = neden

    return [on + f"build sonrası izin verilmeyen değişiklik — {p} ({n})"
            for p, n in sorted(bulunan.items())]


def kontrol_yerel_girdiler(kok: Path) -> list[str]:
    """--release için: yerel paketleme girdileri mevcut olmalı."""
    hatalar = []
    for ad in ("packaging/TeklifYonetim.spec", "packaging/TeklifYonetim.iss",
               "packaging/version_info.txt", "assets"):
        if not (kok / ad).exists():
            hatalar.append(f"release: yerel girdi eksik ({ad})")
    return hatalar


CHANGELOG = "docs/CHANGELOG.md"
_CL_BASLIK = re.compile(r"^##\s*\[(?P<surum>[^\]]+)\]\s*(?:[—–-]\s*)?(?P<kalan>.*)$")
_CL_TARIH = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_CL_TASLAK = ("hazırlanıyor", "hazirlaniyor", "yayınlanmadı", "yayinlanmadi",
              "unreleased", "taslak", "tbd")


def kontrol_changelog(kok: Path, zorunlu: bool = False) -> list[str]:
    """--release kapısı: hedef sürümün CHANGELOG bölümü yayına hazır olmalı.

    Tag'in konduğu commit'in kendi içinde "yayınlanmadı" demesi kabul edilemez.
    Kural yalnız `zorunlu` (release) modunda ve `release_candidate_ready=true`
    iken uygulanır; sürüm hazırlığı sırasında taslak başlık serbesttir.
    Yalnız HEDEF sürümün bölümü incelenir — eski sürümlerin tarihsel metni
    (ör. geçmişte yazılmış "henüz yayınlanmadı" notu) sonucu etkilemez.
    """
    if not zorunlu:
        return []
    manifest = _rehber(kok) / "project_manifest.json"
    if not manifest.is_file():
        return []                       # eksikliği kontrol_manifest raporlar
    try:
        veri = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []                       # bozukluğu kontrol_manifest raporlar
    snapshot = veri.get("snapshot", {})
    if snapshot.get("release_candidate_ready") is not True:
        return []                       # release adayı değil → kapı uygulanmaz
    hedef = str((snapshot.get("release") or {}).get("target_version")
                or snapshot.get("version") or "").strip()
    if not hedef:
        return ["changelog: hedef sürüm manifestten okunamadı"]

    yol = kok / CHANGELOG
    if not yol.exists():
        return [f"changelog: {CHANGELOG} bulunamadı"]
    satirlar = yol.read_text(encoding="utf-8").splitlines()

    bas = kalan = None
    for i, satir in enumerate(satirlar):
        m = _CL_BASLIK.match(satir.strip())
        if m and m.group("surum").strip() == hedef:
            bas, kalan = i, m.group("kalan").strip()
            break
    if bas is None:
        return [f"changelog: {hedef} bölümü yok — yayın öncesi eklenmeli"]

    hatalar = []
    if not _CL_TARIH.match(kalan):
        hatalar.append(
            f"changelog: {hedef} başlığı '## [{hedef}] — YYYY-MM-DD' biçiminde "
            f"değil (bulunan: {kalan!r})")

    son = bas + 1
    while son < len(satirlar) and not _CL_BASLIK.match(satirlar[son].strip()):
        son += 1
    govde = "\n".join(satirlar[bas:son]).lower()
    for isaret in _CL_TASLAK:
        if isaret in govde:
            hatalar.append(
                f"changelog: {hedef} bölümünde taslak işareti var ({isaret!r}) — "
                f"yayınlanan commit kendi içinde 'yayınlanmadı' diyemez")
            break
    return hatalar


# ── Sürücü ──────────────────────────────────────────────────────────────────

def calistir(kok: Path, artifacts: bool = False, release: bool = False,
             stale: bool = False) -> tuple[list[str], list[str]]:
    """(hatalar, uyarilar) döndürür."""
    hatalar: list[str] = []
    uyarilar: list[str] = []

    hatalar += kontrol_yapi(kok)
    hatalar += kontrol_manifest(kok)
    hatalar += kontrol_frontmatter(kok)
    hatalar += kontrol_baglantilar(kok)
    hatalar += kontrol_yonlendirme(kok)
    hatalar += kontrol_gizli(kok)

    if stale or release:
        eski = kontrol_stale(kok)
        (hatalar if release else uyarilar).extend(eski)

    if artifacts or release:
        a_hata, a_uyari = kontrol_artifacts(kok, zorunlu=release)
        hatalar += a_hata
        uyarilar += a_uyari

    if release:
        hatalar += kontrol_yerel_girdiler(kok)
        hatalar += kontrol_changelog(kok, zorunlu=True)
        # R12c — yalnız release modunda zorunlu.
        hatalar += kontrol_build_sonrasi_provenance(kok)

    return hatalar, uyarilar


def main(argv=None) -> int:
    ayristirici = argparse.ArgumentParser(description="PROJECT_GUIDE denetimi")
    ayristirici.add_argument("--stale", action="store_true")
    ayristirici.add_argument("--artifacts", action="store_true")
    ayristirici.add_argument("--release", action="store_true")
    ayristirici.add_argument("--root", default=None)
    a = ayristirici.parse_args(argv)

    kok = Path(a.root).resolve() if a.root else proje_kokunu_bul()
    hatalar, uyarilar = calistir(kok, artifacts=a.artifacts,
                                 release=a.release, stale=a.stale)

    mod = "release" if a.release else ("stale" if a.stale else
                                       ("artifacts" if a.artifacts else "normal"))
    print(f"PROJECT_GUIDE denetimi — mod={mod} kök={kok.name}")
    for u in uyarilar:
        print("  UYARI  ", u)
    for h in hatalar:
        print("  HATA   ", h)
    if not hatalar:
        print(f"  SONUC   temiz ({len(uyarilar)} uyarı)")
        return 0
    print(f"  SONUC   {len(hatalar)} hata")
    return 1


if __name__ == "__main__":
    sys.exit(main())
