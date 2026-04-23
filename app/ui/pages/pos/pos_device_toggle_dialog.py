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
from app.ui.pages.pos.pos_admin_data import (
    load_admin_pos_devices,
    pos_device_display_text,
)


class PosDeviceToggleDialog(QDialog):
    def __init__(
        self,
        *,
        parent: QWidget | None,
    ) -> None:
        super().__init__(parent)

        self.active_pos_devices = load_admin_pos_devices(include_passive=False)
        self.all_pos_devices = load_admin_pos_devices(include_passive=True)
        self.passive_pos_devices = [
            pos_device
            for pos_device in self.all_pos_devices
            if not pos_device.is_active
        ]
        self.payload: dict[str, Any] | None = None

        self.setWindowTitle("POS Cihazı Pasifleştir / Aktifleştir")
        self.resize(760, 470)
        self.setStyleSheet(BANK_DIALOG_STYLES)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 22, 24, 22)
        main_layout.setSpacing(16)

        title = QLabel("POS Cihazı Pasifleştir / Aktifleştir")
        title.setObjectName("SectionTitle")

        subtitle = QLabel(
            "Aktif POS cihazlarını pasifleştirir veya pasif POS cihazlarını tekrar aktif hale getirir. "
            "Açık planlanan ya da fark içeren mutabakatı olan cihazlar pasifleştirilemez."
        )
        subtitle.setObjectName("MutedText")
        subtitle.setWordWrap(True)

        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        form_layout.setHorizontalSpacing(18)
        form_layout.setVerticalSpacing(14)

        self.operation_combo = QComboBox()
        self.operation_combo.setMinimumHeight(38)
        self.operation_combo.addItem("Aktif POS cihazını pasifleştir", "DEACTIVATE")
        self.operation_combo.addItem("Pasif POS cihazını aktifleştir", "REACTIVATE")
        self.operation_combo.currentIndexChanged.connect(self._refresh_pos_device_combo)
        form_layout.addRow("İşlem türü", self.operation_combo)

        self.pos_device_combo = QComboBox()
        self.pos_device_combo.setMinimumHeight(38)
        form_layout.addRow("POS cihazı", self.pos_device_combo)

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

        self._refresh_pos_device_combo()

    def _refresh_pos_device_combo(self) -> None:
        self.pos_device_combo.clear()

        operation_type = self.operation_combo.currentData()

        if operation_type == "DEACTIVATE":
            for pos_device in self.active_pos_devices:
                self.pos_device_combo.addItem(
                    pos_device_display_text(pos_device),
                    pos_device.pos_device_id,
                )

            has_rows = len(self.active_pos_devices) > 0
            self.pos_device_combo.setEnabled(has_rows)
            self.save_button.setEnabled(has_rows)

            if has_rows:
                self.info_label.setText(
                    "Pasifleştirme sırasında sistem açık planlanan ve fark içeren POS mutabakatlarını kontrol eder. "
                    "Açık kayıt varsa işlem engellenir."
                )
            else:
                self.info_label.setText("Pasifleştirilebilir aktif POS cihazı bulunamadı.")

            return

        if operation_type == "REACTIVATE":
            for pos_device in self.passive_pos_devices:
                self.pos_device_combo.addItem(
                    pos_device_display_text(pos_device),
                    pos_device.pos_device_id,
                )

            has_rows = len(self.passive_pos_devices) > 0
            self.pos_device_combo.setEnabled(has_rows)
            self.save_button.setEnabled(has_rows)

            if has_rows:
                self.info_label.setText(
                    "Pasif POS cihazı tekrar aktif hale getirilir. "
                    "Bağlı olduğu banka hesabı veya banka pasifse aktifleştirme yapılamaz."
                )
            else:
                self.info_label.setText("Aktifleştirilebilir pasif POS cihazı bulunamadı.")

            return

        self.pos_device_combo.setEnabled(False)
        self.save_button.setEnabled(False)
        self.info_label.setText("Geçerli bir işlem türü seçilmelidir.")

    def _build_payload(self) -> dict[str, Any]:
        operation_type = str(self.operation_combo.currentData() or "").strip()

        if operation_type not in {"DEACTIVATE", "REACTIVATE"}:
            raise ValueError("Geçerli bir işlem türü seçilmelidir.")

        pos_device_id = self.pos_device_combo.currentData()

        try:
            normalized_pos_device_id = int(pos_device_id)
        except (TypeError, ValueError) as exc:
            raise ValueError("Geçerli bir POS cihazı seçilmelidir.") from exc

        reason = self.reason_input.toPlainText().strip()

        if not reason:
            raise ValueError("İşlem nedeni boş olamaz.")

        if len(reason) < 5:
            raise ValueError("İşlem nedeni daha açıklayıcı olmalıdır.")

        return {
            "operation_type": operation_type,
            "pos_device_id": normalized_pos_device_id,
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