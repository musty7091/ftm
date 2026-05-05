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
        self.selected_settlement: Any | None = None
        self.approved_payloads: dict[int, dict[str, Any]] = {}

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
            "Bekleyen POS yatışlarını listeden kontrol et. "
            "Satırdaki Onayla butonu kaydı onay listesine alır ve pencere açık kalır. "
            "Tutar farklıysa satırı seçip gerçekleşen net tutarı ve fark açıklamasını gir."
        )
        subtitle.setObjectName("MutedText")
        subtitle.setWordWrap(True)

        top_form_layout = QGridLayout()
        top_form_layout.setHorizontalSpacing(12)
        top_form_layout.setVerticalSpacing(8)
        top_form_layout.setColumnStretch(0, 0)
        top_form_layout.setColumnStretch(1, 1)

        realized_date_label = QLabel("Gerçekleşen tarih")
        realized_date_label.setObjectName("MutedText")

        self.realized_date_edit = QDateEdit()
        self.realized_date_edit.setMinimumHeight(38)
        self.realized_date_edit.setCalendarPopup(True)
        self.realized_date_edit.setDisplayFormat("dd.MM.yyyy")
        self.realized_date_edit.setDate(QDate.currentDate())
        self.realized_date_edit.dateChanged.connect(self._refresh_preview)

        top_form_layout.addWidget(realized_date_label, 0, 0)
        top_form_layout.addWidget(self.realized_date_edit, 0, 1)

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
        self.actual_net_amount_input.textChanged.connect(self._refresh_preview)

        reference_no_label = QLabel("Referans no")
        reference_no_label.setObjectName("MutedText")

        self.reference_no_input = QLineEdit()
        self.reference_no_input.setMinimumHeight(38)
        self.reference_no_input.setPlaceholderText("Dekont / referans no")

        description_label = QLabel("Açıklama")
        description_label.setObjectName("MutedText")

        self.description_input = QTextEdit()
        self.description_input.setFixedHeight(62)
        self.description_input.setPlaceholderText("İsteğe bağlı açıklama")

        difference_reason_label = QLabel("Fark açıklaması")
        difference_reason_label.setObjectName("MutedText")

        self.difference_reason_input = QTextEdit()
        self.difference_reason_input.setFixedHeight(62)
        self.difference_reason_input.setPlaceholderText("Tutar farkı varsa açıklama zorunludur.")

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
        self.add_selected_button = QPushButton("Seçiliyi Listeye Al")
        self.apply_button = QPushButton("Onayları Uygula")

        self.cancel_button.setMinimumHeight(40)
        self.add_selected_button.setMinimumHeight(40)
        self.apply_button.setMinimumHeight(40)

        self.cancel_button.clicked.connect(self.reject)
        self.add_selected_button.clicked.connect(self._add_selected_to_approval_list)
        self.apply_button.clicked.connect(self.accept)

        button_layout.addStretch(1)
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.add_selected_button)
        button_layout.addWidget(self.apply_button)

        main_layout.addWidget(title)
        main_layout.addWidget(subtitle)
        main_layout.addLayout(top_form_layout)
        main_layout.addWidget(self.settlement_table, 1)
        main_layout.addLayout(detail_layout)
        main_layout.addWidget(self.preview_label)
        main_layout.addLayout(button_layout)

        if self.planned_settlements:
            self.settlement_table.selectRow(0)
            self._select_settlement_by_row(0)
        else:
            self._set_no_record_state()

        self._refresh_apply_button_state()

    def _build_settlement_table(self) -> None:
        self.settlement_table.setColumnCount(10)
        self.settlement_table.setHorizontalHeaderLabels(
            [
                "ID",
                "POS",
                "Terminal",
                "Banka / Hesap",
                "İşlem",
                "Yatış",
                "Beklenen Net",
                "Gerç. Net",
                "Fark",
                "İşlem",
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
        self.settlement_table.setColumnHidden(0, True)

        header = self.settlement_table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(8, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(9, QHeaderView.Fixed)

        self.settlement_table.setColumnWidth(9, 96)

        self.settlement_table.cellClicked.connect(
            lambda row, column: self._handle_table_cell_clicked(row, column)
        )
        self.settlement_table.itemSelectionChanged.connect(self._handle_table_selection_changed)

        self._fill_settlement_table()

    def _fill_settlement_table(self) -> None:
        self.settlement_by_row = {}
        self.row_by_settlement_id = {}
        self.settlement_table.setRowCount(len(self.planned_settlements))

        for row_index, settlement in enumerate(self.planned_settlements):
            self.settlement_by_row[row_index] = settlement
            self.row_by_settlement_id[settlement.pos_settlement_id] = row_index

            expected_net_text = format_currency_amount(
                settlement.net_amount,
                settlement.currency_code,
            )
            bank_account_text = f"{settlement.bank_name} / {settlement.bank_account_name}"

            values = [
                str(settlement.pos_settlement_id),
                settlement.pos_device_name,
                settlement.terminal_no or "-",
                bank_account_text,
                settlement.transaction_date_text,
                settlement.expected_settlement_date_text,
                expected_net_text,
                expected_net_text,
                format_currency_amount(Decimal("0.00"), settlement.currency_code),
            ]

            for column_index, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setForeground(QColor("#e5e7eb"))

                if column_index in {6, 7, 8}:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                else:
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)

                if column_index in {6, 7, 8}:
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

            approve_button = QPushButton("Onayla")
            approve_button.setFixedWidth(78)
            approve_button.setFixedHeight(24)
            approve_button.setCursor(Qt.PointingHandCursor)
            approve_button.setToolTip("Bu satırdaki POS yatışını beklenen tutarla onay listesine al.")
            approve_button.setStyleSheet(self._row_button_style())
            approve_button.clicked.connect(
                lambda checked=False, selected_row=row_index: self._quick_approve_row(selected_row)
            )

            button_container = QWidget()
            button_layout = QHBoxLayout(button_container)
            button_layout.setContentsMargins(4, 3, 4, 3)
            button_layout.setSpacing(0)
            button_layout.addWidget(approve_button, 0, Qt.AlignCenter)

            self.settlement_table.setCellWidget(row_index, 9, button_container)

        self.settlement_table.resizeRowsToContents()

        for row_index in range(self.settlement_table.rowCount()):
            self.settlement_table.setRowHeight(row_index, 42)

    def _row_button_style(self) -> str:
        return """
            QPushButton {
                background-color: #1e3a8a;
                color: #ffffff;
                border: 1px solid #3b82f6;
                border-radius: 10px;
                padding: 0px;
                margin: 0px;
                font-size: 10px;
                font-weight: 900;
                text-align: center;
            }

            QPushButton:hover {
                background-color: #2563eb;
                border: 1px solid #60a5fa;
                color: #ffffff;
            }

            QPushButton:pressed {
                background-color: #1d4ed8;
                border: 1px solid #bfdbfe;
                color: #ffffff;
            }

            QPushButton:disabled {
                background-color: #14532d;
                color: #bbf7d0;
                border: 1px solid #22c55e;
            }
        """

    def _set_no_record_state(self) -> None:
        self.actual_net_amount_input.setEnabled(False)
        self.reference_no_input.setEnabled(False)
        self.description_input.setEnabled(False)
        self.difference_reason_input.setEnabled(False)
        self.add_selected_button.setEnabled(False)
        self.apply_button.setEnabled(False)
        self.preview_label.setText("Onaylanacak bekleyen POS yatışı bulunmuyor.")

    def _handle_table_cell_clicked(self, row: int, column: int) -> None:
        self._select_settlement_by_row(row)

    def _handle_table_selection_changed(self) -> None:
        selected_indexes = self.settlement_table.selectionModel().selectedRows()

        if not selected_indexes:
            self.selected_settlement = None
            self.preview_label.setText("Seçili kayıt yok.")
            return

        self._select_settlement_by_row(selected_indexes[0].row())

    def _quick_approve_row(self, row_index: int) -> None:
        self._select_settlement_by_row(row_index)

        if self.selected_settlement is None:
            QMessageBox.warning(
                self,
                "Kayıt seçilemedi",
                "Onaylanacak POS yatış kaydı seçilemedi.",
            )
            return

        self.actual_net_amount_input.setText(
            _decimal_to_input_text(self.selected_settlement.net_amount)
        )
        self.difference_reason_input.clear()

        try:
            payload = self._build_payload()
        except Exception as exc:
            QMessageBox.warning(self, "Eksik veya hatalı bilgi", str(exc))
            return

        self._store_payload(payload)
        self._mark_row_as_approved(row_index)
        self._refresh_apply_button_state()
        self._refresh_preview()

    def _add_selected_to_approval_list(self) -> None:
        if self.selected_settlement is None:
            QMessageBox.warning(
                self,
                "Kayıt seçilmedi",
                "Onay listesine alınacak POS yatış kaydı seçilmelidir.",
            )
            return

        selected_row = self._current_selected_row()

        if selected_row is None:
            QMessageBox.warning(
                self,
                "Satır seçilmedi",
                "Onay listesine alınacak satır seçilmelidir.",
            )
            return

        try:
            payload = self._build_payload()
        except Exception as exc:
            QMessageBox.warning(self, "Eksik veya hatalı bilgi", str(exc))
            return

        self._store_payload(payload)
        self._mark_row_as_approved(selected_row)
        self._refresh_apply_button_state()
        self._refresh_preview()

    def _store_payload(self, payload: dict[str, Any]) -> None:
        self.approved_payloads[int(payload["pos_settlement_id"])] = payload

    def _mark_row_as_approved(self, row_index: int) -> None:
        for column_index in range(self.settlement_table.columnCount()):
            item = self.settlement_table.item(row_index, column_index)

            if item is not None:
                item.setBackground(QColor("#103d2d"))
                item.setForeground(QColor("#bbf7d0"))

        widget = self.settlement_table.cellWidget(row_index, 9)

        if widget is not None:
            button = widget.findChild(QPushButton)

            if button is not None:
                button.setText("Alındı")
                button.setEnabled(False)

    def _refresh_apply_button_state(self) -> None:
        approved_count = len(self.approved_payloads)
        self.apply_button.setEnabled(approved_count > 0)

        if approved_count <= 0:
            self.apply_button.setText("Onayları Uygula")
        else:
            self.apply_button.setText(f"Onayları Uygula ({approved_count})")

    def _select_settlement_by_row(self, row_index: int) -> None:
        settlement = self.settlement_by_row.get(row_index)

        if settlement is None:
            self.selected_settlement = None
            self.preview_label.setText("Seçili kayıt bulunamadı.")
            return

        self.selected_settlement = settlement

        self.settlement_table.blockSignals(True)
        self.settlement_table.selectRow(row_index)
        self.settlement_table.blockSignals(False)

        self.actual_net_amount_input.setEnabled(True)
        self.reference_no_input.setEnabled(True)
        self.description_input.setEnabled(True)
        self.difference_reason_input.setEnabled(True)
        self.add_selected_button.setEnabled(True)

        self.actual_net_amount_input.blockSignals(True)
        self.actual_net_amount_input.setText(_decimal_to_input_text(settlement.net_amount))
        self.actual_net_amount_input.blockSignals(False)

        if settlement.reference_no:
            self.reference_no_input.setText(settlement.reference_no)
        else:
            self.reference_no_input.clear()

        if settlement.description:
            self.description_input.setPlainText(settlement.description)
        else:
            self.description_input.clear()

        existing_payload = self.approved_payloads.get(settlement.pos_settlement_id)

        if existing_payload is not None:
            self.actual_net_amount_input.blockSignals(True)
            self.actual_net_amount_input.setText(
                _decimal_to_input_text(existing_payload["actual_net_amount"])
            )
            self.actual_net_amount_input.blockSignals(False)
            self.reference_no_input.setText(existing_payload["reference_no"] or "")
            self.description_input.setPlainText(existing_payload["description"] or "")
            self.difference_reason_input.setPlainText(existing_payload["difference_reason"] or "")
        else:
            self.difference_reason_input.clear()

        self._refresh_preview()

    def _calculate_difference_amount(self) -> Decimal | None:
        if self.selected_settlement is None:
            return None

        actual_net_amount_text = self.actual_net_amount_input.text().strip()

        if not actual_net_amount_text:
            return None

        try:
            actual_net_amount = money(
                actual_net_amount_text,
                field_name="Gerçekleşen net tutar",
            )
        except Exception:
            return None

        difference_amount = money(
            actual_net_amount - Decimal(str(self.selected_settlement.net_amount)),
            field_name="Fark tutarı",
        )

        return difference_amount

    def _refresh_preview(self) -> None:
        if self.selected_settlement is None:
            self.preview_label.setText(
                f"Onay listesi: {len(self.approved_payloads)} kayıt."
            )
            return

        settlement = self.selected_settlement
        difference_amount = self._calculate_difference_amount()

        selected_row = self._current_selected_row()

        if difference_amount is None:
            if selected_row is not None:
                self._update_selected_row_preview(
                    row_index=selected_row,
                    actual_net_text="-",
                    difference_text="-",
                    difference_amount=None,
                )

            self.preview_label.setText(
                f"Seçili: {settlement.pos_device_name} | "
                f"Banka/Hesap: {settlement.bank_name} / {settlement.bank_account_name} | "
                f"Beklenen: {format_currency_amount(settlement.net_amount, settlement.currency_code)} | "
                f"Gerçekleşen: - | Fark: - | "
                f"Onay listesi: {len(self.approved_payloads)} kayıt"
            )
            return

        actual_net_amount = money(
            self.actual_net_amount_input.text().strip(),
            field_name="Gerçekleşen net tutar",
        )

        actual_net_text = format_currency_amount(
            actual_net_amount,
            settlement.currency_code,
        )
        difference_text = format_currency_amount(
            difference_amount,
            settlement.currency_code,
        )

        if selected_row is not None:
            self._update_selected_row_preview(
                row_index=selected_row,
                actual_net_text=actual_net_text,
                difference_text=difference_text,
                difference_amount=difference_amount,
            )

        result_text = "Gerçekleşti" if difference_amount == Decimal("0.00") else "Fark Var"

        self.preview_label.setText(
            f"Seçili: {settlement.pos_device_name} | "
            f"Banka/Hesap: {settlement.bank_name} / {settlement.bank_account_name} | "
            f"Beklenen: {format_currency_amount(settlement.net_amount, settlement.currency_code)} | "
            f"Gerçekleşen: {actual_net_text} | "
            f"Fark: {difference_text} | "
            f"Sonuç: {result_text} | "
            f"Tarih: {_qdate_to_date(self.realized_date_edit.date()).strftime('%d.%m.%Y')} | "
            f"Onay listesi: {len(self.approved_payloads)} kayıt"
        )

    def _current_selected_row(self) -> int | None:
        selected_indexes = self.settlement_table.selectionModel().selectedRows()

        if not selected_indexes:
            return None

        return selected_indexes[0].row()

    def _update_selected_row_preview(
        self,
        *,
        row_index: int,
        actual_net_text: str,
        difference_text: str,
        difference_amount: Decimal | None,
    ) -> None:
        actual_item = self.settlement_table.item(row_index, 7)

        if actual_item is not None:
            actual_item.setText(actual_net_text)

        difference_item = self.settlement_table.item(row_index, 8)

        if difference_item is not None:
            difference_item.setText(difference_text)

            if difference_amount is None:
                difference_item.setForeground(QColor("#e5e7eb"))
            elif difference_amount == Decimal("0.00"):
                difference_item.setForeground(QColor("#a7f3d0"))
            else:
                difference_item.setForeground(QColor("#fbbf24"))

    def _build_payload(self) -> dict[str, Any]:
        if self.selected_settlement is None:
            raise ValueError("Onaylanacak POS yatış kaydı seçilmelidir.")

        settlement = self.selected_settlement

        actual_net_amount = money(
            self.actual_net_amount_input.text().strip(),
            field_name="Gerçekleşen net tutar",
        )

        if actual_net_amount <= Decimal("0.00"):
            raise ValueError("Gerçekleşen net tutar sıfırdan büyük olmalıdır.")

        difference_amount = money(
            actual_net_amount - Decimal(str(settlement.net_amount)),
            field_name="Fark tutarı",
        )

        difference_reason = self.difference_reason_input.toPlainText().strip() or None

        if difference_amount != Decimal("0.00") and not difference_reason:
            raise ValueError("Tutar farkı varsa fark açıklaması zorunludur.")

        return {
            "pos_settlement_id": settlement.pos_settlement_id,
            "realized_settlement_date": _qdate_to_date(self.realized_date_edit.date()),
            "actual_net_amount": actual_net_amount,
            "reference_no": self.reference_no_input.text().strip() or None,
            "description": self.description_input.toPlainText().strip() or None,
            "difference_reason": difference_reason,
        }

    def accept(self) -> None:
        if not self.approved_payloads:
            QMessageBox.warning(
                self,
                "Onay listesi boş",
                "Önce en az bir POS yatışını onay listesine almalısın.",
            )
            return

        super().accept()

    def get_payloads(self) -> list[dict[str, Any]]:
        return list(self.approved_payloads.values())

    def get_payload(self) -> dict[str, Any]:
        payloads = self.get_payloads()

        if not payloads:
            raise ValueError("Onaylanmış POS yatış kaydı bulunmuyor.")

        return payloads[0]