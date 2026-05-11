from __future__ import annotations

from decimal import Decimal
from typing import Any

from PySide6.QtCore import Qt
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
from app.models.bank import Bank, BankAccount
from app.models.credit_facility import CreditCard
from app.models.enums import CreditCardNetwork, CreditCardType, CurrencyCode
from app.services.credit_facility_service import (
    CreditFacilityServiceError,
    create_credit_card,
    update_credit_card,
)
from app.ui.components.no_wheel_widgets import (
    NoWheelComboBox,
    NoWheelDoubleSpinBox,
    NoWheelSpinBox,
)


CREDIT_CARD_DIALOG_STYLE = """
QDialog {
    background-color: #0f172a;
    color: #e5e7eb;
}

QWidget#CreditCardDialogWrapper {
    background-color: #0f172a;
}

QWidget#CreditCardDialogFormBody {
    background-color: #0f172a;
}

QScrollArea#CreditCardDialogScrollArea {
    background-color: #0f172a;
    border: none;
}

QScrollArea#CreditCardDialogScrollArea > QWidget {
    background-color: #0f172a;
}

QScrollArea#CreditCardDialogScrollArea > QWidget > QWidget {
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
QComboBox,
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
QComboBox:focus,
QSpinBox:focus,
QDoubleSpinBox:focus {
    border: 1px solid #3b82f6;
}

QLineEdit:disabled,
QTextEdit:disabled,
QComboBox:disabled,
QSpinBox:disabled,
QDoubleSpinBox:disabled {
    background-color: rgba(30, 41, 59, 0.55);
    color: #94a3b8;
    border: 1px solid rgba(100, 116, 139, 0.32);
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

QCheckBox {
    color: #e5e7eb;
    font-size: 12px;
    spacing: 8px;
    background-color: transparent;
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


class CreditCardDialog(QDialog):
    def __init__(
        self,
        *,
        current_user: Any | None = None,
        credit_card_id: int | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.current_user = current_user
        self.credit_card_id = credit_card_id
        self.is_edit_mode = credit_card_id is not None

        self._banks: list[dict[str, Any]] = []
        self._bank_accounts: list[dict[str, Any]] = []

        self.setWindowTitle("Kredi Kartı Düzenle" if self.is_edit_mode else "Kredi Kartı Tanımla")
        self.resize(720, 640)
        self.setMinimumSize(640, 520)
        self.setSizeGripEnabled(True)
        self.setStyleSheet(CREDIT_CARD_DIALOG_STYLE)

        self.title_label = QLabel("Kredi Kartı Düzenle" if self.is_edit_mode else "Kredi Kartı Tanımla")
        self.title_label.setObjectName("DialogTitle")

        self.subtitle_label = QLabel()
        self.subtitle_label.setObjectName("DialogSubtitle")
        self.subtitle_label.setWordWrap(True)

        self.bank_combo = NoWheelComboBox()
        self.bank_combo.setInsertPolicy(NoWheelComboBox.NoInsert)
        self.bank_combo.currentIndexChanged.connect(self._update_payment_account_combo)

        self.card_name_input = QLineEdit()
        self.card_name_input.setPlaceholderText("Örn: İş Bankası Maximum Ticari Kart")

        self.card_type_combo = NoWheelComboBox()
        self.card_type_combo.setInsertPolicy(NoWheelComboBox.NoInsert)

        self.card_network_combo = NoWheelComboBox()
        self.card_network_combo.setInsertPolicy(NoWheelComboBox.NoInsert)

        self.last_four_digits_input = QLineEdit()
        self.last_four_digits_input.setPlaceholderText("Örn: 1234")
        self.last_four_digits_input.setMaxLength(4)

        self.currency_input = QLineEdit()
        self.currency_input.setReadOnly(True)
        self.currency_input.setText("TRY / TL")
        self.currency_input.setToolTip("Kredi kartı modülü tek para birimiyle çalışır: TL.")

        self.credit_limit_input = NoWheelDoubleSpinBox()
        self.credit_limit_input.setDecimals(2)
        self.credit_limit_input.setMinimum(0.00)
        self.credit_limit_input.setMaximum(999999999999.99)
        self.credit_limit_input.setSingleStep(1000.00)
        self.credit_limit_input.setGroupSeparatorShown(True)

        self.statement_cut_day_input = NoWheelSpinBox()
        self.statement_cut_day_input.setMinimum(0)
        self.statement_cut_day_input.setMaximum(31)
        self.statement_cut_day_input.setSpecialValueText("Yok")

        self.payment_due_day_input = NoWheelSpinBox()
        self.payment_due_day_input.setMinimum(0)
        self.payment_due_day_input.setMaximum(31)
        self.payment_due_day_input.setSpecialValueText("Yok")

        self.payment_account_combo = NoWheelComboBox()
        self.payment_account_combo.setInsertPolicy(NoWheelComboBox.NoInsert)

        self.notes_input = QTextEdit()
        self.notes_input.setPlaceholderText("Açıklama / not")
        self.notes_input.setFixedHeight(86)

        self.create_another_checkbox = QCheckBox("Kaydettikten sonra yeni kart tanımlamaya devam et")
        self.create_another_checkbox.setVisible(not self.is_edit_mode)

        self.save_button = QPushButton("Güncelle" if self.is_edit_mode else "Kaydet")
        self.save_button.setObjectName("PrimaryButton")
        self.save_button.clicked.connect(self._save)

        self.cancel_button = QPushButton("Vazgeç")
        self.cancel_button.setObjectName("SecondaryButton")
        self.cancel_button.clicked.connect(self.reject)

        self._build_ui()
        self._load_reference_data()
        self._populate_static_combos()
        self._populate_bank_combo()
        self._update_payment_account_combo()
        self._apply_mode_text()

        if self.is_edit_mode:
            self._load_credit_card_to_form()

    def _apply_mode_text(self) -> None:
        if self.is_edit_mode:
            self.subtitle_label.setText(
                "Seçili kredi kartı bilgilerini günceller. Kartın bağlı olduğu banka değiştirilemez; "
                "kredi kartı para birimi ürün kararı gereği sabit TL olarak tutulur."
            )
            return

        self.subtitle_label.setText(
            "İşletmeye ait kredi kartı bilgilerini tanımlar. Bu işlem banka bakiyesini değiştirmez; "
            "kredi kartı modülü ürün kararı gereği sadece TL çalışır."
        )

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(22, 20, 22, 18)
        root_layout.setSpacing(12)

        scroll_area = QScrollArea()
        scroll_area.setObjectName("CreditCardDialogScrollArea")
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        wrapper = QWidget()
        wrapper.setObjectName("CreditCardDialogWrapper")

        wrapper_layout = QVBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(0, 8, 8, 8)
        wrapper_layout.setSpacing(10)

        form_body = QWidget()
        form_body.setObjectName("CreditCardDialogFormBody")

        form_layout = QFormLayout(form_body)
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setHorizontalSpacing(16)
        form_layout.setVerticalSpacing(10)
        form_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

        form_layout.addRow(self._label("Banka"), self.bank_combo)
        form_layout.addRow(self._label("Kart Adı"), self.card_name_input)
        form_layout.addRow(self._label("Kart Türü"), self.card_type_combo)
        form_layout.addRow(self._label("Kart Ağı"), self.card_network_combo)
        form_layout.addRow(self._label("Son 4 Hane"), self.last_four_digits_input)
        form_layout.addRow(self._label("Para Birimi"), self.currency_input)
        form_layout.addRow(self._label("Kart Limiti"), self.credit_limit_input)
        form_layout.addRow(self._label("Hesap Kesim Günü"), self.statement_cut_day_input)
        form_layout.addRow(self._label("Son Ödeme Günü"), self.payment_due_day_input)
        form_layout.addRow(self._label("Varsayılan Ödeme Hesabı"), self.payment_account_combo)
        form_layout.addRow(self._label("Not"), self.notes_input)

        help_label = QLabel(
            "Not: Kredi kartı modülü sadece TL çalışır. Gün alanlarında 0 / Yok seçilirse "
            "tarih takibi kart tanımı seviyesinde boş bırakılır. Mouse tekerleği form "
            "alanlarındaki değerleri değiştirmez."
        )
        help_label.setObjectName("DialogHelp")
        help_label.setWordWrap(True)

        wrapper_layout.addWidget(form_body)
        wrapper_layout.addWidget(help_label)
        wrapper_layout.addWidget(self.create_another_checkbox)
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
        label.setMinimumWidth(138)
        return label

    def _load_reference_data(self) -> None:
        self._banks = []
        self._bank_accounts = []

        try:
            with session_scope() as session:
                banks = session.execute(
                    select(Bank)
                    .where(Bank.is_active.is_(True))
                    .order_by(Bank.name.asc())
                ).scalars().all()

                bank_accounts = session.execute(
                    select(BankAccount)
                    .where(BankAccount.is_active.is_(True))
                    .order_by(BankAccount.account_name.asc())
                ).scalars().all()

                self._banks = [
                    {
                        "id": bank.id,
                        "name": bank.name,
                    }
                    for bank in banks
                ]

                self._bank_accounts = [
                    {
                        "id": account.id,
                        "bank_id": account.bank_id,
                        "bank_name": account.bank.name if account.bank else "-",
                        "account_name": account.account_name,
                        "currency_code": account.currency_code.value,
                    }
                    for account in bank_accounts
                ]

        except Exception as exc:
            QMessageBox.warning(
                self,
                "Referans Bilgiler Yüklenemedi",
                f"Banka ve hesap bilgileri yüklenirken hata oluştu:\n\n{exc}",
            )

    def _populate_static_combos(self) -> None:
        self.card_type_combo.clear()
        self.card_type_combo.addItem("Ticari", CreditCardType.BUSINESS)
        self.card_type_combo.addItem("Şirket", CreditCardType.COMPANY)
        self.card_type_combo.addItem("Bireysel", CreditCardType.PERSONAL)
        self.card_type_combo.addItem("Diğer", CreditCardType.OTHER)

        self.card_network_combo.clear()
        self.card_network_combo.addItem("Visa", CreditCardNetwork.VISA)
        self.card_network_combo.addItem("Mastercard", CreditCardNetwork.MASTERCARD)
        self.card_network_combo.addItem("Troy", CreditCardNetwork.TROY)
        self.card_network_combo.addItem("Amex", CreditCardNetwork.AMEX)
        self.card_network_combo.addItem("Diğer", CreditCardNetwork.OTHER)

        self.currency_input.setText("TRY / TL")

    def _populate_bank_combo(self) -> None:
        self.bank_combo.clear()

        if not self._banks:
            self.bank_combo.addItem("Aktif banka bulunamadı", None)
            self.bank_combo.setEnabled(False)
            self.save_button.setEnabled(False)
            return

        self.bank_combo.setEnabled(True)
        self.save_button.setEnabled(True)

        for bank in self._banks:
            self.bank_combo.addItem(str(bank["name"]), int(bank["id"]))

    def _load_credit_card_to_form(self) -> None:
        if self.credit_card_id is None:
            return

        try:
            with session_scope() as session:
                credit_card = session.get(CreditCard, int(self.credit_card_id))

                if credit_card is None:
                    raise CreditFacilityServiceError(
                        f"Kredi kartı bulunamadı. Kredi kartı ID: {self.credit_card_id}"
                    )

                data = {
                    "bank_id": credit_card.bank_id,
                    "card_name": credit_card.card_name,
                    "card_type": credit_card.card_type,
                    "card_network": credit_card.card_network,
                    "last_four_digits": credit_card.last_four_digits or "",
                    "credit_limit": Decimal(credit_card.credit_limit or 0),
                    "statement_cut_day": credit_card.statement_cut_day or 0,
                    "payment_due_day": credit_card.payment_due_day or 0,
                    "default_payment_bank_account_id": credit_card.default_payment_bank_account_id,
                    "notes": credit_card.notes or "",
                }

        except Exception as exc:
            QMessageBox.critical(
                self,
                "Kredi Kartı Yüklenemedi",
                f"Kredi kartı bilgileri yüklenirken hata oluştu:\n\n{exc}",
            )
            self.reject()
            return

        self._set_combo_by_data(self.bank_combo, data["bank_id"])
        self.bank_combo.setEnabled(False)

        self.card_name_input.setText(str(data["card_name"] or ""))
        self._set_combo_by_data(self.card_type_combo, data["card_type"])
        self._set_combo_by_data(self.card_network_combo, data["card_network"])
        self.last_four_digits_input.setText(str(data["last_four_digits"] or ""))
        self.currency_input.setText("TRY / TL")
        self.credit_limit_input.setValue(float(data["credit_limit"]))
        self.statement_cut_day_input.setValue(int(data["statement_cut_day"] or 0))
        self.payment_due_day_input.setValue(int(data["payment_due_day"] or 0))
        self.notes_input.setPlainText(str(data["notes"] or ""))

        self._update_payment_account_combo()
        self._set_combo_by_data(self.payment_account_combo, data["default_payment_bank_account_id"])

    def _set_combo_by_data(self, combo: NoWheelComboBox, data: Any) -> bool:
        for index in range(combo.count()):
            item_data = combo.itemData(index)

            if item_data == data:
                combo.setCurrentIndex(index)
                return True

            if item_data is not None and data is not None and str(item_data) == str(data):
                combo.setCurrentIndex(index)
                return True

        return False

    def _update_payment_account_combo(self) -> None:
        selected_currency = self._selected_currency_code()
        selected_bank_id = self._selected_bank_id()

        self.payment_account_combo.clear()
        self.payment_account_combo.addItem("Seçilmedi", None)

        for account in self._bank_accounts:
            if selected_currency is not None and account["currency_code"] != selected_currency.value:
                continue

            if selected_bank_id is not None and int(account["bank_id"]) != selected_bank_id:
                continue

            label = (
                f"{account['bank_name']} / {account['account_name']} "
                f"({account['currency_code']})"
            )
            self.payment_account_combo.addItem(label, int(account["id"]))

    def _selected_bank_id(self) -> int | None:
        value = self.bank_combo.currentData()

        if value is None:
            return None

        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _selected_currency_code(self) -> CurrencyCode:
        return CurrencyCode.TRY

    def _selected_payment_account_id(self) -> int | None:
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

    def _optional_day(self, spin_box: NoWheelSpinBox) -> int | None:
        value = int(spin_box.value())

        if value <= 0:
            return None

        return value

    def _save(self) -> None:
        selected_bank_id = self._selected_bank_id()
        selected_currency = self._selected_currency_code()

        if selected_bank_id is None:
            QMessageBox.warning(self, "Eksik Bilgi", "Banka seçilmelidir.")
            return

        try:
            with session_scope() as session:
                if self.is_edit_mode:
                    if self.credit_card_id is None:
                        raise CreditFacilityServiceError("Düzenlenecek kredi kartı ID bilgisi bulunamadı.")

                    update_credit_card(
                        session,
                        credit_card_id=int(self.credit_card_id),
                        card_name=self.card_name_input.text(),
                        card_type=self.card_type_combo.currentData(),
                        card_network=self.card_network_combo.currentData(),
                        last_four_digits=self.last_four_digits_input.text(),
                        currency_code=selected_currency,
                        credit_limit=Decimal(str(self.credit_limit_input.value())),
                        statement_cut_day=self._optional_day(self.statement_cut_day_input),
                        payment_due_day=self._optional_day(self.payment_due_day_input),
                        default_payment_bank_account_id=self._selected_payment_account_id(),
                        notes=self.notes_input.toPlainText(),
                        updated_by_user_id=self._current_user_id(),
                    )
                else:
                    create_credit_card(
                        session,
                        bank_id=selected_bank_id,
                        card_name=self.card_name_input.text(),
                        card_type=self.card_type_combo.currentData(),
                        card_network=self.card_network_combo.currentData(),
                        last_four_digits=self.last_four_digits_input.text(),
                        currency_code=selected_currency,
                        credit_limit=Decimal(str(self.credit_limit_input.value())),
                        statement_cut_day=self._optional_day(self.statement_cut_day_input),
                        payment_due_day=self._optional_day(self.payment_due_day_input),
                        default_payment_bank_account_id=self._selected_payment_account_id(),
                        notes=self.notes_input.toPlainText(),
                        created_by_user_id=self._current_user_id(),
                    )

        except CreditFacilityServiceError as exc:
            QMessageBox.warning(
                self,
                "Kredi Kartı Kaydedilemedi",
                str(exc),
            )
            return

        except Exception as exc:
            QMessageBox.critical(
                self,
                "Beklenmeyen Hata",
                f"Kredi kartı kaydedilirken beklenmeyen hata oluştu:\n\n{exc}",
            )
            return

        QMessageBox.information(
            self,
            "Kredi Kartı Kaydedildi",
            "Kredi kartı başarıyla güncellendi." if self.is_edit_mode else "Kredi kartı başarıyla tanımlandı.",
        )

        if not self.is_edit_mode and self.create_another_checkbox.isChecked():
            self._reset_form_for_next_card()
            return

        self.accept()

    def _reset_form_for_next_card(self) -> None:
        self.card_name_input.clear()
        self.last_four_digits_input.clear()
        self.credit_limit_input.setValue(0.00)
        self.statement_cut_day_input.setValue(0)
        self.payment_due_day_input.setValue(0)
        self.payment_account_combo.setCurrentIndex(0)
        self.notes_input.clear()
        self.card_name_input.setFocus()


__all__ = [
    "CreditCardDialog",
]
