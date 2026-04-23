from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import Date, DateTime, Enum, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.db.types import MONEY, RATE
from app.models.enums import (
    CurrencyCode,
    IssuedCheckStatus,
    ReceivedCheckMovementType,
    ReceivedCheckStatus,
)


class IssuedCheck(Base):
    __tablename__ = "issued_checks"

    __table_args__ = (
        UniqueConstraint("bank_account_id", "check_number", name="uq_issued_checks_bank_account_id_check_number"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    supplier_id: Mapped[int] = mapped_column(
        ForeignKey("business_partners.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    bank_account_id: Mapped[int] = mapped_column(
        ForeignKey("bank_accounts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    check_number: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    issue_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    due_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)

    currency_code: Mapped[CurrencyCode] = mapped_column(
        Enum(
            CurrencyCode,
            native_enum=False,
            validate_strings=True,
            length=10,
            name="issued_check_currency_code",
        ),
        nullable=False,
        default=CurrencyCode.TRY,
        server_default=CurrencyCode.TRY.value,
    )

    status: Mapped[IssuedCheckStatus] = mapped_column(
        Enum(
            IssuedCheckStatus,
            native_enum=False,
            validate_strings=True,
            length=20,
            name="issued_check_status",
        ),
        nullable=False,
        default=IssuedCheckStatus.PREPARED,
        server_default=IssuedCheckStatus.PREPARED.value,
        index=True,
    )

    paid_transaction_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("bank_transactions.id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
        index=True,
    )

    reference_no: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    cancelled_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    supplier = relationship(
        "BusinessPartner",
        foreign_keys=[supplier_id],
    )

    bank_account = relationship(
        "BankAccount",
        foreign_keys=[bank_account_id],
    )

    paid_transaction = relationship(
        "BankTransaction",
        foreign_keys=[paid_transaction_id],
    )

    created_by_user = relationship(
        "User",
        foreign_keys=[created_by_user_id],
    )

    cancelled_by_user = relationship(
        "User",
        foreign_keys=[cancelled_by_user_id],
    )

    def __repr__(self) -> str:
        return (
            f"<IssuedCheck id={self.id} "
            f"check_number={self.check_number!r} "
            f"amount={self.amount} "
            f"status={self.status}>"
        )


class ReceivedCheck(Base):
    __tablename__ = "received_checks"

    __table_args__ = (
        UniqueConstraint("drawer_bank_name", "check_number", name="uq_received_checks_drawer_bank_name_check_number"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    customer_id: Mapped[int] = mapped_column(
        ForeignKey("business_partners.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    collection_bank_account_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("bank_accounts.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    drawer_bank_name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    drawer_branch_name: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)

    check_number: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    received_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    due_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)

    currency_code: Mapped[CurrencyCode] = mapped_column(
        Enum(
            CurrencyCode,
            native_enum=False,
            validate_strings=True,
            length=10,
            name="received_check_currency_code",
        ),
        nullable=False,
        default=CurrencyCode.TRY,
        server_default=CurrencyCode.TRY.value,
    )

    status: Mapped[ReceivedCheckStatus] = mapped_column(
        Enum(
            ReceivedCheckStatus,
            native_enum=False,
            validate_strings=True,
            length=20,
            name="received_check_status",
        ),
        nullable=False,
        default=ReceivedCheckStatus.PORTFOLIO,
        server_default=ReceivedCheckStatus.PORTFOLIO.value,
        index=True,
    )

    collected_transaction_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("bank_transactions.id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
        index=True,
    )

    reference_no: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    cancelled_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    customer = relationship(
        "BusinessPartner",
        foreign_keys=[customer_id],
    )

    collection_bank_account = relationship(
        "BankAccount",
        foreign_keys=[collection_bank_account_id],
    )

    collected_transaction = relationship(
        "BankTransaction",
        foreign_keys=[collected_transaction_id],
    )

    created_by_user = relationship(
        "User",
        foreign_keys=[created_by_user_id],
    )

    cancelled_by_user = relationship(
        "User",
        foreign_keys=[cancelled_by_user_id],
    )

    movements: Mapped[List["ReceivedCheckMovement"]] = relationship(
        "ReceivedCheckMovement",
        back_populates="received_check",
        cascade="save-update, merge",
        order_by="ReceivedCheckMovement.id",
    )

    def __repr__(self) -> str:
        return (
            f"<ReceivedCheck id={self.id} "
            f"check_number={self.check_number!r} "
            f"amount={self.amount} "
            f"status={self.status}>"
        )


class ReceivedCheckMovement(Base):
    __tablename__ = "received_check_movements"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    received_check_id: Mapped[int] = mapped_column(
        ForeignKey("received_checks.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    movement_type: Mapped[ReceivedCheckMovementType] = mapped_column(
        Enum(
            ReceivedCheckMovementType,
            native_enum=False,
            validate_strings=True,
            length=40,
            name="received_check_movement_type",
        ),
        nullable=False,
        index=True,
    )

    movement_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    from_status: Mapped[Optional[ReceivedCheckStatus]] = mapped_column(
        Enum(
            ReceivedCheckStatus,
            native_enum=False,
            validate_strings=True,
            length=20,
            name="received_check_status",
        ),
        nullable=True,
    )

    to_status: Mapped[ReceivedCheckStatus] = mapped_column(
        Enum(
            ReceivedCheckStatus,
            native_enum=False,
            validate_strings=True,
            length=20,
            name="received_check_status",
        ),
        nullable=False,
        index=True,
    )

    bank_account_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("bank_accounts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    counterparty_text: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    purpose_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    reference_no: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    gross_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)

    currency_code: Mapped[CurrencyCode] = mapped_column(
        Enum(
            CurrencyCode,
            native_enum=False,
            validate_strings=True,
            length=10,
            name="received_check_currency_code",
        ),
        nullable=False,
        default=CurrencyCode.TRY,
        server_default=CurrencyCode.TRY.value,
    )

    discount_rate: Mapped[Optional[Decimal]] = mapped_column(RATE, nullable=True)
    discount_expense_amount: Mapped[Optional[Decimal]] = mapped_column(MONEY, nullable=True)
    net_bank_amount: Mapped[Optional[Decimal]] = mapped_column(MONEY, nullable=True)

    created_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    received_check = relationship(
        "ReceivedCheck",
        foreign_keys=[received_check_id],
        back_populates="movements",
    )

    bank_account = relationship(
        "BankAccount",
        foreign_keys=[bank_account_id],
    )

    created_by_user = relationship(
        "User",
        foreign_keys=[created_by_user_id],
    )

    def __repr__(self) -> str:
        return (
            f"<ReceivedCheckMovement id={self.id} "
            f"received_check_id={self.received_check_id} "
            f"movement_type={self.movement_type} "
            f"to_status={self.to_status}>"
        )