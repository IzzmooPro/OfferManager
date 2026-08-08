---
purpose: K1–K6 ve O1–O16 denetim bulgularının kapanış kaydı (tarihçe).
read_when: Denetim geçmişi, "bu daha önce görüldü mü?", regresyon şüphesi.
covers: []
last_verified_commit: c3f711e
last_verified_date: 2026-08-08
volatile: false
---

# Denetim tarihçesi

Bu belge **tarihçedir**; güncel durum [CURRENT_STATUS.md](CURRENT_STATUS.md), açık riskler [KNOWN_RISKS.md](KNOWN_RISKS.md).
Sütunlar: kod · sınıf · kök neden (kısa) · kapanış commit'i · korunan davranış · temel test.

## K serisi

| Kod | Sınıf | Kök neden | Commit | Korunan davranış | Test |
|---|---|---|---|---|---|
| K1, K2, K3, K5 | KESİN | Teklif numarası/yedek/e-posta akışlarında sağlamlaştırma eksikleri | `424b2db` | Numara ve ilişkili kayıt atomikliği, yedek/e-posta hata yolları | `test_offer_service`, `test_regressions` |
| K4 | KESİN | Şablondan teklif yükleme UI'da erişilemiyordu | `4beecd1` | Şablon yükleme giriş noktası | `test_create_offer_template_ui` |
| K6-A, K6-D | KESİN | Güncelleme kontrolü kapanışta çökme üretiyordu | `1ff6460` | Kapanışta worker'ların güvenle bitirilmesi | `test_update_dialog_lifecycle`, `test_shutdown_workers` |
| K6-C | KESİN | Thread yaşam döngüsü kapanışta yarım kalıyordu | `d9772fb` | Worker bitmeden teardown yok | `test_thread_lifecycle` |
| K6-B | KESİN | Kapanışta worker toplama eksikti | `fe782e3` | `_shutdown_workers` kapsamı | `test_shutdown_workers` |

## O serisi

| Kod | Sınıf | Kök neden | Commit | Korunan davranış | Test |
|---|---|---|---|---|---|
| O1 | KESİN | — | `ee98dc0` | İlgili regresyon | `test_regressions` |
| O2 | KESİN | — | `ad36cc1` | İlgili regresyon | `test_regressions` |
| O3 | KESİN | — | `02651bd` | İlgili regresyon | `test_regressions` |
| **O4** | **YANLIŞ POZİTİF** | Ölçümle çürütüldü; kod değişmedi | — | — | — |
| O5 | Özgün yarış **yanlış pozitif**; komşu kusurlar KESİN | `os.execl` yerinde yeniden başlatma; tek örnek kilidinde kısmi edinim; restart kapanışında gereksiz ikinci yedek | `6784020` | Restart kapanışında yeni yedek yok; sınırlı mutex beklemesi; kısmi edinim bırakılmaz | `test_restart_flow` |
| O6 | KESİN | Ürün kodu harf/Unicode farkıyla mükerrer kaydediliyordu; `COLLATE NOCASE` sağ operandda etkisizdi | `8b81450` | NFKC+casefold normalizasyon, sütun tarafında collation, benzersiz + kısmi index | `test_product_code_uniqueness` |
| O7 | KESİN | Test izolasyonu yalnız `LOCALAPPDATA`'yı kapsıyordu | `2a55ab6` | Sekiz ortam değişkeni tek geçici köke | `test_env_isolation` |
| O8 | KESİN | Windowed derlemede yakalanmamış istisna sessiz kalıyordu | `9e17609` | Görünür hata penceresi + log yolu + kısa tekrar bastırma | `test_windowed_error_reporting` |
| O9 | KESİN | Keyring hataları sessizce yutuluyor, boş değer silmeye dönüşebiliyordu | `652cb85` | `CredentialStoreError`, okuma hatasında silme yok, düz metin taşıma | `test_credential_store`, `test_smtp_credential_ui` |
| **O10** | **OLASI ölçekleme** — düzeltildi | Ürün seçici tüm kataloğu yüklüyordu | `55ee9a6` | Sonuç sınırı + arama debounce + görünür sonuç bilgisi | `test_product_select_dialog` |
| **O11** | **OLASI ölçekleme** — düzeltildi | Teklif/şablon yüklemede kalem başına ayrı sorgu (N+1) | `fab1bb0` | `get_by_codes()` toplu çözüm | `test_product_batch_lookup` |
| O12 | KESİN | Biten yedek worker'ları serbest bırakılmıyor, çalışan worker kapanışa dahil değildi | `b290911` | `deleteLater` + kapanış beklemesine dahil etme | `test_backup_worker_lifecycle` |
| O13-müşteri | KESİN | Aynı dosyadaki mükerrer müşteri satırları iki kez yazılıyordu | `44c1d58` | Dosya-içi mükerrer atlama (müşteri yolu) | `test_customer_import_duplicates` |
| O13-ürün | Zaten çözülmüş | O6 kapsamındaydı | — | — | `test_product_code_uniqueness` |
| O14 | KESİN (özgün etiketi yanlıştı) | Kaydetme/silme hatasında ham istisna gösterimi ve diyalogun kapanması | `ef4cb4c` | Güvenli mesaj + güvenli log + retry döngüsü | `test_save_error_handling` |
| O15 | KESİN | Yalnız aktif sayfa okunuyor, diğer sayfalardaki veri sessizce atılıyordu | `66527c2` | Sayfa adayı tespiti + kullanıcı seçimi + tek sayfa aktarımı | `test_xlsx_sheet_selection` |
| **O16** | KESİN | Sayfa sorusu modal ilerleme penceresinden **sonra** açılıyor, Windows onu devre dışı bırakıyor ve akış kilitleniyordu | `060baf3` | Sayfa seçimi ilerleme penceresinden önce; iptalde temiz çıkış | `test_import_sheet_dialog_modality` |

## R serisi (v4.1 sonrası)

| No | Sınıf | Kusur | Düzeltme | Test |
|---|---|---|---|---|
| **R10a** | KESİN | `create_offer_page` içindeki iki müşteri kaydetme yolu (`_check_customer_registration`, `_open_add_customer`) ham `{e}` gösteriyor, istisnayı güvenli loglamıyor; başarı logunda **firma adı** geçiyor; servis kaydı ile ekran yenilemesi tek `try` içinde olduğu için kaydedilmiş müşteri için "Müşteri kaydedilemedi" deniyordu | Güvenli `hata_diyalogu` altyapısı; `add` ile kayıt sonrası ekran aşaması ayrı `try` sınırlarına bölündü (`_yeni_musteriyi_goster`); başarı logu `id=%s`; `_open_add_customer` aynı diyalog nesnesiyle yeniden denemeye izin veriyor, kayıttan sonra diyaloğu yeniden açmıyor | `test_create_offer_customer_save_errors` |

| **R10b** | KESİN | `dashboard_page._open_file` korumasız `os.startfile`: dosya silinmiş/erişilemez olduğunda istisna UI akışına sızıyor, güvenli mesaj ve log oluşmuyor, çoklu PDF döngüsünde sonraki dosyalar açılamıyordu | `os.startfile` minimum try/except sınırına alındı; sabit `PDF_ACILAMADI_MESAJ` ile `kismi_hata_goster` (PDF üretimi inkâr edilmez), yol ve ham hata mesaja/loga girmez, döngü devam eder | `test_dashboard_safe_errors::DosyaAcmaTests` |

| **R10c-1** REPORTS | KESİN | `reports_page._generate` / `_export` ham istisna metnini kullanıcıya gösteriyor, teknik nedeni güvenli loglamıyordu | Sabit kullanıcı metni + `op_hata.logla` / `hata_diyalogu.hata_goster`; modül içi `logging`/`logger` kaldırıldı. Commit `c2dfca0` | `test_reports_safe_errors` |

| **R10c-2** SETTINGS | KESİN | Ayarlar, SMTP testi ve logo yükleme/kaldırma yolları ham istisna gösteriyordu; `_upload` başarıyı bildirmediği için iptal/kopyalama hatasında logo devre dışı işareti (`logo.disabled`) siliniyor ve eski logo sessizce etkinleşiyordu; marker yazılamadığında önizleme gerçek aktif logoyu göstermiyordu | Güvenli mesaj + tek güvenli log; `_upload` açık `True`/`False` dönüş sözleşmesi (önizleme hatası kaydı geçersiz kılmaz); marker yalnız gerçek kayıtta silinir; marker yazılamazsa önizleme varsayılan logoya döner, yoksa "Logo Yok". Commit `745fd55` | `test_settings_safe_errors` |

| **R10c-3** BACKUP | KESİN | Yedekleme/geri yükleme ham istisna taşıyordu; `restore_backup` üç farklı sonucu ayırmıyor, rollback ilk hatada duruyor, metadata yazımı başarısız olunca tamamlanmış yedek "başarısız" sayılıyor, geçici klasör temizleme hatası sonucu maskeliyor ve başarısız geri yüklemede yeniden başlatma yapılabiliyordu | Durum makinesi `preflight_failed` / `rolled_back` / `rollback_failed` (sabit metinler); `_geri_al` ilk hatada durmaz, başlangıçtaki var/yok durumunu birebir kurar ve DB'yi yeniden doğrular; metadata ayrı aşamadır (18b); `_gecici_temizle` sonucu değiştirmez; restart yalnız tam başarıda ve tam bir kez. Commit `8616862` | `test_backup_safe_errors` |

| **R10c-4** IMPORT | KESİN | Dosya okuma (`_read_file`, `_read_xlsx_sheets`) ham `str(e)` döndürüyor; CSV logları dosya adı ve ham istisna taşıyor; satır hataları `errors` listesine firma adı/ürün kodu/teklif no yazıyor; kategori hatası kategori adıyla loglanıp kullanıcıya hiç bildirilmiyor; doğrulama/yazma/aşama hataları ilerleme penceresini açık bırakıp yanlış başarı döndürebiliyor; workbook hata yolunda kapatılmıyordu | Sabit `DOSYA_OKUMA_HATASI`; güvenli `kayit_id` yalnız satır/grup SIRASI; kategori başarısızlığı önbelleğe alınır (yeniden denenmez), her farklı kategori bir kez loglanır, kullanıcıya tek toplu uyarı; `stage_state` yalnız sayısal (`kategori_yazildi`); aşamalar birbirinin başarısını inkâr etmez ve ilerleme penceresi her yolda kapanır; dönüş değeri gerçek DB değişikliğini gösterir; `_workbook_kapat` başarı ve hata yollarında `finally` içinde. **R8 gizli sayfa davranışı korunmuştur.** Commit `46d4d75` | `test_import_safe_errors`, `test_csv_import_errors` |

| **R12c** | KESİN | Artifact `227656b`'den build edilmişti; sonrasında kaynak ve test dosyaları değişmesine rağmen `--release` **exit 0** veriyordu. "Build sonrası yalnız manifest/CURRENT_STATUS/KNOWN_RISKS/CHANGELOG değişebilir" kuralının otomatik karşılığı yoktu — eski artifact yeni kaynağın kanıtı gibi yayına gidebilirdi | Yeni `kontrol_build_sonrasi_provenance` kapısı. İzinli **tam** yollar (exact match, klasör/prefix izni YOK): `PROJECT_GUIDE/project_manifest.json`, `PROJECT_GUIDE/CURRENT_STATUS.md`, `PROJECT_GUIDE/KNOWN_RISKS.md`, `docs/CHANGELOG.md`. `built_from_commit..HEAD` commit'leri + staged + unstaged + untracked/non-ignored birlikte denetlenir; add/modify/delete/rename kapsanır, dosya başına tek hata üretilir, yollar `/` biçimine normalize edilir ve mutlak yol sızmaz. **Fail-closed**: `built_from_commit` eksik/bozuk, Git'te bulunamıyor, HEAD'in atası değil veya Git okunamıyorsa kapı kapanır. Yalnız `--release` modunda zorunlu; normal/`--stale`/`--artifacts` davranışı değişmez. Commit `c3f711e` | `test_project_guide` (24 provenance testi), `test_version_consistency` |

## Not

- **R12c kanıt sınırı.** Kapı yalnız **Git'in görebildiği** provenance'ı kanıtlar. Gitignore/local-only `packaging/` ve `assets/` girdilerinin içerik geçmişi commit diff'iyle kanıtlanamaz; onlar `kontrol_yerel_girdiler`, artifact hash ve installer doğrulamalarıyla ayrı kanıt sınıfındadır. Ayrıca `snapshot.built_from_commit` kapının **güvendiği** girdidir — artifact ile commit arasında kriptografik bağ kurulmaz ve manifest build sonrası değişebilen yollardan olduğu için yanlış/ileri bir commit kapıyı sessizce gevşetir; gerçek build loguyla eşleşme **release incelemesinde ayrıca** doğrulanmalıdır.
- **R10c kanıt sınıfı.** Dört alt tur şunlarla ölçüldü: kaynak testleri; mock/izole geçici profil ölçümleri (gerektiği yerde test DB veya `TemporaryDirectory` altında geçici dosya); bazı alt turlarda izole kaynak-modu Windows Qt smoke/probları. **Yeni frozen/paketli EXE, installer, gerçek disk-dolu, gerçek dosya kilidi ve gerçek SQLite commit hatası kanıtı üretilmedi.** Bu yüzden R10c, R6 (paketli restore→restart) ve R8 (gizli sayfa politikası) maddelerini **kapatmaz**. Kapsam da sınırlıdır: iddialar yalnız R10c'de ele alınan ve regresyon testleriyle bağlanan hata yolları içindir.
- O16, **paketli sürümde manuel testle** bulundu; kaynak testleri `QInputDialog.getItem`'i mock'ladığı için gerçek modal entegrasyonu hiç çalıştırılmamıştı. Bu, mock'lu testlerin sınırını gösteren kalıcı bir derstir ([KNOWN_RISKS.md](KNOWN_RISKS.md)).
- Tam commit zinciri burada tutulur; diğer belgelerde tekrarlanmaz.
