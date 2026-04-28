import sys
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from app.db.session import session_scope
from app.models.user import User
from app.services.auth_service import (
    AuthServiceError,
    AuthenticatedUser,
    authenticate_user,
    hash_password,
)
from app.ui.desktop_app import FtmDesktopWindow
from app.ui.styles import get_application_stylesheet


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

        if len(new_password) < 6:
            return "Yeni şifre en az 6 karakter olmalıdır."

        if new_password != repeat_password:
            return "Yeni şifre ve tekrar alanı aynı olmalıdır."

        if new_password.strip().lower() == self.authenticated_user.username.strip().lower():
            return "Şifre kullanıcı adı ile aynı olmamalıdır."

        return None


class LoginDialog(QDialog):
    def __init__(self) -> None:
        super().__init__()

        self.authenticated_user: Optional[AuthenticatedUser] = None

        self.setWindowTitle("FTM Giriş")
        self.setModal(True)
        self.setFixedSize(520, 520)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(28, 28, 28, 28)
        root_layout.setSpacing(0)

        card = QFrame()
        card.setObjectName("LoginOuterCard")

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(34, 32, 34, 32)
        card_layout.setSpacing(18)

        logo = QLabel("FTM")
        logo.setObjectName("LoginLogo")
        logo.setAlignment(Qt.AlignCenter)

        title = QLabel("Finans Takip Merkezi")
        title.setObjectName("LoginTitle")
        title.setAlignment(Qt.AlignCenter)

        subtitle = QLabel("Güvenli oturum açmadan ana panele erişilemez.")
        subtitle.setObjectName("LoginSubtitle")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setWordWrap(True)

        self.identifier_input = QLineEdit()
        self.identifier_input.setPlaceholderText("Kullanıcı adı veya e-posta")
        self.identifier_input.setMinimumHeight(46)

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Şifre")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setMinimumHeight(46)
        self.password_input.returnPressed.connect(self.try_login)

        identifier_label = QLabel("Kullanıcı")
        identifier_label.setObjectName("LoginLabel")

        password_label = QLabel("Şifre")
        password_label.setObjectName("LoginLabel")

        button_row = QHBoxLayout()
        button_row.setSpacing(12)

        cancel_button = QPushButton("Çıkış")
        cancel_button.setObjectName("CancelButton")
        cancel_button.clicked.connect(self.reject)

        login_button = QPushButton("Giriş Yap")
        login_button.setObjectName("LoginButton")
        login_button.clicked.connect(self.try_login)

        button_row.addWidget(cancel_button)
        button_row.addWidget(login_button)

        footer = QLabel("Rol ve yetki sistemi aktif. İşlemler audit log ile izlenir.")
        footer.setObjectName("LoginFooter")
        footer.setAlignment(Qt.AlignCenter)
        footer.setWordWrap(True)

        card_layout.addWidget(logo)
        card_layout.addWidget(title)
        card_layout.addWidget(subtitle)
        card_layout.addSpacing(10)
        card_layout.addWidget(identifier_label)
        card_layout.addWidget(self.identifier_input)
        card_layout.addWidget(password_label)
        card_layout.addWidget(self.password_input)
        card_layout.addSpacing(8)
        card_layout.addLayout(button_row)
        card_layout.addStretch()
        card_layout.addWidget(footer)

        root_layout.addWidget(card)

        self.identifier_input.setFocus()

    def try_login(self) -> None:
        identifier = self.identifier_input.text().strip()
        password = self.password_input.text()

        if not identifier:
            QMessageBox.warning(self, "FTM Giriş", "Kullanıcı adı veya e-posta boş olamaz.")
            self.identifier_input.setFocus()
            return

        if not password:
            QMessageBox.warning(self, "FTM Giriş", "Şifre boş olamaz.")
            self.password_input.setFocus()
            return

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
                    QMessageBox.warning(
                        self,
                        "Şifre Değişikliği Gerekli",
                        "Şifre değiştirilmeden ana panele giriş yapılamaz.",
                    )
                    self.password_input.clear()
                    self.password_input.setFocus()
                    return

            self.authenticated_user = authenticated_user
            self.accept()

        except AuthServiceError as exc:
            QMessageBox.warning(
                self,
                "FTM Giriş Başarısız",
                str(exc),
            )
            self.password_input.clear()
            self.password_input.setFocus()


def main() -> None:
    app = QApplication(sys.argv)
    app.setStyleSheet(get_application_stylesheet())

    login_dialog = LoginDialog()

    if login_dialog.exec() != QDialog.Accepted:
        sys.exit(0)

    if login_dialog.authenticated_user is None:
        sys.exit(0)

    window = FtmDesktopWindow(
        current_user=login_dialog.authenticated_user,
    )
    window.showMaximized()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()