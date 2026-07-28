# Codex inceleme raporu (şablon)

> Yalnız karar ve kanıt. Kod yazma, uygulama önerisini kapsam olarak ver.

## 1. Kısa karar
ONAY / DÜZELTME GEREKLİ / DUR — tek cümle gerekçe.

## 2. Doğrulanan kanıt
Ne, nasıl doğrulandı (dosya, test, ölçüm). Kanıt sınıfını belirt:
kaynak testi / paketli EXE / installer.

## 3. Eksik veya şüpheli kanıt
Hangi iddia kanıtsız; hangi test mock nedeniyle gerçek davranışı kanıtlamıyor;
hangi snapshot değeri eskimiş olabilir.

## 4. Risk
Şiddet + etkilenen değişmez (CRITICAL_INVARIANTS numarası).

## 5. Claude'a verilecek sonraki kapsam
- Hedef ve sınırlar
- Zorunlu kırmızı test
- Doğrulama matrisinden uygulanacak satır
- Verilen izinler (kod / commit / push / build / tag / release)
- Durma koşulları
