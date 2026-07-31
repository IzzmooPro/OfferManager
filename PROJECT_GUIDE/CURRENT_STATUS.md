---
purpose: Projenin son doğrulanmış durumu — tarihli yakalama. Tarihçe için AUDIT_HISTORY.
read_when: Genel yönelim, build/release öncesi, uzun aradan sonra.
covers:
  - core/constants.py
last_verified_commit: 7395561
last_verified_date: 2026-07-31
volatile: true
---

# Son doğrulanmış durum

> **Yakalama tarihi: 2026-07-31 · hedef sürüm: `v4.1`.**
> Bu belge canlı durum iddiasında bulunmaz. **Canlı git durumu snapshot'tan okunmaz; `git status`, `git rev-parse HEAD` ve upstream karşılaştırmasıyla yeniden ölçülür.** Makine-okunur karşılığı: [project_manifest.json](project_manifest.json).

## Sürüm ve kaynak

- Sürüm: **v4.1** — tek kaynak `core/constants.py:APP_VERSION`; Inno `.iss` ve `version_info.txt` eşitlendi
- Commit ayrımı: v4.1 **sürüm hazırlığı** `a63f981` · **U17 dâhil güncel işlevsel kaynak** `7395561` · **eldeki artifact'ın build edildiği HEAD** `d359137` (7395561'i içerir → artifact güncel)
- Kaynak davranışı baseline sonucu (PROJECT_GUIDE testleri hariç): **648 passed, 29 subtests** (`060baf3`)
- PROJECT_GUIDE, sürüm tutarlılık ve U17 updater güven zinciri testleri dâhil son tam suite: **798 passed, 1 skipped, 98 subtests** (2026-07-31, temiz ağaç). Tek skip, artifact stale olmadığı için stale-senaryosu testinin uygulanmamasıdır; `verify_project_guide.py --release` temiz ağaçta **exit 0** verir.
- `py_compile` tüm proje dosyalarında temiz
- v4.1 kaynak commit'lerinin upstream durumu **release öncesinde canlı git komutlarıyla doğrulanmalıdır**; bu belgede canlı remote hash tutulmaz

## Denetim

K1–K6 ve O1–O16 **kapalı** ([AUDIT_HISTORY.md](AUDIT_HISTORY.md)). O4 yanlış pozitif olarak kapandı; O5'in özgün yarış iddiası yanlış pozitifti, komşu kusurlar düzeltildi; O10 ve O11 "olası ölçekleme bulgusu, düzeltildi" sınıfındadır.

## v4.1 doğrulama durumu

Üç kanıt sınıfı da **U17'li kaynakla (`7395561`, build HEAD `d359137`) yeniden** yürütüldü.

- **Temiz build: GEÇTİ** — `packaging/Kurulum-Yap.bat --no-pause` exit 0; PyInstaller onedir + Inno Setup; log'da `[HATA]`/traceback yok
- **Frozen smoke (kanıt sınıfı B): GEÇTİ** — izole ortamda U17'li dist EXE ile: null keyring'de **gözetimsiz açılış, modal yok**; fail keyring'de **"Güvenli Depo" modalı gerçekten açılıyor** (ana pencere arkasında disabled, mesaj kısa ve güvenli, `Tamam` otomasyonla basıldı); manuel güncelleme ağ-hata yolu **"Güncelleme kontrol edilemedi."** — URL/proxy/traceback sızıntısı ve yanlış "uygulama güncel" mesajı yok; indirme/tarayıcı/installer başlatılmadı; tek örnek kilidi; normal kapanış exit 0, tek izole yedek, thread/native crash izi yok
- **Installer (kanıt sınıfı C): GEÇTİ** — U17 öncesi v4.1 → U17'li v4.1 **yerinde upgrade** (exit 0), kurulu EXE hedef hash ile eşleşti, AppId ve kurulum dizini korundu; kurulu uygulama izole smoke exit 0; **uninstall** (exit 0) ve aynı installer ile **temiz reinstall** (exit 0) bu turda **yapıldı**; ikinci kurulu smoke exit 0; **kullanıcı verisi ve yedekleri byte-birebir korundu**; final durum: **U17'li v4.1 kurulu**
- Installer turunda **üç UAC onayı kullanıcı tarafından elle verildi** (UAC güvenli masaüstü otomatikleştirilemez); UAC dışındaki tüm uygulama tıklamaları otomasyonla yapıldı. Credential Manager get/set/delete = **0**
- **Kod imzası yok** → SmartScreen "bilinmeyen yayımcı" uyarısı beklenir
- Artifact hash/boyutları: [project_manifest.json](project_manifest.json)

`release_candidate_ready = true`: teknik kapılar U17'li kaynakla geçti. **Bu "yayınlandı" demek değildir** — tag, GitHub Release ve updater uçtan uca read-back yapılmadı.

## Bilinen sınır

`packaging/`, `assets/`, `dist/`, `installer_output/`, `build/`, `Import_Test/` depo dışıdır → **temiz clone'dan build tekrarlanabilir değildir** ([BUILD_AND_PACKAGING.md](BUILD_AND_PACKAGING.md)).

v4.0 artifact ve kurulum kopyaları `<ROLLBACK_ROOT>` altında **release tamamlanana kadar korunuyor**; temizlik ayrı ve açık onayla yapılacak.

## Tamamlananlar (bu yakalama itibarıyla)

v4.1 kaynak hazırlığı · legacy bilgi aktarımı ve temizliği · boş bağlamlı devir testi · **U17 updater güven zinciri** (asset adı + URL/host allowlist + SHA-256/size, fail-closed) · U17'li temiz build · izole frozen smoke · gerçek yerinde upgrade + uninstall + temiz reinstall · artifact kanıtlarının manifeste işlenmesi.

## Kalan aşamalar

1. Canlı release ön kontrolü — [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md) 1. adım (canlı `git fetch` + `rev-parse` + `rev-list`)
2. Metadata commit ve push
3. v4.1 tag + GitHub Release (asset adı **tam olarak** `TeklifYonetim_Setup_v4.1.exe`, tek `.exe`)
4. Canlı updater uçtan uca read-back
5. `updater_end_to_end_verified` metadata güncellemesi
6. Rollback/baseline klasörlerinin (`<ROLLBACK_ROOT>`) açık onayla temizliği

## Bu yakalamayı yenilerken

1. `git rev-parse --short HEAD` ve upstream farkını ölç.
2. `python -m pytest tests -q` sayılarını güncelle (kaynak ve rehber dâhil ayrımını koru).
3. `python PROJECT_GUIDE/scripts/verify_project_guide.py --artifacts` ile hash'leri doğrula.
4. `last_verified_commit` / `last_verified_date` alanlarını ve `project_manifest.json` `snapshot` bölümünü güncelle.
