---
name: offer-project
description: Teklif Yönetim Sistemi'nde yeni özellik, refactor, genel iyileştirme veya proje sorusu için kanonik rehberden doğru mimari ve dosya akışını seçer. Teşhis, review, doğrulama veya release için ilgili özel skill'i kullan.
argument-hint: "[amaç veya özellik]"
---

# Offer project

1. `PROJECT_GUIDE/INDEX.md` içinden göreve uyan 2–4 kanonik belgeyi seç.
2. `references/project-map.md` ile yalnızca `$ARGUMENTS` ile ilgili canlı kod yolunu bul.
3. UI -> service -> model/DB -> export/PDF etkisini gerektiği kadar izle; tüm katmanları otomatik yükleme.
4. Mevcut benzer kalıbı doğrula ve en küçük genel değişikliği uygula.
5. `PROJECT_GUIDE/TESTING_GUIDE.md` matrisinden hedefli testleri seç; Python değişikliğinde `py_compile`, UI değişikliğinde uygun render/gerçek görsel kanıt ekle.
6. Commit, push, build, install, tag ve release yetkilerini değişiklik yetkisinden ayrı tut.
