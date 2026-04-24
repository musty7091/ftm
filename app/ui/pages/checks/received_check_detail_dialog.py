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
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy import select
from sqlalchemy.orm import aliased

from app.db.session import session_scope
from app.models.bank import Bank, BankAccount
from app.models.business_partner import BusinessPartner
from app.models.check import ReceivedCheck, ReceivedCheckMovement
from app.models.user import User
from app.ui.pages.banks.bank_dialog_styles import BANK_DIALOG_STYLES
from app.ui.pages.checks.checks_data import format_currency_amount, received_status_text


@dataclass(frozen=True)
class ReceivedCheckMainDetail:
    received_check_id: int
    customer_name: str
    drawer_bank_name: str
    drawer_branch_name: str | None
    collection_bank_name: str | None
    collection_bank_account_name: str | None
    check_number: str
    received_date: date
    due_date: date
    amount: Decimal
    currency_code: str
    status: str
    reference_no: str | None
    description: str | None
    created_at: datetime | None
    updated_at: datetime | None


@dataclass(frozen=True)
class ReceivedCheckMovementDetail:
    movement_id: int
    movement_type: str
    movement_date: date
    from_status: str | None
    to_status: str
    bank_name: str | None
    bank_account_name: str | None
    counterparty_text: str | None
    purpose_text: str | None
    reference_no: str | None
    description: str | None
    gross_amount: Decimal
    currency_code: str
    discount_rate: Decimal | None
    discount_expense_amount: Decimal | None
    net_bank_amount: Decimal | None
    created_by_text: str | None
    created_at: datetime | None


@dataclass(frozen=True)
class ReceivedCheckDetailData:
    check: ReceivedCheckMainDetail | None
    movements: list[ReceivedCheckMovementDetail]
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


def _format_rate(value: Decimal | None) -> str:
    if value is None:
        return "-"

    try:
        rate_value = Decimal(str(value))
    except Exception:
        return "-"

    formatted = f"{rate_value:,.4f}"
    formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")
    formatted = formatted.rstrip("0").rstrip(",")

    return f"%{formatted}"


def _format_optional_currency_amount(value: Decimal | None, currency_code: str) -> str:
    if value is None:
        return "-"

    return format_currency_amount(value, currency_code)


def _movement_type_text(movement_type: str) -> str:
    normalized_movement_type = str(movement_type or "").strip().upper()

    if normalized_movement_type == "REGISTERED":
        return "Çek Kaydı Oluşturuldu"

    if normalized_movement_type == "SENT_TO_BANK_COLLECTION":
        return "Bankaya Tahsile Verildi"

    if normalized_movement_type == "MARKED_IN_COLLECTION":
        return "Tahsile Alındı"

    if normalized_movement_type == "COLLECTED":
        return "Tahsil Edildi"

    if normalized_movement_type == "ENDORSED":
        return "Ciro Edildi"

    if normalized_movement_type == "DISCOUNTED":
        return "İskontoya Verildi"

    if normalized_movement_type == "BOUNCED":
        return "Karşılıksız"

    if normalized_movement_type == "RETURNED":
        return "İade"

    if normalized_movement_type == "CANCELLED":
        return "İptal"

    if normalized_movement_type == "REVERSED":
        return "Ters Kayıt / Geri Alma"

    return normalized_movement_type


def _bank_account_text(bank_name: str | None, account_name: str | None) -> str:
    if bank_name and account_name:
        return f"{bank_name} / {account_name}"

    if account_name:
        return account_name

    if bank_name:
        return bank_name

    return "-"


class ReceivedCheckDetailDialog(QDialog):
    def __init__(self, *, received_check_id: int, parent: QWidget | None) -> None:
        super().__init__(parent)

        self.received_check_id = received_check_id
        self.detail_data = self._load_detail_data(received_check_id)

        self.setWindowTitle("Alınan Çek Detayı / Hareket Geçmişi")
        self.resize(1220, 760)
        self.setMinimumSize(1040, 650)
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

            QTableWidget {
                background-color: #0b1220;
                color: #e5e7eb;
                border: 1px solid #1e293b;
                border-radius: 12px;
                gridline-color: #1e293b;
                selection-background-color: #2563eb;
                selection-color: #ffffff;
            }

            QTableWidget::item {
                padding: 6px;
                border-bottom: 1px solid #1e293b;
            }

            QHeaderView::section {
                background-color: #1e293b;
                color: #e5e7eb;
                border: none;
                padding: 8px;
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

        title = QLabel("Alınan Çek Detayı / Hareket Geçmişi")
        title.setObjectName("SectionTitle")

        subtitle = QLabel(
            "Seçilen alınan çekin ana bilgileri ve bugüne kadar oluşan tüm hareketleri bu ekranda listelenir. "
            "Bu ekran sadece görüntüleme amaçlıdır; kayıt değiştirme işlemi yapmaz."
        )
        subtitle.setObjectName("MutedText")
        subtitle.setWordWrap(True)

        main_layout.addWidget(title)
        main_layout.addWidget(subtitle)

        if self.detail_data.error_message:
            main_layout.addWidget(self._build_warning_card(self.detail_data.error_message))
        elif self.detail_data.check is None:
            main_layout.addWidget(self._build_warning_card("Alınan çek kaydı bulunamadı."))
        else:
            main_layout.addWidget(self._build_check_summary_card())
            main_layout.addWidget(self._build_movement_table_card(), 1)

        close_row = QHBoxLayout()
        close_row.addStretch(1)

        close_button = QPushButton("Kapat")
        close_button.setMinimumHeight(40)
        close_button.clicked.connect(self.accept)

        close_row.addWidget(close_button)
        main_layout.addLayout(close_row)

        scroll_area.setWidget(content_widget)
        outer_layout.addWidget(scroll_area)

    def _load_detail_data(self, received_check_id: int) -> ReceivedCheckDetailData:
        try:
            with session_scope() as session:
                collection_bank_account_alias = aliased(BankAccount)
                collection_bank_alias = aliased(Bank)

                check_statement = (
                    select(
                        ReceivedCheck,
                        BusinessPartner,
                        collection_bank_account_alias,
                        collection_bank_alias,
                    )
                    .join(BusinessPartner, ReceivedCheck.customer_id == BusinessPartner.id)
                    .outerjoin(
                        collection_bank_account_alias,
                        ReceivedCheck.collection_bank_account_id == collection_bank_account_alias.id,
                    )
                    .outerjoin(
                        collection_bank_alias,
                        collection_bank_account_alias.bank_id == collection_bank_alias.id,
                    )
                    .where(ReceivedCheck.id == received_check_id)
                )

                check_row = session.execute(check_statement).one_or_none()

                if check_row is None:
                    return ReceivedCheckDetailData(
                        check=None,
                        movements=[],
                        error_message=None,
                    )

                received_check, customer, collection_bank_account, collection_bank = check_row

                check_detail = ReceivedCheckMainDetail(
                    received_check_id=received_check.id,
                    customer_name=customer.name,
                    drawer_bank_name=received_check.drawer_bank_name,
                    drawer_branch_name=received_check.drawer_branch_name,
                    collection_bank_name=collection_bank.name if collection_bank else None,
                    collection_bank_account_name=(
                        collection_bank_account.account_name if collection_bank_account else None
                    ),
                    check_number=received_check.check_number,
                    received_date=received_check.received_date,
                    due_date=received_check.due_date,
                    amount=Decimal(str(received_check.amount)),
                    currency_code=_enum_value(received_check.currency_code),
                    status=_enum_value(received_check.status),
                    reference_no=received_check.reference_no,
                    description=received_check.description,
                    created_at=received_check.created_at,
                    updated_at=received_check.updated_at,
                )

                movement_bank_account_alias = aliased(BankAccount)
                movement_bank_alias = aliased(Bank)
                created_by_user_alias = aliased(User)

                movement_statement = (
                    select(
                        ReceivedCheckMovement,
                        movement_bank_account_alias,
                        movement_bank_alias,
                        created_by_user_alias,
                    )
                    .outerjoin(
                        movement_bank_account_alias,
                        ReceivedCheckMovement.bank_account_id == movement_bank_account_alias.id,
                    )
                    .outerjoin(
                        movement_bank_alias,
                        movement_bank_account_alias.bank_id == movement_bank_alias.id,
                    )
                    .outerjoin(
                        created_by_user_alias,
                        ReceivedCheckMovement.created_by_user_id == created_by_user_alias.id,
                    )
                    .where(ReceivedCheckMovement.received_check_id == received_check_id)
                    .order_by(
                        ReceivedCheckMovement.movement_date.asc(),
                        ReceivedCheckMovement.id.asc(),
                    )
                )

                movement_rows = session.execute(movement_statement).all()

                movements: list[ReceivedCheckMovementDetail] = []

                for movement, movement_bank_account, movement_bank, created_by_user in movement_rows:
                    created_by_text = None

                    if created_by_user is not None:
                        created_by_text = (
                            created_by_user.full_name
                            or created_by_user.username
                            or f"Kullanıcı ID: {created_by_user.id}"
                        )

                    movements.append(
                        ReceivedCheckMovementDetail(
                            movement_id=movement.id,
                            movement_type=_enum_value(movement.movement_type),
                            movement_date=movement.movement_date,
                            from_status=_enum_value(movement.from_status) if movement.from_status else None,
                            to_status=_enum_value(movement.to_status),
                            bank_name=movement_bank.name if movement_bank else None,
                            bank_account_name=(
                                movement_bank_account.account_name if movement_bank_account else None
                            ),
                            counterparty_text=movement.counterparty_text,
                            purpose_text=movement.purpose_text,
                            reference_no=movement.reference_no,
                            description=movement.description,
                            gross_amount=Decimal(str(movement.gross_amount)),
                            currency_code=_enum_value(movement.currency_code),
                            discount_rate=(
                                Decimal(str(movement.discount_rate))
                                if movement.discount_rate is not None
                                else None
                            ),
                            discount_expense_amount=(
                                Decimal(str(movement.discount_expense_amount))
                                if movement.discount_expense_amount is not None
                                else None
                            ),
                            net_bank_amount=(
                                Decimal(str(movement.net_bank_amount))
                                if movement.net_bank_amount is not None
                                else None
                            ),
                            created_by_text=created_by_text,
                            created_at=movement.created_at,
                        )
                    )

                return ReceivedCheckDetailData(
                    check=check_detail,
                    movements=movements,
                    error_message=None,
                )

        except Exception as exc:
            return ReceivedCheckDetailData(
                check=None,
                movements=[],
                error_message=str(exc),
            )

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
        check = self.detail_data.check

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

        collection_account_text = _bank_account_text(
            check.collection_bank_name,
            check.collection_bank_account_name,
        )

        grid.addWidget(self._build_info_box("Çek ID", str(check.received_check_id)), 0, 0)
        grid.addWidget(self._build_info_box("Müşteri", check.customer_name), 0, 1)
        grid.addWidget(self._build_info_box("Çek No", check.check_number), 0, 2)
        grid.addWidget(self._build_info_box("Durum", received_status_text(check.status)), 0, 3)

        grid.addWidget(self._build_info_box("Keşideci Banka", check.drawer_bank_name), 1, 0)
        grid.addWidget(self._build_info_box("Şube", _format_optional_text(check.drawer_branch_name)), 1, 1)
        grid.addWidget(self._build_info_box("Alınış Tarihi", _format_date(check.received_date)), 1, 2)
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
        grid.addWidget(self._build_info_box("Tahsil Hesabı", collection_account_text), 2, 2)
        grid.addWidget(self._build_info_box("Referans No", _format_optional_text(check.reference_no)), 2, 3)

        grid.addWidget(self._build_info_box("Açıklama", _format_optional_text(check.description)), 3, 0, 1, 2)
        grid.addWidget(self._build_info_box("Oluşturma", _format_datetime(check.created_at)), 3, 2)
        grid.addWidget(self._build_info_box("Son Güncelleme", _format_datetime(check.updated_at)), 3, 3)

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

    def _build_movement_table_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("InfoCard")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        title = QLabel("Hareket Geçmişi")
        title.setObjectName("SectionTitle")

        subtitle = QLabel(
            f"Bu çek için toplam {len(self.detail_data.movements)} hareket kaydı listeleniyor."
        )
        subtitle.setObjectName("MutedText")

        self.movements_table = QTableWidget()
        self.movements_table.setColumnCount(12)
        self.movements_table.setHorizontalHeaderLabels(
            [
                "ID",
                "Tarih",
                "Hareket",
                "Önceki",
                "Yeni",
                "Banka / Hesap",
                "Karşı Taraf",
                "Brüt Tutar",
                "İskonto %",
                "Masraf",
                "Net Banka",
                "Açıklama",
            ]
        )
        self.movements_table.verticalHeader().setVisible(False)
        self.movements_table.setAlternatingRowColors(False)
        self.movements_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.movements_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.movements_table.setWordWrap(False)
        self.movements_table.setTextElideMode(Qt.ElideRight)
        self.movements_table.verticalHeader().setDefaultSectionSize(34)
        self.movements_table.verticalHeader().setMinimumSectionSize(30)
        self.movements_table.setMinimumHeight(260)

        header = self.movements_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.Stretch)
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(8, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(9, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(10, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(11, QHeaderView.Stretch)

        self._fill_movements_table()

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(self.movements_table)

        return card

    def _fill_movements_table(self) -> None:
        self.movements_table.setRowCount(len(self.detail_data.movements))

        for row_index, movement in enumerate(self.detail_data.movements):
            bank_account_text = _bank_account_text(
                movement.bank_name,
                movement.bank_account_name,
            )

            description_parts = []

            if movement.purpose_text:
                description_parts.append(movement.purpose_text)

            if movement.description:
                description_parts.append(movement.description)

            if movement.reference_no:
                description_parts.append(f"Ref: {movement.reference_no}")

            if movement.created_by_text:
                description_parts.append(f"Kullanıcı: {movement.created_by_text}")

            description_text = " | ".join(description_parts) if description_parts else "-"

            values = [
                str(movement.movement_id),
                _format_date(movement.movement_date),
                _movement_type_text(movement.movement_type),
                received_status_text(movement.from_status) if movement.from_status else "-",
                received_status_text(movement.to_status),
                bank_account_text,
                _format_optional_text(movement.counterparty_text),
                format_currency_amount(movement.gross_amount, movement.currency_code),
                _format_rate(movement.discount_rate),
                _format_optional_currency_amount(movement.discount_expense_amount, movement.currency_code),
                _format_optional_currency_amount(movement.net_bank_amount, movement.currency_code),
                description_text,
            ]

            for column_index, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(
                    "\n".join(
                        [
                            f"Hareket ID: {movement.movement_id}",
                            f"Tarih: {_format_date(movement.movement_date)}",
                            f"Hareket: {_movement_type_text(movement.movement_type)}",
                            f"Önceki Durum: {received_status_text(movement.from_status) if movement.from_status else '-'}",
                            f"Yeni Durum: {received_status_text(movement.to_status)}",
                            f"Banka / Hesap: {bank_account_text}",
                            f"Karşı Taraf: {_format_optional_text(movement.counterparty_text)}",
                            f"Brüt Tutar: {format_currency_amount(movement.gross_amount, movement.currency_code)}",
                            f"İskonto Oranı: {_format_rate(movement.discount_rate)}",
                            f"İskonto Masrafı: {_format_optional_currency_amount(movement.discount_expense_amount, movement.currency_code)}",
                            f"Net Banka Girişi: {_format_optional_currency_amount(movement.net_bank_amount, movement.currency_code)}",
                            f"Açıklama: {description_text}",
                            f"Kayıt Zamanı: {_format_datetime(movement.created_at)}",
                        ]
                    )
                )

                if column_index in {7, 8, 9, 10}:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                else:
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)

                self.movements_table.setItem(row_index, column_index, item)

        self.movements_table.resizeRowsToContents()