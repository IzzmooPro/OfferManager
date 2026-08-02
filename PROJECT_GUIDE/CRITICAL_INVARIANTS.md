---
purpose: Kaynak ve testlerden doğrulanmış, bozulmaması gereken davranışlar.
read_when: Her kod düzeltmesi ve her incelemede.
covers:
  - services/offer_service.py
  - services/product_service.py
  - database/db_manager.py
  - ui/utils/excel_import.py
  - ui/utils/operation_error.py
  - ui/utils/operation_error_dialog.py
  - core/feedback_report.py
  - ui/dialogs/feedback_dialog.py
  - ui/dashboard_page.py
  - ui/create_offer_page.py
  - ui/dialogs/category_dialog.py
  - ui/main_window.py
  - ui/dialogs/backup_manager.py
  - core/restart.py
  - core/credential_store.py
  - main.py
  - tests/conftest.py
last_verified_commit: 9e89370
last_verified_date: 2026-08-02
volatile: false
---

# Kritik değişmezler

Her madde: **kural → nerede → koruyan test**. Bulguların geçmişi [AUDIT_HISTORY.md](AUDIT_HISTORY.md).

## Veri güvenliği ve izolasyon

1. **Testler gerçek kullanıcı verisine dokunmaz.** `tests/conftest.py` sekiz ortam değişkenini proje importlarından önce tek geçici köke yönlendirir; keyring sahtedir. → `tests/test_env_isolation.py`
2. **Veri klasörü adı `OfferManagementSystem` değişmez** ve kurulum dizininden ayrıdır; kaldırma kullanıcı verisini silmez. → [VERIFICATION_GUIDE.md](VERIFICATION_GUIDE.md) installer kanıtı
3. **Migration'lar geriye uyumlu ve tekrar çalıştırılabilir.** Toplu yazma tek `db.transaction()` kullanır; aynı transaction içinde ikinci writer açılmaz. → `tests/test_regressions.py`, `tests/test_offer_service.py`

## Teklif ve çıktı

4. **Teklif numarası ve ilişkili kayıtlar atomiktir**; kısmi hatada rollback olur, numara üretimi yarışa dayanıklıdır. → `tests/test_offer_service.py`
5. **Arşiv PDF adı DB'deki teklif numarasıyla aynıdır** (`<teklif_no>.pdf`) ve teklif silinince arşiv PDF'i de kalkar. → `tests/test_offer_archive_naming.py`
6. **Maliyet/kâr bilgisi PDF, Excel, CSV veya e-postaya sızmaz.** → `tests/test_profit.py`, `tests/test_export_service.py`
7. **Teklif numarası sayacı geriye alınmaz.** Silinen tekliften doğan numara boşluğu normaldir.

## Ürün kodu ve içe aktarma

8. **Ürün kodu normalizasyonu NFKC + casefold'dur**; arama harf ve Unicode biçiminden bağımsızdır. Karşılaştırma SQL'de sütun tarafında `COLLATE NOCASE` ile yapılır (sağ operandda değil). → `tests/test_product_code_uniqueness.py`
9. **Aynı dosya içindeki mükerrer satırlar** hem ürün hem müşteri yolunda atlanır; hata mesajı kaynak sayfayı belirtir. → `tests/test_customer_import_duplicates.py`, `tests/test_xlsx_sheet_selection.py`
10. **XLSX sayfa seçimi:** gizli sayfa listelenmez/okunmaz; tek aday otomatik seçilir; birden fazlaysa sorulur; yalnız seçilen sayfa aktarılır. → `tests/test_xlsx_sheet_selection.py`
11. **Sayfa sorusu modal ilerleme penceresinden ÖNCE sorulur.** İlerleme penceresi açıkken ikinci bir modal soru açılırsa Windows onu devre dışı bırakır ve akış süresiz kilitlenir. İptalde DB yazımı, hata kutusu ve yarım aktarım olmaz. → `tests/test_import_sheet_dialog_modality.py`
12. **Ürün seçicide sonuç sınırı ve arama debounce'u korunur**; toplu teklif yüklemede ürünler tek sorguyla çözülür. → `tests/test_product_select_dialog.py`, `tests/test_product_batch_lookup.py`

## Thread, kapanış, restart

13. **Çalışan worker bitmeden süreç teardown yapmaz.** Bir `QThread` nesnesi YALNIZ yerleşik `finished` sinyalinden sonra bırakılır — sonuç sinyali `run()` İÇİNDE yayıldığı için sonuç slot'unda `deleteLater`/referans temizliği yapılmaz (ölçüldü: `0xC0000409` fast-fail). Gecikmiş eski worker'ın `finished` sinyali yeni worker'ın referansını ve UI durumunu değiştirmez. Çalışan yedek worker'ı kapanış beklemesine dahildir. → `tests/test_shutdown_workers.py`, `tests/test_thread_lifecycle.py`, `tests/test_backup_worker_lifecycle.py`, `tests/test_pdf_worker_lifecycle.py`
14. **Kapanış sırası:** kapanış yedeği → DB kapatma → çıkış kodu 0.
15. **Restart kapanışında yeni kapanış yedeği alınmaz**; normal Qt/DB kapanışı ve sınırlı mutex beklemesi uygulanır. Ardıl `--restarted-from <pid>` ile açılır, komut satırında EXE yolu bir kez geçer, `os.execl` kullanılmaz. → `tests/test_restart_flow.py`
16. **Tek örnek kilidinde kısmi edinim bırakılmaz**; mutex alınıp paylaşımlı bellek alınamazsa handle kapatılır. → `tests/test_restart_flow.py`

## Gizlilik ve hata bildirimi

17. **SMTP parolası yalnız Windows Credential Manager'da tutulur**; config'e düz metin yazılmaz, loglanmaz. Okuma hatası **sessizce yutulmaz**, `CredentialStoreError` fırlatılır ve okuma hatası kaydı silmeye dönüşmez. → `tests/test_credential_store.py`, `tests/test_smtp_credential_ui.py`, `tests/test_smtp_security.py`
18. **Hiçbir kullanıcı mesajında veya güvenli logda** ham istisna metni, `str(exception)`, traceback, SQL, yerel dosya yolu ya da müşteri/firma/teklif adı bulunmaz. Mesaj sabit metinlerden seçilir; log yalnız işlem adı, istisna sınıf adı, güvenli kayıt id'si ve `dosya:satır` çerçevelerini içerir (`exc_info` kullanılmaz). Diyalog kapanmaz, kullanıcı düzeltip yeniden dener. → `tests/test_save_error_handling.py`, `tests/test_operation_error_dialog.py`, `tests/test_dashboard_safe_errors.py`, `tests/test_create_offer_stage_errors.py`
18b. **Kısmi başarı önceki başarılı aşamayı İNKÂR ETMEZ.** Çok aşamalı akışlarda (kaydet → PDF → arşiv → sonraki eylemler; toplu silme/PDF; DB yazımı → ekran yenileme) sonraki bir aşamanın hatası, tamamlanmış aşamayı "yapılamadı" gibi anlatamaz. Toplu işlemlerde yalnız güvenli sayılar gösterilir; "hiçbiri" türü genelleme yapılmaz. → `tests/test_create_offer_stage_errors.py`, `tests/test_dashboard_safe_errors.py`
18c. **"Log Klasörünü Aç" düğmesi** yalnız beklenmeyen/teknik hatalarda gösterilir ve mesajdaki ipucu ile kutudaki gerçek düğme birebir eşleşir; doğrulama mesajlarında bulunmaz. → `tests/test_operation_error_dialog.py`
18d. **Hata/öneri raporu kullanıcı iradesiyle gider ve gizli alan taşımaz.** Program hiçbir koşulda raporu kendiliğinden göndermez, ağa çıkmaz, kullanıcının SMTP hesabını veya güvenli depodaki parolasını kullanmaz; hiçbir yolda "rapor gönderildi" denmez. Rapora YALNIZ pencerede **görünen** alanlar ve kullanıcının kendi açıklaması girer — `str(exception)`, traceback, mutlak yol, kayıt id'si, teklif no ve müşteri/firma verisi girmez. `mailto:` Qt URL/query API'siyle yüzde-kodlanarak kurulur (CRLF/`&`/`?` enjeksiyonu kapalı). Pano yalnız gerçek tıklamada yazılır; "Vazgeç" yan etki üretmez. `core/feedback_report.py` Qt import etmez ve istisnayı YENİDEN KAYDETMEZ. → `tests/test_feedback_report.py`
19. **Paketlenmiş (windowed) derlemede çalışma zamanı hatası görünür**; hata penceresi log yolunu gösterir, aynı hata kısa süre tekrar bastırılır. → `tests/test_windowed_error_reporting.py`

## Paketleme ve yayın

20. **Dağıtım `PyInstaller onedir + Inno Setup` kalır**; onefile veya EXE-üzerine-kopyalama yoluna dönülmez. Güncelleme installer'ı `os.startfile` ile başlatır.
21. **Sürüm tek kaynaktan gelir** (`core/constants.py:APP_VERSION`); `.iss`, `version_info.txt` ve installer adı bununla eşleşir. → [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md)
22. **Doğrulama sınıfları karıştırılmaz:** kaynak testi ≠ paketli EXE kanıtı ≠ installer kanıtı. → [VERIFICATION_GUIDE.md](VERIFICATION_GUIDE.md)
