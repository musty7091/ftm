# FTM Genel Bakış sayfası - Finansal Radar
from datetime import date
from decimal import Decimal
from typing import Any, Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.ui.components.summary_card import SummaryCard
from app.ui.dashboard_data import DashboardData, DashboardDueItem
from app.ui.ui_helpers import decimal_or_zero, tr_money, tr_number


CURRENCY_DISPLAY_ORDER = ["TRY", "USD", "EUR", "GBP"]


class ClickableSummaryCard(SummaryCard):
    def __init__(
        self,
        title: str,
        value: str,
        hint: str,
        card_type: str,
        target_page: str,
        navigate_to_page: Callable[[str], None] | None,
    ) -> None:
        super().__init__(
            title=title,
            value=value,
            hint=hint,
            card_type=card_type,
        )

        self.target_page = target_page
        self.navigate_to_page = navigate_to_page

        self.setMinimumHeight(128)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(f"{target_page} ekranına gitmek için tıkla.")

    def mousePressEvent(self, event: Any) -> None:
        if self.navigate_to_page is not None and self.target_page:
            self.navigate_to_page(self.target_page)

        super().mousePressEvent(event)


def _format_decimal_tr(value: Any) -> str:
    amount = decimal_or_zero(value)

    formatted = f"{amount:,.2f}"
    formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")

    return formatted


def _format_currency_amount(value: Any, currency_code: str) -> str:
    normalized_currency_code = str(currency_code or "").strip().upper()

    if normalized_currency_code == "TRY":
        return tr_money(value)

    return f"{_format_decimal_tr(value)} {normalized_currency_code}"


def _currency_sort_key(currency_code: str) -> tuple[int, str]:
    normalized_currency_code = str(currency_code or "").strip().upper()

    if normalized_currency_code in CURRENCY_DISPLAY_ORDER:
        return (CURRENCY_DISPLAY_ORDER.index(normalized_currency_code), normalized_currency_code)

    return (999, normalized_currency_code)


def _format_currency_totals(currency_totals: dict[str, Decimal]) -> str:
    if not currency_totals:
        return "0,00 TL"

    lines: list[str] = []

    for currency_code in sorted(currency_totals.keys(), key=_currency_sort_key):
        lines.append(
            _format_currency_amount(currency_totals[currency_code], currency_code)
        )

    return "\n".join(lines)


def _format_currency_totals_inline(currency_totals: dict[str, Decimal]) -> str:
    if not currency_totals:
        return "0,00 TL"

    parts: list[str] = []

    for currency_code in sorted(currency_totals.keys(), key=_currency_sort_key):
        parts.append(
            _format_currency_amount(currency_totals[currency_code], currency_code)
        )

    return " / ".join(parts)


def _format_date_tr(value: date) -> str:
    return value.strftime("%d.%m.%Y")


def _days_text(target_date: date) -> str:
    today = date.today()
    difference = (target_date - today).days

    if difference == 0:
        return "Bugün"
    if difference > 0:
        return f"{difference} gün"
    return f"{abs(difference)} gün geçti"


def _check_type_text(value: str) -> str:
    if value == "RECEIVED":
        return "Alınan"

    if value == "ISSUED":
        return "Yazılan"

    return value or "-"


def _urgency_text(value: str) -> str:
    if value == "PROBLEM":
        return "Problem"
    if value == "OVERDUE":
        return "Vadesi Geçmiş"
    if value == "TODAY":
        return "Bugün"
    if value == "WEEK":
        return "7 Gün"

    return value or "-"


def _urgency_color(value: str) -> QColor:
    if value == "PROBLEM":
        return QColor("#fbbf24")
    if value == "OVERDUE":
        return QColor("#f87171")
    if value == "TODAY":
        return QColor("#bfdbfe")
    if value == "WEEK":
        return QColor("#a7f3d0")

    return QColor("#e5e7eb")


class DashboardPage(QWidget):
    def __init__(
        self,
        dashboard_data: DashboardData,
        navigate_to_page: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__()

        self.dashboard_data = dashboard_data
        self.navigate_to_page = navigate_to_page

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        layout.addLayout(self._build_due_radar_cards())
        layout.addLayout(self._build_money_radar_cards())
        layout.addWidget(self._build_action_items_card(), 1)

    def _build_dashboard_card(
        self,
        *,
        title: str,
        value: str,
        hint: str,
        card_type: str,
        target_page: str,
    ) -> ClickableSummaryCard:
        return ClickableSummaryCard(
            title=title,
            value=value,
            hint=hint,
            card_type=card_type,
            target_page=target_page,
            navigate_to_page=self.navigate_to_page,
        )

    def _calculate_bank_currency_totals(self) -> dict[str, Decimal]:
        currency_totals: dict[str, Decimal] = {}

        for account in self.dashboard_data.bank_accounts:
            currency_code = str(account["currency_code"] or "").strip().upper()

            if not currency_code:
                continue

            currency_totals[currency_code] = currency_totals.get(
                currency_code,
                Decimal("0.00"),
            ) + decimal_or_zero(account["current_balance"])

        return currency_totals

    def _build_pending_pos_text(self) -> str:
        lines = [f"{tr_number(self.dashboard_data.pending_pos_count)} kayıt"]

        if not self.dashboard_data.pending_pos_currency_totals:
            return "\n".join(lines)

        for currency_code in sorted(
            self.dashboard_data.pending_pos_currency_totals.keys(),
            key=_currency_sort_key,
        ):
            lines.append(
                f"{currency_code}: {_format_currency_amount(self.dashboard_data.pending_pos_currency_totals[currency_code], currency_code)}"
            )

        return "\n".join(lines)

    def _build_due_radar_cards(self) -> QGridLayout:
        grid = QGridLayout()
        grid.setSpacing(16)

        overdue_and_problem_count = (
            self.dashboard_data.overdue_pending_count
            + self.dashboard_data.problem_count
        )

        overdue_and_problem_hint_parts: list[str] = []

        if self.dashboard_data.overdue_pending_count > 0:
            overdue_and_problem_hint_parts.append(
                f"Vadesi geçmiş: {_format_currency_totals_inline(self.dashboard_data.overdue_pending_currency_totals)}"
            )

        if self.dashboard_data.problem_count > 0:
            overdue_and_problem_hint_parts.append(
                f"Problem: {_format_currency_totals_inline(self.dashboard_data.problem_currency_totals)}"
            )

        overdue_and_problem_hint = (
            " | ".join(overdue_and_problem_hint_parts)
            if overdue_and_problem_hint_parts
            else "Vadesi geçmiş veya problemli çek görünmüyor"
        )

        cards = [
            self._build_dashboard_card(
                title="BUGÜN VADELİ",
                value=f"{tr_number(self.dashboard_data.due_today_count)} çek",
                hint=_format_currency_totals_inline(self.dashboard_data.due_today_currency_totals),
                card_type="risk" if self.dashboard_data.due_today_count > 0 else "normal",
                target_page="Vade Takvimi",
            ),
            self._build_dashboard_card(
                title="7 GÜN İÇİNDE ALINACAK",
                value=f"{tr_number(self.dashboard_data.next_7_received_count)} çek",
                hint=_format_currency_totals_inline(self.dashboard_data.next_7_received_currency_totals),
                card_type="success",
                target_page="Vade Takvimi",
            ),
            self._build_dashboard_card(
                title="7 GÜN İÇİNDE ÖDENECEK",
                value=f"{tr_number(self.dashboard_data.next_7_issued_count)} çek",
                hint=_format_currency_totals_inline(self.dashboard_data.next_7_issued_currency_totals),
                card_type="risk" if self.dashboard_data.next_7_issued_count > 0 else "normal",
                target_page="Vade Takvimi",
            ),
            self._build_dashboard_card(
                title="RİSK / GECİKME",
                value=f"{tr_number(overdue_and_problem_count)} kayıt",
                hint=overdue_and_problem_hint,
                card_type="risk" if overdue_and_problem_count > 0 else "success",
                target_page="Vade Takvimi",
            ),
        ]

        for column, card in enumerate(cards):
            grid.addWidget(card, 0, column)

        return grid

    def _build_money_radar_cards(self) -> QGridLayout:
        grid = QGridLayout()
        grid.setSpacing(16)

        bank_currency_totals = self._calculate_bank_currency_totals()

        cards = [
            self._build_dashboard_card(
                title="BANKA BAKİYESİ",
                value=_format_currency_totals(bank_currency_totals),
                hint="Aktif banka hesaplarının para birimi bazlı güncel toplamı",
                card_type="highlight",
                target_page="Bankalar",
            ),
            self._build_dashboard_card(
                title="BEKLEYEN POS",
                value=self._build_pending_pos_text(),
                hint="Henüz gerçekleşmemiş POS yatışları",
                card_type="normal",
                target_page="POS Mutabakat",
            ),
            self._build_dashboard_card(
                title="BU AY ALINAN ÇEK",
                value=f"{tr_number(self.dashboard_data.month_received_count)} çek",
                hint=_format_currency_totals_inline(self.dashboard_data.month_received_currency_totals),
                card_type="success",
                target_page="Vade Takvimi",
            ),
            self._build_dashboard_card(
                title="BU AY YAZILAN ÇEK",
                value=f"{tr_number(self.dashboard_data.month_issued_count)} çek",
                hint=_format_currency_totals_inline(self.dashboard_data.month_issued_currency_totals),
                card_type="risk" if self.dashboard_data.month_issued_count > 0 else "normal",
                target_page="Vade Takvimi",
            ),
        ]

        for column, card in enumerate(cards):
            grid.addWidget(card, 0, column)

        return grid

    def _build_action_items_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("Card")
        card.setCursor(Qt.PointingHandCursor)
        card.setToolTip("Vade Takvimi ekranına gitmek için çift tıkla.")

        original_mouse_double_click_event = card.mouseDoubleClickEvent

        def open_due_calendar(event: Any) -> None:
            if self.navigate_to_page is not None:
                self.navigate_to_page("Vade Takvimi")

            original_mouse_double_click_event(event)

        card.mouseDoubleClickEvent = open_due_calendar

        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(14)

        title = QLabel("Aksiyon Gerektiren Çekler")
        title.setObjectName("SectionTitle")

        subtitle = QLabel(
            "Vadesi geçmiş, bugün vadeli, 7 gün içinde vadeli ve problemli/riskli çeklerin öncelikli listesi."
        )
        subtitle.setObjectName("MutedText")
        subtitle.setWordWrap(True)

        table = QTableWidget()
        table.setColumnCount(8)
        table.setHorizontalHeaderLabels(
            [
                "Öncelik",
                "Tür",
                "Taraf",
                "Çek No",
                "Vade",
                "Kalan",
                "Tutar",
                "Durum",
            ]
        )
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(False)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setWordWrap(False)
        table.setTextElideMode(Qt.ElideRight)
        table.setMinimumHeight(320)
        table.cellDoubleClicked.connect(lambda row, column: self._open_due_calendar_from_table())

        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeToContents)

        self._fill_action_items_table(table)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(table, 1)

        return card

    def _open_due_calendar_from_table(self) -> None:
        if self.navigate_to_page is not None:
            self.navigate_to_page("Vade Takvimi")

    def _fill_action_items_table(self, table: QTableWidget) -> None:
        action_items = self.dashboard_data.due_action_items

        if not action_items:
            table.setRowCount(1)

            item = QTableWidgetItem(
                "Aksiyon gerektiren çek bulunmuyor. Bugün radar temiz görünüyor."
            )
            item.setForeground(QColor("#a7f3d0"))
            item.setTextAlignment(Qt.AlignCenter)

            table.setItem(0, 0, item)
            table.setSpan(0, 0, 1, 8)
            table.resizeRowsToContents()
            return

        table.setRowCount(len(action_items))

        for row_index, action_item in enumerate(action_items):
            self._fill_action_item_row(
                table=table,
                row_index=row_index,
                action_item=action_item,
            )

        table.resizeRowsToContents()

    def _fill_action_item_row(
        self,
        *,
        table: QTableWidget,
        row_index: int,
        action_item: DashboardDueItem,
    ) -> None:
        type_text = _check_type_text(action_item.check_type)
        urgency_text = _urgency_text(action_item.urgency)
        amount_text = _format_currency_amount(
            action_item.amount,
            action_item.currency_code,
        )
        due_date_text = _format_date_tr(action_item.due_date)
        days_text = _days_text(action_item.due_date)

        values = [
            urgency_text,
            type_text,
            action_item.party_name,
            action_item.check_number,
            due_date_text,
            days_text,
            amount_text,
            action_item.status_text,
        ]

        foreground = _urgency_color(action_item.urgency)

        for column_index, value in enumerate(values):
            item = QTableWidgetItem(value)
            item.setForeground(foreground)

            if column_index == 6:
                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            else:
                item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)

            if column_index in {0, 6}:
                font = QFont()
                font.setBold(True)
                item.setFont(font)

            item.setToolTip(
                "\n".join(
                    [
                        f"Öncelik: {urgency_text}",
                        f"Tür: {type_text}",
                        f"Taraf: {action_item.party_name}",
                        f"Çek No: {action_item.check_number}",
                        f"Vade: {due_date_text}",
                        f"Kalan: {days_text}",
                        f"Tutar: {amount_text}",
                        f"Durum: {action_item.status_text}",
                        f"Referans: {action_item.reference_no or '-'}",
                        f"Açıklama: {action_item.description or '-'}",
                    ]
                )
            )

            table.setItem(row_index, column_index, item)