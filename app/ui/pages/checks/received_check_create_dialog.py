from dataclasses import dataclass
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
from sqlalchemy import select

from app.db.session import session_scope
from app.models.bank import Bank, BankAccount
from app.models.business_partner import BusinessPartner
from app.models.enums import BusinessPartnerType, CurrencyCode, ReceivedCheckStatus
from app.ui.pages.banks.bank_dialog_styles import BANK_DIALOG_STYLES
from app.utils.decimal_utils import money


@dataclass
class ReceivedCheckCustomerOption:
    partner_id: int
    name: str


@dataclass
class ReceivedCheckBankAccountOption:
    bank_account_id: int
    bank_name: str
    account_name: str
    currency_code: str


def _qdate_to_date(qdate: QDate) -> date:
    return date(qdate.year(), qdate.month(), qdate.day())


class ReceivedCheckCreateDialog(QDialog):
    def __init__(self, *, parent: QWidget | None) -> None:
        super().__init__(parent)

        self.customers = self._load_customers()
        self.bank_accounts = self._load_bank_accounts()

        self.customer_lookup = {
            customer.partner_id: customer
            for customer in self.customers
        }
        self.bank_account_lookup = {
            bank_account.bank_account_id: bank_account
            for bank_account in self.bank_accounts
        }
        self.payload: dict[str, Any] | None = None

        self.setWindowTitle("Alınan Çek Oluştur")
        self.resize(700, 720)
        self.setStyleSheet(BANK_DIALOG_STYLES)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 22, 24, 22)
        main_layout.setSpacing(16)

        title = QLabel("Alınan Çek Oluştur")
        title.setObjectName("SectionTitle")

        subtitle = QLabel(
            "Müşteriden alınan yeni çeki sisteme kaydeder. "
            "İlk durum, para birimi ve isteğe bağlı tahsil hesabı bilgisiyle kayıt oluşturulur."
        )
        subtitle.setObjectName("MutedText")
        subtitle.setWordWrap(True)

        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        form_layout.setFormAlignment(Qt.AlignTop)
        form_layout.setHorizontalSpacing(18)
        form_layout.setVerticalSpacing(14)

        self.customer_combo = QComboBox()
        self.customer_combo.setMinimumHeight(38)
        self._fill_customer_combo()
        form_layout.addRow("Müşteri cari", self.customer_combo)

        self.drawer_bank_name_input = QLineEdit()
        self.drawer_bank_name_input.setMinimumHeight(42)
        self.drawer_bank_name_input.setPlaceholderText("Çeki veren banka adı")
        form_layout.addRow("Keşideci banka", self.drawer_bank_name_input)

        self.drawer_branch_name_input = QLineEdit()
        self.drawer_branch_name_input.setMinimumHeight(42)
        self.drawer_branch_name_input.setPlaceholderText("İsteğe bağlı şube adı")
        form_layout.addRow("Keşideci şube", self.drawer_branch_name_input)

        self.check_number_input = QLineEdit()
        self.check_number_input.setMinimumHeight(42)
        self.check_number_input.setPlaceholderText("Çek numarası")
        form_layout.addRow("Çek no", self.check_number_input)

        self.received_date_edit = QDateEdit()
        self.received_date_edit.setMinimumHeight(38)
        self.received_date_edit.setCalendarPopup(True)
        self.received_date_edit.setDisplayFormat("dd.MM.yyyy")
        self.received_date_edit.setDate(QDate.currentDate())
        form_layout.addRow("Alınış tarihi", self.received_date_edit)

        self.due_date_edit = QDateEdit()
        self.due_date_edit.setMinimumHeight(38)
        self.due_date_edit.setCalendarPopup(True)
        self.due_date_edit.setDisplayFormat("dd.MM.yyyy")
        self.due_date_edit.setDate(QDate.currentDate().addDays(30))
        form_layout.addRow("Vade tarihi", self.due_date_edit)

        self.amount_input = QLineEdit()
        self.amount_input.setMinimumHeight(42)
        self.amount_input.setPlaceholderText("Örn: 12500,50")
        form_layout.addRow("Tutar", self.amount_input)

        self.currency_combo = QComboBox()
        self.currency_combo.setMinimumHeight(38)
        self.currency_combo.addItem("TRY", CurrencyCode.TRY)
        self.currency_combo.addItem("USD", CurrencyCode.USD)
        self.currency_combo.addItem("EUR", CurrencyCode.EUR)
        self.currency_combo.addItem("GBP", CurrencyCode.GBP)
        self.currency_combo.currentIndexChanged.connect(self._fill_collection_bank_account_combo)
        form_layout.addRow("Para birimi", self.currency_combo)

        self.status_combo = QComboBox()
        self.status_combo.setMinimumHeight(38)
        self.status_combo.addItem("Portföy", ReceivedCheckStatus.PORTFOLIO)
        self.status_combo.addItem("Bankaya Verildi", ReceivedCheckStatus.GIVEN_TO_BANK)
        self.status_combo.addItem("Tahsilde", ReceivedCheckStatus.IN_COLLECTION)
        self.status_combo.currentIndexChanged.connect(self._update_collection_bank_account_info)
        form_layout.addRow("İlk durum", self.status_combo)

        self.collection_bank_account_combo = QComboBox()
        self.collection_bank_account_combo.setMinimumHeight(38)
        self.collection_bank_account_combo.currentIndexChanged.connect(self._update_collection_bank_account_info)
        form_layout.addRow("Tahsil hesabı", self.collection_bank_account_combo)

        self.collection_bank_account_info_label = QLabel("")
        self.collection_bank_account_info_label.setObjectName("MutedText")
        self.collection_bank_account_info_label.setWordWrap(True)
        form_layout.addRow("", self.collection_bank_account_info_label)

        self.reference_no_input = QLineEdit()
        self.reference_no_input.setMinimumHeight(42)
        self.reference_no_input.setPlaceholderText("Referans / belge no")
        form_layout.addRow("Referans no", self.reference_no_input)

        self.description_input = QTextEdit()
        self.description_input.setPlaceholderText("İsteğe bağlı açıklama")
        self.description_input.setFixedHeight(110)
        form_layout.addRow("Açıklama", self.description_input)

        self.warning_label = QLabel("")
        self.warning_label.setObjectName("MutedText")
        self.warning_label.setWordWrap(True)

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
        main_layout.addWidget(self.warning_label)
        main_layout.addStretch(1)
        main_layout.addLayout(button_layout)

        self._fill_collection_bank_account_combo()
        self._apply_missing_data_state()

    def _load_customers(self) -> list[ReceivedCheckCustomerOption]:
        with session_scope() as session:
            statement = (
                select(BusinessPartner)
                .where(
                    BusinessPartner.is_active.is_(True),
                    BusinessPartner.partner_type.in_(
                        [
                            BusinessPartnerType.CUSTOMER,
                            BusinessPartnerType.BOTH,
                        ]
                    ),
                )
                .order_by(BusinessPartner.name.asc())
            )

            rows = session.execute(statement).scalars().all()

            return [
                ReceivedCheckCustomerOption(
                    partner_id=customer.id,
                    name=customer.name,
                )
                for customer in rows
            ]

    def _load_bank_accounts(self) -> list[ReceivedCheckBankAccountOption]:
        with session_scope() as session:
            statement = (
                select(BankAccount, Bank)
                .join(Bank, BankAccount.bank_id == Bank.id)
                .where(
                    BankAccount.is_active.is_(True),
                    Bank.is_active.is_(True),
                )
                .order_by(Bank.name.asc(), BankAccount.account_name.asc())
            )

            rows = session.execute(statement).all()

            options: list[ReceivedCheckBankAccountOption] = []

            for bank_account, bank in rows:
                currency_code = (
                    bank_account.currency_code.value
                    if hasattr(bank_account.currency_code, "value")
                    else str(bank_account.currency_code)
                )

                options.append(
                    ReceivedCheckBankAccountOption(
                        bank_account_id=bank_account.id,
                        bank_name=bank.name,
                        account_name=bank_account.account_name,
                        currency_code=currency_code,
                    )
                )

            return options

    def _fill_customer_combo(self) -> None:
        self.customer_combo.clear()

        for customer in self.customers:
            self.customer_combo.addItem(customer.name, customer.partner_id)

    def _selected_currency_code_text(self) -> str:
        currency_value = self.currency_combo.currentData()

        if hasattr(currency_value, "value"):
            return str(currency_value.value).strip().upper()

        return str(currency_value or "").strip().upper()

    def _fill_collection_bank_account_combo(self) -> None:
        selected_currency_code = self._selected_currency_code_text()

        self.collection_bank_account_combo.blockSignals(True)
        self.collection_bank_account_combo.clear()
        self.collection_bank_account_combo.addItem("Seçilmedi", None)

        for bank_account in self.bank_accounts:
            if bank_account.currency_code != selected_currency_code:
                continue

            text = (
                f"{bank_account.bank_name} / "
                f"{bank_account.account_name} / "
                f"{bank_account.currency_code}"
            )
            self.collection_bank_account_combo.addItem(text, bank_account.bank_account_id)

        self.collection_bank_account_combo.blockSignals(False)
        self._update_collection_bank_account_info()

    def _apply_missing_data_state(self) -> None:
        if self.has_required_data():
            self.warning_label.setText("")
            self.save_button.setEnabled(True)
            return

        self.warning_label.setText(self.get_missing_data_message())
        self.save_button.setEnabled(False)

    def has_required_data(self) -> bool:
        return bool(self.customers)

    def get_missing_data_message(self) -> str:
        if not self.customers:
            return "Alınan çek kaydı açılabilmesi için en az bir aktif müşteri cari kartı bulunmalıdır."

        return ""

    def _selected_customer(self) -> ReceivedCheckCustomerOption:
        customer_id = self.customer_combo.currentData()

        try:
            normalized_customer_id = int(customer_id)
        except (TypeError, ValueError) as exc:
            raise ValueError("Geçerli bir müşteri cari seçilmelidir.") from exc

        customer = self.customer_lookup.get(normalized_customer_id)

        if customer is None:
            raise ValueError("Seçilen müşteri cari bulunamadı.")

        return customer

    def _selected_collection_bank_account_id(self) -> int | None:
        bank_account_id = self.collection_bank_account_combo.currentData()

        if bank_account_id in {None, ""}:
            return None

        try:
            return int(bank_account_id)
        except (TypeError, ValueError) as exc:
            raise ValueError("Tahsil hesabı bilgisi okunamadı.") from exc

    def _selected_collection_bank_account(self) -> ReceivedCheckBankAccountOption | None:
        bank_account_id = self._selected_collection_bank_account_id()

        if bank_account_id is None:
            return None

        bank_account = self.bank_account_lookup.get(bank_account_id)

        if bank_account is None:
            raise ValueError("Seçilen tahsil hesabı bulunamadı.")

        return bank_account

    def _selected_status(self) -> ReceivedCheckStatus:
        status_value = self.status_combo.currentData()

        if isinstance(status_value, ReceivedCheckStatus):
            return status_value

        return ReceivedCheckStatus(str(status_value).strip().upper())

    def _selected_currency(self) -> CurrencyCode:
        currency_value = self.currency_combo.currentData()

        if isinstance(currency_value, CurrencyCode):
            return currency_value

        return CurrencyCode(str(currency_value).strip().upper())

    def _update_collection_bank_account_info(self) -> None:
        selected_status = self._selected_status()
        selected_currency_code = self._selected_currency_code_text()
        selected_bank_account = self._selected_collection_bank_account()

        if selected_bank_account is None:
            if selected_status in {ReceivedCheckStatus.GIVEN_TO_BANK, ReceivedCheckStatus.IN_COLLECTION}:
                self.collection_bank_account_info_label.setText(
                    "Bu ilk durumda tahsil hesabı seçmen önerilir. "
                    "Bankaya verildi veya tahsilde statüsü için hesap seçilmezse kayıt kabul edilmeyecektir."
                )
            else:
                self.collection_bank_account_info_label.setText(
                    f"Tahsil hesabı seçmeden portföy kaydı açabilirsin. Seçilirse hesap para birimi {selected_currency_code} olmalıdır."
                )
            return

        self.collection_bank_account_info_label.setText(
            f"Seçili tahsil hesabı: {selected_bank_account.bank_name} / "
            f"{selected_bank_account.account_name} / {selected_bank_account.currency_code}"
        )

    def _build_payload(self) -> dict[str, Any]:
        customer = self._selected_customer()

        drawer_bank_name = self.drawer_bank_name_input.text().strip()
        if not drawer_bank_name:
            raise ValueError("Keşideci banka boş olamaz.")

        drawer_branch_name = self.drawer_branch_name_input.text().strip() or None

        check_number = self.check_number_input.text().strip()
        if not check_number:
            raise ValueError("Çek numarası boş olamaz.")

        received_date = _qdate_to_date(self.received_date_edit.date())
        due_date = _qdate_to_date(self.due_date_edit.date())

        if due_date < received_date:
            raise ValueError("Vade tarihi, alınış tarihinden önce olamaz.")

        amount_text = self.amount_input.text().strip()
        cleaned_amount = money(amount_text, field_name="Çek tutarı")

        if cleaned_amount <= 0:
            raise ValueError("Çek tutarı sıfırdan büyük olmalıdır.")

        selected_currency = self._selected_currency()
        selected_status = self._selected_status()
        selected_collection_bank_account = self._selected_collection_bank_account()

        if selected_collection_bank_account is not None:
            if selected_collection_bank_account.currency_code != selected_currency.value:
                raise ValueError(
                    "Tahsil hesabının para birimi ile çekin para birimi aynı olmalıdır."
                )

        if selected_status in {ReceivedCheckStatus.GIVEN_TO_BANK, ReceivedCheckStatus.IN_COLLECTION}:
            if selected_collection_bank_account is None:
                raise ValueError(
                    "Bankaya Verildi veya Tahsilde ilk durumu için tahsil hesabı seçilmelidir."
                )

        reference_no = self.reference_no_input.text().strip() or None
        description = self.description_input.toPlainText().strip() or None

        return {
            "customer_id": customer.partner_id,
            "collection_bank_account_id": (
                selected_collection_bank_account.bank_account_id
                if selected_collection_bank_account is not None
                else None
            ),
            "drawer_bank_name": drawer_bank_name,
            "drawer_branch_name": drawer_branch_name,
            "check_number": check_number,
            "received_date": received_date,
            "due_date": due_date,
            "amount": cleaned_amount,
            "currency_code": selected_currency,
            "status": selected_status,
            "reference_no": reference_no,
            "description": description,
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