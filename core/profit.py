"""Kâr / iskonto hesaplama — dahili kullanım, saf fonksiyonlar.

Bu modül DB/UI/PDF katmanlarından tamamen bağımsızdır ve sonuçları
YALNIZCA kullanıcının kendi ekranında (teklif oluşturma sayfasındaki
"Kâr Analizi" paneli) gösterilir — PDF, Excel export ve e-posta akışları
bu modülü hiç import etmez.

Fonksiyonlar canlı UI güncellemesinde (iskonto kutusuna her tuş
vuruşunda) çağrıldığı için hata FIRLATMAZ — geçersiz/eksik veri
(sıfır satış, maliyet eksik vb.) her zaman güvenli bir varsayılana
(0) düşer.
"""


def calculate_margin(total_cost: float, total_sale: float) -> dict:
    """Toplam kâr ve kâr marjı yüzdesini hesaplar.

    total_sale: iskonto SONRASI toplam satış tutarı.
    Döner: {"profit": .., "margin_pct": ..}
    """
    total_cost = float(total_cost or 0)
    total_sale = float(total_sale or 0)
    profit = round(total_sale - total_cost, 2)
    margin_pct = round(profit / total_sale * 100, 2) if total_sale > 0 else 0.0
    return {"profit": profit, "margin_pct": margin_pct}


def max_discount(total_cost: float, total_sale: float) -> dict:
    """Maliyetin altına düşmeden verilebilecek en fazla iskontoyu hesaplar.

    total_sale: iskonto ÖNCESİ (ara toplam) satış tutarı olmalı — "bu
    tutardan en fazla ne kadar indirebilirim" sorusuna cevap verir.
    Zaten maliyetin altındaysa (total_cost > total_sale) 0 döner —
    negatif bir "iskonto" anlamsız olur.
    Döner: {"max_discount_amount": .., "max_discount_pct": ..}
    """
    total_cost = float(total_cost or 0)
    total_sale = float(total_sale or 0)
    amount = round(max(0.0, total_sale - total_cost), 2)
    pct = round(amount / total_sale * 100, 2) if total_sale > 0 else 0.0
    return {"max_discount_amount": amount, "max_discount_pct": pct}


# Sarı bölge eşiği: marj bu yüzdenin altına inince "inceliyor" sayılır.
DEFAULT_YELLOW_THRESHOLD = 10.0


def margin_status(margin_pct: float, yellow_threshold: float = DEFAULT_YELLOW_THRESHOLD) -> str:
    """Marj yüzdesini trafik ışığı durumuna çevirir: 'green' / 'yellow' / 'red'.

    red    : marj <= 0 (başabaş veya zarar)
    yellow : 0 < marj <= yellow_threshold (marj inceliyor)
    green  : marj > yellow_threshold (sağlıklı)
    """
    margin_pct = float(margin_pct or 0)
    if margin_pct <= 0:
        return "red"
    if margin_pct <= yellow_threshold:
        return "yellow"
    return "green"


def count_items_missing_cost(cost_prices: list) -> int:
    """Alış fiyatı girilmemiş (<= 0) kalem sayısını döner.

    Kâr hesabının yanıltıcı olabileceği durumları (maliyeti unutulmuş
    ürünler) panelde uyarı olarak göstermek için kullanılır.
    """
    return sum(1 for c in cost_prices if float(c or 0) <= 0)
