---
purpose: Frozen EXE ve installer doğrulama yöntemi; kanıt sınıflarının ayrımı.
read_when: Paketli sürüm veya installer doğrulaması, release öncesi.
covers:
  - packaging/TeklifYonetim.iss
  - core/restart.py
  - core/app_paths.py
  - ui/dialogs/backup_manager.py
last_verified_commit: 7395561
last_verified_date: 2026-07-31
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

## B — İzole frozen smoke

Ön koşul: çalışan `TeklifYonetim` süreci yok; EXE SHA256 beklenenle eşit.

İzolasyon (hepsi zorunlu): `LOCALAPPDATA`, `APPDATA`, `USERPROFILE`, `HOME`, `HOMEDRIVE`, `HOMEPATH`, `TMP`, `TEMP` → `<TEMP_ROOT>` altındaki yeni köke; `PYTHON_KEYRING_BACKEND=keyring.backends.fail.Keyring`; `HTTP_PROXY`/`HTTPS_PROXY`/`ALL_PROXY` → kullanılmayan yerel port, `NO_PROXY` boş.

Senaryolar:

1. **Başlangıç** — ana pencere açılır; DB/log/yedek klasörleri `<TEMP_ROOT>` altında oluşur; Qt plugin/schema/font hatası yok; gerçek kullanıcı yoluna yazım yok.
2. **Tek örnek kilidi** — ikinci süreç pencere açmadan 0 ile çıkar, ilki yaşar.
3. **Normal kapanış** — WM_CLOSE (terminate yok): kapanış yedeği → DB kapatma → çıkış kodu 0; `0xC0000409`/QThread destroyed yok.
4. **Temel UI akışı** — müşteri, ürün, teklif, PDF; teklif numarası ile arşiv PDF adı aynı; PDF'de maliyet/kâr yok.
5. **Credential hata yolu** — fail backend ile kısa "Güvenli Depo" uyarısı; ham istisna UI'da ve logda yok; gerçek Credential Manager'a çağrı gitmez.
6. **Uzun worker ile kapanış** — DB'yi şişirip kapanış yedeğini uzat; süreç worker bitmeden teardown yapmamalı.
7. **Restart** — yardımcı süreç mutex'i tutarken EXE'yi `--restarted-from <pid>` ile başlat; sınırlı bekleme sonrası kilit alınır, komut satırında EXE yolu bir kez geçer.
8. **Hata penceresi** — geçici profile bozuk veritabanı koy; "… - Hata" penceresi log yolunu göstermeli, süreç temiz kod ile çıkmalı. (Üretim artifact'ine hook **eklenmez**.)

Kapanış: yalnız bu turda açılan PID'ler yönetilir, geçici kök proje ve gerçek profil dışında olduğu doğrulanıp silinir, gerçek kullanıcı verisi parmak izi değişmemiş olmalı.

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
