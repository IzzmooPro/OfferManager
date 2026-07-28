---
purpose: Kullanıcı / Codex / Claude iş bölümü, devir kuralları ve rapor şablonlarına yönlendirme.
read_when: Claude uygulaması başlarken, Codex incelemesi başlarken, görev devrinde.
covers: []
last_verified_commit: 060baf3
last_verified_date: 2026-07-28
volatile: false
---

# İşbirliği akışı

## Roller

| Rol | Yapar | Yapmaz |
|---|---|---|
| **Kullanıcı** | Ürün sahibi; kapsamı belirler, izin verir, son kararı verir | — |
| **Codex** | Düşünme, planlama, bağımsız doğrulama, risk analizi, Claude'a verilecek prompt'lar | Kullanıcı açıkça istemedikçe **kaynak kod yazmaz**; Claude çalışırken aynı ağaçta dosya değiştirmez |
| **Claude** | Onaylanan kod / test / build / git uygulaması, kanıt üretimi | İzinsiz commit, push, tag, release, installer çalıştırma, gerçek veri değişikliği |

Yetkiler **ayrı ayrı** verilir: kod değişikliği ≠ commit ≠ push ≠ build ≠ tag ≠ release. Bir turda verilen izin sonraki tura taşınmaz.

## Tur döngüsü

1. **Kullanıcı** kapsamı ve izinleri yazar.
2. **Codex** salt-okunur inceler, riskleri ve eksik kanıtı çıkarır, Claude için kapsam üretir.
3. **Claude** [CHANGE_PROTOCOL.md](CHANGE_PROTOCOL.md) akışını uygular ve kanıtla raporlar.
4. **Codex** kanıtı bağımsız doğrular; eksikse sonraki kapsamı yazar.
5. **Kullanıcı** onaylar veya yön değiştirir.

Aynı anda tek uygulayıcı vardır. Devirde [templates/TASK_HANDOFF.md](templates/TASK_HANDOFF.md) doldurulur (≤30 satır).

## Kanıt dili

- Kanıt sınıfları (kaynak testi / paketli EXE / installer) karıştırılmaz — [VERIFICATION_GUIDE.md](VERIFICATION_GUIDE.md).
- "Tüm kontroller temiz" gibi belirsiz ifade kullanılmaz; sayılar, dosya adları ve git durumu yazılır.
- Bir test kırmızıydı deniyorsa **gerçek hata mesajı** tek satır olarak verilir.
- Yapılmayan adım açıkça "yapılmadı" diye yazılır.

## Rapor şablonları

- Claude sonucu (~700 kelime): [templates/CLAUDE_RESULT_REPORT.md](templates/CLAUDE_RESULT_REPORT.md)
- Codex incelemesi: [templates/CODEX_REVIEW_REPORT.md](templates/CODEX_REVIEW_REPORT.md)
- Görev devri: [templates/TASK_HANDOFF.md](templates/TASK_HANDOFF.md)

## Token bütçesi

- `CLAUDE.md` / `AGENTS.md` yalnız yönlendirir (≤~60 satır).
- [INDEX.md](INDEX.md) yalnız görev → belge eşlemesidir.
- Bir görevde **en fazla 2–4 belge** okunur; klasörün tamamı okunmaz.
- Aynı bilgi tek kanonik yerde durur; tekrar yerine bağlantı verilir.
- Uzun log/komut çıktısı paylaşılmaz; karar + kanıt özeti yeterlidir.
- Aktif görev devri kısa tutulur; tamamlanan iş [AUDIT_HISTORY.md](AUDIT_HISTORY.md) / [DECISIONS.md](DECISIONS.md) içinde birkaç satıra sıkıştırılır.
