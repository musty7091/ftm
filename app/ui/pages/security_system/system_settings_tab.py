from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
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

from app.core.config import BASE_DIR, ENV_FILE, settings
from app.db.session import check_database_connection, session_scope
from app.services.app_settings_service import (
    AppSettingsServiceError,
    app_settings_file_path,
    default_app_settings_dict,
    describe_app_settings_status,
    ensure_runtime_folders,
    load_app_settings,
    parse_mail_recipients,
    save_app_settings_dict,
    update_app_settings,
)
from app.services.audit_service import write_audit_log
from app.services.permission_service import Permission
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
    background-color: rgba(6, 78, 59, 0.26);
    border: 1px solid rgba(16, 185, 129, 0.38);
    border-radius: 14px;
}

QFrame#SystemSettingsWarningCard {
    background-color: rgba(120, 53, 15, 0.26);
    border: 1px solid rgba(245, 158, 11, 0.42);
    border-radius: 14px;
}

QFrame#SystemSettingsRiskCard {
    background-color: rgba(127, 29, 29, 0.26);
    border: 1px solid rgba(248, 113, 113, 0.42);
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

QLabel#SystemSettingsSectionTitle {
    color: #f8fafc;
    font-size: 14px;
    font-weight: 900;
}

QLabel#SystemSettingsSubtitle {
    color: #94a3b8;
    font-size: 12px;
}

QLabel#SystemSettingsFieldLabel {
    color: #bfdbfe;
    font-size: 12px;
    font-weight: 800;
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

QLabel#SystemSettingsFailBadge {
    color: #fecaca;
    font-size: 11px;
    font-weight: 800;
    background-color: rgba(127, 29, 29, 0.40);
    border: 1px solid rgba(248, 113, 113, 0.52);
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

QCheckBox {
    color: #e5e7eb;
    font-size: 12px;
    font-weight: 700;
    spacing: 8px;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 1px solid #cbd5e1;
    background-color: #0b1220;
}

QCheckBox::indicator:checked {
    border: 1px solid #93c5fd;
    background-color: #2563eb;
}

QCheckBox::indicator:disabled {
    border: 1px solid #64748b;
    background-color: #1e293b;
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


class SystemSettingsTab(QWidget):
    def __init__(self) -> None:
        super().__init__()

        self.setStyleSheet(SYSTEM_SETTINGS_TAB_STYLE)

        self.generated_at_label = QLabel("")
        self.generated_at_label.setObjectName("SystemSettingsBadge")

        self.db_status_label = QLabel("DB: Kontrol edilmedi")
        self.db_status_label.setObjectName("SystemSettingsWarnBadge")

        self.folder_status_label = QLabel("Klasör: Kontrol edilmedi")
        self.folder_status_label.setObjectName("SystemSettingsWarnBadge")

        self.mail_status_label = QLabel("Mail: Kontrol edilmedi")
        self.mail_status_label.setObjectName("SystemSettingsWarnBadge")

        self.company_name_input = QLineEdit()
        self.company_address_input = QTextEdit()
        self.company_phone_input = QLineEdit()
        self.company_email_input = QLineEdit()

        self.backup_folder_input = QLineEdit()
        self.export_folder_input = QLineEdit()
        self.log_folder_input = QLineEdit()

        self.control_mail_enabled_checkbox = QCheckBox("Kontrol / uyarı mailleri aktif olsun")
        self.control_mail_to_input = QTextEdit()

        self.report_footer_note_input = QLineEdit()

        self.company_address_input.setFixedHeight(72)
        self.control_mail_to_input.setFixedHeight(72)

        self.settings_table = QTableWidget()
        self.settings_table.setObjectName("SystemSettingsTable")
        self.settings_table.setColumnCount(3)
        self.settings_table.setHorizontalHeaderLabels(["Alan", "Değer", "Durum"])
        self.settings_table.setAlternatingRowColors(True)
        self.settings_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.settings_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.settings_table.verticalHeader().setVisible(False)

        header = self.settings_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)

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
            "Firma bilgileri, klasör yolları, kontrol mail alıcıları ve rapor notu gibi risksiz "
            "ayarlar bu ekrandan yönetilir. Veritabanı şifresi ve SMTP şifresi gibi kritik bilgiler "
            ".env dosyasında kalır."
        )
        subtitle.setObjectName("SystemSettingsSubtitle")
        subtitle.setWordWrap(True)

        card_layout.addLayout(title_row)
        card_layout.addWidget(subtitle)
        card_layout.addLayout(self._build_status_cards())
        card_layout.addLayout(self._build_form_area())
        card_layout.addLayout(self._build_actions())
        card_layout.addWidget(self.settings_table, 1)

        main_layout.addWidget(card, 1)

    def _build_status_cards(self) -> QGridLayout:
        grid = QGridLayout()
        grid.setSpacing(10)

        grid.addWidget(
            self._build_small_card(
                title="Veritabanı",
                body="Bağlantı ve PostgreSQL bilgisi kontrol edilir.",
                badge=self.db_status_label,
                object_name="SystemSettingsInfoCard",
            ),
            0,
            0,
        )

        grid.addWidget(
            self._build_small_card(
                title="Dosya Klasörleri",
                body="Yedek, dışa aktarım ve log klasörleri ayarlanır.",
                badge=self.folder_status_label,
                object_name="SystemSettingsInfoCard",
            ),
            0,
            1,
        )

        grid.addWidget(
            self._build_small_card(
                title="Kontrol Maili",
                body="Sistem kontrol ve uyarı maillerinin alıcıları yönetilir.",
                badge=self.mail_status_label,
                object_name="SystemSettingsInfoCard",
            ),
            0,
            2,
        )

        return grid

    def _build_small_card(
        self,
        *,
        title: str,
        body: str,
        badge: QLabel,
        object_name: str,
    ) -> QWidget:
        card = QFrame()
        card.setObjectName(object_name)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        title_label = QLabel(title)
        title_label.setObjectName("SystemSettingsSectionTitle")

        body_label = QLabel(body)
        body_label.setObjectName("SystemSettingsSubtitle")
        body_label.setWordWrap(True)

        layout.addWidget(title_label)
        layout.addWidget(body_label)
        layout.addStretch(1)
        layout.addWidget(badge, 0, Qt.AlignLeft)

        return card

    def _build_form_area(self) -> QGridLayout:
        grid = QGridLayout()
        grid.setSpacing(12)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        grid.addWidget(self._build_company_group(), 0, 0)
        grid.addWidget(self._build_folder_group(), 0, 1)
        grid.addWidget(self._build_mail_group(), 1, 0)
        grid.addWidget(self._build_report_group(), 1, 1)

        return grid

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

    def _build_folder_group(self) -> QWidget:
        group = QGroupBox("Klasör Ayarları")

        layout = QGridLayout(group)
        layout.setContentsMargins(12, 16, 12, 12)
        layout.setSpacing(8)

        hint = QLabel(
            "Göreli yol yazarsan proje klasörünün altında kullanılır. "
            "Örnek: backups, exports, logs"
        )
        hint.setObjectName("SystemSettingsSubtitle")
        hint.setWordWrap(True)

        layout.addWidget(hint, 0, 0, 1, 2)

        layout.addWidget(self._field_label("Yedek Klasörü"), 1, 0)
        layout.addWidget(self.backup_folder_input, 1, 1)

        layout.addWidget(self._field_label("Export Klasörü"), 2, 0)
        layout.addWidget(self.export_folder_input, 2, 1)

        layout.addWidget(self._field_label("Log Klasörü"), 3, 0)
        layout.addWidget(self.log_folder_input, 3, 1)

        return group

    def _build_mail_group(self) -> QWidget:
        group = QGroupBox("Kontrol Mail Ayarları")

        layout = QVBoxLayout(group)
        layout.setContentsMargins(12, 16, 12, 12)
        layout.setSpacing(8)

        hint = QLabel(
            "Birden fazla alıcı için e-posta adreslerini virgül, noktalı virgül veya boşlukla ayırabilirsin."
        )
        hint.setObjectName("SystemSettingsSubtitle")
        hint.setWordWrap(True)

        layout.addWidget(self.control_mail_enabled_checkbox)
        layout.addWidget(hint)
        layout.addWidget(self.control_mail_to_input)

        return group

    def _build_report_group(self) -> QWidget:
        group = QGroupBox("Rapor Ayarları")

        layout = QGridLayout(group)
        layout.setContentsMargins(12, 16, 12, 12)
        layout.setSpacing(8)

        hint = QLabel(
            "Raporlarda kullanılacak güvenli not alanı. Logo ve gelişmiş rapor kimliği sonraki adımda eklenebilir."
        )
        hint.setObjectName("SystemSettingsSubtitle")
        hint.setWordWrap(True)

        layout.addWidget(hint, 0, 0, 1, 2)

        layout.addWidget(self._field_label("Rapor Alt Notu"), 1, 0)
        layout.addWidget(self.report_footer_note_input, 1, 1)

        return group

    def _build_actions(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(10)

        hint = QLabel(
            f"Ayar dosyası: {app_settings_file_path()}"
        )
        hint.setObjectName("SystemSettingsSubtitle")
        hint.setWordWrap(True)

        layout.addWidget(hint, 1)
        layout.addWidget(self.refresh_button, 0, Qt.AlignVCenter)
        layout.addWidget(self.create_folders_button, 0, Qt.AlignVCenter)
        layout.addWidget(self.reset_defaults_button, 0, Qt.AlignVCenter)
        layout.addWidget(self.save_button, 0, Qt.AlignVCenter)

        return layout

    def _field_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("SystemSettingsFieldLabel")
        label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        return label

    def load_settings(self) -> None:
        try:
            app_settings = load_app_settings()

            self.company_name_input.setText(app_settings.company_name)
            self.company_address_input.setPlainText(app_settings.company_address)
            self.company_phone_input.setText(app_settings.company_phone)
            self.company_email_input.setText(app_settings.company_email)

            self.backup_folder_input.setText(app_settings.backup_folder)
            self.export_folder_input.setText(app_settings.export_folder)
            self.log_folder_input.setText(app_settings.log_folder)

            self.control_mail_enabled_checkbox.setChecked(app_settings.control_mail_enabled)
            self.control_mail_to_input.setPlainText(app_settings.control_mail_to)

            self.report_footer_note_input.setText(app_settings.report_footer_note)

            rows = self._build_status_rows()
            self._fill_table(rows)
            self._update_badges(rows)
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

        backup_folder = self.backup_folder_input.text().strip()
        export_folder = self.export_folder_input.text().strip()
        log_folder = self.log_folder_input.text().strip()

        control_mail_enabled = self.control_mail_enabled_checkbox.isChecked()
        control_mail_to = self.control_mail_to_input.toPlainText().strip()

        report_footer_note = self.report_footer_note_input.text().strip()

        if not company_name:
            QMessageBox.warning(
                self,
                "Eksik Bilgi",
                "Firma adı boş olamaz.",
            )
            return

        if control_mail_enabled and not parse_mail_recipients(control_mail_to):
            QMessageBox.warning(
                self,
                "Kontrol Mail Alıcısı Eksik",
                "Kontrol maili aktifse en az bir geçerli mail alıcısı yazmalısın.",
            )
            return

        try:
            saved_settings = update_app_settings(
                company_name=company_name,
                company_address=company_address,
                company_phone=company_phone,
                company_email=company_email,
                backup_folder=backup_folder,
                export_folder=export_folder,
                log_folder=log_folder,
                control_mail_enabled=control_mail_enabled,
                control_mail_to=control_mail_to,
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
            "Risksiz uygulama ayarları varsayılan değerlere döndürülecek.\n\n"
            "Bu işlem veritabanı ayarlarını, şifreleri veya .env dosyasını değiştirmez.\n\n"
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
            self.backup_folder_input,
            self.export_folder_input,
            self.log_folder_input,
            self.control_mail_enabled_checkbox,
            self.control_mail_to_input,
            self.report_footer_note_input,
            self.save_button,
            self.create_folders_button,
            self.reset_defaults_button,
        ]

        for widget in editable_widgets:
            set_widget_permission(
                widget,
                allowed=can_update,
                tooltip_when_denied="Sistem ayarlarını değiştirmek için SYSTEM_SETTINGS_UPDATE yetkisi gerekir.",
            )

    def _build_status_rows(self) -> list[tuple[str, str, str]]:
        rows: list[tuple[str, str, str]] = []

        rows.extend(self._application_rows())
        rows.extend(self._database_rows())
        rows.extend(self._runtime_settings_rows())
        rows.extend(self._env_mail_rows())

        return rows

    def _application_rows(self) -> list[tuple[str, str, str]]:
        return [
            ("Uygulama Adı", settings.app_name, "OK" if settings.app_name else "WARN"),
            ("Uygulama Ortamı", settings.app_env, "OK" if settings.app_env else "WARN"),
            ("Debug Modu", "Açık" if settings.app_debug else "Kapalı", "WARN" if settings.app_debug else "OK"),
            ("Proje Ana Klasörü", str(BASE_DIR), "OK" if BASE_DIR.exists() else "FAIL"),
            (".env Dosyası", str(ENV_FILE), "OK" if ENV_FILE.exists() else "FAIL"),
            ("Uygulama Ayar Dosyası", str(app_settings_file_path()), "OK" if app_settings_file_path().exists() else "WARN"),
        ]

    def _database_rows(self) -> list[tuple[str, str, str]]:
        rows: list[tuple[str, str, str]] = []

        if settings.is_sqlite:
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
                        "PostgreSQL Host",
                        "SQLite modunda gerekli değil",
                        "OK",
                    ),
                    (
                        "PostgreSQL Port",
                        "SQLite modunda gerekli değil",
                        "OK",
                    ),
                    (
                        "PostgreSQL User",
                        "SQLite modunda gerekli değil",
                        "OK",
                    ),
                    (
                        "DB Echo",
                        "Açık" if settings.database_echo else "Kapalı",
                        "WARN" if settings.database_echo else "OK",
                    ),
                ]
            )

        else:
            rows.extend(
                [
                    (
                        "DB Motoru",
                        "PostgreSQL",
                        "OK",
                    ),
                    (
                        "DB Host",
                        settings.database_host,
                        "OK" if settings.database_host else "FAIL",
                    ),
                    (
                        "DB Port",
                        str(settings.database_port),
                        "OK" if settings.database_port else "FAIL",
                    ),
                    (
                        "DB Name",
                        settings.database_name,
                        "OK" if settings.database_name else "FAIL",
                    ),
                    (
                        "DB User",
                        settings.database_user,
                        "OK" if settings.database_user else "FAIL",
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
                        "DB Aktif Veritabanı",
                        str(db_info.get("database_name", "-")),
                        "OK",
                    ),
                    (
                        "DB Aktif Kullanıcı",
                        str(db_info.get("user_name", "-")),
                        "OK",
                    ),
                    (
                        "DB Sunucu Portu",
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
        mail_status = "Açık" if settings.mail_enabled else "Kapalı"

        rows = [
            ("SMTP Mail Durumu", mail_status, "OK" if settings.mail_enabled else "WARN"),
            ("SMTP Sunucu", settings.mail_server or "-", "OK" if settings.mail_server else "WARN"),
            ("SMTP Port", str(settings.mail_port), "OK" if settings.mail_port else "WARN"),
            ("SMTP TLS", "Açık" if settings.mail_use_tls else "Kapalı", "OK" if settings.mail_use_tls else "WARN"),
            ("SMTP Kullanıcı", settings.mail_username or "-", "OK" if settings.mail_enabled and settings.mail_username else "WARN"),
            ("SMTP Gönderen", settings.mail_from or "-", "OK" if settings.mail_enabled and settings.mail_from else "WARN"),
        ]

        if not settings.mail_enabled:
            rows.append(("SMTP Açıklama", "SMTP mail kapalı. Kontrol mail alıcıları kaydedilebilir ama gönderim yapılamaz.", "WARN"))

        return rows

    def _fill_table(self, rows: list[tuple[str, str, str]]) -> None:
        self.settings_table.setRowCount(len(rows))

        for row_index, (field_name, value, status) in enumerate(rows):
            field_item = QTableWidgetItem(field_name)
            value_item = QTableWidgetItem(value)
            status_item = QTableWidgetItem(status)

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

            self.settings_table.setItem(row_index, 0, field_item)
            self.settings_table.setItem(row_index, 1, value_item)
            self.settings_table.setItem(row_index, 2, status_item)

        self.settings_table.resizeRowsToContents()

    def _update_badges(self, rows: list[tuple[str, str, str]]) -> None:
        now_text = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        self.generated_at_label.setText(f"Güncelleme: {now_text}")

        db_statuses = [
            status
            for field_name, _value, status in rows
            if field_name.startswith("DB ")
        ]

        folder_statuses = [
            status
            for field_name, _value, status in rows
            if "Klasörü" in field_name
        ]

        mail_statuses = [
            status
            for field_name, _value, status in rows
            if "Mail" in field_name or "SMTP" in field_name or "Kontrol Mail" in field_name
        ]

        self._set_badge(
            self.db_status_label,
            prefix="DB",
            statuses=db_statuses,
        )

        self._set_badge(
            self.folder_status_label,
            prefix="Klasör",
            statuses=folder_statuses,
        )

        self._set_badge(
            self.mail_status_label,
            prefix="Mail",
            statuses=mail_statuses,
        )

    def _set_badge(
        self,
        label: QLabel,
        *,
        prefix: str,
        statuses: list[str],
    ) -> None:
        if not statuses:
            label.setText(f"{prefix}: WARN")
            label.setObjectName("SystemSettingsWarnBadge")
            self._refresh_widget_style(label)
            return

        if "FAIL" in statuses:
            label.setText(f"{prefix}: FAIL")
            label.setObjectName("SystemSettingsFailBadge")
            self._refresh_widget_style(label)
            return

        if "WARN" in statuses:
            label.setText(f"{prefix}: WARN")
            label.setObjectName("SystemSettingsWarnBadge")
            self._refresh_widget_style(label)
            return

        label.setText(f"{prefix}: OK")
        label.setObjectName("SystemSettingsOkBadge")
        self._refresh_widget_style(label)

    def _refresh_widget_style(self, widget: QWidget) -> None:
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        widget.update()

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


def build_system_settings_tab() -> QWidget:
    return SystemSettingsTab()


__all__ = [
    "SystemSettingsTab",
    "build_system_settings_tab",
]