---
purpose: UI değişikliklerini entegrasyondan önce gerçek widget koduyla güvenli biçimde önizleme ve karşılaştırma sözleşmesi.
read_when: UI tasarımı planlarken, preview senaryosu eklerken, görsel baseline veya önce-sonra raporu üretirken.
covers: []
last_verified_commit: c917bf8
last_verified_date: 2026-08-22
volatile: false
---

# UI Preview Lab sözleşmesi

## Amaç ve kanıt sınırı

UI Preview Lab, üretim PySide6 widget'larını izole örnek veriyle çalıştırarak
bir UI değişikliğini `main` dalına entegre etmeden önce gösterecektir. Preview,
arayüzün kopyasını veya ayrı bir HTML taklidini oluşturmaz; önizlenen nesne
üründe kullanılan gerçek widget sınıfıdır.

Preview şu iki kanıtın **yerine geçmez**:

- Davranış testi: tıklama, kaydetme, hata, worker ve yaşam döngüsü sözleşmeleri
  kendi pytest testleriyle doğrulanır.
- Frozen/installer kanıtı: kaynak-modu preview, paketli EXE veya kurulu uygulama
  davranışını kanıtlamaz. UI davranışı değişikliğinde [CHANGE_PROTOCOL.md](CHANGE_PROTOCOL.md)
  uyarınca hedefli test, tam suite ve frozen smoke ayrıca gerekir.

Makine-okunur kapsamın tek kaynağı: `ui_preview/catalog.json`.
Pencere, sayfa, diyalog, runtime modal ve yeniden kullanılabilir bileşenler
orada benzersiz kimlikle kayıtlıdır. Kaynakta yeni bir doğrudan Qt görsel
sınıfı eklenip katalog unutulursa `tests/test_ui_preview_catalog.py` kırmızı
olur.

## Değiştirilemez güvenlik sınırları

Preview çalıştırılmadan **önce**, hiçbir üretim modülü import edilmeden geçici
profil kurulmalıdır. Aşağıdaki sınırlar fail-closed uygulanır:

- Gerçek kullanıcı verisi, gerçek DB ve gerçek yedek kullanılmaz veya yazılmaz.
- Windows Credential Manager okunmaz, yazılmaz veya silinmez.
- Ağ, gerçek SMTP ve updater erişimi yapılmaz.
- Tarayıcı, `mailto:`, Explorer, installer, restart veya başka dış süreç açılmaz.
- Üretim veri/ayar/log yolları geçici preview kökü altında kalır. Yalnız
  sentetik PNG, manifest ve HTML raporu kullanıcının açıkça verdiği yeni/boş
  capture klasörüne kontrollü olarak aktarılabilir.
- Preview üretim `main.py` başlangıcına, menüsüne veya gizli debug seçeneğine
  bağlanmaz; bağımsız geliştirici aracı olarak çalışır.
- Capture içeriğinde yalnız sentetik veri bulunur; gerçek firma/müşteri bilgisi,
  credential, mutlak kullanıcı yolu veya log içeriği bulunamaz.
- Test veya hata sonucu baseline'ı otomatik güncelleyemez. Baseline kabulü açık,
  ayrı ve kullanıcı tarafından görülebilir bir işlemdir.

Sandbox bu şartların tamamını kanıtlamadan pencere oluşturmamalıdır. Bloklayıcı
kurulamazsa preview başlamaz; gerçek sisteme düşen bir fallback yoktur.

## Envanter sınıfları

| Tür | Anlamı |
|---|---|
| `window` | Ana pencere veya splash gibi bağımsız üst seviye yüzey |
| `page` | Ana pencerenin navigasyonla gösterdiği tam sayfa |
| `dialog` | Gerçek `QDialog` veya diyalog davranışlı üst seviye yüzey |
| `runtime_modal` | Bir metot içinde anlık üretilen uyarı/onay/sonuç penceresi |
| `component` | Birden çok görünümde kullanılan veya ayrı tasarım kararı taşıyan widget |

Katalogdaki `preview_status` alanı factory hazırlığını gösterir. `planned`,
yüzeyin envantere alındığı fakat çalışan factory'si bulunmadığı anlamına gelir;
factory ve doğrulaması olmadan `implemented` değerine çevrilemez. Mevcut
katalogda bütün yüzeyler `implemented` durumundadır.

## Aşama 2 — sandbox ve fixture durumu

`ui_preview/sandbox.py`, üretim path sabitleri import edilmeden önce geçici
profili kurar. Hassas path modüllerinden biri erken import edilmişse başlamayı
reddeder. Python socket/urllib/SMTP, webbrowser, `subprocess`, `os.system`,
`os.startfile`, Qt `QDesktopServices.openUrl` ve `QProcess.startDetached`
yolları bloklanır ve denetim kaydına alınır. Credential işlemleri yalnız bellek
içi sahte depoya gider; gerçek Credential Manager erişim sayısı sıfır kalır.

`ui_preview/fixtures.py`, yalnız aktif sandbox içinde `empty`, `populated` ve
`dense` profillerini üretir. DB, config, logo, dört imza ve örnek PDF sentetiktir;
sabit tarih ve sıralı kimliklerle üretilir. Manifest mutlak yol içermez ve iki
ayrı sandbox'ta aynı profil aynı mantıksal sayımları ve SHA-256 değerlerini
verir. Bilinmeyen profil üretim verisine düşmez; hata verir.

## Aşama 3–4 — launcher ve tam senaryo durumu

Bağımsız başlangıç `python -m ui_preview` komutudur; üretim `main.py` dosyasına,
menüsüne veya açılış zincirine bağlanmaz. Registry katalog dışı yüzey,
durum, tema, viewport, profil veya yanlış sınıf döndüren factory için
fail-closed davranır. Factory çözümü aktif sandbox dışında yasaktır.

Kullanılabilir komutlar:

```powershell
python -m ui_preview --list
python -m ui_preview --check
python -m ui_preview --launcher --profile populated --dpi 100
python -m ui_preview --scenario component.plus_button.normal --theme dark --viewport 1100x700
python -m ui_preview --smoke-surfaces --json
python -m ui_preview --smoke-all --json
python -m ui_preview --capture component.plus_button.normal --output <CAPTURE_ROOT>\before --label before --json
python -m ui_preview --capture-surfaces --theme dark --output <CAPTURE_ROOT>\dark --label "dark surfaces" --json
python -m ui_preview --compare <CAPTURE_ROOT>\before\capture_manifest.json <CAPTURE_ROOT>\after\capture_manifest.json --output <CAPTURE_ROOT>\report --json
python -m ui_preview --geometry-surfaces --json
python -m ui_preview --geometry-all --json
python -m ui_preview --baseline-plan <CAPTURE_ROOT>\candidate\capture_manifest.json --json
python -m ui_preview --baseline-accept <CAPTURE_ROOT>\candidate\capture_manifest.json --baseline-root <BASELINE_ROOT> --approval-token <PLAN_CIKTISINDAKI_TAM_TOKEN> --json
```

Aşama 4 itibariyla 44 yüzey ve 188 durumun tamamı gerçek üretim widget
factory'sine bağlıdır; `preview_status` değerleri `implemented` durumundadır.
Sayfa, diyalog, runtime modal, splash ve bileşenler için kopya, HTML veya
placeholder UI üretilmez. `--smoke-surfaces` her yüzeyden bir temsilciyi,
`--smoke-all` ise 188 durumun tamamını tek izole preview profilinde oluşturup
kapatır.

Splash widget'ı önizlenebilirlik için `ui/startup_splash.py` içindeki
`StartupSplash` sınıfına davranış korunarak taşınmıştır; `main.py` aynı
sınıfı kullanır. Müşteri geçmişi populated senaryosu gerçek yükleme hatasını
yakalamış ve eksik `fmt_money` import'u minimum düzeltmeyle tamamlanmıştır.

Tema (`light`/`dark`) launcher içinde canlı değişir. Viewport yalnız kanonik
1100×700, 1300×800, 1600×900 ve 1920×1080 değerlerinden seçilir. DPI %100,
%125 veya %150 olarak Qt importundan önce CLI ile belirlenir ve açık süreçte
değişmez.

## Aşama 5 — capture ve karşılaştırma raporu

Tek senaryo veya 44 yüzeylik temsilci seti gerçek widget'tan PNG olarak
yakalanabilir. Her capture seti şunları içerir:

- `capture_manifest.json`: senaryo, sınıf, sentetik profil, tema, viewport,
  DPI, görsel boyutu/SHA-256, Qt/PySide sürümü ve UI kaynak parmak izi,
- `images/*.png`: yalnız sentetik fixture içeren capture'lar,
- `index.html`: yerel temas/contact-sheet sayfası.

Çıktı klasörü açıkça verilmelidir ve yeni ya da boş olmalıdır. Dolu
klasöre sessiz üzerine yazılmaz. Üretim başarısız olursa kısmi rapor
yayımlanmaz. Manifest mutlak checkout/kullanıcı yolu veya credential taşımaz.

`--compare`, aynı senaryo/profil/tema/viewport/DPI/widget sınıfına ait iki
sentetik manifesti SHA-256 ve boyutlarıyla doğrular. Her senaryo için before,
after, diff ve üçlü yan-yana PNG; ayrıca `comparison_manifest.json` ve yerel
`index.html` üretir. Boyut değişikliği desteklenir; eksik/fazla senaryo veya
uyumsuz capture metadata fail-closed reddedilir.

Capture veya karşılaştırma tek başına baseline kabulü değildir. Otomatik
baseline güncelleme seçeneği yoktur; açık kullanıcı onaylı akış aşağıdadır.

## Aşama 6 — geometri ve değiştirilemez baseline

`--geometry-surfaces` 44 yüzeyin ilk temsilcisini, `--geometry-all` ise 188
durumun tamamını gerçek widget olarak açıp denetler. Görünür ve kullanılabilir
alanı olduğu hâlde sıfır boyutta kalan widget `critical`; tek satırlık label
ve button metin taşmaları `warning` olarak raporlanır. Qt'nin boş tabloya ait
iç görünüm/header parçaları ile açıkça `maximumWidth/Height=0` kullanılarak
daraltılmış durumlar hata sayılmaz. Kritik bulgu varsa komut başarısız döner.

Metin taşması yalnız orantılı font metriği güvenilir olduğunda ölçülür. Bazı Qt
`offscreen` ortamları `i` ve `W` karakterlerini aynı genişlikte döndürür; bu
durum JSON'da `text_metrics_reliable=false` olarak açıkça raporlanır ve yanlış
metin uyarısı üretilmez. Böyle bir tur sıfır-boyut denetimini kanıtlar fakat
metin taşmasını kanıtlamaz; karar için gerçek Windows Qt turu gerekir.

Mevcut kaynakta uzun başlıklı adım göstergesinin bağlayıcıları en az 12 px
korunur. “Mevcut Kalemler” modalındaki uzun özel eylem düğmeleri, Windows
`QMessageBox` gösterim sırasında standart genişliği yeniden dayatsa da metin
ölçümü ve güvenli yatay payla kırpılmadan gösterilir. Her iki davranış regresyon
testi ve gerçek Windows capture/geometri turuyla doğrulanır.

Baseline kabulü iki ayrı ve kullanıcı görünür adımdır:

1. `--baseline-plan` manifesti, bütün PNG SHA-256 değerlerini ve boyutlarını
   doğrular; hiçbir dosya yazmadan içeriğe bağlı `ACCEPT-...` token'ı üretir.
2. Kullanıcı adayı gördükten sonra tam token `--baseline-accept` komutuna
   verilir. Komut yeni `baseline-<hash>` sürüm klasörü oluşturur; capture
   manifestini, PNG'leri ve `baseline_record.json` kaydını kopyalar.

Yanlış/eski token, bozulmuş PNG veya var olan sürüm fail-closed reddedilir.
Aynı sürümün üzerine yazılmaz ve `--baseline-update` seçeneği yoktur. Yeni bir
aday için her zaman yeniden capture, plan, kullanıcı görsel onayı ve yeni sürüm
gerekir. Kabul edilen baseline da yalnız sentetik kaynak-mode kanıtıdır;
frozen EXE veya installer doğrulamasının yerine geçmez.

## Planlanan senaryo matrisi

Günlük hızlı profil bütün yüzeyleri açık/koyu temada, 1300×800 ve %100 DPI'da
çalıştırır. Geniş kabul profili kritik yüzeyleri 1100×700, 1300×800,
1600×900 ve 1920×1080 boyutlarında; %100, %125 ve %150 DPI'da doğrular.

`system` tema işletim sistemi ayarına bağlı olduğu için kalıcı piksel baseline'ı
değildir; gerçek Windows kabul turunda ayrıca gösterilir. DPI profilleri Qt
başlamadan önce ayar gerektirdiğinden ayrı alt süreçlerde çalıştırılır.

Her kritik yüzey için en az şu durumlar değerlendirilir:

- boş,
- normal örnek veri,
- yoğun/uzun içerik,
- seçili veya odaklı durum,
- ilgili hata/uyarı durumu,
- minimum pencere boyutu.

Kesin senaryo listesi katalogdaki `states` alanıdır. Factory uygulama aşamasında
her durum ayrı çalıştırılabilir kimliğe dönüşür.

## Entegrasyon öncesi çalışma akışı

1. Onaylı `main` checkout'u temiz ve salt-okunur kaynak olarak ölçülür.
2. UI değişikliği ayrı dal/worktree'de yapılır.
3. Aynı makine, Qt sürümü, tema, DPI, sentetik veri ve viewport ile iki checkout
   capture edilir.
4. Önce, sonra, yan yana ve fark görüntüleri yerel raporda sunulur.
5. Davranış ve geometri testleri ayrıca çalıştırılır.
6. Kullanıcı görsel sonucu onaylamadan baseline güncellenmez ve değişiklik
   `main` dalına entegre edilmez.

Preview iş akışı commit, push, build, tag veya release yetkisi vermez; bunların
her biri [CHANGE_PROTOCOL.md](CHANGE_PROTOCOL.md) uyarınca ayrı onaydır.

## Aşamalı teslimat

1. **Envanter ve sözleşme:** katalog, kapsam testi ve bu belge.
2. **Sandbox:** geçici profil, sentetik DB/asset/PDF ve dış-etki blokları.
3. **Launcher/factory:** gerçek widget üreten bağımsız senaryo kayıt sistemi.
4. **Senaryolar:** katalogdaki bütün `planned` yüzeylerin uygulanması.
5. **Capture/rapor:** PNG, manifest, temas sayfası ve önce-sonra farkı.
6. **Geometri/baseline:** taşma kontrolleri ve açık onaylı baseline akışı.
7. **Kabul:** hedefli test, tam suite, gerçek Windows kaynak-modu turu ve gerekli
   frozen smoke.

Bir aşama kırmızıysa sonraki aşamaya geçilmez. Mevcut davranış testleri preview
testleriyle değiştirilmez veya zayıflatılmaz.

## Aşama 1 tamamlanma ölçütü

- Katalog JSON şeması ve kimlikleri geçerlidir.
- Katalogdaki her kaynak yolu ve sembol gerçekten vardır.
- Doğrudan Qt görsel tabanından türeyen üretim sınıfları katalog dışı değildir.
- Runtime modal ve görsel bileşenler elle denetlenerek kapsama alınmıştır.
- Güvenlik sınırları test tarafından zorlanır.
- INDEX ve test rehberi bu kanonik belgeye yönlendirir.
- Üretim UI kaynağı, kullanıcı verisi, build ve artifact değiştirilmemiştir.
