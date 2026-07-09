# Teklif Yönetim Sistemi — Yol Haritası v3.0

> Son güncelleme: 2026-06-26
> Mevcut sürüm: v2.0
> Hedef sürüm: v3.0

---

## Genel Bakış

Bu yol haritası, v2.0 üzerinden v3.0'a geçiş planıdır. Her faz kendi içinde
tamamlanabilir bir bütündür — bir faz bitmeden sonrakine geçilmez.
Fazlar "temelden çatıya" sıralanmıştır: önce altyapı sağlamlaştırılır,
sonra yeni özellikler eklenir.

### Faz Özeti

| Faz | Ad | Madde Sayısı | Öncelik | Tahmini İş |
|-----|-----|:---:|---------|------------|
| 1 | Altyapı Sağlamlaştırma | 5 | Kritik | Orta |
| 2 | Kullanıcı Deneyimi İyileştirmeleri | 5 | Yüksek | Orta |
| 3 | Yeni İş Özellikleri | 4 | Yüksek | Büyük |
| 4 | Analiz ve Raporlama | 2 | Orta | Orta |
| 5 | Uluslararasılaştırma | 2 | Düşük | Büyük |

---

## Faz 1 — Altyapı Sağlamlaştırma (Kritik)

> **Felsefe:** Yeni özellik eklemeden önce mevcut temeli sağlamlaştır.
> Bu faz kullanıcıya görünür bir değişiklik yapmaz ama sonraki tüm
> fazların güvenle yapılabilmesini sağlar.

### 1.1 Test Kapsamını Genişletmek

**Neden ilk bu?** Sonraki fazlarda onlarca dosya değişecek. Testler olmadan
"bu değişiklik başka bir şeyi bozdu mu?" sorusuna cevap veremeyiz.

#### Yapılacaklar:

- [ ] **CustomerService birim testleri** (`tests/test_customer_service.py`)
  - `add()` — başarılı ekleme, id dönüyor mu?
  - `add()` — boş firma adıyla ekleme (hata vermeli mi?)
  - `get_by_id()` — var olan / var olmayan id
  - `search()` — büyük/küçük harf duyarsızlık, Türkçe karakter (ş, ç, ğ, ü, ö, ı)
  - `update()` — mevcut müşteri güncelleme
  - `delete()` — teklifi olan müşteri silinebilmeli mi? (FK ilişkisi)
  - `count()` — boş DB'de 0, ekleme sonrası doğru sayı

- [ ] **ProductService birim testleri** (`tests/test_product_service.py`)
  - `add()` — başarılı ekleme
  - `add()` — aynı product_code ile tekrar ekleme (UNIQUE ihlali)
  - `get_by_code()` — büyük/küçük harf duyarsızlık
  - `search()` — kod, ad, açıklama alanlarında arama
  - `update()` — fiyat güncelleme, stok güncelleme
  - `delete()` — teklif kaleminde kullanılan ürün silinirse ne olur?

- [ ] **OfferService birim testleri** (`tests/test_offer_service.py`)
  - `save()` — başarılı kayıt, atomik transaction doğrulama
  - `save()` — boş kalem listesi (ValueError)
  - `save()` — negatif miktar (ValueError)
  - `save()` — iskonto > ara toplam (ValueError)
  - `save()` — eşzamanlı kayıt (thread safety, EXCLUSIVE lock)
  - `generate_and_commit_offer_no()` — ardışık numara üretimi
  - `get_filtered()` — her filtre kombinasyonu
  - `get_revenue_summary()` — iptal edilmiş teklifler hariç mi?
  - `delete()` — PDF dosyası da siliniyor mu?
  - `update_status()` — geçersiz durum adı

- [ ] **ExportService birim testleri** (`tests/test_export_service.py`)
  - `export_excel()` — dosya oluşuyor mu, header doğru mu?
  - `export_csv()` — UTF-8-SIG encoding, noktalı virgül ayracı
  - Çoklu para birimli teklif listesinde toplam satırları

- [ ] **DocumentService birim testleri** (`tests/test_document_service.py`)
  - `generate_offer_summary_html()` — HTML çıktı doğrulama
  - Boş kalem listesiyle çağrılırsa ne olur?
  - İskonto sıfırken iskonto satırı gösterilmemeli

- [ ] **Backup & Restore testleri** (`tests/test_backup.py`)
  - Yedek oluşturma — ZIP dosyası geçerli mi, içinde ne var?
  - Geri yükleme — DB bütünlüğü korunuyor mu?
  - Bozuk ZIP ile geri yükleme — hata mesajı doğru mu?
  - Max 20 yedek sınırı — eski yedekler siliniyor mu?

- [ ] **Config testleri** (`tests/test_config.py`)
  - `load_company_config()` — dosya yokken default'lar geliyor mu?
  - `save_company_config()` — atomik yazma (.tmp → rename)
  - Çok satırlı değerler (\\n escape) doğru kaydediliyor/okunuyor mu?

- [ ] **Date utils testleri** (`tests/test_date_utils.py`)
  - `to_storage_date()` — dd.MM.yyyy → YYYY-MM-DD dönüşümü
  - `to_display_date()` — YYYY-MM-DD → dd.MM.yyyy dönüşümü
  - Geçersiz tarih formatıyla ne olur?
  - Boş string girişi

- [ ] **Credential store testleri** (`tests/test_credential_store.py`)
  - `keyring_available()` — keyring yokken False dönmeli
  - `get_smtp_password()` — kayıt yokken boş string dönmeli

#### Etkilenen dosyalar:
- `tests/` altına yeni dosyalar eklenir
- Mevcut kod DEĞİŞMEZ — sadece test eklenir

#### Risk: ⚪ Sıfır
Mevcut koda dokunulmaz, sadece yeni test dosyaları eklenir.

---

### 1.2 Hata Yönetimini İyileştirmek

**Neden?** Şu an bazı yerlerde `except Exception: pass` var. Bir şey
bozulduğunda log'da iz yok, kullanıcı "neden olmadı?" diye kalıyor.

#### Yapılacaklar:

- [ ] **Bare except taraması** — tüm dosyalarda `except Exception: pass`
  ve `except:` kalıplarını bul
- [ ] Her birini spesifik exception tipiyle değiştir:
  - `FileNotFoundError` — dosya bulunamadı
  - `sqlite3.IntegrityError` — DB kısıt ihlali (UNIQUE, FK)
  - `sqlite3.OperationalError` — DB kilidi, tablo yok
  - `PermissionError` — dosya izni yok
  - `OSError` — disk dolu, ağ hatası
  - `ValueError` — geçersiz veri formatı
- [ ] Yakalanan her hatayı `logger.warning()` veya `logger.error()` ile logla
- [ ] Kullanıcıya gösterilmesi gereken hatalarda anlaşılır Türkçe mesaj

#### Tespit edilen bare except lokasyonları (tam liste):

| Dosya | Satır | Durum |
|-------|-------|-------|
| `main.py` | 51, 202, 234 | `except Exception: pass` — MessageBox ve log |
| `core/app_paths.py` | 88, 93 | `except Exception: pass` — migrasyon |
| `core/config.py` | 32 | `except Exception: pass` — config okuma |
| `core/constants.py` | 40 | `except Exception:` — tema okuma fallback |
| `core/credential_store.py` | 27 | `except Exception: pass` — keyring silme |
| `database/db_manager.py` | 108 | `except Exception: pass` — index oluşturma |
| `pdf/pdf_generator.py` | 246, 254, 666 | `except Exception: pass` — temp dosya silme, imza yükleme |
| `ui/dashboard_page.py` | 690 | `except Exception: pass` — ciro format |
| `ui/products_page.py` | 153, 181 | `except Exception: pass` — ürün kod kontrolü |
| `ui/settings_page.py` | 548, 559 | `except Exception: pass` — logo/imza silme |
| `ui/dialogs/backup_manager.py` | 49, 360, 642 | `except Exception: pass` — meta, timer, restart |
| `ui/customers_page.py` | 207 | `except Exception:` — ilişkili teklif sayısı |

#### Etkilenen dosyalar:
- `pdf/pdf_generator.py` — font yükleme, logo yükleme, temp dosya temizliği
- `main.py` — MessageBox, log, exception hook
- `ui/main_window.py` — closeEvent
- `ui/dashboard_page.py` — PDF worker, export, ciro formatı
- `ui/settings_page.py` — logo/imza kaydetme ve silme
- `ui/products_page.py` — ürün kodu kontrol
- `ui/customers_page.py` — ilişkili teklif sayısı
- `ui/dialogs/backup_manager.py` — yedek/geri yükleme, meta, timer
- `database/db_manager.py` — migration except blokları, index
- `core/app_paths.py` — eski veri migrasyonu
- `core/config.py` — config dosyası okuma
- `core/credential_store.py` — keyring işlemleri

#### Risk: 🟡 Düşük
Sadece except blokları değişir, iş mantığı aynı kalır. Ama her değişiklik
sonrası ilgili özelliği test etmek şart.

---

### 1.3 Girdi Doğrulama (Validation) Güçlendirmek

**Neden?** Bazı servis metotlarında girdi doğrulama eksik. Örneğin
`CustomerService.add()` boş firma adını kabul ediyor,
`CustomerService.get_by_id()` row None dönünce `from_row(None)` patlar.

#### Yapılacaklar:

- [ ] **CustomerService.get_by_id()** — `row` None ise `None` döndür
  (şu an `Customer.from_row(None)` çağırıyor → hata)
- [ ] **CustomerService.add()** — `company_name` boş/None ise `ValueError` fırlat
- [ ] **ProductService.add()** — `product_code` ve `product_name` boş ise `ValueError`
- [ ] **OfferService.save()** — `customer_id` veya `company_name` ikisi de
  boşsa uyarı (teklif kime ait?)
- [ ] **Config okuma güvenliği** — `load_company_config()` bozuk dosyada
  sessizce default'a dönüyor ama loglamıyor → log ekle
- [ ] **PDF girdi temizliği** — `_safe_str()` fonksiyonu var ama tüm
  kullanıcı girdileri bu fonksiyondan geçiyor mu kontrol et

#### Etkilenen dosyalar:
- `services/customer_service.py` — get_by_id, add
- `services/product_service.py` — add
- `services/offer_service.py` — save
- `core/config.py` — load_company_config

#### Risk: 🟡 Düşük
Sadece kontrol ekleniyor, mevcut başarılı akışlar etkilenmez.

---

### 1.4 Type Hint Tamamlamak

**Neden?** IDE otomatik tamamlaması daha iyi çalışır, hatalar daha erken
yakalanır, yeni özellik eklerken hangi fonksiyon ne döndürüyor anlaşılır.

#### Yapılacaklar:

- [ ] Tüm service metotlarına parametre ve dönüş tipi ekle
- [ ] Tüm model dataclass alanlarının tipleri doğru mu kontrol et
- [ ] `db_manager.py` — `fetchone` → `Optional[sqlite3.Row]`
- [ ] `db_manager.py` — `fetchall` → `List[sqlite3.Row]`
- [ ] `core/config.py` — `load_company_config() -> dict[str, str]`
- [ ] `core/config.py` — `save_company_config(data: dict[str, str]) -> None`
- [ ] `core/credential_store.py` — tüm fonksiyonlara dönüş tipi
- [ ] `core/date_utils.py` — parametre ve dönüş tipleri
- [ ] `services/document_service.py` — `generate_offer_summary_html` dönüş tipi
- [ ] `services/export_service.py` — `export_excel`, `export_csv` fonksiyon imzaları

#### Etkilenen dosyalar:
- `services/*.py`
- `database/db_manager.py`
- `core/*.py` (config, credential_store, date_utils, app_paths)

#### Risk: ⚪ Sıfır
Sadece tip bilgisi eklenir, çalışma mantığı değişmez.

---

### 1.5 Çift Dosya / Ölü Kod Temizliği

**Neden?** Proje kökünde ve alt klasörlerde aynı dosyanın birden fazla
kopyası var. Eski refaktörden kalan dosyalar ileride karışıklık yaratır.

#### Yapılacaklar:

- [ ] **email_dialog.py çift kopya** — `ui/email_dialog.py` ve
  `ui/dialogs/email_dialog.py` → hangisi aktif tespit et, diğerini sil
- [ ] **Kullanılmayan import taraması** — tüm dosyalarda kullanılmayan
  import'lar var mı kontrol et
- [ ] **git status temizliği** — silinmiş olarak görünen ama git'te takip
  edilen eski dosyaları düzelt (kök dizindeki `app_paths.py`, `constants.py`,
  `ico.ico` vb. `core/` ve `assets/` altına taşınmış)
- [ ] **`.claude/worktrees/` artıkları** — eski worktree klasörlerinin
  temizlenmesi (ana projeyle karışmaması için)

#### Etkilenen dosyalar:
- `ui/email_dialog.py` (muhtemelen silinecek)
- Kök dizindeki eski dosya referansları

#### Risk: ⚪ Sıfır
Kullanılmayan dosyaların silinmesi.

---

## Faz 2 — Kullanıcı Deneyimi İyileştirmeleri (Yüksek)

> **Felsefe:** Mevcut özellikleri daha kullanışlı yap.
> Yeni özellik değil, var olanın kalitesini artır.

### 2.1 Uygulama İçi PDF Önizleme

**Neden?** Şu an PDF görmek için harici program açılıyor.
Kullanıcı programdan çıkmak zorunda kalmamalı.

#### Yapılacaklar:

- [ ] `ui/dialogs/pdf_preview_dialog.py` oluştur
  - QDialog içinde PDF görüntüleyici
  - Yakınlaştır/Uzaklaştır kontrolleri
  - Sayfa navigasyonu (çok sayfalı PDF'ler için)
  - "Klasörde Göster" butonu
  - "E-posta Gönder" butonu (doğrudan EmailDialog'a bağla)
  - "Yazdır" butonu
- [ ] Dashboard sağ tık menüsüne "PDF Önizle" ekle
- [ ] Teklif oluşturma son adımında otomatik önizleme göster
- [ ] Çift tıklama ile önizleme açma

#### Etkilenen dosyalar:
- YENİ: `ui/dialogs/pdf_preview_dialog.py`
- `ui/dashboard_page.py` — sağ tık menü + çift tıklama
- `ui/create_offer_page.py` — son adım önizleme

#### Risk: 🟡 Düşük
Yeni dialog ekleniyor, mevcut kod minimal değişir (menüye yeni item ekleme).

---

### 2.2 Teklif Düzenleme İyileştirmeleri

**Neden?** Mevcut düzenleme akışında küçük ama rahatsız edici eksikler var.

#### Yapılacaklar:

- [ ] **Ürün arama autocomplete** — ürün eklerken ürün kodunu yazmaya
  başlayınca öneri listesi çıksın (mevcut ürün kataloğundan)
- [ ] **Satır sıralama (drag & drop)** — teklif kalemlerinin sırasını
  sürükleyerek değiştirme
- [ ] **Satır kopyalama** — mevcut bir kalemi kopyalayıp miktar/fiyat
  değiştirme (benzer ürünler için)
- [ ] **Tab ile gezinme** — teklif formunda Tab tuşuyla alanlar arası
  doğal gezinme sırası

#### Etkilenen dosyalar:
- `ui/create_offer_page.py` — ürün tablosu, kalem ekleme alanı

#### Risk: 🟡 Düşük
Teklif oluşturma sayfası değişir ama kayıt mantığı (`OfferService.save`)
aynı kalır.

---

### 2.3 Dashboard Tablo İyileştirmeleri

**Neden?** Büyük veri setlerinde (yüzlerce teklif) performans ve
kullanılabilirlik iyileştirmesi gerekir.

#### Yapılacaklar:

- [ ] **Sütun sıralama** — her sütun başlığına tıklayarak artan/azalan
  sıralama (tarih, tutar, firma adı, durum)
- [ ] **Sayfalama (pagination)** — 50+ teklif olduğunda sayfalama veya
  sanal kaydırma (virtual scrolling) ile performans
- [ ] **Sütun genişliği hafıza** — kullanıcının ayarladığı sütun
  genişlikleri kapanıp açınca hatırlansın
- [ ] **Satır seçimi iyileştirmesi** — Shift+Click ile aralık seçme,
  Ctrl+Click ile tekli seçme

#### Etkilenen dosyalar:
- `ui/dashboard_page.py` — OfferTableModel, QTableView ayarları

#### Risk: 🟡 Düşük
Model katmanı değişmez, sadece UI katmanında görünüm iyileştirmesi.

---

### 2.4 Ayarlar Sayfası İyileştirmeleri

**Neden?** SMTP test bağlantısı var ama sonuç geri bildirimi zayıf.
PDF şablon metinleri düzenlemesi daha kullanışlı olabilir.

#### Yapılacaklar:

- [ ] **PDF şablon önizleme** — metin düzenlerken sağ tarafta canlı
  önizleme (değişiklik anında PDF'de nasıl görüneceğini göster)
- [ ] **SMTP şifre görünürlük toggle** — şifre alanında göz ikonu ile
  göster/gizle
- [ ] **Ayarlar değişiklik takibi** — kaydedilmemiş değişiklik varsa
  sayfa değiştirirken uyarı (teklif sayfasında var, ayarlarda yok)
- [ ] **Ayarlar sıfırlama** — "Varsayılana Dön" butonu (tek tek veya
  toplu olarak factory reset)

#### Etkilenen dosyalar:
- `ui/settings_page.py`

#### Risk: 🟡 Düşük
Sadece UI değişiklikleri.

---

### 2.5 Excel Import İyileştirmeleri

**Neden?** Mevcut import sistemi çalışıyor ama hata durumunda
kullanıcıya yetersiz geri bildirim veriyor.

#### Yapılacaklar:

- [ ] **Satır bazlı hata raporu** — hangi satırda ne hata var detaylı göster
- [ ] **Kısmi import** — hatalı satırları atla, başarılı olanları kaydet
  (şu an ya hepsi ya hiçbiri)
- [ ] **Mükerrer kontrol** — import sırasında mevcut kayıtlarla çakışma
  kontrolü (aynı ürün kodu, aynı firma adı)
- [ ] **Güncelleme modu** — mevcut kaydı güncelle veya atla seçeneği

#### Etkilenen dosyalar:
- `ui/utils/excel_import.py`

#### Risk: 🟡 Düşük
Import mantığı değişir ama mevcut veriye zarar vermez (yeni kayıt ekleme).

---

## Faz 3 — Yeni İş Özellikleri (Yüksek)

> **Felsefe:** Kullanıcının günlük işini hızlandıran yeni yetenekler.

### 3.1 Teklif Şablon Sistemi

**Neden?** Kullanıcı benzer teklifleri tekrar tekrar hazırlıyor.
Sık kullanılan ürün kombinasyonlarını şablon olarak kaydetmek
büyük zaman kazandırır.

#### Yapılacaklar:

- [ ] **DB: `offer_templates` tablosu**
  ```
  id, template_name, currency, items_json, created_at
  ```
- [ ] **"Şablon Olarak Kaydet"** — mevcut bir teklifteki kalemleri
  şablon olarak kaydetme
- [ ] **"Şablondan Oluştur"** — yeni teklif oluştururken şablon seçme,
  kalemler otomatik doldurulur
- [ ] **Şablon yönetimi** — şablonları listele, sil, yeniden adlandır

#### Etkilenen dosyalar:
- `database/schema.sql` — yeni tablo
- `database/db_manager.py` — migration (yeni tablo)
- YENİ: `services/template_service.py`
- YENİ: `models/template.py`
- `ui/create_offer_page.py` — şablon seçme UI
- `ui/dashboard_page.py` — sağ tık → "Şablon Olarak Kaydet"

#### Risk: 🟢 Orta
Yeni tablo + yeni servis. Mevcut tablolara dokunulmaz ama
create_offer_page değişir — dikkatli test gerekir.

---

### 3.2 Ürün Kategorileri

**Neden?** Ürün sayısı arttıkça katalogda arama zorlaşır.
Kategorilere ayırmak hem aramayı hem de raporlamayı kolaylaştırır.

#### Yapılacaklar:

- [ ] **DB: `product_categories` tablosu**
  ```
  id, name, parent_id (NULL = ana kategori), sort_order
  ```
- [ ] **products tablosuna `category_id` sütunu** (FK, nullable — geriye uyumlu)
- [ ] Ürünler sayfasında kategori filtresi (dropdown veya ağaç yapısı)
- [ ] Teklif oluştururken kategori bazlı ürün filtreleme
- [ ] Kategorisiz ürünler "Genel" altında görünsün

#### Etkilenen dosyalar:
- `database/schema.sql` — yeni tablo + products'a sütun
- `database/db_manager.py` — migration
- YENİ: `services/category_service.py`
- YENİ: `models/category.py`
- `services/product_service.py` — kategori filtresi ekleme
- `ui/products_page.py` — kategori UI
- `ui/create_offer_page.py` — ürün seçerken kategori filtresi

#### Risk: 🟢 Orta
products tablosuna nullable sütun eklenir (migration ile güvenli).
Mevcut ürünler category_id=NULL olarak kalır, hiçbir şey bozulmaz.

---

### 3.3 Teklif Geçerlilik Hatırlatıcısı

**Neden?** "Beklemede" kalan teklifin süresi dolmuş olabilir.
Kullanıcı bunu takip edemiyorsa fırsat kaçar.

#### Yapılacaklar:

- [ ] **Geçerlilik tarihi hesaplama** — `date + validity (gün)` ile
  son geçerlilik tarihi
- [ ] **Dashboard'da görsel uyarı:**
  - Süresi 3 gün içinde dolacak → sarı ikon
  - Süresi dolmuş → kırmızı ikon
  - Süresi geçmiş + hâlâ "Beklemede" → kalın kırmızı vurgu
- [ ] **Başlangıçta uyarı dialogu** — program açılınca süresi dolan
  teklifler varsa bildirim göster
- [ ] **İstatistik kartına ekleme** — "Süresi Dolan: X teklif" kartı

#### Etkilenen dosyalar:
- `ui/dashboard_page.py` — OfferTableModel renklendirme, yeni kart
- `main.py` — başlangıç kontrolü (opsiyonel)
- `services/offer_service.py` — `get_expiring_offers(days=3)` metodu

#### Risk: 🟡 Düşük
Sadece okuma işlemi + UI renklendirme. Veri değişmez.

---

### 3.4 Müşteri İletişim Geçmişi

**Neden?** Müşteriye son ne zaman teklif verildi, kaçı onaylandı —
bu bilgi müşteri kartında görünmeli.

#### Yapılacaklar:

- [ ] **Müşteri kartında özet istatistik:**
  - Toplam teklif sayısı
  - Onaylanan / İptal / Beklemede sayıları
  - Toplam ciro (para birimi bazlı)
  - Son teklif tarihi
- [ ] **Müşteri geçmişi dialogunda** teklif detaylarını genişletme
  (tıklayınca kalemleri göster)

#### Etkilenen dosyalar:
- `ui/dialogs/customer_history_dialog.py` — detay genişletme
- `ui/customers_page.py` — özet istatistik gösterimi
- `services/offer_service.py` — `get_customer_summary(customer_id)` metodu

#### Risk: 🟡 Düşük
Sadece yeni sorgu + UI gösterimi.

---

## Faz 4 — Analiz ve Raporlama (Orta)

> **Felsefe:** Veriden anlam çıkart, iş kararlarını destekle.

### 4.1 Dashboard Grafikleri

**Neden?** Sayılar tablo halinde var ama görselleştirme yok.
Bir bakışta trendi görmek çok daha etkili.

#### Yapılacaklar:

- [ ] **Aylık ciro trendi** (çizgi grafik)
  - Son 12 ay, para birimi bazlı
  - Geçen yılla karşılaştırma (opsiyonel)
- [ ] **Teklif durum dağılımı** (pasta/halka grafik)
  - Beklemede / Onaylandı / İptal yüzdeleri
- [ ] **En çok teklif verilen müşteriler** (yatay bar grafik)
  - İlk 10 müşteri, teklif sayısı veya ciro bazlı
- [ ] **Aylık teklif sayısı** (bar grafik)
  - Son 12 ay, yeni teklif adedi

#### Teknik seçenekler:
- **Seçenek A:** `matplotlib` ile statik grafik → QLabel'da QPixmap olarak göster
- **Seçenek B:** `pyqtgraph` ile interaktif grafik (hover, zoom)
- **Önerim:** Seçenek A ile başla (ek bağımlılık minimum), sonra gerekirse B'ye geç

#### Etkilenen dosyalar:
- `ui/dashboard_page.py` — grafik alanı ekleme
- `services/offer_service.py` — `get_monthly_revenue(months=12)`,
  `get_top_customers(limit=10)` gibi sorgu metotları
- `docs/requirements.txt` — matplotlib eklenmesi (Seçenek A ise)

#### Risk: 🟢 Orta
Yeni bağımlılık (matplotlib) + dashboard layout değişikliği.
Mevcut tablo ve kartlara dokunulmaz, altına grafik alanı eklenir.

---

### 4.2 Detaylı Raporlama Modülü

**Neden?** "Bu ay ne kadar iş yaptık?", "Hangi müşteriden en çok
kazandık?", "Teklif dönüşüm oranımız kaç?" sorularına tek tıkla cevap.

#### Yapılacaklar:

- [ ] **Yeni sayfa: Raporlar** (sidebar'a 6. sayfa olarak ekle)
- [ ] **Rapor tipleri:**
  - Aylık/yıllık ciro raporu (para birimi bazlı)
  - Müşteri bazlı analiz (ciro, teklif sayısı, dönüşüm oranı)
  - Ürün bazlı analiz (en çok teklif edilen, toplam miktar)
  - Teklif dönüşüm oranı (Onaylanan / Toplam %)
  - Ortalama teklif tutarı trendi
- [ ] **Rapor çıktıları:**
  - Ekranda tablo + grafik
  - Excel'e aktar butonu
  - PDF rapor çıktısı (opsiyonel)
- [ ] **Tarih filtresi** — raporlar için tarih aralığı seçimi

#### Etkilenen dosyalar:
- YENİ: `ui/reports_page.py`
- YENİ: `services/report_service.py`
- `ui/main_window.py` — sidebar'a "Raporlar" ekleme, stack'e sayfa ekleme
- NAV_CARDS listesi güncellenmeli

#### Risk: 🟢 Orta
Tamamen yeni modül. Mevcut koda etkisi sadece main_window'a yeni
sayfa ekleme. Servis katmanı sadece SELECT sorguları çalıştırır.

---

## Faz 5 — Uluslararasılaştırma (Düşük — İleride)

> **Felsefe:** Uluslararası müşterilerle çalışıyorsan gerekli,
> yoksa ertelenebilir.

### 5.1 Çoklu Dil Desteği (i18n)

#### Yapılacaklar:

- [ ] **Dil dosyaları sistemi** — `locales/tr.json`, `locales/en.json`,
  `locales/de.json`
- [ ] **PDF dil seçimi** — teklif oluştururken "PDF Dili" dropdown
  - Türkçe / İngilizce / Almanca
  - Sadece PDF içeriği değişir, arayüz dili ayrı
- [ ] **Arayüz dili** — Ayarlar'dan arayüz dilini değiştirme
  (tüm etiketler, menüler, dialoglar)
- [ ] **Tarih/sayı formatı** — dile göre otomatik
  (1.234,56 ↔ 1,234.56)

#### Risk: 🔴 Yüksek
Tüm UI dosyalarında string değişikliği. Çok geniş kapsamlı.
En son yapılmalı.

---

### 5.2 Otomatik Döviz Kuru

#### Yapılacaklar:

- [ ] **Günlük kur çekme** — TCMB veya Exchange Rate API
- [ ] **Teklif oluştururken kur gösterimi** — "1 EUR = X TL" bilgisi
- [ ] **Ayarlar'da API seçimi** — hangi kaynak kullanılsın
- [ ] **Çevrimdışı mod** — internet yoksa son bilinen kur

#### Risk: 🟢 Orta
Dış API bağımlılığı. Çevrimdışı fallback gerekli.

---

## Versiyon Stratejisi

| Faz | Çıkacak Sürüm | Notlar |
|-----|---------------|--------|
| Faz 1 tamamlandığında | v2.1 | Altyapı, kullanıcı görmez ama temel sağlam |
| Faz 2 tamamlandığında | v2.5 | UX iyileştirmeleri, PDF önizleme |
| Faz 3 tamamlandığında | v3.0 | Yeni iş özellikleri — büyük sürüm |
| Faz 4 tamamlandığında | v3.5 | Raporlama, grafikler |
| Faz 5 tamamlandığında | v4.0 | Uluslararası destek |

---

## Temel Kurallar

1. **Geriye uyumlu ol** — Yeni DB sütunu = nullable + DEFAULT değer.
   Mevcut veriler asla bozulmaz.
2. **Atomik migration** — Her DB değişikliği `_migrate()` içinde
   idempotent (tekrar çalışsa da hata vermez).
3. **Özellik tamamlanmadan sürüm çıkma** — Yarım özellik kullanıcıya ulaşmaz.
4. **Her faz sonunda test çalıştır** — `build_exe.bat` zaten bunu yapıyor.
5. **CHANGELOG'u güncel tut** — Her anlamlı değişiklik kaydedilir.
6. **Yedekleme uyumluluğu** — Yeni tablo/sütun eklenince backup restore
   akışı da güncellenmeli (eski yedek + yeni şema = migration çalışmalı).
7. **Installer güncelle** — Yeni bağımlılık (matplotlib vb.) eklenince
   `TeklifYonetim.spec`, `docs/requirements.txt` ve `build_exe.bat` güncelle.
8. **Tema uyumu** — Her yeni UI bileşeni açık ve koyu temada test edilmeli.

---

## Sonraki Büyük Hedef: Web Versiyonu

_(Bu masaüstü sürümü olgunlaştıktan sonra)_

- FastAPI + HTMX + TailwindCSS + PostgreSQL
- Mevcut `models/`, `services/`, `pdf/`, `core/` katmanları aynen kullanılır
- Sadece `ui/` katmanı web şablonlarıyla değişir
- Detaylar için ayrı bir planlama belgesi hazırlanacak

---

## Geliştirici

- GitHub: [IzzmooPro/offer_management_system](https://github.com/IzzmooPro/offer_management_system)
- E-posta: IzzmooPro@gmail.com
