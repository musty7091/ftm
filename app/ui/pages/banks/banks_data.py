from dataclasses import dataclass
from typing import Any

from sqlalchemy import select

from app.db.session import session_scope
from app.models.bank import Bank, BankAccount
from app.services.bank_transaction_service import get_bank_account_balance_summary
from app.ui.ui_helpers import decimal_or_zero, tr_money


@dataclass
class BankAccountRow:
    bank_id: int
    bank_account_id: int
    bank_name: str
    account_name: str
    currency_code: str
    opening_balance: Any
    incoming_total: Any
    outgoing_total: Any
    current_balance: Any
    is_active: bool


@dataclass
class BanksPageData:
    bank_accounts: list[BankAccountRow]
    total_try_balance: Any
    active_account_count: int
    error_message: str | None = None


def _format_currency_amount(value: Any, currency_code: str) -> str:
    if currency_code == "TRY":
        return tr_money(value)

    return f"{value} {currency_code}"


def load_banks_page_data() -> BanksPageData:
    try:
        with session_scope() as session:
            statement = (
                select(BankAccount, Bank)
                .join(Bank, BankAccount.bank_id == Bank.id)
                .order_by(Bank.name, BankAccount.account_name)
            )

            rows = session.execute(statement).all()

            bank_accounts: list[BankAccountRow] = []
            total_try_balance = decimal_or_zero("0.00")
            active_account_count = 0

            for bank_account, bank in rows:
                summary = get_bank_account_balance_summary(
                    session,
                    bank_account_id=bank_account.id,
                )

                current_balance = decimal_or_zero(summary["current_balance"])

                if bank_account.is_active:
                    active_account_count += 1

                if summary["currency_code"] == "TRY" and bank_account.is_active:
                    total_try_balance += current_balance

                bank_accounts.append(
                    BankAccountRow(
                        bank_id=bank.id,
                        bank_account_id=bank_account.id,
                        bank_name=bank.name,
                        account_name=bank_account.account_name,
                        currency_code=summary["currency_code"],
                        opening_balance=summary["opening_balance"],
                        incoming_total=summary["incoming_total"],
                        outgoing_total=summary["outgoing_total"],
                        current_balance=summary["current_balance"],
                        is_active=bank_account.is_active,
                    )
                )

            return BanksPageData(
                bank_accounts=bank_accounts,
                total_try_balance=total_try_balance,
                active_account_count=active_account_count,
            )

    except Exception as exc:
        return BanksPageData(
            bank_accounts=[],
            total_try_balance=decimal_or_zero("0.00"),
            active_account_count=0,
            error_message=str(exc),
        )