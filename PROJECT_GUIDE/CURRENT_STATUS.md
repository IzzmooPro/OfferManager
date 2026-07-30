---
purpose: Projenin son doğrulanmış durumu — tarihli yakalama. Tarihçe için AUDIT_HISTORY.
read_when: Genel yönelim, build/release öncesi, uzun aradan sonra.
covers:
  - core/constants.py
last_verified_commit: a63f981
last_verified_date: 2026-07-28
volatile: true
---

# Son doğrulanmış durum

> **Yakalama tarihi: 2026-07-28 · hedef sürüm: `v4.1`.**
> Bu belge canlı durum iddiasında bulunmaz. **Canlı git durumu snapshot'tan okunmaz; `git status`, `git rev-parse HEAD` ve upstream karşılaştırmasıyla yeniden ölçülür.** Makine-okunur karşılığı: [project_manifest.json](project_manifest.json).

## Sürüm ve kaynak

- Sürüm: **v4.1** — tek kaynak `core/constants.py:APP_VERSION`; Inno `.iss` ve `version_info.txt` eşitlendi
- İşlevsel sürüm değişikliği commit'i: **`a63f981`** · v4.1 build'inin alındığı commit: **`de64a75`**
- Kaynak davranışı baseline sonucu (PROJECT_GUIDE testleri hariç): **648 passed, 29 subtests** (`060baf3`)
- PROJECT_GUIDE ve sürüm tutarlılık testleri dâhil son tam suite: **746 passed, 29 subtests**
- `py_compile` tüm proje dosyalarında temiz
- v4.1 kaynak commit'lerinin upstream durumu **release öncesinde canlı git komutlarıyla doğrulanmalıdır**; bu belgede canlı remote hash tutulmaz

## Denetim

K1–K6 ve O1–O16 **kapalı** ([AUDIT_HISTORY.md](AUDIT_HISTORY.md)). O4 yanlış pozitif olarak kapandı; O5'in özgün yarış iddiası yanlış pozitifti, komşu kusurlar düzeltildi; O10 ve O11 "olası ölçekleme bulgusu, düzeltildi" sınıfındadır.

## v4.1 doğrulama durumu

- **Temiz build: GEÇTİ** — `packaging/Kurulum-Yap.bat --no-pause` exit 0 (build anında 713 test + PyInstaller + Inno). Suite o tarihten sonra rehber/sürüm testleriyle büyüdü; güncel sayı yukarıdaki "Sürüm ve kaynak" bölümündedir.
- **Frozen smoke (kanıt sınıfı B): GEÇTİ** — UI sürüm göstergesi, başlangıç/asset, tek örnek kilidi, teklif + PDF, O16 sayfa seçimi ve iptal, bozuk DB hata penceresi, normal kapanış
- **Installer (kanıt sınıfı C): GEÇTİ** — gerçek **v4.0 → v4.1 yerinde upgrade**; aynı AppId ve kurulum dizini; **kullanıcı verisi byte-birebir korundu**; kurulu sürüm **v4.1**
- Bu turda **uninstall/reinstall tekrarlanmadı** (v4.0 doğrulamasında geçmişti)
- **Kod imzası yok** → SmartScreen uyarısı beklenir
- Artifact hash/boyutları: [project_manifest.json](project_manifest.json)

`release_candidate_ready = true`: teknik kapılar geçti. **Bu "yayınlandı" demek değildir** — tag, GitHub Release ve updater read-back yapılmadı.

## Bilinen sınır

`packaging/`, `assets/`, `dist/`, `installer_output/`, `build/`, `Import_Test/` depo dışıdır → **temiz clone'dan build tekrarlanabilir değildir** ([BUILD_AND_PACKAGING.md](BUILD_AND_PACKAGING.md)).

v4.0 artifact ve kurulum kopyaları `<ROLLBACK_ROOT>` altında **release tamamlanana kadar korunuyor**; temizlik ayrı ve açık onayla yapılacak.

## Tamamlananlar (bu yakalama itibarıyla)

v4.1 kaynak hazırlığı · temiz build · frozen smoke · gerçek in-place upgrade · artifact kanıtlarının manifeste işlenmesi · legacy bilgi aktarımı ve temizliği · boş bağlamlı devir testi.

## Kalan aşamalar

1. [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md) son geçiş (1. adım: canlı upstream ölçümü)
2. v4.1 tag + GitHub Release
3. Updater uçtan uca read-back → `updater_end_to_end_verified`
4. Rollback klasörlerinin (`<ROLLBACK_ROOT>`) açık onayla temizliği

## Bu yakalamayı yenilerken

1. `git rev-parse --short HEAD` ve upstream farkını ölç.
2. `python -m pytest tests -q` sayılarını güncelle (kaynak ve rehber dâhil ayrımını koru).
3. `python PROJECT_GUIDE/scripts/verify_project_guide.py --artifacts` ile hash'leri doğrula.
4. `last_verified_commit` / `last_verified_date` alanlarını ve `project_manifest.json` `snapshot` bölümünü güncelle.
