"""core.constants.normalize_currency birim testleri."""
import unittest

from core.constants import normalize_currency, CURRENCY_LIST


class TestNormalizeCurrency(unittest.TestCase):
    def test_try_maps_to_tl(self):
        # En kritik senaryo: dosyalar TL'yi "TRY" yazar, sistem "TL" bekler.
        self.assertEqual(normalize_currency("TRY"), "TL")
        self.assertEqual(normalize_currency("try"), "TL")
        self.assertEqual(normalize_currency(" Try "), "TL")

    def test_symbols(self):
        self.assertEqual(normalize_currency("₺"), "TL")
        self.assertEqual(normalize_currency("€"), "EUR")
        self.assertEqual(normalize_currency("$"), "USD")

    def test_valid_codes_pass_through(self):
        for c in CURRENCY_LIST:
            self.assertEqual(normalize_currency(c), c)
        self.assertEqual(normalize_currency("usd"), "USD")

    def test_word_aliases(self):
        self.assertEqual(normalize_currency("EURO"), "EUR")
        self.assertEqual(normalize_currency("DOLAR"), "USD")

    def test_unknown_and_empty_fall_to_default(self):
        self.assertEqual(normalize_currency("XYZ"), "EUR")
        self.assertEqual(normalize_currency(""), "EUR")
        self.assertEqual(normalize_currency(None), "EUR")
        self.assertEqual(normalize_currency("XYZ", default="TL"), "TL")


if __name__ == "__main__":
    unittest.main(verbosity=2)
