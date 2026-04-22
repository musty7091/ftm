from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Date, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.db.types import MONEY
from app.models.enums import BankTransferStatus, CurrencyCode


class BankTransfer(Base):
    __tablename__ = "bank_transfers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    from_bank_account_id: Mapped[int] = mapped_column(
        ForeignKey("bank_accounts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    to_bank_account_id: Mapped[int] = mapped_column(
        ForeignKey("bank_accounts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    transfer_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    value_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)

    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)

    currency_code: Mapped[CurrencyCode] = mapped_column(
        Enum(
            CurrencyCode,
            native_enum=False,
            validate_strings=True,
            length=10,
            name="bank_transfer_currency_code",
        ),
        nullable=False,
        default=CurrencyCode.TRY,
        server_default=CurrencyCode.TRY.value,
    )

    status: Mapped[BankTransferStatus] = mapped_column(
        Enum(
            BankTransferStatus,
            native_enum=False,
            validate_strings=True,
            length=20,
            name="bank_transfer_status",
        ),
        nullable=False,
        default=BankTransferStatus.REALIZED,
        server_default=BankTransferStatus.REALIZED.value,
        index=True,
    )

    outgoing_transaction_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("bank_transactions.id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
        index=True,
    )

    incoming_transaction_id: Mapped[Optional[int]] = mapped_column(
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

    from_bank_account = relationship(
        "BankAccount",
        foreign_keys=[from_bank_account_id],
    )

    to_bank_account = relationship(
        "BankAccount",
        foreign_keys=[to_bank_account_id],
    )

    outgoing_transaction = relationship(
        "BankTransaction",
        foreign_keys=[outgoing_transaction_id],
    )

    incoming_transaction = relationship(
        "BankTransaction",
        foreign_keys=[incoming_transaction_id],
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
            f"<BankTransfer id={self.id} "
            f"from={self.from_bank_account_id} "
            f"to={self.to_bank_account_id} "
            f"amount={self.amount} "
            f"status={self.status}>"
        )