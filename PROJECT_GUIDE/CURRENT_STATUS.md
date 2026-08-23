---
purpose: Projenin son doğrulanmış durumu — tarihli yakalama. Tarihçe için AUDIT_HISTORY.
read_when: Genel yönelim, build/release öncesi, uzun aradan sonra.
covers:
  - core/constants.py
last_verified_commit: e479b5b
last_verified_date: 2026-08-23
volatile: true
---

# Son doğrulanmış durum

> **Yakalama tarihi: 2026-08-23 · sürüm: `v4.2` — YAYINLANDI (public, latest).**
> **Kaynak, yayımlanmış v4.2 artifact'ından ileridedir.** `e479b5b` için temiz yerel EXE + izlenen Inno installer üretildi; dar eski-DLL upgrade temizliği, installer C ve kurulu açılış/kapanış smoke'u geçti. Tam B turu ve yeni release yapılmadı; bu yerel build public v4.2 asset'inin yerine geçmez.
> Bu belge canlı durum iddiasında bulunmaz. **Canlı git durumu snapshot'tan okunmaz; `git status`, `git rev-parse HEAD` ve upstream karşılaştırmasıyla yeniden ölçülür.** Makine-okunur karşılığı: [project_manifest.json](project_manifest.json).

## Sürüm ve kaynak

- Hedef sürüm: **v4.2** — tek kaynak `core/constants.py:APP_VERSION`; Inno `.iss` (`MyAppVersion`, `VersionInfoVersion`, `VersionInfoProductVersion`) ve `version_info.txt` (`4.2.0.0` / `v4.2`) eşitlendi; installer adı `TeklifYonetim_Setup_v4.2.exe`
- **Doğrulama durumu — v4.2 artifact'ı için (TARİHSEL, `227656b`):** temiz build, frozen smoke (**B**), installer (**C**), R12a Yol A+B, yayın ve canlı updater (**D1+D2**) **TAMAMLANDI**. Bu kanıtlar geçerliliğini korur.
- **Yerel doğrulama build durumu (`e479b5b`):** tam test kapısı + temiz EXE/Inno build + installer C geçti. İzlenen `[InstallDelete]` yalnız iki eski OpenSSL DLL'ini hedefliyor; upgrade sonrası paket ağacı `dist` ile birebir. Önceki `841ab4c` B-4 ve `17117b0` B-8/B-9 kanıtları tarihsel hedefli kayıt olarak korunur. Tam B turu yapılmadığı ve yerel set yayımlanmadığı için `artifact_verification_status = stale_source_changed`, `release_candidate_ready = false` kalır.
- Yayımlanmış v4.2 artifact'ları: dist EXE `476015268A26…5353B` (9.476.704 B, 4.2.0.0 / v4.2) · installer `TeklifYonetim_Setup_v4.2.exe` `D61488DFE55D…82B2` (52.548.738 B). Yerel güncel-kaynak doğrulama seti ayrıdır: EXE `D06ECFDECB5C…85A534` (9.722.873 B) · installer `F1B6316A4CC1…0A2F4E` (51.293.458 B).
- **Makinede kurulu sürüm v4.2** — `e479b5b` yerel installer'ı ile kontrollü yerinde upgrade yapıldı: kurulu EXE `D06ECFDECB5C…85A534`, registry `DisplayVersion v4.2`, AppId ve kurulum dizini korundu. Gerçek kullanıcı verisi **34/34**, yedekler **12/12** byte/hash değişmedi; DB `integrity_check=ok`. Kaldırma ve temiz yeniden kurulum bu turda yapılmadı.
- **Doğrulanmış v4.1 artifact arşivi** proje kökünün dışında korunuyor: `<RELEASE_ARCHIVE>/v4.1-published-before-v4.2` (298 dosya, 229.136.053 bayt; dist EXE `872DF3C1…`, installer `DE590641…`). `packaging/Kurulum-Yap.bat` build başında `dist/`, `build/` ve `installer_output/` klasörlerini sildiği için bu kopya **zorunludur**.
- **Paket içeriği — kabul edilmiş ürün kararı:** `_internal/assets/company.cfg` (firma adı, adres, telefon, e-posta, teklif öneki, PDF varsayılan metinleri) ve `assets/logo.png` pakete **bilinçli olarak** dahildir; ürün belirli bir firma için hazırlanmıştır. Paket içinde **SMTP parolası, credential veya token yoktur**. Kullanıcı bu bilgilerin public GitHub installer'ında bulunmasını **kabul etmiştir (2026-08-02)**. `core/config.py` varsayımları, `assets/company.cfg`, `assets/logo.png` ve `packaging/TeklifYonetim.spec` asset kapsamı **değiştirilmez**. → KNOWN_RISKS R12b (kapalı)
- Kaynak davranışı baseline sonucu (PROJECT_GUIDE testleri hariç): **648 passed, 29 subtests** (`060baf3`)
- **Canlı HEAD ve yerel doğrulama build girdisi: `e479b5b88d0a5b1476e5bf648b3ccc28768595f7`.** Manifestin birincil `source_commit=0a1a1ae` alanı önceki bütünleşik A-snapshot'ını, `built_from_commit=227656b` ise yayımlanmış seti korur; yeni tam build ve installer kanıtı `current_source_validation_build` altındadır.
- Birincil bütünleşik son tam suite (`0a1a1ae`): **1165 passed, 3 skipped, 345 subtests**. Güncel `e479b5b` build kapısı ayrıca **1222 passed, 6 skipped, 345 subtests** ölçtü.
- Tarihsel bağlam: `c3f711e` turunda ölçülen tam paket **1152 passed, 4 skipped, 343 subtests** idi; güncel sonuç değildir.
- v4.2 **build anındaki** kapı sonucu ayrı ve tarihsel bir alandır: manifest `build_gate_test_result` (`227656b`) — aşağıdaki "v4.2 Aşama 1 doğrulaması" bölümünde.
- `py_compile` tüm proje dosyalarında temiz
- Upstream durumu **her release öncesi canlı git komutlarıyla** doğrulanır; bu belgede canlı remote hash tutulmaz

## 2026-08-23 yerel tracked-installer build + C doğrulaması

- Build girdisi: `e479b5b`; `packaging/Kurulum-Yap.bat --no-pause` exit 0. Tam test kapısı **1222 passed, 6 skipped, 345 subtests**; temiz PyInstaller onedir + Inno Setup 7.1.0 tamamlandı.
- Yerel EXE: `9.722.873 B / D06ECFDECB5C…85A534 / FileVersion 4.2.0.0 / ProductVersion v4.2`; dist ağacı `296 dosya / 170.329.053 B`.
- Yerel installer: `51.293.458 B / F1B6316A4CC1…0A2F4E`; izlenen `.iss` `59E75C075E77…CA5BE`. Installer exit 0, restart yok; kurulu EXE dist ile aynı, registry/AppId/kısayollar korundu.
- **Installer C: GEÇTİ.** İlk upgrade iki eski DLL'in paket dışında kaldığını yakaladı; dar `[InstallDelete]` düzeltmesi sonrası `_internal\libcrypto-3-x64.dll` ve `libssl-3-x64.dll` silindi. Final kurulum ağacında eksik/fazla/değişen paket dosyası yok; yalnız `unins000.*` installer metadata'sı ayrı.
- Gerçek veri 34/34 ve yedekler 12/12 değişmedi; DB `integrity_check=ok`. Proje dışı rollback kurulum/veri/yedek/registry/kısayol kopyalarıyla korunuyor.
- Final kurulu EXE izole profilde ana pencereyi açtı; kapanış yedeği alındı, DB kapandı, exit 0 ve süreç sızıntısı yok. Tekrarlı görsel UI smoke kullanıcı tarafından fiziksel Esc ile durduruldu; uygulamanın çalıştığı kullanıcı tarafından doğrulandı ve önceki aynı-runtime smoke kanıtı tekrar edilmedi.
- Yerel `.spec` SHA-256: `253D6A6DC0529FBA9E47F9F944EA67F3B159536472CF4BD3F1ACE1390C734B67`; `disable_windowed_traceback=True` korundu.
- **Hedefli B-4 PDF/cp1254 konsol alt kapsamı: GEÇTİ.** Sekiz profil/temp değişkeni + `fail.Keyring` + loopback proxy ile izole paketli EXE'de var olan sentetik teklif seçildi; native kaydet penceresiyle PDF üretildi. Konsolda `PDF oluşturuluyor: SNS-000001 -> ...` ve `PDF tamamlandı` satırları görüldü; `UnicodeEncodeError`, `Logging error`, traceback ve native crash izi yoktu.
- PDF `219.514 B / 147CBD262DD5…06B9B`, 1 sayfa; teklif no mevcut, maliyet/kâr metni yok. Canlı izole DB ve kapanış yedeği `integrity_check=ok`; normal kapanış exit 0; gerçek kullanıcı veri/yedek sayımları değişmedi.
- **Kanıt sınırı:** B-4 PDF/cp1254 kanıtı uygulama runtime kaynağı aynı olan önceki `841ab4c` artifact'ına aittir; final hash'e özgü tam B turu değildir. Bu tur paketleme değişikliği için temiz build + installer C + açılış/kapanış smoke'u yürüttü. Public v4.2 release/tag/asset kayıtları değiştirilmedi.

### Önceki `17117b0` hedefli frozen doğrulaması — tarihsel

- Build girdisi: `17117b0`; temiz PyInstaller onedir build. Inno installer **üretilmedi**. EXE `9.722.876 B / B0222011D663…FC3E / FileVersion 4.2.0.0 / ProductVersion v4.2`; dist ağacı `296 dosya / 170.329.056 B`.
- Yerel `.spec` SHA-256: `253D6A6DC0529FBA9E47F9F944EA67F3B159536472CF4BD3F1ACE1390C734B67`; `disable_windowed_traceback=True` ve build TOC içinde `pyi-disable-windowed-traceback` doğrulandı.
- Değişiklik-etkili kaynak regresyonları: `test_windowed_error_reporting.py` **29 passed**; `test_restart_flow.py` **32 passed**; `test_project_guide.py` sonucu **100/100 ve 7 subtests**. Tam suite bu turda yeniden çalıştırılmadı.
- **B-8 hata penceresi: GEÇTİ.** Bozuk izole DB ile tek güvenli Türkçe hata penceresi; ikinci PyInstaller traceback penceresi yok; UI'da SQLite/traceback yok; teknik traceback logda tam bir kez; exit code 1; gerçek kullanıcı verisi değişmedi.
- **B-9 modal/progress: GEÇTİ.** Zorunlu sekiz profil/temp değişkeni + `fail.Keyring` + loopback proxy izolasyonunda, iki sayfalı XLSX için `Çalışma Sayfası Seç` native `IsWindowEnabled=true` (`HWND 78056274`, owner `21040436`); aynı anda görünür `İçe Aktarma` progress penceresi yok. İptal öncesi/sonrası DB dump `A608A520…F2C26`, `integrity_check=ok`, tüm uygulama tabloları 0 satır. Normal kapanış exit 0; workbook ve gerçek veri/yedek parmak izi değişmedi; native crash marker yok.
- **Kanıt sınırı:** Bu kayıt hedefli B-8/B-9 kanıtıdır; tam B-1..B-9 turu veya installer C kanıtı değildir. Public v4.2 release/tag/asset kayıtları değiştirilmedi.

## R11 geri bildirim özelliği (2026-08-02) — kaynakta tamamlandı

- **Yardım → Sorun veya Öneri Bildir...** menü girişi; teknik hata gerekmez.
- Teknik hata kutularında ve **kısmi başarı** kutularında **"Hata Raporla"** düğmesi. Çakışma / "veritabanı meşgul" gibi beklenen hatalarda **görünmez**; toplu hata kutusunda **bilinçli olarak yoktur** (birden fazla istisnadan yalnız ilkini raporlamak yanıltıcı olur).
- **Tek form:** otomatik toplanan alanların hepsi kalın etiketlerle görünür (Rapor No, Tarih, Sürüm, Sistem + hata yolunda İşlem, Hata Türü, Konum); altında tek düzenlenebilir "Ne oldu?" kutusu. Ayrı ön izleme alanı yoktur — gönderilen metin görünen alanlar + kullanıcı açıklamasıdır.
- **E-postayı Aç / Panoya Kopyala / Vazgeç.** Otomatik gönderim, otomatik ağ isteği ve otomatik hassas veri toplama **yoktur**; kullanıcının SMTP hesabı ve güvenli depodaki parolası **kullanılmaz**. Hiçbir yolda "rapor gönderildi" denmez.
- Rapora ham istisna, traceback, mutlak yol, kayıt id'si, teklif no ve müşteri/firma verisi **girmez**; `mailto:` Qt URL/query API'siyle üretilir (CRLF/`&`/`?` enjeksiyonuna kapalı).
- **Bilinen sınır:** "E-postayı Aç" Windows'un `mailto:` eşlemesine bağlıdır; bazı kurulumlarda yalnız tarayıcı açılabilir veya hiçbir şey açılmayabilir — pencere kısa uyarı gösterir, **"Panoya Kopyala" güvenilir alternatiftir**.
- **Native crash (0xC0000409 sınıfı) v1 kapsamında değildir**: süreç Python'a hiç dönmeden öldüğü için rapor hazırlanamaz.

## v4.2 Aşama 1 doğrulaması (2026-08-02)

- **Temiz build: GEÇTİ** — exit 0; adım 2'deki pytest kapısı build commit'inde **943 passed, 2 skipped, 267 subtests** (manifest `build_gate_test_result`; metadata commit'i sonrası güncel ağaçta 941/4/267 — fark, artifact durumunun `installer_pending` olmasıyla iki kontrolün atlanmasıdır); log'da `[HATA]`/traceback yok.
- **Frozen smoke (kanıt sınıfı B): GEÇTİ** — izole profil + loopback proxy; açılış ve sürüm `v4.2`, null keyring'de **modal yok**, fail keyring'de **"Güvenli Depo" modalı gerçekten açıldı** (ana pencere disabled), tek örnek kilidi (ikinci süreç exit 0), **Yardım → "Sorun veya Öneri Bildir" penceresi açıldı** (ana pencere modal arkasında disabled, Vazgeç ile kapandı), normal kapanış exit 0, tek izole yedek, **0xC0000409 / QThread destroyed / Traceback yok**, tarayıcı-e-posta-installer-TeklifUpdate oluşmadı.
- **R12a — KAPALI (2026-08-02):** *Yol A* paketli dist EXE'de, *Yol B* **kurulu v4.2**'de doğrulandı. Yol B: izole profil + izole DB salt-okunur tetikleyici → gerçek hata kutusu (**Tamam / Log Klasörünü Aç / Hata Raporla**) → gerçek tıklama → tek-form pencerede `İşlem: Kategori ekle`, `Hata Türü: OperationalError`, `Konum: db_manager.py:188 execute <- category_service.py:29 add <- category_dialog.py:78 _add` → **Panoya Kopyala gerçek tıklama**, panoda görünen alanlar + açıklama + teknik özet, **yasaklı içerik yok**. Navigasyon tamamen dış otomasyonla (UIA okuma + gerçek fare) yapıldı.
- **Bu turda tekrarlanmayan B senaryoları** (ilgili kod v4.1'den beri değişmedi): B-4 temel UI akışı (müşteri/ürün/teklif/PDF), B-6 uzun worker ile kapanış, B-7 restart, B-9 modal/progress (O16).
- **Installer (C), push, tag, GitHub Release ve canlı updater (D1/D2): YAPILMADI.**

## v4.2 yayın durumu — **YAYINLANDI (public, latest)**

- Tag **`v4.2`** → `227656b9566200e18a5acdf64da4eac0d93be83d` (**build commit**; metadata commit'lerine taşınmadı) · Release: <https://github.com/IzzmooPro/OfferManager/releases/tag/v4.2> · yayın `2026-08-02T21:09:58Z` · `draft=false`, `prerelease=false`, `latest=true`
- Tek `.exe` asset read-back: `TeklifYonetim_Setup_v4.2.exe` · `size 52548738` · `digest sha256:d61488df…82b2` · `state uploaded`. **Draft aşamasında ve public yayından sonra ayrı ayrı indirildi; ikisi de yerel installer ile byte-eşit.** `--clobber` kullanılmadı.
- **v4.1 tag'i (`a1bfd88`) ve release'i DEĞİŞMEDİ.**
- **D1 — kaynak düzeyi canlı güven zinciri: GEÇTİ.** Gerçek `releases/latest`; tam asset adı, başlangıç host `github.com` ve redirect son host `release-assets.githubusercontent.com` allowlist içinde, `Content-Length` = yazılan bayt = API size = 52.548.738, SHA-256 eşleşti, `download_finished=1` / `failed=0`. **Fail-closed dört senaryoda doğrulandı** (digest yok / asset adı yanlış / size=0 / aynı ad iki kez). `os.startfile`/`os._exit`/`webbrowser` = 0; **installer çalıştırılmadı**.
- **D2 — paketli U17 v4.1 → canlı v4.2: GEÇTİ.** Bu **R3b/R12d'nin ilk gerçek kanıtıdır**. Arşivdeki public v4.1 installer'ı ile geri kuruldu (`872DF3C1…`), paketli U17 istemci canlı v4.2'yi kendiliğinden gördü ("Mevcut sürüm : v4.1 / Yeni sürüm : v4.2"), "Güncelle" dış otomasyonla tıklandı, indirme U17 doğrulamasından geçti, indirilen dosya **bağımsız ölçüldü** (`52548738` / `D61488DF…82B2`), kullanıcı UAC onayıyla kuruldu; final kurulu EXE **9.476.704 / `476015268A26…5353B` / v4.2**. Final izole smoke exit 0, tek izole yedek, crash izi yok.
- **İki UAC onayı kullanıcı müdahalesidir** (v4.1 geri kurulumu + v4.2 güncelleme kurulumu). Credential Manager `get/set/delete = 0`.

- **D2b — kullanıcı eliyle, gerçek profilde bağımsız doğrulama: GEÇTİ (2026-08-03).** Kullanıcı kendi kurulumunda v4.1'e dönüp güncellemeyi denedi: `00:22:47 Güncelleme mevcut: v4.2` → `00:23:29 Yeni sürüm indirildi` (bu satır yalnız U17 doğrulaması geçtikten sonra yazılır) → `00:23:38 Version: v4.2`. **Gerçek veri korundu**: tek fark yeni günlük log ve `backup_meta.json`; `database.db` değişmedi. Bu kanıt D2'nin yerine geçmez, onu güçlendirir (D2 izole + otomasyon, D2b gerçek profil + kullanıcı).

> **Kanıt sınırı — silinmemeli.** D2 artık **paketli U17 istemciden** yapıldı; ancak bu, **gelecekteki** bir sürümün teslimatını kanıtlamaz. Her yeni sürümde D1/D2 tekrarlanır.

## Denetim

K1–K6 ve O1–O16 **kapalı** ([AUDIT_HISTORY.md](AUDIT_HISTORY.md)). O4 yanlış pozitif olarak kapandı; O5'in özgün yarış iddiası yanlış pozitifti, komşu kusurlar düzeltildi; O10 ve O11 "olası ölçekleme bulgusu, düzeltildi" sınıfındadır.

## v4.1 doğrulama durumu · TARİHSEL

Aşağıdaki üç kanıt sınıfı **yayımlanan v4.1 artifact'ı** için geçerlidir (kaynak `7395561`, build HEAD `d359137`). **Bu tarihsel kanıtlar sonraki kaynak commit'leri için tekrarlanmadı.**

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

Kalan alt bulgular sonraki turlarda kapatıldı: R10a/R10b (2026-08-03) ve **R10c (2026-08-04, aşağıda)**.

## R10c güvenli hata turu (2026-08-04) — **DÖRT ALT TURLA TAMAMLANDI**

Hepsi test-first yürütüldü: önce kırmızı regresyon testi, sonra en küçük genel düzeltme.

| Alt tur | Commit | Kapsam | Test |
|---|---|---|---|
| **R10c-1 REPORTS** | `c2dfca0` | Rapor oluşturma ve dışa aktarma hata yolları güvenli altyapıya geçirildi; ham istisna, traceback, SQL, kullanıcı yolu ve müşteri verisi gösterilmiyor | `tests/test_reports_safe_errors.py` |
| **R10c-2 SETTINGS** | `745fd55` | Ayarlar, SMTP ve logo yükleme/kaldırma hata yolları; logo yükleme başarısı açık dönüş değeriyle ayrıldı; iptal/kopyalama hatasında logo devre dışı işareti korunuyor; marker yazılamazsa önizleme gerçek aktif logoyu gösteriyor | `tests/test_settings_safe_errors.py` |
| **R10c-3 BACKUP** | `8616862` | Restore durumları ayrıldı (`preflight_failed` / `rolled_back` / `rollback_failed`); rollback tüm hedefleri deniyor, ilk hatada durmuyor; metadata aşaması asıl yedekleme başarısını inkâr etmiyor; geçici klasör temizleme hatası restore sonucunu değiştirmiyor; başarı ve restart yalnız gerçek başarıda | `tests/test_backup_safe_errors.py` |
| **R10c-4 IMPORT** | `46d4d75` | Dosya okuma, CSV/XLSX, satır, kategori, teklif, doğrulama, aşama ve dışa aktarma hata yolları; aşamalar birbirinin başarısını inkâr etmiyor; kategori yazımı yalnız güvenli sayısal `stage_state` ile taşınıyor; workbook başarı ve hata yollarında güvenli kapatılıyor | `tests/test_import_safe_errors.py`, `tests/test_csv_import_errors.py` |

- Son doğrulanmış tam paket: **1127 passed, 5 skipped, 343 subtests**. Ölçüm, `46d4d75`'e giren **aynı kaynak/test içeriğiyle commit'ten ÖNCE** yapıldı; **commit sonrasında tam paket yeniden çalıştırılmadı**. Aynı turda `py_compile`, `verify_project_guide.py` ve `git diff --check` temizdi. Commit/push sonrası ağaç temizliği ve upstream eşitliği **ayrı bir git kanıtıdır**; bu snapshot'tan okunmaz, canlı git komutlarıyla ölçülür.
- Kurallar [CRITICAL_INVARIANTS.md](CRITICAL_INVARIANTS.md) 18, 18-1, 18b, 18b-2, 18b-3 maddelerine bağlandı.

> **Kanıt sınırı — silinmemeli.** R10c'nin kanıt sınıfı: **kaynak testleri**, **mock/izole geçici profil ölçümleri** (gerektiği yerde test DB veya geçici dosya) ve **bazı alt turlarda izole kaynak-modu Windows Qt smoke/probları**. Bu tur için **yeni frozen/paketli EXE, installer, gerçek disk-dolu, gerçek dosya kilidi ve gerçek SQLite commit hatası kanıtı ÜRETİLMEDİ**. Bu yüzden tur, **R6**'daki paketli gerçek geri yükleme → restart kanıtını ve **R8**'deki gizli sayfa politikası maddesini **kapatmaz**; R8 davranışı yalnız korunmuştur.
> **Bu tur yeni build/paketli EXE/installer üretmedi.** Mevcut kaynak, yayımlanmış v4.2 artifact'ından **ileridedir**; v4.2 tag'i, release'i, artifact hash'leri ve D1/D2/D2b kanıtları **değişmemiştir**.

> **Ayrım — silinmemeli.** *"Yayımlanmış v4.1 geçerlidir"* ile *"mevcut kaynak build edilmedi"* farklı iddialardır. v4.1 tag'i, GitHub Release'i ve canlı updater doğrulaması (D1/D2) **tarihsel olarak geçerlidir**; bu tur yalnız **güncel kaynağın** artifact tazeliğini düşürür.

## Bilinen sınır

`packaging/`, `assets/`, `dist/`, `installer_output/`, `build/`, `Import_Test/` depo dışıdır → **temiz clone'dan build tekrarlanabilir değildir** ([BUILD_AND_PACKAGING.md](BUILD_AND_PACKAGING.md)).

`<ROLLBACK_ROOT>` temizliği **2026-07-31'de açık onayla yapıldı**: yeniden kurulabilir iki kurulum ağacı kopyası silindi (361 MB). Yeniden üretilemeyen iki build artefaktı (**U17 öncesi v4.1** ve **yerel v4.0**, ~118 MB) bilinçli olarak **korundu** ([KNOWN_RISKS.md](KNOWN_RISKS.md) R3c). Geri kurulum bunlara bağlı değildir: doğrulanmış v4.1 installer'ı GitHub v4.1 release'inde ve proje kökünün **dışındaki** doğrulanmış release arşivinde durur (`installer_output/` artık proje kökünde bulunmaz).

## Tamamlananlar (bu yakalama itibarıyla)

v4.1 kaynak hazırlığı · legacy bilgi aktarımı ve temizliği · boş bağlamlı devir testi · **U17 updater güven zinciri** (asset adı + URL/host allowlist + SHA-256/size, fail-closed) · U17'li temiz build · izole frozen smoke · gerçek yerinde upgrade + uninstall + temiz reinstall · artifact kanıtlarının manifeste işlenmesi · **v4.1 tag + GitHub Release yayını** · **canlı updater doğrulaması (D1 + D2)**.

## Kalan aşamalar

v4.2 yayın turu **kapandı**. **R10a ve R10b kapandı (2026-08-03)** — teklif ekranındaki iki müşteri kaydetme yolu güvenli hata altyapısına ve iki aşamalı sınıra geçirildi; dashboard'daki PDF açma yolu korumaya alındı. **R10c dört alt turla kapandı (2026-08-04)** — reports, settings, backup ve import hata yolları güvenli altyapıya geçirildi (yukarıdaki tablo).

**R12c kapandı (2026-08-08, `c3f711e`)** — build sonrası provenance kapısı kodlandı ve testle zorlanıyor (aşağıdaki bölüm).

Açık kalanlar, **paketli/ürün davranışı kanıtı gerektiren** maddelerdir:

- **R6 — AÇIK:** paketli gerçek geri yükleme → restart zinciri. Kaynak/mock kanıtıyla kapanmaz; kendi kanıt sınıfını bekler.
- **R8 — AÇIK, ürün sahibinin kararıyla ERTELENDİ (2026-08-14):** "Tümünü İçe Aktar" gizli sayfa politikası. Kapatılmış veya çözülmüş değildir; mevcut davranış bilinçli olarak korunur ve sonraki UI/tasarım turunun zorunlu kapsamına alınmaz.

Diğer maddelerin durumu bu turda değişmedi — güncel liste [KNOWN_RISKS.md](KNOWN_RISKS.md).

## R12c — build sonrası provenance kapısı (2026-08-08) — **KAPANDI**

- Kök neden: artifact `227656b`'den build edilmişti; sonrasında kaynak ve test dosyaları değiştiği hâlde `--release` **exit 0** veriyordu.
- Yeni `kontrol_build_sonrasi_provenance` kapısı build sonrasında YALNIZ dört **tam** yola izin verir: `PROJECT_GUIDE/project_manifest.json`, `PROJECT_GUIDE/CURRENT_STATUS.md`, `PROJECT_GUIDE/KNOWN_RISKS.md`, `docs/CHANGELOG.md`. Klasör/prefix izni yoktur.
- Commit edilmiş, staged, unstaged ve untracked/non-ignored yasak yollar birlikte denetlenir (add/modify/delete/rename). Eksik/bozuk `built_from_commit`, Git okunamaması ve build commit'inin HEAD'in atası olmaması **fail-closed**. Kontrol yalnız `--release` modunda zorunludur.
- Kanıt: kırmızı **23 failed / 1 passed** → provenance testleri **24 geçti**; `test_project_guide` **98 geçti / 7 subtest**; `test_project_guide + test_version_consistency` **148 geçti / 4 atlandı / 9 subtest**; tam paket **1152 passed, 4 skipped, 343 subtests**. Tam paket ölçümü `c3f711e`'ye giren aynı kaynak/test içeriğiyle **commit'ten önce** yapıldı; commit sonrasında yeniden çalıştırılmadı. `py_compile` ve `git diff --check` temiz.
- Gerçek depo modları: normal **exit 0**, `--stale` **exit 0 / 0 uyarı**, `--artifacts` **exit 0**, `--release` **exit 1** — `release_candidate_ready=false` **ve** build sonrası provenance ihlalleri nedeniyle. (Provenance hata **sayısı** her metadata değişikliğinde değişir; bu snapshot'ta sabitlenmez — güncel değer komutu çalıştırarak ölçülür.) **Yeni build alınana kadar `--release`'in kırmızı kalması doğru davranıştır.**

> **Kanıt sınırı — silinmemeli.** Kapı yalnız **Git'in görebildiği** provenance'ı kanıtlar; gitignore/local-only `packaging/` ve `assets/` girdilerinin geçmişini kanıtlamaz. `built_from_commit` kapının **güvendiği** girdidir ve artifact ile commit arasında kriptografik bağ yoktur — gerçek build loguyla eşleşmesi release incelemesinde **ayrıca** doğrulanmalıdır.

## Açılış bildirimi ertelemesi (2026-08-14, `0a1a1ae`)

Süresi dolan teklif modalı, `MainWindow` oluşturulurken (`_navigate(0)` → `on_enter`) açıldığı için **splash ekranının üzerinde** beliriyordu.

- Dashboard verisi açılışta **yüklenmeye devam eder**; yalnız bildirimler ertelenir.
- Splash fade'in gerçek `finished` sinyali → `acilis_bildirimlerini_planla()` → pencereye ait tek atımlık zamanlayıcı → bir sonraki event-loop turunda gösterim. **Sabit gecikme yok.**
- Gösterim **idempotenttir**; pencere görünür değilse veya kapanış hazırlığı başladıysa modal açılmaz.
- Onay/ret sözleşmesi değişmedi: "Şimdilik Dokunma" / Esc / X hiçbir yazma yapmaz.
- Kanıt sınıfı: **kaynak testi + kaynak-modu Windows Qt smoke**. → `tests/test_expired_offer_prompt.py`, [CRITICAL_INVARIANTS.md](CRITICAL_INVARIANTS.md) 7b

## Bu yakalamadaki artifact durumu

- Birincil bütünleşik A-suite snapshot'ı `source_commit = 0a1a1ae`; canlı HEAD/yerel build girdisi `e479b5b`; yayımlanmış setin `built_from_commit = 227656b` değeri değiştirilmedi. Güncel tam build ve installer C kanıtı manifestte ayrı `current_source_validation_build` alanındadır.
- Proje kökünde `e479b5b` build setine ait yeni `build/`, `dist/` ve `installer_output/` vardır. Yerel installer `F1B6316A…0A2F4E / 51.293.458 B` public `D61488DF…BF82B2` installer değildir; C geçmiş olsa da tam B/release yapılmadığı için `release_candidate_ready=false` kalır.
- Manifestin birincil `dist_exe` alanı yayımlanmış/tarihsel v4.2 EXE kimliğini korur; yeni yerel `dist/TeklifYonetim/TeklifYonetim.exe` bunun yerine yazılmaz. `--artifacts`, tarihsel EXE proje kökünde bulunmadığı için o alanı uyarıyla atlar; tarihsel installer'ı hash/boyutla doğrular. Yeni yerel EXE hash'i ayrı olarak doğrulanır.
- **Yayımlanmış v4.2 artifact'ı tarihsel olarak geçerlidir** ve proje kökünün dışındaki doğrulanmış arşivde korunur: `<RELEASE_ARCHIVE>/v4.2-published-before-ui-redesign` — **299 dosya, 229.266.985 bayt**; dist EXE `476015268A26…5353B`, installer `D61488DFE55D…82B2`. Bu kopya **tarihsel** bir kayıttır; güncel kaynağın artifact'ı **değildir**.
- v4.2 tag'i, GitHub Release'i ve D1/D2/D2b kanıtları **tarihsel olarak geçerlidir**; bu tur yalnız güncel kaynağın artifact tazeliğini düşürür.

## Bu yakalamayı yenilerken

1. `git rev-parse --short HEAD` ve upstream farkını ölç.
2. `python -m pytest tests -q` sayılarını güncelle (kaynak ve rehber dâhil ayrımını koru).
3. `python PROJECT_GUIDE/scripts/verify_project_guide.py --artifacts` ile hash'leri doğrula.
4. `last_verified_commit` / `last_verified_date` alanlarını ve `project_manifest.json` `snapshot` bölümünü güncelle.
