from dataclasses import dataclass
from typing import Any

from sqlalchemy import select

from app.db.session import session_scope
from app.models.bank import Bank, BankAccount
from app.models.pos import PosDevice
from app.ui.pages.pos.pos_data import format_rate_percent


@dataclass
class AdminPosBankAccountRow:
    bank_account_id: int
    bank_id: int
    bank_name: str
    account_name: str
    currency_code: str
    is_active: bool


@dataclass
class AdminPosDeviceRow:
    pos_device_id: int
    bank_account_id: int
    bank_id: int
    bank_name: str
    bank_account_name: str
    name: str
    terminal_no: str | None
    commission_rate: Any
    settlement_delay_days: int
    currency_code: str
    notes: str | None
    is_active: bool


def _enum_value(value: Any) -> str:
    if hasattr(value, "value"):
        return str(value.value)

    return str(value or "").strip().upper()


def load_admin_pos_bank_accounts(*, include_passive: bool = False) -> list[AdminPosBankAccountRow]:
    with session_scope() as session:
        statement = (
            select(BankAccount, Bank)
            .join(Bank, BankAccount.bank_id == Bank.id)
            .order_by(Bank.name, BankAccount.account_name)
        )

        if not include_passive:
            statement = statement.where(Bank.is_active.is_(True))
            statement = statement.where(BankAccount.is_active.is_(True))

        rows = session.execute(statement).all()

        bank_accounts: list[AdminPosBankAccountRow] = []

        for bank_account, bank in rows:
            bank_accounts.append(
                AdminPosBankAccountRow(
                    bank_account_id=bank_account.id,
                    bank_id=bank.id,
                    bank_name=bank.name,
                    account_name=bank_account.account_name,
                    currency_code=_enum_value(bank_account.currency_code),
                    is_active=bool(bank_account.is_active and bank.is_active),
                )
            )

        return bank_accounts


def load_admin_pos_devices(*, include_passive: bool = True) -> list[AdminPosDeviceRow]:
    with session_scope() as session:
        statement = (
            select(PosDevice, BankAccount, Bank)
            .join(BankAccount, PosDevice.bank_account_id == BankAccount.id)
            .join(Bank, BankAccount.bank_id == Bank.id)
            .order_by(Bank.name, PosDevice.name)
        )

        if not include_passive:
            statement = statement.where(PosDevice.is_active.is_(True))

        rows = session.execute(statement).all()

        pos_devices: list[AdminPosDeviceRow] = []

        for pos_device, bank_account, bank in rows:
            pos_devices.append(
                AdminPosDeviceRow(
                    pos_device_id=pos_device.id,
                    bank_account_id=bank_account.id,
                    bank_id=bank.id,
                    bank_name=bank.name,
                    bank_account_name=bank_account.account_name,
                    name=pos_device.name,
                    terminal_no=pos_device.terminal_no,
                    commission_rate=pos_device.commission_rate,
                    settlement_delay_days=pos_device.settlement_delay_days,
                    currency_code=_enum_value(pos_device.currency_code),
                    notes=pos_device.notes,
                    is_active=pos_device.is_active,
                )
            )

        return pos_devices


def pos_bank_account_display_text(bank_account: AdminPosBankAccountRow) -> str:
    status_text = "Aktif" if bank_account.is_active else "Pasif"

    return (
        f"#{bank_account.bank_account_id} / "
        f"{bank_account.bank_name} / "
        f"{bank_account.account_name} / "
        f"{bank_account.currency_code} / "
        f"{status_text}"
    )


def pos_device_display_text(pos_device: AdminPosDeviceRow) -> str:
    status_text = "Aktif" if pos_device.is_active else "Pasif"
    terminal_text = pos_device.terminal_no if pos_device.terminal_no else "-"
    commission_text = format_rate_percent(pos_device.commission_rate)

    return (
        f"#{pos_device.pos_device_id} / "
        f"{pos_device.name} / "
        f"Terminal: {terminal_text} / "
        f"{pos_device.bank_name} - {pos_device.bank_account_name} / "
        f"{commission_text} / "
        f"{status_text}"
    )