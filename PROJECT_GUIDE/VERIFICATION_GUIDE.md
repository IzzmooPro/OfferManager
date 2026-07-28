---
purpose: Frozen EXE ve installer doğrulama yöntemi; kanıt sınıflarının ayrımı.
read_when: Paketli sürüm veya installer doğrulaması, release öncesi.
covers:
  - packaging/TeklifYonetim.iss
  - core/restart.py
  - core/app_paths.py
  - ui/dialogs/backup_manager.py
last_verified_commit: 060baf3
last_verified_date: 2026-07-28
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

## Sürüm yükseltmesinde kapsam

Yeni bir sürüm için **B ve C sınıfları tekrarlanır**; hangi senaryoların atlandığı açıkça yazılır. Örnek: yalnız sürüm numarası ve doğrulanmış düzeltmeler değiştiyse B'de uzun patolojik senaryolar (büyük DB ile worker beklemesi, restart mutex beklemesi) ve C'de uninstall/reinstall tekrarlanmayabilir — bu durumda manifestteki `not_repeated` alanına hangi turda geçtiği yazılır.

## Doğrulanmış son sonuçlar

Bu üç sınıfın en son sonuçları, hangi sürüm için doğrulandığı (`verified_for_version`) ve tarihleri: [CURRENT_STATUS.md](CURRENT_STATUS.md) ve [project_manifest.json](project_manifest.json). Kalan boşluklar: [KNOWN_RISKS.md](KNOWN_RISKS.md).
