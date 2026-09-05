---
purpose: Projenin son doğrulanmış durumu — tarihli yakalama. Tarihçe için AUDIT_HISTORY.
read_when: Genel yönelim, build/release öncesi, uzun aradan sonra.
covers:
  - core/constants.py
last_verified_commit: 649575e
last_verified_date: 2026-09-05
volatile: true
---

# Son doğrulanmış durum

> **Yakalama tarihi: 2026-09-05 · hedef sürüm: `v4.5` — TEMİZ BUILD + HEDEFLİ FROZEN B + TAM INSTALLER C GEÇTİ; YAYIN BEKLİYOR.**
> Public/latest sürüm hâlâ **v4.4**'tür. v4.4 artifact ve yayın kanıtları tarihsel olarak geçerlidir; v4.5 için kullanılamaz.
> Bu belge canlı durum iddiasında bulunmaz. **Canlı git durumu snapshot'tan okunmaz; `git status`, `git rev-parse HEAD` ve upstream karşılaştırmasıyla yeniden ölçülür.** Makine-okunur karşılığı: [project_manifest.json](project_manifest.json).

## Sürüm ve kaynak

- Hedef sürüm: **v4.5** — `core/constants.py`, Inno `.iss`, `version_info.txt` ve `TeklifYonetim_Setup_v4.5.exe` eşleşiyor. İşlevsel kaynak `efcfdcb`; exact kanıt commit'i `649575efd0b905ce84e3a055bc958aa4d32d30eb` girdisinden temiz build, hedefli frozen B ve tam installer C geçti; tag/Release/D1/D2 yapılmadı.
- **v4.5 kaynak ve build:** teklif/PDF yolu, para birimi raporları, import miktarı, spreadsheet formül koruması, kalem tutarı/geçerlilik doğrulaması ve güncellemede normal kapanış → DB kapanışı → installer sırası kaynak testleriyle kapatıldı. `packaging/Kurulum-Yap.bat --no-pause` exit `0`; build kapısı **1242 passed, 6 skipped, 360 subtests**; PyInstaller 6.19.0 onedir ve Inno Setup 7.1.0 tamamlandı.
- **v4.5 artifact:** EXE `9.725.826 B / 3292F3CBAC7D…5E37F / FileVersion 4.5.0.0 / ProductVersion v4.5`; dist ağacı `256 dosya / 168.681.030 B`. Installer `TeklifYonetim_Setup_v4.5.exe / 50.882.931 B / 400AD27F58E1…AB21AF / 4.5.0.0`.
- **Hedefli frozen B GEÇTİ:** null ve fail-keyring için iki ayrı izole profil; null turunda modal `0`, ikinci örnek exit `0` ve ilk süreç yaşadı. Fail turunda tek `Güvenli Depo` modalı, ana pencere native disabled ve modal enabled; kabul sonrası ana pencere enabled. İki turda normal `WM_CLOSE`, tek kapanış yedeği, DB close, exit `0`, `integrity_check=ok`, FK `0`, yasaklı crash işareti `0`, süreç sızıntısı `0`. Gerçek profil veri/yedek manifestleri değişmedi. Kapsam B-1/B-2/B-3/B-5'tir; installer çalıştırılmadı.
- **Tam installer C GEÇTİ:** önceki kurulu v4.5 → exact `649575e` v4.5 yerinde upgrade, iki profilli kurulu smoke, uninstall, temiz reinstall ve ikinci iki profilli kurulu smoke tamamlandı. Upgrade/reinstall ağaçları dist ile `256/256`, eksik/fazla/değişen `0/0/0`; üç yükseltilmiş işlem exit `0`, restart yok. Uninstall sonrası program klasörü, registry ve üç yönetilen kısayol kalktı; özel AIO kısayolu korundu; reinstall sonunda registry `v4.5`, üç yönetilen kısayol ve exact dist EXE geri geldi. Gerçek veri rollback manifestiyle `31/31`, fark `0/0/0`; ana DB `312C189C…9D0CE`, `integrity_check=ok`, FK `0`. İki kurulu smoke toplam `44/44` kontrolle geçti ve gerçek Credential Manager kullanılmadı.
- **v4.4 build öncesi arşivi:** `<RELEASE_ARCHIVE>/v4.4-pre-v4.5-build-20260905`; dist `256 dosya / 168.723.695 B`, EXE `ACABD2DE…53FF8`, installer `4D074FB0…B5FC1`. Kaynak/arşiv sayısı, toplam bayt ve iki ana hash eşit doğrulandı.
- **Yerel release teknik kapıları hazır:** dört untracked öğe proje dışındaki `<USER_DOCUMENTS>/OfferManagementSystem/workspace_hold/pre-v45-release-20260905` klasörüne hash manifestiyle taşındı. Exact `649575e` build + hedefli B + tam C tamamlandı ve `release_candidate_ready=true`. Push, tag, GitHub Release ve yayın sonrası D1/D2 ayrı kapılardır; henüz yapılmadı.
- **Doğrulama durumu — v4.2 artifact'ı için (TARİHSEL, `227656b`):** temiz build, frozen smoke (**B**), installer (**C**), R12a Yol A+B, yayın ve canlı updater (**D1+D2**) **TAMAMLANDI**. Bu kanıtlar geçerliliğini korur.
- **v4.4 güncel durum:** `35f23ac` exact HEAD'inden temiz v4.4 EXE ve installer üretildi; `1225 passed, 6 skipped, 346 subtests`, değişiklik-etkili frozen B ve tam installer C geçti. Anotasyonlu `v4.4` tag exact build commit’ini gösteriyor; public/latest Release ve tek asset read-back temiz; canlı D1 ve paketli v4.3 → v4.4 D2 geçti.
- v4.3 dist EXE: `C037CB3AEF6F…F0ED9AD` (9.722.873 B, FileVersion `4.3.0.0`, ProductVersion `v4.3`) · installer: `TeklifYonetim_Setup_v4.3.exe` `7D7516BC2746…94B8EE` (51.289.869 B). Public v4.2 artifact kimlikleri tarihsel kayıtlarda korunur.
- **Makinede kurulu sürüm v4.5** — exact `400AD27F…AB21AF` installer ile tam C zincirinin temiz yeniden kurulum sonu. Kurulu EXE `3292F3CB…5E37F` dist ile byte-birebir aynı; registry `DisplayVersion v4.5`, aynı AppId ve kurulum yolu doğrulandı. Ana DB hash'i `312C189C…9D0CE` olarak rollback snapshotıyla aynı; DB `integrity_check=ok`, `foreign_key_check` temiz.
- **Doğrulanmış v4.1 artifact arşivi** proje kökünün dışında korunuyor: `<RELEASE_ARCHIVE>/v4.1-published-before-v4.2` (298 dosya, 229.136.053 bayt; dist EXE `872DF3C1…`, installer `DE590641…`). `packaging/Kurulum-Yap.bat` build başında `dist/`, `build/` ve `installer_output/` klasörlerini sildiği için bu kopya **zorunludur**.
- **Paket içeriği — kabul edilmiş ürün kararı:** `_internal/assets/company.cfg` (firma adı, adres, telefon, e-posta, teklif öneki, PDF varsayılan metinleri) ve `assets/logo.png` pakete **bilinçli olarak** dahildir; ürün belirli bir firma için hazırlanmıştır. Paket içinde **SMTP parolası, credential veya token yoktur**. Kullanıcı bu bilgilerin public GitHub installer'ında bulunmasını **kabul etmiştir (2026-08-02)**. `core/config.py` varsayımları, `assets/company.cfg`, `assets/logo.png` ve `packaging/TeklifYonetim.spec` asset kapsamı **değiştirilmez**. → KNOWN_RISKS R12b (kapalı)
- Kaynak davranışı baseline sonucu (PROJECT_GUIDE testleri hariç): **648 passed, 29 subtests** (`060baf3`)
- **Güncel kanıt ve build girdisi: `649575efd0b905ce84e3a055bc958aa4d32d30eb`; işlevsel kaynak: `efcfdcb214c169da96e2a92af289f90cbb04e3d3`.** Build öncesi canlı HEAD exact `649575e` ile eşleşti. Birincil v4.5 artifact kaydı bu commit'e bağlandı; v4.4 ve önceki v4.5 artifact kanıtları tarihsel bağlamda korunur.
- Exact `35f23ac` temiz build kapısı: **1225 passed, 6 skipped, 346 subtests**. Altıncı skip, build başında `release_candidate_ready=false` olan fail-closed manifest aday kontrolüdür.
- **R7 yerel paketli kanıt: GEÇTİ.** EXE `67EC8958…CE20F4E` (9.723.436 B), 256 dosya / 168.723.696 B paket ağacı; fail-keyring turunda gerçek ana pencere 3,193 sn, Güvenli Depo 3,700 sn, tek modal, ana pencere disabled, otomatik Tamam, WM_CLOSE, exit 0, süreç/log sızıntısı 0. Null-keyring turu da uyarı 0 ve normal kapanış exit 0 verdi. Gerçek veri/yedek envanteri değişmedi.
- Tarihsel bağlam: `c3f711e` turunda ölçülen tam paket **1152 passed, 4 skipped, 343 subtests** idi; güncel sonuç değildir.
- v4.2 **build anındaki** kapı sonucu ayrı ve tarihsel bir alandır: manifest `build_gate_test_result` (`227656b`) — aşağıdaki "v4.2 Aşama 1 doğrulaması" bölümünde.
- `py_compile` tüm proje dosyalarında temiz
- Upstream durumu **her release öncesi canlı git komutlarıyla** doğrulanır; bu belgede canlı remote hash tutulmaz

## 2026-09-05 exact `649575e` build + hedefli B + tam C — GEÇTİ

- Build öncesi canlı HEAD `649575efd0b905ce84e3a055bc958aa4d32d30eb` idi ve `git status --short` çıktı vermedi. `packaging/Kurulum-Yap.bat --no-pause` exit `0`; tam test kapısı **1242 passed, 6 skipped, 360 subtests**; PyInstaller 6.19.0 onedir ve Inno Setup 7 tamamlandı.
- EXE `9.725.826 B / 3292F3CBAC7D…5E37F / 4.5.0.0 / v4.5`; dist `256 dosya / 168.681.030 B`. Installer `50.882.931 B / 400AD27F58E1…AB21AF / 4.5.0.0`.
- Local-only paketleme/asset girdilerinin altı SHA-256 değeri önceki kayıtla aynı kaldı; kaynak çalışma ağacı build ve doğrulama boyunca temizdi.
- **Hedefli Frozen B 22/22:** null/fail-keyring izole profilleri, gerçek ana pencereyi splash'ten `1316×839` boyutuyla ayırdı; tek örnek, modal native etkinliği, normal `WM_CLOSE`, tek kapanış yedeği, DB close, `integrity_check=ok`, FK `0`, yasaklı crash işareti `0`, süreç sızıntısı `0`. Kapsam B-1/B-2/B-3/B-5; B-4/B-6/B-7/B-8/B-9 tekrarlanmadı. Kanıt SHA-256 `14136926E26E8A21BF5B7849F57C9B7BBE079E88CC5114AB705C38E35834415C`.
- **Tam Installer C:** önceki kurulu v4.5 → exact `649575e` v4.5 upgrade → iki profilli kurulu smoke → uninstall → temiz reinstall → ikinci iki profilli smoke. Üç yükseltilmiş işlem exit `0`, restart yok; kurulu smoke toplam **44/44**.
- Upgrade ve reinstall ağaçları dist ile `256/256`, fark `0/0/0`; uninstall program/registry/üç yönetilen kısayolu kaldırdı, özel AIO kısayolunu korudu; reinstall registry v4.5 ve üç yönetilen kısayolu geri getirdi.
- Gerçek veri bütün zincirde `31/31`, fark `0/0/0`; ana DB `312C189C…C9D0CE`, `integrity_check=ok`, FK `0`. Rollback: `<USER_DOCUMENTS>/OfferManagementSystem/rollback/v45-before-exact-v45-20260905-150545`.
- Installer log SHA-256: upgrade `CC9D5DEF…F749F`, uninstall `64BC6967…7E1F7`, reinstall `3C7B2D23…C18D8`. Birleşik C kanıtı `B05989145DEC878EDCE57CBE4CC0D188864D72F1BBAA9ED73D6AE2282511D8DA`.
- **Kapsam sınırı:** yerel build/B/C ve veri koruma kanıtıdır. Push, tag, GitHub Release ve canlı updater D1/D2 yapılmadı.

## 2026-08-27 exact release-belge commit build + hedefli B + tam C — GEÇTİ

- Build girdisi: `35f23ac2762ef46c183f60baee539b9033310f1e`; `packaging/Kurulum-Yap.bat --no-pause` exit `0`. Tam test kapısı **1225 passed, 6 skipped, 346 subtests**; temiz PyInstaller 6.19.0 onedir + Inno Setup 7 tamamlandı.
- v4.4 EXE: `9.723.435 B / ACABD2DE0EC4…53FF8 / FileVersion 4.4.0.0 / ProductVersion v4.4`; dist ağacı `256 dosya / 168.723.695 B`.
- v4.4 installer: `TeklifYonetim_Setup_v4.4.exe / 50.889.592 B / 4D074FB0A8AA…B5FC1 / 4.4.0.0`.
- Yerel paketleme girdileri ayrıca ölçüldü: `.spec 253D6A6D…734B67`, `.iss 72EAADE4…B8945`, `version_info C9EC6A5E…6B74E9`, build BAT `32B55D5D…90A1F`; yeni dist'te hedeflenen eski DLL sayısı `0`.
- **Hedefli B GEÇTİ:** exact `ACABD2DE…53FF8` EXE null-keyring turunda modal `0`, ikinci örnek exit `0` ve ilk süreç yaşadı. Fail-keyring turunda tek “Güvenli Depo” modalı, ana pencere native disabled, modal enabled. İki tur WM_CLOSE, tek kapanış yedeği, DB close, exit `0`; iki izole DB `integrity_check=ok`, FK `0`; forbidden marker ve süreç sızıntısı `0`.
- **Tam installer C GEÇTİ:** mevcut v4.4 → düzeltilmiş exact v4.4 upgrade, ilk kurulu smoke, uninstall, veri koruması, temiz reinstall ve ikinci kurulu smoke tamamlandı. Upgrade ve reinstall ağaçları dist ile `256/256`, eksik/fazla/değişen `0/0/0`; eski 39 API-set DLL + `ucrtbase.dll` artık `0`.
- Rollback: `<USER_DOCUMENTS>/OMS-v44-C-Rollback-20260827-0d9b6c2-20260827-104943`; snapshot anında kurulum `258/258`, veri `32/32`, yedek `16/16`, kopya farkı `0/0/0`; registry ve dört kısayol kopyası; kopya DB `integrity_check=ok`, FK `0`.
- Üç yükseltilmiş işlem exit `0`, restart yok. Kaldırmada kurulum klasörü/registry/üç installer kısayolu kalktı, özel `AIO` kısayolu korundu; reinstall sonunda registry v4.4 ve dört kısayol hedefi doğru.
- Ana DB `312C189C…9D0CE` rollback snapshotıyla aynı kaldı. Salt-okunur DB probunun oluşturduğu `database.db-wal` (`0 B`) ve `database.db-shm` (`32.768 B`) installer değişikliği sayılmadı; ardından veri `32/32`, yedek `16/16` hashleri uninstall/reinstall ve kurulu smoke'larda korundu.
- Upgrade ve reinstall sonrası toplam dört izole kurulu smoke null/fail-keyring ile geçti; Computer Use ve gerçek Credential Manager kullanılmadı. **Kapsam sınırı:** B-1/B-2/B-3/B-5 doğrulandı; B-4/B-6/B-7/B-8/B-9 tekrarlanmadı.

## 2026-08-27 v4.4 public yayın + canlı updater — GEÇTİ

- Anotasyonlu `v4.4` tag peeled hedefi exact build commit `35f23ac2762ef46c183f60baee539b9033310f1e`; kanıt commit’ine taşınmadı.
- Public/latest Release: <https://github.com/IzzmooPro/OfferManager/releases/tag/v4.4> · `draft=false`, `prerelease=false` · yayın `2026-08-27T07:57:12Z`.
- Tek asset `TeklifYonetim_Setup_v4.4.exe`: `50.889.592 B`, GitHub digest ve bağımsız yeniden indirme SHA-256 `4D074FB0…B5FC1`; yerel installer ile byte-eşit.
- **D1 GEÇTİ:** gerçek `releases/latest` HTTP 200 ile v4.4’ü döndürdü; üretim asset seçimi tam adı, boyutu ve SHA-256’yı doğruladı. Eksik digest, yanlış ad, sıfır boyut ve çift aynı-ad senaryoları fail-closed kaldı; installer çalıştırılmadı.
- **D2 GEÇTİ:** exact public v4.3 istemci (`C037CB3A…F0ED9AD`) canlı v4.4’ü gördü; görünür güncelleme modalı dış Win32 otomasyonuyla tıklandı. İndirilen dosya `50.889.592 B / 4D074FB0…B5FC1`; logda “Yeni sürüm indirildi” ve “Kurulum başlatıldı” görüldü. Final kurulu EXE `ACABD2DE…53FF8 / v4.4`, registry v4.4; görünür final smoke normal kapanış, DB close ve exit 0 verdi.
- Ana DB `312C189C…9D0CE` rollback ile byte-eşit, `integrity_check=ok`, FK 0. Normal gerçek-profil runtime farkı yalnız log/`backup_meta.json` ve bir yeni kapanış yedeğidir (`16 → 17`). Süreç sızıntısı `0`.

## 2026-08-27 v4.4 installer C ilk denemesi — TARİHSEL KIRMIZI / DURDURULDU

- Doğrulanmış rollback: `<ROLLBACK_ROOT>/OMS-v44-C-Rollback-20260827-8fe66bd`; kurulum `298/298`, veri `34/34`, yedek `15/15`, kopya farkı `0/0/0`; rollback DB `integrity_check=ok`, FK `0`; registry ve dört kısayol kopyası mevcut.
- v4.3 → exact v4.4 installer upgrade exit `0`; Inno `Installation process succeeded`, restart yok. Kurulu EXE `9.723.435 B / 82630D4B…D809FA86 / v4.4`, dist ile byte-eşit; registry/AppId ve kısayollar v4.4.
- **Kırmızı kapı:** dist `256`, kurulu ağaç uninstaller hariç `296`; eksik `0`, değişen `0`, **fazla `40`**. Fazlalar v4.3 rollback ağacında bulunan fakat v4.4 dist'te bulunmayan `_internal\api-ms-win-*.dll` ailesi ve `_internal\ucrtbase.dll`.
- Protokol gereği kurulu smoke, uninstall ve temiz reinstall yapılmadı. Gerçek veri/yedek rollback manifestine göre `0/0/0`; DB `integrity_check=ok`, FK `0`; süreç `0`. Salt-okunur bütünlük probunun oluşturduğu boş WAL/SHM installer değişikliği sayılmaz.
- Kök neden: izlenen ISS `[InstallDelete]` yalnız iki eski OpenSSL DLL'ini kapsıyordu. Kırmızı regresyon testi eklendi; minimum düzeltme yalnız `{app}\_internal\api-ms-win-*.dll` ve exact `{app}\_internal\ucrtbase.dll` temizliğini ekledi. Hedefli paketleme testleri `52 passed, 5 skipped, 3 subtests`; tam paket `1226 passed, 5 skipped, 346 subtests`. Bu ilk kırmızı kanıt silinmedi; düzeltme sonrası `0d9b6c2` build+B+tam C yukarıdaki güncel bölümde geçti.

## 2026-08-23 v4.3 build + frozen/kurulu smoke + tam C doğrulaması

- Build girdisi: `446fc78`; `packaging/Kurulum-Yap.bat --no-pause` exit 0. Tam test kapısı **1222 passed, 6 skipped, 345 subtests**; temiz PyInstaller onedir + Inno Setup 7.1.0 tamamlandı.
- v4.3 EXE: `9.722.873 B / C037CB3AEF6F…F0ED9AD / FileVersion 4.3.0.0 / ProductVersion v4.3`; dist ağacı `296 dosya / 170.329.053 B`.
- v4.3 installer: `51.289.869 B / 7D7516BC2746…94B8EE`; izlenen `.iss` `ABD6CB536816…41422`, `version_info.txt` `70C01FB7F7A…8044`. Build ve paket içerik denetimleri temiz.
- GitHub Release önce taslakta, ardından public/latest durumda read-back edildi: <https://github.com/IzzmooPro/OfferManager/releases/tag/v4.3> · Release ID `375288316` · yayın `2026-08-23T18:30:40Z` · `draft=false`, `prerelease=false`, `latest=true`. Tek asset `TeklifYonetim_Setup_v4.3.exe`, `51.289.869 B`, `state=uploaded`, GitHub digest `sha256:7d7516bc…94b8ee`; public URL'den bağımsız yeniden indirme yerel installer ile byte-eşit. `--clobber` kullanılmadı.
- **D1 — kaynak düzeyi canlı güven zinciri: GEÇTİ.** Gerçek `releases/latest` HTTP 200 ile v4.3'ü (`draft=false`, `prerelease=false`, tek asset) döndürdü. Üretim `select_update_asset` yardımcısı tam adı seçti; başlangıç hostu `github.com`, redirect son hostu `release-assets.githubusercontent.com` allowlist içindeydi. API size = `Content-Length` = yazılan bayt = **51.289.869**; API digest = indirilen dosya = yerel installer SHA-256 `7D7516BC…94B8EE`. `download_finished=1`, `failed=0`; digest yok / yanlış ad / size=0 / aynı ad iki kez senaryolarının dördü de fail-closed. `os.startfile` / `os._exit` / `webbrowser` çağrısı 0; installer çalıştırılmadı ve geçici indirme ölçümden sonra kaldırıldı.
- **D2 — exact paketli v4.2 → canlı v4.3 gerçek teslimat: GEÇTİ.** Doğrulanmış public v4.2 installer’ı (`52.548.738 B / D61488DF…82B2`) ile temiz exact v4.2 istemci kuruldu (`9.476.704 B / 47601526…5353B`, kurulum ağacı `297/297`, fark 0). Paketli istemci logda `Güncelleme mevcut: v4.3` yazdı; görünür modal `Mevcut sürüm: v4.2 / Yeni sürüm: v4.3` gösterdi. “Güncelle” dış Windows otomasyonuyla tıklandı; indirilen installer bağımsız ölçümde `51.289.869 B / 7D7516BC…94B8EE` ve public/yerel artifact ile eşitti. Final kurulu EXE `9.722.873 B / C037CB3A…F0ED9AD / v4.3`, registry v4.3 ve kurulum ağacı dist ile fark 0. Görünür v4.3 smoke normal Alt+F4, kapanış yedeği, DB close ve exit 0 ile kapandı.
- **D2 veri kanıtı:** `database.db` `1.921.024 B / 312C189C…9D0CE` olarak byte/hash değişmedi; `integrity_check=ok`, FK satırı 0. Normal runtime farkları yalnız büyüyen uygulama logu, güncellenen `backup_meta.json` ve tek yeni kapanış yedeğidir; özel `AIO\Teklif Yönetim.lnk` korundu. D2 rollback ve indirilen exact installer: `<ROLLBACK_ROOT>/OMS-v43-D2-Rollback-20260823-07742d3`; silinmeyecek. Credential Manager çağrı sayısı bu gerçek profil turunda ölçülmedi; sıfır iddiası yapılmaz.
- **R6 — paketli gerçek geri yükleme → restart: GEÇTİ/KAPANDI.** Exact dist EXE (`C037CB3A…F0ED9AD`) sekiz profil/temp değişkeni izole köke yönlendirilerek, fail keyring ve loopback proxy ile çalıştırıldı. Canlı sentetik DB önce `R6_PRE_RESTORE_CURRENT` içerirken paketli UI’dan seçilen yedek yalnız `R6_BACKUP_TARGET` içeriyordu; geri yükleme sonrası eski kayıt yok oldu, hedef kayıt geldi, `integrity_check=ok` ve FK satırı 0 kaldı. İlk PID `28084` restart kapanışında yeni kapanış yedeğini doğru biçimde atladı, DB’yi kapattı ve exit 0 verdi; ardıl PID `47344` tam bir `--restarted-from 28084` ile otomatik açıldı. Ardıl normal kapanışta tek kapanış yedeği, DB close ve exit 0 görüldü; iki PID de bitti, süreç sızıntısı 0. Gerçek profil envanteri **46 → 46; eklenen 0, silinen 0, değişen 0**. Gerçek kullanıcı yedeği kullanılmadı; `%TEMP%\OMS-R6-v43-20260823-222337` laboratuvarı kanıtlar kaydedilip push edildikten sonra açık kullanıcı onayıyla kalıcı olarak silindi.
- Dört UAC onayı ve yükseltilmiş v4.3 installer sihirbazı kullanıcı tarafından elle tamamlandı; UAC/yükseltilmiş pencere otomatikleştirilmedi.
- Manifestteki `tag_created`, `github_release_created`, `updater_end_to_end_verified` alanları tamamlanan **public yayın + D1 + D2 setini** birlikte temsil eder ve üçü de `true`dur.
- **Frozen/kurulu smoke: GEÇTİ, kapsam sınırı kayıtlı.** Exact dist EXE izole profil + null keyring + loopback proxy ile görünür `v4.3` arayüzünü açtı; log `Version: v4.3`, DB `integrity_check=ok/fk=0`. Dist, upgrade-kurulu ve temiz-kurulu EXE olmak üzere üç smoke da Alt+F4, kapanış yedeği, DB close ve exit 0 ile normal kapandı. Tam B-1..B-9 matrisi yeniden koşulmadı.
- **Installer C: TAM GEÇTİ.** Önceki v4.3 (`BDEE8AA1…`) → yeni exact v4.3 (`C037CB3A…`) yerinde upgrade, ilk kurulu smoke, uninstall, temiz reinstall ve ikinci kurulu smoke tamamlandı. Her installer/uninstaller exit 0 ve restart yok; kurulum ağacı dist ile birebir (eksik 0, fazla 0, değişen 0; `unins000.*` hariç), eski hedefli DLL'ler yok. Ayrı önceki turda v4.2→v4.3 upgrade de geçmişti; iki kanıt birbirine karıştırılmaz.
- Uninstall sonrasında Program Files dizini, uninstall registry kaydı ve installer-yönetimli kısayollar kalktı. Kullanıcının özel `AIO\Teklif Yönetim.lnk` kısayoluna dokunulmadı. Temiz reinstall sonunda registry v4.3, AppId, kurulum yolu ve üç installer kısayolu geri geldi.
- Başlangıçtaki gerçek veri 32/32 ve yedekler 13/13 tüm zincirde değişmedi; DB `integrity_check=ok`, `foreign_key_check` temiz. Kaldırma-sonrası salt-okunur bütünlük probu boş `database.db-wal` ve `database.db-shm` oluşturdu; ana DB değişmedi ve bunlar installer'a atfedilmedi. Rollback: `<ROLLBACK_ROOT>/OMS-v43-Rollback-20260823-446fc78`; silinmeyecek.
- Upgrade, uninstall ve temiz reinstall için üç UAC kullanıcı tarafından elle onaylandı; UAC otomatikleştirilmedi.
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

Açık kalan ürün davranışı maddeleri:

- **R6 — KAPANDI (2026-08-23):** exact v4.3 paketli EXE’de izole sentetik yedekten gerçek geri yükleme, normal restart kapanışı, tek `--restarted-from` ardılı, geri yüklenmiş DB bütünlüğü, ardıl normal kapanış ve süreç sızıntısı birlikte doğrulandı.
- **R8 — AÇIK, ürün sahibinin kararıyla ERTELENDİ (2026-08-14):** "Tümünü İçe Aktar" gizli sayfa politikası. Kapatılmış veya çözülmüş değildir; mevcut davranış bilinçli olarak korunur ve sonraki UI/tasarım turunun zorunlu kapsamına alınmaz.

Diğer maddelerin durumu bu turda değişmedi — güncel liste [KNOWN_RISKS.md](KNOWN_RISKS.md).

## R12c — build sonrası provenance kapısı (2026-08-08) — **KAPANDI**

- Kök neden: artifact `227656b`'den build edilmişti; sonrasında kaynak ve test dosyaları değiştiği hâlde `--release` **exit 0** veriyordu.
- Yeni `kontrol_build_sonrasi_provenance` kapısı build sonrasında YALNIZ dört **tam** yola izin verir: `PROJECT_GUIDE/project_manifest.json`, `PROJECT_GUIDE/CURRENT_STATUS.md`, `PROJECT_GUIDE/KNOWN_RISKS.md`, `docs/CHANGELOG.md`. Klasör/prefix izni yoktur.
- Commit edilmiş, staged, unstaged ve untracked/non-ignored yasak yollar birlikte denetlenir (add/modify/delete/rename). Eksik/bozuk `built_from_commit`, Git okunamaması ve build commit'inin HEAD'in atası olmaması **fail-closed**. Kontrol yalnız `--release` modunda zorunludur.
- Kanıt: kırmızı **23 failed / 1 passed** → provenance testleri **24 geçti**; `test_project_guide` **98 geçti / 7 subtest**; `test_project_guide + test_version_consistency` **148 geçti / 4 atlandı / 9 subtest**; tam paket **1152 passed, 4 skipped, 343 subtests**. Tam paket ölçümü `c3f711e`'ye giren aynı kaynak/test içeriğiyle **commit'ten önce** yapıldı; commit sonrasında yeniden çalıştırılmadı. `py_compile` ve `git diff --check` temiz.
- Gerçek depo modları bu exact artifact kanıtı işlendiğinde: normal **exit 0**, `--stale` **exit 0 / 0 uyarı**, `--artifacts` **exit 0 / 0 uyarı**, `--release` **exit 0 / 0 uyarı**. Bu yalnız teknik aday kapısıdır; push/tag/GitHub Release/D1/D2 için ayrı açık onay gerekir.

> **Kanıt sınırı — silinmemeli.** Kapı yalnız **Git'in görebildiği** provenance'ı kanıtlar; gitignore/local-only `packaging/` ve `assets/` girdilerinin geçmişini kanıtlamaz. `built_from_commit` kapının **güvendiği** girdidir ve artifact ile commit arasında kriptografik bağ yoktur — gerçek build loguyla eşleşmesi release incelemesinde **ayrıca** doğrulanmalıdır.

## Açılış bildirimi ertelemesi (2026-08-14, `0a1a1ae`)

Süresi dolan teklif modalı, `MainWindow` oluşturulurken (`_navigate(0)` → `on_enter`) açıldığı için **splash ekranının üzerinde** beliriyordu.

- Dashboard verisi açılışta **yüklenmeye devam eder**; yalnız bildirimler ertelenir.
- Splash fade'in gerçek `finished` sinyali → `acilis_bildirimlerini_planla()` → pencereye ait tek atımlık zamanlayıcı → bir sonraki event-loop turunda gösterim. **Sabit gecikme yok.**
- Gösterim **idempotenttir**; pencere görünür değilse veya kapanış hazırlığı başladıysa modal açılmaz.
- Onay/ret sözleşmesi değişmedi: "Şimdilik Dokunma" / Esc / X hiçbir yazma yapmaz.
- Kanıt sınıfı: **kaynak testi + kaynak-modu Windows Qt smoke**. → `tests/test_expired_offer_prompt.py`, [CRITICAL_INVARIANTS.md](CRITICAL_INVARIANTS.md) 7b

## Bu yakalamadaki artifact durumu

- Güncel v4.4 `source_commit = built_from_commit = 35f23ac2762ef46c183f60baee539b9033310f1e`; public v4.3 `built_from_commit = 446fc780131dd77a8a4dcf630f8baa8287b367dd`; R7 yerel aday build girdisi `270e2223c90b6c889f757f1e53c523dd5bb74c12` olarak tarihsel kayıtta korunur.
- Proje kökünde exact v4.4 `build/`, `dist/` ve `installer_output/` çıktıları bulunur. Kimlikleri birincil `dist_exe`/`installer` alanlarında ve `current_source_validation_build` altında kayıtlıdır.
- `446fc78` public v4.3 artifact'ı için B/C/release/D1/D2 kanıtı tarihsel olarak geçerlidir. Exact `35f23ac` v4.4 artifact seti temiz build, hedefli B ve tam C geçti. Artifact `verified`, yerel release adayı hazır; tag/Release/D1/D2 henüz yapılmadı.
- **Yayımlanmış v4.2 artifact'ı tarihsel olarak geçerlidir** ve proje kökünün dışındaki doğrulanmış arşivde korunur: `<RELEASE_ARCHIVE>/v4.2-published-before-ui-redesign` — **299 dosya, 229.266.985 bayt**; dist EXE `476015268A26…5353B`, installer `D61488DFE55D…82B2`. Bu kopya **tarihsel** bir kayıttır; güncel kaynağın artifact'ı **değildir**.
- v4.2 ve v4.3 tag/Release/updater kanıtları **tarihsel olarak geçerlidir**; v4.4 için tag, Release veya updater kanıtı değildir.

## Bu yakalamayı yenilerken

1. `git rev-parse --short HEAD` ve upstream farkını ölç.
2. `python -m pytest tests -q` sayılarını güncelle (kaynak ve rehber dâhil ayrımını koru).
3. `python PROJECT_GUIDE/scripts/verify_project_guide.py --artifacts` ile hash'leri doğrula.
4. `last_verified_commit` / `last_verified_date` alanlarını ve `project_manifest.json` `snapshot` bölümünü güncelle.
