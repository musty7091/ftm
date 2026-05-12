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

from app.db.session import session_scope
from app.models.credit_facility import BankAccountCreditLimit
from app.services.credit_facility_service import (
    CreditFacilityServiceError,
    create_credit_limit_fee_transaction,
    get_credit_limit_debt_summary,
)
from app.ui.components.no_wheel_widgets import (
    NoWheelDateEdit,
    NoWheelDoubleSpinBox,
)


CREDIT_LIMIT_FEE_DIALOG_STYLE = """
QDialog {
    background-color: #0f172a;
    color: #e5e7eb;
}

QWidget#CreditLimitFeeWrapper,
QWidget#CreditLimitFeeFormBody {
    background-color: #0f172a;
}

QScrollArea#CreditLimitFeeScrollArea {
    background-color: #0f172a;
    border: none;
}

QScrollArea#CreditLimitFeeScrollArea > QWidget,
QScrollArea#CreditLimitFeeScrollArea > QWidget > QWidget {
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
QDateEdit:focus,
QDoubleSpinBox:focus {
    border: 1px solid #3b82f6;
}

QLineEdit:disabled,
QTextEdit:disabled,
QDateEdit:disabled,
QDoubleSpinBox:disabled {
    background-color: rgba(30, 41, 59, 0.55);
    color: #94a3b8;
    border: 1px solid rgba(100, 116, 139, 0.32);
}

QDateEdit::drop-down,
QDoubleSpinBox::up-button,
QDoubleSpinBox::down-button {
    background-color: #0f172a;
    border-left: 1px solid #334155;
    width: 24px;
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


class CreditLimitFeeDialog(QDialog):
    def __init__(
        self,
        *,
        current_user: Any | None = None,
        credit_limit_id: int,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.current_user = current_user
        self.credit_limit_id = int(credit_limit_id)

        self._credit_limit_data: dict[str, Any] = {}
        self._summary: dict[str, Any] = {}

        self.setWindowTitle("Masraf Kaydet")
        self.resize(700, 540)
        self.setMinimumSize(620, 480)
        self.setSizeGripEnabled(True)
        self.setStyleSheet(CREDIT_LIMIT_FEE_DIALOG_STYLE)

        self.title_label = QLabel("Masraf Kaydet")
        self.title_label.setObjectName("DialogTitle")

        self.subtitle_label = QLabel(
            "Seçili kredili / limitli hesap için banka masrafı kaydı oluşturur. "
            "Bu işlem banka hesabından para düşmez; masraf borcu olarak takip edilir."
        )
        self.subtitle_label.setObjectName("DialogSubtitle")
        self.subtitle_label.setWordWrap(True)

        self.limit_info_input = QLineEdit()
        self.limit_info_input.setReadOnly(True)

        self.current_fee_debt_input = QLineEdit()
        self.current_fee_debt_input.setReadOnly(True)

        self.total_payable_debt_input = QLineEdit()
        self.total_payable_debt_input.setReadOnly(True)

        self.transaction_date_input = NoWheelDateEdit()
        self.transaction_date_input.setCalendarPopup(True)
        self.transaction_date_input.setDisplayFormat("dd.MM.yyyy")
        self.transaction_date_input.setDate(QDate.currentDate())

        self.amount_input = NoWheelDoubleSpinBox()
        self.amount_input.setDecimals(2)
        self.amount_input.setMinimum(0.00)
        self.amount_input.setMaximum(999999999999.99)
        self.amount_input.setSingleStep(100.00)
        self.amount_input.setGroupSeparatorShown(True)

        self.currency_input = QLineEdit()
        self.currency_input.setReadOnly(True)

        self.reference_no_input = QLineEdit()
        self.reference_no_input.setPlaceholderText("Dekont / referans no")

        self.description_input = QLineEdit()
        self.description_input.setPlaceholderText("Örn: Limit tahsis ücreti, komisyon, banka masrafı")

        self.notes_input = QTextEdit()
        self.notes_input.setPlaceholderText("Not")
        self.notes_input.setFixedHeight(92)

        self.warning_label = QLabel(
            "Kural: Masraf bankadan otomatik tahmin edilmez. Banka dekontunda veya ekstrede görülen gerçek tutarı gir."
        )
        self.warning_label.setObjectName("DialogWarning")
        self.warning_label.setWordWrap(True)

        self.save_button = QPushButton("Masrafı Kaydet")
        self.save_button.setObjectName("PrimaryButton")
        self.save_button.clicked.connect(self._save)

        self.cancel_button = QPushButton("Vazgeç")
        self.cancel_button.setObjectName("SecondaryButton")
        self.cancel_button.clicked.connect(self.reject)

        self._build_ui()
        self._load_reference_data()
        self._populate_form()

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(22, 20, 22, 18)
        root_layout.setSpacing(12)

        scroll_area = QScrollArea()
        scroll_area.setObjectName("CreditLimitFeeScrollArea")
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        wrapper = QWidget()
        wrapper.setObjectName("CreditLimitFeeWrapper")

        wrapper_layout = QVBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(0, 8, 8, 8)
        wrapper_layout.setSpacing(10)

        form_body = QWidget()
        form_body.setObjectName("CreditLimitFeeFormBody")

        form_layout = QFormLayout(form_body)
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setHorizontalSpacing(16)
        form_layout.setVerticalSpacing(10)
        form_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

        form_layout.addRow(self._label("Limit Hesabı"), self.limit_info_input)
        form_layout.addRow(self._label("Mevcut Masraf Borcu"), self.current_fee_debt_input)
        form_layout.addRow(self._label("Toplam Ödenecek"), self.total_payable_debt_input)
        form_layout.addRow(self._label("Masraf Tarihi"), self.transaction_date_input)
        form_layout.addRow(self._label("Masraf Tutarı"), self.amount_input)
        form_layout.addRow(self._label("Para Birimi"), self.currency_input)
        form_layout.addRow(self._label("Referans No"), self.reference_no_input)
        form_layout.addRow(self._label("Açıklama"), self.description_input)
        form_layout.addRow(self._label("Not"), self.notes_input)

        help_label = QLabel(
            "Not: Masraf kaydı sadece borç oluşturur. Ödeme yapmak için daha sonra Limit Öde ekranını kullan."
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
        label.setMinimumWidth(160)
        return label

    def _load_reference_data(self) -> None:
        self._credit_limit_data = {}
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

                self._summary = get_credit_limit_debt_summary(
                    session,
                    credit_limit_id=int(credit_limit.id),
                )

                self._credit_limit_data = {
                    "id": int(credit_limit.id),
                    "limit_name": credit_limit.limit_name,
                    "bank_name": bank_name,
                    "account_name": account_name,
                    "currency_code": credit_limit.currency_code.value,
                    "is_active": bool(credit_limit.is_active),
                }

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
        self.currency_input.setText(currency_code)
        self.current_fee_debt_input.setText(
            self._format_money(self._summary.get("booked_fee_debt", Decimal("0.00")), currency_code)
        )
        self.total_payable_debt_input.setText(
            self._format_money(self._summary.get("booked_total_debt", Decimal("0.00")), currency_code)
        )

        if not bool(self._credit_limit_data.get("is_active")):
            self.save_button.setEnabled(False)
            self.warning_label.setText("Pasif limitli hesaba masraf kaydı girilemez. Önce hesabı aktifleştir.")

    def _selected_transaction_date(self) -> date:
        qdate = self.transaction_date_input.date()
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

    def _save(self) -> None:
        if not self._credit_limit_data:
            QMessageBox.warning(self, "Eksik Bilgi", "Limit bilgisi yüklenemedi.")
            return

        amount = Decimal(str(self.amount_input.value()))

        if amount <= Decimal("0.00"):
            QMessageBox.warning(
                self,
                "Eksik Bilgi",
                "Masraf tutarı sıfırdan büyük olmalıdır.",
            )
            return

        answer = QMessageBox.question(
            self,
            "Masraf Kaydet",
            (
                "Bu işlem banka hesabından para düşmeyecek. Masraf tutarı limitli hesap borcuna eklenecek.\n\n"
                "Devam etmek istiyor musun?"
            ),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if answer != QMessageBox.Yes:
            return

        try:
            with session_scope() as session:
                create_credit_limit_fee_transaction(
                    session,
                    credit_limit_id=self.credit_limit_id,
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
                "Masraf Kaydedilemedi",
                str(exc),
            )
            return

        except Exception as exc:
            QMessageBox.critical(
                self,
                "Beklenmeyen Hata",
                f"Masraf kaydedilirken beklenmeyen hata oluştu:\n\n{exc}",
            )
            return

        QMessageBox.information(
            self,
            "Masraf Kaydedildi",
            "Masraf kaydı başarıyla oluşturuldu.",
        )
        self.accept()

    def _format_money(self, value: Any, currency_code: str) -> str:
        try:
            amount = Decimal(str(value or "0"))
        except Exception:
            amount = Decimal("0.00")

        formatted = f"{amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"{formatted} {currency_code}"


__all__ = [
    "CreditLimitFeeDialog",
]
