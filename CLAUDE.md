# Claude — çalışma yönlendiricisi

Bu dosya yalnız yönlendiricidir. Bilgi tek kanonik yerde: **[PROJECT_GUIDE/INDEX.md](PROJECT_GUIDE/INDEX.md)**.

## Önce oku

1. [PROJECT_GUIDE/INDEX.md](PROJECT_GUIDE/INDEX.md) — görev türüne göre hangi belgeleri okuyacağını söyler.
2. Yalnız oradaki **2–4 belgeyi** oku. Klasörün tamamını okuma.

## Rol

- **Kullanıcı**: ürün sahibi ve son karar mercii.
- **Codex**: düşünme, planlama, bağımsız denetim, risk analizi, Claude promptları. Kullanıcı açıkça istemedikçe kaynak kod yazmaz.
- **Claude (sen)**: onaylanan kod / test / build / git uygulaması.
- Sen çalışırken Codex aynı çalışma ağacında dosya değiştirmez.

## Değişmez kurallar

- Gerçek kullanıcı verisine dokunma: veritabanı, yedekler, ayarlar, Credential Manager. Testler `tests/conftest.py` izolasyonu altında çalışır; her zaman `python -m pytest tests -q`.
- Maliyet ve kâr bilgisi PDF / Excel / CSV / e-posta çıktısına girmez.
- Commit, push, tag, release, installer yayını ve gerçek veri temizliği **yalnız mevcut mesajda açıkça istenirse** yapılır; her yetki ayrı değerlendirilir.
- Değişiklik akışı: [PROJECT_GUIDE/CHANGE_PROTOCOL.md](PROJECT_GUIDE/CHANGE_PROTOCOL.md).
- Bozulmaması gereken davranışlar: [PROJECT_GUIDE/CRITICAL_INVARIANTS.md](PROJECT_GUIDE/CRITICAL_INVARIANTS.md).

## Rapor

Sonuç raporun ~700 kelimeyi aşmasın; şablon: [PROJECT_GUIDE/templates/CLAUDE_RESULT_REPORT.md](PROJECT_GUIDE/templates/CLAUDE_RESULT_REPORT.md).
Uzun komut çıktısı veya çalışma günlüğü yapıştırma; karar + kanıt özeti yeter.

## Yerel ek kaynaklar (kanonik değil)

`.claude/` altındaki skill ve kurallar ile `SORUN_COZUM_NOTLARI.md` **yereldir ve kanonik değildir**. Çelişki hâlinde PROJECT_GUIDE geçerlidir.
