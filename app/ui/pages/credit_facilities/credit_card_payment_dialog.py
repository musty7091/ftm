from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
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
from sqlalchemy.orm import joinedload

from app.db.session import session_scope
from app.models.bank import BankAccount
from app.models.credit_facility import CreditCard
from app.models.enums import CurrencyCode
from app.services.credit_facility_service import (
    CreditFacilityServiceError,
    create_credit_card_payment,
    get_credit_card_debt_summary,
)
from app.ui.components.no_wheel_widgets import (
    NoWheelComboBox,
    NoWheelDateEdit,
    NoWheelDoubleSpinBox,
)


CREDIT_CARD_PAYMENT_DIALOG_STYLE = """
QDialog {
    background-color: #0f172a;
    color: #e5e7eb;
}

QWidget#PaymentDialogWrapper,
QWidget#PaymentDialogFormBody {
    background-color: #0f172a;
}

QScrollArea#PaymentDialogScrollArea {
    background-color: #0f172a;
    border: none;
}

QScrollArea#PaymentDialogScrollArea > QWidget,
QScrollArea#PaymentDialogScrollArea > QWidget > QWidget {
    background-color: #0f172a;
}

QLabel#DialogTitle {
    color: #ffffff;
    font-size: 20px;
    font-weight: 900;
}

QLabel#DialogSubtitle,
QLabel#DialogHelp {
    color: #94a3b8;
    font-size: 12px;
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
QDateEdit,
QComboBox,
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
QDateEdit:focus,
QComboBox:focus,
QDoubleSpinBox:focus {
    border: 1px solid #3b82f6;
}

QLineEdit:disabled,
QTextEdit:disabled,
QDateEdit:disabled,
QComboBox:disabled,
QDoubleSpinBox:disabled {
    background-color: rgba(30, 41, 59, 0.55);
    color: #94a3b8;
    border: 1px solid rgba(100, 116, 139, 0.32);
}

QLineEdit[readOnly="true"] {
    background-color: rgba(30, 41, 59, 0.72);
    color: #cbd5e1;
}

QComboBox::drop-down {
    border: none;
    width: 28px;
}

QComboBox QAbstractItemView {
    background-color: #111827;
    color: #e5e7eb;
    selection-background-color: #2563eb;
    selection-color: #ffffff;
    border: 1px solid #334155;
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


class CreditCardPaymentDialog(QDialog):
    def __init__(
        self,
        *,
        current_user: Any | None = None,
        credit_card_id: int,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.current_user = current_user
        self.credit_card_id = int(credit_card_id)
        self.credit_card_name = ""
        self.remaining_debt = Decimal("0.00")
        self.payment_accounts: list[dict[str, Any]] = []

        self.setWindowTitle("Kredi Kartı Ödemesi Gir")
        self.resize(720, 520)
        self.setMinimumSize(620, 460)
        self.setSizeGripEnabled(True)
        self.setStyleSheet(CREDIT_CARD_PAYMENT_DIALOG_STYLE)

        self.card_info_input = QLineEdit()
        self.card_info_input.setReadOnly(True)

        self.remaining_debt_input = QLineEdit()
        self.remaining_debt_input.setReadOnly(True)

        self.payment_bank_account_combo = NoWheelComboBox()
        self.payment_bank_account_combo.setInsertPolicy(NoWheelComboBox.NoInsert)

        self.payment_date_input = NoWheelDateEdit()
        self.payment_date_input.setCalendarPopup(True)
        self.payment_date_input.setDisplayFormat("dd.MM.yyyy")
        self.payment_date_input.setDate(QDate.currentDate())

        self.amount_input = NoWheelDoubleSpinBox()
        self.amount_input.setDecimals(2)
        self.amount_input.setMinimum(0.00)
        self.amount_input.setMaximum(999999999999.99)
        self.amount_input.setSingleStep(100.00)
        self.amount_input.setGroupSeparatorShown(True)

        self.currency_input = QLineEdit()
        self.currency_input.setReadOnly(True)
        self.currency_input.setText("TRY / TL")

        self.reference_no_input = QLineEdit()
        self.reference_no_input.setPlaceholderText("Dekont / referans no")

        self.notes_input = QTextEdit()
        self.notes_input.setPlaceholderText("Not")
        self.notes_input.setFixedHeight(90)

        self.save_button = QPushButton("Ödemeyi Kaydet")
        self.save_button.setObjectName("PrimaryButton")
        self.save_button.clicked.connect(self._save)

        self.cancel_button = QPushButton("Vazgeç")
        self.cancel_button.setObjectName("SecondaryButton")
        self.cancel_button.clicked.connect(self.reject)

        self._build_ui()
        self._load_payment_data()

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(22, 20, 22, 18)
        root_layout.setSpacing(12)

        title = QLabel("Kredi Kartı Ödemesi Gir")
        title.setObjectName("DialogTitle")

        subtitle = QLabel(
            "Seçili kredi kartının kalan borcuna ödeme kaydı ekler. "
            "Ödeme sadece TL banka hesabından yapılır ve banka hesabında gerçekleşmiş çıkış hareketi oluşturur."
        )
        subtitle.setObjectName("DialogSubtitle")
        subtitle.setWordWrap(True)

        scroll_area = QScrollArea()
        scroll_area.setObjectName("PaymentDialogScrollArea")
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        wrapper = QWidget()
        wrapper.setObjectName("PaymentDialogWrapper")

        wrapper_layout = QVBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(0, 8, 8, 8)
        wrapper_layout.setSpacing(10)

        form_body = QWidget()
        form_body.setObjectName("PaymentDialogFormBody")

        form_layout = QFormLayout(form_body)
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setHorizontalSpacing(16)
        form_layout.setVerticalSpacing(10)
        form_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

        form_layout.addRow(self._label("Kart"), self.card_info_input)
        form_layout.addRow(self._label("Ödenecek Kart Borcu"), self.remaining_debt_input)
        form_layout.addRow(self._label("Ödeme Hesabı"), self.payment_bank_account_combo)
        form_layout.addRow(self._label("Ödeme Tarihi"), self.payment_date_input)
        form_layout.addRow(self._label("Ödeme Tutarı"), self.amount_input)
        form_layout.addRow(self._label("Para Birimi"), self.currency_input)
        form_layout.addRow(self._label("Referans No"), self.reference_no_input)
        form_layout.addRow(self._label("Not"), self.notes_input)

        help_label = QLabel(
            "Not: Bu ekranda sadece seçili kartın ödenecek kalan borcu gösterilir. "
            "Ödeme tutarı mevcut kredi kartı borcundan büyük olamaz. "
            "Tarih, tutar ve hesap seçimi alanlarında mouse tekerleği yanlışlıkla değer değiştirmez."
        )
        help_label.setObjectName("DialogHelp")
        help_label.setWordWrap(True)

        wrapper_layout.addWidget(form_body)
        wrapper_layout.addWidget(help_label)
        wrapper_layout.addStretch(1)

        scroll_area.setWidget(wrapper)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        button_layout.addStretch(1)
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.save_button)

        root_layout.addWidget(title)
        root_layout.addWidget(subtitle)
        root_layout.addWidget(scroll_area, 1)
        root_layout.addLayout(button_layout)

    def _label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("FormLabel")
        label.setMinimumWidth(150)
        return label

    def _load_payment_data(self) -> None:
        try:
            with session_scope() as session:
                credit_card = session.get(CreditCard, self.credit_card_id)

                if credit_card is None:
                    raise CreditFacilityServiceError(
                        f"Kredi kartı bulunamadı. Kredi kartı ID: {self.credit_card_id}"
                    )

                debt_summary = get_credit_card_debt_summary(
                    session,
                    credit_card_id=credit_card.id,
                )

                payment_accounts = session.execute(
                    select(BankAccount)
                    .options(joinedload(BankAccount.bank))
                    .where(BankAccount.is_active.is_(True))
                    .where(BankAccount.currency_code == CurrencyCode.TRY)
                    .order_by(BankAccount.account_name.asc())
                ).scalars().all()

                bank_name = credit_card.bank.name if credit_card.bank else "-"
                self.credit_card_name = credit_card.card_name
                self.remaining_debt = Decimal(debt_summary["remaining_debt"] or Decimal("0.00"))

                self.payment_accounts = [
                    {
                        "id": account.id,
                        "bank_name": account.bank.name if account.bank else "-",
                        "account_name": account.account_name,
                        "currency_code": account.currency_code.value,
                    }
                    for account in payment_accounts
                ]

                form_data = {
                    "card_info": f"{bank_name} / {credit_card.card_name}",
                    "remaining_debt": debt_summary["remaining_debt"],
                }

        except Exception as exc:
            QMessageBox.critical(
                self,
                "Ödeme Bilgisi Yüklenemedi",
                f"Kredi kartı ödeme bilgileri yüklenirken hata oluştu:\n\n{exc}",
            )
            self.reject()
            return

        self.card_info_input.setText(str(form_data["card_info"]))
        self.remaining_debt_input.setText(f"{self._format_decimal(form_data['remaining_debt'])} TL")

        self._populate_payment_account_combo()
        self._configure_amount_input()
        self._update_save_state()

    def _populate_payment_account_combo(self) -> None:
        self.payment_bank_account_combo.clear()

        if not self.payment_accounts:
            self.payment_bank_account_combo.addItem("Aktif TL banka hesabı bulunamadı", None)
            self.payment_bank_account_combo.setEnabled(False)
            return

        self.payment_bank_account_combo.setEnabled(True)

        for account in self.payment_accounts:
            label = (
                f"{account['bank_name']} / {account['account_name']} "
                f"({account['currency_code']})"
            )
            self.payment_bank_account_combo.addItem(label, int(account["id"]))

    def _configure_amount_input(self) -> None:
        if self.remaining_debt <= Decimal("0.00"):
            self.amount_input.setMinimum(0.00)
            self.amount_input.setMaximum(0.00)
            self.amount_input.setValue(0.00)
            self.amount_input.setEnabled(False)
            return

        maximum_value = float(self.remaining_debt)
        self.amount_input.setEnabled(True)
        self.amount_input.setMinimum(0.01)
        self.amount_input.setMaximum(maximum_value)
        self.amount_input.setValue(maximum_value)

    def _update_save_state(self) -> None:
        can_save = bool(self.payment_accounts) and self.remaining_debt > Decimal("0.00")
        self.save_button.setEnabled(can_save)

        if self.remaining_debt <= Decimal("0.00"):
            self.save_button.setToolTip("Bu kredi kartı için ödenecek borç bulunmuyor.")
            return

        if not self.payment_accounts:
            self.save_button.setToolTip("Ödeme için aktif TL banka hesabı bulunmalıdır.")
            return

        self.save_button.setToolTip("")

    def _selected_payment_bank_account_id(self) -> int | None:
        value = self.payment_bank_account_combo.currentData()

        if value is None:
            return None

        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _selected_date(self) -> date:
        qdate = self.payment_date_input.date()
        return date(qdate.year(), qdate.month(), qdate.day())

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

    def _format_decimal(self, value: Any) -> str:
        decimal_value = Decimal(value or Decimal("0.00"))
        formatted = f"{decimal_value:,.2f}"
        return formatted.replace(",", "X").replace(".", ",").replace("X", ".")

    def _save(self) -> None:
        selected_payment_bank_account_id = self._selected_payment_bank_account_id()

        if selected_payment_bank_account_id is None:
            QMessageBox.warning(self, "Eksik Bilgi", "Ödeme yapılacak TL banka hesabı seçilmelidir.")
            return

        try:
            with session_scope() as session:
                create_credit_card_payment(
                    session,
                    credit_card_id=self.credit_card_id,
                    payment_bank_account_id=selected_payment_bank_account_id,
                    payment_date=self._selected_date(),
                    amount=Decimal(str(self.amount_input.value())),
                    reference_no=self.reference_no_input.text(),
                    notes=self.notes_input.toPlainText(),
                    created_by_user_id=self._current_user_id(),
                )

        except CreditFacilityServiceError as exc:
            QMessageBox.warning(
                self,
                "Ödeme Kaydedilemedi",
                str(exc),
            )
            return

        except Exception as exc:
            QMessageBox.critical(
                self,
                "Beklenmeyen Hata",
                f"Kredi kartı ödemesi kaydedilirken beklenmeyen hata oluştu:\n\n{exc}",
            )
            return

        QMessageBox.information(
            self,
            "Ödeme Kaydedildi",
            "Kredi kartı ödemesi başarıyla kaydedildi.",
        )

        self.accept()


__all__ = [
    "CreditCardPaymentDialog",
]
