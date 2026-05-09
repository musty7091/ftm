from __future__ import annotations

from decimal import Decimal
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
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


CREDIT_FACILITIES_PAGE_STYLE = """
QFrame#CreditFacilitiesCard {
    background-color: #111827;
    border: 1px solid #24324a;
    border-radius: 18px;
}

QFrame#CreditFacilitiesSummaryCard {
    background-color: rgba(15, 23, 42, 0.70);
    border: 1px solid rgba(148, 163, 184, 0.24);
    border-radius: 14px;
}

QFrame#CreditFacilitiesInfoCard {
    background-color: rgba(30, 64, 175, 0.18);
    border: 1px solid rgba(59, 130, 246, 0.34);
    border-radius: 14px;
}

QLabel#CreditFacilitiesTitle {
    color: #f8fafc;
    font-size: 18px;
    font-weight: 900;
}

QLabel#CreditFacilitiesSubtitle {
    color: #94a3b8;
    font-size: 12px;
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

QPushButton#CreditFacilitiesPrimaryButton {
    background-color: #2563eb;
    color: #ffffff;
    border: 1px solid #3b82f6;
    border-radius: 11px;
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
    border-radius: 11px;
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
                "Kesim Günü",
                "Son Ödeme",
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
                "Kullanım Şekli",
                "Faiz",
                "Periyot",
                "Gün",
                "Durum",
            ]
        )

        self.card_count_label = self._metric_value_label("0")
        self.card_limit_label = self._metric_value_label("0,00")
        self.limit_count_label = self._metric_value_label("0")
        self.limit_total_label = self._metric_value_label("0,00")

        self.status_label = QLabel("Hazır")
        self.status_label.setObjectName("CreditFacilitiesMuted")
        self.status_label.setWordWrap(True)

        self._build_ui()
        self.refresh_data()

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 14, 12, 12)
        main_layout.setSpacing(12)

        root_card = QFrame()
        root_card.setObjectName("CreditFacilitiesCard")

        root_layout = QVBoxLayout(root_card)
        root_layout.setContentsMargins(18, 16, 18, 16)
        root_layout.setSpacing(14)

        header_layout = QHBoxLayout()
        header_layout.setSpacing(10)

        title_box = QVBoxLayout()
        title_box.setSpacing(3)

        title = QLabel("Kredili Hesaplar / Kartlar")
        title.setObjectName("CreditFacilitiesTitle")

        subtitle = QLabel(
            "Kredi kartları, kredili/limitli mevduat hesapları ve ileride banka kredileri bu modülde izlenecek."
        )
        subtitle.setObjectName("CreditFacilitiesSubtitle")
        subtitle.setWordWrap(True)

        title_box.addWidget(title)
        title_box.addWidget(subtitle)

        refresh_button = QPushButton("Yenile")
        refresh_button.setObjectName("CreditFacilitiesSecondaryButton")
        refresh_button.clicked.connect(self.refresh_data)

        header_layout.addLayout(title_box, 1)
        header_layout.addWidget(refresh_button, 0, Qt.AlignTop)

        summary_layout = QHBoxLayout()
        summary_layout.setSpacing(10)

        summary_layout.addWidget(
            self._build_summary_card(
                title="Aktif Kredi Kartı",
                value_label=self.card_count_label,
                hint="Tanımlı aktif kart sayısı",
            )
        )
        summary_layout.addWidget(
            self._build_summary_card(
                title="Toplam Kart Limiti",
                value_label=self.card_limit_label,
                hint="Para birimleri ayrıştırılmadan genel görünüm",
            )
        )
        summary_layout.addWidget(
            self._build_summary_card(
                title="Aktif Kredili Hesap",
                value_label=self.limit_count_label,
                hint="KMH / limitli mevduat tanımı",
            )
        )
        summary_layout.addWidget(
            self._build_summary_card(
                title="Toplam Limit",
                value_label=self.limit_total_label,
                hint="Para birimleri ayrıştırılmadan genel görünüm",
            )
        )

        tabs = QTabWidget()
        tabs.addTab(self._build_credit_cards_tab(), "Kredi Kartları")
        tabs.addTab(self._build_credit_limits_tab(), "Kredili / Limitli Mevduat")
        tabs.addTab(self._build_future_loans_tab(), "Banka Kredileri / Taksitli Krediler")

        root_layout.addLayout(header_layout)
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

        add_button = QPushButton("Kart Tanımla")
        add_button.setObjectName("CreditFacilitiesPrimaryButton")
        add_button.setEnabled(False)
        add_button.setToolTip("Bir sonraki adımda kredi kartı tanımlama formu bağlanacak.")

        edit_button = QPushButton("Kartı Düzenle")
        edit_button.setObjectName("CreditFacilitiesSecondaryButton")
        edit_button.setEnabled(False)
        edit_button.setToolTip("Bir sonraki adımda kredi kartı düzenleme formu bağlanacak.")

        statement_button = QPushButton("Ekstre Kaydı")
        statement_button.setObjectName("CreditFacilitiesSecondaryButton")
        statement_button.setEnabled(False)
        statement_button.setToolTip("Ekstre takibi bir sonraki fazda bağlanacak.")

        actions.addWidget(add_button)
        actions.addWidget(edit_button)
        actions.addWidget(statement_button)
        actions.addStretch(1)

        info = self._build_info_card(
            "Bu sekme kredi kartı tanımlarını göstermek için hazırlandı. "
            "Kart oluşturma/düzenleme formu bir sonraki adımda bağlanacak."
        )

        layout.addLayout(actions)
        layout.addWidget(info)
        layout.addWidget(self.credit_cards_table, 1)

        return tab

    def _build_credit_limits_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        actions = QHBoxLayout()
        actions.setSpacing(8)

        add_button = QPushButton("Limitli Hesap Tanımla")
        add_button.setObjectName("CreditFacilitiesPrimaryButton")
        add_button.setEnabled(False)
        add_button.setToolTip("Bir sonraki adımda kredili/limitli mevduat formu bağlanacak.")

        edit_button = QPushButton("Limit Tanımını Düzenle")
        edit_button.setObjectName("CreditFacilitiesSecondaryButton")
        edit_button.setEnabled(False)
        edit_button.setToolTip("Bir sonraki adımda limit tanımı düzenleme formu bağlanacak.")

        actions.addWidget(add_button)
        actions.addWidget(edit_button)
        actions.addStretch(1)

        info = self._build_info_card(
            "Bu sekme banka hesabına bağlı KMH / limitli mevduat / rotatif limit tanımlarını göstermek için hazırlandı."
        )

        layout.addLayout(actions)
        layout.addWidget(info)
        layout.addWidget(self.credit_limits_table, 1)

        return tab

    def _build_future_loans_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        info = self._build_info_card(
            "Banka Kredileri / Taksitli Krediler bölümü ileride ayrı ödeme planı, taksit, faiz ve kalan anapara takibiyle açılacak. "
            "Bu sekme şimdilik mimari yer tutucu olarak bırakıldı."
        )

        layout.addWidget(info)
        layout.addStretch(1)

        return tab

    def _build_summary_card(
        self,
        *,
        title: str,
        value_label: QLabel,
        hint: str,
    ) -> QWidget:
        card = QFrame()
        card.setObjectName("CreditFacilitiesSummaryCard")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)

        title_label = QLabel(title)
        title_label.setObjectName("CreditFacilitiesMetricLabel")

        hint_label = QLabel(hint)
        hint_label.setObjectName("CreditFacilitiesMuted")
        hint_label.setWordWrap(True)

        layout.addWidget(title_label)
        layout.addWidget(value_label)
        layout.addWidget(hint_label)

        return card

    def _build_info_card(self, text: str) -> QWidget:
        card = QFrame()
        card.setObjectName("CreditFacilitiesInfoCard")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)

        label = QLabel(text)
        label.setObjectName("CreditFacilitiesSubtitle")
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

    def _metric_value_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("CreditFacilitiesMetric")

        return label

    def refresh_data(self) -> None:
        try:
            with session_scope() as session:
                credit_cards = list_credit_cards(session, include_inactive=True)
                credit_limits = list_credit_limits(session, include_inactive=True)

                card_rows = []
                card_limit_total = Decimal("0.00")

                for credit_card in credit_cards:
                    if credit_card.is_active:
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
                credit_limit_total = Decimal("0.00")

                for credit_limit in credit_limits:
                    if credit_limit.is_active:
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

            self._fill_table(self.credit_cards_table, card_rows)
            self._fill_table(self.credit_limits_table, limit_rows)

            active_card_count = sum(1 for row in credit_cards if row.is_active)
            active_limit_count = sum(1 for row in credit_limits if row.is_active)

            self.card_count_label.setText(str(active_card_count))
            self.card_limit_label.setText(self._format_decimal(card_limit_total))
            self.limit_count_label.setText(str(active_limit_count))
            self.limit_total_label.setText(self._format_decimal(credit_limit_total))

            self.status_label.setText("Kredili Hesaplar / Kartlar verileri yenilendi.")

        except Exception as exc:
            QMessageBox.warning(
                self,
                "Kredili Hesaplar / Kartlar",
                f"Veriler yüklenirken hata oluştu:\n\n{exc}",
            )
            self.status_label.setText(f"Veriler yüklenemedi: {exc}")

    def _fill_table(self, table: QTableWidget, rows: list[list[Any]]) -> None:
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
