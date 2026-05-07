from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy import select
from sqlalchemy.orm import aliased

from app.db.session import session_scope
from app.models.bank import Bank, BankAccount
from app.models.business_partner import BusinessPartner
from app.models.check import ReceivedCheck
from app.models.enums import ReceivedCheckStatus
from app.services.received_check_discount_batch_service import (
    DiscountBatchCheckInput,
    ReceivedCheckDiscountBatchServiceError,
    calculate_received_check_discount_batch,
)
from app.ui.pages.banks.bank_dialog_styles import BANK_DIALOG_STYLES
from app.ui.pages.checks.checks_data import format_currency_amount, received_status_text


@dataclass(frozen=True)
class DiscountableReceivedCheckOption:
    received_check_id: int
    customer_name: str
    drawer_bank_name: str
    collection_bank_account_id: int | None
    collection_bank_name: str | None
    collection_bank_account_name: str | None
    check_number: str
    received_date: date
    due_date: date
    amount: Decimal
    currency_code: str
    status: str
    reference_no: str | None


@dataclass(frozen=True)
class DiscountBankAccountOption:
    bank_account_id: int
    bank_name: str
    account_name: str
    currency_code: str


def _qdate_to_date(qdate: QDate) -> date:
    return date(qdate.year(), qdate.month(), qdate.day())


def _format_decimal_tr(value: Decimal) -> str:
    formatted = f"{value:,.2f}"
    formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")

    return formatted


def _format_days(value: Decimal) -> str:
    formatted = f"{value:,.2f}"
    formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")

    return formatted


class ReceivedCheckDiscountBatchDialog(QDialog):
    def __init__(self, *, parent: QWidget | None) -> None:
        super().__init__(parent)

        self.discountable_checks = self._load_discountable_checks()
        self.bank_accounts = self._load_bank_accounts()

        self.check_lookup = {
            discountable_check.received_check_id: discountable_check
            for discountable_check in self.discountable_checks
        }
        self.bank_account_lookup = {
            bank_account.bank_account_id: bank_account
            for bank_account in self.bank_accounts
        }

        self.selected_check_ids: set[int] = set()
        self.payload: dict[str, Any] | None = None
        self.is_filling_table = False

        self.setWindowTitle("Alınan Çekleri İskontoya Ver / Kırdır")
        self.resize(1320, 820)
        self.setMinimumSize(1100, 700)
        self.setSizeGripEnabled(True)
        self.setStyleSheet(
            BANK_DIALOG_STYLES
            + """
            QScrollArea {
                background-color: #0f172a;
                border: none;
            }

            QScrollArea > QWidget > QWidget {
                background-color: #0f172a;
            }

            QWidget#DialogContent {
                background-color: #0f172a;
            }

            QFrame#PreviewBox {
                background-color: #111827;
                border: 1px solid #1e293b;
                border-radius: 12px;
            }

            QLabel#PreviewTitle {
                color: #93c5fd;
                font-size: 11px;
                font-weight: 800;
            }

            QLabel#PreviewValue {
                color: #ffffff;
                font-size: 17px;
                font-weight: 900;
            }

            QLabel#PreviewHint {
                color: #bfdbfe;
                font-size: 11px;
                font-weight: 600;
            }

            QTableWidget {
                background-color: #0b1220;
                color: #e5e7eb;
                border: 1px solid #1e293b;
                border-radius: 12px;
                gridline-color: #1e293b;
                selection-background-color: #2563eb;
                selection-color: #ffffff;
            }

            QTableWidget::item {
                padding: 6px;
                border-bottom: 1px solid #1e293b;
            }

            QHeaderView::section {
                background-color: #1e293b;
                color: #e5e7eb;
                border: none;
                padding: 8px;
                font-weight: 700;
            }
            """
        )

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.NoFrame)

        content_widget = QWidget()
        content_widget.setObjectName("DialogContent")

        main_layout = QVBoxLayout(content_widget)
        main_layout.setContentsMargins(24, 22, 24, 22)
        main_layout.setSpacing(14)

        title = QLabel("Alınan Çekleri İskontoya Ver / Kırdır")
        title.setObjectName("SectionTitle")

        subtitle = QLabel(
            "Portföyde, bankaya verilmiş veya tahsilde olan birden fazla alınan çeki aynı iskonto paketine ekleyebilirsin. "
            "Farklı keşideci bankalara ait çekler aynı iskonto paketinde kullanılabilir; sistem yalnızca seçilen iskonto hesabının "
            "para birimi ile çek para birimlerinin aynı olmasını zorunlu tutar. Her çek için vadeye kalan gün, faiz kesintisi, "
            "komisyon ve net tutar ayrı hesaplanır. Seçilen banka hesabına tek net giriş oluşur."
        )
        subtitle.setObjectName("MutedText")
        subtitle.setWordWrap(True)

        top_form_layout = QGridLayout()
        top_form_layout.setHorizontalSpacing(12)
        top_form_layout.setVerticalSpacing(10)
        top_form_layout.setColumnStretch(0, 1)
        top_form_layout.setColumnStretch(1, 1)
        top_form_layout.setColumnStretch(2, 1)
        top_form_layout.setColumnStretch(3, 1)

        self.bank_account_combo = QComboBox()
        self.bank_account_combo.setMinimumHeight(38)
        self.bank_account_combo.currentIndexChanged.connect(self._bank_account_changed)

        self._fill_bank_account_combo()

        self.discount_date_edit = QDateEdit()
        self.discount_date_edit.setMinimumHeight(38)
        self.discount_date_edit.setCalendarPopup(True)
        self.discount_date_edit.setDisplayFormat("dd.MM.yyyy")
        self.discount_date_edit.setDate(QDate.currentDate())
        self.discount_date_edit.dateChanged.connect(self._apply_filters)

        self.annual_interest_rate_input = QLineEdit()
        self.annual_interest_rate_input.setMinimumHeight(38)
        self.annual_interest_rate_input.setPlaceholderText("Örn: 35")
        self.annual_interest_rate_input.textChanged.connect(self._update_preview)

        self.commission_rate_input = QLineEdit()
        self.commission_rate_input.setMinimumHeight(38)
        self.commission_rate_input.setPlaceholderText("Örn: 1")
        self.commission_rate_input.setText("0")
        self.commission_rate_input.textChanged.connect(self._update_preview)

        self.bsiv_rate_input = QLineEdit()
        self.bsiv_rate_input.setMinimumHeight(38)
        self.bsiv_rate_input.setPlaceholderText("Örn: 0,30")
        self.bsiv_rate_input.setText("0,30")
        self.bsiv_rate_input.textChanged.connect(self._update_preview)

        self.day_basis_combo = QComboBox()
        self.day_basis_combo.setMinimumHeight(38)
        self.day_basis_combo.addItem("365 gün", 365)
        self.day_basis_combo.addItem("360 gün", 360)
        self.day_basis_combo.currentIndexChanged.connect(self._update_preview)

        self.reference_no_input = QLineEdit()
        self.reference_no_input.setMinimumHeight(38)
        self.reference_no_input.setPlaceholderText("İsteğe bağlı referans no")

        self.search_input = QLineEdit()
        self.search_input.setMinimumHeight(38)
        self.search_input.setPlaceholderText("Müşteri / çek no / banka / referans ara")
        self.search_input.textChanged.connect(self._apply_filters)

        top_form_layout.addWidget(self._build_field_label("İskonto hesabı"), 0, 0)
        top_form_layout.addWidget(self._build_field_label("İskonto tarihi"), 0, 1)
        top_form_layout.addWidget(self._build_field_label("Yıllık faiz (%)"), 0, 2)
        top_form_layout.addWidget(self._build_field_label("Komisyon (%)"), 0, 3)

        top_form_layout.addWidget(self.bank_account_combo, 1, 0)
        top_form_layout.addWidget(self.discount_date_edit, 1, 1)
        top_form_layout.addWidget(self.annual_interest_rate_input, 1, 2)
        top_form_layout.addWidget(self.commission_rate_input, 1, 3)

        top_form_layout.addWidget(self._build_field_label("BSİV (%)"), 2, 0)
        top_form_layout.addWidget(self._build_field_label("Gün bazı"), 2, 1)
        top_form_layout.addWidget(self._build_field_label("Referans no"), 2, 2)
        top_form_layout.addWidget(self._build_field_label("Arama"), 2, 3)

        top_form_layout.addWidget(self.bsiv_rate_input, 3, 0)
        top_form_layout.addWidget(self.day_basis_combo, 3, 1)
        top_form_layout.addWidget(self.reference_no_input, 3, 2)
        top_form_layout.addWidget(self.search_input, 3, 3)

        self.bank_account_info_label = QLabel("")
        self.bank_account_info_label.setObjectName("MutedText")
        self.bank_account_info_label.setWordWrap(True)

        self.results_info_label = QLabel("")
        self.results_info_label.setObjectName("MutedText")
        self.results_info_label.setWordWrap(True)

        self.checks_table = QTableWidget()
        self.checks_table.setColumnCount(13)
        self.checks_table.setHorizontalHeaderLabels(
            [
                "Seç",
                "ID",
                "Müşteri",
                "Çek No",
                "Keşideci Banka",
                "Vade",
                "Gün",
                "Tutar",
                "Faiz",
                "Komisyon",
                "BSİV",
                "Net",
                "Durum",
            ]
        )
        self.checks_table.verticalHeader().setVisible(False)
        self.checks_table.setAlternatingRowColors(False)
        self.checks_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.checks_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.checks_table.setWordWrap(False)
        self.checks_table.setTextElideMode(Qt.ElideRight)
        self.checks_table.verticalHeader().setDefaultSectionSize(34)
        self.checks_table.verticalHeader().setMinimumSectionSize(30)
        self.checks_table.setMinimumHeight(310)
        self.checks_table.itemChanged.connect(self._table_item_changed)

        checks_header = self.checks_table.horizontalHeader()
        checks_header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        checks_header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        checks_header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        checks_header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        checks_header.setSectionResizeMode(4, QHeaderView.Stretch)
        checks_header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        checks_header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        checks_header.setSectionResizeMode(7, QHeaderView.ResizeToContents)
        checks_header.setSectionResizeMode(8, QHeaderView.ResizeToContents)
        checks_header.setSectionResizeMode(9, QHeaderView.ResizeToContents)
        checks_header.setSectionResizeMode(10, QHeaderView.ResizeToContents)
        checks_header.setSectionResizeMode(11, QHeaderView.ResizeToContents)
        checks_header.setSectionResizeMode(12, QHeaderView.ResizeToContents)

        preview_layout = self._build_preview_layout()

        self.description_input = QTextEdit()
        self.description_input.setPlaceholderText("İsteğe bağlı açıklama")
        self.description_input.setFixedHeight(86)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)

        self.save_button = QPushButton("İskonto Paketini Kaydet")
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
        main_layout.addLayout(top_form_layout)
        main_layout.addWidget(self.bank_account_info_label)
        main_layout.addWidget(self.results_info_label)
        main_layout.addWidget(self.checks_table, 1)
        main_layout.addLayout(preview_layout)
        main_layout.addWidget(self._build_field_label("Açıklama"))
        main_layout.addWidget(self.description_input)
        main_layout.addLayout(button_layout)

        scroll_area.setWidget(content_widget)
        outer_layout.addWidget(scroll_area)

        self._apply_filters()

    def _build_field_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("MutedText")
        return label

    def _build_preview_layout(self) -> QGridLayout:
        preview_layout = QGridLayout()
        preview_layout.setSpacing(10)
        preview_layout.setColumnStretch(0, 1)
        preview_layout.setColumnStretch(1, 1)
        preview_layout.setColumnStretch(2, 1)
        preview_layout.setColumnStretch(3, 1)
        preview_layout.setColumnStretch(4, 1)
        preview_layout.setColumnStretch(5, 1)
        preview_layout.setColumnStretch(6, 1)

        self.selected_count_label = self._build_preview_box("SEÇİLEN", "0")
        self.total_gross_label = self._build_preview_box("BRÜT TOPLAM", "-")
        self.weighted_average_days_label = self._build_preview_box("ORT. VADE", "-")
        self.total_interest_label = self._build_preview_box("FAİZ", "-")
        self.total_commission_label = self._build_preview_box("KOMİSYON", "-")
        self.total_bsiv_label = self._build_preview_box("BSİV", "-")
        self.net_bank_amount_label = self._build_preview_box("NET BANKA", "-")

        preview_layout.addWidget(self.selected_count_label, 0, 0)
        preview_layout.addWidget(self.total_gross_label, 0, 1)
        preview_layout.addWidget(self.weighted_average_days_label, 0, 2)
        preview_layout.addWidget(self.total_interest_label, 0, 3)
        preview_layout.addWidget(self.total_commission_label, 0, 4)
        preview_layout.addWidget(self.total_bsiv_label, 0, 5)
        preview_layout.addWidget(self.net_bank_amount_label, 0, 6)

        return preview_layout

    def _build_preview_box(self, title_text: str, value_text: str) -> QFrame:
        box = QFrame()
        box.setObjectName("PreviewBox")

        layout = QVBoxLayout(box)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        title = QLabel(title_text)
        title.setObjectName("PreviewTitle")

        value = QLabel(value_text)
        value.setObjectName("PreviewValue")
        value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        hint = QLabel("")
        hint.setObjectName("PreviewHint")
        hint.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(value)
        layout.addWidget(hint)

        box.value_label = value
        box.hint_label = hint

        return box

    def _load_discountable_checks(self) -> list[DiscountableReceivedCheckOption]:
        with session_scope() as session:
            collection_bank_account_alias = aliased(BankAccount)
            collection_bank_alias = aliased(Bank)

            statement = (
                select(
                    ReceivedCheck,
                    BusinessPartner,
                    collection_bank_account_alias,
                    collection_bank_alias,
                )
                .join(BusinessPartner, ReceivedCheck.customer_id == BusinessPartner.id)
                .outerjoin(
                    collection_bank_account_alias,
                    ReceivedCheck.collection_bank_account_id == collection_bank_account_alias.id,
                )
                .outerjoin(
                    collection_bank_alias,
                    collection_bank_account_alias.bank_id == collection_bank_alias.id,
                )
                .where(
                    ReceivedCheck.status.in_(
                        [
                            ReceivedCheckStatus.PORTFOLIO,
                            ReceivedCheckStatus.GIVEN_TO_BANK,
                            ReceivedCheckStatus.IN_COLLECTION,
                        ]
                    ),
                    ReceivedCheck.collected_transaction_id.is_(None),
                )
                .order_by(ReceivedCheck.due_date.asc(), ReceivedCheck.id.asc())
            )

            rows = session.execute(statement).all()

            results: list[DiscountableReceivedCheckOption] = []

            for received_check, customer, collection_bank_account, collection_bank in rows:
                currency_code = (
                    received_check.currency_code.value
                    if hasattr(received_check.currency_code, "value")
                    else str(received_check.currency_code)
                )

                status_value = (
                    received_check.status.value
                    if hasattr(received_check.status, "value")
                    else str(received_check.status)
                )

                results.append(
                    DiscountableReceivedCheckOption(
                        received_check_id=received_check.id,
                        customer_name=customer.name,
                        drawer_bank_name=received_check.drawer_bank_name,
                        collection_bank_account_id=received_check.collection_bank_account_id,
                        collection_bank_name=collection_bank.name if collection_bank else None,
                        collection_bank_account_name=(
                            collection_bank_account.account_name if collection_bank_account else None
                        ),
                        check_number=received_check.check_number,
                        received_date=received_check.received_date,
                        due_date=received_check.due_date,
                        amount=Decimal(str(received_check.amount)),
                        currency_code=currency_code,
                        status=status_value,
                        reference_no=received_check.reference_no,
                    )
                )

            return results

    def _load_bank_accounts(self) -> list[DiscountBankAccountOption]:
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

            results: list[DiscountBankAccountOption] = []

            for bank_account, bank in rows:
                currency_code = (
                    bank_account.currency_code.value
                    if hasattr(bank_account.currency_code, "value")
                    else str(bank_account.currency_code)
                )

                results.append(
                    DiscountBankAccountOption(
                        bank_account_id=bank_account.id,
                        bank_name=bank.name,
                        account_name=bank_account.account_name,
                        currency_code=currency_code,
                    )
                )

            return results

    def _fill_bank_account_combo(self) -> None:
        previous_signal_state = self.bank_account_combo.blockSignals(True)

        try:
            self.bank_account_combo.clear()

            if not self.bank_accounts:
                self.bank_account_combo.addItem("Aktif banka hesabı yok", None)
                return

            self.bank_account_combo.addItem("İskonto hesabı seçiniz", None)

            for bank_account in self.bank_accounts:
                self.bank_account_combo.addItem(
                    f"{bank_account.bank_name} / {bank_account.account_name} / {bank_account.currency_code}",
                    bank_account.bank_account_id,
                )
        finally:
            self.bank_account_combo.blockSignals(previous_signal_state)

    def has_discountable_checks(self) -> bool:
        return bool(self.discountable_checks)

    def get_missing_data_message(self) -> str:
        return (
            "İskontoya verilebilecek PORTFOLIO, GIVEN_TO_BANK veya IN_COLLECTION durumunda "
            "alınan çek kaydı bulunamadı."
        )

    def _selected_bank_account_id(self) -> int | None:
        current_data = self.bank_account_combo.currentData()

        if current_data in {None, ""}:
            return None

        try:
            return int(current_data)
        except (TypeError, ValueError):
            return None

    def _selected_bank_account(self) -> DiscountBankAccountOption | None:
        selected_bank_account_id = self._selected_bank_account_id()

        if selected_bank_account_id is None:
            return None

        return self.bank_account_lookup.get(selected_bank_account_id)

    def _selected_day_basis(self) -> int:
        try:
            return int(self.day_basis_combo.currentData())
        except (TypeError, ValueError):
            return 365

    def _current_discount_date(self) -> date:
        return _qdate_to_date(self.discount_date_edit.date())

    def _bank_account_changed(self) -> None:
        self.selected_check_ids.clear()
        self._apply_filters()

    def _eligible_checks_for_selected_bank_and_date(self) -> list[DiscountableReceivedCheckOption]:
        selected_bank_account = self._selected_bank_account()
        discount_date = self._current_discount_date()

        eligible_checks = [
            discountable_check
            for discountable_check in self.discountable_checks
            if discountable_check.due_date >= discount_date
        ]

        if selected_bank_account is not None:
            eligible_checks = [
                discountable_check
                for discountable_check in eligible_checks
                if discountable_check.currency_code == selected_bank_account.currency_code
            ]

        return eligible_checks

    def _matches_search(self, discountable_check: DiscountableReceivedCheckOption, search_text: str) -> bool:
        if not search_text:
            return True

        normalized_search_text = search_text.strip().lower()

        collection_text = (
            f"{discountable_check.collection_bank_name} / {discountable_check.collection_bank_account_name}"
            if discountable_check.collection_bank_name and discountable_check.collection_bank_account_name
            else ""
        )

        searchable_text = " | ".join(
            [
                str(discountable_check.received_check_id),
                discountable_check.customer_name,
                discountable_check.check_number,
                discountable_check.drawer_bank_name,
                collection_text,
                discountable_check.reference_no or "",
                discountable_check.received_date.strftime("%d.%m.%Y"),
                discountable_check.due_date.strftime("%d.%m.%Y"),
                format_currency_amount(discountable_check.amount, discountable_check.currency_code),
            ]
        ).lower()

        return normalized_search_text in searchable_text

    def _apply_filters(self) -> None:
        search_text = self.search_input.text().strip()
        eligible_checks = self._eligible_checks_for_selected_bank_and_date()
        eligible_ids = {
            discountable_check.received_check_id
            for discountable_check in eligible_checks
        }

        self.selected_check_ids = {
            received_check_id
            for received_check_id in self.selected_check_ids
            if received_check_id in eligible_ids
        }

        filtered_checks = [
            discountable_check
            for discountable_check in eligible_checks
            if self._matches_search(discountable_check, search_text)
        ]

        filtered_checks.sort(
            key=lambda discountable_check: (
                discountable_check.due_date,
                discountable_check.customer_name.lower(),
                discountable_check.check_number.lower(),
                discountable_check.received_check_id,
            )
        )

        self._fill_table(filtered_checks)
        self._update_results_info_label(filtered_count=len(filtered_checks), eligible_count=len(eligible_checks))
        self._update_bank_account_info()
        self._update_preview()

    def _fill_table(self, filtered_checks: list[DiscountableReceivedCheckOption]) -> None:
        self.is_filling_table = True
        self.checks_table.setRowCount(len(filtered_checks))

        discount_date = self._current_discount_date()

        for row_index, discountable_check in enumerate(filtered_checks):
            days_to_due = (discountable_check.due_date - discount_date).days
            row_calculation = self._calculate_single_row_preview(discountable_check)

            interest_text = "-"
            commission_text = "-"
            bsiv_text = "-"
            net_text = "-"

            if row_calculation is not None:
                interest_text = format_currency_amount(
                    row_calculation.interest_expense_amount,
                    row_calculation.currency_code,
                )
                commission_text = format_currency_amount(
                    row_calculation.commission_amount,
                    row_calculation.currency_code,
                )
                bsiv_text = format_currency_amount(
                    row_calculation.bsiv_amount,
                    row_calculation.currency_code,
                )
                net_text = format_currency_amount(
                    row_calculation.net_amount,
                    row_calculation.currency_code,
                )

            values = [
                "",
                str(discountable_check.received_check_id),
                discountable_check.customer_name,
                discountable_check.check_number,
                discountable_check.drawer_bank_name,
                discountable_check.due_date.strftime("%d.%m.%Y"),
                str(days_to_due),
                format_currency_amount(discountable_check.amount, discountable_check.currency_code),
                interest_text,
                commission_text,
                bsiv_text,
                net_text,
                received_status_text(discountable_check.status),
            ]

            for column_index, value in enumerate(values):
                item = QTableWidgetItem(value)

                if column_index == 0:
                    item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                    item.setCheckState(
                        Qt.CheckState.Checked
                        if discountable_check.received_check_id in self.selected_check_ids
                        else Qt.CheckState.Unchecked
                    )
                    item.setData(Qt.UserRole, discountable_check.received_check_id)
                    item.setTextAlignment(Qt.AlignCenter)
                else:
                    item.setData(Qt.UserRole, discountable_check.received_check_id)

                if days_to_due <= 7:
                    item.setForeground(QColor("#38bdf8"))
                else:
                    item.setForeground(QColor("#e5e7eb"))

                if column_index in {6, 7, 8, 9, 10, 11}:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                elif column_index != 0:
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)

                tooltip_lines = [
                    f"ID: {discountable_check.received_check_id}",
                    f"Müşteri: {discountable_check.customer_name}",
                    f"Çek No: {discountable_check.check_number}",
                    f"Keşideci Banka: {discountable_check.drawer_bank_name}",
                    f"Durum: {received_status_text(discountable_check.status)}",
                    f"Alınış: {discountable_check.received_date.strftime('%d.%m.%Y')}",
                    f"Vade: {discountable_check.due_date.strftime('%d.%m.%Y')}",
                    f"Vadeye kalan gün: {days_to_due}",
                    f"Tutar: {format_currency_amount(discountable_check.amount, discountable_check.currency_code)}",
                ]

                if row_calculation is not None:
                    tooltip_lines.extend(
                        [
                            f"Faiz kesintisi: {interest_text}",
                            f"Komisyon: {commission_text}",
                            f"BSİV: {bsiv_text}",
                            f"Net: {net_text}",
                        ]
                    )

                if discountable_check.collection_bank_name and discountable_check.collection_bank_account_name:
                    tooltip_lines.append(
                        f"Mevcut tahsil hesabı: {discountable_check.collection_bank_name} / "
                        f"{discountable_check.collection_bank_account_name}"
                    )

                if discountable_check.reference_no:
                    tooltip_lines.append(f"Referans No: {discountable_check.reference_no}")

                item.setToolTip("\n".join(tooltip_lines))
                self.checks_table.setItem(row_index, column_index, item)

        self.checks_table.resizeRowsToContents()
        self.is_filling_table = False

    def _update_results_info_label(self, *, filtered_count: int, eligible_count: int) -> None:
        total_count = len(self.discountable_checks)
        selected_bank_account = self._selected_bank_account()
        eligible_drawer_bank_count = len(
            {
                str(discountable_check.drawer_bank_name or "").strip().lower()
                for discountable_check in self._eligible_checks_for_selected_bank_and_date()
                if str(discountable_check.drawer_bank_name or "").strip()
            }
        )

        if total_count == 0:
            self.results_info_label.setText("İskontoya verilebilecek açık alınan çek kaydı bulunamadı.")
            return

        if selected_bank_account is None:
            self.results_info_label.setText(
                f"Toplam {total_count} uygun çek var. Liste karışık para birimi gösterebilir. "
                "İşlem için önce iskonto hesabı seçmelisin. Farklı keşideci bankalara ait çekler aynı pakete eklenebilir."
            )
            return

        if eligible_count == 0:
            self.results_info_label.setText(
                f"Seçilen iskonto hesabının para birimi {selected_bank_account.currency_code}. "
                "Bu para biriminde ve seçili iskonto tarihine göre uygun çek bulunamadı. Keşideci banka filtresi uygulanmaz."
            )
            return

        if filtered_count == 0:
            self.results_info_label.setText(
                "Filtreye uygun kayıt bulunamadı. Arama metnini değiştir."
            )
            return

        drawer_bank_text = (
            f" {eligible_drawer_bank_count} farklı keşideci banka var."
            if eligible_drawer_bank_count > 0
            else ""
        )

        self.results_info_label.setText(
            f"Seçilen iskonto hesabı para birimi: {selected_bank_account.currency_code}. "
            f"{eligible_count} uygun çek içinden {filtered_count} kayıt listeleniyor."
            f"{drawer_bank_text} Farklı keşideci bankalara ait çekler aynı iskonto paketine eklenebilir."
        )

    def _update_bank_account_info(self) -> None:
        selected_bank_account = self._selected_bank_account()

        if selected_bank_account is None:
            self.bank_account_info_label.setText(
                "Çoklu iskonto paketinde seçilen çeklerin para birimi ile iskonto hesabı para birimi aynı olmalıdır. "
                "Keşideci banka kısıtı yoktur."
            )
            return

        self.bank_account_info_label.setText(
            f"Seçili iskonto hesabı: {selected_bank_account.bank_name} / "
            f"{selected_bank_account.account_name} / {selected_bank_account.currency_code}. "
            "Bu hesaba aynı para birimindeki farklı keşideci bankalara ait çekler birlikte kırdırılabilir."
        )

    def _table_item_changed(self, item: QTableWidgetItem) -> None:
        if self.is_filling_table:
            return

        if item.column() != 0:
            return

        received_check_id = item.data(Qt.UserRole)

        try:
            normalized_received_check_id = int(received_check_id)
        except (TypeError, ValueError):
            return

        if item.checkState() == Qt.CheckState.Checked:
            self.selected_check_ids.add(normalized_received_check_id)
        else:
            self.selected_check_ids.discard(normalized_received_check_id)

        self._update_preview()

    def _build_check_input(self, discountable_check: DiscountableReceivedCheckOption) -> DiscountBatchCheckInput:
        return DiscountBatchCheckInput(
            received_check_id=discountable_check.received_check_id,
            check_number=discountable_check.check_number,
            due_date=discountable_check.due_date,
            gross_amount=discountable_check.amount,
            currency_code=discountable_check.currency_code,
        )

    def _selected_check_inputs(self) -> list[DiscountBatchCheckInput]:
        selected_checks = [
            self.check_lookup[received_check_id]
            for received_check_id in sorted(self.selected_check_ids)
            if received_check_id in self.check_lookup
        ]

        selected_checks.sort(
            key=lambda discountable_check: (
                discountable_check.due_date,
                discountable_check.customer_name.lower(),
                discountable_check.check_number.lower(),
                discountable_check.received_check_id,
            )
        )

        return [
            self._build_check_input(discountable_check)
            for discountable_check in selected_checks
        ]

    def _can_attempt_calculation(self) -> bool:
        return bool(self.annual_interest_rate_input.text().strip()) and bool(
            self.commission_rate_input.text().strip()
        )

    def _calculate_single_row_preview(self, discountable_check: DiscountableReceivedCheckOption):
        if not self._can_attempt_calculation():
            return None

        try:
            result = calculate_received_check_discount_batch(
                checks=[self._build_check_input(discountable_check)],
                discount_date=self._current_discount_date(),
                annual_interest_rate=self.annual_interest_rate_input.text().strip(),
                commission_rate=self.commission_rate_input.text().strip(),
                bsiv_rate=self.bsiv_rate_input.text().strip(),
                day_basis=self._selected_day_basis(),
            )
        except ReceivedCheckDiscountBatchServiceError:
            return None

        if not result.item_calculations:
            return None

        return result.item_calculations[0]

    def _update_preview(self) -> None:
        selected_check_inputs = self._selected_check_inputs()

        self.selected_count_label.value_label.setText(str(len(selected_check_inputs)))

        if not selected_check_inputs:
            self.total_gross_label.value_label.setText("-")
            self.weighted_average_days_label.value_label.setText("-")
            self.total_interest_label.value_label.setText("-")
            self.total_commission_label.value_label.setText("-")
            self.total_bsiv_label.value_label.setText("-")
            self.net_bank_amount_label.value_label.setText("-")
            self.save_button.setEnabled(False)
            return

        if not self._can_attempt_calculation():
            currency_code = selected_check_inputs[0].currency_code
            total_gross_amount = sum(
                (item.gross_amount for item in selected_check_inputs),
                Decimal("0.00"),
            )

            self.total_gross_label.value_label.setText(
                format_currency_amount(total_gross_amount, currency_code)
            )
            self.weighted_average_days_label.value_label.setText("-")
            self.total_interest_label.value_label.setText("-")
            self.total_commission_label.value_label.setText("-")
            self.total_bsiv_label.value_label.setText("-")
            self.net_bank_amount_label.value_label.setText("-")
            self.save_button.setEnabled(False)
            return

        try:
            calculation_result = calculate_received_check_discount_batch(
                checks=selected_check_inputs,
                discount_date=self._current_discount_date(),
                annual_interest_rate=self.annual_interest_rate_input.text().strip(),
                commission_rate=self.commission_rate_input.text().strip(),
                bsiv_rate=self.bsiv_rate_input.text().strip(),
                day_basis=self._selected_day_basis(),
            )
        except ReceivedCheckDiscountBatchServiceError as exc:
            self.total_gross_label.value_label.setText("-")
            self.weighted_average_days_label.value_label.setText("-")
            self.total_interest_label.value_label.setText("-")
            self.total_commission_label.value_label.setText("-")
            self.total_bsiv_label.value_label.setText("-")
            self.net_bank_amount_label.value_label.setText("-")
            self.net_bank_amount_label.hint_label.setText(str(exc))
            self.save_button.setEnabled(False)
            return

        self.net_bank_amount_label.hint_label.setText("")

        self.total_gross_label.value_label.setText(
            format_currency_amount(
                calculation_result.total_gross_amount,
                calculation_result.currency_code,
            )
        )
        self.weighted_average_days_label.value_label.setText(
            f"{_format_days(calculation_result.weighted_average_days_to_due)} gün"
        )
        self.total_interest_label.value_label.setText(
            format_currency_amount(
                calculation_result.total_interest_expense_amount,
                calculation_result.currency_code,
            )
        )
        self.total_commission_label.value_label.setText(
            format_currency_amount(
                calculation_result.total_commission_amount,
                calculation_result.currency_code,
            )
        )
        self.total_bsiv_label.value_label.setText(
            format_currency_amount(
                calculation_result.total_bsiv_amount,
                calculation_result.currency_code,
            )
        )
        self.net_bank_amount_label.value_label.setText(
            format_currency_amount(
                calculation_result.net_bank_amount,
                calculation_result.currency_code,
            )
        )
        self.save_button.setEnabled(self._selected_bank_account_id() is not None)

    def _build_payload(self) -> dict[str, Any]:
        bank_account_id = self._selected_bank_account_id()

        if bank_account_id is None:
            raise ValueError("İskonto hesabı seçilmelidir.")

        selected_check_inputs = self._selected_check_inputs()

        if not selected_check_inputs:
            raise ValueError("İskonto paketi için en az bir çek seçilmelidir.")

        if not self.annual_interest_rate_input.text().strip():
            raise ValueError("Yıllık faiz oranı girilmelidir.")

        if not self.commission_rate_input.text().strip():
            raise ValueError("Komisyon oranı girilmelidir.")

        if not self.bsiv_rate_input.text().strip():
            raise ValueError("BSİV oranı girilmelidir.")

        calculate_received_check_discount_batch(
            checks=selected_check_inputs,
            discount_date=self._current_discount_date(),
            annual_interest_rate=self.annual_interest_rate_input.text().strip(),
            commission_rate=self.commission_rate_input.text().strip(),
            bsiv_rate=self.bsiv_rate_input.text().strip(),
            day_basis=self._selected_day_basis(),
        )

        return {
            "bank_account_id": bank_account_id,
            "received_check_ids": [
                item.received_check_id
                for item in selected_check_inputs
            ],
            "discount_date": self._current_discount_date(),
            "annual_interest_rate": self.annual_interest_rate_input.text().strip(),
            "commission_rate": self.commission_rate_input.text().strip(),
            "bsiv_rate": self.bsiv_rate_input.text().strip(),
            "day_basis": self._selected_day_basis(),
            "reference_no": self.reference_no_input.text().strip() or None,
            "description": self.description_input.toPlainText().strip() or None,
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