---
purpose: Frozen EXE ve installer doğrulama yöntemi; kanıt sınıflarının ayrımı.
read_when: Paketli sürüm veya installer doğrulaması, release öncesi.
covers:
  - packaging/TeklifYonetim.iss
  - core/restart.py
  - core/app_paths.py
  - ui/dialogs/backup_manager.py
  - main.py
last_verified_commit: 446fc78
last_verified_date: 2026-08-23
volatile: false
---

# Doğrulama rehberi

## Kanıt sınıfları — karıştırma

| Sınıf | Ne kanıtlar | Ne kanıtlamaz |
|---|---|---|
| **A. Kaynak testi** (`pytest`) | Mantık, servis, izolasyon, regresyon | Paketleme, Qt plugin çözümü, native davranış |
| **B. Paketli EXE kanıtı** (frozen smoke) | Asset/plugin çözümü, tek örnek kilidi, kapanış, restart, hata penceresi | Kurulum, kaldırma, registry, kısayol |
| **C. Installer kanıtı** | Kurulum/upgrade/kaldırma, registry, kısayol, veri koruma | Uygulama mantığı |

Bir sınıfın sonucunu diğerinin yerine yazma.

**Build sonrası provenance kapısı (R12c) bir kanıt SINIFI DEĞİLDİR.** A/B/C ile aynı tabloya yazılmaz: ayrı bir **release süreç kapısıdır**. Yalnız şunu söyler — "eldeki artifact, `built_from_commit`'ten sonra izin verilmeyen bir değişiklik olmadan hâlâ bu kaynağı temsil ediyor". Paketin gerçekten çalıştığını **kanıtlamaz**; **B ve C sınıfı kanıtın yerine geçmez** ve onları atlatmak için kullanılamaz.

> **Provenance temiz sayılmanın ön koşulu.** `built_from_commit`, build anında ölçülen gerçek HEAD ile **eşleştiği elle doğrulanmadan** provenance temiz sayılmaz. Kapı bu alanı girdi olarak kabul eder; doğruluğunu kanıtlamaz ve artifact ile commit arasında kriptografik bağ kurmaz ([RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md) 3. adım).

**Yeni build sonrası zorunlu sıra:**

1. Build başlamadan önce ölçülen gerçek `git rev-parse HEAD` kaydedilir.
2. Manifest `built_from_commit` bu kayıtla **eşleştirilir** (elle karşılaştırma).
3. Build'den sonra **yalnız izinli metadata/kanıt yolları** değiştirilir: `PROJECT_GUIDE/project_manifest.json`, `PROJECT_GUIDE/CURRENT_STATUS.md`, `PROJECT_GUIDE/KNOWN_RISKS.md`, `PROJECT_GUIDE/VERIFICATION_GUIDE.md`, `docs/CHANGELOG.md`. `VERIFICATION_GUIDE.md` izni yalnız gerçekleşen A/B/C sonucu ile kapsam sınırını build commit'ine bağlamak içindir; kaynak, test veya paketleme değişikliğine yetki vermez.
4. `verify_project_guide.py --release` → **exit 0**.

**A sınıfının içindeki güvenli hata regresyonları.** `test_*_safe_errors.py` dosyaları (reports, settings, backup, import + `test_csv_import_errors.py`) A sınıfına girer: izole test yardımcıları ve mock'larla çalışır; yalnız gerektiği yerlerde `TemporaryDirectory`, geçici dosya veya test veritabanı kullanılır. Gerçek kullanıcı verisine dokunmaz. Bunlar **mesaj/log/aşama sözleşmesini** kanıtlar; gerçek disk-dolu, gerçek dosya kilidi, gerçek SQLite commit hatası ve paketli davranışı **kanıtlamaz**. Geri yükleme durum makinesi (`preflight_failed` / `rolled_back` / `rollback_failed`) A sınıfında doğrulanmıştır; bundan ayrı paketli gerçek **geri yükleme → restart** zinciri exact v4.3 frozen EXE üzerinde B sınıfında doğrulanarak R6 kapatılmıştır ([KNOWN_RISKS.md](KNOWN_RISKS.md) R6).

## B — İzole frozen smoke

Ön koşul: çalışan `TeklifYonetim` süreci yok; EXE SHA256 beklenenle eşit.

İzolasyon (hepsi zorunlu): `LOCALAPPDATA`, `APPDATA`, `USERPROFILE`, `HOME`, `HOMEDRIVE`, `HOMEPATH`, `TMP`, `TEMP` → `<TEMP_ROOT>` altındaki yeni köke; `PYTHON_KEYRING_BACKEND=keyring.backends.fail.Keyring`; `HTTP_PROXY`/`HTTPS_PROXY`/`ALL_PROXY` → kullanılmayan yerel port, `NO_PROXY` boş.

Senaryolar:

1. **Başlangıç** — ana pencere açılır; DB/log/yedek klasörleri `<TEMP_ROOT>` altında oluşur; Qt plugin/schema/font hatası yok; gerçek kullanıcı yoluna yazım yok.
2. **Tek örnek kilidi** — ikinci süreç pencere açmadan 0 ile çıkar, ilki yaşar.
3. **Normal kapanış** — WM_CLOSE (terminate yok): otomatik yedek zamanlayıcısı susturulur; varsa aktif yedek bitirilir; aynı DB için paralel ikinci yedek açılmadan kapanış yedeği tam bir kez alınır; kalan worker'lar beklenir → DB kapatma → çıkış kodu 0; `0xC0000409`/QThread destroyed yok.
4. **Temel UI akışı** — müşteri, ürün, teklif, PDF; teklif numarası ile arşiv PDF adı aynı; PDF'de maliyet/kâr yok.
5. **Credential hata yolu** — fail backend ile kısa "Güvenli Depo" uyarısı; ham istisna UI'da ve logda yok; gerçek Credential Manager'a çağrı gitmez.
6. **Uzun worker ile kapanış** — DB'yi şişirip kapanış yedeğini uzat; süreç worker bitmeden teardown yapmamalı.
7. **Restart** — yardımcı süreç mutex'i tutarken EXE'yi `--restarted-from <pid>` ile başlat; sınırlı bekleme sonrası kilit alınır, komut satırında EXE yolu bir kez geçer.
8. **Hata penceresi** — geçici profile bozuk veritabanı koy; tek "… - Hata" penceresi güvenli Türkçe metinle log yolunu göstermeli, ikinci PyInstaller/traceback penceresi açılmamalı, UI'da SQLite/traceback bulunmamalı, teknik traceback uygulama logunda tam bir kez bulunmalı ve süreç **exit code 1** ile bitmeli. (Üretim artifact'ine hook **eklenmez**.)
9. **Modal / progress entegrasyonu (O16 sınıfı)** — modal diyalog ile ilerleme (`QProgressDialog`) penceresinin birleştiği akışlar. Zorunlu ölçüm: **çok sayfalı XLSX** içe aktarımında `Çalışma Sayfası Seç` penceresi açıkken
   - seçim penceresi native **`IsWindowEnabled == true`** olmalı (kullanıcı yanıtlayabilmeli),
   - `İçe Aktarma` **progress penceresi o anda hiç bulunmamalı** (soru progress'ten **önce** sorulur),
   - iptal edilirse DB'ye yazım olmamalı.
   Ölçüm Qt `isEnabled()` ile değil, **native `IsWindowEnabled`** (Win32 `EnumWindows` + `IsWindowEnabled`) ile alınır; pencere başlığı, `HWND`, owner ve açılış sırası kaydedilir.

Kapanış: yalnız bu turda açılan PID'ler yönetilir, geçici kök proje ve gerçek profil dışında olduğu doğrulanıp silinir, gerçek kullanıcı verisi parmak izi değişmemiş olmalı.

### Neden paketli kanıt zorunlu — O16 dersi

**Mock'lu, offscreen ve kaynak-modu testleri paketli modal davranışın yerine geçemez.** 2026-07-31'de O16 deseni (WindowModal `QProgressDialog` açıkken aynı parent'a `QInputDialog.getItem`) **pozitif kontrol** olarak iki kez yeniden kuruldu — hem offscreen hem gerçek Windows Qt platformunda, kaynak modunda — ve **kilitlenme üretilemedi**; seçim penceresi her iki denemede de `enabled=true` ölçüldü. Oysa O16'nın özgün kanıtı **paketli EXE** üzerinde `IsWindowEnabled == 0` olarak alınmıştı.

Sonuç: modal/progress sırası, `QInputDialog`/`QMessageBox` yerleşimi veya içe aktarma akışı değişirse kanıt **yalnız frozen EXE üzerinde** (B sınıfı, 9. senaryo) geçerlidir. Kaynak testleri sırayı korur, davranışı kanıtlamaz.

## C — Installer doğrulaması

Sıra: **işlem öncesi manifest + DB `integrity_check`** → **rollback yedeği** (kurulum dizini + kullanıcı verisi + registry export; kopya hash'leri kaynakla eşit, kopya DB `integrity_check: ok`) → upgrade → uygulama smoke → kaldırma → temiz yeniden kurulum → son kontroller.

- Setup admin manifestlidir; yükseltilmiş sihirbaz pencerelerine otomasyonla tıklanamaz. `/SILENT /LOG /NORESTART` kullanılır; UAC onayını kullanıcı verir.
- Upgrade sonrası: aynı `AppId`, kurulu EXE hash'i yeni dist EXE ile aynı, `dist` dışı artık dosya yok, kullanıcı verisi manifesti değişmemiş.
- Kaldırma sonrası: kurulum dizini, HKLM kaydı, kısayollar ve `unins000.*` kalkar; **kullanıcı verisi bit-bit korunur**.
- Yeniden kurulumda mevcut gerçek veritabanı açılır; boş DB oluşturulmaz.
- Rollback yedeği son rapordan sonra, açık izinle silinir.

## D — Canlı updater doğrulaması (yayın sonrası)

Kanıt sınıfı C'nin devamıdır ve **ancak tag + release + asset yayınlandıktan sonra** yapılabilir. Bu test geçmeden [project_manifest.json](project_manifest.json) içindeki **`updater_end_to_end_verified` `true` yapılmaz**.

Senaryo:

1. **Önceki sürüm kurulu** olsun (izole/test makinesi ya da geri dönüşü hazır kurulum).
2. Yeni **tag + GitHub Release + installer `.exe` asset'i** yayınlanmış olsun.
3. Uygulama açılır → güncelleme kontrolü yeni sürümü **görmeli** (sürüm karşılaştırması `v` önekinden etkilenmez).
4. "Güncelle" → asset **indirilir** ve kurulum `os.startfile` ile başlar; Inno çalışan uygulamayı kapatıp üzerine kurar.
5. Yeni sürüm açılır; **UI'da sürüm** (kenar çubuğu / Hakkında) ve log satırı doğrulanır.

Güvenlik koşulları:

- Tercihen **izole/test ortamı**; gerçek makinede yapılacaksa önce **kullanıcı verisi yedeği** alınır.
- İndirilen asset'in **SHA256'sı** manifest ile karşılaştırılır (read-back).
- Asset adı **tam olarak `TeklifYonetim_Setup_<tag>.exe`** olmalı; updater yalnız bu ada birebir uyan tek asset'i indirir. Adı tutmayan release'te güncelleme **hiç sunulmaz** (fail-closed) — canlı testte "güncelleme çıkmadı" belirtisi önce asset adı, `size` ve `digest` alanlarıyla açıklanır.
- API `digest` (`sha256:<64 hex>`) ve `size` alanları dolu olmalı; updater indirilen dosyanın SHA-256'sını ve bayt sayısını bunlarla karşılaştırır.
- Başarısızlıkta **eski sürüme geri dönüş** yolu hazır tutulur (rollback kopyası / önceki installer).
- Gerçek SMTP, gerçek müşteri verisi ve kurulu üretim kurulumu bu testin kapsamı dışındadır.

## Sürüm yükseltmesinde kapsam

Yeni bir sürüm için **B ve C sınıfları tekrarlanır**; hangi senaryoların atlandığı açıkça yazılır. Örnek: yalnız sürüm numarası ve doğrulanmış düzeltmeler değiştiyse B'de uzun patolojik senaryolar (büyük DB ile worker beklemesi, restart mutex beklemesi) ve C'de uninstall/reinstall tekrarlanmayabilir — bu durumda manifest `installer_test` kaydına atlanan senaryo ve hangi turda geçtiği açıkça yazılır. **v4.1 (U17) turunda hiçbir senaryo atlanmadı: upgrade, uninstall ve temiz reinstall yeniden yürütüldü.**

## D1 / D2 ayrımı — canlı updater kanıtı

Canlı updater doğrulaması **iki ayrı kanıt** üretir; biri diğerinin yerine geçmez:

| | D1 — kaynak düzeyi güven zinciri | D2 — gerçek teslimat E2E |
|---|---|---|
| Çalışan kod | **güncel U17 kaynağı** | **yayımlanmış eski paketli istemci** |
| Ağ | gerçek `releases/latest` + gerçek asset | gerçek release |
| Kanıtladığı | asset adı seçimi, URL/host allowlist, redirect host, size + SHA-256 doğrulaması, fail-closed | eski istemcinin yeni sürümü görüp indirip kurabilmesi |
| Kanıtlamadığı | paketli istemcide çalıştığı | U17 doğrulamalarının uygulandığı (eski updater bunları yapmaz) |
| Installer | **çalıştırılmaz** | çalıştırılır (UAC kullanıcı onayı) |

D2'de indirilen dosyanın hash/boyutu **bağımsız ölçülür**; eski updater bunu doğrulamaz. İkisi birlikte bile "paketli U17 E2E geçti" anlamına **gelmez** — bu ancak bir sonraki sürüm yayımlandığında, kurulu U17'li istemciden yükseltme yapılarak sınanabilir.

## Doğrulanmış son sonuçlar

Bu üç sınıfın en son sonuçları, hangi sürüm için doğrulandığı (`verified_for_version`) ve tarihleri: [CURRENT_STATUS.md](CURRENT_STATUS.md) ve [project_manifest.json](project_manifest.json). Kalan boşluklar: [KNOWN_RISKS.md](KNOWN_RISKS.md).

**A sınıfı — güncel kaynak (2026-08-27):** `1225 passed, 6 skipped, 345 subtests` temiz build kapısında yeniden ölçülecek. Güncel kaynak `17cd101d95430bcdd5a258ea2b779696b77db482`; R7 açılış bildirimi düzeltmesine iki durumlu Güvenli Depo test ekranı ve dış PATH/tırnaklı Python komutu regresyonları eklendi. Preview kataloğu 44 yüzey/188 durumdur; smoke ve geometri bulgusu 0, gerçek credential erişimi 0.

**A→B/C boşluğu:** Yayımlanmış v4.3 artifact `446fc78` kaynaklıdır ve R7 değişikliklerini içermez. Ara `9c7c46b` ile Codex runtime DLL'leri bulaşmış `24e1521` buildleri proje dışındaki geçici kanıt klasörlerine alındı; güncel kaynak için kanıt sayılmaz. Kontrollü PATH ile yeni temiz build sonrasında fail-keyring izolasyonunda splash sırasında modal olmadığını, ana pencere görünürken uyarının yalnız bir kez çıktığını ve normal kapanışı doğrulayan frozen UI smoke gerekir. Bu yapılmadan `17cd101` için B veya C kanıtı iddia edilmez.

**B sınıfı — v4.3 için değişiklik-etkili hedefli smoke + R6 GEÇTİ.** `446fc78` girdisinden üretilen exact dist EXE (`C037CB3A…F0ED9AD`) izole profil + null keyring + loopback proxy ile görünür v4.3 arayüzünü açtı; log `Version: v4.3`, izole DB `integrity_check=ok/fk=0`. Dist EXE ile byte-eşit kurulu EXE upgrade ve temiz reinstall sonrasında iki ayrı smoke'ta daha açıldı. Üçü de dış Windows otomasyonuyla Alt+F4, kapanış yedeği, DB close ve exit 0 ile normal kapandı. Ayrı R6 turunda exact dist EXE’ye paketli UI’dan sentetik yedek gerçekten geri yüklendi; DB hedef durumu ve bütünlüğü doğrulandı; ilk süreç restart kapanışında yedek atlama + DB close + exit 0 verdi; ardıl süreç tek `--restarted-from <pid>` ile otomatik açıldı; ardıl normal kapanış exit 0 ve süreç sızıntısı 0 oldu. Gerçek profil envanteri `0/0/0` farkla korundu. Bu kayıt **tam B-1..B-9 turu değildir**; eklenen kesin kapsam B-7’nin gerçek geri yükleme ile birleşen R6 zinciridir.

**C sınıfı — v4.3 için TAM GEÇTİ.** Exact `TeklifYonetim_Setup_v4.3.exe` (`51.289.869 B / 7D7516BC…94B8EE`) ile önceki v4.3→yeni v4.3 upgrade, kurulu smoke, uninstall, temiz reinstall ve ikinci kurulu smoke tamamlandı. Üç installer/uninstaller işlemi exit 0 ve restart yok; kurulu EXE dist ile byte-eşit, kurulum ağacı dist ile `0/0/0`, registry/AppId/dört kısayol doğru. Kullanıcıya ait özel kısayol kaldırmada korundu. Başlangıçtaki gerçek veri 32/32 ve yedekler 13/13 bütün zincirde byte/hash değişmedi; DB `integrity_check=ok`, `foreign_key_check` temiz. Salt-okunur bütünlük probunun oluşturduğu boş WAL/SHM installer değişikliği sayılmadı. Üç UAC onayı kullanıcı tarafından elle verildi. Bu C kanıtı v4.3 tag/release veya canlı updater D1/D2 kanıtı değildir.
