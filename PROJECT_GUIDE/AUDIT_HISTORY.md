---
purpose: K1–K6 ve O1–O16 denetim bulgularının kapanış kaydı (tarihçe).
read_when: Denetim geçmişi, "bu daha önce görüldü mü?", regresyon şüphesi.
covers: []
last_verified_commit: 060baf3
last_verified_date: 2026-07-28
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

## Not

- O16, **paketli sürümde manuel testle** bulundu; kaynak testleri `QInputDialog.getItem`'i mock'ladığı için gerçek modal entegrasyonu hiç çalıştırılmamıştı. Bu, mock'lu testlerin sınırını gösteren kalıcı bir derstir ([KNOWN_RISKS.md](KNOWN_RISKS.md)).
- Tam commit zinciri burada tutulur; diğer belgelerde tekrarlanmaz.
