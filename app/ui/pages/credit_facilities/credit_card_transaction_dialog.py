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
from app.models.credit_facility import CreditCard
from app.services.credit_facility_service import (
    CreditFacilityServiceError,
    create_credit_card_transaction,
)
from app.ui.components.no_wheel_widgets import (
    NoWheelDateEdit,
    NoWheelDoubleSpinBox,
    NoWheelSpinBox,
)

CREDIT_CARD_FIXED_CURRENCY_CODE = "TRY"
CREDIT_CARD_FIXED_CURRENCY_DISPLAY = "TRY / TL"


CREDIT_CARD_TRANSACTION_DIALOG_STYLE = """
QDialog {
    background-color: #0f172a;
    color: #e5e7eb;
}

QWidget#TransactionDialogWrapper,
QWidget#TransactionDialogFormBody {
    background-color: #0f172a;
}

QScrollArea#TransactionDialogScrollArea {
    background-color: #0f172a;
    border: none;
}

QScrollArea#TransactionDialogScrollArea > QWidget,
QScrollArea#TransactionDialogScrollArea > QWidget > QWidget {
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
QSpinBox,
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
QSpinBox:focus,
QDoubleSpinBox:focus {
    border: 1px solid #3b82f6;
}

QLineEdit:disabled {
    background-color: rgba(30, 41, 59, 0.55);
    color: #94a3b8;
    border: 1px solid rgba(100, 116, 139, 0.32);
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
"""


class CreditCardTransactionDialog(QDialog):
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
        self.credit_card_currency = CREDIT_CARD_FIXED_CURRENCY_CODE

        self.setWindowTitle("Kredi Kartı Harcaması Gir")
        self.resize(700, 580)
        self.setMinimumSize(620, 500)
        self.setSizeGripEnabled(True)
        self.setStyleSheet(CREDIT_CARD_TRANSACTION_DIALOG_STYLE)

        self.card_info_input = QLineEdit()
        self.card_info_input.setReadOnly(True)

        self.transaction_date_input = NoWheelDateEdit()
        self.transaction_date_input.setCalendarPopup(True)
        self.transaction_date_input.setDisplayFormat("dd.MM.yyyy")
        self.transaction_date_input.setDate(QDate.currentDate())

        self.merchant_name_input = QLineEdit()
        self.merchant_name_input.setPlaceholderText("Örn: Akaryakıt, market, tedarikçi, ofis gideri")

        self.description_input = QLineEdit()
        self.description_input.setPlaceholderText("Kısa açıklama")

        self.amount_input = NoWheelDoubleSpinBox()
        self.amount_input.setDecimals(2)
        self.amount_input.setMinimum(0.00)
        self.amount_input.setMaximum(999999999999.99)
        self.amount_input.setSingleStep(100.00)
        self.amount_input.setGroupSeparatorShown(True)

        self.currency_input = QLineEdit()
        self.currency_input.setReadOnly(True)

        self.installment_count_input = NoWheelSpinBox()
        self.installment_count_input.setMinimum(1)
        self.installment_count_input.setMaximum(120)
        self.installment_count_input.setValue(1)

        self.reference_no_input = QLineEdit()
        self.reference_no_input.setPlaceholderText("Slip / referans no")

        self.notes_input = QTextEdit()
        self.notes_input.setPlaceholderText("Not")
        self.notes_input.setFixedHeight(90)

        self.save_button = QPushButton("Kaydet")
        self.save_button.setObjectName("PrimaryButton")
        self.save_button.clicked.connect(self._save)

        self.cancel_button = QPushButton("Vazgeç")
        self.cancel_button.setObjectName("SecondaryButton")
        self.cancel_button.clicked.connect(self.reject)

        self._build_ui()
        self._load_credit_card_info()

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(22, 20, 22, 18)
        root_layout.setSpacing(12)

        title = QLabel("Kredi Kartı Harcaması Gir")
        title.setObjectName("DialogTitle")

        subtitle = QLabel(
            "Seçili kredi kartına TL harcama kaydı ekler. Bu kayıt şimdilik bekleyen harcama olarak tutulur; "
            "ekstre bağlantısı sonraki fazda yapılacak."
        )
        subtitle.setObjectName("DialogSubtitle")
        subtitle.setWordWrap(True)

        scroll_area = QScrollArea()
        scroll_area.setObjectName("TransactionDialogScrollArea")
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        wrapper = QWidget()
        wrapper.setObjectName("TransactionDialogWrapper")

        wrapper_layout = QVBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(0, 8, 8, 8)
        wrapper_layout.setSpacing(10)

        form_body = QWidget()
        form_body.setObjectName("TransactionDialogFormBody")

        form_layout = QFormLayout(form_body)
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setHorizontalSpacing(16)
        form_layout.setVerticalSpacing(10)
        form_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

        form_layout.addRow(self._label("Kart"), self.card_info_input)
        form_layout.addRow(self._label("İşlem Tarihi"), self.transaction_date_input)
        form_layout.addRow(self._label("İşyeri / Başlık"), self.merchant_name_input)
        form_layout.addRow(self._label("Açıklama"), self.description_input)
        form_layout.addRow(self._label("Tutar"), self.amount_input)
        form_layout.addRow(self._label("Para Birimi"), self.currency_input)
        form_layout.addRow(self._label("Taksit Sayısı"), self.installment_count_input)
        form_layout.addRow(self._label("Referans No"), self.reference_no_input)
        form_layout.addRow(self._label("Not"), self.notes_input)

        help_label = QLabel(
            "Not: Kredi kartı harcamaları bu modülde sadece TL olarak kaydedilir. "
            "Tarih, tutar ve taksit alanlarında mouse tekerleği yanlışlıkla değer değiştirmez."
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
        label.setMinimumWidth(138)
        return label

    def _load_credit_card_info(self) -> None:
        try:
            with session_scope() as session:
                credit_card = session.get(CreditCard, self.credit_card_id)

                if credit_card is None:
                    raise CreditFacilityServiceError(
                        f"Kredi kartı bulunamadı. Kredi kartı ID: {self.credit_card_id}"
                    )

                self.credit_card_name = credit_card.card_name
                self.credit_card_currency = CREDIT_CARD_FIXED_CURRENCY_CODE
                bank_name = credit_card.bank.name if credit_card.bank else "-"

        except Exception as exc:
            QMessageBox.critical(
                self,
                "Kart Bilgisi Yüklenemedi",
                f"Kredi kartı bilgisi yüklenirken hata oluştu:\n\n{exc}",
            )
            self.reject()
            return

        self.card_info_input.setText(f"{bank_name} / {self.credit_card_name}")
        self.currency_input.setText(CREDIT_CARD_FIXED_CURRENCY_DISPLAY)

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

    def _selected_date(self) -> date:
        qdate = self.transaction_date_input.date()
        return date(qdate.year(), qdate.month(), qdate.day())

    def _save(self) -> None:
        try:
            with session_scope() as session:
                create_credit_card_transaction(
                    session,
                    credit_card_id=self.credit_card_id,
                    transaction_date=self._selected_date(),
                    merchant_name=self.merchant_name_input.text(),
                    description=self.description_input.text(),
                    amount=Decimal(str(self.amount_input.value())),
                    installment_count=int(self.installment_count_input.value()),
                    reference_no=self.reference_no_input.text(),
                    notes=self.notes_input.toPlainText(),
                    created_by_user_id=self._current_user_id(),
                )

        except CreditFacilityServiceError as exc:
            QMessageBox.warning(
                self,
                "Harcama Kaydedilemedi",
                str(exc),
            )
            return

        except Exception as exc:
            QMessageBox.critical(
                self,
                "Beklenmeyen Hata",
                f"Harcama kaydedilirken beklenmeyen hata oluştu:\n\n{exc}",
            )
            return

        QMessageBox.information(
            self,
            "Harcama Kaydedildi",
            "Kredi kartı harcaması başarıyla kaydedildi.",
        )

        self.accept()


__all__ = [
    "CreditCardTransactionDialog",
]
