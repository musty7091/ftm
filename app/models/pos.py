from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.db.types import MONEY, RATE
from app.models.enums import CurrencyCode, PosSettlementStatus


class PosDevice(Base):
    __tablename__ = "pos_devices"

    __table_args__ = (
        UniqueConstraint("bank_account_id", "terminal_no", name="uq_pos_devices_bank_account_id_terminal_no"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    bank_account_id: Mapped[int] = mapped_column(
        ForeignKey("bank_accounts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    terminal_no: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)

    commission_rate: Mapped[Decimal] = mapped_column(
        RATE,
        nullable=False,
        default=Decimal("0.000000"),
        server_default="0.000000",
    )

    settlement_delay_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
    )

    currency_code: Mapped[CurrencyCode] = mapped_column(
        Enum(
            CurrencyCode,
            native_enum=False,
            validate_strings=True,
            length=10,
            name="pos_device_currency_code",
        ),
        nullable=False,
        default=CurrencyCode.TRY,
        server_default=CurrencyCode.TRY.value,
    )

    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    bank_account = relationship(
        "BankAccount",
        foreign_keys=[bank_account_id],
    )

    def __repr__(self) -> str:
        return f"<PosDevice id={self.id} name={self.name!r} terminal_no={self.terminal_no!r}>"


class PosSettlement(Base):
    __tablename__ = "pos_settlements"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    pos_device_id: Mapped[int] = mapped_column(
        ForeignKey("pos_devices.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    transaction_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    expected_settlement_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    realized_settlement_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)

    gross_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)

    commission_rate: Mapped[Decimal] = mapped_column(
        RATE,
        nullable=False,
        default=Decimal("0.000000"),
        server_default="0.000000",
    )

    commission_amount: Mapped[Decimal] = mapped_column(
        MONEY,
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )

    net_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)

    actual_net_amount: Mapped[Optional[Decimal]] = mapped_column(
        MONEY,
        nullable=True,
    )

    difference_amount: Mapped[Decimal] = mapped_column(
        MONEY,
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )

    difference_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    currency_code: Mapped[CurrencyCode] = mapped_column(
        Enum(
            CurrencyCode,
            native_enum=False,
            validate_strings=True,
            length=10,
            name="pos_settlement_currency_code",
        ),
        nullable=False,
        default=CurrencyCode.TRY,
        server_default=CurrencyCode.TRY.value,
    )

    status: Mapped[PosSettlementStatus] = mapped_column(
        Enum(
            PosSettlementStatus,
            native_enum=False,
            validate_strings=True,
            length=20,
            name="pos_settlement_status",
        ),
        nullable=False,
        default=PosSettlementStatus.PLANNED,
        server_default=PosSettlementStatus.PLANNED.value,
        index=True,
    )

    bank_transaction_id: Mapped[Optional[int]] = mapped_column(
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

    pos_device = relationship(
        "PosDevice",
        foreign_keys=[pos_device_id],
    )

    bank_transaction = relationship(
        "BankTransaction",
        foreign_keys=[bank_transaction_id],
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
            f"<PosSettlement id={self.id} "
            f"pos_device_id={self.pos_device_id} "
            f"gross_amount={self.gross_amount} "
            f"net_amount={self.net_amount} "
            f"actual_net_amount={self.actual_net_amount} "
            f"difference_amount={self.difference_amount} "
            f"status={self.status}>"
        )