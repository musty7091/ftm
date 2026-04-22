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
    QVBoxLayout,
    QWidget,
)

from app.ui.pages.banks.bank_admin_data import (
    AdminBankAccountRow,
    AdminBankRow,
    bank_account_display_text,
    bank_display_text,
    load_admin_bank_accounts,
    load_admin_banks,
)
from app.ui.pages.banks.bank_dialog_styles import BANK_DIALOG_STYLES
from app.ui.pages.banks.bank_account_dialog import BankAccountDialog
from app.ui.pages.banks.bank_definition_dialog import BankDefinitionDialog


class BankManageDialog(QDialog):
    def __init__(
        self,
        *,
        parent: QWidget | None,
    ) -> None:
        super().__init__(parent)

        self.banks = load_admin_banks(include_passive=True)
        self.bank_accounts = load_admin_bank_accounts(include_passive=True)
        self.payload: dict[str, Any] | None = None

        self.setWindowTitle("Banka / Hesap Düzenle")
        self.resize(720, 360)
        self.setStyleSheet(BANK_DIALOG_STYLES)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 22, 24, 22)
        main_layout.setSpacing(16)

        title = QLabel("Banka / Hesap Düzenle")
        title.setObjectName("SectionTitle")

        subtitle = QLabel(
            "Banka tanımlarını veya banka hesabı tanımlarını düzenler."
        )
        subtitle.setObjectName("MutedText")
        subtitle.setWordWrap(True)

        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        form_layout.setHorizontalSpacing(18)
        form_layout.setVerticalSpacing(14)

        self.edit_type_combo = QComboBox()
        self.edit_type_combo.setMinimumHeight(38)
        self.edit_type_combo.addItem("Banka Düzenle", "BANK")
        self.edit_type_combo.addItem("Banka Hesabı Düzenle", "BANK_ACCOUNT")
        self.edit_type_combo.currentIndexChanged.connect(self._refresh_target_combo)
        form_layout.addRow("Düzenleme türü", self.edit_type_combo)

        self.target_combo = QComboBox()
        self.target_combo.setMinimumHeight(38)
        form_layout.addRow("Kayıt", self.target_combo)

        self.info_label = QLabel("")
        self.info_label.setObjectName("MutedText")
        self.info_label.setWordWrap(True)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)

        self.cancel_button = QPushButton("Vazgeç")
        self.edit_button = QPushButton("Düzenle")

        self.cancel_button.setMinimumHeight(40)
        self.edit_button.setMinimumHeight(40)

        self.cancel_button.clicked.connect(self.reject)
        self.edit_button.clicked.connect(self._open_selected_edit_dialog)

        button_layout.addStretch(1)
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.edit_button)

        main_layout.addWidget(title)
        main_layout.addWidget(subtitle)
        main_layout.addSpacing(4)
        main_layout.addLayout(form_layout)
        main_layout.addWidget(self.info_label)
        main_layout.addStretch(1)
        main_layout.addLayout(button_layout)

        self._refresh_target_combo()

    def _refresh_target_combo(self) -> None:
        self.target_combo.clear()

        edit_type = self.edit_type_combo.currentData()

        if edit_type == "BANK":
            for bank in self.banks:
                self.target_combo.addItem(bank_display_text(bank), bank.bank_id)

            has_rows = len(self.banks) > 0
            self.target_combo.setEnabled(has_rows)
            self.edit_button.setEnabled(has_rows)

            self.info_label.setText(
                "Banka adı, kısa adı, notu ve aktif/pasif durumu düzenlenebilir."
                if has_rows
                else "Düzenlenebilir banka tanımı bulunamadı."
            )
            return

        if edit_type == "BANK_ACCOUNT":
            for bank_account in self.bank_accounts:
                self.target_combo.addItem(
                    bank_account_display_text(bank_account),
                    bank_account.bank_account_id,
                )

            has_rows = len(self.bank_accounts) > 0
            self.target_combo.setEnabled(has_rows)
            self.edit_button.setEnabled(has_rows)

            self.info_label.setText(
                "Banka hesabı temel bilgileri düzenlenebilir. Hareket görmüş hesabın para birimi değiştirilemez."
                if has_rows
                else "Düzenlenebilir banka hesabı bulunamadı."
            )
            return

        self.target_combo.setEnabled(False)
        self.edit_button.setEnabled(False)
        self.info_label.setText("Geçerli bir düzenleme türü seçilmelidir.")

    def _selected_bank(self) -> AdminBankRow:
        bank_id = self.target_combo.currentData()

        try:
            normalized_bank_id = int(bank_id)
        except (TypeError, ValueError) as exc:
            raise ValueError("Geçerli bir banka seçilmelidir.") from exc

        for bank in self.banks:
            if bank.bank_id == normalized_bank_id:
                return bank

        raise ValueError("Seçilen banka bulunamadı.")

    def _selected_bank_account(self) -> AdminBankAccountRow:
        bank_account_id = self.target_combo.currentData()

        try:
            normalized_bank_account_id = int(bank_account_id)
        except (TypeError, ValueError) as exc:
            raise ValueError("Geçerli bir banka hesabı seçilmelidir.") from exc

        for bank_account in self.bank_accounts:
            if bank_account.bank_account_id == normalized_bank_account_id:
                return bank_account

        raise ValueError("Seçilen banka hesabı bulunamadı.")

    def _open_selected_edit_dialog(self) -> None:
        edit_type = self.edit_type_combo.currentData()

        try:
            if edit_type == "BANK":
                selected_bank = self._selected_bank()

                dialog = BankDefinitionDialog(
                    parent=self,
                    mode="edit",
                    bank_row=selected_bank,
                )

                if dialog.exec() != QDialog.Accepted:
                    return

                self.payload = {
                    "edit_type": "BANK",
                    "data": dialog.get_payload(),
                }

                self.accept()
                return

            if edit_type == "BANK_ACCOUNT":
                selected_bank_account = self._selected_bank_account()

                active_banks = [
                    bank
                    for bank in load_admin_banks(include_passive=False)
                ]

                dialog = BankAccountDialog(
                    parent=self,
                    mode="edit",
                    banks=active_banks,
                    bank_account_row=selected_bank_account,
                )

                if dialog.exec() != QDialog.Accepted:
                    return

                self.payload = {
                    "edit_type": "BANK_ACCOUNT",
                    "data": dialog.get_payload(),
                }

                self.accept()
                return

            raise ValueError("Geçerli bir düzenleme türü seçilmelidir.")

        except Exception as exc:
            QMessageBox.warning(self, "Eksik veya hatalı bilgi", str(exc))

    def get_payload(self) -> dict[str, Any]:
        if self.payload is None:
            raise ValueError("Düzenleme bilgisi bulunamadı.")

        return self.payload