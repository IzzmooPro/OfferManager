---
paths:
  - "main.py"
  - "ui/**/*.py"
  - "pdf/**/*.py"
---

# PySide6, tema ve belge UI'ı

- Uzun disk/ağ/Excel/PDF işini UI thread'inde bloklama. Worker yaşam döngüsünü kapanışta güvenle bitir; widget'a yalnız ana thread'den dokun.
- Genel QSS'in tablo içi widget ölçülerini ezmediğini kontrol et. Sabit yükseklik/padding ve wrapper layout margin'lerinde `sizeHint` ile gerçek yerleşimi doğrula.
- UI değişikliğini hem açık hem koyu temada render et. Manuel `QPainter` gliflerinde offscreen sonucu kesin kanıt sayma; gerçek Windows ekranını kontrol ettir.
- Uzun yol/URL'yi karakter bazında word-wrap etme; elide + tooltip kullan. Uzun QLineEdit verisini yükleyince kullanıcının başı görmesini sağla.
- PDF/Excel/CSV/e-posta çıktısında müşteriye ait alanları escape/normalize et; dahili maliyet ve kâr bilgisini hiçbir çıktıya ekleme.
- Yeni görsel davranış için ilgili regression testi ekle; yalnız `py_compile` ile tamamlandı deme.
