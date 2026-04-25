from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select

from app.db.session import session_scope
from app.models.bank import Bank, BankAccount
from app.models.bank_transaction import BankTransaction


DIRECTION_TEXTS = {
    "IN": "Giriş",
    "OUT": "Çıkış",
}

STATUS_TEXTS = {
    "PLANNED": "Planlandı",
    "REALIZED": "Gerçekleşti",
    "CANCELLED": "İptal Edildi",
}

SOURCE_TYPE_TEXTS = {
    "OPENING_BALANCE": "Açılış Bakiyesi",
    "CASH_DEPOSIT": "Nakit Yatırma",
    "BANK_TRANSFER": "Banka Transferi",
    "ISSUED_CHECK": "Yazılan Çek",
    "RECEIVED_CHECK": "Alınan Çek",
    "POS_SETTLEMENT": "POS Yatışı",
    "MANUAL_ADJUSTMENT": "Manuel Düzeltme",
    "OTHER": "Diğer",
}


@dataclass(frozen=True)
class BankMovementReportFilter:
    start_date: date
    end_date: date
    bank_id: int | None = None
    bank_account_id: int | None = None
    direction: str = "ALL"
    status: str = "ALL"
    currency_code: str = "ALL"
    source_type: str = "ALL"


@dataclass(frozen=True)
class BankMovementReportRow:
    transaction_id: int
    bank_id: int
    bank_name: str
    bank_account_id: int
    account_name: str
    transaction_date: date
    value_date: date | None
    direction: str
    direction_text: str
    status: str
    status_text: str
    amount: Decimal
    currency_code: str
    source_type: str
    source_type_text: str
    reference_no: str | None
    description: str | None
    row_style: str


@dataclass(frozen=True)
class BankMovementAccountSummary:
    bank_id: int
    bank_name: str
    bank_account_id: int
    account_name: str
    currency_code: str
    transaction_count: int
    incoming_count: int
    outgoing_count: int
    incoming_totals: dict[str, Decimal]
    outgoing_totals: dict[str, Decimal]
    net_totals: dict[str, Decimal]


@dataclass(frozen=True)
class BankMovementReportSummary:
    total_count: int
    incoming_count: int
    outgoing_count: int
    planned_count: int
    realized_count: int
    cancelled_count: int

    incoming_totals: dict[str, Decimal]
    outgoing_totals: dict[str, Decimal]
    net_totals: dict[str, Decimal]

    planned_totals: dict[str, Decimal]
    realized_totals: dict[str, Decimal]
    cancelled_totals: dict[str, Decimal]

    account_summaries: list[BankMovementAccountSummary]


@dataclass(frozen=True)
class BankMovementReportData:
    filters: BankMovementReportFilter
    report_period_text: str
    rows: list[BankMovementReportRow]
    summary: BankMovementReportSummary


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
        totals.get(normalized_currency_code, Decimal("0.00"))
        + _decimal_or_zero(amount)
    ).quantize(Decimal("0.01"))


def _subtract_from_totals(
    totals: dict[str, Decimal],
    currency_code: str,
    amount: Decimal,
) -> None:
    normalized_currency_code = str(currency_code or "TRY").strip().upper() or "TRY"

    totals[normalized_currency_code] = (
        totals.get(normalized_currency_code, Decimal("0.00"))
        - _decimal_or_zero(amount)
    ).quantize(Decimal("0.01"))


def _format_date_tr(value: date) -> str:
    return value.strftime("%d.%m.%Y")


def _direction_text(direction: Any) -> str:
    normalized_direction = _enum_value(direction)

    return DIRECTION_TEXTS.get(normalized_direction, normalized_direction or "-")


def _status_text(status: Any) -> str:
    normalized_status = _enum_value(status)

    return STATUS_TEXTS.get(normalized_status, normalized_status or "-")


def _source_type_text(source_type: Any) -> str:
    normalized_source_type = _enum_value(source_type)

    return SOURCE_TYPE_TEXTS.get(normalized_source_type, normalized_source_type or "-")


def _row_style_for_report(direction: str, status: str) -> str:
    if status == "CANCELLED":
        return "MUTED"

    if status == "PLANNED":
        return "WARNING"

    if direction == "IN":
        return "SUCCESS"

    if direction == "OUT":
        return "RISK"

    return "NORMAL"


def _should_include_row(
    *,
    row_direction: str,
    row_status: str,
    row_currency_code: str,
    row_source_type: str,
    direction_filter: str,
    status_filter: str,
    currency_code_filter: str,
    source_type_filter: str,
) -> bool:
    if direction_filter != "ALL" and row_direction != direction_filter:
        return False

    if status_filter != "ALL" and row_status != status_filter:
        return False

    if currency_code_filter != "ALL" and row_currency_code != currency_code_filter:
        return False

    if source_type_filter != "ALL" and row_source_type != source_type_filter:
        return False

    return True


def _build_account_summaries(
    rows: list[BankMovementReportRow],
) -> list[BankMovementAccountSummary]:
    grouped: dict[int, dict[str, Any]] = {}

    for row in rows:
        if row.bank_account_id not in grouped:
            grouped[row.bank_account_id] = {
                "bank_id": row.bank_id,
                "bank_name": row.bank_name,
                "bank_account_id": row.bank_account_id,
                "account_name": row.account_name,
                "currency_code": row.currency_code,
                "transaction_count": 0,
                "incoming_count": 0,
                "outgoing_count": 0,
                "incoming_totals": {},
                "outgoing_totals": {},
                "net_totals": {},
            }

        account_data = grouped[row.bank_account_id]
        account_data["transaction_count"] += 1

        if row.status == "CANCELLED":
            continue

        if row.direction == "IN":
            account_data["incoming_count"] += 1
            _add_to_totals(
                account_data["incoming_totals"],
                row.currency_code,
                row.amount,
            )
            _add_to_totals(
                account_data["net_totals"],
                row.currency_code,
                row.amount,
            )

        if row.direction == "OUT":
            account_data["outgoing_count"] += 1
            _add_to_totals(
                account_data["outgoing_totals"],
                row.currency_code,
                row.amount,
            )
            _subtract_from_totals(
                account_data["net_totals"],
                row.currency_code,
                row.amount,
            )

    account_summaries: list[BankMovementAccountSummary] = []

    for values in grouped.values():
        account_summaries.append(
            BankMovementAccountSummary(
                bank_id=int(values["bank_id"]),
                bank_name=str(values["bank_name"]),
                bank_account_id=int(values["bank_account_id"]),
                account_name=str(values["account_name"]),
                currency_code=str(values["currency_code"]),
                transaction_count=int(values["transaction_count"]),
                incoming_count=int(values["incoming_count"]),
                outgoing_count=int(values["outgoing_count"]),
                incoming_totals=dict(values["incoming_totals"]),
                outgoing_totals=dict(values["outgoing_totals"]),
                net_totals=dict(values["net_totals"]),
            )
        )

    account_summaries.sort(
        key=lambda item: (
            item.bank_name.lower(),
            item.account_name.lower(),
            item.currency_code,
        )
    )

    return account_summaries


def _build_summary(
    rows: list[BankMovementReportRow],
) -> BankMovementReportSummary:
    incoming_count = 0
    outgoing_count = 0
    planned_count = 0
    realized_count = 0
    cancelled_count = 0

    incoming_totals: dict[str, Decimal] = {}
    outgoing_totals: dict[str, Decimal] = {}
    net_totals: dict[str, Decimal] = {}

    planned_totals: dict[str, Decimal] = {}
    realized_totals: dict[str, Decimal] = {}
    cancelled_totals: dict[str, Decimal] = {}

    for row in rows:
        if row.status == "PLANNED":
            planned_count += 1
            _add_to_totals(planned_totals, row.currency_code, row.amount)

        if row.status == "REALIZED":
            realized_count += 1
            _add_to_totals(realized_totals, row.currency_code, row.amount)

        if row.status == "CANCELLED":
            cancelled_count += 1
            _add_to_totals(cancelled_totals, row.currency_code, row.amount)
            continue

        if row.direction == "IN":
            incoming_count += 1
            _add_to_totals(incoming_totals, row.currency_code, row.amount)
            _add_to_totals(net_totals, row.currency_code, row.amount)

        if row.direction == "OUT":
            outgoing_count += 1
            _add_to_totals(outgoing_totals, row.currency_code, row.amount)
            _subtract_from_totals(net_totals, row.currency_code, row.amount)

    return BankMovementReportSummary(
        total_count=len(rows),
        incoming_count=incoming_count,
        outgoing_count=outgoing_count,
        planned_count=planned_count,
        realized_count=realized_count,
        cancelled_count=cancelled_count,
        incoming_totals=incoming_totals,
        outgoing_totals=outgoing_totals,
        net_totals=net_totals,
        planned_totals=planned_totals,
        realized_totals=realized_totals,
        cancelled_totals=cancelled_totals,
        account_summaries=_build_account_summaries(rows),
    )


def _build_row(
    *,
    transaction: BankTransaction,
    bank_account: BankAccount,
    bank: Bank,
) -> BankMovementReportRow:
    direction = _enum_value(transaction.direction)
    status = _enum_value(transaction.status)
    currency_code = _enum_value(transaction.currency_code) or "TRY"
    source_type = _enum_value(transaction.source_type)

    return BankMovementReportRow(
        transaction_id=transaction.id,
        bank_id=bank.id,
        bank_name=bank.name,
        bank_account_id=bank_account.id,
        account_name=bank_account.account_name,
        transaction_date=transaction.transaction_date,
        value_date=transaction.value_date,
        direction=direction,
        direction_text=_direction_text(direction),
        status=status,
        status_text=_status_text(status),
        amount=_decimal_or_zero(transaction.amount),
        currency_code=currency_code,
        source_type=source_type,
        source_type_text=_source_type_text(source_type),
        reference_no=transaction.reference_no,
        description=transaction.description,
        row_style=_row_style_for_report(
            direction=direction,
            status=status,
        ),
    )


def load_bank_movement_report_data(
    report_filter: BankMovementReportFilter,
) -> BankMovementReportData:
    start_date = report_filter.start_date
    end_date = report_filter.end_date

    if end_date < start_date:
        raise ValueError("Bitiş tarihi başlangıç tarihinden küçük olamaz.")

    direction_filter = _normalize_filter_value(report_filter.direction)
    status_filter = _normalize_filter_value(report_filter.status)
    currency_code_filter = _normalize_filter_value(report_filter.currency_code)
    source_type_filter = _normalize_filter_value(report_filter.source_type)

    rows: list[BankMovementReportRow] = []

    with session_scope() as session:
        statement = (
            select(BankTransaction, BankAccount, Bank)
            .join(BankAccount, BankTransaction.bank_account_id == BankAccount.id)
            .join(Bank, BankAccount.bank_id == Bank.id)
            .where(
                BankTransaction.transaction_date >= start_date,
                BankTransaction.transaction_date <= end_date,
            )
            .order_by(
                BankTransaction.transaction_date.asc(),
                Bank.name.asc(),
                BankAccount.account_name.asc(),
                BankTransaction.id.asc(),
            )
        )

        if report_filter.bank_id is not None:
            statement = statement.where(Bank.id == report_filter.bank_id)

        if report_filter.bank_account_id is not None:
            statement = statement.where(BankAccount.id == report_filter.bank_account_id)

        result_rows = session.execute(statement).all()

        for transaction, bank_account, bank in result_rows:
            row = _build_row(
                transaction=transaction,
                bank_account=bank_account,
                bank=bank,
            )

            if not _should_include_row(
                row_direction=row.direction,
                row_status=row.status,
                row_currency_code=row.currency_code,
                row_source_type=row.source_type,
                direction_filter=direction_filter,
                status_filter=status_filter,
                currency_code_filter=currency_code_filter,
                source_type_filter=source_type_filter,
            ):
                continue

            rows.append(row)

    summary = _build_summary(rows)

    return BankMovementReportData(
        filters=BankMovementReportFilter(
            start_date=start_date,
            end_date=end_date,
            bank_id=report_filter.bank_id,
            bank_account_id=report_filter.bank_account_id,
            direction=direction_filter,
            status=status_filter,
            currency_code=currency_code_filter,
            source_type=source_type_filter,
        ),
        report_period_text=f"{_format_date_tr(start_date)} - {_format_date_tr(end_date)}",
        rows=rows,
        summary=summary,
    )


def load_default_current_month_bank_movement_report_data() -> BankMovementReportData:
    today = date.today()
    start_date = date(today.year, today.month, 1)

    if today.month == 12:
        end_date = date(today.year, 12, 31)
    else:
        end_date = date(today.year, today.month + 1, 1) - timedelta(days=1)

    return load_bank_movement_report_data(
        BankMovementReportFilter(
            start_date=start_date,
            end_date=end_date,
            bank_id=None,
            bank_account_id=None,
            direction="ALL",
            status="ALL",
            currency_code="ALL",
            source_type="ALL",
        )
    )