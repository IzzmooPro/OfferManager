"""
E-Posta Gönderme Dialog Ekranı
Seçilen teklifi SMTP (Örn: Gmail/Outlook) üzerinden PDF ekli olarak müşteriye yollar.
"""
import smtplib, ssl, logging
from email.message import EmailMessage
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QTextEdit, QPushButton, QMessageBox, QFrame
)
from PySide6.QtCore import Qt, QThread, Signal
from core.config import load_company_config
from core.credential_store import get_smtp_password

logger = logging.getLogger("email_dialog")


class EmailWorker(QThread):
    finished = Signal(bool, str)

    def __init__(self, cfg: dict, to_addr: str, subject: str, body: str, pdf_path: str):
        super().__init__()
        self.cfg = cfg
        self.to_addr = to_addr
        self.subject = subject
        self.body = body
        self.pdf_path = pdf_path

    def run(self):
        try:
            msg = EmailMessage()
            msg["Subject"] = self.subject
            msg["From"] = self.cfg.get("smtp_user", "")
            msg["To"] = self.to_addr
            msg.set_content(self.body)

            # PDF Dosyasını Ekle
            pdf_path = Path(self.pdf_path)
            if pdf_path.exists():
                with open(pdf_path, 'rb') as f:
                    pdf_data = f.read()
                msg.add_attachment(pdf_data, maintype='application', subtype='pdf', filename=pdf_path.name)
            else:
                self.finished.emit(False, f"PDF dosyası bulunamadı: {pdf_path}")
                return

            server = self.cfg.get("smtp_server", "").strip()
            port_str = self.cfg.get("smtp_port", "465").strip()
            port = int(port_str) if port_str.isdigit() else 465
            user = self.cfg.get("smtp_user", "").strip()
            from core.credential_store import normalize_smtp_password
            password = normalize_smtp_password(self.cfg.get("smtp_password", ""))

            if port == 465:
                # SSL Bağlantısı (Genellikle 465)
                context = ssl.create_default_context()
                with smtplib.SMTP_SSL(server, port, context=context, timeout=15) as smtp:
                    smtp.login(user, password)
                    smtp.send_message(msg)
            else:
                # STARTTLS Bağlantısı (Genellikle 587)
                with smtplib.SMTP(server, port, timeout=15) as smtp:
                    smtp.starttls()
                    smtp.login(user, password)
                    smtp.send_message(msg)
                    
            self.finished.emit(True, "")
            
        except smtplib.SMTPAuthenticationError:
            self.finished.emit(False, "Kimlik doğrulama reddedildi (Şifre veya Kullanıcı adı yanlış). Gmail kullanıyorsanız 'Uygulama Şifresi' oluşturmayı unutmayın.")
        except TimeoutError:
            self.finished.emit(False, "Bağlantı zaman aşımına uğradı (15 sn). Sunucu adresi ve port numarasını kontrol edin.")
        except Exception as e:
            logger.error("E-posta gönderim hatası: %s", e, exc_info=True)
            self.finished.emit(False, str(e))


class EmailDialog(QDialog):
    def __init__(self, pdf_path: str, customer_email: str = "", offer_no: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Teklif Gönder")
        self.setMinimumSize(560, 480)
        self.resize(560, 520)
        self.pdf_path = pdf_path
        self.cfg = load_company_config()
        self.cfg["smtp_password"] = get_smtp_password()
        self._closing = False   # Worker tamamlanınca UI erişimini korur
        self.worker   = None

        self._build_ui(customer_email, offer_no)

    def _build_ui(self, customer_email, offer_no):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(12)
        
        # Bilgi Notu
        lbl_info = QLabel(f"Eklenecek PDF :  <b>{Path(self.pdf_path).name}</b>")
        lbl_info.setTextFormat(Qt.TextFormat.RichText)
        lay.addWidget(lbl_info)
        lay.addWidget(self._make_line())

        # Alıcı
        h1 = QHBoxLayout()
        lbl_to = QLabel("Alıcı:"); lbl_to.setFixedWidth(50)
        h1.addWidget(lbl_to)
        self.to_input = QLineEdit(customer_email)
        self.to_input.setPlaceholderText("Müşteri E-Posta Adresi (Örn: musteri@firma.com)")
        self.to_input.setMinimumHeight(32)
        h1.addWidget(self.to_input)
        lay.addLayout(h1)

        # Konu
        h2 = QHBoxLayout()
        lbl_sub = QLabel("Konu:"); lbl_sub.setFixedWidth(50)
        h2.addWidget(lbl_sub)
        
        company_name = self.cfg.get("name", "Şirketimiz").strip() or "Şirketimiz"
        default_subject = f"{company_name} - Teklif Dosyası ({offer_no})"
        self.subject_input = QLineEdit(default_subject)
        self.subject_input.setMinimumHeight(32)
        h2.addWidget(self.subject_input)
        lay.addLayout(h2)

        # Mesaj
        from ui.utils.theme_manager import get_theme
        _muted = get_theme()['text_muted']
        lbl_body = QLabel(f"Mesaj Metni:  <span style='color:{_muted};font-size:8pt;'>(düzenleyebilirsiniz)</span>")
        lbl_body.setTextFormat(Qt.TextFormat.RichText)
        lay.addWidget(lbl_body)
        self.body_input = QTextEdit()
        self.body_input.setMinimumHeight(160)
        default_body = f"Merhaba,\n\nTalep etmiş olduğunuz ürün/hizmetlere ait {offer_no} numaralı teklif dosyası ekte bilgilerinize sunulmuştur.\n\nİyi çalışmalar,\n{company_name}"
        self.body_input.setPlainText(default_body)
        lay.addWidget(self.body_input, 1)  # stretch=1 → kalan alanı doldurur

        # Butonlar
        h_btn = QHBoxLayout()
        self.btn_send = QPushButton("Gönder")
        self.btn_send.setObjectName("primary")
        self.btn_send.setFixedSize(140, 36)
        self.btn_send.clicked.connect(self._send_email)
        
        btn_cancel = QPushButton("İptal")
        btn_cancel.setFixedSize(100, 36)
        btn_cancel.clicked.connect(self.reject)
        
        h_btn.addStretch()
        h_btn.addWidget(btn_cancel)
        h_btn.addWidget(self.btn_send)
        lay.addLayout(h_btn)

    def _make_line(self) -> QFrame:
        f = QFrame()
        f.setFrameShape(QFrame.Shape.HLine)
        from ui.utils.theme_manager import get_theme
        f.setStyleSheet(f"background-color: {get_theme()['border']};")
        return f

    def closeEvent(self, event):
        """Dialog kapatılırken çalışan worker'ı güvenle durdur."""
        self._closing = True
        if self.worker and self.worker.isRunning():
            self.worker.finished.disconnect()   # Signal'i kopar — stale callback yok
            self.worker.quit()
            self.worker.wait(4000)              # En fazla 4 sn bekle
        event.accept()

    def _send_email(self):
        if not self.cfg.get("smtp_server") or not self.cfg.get("smtp_user") or not self.cfg.get("smtp_password"):
            QMessageBox.warning(self, "SMTP Ayarı Yok", 
                "E-posta gönderebilmek için uygulamanın sol menüsünden\n"
                "'Ayarlar -> E-Posta Ayarları' sekmesine giderek\n"
                "kendi e-posta adresinizi ve şifrenizi tanımlamanız gerekmektedir.")
            return

        to_addr = self.to_input.text().strip()
        if not to_addr:
            QMessageBox.warning(self, "Eksik Bilgi", "Lütfen alıcı e-posta adresini girin.")
            return

        self.btn_send.setEnabled(False)
        self.btn_send.setText("Gönderiliyor...")

        self.worker = EmailWorker(
            self.cfg, to_addr, 
            self.subject_input.text().strip(), 
            self.body_input.toPlainText(), 
            self.pdf_path
        )
        self.worker.finished.connect(self._on_finished)
        self.worker.start()

    def _on_finished(self, success: bool, error_msg: str):
        # Dialog kapatılmışsa C++ nesnelerine erişme
        if self._closing:
            return
        self.btn_send.setEnabled(True)
        self.btn_send.setText("Gönder")
        if success:
            to_addr = self.to_input.text().strip()
            QMessageBox.information(
                self, "Başarılı",
                f"E-Posta başarıyla gönderildi!\nAlıcı: {to_addr}")
            self.accept()
        else:
            QMessageBox.critical(self, "Gönderim Hatası", f"E-Posta gönderilemedi:\n\n{error_msg}")
