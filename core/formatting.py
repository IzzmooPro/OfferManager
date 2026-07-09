"""Sayı biçimlendirme — Türkçe para/miktar gösterimi.

Tüm katmanlar (UI tabloları, PDF, Excel/CSV export, özet HTML) parasal
değerleri buradan biçimlendirir; böylece format tek yerden yönetilir.

Türk düzeni: binlik ayracı nokta, ondalık ayracı virgül → 1.234,56
"""


def fmt_number(value, decimals: int = 2) -> str:
    """Sayıyı Türk düzeninde biçimlendirir: 1234.56 → '1.234,56'."""
    s = f"{float(value or 0):,.{decimals}f}"
    # ABD düzenindeki ayraçları takas et (geçici işaretleyici ile)
    return s.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def fmt_money(value, sym: str = "", decimals: int = 2) -> str:
    """Parasal değer + para birimi simgesi: 1234.5, '€' → '1.234,50 €'."""
    s = fmt_number(value, decimals)
    return f"{s} {sym}".strip()
