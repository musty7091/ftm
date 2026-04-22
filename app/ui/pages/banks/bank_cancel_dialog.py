from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from sqlalchemy import select
from sqlalchemy.orm import aliased

from app.db.session import session_scope
from app.models.bank import Bank, BankAccount
from app.models.bank_transaction import BankTransaction
from app.models.bank_transfer import BankTransfer
from app.models.enums import BankTransactionStatus, BankTransferStatus, FinancialSourceType
from app.ui.pages.banks.bank_dialog_styles import BANK_DIALOG_STYLES
from app.ui.ui_helpers import tr_money


@dataclass
class CancelableBankTransactionRow:
    bank_transaction_id: int
    transaction_date_text: str
    bank_name: str
    account_name: str
    direction: str
    amount: Any
    currency_code: str
    source_type: str
    reference_no: str | None
    description: str | None


@dataclass
class CancelableBankTransferRow:
    bank_transfer_id: int
    transfer_date_text: str
    from_bank_name: str
    from_account_name: str
    to_bank_name: str
    to_account_name: str
    amount: Any
    currency_code: str
    status: str
    reference_no: str | None
    description: str | None


def _format_amount(value: Any, currency_code: str) -> str:
    if currency_code == "TRY":
        return tr_money(value)

    return f"{value} {currency_code}"


def _direction_text(direction: Any) -> str:
    direction_value = direction.value if hasattr(direction, "value") else str(direction)

    if direction_value == "IN":
        return "Giriş"

    if direction_value == "OUT":
        return "Çıkış"

    return direction_value


def _status_text(status: Any) -> str:
    status_value = status.value if hasattr(status, "value") else str(status)

    if status_value == "REALIZED":
        return "Gerçekleşti"

    if status_value == "PLANNED":
        return "Planlandı"

    if status_value == "CANCELLED":
        return "İptal"

    return status_value


def load_cancelable_bank_transactions() -> list[CancelableBankTransactionRow]:
    with session_scope() as session:
        statement = (
            select(BankTransaction, BankAccount, Bank)
            .join(BankAccount, BankTransaction.bank_account_id == BankAccount.id)
            .join(Bank, BankAccount.bank_id == Bank.id)
            .where(BankTransaction.status != BankTransactionStatus.CANCELLED)
            .where(BankTransaction.source_type != FinancialSourceType.BANK_TRANSFER)
            .order_by(BankTransaction.transaction_date.desc(), BankTransaction.id.desc())
            .limit(200)
        )

        rows = session.execute(statement).all()

        cancelable_rows: list[CancelableBankTransactionRow] = []

        for bank_transaction, bank_account, bank in rows:
            currency_code = (
                bank_transaction.currency_code.value
                if hasattr(bank_transaction.currency_code, "value")
                else str(bank_transaction.currency_code)
            )

            source_type = (
                bank_transaction.source_type.value
                if hasattr(bank_transaction.source_type, "value")
                else str(bank_transaction.source_type)
            )

            cancelable_rows.append(
                CancelableBankTransactionRow(
                    bank_transaction_id=bank_transaction.id,
                    transaction_date_text=bank_transaction.transaction_date.strftime("%d.%m.%Y"),
                    bank_name=bank.name,
                    account_name=bank_account.account_name,
                    direction=_direction_text(bank_transaction.direction),
                    amount=bank_transaction.amount,
                    currency_code=currency_code,
                    source_type=source_type,
                    reference_no=bank_transaction.reference_no,
                    description=bank_transaction.description,
                )
            )

        return cancelable_rows


def load_cancelable_bank_transfers() -> list[CancelableBankTransferRow]:
    from_bank_account = aliased(BankAccount)
    to_bank_account = aliased(BankAccount)
    from_bank = aliased(Bank)
    to_bank = aliased(Bank)

    with session_scope() as session:
        statement = (
            select(
                BankTransfer,
                from_bank_account,
                to_bank_account,
                from_bank,
                to_bank,
            )
            .join(
                from_bank_account,
                BankTransfer.from_bank_account_id == from_bank_account.id,
            )
            .join(
                to_bank_account,
                BankTransfer.to_bank_account_id == to_bank_account.id,
            )
            .join(
                from_bank,
                from_bank_account.bank_id == from_bank.id,
            )
            .join(
                to_bank,
                to_bank_account.bank_id == to_bank.id,
            )
            .where(BankTransfer.status != BankTransferStatus.CANCELLED)
            .order_by(BankTransfer.transfer_date.desc(), BankTransfer.id.desc())
            .limit(200)
        )

        rows = session.execute(statement).all()

        cancelable_rows: list[CancelableBankTransferRow] = []

        for transfer, source_account, target_account, source_bank, target_bank in rows:
            currency_code = (
                transfer.currency_code.value
                if hasattr(transfer.currency_code, "value")
                else str(transfer.currency_code)
            )

            status = (
                transfer.status.value
                if hasattr(transfer.status, "value")
                else str(transfer.status)
            )

            cancelable_rows.append(
                CancelableBankTransferRow(
                    bank_transfer_id=transfer.id,
                    transfer_date_text=transfer.transfer_date.strftime("%d.%m.%Y"),
                    from_bank_name=source_bank.name,
                    from_account_name=source_account.account_name,
                    to_bank_name=target_bank.name,
                    to_account_name=target_account.account_name,
                    amount=transfer.amount,
                    currency_code=currency_code,
                    status=status,
                    reference_no=transfer.reference_no,
                    description=transfer.description,
                )
            )

        return cancelable_rows


class BankCancelDialog(QDialog):
    def __init__(
        self,
        *,
        parent: QWidget | None,
    ) -> None:
        super().__init__(parent)

        self.cancelable_transactions = load_cancelable_bank_transactions()
        self.cancelable_transfers = load_cancelable_bank_transfers()
        self.payload: dict[str, Any] | None = None

        self.setWindowTitle("İptal İşlemleri")
        self.resize(760, 560)
        self.setStyleSheet(BANK_DIALOG_STYLES)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 22, 24, 22)
        main_layout.setSpacing(16)

        title = QLabel("İptal İşlemleri")
        title.setObjectName("SectionTitle")

        subtitle = QLabel(
            "Manuel banka hareketlerini veya banka transferlerini iptal eder. "
            "Transfer iptalinde bağlı giriş ve çıkış hareketleri birlikte iptal edilir."
        )
        subtitle.setObjectName("MutedText")
        subtitle.setWordWrap(True)

        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        form_layout.setFormAlignment(Qt.AlignTop)
        form_layout.setHorizontalSpacing(18)
        form_layout.setVerticalSpacing(14)

        self.operation_type_combo = QComboBox()
        self.operation_type_combo.setMinimumHeight(38)
        self.operation_type_combo.addItem("Banka Hareketi İptal Et", "BANK_TRANSACTION")
        self.operation_type_combo.addItem("Banka Transferi İptal Et", "BANK_TRANSFER")
        self.operation_type_combo.currentIndexChanged.connect(self._refresh_target_combo)
        form_layout.addRow("İşlem türü", self.operation_type_combo)

        self.target_combo = QComboBox()
        self.target_combo.setMinimumHeight(38)
        form_layout.addRow("İptal edilecek kayıt", self.target_combo)

        self.reason_input = QTextEdit()
        self.reason_input.setPlaceholderText("İptal nedenini yazın. Örn: Hatalı tutar girildi.")
        self.reason_input.setFixedHeight(110)
        form_layout.addRow("İptal nedeni", self.reason_input)

        self.info_label = QLabel("")
        self.info_label.setObjectName("MutedText")
        self.info_label.setWordWrap(True)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)

        self.cancel_button = QPushButton("Vazgeç")
        self.save_button = QPushButton("İptal Et")

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
        main_layout.addWidget(self.info_label)
        main_layout.addStretch(1)
        main_layout.addLayout(button_layout)

        self._refresh_target_combo()

    def _transaction_display_text(self, row: CancelableBankTransactionRow) -> str:
        amount_text = _format_amount(row.amount, row.currency_code)
        reference_text = f" / Ref: {row.reference_no}" if row.reference_no else ""

        return (
            f"#{row.bank_transaction_id} / "
            f"{row.transaction_date_text} / "
            f"{row.bank_name} - {row.account_name} / "
            f"{row.direction} / "
            f"{amount_text}"
            f"{reference_text}"
        )

    def _transfer_display_text(self, row: CancelableBankTransferRow) -> str:
        amount_text = _format_amount(row.amount, row.currency_code)
        status_text = _status_text(row.status)
        reference_text = f" / Ref: {row.reference_no}" if row.reference_no else ""

        return (
            f"#{row.bank_transfer_id} / "
            f"{row.transfer_date_text} / "
            f"{row.from_bank_name} - {row.from_account_name} → "
            f"{row.to_bank_name} - {row.to_account_name} / "
            f"{amount_text} / "
            f"{status_text}"
            f"{reference_text}"
        )

    def _refresh_target_combo(self) -> None:
        self.target_combo.clear()

        operation_type = self.operation_type_combo.currentData()

        if operation_type == "BANK_TRANSACTION":
            for row in self.cancelable_transactions:
                self.target_combo.addItem(
                    self._transaction_display_text(row),
                    row.bank_transaction_id,
                )

            has_rows = len(self.cancelable_transactions) > 0
            self.target_combo.setEnabled(has_rows)
            self.save_button.setEnabled(has_rows)

            if has_rows:
                self.info_label.setText(
                    "Listede sadece transfer kaynaklı olmayan ve henüz iptal edilmemiş banka hareketleri görünür."
                )
            else:
                self.info_label.setText(
                    "İptal edilebilir manuel banka hareketi bulunamadı."
                )

            return

        if operation_type == "BANK_TRANSFER":
            for row in self.cancelable_transfers:
                self.target_combo.addItem(
                    self._transfer_display_text(row),
                    row.bank_transfer_id,
                )

            has_rows = len(self.cancelable_transfers) > 0
            self.target_combo.setEnabled(has_rows)
            self.save_button.setEnabled(has_rows)

            if has_rows:
                self.info_label.setText(
                    "Transfer iptal edilirse bağlı banka giriş ve çıkış hareketleri de birlikte iptal edilir."
                )
            else:
                self.info_label.setText(
                    "İptal edilebilir banka transferi bulunamadı."
                )

            return

        self.target_combo.setEnabled(False)
        self.save_button.setEnabled(False)
        self.info_label.setText("Geçerli bir işlem türü seçilmelidir.")

    def _build_payload(self) -> dict[str, Any]:
        operation_type = str(self.operation_type_combo.currentData() or "").strip()

        if operation_type not in {"BANK_TRANSACTION", "BANK_TRANSFER"}:
            raise ValueError("Geçerli bir işlem türü seçilmelidir.")

        entity_id = self.target_combo.currentData()

        try:
            normalized_entity_id = int(entity_id)
        except (TypeError, ValueError) as exc:
            raise ValueError("İptal edilecek geçerli bir kayıt seçilmelidir.") from exc

        cancel_reason = self.reason_input.toPlainText().strip()

        if not cancel_reason:
            raise ValueError("İptal nedeni boş olamaz.")

        if len(cancel_reason) < 5:
            raise ValueError("İptal nedeni daha açıklayıcı olmalıdır.")

        return {
            "operation_type": operation_type,
            "entity_id": normalized_entity_id,
            "cancel_reason": cancel_reason,
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