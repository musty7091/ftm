from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select

from app.db.session import session_scope
from app.models.business_partner import BusinessPartner
from app.models.check import IssuedCheck, ReceivedCheck


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


@dataclass(frozen=True)
class CheckDueReportFilter:
    start_date: date
    end_date: date
    check_type: str = "ALL"
    status_group: str = "ALL"
    currency_code: str = "ALL"


@dataclass(frozen=True)
class CheckDueReportRow:
    check_type: str
    check_type_text: str
    check_id: int
    party_name: str
    check_number: str
    due_date: date
    days_text: str
    days_difference: int
    amount: Decimal
    currency_code: str
    status: str
    status_text: str
    status_group: str
    status_group_text: str
    reference_no: str | None
    description: str | None
    row_style: str


@dataclass(frozen=True)
class CheckDueReportSummary:
    total_count: int

    received_count: int
    issued_count: int
    pending_count: int
    closed_count: int
    problem_count: int
    overdue_count: int
    today_count: int
    next_7_count: int
    next_15_count: int
    next_30_count: int

    received_totals: dict[str, Decimal]
    issued_totals: dict[str, Decimal]
    pending_totals: dict[str, Decimal]
    closed_totals: dict[str, Decimal]
    problem_totals: dict[str, Decimal]
    overdue_totals: dict[str, Decimal]
    today_totals: dict[str, Decimal]
    next_7_totals: dict[str, Decimal]
    next_15_totals: dict[str, Decimal]
    next_30_totals: dict[str, Decimal]
    net_effect_totals: dict[str, Decimal]


@dataclass(frozen=True)
class CheckDueReportData:
    filters: CheckDueReportFilter
    report_period_text: str
    rows: list[CheckDueReportRow]
    summary: CheckDueReportSummary


def _decimal_or_zero(value: Any) -> Decimal:
    if value is None:
        return Decimal("0.00")

    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except Exception:
        return Decimal("0.00")


def _enum_value(value: Any) -> str:
    if value is None:
        return ""

    if hasattr(value, "value"):
        return str(value.value).strip().upper()

    return str(value or "").strip().upper()


def _normalize_filter_value(value: Any, default_value: str = "ALL") -> str:
    normalized_value = str(value or default_value).strip().upper()

    if not normalized_value:
        return default_value

    return normalized_value


def _add_to_totals(
    totals: dict[str, Decimal],
    currency_code: str,
    amount: Decimal,
) -> None:
    normalized_currency_code = str(currency_code or "TRY").strip().upper() or "TRY"

    totals[normalized_currency_code] = (
        totals.get(normalized_currency_code, Decimal("0.00")) + _decimal_or_zero(amount)
    ).quantize(Decimal("0.01"))


def _subtract_from_totals(
    totals: dict[str, Decimal],
    currency_code: str,
    amount: Decimal,
) -> None:
    normalized_currency_code = str(currency_code or "TRY").strip().upper() or "TRY"

    totals[normalized_currency_code] = (
        totals.get(normalized_currency_code, Decimal("0.00")) - _decimal_or_zero(amount)
    ).quantize(Decimal("0.01"))


def _format_date_tr(value: date) -> str:
    return value.strftime("%d.%m.%Y")


def _days_text(target_date: date, today: date) -> str:
    difference = (target_date - today).days

    if difference == 0:
        return "Bugün"

    if difference > 0:
        return f"{difference} gün"

    return f"{abs(difference)} gün geçti"


def _check_status_group(check_type: str, status: str) -> str:
    normalized_check_type = str(check_type or "").strip().upper()
    normalized_status = str(status or "").strip().upper()

    if normalized_check_type == "RECEIVED":
        if normalized_status in RECEIVED_PENDING_STATUSES:
            return "PENDING"

        if normalized_status in RECEIVED_PROBLEM_STATUSES:
            return "PROBLEM"

        if normalized_status in RECEIVED_CLOSED_STATUSES:
            return "CLOSED"

    if normalized_check_type == "ISSUED":
        if normalized_status in ISSUED_PENDING_STATUSES:
            return "PENDING"

        if normalized_status in ISSUED_PROBLEM_STATUSES:
            return "PROBLEM"

        if normalized_status in ISSUED_CLOSED_STATUSES:
            return "CLOSED"

    return "ALL"


def _status_group_text(status_group: str) -> str:
    normalized_status_group = str(status_group or "").strip().upper()

    if normalized_status_group == "PENDING":
        return "Bekleyen"

    if normalized_status_group == "CLOSED":
        return "Sonuçlanan"

    if normalized_status_group == "PROBLEM":
        return "Problemli"

    return "Diğer"


def _received_status_text(status: Any) -> str:
    normalized_status = _enum_value(status)

    return RECEIVED_STATUS_TEXTS.get(normalized_status, normalized_status or "-")


def _issued_status_text(status: Any) -> str:
    normalized_status = _enum_value(status)

    return ISSUED_STATUS_TEXTS.get(normalized_status, normalized_status or "-")


def _row_style_for_report(
    *,
    check_type: str,
    status_group: str,
    due_date: date,
    today: date,
) -> str:
    if status_group == "PROBLEM":
        return "PROBLEM"

    if status_group == "PENDING" and due_date < today:
        return "OVERDUE"

    if status_group == "CLOSED":
        return "CLOSED"

    if check_type == "RECEIVED":
        return "RECEIVED"

    if check_type == "ISSUED":
        return "ISSUED"

    return "NORMAL"


def _should_include_row(
    *,
    row_check_type: str,
    row_status_group: str,
    row_currency_code: str,
    check_type_filter: str,
    status_group_filter: str,
    currency_code_filter: str,
) -> bool:
    if check_type_filter != "ALL" and row_check_type != check_type_filter:
        return False

    if status_group_filter != "ALL" and row_status_group != status_group_filter:
        return False

    if currency_code_filter != "ALL" and row_currency_code != currency_code_filter:
        return False

    return True


def _build_summary(
    *,
    rows: list[CheckDueReportRow],
    today: date,
) -> CheckDueReportSummary:
    received_count = 0
    issued_count = 0
    pending_count = 0
    closed_count = 0
    problem_count = 0
    overdue_count = 0
    today_count = 0
    next_7_count = 0
    next_15_count = 0
    next_30_count = 0

    received_totals: dict[str, Decimal] = {}
    issued_totals: dict[str, Decimal] = {}
    pending_totals: dict[str, Decimal] = {}
    closed_totals: dict[str, Decimal] = {}
    problem_totals: dict[str, Decimal] = {}
    overdue_totals: dict[str, Decimal] = {}
    today_totals: dict[str, Decimal] = {}
    next_7_totals: dict[str, Decimal] = {}
    next_15_totals: dict[str, Decimal] = {}
    next_30_totals: dict[str, Decimal] = {}
    net_effect_totals: dict[str, Decimal] = {}

    for row in rows:
        if row.check_type == "RECEIVED":
            received_count += 1
            _add_to_totals(received_totals, row.currency_code, row.amount)
            _add_to_totals(net_effect_totals, row.currency_code, row.amount)

        if row.check_type == "ISSUED":
            issued_count += 1
            _add_to_totals(issued_totals, row.currency_code, row.amount)
            _subtract_from_totals(net_effect_totals, row.currency_code, row.amount)

        if row.status_group == "PENDING":
            pending_count += 1
            _add_to_totals(pending_totals, row.currency_code, row.amount)

        if row.status_group == "CLOSED":
            closed_count += 1
            _add_to_totals(closed_totals, row.currency_code, row.amount)

        if row.status_group == "PROBLEM":
            problem_count += 1
            _add_to_totals(problem_totals, row.currency_code, row.amount)

        if row.status_group == "PENDING" and row.due_date < today:
            overdue_count += 1
            _add_to_totals(overdue_totals, row.currency_code, row.amount)

        if row.due_date == today:
            today_count += 1
            _add_to_totals(today_totals, row.currency_code, row.amount)

        if today <= row.due_date <= today + timedelta(days=7):
            next_7_count += 1
            _add_to_totals(next_7_totals, row.currency_code, row.amount)

        if today <= row.due_date <= today + timedelta(days=15):
            next_15_count += 1
            _add_to_totals(next_15_totals, row.currency_code, row.amount)

        if today <= row.due_date <= today + timedelta(days=30):
            next_30_count += 1
            _add_to_totals(next_30_totals, row.currency_code, row.amount)

    return CheckDueReportSummary(
        total_count=len(rows),
        received_count=received_count,
        issued_count=issued_count,
        pending_count=pending_count,
        closed_count=closed_count,
        problem_count=problem_count,
        overdue_count=overdue_count,
        today_count=today_count,
        next_7_count=next_7_count,
        next_15_count=next_15_count,
        next_30_count=next_30_count,
        received_totals=received_totals,
        issued_totals=issued_totals,
        pending_totals=pending_totals,
        closed_totals=closed_totals,
        problem_totals=problem_totals,
        overdue_totals=overdue_totals,
        today_totals=today_totals,
        next_7_totals=next_7_totals,
        next_15_totals=next_15_totals,
        next_30_totals=next_30_totals,
        net_effect_totals=net_effect_totals,
    )


def load_check_due_report_data(
    report_filter: CheckDueReportFilter,
) -> CheckDueReportData:
    today = date.today()

    start_date = report_filter.start_date
    end_date = report_filter.end_date

    check_type_filter = _normalize_filter_value(report_filter.check_type)
    status_group_filter = _normalize_filter_value(report_filter.status_group)
    currency_code_filter = _normalize_filter_value(report_filter.currency_code)

    if end_date < start_date:
        raise ValueError("Bitiş tarihi başlangıç tarihinden küçük olamaz.")

    rows: list[CheckDueReportRow] = []

    with session_scope() as session:
        if check_type_filter in {"ALL", "RECEIVED"}:
            received_statement = (
                select(ReceivedCheck, BusinessPartner)
                .join(BusinessPartner, ReceivedCheck.customer_id == BusinessPartner.id)
                .where(
                    ReceivedCheck.due_date >= start_date,
                    ReceivedCheck.due_date <= end_date,
                )
                .order_by(
                    ReceivedCheck.due_date.asc(),
                    ReceivedCheck.id.asc(),
                )
            )

            received_rows = session.execute(received_statement).all()

            for received_check, customer in received_rows:
                due_date = received_check.due_date

                if due_date is None:
                    continue

                status = _enum_value(received_check.status)
                status_group = _check_status_group("RECEIVED", status)
                currency_code = _enum_value(received_check.currency_code) or "TRY"
                amount = _decimal_or_zero(received_check.amount)

                if not _should_include_row(
                    row_check_type="RECEIVED",
                    row_status_group=status_group,
                    row_currency_code=currency_code,
                    check_type_filter=check_type_filter,
                    status_group_filter=status_group_filter,
                    currency_code_filter=currency_code_filter,
                ):
                    continue

                days_difference = (due_date - today).days

                rows.append(
                    CheckDueReportRow(
                        check_type="RECEIVED",
                        check_type_text="Alınan",
                        check_id=received_check.id,
                        party_name=customer.name,
                        check_number=received_check.check_number,
                        due_date=due_date,
                        days_text=_days_text(due_date, today),
                        days_difference=days_difference,
                        amount=amount,
                        currency_code=currency_code,
                        status=status,
                        status_text=_received_status_text(status),
                        status_group=status_group,
                        status_group_text=_status_group_text(status_group),
                        reference_no=received_check.reference_no,
                        description=received_check.description,
                        row_style=_row_style_for_report(
                            check_type="RECEIVED",
                            status_group=status_group,
                            due_date=due_date,
                            today=today,
                        ),
                    )
                )

        if check_type_filter in {"ALL", "ISSUED"}:
            issued_statement = (
                select(IssuedCheck, BusinessPartner)
                .join(BusinessPartner, IssuedCheck.supplier_id == BusinessPartner.id)
                .where(
                    IssuedCheck.due_date >= start_date,
                    IssuedCheck.due_date <= end_date,
                )
                .order_by(
                    IssuedCheck.due_date.asc(),
                    IssuedCheck.id.asc(),
                )
            )

            issued_rows = session.execute(issued_statement).all()

            for issued_check, supplier in issued_rows:
                due_date = issued_check.due_date

                if due_date is None:
                    continue

                status = _enum_value(issued_check.status)
                status_group = _check_status_group("ISSUED", status)
                currency_code = _enum_value(issued_check.currency_code) or "TRY"
                amount = _decimal_or_zero(issued_check.amount)

                if not _should_include_row(
                    row_check_type="ISSUED",
                    row_status_group=status_group,
                    row_currency_code=currency_code,
                    check_type_filter=check_type_filter,
                    status_group_filter=status_group_filter,
                    currency_code_filter=currency_code_filter,
                ):
                    continue

                days_difference = (due_date - today).days

                rows.append(
                    CheckDueReportRow(
                        check_type="ISSUED",
                        check_type_text="Yazılan",
                        check_id=issued_check.id,
                        party_name=supplier.name,
                        check_number=issued_check.check_number,
                        due_date=due_date,
                        days_text=_days_text(due_date, today),
                        days_difference=days_difference,
                        amount=amount,
                        currency_code=currency_code,
                        status=status,
                        status_text=_issued_status_text(status),
                        status_group=status_group,
                        status_group_text=_status_group_text(status_group),
                        reference_no=issued_check.reference_no,
                        description=issued_check.description,
                        row_style=_row_style_for_report(
                            check_type="ISSUED",
                            status_group=status_group,
                            due_date=due_date,
                            today=today,
                        ),
                    )
                )

    rows.sort(
        key=lambda row: (
            row.due_date,
            0 if row.check_type == "RECEIVED" else 1,
            row.party_name.lower(),
            row.check_id,
        )
    )

    summary = _build_summary(
        rows=rows,
        today=today,
    )

    return CheckDueReportData(
        filters=CheckDueReportFilter(
            start_date=start_date,
            end_date=end_date,
            check_type=check_type_filter,
            status_group=status_group_filter,
            currency_code=currency_code_filter,
        ),
        report_period_text=f"{_format_date_tr(start_date)} - {_format_date_tr(end_date)}",
        rows=rows,
        summary=summary,
    )


def load_default_next_30_days_check_due_report_data() -> CheckDueReportData:
    today = date.today()

    return load_check_due_report_data(
        CheckDueReportFilter(
            start_date=today,
            end_date=today + timedelta(days=30),
            check_type="ALL",
            status_group="ALL",
            currency_code="ALL",
        )
    )