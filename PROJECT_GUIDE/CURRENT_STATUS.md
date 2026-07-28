---
purpose: Projenin son doğrulanmış durumu — tarihli yakalama. Tarihçe için AUDIT_HISTORY.
read_when: Genel yönelim, build/release öncesi, uzun aradan sonra.
covers:
  - core/constants.py
last_verified_commit: 060baf3
last_verified_date: 2026-07-28
volatile: true
---

# Son doğrulanmış durum

> **Yakalama tarihi: 2026-07-28 · temel commit: `060baf3`.**
> Bu belge canlı durum iddiasında bulunmaz. **Canlı git durumu snapshot'tan okunmaz; `git status`, `git rev-parse HEAD` ve upstream karşılaştırmasıyla yeniden ölçülür.** Makine-okunur karşılığı: [project_manifest.json](project_manifest.json).

## Kaynak

- Sürüm: **v4.0** — tek kaynak `core/constants.py:APP_VERSION`
- Temel commit (`source_baseline_commit`): **060baf3**
- Kaynak davranışı baseline sonucu (PROJECT_GUIDE testleri hariç): **648 passed, 29 subtests**
- PROJECT_GUIDE testleri dâhil son tam suite: **689 passed, 29 subtests** (~3 dk 33 sn)
- `py_compile` tüm proje dosyalarında temiz

## Denetim

K1–K6 ve O1–O16 **kapalı** ([AUDIT_HISTORY.md](AUDIT_HISTORY.md)). O4 yanlış pozitif olarak kapandı; O5'in özgün yarış iddiası yanlış pozitifti, komşu kusurlar düzeltildi; O10 ve O11 "olası ölçekleme bulgusu, düzeltildi" sınıfındadır.

## Paketli sürüm

- Build: `packaging/Kurulum-Yap.bat --no-pause` → exit 0 (testler + PyInstaller + Inno)
- Yerel makinede kurulu sürüm, aynı yakalamadaki dist derlemesiyle **aynı hash'e** sahipti; güncel değerler [project_manifest.json](project_manifest.json) `snapshot` bölümünde
- **Kod imzası yok** → SmartScreen uyarısı beklenir
- **Frozen smoke (kanıt sınıfı B): GEÇTİ** — başlangıç, tek örnek kilidi, normal kapanış, uzun worker ile kapanış, restart + mutex beklemesi, credential hata yolu, bozuk DB ile hata penceresi, manuel içe aktarma akışı
- **Installer (kanıt sınıfı C): GEÇTİ** — yerinde upgrade, uygulama smoke, kaldırma, temiz yeniden kurulum; kaldırmada kullanıcı verisi bit-bit korundu

## Yayın

- Uzaktaki son tag **v4.0** daha eski bir commit'i gösteriyordu; `060baf3` için tag/release **oluşturulmadı**
- **Açık karar:** yeni sürüm numarası mı verilecek (ör. v4.1) yoksa v4.0 mı yeniden yayınlanacak; kod imzalama yapılacak mı
- Yayın adımları: [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md)

## Bilinen sınır

`packaging/`, `assets/`, `dist/`, `installer_output/`, `build/`, `Import_Test/` depo dışıdır → **temiz clone'dan build tekrarlanabilir değildir** ([BUILD_AND_PACKAGING.md](BUILD_AND_PACKAGING.md)).

## Bu yakalamayı yenilerken

1. `git rev-parse --short HEAD` ve upstream farkını ölç.
2. `python -m pytest tests -q` sayılarını güncelle (kaynak ve rehber dâhil ayrımını koru).
3. `python PROJECT_GUIDE/scripts/verify_project_guide.py --artifacts` ile hash'leri doğrula.
4. `last_verified_commit` / `last_verified_date` alanlarını ve `project_manifest.json` `snapshot` bölümünü güncelle.
