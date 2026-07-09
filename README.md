# Teklif Yönetim Sistemi

Küçük ve orta ölçekli işletmeler için hazırlanmış, **teklif hazırlama ve müşteri/ürün yönetimi** masaüstü uygulaması. Ürünlerinizi ve müşterilerinizi kaydedin, birkaç adımda profesyonel bir teklif oluşturun ve tek tıkla **PDF** çıktısını alın.

> Kısaca: ürünü seç, müşteriyi seç, teklifi oluştur — gerisini program hazırlasın.

## İndir

Son sürümü buradan indirebilirsiniz:

[**En Son Sürüm (Latest Release)**](https://github.com/IzzmooPro/offer_management_system/releases/latest)

Kurulum dosyası şu isimle görünür:

`TeklifYonetim_Setup_v<sürüm>.exe`

Kurulumu çalıştırın, program açılsın — verileriniz bilgisayarınızda güvenle saklanır.

## Ne İşe Yarar?

- **3 adımlı teklif sihirbazı** — müşteri, ürünler, koşullar → hazır teklif
- **Profesyonel PDF** — logolu, imzalı, Türkçe karakter tam destekli
- **Ürün & müşteri yönetimi** — arama, filtre, Excel/CSV içe-dışa aktarma
- **Kategoriler ve şablonlar** — sık kullanılan teklifleri tek tıkla kur
- **Raporlar** — aylık ciro, müşteri/ürün sıralaması, dönüşüm oranı
- **Çoklu para birimi** — TL / EUR / USD
- **Açık / Koyu tema**
- **Otomatik yedekleme** ve geri yükleme
- Yeni sürüm çıktığında **program sizi bilgilendirir**

## Güncellemeler Nasıl Çalışır?

Program açıldığında yeni sürüm olup olmadığını kontrol eder. Yeni sürüm varsa size sorar:

1. Yeni sürüm bulunduğunu gösterir.
2. İndirmek isteyip istemediğinizi sorar.
3. İndirme bitince kurulumu başlatır; kurulum mevcut sürümün üzerine yazar.

Güncellemeler **zorla kurulmaz** — her adımda onay istenir. Güncelleme yalnızca programı yeniler; müşteri/teklif verilerinize ve yedeklerinize **dokunmaz**.

## Verileriniz Nerede?

- Veriler: `%LOCALAPPDATA%\OfferManagementSystem\data`
- Yedekler: `Belgeler\OfferManagementSystem\backups`

Bu klasörler program dosyalarından ayrıdır; güncelleme ve yeniden kurulumdan etkilenmez.

## Kaynak Koddan Çalıştırmak

Python 3.12+ kuruluysa projeyi kaynak koddan çalıştırmak için:

```
Baslat.bat
```

Bu betik gerekli paketleri (PySide6, reportlab, Pillow, openpyxl, keyring) hazırlayıp programı açar. Elle kurulum için: `pip install -r requirements.txt`.

## Geliştirici

Geliştirici: **IzzmooPro**

---

# English

**Offer Management System** is a Windows desktop app for preparing quotations and managing customers/products. Save your products and customers, build a professional quote in a few steps, and export it as a **PDF** with one click.

## Download

[**Latest Release**](https://github.com/IzzmooPro/offer_management_system/releases/latest) — installer looks like `TeklifYonetim_Setup_v<version>.exe`.

## Features

- 3-step quote wizard, professional PDF output (logo, signatures, full Turkish support)
- Product & customer management with Excel/CSV import-export
- Categories, templates, reports (revenue, rankings, conversion rate)
- Multi-currency (TRY / EUR / USD), light/dark theme
- Automatic backups, in-app update notifications

## How Updates Work

On startup the app checks for a newer version and asks before downloading and installing. Updates never touch your data or backups.

## Run From Source

With Python 3.12+ installed, run `Baslat.bat` (or `pip install -r requirements.txt` then `python main.py`).
