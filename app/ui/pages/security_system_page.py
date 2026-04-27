from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.ui.navigation import role_to_text, username_to_text
from app.ui.pages.placeholder_page import AccessDeniedPage
from app.ui.pages.security_system import (
    SECURITY_SYSTEM_PAGE_STYLE,
    build_audit_logs_tab,
    build_backup_tab,
    build_login_logs_tab,
    build_roles_tab,
    build_system_settings_tab,
    build_users_tab,
)


class SecuritySystemPage(QWidget):
    def __init__(self, current_user: Any | None = None) -> None:
        super().__init__()

        self.current_user = current_user
        self.current_role = role_to_text(current_user.role if current_user else None)
        self.current_username = username_to_text(current_user)

        self.setStyleSheet(SECURITY_SYSTEM_PAGE_STYLE)

        if self.current_role != "ADMIN":
            blocked_layout = QVBoxLayout(self)
            blocked_layout.setContentsMargins(0, 0, 0, 0)
            blocked_layout.setSpacing(0)

            blocked_layout.addWidget(
                AccessDeniedPage(
                    username=self.current_username,
                    role=self.current_role,
                )
            )
            return

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(16)

        main_layout.addWidget(self._build_hero())

        tabs = QTabWidget()
        tabs.setObjectName("SecuritySystemTabs")

        tabs.addTab(build_users_tab(), "Kullanıcılar")
        tabs.addTab(build_roles_tab(), "Roller / Yetkiler")
        tabs.addTab(build_login_logs_tab(), "Giriş Kayıtları")
        tabs.addTab(build_audit_logs_tab(), "İşlem Kayıtları")
        tabs.addTab(build_system_settings_tab(), "Sistem Ayarları")
        tabs.addTab(build_backup_tab(), "Yedekleme")

        main_layout.addWidget(tabs, 1)

    def _build_hero(self) -> QWidget:
        hero = QFrame()
        hero.setObjectName("SecuritySystemHero")

        layout = QVBoxLayout(hero)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(10)

        title_row = QHBoxLayout()
        title_row.setSpacing(10)

        title = QLabel("Güvenlik ve Sistem Yönetimi")
        title.setObjectName("SecuritySystemTitle")

        badge = QLabel("Sadece ADMIN")
        badge.setObjectName("SecuritySystemAdminBadge")

        title_row.addWidget(title, 1)
        title_row.addWidget(badge, 0, Qt.AlignVCenter)

        subtitle = QLabel(
            "Kullanıcı yönetimi, roller, giriş kayıtları, işlem geçmişi, sistem ayarları "
            "ve yedekleme süreçleri bu tek merkezden yönetilecek."
        )
        subtitle.setObjectName("SecuritySystemSubTitle")
        subtitle.setWordWrap(True)

        layout.addLayout(title_row)
        layout.addWidget(subtitle)

        return hero


__all__ = [
    "SecuritySystemPage",
]