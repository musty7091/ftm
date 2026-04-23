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
from app.models.enums import BusinessPartnerType, IssuedCheckStatus
from app.ui.pages.banks.bank_dialog_styles import BANK_DIALOG_STYLES
from app.utils.decimal_utils import money


@dataclass
class IssuedCheckSupplierOption:
    partner_id: int
    name: str


@dataclass
class IssuedCheckBankAccountOption:
    bank_account_id: int
    bank_name: str
    account_name: str
    currency_code: str


def _qdate_to_date(qdate: QDate) -> date:
    return date(qdate.year(), qdate.month(), qdate.day())


class IssuedCheckCreateDialog(QDialog):
    def __init__(self, *, parent: QWidget | None) -> None:
        super().__init__(parent)

        self.suppliers = self._load_suppliers()
        self.bank_accounts = self._load_bank_accounts()

        self.supplier_lookup = {
            supplier.partner_id: supplier
            for supplier in self.suppliers
        }
        self.bank_account_lookup = {
            bank_account.bank_account_id: bank_account
            for bank_account in self.bank_accounts
        }
        self.payload: dict[str, Any] | None = None

        self.setWindowTitle("Yazılan Çek Oluştur")
        self.resize(640, 640)
        self.setStyleSheet(BANK_DIALOG_STYLES)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 22, 24, 22)
        main_layout.setSpacing(16)

        title = QLabel("Yazılan Çek Oluştur")
        title.setObjectName("SectionTitle")

        subtitle = QLabel(
            "Tedarikçiye yazılan yeni çeki sisteme kaydeder. "
            "Kayıt servis katmanındaki yetki ve audit kontrollerinden geçerek oluşturulur."
        )
        subtitle.setObjectName("MutedText")
        subtitle.setWordWrap(True)

        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        form_layout.setFormAlignment(Qt.AlignTop)
        form_layout.setHorizontalSpacing(18)
        form_layout.setVerticalSpacing(14)

        self.supplier_combo = QComboBox()
        self.supplier_combo.setMinimumHeight(38)
        self._fill_supplier_combo()
        form_layout.addRow("Tedarikçi cari", self.supplier_combo)

        self.bank_account_combo = QComboBox()
        self.bank_account_combo.setMinimumHeight(38)
        self._fill_bank_account_combo()
        self.bank_account_combo.currentIndexChanged.connect(self._update_bank_account_info_text)
        form_layout.addRow("Banka hesabı", self.bank_account_combo)

        self.bank_account_info_label = QLabel("")
        self.bank_account_info_label.setObjectName("MutedText")
        self.bank_account_info_label.setWordWrap(True)
        form_layout.addRow("", self.bank_account_info_label)

        self.check_number_input = QLineEdit()
        self.check_number_input.setMinimumHeight(42)
        self.check_number_input.setPlaceholderText("Çek numarası")
        form_layout.addRow("Çek no", self.check_number_input)

        self.issue_date_edit = QDateEdit()
        self.issue_date_edit.setMinimumHeight(38)
        self.issue_date_edit.setCalendarPopup(True)
        self.issue_date_edit.setDisplayFormat("dd.MM.yyyy")
        self.issue_date_edit.setDate(QDate.currentDate())
        form_layout.addRow("Keşide tarihi", self.issue_date_edit)

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

        self.status_combo = QComboBox()
        self.status_combo.setMinimumHeight(38)
        self.status_combo.addItem("Hazırlandı", IssuedCheckStatus.PREPARED)
        self.status_combo.addItem("Verildi", IssuedCheckStatus.GIVEN)
        form_layout.addRow("İlk durum", self.status_combo)

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

        self._update_bank_account_info_text()
        self._apply_missing_data_state()

    def _load_suppliers(self) -> list[IssuedCheckSupplierOption]:
        with session_scope() as session:
            statement = (
                select(BusinessPartner)
                .where(
                    BusinessPartner.is_active.is_(True),
                    BusinessPartner.partner_type.in_(
                        [
                            BusinessPartnerType.SUPPLIER,
                            BusinessPartnerType.BOTH,
                        ]
                    ),
                )
                .order_by(BusinessPartner.name.asc())
            )

            rows = session.execute(statement).scalars().all()

            return [
                IssuedCheckSupplierOption(
                    partner_id=partner.id,
                    name=partner.name,
                )
                for partner in rows
            ]

    def _load_bank_accounts(self) -> list[IssuedCheckBankAccountOption]:
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

            options: list[IssuedCheckBankAccountOption] = []

            for bank_account, bank in rows:
                currency_code = (
                    bank_account.currency_code.value
                    if hasattr(bank_account.currency_code, "value")
                    else str(bank_account.currency_code)
                )

                options.append(
                    IssuedCheckBankAccountOption(
                        bank_account_id=bank_account.id,
                        bank_name=bank.name,
                        account_name=bank_account.account_name,
                        currency_code=currency_code,
                    )
                )

            return options

    def _fill_supplier_combo(self) -> None:
        self.supplier_combo.clear()

        for supplier in self.suppliers:
            self.supplier_combo.addItem(supplier.name, supplier.partner_id)

    def _fill_bank_account_combo(self) -> None:
        self.bank_account_combo.clear()

        for bank_account in self.bank_accounts:
            text = (
                f"{bank_account.bank_name} / "
                f"{bank_account.account_name} / "
                f"{bank_account.currency_code}"
            )
            self.bank_account_combo.addItem(text, bank_account.bank_account_id)

    def _apply_missing_data_state(self) -> None:
        if self.has_required_data():
            self.warning_label.setText("")
            self.save_button.setEnabled(True)
            return

        self.warning_label.setText(self.get_missing_data_message())
        self.save_button.setEnabled(False)

    def has_required_data(self) -> bool:
        return bool(self.suppliers) and bool(self.bank_accounts)

    def get_missing_data_message(self) -> str:
        missing_items: list[str] = []

        if not self.suppliers:
            missing_items.append("aktif tedarikçi cari kartı")

        if not self.bank_accounts:
            missing_items.append("aktif banka hesabı")

        if not missing_items:
            return ""

        return (
            "Yazılan çek kaydı açılabilmesi için en az bir "
            + " ve ".join(missing_items)
            + " bulunmalıdır."
        )

    def _selected_supplier(self) -> IssuedCheckSupplierOption:
        supplier_id = self.supplier_combo.currentData()

        try:
            normalized_supplier_id = int(supplier_id)
        except (TypeError, ValueError) as exc:
            raise ValueError("Geçerli bir tedarikçi cari seçilmelidir.") from exc

        supplier = self.supplier_lookup.get(normalized_supplier_id)

        if supplier is None:
            raise ValueError("Seçilen tedarikçi cari bulunamadı.")

        return supplier

    def _selected_bank_account(self) -> IssuedCheckBankAccountOption:
        bank_account_id = self.bank_account_combo.currentData()

        try:
            normalized_bank_account_id = int(bank_account_id)
        except (TypeError, ValueError) as exc:
            raise ValueError("Geçerli bir banka hesabı seçilmelidir.") from exc

        bank_account = self.bank_account_lookup.get(normalized_bank_account_id)

        if bank_account is None:
            raise ValueError("Seçilen banka hesabı bulunamadı.")

        return bank_account

    def _update_bank_account_info_text(self) -> None:
        if not self.bank_accounts:
            self.bank_account_info_label.setText("Aktif banka hesabı bulunamadı.")
            return

        try:
            bank_account = self._selected_bank_account()
        except Exception:
            self.bank_account_info_label.setText("")
            return

        self.bank_account_info_label.setText(
            f"Seçili banka hesabının para birimi: {bank_account.currency_code}. "
            f"Çek kaydı bu para birimiyle oluşturulacaktır."
        )

    def _build_payload(self) -> dict[str, Any]:
        supplier = self._selected_supplier()
        bank_account = self._selected_bank_account()

        check_number = self.check_number_input.text().strip()
        if not check_number:
            raise ValueError("Çek numarası boş olamaz.")

        issue_date = _qdate_to_date(self.issue_date_edit.date())
        due_date = _qdate_to_date(self.due_date_edit.date())

        if due_date < issue_date:
            raise ValueError("Vade tarihi, keşide tarihinden önce olamaz.")

        amount_text = self.amount_input.text().strip()
        cleaned_amount = money(amount_text, field_name="Çek tutarı")

        if cleaned_amount <= 0:
            raise ValueError("Çek tutarı sıfırdan büyük olmalıdır.")

        status_value = self.status_combo.currentData()

        if isinstance(status_value, IssuedCheckStatus):
            normalized_status = status_value
        else:
            normalized_status = IssuedCheckStatus(str(status_value).strip().upper())

        reference_no = self.reference_no_input.text().strip()
        description = self.description_input.toPlainText().strip()

        return {
            "supplier_id": supplier.partner_id,
            "bank_account_id": bank_account.bank_account_id,
            "check_number": check_number,
            "issue_date": issue_date,
            "due_date": due_date,
            "amount": cleaned_amount,
            "status": normalized_status,
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