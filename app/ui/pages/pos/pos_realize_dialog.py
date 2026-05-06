from datetime import date
from decimal import Decimal
from typing import Any

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QDateEdit,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.ui.pages.banks.bank_dialog_styles import BANK_DIALOG_STYLES
from app.ui.pages.pos.pos_data import format_currency_amount
from app.utils.decimal_utils import money


def _qdate_to_date(qdate: QDate) -> date:
    return date(qdate.year(), qdate.month(), qdate.day())


def _decimal_to_input_text(value: Any) -> str:
    return str(value or "0.00").replace(".", ",")


class PosRealizeDialog(QDialog):
    def __init__(
        self,
        *,
        parent: QWidget | None,
        planned_settlements: list[Any],
    ) -> None:
        super().__init__(parent)

        self.planned_settlements = planned_settlements
        self.settlement_by_row: dict[int, Any] = {}
        self.row_by_settlement_id: dict[int, int] = {}
        self.row_edit_values: dict[int, dict[str, str]] = {}
        self.selected_settlement: Any | None = None
        self.selected_row_index: int | None = None
        self.payloads: list[dict[str, Any]] = []

        self._updating_table = False
        self._loading_detail = False

        self.setWindowTitle("Bekleyen POS Yatışlarını Onayla")
        self.resize(1280, 760)
        self.setMinimumSize(1120, 660)
        self.setStyleSheet(BANK_DIALOG_STYLES)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 22, 24, 22)
        main_layout.setSpacing(12)

        title = QLabel("Bekleyen POS Yatışlarını Onayla")
        title.setObjectName("SectionTitle")

        subtitle = QLabel(
            "Satırı seç, gerekiyorsa gerçekleşen net tutarı düzelt. "
            "Onaylanacak satırları tablodaki Seç kutusuyla işaretle. "
            "En alttaki Seçilenleri Onayla butonu işaretli kayıtların tamamını işler."
        )
        subtitle.setObjectName("MutedText")
        subtitle.setWordWrap(True)

        top_layout = QGridLayout()
        top_layout.setHorizontalSpacing(12)
        top_layout.setVerticalSpacing(8)
        top_layout.setColumnStretch(0, 0)
        top_layout.setColumnStretch(1, 1)
        top_layout.setColumnStretch(2, 0)
        top_layout.setColumnStretch(3, 0)

        realized_date_label = QLabel("Gerçekleşen tarih")
        realized_date_label.setObjectName("MutedText")

        self.realized_date_edit = QDateEdit()
        self.realized_date_edit.setMinimumHeight(38)
        self.realized_date_edit.setCalendarPopup(True)
        self.realized_date_edit.setDisplayFormat("dd.MM.yyyy")
        self.realized_date_edit.setDate(QDate.currentDate())
        self.realized_date_edit.dateChanged.connect(self._refresh_preview)

        self.select_all_button = QPushButton("Tümünü Seç")
        self.clear_selection_button = QPushButton("Seçimi Temizle")

        self.select_all_button.setMinimumHeight(38)
        self.clear_selection_button.setMinimumHeight(38)

        self.select_all_button.clicked.connect(self._select_all_rows)
        self.clear_selection_button.clicked.connect(self._clear_all_rows)

        top_layout.addWidget(realized_date_label, 0, 0)
        top_layout.addWidget(self.realized_date_edit, 0, 1)
        top_layout.addWidget(self.select_all_button, 0, 2)
        top_layout.addWidget(self.clear_selection_button, 0, 3)

        self.settlement_table = QTableWidget()
        self._build_settlement_table()

        detail_layout = QGridLayout()
        detail_layout.setHorizontalSpacing(12)
        detail_layout.setVerticalSpacing(8)
        detail_layout.setColumnStretch(0, 0)
        detail_layout.setColumnStretch(1, 1)
        detail_layout.setColumnStretch(2, 0)
        detail_layout.setColumnStretch(3, 1)

        actual_net_amount_label = QLabel("Gerçekleşen net tutar")
        actual_net_amount_label.setObjectName("MutedText")

        self.actual_net_amount_input = QLineEdit()
        self.actual_net_amount_input.setMinimumHeight(38)
        self.actual_net_amount_input.setPlaceholderText("Örn: 98010,00")
        self.actual_net_amount_input.textChanged.connect(self._handle_detail_changed)

        reference_no_label = QLabel("Referans no")
        reference_no_label.setObjectName("MutedText")

        self.reference_no_input = QLineEdit()
        self.reference_no_input.setMinimumHeight(38)
        self.reference_no_input.setPlaceholderText("Dekont / referans no")
        self.reference_no_input.textChanged.connect(self._handle_detail_changed)

        description_label = QLabel("Açıklama")
        description_label.setObjectName("MutedText")

        self.description_input = QTextEdit()
        self.description_input.setFixedHeight(62)
        self.description_input.setPlaceholderText("İsteğe bağlı açıklama")
        self.description_input.textChanged.connect(self._handle_detail_changed)

        difference_reason_label = QLabel("Fark açıklaması")
        difference_reason_label.setObjectName("MutedText")

        self.difference_reason_input = QTextEdit()
        self.difference_reason_input.setFixedHeight(62)
        self.difference_reason_input.setPlaceholderText("Tutar farkı varsa açıklama zorunludur.")
        self.difference_reason_input.textChanged.connect(self._handle_detail_changed)

        detail_layout.addWidget(actual_net_amount_label, 0, 0)
        detail_layout.addWidget(self.actual_net_amount_input, 0, 1)
        detail_layout.addWidget(reference_no_label, 0, 2)
        detail_layout.addWidget(self.reference_no_input, 0, 3)
        detail_layout.addWidget(description_label, 1, 0)
        detail_layout.addWidget(self.description_input, 1, 1)
        detail_layout.addWidget(difference_reason_label, 1, 2)
        detail_layout.addWidget(self.difference_reason_input, 1, 3)

        self.preview_label = QLabel("")
        self.preview_label.setObjectName("MutedText")
        self.preview_label.setWordWrap(True)
        self.preview_label.setMinimumHeight(42)
        self.preview_label.setMaximumHeight(72)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)

        self.cancel_button = QPushButton("Vazgeç")
        self.apply_button = QPushButton("Seçilenleri Onayla")

        self.cancel_button.setMinimumHeight(40)
        self.apply_button.setMinimumHeight(40)

        self.cancel_button.clicked.connect(self.reject)
        self.apply_button.clicked.connect(self.accept)

        button_layout.addStretch(1)
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.apply_button)

        main_layout.addWidget(title)
        main_layout.addWidget(subtitle)
        main_layout.addLayout(top_layout)
        main_layout.addWidget(self.settlement_table, 1)
        main_layout.addLayout(detail_layout)
        main_layout.addWidget(self.preview_label)
        main_layout.addLayout(button_layout)

        if self.planned_settlements:
            self.settlement_table.selectRow(0)
            self._select_settlement_by_row(0)
        else:
            self._set_no_record_state()

        self._refresh_action_state()

    def _build_settlement_table(self) -> None:
        self.settlement_table.setColumnCount(10)
        self.settlement_table.setHorizontalHeaderLabels(
            [
                "Seç",
                "ID",
                "POS",
                "Terminal",
                "Banka / Hesap",
                "İşlem",
                "Yatış",
                "Beklenen Net",
                "Gerç. Net",
                "Fark",
            ]
        )

        self.settlement_table.verticalHeader().setVisible(False)
        self.settlement_table.setAlternatingRowColors(False)
        self.settlement_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.settlement_table.setSelectionMode(QTableWidget.SingleSelection)
        self.settlement_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.settlement_table.setWordWrap(False)
        self.settlement_table.setTextElideMode(Qt.ElideRight)
        self.settlement_table.setMinimumHeight(270)
        self.settlement_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.settlement_table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.settlement_table.setColumnHidden(1, True)

        header = self.settlement_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(8, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(9, QHeaderView.ResizeToContents)

        self.settlement_table.setColumnWidth(0, 54)

        self.settlement_table.cellClicked.connect(
            lambda row, column: self._handle_table_cell_clicked(row, column)
        )
        self.settlement_table.itemSelectionChanged.connect(self._handle_table_selection_changed)
        self.settlement_table.itemChanged.connect(self._handle_table_item_changed)

        self._fill_settlement_table()

    def _fill_settlement_table(self) -> None:
        self._updating_table = True

        try:
            self.settlement_by_row = {}
            self.row_by_settlement_id = {}
            self.row_edit_values = {}
            self.settlement_table.setRowCount(len(self.planned_settlements))

            for row_index, settlement in enumerate(self.planned_settlements):
                self.settlement_by_row[row_index] = settlement
                self.row_by_settlement_id[int(settlement.pos_settlement_id)] = row_index
                self.row_edit_values[int(settlement.pos_settlement_id)] = self._default_edit_values(settlement)

                expected_net_text = format_currency_amount(
                    settlement.net_amount,
                    settlement.currency_code,
                )
                bank_account_text = f"{settlement.bank_name} / {settlement.bank_account_name}"

                select_item = QTableWidgetItem("")
                select_item.setFlags(
                    select_item.flags()
                    | Qt.ItemFlag.ItemIsUserCheckable
                    | Qt.ItemFlag.ItemIsEnabled
                    | Qt.ItemFlag.ItemIsSelectable
                )
                select_item.setCheckState(Qt.CheckState.Unchecked)
                select_item.setTextAlignment(Qt.AlignCenter)
                self.settlement_table.setItem(row_index, 0, select_item)

                values = {
                    1: str(settlement.pos_settlement_id),
                    2: settlement.pos_device_name,
                    3: settlement.terminal_no or "-",
                    4: bank_account_text,
                    5: settlement.transaction_date_text,
                    6: settlement.expected_settlement_date_text,
                    7: expected_net_text,
                    8: expected_net_text,
                    9: format_currency_amount(Decimal("0.00"), settlement.currency_code),
                }

                for column_index, value in values.items():
                    item = QTableWidgetItem(value)
                    item.setForeground(QColor("#e5e7eb"))

                    if column_index in {7, 8, 9}:
                        item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    else:
                        item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)

                    if column_index in {7, 8, 9}:
                        font = QFont()
                        font.setBold(True)
                        item.setFont(font)

                    item.setToolTip(
                        "\n".join(
                            [
                                f"Kayıt ID: {settlement.pos_settlement_id}",
                                f"POS: {settlement.pos_device_name}",
                                f"Terminal: {settlement.terminal_no or '-'}",
                                f"Banka: {settlement.bank_name}",
                                f"Hesap: {settlement.bank_account_name}",
                                f"İşlem Tarihi: {settlement.transaction_date_text}",
                                f"Beklenen Yatış: {settlement.expected_settlement_date_text}",
                                f"Beklenen Net: {expected_net_text}",
                            ]
                        )
                    )

                    self.settlement_table.setItem(row_index, column_index, item)

            self.settlement_table.resizeRowsToContents()

            for row_index in range(self.settlement_table.rowCount()):
                self.settlement_table.setRowHeight(row_index, 40)

        finally:
            self._updating_table = False

    def _default_edit_values(self, settlement: Any) -> dict[str, str]:
        return {
            "actual_net_amount_text": _decimal_to_input_text(settlement.net_amount),
            "reference_no": settlement.reference_no or "",
            "description": settlement.description or "",
            "difference_reason": "",
        }

    def _set_no_record_state(self) -> None:
        self.actual_net_amount_input.setEnabled(False)
        self.reference_no_input.setEnabled(False)
        self.description_input.setEnabled(False)
        self.difference_reason_input.setEnabled(False)
        self.select_all_button.setEnabled(False)
        self.clear_selection_button.setEnabled(False)
        self.apply_button.setEnabled(False)
        self.preview_label.setText("Onaylanacak bekleyen POS yatışı bulunmuyor.")

    def _handle_table_cell_clicked(self, row: int, column: int) -> None:
        self._select_settlement_by_row(row)

    def _handle_table_selection_changed(self) -> None:
        selected_indexes = self.settlement_table.selectionModel().selectedRows()

        if not selected_indexes:
            self.selected_settlement = None
            self.selected_row_index = None
            self.preview_label.setText("Seçili kayıt yok.")
            self._refresh_action_state()
            return

        self._select_settlement_by_row(selected_indexes[0].row())

    def _handle_table_item_changed(self, item: QTableWidgetItem) -> None:
        if self._updating_table:
            return

        if item.column() != 0:
            return

        row_index = item.row()
        self._set_row_visual_state(
            row_index=row_index,
            is_checked=self._is_row_checked(row_index),
        )
        self._refresh_action_state()
        self._refresh_preview()

    def _select_settlement_by_row(self, row_index: int) -> None:
        settlement = self.settlement_by_row.get(row_index)

        if settlement is None:
            self.selected_settlement = None
            self.selected_row_index = None
            self.preview_label.setText("Seçili kayıt bulunamadı.")
            self._refresh_action_state()
            return

        self.selected_settlement = settlement
        self.selected_row_index = row_index

        values = self.row_edit_values.get(
            int(settlement.pos_settlement_id),
            self._default_edit_values(settlement),
        )

        self._loading_detail = True

        try:
            self.actual_net_amount_input.setEnabled(True)
            self.reference_no_input.setEnabled(True)
            self.description_input.setEnabled(True)
            self.difference_reason_input.setEnabled(True)

            self.actual_net_amount_input.setText(values["actual_net_amount_text"])
            self.reference_no_input.setText(values["reference_no"])
            self.description_input.setPlainText(values["description"])
            self.difference_reason_input.setPlainText(values["difference_reason"])

        finally:
            self._loading_detail = False

        self._refresh_preview()
        self._refresh_action_state()

    def _handle_detail_changed(self) -> None:
        if self._loading_detail:
            return

        if self.selected_settlement is None or self.selected_row_index is None:
            return

        settlement_id = int(self.selected_settlement.pos_settlement_id)

        self.row_edit_values[settlement_id] = {
            "actual_net_amount_text": self.actual_net_amount_input.text().strip(),
            "reference_no": self.reference_no_input.text().strip(),
            "description": self.description_input.toPlainText().strip(),
            "difference_reason": self.difference_reason_input.toPlainText().strip(),
        }

        self._set_row_checked(self.selected_row_index, True)
        self._refresh_row_amount_preview(self.selected_row_index, self.selected_settlement)
        self._refresh_action_state()
        self._refresh_preview()

    def _select_all_rows(self) -> None:
        for row_index in range(self.settlement_table.rowCount()):
            self._set_row_checked(row_index, True)

        self._refresh_action_state()
        self._refresh_preview()

    def _clear_all_rows(self) -> None:
        for row_index in range(self.settlement_table.rowCount()):
            self._set_row_checked(row_index, False)

        self._refresh_action_state()
        self._refresh_preview()

    def _set_row_checked(self, row_index: int, checked: bool) -> None:
        item = self.settlement_table.item(row_index, 0)

        if item is None:
            return

        self._updating_table = True

        try:
            item.setCheckState(
                Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
            )
            self._set_row_visual_state(row_index=row_index, is_checked=checked)

        finally:
            self._updating_table = False

    def _is_row_checked(self, row_index: int) -> bool:
        item = self.settlement_table.item(row_index, 0)

        if item is None:
            return False

        return item.checkState() == Qt.CheckState.Checked

    def _checked_row_indexes(self) -> list[int]:
        checked_rows: list[int] = []

        for row_index in range(self.settlement_table.rowCount()):
            if self._is_row_checked(row_index):
                checked_rows.append(row_index)

        return checked_rows

    def _set_row_visual_state(self, *, row_index: int, is_checked: bool) -> None:
        background_color = QColor("#103d2d") if is_checked else QColor("#111827")
        foreground_color = QColor("#bbf7d0") if is_checked else QColor("#e5e7eb")

        self._updating_table = True

        try:
            for column_index in range(self.settlement_table.columnCount()):
                item = self.settlement_table.item(row_index, column_index)

                if item is not None:
                    item.setBackground(background_color)
                    item.setForeground(foreground_color)

        finally:
            self._updating_table = False

    def _refresh_row_amount_preview(self, row_index: int, settlement: Any) -> None:
        values = self.row_edit_values.get(
            int(settlement.pos_settlement_id),
            self._default_edit_values(settlement),
        )

        try:
            actual_net_amount = money(
                values["actual_net_amount_text"],
                field_name="Gerçekleşen net tutar",
            )
        except Exception:
            actual_item = self.settlement_table.item(row_index, 8)
            difference_item = self.settlement_table.item(row_index, 9)

            if actual_item is not None:
                actual_item.setText("-")

            if difference_item is not None:
                difference_item.setText("-")
                difference_item.setForeground(QColor("#fbbf24"))

            return

        difference_amount = money(
            actual_net_amount - Decimal(str(settlement.net_amount)),
            field_name="Fark tutarı",
        )

        actual_item = self.settlement_table.item(row_index, 8)
        difference_item = self.settlement_table.item(row_index, 9)

        if actual_item is not None:
            actual_item.setText(
                format_currency_amount(actual_net_amount, settlement.currency_code)
            )

        if difference_item is not None:
            difference_item.setText(
                format_currency_amount(difference_amount, settlement.currency_code)
            )

            if difference_amount == Decimal("0.00"):
                difference_item.setForeground(QColor("#bbf7d0"))
            else:
                difference_item.setForeground(QColor("#fbbf24"))

    def _refresh_preview(self) -> None:
        checked_count = len(self._checked_row_indexes())

        if self.selected_settlement is None:
            self.preview_label.setText(f"Seçilen kayıt: {checked_count}")
            return

        settlement = self.selected_settlement
        values = self.row_edit_values.get(
            int(settlement.pos_settlement_id),
            self._default_edit_values(settlement),
        )

        try:
            actual_net_amount = money(
                values["actual_net_amount_text"],
                field_name="Gerçekleşen net tutar",
            )
            difference_amount = money(
                actual_net_amount - Decimal(str(settlement.net_amount)),
                field_name="Fark tutarı",
            )
            actual_text = format_currency_amount(actual_net_amount, settlement.currency_code)
            difference_text = format_currency_amount(difference_amount, settlement.currency_code)

        except Exception:
            actual_text = "-"
            difference_text = "-"

        self.preview_label.setText(
            f"Seçili: {settlement.pos_device_name} | "
            f"Beklenen: {format_currency_amount(settlement.net_amount, settlement.currency_code)} | "
            f"Gerçekleşen: {actual_text} | "
            f"Fark: {difference_text} | "
            f"Seçilen kayıt: {checked_count}"
        )

    def _refresh_action_state(self) -> None:
        checked_count = len(self._checked_row_indexes())
        self.apply_button.setEnabled(checked_count > 0)

        if checked_count <= 0:
            self.apply_button.setText("Seçilenleri Onayla")
        else:
            self.apply_button.setText(f"Seçilenleri Onayla ({checked_count})")

    def _build_payload_for_row(self, row_index: int) -> dict[str, Any]:
        settlement = self.settlement_by_row.get(row_index)

        if settlement is None:
            raise ValueError("Satırdaki POS yatış kaydı bulunamadı.")

        values = self.row_edit_values.get(
            int(settlement.pos_settlement_id),
            self._default_edit_values(settlement),
        )

        actual_net_amount = money(
            values["actual_net_amount_text"],
            field_name="Gerçekleşen net tutar",
        )

        if actual_net_amount <= Decimal("0.00"):
            raise ValueError("Gerçekleşen net tutar sıfırdan büyük olmalıdır.")

        difference_amount = money(
            actual_net_amount - Decimal(str(settlement.net_amount)),
            field_name="Fark tutarı",
        )

        difference_reason = values["difference_reason"].strip() or None

        if difference_amount != Decimal("0.00") and not difference_reason:
            raise ValueError("Tutar farkı varsa fark açıklaması zorunludur.")

        return {
            "pos_settlement_id": settlement.pos_settlement_id,
            "realized_settlement_date": _qdate_to_date(self.realized_date_edit.date()),
            "actual_net_amount": actual_net_amount,
            "reference_no": values["reference_no"].strip() or None,
            "description": values["description"].strip() or None,
            "difference_reason": difference_reason,
        }

    def accept(self) -> None:
        checked_rows = self._checked_row_indexes()

        if not checked_rows:
            QMessageBox.warning(
                self,
                "Seçili kayıt yok",
                "Önce onaylanacak POS yatışlarını seçmelisin.",
            )
            return

        payloads: list[dict[str, Any]] = []

        for row_index in checked_rows:
            try:
                payloads.append(self._build_payload_for_row(row_index))
            except Exception as exc:
                self.settlement_table.selectRow(row_index)
                self._select_settlement_by_row(row_index)
                QMessageBox.warning(self, "Eksik veya hatalı bilgi", str(exc))
                return

        self.payloads = payloads
        super().accept()

    def get_payloads(self) -> list[dict[str, Any]]:
        return self.payloads

    def get_payload(self) -> dict[str, Any]:
        payloads = self.get_payloads()

        if not payloads:
            raise ValueError("Onaylanmış POS yatış kaydı bulunmuyor.")

        return payloads[0]