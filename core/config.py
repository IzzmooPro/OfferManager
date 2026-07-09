"""Merkezi şirket konfigürasyonu — tüm modüller buradan okur/yazar."""
import logging
from core.app_paths import CFG_PATH

logger = logging.getLogger("config")

_DEFAULTS = {
    "name": "SENSORYUM ENDÜSTRİ TEKN. SAN. VE TİC. LTD. ŞTİ.",
    "address": "HALKPINAR MAH.1203 /11 SOK.NO:4 D:515",
    "tel": "0533 571 61 62", "fax": "",
    "mail": "info@sensoryum.com.tr", "web": "",
    "offer_prefix": "SNS",
    "sales_person1_name": "", "sales_person1_title": "", "sales_person1_email": "",
    "sales_person2_name": "", "sales_person2_title": "", "sales_person2_email": "",
    "sales_person3_name": "", "sales_person3_title": "", "sales_person3_email": "",
    "sales_person4_name": "", "sales_person4_title": "", "sales_person4_email": "",
    "smtp_server": "", "smtp_port": "465", "smtp_user": "",
    # Giriş metni varsayılan olarak BOŞ — kullanıcı isterse Ayarlar'dan doldurur
    "pdf_giris_metni": "",
    "pdf_iskonto":     "Firmanıza özel iskonto uygulanmıştır; belirtilen fiyatlar nettir.",
    "pdf_teslim_yeri": "Teslimat, büromuzdan veya kargo ücreti alıcıya ait olmak üzere kargo aracılığıyla yapılır.",
    "pdf_kur_notu":    "• Döviz cinsinden fiyatlar, fatura tarihindeki TCMB efektif satış kuru üzerinden Türk lirasına çevrilir.",
    "pdf_kdv_notu":    "• Fiyatlara KDV dahil değildir.",
    "pdf_onay_metni":  "Yukarıdaki ürünleri, belirtilen özellik ve koşullarla satın almayı kabul ediyoruz.",
    "pdf_teslim_notu": "Not: Teslim süreleri, teklif tarihindeki stok durumuna göre verilmiştir. Sipariş tarihinde stok durumuna bağlı olarak değişebilir.",
    "pdf_iptal_notu":  "Siparişin yazılı olarak onaylanmasının ardından iptal ve iade kabul edilmez.",
}


def load_company_config() -> dict[str, str]:
    d = dict(_DEFAULTS)
    if CFG_PATH.exists():
        try:
            for line in CFG_PATH.read_text(encoding="utf-8").splitlines():
                if "=" in line:
                    k, _, v = line.partition("=")
                    d[k.strip()] = v.strip().replace("\\n", "\n")
        except (OSError, UnicodeDecodeError) as e:
            logger.warning("Config dosyası okunamadı, varsayılanlar kullanılıyor: %s", e)
    return d


def save_company_config(data: dict[str, str]) -> None:
    CFG_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for k, v in data.items():
        safe_v = str(v).replace("\n", "\\n")
        lines.append(f"{k}={safe_v}")
    tmp = CFG_PATH.with_suffix(".cfg.tmp")
    tmp.write_text("\n".join(lines), encoding="utf-8")
    tmp.replace(CFG_PATH)
