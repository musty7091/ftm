from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from app.reports.discount_batch_report_data import (
    DiscountBatchReportBatchRow,
    DiscountBatchReportData,
    DiscountBatchReportFilter,
    DiscountBatchReportItemRow,
    load_discount_batch_report_data,
)


@dataclass(frozen=True)
class FinancingCostReportFilter:
    start_date: date
    end_date: date
    bank_id: int | None = None
    bank_account_id: int | None = None
    discount_batch_id: int | None = None
    currency_code: str = "ALL"


@dataclass(frozen=True)
class FinancingCostReportRow:
    batch_id: int
    bank_id: int
    bank_name: str
    bank_account_id: int
    account_name: str
    discount_date: date
    currency_code: str

    check_count: int
    average_days_to_due: Decimal
    day_basis: int

    annual_interest_rate: Decimal
    commission_rate: Decimal
    bsiv_rate: Decimal

    total_gross_amount: Decimal
    total_interest_expense_amount: Decimal
    total_commission_amount: Decimal
    total_bsiv_amount: Decimal
    total_discount_expense_amount: Decimal
    net_bank_amount: Decimal

    interest_ratio: Decimal
    commission_ratio: Decimal
    bsiv_ratio: Decimal
    total_expense_ratio: Decimal
    net_ratio: Decimal

    reference_no: str | None
    description: str | None
    row_style: str


@dataclass(frozen=True)
class FinancingCostReportCheckRow:
    item_id: int
    batch_id: int
    received_check_id: int
    check_number: str
    customer_name: str
    drawer_bank_name: str
    due_date: date
    days_to_due: int
    gross_amount: Decimal
    interest_expense_amount: Decimal
    commission_amount: Decimal
    bsiv_amount: Decimal
    total_expense_amount: Decimal
    net_amount: Decimal
    currency_code: str
    expense_ratio: Decimal
    row_style: str


@dataclass(frozen=True)
class FinancingCostBankSummary:
    bank_id: int
    bank_name: str
    bank_account_id: int
    account_name: str
    currency_code: str

    batch_count: int
    check_count: int
    average_days_to_due: Decimal

    total_gross_amount: Decimal
    total_interest_expense_amount: Decimal
    total_commission_amount: Decimal
    total_bsiv_amount: Decimal
    total_discount_expense_amount: Decimal
    net_bank_amount: Decimal

    interest_ratio: Decimal
    commission_ratio: Decimal
    bsiv_ratio: Decimal
    total_expense_ratio: Decimal
    net_ratio: Decimal


@dataclass(frozen=True)
class FinancingCostReportSummary:
    total_batch_count: int
    total_check_count: int
    average_days_to_due: Decimal

    total_gross_amount_by_currency: dict[str, Decimal]
    total_interest_expense_by_currency: dict[str, Decimal]
    total_commission_by_currency: dict[str, Decimal]
    total_bsiv_by_currency: dict[str, Decimal]
    total_discount_expense_by_currency: dict[str, Decimal]
    net_bank_amount_by_currency: dict[str, Decimal]

    total_expense_ratio_by_currency: dict[str, Decimal]
    net_ratio_by_currency: dict[str, Decimal]

    bank_summaries: list[FinancingCostBankSummary]


@dataclass(frozen=True)
class FinancingCostReportData:
    filters: FinancingCostReportFilter
    report_period_text: str
    rows: list[FinancingCostReportRow]
    check_rows: list[FinancingCostReportCheckRow]
    summary: FinancingCostReportSummary


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


def _normalize_filter_value(value: Any, default_value: str = "ALL") -> str:
    normalized_value = str(value or default_value).strip().upper()

    if not normalized_value:
        return default_value

    return normalized_value


def _format_date_tr(value: date) -> str:
    return value.strftime("%d.%m.%Y")


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


def _ratio(
    *,
    numerator: Decimal,
    denominator: Decimal,
) -> Decimal:
    numerator_value = _decimal_or_zero(numerator)
    denominator_value = _decimal_or_zero(denominator)

    if denominator_value <= Decimal("0.00"):
        return Decimal("0.00")

    return ((numerator_value / denominator_value) * Decimal("100")).quantize(Decimal("0.01"))


def _average_decimal(
    *,
    total_value: Decimal,
    count: int,
) -> Decimal:
    if count <= 0:
        return Decimal("0.00")

    return (_decimal_or_zero(total_value) / Decimal(count)).quantize(Decimal("0.01"))


def _row_style_for_total_expense_ratio(total_expense_ratio: Decimal) -> str:
    if total_expense_ratio >= Decimal("10.00"):
        return "RISK"

    if total_expense_ratio >= Decimal("5.00"):
        return "WARNING"

    return "NORMAL"


def _build_financing_cost_row(
    batch_row: DiscountBatchReportBatchRow,
) -> FinancingCostReportRow:
    total_gross_amount = _decimal_or_zero(batch_row.total_gross_amount)
    total_interest_expense_amount = _decimal_or_zero(batch_row.total_interest_expense_amount)
    total_commission_amount = _decimal_or_zero(batch_row.total_commission_amount)
    total_bsiv_amount = _decimal_or_zero(batch_row.total_bsiv_amount)
    total_discount_expense_amount = _decimal_or_zero(batch_row.total_discount_expense_amount)
    net_bank_amount = _decimal_or_zero(batch_row.net_bank_amount)

    interest_ratio = _ratio(
        numerator=total_interest_expense_amount,
        denominator=total_gross_amount,
    )
    commission_ratio = _ratio(
        numerator=total_commission_amount,
        denominator=total_gross_amount,
    )
    bsiv_ratio = _ratio(
        numerator=total_bsiv_amount,
        denominator=total_gross_amount,
    )
    total_expense_ratio = _ratio(
        numerator=total_discount_expense_amount,
        denominator=total_gross_amount,
    )
    net_ratio = _ratio(
        numerator=net_bank_amount,
        denominator=total_gross_amount,
    )

    return FinancingCostReportRow(
        batch_id=batch_row.batch_id,
        bank_id=batch_row.bank_id,
        bank_name=batch_row.bank_name,
        bank_account_id=batch_row.bank_account_id,
        account_name=batch_row.account_name,
        discount_date=batch_row.discount_date,
        currency_code=batch_row.currency_code,
        check_count=batch_row.check_count,
        average_days_to_due=batch_row.average_days_to_due,
        day_basis=batch_row.day_basis,
        annual_interest_rate=_rate_or_zero(batch_row.annual_interest_rate),
        commission_rate=_rate_or_zero(batch_row.commission_rate),
        bsiv_rate=_rate_or_zero(batch_row.bsiv_rate),
        total_gross_amount=total_gross_amount,
        total_interest_expense_amount=total_interest_expense_amount,
        total_commission_amount=total_commission_amount,
        total_bsiv_amount=total_bsiv_amount,
        total_discount_expense_amount=total_discount_expense_amount,
        net_bank_amount=net_bank_amount,
        interest_ratio=interest_ratio,
        commission_ratio=commission_ratio,
        bsiv_ratio=bsiv_ratio,
        total_expense_ratio=total_expense_ratio,
        net_ratio=net_ratio,
        reference_no=batch_row.reference_no,
        description=batch_row.description,
        row_style=_row_style_for_total_expense_ratio(total_expense_ratio),
    )


def _build_financing_cost_check_row(
    item_row: DiscountBatchReportItemRow,
) -> FinancingCostReportCheckRow:
    gross_amount = _decimal_or_zero(item_row.gross_amount)
    total_expense_amount = _decimal_or_zero(item_row.total_expense_amount)

    expense_ratio = _ratio(
        numerator=total_expense_amount,
        denominator=gross_amount,
    )

    return FinancingCostReportCheckRow(
        item_id=item_row.item_id,
        batch_id=item_row.batch_id,
        received_check_id=item_row.received_check_id,
        check_number=item_row.check_number,
        customer_name=item_row.customer_name,
        drawer_bank_name=item_row.drawer_bank_name,
        due_date=item_row.due_date,
        days_to_due=item_row.days_to_due,
        gross_amount=gross_amount,
        interest_expense_amount=_decimal_or_zero(item_row.interest_expense_amount),
        commission_amount=_decimal_or_zero(item_row.commission_amount),
        bsiv_amount=_decimal_or_zero(item_row.bsiv_amount),
        total_expense_amount=total_expense_amount,
        net_amount=_decimal_or_zero(item_row.net_amount),
        currency_code=item_row.currency_code,
        expense_ratio=expense_ratio,
        row_style=_row_style_for_total_expense_ratio(expense_ratio),
    )


def _build_financing_cost_check_rows(
    item_rows: list[DiscountBatchReportItemRow],
) -> list[FinancingCostReportCheckRow]:
    check_rows = [
        _build_financing_cost_check_row(item_row)
        for item_row in item_rows
    ]

    check_rows.sort(
        key=lambda item: (
            item.batch_id,
            item.due_date,
            item.check_number,
            item.item_id,
        )
    )

    return check_rows


def _build_bank_summaries(
    rows: list[FinancingCostReportRow],
) -> list[FinancingCostBankSummary]:
    grouped: dict[tuple[int, int, str], dict[str, Any]] = {}

    for row in rows:
        key = (
            row.bank_id,
            row.bank_account_id,
            row.currency_code,
        )

        if key not in grouped:
            grouped[key] = {
                "bank_id": row.bank_id,
                "bank_name": row.bank_name,
                "bank_account_id": row.bank_account_id,
                "account_name": row.account_name,
                "currency_code": row.currency_code,
                "batch_count": 0,
                "check_count": 0,
                "days_total": Decimal("0.00"),
                "total_gross_amount": Decimal("0.00"),
                "total_interest_expense_amount": Decimal("0.00"),
                "total_commission_amount": Decimal("0.00"),
                "total_bsiv_amount": Decimal("0.00"),
                "total_discount_expense_amount": Decimal("0.00"),
                "net_bank_amount": Decimal("0.00"),
            }

        values = grouped[key]
        values["batch_count"] += 1
        values["check_count"] += row.check_count
        values["days_total"] += row.average_days_to_due
        values["total_gross_amount"] += row.total_gross_amount
        values["total_interest_expense_amount"] += row.total_interest_expense_amount
        values["total_commission_amount"] += row.total_commission_amount
        values["total_bsiv_amount"] += row.total_bsiv_amount
        values["total_discount_expense_amount"] += row.total_discount_expense_amount
        values["net_bank_amount"] += row.net_bank_amount

    bank_summaries: list[FinancingCostBankSummary] = []

    for values in grouped.values():
        total_gross_amount = _decimal_or_zero(values["total_gross_amount"])
        total_interest_expense_amount = _decimal_or_zero(values["total_interest_expense_amount"])
        total_commission_amount = _decimal_or_zero(values["total_commission_amount"])
        total_bsiv_amount = _decimal_or_zero(values["total_bsiv_amount"])
        total_discount_expense_amount = _decimal_or_zero(values["total_discount_expense_amount"])
        net_bank_amount = _decimal_or_zero(values["net_bank_amount"])
        batch_count = int(values["batch_count"])

        bank_summaries.append(
            FinancingCostBankSummary(
                bank_id=int(values["bank_id"]),
                bank_name=str(values["bank_name"]),
                bank_account_id=int(values["bank_account_id"]),
                account_name=str(values["account_name"]),
                currency_code=str(values["currency_code"]),
                batch_count=batch_count,
                check_count=int(values["check_count"]),
                average_days_to_due=_average_decimal(
                    total_value=_decimal_or_zero(values["days_total"]),
                    count=batch_count,
                ),
                total_gross_amount=total_gross_amount,
                total_interest_expense_amount=total_interest_expense_amount,
                total_commission_amount=total_commission_amount,
                total_bsiv_amount=total_bsiv_amount,
                total_discount_expense_amount=total_discount_expense_amount,
                net_bank_amount=net_bank_amount,
                interest_ratio=_ratio(
                    numerator=total_interest_expense_amount,
                    denominator=total_gross_amount,
                ),
                commission_ratio=_ratio(
                    numerator=total_commission_amount,
                    denominator=total_gross_amount,
                ),
                bsiv_ratio=_ratio(
                    numerator=total_bsiv_amount,
                    denominator=total_gross_amount,
                ),
                total_expense_ratio=_ratio(
                    numerator=total_discount_expense_amount,
                    denominator=total_gross_amount,
                ),
                net_ratio=_ratio(
                    numerator=net_bank_amount,
                    denominator=total_gross_amount,
                ),
            )
        )

    bank_summaries.sort(
        key=lambda item: (
            item.bank_name.lower(),
            item.account_name.lower(),
            item.currency_code,
        )
    )

    return bank_summaries


def _build_ratio_totals(
    *,
    numerator_totals: dict[str, Decimal],
    denominator_totals: dict[str, Decimal],
) -> dict[str, Decimal]:
    ratios: dict[str, Decimal] = {}

    for currency_code, numerator in numerator_totals.items():
        ratios[currency_code] = _ratio(
            numerator=numerator,
            denominator=denominator_totals.get(currency_code, Decimal("0.00")),
        )

    return ratios


def _build_summary(
    rows: list[FinancingCostReportRow],
) -> FinancingCostReportSummary:
    total_gross_amount_by_currency: dict[str, Decimal] = {}
    total_interest_expense_by_currency: dict[str, Decimal] = {}
    total_commission_by_currency: dict[str, Decimal] = {}
    total_bsiv_by_currency: dict[str, Decimal] = {}
    total_discount_expense_by_currency: dict[str, Decimal] = {}
    net_bank_amount_by_currency: dict[str, Decimal] = {}

    total_check_count = 0
    total_days = Decimal("0.00")

    for row in rows:
        total_check_count += row.check_count
        total_days += row.average_days_to_due

        _add_to_totals(
            total_gross_amount_by_currency,
            row.currency_code,
            row.total_gross_amount,
        )
        _add_to_totals(
            total_interest_expense_by_currency,
            row.currency_code,
            row.total_interest_expense_amount,
        )
        _add_to_totals(
            total_commission_by_currency,
            row.currency_code,
            row.total_commission_amount,
        )
        _add_to_totals(
            total_bsiv_by_currency,
            row.currency_code,
            row.total_bsiv_amount,
        )
        _add_to_totals(
            total_discount_expense_by_currency,
            row.currency_code,
            row.total_discount_expense_amount,
        )
        _add_to_totals(
            net_bank_amount_by_currency,
            row.currency_code,
            row.net_bank_amount,
        )

    average_days_to_due = _average_decimal(
        total_value=total_days,
        count=len(rows),
    )

    total_expense_ratio_by_currency = _build_ratio_totals(
        numerator_totals=total_discount_expense_by_currency,
        denominator_totals=total_gross_amount_by_currency,
    )

    net_ratio_by_currency = _build_ratio_totals(
        numerator_totals=net_bank_amount_by_currency,
        denominator_totals=total_gross_amount_by_currency,
    )

    return FinancingCostReportSummary(
        total_batch_count=len(rows),
        total_check_count=total_check_count,
        average_days_to_due=average_days_to_due,
        total_gross_amount_by_currency=total_gross_amount_by_currency,
        total_interest_expense_by_currency=total_interest_expense_by_currency,
        total_commission_by_currency=total_commission_by_currency,
        total_bsiv_by_currency=total_bsiv_by_currency,
        total_discount_expense_by_currency=total_discount_expense_by_currency,
        net_bank_amount_by_currency=net_bank_amount_by_currency,
        total_expense_ratio_by_currency=total_expense_ratio_by_currency,
        net_ratio_by_currency=net_ratio_by_currency,
        bank_summaries=_build_bank_summaries(rows),
    )


def _to_discount_batch_filter(
    report_filter: FinancingCostReportFilter,
) -> DiscountBatchReportFilter:
    return DiscountBatchReportFilter(
        start_date=report_filter.start_date,
        end_date=report_filter.end_date,
        bank_id=report_filter.bank_id,
        bank_account_id=report_filter.bank_account_id,
        discount_batch_id=report_filter.discount_batch_id,
        currency_code=_normalize_filter_value(report_filter.currency_code),
    )


def load_financing_cost_report_data(
    report_filter: FinancingCostReportFilter,
) -> FinancingCostReportData:
    start_date = report_filter.start_date
    end_date = report_filter.end_date

    if end_date < start_date:
        raise ValueError("Bitiş tarihi başlangıç tarihinden küçük olamaz.")

    discount_batch_data: DiscountBatchReportData = load_discount_batch_report_data(
        _to_discount_batch_filter(report_filter)
    )

    rows = [
        _build_financing_cost_row(batch_row)
        for batch_row in discount_batch_data.batch_rows
    ]

    check_rows = _build_financing_cost_check_rows(discount_batch_data.item_rows)

    summary = _build_summary(rows)

    return FinancingCostReportData(
        filters=FinancingCostReportFilter(
            start_date=start_date,
            end_date=end_date,
            bank_id=report_filter.bank_id,
            bank_account_id=report_filter.bank_account_id,
            discount_batch_id=report_filter.discount_batch_id,
            currency_code=_normalize_filter_value(report_filter.currency_code),
        ),
        report_period_text=f"{_format_date_tr(start_date)} - {_format_date_tr(end_date)}",
        rows=rows,
        check_rows=check_rows,
        summary=summary,
    )


def load_default_current_month_financing_cost_report_data() -> FinancingCostReportData:
    today = date.today()
    start_date = date(today.year, today.month, 1)

    if today.month == 12:
        end_date = date(today.year, 12, 31)
    else:
        end_date = date(today.year, today.month + 1, 1) - timedelta(days=1)

    return load_financing_cost_report_data(
        FinancingCostReportFilter(
            start_date=start_date,
            end_date=end_date,
            bank_id=None,
            bank_account_id=None,
            discount_batch_id=None,
            currency_code="ALL",
        )
    )


__all__ = [
    "FinancingCostReportFilter",
    "FinancingCostReportRow",
    "FinancingCostReportCheckRow",
    "FinancingCostBankSummary",
    "FinancingCostReportSummary",
    "FinancingCostReportData",
    "load_financing_cost_report_data",
    "load_default_current_month_financing_cost_report_data",
]