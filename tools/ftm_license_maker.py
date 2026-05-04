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
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


PRIVATE_KEY_FILE_NAME = "ftm_license_ed25519_private.pem"

FALLBACK_PRIVATE_KEY_FOLDER = Path(
    os.environ.get(
        "FTM_LICENSE_PRIVATE_KEY_FOLDER",
        r"C:\FTM_PRIVATE_KEYS",
    )
)

FALLBACK_PRIVATE_KEY_FILE = FALLBACK_PRIVATE_KEY_FOLDER / PRIVATE_KEY_FILE_NAME

DEFAULT_OUTPUT_FOLDER = Path.home() / "Desktop"

SIGNED_LICENSE_VERSION = 2
SIGNED_LICENSE_ALGORITHM = "Ed25519"
LICENSE_DATE_FORMAT = "%Y-%m-%d"


APP_STYLE = """
QWidget {
    background-color: #0f172a;
    color: #e5e7eb;
    font-size: 12px;
}

QFrame#Shell {
    background-color: #0f172a;
    border: none;
}

QFrame#HeaderCard {
    background-color: #111827;
    border: 1px solid #263449;
    border-radius: 14px;
}

QFrame#MainCard {
    background-color: #111827;
    border: 1px solid #263449;
    border-radius: 16px;
}

QFrame#InnerCard {
    background-color: #0b1220;
    border: 1px solid #24324a;
    border-radius: 13px;
}

QLabel#Title {
    color: #f8fafc;
    font-size: 24px;
    font-weight: 900;
}

QLabel#Subtitle {
    color: #94a3b8;
    font-size: 12px;
}

QLabel#SectionTitle {
    color: #bfdbfe;
    font-size: 14px;
    font-weight: 900;
}

QLabel#MutedText {
    color: #94a3b8;
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

QLineEdit,
QTextEdit,
QComboBox,
QDateEdit,
QSpinBox {
    background-color: #111827;
    color: #f8fafc;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 5px 8px;
    selection-background-color: #2563eb;
    selection-color: #ffffff;
    min-height: 26px;
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
    color: #cbd5e1;
    border: 1px solid #475569;
}

QTextEdit {
    min-height: 58px;
    max-height: 72px;
}

QPushButton {
    background-color: #1e293b;
    color: #f8fafc;
    border: 1px solid #334155;
    border-radius: 9px;
    padding: 8px 14px;
    font-weight: 800;
    min-height: 32px;
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
"""


class LicenseMakerError(ValueError):
    pass


class FTMLicenseMakerWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("FTM Licence Maker")
        self.resize(1160, 660)
        self.setMinimumSize(1020, 600)
        self.setStyleSheet(APP_STYLE)

        self.private_key_path_input = QLineEdit("")
        self.private_key_path_input.setReadOnly(True)

        self.private_key_status_label = QLabel("")
        self.private_key_status_label.setObjectName("SuccessText")
        self.private_key_status_label.setWordWrap(True)

        self.public_fingerprint_input = QLineEdit("")
        self.public_fingerprint_input.setReadOnly(True)

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
        self.output_folder_input.setReadOnly(True)

        self.output_file_input = QLineEdit("")
        self.output_file_input.setReadOnly(True)

        self.select_output_folder_button = QPushButton("Klasör Seç")
        self.select_output_folder_button.clicked.connect(self._select_output_folder)

        self.generate_button = QPushButton("İmzalı Lisans Oluştur")
        self.generate_button.setObjectName("Primary")
        self.generate_button.clicked.connect(self._generate_license)

        self.clear_button = QPushButton("Formu Temizle")
        self.clear_button.setObjectName("Danger")
        self.clear_button.clicked.connect(self._clear_form)

        self._build_ui()
        self._load_private_key_status()
        self._sync_license_type_inputs()

    def _build_ui(self) -> None:
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(18, 16, 18, 16)
        outer_layout.setSpacing(10)

        shell = QFrame()
        shell.setObjectName("Shell")
        shell.setMaximumWidth(1220)

        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(10)

        shell_layout.addWidget(self._build_header())
        shell_layout.addWidget(self._build_main_card())

        outer_layout.addWidget(shell, 0, Qt.AlignHCenter | Qt.AlignTop)
        outer_layout.addStretch(1)

    def _build_header(self) -> QWidget:
        card = QFrame()
        card.setObjectName("HeaderCard")
        card.setFixedHeight(76)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(2)

        title = QLabel("FTM Licence Maker")
        title.setObjectName("Title")

        subtitle = QLabel(
            "Version 2 Ed25519 imzalı FTM lisansı üretir. "
            "Private key önce EXE yanındaki keys klasöründe, sonra C:\\FTM_PRIVATE_KEYS içinde aranır."
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
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)
        grid.setColumnStretch(0, 3)
        grid.setColumnStretch(1, 2)

        grid.addWidget(self._build_license_card(), 0, 0, 3, 1)
        grid.addWidget(self._build_key_card(), 0, 1)
        grid.addWidget(self._build_output_card(), 1, 1)
        grid.addWidget(self._build_info_card(), 2, 1)

        layout.addLayout(grid)
        layout.addLayout(self._build_button_row())

        return card

    def _build_license_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("InnerCard")
        card.setMinimumWidth(640)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        title = QLabel("Lisans Bilgileri")
        title.setObjectName("SectionTitle")

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(7)
        form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

        form.addRow("Firma adı", self.company_name_input)
        form.addRow("Cihaz kodu", self.device_code_input)
        form.addRow("Lisans tipi", self.license_type_combo)
        form.addRow("Özel tip", self.custom_license_type_input)
        form.addRow("Gün", self.days_input)
        form.addRow("Başlangıç", self.starts_at_input)
        form.addRow("Not", self.notes_input)

        layout.addWidget(title)
        layout.addLayout(form)

        return card

    def _build_key_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("InnerCard")
        card.setFixedHeight(164)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(7)

        title = QLabel("Güvenlik Anahtarı")
        title.setObjectName("SectionTitle")

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(7)
        form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

        form.addRow("Private key", self.private_key_path_input)
        form.addRow("Fingerprint", self.public_fingerprint_input)

        layout.addWidget(title)
        layout.addLayout(form)
        layout.addWidget(self.private_key_status_label)

        return card

    def _build_output_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("InnerCard")
        card.setFixedHeight(148)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(7)

        title = QLabel("Çıktı")
        title.setObjectName("SectionTitle")

        folder_row = QHBoxLayout()
        folder_row.setSpacing(8)
        folder_row.addWidget(self.output_folder_input, 1)
        folder_row.addWidget(self.select_output_folder_button)

        folder_widget = QWidget()
        folder_widget.setLayout(folder_row)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(7)
        form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

        form.addRow("Klasör", folder_widget)
        form.addRow("Son dosya", self.output_file_input)

        layout.addWidget(title)
        layout.addLayout(form)

        return card

    def _build_info_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("InnerCard")
        card.setFixedHeight(116)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)

        title = QLabel("Kısa Kullanım")
        title.setObjectName("SectionTitle")

        text = QLabel(
            "1. Test bilgisayardaki cihaz kodunu al.\n"
            "2. Firma adı ve lisans süresini gir.\n"
            "3. .ftmlic dosyasını oluşturup test bilgisayara yükle.\n"
            "Private key dosyasını müşteriye gönderme."
        )
        text.setObjectName("MutedText")
        text.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(text)

        return card

    def _build_button_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)
        row.addStretch(1)
        row.addWidget(self.clear_button)
        row.addWidget(self.generate_button)
        return row

    def _load_private_key_status(self) -> None:
        try:
            private_key, private_key_file = _load_private_key_with_path()
            public_key = private_key.public_key()

            self.private_key_path_input.setText(str(private_key_file))
            self.public_fingerprint_input.setText(_public_key_fingerprint(public_key))
            self.private_key_status_label.setObjectName("SuccessText")
            self.private_key_status_label.setText(
                "Private key bulundu ve Ed25519 formatında doğrulandı."
            )

        except Exception as exc:
            self.private_key_path_input.setText(_candidate_key_paths_text())
            self.public_fingerprint_input.setText("")
            self.private_key_status_label.setObjectName("WarningText")
            self.private_key_status_label.setText(
                "Private key okunamadı. Lisans oluşturulamaz.\n"
                f"Hata: {exc}"
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
            private_key, private_key_file = _load_private_key_with_path()

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

            self.private_key_path_input.setText(str(private_key_file))
            self.output_file_input.setText(str(output_file))

            QMessageBox.information(
                self,
                "Lisans Oluşturuldu",
                "İmzalı lisans başarıyla oluşturuldu.\n\n"
                f"Dosya:\n{output_file}",
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


def _portable_private_key_file() -> Path:
    return _application_folder() / "keys" / PRIVATE_KEY_FILE_NAME


def _candidate_private_key_files() -> list[Path]:
    portable_private_key_file = _portable_private_key_file()

    candidates = [
        portable_private_key_file,
        FALLBACK_PRIVATE_KEY_FILE,
    ]

    unique_candidates: list[Path] = []
    seen_paths: set[str] = set()

    for candidate in candidates:
        normalized_path = str(candidate.resolve() if candidate.exists() else candidate)

        if normalized_path in seen_paths:
            continue

        seen_paths.add(normalized_path)
        unique_candidates.append(candidate)

    return unique_candidates


def _candidate_key_paths_text() -> str:
    return " | ".join(str(path) for path in _candidate_private_key_files())


def _load_private_key_with_path() -> tuple[Ed25519PrivateKey, Path]:
    errors: list[str] = []

    for private_key_file in _candidate_private_key_files():
        if not private_key_file.exists():
            errors.append(f"Bulunamadı: {private_key_file}")
            continue

        try:
            loaded_key = serialization.load_pem_private_key(
                private_key_file.read_bytes(),
                password=None,
            )

        except Exception as exc:
            errors.append(f"Okunamadı: {private_key_file} | Hata: {exc}")
            continue

        if not isinstance(loaded_key, Ed25519PrivateKey):
            errors.append(f"Ed25519 formatında değil: {private_key_file}")
            continue

        return loaded_key, private_key_file

    raise LicenseMakerError(
        "Geçerli private key dosyası bulunamadı.\n\n"
        "Aranan yollar:\n"
        + "\n".join(f"- {path}" for path in _candidate_private_key_files())
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
    window.resize(1160, 660)
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