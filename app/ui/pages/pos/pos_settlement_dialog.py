from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from PySide6.QtCore import QDate, QEvent, Qt
from PySide6.QtGui import QColor, QFont, QKeyEvent
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QFormLayout,
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
from app.ui.pages.pos.pos_data import format_currency_amount, format_rate_percent
from app.utils.decimal_utils import money


TURKISH_MONTH_NAMES = {
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


def _qdate_to_date(qdate: QDate) -> date:
    return date(qdate.year(), qdate.month(), qdate.day())


def _normalize_percent_rate_to_ratio(rate_value: Decimal) -> Decimal:
    if rate_value <= Decimal("0.00"):
        return Decimal("0.00")

    if rate_value > Decimal("1.00"):
        return rate_value / Decimal("100")

    return rate_value


class MonthCalendarDialog(QDialog):
    def __init__(
        self,
        *,
        parent: QWidget | None,
        selected_date: QDate,
        title_text: str,
    ) -> None:
        super().__init__(parent)

        self.selected_date = selected_date
        self.display_year = selected_date.year()
        self.display_month = selected_date.month()

        self.setWindowTitle(title_text)
        self.resize(460, 460)
        self.setMinimumSize(430, 430)
        self.setStyleSheet(BANK_DIALOG_STYLES)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 18, 18, 18)
        main_layout.setSpacing(14)

        title = QLabel(title_text)
        title.setObjectName("SectionTitle")

        navigation_layout = QHBoxLayout()
        navigation_layout.setSpacing(10)

        self.previous_month_button = QPushButton("‹")
        self.next_month_button = QPushButton("›")
        self.month_year_label = QLabel("")
        self.month_year_label.setAlignment(Qt.AlignCenter)
        self.month_year_label.setObjectName("SectionTitle")

        self.previous_month_button.setFixedSize(42, 34)
        self.next_month_button.setFixedSize(42, 34)

        self.previous_month_button.setDefault(False)
        self.previous_month_button.setAutoDefault(False)
        self.next_month_button.setDefault(False)
        self.next_month_button.setAutoDefault(False)

        self.previous_month_button.clicked.connect(self._go_previous_month)
        self.next_month_button.clicked.connect(self._go_next_month)

        navigation_layout.addWidget(self.previous_month_button)
        navigation_layout.addStretch(1)
        navigation_layout.addWidget(self.month_year_label)
        navigation_layout.addStretch(1)
        navigation_layout.addWidget(self.next_month_button)

        self.calendar_table = QTableWidget()
        self.calendar_table.setColumnCount(8)
        self.calendar_table.setRowCount(6)
        self.calendar_table.setHorizontalHeaderLabels(
            ["Hf", "Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]
        )
        self.calendar_table.verticalHeader().setVisible(False)
        self.calendar_table.setAlternatingRowColors(False)
        self.calendar_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.calendar_table.setSelectionMode(QTableWidget.NoSelection)
        self.calendar_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.calendar_table.setWordWrap(False)
        self.calendar_table.setMinimumHeight(268)
        self.calendar_table.setShowGrid(True)
        self.calendar_table.cellClicked.connect(self._handle_calendar_cell_clicked)

        horizontal_header = self.calendar_table.horizontalHeader()
        horizontal_header.setSectionResizeMode(QHeaderView.Fixed)
        horizontal_header.setDefaultAlignment(Qt.AlignCenter)

        self.calendar_table.setColumnWidth(0, 46)

        for column_index in range(1, 8):
            self.calendar_table.setColumnWidth(column_index, 52)

        for row_index in range(self.calendar_table.rowCount()):
            self.calendar_table.setRowHeight(row_index, 38)

        self.selected_date_label = QLabel("")
        self.selected_date_label.setObjectName("MutedText")
        self.selected_date_label.setMinimumHeight(32)
        self.selected_date_label.setStyleSheet(
            """
            QLabel {
                background-color: #13243a;
                color: #bfdbfe;
                border: 1px solid #2563eb;
                border-radius: 10px;
                padding: 7px 10px;
                font-weight: 700;
            }
            """
        )

        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)

        self.cancel_button = QPushButton("Vazgeç")
        self.select_button = QPushButton("Seç")

        self.cancel_button.setMinimumHeight(38)
        self.select_button.setMinimumHeight(38)

        self.cancel_button.setDefault(False)
        self.cancel_button.setAutoDefault(False)
        self.select_button.setDefault(True)
        self.select_button.setAutoDefault(True)

        self.cancel_button.clicked.connect(self.reject)
        self.select_button.clicked.connect(self.accept)

        button_layout.addStretch(1)
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.select_button)

        main_layout.addWidget(title)
        main_layout.addLayout(navigation_layout)
        main_layout.addWidget(self.calendar_table, 1)
        main_layout.addWidget(self.selected_date_label)
        main_layout.addLayout(button_layout)

        self._render_calendar()

    def get_selected_date(self) -> QDate:
        return self.selected_date

    def _go_previous_month(self) -> None:
        if self.display_month == 1:
            self.display_month = 12
            self.display_year -= 1
        else:
            self.display_month -= 1

        self._move_selected_date_into_displayed_month()
        self._render_calendar()

    def _go_next_month(self) -> None:
        if self.display_month == 12:
            self.display_month = 1
            self.display_year += 1
        else:
            self.display_month += 1

        self._move_selected_date_into_displayed_month()
        self._render_calendar()

    def _move_selected_date_into_displayed_month(self) -> None:
        last_day = monthrange(self.display_year, self.display_month)[1]
        safe_day = min(self.selected_date.day(), last_day)

        self.selected_date = QDate(
            self.display_year,
            self.display_month,
            safe_day,
        )

    def _render_calendar(self) -> None:
        self.month_year_label.setText(
            f"{TURKISH_MONTH_NAMES[self.display_month]} {self.display_year}"
        )
        self.selected_date_label.setText(
            f"Seçilen tarih: {self.selected_date.toString('dd.MM.yyyy')}"
        )

        first_day = date(self.display_year, self.display_month, 1)
        first_day_weekday = first_day.weekday()
        grid_start_date = first_day - timedelta(days=first_day_weekday)
        today = QDate.currentDate()

        for row_index in range(6):
            week_start_date = grid_start_date + timedelta(days=row_index * 7)
            iso_week_number = week_start_date.isocalendar().week

            week_item = QTableWidgetItem(str(iso_week_number))
            week_item.setTextAlignment(Qt.AlignCenter)
            week_item.setForeground(QColor("#93c5fd"))
            week_item.setBackground(QColor("#0f172a"))

            week_font = QFont()
            week_font.setBold(True)
            week_item.setFont(week_font)

            week_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.calendar_table.setItem(row_index, 0, week_item)

            for day_column_index in range(7):
                table_column_index = day_column_index + 1
                current_date = week_start_date + timedelta(days=day_column_index)

                item = QTableWidgetItem("")
                item.setTextAlignment(Qt.AlignCenter)
                item.setBackground(QColor("#0f172a"))
                item.setForeground(QColor("#64748b"))
                item.setFlags(Qt.ItemFlag.ItemIsEnabled)

                if current_date.month == self.display_month:
                    current_qdate = QDate(
                        current_date.year,
                        current_date.month,
                        current_date.day,
                    )

                    item.setText(str(current_date.day))
                    item.setData(Qt.ItemDataRole.UserRole, current_qdate)
                    item.setFlags(
                        Qt.ItemFlag.ItemIsEnabled
                        | Qt.ItemFlag.ItemIsSelectable
                    )

                    if day_column_index in {5, 6}:
                        item.setForeground(QColor("#ef4444"))
                    else:
                        item.setForeground(QColor("#ffffff"))

                    if current_qdate == today:
                        item.setBackground(QColor("#13243a"))
                        item.setForeground(QColor("#bfdbfe"))

                        today_font = QFont()
                        today_font.setBold(True)
                        item.setFont(today_font)

                    if current_qdate == self.selected_date:
                        item.setBackground(QColor("#2563eb"))
                        item.setForeground(QColor("#ffffff"))

                        selected_font = QFont()
                        selected_font.setBold(True)
                        item.setFont(selected_font)

                self.calendar_table.setItem(
                    row_index,
                    table_column_index,
                    item,
                )

    def _handle_calendar_cell_clicked(
        self,
        row_index: int,
        column_index: int,
    ) -> None:
        if column_index == 0:
            return

        item = self.calendar_table.item(row_index, column_index)

        if item is None:
            return

        selected_date = item.data(Qt.ItemDataRole.UserRole)

        if not isinstance(selected_date, QDate):
            return

        if not selected_date.isValid():
            return

        self.selected_date = selected_date
        self._render_calendar()


class PosSettlementDialog(QDialog):
    def __init__(
        self,
        *,
        parent: QWidget | None,
        pos_devices: list[Any],
    ) -> None:
        super().__init__(parent)

        self.pos_devices = pos_devices
        self.pos_device_lookup = {
            pos_device.pos_device_id: pos_device
            for pos_device in self.pos_devices
        }
        self.payload: dict[str, Any] | None = None

        self.setWindowTitle("POS Yatış Kaydı Oluştur")
        self.resize(760, 650)
        self.setStyleSheet(BANK_DIALOG_STYLES)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 22, 24, 22)
        main_layout.setSpacing(16)

        title = QLabel("POS Yatış Kaydı Oluştur")
        title.setObjectName("SectionTitle")

        subtitle = QLabel(
            "Seçilen POS cihazı için yeni bir planlanan POS yatış kaydı oluşturur. "
            "Komisyon ve net tutar otomatik hesaplanır."
        )
        subtitle.setObjectName("MutedText")
        subtitle.setWordWrap(True)

        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        form_layout.setFormAlignment(Qt.AlignTop)
        form_layout.setHorizontalSpacing(18)
        form_layout.setVerticalSpacing(14)

        self.pos_device_combo = QComboBox()
        self.pos_device_combo.setMinimumHeight(38)
        self._fill_pos_device_combo()
        self.pos_device_combo.currentIndexChanged.connect(self._refresh_preview)
        form_layout.addRow("POS cihazı", self.pos_device_combo)

        self.transaction_date_edit = QDateEdit()
        self.transaction_date_edit.setMinimumHeight(38)
        self.transaction_date_edit.setCalendarPopup(False)
        self.transaction_date_edit.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.transaction_date_edit.setDisplayFormat("dd.MM.yyyy")
        self.transaction_date_edit.setDate(QDate.currentDate())
        self.transaction_date_edit.dateChanged.connect(self._refresh_preview)

        self.today_button = QPushButton("Bugün")
        self.today_button.setMinimumHeight(38)
        self.today_button.setDefault(False)
        self.today_button.setAutoDefault(False)
        self.today_button.clicked.connect(self._set_transaction_date_today)

        self.calendar_button = QPushButton("📅 Takvim")
        self.calendar_button.setMinimumHeight(38)
        self.calendar_button.setDefault(False)
        self.calendar_button.setAutoDefault(False)
        self.calendar_button.clicked.connect(self._open_transaction_date_calendar)

        date_row = QWidget()
        date_row_layout = QHBoxLayout(date_row)
        date_row_layout.setContentsMargins(0, 0, 0, 0)
        date_row_layout.setSpacing(10)
        date_row_layout.addWidget(self.transaction_date_edit, 1)
        date_row_layout.addWidget(self.today_button, 0)
        date_row_layout.addWidget(self.calendar_button, 0)

        form_layout.addRow("İşlem tarihi", date_row)

        self.gross_amount_input = QLineEdit()
        self.gross_amount_input.setMinimumHeight(42)
        self.gross_amount_input.setPlaceholderText("Örn: 125000,00")
        self.gross_amount_input.textChanged.connect(self._refresh_preview)
        self.gross_amount_input.returnPressed.connect(self.accept)
        form_layout.addRow("Brüt tutar", self.gross_amount_input)

        self.reference_no_input = QLineEdit()
        self.reference_no_input.setMinimumHeight(42)
        self.reference_no_input.setPlaceholderText("Slip / batch / referans no")
        self.reference_no_input.returnPressed.connect(self.accept)
        form_layout.addRow("Referans no", self.reference_no_input)

        self.description_input = QTextEdit()
        self.description_input.setFixedHeight(100)
        self.description_input.setPlaceholderText("İsteğe bağlı açıklama")
        form_layout.addRow("Açıklama", self.description_input)

        self.preview_label = QLabel("")
        self.preview_label.setObjectName("MutedText")
        self.preview_label.setWordWrap(True)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)

        self.cancel_button = QPushButton("Vazgeç")
        self.save_button = QPushButton("Kaydet")

        self.cancel_button.setMinimumHeight(40)
        self.save_button.setMinimumHeight(40)

        self.cancel_button.setDefault(False)
        self.cancel_button.setAutoDefault(False)

        self.save_button.setDefault(True)
        self.save_button.setAutoDefault(True)

        self.cancel_button.clicked.connect(self.reject)
        self.save_button.clicked.connect(self.accept)

        button_layout.addStretch(1)
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.save_button)

        main_layout.addWidget(title)
        main_layout.addWidget(subtitle)
        main_layout.addSpacing(4)
        main_layout.addLayout(form_layout)
        main_layout.addWidget(self.preview_label)
        main_layout.addStretch(1)
        main_layout.addLayout(button_layout)

        self._install_enter_shortcuts()
        self._refresh_preview()

    def _install_enter_shortcuts(self) -> None:
        self.pos_device_combo.installEventFilter(self)
        self.transaction_date_edit.installEventFilter(self)
        self.gross_amount_input.installEventFilter(self)
        self.reference_no_input.installEventFilter(self)
        self.description_input.installEventFilter(self)

    def eventFilter(self, watched: Any, event: Any) -> bool:
        if event.type() == QEvent.Type.KeyPress and isinstance(event, QKeyEvent):
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                if watched is self.description_input:
                    if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                        self.accept()
                        return True

                    return False

                self.accept()
                return True

        return super().eventFilter(watched, event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            focused_widget = self.focusWidget()

            if isinstance(focused_widget, QTextEdit):
                if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                    self.accept()
                    return

                super().keyPressEvent(event)
                return

            self.accept()
            return

        super().keyPressEvent(event)

    def _set_transaction_date_today(self) -> None:
        self.transaction_date_edit.setDate(QDate.currentDate())
        self._refresh_preview()

    def _open_transaction_date_calendar(self) -> None:
        dialog = MonthCalendarDialog(
            parent=self,
            selected_date=self.transaction_date_edit.date(),
            title_text="İşlem Tarihi Seç",
        )

        if dialog.exec() == QDialog.Accepted:
            self.transaction_date_edit.setDate(dialog.get_selected_date())
            self._refresh_preview()

    def _fill_pos_device_combo(self) -> None:
        self.pos_device_combo.clear()

        for pos_device in self.pos_devices:
            text = (
                f"{pos_device.name} / "
                f"{pos_device.bank_name} - {pos_device.bank_account_name} / "
                f"{pos_device.currency_code} / "
                f"Terminal: {pos_device.terminal_no or '-'}"
            )
            self.pos_device_combo.addItem(text, pos_device.pos_device_id)

    def _selected_pos_device(self) -> Any:
        pos_device_id = self.pos_device_combo.currentData()

        try:
            normalized_pos_device_id = int(pos_device_id)
        except (TypeError, ValueError) as exc:
            raise ValueError("Geçerli bir POS cihazı seçilmelidir.") from exc

        pos_device = self.pos_device_lookup.get(normalized_pos_device_id)

        if pos_device is None:
            raise ValueError("Seçilen POS cihazı bulunamadı.")

        return pos_device

    def _calculate_preview_values(self) -> tuple[Any, Any] | tuple[None, None]:
        pos_device = self._selected_pos_device()
        gross_amount_text = self.gross_amount_input.text().strip()

        if not gross_amount_text:
            return None, None

        try:
            gross_amount = money(gross_amount_text, field_name="POS brüt tutarı")
        except Exception:
            return None, None

        normalized_ratio = _normalize_percent_rate_to_ratio(
            Decimal(str(pos_device.commission_rate))
        )

        commission_amount = money(
            gross_amount * normalized_ratio,
            field_name="POS komisyon tutarı",
        )

        net_amount = money(
            gross_amount - commission_amount,
            field_name="POS net tutarı",
        )

        return commission_amount, net_amount

    def _refresh_preview(self) -> None:
        try:
            pos_device = self._selected_pos_device()
        except Exception:
            self.preview_label.setText("Geçerli bir POS cihazı seçilmelidir.")
            return

        transaction_date = _qdate_to_date(self.transaction_date_edit.date())
        expected_settlement_date = transaction_date + timedelta(
            days=int(pos_device.settlement_delay_days or 0)
        )

        commission_amount, net_amount = self._calculate_preview_values()

        preview_lines = [
            f"Banka: {pos_device.bank_name}",
            f"Hesap: {pos_device.bank_account_name}",
            f"Para Birimi: {pos_device.currency_code}",
            f"Komisyon Oranı: {format_rate_percent(pos_device.commission_rate)}",
            f"Valör Gün: {pos_device.settlement_delay_days}",
            f"Beklenen Yatış Tarihi: {expected_settlement_date.strftime('%d.%m.%Y')}",
        ]

        if commission_amount is not None and net_amount is not None:
            preview_lines.append(
                f"Tahmini Komisyon: {format_currency_amount(commission_amount, pos_device.currency_code)}"
            )
            preview_lines.append(
                f"Tahmini Net: {format_currency_amount(net_amount, pos_device.currency_code)}"
            )
        else:
            preview_lines.append("Tahmini Komisyon: -")
            preview_lines.append("Tahmini Net: -")

        self.preview_label.setText("\n".join(preview_lines))

    def _build_payload(self) -> dict[str, Any]:
        pos_device = self._selected_pos_device()

        gross_amount_text = self.gross_amount_input.text().strip()
        cleaned_gross_amount = money(gross_amount_text, field_name="POS brüt tutarı")

        if cleaned_gross_amount <= Decimal("0.00"):
            raise ValueError("POS brüt tutarı sıfırdan büyük olmalıdır.")

        return {
            "pos_device_id": pos_device.pos_device_id,
            "transaction_date": _qdate_to_date(self.transaction_date_edit.date()),
            "gross_amount": cleaned_gross_amount,
            "reference_no": self.reference_no_input.text().strip() or None,
            "description": self.description_input.toPlainText().strip() or None,
        }

    def accept(self) -> None:
        try:
            self.payload = self._build_payload()
        except Exception as exc:
            QMessageBox.warning(self, "Eksik veya hatalı bilgi", str(exc))
            return

        super().accept()

    def get_payload(self) -> dict[str, Any]:
        if self.payload is None:
            self.payload = self._build_payload()

        return self.payload