from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Date, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.db.types import MONEY
from app.models.enums import BankTransactionStatus, CurrencyCode, FinancialSourceType, TransactionDirection


class BankTransaction(Base):
    __tablename__ = "bank_transactions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    bank_account_id: Mapped[int] = mapped_column(
        ForeignKey("bank_accounts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    transaction_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    value_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)

    direction: Mapped[TransactionDirection] = mapped_column(
        Enum(
            TransactionDirection,
            native_enum=False,
            validate_strings=True,
            length=10,
            name="transaction_direction",
        ),
        nullable=False,
    )

    status: Mapped[BankTransactionStatus] = mapped_column(
        Enum(
            BankTransactionStatus,
            native_enum=False,
            validate_strings=True,
            length=20,
            name="bank_transaction_status",
        ),
        nullable=False,
        default=BankTransactionStatus.REALIZED,
        server_default=BankTransactionStatus.REALIZED.value,
        index=True,
    )

    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)

    currency_code: Mapped[CurrencyCode] = mapped_column(
        Enum(
            CurrencyCode,
            native_enum=False,
            validate_strings=True,
            length=10,
            name="bank_transaction_currency_code",
        ),
        nullable=False,
        default=CurrencyCode.TRY,
        server_default=CurrencyCode.TRY.value,
    )

    source_type: Mapped[FinancialSourceType] = mapped_column(
        Enum(
            FinancialSourceType,
            native_enum=False,
            validate_strings=True,
            length=40,
            name="financial_source_type",
        ),
        nullable=False,
        default=FinancialSourceType.OTHER,
        server_default=FinancialSourceType.OTHER.value,
        index=True,
    )

    source_id: Mapped[Optional[int]] = mapped_column(nullable=True, index=True)

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

    bank_account: Mapped["BankAccount"] = relationship(
        "BankAccount",
        back_populates="transactions",
    )

    created_by_user: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[created_by_user_id],
    )

    cancelled_by_user: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[cancelled_by_user_id],
    )

    def __repr__(self) -> str:
        return (
            f"<BankTransaction id={self.id} "
            f"account_id={self.bank_account_id} "
            f"direction={self.direction} "
            f"amount={self.amount} "
            f"status={self.status}>"
        )