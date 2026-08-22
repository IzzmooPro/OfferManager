---
purpose: Doğrulanmış ve hâlâ geçerli hata belirtileri → kök neden → çözüm.
read_when: Bilinen bir belirti görüldüğünde.
covers: []
last_verified_commit: 060baf3
last_verified_date: 2026-07-28
volatile: false
---

# Sorun giderme

Yalnız **doğrulanmış ve güncel** maddeler. Daha eski, tek seferlik veya artık geçerliliği belirsiz notlar yerel `docs/local/SORUN_COZUM_NOTLARI.md` dosyasındadır; o dosya **kanonik değildir**.

| Belirti | Kök neden | Çözüm / kontrol |
|---|---|---|
| Testler gerçek verileri siliyor | `unittest discover` conftest izolasyonunu atlıyor | Daima `python -m pytest tests -q` ([TESTING_GUIDE.md](TESTING_GUIDE.md)) |
| Çok sayfalı Excel içe aktarımı takılıyor, "Çalışma Sayfası Seç" tıklanmıyor | Modal ilerleme penceresi sonradan açılan soruyu devre dışı bırakıyor | O16 düzeltmesi: sayfa seçimi ilerleme penceresinden önce. Regresyon: `tests/test_import_sheet_dialog_modality.py` |
| Excel başlıkları eşleşmiyor (Türkçe "İ") | `"İ".lower()` birleşik nokta üretiyor | `ui/utils/excel_import.py` içindeki `_norm` Türkçe İ→i, I→ı çevirisini yapar |
| Aynı ürün kodu iki kez kaydedilebiliyor | SQLite `NOCASE` yalnız ASCII; collation yanlış tarafta | NFKC+casefold normalizasyon, sütun tarafında `COLLATE NOCASE`; `tests/test_product_code_uniqueness.py` |
| Kapanışta uygulama çöküyor (`0xC0000409`) | Çalışan `QThread` yok ediliyor | Kapanış worker'ları bekler (`_shutdown_workers`); yeni worker eklerken listeye dahil et |
| Paketlenmiş sürümde hata sessizce kayboluyor | Windowed derlemede stdout/stderr yok | `exception_hook` görünür pencere + log yolu gösterir; `tests/test_windowed_error_reporting.py` |
| "Kayıtlı SMTP şifresi okunamadı" uyarısı | Credential Manager erişilemiyor veya boş | Beklenen davranış: boş alan silme anlamına gelmez; sorun giderilmeden kaydetme yapılmamalı |
| Güncelleme kurulumu başlamıyor / UAC yükselmiyor | `subprocess` admin manifestli kurulumu yükseltemez | `os.startfile` kullanılır; değiştirme |
| Kaldırıcı "PathRedir: Not initialized" veriyor | Inno 7'de `[Code]` bölümü olmayan kurulum hatası | `.iss` içindeki boş `[Code]` bölümü silinmemeli |
| Kurulum sonrası "Failed to load Python DLL" | onefile `Temp\_MEI` açılımı bozulmuş | onedir kullanılır; onefile'a dönülmez |
| Sürüm alanları uyuşmuyor | Sürüm elle birden çok yere yazılmış | Tek kaynak `core/constants.py`; [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md) eşleşme listesi |
| Build "EXE oluşmadı" ile duruyor | Testler kırmızı veya Inno bulunamadı | `Kurulum-Yap.bat` çıktısındaki adım numarasına bak; testleri ayrıca çalıştır |
