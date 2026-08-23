---
purpose: Maliyet ve kâr verisinin nerede tutulduğu, nereye asla sızmadığı ve bunun bedeli.
read_when: Kâr paneli, maliyet alanı, teklif kalemi şeması veya herhangi bir dışa aktarma değişikliğinde.
covers:
  - database/schema.sql
  - core/profit.py
  - services/export_service.py
  - pdf/pdf_generator.py
last_verified_commit: 8054be0
last_verified_date: 2026-08-23
volatile: false
---

# 0001 — Maliyet/kâr verisi sınırı

## Bağlam

Kullanıcı teklif hazırlarken iskonto payını görebilmek için kâr analizi istedi. Kâr, satış fiyatı ile alış fiyatı (maliyet) farkından hesaplanır. Maliyet **müşteriye giden hiçbir belgede** görünmemelidir.

## Karar

- **Maliyet yalnız ürün kataloğunda tutulur:** `products.cost_price` (`database/schema.sql`). Kâr hesabı `core/profit.py` içinde yapılır ve yalnız uygulama içi panelde gösterilir.
- **`offer_items` tablosunda maliyet snapshot'ı TUTULMAZ.** Şemada teklif kalemine ait bir maliyet sütunu yoktur; bu bilinçlidir — maliyet teklif kaydına hiç yazılmadığı için oradan sızması fiziksel olarak mümkün değildir.
- **Maliyet ve kâr; teklif PDF'ine, teklif Excel/CSV dışa aktarmasına ve e-postaya dahil edilmez.**
- **Ürün kataloğu dışa aktarmasında "Alış Fiyatı" sütunu bulunabilir** — bu dosya kullanıcının kendi kataloğudur, müşteriye gitmez ve içe aktarma ile gidiş-dönüş uyumludur.

## Sonuçları ve bedeli

- Eski bir teklifin kâr rakamı, **teklif anındaki maliyeti değil, ürünün güncel maliyetini** yansıtır. Maliyet sonradan değişirse geçmiş teklifin kârı da değişmiş görünür.
- Teklifteki ürün **silinmişse veya kodu değişmişse** eşleşme kurulamaz; kâr hesabı o kalem için **0 maliyet** davranışına düşebilir. Bu, gizlilik lehine kabul edilmiş bir doğruluk kaybıdır.
- Kâr, geçmişe dönük denetlenebilir bir kayıt değildir; anlık bir yardımcı göstergedir.

## Geri alma / genişletme koşulu

İleride teklif anındaki maliyetin saklanması istenirse şunlar **birlikte** gerekir:

1. `offer_items` için geriye uyumlu ve tekrar çalıştırılabilir **migration** (nullable + varsayılan),
2. Yeni alanın **hiçbir dışa aktarma, PDF ve e-posta yoluna** girmediğini kanıtlayan gizlilik testleri,
3. Yedek/geri yükleme akışının yeni sütunla uyumu,
4. Bu ADR'nin güncellenmesi.

İlgili değişmezler: [../CRITICAL_INVARIANTS.md](../CRITICAL_INVARIANTS.md) (6. madde) · gizlilik sınırları: [../SECURITY_AND_PRIVACY.md](../SECURITY_AND_PRIVACY.md)
