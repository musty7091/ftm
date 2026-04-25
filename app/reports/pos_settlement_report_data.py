from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select

from app.db.session import session_scope
from app.models.bank import Bank, BankAccount
from app.models.pos import PosDevice, PosSettlement


STATUS_TEXTS = {
    "PLANNED": "Planlandı",
    "REALIZED": "Gerçekleşti",
    "CANCELLED": "İptal Edildi",
    "MISMATCH": "Fark Var",
}


@dataclass(frozen=True)
class PosSettlementReportFilter:
    start_date: date
    end_date: date
    pos_device_id: int | None = None
    bank_id: int | None = None
    bank_account_id: int | None = None
    status: str = "ALL"
    currency_code: str = "ALL"


@dataclass(frozen=True)
class PosSettlementReportRow:
    settlement_id: int
    pos_device_id: int
    pos_device_name: str
    terminal_no: str | None

    bank_id: int
    bank_name: str
    bank_account_id: int
    account_name: str

    transaction_date: date
    expected_settlement_date: date
    realized_settlement_date: date | None

    gross_amount: Decimal
    commission_rate: Decimal
    commission_amount: Decimal
    net_amount: Decimal
    actual_net_amount: Decimal | None
    difference_amount: Decimal

    currency_code: str
    status: str
    status_text: str
    reference_no: str | None
    description: str | None
    difference_reason: str | None
    row_style: str


@dataclass(frozen=True)
class PosSettlementDeviceSummary:
    pos_device_id: int
    pos_device_name: str
    terminal_no: str | None
    bank_name: str
    account_name: str
    currency_code: str

    record_count: int
    planned_count: int
    realized_count: int
    cancelled_count: int
    mismatch_count: int

    gross_totals: dict[str, Decimal]
    commission_totals: dict[str, Decimal]
    expected_net_totals: dict[str, Decimal]
    actual_net_totals: dict[str, Decimal]
    difference_totals: dict[str, Decimal]


@dataclass(frozen=True)
class PosSettlementReportSummary:
    total_count: int
    planned_count: int
    realized_count: int
    cancelled_count: int
    mismatch_count: int

    gross_totals: dict[str, Decimal]
    commission_totals: dict[str, Decimal]
    expected_net_totals: dict[str, Decimal]
    actual_net_totals: dict[str, Decimal]
    difference_totals: dict[str, Decimal]

    device_summaries: list[PosSettlementDeviceSummary]


@dataclass(frozen=True)
class PosSettlementReportData:
    filters: PosSettlementReportFilter
    report_period_text: str
    rows: list[PosSettlementReportRow]
    summary: PosSettlementReportSummary


def _decimal_or_zero(value: Any) -> Decimal:
    if value is None:
        return Decimal("0.00")

    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except Exception:
        return Decimal("0.00")


def _rate_or_zero(value: Any) -> Decimal:
    if value is None:
        return Decimal("0.000000")

    try:
        return Decimal(str(value)).quantize(Decimal("0.000001"))
    except Exception:
        return Decimal("0.000000")


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
        totals.get(normalized_currency_code, Decimal("0.00"))
        + _decimal_or_zero(amount)
    ).quantize(Decimal("0.01"))


def _format_date_tr(value: date) -> str:
    return value.strftime("%d.%m.%Y")


def _status_text(status: Any) -> str:
    normalized_status = _enum_value(status)

    return STATUS_TEXTS.get(normalized_status, normalized_status or "-")


def _row_style_for_report(status: str, difference_amount: Decimal) -> str:
    normalized_status = str(status or "").strip().upper()

    if normalized_status == "CANCELLED":
        return "MUTED"

    if normalized_status == "MISMATCH":
        return "PROBLEM"

    if _decimal_or_zero(difference_amount) != Decimal("0.00"):
        return "WARNING"

    if normalized_status == "REALIZED":
        return "SUCCESS"

    if normalized_status == "PLANNED":
        return "WARNING"

    return "NORMAL"


def _should_include_row(
    *,
    row_status: str,
    row_currency_code: str,
    status_filter: str,
    currency_code_filter: str,
) -> bool:
    if status_filter != "ALL" and row_status != status_filter:
        return False

    if currency_code_filter != "ALL" and row_currency_code != currency_code_filter:
        return False

    return True


def _build_device_summaries(
    rows: list[PosSettlementReportRow],
) -> list[PosSettlementDeviceSummary]:
    grouped: dict[int, dict[str, Any]] = {}

    for row in rows:
        if row.pos_device_id not in grouped:
            grouped[row.pos_device_id] = {
                "pos_device_id": row.pos_device_id,
                "pos_device_name": row.pos_device_name,
                "terminal_no": row.terminal_no,
                "bank_name": row.bank_name,
                "account_name": row.account_name,
                "currency_code": row.currency_code,
                "record_count": 0,
                "planned_count": 0,
                "realized_count": 0,
                "cancelled_count": 0,
                "mismatch_count": 0,
                "gross_totals": {},
                "commission_totals": {},
                "expected_net_totals": {},
                "actual_net_totals": {},
                "difference_totals": {},
            }

        device_data = grouped[row.pos_device_id]
        device_data["record_count"] += 1

        if row.status == "PLANNED":
            device_data["planned_count"] += 1

        if row.status == "REALIZED":
            device_data["realized_count"] += 1

        if row.status == "CANCELLED":
            device_data["cancelled_count"] += 1

        if row.status == "MISMATCH":
            device_data["mismatch_count"] += 1

        if row.status == "CANCELLED":
            continue

        _add_to_totals(
            device_data["gross_totals"],
            row.currency_code,
            row.gross_amount,
        )
        _add_to_totals(
            device_data["commission_totals"],
            row.currency_code,
            row.commission_amount,
        )
        _add_to_totals(
            device_data["expected_net_totals"],
            row.currency_code,
            row.net_amount,
        )
        _add_to_totals(
            device_data["actual_net_totals"],
            row.currency_code,
            _decimal_or_zero(row.actual_net_amount),
        )
        _add_to_totals(
            device_data["difference_totals"],
            row.currency_code,
            row.difference_amount,
        )

    device_summaries: list[PosSettlementDeviceSummary] = []

    for values in grouped.values():
        device_summaries.append(
            PosSettlementDeviceSummary(
                pos_device_id=int(values["pos_device_id"]),
                pos_device_name=str(values["pos_device_name"]),
                terminal_no=values["terminal_no"],
                bank_name=str(values["bank_name"]),
                account_name=str(values["account_name"]),
                currency_code=str(values["currency_code"]),
                record_count=int(values["record_count"]),
                planned_count=int(values["planned_count"]),
                realized_count=int(values["realized_count"]),
                cancelled_count=int(values["cancelled_count"]),
                mismatch_count=int(values["mismatch_count"]),
                gross_totals=dict(values["gross_totals"]),
                commission_totals=dict(values["commission_totals"]),
                expected_net_totals=dict(values["expected_net_totals"]),
                actual_net_totals=dict(values["actual_net_totals"]),
                difference_totals=dict(values["difference_totals"]),
            )
        )

    device_summaries.sort(
        key=lambda item: (
            item.bank_name.lower(),
            item.pos_device_name.lower(),
            item.currency_code,
        )
    )

    return device_summaries


def _build_summary(
    rows: list[PosSettlementReportRow],
) -> PosSettlementReportSummary:
    planned_count = 0
    realized_count = 0
    cancelled_count = 0
    mismatch_count = 0

    gross_totals: dict[str, Decimal] = {}
    commission_totals: dict[str, Decimal] = {}
    expected_net_totals: dict[str, Decimal] = {}
    actual_net_totals: dict[str, Decimal] = {}
    difference_totals: dict[str, Decimal] = {}

    for row in rows:
        if row.status == "PLANNED":
            planned_count += 1

        if row.status == "REALIZED":
            realized_count += 1

        if row.status == "CANCELLED":
            cancelled_count += 1
            continue

        if row.status == "MISMATCH":
            mismatch_count += 1

        _add_to_totals(gross_totals, row.currency_code, row.gross_amount)
        _add_to_totals(commission_totals, row.currency_code, row.commission_amount)
        _add_to_totals(expected_net_totals, row.currency_code, row.net_amount)
        _add_to_totals(actual_net_totals, row.currency_code, _decimal_or_zero(row.actual_net_amount))
        _add_to_totals(difference_totals, row.currency_code, row.difference_amount)

    return PosSettlementReportSummary(
        total_count=len(rows),
        planned_count=planned_count,
        realized_count=realized_count,
        cancelled_count=cancelled_count,
        mismatch_count=mismatch_count,
        gross_totals=gross_totals,
        commission_totals=commission_totals,
        expected_net_totals=expected_net_totals,
        actual_net_totals=actual_net_totals,
        difference_totals=difference_totals,
        device_summaries=_build_device_summaries(rows),
    )


def _build_row(
    *,
    settlement: PosSettlement,
    pos_device: PosDevice,
    bank_account: BankAccount,
    bank: Bank,
) -> PosSettlementReportRow:
    status = _enum_value(settlement.status)
    currency_code = _enum_value(settlement.currency_code) or "TRY"
    difference_amount = _decimal_or_zero(settlement.difference_amount)

    return PosSettlementReportRow(
        settlement_id=settlement.id,
        pos_device_id=pos_device.id,
        pos_device_name=pos_device.name,
        terminal_no=pos_device.terminal_no,
        bank_id=bank.id,
        bank_name=bank.name,
        bank_account_id=bank_account.id,
        account_name=bank_account.account_name,
        transaction_date=settlement.transaction_date,
        expected_settlement_date=settlement.expected_settlement_date,
        realized_settlement_date=settlement.realized_settlement_date,
        gross_amount=_decimal_or_zero(settlement.gross_amount),
        commission_rate=_rate_or_zero(settlement.commission_rate),
        commission_amount=_decimal_or_zero(settlement.commission_amount),
        net_amount=_decimal_or_zero(settlement.net_amount),
        actual_net_amount=(
            None
            if settlement.actual_net_amount is None
            else _decimal_or_zero(settlement.actual_net_amount)
        ),
        difference_amount=difference_amount,
        currency_code=currency_code,
        status=status,
        status_text=_status_text(status),
        reference_no=settlement.reference_no,
        description=settlement.description,
        difference_reason=settlement.difference_reason,
        row_style=_row_style_for_report(
            status=status,
            difference_amount=difference_amount,
        ),
    )


def load_pos_settlement_report_data(
    report_filter: PosSettlementReportFilter,
) -> PosSettlementReportData:
    start_date = report_filter.start_date
    end_date = report_filter.end_date

    if end_date < start_date:
        raise ValueError("Bitiş tarihi başlangıç tarihinden küçük olamaz.")

    status_filter = _normalize_filter_value(report_filter.status)
    currency_code_filter = _normalize_filter_value(report_filter.currency_code)

    rows: list[PosSettlementReportRow] = []

    with session_scope() as session:
        statement = (
            select(PosSettlement, PosDevice, BankAccount, Bank)
            .join(PosDevice, PosSettlement.pos_device_id == PosDevice.id)
            .join(BankAccount, PosDevice.bank_account_id == BankAccount.id)
            .join(Bank, BankAccount.bank_id == Bank.id)
            .where(
                PosSettlement.transaction_date >= start_date,
                PosSettlement.transaction_date <= end_date,
            )
            .order_by(
                PosSettlement.transaction_date.asc(),
                Bank.name.asc(),
                PosDevice.name.asc(),
                PosSettlement.id.asc(),
            )
        )

        if report_filter.pos_device_id is not None:
            statement = statement.where(PosDevice.id == report_filter.pos_device_id)

        if report_filter.bank_id is not None:
            statement = statement.where(Bank.id == report_filter.bank_id)

        if report_filter.bank_account_id is not None:
            statement = statement.where(BankAccount.id == report_filter.bank_account_id)

        result_rows = session.execute(statement).all()

        for settlement, pos_device, bank_account, bank in result_rows:
            row = _build_row(
                settlement=settlement,
                pos_device=pos_device,
                bank_account=bank_account,
                bank=bank,
            )

            if not _should_include_row(
                row_status=row.status,
                row_currency_code=row.currency_code,
                status_filter=status_filter,
                currency_code_filter=currency_code_filter,
            ):
                continue

            rows.append(row)

    summary = _build_summary(rows)

    return PosSettlementReportData(
        filters=PosSettlementReportFilter(
            start_date=start_date,
            end_date=end_date,
            pos_device_id=report_filter.pos_device_id,
            bank_id=report_filter.bank_id,
            bank_account_id=report_filter.bank_account_id,
            status=status_filter,
            currency_code=currency_code_filter,
        ),
        report_period_text=f"{_format_date_tr(start_date)} - {_format_date_tr(end_date)}",
        rows=rows,
        summary=summary,
    )


def load_default_current_month_pos_settlement_report_data() -> PosSettlementReportData:
    today = date.today()
    start_date = date(today.year, today.month, 1)

    if today.month == 12:
        end_date = date(today.year, 12, 31)
    else:
        end_date = date(today.year, today.month + 1, 1) - timedelta(days=1)

    return load_pos_settlement_report_data(
        PosSettlementReportFilter(
            start_date=start_date,
            end_date=end_date,
            pos_device_id=None,
            bank_id=None,
            bank_account_id=None,
            status="ALL",
            currency_code="ALL",
        )
    )