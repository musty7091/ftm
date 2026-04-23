from datetime import date, timedelta
from typing import Any

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QFormLayout,
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

from app.ui.pages.banks.bank_dialog_styles import BANK_DIALOG_STYLES
from app.ui.pages.pos.pos_data import (
    PosSettlementRow,
    build_currency_totals_text,
    format_currency_amount,
    format_rate_percent,
    load_pos_history_data,
    status_text,
)


def _qdate_to_date(qdate: QDate) -> date:
    return date(qdate.year(), qdate.month(), qdate.day())


class PosHistoryDialog(QDialog):
    def __init__(
        self,
        *,
        parent: QWidget | None,
        pos_devices: list[Any],
    ) -> None:
        super().__init__(parent)

        self.pos_devices = pos_devices
        self.bank_options = self._build_bank_options()
        self.current_rows: list[PosSettlementRow] = []
        self.difference_settlement_by_row: dict[int, PosSettlementRow] = {}

        self.setWindowTitle("POS Geçmiş İşlemler / Filtreler")
        self.resize(1380, 860)
        self.setStyleSheet(BANK_DIALOG_STYLES)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 22, 24, 22)
        main_layout.setSpacing(16)

        title = QLabel("POS Geçmiş İşlemler / Filtreler")
        title.setObjectName("SectionTitle")

        subtitle = QLabel(
            "Geçmiş POS kayıtlarını tarih, durum, POS cihazı ve banka bazında filtreleyerek görüntüler."
        )
        subtitle.setObjectName("MutedText")
        subtitle.setWordWrap(True)

        filter_card = QWidget()
        filter_layout = QGridLayout(filter_card)
        filter_layout.setContentsMargins(0, 0, 0, 0)
        filter_layout.setHorizontalSpacing(16)
        filter_layout.setVerticalSpacing(12)

        self.start_date_edit = QDateEdit()
        self.start_date_edit.setMinimumHeight(38)
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDisplayFormat("dd.MM.yyyy")
        self.start_date_edit.setDate(QDate.currentDate().addDays(-30))

        self.end_date_edit = QDateEdit()
        self.end_date_edit.setMinimumHeight(38)
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setDisplayFormat("dd.MM.yyyy")
        self.end_date_edit.setDate(QDate.currentDate())

        self.status_combo = QComboBox()
        self.status_combo.setMinimumHeight(38)
        self.status_combo.addItem("Tümü", "")
        self.status_combo.addItem("Planlandı", "PLANNED")
        self.status_combo.addItem("Gerçekleşti", "REALIZED")
        self.status_combo.addItem("Fark Var", "MISMATCH")
        self.status_combo.addItem("İptal", "CANCELLED")

        self.pos_device_combo = QComboBox()
        self.pos_device_combo.setMinimumHeight(38)
        self.pos_device_combo.addItem("Tüm POS cihazları", None)

        for pos_device in sorted(
            self.pos_devices,
            key=lambda x: (x.bank_name, x.name, x.pos_device_id),
        ):
            self.pos_device_combo.addItem(
                f"{pos_device.name} / {pos_device.bank_name} / {pos_device.bank_account_name}",
                pos_device.pos_device_id,
            )

        self.bank_combo = QComboBox()
        self.bank_combo.setMinimumHeight(38)
        self.bank_combo.addItem("Tüm bankalar", None)

        for bank_id, bank_name in self.bank_options:
            self.bank_combo.addItem(bank_name, bank_id)

        filter_layout.addWidget(QLabel("Başlangıç tarihi"), 0, 0)
        filter_layout.addWidget(self.start_date_edit, 1, 0)

        filter_layout.addWidget(QLabel("Bitiş tarihi"), 0, 1)
        filter_layout.addWidget(self.end_date_edit, 1, 1)

        filter_layout.addWidget(QLabel("Durum"), 0, 2)
        filter_layout.addWidget(self.status_combo, 1, 2)

        filter_layout.addWidget(QLabel("POS cihazı"), 0, 3)
        filter_layout.addWidget(self.pos_device_combo, 1, 3)

        filter_layout.addWidget(QLabel("Banka"), 0, 4)
        filter_layout.addWidget(self.bank_combo, 1, 4)

        button_row = QHBoxLayout()
        button_row.setSpacing(10)

        self.search_button = QPushButton("Filtrele")
        self.search_button.setMinimumHeight(40)
        self.search_button.clicked.connect(self._run_search)

        self.reset_button = QPushButton("Sıfırla")
        self.reset_button.setMinimumHeight(40)
        self.reset_button.clicked.connect(self._reset_filters)

        self.close_button = QPushButton("Kapat")
        self.close_button.setMinimumHeight(40)
        self.close_button.clicked.connect(self.reject)

        button_row.addStretch(1)
        button_row.addWidget(self.reset_button)
        button_row.addWidget(self.search_button)
        button_row.addWidget(self.close_button)

        self.summary_label = QLabel("")
        self.summary_label.setObjectName("MutedText")
        self.summary_label.setWordWrap(True)

        self.table = QTableWidget()
        self.table.setColumnCount(13)
        self.table.setHorizontalHeaderLabels(
            [
                "ID",
                "POS",
                "Terminal",
                "Banka",
                "Hesap",
                "İşlem Tarihi",
                "Beklenen",
                "Gerçekleşen",
                "Brüt",
                "Komisyon",
                "Net",
                "Durum",
                "Fark",
            ]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(12, QHeaderView.Fixed)
        self.table.setColumnWidth(12, 72)
        self.table.setMinimumHeight(520)
        self.table.cellClicked.connect(self._handle_table_cell_clicked)

        main_layout.addWidget(title)
        main_layout.addWidget(subtitle)
        main_layout.addWidget(filter_card)
        main_layout.addLayout(button_row)
        main_layout.addWidget(self.summary_label)
        main_layout.addWidget(self.table, 1)

        self._run_search()

    def _build_bank_options(self) -> list[tuple[int, str]]:
        unique_banks: dict[int, str] = {}

        for pos_device in self.pos_devices:
            if pos_device.bank_id not in unique_banks:
                unique_banks[pos_device.bank_id] = pos_device.bank_name

        return sorted(unique_banks.items(), key=lambda item: item[1])

    def _reset_filters(self) -> None:
        self.start_date_edit.setDate(QDate.currentDate().addDays(-30))
        self.end_date_edit.setDate(QDate.currentDate())
        self.status_combo.setCurrentIndex(0)
        self.pos_device_combo.setCurrentIndex(0)
        self.bank_combo.setCurrentIndex(0)
        self._run_search()

    def _run_search(self) -> None:
        start_date = _qdate_to_date(self.start_date_edit.date())
        end_date = _qdate_to_date(self.end_date_edit.date())

        if start_date > end_date:
            QMessageBox.warning(
                self,
                "Hatalı tarih aralığı",
                "Başlangıç tarihi bitiş tarihinden büyük olamaz.",
            )
            return

        history_data = load_pos_history_data(
            start_date=start_date,
            end_date=end_date,
            status=str(self.status_combo.currentData() or "").strip() or None,
            pos_device_id=self.pos_device_combo.currentData(),
            bank_id=self.bank_combo.currentData(),
            limit=2000,
        )

        if history_data.error_message:
            QMessageBox.warning(
                self,
                "Geçmiş kayıtlar okunamadı",
                history_data.error_message,
            )
            return

        self.current_rows = history_data.pos_settlements
        self._fill_table(self.current_rows)

        summary_lines = [
            f"Bulunan kayıt: {history_data.total_count}",
            f"Net toplam: {build_currency_totals_text(history_data.currency_totals)}",
        ]
        self.summary_label.setText("\n".join(summary_lines))

    def _fill_table(self, rows: list[PosSettlementRow]) -> None:
        self.difference_settlement_by_row = {}
        self.table.setRowCount(len(rows))

        for row_index, settlement in enumerate(rows):
            commission_text = (
                f"{format_currency_amount(settlement.commission_amount, settlement.currency_code)} "
                f"({format_rate_percent(settlement.commission_rate)})"
            )

            realized_text = (
                settlement.realized_settlement_date_text
                if settlement.realized_settlement_date_text
                else "-"
            )

            values = [
                str(settlement.pos_settlement_id),
                settlement.pos_device_name,
                settlement.terminal_no or "-",
                settlement.bank_name,
                settlement.bank_account_name,
                settlement.transaction_date_text,
                settlement.expected_settlement_date_text,
                realized_text,
                format_currency_amount(settlement.gross_amount, settlement.currency_code),
                commission_text,
                format_currency_amount(
                    settlement.actual_net_amount
                    if settlement.actual_net_amount is not None
                    else settlement.net_amount,
                    settlement.currency_code,
                ),
                status_text(settlement.status),
            ]

            for column_index, value in enumerate(values):
                item = QTableWidgetItem(value)

                if settlement.status == "CANCELLED":
                    item.setForeground(QColor("#64748b"))
                elif settlement.status == "MISMATCH":
                    item.setForeground(QColor("#fbbf24"))
                else:
                    item.setForeground(QColor("#e5e7eb"))

                if column_index in {8, 9, 10}:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                else:
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)

                if column_index in {10, 11}:
                    font = QFont()
                    font.setBold(True)
                    item.setFont(font)

                self.table.setItem(row_index, column_index, item)

            self._set_difference_cell(
                row_index=row_index,
                settlement=settlement,
            )

        self.table.resizeRowsToContents()

    def _set_difference_cell(
        self,
        *,
        row_index: int,
        settlement: PosSettlementRow,
    ) -> None:
        if settlement.status != "MISMATCH":
            item = QTableWidgetItem("-")
            item.setForeground(QColor("#64748b"))
            item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row_index, 12, item)
            return

        self.difference_settlement_by_row[row_index] = settlement

        item = QTableWidgetItem("Detay")
        item.setToolTip("Fark detayını göster")
        item.setTextAlignment(Qt.AlignCenter)

        font = QFont()
        font.setBold(True)
        font.setUnderline(True)
        item.setFont(font)

        item.setForeground(QColor("#38bdf8"))
        self.table.setItem(row_index, 12, item)

    def _handle_table_cell_clicked(self, row: int, column: int) -> None:
        if column != 12:
            return

        settlement = self.difference_settlement_by_row.get(row)

        if settlement is None:
            return

        self._show_difference_detail(settlement)

    def _show_difference_detail(self, settlement: PosSettlementRow) -> None:
        expected_net_amount_text = format_currency_amount(
            settlement.net_amount,
            settlement.currency_code,
        )

        actual_net_source = (
            settlement.actual_net_amount
            if settlement.actual_net_amount is not None
            else settlement.net_amount
        )

        actual_net_amount_text = format_currency_amount(
            actual_net_source,
            settlement.currency_code,
        )

        difference_amount_text = format_currency_amount(
            settlement.difference_amount,
            settlement.currency_code,
        )

        difference_reason = (
            settlement.difference_reason.strip()
            if settlement.difference_reason
            else "Fark açıklaması girilmemiş."
        )

        detail_text = (
            f"POS: {settlement.pos_device_name}\n"
            f"Terminal: {settlement.terminal_no or '-'}\n"
            f"Banka: {settlement.bank_name}\n"
            f"Hesap: {settlement.bank_account_name}\n\n"
            f"İşlem Tarihi: {settlement.transaction_date_text}\n"
            f"Beklenen Yatış Tarihi: {settlement.expected_settlement_date_text}\n"
            f"Gerçekleşen Yatış Tarihi: {settlement.realized_settlement_date_text or '-'}\n\n"
            f"Beklenen Net: {expected_net_amount_text}\n"
            f"Gerçekleşen Net: {actual_net_amount_text}\n"
            f"Fark: {difference_amount_text}\n\n"
            f"Açıklama:\n{difference_reason}"
        )

        QMessageBox.information(
            self,
            f"POS Fark Detayı - Kayıt ID: {settlement.pos_settlement_id}",
            detail_text,
        )