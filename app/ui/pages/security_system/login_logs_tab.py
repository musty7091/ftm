from __future__ import annotations

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


LOGIN_LOGS_TAB_STYLE = """
QFrame#LoginLogsTabCard {
    background-color: #111827;
    border: 1px solid #24324a;
    border-radius: 18px;
}

QFrame#LoginLogsToolbar {
    background-color: rgba(15, 23, 42, 0.64);
    border: 1px solid rgba(148, 163, 184, 0.22);
    border-radius: 14px;
}

QLabel#LoginLogsTitle {
    color: #f8fafc;
    font-size: 16px;
    font-weight: 900;
}

QLabel#LoginLogsSubtitle {
    color: #94a3b8;
    font-size: 12px;
}

QLabel#LoginLogsCountBadge {
    color: #dbeafe;
    font-size: 11px;
    font-weight: 800;
    background-color: rgba(30, 64, 175, 0.32);
    border: 1px solid rgba(59, 130, 246, 0.42);
    border-radius: 8px;
    padding: 5px 9px;
}

QPushButton#LoginLogsRefreshButton {
    background-color: #2563eb;
    color: #ffffff;
    border: 1px solid #3b82f6;
    border-radius: 11px;
    padding: 8px 14px;
    font-weight: 900;
}

QPushButton#LoginLogsRefreshButton:hover {
    background-color: #1d4ed8;
}

QPushButton#LoginLogsPassiveButton {
    background-color: #1f2937;
    color: #94a3b8;
    border: 1px solid #334155;
    border-radius: 10px;
    padding: 8px 12px;
    font-weight: 800;
}

QPushButton#LoginLogsPassiveButton:disabled {
    background-color: rgba(30, 41, 59, 0.55);
    color: #64748b;
    border: 1px solid rgba(100, 116, 139, 0.32);
}

QTableWidget#LoginLogsTable {
    background-color: #0f172a;
    color: #e5e7eb;
    border: 1px solid #334155;
    border-radius: 12px;
    gridline-color: #334155;
    selection-background-color: #2563eb;
    selection-color: #ffffff;
    alternate-background-color: #111827;
}

QTableWidget#LoginLogsTable::item {
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


class LoginLogsTab(QWidget):
    def __init__(self) -> None:
        super().__init__()

        self.setStyleSheet(LOGIN_LOGS_TAB_STYLE)

        self.log_count_label = QLabel("0 kayıt")
        self.log_count_label.setObjectName("LoginLogsCountBadge")

        self.table = QTableWidget()
        self.table.setObjectName("LoginLogsTable")
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(
            [
                "Tarih",
                "Kullanıcı",
                "Sonuç",
                "Sebep",
                "Rol",
                "Açıklama",
                "Kayıt ID",
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
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)

        self._build_ui()
        self.load_login_logs()

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 14, 12, 12)
        main_layout.setSpacing(12)

        card = QFrame()
        card.setObjectName("LoginLogsTabCard")

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 16, 18, 16)
        card_layout.setSpacing(14)

        title = QLabel("Giriş Kayıtları")
        title.setObjectName("LoginLogsTitle")

        subtitle = QLabel(
            "Bu ekranda yalnızca kullanıcı giriş hareketleri gösterilir. "
            "Başarılı girişler ve başarısız giriş denemeleri burada sade şekilde izlenir."
        )
        subtitle.setObjectName("LoginLogsSubtitle")
        subtitle.setWordWrap(True)

        toolbar = self._build_toolbar()

        info_button = QPushButton(
            "Bu ekran sadece LOGIN_SUCCESS ve LOGIN_FAILED kayıtlarını gösterir"
        )
        info_button.setObjectName("LoginLogsPassiveButton")
        info_button.setEnabled(False)

        card_layout.addWidget(title)
        card_layout.addWidget(subtitle)
        card_layout.addWidget(toolbar)
        card_layout.addWidget(self.table, 1)
        card_layout.addWidget(info_button, 0, Qt.AlignRight)

        main_layout.addWidget(card, 1)

    def _build_toolbar(self) -> QWidget:
        toolbar = QFrame()
        toolbar.setObjectName("LoginLogsToolbar")

        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        info = QLabel(
            "Son 300 giriş kaydı gösterilir. Listeyi Yenile butonu veritabanından giriş kayıtlarını tekrar okur."
        )
        info.setObjectName("LoginLogsSubtitle")
        info.setWordWrap(True)

        refresh_button = QPushButton("Listeyi Yenile")
        refresh_button.setObjectName("LoginLogsRefreshButton")
        refresh_button.clicked.connect(self.load_login_logs)

        layout.addWidget(info, 1)
        layout.addWidget(self.log_count_label, 0, Qt.AlignVCenter)
        layout.addWidget(refresh_button, 0, Qt.AlignVCenter)

        return toolbar

    def load_login_logs(self) -> None:
        try:
            logs = self._fetch_login_logs()
            self._fill_table(logs)
            self.log_count_label.setText(f"{len(logs)} kayıt")
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Giriş Kayıtları Okunamadı",
                f"Giriş kayıtları okunurken hata oluştu:\n\n{exc}",
            )

    def _fetch_login_logs(self) -> list[AuditLog]:
        with session_scope() as session:
            statement = (
                select(AuditLog)
                .options(joinedload(AuditLog.user))
                .where(AuditLog.action.in_(["LOGIN_SUCCESS", "LOGIN_FAILED"]))
                .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
                .limit(300)
            )

            logs = session.execute(statement).scalars().all()

            return list(logs)

    def _fill_table(self, logs: list[AuditLog]) -> None:
        self.table.setRowCount(0)

        for row_index, log in enumerate(logs):
            self.table.insertRow(row_index)

            values = [
                self._format_datetime(log.created_at),
                self._username_text(log),
                self._result_text(log.action),
                self._reason_text(log),
                self._role_text(log),
                str(log.description or "-"),
                str(log.id or "-"),
            ]

            for column_index, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)

                if column_index in {0, 2, 3, 4, 6}:
                    item.setTextAlignment(Qt.AlignCenter)

                self.table.setItem(row_index, column_index, item)

        self.table.resizeRowsToContents()

    def _username_text(self, log: AuditLog) -> str:
        if log.user is not None:
            username = getattr(log.user, "username", None)

            if username:
                return str(username)

        values = self._safe_dict(log.new_values)

        username = values.get("username")
        if username:
            return str(username)

        identifier = values.get("identifier")
        if identifier:
            return str(identifier)

        return "-"

    def _result_text(self, action: Any) -> str:
        action_text = str(action or "").strip()

        if action_text == "LOGIN_SUCCESS":
            return "Başarılı"

        if action_text == "LOGIN_FAILED":
            return "Başarısız"

        return action_text or "-"

    def _reason_text(self, log: AuditLog) -> str:
        values = self._safe_dict(log.new_values)
        reason = str(values.get("reason") or "").strip()

        reason_map = {
            "USER_NOT_FOUND": "Kullanıcı Bulunamadı",
            "USER_PASSIVE": "Kullanıcı Pasif",
            "INVALID_PASSWORD": "Hatalı Şifre",
        }

        if reason:
            return reason_map.get(reason, reason)

        if str(log.action or "") == "LOGIN_SUCCESS":
            return "-"

        return "-"

    def _role_text(self, log: AuditLog) -> str:
        values = self._safe_dict(log.new_values)
        role = values.get("role")

        if role:
            return str(role)

        if log.user is not None:
            user_role = getattr(log.user, "role", None)

            if hasattr(user_role, "value"):
                return str(user_role.value)

            if user_role:
                return str(user_role)

        return "-"

    def _safe_dict(self, value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return value

        return {}

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


def build_login_logs_tab() -> QWidget:
    return LoginLogsTab()


__all__ = [
    "LoginLogsTab",
    "build_login_logs_tab",
]