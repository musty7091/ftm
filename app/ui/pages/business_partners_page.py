from dataclasses import dataclass
from functools import cmp_to_key
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QAbstractScrollArea,
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
    QMenu,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTabWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy import func, select

from app.db.session import session_scope
from app.models.business_partner import BusinessPartner
from app.models.check import IssuedCheck, ReceivedCheck
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


@dataclass(frozen=True)
class PartnerPositionBucket:
    count: int
    currency_totals: dict[str, Decimal]


PARTNER_TYPE_TEXTS = {
    "CUSTOMER": "Müşteri",
    "SUPPLIER": "Tedarikçi",
    "BOTH": "Müşteri & Tedarikçi",
    "OTHER": "Diğer",
}

POSITION_EMPTY_TITLE = "Seçili Muhatap: Henüz seçim yok"
POSITION_EMPTY_SUBTITLE = "Bir müşteri / tedarikçi seçildiğinde çek pozisyonu burada görünür."
POSITION_EMPTY_CARD_VALUE = "—"
POSITION_EMPTY_CARD_HINT = "Seçim bekleniyor"

PROFILE_EMPTY_NAME = "Muhatap seçilmedi"
PROFILE_EMPTY_META = "Tablodan bir müşteri / tedarikçi seçildiğinde mini profil burada görünür."
PROFILE_EMPTY_RISK_TITLE = "Seçim bekleniyor"
PROFILE_EMPTY_RISK_DETAIL = "Firma kimliği ve çek pozisyonu seçime göre özetlenir."


RECEIVED_OPEN_STATUSES = {
    "PORTFOLIO",
    "GIVEN_TO_BANK",
    "IN_COLLECTION",
}

RECEIVED_PROBLEM_STATUSES = {
    "BOUNCED",
}

RECEIVED_CLOSED_STATUSES = {
    "COLLECTED",
    "ENDORSED",
    "DISCOUNTED",
    "RETURNED",
    "CANCELLED",
}

ISSUED_OPEN_STATUSES = {
    "PREPARED",
    "GIVEN",
}

ISSUED_PROBLEM_STATUSES = {
    "RISK",
}

ISSUED_CLOSED_STATUSES = {
    "PAID",
    "CANCELLED",
}

RECEIVED_STATUS_TEXTS = {
    "PORTFOLIO": "Portföyde",
    "GIVEN_TO_BANK": "Bankaya Verildi",
    "IN_COLLECTION": "Tahsilde",
    "COLLECTED": "Tahsil Edildi",
    "BOUNCED": "Karşılıksız",
    "RETURNED": "İade Edildi",
    "ENDORSED": "Ciro Edildi",
    "DISCOUNTED": "İskontoya Verildi",
    "CANCELLED": "İptal Edildi",
}


ISSUED_STATUS_TEXTS = {
    "PREPARED": "Hazırlandı",
    "GIVEN": "Verildi",
    "PAID": "Ödendi",
    "CANCELLED": "İptal Edildi",
    "RISK": "Riskli",
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

QFrame#FilterPanel {
    background-color: #101827;
    border: 1px solid #24324a;
    border-radius: 18px;
}

QFrame#FilterPanelAccent {
    background-color: rgba(37, 99, 235, 0.10);
    border: 1px solid rgba(59, 130, 246, 0.35);
    border-radius: 14px;
}

QFrame#PositionPanel {
    background-color: rgba(6, 78, 59, 0.16);
    border: 1px solid rgba(16, 185, 129, 0.35);
    border-radius: 16px;
}

QFrame#PositionMiniCard {
    background-color: rgba(15, 23, 42, 0.74);
    border: 1px solid rgba(148, 163, 184, 0.16);
    border-radius: 12px;
}

QLabel#PositionTitle {
    color: #f8fafc;
    font-size: 15px;
    font-weight: 800;
}

QLabel#PositionSubtitle {
    color: #93c5fd;
    font-size: 12px;
}

QLabel#PositionCardTitle {
    color: #bfdbfe;
    font-size: 11px;
    font-weight: 800;
}

QLabel#PositionCardValue {
    color: #ffffff;
    font-size: 15px;
    font-weight: 900;
}

QLabel#PositionCardHint {
    color: #94a3b8;
    font-size: 11px;
}

QFrame#CardActiveFilter {
    background-color: rgba(37, 99, 235, 0.22);
    border: 1px solid rgba(96, 165, 250, 0.72);
    border-radius: 18px;
}

QFrame#PartnerProfileCard {
    background-color: rgba(15, 23, 42, 0.72);
    border: 1px solid rgba(148, 163, 184, 0.18);
    border-radius: 14px;
}

QFrame#PartnerRiskCard {
    background-color: rgba(30, 41, 59, 0.64);
    border: 1px solid rgba(96, 165, 250, 0.28);
    border-radius: 14px;
}

QLabel#ProfileName {
    color: #f8fafc;
    font-size: 16px;
    font-weight: 900;
}

QLabel#ProfileMeta {
    color: #93c5fd;
    font-size: 12px;
    font-weight: 700;
}

QLabel#ProfileField {
    color: #cbd5e1;
    font-size: 12px;
}

QLabel#ProfileFieldMuted {
    color: #94a3b8;
    font-size: 12px;
}

QLabel#RiskTitle {
    color: #f8fafc;
    font-size: 14px;
    font-weight: 900;
}

QLabel#RiskDetail {
    color: #cbd5e1;
    font-size: 12px;
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


def _normalize_duplicate_text(value: str | None) -> str:
    return str(value or "").strip().lower()


def _normalize_sort_text(value: str | None) -> str:
    return str(value or "").strip().lower()


def _partner_type_sort_order(value: Any) -> int:
    value_text = _enum_value(value)

    order_map = {
        "CUSTOMER": 10,
        "SUPPLIER": 20,
        "BOTH": 30,
        "OTHER": 40,
    }

    return order_map.get(value_text, 99)


def _format_datetime(value: datetime | None) -> str:
    if value is None:
        return "-"

    try:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)

        local_value = value.astimezone()
        return local_value.strftime("%d.%m.%Y %H:%M")
    except Exception:
        return value.strftime("%d.%m.%Y %H:%M")

def _format_date(value: Any) -> str:
    if value is None:
        return "-"

    if hasattr(value, "strftime"):
        return value.strftime("%d.%m.%Y")

    return str(value)

def _format_decimal_tr(value: Decimal) -> str:
    formatted = f"{value:,.2f}"
    return formatted.replace(",", "X").replace(".", ",").replace("X", ".")


def _format_currency_amount(amount: Decimal, currency_code: str) -> str:
    return f"{_format_decimal_tr(Decimal(str(amount)))} {currency_code}"


def _sorted_currency_codes(currency_totals: dict[str, Decimal]) -> list[str]:
    if not currency_totals:
        return []

    codes = sorted(currency_totals)

    if "TRY" in codes:
        codes.remove("TRY")
        return ["TRY", *codes]

    return codes


def _format_currency_totals(currency_totals: dict[str, Decimal]) -> str:
    if not currency_totals:
        return "-"

    formatted_parts: list[str] = []

    for currency_code in _sorted_currency_codes(currency_totals):
        amount = currency_totals[currency_code]
        formatted_parts.append(_format_currency_amount(amount, currency_code))

    return " / ".join(formatted_parts)


def _format_currency_totals_compact(currency_totals: dict[str, Decimal]) -> str:
    if not currency_totals:
        return "-"

    currency_codes = _sorted_currency_codes(currency_totals)
    first_currency_code = currency_codes[0]
    first_amount = currency_totals[first_currency_code]
    first_text = _format_currency_amount(first_amount, first_currency_code)

    extra_currency_count = len(currency_codes) - 1

    if extra_currency_count <= 0:
        return first_text

    return f"{first_text} + {extra_currency_count} para birimi"


def _format_position_bucket(bucket: PartnerPositionBucket) -> tuple[str, str]:
    if bucket.count <= 0:
        return "0 kayıt", "-"

    return f"{bucket.count} kayıt", _format_currency_totals_compact(bucket.currency_totals)


def _format_position_bucket_tooltip(bucket: PartnerPositionBucket) -> str:
    if bucket.count <= 0:
        return "Bu pozisyonda çek kaydı bulunmuyor."

    return f"{bucket.count} kayıt\n{_format_currency_totals(bucket.currency_totals)}"

def _received_status_text(value: Any) -> str:
    status = _enum_value(value)

    return RECEIVED_STATUS_TEXTS.get(status, status or "-")


def _issued_status_text(value: Any) -> str:
    status = _enum_value(value)

    return ISSUED_STATUS_TEXTS.get(status, status or "-")

def _empty_position_bucket() -> PartnerPositionBucket:
    return PartnerPositionBucket(count=0, currency_totals={})


def _add_amount_to_bucket(
    buckets: dict[str, PartnerPositionBucket],
    bucket_key: str,
    amount: Decimal,
    currency_code: str,
) -> None:
    current_bucket = buckets.get(bucket_key, _empty_position_bucket())
    new_totals = dict(current_bucket.currency_totals)
    new_totals[currency_code] = (new_totals.get(currency_code, Decimal("0.00")) + amount).quantize(Decimal("0.01"))

    buckets[bucket_key] = PartnerPositionBucket(
        count=current_bucket.count + 1,
        currency_totals=new_totals,
    )


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

class BusinessPartnerChecksDetailDialog(QDialog):
    def __init__(
        self,
        *,
        parent: QWidget | None,
        partner_row: BusinessPartnerRow,
    ) -> None:
        super().__init__(parent)

        self.partner_row = partner_row
        self.received_rows = self._load_received_checks()
        self.issued_rows = self._load_issued_checks()

        self.setWindowTitle(f"Çek Detayları - {partner_row.name}")
        self.resize(1180, 720)
        self.setMinimumSize(980, 620)
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

            QTabWidget::pane {
                border: 1px solid #1e293b;
                background-color: #0b1220;
                border-radius: 12px;
                top: -1px;
            }

            QTabBar::tab {
                background-color: #172033;
                color: #94a3b8;
                border: 1px solid #24324a;
                border-bottom: none;
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
                padding: 8px 16px;
                margin-right: 5px;
                min-width: 128px;
                font-weight: 600;
            }

            QTabBar::tab:selected {
                background-color: #2563eb;
                color: #ffffff;
            }

            QTabBar::tab:hover:!selected {
                background-color: #1e293b;
                color: #e5e7eb;
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

        title = QLabel(f"Çek Detayları: {self.partner_row.name}")
        title.setObjectName("DialogTitle")

        subtitle = QLabel(
            f"Tip: {business_partner_type_text(self.partner_row.partner_type)} | "
            f"Durum: {'Aktif' if self.partner_row.is_active else 'Pasif'} | "
            "Bu ekran cari hesap hareketi değil, seçili karta bağlı gelen ve giden çek listesidir."
        )
        subtitle.setObjectName("DialogSubtitle")
        subtitle.setWordWrap(True)

        tabs = QTabWidget()
        tabs.addTab(self._build_received_tab(), f"Alınan Çekler ({len(self.received_rows)})")
        tabs.addTab(self._build_issued_tab(), f"Yazılan Çekler ({len(self.issued_rows)})")

        button_row = QHBoxLayout()
        button_row.addStretch(1)

        close_button = QPushButton("Kapat")
        close_button.setObjectName("ActionSecondaryButton")
        close_button.setMinimumHeight(40)
        close_button.clicked.connect(self.accept)

        button_row.addWidget(close_button)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(tabs, 1)
        layout.addLayout(button_row)

        root_layout.addWidget(card)

    def _load_received_checks(self) -> list[ReceivedCheck]:
        with session_scope() as session:
            rows = list(
                session.execute(
                    select(ReceivedCheck)
                    .where(ReceivedCheck.customer_id == self.partner_row.id)
                    .order_by(
                        ReceivedCheck.due_date.asc(),
                        ReceivedCheck.id.asc(),
                    )
                )
                .scalars()
                .all()
            )

            for row in rows:
                session.expunge(row)

            return rows

    def _load_issued_checks(self) -> list[IssuedCheck]:
        with session_scope() as session:
            rows = list(
                session.execute(
                    select(IssuedCheck)
                    .where(IssuedCheck.supplier_id == self.partner_row.id)
                    .order_by(
                        IssuedCheck.due_date.asc(),
                        IssuedCheck.id.asc(),
                    )
                )
                .scalars()
                .all()
            )

            for row in rows:
                session.expunge(row)

            return rows

    def _build_received_tab(self) -> QWidget:
        page = QWidget()

        layout = QVBoxLayout(page)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        info_label = QLabel(
            "Bu listede seçili karttan alınan çekler görünür."
            if self.received_rows
            else "Bu karta ait alınan çek bulunmuyor."
        )
        info_label.setObjectName("MutedText")
        info_label.setWordWrap(True)

        table = QTableWidget()
        table.setColumnCount(9)
        table.setHorizontalHeaderLabels(
            [
                "ID",
                "Çek No",
                "Keşideci Banka",
                "Alınış",
                "Vade",
                "Tutar",
                "Durum",
                "Referans",
                "Açıklama",
            ]
        )
        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setWordWrap(False)
        table.setTextElideMode(Qt.ElideRight)
        table.verticalHeader().setDefaultSectionSize(32)
        table.verticalHeader().setMinimumSectionSize(28)

        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(8, QHeaderView.ResizeToContents)

        self._fill_received_table(table)

        layout.addWidget(info_label)
        layout.addWidget(table, 1)

        return page

    def _build_issued_tab(self) -> QWidget:
        page = QWidget()

        layout = QVBoxLayout(page)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        info_label = QLabel(
            "Bu listede seçili karta yazılan çekler görünür."
            if self.issued_rows
            else "Bu karta ait yazılan çek bulunmuyor."
        )
        info_label.setObjectName("MutedText")
        info_label.setWordWrap(True)

        table = QTableWidget()
        table.setColumnCount(9)
        table.setHorizontalHeaderLabels(
            [
                "ID",
                "Çek No",
                "Keşide",
                "Vade",
                "Tutar",
                "Durum",
                "Referans",
                "Açıklama",
                "Banka Hesap ID",
            ]
        )
        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setWordWrap(False)
        table.setTextElideMode(Qt.ElideRight)
        table.verticalHeader().setDefaultSectionSize(32)
        table.verticalHeader().setMinimumSectionSize(28)

        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.Stretch)
        header.setSectionResizeMode(8, QHeaderView.ResizeToContents)

        self._fill_issued_table(table)

        layout.addWidget(info_label)
        layout.addWidget(table, 1)

        return page

    def _fill_received_table(self, table: QTableWidget) -> None:
        table.setRowCount(len(self.received_rows))

        for row_index, received_check in enumerate(self.received_rows):
            currency_code = _enum_value(received_check.currency_code) or "TRY"

            values = [
                str(received_check.id),
                received_check.check_number,
                received_check.drawer_bank_name,
                _format_date(received_check.received_date),
                _format_date(received_check.due_date),
                _format_currency_amount(
                    Decimal(str(received_check.amount or "0.00")),
                    currency_code,
                ),
                _received_status_text(received_check.status),
                received_check.reference_no or "-",
                received_check.description or "-",
            ]

            status = _enum_value(received_check.status)

            for column_index, value in enumerate(values):
                item = QTableWidgetItem(value)

                if status in RECEIVED_OPEN_STATUSES:
                    item.setForeground(QColor("#e5e7eb"))
                elif status in RECEIVED_PROBLEM_STATUSES:
                    item.setForeground(QColor("#fbbf24"))
                elif status in RECEIVED_CLOSED_STATUSES:
                    item.setForeground(QColor("#22c55e"))
                else:
                    item.setForeground(QColor("#e5e7eb"))

                if column_index == 5:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                else:
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)

                item.setToolTip("\n".join([
                    f"ID: {received_check.id}",
                    f"Çek No: {received_check.check_number}",
                    f"Keşideci Banka: {received_check.drawer_bank_name}",
                    f"Alınış: {_format_date(received_check.received_date)}",
                    f"Vade: {_format_date(received_check.due_date)}",
                    f"Tutar: {values[5]}",
                    f"Durum: {values[6]}",
                    f"Referans: {received_check.reference_no or '-'}",
                    f"Açıklama: {received_check.description or '-'}",
                ]))

                table.setItem(row_index, column_index, item)

        table.resizeRowsToContents()

    def _fill_issued_table(self, table: QTableWidget) -> None:
        table.setRowCount(len(self.issued_rows))

        for row_index, issued_check in enumerate(self.issued_rows):
            currency_code = _enum_value(issued_check.currency_code) or "TRY"

            values = [
                str(issued_check.id),
                issued_check.check_number,
                _format_date(issued_check.issue_date),
                _format_date(issued_check.due_date),
                _format_currency_amount(
                    Decimal(str(issued_check.amount or "0.00")),
                    currency_code,
                ),
                _issued_status_text(issued_check.status),
                issued_check.reference_no or "-",
                issued_check.description or "-",
                str(issued_check.bank_account_id),
            ]

            status = _enum_value(issued_check.status)

            for column_index, value in enumerate(values):
                item = QTableWidgetItem(value)

                if status in ISSUED_OPEN_STATUSES:
                    item.setForeground(QColor("#e5e7eb"))
                elif status in ISSUED_PROBLEM_STATUSES:
                    item.setForeground(QColor("#fbbf24"))
                elif status in ISSUED_CLOSED_STATUSES:
                    item.setForeground(QColor("#22c55e"))
                else:
                    item.setForeground(QColor("#e5e7eb"))

                if column_index == 4:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                else:
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)

                item.setToolTip("\n".join([
                    f"ID: {issued_check.id}",
                    f"Çek No: {issued_check.check_number}",
                    f"Keşide: {_format_date(issued_check.issue_date)}",
                    f"Vade: {_format_date(issued_check.due_date)}",
                    f"Tutar: {values[4]}",
                    f"Durum: {values[5]}",
                    f"Referans: {issued_check.reference_no or '-'}",
                    f"Açıklama: {issued_check.description or '-'}",
                    f"Banka Hesap ID: {issued_check.bank_account_id}",
                ]))

                table.setItem(row_index, column_index, item)

        table.resizeRowsToContents()

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
        self.sort_column_index: int | None = None
        self.sort_order = Qt.AscendingOrder

        self.setObjectName("BusinessPartnersPage")
        self.setStyleSheet(PAGE_STYLE)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(10)

        filter_card = self._build_filter_card()
        summary_layout = self._build_summary_layout()
        table_card = self._build_table_card()

        root_layout.addWidget(filter_card)
        root_layout.addLayout(summary_layout)
        root_layout.addWidget(table_card, 1)

        self._reload_data(reset_page=True)

    def _build_filter_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("FilterPanel")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(12)

        top_row = QHBoxLayout()
        top_row.setSpacing(10)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)

        title = QLabel("Müşteri / Tedarikçi Kartları")
        title.setObjectName("SectionTitle")

        subtitle = QLabel(
            "Çeklerde kullanılan taraf kartlarını yönet. Bu ekran cari borç/alacak defteri değil, çek muhatabı takip merkezidir."
        )
        subtitle.setObjectName("MutedText")
        subtitle.setWordWrap(True)

        title_box.addWidget(title)
        title_box.addWidget(subtitle)

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

        self.check_details_button = QPushButton("Çek Detayları")
        self.check_details_button.setObjectName("ActionSuccessButton")
        self.check_details_button.setMinimumHeight(38)
        self.check_details_button.clicked.connect(self._open_selected_partner_check_details)

        self.refresh_button = QPushButton("Yenile")
        self.refresh_button.setObjectName("ActionSecondaryButton")
        self.refresh_button.setMinimumHeight(38)
        self.refresh_button.clicked.connect(lambda: self._reload_data(reset_page=False))

        top_row.addLayout(title_box, 1)
        top_row.addWidget(self.new_button)
        top_row.addWidget(self.edit_button)
        top_row.addWidget(self.toggle_active_button)
        top_row.addWidget(self.check_details_button)
        top_row.addWidget(self.refresh_button)

        filter_inner = QFrame()
        filter_inner.setObjectName("FilterPanelAccent")

        filter_layout = QGridLayout(filter_inner)
        filter_layout.setContentsMargins(14, 12, 14, 12)
        filter_layout.setHorizontalSpacing(12)
        filter_layout.setVerticalSpacing(8)
        filter_layout.setColumnStretch(0, 2)
        filter_layout.setColumnStretch(1, 1)
        filter_layout.setColumnStretch(2, 1)
        filter_layout.setColumnStretch(3, 1)

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

        filter_layout.addWidget(search_label, 0, 0)
        filter_layout.addWidget(type_label, 0, 1)
        filter_layout.addWidget(status_label, 0, 2)
        filter_layout.addWidget(page_size_label, 0, 3)

        filter_layout.addWidget(self.search_input, 1, 0)
        filter_layout.addWidget(self.type_filter_combo, 1, 1)
        filter_layout.addWidget(self.status_filter_combo, 1, 2)
        filter_layout.addWidget(self.page_size_combo, 1, 3)

        self.permission_label = QLabel("")
        self.permission_label.setObjectName("MutedText")
        self.permission_label.setWordWrap(True)

        layout.addLayout(top_row)
        layout.addWidget(filter_inner)
        layout.addWidget(self.permission_label)

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

        self._configure_summary_filter_card(
            self.total_count_card,
            "ALL",
            "Tüm müşteri / tedarikçi kartlarını listele",
        )
        self._configure_summary_filter_card(
            self.customer_count_card,
            BusinessPartnerType.CUSTOMER.value,
            "Sadece müşteri kartlarını listele",
        )
        self._configure_summary_filter_card(
            self.supplier_count_card,
            BusinessPartnerType.SUPPLIER.value,
            "Sadece tedarikçi kartlarını listele",
        )
        self._configure_summary_filter_card(
            self.both_count_card,
            BusinessPartnerType.BOTH.value,
            "Müşteri ve tedarikçi olarak kullanılan kartları listele",
        )
        self._configure_summary_filter_card(
            self.other_count_card,
            BusinessPartnerType.OTHER.value,
            "Diğer tipindeki kartları listele",
        )

        layout.addWidget(self.total_count_card, 0, 0)
        layout.addWidget(self.customer_count_card, 0, 1)
        layout.addWidget(self.supplier_count_card, 0, 2)
        layout.addWidget(self.both_count_card, 0, 3)
        layout.addWidget(self.other_count_card, 0, 4)

        return layout

    def _build_summary_card(self, title_text: str, value_text: str, hint_text: str) -> QFrame:
        card = QFrame()
        card.setObjectName("Card")
        card.setMinimumHeight(84)
        card.setMaximumHeight(92)

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

    def _configure_summary_filter_card(self, card: QFrame, filter_value: str, tooltip_text: str) -> None:
        card.summary_filter_value = filter_value
        card.setCursor(Qt.PointingHandCursor)
        card.setToolTip(tooltip_text)

        def handle_click(event, selected_filter_value: str = filter_value) -> None:
            if event.button() == Qt.LeftButton:
                self._summary_filter_card_clicked(selected_filter_value)
            else:
                QFrame.mouseReleaseEvent(card, event)

        card.mouseReleaseEvent = handle_click

    def _summary_filter_card_clicked(self, selected_filter_value: str) -> None:
        index = self.type_filter_combo.findData(selected_filter_value)

        if index < 0:
            return

        self.type_filter_combo.setCurrentIndex(index)
        self._apply_filters(reset_page=True)

    def _build_table_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("Card")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(10)

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
        self.table.verticalHeader().setDefaultSectionSize(32)
        self.table.verticalHeader().setMinimumSectionSize(28)
        self.table.setMinimumHeight(300)
        self.table.setSizeAdjustPolicy(QAbstractScrollArea.AdjustIgnored)
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._open_table_context_menu)
        self.table.itemSelectionChanged.connect(self._selection_changed)
        self.table.itemDoubleClicked.connect(self._open_check_details_from_table_double_click)

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
        header.setSectionsClickable(True)
        header.setSortIndicatorShown(False)
        header.sectionClicked.connect(self._table_header_clicked)

        position_panel = self._build_position_panel()

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

        layout.addWidget(self.results_info_label)
        layout.addWidget(self.table, 1)
        layout.addWidget(position_panel)
        layout.addLayout(pagination_row)

        self._update_permission_state()

        return card

    def _build_position_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("PositionPanel")
        panel.setMinimumHeight(226)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        header_row = QHBoxLayout()
        header_row.setSpacing(10)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)

        self.position_title_label = QLabel(POSITION_EMPTY_TITLE)
        self.position_title_label.setObjectName("PositionTitle")

        self.position_subtitle_label = QLabel(POSITION_EMPTY_SUBTITLE)
        self.position_subtitle_label.setObjectName("PositionSubtitle")
        self.position_subtitle_label.setWordWrap(True)

        title_box.addWidget(self.position_title_label)
        title_box.addWidget(self.position_subtitle_label)

        header_row.addLayout(title_box, 1)

        profile_row = QHBoxLayout()
        profile_row.setSpacing(8)

        self.profile_identity_card = self._build_partner_profile_identity_card()
        self.profile_risk_card = self._build_partner_profile_risk_card()

        profile_row.addWidget(self.profile_identity_card, 3)
        profile_row.addWidget(self.profile_risk_card, 2)

        position_grid = QGridLayout()
        position_grid.setSpacing(8)
        position_grid.setColumnStretch(0, 1)
        position_grid.setColumnStretch(1, 1)
        position_grid.setColumnStretch(2, 1)
        position_grid.setColumnStretch(3, 1)
        position_grid.setColumnStretch(4, 1)
        position_grid.setColumnStretch(5, 1)

        self.received_open_card = self._build_position_mini_card("ALINAN AÇIK", "0 kayıt", "-")
        self.received_closed_card = self._build_position_mini_card("ALINAN SONUÇ", "0 kayıt", "-")
        self.received_problem_card = self._build_position_mini_card("ALINAN PROBLEM", "0 kayıt", "-")
        self.issued_open_card = self._build_position_mini_card("YAZILAN AÇIK", "0 kayıt", "-")
        self.issued_closed_card = self._build_position_mini_card("YAZILAN SONUÇ", "0 kayıt", "-")
        self.issued_problem_card = self._build_position_mini_card("YAZILAN RİSK", "0 kayıt", "-")

        position_grid.addWidget(self.received_open_card, 0, 0)
        position_grid.addWidget(self.received_closed_card, 0, 1)
        position_grid.addWidget(self.received_problem_card, 0, 2)
        position_grid.addWidget(self.issued_open_card, 0, 3)
        position_grid.addWidget(self.issued_closed_card, 0, 4)
        position_grid.addWidget(self.issued_problem_card, 0, 5)

        layout.addLayout(header_row)
        layout.addLayout(profile_row)
        layout.addLayout(position_grid)

        return panel

    def _build_partner_profile_identity_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("PartnerProfileCard")
        card.setMinimumHeight(86)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 9, 12, 9)
        layout.setSpacing(3)

        self.profile_name_label = QLabel(PROFILE_EMPTY_NAME)
        self.profile_name_label.setObjectName("ProfileName")
        self.profile_name_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self.profile_meta_label = QLabel(PROFILE_EMPTY_META)
        self.profile_meta_label.setObjectName("ProfileMeta")
        self.profile_meta_label.setWordWrap(True)

        self.profile_detail_label = QLabel("Vergi No: - | Yetkili: - | Telefon: - | E-posta: -")
        self.profile_detail_label.setObjectName("ProfileField")
        self.profile_detail_label.setWordWrap(True)
        self.profile_detail_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self.profile_note_label = QLabel("Not: -")
        self.profile_note_label.setObjectName("ProfileFieldMuted")
        self.profile_note_label.setWordWrap(True)
        self.profile_note_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        layout.addWidget(self.profile_name_label)
        layout.addWidget(self.profile_meta_label)
        layout.addWidget(self.profile_detail_label)
        layout.addWidget(self.profile_note_label)

        return card

    def _build_partner_profile_risk_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("PartnerRiskCard")
        card.setMinimumHeight(86)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 9, 12, 9)
        layout.setSpacing(4)

        self.profile_risk_title_label = QLabel(PROFILE_EMPTY_RISK_TITLE)
        self.profile_risk_title_label.setObjectName("RiskTitle")

        self.profile_risk_detail_label = QLabel(PROFILE_EMPTY_RISK_DETAIL)
        self.profile_risk_detail_label.setObjectName("RiskDetail")
        self.profile_risk_detail_label.setWordWrap(True)

        layout.addWidget(self.profile_risk_title_label)
        layout.addWidget(self.profile_risk_detail_label)
        layout.addStretch(1)

        return card

    def _build_position_mini_card(self, title_text: str, value_text: str, hint_text: str) -> QFrame:
        card = QFrame()
        card.setObjectName("PositionMiniCard")
        card.setMinimumHeight(76)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(2)

        title = QLabel(title_text)
        title.setObjectName("PositionCardTitle")

        value = QLabel(value_text)
        value.setObjectName("PositionCardValue")
        value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        hint = QLabel(hint_text)
        hint.setObjectName("PositionCardHint")
        hint.setWordWrap(True)

        layout.addWidget(title)
        layout.addStretch(1)
        layout.addWidget(value)
        layout.addWidget(hint)

        card.value_label = value
        card.hint_label = hint

        return card

    def _update_permission_state(self) -> None:
        self.new_button.setEnabled(self.can_modify)
        self.edit_button.setEnabled(False)
        self.toggle_active_button.setEnabled(False)
        self.check_details_button.setEnabled(False)

        if self.can_modify:
            self.permission_label.setText(
                "Bu rol kart ekleme, düzenleme ve aktif/pasif işlemi yapabilir. "
                "Aynı ad veya vergi no engellenir; aynı telefon/e-posta için uyarı verilir."
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

        self._sort_filtered_rows()

        self._clamp_current_page()
        self._fill_table(self._current_page_rows())
        self._update_results_info()
        self._update_summary_cards()
        self._update_summary_filter_card_styles()
        self._update_pagination_controls()
        self._selection_changed()

    def _table_header_clicked(self, logical_index: int) -> None:
        if logical_index < 0 or logical_index >= self.table.columnCount():
            return

        if self.sort_column_index == logical_index:
            self.sort_order = (
                Qt.DescendingOrder
                if self.sort_order == Qt.AscendingOrder
                else Qt.AscendingOrder
            )
        else:
            self.sort_column_index = logical_index
            self.sort_order = Qt.AscendingOrder

        header = self.table.horizontalHeader()
        header.setSortIndicatorShown(True)
        header.setSortIndicator(logical_index, self.sort_order)

        self._apply_filters(reset_page=True)

    def _sort_filtered_rows(self) -> None:
        if self.sort_column_index is None:
            self.filtered_rows.sort(
                key=lambda row: (
                    not row.is_active,
                    _partner_type_sort_order(row.partner_type),
                    row.name.lower(),
                    row.id,
                )
            )
            return

        self.filtered_rows.sort(key=cmp_to_key(self._compare_partner_rows_for_current_sort))

    def _compare_partner_rows_for_current_sort(
        self,
        left_row: BusinessPartnerRow,
        right_row: BusinessPartnerRow,
    ) -> int:
        column_index = self.sort_column_index

        if column_index is None:
            return 0

        left_value = self._sort_value_for_column(left_row, column_index)
        right_value = self._sort_value_for_column(right_row, column_index)

        left_empty = left_value in {None, ""}
        right_empty = right_value in {None, ""}

        if left_empty and not right_empty:
            return 1

        if right_empty and not left_empty:
            return -1

        if left_empty and right_empty:
            return self._compare_default_partner_order(left_row, right_row)

        if left_value < right_value:
            result = -1
        elif left_value > right_value:
            result = 1
        else:
            result = self._compare_default_partner_order(left_row, right_row)

        if self.sort_order == Qt.DescendingOrder and result != 0:
            result = -result

        return result

    def _compare_default_partner_order(
        self,
        left_row: BusinessPartnerRow,
        right_row: BusinessPartnerRow,
    ) -> int:
        left_default = (not left_row.is_active, left_row.name.lower(), left_row.id)
        right_default = (not right_row.is_active, right_row.name.lower(), right_row.id)

        if left_default < right_default:
            return -1

        if left_default > right_default:
            return 1

        return 0

    def _sort_value_for_column(self, row: BusinessPartnerRow, column_index: int) -> Any:
        if column_index == 0:
            return row.id

        if column_index == 1:
            return row.name.lower()

        if column_index == 2:
            return _partner_type_sort_order(row.partner_type)

        if column_index == 3:
            return _normalize_sort_text(row.tax_number)

        if column_index == 4:
            return _normalize_sort_text(row.tax_office)

        if column_index == 5:
            return _normalize_sort_text(row.authorized_person)

        if column_index == 6:
            return _normalize_sort_text(row.phone)

        if column_index == 7:
            return _normalize_sort_text(row.email)

        if column_index == 8:
            return 0 if row.is_active else 1

        if column_index == 9:
            return _normalize_sort_text(row.notes)

        return row.id

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
                    item.setForeground(QColor("#64748b"))
                    item.setBackground(QColor("#0b1120"))

                    if column_index == 8:
                        item.setForeground(QColor("#fca5a5"))
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

        for row_index in range(self.table.rowCount()):
            if self.table.rowHeight(row_index) > 44:
                self.table.setRowHeight(row_index, 44)

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

    def _update_summary_filter_card_styles(self) -> None:
        selected_type = str(self.type_filter_combo.currentData() or "ALL")

        for card in [
            self.total_count_card,
            self.customer_count_card,
            self.supplier_count_card,
            self.both_count_card,
            self.other_count_card,
        ]:
            card_filter_value = str(getattr(card, "summary_filter_value", ""))
            card.setObjectName(
                "CardActiveFilter"
                if card_filter_value == selected_type
                else "Card"
            )
            card.style().unpolish(card)
            card.style().polish(card)
            card.update()

    def _update_pagination_controls(self) -> None:
        total_page_count = self._total_page_count()

        self.previous_page_button.setEnabled(self.current_page_index > 0)
        self.next_page_button.setEnabled(self.current_page_index < total_page_count - 1)

        self.page_info_label.setText(
            f"Sayfa {self.current_page_index + 1} / {total_page_count}"
        )

    def _selected_partner_id(self) -> int | None:
        selection_model = self.table.selectionModel()

        if selection_model is None or not selection_model.hasSelection():
            return None

        selected_rows = selection_model.selectedRows()

        if selected_rows:
            current_row = selected_rows[0].row()
        else:
            selected_indexes = selection_model.selectedIndexes()

            if not selected_indexes:
                return None

            current_row = selected_indexes[0].row()

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

    def _open_check_details_from_table_double_click(self, item: QTableWidgetItem) -> None:
        if item is None:
            return

        self.table.selectRow(item.row())
        self._open_selected_partner_check_details()

    def _open_table_context_menu(self, position) -> None:
        row_index = self.table.rowAt(position.y())

        if row_index < 0:
            return

        self.table.selectRow(row_index)
        selected_row = self._selected_partner_row()

        if selected_row is None:
            return

        menu = QMenu(self)
        menu.setStyleSheet(
            """
            QMenu {
                background-color: #111827;
                color: #e5e7eb;
                border: 1px solid #334155;
                border-radius: 10px;
                padding: 6px;
            }
            QMenu::item {
                padding: 8px 24px 8px 12px;
                border-radius: 8px;
            }
            QMenu::item:selected {
                background-color: #2563eb;
                color: #ffffff;
            }
            QMenu::item:disabled {
                color: #64748b;
            }
            """
        )

        check_details_action = menu.addAction("Çek Detayları")
        edit_action = menu.addAction("Düzenle")
        edit_action.setEnabled(self.can_modify)
        menu.addSeparator()

        toggle_text = "Pasife Al" if selected_row.is_active else "Aktife Al"
        toggle_action = menu.addAction(toggle_text)
        toggle_action.setEnabled(self.can_modify)

        selected_action = menu.exec(self.table.viewport().mapToGlobal(position))

        if selected_action == check_details_action:
            self._open_selected_partner_check_details()
        elif selected_action == edit_action:
            self._open_edit_dialog()
        elif selected_action == toggle_action:
            self._toggle_selected_partner_active_state()

    def _selection_changed(self) -> None:
        selected_row = self._selected_partner_row()
        has_selection = selected_row is not None

        self.edit_button.setEnabled(self.can_modify and has_selection)
        self.toggle_active_button.setEnabled(self.can_modify and has_selection)
        self.check_details_button.setEnabled(has_selection)

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

        self._update_selected_partner_position_summary(selected_row)

    def _open_selected_partner_check_details(self) -> None:
        selected_row = self._selected_partner_row()

        if selected_row is None:
            QMessageBox.information(
                self,
                "Seçim gerekli",
                "Çek detaylarını görmek için bir müşteri / tedarikçi kartı seçmelisin.",
            )
            return

        dialog = BusinessPartnerChecksDetailDialog(
            parent=self,
            partner_row=selected_row,
        )
        dialog.exec()

    def _clear_position_summary(self) -> None:
        self.position_title_label.setText(POSITION_EMPTY_TITLE)
        self.position_subtitle_label.setText(POSITION_EMPTY_SUBTITLE)
        self._clear_partner_profile()

        for card in [
            self.received_open_card,
            self.received_closed_card,
            self.received_problem_card,
            self.issued_open_card,
            self.issued_closed_card,
            self.issued_problem_card,
        ]:
            card.value_label.setText(POSITION_EMPTY_CARD_VALUE)
            card.hint_label.setText(POSITION_EMPTY_CARD_HINT)
            card.setToolTip(POSITION_EMPTY_SUBTITLE)
            card.value_label.setToolTip(POSITION_EMPTY_SUBTITLE)
            card.hint_label.setToolTip(POSITION_EMPTY_SUBTITLE)

    def _clear_partner_profile(self) -> None:
        self.profile_name_label.setText(PROFILE_EMPTY_NAME)
        self.profile_meta_label.setText(PROFILE_EMPTY_META)
        self.profile_detail_label.setText("Vergi No: - | Yetkili: - | Telefon: - | E-posta: -")
        self.profile_note_label.setText("Not: -")
        self.profile_risk_title_label.setText(PROFILE_EMPTY_RISK_TITLE)
        self.profile_risk_detail_label.setText(PROFILE_EMPTY_RISK_DETAIL)

        self.profile_identity_card.setToolTip(PROFILE_EMPTY_META)
        self.profile_risk_card.setToolTip(PROFILE_EMPTY_RISK_DETAIL)

    def _update_selected_partner_position_summary(self, selected_row: BusinessPartnerRow | None) -> None:
        if selected_row is None:
            self._clear_position_summary()
            return

        position = self._load_partner_position_summary(selected_row.id)

        partner_type_text = business_partner_type_text(selected_row.partner_type)
        partner_status_text = "Aktif" if selected_row.is_active else "Pasif"

        self.position_title_label.setText(
            f"Seçili Muhatap: {selected_row.name} / {partner_type_text} / {partner_status_text}"
        )
        self.position_subtitle_label.setText(
            "Bu özet cari bakiye değildir; yalnız bu muhatapla bağlantılı alınan/yazılan çek pozisyonunu gösterir."
        )

        self._update_partner_profile(selected_row, position)

        self._set_position_card(self.received_open_card, position["received_open"])
        self._set_position_card(self.received_closed_card, position["received_closed"])
        self._set_position_card(self.received_problem_card, position["received_problem"])
        self._set_position_card(self.issued_open_card, position["issued_open"])
        self._set_position_card(self.issued_closed_card, position["issued_closed"])
        self._set_position_card(self.issued_problem_card, position["issued_problem"])

    def _update_partner_profile(
        self,
        selected_row: BusinessPartnerRow,
        position: dict[str, PartnerPositionBucket],
    ) -> None:
        partner_type_text = business_partner_type_text(selected_row.partner_type)
        partner_status_text = "Aktif" if selected_row.is_active else "Pasif"

        self.profile_name_label.setText(selected_row.name)
        self.profile_meta_label.setText(
            f"Kart ID: {selected_row.id} • {partner_type_text} • {partner_status_text}"
        )
        self.profile_detail_label.setText(
            f"Vergi No: {_format_optional_text(selected_row.tax_number)} | "
            f"Vergi Dairesi: {_format_optional_text(selected_row.tax_office)} | "
            f"Yetkili: {_format_optional_text(selected_row.authorized_person)} | "
            f"Telefon: {_format_optional_text(selected_row.phone)} | "
            f"E-posta: {_format_optional_text(selected_row.email)}"
        )
        self.profile_note_label.setText(f"Not: {_format_optional_text(selected_row.notes)}")

        risk_title, risk_detail = self._build_partner_risk_summary(selected_row, position)
        self.profile_risk_title_label.setText(risk_title)
        self.profile_risk_detail_label.setText(risk_detail)

        tooltip_text = (
            f"{selected_row.name}\n"
            f"Tip: {partner_type_text}\n"
            f"Durum: {partner_status_text}\n"
            f"Vergi No: {_format_optional_text(selected_row.tax_number)}\n"
            f"Vergi Dairesi: {_format_optional_text(selected_row.tax_office)}\n"
            f"Yetkili: {_format_optional_text(selected_row.authorized_person)}\n"
            f"Telefon: {_format_optional_text(selected_row.phone)}\n"
            f"E-posta: {_format_optional_text(selected_row.email)}\n"
            f"Adres: {_format_optional_text(selected_row.address)}\n"
            f"Not: {_format_optional_text(selected_row.notes)}"
        )

        self.profile_identity_card.setToolTip(tooltip_text)
        self.profile_risk_card.setToolTip(risk_detail)

    def _build_partner_risk_summary(
        self,
        selected_row: BusinessPartnerRow,
        position: dict[str, PartnerPositionBucket],
    ) -> tuple[str, str]:
        received_open_count = position["received_open"].count
        received_problem_count = position["received_problem"].count
        issued_open_count = position["issued_open"].count
        issued_problem_count = position["issued_problem"].count
        total_position_count = sum(bucket.count for bucket in position.values())

        if not selected_row.is_active:
            return (
                "Pasif Muhatap",
                "Bu kart pasif durumda. Geçmiş çeklerde görünür; yeni işlemlerde dikkatli kullanılmalı.",
            )

        if received_problem_count > 0 or issued_problem_count > 0:
            return (
                "Problemli Çek Var",
                f"Alınan problemli: {received_problem_count} kayıt | Yazılan riskli: {issued_problem_count} kayıt.",
            )

        if received_open_count > 0 or issued_open_count > 0:
            return (
                "Açık Pozisyon Var",
                f"Alınan açık: {received_open_count} kayıt | Yazılan açık: {issued_open_count} kayıt.",
            )

        if total_position_count > 0:
            return (
                "Geçmiş Hareket Var",
                "Bu muhatapta açık/problemli çek yok; sonuçlanmış çek geçmişi bulunuyor.",
            )

        return (
            "Çek Hareketi Yok",
            "Bu muhatapla bağlantılı alınan veya yazılan çek kaydı bulunmuyor.",
        )

    def _set_position_card(self, card: QFrame, bucket: PartnerPositionBucket) -> None:
        value_text, hint_text = _format_position_bucket(bucket)
        tooltip_text = _format_position_bucket_tooltip(bucket)

        card.value_label.setText(value_text)
        card.hint_label.setText(hint_text)
        card.setToolTip(tooltip_text)
        card.value_label.setToolTip(tooltip_text)
        card.hint_label.setToolTip(tooltip_text)

    def _load_partner_position_summary(self, partner_id: int) -> dict[str, PartnerPositionBucket]:
        buckets: dict[str, PartnerPositionBucket] = {
            "received_open": _empty_position_bucket(),
            "received_closed": _empty_position_bucket(),
            "received_problem": _empty_position_bucket(),
            "issued_open": _empty_position_bucket(),
            "issued_closed": _empty_position_bucket(),
            "issued_problem": _empty_position_bucket(),
        }

        with session_scope() as session:
            received_checks = list(
                session.execute(
                    select(ReceivedCheck).where(ReceivedCheck.customer_id == partner_id)
                ).scalars().all()
            )

            issued_checks = list(
                session.execute(
                    select(IssuedCheck).where(IssuedCheck.supplier_id == partner_id)
                ).scalars().all()
            )

            for received_check in received_checks:
                status = _enum_value(received_check.status)
                currency_code = _enum_value(received_check.currency_code) or "TRY"
                amount = Decimal(str(received_check.amount or "0.00")).quantize(Decimal("0.01"))

                if status in RECEIVED_OPEN_STATUSES:
                    _add_amount_to_bucket(buckets, "received_open", amount, currency_code)
                elif status in RECEIVED_PROBLEM_STATUSES:
                    _add_amount_to_bucket(buckets, "received_problem", amount, currency_code)
                elif status in RECEIVED_CLOSED_STATUSES:
                    _add_amount_to_bucket(buckets, "received_closed", amount, currency_code)

            for issued_check in issued_checks:
                status = _enum_value(issued_check.status)
                currency_code = _enum_value(issued_check.currency_code) or "TRY"
                amount = Decimal(str(issued_check.amount or "0.00")).quantize(Decimal("0.01"))

                if status in ISSUED_OPEN_STATUSES:
                    _add_amount_to_bucket(buckets, "issued_open", amount, currency_code)
                elif status in ISSUED_PROBLEM_STATUSES:
                    _add_amount_to_bucket(buckets, "issued_problem", amount, currency_code)
                elif status in ISSUED_CLOSED_STATUSES:
                    _add_amount_to_bucket(buckets, "issued_closed", amount, currency_code)

        return buckets

    def _find_duplicate_name(
        self,
        *,
        session,
        name: str,
        exclude_partner_id: int | None,
    ) -> BusinessPartner | None:
        normalized_name = _normalize_duplicate_text(name)

        statement = select(BusinessPartner).where(
            func.lower(func.trim(BusinessPartner.name)) == normalized_name
        )

        if exclude_partner_id is not None:
            statement = statement.where(BusinessPartner.id != exclude_partner_id)

        return session.execute(statement).scalar_one_or_none()

    def _find_duplicate_tax_number(
        self,
        *,
        session,
        tax_number: str | None,
        exclude_partner_id: int | None,
    ) -> BusinessPartner | None:
        normalized_tax_number = _normalize_duplicate_text(tax_number)

        if not normalized_tax_number:
            return None

        statement = select(BusinessPartner).where(
            func.lower(func.trim(BusinessPartner.tax_number)) == normalized_tax_number
        )

        if exclude_partner_id is not None:
            statement = statement.where(BusinessPartner.id != exclude_partner_id)

        return session.execute(statement).scalar_one_or_none()

    def _validate_hard_duplicates(
        self,
        *,
        payload: dict[str, Any],
        exclude_partner_id: int | None,
    ) -> None:
        with session_scope() as session:
            duplicate_name = self._find_duplicate_name(
                session=session,
                name=payload["name"],
                exclude_partner_id=exclude_partner_id,
            )

            if duplicate_name is not None:
                raise ValueError(
                    f"Bu ad / ünvan ile zaten bir kart var. Mevcut Kart ID: {duplicate_name.id}"
                )

            duplicate_tax_number = self._find_duplicate_tax_number(
                session=session,
                tax_number=payload["tax_number"],
                exclude_partner_id=exclude_partner_id,
            )

            if duplicate_tax_number is not None:
                raise ValueError(
                    f"Bu vergi no / kimlik no başka bir kartta kullanılmış. "
                    f"Kayıt yapılamaz. Mevcut Kart ID: {duplicate_tax_number.id}"
                )

    def _find_soft_duplicate_rows(
        self,
        *,
        payload: dict[str, Any],
        exclude_partner_id: int | None,
    ) -> list[dict[str, Any]]:
        warnings: list[dict[str, Any]] = []

        normalized_phone = _normalize_duplicate_text(payload.get("phone"))
        normalized_email = _normalize_duplicate_text(payload.get("email"))

        if not normalized_phone and not normalized_email:
            return warnings

        with session_scope() as session:
            if normalized_phone:
                phone_statement = select(BusinessPartner).where(
                    func.lower(func.trim(BusinessPartner.phone)) == normalized_phone
                )

                if exclude_partner_id is not None:
                    phone_statement = phone_statement.where(BusinessPartner.id != exclude_partner_id)

                phone_matches = list(session.execute(phone_statement).scalars().all())

                for partner in phone_matches:
                    warnings.append(
                        {
                            "field": "Telefon",
                            "value": payload.get("phone"),
                            "partner_id": partner.id,
                            "partner_name": partner.name,
                            "partner_type": business_partner_type_text(partner.partner_type),
                            "is_active": bool(partner.is_active),
                        }
                    )

            if normalized_email:
                email_statement = select(BusinessPartner).where(
                    func.lower(func.trim(BusinessPartner.email)) == normalized_email
                )

                if exclude_partner_id is not None:
                    email_statement = email_statement.where(BusinessPartner.id != exclude_partner_id)

                email_matches = list(session.execute(email_statement).scalars().all())

                for partner in email_matches:
                    warnings.append(
                        {
                            "field": "E-posta",
                            "value": payload.get("email"),
                            "partner_id": partner.id,
                            "partner_name": partner.name,
                            "partner_type": business_partner_type_text(partner.partner_type),
                            "is_active": bool(partner.is_active),
                        }
                    )

        return warnings

    def _confirm_soft_duplicates(
        self,
        *,
        payload: dict[str, Any],
        exclude_partner_id: int | None,
    ) -> bool:
        warnings = self._find_soft_duplicate_rows(
            payload=payload,
            exclude_partner_id=exclude_partner_id,
        )

        if not warnings:
            return True

        warning_lines = [
            "Bu kayıt bazı bilgiler açısından mevcut kartlara benziyor:",
            "",
        ]

        for warning in warnings:
            warning_lines.append(
                f"- {warning['field']}: {warning['value']} | "
                f"Kart ID: {warning['partner_id']} | "
                f"{warning['partner_name']} | "
                f"{warning['partner_type']} | "
                f"{'Aktif' if warning['is_active'] else 'Pasif'}"
            )

        warning_lines.extend(
            [
                "",
                "Bu bir mükerrer kayıt olabilir.",
                "Yine de devam etmek istiyor musun?",
            ]
        )

        answer = QMessageBox.question(
            self,
            "Benzer kayıt uyarısı",
            "\n".join(warning_lines),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        return answer == QMessageBox.Yes

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
            self._validate_hard_duplicates(payload=payload, exclude_partner_id=None)
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Mükerrer kayıt engellendi",
                str(exc),
            )
            return

        if not self._confirm_soft_duplicates(payload=payload, exclude_partner_id=None):
            return

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
            self._validate_hard_duplicates(payload=payload, exclude_partner_id=selected_row.id)
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Mükerrer kayıt engellendi",
                str(exc),
            )
            return

        if not self._confirm_soft_duplicates(payload=payload, exclude_partner_id=selected_row.id):
            return

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
            duplicate_name = self._find_duplicate_name(
                session=session,
                name=payload["name"],
                exclude_partner_id=None,
            )

            if duplicate_name is not None:
                raise ValueError(
                    f"Bu ad / ünvan ile zaten bir kart var. Mevcut Kart ID: {duplicate_name.id}"
                )

            duplicate_tax_number = self._find_duplicate_tax_number(
                session=session,
                tax_number=payload["tax_number"],
                exclude_partner_id=None,
            )

            if duplicate_tax_number is not None:
                raise ValueError(
                    f"Bu vergi no / kimlik no başka bir kartta kullanılmış. "
                    f"Kayıt yapılamaz. Mevcut Kart ID: {duplicate_tax_number.id}"
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

            duplicate_name = self._find_duplicate_name(
                session=session,
                name=payload["name"],
                exclude_partner_id=partner_id,
            )

            if duplicate_name is not None:
                raise ValueError(
                    f"Bu ad / ünvan ile başka bir kart var. Mevcut Kart ID: {duplicate_name.id}"
                )

            duplicate_tax_number = self._find_duplicate_tax_number(
                session=session,
                tax_number=payload["tax_number"],
                exclude_partner_id=partner_id,
            )

            if duplicate_tax_number is not None:
                raise ValueError(
                    f"Bu vergi no / kimlik no başka bir kartta kullanılmış. "
                    f"Kayıt yapılamaz. Mevcut Kart ID: {duplicate_tax_number.id}"
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