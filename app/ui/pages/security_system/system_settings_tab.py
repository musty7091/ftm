from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QHeaderView,
)

from app.core.config import BASE_DIR, ENV_FILE, settings
from app.db.session import check_database_connection
from app.services.permission_service import Permission
from app.ui.permission_ui import (
    apply_permission_to_button,
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

QPushButton#SystemSettingsSuccessButton:disabled {
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

        self.mail_status_label = QLabel("")
        self.mail_status_label.setObjectName("SystemSettingsBadge")

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

        self.create_folders_button = QPushButton("Klasörleri Kontrol Et / Oluştur")
        self.create_folders_button.setObjectName("SystemSettingsSuccessButton")
        self.create_folders_button.clicked.connect(self.create_required_folders)

        apply_permission_to_button(
            self.create_folders_button,
            current_user=self._current_user(),
            permission=Permission.SYSTEM_SETTINGS_UPDATE,
            tooltip_when_denied="Sistem klasörlerini oluşturmak için SYSTEM_SETTINGS_UPDATE yetkisi gerekir.",
        )

        self._build_ui()
        self.load_settings()

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
            "Uygulama ortamı, veritabanı bağlantısı, klasör yolları ve mail ayarları burada izlenir. "
            "Bu ekran ayar dosyasını değiştirmez; güvenli şekilde mevcut durumu gösterir."
        )
        subtitle.setObjectName("SystemSettingsSubtitle")
        subtitle.setWordWrap(True)

        card_layout.addLayout(title_row)
        card_layout.addWidget(subtitle)
        card_layout.addLayout(self._build_status_cards())
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
                body="Yedek, dışa aktarım ve log klasörleri kontrol edilir.",
                badge=self.folder_status_label,
                object_name="SystemSettingsInfoCard",
            ),
            0,
            1,
        )

        grid.addWidget(
            self._build_small_card(
                title="Mail",
                body="Mail açık/kapalı durumu ve alıcı bilgisi gösterilir.",
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

    def _build_actions(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(10)

        hint = QLabel(
            "Not: .env içeriği güvenlik sebebiyle doğrudan düzenlenmez. "
            "Bu ekran sadece güvenli özet gösterir."
        )
        hint.setObjectName("SystemSettingsSubtitle")
        hint.setWordWrap(True)

        layout.addWidget(hint, 1)
        layout.addWidget(self.refresh_button, 0, Qt.AlignVCenter)
        layout.addWidget(self.create_folders_button, 0, Qt.AlignVCenter)

        return layout

    def load_settings(self) -> None:
        rows: list[tuple[str, str, str]] = []

        rows.extend(self._application_rows())
        rows.extend(self._database_rows())
        rows.extend(self._folder_rows())
        rows.extend(self._mail_rows())

        self._fill_table(rows)
        self._update_badges(rows)

    def create_required_folders(self) -> None:
        if not user_has_permission(
            current_user=self._current_user(),
            permission=Permission.SYSTEM_SETTINGS_UPDATE,
        ):
            QMessageBox.warning(
                self,
                "Yetkisiz işlem",
                "Sistem klasörlerini oluşturmak için SYSTEM_SETTINGS_UPDATE yetkisi gerekir.",
            )
            return

        folders = [
            settings.backup_folder,
            settings.export_folder,
            settings.log_folder,
        ]

        try:
            for folder in folders:
                Path(folder).mkdir(parents=True, exist_ok=True)

            QMessageBox.information(
                self,
                "Klasörler Hazır",
                "Yedek, dışa aktarım ve log klasörleri kontrol edildi / oluşturuldu.",
            )

            self.load_settings()

        except Exception as exc:
            QMessageBox.critical(
                self,
                "Klasör Oluşturulamadı",
                f"Sistem klasörleri oluşturulurken hata oluştu:\n\n{exc}",
            )

    def _application_rows(self) -> list[tuple[str, str, str]]:
        return [
            ("Uygulama Adı", settings.app_name, "OK" if settings.app_name else "WARN"),
            ("Uygulama Ortamı", settings.app_env, "OK" if settings.app_env else "WARN"),
            ("Debug Modu", "Açık" if settings.app_debug else "Kapalı", "WARN" if settings.app_debug else "OK"),
            ("Proje Ana Klasörü", str(BASE_DIR), "OK" if BASE_DIR.exists() else "FAIL"),
            (".env Dosyası", str(ENV_FILE), "OK" if ENV_FILE.exists() else "FAIL"),
        ]

    def _database_rows(self) -> list[tuple[str, str, str]]:
        rows = [
            ("DB Host", settings.database_host, "OK" if settings.database_host else "FAIL"),
            ("DB Port", str(settings.database_port), "OK" if settings.database_port else "FAIL"),
            ("DB Name", settings.database_name, "OK" if settings.database_name else "FAIL"),
            ("DB User", settings.database_user, "OK" if settings.database_user else "FAIL"),
            ("DB Echo", "Açık" if settings.database_echo else "Kapalı", "WARN" if settings.database_echo else "OK"),
        ]

        try:
            db_info = check_database_connection()

            rows.extend(
                [
                    ("DB Bağlantı", "Başarılı", "OK"),
                    ("DB Aktif Veritabanı", str(db_info.get("database_name", "-")), "OK"),
                    ("DB Aktif Kullanıcı", str(db_info.get("user_name", "-")), "OK"),
                    ("DB Sunucu Portu", str(db_info.get("server_port", "-")), "OK"),
                    ("DB Sürüm", str(db_info.get("version_text", "-")), "OK"),
                ]
            )

        except Exception as exc:
            rows.append(("DB Bağlantı", str(exc), "FAIL"))

        return rows

    def _folder_rows(self) -> list[tuple[str, str, str]]:
        return [
            self._folder_row("Yedek Klasörü", settings.backup_folder),
            self._folder_row("Dışa Aktarım Klasörü", settings.export_folder),
            self._folder_row("Log Klasörü", settings.log_folder),
        ]

    def _folder_row(self, label: str, folder: Path) -> tuple[str, str, str]:
        folder_path = Path(folder)

        if folder_path.exists() and folder_path.is_dir():
            return (label, str(folder_path), "OK")

        return (label, str(folder_path), "WARN")

    def _mail_rows(self) -> list[tuple[str, str, str]]:
        mail_status = "Açık" if settings.mail_enabled else "Kapalı"

        rows = [
            ("Mail Durumu", mail_status, "OK" if settings.mail_enabled else "WARN"),
            ("Mail Sunucu", settings.mail_server or "-", "OK" if settings.mail_server else "WARN"),
            ("Mail Port", str(settings.mail_port), "OK" if settings.mail_port else "WARN"),
            ("Mail TLS", "Açık" if settings.mail_use_tls else "Kapalı", "OK" if settings.mail_use_tls else "WARN"),
            ("Mail Kullanıcı", settings.mail_username or "-", "OK" if settings.mail_enabled and settings.mail_username else "WARN"),
            ("Mail Gönderen", settings.mail_from or "-", "OK" if settings.mail_enabled and settings.mail_from else "WARN"),
            ("Mail Alıcı", settings.mail_to or "-", "OK" if settings.mail_enabled and settings.mail_to else "WARN"),
        ]

        if not settings.mail_enabled:
            rows.append(("Mail Açıklama", "Mail kapalı. Bu geliştirme ortamında sorun olmayabilir.", "WARN"))

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
                status_item.setForeground(Qt.green)
            elif status == "WARN":
                status_item.setForeground(Qt.yellow)
            else:
                status_item.setForeground(Qt.red)

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
            if field_name.startswith("Mail")
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

    def _current_user(self) -> Any | None:
        window = self.window()

        if window is None:
            return None

        return getattr(window, "current_user", None)


def build_system_settings_tab() -> QWidget:
    return SystemSettingsTab()


__all__ = [
    "SystemSettingsTab",
    "build_system_settings_tab",
]