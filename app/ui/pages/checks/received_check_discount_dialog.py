from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QFormLayout,
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
from app.ui.pages.banks.bank_dialog_styles import BANK_DIALOG_STYLES
from app.ui.ui_helpers import tr_money


@dataclass
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


@dataclass
class DiscountBankAccountOption:
    bank_account_id: int
    bank_name: str
    account_name: str
    currency_code: str


def _format_decimal_tr(value: Any) -> str:
    try:
        amount = Decimal(str(value))
    except Exception:
        amount = Decimal("0.00")

    formatted = f"{amount:,.2f}"
    formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")

    return formatted


def _format_currency_amount(value: Any, currency_code: str) -> str:
    normalized_currency_code = str(currency_code or "").strip().upper()

    if normalized_currency_code == "TRY":
        return tr_money(value)

    return f"{_format_decimal_tr(value)} {normalized_currency_code}"


def _parse_decimal_input(value: str) -> Decimal:
    text_value = str(value or "").strip().replace(" ", "")

    if not text_value:
        return Decimal("0.00")

    if "," in text_value and "." in text_value:
        text_value = text_value.replace(".", "").replace(",", ".")
    elif "," in text_value:
        text_value = text_value.replace(",", ".")

    try:
        return Decimal(text_value)
    except InvalidOperation:
        return Decimal("0.00")


def _received_status_text(status: str) -> str:
    normalized_status = str(status or "").strip().upper()

    if normalized_status == "PORTFOLIO":
        return "Portföy"

    if normalized_status == "GIVEN_TO_BANK":
        return "Bankaya Verildi"

    if normalized_status == "IN_COLLECTION":
        return "Tahsilde"

    if normalized_status == "COLLECTED":
        return "Tahsil Edildi"

    if normalized_status == "BOUNCED":
        return "Karşılıksız"

    if normalized_status == "RETURNED":
        return "İade"

    if normalized_status == "ENDORSED":
        return "Ciro Edildi"

    if normalized_status == "DISCOUNTED":
        return "İskontoya Verildi"

    if normalized_status == "CANCELLED":
        return "İptal"

    return normalized_status


def _qdate_to_date(qdate: QDate) -> date:
    return date(qdate.year(), qdate.month(), qdate.day())


class ReceivedCheckDiscountDialog(QDialog):
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

        self.filtered_check_ids: list[int] = []
        self.payload: dict[str, Any] | None = None

        self.setWindowTitle("Alınan Çeki İskontoya Ver / Kırdır")
        self.resize(1100, 790)
        self.setMinimumSize(940, 680)
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

            QLabel#PreviewValue {
                color: #e5e7eb;
                font-size: 18px;
                font-weight: 700;
            }

            QLabel#PreviewTitle {
                color: #94a3b8;
                font-size: 11px;
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
        main_layout.setSpacing(16)

        title = QLabel("Alınan Çeki İskontoya Ver / Kırdır")
        title.setObjectName("SectionTitle")

        subtitle = QLabel(
            "Portföyde, bankaya verilmiş veya tahsilde olan alınan çeki seçer, aynı para birimindeki banka hesabına "
            "iskonto sonrası net tutar kadar giriş oluşturursun. Brüt tutar, iskonto masrafı ve net banka girişi "
            "canlı olarak hesaplanır."
        )
        subtitle.setObjectName("MutedText")
        subtitle.setWordWrap(True)

        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(12)

        self.search_input = QLineEdit()
        self.search_input.setMinimumHeight(40)
        self.search_input.setPlaceholderText("Müşteri / çek no / banka / referans ara")
        self.search_input.textChanged.connect(self._apply_filters)

        self.due_filter_combo = QComboBox()
        self.due_filter_combo.setMinimumHeight(40)
        self.due_filter_combo.addItem("Gecikenler + 7 Gün İçinde", "OVERDUE_AND_NEXT_7_DAYS")
        self.due_filter_combo.addItem("Gecikenler", "OVERDUE")
        self.due_filter_combo.addItem("Bugün Vadeli", "TODAY")
        self.due_filter_combo.addItem("7 Gün İçinde", "NEXT_7_DAYS")
        self.due_filter_combo.addItem("30 Gün İçinde", "NEXT_30_DAYS")
        self.due_filter_combo.addItem("Tümü", "ALL")
        self.due_filter_combo.currentIndexChanged.connect(self._apply_filters)

        filter_layout.addWidget(self.search_input, 3)
        filter_layout.addWidget(self.due_filter_combo, 1)

        self.results_info_label = QLabel("")
        self.results_info_label.setObjectName("MutedText")
        self.results_info_label.setWordWrap(True)

        self.checks_table = QTableWidget()
        self.checks_table.setColumnCount(8)
        self.checks_table.setHorizontalHeaderLabels(
            [
                "ID",
                "Müşteri",
                "Çek No",
                "Keşideci Banka",
                "Alınış",
                "Vade",
                "Tutar",
                "Durum",
            ]
        )
        self.checks_table.verticalHeader().setVisible(False)
        self.checks_table.setAlternatingRowColors(False)
        self.checks_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.checks_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.checks_table.setMinimumHeight(250)
        self.checks_table.setWordWrap(False)
        self.checks_table.setTextElideMode(Qt.ElideRight)
        self.checks_table.verticalHeader().setDefaultSectionSize(34)
        self.checks_table.verticalHeader().setMinimumSectionSize(30)
        self.checks_table.itemSelectionChanged.connect(self._update_selected_check_info)

        checks_header = self.checks_table.horizontalHeader()
        checks_header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        checks_header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        checks_header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        checks_header.setSectionResizeMode(3, QHeaderView.Stretch)
        checks_header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        checks_header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        checks_header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        checks_header.setSectionResizeMode(7, QHeaderView.ResizeToContents)

        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        form_layout.setFormAlignment(Qt.AlignTop)
        form_layout.setHorizontalSpacing(18)
        form_layout.setVerticalSpacing(14)

        self.info_label = QLabel("")
        self.info_label.setObjectName("MutedText")
        self.info_label.setWordWrap(True)
        form_layout.addRow("Seçili çek", self.info_label)

        self.bank_account_combo = QComboBox()
        self.bank_account_combo.setMinimumHeight(38)
        self.bank_account_combo.currentIndexChanged.connect(self._update_bank_account_info)
        self.bank_account_combo.currentIndexChanged.connect(self._update_preview)
        form_layout.addRow("Banka hesabı", self.bank_account_combo)

        self.bank_account_info_label = QLabel("")
        self.bank_account_info_label.setObjectName("MutedText")
        self.bank_account_info_label.setWordWrap(True)
        form_layout.addRow("", self.bank_account_info_label)

        self.discount_date_edit = QDateEdit()
        self.discount_date_edit.setMinimumHeight(38)
        self.discount_date_edit.setCalendarPopup(True)
        self.discount_date_edit.setDisplayFormat("dd.MM.yyyy")
        self.discount_date_edit.setDate(QDate.currentDate())
        form_layout.addRow("İskonto tarihi", self.discount_date_edit)

        self.discount_rate_input = QLineEdit()
        self.discount_rate_input.setMinimumHeight(38)
        self.discount_rate_input.setPlaceholderText("Örn: 3,50")
        self.discount_rate_input.textChanged.connect(self._update_preview)
        form_layout.addRow("İskonto oranı (%)", self.discount_rate_input)

        self.reference_no_combo = QComboBox()
        self.reference_no_combo.setEditable(True)
        self.reference_no_combo.setMinimumHeight(38)
        self.reference_no_combo.setInsertPolicy(QComboBox.NoInsert)
        form_layout.addRow("Referans no", self.reference_no_combo)

        self.description_input = QTextEdit()
        self.description_input.setPlaceholderText("İsteğe bağlı açıklama")
        self.description_input.setFixedHeight(88)
        form_layout.addRow("Açıklama", self.description_input)

        preview_layout = self._build_preview_layout()

        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)

        self.save_button = QPushButton("İskonto İşlemini Kaydet")
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
        main_layout.addLayout(filter_layout)
        main_layout.addWidget(self.results_info_label)
        main_layout.addWidget(self.checks_table)
        main_layout.addSpacing(4)
        main_layout.addLayout(form_layout)
        main_layout.addSpacing(4)
        main_layout.addLayout(preview_layout)
        main_layout.addSpacing(8)
        main_layout.addLayout(button_layout)

        scroll_area.setWidget(content_widget)
        outer_layout.addWidget(scroll_area)

        self._apply_filters()
        self._update_preview()

    def _build_preview_layout(self) -> QGridLayout:
        preview_layout = QGridLayout()
        preview_layout.setSpacing(12)
        preview_layout.setColumnStretch(0, 1)
        preview_layout.setColumnStretch(1, 1)
        preview_layout.setColumnStretch(2, 1)

        gross_box = self._build_preview_box("BRÜT ÇEK TUTARI")
        expense_box = self._build_preview_box("İSKONTO MASRAFI")
        net_box = self._build_preview_box("NET BANKA GİRİŞİ")

        self.gross_amount_label = gross_box.findChild(QLabel, "PreviewValue")
        self.discount_expense_label = expense_box.findChild(QLabel, "PreviewValue")
        self.net_bank_amount_label = net_box.findChild(QLabel, "PreviewValue")

        preview_layout.addWidget(gross_box, 0, 0)
        preview_layout.addWidget(expense_box, 0, 1)
        preview_layout.addWidget(net_box, 0, 2)

        return preview_layout

    def _build_preview_box(self, title_text: str) -> QWidget:
        box = QWidget()
        box.setObjectName("PreviewBox")

        layout = QVBoxLayout(box)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)

        title = QLabel(title_text)
        title.setObjectName("PreviewTitle")

        value = QLabel("-")
        value.setObjectName("PreviewValue")
        value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        layout.addWidget(title)
        layout.addWidget(value)

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
                        collection_bank_account_name=collection_bank_account.account_name if collection_bank_account else None,
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

    def has_discountable_checks(self) -> bool:
        return bool(self.discountable_checks)

    def get_missing_data_message(self) -> str:
        return (
            "İskontoya verilebilecek PORTFOLIO, GIVEN_TO_BANK veya IN_COLLECTION durumunda "
            "alınan çek kaydı bulunamadı."
        )

    def _matches_search(self, discountable_check: DiscountableReceivedCheckOption, search_text: str) -> bool:
        if not search_text:
            return True

        normalized_search_text = search_text.strip().lower()

        searchable_text = " | ".join(
            [
                str(discountable_check.received_check_id),
                discountable_check.customer_name,
                discountable_check.check_number,
                discountable_check.drawer_bank_name,
                discountable_check.reference_no or "",
                discountable_check.collection_bank_name or "",
                discountable_check.collection_bank_account_name or "",
                discountable_check.received_date.strftime("%d.%m.%Y"),
                discountable_check.due_date.strftime("%d.%m.%Y"),
                _format_currency_amount(discountable_check.amount, discountable_check.currency_code),
            ]
        ).lower()

        return normalized_search_text in searchable_text

    def _matches_due_filter(self, discountable_check: DiscountableReceivedCheckOption, filter_key: str) -> bool:
        today = date.today()
        due_date = discountable_check.due_date

        if filter_key == "OVERDUE_AND_NEXT_7_DAYS":
            return due_date < today or due_date <= today + timedelta(days=7)

        if filter_key == "OVERDUE":
            return due_date < today

        if filter_key == "TODAY":
            return due_date == today

        if filter_key == "NEXT_7_DAYS":
            return today <= due_date <= today + timedelta(days=7)

        if filter_key == "NEXT_30_DAYS":
            return today <= due_date <= today + timedelta(days=30)

        return True

    def _apply_filters(self) -> None:
        search_text = self.search_input.text().strip()
        filter_key = str(self.due_filter_combo.currentData() or "ALL").strip().upper()

        filtered_checks = [
            discountable_check
            for discountable_check in self.discountable_checks
            if self._matches_search(discountable_check, search_text)
            and self._matches_due_filter(discountable_check, filter_key)
        ]

        filtered_checks.sort(
            key=lambda discountable_check: (
                discountable_check.due_date,
                discountable_check.customer_name.lower(),
                discountable_check.check_number.lower(),
                discountable_check.received_check_id,
            )
        )

        self.filtered_check_ids = [
            discountable_check.received_check_id
            for discountable_check in filtered_checks
        ]

        self._fill_table(filtered_checks)
        self._update_results_info_label(len(filtered_checks))
        self._select_first_row_if_available()
        self._update_selected_check_info()

    def _fill_table(self, filtered_checks: list[DiscountableReceivedCheckOption]) -> None:
        self.checks_table.setRowCount(len(filtered_checks))

        today = date.today()

        for row_index, discountable_check in enumerate(filtered_checks):
            values = [
                str(discountable_check.received_check_id),
                discountable_check.customer_name,
                discountable_check.check_number,
                discountable_check.drawer_bank_name,
                discountable_check.received_date.strftime("%d.%m.%Y"),
                discountable_check.due_date.strftime("%d.%m.%Y"),
                _format_currency_amount(discountable_check.amount, discountable_check.currency_code),
                _received_status_text(discountable_check.status),
            ]

            is_overdue = discountable_check.due_date < today
            is_due_soon = today <= discountable_check.due_date <= today + timedelta(days=7)

            for column_index, value in enumerate(values):
                item = QTableWidgetItem(value)

                if is_overdue:
                    item.setForeground(QColor("#f59e0b"))
                elif is_due_soon:
                    item.setForeground(QColor("#38bdf8"))
                else:
                    item.setForeground(QColor("#e5e7eb"))

                if column_index == 6:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                else:
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)

                if column_index == 0:
                    item.setData(Qt.UserRole, discountable_check.received_check_id)

                tooltip_lines = [
                    f"ID: {discountable_check.received_check_id}",
                    f"Müşteri: {discountable_check.customer_name}",
                    f"Çek No: {discountable_check.check_number}",
                    f"Keşideci Banka: {discountable_check.drawer_bank_name}",
                    f"Durum: {_received_status_text(discountable_check.status)}",
                    f"Alınış: {discountable_check.received_date.strftime('%d.%m.%Y')}",
                    f"Vade: {discountable_check.due_date.strftime('%d.%m.%Y')}",
                    f"Tutar: {_format_currency_amount(discountable_check.amount, discountable_check.currency_code)}",
                ]

                if discountable_check.collection_bank_name and discountable_check.collection_bank_account_name:
                    tooltip_lines.append(
                        f"Mevcut Tahsil Hesabı: "
                        f"{discountable_check.collection_bank_name} / "
                        f"{discountable_check.collection_bank_account_name}"
                    )

                if discountable_check.reference_no:
                    tooltip_lines.append(f"Referans No: {discountable_check.reference_no}")

                item.setToolTip("\n".join(tooltip_lines))
                self.checks_table.setItem(row_index, column_index, item)

        self.checks_table.resizeRowsToContents()

    def _update_results_info_label(self, filtered_count: int) -> None:
        total_count = len(self.discountable_checks)

        if total_count == 0:
            self.results_info_label.setText(
                "İskontoya verilebilecek açık alınan çek kaydı bulunamadı."
            )
            return

        if filtered_count == 0:
            self.results_info_label.setText(
                "Filtreye uygun kayıt bulunamadı. Arama metnini veya vade filtresini değiştir."
            )
            return

        self.results_info_label.setText(
            f"Toplam {total_count} uygun alınan çek içinden {filtered_count} kayıt listeleniyor. "
            "Liste vade tarihine göre sıralıdır."
        )

    def _select_first_row_if_available(self) -> None:
        if self.checks_table.rowCount() <= 0:
            self.checks_table.clearSelection()
            return

        self.checks_table.setCurrentCell(0, 0)
        self.checks_table.selectRow(0)

    def _selected_check_from_table(self) -> DiscountableReceivedCheckOption | None:
        current_row = self.checks_table.currentRow()

        if current_row < 0:
            return None

        id_item = self.checks_table.item(current_row, 0)

        if id_item is None:
            return None

        received_check_id = id_item.data(Qt.UserRole)

        try:
            normalized_received_check_id = int(received_check_id)
        except (TypeError, ValueError):
            return None

        return self.check_lookup.get(normalized_received_check_id)

    def _fill_bank_account_combo_for_selected_check(self, selected_check: DiscountableReceivedCheckOption | None) -> None:
        self.bank_account_combo.blockSignals(True)
        self.bank_account_combo.clear()

        if selected_check is None:
            self.bank_account_combo.addItem("Önce çek seçiniz", None)
            self.bank_account_combo.blockSignals(False)
            return

        matching_accounts = [
            bank_account
            for bank_account in self.bank_accounts
            if bank_account.currency_code == selected_check.currency_code
        ]

        self.bank_account_combo.addItem("Seçilmedi", None)

        selected_index = 0

        for bank_account in matching_accounts:
            text = (
                f"{bank_account.bank_name} / "
                f"{bank_account.account_name} / "
                f"{bank_account.currency_code}"
            )
            self.bank_account_combo.addItem(text, bank_account.bank_account_id)

            if (
                selected_check.collection_bank_account_id is not None
                and bank_account.bank_account_id == selected_check.collection_bank_account_id
            ):
                selected_index = self.bank_account_combo.count() - 1

        self.bank_account_combo.setCurrentIndex(selected_index)
        self.bank_account_combo.blockSignals(False)

    def _selected_bank_account_id(self) -> int | None:
        current_data = self.bank_account_combo.currentData()

        if current_data in {None, ""}:
            return None

        try:
            return int(current_data)
        except (TypeError, ValueError):
            return None

    def _update_bank_account_info(self) -> None:
        selected_check = self._selected_check_from_table()

        if selected_check is None:
            self.bank_account_info_label.setText("")
            return

        selected_bank_account_id = self._selected_bank_account_id()

        if selected_bank_account_id is None:
            self.bank_account_info_label.setText(
                f"Bu çek {selected_check.currency_code} para birimindedir. "
                "İskonto işlemi için aynı para biriminde aktif banka hesabı seçilmelidir."
            )
            return

        selected_bank_account = self.bank_account_lookup.get(selected_bank_account_id)

        if selected_bank_account is None:
            self.bank_account_info_label.setText("Seçilen banka hesabı bulunamadı.")
            return

        self.bank_account_info_label.setText(
            f"Seçili banka hesabı: {selected_bank_account.bank_name} / "
            f"{selected_bank_account.account_name} / "
            f"{selected_bank_account.currency_code}"
        )

    def _update_selected_check_info(self) -> None:
        selected_check = self._selected_check_from_table()
        self._fill_bank_account_combo_for_selected_check(selected_check)

        if selected_check is None:
            self.info_label.setText("İskonto için önce listeden bir çek seçmelisin.")
            self.reference_no_combo.clear()
            self.bank_account_info_label.setText("")
            self.save_button.setEnabled(False)
            self._update_preview()
            return

        current_collection_text = "-"
        if selected_check.collection_bank_name and selected_check.collection_bank_account_name:
            current_collection_text = (
                f"{selected_check.collection_bank_name} / {selected_check.collection_bank_account_name}"
            )

        self.info_label.setText(
            f"Müşteri: {selected_check.customer_name}\n"
            f"Keşideci Banka: {selected_check.drawer_bank_name}\n"
            f"Mevcut Tahsil Hesabı: {current_collection_text}\n"
            f"Durum: {_received_status_text(selected_check.status)}\n"
            f"Alınış: {selected_check.received_date.strftime('%d.%m.%Y')} | "
            f"Vade: {selected_check.due_date.strftime('%d.%m.%Y')}\n"
            f"Çek tutarı: {_format_currency_amount(selected_check.amount, selected_check.currency_code)}"
        )

        self.reference_no_combo.clear()

        if selected_check.reference_no:
            self.reference_no_combo.addItem(selected_check.reference_no)

        self.reference_no_combo.setEditText(selected_check.reference_no or "")
        self._update_bank_account_info()
        self.save_button.setEnabled(True)
        self._update_preview()

    def _update_preview(self) -> None:
        selected_check = self._selected_check_from_table()

        if selected_check is None:
            self.gross_amount_label.setText("-")
            self.discount_expense_label.setText("-")
            self.net_bank_amount_label.setText("-")
            return

        discount_rate = _parse_decimal_input(self.discount_rate_input.text())

        gross_amount = selected_check.amount
        discount_expense_amount = (gross_amount * discount_rate / Decimal("100")).quantize(Decimal("0.01"))
        net_bank_amount = (gross_amount - discount_expense_amount).quantize(Decimal("0.01"))

        if discount_rate <= Decimal("0"):
            discount_expense_amount = Decimal("0.00")
            net_bank_amount = gross_amount

        if net_bank_amount < Decimal("0.00"):
            net_bank_amount = Decimal("0.00")

        self.gross_amount_label.setText(
            _format_currency_amount(gross_amount, selected_check.currency_code)
        )
        self.discount_expense_label.setText(
            _format_currency_amount(discount_expense_amount, selected_check.currency_code)
        )
        self.net_bank_amount_label.setText(
            _format_currency_amount(net_bank_amount, selected_check.currency_code)
        )

    def _build_payload(self) -> dict[str, Any]:
        selected_check = self._selected_check_from_table()

        if selected_check is None:
            raise ValueError("İskontoya verilecek çek seçilmelidir.")

        bank_account_id = self._selected_bank_account_id()

        if bank_account_id is None:
            raise ValueError("Banka hesabı seçilmelidir.")

        discount_rate = _parse_decimal_input(self.discount_rate_input.text())

        if discount_rate <= Decimal("0"):
            raise ValueError("İskonto oranı sıfırdan büyük olmalıdır.")

        if discount_rate >= Decimal("100"):
            raise ValueError("İskonto oranı 100'den küçük olmalıdır.")

        discount_date = _qdate_to_date(self.discount_date_edit.date())
        reference_no = self.reference_no_combo.currentText().strip()
        description = self.description_input.toPlainText().strip()

        return {
            "received_check_id": selected_check.received_check_id,
            "bank_account_id": bank_account_id,
            "discount_date": discount_date,
            "discount_rate": discount_rate,
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