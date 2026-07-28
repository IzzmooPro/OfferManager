---
purpose: Değişiklik akışı, riskle orantılı doğrulama matrisi ve dokümantasyon/temizlik kuralları.
read_when: Her uygulama görevinde ve incelemede.
covers: []
last_verified_commit: 060baf3
last_verified_date: 2026-07-28
volatile: false
---

# Değişiklik protokolü

## Zorunlu akış

```
bulgu → salt-okunur doğrulama → kırmızı regresyon testi → minimum düzeltme
→ hedefli test → ilgili regresyon grubu → (gerekiyorsa) tam suite
→ commit → (gerekiyorsa) temiz build → frozen smoke → installer smoke
→ push / tag / release
```

- Salt-okunur turda **dosya değiştirilmez**; ölçüm ve sınıflandırma yapılır (KESİN / OLASI / YANLIŞ POZİTİF).
- Düzeltme **minimum ve genel** olur; tek örneğe/dosyaya özel hile eklenmez.
- Bir adım kırmızıysa sonraki adıma geçilmez; durulur ve raporlanır.
- Commit, push, build, tag ve release **ayrı ayrı** izin gerektirir.

## Riskle orantılı doğrulama matrisi

| Değişiklik türü | Zorunlu | Gerekli değil |
|---|---|---|
| Belge / rehber | `tests/test_project_guide.py` + verify normal | Tam suite, build |
| Saf yardımcı fonksiyon, biçimleme | Hedefli test + ilgili dosya `py_compile` | Build, smoke |
| Servis / DB / migration | Hedefli test + tam suite | Frozen smoke (davranış UI'da değişmiyorsa) |
| UI davranışı (diyalog, modal, sayfa) | Hedefli test + tam suite + **frozen smoke** | Installer smoke |
| Kapanış / thread / restart | Tam suite + **frozen smoke** (kapanış senaryoları) | Installer smoke |
| Paketleme (`.spec`, `.iss`, build script) | Temiz build + frozen smoke + **installer smoke** | — |
| Sürüm / yayın | [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md) tamamı | — |

Küçük bir değişiklikte bütün uzun smoke turlarını tekrarlama; tablodaki en yüksek satır neyse onu uygula.

## Rehber bakımı

`python PROJECT_GUIDE/scripts/verify_project_guide.py [mod]`

| Mod | Kontrol |
|---|---|
| (normal) | Zorunlu dosyalar, `project_manifest.json` şeması, frontmatter, `covers` yollarının varlığı, Markdown iç bağlantıları, INDEX yönlendirme hedefleri, gizli veri / mutlak kullanıcı yolu taraması, snapshot hash biçimleri |
| `--stale` | `covers` altındaki kaynakların `last_verified_commit`'ten sonra değişip değişmediği |
| `--artifacts` | Mevcut artifact'ların SHA256'sı manifest ile uyuşuyor mu (yoksa atlanır) |
| `--release` | Yukarıdakilerin tamamı **zorunlu**; eksik yerel girdi veya eskimiş belge varsa sıfırdan farklı çıkış |

**Stale kuralı:** bir belge, `covers` içindeki kaynak/test/build dosyaları **commit geçmişinde** (`last_verified_commit..HEAD`) **veya çalışma ağacında** (staged / unstaged / untracked) değiştiyse eskimiş sayılır. Belge başına en fazla bir satır üretilir; aynı dosya birden çok kaynakta görünürse tek neden yazılır.

**Rehber altyapısı stale üretmez.** `PROJECT_GUIDE/`, `CLAUDE.md`, `AGENTS.md` ve `tests/test_project_guide.py` **hiçbir belgenin `covers` alanında yer almaz** (bu belge dâhil, `covers: []`). Doğruluklarını yapı, bağlantı ve `tests/test_project_guide.py` kontrolleri üstlenir. Böylece rehberi oluşturan veya güncelleyen bir commit hiçbir kaynak belgesini anlamsızca eskitmez.

`covers` boşsa belge süreç/politika belgesidir ve stale hesabına girmez. Git okunamıyorsa güvenli "doğrulanamadı" uyarısı üretilir, hata verilmez.

**Artifact kuralı:** `--artifacts` modunda artifact dosyası yoksa çıkış 0 kalır ve "yerel doğrulama atlandı" uyarısı yazılır; `--release` modunda aynı eksiklik hatadır. Artifact varsa yanlış hash/boyut her iki modda da hatadır.

## Dokümantasyon kuralları

- Aynı bilgi **tek kanonik belgede** durur; diğerleri göreli bağlantı verir.
- Uzun komut çıktısı, çalışma günlüğü veya sohbet kopyası eklenmez; karar + kanıt özeti yazılır.
- Snapshot ile tarihçe ayrılır: [CURRENT_STATUS.md](CURRENT_STATUS.md) bugünü, [AUDIT_HISTORY.md](AUDIT_HISTORY.md) geçmişi tutar.
- Emin olunmayan bilgi kesin gerçek gibi yazılmaz; kanıt sınıfı belirtilir.
- Belge değişince `last_verified_commit` / `last_verified_date` güncellenir.

## Temizlik politikası

- **Generated ve yeniden üretilebilir:** `__pycache__/`, `.pytest_cache/`, `build/` — istenirse silinebilir; `dist/` ve `installer_output/` **geçerli release adayıysa silinmez**.
- **Local-only build girdisi:** `packaging/`, `assets/`, `.bat` başlatıcılar — **silinmez**.
- **Gerçek kullanıcı verisi:** `Import_Test/` ve `<USER_DATA_ROOT>` / `<BACKUP_ROOT>` — yalnız açık izinle ve yedekle.
- **Legacy belge:** `docs/` altındaki eski yol haritaları, `GITHUB_IS_AKISI_LOCAL.md`, `SORUN_COZUM_NOTLARI.md` — **karşılaştırmalı onay** turu olmadan silinmez/taşınmaz.
- **Bilinmeyen** → dokunulmaz. **Git tarafından izlenen** → yalnız normal değişiklik akışıyla.
- Silmeden önce kapsam listelenir, sonrasında doğrulanır; geniş glob veya çözülmemiş değişkenle recursive silme yapılmaz.

## Dağıtım öncesi veri temizliği (tehlikeli araç)

`python scripts/clear_for_distribution.py --yes`

**Gerçek kullanıcı verisini siler.** Koddan doğrulanan sözleşme: müşteri, ürün, teklif, teklif kalemleri, teklif sayacı ve kategoriler silinir; **şirket ayarları, logo, imzalar ve tema korunur**; silmeden **önce otomatik ZIP yedeği** alınır (`create_backup`).

Kurallar:

- Yalnız **açık kullanıcı izniyle** çalıştırılır. `--yes` onay sorusunu atlar; izin yoksa kullanılmaz.
- Çalıştırmadan önce **ayrı bir veri yedeği** alınır (aracın kendi yedeği tek güvence sayılmaz).
- **Dry-run seçeneği yoktur.** Ön envanter elle yapılır: DB salt-okunur açılıp müşteri/ürün/teklif sayıları ve yedek klasörü kaydedilir; işlem sonrası aynı sayımlar karşılaştırılır.
- **Rutin bir release adımı değildir.** Sırf sürüm alınıyor diye çalıştırılmaz; yalnız temiz bir dağıtım kopyası hazırlanırken gerekir ([RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md)).
- Geliştirme makinesindeki gerçek veride kullanılacaksa kapsam, yedek yolu ve geri dönüş planı önceden yazılır.
