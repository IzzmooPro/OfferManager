---
purpose: Test çalıştırma kuralları ve konu → test dosyası matrisi.
read_when: Test yazarken, test seçerken, düzeltme sonrası doğrulamada.
covers:
  - tests/conftest.py
  - tests/test_env_isolation.py
  - tests/test_offer_service.py
  - tests/test_product_code_uniqueness.py
  - tests/test_import_sheet_dialog_modality.py
  - tests/test_xlsx_sheet_selection.py
  - tests/test_shutdown_workers.py
  - tests/test_updater_asset_verification.py
  - tests/test_restart_flow.py
  - tests/test_credential_store.py
  - tests/test_save_error_handling.py
last_verified_commit: c3f711e
last_verified_date: 2026-08-08
volatile: false
---

# Test rehberi

## Kurallar

- **Daima** `python -m pytest tests -q`. `unittest discover` **kullanılmaz**: `tests/conftest.py` izolasyonunu atlar ve gerçek kullanıcı verisine yazar.
- UI testleri `QT_QPA_PLATFORM=offscreen` ile çalışır; test modülü bunu kendi başında ayarlar.
- Yeni davranış için önce **kırmızı** regresyon testi yaz; yalnız `py_compile` ile "tamamlandı" deme.
- Gerçek SMTP, ağ, tarayıcı, installer ve Credential Manager testte kullanılmaz; bloklayan işler sahte worker/sunucularla temsil edilir.
- Geçici dosyalar `TemporaryDirectory` ile üretilir ve testten sonra kalmaz.

## Konu → test dosyası

| Konu | Test dosyası |
|---|---|
| Ortam izolasyonu (K/O ön koşulu) | `tests/test_env_isolation.py`, `tests/conftest.py` |
| Teklif numarası, atomiklik, teklif servisi | `tests/test_offer_service.py`, `tests/test_regressions.py` |
| Arşiv PDF adı | `tests/test_offer_archive_naming.py` |
| Kâr/maliyet gizliliği | `tests/test_profit.py`, `tests/test_export_service.py` |
| Ürün kodu normalizasyonu (O6, O13-ürün) | `tests/test_product_code_uniqueness.py` |
| Ürün seçici sınırı/debounce (O10) | `tests/test_product_select_dialog.py` |
| Toplu ürün çözümü (O11) | `tests/test_product_batch_lookup.py` |
| CSV içe aktarma hataları | `tests/test_csv_import_errors.py` |
| Müşteri mükerrer satırları (O13-müşteri) | `tests/test_customer_import_duplicates.py` |
| XLSX sayfa seçim mantığı (O15) | `tests/test_xlsx_sheet_selection.py` |
| XLSX sayfa seçiminde modal sırası (O16) | `tests/test_import_sheet_dialog_modality.py` |
| Kaydetme/silme hata yolları (O14) | `tests/test_save_error_handling.py` |
| Worker kapanışı (K6, O12) | `tests/test_shutdown_workers.py`, `tests/test_thread_lifecycle.py`, `tests/test_backup_worker_lifecycle.py` |
| Restart ve tek örnek kilidi (O5) | `tests/test_restart_flow.py` |
| Credential / SMTP gizliliği (O9) | `tests/test_credential_store.py`, `tests/test_smtp_credential_ui.py`, `tests/test_smtp_security.py` |
| Windowed hata bildirimi (O8) | `tests/test_windowed_error_reporting.py` |
| E-posta diyalogu yaşam döngüsü | `tests/test_email_dialog_lifecycle.py` |
| Güncelleme diyalogu yaşam döngüsü | `tests/test_update_dialog_lifecycle.py` |
| Updater güven zinciri (asset seçimi, URL/host, SHA-256, size) | `tests/test_updater_asset_verification.py` |
| Şablon / kategori / müşteri / ürün servisleri | adı eşleşen `tests/test_*_service.py` |
| Süresi geçen teklif uyarısı | `tests/test_expired_offer_prompt.py` |
| Rehber tutarlılığı | `tests/test_project_guide.py` |
| **Build sonrası provenance / release kapısı (R12c)** | `tests/test_project_guide.py`, `tests/test_version_consistency.py` |

### R12c provenance testleri hakkında

- Testler **geçici, gerçek bir Git deposu** kurar (`git init` + commit) ve yalnız orada çalışır: **gerçek depoya, gerçek artifact'lara ve kullanıcı verisine dokunmaz**.
- Kapsanan yollar: izinli dört **tam** yolun geçmesi; kaynak/`tests/`/izlenen paketleme girdisi/başka rehber belgesi değişikliğinin kırmızı olması; **commit edilmiş, staged, unstaged ve untracked/non-ignored** değişikliklerin ayrı ayrı yakalanması; **silme ve yeniden adlandırma**; benzer-isim ve klasör-prefix hilelerinin geçmemesi; aynı dosya için tek hata üretilmesi; gitignore'daki build çıktılarının ihlal sayılmaması.
- **Fail-closed** yolları: `built_from_commit` eksik, bozuk, Git'te bulunamıyor, HEAD'in atası değil veya Git hiç okunamıyor.
- Mod sınırı: kontrolün yalnız `--release` modunda çalıştığı; normal/`--stale`/`--artifacts` modlarının etkilenmediği.
- **Kanıtlamadıkları — silinmemeli:** kaynak testi, artifact ile `built_from_commit` arasında gerçek bir **kriptografik bağ** kurmaz ve gitignore/local-only `packaging/`–`assets/` girdilerinin **içerik geçmişini** doğrulamaz. Bu ikisi release incelemesinin elle yürütülen adımlarıdır ([RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md)).

## Yalnız kaynakta test edilenler

Aşağıdakiler kaynak testiyle örtülür ama **paketli sürümde doğrulanmamıştır**; bunları frozen kanıtı gibi sunma:

- Güncelleme indirme ve kurulum başlatma (`_apply_update`) — asset seçimi ve içerik doğrulaması sahte release JSON'u ve sahte `urlopen` ile örtülür; **gerçek GitHub redirect host'u ve gerçek installer çalıştırma kaynak testinde doğrulanmaz** (KNOWN_RISKS R3b, R3d)
- Gerçek SMTP gönderimi
- O14 retry döngüsünün gerçek modal `exec()` davranışı

Paketli/installer doğrulaması: [VERIFICATION_GUIDE.md](VERIFICATION_GUIDE.md).
