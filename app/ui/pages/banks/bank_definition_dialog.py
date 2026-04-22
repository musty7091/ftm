from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.ui.pages.banks.bank_dialog_styles import BANK_DIALOG_STYLES


class BankDefinitionDialog(QDialog):
    def __init__(
        self,
        *,
        parent: QWidget | None,
        mode: str,
        bank_row: Any | None = None,
    ) -> None:
        super().__init__(parent)

        self.mode = mode
        self.bank_row = bank_row
        self.payload: dict[str, Any] | None = None

        if self.mode not in {"create", "edit"}:
            raise ValueError("Geçersiz banka form modu.")

        self.setWindowTitle("Banka Ekle" if self.mode == "create" else "Banka Düzenle")
        self.resize(560, 460)
        self.setStyleSheet(BANK_DIALOG_STYLES)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 22, 24, 22)
        main_layout.setSpacing(16)

        title_text = "Banka Ekle" if self.mode == "create" else "Banka Düzenle"
        subtitle_text = (
            "Yeni banka tanımı oluşturur."
            if self.mode == "create"
            else "Mevcut banka tanımını günceller."
        )

        title = QLabel(title_text)
        title.setObjectName("SectionTitle")

        subtitle = QLabel(subtitle_text)
        subtitle.setObjectName("MutedText")
        subtitle.setWordWrap(True)

        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        form_layout.setHorizontalSpacing(18)
        form_layout.setVerticalSpacing(14)

        self.name_input = QLineEdit()
        self.name_input.setMinimumHeight(42)
        self.name_input.setPlaceholderText("Örn: Garanti Bankası")
        form_layout.addRow("Banka adı", self.name_input)

        self.short_name_input = QLineEdit()
        self.short_name_input.setMinimumHeight(42)
        self.short_name_input.setPlaceholderText("Örn: Garanti")
        form_layout.addRow("Kısa ad", self.short_name_input)

        self.notes_input = QTextEdit()
        self.notes_input.setFixedHeight(110)
        self.notes_input.setPlaceholderText("İsteğe bağlı not")
        form_layout.addRow("Not", self.notes_input)

        self.is_active_checkbox = QCheckBox("Banka aktif")
        self.is_active_checkbox.setChecked(True)

        if self.mode == "edit":
            form_layout.addRow("Durum", self.is_active_checkbox)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)

        self.cancel_button = QPushButton("Vazgeç")
        self.save_button = QPushButton("Kaydet")

        self.cancel_button.setMinimumHeight(40)
        self.save_button.setMinimumHeight(40)

        self.cancel_button.clicked.connect(self.reject)
        self.save_button.clicked.connect(self.accept)

        button_layout.addStretch(1)
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.save_button)

        main_layout.addWidget(title)
        main_layout.addWidget(subtitle)
        main_layout.addSpacing(4)
        main_layout.addLayout(form_layout)
        main_layout.addStretch(1)
        main_layout.addLayout(button_layout)

        self._load_existing_values()

    def _load_existing_values(self) -> None:
        if self.mode != "edit" or self.bank_row is None:
            return

        self.name_input.setText(self.bank_row.name or "")
        self.short_name_input.setText(self.bank_row.short_name or "")
        self.notes_input.setPlainText(self.bank_row.notes or "")
        self.is_active_checkbox.setChecked(bool(self.bank_row.is_active))

    def _build_payload(self) -> dict[str, Any]:
        name = self.name_input.text().strip()
        short_name = self.short_name_input.text().strip()
        notes = self.notes_input.toPlainText().strip()

        if not name:
            raise ValueError("Banka adı boş olamaz.")

        payload = {
            "name": name,
            "short_name": short_name or None,
            "notes": notes or None,
            "is_active": bool(self.is_active_checkbox.isChecked()),
        }

        if self.mode == "edit":
            if self.bank_row is None:
                raise ValueError("Düzenlenecek banka bulunamadı.")

            payload["bank_id"] = self.bank_row.bank_id

        return payload

    def accept(self) -> None:
        try:
            self.payload = self._build_payload()
        except Exception as exc:
            QMessageBox.warning(self, "Eksik veya hatalı bilgi", str(exc))
            return

        super().accept()

    def get_payload(self) -> dict[str, Any]:
        if self.payload is None:
            self.payload = self._build_payload()

        return self.payload