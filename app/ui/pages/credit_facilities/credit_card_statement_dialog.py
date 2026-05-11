from __future__ import annotations

import calendar
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
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.db.session import session_scope
from app.models.credit_facility import CreditCard, CreditCardPayment, CreditCardTransaction
from app.models.enums import CreditCardPaymentStatus, CreditCardTransactionStatus
from app.utils.decimal_utils import money


CREDIT_CARD_STATEMENT_DIALOG_STYLE = """
QDialog {
    background-color: #0f172a;
    color: #e5e7eb;
}

QFrame#StatementCard {
    background-color: #111827;
    border: 1px solid #24324a;
    border-radius: 16px;
}

QFrame#StatementSummaryCard {
    background-color: rgba(15, 23, 42, 0.74);
    border: 1px solid rgba(148, 163, 184, 0.24);
    border-radius: 12px;
}

QLabel#DialogTitle {
    color: #ffffff;
    font-size: 20px;
    font-weight: 900;
}

QLabel#DialogSubtitle,
QLabel#MutedText {
    color: #94a3b8;
    font-size: 12px;
}

QLabel#SectionTitle {
    color: #f8fafc;
    font-size: 14px;
    font-weight: 900;
}

QLabel#MetricLabel {
    color: #94a3b8;
    font-size: 11px;
    font-weight: 800;
}

QLabel#MetricValue {
    color: #f8fafc;
    font-size: 15px;
    font-weight: 900;
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

QTableWidget#StatementTable {
    background-color: #0f172a;
    color: #e5e7eb;
    border: 1px solid #334155;
    border-radius: 12px;
    gridline-color: #334155;
    selection-background-color: #2563eb;
    selection-color: #ffffff;
    alternate-background-color: #111827;
}

QTableWidget#StatementTable::item {
    padding: 6px;
    border: none;
}

QHeaderView::section {
    background-color: #1f2937;
    color: #f8fafc;
    border: 1px solid #334155;
    padding: 8px;
    font-weight: 900;
}

QTableCornerButton::section {
    background-color: #1f2937;
    border: 1px solid #334155;
}
"""


ACTIVE_TRANSACTION_STATUSES = {
    CreditCardTransactionStatus.PENDING,
    CreditCardTransactionStatus.IN_STATEMENT,
}

ACTIVE_PAYMENT_STATUSES = {
    CreditCardPaymentStatus.RECORDED,
}


@dataclass(frozen=True)
class StatementMovementRow:
    movement_date: date
    movement_type: str
    description: str
    purchase_amount: Decimal
    payment_amount: Decimal
    status_text: str
    reference_no: str
    is_cancelled: bool
    sort_order: int
    row_id: int


class CreditCardStatementDialog(QDialog):
    def __init__(
        self,
        *,
        credit_card_id: int,
        current_user: Any | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.credit_card_id = int(credit_card_id)
        self.current_user = current_user

        self.setWindowTitle("Kredi Kartı Ekstresi / Dönem Hareketleri")
        self.resize(980, 680)
        self.setMinimumSize(860, 560)
        self.setSizeGripEnabled(True)
        self.setStyleSheet(CREDIT_CARD_STATEMENT_DIALOG_STYLE)

        self.card_name_value_label = self._metric_value_label("-")
        self.period_value_label = self._metric_value_label("-")
        self.cut_day_value_label = self._metric_value_label("-")
        self.payment_day_value_label = self._metric_value_label("-")
        self.purchase_total_value_label = self._metric_value_label("0,00 TL")
        self.payment_total_value_label = self._metric_value_label("0,00 TL")
        self.net_total_value_label = self._metric_value_label("0,00 TL")
        self.row_count_value_label = self._metric_value_label("0")

        self.movements_table = QTableWidget()
        self.movements_table.setObjectName("StatementTable")
        self.movements_table.setColumnCount(7)
        self.movements_table.setHorizontalHeaderLabels(
            [
                "Tarih",
                "Tür",
                "Açıklama",
                "Harcama (TL)",
                "Ödeme (TL)",
                "Durum",
                "Referans",
            ]
        )
        self.movements_table.setAlternatingRowColors(True)
        self.movements_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.movements_table.setSelectionMode(QTableWidget.SingleSelection)
        self.movements_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.movements_table.verticalHeader().setVisible(False)

        table_header = self.movements_table.horizontalHeader()
        table_header.setSectionResizeMode(QHeaderView.ResizeToContents)
        table_header.setStretchLastSection(True)

        self.close_button = QPushButton("Kapat")
        self.close_button.setObjectName("SecondaryButton")
        self.close_button.clicked.connect(self.accept)

        self._build_ui()
        self._load_statement_data()

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(22, 20, 22, 18)
        root_layout.setSpacing(12)

        title_label = QLabel("Kredi Kartı Ekstresi / Dönem Hareketleri")
        title_label.setObjectName("DialogTitle")

        subtitle_label = QLabel(
            "Seçili kredi kartının mevcut dönem içindeki harcama ve ödeme hareketlerini gösterir. "
            "Bu ekran sadece görüntüleme amaçlıdır; veri değiştirmez."
        )
        subtitle_label.setObjectName("DialogSubtitle")
        subtitle_label.setWordWrap(True)

        info_card = QFrame()
        info_card.setObjectName("StatementCard")
        info_layout = QVBoxLayout(info_card)
        info_layout.setContentsMargins(14, 12, 14, 12)
        info_layout.setSpacing(10)

        info_title = QLabel("Kart ve Dönem Bilgisi")
        info_title.setObjectName("SectionTitle")

        info_grid = QGridLayout()
        info_grid.setHorizontalSpacing(20)
        info_grid.setVerticalSpacing(5)
        info_grid.addWidget(self._metric_label("Kart"), 0, 0)
        info_grid.addWidget(self._metric_label("Dönem"), 0, 1)
        info_grid.addWidget(self._metric_label("Hesap Kesim"), 0, 2)
        info_grid.addWidget(self._metric_label("Son Ödeme"), 0, 3)
        info_grid.addWidget(self.card_name_value_label, 1, 0)
        info_grid.addWidget(self.period_value_label, 1, 1)
        info_grid.addWidget(self.cut_day_value_label, 1, 2)
        info_grid.addWidget(self.payment_day_value_label, 1, 3)

        info_layout.addWidget(info_title)
        info_layout.addLayout(info_grid)

        summary_layout = QHBoxLayout()
        summary_layout.setSpacing(10)
        summary_layout.addWidget(
            self._build_summary_card(
                title="Dönem Harcaması",
                value_label=self.purchase_total_value_label,
                hint="İptal edilmemiş harcamaların toplamı.",
            )
        )
        summary_layout.addWidget(
            self._build_summary_card(
                title="Dönem Ödemesi",
                value_label=self.payment_total_value_label,
                hint="İptal edilmemiş ödemelerin toplamı.",
            )
        )
        summary_layout.addWidget(
            self._build_summary_card(
                title="Dönem Neti",
                value_label=self.net_total_value_label,
                hint="Harcama eksi ödeme.",
            )
        )
        summary_layout.addWidget(
            self._build_summary_card(
                title="Hareket Sayısı",
                value_label=self.row_count_value_label,
                hint="Dönem içinde görünen satır adedi.",
            )
        )

        movement_card = QFrame()
        movement_card.setObjectName("StatementCard")
        movement_layout = QVBoxLayout(movement_card)
        movement_layout.setContentsMargins(14, 12, 14, 12)
        movement_layout.setSpacing(10)

        movement_title = QLabel("Dönem Hareketleri")
        movement_title.setObjectName("SectionTitle")

        help_label = QLabel(
            "Harcama ve ödeme hareketleri aynı tabloda gösterilir. İptal edilmiş hareketler bilgi amaçlı görünür; "
            "dönem toplamlarına dahil edilmez."
        )
        help_label.setObjectName("MutedText")
        help_label.setWordWrap(True)

        movement_layout.addWidget(movement_title)
        movement_layout.addWidget(help_label)
        movement_layout.addWidget(self.movements_table, 1)

        button_layout = QHBoxLayout()
        button_layout.addStretch(1)
        button_layout.addWidget(self.close_button)

        root_layout.addWidget(title_label)
        root_layout.addWidget(subtitle_label)
        root_layout.addWidget(info_card)
        root_layout.addLayout(summary_layout)
        root_layout.addWidget(movement_card, 1)
        root_layout.addLayout(button_layout)

    def _build_summary_card(self, *, title: str, value_label: QLabel, hint: str) -> QWidget:
        card = QFrame()
        card.setObjectName("StatementSummaryCard")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        title_label = QLabel(title)
        title_label.setObjectName("MetricLabel")

        hint_label = QLabel(hint)
        hint_label.setObjectName("MutedText")
        hint_label.setWordWrap(True)

        layout.addWidget(title_label)
        layout.addWidget(value_label)
        layout.addWidget(hint_label)

        return card

    def _metric_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("MetricLabel")
        return label

    def _metric_value_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("MetricValue")
        label.setWordWrap(True)
        return label

    def _load_statement_data(self) -> None:
        try:
            with session_scope() as session:
                credit_card = session.get(CreditCard, self.credit_card_id)

                if credit_card is None:
                    raise ValueError(f"Kredi kartı bulunamadı. ID: {self.credit_card_id}")

                period_start, period_end, period_label = self._current_period_range(
                    today=date.today(),
                    statement_cut_day=credit_card.statement_cut_day,
                )

                bank_name = "-"
                if getattr(credit_card, "bank", None) is not None:
                    bank_name = credit_card.bank.name or "-"

                card_display_name = self._card_display_name(
                    bank_name=bank_name,
                    card_name=credit_card.card_name,
                    last_four_digits=credit_card.last_four_digits,
                )

                transactions = list(
                    session.execute(
                        select(CreditCardTransaction)
                        .where(
                            CreditCardTransaction.credit_card_id == credit_card.id,
                            CreditCardTransaction.transaction_date >= period_start,
                            CreditCardTransaction.transaction_date <= period_end,
                        )
                        .order_by(
                            CreditCardTransaction.transaction_date.asc(),
                            CreditCardTransaction.id.asc(),
                        )
                    )
                    .scalars()
                    .all()
                )

                payments = list(
                    session.execute(
                        select(CreditCardPayment)
                        .options(
                            joinedload(CreditCardPayment.payment_bank_account),
                        )
                        .where(
                            CreditCardPayment.credit_card_id == credit_card.id,
                            CreditCardPayment.payment_date >= period_start,
                            CreditCardPayment.payment_date <= period_end,
                        )
                        .order_by(
                            CreditCardPayment.payment_date.asc(),
                            CreditCardPayment.id.asc(),
                        )
                    )
                    .scalars()
                    .all()
                )

                rows: list[StatementMovementRow] = []
                purchase_total = Decimal("0.00")
                payment_total = Decimal("0.00")

                for transaction in transactions:
                    amount = money(transaction.amount or Decimal("0.00"), field_name="Harcama tutarı")
                    is_cancelled = transaction.status in {
                        CreditCardTransactionStatus.CANCELLED,
                        CreditCardTransactionStatus.REFUNDED,
                    }

                    if transaction.status in ACTIVE_TRANSACTION_STATUSES:
                        purchase_total += amount

                    description_parts = [str(transaction.merchant_name or "-")]
                    if transaction.description:
                        description_parts.append(str(transaction.description))

                    rows.append(
                        StatementMovementRow(
                            movement_date=transaction.transaction_date,
                            movement_type="Harcama",
                            description=" / ".join(description_parts),
                            purchase_amount=amount,
                            payment_amount=Decimal("0.00"),
                            status_text=self._transaction_status_text(transaction.status),
                            reference_no=transaction.reference_no or "-",
                            is_cancelled=is_cancelled,
                            sort_order=1,
                            row_id=int(transaction.id),
                        )
                    )

                for payment in payments:
                    amount = money(payment.amount or Decimal("0.00"), field_name="Ödeme tutarı")
                    is_cancelled = payment.status == CreditCardPaymentStatus.CANCELLED

                    if payment.status in ACTIVE_PAYMENT_STATUSES:
                        payment_total += amount

                    payment_account_label = self._payment_account_label(payment)

                    rows.append(
                        StatementMovementRow(
                            movement_date=payment.payment_date,
                            movement_type="Ödeme",
                            description=payment_account_label,
                            purchase_amount=Decimal("0.00"),
                            payment_amount=amount,
                            status_text=self._payment_status_text(payment.status),
                            reference_no=payment.reference_no or "-",
                            is_cancelled=is_cancelled,
                            sort_order=2,
                            row_id=int(payment.id),
                        )
                    )

                rows.sort(key=lambda item: (item.movement_date, item.sort_order, item.row_id))

                self.card_name_value_label.setText(card_display_name)
                self.period_value_label.setText(period_label)
                self.cut_day_value_label.setText(self._format_day(credit_card.statement_cut_day))
                self.payment_day_value_label.setText(self._format_day(credit_card.payment_due_day))
                self.purchase_total_value_label.setText(self._format_tl(purchase_total))
                self.payment_total_value_label.setText(self._format_tl(payment_total))
                self.net_total_value_label.setText(self._format_tl(purchase_total - payment_total))
                self.row_count_value_label.setText(str(len(rows)))
                self._fill_movements_table(rows)

        except Exception as exc:
            QMessageBox.critical(
                self,
                "Ekstre Bilgisi Yüklenemedi",
                f"Kredi kartı dönem hareketleri yüklenirken hata oluştu:\n\n{exc}",
            )
            self.reject()

    def _fill_movements_table(self, rows: list[StatementMovementRow]) -> None:
        self.movements_table.clearSpans()
        self.movements_table.clearSelection()

        if not rows:
            self.movements_table.setRowCount(1)
            empty_item = QTableWidgetItem("Bu dönem için harcama veya ödeme hareketi bulunmuyor.")
            empty_item.setFlags(empty_item.flags() & ~Qt.ItemIsEditable)
            empty_item.setForeground(QColor("#94a3b8"))
            empty_item.setTextAlignment(Qt.AlignCenter)
            self.movements_table.setItem(0, 0, empty_item)
            self.movements_table.setSpan(0, 0, 1, self.movements_table.columnCount())

            for column_index in range(1, self.movements_table.columnCount()):
                hidden_item = QTableWidgetItem("")
                hidden_item.setFlags(hidden_item.flags() & ~Qt.ItemIsEditable)
                self.movements_table.setItem(0, column_index, hidden_item)

            self.movements_table.resizeRowsToContents()
            return

        self.movements_table.setRowCount(len(rows))

        for row_index, row in enumerate(rows):
            values = [
                self._format_date(row.movement_date),
                row.movement_type,
                row.description,
                self._format_tl(row.purchase_amount) if row.purchase_amount > Decimal("0.00") else "-",
                self._format_tl(row.payment_amount) if row.payment_amount > Decimal("0.00") else "-",
                row.status_text,
                row.reference_no,
            ]

            for column_index, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)

                if column_index in {3, 4}:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                else:
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)

                if row.movement_type == "Ödeme" and not row.is_cancelled:
                    item.setForeground(QColor("#22c55e"))
                elif row.is_cancelled:
                    item.setForeground(QColor("#94a3b8"))
                elif row.movement_type == "Harcama":
                    item.setForeground(QColor("#e5e7eb"))

                self.movements_table.setItem(row_index, column_index, item)

        self.movements_table.resizeRowsToContents()
        self.movements_table.resizeColumnsToContents()

    def _payment_account_label(self, payment: CreditCardPayment) -> str:
        account = getattr(payment, "payment_bank_account", None)

        if account is None:
            return "Ödeme hesabı belirtilmemiş"

        bank_name = "-"
        if getattr(account, "bank", None) is not None:
            bank_name = account.bank.name or "-"

        account_name = account.account_name or "-"
        return f"{bank_name} / {account_name}"

    def _card_display_name(
        self,
        *,
        bank_name: str,
        card_name: str,
        last_four_digits: str | None,
    ) -> str:
        suffix = f" (*{last_four_digits})" if last_four_digits else ""
        return f"{bank_name} / {card_name}{suffix}"

    def _current_period_range(
        self,
        *,
        today: date,
        statement_cut_day: int | None,
    ) -> tuple[date, date, str]:
        if statement_cut_day is None:
            period_start = today - timedelta(days=29)
            period_end = today
            return (
                period_start,
                period_end,
                f"{self._format_date(period_start)} - {self._format_date(period_end)} (Son 30 gün)",
            )

        cut_day = int(statement_cut_day)
        current_month_cut = self._safe_month_day(today.year, today.month, cut_day)

        if today <= current_month_cut:
            previous_year, previous_month = self._subtract_month(today.year, today.month)
            previous_cut = self._safe_month_day(previous_year, previous_month, cut_day)
            period_start = previous_cut + timedelta(days=1)
            period_end = current_month_cut
        else:
            next_year, next_month = self._add_month(today.year, today.month)
            period_start = current_month_cut + timedelta(days=1)
            period_end = self._safe_month_day(next_year, next_month, cut_day)

        return (
            period_start,
            period_end,
            f"{self._format_date(period_start)} - {self._format_date(period_end)}",
        )

    def _safe_month_day(self, year: int, month: int, day: int) -> date:
        last_day = calendar.monthrange(year, month)[1]
        safe_day = min(max(int(day), 1), last_day)
        return date(year, month, safe_day)

    def _add_month(self, year: int, month: int) -> tuple[int, int]:
        if month == 12:
            return year + 1, 1

        return year, month + 1

    def _subtract_month(self, year: int, month: int) -> tuple[int, int]:
        if month == 1:
            return year - 1, 12

        return year, month - 1

    def _transaction_status_text(self, status: CreditCardTransactionStatus | str) -> str:
        status_value = status.value if isinstance(status, CreditCardTransactionStatus) else str(status)

        if status_value == CreditCardTransactionStatus.PENDING.value:
            return "Borçta"
        if status_value == CreditCardTransactionStatus.IN_STATEMENT.value:
            return "Ekstrede"
        if status_value == CreditCardTransactionStatus.CANCELLED.value:
            return "İptal"
        if status_value == CreditCardTransactionStatus.REFUNDED.value:
            return "İade"

        return status_value

    def _payment_status_text(self, status: CreditCardPaymentStatus | str) -> str:
        status_value = status.value if isinstance(status, CreditCardPaymentStatus) else str(status)

        if status_value == CreditCardPaymentStatus.RECORDED.value:
            return "Kayıtlı"
        if status_value == CreditCardPaymentStatus.CANCELLED.value:
            return "İptal"

        return status_value

    def _format_day(self, value: int | None) -> str:
        if value is None:
            return "Yok"

        try:
            clean_value = int(value)
        except (TypeError, ValueError):
            return "Yok"

        if clean_value <= 0:
            return "Yok"

        return str(clean_value)

    def _format_date(self, value: date | None) -> str:
        if value is None:
            return "-"

        return value.strftime("%d.%m.%Y")

    def _format_tl(self, value: Decimal | int | float | str | None) -> str:
        decimal_value = money(value or Decimal("0.00"), field_name="Tutar")
        text = f"{decimal_value:,.2f}"
        text = text.replace(",", "TEMP").replace(".", ",").replace("TEMP", ".")
        return f"{text} TL"


__all__ = [
    "CreditCardStatementDialog",
]
