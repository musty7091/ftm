from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.bank import Bank, BankAccount
from app.models.check import IssuedCheck, ReceivedCheck
from app.models.enums import IssuedCheckStatus, ReceivedCheckStatus
from app.services.bank_transaction_service import get_bank_account_balance_summary
from app.utils.decimal_utils import money


RISK_HORIZONS = [7, 15, 30]


def _decimal_from_db(value: object) -> Decimal:
    if value is None:
        return Decimal("0.00")

    if isinstance(value, Decimal):
        return value

    return Decimal(str(value))


def get_pending_issued_checks_total(
    session: Session,
    *,
    bank_account_id: int,
    cutoff_date: date,
) -> Decimal:
    statement = select(
        func.coalesce(func.sum(IssuedCheck.amount), Decimal("0.00"))
    ).where(
        IssuedCheck.bank_account_id == bank_account_id,
        IssuedCheck.due_date <= cutoff_date,
        IssuedCheck.status.in_(
            [
                IssuedCheckStatus.PREPARED,
                IssuedCheckStatus.GIVEN,
                IssuedCheckStatus.RISK,
            ]
        ),
    )

    total = session.execute(statement).scalar_one()

    return money(_decimal_from_db(total), field_name="Bekleyen yazdığımız çek toplamı")


def get_expected_received_checks_total(
    session: Session,
    *,
    bank_account_id: int,
    cutoff_date: date,
) -> Decimal:
    statement = select(
        func.coalesce(func.sum(ReceivedCheck.amount), Decimal("0.00"))
    ).where(
        ReceivedCheck.collection_bank_account_id == bank_account_id,
        ReceivedCheck.due_date <= cutoff_date,
        ReceivedCheck.status.in_(
            [
                ReceivedCheckStatus.GIVEN_TO_BANK,
                ReceivedCheckStatus.IN_COLLECTION,
            ]
        ),
    )

    total = session.execute(statement).scalar_one()

    return money(_decimal_from_db(total), field_name="Beklenen müşteri çeki toplamı")


def get_bank_risk_summary(
    session: Session,
    *,
    as_of_date: date,
    horizon_days: int,
) -> list[dict[str, Any]]:
    cutoff_date = as_of_date + timedelta(days=horizon_days)

    statement = (
        select(BankAccount, Bank)
        .join(Bank, BankAccount.bank_id == Bank.id)
        .where(BankAccount.is_active.is_(True))
        .order_by(Bank.name, BankAccount.account_name)
    )

    rows = session.execute(statement).all()

    summaries: list[dict[str, Any]] = []

    for bank_account, bank in rows:
        balance_summary = get_bank_account_balance_summary(
            session,
            bank_account_id=bank_account.id,
        )

        current_balance = money(balance_summary["current_balance"], field_name="Güncel bakiye")

        pending_issued_checks_total = get_pending_issued_checks_total(
            session,
            bank_account_id=bank_account.id,
            cutoff_date=cutoff_date,
        )

        expected_received_checks_total = get_expected_received_checks_total(
            session,
            bank_account_id=bank_account.id,
            cutoff_date=cutoff_date,
        )

        projected_balance = money(
            current_balance - pending_issued_checks_total + expected_received_checks_total,
            field_name="Tahmini bakiye",
        )

        if projected_balance < Decimal("0.00"):
            risk_status = "RISK"
        elif pending_issued_checks_total > Decimal("0.00"):
            risk_status = "TAKIP"
        else:
            risk_status = "OK"

        summaries.append(
            {
                "bank_account_id": bank_account.id,
                "bank_name": bank.name,
                "account_name": bank_account.account_name,
                "currency_code": bank_account.currency_code.value,
                "as_of_date": as_of_date,
                "cutoff_date": cutoff_date,
                "horizon_days": horizon_days,
                "current_balance": current_balance,
                "pending_issued_checks_total": pending_issued_checks_total,
                "expected_received_checks_total": expected_received_checks_total,
                "projected_balance": projected_balance,
                "risk_status": risk_status,
            }
        )

    return summaries


def get_all_bank_risk_summaries(
    session: Session,
    *,
    as_of_date: date,
) -> dict[int, list[dict[str, Any]]]:
    result: dict[int, list[dict[str, Any]]] = {}

    for horizon_days in RISK_HORIZONS:
        result[horizon_days] = get_bank_risk_summary(
            session,
            as_of_date=as_of_date,
            horizon_days=horizon_days,
        )

    return result