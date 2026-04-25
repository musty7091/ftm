import calendar
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy import select

from app.db.session import session_scope
from app.models.business_partner import BusinessPartner
from app.models.check import IssuedCheck, ReceivedCheck
from app.ui.ui_helpers import clear_layout


CALENDAR_PAGE_STYLE = """
QFrame#DueCalendarToolbar {
    background-color: #111827;
    border: 1px solid #1f2937;
    border-radius: 18px;
}

QFrame#DueCalendarSummaryStrip {
    background-color: rgba(15, 23, 42, 0.92);
    border: 1px solid #24324a;
    border-radius: 14px;
}

QFrame#DueCalendarBoard {
    background-color: #0b1220;
    border: 1px solid #1e293b;
    border-radius: 18px;
}

QFrame#DueCalendarDayCard {
    background-color: #111827;
    border: 1px solid #24324a;
    border-radius: 12px;
}

QFrame#DueCalendarTodayCard {
    background-color: rgba(37, 99, 235, 0.22);
    border: 2px solid #3b82f6;
    border-radius: 12px;
}

QFrame#DueCalendarSelectedCard {
    background-color: rgba(16, 185, 129, 0.18);
    border: 2px solid #10b981;
    border-radius: 12px;
}

QFrame#DueCalendarMutedCard {
    background-color: rgba(15, 23, 42, 0.48);
    border: 1px solid rgba(71, 85, 105, 0.32);
    border-radius: 12px;
}

QFrame#DueCalendarDetailCard {
    background-color: #111827;
    border: 1px solid #1f2937;
    border-radius: 18px;
}

QTableWidget {
    background-color: #0b1220;
    color: #e5e7eb;
    border: 1px solid #1e293b;
    border-radius: 12px;
    gridline-color: #1f2937;
    selection-background-color: #1d4ed8;
    selection-color: #ffffff;
}

QTableWidget::item {
    padding: 5px;
}

QHeaderView::section {
    background-color: #1e293b;
    color: #f8fafc;
    border: none;
    border-right: 1px solid #334155;
    padding: 7px;
    font-weight: 800;
}

QLabel#CalendarMonthTitle {
    color: #f8fafc;
    font-size: 22px;
    font-weight: 900;
}

QLabel#CalendarSectionTitle {
    color: #f8fafc;
    font-size: 16px;
    font-weight: 800;
}

QLabel#CalendarDialogTitle {
    color: #f8fafc;
    font-size: 20px;
    font-weight: 900;
}

QLabel#CalendarDayNumber {
    color: #f8fafc;
    font-size: 16px;
    font-weight: 900;
}

QLabel#CalendarMutedDayNumber {
    color: #64748b;
    font-size: 16px;
    font-weight: 800;
}

QLabel#CalendarWeekday {
    color: #bfdbfe;
    font-size: 12px;
    font-weight: 900;
}

QLabel#CalendarInfoText {
    color: #94a3b8;
    font-size: 12px;
}

QLabel#CalendarPillGreen {
    background-color: rgba(6, 78, 59, 0.36);
    color: #a7f3d0;
    border: 1px solid rgba(16, 185, 129, 0.38);
    border-radius: 8px;
    padding: 3px 6px;
    font-size: 10px;
    font-weight: 800;
}

QLabel#CalendarPillRed {
    background-color: rgba(127, 29, 29, 0.34);
    color: #fecaca;
    border: 1px solid rgba(239, 68, 68, 0.38);
    border-radius: 8px;
    padding: 3px 6px;
    font-size: 10px;
    font-weight: 800;
}

QLabel#CalendarPillBlue {
    background-color: rgba(30, 64, 175, 0.36);
    color: #bfdbfe;
    border: 1px solid rgba(59, 130, 246, 0.40);
    border-radius: 8px;
    padding: 3px 6px;
    font-size: 10px;
    font-weight: 800;
}

QLabel#CalendarPillAmber {
    background-color: rgba(120, 53, 15, 0.38);
    color: #fde68a;
    border: 1px solid rgba(245, 158, 11, 0.42);
    border-radius: 8px;
    padding: 3px 6px;
    font-size: 10px;
    font-weight: 800;
}

QLabel#CalendarPillMuted {
    background-color: rgba(51, 65, 85, 0.42);
    color: #cbd5e1;
    border: 1px solid rgba(100, 116, 139, 0.36);
    border-radius: 8px;
    padding: 3px 6px;
    font-size: 10px;
    font-weight: 800;
}

QPushButton#CalendarPrimaryButton {
    background-color: #2563eb;
    color: #ffffff;
    border: 1px solid #3b82f6;
    border-radius: 12px;
    padding: 9px 14px;
    text-align: center;
    font-weight: 800;
}

QPushButton#CalendarPrimaryButton:hover {
    background-color: #1d4ed8;
}

QPushButton#CalendarSecondaryButton {
    background-color: #1f2937;
    color: #cbd5e1;
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 9px 14px;
    text-align: center;
    font-weight: 700;
}

QPushButton#CalendarSecondaryButton:hover {
    background-color: #334155;
    color: #ffffff;
}

QComboBox {
    background-color: #0f172a;
    color: #f8fafc;
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 8px 10px;
}

QComboBox:focus {
    border: 1px solid #3b82f6;
}

QComboBox::drop-down {
    border: none;
    width: 26px;
}

QComboBox QAbstractItemView {
    background-color: #111827;
    color: #e5e7eb;
    border: 1px solid #334155;
    selection-background-color: #2563eb;
    selection-color: #ffffff;
    outline: 0;
}

QComboBox QAbstractItemView::item {
    min-height: 28px;
    padding: 8px;
    color: #e5e7eb;
    background-color: #111827;
}

QComboBox QAbstractItemView::item:selected {
    background-color: #2563eb;
    color: #ffffff;
}
"""


MONTH_NAMES_TR = {
    1: "Ocak",
    2: "Şubat",
    3: "Mart",
    4: "Nisan",
    5: "Mayıs",
    6: "Haziran",
    7: "Temmuz",
    8: "Ağustos",
    9: "Eylül",
    10: "Ekim",
    11: "Kasım",
    12: "Aralık",
}


WEEKDAY_NAMES_TR = [
    "Pazartesi",
    "Salı",
    "Çarşamba",
    "Perşembe",
    "Cuma",
    "Cumartesi",
    "Pazar",
]


RECEIVED_PENDING_STATUSES = {
    "PORTFOLIO",
    "GIVEN_TO_BANK",
    "IN_COLLECTION",
}

RECEIVED_PROBLEM_STATUSES = {
    "BOUNCED",
}

RECEIVED_CLOSED_STATUSES = {
    "COLLECTED",
    "ENDORSED",
    "DISCOUNTED",
    "RETURNED",
    "CANCELLED",
}

ISSUED_PENDING_STATUSES = {
    "PREPARED",
    "GIVEN",
}

ISSUED_PROBLEM_STATUSES = {
    "RISK",
}

ISSUED_CLOSED_STATUSES = {
    "PAID",
    "CANCELLED",
}


RECEIVED_STATUS_TEXTS = {
    "PORTFOLIO": "Portföyde",
    "GIVEN_TO_BANK": "Bankaya Verildi",
    "IN_COLLECTION": "Tahsilde",
    "COLLECTED": "Tahsil Edildi",
    "BOUNCED": "Karşılıksız",
    "RETURNED": "İade Edildi",
    "ENDORSED": "Ciro Edildi",
    "DISCOUNTED": "İskontoya Verildi",
    "CANCELLED": "İptal Edildi",
}


ISSUED_STATUS_TEXTS = {
    "PREPARED": "Hazırlandı",
    "GIVEN": "Verildi",
    "PAID": "Ödendi",
    "CANCELLED": "İptal Edildi",
    "RISK": "Riskli",
}


@dataclass(frozen=True)
class CalendarDayInfo:
    day_date: date
    is_current_month: bool
    is_today: bool
    is_selected: bool


@dataclass(frozen=True)
class DueCheckItem:
    check_type: str
    check_id: int
    party_name: str
    check_number: str
    due_date: date
    amount: Decimal
    currency_code: str
    status: str
    status_text: str
    reference_no: str | None
    description: str | None


@dataclass(frozen=True)
class DaySummary:
    received_count: int
    issued_count: int
    pending_count: int
    closed_count: int
    problem_count: int
    overdue_count: int
    received_totals: dict[str, Decimal]
    issued_totals: dict[str, Decimal]
    pending_totals: dict[str, Decimal]
    closed_totals: dict[str, Decimal]
    problem_totals: dict[str, Decimal]


def _month_start(value: date) -> date:
    return date(value.year, value.month, 1)


def _add_months(value: date, month_delta: int) -> date:
    month_index = value.month - 1 + month_delta
    year = value.year + month_index // 12
    month = month_index % 12 + 1

    return date(year, month, 1)


def _format_date_tr(value: date) -> str:
    return value.strftime("%d.%m.%Y")


def _format_month_title(value: date) -> str:
    return f"{MONTH_NAMES_TR.get(value.month, value.strftime('%B'))} {value.year}"


def _enum_value(value: Any) -> str:
    if value is None:
        return ""

    if hasattr(value, "value"):
        return str(value.value).strip().upper()

    return str(value).strip().upper()


def _format_decimal_tr(value: Decimal) -> str:
    formatted = f"{value:,.2f}"
    return formatted.replace(",", "X").replace(".", ",").replace("X", ".")


def _format_currency_amount(amount: Decimal, currency_code: str) -> str:
    return f"{_format_decimal_tr(Decimal(str(amount)))} {currency_code}"


def _format_currency_totals(currency_totals: dict[str, Decimal]) -> str:
    if not currency_totals:
        return "-"

    parts: list[str] = []

    for currency_code in sorted(currency_totals):
        parts.append(_format_currency_amount(currency_totals[currency_code], currency_code))

    return " / ".join(parts)


def _add_to_totals(totals: dict[str, Decimal], currency_code: str, amount: Decimal) -> None:
    totals[currency_code] = (
        totals.get(currency_code, Decimal("0.00")) + amount
    ).quantize(Decimal("0.01"))


def _received_status_text(value: Any) -> str:
    status = _enum_value(value)

    return RECEIVED_STATUS_TEXTS.get(status, status or "-")


def _issued_status_text(value: Any) -> str:
    status = _enum_value(value)

    return ISSUED_STATUS_TEXTS.get(status, status or "-")


def _check_status_group(check_type: str, status: str) -> str:
    if check_type == "RECEIVED":
        if status in RECEIVED_PENDING_STATUSES:
            return "PENDING"
        if status in RECEIVED_PROBLEM_STATUSES:
            return "PROBLEM"
        if status in RECEIVED_CLOSED_STATUSES:
            return "CLOSED"

    if check_type == "ISSUED":
        if status in ISSUED_PENDING_STATUSES:
            return "PENDING"
        if status in ISSUED_PROBLEM_STATUSES:
            return "PROBLEM"
        if status in ISSUED_CLOSED_STATUSES:
            return "CLOSED"

    return "ALL"


def _days_text(target_date: date, today: date) -> str:
    difference = (target_date - today).days

    if difference == 0:
        return "Bugün"
    if difference > 0:
        return f"{difference} gün"
    return f"{abs(difference)} gün geçti"


class CalendarDayCard(QFrame):
    def __init__(
        self,
        *,
        day_info: CalendarDayInfo,
        day_summary: DaySummary,
        on_click: Callable[[date], None],
        on_double_click: Callable[[date], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.day_info = day_info
        self.day_summary = day_summary
        self.on_click = on_click
        self.on_double_click = on_double_click

        if day_info.is_selected:
            self.setObjectName("DueCalendarSelectedCard")
        elif day_info.is_today:
            self.setObjectName("DueCalendarTodayCard")
        elif not day_info.is_current_month:
            self.setObjectName("DueCalendarMutedCard")
        else:
            self.setObjectName("DueCalendarDayCard")

        self.setMinimumHeight(90)
        self.setCursor(Qt.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        number_row = QHBoxLayout()
        number_row.setSpacing(6)

        day_number = QLabel(str(day_info.day_date.day))
        day_number.setObjectName(
            "CalendarDayNumber"
            if day_info.is_current_month
            else "CalendarMutedDayNumber"
        )

        number_row.addWidget(day_number)
        number_row.addStretch(1)

        if day_info.is_today:
            today_label = QLabel("BUGÜN")
            today_label.setObjectName("CalendarPillBlue")
            number_row.addWidget(today_label)

        layout.addLayout(number_row)
        layout.addStretch(1)

        if day_summary.received_count > 0:
            received_totals_text = _format_currency_totals(day_summary.received_totals)
            received_label = QLabel(f"Alınan: {day_summary.received_count}")
            received_label.setObjectName("CalendarPillGreen")
            received_label.setToolTip(f"Alınan çek toplamı: {received_totals_text}")
            layout.addWidget(received_label)

        if day_summary.issued_count > 0:
            issued_totals_text = _format_currency_totals(day_summary.issued_totals)
            issued_label = QLabel(f"Yazılan: {day_summary.issued_count}")
            issued_label.setObjectName("CalendarPillRed")
            issued_label.setToolTip(f"Yazılan çek toplamı: {issued_totals_text}")
            layout.addWidget(issued_label)

        if day_summary.pending_count > 0:
            pending_totals_text = _format_currency_totals(day_summary.pending_totals)
            pending_label = QLabel(f"Bekleyen: {day_summary.pending_count}")
            pending_label.setObjectName("CalendarPillBlue")
            pending_label.setToolTip(f"Bekleyen çek toplamı: {pending_totals_text}")
            layout.addWidget(pending_label)

        if day_summary.closed_count > 0:
            closed_totals_text = _format_currency_totals(day_summary.closed_totals)
            closed_label = QLabel(f"Sonuç: {day_summary.closed_count}")
            closed_label.setObjectName("CalendarPillMuted")
            closed_label.setToolTip(f"Sonuçlanan çek toplamı: {closed_totals_text}")
            layout.addWidget(closed_label)

        warning_count = day_summary.problem_count + day_summary.overdue_count

        if warning_count > 0:
            problem_totals_text = _format_currency_totals(day_summary.problem_totals)
            warning_label = QLabel(f"Problem: {warning_count}")
            warning_label.setObjectName("CalendarPillAmber")
            warning_label.setToolTip(
                f"Problem/Risk: {day_summary.problem_count} | "
                f"Vadesi geçmiş bekleyen: {day_summary.overdue_count} | "
                f"Tutar: {problem_totals_text}"
            )
            layout.addWidget(warning_label)

    def mousePressEvent(self, event: Any) -> None:
        self.on_click(self.day_info.day_date)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: Any) -> None:
        self.on_double_click(self.day_info.day_date)
        super().mouseDoubleClickEvent(event)


class DueCheckDetailDialog(QDialog):
    def __init__(
        self,
        *,
        parent: QWidget | None,
        selected_date: date,
        today: date,
        items: list[DueCheckItem],
    ) -> None:
        super().__init__(parent)

        self.selected_date = selected_date
        self.today = today
        self.items = items

        self.setWindowTitle(f"Vade Detayları - {_format_date_tr(selected_date)}")
        self.resize(1120, 680)
        self.setMinimumSize(980, 580)
        self.setModal(True)
        self.setStyleSheet(
            CALENDAR_PAGE_STYLE
            + """
            QDialog {
                background-color: #0f172a;
            }
            """
        )

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(22, 22, 22, 22)
        root_layout.setSpacing(0)

        card = QFrame()
        card.setObjectName("DueCalendarDetailCard")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(12)

        title = QLabel(f"Seçili Gün Detayları: {_format_date_tr(selected_date)}")
        title.setObjectName("CalendarDialogTitle")

        subtitle = QLabel(
            "Bu pencerede seçili güne ait alınan ve yazılan çekler listelenir."
            if items
            else "Bu güne ait çek kaydı bulunmuyor."
        )
        subtitle.setObjectName("CalendarInfoText")
        subtitle.setWordWrap(True)

        summary = self._build_summary(items)

        summary_row = QHBoxLayout()
        summary_row.setSpacing(10)

        received_label = QLabel(
            f"Alınan: {summary.received_count} / {_format_currency_totals(summary.received_totals)}"
        )
        received_label.setObjectName("CalendarPillGreen")

        issued_label = QLabel(
            f"Yazılan: {summary.issued_count} / {_format_currency_totals(summary.issued_totals)}"
        )
        issued_label.setObjectName("CalendarPillRed")

        pending_label = QLabel(
            f"Bekleyen: {summary.pending_count} / {_format_currency_totals(summary.pending_totals)}"
        )
        pending_label.setObjectName("CalendarPillBlue")

        closed_label = QLabel(
            f"Sonuçlanan: {summary.closed_count} / {_format_currency_totals(summary.closed_totals)}"
        )
        closed_label.setObjectName("CalendarPillMuted")

        warning_label = QLabel(
            f"Problem: {summary.problem_count} | Vadesi geçmiş: {summary.overdue_count}"
        )
        warning_label.setObjectName("CalendarPillAmber")

        summary_row.addWidget(received_label)
        summary_row.addWidget(issued_label)
        summary_row.addWidget(pending_label)
        summary_row.addWidget(closed_label)
        summary_row.addWidget(warning_label)
        summary_row.addStretch(1)

        table = self._build_table()
        self._fill_table(table)

        button_row = QHBoxLayout()
        button_row.addStretch(1)

        close_button = QPushButton("Kapat")
        close_button.setObjectName("CalendarSecondaryButton")
        close_button.setMinimumHeight(40)
        close_button.clicked.connect(self.accept)

        button_row.addWidget(close_button)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addLayout(summary_row)
        layout.addWidget(table, 1)
        layout.addLayout(button_row)

        root_layout.addWidget(card)

    def _build_summary(self, items: list[DueCheckItem]) -> DaySummary:
        return CheckDueCalendarPage.build_summary_from_items(
            items=items,
            today=self.today,
        )

    def _build_table(self) -> QTableWidget:
        table = QTableWidget()
        table.setColumnCount(9)
        table.setHorizontalHeaderLabels(
            [
                "Tür",
                "Taraf",
                "Çek No",
                "Vade",
                "Kalan",
                "Tutar",
                "Durum",
                "Referans",
                "Açıklama",
            ]
        )
        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setWordWrap(False)
        table.setTextElideMode(Qt.ElideRight)
        table.verticalHeader().setDefaultSectionSize(32)
        table.verticalHeader().setMinimumSectionSize(28)

        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(8, QHeaderView.Stretch)

        return table

    def _fill_table(self, table: QTableWidget) -> None:
        table.setRowCount(len(self.items))

        for row_index, item in enumerate(self.items):
            type_text = "Alınan" if item.check_type == "RECEIVED" else "Yazılan"
            amount_text = _format_currency_amount(item.amount, item.currency_code)
            days_text = _days_text(item.due_date, self.today)
            status_group = _check_status_group(item.check_type, item.status)

            if status_group == "PENDING":
                status_text = f"Bekleyen - {item.status_text}"
            elif status_group == "CLOSED":
                status_text = f"Sonuçlanan - {item.status_text}"
            elif status_group == "PROBLEM":
                status_text = f"Problemli - {item.status_text}"
            else:
                status_text = item.status_text

            values = [
                type_text,
                item.party_name,
                item.check_number,
                _format_date_tr(item.due_date),
                days_text,
                amount_text,
                status_text,
                item.reference_no or "-",
                item.description or "-",
            ]

            for column_index, value in enumerate(values):
                table_item = QTableWidgetItem(value)

                if item.check_type == "RECEIVED":
                    base_color = QColor("#a7f3d0")
                else:
                    base_color = QColor("#fecaca")

                if status_group == "PROBLEM":
                    base_color = QColor("#fbbf24")
                elif status_group == "CLOSED":
                    base_color = QColor("#94a3b8")
                elif status_group == "PENDING" and item.due_date < self.today:
                    base_color = QColor("#f87171")

                table_item.setForeground(base_color)

                if column_index == 5:
                    table_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                else:
                    table_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)

                table_item.setToolTip(
                    "\n".join(
                        [
                            f"Tür: {type_text}",
                            f"Taraf: {item.party_name}",
                            f"Çek No: {item.check_number}",
                            f"Vade: {_format_date_tr(item.due_date)}",
                            f"Kalan: {days_text}",
                            f"Tutar: {amount_text}",
                            f"Durum: {status_text}",
                            f"Referans: {item.reference_no or '-'}",
                            f"Açıklama: {item.description or '-'}",
                        ]
                    )
                )

                table.setItem(row_index, column_index, table_item)

        table.resizeRowsToContents()


class CheckDueCalendarPage(QWidget):
    def __init__(self, current_user: Any | None = None) -> None:
        super().__init__()

        self.current_user = current_user
        self.today = date.today()
        self.current_month = _month_start(self.today)
        self.selected_date = self.today
        self.due_items_by_date: dict[date, list[DueCheckItem]] = {}

        self.setObjectName("CheckDueCalendarPage")
        self.setStyleSheet(CALENDAR_PAGE_STYLE)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(10)

        self.toolbar = self._build_toolbar()
        self.summary_strip = self._build_summary_strip()
        calendar_board = self._build_calendar_board()

        root_layout.addWidget(self.toolbar)
        root_layout.addWidget(self.summary_strip)
        root_layout.addWidget(calendar_board, 1)

        self._render_calendar()
        self._update_selected_day_summary()

    @staticmethod
    def build_summary_from_items(
        *,
        items: list[DueCheckItem],
        today: date,
    ) -> DaySummary:
        received_count = 0
        issued_count = 0
        pending_count = 0
        closed_count = 0
        problem_count = 0
        overdue_count = 0

        received_totals: dict[str, Decimal] = {}
        issued_totals: dict[str, Decimal] = {}
        pending_totals: dict[str, Decimal] = {}
        closed_totals: dict[str, Decimal] = {}
        problem_totals: dict[str, Decimal] = {}

        for item in items:
            status_group = _check_status_group(item.check_type, item.status)

            if item.check_type == "RECEIVED":
                received_count += 1
                _add_to_totals(received_totals, item.currency_code, item.amount)

            if item.check_type == "ISSUED":
                issued_count += 1
                _add_to_totals(issued_totals, item.currency_code, item.amount)

            if status_group == "PENDING":
                pending_count += 1
                _add_to_totals(pending_totals, item.currency_code, item.amount)

                if item.due_date < today:
                    overdue_count += 1

            if status_group == "CLOSED":
                closed_count += 1
                _add_to_totals(closed_totals, item.currency_code, item.amount)

            if status_group == "PROBLEM":
                problem_count += 1
                _add_to_totals(problem_totals, item.currency_code, item.amount)

        return DaySummary(
            received_count=received_count,
            issued_count=issued_count,
            pending_count=pending_count,
            closed_count=closed_count,
            problem_count=problem_count,
            overdue_count=overdue_count,
            received_totals=received_totals,
            issued_totals=issued_totals,
            pending_totals=pending_totals,
            closed_totals=closed_totals,
            problem_totals=problem_totals,
        )

    def _build_toolbar(self) -> QWidget:
        toolbar = QFrame()
        toolbar.setObjectName("DueCalendarToolbar")

        layout = QVBoxLayout(toolbar)
        layout.setContentsMargins(18, 12, 18, 12)
        layout.setSpacing(10)

        top_row = QHBoxLayout()
        top_row.setSpacing(10)

        type_label = QLabel("Çek türü")
        type_label.setObjectName("MutedText")

        self.check_type_combo = QComboBox()
        self.check_type_combo.setMinimumHeight(36)
        self.check_type_combo.addItem("Tümü", "ALL")
        self.check_type_combo.addItem("Sadece Alınan Çekler", "RECEIVED")
        self.check_type_combo.addItem("Sadece Yazılan Çekler", "ISSUED")
        self.check_type_combo.currentIndexChanged.connect(self._filters_changed)

        status_label = QLabel("Durum")
        status_label.setObjectName("MutedText")

        self.status_combo = QComboBox()
        self.status_combo.setMinimumHeight(36)
        self.status_combo.addItem("Tümü", "ALL")
        self.status_combo.addItem("Bekleyen Çekler", "PENDING")
        self.status_combo.addItem("Sonuçlanan Çekler", "CLOSED")
        self.status_combo.addItem("Problemli / Riskli", "PROBLEM")
        self.status_combo.currentIndexChanged.connect(self._filters_changed)

        self.previous_month_button = QPushButton("Önceki Ay")
        self.previous_month_button.setObjectName("CalendarSecondaryButton")
        self.previous_month_button.setMinimumHeight(36)
        self.previous_month_button.clicked.connect(self._go_previous_month)

        self.month_title_label = QLabel("")
        self.month_title_label.setObjectName("CalendarMonthTitle")
        self.month_title_label.setAlignment(Qt.AlignCenter)
        self.month_title_label.setMinimumWidth(150)

        self.next_month_button = QPushButton("Sonraki Ay")
        self.next_month_button.setObjectName("CalendarSecondaryButton")
        self.next_month_button.setMinimumHeight(36)
        self.next_month_button.clicked.connect(self._go_next_month)

        self.today_button = QPushButton("Bugüne Git")
        self.today_button.setObjectName("CalendarPrimaryButton")
        self.today_button.setMinimumHeight(36)
        self.today_button.clicked.connect(self._go_today)

        self.detail_button = QPushButton("Detayları Göster")
        self.detail_button.setObjectName("CalendarPrimaryButton")
        self.detail_button.setMinimumHeight(36)
        self.detail_button.clicked.connect(self._open_selected_day_details)

        top_row.addWidget(type_label)
        top_row.addWidget(self.check_type_combo)
        top_row.addWidget(status_label)
        top_row.addWidget(self.status_combo)
        top_row.addStretch(1)
        top_row.addWidget(self.previous_month_button)
        top_row.addWidget(self.month_title_label)
        top_row.addWidget(self.next_month_button)
        top_row.addWidget(self.today_button)
        top_row.addWidget(self.detail_button)

        month_summary_row = QHBoxLayout()
        month_summary_row.setSpacing(10)

        self.month_received_label = QLabel("Bu Ay Alınan: -")
        self.month_received_label.setObjectName("CalendarPillGreen")

        self.month_issued_label = QLabel("Bu Ay Yazılan: -")
        self.month_issued_label.setObjectName("CalendarPillRed")

        self.month_pending_label = QLabel("Bu Ay Bekleyen: -")
        self.month_pending_label.setObjectName("CalendarPillBlue")

        self.month_closed_label = QLabel("Bu Ay Sonuçlanan: -")
        self.month_closed_label.setObjectName("CalendarPillMuted")

        self.month_problem_label = QLabel("Bu Ay Problem: -")
        self.month_problem_label.setObjectName("CalendarPillAmber")

        self.month_overdue_label = QLabel("Vadesi Geçmiş: -")
        self.month_overdue_label.setObjectName("CalendarPillAmber")

        legend_title = QLabel("Renk")
        legend_title.setObjectName("MutedText")

        received = QLabel("Alınan")
        received.setObjectName("CalendarPillGreen")

        issued = QLabel("Yazılan")
        issued.setObjectName("CalendarPillRed")

        pending = QLabel("Bekleyen")
        pending.setObjectName("CalendarPillBlue")

        closed = QLabel("Sonuç")
        closed.setObjectName("CalendarPillMuted")

        problem = QLabel("Problem")
        problem.setObjectName("CalendarPillAmber")

        month_summary_row.addWidget(self.month_received_label)
        month_summary_row.addWidget(self.month_issued_label)
        month_summary_row.addWidget(self.month_pending_label)
        month_summary_row.addWidget(self.month_closed_label)
        month_summary_row.addWidget(self.month_problem_label)
        month_summary_row.addWidget(self.month_overdue_label)
        month_summary_row.addStretch(1)
        month_summary_row.addWidget(legend_title)
        month_summary_row.addWidget(received)
        month_summary_row.addWidget(issued)
        month_summary_row.addWidget(pending)
        month_summary_row.addWidget(closed)
        month_summary_row.addWidget(problem)

        layout.addLayout(top_row)
        layout.addLayout(month_summary_row)

        return toolbar

    def _build_summary_strip(self) -> QWidget:
        strip = QFrame()
        strip.setObjectName("DueCalendarSummaryStrip")

        layout = QHBoxLayout(strip)
        layout.setContentsMargins(14, 8, 14, 8)
        layout.setSpacing(10)

        self.selected_day_label = QLabel("Seçili Gün: -")
        self.selected_day_label.setObjectName("CalendarSectionTitle")

        self.selected_day_note_label = QLabel("")
        self.selected_day_note_label.setObjectName("CalendarInfoText")

        self.selected_day_received_label = QLabel("Alınan: -")
        self.selected_day_received_label.setObjectName("CalendarPillGreen")

        self.selected_day_issued_label = QLabel("Yazılan: -")
        self.selected_day_issued_label.setObjectName("CalendarPillRed")

        self.selected_day_pending_label = QLabel("Bekleyen: -")
        self.selected_day_pending_label.setObjectName("CalendarPillBlue")

        self.selected_day_closed_label = QLabel("Sonuçlanan: -")
        self.selected_day_closed_label.setObjectName("CalendarPillMuted")

        self.selected_day_problem_label = QLabel("Problem: -")
        self.selected_day_problem_label.setObjectName("CalendarPillAmber")

        layout.addWidget(self.selected_day_label)
        layout.addWidget(self.selected_day_note_label, 1)
        layout.addWidget(self.selected_day_received_label)
        layout.addWidget(self.selected_day_issued_label)
        layout.addWidget(self.selected_day_pending_label)
        layout.addWidget(self.selected_day_closed_label)
        layout.addWidget(self.selected_day_problem_label)

        return strip

    def _build_calendar_board(self) -> QWidget:
        calendar_board = QFrame()
        calendar_board.setObjectName("DueCalendarBoard")

        calendar_layout = QVBoxLayout(calendar_board)
        calendar_layout.setContentsMargins(14, 12, 14, 12)
        calendar_layout.setSpacing(8)

        self.calendar_grid = QGridLayout()
        self.calendar_grid.setSpacing(8)

        calendar_layout.addLayout(self.calendar_grid)

        return calendar_board

    def _filters_changed(self) -> None:
        self._render_calendar()
        self._update_selected_day_summary()

    def _selected_check_type_filter(self) -> str:
        return str(self.check_type_combo.currentData() or "ALL")

    def _selected_status_filter(self) -> str:
        return str(self.status_combo.currentData() or "ALL")

    def _calendar_weeks(self) -> list[list[date]]:
        calendar_builder = calendar.Calendar(firstweekday=0)

        return calendar_builder.monthdatescalendar(
            self.current_month.year,
            self.current_month.month,
        )

    def _render_calendar(self) -> None:
        clear_layout(self.calendar_grid)

        self.month_title_label.setText(_format_month_title(self.current_month))

        month_weeks = self._calendar_weeks()
        visible_start = month_weeks[0][0]
        visible_end = month_weeks[-1][-1]

        self.due_items_by_date = self._load_due_items_by_date(
            start_date=visible_start,
            end_date=visible_end,
        )

        self._update_month_summary()

        for column_index, weekday_name in enumerate(WEEKDAY_NAMES_TR):
            weekday_label = QLabel(weekday_name)
            weekday_label.setObjectName("CalendarWeekday")
            weekday_label.setAlignment(Qt.AlignCenter)
            self.calendar_grid.addWidget(weekday_label, 0, column_index)

        for row_index, week in enumerate(month_weeks, start=1):
            for column_index, day_date in enumerate(week):
                day_items = self.due_items_by_date.get(day_date, [])
                day_summary = self._build_day_summary(day_items)

                day_info = CalendarDayInfo(
                    day_date=day_date,
                    is_current_month=day_date.month == self.current_month.month,
                    is_today=day_date == self.today,
                    is_selected=day_date == self.selected_date,
                )

                card = CalendarDayCard(
                    day_info=day_info,
                    day_summary=day_summary,
                    on_click=self._select_day,
                    on_double_click=self._open_day_details_by_date,
                    parent=self,
                )

                self.calendar_grid.addWidget(card, row_index, column_index)

        for column_index in range(7):
            self.calendar_grid.setColumnStretch(column_index, 1)

        for row_index in range(len(month_weeks) + 1):
            self.calendar_grid.setRowStretch(row_index, 1)

    def _load_due_items_by_date(
        self,
        *,
        start_date: date,
        end_date: date,
    ) -> dict[date, list[DueCheckItem]]:
        items_by_date: dict[date, list[DueCheckItem]] = {}

        check_type_filter = self._selected_check_type_filter()
        status_filter = self._selected_status_filter()

        with session_scope() as session:
            if check_type_filter in {"ALL", "RECEIVED"}:
                received_statement = (
                    select(ReceivedCheck, BusinessPartner)
                    .join(BusinessPartner, ReceivedCheck.customer_id == BusinessPartner.id)
                    .where(
                        ReceivedCheck.due_date >= start_date,
                        ReceivedCheck.due_date <= end_date,
                    )
                    .order_by(
                        ReceivedCheck.due_date.asc(),
                        ReceivedCheck.id.asc(),
                    )
                )

                received_rows = session.execute(received_statement).all()

                for received_check, customer in received_rows:
                    status = _enum_value(received_check.status)
                    group = _check_status_group("RECEIVED", status)

                    if status_filter != "ALL" and group != status_filter:
                        continue

                    due_date = received_check.due_date
                    amount = Decimal(str(received_check.amount or "0.00")).quantize(Decimal("0.01"))
                    currency_code = _enum_value(received_check.currency_code) or "TRY"

                    item = DueCheckItem(
                        check_type="RECEIVED",
                        check_id=received_check.id,
                        party_name=customer.name,
                        check_number=received_check.check_number,
                        due_date=due_date,
                        amount=amount,
                        currency_code=currency_code,
                        status=status,
                        status_text=_received_status_text(status),
                        reference_no=received_check.reference_no,
                        description=received_check.description,
                    )

                    items_by_date.setdefault(due_date, []).append(item)

            if check_type_filter in {"ALL", "ISSUED"}:
                issued_statement = (
                    select(IssuedCheck, BusinessPartner)
                    .join(BusinessPartner, IssuedCheck.supplier_id == BusinessPartner.id)
                    .where(
                        IssuedCheck.due_date >= start_date,
                        IssuedCheck.due_date <= end_date,
                    )
                    .order_by(
                        IssuedCheck.due_date.asc(),
                        IssuedCheck.id.asc(),
                    )
                )

                issued_rows = session.execute(issued_statement).all()

                for issued_check, supplier in issued_rows:
                    status = _enum_value(issued_check.status)
                    group = _check_status_group("ISSUED", status)

                    if status_filter != "ALL" and group != status_filter:
                        continue

                    due_date = issued_check.due_date
                    amount = Decimal(str(issued_check.amount or "0.00")).quantize(Decimal("0.01"))
                    currency_code = _enum_value(issued_check.currency_code) or "TRY"

                    item = DueCheckItem(
                        check_type="ISSUED",
                        check_id=issued_check.id,
                        party_name=supplier.name,
                        check_number=issued_check.check_number,
                        due_date=due_date,
                        amount=amount,
                        currency_code=currency_code,
                        status=status,
                        status_text=_issued_status_text(status),
                        reference_no=issued_check.reference_no,
                        description=issued_check.description,
                    )

                    items_by_date.setdefault(due_date, []).append(item)

        for day_date in items_by_date:
            items_by_date[day_date].sort(
                key=lambda item: (
                    item.check_type,
                    item.party_name.lower(),
                    item.check_id,
                )
            )

        return items_by_date

    def _build_day_summary(self, items: list[DueCheckItem]) -> DaySummary:
        return self.build_summary_from_items(
            items=items,
            today=self.today,
        )

    def _current_month_items(self) -> list[DueCheckItem]:
        items: list[DueCheckItem] = []

        for day_date, day_items in self.due_items_by_date.items():
            if day_date.year == self.current_month.year and day_date.month == self.current_month.month:
                items.extend(day_items)

        return items

    def _update_month_summary(self) -> None:
        month_items = self._current_month_items()
        month_summary = self._build_day_summary(month_items)

        self.month_received_label.setText(
            f"Bu Ay Alınan: {month_summary.received_count} / {_format_currency_totals(month_summary.received_totals)}"
        )
        self.month_issued_label.setText(
            f"Bu Ay Yazılan: {month_summary.issued_count} / {_format_currency_totals(month_summary.issued_totals)}"
        )
        self.month_pending_label.setText(
            f"Bu Ay Bekleyen: {month_summary.pending_count} / {_format_currency_totals(month_summary.pending_totals)}"
        )
        self.month_closed_label.setText(
            f"Bu Ay Sonuçlanan: {month_summary.closed_count} / {_format_currency_totals(month_summary.closed_totals)}"
        )
        self.month_problem_label.setText(
            f"Bu Ay Problem: {month_summary.problem_count} / {_format_currency_totals(month_summary.problem_totals)}"
        )
        self.month_overdue_label.setText(
            f"Vadesi Geçmiş: {month_summary.overdue_count}"
        )

    def _select_day(self, selected_date: date) -> None:
        self.selected_date = selected_date

        if selected_date.month != self.current_month.month or selected_date.year != self.current_month.year:
            self.current_month = _month_start(selected_date)

        self._render_calendar()
        self._update_selected_day_summary()

    def _update_selected_day_summary(self) -> None:
        selected_items = self.due_items_by_date.get(self.selected_date, [])
        summary = self._build_day_summary(selected_items)

        self.selected_day_label.setText(f"Seçili Gün: {_format_date_tr(self.selected_date)}")

        if self.selected_date == self.today:
            day_note = "Bugün"
        elif self.selected_date < self.today:
            day_note = "Geçmiş tarih"
        else:
            day_note = "Gelecek tarih"

        self.selected_day_note_label.setText(
            f"{day_note} | {len(selected_items)} çek kaydı"
            if selected_items
            else f"{day_note} | Çek kaydı yok"
        )

        self.selected_day_received_label.setText(
            f"Alınan: {summary.received_count} / {_format_currency_totals(summary.received_totals)}"
        )
        self.selected_day_issued_label.setText(
            f"Yazılan: {summary.issued_count} / {_format_currency_totals(summary.issued_totals)}"
        )
        self.selected_day_pending_label.setText(
            f"Bekleyen: {summary.pending_count} / {_format_currency_totals(summary.pending_totals)}"
        )
        self.selected_day_closed_label.setText(
            f"Sonuçlanan: {summary.closed_count} / {_format_currency_totals(summary.closed_totals)}"
        )
        self.selected_day_problem_label.setText(
            f"Problem: {summary.problem_count} | Vadesi geçmiş: {summary.overdue_count}"
        )

        self.detail_button.setEnabled(bool(selected_items))

    def _open_selected_day_details(self) -> None:
        self._open_day_details_by_date(self.selected_date)

    def _open_day_details_by_date(self, selected_date: date) -> None:
        self.selected_date = selected_date

        if selected_date.month != self.current_month.month or selected_date.year != self.current_month.year:
            self.current_month = _month_start(selected_date)
            self._render_calendar()

        self._update_selected_day_summary()

        selected_items = self.due_items_by_date.get(selected_date, [])

        if not selected_items:
            return

        dialog = DueCheckDetailDialog(
            parent=self,
            selected_date=selected_date,
            today=self.today,
            items=selected_items,
        )
        dialog.exec()

    def _go_previous_month(self) -> None:
        self.current_month = _add_months(self.current_month, -1)

        if self.selected_date.month != self.current_month.month or self.selected_date.year != self.current_month.year:
            self.selected_date = self.current_month

        self._render_calendar()
        self._update_selected_day_summary()

    def _go_next_month(self) -> None:
        self.current_month = _add_months(self.current_month, 1)

        if self.selected_date.month != self.current_month.month or self.selected_date.year != self.current_month.year:
            self.selected_date = self.current_month

        self._render_calendar()
        self._update_selected_day_summary()

    def _go_today(self) -> None:
        self.today = date.today()
        self.current_month = _month_start(self.today)
        self.selected_date = self.today

        self._render_calendar()
        self._update_selected_day_summary()