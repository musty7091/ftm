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

from app.ui.pages.banks.bank_admin_data import (
    bank_account_display_text,
    load_admin_bank_accounts,
)
from app.ui.pages.banks.bank_dialog_styles import BANK_DIALOG_STYLES


class BankAccountDeactivateDialog(QDialog):
    def __init__(
        self,
        *,
        parent: QWidget | None,
    ) -> None:
        super().__init__(parent)

        self.active_bank_accounts = load_admin_bank_accounts(include_passive=False)
        self.all_bank_accounts = load_admin_bank_accounts(include_passive=True)
        self.passive_bank_accounts = [
            bank_account
            for bank_account in self.all_bank_accounts
            if not bank_account.is_active
        ]
        self.payload: dict[str, Any] | None = None

        self.setWindowTitle("Hesap Pasifleştir / Aktifleştir")
        self.resize(760, 470)
        self.setStyleSheet(BANK_DIALOG_STYLES)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 22, 24, 22)
        main_layout.setSpacing(16)

        title = QLabel("Hesap Pasifleştir / Aktifleştir")
        title.setObjectName("SectionTitle")

        subtitle = QLabel(
            "Aktif banka hesaplarını pasifleştirir veya pasif banka hesaplarını tekrar aktif hale getirir. "
            "Bakiyesi sıfır olmayan hesaplar pasifleştirilemez."
        )
        subtitle.setObjectName("MutedText")
        subtitle.setWordWrap(True)

        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        form_layout.setHorizontalSpacing(18)
        form_layout.setVerticalSpacing(14)

        self.operation_combo = QComboBox()
        self.operation_combo.setMinimumHeight(38)
        self.operation_combo.addItem("Aktif hesabı pasifleştir", "DEACTIVATE")
        self.operation_combo.addItem("Pasif hesabı aktifleştir", "REACTIVATE")
        self.operation_combo.currentIndexChanged.connect(self._refresh_account_combo)
        form_layout.addRow("İşlem türü", self.operation_combo)

        self.account_combo = QComboBox()
        self.account_combo.setMinimumHeight(38)
        form_layout.addRow("Banka hesabı", self.account_combo)

        self.reason_input = QTextEdit()
        self.reason_input.setFixedHeight(120)
        self.reason_input.setPlaceholderText("İşlem nedenini yazın.")
        form_layout.addRow("Neden", self.reason_input)

        self.info_label = QLabel("")
        self.info_label.setObjectName("MutedText")
        self.info_label.setWordWrap(True)

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
        main_layout.addWidget(self.info_label)
        main_layout.addStretch(1)
        main_layout.addLayout(button_layout)

        self._refresh_account_combo()

    def _refresh_account_combo(self) -> None:
        self.account_combo.clear()

        operation_type = self.operation_combo.currentData()

        if operation_type == "DEACTIVATE":
            for bank_account in self.active_bank_accounts:
                self.account_combo.addItem(
                    bank_account_display_text(bank_account),
                    bank_account.bank_account_id,
                )

            has_rows = len(self.active_bank_accounts) > 0
            self.account_combo.setEnabled(has_rows)
            self.save_button.setEnabled(has_rows)

            if has_rows:
                self.info_label.setText(
                    "Pasifleştirme sırasında sistem hesabın güncel bakiyesini kontrol eder. "
                    "Bakiye sıfır değilse işlem engellenir."
                )
            else:
                self.info_label.setText("Pasifleştirilebilir aktif banka hesabı bulunamadı.")

            return

        if operation_type == "REACTIVATE":
            for bank_account in self.passive_bank_accounts:
                self.account_combo.addItem(
                    bank_account_display_text(bank_account),
                    bank_account.bank_account_id,
                )

            has_rows = len(self.passive_bank_accounts) > 0
            self.account_combo.setEnabled(has_rows)
            self.save_button.setEnabled(has_rows)

            if has_rows:
                self.info_label.setText(
                    "Pasif banka hesabı tekrar aktif hale getirilir. "
                    "Bağlı olduğu banka pasifse aktifleştirme yapılamaz."
                )
            else:
                self.info_label.setText("Aktifleştirilebilir pasif banka hesabı bulunamadı.")

            return

        self.account_combo.setEnabled(False)
        self.save_button.setEnabled(False)
        self.info_label.setText("Geçerli bir işlem türü seçilmelidir.")

    def _build_payload(self) -> dict[str, Any]:
        operation_type = str(self.operation_combo.currentData() or "").strip()

        if operation_type not in {"DEACTIVATE", "REACTIVATE"}:
            raise ValueError("Geçerli bir işlem türü seçilmelidir.")

        bank_account_id = self.account_combo.currentData()

        try:
            normalized_bank_account_id = int(bank_account_id)
        except (TypeError, ValueError) as exc:
            raise ValueError("Geçerli bir banka hesabı seçilmelidir.") from exc

        reason = self.reason_input.toPlainText().strip()

        if not reason:
            raise ValueError("İşlem nedeni boş olamaz.")

        if len(reason) < 5:
            raise ValueError("İşlem nedeni daha açıklayıcı olmalıdır.")

        return {
            "operation_type": operation_type,
            "bank_account_id": normalized_bank_account_id,
            "reason": reason,
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