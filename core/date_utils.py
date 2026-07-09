"""Uygulama tarihlerini veritabanı ve kullanıcı görünümü arasında dönüştürür."""
from datetime import date, datetime
from typing import Optional, Union


_STORAGE_FORMAT = "%Y-%m-%d"
_DISPLAY_FORMAT = "%d.%m.%Y"


def parse_date(value: str) -> Optional[date]:
    value = (value or "").strip()
    for fmt in (_STORAGE_FORMAT, _DISPLAY_FORMAT):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def to_storage_date(value: Union[str, date, datetime, None]) -> str:
    if isinstance(value, (date, datetime)):
        return value.strftime(_STORAGE_FORMAT)
    parsed = parse_date(str(value or ""))
    return parsed.strftime(_STORAGE_FORMAT) if parsed else str(value or "")


def to_display_date(value: Union[str, date, datetime, None], default: str = "") -> str:
    if isinstance(value, (date, datetime)):
        return value.strftime(_DISPLAY_FORMAT)
    parsed = parse_date(str(value or ""))
    return parsed.strftime(_DISPLAY_FORMAT) if parsed else (str(value or "") or default)
