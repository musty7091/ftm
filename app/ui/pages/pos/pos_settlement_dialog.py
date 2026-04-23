from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.ui.pages.banks.bank_dialog_styles import BANK_DIALOG_STYLES
from app.ui.pages.pos.pos_data import format_currency_amount, format_rate_percent
from app.utils.decimal_utils import money


def _qdate_to_date(qdate: QDate) -> date:
    return date(qdate.year(), qdate.month(), qdate.day())


def _normalize_percent_rate_to_ratio(rate_value: Decimal) -> Decimal:
    if rate_value <= Decimal("0.00"):
        return Decimal("0.00")

    if rate_value > Decimal("1.00"):
        return rate_value / Decimal("100")

    return rate_value


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
        self.resize(700, 650)
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
        self.transaction_date_edit.setCalendarPopup(True)
        self.transaction_date_edit.setDisplayFormat("dd.MM.yyyy")
        self.transaction_date_edit.setDate(QDate.currentDate())
        self.transaction_date_edit.dateChanged.connect(self._refresh_preview)
        form_layout.addRow("İşlem tarihi", self.transaction_date_edit)

        self.gross_amount_input = QLineEdit()
        self.gross_amount_input.setMinimumHeight(42)
        self.gross_amount_input.setPlaceholderText("Örn: 125000,00")
        self.gross_amount_input.textChanged.connect(self._refresh_preview)
        form_layout.addRow("Brüt tutar", self.gross_amount_input)

        self.reference_no_input = QLineEdit()
        self.reference_no_input.setMinimumHeight(42)
        self.reference_no_input.setPlaceholderText("Slip / batch / referans no")
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