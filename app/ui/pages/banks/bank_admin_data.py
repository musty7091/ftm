from dataclasses import dataclass
from typing import Any

from sqlalchemy import select

from app.db.session import session_scope
from app.models.bank import Bank, BankAccount
from app.ui.ui_helpers import tr_money


@dataclass
class AdminBankRow:
    bank_id: int
    name: str
    short_name: str | None
    notes: str | None
    is_active: bool


@dataclass
class AdminBankAccountRow:
    bank_account_id: int
    bank_id: int
    bank_name: str
    account_name: str
    account_type: str
    currency_code: str
    iban: str | None
    branch_name: str | None
    branch_code: str | None
    account_no: str | None
    opening_balance: Any
    opening_date_text: str | None
    notes: str | None
    is_active: bool


def _enum_value(value: Any) -> str:
    if hasattr(value, "value"):
        return str(value.value)

    return str(value)


def _format_amount(value: Any, currency_code: str) -> str:
    if currency_code == "TRY":
        return tr_money(value)

    return f"{value} {currency_code}"


def load_admin_banks(*, include_passive: bool = True) -> list[AdminBankRow]:
    with session_scope() as session:
        statement = select(Bank).order_by(Bank.name)

        if not include_passive:
            statement = statement.where(Bank.is_active.is_(True))

        banks = session.execute(statement).scalars().all()

        return [
            AdminBankRow(
                bank_id=bank.id,
                name=bank.name,
                short_name=bank.short_name,
                notes=bank.notes,
                is_active=bank.is_active,
            )
            for bank in banks
        ]


def load_admin_bank_accounts(*, include_passive: bool = True) -> list[AdminBankAccountRow]:
    with session_scope() as session:
        statement = (
            select(BankAccount, Bank)
            .join(Bank, BankAccount.bank_id == Bank.id)
            .order_by(Bank.name, BankAccount.account_name)
        )

        if not include_passive:
            statement = statement.where(BankAccount.is_active.is_(True))

        rows = session.execute(statement).all()

        bank_accounts: list[AdminBankAccountRow] = []

        for bank_account, bank in rows:
            opening_date_text = (
                bank_account.opening_date.strftime("%d.%m.%Y")
                if bank_account.opening_date
                else None
            )

            bank_accounts.append(
                AdminBankAccountRow(
                    bank_account_id=bank_account.id,
                    bank_id=bank.id,
                    bank_name=bank.name,
                    account_name=bank_account.account_name,
                    account_type=_enum_value(bank_account.account_type),
                    currency_code=_enum_value(bank_account.currency_code),
                    iban=bank_account.iban,
                    branch_name=bank_account.branch_name,
                    branch_code=bank_account.branch_code,
                    account_no=bank_account.account_no,
                    opening_balance=bank_account.opening_balance,
                    opening_date_text=opening_date_text,
                    notes=bank_account.notes,
                    is_active=bank_account.is_active,
                )
            )

        return bank_accounts


def bank_display_text(bank: AdminBankRow) -> str:
    status_text = "Aktif" if bank.is_active else "Pasif"
    short_name_text = f" / {bank.short_name}" if bank.short_name else ""

    return f"#{bank.bank_id} / {bank.name}{short_name_text} / {status_text}"


def bank_account_display_text(bank_account: AdminBankAccountRow) -> str:
    status_text = "Aktif" if bank_account.is_active else "Pasif"
    opening_text = _format_amount(
        bank_account.opening_balance,
        bank_account.currency_code,
    )

    return (
        f"#{bank_account.bank_account_id} / "
        f"{bank_account.bank_name} / "
        f"{bank_account.account_name} / "
        f"{bank_account.currency_code} / "
        f"Açılış: {opening_text} / "
        f"{status_text}"
    )