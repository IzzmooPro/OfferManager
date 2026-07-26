"""O3 — Bozuk/okunamayan CSV "boş dosya" diye raporlanmamalı.

_read_file() CSV dalında dört kodlamayı deniyor ve her denemeyi
`except Exception: continue` ile yutuyordu. Tüm denemeler başarısız olunca
(rows=[], err="") dönüyor, çağıran da "Dosyada veri bulunamadı." diyordu —
kullanıcı gerçek nedeni asla göremiyordu. Ayrıca csv.Sniffer ayıracı
belirleyemediğinde okunabilir dosyalar da reddediliyordu.

Bu testler GERÇEKTEN boş dosya ile OKUNAMAYAN dosyayı ayırır.
"""
import csv
import io
import logging
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ui.utils import excel_import
from ui.utils.excel_import import _read_file


class CsvReadErrorTests(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="oms_o3_")
        self.addCleanup(self._tmp.cleanup)

    def _yaz(self, ad: str, icerik, encoding="utf-8") -> str:
        yol = Path(self._tmp.name) / ad
        if isinstance(icerik, bytes):
            yol.write_bytes(icerik)
        else:
            yol.write_text(icerik, encoding=encoding)
        return str(yol)

    # ── Gerçekten boş dosya ile okunamayan dosya ayrılmalı ───────────────

    def test_truly_empty_csv_reports_no_data_without_error(self):
        rows, err = _read_file(self._yaz("bos.csv", ""))
        self.assertEqual(rows, [])
        self.assertEqual(err, "", "boş dosya için hata mesajı üretilmemeli")

    def test_whitespace_only_csv_is_treated_as_empty(self):
        rows, err = _read_file(self._yaz("bosluk.csv", "\n\n   \n"))
        self.assertEqual(rows, [])
        self.assertEqual(err, "")

    def test_binary_content_reports_read_error_not_empty_file(self):
        # PNG başlığı: NUL baytları içerir, metin değildir
        ikili = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x01\x00" + bytes(range(256))
        rows, err = _read_file(self._yaz("resim.csv", ikili))
        self.assertEqual(rows, [], "ikili içerikten satır üretilmemeli")
        self.assertTrue(err, "bozuk dosya sessizce 'boş dosya' sayıldı")

    def test_last_meaningful_error_is_preserved(self):
        # Tüm kodlama denemeleri ayrıştırmada başarısız olsun
        yol = self._yaz("bozuk.csv", "a,b\n1,2\n")
        with mock.patch.object(excel_import.csv, "DictReader",
                               side_effect=csv.Error("alan sınırı aşıldı")):
            with self.assertLogs("excel_import", level="WARNING"):
                rows, err = _read_file(yol)
        self.assertEqual(rows, [])
        self.assertTrue(err, "son anlamlı hata kaybedildi (err boş döndü)")

    def test_sniffer_failure_is_logged_not_swallowed(self):
        # Tek sütunlu dosyada csv.Sniffer ayıracı belirleyemez
        yol = self._yaz("tek_sutun.csv", "Firma Adı\nAlfa Ltd.\nBeta A.Ş.\n")
        with self.assertLogs("excel_import", level="INFO") as kayit:
            rows, err = _read_file(yol)
        self.assertEqual(err, "")
        self.assertTrue(any("ayıraç" in m.lower() or "ayirac" in m.lower()
                            for m in kayit.output),
                        f"ayıraç sorunu loglanmadı: {kayit.output}")

    # ── Okunabilir dosyalar çalışmaya devam etmeli ───────────────────────

    def test_comma_csv_parses(self):
        yol = self._yaz("virgul.csv", "Firma Adı,E-posta\nAlfa,a@b.com\n")
        rows, err = _read_file(yol)
        self.assertEqual(err, "")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["Firma Adı"], "Alfa")
        self.assertEqual(rows[0]["E-posta"], "a@b.com")

    def test_semicolon_turkish_csv_parses(self):
        yol = self._yaz(
            "noktali.csv",
            "Firma Adı;İlgili Kişi;Şehir\nÖzçelik Ltd.;Ayşe Gül;İstanbul\n")
        rows, err = _read_file(yol)
        self.assertEqual(err, "")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["Firma Adı"], "Özçelik Ltd.")
        self.assertEqual(rows[0]["İlgili Kişi"], "Ayşe Gül")
        self.assertEqual(rows[0]["Şehir"], "İstanbul")

    def test_utf8_bom_csv_parses_without_bom_in_header(self):
        yol = self._yaz("bom.csv", "Firma Adı;E-posta\nAlfa;a@b.com\n",
                        encoding="utf-8-sig")
        rows, err = _read_file(yol)
        self.assertEqual(err, "")
        self.assertEqual(len(rows), 1)
        self.assertIn("Firma Adı", rows[0],
                      f"BOM başlığa karıştı: {list(rows[0])}")

    def test_single_column_csv_parses_with_fallback(self):
        yol = self._yaz("tek_sutun.csv", "Firma Adı\nAlfa Ltd.\nBeta A.Ş.\n")
        rows, err = _read_file(yol)
        self.assertEqual(err, "", "okunabilir tek sütunlu dosya reddedildi")
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["Firma Adı"], "Alfa Ltd.")

    # ── Kullanıcıya gösterilen mesaj ─────────────────────────────────────

    def test_error_message_is_short_and_not_a_traceback(self):
        ikili = b"\x00\x01\x02\x03" * 512
        _, err = _read_file(self._yaz("ikili.csv", ikili))
        self.assertTrue(err)
        self.assertLess(len(err), 240, f"mesaj çok uzun: {err!r}")
        for teknik in ("Traceback", "UnicodeDecodeError", "Exception",
                       "0x", "line "):
            self.assertNotIn(teknik, err,
                             f"kullanıcı mesajında teknik ayrıntı var: {err!r}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
