from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import aliased

from app.db.session import session_scope
from app.models.bank import Bank, BankAccount
from app.models.business_partner import BusinessPartner
from app.models.check import IssuedCheck, ReceivedCheck
from app.models.enums import IssuedCheckStatus, ReceivedCheckStatus
from app.ui.ui_helpers import decimal_or_zero, tr_money


CURRENCY_DISPLAY_ORDER = ["TRY", "USD", "EUR", "GBP"]


ISSUED_PENDING_STATUSES = {
    IssuedCheckStatus.PREPARED.value,
    IssuedCheckStatus.GIVEN.value,
}

RECEIVED_PENDING_STATUSES = {
    ReceivedCheckStatus.PORTFOLIO.value,
    ReceivedCheckStatus.GIVEN_TO_BANK.value,
    ReceivedCheckStatus.IN_COLLECTION.value,
}

RECEIVED_PROBLEM_STATUSES = {
    ReceivedCheckStatus.BOUNCED.value,
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


def load_checks_page_data() -> ChecksPageData:
    try:
        with session_scope() as session:
            today = date.today()
            due_soon_end_date = today + timedelta(days=7)

            issued_statement = (
                select(IssuedCheck, BusinessPartner, BankAccount, Bank)
                .join(BusinessPartner, IssuedCheck.supplier_id == BusinessPartner.id)
                .join(BankAccount, IssuedCheck.bank_account_id == BankAccount.id)
                .join(Bank, BankAccount.bank_id == Bank.id)
                .order_by(IssuedCheck.due_date.asc(), IssuedCheck.id.desc())
                .limit(200)
            )

            issued_rows = session.execute(issued_statement).all()

            issued_checks: list[IssuedCheckRow] = []
            pending_issued_count = 0
            issued_due_soon_count = 0
            issued_problem_count = 0
            pending_issued_currency_totals: dict[str, Any] = {}

            for issued_check, supplier, bank_account, bank in issued_rows:
                status_value = _enum_value(issued_check.status)
                currency_code = _enum_value(issued_check.currency_code)

                if status_value in ISSUED_PENDING_STATUSES:
                    pending_issued_count += 1
                    pending_issued_currency_totals[currency_code] = decimal_or_zero(
                        pending_issued_currency_totals.get(currency_code, "0.00")
                    ) + decimal_or_zero(issued_check.amount)

                    if today <= issued_check.due_date <= due_soon_end_date:
                        issued_due_soon_count += 1

                if status_value == IssuedCheckStatus.RISK.value:
                    issued_problem_count += 1

                issued_checks.append(
                    IssuedCheckRow(
                        issued_check_id=issued_check.id,
                        supplier_name=supplier.name,
                        bank_name=bank.name,
                        bank_account_name=bank_account.account_name,
                        check_number=issued_check.check_number,
                        issue_date_text=issued_check.issue_date.strftime("%d.%m.%Y"),
                        due_date_text=issued_check.due_date.strftime("%d.%m.%Y"),
                        amount=issued_check.amount,
                        currency_code=currency_code,
                        status=status_value,
                        reference_no=issued_check.reference_no,
                        description=issued_check.description,
                    )
                )

            collection_bank_account_alias = aliased(BankAccount)
            collection_bank_alias = aliased(Bank)

            received_statement = (
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
                .order_by(ReceivedCheck.due_date.asc(), ReceivedCheck.id.desc())
                .limit(200)
            )

            received_rows = session.execute(received_statement).all()

            received_checks: list[ReceivedCheckRow] = []
            pending_received_count = 0
            received_due_soon_count = 0
            received_problem_count = 0
            pending_received_currency_totals: dict[str, Any] = {}

            for received_check, customer, collection_bank_account, collection_bank in received_rows:
                status_value = _enum_value(received_check.status)
                currency_code = _enum_value(received_check.currency_code)

                if status_value in RECEIVED_PENDING_STATUSES:
                    pending_received_count += 1
                    pending_received_currency_totals[currency_code] = decimal_or_zero(
                        pending_received_currency_totals.get(currency_code, "0.00")
                    ) + decimal_or_zero(received_check.amount)

                    if today <= received_check.due_date <= due_soon_end_date:
                        received_due_soon_count += 1

                if status_value in RECEIVED_PROBLEM_STATUSES:
                    received_problem_count += 1

                received_checks.append(
                    ReceivedCheckRow(
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
                        currency_code=currency_code,
                        status=status_value,
                        reference_no=received_check.reference_no,
                        description=received_check.description,
                    )
                )

            return ChecksPageData(
                issued_checks=issued_checks,
                received_checks=received_checks,
                pending_issued_count=pending_issued_count,
                pending_received_count=pending_received_count,
                pending_issued_currency_totals=pending_issued_currency_totals,
                pending_received_currency_totals=pending_received_currency_totals,
                issued_due_soon_count=issued_due_soon_count,
                received_due_soon_count=received_due_soon_count,
                issued_problem_count=issued_problem_count,
                received_problem_count=received_problem_count,
            )

    except Exception as exc:
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
            error_message=str(exc),
        )