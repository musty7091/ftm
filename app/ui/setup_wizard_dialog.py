from __future__ import annotations

from dataclasses import dataclass

from app.core.security import PasswordValidationError, validate_password_strength

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


DEFAULT_SQLITE_DATABASE_PATH = "data/ftm_local.db"


SETUP_WIZARD_STYLE = """
QDialog {
    background-color: #0f172a;
    color: #e5e7eb;
}

QDialog QWidget {
    background-color: #0f172a;
    color: #e5e7eb;
}

QFrame#SetupWizardHeader {
    background-color: #111827;
    border: 1px solid #24324a;
    border-radius: 18px;
}

QFrame#SetupWizardCard {
    background-color: #111827;
    border: 1px solid #24324a;
    border-radius: 18px;
}

QFrame#SetupWizardInfoBox {
    background-color: rgba(15, 23, 42, 0.68);
    border: 1px solid rgba(148, 163, 184, 0.22);
    border-radius: 14px;
}

QLabel {
    color: #e5e7eb;
    font-size: 13px;
    background-color: transparent;
}

QLabel#SetupWizardTitle {
    color: #f8fafc;
    font-size: 22px;
    font-weight: 900;
    background-color: transparent;
}

QLabel#SetupWizardSubtitle {
    color: #94a3b8;
    font-size: 13px;
    background-color: transparent;
}

QLabel#SetupWizardSectionTitle {
    color: #f8fafc;
    font-size: 15px;
    font-weight: 900;
    background-color: transparent;
}

QLabel#SetupWizardWarningText {
    color: #fde68a;
    font-size: 12px;
    font-weight: 700;
    background-color: transparent;
}

QLabel#SetupWizardSuccessText {
    color: #bbf7d0;
    font-size: 12px;
    font-weight: 700;
    background-color: transparent;
}

QGroupBox {
    color: #bfdbfe;
    font-size: 13px;
    font-weight: 900;
    border: 1px solid #334155;
    border-radius: 14px;
    margin-top: 12px;
    padding: 14px;
    background-color: #0f172a;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 8px;
    color: #bfdbfe;
    background-color: #111827;
}

QLineEdit,
QTextEdit {
    background-color: #0f172a;
    color: #f8fafc;
    border: 1px solid #334155;
    border-radius: 10px;
    padding: 8px 12px;
    selection-background-color: #2563eb;
    selection-color: #ffffff;
    font-size: 13px;
}

QLineEdit:focus,
QTextEdit:focus {
    border: 1px solid #38bdf8;
    background-color: #0b1220;
}

QLineEdit::placeholder,
QTextEdit::placeholder {
    color: #64748b;
}

QLineEdit[readOnly="true"] {
    background-color: #111827;
    color: #cbd5e1;
    border: 1px solid #475569;
}

QPushButton {
    background-color: #1e293b;
    color: #f8fafc;
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 9px 16px;
    font-weight: 800;
}

QPushButton:hover {
    background-color: #334155;
    border-color: #475569;
}

QPushButton:pressed {
    background-color: #0f172a;
}

QPushButton#SetupWizardPrimaryButton {
    background-color: #047857;
    color: #ffffff;
    border: 1px solid #10b981;
}

QPushButton#SetupWizardPrimaryButton:hover {
    background-color: #059669;
    border-color: #34d399;
}

QPushButton#SetupWizardCancelButton {
    background-color: #7f1d1d;
    color: #ffffff;
    border: 1px solid #f87171;
}

QPushButton#SetupWizardCancelButton:hover {
    background-color: #991b1b;
    border-color: #fca5a5;
}
"""


@dataclass(frozen=True)
class SetupWizardPayload:
    database_engine: str

    sqlite_database_path: str

    database_host: str
    database_port: int
    database_name: str
    database_user: str
    database_password: str

    company_name: str
    company_address: str
    company_phone: str
    company_email: str

    admin_username: str
    admin_full_name: str
    admin_password: str
    admin_email: str | None


class SetupWizardDialog(QDialog):
    def __init__(self, *, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.payload: SetupWizardPayload | None = None

        self.setWindowTitle("FTM İlk Kurulum Sihirbazı")
        self.resize(980, 720)
        self.setMinimumSize(880, 660)
        self.setStyleSheet(SETUP_WIZARD_STYLE)
        self.setSizeGripEnabled(True)

        self.sqlite_database_path_input = QLineEdit()
        self.sqlite_database_path_input.setPlaceholderText(DEFAULT_SQLITE_DATABASE_PATH)
        self.sqlite_database_path_input.setText(DEFAULT_SQLITE_DATABASE_PATH)
        self.sqlite_database_path_input.setReadOnly(True)
        self.sqlite_database_path_input.setToolTip(
            "FTM yerel SQLite veritabanı kullanır. "
            "Bu dosya AppData\\Local\\FTM altında güvenli şekilde yönetilir."
        )

        self.company_name_input = QLineEdit()
        self.company_name_input.setPlaceholderText("Firma adı")
        self.company_name_input.setText("FTM Finans Takip Merkezi")

        self.company_address_input = QTextEdit()
        self.company_address_input.setPlaceholderText("Firma adresi")
        self.company_address_input.setFixedHeight(72)

        self.company_phone_input = QLineEdit()
        self.company_phone_input.setPlaceholderText("Firma telefon")

        self.company_email_input = QLineEdit()
        self.company_email_input.setPlaceholderText("firma@example.com")

        self.admin_username_input = QLineEdit()
        self.admin_username_input.setPlaceholderText("admin")
        self.admin_username_input.setText("admin")

        self.admin_full_name_input = QLineEdit()
        self.admin_full_name_input.setPlaceholderText("Sistem Yöneticisi")
        self.admin_full_name_input.setText("Sistem Yöneticisi")

        self.admin_email_input = QLineEdit()
        self.admin_email_input.setPlaceholderText("admin@example.com")

        self.admin_password_input = QLineEdit()
        self.admin_password_input.setPlaceholderText("En az 8 karakter, harf ve rakam")
        self.admin_password_input.setEchoMode(QLineEdit.Password)

        self.admin_password_repeat_input = QLineEdit()
        self.admin_password_repeat_input.setPlaceholderText("Şifre tekrarı")
        self.admin_password_repeat_input.setEchoMode(QLineEdit.Password)

        self.status_label = QLabel(
            "FTM yerel SQLite veritabanı ile kurulacaktır. "
            "Veritabanı yolu sistem tarafından güvenli AppData klasöründe yönetilir."
        )
        self.status_label.setObjectName("SetupWizardSubtitle")
        self.status_label.setWordWrap(True)

        self.cancel_button = QPushButton("Vazgeç")
        self.cancel_button.setObjectName("SetupWizardCancelButton")
        self.cancel_button.clicked.connect(self.reject)

        self.finish_button = QPushButton("Kurulumu Tamamla")
        self.finish_button.setObjectName("SetupWizardPrimaryButton")
        self.finish_button.clicked.connect(self.accept)

        self._build_ui()

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 18, 18, 18)
        main_layout.setSpacing(14)

        main_layout.addWidget(self._build_header())
        main_layout.addWidget(self._build_main_card(), 1)
        main_layout.addLayout(self._build_button_layout())

    def _build_header(self) -> QWidget:
        header = QFrame()
        header.setObjectName("SetupWizardHeader")

        layout = QVBoxLayout(header)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(6)

        title = QLabel("FTM İlk Kurulum Sihirbazı")
        title.setObjectName("SetupWizardTitle")

        subtitle = QLabel(
            "Bu ekran FTM'nin ilk kullanım ayarlarını hazırlar. "
            "FTM yerel SQLite veritabanı ile çalışır; kullanıcıdan teknik veritabanı seçimi istenmez. "
            "Firma bilgilerini ve ilk ADMIN kullanıcısını oluşturman yeterlidir."
        )
        subtitle.setObjectName("SetupWizardSubtitle")
        subtitle.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(subtitle)

        return header

    def _build_main_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("SetupWizardCard")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(14)

        layout.addWidget(self._build_database_group())
        layout.addWidget(self._build_company_group())
        layout.addWidget(self._build_admin_group())
        layout.addWidget(self.status_label)

        return card

    def _build_database_group(self) -> QWidget:
        group = QGroupBox("1. Yerel Veri Dosyası")

        layout = QVBoxLayout(group)
        layout.setContentsMargins(14, 18, 14, 14)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(12)
        form.addRow("SQLite dosyası", self.sqlite_database_path_input)

        layout.addLayout(form)
        layout.addWidget(self._build_database_info_box())

        return group

    def _build_database_info_box(self) -> QWidget:
        box = QFrame()
        box.setObjectName("SetupWizardInfoBox")

        layout = QVBoxLayout(box)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)

        info = QLabel(
            "FTM bu kurulumda yerel SQLite veritabanı kullanır. "
            "Veri dosyası AppData\\Local\\FTM\\data altında yönetilir. "
            "Bu yapı tek bilgisayar kullanılan masaüstü finans takip sistemi için sade, güvenli ve taşınabilir bir kurulum sağlar."
        )
        info.setObjectName("SetupWizardWarningText")
        info.setWordWrap(True)

        layout.addWidget(info)

        return box

    def _build_company_group(self) -> QWidget:
        group = QGroupBox("2. Firma Bilgileri")

        grid = QGridLayout(group)
        grid.setContentsMargins(14, 18, 14, 14)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(12)

        grid.addWidget(QLabel("Firma adı"), 0, 0)
        grid.addWidget(self.company_name_input, 0, 1)

        grid.addWidget(QLabel("Telefon"), 0, 2)
        grid.addWidget(self.company_phone_input, 0, 3)

        grid.addWidget(QLabel("E-posta"), 1, 0)
        grid.addWidget(self.company_email_input, 1, 1)

        grid.addWidget(QLabel("Adres"), 2, 0)
        grid.addWidget(self.company_address_input, 2, 1, 1, 3)

        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)

        return group

    def _build_admin_group(self) -> QWidget:
        group = QGroupBox("3. İlk ADMIN Kullanıcısı")

        grid = QGridLayout(group)
        grid.setContentsMargins(14, 18, 14, 14)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(12)

        grid.addWidget(QLabel("Kullanıcı adı"), 0, 0)
        grid.addWidget(self.admin_username_input, 0, 1)

        grid.addWidget(QLabel("Ad soyad"), 0, 2)
        grid.addWidget(self.admin_full_name_input, 0, 3)

        grid.addWidget(QLabel("E-posta"), 1, 0)
        grid.addWidget(self.admin_email_input, 1, 1)

        grid.addWidget(QLabel("Şifre"), 2, 0)
        grid.addWidget(self.admin_password_input, 2, 1)

        grid.addWidget(QLabel("Şifre tekrar"), 2, 2)
        grid.addWidget(self.admin_password_repeat_input, 2, 3)

        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)

        return group

    def _build_button_layout(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(10)

        layout.addStretch(1)
        layout.addWidget(self.cancel_button)
        layout.addWidget(self.finish_button)

        return layout

    def _build_payload(self) -> SetupWizardPayload:
        database_engine = "sqlite"

        sqlite_database_path = DEFAULT_SQLITE_DATABASE_PATH
        self.sqlite_database_path_input.setText(DEFAULT_SQLITE_DATABASE_PATH)

        database_host = ""
        database_port = 0
        database_name = "ftm_local"
        database_user = ""
        database_password = ""

        company_name = self.company_name_input.text().strip()
        company_address = self.company_address_input.toPlainText().strip()
        company_phone = self.company_phone_input.text().strip()
        company_email = self.company_email_input.text().strip()

        admin_username = self.admin_username_input.text().strip()
        admin_full_name = self.admin_full_name_input.text().strip()
        admin_email = self.admin_email_input.text().strip()
        admin_password = self.admin_password_input.text()
        admin_password_repeat = self.admin_password_repeat_input.text()

        if sqlite_database_path != DEFAULT_SQLITE_DATABASE_PATH:
            raise ValueError("SQLite Local veritabanı yolu sistem tarafından sabitlenmiştir.")

        if not company_name:
            raise ValueError("Firma adı boş olamaz.")

        if company_email and "@" not in company_email:
            raise ValueError("Firma e-posta adresi geçerli görünmüyor.")

        if not admin_username:
            raise ValueError("ADMIN kullanıcı adı boş olamaz.")

        if not admin_full_name:
            raise ValueError("ADMIN ad soyad boş olamaz.")

        if admin_email and "@" not in admin_email:
            raise ValueError("ADMIN e-posta adresi geçerli görünmüyor.")

        if admin_password != admin_password_repeat:
            raise ValueError("ADMIN şifreleri aynı olmalıdır.")

        if admin_password.strip().lower() == admin_username.strip().lower():
            raise ValueError("ADMIN şifresi kullanıcı adıyla aynı olamaz.")

        try:
            validate_password_strength(admin_password)
        except PasswordValidationError as exc:
            raise ValueError(f"ADMIN şifresi geçersiz: {exc}") from exc

        return SetupWizardPayload(
            database_engine=database_engine,
            sqlite_database_path=sqlite_database_path,
            database_host=database_host,
            database_port=database_port,
            database_name=database_name,
            database_user=database_user,
            database_password=database_password,
            company_name=company_name,
            company_address=company_address,
            company_phone=company_phone,
            company_email=company_email,
            admin_username=admin_username,
            admin_full_name=admin_full_name,
            admin_password=admin_password,
            admin_email=admin_email or None,
        )

    def accept(self) -> None:
        try:
            self.payload = self._build_payload()
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Kurulum Bilgileri Eksik veya Hatalı",
                str(exc),
            )
            return

        super().accept()

    def get_payload(self) -> SetupWizardPayload:
        if self.payload is None:
            self.payload = self._build_payload()

        return self.payload


__all__ = [
    "SetupWizardDialog",
    "SetupWizardPayload",
    "DEFAULT_SQLITE_DATABASE_PATH",
]