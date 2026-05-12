from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from sqlalchemy import select

from app.db.session import session_scope
from app.models.bank import BankAccount
from app.models.credit_facility import BankAccountCreditLimit
from app.services.credit_facility_service import (
    CreditFacilityServiceError,
    create_credit_limit_payment_transaction,
    create_credit_limit_usage_transaction,
    get_credit_limit_debt_summary,
)
from app.ui.components.no_wheel_widgets import (
    NoWheelComboBox,
    NoWheelDateEdit,
    NoWheelDoubleSpinBox,
)


CREDIT_LIMIT_TRANSACTION_DIALOG_STYLE = """
QDialog {
    background-color: #0f172a;
    color: #e5e7eb;
}

QWidget#CreditLimitTransactionWrapper,
QWidget#CreditLimitTransactionFormBody {
    background-color: #0f172a;
}

QScrollArea#CreditLimitTransactionScrollArea {
    background-color: #0f172a;
    border: none;
}

QScrollArea#CreditLimitTransactionScrollArea > QWidget,
QScrollArea#CreditLimitTransactionScrollArea > QWidget > QWidget {
    background-color: #0f172a;
}

QLabel#DialogTitle {
    color: #ffffff;
    font-size: 20px;
    font-weight: 900;
}

QLabel#DialogSubtitle,
QLabel#DialogHelp,
QLabel#DialogWarning {
    color: #94a3b8;
    font-size: 12px;
}

QLabel#DialogWarning {
    color: #fbbf24;
    font-weight: 800;
}

QLabel#FormLabel {
    color: #dbeafe;
    font-size: 12px;
    font-weight: 900;
    background-color: transparent;
    padding-right: 8px;
}

QLineEdit,
QTextEdit,
QComboBox,
QDateEdit,
QDoubleSpinBox {
    background-color: #111827;
    color: #e5e7eb;
    border: 1px solid #334155;
    border-radius: 9px;
    padding: 8px 10px;
    min-height: 28px;
}

QLineEdit:focus,
QTextEdit:focus,
QComboBox:focus,
QDateEdit:focus,
QDoubleSpinBox:focus {
    border: 1px solid #3b82f6;
}

QLineEdit:disabled,
QTextEdit:disabled,
QComboBox:disabled,
QDateEdit:disabled,
QDoubleSpinBox:disabled {
    background-color: rgba(30, 41, 59, 0.55);
    color: #94a3b8;
    border: 1px solid rgba(100, 116, 139, 0.32);
}

QComboBox::drop-down,
QDateEdit::drop-down,
QDoubleSpinBox::up-button,
QDoubleSpinBox::down-button {
    background-color: #0f172a;
    border-left: 1px solid #334155;
    width: 24px;
}

QComboBox QAbstractItemView {
    background-color: #111827;
    color: #e5e7eb;
    selection-background-color: #2563eb;
    selection-color: #ffffff;
    border: 1px solid #334155;
}

QCheckBox {
    color: #e5e7eb;
    font-size: 12px;
    spacing: 8px;
    background-color: transparent;
}

QCalendarWidget QWidget {
    background-color: #111827;
    color: #e5e7eb;
}

QCalendarWidget QToolButton {
    background-color: #1f2937;
    color: #f8fafc;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 5px;
    margin: 2px;
}

QCalendarWidget QToolButton:hover {
    background-color: #2563eb;
}

QCalendarWidget QMenu {
    background-color: #111827;
    color: #e5e7eb;
    border: 1px solid #334155;
}

QCalendarWidget QSpinBox {
    background-color: #111827;
    color: #e5e7eb;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 4px;
}

QCalendarWidget QAbstractItemView:enabled {
    background-color: #0f172a;
    color: #e5e7eb;
    selection-background-color: #2563eb;
    selection-color: #ffffff;
}

QCalendarWidget QAbstractItemView:disabled {
    color: #64748b;
}

QPushButton#PrimaryButton {
    background-color: #2563eb;
    color: #ffffff;
    border: 1px solid #3b82f6;
    border-radius: 10px;
    padding: 8px 16px;
    font-weight: 900;
}

QPushButton#PrimaryButton:hover {
    background-color: #1d4ed8;
}

QPushButton#SecondaryButton {
    background-color: #172033;
    color: #cbd5e1;
    border: 1px solid #24324a;
    border-radius: 10px;
    padding: 8px 16px;
    font-weight: 900;
}

QPushButton#SecondaryButton:hover {
    background-color: #1e293b;
    color: #ffffff;
}

QPushButton:disabled {
    background-color: rgba(30, 41, 59, 0.55);
    color: #64748b;
    border: 1px solid rgba(100, 116, 139, 0.32);
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


class CreditLimitTransactionDialog(QDialog):
    MODE_USAGE = "usage"
    MODE_PAYMENT = "payment"

    def __init__(
        self,
        *,
        current_user: Any | None = None,
        credit_limit_id: int,
        mode: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        clean_mode = str(mode or "").strip().lower()
        if clean_mode not in {self.MODE_USAGE, self.MODE_PAYMENT}:
            raise ValueError("Limit hareket modu 'usage' veya 'payment' olmalıdır.")

        self.current_user = current_user
        self.credit_limit_id = int(credit_limit_id)
        self.mode = clean_mode

        self._credit_limit_data: dict[str, Any] = {}
        self._payment_accounts: list[dict[str, Any]] = []
        self._summary: dict[str, Any] = {}

        self.setWindowTitle("Limit Kullan" if self.is_usage_mode else "Limit Öde")
        self.resize(720, 560)
        self.setMinimumSize(620, 500)
        self.setSizeGripEnabled(True)
        self.setStyleSheet(CREDIT_LIMIT_TRANSACTION_DIALOG_STYLE)

        self.title_label = QLabel("Limit Kullan" if self.is_usage_mode else "Limit Öde")
        self.title_label.setObjectName("DialogTitle")

        self.subtitle_label = QLabel()
        self.subtitle_label.setObjectName("DialogSubtitle")
        self.subtitle_label.setWordWrap(True)

        self.limit_info_input = QLineEdit()
        self.limit_info_input.setReadOnly(True)

        self.limit_amount_input = QLineEdit()
        self.limit_amount_input.setReadOnly(True)

        self.current_debt_input = QLineEdit()
        self.current_debt_input.setReadOnly(True)

        self.payable_principal_debt_input = QLineEdit()
        self.payable_principal_debt_input.setReadOnly(True)

        self.interest_debt_input = QLineEdit()
        self.interest_debt_input.setReadOnly(True)

        self.fee_debt_input = QLineEdit()
        self.fee_debt_input.setReadOnly(True)

        self.total_payable_debt_input = QLineEdit()
        self.total_payable_debt_input.setReadOnly(True)

        self.available_limit_input = QLineEdit()
        self.available_limit_input.setReadOnly(True)

        self.fee_allocation_input = QLineEdit()
        self.fee_allocation_input.setReadOnly(True)

        self.interest_allocation_input = QLineEdit()
        self.interest_allocation_input.setReadOnly(True)

        self.principal_allocation_input = QLineEdit()
        self.principal_allocation_input.setReadOnly(True)

        self.allocation_summary_input = QLineEdit()
        self.allocation_summary_input.setReadOnly(True)

        self.transaction_date_input = NoWheelDateEdit()
        self.transaction_date_input.setCalendarPopup(True)
        self.transaction_date_input.setDisplayFormat("dd.MM.yyyy")
        self.transaction_date_input.setDate(QDate.currentDate())
        self.transaction_date_input.dateChanged.connect(self._update_effective_date_preview)

        self.effective_date_input = QLineEdit()
        self.effective_date_input.setReadOnly(True)

        self.payment_account_combo = NoWheelComboBox()
        self.payment_account_combo.setInsertPolicy(NoWheelComboBox.NoInsert)

        self.amount_input = NoWheelDoubleSpinBox()
        self.amount_input.setDecimals(2)
        self.amount_input.setMinimum(0.00)
        self.amount_input.setMaximum(999999999999.99)
        self.amount_input.setSingleStep(1000.00)
        self.amount_input.setGroupSeparatorShown(True)
        self.amount_input.valueChanged.connect(self._update_payment_allocation_preview)

        self.currency_input = QLineEdit()
        self.currency_input.setReadOnly(True)

        self.create_bank_entry_checkbox = QCheckBox("Bağlı banka hesabına para girişi oluştur")
        self.create_bank_entry_checkbox.setChecked(True)

        self.reference_no_input = QLineEdit()
        self.reference_no_input.setPlaceholderText("Dekont / referans no")

        self.description_input = QLineEdit()
        self.description_input.setPlaceholderText("Kısa açıklama")

        self.notes_input = QTextEdit()
        self.notes_input.setPlaceholderText("Not")
        self.notes_input.setFixedHeight(88)

        self.warning_label = QLabel()
        self.warning_label.setObjectName("DialogWarning")
        self.warning_label.setWordWrap(True)

        self.save_button = QPushButton("Kullanımı Kaydet" if self.is_usage_mode else "Ödemeyi Kaydet")
        self.save_button.setObjectName("PrimaryButton")
        self.save_button.clicked.connect(self._save)

        self.cancel_button = QPushButton("Vazgeç")
        self.cancel_button.setObjectName("SecondaryButton")
        self.cancel_button.clicked.connect(self.reject)

        self._build_ui()
        self._apply_mode_text()
        self._load_reference_data()
        self._populate_form()

    @property
    def is_usage_mode(self) -> bool:
        return self.mode == self.MODE_USAGE

    @property
    def is_payment_mode(self) -> bool:
        return self.mode == self.MODE_PAYMENT

    def _apply_mode_text(self) -> None:
        if self.is_usage_mode:
            self.subtitle_label.setText(
                "Seçili kredili / limitli hesaptan kullanım kaydı oluşturur. "
                "Limit kullanımı aynı gün faize etki eder. İstersen bağlı banka hesabına aynı tutarda giriş hareketi de oluşturulur."
            )
            self.warning_label.setText(
                "Kural: Limit kullanımı işlem tarihinde borca eklenir ve aynı gün faiz hesabına girer."
            )
            return

        self.subtitle_label.setText(
            "Seçili kredili / limitli hesap için ödeme kaydı oluşturur. "
            "Sistem ödemeyi otomatik olarak önce masraf, sonra faiz, en son ana para borcuna dağıtır."
        )
        self.warning_label.setText(
            "Bilgi: Ödeme banka hesabından işlem tarihinde çıkar. Ana paraya ayrılan bölüm faiz hesabında ertesi gün düşer."
        )

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(22, 20, 22, 18)
        root_layout.setSpacing(12)

        scroll_area = QScrollArea()
        scroll_area.setObjectName("CreditLimitTransactionScrollArea")
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        wrapper = QWidget()
        wrapper.setObjectName("CreditLimitTransactionWrapper")

        wrapper_layout = QVBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(0, 8, 8, 8)
        wrapper_layout.setSpacing(10)

        form_body = QWidget()
        form_body.setObjectName("CreditLimitTransactionFormBody")

        form_layout = QFormLayout(form_body)
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setHorizontalSpacing(16)
        form_layout.setVerticalSpacing(10)
        form_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

        form_layout.addRow(self._label("Limit Hesabı"), self.limit_info_input)

        if self.is_usage_mode:
            form_layout.addRow(self._label("Limit Tutarı"), self.limit_amount_input)
            form_layout.addRow(self._label("Kullanılabilir Limit"), self.available_limit_input)
            form_layout.addRow(self._label("İşlem Tarihi"), self.transaction_date_input)
            form_layout.addRow(self._label("Faize Etki Tarihi"), self.effective_date_input)
            form_layout.addRow(self._label("Kullanım Tutarı"), self.amount_input)
            form_layout.addRow(self._label("Para Birimi"), self.currency_input)
            form_layout.addRow(self._label("Banka Hareketi"), self.create_bank_entry_checkbox)
        else:
            form_layout.addRow(self._label("Toplam Ödenecek"), self.total_payable_debt_input)
            form_layout.addRow(self._label("Ödeme Tutarı"), self.amount_input)
            form_layout.addRow(self._label("Ödeme Hesabı"), self.payment_account_combo)
            form_layout.addRow(self._label("İşlem Tarihi"), self.transaction_date_input)
            form_layout.addRow(self._label("Para Birimi"), self.currency_input)
            form_layout.addRow(self._label("Dağılım Özeti"), self.allocation_summary_input)

        form_layout.addRow(self._label("Referans No"), self.reference_no_input)
        form_layout.addRow(self._label("Açıklama"), self.description_input)
        form_layout.addRow(self._label("Not"), self.notes_input)

        help_label = QLabel(
            "Not: Tarih, tutar ve hesap seçimi alanlarında mouse tekerleği yanlışlıkla değer değiştirmez."
        )
        help_label.setObjectName("DialogHelp")
        help_label.setWordWrap(True)

        wrapper_layout.addWidget(form_body)
        wrapper_layout.addWidget(self.warning_label)
        wrapper_layout.addWidget(help_label)
        wrapper_layout.addStretch(1)

        scroll_area.setWidget(wrapper)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        button_layout.addStretch(1)
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.save_button)

        root_layout.addWidget(self.title_label)
        root_layout.addWidget(self.subtitle_label)
        root_layout.addWidget(scroll_area, 1)
        root_layout.addLayout(button_layout)

    def _label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("FormLabel")
        label.setMinimumWidth(168)
        return label

    def _load_reference_data(self) -> None:
        self._credit_limit_data = {}
        self._payment_accounts = []
        self._summary = {}

        try:
            with session_scope() as session:
                credit_limit = session.get(BankAccountCreditLimit, self.credit_limit_id)

                if credit_limit is None:
                    raise CreditFacilityServiceError(
                        f"Kredili / limitli hesap bulunamadı. ID: {self.credit_limit_id}"
                    )

                bank_account = credit_limit.bank_account
                bank_name = "-"
                account_name = "-"

                if bank_account is not None:
                    account_name = bank_account.account_name or "-"
                    if getattr(bank_account, "bank", None) is not None:
                        bank_name = bank_account.bank.name or "-"

                currency_code = credit_limit.currency_code.value
                self._summary = get_credit_limit_debt_summary(
                    session,
                    credit_limit_id=int(credit_limit.id),
                )

                self._credit_limit_data = {
                    "id": int(credit_limit.id),
                    "limit_name": credit_limit.limit_name,
                    "bank_account_id": int(credit_limit.bank_account_id),
                    "bank_name": bank_name,
                    "account_name": account_name,
                    "currency_code": currency_code,
                    "limit_amount": Decimal(credit_limit.limit_amount or 0),
                    "is_active": bool(credit_limit.is_active),
                }

                if self.is_payment_mode:
                    accounts = session.execute(
                        select(BankAccount)
                        .where(
                            BankAccount.is_active.is_(True),
                            BankAccount.currency_code == credit_limit.currency_code,
                        )
                        .order_by(BankAccount.account_name.asc())
                    ).scalars().all()

                    self._payment_accounts = [
                        {
                            "id": int(account.id),
                            "bank_name": account.bank.name if account.bank else "-",
                            "account_name": account.account_name,
                            "currency_code": account.currency_code.value,
                        }
                        for account in accounts
                    ]

        except Exception as exc:
            QMessageBox.critical(
                self,
                "Limit Bilgisi Yüklenemedi",
                f"Kredili / limitli hesap bilgisi yüklenirken hata oluştu:\n\n{exc}",
            )
            self.reject()

    def _populate_form(self) -> None:
        if not self._credit_limit_data:
            self.save_button.setEnabled(False)
            return

        currency_code = str(self._credit_limit_data.get("currency_code") or "-")
        limit_label = (
            f"{self._credit_limit_data.get('bank_name', '-')} / "
            f"{self._credit_limit_data.get('account_name', '-')} / "
            f"{self._credit_limit_data.get('limit_name', '-')}"
        )
        self.limit_info_input.setText(limit_label)
        self.limit_amount_input.setText(
            self._format_money(self._summary.get("limit_amount", Decimal("0.00")), currency_code)
        )

        faize_esas_borc = self._decimal_from_summary("principal_debt")
        odenebilir_ana_para = self._decimal_from_summary("booked_principal_debt")
        faiz_borcu = self._decimal_from_summary("booked_interest_debt")
        masraf_borcu = self._decimal_from_summary("booked_fee_debt")
        toplam_odenecek_borc = self._decimal_from_summary("booked_total_debt")
        kullanilabilir_limit = self._decimal_from_summary("available_limit")

        self.current_debt_input.setText(self._format_money(faize_esas_borc, currency_code))
        self.payable_principal_debt_input.setText(self._format_money(odenebilir_ana_para, currency_code))
        self.interest_debt_input.setText(self._format_money(faiz_borcu, currency_code))
        self.fee_debt_input.setText(self._format_money(masraf_borcu, currency_code))
        self.total_payable_debt_input.setText(self._format_money(toplam_odenecek_borc, currency_code))
        self.available_limit_input.setText(self._format_money(kullanilabilir_limit, currency_code))
        self.currency_input.setText(currency_code)

        maximum_amount = Decimal("0.00")
        if self.is_usage_mode:
            maximum_amount = kullanilabilir_limit
        else:
            maximum_amount = toplam_odenecek_borc
            self._populate_payment_account_combo()

        if self.is_payment_mode and maximum_amount > Decimal("0.00"):
            self.warning_label.setText(
                "Bilgi: Ödeme otomatik dağıtılır. Önce masraf, sonra faiz, kalan varsa ana para kapanır."
            )

        if maximum_amount <= Decimal("0.00"):
            self.amount_input.setMaximum(0.00)
            self.amount_input.setValue(0.00)
            self.save_button.setEnabled(False)
            if self.is_usage_mode:
                self.warning_label.setText(
                    "Bu limitte kullanılabilir tutar bulunmuyor. Yeni kullanım kaydı oluşturulamaz."
                )
            else:
                self.warning_label.setText(
                    "Bu limitli hesapta ödenecek borç bulunmuyor. Ödeme kaydı oluşturulamaz."
                )
        else:
            self.amount_input.setMaximum(float(maximum_amount))
            self.amount_input.setValue(float(maximum_amount))
            self.save_button.setEnabled(True)

        self._update_payment_allocation_preview()

        if self.is_payment_mode and self.payment_account_combo.count() <= 0:
            self.save_button.setEnabled(False)

        self._update_effective_date_preview()

    def _populate_payment_account_combo(self) -> None:
        self.payment_account_combo.clear()

        if not self._payment_accounts:
            self.payment_account_combo.addItem("Uygun aktif ödeme hesabı bulunamadı", None)
            self.payment_account_combo.setEnabled(False)
            self.save_button.setEnabled(False)
            return

        self.payment_account_combo.setEnabled(True)

        linked_account_id = int(self._credit_limit_data.get("bank_account_id") or 0)
        preferred_index = 0

        for index, account in enumerate(self._payment_accounts):
            label = f"{account['bank_name']} / {account['account_name']} ({account['currency_code']})"
            self.payment_account_combo.addItem(label, int(account["id"]))

            if int(account["id"]) == linked_account_id:
                preferred_index = index

        self.payment_account_combo.setCurrentIndex(preferred_index)

    def _decimal_from_summary(self, key: str) -> Decimal:
        try:
            return Decimal(str(self._summary.get(key, Decimal("0.00")) or Decimal("0.00")))
        except Exception:
            return Decimal("0.00")

    def _calculate_payment_allocation_preview(self, payment_amount: Decimal) -> dict[str, Decimal]:
        remaining_amount = max(payment_amount, Decimal("0.00"))
        fee_debt = self._decimal_from_summary("booked_fee_debt")
        interest_debt = self._decimal_from_summary("booked_interest_debt")
        principal_debt = self._decimal_from_summary("booked_principal_debt")

        fee_amount = min(remaining_amount, fee_debt)
        remaining_amount = max(remaining_amount - fee_amount, Decimal("0.00"))

        interest_amount = min(remaining_amount, interest_debt)
        remaining_amount = max(remaining_amount - interest_amount, Decimal("0.00"))

        principal_amount = min(remaining_amount, principal_debt)

        return {
            "fee_amount": fee_amount,
            "interest_amount": interest_amount,
            "principal_amount": principal_amount,
        }

    def _update_payment_allocation_preview(self) -> None:
        if not self.is_payment_mode:
            return

        currency_code = str(self._credit_limit_data.get("currency_code") or "-")
        amount = Decimal(str(self.amount_input.value()))
        allocation = self._calculate_payment_allocation_preview(amount)

        self.fee_allocation_input.setText(
            self._format_money(allocation["fee_amount"], currency_code)
        )
        self.interest_allocation_input.setText(
            self._format_money(allocation["interest_amount"], currency_code)
        )
        self.principal_allocation_input.setText(
            self._format_money(allocation["principal_amount"], currency_code)
        )

        parts = []
        if allocation["fee_amount"] > Decimal("0.00"):
            parts.append(f"Masraf: {self._format_money(allocation['fee_amount'], currency_code)}")
        if allocation["interest_amount"] > Decimal("0.00"):
            parts.append(f"Faiz: {self._format_money(allocation['interest_amount'], currency_code)}")
        if allocation["principal_amount"] > Decimal("0.00"):
            parts.append(f"Ana para: {self._format_money(allocation['principal_amount'], currency_code)}")

        if not parts:
            self.allocation_summary_input.setText("Ödenecek tutar yok")
        else:
            self.allocation_summary_input.setText(" | ".join(parts))

    def _selected_payment_account_id(self) -> int | None:
        if not self.is_payment_mode:
            return None

        value = self.payment_account_combo.currentData()
        if value is None:
            return None

        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _current_user_id(self) -> int | None:
        if self.current_user is None:
            return None

        user_id = getattr(self.current_user, "id", None)

        if user_id is None:
            return None

        try:
            return int(user_id)
        except (TypeError, ValueError):
            return None

    def _selected_transaction_date(self) -> date:
        qdate = self.transaction_date_input.date()
        return date(qdate.year(), qdate.month(), qdate.day())

    def _effective_date_for_preview(self) -> date:
        transaction_date = self._selected_transaction_date()

        if self.is_payment_mode:
            return transaction_date + timedelta(days=1)

        return transaction_date

    def _update_effective_date_preview(self) -> None:
        effective_date = self._effective_date_for_preview()
        self.effective_date_input.setText(self._format_date(effective_date))

    def _save(self) -> None:
        if not self._credit_limit_data:
            QMessageBox.warning(self, "Eksik Bilgi", "Limit bilgisi yüklenemedi.")
            return

        amount = Decimal(str(self.amount_input.value()))

        if amount <= Decimal("0.00"):
            QMessageBox.warning(
                self,
                "Eksik Bilgi",
                "Tutar sıfırdan büyük olmalıdır.",
            )
            return

        if self.is_payment_mode and self._selected_payment_account_id() is None:
            QMessageBox.warning(
                self,
                "Eksik Bilgi",
                "Ödeme hesabı seçilmelidir.",
            )
            return

        try:
            with session_scope() as session:
                if self.is_usage_mode:
                    create_credit_limit_usage_transaction(
                        session,
                        credit_limit_id=self.credit_limit_id,
                        transaction_date=self._selected_transaction_date(),
                        amount=amount,
                        reference_no=self.reference_no_input.text(),
                        description=self.description_input.text(),
                        notes=self.notes_input.toPlainText(),
                        create_bank_account_entry=self.create_bank_entry_checkbox.isChecked(),
                        created_by_user_id=self._current_user_id(),
                    )
                else:
                    payment_account_id = self._selected_payment_account_id()
                    if payment_account_id is None:
                        raise CreditFacilityServiceError("Ödeme hesabı seçilmelidir.")

                    create_credit_limit_payment_transaction(
                        session,
                        credit_limit_id=self.credit_limit_id,
                        payment_bank_account_id=payment_account_id,
                        transaction_date=self._selected_transaction_date(),
                        amount=amount,
                        reference_no=self.reference_no_input.text(),
                        description=self.description_input.text(),
                        notes=self.notes_input.toPlainText(),
                        created_by_user_id=self._current_user_id(),
                    )

        except CreditFacilityServiceError as exc:
            QMessageBox.warning(
                self,
                "Limit Hareketi Kaydedilemedi",
                str(exc),
            )
            return

        except Exception as exc:
            QMessageBox.critical(
                self,
                "Beklenmeyen Hata",
                f"Limit hareketi kaydedilirken beklenmeyen hata oluştu:\n\n{exc}",
            )
            return

        QMessageBox.information(
            self,
            "Limit Hareketi Kaydedildi",
            "Limit kullanım kaydı başarıyla oluşturuldu."
            if self.is_usage_mode
            else "Limit ödeme kaydı başarıyla oluşturuldu.",
        )
        self.accept()

    def _format_money(self, value: Any, currency_code: str) -> str:
        try:
            amount = Decimal(str(value or "0"))
        except Exception:
            amount = Decimal("0.00")

        formatted = f"{amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"{formatted} {currency_code}"

    def _format_date(self, value: date) -> str:
        return value.strftime("%d.%m.%Y")


__all__ = [
    "CreditLimitTransactionDialog",
]
