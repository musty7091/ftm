import calendar
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
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
from app.ui.pages.checks.due_day_report_dialog import DueDayReportDialog


CALENDAR_PAGE_STYLE = """
QFrame#DueCalendarToolbar {
    background-color: #111827;
    border: 1px solid #1f2937;
    border-radius: 16px;
}

QFrame#DueCalendarSummaryStrip {
    background-color: #0b1220;
    border: 1px solid #1e293b;
    border-radius: 16px;
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

QFrame#DueCalendarDayCard:hover {
    border: 1px solid #3b82f6;
}

QFrame#DueCalendarTodayCard {
    background-color: #111827;
    border: 1px solid #3b82f6;
    border-radius: 12px;
}

QFrame#DueCalendarSelectedCard {
    background-color: rgba(37, 99, 235, 0.14);
    border: 2px solid #3b82f6;
    border-radius: 12px;
}

QFrame#DueCalendarEmptyCell {
    background-color: transparent;
    border: none;
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
    font-weight: 600;
}

QLabel#CalendarMonthTitle {
    color: #f8fafc;
    font-size: 22px;
    font-weight: 700;
}

QLabel#CalendarSectionTitle {
    color: #f8fafc;
    font-size: 16px;
    font-weight: 650;
}

QLabel#CalendarDayNumber {
    color: #f8fafc;
    font-size: 14px;
    font-weight: 600;
}

QLabel#CalendarWeekday {
    color: #bfdbfe;
    font-size: 12px;
    font-weight: 500;
}

QLabel#CalendarInfoText {
    color: #94a3b8;
    font-size: 12px;
}

QLabel#CalendarSmallText {
    color: #cbd5e1;
    font-size: 10px;
    font-weight: 450;
}

QLabel#CalendarTinyMuted {
    color: #64748b;
    font-size: 10px;
    font-weight: 500;
}

QLabel#CalendarTodayBadge {
    background-color: rgba(37, 99, 235, 0.22);
    color: #bfdbfe;
    border: 1px solid rgba(59, 130, 246, 0.42);
    border-radius: 8px;
    padding: 2px 6px;
    font-size: 9px;
    font-weight: 500;
}

QLabel#CalendarRiskBadge {
    background-color: rgba(120, 53, 15, 0.38);
    color: #fde68a;
    border: 1px solid rgba(245, 158, 11, 0.42);
    border-radius: 8px;
    padding: 2px 6px;
    font-size: 9px;
    font-weight: 500;
}

QLabel#CalendarNetPositive {
    color: #a7f3d0;
    font-size: 10px;
    font-weight: 600;
}

QLabel#CalendarNetNegative {
    color: #fecaca;
    font-size: 10px;
    font-weight: 600;
}

QLabel#CalendarNetNeutral {
    color: #cbd5e1;
    font-size: 10px;
    font-weight: 500;
}

QLabel#CalendarSummaryBox {
    background-color: #101827;
    color: #cbd5e1;
    border: 1px solid #24324a;
    border-radius: 12px;
    padding: 8px 10px;
    font-size: 12px;
    font-weight: 600;
}

QLabel#CalendarSummaryPositive {
    background-color: rgba(6, 78, 59, 0.24);
    color: #a7f3d0;
    border: 1px solid rgba(16, 185, 129, 0.34);
    border-radius: 12px;
    padding: 8px 10px;
    font-size: 12px;
    font-weight: 500;
}

QLabel#CalendarSummaryNegative {
    background-color: rgba(127, 29, 29, 0.22);
    color: #fecaca;
    border: 1px solid rgba(239, 68, 68, 0.34);
    border-radius: 12px;
    padding: 8px 10px;
    font-size: 12px;
    font-weight: 500;
}

QLabel#CalendarSummaryWarning {
    background-color: rgba(120, 53, 15, 0.24);
    color: #fde68a;
    border: 1px solid rgba(245, 158, 11, 0.34);
    border-radius: 12px;
    padding: 8px 10px;
    font-size: 12px;
    font-weight: 500;
}

QPushButton#CalendarPrimaryButton {
    background-color: #2563eb;
    color: #ffffff;
    border: 1px solid #3b82f6;
    border-radius: 11px;
    padding: 8px 13px;
    text-align: center;
    font-weight: 600;
}

QPushButton#CalendarPrimaryButton:hover {
    background-color: #1d4ed8;
}

QPushButton#CalendarSecondaryButton {
    background-color: #1f2937;
    color: #cbd5e1;
    border: 1px solid #334155;
    border-radius: 11px;
    padding: 8px 13px;
    text-align: center;
    font-weight: 500;
}

QPushButton#CalendarSecondaryButton:hover {
    background-color: #334155;
    color: #ffffff;
}

QComboBox {
    background-color: #0f172a;
    color: #f8fafc;
    border: 1px solid #334155;
    border-radius: 11px;
    padding: 7px 10px;
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
    item_count: int
    received_count: int
    issued_count: int
    pending_count: int
    closed_count: int
    problem_count: int
    overdue_count: int
    received_totals: dict[str, Decimal]
    issued_totals: dict[str, Decimal]
    net_totals: dict[str, Decimal]


def _month_start(value: date) -> date:
    return date(value.year, value.month, 1)


def _month_end(value: date) -> date:
    last_day = calendar.monthrange(value.year, value.month)[1]
    return date(value.year, value.month, last_day)


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


def _display_currency_code(currency_code: str) -> str:
    normalized_currency_code = str(currency_code or "").strip().upper()

    if normalized_currency_code == "TRY":
        return "TL"

    return normalized_currency_code or "TL"


def _format_decimal_tr(value: Decimal) -> str:
    formatted = f"{Decimal(str(value)):,.2f}"
    return formatted.replace(",", "X").replace(".", ",").replace("X", ".")


def _format_currency_amount(amount: Decimal, currency_code: str) -> str:
    return f"{_format_decimal_tr(Decimal(str(amount)))} {_display_currency_code(currency_code)}"


def _format_currency_totals(currency_totals: dict[str, Decimal]) -> str:
    if not currency_totals:
        return "0,00 TL"

    parts: list[str] = []

    for currency_code in sorted(currency_totals):
        parts.append(_format_currency_amount(currency_totals[currency_code], currency_code))

    return " / ".join(parts)


def _format_short_amount(amount: Decimal) -> str:
    normalized_amount = Decimal(str(amount))
    rounded_amount = normalized_amount.quantize(Decimal("1"))

    formatted = f"{rounded_amount:,.0f}"
    return formatted.replace(",", "X").replace(".", ",").replace("X", ".")


def _single_currency_or_none(currency_totals: dict[str, Decimal]) -> tuple[str, Decimal] | None:
    if len(currency_totals) != 1:
        return None

    currency_code = next(iter(currency_totals))
    return currency_code, currency_totals[currency_code]


def _format_short_totals(currency_totals: dict[str, Decimal]) -> str:
    single_value = _single_currency_or_none(currency_totals)

    if single_value is None:
        if not currency_totals:
            return "0"
        return "Çoklu"

    currency_code, amount = single_value
    return f"{_format_short_amount(amount)} {_display_currency_code(currency_code)}"


def _add_to_totals(totals: dict[str, Decimal], currency_code: str, amount: Decimal) -> None:
    normalized_currency_code = str(currency_code or "TRY").strip().upper()
    totals[normalized_currency_code] = (
        totals.get(normalized_currency_code, Decimal("0.00")) + Decimal(str(amount))
    ).quantize(Decimal("0.01"))


def _subtract_from_totals(totals: dict[str, Decimal], currency_code: str, amount: Decimal) -> None:
    normalized_currency_code = str(currency_code or "TRY").strip().upper()
    totals[normalized_currency_code] = (
        totals.get(normalized_currency_code, Decimal("0.00")) - Decimal(str(amount))
    ).quantize(Decimal("0.01"))


def _received_status_text(value: Any) -> str:
    status = _enum_value(value)

    return RECEIVED_STATUS_TEXTS.get(status, status or "-")


def _issued_status_text(value: Any) -> str:
    status = _enum_value(value)

    return ISSUED_STATUS_TEXTS.get(status, status or "-")


def _check_status_group(check_type: str, status: str) -> str:
    normalized_status = str(status or "").strip().upper()

    if check_type == "RECEIVED":
        if normalized_status in RECEIVED_PENDING_STATUSES:
            return "PENDING"
        if normalized_status in RECEIVED_PROBLEM_STATUSES:
            return "PROBLEM"
        if normalized_status in RECEIVED_CLOSED_STATUSES:
            return "CLOSED"

    if check_type == "ISSUED":
        if normalized_status in ISSUED_PENDING_STATUSES:
            return "PENDING"
        if normalized_status in ISSUED_PROBLEM_STATUSES:
            return "PROBLEM"
        if normalized_status in ISSUED_CLOSED_STATUSES:
            return "CLOSED"

    return "ALL"


def _days_text(target_date: date, today: date) -> str:
    difference = (target_date - today).days

    if difference == 0:
        return "Bugün"
    if difference > 0:
        return f"{difference} gün"
    return f"{abs(difference)} gün geçti"


def _net_total_sum(net_totals: dict[str, Decimal]) -> Decimal:
    if len(net_totals) != 1:
        return Decimal("0.00")

    return next(iter(net_totals.values()))


class CalendarDayCard(QFrame):
    def __init__(
        self,
        *,
        day_info: CalendarDayInfo,
        day_summary: DaySummary,
        on_click: Callable[[date], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.day_info = day_info
        self.day_summary = day_summary
        self.on_click = on_click

        if day_info.is_selected:
            self.setObjectName("DueCalendarSelectedCard")
        elif day_info.is_today:
            self.setObjectName("DueCalendarTodayCard")
        else:
            self.setObjectName("DueCalendarDayCard")

        self.setMinimumHeight(62)
        self.setCursor(Qt.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 5, 8, 5)
        layout.setSpacing(1)

        number_row = QHBoxLayout()
        number_row.setSpacing(6)

        day_number = QLabel(str(day_info.day_date.day))
        day_number.setObjectName("CalendarDayNumber")

        number_row.addWidget(day_number)
        number_row.addStretch(1)

        if day_info.is_today:
            today_label = QLabel("BUGÜN")
            today_label.setObjectName("CalendarTodayBadge")
            number_row.addWidget(today_label)

        if day_summary.problem_count > 0 or day_summary.overdue_count > 0:
            warning_label = QLabel("RİSK")
            warning_label.setObjectName("CalendarRiskBadge")
            warning_label.setToolTip(
                f"Problemli: {day_summary.problem_count} | "
                f"Vadesi geçmiş bekleyen: {day_summary.overdue_count}"
            )
            number_row.addWidget(warning_label)

        layout.addLayout(number_row)

        if day_summary.item_count <= 0:
            empty_hint = QLabel(" ")
            empty_hint.setObjectName("CalendarTinyMuted")
            layout.addWidget(empty_hint)
            layout.addStretch(1)
            return

        incoming_text = QLabel(f"Giriş: {_format_short_totals(day_summary.received_totals)}")
        incoming_text.setObjectName("CalendarSmallText")
        incoming_text.setToolTip(
            f"Alınan çek toplamı: {_format_currency_totals(day_summary.received_totals)}"
        )

        outgoing_text = QLabel(f"Çıkış: {_format_short_totals(day_summary.issued_totals)}")
        outgoing_text.setObjectName("CalendarSmallText")
        outgoing_text.setToolTip(
            f"Yazılan çek toplamı: {_format_currency_totals(day_summary.issued_totals)}"
        )

        net_single_value = _single_currency_or_none(day_summary.net_totals)
        if net_single_value is None:
            net_label_text = "Net: Çoklu"
            net_object_name = "CalendarNetNeutral"
            net_tooltip = f"Net etki: {_format_currency_totals(day_summary.net_totals)}"
        else:
            currency_code, net_amount = net_single_value
            net_label_text = f"Net: {_format_short_amount(net_amount)} {_display_currency_code(currency_code)}"

            if net_amount > Decimal("0.00"):
                net_object_name = "CalendarNetPositive"
            elif net_amount < Decimal("0.00"):
                net_object_name = "CalendarNetNegative"
            else:
                net_object_name = "CalendarNetNeutral"

            net_tooltip = f"Net etki: {_format_currency_amount(net_amount, currency_code)}"

        net_text = QLabel(net_label_text)
        net_text.setObjectName(net_object_name)
        net_text.setToolTip(net_tooltip)

        layout.addSpacing(3)
        layout.addWidget(incoming_text)
        layout.addWidget(outgoing_text)
        layout.addWidget(net_text)
        layout.addStretch(1)

    def mousePressEvent(self, event: Any) -> None:
        self.on_click(self.day_info.day_date)
        super().mousePressEvent(event)


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
        self.calendar_board = self._build_calendar_board()
        self.detail_panel = self._build_selected_day_detail_panel()

        root_layout.addWidget(self.toolbar)
        root_layout.addWidget(self.summary_strip)
        root_layout.addWidget(self.calendar_board, 1)
        root_layout.addWidget(self.detail_panel)

        self._render_calendar()

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
        net_totals: dict[str, Decimal] = {}

        for item in items:
            status_group = _check_status_group(item.check_type, item.status)

            if item.check_type == "RECEIVED":
                received_count += 1
                _add_to_totals(received_totals, item.currency_code, item.amount)
                _add_to_totals(net_totals, item.currency_code, item.amount)

            if item.check_type == "ISSUED":
                issued_count += 1
                _add_to_totals(issued_totals, item.currency_code, item.amount)
                _subtract_from_totals(net_totals, item.currency_code, item.amount)

            if status_group == "PENDING":
                pending_count += 1

                if item.due_date < today:
                    overdue_count += 1

            if status_group == "CLOSED":
                closed_count += 1

            if status_group == "PROBLEM":
                problem_count += 1

        return DaySummary(
            item_count=len(items),
            received_count=received_count,
            issued_count=issued_count,
            pending_count=pending_count,
            closed_count=closed_count,
            problem_count=problem_count,
            overdue_count=overdue_count,
            received_totals=received_totals,
            issued_totals=issued_totals,
            net_totals=net_totals,
        )

    def _build_toolbar(self) -> QWidget:
        toolbar = QFrame()
        toolbar.setObjectName("DueCalendarToolbar")

        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(14, 9, 14, 9)
        layout.setSpacing(10)

        type_label = QLabel("Çek türü")
        type_label.setObjectName("CalendarInfoText")

        self.check_type_combo = QComboBox()
        self.check_type_combo.setMinimumHeight(34)
        self.check_type_combo.addItem("Tümü", "ALL")
        self.check_type_combo.addItem("Alınan", "RECEIVED")
        self.check_type_combo.addItem("Yazılan", "ISSUED")
        self.check_type_combo.currentIndexChanged.connect(self._filters_changed)

        status_label = QLabel("Durum")
        status_label.setObjectName("CalendarInfoText")

        self.status_combo = QComboBox()
        self.status_combo.setMinimumHeight(34)
        self.status_combo.addItem("Bekleyen", "PENDING")
        self.status_combo.addItem("Tümü", "ALL")
        self.status_combo.addItem("Sonuçlanan", "CLOSED")
        self.status_combo.addItem("Problemli / Riskli", "PROBLEM")
        self.status_combo.addItem("Vadesi Geçmiş", "OVERDUE")
        self.status_combo.currentIndexChanged.connect(self._filters_changed)

        self.previous_month_button = QPushButton("‹")
        self.previous_month_button.setObjectName("CalendarSecondaryButton")
        self.previous_month_button.setFixedWidth(46)
        self.previous_month_button.setMinimumHeight(34)
        self.previous_month_button.clicked.connect(self._go_previous_month)

        self.month_title_label = QLabel("")
        self.month_title_label.setObjectName("CalendarMonthTitle")
        self.month_title_label.setAlignment(Qt.AlignCenter)
        self.month_title_label.setMinimumWidth(160)

        self.next_month_button = QPushButton("›")
        self.next_month_button.setObjectName("CalendarSecondaryButton")
        self.next_month_button.setFixedWidth(46)
        self.next_month_button.setMinimumHeight(34)
        self.next_month_button.clicked.connect(self._go_next_month)

        self.today_button = QPushButton("Bugün")
        self.today_button.setObjectName("CalendarPrimaryButton")
        self.today_button.setMinimumHeight(34)
        self.today_button.clicked.connect(self._go_today)

        layout.addWidget(type_label)
        layout.addWidget(self.check_type_combo)
        layout.addWidget(status_label)
        layout.addWidget(self.status_combo)
        layout.addStretch(1)
        layout.addWidget(self.previous_month_button)
        layout.addWidget(self.month_title_label)
        layout.addWidget(self.next_month_button)
        layout.addWidget(self.today_button)

        return toolbar

    def _build_summary_strip(self) -> QWidget:
        strip = QFrame()
        strip.setObjectName("DueCalendarSummaryStrip")

        layout = QHBoxLayout(strip)
        layout.setContentsMargins(14, 8, 14, 8)
        layout.setSpacing(10)

        self.month_received_label = QLabel("Alınacak: -")
        self.month_received_label.setObjectName("CalendarSummaryBox")

        self.month_issued_label = QLabel("Ödenecek: -")
        self.month_issued_label.setObjectName("CalendarSummaryBox")

        self.month_net_label = QLabel("Net: -")
        self.month_net_label.setObjectName("CalendarSummaryBox")

        self.month_warning_label = QLabel("Risk: -")
        self.month_warning_label.setObjectName("CalendarSummaryWarning")

        layout.addWidget(self.month_received_label)
        layout.addWidget(self.month_issued_label)
        layout.addWidget(self.month_net_label)
        layout.addWidget(self.month_warning_label)
        layout.addStretch(1)

        return strip

    def _build_calendar_board(self) -> QWidget:
        board = QFrame()
        board.setObjectName("DueCalendarBoard")

        layout = QVBoxLayout(board)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        weekday_layout = QGridLayout()
        weekday_layout.setContentsMargins(0, 0, 0, 0)
        weekday_layout.setHorizontalSpacing(8)
        weekday_layout.setVerticalSpacing(0)

        for column_index, weekday_name in enumerate(WEEKDAY_NAMES_TR):
            label = QLabel(weekday_name)
            label.setObjectName("CalendarWeekday")
            label.setAlignment(Qt.AlignCenter)
            weekday_layout.addWidget(label, 0, column_index)

        self.calendar_grid = QGridLayout()
        self.calendar_grid.setContentsMargins(0, 0, 0, 0)
        self.calendar_grid.setHorizontalSpacing(6)
        self.calendar_grid.setVerticalSpacing(6)

        for column_index in range(7):
            self.calendar_grid.setColumnStretch(column_index, 1)

        layout.addLayout(weekday_layout)
        layout.addLayout(self.calendar_grid, 1)

        return board

    def _build_selected_day_detail_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("DueCalendarDetailCard")
        panel.setMinimumHeight(230)
        panel.setMaximumHeight(280)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(7)

        header_row = QHBoxLayout()
        header_row.setSpacing(8)

        self.selected_day_title_label = QLabel("Seçili Gün")
        self.selected_day_title_label.setObjectName("CalendarSectionTitle")

        self.selected_day_summary_label = QLabel("")
        self.selected_day_summary_label.setObjectName("CalendarInfoText")
        self.selected_day_summary_label.setWordWrap(False)
        self.selected_day_summary_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.selected_day_summary_label.setMaximumWidth(430)
        self.selected_day_summary_label.setMinimumHeight(20)
        self.selected_day_summary_label.setMaximumHeight(20)

        self.selected_day_report_button = QPushButton("Gün Raporu")
        self.selected_day_report_button.setObjectName("CalendarPrimaryButton")
        self.selected_day_report_button.setMinimumHeight(32)
        self.selected_day_report_button.clicked.connect(self._open_selected_day_report)

        header_row.addWidget(self.selected_day_title_label)
        header_row.addStretch(1)
        header_row.addWidget(self.selected_day_summary_label)
        header_row.addWidget(self.selected_day_report_button)

        self.selected_day_table = QTableWidget()
        self.selected_day_table.setColumnCount(8)
        self.selected_day_table.setHorizontalHeaderLabels(
            [
                "Tür",
                "Taraf",
                "Çek No",
                "Kalan",
                "Tutar",
                "Durum",
                "Referans",
                "Açıklama",
            ]
        )
        self.selected_day_table.verticalHeader().setVisible(False)
        self.selected_day_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.selected_day_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.selected_day_table.setWordWrap(False)
        self.selected_day_table.setTextElideMode(Qt.ElideRight)
        self.selected_day_table.verticalHeader().setDefaultSectionSize(32)
        self.selected_day_table.verticalHeader().setMinimumSectionSize(28)
        self.selected_day_table.setMinimumHeight(150)
        self.selected_day_table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.selected_day_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.selected_day_table.setVerticalScrollMode(QTableWidget.ScrollPerPixel)

        header = self.selected_day_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.Stretch)

        layout.addLayout(header_row)
        layout.addWidget(self.selected_day_table)

        return panel

    def _filters_changed(self) -> None:
        self._render_calendar()

    def _go_previous_month(self) -> None:
        self.current_month = _add_months(self.current_month, -1)
        self.selected_date = self.current_month
        self._render_calendar()

    def _go_next_month(self) -> None:
        self.current_month = _add_months(self.current_month, 1)
        self.selected_date = self.current_month
        self._render_calendar()

    def _go_today(self) -> None:
        self.today = date.today()
        self.current_month = _month_start(self.today)
        self.selected_date = self.today
        self._render_calendar()

    def _selected_check_type_filter(self) -> str:
        return str(self.check_type_combo.currentData() or "ALL").strip().upper()

    def _selected_status_filter(self) -> str:
        return str(self.status_combo.currentData() or "PENDING").strip().upper()

    def _render_calendar(self) -> None:
        self.month_title_label.setText(_format_month_title(self.current_month))
        self.due_items_by_date = self._load_due_items_for_month()
        self._update_month_summary()

        clear_layout(self.calendar_grid)

        calendar_weeks = calendar.Calendar(firstweekday=0).monthdatescalendar(
            self.current_month.year,
            self.current_month.month,
        )

        for row_index, week in enumerate(calendar_weeks):
            self.calendar_grid.setRowStretch(row_index, 1)

            for column_index, day_date in enumerate(week):
                if day_date.month != self.current_month.month:
                    empty_cell = QFrame()
                    empty_cell.setObjectName("DueCalendarEmptyCell")
                    empty_cell.setMinimumHeight(62)
                    self.calendar_grid.addWidget(empty_cell, row_index, column_index)
                    continue

                day_summary = self.build_summary_from_items(
                    items=self.due_items_by_date.get(day_date, []),
                    today=self.today,
                )

                day_card = CalendarDayCard(
                    day_info=CalendarDayInfo(
                        day_date=day_date,
                        is_today=day_date == self.today,
                        is_selected=day_date == self.selected_date,
                    ),
                    day_summary=day_summary,
                    on_click=self._select_day,
                )
                self.calendar_grid.addWidget(day_card, row_index, column_index)

        self._update_selected_day_details()

    def _select_day(self, selected_date: date) -> None:
        if selected_date.month != self.current_month.month:
            return

        self.selected_date = selected_date
        self._render_calendar()

    def _load_due_items_for_month(self) -> dict[date, list[DueCheckItem]]:
        start_date = _month_start(self.current_month)
        end_date = _month_end(self.current_month)
        check_type_filter = self._selected_check_type_filter()
        status_filter = self._selected_status_filter()

        items_by_date: dict[date, list[DueCheckItem]] = {}

        try:
            with session_scope() as session:
                if check_type_filter in {"ALL", "RECEIVED"}:
                    received_statement = (
                        select(ReceivedCheck, BusinessPartner)
                        .join(BusinessPartner, ReceivedCheck.customer_id == BusinessPartner.id)
                        .where(
                            ReceivedCheck.due_date >= start_date,
                            ReceivedCheck.due_date <= end_date,
                        )
                        .order_by(ReceivedCheck.due_date.asc(), ReceivedCheck.id.asc())
                    )

                    for received_check, customer in session.execute(received_statement).all():
                        status_value = _enum_value(received_check.status)

                        item = DueCheckItem(
                            check_type="RECEIVED",
                            check_id=received_check.id,
                            party_name=customer.name,
                            check_number=received_check.check_number,
                            due_date=received_check.due_date,
                            amount=Decimal(str(received_check.amount)),
                            currency_code=_enum_value(received_check.currency_code) or "TRY",
                            status=status_value,
                            status_text=_received_status_text(status_value),
                            reference_no=received_check.reference_no,
                            description=received_check.description,
                        )

                        if self._item_matches_status_filter(item, status_filter):
                            items_by_date.setdefault(item.due_date, []).append(item)

                if check_type_filter in {"ALL", "ISSUED"}:
                    issued_statement = (
                        select(IssuedCheck, BusinessPartner)
                        .join(BusinessPartner, IssuedCheck.supplier_id == BusinessPartner.id)
                        .where(
                            IssuedCheck.due_date >= start_date,
                            IssuedCheck.due_date <= end_date,
                        )
                        .order_by(IssuedCheck.due_date.asc(), IssuedCheck.id.asc())
                    )

                    for issued_check, supplier in session.execute(issued_statement).all():
                        status_value = _enum_value(issued_check.status)

                        item = DueCheckItem(
                            check_type="ISSUED",
                            check_id=issued_check.id,
                            party_name=supplier.name,
                            check_number=issued_check.check_number,
                            due_date=issued_check.due_date,
                            amount=Decimal(str(issued_check.amount)),
                            currency_code=_enum_value(issued_check.currency_code) or "TRY",
                            status=status_value,
                            status_text=_issued_status_text(status_value),
                            reference_no=issued_check.reference_no,
                            description=issued_check.description,
                        )

                        if self._item_matches_status_filter(item, status_filter):
                            items_by_date.setdefault(item.due_date, []).append(item)

        except Exception as exc:
            self._show_data_error_on_detail_panel(str(exc))
            return {}

        for day_items in items_by_date.values():
            day_items.sort(
                key=lambda item: (
                    item.due_date,
                    item.check_type,
                    item.party_name.lower(),
                    item.check_number.lower(),
                    item.check_id,
                )
            )

        return items_by_date

    def _item_matches_status_filter(self, item: DueCheckItem, status_filter: str) -> bool:
        normalized_status_filter = str(status_filter or "PENDING").strip().upper()
        status_group = _check_status_group(item.check_type, item.status)

        if normalized_status_filter == "ALL":
            return True

        if normalized_status_filter == "OVERDUE":
            return status_group == "PENDING" and item.due_date < self.today

        return status_group == normalized_status_filter

    def _update_month_summary(self) -> None:
        all_items: list[DueCheckItem] = []

        for day_items in self.due_items_by_date.values():
            all_items.extend(day_items)

        month_summary = self.build_summary_from_items(
            items=all_items,
            today=self.today,
        )

        self.month_received_label.setText(
            f"Alınacak: {_format_currency_totals(month_summary.received_totals)}"
        )
        self.month_issued_label.setText(
            f"Ödenecek: {_format_currency_totals(month_summary.issued_totals)}"
        )

        net_text = _format_currency_totals(month_summary.net_totals)
        self.month_net_label.setText(f"Net: {net_text}")

        net_single_value = _single_currency_or_none(month_summary.net_totals)

        if net_single_value is None:
            self.month_net_label.setObjectName("CalendarSummaryBox")
        else:
            _, net_amount = net_single_value

            if net_amount >= Decimal("0.00"):
                self.month_net_label.setObjectName("CalendarSummaryPositive")
            else:
                self.month_net_label.setObjectName("CalendarSummaryNegative")

        self.month_net_label.style().unpolish(self.month_net_label)
        self.month_net_label.style().polish(self.month_net_label)

        self.month_warning_label.setText(
            f"Risk: {month_summary.problem_count} | Vadesi geçmiş: {month_summary.overdue_count}"
        )

    def _update_selected_day_details(self) -> None:
        items = self.due_items_by_date.get(self.selected_date, [])
        selected_summary = self.build_summary_from_items(
            items=items,
            today=self.today,
        )

        self.selected_day_title_label.setText(
            f"Seçili Gün: {_format_date_tr(self.selected_date)}"
        )

        self.selected_day_summary_label.setText(
            f"G: {_format_short_totals(selected_summary.received_totals)} | "
            f"Ç: {_format_short_totals(selected_summary.issued_totals)} | "
            f"N: {_format_short_totals(selected_summary.net_totals)} | "
            f"Kt: {selected_summary.item_count}"
        )

        self._fill_selected_day_table(items)

    def _fill_selected_day_table(self, items: list[DueCheckItem]) -> None:
        self.selected_day_table.setRowCount(len(items))

        for row_index, item in enumerate(items):
            type_text = "Alınan" if item.check_type == "RECEIVED" else "Yazılan"
            amount_text = _format_currency_amount(item.amount, item.currency_code)
            days_text = _days_text(item.due_date, self.today)
            status_group = _check_status_group(item.check_type, item.status)

            values = [
                type_text,
                item.party_name,
                item.check_number,
                days_text,
                amount_text,
                item.status_text,
                item.reference_no or "-",
                item.description or "-",
            ]

            for column_index, value in enumerate(values):
                table_item = QTableWidgetItem(value)

                color = QColor("#e5e7eb")

                if item.check_type == "RECEIVED":
                    color = QColor("#a7f3d0")

                if item.check_type == "ISSUED":
                    color = QColor("#fecaca")

                if status_group == "PROBLEM":
                    color = QColor("#fbbf24")
                elif status_group == "CLOSED":
                    color = QColor("#94a3b8")
                elif status_group == "PENDING" and item.due_date < self.today:
                    color = QColor("#f87171")

                table_item.setForeground(color)

                if column_index == 4:
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
                            f"Durum: {item.status_text}",
                            f"Referans: {item.reference_no or '-'}",
                            f"Açıklama: {item.description or '-'}",
                        ]
                    )
                )

                self.selected_day_table.setItem(row_index, column_index, table_item)

        for row_index in range(self.selected_day_table.rowCount()):
            self.selected_day_table.setRowHeight(row_index, 32)

    def _open_selected_day_report(self) -> None:
        dialog = DueDayReportDialog(
            parent=self,
            report_date=self.selected_date,
            check_type_filter=self._selected_check_type_filter(),
            status_filter=self._selected_status_filter(),
        )
        dialog.exec()

    def _show_data_error_on_detail_panel(self, error_message: str) -> None:
        self.selected_day_title_label.setText("Vade verileri okunamadı")
        self.selected_day_summary_label.setText(error_message)
        self.selected_day_table.setRowCount(0)
