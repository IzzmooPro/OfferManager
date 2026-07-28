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
| R3 | **v4.1 kaynak hazırlığı yapıldı ama artifact yok** — eldeki `dist/` ve `installer_output/` hâlâ v4.0 derlemesi; `release_ready = false`, `--release` bilerek başarısız | Orta | v4.1 temiz build → frozen smoke → installer doğrulaması → tag + release ([RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md)) |
| R3b | **Kurulu uygulama ve uzaktaki tag hâlâ v4.0** — v4.1 yayınlanana kadar kullanıcılar eski sürümde | Düşük | v4.1 release'i sonrası güncelleme akışıyla dağıtılır; `v4.0` tag'i değiştirilmez |
| R4 | **Mock'lu UI testleri gerçek modal davranışı kanıtlamaz** — O16 tam da bu boşlukta doğdu | Orta | Modal + ilerleme penceresi birleşen başka akışlar (dışa aktarma, yedek geri yükleme) aynı gözle taranmalı |
| R5 | **Güncelleme akışı uçtan uca denenmedi** — indirme + `_apply_update` yalnız mock ile örtülü | Orta | Yayın sonrası izole makinede gerçek güncelleme denemesi |
| R6 | **Gerçek geri yükleme → restart zinciri** paketli sürümde uçtan uca denenmedi; yalnız güvenli mutex senaryosu doğrulandı | Düşük-orta | İzole profilde gerçek yedekten geri yükleme senaryosu |
| R7 | **Açılışta credential uyarısı ana pencereyi bekletiyor** — güvenli depo okunamazsa kullanıcı onaylayana kadar açılış durur | Düşük-orta | Uyarıyı ana pencere açıldıktan sonra göstermek değerlendirilebilir |
| R8 | **"Tümünü İçe Aktar" gizli sayfaları da okuyor** — O15 yalnız tek sayfa seçimi yolunu kapsadı | Düşük-orta | Gizli sayfa politikasını iki yolda eşitle |
| R9 | **Müşteri tablosunda UNIQUE kimlik kuralı yok** — mükerrer koruması yalnız içe aktarma katmanında | Düşük-orta | Normalize anahtar + geriye uyumlu migration değerlendirmesi |
| R10 | **Teklif/kategori/şablon hata yolları** O14 kapsamına alınmadı | Düşük | Aynı güvenli mesaj + retry deseninin taşınması |
| R11 | **500 kalemli teklifte UI doldurma ~3 sn** (`_add_row`) | Düşük | Gerçek veride maks ~10 kalem; toplu/gecikmeli satır kurulumu ileride |
| R12 | **Normal kapanış yedeği büyük veritabanında kapanışı uzatır** | Düşük | Ölçüldü ve kabul edildi; gerekirse ilerleme göstergesi |
