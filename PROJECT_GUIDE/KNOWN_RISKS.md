---
purpose: Doğrulanmış açık riskler ve sonraki adımları — snapshot.
read_when: Denetim, release kararı, risk analizi.
covers: []
last_verified_commit: 060baf3
last_verified_date: 2026-07-28
volatile: true
---

# Bilinen riskler (snapshot — 2026-07-28)

Kapanmış bulgular burada değil, [AUDIT_HISTORY.md](AUDIT_HISTORY.md) içindedir.

| # | Risk | Şiddet | Sonraki adım |
|---|---|---|---|
| R1 | **Kod imzası yok** — SmartScreen "bilinmeyen yayımcı" uyarısı sürüyor | Orta | İmzalama sertifikası kararı; alınmazsa kullanıcıya beklenen uyarı anlatılır |
| R2 | **Temiz clone'dan build alınamaz** (`packaging/`, `assets/` local-only) | Orta | Bilinçli karar; tek makine bağımlılığını azaltmak için bu girdilerin yedeği ayrı tutulmalı |
| R3 | **v4.1 artifact hazır ve doğrulandı ama yayınlanmadı** — tag, GitHub Release ve updater read-back yok; uzaktaki tag hâlâ `v4.0`, `origin/main` geride | Orta | [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md) 6. adım; `v4.0` tag'i değiştirilmez |
| R3b | **Gerçek updater akışı uçtan uca doğrulanmadı** — indirme + kurulum başlatma yalnız mock ile örtülü | Orta | v4.1 release'i sonrası eski sürümden canlı güncelleme denemesi |
| R3c | **Rollback klasörleri diskte duruyor** (`<ROLLBACK_ROOT>`, ~249 MB) | Düşük | Release ve updater doğrulaması bitince açık onayla silinir |
| R4 | **Mock'lu UI testleri gerçek modal davranışı kanıtlamaz** — O16 tam da bu boşlukta doğdu | Orta | Modal + ilerleme penceresi birleşen başka akışlar (dışa aktarma, yedek geri yükleme) aynı gözle taranmalı |
| R6 | **Gerçek geri yükleme → restart zinciri** paketli sürümde uçtan uca denenmedi; yalnız güvenli mutex senaryosu doğrulandı (v4.0 turunda) | Düşük-orta | İzole profilde gerçek yedekten geri yükleme senaryosu |
| R7 | **Açılışta credential uyarısı ana pencereyi bekletiyor** — güvenli depo okunamazsa kullanıcı onaylayana kadar açılış durur | Düşük-orta | Uyarıyı ana pencere açıldıktan sonra göstermek değerlendirilebilir |
| R8 | **"Tümünü İçe Aktar" gizli sayfaları da okuyor** — O15 yalnız tek sayfa seçimi yolunu kapsadı | Düşük-orta | Gizli sayfa politikasını iki yolda eşitle |
| R9 | **Müşteri tablosunda UNIQUE kimlik kuralı yok** — mükerrer koruması yalnız içe aktarma katmanında | Düşük-orta | Normalize anahtar + geriye uyumlu migration değerlendirmesi |
| R10 | **Teklif/kategori/şablon hata yolları** O14 kapsamına alınmadı | Düşük | Aynı güvenli mesaj + retry deseninin taşınması |
| R11 | **500 kalemli teklifte UI doldurma ~3 sn** (`_add_row`) | Düşük | Gerçek veride maks ~10 kalem; toplu/gecikmeli satır kurulumu ileride |
| R12 | **Normal kapanış yedeği büyük veritabanında kapanışı uzatır** | Düşük | Ölçüldü ve kabul edildi; gerekirse ilerleme göstergesi |
