# Bilinen sorunlar indeksi

Kaynak: `docs/local/SORUN_COZUM_NOTLARI.md` (yerel, kanonik değil). Bu indeks yalnızca hangi bölümün okunacağını söyler; çözümü güncel kodda yeniden doğrula.

| Belirti/alan | Bölüm |
|---|---:|
| `_MEI`, Python DLL, onefile/onedir | 1 |
| updater exe yolu/bozuk Türkçe, installer üzerine güncelleme | 2 |
| UAC, installer başlamıyor, subprocess | 3 |
| güncelleme diyaloğu kırpılıyor | 4 |
| `.bat`, CRLF, komutlar parçalanıyor | 5 |
| spec/main.py yolu, `SPECPATH` | 6 |
| test gerçek veriyi bozuyor, pytest izolasyonu | 7 |
| Gmail/App Password/SMTP | 8 |
| Türkçe `İ`, Excel başlığı | 9 |
| tablo combo/spin hizası, QSS min-height | 10 |
| GitHub repo rename/yönlendirme | 11 |
| eski installer siliniyor | 12 |
| Claude worktree temizliği | 13 |
| LocalAppData klasör adı/depo adı | 14 |
| GitHub'a ne girer, yerel/public ayrımı | 15 |
| Inno uninstall `PathRedir` | 16 |
| masaüstü kısayolu varsayılanı | 17 |
| updater uygulamayı kapatın, AppMutex | 18 |
| installer kapatamıyor/asılı process/taskkill | 19 |
| Qt buton metni kırpılıyor, fixedHeight | 20 |
| form alanı hizası, wrapper margins | 21 |
| pencere/uygulama ikonu | 22 |
| `+` glifi ortalama, QPainter/offscreen sınırı | 23 |
| yedekleme/Hakkında dialog kompaktlığı | 24 |
| Excel filtre oku başlığı kesiyor | 25 |
| uzun QLineEdit metninin sonu görünüyor | 26 |
| TRY/TL/para birimi normalizasyonu | 27 |
| toplu silme/import yavaş, satır başı commit | 28 |
| sekme geçişi yavaş, dirty flag/debounce | 29 |
| Excel import yavaş/ilerleme, N+1 sorgu | 30 |
| 10k satır tablo, ilk 500/limit | 31 |

Okuma deseni: başlığı `rg -n '^## N\.' docs/local/SORUN_COZUM_NOTLARI.md` ile bul; sonraki `##` başlığına kadar olan küçük aralığı oku. Birbiriyle bağlantılıysa en fazla iki bölüm aç.

**Güncellik uyarısı (Bölüm 2 vs 18/19):** Bölüm 2'nin çözüm metni "CloseApplications+AppMutex" der; bu artık geçersiz. Bölüm 18, AppMutex'i kaldırdı (yalnız `CloseApplications=yes` + `SetupMutex` kalır) ve Bölüm 19 taskkill/`os._exit` katmanını ekledi — canlı `packaging/TeklifYonetim.iss` ve `ui/utils/updater.py` bunu doğrular. Updater/installer belirtisinde Bölüm 2'yi tek başına son söz sayma; Bölüm 18 ve 19'u da aç, AppMutex'i geri ekleme.
