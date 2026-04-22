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

from app.models.enums import BankTransferStatus
from app.ui.pages.banks.bank_dialog_styles import BANK_DIALOG_STYLES
from app.ui.ui_helpers import decimal_or_zero, tr_money
from app.utils.decimal_utils import money


def _format_currency_amount(value: Any, currency_code: str) -> str:
    if currency_code == "TRY":
        return tr_money(value)

    return f"{value} {currency_code}"


def _qdate_to_date(qdate: QDate) -> date:
    return date(qdate.year(), qdate.month(), qdate.day())


class BankTransferDialog(QDialog):
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

        self.setWindowTitle("Banka Transferi Oluştur")
        self.resize(640, 600)
        self.setStyleSheet(BANK_DIALOG_STYLES)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 22, 24, 22)
        main_layout.setSpacing(16)

        title = QLabel("Banka Transferi Oluştur")
        title.setObjectName("SectionTitle")

        subtitle = QLabel(
            "Aynı para birimindeki iki aktif banka hesabı arasında transfer oluşturur. "
            "Gerçekleşti durumundaki transferler çıkış ve giriş hareketlerini otomatik üretir."
        )
        subtitle.setObjectName("MutedText")
        subtitle.setWordWrap(True)

        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        form_layout.setFormAlignment(Qt.AlignTop)
        form_layout.setHorizontalSpacing(18)
        form_layout.setVerticalSpacing(14)

        self.from_account_combo = QComboBox()
        self.from_account_combo.setMinimumHeight(38)
        self._fill_from_account_combo()
        self.from_account_combo.currentIndexChanged.connect(self._refresh_to_account_combo)
        form_layout.addRow("Çıkış hesabı", self.from_account_combo)

        self.to_account_combo = QComboBox()
        self.to_account_combo.setMinimumHeight(38)
        form_layout.addRow("Giriş hesabı", self.to_account_combo)

        self.status_combo = QComboBox()
        self.status_combo.setMinimumHeight(38)
        self.status_combo.addItem("Gerçekleşti", BankTransferStatus.REALIZED)
        self.status_combo.addItem("Planlandı", BankTransferStatus.PLANNED)
        form_layout.addRow("Durum", self.status_combo)

        self.transfer_date_edit = QDateEdit()
        self.transfer_date_edit.setMinimumHeight(38)
        self.transfer_date_edit.setCalendarPopup(True)
        self.transfer_date_edit.setDisplayFormat("dd.MM.yyyy")
        self.transfer_date_edit.setDate(QDate.currentDate())
        form_layout.addRow("Transfer tarihi", self.transfer_date_edit)

        self.amount_input = QLineEdit()
        self.amount_input.setMinimumHeight(42)
        self.amount_input.setPlaceholderText("Örn: 5000,00")
        form_layout.addRow("Tutar", self.amount_input)

        self.reference_no_input = QLineEdit()
        self.reference_no_input.setMinimumHeight(42)
        self.reference_no_input.setPlaceholderText("Dekont / EFT / havale no")
        form_layout.addRow("Referans no", self.reference_no_input)

        self.description_input = QTextEdit()
        self.description_input.setPlaceholderText("İsteğe bağlı açıklama")
        self.description_input.setFixedHeight(105)
        form_layout.addRow("Açıklama", self.description_input)

        self.info_label = QLabel("")
        self.info_label.setObjectName("MutedText")
        self.info_label.setWordWrap(True)

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
        main_layout.addWidget(self.info_label)
        main_layout.addStretch(1)
        main_layout.addLayout(button_layout)

        self._refresh_to_account_combo()

    def _account_display_text(self, bank_account: Any) -> str:
        balance_text = _format_currency_amount(
            bank_account.current_balance,
            bank_account.currency_code,
        )

        return (
            f"{bank_account.bank_name} / "
            f"{bank_account.account_name} / "
            f"{bank_account.currency_code} / "
            f"Güncel: {balance_text}"
        )

    def _fill_from_account_combo(self) -> None:
        self.from_account_combo.clear()

        for bank_account in self.bank_accounts:
            self.from_account_combo.addItem(
                self._account_display_text(bank_account),
                bank_account.bank_account_id,
            )

    def _selected_from_bank_account(self) -> Any:
        bank_account_id = self.from_account_combo.currentData()

        try:
            normalized_bank_account_id = int(bank_account_id)
        except (TypeError, ValueError) as exc:
            raise ValueError("Geçerli bir çıkış hesabı seçilmelidir.") from exc

        bank_account = self.account_lookup.get(normalized_bank_account_id)

        if bank_account is None:
            raise ValueError("Seçilen çıkış hesabı bulunamadı.")

        return bank_account

    def _selected_to_bank_account(self) -> Any:
        bank_account_id = self.to_account_combo.currentData()

        try:
            normalized_bank_account_id = int(bank_account_id)
        except (TypeError, ValueError) as exc:
            raise ValueError("Geçerli bir giriş hesabı seçilmelidir.") from exc

        bank_account = self.account_lookup.get(normalized_bank_account_id)

        if bank_account is None:
            raise ValueError("Seçilen giriş hesabı bulunamadı.")

        return bank_account

    def _refresh_to_account_combo(self) -> None:
        self.to_account_combo.clear()

        try:
            from_bank_account = self._selected_from_bank_account()
        except Exception:
            self.to_account_combo.setEnabled(False)
            self.info_label.setText("Önce geçerli bir çıkış hesabı seçilmelidir.")
            return

        matching_target_accounts = [
            bank_account
            for bank_account in self.bank_accounts
            if bank_account.bank_account_id != from_bank_account.bank_account_id
            and bank_account.currency_code == from_bank_account.currency_code
        ]

        for bank_account in matching_target_accounts:
            self.to_account_combo.addItem(
                self._account_display_text(bank_account),
                bank_account.bank_account_id,
            )

        has_target_account = len(matching_target_accounts) > 0
        self.to_account_combo.setEnabled(has_target_account)
        self.save_button.setEnabled(has_target_account)

        if has_target_account:
            self.info_label.setText(
                f"Sadece {from_bank_account.currency_code} para birimindeki farklı hesaplar listelenir."
            )
        else:
            self.info_label.setText(
                "Seçilen çıkış hesabıyla aynı para biriminde başka aktif hesap bulunamadı."
            )

    def _build_payload(self) -> dict[str, Any]:
        from_bank_account = self._selected_from_bank_account()
        to_bank_account = self._selected_to_bank_account()

        if from_bank_account.bank_account_id == to_bank_account.bank_account_id:
            raise ValueError("Aynı banka hesabı içinde transfer yapılamaz.")

        if from_bank_account.currency_code != to_bank_account.currency_code:
            raise ValueError("Transfer yapılacak hesapların para birimi aynı olmalıdır.")

        amount_text = self.amount_input.text().strip()
        cleaned_amount = money(amount_text, field_name="Transfer tutarı")

        if cleaned_amount <= decimal_or_zero("0.00"):
            raise ValueError("Transfer tutarı sıfırdan büyük olmalıdır.")

        status_value = self.status_combo.currentData()

        if not isinstance(status_value, BankTransferStatus):
            status_value = BankTransferStatus(str(status_value).strip().upper())

        reference_no = self.reference_no_input.text().strip()
        description = self.description_input.toPlainText().strip()

        return {
            "from_bank_account_id": from_bank_account.bank_account_id,
            "to_bank_account_id": to_bank_account.bank_account_id,
            "transfer_date": _qdate_to_date(self.transfer_date_edit.date()),
            "value_date": None,
            "amount": cleaned_amount,
            "status": status_value,
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