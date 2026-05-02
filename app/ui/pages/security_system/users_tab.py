from __future__ import annotations

from datetime import datetime
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy import func, select

from app.core.security import PasswordValidationError, validate_password_strength
from app.db.session import session_scope
from app.models.enums import UserRole
from app.models.user import User
from app.services.audit_service import write_audit_log
from app.services.auth_service import hash_password


USERS_TAB_STYLE = """
QFrame#UsersTabCard {
    background-color: #111827;
    border: 1px solid #24324a;
    border-radius: 18px;
}

QFrame#UsersTabToolbar {
    background-color: rgba(15, 23, 42, 0.64);
    border: 1px solid rgba(148, 163, 184, 0.22);
    border-radius: 14px;
}

QFrame#UsersDialogPanel {
    background-color: #111827;
    border: 1px solid #24324a;
    border-radius: 18px;
}

QLabel#UsersTabTitle {
    color: #f8fafc;
    font-size: 16px;
    font-weight: 900;
}

QLabel#UsersTabSubtitle {
    color: #94a3b8;
    font-size: 12px;
}

QLabel#UsersTabFieldLabel {
    color: #bfdbfe;
    font-size: 12px;
    font-weight: 800;
}

QLabel#UsersTabCountBadge {
    color: #dbeafe;
    font-size: 11px;
    font-weight: 800;
    background-color: rgba(30, 64, 175, 0.32);
    border: 1px solid rgba(59, 130, 246, 0.42);
    border-radius: 8px;
    padding: 5px 9px;
}

QPushButton#UsersTabRefreshButton {
    background-color: #2563eb;
    color: #ffffff;
    border: 1px solid #3b82f6;
    border-radius: 11px;
    padding: 8px 14px;
    font-weight: 900;
}

QPushButton#UsersTabRefreshButton:hover {
    background-color: #1d4ed8;
}

QPushButton#UsersTabCreateButton {
    background-color: #047857;
    color: #ffffff;
    border: 1px solid #10b981;
    border-radius: 11px;
    padding: 8px 14px;
    font-weight: 900;
}

QPushButton#UsersTabCreateButton:hover {
    background-color: #059669;
}

QPushButton#UsersTabEditButton {
    background-color: #4338ca;
    color: #ffffff;
    border: 1px solid #818cf8;
    border-radius: 11px;
    padding: 8px 14px;
    font-weight: 900;
}

QPushButton#UsersTabEditButton:hover {
    background-color: #4f46e5;
}

QPushButton#UsersTabEditButton:disabled {
    background-color: rgba(30, 41, 59, 0.55);
    color: #64748b;
    border: 1px solid rgba(100, 116, 139, 0.32);
}

QPushButton#UsersTabActivateButton {
    background-color: #0f766e;
    color: #ffffff;
    border: 1px solid #14b8a6;
    border-radius: 11px;
    padding: 8px 14px;
    font-weight: 900;
}

QPushButton#UsersTabActivateButton:hover {
    background-color: #0d9488;
}

QPushButton#UsersTabActivateButton:disabled {
    background-color: rgba(30, 41, 59, 0.55);
    color: #64748b;
    border: 1px solid rgba(100, 116, 139, 0.32);
}

QPushButton#UsersTabDeactivateButton {
    background-color: #7f1d1d;
    color: #ffffff;
    border: 1px solid #f87171;
    border-radius: 11px;
    padding: 8px 14px;
    font-weight: 900;
}

QPushButton#UsersTabDeactivateButton:hover {
    background-color: #991b1b;
}

QPushButton#UsersTabDeactivateButton:disabled {
    background-color: rgba(30, 41, 59, 0.55);
    color: #64748b;
    border: 1px solid rgba(100, 116, 139, 0.32);
}

QPushButton#UsersTabResetPasswordButton {
    background-color: #92400e;
    color: #ffffff;
    border: 1px solid #f59e0b;
    border-radius: 11px;
    padding: 8px 14px;
    font-weight: 900;
}

QPushButton#UsersTabResetPasswordButton:hover {
    background-color: #b45309;
}

QPushButton#UsersTabResetPasswordButton:disabled {
    background-color: rgba(30, 41, 59, 0.55);
    color: #64748b;
    border: 1px solid rgba(100, 116, 139, 0.32);
}

QPushButton#UsersTabPassiveButton {
    background-color: #1f2937;
    color: #94a3b8;
    border: 1px solid #334155;
    border-radius: 10px;
    padding: 8px 12px;
    font-weight: 800;
}

QPushButton#UsersTabPassiveButton:disabled {
    background-color: rgba(30, 41, 59, 0.55);
    color: #64748b;
    border: 1px solid rgba(100, 116, 139, 0.32);
}

QLineEdit,
QComboBox {
    background-color: #0f172a;
    color: #f8fafc;
    border: 1px solid #334155;
    border-radius: 10px;
    padding: 8px 10px;
    font-size: 12px;
}

QLineEdit:hover,
QComboBox:hover {
    border: 1px solid #475569;
}

QLineEdit:focus,
QComboBox:focus {
    border: 1px solid #3b82f6;
}

QLineEdit:disabled {
    background-color: rgba(30, 41, 59, 0.72);
    color: #94a3b8;
    border: 1px solid #334155;
}

QComboBox::drop-down {
    border: none;
    width: 26px;
}

QComboBox QAbstractItemView {
    background-color: #111827;
    color: #e5e7eb;
    border: 1px solid #334155;
    selection-background-color: #2563eb;
    selection-color: #ffffff;
    outline: 0;
}

QCheckBox {
    color: #e5e7eb;
    font-size: 12px;
    font-weight: 700;
}

QTableWidget#UsersTable {
    background-color: #0f172a;
    color: #e5e7eb;
    border: 1px solid #334155;
    border-radius: 12px;
    gridline-color: #334155;
    selection-background-color: #2563eb;
    selection-color: #ffffff;
    alternate-background-color: #111827;
}

QTableWidget#UsersTable::item {
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


def _role_text(role: Any) -> str:
    if hasattr(role, "value"):
        return str(role.value)

    return str(role or "-").strip().upper() or "-"


def _user_audit_values(user: User) -> dict[str, Any]:
    return {
        "id": int(user.id),
        "username": str(user.username or ""),
        "full_name": str(user.full_name or ""),
        "email": user.email,
        "role": _role_text(user.role),
        "is_active": bool(user.is_active),
        "must_change_password": bool(user.must_change_password),
    }


def _validate_password_policy(password: str) -> str | None:
    try:
        validate_password_strength(password)
    except PasswordValidationError as exc:
        return str(exc)

    return None


class NewUserDialog(QDialog):
    def __init__(
        self,
        *,
        actor_user_id: int | None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.actor_user_id = actor_user_id

        self.setWindowTitle("Yeni Kullanıcı Ekle")
        self.setModal(True)
        self.setMinimumWidth(620)
        self.setStyleSheet(USERS_TAB_STYLE)

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Örn: ahmet")

        self.full_name_input = QLineEdit()
        self.full_name_input.setPlaceholderText("Örn: Ahmet Yılmaz")

        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("Örn: ahmet@example.com")

        self.role_combo = QComboBox()
        self.role_combo.addItem("ADMIN", UserRole.ADMIN.value)
        self.role_combo.addItem("FINANCE", UserRole.FINANCE.value)
        self.role_combo.addItem("DATA_ENTRY", UserRole.DATA_ENTRY.value)
        self.role_combo.addItem("VIEWER", UserRole.VIEWER.value)

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("En az 8 karakter, harf ve rakam")
        self.password_input.setEchoMode(QLineEdit.Password)

        self.password_repeat_input = QLineEdit()
        self.password_repeat_input.setPlaceholderText("Geçici şifre tekrar")
        self.password_repeat_input.setEchoMode(QLineEdit.Password)

        self.is_active_checkbox = QCheckBox("Kullanıcı aktif olsun")
        self.is_active_checkbox.setChecked(True)

        self.must_change_password_checkbox = QCheckBox("İlk girişte şifre değiştirsin")
        self.must_change_password_checkbox.setChecked(True)

        self._build_ui()

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 18, 18, 18)
        main_layout.setSpacing(14)

        panel = QFrame()
        panel.setObjectName("UsersDialogPanel")

        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(18, 16, 18, 16)
        panel_layout.setSpacing(14)

        title = QLabel("Yeni Kullanıcı Ekle")
        title.setObjectName("UsersTabTitle")

        subtitle = QLabel(
            "Bu form ADMIN yetkisiyle yeni kullanıcı oluşturur. "
            "Şifre veritabanına açık metin olarak değil, güvenli hash olarak kaydedilir. "
            "Şifre en az 8 karakter olmalı, en az bir harf ve en az bir rakam içermelidir."
        )
        subtitle.setObjectName("UsersTabSubtitle")
        subtitle.setWordWrap(True)

        form_layout = QGridLayout()
        form_layout.setHorizontalSpacing(14)
        form_layout.setVerticalSpacing(12)

        form_layout.addWidget(self._field_label("Kullanıcı Adı"), 0, 0)
        form_layout.addWidget(self.username_input, 0, 1)

        form_layout.addWidget(self._field_label("Ad Soyad"), 1, 0)
        form_layout.addWidget(self.full_name_input, 1, 1)

        form_layout.addWidget(self._field_label("E-posta"), 2, 0)
        form_layout.addWidget(self.email_input, 2, 1)

        form_layout.addWidget(self._field_label("Rol"), 3, 0)
        form_layout.addWidget(self.role_combo, 3, 1)

        form_layout.addWidget(self._field_label("Geçici Şifre"), 4, 0)
        form_layout.addWidget(self.password_input, 4, 1)

        form_layout.addWidget(self._field_label("Şifre Tekrar"), 5, 0)
        form_layout.addWidget(self.password_repeat_input, 5, 1)

        form_layout.addWidget(self.is_active_checkbox, 6, 1)
        form_layout.addWidget(self.must_change_password_checkbox, 7, 1)

        button_layout = QHBoxLayout()
        button_layout.addStretch(1)

        cancel_button = QPushButton("Vazgeç")
        cancel_button.setObjectName("UsersTabPassiveButton")
        cancel_button.clicked.connect(self.reject)

        save_button = QPushButton("Kullanıcıyı Kaydet")
        save_button.setObjectName("UsersTabCreateButton")
        save_button.clicked.connect(self._save_user)

        button_layout.addWidget(cancel_button)
        button_layout.addWidget(save_button)

        panel_layout.addWidget(title)
        panel_layout.addWidget(subtitle)
        panel_layout.addLayout(form_layout)
        panel_layout.addLayout(button_layout)

        main_layout.addWidget(panel)

    def _field_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("UsersTabFieldLabel")

        return label

    def _save_user(self) -> None:
        username = self.username_input.text().strip()
        full_name = self.full_name_input.text().strip()
        email = self.email_input.text().strip()
        role_text = str(self.role_combo.currentData() or UserRole.VIEWER.value)
        password = self.password_input.text()
        password_repeat = self.password_repeat_input.text()

        validation_error = self._validate_form(
            username=username,
            full_name=full_name,
            email=email,
            password=password,
            password_repeat=password_repeat,
        )

        if validation_error:
            QMessageBox.warning(
                self,
                "Kullanıcı Kaydedilemedi",
                validation_error,
            )
            return

        try:
            self._create_user(
                username=username,
                full_name=full_name,
                email=email or None,
                role_text=role_text,
                password=password,
                is_active=self.is_active_checkbox.isChecked(),
                must_change_password=self.must_change_password_checkbox.isChecked(),
            )

            QMessageBox.information(
                self,
                "Kullanıcı Oluşturuldu",
                f"{username} kullanıcısı başarıyla oluşturuldu.",
            )
            self.accept()

        except Exception as exc:
            QMessageBox.critical(
                self,
                "Kullanıcı Kaydedilemedi",
                f"Kullanıcı kaydedilirken hata oluştu:\n\n{exc}",
            )

    def _validate_form(
        self,
        *,
        username: str,
        full_name: str,
        email: str,
        password: str,
        password_repeat: str,
    ) -> str | None:
        if not username:
            return "Kullanıcı adı boş olamaz."

        if len(username) < 3:
            return "Kullanıcı adı en az 3 karakter olmalıdır."

        if " " in username:
            return "Kullanıcı adında boşluk olmamalıdır."

        if not full_name:
            return "Ad Soyad boş olamaz."

        if email and "@" not in email:
            return "E-posta adresi geçerli görünmüyor."

        if not password:
            return "Geçici şifre boş olamaz."

        if password != password_repeat:
            return "Şifre ve şifre tekrar alanları aynı olmalıdır."

        if password.strip().lower() == username.strip().lower():
            return "Geçici şifre kullanıcı adı ile aynı olmamalıdır."

        password_policy_error = _validate_password_policy(password)

        if password_policy_error:
            return password_policy_error

        return None

    def _create_user(
        self,
        *,
        username: str,
        full_name: str,
        email: str | None,
        role_text: str,
        password: str,
        is_active: bool,
        must_change_password: bool,
    ) -> None:
        normalized_username = username.strip()
        normalized_email = None if email is None else email.strip()
        normalized_role = UserRole(role_text)

        with session_scope() as session:
            username_exists_statement = select(User).where(
                func.lower(User.username) == normalized_username.lower()
            )
            username_exists = session.execute(username_exists_statement).scalar_one_or_none()

            if username_exists is not None:
                raise ValueError("Bu kullanıcı adı zaten kayıtlı.")

            if normalized_email:
                email_exists_statement = select(User).where(
                    func.lower(User.email) == normalized_email.lower()
                )
                email_exists = session.execute(email_exists_statement).scalar_one_or_none()

                if email_exists is not None:
                    raise ValueError("Bu e-posta adresi zaten kayıtlı.")

            user = User(
                username=normalized_username,
                full_name=full_name.strip(),
                email=normalized_email,
                password_hash=hash_password(password),
                role=normalized_role,
                is_active=is_active,
                must_change_password=must_change_password,
            )

            session.add(user)
            session.flush()

            write_audit_log(
                session,
                user_id=self.actor_user_id,
                action="USER_CREATED",
                entity_type="User",
                entity_id=user.id,
                description=f"Kullanıcı oluşturuldu: {user.username}",
                old_values=None,
                new_values=_user_audit_values(user),
            )


class EditUserDialog(QDialog):
    def __init__(
        self,
        *,
        user_id: int,
        current_user_id: int | None,
        current_username: str | None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.user_id = user_id
        self.current_user_id = current_user_id
        self.current_username = current_username

        self.setWindowTitle("Kullanıcı Bilgilerini Düzenle")
        self.setModal(True)
        self.setMinimumWidth(640)
        self.setStyleSheet(USERS_TAB_STYLE)

        self.username_input = QLineEdit()
        self.username_input.setEnabled(False)

        self.full_name_input = QLineEdit()
        self.full_name_input.setPlaceholderText("Ad Soyad")

        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("E-posta")

        self.role_combo = QComboBox()
        self.role_combo.addItem("ADMIN", UserRole.ADMIN.value)
        self.role_combo.addItem("FINANCE", UserRole.FINANCE.value)
        self.role_combo.addItem("DATA_ENTRY", UserRole.DATA_ENTRY.value)
        self.role_combo.addItem("VIEWER", UserRole.VIEWER.value)

        self.must_change_password_checkbox = QCheckBox("İlk girişte şifre değiştirsin")

        self._load_user()
        self._build_ui()

    def _load_user(self) -> None:
        with session_scope() as session:
            user = session.get(User, self.user_id)

            if user is None:
                raise ValueError("Kullanıcı kaydı bulunamadı.")

            self.username_input.setText(str(user.username or ""))
            self.full_name_input.setText(str(user.full_name or ""))
            self.email_input.setText(str(user.email or ""))
            self.must_change_password_checkbox.setChecked(bool(user.must_change_password))

            role_text = _role_text(user.role)
            role_index = self.role_combo.findData(role_text)

            if role_index >= 0:
                self.role_combo.setCurrentIndex(role_index)

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 18, 18, 18)
        main_layout.setSpacing(14)

        panel = QFrame()
        panel.setObjectName("UsersDialogPanel")

        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(18, 16, 18, 16)
        panel_layout.setSpacing(14)

        title = QLabel("Kullanıcı Bilgilerini Düzenle")
        title.setObjectName("UsersTabTitle")

        subtitle = QLabel(
            "Bu form kullanıcı adı dışındaki temel bilgileri düzenler. "
            "Kullanıcı adı giriş kimliği olduğu için bu adımda değiştirilemez."
        )
        subtitle.setObjectName("UsersTabSubtitle")
        subtitle.setWordWrap(True)

        form_layout = QGridLayout()
        form_layout.setHorizontalSpacing(14)
        form_layout.setVerticalSpacing(12)

        form_layout.addWidget(self._field_label("Kullanıcı Adı"), 0, 0)
        form_layout.addWidget(self.username_input, 0, 1)

        form_layout.addWidget(self._field_label("Ad Soyad"), 1, 0)
        form_layout.addWidget(self.full_name_input, 1, 1)

        form_layout.addWidget(self._field_label("E-posta"), 2, 0)
        form_layout.addWidget(self.email_input, 2, 1)

        form_layout.addWidget(self._field_label("Rol"), 3, 0)
        form_layout.addWidget(self.role_combo, 3, 1)

        form_layout.addWidget(self.must_change_password_checkbox, 4, 1)

        button_layout = QHBoxLayout()
        button_layout.addStretch(1)

        cancel_button = QPushButton("Vazgeç")
        cancel_button.setObjectName("UsersTabPassiveButton")
        cancel_button.clicked.connect(self.reject)

        save_button = QPushButton("Bilgileri Kaydet")
        save_button.setObjectName("UsersTabEditButton")
        save_button.clicked.connect(self._save_user)

        button_layout.addWidget(cancel_button)
        button_layout.addWidget(save_button)

        panel_layout.addWidget(title)
        panel_layout.addWidget(subtitle)
        panel_layout.addLayout(form_layout)
        panel_layout.addLayout(button_layout)

        main_layout.addWidget(panel)

    def _field_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("UsersTabFieldLabel")

        return label

    def _save_user(self) -> None:
        full_name = self.full_name_input.text().strip()
        email = self.email_input.text().strip()
        new_role_text = str(self.role_combo.currentData() or UserRole.VIEWER.value)
        must_change_password = self.must_change_password_checkbox.isChecked()

        validation_error = self._validate_form(
            full_name=full_name,
            email=email,
        )

        if validation_error:
            QMessageBox.warning(
                self,
                "Kullanıcı Güncellenemedi",
                validation_error,
            )
            return

        answer = QMessageBox.question(
            self,
            "Kullanıcı Güncellensin mi?",
            "Kullanıcı bilgilerini kaydetmek istiyor musun?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if answer != QMessageBox.Yes:
            return

        try:
            self._update_user(
                full_name=full_name,
                email=email or None,
                new_role_text=new_role_text,
                must_change_password=must_change_password,
            )

            QMessageBox.information(
                self,
                "Kullanıcı Güncellendi",
                "Kullanıcı bilgileri başarıyla güncellendi.",
            )
            self.accept()

        except Exception as exc:
            QMessageBox.critical(
                self,
                "Kullanıcı Güncellenemedi",
                f"Kullanıcı güncellenirken hata oluştu:\n\n{exc}",
            )

    def _validate_form(
        self,
        *,
        full_name: str,
        email: str,
    ) -> str | None:
        if not full_name:
            return "Ad Soyad boş olamaz."

        if email and "@" not in email:
            return "E-posta adresi geçerli görünmüyor."

        return None

    def _update_user(
        self,
        *,
        full_name: str,
        email: str | None,
        new_role_text: str,
        must_change_password: bool,
    ) -> None:
        normalized_email = None if email is None else email.strip()
        new_role = UserRole(new_role_text)

        with session_scope() as session:
            user = session.get(User, self.user_id)

            if user is None:
                raise ValueError("Kullanıcı kaydı bulunamadı.")

            old_values = _user_audit_values(user)
            old_role_text = _role_text(user.role)

            if normalized_email:
                email_exists_statement = select(User).where(
                    func.lower(User.email) == normalized_email.lower(),
                    User.id != self.user_id,
                )
                email_exists = session.execute(email_exists_statement).scalar_one_or_none()

                if email_exists is not None:
                    raise ValueError("Bu e-posta adresi başka bir kullanıcıda kayıtlı.")

            if old_role_text == UserRole.ADMIN.value and new_role != UserRole.ADMIN:
                self._validate_admin_role_can_change(
                    session=session,
                    user=user,
                )

            user.full_name = full_name.strip()
            user.email = normalized_email
            user.role = new_role
            user.must_change_password = must_change_password

            session.flush()

            write_audit_log(
                session,
                user_id=self.current_user_id,
                action="USER_UPDATED",
                entity_type="User",
                entity_id=user.id,
                description=f"Kullanıcı bilgileri güncellendi: {user.username}",
                old_values=old_values,
                new_values=_user_audit_values(user),
            )

    def _validate_admin_role_can_change(
        self,
        *,
        session,
        user: User,
    ) -> None:
        if self.current_user_id is not None and int(user.id) == self.current_user_id:
            raise ValueError("Kendi ADMIN rolünü değiştiremezsin.")

        if self.current_username and str(user.username).lower() == self.current_username.lower():
            raise ValueError("Kendi ADMIN rolünü değiştiremezsin.")

        if not bool(user.is_active):
            return

        active_admin_count_statement = select(func.count(User.id)).where(
            User.role == UserRole.ADMIN,
            User.is_active.is_(True),
        )
        active_admin_count = session.execute(active_admin_count_statement).scalar_one()

        if int(active_admin_count or 0) <= 1:
            raise ValueError("Son aktif ADMIN kullanıcısının rolü değiştirilemez.")


class ResetPasswordDialog(QDialog):
    def __init__(
        self,
        *,
        user_id: int,
        username: str,
        actor_user_id: int | None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.user_id = user_id
        self.username = username
        self.actor_user_id = actor_user_id

        self.setWindowTitle("Şifre Sıfırla")
        self.setModal(True)
        self.setMinimumWidth(560)
        self.setStyleSheet(USERS_TAB_STYLE)

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("En az 8 karakter, harf ve rakam")
        self.password_input.setEchoMode(QLineEdit.Password)

        self.password_repeat_input = QLineEdit()
        self.password_repeat_input.setPlaceholderText("Yeni geçici şifre tekrar")
        self.password_repeat_input.setEchoMode(QLineEdit.Password)

        self.must_change_password_checkbox = QCheckBox("Kullanıcı ilk girişte şifre değiştirsin")
        self.must_change_password_checkbox.setChecked(True)

        self._build_ui()

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 18, 18, 18)
        main_layout.setSpacing(14)

        panel = QFrame()
        panel.setObjectName("UsersDialogPanel")

        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(18, 16, 18, 16)
        panel_layout.setSpacing(14)

        title = QLabel("Kullanıcı Şifresini Sıfırla")
        title.setObjectName("UsersTabTitle")

        subtitle = QLabel(
            f"{self.username} kullanıcısı için yeni geçici şifre belirle. "
            "Şifre güvenli hash olarak kaydedilecek. "
            "Şifre en az 8 karakter olmalı, en az bir harf ve en az bir rakam içermelidir."
        )
        subtitle.setObjectName("UsersTabSubtitle")
        subtitle.setWordWrap(True)

        form_layout = QGridLayout()
        form_layout.setHorizontalSpacing(14)
        form_layout.setVerticalSpacing(12)

        form_layout.addWidget(self._field_label("Yeni Geçici Şifre"), 0, 0)
        form_layout.addWidget(self.password_input, 0, 1)

        form_layout.addWidget(self._field_label("Şifre Tekrar"), 1, 0)
        form_layout.addWidget(self.password_repeat_input, 1, 1)

        form_layout.addWidget(self.must_change_password_checkbox, 2, 1)

        button_layout = QHBoxLayout()
        button_layout.addStretch(1)

        cancel_button = QPushButton("Vazgeç")
        cancel_button.setObjectName("UsersTabPassiveButton")
        cancel_button.clicked.connect(self.reject)

        save_button = QPushButton("Şifreyi Sıfırla")
        save_button.setObjectName("UsersTabResetPasswordButton")
        save_button.clicked.connect(self._reset_password)

        button_layout.addWidget(cancel_button)
        button_layout.addWidget(save_button)

        panel_layout.addWidget(title)
        panel_layout.addWidget(subtitle)
        panel_layout.addLayout(form_layout)
        panel_layout.addLayout(button_layout)

        main_layout.addWidget(panel)

    def _field_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("UsersTabFieldLabel")

        return label

    def _reset_password(self) -> None:
        password = self.password_input.text()
        password_repeat = self.password_repeat_input.text()

        validation_error = self._validate_password(
            password=password,
            password_repeat=password_repeat,
        )

        if validation_error:
            QMessageBox.warning(
                self,
                "Şifre Sıfırlanamadı",
                validation_error,
            )
            return

        answer = QMessageBox.question(
            self,
            "Şifre Sıfırlansın mı?",
            f"{self.username} kullanıcısının şifresini sıfırlamak istiyor musun?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if answer != QMessageBox.Yes:
            return

        try:
            with session_scope() as session:
                user = session.get(User, self.user_id)

                if user is None:
                    raise ValueError("Kullanıcı kaydı bulunamadı.")

                old_values = {
                    "id": int(user.id),
                    "username": str(user.username or ""),
                    "must_change_password": bool(user.must_change_password),
                }

                user.password_hash = hash_password(password)
                user.must_change_password = self.must_change_password_checkbox.isChecked()

                session.flush()

                write_audit_log(
                    session,
                    user_id=self.actor_user_id,
                    action="USER_PASSWORD_RESET",
                    entity_type="User",
                    entity_id=user.id,
                    description=f"Kullanıcı şifresi sıfırlandı: {user.username}",
                    old_values=old_values,
                    new_values={
                        "id": int(user.id),
                        "username": str(user.username or ""),
                        "must_change_password": bool(user.must_change_password),
                    },
                )

            QMessageBox.information(
                self,
                "Şifre Sıfırlandı",
                f"{self.username} kullanıcısının şifresi başarıyla sıfırlandı.",
            )
            self.accept()

        except Exception as exc:
            QMessageBox.critical(
                self,
                "Şifre Sıfırlanamadı",
                f"Şifre sıfırlanırken hata oluştu:\n\n{exc}",
            )

    def _validate_password(
        self,
        *,
        password: str,
        password_repeat: str,
    ) -> str | None:
        if not password:
            return "Yeni geçici şifre boş olamaz."

        if password != password_repeat:
            return "Şifre ve şifre tekrar alanları aynı olmalıdır."

        if password.strip().lower() == self.username.strip().lower():
            return "Şifre kullanıcı adı ile aynı olmamalıdır."

        password_policy_error = _validate_password_policy(password)

        if password_policy_error:
            return password_policy_error

        return None


class UsersTab(QWidget):
    def __init__(self) -> None:
        super().__init__()

        self.setStyleSheet(USERS_TAB_STYLE)

        self.user_count_label = QLabel("0 kullanıcı")
        self.user_count_label.setObjectName("UsersTabCountBadge")

        self.edit_button = QPushButton("Bilgileri Düzenle")
        self.edit_button.setObjectName("UsersTabEditButton")
        self.edit_button.setEnabled(False)
        self.edit_button.clicked.connect(self.open_edit_user_dialog)

        self.activate_button = QPushButton("Aktif Yap")
        self.activate_button.setObjectName("UsersTabActivateButton")
        self.activate_button.setEnabled(False)
        self.activate_button.clicked.connect(self.activate_selected_user)

        self.deactivate_button = QPushButton("Pasif Yap")
        self.deactivate_button.setObjectName("UsersTabDeactivateButton")
        self.deactivate_button.setEnabled(False)
        self.deactivate_button.clicked.connect(self.deactivate_selected_user)

        self.reset_password_button = QPushButton("Şifre Sıfırla")
        self.reset_password_button.setObjectName("UsersTabResetPasswordButton")
        self.reset_password_button.setEnabled(False)
        self.reset_password_button.clicked.connect(self.open_reset_password_dialog)

        self.table = QTableWidget()
        self.table.setObjectName("UsersTable")
        self.table.setColumnCount(10)
        self.table.setHorizontalHeaderLabels(
            [
                "ID",
                "Kullanıcı Adı",
                "Ad Soyad",
                "E-posta",
                "Rol",
                "Aktif",
                "Şifre Değişsin",
                "Son Giriş",
                "Oluşturma",
                "Güncelleme",
            ]
        )
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.itemSelectionChanged.connect(self.update_action_buttons)

        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(8, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(9, QHeaderView.ResizeToContents)

        self._build_ui()
        self.load_users()

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 14, 12, 12)
        main_layout.setSpacing(12)

        card = QFrame()
        card.setObjectName("UsersTabCard")

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 16, 18, 16)
        card_layout.setSpacing(14)

        title = QLabel("Kullanıcı Yönetimi")
        title.setObjectName("UsersTabTitle")

        subtitle = QLabel(
            "Bu ekranda sistem kullanıcıları gerçek veritabanından okunur. "
            "Kullanıcı yönetimi işlemleri audit log ile kayıt altına alınır."
        )
        subtitle.setObjectName("UsersTabSubtitle")
        subtitle.setWordWrap(True)

        toolbar = self._build_toolbar()

        card_layout.addWidget(title)
        card_layout.addWidget(subtitle)
        card_layout.addWidget(toolbar)
        card_layout.addWidget(self.table, 1)

        info_button = QPushButton("Kullanıcı adı bu aşamada değiştirilemez; giriş kimliği olarak sabit tutulur")
        info_button.setObjectName("UsersTabPassiveButton")
        info_button.setEnabled(False)

        card_layout.addWidget(info_button, 0, Qt.AlignRight)

        main_layout.addWidget(card, 1)

    def _build_toolbar(self) -> QWidget:
        toolbar = QFrame()
        toolbar.setObjectName("UsersTabToolbar")

        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        info = QLabel(
            "Tablodan kullanıcı seçerek bilgilerini düzenleyebilir, aktif/pasif yapabilir veya şifresini sıfırlayabilirsin."
        )
        info.setObjectName("UsersTabSubtitle")
        info.setWordWrap(True)

        create_button = QPushButton("Yeni Kullanıcı Ekle")
        create_button.setObjectName("UsersTabCreateButton")
        create_button.clicked.connect(self.open_new_user_dialog)

        refresh_button = QPushButton("Listeyi Yenile")
        refresh_button.setObjectName("UsersTabRefreshButton")
        refresh_button.clicked.connect(self.load_users)

        layout.addWidget(info, 1)
        layout.addWidget(self.user_count_label, 0, Qt.AlignVCenter)
        layout.addWidget(create_button, 0, Qt.AlignVCenter)
        layout.addWidget(self.edit_button, 0, Qt.AlignVCenter)
        layout.addWidget(self.activate_button, 0, Qt.AlignVCenter)
        layout.addWidget(self.deactivate_button, 0, Qt.AlignVCenter)
        layout.addWidget(self.reset_password_button, 0, Qt.AlignVCenter)
        layout.addWidget(refresh_button, 0, Qt.AlignVCenter)

        return toolbar

    def open_new_user_dialog(self) -> None:
        dialog = NewUserDialog(
            actor_user_id=self._current_user_id(),
            parent=self,
        )

        if dialog.exec() != QDialog.Accepted:
            return

        self.load_users()

    def open_edit_user_dialog(self) -> None:
        selected_user = self._selected_user_from_table()

        if selected_user is None:
            QMessageBox.warning(
                self,
                "Kullanıcı Seçilmedi",
                "Düzenlemek için önce tablodan bir kullanıcı seçmelisin.",
            )
            return

        user_id, _username, _is_active = selected_user

        try:
            dialog = EditUserDialog(
                user_id=user_id,
                current_user_id=self._current_user_id(),
                current_username=self._current_username(),
                parent=self,
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Kullanıcı Açılmadı",
                f"Kullanıcı bilgileri açılırken hata oluştu:\n\n{exc}",
            )
            return

        if dialog.exec() != QDialog.Accepted:
            return

        self.load_users()

    def open_reset_password_dialog(self) -> None:
        selected_user = self._selected_user_from_table()

        if selected_user is None:
            QMessageBox.warning(
                self,
                "Kullanıcı Seçilmedi",
                "Şifre sıfırlamak için önce tablodan bir kullanıcı seçmelisin.",
            )
            return

        user_id, username, _is_active = selected_user

        dialog = ResetPasswordDialog(
            user_id=user_id,
            username=username,
            actor_user_id=self._current_user_id(),
            parent=self,
        )

        if dialog.exec() != QDialog.Accepted:
            return

        self.load_users()

    def load_users(self) -> None:
        try:
            users = self._fetch_users()
            self._fill_table(users)
            self.user_count_label.setText(f"{len(users)} kullanıcı")
            self.update_action_buttons()
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Kullanıcı Listesi Okunamadı",
                f"Kullanıcı listesi okunurken hata oluştu:\n\n{exc}",
            )

    def _fetch_users(self) -> list[User]:
        with session_scope() as session:
            statement = select(User).order_by(
                User.is_active.desc(),
                User.username.asc(),
                User.id.asc(),
            )
            users = session.execute(statement).scalars().all()

            return list(users)

    def _fill_table(self, users: list[User]) -> None:
        self.table.setRowCount(0)

        for row_index, user in enumerate(users):
            self.table.insertRow(row_index)

            values = [
                user.id,
                user.username,
                user.full_name,
                user.email or "-",
                _role_text(user.role),
                "Evet" if user.is_active else "Hayır",
                "Evet" if user.must_change_password else "Hayır",
                self._format_datetime(user.last_login_at),
                self._format_datetime(user.created_at),
                self._format_datetime(user.updated_at),
            ]

            for column_index, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)

                if column_index == 0:
                    item.setTextAlignment(Qt.AlignCenter)

                if column_index in {5, 6}:
                    item.setTextAlignment(Qt.AlignCenter)

                if column_index in {7, 8, 9}:
                    item.setTextAlignment(Qt.AlignCenter)

                self.table.setItem(row_index, column_index, item)

        self.table.resizeRowsToContents()

    def update_action_buttons(self) -> None:
        selected_user = self._selected_user_from_table()

        if selected_user is None:
            self.edit_button.setEnabled(False)
            self.activate_button.setEnabled(False)
            self.deactivate_button.setEnabled(False)
            self.reset_password_button.setEnabled(False)
            return

        _user_id, _username, is_active = selected_user

        self.edit_button.setEnabled(True)
        self.activate_button.setEnabled(not is_active)
        self.deactivate_button.setEnabled(is_active)
        self.reset_password_button.setEnabled(True)

    def activate_selected_user(self) -> None:
        selected_user = self._selected_user_from_table()

        if selected_user is None:
            QMessageBox.warning(
                self,
                "Kullanıcı Seçilmedi",
                "Aktif yapmak için önce tablodan bir kullanıcı seçmelisin.",
            )
            return

        user_id, username, is_active = selected_user

        if is_active:
            QMessageBox.information(
                self,
                "Kullanıcı Zaten Aktif",
                f"{username} kullanıcısı zaten aktif durumda.",
            )
            return

        answer = QMessageBox.question(
            self,
            "Kullanıcı Aktif Yapılsın mı?",
            f"{username} kullanıcısını aktif yapmak istiyor musun?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if answer != QMessageBox.Yes:
            return

        self._set_user_active_status(
            user_id=user_id,
            target_is_active=True,
        )

    def deactivate_selected_user(self) -> None:
        selected_user = self._selected_user_from_table()

        if selected_user is None:
            QMessageBox.warning(
                self,
                "Kullanıcı Seçilmedi",
                "Pasif yapmak için önce tablodan bir kullanıcı seçmelisin.",
            )
            return

        user_id, username, is_active = selected_user

        if not is_active:
            QMessageBox.information(
                self,
                "Kullanıcı Zaten Pasif",
                f"{username} kullanıcısı zaten pasif durumda.",
            )
            return

        answer = QMessageBox.question(
            self,
            "Kullanıcı Pasif Yapılsın mı?",
            f"{username} kullanıcısını pasif yapmak istiyor musun?\n\n"
            "Pasif kullanıcı uygulamaya giriş yapamaz.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if answer != QMessageBox.Yes:
            return

        self._set_user_active_status(
            user_id=user_id,
            target_is_active=False,
        )

    def _set_user_active_status(
        self,
        *,
        user_id: int,
        target_is_active: bool,
    ) -> None:
        try:
            with session_scope() as session:
                user = session.get(User, user_id)

                if user is None:
                    raise ValueError("Kullanıcı kaydı bulunamadı.")

                if bool(user.is_active) == target_is_active:
                    durum = "aktif" if target_is_active else "pasif"
                    raise ValueError(f"Bu kullanıcı zaten {durum} durumda.")

                old_values = _user_audit_values(user)

                if not target_is_active:
                    self._validate_user_can_be_deactivated(
                        session=session,
                        user=user,
                    )

                user.is_active = target_is_active
                session.flush()

                write_audit_log(
                    session,
                    user_id=self._current_user_id(),
                    action="USER_ACTIVATED" if target_is_active else "USER_DEACTIVATED",
                    entity_type="User",
                    entity_id=user.id,
                    description=(
                        f"Kullanıcı aktif yapıldı: {user.username}"
                        if target_is_active
                        else f"Kullanıcı pasif yapıldı: {user.username}"
                    ),
                    old_values=old_values,
                    new_values=_user_audit_values(user),
                )

            QMessageBox.information(
                self,
                "İşlem Tamamlandı",
                "Kullanıcı durumu başarıyla güncellendi.",
            )
            self.load_users()

        except Exception as exc:
            QMessageBox.critical(
                self,
                "Kullanıcı Durumu Güncellenemedi",
                f"Kullanıcı durumu güncellenirken hata oluştu:\n\n{exc}",
            )

    def _validate_user_can_be_deactivated(
        self,
        *,
        session,
        user: User,
    ) -> None:
        current_user_id = self._current_user_id()
        current_username = self._current_username()

        if current_user_id is not None and int(user.id) == current_user_id:
            raise ValueError("Kendi kullanıcını pasif yapamazsın.")

        if current_username and str(user.username).lower() == current_username.lower():
            raise ValueError("Kendi kullanıcını pasif yapamazsın.")

        if _role_text(user.role) != UserRole.ADMIN.value:
            return

        active_admin_count_statement = select(func.count(User.id)).where(
            User.role == UserRole.ADMIN,
            User.is_active.is_(True),
        )
        active_admin_count = session.execute(active_admin_count_statement).scalar_one()

        if int(active_admin_count or 0) <= 1:
            raise ValueError("Son aktif ADMIN kullanıcısı pasif yapılamaz.")

    def _selected_user_from_table(self) -> tuple[int, str, bool] | None:
        selected_items = self.table.selectedItems()

        if not selected_items:
            return None

        selected_row = selected_items[0].row()

        id_item = self.table.item(selected_row, 0)
        username_item = self.table.item(selected_row, 1)
        active_item = self.table.item(selected_row, 5)

        if id_item is None or username_item is None or active_item is None:
            return None

        try:
            user_id = int(id_item.text())
        except ValueError:
            return None

        username = username_item.text().strip()
        is_active = active_item.text().strip().lower() == "evet"

        return user_id, username, is_active

    def _current_user_id(self) -> int | None:
        current_user = getattr(self.window(), "current_user", None)

        if current_user is None:
            return None

        current_user_id = getattr(current_user, "id", None)

        if current_user_id is None:
            return None

        try:
            return int(current_user_id)
        except (TypeError, ValueError):
            return None

    def _current_username(self) -> str | None:
        current_user = getattr(self.window(), "current_user", None)

        if current_user is None:
            return None

        username = getattr(current_user, "username", None)

        if not username:
            return None

        return str(username).strip()

    def _format_datetime(self, value: Any) -> str:
        if value is None:
            return "-"

        if isinstance(value, datetime):
            return value.strftime("%d.%m.%Y %H:%M")

        return str(value)


def build_users_tab() -> QWidget:
    return UsersTab()


__all__ = [
    "NewUserDialog",
    "EditUserDialog",
    "ResetPasswordDialog",
    "UsersTab",
    "build_users_tab",
]