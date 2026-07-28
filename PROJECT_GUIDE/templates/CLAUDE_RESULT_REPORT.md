# Claude sonuç raporu (şablon)

> Yaklaşık 700 kelime sınırı. Uzun komut çıktısı ve çalışma günlüğü yapıştırma.

## 1. Sonuç
Madde/kod, karar (GEÇTİ / BAŞARISIZ / TETİKLENEMEDİ) ve tek cümlelik özet.

## 2. Kök neden
Nerede, neden. `dosya:satır` referansı ver.

## 3. Değişiklik
Değişen dosyalar ve satır sayısı; davranışın özeti. Kapsam dışı bırakılanlar.

## 4. Kritik davranış
Korunan veya yeni gelen değişmez; hangi eski davranış aynen sürüyor.

## 5. Test kanıtı
Hedefli test sonucu, ilgili regresyon grubu, gerekiyorsa tam suite sayısı.
Kırmızıydı deniyorsa **gerçek hata mesajı tek satır**.
Kanıt sınıfını belirt: kaynak testi / paketli EXE / installer.

## 6. Git durumu
`HEAD`, upstream, ahead/behind, çalışma ağacı temiz mi, commit/push yapıldı mı.
Yapılmadıysa açıkça "commit yapılmadı" yaz.

## 7. Güvenlik ve temizlik
Gerçek kullanıcı verisi parmak izi, credential sınırı, süreç/geçici dosya artığı,
artifact hash'lerinin değişip değişmediği.

## 8. Kalan risk
Şiddet + sonraki adım. Yeni risk çıktıysa KNOWN_RISKS'e eklenmesi gerektiğini yaz.

## 9. Kullanıcıdan beklenen karar
Tek ve net soru; hangi izin gerekiyor (commit / push / build / tag / release).
