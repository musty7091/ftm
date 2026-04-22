from datetime import date
from typing import Any

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
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

from app.models.enums import BankAccountType, CurrencyCode
from app.ui.pages.banks.bank_admin_data import AdminBankRow, bank_display_text
from app.ui.pages.banks.bank_dialog_styles import BANK_DIALOG_STYLES
from app.utils.decimal_utils import money


def _qdate_to_date_or_none(qdate: QDate, enabled: bool) -> date | None:
    if not enabled:
        return None

    return date(qdate.year(), qdate.month(), qdate.day())


class BankAccountDialog(QDialog):
    def __init__(
        self,
        *,
        parent: QWidget | None,
        mode: str,
        banks: list[AdminBankRow],
        bank_account_row: Any | None = None,
    ) -> None:
        super().__init__(parent)

        self.mode = mode
        self.banks = banks
        self.bank_account_row = bank_account_row
        self.payload: dict[str, Any] | None = None

        if self.mode not in {"create", "edit"}:
            raise ValueError("Geçersiz banka hesabı form modu.")

        self.setWindowTitle("Banka Hesabı Ekle" if self.mode == "create" else "Banka Hesabı Düzenle")
        self.resize(680, 720)
        self.setStyleSheet(BANK_DIALOG_STYLES)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 22, 24, 22)
        main_layout.setSpacing(16)

        title_text = "Banka Hesabı Ekle" if self.mode == "create" else "Banka Hesabı Düzenle"
        subtitle_text = (
            "Seçilen bankaya yeni hesap tanımı oluşturur."
            if self.mode == "create"
            else "Mevcut banka hesabı tanımını günceller."
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

        self.bank_combo = QComboBox()
        self.bank_combo.setMinimumHeight(38)
        self._fill_bank_combo()
        form_layout.addRow("Banka", self.bank_combo)

        self.account_name_input = QLineEdit()
        self.account_name_input.setMinimumHeight(42)
        self.account_name_input.setPlaceholderText("Örn: TL Vadesiz Hesap")
        form_layout.addRow("Hesap adı", self.account_name_input)

        self.account_type_combo = QComboBox()
        self.account_type_combo.setMinimumHeight(38)
        self._fill_account_type_combo()
        form_layout.addRow("Hesap türü", self.account_type_combo)

        self.currency_combo = QComboBox()
        self.currency_combo.setMinimumHeight(38)
        self._fill_currency_combo()
        form_layout.addRow("Para birimi", self.currency_combo)

        self.iban_input = QLineEdit()
        self.iban_input.setMinimumHeight(42)
        self.iban_input.setPlaceholderText("İsteğe bağlı IBAN")
        form_layout.addRow("IBAN", self.iban_input)

        self.branch_name_input = QLineEdit()
        self.branch_name_input.setMinimumHeight(42)
        self.branch_name_input.setPlaceholderText("Şube adı")
        form_layout.addRow("Şube adı", self.branch_name_input)

        self.branch_code_input = QLineEdit()
        self.branch_code_input.setMinimumHeight(42)
        self.branch_code_input.setPlaceholderText("Şube kodu")
        form_layout.addRow("Şube kodu", self.branch_code_input)

        self.account_no_input = QLineEdit()
        self.account_no_input.setMinimumHeight(42)
        self.account_no_input.setPlaceholderText("Hesap no")
        form_layout.addRow("Hesap no", self.account_no_input)

        self.opening_balance_input = QLineEdit()
        self.opening_balance_input.setMinimumHeight(42)
        self.opening_balance_input.setPlaceholderText("Örn: 0,00")
        self.opening_balance_input.setText("0,00")
        form_layout.addRow("Açılış bakiyesi", self.opening_balance_input)

        self.opening_date_enabled_checkbox = QCheckBox("Açılış tarihi gir")
        self.opening_date_enabled_checkbox.setChecked(False)

        self.opening_date_edit = QDateEdit()
        self.opening_date_edit.setMinimumHeight(38)
        self.opening_date_edit.setCalendarPopup(True)
        self.opening_date_edit.setDisplayFormat("dd.MM.yyyy")
        self.opening_date_edit.setDate(QDate.currentDate())
        self.opening_date_edit.setEnabled(False)

        self.opening_date_enabled_checkbox.toggled.connect(self.opening_date_edit.setEnabled)

        opening_date_layout = QHBoxLayout()
        opening_date_layout.setSpacing(10)
        opening_date_layout.addWidget(self.opening_date_enabled_checkbox)
        opening_date_layout.addWidget(self.opening_date_edit)

        form_layout.addRow("Açılış tarihi", opening_date_layout)

        self.notes_input = QTextEdit()
        self.notes_input.setFixedHeight(90)
        self.notes_input.setPlaceholderText("İsteğe bağlı not")
        form_layout.addRow("Not", self.notes_input)

        self.is_active_checkbox = QCheckBox("Hesap aktif")
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

    def _fill_bank_combo(self) -> None:
        self.bank_combo.clear()

        for bank in self.banks:
            self.bank_combo.addItem(bank_display_text(bank), bank.bank_id)

    def _fill_account_type_combo(self) -> None:
        self.account_type_combo.clear()

        label_map = {
            BankAccountType.CHECKING: "Vadesiz / Cari Hesap",
            BankAccountType.CHECK: "Çek Hesabı",
            BankAccountType.POS: "POS Hesabı",
            BankAccountType.CASH_DEPOSIT: "Nakit Yatırma",
            BankAccountType.SAVINGS: "Vadeli / Birikim",
            BankAccountType.OTHER: "Diğer",
        }

        for account_type in BankAccountType:
            self.account_type_combo.addItem(label_map.get(account_type, account_type.value), account_type.value)

    def _fill_currency_combo(self) -> None:
        self.currency_combo.clear()

        for currency_code in CurrencyCode:
            self.currency_combo.addItem(currency_code.value, currency_code.value)

    def _set_combo_by_data(self, combo: QComboBox, data_value: Any) -> None:
        for index in range(combo.count()):
            if str(combo.itemData(index)) == str(data_value):
                combo.setCurrentIndex(index)
                return

    def _load_existing_values(self) -> None:
        if self.mode != "edit" or self.bank_account_row is None:
            return

        self._set_combo_by_data(self.bank_combo, self.bank_account_row.bank_id)
        self.account_name_input.setText(self.bank_account_row.account_name or "")
        self._set_combo_by_data(self.account_type_combo, self.bank_account_row.account_type)
        self._set_combo_by_data(self.currency_combo, self.bank_account_row.currency_code)

        self.iban_input.setText(self.bank_account_row.iban or "")
        self.branch_name_input.setText(self.bank_account_row.branch_name or "")
        self.branch_code_input.setText(self.bank_account_row.branch_code or "")
        self.account_no_input.setText(self.bank_account_row.account_no or "")
        self.opening_balance_input.setText(str(self.bank_account_row.opening_balance or "0.00"))
        self.notes_input.setPlainText(self.bank_account_row.notes or "")
        self.is_active_checkbox.setChecked(bool(self.bank_account_row.is_active))

        if self.bank_account_row.opening_date_text:
            day, month, year = self.bank_account_row.opening_date_text.split(".")
            self.opening_date_enabled_checkbox.setChecked(True)
            self.opening_date_edit.setDate(QDate(int(year), int(month), int(day)))

    def _build_payload(self) -> dict[str, Any]:
        bank_id = self.bank_combo.currentData()

        try:
            normalized_bank_id = int(bank_id)
        except (TypeError, ValueError) as exc:
            raise ValueError("Geçerli bir banka seçilmelidir.") from exc

        account_name = self.account_name_input.text().strip()

        if not account_name:
            raise ValueError("Hesap adı boş olamaz.")

        opening_balance_text = self.opening_balance_input.text().strip() or "0,00"
        cleaned_opening_balance = money(opening_balance_text, field_name="Açılış bakiyesi")

        payload = {
            "bank_id": normalized_bank_id,
            "account_name": account_name,
            "account_type": str(self.account_type_combo.currentData()),
            "currency_code": str(self.currency_combo.currentData()),
            "iban": self.iban_input.text().strip() or None,
            "branch_name": self.branch_name_input.text().strip() or None,
            "branch_code": self.branch_code_input.text().strip() or None,
            "account_no": self.account_no_input.text().strip() or None,
            "opening_balance": cleaned_opening_balance,
            "opening_date": _qdate_to_date_or_none(
                self.opening_date_edit.date(),
                self.opening_date_enabled_checkbox.isChecked(),
            ),
            "notes": self.notes_input.toPlainText().strip() or None,
            "is_active": bool(self.is_active_checkbox.isChecked()),
        }

        if self.mode == "edit":
            if self.bank_account_row is None:
                raise ValueError("Düzenlenecek banka hesabı bulunamadı.")

            payload["bank_account_id"] = self.bank_account_row.bank_account_id

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