from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.services.backup_mail_settings_service import (
    BackupMailSettingsError,
    is_valid_email,
    load_backup_mail_settings,
    save_backup_mail_settings,
    send_backup_mail_test,
)


class BackupMailSettingsDialog(QDialog):
    def __init__(self, *, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.setWindowTitle("Yedekleme Maili Ayarları")
        self.resize(620, 360)
        self.setMinimumSize(560, 320)
        self.setSizeGripEnabled(True)

        self.setStyleSheet(
            """
            QDialog {
                background-color: #0f172a;
                color: #e5e7eb;
            }

            QLabel#DialogTitle {
                color: #ffffff;
                font-size: 20px;
                font-weight: 800;
            }

            QLabel#DialogSubtitle,
            QLabel#StatusLabel,
            QLabel#HelpLabel {
                color: #94a3b8;
                font-size: 12px;
            }

            QLineEdit {
                background-color: #111827;
                color: #e5e7eb;
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 8px 10px;
                min-height: 24px;
            }

            QLineEdit:focus {
                border: 1px solid #3b82f6;
            }

            QCheckBox {
                color: #e5e7eb;
                font-size: 13px;
                spacing: 8px;
            }

            QPushButton {
                background-color: #2563eb;
                color: #ffffff;
                border: 1px solid #3b82f6;
                border-radius: 9px;
                padding: 8px 14px;
                font-weight: 700;
                min-height: 26px;
            }

            QPushButton:hover {
                background-color: #1d4ed8;
            }

            QPushButton#SecondaryButton {
                background-color: #172033;
                color: #cbd5e1;
                border: 1px solid #24324a;
            }

            QPushButton#SecondaryButton:hover {
                background-color: #1e293b;
                color: #ffffff;
            }

            QPushButton:disabled {
                background-color: #111827;
                color: #64748b;
                border: 1px solid #1e293b;
            }
            """
        )

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 22, 24, 22)
        main_layout.setSpacing(14)

        title_label = QLabel("Yedekleme Maili")
        title_label.setObjectName("DialogTitle")

        subtitle_label = QLabel(
            "Yedek dosyalarının hangi müşteri mail adresine gönderileceğini belirler. "
            "Gönderici FTM merkezi mail hesabıdır; müşteri SMTP bilgisi görmez."
        )
        subtitle_label.setObjectName("DialogSubtitle")
        subtitle_label.setWordWrap(True)

        self.enabled_checkbox = QCheckBox("Yedekleri mail olarak gönder")
        self.enabled_checkbox.stateChanged.connect(self._update_controls_state)

        recipient_label = QLabel("Alıcı mail adresi")
        recipient_label.setObjectName("HelpLabel")

        self.recipient_input = QLineEdit()
        self.recipient_input.setPlaceholderText("ornek@firma.com")
        self.recipient_input.textChanged.connect(self._update_controls_state)

        self.status_label = QLabel("")
        self.status_label.setObjectName("StatusLabel")
        self.status_label.setWordWrap(True)

        help_label = QLabel(
            "Not: Bu ekrandaki mail adresi sadece yedek alıcısıdır. "
            "Merkezi gönderici mail şifresi bu ekranda gösterilmez."
        )
        help_label.setObjectName("HelpLabel")
        help_label.setWordWrap(True)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)

        self.test_button = QPushButton("Test Mail Gönder")
        self.test_button.setObjectName("SecondaryButton")
        self.test_button.clicked.connect(self._send_test_mail)

        self.save_button = QPushButton("Kaydet")
        self.save_button.clicked.connect(self._save_settings)

        self.cancel_button = QPushButton("Vazgeç")
        self.cancel_button.setObjectName("SecondaryButton")
        self.cancel_button.clicked.connect(self.reject)

        button_layout.addWidget(self.test_button)
        button_layout.addStretch(1)
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.save_button)

        main_layout.addWidget(title_label)
        main_layout.addWidget(subtitle_label)
        main_layout.addSpacing(4)
        main_layout.addWidget(self.enabled_checkbox)
        main_layout.addWidget(recipient_label)
        main_layout.addWidget(self.recipient_input)
        main_layout.addWidget(self.status_label)
        main_layout.addWidget(help_label)
        main_layout.addStretch(1)
        main_layout.addLayout(button_layout)

        self._load_settings_to_form()
        self._update_controls_state()

    def _load_settings_to_form(self) -> None:
        try:
            settings = load_backup_mail_settings()

        except Exception as exc:
            self.status_label.setText(f"Ayarlar okunamadı: {exc}")
            return

        self.enabled_checkbox.setChecked(settings.enabled)
        self.recipient_input.setText(settings.recipient_email)

        if settings.last_test_at or settings.last_test_status or settings.last_test_message:
            self.status_label.setText(
                "Son test: "
                f"{settings.last_test_status or '-'} | "
                f"{settings.last_test_at or '-'} | "
                f"{settings.last_test_message or '-'}"
            )
        else:
            self.status_label.setText("Henüz test maili gönderilmedi.")

    def _recipient_email(self) -> str:
        return self.recipient_input.text().strip().lower()

    def _update_controls_state(self) -> None:
        enabled = self.enabled_checkbox.isChecked()
        recipient_email = self._recipient_email()

        self.recipient_input.setEnabled(enabled)
        self.test_button.setEnabled(enabled and bool(recipient_email))
        self.save_button.setEnabled(True)

        if enabled and recipient_email and not is_valid_email(recipient_email):
            self.status_label.setText("Alıcı mail adresi geçerli formatta değil.")

    def _save_settings(self) -> None:
        try:
            saved_settings = save_backup_mail_settings(
                enabled=self.enabled_checkbox.isChecked(),
                recipient_email=self._recipient_email(),
            )

        except BackupMailSettingsError as exc:
            QMessageBox.warning(self, "Eksik veya hatalı bilgi", str(exc))
            return

        except Exception as exc:
            QMessageBox.warning(self, "Ayar kaydetme hatası", str(exc))
            return

        QMessageBox.information(
            self,
            "Ayar kaydedildi",
            "Yedekleme maili ayarı kaydedildi.",
        )

        self.enabled_checkbox.setChecked(saved_settings.enabled)
        self.recipient_input.setText(saved_settings.recipient_email)
        self._load_settings_to_form()
        self._update_controls_state()

    def _send_test_mail(self) -> None:
        recipient_email = self._recipient_email()

        if not recipient_email:
            QMessageBox.warning(
                self,
                "Eksik bilgi",
                "Test maili göndermek için alıcı mail adresi girilmelidir.",
            )
            return

        if not is_valid_email(recipient_email):
            QMessageBox.warning(
                self,
                "Hatalı mail adresi",
                "Geçerli bir alıcı mail adresi girilmelidir.",
            )
            return

        try:
            save_backup_mail_settings(
                enabled=self.enabled_checkbox.isChecked(),
                recipient_email=recipient_email,
            )

        except Exception as exc:
            QMessageBox.warning(self, "Ayar kaydetme hatası", str(exc))
            return

        self.test_button.setEnabled(False)
        self.test_button.setText("Gönderiliyor...")
        self.status_label.setText("Test maili gönderiliyor...")
        self.repaint()

        result = send_backup_mail_test(recipient_email=recipient_email)

        self.test_button.setText("Test Mail Gönder")
        self._update_controls_state()

        if result.success:
            QMessageBox.information(
                self,
                "Test maili başarılı",
                result.message,
            )
        else:
            QMessageBox.warning(
                self,
                "Test maili gönderilemedi",
                result.message,
            )

        self._load_settings_to_form()
        self._update_controls_state()
