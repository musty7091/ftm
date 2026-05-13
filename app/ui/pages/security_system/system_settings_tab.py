from __future__ import annotations

from datetime import datetime
from typing import Any

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
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

from app.core.config import BASE_DIR, ENV_FILE, IS_PACKAGED_APP, settings
from app.db.session import check_database_connection, session_scope
from app.services.app_settings_service import (
    AppSettingsServiceError,
    app_settings_file_path,
    default_app_settings_dict,
    describe_app_settings_status,
    ensure_runtime_folders,
    load_app_settings,
    save_app_settings_dict,
    update_app_settings,
)
from app.services.audit_service import write_audit_log
from app.services.backup_mail_settings_service import load_backup_mail_settings
from app.services.permission_service import Permission
from app.ui.pages.settings.backup_mail_settings_dialog import BackupMailSettingsDialog
from app.ui.permission_ui import (
    set_widget_permission,
    user_has_permission,
)


SYSTEM_SETTINGS_TAB_STYLE = """
QFrame#SystemSettingsCard {
    background-color: #111827;
    border: 1px solid #24324a;
    border-radius: 18px;
}

QFrame#SystemSettingsInfoCard {
    background-color: rgba(15, 23, 42, 0.66);
    border: 1px solid rgba(148, 163, 184, 0.22);
    border-radius: 14px;
}

QFrame#SystemSettingsSuccessCard {
    background-color: rgba(6, 78, 59, 0.24);
    border: 1px solid rgba(16, 185, 129, 0.38);
    border-radius: 14px;
}

QFrame#SystemSettingsWarningCard {
    background-color: rgba(120, 53, 15, 0.24);
    border: 1px solid rgba(245, 158, 11, 0.42);
    border-radius: 14px;
}

QFrame#SystemSettingsActionCard {
    background-color: rgba(15, 23, 42, 0.58);
    border: 1px solid rgba(59, 130, 246, 0.28);
    border-radius: 14px;
}

QGroupBox {
    color: #f8fafc;
    font-size: 13px;
    font-weight: 900;
    border: 1px solid rgba(148, 163, 184, 0.24);
    border-radius: 14px;
    margin-top: 12px;
    padding: 14px 12px 12px 12px;
    background-color: rgba(15, 23, 42, 0.42);
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0px 8px;
    left: 12px;
}

QLabel#SystemSettingsTitle {
    color: #f8fafc;
    font-size: 16px;
    font-weight: 900;
}

QLabel#SystemSettingsSubtitle {
    color: #94a3b8;
    font-size: 12px;
}

QLabel#SystemSettingsSectionTitle {
    color: #f8fafc;
    font-size: 14px;
    font-weight: 900;
}

QLabel#SystemSettingsFieldLabel {
    color: #bfdbfe;
    font-size: 12px;
    font-weight: 800;
}

QLabel#SystemSettingsValue {
    color: #e5e7eb;
    font-size: 12px;
    font-weight: 700;
}

QLabel#SystemSettingsMutedValue {
    color: #94a3b8;
    font-size: 12px;
}

QLabel#SystemSettingsBadge {
    color: #dbeafe;
    font-size: 11px;
    font-weight: 800;
    background-color: rgba(30, 64, 175, 0.32);
    border: 1px solid rgba(59, 130, 246, 0.42);
    border-radius: 8px;
    padding: 5px 9px;
}

QLabel#SystemSettingsOkBadge {
    color: #d1fae5;
    font-size: 11px;
    font-weight: 800;
    background-color: rgba(6, 78, 59, 0.34);
    border: 1px solid rgba(16, 185, 129, 0.42);
    border-radius: 8px;
    padding: 5px 9px;
}

QLabel#SystemSettingsWarnBadge {
    color: #fde68a;
    font-size: 11px;
    font-weight: 800;
    background-color: rgba(120, 53, 15, 0.36);
    border: 1px solid rgba(245, 158, 11, 0.48);
    border-radius: 8px;
    padding: 5px 9px;
}

QLineEdit,
QTextEdit {
    background-color: #0f172a;
    color: #f8fafc;
    border: 1px solid #334155;
    border-radius: 10px;
    padding: 8px 10px;
    font-size: 12px;
}

QLineEdit:focus,
QTextEdit:focus {
    border: 1px solid #3b82f6;
}

QLineEdit:disabled,
QTextEdit:disabled {
    background-color: rgba(30, 41, 59, 0.55);
    color: #64748b;
    border: 1px solid rgba(100, 116, 139, 0.32);
}

QPushButton#SystemSettingsPrimaryButton {
    background-color: #2563eb;
    color: #ffffff;
    border: 1px solid #3b82f6;
    border-radius: 11px;
    padding: 8px 14px;
    font-weight: 900;
}

QPushButton#SystemSettingsPrimaryButton:hover {
    background-color: #1d4ed8;
}

QPushButton#SystemSettingsSuccessButton {
    background-color: #047857;
    color: #ffffff;
    border: 1px solid #10b981;
    border-radius: 11px;
    padding: 8px 14px;
    font-weight: 900;
}

QPushButton#SystemSettingsSuccessButton:hover {
    background-color: #059669;
}

QPushButton#SystemSettingsWarningButton {
    background-color: #92400e;
    color: #ffffff;
    border: 1px solid #f59e0b;
    border-radius: 11px;
    padding: 8px 14px;
    font-weight: 900;
}

QPushButton#SystemSettingsWarningButton:hover {
    background-color: #b45309;
}

QPushButton#SystemSettingsSecondaryButton {
    background-color: #172033;
    color: #cbd5e1;
    border: 1px solid #24324a;
    border-radius: 11px;
    padding: 8px 14px;
    font-weight: 900;
}

QPushButton#SystemSettingsSecondaryButton:hover {
    background-color: #1e293b;
    color: #ffffff;
}

QPushButton:disabled {
    background-color: rgba(30, 41, 59, 0.55);
    color: #64748b;
    border: 1px solid rgba(100, 116, 139, 0.32);
}

QTableWidget#SystemSettingsTable {
    background-color: #0f172a;
    color: #e5e7eb;
    border: 1px solid #334155;
    border-radius: 12px;
    gridline-color: #334155;
    selection-background-color: #2563eb;
    selection-color: #ffffff;
    alternate-background-color: #111827;
}

QTableWidget#SystemSettingsTable::item {
    padding: 6px;
    border: none;
}

QHeaderView::section {
    background-color: #1f2937;
    color: #f8fafc;
    border: 1px solid #334155;
    padding: 8px;
    font-weight: 900;
}

QTableCornerButton::section {
    background-color: #1f2937;
    border: 1px solid #334155;
}
"""


class TechnicalDetailsDialog(QDialog):
    def __init__(
        self,
        *,
        parent: QWidget | None,
        rows: list[tuple[str, str, str]],
    ) -> None:
        super().__init__(parent)

        self.setWindowTitle("Teknik Sistem Detayları")
        self.resize(900, 620)
        self.setMinimumSize(760, 480)
        self.setSizeGripEnabled(True)
        self.setStyleSheet(SYSTEM_SETTINGS_TAB_STYLE)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 16, 18, 16)
        main_layout.setSpacing(12)

        title = QLabel("Teknik Sistem Detayları")
        title.setObjectName("SystemSettingsTitle")

        subtitle = QLabel(
            "Bu pencere geliştirici / yönetici kontrolü içindir. Müşteri kullanımında ana ayar ekranı sade tutulur."
        )
        subtitle.setObjectName("SystemSettingsSubtitle")
        subtitle.setWordWrap(True)

        self.table = QTableWidget()
        self.table.setObjectName("SystemSettingsTable")
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Alan", "Değer", "Durum"])
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)

        self._fill_table(rows)

        close_button = QPushButton("Kapat")
        close_button.setObjectName("SystemSettingsSecondaryButton")
        close_button.clicked.connect(self.accept)

        button_layout = QHBoxLayout()
        button_layout.addStretch(1)
        button_layout.addWidget(close_button)

        main_layout.addWidget(title)
        main_layout.addWidget(subtitle)
        main_layout.addWidget(self.table, 1)
        main_layout.addLayout(button_layout)

    def _fill_table(self, rows: list[tuple[str, str, str]]) -> None:
        self.table.setRowCount(len(rows))

        for row_index, (field_name, value, status) in enumerate(rows):
            field_item = QTableWidgetItem(str(field_name))
            value_item = QTableWidgetItem(str(value))
            status_item = QTableWidgetItem(str(status))

            field_item.setFlags(field_item.flags() & ~Qt.ItemIsEditable)
            value_item.setFlags(value_item.flags() & ~Qt.ItemIsEditable)
            status_item.setFlags(status_item.flags() & ~Qt.ItemIsEditable)
            status_item.setTextAlignment(Qt.AlignCenter)

            if status == "OK":
                status_item.setForeground(QColor("#22c55e"))
            elif status == "WARN":
                status_item.setForeground(QColor("#fbbf24"))
            else:
                status_item.setForeground(QColor("#f87171"))

            self.table.setItem(row_index, 0, field_item)
            self.table.setItem(row_index, 1, value_item)
            self.table.setItem(row_index, 2, status_item)

        self.table.resizeRowsToContents()


class SystemSettingsTab(QWidget):
    def __init__(self) -> None:
        super().__init__()

        self.setStyleSheet(SYSTEM_SETTINGS_TAB_STYLE)

        self._last_app_settings: Any | None = None

        self.generated_at_label = QLabel("")
        self.generated_at_label.setObjectName("SystemSettingsBadge")

        self.backup_mail_status_label = QLabel("Yedekleme Maili: Kontrol edilmedi")
        self.backup_mail_status_label.setObjectName("SystemSettingsWarnBadge")

        self.backup_mail_recipient_label = QLabel("-")
        self.backup_mail_recipient_label.setObjectName("SystemSettingsValue")

        self.backup_mail_last_test_label = QLabel("-")
        self.backup_mail_last_test_label.setObjectName("SystemSettingsMutedValue")
        self.backup_mail_last_test_label.setWordWrap(True)

        self.company_name_input = QLineEdit()
        self.company_address_input = QTextEdit()
        self.company_phone_input = QLineEdit()
        self.company_email_input = QLineEdit()

        self.report_footer_note_input = QLineEdit()

        self.company_address_input.setFixedHeight(84)

        self.refresh_button = QPushButton("Ayarları Yenile")
        self.refresh_button.setObjectName("SystemSettingsPrimaryButton")
        self.refresh_button.clicked.connect(self.load_settings)

        self.save_button = QPushButton("Ayarları Kaydet")
        self.save_button.setObjectName("SystemSettingsSuccessButton")
        self.save_button.clicked.connect(self.save_settings)

        self.create_folders_button = QPushButton("Klasörleri Oluştur")
        self.create_folders_button.setObjectName("SystemSettingsSuccessButton")
        self.create_folders_button.clicked.connect(self.create_required_folders)

        self.reset_defaults_button = QPushButton("Varsayılana Dön")
        self.reset_defaults_button.setObjectName("SystemSettingsWarningButton")
        self.reset_defaults_button.clicked.connect(self.reset_to_defaults)

        self.backup_mail_settings_button = QPushButton("Yedekleme Maili Ayarları")
        self.backup_mail_settings_button.setObjectName("SystemSettingsPrimaryButton")
        self.backup_mail_settings_button.clicked.connect(self.open_backup_mail_settings_dialog)

        self.technical_details_button = QPushButton("Teknik Detayları Göster")
        self.technical_details_button.setObjectName("SystemSettingsSecondaryButton")
        self.technical_details_button.clicked.connect(self.open_technical_details_dialog)

        self._build_ui()

        self.load_settings()
        QTimer.singleShot(0, self.apply_permissions)

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 14, 12, 12)
        main_layout.setSpacing(12)

        card = QFrame()
        card.setObjectName("SystemSettingsCard")

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 16, 18, 16)
        card_layout.setSpacing(14)

        title_row = QHBoxLayout()
        title_row.setSpacing(10)

        title = QLabel("Sistem Ayarları")
        title.setObjectName("SystemSettingsTitle")

        title_row.addWidget(title, 1)
        title_row.addWidget(self.generated_at_label, 0, Qt.AlignVCenter)

        subtitle = QLabel(
            "Firma bilgileri, yedekleme maili ve rapor notu bu ekrandan yönetilir. "
            "SMTP şifresi ve teknik ayarlar müşteriye gösterilmez."
        )
        subtitle.setObjectName("SystemSettingsSubtitle")
        subtitle.setWordWrap(True)

        form_grid = QGridLayout()
        form_grid.setSpacing(12)
        form_grid.setColumnStretch(0, 1)
        form_grid.setColumnStretch(1, 1)

        form_grid.addWidget(self._build_company_group(), 0, 0)
        form_grid.addWidget(self._build_backup_mail_group(), 0, 1)
        form_grid.addWidget(self._build_report_group(), 1, 0)
        form_grid.addWidget(self._build_maintenance_group(), 1, 1)

        card_layout.addLayout(title_row)
        card_layout.addWidget(subtitle)
        card_layout.addLayout(form_grid, 1)

        main_layout.addWidget(card, 1)

    def _build_company_group(self) -> QWidget:
        group = QGroupBox("Firma Bilgileri")

        layout = QGridLayout(group)
        layout.setContentsMargins(12, 16, 12, 12)
        layout.setSpacing(8)

        layout.addWidget(self._field_label("Firma Adı"), 0, 0)
        layout.addWidget(self.company_name_input, 0, 1)

        layout.addWidget(self._field_label("Adres"), 1, 0)
        layout.addWidget(self.company_address_input, 1, 1)

        layout.addWidget(self._field_label("Telefon"), 2, 0)
        layout.addWidget(self.company_phone_input, 2, 1)

        layout.addWidget(self._field_label("E-posta"), 3, 0)
        layout.addWidget(self.company_email_input, 3, 1)

        return group

    def _build_backup_mail_group(self) -> QWidget:
        group = QGroupBox("Yedekleme Maili")

        layout = QVBoxLayout(group)
        layout.setContentsMargins(12, 16, 12, 12)
        layout.setSpacing(10)

        hint = QLabel(
            "Müşterinin yedek alıcı mail adresi buradan yönetilir. "
            "Merkezi gönderici hesap ve uygulama şifresi bu ekranda gösterilmez."
        )
        hint.setObjectName("SystemSettingsSubtitle")
        hint.setWordWrap(True)

        recipient_title = QLabel("Alıcı")
        recipient_title.setObjectName("SystemSettingsFieldLabel")

        last_test_title = QLabel("Son Test")
        last_test_title.setObjectName("SystemSettingsFieldLabel")

        layout.addWidget(self.backup_mail_status_label, 0, Qt.AlignLeft)
        layout.addWidget(hint)
        layout.addWidget(recipient_title)
        layout.addWidget(self.backup_mail_recipient_label)
        layout.addWidget(last_test_title)
        layout.addWidget(self.backup_mail_last_test_label)
        layout.addStretch(1)
        layout.addWidget(self.backup_mail_settings_button, 0, Qt.AlignLeft)

        return group

    def _build_report_group(self) -> QWidget:
        group = QGroupBox("Rapor Ayarları")

        layout = QGridLayout(group)
        layout.setContentsMargins(12, 16, 12, 12)
        layout.setSpacing(8)

        hint = QLabel("Raporlarda kullanılacak güvenli not alanı.")
        hint.setObjectName("SystemSettingsSubtitle")
        hint.setWordWrap(True)

        layout.addWidget(hint, 0, 0, 1, 2)

        layout.addWidget(self._field_label("Rapor Alt Notu"), 1, 0)
        layout.addWidget(self.report_footer_note_input, 1, 1)

        return group

    def _build_maintenance_group(self) -> QWidget:
        group = QGroupBox("Bakım İşlemleri")

        layout = QVBoxLayout(group)
        layout.setContentsMargins(12, 16, 12, 12)
        layout.setSpacing(10)

        hint = QLabel(
            "Klasör oluşturma, ayar yenileme ve teknik detay görüntüleme işlemleri burada tutulur."
        )
        hint.setObjectName("SystemSettingsSubtitle")
        hint.setWordWrap(True)

        row_one = QHBoxLayout()
        row_one.setSpacing(8)
        row_one.addWidget(self.refresh_button)
        row_one.addWidget(self.create_folders_button)

        row_two = QHBoxLayout()
        row_two.setSpacing(8)
        row_two.addWidget(self.technical_details_button)
        row_two.addWidget(self.reset_defaults_button)

        row_three = QHBoxLayout()
        row_three.setSpacing(8)
        row_three.addStretch(1)
        row_three.addWidget(self.save_button)

        layout.addWidget(hint)
        layout.addLayout(row_one)
        layout.addLayout(row_two)
        layout.addStretch(1)
        layout.addLayout(row_three)

        return group

    def _field_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("SystemSettingsFieldLabel")
        label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        return label

    def load_settings(self) -> None:
        try:
            app_settings = load_app_settings()
            self._last_app_settings = app_settings

            self.company_name_input.setText(app_settings.company_name)
            self.company_address_input.setPlainText(app_settings.company_address)
            self.company_phone_input.setText(app_settings.company_phone)
            self.company_email_input.setText(app_settings.company_email)
            self.report_footer_note_input.setText(app_settings.report_footer_note)

            self._refresh_backup_mail_summary()

            now_text = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
            self.generated_at_label.setText(f"Güncelleme: {now_text}")

            self.apply_permissions()

        except AppSettingsServiceError as exc:
            QMessageBox.critical(
                self,
                "Ayarlar Yüklenemedi",
                str(exc),
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Beklenmeyen Hata",
                f"Sistem ayarları yüklenirken hata oluştu:\n\n{exc}",
            )

    def save_settings(self) -> None:
        if not self._ensure_update_permission():
            return

        old_values = self._safe_current_settings_dict()

        company_name = self.company_name_input.text().strip()
        company_address = self.company_address_input.toPlainText().strip()
        company_phone = self.company_phone_input.text().strip()
        company_email = self.company_email_input.text().strip()
        report_footer_note = self.report_footer_note_input.text().strip()

        if not company_name:
            QMessageBox.warning(
                self,
                "Eksik Bilgi",
                "Firma adı boş olamaz.",
            )
            return

        current_settings = self._safe_current_app_settings()

        try:
            saved_settings = update_app_settings(
                company_name=company_name,
                company_address=company_address,
                company_phone=company_phone,
                company_email=company_email,
                backup_folder=current_settings.backup_folder,
                export_folder=current_settings.export_folder,
                log_folder=current_settings.log_folder,
                control_mail_enabled=current_settings.control_mail_enabled,
                control_mail_to=current_settings.control_mail_to,
                report_footer_note=report_footer_note,
            )

            new_values = {
                "company_name": saved_settings.company_name,
                "company_address": saved_settings.company_address,
                "company_phone": saved_settings.company_phone,
                "company_email": saved_settings.company_email,
                "backup_folder": saved_settings.backup_folder,
                "export_folder": saved_settings.export_folder,
                "log_folder": saved_settings.log_folder,
                "control_mail_enabled": saved_settings.control_mail_enabled,
                "control_mail_to": saved_settings.control_mail_to,
                "report_footer_note": saved_settings.report_footer_note,
            }

            self._write_settings_audit_log(
                action="SYSTEM_SETTINGS_UPDATED",
                description="Risksiz sistem ayarları güncellendi.",
                old_values=old_values,
                new_values=new_values,
            )

            QMessageBox.information(
                self,
                "Ayarlar Kaydedildi",
                "Sistem ayarları başarıyla kaydedildi.",
            )

            self.load_settings()

        except AppSettingsServiceError as exc:
            QMessageBox.warning(
                self,
                "Ayarlar Kaydedilemedi",
                str(exc),
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Beklenmeyen Hata",
                f"Sistem ayarları kaydedilirken hata oluştu:\n\n{exc}",
            )

    def create_required_folders(self) -> None:
        if not self._ensure_update_permission():
            return

        try:
            folders = ensure_runtime_folders()

            self._write_settings_audit_log(
                action="SYSTEM_RUNTIME_FOLDERS_CREATED",
                description="Sistem klasörleri kontrol edildi / oluşturuldu.",
                old_values=None,
                new_values=folders,
            )

            QMessageBox.information(
                self,
                "Klasörler Hazır",
                "Yedek, dışa aktarım ve log klasörleri kontrol edildi / oluşturuldu.",
            )

            self.load_settings()

        except AppSettingsServiceError as exc:
            QMessageBox.warning(
                self,
                "Klasörler Oluşturulamadı",
                str(exc),
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Beklenmeyen Hata",
                f"Sistem klasörleri oluşturulurken hata oluştu:\n\n{exc}",
            )

    def reset_to_defaults(self) -> None:
        if not self._ensure_update_permission():
            return

        answer = QMessageBox.question(
            self,
            "Varsayılan Ayarlara Dönülsün mü?",
            "Firma bilgileri, klasör ayarları, kontrol maili ve rapor notu varsayılan değerlere döndürülecek.\n\n"
            "Bu işlem veritabanını, lisansı, .env dosyasını veya Gmail uygulama şifresini değiştirmez.\n\n"
            "Devam etmek istiyor musun?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if answer != QMessageBox.Yes:
            return

        old_values = self._safe_current_settings_dict()

        try:
            new_values = save_app_settings_dict(default_app_settings_dict())

            self._write_settings_audit_log(
                action="SYSTEM_SETTINGS_RESET_TO_DEFAULTS",
                description="Risksiz sistem ayarları varsayılana döndürüldü.",
                old_values=old_values,
                new_values=new_values,
            )

            QMessageBox.information(
                self,
                "Varsayılan Ayarlar Yüklendi",
                "Risksiz sistem ayarları varsayılan değerlere döndürüldü.",
            )

            self.load_settings()

        except AppSettingsServiceError as exc:
            QMessageBox.warning(
                self,
                "Varsayılana Dönülemedi",
                str(exc),
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Beklenmeyen Hata",
                f"Varsayılan ayarlar yüklenirken hata oluştu:\n\n{exc}",
            )

    def open_backup_mail_settings_dialog(self) -> None:
        if not self._ensure_update_permission():
            return

        dialog = BackupMailSettingsDialog(parent=self)
        dialog.exec()

        self.load_settings()

    def open_technical_details_dialog(self) -> None:
        rows = self._build_status_rows()
        dialog = TechnicalDetailsDialog(
            parent=self,
            rows=rows,
        )
        dialog.exec()

    def apply_permissions(self) -> None:
        can_update = user_has_permission(
            current_user=self._current_user(),
            permission=Permission.SYSTEM_SETTINGS_UPDATE,
        )

        editable_widgets: list[QWidget] = [
            self.company_name_input,
            self.company_address_input,
            self.company_phone_input,
            self.company_email_input,
            self.report_footer_note_input,
            self.save_button,
            self.create_folders_button,
            self.reset_defaults_button,
            self.backup_mail_settings_button,
        ]

        for widget in editable_widgets:
            set_widget_permission(
                widget,
                allowed=can_update,
                tooltip_when_denied="Sistem ayarlarını değiştirmek için SYSTEM_SETTINGS_UPDATE yetkisi gerekir.",
            )

    def _safe_current_app_settings(self) -> Any:
        if self._last_app_settings is not None:
            return self._last_app_settings

        app_settings = load_app_settings()
        self._last_app_settings = app_settings
        return app_settings

    def _refresh_backup_mail_summary(self) -> None:
        try:
            backup_mail_settings = load_backup_mail_settings()

        except Exception as exc:
            self.backup_mail_status_label.setText("Yedekleme Maili: WARN")
            self.backup_mail_status_label.setObjectName("SystemSettingsWarnBadge")
            self.backup_mail_recipient_label.setText("-")
            self.backup_mail_last_test_label.setText(f"Ayar okunamadı: {exc}")
            self._refresh_widget_style(self.backup_mail_status_label)
            return

        if backup_mail_settings.enabled:
            self.backup_mail_status_label.setText("Yedekleme Maili: Açık")
            self.backup_mail_status_label.setObjectName("SystemSettingsOkBadge")
        else:
            self.backup_mail_status_label.setText("Yedekleme Maili: Kapalı")
            self.backup_mail_status_label.setObjectName("SystemSettingsBadge")

        self.backup_mail_recipient_label.setText(
            backup_mail_settings.recipient_email or "Alıcı mail tanımlı değil."
        )

        if backup_mail_settings.last_test_at or backup_mail_settings.last_test_status:
            self.backup_mail_last_test_label.setText(
                f"{backup_mail_settings.last_test_status or '-'} | "
                f"{backup_mail_settings.last_test_at or '-'} | "
                f"{backup_mail_settings.last_test_message or '-'}"
            )
        else:
            self.backup_mail_last_test_label.setText("Henüz test maili gönderilmedi.")

        self._refresh_widget_style(self.backup_mail_status_label)

    def _build_status_rows(self) -> list[tuple[str, str, str]]:
        rows: list[tuple[str, str, str]] = []

        rows.extend(self._application_rows())
        rows.extend(self._database_rows())
        rows.extend(self._runtime_settings_rows())
        rows.extend(self._env_mail_rows())
        rows.extend(self._backup_mail_rows())

        return rows

    def _application_rows(self) -> list[tuple[str, str, str]]:
        if IS_PACKAGED_APP:
            env_file_value = "Paketli EXE modunda kullanılmıyor"
            env_file_status = "OK"
        else:
            env_file_value = str(ENV_FILE)
            env_file_status = "OK" if ENV_FILE.exists() else "WARN"

        return [
            ("Uygulama Adı", settings.app_name, "OK" if settings.app_name else "WARN"),
            ("Uygulama Ortamı", settings.app_env, "OK" if settings.app_env else "WARN"),
            ("Debug Modu", "Açık" if settings.app_debug else "Kapalı", "WARN" if settings.app_debug else "OK"),
            ("Proje Ana Klasörü", str(BASE_DIR), "OK" if BASE_DIR.exists() else "FAIL"),
            (".env Dosyası", env_file_value, env_file_status),
            ("Uygulama Ayar Dosyası", str(app_settings_file_path()), "OK" if app_settings_file_path().exists() else "WARN"),
        ]

    def _database_rows(self) -> list[tuple[str, str, str]]:
        rows: list[tuple[str, str, str]] = []

        sqlite_database_path = settings.sqlite_database_path
        sqlite_database_folder = sqlite_database_path.parent

        rows.extend(
            [
                (
                    "DB Motoru",
                    "SQLite / Local",
                    "OK",
                ),
                (
                    "SQLite Dosyası",
                    str(sqlite_database_path),
                    "OK" if sqlite_database_path.exists() and sqlite_database_path.is_file() else "FAIL",
                ),
                (
                    "SQLite Klasörü",
                    str(sqlite_database_folder),
                    "OK" if sqlite_database_folder.exists() and sqlite_database_folder.is_dir() else "FAIL",
                ),
                (
                    "DB Echo",
                    "Açık" if settings.database_echo else "Kapalı",
                    "WARN" if settings.database_echo else "OK",
                ),
            ]
        )

        try:
            db_info = check_database_connection()

            rows.extend(
                [
                    (
                        "DB Bağlantı",
                        "Başarılı",
                        "OK",
                    ),
                    (
                        "DB Aktif Motor",
                        str(db_info.get("database_engine", "-")),
                        "OK",
                    ),
                    (
                        "DB Aktif Veri Dosyası",
                        str(db_info.get("database_name", "-")),
                        "OK",
                    ),
                    (
                        "DB Çalışma Kullanıcısı",
                        str(db_info.get("user_name", "-")),
                        "OK",
                    ),
                    (
                        "DB Çalışma Modu",
                        str(db_info.get("server_port", "-")),
                        "OK",
                    ),
                    (
                        "DB Sürüm",
                        str(db_info.get("version_text", "-")),
                        "OK",
                    ),
                ]
            )

        except Exception as exc:
            rows.append(
                (
                    "DB Bağlantı",
                    str(exc),
                    "FAIL",
                )
            )

        return rows

    def _runtime_settings_rows(self) -> list[tuple[str, str, str]]:
        rows: list[tuple[str, str, str]] = []

        for row in describe_app_settings_status():
            rows.append(
                (
                    str(row.get("label", "-")),
                    str(row.get("value", "-")),
                    str(row.get("status", "WARN")),
                )
            )

        return rows

    def _env_mail_rows(self) -> list[tuple[str, str, str]]:
        smtp_password_status = "Tanımlı (gizli)" if settings.mail_password else "-"

        rows = [
            ("SMTP Mail Durumu", "Açık" if settings.mail_enabled else "Kapalı", "OK"),
            (
                "SMTP Sunucu",
                settings.mail_server or "-",
                "OK" if (not settings.mail_enabled or settings.mail_server) else "WARN",
            ),
            (
                "SMTP Port",
                str(settings.mail_port),
                "OK" if (not settings.mail_enabled or settings.mail_port) else "WARN",
            ),
            (
                "SMTP TLS",
                "Açık" if settings.mail_use_tls else "Kapalı",
                "OK",
            ),
            (
                "SMTP Kullanıcı",
                settings.mail_username or "-",
                "OK" if (not settings.mail_enabled or settings.mail_username) else "WARN",
            ),
            (
                "SMTP Şifre",
                smtp_password_status,
                "OK" if (not settings.mail_enabled or settings.mail_password) else "WARN",
            ),
            (
                "SMTP Gönderen",
                settings.mail_from or "-",
                "OK" if (not settings.mail_enabled or settings.mail_from) else "WARN",
            ),
        ]

        return rows

    def _backup_mail_rows(self) -> list[tuple[str, str, str]]:
        try:
            backup_mail_settings = load_backup_mail_settings()

            backup_mail_status = "Açık" if backup_mail_settings.enabled else "Kapalı"
            recipient_email = backup_mail_settings.recipient_email or "-"

            rows = [
                (
                    "Yedekleme Mail Durumu",
                    backup_mail_status,
                    "OK" if not backup_mail_settings.enabled or backup_mail_settings.recipient_email else "WARN",
                ),
                (
                    "Yedekleme Mail Alıcısı",
                    recipient_email,
                    "OK" if not backup_mail_settings.enabled or backup_mail_settings.recipient_email else "WARN",
                ),
            ]

            if backup_mail_settings.last_test_at or backup_mail_settings.last_test_status:
                rows.append(
                    (
                        "Yedekleme Mail Son Test",
                        (
                            f"{backup_mail_settings.last_test_status or '-'} | "
                            f"{backup_mail_settings.last_test_at or '-'} | "
                            f"{backup_mail_settings.last_test_message or '-'}"
                        ),
                        "OK" if backup_mail_settings.last_test_status == "OK" else "WARN",
                    )
                )
            else:
                rows.append(
                    (
                        "Yedekleme Mail Son Test",
                        "Henüz test maili gönderilmedi.",
                        "OK" if not backup_mail_settings.enabled else "WARN",
                    )
                )

            return rows

        except Exception as exc:
            return [
                (
                    "Yedekleme Mail Ayarı",
                    str(exc),
                    "WARN",
                )
            ]

    def _safe_current_settings_dict(self) -> dict[str, Any] | None:
        try:
            app_settings = load_app_settings()

            return {
                "company_name": app_settings.company_name,
                "company_address": app_settings.company_address,
                "company_phone": app_settings.company_phone,
                "company_email": app_settings.company_email,
                "backup_folder": app_settings.backup_folder,
                "export_folder": app_settings.export_folder,
                "log_folder": app_settings.log_folder,
                "control_mail_enabled": app_settings.control_mail_enabled,
                "control_mail_to": app_settings.control_mail_to,
                "report_footer_note": app_settings.report_footer_note,
            }

        except Exception:
            return None

    def _ensure_update_permission(self) -> bool:
        if user_has_permission(
            current_user=self._current_user(),
            permission=Permission.SYSTEM_SETTINGS_UPDATE,
        ):
            return True

        QMessageBox.warning(
            self,
            "Yetkisiz işlem",
            "Sistem ayarlarını değiştirmek için SYSTEM_SETTINGS_UPDATE yetkisi gerekir.",
        )
        return False

    def _write_settings_audit_log(
        self,
        *,
        action: str,
        description: str,
        old_values: dict[str, Any] | None,
        new_values: dict[str, Any] | None,
    ) -> None:
        try:
            with session_scope() as session:
                write_audit_log(
                    session,
                    user_id=self._current_user_id(),
                    action=action,
                    entity_type="AppSettings",
                    entity_id=None,
                    description=description,
                    old_values=old_values,
                    new_values=new_values,
                )

        except Exception:
            pass

    def _current_user(self) -> Any | None:
        window = self.window()

        if window is None:
            return None

        return getattr(window, "current_user", None)

    def _current_user_id(self) -> int | None:
        current_user = self._current_user()

        if current_user is None:
            return None

        user_id = getattr(current_user, "id", None)

        if user_id is None:
            return None

        try:
            return int(user_id)
        except (TypeError, ValueError):
            return None

    def _refresh_widget_style(self, widget: QWidget) -> None:
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        widget.update()


def build_system_settings_tab() -> QWidget:
    return SystemSettingsTab()


__all__ = [
    "SystemSettingsTab",
    "build_system_settings_tab",
]
