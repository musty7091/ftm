from dataclasses import dataclass
from datetime import date, timedelta
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
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy import select
from sqlalchemy.orm import aliased

from app.db.session import session_scope
from app.models.bank import Bank, BankAccount
from app.models.business_partner import BusinessPartner
from app.models.check import IssuedCheck, ReceivedCheck
from app.models.enums import IssuedCheckStatus, ReceivedCheckStatus
from app.ui.pages.banks.bank_dialog_styles import BANK_DIALOG_STYLES
from app.ui.pages.checks.checks_data import (
    format_currency_amount,
    issued_status_text,
    received_status_text,
)


ISSUED_OPEN_STATUS_VALUES = {
    IssuedCheckStatus.PREPARED.value,
    IssuedCheckStatus.GIVEN.value,
}

RECEIVED_OPEN_STATUS_VALUES = {
    ReceivedCheckStatus.PORTFOLIO.value,
    ReceivedCheckStatus.GIVEN_TO_BANK.value,
    ReceivedCheckStatus.IN_COLLECTION.value,
}


@dataclass(frozen=True)
class CheckReportRow:
    report_group: str
    check_type: str
    check_id: int
    partner_name: str
    bank_text: str
    check_number: str
    issue_or_received_date: date
    due_date: date
    amount: Decimal
    currency_code: str
    status: str
    reference_no: str | None


@dataclass(frozen=True)
class ChecksReportData:
    issued_open_rows: list[CheckReportRow]
    received_open_rows: list[CheckReportRow]
    received_problem_rows: list[CheckReportRow]
    received_discounted_rows: list[CheckReportRow]
    received_endorsed_rows: list[CheckReportRow]
    error_message: str | None = None


def _enum_value(value: Any) -> str:
    if value is None:
        return ""

    if hasattr(value, "value"):
        return str(value.value)

    return str(value).strip().upper()


def _format_date(value: date | None) -> str:
    if value is None:
        return "-"

    return value.strftime("%d.%m.%Y")


def _status_text(check_type: str, status: str) -> str:
    if check_type == "Yazılan":
        return issued_status_text(status)

    return received_status_text(status)


def _currency_totals_text(rows: list[CheckReportRow]) -> str:
    if not rows:
        return "Kayıt yok"

    totals: dict[str, Decimal] = {}

    for row in rows:
        currency_code = row.currency_code
        totals[currency_code] = totals.get(currency_code, Decimal("0")) + Decimal(str(row.amount))

    parts = [
        format_currency_amount(total_amount, currency_code)
        for currency_code, total_amount in sorted(totals.items())
    ]

    return " | ".join(parts)


def _bank_text(bank_name: str | None, account_name: str | None) -> str:
    cleaned_bank_name = str(bank_name or "").strip()
    cleaned_account_name = str(account_name or "").strip()

    if cleaned_bank_name and cleaned_account_name:
        return f"{cleaned_bank_name} / {cleaned_account_name}"

    if cleaned_bank_name:
        return cleaned_bank_name

    if cleaned_account_name:
        return cleaned_account_name

    return "-"


class ChecksReportDialog(QDialog):
    def __init__(self, *, parent: QWidget | None) -> None:
        super().__init__(parent)

        self.today = date.today()
        self.week_end = self.today + timedelta(days=7)
        self.report_data = self._load_report_data()

        self.setWindowTitle("Çek Rapor Özeti")
        self.resize(1240, 780)
        self.setMinimumSize(1040, 660)
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

            QFrame#ReportCard {
                background-color: #111827;
                border: 1px solid #1e293b;
                border-radius: 14px;
            }

            QFrame#ReportCardRisk {
                background-color: rgba(127, 29, 29, 0.24);
                border: 1px solid #ef4444;
                border-radius: 14px;
            }

            QFrame#ReportCardSuccess {
                background-color: rgba(6, 78, 59, 0.26);
                border: 1px solid #10b981;
                border-radius: 14px;
            }

            QLabel#ReportTitle {
                color: #93c5fd;
                font-size: 12px;
                font-weight: 800;
            }

            QLabel#ReportValue {
                color: #ffffff;
                font-size: 21px;
                font-weight: 900;
            }

            QLabel#ReportHint {
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

            QTabWidget::pane {
                border: 1px solid #1e293b;
                background-color: #0b1220;
                border-radius: 12px;
                top: -1px;
            }

            QTabBar::tab {
                background-color: #172033;
                color: #94a3b8;
                border: 1px solid #24324a;
                border-bottom: none;
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
                padding: 8px 16px;
                margin-right: 5px;
                min-width: 130px;
                font-weight: 600;
            }

            QTabBar::tab:selected {
                background-color: #2563eb;
                color: #ffffff;
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

        title = QLabel("Çek Rapor Özeti")
        title.setObjectName("SectionTitle")

        subtitle = QLabel(
            "Açık, vadesi yaklaşan, vadesi geçmiş, problemli, iskonto edilen ve ciro edilen çeklerin hızlı rapor özetidir. "
            "Bu ekran sadece görüntüleme amaçlıdır."
        )
        subtitle.setObjectName("MutedText")
        subtitle.setWordWrap(True)

        date_hint = QLabel(
            f"Rapor tarihi: {_format_date(self.today)} | 7 günlük vade aralığı: {_format_date(self.today)} - {_format_date(self.week_end)}"
        )
        date_hint.setObjectName("MutedText")
        date_hint.setWordWrap(True)

        main_layout.addWidget(title)
        main_layout.addWidget(subtitle)
        main_layout.addWidget(date_hint)

        if self.report_data.error_message:
            main_layout.addWidget(self._build_warning_card(self.report_data.error_message))
        else:
            main_layout.addLayout(self._build_summary_cards())
            main_layout.addWidget(self._build_tabs(), 1)

        close_row = QHBoxLayout()
        close_row.addStretch(1)

        close_button = QPushButton("Kapat")
        close_button.setMinimumHeight(40)
        close_button.clicked.connect(self.accept)

        close_row.addWidget(close_button)
        main_layout.addLayout(close_row)

        scroll_area.setWidget(content_widget)
        outer_layout.addWidget(scroll_area)

    def _load_report_data(self) -> ChecksReportData:
        try:
            issued_open_rows = self._load_issued_open_rows()
            received_open_rows = self._load_received_open_rows()
            received_problem_rows = self._load_received_rows_by_status(
                statuses=[ReceivedCheckStatus.BOUNCED],
                report_group="Problemli Alınan",
            )
            received_discounted_rows = self._load_received_rows_by_status(
                statuses=[ReceivedCheckStatus.DISCOUNTED],
                report_group="İskonto Edilen",
            )
            received_endorsed_rows = self._load_received_rows_by_status(
                statuses=[ReceivedCheckStatus.ENDORSED],
                report_group="Ciro Edilen",
            )

            return ChecksReportData(
                issued_open_rows=issued_open_rows,
                received_open_rows=received_open_rows,
                received_problem_rows=received_problem_rows,
                received_discounted_rows=received_discounted_rows,
                received_endorsed_rows=received_endorsed_rows,
                error_message=None,
            )

        except Exception as exc:
            return ChecksReportData(
                issued_open_rows=[],
                received_open_rows=[],
                received_problem_rows=[],
                received_discounted_rows=[],
                received_endorsed_rows=[],
                error_message=str(exc),
            )

    def _load_issued_open_rows(self) -> list[CheckReportRow]:
        with session_scope() as session:
            statement = (
                select(IssuedCheck, BusinessPartner, BankAccount, Bank)
                .join(BusinessPartner, IssuedCheck.supplier_id == BusinessPartner.id)
                .join(BankAccount, IssuedCheck.bank_account_id == BankAccount.id)
                .join(Bank, BankAccount.bank_id == Bank.id)
                .where(
                    IssuedCheck.status.in_(
                        [
                            IssuedCheckStatus.PREPARED,
                            IssuedCheckStatus.GIVEN,
                        ]
                    )
                )
                .order_by(IssuedCheck.due_date.asc(), IssuedCheck.id.asc())
            )

            rows = session.execute(statement).all()

            result: list[CheckReportRow] = []

            for issued_check, supplier, bank_account, bank in rows:
                status_value = _enum_value(issued_check.status)

                if issued_check.due_date < self.today:
                    report_group = "Vadesi Geçmiş"
                elif self.today <= issued_check.due_date <= self.week_end:
                    report_group = "7 Gün İçinde"
                else:
                    report_group = "Açık Yazılan"

                result.append(
                    CheckReportRow(
                        report_group=report_group,
                        check_type="Yazılan",
                        check_id=issued_check.id,
                        partner_name=supplier.name,
                        bank_text=_bank_text(bank.name, bank_account.account_name),
                        check_number=issued_check.check_number,
                        issue_or_received_date=issued_check.issue_date,
                        due_date=issued_check.due_date,
                        amount=Decimal(str(issued_check.amount)),
                        currency_code=_enum_value(issued_check.currency_code),
                        status=status_value,
                        reference_no=issued_check.reference_no,
                    )
                )

            return result

    def _load_received_open_rows(self) -> list[CheckReportRow]:
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
                    )
                )
                .order_by(ReceivedCheck.due_date.asc(), ReceivedCheck.id.asc())
            )

            rows = session.execute(statement).all()

            result: list[CheckReportRow] = []

            for received_check, customer, collection_bank_account, collection_bank in rows:
                if received_check.due_date < self.today:
                    report_group = "Vadesi Geçmiş"
                elif self.today <= received_check.due_date <= self.week_end:
                    report_group = "7 Gün İçinde"
                else:
                    report_group = "Açık Alınan"

                result.append(
                    CheckReportRow(
                        report_group=report_group,
                        check_type="Alınan",
                        check_id=received_check.id,
                        partner_name=customer.name,
                        bank_text=_bank_text(
                            collection_bank.name if collection_bank else None,
                            collection_bank_account.account_name if collection_bank_account else None,
                        ),
                        check_number=received_check.check_number,
                        issue_or_received_date=received_check.received_date,
                        due_date=received_check.due_date,
                        amount=Decimal(str(received_check.amount)),
                        currency_code=_enum_value(received_check.currency_code),
                        status=_enum_value(received_check.status),
                        reference_no=received_check.reference_no,
                    )
                )

            return result

    def _load_received_rows_by_status(
        self,
        *,
        statuses: list[ReceivedCheckStatus],
        report_group: str,
    ) -> list[CheckReportRow]:
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
                .where(ReceivedCheck.status.in_(statuses))
                .order_by(ReceivedCheck.due_date.asc(), ReceivedCheck.id.asc())
            )

            rows = session.execute(statement).all()

            result: list[CheckReportRow] = []

            for received_check, customer, collection_bank_account, collection_bank in rows:
                result.append(
                    CheckReportRow(
                        report_group=report_group,
                        check_type="Alınan",
                        check_id=received_check.id,
                        partner_name=customer.name,
                        bank_text=_bank_text(
                            collection_bank.name if collection_bank else None,
                            collection_bank_account.account_name if collection_bank_account else None,
                        ),
                        check_number=received_check.check_number,
                        issue_or_received_date=received_check.received_date,
                        due_date=received_check.due_date,
                        amount=Decimal(str(received_check.amount)),
                        currency_code=_enum_value(received_check.currency_code),
                        status=_enum_value(received_check.status),
                        reference_no=received_check.reference_no,
                    )
                )

            return result

    def _build_warning_card(self, message: str) -> QWidget:
        card = QFrame()
        card.setObjectName("ReportCardRisk")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(8)

        title = QLabel("Rapor bilgisi okunamadı")
        title.setObjectName("SectionTitle")

        body = QLabel(message)
        body.setObjectName("MutedText")
        body.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(body)

        return card

    def _build_summary_cards(self) -> QGridLayout:
        grid = QGridLayout()
        grid.setSpacing(10)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 1)
        grid.setColumnStretch(3, 1)

        overdue_rows = self._overdue_rows()
        due_soon_rows = self._due_soon_rows()
        problem_rows = self.report_data.received_problem_rows
        discount_and_endorse_rows = (
            self.report_data.received_discounted_rows
            + self.report_data.received_endorsed_rows
        )

        grid.addWidget(
            self._build_summary_card(
                "VADESİ GEÇEN AÇIK",
                str(len(overdue_rows)),
                _currency_totals_text(overdue_rows),
                "risk",
            ),
            0,
            0,
        )

        grid.addWidget(
            self._build_summary_card(
                "7 GÜN İÇİNDE",
                str(len(due_soon_rows)),
                _currency_totals_text(due_soon_rows),
                "normal",
            ),
            0,
            1,
        )

        grid.addWidget(
            self._build_summary_card(
                "PROBLEMLİ ALINAN",
                str(len(problem_rows)),
                _currency_totals_text(problem_rows),
                "risk",
            ),
            0,
            2,
        )

        grid.addWidget(
            self._build_summary_card(
                "İSKONTO / CİRO",
                str(len(discount_and_endorse_rows)),
                _currency_totals_text(discount_and_endorse_rows),
                "success",
            ),
            0,
            3,
        )

        return grid

    def _build_summary_card(
        self,
        title_text: str,
        value_text: str,
        hint_text: str,
        card_type: str,
    ) -> QWidget:
        card = QFrame()

        if card_type == "risk":
            card.setObjectName("ReportCardRisk")
        elif card_type == "success":
            card.setObjectName("ReportCardSuccess")
        else:
            card.setObjectName("ReportCard")

        card.setMinimumHeight(104)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(5)

        title = QLabel(title_text)
        title.setObjectName("ReportTitle")

        value = QLabel(value_text)
        value.setObjectName("ReportValue")

        hint = QLabel(hint_text)
        hint.setObjectName("ReportHint")
        hint.setWordWrap(True)

        layout.addWidget(title)
        layout.addStretch(1)
        layout.addWidget(value)
        layout.addWidget(hint)

        return card

    def _build_tabs(self) -> QWidget:
        tabs = QTabWidget()

        tabs.addTab(
            self._build_table_tab(
                title="Vade Takibi",
                subtitle="Vadesi geçmiş ve 7 gün içinde vadesi gelecek açık çekler.",
                rows=self._overdue_rows() + self._due_soon_rows(),
            ),
            "Vade Takibi",
        )

        tabs.addTab(
            self._build_table_tab(
                title="Açık Çekler",
                subtitle="Henüz sonuçlanmamış yazılan ve alınan çekler.",
                rows=self.report_data.issued_open_rows + self.report_data.received_open_rows,
            ),
            "Açık Çekler",
        )

        tabs.addTab(
            self._build_table_tab(
                title="Problemli Alınan",
                subtitle="Karşılıksız işaretlenen alınan çekler.",
                rows=self.report_data.received_problem_rows,
            ),
            "Problemli",
        )

        tabs.addTab(
            self._build_table_tab(
                title="İskonto / Ciro",
                subtitle="İskontoya verilen ve ciro edilen alınan çekler.",
                rows=self.report_data.received_discounted_rows + self.report_data.received_endorsed_rows,
            ),
            "İskonto / Ciro",
        )

        return tabs

    def _build_table_tab(
        self,
        *,
        title: str,
        subtitle: str,
        rows: list[CheckReportRow],
    ) -> QWidget:
        page = QWidget()

        layout = QVBoxLayout(page)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        title_label = QLabel(title)
        title_label.setObjectName("SectionTitle")

        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("MutedText")
        subtitle_label.setWordWrap(True)

        count_label = QLabel(
            f"Toplam {len(rows)} kayıt listeleniyor. Toplam: {_currency_totals_text(rows)}"
        )
        count_label.setObjectName("MutedText")
        count_label.setWordWrap(True)

        table = QTableWidget()
        table.setColumnCount(11)
        table.setHorizontalHeaderLabels(
            [
                "Grup",
                "Tür",
                "ID",
                "Taraf",
                "Banka / Hesap",
                "Çek No",
                "Alınış / Keşide",
                "Vade",
                "Tutar",
                "Durum",
                "Referans",
            ]
        )
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(False)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setWordWrap(False)
        table.setTextElideMode(Qt.ElideRight)
        table.verticalHeader().setDefaultSectionSize(34)
        table.verticalHeader().setMinimumSectionSize(30)
        table.setMinimumHeight(360)

        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(8, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(9, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(10, QHeaderView.ResizeToContents)

        self._fill_table(table, rows)

        layout.addWidget(title_label)
        layout.addWidget(subtitle_label)
        layout.addWidget(count_label)
        layout.addWidget(table, 1)

        return page

    def _fill_table(self, table: QTableWidget, rows: list[CheckReportRow]) -> None:
        sorted_rows = sorted(
            rows,
            key=lambda row: (
                row.due_date,
                row.check_type,
                row.partner_name.lower(),
                row.check_id,
            ),
        )

        table.setRowCount(len(sorted_rows))

        for row_index, row in enumerate(sorted_rows):
            values = [
                row.report_group,
                row.check_type,
                str(row.check_id),
                row.partner_name,
                row.bank_text,
                row.check_number,
                _format_date(row.issue_or_received_date),
                _format_date(row.due_date),
                format_currency_amount(row.amount, row.currency_code),
                _status_text(row.check_type, row.status),
                row.reference_no or "-",
            ]

            for column_index, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(str(value))

                if row.report_group == "Vadesi Geçmiş":
                    item.setForeground(QColor("#f59e0b"))
                elif row.report_group == "Problemli Alınan":
                    item.setForeground(QColor("#fbbf24"))
                elif row.status in {"DISCOUNTED", "ENDORSED"}:
                    item.setForeground(QColor("#38bdf8"))
                else:
                    item.setForeground(QColor("#e5e7eb"))

                if column_index == 8:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                else:
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)

                table.setItem(row_index, column_index, item)

        table.resizeRowsToContents()

    def _overdue_rows(self) -> list[CheckReportRow]:
        rows = self.report_data.issued_open_rows + self.report_data.received_open_rows

        return [
            row
            for row in rows
            if row.due_date < self.today
        ]

    def _due_soon_rows(self) -> list[CheckReportRow]:
        rows = self.report_data.issued_open_rows + self.report_data.received_open_rows

        return [
            row
            for row in rows
            if self.today <= row.due_date <= self.week_end
        ]