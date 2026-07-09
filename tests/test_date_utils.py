"""Date utils birim testleri."""
import unittest
from datetime import date, datetime

from core.date_utils import parse_date, to_storage_date, to_display_date


class TestDateUtils(unittest.TestCase):

    # ── parse_date ───────────────────────────────────────────────────────

    def test_parse_iso_format(self):
        result = parse_date("2026-06-26")
        self.assertEqual(result, date(2026, 6, 26))

    def test_parse_display_format(self):
        result = parse_date("26.06.2026")
        self.assertEqual(result, date(2026, 6, 26))

    def test_parse_empty_string(self):
        self.assertIsNone(parse_date(""))

    def test_parse_none(self):
        self.assertIsNone(parse_date(None))

    def test_parse_invalid_format(self):
        self.assertIsNone(parse_date("invalid"))
        self.assertIsNone(parse_date("2026/06/26"))

    def test_parse_strips_whitespace(self):
        result = parse_date("  2026-06-26  ")
        self.assertEqual(result, date(2026, 6, 26))

    # ── to_storage_date ──────────────────────────────────────────────────

    def test_storage_from_display_format(self):
        self.assertEqual(to_storage_date("26.06.2026"), "2026-06-26")

    def test_storage_from_iso_format(self):
        self.assertEqual(to_storage_date("2026-06-26"), "2026-06-26")

    def test_storage_from_date_object(self):
        self.assertEqual(to_storage_date(date(2026, 6, 26)), "2026-06-26")

    def test_storage_from_datetime_object(self):
        dt = datetime(2026, 6, 26, 14, 30)
        self.assertEqual(to_storage_date(dt), "2026-06-26")

    def test_storage_empty_returns_empty(self):
        self.assertEqual(to_storage_date(""), "")

    def test_storage_none_returns_empty(self):
        self.assertEqual(to_storage_date(None), "")

    def test_storage_invalid_returns_as_is(self):
        self.assertEqual(to_storage_date("geçersiz"), "geçersiz")

    # ── to_display_date ──────────────────────────────────────────────────

    def test_display_from_iso_format(self):
        self.assertEqual(to_display_date("2026-06-26"), "26.06.2026")

    def test_display_from_display_format(self):
        self.assertEqual(to_display_date("26.06.2026"), "26.06.2026")

    def test_display_from_date_object(self):
        self.assertEqual(to_display_date(date(2026, 6, 26)), "26.06.2026")

    def test_display_empty_with_default(self):
        self.assertEqual(to_display_date("", default="N/A"), "N/A")

    def test_display_none_with_default(self):
        self.assertEqual(to_display_date(None, default="—"), "—")

    def test_display_invalid_returns_as_is(self):
        self.assertEqual(to_display_date("geçersiz"), "geçersiz")


if __name__ == "__main__":
    unittest.main(verbosity=2)
