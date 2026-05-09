from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.db.types import MONEY, RATE
from app.models.enums import (
    CreditCardNetwork,
    CreditCardStatementStatus,
    CreditCardTransactionStatus,
    CreditCardType,
    CreditLimitType,
    CreditLimitUsageMode,
    CurrencyCode,
    InterestPeriod,
)


class CreditCard(Base):
    __tablename__ = "credit_cards"

    __table_args__ = (
        UniqueConstraint(
            "bank_id",
            "card_name",
            name="uq_credit_cards_bank_id_card_name",
        ),
        UniqueConstraint(
            "bank_id",
            "last_four_digits",
            name="uq_credit_cards_bank_id_last_four_digits",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    bank_id: Mapped[int] = mapped_column(
        ForeignKey("banks.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    card_name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)

    card_type: Mapped[CreditCardType] = mapped_column(
        Enum(
            CreditCardType,
            native_enum=False,
            validate_strings=True,
            length=30,
            name="credit_card_type",
        ),
        nullable=False,
        default=CreditCardType.BUSINESS,
        server_default=CreditCardType.BUSINESS.value,
    )

    card_network: Mapped[CreditCardNetwork] = mapped_column(
        Enum(
            CreditCardNetwork,
            native_enum=False,
            validate_strings=True,
            length=30,
            name="credit_card_network",
        ),
        nullable=False,
        default=CreditCardNetwork.OTHER,
        server_default=CreditCardNetwork.OTHER.value,
    )

    last_four_digits: Mapped[Optional[str]] = mapped_column(String(4), nullable=True, index=True)

    currency_code: Mapped[CurrencyCode] = mapped_column(
        Enum(
            CurrencyCode,
            native_enum=False,
            validate_strings=True,
            length=10,
            name="credit_card_currency_code",
        ),
        nullable=False,
        default=CurrencyCode.TRY,
        server_default=CurrencyCode.TRY.value,
    )

    credit_limit: Mapped[Decimal] = mapped_column(
        MONEY,
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )

    statement_cut_day: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    payment_due_day: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    default_payment_bank_account_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("bank_accounts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    bank = relationship("Bank")
    default_payment_bank_account = relationship("BankAccount")

    statements: Mapped[List["CreditCardStatement"]] = relationship(
        "CreditCardStatement",
        back_populates="credit_card",
        cascade="save-update, merge",
    )

    transactions: Mapped[List["CreditCardTransaction"]] = relationship(
        "CreditCardTransaction",
        back_populates="credit_card",
        cascade="save-update, merge",
    )

    def __repr__(self) -> str:
        return (
            f"<CreditCard id={self.id} bank_id={self.bank_id} "
            f"card_name={self.card_name!r} last_four_digits={self.last_four_digits!r}>"
        )


class CreditCardStatement(Base):
    __tablename__ = "credit_card_statements"

    __table_args__ = (
        UniqueConstraint(
            "credit_card_id",
            "period_label",
            name="uq_credit_card_statements_card_id_period_label",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    credit_card_id: Mapped[int] = mapped_column(
        ForeignKey("credit_cards.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    period_label: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    statement_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    due_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    statement_amount: Mapped[Decimal] = mapped_column(
        MONEY,
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )

    minimum_payment_amount: Mapped[Decimal] = mapped_column(
        MONEY,
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )

    paid_amount: Mapped[Decimal] = mapped_column(
        MONEY,
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )

    remaining_amount: Mapped[Decimal] = mapped_column(
        MONEY,
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )

    status: Mapped[CreditCardStatementStatus] = mapped_column(
        Enum(
            CreditCardStatementStatus,
            native_enum=False,
            validate_strings=True,
            length=30,
            name="credit_card_statement_status",
        ),
        nullable=False,
        default=CreditCardStatementStatus.ISSUED,
        server_default=CreditCardStatementStatus.ISSUED.value,
        index=True,
    )

    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    credit_card: Mapped["CreditCard"] = relationship(
        "CreditCard",
        back_populates="statements",
    )

    payments: Mapped[List["CreditCardPayment"]] = relationship(
        "CreditCardPayment",
        back_populates="statement",
        cascade="save-update, merge",
    )

    transactions: Mapped[List["CreditCardTransaction"]] = relationship(
        "CreditCardTransaction",
        back_populates="statement",
        cascade="save-update, merge",
    )

    def __repr__(self) -> str:
        return (
            f"<CreditCardStatement id={self.id} credit_card_id={self.credit_card_id} "
            f"period_label={self.period_label!r} status={self.status!r}>"
        )


class CreditCardTransaction(Base):
    __tablename__ = "credit_card_transactions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    credit_card_id: Mapped[int] = mapped_column(
        ForeignKey("credit_cards.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    statement_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("credit_card_statements.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    transaction_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    merchant_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)

    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    amount: Mapped[Decimal] = mapped_column(
        MONEY,
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )

    currency_code: Mapped[CurrencyCode] = mapped_column(
        Enum(
            CurrencyCode,
            native_enum=False,
            validate_strings=True,
            length=10,
            name="credit_card_transaction_currency_code",
        ),
        nullable=False,
        default=CurrencyCode.TRY,
        server_default=CurrencyCode.TRY.value,
    )

    installment_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
    )

    installment_no: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
    )

    status: Mapped[CreditCardTransactionStatus] = mapped_column(
        Enum(
            CreditCardTransactionStatus,
            native_enum=False,
            validate_strings=True,
            length=30,
            name="credit_card_transaction_status",
        ),
        nullable=False,
        default=CreditCardTransactionStatus.PENDING,
        server_default=CreditCardTransactionStatus.PENDING.value,
        index=True,
    )

    reference_no: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    credit_card: Mapped["CreditCard"] = relationship(
        "CreditCard",
        back_populates="transactions",
    )

    statement: Mapped[Optional["CreditCardStatement"]] = relationship(
        "CreditCardStatement",
        back_populates="transactions",
    )

    def __repr__(self) -> str:
        return (
            f"<CreditCardTransaction id={self.id} credit_card_id={self.credit_card_id} "
            f"merchant_name={self.merchant_name!r} amount={self.amount}>"
        )


class CreditCardPayment(Base):
    __tablename__ = "credit_card_payments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    statement_id: Mapped[int] = mapped_column(
        ForeignKey("credit_card_statements.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    payment_bank_account_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("bank_accounts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    payment_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    amount: Mapped[Decimal] = mapped_column(
        MONEY,
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )

    reference_no: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    statement: Mapped["CreditCardStatement"] = relationship(
        "CreditCardStatement",
        back_populates="payments",
    )

    payment_bank_account = relationship("BankAccount")

    def __repr__(self) -> str:
        return (
            f"<CreditCardPayment id={self.id} statement_id={self.statement_id} "
            f"amount={self.amount}>"
        )


class BankAccountCreditLimit(Base):
    __tablename__ = "bank_account_credit_limits"

    __table_args__ = (
        UniqueConstraint(
            "bank_account_id",
            "limit_name",
            name="uq_bank_account_credit_limits_account_id_limit_name",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    bank_account_id: Mapped[int] = mapped_column(
        ForeignKey("bank_accounts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    limit_name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)

    limit_type: Mapped[CreditLimitType] = mapped_column(
        Enum(
            CreditLimitType,
            native_enum=False,
            validate_strings=True,
            length=30,
            name="credit_limit_type",
        ),
        nullable=False,
        default=CreditLimitType.KMH,
        server_default=CreditLimitType.KMH.value,
        index=True,
    )

    currency_code: Mapped[CurrencyCode] = mapped_column(
        Enum(
            CurrencyCode,
            native_enum=False,
            validate_strings=True,
            length=10,
            name="credit_limit_currency_code",
        ),
        nullable=False,
        default=CurrencyCode.TRY,
        server_default=CurrencyCode.TRY.value,
    )

    limit_amount: Mapped[Decimal] = mapped_column(
        MONEY,
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )

    usage_mode: Mapped[CreditLimitUsageMode] = mapped_column(
        Enum(
            CreditLimitUsageMode,
            native_enum=False,
            validate_strings=True,
            length=40,
            name="credit_limit_usage_mode",
        ),
        nullable=False,
        default=CreditLimitUsageMode.MANUAL,
        server_default=CreditLimitUsageMode.MANUAL.value,
    )

    manual_used_amount: Mapped[Decimal] = mapped_column(
        MONEY,
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )

    interest_rate: Mapped[Decimal] = mapped_column(
        RATE,
        nullable=False,
        default=Decimal("0.000000"),
        server_default="0.000000",
    )

    interest_period: Mapped[InterestPeriod] = mapped_column(
        Enum(
            InterestPeriod,
            native_enum=False,
            validate_strings=True,
            length=30,
            name="interest_period",
        ),
        nullable=False,
        default=InterestPeriod.MONTHLY,
        server_default=InterestPeriod.MONTHLY.value,
    )

    interest_day: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    contract_start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    contract_end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    bank_account = relationship("BankAccount")

    def __repr__(self) -> str:
        return (
            f"<BankAccountCreditLimit id={self.id} bank_account_id={self.bank_account_id} "
            f"limit_name={self.limit_name!r} limit_type={self.limit_type!r}>"
        )


__all__ = [
    "CreditCard",
    "CreditCardStatement",
    "CreditCardTransaction",
    "CreditCardPayment",
    "BankAccountCreditLimit",
]
