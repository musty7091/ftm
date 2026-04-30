from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.services.license_service import (
    LicenseServiceError,
    create_license_file_for_device_code,
)


APP_TITLE = "FTM Lisans Üretici"
DEFAULT_OUTPUT_FOLDER = PROJECT_ROOT / "licenses"
DEFAULT_LICENSE_TYPE = "annual"


class LicenseGeneratorWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle(APP_TITLE)
        self.resize(860, 720)
        self.setMinimumSize(820, 680)

        self.company_name_input = QLineEdit()
        self.company_name_input.setPlaceholderText("Örn: ABC Market")

        self.device_code_input = QLineEdit()
        self.device_code_input.setPlaceholderText("Örn: FTM-D7A3-B894-D26B-5D81-D2A4")

        self.valid_days_input = QSpinBox()
        self.valid_days_input.setMinimum(1)
        self.valid_days_input.setMaximum(3650)
        self.valid_days_input.setValue(365)
        self.valid_days_input.setSuffix(" gün")

        self.output_folder_input = QLineEdit()
        self.output_folder_input.setText(str(DEFAULT_OUTPUT_FOLDER))
        self.output_folder_input.setReadOnly(True)

        self.result_label = QLabel("Henüz lisans üretilmedi.")
        self.result_label.setObjectName("ResultLabel")
        self.result_label.setWordWrap(True)
        self.result_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self.last_created_file: Path | None = None

        self._build_ui()
        self._apply_style()

    def _build_ui(self) -> None:
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        content = QWidget()
        content.setObjectName("ContentRoot")

        root_layout = QVBoxLayout(content)
        root_layout.setContentsMargins(24, 24, 24, 24)
        root_layout.setSpacing(16)

        root_layout.addWidget(self._build_header_card())
        root_layout.addWidget(self._build_form_card())
        root_layout.addWidget(self._build_result_card())
        root_layout.addStretch(1)

        scroll_area.setWidget(content)
        outer_layout.addWidget(scroll_area)

    def _build_header_card(self) -> QWidget:
        header_card = QFrame()
        header_card.setObjectName("HeaderCard")

        header_layout = QVBoxLayout(header_card)
        header_layout.setContentsMargins(22, 20, 22, 20)
        header_layout.setSpacing(10)

        title = QLabel("FTM Lisans Üretici")
        title.setObjectName("Title")

        subtitle = QLabel(
            "Müşteriden gelen cihaz koduna göre lisans dosyası üretir. "
            "Bu uygulama sadece sende kalır; müşteriye yalnızca oluşan .ftmlic dosyası gönderilir."
        )
        subtitle.setObjectName("Subtitle")
        subtitle.setWordWrap(True)

        warning = QLabel(
            "Önemli: Lisansın çalışması için cihaz kodu birebir doğru olmalıdır. "
            "Firma adı ekranda ve takipte görünür; cihaz kodu teknik olarak kritik alandır."
        )
        warning.setObjectName("WarningText")
        warning.setWordWrap(True)

        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        header_layout.addWidget(warning)

        return header_card

    def _build_form_card(self) -> QWidget:
        form_card = QFrame()
        form_card.setObjectName("Card")

        form_layout = QVBoxLayout(form_card)
        form_layout.setContentsMargins(22, 20, 22, 20)
        form_layout.setSpacing(16)

        section_title = QLabel("Lisans Bilgileri")
        section_title.setObjectName("SectionTitle")

        form_layout.addWidget(section_title)
        form_layout.addWidget(
            self._build_field_row(
                label_text="Firma / Müşteri Adı",
                field_widget=self.company_name_input,
                helper_text="Lisans ekranında görünecek müşteri adıdır. Resmi unvan şart değil, takip edilebilir kısa ad yeterlidir.",
            )
        )
        form_layout.addWidget(
            self._build_device_code_row()
        )
        form_layout.addWidget(
            self._build_field_row(
                label_text="Lisans Süresi",
                field_widget=self.valid_days_input,
                helper_text="Genellikle 365 gün kullanılır. Deneme lisansı için daha kısa süre verebilirsin.",
            )
        )
        form_layout.addWidget(
            self._build_output_folder_row()
        )
        form_layout.addWidget(
            self._build_action_buttons()
        )

        return form_card

    def _build_field_row(
        self,
        *,
        label_text: str,
        field_widget: QWidget,
        helper_text: str,
    ) -> QWidget:
        row = QFrame()
        row.setObjectName("FieldRow")

        layout = QVBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        label = QLabel(label_text)
        label.setObjectName("FieldLabel")

        helper = QLabel(helper_text)
        helper.setObjectName("FieldHelper")
        helper.setWordWrap(True)

        field_widget.setMinimumHeight(42)

        layout.addWidget(label)
        layout.addWidget(field_widget)
        layout.addWidget(helper)

        return row

    def _build_device_code_row(self) -> QWidget:
        row = QFrame()
        row.setObjectName("FieldRow")

        layout = QVBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        label = QLabel("Cihaz Kodu")
        label.setObjectName("FieldLabel")

        input_row = QHBoxLayout()
        input_row.setSpacing(10)

        self.device_code_input.setMinimumHeight(42)

        paste_button = QPushButton("Panodan Yapıştır")
        paste_button.setMinimumHeight(42)
        paste_button.clicked.connect(self.paste_device_code)

        input_row.addWidget(self.device_code_input, 1)
        input_row.addWidget(paste_button, 0)

        helper = QLabel(
            "Müşterinin FTM uygulamasındaki Lisans ekranından kopyaladığı cihaz kodu birebir buraya yapıştırılmalıdır."
        )
        helper.setObjectName("FieldHelper")
        helper.setWordWrap(True)

        layout.addWidget(label)
        layout.addLayout(input_row)
        layout.addWidget(helper)

        return row

    def _build_output_folder_row(self) -> QWidget:
        row = QFrame()
        row.setObjectName("FieldRow")

        layout = QVBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        label = QLabel("Çıktı Klasörü")
        label.setObjectName("FieldLabel")

        input_row = QHBoxLayout()
        input_row.setSpacing(10)

        self.output_folder_input.setMinimumHeight(42)

        select_folder_button = QPushButton("Klasör Seç")
        select_folder_button.setMinimumHeight(42)
        select_folder_button.clicked.connect(self.select_output_folder)

        input_row.addWidget(self.output_folder_input, 1)
        input_row.addWidget(select_folder_button, 0)

        helper = QLabel(
            "Üretilen .ftmlic lisans dosyası bu klasöre kaydedilir. Varsayılan klasör: C:\\ftm\\licenses"
        )
        helper.setObjectName("FieldHelper")
        helper.setWordWrap(True)

        layout.addWidget(label)
        layout.addLayout(input_row)
        layout.addWidget(helper)

        return row

    def _build_action_buttons(self) -> QWidget:
        row = QFrame()
        row.setObjectName("ButtonRowFrame")

        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 6, 0, 0)
        layout.setSpacing(10)

        generate_button = QPushButton("Lisans Dosyası Üret")
        generate_button.setObjectName("PrimaryButton")
        generate_button.setMinimumHeight(44)
        generate_button.clicked.connect(self.generate_license)

        clear_button = QPushButton("Formu Temizle")
        clear_button.setMinimumHeight(44)
        clear_button.clicked.connect(self.clear_form)

        open_folder_button = QPushButton("Çıktı Klasörünü Aç")
        open_folder_button.setMinimumHeight(44)
        open_folder_button.clicked.connect(self.open_output_folder)

        layout.addWidget(generate_button)
        layout.addWidget(clear_button)
        layout.addWidget(open_folder_button)
        layout.addStretch(1)

        return row

    def _build_result_card(self) -> QWidget:
        result_card = QFrame()
        result_card.setObjectName("Card")

        result_layout = QVBoxLayout(result_card)
        result_layout.setContentsMargins(22, 20, 22, 20)
        result_layout.setSpacing(12)

        section_title = QLabel("Sonuç")
        section_title.setObjectName("SectionTitle")

        result_layout.addWidget(section_title)
        result_layout.addWidget(self.result_label)

        return result_card

    def paste_device_code(self) -> None:
        clipboard_text = QApplication.clipboard().text().strip()

        if not clipboard_text:
            QMessageBox.warning(
                self,
                "Pano Boş",
                "Panoda yapıştırılacak cihaz kodu bulunamadı.",
            )
            return

        self.device_code_input.setText(clipboard_text.upper())

    def select_output_folder(self) -> None:
        selected_folder = QFileDialog.getExistingDirectory(
            self,
            "Lisans Çıktı Klasörü Seç",
            self.output_folder_input.text().strip() or str(DEFAULT_OUTPUT_FOLDER),
        )

        if not selected_folder:
            return

        self.output_folder_input.setText(selected_folder)

    def generate_license(self) -> None:
        company_name = self.company_name_input.text().strip()
        device_code = self.device_code_input.text().strip().upper()
        valid_days = int(self.valid_days_input.value())
        output_folder_text = self.output_folder_input.text().strip()

        validation_error = self._validate_form(
            company_name=company_name,
            device_code=device_code,
            output_folder_text=output_folder_text,
        )

        if validation_error:
            QMessageBox.warning(
                self,
                "Eksik veya Hatalı Bilgi",
                validation_error,
            )
            return

        output_folder = Path(output_folder_text).expanduser()
        output_file = output_folder / self._build_default_file_name(
            company_name=company_name,
            valid_days=valid_days,
        )

        try:
            license_data = create_license_file_for_device_code(
                company_name=company_name,
                device_code=device_code,
                output_file=output_file,
                valid_days=valid_days,
                license_type=DEFAULT_LICENSE_TYPE,
                notes=self._build_default_note(
                    company_name=company_name,
                    valid_days=valid_days,
                ),
                overwrite=True,
            )

        except LicenseServiceError as exc:
            QMessageBox.critical(
                self,
                "Lisans Üretilemedi",
                str(exc),
            )
            return

        except Exception as exc:
            QMessageBox.critical(
                self,
                "Lisans Üretilemedi",
                f"Beklenmeyen hata oluştu:\n\n{exc}",
            )
            return

        self.last_created_file = output_file

        self.result_label.setText(
            "Lisans dosyası başarıyla üretildi.\n\n"
            f"Firma: {license_data.company_name}\n"
            f"Cihaz Kodu: {license_data.device_code}\n"
            f"Lisans Tipi: {license_data.license_type}\n"
            f"Başlangıç: {license_data.starts_at}\n"
            f"Bitiş: {license_data.expires_at}\n"
            f"Dosya: {output_file}"
        )

        QMessageBox.information(
            self,
            "Lisans Üretildi",
            "Lisans dosyası başarıyla üretildi.\n\n"
            f"{output_file}\n\n"
            "Bu dosyayı müşteriye gönderebilirsin.",
        )

    def clear_form(self) -> None:
        self.company_name_input.clear()
        self.device_code_input.clear()
        self.valid_days_input.setValue(365)
        self.output_folder_input.setText(str(DEFAULT_OUTPUT_FOLDER))
        self.result_label.setText("Henüz lisans üretilmedi.")
        self.last_created_file = None
        self.company_name_input.setFocus()

    def open_output_folder(self) -> None:
        output_folder_text = self.output_folder_input.text().strip()

        if not output_folder_text:
            QMessageBox.warning(
                self,
                "Klasör Açılamadı",
                "Çıktı klasörü boş.",
            )
            return

        output_folder = Path(output_folder_text).expanduser()
        output_folder.mkdir(parents=True, exist_ok=True)

        try:
            if sys.platform.startswith("win"):
                import os

                os.startfile(output_folder)
                return

            QMessageBox.information(
                self,
                "Çıktı Klasörü",
                str(output_folder),
            )

        except Exception as exc:
            QMessageBox.warning(
                self,
                "Klasör Açılamadı",
                f"Klasör açılırken hata oluştu:\n\n{exc}",
            )

    def _validate_form(
        self,
        *,
        company_name: str,
        device_code: str,
        output_folder_text: str,
    ) -> str | None:
        if not company_name:
            return "Firma / müşteri adı boş olamaz."

        if not device_code:
            return "Cihaz kodu boş olamaz."

        if not device_code.startswith("FTM-"):
            return "Cihaz kodu FTM- ile başlamalıdır."

        device_code_parts = device_code.split("-")

        if len(device_code_parts) != 6:
            return "Cihaz kodu formatı geçersiz. Beklenen örnek: FTM-D7A3-B894-D26B-5D81-D2A4"

        for code_part in device_code_parts[1:]:
            if len(code_part) != 4 or not code_part.isalnum():
                return "Cihaz kodu formatı geçersiz. Her bölüm 4 harf/rakam olmalıdır."

        if not output_folder_text:
            return "Çıktı klasörü boş olamaz."

        return None

    def _build_default_file_name(
        self,
        *,
        company_name: str,
        valid_days: int,
    ) -> str:
        today_text = date.today().strftime("%Y%m%d")
        company_slug = self._slugify(company_name)

        return f"{company_slug}_{valid_days}_GUN_{today_text}.ftmlic"

    def _build_default_note(
        self,
        *,
        company_name: str,
        valid_days: int,
    ) -> str:
        return f"{company_name} için {valid_days} günlük FTM lisansı."

    def _slugify(self, value: str) -> str:
        replacements = {
            "ç": "c",
            "ğ": "g",
            "ı": "i",
            "ö": "o",
            "ş": "s",
            "ü": "u",
            "Ç": "C",
            "Ğ": "G",
            "İ": "I",
            "Ö": "O",
            "Ş": "S",
            "Ü": "U",
        }

        cleaned_value = str(value or "").strip()

        for source_char, target_char in replacements.items():
            cleaned_value = cleaned_value.replace(source_char, target_char)

        cleaned_value = re.sub(r"[^A-Za-z0-9]+", "_", cleaned_value)
        cleaned_value = cleaned_value.strip("_").upper()

        if not cleaned_value:
            return "FTM_LISANS"

        return cleaned_value

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            QWidget {
                background-color: #0f172a;
                color: #e5e7eb;
                font-family: Segoe UI;
                font-size: 13px;
            }

            QWidget#ContentRoot {
                background-color: #0f172a;
            }

            QFrame#HeaderCard,
            QFrame#Card {
                background-color: #111827;
                border: 1px solid #334155;
                border-radius: 16px;
            }

            QFrame#FieldRow,
            QFrame#ButtonRowFrame {
                background-color: transparent;
                border: none;
            }

            QLabel#Title {
                color: #ffffff;
                font-size: 28px;
                font-weight: 900;
            }

            QLabel#SectionTitle {
                color: #ffffff;
                font-size: 19px;
                font-weight: 900;
            }

            QLabel#Subtitle,
            QLabel#ResultLabel {
                color: #cbd5e1;
                font-size: 12px;
            }

            QLabel#WarningText {
                color: #fde68a;
                font-size: 12px;
                font-weight: 800;
            }

            QLabel#FieldLabel {
                color: #f8fafc;
                font-size: 13px;
                font-weight: 900;
            }

            QLabel#FieldHelper {
                color: #94a3b8;
                font-size: 11px;
            }

            QLineEdit,
            QSpinBox {
                background-color: #1e293b;
                color: #e5e7eb;
                border: 1px solid #475569;
                border-radius: 10px;
                padding: 8px 10px;
                min-height: 38px;
                selection-background-color: #2563eb;
            }

            QLineEdit:focus,
            QSpinBox:focus {
                border: 1px solid #60a5fa;
            }

            QPushButton {
                background-color: #1e293b;
                color: #e5e7eb;
                border: 1px solid #475569;
                border-radius: 10px;
                padding: 10px 14px;
                font-weight: 800;
                min-height: 38px;
            }

            QPushButton:hover {
                background-color: #334155;
                border: 1px solid #64748b;
            }

            QPushButton#PrimaryButton {
                background-color: #2563eb;
                color: #ffffff;
                border: 1px solid #60a5fa;
            }

            QPushButton#PrimaryButton:hover {
                background-color: #1d4ed8;
            }

            QScrollArea {
                border: none;
                background-color: #0f172a;
            }

            QScrollBar:vertical {
                background-color: #0f172a;
                width: 10px;
                margin: 0px;
                border: none;
            }

            QScrollBar::handle:vertical {
                background-color: #334155;
                min-height: 30px;
                border-radius: 5px;
            }

            QScrollBar::handle:vertical:hover {
                background-color: #475569;
            }

            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0px;
                background: none;
                border: none;
            }

            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical {
                background: none;
            }
            """
        )


def main() -> None:
    app = QApplication(sys.argv)

    window = LicenseGeneratorWindow()
    window.showMaximized()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()