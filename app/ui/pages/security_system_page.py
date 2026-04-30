from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.services.license_service import check_license, license_file_path
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
        self._register_tab("Lisans", build_license_tab)

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
            "Kullanıcı yönetimi, roller, giriş kayıtları, işlem geçmişi, sistem ayarları, "
            "yedekleme ve lisans süreçleri bu tek merkezden yönetilecek."
        )
        subtitle.setObjectName("SecuritySystemSubTitle")
        subtitle.setWordWrap(True)

        layout.addLayout(title_row)
        layout.addWidget(subtitle)

        return hero


class LicenseTabPage(QWidget):
    def __init__(self) -> None:
        super().__init__()

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(18, 18, 18, 18)
        self.main_layout.setSpacing(14)

        self.render()

    def render(self) -> None:
        _clear_layout(self.main_layout)

        license_result = check_license()

        self.main_layout.addWidget(self._build_summary_card(license_result))
        self.main_layout.addWidget(self._build_action_card(license_result))
        self.main_layout.addWidget(self._build_detail_card(license_result))
        self.main_layout.addWidget(self._build_info_card())
        self.main_layout.addStretch(1)

    def _build_summary_card(self, license_result: Any) -> QWidget:
        summary_card = QFrame()
        summary_card.setObjectName("SecuritySystemHero")

        summary_layout = QVBoxLayout(summary_card)
        summary_layout.setContentsMargins(20, 18, 20, 18)
        summary_layout.setSpacing(10)

        title_row = QHBoxLayout()
        title_row.setSpacing(10)

        title = QLabel("Lisans Durumu")
        title.setObjectName("SecuritySystemTitle")

        status_badge = QLabel(license_result.status_label)
        status_badge.setObjectName("SecuritySystemAdminBadge")

        title_row.addWidget(title, 1)
        title_row.addWidget(status_badge, 0, Qt.AlignVCenter)

        message = QLabel(license_result.message)
        message.setObjectName("SecuritySystemSubTitle")
        message.setWordWrap(True)

        summary_layout.addLayout(title_row)
        summary_layout.addWidget(message)

        return summary_card

    def _build_action_card(self, license_result: Any) -> QWidget:
        action_card = QFrame()
        action_card.setObjectName("SecuritySystemHero")

        action_layout = QVBoxLayout(action_card)
        action_layout.setContentsMargins(20, 18, 20, 18)
        action_layout.setSpacing(12)

        title = QLabel("Lisans İşlemleri")
        title.setObjectName("SecuritySystemTitle")

        description = QLabel(
            "Müşteri cihaz kodunu buradan kopyalayabilir. "
            "Gönderilen lisans dosyası yine bu ekrandan seçilerek yüklenebilir."
        )
        description.setObjectName("SecuritySystemSubTitle")
        description.setWordWrap(True)

        button_row = QHBoxLayout()
        button_row.setSpacing(10)

        copy_device_button = QPushButton("Cihaz Kodunu Kopyala")
        copy_device_button.setObjectName("PrimaryButton")
        copy_device_button.setMinimumHeight(40)
        copy_device_button.clicked.connect(
            lambda: self.copy_device_code(license_result.device_code)
        )

        load_license_button = QPushButton("Lisans Dosyası Yükle")
        load_license_button.setObjectName("RefreshButton")
        load_license_button.setMinimumHeight(40)
        load_license_button.clicked.connect(self.load_license_file)

        refresh_button = QPushButton("Lisans Durumunu Yenile")
        refresh_button.setObjectName("RefreshButton")
        refresh_button.setMinimumHeight(40)
        refresh_button.clicked.connect(self.render)

        button_row.addWidget(copy_device_button)
        button_row.addWidget(load_license_button)
        button_row.addWidget(refresh_button)
        button_row.addStretch(1)

        action_layout.addWidget(title)
        action_layout.addWidget(description)
        action_layout.addLayout(button_row)

        return action_card

    def _build_detail_card(self, license_result: Any) -> QWidget:
        detail_card = QFrame()
        detail_card.setObjectName("SecuritySystemHero")

        detail_layout = QVBoxLayout(detail_card)
        detail_layout.setContentsMargins(20, 18, 20, 18)
        detail_layout.setSpacing(12)

        detail_title = QLabel("Lisans Bilgileri")
        detail_title.setObjectName("SecuritySystemTitle")

        detail_grid = QGridLayout()
        detail_grid.setHorizontalSpacing(18)
        detail_grid.setVerticalSpacing(10)

        rows = [
            ("Durum", license_result.status_label),
            ("Firma", license_result.company_name or "-"),
            ("Lisans Tipi", license_result.license_type or "-"),
            ("Cihaz Kodu", license_result.device_code),
            ("Başlangıç Tarihi", _format_license_date(license_result.starts_at)),
            ("Bitiş Tarihi", _format_license_date(license_result.expires_at)),
            ("Kalan Süre", _format_days_remaining(license_result.days_remaining)),
            ("Lisans Dosyası", str(license_result.license_file)),
            ("Uygulama Açılışı", "İzin Var" if license_result.allow_app_open else "Engelli"),
            ("Veri Girişi", "İzin Var" if license_result.allow_data_entry else "Engelli"),
        ]

        for row_index, (label_text, value_text) in enumerate(rows):
            label = QLabel(label_text)
            label.setObjectName("SecuritySystemSubTitle")

            value = QLabel(str(value_text))
            value.setObjectName("SecuritySystemSubTitle")
            value.setWordWrap(True)
            value.setTextInteractionFlags(Qt.TextSelectableByMouse)

            detail_grid.addWidget(label, row_index, 0, Qt.AlignTop)
            detail_grid.addWidget(value, row_index, 1)

        detail_grid.setColumnStretch(0, 0)
        detail_grid.setColumnStretch(1, 1)

        detail_layout.addWidget(detail_title)
        detail_layout.addLayout(detail_grid)

        return detail_card

    def _build_info_card(self) -> QWidget:
        info_card = QFrame()
        info_card.setObjectName("SecuritySystemHero")

        info_layout = QVBoxLayout(info_card)
        info_layout.setContentsMargins(20, 18, 20, 18)
        info_layout.setSpacing(8)

        info_title = QLabel("Not")
        info_title.setObjectName("SecuritySystemTitle")

        info_text = QLabel(
            "Bu aşamada lisans sistemi uyarı modundadır. "
            "Lisans yoksa veya süresi dolmuşsa bilgi verir; programı henüz tamamen kilitlemez. "
            "Müşteri lisans dosyasını bu ekrandan yükleyebilir."
        )
        info_text.setObjectName("SecuritySystemSubTitle")
        info_text.setWordWrap(True)

        info_layout.addWidget(info_title)
        info_layout.addWidget(info_text)

        return info_card

    def copy_device_code(self, device_code: str) -> None:
        cleaned_device_code = str(device_code or "").strip()

        if not cleaned_device_code:
            QMessageBox.warning(
                self,
                "Cihaz Kodu Kopyalanamadı",
                "Cihaz kodu boş görünüyor. Lisans ekranını yenileyip tekrar deneyin.",
            )
            return

        clipboard = QApplication.clipboard()
        clipboard.setText(cleaned_device_code)

        QMessageBox.information(
            self,
            "Cihaz Kodu Kopyalandı",
            "Cihaz kodu panoya kopyalandı.\n\n"
            f"{cleaned_device_code}\n\n"
            "Bu kodu lisans oluşturmak için kullanabilirsiniz.",
        )

    def load_license_file(self) -> None:
        selected_file, _ = QFileDialog.getOpenFileName(
            self,
            "Lisans Dosyası Seç",
            "",
            "FTM Lisans Dosyası (*.json *.ftmlic);;JSON Dosyası (*.json);;Tüm Dosyalar (*.*)",
        )

        if not selected_file:
            return

        source_path = Path(selected_file)

        validation_error = _validate_license_file_for_install(source_path)

        if validation_error:
            QMessageBox.critical(
                self,
                "Lisans Dosyası Yüklenemedi",
                validation_error,
            )
            return

        target_path = license_file_path()

        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)

            if target_path.exists():
                backup_path = _build_existing_license_backup_path(target_path)
                shutil.copy2(target_path, backup_path)

            shutil.copy2(source_path, target_path)

        except OSError as exc:
            QMessageBox.critical(
                self,
                "Lisans Dosyası Yüklenemedi",
                f"Lisans dosyası kopyalanırken hata oluştu:\n\n{exc}",
            )
            return

        self.render()

        refreshed_result = check_license()

        if refreshed_result.is_valid:
            QMessageBox.information(
                self,
                "Lisans Dosyası Yüklendi",
                "Lisans dosyası başarıyla yüklendi.\n\n"
                f"Durum: {refreshed_result.status_label}\n"
                f"Firma: {refreshed_result.company_name or '-'}\n"
                f"Bitiş Tarihi: {_format_license_date(refreshed_result.expires_at)}",
            )
            return

        QMessageBox.warning(
            self,
            "Lisans Dosyası Yüklendi Ancak Aktif Değil",
            "Lisans dosyası doğru klasöre yüklendi fakat geçerli görünmüyor.\n\n"
            f"Durum: {refreshed_result.status_label}\n"
            f"Açıklama: {refreshed_result.message}",
        )


def build_license_tab() -> QWidget:
    return LicenseTabPage()


def _validate_license_file_for_install(source_path: Path) -> str | None:
    if not source_path.exists():
        return f"Seçilen lisans dosyası bulunamadı:\n\n{source_path}"

    if not source_path.is_file():
        return f"Seçilen yol bir dosya değil:\n\n{source_path}"

    if source_path.suffix.lower() not in {".json", ".ftmlic"}:
        return (
            "Lisans dosyası uzantısı geçersiz.\n\n"
            "Beklenen dosya türü: .json veya .ftmlic"
        )

    try:
        with source_path.open("r", encoding="utf-8") as file:
            loaded_data = json.load(file)

    except json.JSONDecodeError:
        return (
            "Lisans dosyası okunamadı.\n\n"
            "Dosya JSON formatında değil veya bozuk görünüyor."
        )

    except OSError as exc:
        return f"Lisans dosyası okunamadı:\n\n{exc}"

    if not isinstance(loaded_data, dict):
        return "Lisans dosyası geçersiz. Dosya içeriği JSON nesnesi olmalıdır."

    required_fields = [
        "company_name",
        "license_type",
        "device_code",
        "starts_at",
        "expires_at",
        "issued_at",
        "notes",
        "signature",
    ]

    missing_fields = [
        field_name
        for field_name in required_fields
        if field_name not in loaded_data
    ]

    if missing_fields:
        return (
            "Lisans dosyası eksik alanlar içeriyor.\n\n"
            "Eksik alanlar: " + ", ".join(missing_fields)
        )

    return None


def _build_existing_license_backup_path(target_path: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    return target_path.with_name(
        f"{target_path.stem}.backup_{timestamp}{target_path.suffix}"
    )


def _clear_layout(layout: QVBoxLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)

        child_widget = item.widget()
        child_layout = item.layout()

        if child_widget is not None:
            child_widget.setParent(None)
            child_widget.deleteLater()

        if child_layout is not None:
            _clear_nested_layout(child_layout)


def _clear_nested_layout(layout: Any) -> None:
    while layout.count():
        item = layout.takeAt(0)

        child_widget = item.widget()
        child_layout = item.layout()

        if child_widget is not None:
            child_widget.setParent(None)
            child_widget.deleteLater()

        if child_layout is not None:
            _clear_nested_layout(child_layout)


def _format_license_date(value: str) -> str:
    cleaned_value = str(value or "").strip()

    if not cleaned_value:
        return "-"

    try:
        parsed_date = datetime.strptime(cleaned_value, "%Y-%m-%d")
    except ValueError:
        return cleaned_value

    return parsed_date.strftime("%d.%m.%Y")


def _format_days_remaining(value: int | None) -> str:
    if value is None:
        return "-"

    if value < 0:
        return f"Süresi {abs(value)} gün önce doldu"

    if value == 0:
        return "Bugün bitiyor"

    return f"{value} gün"


__all__ = [
    "SecuritySystemPage",
]