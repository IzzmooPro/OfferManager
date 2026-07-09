"""Config modülü birim testleri.

ÖNEMLİ: Testler gerçek kullanıcı config dosyasına (AppData) ASLA dokunmaz.
CFG_PATH her testte geçici bir dosyaya yönlendirilir — böylece testler
pytest dışında doğrudan da çalıştırılsa kullanıcı ayarları bozulmaz.
(Geçmişte doğrudan çalıştırma gerçek company.cfg'yi test verisiyle ezmişti.)
"""
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

import core.config as config_mod
from core.config import load_company_config, save_company_config, _DEFAULTS


class TestConfig(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="oms_cfg_test_")
        self.cfg = Path(self._tmp.name) / "company.cfg"
        self._patcher = patch.object(config_mod, "CFG_PATH", self.cfg)
        self._patcher.start()

    def tearDown(self):
        self._patcher.stop()
        self._tmp.cleanup()

    # ── load ─────────────────────────────────────────────────────────────

    def test_load_returns_defaults_when_no_file(self):
        config = load_company_config()
        self.assertEqual(config["name"], _DEFAULTS["name"])
        self.assertEqual(config["offer_prefix"], _DEFAULTS["offer_prefix"])

    def test_load_merges_with_defaults(self):
        self.cfg.write_text("name=Özel Firma\n", encoding="utf-8")
        config = load_company_config()
        self.assertEqual(config["name"], "Özel Firma")
        self.assertEqual(config["offer_prefix"], _DEFAULTS["offer_prefix"])

    def test_load_handles_multiline_values(self):
        self.cfg.write_text("pdf_giris_metni=Satır 1\\nSatır 2\n", encoding="utf-8")
        config = load_company_config()
        self.assertIn("\n", config["pdf_giris_metni"])
        self.assertEqual(config["pdf_giris_metni"], "Satır 1\nSatır 2")

    def test_load_ignores_lines_without_equals(self):
        self.cfg.write_text("bu satırda eşittir yok\nname=Geçerli\n", encoding="utf-8")
        config = load_company_config()
        self.assertEqual(config["name"], "Geçerli")

    def test_load_handles_empty_file(self):
        self.cfg.write_text("", encoding="utf-8")
        config = load_company_config()
        self.assertEqual(config["name"], _DEFAULTS["name"])

    # ── save ─────────────────────────────────────────────────────────────

    def test_save_creates_file(self):
        save_company_config({"name": "Test Firma", "tel": "0555"})
        self.assertTrue(self.cfg.exists())

    def test_save_roundtrip(self):
        original = dict(_DEFAULTS)
        original["name"] = "Roundtrip Firma"
        original["pdf_giris_metni"] = "Birinci satır\nİkinci satır"
        save_company_config(original)
        loaded = load_company_config()
        self.assertEqual(loaded["name"], "Roundtrip Firma")
        self.assertEqual(loaded["pdf_giris_metni"], "Birinci satır\nİkinci satır")

    def test_save_is_atomic(self):
        save_company_config({"name": "Atomik"})
        tmp = self.cfg.with_suffix(".cfg.tmp")
        self.assertFalse(tmp.exists())

    def test_save_overwrites_previous(self):
        save_company_config({"name": "Birinci"})
        save_company_config({"name": "İkinci"})
        loaded = load_company_config()
        self.assertEqual(loaded["name"], "İkinci")

    def test_isolation_does_not_touch_real_config(self):
        """Testin kendisi gerçek CFG_PATH'i değil geçici dosyayı kullanmalı."""
        save_company_config({"name": "İzolasyon Testi"})
        self.assertTrue(str(self.cfg).startswith(tempfile.gettempdir()))


if __name__ == "__main__":
    unittest.main(verbosity=2)
