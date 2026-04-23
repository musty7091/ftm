from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select, text

from app.db.session import session_scope
from app.models.bank import Bank, BankAccount
from app.models.check import IssuedCheck, ReceivedCheck
from app.models.enums import IssuedCheckStatus, PosSettlementStatus, ReceivedCheckStatus
from app.models.pos import PosSettlement
from app.services.bank_transaction_service import get_bank_account_balance_summary
from app.services.system_health_service import run_system_health_check
from app.ui.ui_helpers import decimal_or_zero


@dataclass
class DashboardData:
    health_status: str
    health_ok_count: int
    health_warn_count: int
    health_fail_count: int
    bank_accounts: list[dict[str, Any]]
    pending_pos_count: int
    pending_pos_currency_totals: dict[str, Decimal]
    pending_issued_check_amount: Decimal
    pending_received_check_amount: Decimal
    permission_denied_count: int
    error_message: str | None = None


def _enum_value(value: Any) -> str:
    if hasattr(value, "value"):
        return str(value.value)

    return str(value or "").strip().upper()


def load_dashboard_data() -> DashboardData:
    try:
        with session_scope() as session:
            health_report = run_system_health_check(session)

            bank_statement = (
                select(BankAccount, Bank)
                .join(Bank, BankAccount.bank_id == Bank.id)
                .where(BankAccount.is_active.is_(True))
                .order_by(Bank.name, BankAccount.account_name)
            )

            bank_rows = session.execute(bank_statement).all()

            bank_accounts: list[dict[str, Any]] = []

            for bank_account, bank in bank_rows:
                summary = get_bank_account_balance_summary(
                    session,
                    bank_account_id=bank_account.id,
                )

                bank_accounts.append(
                    {
                        "bank_name": bank.name,
                        "account_name": bank_account.account_name,
                        "currency_code": summary["currency_code"],
                        "opening_balance": summary["opening_balance"],
                        "incoming_total": summary["incoming_total"],
                        "outgoing_total": summary["outgoing_total"],
                        "current_balance": summary["current_balance"],
                    }
                )

            pending_pos_count = int(
                session.execute(
                    select(func.count(PosSettlement.id)).where(
                        PosSettlement.status == PosSettlementStatus.PLANNED
                    )
                ).scalar_one()
                or 0
            )

            pending_pos_currency_rows = session.execute(
                select(
                    PosSettlement.currency_code,
                    func.coalesce(func.sum(PosSettlement.net_amount), Decimal("0.00")),
                )
                .where(PosSettlement.status == PosSettlementStatus.PLANNED)
                .group_by(PosSettlement.currency_code)
            ).all()

            pending_pos_currency_totals: dict[str, Decimal] = {}

            for currency_code, total_amount in pending_pos_currency_rows:
                normalized_currency_code = _enum_value(currency_code)

                if not normalized_currency_code:
                    continue

                pending_pos_currency_totals[normalized_currency_code] = decimal_or_zero(
                    total_amount
                )

            pending_issued_check_amount = decimal_or_zero(
                session.execute(
                    select(func.coalesce(func.sum(IssuedCheck.amount), Decimal("0.00"))).where(
                        IssuedCheck.status.in_(
                            [
                                IssuedCheckStatus.PREPARED,
                                IssuedCheckStatus.GIVEN,
                            ]
                        )
                    )
                ).scalar_one()
            )

            pending_received_check_amount = decimal_or_zero(
                session.execute(
                    select(func.coalesce(func.sum(ReceivedCheck.amount), Decimal("0.00"))).where(
                        ReceivedCheck.status.in_(
                            [
                                ReceivedCheckStatus.PORTFOLIO,
                                ReceivedCheckStatus.GIVEN_TO_BANK,
                                ReceivedCheckStatus.IN_COLLECTION,
                            ]
                        )
                    )
                ).scalar_one()
            )

            permission_denied_count = int(
                session.execute(
                    text("SELECT COUNT(*) FROM audit_logs WHERE action = 'PERMISSION_DENIED'")
                ).scalar_one()
                or 0
            )

            return DashboardData(
                health_status=health_report.overall_status,
                health_ok_count=health_report.passed_count,
                health_warn_count=health_report.warning_count,
                health_fail_count=health_report.failed_count,
                bank_accounts=bank_accounts,
                pending_pos_count=pending_pos_count,
                pending_pos_currency_totals=pending_pos_currency_totals,
                pending_issued_check_amount=pending_issued_check_amount,
                pending_received_check_amount=pending_received_check_amount,
                permission_denied_count=permission_denied_count,
            )

    except Exception as exc:
        return DashboardData(
            health_status="FAIL",
            health_ok_count=0,
            health_warn_count=0,
            health_fail_count=1,
            bank_accounts=[],
            pending_pos_count=0,
            pending_pos_currency_totals={},
            pending_issued_check_amount=Decimal("0.00"),
            pending_received_check_amount=Decimal("0.00"),
            permission_denied_count=0,
            error_message=str(exc),
        )