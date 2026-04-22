from datetime import date
from typing import Any

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
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

from app.models.enums import BankTransactionStatus, FinancialSourceType, TransactionDirection
from app.ui.pages.banks.bank_dialog_styles import BANK_DIALOG_STYLES
from app.ui.ui_helpers import decimal_or_zero, tr_money
from app.utils.decimal_utils import money


def _format_currency_amount(value: Any, currency_code: str) -> str:
    if currency_code == "TRY":
        return tr_money(value)

    return f"{value} {currency_code}"


def _qdate_to_date(qdate: QDate) -> date:
    return date(qdate.year(), qdate.month(), qdate.day())


class BankTransactionDialog(QDialog):
    def __init__(
        self,
        *,
        parent: QWidget | None,
        bank_accounts: list[Any],
    ) -> None:
        super().__init__(parent)

        self.bank_accounts = bank_accounts
        self.account_lookup = {
            bank_account.bank_account_id: bank_account
            for bank_account in self.bank_accounts
        }
        self.payload: dict[str, Any] | None = None

        self.setWindowTitle("Banka Hareketi Oluştur")
        self.resize(600, 560)
        self.setStyleSheet(BANK_DIALOG_STYLES)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 22, 24, 22)
        main_layout.setSpacing(16)

        title = QLabel("Banka Hareketi Oluştur")
        title.setObjectName("SectionTitle")

        subtitle = QLabel(
            "Seçilen banka hesabına giriş veya çıkış hareketi ekler. "
            "Kayıt mevcut yetki ve audit sistemi üzerinden oluşturulur."
        )
        subtitle.setObjectName("MutedText")
        subtitle.setWordWrap(True)

        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        form_layout.setFormAlignment(Qt.AlignTop)
        form_layout.setHorizontalSpacing(18)
        form_layout.setVerticalSpacing(14)

        self.account_combo = QComboBox()
        self.account_combo.setMinimumHeight(38)
        self._fill_account_combo()
        form_layout.addRow("Banka hesabı", self.account_combo)

        self.direction_combo = QComboBox()
        self.direction_combo.setMinimumHeight(38)
        self.direction_combo.addItem("Giriş / Tahsilat", TransactionDirection.IN.value)
        self.direction_combo.addItem("Çıkış / Ödeme", TransactionDirection.OUT.value)
        form_layout.addRow("Hareket yönü", self.direction_combo)

        self.status_combo = QComboBox()
        self.status_combo.setMinimumHeight(38)
        self.status_combo.addItem("Gerçekleşti", BankTransactionStatus.REALIZED.value)
        self.status_combo.addItem("Planlandı", BankTransactionStatus.PLANNED.value)
        form_layout.addRow("Durum", self.status_combo)

        self.transaction_date_edit = QDateEdit()
        self.transaction_date_edit.setMinimumHeight(38)
        self.transaction_date_edit.setCalendarPopup(True)
        self.transaction_date_edit.setDisplayFormat("dd.MM.yyyy")
        self.transaction_date_edit.setDate(QDate.currentDate())
        form_layout.addRow("İşlem tarihi", self.transaction_date_edit)

        self.amount_input = QLineEdit()
        self.amount_input.setMinimumHeight(42)
        self.amount_input.setPlaceholderText("Örn: 12500,50")
        form_layout.addRow("Tutar", self.amount_input)

        self.reference_no_input = QLineEdit()
        self.reference_no_input.setMinimumHeight(42)
        self.reference_no_input.setPlaceholderText("Dekont / fiş / açıklama no")
        form_layout.addRow("Referans no", self.reference_no_input)

        self.description_input = QTextEdit()
        self.description_input.setPlaceholderText("İsteğe bağlı açıklama")
        self.description_input.setFixedHeight(105)
        form_layout.addRow("Açıklama", self.description_input)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)

        self.save_button = QPushButton("Kaydet")
        self.cancel_button = QPushButton("Vazgeç")

        self.save_button.setMinimumHeight(40)
        self.cancel_button.setMinimumHeight(40)

        self.save_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)

        button_layout.addStretch(1)
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.save_button)

        main_layout.addWidget(title)
        main_layout.addWidget(subtitle)
        main_layout.addSpacing(4)
        main_layout.addLayout(form_layout)
        main_layout.addStretch(1)
        main_layout.addLayout(button_layout)

    def _fill_account_combo(self) -> None:
        self.account_combo.clear()

        for bank_account in self.bank_accounts:
            balance_text = _format_currency_amount(
                bank_account.current_balance,
                bank_account.currency_code,
            )

            text = (
                f"{bank_account.bank_name} / "
                f"{bank_account.account_name} / "
                f"{bank_account.currency_code} / "
                f"Güncel: {balance_text}"
            )

            self.account_combo.addItem(text, bank_account.bank_account_id)

    def _selected_bank_account(self) -> Any:
        bank_account_id = self.account_combo.currentData()

        try:
            normalized_bank_account_id = int(bank_account_id)
        except (TypeError, ValueError) as exc:
            raise ValueError("Geçerli bir banka hesabı seçilmelidir.") from exc

        bank_account = self.account_lookup.get(normalized_bank_account_id)

        if bank_account is None:
            raise ValueError("Seçilen banka hesabı bulunamadı.")

        return bank_account

    def _build_payload(self) -> dict[str, Any]:
        bank_account = self._selected_bank_account()

        amount_text = self.amount_input.text().strip()
        cleaned_amount = money(amount_text, field_name="Banka hareket tutarı")

        if cleaned_amount <= decimal_or_zero("0.00"):
            raise ValueError("Banka hareket tutarı sıfırdan büyük olmalıdır.")

        direction_value = str(self.direction_combo.currentData()).strip().upper()
        status_value = str(self.status_combo.currentData()).strip().upper()

        reference_no = self.reference_no_input.text().strip()
        description = self.description_input.toPlainText().strip()

        return {
            "bank_account_id": bank_account.bank_account_id,
            "transaction_date": _qdate_to_date(self.transaction_date_edit.date()),
            "value_date": None,
            "direction": direction_value,
            "status": status_value,
            "amount": cleaned_amount,
            "currency_code": bank_account.currency_code,
            "source_type": FinancialSourceType.MANUAL_ADJUSTMENT.value,
            "source_id": None,
            "reference_no": reference_no or None,
            "description": description or None,
        }

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