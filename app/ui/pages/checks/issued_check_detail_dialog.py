from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy import select
from sqlalchemy.orm import aliased

from app.db.session import session_scope
from app.models.bank import Bank, BankAccount
from app.models.bank_transaction import BankTransaction
from app.models.business_partner import BusinessPartner
from app.models.check import IssuedCheck
from app.models.user import User
from app.ui.pages.banks.bank_dialog_styles import BANK_DIALOG_STYLES
from app.ui.pages.checks.checks_data import format_currency_amount, issued_status_text


@dataclass(frozen=True)
class IssuedCheckDetailData:
    issued_check_id: int
    supplier_name: str
    bank_name: str
    bank_account_name: str
    check_number: str
    issue_date: date
    due_date: date
    amount: Decimal
    currency_code: str
    status: str
    reference_no: str | None
    description: str | None
    created_by_text: str | None
    created_at: datetime | None
    updated_at: datetime | None
    paid_transaction_id: int | None
    paid_transaction_date: date | None
    paid_transaction_reference_no: str | None
    paid_transaction_description: str | None
    cancelled_by_text: str | None
    cancelled_at: datetime | None
    cancel_reason: str | None


@dataclass(frozen=True)
class IssuedCheckDetailResult:
    check: IssuedCheckDetailData | None
    error_message: str | None = None


def _enum_value(value: Any) -> str:
    if value is None:
        return ""

    if hasattr(value, "value"):
        return str(value.value)

    return str(value).strip().upper()


def _format_date(value: date | None) -> str:
    if value is None:
        return "-"

    return value.strftime("%d.%m.%Y")


def _format_datetime(value: datetime | None) -> str:
    if value is None:
        return "-"

    return value.strftime("%d.%m.%Y %H:%M")


def _format_optional_text(value: str | None) -> str:
    cleaned_value = str(value or "").strip()

    if not cleaned_value:
        return "-"

    return cleaned_value


def _user_display_text(user: User | None) -> str | None:
    if user is None:
        return None

    full_name = str(getattr(user, "full_name", "") or "").strip()
    username = str(getattr(user, "username", "") or "").strip()

    if full_name and username:
        return f"{full_name} ({username})"

    if full_name:
        return full_name

    if username:
        return username

    return f"Kullanıcı ID: {user.id}"


class IssuedCheckDetailDialog(QDialog):
    def __init__(self, *, issued_check_id: int, parent: QWidget | None) -> None:
        super().__init__(parent)

        self.issued_check_id = issued_check_id
        self.detail_result = self._load_detail_data(issued_check_id)

        self.setWindowTitle("Yazılan Çek Detayı")
        self.resize(1080, 700)
        self.setMinimumSize(920, 600)
        self.setSizeGripEnabled(True)
        self.setStyleSheet(
            BANK_DIALOG_STYLES
            + """
            QScrollArea {
                background-color: #0f172a;
                border: none;
            }

            QScrollArea > QWidget > QWidget {
                background-color: #0f172a;
            }

            QWidget#DialogContent {
                background-color: #0f172a;
            }

            QFrame#InfoCard {
                background-color: #111827;
                border: 1px solid #1e293b;
                border-radius: 14px;
            }

            QFrame#WarningCard {
                background-color: rgba(127, 29, 29, 0.35);
                border: 1px solid #ef4444;
                border-radius: 14px;
            }

            QFrame#PaidCard {
                background-color: rgba(20, 83, 45, 0.30);
                border: 1px solid #22c55e;
                border-radius: 14px;
            }

            QFrame#CancelCard {
                background-color: rgba(127, 29, 29, 0.24);
                border: 1px solid #f87171;
                border-radius: 14px;
            }

            QLabel#InfoTitle {
                color: #93c5fd;
                font-size: 12px;
                font-weight: 700;
            }

            QLabel#InfoValue {
                color: #f8fafc;
                font-size: 14px;
                font-weight: 700;
            }
            """
        )

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.NoFrame)

        content_widget = QWidget()
        content_widget.setObjectName("DialogContent")

        main_layout = QVBoxLayout(content_widget)
        main_layout.setContentsMargins(24, 22, 24, 22)
        main_layout.setSpacing(16)

        title = QLabel("Yazılan Çek Detayı")
        title.setObjectName("SectionTitle")

        subtitle = QLabel(
            "Seçilen yazılan çekin ana bilgileri, ödeme durumu ve iptal bilgileri bu ekranda gösterilir. "
            "Bu ekran sadece görüntüleme amaçlıdır; kayıt değiştirme işlemi yapmaz."
        )
        subtitle.setObjectName("MutedText")
        subtitle.setWordWrap(True)

        main_layout.addWidget(title)
        main_layout.addWidget(subtitle)

        if self.detail_result.error_message:
            main_layout.addWidget(self._build_warning_card(self.detail_result.error_message))
        elif self.detail_result.check is None:
            main_layout.addWidget(self._build_warning_card("Yazılan çek kaydı bulunamadı."))
        else:
            main_layout.addWidget(self._build_check_summary_card())

            if self.detail_result.check.paid_transaction_id is not None:
                main_layout.addWidget(self._build_paid_info_card())

            if self.detail_result.check.status == "CANCELLED":
                main_layout.addWidget(self._build_cancel_info_card())

        close_row = QHBoxLayout()
        close_row.addStretch(1)

        close_button = QPushButton("Kapat")
        close_button.setMinimumHeight(40)
        close_button.clicked.connect(self.accept)

        close_row.addWidget(close_button)
        main_layout.addLayout(close_row)

        scroll_area.setWidget(content_widget)
        outer_layout.addWidget(scroll_area)

    def _load_detail_data(self, issued_check_id: int) -> IssuedCheckDetailResult:
        try:
            with session_scope() as session:
                paid_transaction_alias = aliased(BankTransaction)
                created_by_user_alias = aliased(User)
                cancelled_by_user_alias = aliased(User)

                statement = (
                    select(
                        IssuedCheck,
                        BusinessPartner,
                        BankAccount,
                        Bank,
                        paid_transaction_alias,
                        created_by_user_alias,
                        cancelled_by_user_alias,
                    )
                    .join(BusinessPartner, IssuedCheck.supplier_id == BusinessPartner.id)
                    .join(BankAccount, IssuedCheck.bank_account_id == BankAccount.id)
                    .join(Bank, BankAccount.bank_id == Bank.id)
                    .outerjoin(
                        paid_transaction_alias,
                        IssuedCheck.paid_transaction_id == paid_transaction_alias.id,
                    )
                    .outerjoin(
                        created_by_user_alias,
                        IssuedCheck.created_by_user_id == created_by_user_alias.id,
                    )
                    .outerjoin(
                        cancelled_by_user_alias,
                        IssuedCheck.cancelled_by_user_id == cancelled_by_user_alias.id,
                    )
                    .where(IssuedCheck.id == issued_check_id)
                )

                row = session.execute(statement).one_or_none()

                if row is None:
                    return IssuedCheckDetailResult(check=None, error_message=None)

                (
                    issued_check,
                    supplier,
                    bank_account,
                    bank,
                    paid_transaction,
                    created_by_user,
                    cancelled_by_user,
                ) = row

                paid_transaction_date = None
                paid_transaction_reference_no = None
                paid_transaction_description = None

                if paid_transaction is not None:
                    paid_transaction_date = paid_transaction.transaction_date
                    paid_transaction_reference_no = paid_transaction.reference_no
                    paid_transaction_description = paid_transaction.description

                detail = IssuedCheckDetailData(
                    issued_check_id=issued_check.id,
                    supplier_name=supplier.name,
                    bank_name=bank.name,
                    bank_account_name=bank_account.account_name,
                    check_number=issued_check.check_number,
                    issue_date=issued_check.issue_date,
                    due_date=issued_check.due_date,
                    amount=Decimal(str(issued_check.amount)),
                    currency_code=_enum_value(issued_check.currency_code),
                    status=_enum_value(issued_check.status),
                    reference_no=issued_check.reference_no,
                    description=issued_check.description,
                    created_by_text=_user_display_text(created_by_user),
                    created_at=issued_check.created_at,
                    updated_at=issued_check.updated_at,
                    paid_transaction_id=issued_check.paid_transaction_id,
                    paid_transaction_date=paid_transaction_date,
                    paid_transaction_reference_no=paid_transaction_reference_no,
                    paid_transaction_description=paid_transaction_description,
                    cancelled_by_text=_user_display_text(cancelled_by_user),
                    cancelled_at=issued_check.cancelled_at,
                    cancel_reason=issued_check.cancel_reason,
                )

                return IssuedCheckDetailResult(check=detail, error_message=None)

        except Exception as exc:
            return IssuedCheckDetailResult(check=None, error_message=str(exc))

    def _build_warning_card(self, message: str) -> QWidget:
        card = QFrame()
        card.setObjectName("WarningCard")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(8)

        title = QLabel("Detay bilgisi okunamadı")
        title.setObjectName("SectionTitle")

        body = QLabel(message)
        body.setObjectName("MutedText")
        body.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(body)

        return card

    def _build_check_summary_card(self) -> QWidget:
        check = self.detail_result.check

        card = QFrame()
        card.setObjectName("InfoCard")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        title = QLabel("Çek Ana Bilgileri")
        title.setObjectName("SectionTitle")

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(12)

        grid.addWidget(self._build_info_box("Çek ID", str(check.issued_check_id)), 0, 0)
        grid.addWidget(self._build_info_box("Tedarikçi", check.supplier_name), 0, 1)
        grid.addWidget(self._build_info_box("Çek No", check.check_number), 0, 2)
        grid.addWidget(self._build_info_box("Durum", issued_status_text(check.status)), 0, 3)

        grid.addWidget(self._build_info_box("Banka", check.bank_name), 1, 0)
        grid.addWidget(self._build_info_box("Banka Hesabı", check.bank_account_name), 1, 1)
        grid.addWidget(self._build_info_box("Keşide Tarihi", _format_date(check.issue_date)), 1, 2)
        grid.addWidget(self._build_info_box("Vade Tarihi", _format_date(check.due_date)), 1, 3)

        grid.addWidget(
            self._build_info_box(
                "Tutar",
                format_currency_amount(check.amount, check.currency_code),
            ),
            2,
            0,
        )
        grid.addWidget(self._build_info_box("Para Birimi", check.currency_code), 2, 1)
        grid.addWidget(self._build_info_box("Referans No", _format_optional_text(check.reference_no)), 2, 2)
        grid.addWidget(self._build_info_box("Oluşturan", _format_optional_text(check.created_by_text)), 2, 3)

        grid.addWidget(self._build_info_box("Açıklama", _format_optional_text(check.description)), 3, 0, 1, 2)
        grid.addWidget(self._build_info_box("Oluşturma", _format_datetime(check.created_at)), 3, 2)
        grid.addWidget(self._build_info_box("Son Güncelleme", _format_datetime(check.updated_at)), 3, 3)

        layout.addWidget(title)
        layout.addLayout(grid)

        return card

    def _build_paid_info_card(self) -> QWidget:
        check = self.detail_result.check

        card = QFrame()
        card.setObjectName("PaidCard")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        title = QLabel("Ödeme Bilgisi")
        title.setObjectName("SectionTitle")

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(12)

        grid.addWidget(
            self._build_info_box(
                "Banka Hareket ID",
                str(check.paid_transaction_id) if check.paid_transaction_id is not None else "-",
            ),
            0,
            0,
        )
        grid.addWidget(
            self._build_info_box(
                "Ödeme Tarihi",
                _format_date(check.paid_transaction_date),
            ),
            0,
            1,
        )
        grid.addWidget(
            self._build_info_box(
                "Referans No",
                _format_optional_text(check.paid_transaction_reference_no),
            ),
            0,
            2,
        )
        grid.addWidget(
            self._build_info_box(
                "Açıklama",
                _format_optional_text(check.paid_transaction_description),
            ),
            0,
            3,
        )

        layout.addWidget(title)
        layout.addLayout(grid)

        return card

    def _build_cancel_info_card(self) -> QWidget:
        check = self.detail_result.check

        card = QFrame()
        card.setObjectName("CancelCard")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        title = QLabel("İptal Bilgisi")
        title.setObjectName("SectionTitle")

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(12)

        grid.addWidget(self._build_info_box("İptal Eden", _format_optional_text(check.cancelled_by_text)), 0, 0)
        grid.addWidget(self._build_info_box("İptal Zamanı", _format_datetime(check.cancelled_at)), 0, 1)
        grid.addWidget(self._build_info_box("İptal Nedeni", _format_optional_text(check.cancel_reason)), 0, 2, 1, 2)

        layout.addWidget(title)
        layout.addLayout(grid)

        return card

    def _build_info_box(self, title_text: str, value_text: str) -> QWidget:
        box = QFrame()
        box.setObjectName("InfoCard")

        layout = QVBoxLayout(box)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(3)

        title = QLabel(title_text)
        title.setObjectName("InfoTitle")

        value = QLabel(value_text)
        value.setObjectName("InfoValue")
        value.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(value)

        return box