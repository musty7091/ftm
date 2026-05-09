from __future__ import annotations

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
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.db.session import session_scope
from app.services.credit_facility_service import (
    list_credit_cards,
    list_credit_limits,
)
from app.ui.pages.credit_facilities.credit_card_dialog import CreditCardDialog


CREDIT_FACILITIES_PAGE_STYLE = """
QFrame#CreditFacilitiesCard {
    background-color: #111827;
    border: 1px solid #24324a;
    border-radius: 18px;
}

QFrame#CreditFacilitiesSummaryCard {
    background-color: rgba(15, 23, 42, 0.72);
    border: 1px solid rgba(148, 163, 184, 0.24);
    border-radius: 14px;
}

QFrame#CreditFacilitiesInfoCard {
    background-color: rgba(30, 64, 175, 0.14);
    border: 1px solid rgba(59, 130, 246, 0.28);
    border-radius: 12px;
}

QLabel#CreditFacilitiesSectionTitle {
    color: #f8fafc;
    font-size: 14px;
    font-weight: 900;
}

QLabel#CreditFacilitiesMetric {
    color: #f8fafc;
    font-size: 22px;
    font-weight: 900;
}

QLabel#CreditFacilitiesMetricLabel {
    color: #94a3b8;
    font-size: 11px;
    font-weight: 700;
}

QLabel#CreditFacilitiesMuted {
    color: #94a3b8;
    font-size: 12px;
}

QLabel#CreditFacilitiesSummaryValue {
    color: #f8fafc;
    font-size: 16px;
    font-weight: 900;
}

QPushButton#CreditFacilitiesPrimaryButton {
    background-color: #2563eb;
    color: #ffffff;
    border: 1px solid #3b82f6;
    border-radius: 10px;
    padding: 8px 14px;
    font-weight: 900;
}

QPushButton#CreditFacilitiesPrimaryButton:hover {
    background-color: #1d4ed8;
}

QPushButton#CreditFacilitiesSecondaryButton {
    background-color: #172033;
    color: #cbd5e1;
    border: 1px solid #24324a;
    border-radius: 10px;
    padding: 8px 14px;
    font-weight: 900;
}

QPushButton#CreditFacilitiesSecondaryButton:hover {
    background-color: #1e293b;
    color: #ffffff;
}

QPushButton:disabled {
    background-color: rgba(30, 41, 59, 0.55);
    color: #64748b;
    border: 1px solid rgba(100, 116, 139, 0.32);
}

QTabWidget::pane {
    border: 1px solid #24324a;
    border-radius: 14px;
    background-color: #0f172a;
    top: -1px;
}

QTabBar::tab {
    background-color: #111827;
    color: #94a3b8;
    border: 1px solid #24324a;
    border-bottom: none;
    padding: 10px 14px;
    margin-right: 4px;
    border-top-left-radius: 10px;
    border-top-right-radius: 10px;
    font-weight: 800;
}

QTabBar::tab:selected {
    background-color: #1d4ed8;
    color: #ffffff;
    border: 1px solid #3b82f6;
    border-bottom: none;
}

QTableWidget#CreditFacilitiesTable {
    background-color: #0f172a;
    color: #e5e7eb;
    border: 1px solid #334155;
    border-radius: 12px;
    gridline-color: #334155;
    selection-background-color: #2563eb;
    selection-color: #ffffff;
    alternate-background-color: #111827;
}

QTableWidget#CreditFacilitiesTable::item {
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


class CreditFacilitiesPage(QWidget):
    def __init__(self, current_user: Any | None = None) -> None:
        super().__init__()

        self.current_user = current_user
        self.setStyleSheet(CREDIT_FACILITIES_PAGE_STYLE)

        self.credit_cards_table = self._build_table(
            [
                "Banka",
                "Kart Adı",
                "Tür",
                "Ağ",
                "Son 4",
                "Para",
                "Limit",
                "Kesim",
                "Ödeme",
                "Durum",
            ]
        )

        self.credit_limits_table = self._build_table(
            [
                "Banka Hesabı",
                "Limit Adı",
                "Tip",
                "Para",
                "Limit",
                "Kullanılan",
                "Kullanım",
                "Faiz",
                "Periyot",
                "Gün",
                "Durum",
            ]
        )

        self.card_count_value_label = self._summary_value_label("0")
        self.card_limit_value_label = self._summary_value_label("0,00")
        self.limit_count_value_label = self._summary_value_label("0")
        self.limit_total_value_label = self._summary_value_label("0,00")

        self.status_label = QLabel("Hazır")
        self.status_label.setObjectName("CreditFacilitiesMuted")
        self.status_label.setWordWrap(True)

        self._build_ui()
        self.refresh_data()

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 10, 12, 12)
        main_layout.setSpacing(10)

        root_card = QFrame()
        root_card.setObjectName("CreditFacilitiesCard")

        root_layout = QVBoxLayout(root_card)
        root_layout.setContentsMargins(16, 14, 16, 14)
        root_layout.setSpacing(12)

        summary_layout = QHBoxLayout()
        summary_layout.setSpacing(10)
        summary_layout.addWidget(
            self._build_summary_card(
                title="Kredi Kartları",
                first_label="Aktif kart",
                first_value_label=self.card_count_value_label,
                second_label="Toplam kart limiti",
                second_value_label=self.card_limit_value_label,
                hint="İlk bakışta kart adedi ve limit büyüklüğü.",
            )
        )
        summary_layout.addWidget(
            self._build_summary_card(
                title="Kredili / Limitli Hesaplar",
                first_label="Aktif tanım",
                first_value_label=self.limit_count_value_label,
                second_label="Toplam limit",
                second_value_label=self.limit_total_value_label,
                hint="KMH / limitli mevduat genel görünümü.",
            )
        )

        tabs = QTabWidget()
        tabs.addTab(self._build_credit_cards_tab(), "Kredi Kartları")
        tabs.addTab(self._build_credit_limits_tab(), "Kredili / Limitli Mevduat")
        tabs.addTab(self._build_future_loans_tab(), "Banka Kredileri / Taksitli Krediler")

        root_layout.addLayout(summary_layout)
        root_layout.addWidget(tabs, 1)
        root_layout.addWidget(self.status_label)

        main_layout.addWidget(root_card, 1)

    def _build_credit_cards_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        actions = QHBoxLayout()
        actions.setSpacing(8)

        self.add_credit_card_button = QPushButton("Kart Tanımla")
        self.add_credit_card_button.setObjectName("CreditFacilitiesPrimaryButton")
        self.add_credit_card_button.setEnabled(True)
        self.add_credit_card_button.setToolTip("Yeni kredi kartı tanımı oluştur.")
        self.add_credit_card_button.clicked.connect(self.open_credit_card_dialog)

        edit_button = QPushButton("Düzenle")
        edit_button.setObjectName("CreditFacilitiesSecondaryButton")
        edit_button.setEnabled(False)
        edit_button.setToolTip("Bir sonraki adımda kredi kartı düzenleme formu bağlanacak.")

        statement_button = QPushButton("Ekstre")
        statement_button.setObjectName("CreditFacilitiesSecondaryButton")
        statement_button.setEnabled(False)
        statement_button.setToolTip("Ekstre takibi bir sonraki fazda bağlanacak.")

        actions.addWidget(self.add_credit_card_button)
        actions.addWidget(edit_button)
        actions.addWidget(statement_button)
        actions.addStretch(1)

        hint_label = QLabel(
            "Bu alan şimdilik kart tanımlarını gösterecek. Kayıt formları kademeli olarak bağlanıyor."
        )
        hint_label.setObjectName("CreditFacilitiesMuted")
        hint_label.setWordWrap(True)

        layout.addLayout(actions)
        layout.addWidget(hint_label)
        layout.addWidget(self.credit_cards_table, 1)

        return tab

    def _build_credit_limits_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        actions = QHBoxLayout()
        actions.setSpacing(8)

        add_button = QPushButton("Limit Tanımla")
        add_button.setObjectName("CreditFacilitiesPrimaryButton")
        add_button.setEnabled(False)
        add_button.setToolTip("Bir sonraki adımda kredili/limitli mevduat formu bağlanacak.")

        edit_button = QPushButton("Düzenle")
        edit_button.setObjectName("CreditFacilitiesSecondaryButton")
        edit_button.setEnabled(False)
        edit_button.setToolTip("Bir sonraki adımda limit tanımı düzenleme formu bağlanacak.")

        actions.addWidget(add_button)
        actions.addWidget(edit_button)
        actions.addStretch(1)

        hint_label = QLabel(
            "Bu alan banka hesabına bağlı KMH / limitli mevduat / rotatif limit tanımlarını gösterecek."
        )
        hint_label.setObjectName("CreditFacilitiesMuted")
        hint_label.setWordWrap(True)

        layout.addLayout(actions)
        layout.addWidget(hint_label)
        layout.addWidget(self.credit_limits_table, 1)

        return tab

    def _build_future_loans_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        info = self._build_info_card(
            "Banka Kredileri / Taksitli Krediler bölümü sonraki fazda açılacak. "
            "Burada kredi tanımı, taksit planı, faiz ve kalan anapara takibi yer alacak."
        )

        layout.addWidget(info)
        layout.addStretch(1)

        return tab

    def _build_summary_card(
        self,
        *,
        title: str,
        first_label: str,
        first_value_label: QLabel,
        second_label: str,
        second_value_label: QLabel,
        hint: str,
    ) -> QWidget:
        card = QFrame()
        card.setObjectName("CreditFacilitiesSummaryCard")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        title_label = QLabel(title)
        title_label.setObjectName("CreditFacilitiesSectionTitle")

        metrics_layout = QGridLayout()
        metrics_layout.setHorizontalSpacing(18)
        metrics_layout.setVerticalSpacing(4)

        first_label_widget = QLabel(first_label)
        first_label_widget.setObjectName("CreditFacilitiesMetricLabel")

        second_label_widget = QLabel(second_label)
        second_label_widget.setObjectName("CreditFacilitiesMetricLabel")

        hint_label = QLabel(hint)
        hint_label.setObjectName("CreditFacilitiesMuted")
        hint_label.setWordWrap(True)

        metrics_layout.addWidget(first_label_widget, 0, 0)
        metrics_layout.addWidget(second_label_widget, 0, 1)
        metrics_layout.addWidget(first_value_label, 1, 0)
        metrics_layout.addWidget(second_value_label, 1, 1)

        layout.addWidget(title_label)
        layout.addLayout(metrics_layout)
        layout.addWidget(hint_label)

        return card

    def _build_info_card(self, text: str) -> QWidget:
        card = QFrame()
        card.setObjectName("CreditFacilitiesInfoCard")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)

        label = QLabel(text)
        label.setObjectName("CreditFacilitiesMuted")
        label.setWordWrap(True)

        layout.addWidget(label)

        return card

    def _build_table(self, headers: list[str]) -> QTableWidget:
        table = QTableWidget()
        table.setObjectName("CreditFacilitiesTable")
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.verticalHeader().setVisible(False)

        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setStretchLastSection(True)

        return table

    def _summary_value_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("CreditFacilitiesSummaryValue")
        return label

    def open_credit_card_dialog(self) -> None:
        try:
            dialog = CreditCardDialog(
                current_user=self.current_user,
                parent=self,
            )

            if dialog.exec() == QDialog.Accepted:
                self.refresh_data()

        except Exception as exc:
            QMessageBox.critical(
                self,
                "Kart Tanımla Açılamadı",
                f"Kredi kartı tanımlama formu açılırken hata oluştu:\n\n{exc}",
            )

    def refresh_data(self) -> None:
        try:
            with session_scope() as session:
                credit_cards = list_credit_cards(session, include_inactive=True)
                credit_limits = list_credit_limits(session, include_inactive=True)

                card_rows = []
                active_card_count = 0
                card_limit_total = Decimal("0.00")

                for credit_card in credit_cards:
                    if credit_card.is_active:
                        active_card_count += 1
                        card_limit_total += Decimal(credit_card.credit_limit or 0)

                    bank_name = "-"
                    if getattr(credit_card, "bank", None) is not None:
                        bank_name = credit_card.bank.name or "-"

                    card_rows.append(
                        [
                            bank_name,
                            credit_card.card_name,
                            credit_card.card_type.value,
                            credit_card.card_network.value,
                            credit_card.last_four_digits or "-",
                            credit_card.currency_code.value,
                            self._format_decimal(credit_card.credit_limit),
                            self._format_day(credit_card.statement_cut_day),
                            self._format_day(credit_card.payment_due_day),
                            "Aktif" if credit_card.is_active else "Pasif",
                        ]
                    )

                limit_rows = []
                active_limit_count = 0
                credit_limit_total = Decimal("0.00")

                for credit_limit in credit_limits:
                    if credit_limit.is_active:
                        active_limit_count += 1
                        credit_limit_total += Decimal(credit_limit.limit_amount or 0)

                    account_name = "-"
                    bank_account = getattr(credit_limit, "bank_account", None)
                    if bank_account is not None:
                        bank_name = "-"
                        if getattr(bank_account, "bank", None) is not None:
                            bank_name = bank_account.bank.name or "-"
                        account_name = f"{bank_name} / {bank_account.account_name}"

                    limit_rows.append(
                        [
                            account_name,
                            credit_limit.limit_name,
                            credit_limit.limit_type.value,
                            credit_limit.currency_code.value,
                            self._format_decimal(credit_limit.limit_amount),
                            self._format_decimal(credit_limit.manual_used_amount),
                            credit_limit.usage_mode.value,
                            self._format_decimal(credit_limit.interest_rate),
                            credit_limit.interest_period.value,
                            self._format_day(credit_limit.interest_day),
                            "Aktif" if credit_limit.is_active else "Pasif",
                        ]
                    )

            self._fill_table(
                table=self.credit_cards_table,
                rows=card_rows,
                empty_message="Henüz tanımlı kredi kartı yok.",
            )
            self._fill_table(
                table=self.credit_limits_table,
                rows=limit_rows,
                empty_message="Henüz tanımlı kredili / limitli mevduat hesabı yok.",
            )

            self.card_count_value_label.setText(str(active_card_count))
            self.card_limit_value_label.setText(self._format_decimal(card_limit_total))
            self.limit_count_value_label.setText(str(active_limit_count))
            self.limit_total_value_label.setText(self._format_decimal(credit_limit_total))

            self.status_label.setText("Kredili Hesaplar / Kartlar verileri yenilendi.")

        except Exception as exc:
            QMessageBox.warning(
                self,
                "Kredili Hesaplar / Kartlar",
                f"Veriler yüklenirken hata oluştu:\n\n{exc}",
            )
            self.status_label.setText(f"Veriler yüklenemedi: {exc}")

    def _fill_table(
        self,
        *,
        table: QTableWidget,
        rows: list[list[Any]],
        empty_message: str,
    ) -> None:
        table.clearSpans()

        if not rows:
            table.setRowCount(1)

            empty_item = QTableWidgetItem(empty_message)
            empty_item.setFlags(empty_item.flags() & ~Qt.ItemIsEditable)
            empty_item.setForeground(QColor("#94a3b8"))
            empty_item.setTextAlignment(Qt.AlignCenter)

            table.setItem(0, 0, empty_item)
            table.setSpan(0, 0, 1, table.columnCount())

            for column_index in range(1, table.columnCount()):
                hidden_item = QTableWidgetItem("")
                hidden_item.setFlags(hidden_item.flags() & ~Qt.ItemIsEditable)
                table.setItem(0, column_index, hidden_item)

            table.resizeRowsToContents()
            return

        table.setRowCount(len(rows))

        for row_index, row_values in enumerate(rows):
            for column_index, value in enumerate(row_values):
                item = QTableWidgetItem(str(value))
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)

                if str(value).strip().lower() == "aktif":
                    item.setForeground(QColor("#22c55e"))
                elif str(value).strip().lower() == "pasif":
                    item.setForeground(QColor("#f87171"))

                table.setItem(row_index, column_index, item)

        table.resizeRowsToContents()

    def _format_decimal(self, value: Any) -> str:
        try:
            decimal_value = Decimal(value or 0)
        except Exception:
            return "0,00"

        formatted = f"{decimal_value:,.2f}"
        return formatted.replace(",", "X").replace(".", ",").replace("X", ".")

    def _format_day(self, value: Any) -> str:
        if value is None:
            return "-"

        return str(value)


__all__ = [
    "CreditFacilitiesPage",
]
