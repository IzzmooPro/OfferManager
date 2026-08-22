---
name: offer-review
description: Teklif Yönetim Sistemi diffini, commitini veya seçili dosyaları veri kaybı, migration, transaction, PySide6, PDF/Excel, updater ve release regresyonları açısından kanıta dayalı inceler.
argument-hint: "[diff, commit veya dosya]"
---

# Offer review

1. İnceleme tabanını belirle; `PROJECT_GUIDE/INDEX.md` üzerinden konuya uyan 2–4 belgeyi, ilgili diffi ve gereken çağıranları oku. Kullanıcı düzeltme istemediyse dosya değiştirme.
2. Öncelik: veri kaybı/gerçek DB'ye test; migration ve transaction atomikliği; maliyet-kâr sızması; UI thread/worker cleanup; tema/yerleşim; updater/installer/sürüm; sessiz hata.
3. Eski sorun notunu güncel kodda yeniden doğrulamadan bulgu yapma. Yalnızca diff ile tetiklenebilen gerçek regresyonları raporla.
4. Her bulguya dosya/satır, tetikleme koşulu, etki ve en küçük düzeltmeyi ekle. Stil tercihini hata gibi yükseltme.
5. Kaynak testi, frozen EXE ve installer kanıtını birbirinin yerine kullanma.
6. Bulguları `PROJECT_GUIDE/templates/CODEX_REVIEW_REPORT.md` karar yapısıyla ver; bulgu yoksa açıkça söyle ve kalan test boşluklarını ayrı belirt.
