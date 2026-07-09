"""Belge ve şablon servisi (HTML/PDF için)."""
import datetime
from html import escape as _esc
from models.offer import Offer
from core.constants import SYM_MAP
from core.formatting import fmt_money
from core.date_utils import to_display_date


class DocumentService:
    @staticmethod
    def generate_offer_summary_html(offer: "Offer") -> str:
        """Kullanıcının gördüğü teklif özet HTML'ini oluşturur — tema uyumlu."""
        from ui.utils.theme_manager import get_theme
        t = get_theme()
        fg = t['text_primary']
        fg2 = t['text_secondary']
        fg_m = t['text_muted']
        bg = t['bg_card']
        bg_alt = t['bg_table_alt']
        bg_hdr = t['accent_blue']
        border = t['border']
        accent = t['accent_blue']

        sym = SYM_MAP.get(offer.currency or "EUR", "€")
        company = _esc(offer.company_name or "—")
        contact = _esc(offer.contact_person or "—")
        address = _esc(offer.customer_address or "—")
        date_str = to_display_date(
            offer.date, datetime.date.today().strftime("%d.%m.%Y"))
        validity = _esc(offer.validity or "Belirtilmemiş")
        note = _esc(offer.validity_note or "")
        payment = _esc(offer.payment_term or "Belirtilmemiş")
        total = offer.total_amount or 0.0
        subtotal = sum((item.quantity or 0) * (item.unit_price or 0) for item in offer.items)
        discount = float(offer.discount_amount or 0)

        rows_html = ""
        for r, item in enumerate(offer.items):
            code = _esc(item.product_code or "")
            name = _esc(item.product_name or "")
            desc = _esc(item.description or "")
            qty = item.quantity or 0.0
            price = item.unit_price or 0.0
            unit = _esc(item.unit or "")
            delv = _esc(item.delivery_time or "")
            row_bg = bg_alt if r % 2 == 0 else bg
            rows_html += (
                f"<tr style='background:{row_bg};'>"
                f"<td style='padding:3px 6px;font-size:8pt;color:{fg_m};'>{r+1}</td>"
                f"<td style='padding:3px 6px;color:{fg};'><b>{code}</b></td>"
                f"<td style='padding:3px 6px;color:{fg};'>{name}"
                f"{'<br><span style=\"color:'+fg_m+';font-size:8pt;\">'+desc+'</span>' if desc else ''}</td>"
                f"<td style='padding:3px 6px;text-align:right;color:{fg};'>{qty:g} {unit}</td>"
                f"<td style='padding:3px 6px;text-align:right;color:{fg};'>{fmt_money(price, sym)}</td>"
                f"<td style='padding:3px 6px;text-align:right;font-weight:bold;color:{fg};'>{fmt_money(qty*price, sym)}</td>"
                f"<td style='padding:3px 6px;font-size:8pt;color:{fg_m};text-align:center;'>{delv}</td>"
                f"</tr>"
            )

        validity_bg = "#3d2800" if t['name'] == 'dark' else "#fff8e8"
        validity_fg = "#fbbf24" if t['name'] == 'dark' else "#c05500"
        payment_bg = "#0a1e3d" if t['name'] == 'dark' else "#f0f8ff"
        payment_fg = "#5a9bf5" if t['name'] == 'dark' else "#0055aa"

        # Not, geçerliliğin yanına sıkıştırılmaz — kendi satırında kalın gösterilir
        note_row = ""
        if note:
            note_row = (
                f"<tr style='background:{validity_bg};'>"
                f"<td colspan='2' style='padding:4px 6px;color:{fg};'><b>Not:</b></td>"
                f"<td colspan='5' style='padding:4px 6px;color:{validity_fg};"
                f"font-weight:bold;'>{note}</td>"
                f"</tr>"
            )
        validity_row = (
            f"<tr style='background:{validity_bg};'>"
            f"<td colspan='2' style='padding:4px 6px;color:{fg};'><b>Teklif Geçerliliği:</b></td>"
            f"<td colspan='3' style='padding:4px 6px;color:{validity_fg};font-weight:bold;'>{validity}</td>"
            f"<td colspan='2'></td></tr>"
            f"{note_row}"
            f"<tr style='background:{payment_bg};'>"
            f"<td colspan='2' style='padding:4px 6px;color:{fg};'><b>Ödeme Vadesi:</b></td>"
            f"<td colspan='5' style='padding:4px 6px;color:{payment_fg};font-weight:bold;'>{payment}</td>"
            f"</tr>"
        )

        discount_rows = ""
        if discount > 0:
            if offer.discount_type == "percent":
                discount_label = f"İskonto (%{offer.discount_value:g})"
            else:
                discount_label = "İskonto"
            disc_fg = "#f87171" if t['name'] == 'dark' else "#b00020"
            discount_rows = (
                f"<tr style='background:{bg_alt};'>"
                f"<td colspan='5' style='padding:4px 6px;text-align:right;color:{fg};'>Ara Toplam:</td>"
                f"<td colspan='2' style='padding:4px 6px;text-align:right;color:{fg};'>{fmt_money(subtotal, sym)}</td>"
                "</tr>"
                f"<tr style='background:{bg_alt};color:{disc_fg};'>"
                f"<td colspan='5' style='padding:4px 6px;text-align:right;'>{discount_label}:</td>"
                f"<td colspan='2' style='padding:4px 6px;text-align:right;'>-{fmt_money(discount, sym)}</td>"
                "</tr>"
            )

        total_bg = "#0a1e3d" if t['name'] == 'dark' else "#e8f0fe"
        total_fg = accent

        html = f"""
        <b style='font-size:10pt;color:{fg};'>Teklif Özeti</b><br><br>
        <table width='100%' style='margin-bottom:6px;color:{fg};'>
        <tr><td width='110'><b>Teklif No:</b></td><td>{offer.offer_no}</td>
            <td width='60'><b>Tarih:</b></td><td>{date_str}</td></tr>
        <tr><td><b>Firma:</b></td><td><b>{company}</b></td>
            <td><b>İlgili:</b></td><td>{contact}</td></tr>
        <tr><td><b>Adres:</b></td><td>{address}</td>
            <td><b>E-posta:</b></td><td>{_esc(offer.customer_email or '—')}</td></tr>
        <tr><td><b>Telefon:</b></td><td colspan='3'>{_esc(offer.customer_phone or '—')}</td></tr>
        </table>
        <hr style='margin:8px 0;border-color:{border};'>
        <table width='100%' cellspacing='0'>
        <tr style='background:{bg_hdr};color:white;'>
            <th style='padding:4px 6px;text-align:center;width:24px;'>#</th>
            <th style='padding:4px 6px;text-align:left;'>Kod</th>
            <th style='padding:4px 6px;text-align:left;'>Ürün</th>
            <th style='padding:4px 6px;text-align:right;'>Miktar</th>
            <th style='padding:4px 6px;text-align:right;'>Birim Fiyat</th>
            <th style='padding:4px 6px;text-align:right;'>Toplam</th>
            <th style='padding:4px 6px;text-align:center;'>Teslim</th>
        </tr>
        {rows_html}
        {discount_rows}
        <tr style='background:{total_bg};'>
            <td colspan='5' style='padding:5px 6px;text-align:right;font-weight:bold;color:{fg};'>
            Genel Toplam:</td>
            <td colspan='2' style='padding:5px 6px;text-align:right;font-size:11pt;
            font-weight:bold;color:{total_fg};'>{fmt_money(total, sym)}</td>
        </tr>
        {validity_row}
        </table>
        """
        return html
