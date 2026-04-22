from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.db.types import MONEY
from app.models.enums import BankAccountType, CurrencyCode


class Bank(Base):
    __tablename__ = "banks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    name: Mapped[str] = mapped_column(String(150), nullable=False, unique=True, index=True)
    short_name: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, unique=True, index=True)

    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    accounts: Mapped[List["BankAccount"]] = relationship(
        "BankAccount",
        back_populates="bank",
        cascade="save-update, merge",
    )

    def __repr__(self) -> str:
        return f"<Bank id={self.id} name={self.name!r}>"


class BankAccount(Base):
    __tablename__ = "bank_accounts"

    __table_args__ = (
        UniqueConstraint("bank_id", "account_name", name="uq_bank_accounts_bank_id_account_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    bank_id: Mapped[int] = mapped_column(
        ForeignKey("banks.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    account_name: Mapped[str] = mapped_column(String(150), nullable=False)
    account_type: Mapped[BankAccountType] = mapped_column(
        Enum(
            BankAccountType,
            native_enum=False,
            validate_strings=True,
            length=30,
            name="bank_account_type",
        ),
        nullable=False,
        default=BankAccountType.CHECKING,
        server_default=BankAccountType.CHECKING.value,
    )

    currency_code: Mapped[CurrencyCode] = mapped_column(
        Enum(
            CurrencyCode,
            native_enum=False,
            validate_strings=True,
            length=10,
            name="currency_code",
        ),
        nullable=False,
        default=CurrencyCode.TRY,
        server_default=CurrencyCode.TRY.value,
    )

    iban: Mapped[Optional[str]] = mapped_column(String(34), nullable=True, unique=True, index=True)
    branch_name: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    branch_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    account_no: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)

    opening_balance: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=Decimal("0.00"), server_default="0.00")
    opening_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    bank: Mapped["Bank"] = relationship(
        "Bank",
        back_populates="accounts",
    )

    transactions: Mapped[List["BankTransaction"]] = relationship(
        "BankTransaction",
        back_populates="bank_account",
        cascade="save-update, merge",
    )

    def __repr__(self) -> str:
        return f"<BankAccount id={self.id} bank_id={self.bank_id} account_name={self.account_name!r}>"