# Karar kayıtları

Kısa kararlar [../DECISIONS.md](../DECISIONS.md) içindeki tabloda tutulur. Bu klasör yalnız **uzun gerekçe gerektiren** kararlar içindir.

## Ne zaman ayrı dosya

- Karar birden çok modülü veya yayın akışını etkiliyorsa
- Değerlendirilen alternatiflerin ve ölçümlerin kaydı gerekiyorsa
- Karar ileride geri alınabilir ve gerekçesi unutulursa risk doğuyorsa

## Dosya adı

`NNNN-kisa-baslik.md` (örn. `0001-onedir-paketleme.md`)

## İçerik

```
---
purpose: <tek cümle>
read_when: <hangi durumda okunur>
covers: [<etkilenen kaynak yolları>]
last_verified_commit: <kısa sha>
last_verified_date: <YYYY-AA-GG>
volatile: false
---

# Başlık
## Bağlam
## Değerlendirilen seçenekler
## Karar
## Sonuçları ve bedeli
## Geri alma koşulu
```

Yeni dosya eklendiğinde [../DECISIONS.md](../DECISIONS.md) tablosuna bir satır eklenir ve buraya bağlantı verilir.
