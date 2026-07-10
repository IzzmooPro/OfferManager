# Değişiklik Geçmişi

---

## [v4.0] — 2026-07-10

### Performans
- **Toplu silme çok daha hızlı:** Ürünler/Müşteriler sayfasında çok sayıda
  kaydı seçip silmek artık tek işlemde yapılıyor; binlerce kayıtta saniyeler
  yerine göz açıp kapayıncaya kadar tamamlanıyor.
- **Excel içe aktarma çok daha hızlı:** Büyük dosyalarda içe aktarma süresi
  belirgin şekilde kısaldı (10.000 satırlık bir dosya ~10 saniyeden ~1 saniyenin
  altına indi). Mükerrer kontrolü yeniden yazıldı.
- **Sekmeler arası geçiş akıcılaştı:** Ürünler/Müşteriler sekmesine her
  geçişte tablo gereksiz yere baştan kurulmuyordu; artık yalnızca veri
  değiştiğinde yenileniyor. On binlerce üründe hissedilen takılma giderildi.
- **Büyük listelerde anlık açılış:** Ürünler/Müşteriler tablosu ilk 500 kaydı
  gösterir; liste daha büyükse üstte "… ilk 500 gösteriliyor, arama yapın"
  notu çıkar. Arama ve kategori filtresi her zaman tüm veritabanında çalışır.

### Yeni
- **İçe aktarma ilerleme penceresi:** Excel içe aktarırken gerçek ilerlemeyi
  (okuma → denetleme → kaydetme, %0–100) gösteren bir pencere eklendi.

### İyileştirmeler
- **Ara kutusu daha akıcı:** Ürün/müşteri aramasında her tuş vuruşunda değil,
  yazmayı bıraktığınızda arama yapılır — çok sayıda kayıtta yazarken takılma olmaz.

---

## [v3.9] — 2026-07-10

### Yeni Özellik
- **Ürünlerde toplu silme:** Artık Ürünler sayfasında Shift/Ctrl ile birden
  fazla ürün seçip tek seferde silebilirsiniz (Müşteriler sayfasındaki gibi).
  Çok sayıda ürünle çalışırken filtreleyip topluca temizlemeyi kolaylaştırır.
  Silinen ürünlerin mevcut tekliflerdeki bilgileri değişmeden kalır.

---

## [v3.8] — 2026-07-10

### Yeni Özellik
- **Kâr Analizi paneli:** Ürünlere "Alış Fiyatı" (maliyet) eklendi. Teklif
  oluştururken, yalnızca **sizin gördüğünüz** katlanabilir bir panelde
  toplam alış/satış, kâr (₺ ve %), ve "maliyetine düşmeden en fazla ne
  kadar iskonto verebileceğiniz" canlı gösterilir. Marj durumuna göre
  yeşil/sarı/kırmızı renk uyarısı ve maliyeti girilmemiş ürün uyarısı var.
  Bu bilgiler **PDF, Excel ve e-postaya asla dahil edilmez** — müşteri görmez.

### İyileştirmeler
- **İçe aktarma — para birimi:** Fiyatları "TRY" veya "₺" ile yazılmış
  Excel dosyaları artık doğru şekilde TL olarak aktarılıyor (önceden
  yanlışlıkla EUR'a düşüyordu).
- **İçe aktarma — Excel başlıkları:** Dışa/içe aktarılan dosyalarda dar
  sütun başlıkları artık kesilmiyor.
- Çeşitli pencere düzeni ve okunabilirlik iyileştirmeleri (form hizası,
  pencere ikonu, buton yazıları, kompakt yedekleme/hakkında pencereleri,
  uzun metinlerin baştan gösterilmesi).

---

## [v3.7] — 2026-07-09

### Düzeltmeler
- **Güncelleme takılması giderildi:** Bazı durumlarda güncellenen program
  düzgün kapanmayıp kurulum "uygulamaları kapatamadı" ekranında takılıyordu.
  Kurulum artık çalışan uygulamayı en baştan kesin olarak kapatıyor; program
  da güncelleme sırasında kendini temiz şekilde sonlandırıyor. Güncelleme
  artık elle müdahale olmadan akıp gidiyor.

---

## [v3.6] — 2026-07-09

### Düzeltmeler
- **Güncelleme sırasındaki "uygulamayı kapatın" uyarısı kaldırıldı:**
  Kurulum aracı artık çalışan uygulamayı kendisi nazikçe kapatıyor
  (Restart Manager). Güncelleme daha akıcı; kullanıcının programı elle
  kapatması gerekmiyor.

---

## [v3.5] — 2026-07-09

### Düzeltmeler
- **Açılışta "Failed to load Python DLL (python314.dll)" hatası giderildi:**
  paketleme tek-dosya (onefile) modundan klasörlü (onedir) moda geçirildi.
  Program artık her açılışta kendini Temp'e açmıyor; antivirüs/Temp
  temizliği kaynaklı açılış hataları kökten ortadan kalktı.
- **Kaldırma sırasındaki "PathRedir: Not initialized" iç hatası giderildi:**
  Inno Setup 7 önizleme sürümünün, [Code] bölümü olmayan kurulumlardaki
  bilinen hatası — kurulum betiğine zararsız bir [Code] bölümü eklenerek
  atlatıldı (resmi 7.0.1 sürüm notundaki bug).
- Kurulumda "Masaüstü kısayolu oluştur" seçeneği artık varsayılan İŞARETLİ.

---

## [v3.4] — 2026-07-09

### İç / Bakım
- GitHub deposu **OfferManager** olarak yeniden adlandırıldı. Koddaki güncelleme
  kontrolü ve bağlantı referansları yeni adrese güncellendi. Eski kurulumlar
  güncellemeyi GitHub'ın otomatik yönlendirmesiyle sorunsuz almaya devam eder.

---

## [v3.3] — 2026-07-09

Bakım sürümü — güncelleme akışının (indir → UAC → kur) uçtan uca canlı
doğrulanması. Kullanıcı arayüzünde değişiklik yok.

---

## [v3.2] — 2026-07-09

### Düzeltmeler / İç
- **Güncelleme mantığı tek yere indirildi:** Hakkında penceresindeki
  "Güncelleme Kontrol Et" butonu artık tarayıcıya yönlendirmek yerine
  açılıştakiyle **aynı** uygulama-içi indir-kur diyaloğunu kullanır
  (tek kaynak: `ui/utils/updater`). Tekrar eden `_UpdateChecker` sınıfı
  ve ölü import'lar kaldırıldı.
- **Güncelleme kurulum başlatma düzeltmesi:** İndirilen kurulum artık
  `os.startfile` (ShellExecute) ile başlatılır; Inno kurulumunun yönetici
  manifesti UAC yükseltmesini tetikler. Önceki `subprocess`/CreateProcess
  yolu manifestli kurulumu yükseltemiyor ve başlatamıyordu.

---

## [v3.1] — 2026-07-09

Bakım sürümü. Arayüzde değişiklik yok; öncelikli amaç GitHub üzerinden
otomatik güncelleme akışının (indir → kur) uçtan uca doğrulanması.

### İç / Bakım
- Depo ve paketleme düzeni "dport" mantığına göre ayrıldı: kaynak + README
  GitHub'da, paketleme (spec/iss/bat) yerel; README kök dizine taşındı
- installer-tabanlı güncelleme mantığı (Inno kurulumu üzerine yazar) doğrulandı

---

## [v3.0] — 2026-07-09

Büyük sürüm: altyapı sağlamlaştırma, UX derinleştirme, yeni iş özellikleri,
raporlama ve PDF'in baştan yeniden tasarımı.

### Altyapı & Kalite
- Test kapsamı 11 → 153; `tests/conftest.py` ile izole veritabanı
- 25+ genel `except` → spesifik exception + loglama
- Service katmanına (müşteri/ürün/teklif) girdi doğrulama + type hint
- `core/` yeniden düzenlendi: `app_paths`, `config`, `constants`, `formatting`,
  `date_utils`, `credential_store` — tek kaynak ilkesi
- Türkçe sayı biçimi tüm katmanlara (UI/PDF/Excel/CSV) — `core/formatting.py`
- Veri `%LOCALAPPDATA%`'ya taşındı; program dosyalarından ayrık + tek-seferlik migration

### Yeni İş Özellikleri
- Ürün kategorileri (CRUD, atomik silme, geriye uyumlu migration)
- Teklif şablonları (JSON kalemler, tekliften şablon oluşturma)
- Geçerlilik süresi dolan tekliflerin otomatik iptali
- Müşteriler sayfasına "Teklif" / "Son Teklif" özet sütunları
- Raporlar sayfası: aylık ciro, müşteri/ürün sıralaması, dönüşüm oranı, Excel export
- Excel roundtrip: Müşteri/Ürün/Teklif içe-dışa aktarma; "Tümü tek dosya" akışı

### UX
- QtPdf tabanlı PDF önizleme (zoom, yazdır, e-posta, klasörde göster)
- Dashboard sütun genişliği hafızası, satır sıralama, tarih ISO sıralaması
- SMTP şifresi Windows Credential Manager'da (keyring); boşluk temizleme (Gmail App Password)

### PDF Yeniden Tasarımı
- `pdf/pdf_generator.py` mockup'a göre tamamen yeniden yazıldı
  (lacivert başlık bandı, ikonlu kartlar, rozetli ürün tablosu, QR alt bant)
- Tüm kullanıcı verisi XML-escape (`_esc`) — özel karakter çökmesi giderildi
- Poppins fontu gömüldü (Türkçe tam, kompakt)

### Bu Sürümdeki Temizlikler
- `requirements.txt`'ten kullanılmayan `matplotlib` bağımlılığı kaldırıldı
- `discount_type` varsayılanı tüm katmanlarda `'amount'`'a eşitlendi (şema + model)
- `get_all_customer_summaries` sorgusundaki kullanılmayan `ok`/`wait` sütunları silindi

---

## [v2.0] — 2026-06-20

### Bug Düzeltmeleri (7)
- **Müşteri silme:** Teklif sayısı uyarısı hiç çalışmıyordu (dataclass `.get()` hatası) — düzeltildi
- **PDF satır sonu:** Config'deki `\n` kaçış dizisi PDF'de literal görünüyordu — `_load_company()` düzeltildi
- **Otomatik müşteri kaydı:** Telefon ve e-posta alanları boş kaydediliyordu — form alanlarından alınıyor
- **PDF çift sayfa:** `_NumberedCanvas` çok sayfalı belgelerde sayfaları iki kez basıyordu — düzeltildi
- **PDF miktar formatı:** Tam sayı miktarlar "1.0" yerine "1" gösteriyor
- **Koyu tema bağlantıları:** Hakkında dialogunda linkler siyah hardcoded — tema rengi kullanılıyor
- **Ölü kod:** Kullanılmayan `_SmartSpinBox` sınıfı temizlendi

### Mimari İyileştirmeler
- **Config DRY:** 3 dosyadaki config kopyası kaldırıldı, tek merkezi `core/config.py` modülü oluşturuldu
- **DB schema cache:** `close()` sonrası `get_db()` çağrılırsa gereksiz migration tekrar çalışmıyor
- **PdfWorker bellek temizliği:** `deleteLater()` ile QThread temizleniyor
- **Temp PDF temizliği:** Önizleme temp dosyaları özel dizinde temizleniyor
- **Kullanılmayan import temizliği:** `CFG_PATH` vb. kaldırıldı

### Yeni Özellikler
- **Tema kalıcılığı:** Açık/koyu tema tercihi `DATA_DIR/theme.txt`'ye kaydedilip başlangıçta okunuyor
- **PDF sayfa numarası:** Çok sayfalı belgelerde "Sayfa X / Y" (tek sayfalıda gizli)
- **PDF bölüm toggle'ları:** 8 PDF alanı ayrı ayrı "PDF'de göster" checkbox'u ile gizlenebilir/gösterilebilir
- **StatusBar:** "Teklif kaydedildi", "Yedek alındı — 14:30", "Tema: Koyu" bildirimleri
- **Boş tablo mesajı:** "Henüz teklif oluşturulmamış" / "Aramanıza uygun teklif bulunamadı"
- **Toplu durum değiştirme:** Birden fazla teklif seçip hepsinin durumunu birden değiştirme
- **Export butonları:** "Dışa Aktar ▾" dropdown (Excel/CSV) toolbar'a ve context menüye bağlandı
- **Scroll pozisyonu:** Düzenleme sonrası listeye dönünce aynı yerde kalıyor
- **Klavye kısayolları:** Ctrl+E (Düzenle), Ctrl+D (Kopyala) eklendi
- **Kopyalama bildirimi:** StatusBar'da "Teklif kopyalandı" mesajı
- **Tarih aralığı filtresi:** Filtre panelinde başlangıç — bitiş tarih seçiciler
- **Gelişmiş filtre paneli:** Para birimi + tutar aralığı filtreleri (SQL tarafında)
- **Müşteri geçmişi erişimi:** Dashboard sağ tık → "Müşteri Geçmişi" + Müşteriler sayfasında "Geçmiş" butonu
- **Splash screen:** Animasyonlu progress bar, gerçek yükleme adımları, fade-out geçişi
- **Ürün tablosu Undo:** Satır silinince Ctrl+Z ile geri alma + statusbar bildirimi
- **Müşteri notu:** Müşteri formuna not/açıklama alanı (DB migration ile geriye uyumlu)

### Koyu Tema Elden Geçirme
- Step indicator pending kutuları: beyaz → koyu kart rengi
- Step bağlantı çizgisi: açık gri → tema border rengi
- Logo/İmza önizleme kutuları: beyaz → `paintEvent` ile tam tema uyumu
- Dashboard ayırıcı, progress bar boş durumu → tema renkleri
- İskonto alanı: hardcoded stil → QSS tema sistemi
- Tüm hint label'lar (`color:#888/#999/#666/#555`) → `hint_label` objectName + QSS
- Backup uyarı kutusu: sarı → koyu temada amber tonları
- Excel import bilgi kutuları: okunmaz → HTML span rengi + tema arka plan
- Email dialog ayırıcı + hint → tema renkleri
- Help dialogs açıklama/bağlantı/özellik metinleri → tema renkleri
- SpinBox okları: kaba dolgulu üçgen → ince çizgi chevron (RoundCap + RoundJoin)
- Checkbox stili: kare kutucuk + mavi arka plan + beyaz checkmark ikonu

### UI İyileştirmeleri
- Dialog'lar büyütülünce form elemanları dağılmıyordu (maxHeight + addStretch)
- PDF Ayarları kompakt tasarım: ayrı kartlar → tek satırlık kompakt alanlar
- Toolbar buton genişlikleri: fixedWidth → otomatik genişlik (yazılar kesilmiyordu)
- Hover animasyon: `pos()` animasyonu (layout bozuyordu) → `contentsMargins` animasyonu

### Güncelleme & Versiyon
- Sürüm v1.0 → v2.0 (tüm referanslar güncellendi)
- Güncelleme scripti: `taskkill /PID` ile eski process'i zorla kapatma + retry mekanizması

---

## [v1.0] — 2026-03-14

İlk kararlı sürüm.

- 3 adımlı teklif sihirbazı
- Profesyonel PDF çıktısı (logo, imzalar, Türkçe karakter)
- Ürün ve müşteri yönetimi (CRUD, Excel/CSV import)
- Dashboard, arama, filtre, durum takibi
- Excel/CSV export
- Çoklu para birimi (TL / EUR / USD)
- Açık/Koyu tema
- Otomatik yedekleme ve geri yükleme
- GitHub tabanlı otomatik güncelleme sistemi
- Şirket ayarları (logo, imza, yetkili bilgileri)
- F1 yardım penceresi
- Tek örnek kontrolü
