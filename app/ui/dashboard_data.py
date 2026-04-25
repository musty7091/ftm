from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select, text

from app.db.session import session_scope
from app.models.bank import Bank, BankAccount
from app.models.business_partner import BusinessPartner
from app.models.check import IssuedCheck, ReceivedCheck
from app.models.enums import PosSettlementStatus
from app.models.pos import PosSettlement
from app.services.bank_transaction_service import get_bank_account_balance_summary
from app.services.system_health_service import run_system_health_check
from app.ui.ui_helpers import decimal_or_zero


RECEIVED_PENDING_STATUSES = {
    "PORTFOLIO",
    "GIVEN_TO_BANK",
    "IN_COLLECTION",
}

RECEIVED_PROBLEM_STATUSES = {
    "BOUNCED",
}

RECEIVED_CLOSED_STATUSES = {
    "COLLECTED",
    "ENDORSED",
    "DISCOUNTED",
    "RETURNED",
    "CANCELLED",
}

ISSUED_PENDING_STATUSES = {
    "PREPARED",
    "GIVEN",
}

ISSUED_PROBLEM_STATUSES = {
    "RISK",
}

ISSUED_CLOSED_STATUSES = {
    "PAID",
    "CANCELLED",
}


RECEIVED_STATUS_TEXTS = {
    "PORTFOLIO": "Portföyde",
    "GIVEN_TO_BANK": "Bankaya Verildi",
    "IN_COLLECTION": "Tahsilde",
    "COLLECTED": "Tahsil Edildi",
    "BOUNCED": "Karşılıksız",
    "RETURNED": "İade Edildi",
    "ENDORSED": "Ciro Edildi",
    "DISCOUNTED": "İskontoya Verildi",
    "CANCELLED": "İptal Edildi",
}


ISSUED_STATUS_TEXTS = {
    "PREPARED": "Hazırlandı",
    "GIVEN": "Verildi",
    "PAID": "Ödendi",
    "CANCELLED": "İptal Edildi",
    "RISK": "Riskli",
}


@dataclass
class DashboardDueItem:
    check_type: str
    check_id: int
    party_name: str
    check_number: str
    due_date: date
    amount: Decimal
    currency_code: str
    status: str
    status_text: str
    urgency: str
    reference_no: str | None
    description: str | None


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

    due_today_count: int
    due_today_currency_totals: dict[str, Decimal]

    next_7_received_count: int
    next_7_received_currency_totals: dict[str, Decimal]

    next_7_issued_count: int
    next_7_issued_currency_totals: dict[str, Decimal]

    overdue_pending_count: int
    overdue_pending_currency_totals: dict[str, Decimal]

    problem_count: int
    problem_currency_totals: dict[str, Decimal]

    month_received_count: int
    month_received_currency_totals: dict[str, Decimal]

    month_issued_count: int
    month_issued_currency_totals: dict[str, Decimal]

    due_action_items: list[DashboardDueItem]

    error_message: str | None = None


def _enum_value(value: Any) -> str:
    if value is None:
        return ""

    if hasattr(value, "value"):
        return str(value.value).strip().upper()

    return str(value or "").strip().upper()


def _received_status_text(value: Any) -> str:
    status = _enum_value(value)

    return RECEIVED_STATUS_TEXTS.get(status, status or "-")


def _issued_status_text(value: Any) -> str:
    status = _enum_value(value)

    return ISSUED_STATUS_TEXTS.get(status, status or "-")


def _check_status_group(check_type: str, status: str) -> str:
    if check_type == "RECEIVED":
        if status in RECEIVED_PENDING_STATUSES:
            return "PENDING"
        if status in RECEIVED_PROBLEM_STATUSES:
            return "PROBLEM"
        if status in RECEIVED_CLOSED_STATUSES:
            return "CLOSED"

    if check_type == "ISSUED":
        if status in ISSUED_PENDING_STATUSES:
            return "PENDING"
        if status in ISSUED_PROBLEM_STATUSES:
            return "PROBLEM"
        if status in ISSUED_CLOSED_STATUSES:
            return "CLOSED"

    return "ALL"


def _add_to_totals(
    totals: dict[str, Decimal],
    currency_code: str,
    amount: Decimal,
) -> None:
    normalized_currency_code = str(currency_code or "TRY").strip().upper() or "TRY"

    totals[normalized_currency_code] = (
        totals.get(normalized_currency_code, Decimal("0.00")) + decimal_or_zero(amount)
    ).quantize(Decimal("0.01"))


def _month_start(value: date) -> date:
    return date(value.year, value.month, 1)


def _add_months(value: date, month_delta: int) -> date:
    month_index = value.month - 1 + month_delta
    year = value.year + month_index // 12
    month = month_index % 12 + 1

    return date(year, month, 1)


def _month_end(value: date) -> date:
    return _add_months(_month_start(value), 1) - timedelta(days=1)


def _empty_dashboard_data(error_message: str | None = None) -> DashboardData:
    return DashboardData(
        health_status="FAIL" if error_message else "OK",
        health_ok_count=0,
        health_warn_count=0,
        health_fail_count=1 if error_message else 0,
        bank_accounts=[],
        pending_pos_count=0,
        pending_pos_currency_totals={},
        pending_issued_check_amount=Decimal("0.00"),
        pending_received_check_amount=Decimal("0.00"),
        permission_denied_count=0,
        due_today_count=0,
        due_today_currency_totals={},
        next_7_received_count=0,
        next_7_received_currency_totals={},
        next_7_issued_count=0,
        next_7_issued_currency_totals={},
        overdue_pending_count=0,
        overdue_pending_currency_totals={},
        problem_count=0,
        problem_currency_totals={},
        month_received_count=0,
        month_received_currency_totals={},
        month_issued_count=0,
        month_issued_currency_totals={},
        due_action_items=[],
        error_message=error_message,
    )


def _action_priority(urgency: str) -> int:
    if urgency == "PROBLEM":
        return 0
    if urgency == "OVERDUE":
        return 1
    if urgency == "TODAY":
        return 2
    if urgency == "WEEK":
        return 3

    return 99


def load_dashboard_data() -> DashboardData:
    try:
        today = date.today()
        next_7_date = today + timedelta(days=7)
        current_month_start = _month_start(today)
        current_month_end = _month_end(today)

        due_today_count = 0
        due_today_currency_totals: dict[str, Decimal] = {}

        next_7_received_count = 0
        next_7_received_currency_totals: dict[str, Decimal] = {}

        next_7_issued_count = 0
        next_7_issued_currency_totals: dict[str, Decimal] = {}

        overdue_pending_count = 0
        overdue_pending_currency_totals: dict[str, Decimal] = {}

        problem_count = 0
        problem_currency_totals: dict[str, Decimal] = {}

        month_received_count = 0
        month_received_currency_totals: dict[str, Decimal] = {}

        month_issued_count = 0
        month_issued_currency_totals: dict[str, Decimal] = {}

        due_action_items: list[DashboardDueItem] = []

        pending_issued_check_amount = Decimal("0.00")
        pending_received_check_amount = Decimal("0.00")

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

            received_rows = session.execute(
                select(ReceivedCheck, BusinessPartner)
                .join(BusinessPartner, ReceivedCheck.customer_id == BusinessPartner.id)
                .order_by(ReceivedCheck.due_date.asc(), ReceivedCheck.id.asc())
            ).all()

            for received_check, customer in received_rows:
                if received_check.due_date is None:
                    continue

                status = _enum_value(received_check.status)
                status_group = _check_status_group("RECEIVED", status)
                due_date = received_check.due_date
                amount = decimal_or_zero(received_check.amount)
                currency_code = _enum_value(received_check.currency_code) or "TRY"

                if current_month_start <= due_date <= current_month_end:
                    month_received_count += 1
                    _add_to_totals(month_received_currency_totals, currency_code, amount)

                if status_group == "PENDING":
                    pending_received_check_amount = (
                        pending_received_check_amount + amount
                    ).quantize(Decimal("0.01"))

                    if due_date == today:
                        due_today_count += 1
                        _add_to_totals(due_today_currency_totals, currency_code, amount)

                    if today <= due_date <= next_7_date:
                        next_7_received_count += 1
                        _add_to_totals(next_7_received_currency_totals, currency_code, amount)

                    if due_date < today:
                        overdue_pending_count += 1
                        _add_to_totals(overdue_pending_currency_totals, currency_code, amount)

                    urgency: str | None = None

                    if due_date < today:
                        urgency = "OVERDUE"
                    elif due_date == today:
                        urgency = "TODAY"
                    elif due_date <= next_7_date:
                        urgency = "WEEK"

                    if urgency is not None:
                        due_action_items.append(
                            DashboardDueItem(
                                check_type="RECEIVED",
                                check_id=received_check.id,
                                party_name=customer.name,
                                check_number=received_check.check_number,
                                due_date=due_date,
                                amount=amount,
                                currency_code=currency_code,
                                status=status,
                                status_text=_received_status_text(status),
                                urgency=urgency,
                                reference_no=received_check.reference_no,
                                description=received_check.description,
                            )
                        )

                if status_group == "PROBLEM":
                    problem_count += 1
                    _add_to_totals(problem_currency_totals, currency_code, amount)

                    due_action_items.append(
                        DashboardDueItem(
                            check_type="RECEIVED",
                            check_id=received_check.id,
                            party_name=customer.name,
                            check_number=received_check.check_number,
                            due_date=due_date,
                            amount=amount,
                            currency_code=currency_code,
                            status=status,
                            status_text=_received_status_text(status),
                            urgency="PROBLEM",
                            reference_no=received_check.reference_no,
                            description=received_check.description,
                        )
                    )

            issued_rows = session.execute(
                select(IssuedCheck, BusinessPartner)
                .join(BusinessPartner, IssuedCheck.supplier_id == BusinessPartner.id)
                .order_by(IssuedCheck.due_date.asc(), IssuedCheck.id.asc())
            ).all()

            for issued_check, supplier in issued_rows:
                if issued_check.due_date is None:
                    continue

                status = _enum_value(issued_check.status)
                status_group = _check_status_group("ISSUED", status)
                due_date = issued_check.due_date
                amount = decimal_or_zero(issued_check.amount)
                currency_code = _enum_value(issued_check.currency_code) or "TRY"

                if current_month_start <= due_date <= current_month_end:
                    month_issued_count += 1
                    _add_to_totals(month_issued_currency_totals, currency_code, amount)

                if status_group == "PENDING":
                    pending_issued_check_amount = (
                        pending_issued_check_amount + amount
                    ).quantize(Decimal("0.01"))

                    if due_date == today:
                        due_today_count += 1
                        _add_to_totals(due_today_currency_totals, currency_code, amount)

                    if today <= due_date <= next_7_date:
                        next_7_issued_count += 1
                        _add_to_totals(next_7_issued_currency_totals, currency_code, amount)

                    if due_date < today:
                        overdue_pending_count += 1
                        _add_to_totals(overdue_pending_currency_totals, currency_code, amount)

                    urgency = None

                    if due_date < today:
                        urgency = "OVERDUE"
                    elif due_date == today:
                        urgency = "TODAY"
                    elif due_date <= next_7_date:
                        urgency = "WEEK"

                    if urgency is not None:
                        due_action_items.append(
                            DashboardDueItem(
                                check_type="ISSUED",
                                check_id=issued_check.id,
                                party_name=supplier.name,
                                check_number=issued_check.check_number,
                                due_date=due_date,
                                amount=amount,
                                currency_code=currency_code,
                                status=status,
                                status_text=_issued_status_text(status),
                                urgency=urgency,
                                reference_no=issued_check.reference_no,
                                description=issued_check.description,
                            )
                        )

                if status_group == "PROBLEM":
                    problem_count += 1
                    _add_to_totals(problem_currency_totals, currency_code, amount)

                    due_action_items.append(
                        DashboardDueItem(
                            check_type="ISSUED",
                            check_id=issued_check.id,
                            party_name=supplier.name,
                            check_number=issued_check.check_number,
                            due_date=due_date,
                            amount=amount,
                            currency_code=currency_code,
                            status=status,
                            status_text=_issued_status_text(status),
                            urgency="PROBLEM",
                            reference_no=issued_check.reference_no,
                            description=issued_check.description,
                        )
                    )

            due_action_items.sort(
                key=lambda item: (
                    _action_priority(item.urgency),
                    item.due_date,
                    item.check_type,
                    item.party_name.lower(),
                    item.check_id,
                )
            )

            due_action_items = due_action_items[:12]

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
                due_today_count=due_today_count,
                due_today_currency_totals=due_today_currency_totals,
                next_7_received_count=next_7_received_count,
                next_7_received_currency_totals=next_7_received_currency_totals,
                next_7_issued_count=next_7_issued_count,
                next_7_issued_currency_totals=next_7_issued_currency_totals,
                overdue_pending_count=overdue_pending_count,
                overdue_pending_currency_totals=overdue_pending_currency_totals,
                problem_count=problem_count,
                problem_currency_totals=problem_currency_totals,
                month_received_count=month_received_count,
                month_received_currency_totals=month_received_currency_totals,
                month_issued_count=month_issued_count,
                month_issued_currency_totals=month_issued_currency_totals,
                due_action_items=due_action_items,
            )

    except Exception as exc:
        return _empty_dashboard_data(error_message=str(exc))