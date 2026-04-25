from __future__ import annotations

from dataclasses import dataclass
from datetime import date
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
class RiskCheckReportFilter:
    start_date: date
    end_date: date
    check_type: str = "ALL"
    risk_type: str = "ALL"
    currency_code: str = "ALL"


@dataclass(frozen=True)
class RiskCheckReportRow:
    risk_type: str
    risk_type_text: str
    check_type: str
    check_type_text: str
    check_id: int
    party_name: str
    check_number: str
    due_date: date
    delay_days: int
    delay_text: str
    amount: Decimal
    currency_code: str
    status: str
    status_text: str
    reference_no: str | None
    description: str | None
    row_style: str


@dataclass(frozen=True)
class RiskCheckPartySummary:
    party_name: str
    record_count: int
    totals: dict[str, Decimal]


@dataclass(frozen=True)
class RiskCheckReportSummary:
    total_count: int

    received_problem_count: int
    issued_problem_count: int
    received_overdue_count: int
    issued_overdue_count: int

    problem_count: int
    overdue_count: int

    received_problem_totals: dict[str, Decimal]
    issued_problem_totals: dict[str, Decimal]
    received_overdue_totals: dict[str, Decimal]
    issued_overdue_totals: dict[str, Decimal]

    problem_totals: dict[str, Decimal]
    overdue_totals: dict[str, Decimal]
    grand_totals: dict[str, Decimal]

    party_summaries: list[RiskCheckPartySummary]


@dataclass(frozen=True)
class RiskCheckReportData:
    filters: RiskCheckReportFilter
    report_period_text: str
    rows: list[RiskCheckReportRow]
    summary: RiskCheckReportSummary


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


def _merge_totals(
    target: dict[str, Decimal],
    source: dict[str, Decimal],
) -> None:
    for currency_code, amount in source.items():
        _add_to_totals(target, currency_code, amount)


def _format_date_tr(value: date) -> str:
    return value.strftime("%d.%m.%Y")


def _delay_text(delay_days: int) -> str:
    if delay_days <= 0:
        return "Bugün / henüz gecikmedi"

    return f"{delay_days} gün gecikti"


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


def _received_status_text(status: Any) -> str:
    normalized_status = _enum_value(status)

    return RECEIVED_STATUS_TEXTS.get(normalized_status, normalized_status or "-")


def _issued_status_text(status: Any) -> str:
    normalized_status = _enum_value(status)

    return ISSUED_STATUS_TEXTS.get(normalized_status, normalized_status or "-")


def _should_include_row(
    *,
    row_check_type: str,
    row_risk_type: str,
    row_currency_code: str,
    check_type_filter: str,
    risk_type_filter: str,
    currency_code_filter: str,
) -> bool:
    if check_type_filter != "ALL" and row_check_type != check_type_filter:
        return False

    if risk_type_filter != "ALL" and row_risk_type != risk_type_filter:
        return False

    if currency_code_filter != "ALL" and row_currency_code != currency_code_filter:
        return False

    return True


def _build_party_summaries(
    rows: list[RiskCheckReportRow],
) -> list[RiskCheckPartySummary]:
    grouped: dict[str, dict[str, Any]] = {}

    for row in rows:
        party_name = row.party_name or "-"

        if party_name not in grouped:
            grouped[party_name] = {
                "record_count": 0,
                "totals": {},
            }

        grouped[party_name]["record_count"] += 1
        _add_to_totals(
            grouped[party_name]["totals"],
            row.currency_code,
            row.amount,
        )

    party_summaries: list[RiskCheckPartySummary] = []

    for party_name, values in grouped.items():
        party_summaries.append(
            RiskCheckPartySummary(
                party_name=party_name,
                record_count=int(values["record_count"]),
                totals=dict(values["totals"]),
            )
        )

    party_summaries.sort(
        key=lambda item: (
            -item.record_count,
            item.party_name.lower(),
        )
    )

    return party_summaries[:10]


def _build_summary(
    rows: list[RiskCheckReportRow],
) -> RiskCheckReportSummary:
    received_problem_count = 0
    issued_problem_count = 0
    received_overdue_count = 0
    issued_overdue_count = 0

    problem_count = 0
    overdue_count = 0

    received_problem_totals: dict[str, Decimal] = {}
    issued_problem_totals: dict[str, Decimal] = {}
    received_overdue_totals: dict[str, Decimal] = {}
    issued_overdue_totals: dict[str, Decimal] = {}

    problem_totals: dict[str, Decimal] = {}
    overdue_totals: dict[str, Decimal] = {}
    grand_totals: dict[str, Decimal] = {}

    for row in rows:
        _add_to_totals(grand_totals, row.currency_code, row.amount)

        if row.risk_type == "PROBLEM":
            problem_count += 1
            _add_to_totals(problem_totals, row.currency_code, row.amount)

            if row.check_type == "RECEIVED":
                received_problem_count += 1
                _add_to_totals(received_problem_totals, row.currency_code, row.amount)

            if row.check_type == "ISSUED":
                issued_problem_count += 1
                _add_to_totals(issued_problem_totals, row.currency_code, row.amount)

        if row.risk_type == "OVERDUE":
            overdue_count += 1
            _add_to_totals(overdue_totals, row.currency_code, row.amount)

            if row.check_type == "RECEIVED":
                received_overdue_count += 1
                _add_to_totals(received_overdue_totals, row.currency_code, row.amount)

            if row.check_type == "ISSUED":
                issued_overdue_count += 1
                _add_to_totals(issued_overdue_totals, row.currency_code, row.amount)

    return RiskCheckReportSummary(
        total_count=len(rows),
        received_problem_count=received_problem_count,
        issued_problem_count=issued_problem_count,
        received_overdue_count=received_overdue_count,
        issued_overdue_count=issued_overdue_count,
        problem_count=problem_count,
        overdue_count=overdue_count,
        received_problem_totals=received_problem_totals,
        issued_problem_totals=issued_problem_totals,
        received_overdue_totals=received_overdue_totals,
        issued_overdue_totals=issued_overdue_totals,
        problem_totals=problem_totals,
        overdue_totals=overdue_totals,
        grand_totals=grand_totals,
        party_summaries=_build_party_summaries(rows),
    )


def _build_risk_row(
    *,
    risk_type: str,
    check_type: str,
    check_id: int,
    party_name: str,
    check_number: str,
    due_date: date,
    amount: Decimal,
    currency_code: str,
    status: str,
    status_text: str,
    reference_no: str | None,
    description: str | None,
    today: date,
) -> RiskCheckReportRow:
    normalized_risk_type = str(risk_type or "").strip().upper()
    normalized_check_type = str(check_type or "").strip().upper()

    if normalized_risk_type == "OVERDUE":
        risk_type_text = "Vadesi Geçmiş"
        row_style = "OVERDUE"
    elif normalized_risk_type == "PROBLEM":
        risk_type_text = "Problemli / Riskli"
        row_style = "PROBLEM"
    else:
        risk_type_text = "Diğer"
        row_style = "NORMAL"

    if normalized_check_type == "RECEIVED":
        check_type_text = "Alınan"
    elif normalized_check_type == "ISSUED":
        check_type_text = "Yazılan"
    else:
        check_type_text = normalized_check_type or "-"

    delay_days = max(0, (today - due_date).days)

    return RiskCheckReportRow(
        risk_type=normalized_risk_type,
        risk_type_text=risk_type_text,
        check_type=normalized_check_type,
        check_type_text=check_type_text,
        check_id=check_id,
        party_name=party_name,
        check_number=check_number,
        due_date=due_date,
        delay_days=delay_days,
        delay_text=_delay_text(delay_days),
        amount=_decimal_or_zero(amount),
        currency_code=currency_code,
        status=status,
        status_text=status_text,
        reference_no=reference_no,
        description=description,
        row_style=row_style,
    )


def load_risk_check_report_data(
    report_filter: RiskCheckReportFilter,
) -> RiskCheckReportData:
    today = date.today()

    start_date = report_filter.start_date
    end_date = report_filter.end_date

    if end_date < start_date:
        raise ValueError("Bitiş tarihi başlangıç tarihinden küçük olamaz.")

    check_type_filter = _normalize_filter_value(report_filter.check_type)
    risk_type_filter = _normalize_filter_value(report_filter.risk_type)
    currency_code_filter = _normalize_filter_value(report_filter.currency_code)

    rows: list[RiskCheckReportRow] = []

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
                amount = _decimal_or_zero(received_check.amount)
                currency_code = _enum_value(received_check.currency_code) or "TRY"

                risk_type: str | None = None

                if status_group == "PROBLEM":
                    risk_type = "PROBLEM"
                elif status_group == "PENDING" and due_date < today:
                    risk_type = "OVERDUE"

                if risk_type is None:
                    continue

                if not _should_include_row(
                    row_check_type="RECEIVED",
                    row_risk_type=risk_type,
                    row_currency_code=currency_code,
                    check_type_filter=check_type_filter,
                    risk_type_filter=risk_type_filter,
                    currency_code_filter=currency_code_filter,
                ):
                    continue

                rows.append(
                    _build_risk_row(
                        risk_type=risk_type,
                        check_type="RECEIVED",
                        check_id=received_check.id,
                        party_name=customer.name,
                        check_number=received_check.check_number,
                        due_date=due_date,
                        amount=amount,
                        currency_code=currency_code,
                        status=status,
                        status_text=_received_status_text(status),
                        reference_no=received_check.reference_no,
                        description=received_check.description,
                        today=today,
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
                amount = _decimal_or_zero(issued_check.amount)
                currency_code = _enum_value(issued_check.currency_code) or "TRY"

                risk_type = None

                if status_group == "PROBLEM":
                    risk_type = "PROBLEM"
                elif status_group == "PENDING" and due_date < today:
                    risk_type = "OVERDUE"

                if risk_type is None:
                    continue

                if not _should_include_row(
                    row_check_type="ISSUED",
                    row_risk_type=risk_type,
                    row_currency_code=currency_code,
                    check_type_filter=check_type_filter,
                    risk_type_filter=risk_type_filter,
                    currency_code_filter=currency_code_filter,
                ):
                    continue

                rows.append(
                    _build_risk_row(
                        risk_type=risk_type,
                        check_type="ISSUED",
                        check_id=issued_check.id,
                        party_name=supplier.name,
                        check_number=issued_check.check_number,
                        due_date=due_date,
                        amount=amount,
                        currency_code=currency_code,
                        status=status,
                        status_text=_issued_status_text(status),
                        reference_no=issued_check.reference_no,
                        description=issued_check.description,
                        today=today,
                    )
                )

    rows.sort(
        key=lambda row: (
            0 if row.risk_type == "PROBLEM" else 1,
            row.due_date,
            0 if row.check_type == "RECEIVED" else 1,
            row.party_name.lower(),
            row.check_id,
        )
    )

    summary = _build_summary(rows)

    return RiskCheckReportData(
        filters=RiskCheckReportFilter(
            start_date=start_date,
            end_date=end_date,
            check_type=check_type_filter,
            risk_type=risk_type_filter,
            currency_code=currency_code_filter,
        ),
        report_period_text=f"{_format_date_tr(start_date)} - {_format_date_tr(end_date)}",
        rows=rows,
        summary=summary,
    )


def load_default_current_year_risk_check_report_data() -> RiskCheckReportData:
    today = date.today()

    return load_risk_check_report_data(
        RiskCheckReportFilter(
            start_date=date(today.year, 1, 1),
            end_date=date(today.year, 12, 31),
            check_type="ALL",
            risk_type="ALL",
            currency_code="ALL",
        )
    )