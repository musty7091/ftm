from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
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

from app.db.session import session_scope
from app.models.enums import UserRole
from app.models.role_permission import RolePermission
from app.services.audit_service import write_audit_log
from app.services.permission_service import Permission, get_permissions_for_role_from_db


ROLES_TAB_STYLE = """
QFrame#RolesTabCard {
    background-color: #111827;
    border: 1px solid #24324a;
    border-radius: 18px;
}

QFrame#RolesTabInfoBox {
    background-color: rgba(15, 23, 42, 0.64);
    border: 1px solid rgba(148, 163, 184, 0.22);
    border-radius: 14px;
}

QFrame#RolesTabEditorBox {
    background-color: rgba(15, 23, 42, 0.48);
    border: 1px solid rgba(59, 130, 246, 0.28);
    border-radius: 14px;
}

QLabel#RolesTabTitle {
    color: #f8fafc;
    font-size: 16px;
    font-weight: 900;
}

QLabel#RolesTabSubtitle {
    color: #94a3b8;
    font-size: 12px;
}

QLabel#RolesTabSectionTitle {
    color: #f8fafc;
    font-size: 14px;
    font-weight: 900;
}

QLabel#RolesTabFieldLabel {
    color: #bfdbfe;
    font-size: 12px;
    font-weight: 800;
}

QLabel#RolesTabBadge {
    color: #dbeafe;
    font-size: 11px;
    font-weight: 800;
    background-color: rgba(30, 64, 175, 0.32);
    border: 1px solid rgba(59, 130, 246, 0.42);
    border-radius: 8px;
    padding: 5px 9px;
}

QLabel#RolesTabSuccessBadge {
    color: #d1fae5;
    font-size: 11px;
    font-weight: 800;
    background-color: rgba(6, 78, 59, 0.34);
    border: 1px solid rgba(16, 185, 129, 0.42);
    border-radius: 8px;
    padding: 5px 9px;
}

QLabel#RolesTabWarningBadge {
    color: #fde68a;
    font-size: 11px;
    font-weight: 800;
    background-color: rgba(120, 53, 15, 0.36);
    border: 1px solid rgba(245, 158, 11, 0.48);
    border-radius: 8px;
    padding: 5px 9px;
}

QComboBox {
    background-color: #0f172a;
    color: #f8fafc;
    border: 1px solid #334155;
    border-radius: 10px;
    padding: 8px 10px;
    font-size: 12px;
    min-width: 170px;
}

QComboBox:hover {
    border: 1px solid #475569;
}

QComboBox:focus {
    border: 1px solid #3b82f6;
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

QPushButton#RolesTabRefreshButton {
    background-color: #2563eb;
    color: #ffffff;
    border: 1px solid #3b82f6;
    border-radius: 11px;
    padding: 8px 14px;
    font-weight: 900;
}

QPushButton#RolesTabRefreshButton:hover {
    background-color: #1d4ed8;
}

QPushButton#RolesTabSaveButton {
    background-color: #047857;
    color: #ffffff;
    border: 1px solid #10b981;
    border-radius: 11px;
    padding: 8px 14px;
    font-weight: 900;
}

QPushButton#RolesTabSaveButton:hover {
    background-color: #059669;
}

QPushButton#RolesTabSaveButton:disabled {
    background-color: rgba(30, 41, 59, 0.55);
    color: #64748b;
    border: 1px solid rgba(100, 116, 139, 0.32);
}

QPushButton#RolesTabPassiveButton {
    background-color: #1f2937;
    color: #94a3b8;
    border: 1px solid #334155;
    border-radius: 10px;
    padding: 8px 12px;
    font-weight: 800;
}

QPushButton#RolesTabPassiveButton:disabled {
    background-color: rgba(30, 41, 59, 0.55);
    color: #64748b;
    border: 1px solid rgba(100, 116, 139, 0.32);
}

QTableWidget#RolesEditorTable {
    background-color: #0f172a;
    color: #e5e7eb;
    border: 1px solid #334155;
    border-radius: 12px;
    gridline-color: #334155;
    selection-background-color: #2563eb;
    selection-color: #ffffff;
    alternate-background-color: #111827;
}

QTableWidget#RolesEditorTable::item {
    padding: 6px;
    border: none;
}

/* Checkbox görünürlüğü düzeltildi */
QTableWidget#RolesEditorTable::indicator {
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 1px solid #94a3b8;
    background-color: #0b1220;
    margin: 2px;
}

QTableWidget#RolesEditorTable::indicator:unchecked {
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 1px solid #cbd5e1;
    background-color: #0b1220;
}

QTableWidget#RolesEditorTable::indicator:checked {
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 1px solid #93c5fd;
    background-color: #2563eb;
}

QTableWidget#RolesEditorTable::indicator:disabled {
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 1px solid #64748b;
    background-color: #1e293b;
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


ROLE_CHOICES = [
    UserRole.FINANCE,
    UserRole.DATA_ENTRY,
    UserRole.VIEWER,
    UserRole.ADMIN,
]


PERMISSION_GROUPS: list[tuple[str, list[Permission]]] = [
    (
        "Kullanıcı Yönetimi",
        [
            Permission.USER_VIEW,
            Permission.USER_CREATE,
            Permission.USER_UPDATE_ROLE,
            Permission.USER_DEACTIVATE,
            Permission.USER_REACTIVATE,
        ],
    ),
    (
        "Banka / Hesap",
        [
            Permission.BANK_CREATE,
            Permission.BANK_UPDATE,
            Permission.BANK_ACCOUNT_CREATE,
            Permission.BANK_ACCOUNT_UPDATE,
            Permission.BANK_ACCOUNT_DEACTIVATE,
            Permission.BANK_ACCOUNT_REACTIVATE,
        ],
    ),
    (
        "Banka Hareketleri / Transfer",
        [
            Permission.BANK_TRANSACTION_VIEW,
            Permission.BANK_TRANSACTION_CREATE,
            Permission.BANK_TRANSACTION_CANCEL,
            Permission.BANK_TRANSFER_VIEW,
            Permission.BANK_TRANSFER_CREATE,
            Permission.BANK_TRANSFER_REALIZE,
            Permission.BANK_TRANSFER_CANCEL,
        ],
    ),
    (
        "POS",
        [
            Permission.POS_DEVICE_CREATE,
            Permission.POS_DEVICE_UPDATE,
            Permission.POS_DEVICE_DEACTIVATE,
            Permission.POS_DEVICE_REACTIVATE,
            Permission.POS_SETTLEMENT_VIEW,
            Permission.POS_SETTLEMENT_CREATE,
            Permission.POS_SETTLEMENT_REALIZE,
            Permission.POS_SETTLEMENT_CANCEL,
        ],
    ),
    (
        "Cari Kartlar",
        [
            Permission.BUSINESS_PARTNER_VIEW,
            Permission.BUSINESS_PARTNER_CREATE,
        ],
    ),
    (
        "Çek Yönetimi",
        [
            Permission.ISSUED_CHECK_VIEW,
            Permission.ISSUED_CHECK_CREATE,
            Permission.ISSUED_CHECK_PAY,
            Permission.ISSUED_CHECK_CANCEL,
            Permission.RECEIVED_CHECK_VIEW,
            Permission.RECEIVED_CHECK_CREATE,
            Permission.RECEIVED_CHECK_SEND_TO_BANK,
            Permission.RECEIVED_CHECK_COLLECT,
            Permission.RECEIVED_CHECK_ENDORSE,
            Permission.RECEIVED_CHECK_DISCOUNT,
            Permission.RECEIVED_CHECK_CANCEL,
        ],
    ),
    (
        "Raporlar",
        [
            Permission.REPORT_VIEW_ALL,
            Permission.REPORT_EXPORT_ALL,
            Permission.REPORT_VIEW_LIMITED,
            Permission.REPORT_EXPORT_LIMITED,
        ],
    ),
    (
        "Güvenlik / Sistem",
        [
            Permission.AUDIT_LOG_VIEW,
            Permission.BACKUP_RUN,
            Permission.RESTORE_TEST_RUN,
            Permission.SYSTEM_SETTINGS_VIEW,
            Permission.SYSTEM_SETTINGS_UPDATE,
        ],
    ),
]


PERMISSION_LABELS = {
    Permission.USER_VIEW: "Kullanıcıları görüntüle",
    Permission.USER_CREATE: "Kullanıcı oluştur",
    Permission.USER_UPDATE_ROLE: "Kullanıcı rolünü değiştir",
    Permission.USER_DEACTIVATE: "Kullanıcı pasif yap",
    Permission.USER_REACTIVATE: "Kullanıcı aktif yap",
    Permission.BANK_CREATE: "Banka oluştur",
    Permission.BANK_UPDATE: "Banka düzenle",
    Permission.BANK_ACCOUNT_CREATE: "Banka hesabı oluştur",
    Permission.BANK_ACCOUNT_UPDATE: "Banka hesabı düzenle",
    Permission.BANK_ACCOUNT_DEACTIVATE: "Banka hesabı pasif yap",
    Permission.BANK_ACCOUNT_REACTIVATE: "Banka hesabı aktif yap",
    Permission.BANK_TRANSACTION_VIEW: "Banka hareketi görüntüle",
    Permission.BANK_TRANSACTION_CREATE: "Banka hareketi oluştur",
    Permission.BANK_TRANSACTION_CANCEL: "Banka hareketi iptal et",
    Permission.BANK_TRANSFER_VIEW: "Transfer görüntüle",
    Permission.BANK_TRANSFER_CREATE: "Transfer oluştur",
    Permission.BANK_TRANSFER_REALIZE: "Transfer gerçekleştir",
    Permission.BANK_TRANSFER_CANCEL: "Transfer iptal et",
    Permission.POS_DEVICE_CREATE: "POS cihazı oluştur",
    Permission.POS_DEVICE_UPDATE: "POS cihazı düzenle",
    Permission.POS_DEVICE_DEACTIVATE: "POS cihazı pasif yap",
    Permission.POS_DEVICE_REACTIVATE: "POS cihazı aktif yap",
    Permission.POS_SETTLEMENT_VIEW: "POS mutabakat görüntüle",
    Permission.POS_SETTLEMENT_CREATE: "POS mutabakat oluştur",
    Permission.POS_SETTLEMENT_REALIZE: "POS mutabakat gerçekleştir",
    Permission.POS_SETTLEMENT_CANCEL: "POS mutabakat iptal et",
    Permission.BUSINESS_PARTNER_VIEW: "Cari kart görüntüle",
    Permission.BUSINESS_PARTNER_CREATE: "Cari kart oluştur",
    Permission.ISSUED_CHECK_VIEW: "Yazılan çek görüntüle",
    Permission.ISSUED_CHECK_CREATE: "Yazılan çek oluştur",
    Permission.ISSUED_CHECK_PAY: "Yazılan çek öde",
    Permission.ISSUED_CHECK_CANCEL: "Yazılan çek iptal et",
    Permission.RECEIVED_CHECK_VIEW: "Alınan çek görüntüle",
    Permission.RECEIVED_CHECK_CREATE: "Alınan çek oluştur",
    Permission.RECEIVED_CHECK_SEND_TO_BANK: "Alınan çeki bankaya gönder",
    Permission.RECEIVED_CHECK_COLLECT: "Alınan çeki tahsil et",
    Permission.RECEIVED_CHECK_ENDORSE: "Alınan çeki ciro et",
    Permission.RECEIVED_CHECK_DISCOUNT: "Alınan çeki iskonto et",
    Permission.RECEIVED_CHECK_CANCEL: "Alınan çek iptal et",
    Permission.REPORT_VIEW_ALL: "Tüm raporları görüntüle",
    Permission.REPORT_EXPORT_ALL: "Tüm raporları dışa aktar",
    Permission.REPORT_VIEW_LIMITED: "Sınırlı rapor görüntüle",
    Permission.REPORT_EXPORT_LIMITED: "Sınırlı rapor dışa aktar",
    Permission.AUDIT_LOG_VIEW: "İşlem kayıtlarını görüntüle",
    Permission.BACKUP_RUN: "Yedekleme çalıştır",
    Permission.RESTORE_TEST_RUN: "Geri yükleme testi çalıştır",
    Permission.SYSTEM_SETTINGS_VIEW: "Sistem ayarlarını görüntüle",
    Permission.SYSTEM_SETTINGS_UPDATE: "Sistem ayarlarını güncelle",
}


CRITICAL_PERMISSIONS = {
    Permission.USER_VIEW,
    Permission.USER_CREATE,
    Permission.USER_UPDATE_ROLE,
    Permission.USER_DEACTIVATE,
    Permission.USER_REACTIVATE,
    Permission.AUDIT_LOG_VIEW,
    Permission.BACKUP_RUN,
    Permission.RESTORE_TEST_RUN,
    Permission.SYSTEM_SETTINGS_UPDATE,
}


ADMIN_ONLY_PERMISSIONS = {
    Permission.USER_VIEW,
    Permission.USER_CREATE,
    Permission.USER_UPDATE_ROLE,
    Permission.USER_DEACTIVATE,
    Permission.USER_REACTIVATE,
    Permission.AUDIT_LOG_VIEW,
    Permission.BACKUP_RUN,
    Permission.RESTORE_TEST_RUN,
    Permission.SYSTEM_SETTINGS_VIEW,
    Permission.SYSTEM_SETTINGS_UPDATE,
}


class RolesTab(QWidget):
    def __init__(self) -> None:
        super().__init__()

        self.setStyleSheet(ROLES_TAB_STYLE)

        self._is_loading_editor = False
        self.permission_state: dict[str, bool] = {}

        self.source_label = QLabel("Kaynak: Veritabanı")
        self.source_label.setObjectName("RolesTabBadge")

        self.allowed_count_label = QLabel("Açık yetki: 0")
        self.allowed_count_label.setObjectName("RolesTabSuccessBadge")

        self.critical_count_label = QLabel("Kritik yetki: 0")
        self.critical_count_label.setObjectName("RolesTabWarningBadge")

        self.role_combo = QComboBox()
        for role in ROLE_CHOICES:
            if role == UserRole.ADMIN:
                self.role_combo.addItem("ADMIN - korumalı", role.value)
            else:
                self.role_combo.addItem(role.value, role.value)
        self.role_combo.currentIndexChanged.connect(self.load_selected_role_permissions)

        self.group_filter_combo = QComboBox()
        self.group_filter_combo.addItem("Tüm yetki grupları", "ALL")
        for group_name, _permissions in PERMISSION_GROUPS:
            self.group_filter_combo.addItem(group_name, group_name)
        self.group_filter_combo.currentIndexChanged.connect(self.render_editor_table)

        self.save_role_button = QPushButton("Yetkileri Kaydet")
        self.save_role_button.setObjectName("RolesTabSaveButton")
        self.save_role_button.clicked.connect(self.save_selected_role_permissions)

        self.refresh_button = QPushButton("Yenile")
        self.refresh_button.setObjectName("RolesTabRefreshButton")
        self.refresh_button.clicked.connect(self.load_selected_role_permissions)

        self.role_status_label = QLabel("")
        self.role_status_label.setObjectName("RolesTabSubtitle")
        self.role_status_label.setWordWrap(True)

        self.editor_table = QTableWidget()
        self.editor_table.setObjectName("RolesEditorTable")
        self.editor_table.setColumnCount(4)
        self.editor_table.setHorizontalHeaderLabels(
            [
                "Grup",
                "Yetki",
                "Kritik",
                "Açık mı?",
            ]
        )
        self.editor_table.setAlternatingRowColors(True)
        self.editor_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.editor_table.setSelectionMode(QTableWidget.SingleSelection)
        self.editor_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.editor_table.verticalHeader().setVisible(False)
        self.editor_table.itemChanged.connect(self._on_editor_item_changed)

        editor_header = self.editor_table.horizontalHeader()
        editor_header.setStretchLastSection(False)
        editor_header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        editor_header.setSectionResizeMode(1, QHeaderView.Stretch)
        editor_header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        editor_header.setSectionResizeMode(3, QHeaderView.Fixed)

        self.editor_table.setColumnWidth(2, 90)
        self.editor_table.setColumnWidth(3, 80)

        self._build_ui()
        self.load_selected_role_permissions()

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 14, 12, 12)
        main_layout.setSpacing(12)

        card = QFrame()
        card.setObjectName("RolesTabCard")

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 16, 18, 16)
        card_layout.setSpacing(14)

        title = QLabel("Roller ve Yetkiler")
        title.setObjectName("RolesTabTitle")

        subtitle = QLabel(
            "Rol seç, yetkileri işaretle, kaydet. "
            "ADMIN rolü sistem güvenliği için korumalıdır. "
            "Kullanıcı yönetimi, audit log, yedekleme ve sistem ayarları yalnızca ADMIN tarafından kullanılabilir."
        )
        subtitle.setObjectName("RolesTabSubtitle")
        subtitle.setWordWrap(True)

        card_layout.addWidget(title)
        card_layout.addWidget(subtitle)
        card_layout.addWidget(self._build_summary_bar())
        card_layout.addWidget(self._build_editor_bar())
        card_layout.addWidget(self.role_status_label)
        card_layout.addWidget(self.editor_table, 1)

        info_button = QPushButton(
            "Güvenlik ve Sistem modülü sadece ADMIN kullanıcıya açıktır. "
            "Non-admin rollerde bu alana ait yetkiler kilitli tutulur."
        )
        info_button.setObjectName("RolesTabPassiveButton")
        info_button.setEnabled(False)

        card_layout.addWidget(info_button, 0, Qt.AlignRight)

        main_layout.addWidget(card, 1)

    def _build_summary_bar(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("RolesTabInfoBox")

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        info = QLabel(
            "Yetkiler role_permissions tablosundan okunur ve kaydedilir. "
            "ADMIN'e özel güvenlik yetkileri non-admin rollere verilemez."
        )
        info.setObjectName("RolesTabSubtitle")
        info.setWordWrap(True)

        layout.addWidget(info, 1)
        layout.addWidget(self.source_label, 0, Qt.AlignVCenter)
        layout.addWidget(self.allowed_count_label, 0, Qt.AlignVCenter)
        layout.addWidget(self.critical_count_label, 0, Qt.AlignVCenter)

        return bar

    def _build_editor_bar(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("RolesTabEditorBox")

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        role_label = QLabel("Rol")
        role_label.setObjectName("RolesTabFieldLabel")

        filter_label = QLabel("Grup")
        filter_label.setObjectName("RolesTabFieldLabel")

        layout.addWidget(role_label, 0, Qt.AlignVCenter)
        layout.addWidget(self.role_combo, 0, Qt.AlignVCenter)
        layout.addSpacing(12)
        layout.addWidget(filter_label, 0, Qt.AlignVCenter)
        layout.addWidget(self.group_filter_combo, 0, Qt.AlignVCenter)
        layout.addStretch(1)
        layout.addWidget(self.refresh_button, 0, Qt.AlignVCenter)
        layout.addWidget(self.save_role_button, 0, Qt.AlignVCenter)

        return bar

    def load_selected_role_permissions(self) -> None:
        try:
            selected_role = self._selected_role()

            with session_scope() as session:
                selected_permissions = get_permissions_for_role_from_db(
                    session,
                    selected_role,
                    fallback_to_code_defaults=True,
                )

            self.permission_state = {
                permission.value: permission in selected_permissions
                for permission in Permission
            }

            self.permission_state = self._permission_state_for_role(
                role=selected_role,
                permission_state=self.permission_state,
            )

            self.render_editor_table()
            self._update_role_status()
            self._update_summary_labels()

        except Exception as exc:
            QMessageBox.critical(
                self,
                "Rol Yetkileri Yüklenemedi",
                f"Seçili rol yetkileri yüklenirken hata oluştu:\n\n{exc}",
            )

    def render_editor_table(self) -> None:
        self._is_loading_editor = True
        self.editor_table.setRowCount(0)

        try:
            selected_role = self._selected_role()
            is_admin_role = selected_role == UserRole.ADMIN
            selected_group = self._selected_group_filter()

            row_index = 0

            for group_name, permissions in PERMISSION_GROUPS:
                if selected_group != "ALL" and selected_group != group_name:
                    continue

                for permission in permissions:
                    is_admin_only_permission = self._is_admin_only_permission(permission)

                    self.editor_table.insertRow(row_index)

                    group_item = QTableWidgetItem(group_name)
                    group_item.setFlags(group_item.flags() & ~Qt.ItemIsEditable)

                    permission_item = QTableWidgetItem(self._permission_label(permission))
                    permission_item.setFlags(permission_item.flags() & ~Qt.ItemIsEditable)

                    critical_item = QTableWidgetItem(
                        self._critical_text(permission)
                    )
                    critical_item.setTextAlignment(Qt.AlignCenter)
                    critical_item.setFlags(critical_item.flags() & ~Qt.ItemIsEditable)

                    allowed_item = QTableWidgetItem("")
                    allowed_item.setTextAlignment(Qt.AlignCenter)
                    allowed_item.setData(Qt.UserRole, permission.value)

                    if is_admin_role:
                        allowed_item.setCheckState(Qt.Checked)
                    elif is_admin_only_permission:
                        allowed_item.setCheckState(Qt.Unchecked)
                    else:
                        allowed_item.setCheckState(
                            Qt.Checked
                            if self.permission_state.get(permission.value, False)
                            else Qt.Unchecked
                        )

                    if is_admin_role:
                        allowed_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                        allowed_item.setToolTip("ADMIN rolü korumalıdır ve tüm yetkilere sahiptir.")
                    elif is_admin_only_permission:
                        allowed_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                        allowed_item.setToolTip(
                            "Bu yetki Güvenlik ve Sistem modülüne aittir. "
                            "Sadece ADMIN kullanıcı tarafından kullanılabilir."
                        )
                    else:
                        allowed_item.setFlags(
                            Qt.ItemIsEnabled
                            | Qt.ItemIsSelectable
                            | Qt.ItemIsUserCheckable
                        )

                    self.editor_table.setItem(row_index, 0, group_item)
                    self.editor_table.setItem(row_index, 1, permission_item)
                    self.editor_table.setItem(row_index, 2, critical_item)
                    self.editor_table.setItem(row_index, 3, allowed_item)

                    row_index += 1

            self.editor_table.resizeRowsToContents()

        finally:
            self._is_loading_editor = False

    def _on_editor_item_changed(self, item: QTableWidgetItem) -> None:
        if self._is_loading_editor:
            return

        if item.column() != 3:
            return

        permission_value = item.data(Qt.UserRole)

        if not permission_value:
            return

        permission_text = str(permission_value)

        try:
            permission = Permission(permission_text)
        except ValueError:
            return

        selected_role = self._selected_role()

        if selected_role != UserRole.ADMIN and self._is_admin_only_permission(permission):
            self.permission_state[permission_text] = False
            item.setCheckState(Qt.Unchecked)
            return

        self.permission_state[permission_text] = item.checkState() == Qt.Checked
        self._update_summary_labels()

    def save_selected_role_permissions(self) -> None:
        selected_role = self._selected_role()

        if selected_role == UserRole.ADMIN:
            QMessageBox.warning(
                self,
                "ADMIN Rolü Korumalı",
                "ADMIN rolü bu ekrandan değiştirilemez.",
            )
            return

        selected_permission_values = self._selected_permission_values()
        selected_permission_values = self._sanitize_permission_values_for_role(
            role=selected_role,
            selected_permission_values=selected_permission_values,
        )

        validation_error = self._validate_role_permissions_before_save(
            role=selected_role,
            selected_permission_values=selected_permission_values,
        )

        if validation_error:
            QMessageBox.warning(
                self,
                "Yetkiler Kaydedilemedi",
                validation_error,
            )
            return

        if self._has_critical_permissions(selected_permission_values):
            answer = QMessageBox.question(
                self,
                "Kritik Yetki Onayı",
                "Seçili role kritik yetkiler veriliyor.\n\n"
                "Kritik yetkiler finansal işlem, rapor veya iptal gibi önemli alanlara erişim sağlayabilir.\n\n"
                "Devam etmek istiyor musun?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )

            if answer != QMessageBox.Yes:
                return

        answer = QMessageBox.question(
            self,
            "Yetkiler Kaydedilsin mi?",
            f"{selected_role.value} rolünün yetkilerini kaydetmek istiyor musun?\n\n"
            "Not: Güvenlik ve Sistem modülüne ait yetkiler ADMIN dışındaki roller için kapalı tutulur.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if answer != QMessageBox.Yes:
            return

        try:
            result = self._save_role_permissions_to_db(
                role=selected_role,
                selected_permission_values=selected_permission_values,
            )

            if result["changed"] == 0:
                QMessageBox.information(
                    self,
                    "Değişiklik Yok",
                    f"{selected_role.value} rolünde kaydedilecek yeni bir değişiklik yok.",
                )
            else:
                QMessageBox.information(
                    self,
                    "Yetkiler Kaydedildi",
                    f"{selected_role.value} rolünün yetkileri güncellendi.\n\n"
                    f"Güncellenen kayıt: {result['updated_count']}\n"
                    f"Değişmeyen kayıt: {result['unchanged_count']}\n"
                    f"Açık yetki sayısı: {result['allowed_count']}",
                )

            self.load_selected_role_permissions()

        except Exception as exc:
            QMessageBox.critical(
                self,
                "Yetkiler Kaydedilemedi",
                f"Rol yetkileri kaydedilirken hata oluştu:\n\n{exc}",
            )

    def _save_role_permissions_to_db(
        self,
        *,
        role: UserRole,
        selected_permission_values: set[str],
    ) -> dict[str, int]:
        updated_count = 0
        unchanged_count = 0

        selected_permission_values = self._sanitize_permission_values_for_role(
            role=role,
            selected_permission_values=selected_permission_values,
        )

        with session_scope() as session:
            existing_statement = select(RolePermission).where(
                RolePermission.role == role,
            )
            existing_rows = session.execute(existing_statement).scalars().all()

            existing_by_permission = {
                str(row.permission): row
                for row in existing_rows
            }

            old_values = {
                "role": role.value,
                "allowed_permissions": sorted(
                    str(row.permission)
                    for row in existing_rows
                    if bool(row.is_allowed)
                ),
            }

            for permission in Permission:
                expected_allowed = permission.value in selected_permission_values
                existing_row = existing_by_permission.get(permission.value)

                if existing_row is None:
                    existing_row = RolePermission(
                        role=role,
                        permission=permission.value,
                        is_allowed=expected_allowed,
                    )
                    session.add(existing_row)
                    updated_count += 1
                    continue

                if bool(existing_row.is_allowed) != expected_allowed:
                    existing_row.is_allowed = expected_allowed
                    updated_count += 1
                    continue

                unchanged_count += 1

            session.flush()

            new_values = {
                "role": role.value,
                "allowed_permissions": sorted(selected_permission_values),
            }

            changed = 1 if old_values != new_values else 0

            if changed:
                write_audit_log(
                    session,
                    user_id=self._current_user_id(),
                    action="ROLE_PERMISSIONS_UPDATED",
                    entity_type="RolePermission",
                    entity_id=None,
                    description=f"Rol yetkileri güncellendi: {role.value}",
                    old_values=old_values,
                    new_values=new_values,
                )

        return {
            "changed": changed,
            "updated_count": updated_count,
            "unchanged_count": unchanged_count,
            "allowed_count": len(selected_permission_values),
        }

    def _selected_permission_values(self) -> set[str]:
        selected_role = self._selected_role()

        selected_values = {
            permission_value
            for permission_value, is_allowed in self.permission_state.items()
            if is_allowed
        }

        return self._sanitize_permission_values_for_role(
            role=selected_role,
            selected_permission_values=selected_values,
        )

    def _validate_role_permissions_before_save(
        self,
        *,
        role: UserRole,
        selected_permission_values: set[str],
    ) -> str | None:
        if role == UserRole.ADMIN:
            return "ADMIN rolü bu ekrandan değiştirilemez."

        if not selected_permission_values:
            return "Bir role ait tüm yetkileri kapatmak güvenli değildir. En az bir yetki seçili olmalıdır."

        return None

    def _has_critical_permissions(self, selected_permission_values: set[str]) -> bool:
        critical_values = {
            permission.value
            for permission in CRITICAL_PERMISSIONS
            if permission not in ADMIN_ONLY_PERMISSIONS
        }

        return bool(selected_permission_values.intersection(critical_values))

    def _update_role_status(self) -> None:
        selected_role = self._selected_role()

        if selected_role == UserRole.ADMIN:
            self.save_role_button.setEnabled(False)
            self.role_status_label.setText(
                "ADMIN rolü korumalıdır. Tüm yetkilere sahip kalır ve bu ekrandan değiştirilemez."
            )
            return

        self.save_role_button.setEnabled(True)
        self.role_status_label.setText(
            f"{selected_role.value} rolü düzenlenebilir. "
            "Ancak Kullanıcı Yönetimi ve Güvenlik / Sistem yetkileri yalnızca ADMIN içindir; "
            "bu rol için kilitli ve kapalı tutulur."
        )

    def _update_summary_labels(self) -> None:
        allowed_count = len(self._selected_permission_values())
        total_count = len(list(Permission))

        critical_values = {
            permission.value
            for permission in CRITICAL_PERMISSIONS
            if permission not in ADMIN_ONLY_PERMISSIONS
        }
        critical_count = len(self._selected_permission_values().intersection(critical_values))

        self.allowed_count_label.setText(f"Açık yetki: {allowed_count}/{total_count}")
        self.critical_count_label.setText(f"Kritik yetki: {critical_count}")

    def _selected_role(self) -> UserRole:
        role_value = str(self.role_combo.currentData() or UserRole.VIEWER.value)

        return UserRole(role_value)

    def _selected_group_filter(self) -> str:
        return str(self.group_filter_combo.currentData() or "ALL")

    def _permission_label(self, permission: Permission) -> str:
        label = PERMISSION_LABELS.get(permission, permission.value)

        if self._is_admin_only_permission(permission):
            return f"{label} (Sadece ADMIN)"

        return label

    def _critical_text(self, permission: Permission) -> str:
        if self._is_admin_only_permission(permission):
            return "ADMIN"

        if permission in CRITICAL_PERMISSIONS:
            return "Evet"

        return "-"

    def _is_admin_only_permission(self, permission: Permission) -> bool:
        return permission in ADMIN_ONLY_PERMISSIONS

    def _permission_state_for_role(
        self,
        *,
        role: UserRole,
        permission_state: dict[str, bool],
    ) -> dict[str, bool]:
        normalized_state = dict(permission_state)

        if role == UserRole.ADMIN:
            for permission in Permission:
                normalized_state[permission.value] = True

            return normalized_state

        for permission in ADMIN_ONLY_PERMISSIONS:
            normalized_state[permission.value] = False

        return normalized_state

    def _sanitize_permission_values_for_role(
        self,
        *,
        role: UserRole,
        selected_permission_values: set[str],
    ) -> set[str]:
        if role == UserRole.ADMIN:
            return set(permission.value for permission in Permission)

        admin_only_values = {
            permission.value
            for permission in ADMIN_ONLY_PERMISSIONS
        }

        return {
            permission_value
            for permission_value in selected_permission_values
            if permission_value not in admin_only_values
        }

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


def build_roles_tab() -> QWidget:
    return RolesTab()


__all__ = [
    "RolesTab",
    "build_roles_tab",
]