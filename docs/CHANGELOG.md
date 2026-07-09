# Değişiklik Geçmişi

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
