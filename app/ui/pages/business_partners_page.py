from dataclasses import dataclass
from datetime import datetime
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
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
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.db.session import session_scope
from app.models.business_partner import BusinessPartner
from app.models.enums import BusinessPartnerType
from app.services.audit_service import write_audit_log


@dataclass(frozen=True)
class BusinessPartnerRow:
    id: int
    name: str
    partner_type: str
    tax_office: str | None
    tax_number: str | None
    authorized_person: str | None
    phone: str | None
    email: str | None
    address: str | None
    notes: str | None
    is_active: bool
    created_at: datetime | None
    updated_at: datetime | None


PARTNER_TYPE_TEXTS = {
    "CUSTOMER": "Müşteri",
    "SUPPLIER": "Tedarikçi",
    "BOTH": "Müşteri & Tedarikçi",
    "OTHER": "Diğer",
}


PAGE_STYLE = """
QLineEdit,
QTextEdit,
QComboBox {
    background-color: #0f172a;
    color: #f8fafc;
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 8px 10px;
}

QLineEdit:focus,
QTextEdit:focus,
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

QComboBox QAbstractItemView::item {
    min-height: 28px;
    padding: 8px;
    color: #e5e7eb;
    background-color: #111827;
}

QComboBox QAbstractItemView::item:selected {
    background-color: #2563eb;
    color: #ffffff;
}

QCheckBox {
    color: #cbd5e1;
    spacing: 8px;
}

QPushButton#ActionPrimaryButton {
    background-color: #2563eb;
    color: white;
    border: 1px solid #3b82f6;
    border-radius: 12px;
    padding: 9px 14px;
    text-align: center;
    font-weight: 700;
}

QPushButton#ActionPrimaryButton:hover {
    background-color: #1d4ed8;
}

QPushButton#ActionDangerButton {
    background-color: #7f1d1d;
    color: #fee2e2;
    border: 1px solid #ef4444;
    border-radius: 12px;
    padding: 9px 14px;
    text-align: center;
    font-weight: 700;
}

QPushButton#ActionDangerButton:hover {
    background-color: #991b1b;
}

QPushButton#ActionSuccessButton {
    background-color: #064e3b;
    color: #d1fae5;
    border: 1px solid #10b981;
    border-radius: 12px;
    padding: 9px 14px;
    text-align: center;
    font-weight: 700;
}

QPushButton#ActionSuccessButton:hover {
    background-color: #065f46;
}

QPushButton#ActionSecondaryButton {
    background-color: #1f2937;
    color: #cbd5e1;
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 9px 14px;
    text-align: center;
    font-weight: 700;
}

QPushButton#ActionSecondaryButton:hover {
    background-color: #334155;
    color: #ffffff;
}
"""


def _enum_value(value: Any) -> str:
    if value is None:
        return ""

    if hasattr(value, "value"):
        return str(value.value).strip().upper()

    return str(value).strip().upper()


def business_partner_type_text(value: Any) -> str:
    value_text = _enum_value(value)

    return PARTNER_TYPE_TEXTS.get(value_text, value_text or "-")


def _format_optional_text(value: str | None) -> str:
    cleaned_value = str(value or "").strip()

    if not cleaned_value:
        return "-"

    return cleaned_value


def _clean_optional_text(value: str | None) -> str | None:
    cleaned_value = str(value or "").strip()

    if not cleaned_value:
        return None

    return cleaned_value


def _format_datetime(value: datetime | None) -> str:
    if value is None:
        return "-"

    return value.strftime("%d.%m.%Y %H:%M")


def _current_role_text(current_user: Any | None) -> str:
    if current_user is None:
        return "VIEWER"

    role = getattr(current_user, "role", None)

    if role is None:
        return "VIEWER"

    if hasattr(role, "value"):
        return str(role.value).strip().upper()

    return str(role).strip().upper()


def _current_user_id(current_user: Any | None) -> int | None:
    if current_user is None:
        return None

    user_id = getattr(current_user, "id", None)

    if user_id is None:
        return None

    try:
        return int(user_id)
    except (TypeError, ValueError):
        return None


def _business_partner_to_dict(partner: BusinessPartner) -> dict[str, Any]:
    return {
        "id": partner.id,
        "name": partner.name,
        "partner_type": partner.partner_type.value if hasattr(partner.partner_type, "value") else str(partner.partner_type),
        "tax_office": partner.tax_office,
        "tax_number": partner.tax_number,
        "authorized_person": partner.authorized_person,
        "phone": partner.phone,
        "email": partner.email,
        "address": partner.address,
        "notes": partner.notes,
        "is_active": bool(partner.is_active),
        "created_at": partner.created_at.isoformat() if partner.created_at else None,
        "updated_at": partner.updated_at.isoformat() if partner.updated_at else None,
    }


class BusinessPartnerDialog(QDialog):
    def __init__(
        self,
        *,
        parent: QWidget | None,
        partner_row: BusinessPartnerRow | None = None,
    ) -> None:
        super().__init__(parent)

        self.partner_row = partner_row
        self.payload: dict[str, Any] | None = None

        if self.partner_row is None:
            self.setWindowTitle("Yeni Müşteri / Tedarikçi Kartı")
        else:
            self.setWindowTitle("Müşteri / Tedarikçi Kartı Düzenle")

        self.setMinimumSize(720, 620)
        self.resize(780, 680)
        self.setModal(True)
        self.setStyleSheet(
            PAGE_STYLE
            + """
            QDialog {
                background-color: #0f172a;
            }

            QFrame#DialogCard {
                background-color: #111827;
                border: 1px solid #1f2937;
                border-radius: 18px;
            }

            QLabel#DialogTitle {
                color: #f8fafc;
                font-size: 20px;
                font-weight: 800;
            }

            QLabel#DialogSubtitle {
                color: #94a3b8;
                font-size: 12px;
            }

            QLabel#DialogLabel {
                color: #cbd5e1;
                font-weight: 700;
            }
            """
        )

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(22, 22, 22, 22)
        root_layout.setSpacing(0)

        card = QFrame()
        card.setObjectName("DialogCard")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(12)

        title = QLabel(
            "Yeni Kart"
            if self.partner_row is None
            else f"Kart Düzenle: {self.partner_row.name}"
        )
        title.setObjectName("DialogTitle")

        subtitle = QLabel(
            "Bu kartlar çeklerde taraf seçimi için kullanılır. Cari borç/alacak bakiyesi tutulmaz."
        )
        subtitle.setObjectName("DialogSubtitle")
        subtitle.setWordWrap(True)

        form_layout = QGridLayout()
        form_layout.setHorizontalSpacing(12)
        form_layout.setVerticalSpacing(10)
        form_layout.setColumnStretch(0, 1)
        form_layout.setColumnStretch(1, 1)

        self.name_input = QLineEdit()
        self.name_input.setMinimumHeight(38)
        self.name_input.setPlaceholderText("Firma / kişi adı")

        self.partner_type_combo = QComboBox()
        self.partner_type_combo.setMinimumHeight(38)
        self.partner_type_combo.addItem("Müşteri", BusinessPartnerType.CUSTOMER.value)
        self.partner_type_combo.addItem("Tedarikçi", BusinessPartnerType.SUPPLIER.value)
        self.partner_type_combo.addItem("Müşteri & Tedarikçi", BusinessPartnerType.BOTH.value)
        self.partner_type_combo.addItem("Diğer", BusinessPartnerType.OTHER.value)

        self.tax_number_input = QLineEdit()
        self.tax_number_input.setMinimumHeight(38)
        self.tax_number_input.setPlaceholderText("Vergi no / kimlik no")

        self.tax_office_input = QLineEdit()
        self.tax_office_input.setMinimumHeight(38)
        self.tax_office_input.setPlaceholderText("Vergi dairesi")

        self.authorized_person_input = QLineEdit()
        self.authorized_person_input.setMinimumHeight(38)
        self.authorized_person_input.setPlaceholderText("Yetkili kişi")

        self.phone_input = QLineEdit()
        self.phone_input.setMinimumHeight(38)
        self.phone_input.setPlaceholderText("Telefon")

        self.email_input = QLineEdit()
        self.email_input.setMinimumHeight(38)
        self.email_input.setPlaceholderText("E-posta")

        self.is_active_checkbox = QCheckBox("Aktif kart")
        self.is_active_checkbox.setChecked(True)

        self.address_input = QTextEdit()
        self.address_input.setPlaceholderText("Adres")
        self.address_input.setFixedHeight(78)

        self.notes_input = QTextEdit()
        self.notes_input.setPlaceholderText("Not / açıklama / risk notu")
        self.notes_input.setFixedHeight(90)

        form_layout.addWidget(self._label("Ad / Ünvan"), 0, 0)
        form_layout.addWidget(self._label("Tip"), 0, 1)
        form_layout.addWidget(self.name_input, 1, 0)
        form_layout.addWidget(self.partner_type_combo, 1, 1)

        form_layout.addWidget(self._label("Vergi No / Kimlik No"), 2, 0)
        form_layout.addWidget(self._label("Vergi Dairesi"), 2, 1)
        form_layout.addWidget(self.tax_number_input, 3, 0)
        form_layout.addWidget(self.tax_office_input, 3, 1)

        form_layout.addWidget(self._label("Yetkili"), 4, 0)
        form_layout.addWidget(self._label("Telefon"), 4, 1)
        form_layout.addWidget(self.authorized_person_input, 5, 0)
        form_layout.addWidget(self.phone_input, 5, 1)

        form_layout.addWidget(self._label("E-posta"), 6, 0)
        form_layout.addWidget(self._label("Durum"), 6, 1)
        form_layout.addWidget(self.email_input, 7, 0)
        form_layout.addWidget(self.is_active_checkbox, 7, 1)

        form_layout.addWidget(self._label("Adres"), 8, 0, 1, 2)
        form_layout.addWidget(self.address_input, 9, 0, 1, 2)

        form_layout.addWidget(self._label("Not"), 10, 0, 1, 2)
        form_layout.addWidget(self.notes_input, 11, 0, 1, 2)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        button_layout.addStretch(1)

        cancel_button = QPushButton("Vazgeç")
        cancel_button.setObjectName("ActionSecondaryButton")
        cancel_button.setMinimumHeight(40)
        cancel_button.clicked.connect(self.reject)

        save_button = QPushButton("Kaydet")
        save_button.setObjectName("ActionPrimaryButton")
        save_button.setMinimumHeight(40)
        save_button.clicked.connect(self.accept)

        button_layout.addWidget(cancel_button)
        button_layout.addWidget(save_button)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(4)
        layout.addLayout(form_layout)
        layout.addLayout(button_layout)

        root_layout.addWidget(card)

        self._fill_existing_values()

    def _label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("DialogLabel")
        return label

    def _fill_existing_values(self) -> None:
        if self.partner_row is None:
            return

        self.name_input.setText(self.partner_row.name)
        self.tax_number_input.setText(self.partner_row.tax_number or "")
        self.tax_office_input.setText(self.partner_row.tax_office or "")
        self.authorized_person_input.setText(self.partner_row.authorized_person or "")
        self.phone_input.setText(self.partner_row.phone or "")
        self.email_input.setText(self.partner_row.email or "")
        self.address_input.setPlainText(self.partner_row.address or "")
        self.notes_input.setPlainText(self.partner_row.notes or "")
        self.is_active_checkbox.setChecked(self.partner_row.is_active)

        partner_type_index = self.partner_type_combo.findData(self.partner_row.partner_type)

        if partner_type_index >= 0:
            self.partner_type_combo.setCurrentIndex(partner_type_index)

    def _build_payload(self) -> dict[str, Any]:
        name = self.name_input.text().strip()
        partner_type = str(self.partner_type_combo.currentData() or "").strip().upper()
        email = self.email_input.text().strip()

        if not name:
            raise ValueError("Ad / Ünvan boş olamaz.")

        if not partner_type:
            raise ValueError("Tip seçilmelidir.")

        if partner_type not in {item.value for item in BusinessPartnerType}:
            raise ValueError("Geçersiz kart tipi seçildi.")

        if email and "@" not in email:
            raise ValueError("E-posta adresi geçerli görünmüyor.")

        return {
            "name": name,
            "partner_type": partner_type,
            "tax_office": _clean_optional_text(self.tax_office_input.text()),
            "tax_number": _clean_optional_text(self.tax_number_input.text()),
            "authorized_person": _clean_optional_text(self.authorized_person_input.text()),
            "phone": _clean_optional_text(self.phone_input.text()),
            "email": _clean_optional_text(email),
            "address": _clean_optional_text(self.address_input.toPlainText()),
            "notes": _clean_optional_text(self.notes_input.toPlainText()),
            "is_active": bool(self.is_active_checkbox.isChecked()),
        }

    def accept(self) -> None:
        try:
            self.payload = self._build_payload()
        except Exception as exc:
            QMessageBox.warning(self, "Eksik veya hatalı bilgi", str(exc))
            return

        super().accept()

    def get_payload(self) -> dict[str, Any]:
        if self.payload is None:
            self.payload = self._build_payload()

        return self.payload


class BusinessPartnersPage(QWidget):
    def __init__(self, current_user: Any | None = None) -> None:
        super().__init__()

        self.current_user = current_user
        self.current_role = _current_role_text(current_user)
        self.can_modify = self.current_role in {"ADMIN", "FINANCE", "DATA_ENTRY"}

        self.partner_rows: list[BusinessPartnerRow] = []
        self.filtered_rows: list[BusinessPartnerRow] = []
        self.current_page_index = 0

        self.setObjectName("BusinessPartnersPage")
        self.setStyleSheet(PAGE_STYLE)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(14)

        header_card = self._build_header_card()
        filter_card = self._build_filter_card()
        summary_layout = self._build_summary_layout()
        table_card = self._build_table_card()

        root_layout.addWidget(header_card)
        root_layout.addWidget(filter_card)
        root_layout.addLayout(summary_layout)
        root_layout.addWidget(table_card, 1)

        self._reload_data(reset_page=True)

    def _build_header_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("Card")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(6)

        title = QLabel("Müşteri / Tedarikçi Kartları")
        title.setObjectName("SectionTitle")

        subtitle = QLabel(
            "Gelen ve giden çeklerde kullanılan taraf kartlarını bu ekranda yönetebilirsin. "
            "Bu ekran cari borç/alacak defteri değildir; çekin kimden alındığını veya kime verildiğini düzenli takip etmek için kullanılır."
        )
        subtitle.setObjectName("MutedText")
        subtitle.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(subtitle)

        return card

    def _build_filter_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("Card")

        layout = QGridLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(8)
        layout.setColumnStretch(0, 2)
        layout.setColumnStretch(1, 1)
        layout.setColumnStretch(2, 1)
        layout.setColumnStretch(3, 1)

        search_label = QLabel("Arama")
        search_label.setObjectName("MutedText")

        type_label = QLabel("Tip")
        type_label.setObjectName("MutedText")

        status_label = QLabel("Durum")
        status_label.setObjectName("MutedText")

        page_size_label = QLabel("Sayfa")
        page_size_label.setObjectName("MutedText")

        self.search_input = QLineEdit()
        self.search_input.setMinimumHeight(38)
        self.search_input.setPlaceholderText("Ad, vergi no, telefon, e-posta, yetkili veya not ara")
        self.search_input.textChanged.connect(self._filter_changed)

        self.type_filter_combo = QComboBox()
        self.type_filter_combo.setMinimumHeight(38)
        self.type_filter_combo.addItem("Tüm tipler", "ALL")
        self.type_filter_combo.addItem("Müşteri", BusinessPartnerType.CUSTOMER.value)
        self.type_filter_combo.addItem("Tedarikçi", BusinessPartnerType.SUPPLIER.value)
        self.type_filter_combo.addItem("Müşteri & Tedarikçi", BusinessPartnerType.BOTH.value)
        self.type_filter_combo.addItem("Diğer", BusinessPartnerType.OTHER.value)
        self.type_filter_combo.currentIndexChanged.connect(self._filter_changed)

        self.status_filter_combo = QComboBox()
        self.status_filter_combo.setMinimumHeight(38)
        self.status_filter_combo.addItem("Aktif", "ACTIVE")
        self.status_filter_combo.addItem("Tümü", "ALL")
        self.status_filter_combo.addItem("Pasif", "PASSIVE")
        self.status_filter_combo.currentIndexChanged.connect(self._filter_changed)

        self.page_size_combo = QComboBox()
        self.page_size_combo.setMinimumHeight(38)
        self.page_size_combo.addItem("25 kayıt", 25)
        self.page_size_combo.addItem("50 kayıt", 50)
        self.page_size_combo.addItem("100 kayıt", 100)
        self.page_size_combo.currentIndexChanged.connect(self._page_size_changed)

        layout.addWidget(search_label, 0, 0)
        layout.addWidget(type_label, 0, 1)
        layout.addWidget(status_label, 0, 2)
        layout.addWidget(page_size_label, 0, 3)

        layout.addWidget(self.search_input, 1, 0)
        layout.addWidget(self.type_filter_combo, 1, 1)
        layout.addWidget(self.status_filter_combo, 1, 2)
        layout.addWidget(self.page_size_combo, 1, 3)

        return card

    def _build_summary_layout(self) -> QGridLayout:
        layout = QGridLayout()
        layout.setSpacing(10)
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(1, 1)
        layout.setColumnStretch(2, 1)
        layout.setColumnStretch(3, 1)
        layout.setColumnStretch(4, 1)

        self.total_count_card = self._build_summary_card("TOPLAM KART", "0", "Tüm kayıtlar")
        self.customer_count_card = self._build_summary_card("MÜŞTERİ", "0", "Çek aldığın taraflar")
        self.supplier_count_card = self._build_summary_card("TEDARİKÇİ", "0", "Çek verdiğin taraflar")
        self.both_count_card = self._build_summary_card("HER İKİSİ", "0", "İki yönde kullanılanlar")
        self.other_count_card = self._build_summary_card("DİĞER", "0", "Tek seferlik / nadir")

        layout.addWidget(self.total_count_card, 0, 0)
        layout.addWidget(self.customer_count_card, 0, 1)
        layout.addWidget(self.supplier_count_card, 0, 2)
        layout.addWidget(self.both_count_card, 0, 3)
        layout.addWidget(self.other_count_card, 0, 4)

        return layout

    def _build_summary_card(self, title_text: str, value_text: str, hint_text: str) -> QFrame:
        card = QFrame()
        card.setObjectName("Card")
        card.setMinimumHeight(92)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(4)

        title = QLabel(title_text)
        title.setObjectName("MutedText")

        value = QLabel(value_text)
        value.setObjectName("CardValue")
        value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        hint = QLabel(hint_text)
        hint.setObjectName("MutedText")
        hint.setWordWrap(True)

        layout.addWidget(title)
        layout.addStretch(1)
        layout.addWidget(value)
        layout.addWidget(hint)

        card.value_label = value
        card.hint_label = hint

        return card

    def _build_table_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("Card")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        action_row = QHBoxLayout()
        action_row.setSpacing(10)

        self.new_button = QPushButton("Yeni Kart")
        self.new_button.setObjectName("ActionPrimaryButton")
        self.new_button.setMinimumHeight(38)
        self.new_button.clicked.connect(self._open_create_dialog)

        self.edit_button = QPushButton("Düzenle")
        self.edit_button.setObjectName("ActionSecondaryButton")
        self.edit_button.setMinimumHeight(38)
        self.edit_button.clicked.connect(self._open_edit_dialog)

        self.toggle_active_button = QPushButton("Pasife Al")
        self.toggle_active_button.setObjectName("ActionDangerButton")
        self.toggle_active_button.setMinimumHeight(38)
        self.toggle_active_button.clicked.connect(self._toggle_selected_partner_active_state)

        self.refresh_button = QPushButton("Yenile")
        self.refresh_button.setObjectName("ActionSecondaryButton")
        self.refresh_button.setMinimumHeight(38)
        self.refresh_button.clicked.connect(lambda: self._reload_data(reset_page=False))

        action_row.addWidget(self.new_button)
        action_row.addWidget(self.edit_button)
        action_row.addWidget(self.toggle_active_button)
        action_row.addWidget(self.refresh_button)
        action_row.addStretch(1)

        self.permission_label = QLabel("")
        self.permission_label.setObjectName("MutedText")
        self.permission_label.setWordWrap(True)

        self.results_info_label = QLabel("")
        self.results_info_label.setObjectName("MutedText")
        self.results_info_label.setWordWrap(True)

        self.table = QTableWidget()
        self.table.setColumnCount(10)
        self.table.setHorizontalHeaderLabels(
            [
                "ID",
                "Ad / Ünvan",
                "Tip",
                "Vergi No",
                "Vergi Dairesi",
                "Yetkili",
                "Telefon",
                "E-posta",
                "Durum",
                "Not",
            ]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setWordWrap(False)
        self.table.setTextElideMode(Qt.ElideRight)
        self.table.verticalHeader().setDefaultSectionSize(34)
        self.table.verticalHeader().setMinimumSectionSize(30)
        self.table.setMinimumHeight(420)
        self.table.itemSelectionChanged.connect(self._selection_changed)
        self.table.itemDoubleClicked.connect(lambda item: self._open_edit_dialog())

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(8, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(9, QHeaderView.ResizeToContents)

        pagination_row = QHBoxLayout()
        pagination_row.setSpacing(10)

        self.previous_page_button = QPushButton("Önceki")
        self.previous_page_button.setObjectName("ActionSecondaryButton")
        self.previous_page_button.setMinimumHeight(34)
        self.previous_page_button.clicked.connect(self._go_previous_page)

        self.page_info_label = QLabel("")
        self.page_info_label.setObjectName("MutedText")
        self.page_info_label.setAlignment(Qt.AlignCenter)

        self.next_page_button = QPushButton("Sonraki")
        self.next_page_button.setObjectName("ActionSecondaryButton")
        self.next_page_button.setMinimumHeight(34)
        self.next_page_button.clicked.connect(self._go_next_page)

        pagination_row.addStretch(1)
        pagination_row.addWidget(self.previous_page_button)
        pagination_row.addWidget(self.page_info_label)
        pagination_row.addWidget(self.next_page_button)

        layout.addLayout(action_row)
        layout.addWidget(self.permission_label)
        layout.addWidget(self.results_info_label)
        layout.addWidget(self.table, 1)
        layout.addLayout(pagination_row)

        self._update_permission_state()

        return card

    def _update_permission_state(self) -> None:
        self.new_button.setEnabled(self.can_modify)
        self.edit_button.setEnabled(False)
        self.toggle_active_button.setEnabled(False)

        if self.can_modify:
            self.permission_label.setText(
                "Bu rol müşteri / tedarikçi kartı ekleme, düzenleme ve aktif/pasif işlemi yapabilir."
            )
        else:
            self.permission_label.setText(
                "Bu rol sadece müşteri / tedarikçi kartlarını görüntüleyebilir."
            )

    def _load_partner_rows(self) -> list[BusinessPartnerRow]:
        with session_scope() as session:
            statement = (
                select(BusinessPartner)
                .order_by(
                    BusinessPartner.is_active.desc(),
                    BusinessPartner.name.asc(),
                    BusinessPartner.id.asc(),
                )
            )

            partners = list(session.execute(statement).scalars().all())

            rows: list[BusinessPartnerRow] = []

            for partner in partners:
                rows.append(
                    BusinessPartnerRow(
                        id=partner.id,
                        name=partner.name,
                        partner_type=_enum_value(partner.partner_type),
                        tax_office=partner.tax_office,
                        tax_number=partner.tax_number,
                        authorized_person=partner.authorized_person,
                        phone=partner.phone,
                        email=partner.email,
                        address=partner.address,
                        notes=partner.notes,
                        is_active=bool(partner.is_active),
                        created_at=partner.created_at,
                        updated_at=partner.updated_at,
                    )
                )

            return rows

    def _reload_data(self, *, reset_page: bool) -> None:
        self.partner_rows = self._load_partner_rows()

        if reset_page:
            self.current_page_index = 0

        self._apply_filters(reset_page=reset_page)

    def _matches_search(self, row: BusinessPartnerRow, search_text: str) -> bool:
        if not search_text:
            return True

        normalized_search_text = search_text.strip().lower()

        searchable_text = " | ".join(
            [
                str(row.id),
                row.name,
                business_partner_type_text(row.partner_type),
                row.partner_type,
                row.tax_office or "",
                row.tax_number or "",
                row.authorized_person or "",
                row.phone or "",
                row.email or "",
                row.address or "",
                row.notes or "",
                "aktif" if row.is_active else "pasif",
            ]
        ).lower()

        return normalized_search_text in searchable_text

    def _matches_type_filter(self, row: BusinessPartnerRow) -> bool:
        selected_type = str(self.type_filter_combo.currentData() or "ALL")

        if selected_type == "ALL":
            return True

        return row.partner_type == selected_type

    def _matches_status_filter(self, row: BusinessPartnerRow) -> bool:
        selected_status = str(self.status_filter_combo.currentData() or "ALL")

        if selected_status == "ALL":
            return True

        if selected_status == "ACTIVE":
            return row.is_active

        if selected_status == "PASSIVE":
            return not row.is_active

        return True

    def _filter_changed(self) -> None:
        self._apply_filters(reset_page=True)

    def _page_size_changed(self) -> None:
        self._apply_filters(reset_page=True)

    def _apply_filters(self, *, reset_page: bool) -> None:
        if reset_page:
            self.current_page_index = 0

        search_text = self.search_input.text().strip()

        self.filtered_rows = [
            row
            for row in self.partner_rows
            if self._matches_search(row, search_text)
            and self._matches_type_filter(row)
            and self._matches_status_filter(row)
        ]

        self.filtered_rows.sort(
            key=lambda row: (
                not row.is_active,
                row.partner_type,
                row.name.lower(),
                row.id,
            )
        )

        self._clamp_current_page()
        self._fill_table(self._current_page_rows())
        self._update_results_info()
        self._update_summary_cards()
        self._update_pagination_controls()
        self._selection_changed()

    def _selected_page_size(self) -> int:
        try:
            value = int(self.page_size_combo.currentData())
        except (TypeError, ValueError):
            value = 25

        if value <= 0:
            return 25

        return value

    def _total_page_count(self) -> int:
        page_size = self._selected_page_size()

        if not self.filtered_rows:
            return 1

        return max(1, ((len(self.filtered_rows) - 1) // page_size) + 1)

    def _clamp_current_page(self) -> None:
        total_page_count = self._total_page_count()

        if self.current_page_index < 0:
            self.current_page_index = 0

        if self.current_page_index >= total_page_count:
            self.current_page_index = total_page_count - 1

    def _current_page_rows(self) -> list[BusinessPartnerRow]:
        page_size = self._selected_page_size()
        start_index = self.current_page_index * page_size
        end_index = start_index + page_size

        return self.filtered_rows[start_index:end_index]

    def _go_previous_page(self) -> None:
        if self.current_page_index <= 0:
            return

        self.current_page_index -= 1
        self._apply_filters(reset_page=False)

    def _go_next_page(self) -> None:
        if self.current_page_index >= self._total_page_count() - 1:
            return

        self.current_page_index += 1
        self._apply_filters(reset_page=False)

    def _fill_table(self, rows: list[BusinessPartnerRow]) -> None:
        self.table.setRowCount(len(rows))

        for row_index, row in enumerate(rows):
            values = [
                str(row.id),
                row.name,
                business_partner_type_text(row.partner_type),
                _format_optional_text(row.tax_number),
                _format_optional_text(row.tax_office),
                _format_optional_text(row.authorized_person),
                _format_optional_text(row.phone),
                _format_optional_text(row.email),
                "Aktif" if row.is_active else "Pasif",
                _format_optional_text(row.notes),
            ]

            tooltip_lines = [
                f"ID: {row.id}",
                f"Ad / Ünvan: {row.name}",
                f"Tip: {business_partner_type_text(row.partner_type)}",
                f"Vergi No: {_format_optional_text(row.tax_number)}",
                f"Vergi Dairesi: {_format_optional_text(row.tax_office)}",
                f"Yetkili: {_format_optional_text(row.authorized_person)}",
                f"Telefon: {_format_optional_text(row.phone)}",
                f"E-posta: {_format_optional_text(row.email)}",
                f"Adres: {_format_optional_text(row.address)}",
                f"Not: {_format_optional_text(row.notes)}",
                f"Durum: {'Aktif' if row.is_active else 'Pasif'}",
                f"Oluşturma: {_format_datetime(row.created_at)}",
                f"Son Güncelleme: {_format_datetime(row.updated_at)}",
            ]

            for column_index, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.UserRole, row.id)
                item.setToolTip("\n".join(tooltip_lines))

                if column_index == 0:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                else:
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)

                if not row.is_active:
                    item.setForeground(QColor("#94a3b8"))
                elif row.partner_type == BusinessPartnerType.CUSTOMER.value:
                    item.setForeground(QColor("#e5e7eb"))
                elif row.partner_type == BusinessPartnerType.SUPPLIER.value:
                    item.setForeground(QColor("#bfdbfe"))
                elif row.partner_type == BusinessPartnerType.BOTH.value:
                    item.setForeground(QColor("#a7f3d0"))
                elif row.partner_type == BusinessPartnerType.OTHER.value:
                    item.setForeground(QColor("#facc15"))
                else:
                    item.setForeground(QColor("#e5e7eb"))

                self.table.setItem(row_index, column_index, item)

        self.table.resizeRowsToContents()

    def _update_results_info(self) -> None:
        total_count = len(self.partner_rows)
        filtered_count = len(self.filtered_rows)

        if total_count == 0:
            self.results_info_label.setText(
                "Henüz müşteri / tedarikçi kartı bulunmuyor. Yeni Kart butonu ile ilk kartı oluşturabilirsin."
            )
            return

        if filtered_count == 0:
            self.results_info_label.setText(
                "Arama veya filtreye uygun müşteri / tedarikçi kartı bulunamadı."
            )
            return

        page_size = self._selected_page_size()
        start_number = self.current_page_index * page_size + 1
        end_number = min(start_number + page_size - 1, filtered_count)

        self.results_info_label.setText(
            f"Toplam {total_count} kart içinden {filtered_count} kayıt bulundu. "
            f"{start_number}-{end_number} arası gösteriliyor."
        )

    def _update_summary_cards(self) -> None:
        total_count = len(self.partner_rows)
        customer_count = len(
            [
                row
                for row in self.partner_rows
                if row.partner_type == BusinessPartnerType.CUSTOMER.value
            ]
        )
        supplier_count = len(
            [
                row
                for row in self.partner_rows
                if row.partner_type == BusinessPartnerType.SUPPLIER.value
            ]
        )
        both_count = len(
            [
                row
                for row in self.partner_rows
                if row.partner_type == BusinessPartnerType.BOTH.value
            ]
        )
        other_count = len(
            [
                row
                for row in self.partner_rows
                if row.partner_type == BusinessPartnerType.OTHER.value
            ]
        )

        self.total_count_card.value_label.setText(str(total_count))
        self.customer_count_card.value_label.setText(str(customer_count))
        self.supplier_count_card.value_label.setText(str(supplier_count))
        self.both_count_card.value_label.setText(str(both_count))
        self.other_count_card.value_label.setText(str(other_count))

    def _update_pagination_controls(self) -> None:
        total_page_count = self._total_page_count()

        self.previous_page_button.setEnabled(self.current_page_index > 0)
        self.next_page_button.setEnabled(self.current_page_index < total_page_count - 1)

        self.page_info_label.setText(
            f"Sayfa {self.current_page_index + 1} / {total_page_count}"
        )

    def _selected_partner_id(self) -> int | None:
        current_row = self.table.currentRow()

        if current_row < 0:
            return None

        id_item = self.table.item(current_row, 0)

        if id_item is None:
            return None

        partner_id = id_item.data(Qt.UserRole)

        if partner_id in {None, ""}:
            partner_id = id_item.text()

        try:
            return int(partner_id)
        except (TypeError, ValueError):
            return None

    def _selected_partner_row(self) -> BusinessPartnerRow | None:
        selected_partner_id = self._selected_partner_id()

        if selected_partner_id is None:
            return None

        for row in self.partner_rows:
            if row.id == selected_partner_id:
                return row

        return None

    def _selection_changed(self) -> None:
        selected_row = self._selected_partner_row()
        has_selection = selected_row is not None

        self.edit_button.setEnabled(self.can_modify and has_selection)
        self.toggle_active_button.setEnabled(self.can_modify and has_selection)

        if not has_selection:
            self.toggle_active_button.setText("Pasife Al")
            self.toggle_active_button.setObjectName("ActionDangerButton")
        elif selected_row.is_active:
            self.toggle_active_button.setText("Pasife Al")
            self.toggle_active_button.setObjectName("ActionDangerButton")
        else:
            self.toggle_active_button.setText("Aktife Al")
            self.toggle_active_button.setObjectName("ActionSuccessButton")

        self.toggle_active_button.style().unpolish(self.toggle_active_button)
        self.toggle_active_button.style().polish(self.toggle_active_button)
        self.toggle_active_button.update()

    def _find_duplicate_name(
        self,
        *,
        session,
        name: str,
        exclude_partner_id: int | None,
    ) -> BusinessPartner | None:
        statement = select(BusinessPartner).where(
            func.lower(BusinessPartner.name) == name.lower()
        )

        if exclude_partner_id is not None:
            statement = statement.where(BusinessPartner.id != exclude_partner_id)

        return session.execute(statement).scalar_one_or_none()

    def _open_create_dialog(self) -> None:
        if not self.can_modify:
            QMessageBox.warning(
                self,
                "Yetkisiz işlem",
                "Bu işlem için ADMIN, FINANCE veya DATA_ENTRY yetkisi gerekir.",
            )
            return

        dialog = BusinessPartnerDialog(parent=self)

        if dialog.exec() != QDialog.Accepted:
            return

        payload = dialog.get_payload()

        try:
            self._create_partner(payload)
            self._reload_data(reset_page=True)

            QMessageBox.information(
                self,
                "Kart oluşturuldu",
                "Müşteri / tedarikçi kartı başarıyla oluşturuldu.",
            )

        except Exception as exc:
            QMessageBox.warning(
                self,
                "Kart oluşturulamadı",
                str(exc),
            )

    def _open_edit_dialog(self) -> None:
        if not self.can_modify:
            QMessageBox.warning(
                self,
                "Yetkisiz işlem",
                "Bu işlem için ADMIN, FINANCE veya DATA_ENTRY yetkisi gerekir.",
            )
            return

        selected_row = self._selected_partner_row()

        if selected_row is None:
            QMessageBox.information(
                self,
                "Seçim gerekli",
                "Düzenlemek için bir müşteri / tedarikçi kartı seçmelisin.",
            )
            return

        dialog = BusinessPartnerDialog(parent=self, partner_row=selected_row)

        if dialog.exec() != QDialog.Accepted:
            return

        payload = dialog.get_payload()

        try:
            self._update_partner(selected_row.id, payload)
            self._reload_data(reset_page=False)

            QMessageBox.information(
                self,
                "Kart güncellendi",
                "Müşteri / tedarikçi kartı başarıyla güncellendi.",
            )

        except Exception as exc:
            QMessageBox.warning(
                self,
                "Kart güncellenemedi",
                str(exc),
            )

    def _create_partner(self, payload: dict[str, Any]) -> None:
        with session_scope() as session:
            duplicate = self._find_duplicate_name(
                session=session,
                name=payload["name"],
                exclude_partner_id=None,
            )

            if duplicate is not None:
                raise ValueError(
                    f"Bu ad / ünvan ile zaten bir kart var. Mevcut Kart ID: {duplicate.id}"
                )

            partner = BusinessPartner(
                name=payload["name"],
                partner_type=BusinessPartnerType(payload["partner_type"]),
                tax_office=payload["tax_office"],
                tax_number=payload["tax_number"],
                authorized_person=payload["authorized_person"],
                phone=payload["phone"],
                email=payload["email"],
                address=payload["address"],
                notes=payload["notes"],
                is_active=payload["is_active"],
            )

            session.add(partner)
            session.flush()

            write_audit_log(
                session,
                user_id=_current_user_id(self.current_user),
                action="BUSINESS_PARTNER_CREATED",
                entity_type="BusinessPartner",
                entity_id=partner.id,
                description=f"Müşteri / tedarikçi kartı oluşturuldu: {partner.name}",
                old_values=None,
                new_values=_business_partner_to_dict(partner),
            )

    def _update_partner(self, partner_id: int, payload: dict[str, Any]) -> None:
        with session_scope() as session:
            partner = session.get(BusinessPartner, partner_id)

            if partner is None:
                raise ValueError(f"Kart bulunamadı. Kart ID: {partner_id}")

            duplicate = self._find_duplicate_name(
                session=session,
                name=payload["name"],
                exclude_partner_id=partner_id,
            )

            if duplicate is not None:
                raise ValueError(
                    f"Bu ad / ünvan ile başka bir kart var. Mevcut Kart ID: {duplicate.id}"
                )

            old_values = _business_partner_to_dict(partner)

            partner.name = payload["name"]
            partner.partner_type = BusinessPartnerType(payload["partner_type"])
            partner.tax_office = payload["tax_office"]
            partner.tax_number = payload["tax_number"]
            partner.authorized_person = payload["authorized_person"]
            partner.phone = payload["phone"]
            partner.email = payload["email"]
            partner.address = payload["address"]
            partner.notes = payload["notes"]
            partner.is_active = payload["is_active"]

            session.flush()

            write_audit_log(
                session,
                user_id=_current_user_id(self.current_user),
                action="BUSINESS_PARTNER_UPDATED",
                entity_type="BusinessPartner",
                entity_id=partner.id,
                description=f"Müşteri / tedarikçi kartı güncellendi: {partner.name}",
                old_values=old_values,
                new_values=_business_partner_to_dict(partner),
            )

    def _toggle_selected_partner_active_state(self) -> None:
        if not self.can_modify:
            QMessageBox.warning(
                self,
                "Yetkisiz işlem",
                "Bu işlem için ADMIN, FINANCE veya DATA_ENTRY yetkisi gerekir.",
            )
            return

        selected_row = self._selected_partner_row()

        if selected_row is None:
            QMessageBox.information(
                self,
                "Seçim gerekli",
                "Aktif/pasif işlemi için bir müşteri / tedarikçi kartı seçmelisin.",
            )
            return

        if selected_row.is_active:
            question_title = "Kart pasife alınsın mı?"
            question_text = (
                f"{selected_row.name} pasife alınacak.\n\n"
                "Pasif kart geçmiş çeklerde görünmeye devam eder ancak yeni işlemlerde tercih edilmemelidir.\n\n"
                "Devam etmek istiyor musun?"
            )
            new_active_state = False
        else:
            question_title = "Kart aktife alınsın mı?"
            question_text = (
                f"{selected_row.name} tekrar aktif yapılacak.\n\n"
                "Devam etmek istiyor musun?"
            )
            new_active_state = True

        answer = QMessageBox.question(
            self,
            question_title,
            question_text,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if answer != QMessageBox.Yes:
            return

        try:
            self._set_partner_active_state(selected_row.id, new_active_state)
            self._reload_data(reset_page=False)

            QMessageBox.information(
                self,
                "İşlem tamamlandı",
                "Kart durumu başarıyla güncellendi.",
            )

        except Exception as exc:
            QMessageBox.warning(
                self,
                "İşlem tamamlanamadı",
                str(exc),
            )

    def _set_partner_active_state(self, partner_id: int, is_active: bool) -> None:
        with session_scope() as session:
            partner = session.get(BusinessPartner, partner_id)

            if partner is None:
                raise ValueError(f"Kart bulunamadı. Kart ID: {partner_id}")

            old_values = _business_partner_to_dict(partner)

            partner.is_active = is_active

            session.flush()

            write_audit_log(
                session,
                user_id=_current_user_id(self.current_user),
                action=(
                    "BUSINESS_PARTNER_ACTIVATED"
                    if is_active
                    else "BUSINESS_PARTNER_DEACTIVATED"
                ),
                entity_type="BusinessPartner",
                entity_id=partner.id,
                description=(
                    f"Müşteri / tedarikçi kartı "
                    f"{'aktife alındı' if is_active else 'pasife alındı'}: {partner.name}"
                ),
                old_values=old_values,
                new_values=_business_partner_to_dict(partner),
            )