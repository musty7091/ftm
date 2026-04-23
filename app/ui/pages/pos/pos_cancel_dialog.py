from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.ui.pages.banks.bank_dialog_styles import BANK_DIALOG_STYLES
from app.ui.pages.pos.pos_data import format_currency_amount


class PosCancelDialog(QDialog):
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

        self.setWindowTitle("POS Kaydı İptal Et")
        self.resize(720, 500)
        self.setStyleSheet(BANK_DIALOG_STYLES)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 22, 24, 22)
        main_layout.setSpacing(16)

        title = QLabel("POS Kaydı İptal Et")
        title.setObjectName("SectionTitle")

        subtitle = QLabel(
            "Bu ekran sadece planlanan POS yatış kayıtlarını iptal eder. "
            "Henüz banka hareketine dönüşmemiş kayıtlar güvenli şekilde iptal edilir."
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
        self.settlement_combo.currentIndexChanged.connect(self._refresh_preview)
        form_layout.addRow("Planlanan kayıt", self.settlement_combo)

        self.cancel_reason_input = QTextEdit()
        self.cancel_reason_input.setFixedHeight(130)
        self.cancel_reason_input.setPlaceholderText("İptal nedenini yazın.")
        form_layout.addRow("İptal nedeni", self.cancel_reason_input)

        self.preview_label = QLabel("")
        self.preview_label.setObjectName("MutedText")
        self.preview_label.setWordWrap(True)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)

        self.cancel_button = QPushButton("Vazgeç")
        self.save_button = QPushButton("İptal Et")

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

    def _fill_settlement_combo(self) -> None:
        self.settlement_combo.clear()

        for settlement in self.planned_settlements:
            text = (
                f"#{settlement.pos_settlement_id} / "
                f"{settlement.pos_device_name} / "
                f"{settlement.bank_name} / "
                f"Net: {format_currency_amount(settlement.net_amount, settlement.currency_code)} / "
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
            raise ValueError("Seçilen POS kaydı bulunamadı.")

        return settlement

    def _refresh_preview(self) -> None:
        try:
            settlement = self._selected_settlement()
        except Exception:
            self.preview_label.setText("Geçerli bir planlanan kayıt seçilmelidir.")
            return

        preview_lines = [
            f"POS: {settlement.pos_device_name}",
            f"Terminal: {settlement.terminal_no or '-'}",
            f"Banka: {settlement.bank_name}",
            f"Hesap: {settlement.bank_account_name}",
            f"İşlem Tarihi: {settlement.transaction_date_text}",
            f"Beklenen Yatış Tarihi: {settlement.expected_settlement_date_text}",
            f"Brüt: {format_currency_amount(settlement.gross_amount, settlement.currency_code)}",
            f"Net: {format_currency_amount(settlement.net_amount, settlement.currency_code)}",
        ]

        self.preview_label.setText("\n".join(preview_lines))

    def _build_payload(self) -> dict[str, Any]:
        settlement = self._selected_settlement()
        cancel_reason = self.cancel_reason_input.toPlainText().strip()

        if not cancel_reason:
            raise ValueError("İptal nedeni boş olamaz.")

        if len(cancel_reason) < 5:
            raise ValueError("İptal nedeni daha açıklayıcı olmalıdır.")

        return {
            "pos_settlement_id": settlement.pos_settlement_id,
            "cancel_reason": cancel_reason,
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