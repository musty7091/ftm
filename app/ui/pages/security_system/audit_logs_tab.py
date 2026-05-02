from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.db.session import session_scope
from app.models.audit_log import AuditLog


AUDIT_LOGS_TAB_STYLE = """
QFrame#AuditLogsTabCard {
    background-color: #111827;
    border: 1px solid #24324a;
    border-radius: 18px;
}

QFrame#AuditLogsToolbar {
    background-color: rgba(15, 23, 42, 0.64);
    border: 1px solid rgba(148, 163, 184, 0.22);
    border-radius: 14px;
}

QLabel#AuditLogsTitle {
    color: #f8fafc;
    font-size: 16px;
    font-weight: 900;
}

QLabel#AuditLogsSubtitle {
    color: #94a3b8;
    font-size: 12px;
}

QLabel#AuditLogsCountBadge {
    color: #dbeafe;
    font-size: 11px;
    font-weight: 800;
    background-color: rgba(30, 64, 175, 0.32);
    border: 1px solid rgba(59, 130, 246, 0.42);
    border-radius: 8px;
    padding: 5px 9px;
}

QPushButton#AuditLogsRefreshButton {
    background-color: #2563eb;
    color: #ffffff;
    border: 1px solid #3b82f6;
    border-radius: 11px;
    padding: 8px 14px;
    font-weight: 900;
}

QPushButton#AuditLogsRefreshButton:hover {
    background-color: #1d4ed8;
}

QPushButton#AuditLogsPassiveButton {
    background-color: #1f2937;
    color: #94a3b8;
    border: 1px solid #334155;
    border-radius: 10px;
    padding: 8px 12px;
    font-weight: 800;
}

QPushButton#AuditLogsPassiveButton:disabled {
    background-color: rgba(30, 41, 59, 0.55);
    color: #64748b;
    border: 1px solid rgba(100, 116, 139, 0.32);
}

QTableWidget#AuditLogsTable {
    background-color: #0f172a;
    color: #e5e7eb;
    border: 1px solid #334155;
    border-radius: 12px;
    gridline-color: #334155;
    selection-background-color: #2563eb;
    selection-color: #ffffff;
    alternate-background-color: #111827;
}

QTableWidget#AuditLogsTable::item {
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


class AuditLogsTab(QWidget):
    def __init__(self) -> None:
        super().__init__()

        self.setStyleSheet(AUDIT_LOGS_TAB_STYLE)

        self.log_count_label = QLabel("0 kayıt")
        self.log_count_label.setObjectName("AuditLogsCountBadge")

        self.table = QTableWidget()
        self.table.setObjectName("AuditLogsTable")
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels(
            [
                "Tarih",
                "Kullanıcı",
                "İşlem",
                "Varlık",
                "Kayıt ID",
                "Açıklama",
                "Eski Değer",
                "Yeni Değer",
                "IP",
            ]
        )
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setWordWrap(False)

        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.Stretch)
        header.setSectionResizeMode(6, QHeaderView.Stretch)
        header.setSectionResizeMode(7, QHeaderView.Stretch)
        header.setSectionResizeMode(8, QHeaderView.ResizeToContents)

        self._build_ui()
        self.load_audit_logs()

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 14, 12, 12)
        main_layout.setSpacing(12)

        card = QFrame()
        card.setObjectName("AuditLogsTabCard")

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 16, 18, 16)
        card_layout.setSpacing(14)

        title = QLabel("İşlem Kayıtları")
        title.setObjectName("AuditLogsTitle")

        subtitle = QLabel(
            "Bu ekranda sistemde yapılan kritik işlemler listelenir. "
            "Kullanıcı yönetimi, giriş denemeleri, aktif/pasif işlemleri, şifre sıfırlama "
            "ve diğer önemli hareketler burada izlenir."
        )
        subtitle.setObjectName("AuditLogsSubtitle")
        subtitle.setWordWrap(True)

        toolbar = self._build_toolbar()

        info_button = QPushButton("Şifrelerin kendisi audit log içinde tutulmaz; sadece şifre sıfırlama işlemi kaydedilir")
        info_button.setObjectName("AuditLogsPassiveButton")
        info_button.setEnabled(False)

        card_layout.addWidget(title)
        card_layout.addWidget(subtitle)
        card_layout.addWidget(toolbar)
        card_layout.addWidget(self.table, 1)
        card_layout.addWidget(info_button, 0, Qt.AlignRight)

        main_layout.addWidget(card, 1)

    def _build_toolbar(self) -> QWidget:
        toolbar = QFrame()
        toolbar.setObjectName("AuditLogsToolbar")

        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        info = QLabel(
            "Son 300 işlem gösterilir. Listeyi Yenile butonu veritabanından kayıtları tekrar okur."
        )
        info.setObjectName("AuditLogsSubtitle")
        info.setWordWrap(True)

        refresh_button = QPushButton("Listeyi Yenile")
        refresh_button.setObjectName("AuditLogsRefreshButton")
        refresh_button.clicked.connect(self.load_audit_logs)

        layout.addWidget(info, 1)
        layout.addWidget(self.log_count_label, 0, Qt.AlignVCenter)
        layout.addWidget(refresh_button, 0, Qt.AlignVCenter)

        return toolbar

    def load_audit_logs(self) -> None:
        try:
            logs = self._fetch_audit_logs()
            self._fill_table(logs)
            self.log_count_label.setText(f"{len(logs)} kayıt")
        except Exception as exc:
            QMessageBox.critical(
                self,
                "İşlem Kayıtları Okunamadı",
                f"İşlem kayıtları okunurken hata oluştu:\n\n{exc}",
            )

    def _fetch_audit_logs(self) -> list[AuditLog]:
        with session_scope() as session:
            statement = (
                select(AuditLog)
                .options(joinedload(AuditLog.user))
                .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
                .limit(300)
            )

            logs = session.execute(statement).scalars().all()

            return list(logs)

    def _fill_table(self, logs: list[AuditLog]) -> None:
        self.table.setRowCount(0)

        for row_index, log in enumerate(logs):
            self.table.insertRow(row_index)

            username = "-"
            if log.user is not None:
                username = str(log.user.username or "-")

            values = [
                self._format_datetime(log.created_at),
                username,
                self._action_text(log.action),
                str(log.entity_type or "-"),
                "-" if log.entity_id is None else str(log.entity_id),
                str(log.description or "-"),
                self._format_json_value(log.old_values),
                self._format_json_value(log.new_values),
                str(log.ip_address or "-"),
            ]

            for column_index, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)

                if column_index in {0, 2, 3, 4, 8}:
                    item.setTextAlignment(Qt.AlignCenter)

                self.table.setItem(row_index, column_index, item)

        self.table.resizeRowsToContents()

    def _action_text(self, action: Any) -> str:
        action_text = str(action or "").strip()

        action_map = {
            "LOGIN_SUCCESS": "Giriş Başarılı",
            "LOGIN_FAILED": "Giriş Başarısız",
            "USER_CREATED": "Kullanıcı Oluşturuldu",
            "USER_UPDATED": "Kullanıcı Güncellendi",
            "USER_ACTIVATED": "Kullanıcı Aktif Yapıldı",
            "USER_DEACTIVATED": "Kullanıcı Pasif Yapıldı",
            "USER_PASSWORD_RESET": "Şifre Sıfırlandı",
        }

        return action_map.get(action_text, action_text or "-")

    def _format_json_value(self, value: Any) -> str:
        if value is None:
            return "-"

        try:
            return json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                default=str,
            )
        except Exception:
            return str(value)

    def _format_datetime(self, value: Any) -> str:
        if value is None:
            return "-"

        if isinstance(value, datetime):
            try:
                if value.tzinfo is None:
                    value = value.replace(tzinfo=timezone.utc)

                local_value = value.astimezone()
                return local_value.strftime("%d.%m.%Y %H:%M:%S")
            except Exception:
                return value.strftime("%d.%m.%Y %H:%M:%S")

        return str(value)


def build_audit_logs_tab() -> QWidget:
    return AuditLogsTab()


__all__ = [
    "AuditLogsTab",
    "build_audit_logs_tab",
]