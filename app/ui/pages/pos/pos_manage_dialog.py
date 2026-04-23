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

from app.ui.pages.banks.bank_dialog_styles import BANK_DIALOG_STYLES
from app.ui.pages.pos.pos_admin_data import (
    AdminPosDeviceRow,
    load_admin_pos_bank_accounts,
    load_admin_pos_devices,
    pos_device_display_text,
)
from app.ui.pages.pos.pos_device_dialog import PosDeviceDialog


class PosManageDialog(QDialog):
    def __init__(
        self,
        *,
        parent: QWidget | None,
    ) -> None:
        super().__init__(parent)

        self.pos_devices = load_admin_pos_devices(include_passive=True)
        self.payload: dict[str, Any] | None = None

        self.setWindowTitle("POS Cihazı Düzenle")
        self.resize(760, 360)
        self.setStyleSheet(BANK_DIALOG_STYLES)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 22, 24, 22)
        main_layout.setSpacing(16)

        title = QLabel("POS Cihazı Düzenle")
        title.setObjectName("SectionTitle")

        subtitle = QLabel(
            "Mevcut POS cihazı tanımlarını düzenler. İsim, terminal no, komisyon oranı, "
            "valör gün, not ve aktif/pasif durumu güncellenebilir."
        )
        subtitle.setObjectName("MutedText")
        subtitle.setWordWrap(True)

        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        form_layout.setHorizontalSpacing(18)
        form_layout.setVerticalSpacing(14)

        self.target_combo = QComboBox()
        self.target_combo.setMinimumHeight(38)
        form_layout.addRow("POS cihazı", self.target_combo)

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

        for pos_device in self.pos_devices:
            self.target_combo.addItem(
                pos_device_display_text(pos_device),
                pos_device.pos_device_id,
            )

        has_rows = len(self.pos_devices) > 0
        self.target_combo.setEnabled(has_rows)
        self.edit_button.setEnabled(has_rows)

        if has_rows:
            self.info_label.setText(
                "POS cihazı bilgileri düzenlenebilir. Pasif bağlı hesaplara kayıt taşımak "
                "servis katmanında ayrıca kontrol edilir."
            )
        else:
            self.info_label.setText("Düzenlenebilir POS cihazı bulunamadı.")

    def _selected_pos_device(self) -> AdminPosDeviceRow:
        pos_device_id = self.target_combo.currentData()

        try:
            normalized_pos_device_id = int(pos_device_id)
        except (TypeError, ValueError) as exc:
            raise ValueError("Geçerli bir POS cihazı seçilmelidir.") from exc

        for pos_device in self.pos_devices:
            if pos_device.pos_device_id == normalized_pos_device_id:
                return pos_device

        raise ValueError("Seçilen POS cihazı bulunamadı.")

    def _open_selected_edit_dialog(self) -> None:
        try:
            selected_pos_device = self._selected_pos_device()

            available_bank_accounts = load_admin_pos_bank_accounts(include_passive=True)

            dialog = PosDeviceDialog(
                parent=self,
                mode="edit",
                bank_accounts=available_bank_accounts,
                pos_device_row=selected_pos_device,
            )

            if dialog.exec() != QDialog.Accepted:
                return

            self.payload = {
                "edit_type": "POS_DEVICE",
                "data": dialog.get_payload(),
            }

            self.accept()

        except Exception as exc:
            QMessageBox.warning(self, "Eksik veya hatalı bilgi", str(exc))

    def get_payload(self) -> dict[str, Any]:
        if self.payload is None:
            raise ValueError("Düzenleme bilgisi bulunamadı.")

        return self.payload