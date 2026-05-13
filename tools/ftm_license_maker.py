from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


MAKER_VERSION = "2.3.2"

ENCRYPTED_PRIVATE_KEY_FILE_NAME = "ftm_license_ed25519_private_encrypted.pem"
LEGACY_PLAIN_PRIVATE_KEY_FILE_NAME = "ftm_license_ed25519_private.pem"

LICENSE_ADMIN_FOLDER = Path(
    os.environ.get(
        "FTM_LICENSE_ADMIN_FOLDER",
        r"C:\FTM_LICENSE_ADMIN",
    )
)

LICENSE_ADMIN_KEYS_FOLDER = LICENSE_ADMIN_FOLDER / "keys"
LICENSE_ADMIN_OUTPUT_FOLDER = LICENSE_ADMIN_FOLDER / "output"
LICENSE_ADMIN_LOGS_FOLDER = LICENSE_ADMIN_FOLDER / "logs"

DEFAULT_ENCRYPTED_PRIVATE_KEY_FILE = Path(
    os.environ.get(
        "FTM_LICENSE_ENCRYPTED_PRIVATE_KEY_FILE",
        str(LICENSE_ADMIN_KEYS_FOLDER / ENCRYPTED_PRIVATE_KEY_FILE_NAME),
    )
)

DEFAULT_OUTPUT_FOLDER = Path(
    os.environ.get(
        "FTM_LICENSE_OUTPUT_FOLDER",
        str(LICENSE_ADMIN_OUTPUT_FOLDER),
    )
)

DEFAULT_LICENSE_GENERATION_LOG_FILE = Path(
    os.environ.get(
        "FTM_LICENSE_GENERATION_LOG_FILE",
        str(LICENSE_ADMIN_LOGS_FOLDER / "license_generation_log.jsonl"),
    )
)

SIGNED_LICENSE_VERSION = 2
SIGNED_LICENSE_ALGORITHM = "Ed25519"
LICENSE_DATE_FORMAT = "%Y-%m-%d"


APP_STYLE = """
QWidget {
    background-color: #0f172a;
    color: #e5e7eb;
    font-size: 12px;
}

QScrollArea {
    background-color: #0f172a;
    border: none;
}

QFrame#Shell {
    background-color: #0f172a;
    border: none;
}

QFrame#HeaderCard {
    background-color: #111827;
    border: 1px solid #263449;
    border-radius: 16px;
}

QFrame#MainCard {
    background-color: #111827;
    border: 1px solid #263449;
    border-radius: 18px;
}

QFrame#InnerCard {
    background-color: #0b1220;
    border: 1px solid #24324a;
    border-radius: 15px;
}

QFrame#SectionHeader {
    background-color: #0f1b31;
    border: none;
    border-radius: 9px;
}

QLabel#Title {
    color: #f8fafc;
    font-size: 25px;
    font-weight: 900;
}

QLabel#Subtitle {
    color: #b6c7df;
    font-size: 12px;
}

QLabel#SectionTitle {
    color: #dbeafe;
    font-size: 15px;
    font-weight: 900;
}

QLabel#FieldLabel {
    color: #e5e7eb;
    font-size: 12px;
    font-weight: 800;
}

QLabel#MutedText {
    color: #aab8cc;
    font-size: 12px;
}

QLabel#WarningText {
    color: #fde68a;
    font-size: 12px;
    font-weight: 800;
}

QLabel#SuccessText {
    color: #bbf7d0;
    font-size: 12px;
    font-weight: 800;
}

QLabel#StatusBox {
    background-color: #0f1b31;
    color: #bbf7d0;
    border: 1px solid #24324a;
    border-radius: 10px;
    padding: 9px 10px;
    font-size: 12px;
    font-weight: 800;
}

QLabel#WarningBox {
    background-color: #2a1f0a;
    color: #fde68a;
    border: 1px solid #8a6d1d;
    border-radius: 10px;
    padding: 9px 10px;
    font-size: 12px;
    font-weight: 800;
}

QLineEdit,
QTextEdit,
QComboBox,
QDateEdit,
QSpinBox {
    background-color: #111827;
    color: #f8fafc;
    border: 1px solid #334155;
    border-radius: 9px;
    padding: 7px 10px;
    selection-background-color: #2563eb;
    selection-color: #ffffff;
    min-height: 32px;
}

QLineEdit:focus,
QTextEdit:focus,
QComboBox:focus,
QDateEdit:focus,
QSpinBox:focus {
    border: 1px solid #38bdf8;
}

QLineEdit[readOnly="true"] {
    background-color: #0f172a;
    color: #dbeafe;
    border: 1px solid #475569;
}

QLineEdit#PasswordInput {
    background-color: #111827;
    color: #f8fafc;
    border: 1px solid #38bdf8;
}

QLineEdit#PathInput {
    font-family: Consolas, "Courier New", monospace;
    font-size: 11px;
}

QLineEdit#FingerprintInput {
    font-family: Consolas, "Courier New", monospace;
    font-size: 11px;
}

QTextEdit {
    min-height: 86px;
}

QPushButton {
    background-color: #1e293b;
    color: #f8fafc;
    border: 1px solid #334155;
    border-radius: 10px;
    padding: 8px 15px;
    font-weight: 900;
    min-height: 36px;
}

QPushButton:hover {
    background-color: #334155;
}

QPushButton#Primary {
    background-color: #047857;
    border: 1px solid #10b981;
    color: #ffffff;
}

QPushButton#Primary:hover {
    background-color: #059669;
}

QPushButton#Danger {
    background-color: #7f1d1d;
    border: 1px solid #f87171;
    color: #ffffff;
}

QPushButton#Danger:hover {
    background-color: #991b1b;
}

QCheckBox {
    color: #dbeafe;
    font-size: 12px;
    font-weight: 800;
    spacing: 7px;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
}
"""


class LicenseMakerError(ValueError):
    pass


class FTMLicenseMakerWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("FTM Licence Maker")
        self.resize(1320, 780)
        self.setMinimumSize(1180, 720)
        self.setStyleSheet(APP_STYLE)

        self.private_key_path_input = QLineEdit("")
        self.private_key_path_input.setObjectName("PathInput")
        self.private_key_path_input.setReadOnly(True)

        self.private_key_password_input = QLineEdit("")
        self.private_key_password_input.setObjectName("PasswordInput")
        self.private_key_password_input.setEchoMode(QLineEdit.Password)
        self.private_key_password_input.setPlaceholderText(
            "Encrypted private key parolası"
        )
        self.private_key_password_input.setClearButtonEnabled(True)

        self.show_password_checkbox = QCheckBox("Parolayı göster")
        self.show_password_checkbox.stateChanged.connect(self._toggle_password_visibility)

        self.private_key_status_label = QLabel("")
        self.private_key_status_label.setObjectName("StatusBox")
        self.private_key_status_label.setWordWrap(True)

        self.legacy_key_warning_label = QLabel("")
        self.legacy_key_warning_label.setObjectName("WarningBox")
        self.legacy_key_warning_label.setWordWrap(True)
        self.legacy_key_warning_label.setVisible(False)

        self.public_fingerprint_input = QLineEdit("")
        self.public_fingerprint_input.setObjectName("FingerprintInput")
        self.public_fingerprint_input.setReadOnly(True)
        self.public_fingerprint_input.setPlaceholderText(
            "Private key doğrulandıktan sonra fingerprint burada gösterilir"
        )

        self.company_name_input = QLineEdit()
        self.company_name_input.setPlaceholderText("Örnek: ABC Market")

        self.device_code_input = QLineEdit()
        self.device_code_input.setPlaceholderText("FTM-XXXX-XXXX-XXXX-XXXX-XXXX")

        self.license_type_combo = QComboBox()
        self.license_type_combo.addItem("Yıllık Lisans", "annual")
        self.license_type_combo.addItem("30 Gün Demo", "demo_30_days")
        self.license_type_combo.addItem("7 Gün Test", "test_7_days")
        self.license_type_combo.addItem("Özel / Manuel", "custom")
        self.license_type_combo.currentIndexChanged.connect(self._sync_license_type_inputs)

        self.custom_license_type_input = QLineEdit()
        self.custom_license_type_input.setPlaceholderText("Örnek: annual_test")
        self.custom_license_type_input.setText("annual_test")

        self.days_input = QSpinBox()
        self.days_input.setMinimum(1)
        self.days_input.setMaximum(3650)
        self.days_input.setValue(365)

        self.starts_at_input = QDateEdit()
        self.starts_at_input.setCalendarPopup(True)
        self.starts_at_input.setDisplayFormat("yyyy-MM-dd")
        self.starts_at_input.setDate(QDate.currentDate())

        self.notes_input = QTextEdit()
        self.notes_input.setPlaceholderText("Lisans notu")

        self.output_folder_input = QLineEdit(str(DEFAULT_OUTPUT_FOLDER))
        self.output_folder_input.setObjectName("PathInput")
        self.output_folder_input.setReadOnly(True)

        self.output_file_input = QLineEdit("")
        self.output_file_input.setObjectName("PathInput")
        self.output_file_input.setReadOnly(True)

        self.log_file_input = QLineEdit(str(DEFAULT_LICENSE_GENERATION_LOG_FILE))
        self.log_file_input.setObjectName("PathInput")
        self.log_file_input.setReadOnly(True)

        self.select_output_folder_button = QPushButton("Klasör Seç")
        self.select_output_folder_button.clicked.connect(self._select_output_folder)

        self.verify_key_button = QPushButton("Private Key Doğrula")
        self.verify_key_button.clicked.connect(self._verify_private_key_from_ui)

        self.generate_button = QPushButton("İmzalı Lisans Oluştur")
        self.generate_button.setObjectName("Primary")
        self.generate_button.setMinimumWidth(180)
        self.generate_button.clicked.connect(self._generate_license)

        self.clear_button = QPushButton("Formu Temizle")
        self.clear_button.setObjectName("Danger")
        self.clear_button.setMinimumWidth(140)
        self.clear_button.clicked.connect(self._clear_form)

        self._build_ui()
        self._load_private_key_status()
        self._sync_license_type_inputs()

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(14, 12, 14, 12)
        root_layout.setSpacing(0)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(4, 4, 4, 4)
        scroll_layout.setSpacing(10)

        shell = QFrame()
        shell.setObjectName("Shell")

        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(12)

        shell_layout.addWidget(self._build_header())
        shell_layout.addWidget(self._build_main_card())

        scroll_layout.addWidget(shell, 0, Qt.AlignHCenter | Qt.AlignTop)
        scroll_layout.addStretch(1)

        scroll_area.setWidget(scroll_content)
        root_layout.addWidget(scroll_area)

    def _build_header(self) -> QWidget:
        card = QFrame()
        card.setObjectName("HeaderCard")
        card.setMinimumHeight(92)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(5)

        title = QLabel("FTM Licence Maker")
        title.setObjectName("Title")

        subtitle = QLabel(
            "Version 2 Ed25519 imzalı FTM lisansı üretir. "
            "Lisans üretimi sadece Mustafa'nın kişisel bilgisayarında yapılmalıdır. "
            "Private key encrypted PEM dosyası ve parola olmadan lisans üretilemez."
        )
        subtitle.setObjectName("Subtitle")
        subtitle.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(subtitle)

        return card

    def _build_main_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("MainCard")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(14)
        grid.setColumnStretch(0, 13)
        grid.setColumnStretch(1, 11)

        left_column = self._build_license_card()
        right_column = self._build_right_column()

        grid.addWidget(left_column, 0, 0)
        grid.addWidget(right_column, 0, 1)

        layout.addLayout(grid)
        layout.addLayout(self._build_button_row())

        return card

    def _build_right_column(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        layout.addWidget(self._build_key_card())
        layout.addWidget(self._build_output_card())
        layout.addWidget(self._build_info_card())
        layout.addStretch(1)

        return container

    def _build_card_title(self, title_text: str) -> QWidget:
        header = QFrame()
        header.setObjectName("SectionHeader")
        header.setMinimumHeight(36)

        layout = QHBoxLayout(header)
        layout.setContentsMargins(12, 5, 12, 5)

        title = QLabel(title_text)
        title.setObjectName("SectionTitle")

        layout.addWidget(title)
        layout.addStretch(1)

        return header

    def _build_labeled_field(self, label_text: str, widget: QWidget) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        label = QLabel(label_text)
        label.setObjectName("FieldLabel")

        layout.addWidget(label)
        layout.addWidget(widget)

        return container

    def _build_password_widget(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(7)

        layout.addWidget(self.private_key_password_input)
        layout.addWidget(self.show_password_checkbox, 0, Qt.AlignLeft)

        return container

    def _build_license_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("InnerCard")
        card.setMinimumWidth(650)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(13)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(13)
        form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

        form.addRow("Firma adı", self.company_name_input)
        form.addRow("Cihaz kodu", self.device_code_input)
        form.addRow("Lisans tipi", self.license_type_combo)
        form.addRow("Özel tip", self.custom_license_type_input)
        form.addRow("Gün", self.days_input)
        form.addRow("Başlangıç", self.starts_at_input)
        form.addRow("Not", self.notes_input)

        layout.addWidget(self._build_card_title("Lisans Bilgileri"))
        layout.addLayout(form)
        layout.addStretch(1)

        return card

    def _build_key_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("InnerCard")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(11)

        layout.addWidget(self._build_card_title("Güvenlik Anahtarı"))

        layout.addWidget(
            self._build_labeled_field(
                "Encrypted private key dosyası",
                self.private_key_path_input,
            )
        )
        layout.addWidget(
            self._build_labeled_field(
                "Private key parolası",
                self._build_password_widget(),
            )
        )
        layout.addWidget(
            self._build_labeled_field(
                "Public key fingerprint",
                self.public_fingerprint_input,
            )
        )

        layout.addWidget(self.verify_key_button)
        layout.addWidget(self.private_key_status_label)
        layout.addWidget(self.legacy_key_warning_label)

        return card

    def _build_output_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("InnerCard")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(11)

        folder_row = QHBoxLayout()
        folder_row.setContentsMargins(0, 0, 0, 0)
        folder_row.setSpacing(8)
        folder_row.addWidget(self.output_folder_input, 1)
        folder_row.addWidget(self.select_output_folder_button)

        folder_widget = QWidget()
        folder_widget.setLayout(folder_row)

        layout.addWidget(self._build_card_title("Çıktı ve Log"))
        layout.addWidget(self._build_labeled_field("Çıktı klasörü", folder_widget))
        layout.addWidget(self._build_labeled_field("Son lisans dosyası", self.output_file_input))
        layout.addWidget(self._build_labeled_field("Lisans üretim logu", self.log_file_input))

        return card

    def _build_info_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("InnerCard")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        text = QLabel(
            "1. Müşteri bilgisayarında sadece FTM kurulur ve cihaz kodu alınır.\n"
            "2. Lisans müşteri bilgisayarında değil, Mustafa'nın kişisel bilgisayarında üretilir.\n"
            "3. Private key müşteriye gitmez; müşteriye sadece .ftmlic dosyası aktarılır.\n"
            "4. Bu araç müşteri kurulum paketine eklenmez."
        )
        text.setObjectName("MutedText")
        text.setWordWrap(True)

        layout.addWidget(self._build_card_title("Güvenli Kullanım"))
        layout.addWidget(text)

        return card

    def _build_button_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(12)
        row.addStretch(1)
        row.addWidget(self.clear_button)
        row.addWidget(self.generate_button)
        return row

    def _toggle_password_visibility(self) -> None:
        if self.show_password_checkbox.isChecked():
            self.private_key_password_input.setEchoMode(QLineEdit.Normal)
            return

        self.private_key_password_input.setEchoMode(QLineEdit.Password)

    def _load_private_key_status(self) -> None:
        try:
            private_key_file = _find_encrypted_private_key_file()
            _assert_encrypted_private_key_file(private_key_file)

            self.private_key_path_input.setText(str(private_key_file))
            self.public_fingerprint_input.setText("")
            self.private_key_status_label.setObjectName("StatusBox")
            self.private_key_status_label.setText(
                "Encrypted key bulundu. Parolayı girip doğrulayın. Parolayı görerek kontrol etmek için kutuyu işaretleyebilirsin."
            )

            warnings = _find_plain_private_key_warnings()

            if warnings:
                self.legacy_key_warning_label.setVisible(True)
                first_warning_path = warnings[0]
                extra_count = len(warnings) - 1
                extra_text = f" (+{extra_count} dosya)" if extra_count > 0 else ""
                self.legacy_key_warning_label.setText(
                    "UYARI: Şifresiz private key bulundu ve kullanılmayacak. "
                    "Encrypted key doğrulandıktan sonra bu dosyayı güvenli offline yedeğe alıp "
                    "günlük kullanımdan kaldır.\n"
                    f"{first_warning_path}{extra_text}"
                )
            else:
                self.legacy_key_warning_label.setVisible(False)
                self.legacy_key_warning_label.setText("")

        except Exception as exc:
            self.private_key_path_input.setText(_candidate_key_paths_text())
            self.public_fingerprint_input.setText("")
            self.private_key_status_label.setObjectName("WarningBox")
            self.private_key_status_label.setText(
                "Encrypted private key hazır değil. Lisans oluşturulamaz.\n"
                f"Hata: {exc}"
            )
            self.legacy_key_warning_label.setVisible(False)
            self.legacy_key_warning_label.setText("")

    def _verify_private_key_from_ui(self) -> None:
        try:
            password_text = self.private_key_password_input.text()

            if password_text != password_text.strip():
                self.private_key_status_label.setObjectName("WarningBox")
                self.private_key_status_label.setText(
                    "Parolanın başında veya sonunda boşluk var. "
                    "Bu bilinçli değilse parolayı temizleyip tekrar dene."
                )

            private_key, private_key_file = _load_private_key_with_path(
                password=password_text
            )
            public_key = private_key.public_key()
            fingerprint = _public_key_fingerprint(public_key)

            self.private_key_path_input.setText(str(private_key_file))
            self.public_fingerprint_input.setText(fingerprint)
            self.private_key_status_label.setObjectName("StatusBox")
            self.private_key_status_label.setText(
                "Encrypted private key parola ile doğrulandı."
            )

            QMessageBox.information(
                self,
                "Private Key Doğrulandı",
                "Encrypted private key başarıyla açıldı.\n\n"
                f"Fingerprint:\n{fingerprint}",
            )

        except Exception as exc:
            self.public_fingerprint_input.setText("")
            self.private_key_status_label.setObjectName("WarningBox")
            self.private_key_status_label.setText(
                "Private key doğrulanamadı.\n"
                f"Hata: {exc}"
            )

            QMessageBox.critical(
                self,
                "Private Key Doğrulanamadı",
                str(exc),
            )

    def _select_output_folder(self) -> None:
        selected_folder = QFileDialog.getExistingDirectory(
            self,
            "Lisans çıktı klasörü seç",
            self.output_folder_input.text().strip() or str(DEFAULT_OUTPUT_FOLDER),
        )

        if selected_folder:
            self.output_folder_input.setText(selected_folder)

    def _sync_license_type_inputs(self) -> None:
        selected_type = str(self.license_type_combo.currentData() or "").strip()

        if selected_type == "annual":
            self.days_input.setValue(365)
            self.custom_license_type_input.setEnabled(False)
            return

        if selected_type == "demo_30_days":
            self.days_input.setValue(30)
            self.custom_license_type_input.setEnabled(False)
            return

        if selected_type == "test_7_days":
            self.days_input.setValue(7)
            self.custom_license_type_input.setEnabled(False)
            return

        self.custom_license_type_input.setEnabled(True)

    def _selected_license_type(self) -> str:
        selected_type = str(self.license_type_combo.currentData() or "").strip()

        if selected_type == "custom":
            return _clean_required_text(
                self.custom_license_type_input.text(),
                "Özel lisans tipi",
            )

        return selected_type

    def _generate_license(self) -> None:
        try:
            password_text = self.private_key_password_input.text()

            if password_text != password_text.strip():
                self.private_key_status_label.setObjectName("WarningBox")
                self.private_key_status_label.setText(
                    "Parolanın başında veya sonunda boşluk var. "
                    "Bu bilinçli değilse parolayı temizleyip tekrar dene."
                )

            private_key, private_key_file = _load_private_key_with_path(
                password=password_text
            )
            public_key = private_key.public_key()
            public_key_fingerprint = _public_key_fingerprint(public_key)

            company_name = _clean_required_text(
                self.company_name_input.text(),
                "Firma adı",
            )
            device_code = _clean_device_code(self.device_code_input.text())
            license_type = _clean_required_text(
                self._selected_license_type(),
                "Lisans tipi",
            )
            valid_days = int(self.days_input.value())
            starts_at = self.starts_at_input.date().toPython()
            expires_at = starts_at + timedelta(days=valid_days)
            notes = self.notes_input.toPlainText().strip()

            payload = {
                "company_name": company_name,
                "license_type": license_type,
                "device_code": device_code,
                "starts_at": starts_at.strftime(LICENSE_DATE_FORMAT),
                "expires_at": expires_at.strftime(LICENSE_DATE_FORMAT),
                "issued_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "notes": notes,
            }

            license_data = _build_signed_license_data(
                private_key=private_key,
                payload=payload,
            )

            output_folder = Path(
                self.output_folder_input.text().strip() or str(DEFAULT_OUTPUT_FOLDER)
            ).expanduser()

            output_folder.mkdir(parents=True, exist_ok=True)

            output_file = output_folder / _build_license_file_name(
                company_name=company_name,
                device_code=device_code,
                license_type=license_type,
            )

            _write_json_file(
                target_file=output_file,
                payload=license_data,
            )

            _write_license_generation_log(
                company_name=company_name,
                device_code=device_code,
                license_type=license_type,
                starts_at=payload["starts_at"],
                expires_at=payload["expires_at"],
                output_file=output_file,
                private_key_file=private_key_file,
                public_key_fingerprint=public_key_fingerprint,
            )

            self.private_key_path_input.setText(str(private_key_file))
            self.public_fingerprint_input.setText(public_key_fingerprint)
            self.output_file_input.setText(str(output_file))
            self.private_key_status_label.setObjectName("StatusBox")
            self.private_key_status_label.setText(
                "Lisans üretildi ve üretim logu yazıldı."
            )

            QMessageBox.information(
                self,
                "Lisans Oluşturuldu",
                "İmzalı lisans başarıyla oluşturuldu.\n\n"
                f"Dosya:\n{output_file}\n\n"
                "Bu dosyada private key veya private key parolası yoktur. "
                "Müşteri bilgisayarına yalnızca bu .ftmlic dosyasını aktar.",
            )

        except Exception as exc:
            QMessageBox.critical(
                self,
                "Lisans Oluşturulamadı",
                str(exc),
            )

    def _clear_form(self) -> None:
        self.company_name_input.clear()
        self.device_code_input.clear()
        self.license_type_combo.setCurrentIndex(0)
        self.custom_license_type_input.setText("annual_test")
        self.days_input.setValue(365)
        self.starts_at_input.setDate(QDate.currentDate())
        self.notes_input.clear()
        self.output_file_input.clear()


def _application_folder() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent

    return Path(__file__).resolve().parent


def _candidate_encrypted_private_key_files() -> list[Path]:
    candidates = [
        DEFAULT_ENCRYPTED_PRIVATE_KEY_FILE,
    ]

    unique_candidates: list[Path] = []
    seen_paths: set[str] = set()

    for candidate in candidates:
        try:
            normalized_path = str(candidate.expanduser().resolve())
        except OSError:
            normalized_path = str(candidate)

        if normalized_path in seen_paths:
            continue

        seen_paths.add(normalized_path)
        unique_candidates.append(candidate)

    return unique_candidates


def _candidate_plain_private_key_files() -> list[Path]:
    candidates = [
        Path(os.environ.get("FTM_LICENSE_PLAIN_PRIVATE_KEY_FILE", "")).expanduser()
        if os.environ.get("FTM_LICENSE_PLAIN_PRIVATE_KEY_FILE")
        else None,
        Path(r"C:\FTM_PRIVATE_KEYS") / LEGACY_PLAIN_PRIVATE_KEY_FILE_NAME,
        LICENSE_ADMIN_KEYS_FOLDER / LEGACY_PLAIN_PRIVATE_KEY_FILE_NAME,
        _application_folder() / "keys" / LEGACY_PLAIN_PRIVATE_KEY_FILE_NAME,
    ]

    unique_candidates: list[Path] = []
    seen_paths: set[str] = set()

    for candidate in candidates:
        if candidate is None:
            continue

        try:
            normalized_path = str(candidate.expanduser().resolve())
        except OSError:
            normalized_path = str(candidate)

        if normalized_path in seen_paths:
            continue

        seen_paths.add(normalized_path)
        unique_candidates.append(candidate)

    return unique_candidates


def _find_plain_private_key_warnings() -> list[Path]:
    warnings: list[Path] = []

    for candidate in _candidate_plain_private_key_files():
        try:
            if candidate.exists() and candidate.is_file():
                warnings.append(candidate)
        except OSError:
            continue

    return warnings


def _candidate_key_paths_text() -> str:
    return " | ".join(str(path) for path in _candidate_encrypted_private_key_files())


def _find_encrypted_private_key_file() -> Path:
    errors: list[str] = []

    for private_key_file in _candidate_encrypted_private_key_files():
        if not private_key_file.exists():
            errors.append(f"Bulunamadı: {private_key_file}")
            continue

        if not private_key_file.is_file():
            errors.append(f"Dosya değil: {private_key_file}")
            continue

        _assert_encrypted_private_key_file(private_key_file)
        return private_key_file

    raise LicenseMakerError(
        "Geçerli encrypted private key dosyası bulunamadı.\n\n"
        "Aranan yollar:\n"
        + "\n".join(f"- {path}" for path in _candidate_encrypted_private_key_files())
        + "\n\nDetay:\n"
        + "\n".join(errors)
        + "\n\nBeklenen güvenli yol:\n"
        + str(DEFAULT_ENCRYPTED_PRIVATE_KEY_FILE)
    )


def _assert_encrypted_private_key_file(private_key_file: Path) -> None:
    try:
        key_bytes = private_key_file.read_bytes()
    except OSError as exc:
        raise LicenseMakerError(
            f"Private key dosyası okunamadı: {private_key_file}\nHata: {exc}"
        ) from exc

    if b"-----BEGIN ENCRYPTED PRIVATE KEY-----" not in key_bytes:
        if b"-----BEGIN PRIVATE KEY-----" in key_bytes:
            raise LicenseMakerError(
                "Bu dosya şifresiz private key gibi görünüyor ve güvenlik nedeniyle reddedildi.\n"
                "ADIM 2.2 ile parolalı/encrypted private key üretmelisin.\n\n"
                f"Dosya: {private_key_file}"
            )

        raise LicenseMakerError(
            "Private key dosyası encrypted PKCS8 PEM formatında değil.\n"
            "Beklenen başlık: -----BEGIN ENCRYPTED PRIVATE KEY-----\n\n"
            f"Dosya: {private_key_file}"
        )


def _clean_private_key_password(password: str) -> str:
    cleaned_password = password or ""

    if not cleaned_password:
        raise LicenseMakerError(
            "Private key parolası boş olamaz.\n"
            "Encrypted private key dosyasını açmak için parolayı girmelisin."
        )

    if "\n" in cleaned_password or "\r" in cleaned_password:
        raise LicenseMakerError("Private key parolası satır sonu karakteri içeremez.")

    return cleaned_password


def _load_private_key_with_path(*, password: str) -> tuple[Ed25519PrivateKey, Path]:
    cleaned_password = _clean_private_key_password(password)
    errors: list[str] = []

    for private_key_file in _candidate_encrypted_private_key_files():
        if not private_key_file.exists():
            errors.append(f"Bulunamadı: {private_key_file}")
            continue

        if not private_key_file.is_file():
            errors.append(f"Dosya değil: {private_key_file}")
            continue

        try:
            _assert_encrypted_private_key_file(private_key_file)

            loaded_key = serialization.load_pem_private_key(
                private_key_file.read_bytes(),
                password=cleaned_password.encode("utf-8"),
            )

        except TypeError:
            errors.append(
                f"Açılamadı: {private_key_file} | Dosya parola istemiyor olabilir veya parola biçimi uygun değil."
            )
            continue

        except ValueError:
            errors.append(
                f"Açılamadı: {private_key_file} | Parola hatalı olabilir veya dosya bozuk olabilir."
            )
            continue

        except Exception as exc:
            errors.append(f"Okunamadı: {private_key_file} | Hata: {exc}")
            continue

        if not isinstance(loaded_key, Ed25519PrivateKey):
            errors.append(f"Ed25519 formatında değil: {private_key_file}")
            continue

        return loaded_key, private_key_file

    raise LicenseMakerError(
        "Encrypted private key açılamadı.\n\n"
        "Kontrol et:\n"
        "- Private key dosyası doğru yerde mi?\n"
        "- Parola doğru mu?\n"
        "- Dosya ADIM 2.2 ile oluşturulan encrypted PEM dosyası mı?\n\n"
        "Aranan yollar:\n"
        + "\n".join(f"- {path}" for path in _candidate_encrypted_private_key_files())
        + "\n\nDetay:\n"
        + "\n".join(errors)
    )


def _build_signed_license_data(
    *,
    private_key: Ed25519PrivateKey,
    payload: dict[str, Any],
) -> dict[str, Any]:
    payload_bytes = _canonicalize_payload(payload)
    signature_bytes = private_key.sign(payload_bytes)
    signature_text = base64.b64encode(signature_bytes).decode("ascii")

    return {
        "version": SIGNED_LICENSE_VERSION,
        "algorithm": SIGNED_LICENSE_ALGORITHM,
        "payload": payload,
        "signature": signature_text,
    }


def _canonicalize_payload(payload: dict[str, Any]) -> bytes:
    payload_text = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )

    return payload_text.encode("utf-8")


def _write_json_file(
    *,
    target_file: Path,
    payload: dict[str, Any],
) -> None:
    target_file.parent.mkdir(parents=True, exist_ok=True)

    target_file.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _write_license_generation_log(
    *,
    company_name: str,
    device_code: str,
    license_type: str,
    starts_at: str,
    expires_at: str,
    output_file: Path,
    private_key_file: Path,
    public_key_fingerprint: str,
) -> None:
    log_file = DEFAULT_LICENSE_GENERATION_LOG_FILE.expanduser()
    log_file.parent.mkdir(parents=True, exist_ok=True)

    log_payload = {
        "event": "license_generated",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "company_name": company_name,
        "device_code": device_code,
        "license_type": license_type,
        "starts_at": starts_at,
        "expires_at": expires_at,
        "output_file": str(output_file),
        "private_key_file": str(private_key_file),
        "public_key_fingerprint": public_key_fingerprint,
        "maker_version": MAKER_VERSION,
        "algorithm": SIGNED_LICENSE_ALGORITHM,
        "signed_license_version": SIGNED_LICENSE_VERSION,
    }

    log_file.open("a", encoding="utf-8").write(
        json.dumps(
            log_payload,
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n"
    )


def _public_key_fingerprint(public_key: Ed25519PublicKey) -> str:
    public_key_der = public_key.public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    fingerprint = hashlib.sha256(public_key_der).hexdigest().upper()

    return "-".join(
        fingerprint[index : index + 8]
        for index in range(0, len(fingerprint), 8)
    )


def _build_license_file_name(
    *,
    company_name: str,
    device_code: str,
    license_type: str,
) -> str:
    safe_company = _safe_file_name(company_name)
    safe_device = _safe_file_name(device_code)
    safe_license_type = _safe_file_name(license_type)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    return f"{safe_company}_{safe_license_type}_{safe_device}_{timestamp}.ftmlic"


def _clean_device_code(value: Any) -> str:
    cleaned_value = str(value or "").strip().upper()

    if not cleaned_value:
        raise LicenseMakerError("Cihaz kodu boş olamaz.")

    if not cleaned_value.startswith("FTM-"):
        raise LicenseMakerError("Cihaz kodu FTM- ile başlamalıdır.")

    parts = cleaned_value.split("-")

    if len(parts) != 6:
        raise LicenseMakerError(
            "Cihaz kodu formatı geçersiz.\n"
            "Beklenen format: FTM-XXXX-XXXX-XXXX-XXXX-XXXX"
        )

    if parts[0] != "FTM":
        raise LicenseMakerError(
            "Cihaz kodu formatı geçersiz.\n"
            "Beklenen format: FTM-XXXX-XXXX-XXXX-XXXX-XXXX"
        )

    for part in parts[1:]:
        if len(part) != 4:
            raise LicenseMakerError(
                "Cihaz kodu formatı geçersiz. Her kod bölümü 4 karakter olmalıdır."
            )

        if not part.isalnum():
            raise LicenseMakerError(
                "Cihaz kodu formatı geçersiz. Kod yalnızca harf ve rakam içermelidir."
            )

    return cleaned_value


def _clean_required_text(value: Any, field_name: str) -> str:
    cleaned_value = str(value or "").strip()

    if not cleaned_value:
        raise LicenseMakerError(f"{field_name} boş olamaz.")

    return cleaned_value


def _safe_file_name(value: str) -> str:
    cleaned_value = str(value or "").strip()

    if not cleaned_value:
        cleaned_value = "license"

    cleaned_value = re.sub(r"[^A-Za-z0-9._-]+", "_", cleaned_value)
    cleaned_value = cleaned_value.strip("._-")

    if not cleaned_value:
        return "license"

    return cleaned_value[:80]


def main() -> None:
    app = QApplication(sys.argv)

    window = FTMLicenseMakerWindow()
    window.resize(1320, 780)
    window.show()

    screen = app.primaryScreen()

    if screen is not None:
        screen_geometry = screen.availableGeometry()
        window_geometry = window.frameGeometry()
        window_geometry.moveCenter(screen_geometry.center())
        window.move(window_geometry.topLeft())

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
