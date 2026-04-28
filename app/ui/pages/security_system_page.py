from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import Qt, QTimer
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

        self.tabs: QTabWidget | None = None
        self._tab_builders: dict[int, Callable[[], QWidget]] = {}
        self._loaded_tab_indexes: set[int] = set()
        self._loading_tab_indexes: set[int] = set()

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

        self.tabs = QTabWidget()
        self.tabs.setObjectName("SecuritySystemTabs")

        self._register_tab("Kullanıcılar", build_users_tab)
        self._register_tab("Roller / Yetkiler", build_roles_tab)
        self._register_tab("Giriş Kayıtları", build_login_logs_tab)
        self._register_tab("İşlem Kayıtları", build_audit_logs_tab)
        self._register_tab("Sistem Ayarları", build_system_settings_tab)
        self._register_tab("Yedekleme", build_backup_tab)

        self.tabs.currentChanged.connect(self._on_tab_changed)

        main_layout.addWidget(self.tabs, 1)

        QTimer.singleShot(0, self._load_current_tab)

    def _register_tab(
        self,
        title: str,
        builder: Callable[[], QWidget],
    ) -> None:
        if self.tabs is None:
            return

        placeholder = self._build_lazy_placeholder(title)
        tab_index = self.tabs.addTab(placeholder, title)

        self._tab_builders[tab_index] = builder

    def _on_tab_changed(self, tab_index: int) -> None:
        QTimer.singleShot(0, lambda: self._load_tab_by_index(tab_index))

    def _build_lazy_placeholder(self, title: str) -> QWidget:
        page = QWidget()

        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)

        card = QFrame()
        card.setObjectName("SecuritySystemHero")

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 16, 18, 16)
        card_layout.setSpacing(8)

        label = QLabel(f"{title} sekmesi hazırlanıyor...")
        label.setObjectName("SecuritySystemTitle")

        description = QLabel(
            "Bu sekme ilk kez açıldığında yüklenecek. "
            "Bu yöntem Güvenlik ve Sistem ekranının daha hızlı açılmasını sağlar."
        )
        description.setObjectName("SecuritySystemSubTitle")
        description.setWordWrap(True)

        card_layout.addWidget(label)
        card_layout.addWidget(description)
        card_layout.addStretch(1)

        layout.addWidget(card)
        layout.addStretch(1)

        return page

    def _load_current_tab(self) -> None:
        if self.tabs is None:
            return

        self._load_tab_by_index(self.tabs.currentIndex())

    def _load_tab_by_index(self, tab_index: int) -> None:
        if self.tabs is None:
            return

        if tab_index < 0:
            return

        if tab_index in self._loaded_tab_indexes:
            return

        if tab_index in self._loading_tab_indexes:
            return

        builder = self._tab_builders.get(tab_index)

        if builder is None:
            return

        self._loading_tab_indexes.add(tab_index)

        tab_title = self.tabs.tabText(tab_index)

        try:
            page = builder()
        except Exception as exc:
            page = self._build_tab_error_page(
                title=tab_title,
                error_message=str(exc),
            )

        self._replace_tab_safely(
            tab_index=tab_index,
            page=page,
            tab_title=tab_title,
        )

        self._loading_tab_indexes.discard(tab_index)
        self._loaded_tab_indexes.add(tab_index)

    def _replace_tab_safely(
        self,
        *,
        tab_index: int,
        page: QWidget,
        tab_title: str,
    ) -> None:
        if self.tabs is None:
            return

        old_signals_blocked = self.tabs.blockSignals(True)
        old_updates_enabled = self.tabs.updatesEnabled()

        self.tabs.setUpdatesEnabled(False)

        try:
            if tab_index < 0 or tab_index >= self.tabs.count():
                return

            self.tabs.removeTab(tab_index)
            self.tabs.insertTab(tab_index, page, tab_title)
            self.tabs.setCurrentIndex(tab_index)

        finally:
            self.tabs.setUpdatesEnabled(old_updates_enabled)
            self.tabs.blockSignals(old_signals_blocked)

    def _build_tab_error_page(
        self,
        *,
        title: str,
        error_message: str,
    ) -> QWidget:
        page = QWidget()

        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)

        card = QFrame()
        card.setObjectName("SecuritySystemHero")

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 16, 18, 16)
        card_layout.setSpacing(8)

        label = QLabel(f"{title} sekmesi yüklenemedi")
        label.setObjectName("SecuritySystemTitle")

        description = QLabel(error_message)
        description.setObjectName("SecuritySystemSubTitle")
        description.setWordWrap(True)

        card_layout.addWidget(label)
        card_layout.addWidget(description)
        card_layout.addStretch(1)

        layout.addWidget(card)
        layout.addStretch(1)

        return page

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