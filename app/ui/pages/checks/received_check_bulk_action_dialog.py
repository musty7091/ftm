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


ACTION_SEND_TO_BANK = "SEND_TO_BANK"
ACTION_COLLECT = "COLLECT"
ACTION_ENDORSE = "ENDORSE"


ACTION_TITLES = {
    ACTION_SEND_TO_BANK: "Toplu Bankaya Tahsile Ver",
    ACTION_COLLECT: "Toplu Tahsil Et",
    ACTION_ENDORSE: "Toplu Ciro Et",
}


ACTION_BUTTON_TEXTS = {
    ACTION_SEND_TO_BANK: "Toplu Bankaya Ver",
    ACTION_COLLECT: "Toplu Tahsil Et",
    ACTION_ENDORSE: "Toplu Ciro Et",
}


ACTION_SUBTITLES = {
    ACTION_SEND_TO_BANK: (
        "Seçili PORTFOLIO durumundaki alınan çekleri aynı banka hesabına tahsile gönderir. "
        "Bu işlem henüz banka para girişi oluşturmaz; çekleri tahsil sürecine taşır."
    ),
    ACTION_COLLECT: (
        "Seçili tahsil edilebilir alınan çekleri tek işlem tarihiyle tahsil eder. "
        "Banka hesabı seçilirse tüm çekler bu hesaba tahsil edilir; seçilmezse çeklerin mevcut tahsil hesabı kullanılır."
    ),
    ACTION_ENDORSE: (
        "Seçili PORTFOLIO durumundaki alınan çekleri aynı kişi / kurum lehine ciro eder. "
        "Bu işlem banka hareketi oluşturmaz; çekleri portföyden çıkarır."
    ),
}


SEND_TO_BANK_ALLOWED_STATUSES = {
    ReceivedCheckStatus.PORTFOLIO.value,
}

COLLECT_ALLOWED_STATUSES = {
    ReceivedCheckStatus.PORTFOLIO.value,
    ReceivedCheckStatus.GIVEN_TO_BANK.value,
    ReceivedCheckStatus.IN_COLLECTION.value,
}

ENDORSE_ALLOWED_STATUSES = {
    ReceivedCheckStatus.PORTFOLIO.value,
}


@dataclass(frozen=True)
class BulkReceivedCheckOption:
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
    description: str | None


@dataclass(frozen=True)
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


def _normalize_action_type(action_type: str) -> str:
    normalized_action_type = str(action_type or "").strip().upper()

    if normalized_action_type not in {
        ACTION_SEND_TO_BANK,
        ACTION_COLLECT,
        ACTION_ENDORSE,
    }:
        raise ValueError(f"Geçersiz toplu alınan çek işlem türü: {action_type}")

    return normalized_action_type


def _normalize_received_check_ids(received_check_ids: list[int]) -> list[int]:
    normalized_ids: list[int] = []
    seen_ids: set[int] = set()

    for raw_id in received_check_ids:
        try:
            received_check_id = int(raw_id)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Geçersiz alınan çek ID değeri: {raw_id}") from exc

        if received_check_id <= 0:
            raise ValueError(f"Geçersiz alınan çek ID değeri: {received_check_id}")

        if received_check_id not in seen_ids:
            normalized_ids.append(received_check_id)
            seen_ids.add(received_check_id)

    if not normalized_ids:
        raise ValueError("Toplu işlem için en az bir alınan çek seçilmelidir.")

    return normalized_ids


class ReceivedCheckBulkActionDialog(QDialog):
    def __init__(
        self,
        *,
        parent: QWidget | None,
        action_type: str,
        received_check_ids: list[int],
    ) -> None:
        super().__init__(parent)

        self.action_type = _normalize_action_type(action_type)
        self.received_check_ids = _normalize_received_check_ids(received_check_ids)

        self.selected_checks = self._load_selected_checks(self.received_check_ids)
        self.collection_bank_accounts = self._load_collection_bank_accounts()
        self.collection_bank_account_lookup = {
            collection_bank_account.bank_account_id: collection_bank_account
            for collection_bank_account in self.collection_bank_accounts
        }

        self.payload: dict[str, Any] | None = None

        title_text = ACTION_TITLES[self.action_type]

        self.setWindowTitle(title_text)
        self.resize(1120, 760)
        self.setMinimumSize(940, 660)
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

        title = QLabel(title_text)
        title.setObjectName("SectionTitle")

        subtitle = QLabel(ACTION_SUBTITLES[self.action_type])
        subtitle.setObjectName("MutedText")
        subtitle.setWordWrap(True)

        self.summary_label = QLabel("")
        self.summary_label.setObjectName("MutedText")
        self.summary_label.setWordWrap(True)
        self.summary_label.setStyleSheet(
            """
            QLabel {
                background-color: #13243a;
                color: #bfdbfe;
                border: 1px solid #2563eb;
                border-radius: 10px;
                padding: 8px 10px;
                font-weight: 700;
            }
            """
        )

        self.checks_table = QTableWidget()
        self.checks_table.setColumnCount(9)
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
                "Tahsil Hesabı",
            ]
        )
        self.checks_table.verticalHeader().setVisible(False)
        self.checks_table.setAlternatingRowColors(False)
        self.checks_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.checks_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.checks_table.setMinimumHeight(280)
        self.checks_table.setWordWrap(False)
        self.checks_table.setTextElideMode(Qt.ElideRight)
        self.checks_table.verticalHeader().setDefaultSectionSize(34)
        self.checks_table.verticalHeader().setMinimumSectionSize(30)

        checks_header = self.checks_table.horizontalHeader()
        checks_header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        checks_header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        checks_header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        checks_header.setSectionResizeMode(3, QHeaderView.Stretch)
        checks_header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        checks_header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        checks_header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        checks_header.setSectionResizeMode(7, QHeaderView.ResizeToContents)
        checks_header.setSectionResizeMode(8, QHeaderView.ResizeToContents)

        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        form_layout.setFormAlignment(Qt.AlignTop)
        form_layout.setHorizontalSpacing(18)
        form_layout.setVerticalSpacing(14)

        self.action_date_edit = QDateEdit()
        self.action_date_edit.setMinimumHeight(38)
        self.action_date_edit.setCalendarPopup(True)
        self.action_date_edit.setDisplayFormat("dd.MM.yyyy")
        self.action_date_edit.setDate(QDate.currentDate())

        action_date_label = "İşlem tarihi"
        if self.action_type == ACTION_SEND_TO_BANK:
            action_date_label = "Bankaya veriliş tarihi"
        elif self.action_type == ACTION_COLLECT:
            action_date_label = "Tahsil tarihi"
        elif self.action_type == ACTION_ENDORSE:
            action_date_label = "Ciro tarihi"

        form_layout.addRow(action_date_label, self.action_date_edit)

        self.collection_account_combo = QComboBox()
        self.collection_account_combo.setMinimumHeight(38)
        self.collection_account_combo.currentIndexChanged.connect(self._update_collection_account_info)

        self.collection_account_info_label = QLabel("")
        self.collection_account_info_label.setObjectName("MutedText")
        self.collection_account_info_label.setWordWrap(True)

        if self.action_type in {ACTION_SEND_TO_BANK, ACTION_COLLECT}:
            collection_account_label = "Tahsil hesabı"
            if self.action_type == ACTION_COLLECT:
                collection_account_label = "Tahsil hesabı"

            form_layout.addRow(collection_account_label, self.collection_account_combo)
            form_layout.addRow("", self.collection_account_info_label)

        self.counterparty_input = QLineEdit()
        self.counterparty_input.setMinimumHeight(42)
        self.counterparty_input.setPlaceholderText("Çeklerin verildiği kişi / kurum / işletme")

        self.purpose_input = QLineEdit()
        self.purpose_input.setMinimumHeight(42)
        self.purpose_input.setPlaceholderText("Örn: Ürün alımı, ödeme, devir, mutabakat")

        if self.action_type == ACTION_ENDORSE:
            form_layout.addRow("Kime verildi", self.counterparty_input)
            form_layout.addRow("Kullanım amacı", self.purpose_input)

        self.reference_no_input = QLineEdit()
        self.reference_no_input.setMinimumHeight(38)
        self.reference_no_input.setPlaceholderText("İsteğe bağlı ortak referans no")
        form_layout.addRow("Referans no", self.reference_no_input)

        self.description_input = QTextEdit()
        self.description_input.setPlaceholderText("İsteğe bağlı ortak açıklama")
        self.description_input.setFixedHeight(92)
        form_layout.addRow("Açıklama", self.description_input)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)

        self.save_button = QPushButton(ACTION_BUTTON_TEXTS[self.action_type])
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
        main_layout.addWidget(self.summary_label)
        main_layout.addWidget(self.checks_table)
        main_layout.addSpacing(4)
        main_layout.addLayout(form_layout)
        main_layout.addSpacing(8)
        main_layout.addLayout(button_layout)

        scroll_area.setWidget(content_widget)
        outer_layout.addWidget(scroll_area)

        self._fill_table()
        self._refresh_summary()
        self._fill_collection_account_combo()
        self._update_collection_account_info()
        self._refresh_save_button_state()

    def has_selected_checks(self) -> bool:
        return bool(self.selected_checks)

    def get_missing_data_message(self) -> str:
        return "Toplu işlem için seçili alınan çek bulunamadı."

    def _load_selected_checks(self, received_check_ids: list[int]) -> list[BulkReceivedCheckOption]:
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
                .where(ReceivedCheck.id.in_(received_check_ids))
                .order_by(ReceivedCheck.due_date.asc(), ReceivedCheck.id.asc())
            )

            rows = session.execute(statement).all()
            found_ids: set[int] = set()
            results: list[BulkReceivedCheckOption] = []

            for received_check, customer, collection_bank_account, collection_bank in rows:
                found_ids.add(received_check.id)

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
                    BulkReceivedCheckOption(
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
                        description=received_check.description,
                    )
                )

            missing_ids = [
                received_check_id
                for received_check_id in received_check_ids
                if received_check_id not in found_ids
            ]

            if missing_ids:
                raise ValueError(
                    "Bazı alınan çek kayıtları bulunamadı: "
                    + ", ".join(str(received_check_id) for received_check_id in missing_ids)
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

    def _allowed_statuses_for_action(self) -> set[str]:
        if self.action_type == ACTION_SEND_TO_BANK:
            return SEND_TO_BANK_ALLOWED_STATUSES

        if self.action_type == ACTION_COLLECT:
            return COLLECT_ALLOWED_STATUSES

        if self.action_type == ACTION_ENDORSE:
            return ENDORSE_ALLOWED_STATUSES

        return set()

    def _ineligible_checks(self) -> list[BulkReceivedCheckOption]:
        allowed_statuses = self._allowed_statuses_for_action()

        return [
            selected_check
            for selected_check in self.selected_checks
            if str(selected_check.status or "").strip().upper() not in allowed_statuses
        ]

    def _currency_codes(self) -> set[str]:
        return {
            str(selected_check.currency_code or "").strip().upper()
            for selected_check in self.selected_checks
            if str(selected_check.currency_code or "").strip()
        }

    def _has_missing_existing_collection_account(self) -> bool:
        return any(
            selected_check.collection_bank_account_id is None
            for selected_check in self.selected_checks
        )

    def _totals_by_currency(self) -> dict[str, Decimal]:
        totals: dict[str, Decimal] = {}

        for selected_check in self.selected_checks:
            currency_code = str(selected_check.currency_code or "").strip().upper()
            totals[currency_code] = totals.get(currency_code, Decimal("0.00")) + selected_check.amount

        return totals

    def _totals_text(self) -> str:
        totals = self._totals_by_currency()

        if not totals:
            return "Toplam yok"

        return " | ".join(
            f"{currency_code}: {_format_currency_amount(amount, currency_code)}"
            for currency_code, amount in sorted(totals.items())
        )

    def _fill_table(self) -> None:
        self.checks_table.setRowCount(len(self.selected_checks))

        for row_index, selected_check in enumerate(self.selected_checks):
            collection_account_text = "-"

            if selected_check.collection_bank_name and selected_check.collection_bank_account_name:
                collection_account_text = (
                    f"{selected_check.collection_bank_name} / "
                    f"{selected_check.collection_bank_account_name}"
                )

            values = [
                str(selected_check.received_check_id),
                selected_check.customer_name,
                selected_check.check_number,
                selected_check.drawer_bank_name,
                selected_check.received_date.strftime("%d.%m.%Y"),
                selected_check.due_date.strftime("%d.%m.%Y"),
                _format_currency_amount(selected_check.amount, selected_check.currency_code),
                _received_status_text(selected_check.status),
                collection_account_text,
            ]

            is_ineligible = selected_check in self._ineligible_checks()

            for column_index, value in enumerate(values):
                item = QTableWidgetItem(value)

                if is_ineligible:
                    item.setForeground(QColor("#fbbf24"))
                elif str(selected_check.status or "").strip().upper() == "PORTFOLIO":
                    item.setForeground(QColor("#e5e7eb"))
                elif str(selected_check.status or "").strip().upper() == "GIVEN_TO_BANK":
                    item.setForeground(QColor("#38bdf8"))
                elif str(selected_check.status or "").strip().upper() == "IN_COLLECTION":
                    item.setForeground(QColor("#bfdbfe"))
                else:
                    item.setForeground(QColor("#e5e7eb"))

                if column_index == 6:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                else:
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)

                if column_index == 0:
                    item.setData(Qt.UserRole, selected_check.received_check_id)

                tooltip_lines = [
                    f"ID: {selected_check.received_check_id}",
                    f"Müşteri: {selected_check.customer_name}",
                    f"Çek No: {selected_check.check_number}",
                    f"Keşideci Banka: {selected_check.drawer_bank_name}",
                    f"Durum: {_received_status_text(selected_check.status)}",
                    f"Alınış: {selected_check.received_date.strftime('%d.%m.%Y')}",
                    f"Vade: {selected_check.due_date.strftime('%d.%m.%Y')}",
                    f"Tutar: {_format_currency_amount(selected_check.amount, selected_check.currency_code)}",
                    f"Tahsil Hesabı: {collection_account_text}",
                ]

                if is_ineligible:
                    tooltip_lines.append("Bu çek seçili toplu işlem için uygun durumda değil.")

                item.setToolTip("\n".join(tooltip_lines))
                self.checks_table.setItem(row_index, column_index, item)

        for row_index in range(self.checks_table.rowCount()):
            self.checks_table.setRowHeight(row_index, 34)

    def _refresh_summary(self) -> None:
        ineligible_checks = self._ineligible_checks()
        currency_codes = self._currency_codes()

        lines = [
            f"Seçili çek sayısı: {len(self.selected_checks)}",
            f"Toplam: {self._totals_text()}",
        ]

        if len(currency_codes) > 1 and self.action_type in {ACTION_SEND_TO_BANK, ACTION_COLLECT}:
            lines.append(
                "Uyarı: Banka hesabı gerektiren toplu işlemlerde tek seferde aynı para birimindeki çekler işlenmelidir."
            )

        if ineligible_checks:
            lines.append(
                f"Uyarı: {len(ineligible_checks)} çek bu işlem için uygun durumda değil. "
                "Uygun olmayan satırlar sarı renkle gösterilir."
            )

        if self.action_type == ACTION_COLLECT:
            lines.append(
                "Tahsil hesabı seçmezsen, çeklerin mevcut tahsil hesabı kullanılır. "
                "Tahsil hesabı olmayan çek varsa hesap seçimi zorunludur."
            )

        self.summary_label.setText("\n".join(lines))

    def _fill_collection_account_combo(self) -> None:
        if self.action_type not in {ACTION_SEND_TO_BANK, ACTION_COLLECT}:
            return

        self.collection_account_combo.blockSignals(True)
        self.collection_account_combo.clear()

        currency_codes = self._currency_codes()

        if len(currency_codes) != 1:
            self.collection_account_combo.addItem("Tek para birimi seçilmelidir", None)
            self.collection_account_combo.setEnabled(False)
            self.collection_account_combo.blockSignals(False)
            return

        selected_currency_code = next(iter(currency_codes))

        matching_accounts = [
            collection_bank_account
            for collection_bank_account in self.collection_bank_accounts
            if collection_bank_account.currency_code == selected_currency_code
        ]

        if self.action_type == ACTION_COLLECT:
            self.collection_account_combo.addItem(
                "Çeklerin mevcut tahsil hesabını kullan",
                None,
            )
        else:
            self.collection_account_combo.addItem("Seçilmedi", None)

        for collection_bank_account in matching_accounts:
            text = (
                f"{collection_bank_account.bank_name} / "
                f"{collection_bank_account.account_name} / "
                f"{collection_bank_account.currency_code}"
            )
            self.collection_account_combo.addItem(text, collection_bank_account.bank_account_id)

        self.collection_account_combo.setEnabled(True)
        self.collection_account_combo.blockSignals(False)

    def _selected_collection_account_id(self) -> int | None:
        if self.action_type not in {ACTION_SEND_TO_BANK, ACTION_COLLECT}:
            return None

        current_data = self.collection_account_combo.currentData()

        if current_data in {None, ""}:
            return None

        try:
            return int(current_data)
        except (TypeError, ValueError):
            return None

    def _update_collection_account_info(self) -> None:
        if self.action_type not in {ACTION_SEND_TO_BANK, ACTION_COLLECT}:
            return

        currency_codes = self._currency_codes()

        if len(currency_codes) != 1:
            self.collection_account_info_label.setText(
                "Seçili çeklerde birden fazla para birimi var. "
                "Bu toplu işlem için çekleri para birimine göre ayrı ayrı seçmelisin."
            )
            return

        selected_currency_code = next(iter(currency_codes))
        selected_collection_account_id = self._selected_collection_account_id()

        if selected_collection_account_id is None:
            if self.action_type == ACTION_COLLECT:
                self.collection_account_info_label.setText(
                    "Tahsil hesabı seçilmedi. Çeklerin mevcut tahsil hesabı kullanılacak. "
                    "Mevcut tahsil hesabı olmayan çek varsa işlem onaylanmaz."
                )
            else:
                self.collection_account_info_label.setText(
                    f"Seçili çekler {selected_currency_code} para birimindedir. "
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

    def _refresh_save_button_state(self) -> None:
        self.save_button.setEnabled(bool(self.selected_checks))

    def _validate_payload(self) -> None:
        if not self.selected_checks:
            raise ValueError("Toplu işlem için en az bir alınan çek seçilmelidir.")

        ineligible_checks = self._ineligible_checks()

        if ineligible_checks:
            raise ValueError(
                "Seçili çeklerden bazıları bu işlem için uygun durumda değil:\n"
                + "\n".join(
                    f"- Çek ID {selected_check.received_check_id}: {_received_status_text(selected_check.status)}"
                    for selected_check in ineligible_checks[:20]
                )
            )

        currency_codes = self._currency_codes()

        if self.action_type in {ACTION_SEND_TO_BANK, ACTION_COLLECT} and len(currency_codes) != 1:
            raise ValueError(
                "Bu toplu işlem için seçili çekler tek para biriminde olmalıdır. "
                "Lütfen TRY / USD / EUR / GBP çekleri ayrı ayrı işleyin."
            )

        if self.action_type == ACTION_SEND_TO_BANK and self._selected_collection_account_id() is None:
            raise ValueError("Bankaya tahsile verme işlemi için tahsil hesabı seçilmelidir.")

        if self.action_type == ACTION_COLLECT:
            if self._selected_collection_account_id() is None and self._has_missing_existing_collection_account():
                raise ValueError(
                    "Seçili çeklerden bazılarında mevcut tahsil hesabı yok. "
                    "Toplu tahsil için tahsil hesabı seçmelisin."
                )

        if self.action_type == ACTION_ENDORSE:
            counterparty_text = self.counterparty_input.text().strip()
            purpose_text = self.purpose_input.text().strip()

            if not counterparty_text:
                raise ValueError("Kime verildi bilgisi boş olamaz.")

            if not purpose_text:
                raise ValueError("Kullanım amacı boş olamaz.")

    def _build_payload(self) -> dict[str, Any]:
        self._validate_payload()

        payload: dict[str, Any] = {
            "action_type": self.action_type,
            "received_check_ids": [
                selected_check.received_check_id
                for selected_check in self.selected_checks
            ],
            "action_date": _qdate_to_date(self.action_date_edit.date()),
            "reference_no": self.reference_no_input.text().strip() or None,
            "description": self.description_input.toPlainText().strip() or None,
        }

        if self.action_type in {ACTION_SEND_TO_BANK, ACTION_COLLECT}:
            payload["collection_bank_account_id"] = self._selected_collection_account_id()

        if self.action_type == ACTION_ENDORSE:
            payload["counterparty_text"] = self.counterparty_input.text().strip()
            payload["purpose_text"] = self.purpose_input.text().strip()

        return payload

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
