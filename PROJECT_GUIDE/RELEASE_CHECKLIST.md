---
purpose: Yayın öncesi zorunlu sıra ve GitHub yayın akışı.
read_when: Release hazırlığı ve yayın anı.
covers:
  - core/constants.py
  - packaging/TeklifYonetim.iss
  - packaging/version_info.txt
  - packaging/Kurulum-Yap.bat
  - ui/utils/updater.py
last_verified_commit: 2fbb931
last_verified_date: 2026-08-27
volatile: false
---

# Yayın kontrol listesi

Sıra atlanmaz. Her adım kanıtla kapatılır; kanıt sınıfları [VERIFICATION_GUIDE.md](VERIFICATION_GUIDE.md).

## 1. Kaynak hazır

Upstream durumu hiçbir belgede sabit tutulmaz; **her release öncesi canlı ölçülür**:

- [ ] `git fetch origin` çalıştırıldı
- [ ] `git rev-parse HEAD` ve `git rev-parse origin/main` karşılaştırıldı
- [ ] `git rev-list --left-right --count origin/main...HEAD` ile ahead/behind ölçüldü (yayın için **0 geride** olmalı)
- [ ] `git status --short --untracked-files=all` boş (çalışma ağacı temiz)
- [ ] `python -m pytest tests -q` yeşil
- [ ] `py_compile` tüm proje dosyalarında temiz
- [ ] Açık riskler gözden geçirildi ([KNOWN_RISKS.md](KNOWN_RISKS.md))

## 2. Sürüm eşleşmesi

- [ ] `core/constants.py:APP_VERSION` hedef sürüm
- [ ] `.iss` `MyAppVersion` aynı; `VersionInfoVersion` / `VersionInfoProductVersion` sayısal karşılığı
- [ ] `packaging/version_info.txt` `filevers`/`prodvers`/`ProductVersion` aynı
- [ ] Installer dosya adı `TeklifYonetim_Setup_<sürüm>.exe`
- [ ] Yayınlanacak tag `vX.Y` aynı sürümü gösteriyor

## 3. Temiz build

- [ ] **Build BAŞLAMADAN hemen önce** gerçek `git rev-parse HEAD` çalıştırılıp değeri kaydedildi (build logunun yanında tutulur)
- [ ] `packaging/Kurulum-Yap.bat --no-pause` → exit 0 (testler + PyInstaller + Inno)
- [ ] Yeni EXE/installer SHA256'ları eskisinden farklı
- [ ] `dist/TeklifYonetim` içinde `dist` dışı artık dosya yok
- [ ] Pakette gerçek kullanıcı verisi (DB, log, yedek, PDF), `tests/`, `Import_Test/`, `.git` yok
- [ ] `project_manifest.json` snapshot alanları güncellendi
- [ ] **`built_from_commit` alanına, build öncesinde kaydedilen O gerçek HEAD yazıldı** — sonradan hatırlanan veya tahmin edilen bir değer değil
- [ ] **`built_from_commit`, gerçek build logu/ölçümüyle ELLE karşılaştırıldı.** Manifest alanına körlemesine güvenilmez: `--release` provenance kapısı bu alanı **girdi olarak kabul eder**, doğruluğunu kanıtlamaz
- [ ] Artifact ile commit arasında **kriptografik bağ olmadığı** kabul edildi; bağ yalnız bu elle karşılaştırmayla kurulur (kod imzası kararından **ayrı** bir konudur — [Açık kararlar](#açık-kararlar))

### Build sonrası provenance kapısı (R12c)

- [ ] Build'den sonra **yalnız** şu **tam** yollar değişti (exact match; klasör/prefix izni yok):
      `PROJECT_GUIDE/project_manifest.json` · `PROJECT_GUIDE/CURRENT_STATUS.md` · `PROJECT_GUIDE/KNOWN_RISKS.md` · `PROJECT_GUIDE/VERIFICATION_GUIDE.md` · `docs/CHANGELOG.md`
- [ ] Kaynak kodu, `tests/` veya başka bir rehber belgesi değiştiyse **yeni build alındı** (eski artifact yeni kaynağın kanıtı sayılmaz)
- [ ] `python PROJECT_GUIDE/scripts/verify_project_guide.py --release` → **exit 0**; provenance açısından da temiz. **Bu geçmeden tag ve release YAPILMAZ.**
- [ ] Local-only `packaging/` ve `assets/` girdileri **ayrıca** hash/envanter/build incelemesiyle doğrulandı — provenance kapısı bunların geçmişini kanıtlamaz ([CHANGE_PROTOCOL.md](CHANGE_PROTOCOL.md))

> **2026-08-27 v4.4 installer düzeltmesi çalışma ağacındayken `--release` için `exit 1` BEKLENİR.** Exact v4.4 temiz build ve değişiklik-etkili B geçti; ilk C upgrade denemesi kurulum ağacında 40 eski runtime DLL'i bıraktığı için kırmızı durduruldu. Dar `[InstallDelete]` düzeltmesi ve regresyon testi mevcut artifact'tan sonra değişti; yeni temiz build, B ve tam C tamamlanmadan `release_candidate_ready` true yapılmaz, tag/Release oluşturulmaz.

## 4. Paketli doğrulama (kanıt sınıfı B)

- [ ] İzole frozen smoke geçti ([VERIFICATION_GUIDE.md](VERIFICATION_GUIDE.md))

## 5. Installer doğrulaması (kanıt sınıfı C)

- [ ] Rollback yedeği alındı ve doğrulandı
- [ ] Upgrade → uygulama smoke → kaldırma → temiz yeniden kurulum geçti
- [ ] Kaldırmada kullanıcı verisi korundu

## 6. Yayın

- [ ] Commit (yalnız açık istek üzerine)
- [ ] Push → `origin/main` ile senkron doğrulandı
- [ ] Tag `vX.Y` oluşturuldu ve push edildi
- [ ] GitHub Release oluşturuldu; asset **tam olarak `TeklifYonetim_Setup_vX.Y.exe`** adıyla yüklendi (updater yalnız bu adı kabul eder)
- [ ] `gh release view --json assets` ile asset'in `size` ve `digest` (`sha256:<64 hex>`) alanlarının dolu olduğu doğrulandı — biri eksikse updater fail-closed davranır ve otomatik güncelleme çalışmaz
- [ ] Yayın sonrası read-back: tag, release ve indirilebilir asset doğrulandı
- [ ] Eski sürümden **canlı güncelleme denemesi** ([VERIFICATION_GUIDE.md](VERIFICATION_GUIDE.md) — updater uçtan uca)
- [ ] `docs/CHANGELOG.md` sürüm başlığı yayın tarihiyle güncellendi
- [ ] Rollback klasörleri (`<ROLLBACK_ROOT>`) açık onayla temizlendi

### GitHub release işlemleri (`gh`)

> Aşağıdakiler **örnektir**. Çalıştırmadan önce sürüm, dosya adı ve depo hedefi
> yeniden doğrulanır; komut körlemesine kopyalanmaz.

**Ön kontrol** — mevcut tag/release var mı:

```bash
gh release list -R <OWNER>/<REPO>
```

**Yeni release** (tag yoksa `gh` tag'i de oluşturur):

```bash
gh release create vX.Y "installer_output/TeklifYonetim_Setup_vX.Y.exe" -R <OWNER>/<REPO> --title "Teklif Yönetim Sistemi vX.Y" --notes "<CHANGELOG özeti>"
```

**Mevcut release'e asset yükleme / değiştirme:**

```bash
gh release upload vX.Y "installer_output/TeklifYonetim_Setup_vX.Y.exe" --clobber -R <OWNER>/<REPO>
```

- Release başlığı biçimi: **`Teklif Yönetim Sistemi vX.Y`**
- Asset adı **tam olarak `TeklifYonetim_Setup_vX.Y.exe`** olmalı. Updater yalnız bu ada birebir uyan **tek** asset'i indirir; başka `.exe`'ler seçilmez, aynı ad iki kez varsa güncelleme sunulmaz (fail-closed). Büyük/küçük harf farkı kabul edilmez.
- Updater indirmeden önce API `size` ve `digest` alanlarını, indirme sonrası gerçek bayt sayısı + SHA-256 değerini doğrular. Bu alanlar release'te eksikse **otomatik güncelleme hiç başlamaz**.
- **Mevcut bir tag veya release üzerine yazmak** (`--clobber`, tag taşıma, release silme) **açık kullanıcı izni gerektirir**; yayınlanmış tag varsayılan olarak değiştirilmez.
- **Read-back zorunlu:** `gh release view vX.Y -R <OWNER>/<REPO>` ile tag'in doğru commit'i gösterdiği, release'in yayında olduğu ve asset'in indirilebilir olduğu doğrulanır; indirilen dosyanın SHA256'sı [project_manifest.json](project_manifest.json) ile karşılaştırılır.

## Temiz dağıtım kopyası (isteğe bağlı)

Sıfır veriyle bir kurulum dağıtılacaksa `scripts/clear_for_distribution.py` kullanılır — **gerçek veriyi siler, açık izin ve ön yedek ister, rutin release adımı değildir**. Koşullar: [CHANGE_PROTOCOL.md](CHANGE_PROTOCOL.md#dağıtım-öncesi-veri-temizliği-tehlikeli-araç).

## Depo gerçeği

GitHub'da yalnız kaynak kod, `tests/`, `README.md`, `docs/CHANGELOG.md`, `requirements.txt`, `.gitignore`, `CLAUDE.md`, `AGENTS.md` ve `PROJECT_GUIDE/` bulunur. `packaging/`, `assets/`, `dist/`, `installer_output/`, `build/`, `Import_Test/` ve `.bat` başlatıcılar yereldir; bu yüzden **release yalnız bu makinede üretilebilir** ([BUILD_AND_PACKAGING.md](BUILD_AND_PACKAGING.md)).

## Sürüm yükseltmesinin üç durumu

| Durum | Manifest | `--artifacts` | `--release` |
|---|---|---|---|
| **Ara durum** — sürüm alanları yükseltildi, yeni build yok | `artifact_built_for_version` = eski sürüm, `artifact_verification_status = stale_for_target_version`, `release_candidate_ready = false` | exit 0 + "eldeki derleme … hedef sürüm …" uyarısı | **exit 1** (beklenen) |
| **Aday** — build + frozen smoke + installer geçti | `artifact_built_for_version` = hedef sürüm, `artifact_verification_status = verified`, `release_candidate_ready = true` | exit 0, uyarı yok | exit 0 |
| **Yayınlandı** | `tag_created`, `github_release_created`, `updater_end_to_end_verified` = true | exit 0 | exit 0 |

Eski artifact'ların hash'leri yeni sürüm gibi **etiketlenmez**; tarihsel bilgi yalnız `upgrade_baseline` alanında tutulur.

> **`release_candidate_ready = true` yayınlandı demek değildir.** Yalnız 1–5. adımların geçtiğini söyler; 6. adım ayrıdır.

## Açık kararlar

- Kod imzası yok → SmartScreen uyarısı sürer.
- Mevcut hedef sürüm ve kalan adımlar: [CURRENT_STATUS.md](CURRENT_STATUS.md).
- Yayınlanmış bir tag (ör. `v4.0`) **değiştirilmez ve yeniden kullanılmaz**.
