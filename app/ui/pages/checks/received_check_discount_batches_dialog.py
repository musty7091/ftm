from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy import select

from app.db.session import session_scope
from app.models.bank import Bank, BankAccount
from app.models.business_partner import BusinessPartner
from app.models.check import (
    ReceivedCheck,
    ReceivedCheckDiscountBatch,
    ReceivedCheckDiscountBatchItem,
)
from app.models.user import User
from app.ui.pages.banks.bank_dialog_styles import BANK_DIALOG_STYLES
from app.ui.pages.checks.checks_data import format_currency_amount, received_status_text


@dataclass(frozen=True)
class DiscountBatchSummaryRow:
    batch_id: int
    bank_account_text: str
    bank_transaction_id: int | None
    discount_date: date
    annual_interest_rate: Decimal
    day_basis: int
    commission_rate: Decimal
    total_gross_amount: Decimal
    total_interest_expense_amount: Decimal
    total_commission_amount: Decimal
    total_discount_expense_amount: Decimal
    net_bank_amount: Decimal
    currency_code: str
    reference_no: str | None
    description: str | None
    created_by_text: str | None
    created_at: datetime | None


@dataclass(frozen=True)
class DiscountBatchItemRow:
    item_id: int
    batch_id: int
    received_check_id: int
    customer_name: str
    drawer_bank_name: str
    check_number: str
    due_date: date
    gross_amount: Decimal
    days_to_due: int
    annual_interest_rate: Decimal
    day_basis: int
    interest_expense_amount: Decimal
    commission_rate: Decimal
    commission_amount: Decimal
    total_expense_amount: Decimal
    net_amount: Decimal
    currency_code: str
    check_status: str


def _format_date(value: date | None) -> str:
    if value is None:
        return "-"

    return value.strftime("%d.%m.%Y")


def _format_datetime(value: datetime | None) -> str:
    if value is None:
        return "-"

    return value.strftime("%d.%m.%Y %H:%M")


def _format_optional_text(value: str | None) -> str:
    cleaned_value = str(value or "").strip()

    if not cleaned_value:
        return "-"

    return cleaned_value


def _enum_value(value: Any) -> str:
    if value is None:
        return ""

    if hasattr(value, "value"):
        return str(value.value)

    return str(value).strip().upper()


def _format_decimal_tr(value: Decimal, decimal_count: int = 2) -> str:
    formatted = f"{value:,.{decimal_count}f}"
    formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")

    return formatted


def _format_rate(value: Decimal | None) -> str:
    if value is None:
        return "-"

    formatted = _format_decimal_tr(Decimal(str(value)), 4)
    formatted = formatted.rstrip("0").rstrip(",")

    return f"%{formatted}"


def _format_days(value: Decimal | None) -> str:
    if value is None:
        return "-"

    formatted = _format_decimal_tr(Decimal(str(value)), 2)

    return f"{formatted} gün"


def _user_display_text(user: User | None) -> str | None:
    if user is None:
        return None

    full_name = str(getattr(user, "full_name", "") or "").strip()
    username = str(getattr(user, "username", "") or "").strip()

    if full_name and username:
        return f"{full_name} ({username})"

    if full_name:
        return full_name

    if username:
        return username

    return f"Kullanıcı ID: {user.id}"


def _calculate_weighted_average_days(items: list[DiscountBatchItemRow]) -> Decimal | None:
    if not items:
        return None

    total_gross_amount = Decimal("0.00")
    weighted_total = Decimal("0.000000")

    for item in items:
        total_gross_amount += Decimal(str(item.gross_amount))
        weighted_total += Decimal(str(item.gross_amount)) * Decimal(str(item.days_to_due))

    if total_gross_amount <= Decimal("0.00"):
        return None

    return (weighted_total / total_gross_amount).quantize(Decimal("0.000001"))


class ReceivedCheckDiscountBatchesDialog(QDialog):
    def __init__(self, *, parent: QWidget | None) -> None:
        super().__init__(parent)

        self.batch_rows = self._load_batch_rows()
        self.batch_lookup = {
            batch.batch_id: batch
            for batch in self.batch_rows
        }

        self.setWindowTitle("İskonto Paketleri / Kırdırılan Çekler")
        self.resize(1320, 820)
        self.setMinimumSize(1080, 690)
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

            QFrame#SummaryCard {
                background-color: #111827;
                border: 1px solid #1e293b;
                border-radius: 14px;
            }

            QFrame#SummaryCardStrong {
                background-color: rgba(6, 78, 59, 0.28);
                border: 1px solid #10b981;
                border-radius: 14px;
            }

            QLabel#SummaryTitle {
                color: #93c5fd;
                font-size: 11px;
                font-weight: 800;
            }

            QLabel#SummaryValue {
                color: #ffffff;
                font-size: 17px;
                font-weight: 900;
            }

            QLabel#SummaryHint {
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

        title = QLabel("İskonto Paketleri / Kırdırılan Çekler")
        title.setObjectName("SectionTitle")

        subtitle = QLabel(
            "Bankaya iskonto/kırdırma amacıyla verilen çek paketlerini ve paket içindeki her çekin "
            "faiz, komisyon, toplam kesinti ve net banka giriş detayını bu ekranda görebilirsin."
        )
        subtitle.setObjectName("MutedText")
        subtitle.setWordWrap(True)

        self.search_input = QLineEdit()
        self.search_input.setMinimumHeight(38)
        self.search_input.setPlaceholderText("Paket ID / banka / referans / açıklama ara")
        self.search_input.textChanged.connect(self._apply_filter)

        self.results_info_label = QLabel("")
        self.results_info_label.setObjectName("MutedText")
        self.results_info_label.setWordWrap(True)

        self.batch_table = QTableWidget()
        self.batch_table.setColumnCount(11)
        self.batch_table.setHorizontalHeaderLabels(
            [
                "Paket ID",
                "Tarih",
                "Banka / Hesap",
                "Brüt",
                "Faiz",
                "Komisyon",
                "Kesinti",
                "Net Banka",
                "Faiz %",
                "Komisyon %",
                "Referans",
            ]
        )
        self.batch_table.verticalHeader().setVisible(False)
        self.batch_table.setAlternatingRowColors(False)
        self.batch_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.batch_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.batch_table.setWordWrap(False)
        self.batch_table.setTextElideMode(Qt.ElideRight)
        self.batch_table.verticalHeader().setDefaultSectionSize(34)
        self.batch_table.verticalHeader().setMinimumSectionSize(30)
        self.batch_table.setMinimumHeight(230)
        self.batch_table.itemSelectionChanged.connect(self._selected_batch_changed)

        batch_header = self.batch_table.horizontalHeader()
        batch_header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        batch_header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        batch_header.setSectionResizeMode(2, QHeaderView.Stretch)
        batch_header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        batch_header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        batch_header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        batch_header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        batch_header.setSectionResizeMode(7, QHeaderView.ResizeToContents)
        batch_header.setSectionResizeMode(8, QHeaderView.ResizeToContents)
        batch_header.setSectionResizeMode(9, QHeaderView.ResizeToContents)
        batch_header.setSectionResizeMode(10, QHeaderView.ResizeToContents)

        summary_layout = self._build_summary_layout()

        self.item_info_label = QLabel("")
        self.item_info_label.setObjectName("MutedText")
        self.item_info_label.setWordWrap(True)

        self.item_table = QTableWidget()
        self.item_table.setColumnCount(14)
        self.item_table.setHorizontalHeaderLabels(
            [
                "Satır ID",
                "Çek ID",
                "Müşteri",
                "Çek No",
                "Keşideci Banka",
                "Vade",
                "Gün",
                "Brüt",
                "Faiz %",
                "Faiz",
                "Komisyon %",
                "Komisyon",
                "Net",
                "Durum",
            ]
        )
        self.item_table.verticalHeader().setVisible(False)
        self.item_table.setAlternatingRowColors(False)
        self.item_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.item_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.item_table.setWordWrap(False)
        self.item_table.setTextElideMode(Qt.ElideRight)
        self.item_table.verticalHeader().setDefaultSectionSize(34)
        self.item_table.verticalHeader().setMinimumSectionSize(30)
        self.item_table.setMinimumHeight(310)

        item_header = self.item_table.horizontalHeader()
        item_header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        item_header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        item_header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        item_header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        item_header.setSectionResizeMode(4, QHeaderView.Stretch)
        item_header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        item_header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        item_header.setSectionResizeMode(7, QHeaderView.ResizeToContents)
        item_header.setSectionResizeMode(8, QHeaderView.ResizeToContents)
        item_header.setSectionResizeMode(9, QHeaderView.ResizeToContents)
        item_header.setSectionResizeMode(10, QHeaderView.ResizeToContents)
        item_header.setSectionResizeMode(11, QHeaderView.ResizeToContents)
        item_header.setSectionResizeMode(12, QHeaderView.ResizeToContents)
        item_header.setSectionResizeMode(13, QHeaderView.ResizeToContents)

        button_layout = QHBoxLayout()
        button_layout.addStretch(1)

        close_button = QPushButton("Kapat")
        close_button.setMinimumHeight(40)
        close_button.clicked.connect(self.accept)

        button_layout.addWidget(close_button)

        main_layout.addWidget(title)
        main_layout.addWidget(subtitle)
        main_layout.addWidget(self.search_input)
        main_layout.addWidget(self.results_info_label)
        main_layout.addWidget(self.batch_table)
        main_layout.addLayout(summary_layout)
        main_layout.addWidget(self.item_info_label)
        main_layout.addWidget(self.item_table, 1)
        main_layout.addLayout(button_layout)

        scroll_area.setWidget(content_widget)
        outer_layout.addWidget(scroll_area)

        self._apply_filter()

    def _build_summary_layout(self) -> QGridLayout:
        summary_layout = QGridLayout()
        summary_layout.setSpacing(10)
        summary_layout.setColumnStretch(0, 1)
        summary_layout.setColumnStretch(1, 1)
        summary_layout.setColumnStretch(2, 1)
        summary_layout.setColumnStretch(3, 1)
        summary_layout.setColumnStretch(4, 1)
        summary_layout.setColumnStretch(5, 1)

        self.summary_check_count_card = self._build_summary_card("ÇEK SAYISI", "-", "", False)
        self.summary_gross_card = self._build_summary_card("BRÜT TOPLAM", "-", "", False)
        self.summary_average_days_card = self._build_summary_card("ORT. VADE", "-", "", False)
        self.summary_interest_card = self._build_summary_card("FAİZ", "-", "", False)
        self.summary_commission_card = self._build_summary_card("KOMİSYON", "-", "", False)
        self.summary_net_card = self._build_summary_card("NET BANKA", "-", "", True)

        summary_layout.addWidget(self.summary_check_count_card, 0, 0)
        summary_layout.addWidget(self.summary_gross_card, 0, 1)
        summary_layout.addWidget(self.summary_average_days_card, 0, 2)
        summary_layout.addWidget(self.summary_interest_card, 0, 3)
        summary_layout.addWidget(self.summary_commission_card, 0, 4)
        summary_layout.addWidget(self.summary_net_card, 0, 5)

        return summary_layout

    def _build_summary_card(
        self,
        title_text: str,
        value_text: str,
        hint_text: str,
        strong: bool,
    ) -> QFrame:
        card = QFrame()
        card.setObjectName("SummaryCardStrong" if strong else "SummaryCard")
        card.setMinimumHeight(92)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        title = QLabel(title_text)
        title.setObjectName("SummaryTitle")

        value = QLabel(value_text)
        value.setObjectName("SummaryValue")
        value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        hint = QLabel(hint_text)
        hint.setObjectName("SummaryHint")
        hint.setWordWrap(True)

        layout.addWidget(title)
        layout.addStretch(1)
        layout.addWidget(value)
        layout.addWidget(hint)

        card.value_label = value
        card.hint_label = hint

        return card

    def _load_batch_rows(self) -> list[DiscountBatchSummaryRow]:
        with session_scope() as session:
            statement = (
                select(
                    ReceivedCheckDiscountBatch,
                    BankAccount,
                    Bank,
                    User,
                )
                .join(BankAccount, ReceivedCheckDiscountBatch.bank_account_id == BankAccount.id)
                .join(Bank, BankAccount.bank_id == Bank.id)
                .outerjoin(User, ReceivedCheckDiscountBatch.created_by_user_id == User.id)
                .order_by(
                    ReceivedCheckDiscountBatch.discount_date.desc(),
                    ReceivedCheckDiscountBatch.id.desc(),
                )
            )

            rows = session.execute(statement).all()

            result: list[DiscountBatchSummaryRow] = []

            for batch, bank_account, bank, created_by_user in rows:
                currency_code = _enum_value(batch.currency_code)

                result.append(
                    DiscountBatchSummaryRow(
                        batch_id=batch.id,
                        bank_account_text=f"{bank.name} / {bank_account.account_name}",
                        bank_transaction_id=batch.bank_transaction_id,
                        discount_date=batch.discount_date,
                        annual_interest_rate=Decimal(str(batch.annual_interest_rate)),
                        day_basis=int(batch.day_basis),
                        commission_rate=Decimal(str(batch.commission_rate)),
                        total_gross_amount=Decimal(str(batch.total_gross_amount)),
                        total_interest_expense_amount=Decimal(str(batch.total_interest_expense_amount)),
                        total_commission_amount=Decimal(str(batch.total_commission_amount)),
                        total_discount_expense_amount=Decimal(str(batch.total_discount_expense_amount)),
                        net_bank_amount=Decimal(str(batch.net_bank_amount)),
                        currency_code=currency_code,
                        reference_no=batch.reference_no,
                        description=batch.description,
                        created_by_text=_user_display_text(created_by_user),
                        created_at=batch.created_at,
                    )
                )

            return result

    def _load_item_rows(self, batch_id: int) -> list[DiscountBatchItemRow]:
        with session_scope() as session:
            statement = (
                select(
                    ReceivedCheckDiscountBatchItem,
                    ReceivedCheck,
                    BusinessPartner,
                )
                .join(ReceivedCheck, ReceivedCheckDiscountBatchItem.received_check_id == ReceivedCheck.id)
                .join(BusinessPartner, ReceivedCheck.customer_id == BusinessPartner.id)
                .where(ReceivedCheckDiscountBatchItem.batch_id == batch_id)
                .order_by(
                    ReceivedCheckDiscountBatchItem.due_date.asc(),
                    ReceivedCheckDiscountBatchItem.id.asc(),
                )
            )

            rows = session.execute(statement).all()

            result: list[DiscountBatchItemRow] = []

            for item, received_check, customer in rows:
                result.append(
                    DiscountBatchItemRow(
                        item_id=item.id,
                        batch_id=item.batch_id,
                        received_check_id=item.received_check_id,
                        customer_name=customer.name,
                        drawer_bank_name=received_check.drawer_bank_name,
                        check_number=received_check.check_number,
                        due_date=item.due_date,
                        gross_amount=Decimal(str(item.gross_amount)),
                        days_to_due=int(item.days_to_due),
                        annual_interest_rate=Decimal(str(item.annual_interest_rate)),
                        day_basis=int(item.day_basis),
                        interest_expense_amount=Decimal(str(item.interest_expense_amount)),
                        commission_rate=Decimal(str(item.commission_rate)),
                        commission_amount=Decimal(str(item.commission_amount)),
                        total_expense_amount=Decimal(str(item.total_expense_amount)),
                        net_amount=Decimal(str(item.net_amount)),
                        currency_code=_enum_value(item.currency_code),
                        check_status=_enum_value(received_check.status),
                    )
                )

            return result

    def _apply_filter(self) -> None:
        search_text = self.search_input.text().strip().lower()

        if not search_text:
            filtered_rows = self.batch_rows
        else:
            filtered_rows = [
                row
                for row in self.batch_rows
                if search_text in self._batch_search_text(row)
            ]

        self._fill_batch_table(filtered_rows)
        self._update_results_info(filtered_rows)

        if self.batch_table.rowCount() > 0:
            self.batch_table.setCurrentCell(0, 0)
            self.batch_table.selectRow(0)
            self._selected_batch_changed()
        else:
            self._fill_item_table([])
            self._clear_summary()

    def _batch_search_text(self, row: DiscountBatchSummaryRow) -> str:
        return " | ".join(
            [
                str(row.batch_id),
                row.bank_account_text,
                str(row.bank_transaction_id or ""),
                _format_date(row.discount_date),
                _format_rate(row.annual_interest_rate),
                _format_rate(row.commission_rate),
                format_currency_amount(row.total_gross_amount, row.currency_code),
                format_currency_amount(row.net_bank_amount, row.currency_code),
                row.reference_no or "",
                row.description or "",
                row.created_by_text or "",
            ]
        ).lower()

    def _fill_batch_table(self, rows: list[DiscountBatchSummaryRow]) -> None:
        self.batch_table.setRowCount(len(rows))

        for row_index, row in enumerate(rows):
            values = [
                str(row.batch_id),
                _format_date(row.discount_date),
                row.bank_account_text,
                format_currency_amount(row.total_gross_amount, row.currency_code),
                format_currency_amount(row.total_interest_expense_amount, row.currency_code),
                format_currency_amount(row.total_commission_amount, row.currency_code),
                format_currency_amount(row.total_discount_expense_amount, row.currency_code),
                format_currency_amount(row.net_bank_amount, row.currency_code),
                _format_rate(row.annual_interest_rate),
                _format_rate(row.commission_rate),
                row.reference_no or "-",
            ]

            tooltip_lines = [
                f"Paket ID: {row.batch_id}",
                f"Banka / Hesap: {row.bank_account_text}",
                f"Banka Hareket ID: {row.bank_transaction_id or '-'}",
                f"İskonto Tarihi: {_format_date(row.discount_date)}",
                f"Yıllık Faiz: {_format_rate(row.annual_interest_rate)}",
                f"Gün Bazı: {row.day_basis}",
                f"Komisyon: {_format_rate(row.commission_rate)}",
                f"Brüt Toplam: {format_currency_amount(row.total_gross_amount, row.currency_code)}",
                f"Toplam Faiz: {format_currency_amount(row.total_interest_expense_amount, row.currency_code)}",
                f"Toplam Komisyon: {format_currency_amount(row.total_commission_amount, row.currency_code)}",
                f"Toplam Kesinti: {format_currency_amount(row.total_discount_expense_amount, row.currency_code)}",
                f"Net Banka: {format_currency_amount(row.net_bank_amount, row.currency_code)}",
                f"Referans: {_format_optional_text(row.reference_no)}",
                f"Açıklama: {_format_optional_text(row.description)}",
                f"Oluşturan: {_format_optional_text(row.created_by_text)}",
                f"Oluşturma: {_format_datetime(row.created_at)}",
            ]

            for column_index, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.UserRole, row.batch_id)
                item.setToolTip("\n".join(tooltip_lines))

                if column_index in {3, 4, 5, 6, 7, 8, 9}:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                else:
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)

                if column_index == 7:
                    item.setForeground(QColor("#34d399"))
                else:
                    item.setForeground(QColor("#e5e7eb"))

                self.batch_table.setItem(row_index, column_index, item)

        self.batch_table.resizeRowsToContents()

    def _update_results_info(self, rows: list[DiscountBatchSummaryRow]) -> None:
        total_count = len(self.batch_rows)
        filtered_count = len(rows)

        if total_count == 0:
            self.results_info_label.setText("Henüz oluşturulmuş iskonto paketi bulunamadı.")
            return

        if filtered_count == 0:
            self.results_info_label.setText("Arama kriterine uygun iskonto paketi bulunamadı.")
            return

        self.results_info_label.setText(
            f"Toplam {total_count} iskonto paketi içinden {filtered_count} kayıt listeleniyor."
        )

    def _selected_batch_id(self) -> int | None:
        current_row = self.batch_table.currentRow()

        if current_row < 0:
            return None

        id_item = self.batch_table.item(current_row, 0)

        if id_item is None:
            return None

        batch_id = id_item.data(Qt.UserRole)

        if batch_id in {None, ""}:
            batch_id = id_item.text()

        try:
            return int(batch_id)
        except (TypeError, ValueError):
            return None

    def _selected_batch_changed(self) -> None:
        batch_id = self._selected_batch_id()

        if batch_id is None:
            self._fill_item_table([])
            self._clear_summary()
            return

        batch = self.batch_lookup.get(batch_id)

        if batch is None:
            self._fill_item_table([])
            self._clear_summary()
            return

        items = self._load_item_rows(batch_id)

        self._update_summary(batch, items)
        self._fill_item_table(items)

    def _update_summary(
        self,
        batch: DiscountBatchSummaryRow,
        items: list[DiscountBatchItemRow],
    ) -> None:
        weighted_average_days = _calculate_weighted_average_days(items)

        self.summary_check_count_card.value_label.setText(str(len(items)))
        self.summary_check_count_card.hint_label.setText(f"Paket ID: {batch.batch_id}")

        self.summary_gross_card.value_label.setText(
            format_currency_amount(batch.total_gross_amount, batch.currency_code)
        )
        self.summary_gross_card.hint_label.setText("Brüt çek toplamı")

        self.summary_average_days_card.value_label.setText(_format_days(weighted_average_days))
        self.summary_average_days_card.hint_label.setText(f"Gün bazı: {batch.day_basis}")

        self.summary_interest_card.value_label.setText(
            format_currency_amount(batch.total_interest_expense_amount, batch.currency_code)
        )
        self.summary_interest_card.hint_label.setText(f"Yıllık faiz: {_format_rate(batch.annual_interest_rate)}")

        self.summary_commission_card.value_label.setText(
            format_currency_amount(batch.total_commission_amount, batch.currency_code)
        )
        self.summary_commission_card.hint_label.setText(f"Komisyon: {_format_rate(batch.commission_rate)}")

        self.summary_net_card.value_label.setText(
            format_currency_amount(batch.net_bank_amount, batch.currency_code)
        )
        self.summary_net_card.hint_label.setText(f"Banka hareket ID: {batch.bank_transaction_id or '-'}")

        self.item_info_label.setText(
            f"Seçili paket: {batch.batch_id} | "
            f"İskonto tarihi: {_format_date(batch.discount_date)} | "
            f"Banka/Hesap: {batch.bank_account_text} | "
            f"Referans: {_format_optional_text(batch.reference_no)}"
        )

    def _clear_summary(self) -> None:
        for card in [
            self.summary_check_count_card,
            self.summary_gross_card,
            self.summary_average_days_card,
            self.summary_interest_card,
            self.summary_commission_card,
            self.summary_net_card,
        ]:
            card.value_label.setText("-")
            card.hint_label.setText("")

        self.item_info_label.setText("")

    def _fill_item_table(self, rows: list[DiscountBatchItemRow]) -> None:
        self.item_table.setRowCount(len(rows))

        for row_index, row in enumerate(rows):
            values = [
                str(row.item_id),
                str(row.received_check_id),
                row.customer_name,
                row.check_number,
                row.drawer_bank_name,
                _format_date(row.due_date),
                str(row.days_to_due),
                format_currency_amount(row.gross_amount, row.currency_code),
                _format_rate(row.annual_interest_rate),
                format_currency_amount(row.interest_expense_amount, row.currency_code),
                _format_rate(row.commission_rate),
                format_currency_amount(row.commission_amount, row.currency_code),
                format_currency_amount(row.net_amount, row.currency_code),
                received_status_text(row.check_status),
            ]

            tooltip_lines = [
                f"Satır ID: {row.item_id}",
                f"Paket ID: {row.batch_id}",
                f"Çek ID: {row.received_check_id}",
                f"Müşteri: {row.customer_name}",
                f"Çek No: {row.check_number}",
                f"Keşideci Banka: {row.drawer_bank_name}",
                f"Vade: {_format_date(row.due_date)}",
                f"Vadeye kalan gün: {row.days_to_due}",
                f"Brüt tutar: {format_currency_amount(row.gross_amount, row.currency_code)}",
                f"Yıllık faiz: {_format_rate(row.annual_interest_rate)}",
                f"Faiz kesintisi: {format_currency_amount(row.interest_expense_amount, row.currency_code)}",
                f"Komisyon oranı: {_format_rate(row.commission_rate)}",
                f"Komisyon: {format_currency_amount(row.commission_amount, row.currency_code)}",
                f"Toplam kesinti: {format_currency_amount(row.total_expense_amount, row.currency_code)}",
                f"Net tutar: {format_currency_amount(row.net_amount, row.currency_code)}",
                f"Çek durumu: {received_status_text(row.check_status)}",
            ]

            for column_index, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip("\n".join(tooltip_lines))

                if column_index in {6, 7, 8, 9, 10, 11, 12}:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                else:
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)

                if column_index == 12:
                    item.setForeground(QColor("#34d399"))
                elif column_index in {9, 11}:
                    item.setForeground(QColor("#fbbf24"))
                else:
                    item.setForeground(QColor("#e5e7eb"))

                self.item_table.setItem(row_index, column_index, item)

        self.item_table.resizeRowsToContents()