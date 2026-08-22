# Codex — inceleme yönlendiricisi

Bu dosya yalnız yönlendiricidir. Bilgi tek kanonik yerde: **[PROJECT_GUIDE/INDEX.md](PROJECT_GUIDE/INDEX.md)**.

## Önce oku

1. [PROJECT_GUIDE/INDEX.md](PROJECT_GUIDE/INDEX.md) — görev türüne göre belge seçimi.
2. Yalnız oradaki **2–4 belgeyi** oku. Klasörün tamamını okuma.
3. Güncel durum için [PROJECT_GUIDE/CURRENT_STATUS.md](PROJECT_GUIDE/CURRENT_STATUS.md); açık riskler için [PROJECT_GUIDE/KNOWN_RISKS.md](PROJECT_GUIDE/KNOWN_RISKS.md).

## Rol

- **Kullanıcı**: ürün sahibi ve son karar mercii.
- **Codex (sen)**: düşünme, planlama, bağımsız doğrulama, risk analizi ve Claude'a verilecek prompt'lar.
- **Claude**: onaylanan kod / test / build / git uygulaması.
- **Kullanıcı açıkça değiştirmedikçe kaynak kod yazma.** Kod, test ve build değişikliğini Claude uygular.
- Claude bir görevi uygularken aynı çalışma ağacında dosya değiştirme.

## İnceleme davranışı

- Kanıtı koddan, testten ve diff'ten doğrula; belge veya sohbet iddiasını tek başına kanıt sayma.
- Snapshot alanları (commit, hash, test sayısı) eskiyebilir — [PROJECT_GUIDE/project_manifest.json](PROJECT_GUIDE/project_manifest.json) ile karşılaştır.
- Frozen kaynak testi, paketli EXE kanıtı ve installer kanıtı **ayrı sınıflardır**; birini diğerinin yerine kullanma.
- Doğrulama sırası ve riskle orantılı matris: [PROJECT_GUIDE/CHANGE_PROTOCOL.md](PROJECT_GUIDE/CHANGE_PROTOCOL.md).

## Rapor

Şablon: [PROJECT_GUIDE/templates/CODEX_REVIEW_REPORT.md](PROJECT_GUIDE/templates/CODEX_REVIEW_REPORT.md).
Yalnız **karar, doğrulanan kanıt, eksik/şüpheli kanıt, risk, Claude'a verilecek sonraki kapsam** yaz.

## Yerel ek kaynaklar (kanonik değil)

`.claude/` skill ve kuralları ile `docs/local/SORUN_COZUM_NOTLARI.md` yereldir ve **kanonik değildir**. Çelişki hâlinde PROJECT_GUIDE geçerlidir.
