"""
PDF teklif oluşturucu.
ReportLab ile modern kurumsal teklif belgesi üretir (lacivert/mavi tasarım):
  - Sayfa üstü: beyaz alanda logo + lacivert diyagonal bantta TEKLİF NO / TARİH
  - Bilgi kartları (Ödeme Koşulu / Teslim Süresi), müşteri kartı
  - Numaralı zebra ürün tablosu, GENEL TOPLAM bandı + Notlar kutusu
  - Sayfa altı: lacivert iletişim bandı + QR kod (web/e-posta)
Türkçe karakter desteği: gömülü DejaVu ya da Windows sistem fontları.
"""
import logging
import datetime
import math
import re
from pathlib import Path
from core.app_paths import (
    ASSETS_DIR,
    LOGO_PATH,
    SIG1_PATH,
    SIG2_PATH,
    SIG3_PATH,
    SIG4_PATH,
    DEFAULT_LOGO_PATH,
    LOGO_DISABLED_PATH,
)

# İmza görselleri yetkili sırasıyla eşleşir: 1. Yetkili ↔ SIG1, 2. ↔ SIG2 ...
_SIG_PATHS = (SIG1_PATH, SIG2_PATH, SIG3_PATH, SIG4_PATH)
from xml.sax.saxutils import escape as _xml_escape
from core.constants import SYM_MAP
from core.date_utils import to_display_date
from core.formatting import fmt_money
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.lib.utils import ImageReader, simpleSplit
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame, NextPageTemplate,
    Paragraph, Spacer, Table, TableStyle, Image, KeepTogether
)
from reportlab.graphics.shapes import (
    Drawing, Circle, Rect, Line, PolyLine, Polygon, String
)
from reportlab.graphics import renderPDF
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas as _Canvas

try:
    from reportlab.graphics.barcode import qr as _qr_module
except ImportError:  # barkod eklentisi yoksa QR sessizce atlanır
    _qr_module = None

logger = logging.getLogger("pdf_generator")

# ── Renk paleti (mockup tasarımı) ────────────────────────────────────────────
NAVY        = colors.HexColor("#131C36")   # koyu lacivert bant/başlık
BLUE        = colors.HexColor("#1878E8")   # marka mavisi (şerit, ikonlar)
BLUE_ON_NAVY= colors.HexColor("#6FB1F5")   # lacivert zemin üstü vurgu metni
LIGHT_BG    = colors.HexColor("#F4F6FA")   # açık kutu zemini
BORDER      = colors.HexColor("#DCE4EE")   # kart/tablo kenarlığı
LINE_SOFT   = colors.HexColor("#E3E9F2")   # tablo satır ayracı
ROW_ALT     = colors.HexColor("#F5F7FA")   # zebra satır
TEXT_MUTED  = colors.HexColor("#5A6B83")   # ikincil metin
FOOT_MUTED  = colors.HexColor("#9FB0C8")   # bant üstü soluk metin

# ── Sayfa metrikleri ─────────────────────────────────────────────────────────
MARGIN         = 12 * mm
HEADER_H       = 34 * mm   # ilk sayfa üst bandı
LATER_HEADER_H = 13 * mm   # devam sayfaları üst bandı
FOOTER_H       = 22 * mm   # alt iletişim bandı


class _NumberedCanvas(_Canvas):
    """Her sayfaya 'Sayfa X / Y' ekleyen canvas — tek sayfalı belgelerde gizlenir."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_pages: list = []

    def showPage(self):
        self._saved_pages.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved_pages)
        for idx, state in enumerate(self._saved_pages):
            self.__dict__.update(state)
            if total > 1:
                self._draw_page_number(idx + 1, total)
            _Canvas.showPage(self)
        _Canvas.save(self)

    def _draw_page_number(self, page_num: int, total: int):
        self.saveState()
        font_name = _FONT_REGULAR if _FONTS_LOADED else "Helvetica"
        self.setFont(font_name, 6.5)
        self.setFillColor(FOOT_MUTED)
        self.drawCentredString(A4[0] / 2, 2.2 * mm, f"Sayfa {page_num} / {total}")
        self.restoreState()


def _safe_str(value) -> str:
    """None veya boş değerleri güvenli stringe çevirir.
    PDF'de 'None' yazmasını engeller.
    """
    if value is None:
        return ""
    s = str(value)
    return "" if s.strip().lower() == "none" else s


def _esc(value) -> str:
    """Kullanıcı verisini Paragraph'ın XML ayrıştırıcısı için kaçışlar.

    Ürün adı/açıklama gibi metinlerde '<', '>' veya '&' bulunursa
    ReportLab Paragraph ayrıştırması çöker — tüm serbest metin buradan geçer.
    """
    return _xml_escape(_safe_str(value))


def _esc_ml(value) -> str:
    """Kaçışla + satır sonlarını koru — çok satırlı ayar metinleri için.

    Paragraph düz satır sonu karakterini boşluğa çevirir; ayarlardaki çok
    satırlı metinler (giriş metni, notlar) satır yapısını <br/> ile korur.
    """
    return _esc(value).replace("\n", "<br/>")

# ── Font kayıt sistemi ────────────────────────────────────────────────────────

# Font arama sırası:
# 1. Projeye gömülü DejaVu (her platformda çalışır — önerilen)
# 2. Windows sistem fontları
# 3. Linux sistem fontları
_ASSETS_FONTS = ASSETS_DIR / "fonts"

_FONT_SEARCH = [
    # Projeye gömülü Poppins (mockup fontu — modern geometrik, tam Türkçe)
    (str(_ASSETS_FONTS / "Poppins-Regular.ttf"), str(_ASSETS_FONTS / "Poppins-SemiBold.ttf")),
    # Projeye gömülü DejaVu (yedek — garantili Türkçe)
    (str(_ASSETS_FONTS / "DejaVuSans.ttf"),      str(_ASSETS_FONTS / "DejaVuSans-Bold.ttf")),
    # Windows sistem fontları (yedek)
    ("C:/Windows/Fonts/arial.ttf",               "C:/Windows/Fonts/arialbd.ttf"),
    ("C:/Windows/Fonts/calibri.ttf",             "C:/Windows/Fonts/calibrib.ttf"),
    ("C:/Windows/Fonts/tahoma.ttf",              "C:/Windows/Fonts/tahomabd.ttf"),
    ("C:/Windows/Fonts/verdana.ttf",             "C:/Windows/Fonts/verdanab.ttf"),
]

_FONT_REGULAR  = "Helvetica"
_FONT_BOLD     = "Helvetica-Bold"
_FONTS_LOADED  = False
_STYLE_COUNTER = 0


def _load_fonts():
    """Türkçe destekli TTF fontunu sisteme göre yükler."""
    global _FONT_REGULAR, _FONT_BOLD, _FONTS_LOADED
    if _FONTS_LOADED:
        return

    for reg_path, bold_path in _FONT_SEARCH:
        if Path(reg_path).exists():
            try:
                pdfmetrics.registerFont(TTFont("TR_Regular", reg_path))
                pdfmetrics.registerFont(TTFont("TR_Bold",    bold_path))
                pdfmetrics.registerFontFamily(
                    "TR",
                    normal="TR_Regular",
                    bold="TR_Bold",
                )
                _FONT_REGULAR = "TR_Regular"
                _FONT_BOLD    = "TR_Bold"
                _FONTS_LOADED = True
                logger.info("Font yüklendi: %s", reg_path)
                return
            except Exception as e:
                logger.warning("Font yüklenemedi (%s): %s", reg_path, e)

    logger.warning("Türkçe font bulunamadı, Helvetica kullanılacak (karakterler bozuk çıkabilir)")
    _FONTS_LOADED = True


# ── Config okuma ─────────────────────────────────────────────────────────────

def _load_company() -> dict:
    from core.config import load_company_config
    return load_company_config()


# ── Ana üretici ──────────────────────────────────────────────────────────────

from models.offer import Offer

def generate_pdf(offer_data: Offer, output_path: str) -> str:
    """PDF oluştur ve atomik olarak kaydet.

    Önce geçici dosyaya yazar (.tmp); tamamlanınca hedef konuma taşır.
    Disk dolu / hata durumunda geçici dosya temizlenir, orijinal dokunulmaz.
    """
    validity = (offer_data.validity or "").strip()
    payment_term = (offer_data.payment_term or "").strip()
    if not validity or validity.casefold() == "belirtilmemiş":
        raise ValueError("PDF için Teklif Geçerlilik Süresi zorunludur.")
    if not re.fullmatch(r"\d+\s*g[üu]n", validity, flags=re.IGNORECASE):
        raise ValueError(
            "PDF için geçerlilik tarih olarak değil, gün sayısı olarak girilmelidir.")
    if not payment_term or payment_term.casefold() == "belirtilmemiş":
        raise ValueError("PDF için Ödeme Şekli / Vadesi zorunludur.")

    _load_fonts()
    company  = _load_company()
    currency = offer_data.currency or "EUR"
    sym      = SYM_MAP.get(currency, currency)

    logger.info("PDF oluşturuluyor: %s → %s", offer_data.offer_no or "?", output_path)

    # Yerleşim stratejisi — öngörülebilir doğal akış:
    #   1. Normal yerleşim tek sayfaya sığıyorsa onu kullan.
    #   2. Sığmıyorsa kompakt (daha küçük font/boşluk) dene; sayfa sayısını
    #      azaltıyorsa kompaktı seç.
    #   3. Tablo ortasına asla zorla sayfa sonu eklenmez — sayfa dolunca
    #      kendiliğinden böler, başlık satırı her sayfada tekrarlanır.
    tmp_path = Path(output_path + ".tmp")
    normal_path = Path(output_path + ".normal.tmp")
    compact_path = Path(output_path + ".compact.tmp")
    try:
        normal_info = _build_pdf_document(
            offer_data, company, sym, normal_path, compact=False)
        chosen_path = normal_path

        if normal_info["pages"] > 1:
            compact_info = _build_pdf_document(
                offer_data, company, sym, compact_path, compact=True)
            if compact_info["pages"] < normal_info["pages"]:
                chosen_path = compact_path

        chosen_path.replace(tmp_path)
        tmp_path.replace(Path(output_path))
    except Exception:
        for candidate in (tmp_path, normal_path, compact_path):
            if candidate.exists():
                try:
                    candidate.unlink()
                except OSError:
                    pass
        raise
    finally:
        for candidate in (normal_path, compact_path):
            if candidate.exists():
                try:
                    candidate.unlink()
                except OSError:
                    pass

    logger.info("PDF tamamlandı: %s", output_path)
    return output_path


def _build_pdf_document(offer_data: Offer, company: dict, sym: str,
                        output_path: Path, compact: bool = False) -> dict:
    """Bir yerleşim adayı oluştur ve sayfa sayısını döndür."""
    W, H = A4
    body_w = W - 2 * MARGIN
    frame_kw = dict(leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    frame_bottom = FOOTER_H + 4 * mm
    frame_first = Frame(MARGIN, frame_bottom, body_w,
                        H - HEADER_H - 4 * mm - frame_bottom, **frame_kw)
    frame_later = Frame(MARGIN, frame_bottom, body_w,
                        H - LATER_HEADER_H - 4 * mm - frame_bottom, **frame_kw)

    def _on_first(cv, doc):
        _draw_first_header(cv, offer_data, company)
        _draw_footer(cv, company)

    def _on_later(cv, doc):
        _draw_later_header(cv, offer_data)
        _draw_footer(cv, company)

    doc = BaseDocTemplate(
        str(output_path), pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=HEADER_H, bottomMargin=FOOTER_H,
    )
    doc.addPageTemplates([
        PageTemplate(id="First", frames=[frame_first], onPage=_on_first),
        PageTemplate(id="Later", frames=[frame_later], onPage=_on_later),
    ])

    gap_large = 2 * mm if compact else 3.5 * mm
    gap_small = 1.5 * mm if compact else 2.5 * mm

    story = [NextPageTemplate("Later")]
    story += _info_cards(offer_data, body_w)
    story.append(Spacer(1, gap_small))
    story += _customer_card(offer_data, body_w)
    intro = _intro_text(company)
    if intro:
        story.append(Spacer(1, gap_small))
        story += intro
    story.append(Spacer(1, gap_large))
    story += _product_table(offer_data, body_w, sym, compact=compact)
    story.append(Spacer(1, gap_large))
    # Toplam bandı + Notlar kutusu tek grup: sayfa sonunda bölünmesin
    story.append(KeepTogether(_totals_and_notes(offer_data, company, body_w, sym)))

    tail = _features_row(body_w, compact=compact)
    tail += _signature_block(company, body_w, compact=compact)
    story.append(KeepTogether(tail))

    doc.build(story, canvasmaker=_NumberedCanvas)
    return {"pages": doc.page}


# ── Yardımcı: stil üretici ───────────────────────────────────────────────────

def _s(size=9, bold=False, align=TA_LEFT, color=colors.black,
       leading=None, left_indent=0, first_indent=0) -> ParagraphStyle:
    global _STYLE_COUNTER
    _STYLE_COUNTER += 1
    return ParagraphStyle(
        name=f"s{_STYLE_COUNTER}",
        fontSize=size,
        fontName=_FONT_BOLD if bold else _FONT_REGULAR,
        alignment=align,
        leading=leading if leading is not None else size + 5,
        textColor=color,
        leftIndent=left_indent,
        firstLineIndent=first_indent,
    )


_TR_MONTHS = ("Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
              "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık")


def _long_date(value) -> str:
    """Tarihi '22 Temmuz 2025' biçiminde göster (mockup formatı)."""
    disp = to_display_date(value)  # gg.aa.yyyy
    try:
        dd, mm_, yy = disp.split(".")
        return f"{int(dd)} {_TR_MONTHS[int(mm_) - 1]} {yy}"
    except (ValueError, IndexError):
        return disp


# ── Canvas çizimleri (bantlar) ───────────────────────────────────────────────

def _draw_first_header(cv, offer: Offer, company: dict):
    """İlk sayfa üst bandı: solda logo, sağda diyagonal lacivert blok."""
    W, H = A4
    y0 = H - HEADER_H
    x_top = W * 0.44          # diyagonalın üst kenardaki başlangıcı
    x_bot = W * 0.54          # diyagonalın alt kenardaki bitişi
    stripe_w = 8 * mm

    cv.saveState()
    # Mavi diyagonal şerit (lacivert bloğun hemen solunda)
    p = cv.beginPath()
    p.moveTo(x_top - stripe_w, H)
    p.lineTo(x_top, H)
    p.lineTo(x_bot, y0)
    p.lineTo(x_bot - stripe_w, y0)
    p.close()
    cv.setFillColor(BLUE)
    cv.drawPath(p, stroke=0, fill=1)
    # Lacivert blok
    p = cv.beginPath()
    p.moveTo(x_top, H)
    p.lineTo(W, H)
    p.lineTo(W, y0)
    p.lineTo(x_bot, y0)
    p.close()
    cv.setFillColor(NAVY)
    cv.drawPath(p, stroke=0, fill=1)

    # Logo — kullanıcı kaldırdıysa boş, yoksa önce özel logo sonra varsayılan
    if not LOGO_DISABLED_PATH.exists():
        _logo = LOGO_PATH if LOGO_PATH.exists() else DEFAULT_LOGO_PATH
        if _logo.exists():
            try:
                img = ImageReader(str(_logo))
                iw, ih = img.getSize()
                scale = min((62 * mm) / iw, (16 * mm) / ih)
                lw, lh = iw * scale, ih * scale
                cv.drawImage(img, MARGIN, y0 + (HEADER_H - lh) / 2.0,
                             lw, lh, mask='auto')
            except Exception as e:
                logger.warning("Logo yüklenemedi: %s", e)

    # Sağ blok metinleri (ikon + etiket + değer) — blok, lacivert alanın
    # tam görünür kısmında (x_bot..W) yatayca ortalanır
    no_str = _safe_str(offer.offer_no)
    date_str = _long_date(offer.date)
    val_w = max(pdfmetrics.stringWidth(s, _FONT_REGULAR, 9)
                for s in (no_str, date_str))
    block_w = 36 * mm + val_w      # ikon(6) + etiket(30) + değer
    bx = x_bot + (W - x_bot - block_w) / 2.0
    label_x = bx + 6 * mm
    val_x = bx + 36 * mm

    cv.setFillColor(colors.white)
    cv.setFont(_FONT_BOLD, 22)
    cv.drawCentredString(bx + block_w / 2.0, H - 12.5 * mm, "TEKLİF")
    cv.setFont(_FONT_BOLD, 8.5)
    cv.drawString(label_x, H - 20.5 * mm, "TEKLİF NO")
    cv.drawString(label_x, H - 27 * mm, "TEKLİF TARİHİ")

    # Belge ikonu (TEKLİF NO satırı)
    cv.setStrokeColor(colors.white)
    cv.setLineWidth(0.9)
    doc_y = H - 21.3 * mm
    cv.roundRect(bx, doc_y, 3.2 * mm, 4 * mm, 0.5 * mm, stroke=1, fill=0)
    cv.setLineWidth(0.6)
    cv.line(bx + 0.8 * mm, doc_y + 2.6 * mm, bx + 2.4 * mm, doc_y + 2.6 * mm)
    cv.line(bx + 0.8 * mm, doc_y + 1.4 * mm, bx + 2.4 * mm, doc_y + 1.4 * mm)
    # Takvim ikonu (TEKLİF TARİHİ satırı)
    cal_y = H - 27.9 * mm
    cv.setLineWidth(0.9)
    cv.roundRect(bx, cal_y, 3.6 * mm, 3.4 * mm, 0.4 * mm, stroke=1, fill=0)
    cv.line(bx + 0.9 * mm, cal_y + 3.4 * mm, bx + 0.9 * mm, cal_y + 4.1 * mm)
    cv.line(bx + 2.7 * mm, cal_y + 3.4 * mm, bx + 2.7 * mm, cal_y + 4.1 * mm)
    cv.setLineWidth(0.6)
    cv.line(bx, cal_y + 2.4 * mm, bx + 3.6 * mm, cal_y + 2.4 * mm)

    cv.setFillColor(BLUE_ON_NAVY)
    cv.setFont(_FONT_REGULAR, 9)
    cv.drawString(val_x, H - 20.5 * mm, no_str)
    cv.drawString(val_x, H - 27 * mm, date_str)
    cv.restoreState()


def _draw_later_header(cv, offer: Offer):
    """Devam sayfaları: ince lacivert bant + teklif no/tarih."""
    W, H = A4
    y0 = H - LATER_HEADER_H
    cv.saveState()
    cv.setFillColor(NAVY)
    cv.rect(0, y0, W, LATER_HEADER_H, stroke=0, fill=1)
    cv.setFillColor(BLUE)
    cv.rect(0, y0 - 1.2 * mm, W, 1.2 * mm, stroke=0, fill=1)
    cv.setFillColor(colors.white)
    cv.setFont(_FONT_BOLD, 11)
    cv.drawString(MARGIN, y0 + 4.5 * mm, "TEKLİF")
    cv.setFillColor(BLUE_ON_NAVY)
    cv.setFont(_FONT_REGULAR, 8.5)
    cv.drawRightString(
        W - MARGIN, y0 + 4.5 * mm,
        f"{_safe_str(offer.offer_no)}  |  {_long_date(offer.date)}")
    cv.restoreState()


def _draw_footer(cv, company: dict):
    """Alt iletişim bandı: şirket bilgileri + QR kod (web/e-posta)."""
    W, H = A4
    cv.saveState()
    cv.setFillColor(NAVY)
    cv.rect(0, 0, W, FOOTER_H, stroke=0, fill=1)
    cv.setFillColor(BLUE)
    cv.rect(0, FOOTER_H, W, 1.2 * mm, stroke=0, fill=1)

    name = _safe_str(company.get("name", ""))
    addr = _safe_str(company.get("address", "")).replace("\n", " ")
    tel  = _safe_str(company.get("tel", ""))
    mail = _safe_str(company.get("mail", ""))
    web  = _safe_str(company.get("web", ""))
    qr_data = web or mail

    # Küçük beyaz kontur ikonlar — hepsi (x, y) sol-alt köşesine göre ~3.4mm
    def icon_pin(x, y):
        cv.setStrokeColor(colors.white); cv.setLineWidth(0.8)
        cv.circle(x + 1.4 * mm, y + 2.1 * mm, 1.1 * mm, stroke=1, fill=0)
        cv.line(x + 0.55 * mm, y + 1.35 * mm, x + 1.4 * mm, y, )
        cv.line(x + 2.25 * mm, y + 1.35 * mm, x + 1.4 * mm, y)

    def icon_phone(x, y):
        cv.setStrokeColor(colors.white)
        cv.setFillColor(colors.white)
        cv.setLineWidth(0.8)
        p = cv.beginPath()
        p.arc(x, y - 0.6 * mm, x + 3 * mm, y + 2.4 * mm, 35, 110)
        cv.drawPath(p, stroke=1, fill=0)
        cv.circle(x + 0.55 * mm, y + 1.0 * mm, 0.5 * mm, stroke=0, fill=1)
        cv.circle(x + 2.45 * mm, y + 1.0 * mm, 0.5 * mm, stroke=0, fill=1)

    def icon_mail(x, y):
        cv.setStrokeColor(colors.white); cv.setLineWidth(0.7)
        cv.rect(x, y, 3.4 * mm, 2.4 * mm, stroke=1, fill=0)
        cv.line(x, y + 2.4 * mm, x + 1.7 * mm, y + 1.1 * mm)
        cv.line(x + 3.4 * mm, y + 2.4 * mm, x + 1.7 * mm, y + 1.1 * mm)

    def icon_globe(x, y):
        cx, cy, r = x + 1.5 * mm, y + 1.3 * mm, 1.4 * mm
        cv.setStrokeColor(colors.white); cv.setLineWidth(0.7)
        cv.circle(cx, cy, r, stroke=1, fill=0)
        cv.line(cx - r, cy, cx + r, cy)
        cv.ellipse(cx - r * 0.45, cy - r, cx + r * 0.45, cy + r, stroke=1, fill=0)

    # Üç sütunlu düzen (mockup): solda ad+adres, ortada tel+e-posta,
    # sağda web, en sağda QR — hepsi bantta dikeyce dengeli
    # Sol blok: konum ikonu + şirket adı, altında adres (en çok 2 satır)
    text_x = MARGIN + 5.5 * mm
    icon_pin(MARGIN, 11.6 * mm)
    cv.setFillColor(colors.white)
    cv.setFont(_FONT_BOLD, 7.5)
    cv.drawString(text_x, 12.8 * mm, name)
    cv.setFillColor(FOOT_MUTED)
    cv.setFont(_FONT_REGULAR, 6.8)
    addr_lines = simpleSplit(addr, _FONT_REGULAR, 6.8, 80 * mm)[:2] if addr else []
    ay = 9.6 * mm
    for line in addr_lines:
        cv.drawString(text_x, ay, line)
        ay -= 3 * mm

    # Orta blok: telefon + e-posta alt alta (tek değer varsa ortalanır)
    mid_x = W * 0.51
    mid_rows = [(icon_phone, tel), (icon_mail, mail)]
    mid_rows = [(ic, v) for ic, v in mid_rows if v]
    ys = (12.6 * mm, 7.6 * mm) if len(mid_rows) == 2 else (9.8 * mm,)
    cv.setFont(_FONT_REGULAR, 7)
    for (icon_fn, value), y in zip(mid_rows, ys):
        icon_fn(mid_x, y - 0.4 * mm)
        cv.setFillColor(colors.white)
        cv.drawString(mid_x + 5.2 * mm, y, value)

    # Sağ blok: web adresi (dikeyde ortalı)
    if web:
        wx = W * 0.69
        icon_globe(wx, 9.1 * mm)
        cv.setFillColor(colors.white)
        cv.setFont(_FONT_REGULAR, 7)
        cv.drawString(wx + 5.2 * mm, 9.8 * mm, web)

    cv.setFillColor(FOOT_MUTED)
    cv.setFont(_FONT_REGULAR, 6)
    cv.drawString(MARGIN, 2 * mm,
                  f"Baskı Tarihi: {datetime.date.today().strftime('%d.%m.%Y')}")

    if qr_data and _qr_module is not None:
        try:
            url = qr_data if "@" in qr_data or qr_data.startswith("http") \
                else f"https://{qr_data}"
            widget = _qr_module.QrCodeWidget(url, barLevel="M")
            b = widget.getBounds()
            size = 15 * mm
            pad = 1.4 * mm
            qx = W - MARGIN - size
            qy = (FOOTER_H - size) / 2.0
            cv.setFillColor(colors.white)
            cv.roundRect(qx - pad, qy - pad, size + 2 * pad, size + 2 * pad,
                         1.5 * mm, stroke=0, fill=1)
            d = Drawing(size, size, transform=[
                size / (b[2] - b[0]), 0, 0, size / (b[3] - b[1]), 0, 0])
            d.add(widget)
            renderPDF.draw(d, cv, qx, qy)
        except Exception as e:
            logger.warning("QR kod çizilemedi: %s", e)
    cv.restoreState()


# ── Vektör ikonlar ───────────────────────────────────────────────────────────

def _card_icon(kind: str, sz=11 * mm) -> Drawing:
    """Kart/başlık ikonu: mavi dolu daire üstünde beyaz kontur sembol."""
    c = sz / 2.0
    sw = max(0.7, sz / (11 * mm))   # ikon küçülünce çizgi de incelsin
    d = Drawing(sz, sz)
    d.add(Circle(c, c, sz * 0.42, fillColor=BLUE, strokeColor=None))
    if kind == "wallet":
        d.add(Rect(c - sz * 0.23, c - sz * 0.16, sz * 0.46, sz * 0.32,
                   rx=sz * 0.05, ry=sz * 0.05, fillColor=None,
                   strokeColor=colors.white, strokeWidth=sw))
        d.add(Line(c - sz * 0.23, c + sz * 0.07, c + sz * 0.23, c + sz * 0.07,
                   strokeColor=colors.white, strokeWidth=sw * 0.8))
        d.add(Circle(c + sz * 0.13, c - sz * 0.04, sz * 0.035,
                     fillColor=colors.white, strokeColor=None))
    elif kind == "clock":
        d.add(Circle(c, c, sz * 0.24, fillColor=None,
                     strokeColor=colors.white, strokeWidth=sw))
        d.add(Line(c, c, c, c + sz * 0.15,
                   strokeColor=colors.white, strokeWidth=sw))
        d.add(Line(c, c, c + sz * 0.12, c,
                   strokeColor=colors.white, strokeWidth=sw))
    elif kind == "person":
        d.add(Circle(c, c + sz * 0.11, sz * 0.115, fillColor=colors.white,
                     strokeColor=None))
        d.add(Polygon([c - sz * 0.21, c - sz * 0.24,
                       c + sz * 0.21, c - sz * 0.24,
                       c + sz * 0.14, c - sz * 0.035,
                       c - sz * 0.14, c - sz * 0.035],
                      fillColor=colors.white, strokeColor=None))
    elif kind == "doc":
        d.add(Rect(c - sz * 0.13, c - sz * 0.19, sz * 0.26, sz * 0.38,
                   rx=sz * 0.03, ry=sz * 0.03, fillColor=None,
                   strokeColor=colors.white, strokeWidth=sw))
        d.add(Line(c - sz * 0.06, c + sz * 0.07, c + sz * 0.06, c + sz * 0.07,
                   strokeColor=colors.white, strokeWidth=sw * 0.7))
        d.add(Line(c - sz * 0.06, c, c + sz * 0.06, c,
                   strokeColor=colors.white, strokeWidth=sw * 0.7))
        d.add(Line(c - sz * 0.06, c - sz * 0.07, c + sz * 0.06, c - sz * 0.07,
                   strokeColor=colors.white, strokeWidth=sw * 0.7))
    elif kind == "calc":
        d.add(Rect(c - sz * 0.15, c - sz * 0.2, sz * 0.3, sz * 0.4,
                   rx=sz * 0.04, ry=sz * 0.04, fillColor=None,
                   strokeColor=colors.white, strokeWidth=sw))
        d.add(Line(c - sz * 0.08, c + sz * 0.1, c + sz * 0.08, c + sz * 0.1,
                   strokeColor=colors.white, strokeWidth=sw * 0.8))
        d.add(Circle(c - sz * 0.07, c - sz * 0.02, sz * 0.025,
                     fillColor=colors.white, strokeColor=None))
        d.add(Circle(c + sz * 0.07, c - sz * 0.02, sz * 0.025,
                     fillColor=colors.white, strokeColor=None))
        d.add(Circle(c - sz * 0.07, c - sz * 0.11, sz * 0.025,
                     fillColor=colors.white, strokeColor=None))
        d.add(Circle(c + sz * 0.07, c - sz * 0.11, sz * 0.025,
                     fillColor=colors.white, strokeColor=None))
    return d


def _feature_icon(kind: str) -> Drawing:
    """Alt özellik şeridi ikonu: lacivert konturlu daire + sembol."""
    sz = 9 * mm
    c = sz / 2.0
    d = Drawing(sz, sz)
    d.add(Circle(c, c, sz * 0.44, fillColor=None,
                 strokeColor=NAVY, strokeWidth=1))
    if kind == "check":
        d.add(PolyLine([c - 1.7 * mm, c + 0.1 * mm,
                        c - 0.5 * mm, c - 1.2 * mm,
                        c + 1.8 * mm, c + 1.4 * mm],
                       strokeColor=NAVY, strokeWidth=1.1))
    elif kind == "target":
        d.add(Circle(c, c, 1.8 * mm, fillColor=None,
                     strokeColor=NAVY, strokeWidth=0.9))
        d.add(Circle(c, c, 0.6 * mm, fillColor=NAVY, strokeColor=None))
    elif kind == "gear":
        d.add(Circle(c, c, 1.4 * mm, fillColor=None,
                     strokeColor=NAVY, strokeWidth=0.9))
        for k in range(6):
            ang = k * math.pi / 3
            d.add(Line(c + 2.0 * mm * math.cos(ang), c + 2.0 * mm * math.sin(ang),
                       c + 2.9 * mm * math.cos(ang), c + 2.9 * mm * math.sin(ang),
                       strokeColor=NAVY, strokeWidth=0.9))
    elif kind == "star":
        pts = []
        for i in range(10):
            ang = math.pi / 2 + i * math.pi / 5
            r = 2.4 * mm if i % 2 == 0 else 1.1 * mm
            pts += [c + r * math.cos(ang), c + r * math.sin(ang)]
        d.add(Polygon(pts, fillColor=NAVY, strokeColor=None))
    return d


def _th_icon(kind: str, sz=3.4 * mm) -> Drawing:
    """Tablo başlığı ikonu — beyaz kontur, saydam zemin (lacivert şerit üstü)."""
    d = Drawing(sz, sz)
    c = sz / 2.0
    w = colors.white
    sw = 0.7
    if kind == "no":
        d.add(Circle(c, c, sz * 0.4, fillColor=None, strokeColor=w,
                     strokeWidth=sw))
        d.add(Circle(c, c, sz * 0.09, fillColor=w, strokeColor=None))
    elif kind == "layers":
        d.add(Rect(sz * 0.24, sz * 0.1, sz * 0.62, sz * 0.62, fillColor=None,
                   strokeColor=w, strokeWidth=sw))
        d.add(Rect(sz * 0.1, sz * 0.28, sz * 0.62, sz * 0.62, fillColor=None,
                   strokeColor=w, strokeWidth=sw))
    elif kind == "barcode":
        for dx, tall in ((0.10, 1), (0.30, .65), (0.50, 1), (0.70, .65), (0.88, 1)):
            x = sz * dx
            h = sz * 0.6 * tall
            d.add(Line(x, c - h / 2, x, c + h / 2, strokeColor=w, strokeWidth=sw))
    elif kind == "box":
        d.add(Rect(sz * 0.15, sz * 0.15, sz * 0.7, sz * 0.7, fillColor=None,
                   strokeColor=w, strokeWidth=sw))
        d.add(Line(sz * 0.15, sz * 0.62, sz * 0.85, sz * 0.62,
                   strokeColor=w, strokeWidth=sw * 0.8))
    elif kind == "doc":
        d.add(Rect(sz * 0.2, sz * 0.06, sz * 0.6, sz * 0.88,
                   rx=sz * 0.06, ry=sz * 0.06, fillColor=None,
                   strokeColor=w, strokeWidth=sw))
        d.add(Line(sz * 0.32, sz * 0.6, sz * 0.68, sz * 0.6,
                   strokeColor=w, strokeWidth=sw * 0.8))
        d.add(Line(sz * 0.32, sz * 0.42, sz * 0.68, sz * 0.42,
                   strokeColor=w, strokeWidth=sw * 0.8))
    elif kind == "clock":
        d.add(Circle(c, c, sz * 0.36, fillColor=None, strokeColor=w,
                     strokeWidth=sw))
        d.add(Line(c, c, c, c + sz * 0.22, strokeColor=w, strokeWidth=sw))
        d.add(Line(c, c, c + sz * 0.17, c, strokeColor=w, strokeWidth=sw))
    elif kind == "tag":
        d.add(Polygon([c, sz * 0.06, sz * 0.94, c, c, sz * 0.94, sz * 0.06, c],
                      fillColor=None, strokeColor=w, strokeWidth=sw))
        d.add(Circle(c, c, sz * 0.07, fillColor=w, strokeColor=None))
    elif kind == "coin":
        d.add(Circle(c, c, sz * 0.4, fillColor=None, strokeColor=w,
                     strokeWidth=sw))
        d.add(Circle(c, c, sz * 0.19, fillColor=None, strokeColor=w,
                     strokeWidth=sw * 0.8))
    elif kind == "calc":
        d.add(Rect(sz * 0.22, sz * 0.06, sz * 0.56, sz * 0.88,
                   rx=sz * 0.05, ry=sz * 0.05, fillColor=None,
                   strokeColor=w, strokeWidth=sw))
        d.add(Line(sz * 0.34, sz * 0.7, sz * 0.66, sz * 0.7,
                   strokeColor=w, strokeWidth=sw * 0.8))
        for px in (0.36, 0.64):
            for py in (0.46, 0.26):
                d.add(Circle(sz * px, sz * py, sz * 0.05,
                             fillColor=w, strokeColor=None))
    return d


def _th_cell(icon_kind, text, style, col_width, font_size, cell_pad):
    """Başlık hücresi: ikon + metin, kolon içinde ORTALI.

    Hücreyi tam dolduran iç tablo [boşluk, ikon, metin, boşluk] kurulur;
    soldaki ve sağdaki boşluk eşit olduğundan ikon+metin grubu kolonun tam
    ortasına oturur (hAlign hücre içinde güvenilir çalışmadığı için)."""
    para = Paragraph(text.replace("\n", "<br/>"), style)
    if icon_kind is None:
        return para
    lines = text.split("\n")
    tw = max(pdfmetrics.stringWidth(ln, _FONT_BOLD, font_size)
             for ln in lines) + 2
    icon_w = 4.4 * mm
    avail = max(col_width - cell_pad, icon_w + tw)
    lead = max((avail - icon_w - tw) / 2.0, 0)
    inner = Table([["", _th_icon(icon_kind), para, ""]],
                  colWidths=[lead, icon_w, tw, avail - 2 * lead - icon_w - tw])
    inner.setStyle(TableStyle([
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ("LEFTPADDING",   (0,0), (-1,-1), 0),
        ("RIGHTPADDING",  (0,0), (-1,-1), 0),
        ("TOPPADDING",    (0,0), (-1,-1), 0),
        ("BOTTOMPADDING", (0,0), (-1,-1), 0),
    ]))
    return inner


def _num_badge(n: int, compact: bool = False) -> Drawing:
    """Ürün tablosu satır numarası: mavi daire içinde beyaz rakam."""
    sz = 4.8 * mm if compact else 5.4 * mm
    c = sz / 2.0
    fs = 6 if compact else 6.5
    d = Drawing(sz, sz)
    d.add(Circle(c, c, c, fillColor=NAVY, strokeColor=None))
    d.add(String(c, c - fs * 0.36, str(n), fontName=_FONT_BOLD,
                 fontSize=fs, fillColor=colors.white, textAnchor="middle"))
    return d


# ── Bölümler ─────────────────────────────────────────────────────────────────

def _delivery_values(offer_data: Offer) -> set:
    return {(it.delivery_time or "").strip() or "2-3 Hafta"
            for it in offer_data.items}


def _delivery_summary(offer_data: Offer) -> str:
    """Kart için teslim süresi: tüm kalemler aynıysa onu, değilse tabloya yönlendir."""
    values = _delivery_values(offer_data)
    if len(values) == 1:
        return next(iter(values))
    return "Tabloda belirtilmiştir" if values else "-"


def _info_cards(offer_data: Offer, width):
    """Ödeme Koşulu + Teslim Süresi kartları (yuvarlak köşeli, ikonlu)."""
    gap = 5 * mm
    cw = (width - gap) / 2.0

    def card(icon_kind, label, value):
        inner = Table(
            [[_card_icon(icon_kind),
              [Paragraph(label, _s(7, True, color=NAVY)),
               Paragraph(_esc(value), _s(11, True, color=NAVY))]]],
            colWidths=[13 * mm, cw - 13 * mm])
        inner.setStyle(TableStyle([
            ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
            ("BOX",           (0,0), (-1,-1), 0.8, BORDER),
            ("ROUNDEDCORNERS",[6]),
            ("LEFTPADDING",   (0,0), (0,0),   6),
            ("LEFTPADDING",   (1,0), (1,0),   4),
            ("RIGHTPADDING",  (0,0), (-1,-1), 4),
            ("TOPPADDING",    (0,0), (-1,-1), 5),
            ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ]))
        return inner

    row = Table(
        [[card("wallet", "ÖDEME KOŞULU", offer_data.payment_term or ""),
          "",
          card("clock", "TESLİM SÜRESİ", _delivery_summary(offer_data))]],
        colWidths=[cw, gap, cw])
    row.setStyle(TableStyle([
        ("VALIGN",        (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING",   (0,0), (-1,-1), 0),
        ("RIGHTPADDING",  (0,0), (-1,-1), 0),
        ("TOPPADDING",    (0,0), (-1,-1), 0),
        ("BOTTOMPADDING", (0,0), (-1,-1), 0),
    ]))
    return [row]


def _customer_card(offer_data: Offer, width):
    """Müşteri bilgileri — iki eşit sütunlu, kenarlıklı kart (ikonsuz).
    İki yarıda da etiket/iki nokta sütunları aynı genişlikte."""
    lb = _s(7.5, True, color=NAVY)
    vb = _s(8.5)

    def row(label, value):
        return [Paragraph(label, lb), Paragraph(":", lb),
                Paragraph(_esc(value), vb)]

    left_rows = [
        row("FİRMA ADI", offer_data.company_name or ""),
        row("ADRES",     offer_data.customer_address or ""),
    ]
    right_rows = [
        row("İLGİLİ KİŞİ", offer_data.contact_person or ""),
        row("E-POSTA",     offer_data.customer_email or ""),
        row("TELEFON",     offer_data.customer_phone or ""),
    ]

    # Kolon toplamı TAM sayfa genişliği olmalı — dar kalırsa tablo ortalanıp
    # kenarlar üstteki kart/alttaki tablo hizasından içeri kayar
    pad = 8          # kart iç kenar payı (pt)
    half = width / 2.0
    inner_w = half - 2 * pad     # hücre içi pay (LEFT + RIGHT pad) düşülür
    label_w = 20 * mm
    ts = TableStyle([
        ("VALIGN",        (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING",   (0,0), (-1,-1), 0),
        ("RIGHTPADDING",  (0,0), (-1,-1), 2),
        ("BOTTOMPADDING", (0,0), (-1,-1), 2),
        ("TOPPADDING",    (0,0), (-1,-1), 0),
    ])
    lt = Table(left_rows,  colWidths=[label_w, 3 * mm, inner_w - label_w - 3 * mm])
    lt.setStyle(ts)
    rt = Table(right_rows, colWidths=[label_w, 3 * mm, inner_w - label_w - 3 * mm])
    rt.setStyle(ts)

    wrapper = Table([[lt, rt]], colWidths=[half, half])
    wrapper.setStyle(TableStyle([
        ("VALIGN",        (0,0), (-1,-1), "TOP"),
        ("BOX",           (0,0), (-1,-1), 0.8, BORDER),
        ("ROUNDEDCORNERS",[6]),
        ("LEFTPADDING",   (0,0), (-1,-1), pad),
        ("RIGHTPADDING",  (0,0), (-1,-1), pad),
        ("TOPPADDING",    (0,0), (-1,-1), 7),
        ("BOTTOMPADDING", (0,0), (-1,-1), 7),
    ]))
    return [wrapper]


def _is_enabled(company: dict, key: str) -> bool:
    return company.get(f"{key}_enabled", "1") != "0"


def _intro_text(company: dict):
    if not _is_enabled(company, "pdf_giris_metni"):
        return []
    giris = company.get("pdf_giris_metni", "")
    elements = []
    if giris:
        elements.append(Paragraph(_esc_ml(giris), _s(9)))
    return elements


def _product_table(offer_data: Offer, width, sym, compact=False):
    """Ürün tablosu — lacivert başlık, mavi numara rozetleri, zebra satırlar.
    Sayfaya sığmazsa doğal akışla bölünür, başlık her sayfada tekrarlanır."""
    font_size = 7.5 if compact else 8.5
    leading = 9.5 if compact else None
    th_l = _s(font_size, True,  TA_LEFT,   colors.white, leading)
    th_c = _s(font_size, True,  TA_CENTER, colors.white, leading)
    th_r = _s(font_size, True,  TA_RIGHT,  colors.white, leading)
    tc = _s(font_size, False, TA_LEFT, colors.black, leading)
    tm = _s(font_size, False, TA_CENTER, colors.black, leading)
    tr = _s(font_size, False, TA_RIGHT, colors.black, leading)

    # Teslim süresi tüm kalemlerde aynıysa sütun gereksiz — üstteki kartta
    # zaten yazıyor (mockup'ta da bu sütun yok). Farklıysa sütun gösterilir.
    show_delivery = len(_delivery_values(offer_data)) > 1

    # Kolon genişlikleri (Ürün Adı kalan alanı alır) — dar kolonlar ikon +
    # başlık sığacak kadar geniş olmalı
    if show_delivery:
        col_w = [12*mm, 24*mm, 28*mm, 26*mm, 14*mm, 16*mm, 12*mm, 21*mm, 21*mm]
    else:
        col_w = [12*mm, 25*mm, 34*mm, 30*mm, 14*mm, 13*mm, 22*mm, 22*mm]
    diff  = width - sum(col_w)
    col_w[2] += diff

    # Tüm başlıklar kendi kolonunda ortalı (kullanıcı tercihi). Ortalama
    # _th_cell içinde kolon genişliğine göre kurulur → gerçek col_w gerekli.
    cell_pad = 2 * (3 if compact else 4)
    hdr_specs = [("no", "No"), ("barcode", "Malzeme\nKodu"),
                 ("box", "Ürün Adı"), ("doc", "Açıklama"), ("layers", "Adet")]
    if show_delivery:
        hdr_specs.append(("clock", "Teslim\nSüresi"))
    hdr_specs += [("tag", "Br"), ("coin", "Net Fiyat"), ("calc", "Toplam")]
    headers = [
        _th_cell(icon, txt, th_c, col_w[i], font_size, cell_pad)
        for i, (icon, txt) in enumerate(hdr_specs)
    ]

    data = [headers]
    for i, item in enumerate(offer_data.items, 1):
        qty = item.quantity or 1.0
        price = item.unit_price or 0.0
        total = item.total_price or (qty * price)
        qty_str = f"{qty:g}" if qty == int(qty) else f"{qty:.2f}"
        cells = [
            _num_badge(i, compact),
            Paragraph(_esc(item.product_code), tc),
            Paragraph(_esc(item.product_name), tc),
            Paragraph(_esc(item.description), tc),
            Paragraph(qty_str, tm),
        ]
        if show_delivery:
            cells.append(Paragraph(_esc(item.delivery_time or "2-3 Hafta"), tm))
        cells += [
            Paragraph(_esc(item.unit or "Adet"), tm),
            Paragraph(fmt_money(price, sym), tr),
            Paragraph(fmt_money(total, sym), tr),
        ]
        data.append(cells)

    table = Table(data, colWidths=col_w, repeatRows=1)
    style = TableStyle([
        ("BACKGROUND",    (0,0), (-1,0),  NAVY),
        ("TEXTCOLOR",     (0,0), (-1,0),  colors.white),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ("ALIGN",         (0,0), (0,-1),  "CENTER"),
        ("BOX",           (0,0), (-1,-1), 0.8, BORDER),
        ("LINEBELOW",     (0,1), (-1,-2), 0.5, LINE_SOFT),
        # Dikey kolon çizgileri: gövdede yumuşak gri, başlıkta açık lacivert
        ("LINEBEFORE",    (1,1), (-1,-1), 0.5, LINE_SOFT),
        ("LINEBEFORE",    (1,0), (-1,0),  0.5, colors.HexColor("#3A4A73")),
        ("ROUNDEDCORNERS",[5]),
        ("TOPPADDING",    (0,0), (-1,-1), 2.5 if compact else 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 2.5 if compact else 5),
        ("LEFTPADDING",   (0,0), (-1,-1), 3 if compact else 4),
        ("RIGHTPADDING",  (0,0), (-1,-1), 3 if compact else 4),
    ])
    for r in range(1, len(data)):
        if (r - 1) % 2 == 1:
            style.add("BACKGROUND", (0,r), (-1,r), ROW_ALT)
    table.setStyle(style)
    return [table]


def _is_redundant_validity_note(note: str) -> bool:
    """Otomatik sabit-fiyat cümlesini tekrar eden notları ayıkla."""
    normalized = re.sub(r"[^a-zçğıöşü0-9]+", " ", (note or "").casefold())
    words = set(normalized.split())
    has_fixed_price = any(word.startswith("sabit") for word in words)
    has_validity_context = "geçerlilik" in words or "teklif" in words
    return has_fixed_price and has_validity_context


def _clean_note(text: str) -> str:
    """Config notlarındaki baştaki madde işaretini ayıkla — kutu kendi ekler."""
    return re.sub(r"^\s*[•\-\*]\s*", "", _safe_str(text).strip())


def _total_box(offer_data: Offer, width, sym):
    """GENEL TOPLAM lacivert bandı; iskonto varsa ara toplam satırlarıyla."""
    total = offer_data.total_amount or 0.0
    discount = getattr(offer_data, 'discount_amount', 0.0) or 0.0
    show_discount = (discount > 0
                     and getattr(offer_data, "show_discount", True))

    data = []
    style_extra = []
    if show_discount:
        subtotal = total + discount
        discount_type = getattr(offer_data, "discount_type", "amount")
        discount_value = float(getattr(offer_data, "discount_value", 0) or 0)
        if discount_type == "percent":
            discount_label = f"İskonto (%{discount_value:g})"
        else:
            discount_label = "İskonto"
        data.append([
            Paragraph("Ara Toplam", _s(8.5, False, TA_LEFT, colors.white)),
            "",
            Paragraph(fmt_money(subtotal, sym),
                      _s(8.5, False, TA_RIGHT, colors.white)),
        ])
        data.append([
            Paragraph(discount_label,
                      _s(8.5, False, TA_LEFT, colors.HexColor("#FF9B9B"))),
            "",
            Paragraph(f"-{fmt_money(discount, sym)}",
                      _s(8.5, False, TA_RIGHT, colors.HexColor("#FF9B9B"))),
        ])
        style_extra.append(
            ("LINEBELOW", (0,1), (-1,1), 0.5, colors.HexColor("#3A4A73")))

    # Mockup düzeni: solda ikon, yanında etiket + büyük tutar alt alta
    label_row = len(data)
    data.append([
        _card_icon("calc", 10 * mm),
        [Paragraph("GENEL TOPLAM", _s(9.5, True, TA_LEFT, colors.white)),
         Paragraph(fmt_money(total, sym),
                   _s(15, True, TA_LEFT, colors.white, leading=19))],
        "",
    ])

    icon_w = 15 * mm
    val_w = (width - icon_w) * 0.58   # iskonto tutarları sarmadan sığmalı
    t = Table(data, colWidths=[icon_w, width - icon_w - val_w, val_w])
    span_extra = []
    for r in range(label_row):           # iskonto satırları: etiket ikon
        span_extra.append(("SPAN", (0, r), (1, r)))  # sütunuyla birleşik
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), NAVY),
        ("ROUNDEDCORNERS",[6]),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ("SPAN",          (1,label_row), (2,label_row)),
        ("LEFTPADDING",   (0,0), (-1,-1), 10),
        ("LEFTPADDING",   (1,label_row), (1,label_row), 6),
        ("RIGHTPADDING",  (0,0), (-1,-1), 10),
        ("TOPPADDING",    (0,0), (-1,-1), 3),
        ("BOTTOMPADDING", (0,0), (-1,-1), 3),
        ("TOPPADDING",    (0,label_row), (-1,label_row), 8),
        ("BOTTOMPADDING", (0,label_row), (-1,label_row), 8),
    ] + style_extra + span_extra))
    return t


def _notes_box(offer_data: Offer, company: dict, width):
    """Notlar kutusu — geçerlilik, iskonto/teslimat koşulları ve ayar notları."""
    bullets = []

    validity = (offer_data.validity or "").strip()
    match = re.fullmatch(r"(\d+)\s*g[üu]n", validity, flags=re.IGNORECASE)
    if match:
        validity_text = (
            f"Teklif geçerlilik süresi {int(match.group(1))} gündür; "
            f"bu süre boyunca fiyat teklifimiz sabittir.")
    else:
        validity_text = f"Teklif geçerlilik süresi: {validity}" if validity else ""
    if validity_text:
        bullets.append((validity_text, True))
    note = (offer_data.validity_note or "").strip()
    if note and not _is_redundant_validity_note(note):
        bullets.append((note, True))

    iskonto = company.get("pdf_iskonto", "") if _is_enabled(company, "pdf_iskonto") else ""
    # İskonto uygulanmamış teklifte yanıltıcı iskonto metni gösterme.
    if iskonto and (
        getattr(offer_data, 'discount_amount', 0) <= 0
        or not getattr(offer_data, 'show_discount', True)
    ):
        iskonto = ""
    if iskonto:
        bullets.append((iskonto, False))

    for key in ("pdf_kdv_notu", "pdf_kur_notu", "pdf_teslim_yeri",
                "pdf_teslim_notu", "pdf_iptal_notu"):
        text = company.get(key, "") if _is_enabled(company, key) else ""
        text = _clean_note(text)
        if text:
            bullets.append((text, False))

    title = Table(
        [[_card_icon("doc", 8 * mm),
          Paragraph("Notlar", _s(10, True, color=NAVY))]],
        colWidths=[11 * mm, width - 11 * mm - 18])
    title.setStyle(TableStyle([
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ("LEFTPADDING",   (0,0), (-1,-1), 0),
        ("RIGHTPADDING",  (0,0), (-1,-1), 0),
        ("TOPPADDING",    (0,0), (-1,-1), 0),
        ("BOTTOMPADDING", (0,0), (-1,-1), 0),
    ]))

    # Asılı girinti: satır kaydığında metin madde işaretinin altına değil,
    # madde metninin hizasına iner
    bullet_style_kw = dict(color=colors.HexColor("#33415C"), leading=8.5,
                           left_indent=7, first_indent=-7)
    rows = [[title]]
    for text, emphasize in bullets:
        body = _esc_ml(_clean_note(text))
        if emphasize:
            body = f"<b>{body}</b>"
        rows.append([Paragraph(f"•  {body}", _s(6.5, **bullet_style_kw))])

    # Mockup: kutu yok — beyaz zemin, soldaki dikey ayraç wrapper'da çizilir
    t = Table(rows, colWidths=[width])
    t.setStyle(TableStyle([
        ("LEFTPADDING",   (0,0), (-1,-1), 12),
        ("RIGHTPADDING",  (0,0), (-1,-1), 4),
        ("TOPPADDING",    (0,0), (-1,-1), 1.5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 1.5),
        ("TOPPADDING",    (0,0), (-1,0),  4),
        ("BOTTOMPADDING", (0,-1), (-1,-1), 4),
    ]))
    return t


def _totals_and_notes(offer_data: Offer, company: dict, width, sym):
    """Sol: GENEL TOPLAM bandı, sağ: Notlar kutusu — yan yana."""
    left_w = 66 * mm
    gap = 5 * mm
    right_w = width - left_w - gap
    t = Table(
        [[_total_box(offer_data, left_w, sym), "",
          _notes_box(offer_data, company, right_w)]],
        colWidths=[left_w, gap, right_w])
    t.setStyle(TableStyle([
        ("VALIGN",        (0,0), (-1,-1), "TOP"),
        ("LINEBEFORE",    (2,0), (2,-1),  0.9, NAVY),   # dikey ayraç (mockup)
        ("LEFTPADDING",   (0,0), (-1,-1), 0),
        ("RIGHTPADDING",  (0,0), (-1,-1), 0),
        ("TOPPADDING",    (0,0), (-1,-1), 0),
        ("BOTTOMPADDING", (0,0), (-1,-1), 0),
    ]))
    return [t]


_FEATURES = [
    ("check",  "Güvenilir",     "Kaliteli ve güvenilir ürünler"),
    ("target", "Çözüm Odaklı",  "İhtiyacınıza özel çözümler"),
    ("gear",   "Teknik Destek", "Satış öncesi ve sonrası destek"),
    ("star",   "Uzman Kadro",   "Deneyimli ve uzman ekip"),
]


def _features_row(width, compact=False):
    """Alt özellik şeridi: 4 ikonlu güven mesajı."""
    cw = width / 4.0
    cells = []
    for kind, title, desc in _FEATURES:
        inner = Table(
            [[_feature_icon(kind),
              [Paragraph(title, _s(7.5, True, color=NAVY)),
               Paragraph(desc, _s(6.5, color=TEXT_MUTED, leading=8))]]],
            colWidths=[10 * mm, cw - 10 * mm])
        inner.setStyle(TableStyle([
            ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
            ("LEFTPADDING",   (0,0), (-1,-1), 0),
            ("RIGHTPADDING",  (0,0), (-1,-1), 2),
            ("TOPPADDING",    (0,0), (-1,-1), 0),
            ("BOTTOMPADDING", (0,0), (-1,-1), 0),
        ]))
        cells.append(inner)

    row = Table([cells], colWidths=[cw] * 4)
    row.setStyle(TableStyle([
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ("LINEABOVE",     (0,0), (-1,0),  0.5, LINE_SOFT),
        ("LEFTPADDING",   (0,0), (-1,-1), 2),
        ("RIGHTPADDING",  (0,0), (-1,-1), 2),
        ("TOPPADDING",    (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
    ]))
    return [Spacer(1, 2 * mm if compact else 4 * mm), row]


def _signature_block(company, width, compact=False):
    n  = _s(8.5, True)
    sm = _s(8.5)
    elements = [Spacer(1, 2 * mm if compact else 4 * mm)]

    def person_col(name, title, email, sig_path=None):
        if not name:
            return [Spacer(1, 5*mm)]
        items = [Paragraph(f"<b>{_esc(name)}</b>", n),
                 Paragraph(_esc(title), sm),
                 Paragraph(_esc(email), sm)]
        if sig_path and Path(sig_path).exists():
            try:
                items.append(Spacer(1, 2*mm))
                items.append(Image(str(sig_path), width=35*mm, height=14*mm,
                                   kind='proportional'))
            except (OSError, ValueError) as e:
                logger.warning("İmza görseli yüklenemedi (%s): %s", sig_path, e)
        return items

    # Adı dolu yetkilileri sırasıyla topla — imza görseli AYNI sıradan gelir
    persons = []
    for i in range(1, 5):
        name = (company.get(f"sales_person{i}_name", "") or "").strip()
        if name:
            persons.append((
                name,
                company.get(f"sales_person{i}_title", ""),
                company.get(f"sales_person{i}_email", ""),
                str(_SIG_PATHS[i - 1]),
            ))
    if persons:
        cols = [person_col(n, t, e, p) for n, t, e, p in persons]
        sig = Table([cols], colWidths=[width / len(cols)] * len(cols))
        sig.setStyle(TableStyle([
            ("VALIGN",       (0,0), (-1,-1), "TOP"),
            ("LEFTPADDING",  (0,0), (-1,-1), 0),
            ("RIGHTPADDING", (0,0), (-1,-1), 0),
        ]))
        elements.append(sig)
    else:
        elements.append(Spacer(1, 5*mm))
    elements.append(Spacer(1, 3*mm if compact else 6*mm))

    onay = _s(8.5)
    onay_metni = company.get("pdf_onay_metni", "") if _is_enabled(company, "pdf_onay_metni") else ""
    if onay_metni:
        elements.append(Paragraph(_esc_ml(onay_metni), onay))
    elements.append(Spacer(1, 1.5*mm if compact else 3*mm))

    auth = Table(
        [[Paragraph("Yetkili :", onay),     Paragraph("Onay Tarihi:", onay)],
         [Spacer(1, 5*mm if compact else 8*mm),
          Spacer(1, 5*mm if compact else 8*mm)],
         [Paragraph("Kaşe / İmza :", onay), Paragraph("", onay)]],
        colWidths=[width/2, width/2]
    )
    auth.setStyle(TableStyle([("VALIGN", (0,0), (-1,-1), "TOP")]))
    elements.append(auth)
    return elements
