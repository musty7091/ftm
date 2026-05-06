from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from math import ceil
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import aliased

from app.db.session import session_scope
from app.models.bank import Bank, BankAccount
from app.models.business_partner import BusinessPartner
from app.models.check import IssuedCheck, ReceivedCheck
from app.models.enums import IssuedCheckStatus, ReceivedCheckStatus
from app.ui.ui_helpers import decimal_or_zero, tr_money


CURRENCY_DISPLAY_ORDER = ["TRY", "USD", "EUR", "GBP"]

DEFAULT_CHECK_TABLE_PAGE_SIZE = 25
MAX_CHECK_TABLE_PAGE_SIZE = 500
LEGACY_CHECK_PAGE_PREVIEW_LIMIT = 200


ISSUED_PENDING_STATUSES = {
    IssuedCheckStatus.PREPARED.value,
    IssuedCheckStatus.GIVEN.value,
}

RECEIVED_PENDING_STATUSES = {
    ReceivedCheckStatus.PORTFOLIO.value,
    ReceivedCheckStatus.GIVEN_TO_BANK.value,
    ReceivedCheckStatus.IN_COLLECTION.value,
}

ISSUED_PROBLEM_STATUSES = {
    IssuedCheckStatus.RISK.value,
}

RECEIVED_PROBLEM_STATUSES = {
    ReceivedCheckStatus.BOUNCED.value,
}

ISSUED_CLOSED_STATUSES = {
    IssuedCheckStatus.PAID.value,
    IssuedCheckStatus.CANCELLED.value,
}

RECEIVED_CLOSED_STATUSES = {
    ReceivedCheckStatus.COLLECTED.value,
    ReceivedCheckStatus.ENDORSED.value,
    ReceivedCheckStatus.DISCOUNTED.value,
    ReceivedCheckStatus.RETURNED.value,
    ReceivedCheckStatus.CANCELLED.value,
}


@dataclass
class IssuedCheckRow:
    issued_check_id: int
    supplier_name: str
    bank_name: str
    bank_account_name: str
    check_number: str
    issue_date_text: str
    due_date_text: str
    amount: Any
    currency_code: str
    status: str
    reference_no: str | None
    description: str | None


@dataclass
class ReceivedCheckRow:
    received_check_id: int
    customer_name: str
    drawer_bank_name: str
    collection_bank_name: str | None
    collection_bank_account_name: str | None
    check_number: str
    received_date_text: str
    due_date_text: str
    amount: Any
    currency_code: str
    status: str
    reference_no: str | None
    description: str | None


@dataclass
class CheckTableData:
    rows: list[Any]
    total_count: int
    page_index: int
    page_size: int
    total_pages: int
    currency_totals: dict[str, Any]
    error_message: str | None = None


@dataclass
class ChecksSummaryData:
    pending_issued_count: int
    pending_received_count: int
    pending_issued_currency_totals: dict[str, Any]
    pending_received_currency_totals: dict[str, Any]
    issued_due_soon_count: int
    received_due_soon_count: int
    issued_problem_count: int
    received_problem_count: int
    error_message: str | None = None


@dataclass
class ChecksPageData:
    issued_checks: list[IssuedCheckRow]
    received_checks: list[ReceivedCheckRow]
    pending_issued_count: int
    pending_received_count: int
    pending_issued_currency_totals: dict[str, Any]
    pending_received_currency_totals: dict[str, Any]
    issued_due_soon_count: int
    received_due_soon_count: int
    issued_problem_count: int
    received_problem_count: int
    error_message: str | None = None


def _enum_value(value: Any) -> str:
    if hasattr(value, "value"):
        return str(value.value)

    return str(value or "").strip().upper()


def _format_decimal_tr(value: Any) -> str:
    amount = decimal_or_zero(value)

    formatted = f"{amount:,.2f}"
    formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")

    return formatted


def format_currency_amount(value: Any, currency_code: str) -> str:
    normalized_currency_code = str(currency_code or "").strip().upper()

    if normalized_currency_code == "TRY":
        return tr_money(value)

    return f"{_format_decimal_tr(value)} {normalized_currency_code}"


def currency_sort_key(currency_code: str) -> tuple[int, str]:
    normalized_currency_code = str(currency_code or "").strip().upper()

    if normalized_currency_code in CURRENCY_DISPLAY_ORDER:
        return (CURRENCY_DISPLAY_ORDER.index(normalized_currency_code), normalized_currency_code)

    return (999, normalized_currency_code)


def build_currency_totals_text(currency_totals: dict[str, Any]) -> str:
    if not currency_totals:
        return "Kayıt yok"

    lines: list[str] = []

    for currency_code in sorted(currency_totals.keys(), key=currency_sort_key):
        lines.append(
            f"{currency_code}: {format_currency_amount(currency_totals[currency_code], currency_code)}"
        )

    return "\n".join(lines)


def issued_status_text(status: str) -> str:
    normalized_status = str(status or "").strip().upper()

    if normalized_status == "PREPARED":
        return "Hazırlandı"

    if normalized_status == "GIVEN":
        return "Verildi"

    if normalized_status == "PAID":
        return "Ödendi"

    if normalized_status == "CANCELLED":
        return "İptal"

    if normalized_status == "RISK":
        return "Risk"

    return normalized_status


def received_status_text(status: str) -> str:
    normalized_status = str(status or "").strip().upper()

    if normalized_status == "PORTFOLIO":
        return "Portföy"

    if normalized_status == "GIVEN_TO_BANK":
        return "Bankaya Verildi"

    if normalized_status == "IN_COLLECTION":
        return "Tahsilde"

    if normalized_status == "COLLECTED":
        return "Tahsil Edildi"

    if normalized_status == "BOUNCED":
        return "Karşılıksız"

    if normalized_status == "RETURNED":
        return "İade"

    if normalized_status == "ENDORSED":
        return "Ciro Edildi"

    if normalized_status == "DISCOUNTED":
        return "İskontoya Verildi"

    if normalized_status == "CANCELLED":
        return "İptal"

    return normalized_status


def _normalize_filter_key(filter_key: str | None) -> str:
    normalized_filter_key = str(filter_key or "OPEN").strip().upper()

    if normalized_filter_key not in {"OPEN", "PROBLEM", "CLOSED", "ALL"}:
        return "OPEN"

    return normalized_filter_key


def _normalize_sort_direction(sort_direction: str | None) -> str:
    normalized_sort_direction = str(sort_direction or "ASC").strip().upper()

    if normalized_sort_direction not in {"ASC", "DESC"}:
        return "ASC"

    return normalized_sort_direction


def _normalize_page_index(page_index: int | str | None) -> int:
    try:
        normalized_page_index = int(page_index or 0)
    except (TypeError, ValueError):
        return 0

    return max(0, normalized_page_index)


def _normalize_page_size(page_size: int | str | None) -> int:
    try:
        normalized_page_size = int(page_size or DEFAULT_CHECK_TABLE_PAGE_SIZE)
    except (TypeError, ValueError):
        return DEFAULT_CHECK_TABLE_PAGE_SIZE

    if normalized_page_size <= 0:
        return DEFAULT_CHECK_TABLE_PAGE_SIZE

    return min(normalized_page_size, MAX_CHECK_TABLE_PAGE_SIZE)


def _empty_table_data(
    *,
    page_index: int = 0,
    page_size: int = DEFAULT_CHECK_TABLE_PAGE_SIZE,
    error_message: str | None = None,
) -> CheckTableData:
    return CheckTableData(
        rows=[],
        total_count=0,
        page_index=page_index,
        page_size=page_size,
        total_pages=1,
        currency_totals={},
        error_message=error_message,
    )


def _status_values_for_issued_filter(filter_key: str) -> list[str] | None:
    normalized_filter_key = _normalize_filter_key(filter_key)

    if normalized_filter_key == "OPEN":
        return sorted(ISSUED_PENDING_STATUSES)

    if normalized_filter_key == "PROBLEM":
        return sorted(ISSUED_PROBLEM_STATUSES)

    if normalized_filter_key == "CLOSED":
        return sorted(ISSUED_CLOSED_STATUSES)

    return None


def _status_values_for_received_filter(filter_key: str) -> list[str] | None:
    normalized_filter_key = _normalize_filter_key(filter_key)

    if normalized_filter_key == "OPEN":
        return sorted(RECEIVED_PENDING_STATUSES)

    if normalized_filter_key == "PROBLEM":
        return sorted(RECEIVED_PROBLEM_STATUSES)

    if normalized_filter_key == "CLOSED":
        return sorted(RECEIVED_CLOSED_STATUSES)

    return None


def _apply_issued_filters(statement: Any, *, search_text: str | None, filter_key: str) -> Any:
    status_values = _status_values_for_issued_filter(filter_key)

    if status_values is not None:
        statement = statement.where(IssuedCheck.status.in_(status_values))

    cleaned_search_text = str(search_text or "").strip()

    if cleaned_search_text:
        like_text = f"%{cleaned_search_text}%"
        statement = statement.where(
            or_(
                BusinessPartner.name.ilike(like_text),
                Bank.name.ilike(like_text),
                BankAccount.account_name.ilike(like_text),
                IssuedCheck.check_number.ilike(like_text),
                IssuedCheck.reference_no.ilike(like_text),
                IssuedCheck.description.ilike(like_text),
            )
        )

    return statement


def _apply_received_filters(
    statement: Any,
    *,
    search_text: str | None,
    filter_key: str,
    collection_bank_account_alias: Any,
    collection_bank_alias: Any,
) -> Any:
    status_values = _status_values_for_received_filter(filter_key)

    if status_values is not None:
        statement = statement.where(ReceivedCheck.status.in_(status_values))

    cleaned_search_text = str(search_text or "").strip()

    if cleaned_search_text:
        like_text = f"%{cleaned_search_text}%"
        statement = statement.where(
            or_(
                BusinessPartner.name.ilike(like_text),
                ReceivedCheck.drawer_bank_name.ilike(like_text),
                ReceivedCheck.drawer_branch_name.ilike(like_text),
                collection_bank_alias.name.ilike(like_text),
                collection_bank_account_alias.account_name.ilike(like_text),
                ReceivedCheck.check_number.ilike(like_text),
                ReceivedCheck.reference_no.ilike(like_text),
                ReceivedCheck.description.ilike(like_text),
            )
        )

    return statement


def _issued_order_expressions(sort_key: str | None, sort_direction: str | None) -> list[Any]:
    normalized_sort_key = str(sort_key or "due_date").strip().lower()
    normalized_sort_direction = _normalize_sort_direction(sort_direction)

    if normalized_sort_key == "id":
        primary_expression = IssuedCheck.id
    elif normalized_sort_key == "supplier_name":
        primary_expression = func.lower(BusinessPartner.name)
    elif normalized_sort_key == "bank_account":
        primary_expression = func.lower(Bank.name + " / " + BankAccount.account_name)
    elif normalized_sort_key == "check_number":
        primary_expression = func.lower(IssuedCheck.check_number)
    elif normalized_sort_key == "issue_date":
        primary_expression = IssuedCheck.issue_date
    elif normalized_sort_key == "due_date":
        primary_expression = IssuedCheck.due_date
    elif normalized_sort_key == "amount":
        primary_expression = IssuedCheck.amount
    elif normalized_sort_key == "status":
        primary_expression = IssuedCheck.status
    elif normalized_sort_key == "reference_no":
        primary_expression = func.lower(func.coalesce(IssuedCheck.reference_no, ""))
    else:
        primary_expression = IssuedCheck.due_date

    if normalized_sort_direction == "DESC":
        return [primary_expression.desc(), IssuedCheck.id.desc()]

    return [primary_expression.asc(), IssuedCheck.id.desc()]


def _received_order_expressions(
    sort_key: str | None,
    sort_direction: str | None,
    *,
    collection_bank_account_alias: Any,
    collection_bank_alias: Any,
) -> list[Any]:
    normalized_sort_key = str(sort_key or "due_date").strip().lower()
    normalized_sort_direction = _normalize_sort_direction(sort_direction)

    if normalized_sort_key == "id":
        primary_expression = ReceivedCheck.id
    elif normalized_sort_key == "customer_name":
        primary_expression = func.lower(BusinessPartner.name)
    elif normalized_sort_key == "drawer_bank_name":
        primary_expression = func.lower(ReceivedCheck.drawer_bank_name)
    elif normalized_sort_key == "collection_account":
        primary_expression = func.lower(
            func.coalesce(collection_bank_alias.name, "") + " / " + func.coalesce(collection_bank_account_alias.account_name, "")
        )
    elif normalized_sort_key == "check_number":
        primary_expression = func.lower(ReceivedCheck.check_number)
    elif normalized_sort_key == "received_date":
        primary_expression = ReceivedCheck.received_date
    elif normalized_sort_key == "due_date":
        primary_expression = ReceivedCheck.due_date
    elif normalized_sort_key == "amount":
        primary_expression = ReceivedCheck.amount
    elif normalized_sort_key == "status":
        primary_expression = ReceivedCheck.status
    elif normalized_sort_key == "reference_no":
        primary_expression = func.lower(func.coalesce(ReceivedCheck.reference_no, ""))
    else:
        primary_expression = ReceivedCheck.due_date

    if normalized_sort_direction == "DESC":
        return [primary_expression.desc(), ReceivedCheck.id.desc()]

    return [primary_expression.asc(), ReceivedCheck.id.desc()]


def _issued_row_from_orm(
    issued_check: IssuedCheck,
    supplier: BusinessPartner,
    bank_account: BankAccount,
    bank: Bank,
) -> IssuedCheckRow:
    return IssuedCheckRow(
        issued_check_id=issued_check.id,
        supplier_name=supplier.name,
        bank_name=bank.name,
        bank_account_name=bank_account.account_name,
        check_number=issued_check.check_number,
        issue_date_text=issued_check.issue_date.strftime("%d.%m.%Y"),
        due_date_text=issued_check.due_date.strftime("%d.%m.%Y"),
        amount=issued_check.amount,
        currency_code=_enum_value(issued_check.currency_code),
        status=_enum_value(issued_check.status),
        reference_no=issued_check.reference_no,
        description=issued_check.description,
    )


def _received_row_from_orm(
    received_check: ReceivedCheck,
    customer: BusinessPartner,
    collection_bank_account: BankAccount | None,
    collection_bank: Bank | None,
) -> ReceivedCheckRow:
    return ReceivedCheckRow(
        received_check_id=received_check.id,
        customer_name=customer.name,
        drawer_bank_name=received_check.drawer_bank_name,
        collection_bank_name=collection_bank.name if collection_bank else None,
        collection_bank_account_name=(
            collection_bank_account.account_name if collection_bank_account else None
        ),
        check_number=received_check.check_number,
        received_date_text=received_check.received_date.strftime("%d.%m.%Y"),
        due_date_text=received_check.due_date.strftime("%d.%m.%Y"),
        amount=received_check.amount,
        currency_code=_enum_value(received_check.currency_code),
        status=_enum_value(received_check.status),
        reference_no=received_check.reference_no,
        description=received_check.description,
    )


def _issued_currency_totals(
    *,
    search_text: str | None,
    filter_key: str,
) -> dict[str, Any]:
    statement = (
        select(IssuedCheck.currency_code, func.coalesce(func.sum(IssuedCheck.amount), Decimal("0.00")))
        .join(BusinessPartner, IssuedCheck.supplier_id == BusinessPartner.id)
        .join(BankAccount, IssuedCheck.bank_account_id == BankAccount.id)
        .join(Bank, BankAccount.bank_id == Bank.id)
        .group_by(IssuedCheck.currency_code)
    )

    statement = _apply_issued_filters(
        statement,
        search_text=search_text,
        filter_key=filter_key,
    )

    totals: dict[str, Any] = {}

    with session_scope() as session:
        for currency_code, total_amount in session.execute(statement).all():
            totals[_enum_value(currency_code)] = decimal_or_zero(total_amount)

    return totals


def _received_currency_totals(
    *,
    search_text: str | None,
    filter_key: str,
) -> dict[str, Any]:
    collection_bank_account_alias = aliased(BankAccount)
    collection_bank_alias = aliased(Bank)

    statement = (
        select(ReceivedCheck.currency_code, func.coalesce(func.sum(ReceivedCheck.amount), Decimal("0.00")))
        .join(BusinessPartner, ReceivedCheck.customer_id == BusinessPartner.id)
        .outerjoin(
            collection_bank_account_alias,
            ReceivedCheck.collection_bank_account_id == collection_bank_account_alias.id,
        )
        .outerjoin(
            collection_bank_alias,
            collection_bank_account_alias.bank_id == collection_bank_alias.id,
        )
        .group_by(ReceivedCheck.currency_code)
    )

    statement = _apply_received_filters(
        statement,
        search_text=search_text,
        filter_key=filter_key,
        collection_bank_account_alias=collection_bank_account_alias,
        collection_bank_alias=collection_bank_alias,
    )

    totals: dict[str, Any] = {}

    with session_scope() as session:
        for currency_code, total_amount in session.execute(statement).all():
            totals[_enum_value(currency_code)] = decimal_or_zero(total_amount)

    return totals


def load_issued_checks_table_data(
    *,
    search_text: str | None = None,
    filter_key: str = "OPEN",
    sort_key: str = "due_date",
    sort_direction: str = "ASC",
    page_index: int = 0,
    page_size: int = DEFAULT_CHECK_TABLE_PAGE_SIZE,
) -> CheckTableData:
    normalized_filter_key = _normalize_filter_key(filter_key)
    normalized_sort_direction = _normalize_sort_direction(sort_direction)
    normalized_page_index = _normalize_page_index(page_index)
    normalized_page_size = _normalize_page_size(page_size)

    try:
        count_statement = (
            select(func.count(IssuedCheck.id))
            .join(BusinessPartner, IssuedCheck.supplier_id == BusinessPartner.id)
            .join(BankAccount, IssuedCheck.bank_account_id == BankAccount.id)
            .join(Bank, BankAccount.bank_id == Bank.id)
        )
        count_statement = _apply_issued_filters(
            count_statement,
            search_text=search_text,
            filter_key=normalized_filter_key,
        )

        row_statement = (
            select(IssuedCheck, BusinessPartner, BankAccount, Bank)
            .join(BusinessPartner, IssuedCheck.supplier_id == BusinessPartner.id)
            .join(BankAccount, IssuedCheck.bank_account_id == BankAccount.id)
            .join(Bank, BankAccount.bank_id == Bank.id)
        )
        row_statement = _apply_issued_filters(
            row_statement,
            search_text=search_text,
            filter_key=normalized_filter_key,
        )
        row_statement = row_statement.order_by(
            *_issued_order_expressions(sort_key, normalized_sort_direction)
        )

        with session_scope() as session:
            total_count = int(session.execute(count_statement).scalar_one() or 0)
            total_pages = max(1, ceil(total_count / normalized_page_size))

            if normalized_page_index >= total_pages:
                normalized_page_index = total_pages - 1

            row_statement = (
                row_statement
                .offset(normalized_page_index * normalized_page_size)
                .limit(normalized_page_size)
            )

            rows = [
                _issued_row_from_orm(issued_check, supplier, bank_account, bank)
                for issued_check, supplier, bank_account, bank in session.execute(row_statement).all()
            ]

        currency_totals = _issued_currency_totals(
            search_text=search_text,
            filter_key=normalized_filter_key,
        )

        return CheckTableData(
            rows=rows,
            total_count=total_count,
            page_index=normalized_page_index,
            page_size=normalized_page_size,
            total_pages=total_pages,
            currency_totals=currency_totals,
            error_message=None,
        )

    except Exception as exc:
        return _empty_table_data(
            page_index=normalized_page_index,
            page_size=normalized_page_size,
            error_message=str(exc),
        )


def load_received_checks_table_data(
    *,
    search_text: str | None = None,
    filter_key: str = "OPEN",
    sort_key: str = "due_date",
    sort_direction: str = "ASC",
    page_index: int = 0,
    page_size: int = DEFAULT_CHECK_TABLE_PAGE_SIZE,
) -> CheckTableData:
    normalized_filter_key = _normalize_filter_key(filter_key)
    normalized_sort_direction = _normalize_sort_direction(sort_direction)
    normalized_page_index = _normalize_page_index(page_index)
    normalized_page_size = _normalize_page_size(page_size)

    collection_bank_account_alias = aliased(BankAccount)
    collection_bank_alias = aliased(Bank)

    try:
        count_statement = (
            select(func.count(ReceivedCheck.id))
            .join(BusinessPartner, ReceivedCheck.customer_id == BusinessPartner.id)
            .outerjoin(
                collection_bank_account_alias,
                ReceivedCheck.collection_bank_account_id == collection_bank_account_alias.id,
            )
            .outerjoin(
                collection_bank_alias,
                collection_bank_account_alias.bank_id == collection_bank_alias.id,
            )
        )
        count_statement = _apply_received_filters(
            count_statement,
            search_text=search_text,
            filter_key=normalized_filter_key,
            collection_bank_account_alias=collection_bank_account_alias,
            collection_bank_alias=collection_bank_alias,
        )

        row_statement = (
            select(
                ReceivedCheck,
                BusinessPartner,
                collection_bank_account_alias,
                collection_bank_alias,
            )
            .join(BusinessPartner, ReceivedCheck.customer_id == BusinessPartner.id)
            .outerjoin(
                collection_bank_account_alias,
                ReceivedCheck.collection_bank_account_id == collection_bank_account_alias.id,
            )
            .outerjoin(
                collection_bank_alias,
                collection_bank_account_alias.bank_id == collection_bank_alias.id,
            )
        )
        row_statement = _apply_received_filters(
            row_statement,
            search_text=search_text,
            filter_key=normalized_filter_key,
            collection_bank_account_alias=collection_bank_account_alias,
            collection_bank_alias=collection_bank_alias,
        )
        row_statement = row_statement.order_by(
            *_received_order_expressions(
                sort_key,
                normalized_sort_direction,
                collection_bank_account_alias=collection_bank_account_alias,
                collection_bank_alias=collection_bank_alias,
            )
        )

        with session_scope() as session:
            total_count = int(session.execute(count_statement).scalar_one() or 0)
            total_pages = max(1, ceil(total_count / normalized_page_size))

            if normalized_page_index >= total_pages:
                normalized_page_index = total_pages - 1

            row_statement = (
                row_statement
                .offset(normalized_page_index * normalized_page_size)
                .limit(normalized_page_size)
            )

            rows = [
                _received_row_from_orm(received_check, customer, collection_bank_account, collection_bank)
                for received_check, customer, collection_bank_account, collection_bank in session.execute(row_statement).all()
            ]

        currency_totals = _received_currency_totals(
            search_text=search_text,
            filter_key=normalized_filter_key,
        )

        return CheckTableData(
            rows=rows,
            total_count=total_count,
            page_index=normalized_page_index,
            page_size=normalized_page_size,
            total_pages=total_pages,
            currency_totals=currency_totals,
            error_message=None,
        )

    except Exception as exc:
        return _empty_table_data(
            page_index=normalized_page_index,
            page_size=normalized_page_size,
            error_message=str(exc),
        )


def load_checks_summary_data() -> ChecksSummaryData:
    try:
        with session_scope() as session:
            today = date.today()
            due_soon_end_date = today + timedelta(days=7)

            pending_issued_totals_statement = (
                select(
                    IssuedCheck.currency_code,
                    func.count(IssuedCheck.id),
                    func.coalesce(func.sum(IssuedCheck.amount), Decimal("0.00")),
                )
                .where(IssuedCheck.status.in_(sorted(ISSUED_PENDING_STATUSES)))
                .group_by(IssuedCheck.currency_code)
            )

            pending_received_totals_statement = (
                select(
                    ReceivedCheck.currency_code,
                    func.count(ReceivedCheck.id),
                    func.coalesce(func.sum(ReceivedCheck.amount), Decimal("0.00")),
                )
                .where(ReceivedCheck.status.in_(sorted(RECEIVED_PENDING_STATUSES)))
                .group_by(ReceivedCheck.currency_code)
            )

            pending_issued_count = 0
            pending_issued_currency_totals: dict[str, Any] = {}

            for currency_code, row_count, total_amount in session.execute(pending_issued_totals_statement).all():
                pending_issued_count += int(row_count or 0)
                pending_issued_currency_totals[_enum_value(currency_code)] = decimal_or_zero(total_amount)

            pending_received_count = 0
            pending_received_currency_totals: dict[str, Any] = {}

            for currency_code, row_count, total_amount in session.execute(pending_received_totals_statement).all():
                pending_received_count += int(row_count or 0)
                pending_received_currency_totals[_enum_value(currency_code)] = decimal_or_zero(total_amount)

            issued_due_soon_count = int(
                session.execute(
                    select(func.count(IssuedCheck.id)).where(
                        IssuedCheck.status.in_(sorted(ISSUED_PENDING_STATUSES)),
                        IssuedCheck.due_date >= today,
                        IssuedCheck.due_date <= due_soon_end_date,
                    )
                ).scalar_one() or 0
            )

            received_due_soon_count = int(
                session.execute(
                    select(func.count(ReceivedCheck.id)).where(
                        ReceivedCheck.status.in_(sorted(RECEIVED_PENDING_STATUSES)),
                        ReceivedCheck.due_date >= today,
                        ReceivedCheck.due_date <= due_soon_end_date,
                    )
                ).scalar_one() or 0
            )

            issued_problem_count = int(
                session.execute(
                    select(func.count(IssuedCheck.id)).where(
                        IssuedCheck.status.in_(sorted(ISSUED_PROBLEM_STATUSES))
                    )
                ).scalar_one() or 0
            )

            received_problem_count = int(
                session.execute(
                    select(func.count(ReceivedCheck.id)).where(
                        ReceivedCheck.status.in_(sorted(RECEIVED_PROBLEM_STATUSES))
                    )
                ).scalar_one() or 0
            )

            return ChecksSummaryData(
                pending_issued_count=pending_issued_count,
                pending_received_count=pending_received_count,
                pending_issued_currency_totals=pending_issued_currency_totals,
                pending_received_currency_totals=pending_received_currency_totals,
                issued_due_soon_count=issued_due_soon_count,
                received_due_soon_count=received_due_soon_count,
                issued_problem_count=issued_problem_count,
                received_problem_count=received_problem_count,
                error_message=None,
            )

    except Exception as exc:
        return ChecksSummaryData(
            pending_issued_count=0,
            pending_received_count=0,
            pending_issued_currency_totals={},
            pending_received_currency_totals={},
            issued_due_soon_count=0,
            received_due_soon_count=0,
            issued_problem_count=0,
            received_problem_count=0,
            error_message=str(exc),
        )


def load_checks_page_data() -> ChecksPageData:
    summary_data = load_checks_summary_data()

    if summary_data.error_message:
        return ChecksPageData(
            issued_checks=[],
            received_checks=[],
            pending_issued_count=0,
            pending_received_count=0,
            pending_issued_currency_totals={},
            pending_received_currency_totals={},
            issued_due_soon_count=0,
            received_due_soon_count=0,
            issued_problem_count=0,
            received_problem_count=0,
            error_message=summary_data.error_message,
        )

    issued_table_data = load_issued_checks_table_data(
        search_text=None,
        filter_key="ALL",
        sort_key="due_date",
        sort_direction="ASC",
        page_index=0,
        page_size=LEGACY_CHECK_PAGE_PREVIEW_LIMIT,
    )

    if issued_table_data.error_message:
        return ChecksPageData(
            issued_checks=[],
            received_checks=[],
            pending_issued_count=0,
            pending_received_count=0,
            pending_issued_currency_totals={},
            pending_received_currency_totals={},
            issued_due_soon_count=0,
            received_due_soon_count=0,
            issued_problem_count=0,
            received_problem_count=0,
            error_message=issued_table_data.error_message,
        )

    received_table_data = load_received_checks_table_data(
        search_text=None,
        filter_key="ALL",
        sort_key="due_date",
        sort_direction="ASC",
        page_index=0,
        page_size=LEGACY_CHECK_PAGE_PREVIEW_LIMIT,
    )

    if received_table_data.error_message:
        return ChecksPageData(
            issued_checks=[],
            received_checks=[],
            pending_issued_count=0,
            pending_received_count=0,
            pending_issued_currency_totals={},
            pending_received_currency_totals={},
            issued_due_soon_count=0,
            received_due_soon_count=0,
            issued_problem_count=0,
            received_problem_count=0,
            error_message=received_table_data.error_message,
        )

    return ChecksPageData(
        issued_checks=issued_table_data.rows,
        received_checks=received_table_data.rows,
        pending_issued_count=summary_data.pending_issued_count,
        pending_received_count=summary_data.pending_received_count,
        pending_issued_currency_totals=summary_data.pending_issued_currency_totals,
        pending_received_currency_totals=summary_data.pending_received_currency_totals,
        issued_due_soon_count=summary_data.issued_due_soon_count,
        received_due_soon_count=summary_data.received_due_soon_count,
        issued_problem_count=summary_data.issued_problem_count,
        received_problem_count=summary_data.received_problem_count,
        error_message=None,
    )
