"""Teklif kimliğiyle oluşturulan PDF dosya adları için güvenlik sınırı."""
from pathlib import Path


_WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}
_INVALID_FILENAME_CHARS = set('<>:"/\\|?*')


def validate_offer_number(value) -> str:
    """Teklif numarasını hem kimlik hem de dosya adı bileşeni olarak doğrula."""
    offer_no = str(value or "").strip()
    base_name = offer_no.split(".", 1)[0].upper()
    if (
        not offer_no
        or offer_no in {".", ".."}
        or offer_no[-1:] in {".", " "}
        or base_name in _WINDOWS_RESERVED_NAMES
        or any(char in _INVALID_FILENAME_CHARS or ord(char) < 32 for char in offer_no)
    ):
        raise ValueError("Teklif numarası geçersiz karakter içeriyor.")
    return offer_no


def offer_pdf_path(directory, offer_no) -> Path:
    """PDF hedefinin verilen kökün altında kaldığını doğrulayarak döndür."""
    root = Path(directory).resolve()
    target = (root / f"{validate_offer_number(offer_no)}.pdf").resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValueError("Teklif PDF yolu geçersiz.") from exc
    return target
