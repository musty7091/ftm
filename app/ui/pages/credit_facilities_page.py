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
    QInputDialog,
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
    CreditFacilityServiceError,
    activate_credit_card,
    activate_credit_limit,
    cancel_credit_limit_transaction,
    cancel_credit_card_payment,
    cancel_credit_card_transaction,
    deactivate_credit_card,
    deactivate_credit_limit,
    get_credit_card_debt_summary,
    get_credit_card_recommendation_status,
    get_credit_limit_debt_summary,
    list_credit_limit_transactions,
    list_credit_card_payments,
    list_credit_card_transactions,
    list_credit_cards,
    list_credit_limits,
)
from app.ui.pages.credit_facilities.credit_card_dialog import CreditCardDialog
from app.ui.pages.credit_facilities.credit_card_payment_dialog import CreditCardPaymentDialog
from app.ui.pages.credit_facilities.credit_card_statement_dialog import CreditCardStatementDialog
from app.ui.pages.credit_facilities.credit_card_transaction_dialog import CreditCardTransactionDialog
from app.ui.pages.credit_facilities.credit_limit_dialog import CreditLimitDialog
from app.ui.pages.credit_facilities.credit_limit_period_report_dialog import CreditLimitPeriodReportDialog
from app.ui.pages.credit_facilities.credit_limit_transaction_dialog import CreditLimitTransactionDialog


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

QLabel#CreditFacilitiesSectionTitle {
    color: #f8fafc;
    font-size: 14px;
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

QPushButton#CreditFacilitiesWarningButton {
    background-color: #92400e;
    color: #ffffff;
    border: 1px solid #f59e0b;
    border-radius: 10px;
    padding: 8px 14px;
    font-weight: 900;
}

QPushButton#CreditFacilitiesWarningButton:hover {
    background-color: #b45309;
}

QPushButton#CreditFacilitiesDangerButton {
    background-color: #7f1d1d;
    color: #ffffff;
    border: 1px solid #ef4444;
    border-radius: 10px;
    padding: 8px 14px;
    font-weight: 900;
}

QPushButton#CreditFacilitiesDangerButton:hover {
    background-color: #991b1b;
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


ACTIVE_TRANSACTION_STATUSES = {
    "PENDING",
    "IN_STATEMENT",
}

ACTIVE_PAYMENT_STATUSES = {
    "RECORDED",
}

ACTIVE_CREDIT_LIMIT_TRANSACTION_STATUSES = {
    "ACTIVE",
}


class CreditFacilitiesPage(QWidget):
    def __init__(self, current_user: Any | None = None) -> None:
        super().__init__()

        self.current_user = current_user
        self.setStyleSheet(CREDIT_FACILITIES_PAGE_STYLE)

        self._credit_card_row_ids: list[int | None] = []
        self._credit_card_row_active: list[bool | None] = []
        self._credit_card_row_display_names: list[str | None] = []
        self._credit_card_row_remaining_debt: list[Decimal | None] = []
        self._transaction_row_ids: list[int | None] = []
        self._transaction_row_status: list[str | None] = []
        self._payment_row_ids: list[int | None] = []
        self._payment_row_status: list[str | None] = []
        self._credit_limit_row_ids: list[int | None] = []
        self._credit_limit_row_active: list[bool | None] = []
        self._credit_limit_row_display_names: list[str | None] = []
        self._credit_limit_row_total_debt: list[Decimal | None] = []
        self._credit_limit_transaction_row_ids: list[int | None] = []
        self._credit_limit_transaction_row_status: list[str | None] = []

        self.credit_cards_table = self._build_table(
            [
                "Banka",
                "Kart Adı",
                "Son 4 Hane",
                "Kart Limiti",
                "Harcama",
                "Kullanılabilir Limit",
                "Tavsiye",
                "Kesim Tarihi",
                "Ödeme Tarihi",
                "Durum",
            ]
        )
        self.credit_cards_table.itemSelectionChanged.connect(self._on_credit_card_selection_changed)

        self.transactions_table = self._build_table(
            [
                "Kart",
                "Tarih",
                "İşyeri / Başlık",
                "Açıklama",
                "Tutar (TL)",
                "Taksit",
                "Durum",
                "Referans",
            ]
        )
        self.transactions_table.itemSelectionChanged.connect(self._update_transaction_actions)

        self.payments_table = self._build_table(
            [
                "Kart",
                "Tarih",
                "Ödeme Hesabı",
                "Tutar (TL)",
                "Durum",
                "Referans",
            ]
        )
        self.payments_table.itemSelectionChanged.connect(self._update_payment_actions)

        self.credit_limits_table = self._build_table(
            [
                "Banka Hesabı",
                "Limit Adı",
                "Tip",
                "Para",
                "Limit",
                "Faize Esas Borç",
                "Ödenebilir Borç",
                "Faiz / Masraf",
                "Kullanılabilir",
                "Faiz Oranı",
                "Gün",
                "Durum",
            ]
        )
        self.credit_limits_table.itemSelectionChanged.connect(self._on_credit_limit_selection_changed)

        self.credit_limit_transactions_table = self._build_table(
            [
                "Limit Hesabı",
                "İşlem Tarihi",
                "Faize Etki Tarihi",
                "Tür",
                "Tutar",
                "Durum",
                "Referans",
                "Açıklama",
            ]
        )
        self.credit_limit_transactions_table.itemSelectionChanged.connect(
            self._update_credit_limit_transaction_actions
        )

        self.card_count_value_label = self._summary_value_label("0")
        self.card_limit_value_label = self._summary_value_label("0,00 TL")
        self.card_used_value_label = self._summary_value_label("0,00 TL")
        self.card_remaining_value_label = self._summary_value_label("0,00 TL")
        self.limit_count_value_label = self._summary_value_label("0")
        self.limit_total_value_label = self._summary_value_label("0,00")
        self.limit_debt_value_label = self._summary_value_label("0,00")
        self.limit_available_value_label = self._summary_value_label("0,00")

        self.add_credit_card_button: QPushButton | None = None
        self.edit_credit_card_button: QPushButton | None = None
        self.toggle_credit_card_button: QPushButton | None = None
        self.transaction_credit_card_button: QPushButton | None = None
        self.payment_credit_card_button: QPushButton | None = None
        self.statement_credit_card_button: QPushButton | None = None
        self.cancel_transaction_button: QPushButton | None = None
        self.cancel_payment_button: QPushButton | None = None

        self.add_credit_limit_button: QPushButton | None = None
        self.edit_credit_limit_button: QPushButton | None = None
        self.toggle_credit_limit_button: QPushButton | None = None
        self.use_credit_limit_button: QPushButton | None = None
        self.pay_credit_limit_button: QPushButton | None = None
        self.period_report_credit_limit_button: QPushButton | None = None
        self.cancel_credit_limit_transaction_button: QPushButton | None = None

        self.transaction_title_label = QLabel("Harcama Kayıtları")
        self.transaction_title_label.setObjectName("CreditFacilitiesSectionTitle")

        self.payment_title_label = QLabel("Ödeme Kayıtları")
        self.payment_title_label.setObjectName("CreditFacilitiesSectionTitle")

        self.credit_limit_transaction_title_label = QLabel("Limit Hareketleri")
        self.credit_limit_transaction_title_label.setObjectName("CreditFacilitiesSectionTitle")

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
                second_label="Toplam limit",
                second_value_label=self.card_limit_value_label,
                third_label="Kalan borç",
                third_value_label=self.card_used_value_label,
                fourth_label="Kullanılabilir",
                fourth_value_label=self.card_remaining_value_label,
                hint="Kredi kartları sadece TL takip edilir; ödemeler bankadan düşer ve kart borcunu azaltır.",
            )
        )
        summary_layout.addWidget(
            self._build_summary_card(
                title="Kredili / Limitli Hesaplar",
                first_label="Aktif tanım",
                first_value_label=self.limit_count_value_label,
                second_label="Toplam limit",
                second_value_label=self.limit_total_value_label,
                third_label="Ödenebilir borç",
                third_value_label=self.limit_debt_value_label,
                fourth_label="Kullanılabilir",
                fourth_value_label=self.limit_available_value_label,
                hint="Ödenebilir borç kayıtlı gerçek borçtur; faize esas borç ve kullanılabilir limit valör tarihine göre hesaplanır.",
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
        self.add_credit_card_button.clicked.connect(self.open_credit_card_dialog)

        self.edit_credit_card_button = QPushButton("Düzenle")
        self.edit_credit_card_button.setObjectName("CreditFacilitiesSecondaryButton")
        self.edit_credit_card_button.setEnabled(False)
        self.edit_credit_card_button.clicked.connect(self.open_selected_credit_card_edit_dialog)

        self.toggle_credit_card_button = QPushButton("Pasife Al")
        self.toggle_credit_card_button.setObjectName("CreditFacilitiesWarningButton")
        self.toggle_credit_card_button.setEnabled(False)
        self.toggle_credit_card_button.clicked.connect(self.toggle_selected_credit_card_active_state)

        self.transaction_credit_card_button = QPushButton("Harcama Gir")
        self.transaction_credit_card_button.setObjectName("CreditFacilitiesPrimaryButton")
        self.transaction_credit_card_button.setEnabled(False)
        self.transaction_credit_card_button.clicked.connect(self.open_credit_card_transaction_dialog)

        self.payment_credit_card_button = QPushButton("Ödeme Gir")
        self.payment_credit_card_button.setObjectName("CreditFacilitiesPrimaryButton")
        self.payment_credit_card_button.setEnabled(False)
        self.payment_credit_card_button.clicked.connect(self.open_credit_card_payment_dialog)

        self.statement_credit_card_button = QPushButton("Ekstre")
        self.statement_credit_card_button.setObjectName("CreditFacilitiesSecondaryButton")
        self.statement_credit_card_button.setEnabled(False)
        self.statement_credit_card_button.setToolTip("Seçili kredi kartının dönem içi harcama ve ödeme hareketlerini gösterir.")
        self.statement_credit_card_button.clicked.connect(self.open_credit_card_statement_dialog)

        actions.addWidget(self.add_credit_card_button)
        actions.addWidget(self.edit_credit_card_button)
        actions.addWidget(self.toggle_credit_card_button)
        actions.addWidget(self.transaction_credit_card_button)
        actions.addWidget(self.payment_credit_card_button)
        actions.addWidget(self.statement_credit_card_button)
        actions.addStretch(1)

        hint_label = QLabel(
            "Kredi kartları sadece TL çalışır. Ödeme girildiğinde TL banka hesabından çıkış oluşur, "
            "kart borcu ve kullanılabilir limit otomatik güncellenir."
        )
        hint_label.setObjectName("CreditFacilitiesMuted")
        hint_label.setWordWrap(True)

        transaction_actions = QHBoxLayout()
        transaction_actions.setSpacing(8)

        self.cancel_transaction_button = QPushButton("Harcama İptal")
        self.cancel_transaction_button.setObjectName("CreditFacilitiesDangerButton")
        self.cancel_transaction_button.setEnabled(False)
        self.cancel_transaction_button.clicked.connect(self.cancel_selected_transaction)

        transaction_actions.addWidget(self.transaction_title_label)
        transaction_actions.addStretch(1)
        transaction_actions.addWidget(self.cancel_transaction_button)

        payment_actions = QHBoxLayout()
        payment_actions.setSpacing(8)

        self.cancel_payment_button = QPushButton("Ödeme İptal")
        self.cancel_payment_button.setObjectName("CreditFacilitiesDangerButton")
        self.cancel_payment_button.setEnabled(False)
        self.cancel_payment_button.clicked.connect(self.cancel_selected_payment)

        payment_actions.addWidget(self.payment_title_label)
        payment_actions.addStretch(1)
        payment_actions.addWidget(self.cancel_payment_button)

        layout.addLayout(actions)
        layout.addWidget(hint_label)
        layout.addWidget(self.credit_cards_table, 1)
        layout.addLayout(transaction_actions)
        layout.addWidget(self.transactions_table, 1)
        layout.addLayout(payment_actions)
        layout.addWidget(self.payments_table, 1)

        return tab

    def _build_credit_limits_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        actions = QHBoxLayout()
        actions.setSpacing(8)

        self.add_credit_limit_button = QPushButton("Limit Tanımla")
        self.add_credit_limit_button.setObjectName("CreditFacilitiesPrimaryButton")
        self.add_credit_limit_button.clicked.connect(self.open_credit_limit_dialog)

        self.edit_credit_limit_button = QPushButton("Düzenle")
        self.edit_credit_limit_button.setObjectName("CreditFacilitiesSecondaryButton")
        self.edit_credit_limit_button.setEnabled(False)
        self.edit_credit_limit_button.clicked.connect(self.open_selected_credit_limit_edit_dialog)

        self.toggle_credit_limit_button = QPushButton("Pasife Al")
        self.toggle_credit_limit_button.setObjectName("CreditFacilitiesWarningButton")
        self.toggle_credit_limit_button.setEnabled(False)
        self.toggle_credit_limit_button.clicked.connect(self.toggle_selected_credit_limit_active_state)

        self.use_credit_limit_button = QPushButton("Limit Kullan")
        self.use_credit_limit_button.setObjectName("CreditFacilitiesPrimaryButton")
        self.use_credit_limit_button.setEnabled(False)
        self.use_credit_limit_button.setToolTip("Seçili limitli hesap için kullanım hareketi oluşturur. Kullanım aynı gün faize etki eder.")
        self.use_credit_limit_button.clicked.connect(self.open_credit_limit_usage_dialog)

        self.pay_credit_limit_button = QPushButton("Limit Öde")
        self.pay_credit_limit_button.setObjectName("CreditFacilitiesPrimaryButton")
        self.pay_credit_limit_button.setEnabled(False)
        self.pay_credit_limit_button.setToolTip("Seçili limitli hesap için ödeme hareketi oluşturur. Ödeme faiz hesabında ertesi gün borçtan düşer.")
        self.pay_credit_limit_button.clicked.connect(self.open_credit_limit_payment_dialog)

        self.period_report_credit_limit_button = QPushButton("Dönem Raporu")
        self.period_report_credit_limit_button.setObjectName("CreditFacilitiesSecondaryButton")
        self.period_report_credit_limit_button.setEnabled(False)
        self.period_report_credit_limit_button.setToolTip("Seçili limitli hesabın dönem hareketlerini ve günlük faiz hesabını gösterir.")
        self.period_report_credit_limit_button.clicked.connect(self.open_credit_limit_period_report_dialog)

        actions.addWidget(self.add_credit_limit_button)
        actions.addWidget(self.edit_credit_limit_button)
        actions.addWidget(self.toggle_credit_limit_button)
        actions.addWidget(self.use_credit_limit_button)
        actions.addWidget(self.pay_credit_limit_button)
        actions.addWidget(self.period_report_credit_limit_button)
        actions.addStretch(1)

        hint_label = QLabel(
            "Limit kullanımı aynı gün faize etki eder. Limit ödemesi banka valörü nedeniyle faiz hesabında "
            "ertesi gün borçtan düşer. Hareket dökümünde işlem tarihi ve faize etki tarihi ayrı gösterilir."
        )
        hint_label.setObjectName("CreditFacilitiesMuted")
        hint_label.setWordWrap(True)

        movement_actions = QHBoxLayout()
        movement_actions.setSpacing(8)

        self.cancel_credit_limit_transaction_button = QPushButton("Hareket İptal")
        self.cancel_credit_limit_transaction_button.setObjectName("CreditFacilitiesDangerButton")
        self.cancel_credit_limit_transaction_button.setEnabled(False)
        self.cancel_credit_limit_transaction_button.clicked.connect(self.cancel_selected_credit_limit_transaction)

        movement_actions.addWidget(self.credit_limit_transaction_title_label)
        movement_actions.addStretch(1)
        movement_actions.addWidget(self.cancel_credit_limit_transaction_button)

        layout.addLayout(actions)
        layout.addWidget(hint_label)
        layout.addWidget(self.credit_limits_table, 1)
        layout.addLayout(movement_actions)
        layout.addWidget(self.credit_limit_transactions_table, 1)

        return tab

    def _build_future_loans_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        info = QLabel(
            "Banka Kredileri / Taksitli Krediler bölümü sonraki fazda açılacak. "
            "Burada kredi tanımı, taksit planı, faiz ve kalan anapara takibi yer alacak."
        )
        info.setObjectName("CreditFacilitiesMuted")
        info.setWordWrap(True)

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
        third_label: str,
        third_value_label: QLabel | None,
        fourth_label: str,
        fourth_value_label: QLabel | None,
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

        metrics_layout.addWidget(first_label_widget, 0, 0)
        metrics_layout.addWidget(second_label_widget, 0, 1)
        metrics_layout.addWidget(first_value_label, 1, 0)
        metrics_layout.addWidget(second_value_label, 1, 1)

        if third_value_label is not None:
            third_label_widget = QLabel(third_label)
            third_label_widget.setObjectName("CreditFacilitiesMetricLabel")
            metrics_layout.addWidget(third_label_widget, 0, 2)
            metrics_layout.addWidget(third_value_label, 1, 2)

        if fourth_value_label is not None:
            fourth_label_widget = QLabel(fourth_label)
            fourth_label_widget.setObjectName("CreditFacilitiesMetricLabel")
            metrics_layout.addWidget(fourth_label_widget, 0, 3)
            metrics_layout.addWidget(fourth_value_label, 1, 3)

        hint_label = QLabel(hint)
        hint_label.setObjectName("CreditFacilitiesMuted")
        hint_label.setWordWrap(True)

        layout.addWidget(title_label)
        layout.addLayout(metrics_layout)
        layout.addWidget(hint_label)

        return card

    def _build_table(self, headers: list[str]) -> QTableWidget:
        table = QTableWidget()
        table.setObjectName("CreditFacilitiesTable")
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setSelectionMode(QTableWidget.SingleSelection)
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
        dialog = CreditCardDialog(
            current_user=self.current_user,
            parent=self,
        )

        if dialog.exec() == QDialog.Accepted:
            self.refresh_data()

    def open_selected_credit_card_edit_dialog(self) -> None:
        credit_card_id = self._selected_credit_card_id()

        if credit_card_id is None:
            QMessageBox.warning(
                self,
                "Kart Seçilmedi",
                "Düzenlemek için listeden bir kredi kartı seçmelisin.",
            )
            return

        dialog = CreditCardDialog(
            current_user=self.current_user,
            credit_card_id=credit_card_id,
            parent=self,
        )

        if dialog.exec() == QDialog.Accepted:
            self.refresh_data()

    def open_credit_card_transaction_dialog(self) -> None:
        credit_card_id = self._selected_credit_card_id()
        is_active = self._selected_credit_card_is_active()

        if credit_card_id is None:
            QMessageBox.warning(
                self,
                "Kart Seçilmedi",
                "Harcama girmek için listeden bir kredi kartı seçmelisin.",
            )
            return

        if is_active is not True:
            QMessageBox.warning(
                self,
                "Kart Pasif",
                "Pasif karta harcama girişi yapılamaz.",
            )
            return

        dialog = CreditCardTransactionDialog(
            current_user=self.current_user,
            credit_card_id=credit_card_id,
            parent=self,
        )

        if dialog.exec() == QDialog.Accepted:
            self.refresh_data()
            self._restore_credit_card_selection(credit_card_id)
            self.status_label.setText("Kredi kartı harcaması kaydedildi.")

    def open_credit_card_payment_dialog(self) -> None:
        credit_card_id = self._selected_credit_card_id()
        is_active = self._selected_credit_card_is_active()
        remaining_debt = self._selected_credit_card_remaining_debt()

        if credit_card_id is None:
            QMessageBox.warning(
                self,
                "Kart Seçilmedi",
                "Ödeme girmek için listeden bir kredi kartı seçmelisin.",
            )
            return

        if is_active is not True:
            QMessageBox.warning(
                self,
                "Kart Pasif",
                "Pasif karta ödeme girişi yapılamaz.",
            )
            return

        if remaining_debt is not None and remaining_debt <= Decimal("0.00"):
            QMessageBox.information(
                self,
                "Ödenecek Borç Yok",
                "Seçili kredi kartı için ödenecek borç bulunmuyor.",
            )
            return

        dialog = CreditCardPaymentDialog(
            current_user=self.current_user,
            credit_card_id=credit_card_id,
            parent=self,
        )

        if dialog.exec() == QDialog.Accepted:
            self.refresh_data()
            self._restore_credit_card_selection(credit_card_id)
            self.status_label.setText("Kredi kartı ödemesi kaydedildi.")

    def open_credit_card_statement_dialog(self) -> None:
        credit_card_id = self._selected_credit_card_id()

        if credit_card_id is None:
            QMessageBox.warning(
                self,
                "Kart Seçilmedi",
                "Ekstre hareketlerini görmek için listeden bir kredi kartı seçmelisin.",
            )
            return

        dialog = CreditCardStatementDialog(
            credit_card_id=credit_card_id,
            parent=self,
        )

        dialog.exec()
        self.status_label.setText("Kredi kartı dönem hareketleri görüntülendi.")

    def open_credit_limit_dialog(self) -> None:
        dialog = CreditLimitDialog(
            current_user=self.current_user,
            parent=self,
        )

        if dialog.exec() == QDialog.Accepted:
            self.refresh_data()
            self.status_label.setText("Limitli hesap tanımı kaydedildi.")

    def open_selected_credit_limit_edit_dialog(self) -> None:
        credit_limit_id = self._selected_credit_limit_id()

        if credit_limit_id is None:
            QMessageBox.warning(
                self,
                "Limit Seçilmedi",
                "Düzenlemek için listeden bir limitli hesap seçmelisin.",
            )
            return

        dialog = CreditLimitDialog(
            current_user=self.current_user,
            credit_limit_id=credit_limit_id,
            parent=self,
        )

        if dialog.exec() == QDialog.Accepted:
            self.refresh_data()
            self._restore_credit_limit_selection(credit_limit_id)
            self.status_label.setText("Limitli hesap tanımı güncellendi.")

    def toggle_selected_credit_limit_active_state(self) -> None:
        credit_limit_id = self._selected_credit_limit_id()
        is_active = self._selected_credit_limit_is_active()
        display_name = self._selected_credit_limit_display_name() or "Seçili limitli hesap"

        if credit_limit_id is None or is_active is None:
            QMessageBox.warning(
                self,
                "Limit Seçilmedi",
                "İşlem yapmak için listeden bir limitli hesap seçmelisin.",
            )
            return

        if is_active:
            question = f"{display_name} pasife alınacak. Devam etmek istiyor musun?"
            button_text = "Limiti Pasife Al"
        else:
            question = f"{display_name} tekrar aktif hale getirilecek. Devam etmek istiyor musun?"
            button_text = "Limiti Aktifleştir"

        answer = QMessageBox.question(
            self,
            button_text,
            question,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if answer != QMessageBox.Yes:
            return

        try:
            with session_scope() as session:
                if is_active:
                    deactivate_credit_limit(
                        session,
                        credit_limit_id=credit_limit_id,
                        updated_by_user_id=self._current_user_id(),
                    )
                else:
                    activate_credit_limit(
                        session,
                        credit_limit_id=credit_limit_id,
                        updated_by_user_id=self._current_user_id(),
                    )

        except CreditFacilityServiceError as exc:
            QMessageBox.warning(
                self,
                "Limit Durumu Değiştirilemedi",
                str(exc),
            )
            return

        except Exception as exc:
            QMessageBox.critical(
                self,
                "Beklenmeyen Hata",
                f"Limit durumu değiştirilirken beklenmeyen hata oluştu:\n\n{exc}",
            )
            return

        self.refresh_data()
        self._restore_credit_limit_selection(credit_limit_id)
        self.status_label.setText("Limitli hesap durumu güncellendi.")

    def open_credit_limit_usage_dialog(self) -> None:
        self._open_credit_limit_transaction_dialog(mode=CreditLimitTransactionDialog.MODE_USAGE)

    def open_credit_limit_payment_dialog(self) -> None:
        self._open_credit_limit_transaction_dialog(mode=CreditLimitTransactionDialog.MODE_PAYMENT)

    def open_credit_limit_period_report_dialog(self) -> None:
        credit_limit_id = self._selected_credit_limit_id()

        if credit_limit_id is None:
            QMessageBox.warning(
                self,
                "Limit Seçilmedi",
                "Dönem raporu almak için listeden bir kredili / limitli hesap seçmelisin.",
            )
            return

        dialog = CreditLimitPeriodReportDialog(
            current_user=self.current_user,
            credit_limit_id=credit_limit_id,
            parent=self,
        )
        dialog.exec()

    def _open_credit_limit_transaction_dialog(self, *, mode: str) -> None:
        credit_limit_id = self._selected_credit_limit_id()
        is_active = self._selected_credit_limit_is_active()

        if credit_limit_id is None:
            QMessageBox.warning(
                self,
                "Limit Seçilmedi",
                "İşlem yapmak için listeden bir kredili / limitli hesap seçmelisin.",
            )
            return

        if is_active is not True:
            QMessageBox.warning(
                self,
                "Limit Pasif",
                "Pasif kredili / limitli hesap için kullanım veya ödeme hareketi girilemez.",
            )
            return

        dialog = CreditLimitTransactionDialog(
            current_user=self.current_user,
            credit_limit_id=credit_limit_id,
            mode=mode,
            parent=self,
        )

        if dialog.exec() == QDialog.Accepted:
            self.refresh_data()
            self._restore_credit_limit_selection(credit_limit_id)

            if mode == CreditLimitTransactionDialog.MODE_USAGE:
                self.status_label.setText("Limit kullanım hareketi kaydedildi.")
            else:
                self.status_label.setText("Limit ödeme hareketi kaydedildi.")

    def cancel_selected_credit_limit_transaction(self) -> None:
        transaction_id = self._selected_credit_limit_transaction_id()
        transaction_status = self._selected_credit_limit_transaction_status()
        credit_limit_id = self._selected_credit_limit_id()

        if transaction_id is None:
            QMessageBox.warning(
                self,
                "Hareket Seçilmedi",
                "İptal etmek için listeden bir limit hareketi seçmelisin.",
            )
            return

        if transaction_status == "CANCELLED":
            QMessageBox.information(
                self,
                "Hareket Zaten İptal",
                "Seçili limit hareketi zaten iptal edilmiş.",
            )
            return

        cancel_reason, accepted = QInputDialog.getText(
            self,
            "Limit Hareketi İptal Nedeni",
            "İptal nedeni:",
        )

        if not accepted:
            return

        if not str(cancel_reason or "").strip():
            QMessageBox.warning(
                self,
                "Eksik Bilgi",
                "Limit hareketi iptali için açıklama girmelisin.",
            )
            return

        answer = QMessageBox.question(
            self,
            "Limit Hareketi İptal",
            "Seçili limit hareketi ve varsa bağlı banka hareketi iptal edilecek. Devam etmek istiyor musun?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if answer != QMessageBox.Yes:
            return

        try:
            with session_scope() as session:
                cancel_credit_limit_transaction(
                    session,
                    transaction_id=transaction_id,
                    cancel_reason=str(cancel_reason),
                    cancelled_by_user_id=self._current_user_id(),
                )

        except CreditFacilityServiceError as exc:
            QMessageBox.warning(
                self,
                "Limit Hareketi İptal Edilemedi",
                str(exc),
            )
            return

        except Exception as exc:
            QMessageBox.critical(
                self,
                "Beklenmeyen Hata",
                f"Limit hareketi iptal edilirken beklenmeyen hata oluştu:\n\n{exc}",
            )
            return

        self.refresh_data()

        if credit_limit_id is not None:
            self._restore_credit_limit_selection(credit_limit_id)

        self.status_label.setText("Limit hareketi iptal edildi.")

    def toggle_selected_credit_card_active_state(self) -> None:
        credit_card_id = self._selected_credit_card_id()
        is_active = self._selected_credit_card_is_active()

        if credit_card_id is None or is_active is None:
            QMessageBox.warning(
                self,
                "Kart Seçilmedi",
                "İşlem yapmak için listeden bir kredi kartı seçmelisin.",
            )
            return

        if is_active:
            question = "Seçili kredi kartı pasife alınacak. Devam etmek istiyor musun?"
            button_text = "Kartı Pasife Al"
        else:
            question = "Seçili kredi kartı tekrar aktif hale getirilecek. Devam etmek istiyor musun?"
            button_text = "Kartı Aktifleştir"

        answer = QMessageBox.question(
            self,
            button_text,
            question,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if answer != QMessageBox.Yes:
            return

        try:
            with session_scope() as session:
                if is_active:
                    deactivate_credit_card(
                        session,
                        credit_card_id=credit_card_id,
                        updated_by_user_id=self._current_user_id(),
                    )
                else:
                    activate_credit_card(
                        session,
                        credit_card_id=credit_card_id,
                        updated_by_user_id=self._current_user_id(),
                    )

        except CreditFacilityServiceError as exc:
            QMessageBox.warning(
                self,
                "Kart Durumu Değiştirilemedi",
                str(exc),
            )
            return

        except Exception as exc:
            QMessageBox.critical(
                self,
                "Beklenmeyen Hata",
                f"Kart durumu değiştirilirken beklenmeyen hata oluştu:\n\n{exc}",
            )
            return

        self.refresh_data()
        self._restore_credit_card_selection(credit_card_id)

    def cancel_selected_transaction(self) -> None:
        transaction_id = self._selected_transaction_id()
        transaction_status = self._selected_transaction_status()
        credit_card_id = self._selected_credit_card_id()

        if transaction_id is None:
            QMessageBox.warning(
                self,
                "Harcama Seçilmedi",
                "İptal etmek için listeden bir harcama seçmelisin.",
            )
            return

        if transaction_status == "CANCELLED":
            QMessageBox.information(
                self,
                "Harcama Zaten İptal",
                "Seçili harcama zaten iptal edilmiş.",
            )
            return

        answer = QMessageBox.question(
            self,
            "Harcama İptal",
            "Seçili kredi kartı harcaması iptal edilecek. Devam etmek istiyor musun?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if answer != QMessageBox.Yes:
            return

        try:
            with session_scope() as session:
                cancel_credit_card_transaction(
                    session,
                    transaction_id=transaction_id,
                    updated_by_user_id=self._current_user_id(),
                )

        except CreditFacilityServiceError as exc:
            QMessageBox.warning(
                self,
                "Harcama İptal Edilemedi",
                str(exc),
            )
            return

        except Exception as exc:
            QMessageBox.critical(
                self,
                "Beklenmeyen Hata",
                f"Harcama iptal edilirken beklenmeyen hata oluştu:\n\n{exc}",
            )
            return

        self.refresh_data()

        if credit_card_id is not None:
            self._restore_credit_card_selection(credit_card_id)

        self.status_label.setText("Kredi kartı harcaması iptal edildi.")

    def cancel_selected_payment(self) -> None:
        payment_id = self._selected_payment_id()
        payment_status = self._selected_payment_status()
        credit_card_id = self._selected_credit_card_id()

        if payment_id is None:
            QMessageBox.warning(
                self,
                "Ödeme Seçilmedi",
                "İptal etmek için listeden bir ödeme seçmelisin.",
            )
            return

        if payment_status == "CANCELLED":
            QMessageBox.information(
                self,
                "Ödeme Zaten İptal",
                "Seçili ödeme zaten iptal edilmiş.",
            )
            return

        cancel_reason, accepted = QInputDialog.getText(
            self,
            "Ödeme İptal Nedeni",
            "Ödeme iptal nedeni:",
        )

        if not accepted:
            return

        if not str(cancel_reason or "").strip():
            QMessageBox.warning(
                self,
                "Eksik Bilgi",
                "Ödeme iptali için açıklama girmelisin.",
            )
            return

        answer = QMessageBox.question(
            self,
            "Ödeme İptal",
            "Seçili kredi kartı ödemesi ve buna bağlı banka hareketi iptal edilecek. Devam etmek istiyor musun?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if answer != QMessageBox.Yes:
            return

        try:
            with session_scope() as session:
                cancel_credit_card_payment(
                    session,
                    payment_id=payment_id,
                    cancel_reason=str(cancel_reason),
                    cancelled_by_user_id=self._current_user_id(),
                )

        except CreditFacilityServiceError as exc:
            QMessageBox.warning(
                self,
                "Ödeme İptal Edilemedi",
                str(exc),
            )
            return

        except Exception as exc:
            QMessageBox.critical(
                self,
                "Beklenmeyen Hata",
                f"Ödeme iptal edilirken beklenmeyen hata oluştu:\n\n{exc}",
            )
            return

        self.refresh_data()

        if credit_card_id is not None:
            self._restore_credit_card_selection(credit_card_id)

        self.status_label.setText("Kredi kartı ödemesi iptal edildi.")

    def refresh_data(self) -> None:
        try:
            with session_scope() as session:
                credit_cards = list_credit_cards(session, include_inactive=True)
                credit_limits = list_credit_limits(session, include_inactive=True)

                card_rows: list[list[Any]] = []
                card_row_ids: list[int | None] = []
                card_row_active: list[bool | None] = []
                card_row_display_names: list[str | None] = []
                card_row_remaining_debt: list[Decimal | None] = []
                active_card_count = 0
                card_limit_total = Decimal("0.00")
                card_remaining_debt_total = Decimal("0.00")
                card_available_limit_total = Decimal("0.00")

                for credit_card in credit_cards:
                    card_id = int(credit_card.id)
                    debt_summary = get_credit_card_debt_summary(session, credit_card_id=card_id)

                    card_limit = Decimal(debt_summary["credit_limit"] or Decimal("0.00"))
                    remaining_debt = Decimal(debt_summary["remaining_debt"] or Decimal("0.00"))
                    available_limit = Decimal(debt_summary["available_limit"] or Decimal("0.00"))

                    recommendation = get_credit_card_recommendation_status(
                        credit_card=credit_card,
                        available_limit=available_limit,
                    )
                    recommendation_label = str(recommendation.get("label") or "-")

                    if credit_card.is_active:
                        active_card_count += 1
                        card_limit_total += card_limit
                        card_remaining_debt_total += remaining_debt
                        card_available_limit_total += available_limit

                    bank_name = "-"
                    if getattr(credit_card, "bank", None) is not None:
                        bank_name = credit_card.bank.name or "-"

                    display_name = self._credit_card_display_name(
                        bank_name=bank_name,
                        card_name=credit_card.card_name,
                        last_four_digits=credit_card.last_four_digits,
                    )

                    card_rows.append(
                        [
                            bank_name,
                            credit_card.card_name,
                            credit_card.last_four_digits or "-",
                            self._format_tl(card_limit),
                            self._format_tl(remaining_debt),
                            self._format_tl(available_limit),
                            recommendation_label,
                            self._format_day(credit_card.statement_cut_day),
                            self._format_day(credit_card.payment_due_day),
                            "Aktif" if credit_card.is_active else "Pasif",
                        ]
                    )
                    card_row_ids.append(card_id)
                    card_row_active.append(bool(credit_card.is_active))
                    card_row_display_names.append(display_name)
                    card_row_remaining_debt.append(remaining_debt)

                limit_rows: list[list[Any]] = []
                credit_limit_row_ids: list[int | None] = []
                credit_limit_row_active: list[bool | None] = []
                credit_limit_row_display_names: list[str | None] = []
                credit_limit_row_total_debt: list[Decimal | None] = []
                active_limit_count = 0
                credit_limit_total = Decimal("0.00")
                credit_limit_debt_total = Decimal("0.00")
                credit_limit_available_total = Decimal("0.00")

                for credit_limit in credit_limits:
                    credit_limit_id = int(credit_limit.id)
                    debt_summary = get_credit_limit_debt_summary(
                        session,
                        credit_limit_id=credit_limit_id,
                    )

                    limit_amount = Decimal(debt_summary["limit_amount"] or Decimal("0.00"))
                    principal_debt = Decimal(debt_summary["principal_debt"] or Decimal("0.00"))
                    interest_fee_total = Decimal(debt_summary["interest_total"] or Decimal("0.00")) + Decimal(
                        debt_summary["fee_total"] or Decimal("0.00")
                    )
                    total_debt = Decimal(debt_summary["total_debt"] or Decimal("0.00"))
                    booked_total_debt = Decimal(debt_summary["booked_total_debt"] or Decimal("0.00"))
                    available_limit = Decimal(debt_summary["available_limit"] or Decimal("0.00"))

                    if credit_limit.is_active:
                        active_limit_count += 1
                        credit_limit_total += limit_amount
                        credit_limit_debt_total += booked_total_debt
                        credit_limit_available_total += available_limit

                    account_name = "-"
                    bank_account = getattr(credit_limit, "bank_account", None)
                    if bank_account is not None:
                        bank_name = "-"
                        if getattr(bank_account, "bank", None) is not None:
                            bank_name = bank_account.bank.name or "-"
                        account_name = f"{bank_name} / {bank_account.account_name}"

                    display_name = f"{account_name} / {credit_limit.limit_name}"
                    currency_code = str(debt_summary.get("currency_code") or credit_limit.currency_code.value)

                    limit_rows.append(
                        [
                            account_name,
                            credit_limit.limit_name,
                            self._credit_limit_type_text(credit_limit.limit_type.value),
                            currency_code,
                            self._format_money(limit_amount, currency_code),
                            self._format_money(principal_debt, currency_code),
                            self._format_money(booked_total_debt, currency_code),
                            self._format_money(interest_fee_total, currency_code),
                            self._format_money(available_limit, currency_code),
                            f"% {self._format_decimal(credit_limit.interest_rate)}",
                            self._format_day(credit_limit.interest_day),
                            "Aktif" if credit_limit.is_active else "Pasif",
                        ]
                    )
                    credit_limit_row_ids.append(credit_limit_id)
                    credit_limit_row_active.append(bool(credit_limit.is_active))
                    credit_limit_row_display_names.append(display_name)
                    credit_limit_row_total_debt.append(booked_total_debt)

            self._credit_card_row_ids = card_row_ids
            self._credit_card_row_active = card_row_active
            self._credit_card_row_display_names = card_row_display_names
            self._credit_card_row_remaining_debt = card_row_remaining_debt
            self._credit_limit_row_ids = credit_limit_row_ids
            self._credit_limit_row_active = credit_limit_row_active
            self._credit_limit_row_display_names = credit_limit_row_display_names
            self._credit_limit_row_total_debt = credit_limit_row_total_debt

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
            self.card_limit_value_label.setText(self._format_tl(card_limit_total))
            self.card_used_value_label.setText(self._format_tl(card_remaining_debt_total))
            self.card_remaining_value_label.setText(self._format_tl(card_available_limit_total))
            self.limit_count_value_label.setText(str(active_limit_count))
            self.limit_total_value_label.setText(self._format_decimal(credit_limit_total))
            self.limit_debt_value_label.setText(self._format_decimal(credit_limit_debt_total))
            self.limit_available_value_label.setText(self._format_decimal(credit_limit_available_total))

            self.status_label.setText("Kredili Hesaplar / Kartlar verileri yenilendi.")
            self._update_credit_card_actions()
            self._update_credit_limit_actions()
            self.refresh_transactions_for_selected_card()
            self.refresh_payments_for_selected_card()
            self.refresh_credit_limit_transactions_for_selected_limit()

        except Exception as exc:
            QMessageBox.warning(
                self,
                "Kredili Hesaplar / Kartlar",
                f"Veriler yüklenirken hata oluştu:\n\n{exc}",
            )
            self.status_label.setText(f"Veriler yüklenemedi: {exc}")

    def refresh_transactions_for_selected_card(self) -> None:
        credit_card_id = self._selected_credit_card_id()

        if credit_card_id is None:
            self._transaction_row_ids = []
            self._transaction_row_status = []
            self.transaction_title_label.setText("Harcama Kayıtları")
            self._fill_table(
                table=self.transactions_table,
                rows=[],
                empty_message="Harcama görmek için önce bir kredi kartı seç.",
            )
            self._update_transaction_actions()
            return

        selected_card_name = self._selected_credit_card_display_name() or "Seçili Kart"

        try:
            with session_scope() as session:
                transactions = list_credit_card_transactions(
                    session,
                    credit_card_id=credit_card_id,
                    include_cancelled=True,
                )
                payments = list_credit_card_payments(
                    session,
                    credit_card_id=credit_card_id,
                    include_cancelled=True,
                )
                payment_status_by_transaction_id = self._build_transaction_payment_status_map(
                    transactions=transactions,
                    payments=payments,
                )

                rows: list[list[Any]] = []
                row_ids: list[int | None] = []
                row_statuses: list[str | None] = []

                for transaction in transactions:
                    transaction_id = int(transaction.id)
                    rows.append(
                        [
                            selected_card_name,
                            self._format_date(transaction.transaction_date),
                            transaction.merchant_name,
                            transaction.description or "-",
                            self._format_tl(transaction.amount),
                            f"{transaction.installment_no}/{transaction.installment_count}",
                            payment_status_by_transaction_id.get(
                                transaction_id,
                                self._transaction_status_text(transaction.status.value),
                            ),
                            transaction.reference_no or "-",
                        ]
                    )
                    row_ids.append(transaction_id)
                    row_statuses.append(transaction.status.value)

            self._transaction_row_ids = row_ids
            self._transaction_row_status = row_statuses

            self.transaction_title_label.setText(f"Harcama Kayıtları - {selected_card_name}")
            self._fill_table(
                table=self.transactions_table,
                rows=rows,
                empty_message=f"{selected_card_name} için henüz harcama kaydı yok.",
            )
            self._update_transaction_actions()

        except Exception as exc:
            QMessageBox.warning(
                self,
                "Harcama Listesi",
                f"Harcama kayıtları yüklenirken hata oluştu:\n\n{exc}",
            )

    def refresh_payments_for_selected_card(self) -> None:
        credit_card_id = self._selected_credit_card_id()

        if credit_card_id is None:
            self._payment_row_ids = []
            self._payment_row_status = []
            self.payment_title_label.setText("Ödeme Kayıtları")
            self._fill_table(
                table=self.payments_table,
                rows=[],
                empty_message="Ödeme görmek için önce bir kredi kartı seç.",
            )
            self._update_payment_actions()
            return

        selected_card_name = self._selected_credit_card_display_name() or "Seçili Kart"

        try:
            with session_scope() as session:
                payments = list_credit_card_payments(
                    session,
                    credit_card_id=credit_card_id,
                    include_cancelled=True,
                )

                rows: list[list[Any]] = []
                row_ids: list[int | None] = []
                row_statuses: list[str | None] = []

                for payment in payments:
                    account_label = "-"
                    payment_account = getattr(payment, "payment_bank_account", None)
                    if payment_account is not None:
                        bank_name = "-"
                        if getattr(payment_account, "bank", None) is not None:
                            bank_name = payment_account.bank.name or "-"
                        account_label = f"{bank_name} / {payment_account.account_name}"

                    rows.append(
                        [
                            selected_card_name,
                            self._format_date(payment.payment_date),
                            account_label,
                            self._format_tl(payment.amount),
                            self._payment_status_text(payment.status.value),
                            payment.reference_no or "-",
                        ]
                    )
                    row_ids.append(int(payment.id))
                    row_statuses.append(payment.status.value)

            self._payment_row_ids = row_ids
            self._payment_row_status = row_statuses

            self.payment_title_label.setText(f"Ödeme Kayıtları - {selected_card_name}")
            self._fill_table(
                table=self.payments_table,
                rows=rows,
                empty_message=f"{selected_card_name} için henüz ödeme kaydı yok.",
            )
            self._update_payment_actions()

        except Exception as exc:
            QMessageBox.warning(
                self,
                "Ödeme Listesi",
                f"Ödeme kayıtları yüklenirken hata oluştu:\n\n{exc}",
            )

    def refresh_credit_limit_transactions_for_selected_limit(self) -> None:
        credit_limit_id = self._selected_credit_limit_id()

        if credit_limit_id is None:
            self._credit_limit_transaction_row_ids = []
            self._credit_limit_transaction_row_status = []
            self.credit_limit_transaction_title_label.setText("Limit Hareketleri")
            self._fill_table(
                table=self.credit_limit_transactions_table,
                rows=[],
                empty_message="Hareket görmek için önce bir kredili / limitli hesap seç.",
            )
            self._update_credit_limit_transaction_actions()
            return

        selected_limit_name = self._selected_credit_limit_display_name() or "Seçili Limit"

        try:
            with session_scope() as session:
                transactions = list_credit_limit_transactions(
                    session,
                    credit_limit_id=credit_limit_id,
                    include_cancelled=True,
                )

                rows: list[list[Any]] = []
                row_ids: list[int | None] = []
                row_statuses: list[str | None] = []

                for transaction in transactions:
                    currency_code = str(
                        getattr(transaction.currency_code, "value", transaction.currency_code) or ""
                    )
                    transaction_type = str(
                        getattr(transaction.transaction_type, "value", transaction.transaction_type) or ""
                    )
                    transaction_status = str(
                        getattr(transaction.status, "value", transaction.status) or ""
                    )

                    rows.append(
                        [
                            selected_limit_name,
                            self._format_date(transaction.transaction_date),
                            self._format_date(transaction.effective_date),
                            self._credit_limit_transaction_type_text(transaction_type),
                            self._format_money(transaction.amount, currency_code),
                            self._credit_limit_transaction_status_text(transaction_status),
                            transaction.reference_no or "-",
                            transaction.description or "-",
                        ]
                    )
                    row_ids.append(int(transaction.id))
                    row_statuses.append(transaction_status)

            self._credit_limit_transaction_row_ids = row_ids
            self._credit_limit_transaction_row_status = row_statuses

            self.credit_limit_transaction_title_label.setText(f"Limit Hareketleri - {selected_limit_name}")
            self._fill_table(
                table=self.credit_limit_transactions_table,
                rows=rows,
                empty_message=f"{selected_limit_name} için henüz limit hareketi yok.",
            )
            self._update_credit_limit_transaction_actions()

        except Exception as exc:
            QMessageBox.warning(
                self,
                "Limit Hareketleri",
                f"Limit hareketleri yüklenirken hata oluştu:\n\n{exc}",
            )

    def _fill_table(
        self,
        *,
        table: QTableWidget,
        rows: list[list[Any]],
        empty_message: str,
    ) -> None:
        table.clearSpans()
        table.clearSelection()

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

                text_value = str(value).strip().upper()

                if text_value in {
                    "AKTIF",
                    "KAYITLI",
                    "AKTİF",
                    "ÖDENDI",
                    "ÖDENDİ",
                    "TAVSIYE EDILEN",
                    "TAVSİYE EDİLEN",
                }:
                    item.setForeground(QColor("#22c55e"))
                elif text_value in {"PASIF", "İPTAL", "IPTAL", "LIMIT YETERSIZ", "LİMİT YETERSİZ"}:
                    item.setForeground(QColor("#f87171"))
                elif text_value in {"EKSTREDE", "UYGUN"}:
                    item.setForeground(QColor("#60a5fa"))
                elif text_value in {
                    "BORÇTA",
                    "KISMI ÖDENDI",
                    "KISMI ÖDENDİ",
                    "KISMİ ÖDENDI",
                    "KISMİ ÖDENDİ",
                    "İADE",
                    "KESIME YAKIN",
                    "KESİME YAKIN",
                    "BUGÜN KESIM",
                    "BUGÜN KESİM",
                    "TARIH YOK",
                    "TARİH YOK",
                }:
                    item.setForeground(QColor("#fbbf24"))

                table.setItem(row_index, column_index, item)

        table.resizeRowsToContents()

    def _on_credit_card_selection_changed(self) -> None:
        self._update_credit_card_actions()
        self.refresh_transactions_for_selected_card()
        self.refresh_payments_for_selected_card()

    def _on_credit_limit_selection_changed(self) -> None:
        self._update_credit_limit_actions()
        self.refresh_credit_limit_transactions_for_selected_limit()

    def _restore_credit_limit_selection(self, credit_limit_id: int) -> None:
        for row_index, row_credit_limit_id in enumerate(self._credit_limit_row_ids):
            if row_credit_limit_id == credit_limit_id:
                self.credit_limits_table.selectRow(row_index)
                return

    def _selected_credit_limit_id(self) -> int | None:
        row_index = self.credit_limits_table.currentRow()

        if row_index < 0:
            return None

        if row_index >= len(self._credit_limit_row_ids):
            return None

        return self._credit_limit_row_ids[row_index]

    def _selected_credit_limit_is_active(self) -> bool | None:
        row_index = self.credit_limits_table.currentRow()

        if row_index < 0:
            return None

        if row_index >= len(self._credit_limit_row_active):
            return None

        return self._credit_limit_row_active[row_index]

    def _selected_credit_limit_display_name(self) -> str | None:
        row_index = self.credit_limits_table.currentRow()

        if row_index < 0:
            return None

        if row_index >= len(self._credit_limit_row_display_names):
            return None

        return self._credit_limit_row_display_names[row_index]

    def _selected_credit_limit_total_debt(self) -> Decimal | None:
        row_index = self.credit_limits_table.currentRow()

        if row_index < 0:
            return None

        if row_index >= len(self._credit_limit_row_total_debt):
            return None

        return self._credit_limit_row_total_debt[row_index]

    def _selected_credit_limit_transaction_id(self) -> int | None:
        row_index = self.credit_limit_transactions_table.currentRow()

        if row_index < 0:
            return None

        if row_index >= len(self._credit_limit_transaction_row_ids):
            return None

        return self._credit_limit_transaction_row_ids[row_index]

    def _selected_credit_limit_transaction_status(self) -> str | None:
        row_index = self.credit_limit_transactions_table.currentRow()

        if row_index < 0:
            return None

        if row_index >= len(self._credit_limit_transaction_row_status):
            return None

        return self._credit_limit_transaction_row_status[row_index]

    def _restore_credit_card_selection(self, credit_card_id: int) -> None:
        for row_index, row_card_id in enumerate(self._credit_card_row_ids):
            if row_card_id == credit_card_id:
                self.credit_cards_table.selectRow(row_index)
                return

    def _selected_credit_card_id(self) -> int | None:
        row_index = self.credit_cards_table.currentRow()

        if row_index < 0:
            return None

        if row_index >= len(self._credit_card_row_ids):
            return None

        return self._credit_card_row_ids[row_index]

    def _selected_credit_card_is_active(self) -> bool | None:
        row_index = self.credit_cards_table.currentRow()

        if row_index < 0:
            return None

        if row_index >= len(self._credit_card_row_active):
            return None

        return self._credit_card_row_active[row_index]

    def _selected_credit_card_display_name(self) -> str | None:
        row_index = self.credit_cards_table.currentRow()

        if row_index < 0:
            return None

        if row_index >= len(self._credit_card_row_display_names):
            return None

        return self._credit_card_row_display_names[row_index]

    def _selected_credit_card_remaining_debt(self) -> Decimal | None:
        row_index = self.credit_cards_table.currentRow()

        if row_index < 0:
            return None

        if row_index >= len(self._credit_card_row_remaining_debt):
            return None

        return self._credit_card_row_remaining_debt[row_index]

    def _selected_transaction_id(self) -> int | None:
        row_index = self.transactions_table.currentRow()

        if row_index < 0:
            return None

        if row_index >= len(self._transaction_row_ids):
            return None

        return self._transaction_row_ids[row_index]

    def _selected_transaction_status(self) -> str | None:
        row_index = self.transactions_table.currentRow()

        if row_index < 0:
            return None

        if row_index >= len(self._transaction_row_status):
            return None

        return self._transaction_row_status[row_index]

    def _selected_payment_id(self) -> int | None:
        row_index = self.payments_table.currentRow()

        if row_index < 0:
            return None

        if row_index >= len(self._payment_row_ids):
            return None

        return self._payment_row_ids[row_index]

    def _selected_payment_status(self) -> str | None:
        row_index = self.payments_table.currentRow()

        if row_index < 0:
            return None

        if row_index >= len(self._payment_row_status):
            return None

        return self._payment_row_status[row_index]

    def _update_credit_card_actions(self) -> None:
        selected_card_id = self._selected_credit_card_id()
        selected_is_active = self._selected_credit_card_is_active()
        selected_remaining_debt = self._selected_credit_card_remaining_debt()
        has_selection = selected_card_id is not None
        has_payable_debt = selected_remaining_debt is not None and selected_remaining_debt > Decimal("0.00")

        if self.edit_credit_card_button is not None:
            self.edit_credit_card_button.setEnabled(has_selection)

        if self.toggle_credit_card_button is not None:
            self.toggle_credit_card_button.setEnabled(has_selection)

            if selected_is_active is False:
                self.toggle_credit_card_button.setText("Aktifleştir")
                self.toggle_credit_card_button.setObjectName("CreditFacilitiesPrimaryButton")
            else:
                self.toggle_credit_card_button.setText("Pasife Al")
                self.toggle_credit_card_button.setObjectName("CreditFacilitiesWarningButton")

            self.toggle_credit_card_button.style().unpolish(self.toggle_credit_card_button)
            self.toggle_credit_card_button.style().polish(self.toggle_credit_card_button)
            self.toggle_credit_card_button.update()

        if self.transaction_credit_card_button is not None:
            self.transaction_credit_card_button.setEnabled(has_selection and selected_is_active is True)

        if self.payment_credit_card_button is not None:
            self.payment_credit_card_button.setEnabled(
                has_selection and selected_is_active is True and has_payable_debt
            )

        if self.statement_credit_card_button is not None:
            self.statement_credit_card_button.setEnabled(has_selection)

    def _update_credit_limit_actions(self) -> None:
        selected_credit_limit_id = self._selected_credit_limit_id()
        selected_is_active = self._selected_credit_limit_is_active()
        selected_total_debt = self._selected_credit_limit_total_debt()
        has_selection = selected_credit_limit_id is not None
        has_payable_debt = selected_total_debt is not None and selected_total_debt > Decimal("0.00")

        if self.edit_credit_limit_button is not None:
            self.edit_credit_limit_button.setEnabled(has_selection)

        if self.toggle_credit_limit_button is not None:
            self.toggle_credit_limit_button.setEnabled(has_selection)

            if selected_is_active is False:
                self.toggle_credit_limit_button.setText("Aktifleştir")
                self.toggle_credit_limit_button.setObjectName("CreditFacilitiesPrimaryButton")
            else:
                self.toggle_credit_limit_button.setText("Pasife Al")
                self.toggle_credit_limit_button.setObjectName("CreditFacilitiesWarningButton")

            self.toggle_credit_limit_button.style().unpolish(self.toggle_credit_limit_button)
            self.toggle_credit_limit_button.style().polish(self.toggle_credit_limit_button)
            self.toggle_credit_limit_button.update()

        if self.use_credit_limit_button is not None:
            self.use_credit_limit_button.setEnabled(has_selection and selected_is_active is True)

        if self.pay_credit_limit_button is not None:
            self.pay_credit_limit_button.setEnabled(
                has_selection and selected_is_active is True and has_payable_debt
            )

        if self.period_report_credit_limit_button is not None:
            self.period_report_credit_limit_button.setEnabled(has_selection)

    def _update_credit_limit_transaction_actions(self) -> None:
        transaction_id = self._selected_credit_limit_transaction_id()
        transaction_status = self._selected_credit_limit_transaction_status()

        if self.cancel_credit_limit_transaction_button is not None:
            self.cancel_credit_limit_transaction_button.setEnabled(
                transaction_id is not None and transaction_status not in {"CANCELLED"}
            )

    def _update_transaction_actions(self) -> None:
        transaction_id = self._selected_transaction_id()
        transaction_status = self._selected_transaction_status()

        if self.cancel_transaction_button is not None:
            self.cancel_transaction_button.setEnabled(
                transaction_id is not None and transaction_status not in {"CANCELLED", "IN_STATEMENT"}
            )

    def _update_payment_actions(self) -> None:
        payment_id = self._selected_payment_id()
        payment_status = self._selected_payment_status()

        if self.cancel_payment_button is not None:
            self.cancel_payment_button.setEnabled(
                payment_id is not None and payment_status not in {"CANCELLED"}
            )

    def _current_user_id(self) -> int | None:
        if self.current_user is None:
            return None

        user_id = getattr(self.current_user, "id", None)

        if user_id is None:
            return None

        try:
            return int(user_id)
        except (TypeError, ValueError):
            return None

    def _credit_card_display_name(
        self,
        *,
        bank_name: str,
        card_name: str,
        last_four_digits: Any,
    ) -> str:
        digits_text = str(last_four_digits or "").strip()

        if digits_text:
            return f"{bank_name} / {card_name} (*{digits_text})"

        return f"{bank_name} / {card_name}"

    def _build_transaction_payment_status_map(
        self,
        *,
        transactions: list[Any],
        payments: list[Any],
    ) -> dict[int, str]:
        active_payment_total = Decimal("0.00")

        for payment in payments:
            payment_status = str(getattr(payment.status, "value", payment.status) or "").strip().upper()

            if payment_status != "RECORDED":
                continue

            try:
                active_payment_total += Decimal(payment.amount or 0)
            except Exception:
                continue

        remaining_payment_coverage = active_payment_total
        status_by_transaction_id: dict[int, str] = {}

        active_transactions = []

        for transaction in transactions:
            transaction_status = str(
                getattr(transaction.status, "value", transaction.status) or ""
            ).strip().upper()

            if transaction_status not in ACTIVE_TRANSACTION_STATUSES:
                continue

            active_transactions.append(transaction)

        active_transactions.sort(
            key=lambda item: (
                item.transaction_date,
                int(item.id),
            )
        )

        for transaction in active_transactions:
            transaction_id = int(transaction.id)

            try:
                transaction_amount = Decimal(transaction.amount or 0)
            except Exception:
                transaction_amount = Decimal("0.00")

            if transaction_amount <= Decimal("0.00"):
                status_by_transaction_id[transaction_id] = "Borçta"
                continue

            if remaining_payment_coverage >= transaction_amount:
                status_by_transaction_id[transaction_id] = "Ödendi"
                remaining_payment_coverage -= transaction_amount
                continue

            if remaining_payment_coverage > Decimal("0.00"):
                status_by_transaction_id[transaction_id] = "Kısmi Ödendi"
                remaining_payment_coverage = Decimal("0.00")
                continue

            status_by_transaction_id[transaction_id] = "Borçta"

        return status_by_transaction_id

    def _transaction_status_text(self, status: str) -> str:
        status_map = {
            "PENDING": "Borçta",
            "IN_STATEMENT": "Ekstrede",
            "CANCELLED": "İptal",
            "REFUNDED": "İade",
        }

        return status_map.get(str(status or "").strip().upper(), str(status or "-"))

    def _payment_status_text(self, status: str) -> str:
        status_map = {
            "RECORDED": "Kayıtlı",
            "CANCELLED": "İptal",
        }

        return status_map.get(str(status or "").strip().upper(), str(status or "-"))

    def _credit_limit_transaction_type_text(self, value: Any) -> str:
        type_map = {
            "USAGE": "Limit Kullanımı",
            "PAYMENT": "Limit Ödemesi",
            "INTEREST": "Faiz",
            "FEE": "Masraf",
            "ADJUSTMENT": "Düzeltme",
        }

        return type_map.get(str(value or "").strip().upper(), str(value or "-"))

    def _credit_limit_transaction_status_text(self, value: Any) -> str:
        status_map = {
            "ACTIVE": "Aktif",
            "CANCELLED": "İptal",
        }

        return status_map.get(str(value or "").strip().upper(), str(value or "-"))

    def _credit_limit_type_text(self, value: Any) -> str:
        type_map = {
            "KMH": "KMH",
            "LIMITED_DEPOSIT": "Limitli Mevduat",
            "ROTATIVE_LIMIT": "Rotatif Limit",
            "OTHER": "Diğer",
        }

        return type_map.get(str(value or "").strip().upper(), str(value or "-"))

    def _format_money(self, value: Any, currency_code: Any) -> str:
        clean_currency_code = str(currency_code or "").strip().upper()

        if not clean_currency_code:
            return self._format_decimal(value)

        return f"{self._format_decimal(value)} {clean_currency_code}"

    def _format_decimal(self, value: Any) -> str:
        try:
            decimal_value = Decimal(value or 0)
        except Exception:
            return "0,00"

        formatted = f"{decimal_value:,.2f}"
        return formatted.replace(",", "X").replace(".", ",").replace("X", ".")

    def _format_tl(self, value: Any) -> str:
        return f"{self._format_decimal(value)} TL"

    def _format_day(self, value: Any) -> str:
        if value is None:
            return "-"

        return str(value)

    def _format_date(self, value: Any) -> str:
        if value is None:
            return "-"

        try:
            return value.strftime("%d.%m.%Y")
        except Exception:
            return str(value)


__all__ = [
    "CreditFacilitiesPage",
]
