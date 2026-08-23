"""PDF log mesajlarının dar Windows konsol kodlamalarıyla uyumluluğu."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from models.offer import Offer
from pdf import pdf_generator


class PdfConsoleLoggingTests(unittest.TestCase):

    def test_generate_pdf_logs_are_cp1254_encodable(self):
        """Konsola bağlı frozen EXE log yazarken UnicodeEncodeError üretmemeli."""
        offer = Offer(
            offer_no="SNS-000001",
            validity="10 gün",
            payment_term="30 gün",
            currency="EUR",
        )

        def dar_konsola_yaz(sablon, *args):
            (sablon % args).encode("cp1254", errors="strict")

        def sahte_pdf(_offer, _company, _sym, output_path, compact=False):
            Path(output_path).write_bytes(b"PDF")
            return {"pages": 1}

        with tempfile.TemporaryDirectory() as tmp:
            hedef = str(Path(tmp) / "teklif.pdf")
            with mock.patch.object(pdf_generator, "_load_fonts"), \
                    mock.patch.object(pdf_generator, "_load_company",
                                      return_value={}), \
                    mock.patch.object(pdf_generator, "_build_pdf_document",
                                      side_effect=sahte_pdf), \
                    mock.patch.object(pdf_generator.logger, "info",
                                      side_effect=dar_konsola_yaz):
                self.assertEqual(pdf_generator.generate_pdf(offer, hedef), hedef)

            self.assertEqual(Path(hedef).read_bytes(), b"PDF")


if __name__ == "__main__":
    unittest.main()
