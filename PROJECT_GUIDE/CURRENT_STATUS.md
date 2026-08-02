---
purpose: Projenin son doğrulanmış durumu — tarihli yakalama. Tarihçe için AUDIT_HISTORY.
read_when: Genel yönelim, build/release öncesi, uzun aradan sonra.
covers:
  - core/constants.py
last_verified_commit: 25518fb
last_verified_date: 2026-08-02
volatile: true
---

# Son doğrulanmış durum

> **Yakalama tarihi: 2026-08-02 · hedef sürüm: `v4.2` (ARA DURUM — build bekliyor).**
> Bu belge canlı durum iddiasında bulunmaz. **Canlı git durumu snapshot'tan okunmaz; `git status`, `git rev-parse HEAD` ve upstream karşılaştırmasıyla yeniden ölçülür.** Makine-okunur karşılığı: [project_manifest.json](project_manifest.json).

## Sürüm ve kaynak

- Hedef sürüm: **v4.2** — tek kaynak `core/constants.py:APP_VERSION`; Inno `.iss` (`MyAppVersion`, `VersionInfoVersion`, `VersionInfoProductVersion`) ve `version_info.txt` (`4.2.0.0` / `v4.2`) eşitlendi; installer adı `TeklifYonetim_Setup_v4.2.exe`
- ⚠️ **ARA DURUM:** sürüm alanları v4.2'ye yükseltildi, **yeni build henüz alınmadı**. Eldeki derleme hâlâ **v4.1**'dir (build HEAD `d359137`) → `artifact_verification_status = stale_for_target_version`, `release_candidate_ready = false`, `--release` kapısı bilinçli olarak **kırmızı**.
- Eldeki v4.1 artifact'ı ne R10/PdfWorker ne de R11 değişikliklerini içerir; hash/boyutları **v4.2 gibi etiketlenmedi**, olduğu gibi korundu.
- **Doğrulanmış v4.1 artifact arşivi** proje kökünün dışında korunuyor: `<RELEASE_ARCHIVE>/v4.1-published-before-v4.2` (298 dosya, 229.136.053 bayt; dist EXE `872DF3C1…`, installer `DE590641…`). `packaging/Kurulum-Yap.bat` build başında `dist/`, `build/` ve `installer_output/` klasörlerini sildiği için bu kopya **zorunludur**.
- Kaynak davranışı baseline sonucu (PROJECT_GUIDE testleri hariç): **648 passed, 29 subtests** (`060baf3`)
- PROJECT_GUIDE, sürüm tutarlılık, R10 ve R11 testleri dâhil son tam suite: **943 passed, 2 skipped, 267 subtests** (2026-08-02, temiz ağaç). İki skip: `--release` kapısı (artifact hedef sürüm için stale) ve `installer_pending` durum kontrolü — ikisi de ARA DURUMUN beklenen sonucudur.
- `py_compile` tüm proje dosyalarında temiz
- Upstream durumu **her release öncesi canlı git komutlarıyla** doğrulanır; bu belgede canlı remote hash tutulmaz

## R11 geri bildirim özelliği (2026-08-02) — kaynakta tamamlandı

- **Yardım → Sorun veya Öneri Bildir...** menü girişi; teknik hata gerekmez.
- Teknik hata kutularında ve **kısmi başarı** kutularında **"Hata Raporla"** düğmesi. Çakışma / "veritabanı meşgul" gibi beklenen hatalarda **görünmez**; toplu hata kutusunda **bilinçli olarak yoktur** (birden fazla istisnadan yalnız ilkini raporlamak yanıltıcı olur).
- **Tek form:** otomatik toplanan alanların hepsi kalın etiketlerle görünür (Rapor No, Tarih, Sürüm, Sistem + hata yolunda İşlem, Hata Türü, Konum); altında tek düzenlenebilir "Ne oldu?" kutusu. Ayrı ön izleme alanı yoktur — gönderilen metin görünen alanlar + kullanıcı açıklamasıdır.
- **E-postayı Aç / Panoya Kopyala / Vazgeç.** Otomatik gönderim, otomatik ağ isteği ve otomatik hassas veri toplama **yoktur**; kullanıcının SMTP hesabı ve güvenli depodaki parolası **kullanılmaz**. Hiçbir yolda "rapor gönderildi" denmez.
- Rapora ham istisna, traceback, mutlak yol, kayıt id'si, teklif no ve müşteri/firma verisi **girmez**; `mailto:` Qt URL/query API'siyle üretilir (CRLF/`&`/`?` enjeksiyonuna kapalı).
- **Bilinen sınır:** "E-postayı Aç" Windows'un `mailto:` eşlemesine bağlıdır; bazı kurulumlarda yalnız tarayıcı açılabilir veya hiçbir şey açılmayabilir — pencere kısa uyarı gösterir, **"Panoya Kopyala" güvenilir alternatiftir**.
- **Native crash (0xC0000409 sınıfı) v1 kapsamında değildir**: süreç Python'a hiç dönmeden öldüğü için rapor hazırlanamaz.

## Denetim

K1–K6 ve O1–O16 **kapalı** ([AUDIT_HISTORY.md](AUDIT_HISTORY.md)). O4 yanlış pozitif olarak kapandı; O5'in özgün yarış iddiası yanlış pozitifti, komşu kusurlar düzeltildi; O10 ve O11 "olası ölçekleme bulgusu, düzeltildi" sınıfındadır.

## v4.1 doğrulama durumu · TARİHSEL

Aşağıdaki üç kanıt sınıfı **yayımlanan v4.1 artifact'ı** için geçerlidir (kaynak `7395561`, build HEAD `d359137`). **Güncel kaynak `25518fb` için tekrarlanmadı.**

- **Temiz build: GEÇTİ** — `packaging/Kurulum-Yap.bat --no-pause` exit 0; PyInstaller onedir + Inno Setup; log'da `[HATA]`/traceback yok
- **Frozen smoke (kanıt sınıfı B): GEÇTİ** — izole ortamda U17'li dist EXE ile: null keyring'de **gözetimsiz açılış, modal yok**; fail keyring'de **"Güvenli Depo" modalı gerçekten açılıyor** (ana pencere arkasında disabled, mesaj kısa ve güvenli, `Tamam` otomasyonla basıldı); manuel güncelleme ağ-hata yolu **"Güncelleme kontrol edilemedi."** — URL/proxy/traceback sızıntısı ve yanlış "uygulama güncel" mesajı yok; indirme/tarayıcı/installer başlatılmadı; tek örnek kilidi; normal kapanış exit 0, tek izole yedek, thread/native crash izi yok
- **Installer (kanıt sınıfı C): GEÇTİ** — U17 öncesi v4.1 → U17'li v4.1 **yerinde upgrade** (exit 0), kurulu EXE hedef hash ile eşleşti, AppId ve kurulum dizini korundu; kurulu uygulama izole smoke exit 0; **uninstall** (exit 0) ve aynı installer ile **temiz reinstall** (exit 0) bu turda **yapıldı**; ikinci kurulu smoke exit 0; **kullanıcı verisi ve yedekleri byte-birebir korundu**; final durum: **U17'li v4.1 kurulu**
- Installer turunda **üç UAC onayı kullanıcı tarafından elle verildi** (UAC güvenli masaüstü otomatikleştirilemez); UAC dışındaki tüm uygulama tıklamaları otomasyonla yapıldı. Credential Manager get/set/delete = **0**
- **Kod imzası yok** → SmartScreen "bilinmeyen yayımcı" uyarısı beklenir
- Artifact hash/boyutları: [project_manifest.json](project_manifest.json)

## v4.1 yayın durumu — **YAYINLANDI (public, latest)** · TARİHSEL

- Tag **`v4.1`** → `a1bfd88a46cbc783226c148b7f62275101056c8b` · Release: <https://github.com/IzzmooPro/OfferManager/releases/tag/v4.1> · yayın `2026-07-31T10:42:31Z` · `draft=false`, `prerelease=false`, `latest=true`
- Tek `.exe` asset read-back ile doğrulandı: `TeklifYonetim_Setup_v4.1.exe` · `size 52501243` · `digest sha256:de590641…ac98b` · `state uploaded`; yeniden indirilen dosya yerel installer ile **byte-eşit**
- **D1 — kaynak düzeyi canlı U17 güven zinciri: GEÇTİ** (2026-07-31). Gerçek `releases/latest` + gerçek asset; tam ad seçimi, URL/host kontrolü, redirect son host `release-assets.githubusercontent.com`, `Content-Length` = yazılan bayt = 52.501.243, SHA-256 eşleşti, `download_finished=1` / `failed=0`, `os.startfile`/`os._exit`/`webbrowser` = 0. **Installer çalıştırılmadı.**
- **D2 — gerçek teslimat E2E: GEÇTİ** (2026-07-31, ana makinede açık izinle). Gerçek public v4.0 (`32EB324E…94DCA`) kuruldu → v4.0 başlangıç updater'ı canlı v4.1'i gördü → indirme bağımsız doğrulandı (`52501243` / `DE590641…8AC98B`) → kullanıcı UAC onayıyla kurulum → final kurulu EXE **9.437.741 B / `872DF3C1…95A0DD` / v4.1**; izole smoke exit 0, tek izole yedek, crash izi yok. Gerçek kullanıcı verisi/yedekleri **değişmedi**, Credential Manager `get/set/delete = 0`. Üç UAC onayı **kullanıcı müdahalesidir**.
- `updater_end_to_end_verified = true`

> **Kanıt sınırı — silinmemeli.** D1 ve D2 **ayrı** kanıtlardır ve "U17 paketli E2E geçti" diye **genellenemez**. D2'de teslimatı yapan istemci **v4.0**'dır ve v4.0 updater'ı U17 doğrulaması (asset adı, host allowlist, SHA-256/size) **yapmaz** — indirilen dosyanın hash/boyutu bağımsız ölçülmüştür. Paketli U17 istemcinin bir sonraki sürüme gerçek yükseltmesi ilk kez **v4.2** yayımlandığında doğrulanabilir ([KNOWN_RISKS.md](KNOWN_RISKS.md) R3b).

**Kod imzası yok** → Windows SmartScreen "Bilinmeyen yayımcı" uyarısı beklenir ([KNOWN_RISKS.md](KNOWN_RISKS.md) R1).

## R4 modal/progress incelemesi (2026-07-31)

Salt okunur tarama tamamlandı: **ürün kusuru bulunamadı**. Kaynak envanterinde `WindowModal` yalnız `ui/utils/excel_import.py` içinde; sayfa seçimi progress penceresinden önce sorulur; dışa aktarma, yedekleme, e-posta, SMTP ve updater akışlarında **ikinci riskli modal/progress birleşimi yok**. Gerçek Windows platformunda native `IsWindowEnabled` ile ölçüldü.

**Ancak** O16 deseni kaynak modunda (offscreen ve gerçek platform, iki deneme) **yeniden üretilemedi** — özgün kanıt paketli EXE'de alınmıştı. Bu yüzden kalıcı kural korunuyor: modal/progress/import sırası değişirse kanıt **frozen EXE** üzerinde alınır ([VERIFICATION_GUIDE.md](VERIFICATION_GUIDE.md) B sınıfı 9. senaryo, [KNOWN_RISKS.md](KNOWN_RISKS.md) R4).

## R10 güvenilirlik turu (2026-08-02) — kaynakta tamamlandı

- **R10-A** `9bf4d8d` — kategori ekleme/ad değiştirme/silme: ham istisna gitti, güvenli mesaj + güvenli log, "Log Klasörünü Aç" düğmesi; yeni ince sarmalayıcı `ui/utils/operation_error_dialog.py` (`operation_error` UI'dan bağımsız kaldı).
- **R10-B** `49ef0b3` — dashboard teklif/şablon/PDF/dışa aktarma: 12 ham hata yolu kapandı; toplu işlemlerde yalnız güvenli sayılar ("X silindi, Y silinemedi"); `PdfWorker` artık `(exception, güvenli_id)` taşıyor.
- **PdfWorker yaşam döngüsü** `f29ea47` — sonuç sinyali `run()` içinde yayıldığı için temizlik yalnız yerleşik `finished` yolunda yapılıyor. Kusur ölçülmüştü: alt süreç `0xC0000409` ile fast-fail veriyordu.
- **R10-C** `25518fb` — `_finish_offer` **A/B/C/D** aşamalarına ayrıldı; kaydedilmiş teklif/PDF artık inkâr edilmiyor, `_preview_pdf` üretim ve pencere hatası ayrıldı, başarı logundan tam kullanıcı yolu çıkarıldı.

Kalan alt bulgular **kapatılmadı**, ayrı maddeler olarak izleniyor: [KNOWN_RISKS.md](KNOWN_RISKS.md) R10a (müşteri kaydetme catch'leri + firma adı logu), R10b (`_open_file`), R10c (import/settings/backup/reports envanteri).

> **Ayrım — silinmemeli.** *"Yayımlanmış v4.1 geçerlidir"* ile *"mevcut kaynak build edilmedi"* farklı iddialardır. v4.1 tag'i, GitHub Release'i ve canlı updater doğrulaması (D1/D2) **tarihsel olarak geçerlidir**; bu tur yalnız **güncel kaynağın** artifact tazeliğini düşürür.

## Bilinen sınır

`packaging/`, `assets/`, `dist/`, `installer_output/`, `build/`, `Import_Test/` depo dışıdır → **temiz clone'dan build tekrarlanabilir değildir** ([BUILD_AND_PACKAGING.md](BUILD_AND_PACKAGING.md)).

`<ROLLBACK_ROOT>` temizliği **2026-07-31'de açık onayla yapıldı**: yeniden kurulabilir iki kurulum ağacı kopyası silindi (361 MB). Yeniden üretilemeyen iki build artefaktı (**U17 öncesi v4.1** ve **yerel v4.0**, ~118 MB) bilinçli olarak **korundu** ([KNOWN_RISKS.md](KNOWN_RISKS.md) R3c). Geri kurulum bunlara bağlı değildir: doğrulanmış v4.1 installer'ı `installer_output/` altında ve GitHub v4.1 release'inde durur.

## Tamamlananlar (bu yakalama itibarıyla)

v4.1 kaynak hazırlığı · legacy bilgi aktarımı ve temizliği · boş bağlamlı devir testi · **U17 updater güven zinciri** (asset adı + URL/host allowlist + SHA-256/size, fail-closed) · U17'li temiz build · izole frozen smoke · gerçek yerinde upgrade + uninstall + temiz reinstall · artifact kanıtlarının manifeste işlenmesi · **v4.1 tag + GitHub Release yayını** · **canlı updater doğrulaması (D1 + D2)**.

## Kalan aşamalar

**Aşama 1 (bu tur):** R11 kaynak doğrulaması · v4.2 sürüm hazırlığı · yerel commit · temiz build · frozen smoke (B) · artifact metadata.

**Aşama 2 (Codex incelemesinden sonra):**

1. Installer doğrulaması (kanıt sınıfı **C**): upgrade → uninstall → temiz reinstall
2. `origin/main`'e push
3. `v4.2` tag'i ve GitHub Release + asset read-back
4. Canlı updater doğrulaması **D1** ve **D2** — D2 bu kez ilk kez **paketli U17 istemciden** yapılabilir ([KNOWN_RISKS.md](KNOWN_RISKS.md) R3b)
5. Küçük denetim maddeleri: R10a, R10b, R10c

## Bu yakalamayı yenilerken

1. `git rev-parse --short HEAD` ve upstream farkını ölç.
2. `python -m pytest tests -q` sayılarını güncelle (kaynak ve rehber dâhil ayrımını koru).
3. `python PROJECT_GUIDE/scripts/verify_project_guide.py --artifacts` ile hash'leri doğrula.
4. `last_verified_commit` / `last_verified_date` alanlarını ve `project_manifest.json` `snapshot` bölümünü güncelle.
