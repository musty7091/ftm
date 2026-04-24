import sys
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from app.db.session import session_scope
from app.services.auth_service import AuthServiceError, AuthenticatedUser, authenticate_user
from app.ui.desktop_app import FtmDesktopWindow
from app.ui.styles import get_application_stylesheet


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

                session.flush()

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