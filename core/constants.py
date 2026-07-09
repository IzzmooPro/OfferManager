"""Uygulama geneli sabitler — tek kaynak, tüm modüller buradan import eder."""

APP_VERSION = "v3.4"

SYM_MAP = {"TL": "₺", "EUR": "€", "USD": "$"}

# Para birimi seçenekleri — combobox'larda tek kaynak (varsayılan: EUR)
CURRENCY_LIST = ["EUR", "USD", "TL"]

UNIT_LIST = ["Adet", "Kg", "Metre", "Litre", "Paket", "Kutu", "Set", "Takım"]

DELIVERY_LIST = [
    "1 Hafta", "2 Hafta", "3 Hafta",
    "1 Ay", "2 Ay", "3 Ay",
    "Stoktan", "Sipariş Üzerine", "Belirtilmemiş",
]

STATUS_ORDER = ["Beklemede", "Onaylandı", "İptal"]

# Açık tema paleti
_STATUS_LIGHT = {
    "Beklemede": {"bg": "#fff8e1", "fg": "#b45309", "dot": "#f59e0b"},
    "Onaylandı": {"bg": "#ecfdf5", "fg": "#065f46", "dot": "#10b981"},
    "İptal":     {"bg": "#fef2f2", "fg": "#991b1b", "dot": "#ef4444"},
}

# Koyu tema paleti
_STATUS_DARK = {
    "Beklemede": {"bg": "#3d2800", "fg": "#fbbf24", "dot": "#f59e0b"},
    "Onaylandı": {"bg": "#052e16", "fg": "#34d399", "dot": "#10b981"},
    "İptal":     {"bg": "#3b0808", "fg": "#f87171", "dot": "#ef4444"},
}

# Geriye dönük uyumluluk için — doğrudan kullanmak yerine get_status_config() tercih edin
STATUS_CONFIG = _STATUS_LIGHT


def get_status_config() -> dict:
    """Aktif temaya göre doğru durum renk paletini döndür (light / dark)."""
    try:
        from ui.utils.theme_manager import get_theme
        return _STATUS_DARK if get_theme().get("name") == "dark" else _STATUS_LIGHT
    except (ImportError, AttributeError):
        return _STATUS_LIGHT
