from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select

from app.db.session import session_scope
from app.models.bank import Bank, BankAccount
from app.models.business_partner import BusinessPartner
from app.models.check import (
    ReceivedCheck,
    ReceivedCheckDiscountBatch,
    ReceivedCheckDiscountBatchItem,
)


@dataclass(frozen=True)
class DiscountBatchReportFilter:
    start_date: date
    end_date: date
    bank_id: int | None = None
    bank_account_id: int | None = None
    discount_batch_id: int | None = None
    currency_code: str = "ALL"


@dataclass(frozen=True)
class DiscountBatchOption:
    batch_id: int
    discount_date: date
    bank_id: int
    bank_name: str
    bank_account_id: int
    account_name: str
    total_gross_amount: Decimal
    total_discount_expense_amount: Decimal
    net_bank_amount: Decimal
    currency_code: str
    reference_no: str | None
    display_text: str


@dataclass(frozen=True)
class DiscountBatchReportBatchRow:
    batch_id: int
    bank_id: int
    bank_name: str
    bank_account_id: int
    account_name: str
    discount_date: date
    annual_interest_rate: Decimal
    commission_rate: Decimal
    bsiv_rate: Decimal
    day_basis: int
    total_gross_amount: Decimal
    total_interest_expense_amount: Decimal
    total_commission_amount: Decimal
    total_bsiv_amount: Decimal
    total_discount_expense_amount: Decimal
    net_bank_amount: Decimal
    currency_code: str
    reference_no: str | None
    description: str | None
    check_count: int
    average_days_to_due: Decimal
    expense_ratio: Decimal
    row_style: str


@dataclass(frozen=True)
class DiscountBatchReportItemRow:
    item_id: int
    batch_id: int
    received_check_id: int
    check_number: str
    customer_name: str
    drawer_bank_name: str
    due_date: date
    gross_amount: Decimal
    days_to_due: int
    annual_interest_rate: Decimal
    interest_expense_amount: Decimal
    commission_rate: Decimal
    commission_amount: Decimal
    bsiv_rate: Decimal
    bsiv_amount: Decimal
    total_expense_amount: Decimal
    net_amount: Decimal
    currency_code: str
    row_style: str


@dataclass(frozen=True)
class DiscountBatchBankSummary:
    bank_id: int
    bank_name: str
    bank_account_id: int
    account_name: str
    currency_code: str
    batch_count: int
    check_count: int
    total_gross_amount: Decimal
    total_interest_expense_amount: Decimal
    total_commission_amount: Decimal
    total_bsiv_amount: Decimal
    total_discount_expense_amount: Decimal
    net_bank_amount: Decimal


@dataclass(frozen=True)
class DiscountBatchReportSummary:
    total_batch_count: int
    total_check_count: int
    average_days_to_due: Decimal
    total_gross_amount_by_currency: dict[str, Decimal]
    total_interest_expense_by_currency: dict[str, Decimal]
    total_commission_by_currency: dict[str, Decimal]
    total_bsiv_by_currency: dict[str, Decimal]
    total_discount_expense_by_currency: dict[str, Decimal]
    net_bank_amount_by_currency: dict[str, Decimal]
    bank_summaries: list[DiscountBatchBankSummary]


@dataclass(frozen=True)
class DiscountBatchReportData:
    filters: DiscountBatchReportFilter
    report_period_text: str
    batch_rows: list[DiscountBatchReportBatchRow]
    item_rows: list[DiscountBatchReportItemRow]
    summary: DiscountBatchReportSummary


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


def _format_date_tr(value: date) -> str:
    return value.strftime("%d.%m.%Y")


def _format_decimal_tr(value: Any) -> str:
    amount = _decimal_or_zero(value)

    formatted = f"{amount:,.2f}"
    formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")

    return formatted


def _format_currency_amount(value: Any, currency_code: str) -> str:
    normalized_currency_code = str(currency_code or "TRY").strip().upper() or "TRY"

    if normalized_currency_code == "TRY":
        return f"{_format_decimal_tr(value)} TL"

    return f"{_format_decimal_tr(value)} {normalized_currency_code}"


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


def _expense_ratio(
    *,
    total_gross_amount: Decimal,
    total_discount_expense_amount: Decimal,
) -> Decimal:
    gross_amount = _decimal_or_zero(total_gross_amount)
    expense_amount = _decimal_or_zero(total_discount_expense_amount)

    if gross_amount <= Decimal("0.00"):
        return Decimal("0.00")

    return ((expense_amount / gross_amount) * Decimal("100")).quantize(Decimal("0.01"))


def _row_style_for_batch(expense_ratio: Decimal) -> str:
    if expense_ratio >= Decimal("10.00"):
        return "RISK"

    if expense_ratio >= Decimal("5.00"):
        return "WARNING"

    return "NORMAL"


def _row_style_for_item(days_to_due: int, total_expense_amount: Decimal, gross_amount: Decimal) -> str:
    item_expense_ratio = _expense_ratio(
        total_gross_amount=gross_amount,
        total_discount_expense_amount=total_expense_amount,
    )

    if item_expense_ratio >= Decimal("10.00"):
        return "RISK"

    if item_expense_ratio >= Decimal("5.00") or days_to_due >= 90:
        return "WARNING"

    return "NORMAL"


def _build_discount_batch_option(
    *,
    batch: ReceivedCheckDiscountBatch,
    bank_account: BankAccount,
    bank: Bank,
) -> DiscountBatchOption:
    currency_code = _enum_value(batch.currency_code) or "TRY"
    total_gross_amount = _decimal_or_zero(batch.total_gross_amount)
    total_discount_expense_amount = _decimal_or_zero(batch.total_discount_expense_amount)
    net_bank_amount = _decimal_or_zero(batch.net_bank_amount)

    display_text = (
        f"#{batch.id} | "
        f"{_format_date_tr(batch.discount_date)} | "
        f"{bank.name} / {bank_account.account_name} | "
        f"Brüt: {_format_currency_amount(total_gross_amount, currency_code)} | "
        f"Masraf: {_format_currency_amount(total_discount_expense_amount, currency_code)} | "
        f"Net: {_format_currency_amount(net_bank_amount, currency_code)}"
    )

    if batch.reference_no:
        display_text = f"{display_text} | Ref: {batch.reference_no}"

    return DiscountBatchOption(
        batch_id=int(batch.id),
        discount_date=batch.discount_date,
        bank_id=int(bank.id),
        bank_name=str(bank.name),
        bank_account_id=int(bank_account.id),
        account_name=str(bank_account.account_name),
        total_gross_amount=total_gross_amount,
        total_discount_expense_amount=total_discount_expense_amount,
        net_bank_amount=net_bank_amount,
        currency_code=currency_code,
        reference_no=batch.reference_no,
        display_text=display_text,
    )


def _build_batch_row(
    *,
    batch: ReceivedCheckDiscountBatch,
    bank_account: BankAccount,
    bank: Bank,
    item_count_map: dict[int, int],
    average_days_map: dict[int, Decimal],
) -> DiscountBatchReportBatchRow:
    currency_code = _enum_value(batch.currency_code) or "TRY"

    expense_ratio = _expense_ratio(
        total_gross_amount=_decimal_or_zero(batch.total_gross_amount),
        total_discount_expense_amount=_decimal_or_zero(batch.total_discount_expense_amount),
    )

    return DiscountBatchReportBatchRow(
        batch_id=int(batch.id),
        bank_id=int(bank.id),
        bank_name=str(bank.name),
        bank_account_id=int(bank_account.id),
        account_name=str(bank_account.account_name),
        discount_date=batch.discount_date,
        annual_interest_rate=_rate_or_zero(batch.annual_interest_rate),
        commission_rate=_rate_or_zero(batch.commission_rate),
        bsiv_rate=_rate_or_zero(batch.bsiv_rate),
        day_basis=int(batch.day_basis or 365),
        total_gross_amount=_decimal_or_zero(batch.total_gross_amount),
        total_interest_expense_amount=_decimal_or_zero(batch.total_interest_expense_amount),
        total_commission_amount=_decimal_or_zero(batch.total_commission_amount),
        total_bsiv_amount=_decimal_or_zero(batch.total_bsiv_amount),
        total_discount_expense_amount=_decimal_or_zero(batch.total_discount_expense_amount),
        net_bank_amount=_decimal_or_zero(batch.net_bank_amount),
        currency_code=currency_code,
        reference_no=batch.reference_no,
        description=batch.description,
        check_count=int(item_count_map.get(int(batch.id), 0)),
        average_days_to_due=average_days_map.get(int(batch.id), Decimal("0.00")),
        expense_ratio=expense_ratio,
        row_style=_row_style_for_batch(expense_ratio),
    )


def _build_item_row(
    *,
    item: ReceivedCheckDiscountBatchItem,
    received_check: ReceivedCheck,
    customer: BusinessPartner,
) -> DiscountBatchReportItemRow:
    gross_amount = _decimal_or_zero(item.gross_amount)
    total_expense_amount = _decimal_or_zero(item.total_expense_amount)
    days_to_due = int(item.days_to_due or 0)

    return DiscountBatchReportItemRow(
        item_id=int(item.id),
        batch_id=int(item.batch_id),
        received_check_id=int(item.received_check_id),
        check_number=str(received_check.check_number or ""),
        customer_name=str(customer.name or ""),
        drawer_bank_name=str(received_check.drawer_bank_name or ""),
        due_date=item.due_date,
        gross_amount=gross_amount,
        days_to_due=days_to_due,
        annual_interest_rate=_rate_or_zero(item.annual_interest_rate),
        interest_expense_amount=_decimal_or_zero(item.interest_expense_amount),
        commission_rate=_rate_or_zero(item.commission_rate),
        commission_amount=_decimal_or_zero(item.commission_amount),
        bsiv_rate=_rate_or_zero(item.bsiv_rate),
        bsiv_amount=_decimal_or_zero(item.bsiv_amount),
        total_expense_amount=total_expense_amount,
        net_amount=_decimal_or_zero(item.net_amount),
        currency_code=_enum_value(item.currency_code) or "TRY",
        row_style=_row_style_for_item(
            days_to_due=days_to_due,
            total_expense_amount=total_expense_amount,
            gross_amount=gross_amount,
        ),
    )


def _build_item_maps(
    item_rows: list[DiscountBatchReportItemRow],
) -> tuple[dict[int, int], dict[int, Decimal]]:
    item_count_map: dict[int, int] = {}
    days_sum_map: dict[int, int] = {}

    for item_row in item_rows:
        item_count_map[item_row.batch_id] = item_count_map.get(item_row.batch_id, 0) + 1
        days_sum_map[item_row.batch_id] = days_sum_map.get(item_row.batch_id, 0) + item_row.days_to_due

    average_days_map: dict[int, Decimal] = {}

    for batch_id, item_count in item_count_map.items():
        if item_count <= 0:
            average_days_map[batch_id] = Decimal("0.00")
            continue

        average_days_map[batch_id] = (
            Decimal(days_sum_map.get(batch_id, 0)) / Decimal(item_count)
        ).quantize(Decimal("0.01"))

    return item_count_map, average_days_map


def _build_bank_summaries(
    batch_rows: list[DiscountBatchReportBatchRow],
) -> list[DiscountBatchBankSummary]:
    grouped: dict[tuple[int, int, str], dict[str, Any]] = {}

    for batch_row in batch_rows:
        key = (
            batch_row.bank_id,
            batch_row.bank_account_id,
            batch_row.currency_code,
        )

        if key not in grouped:
            grouped[key] = {
                "bank_id": batch_row.bank_id,
                "bank_name": batch_row.bank_name,
                "bank_account_id": batch_row.bank_account_id,
                "account_name": batch_row.account_name,
                "currency_code": batch_row.currency_code,
                "batch_count": 0,
                "check_count": 0,
                "total_gross_amount": Decimal("0.00"),
                "total_interest_expense_amount": Decimal("0.00"),
                "total_commission_amount": Decimal("0.00"),
                "total_bsiv_amount": Decimal("0.00"),
                "total_discount_expense_amount": Decimal("0.00"),
                "net_bank_amount": Decimal("0.00"),
            }

        values = grouped[key]
        values["batch_count"] += 1
        values["check_count"] += batch_row.check_count
        values["total_gross_amount"] += batch_row.total_gross_amount
        values["total_interest_expense_amount"] += batch_row.total_interest_expense_amount
        values["total_commission_amount"] += batch_row.total_commission_amount
        values["total_bsiv_amount"] += batch_row.total_bsiv_amount
        values["total_discount_expense_amount"] += batch_row.total_discount_expense_amount
        values["net_bank_amount"] += batch_row.net_bank_amount

    bank_summaries: list[DiscountBatchBankSummary] = []

    for values in grouped.values():
        bank_summaries.append(
            DiscountBatchBankSummary(
                bank_id=int(values["bank_id"]),
                bank_name=str(values["bank_name"]),
                bank_account_id=int(values["bank_account_id"]),
                account_name=str(values["account_name"]),
                currency_code=str(values["currency_code"]),
                batch_count=int(values["batch_count"]),
                check_count=int(values["check_count"]),
                total_gross_amount=_decimal_or_zero(values["total_gross_amount"]),
                total_interest_expense_amount=_decimal_or_zero(values["total_interest_expense_amount"]),
                total_commission_amount=_decimal_or_zero(values["total_commission_amount"]),
                total_bsiv_amount=_decimal_or_zero(values["total_bsiv_amount"]),
                total_discount_expense_amount=_decimal_or_zero(values["total_discount_expense_amount"]),
                net_bank_amount=_decimal_or_zero(values["net_bank_amount"]),
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


def _build_summary(
    batch_rows: list[DiscountBatchReportBatchRow],
    item_rows: list[DiscountBatchReportItemRow],
) -> DiscountBatchReportSummary:
    total_gross_amount_by_currency: dict[str, Decimal] = {}
    total_interest_expense_by_currency: dict[str, Decimal] = {}
    total_commission_by_currency: dict[str, Decimal] = {}
    total_bsiv_by_currency: dict[str, Decimal] = {}
    total_discount_expense_by_currency: dict[str, Decimal] = {}
    net_bank_amount_by_currency: dict[str, Decimal] = {}

    total_days = 0

    for item_row in item_rows:
        total_days += item_row.days_to_due

    average_days_to_due = Decimal("0.00")

    if item_rows:
        average_days_to_due = (Decimal(total_days) / Decimal(len(item_rows))).quantize(Decimal("0.01"))

    for batch_row in batch_rows:
        _add_to_totals(
            total_gross_amount_by_currency,
            batch_row.currency_code,
            batch_row.total_gross_amount,
        )
        _add_to_totals(
            total_interest_expense_by_currency,
            batch_row.currency_code,
            batch_row.total_interest_expense_amount,
        )
        _add_to_totals(
            total_commission_by_currency,
            batch_row.currency_code,
            batch_row.total_commission_amount,
        )
        _add_to_totals(
            total_bsiv_by_currency,
            batch_row.currency_code,
            batch_row.total_bsiv_amount,
        )
        _add_to_totals(
            total_discount_expense_by_currency,
            batch_row.currency_code,
            batch_row.total_discount_expense_amount,
        )
        _add_to_totals(
            net_bank_amount_by_currency,
            batch_row.currency_code,
            batch_row.net_bank_amount,
        )

    return DiscountBatchReportSummary(
        total_batch_count=len(batch_rows),
        total_check_count=len(item_rows),
        average_days_to_due=average_days_to_due,
        total_gross_amount_by_currency=total_gross_amount_by_currency,
        total_interest_expense_by_currency=total_interest_expense_by_currency,
        total_commission_by_currency=total_commission_by_currency,
        total_bsiv_by_currency=total_bsiv_by_currency,
        total_discount_expense_by_currency=total_discount_expense_by_currency,
        net_bank_amount_by_currency=net_bank_amount_by_currency,
        bank_summaries=_build_bank_summaries(batch_rows),
    )


def _load_item_rows_for_batches(
    batch_ids: list[int],
) -> list[DiscountBatchReportItemRow]:
    if not batch_ids:
        return []

    item_rows: list[DiscountBatchReportItemRow] = []

    with session_scope() as session:
        statement = (
            select(
                ReceivedCheckDiscountBatchItem,
                ReceivedCheck,
                BusinessPartner,
            )
            .join(
                ReceivedCheck,
                ReceivedCheckDiscountBatchItem.received_check_id == ReceivedCheck.id,
            )
            .join(
                BusinessPartner,
                ReceivedCheck.customer_id == BusinessPartner.id,
            )
            .where(ReceivedCheckDiscountBatchItem.batch_id.in_(batch_ids))
            .order_by(
                ReceivedCheckDiscountBatchItem.batch_id.asc(),
                ReceivedCheckDiscountBatchItem.due_date.asc(),
                ReceivedCheck.check_number.asc(),
                ReceivedCheckDiscountBatchItem.id.asc(),
            )
        )

        result_rows = session.execute(statement).all()

        for item, received_check, customer in result_rows:
            item_rows.append(
                _build_item_row(
                    item=item,
                    received_check=received_check,
                    customer=customer,
                )
            )

    return item_rows


def list_discount_batch_options(
    *,
    start_date: date,
    end_date: date,
    bank_id: int | None = None,
    bank_account_id: int | None = None,
    currency_code: str = "ALL",
) -> list[DiscountBatchOption]:
    if end_date < start_date:
        raise ValueError("Bitiş tarihi başlangıç tarihinden küçük olamaz.")

    currency_code_filter = _normalize_filter_value(currency_code)

    options: list[DiscountBatchOption] = []

    with session_scope() as session:
        statement = (
            select(
                ReceivedCheckDiscountBatch,
                BankAccount,
                Bank,
            )
            .join(
                BankAccount,
                ReceivedCheckDiscountBatch.bank_account_id == BankAccount.id,
            )
            .join(
                Bank,
                BankAccount.bank_id == Bank.id,
            )
            .where(
                ReceivedCheckDiscountBatch.discount_date >= start_date,
                ReceivedCheckDiscountBatch.discount_date <= end_date,
            )
            .order_by(
                ReceivedCheckDiscountBatch.discount_date.desc(),
                Bank.name.asc(),
                BankAccount.account_name.asc(),
                ReceivedCheckDiscountBatch.id.desc(),
            )
        )

        if bank_id is not None:
            statement = statement.where(Bank.id == bank_id)

        if bank_account_id is not None:
            statement = statement.where(BankAccount.id == bank_account_id)

        result_rows = session.execute(statement).all()

        for batch, bank_account, bank in result_rows:
            batch_currency_code = _enum_value(batch.currency_code) or "TRY"

            if currency_code_filter != "ALL" and batch_currency_code != currency_code_filter:
                continue

            options.append(
                _build_discount_batch_option(
                    batch=batch,
                    bank_account=bank_account,
                    bank=bank,
                )
            )

    return options


def load_discount_batch_report_data(
    report_filter: DiscountBatchReportFilter,
) -> DiscountBatchReportData:
    start_date = report_filter.start_date
    end_date = report_filter.end_date

    if end_date < start_date:
        raise ValueError("Bitiş tarihi başlangıç tarihinden küçük olamaz.")

    currency_code_filter = _normalize_filter_value(report_filter.currency_code)

    batch_records: list[tuple[ReceivedCheckDiscountBatch, BankAccount, Bank]] = []

    with session_scope() as session:
        statement = (
            select(
                ReceivedCheckDiscountBatch,
                BankAccount,
                Bank,
            )
            .join(
                BankAccount,
                ReceivedCheckDiscountBatch.bank_account_id == BankAccount.id,
            )
            .join(
                Bank,
                BankAccount.bank_id == Bank.id,
            )
            .where(
                ReceivedCheckDiscountBatch.discount_date >= start_date,
                ReceivedCheckDiscountBatch.discount_date <= end_date,
            )
            .order_by(
                ReceivedCheckDiscountBatch.discount_date.asc(),
                Bank.name.asc(),
                BankAccount.account_name.asc(),
                ReceivedCheckDiscountBatch.id.asc(),
            )
        )

        if report_filter.bank_id is not None:
            statement = statement.where(Bank.id == report_filter.bank_id)

        if report_filter.bank_account_id is not None:
            statement = statement.where(BankAccount.id == report_filter.bank_account_id)

        if report_filter.discount_batch_id is not None:
            statement = statement.where(ReceivedCheckDiscountBatch.id == report_filter.discount_batch_id)

        result_rows = session.execute(statement).all()

        for batch, bank_account, bank in result_rows:
            batch_currency_code = _enum_value(batch.currency_code) or "TRY"

            if currency_code_filter != "ALL" and batch_currency_code != currency_code_filter:
                continue

            batch_records.append((batch, bank_account, bank))

    batch_ids = [int(batch.id) for batch, _, _ in batch_records]
    item_rows = _load_item_rows_for_batches(batch_ids)

    item_count_map, average_days_map = _build_item_maps(item_rows)

    batch_rows = [
        _build_batch_row(
            batch=batch,
            bank_account=bank_account,
            bank=bank,
            item_count_map=item_count_map,
            average_days_map=average_days_map,
        )
        for batch, bank_account, bank in batch_records
    ]

    summary = _build_summary(
        batch_rows=batch_rows,
        item_rows=item_rows,
    )

    return DiscountBatchReportData(
        filters=DiscountBatchReportFilter(
            start_date=start_date,
            end_date=end_date,
            bank_id=report_filter.bank_id,
            bank_account_id=report_filter.bank_account_id,
            discount_batch_id=report_filter.discount_batch_id,
            currency_code=currency_code_filter,
        ),
        report_period_text=f"{_format_date_tr(start_date)} - {_format_date_tr(end_date)}",
        batch_rows=batch_rows,
        item_rows=item_rows,
        summary=summary,
    )


def load_default_current_month_discount_batch_report_data() -> DiscountBatchReportData:
    today = date.today()
    start_date = date(today.year, today.month, 1)

    if today.month == 12:
        end_date = date(today.year, 12, 31)
    else:
        end_date = date(today.year, today.month + 1, 1) - timedelta(days=1)

    return load_discount_batch_report_data(
        DiscountBatchReportFilter(
            start_date=start_date,
            end_date=end_date,
            bank_id=None,
            bank_account_id=None,
            discount_batch_id=None,
            currency_code="ALL",
        )
    )


__all__ = [
    "DiscountBatchReportFilter",
    "DiscountBatchOption",
    "DiscountBatchReportBatchRow",
    "DiscountBatchReportItemRow",
    "DiscountBatchBankSummary",
    "DiscountBatchReportSummary",
    "DiscountBatchReportData",
    "list_discount_batch_options",
    "load_discount_batch_report_data",
    "load_default_current_month_discount_batch_report_data",
]