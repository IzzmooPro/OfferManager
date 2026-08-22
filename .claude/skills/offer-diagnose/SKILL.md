---
name: offer-diagnose
description: Teklif Yönetim Sistemi'nde UI, veri, SQLite, PDF/Excel, SMTP, yedekleme, updater, build veya installer sorunlarında kök nedeni kanıtlar; istenirse küçük genel patch ve hedefli test uygular.
argument-hint: "[belirti ve beklenen sonuç]"
---

# Offer teşhis

1. `$ARGUMENTS` içinden belirti, beklenen sonuç ve yetkiyi ayır. Durum belirsizse `offer_state.py` çalıştır.
2. `references/known-problems-index.md` içinden anahtar kelimeyle eşleşen numarayı bul. Eşleşme varsa `docs/local/SORUN_COZUM_NOTLARI.md` içinde yalnızca o başlıktan sonraki başlığa kadar oku; yoksa defteri açma.
3. `PROJECT_GUIDE/INDEX.md` ile ilgili 2–4 kanonik belgeyi, sonra proje haritasından gerçek yolu seç; girdi -> UI -> service -> DB/çıktı -> cleanup akışını izle.
4. Log, kod yolu, ölçüm veya tekrarlanabilir test olmadan kök neden ilan etme. Eski notu güncel kodda doğrulamadan çözüm sayma.
5. Yalnız teşhis istendiyse dosya değiştirme. Düzeltme istendiyse en küçük genel patch'i uygula; başarı, hata ve rollback/cleanup yolunu hedefli test et. Başarısız testten sonra nedeni incelemeden otomatik tekrar yapma.
6. Kısa raporla: `kök neden / değişiklik / kanıt / kalan gerçek test`.

Yeni ve doğrulanmış kalıcı bir ders varsa kullanıcı istemeden sorun defterini büyütme. Kayıt istendiğinde yalnızca son hali, kanıt ve genellenebilir kuralı ekle; indeksi de güncelle.
