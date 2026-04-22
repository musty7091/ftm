# FTM Genel Bakış sayfası
from decimal import Decimal
from typing import Any

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

from app.ui.components.info_card import InfoCard
from app.ui.components.summary_card import SummaryCard
from app.ui.dashboard_data import DashboardData
from app.ui.ui_helpers import decimal_or_zero, tr_money, tr_number


CURRENCY_DISPLAY_ORDER = ["TRY", "USD", "EUR", "GBP"]


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


class DashboardPage(QWidget):
    def __init__(self, dashboard_data: DashboardData) -> None:
        super().__init__()

        self.dashboard_data = dashboard_data

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        layout.addLayout(self._build_summary_cards())
        layout.addWidget(self._build_bank_table_card(), 1)
        layout.addLayout(self._build_bottom_cards())

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

    def _build_currency_totals_text(self) -> str:
        currency_totals = self._calculate_bank_currency_totals()

        if not currency_totals:
            return "Kayıt yok"

        lines: list[str] = []

        for currency_code in sorted(currency_totals.keys(), key=_currency_sort_key):
            lines.append(
                f"{currency_code}: {_format_currency_amount(currency_totals[currency_code], currency_code)}"
            )

        return "\n".join(lines)

    def _build_summary_cards(self) -> QGridLayout:
        grid = QGridLayout()
        grid.setSpacing(16)

        health_hint = (
            f"OK: {self.dashboard_data.health_ok_count} | "
            f"WARN: {self.dashboard_data.health_warn_count} | "
            f"FAIL: {self.dashboard_data.health_fail_count}"
        )

        bank_currency_totals_text = self._build_currency_totals_text()

        cards = [
            SummaryCard(
                "SİSTEM SAĞLIĞI",
                self.dashboard_data.health_status,
                health_hint,
                "success" if self.dashboard_data.health_status == "OK" else "risk",
            ),
            SummaryCard(
                "BANKA BAKİYELERİ",
                bank_currency_totals_text,
                "Aktif banka hesaplarının para birimi bazlı güncel toplamı",
                "highlight",
            ),
            SummaryCard(
                "BEKLEYEN POS",
                tr_number(self.dashboard_data.pending_pos_count),
                "Henüz gerçekleşmemiş POS yatış kaydı",
                "normal",
            ),
            SummaryCard(
                "YAZILAN ÇEK RİSKİ",
                tr_money(self.dashboard_data.pending_issued_check_amount),
                "Ödenmemiş yazılan çek toplamı",
                "risk",
            ),
            SummaryCard(
                "ALINACAK ÇEK",
                tr_money(self.dashboard_data.pending_received_check_amount),
                "Portföy / bankada / tahsilde bekleyen çekler",
                "success",
            ),
            SummaryCard(
                "YETKİSİZ DENEME",
                tr_number(self.dashboard_data.permission_denied_count),
                "Toplam PERMISSION_DENIED audit kaydı",
                "normal",
            ),
        ]

        positions = [
            (0, 0),
            (0, 1),
            (0, 2),
            (1, 0),
            (1, 1),
            (1, 2),
        ]

        for card, position in zip(cards, positions):
            row, column = position
            grid.addWidget(card, row, column)

        return grid

    def _build_bank_table_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("Card")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(14)

        title = QLabel("Banka Hesapları")
        title.setObjectName("SectionTitle")

        subtitle = QLabel(
            "Açılış bakiyesi, giriş, çıkış ve güncel bakiye özeti. "
            "Her hesap kendi para birimiyle gösterilir."
        )
        subtitle.setObjectName("MutedText")

        bank_table = QTableWidget()
        bank_table.setColumnCount(7)
        bank_table.setHorizontalHeaderLabels(
            [
                "Banka",
                "Hesap",
                "Para Birimi",
                "Açılış",
                "Giriş",
                "Çıkış",
                "Güncel",
            ]
        )
        bank_table.verticalHeader().setVisible(False)
        bank_table.setAlternatingRowColors(False)
        bank_table.setSelectionBehavior(QTableWidget.SelectRows)
        bank_table.setEditTriggers(QTableWidget.NoEditTriggers)
        bank_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        self._fill_bank_table(bank_table)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(bank_table, 1)

        return card

    def _fill_bank_table(self, bank_table: QTableWidget) -> None:
        bank_table.setRowCount(len(self.dashboard_data.bank_accounts))

        for row_index, account in enumerate(self.dashboard_data.bank_accounts):
            currency_code = str(account["currency_code"] or "").strip().upper()

            values = [
                account["bank_name"],
                account["account_name"],
                currency_code,
                _format_currency_amount(account["opening_balance"], currency_code),
                _format_currency_amount(account["incoming_total"], currency_code),
                _format_currency_amount(account["outgoing_total"], currency_code),
                _format_currency_amount(account["current_balance"], currency_code),
            ]

            for column_index, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setForeground(QColor("#e5e7eb"))

                if column_index in {3, 4, 5, 6}:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                else:
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)

                if column_index == 6:
                    font = QFont()
                    font.setBold(True)
                    item.setFont(font)

                bank_table.setItem(row_index, column_index, item)

        bank_table.resizeRowsToContents()

    def _build_bottom_cards(self) -> QGridLayout:
        grid = QGridLayout()
        grid.setSpacing(16)

        security_card = InfoCard(
            "Güvenlik",
            "Yetkisiz işlem denemeleri audit log’a düşüyor. Güvenlik özeti mail sistemi aktif.",
            "Kilit kapıda, kamera kayıtta.",
        )

        backup_card = InfoCard(
            "Yedekleme",
            "Günlük PostgreSQL yedeği, mail eki ve haftalık restore testi hazır.",
            "Yedek var, restore var; panik yok.",
        )

        report_card = InfoCard(
            "Raporlar",
            "Excel finans raporu, POS mutabakatı, risk ve sağlık raporları bu omurgaya bağlanacak.",
            "Rakamlar artık sahneye çıkacak.",
        )

        grid.addWidget(security_card, 0, 0)
        grid.addWidget(backup_card, 0, 1)
        grid.addWidget(report_card, 0, 2)

        return grid