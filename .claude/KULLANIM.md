# Claude ile Teklif Yönetim Sistemi Çalışma Rehberi

Bu dosya sizin içindir. Claude'a proje klasörüyle birlikte `.claude/` klasörünü verdiğinizde ana kurallar otomatik, ayrıntılar ise yalnızca gerektiğinde okunur.

## Neden daha az token harcar?

- `CLAUDE.md` yalnızca kısa ve kalıcı kuralları taşır.
- `project-map.md` Claude'u doğrudan ilgili dosyaya yollar; tüm repoyu okumasını engeller.
- 32 KB'lik `docs/local/SORUN_COZUM_NOTLARI.md` her görevde açılmaz. `known-problems-index.md` yalnızca eşleşen sorun numarasını buldurur.
- Preflight betiği kök, branch, commit, kaynak sürüm eşleşmesi ve release girdilerini tek seferde kısa raporlar.
- Agent paketi doğrulayıcısı eksik referansı, bozuk skill frontmatter'ını ve legacy belgeye dönüşü yakalar.

## Uzun aradan sonra ilk mesaj

Claude'da projeyi klasör olarak açın ve şunu yazın:

```text
Offer preflight yap. Hiçbir dosyayı değiştirme. Canlı dosyaları esas al; güncel sürüm, git durumu, mimari, yerel/public ayrımı ve dikkat edilmesi gereken en önemli noktaları en fazla 7 Türkçe maddede anlat.
```

## Sorun çözdürme

```text
Offer diagnose akışını kullan.
Belirti: [ne oluyor]
Beklenen: [nasıl olmalı]
Yetki: [yalnız incele / düzelt ve test et]
```

Claude eski bir sorunla benzerlik bulursa sorun defterinin tamamını değil, yalnızca ilgili numaralı bölümü okur. Eski çözümü körlemesine kopyalamaz; güncel kodda yeniden doğrular.

## Yeni özellik veya genel iyileştirme

```text
Offer project haritasını kullan. [istediğim özelliği] mevcut service/model/UI ayrımına uygun biçimde uygula. Önce ilgili kod yolunu bul, sonra en küçük genel değişikliği yap ve hedefli test et. Commit veya push yapma.
```

## Kod incelemesi

```text
Offer review akışını kullan. Mevcut diffi veri kaybı, migration, transaction, UI thread, tema, PDF/Excel bilgi sızması ve updater regresyonu açısından incele. Dosya değiştirme.
```

## Bağımsız doğrulama

```text
Offer verify akışını kullan. Kaynak testi, paketli EXE ve installer kanıtını ayrı raporla. Build veya kurulum yapma; yalnız mevcut kanıtı denetle.
```

## Sürüm/yayın

```text
Offer release akışını vX.Y için kullan. Önce yalnızca preflight ve sürüm eşleşme raporu ver; henüz commit, push veya release yapma.
```

Yayın istiyorsanız bunu ayrıca açıkça yazın. Hedef sürüm verilmeden release başlatılmaz.

## Sorun defterine yeni kayıt

Bir hata gerçekten çözülüp doğrulandıktan sonra şunu söyleyin:

```text
Bu çözümü docs/local/SORUN_COZUM_NOTLARI.md dosyasına yalnızca son haliyle ekle: Belirti, Kök Sebep, Nihai Çözüm, Kanıt ve genellenebilir Kural. Başarısız ara denemeleri yazma; known-problems-index.md indeksini de güncelle.
```

`.claude/skills`, `.claude/rules`, `.claude/scripts`, bu rehber ve agent testleri Git ile paylaşılır. Makineye özel `.claude/settings.local.json`, `.claude/worktrees/` ve generated cache dosyaları paylaşılmaz.

Yerel agent dosyalarını değiştirdikten sonra:

```text
python .claude/scripts/validate_agent_pack.py
python -m pytest .claude/tests -q
```
