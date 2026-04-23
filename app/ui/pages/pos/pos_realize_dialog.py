from datetime import date
from decimal import Decimal
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
from app.ui.pages.pos.pos_data import format_currency_amount
from app.utils.decimal_utils import money


def _qdate_to_date(qdate: QDate) -> date:
    return date(qdate.year(), qdate.month(), qdate.day())


class PosRealizeDialog(QDialog):
    def __init__(
        self,
        *,
        parent: QWidget | None,
        planned_settlements: list[Any],
    ) -> None:
        super().__init__(parent)

        self.planned_settlements = planned_settlements
        self.settlement_lookup = {
            settlement.pos_settlement_id: settlement
            for settlement in self.planned_settlements
        }
        self.payload: dict[str, Any] | None = None

        self.setWindowTitle("POS Yatışını Gerçekleştir")
        self.resize(720, 680)
        self.setStyleSheet(BANK_DIALOG_STYLES)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 22, 24, 22)
        main_layout.setSpacing(16)

        title = QLabel("POS Yatışını Gerçekleştir")
        title.setObjectName("SectionTitle")

        subtitle = QLabel(
            "Planlanan POS yatış kaydını gerçekleşen banka girişine dönüştürür. "
            "Gerçekleşen net tutar beklenenden farklıysa kayıt fark durumuna geçer."
        )
        subtitle.setObjectName("MutedText")
        subtitle.setWordWrap(True)

        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        form_layout.setFormAlignment(Qt.AlignTop)
        form_layout.setHorizontalSpacing(18)
        form_layout.setVerticalSpacing(14)

        self.settlement_combo = QComboBox()
        self.settlement_combo.setMinimumHeight(38)
        self._fill_settlement_combo()
        self.settlement_combo.currentIndexChanged.connect(self._on_settlement_changed)
        form_layout.addRow("Planlanan kayıt", self.settlement_combo)

        self.realized_date_edit = QDateEdit()
        self.realized_date_edit.setMinimumHeight(38)
        self.realized_date_edit.setCalendarPopup(True)
        self.realized_date_edit.setDisplayFormat("dd.MM.yyyy")
        self.realized_date_edit.setDate(QDate.currentDate())
        self.realized_date_edit.dateChanged.connect(self._refresh_preview)
        form_layout.addRow("Gerçekleşen tarih", self.realized_date_edit)

        self.actual_net_amount_input = QLineEdit()
        self.actual_net_amount_input.setMinimumHeight(42)
        self.actual_net_amount_input.setPlaceholderText("Örn: 98010,00")
        self.actual_net_amount_input.textChanged.connect(self._refresh_preview)
        form_layout.addRow("Gerçekleşen net tutar", self.actual_net_amount_input)

        self.reference_no_input = QLineEdit()
        self.reference_no_input.setMinimumHeight(42)
        self.reference_no_input.setPlaceholderText("Dekont / referans no")
        form_layout.addRow("Referans no", self.reference_no_input)

        self.description_input = QTextEdit()
        self.description_input.setFixedHeight(90)
        self.description_input.setPlaceholderText("İsteğe bağlı açıklama")
        form_layout.addRow("Açıklama", self.description_input)

        self.difference_reason_input = QTextEdit()
        self.difference_reason_input.setFixedHeight(110)
        self.difference_reason_input.setPlaceholderText("Tutar farkı varsa açıklama yazın.")
        form_layout.addRow("Fark açıklaması", self.difference_reason_input)

        self.preview_label = QLabel("")
        self.preview_label.setObjectName("MutedText")
        self.preview_label.setWordWrap(True)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)

        self.cancel_button = QPushButton("Vazgeç")
        self.save_button = QPushButton("Uygula")

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

        self._on_settlement_changed()

    def _fill_settlement_combo(self) -> None:
        self.settlement_combo.clear()

        for settlement in self.planned_settlements:
            text = (
                f"#{settlement.pos_settlement_id} / "
                f"{settlement.pos_device_name} / "
                f"{settlement.bank_name} / "
                f"Beklenen Net: {format_currency_amount(settlement.net_amount, settlement.currency_code)} / "
                f"Beklenen: {settlement.expected_settlement_date_text}"
            )
            self.settlement_combo.addItem(text, settlement.pos_settlement_id)

    def _selected_settlement(self) -> Any:
        settlement_id = self.settlement_combo.currentData()

        try:
            normalized_settlement_id = int(settlement_id)
        except (TypeError, ValueError) as exc:
            raise ValueError("Geçerli bir planlanan kayıt seçilmelidir.") from exc

        settlement = self.settlement_lookup.get(normalized_settlement_id)

        if settlement is None:
            raise ValueError("Seçilen POS yatış kaydı bulunamadı.")

        return settlement

    def _on_settlement_changed(self) -> None:
        try:
            settlement = self._selected_settlement()
        except Exception:
            self.preview_label.setText("Geçerli bir planlanan kayıt seçilmelidir.")
            return

        expected_net_text = str(settlement.net_amount).replace(".", ",")
        self.actual_net_amount_input.setText(expected_net_text)

        if settlement.reference_no:
            self.reference_no_input.setText(settlement.reference_no)
        else:
            self.reference_no_input.clear()

        if settlement.description:
            self.description_input.setPlainText(settlement.description)
        else:
            self.description_input.clear()

        self.difference_reason_input.clear()
        self._refresh_preview()

    def _calculate_difference_amount(self) -> Decimal | None:
        settlement = self._selected_settlement()
        actual_net_amount_text = self.actual_net_amount_input.text().strip()

        if not actual_net_amount_text:
            return None

        try:
            actual_net_amount = money(actual_net_amount_text, field_name="Gerçekleşen net tutar")
        except Exception:
            return None

        difference_amount = money(
            actual_net_amount - Decimal(str(settlement.net_amount)),
            field_name="Fark tutarı",
        )

        return difference_amount

    def _refresh_preview(self) -> None:
        try:
            settlement = self._selected_settlement()
        except Exception:
            self.preview_label.setText("Geçerli bir planlanan kayıt seçilmelidir.")
            return

        difference_amount = self._calculate_difference_amount()

        preview_lines = [
            f"POS: {settlement.pos_device_name}",
            f"Banka: {settlement.bank_name}",
            f"Hesap: {settlement.bank_account_name}",
            f"İşlem Tarihi: {settlement.transaction_date_text}",
            f"Beklenen Yatış Tarihi: {settlement.expected_settlement_date_text}",
            f"Beklenen Net: {format_currency_amount(settlement.net_amount, settlement.currency_code)}",
        ]

        if difference_amount is None:
            preview_lines.append("Gerçekleşen Net: -")
            preview_lines.append("Fark: -")
            preview_lines.append("Sonuç Durumu: -")
        else:
            actual_net_amount = money(
                self.actual_net_amount_input.text().strip(),
                field_name="Gerçekleşen net tutar",
            )
            preview_lines.append(
                f"Gerçekleşen Net: {format_currency_amount(actual_net_amount, settlement.currency_code)}"
            )
            preview_lines.append(
                f"Fark: {format_currency_amount(difference_amount, settlement.currency_code)}"
            )
            preview_lines.append(
                "Sonuç Durumu: Gerçekleşti"
                if difference_amount == Decimal("0.00")
                else "Sonuç Durumu: Fark Var"
            )

        preview_lines.append(
            f"Gerçekleşen Tarih: {_qdate_to_date(self.realized_date_edit.date()).strftime('%d.%m.%Y')}"
        )

        self.preview_label.setText("\n".join(preview_lines))

    def _build_payload(self) -> dict[str, Any]:
        settlement = self._selected_settlement()

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