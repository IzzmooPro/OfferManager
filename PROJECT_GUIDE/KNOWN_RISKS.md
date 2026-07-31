---
purpose: Doğrulanmış açık riskler ve sonraki adımları — snapshot.
read_when: Denetim, release kararı, risk analizi.
covers: []
last_verified_commit: 7395561
last_verified_date: 2026-07-31
volatile: true
---

# Bilinen riskler (snapshot — 2026-07-31)

Kapanmış bulgular burada değil, [AUDIT_HISTORY.md](AUDIT_HISTORY.md) içindedir.

| # | Risk | Şiddet | Sonraki adım |
|---|---|---|---|
| R1 | **Kod imzası yok** — SmartScreen "bilinmeyen yayımcı" uyarısı sürüyor | Orta | İmzalama sertifikası kararı; alınmazsa kullanıcıya beklenen uyarı anlatılır |
| R2 | **Temiz clone'dan build alınamaz** (`packaging/`, `assets/` local-only) | Orta | Bilinçli karar; tek makine bağımlılığını azaltmak için bu girdilerin yedeği ayrı tutulmalı |
| R3 | **v4.1 artifact üretildi ve doğrulandı, ama yayınlanmadı** — v4.1 için tag, GitHub Release ve indirilen asset read-back'i yok; updater ile dağıtım başlamadı. Upstream senkronu bu belgeden okunmaz, **release öncesi canlı git komutlarıyla doğrulanır** | Orta | [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md) 1. adım (canlı `git fetch` + `rev-parse` + `rev-list`) ve 6. adım; yayınlanmış `v4.0` tag'i değiştirilmez |
| R3b | **Gerçek updater akışı uçtan uca doğrulanmadı** — indirme + kurulum başlatma yalnız mock ile örtülü | Orta | v4.1 release'i sonrası eski sürümden canlı güncelleme denemesi |
| R3d | **Updater CDN host'u zamanla değişebilir** — 2026-07-31 canlı API sorgusunda mevcut `v4.0` asset'inin son host'u `release-assets.githubusercontent.com` olarak doğrulandı; allowlist ayrıca `github.com` ve `objects.githubusercontent.com` içerir. GitHub ileride listede olmayan bir host kullanırsa güncelleme **fail-closed** olur — güvenli, ama çalışmaz | Orta | Canlı updater turunda gerçek redirect host'u yeniden ölçülür; host değişirse allowlist güncellenir |
| R5 | **Ele geçirilmiş GitHub release metadata'sına karşı bağımsız güven kökü yok** — updater'ın kullandığı SHA-256 digest'i de aynı release API'sinden gelir; bozuk/eksik indirmeyi ve yanlış asset seçimini engeller, metadata'yı ele geçiren saldırganı engellemez | Orta | Kod imzası (Authenticode) veya ayrı anahtarla imzalanmış güncelleme manifesti; R1 ile birlikte değerlendirilir |
| R3c | **Rollback klasörleri diskte duruyor** (`<ROLLBACK_ROOT>`, ~249 MB) | Düşük | Release ve updater doğrulaması bitince açık onayla silinir |
| R4 | **Mock'lu UI testleri gerçek modal davranışı kanıtlamaz** — O16 tam da bu boşlukta doğdu | Orta | Modal + ilerleme penceresi birleşen başka akışlar (dışa aktarma, yedek geri yükleme) aynı gözle taranmalı |
| R6 | **Gerçek geri yükleme → restart zinciri** paketli sürümde uçtan uca denenmedi; yalnız güvenli mutex senaryosu doğrulandı (v4.0 turunda) | Düşük-orta | İzole profilde gerçek yedekten geri yükleme senaryosu |
| R7 | **Açılışta credential uyarısı ana pencereyi bekletiyor** — güvenli depo okunamazsa kullanıcı onaylayana kadar açılış durur | Düşük-orta | Uyarıyı ana pencere açıldıktan sonra göstermek değerlendirilebilir |
| R8 | **"Tümünü İçe Aktar" gizli sayfaları da okuyor** — O15 yalnız tek sayfa seçimi yolunu kapsadı | Düşük-orta | Gizli sayfa politikasını iki yolda eşitle |
| R9 | **Müşteri tablosunda UNIQUE kimlik kuralı yok** — mükerrer koruması yalnız içe aktarma katmanında | Düşük-orta | Normalize anahtar + geriye uyumlu migration değerlendirmesi |
| R10 | **Teklif/kategori/şablon hata yolları** O14 kapsamına alınmadı | Düşük | Aynı güvenli mesaj + retry deseninin taşınması |
| R11 | **500 kalemli teklifte UI doldurma ~3 sn** (`_add_row`) | Düşük | Gerçek veride maks ~10 kalem; toplu/gecikmeli satır kurulumu ileride |
| R12 | **Normal kapanış yedeği büyük veritabanında kapanışı uzatır** | Düşük | Ölçüldü ve kabul edildi; gerekirse ilerleme göstergesi |
