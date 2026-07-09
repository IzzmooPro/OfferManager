# Teklif Yönetim Sistemi — v2.0

Profesyonel teklif, ürün ve müşteri yönetimi için Windows masaüstü uygulaması.

---

## Özellikler

- 3 adımlı teklif sihirbazı (Müşteri → Ürünler → Özet & PDF)
- Profesyonel PDF teklif çıktısı (logo, imzalar, sayfa numarası, Türkçe karakter)
- PDF bölüm toggle'ları — 8 alan ayrı ayrı gösterilebilir/gizlenebilir
- Ürün ve müşteri yönetimi (CRUD, Excel/CSV import)
- Müşteri notu alanı
- Dashboard — istatistik kartları, ciro özeti, arama, durum filtresi
- Gelişmiş filtre paneli — tarih aralığı, para birimi, tutar aralığı
- Toplu durum değiştirme, teklif kopyalama
- Excel/CSV export (teklif listesi)
- Çoklu para birimi (TL / EUR / USD)
- Açık/koyu tema (kalıcı — kapatıp açınca korunur)
- Otomatik yedekleme ve geri yükleme
- GitHub tabanlı otomatik güncelleme sistemi
- E-posta ile PDF gönderimi (SMTP)
- Müşteri teklif geçmişi
- Splash screen (animasyonlu yükleme ekranı)
- Ürün tablosunda Undo (Ctrl+Z)
- StatusBar bildirimleri
- Tek örnek kontrolü (çift program açılmaz)

---

## Ekran Görüntüleri

![Koyu Tema](screenshots/D1.png)
![Açık Tema](screenshots/L1.png)

---

## Gereksinimler

- Windows 10 veya üzeri
- Python 3.12 veya üzeri

---

## Kurulum

### Kullanıcı
Proje klasöründeki `Baslat.bat` dosyasına çift tıklayın. Eksik bileşenler otomatik kurulur.

### Geliştirici
```bat
pip install -r docs\requirements.txt
python main.py
```

---

## Kısayollar

| Kısayol  | İşlev                        |
|----------|------------------------------|
| F1       | Yardım penceresi aç / kapat  |
| Ctrl+T   | Tema değiştir (açık/koyu)    |
| Ctrl+B   | Yedekle / Geri Yükle         |
| Ctrl+F   | Teklif arama                 |
| Ctrl+E   | Teklif düzenle               |
| Ctrl+D   | Teklif kopyala               |
| Ctrl+P   | PDF oluştur                  |
| Ctrl+Z   | Ürün tablosunda geri al      |
| Ctrl+H   | Hakkında                     |
| Delete   | Seçili teklifi sil           |

---

## Veri Mimarisi

Program dosyaları ve kullanıcı verileri **ayrı klasörlerde** saklanır.
Güncelleme sistemi veri klasörlerine hiçbir zaman dokunmaz.

```
Kullanıcı Verisi:
  %LOCALAPPDATA%\OfferManagementSystem\data\
    ├── database.db        ← Tüm veriler
    ├── company.cfg        ← Şirket bilgileri ve PDF ayarları
    ├── theme.txt          ← Tema tercihi (light/dark)
    ├── logo.png           ← Şirket logosu
    ├── signature1.png     ← 1. yetkili imzası
    ├── signature2.png     ← 2. yetkili imzası
    ├── offers_pdf/        ← Oluşturulan PDF'ler
    ├── logs/              ← Uygulama logları (30 gün)
    └── backup_meta.json   ← Otomatik yedekleme ayarları

Yedekler:
  %USERPROFILE%\Documents\OfferManagementSystem\backups\
    └── backup_YYYY_MM_DD_HHMMSS.zip
```

---

## Klasör Yapısı (Kaynak Kod)

```
offer_management_system/
├── main.py                  ← Ana giriş noktası
├── build_exe.bat            ← PyInstaller ile EXE derleme
├── Baslat.bat               ← Kullanıcı başlatıcı
├── core/
│   ├── app_paths.py         ← Merkezi path yönetimi
│   ├── config.py            ← Merkezi config okuma/yazma
│   ├── constants.py         ← Sabitler, renk paletleri
│   ├── credential_store.py  ← SMTP şifre (Windows keyring)
│   └── date_utils.py        ← Tarih format dönüşümleri
├── database/
│   ├── db_manager.py        ← SQLite yönetimi + migration
│   └── schema.sql           ← Tablo tanımları
├── models/                  ← Dataclass modeller
├── services/                ← İş mantığı (CRUD, export, PDF)
├── pdf/
│   └── pdf_generator.py     ← ReportLab PDF üretici
├── ui/
│   ├── main_window.py       ← Ana pencere + sidebar
│   ├── dashboard_page.py    ← Dashboard + tablo
│   ├── create_offer_page.py ← 3 adımlı wizard
│   ├── customers_page.py    ← Müşteri yönetimi
│   ├── products_page.py     ← Ürün yönetimi
│   ├── settings_page.py     ← Ayarlar (5 sekme)
│   ├── dialogs/             ← Dialog pencereleri
│   ├── utils/               ← Tema, güncelleme, Excel import
│   └── widgets/             ← Özel widget bileşenleri
├── assets/                  ← Logo, ikon, fontlar
├── docs/                    ← README, CHANGELOG, ROADMAP
├── scripts/                 ← Dağıtım scriptleri
└── tests/                   ← Test dosyaları
```

---

## EXE Derleme

```bat
build_exe.bat
```

Çıktı: `dist\TeklifYonetim.exe` — tek dosya, kurulum gerektirmez.

---

## Yedekleme

- **Otomatik**: Kapanışta + teklif kaydında + belirli aralıklarla
- **Manuel**: Araçlar → Yedekle / Geri Yükle (Ctrl+B)
- **Format**: `backup_YYYY_MM_DD_HHMMSS.zip`
- En fazla 20 yedek tutulur, eskiler otomatik silinir

---

## Otomatik Güncelleme

Program her açılışında GitHub'u arka planda kontrol eder.
- Güncelleme varsa → "Yeni bir sürüm bulundu." diyalogu açılır
- Güncelle → İndirir, eski programı kapatır, yükler, yeniden açar
- Güncelleme sistemi veri klasörlerine **kesinlikle dokunmaz**

---

## v1.0 → v2.0 Değişiklik Özeti

7 bug düzeltmesi, koyu tema tam elden geçirme, 15+ yeni özellik, mimari iyileştirmeler.
Detaylar için: [CHANGELOG.md](CHANGELOG.md)

---

## Geliştirici

- GitHub: [IzzmooPro/offer_management_system](https://github.com/IzzmooPro/offer_management_system)
- E-posta: IzzmooPro@gmail.com
