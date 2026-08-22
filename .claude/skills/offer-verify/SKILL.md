---
name: offer-verify
description: Teklif Yönetim Sistemi'nde kaynak testi, paketli EXE, installer veya release hazırlığı iddialarını birbirinden ayırarak bağımsız kanıtla doğrular. Değişiklik uygulamak veya release yapmak için kullanılmaz.
argument-hint: "[doğrulanacak iddia, artifact veya kapsam]"
---

# Offer verify

1. Kök, HEAD ve kirli durumu `offer_state.py` ile yeniden ölç; snapshot'lara canlı gerçek muamelesi yapma.
2. `PROJECT_GUIDE/INDEX.md` içinden doğrulama konusuna uyan 2–4 belgeyi seç. Frozen/installer için `VERIFICATION_GUIDE.md`, test seçimi için `TESTING_GUIDE.md` kullan.
3. Kaynak, frozen EXE ve installer kanıtını ayrı sınıflandır. Bir sınıfın geçmesi diğerini kanıtlamaz.
4. Mevcut log, hash, boyut, sürüm, exit code ve görsel davranışı iddiayla eşleştir. Mock testin gerçek ağ/UAC/installer davranışını kanıtlamadığını belirt.
5. Kullanıcı ayrıca istemedikçe dosya değiştirme, build alma, installer çalıştırma veya dış sistemi değiştirme.
6. Kararı `doğrulandı / eksik kanıt / risk / sonraki en dar test` olarak raporla.
