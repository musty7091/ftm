from __future__ import annotations

from datetime import date
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
from app.models.enums import CreditLimitType, CreditLimitUsageMode, InterestPeriod
from app.services.credit_facility_service import (
    CreditFacilityServiceError,
    create_credit_limit,
    update_credit_limit,
)
from app.ui.components.no_wheel_widgets import (
    NoWheelComboBox,
    NoWheelDateEdit,
    NoWheelDoubleSpinBox,
    NoWheelSpinBox,
)


CREDIT_LIMIT_DIALOG_STYLE = """
QDialog {
    background-color: #0f172a;
    color: #e5e7eb;
}

QWidget#CreditLimitDialogWrapper {
    background-color: #0f172a;
}

QWidget#CreditLimitDialogFormBody {
    background-color: #0f172a;
}

QScrollArea#CreditLimitDialogScrollArea {
    background-color: #0f172a;
    border: none;
}

QScrollArea#CreditLimitDialogScrollArea > QWidget {
    background-color: #0f172a;
}

QScrollArea#CreditLimitDialogScrollArea > QWidget > QWidget {
    background-color: #0f172a;
}

QLabel#DialogTitle {
    color: #ffffff;
    font-size: 20px;
    font-weight: 900;
}

QLabel#DialogSubtitle,
QLabel#DialogHelp,
QLabel#CurrencyInfoLabel,
QLabel#ModeInfoLabel {
    color: #94a3b8;
    font-size: 12px;
}

QLabel#CurrencyBadge {
    background-color: rgba(37, 99, 235, 0.20);
    color: #dbeafe;
    border: 1px solid rgba(59, 130, 246, 0.45);
    border-radius: 10px;
    padding: 8px 10px;
    font-size: 13px;
    font-weight: 900;
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
QDateEdit:focus,
QSpinBox:focus,
QDoubleSpinBox:focus {
    border: 1px solid #3b82f6;
}

QLineEdit:disabled,
QTextEdit:disabled,
QComboBox:disabled,
QDateEdit:disabled,
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

QCalendarWidget {
    background-color: #0f172a;
    color: #e5e7eb;
    border: 1px solid #334155;
}

QCalendarWidget QWidget {
    background-color: #0f172a;
    color: #e5e7eb;
}

QCalendarWidget QToolButton {
    background-color: #1e40af;
    color: #ffffff;
    border: 1px solid #2563eb;
    border-radius: 6px;
    padding: 5px 8px;
    font-weight: 900;
}

QCalendarWidget QToolButton:hover {
    background-color: #2563eb;
}

QCalendarWidget QMenu {
    background-color: #111827;
    color: #e5e7eb;
    border: 1px solid #334155;
}

QCalendarWidget QMenu::item:selected {
    background-color: #2563eb;
    color: #ffffff;
}

QCalendarWidget QSpinBox {
    background-color: #111827;
    color: #e5e7eb;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 4px 8px;
}

QCalendarWidget QAbstractItemView {
    background-color: #0f172a;
    color: #e5e7eb;
    selection-background-color: #2563eb;
    selection-color: #ffffff;
    alternate-background-color: #111827;
    outline: none;
}

QCalendarWidget QHeaderView::section {
    background-color: #111827;
    color: #cbd5e1;
    border: 1px solid #334155;
    padding: 4px;
    font-weight: 900;
}
"""


class CreditLimitDialog(QDialog):
    def __init__(
        self,
        *,
        current_user: Any | None = None,
        credit_limit_id: int | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.current_user = current_user
        self.credit_limit_id = credit_limit_id
        self.is_edit_mode = credit_limit_id is not None

        self._bank_accounts: list[dict[str, Any]] = []

        self.setWindowTitle(
            "Limitli Hesap Düzenle" if self.is_edit_mode else "Limitli Hesap Tanımla"
        )
        self.resize(760, 700)
        self.setMinimumSize(660, 560)
        self.setSizeGripEnabled(True)
        self.setStyleSheet(CREDIT_LIMIT_DIALOG_STYLE)

        self.title_label = QLabel(
            "Limitli Hesap Düzenle" if self.is_edit_mode else "Limitli Hesap Tanımla"
        )
        self.title_label.setObjectName("DialogTitle")

        self.subtitle_label = QLabel()
        self.subtitle_label.setObjectName("DialogSubtitle")
        self.subtitle_label.setWordWrap(True)

        self.bank_account_combo = NoWheelComboBox()
        self.bank_account_combo.setInsertPolicy(NoWheelComboBox.NoInsert)
        self.bank_account_combo.currentIndexChanged.connect(self._update_currency_info)

        self.currency_badge = QLabel("Para Birimi: -")
        self.currency_badge.setObjectName("CurrencyBadge")

        self.currency_info_label = QLabel(
            "Para birimi elle seçilmez; seçilen banka hesabının para birimi kullanılır."
        )
        self.currency_info_label.setObjectName("CurrencyInfoLabel")
        self.currency_info_label.setWordWrap(True)

        self.limit_name_input = QLineEdit()
        self.limit_name_input.setPlaceholderText("Örn: Garanti KMH / İş Bankası Rotatif Limit")

        self.limit_type_combo = NoWheelComboBox()
        self.limit_type_combo.setInsertPolicy(NoWheelComboBox.NoInsert)

        self.limit_amount_input = NoWheelDoubleSpinBox()
        self.limit_amount_input.setDecimals(2)
        self.limit_amount_input.setMinimum(0.00)
        self.limit_amount_input.setMaximum(999999999999.99)
        self.limit_amount_input.setSingleStep(1000.00)
        self.limit_amount_input.setGroupSeparatorShown(True)

        self.interest_rate_input = NoWheelDoubleSpinBox()
        self.interest_rate_input.setDecimals(6)
        self.interest_rate_input.setMinimum(0.000000)
        self.interest_rate_input.setMaximum(100.000000)
        self.interest_rate_input.setSingleStep(0.100000)
        self.interest_rate_input.setSuffix(" %")

        self.interest_day_input = NoWheelSpinBox()
        self.interest_day_input.setMinimum(0)
        self.interest_day_input.setMaximum(31)
        self.interest_day_input.setSpecialValueText("Ay sonu")

        self.start_date_enabled_checkbox = QCheckBox("Sözleşme başlangıç tarihi kullan")
        self.start_date_enabled_checkbox.toggled.connect(self._update_date_enabled_states)

        self.contract_start_date_input = NoWheelDateEdit()
        self.contract_start_date_input.setCalendarPopup(True)
        self.contract_start_date_input.setDisplayFormat("dd.MM.yyyy")
        self.contract_start_date_input.setDate(QDate.currentDate())

        self.end_date_enabled_checkbox = QCheckBox("Sözleşme bitiş tarihi kullan")
        self.end_date_enabled_checkbox.toggled.connect(self._update_date_enabled_states)

        self.contract_end_date_input = NoWheelDateEdit()
        self.contract_end_date_input.setCalendarPopup(True)
        self.contract_end_date_input.setDisplayFormat("dd.MM.yyyy")
        self.contract_end_date_input.setDate(QDate.currentDate().addYears(1))

        self.notes_input = QTextEdit()
        self.notes_input.setPlaceholderText("Açıklama / not")
        self.notes_input.setFixedHeight(92)

        self.mode_info_label = QLabel(
            "Takip şekli: Hareket bazlı. KMH / kredili mevduat için limit kullanımı, ödeme, faiz ve masraf "
            "işlemleri ayrı kayıt olarak girilecek. Ödeme hareketleri faiz hesabında ertesi gün borçtan düşecek."
        )
        self.mode_info_label.setObjectName("ModeInfoLabel")
        self.mode_info_label.setWordWrap(True)

        self.create_another_checkbox = QCheckBox("Kaydettikten sonra yeni limitli hesap tanımlamaya devam et")
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
        self._populate_bank_account_combo()
        self._apply_mode_text()
        self._update_date_enabled_states()
        self._update_currency_info()

        if self.is_edit_mode:
            self._load_credit_limit_to_form()

    def _apply_mode_text(self) -> None:
        if self.is_edit_mode:
            self.subtitle_label.setText(
                "Seçili limitli hesap tanımını günceller. Bağlı banka hesabı değiştirilemez; "
                "limit, faiz ve takip bilgileri düzenlenebilir."
            )
            return

        self.subtitle_label.setText(
            "Banka hesabına bağlı KMH / kredili mevduat veya rotatif limit tanımlar. "
            "Bu ekran sadece limit tanımı yapar; kullanım ve ödeme hareketleri ayrı girilir."
        )

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(22, 20, 22, 18)
        root_layout.setSpacing(12)

        scroll_area = QScrollArea()
        scroll_area.setObjectName("CreditLimitDialogScrollArea")
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        wrapper = QWidget()
        wrapper.setObjectName("CreditLimitDialogWrapper")

        wrapper_layout = QVBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(0, 8, 8, 8)
        wrapper_layout.setSpacing(10)

        form_body = QWidget()
        form_body.setObjectName("CreditLimitDialogFormBody")

        form_layout = QFormLayout(form_body)
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setHorizontalSpacing(16)
        form_layout.setVerticalSpacing(10)
        form_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

        form_layout.addRow(self._label("Banka Hesabı"), self.bank_account_combo)
        form_layout.addRow(self._label("Para Birimi"), self.currency_badge)
        form_layout.addRow(self._label("Limit Adı"), self.limit_name_input)
        form_layout.addRow(self._label("Limit Tipi"), self.limit_type_combo)
        form_layout.addRow(self._label("Limit Tutarı"), self.limit_amount_input)
        form_layout.addRow(self._label("Aylık Faiz Oranı"), self.interest_rate_input)
        form_layout.addRow(self._label("Faiz / Ödeme Günü"), self.interest_day_input)
        form_layout.addRow(self._label("Başlangıç"), self._date_row(self.start_date_enabled_checkbox, self.contract_start_date_input))
        form_layout.addRow(self._label("Bitiş"), self._date_row(self.end_date_enabled_checkbox, self.contract_end_date_input))
        form_layout.addRow(self._label("Not"), self.notes_input)

        help_label = QLabel(
            "Not: Gün alanında 0 / Ay sonu seçilirse dönem sonu ay sonu kabul edilir. "
            "Mouse tekerleği form alanlarındaki değerleri değiştirmez."
        )
        help_label.setObjectName("DialogHelp")
        help_label.setWordWrap(True)

        wrapper_layout.addWidget(form_body)
        wrapper_layout.addWidget(self.currency_info_label)
        wrapper_layout.addWidget(self.mode_info_label)
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
        label.setMinimumWidth(152)
        return label

    def _date_row(self, checkbox: QCheckBox, date_input: NoWheelDateEdit) -> QWidget:
        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(10)
        row_layout.addWidget(checkbox)
        row_layout.addWidget(date_input)
        row_layout.setStretch(0, 1)
        row_layout.setStretch(1, 1)
        return row_widget

    def _load_reference_data(self) -> None:
        self._bank_accounts = []

        try:
            with session_scope() as session:
                bank_accounts = session.execute(
                    select(BankAccount).order_by(BankAccount.account_name.asc())
                ).scalars().all()

                self._bank_accounts = [
                    {
                        "id": account.id,
                        "bank_name": account.bank.name if account.bank else "-",
                        "account_name": account.account_name,
                        "currency_code": account.currency_code.value,
                        "is_active": bool(account.is_active),
                    }
                    for account in bank_accounts
                ]

        except Exception as exc:
            QMessageBox.warning(
                self,
                "Referans Bilgiler Yüklenemedi",
                f"Banka hesabı bilgileri yüklenirken hata oluştu:\n\n{exc}",
            )

    def _populate_static_combos(self) -> None:
        self.limit_type_combo.clear()
        self.limit_type_combo.addItem("KMH / Kredili Mevduat", CreditLimitType.KMH)
        self.limit_type_combo.addItem("Rotatif Kredi / Rotatif Limit", CreditLimitType.ROTATIVE_LIMIT)
        self.limit_type_combo.addItem("Diğer", CreditLimitType.OTHER)

    def _populate_bank_account_combo(self) -> None:
        self.bank_account_combo.clear()

        usable_accounts = []
        for account in self._bank_accounts:
            if account["is_active"]:
                usable_accounts.append(account)

        if not usable_accounts:
            self.bank_account_combo.addItem("Aktif banka hesabı bulunamadı", None)
            self.bank_account_combo.setEnabled(False)
            self.save_button.setEnabled(False)
            return

        self.bank_account_combo.setEnabled(True)
        self.save_button.setEnabled(True)

        for account in usable_accounts:
            label = f"{account['bank_name']} / {account['account_name']} ({account['currency_code']})"
            self.bank_account_combo.addItem(label, int(account["id"]))

    def _load_credit_limit_to_form(self) -> None:
        if self.credit_limit_id is None:
            return

        try:
            with session_scope() as session:
                credit_limit = session.get(BankAccountCreditLimit, int(self.credit_limit_id))

                if credit_limit is None:
                    raise CreditFacilityServiceError(
                        f"Kredili / limitli hesap tanımı bulunamadı. ID: {self.credit_limit_id}"
                    )

                data = {
                    "bank_account_id": credit_limit.bank_account_id,
                    "limit_name": credit_limit.limit_name,
                    "limit_type": credit_limit.limit_type,
                    "limit_amount": Decimal(credit_limit.limit_amount or 0),
                    "interest_rate": Decimal(credit_limit.interest_rate or 0),
                    "interest_day": credit_limit.interest_day or 0,
                    "contract_start_date": credit_limit.contract_start_date,
                    "contract_end_date": credit_limit.contract_end_date,
                    "notes": credit_limit.notes or "",
                }

        except Exception as exc:
            QMessageBox.critical(
                self,
                "Limitli Hesap Yüklenemedi",
                f"Limitli hesap bilgileri yüklenirken hata oluştu:\n\n{exc}",
            )
            self.reject()
            return

        self._ensure_current_account_in_combo(int(data["bank_account_id"]))
        self._set_combo_by_data(self.bank_account_combo, data["bank_account_id"])
        self.bank_account_combo.setEnabled(False)

        self.limit_name_input.setText(str(data["limit_name"] or ""))
        self._ensure_current_limit_type_in_combo(data["limit_type"])
        self._set_combo_by_data(self.limit_type_combo, data["limit_type"])
        self.limit_amount_input.setValue(float(data["limit_amount"]))
        self.interest_rate_input.setValue(float(data["interest_rate"]))
        self.interest_day_input.setValue(int(data["interest_day"] or 0))
        self.notes_input.setPlainText(str(data["notes"] or ""))

        start_date = data["contract_start_date"]
        if isinstance(start_date, date):
            self.start_date_enabled_checkbox.setChecked(True)
            self.contract_start_date_input.setDate(
                QDate(start_date.year, start_date.month, start_date.day)
            )

        end_date = data["contract_end_date"]
        if isinstance(end_date, date):
            self.end_date_enabled_checkbox.setChecked(True)
            self.contract_end_date_input.setDate(QDate(end_date.year, end_date.month, end_date.day))

        self._update_date_enabled_states()
        self._update_currency_info()

    def _ensure_current_account_in_combo(self, bank_account_id: int) -> None:
        for index in range(self.bank_account_combo.count()):
            if self.bank_account_combo.itemData(index) == bank_account_id:
                return

        for account in self._bank_accounts:
            if int(account["id"]) != bank_account_id:
                continue

            status_text = "Pasif" if not account["is_active"] else "Aktif"
            label = (
                f"{account['bank_name']} / {account['account_name']} "
                f"({account['currency_code']}) - {status_text}"
            )
            self.bank_account_combo.addItem(label, bank_account_id)
            return

    def _ensure_current_limit_type_in_combo(self, limit_type: CreditLimitType) -> None:
        for index in range(self.limit_type_combo.count()):
            if self.limit_type_combo.itemData(index) == limit_type:
                return

        if limit_type == CreditLimitType.LIMITED_DEPOSIT:
            self.limit_type_combo.addItem(
                "Limitli Mevduat (Eski Tanım)",
                CreditLimitType.LIMITED_DEPOSIT,
            )
            return

        self.limit_type_combo.addItem(str(limit_type.value), limit_type)

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

    def _selected_bank_account_id(self) -> int | None:
        value = self.bank_account_combo.currentData()

        if value is None:
            return None

        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _selected_account_currency(self) -> str | None:
        account_id = self._selected_bank_account_id()

        if account_id is None:
            return None

        for account in self._bank_accounts:
            if int(account["id"]) == account_id:
                return str(account["currency_code"])

        return None

    def _update_currency_info(self) -> None:
        currency_code = self._selected_account_currency()

        if not currency_code:
            self.currency_badge.setText("Para Birimi: -")
            return

        self.currency_badge.setText(f"Para Birimi: {currency_code}")

    def _update_date_enabled_states(self) -> None:
        self.contract_start_date_input.setEnabled(self.start_date_enabled_checkbox.isChecked())
        self.contract_end_date_input.setEnabled(self.end_date_enabled_checkbox.isChecked())

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

    def _optional_date(self, checkbox: QCheckBox, date_input: NoWheelDateEdit) -> date | None:
        if not checkbox.isChecked():
            return None

        qdate = date_input.date()
        return date(qdate.year(), qdate.month(), qdate.day())

    def _save(self) -> None:
        selected_bank_account_id = self._selected_bank_account_id()

        if selected_bank_account_id is None:
            QMessageBox.warning(self, "Eksik Bilgi", "Banka hesabı seçilmelidir.")
            return

        try:
            with session_scope() as session:
                if self.is_edit_mode:
                    if self.credit_limit_id is None:
                        raise CreditFacilityServiceError(
                            "Düzenlenecek limitli hesap ID bilgisi bulunamadı."
                        )

                    update_credit_limit(
                        session,
                        credit_limit_id=int(self.credit_limit_id),
                        limit_name=self.limit_name_input.text(),
                        limit_type=self.limit_type_combo.currentData(),
                        limit_amount=Decimal(str(self.limit_amount_input.value())),
                        usage_mode=CreditLimitUsageMode.TRANSACTION_BASED,
                        manual_used_amount=Decimal("0.00"),
                        interest_rate=Decimal(str(self.interest_rate_input.value())),
                        interest_period=InterestPeriod.MONTHLY,
                        interest_day=self._optional_day(self.interest_day_input),
                        contract_start_date=self._optional_date(
                            self.start_date_enabled_checkbox,
                            self.contract_start_date_input,
                        ),
                        contract_end_date=self._optional_date(
                            self.end_date_enabled_checkbox,
                            self.contract_end_date_input,
                        ),
                        notes=self.notes_input.toPlainText(),
                        updated_by_user_id=self._current_user_id(),
                    )
                else:
                    create_credit_limit(
                        session,
                        bank_account_id=selected_bank_account_id,
                        limit_name=self.limit_name_input.text(),
                        limit_type=self.limit_type_combo.currentData(),
                        limit_amount=Decimal(str(self.limit_amount_input.value())),
                        usage_mode=CreditLimitUsageMode.TRANSACTION_BASED,
                        manual_used_amount=Decimal("0.00"),
                        interest_rate=Decimal(str(self.interest_rate_input.value())),
                        interest_period=InterestPeriod.MONTHLY,
                        interest_day=self._optional_day(self.interest_day_input),
                        contract_start_date=self._optional_date(
                            self.start_date_enabled_checkbox,
                            self.contract_start_date_input,
                        ),
                        contract_end_date=self._optional_date(
                            self.end_date_enabled_checkbox,
                            self.contract_end_date_input,
                        ),
                        notes=self.notes_input.toPlainText(),
                        created_by_user_id=self._current_user_id(),
                    )

        except CreditFacilityServiceError as exc:
            QMessageBox.warning(
                self,
                "Limitli Hesap Kaydedilemedi",
                str(exc),
            )
            return

        except Exception as exc:
            QMessageBox.critical(
                self,
                "Beklenmeyen Hata",
                f"Limitli hesap kaydedilirken beklenmeyen hata oluştu:\n\n{exc}",
            )
            return

        QMessageBox.information(
            self,
            "Limitli Hesap Kaydedildi",
            "Limitli hesap başarıyla güncellendi."
            if self.is_edit_mode
            else "Limitli hesap başarıyla tanımlandı.",
        )

        if not self.is_edit_mode and self.create_another_checkbox.isChecked():
            self._reset_form_for_next_limit()
            return

        self.accept()

    def _reset_form_for_next_limit(self) -> None:
        self.limit_name_input.clear()
        self.limit_amount_input.setValue(0.00)
        self.interest_rate_input.setValue(0.000000)
        self.interest_day_input.setValue(0)
        self.start_date_enabled_checkbox.setChecked(False)
        self.end_date_enabled_checkbox.setChecked(False)
        self.notes_input.clear()
        self.limit_name_input.setFocus()


__all__ = [
    "CreditLimitDialog",
]
