# Offer Management System — genel inceleme ve düzeltme devir raporu

**Tarih:** 2026-09-05
**İncelenen HEAD:** `e60ad2b7c034188ab9324f9253d77c7fb34ee365`
**Karar:** DÜZELTME GEREKLİ
**Genel değerlendirme:** **7/10**
**Uygulama durumu:** B01–B06 kaynak düzeyinde uygulandı ve regresyon testleri eklendi; commit/build/frozen/installer doğrulaması yapılmadı.

Bu dosya, kullanıcının genel inceleme talebi üzerine bulunan sorunları Claude veya Codex'e eksiksiz devretmek için hazırlanmış tarihli bir inceleme kaydıdır. Kalıcı proje kurallarının yerine geçmez. Kanonik başlangıç noktası [PROJECT_GUIDE/INDEX.md](PROJECT_GUIDE/INDEX.md), değişiklik sırası [CHANGE_PROTOCOL.md](PROJECT_GUIDE/CHANGE_PROTOCOL.md), korunacak sözleşmeler [CRITICAL_INVARIANTS.md](PROJECT_GUIDE/CRITICAL_INVARIANTS.md), test kuralları [TESTING_GUIDE.md](PROJECT_GUIDE/TESTING_GUIDE.md) içindedir.

**Önemli:** “Doğrulandı” sözcüğü, ilgili bölümde açıklanan kanıt sınıfı için kullanılır. Bellek içi SQLite deneyi, mock ile yakalanan dosya yolu, kaynak okuması ve gerçek paketli uygulama davranışı birbirinin yerine geçmez. Aşağıdaki yeniden üretim tarifleri yazılmış/çalıştırılmış yeni regresyon testleri değildir; uygulayıcının ekleyeceği testler için spesifikasyondur.

## 1. İnceleme kapsamı ve puan gerekçesi

| Alan | Puan | Gerekçe |
|---|---:|---|
| İşlev kapsamı | 8/10 | Müşteri/ürün yönetimi, teklif, iskonto, PDF, e-posta, içe/dışa aktarma, rapor, yedekleme ve güncelleme akışları var. |
| Mimari ve bakım | 7/10 | UI/servis/model/DB ayrımı mevcut; bazı UI ve import modülleri çok sayıda sorumluluk taşıyor. |
| Veri ve hesap doğruluğu | 6/10 | Transaction ve genel toplam kontrolleri iyi; para birimi, import miktarı ve satır tutarı sınırlarında açık var. |
| Güvenlik | 6/10 | Credential Manager, TLS ve updater indirme doğrulaması güçlü; dosya yolu ve Excel metin/formül ayrımı eksik. |
| Test/doğrulama altyapısı | 8/10 | Geniş test paketi, izolasyon ve rehber denetimi var; bu rapordaki önemli sınır örnekleri yeşil paketten kaçabiliyor. |

Puanlar ölçülmüş kapsam yüzdesi veya matematiksel kalite metriği değildir; incelenen kanıta dayalı mühendislik değerlendirmesidir. Genel 7/10 puanı, işlev ve test olgunluğuna rağmen güvenlik/veri doğruluğu düzeltmelerinin gerekli olduğunu ifade eder. Canlı görsel kalite için puan verilmedi.

### Güçlü ve korunması gereken taraflar

- `database/db_manager.py`: transaction context manager, rollback ve bağlantıların kapatılması; bağlantıda foreign key etkinleştirme.
- `services/offer_service.py`: teklif ile kalemlerin aynı transaction içinde kaydı; numara sayacının atomik ilerlemesi; genel toplam/iskonto kontrolü.
- `ui/dialogs/backup_manager.py`: SQLite backup API, geri yükleme ön kontrolü, geri alma girişimi ve farklı başarısızlık sonuçlarının ayrımı.
- `ui/main_window.py`: çalışan worker'ların tekilleştirilmesi, bitmeden teardown yapılmaması, kapanışın ertelenmesi.
- `core/credential_store.py`: güvenli depo kullanımı ve düz metin paroladan geçişte işlem sırasının korunması.
- `ui/dialogs/email_dialog.py`: `ssl.create_default_context()` ile SMTP SSL/STARTTLS.
- `ui/utils/updater.py`: tam asset adı, host, boyut ve SHA-256 kontrolü; başarısız doğrulamadan sonra kuruluma geçmeme.
- `ui/utils/operation_error.py`: ham hata içeriği yerine güvenli sınıf/konum bilgisi ile loglama.

Bu kaynak incelemesi, bütün hata yollarının kusursuz olduğunu veya gerçek SMTP/installer kabulünün bu turda yapıldığını göstermez.

## 2. Gerçek doğrulama kaydı

### 2.1 Çalışma ağacı

İnceleme başında ve sonunda izlenen kaynak dosyalarında değişiklik görülmedi. Başlangıçta mevcut olan untracked öğeler korunmuştur:

- `.codex-a6-temp/`
- `Düzeltmeler.txt`
- `Yeni Tasarım v5.Konsept.png`
- `v5 Dönüşüm.txt`

İlk sandbox'lı `git status` bazı geçici/cache dizinlerinde erişim uyarısı verdi. Bu dizinler silinmedi. Bu raporun oluşturulması ayrı belge değişikliğidir; kaynak/test/build düzeltmesi değildir.

**Release kapısı notu:** Bu yeni rapor kökte untracked bir Markdown dosyasıdır ve build sonrası izinli exact yollar listesinde değildir. `--release` provenance kontrolü bunu yeni girdi olarak değerlendirebilir. Bu durum eski artifact'ın bozulduğu anlamına gelmez; mevcut ağaç için yayın kapısının ayrı değerlendirilmesi gerektiğini gösterir. Kapıyı geçirmek amacıyla allowlist'i genişletme, raporu gizleme veya mevcut kanıtları değiştirme. Bu belge turunda `--release` çalıştırılmadı.

### 2.2 Mevcut tam test paketi

Çalıştırılan PowerShell ortamı ve test komutu:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONIOENCODING='utf-8'
python -m pytest tests -q -p no:cacheprovider
```

Sonuç:

```text
1227 passed, 4 skipped, 346 subtests passed in 270.07s (0:04:30)
exit code: 0
```

Çıktı, o oturumda `%TEMP%/oms-general-review-pytest-20260905.log` dosyasına yönlendirildi. Geçici log uzun süreli arşiv garantisi değildir; yukarıdaki sonuç bu raporda saklanmıştır.

İlk deneme `tests/conftest.py` geçici profil klasörünü oluştururken `PermissionError / WinError 5` ile, ürün testlerine ulaşmadan exit 4 verdi. Kök neden sandbox/geçici klasör erişimiydi. İzinli sandbox dışı tekrar yukarıdaki başarılı sonucu verdi. İlk başarısızlık bir ürün hatası veya başarısız regresyon testi olarak sayılmaz.

`-q` çıktısında dört skip'in tek tek nedenleri toplanmadı. Bunlara tahmini neden atanmamalı; skip, başarı kanıtı değildir. Test sayısı coverage yüzdesi değildir. Test süreci tamamlandıktan sonra takip edilen ana Python PID'leri kalmadı; sistem çapında tüm olası alt süreçler için eksiksiz sızıntı envanteri yapıldığı iddia edilmez.

### 2.3 Diğer doğrulamalar

- `python PROJECT_GUIDE/scripts/verify_project_guide.py --stale`: **temiz, 0 uyarı** — ilk incelemedeki kaynak ağacı için.
- `git diff --check`: temiz.
- Bulgular için bellek içi SQLite ve yan etkisi engellenmiş çağrı yakalama deneyleri yapıldı.
- Excel hücre deneyi bellekte `openpyxl.Workbook` ile yapıldı; gerçek Excel uygulaması açılmadı.
- Import ayrıştırma deneyi ilgili fonksiyonların AST ile alınan kaynak gövdeleri üzerinden yapıldı; gerçek dosya seçme/onay penceresi çalıştırılmadı.
- Deneyler repo içine yeni test veya script olarak kaydedilmedi. Aşağıdaki tarifler uygulayıcının gerçek regresyon testlerini oluşturması içindir.

**Bu turda yapılmayanlar:** build, frozen/native UI smoke, installer, gerçek kullanıcı DB'sinde işlem, gerçek dosya silme deneyi, canlı GitHub yayın kontrolü, gerçek SMTP gönderimi, ekran görüntüsü/görsel kabul, kapsam yüzdesi ölçümü ve performans benchmark'ı.

## 3. Bulgu özeti ve öncelik

| Kimlik | Öncelik | Durum / kanıt | Konu |
|---|---|---|---|
| B01 | P1 / yüksek | Kaynak + bellek içi DB + engellenmiş unlink çağrısı | Teklif numarasından dosya yolu kaçışı |
| B02 | P2 / orta | Servis sorgusu deneyle; UI toplamı kaynakla doğrulandı | Para birimlerinin aynı toplamda birleşmesi |
| B03 | P2 / orta | Ayrıştırma fonksiyonu deneyle doğrulandı | Sıfır/geçersiz miktarın 1 yapılması |
| B04 | P2 / orta | Bellekte hücre tipi deneyle doğrulandı | Excel metninin formül olması |
| B05 | P2 / orta | Gerçek servis + bellek içi DB ile doğrulandı | Satır hesabı tutarsızlığının kabulü |
| B06 | P2 / düşük-orta | Saf fonksiyon çağrısıyla doğrulandı | Büyük geçerlilik değerinde OverflowError |

P1: öncelikli güvenlik/veri kaybı riski. P2: normal akışta ele alınması gereken doğruluk veya sağlamlık sorunu. Bu öncelikler sömürülebilirlik skoru değildir.

## 4. B01 — teklif numarasından dosya yolu kaçışı

### Kanıt ve kök neden

- [services/offer_service.py](services/offer_service.py), `save`, yaklaşık 191–282: `keep_offer_no=True` yolunda numara strip edilip korunuyor; güvenli dosya bileşeni kontrolü yok.
- Aynı dosya, `delete`, yaklaşık 292–310; özellikle 298 ve 301:

```python
pdf_path = PDF_DIR / f"{row['offer_no']}.pdf"
if pdf_path.exists():
    pdf_path.unlink()
```

- [ui/utils/excel_import.py](ui/utils/excel_import.py), `_validate_offer_rows`, yaklaşık 939: teklif no boşluk kontrolünden sonra grup anahtarı oluyor.
- `_perform_offer_import`, yaklaşık 1031: `svc.save(offer, keep_offer_no=True)` ile saklanıyor.

Numaranın `../outside` olması, birleştirilen yolun `PDF_DIR/../outside.pdf` olmasına yol açıyor. `Path /` birleştirmesi güvenlik denetimi değildir. Windows mutlak, sürücülü ve UNC yolları ayrıca değerlendirilmelidir.

### Yapılan güvenli deney

1. Gerçek `database/schema.sql` ile SQLite `:memory:` kuruldu; uygulamanın gerçek DB'si açılmadı.
2. Servisin `get_db` bağımlılığı bu DB'ye yönlendirildi; teklif öneki sentetik `TEST` yapıldı.
3. Firma `Synthetic`, tarih güncel ISO tarih, tek kalem `1 × 100 = 100`, numara `../outside` olan teklif `keep_offer_no=True` ile kaydedildi.
4. `Path.exists` true dönecek, `Path.unlink` yalnız çağrı kaydedecek biçimde mock edildi.
5. `OfferService.delete(id)` çağrıldı.

Yakalanan sonuç, gerçek olmayan sentetik kök altında `pdf/../outside.pdf` idi. **Hiçbir gerçek dosya silinmedi.** Kanıt, dışarıdaki dosyanın gerçekten var olduğunu değil; servisin var olması hâlinde bu yolu silmeye göndereceğini gösterir.

### Etki ve kapsam sınırı

Kullanıcı özel hazırlanmış teklif verisini içe aktarıp ilgili teklifi sildiğinde, süreç yetkisiyle erişilebilen başka bir PDF hedeflenebilir. Uygulama kendiliğinden uzaktan dosya silmiyor; import ve sonraki kullanıcı işlemi gerekir. `.pdf` eki eklenir ve işletim sistemi izinleri geçerlidir.

Aynı ham numara aşağıdaki PDF yollarında da kaynakta görülüyor:

- `ui/create_offer_page.py`: yaklaşık 1720 önizleme, 1815 arşiv.
- `ui/dashboard_page.py`: yaklaşık 1052/1087 önizleme, 1120 önerilen kayıt adı, 1138 toplu çıktı.

Bu ek yerler **kaynakla belirlenmiş tarama kapsamıdır**; hepsinde uçtan uca dış dosya yazma deneyi yapılmadı. Dosya diyaloğundaki önerilen ad ile otomatik yazılan yol aynı risk sınıfı sayılmamalı.

### İstenen düzeltme

- Teklif numarasının iş kimliği olması ile güvenli dosya bileşeni olması arasındaki sınırı açıkça kur.
- Yeni import/kayıtlarda tehlikeli numaraları kullanıcıya güvenli doğrulama hatasıyla reddet; sessiz yeniden adlandırma yapma.
- Eski DB'de zaten bulunabilecek tehlikeli numaralara karşı yazma/silme noktasında da kök içinde kalma kontrolü yap. Yalnız yeni girdiyi doğrulamak yeterli değildir.
- Paylaşılan yardımcıyı gerçek tüketicilerde kullan; yalnız `delete` içindeki tek satırı düzeltmekle yetinme.
- Ayarlardaki teklif öneki de üretilen dosya adına etki ettiği için aynı sözleşmeye göre incelenmeli.
- `../`, `..\\`, mutlak/sürücülü/UNC yol, ayraçlar, Windows özel adları ve çakışma durumlarını değerlendir. Bu listenin her öğesi mevcut deneyde ayrı ayrı doğrulanmadı.
- Güvenli mevcut numaraların dosya adı değişmemeli. Kritik değişmez 5: arşiv adı gerçek DB teklif numarasıyla eşleşmeli.
- Sadece `Path(...).name` ile kırpmak farklı numaraları aynı ada düşürebilir; çakışma politikasını görmezden gelme.
- Eski kayıtlar için toplu migration/silme/yeniden adlandırma bu raporla yetkilendirilmiş değildir.

### Kabul testleri

- Yeni zararlı numara kaydı/importu güvenli biçimde reddedilir; teklif/kalem/sayaçta kısmi kayıt olmaz.
- Legacy tehlikeli numara doğrudan izole DB'ye yerleştirilir; silme ve otomatik PDF yolları kök dışına erişmez.
- Sentetik geçici kökün kardeş dizininde koruma dosyası varsa içeriği/hash'i değişmez; gerçek kullanıcı dosyası kullanılmaz.
- Normal numaralı teklif gerçek numarayla arşivlenir ve doğru arşiv silinir.
- Önizleme, tekli/toplu çıktı ve arşiv yolları aynı yardımcı sözleşmesini kullanır.
- DB silme başarılı, PDF temizleme başarısız gibi sonuçlarda kısmi başarı doğru gösterilir.

**İlgili testler:** `test_offer_service.py`, `test_offer_archive_naming.py`, `test_import_safe_errors.py`, `test_dashboard_safe_errors.py`, `test_create_offer_stage_errors.py`.

**Ek kaynak gözlemi:** `delete` PDF'i DB transaction'ından önce siliyor. Sonradan DB silme/commit hata verirse PDF kaybolup kayıt kalabilir. Bu sıra kaynakta görüldü; bu audit'te hata enjekte edilerek ayrıca yeniden üretilmedi. B01 düzeltmesinde ayrı regresyonla doğrula; yalnız işlemlerin sırasını değiştirmenin tüm kısmi başarısızlıkları çözdüğünü varsayma.

## 5. B02 — para birimlerinin aynı toplamda birleşmesi

### Kanıt

[services/report_service.py](services/report_service.py), `product_ranking`, yaklaşık 58–73:

```sql
SUM(oi.total_price) as total_revenue
...
GROUP BY oi.product_code, oi.product_name
```

Teklifin `currency` alanı gruplama/sonuç içinde yok. Aynı sentetik üründen, biri EUR biri USD olan iki ayrı 100 tutarlı teklif kaydedildi. Gerçek servis sonucu:

```text
offer_count: 2
total_qty: 2.0
total_revenue: 200.0
currency: sonuçta yok
```

[ui/reports_page.py](ui/reports_page.py), `_report_monthly_revenue`, yaklaşık 143–160: servis para birimlerini ayrı döndürse de UI bütün döviz değerlerini `total_revenue += val` ile topluyor ve tek `Toplam` gösteriyor. Bu ikinci yol kaynak incelemesiyle doğrulandı; widget üzerinde ayrıca render edilmedi.

### Düzeltme ve karar sınırları

- Kur dönüşümü eklemeden para birimi bazında gruplama ve gösterim yap. `100 EUR` ile `100 USD` ayrı kalmalı.
- Ürün sıralaması UI'sında tutarın para birimi görünür olmalı; aylık özet tek bir birimsiz toplam üretmemeli.
- Ürün başına tek satır mı, ürün+para birimi başına satır mı kullanılacağı uygulanmadan önce açıkça seçilip test edilmelidir.
- Ürün sıralamasındaki limit/teklif sayısı anlamını koru veya değişikliği açıkça belgele.
- Otomatik kur servisi, tarihsel kur, yeni baz para birimi bu düzeltmenin zorunlu kapsamı değildir.
- İptal tekliflerin hariç tutulması korunmalı. Bekleyen teklifin “ciro” sayılması mevcut davranıştır; bu rapor o ürün kararını değiştirmiyor.

**Ek tarama:** `OfferService.get_monthly_stats` ve `get_top_customers` de kaynakta para birimi ayrımı olmadan toplam alıyor. Canlı UI tüketicileri bu audit'te doğrulanmadı. Kullanılan tüm parasal toplama yollarını tarayıp aktif olanları aynı sözleşmeye bağla. `ReportService.customer_ranking` gruplamada para birimini ayırıyor fakat farklı dövizleri sayısal tutarla sıralıyor; bu bir sıralama anlamı/ürün kararıdır, ürün raporundaki kesin toplama hatasıyla karıştırılmamalı.

### Kabul testleri

- Aynı ürün, 100 EUR + 100 USD: birimsiz 200 yok; iki para birimi korunur.
- Aynı para biriminde 100 + 50: doğru 150.
- İptal teklif toplamları etkilemez.
- Aylık servis verisi doğru olsa da UI özetinde yeniden karışmaz; UI testinde özet metnini doğrula.
- Boş rapor ve tek para birimi raporu bozulmaz; dışa aktarılan rapor da ayrımı korur.

**İlgili testler:** `test_reports_safe_errors.py`, `test_export_service.py`, `test_offer_service.py`, `test_currency.py`; gerekiyorsa davranış odaklı rapor servisi testleri ekle.

## 6. B03 — sıfır/geçersiz miktarın sessizce 1 yapılması

### Kanıt ve kök neden

[ui/utils/excel_import.py](ui/utils/excel_import.py), `_validate_offer_rows`, yaklaşık 974:

```python
qty = _parse_number(r.get("quantity"), 0) or 1
```

`_parse_number` geçersiz/boş metni varsayılan 0'a düşürüyor. Ardından `or 1`, sıfırı geçerli 1 adede çeviriyor. Ayrıca `_map_row`, sayısal değerlerde `(value or "")` kullanarak sıfır ile boş değeri daha erken aşamada birleştiriyor. Yalnız `or 1` ifadesini kaldırmak bütün giriş ayrımını düzeltmeyebilir.

Deney girdisi:

```python
{
    "Teklif No": "ZERO",
    "Firma Adı": "Synthetic",
    "Ürün Adı": "P",
    "Miktar": 0,  # ikinci denemede "invalid"
    "Birim Fiyat": 100,
}
```

İki ayrı deneyde sonuç `quantity=1`, hata listesi `[]` oldu. İlgili kaynak fonksiyonları AST ile alınarak çalıştırıldı; DB duplicate sorgusu sentetik boş sonuç döndürdü. Gerçek CSV/XLSX dosyası veya UI onayı bu deneyin parçası değildi.

### İstenen davranış

- Boş, sıfır, negatif, bozuk ve geçerli sayısal değerleri ayır.
- Açıkça 0 veya bozuk miktar içeren satır sessizce 1 olamaz; açıklayıcı güvenli doğrulama sonucu üretmeli.
- Boş miktarın 1 sayılması ürün kararı olarak korunacaksa yalnız gerçekten boş girdi için uygulanmalı.
- Türkçe/uluslararası geçerli sayı biçimlerini bozma; genel parser değişikliği ürün fiyatı/stok gibi diğer kullanıcıları da etkileyebilir.
- Bir teklifin bir kalemi geçersizse tüm teklifin reddi veya açık kısmi aktarım politikasını belirle. Sessiz kalem düşürerek toplamı değiştirme.
- Satır/grup numarasıyla hata bildir; ham müşteri/teklif verisini teknik loglara taşımama sözleşmesini koru.

### Kabul testleri

- Sayısal `0`, metin `"0"`, `"0,0"`, negatif sayı ve `"invalid"` sessizce 1'e dönüşmez.
- Boş/None ayrı test edilir; seçilen politika belgelenir.
- Geçerli kesirli miktar ve yerel sayı biçimleri doğru aktarılır.
- Hatalı teklif için DB/kalem/sayaç değişimi sözleşmeye uygundur; başarı sayacı yanlış artmaz.
- Parser testi yanında sentetik CSV ve XLSX okuma → gruplama → kaydetme zinciri test edilir.

**İlgili testler:** `test_import_safe_errors.py`, `test_csv_import_errors.py`, `test_offer_service.py` ve import regresyonları.

## 7. B04 — Excel metin alanlarının formül hücresine dönüşmesi

### Kanıt

[services/export_service.py](services/export_service.py), `_write_table_sheet`, yaklaşık 153:

```python
cell = ws.cell(row=r_idx, column=c_idx, value=val)
```

Bellekte yapılan deney:

```python
from openpyxl import Workbook
from services.export_service import _write_table_sheet

wb = Workbook()
_write_table_sheet(wb.active, ["Firma"], [["=1+1"]])
assert wb.active["A2"].data_type == "f"  # mevcut hatalı davranış
```

`f`, formül hücresidir. `openpyxl` burada formülü hesaplamaz; Excel gibi tüketicinin değerlendirebileceği türde saklar. Bu audit gerçek Excel'de hesaplama, ağ erişimi veya komut çalıştırma kanıtı üretmedi.

### Kapsam ve çözüm

- Firma, ürün adı/kodu, açıklama, not, teklif no gibi dışarıdan gelebilen metin alanları literal metin olarak saklanmalı.
- Aynı dosyada `export_excel` yaklaşık 85'te doğrudan hücre yazımı da var; sadece `_write_table_sheet` düzeltmesiyle kapsamın kapandığını varsayma.
- Sayısal fiyat/miktar hücrelerini metne dönüştürme. Meşru sayısal tipleri koru.
- XLSX için doğru hücre tipi/serileştirme politikasını kullan; başına körlemesine karakter ekleyip roundtrip verisini değiştirme.
- CSV `export_csv` yolunda `_row(o)` doğrudan yazılıyor. CSV'nin hücre tipi yoktur; spreadsheet tüketicisindeki davranışı ayrıca sınanmalı. Yalnız CSV tırnaklamasının formül yorumlamasını önlediğini varsayma.
- CSV'de kullanılacak kaçış politikasını açıkça belirle; veri roundtrip'i ile güvenli açılış arasındaki farkı test et. CSV tarafı bu audit'te gerçek spreadsheet ile yeniden üretilmiş bulgu değildir.

### Kabul testleri

- `=1+1` gibi sentetik metin XLSX kaydedilip tekrar `data_only=False` ile açıldığında `data_type != 'f'`; değer bozulmamış olmalı.
- Yalnız hücre belleğini değil, gerçek geçici XLSX serileştirme/yeniden okuma sonucunu denetle.
- Kullanılan tüketiciye göre `+`, `-`, `@`, baştaki kontrol/boşluk karakterleri ayrıca değerlendirilmeli; bu çeşitlerin hepsinin mevcut XLSX yolunda formül olduğu iddia edilmez.
- Negatif sayısal değer, miktar ve fiyat numeric kalır.
- Müşteri/ürün/tam teklif dışa aktarımları ve tekrar içe aktarma korunur.
- Maliyet/kâr gizliliği regresyonları geçer.

**İlgili testler:** `test_export_service.py`, `test_profit.py` ve ilgili roundtrip/import testleri.

## 8. B05 — miktar × birim fiyat ile satır toplamı uyumsuzluğu

### Kanıt

[services/offer_service.py](services/offer_service.py), `save`, yaklaşık 201–222:

- Miktar pozitifliği ve fiyatların negatif olmaması kontrol ediliyor.
- Ara toplam, gelen `item.total_price` değerlerinden alınıyor.
- Teklif genel toplamı bu ara toplamla karşılaştırılıyor.
- `item.quantity * item.unit_price` ile `item.total_price` karşılaştırılmıyor.

Gerçek servise bellek içi DB ile şu veri verildi:

```python
Offer(
    company_name="Synthetic",
    date="2026-09-05",
    total_amount=1,
    items=[OfferItem(quantity=2, unit_price=100, total_price=1)],
)
```

Kayıt başarılı oldu. DB'den okunan satır `quantity=2.0, unit_price=100.0, total_price=1.0` idi. Gerçek UI üzerinden bu uyumsuzluğun üretildiği sınanmadı; importun normal yolu çarpımı kendisi yapıyor. Bulgu, servis sınırının eksik doğrulamasıdır.

### Etki ve çözüm

Farklı çağıranlar veya ileride eklenecek akışlar tutarsız tutar saklayabilir. `services/document_service.py` özet üretiminde miktar × fiyatı yeniden hesaplıyor; tüketiciler farklı alanlara güvenirse kayıt/özet ayrışabilir. Gerçek PDF üzerinde bu ayrışma bu audit'te ayrıca ölçülmedi.

- Servis, satır tutarını tek sözleşmeden hesaplamalı veya uyumsuz girdiyi reddetmeli.
- Para yuvarlama hassasiyeti açıkça belirlenmeli; her yere farklı tolerans eklenmemeli.
- DB transaction başlamadan önce tüm satırlar doğrulanmalı; başarısız kayıtta numara tüketilmemeli.
- İskonto öncesi/sonrası tutar ayrımı ve legacy `discount_amount` davranışı korunmalı.
- `NaN`/sonsuz değerler, miktar ve iskonto dahil ek kabul testlerine alınmalı. Bu özel değerlerin gerçek DB'ye kabul edildiği bu audit'te doğrulanmadı; bunlar ek sağlamlık kapsamıdır.
- Mevcut DB'deki olası tutarsız kayıtlar otomatik yeniden hesaplanmamalı; gerekiyorsa ayrı salt-okunur envanter ve ürün sahibi kararı gerekir.

### Kabul testleri

- `2 × 100, total_price=1`: seçilen politika gereği açıkça reddedilir veya tutarlı 200 olarak hesaplanır; 1 diye sessiz kayıt yok.
- Tutarlı satır, kesirli miktar ve yuvarlama sınırı doğru sonuç verir.
- Birden çok kalem, yüzde/sabit iskonto, sıfır fiyat ve geçersiz negatif değerler kapsanır.
- Hatalı kayıtta teklif/kalem/sayaç aynı kalır.
- Sonlu olmayan değerler güvenli doğrulama sonucuna gider.

**İlgili testler:** `test_offer_service.py`, `test_profit.py`, `test_export_service.py`, `test_create_offer_stage_errors.py` ve model hesap testleri.

## 9. B06 — aşırı geçerlilik süresinde OverflowError

### Kanıt

[services/offer_service.py](services/offer_service.py), `remaining_days`, yaklaşık 31–53. Tarih ayrıştırma hatası yakalanıyor; tamsayı dönüşümü, ay çarpımı ve tarih toplaması tüm sınırlar için korunmuyor:

```python
days = int(match.group(1))
if "ay" in validity.lower():
    days *= 30
expiry = offer_date + datetime.timedelta(days=days)
```

Deney:

```python
remaining_days(SimpleNamespace(date="2026-09-05", validity="999999999 gun"))
# OverflowError
```

Fonksiyon, geçersiz/anlaşılamayan süre için `None` dönüp teklifi süresi dolmuş saymama sözleşmesine sahip. Büyük ama regex'e uyan sayı bu güvenli davranışı aşıyor.

### Etki ve çözüm

Bu değer mevcut/import edilmiş bir kayıtta bulunursa, süresi dolan teklifleri tarayan akış hata alabilir. `get_expiring_offers` ve dolayısıyla `get_expired_pending`/`cancel_expired` değerlendirilmelidir. Ana uygulamanın tamamının çöktüğü veya gerçek açılışın başarısız olduğu bu turda sınanmadı.

- Tamsayı dönüşümü ve tarih taşmasını birlikte güvenli ele al; bozuk mevcut veride fonksiyon exception sızdırmadan `None` dönmeli.
- Yeni girdilerde kabul edilen süre aralığını doğrula. Keyfi ürün limiti ekleme; tarih temsil sınırı ile ürün politikasını ayır.
- “Ay = 30 gün” mevcut ürün kararı korunmalı.
- Bozuk süre, otomatik iptal gerekçesi olamaz; aynı listedeki sağlıklı kayıtların değerlendirilmesi sürmeli.

### Kabul testleri

- `999999999 gun`, çok uzun sayısal metin, büyük ay değeri ve `9999-12-31` üzerine pozitif süre güvenli sonuç verir.
- Normal gün/ay, boş süre, bozuk tarih ve son geçerlilik günü davranışı korunur.
- Bozuk kaydın yanında gerçekten süresi dolan sağlıklı kayıt bulunabilir.
- Kullanıcı onayı olmadan durum değişmez; `cancel_expired` bozuk süreyi iptal etmez.

**İlgili testler:** `test_offer_service.py`, `test_expired_offer_prompt.py`, `test_date_utils.py`.

## 10. Bakım eksikleri ve bilinen riskler — B01–B06'dan ayrı

### M01 — büyük modüller

İncelenen kaynakta `ui/create_offer_page.py` 2.049, `ui/utils/excel_import.py` 1.326, `ui/dashboard_page.py` 1.326 satırdı. `CreateOfferPage._finish_offer` yaklaşık 171, `run_import_all_flow` yaklaşık 164 satırdı. Bunlar bakım göstergesidir; satır sayısı tek başına hata değildir. Tema dosyasındaki uzun stylesheet gibi deklaratif içerikler iş akışı karmaşıklığıyla aynı değerlendirilmemeli.

Öneri: güvenlik/doğruluk düzeltmelerinden sonra, davranış testleri altında doğrulama, işlem yürütme ve UI gösterimi sorumluluklarını ayır. B01–B06 yaması içinde kapsamlı yeniden yazım yapma.

### M02 — yeniden üretilebilir build ve bağımlılık sürümleri

`.gitignore` çoğu `packaging/` girdisini ve `assets/` klasörünü dışarıda tutuyor; `packaging/TeklifYonetim.iss` izlenen istisna. Temiz clone tüm build girdilerini içermiyor. `requirements.txt` PySide6/reportlab/Pillow/openpyxl/keyring için yalnız alt sınırlar (`>=`) belirtiyor; aynı tarihte/başka makinede aynı çözümleme garanti değil.

Bu bilinçli yerel girdi politikasını otomatik tersine çevirme. Uygun ayrı kapsam: yerel girdilerin doğrulanmış yedeği, hash/env envanteri, sürümlenmiş bağımlılık çözümleme/constraints stratejisi ve temiz ortamda yeniden üretim. Şirket varlıkları veya hassas veriler otomatik Git'e eklenmemeli. Bu tur yeni clone/build yapılmadı; bağımlılık güvenlik açığı taraması veya “şu sürüm güvensiz” iddiası yok.

### M03 — updater için bağımsız imza güven kökü

Boyut/SHA-256/host kontrolü mevcut ve korunmalı. SHA-256 aynı GitHub release metadata'sından geldiği için metadata ele geçirilmesine karşı bağımsız imza sağlamıyor. Kanonik riskler R1/R5; bu yeni keşfedilmiş bir indirme hash hatası değildir.

Authenticode veya ayrı anahtarlı imzalı manifest ayrı tasarım/ürün kararıdır. Anahtar saklama, rotasyon, eski istemci uyumu, sürüm geriletme politikası ayrıca ele alınmalı. Bu rapor sertifika satın alma, anahtar üretme veya release değiştirme yetkisi vermez. Canlı GitHub hesabı/yayın güvenliği bu turda denetlenmedi.

### M04 — testlerin sınırı

Geniş paket yeşilken B01–B06 örneklerinin bir kısmı yanlış davranabiliyor. Hedef daha fazla test sayısı değil, dış girdiler ve sınır sözleşmeleri için anlamlı regresyonlardır. Mock testinin hangi sınırı gerçekten sınadığı açık yazılmalı. Coverage yüzdesi ölçülmedi; test sayısından türetilmemeli.

### Daha önce kayıtlı riskler: yalnız tarihli bağlam

[KNOWN_RISKS.md](PROJECT_GUIDE/KNOWN_RISKS.md) okumasında aşağıdakiler görüldü. Bunlar bu tur yeni canlı deneyle doğrulanmış bulgular gibi raporlanmamalı:

- R8: “Tümünü İçe Aktar” gizli sayfa davranışı ürün sahibi kararıyla ertelenmiş; B03 bahanesiyle gizlice kapsama alınmamalı.
- R9: müşteri UNIQUE kimlik kuralı eksikliği; yeni veri birleştirme/migration ayrı karar.
- R11: 500 kalemli teklif doldurma performansı; tarihsel ölçüm, bu tur benchmark yok.
- R12: büyük DB'de kapanış yedeğinin gecikmesi; tarihsel kabul, güncel ölçüm yok.
- R13: ürün kodu sütunu genişliği; tarihsel görsel bulgu, bu tur canlı ekran doğrulanmadı.
- R3d: CDN host değişirse updater erişilebilirliği; bu tur canlı host testi yok.

Firma bilgisi/logo paket içeriği kabul edilmiş ürün kararıdır (R12b); güvenlik temizliği adı altında kaldırılmamalı. Daha önce kapatılmış thread, geri yükleme ve modal bulguları yalnız eski isimleri görüldü diye yeniden açık ilan edilmemeli.

## 11. Uygulama sırası ve doğrulama matrisi

1. Çalışma ağacını/HEAD'i tekrar kontrol et. Bu belgedeki satırlar tarihli; fonksiyon adından yeniden bul.
2. B01 için hatayı gösteren test, minimum çözüm, hedefli testler.
3. B02 ve B03 için ayrı davranış testleri/düzeltmeler.
4. B04 çıktı sözleşmesi; ardından B05 ve B06 veri sınırları.
5. Birbirinden bağımsız düzeltmeleri izlenebilir tut. Aynı ağaçta başka agent uygulama yapıyorsa dosya değiştirme.
6. Bütün etkili kaynak testleri sonrası tam suite. Kırmızı sonucu sakla, nedeni incele; başarısızlığı kör tekrar veya assertion zayıflatmayla kapatma.
7. UI davranışı değişen yollar için kaynak/offscreen sonucundan ayrı frozen smoke planla. Build/frozen/installer izinlerini ve kanıtlarını ayrı tut.
8. Kalıcı kural değişmişse ilgili kanonik belgeyi güncelle; bu tarihli raporun ilk kanıtlarını silme.

| Kapsam | Gerekli kaynak doğrulaması | Paketli doğrulama |
|---|---|---|
| B01 servis + PDF/import/UI tüketicileri | İlgili teklif/arşiv/import/hata testleri + tam suite | Etkilenen PDF/import/silme UI yolları için izinli frozen smoke |
| B02 rapor servisi + UI | Para birimi/rapor/çıktı testleri + tam suite | Ayrı para birimi gösterimi için frozen smoke |
| B03 import doğrulama + UI sonucu | CSV/XLSX + kayıt/rollback testleri + tam suite | Geçersiz girdi/özet/iptal için frozen smoke |
| B04 çıktı serileştirme | XLSX yeniden okuma/roundtrip + ilgili çıktı testleri; değişiklik etkisine göre tam suite | Kaynak XLSX kanıtı ile gerçek spreadsheet kabulünü ayır; UI değişirse frozen smoke |
| B05 servis hesap sözleşmesi | Teklif/iskonto/yuvarlama/rollback + tam suite | UI davranışı değişirse frozen smoke |
| B06 servis/süre ve tüketiciler | Sınır değerleri + teklif/onay testleri + tam suite | Bildirim UI davranışı değişirse frozen smoke |

Bu tablo [CHANGE_PROTOCOL.md](PROJECT_GUIDE/CHANGE_PROTOCOL.md) yerine geçmez; uygulama kapsamı genişlerse oradaki en yüksek risk satırı uygulanır. Paketleme değişikliği yokken installer testi otomatik zorunlu sayılmaz. Build gerekiyorsa eski geçerli artifact'ları temizleme riski ayrıca yönetilir.

## 12. Claude/Codex'e verilecek hazır görev metni

> Önce AGENTS.md ve PROJECT_GUIDE/INDEX.md yönlendirmesini oku. Ardından bu raporu incele: GENEL_INCELEME_VE_DUZELTME_PLANI_2026-09-05.md. Rapor e60ad2b7c034188ab9324f9253d77c7fb34ee365 kaynağına aittir; güncel HEAD/status ve ilgili fonksiyonları yeniden kontrol et.
>
> Öncelik B01, ardından B02–B06. Her bulguyu önce izole regresyon testiyle yeniden üret; sonra minimum düzeltme yap. Raporda doğrulanmış deney, kaynak gözlemi ve önerilen ek test ayrımını koru. Hata testini sadece mevcut yanlış davranışı onaylayan teste dönüştürme. Testleri gerçek kullanıcı verisi/SMTP/keyring/installer üzerinde çalıştırma; tests/conftest.py izolasyonunu atlayan unittest discover kullanma.
>
> B01 için mevcut/legacy veriye karşı tüketim noktasında koruma ve bütün PDF yolu kullanıcıları; B02 için döviz ayrımı; B03 için boş/sıfır/bozuk ayrımı; B04 için literal metin ve dosya roundtrip'i; B05 için tutarlı satır hesabı; B06 için taşma ve bozuk kaydın güvenli atlanması zorunlu kabul kapsamıdır. Açık ürün politikası gerektiğinde seçenekleri ve mevcut davranışı netleştir. Mevcut kullanıcı kayıtlarını otomatik düzeltme/silme/yeniden adlandırma.
>
> M01–M04 bakım maddelerini ve ertelenmiş bilinen riskleri B01–B06 düzeltmelerine otomatik ekleme. Kaynak/test değişikliği yetkisini kullanıcının güncel talebinden kontrol et: bu rapor tek başına bir uygulama izni değildir. Codex'in mevcut AGENTS rolü kaynak yazmayı sınırlıyorsa, kullanıcı Codex'e uygulamayı açıkça devretmeden bu rolü kendiliğinden değiştirme. Commit, push, build, native/frozen çalıştırma, installer, tag ve release için mevcut ayrı izin kurallarını koru.
>
> Sonunda her bulgu için: değişen dosya/fonksiyon, önceki kırmızı test, sonraki hedefli/tam test sonucu, testin kanıt sınırı, kalan ürün kararı/riski ve sonraki ayrı onay adımını yaz. Frozen doğrulama yapılmadıysa açıkça belirt; yalnız kaynak testiyle paketli kabul iddia etme. Kanonik doküman güncellemelerini tamamla, bu rapordaki tarihli başlangıç kanıtını koru.

## 13. Kapanış kaydı — uygulayıcı dolduracak

| Kimlik | İlk regresyon / kırmızı kanıt | Düzeltme ve yeşil kanıt | Frozen/gerçek tüketici kanıtı | Son durum |
|---|---|---|---|---|
| B01 | `../outside` import numarası kabul edildi; legacy kayıtta dış yol `unlink` hedefi olabiliyordu | `core/offer_files.py` ile numara/temel yol doğrulaması; yeni import reddi ve legacy silmede dış yol çağrılmaması. `test_general_review_regressions` | Yok | Kaynak düzeyinde KAPALI |
| B02 | Aynı ürünün EUR ve USD tutarları tek sayı olarak birleşiyordu | `product_ranking` ürün+para birimine göre gruplandı; aylık özet para birimi tutarlarını ayrı gösteriyor. `test_general_review_regressions` | Yok | Kaynak düzeyinde KAPALI |
| B03 | Sıfır, negatif ve bozuk miktar 1'e dönüşüyordu | Boş miktar 1 varsayılanını korur; açık sıfır/negatif/bozuk değer teklifi reddeder. `test_general_review_regressions` | Yok | Kaynak düzeyinde KAPALI |
| B04 | `=1+1` XLSX'te formül hücresiydi | Metinler XLSX/CSV'de literal ön ekle yazılır; serileştirip yeniden okuyan test eklendi. `test_general_review_regressions` | Gerçek Excel kabulü yok | Kaynak düzeyinde KAPALI |
| B05 | Kalem `2 × 100 = 1` olarak kaydedilebiliyordu | Sonlu sayı ve kalem çarpım/tutar denetimi eklendi; tutarsız yazma reddediliyor. `test_general_review_regressions` | Yok | Kaynak düzeyinde KAPALI |
| B06 | Büyük geçerlilik değeri `OverflowError` veriyordu | Tarih taşması çözümlenemeyen geçerlilik olarak `None` döner. `test_general_review_regressions` | Yok | Kaynak düzeyinde KAPALI |

**Doğrulama sonucu (2026-09-05):** İlk yeni test turu, beklenen eski davranışları göstererek `12 failed, 4 passed, 1 subtests` verdi. Düzeltme sonrası hedefli grup `94 passed, 27 subtests`; tam kaynak paketi ikinci turda `1237 passed, 4 skipped, 354 subtests` ile geçti. Son ek sınır testinden sonra tam kaynak paketi yeniden `1238 passed, 4 skipped, 360 subtests` ile geçti. İlk tam paket turu yaklaşık 58 saniyede `0xC0000409` ile kesildi; işaretleyici/stderr yoktu. Aynı worker yaşam döngüsü dosyası sonra ayrı çalıştırıldığında `35 passed` verdi; tam paket kontrollü iki kez başarıyla tamamlandı. Bu, paketli EXE veya installer kanıtı değildir.

Değişiklikler kullanıcı onaylı v4.5 kaynak hazırlığı commit'inde toplanmıştır; exact hash canlı Git kaydından okunmalıdır. Frozen kanıtı henüz yoktur. İlk bulgular ile başarısız ilk tam test turu tarihsel kanıt olarak korunmuştur.

## 14. B07 — Güncellemede kaydedilmemiş veri ve kapanış koruması (2026-09-05)

**Bulgu:** Güncelleyici installer'ı başlatıp `os._exit(0)` çağırıyordu. Bu yol ana pencerenin kaydedilmemiş teklif/ayar onayı, kapanış yedeği ve worker bekleme akışını atlayabiliyordu. Installer'daki zorla sonlandırma yalnız uygulama zaten kapanmayı başlatmadıysa devreye giriyordu; ana sorun uygulamanın kontrollü kapanış istememesiydi.

**Düzeltme:** `UpdateDialog`, installer'ı çalıştırmadan önce ana pencerenin normal `closeEvent` akışını ister. Kullanıcı kapanışı iptal ederse indirilen installer çalıştırılmaz ve geçici dosya kaldırılır. Kapanış yedek/worker akışı tamamlanınca installer isteği kuyruğa alınır; olay döngüsü bittikten ve `main.py` veritabanını kapattıktan sonra installer başlatılır. Doğrudan `os._exit(0)` yolu kaldırılmıştır.

**Kaynak kanıtı:** `tests/test_update_graceful_shutdown.py` iptalde installer'ın çağrılmadığını; ertelenmiş kapanışta beklendiğini; installer'ın DB kapatma çağrısından sonra başlatıldığını ve başlatma hatasının yol/traceback sızdırmadığını doğrular. İlgili updater/restart grubu `98 passed, 69 subtests`; son tam kaynak paketi `1244 passed, 4 skipped, 360 subtests` ile geçti.

**Sınır:** Bu kaynak kanıtıdır. Yeni sürüm üretildiğinde kurulu v4.4 → yeni sürüm upgrade, gerçek DB/ayar/PDF/yedek envanteri karşılaştırması ve public v4.4 istemcisinden canlı D2 updater kabulü ayrıca yapılmalıdır.
