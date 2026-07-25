"""SMTP taşıma güvenliği regresyon testleri.

STARTTLS (port 587) yolunda `smtp.starttls()` context'siz çağrılıyordu;
Python bu durumda `ssl._create_stdlib_context()` kullanır — sertifika
doğrulaması KAPALIDIR (check_hostname=False, verify_mode=CERT_NONE).
Araya giren biri SMTP oturumunu çözüp kullanıcı adı + uygulama şifresini
ve gönderilen teklif PDF'ini okuyabiliyordu.
"""
import smtplib
import ssl
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from ui.dialogs.email_dialog import EmailWorker
from ui.settings_page import SmtpTestWorker


class _FakeSMTP:
    """starttls'e verilen TLS context'ini kaydeden sahte SMTP sunucusu."""

    last = None

    def __init__(self, host, port, timeout=None):
        self.host = host
        self.port = port
        self.tls_context = None
        self.starttls_called = False
        _FakeSMTP.last = self

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def ehlo(self, *args):
        return (250, b"ok")

    def starttls(self, *, context=None):
        self.starttls_called = True
        self.tls_context = context
        return (220, b"ready")

    def login(self, user, password):
        return (235, b"ok")

    def send_message(self, message):
        return {}


class _Recorder:
    """Signal yerine geçen basit kayıt nesnesi (QThread örneği gerektirmez)."""

    def __init__(self):
        self.calls = []

    def emit(self, *args):
        self.calls.append(args)


_CFG_587 = {
    "smtp_server": "smtp.example.com",
    "smtp_port": "587",
    "smtp_user": "user@example.com",
    "smtp_password": "gizli-sifre",
}


class StartTlsCertificateVerificationTests(unittest.TestCase):

    def _assert_verified(self, context, where: str):
        self.assertIsNotNone(
            context, f"{where}: starttls sertifika doğrulaması olmadan çağrıldı")
        self.assertTrue(context.check_hostname,
                        f"{where}: sunucu adı doğrulanmıyor")
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED,
                         f"{where}: sertifika zinciri doğrulanmıyor")

    def test_email_worker_starttls_verifies_certificate(self):
        with tempfile.TemporaryDirectory(prefix="oms_smtp_") as temp_dir:
            pdf_path = Path(temp_dir) / "TEKLIF.pdf"
            pdf_path.write_bytes(b"%PDF-1.4 test")
            worker = SimpleNamespace(
                cfg=dict(_CFG_587),
                to_addr="musteri@example.com",
                subject="Teklif",
                body="Merhaba",
                pdf_path=str(pdf_path),
                send_finished=_Recorder(),
            )
            with mock.patch.object(smtplib, "SMTP", _FakeSMTP):
                EmailWorker.run(worker)

        self.assertEqual(worker.send_finished.calls, [(True, "")],
                         "Gönderim sahte sunucuda başarısız oldu")
        self.assertTrue(_FakeSMTP.last.starttls_called)
        self._assert_verified(_FakeSMTP.last.tls_context, "EmailWorker")

    def test_smtp_test_worker_starttls_verifies_certificate(self):
        worker = SimpleNamespace(cfg=dict(_CFG_587), result=_Recorder())
        with mock.patch.object(smtplib, "SMTP", _FakeSMTP):
            SmtpTestWorker.run(worker)

        self.assertTrue(worker.result.calls and worker.result.calls[0][0],
                        f"Test bağlantısı başarısız: {worker.result.calls}")
        self.assertTrue(_FakeSMTP.last.starttls_called)
        self._assert_verified(_FakeSMTP.last.tls_context, "SmtpTestWorker")


if __name__ == "__main__":
    unittest.main(verbosity=2)
