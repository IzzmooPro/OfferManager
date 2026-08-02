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
| R3 | ~~v4.1 yayınlanmadı~~ → **kapandı 2026-07-31**: v4.1 tag + GitHub Release yayımlandı (public, latest); tek `.exe` asset'i read-back ile **doğrulandı** ve canlı **updater** doğrulaması (D1 + D2) geçti ([CURRENT_STATUS.md](CURRENT_STATUS.md) ve [project_manifest.json](project_manifest.json)) | — | Upstream senkronu bu belgeden okunmaz; her release öncesi [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md) 1. adımıyla canlı git komutlarıyla doğrulanır |
| R3b | **Paketli U17 istemcinin sonraki sürüme yükseltmesi henüz doğrulanmadı** — 2026-07-31'de D1 (kaynak düzeyi canlı güven zinciri) ve D2 (gerçek public v4.0 → canlı v4.1 teslimatı) geçti; ancak D2'de teslimatı yapan istemci **v4.0**'dır ve v4.0 updater'ı U17 doğrulaması yapmaz. **"U17 paketli E2E geçti" denemez.** | Orta | **v4.2 yayımlandığında** kurulu U17'li v4.1 istemciden canlı yükseltme tekrarlanacak; asset adı reddi, host allowlist ve SHA-256/size fail-closed davranışı paketli istemcide ölçülecek |
| R3d | **Updater CDN host'u zamanla değişebilir** — v4.1 release'i için indirmenin son host'u **canlı olarak `release-assets.githubusercontent.com`** doğrulandı ve allowlist'te yer alıyor (`github.com`, `objects.githubusercontent.com` ile birlikte). GitHub ileride listede olmayan bir CDN host'u kullanırsa updater **fail-closed** olur — güvenli, ama güncelleme çalışmaz; **erişilebilirlik riski sürüyor** | Orta | Her release turunda gerçek redirect host'u yeniden ölçülür; değişirse allowlist güncellenir |
| R5 | **Ele geçirilmiş GitHub release metadata'sına karşı bağımsız güven kökü yok** — updater'ın kullandığı SHA-256 digest'i de aynı release API'sinden gelir; bozuk/eksik indirmeyi ve yanlış asset seçimini engeller, metadata'yı ele geçiren saldırganı engellemez | Orta | Kod imzası (Authenticode) veya ayrı anahtarla imzalanmış güncelleme manifesti; R1 ile birlikte değerlendirilir |
| R3c | **Yeniden üretilemeyen iki build artefaktı diskte tutuluyor** (`<ROLLBACK_ROOT>` altında ~118 MB): U17 **öncesi** v4.1 build'i ve **yerel** v4.0 build'i. Yeniden kurulabilir iki kurulum ağacı kopyası 2026-07-31'de silindi (361 MB). Bu iki artefakt yayımlanmadı ve yeniden üretilemez; makinenin geri alınabilirliği bunlara **bağlı değildir** — doğrulanmış v4.1 installer'ı hem yerelde hem GitHub v4.1 release'inde durur | Düşük | Yalnız tarihsel değer; saklamaya devam veya açık onayla silme |
| R4 | **Paketli modal davranışı yalnız frozen EXE'de kanıtlanabilir** — kaynak/offscreen ölçüm O16 desenini yeniden üretemez (2026-07-31'de pozitif kontrol iki kez kuruldu, kilitlenme üretilemedi). Diğer akışların taraması **2026-07-31'de tamamlandı**: **ikinci riskli modal/progress akışı bulunmadı**. Kaynak envanteri: `WindowModal` yalnız `ui/utils/excel_import.py` içinde; sayfa seçimi **progress penceresinden önce** sorulur; dışa aktarma, yedekleme, e-posta, SMTP ve updater akışlarında modal + ilerleme penceresi birleşimi yok | Düşük | Yalnız **modal/progress/import sırası değişirse**: paketli native smoke — [VERIFICATION_GUIDE.md](VERIFICATION_GUIDE.md) B sınıfı 9. senaryo (`IsWindowEnabled`) |
| R6 | **Gerçek geri yükleme → restart zinciri** paketli sürümde uçtan uca denenmedi; yalnız güvenli mutex senaryosu doğrulandı (v4.0 turunda) | Düşük-orta | İzole profilde gerçek yedekten geri yükleme senaryosu |
| R7 | **Açılışta credential uyarısı ana pencereyi bekletiyor** — güvenli depo okunamazsa kullanıcı onaylayana kadar açılış durur | Düşük-orta | Uyarıyı ana pencere açıldıktan sonra göstermek değerlendirilebilir |
| R8 | **"Tümünü İçe Aktar" gizli sayfaları da okuyor** — O15 yalnız tek sayfa seçimi yolunu kapsadı | Düşük-orta | Gizli sayfa politikasını iki yolda eşitle |
| R9 | **Müşteri tablosunda UNIQUE kimlik kuralı yok** — mükerrer koruması yalnız içe aktarma katmanında | Düşük-orta | Normalize anahtar + geriye uyumlu migration değerlendirmesi |
| R10 | ~~Teklif/kategori/şablon hata yolları~~ → **kapandı 2026-08-02**: kategori (R10-A), dashboard teklif/şablon/PDF/dışa aktarma (R10-B) ve teklif kaydetme/PDF aşama sınırları (R10-C) güvenli mesaj + güvenli loga geçirildi; kısmi başarı mesajları ve "Log Klasörünü Aç" erişimi eklendi; PdfWorker yaşam döngüsü kusuru kapandı | — | Kalan alt maddeler R10a–R10c olarak ayrı izlenir |
| R10a | **`create_offer_page` müşteri kaydetme catch'leri** (iki yol) hâlâ ham `{e}` gösteriyor ve loglamıyor; başarı logunda **firma adı** geçiyor | Düşük | R10-C2: servis kaydı ile `_load_customers`/UI seçimini ayırıp güvenli mesaja geçir; catch'i körlemesine değiştirme |
| R10b | **`dashboard_page._open_file`** korumasız `os.startfile` — dosya yoksa yakalanmamış istisna | Düşük | Ayrı küçük tur: güvenli hata + log |
| R10c | **import / settings / backup / reports** ham hata mesajları envanterlenmedi (~19 çağrı yeri) | Düşük | Sonraki envanter turu |
| R11 | **500 kalemli teklifte UI doldurma ~3 sn** (`_add_row`) | Düşük | Gerçek veride maks ~10 kalem; toplu/gecikmeli satır kurulumu ileride |
| R12 | **Normal kapanış yedeği büyük veritabanında kapanışı uzatır** | Düşük | Ölçüldü ve kabul edildi; gerekirse ilerleme göstergesi |

## R12 — v4.2 Aşama 1 sonrası açık kalanlar (2026-08-02)

| No | Risk | Durum |
|---|---|---|
| R12a | **Frozen modda örtülemeyen R11 yolları**: bildirim penceresi içindeki *Panoya Kopyala* tıklaması/pano içeriği ve *teknik hata kutusu → "Hata Raporla"*. Sebep ölçüldü: `QPlainTextEdit` Tab'ı yutuyor, Qt açılır menüsü UIA `Invoke`'unu bloke ediyor. Kaynak testleri bu yolları örter ama **frozen kanıt yerine geçmez**. | AÇIK — Aşama 2'de installer sonrası kurulu uygulamada tekrar denenecek |
| R12b | **`_internal/assets/company.cfg` pakete giriyor**: firmanın kendi adı/adresi/telefonu/e-postası + PDF şablon metinleri. SMTP kullanıcı adı/parola/token **YOK**; dosya v4.1 paketiyle **byte-eşit** (en az v4.1'den beri sürüyor). | AÇIK — kullanıcı kararı bekliyor |
| R12c | **Build sonrası provenance kuralı henüz testle zorlanmıyor**: "build sonrası yalnız manifest/CURRENT_STATUS/KNOWN_RISKS/CHANGELOG değişebilir" kuralı için otomatik kontrol yok. Bu turda metadata commit'i `tests/test_version_consistency.py` dosyasına da dokundu (pakete girmeyen dosya; paket denetimiyle doğrulandı). | AÇIK — kural bir sonraki build'den ÖNCE kodlanmalı |
| R12d | **Paketli U17 → v4.2 gerçek yükseltme (R3b)** ilk kez v4.2 yayımlandıktan sonra D2 ile sınanabilir. | AÇIK — Aşama 2 |

