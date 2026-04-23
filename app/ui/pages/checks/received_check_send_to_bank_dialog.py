from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QFormLayout,
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
class SendableReceivedCheckOption:
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
class CollectionBankAccountOption:
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


class ReceivedCheckSendToBankDialog(QDialog):
    def __init__(self, *, parent: QWidget | None) -> None:
        super().__init__(parent)

        self.sendable_checks = self._load_sendable_checks()
        self.collection_bank_accounts = self._load_collection_bank_accounts()

        self.check_lookup = {
            sendable_check.received_check_id: sendable_check
            for sendable_check in self.sendable_checks
        }
        self.collection_bank_account_lookup = {
            collection_bank_account.bank_account_id: collection_bank_account
            for collection_bank_account in self.collection_bank_accounts
        }

        self.filtered_check_ids: list[int] = []
        self.payload: dict[str, Any] | None = None

        self.setWindowTitle("Alınan Çeki Bankaya Tahsile Ver")
        self.resize(1080, 740)
        self.setMinimumSize(920, 640)
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

        title = QLabel("Alınan Çeki Bankaya Tahsile Ver")
        title.setObjectName("SectionTitle")

        subtitle = QLabel(
            "Portföydeki alınan çeki seçer, uygun banka hesabına tahsile gönderirsin. "
            "Bu işlem banka hesabına henüz para girişi oluşturmaz; sadece çek tahsil sürecine alınır."
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

        self.collection_account_combo = QComboBox()
        self.collection_account_combo.setMinimumHeight(38)
        self.collection_account_combo.currentIndexChanged.connect(self._update_collection_account_info)
        form_layout.addRow("Tahsil hesabı", self.collection_account_combo)

        self.collection_account_info_label = QLabel("")
        self.collection_account_info_label.setObjectName("MutedText")
        self.collection_account_info_label.setWordWrap(True)
        form_layout.addRow("", self.collection_account_info_label)

        self.sent_date_edit = QDateEdit()
        self.sent_date_edit.setMinimumHeight(38)
        self.sent_date_edit.setCalendarPopup(True)
        self.sent_date_edit.setDisplayFormat("dd.MM.yyyy")
        self.sent_date_edit.setDate(QDate.currentDate())
        form_layout.addRow("Bankaya veriliş tarihi", self.sent_date_edit)

        self.reference_no_combo = QComboBox()
        self.reference_no_combo.setEditable(True)
        self.reference_no_combo.setMinimumHeight(38)
        self.reference_no_combo.setInsertPolicy(QComboBox.NoInsert)
        form_layout.addRow("Referans no", self.reference_no_combo)

        self.description_input = QTextEdit()
        self.description_input.setPlaceholderText("İsteğe bağlı açıklama")
        self.description_input.setFixedHeight(88)
        form_layout.addRow("Açıklama", self.description_input)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)

        self.save_button = QPushButton("Bankaya Gönder")
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
        main_layout.addSpacing(8)
        main_layout.addLayout(button_layout)

        scroll_area.setWidget(content_widget)
        outer_layout.addWidget(scroll_area)

        self._apply_filters()

    def _load_sendable_checks(self) -> list[SendableReceivedCheckOption]:
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
                    ReceivedCheck.status == ReceivedCheckStatus.PORTFOLIO,
                    ReceivedCheck.collected_transaction_id.is_(None),
                )
                .order_by(ReceivedCheck.due_date.asc(), ReceivedCheck.id.asc())
            )

            rows = session.execute(statement).all()

            results: list[SendableReceivedCheckOption] = []

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
                    SendableReceivedCheckOption(
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

    def _load_collection_bank_accounts(self) -> list[CollectionBankAccountOption]:
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

            results: list[CollectionBankAccountOption] = []

            for bank_account, bank in rows:
                currency_code = (
                    bank_account.currency_code.value
                    if hasattr(bank_account.currency_code, "value")
                    else str(bank_account.currency_code)
                )

                results.append(
                    CollectionBankAccountOption(
                        bank_account_id=bank_account.id,
                        bank_name=bank.name,
                        account_name=bank_account.account_name,
                        currency_code=currency_code,
                    )
                )

            return results

    def has_sendable_checks(self) -> bool:
        return bool(self.sendable_checks)

    def get_missing_data_message(self) -> str:
        return "Bankaya tahsile gönderilebilecek PORTFOLIO durumunda alınan çek kaydı bulunamadı."

    def _matches_search(self, sendable_check: SendableReceivedCheckOption, search_text: str) -> bool:
        if not search_text:
            return True

        normalized_search_text = search_text.strip().lower()

        searchable_text = " | ".join(
            [
                str(sendable_check.received_check_id),
                sendable_check.customer_name,
                sendable_check.check_number,
                sendable_check.drawer_bank_name,
                sendable_check.reference_no or "",
                sendable_check.collection_bank_name or "",
                sendable_check.collection_bank_account_name or "",
                sendable_check.received_date.strftime("%d.%m.%Y"),
                sendable_check.due_date.strftime("%d.%m.%Y"),
                _format_currency_amount(sendable_check.amount, sendable_check.currency_code),
            ]
        ).lower()

        return normalized_search_text in searchable_text

    def _matches_due_filter(self, sendable_check: SendableReceivedCheckOption, filter_key: str) -> bool:
        today = date.today()
        due_date = sendable_check.due_date

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
            sendable_check
            for sendable_check in self.sendable_checks
            if self._matches_search(sendable_check, search_text)
            and self._matches_due_filter(sendable_check, filter_key)
        ]

        filtered_checks.sort(
            key=lambda sendable_check: (
                sendable_check.due_date,
                sendable_check.customer_name.lower(),
                sendable_check.check_number.lower(),
                sendable_check.received_check_id,
            )
        )

        self.filtered_check_ids = [sendable_check.received_check_id for sendable_check in filtered_checks]

        self._fill_table(filtered_checks)
        self._update_results_info_label(len(filtered_checks))
        self._select_first_row_if_available()
        self._update_selected_check_info()

    def _fill_table(self, filtered_checks: list[SendableReceivedCheckOption]) -> None:
        self.checks_table.setRowCount(len(filtered_checks))

        today = date.today()

        for row_index, sendable_check in enumerate(filtered_checks):
            values = [
                str(sendable_check.received_check_id),
                sendable_check.customer_name,
                sendable_check.check_number,
                sendable_check.drawer_bank_name,
                sendable_check.received_date.strftime("%d.%m.%Y"),
                sendable_check.due_date.strftime("%d.%m.%Y"),
                _format_currency_amount(sendable_check.amount, sendable_check.currency_code),
                _received_status_text(sendable_check.status),
            ]

            is_overdue = sendable_check.due_date < today
            is_due_soon = today <= sendable_check.due_date <= today + timedelta(days=7)

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
                    item.setData(Qt.UserRole, sendable_check.received_check_id)

                tooltip_lines = [
                    f"ID: {sendable_check.received_check_id}",
                    f"Müşteri: {sendable_check.customer_name}",
                    f"Çek No: {sendable_check.check_number}",
                    f"Keşideci Banka: {sendable_check.drawer_bank_name}",
                    f"Durum: {_received_status_text(sendable_check.status)}",
                    f"Alınış: {sendable_check.received_date.strftime('%d.%m.%Y')}",
                    f"Vade: {sendable_check.due_date.strftime('%d.%m.%Y')}",
                    f"Tutar: {_format_currency_amount(sendable_check.amount, sendable_check.currency_code)}",
                ]

                if sendable_check.collection_bank_name and sendable_check.collection_bank_account_name:
                    tooltip_lines.append(
                        f"Mevcut Tahsil Hesabı: {sendable_check.collection_bank_name} / {sendable_check.collection_bank_account_name}"
                    )

                if sendable_check.reference_no:
                    tooltip_lines.append(f"Referans No: {sendable_check.reference_no}")

                item.setToolTip("\n".join(tooltip_lines))
                self.checks_table.setItem(row_index, column_index, item)

        self.checks_table.resizeRowsToContents()

    def _update_results_info_label(self, filtered_count: int) -> None:
        total_count = len(self.sendable_checks)

        if total_count == 0:
            self.results_info_label.setText("Bankaya tahsile gönderilebilecek PORTFOLIO durumunda çek bulunamadı.")
            return

        if filtered_count == 0:
            self.results_info_label.setText(
                "Filtreye uygun kayıt bulunamadı. Arama metnini veya vade filtresini değiştir."
            )
            return

        self.results_info_label.setText(
            f"Toplam {total_count} portföy çeki içinden {filtered_count} kayıt listeleniyor. "
            "Liste vade tarihine göre sıralıdır."
        )

    def _select_first_row_if_available(self) -> None:
        if self.checks_table.rowCount() <= 0:
            self.checks_table.clearSelection()
            return

        self.checks_table.setCurrentCell(0, 0)
        self.checks_table.selectRow(0)

    def _selected_check_from_table(self) -> SendableReceivedCheckOption | None:
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

    def _fill_collection_account_combo_for_selected_check(self, selected_check: SendableReceivedCheckOption | None) -> None:
        self.collection_account_combo.blockSignals(True)
        self.collection_account_combo.clear()

        if selected_check is None:
            self.collection_account_combo.addItem("Önce çek seçiniz", None)
            self.collection_account_combo.blockSignals(False)
            return

        matching_accounts = [
            collection_bank_account
            for collection_bank_account in self.collection_bank_accounts
            if collection_bank_account.currency_code == selected_check.currency_code
        ]

        self.collection_account_combo.addItem("Seçilmedi", None)

        selected_index = 0

        for collection_bank_account in matching_accounts:
            text = (
                f"{collection_bank_account.bank_name} / "
                f"{collection_bank_account.account_name} / "
                f"{collection_bank_account.currency_code}"
            )
            self.collection_account_combo.addItem(text, collection_bank_account.bank_account_id)

            if (
                selected_check.collection_bank_account_id is not None
                and collection_bank_account.bank_account_id == selected_check.collection_bank_account_id
            ):
                selected_index = self.collection_account_combo.count() - 1

        self.collection_account_combo.setCurrentIndex(selected_index)
        self.collection_account_combo.blockSignals(False)

    def _selected_collection_account_id(self) -> int | None:
        current_data = self.collection_account_combo.currentData()

        if current_data in {None, ""}:
            return None

        try:
            return int(current_data)
        except (TypeError, ValueError):
            return None

    def _update_collection_account_info(self) -> None:
        selected_check = self._selected_check_from_table()

        if selected_check is None:
            self.collection_account_info_label.setText("")
            return

        selected_collection_account_id = self._selected_collection_account_id()

        if selected_collection_account_id is None:
            self.collection_account_info_label.setText(
                f"Bu çek {selected_check.currency_code} para birimindedir. "
                "Bankaya tahsile verme işlemi için aynı para biriminde aktif banka hesabı seçilmelidir."
            )
            return

        selected_collection_account = self.collection_bank_account_lookup.get(selected_collection_account_id)

        if selected_collection_account is None:
            self.collection_account_info_label.setText("Seçilen tahsil hesabı bulunamadı.")
            return

        self.collection_account_info_label.setText(
            f"Seçili tahsil hesabı: {selected_collection_account.bank_name} / "
            f"{selected_collection_account.account_name} / "
            f"{selected_collection_account.currency_code}"
        )

    def _update_selected_check_info(self) -> None:
        selected_check = self._selected_check_from_table()
        self._fill_collection_account_combo_for_selected_check(selected_check)

        if selected_check is None:
            self.info_label.setText("Bankaya göndermek için önce listeden bir çek seçmelisin.")
            self.reference_no_combo.clear()
            self.collection_account_info_label.setText("")
            self.save_button.setEnabled(False)
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
        self._update_collection_account_info()
        self.save_button.setEnabled(True)

    def _build_payload(self) -> dict[str, Any]:
        selected_check = self._selected_check_from_table()

        if selected_check is None:
            raise ValueError("Bankaya gönderilecek çek seçilmelidir.")

        collection_bank_account_id = self._selected_collection_account_id()

        if collection_bank_account_id is None:
            raise ValueError("Tahsil hesabı seçilmelidir.")

        sent_date = _qdate_to_date(self.sent_date_edit.date())
        reference_no = self.reference_no_combo.currentText().strip()
        description = self.description_input.toPlainText().strip()

        return {
            "received_check_id": selected_check.received_check_id,
            "collection_bank_account_id": collection_bank_account_id,
            "sent_date": sent_date,
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