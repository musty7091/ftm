import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import Qt, QEventLoop, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)
from app.core.security import PasswordValidationError, validate_password_strength
from app.core.runtime_paths import ensure_runtime_folders as ensure_core_runtime_folders
from app.db.session import session_scope
from app.models.user import User
from app.services.auth_service import (
    AuthServiceError,
    AuthenticatedUser,
    authenticate_user,
    hash_password,
)
from app.services.startup_update_service import (
    STATUS_FIRST_INSTALL_REQUIRED,
    STATUS_UPDATED,
    run_startup_update_gate,
    startup_update_result_to_text,
)
from app.services.version_compatibility_service import (
    DatabaseVersionCompatibilityError,
    assert_database_version_is_compatible,
)
from app.services.license_service import (
    LICENSE_STATUS_ACTIVE,
    LICENSE_STATUS_EXPIRING_SOON,
    LicenseServiceError,
    check_license,
    get_device_code,
    is_signed_license_file_data,
    license_file_path,
    verify_signed_license_file_data,
)
from app.services.setup_service import is_setup_completed
from app.services.sqlite_setup_apply_service import (
    SqliteSetupApplyServiceError,
    apply_sqlite_initial_setup,
)
from app.ui.desktop_app import FtmDesktopWindow
from app.ui.setup_wizard_dialog import SetupWizardDialog
from app.ui.styles import get_application_stylesheet


VALID_LOGIN_LICENSE_STATUSES = {
    LICENSE_STATUS_ACTIVE,
    LICENSE_STATUS_EXPIRING_SOON,
}


class LicenseRequiredDialog(QDialog):
    def __init__(self, initial_license_result: Any | None = None) -> None:
        super().__init__()

        self.license_result = initial_license_result or check_license()
        self.detail_value_labels: dict[str, QLabel] = {}

        self.setWindowTitle("FTM Lisans Gerekli")
        self.setModal(True)
        self.setMinimumSize(1024, 700)
        self.setWindowFlags(self.windowFlags() | Qt.Window)

        screen = QApplication.primaryScreen()
        if screen is not None:
            self.setGeometry(screen.availableGeometry())

        self.setWindowState(Qt.WindowMaximized)

        self.status_badge = QLabel()
        self.status_badge.setAlignment(Qt.AlignCenter)
        self.status_badge.setMinimumHeight(36)

        self.message_label = QLabel()
        self.message_label.setObjectName("LoginSubtitle")
        self.message_label.setWordWrap(True)
        self.message_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self.device_code_input = QLineEdit()
        self.device_code_input.setReadOnly(True)
        self.device_code_input.setMinimumHeight(44)
        self.device_code_input.setCursorPosition(0)

        self._build_ui()
        self.refresh_license_status(show_success_message=False)

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(28, 28, 28, 28)
        root_layout.setSpacing(0)

        card = QFrame()
        card.setObjectName("LoginOuterCard")

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(30, 28, 30, 28)
        card_layout.setSpacing(16)

        logo = QLabel("FTM")
        logo.setObjectName("LoginLogo")
        logo.setAlignment(Qt.AlignCenter)

        title = QLabel("FTM Lisans Gerekli")
        title.setObjectName("LoginTitle")
        title.setAlignment(Qt.AlignCenter)

        subtitle = QLabel(
            "Bu bilgisayarda geçerli bir FTM lisansı bulunamadı. "
            "Uygulamaya giriş yapabilmek için version 2 imzalı lisans dosyası yüklenmelidir."
        )
        subtitle.setObjectName("LoginSubtitle")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setWordWrap(True)

        status_card = QFrame()
        status_card.setObjectName("Card")

        status_layout = QVBoxLayout(status_card)
        status_layout.setContentsMargins(18, 16, 18, 16)
        status_layout.setSpacing(10)

        status_title_row = QHBoxLayout()
        status_title_row.setSpacing(10)

        status_title = QLabel("Lisans Durumu")
        status_title.setObjectName("LoginLabel")

        status_title_row.addWidget(status_title, 1)
        status_title_row.addWidget(self.status_badge, 0, Qt.AlignVCenter)

        status_layout.addLayout(status_title_row)
        status_layout.addWidget(self.message_label)

        device_card = QFrame()
        device_card.setObjectName("Card")

        device_layout = QVBoxLayout(device_card)
        device_layout.setContentsMargins(18, 16, 18, 16)
        device_layout.setSpacing(10)

        device_title = QLabel("Cihaz Kodu")
        device_title.setObjectName("LoginLabel")

        device_description = QLabel(
            "Lisans üretimi için bu cihaz kodu kullanılacak. "
            "Kodu kopyalayıp lisans oluşturacak kişiye gönderebilirsin."
        )
        device_description.setObjectName("LoginFooter")
        device_description.setWordWrap(True)

        device_layout.addWidget(device_title)
        device_layout.addWidget(self.device_code_input)
        device_layout.addWidget(device_description)

        detail_card = QFrame()
        detail_card.setObjectName("Card")

        detail_layout = QVBoxLayout(detail_card)
        detail_layout.setContentsMargins(18, 16, 18, 16)
        detail_layout.setSpacing(10)

        detail_title = QLabel("Lisans Bilgileri")
        detail_title.setObjectName("LoginLabel")

        detail_grid = QGridLayout()
        detail_grid.setHorizontalSpacing(14)
        detail_grid.setVerticalSpacing(8)

        detail_rows = [
            ("status", "Durum"),
            ("company", "Firma"),
            ("license_type", "Lisans Tipi"),
            ("starts_at", "Başlangıç Tarihi"),
            ("expires_at", "Bitiş Tarihi"),
            ("days_remaining", "Kalan Süre"),
            ("license_file", "Lisans Dosyası"),
        ]

        for row_index, (key, label_text) in enumerate(detail_rows):
            label = QLabel(label_text)
            label.setObjectName("LoginFooter")

            value = QLabel("-")
            value.setObjectName("LoginFooter")
            value.setWordWrap(True)
            value.setTextInteractionFlags(Qt.TextSelectableByMouse)

            self.detail_value_labels[key] = value

            detail_grid.addWidget(label, row_index, 0, Qt.AlignTop)
            detail_grid.addWidget(value, row_index, 1)

        detail_grid.setColumnStretch(0, 0)
        detail_grid.setColumnStretch(1, 1)

        detail_layout.addWidget(detail_title)
        detail_layout.addLayout(detail_grid)

        contact_card = QFrame()
        contact_card.setObjectName("Card")

        contact_layout = QVBoxLayout(contact_card)
        contact_layout.setContentsMargins(18, 16, 18, 16)
        contact_layout.setSpacing(8)

        contact_title = QLabel("Lisans Yenileme / Yeni Lisans")
        contact_title.setObjectName("LoginLabel")

        contact_text = QLabel(
            "Lisans yenilemek veya yeni lisans almak için lütfen iletişime geçin.\n\n"
            "Telefon: \n"
            "E-posta: "
        )
        contact_text.setObjectName("LoginFooter")
        contact_text.setWordWrap(True)
        contact_text.setTextInteractionFlags(Qt.TextSelectableByMouse)

        contact_layout.addWidget(contact_title)
        contact_layout.addWidget(contact_text)

        button_row = QHBoxLayout()
        button_row.setSpacing(10)

        copy_device_button = QPushButton("Cihaz Kodunu Kopyala")
        copy_device_button.setObjectName("LoginButton")
        copy_device_button.setAutoDefault(False)
        copy_device_button.setDefault(False)
        copy_device_button.clicked.connect(self.copy_device_code)

        load_license_button = QPushButton("İmzalı Lisans Dosyası Yükle")
        load_license_button.setObjectName("LoginButton")
        load_license_button.setAutoDefault(False)
        load_license_button.setDefault(False)
        load_license_button.clicked.connect(self.load_license_file)

        refresh_button = QPushButton("Lisans Durumunu Yenile")
        refresh_button.setObjectName("CancelButton")
        refresh_button.setAutoDefault(False)
        refresh_button.setDefault(False)
        refresh_button.clicked.connect(lambda: self.refresh_license_status(show_success_message=True))

        exit_button = QPushButton("Uygulamadan Çık")
        exit_button.setObjectName("CancelButton")
        exit_button.setAutoDefault(False)
        exit_button.setDefault(False)
        exit_button.clicked.connect(self.reject)

        button_row.addWidget(copy_device_button)
        button_row.addWidget(load_license_button)
        button_row.addWidget(refresh_button)
        button_row.addWidget(exit_button)

        footer = QLabel(
            "Geçerli lisans yüklenmeden login ekranı açılmaz. "
            "Bu ekran FTM girişinden önce güvenlik kapısı olarak çalışır."
        )
        footer.setObjectName("LoginFooter")
        footer.setAlignment(Qt.AlignCenter)
        footer.setWordWrap(True)

        card_layout.addWidget(logo)
        card_layout.addWidget(title)
        card_layout.addWidget(subtitle)
        card_layout.addWidget(status_card)
        card_layout.addWidget(device_card)
        card_layout.addWidget(detail_card)
        card_layout.addWidget(contact_card)
        card_layout.addStretch(1)
        card_layout.addLayout(button_row)
        card_layout.addWidget(footer)

        root_layout.addWidget(card)

    def copy_device_code(self) -> None:
        device_code = self._current_device_code()

        if not device_code:
            QMessageBox.warning(
                self,
                "Cihaz Kodu Kopyalanamadı",
                "Cihaz kodu boş görünüyor. Lisans durumunu yenileyip tekrar deneyin.",
            )
            return

        clipboard = QApplication.clipboard()
        clipboard.setText(device_code)

        QMessageBox.information(
            self,
            "Cihaz Kodu Kopyalandı",
            "Cihaz kodu panoya kopyalandı.\n\n"
            f"{device_code}",
        )

    def load_license_file(self) -> None:
        selected_file, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "İmzalı Lisans Dosyası Seç",
            "",
            "FTM Lisans Dosyası (*.ftmlic *.json);;JSON Dosyası (*.json);;Tüm Dosyalar (*.*)",
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

        try:
            ensure_core_runtime_folders()
            target_path = license_file_path()
            target_path.parent.mkdir(parents=True, exist_ok=True)

            same_file = False
            try:
                same_file = source_path.resolve() == target_path.resolve()
            except OSError:
                same_file = False

            if not same_file:
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

        self.refresh_license_status(show_success_message=False)

        if _is_license_valid_for_login(self.license_result):
            QMessageBox.information(
                self,
                "İmzalı Lisans Dosyası Yüklendi",
                "Version 2 imzalı lisans dosyası başarıyla yüklendi.\n\n"
                f"Durum: {self.license_result.status_label}\n"
                f"Firma: {self.license_result.company_name or '-'}\n"
                f"Bitiş Tarihi: {_format_license_date(self.license_result.expires_at)}\n\n"
                "Şimdi giriş ekranına geçilecek.",
            )
            self.accept()
            return

        QMessageBox.warning(
            self,
            "Lisans Dosyası Yüklendi Ancak Aktif Değil",
            "Lisans dosyası doğru klasöre yüklendi fakat login için geçerli görünmüyor.\n\n"
            f"Durum: {self.license_result.status_label}\n"
            f"Açıklama: {self.license_result.message}",
        )

    def refresh_license_status(self, *, show_success_message: bool) -> None:
        try:
            self.license_result = check_license()
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Lisans Durumu Okunamadı",
                f"Lisans durumu kontrol edilirken beklenmeyen hata oluştu:\n\n{exc}",
            )
            return

        self._render_license_result()

        if not show_success_message:
            return

        if _is_license_valid_for_login(self.license_result):
            QMessageBox.information(
                self,
                "Lisans Aktif",
                "Geçerli lisans bulundu. Şimdi giriş ekranına geçilecek.",
            )
            self.accept()
            return

        QMessageBox.warning(
            self,
            "Lisans Gerekli",
            "Login ekranına geçmek için geçerli bir lisans bulunamadı.\n\n"
            f"Durum: {self.license_result.status_label}\n"
            f"Açıklama: {self.license_result.message}",
        )

    def _render_license_result(self) -> None:
        status_label = str(self.license_result.status_label or "Lisans Durumu")
        status_object_name = "HealthOk" if _is_license_valid_for_login(self.license_result) else "HealthFail"

        self.status_badge.setText(status_label)
        self.status_badge.setObjectName(status_object_name)
        _refresh_widget_style(self.status_badge)

        self.message_label.setText(str(self.license_result.message or "-"))
        self.device_code_input.setText(self._current_device_code())

        detail_values = {
            "status": status_label,
            "company": self.license_result.company_name or "-",
            "license_type": self.license_result.license_type or "-",
            "starts_at": _format_license_date(self.license_result.starts_at),
            "expires_at": _format_license_date(self.license_result.expires_at),
            "days_remaining": _format_days_remaining(self.license_result.days_remaining),
            "license_file": str(self.license_result.license_file),
        }

        for key, value in detail_values.items():
            value_label = self.detail_value_labels.get(key)
            if value_label is not None:
                value_label.setText(str(value))

    def _current_device_code(self) -> str:
        result_device_code = str(getattr(self.license_result, "device_code", "") or "").strip()

        if result_device_code:
            return result_device_code

        try:
            return get_device_code()
        except Exception:
            return ""


class ForcedPasswordChangeDialog(QDialog):
    def __init__(self, authenticated_user: AuthenticatedUser) -> None:
        super().__init__()

        self.authenticated_user = authenticated_user

        self.setWindowTitle("Şifre Değişikliği Zorunlu")
        self.setModal(True)
        self.setFixedSize(540, 430)

        self.new_password_input = QLineEdit()
        self.new_password_input.setPlaceholderText("Yeni şifre")
        self.new_password_input.setEchoMode(QLineEdit.Password)
        self.new_password_input.setMinimumHeight(44)

        self.repeat_password_input = QLineEdit()
        self.repeat_password_input.setPlaceholderText("Yeni şifre tekrar")
        self.repeat_password_input.setEchoMode(QLineEdit.Password)
        self.repeat_password_input.setMinimumHeight(44)
        self.repeat_password_input.returnPressed.connect(self.try_change_password)

        self._build_ui()

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(28, 28, 28, 28)
        root_layout.setSpacing(0)

        card = QFrame()
        card.setObjectName("LoginOuterCard")

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(30, 28, 30, 28)
        card_layout.setSpacing(16)

        title = QLabel("Şifre Değişikliği Gerekli")
        title.setObjectName("LoginTitle")
        title.setAlignment(Qt.AlignCenter)

        subtitle = QLabel(
            "Bu kullanıcı için ilk girişte şifre değiştirme zorunlu. "
            "Ana panele geçmeden önce yeni şifre belirlemelisin."
        )
        subtitle.setObjectName("LoginSubtitle")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setWordWrap(True)

        user_info = QLabel(
            f"Kullanıcı: {self.authenticated_user.username} / {self.authenticated_user.role.value}"
        )
        user_info.setObjectName("LoginFooter")
        user_info.setAlignment(Qt.AlignCenter)
        user_info.setWordWrap(True)

        form_layout = QGridLayout()
        form_layout.setHorizontalSpacing(12)
        form_layout.setVerticalSpacing(10)

        new_password_label = QLabel("Yeni Şifre")
        new_password_label.setObjectName("LoginLabel")

        repeat_password_label = QLabel("Şifre Tekrar")
        repeat_password_label.setObjectName("LoginLabel")

        form_layout.addWidget(new_password_label, 0, 0)
        form_layout.addWidget(self.new_password_input, 0, 1)

        form_layout.addWidget(repeat_password_label, 1, 0)
        form_layout.addWidget(self.repeat_password_input, 1, 1)

        button_row = QHBoxLayout()
        button_row.setSpacing(12)

        cancel_button = QPushButton("Vazgeç")
        cancel_button.setObjectName("CancelButton")
        cancel_button.clicked.connect(self.reject)

        save_button = QPushButton("Şifreyi Değiştir")
        save_button.setObjectName("LoginButton")
        save_button.clicked.connect(self.try_change_password)

        button_row.addWidget(cancel_button)
        button_row.addWidget(save_button)

        footer = QLabel(
            "Şifre değişikliği tamamlanmadan uygulamaya giriş yapılamaz."
        )
        footer.setObjectName("LoginFooter")
        footer.setAlignment(Qt.AlignCenter)
        footer.setWordWrap(True)

        card_layout.addWidget(title)
        card_layout.addWidget(subtitle)
        card_layout.addWidget(user_info)
        card_layout.addSpacing(8)
        card_layout.addLayout(form_layout)
        card_layout.addSpacing(8)
        card_layout.addLayout(button_row)
        card_layout.addStretch()
        card_layout.addWidget(footer)

        root_layout.addWidget(card)

        self.new_password_input.setFocus()

    def try_change_password(self) -> None:
        new_password = self.new_password_input.text()
        repeat_password = self.repeat_password_input.text()

        validation_error = self._validate_password(
            new_password=new_password,
            repeat_password=repeat_password,
        )

        if validation_error:
            QMessageBox.warning(
                self,
                "Şifre Değiştirilemedi",
                validation_error,
            )
            return

        try:
            with session_scope() as session:
                user = session.get(User, self.authenticated_user.id)

                if user is None:
                    raise ValueError("Kullanıcı kaydı bulunamadı.")

                user.password_hash = hash_password(new_password)
                user.must_change_password = False

                session.flush()

            QMessageBox.information(
                self,
                "Şifre Değiştirildi",
                "Şifren başarıyla değiştirildi. Ana panele geçiliyor.",
            )

            self.accept()

        except Exception as exc:
            QMessageBox.critical(
                self,
                "Şifre Değiştirilemedi",
                f"Şifre değiştirilirken hata oluştu:\n\n{exc}",
            )

    def _validate_password(
        self,
        *,
        new_password: str,
        repeat_password: str,
    ) -> str | None:
        if not new_password:
            return "Yeni şifre boş olamaz."

        try:
            validate_password_strength(new_password)
        except PasswordValidationError as exc:
            return str(exc)

        if new_password != repeat_password:
            return "Yeni şifre ve tekrar alanı aynı olmalıdır."

        if new_password.strip().lower() == self.authenticated_user.username.strip().lower():
            return "Şifre kullanıcı adı ile aynı olmamalıdır."

        return None


class LoginDialog(QDialog):
    def __init__(self) -> None:
        super().__init__()

        self.authenticated_user: Optional[AuthenticatedUser] = None
        self._allow_dialog_close = False

        self.setWindowTitle("FTM Giriş")
        self.setModal(True)
        self.setFixedSize(560, 710)
        self.setStyleSheet(self._login_dialog_stylesheet())

        self.startup_step_messages = [
            "[•] Veritabanı kontrol ediliyor...",
            "[•] SQLite quick_check çalıştırılıyor...",
            "[•] Veritabanı güncel. Uygulama hazırlanıyor...",
            "[✓] Kontroller tamamlandı. Giriş ekranı hazır.",
        ]
        self.startup_step_index = 0
        self.startup_status_message_label = QLabel()
        self.startup_status_message_label.setWordWrap(True)
        self.startup_status_message_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.startup_status_counter_label = QLabel()
        self.startup_status_dots_label = QLabel()
        self.startup_status_timer = QTimer(self)
        self.startup_status_timer.setInterval(850)
        self.startup_status_timer.timeout.connect(self._advance_startup_status_message)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(20, 20, 20, 20)
        root_layout.setSpacing(0)

        card = QFrame()
        card.setObjectName("LoginOuterCard")

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(36, 30, 36, 24)
        card_layout.setSpacing(14)

        logo = self._build_login_logo_widget()

        title = QLabel("Finans Takip Merkezi")
        title.setObjectName("LoginTitle")
        title.setAlignment(Qt.AlignCenter)

        subtitle = QLabel("Güvenli oturum açmadan ana panele erişilemez.")
        subtitle.setObjectName("LoginSubtitle")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setWordWrap(True)

        self.identifier_input = QLineEdit()
        self.identifier_input.setPlaceholderText("Kullanıcı adı veya e-posta")
        self.identifier_input.setMinimumHeight(48)

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Şifre")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setMinimumHeight(48)
        self.password_input.returnPressed.connect(self.try_login)

        identifier_label = QLabel("Kullanıcı")
        identifier_label.setObjectName("LoginLabel")

        password_label = QLabel("Şifre")
        password_label.setObjectName("LoginLabel")

        button_row = QHBoxLayout()
        button_row.setSpacing(12)

        cancel_button = QPushButton("Çıkış")
        cancel_button.setObjectName("CancelButton")
        cancel_button.setMinimumHeight(46)
        cancel_button.setAutoDefault(False)
        cancel_button.setDefault(False)
        cancel_button.clicked.connect(self.cancel_login)

        login_button = QPushButton("Giriş Yap")
        login_button.setObjectName("LoginButton")
        login_button.setMinimumHeight(46)
        login_button.setAutoDefault(False)
        login_button.setDefault(False)
        login_button.clicked.connect(self.try_login)

        button_row.addWidget(cancel_button)
        button_row.addWidget(login_button)

        startup_status_panel = self._build_startup_status_panel()

        footer = QLabel("Rol ve yetki sistemi aktif. İşlemler audit log ile izlenir.")
        footer.setObjectName("LoginFooter")
        footer.setAlignment(Qt.AlignCenter)
        footer.setWordWrap(True)

        card_layout.addWidget(logo, 0, Qt.AlignCenter)
        card_layout.addSpacing(4)
        card_layout.addWidget(title)
        card_layout.addWidget(subtitle)
        card_layout.addSpacing(12)
        card_layout.addWidget(identifier_label)
        card_layout.addWidget(self.identifier_input)
        card_layout.addSpacing(6)
        card_layout.addWidget(password_label)
        card_layout.addWidget(self.password_input)
        card_layout.addSpacing(10)
        card_layout.addLayout(button_row)
        card_layout.addSpacing(4)
        card_layout.addWidget(startup_status_panel)
        card_layout.addStretch()
        card_layout.addWidget(footer)

        root_layout.addWidget(card)

        self._reset_startup_status_panel()
        self.identifier_input.setFocus()

    def _login_dialog_stylesheet(self) -> str:
        return """
        QDialog {
            background-color: #070d1a;
        }

        QFrame#LoginOuterCard {
            background-color: qlineargradient(
                x1: 0, y1: 0,
                x2: 0, y2: 1,
                stop: 0 #121c2f,
                stop: 1 #0d1628
            );
            border: 1px solid #243550;
            border-radius: 24px;
        }

        QLabel#LoginImageLogo {
            background-color: transparent;
            border: none;
        }

        QLabel#LoginLogo {
            background-color: #0f172a;
            color: #e0f2fe;
            border: 1px solid #38bdf8;
            border-radius: 46px;
            font-size: 28px;
            font-weight: 900;
            letter-spacing: 2px;
        }

        QLabel#LoginTitle {
            color: #f8fafc;
            font-size: 22px;
            font-weight: 900;
        }

        QLabel#LoginSubtitle {
            color: #a8bdd7;
            font-size: 12px;
        }

        QLabel#LoginLabel {
            color: #dbeafe;
            font-size: 12px;
            font-weight: 800;
        }

        QLabel#LoginFooter {
            color: #8ea3bf;
            font-size: 11px;
        }

        QLineEdit {
            background-color: #0c1424;
            color: #f8fafc;
            border: 1px solid #283a57;
            border-radius: 13px;
            padding-left: 14px;
            padding-right: 14px;
            selection-background-color: #2563eb;
            selection-color: #ffffff;
            font-size: 12px;
        }

        QLineEdit:focus {
            border: 1px solid #38bdf8;
            background-color: #0f1b31;
        }

        QPushButton {
            border-radius: 13px;
            font-size: 13px;
            font-weight: 900;
            padding: 8px 14px;
        }

        QPushButton#LoginButton {
            background-color: qlineargradient(
                x1: 0, y1: 0,
                x2: 1, y2: 1,
                stop: 0 #2563eb,
                stop: 1 #0ea5e9
            );
            color: #ffffff;
            border: 1px solid #38bdf8;
        }

        QPushButton#LoginButton:hover {
            background-color: #1d4ed8;
            border: 1px solid #7dd3fc;
        }

        QPushButton#CancelButton {
            background-color: #111b2d;
            color: #dbeafe;
            border: 1px solid #293b58;
        }

        QPushButton#CancelButton:hover {
            background-color: #17243a;
            border: 1px solid #3b587c;
        }

        QFrame#StartupStatusPanel {
            background-color: qlineargradient(
                x1: 0, y1: 0,
                x2: 1, y2: 1,
                stop: 0 #07111f,
                stop: 1 #0b1c31
            );
            border: 1px solid #1b3b5a;
            border-radius: 16px;
        }

        QLabel#StartupStatusTitle {
            color: #bfdbfe;
            font-size: 12px;
            font-weight: 900;
        }

        QLabel#StartupStatusBadge {
            color: #67e8f9;
            font-size: 11px;
            font-weight: 900;
            padding: 2px 8px;
            border: 1px solid #164e63;
            border-radius: 9px;
            background-color: #082f49;
        }

        QLabel#StartupStatusMessage {
            color: #f8fafc;
            font-size: 12px;
            font-weight: 750;
        }

        QLabel#StartupStatusDots {
            color: #22d3ee;
            font-size: 13px;
            font-weight: 900;
            letter-spacing: 5px;
        }
        """

    def _build_startup_status_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("StartupStatusPanel")
        panel.setMinimumHeight(92)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(7)

        header_row = QHBoxLayout()
        header_row.setSpacing(8)

        title = QLabel("Güvenli açılış")
        title.setObjectName("StartupStatusTitle")

        self.startup_status_counter_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.startup_status_counter_label.setObjectName("StartupStatusBadge")

        header_row.addWidget(title, 1)
        header_row.addWidget(self.startup_status_counter_label, 0)

        self.startup_status_message_label.setObjectName("StartupStatusMessage")

        self.startup_status_dots_label.setAlignment(Qt.AlignCenter)
        self.startup_status_dots_label.setObjectName("StartupStatusDots")

        layout.addLayout(header_row)
        layout.addWidget(self.startup_status_message_label)
        layout.addWidget(self.startup_status_dots_label)

        return panel

    def _build_login_logo_widget(self) -> QLabel:
        logo = QLabel("FTM")
        logo.setObjectName("LoginLogo")
        logo.setAlignment(Qt.AlignCenter)
        logo.setFixedSize(92, 92)

        logo_path = _find_login_logo_path()
        if logo_path is not None:
            pixmap = QPixmap(str(logo_path))
            if not pixmap.isNull():
                logo.setPixmap(
                    pixmap.scaled(
                        82,
                        82,
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation,
                    )
                )
                logo.setObjectName("LoginImageLogo")
                return logo

        logo.setStyleSheet(
            """
            QLabel {
                background-color: #0f172a;
                color: #e0f2fe;
                border: 2px solid #38bdf8;
                border-radius: 54px;
                font-size: 31px;
                font-weight: 900;
                letter-spacing: 2px;
            }
            """
        )
        return logo

    def _reset_startup_status_panel(self) -> None:
        self.startup_status_timer.stop()
        self.startup_step_index = 0
        self.startup_status_counter_label.setText("Hazır")
        self.startup_status_message_label.setText(
            "Giriş yaptığınızda güvenli açılış kontrolü gösterilir."
        )
        self.startup_status_dots_label.setText("○ ○ ○ ○")

    def _start_login_status_simulation(self) -> None:
        self.startup_step_index = 0
        self._render_startup_status_message()
        self.startup_status_timer.start()

    def _play_login_status_sequence(self) -> None:
        self.startup_status_timer.stop()

        for step_index in range(len(self.startup_step_messages)):
            self.startup_step_index = step_index
            self._render_startup_status_message()
            QApplication.processEvents()
            self._wait_with_ui(milliseconds=620)

    def _wait_with_ui(self, *, milliseconds: int) -> None:
        wait_loop = QEventLoop(self)
        QTimer.singleShot(max(1, int(milliseconds)), wait_loop.quit)
        wait_loop.exec()

    def _finish_login_status_simulation(self, *, success: bool, message: str | None = None) -> None:
        self.startup_status_timer.stop()

        if success:
            self.startup_status_counter_label.setText("Tamam")
            self.startup_status_message_label.setText(
                message or "[✓] Kontroller tamamlandı. Güvenli giriş başlatılıyor."
            )
            self.startup_status_dots_label.setText("● ● ● ●")
            return

        self.startup_status_counter_label.setText("Dikkat")
        self.startup_status_message_label.setText(
            message or "[!] Giriş tamamlanamadı. Bilgileri kontrol edip tekrar deneyin."
        )
        self.startup_status_dots_label.setText("● ○ ○ ○")

    def _render_startup_status_message(self) -> None:
        total_steps = len(self.startup_step_messages)
        current_number = self.startup_step_index + 1
        current_message = self.startup_step_messages[self.startup_step_index]

        active_dot_index = self.startup_step_index % total_steps
        dots = " ".join(
            "●" if index == active_dot_index else "○"
            for index in range(total_steps)
        )

        self.startup_status_counter_label.setText(
            f"{current_number:02d} / {total_steps:02d}"
        )
        self.startup_status_message_label.setText(current_message)
        self.startup_status_dots_label.setText(dots)

    def _advance_startup_status_message(self) -> None:
        self.startup_step_index += 1

        if self.startup_step_index >= len(self.startup_step_messages):
            self.startup_step_index = 0

        self._render_startup_status_message()

    def accept(self) -> None:
        if self.authenticated_user is None:
            self.password_input.clear()
            self.password_input.setFocus()
            return

        self._allow_dialog_close = True
        super().accept()

    def reject(self) -> None:
        self._allow_dialog_close = True
        super().reject()

    def cancel_login(self) -> None:
        self.reject()

    def try_login(self) -> None:
        identifier = self.identifier_input.text().strip()
        password = self.password_input.text()

        if not identifier:
            QMessageBox.warning(
                self,
                "FTM Giriş",
                "Kullanıcı adı veya e-posta boş olamaz.",
            )
            self.identifier_input.setFocus()
            return

        if not password:
            QMessageBox.warning(
                self,
                "FTM Giriş",
                "Şifre boş olamaz.",
            )
            self.password_input.setFocus()
            return

        self._play_login_status_sequence()

        try:
            with session_scope() as session:
                authenticated_user = authenticate_user(
                    session,
                    identifier=identifier,
                    password=password,
                )

                user = session.get(User, authenticated_user.id)

                must_change_password = False
                if user is not None:
                    must_change_password = bool(user.must_change_password)

                session.flush()

            if must_change_password:
                password_change_dialog = ForcedPasswordChangeDialog(authenticated_user)

                if password_change_dialog.exec() != QDialog.Accepted:
                    self._finish_login_status_simulation(
                        success=False,
                        message="[!] Şifre değişikliği tamamlanmadı. Giriş güvenli şekilde durduruldu.",
                    )
                    QMessageBox.warning(
                        self,
                        "Şifre Değişikliği Gerekli",
                        "Şifre değiştirilmeden ana panele giriş yapılamaz.",
                    )
                    self.password_input.clear()
                    self.password_input.setFocus()
                    return

            self.authenticated_user = authenticated_user
            self._finish_login_status_simulation(success=True)
            QApplication.processEvents()
            self._wait_with_ui(milliseconds=700)
            self.accept()

        except AuthServiceError as exc:
            self._show_login_failed_message(str(exc))
            return

        except Exception as exc:
            self._show_login_failed_message(
                "Giriş kontrolü sırasında beklenmeyen bir hata oluştu.\n\n"
                f"Hata: {exc}"
            )
            return

    def _show_login_failed_message(self, message: str) -> None:
        self.authenticated_user = None
        self._allow_dialog_close = False
        self._finish_login_status_simulation(
            success=False,
            message="[!] Giriş tamamlanamadı. Bilgileri kontrol edip tekrar deneyin.",
        )

        QMessageBox.warning(
            self,
            "FTM Giriş Başarısız",
            message,
        )

        self.password_input.clear()
        self.password_input.setFocus()
        self.show()
        self.raise_()
        self.activateWindow()


def _find_login_logo_path() -> Path | None:
    candidates: list[Path] = []

    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent / "ftm_branding_assets" / "icon.png")

    try:
        project_root = Path(__file__).resolve().parents[2]
        candidates.extend(
            [
                project_root / "ftm_branding_assets" / "icon.png",
                project_root / "app" / "assets" / "branding" / "ftm_app_icon.png",
                project_root / "app" / "assets" / "branding" / "ftm_app_icon.ico",
            ]
        )
    except Exception:
        pass

    candidates.extend(
        [
            Path.cwd() / "ftm_branding_assets" / "icon.png",
            Path(r"C:\ftm\ftm_branding_assets\icon.png"),
        ]
    )

    seen_paths: set[str] = set()

    for candidate in candidates:
        try:
            normalized_path = str(candidate.expanduser().resolve())
        except OSError:
            normalized_path = str(candidate)

        if normalized_path in seen_paths:
            continue

        seen_paths.add(normalized_path)

        if candidate.exists() and candidate.is_file():
            return candidate

    return None


def _run_initial_setup_if_needed() -> bool:
    try:
        ensure_core_runtime_folders()

        if is_setup_completed():
            return True

    except Exception as exc:
        QMessageBox.critical(
            None,
            "FTM Kurulum Kontrolü",
            f"Kurulum durumu kontrol edilirken hata oluştu:\n\n{exc}",
        )
        return False

    setup_dialog = SetupWizardDialog()
    setup_dialog.setWindowModality(Qt.ApplicationModal)
    setup_dialog.showMaximized()
    setup_dialog.raise_()
    setup_dialog.activateWindow()

    if setup_dialog.exec() != QDialog.Accepted:
        QMessageBox.warning(
            None,
            "FTM İlk Kurulum",
            "İlk kurulum tamamlanmadan uygulamaya giriş yapılamaz.",
        )
        return False

    try:
        payload = setup_dialog.get_payload()

        if payload.database_engine != "sqlite":
            QMessageBox.warning(
                None,
                "FTM Local Kurulum",
                "Bu kurulum paketinde şu anda sadece SQLite Local modu destekleniyor.\n\n"
                "Lütfen veritabanı tipi olarak SQLite seçip kurulumu tekrar başlatın.",
            )
            return False

        result = apply_sqlite_initial_setup(
            sqlite_database_path=payload.sqlite_database_path,
            company_name=payload.company_name,
            company_address=payload.company_address,
            company_phone=payload.company_phone,
            company_email=payload.company_email,
            admin_username=payload.admin_username,
            admin_full_name=payload.admin_full_name,
            admin_password=payload.admin_password,
            admin_email=payload.admin_email,
        )

        QMessageBox.information(
            None,
            "FTM İlk Kurulum Tamamlandı",
            "İlk kurulum başarıyla tamamlandı.\n\n"
            f"Firma: {result.company_name}\n"
            f"ADMIN kullanıcı: {result.admin_username}\n"
            f"Veritabanı: {result.sqlite_database_path}\n\n"
            "Şimdi lisans kontrolü yapılacak.",
        )

        return True

    except SqliteSetupApplyServiceError as exc:
        QMessageBox.critical(
            None,
            "FTM İlk Kurulum Başarısız",
            str(exc),
        )
        return False

    except Exception as exc:
        QMessageBox.critical(
            None,
            "FTM İlk Kurulum Başarısız",
            f"İlk kurulum sırasında beklenmeyen hata oluştu:\n\n{exc}",
        )
        return False


def _run_database_migration_gate_if_needed() -> bool:
    try:
        ensure_core_runtime_folders()
        result = run_startup_update_gate()

    except Exception as exc:
        QMessageBox.critical(
            None,
            "FTM Otomatik Güncelleme Kontrolü",
            "Otomatik güncelleme kontrolü sırasında beklenmeyen bir hata oluştu. "
            "Mevcut verilerinizin güvenliği için uygulama başlatılmadı.\n\n"
            f"Hata: {exc}",
        )
        return False

    if not result.should_continue_to_app:
        QMessageBox.critical(
            None,
            "FTM Otomatik Güncelleme Kontrolü",
            "Veritabanı otomatik güncelleme kontrolü başarısız oldu. "
            "Mevcut verilerinizin güvenliği için uygulama başlatılmadı.\n\n"
            f"{startup_update_result_to_text(result)}",
        )
        return False

    if result.status == STATUS_UPDATED:
        applied_migrations_text = "\n".join(
            f"- {migration_id}"
            for migration_id in result.applied_migration_ids
        )
        backup_file_text = result.backup_file or "Yedek dosyası bilgisi alınamadı."

        QMessageBox.information(
            None,
            "FTM Otomatik Güncelleme Tamamlandı",
            "Veritabanı yeni sürüm için otomatik olarak güncellendi.\n\n"
            f"Uygulanan güncelleme sayısı: {len(result.applied_migration_ids)}\n"
            f"Şema sürümü: {result.current_schema_version} / {result.expected_schema_version}\n"
            f"SQLite quick_check: {result.quick_check_result or '-'}\n\n"
            "Uygulanan güncellemeler:\n"
            f"{applied_migrations_text}\n\n"
            "Güncelleme öncesi güvenli yedek:\n"
            f"{backup_file_text}",
        )

    if result.status == STATUS_FIRST_INSTALL_REQUIRED:
        return True

    return True


def _run_database_version_compatibility_gate_if_needed() -> bool:
    try:
        ensure_core_runtime_folders()
        assert_database_version_is_compatible()
        return True

    except DatabaseVersionCompatibilityError as exc:
        QMessageBox.critical(
            None,
            "FTM Sürüm Uyumluluk Kontrolü",
            "Uygulama ve veritabanı sürüm uyumu sağlanamadı. "
            "Mevcut verilerinizin güvenliği için uygulama başlatılmadı.\n\n"
            f"{exc.user_message}\n\n"
            "Teknik detay:\n"
            f"{exc.technical_message}",
        )
        return False

    except Exception as exc:
        QMessageBox.critical(
            None,
            "FTM Sürüm Uyumluluk Kontrolü",
            "Sürüm uyumluluk kontrolü sırasında beklenmeyen bir hata oluştu. "
            "Mevcut verilerinizin güvenliği için uygulama başlatılmadı.\n\n"
            f"Hata: {exc}",
        )
        return False


def _run_license_gate_if_needed() -> bool:
    try:
        ensure_core_runtime_folders()
        license_result = check_license()

    except Exception as exc:
        QMessageBox.critical(
            None,
            "FTM Lisans Kontrolü",
            f"Lisans durumu kontrol edilirken hata oluştu:\n\n{exc}",
        )
        return False

    if _is_license_valid_for_login(license_result):
        return True

    license_dialog = LicenseRequiredDialog(license_result)
    license_dialog.setWindowModality(Qt.ApplicationModal)
    license_dialog.setWindowState(Qt.WindowMaximized)
    license_dialog.raise_()
    license_dialog.activateWindow()

    return license_dialog.exec() == QDialog.Accepted


def _is_license_valid_for_login(license_result: Any) -> bool:
    status = str(getattr(license_result, "status", "") or "").strip()
    is_valid = bool(getattr(license_result, "is_valid", False))

    return is_valid and status in VALID_LOGIN_LICENSE_STATUSES


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

    if not is_signed_license_file_data(loaded_data):
        return (
            "Lisans dosyası eski formatta veya imzasız görünüyor.\n\n"
            "FTM artık yalnızca version 2 Ed25519 imzalı lisans dosyalarını kabul eder."
        )

    try:
        verify_signed_license_file_data(loaded_data)

    except LicenseServiceError as exc:
        return str(exc)

    except Exception as exc:
        return f"Lisans dosyası doğrulanırken beklenmeyen hata oluştu:\n\n{exc}"

    return None


def _build_existing_license_backup_path(target_path: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    return target_path.with_name(
        f"{target_path.stem}.backup_{timestamp}{target_path.suffix}"
    )


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


def _refresh_widget_style(widget: Any) -> None:
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()


def main() -> None:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setStyleSheet(get_application_stylesheet())

    if not _run_initial_setup_if_needed():
        sys.exit(0)

    if not _run_database_migration_gate_if_needed():
        sys.exit(0)

    if not _run_database_version_compatibility_gate_if_needed():
        sys.exit(0)

    if not _run_license_gate_if_needed():
        sys.exit(0)

    login_dialog = LoginDialog()

    if login_dialog.exec() != QDialog.Accepted:
        sys.exit(0)

    if login_dialog.authenticated_user is None:
        sys.exit(0)

    window = FtmDesktopWindow(
        current_user=login_dialog.authenticated_user,
    )
    window.showMaximized()

    app.setQuitOnLastWindowClosed(True)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
