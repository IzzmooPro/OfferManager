---
purpose: Kalıcı teknik kararlar ve gerekçeleri (neden böyle yapıldı).
read_when: "Neden bu şekilde?" sorusu, mimari değişiklik önerisi.
covers: []
last_verified_commit: 060baf3
last_verified_date: 2026-07-28
volatile: false
---

# Kararlar

Yeni bir karar alındığında bu tabloya bir satır eklenir; uzun gerekçe gerekiyorsa [decisions/](decisions/README.md) altına ayrı dosya açılır.

| # | Karar | Gerekçe | Durum |
|---|---|---|---|
| D1 | Dağıtım **PyInstaller onedir + Inno Setup** | onefile her açılışta `Temp\_MEI` açıyor; antivirüs/Temp temizliği "Failed to load Python DLL" hatasına yol açıyordu | Kalıcı |
| D2 | Kullanıcı verisi kurulum dizininden **ayrı** (`OfferManagementSystem`) | Kaldırma ve upgrade kullanıcı verisini etkilemesin | Kalıcı |
| D3 | Veri klasörü adı depo adından bağımsız | Depo yeniden adlandırıldı; veri yolu değişirse eski kurulumlar veriyi kaybederdi | Kalıcı |
| D4 | Inno'da **`AppMutex` yok**, `CloseApplications` + `SetupMutex` var | AppMutex otomatik güncellemede kullanıcıya gereksiz "uygulamayı kapatın" uyarısı çıkarıyordu | Kalıcı |
| D5 | `.iss` içinde boş **`[Code]` bölümü korunur** | Inno 7 önizlemesinde `[Code]` olmayan kurulumların kaldırıcısı "PathRedir: Not initialized" hatası veriyor | Kalıcı |
| D6 | Güncelleme installer'ı `os.startfile` ile başlatır | `subprocess`/CreateProcess admin manifestli kurulumu yükseltemiyor | Kalıcı |
| D7 | SMTP parolası **yalnız Credential Manager**'da | Config dosyasında düz metin parola kabul edilemez | Kalıcı |
| D8 | Maliyet/kâr **hiçbir dış çıktıda** yok | Müşteriye giden belgede iç maliyet görünmemeli | Kalıcı |
| D9 | Ürün kodu **NFKC + casefold** ile normalize | SQLite `NOCASE` yalnız ASCII; Türkçe/Unicode kodlar mükerrer kaydediliyordu | Kalıcı |
| D10 | XLSX'te sayfalar **birleştirilmez**, kullanıcı seçer | Otomatik birleştirme sessiz veri karışımı üretiyordu | Kalıcı |
| D11 | Sayfa sorusu **ilerleme penceresinden önce** | Modal ilerleme penceresi sonradan açılan soruyu Windows'ta devre dışı bırakıyor (O16) | Kalıcı |
| D12 | Restart **`os.execl` ile değil**, ardıl süreç + `--restarted-from` ile | `os.execl` Windows'ta yerinde değiştirme yapmaz; kilit ve kapanış sırası bozuluyordu | Kalıcı |
| D13 | `packaging/`, `assets/`, `Import_Test/` ve build çıktıları **depo dışında** | Gerçek müşteri verisi ve yerel paketleme girdileri GitHub'a gitmemeli; bedeli temiz clone build'in tekrarlanamaması | Kalıcı, bilinçli |
| D14 | Testler **yalnız pytest** ile | `unittest discover` conftest izolasyonunu atlıyor ve gerçek veriyi siliyordu | Kalıcı |
| D15 | Teklif numarası sayacı **geriye alınmaz** | Silinen tekliften doğan boşluk, numara tekrar kullanımından daha güvenli | Kalıcı |
| D16 | Kanonik bilgi **PROJECT_GUIDE**'da; `.claude/`, `docs/` ve yerel notlar kanonik değil | Tek doğruluk kaynağı ve düşük token maliyeti | Kalıcı |
