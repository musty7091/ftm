from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
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

from app.models.enums import CurrencyCode
from app.ui.pages.banks.bank_dialog_styles import BANK_DIALOG_STYLES
from app.ui.pages.pos.pos_admin_data import (
    AdminPosBankAccountRow,
    pos_bank_account_display_text,
)


class PosDeviceDialog(QDialog):
    def __init__(
        self,
        *,
        parent: QWidget | None,
        mode: str,
        bank_accounts: list[AdminPosBankAccountRow],
        pos_device_row: Any | None = None,
    ) -> None:
        super().__init__(parent)

        self.mode = mode
        self.bank_accounts = bank_accounts
        self.pos_device_row = pos_device_row
        self.payload: dict[str, Any] | None = None

        if self.mode not in {"create", "edit"}:
            raise ValueError("Geçersiz POS cihaz form modu.")

        self.setWindowTitle("POS Cihazı Ekle" if self.mode == "create" else "POS Cihazı Düzenle")
        self.resize(680, 660)
        self.setStyleSheet(BANK_DIALOG_STYLES)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 22, 24, 22)
        main_layout.setSpacing(16)

        title_text = "POS Cihazı Ekle" if self.mode == "create" else "POS Cihazı Düzenle"
        subtitle_text = (
            "Seçilen banka hesabına yeni POS cihazı tanımı oluşturur."
            if self.mode == "create"
            else "Mevcut POS cihazı tanımını günceller."
        )

        title = QLabel(title_text)
        title.setObjectName("SectionTitle")

        subtitle = QLabel(subtitle_text)
        subtitle.setObjectName("MutedText")
        subtitle.setWordWrap(True)

        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        form_layout.setHorizontalSpacing(18)
        form_layout.setVerticalSpacing(12)

        self.bank_account_combo = QComboBox()
        self.bank_account_combo.setMinimumHeight(38)
        self._fill_bank_account_combo()
        self.bank_account_combo.currentIndexChanged.connect(self._sync_currency_with_account)
        form_layout.addRow("Banka hesabı", self.bank_account_combo)

        self.name_input = QLineEdit()
        self.name_input.setMinimumHeight(42)
        self.name_input.setPlaceholderText("Örn: Garanti POS")
        form_layout.addRow("POS cihaz adı", self.name_input)

        self.terminal_no_input = QLineEdit()
        self.terminal_no_input.setMinimumHeight(42)
        self.terminal_no_input.setPlaceholderText("Örn: 1251212")
        form_layout.addRow("Terminal no", self.terminal_no_input)

        self.commission_rate_input = QLineEdit()
        self.commission_rate_input.setMinimumHeight(42)
        self.commission_rate_input.setPlaceholderText("Örn: 1,99")
        form_layout.addRow("Komisyon oranı (%)", self.commission_rate_input)

        self.settlement_delay_days_input = QSpinBox()
        self.settlement_delay_days_input.setMinimumHeight(38)
        self.settlement_delay_days_input.setMinimum(0)
        self.settlement_delay_days_input.setMaximum(60)
        self.settlement_delay_days_input.setValue(1)
        form_layout.addRow("Valör gün", self.settlement_delay_days_input)

        self.currency_combo = QComboBox()
        self.currency_combo.setMinimumHeight(38)
        self._fill_currency_combo()
        self.currency_combo.setEnabled(False)
        form_layout.addRow("Para birimi", self.currency_combo)

        self.currency_info_label = QLabel(
            "POS cihazı para birimi, seçilen banka hesabının para birimi ile aynı tutulur."
        )
        self.currency_info_label.setObjectName("MutedText")
        self.currency_info_label.setWordWrap(True)
        form_layout.addRow("", self.currency_info_label)

        self.notes_input = QTextEdit()
        self.notes_input.setFixedHeight(110)
        self.notes_input.setPlaceholderText("İsteğe bağlı not")
        form_layout.addRow("Not", self.notes_input)

        self.is_active_checkbox = QCheckBox("POS cihazı aktif")
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
        self._sync_currency_with_account()

    def _fill_bank_account_combo(self) -> None:
        self.bank_account_combo.clear()

        for bank_account in self.bank_accounts:
            self.bank_account_combo.addItem(
                pos_bank_account_display_text(bank_account),
                bank_account.bank_account_id,
            )

    def _fill_currency_combo(self) -> None:
        self.currency_combo.clear()

        for currency_code in CurrencyCode:
            self.currency_combo.addItem(currency_code.value, currency_code.value)

    def _set_combo_by_data(self, combo: QComboBox, data_value: Any) -> None:
        for index in range(combo.count()):
            if str(combo.itemData(index)) == str(data_value):
                combo.setCurrentIndex(index)
                return

    def _find_bank_account_by_id(self, bank_account_id: Any) -> AdminPosBankAccountRow | None:
        try:
            normalized_bank_account_id = int(bank_account_id)
        except (TypeError, ValueError):
            return None

        for bank_account in self.bank_accounts:
            if bank_account.bank_account_id == normalized_bank_account_id:
                return bank_account

        return None

    def _sync_currency_with_account(self) -> None:
        selected_bank_account = self._find_bank_account_by_id(
            self.bank_account_combo.currentData()
        )

        if selected_bank_account is None:
            return

        self._set_combo_by_data(
            self.currency_combo,
            selected_bank_account.currency_code,
        )

    def _load_existing_values(self) -> None:
        if self.mode != "edit" or self.pos_device_row is None:
            return

        self._set_combo_by_data(
            self.bank_account_combo,
            self.pos_device_row.bank_account_id,
        )

        self.name_input.setText(self.pos_device_row.name or "")
        self.terminal_no_input.setText(self.pos_device_row.terminal_no or "")

        commission_rate_text = str(self.pos_device_row.commission_rate or "0.00")
        commission_rate_text = commission_rate_text.replace(".", ",")
        self.commission_rate_input.setText(commission_rate_text)

        self.settlement_delay_days_input.setValue(
            int(self.pos_device_row.settlement_delay_days or 0)
        )

        self._set_combo_by_data(
            self.currency_combo,
            self.pos_device_row.currency_code,
        )

        self.notes_input.setPlainText(self.pos_device_row.notes or "")
        self.is_active_checkbox.setChecked(bool(self.pos_device_row.is_active))

    def _build_payload(self) -> dict[str, Any]:
        bank_account_id = self.bank_account_combo.currentData()

        try:
            normalized_bank_account_id = int(bank_account_id)
        except (TypeError, ValueError) as exc:
            raise ValueError("Geçerli bir banka hesabı seçilmelidir.") from exc

        selected_bank_account = self._find_bank_account_by_id(normalized_bank_account_id)

        if selected_bank_account is None:
            raise ValueError("Seçilen banka hesabı bulunamadı.")

        name = self.name_input.text().strip()

        if not name:
            raise ValueError("POS cihaz adı boş olamaz.")

        commission_rate_text = self.commission_rate_input.text().strip()

        if not commission_rate_text:
            raise ValueError("Komisyon oranı boş olamaz.")

        payload = {
            "bank_account_id": normalized_bank_account_id,
            "name": name,
            "terminal_no": self.terminal_no_input.text().strip() or None,
            "commission_rate": commission_rate_text,
            "settlement_delay_days": int(self.settlement_delay_days_input.value()),
            "currency_code": selected_bank_account.currency_code,
            "notes": self.notes_input.toPlainText().strip() or None,
            "is_active": bool(self.is_active_checkbox.isChecked()),
        }

        if self.mode == "edit":
            if self.pos_device_row is None:
                raise ValueError("Düzenlenecek POS cihazı bulunamadı.")

            payload["pos_device_id"] = self.pos_device_row.pos_device_id

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