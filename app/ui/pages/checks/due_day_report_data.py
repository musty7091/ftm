from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import aliased

from app.db.session import session_scope
from app.models.bank import Bank, BankAccount
from app.models.business_partner import BusinessPartner
from app.models.check import IssuedCheck, ReceivedCheck
from app.models.enums import IssuedCheckStatus, ReceivedCheckStatus
from app.ui.ui_helpers import decimal_or_zero


ISSUED_PENDING_STATUSES = {
    IssuedCheckStatus.PREPARED.value,
    IssuedCheckStatus.GIVEN.value,
}

ISSUED_PROBLEM_STATUSES = {
    IssuedCheckStatus.RISK.value,
}

ISSUED_CLOSED_STATUSES = {
    IssuedCheckStatus.PAID.value,
    IssuedCheckStatus.CANCELLED.value,
}

RECEIVED_PENDING_STATUSES = {
    ReceivedCheckStatus.PORTFOLIO.value,
    ReceivedCheckStatus.GIVEN_TO_BANK.value,
    ReceivedCheckStatus.IN_COLLECTION.value,
}

RECEIVED_PROBLEM_STATUSES = {
    ReceivedCheckStatus.BOUNCED.value,
}

RECEIVED_CLOSED_STATUSES = {
    ReceivedCheckStatus.COLLECTED.value,
    ReceivedCheckStatus.ENDORSED.value,
    ReceivedCheckStatus.DISCOUNTED.value,
    ReceivedCheckStatus.RETURNED.value,
    ReceivedCheckStatus.CANCELLED.value,
}

CURRENCY_DISPLAY_ORDER = ["TRY", "USD", "EUR", "GBP"]


@dataclass(frozen=True)
class DueDayCheckRow:
    check_type: str
    check_id: int
    party_name: str
    bank_text: str
    check_number: str
    transaction_date_text: str
    due_date_text: str
    remaining_day_text: str
    amount: Decimal
    currency_code: str
    amount_text: str
    status: str
    status_text: str
    status_group: str
    reference_no: str | None
    description: str | None


@dataclass(frozen=True)
class DueDayCurrencyLine:
    currency_code: str
    incoming_total: Decimal
    outgoing_total: Decimal
    net_total: Decimal
    incoming_total_text: str
    outgoing_total_text: str
    net_total_text: str


@dataclass(frozen=True)
class DueDayReportData:
    report_date: date
    report_date_text: str
    generated_at: datetime
    generated_at_text: str
    check_type_filter: str
    status_filter: str
    received_rows: list[DueDayCheckRow]
    issued_rows: list[DueDayCheckRow]
    currency_lines: list[DueDayCurrencyLine]
    incoming_totals: dict[str, Decimal]
    outgoing_totals: dict[str, Decimal]
    net_totals: dict[str, Decimal]
    received_count: int
    issued_count: int
    total_count: int
    pending_count: int
    closed_count: int
    problem_count: int
    overdue_count: int
    warning_messages: list[str]
    error_message: str | None = None


def _normalize_report_date(value: date | datetime | str) -> date:
    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    cleaned_value = str(value or "").strip()

    if not cleaned_value:
        raise ValueError("Rapor tarihi boş olamaz.")

    for date_format in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(cleaned_value, date_format).date()
        except ValueError:
            continue

    raise ValueError(
        "Rapor tarihi okunamadı. Desteklenen formatlar: YYYY-MM-DD, DD.MM.YYYY, DD/MM/YYYY."
    )


def _enum_value(value: Any) -> str:
    if value is None:
        return ""

    if hasattr(value, "value"):
        return str(value.value).strip().upper()

    return str(value).strip().upper()


def _display_currency_code(currency_code: str) -> str:
    normalized_currency_code = str(currency_code or "").strip().upper()

    if normalized_currency_code == "TRY":
        return "TL"

    return normalized_currency_code or "TL"


def _currency_sort_key(currency_code: str) -> tuple[int, str]:
    normalized_currency_code = str(currency_code or "").strip().upper()

    if normalized_currency_code in CURRENCY_DISPLAY_ORDER:
        return (CURRENCY_DISPLAY_ORDER.index(normalized_currency_code), normalized_currency_code)

    return (999, normalized_currency_code)


def _format_date_tr(value: date | None) -> str:
    if value is None:
        return "-"

    return value.strftime("%d.%m.%Y")


def _format_datetime_tr(value: datetime | None) -> str:
    if value is None:
        return "-"

    return value.strftime("%d.%m.%Y %H:%M")


def _format_decimal_tr(value: Any) -> str:
    amount = decimal_or_zero(value)

    formatted = f"{amount:,.2f}"
    return formatted.replace(",", "X").replace(".", ",").replace("X", ".")


def format_currency_amount(value: Any, currency_code: str) -> str:
    return f"{_format_decimal_tr(value)} {_display_currency_code(currency_code)}"


def build_currency_totals_text(currency_totals: dict[str, Decimal]) -> str:
    if not currency_totals:
        return "0,00 TL"

    parts: list[str] = []

    for currency_code in sorted(currency_totals.keys(), key=_currency_sort_key):
        parts.append(format_currency_amount(currency_totals[currency_code], currency_code))

    return " / ".join(parts)


def _add_to_totals(totals: dict[str, Decimal], currency_code: str, amount: Any) -> None:
    normalized_currency_code = str(currency_code or "TRY").strip().upper()
    totals[normalized_currency_code] = (
        totals.get(normalized_currency_code, Decimal("0.00")) + decimal_or_zero(amount)
    ).quantize(Decimal("0.01"))


def _subtract_from_totals(totals: dict[str, Decimal], currency_code: str, amount: Any) -> None:
    normalized_currency_code = str(currency_code or "TRY").strip().upper()
    totals[normalized_currency_code] = (
        totals.get(normalized_currency_code, Decimal("0.00")) - decimal_or_zero(amount)
    ).quantize(Decimal("0.01"))


def _status_group(check_type: str, status: str) -> str:
    normalized_status = str(status or "").strip().upper()

    if check_type == "RECEIVED":
        if normalized_status in RECEIVED_PENDING_STATUSES:
            return "PENDING"
        if normalized_status in RECEIVED_PROBLEM_STATUSES:
            return "PROBLEM"
        if normalized_status in RECEIVED_CLOSED_STATUSES:
            return "CLOSED"

    if check_type == "ISSUED":
        if normalized_status in ISSUED_PENDING_STATUSES:
            return "PENDING"
        if normalized_status in ISSUED_PROBLEM_STATUSES:
            return "PROBLEM"
        if normalized_status in ISSUED_CLOSED_STATUSES:
            return "CLOSED"

    return "OTHER"


def _status_matches_filter(
    *,
    check_type: str,
    status: str,
    due_date: date,
    report_date: date,
    today: date,
    status_filter: str,
) -> bool:
    normalized_status_filter = str(status_filter or "ALL").strip().upper()
    group = _status_group(check_type, status)

    if normalized_status_filter == "ALL":
        return True

    if normalized_status_filter == "PENDING":
        return group == "PENDING"

    if normalized_status_filter == "CLOSED":
        return group == "CLOSED"

    if normalized_status_filter == "PROBLEM":
        return group == "PROBLEM"

    if normalized_status_filter == "OVERDUE":
        return group == "PENDING" and due_date < today

    if normalized_status_filter == "TODAY":
        return due_date == report_date

    return True


def _remaining_day_text(target_date: date, today: date) -> str:
    difference = (target_date - today).days

    if difference == 0:
        return "Bugün"

    if difference > 0:
        return f"{difference} gün"

    return f"{abs(difference)} gün geçti"


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
        return "Riskli"

    return normalized_status or "-"


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

    return normalized_status or "-"


def _normalize_check_type_filter(check_type_filter: str | None) -> str:
    normalized_check_type_filter = str(check_type_filter or "ALL").strip().upper()

    if normalized_check_type_filter not in {"ALL", "RECEIVED", "ISSUED"}:
        return "ALL"

    return normalized_check_type_filter


def _normalize_status_filter(status_filter: str | None) -> str:
    normalized_status_filter = str(status_filter or "ALL").strip().upper()

    if normalized_status_filter not in {"ALL", "PENDING", "CLOSED", "PROBLEM", "OVERDUE", "TODAY"}:
        return "ALL"

    return normalized_status_filter


def _build_received_bank_text(
    *,
    drawer_bank_name: str | None,
    collection_bank_name: str | None,
    collection_bank_account_name: str | None,
) -> str:
    parts: list[str] = []

    cleaned_drawer_bank_name = str(drawer_bank_name or "").strip()

    if cleaned_drawer_bank_name:
        parts.append(f"Keşideci: {cleaned_drawer_bank_name}")

    if collection_bank_name and collection_bank_account_name:
        parts.append(f"Tahsil: {collection_bank_name} / {collection_bank_account_name}")

    if not parts:
        return "-"

    return " | ".join(parts)


def _build_issued_bank_text(
    *,
    bank_name: str | None,
    bank_account_name: str | None,
) -> str:
    if bank_name and bank_account_name:
        return f"{bank_name} / {bank_account_name}"

    if bank_name:
        return bank_name

    if bank_account_name:
        return bank_account_name

    return "-"


def _load_received_rows(
    *,
    session: Any,
    report_date: date,
    today: date,
    status_filter: str,
) -> list[DueDayCheckRow]:
    collection_bank_account_alias = aliased(BankAccount)
    collection_bank_alias = aliased(Bank)

    statement = (
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
        .where(ReceivedCheck.due_date == report_date)
        .order_by(ReceivedCheck.id.asc())
    )

    rows: list[DueDayCheckRow] = []

    for received_check, customer, collection_bank_account, collection_bank in session.execute(statement).all():
        status = _enum_value(received_check.status)

        if not _status_matches_filter(
            check_type="RECEIVED",
            status=status,
            due_date=received_check.due_date,
            report_date=report_date,
            today=today,
            status_filter=status_filter,
        ):
            continue

        currency_code = _enum_value(received_check.currency_code) or "TRY"
        amount = decimal_or_zero(received_check.amount)

        rows.append(
            DueDayCheckRow(
                check_type="RECEIVED",
                check_id=received_check.id,
                party_name=customer.name,
                bank_text=_build_received_bank_text(
                    drawer_bank_name=received_check.drawer_bank_name,
                    collection_bank_name=collection_bank.name if collection_bank else None,
                    collection_bank_account_name=(
                        collection_bank_account.account_name if collection_bank_account else None
                    ),
                ),
                check_number=received_check.check_number,
                transaction_date_text=_format_date_tr(received_check.received_date),
                due_date_text=_format_date_tr(received_check.due_date),
                remaining_day_text=_remaining_day_text(received_check.due_date, today),
                amount=amount,
                currency_code=currency_code,
                amount_text=format_currency_amount(amount, currency_code),
                status=status,
                status_text=received_status_text(status),
                status_group=_status_group("RECEIVED", status),
                reference_no=received_check.reference_no,
                description=received_check.description,
            )
        )

    return rows


def _load_issued_rows(
    *,
    session: Any,
    report_date: date,
    today: date,
    status_filter: str,
) -> list[DueDayCheckRow]:
    statement = (
        select(IssuedCheck, BusinessPartner, BankAccount, Bank)
        .join(BusinessPartner, IssuedCheck.supplier_id == BusinessPartner.id)
        .join(BankAccount, IssuedCheck.bank_account_id == BankAccount.id)
        .join(Bank, BankAccount.bank_id == Bank.id)
        .where(IssuedCheck.due_date == report_date)
        .order_by(IssuedCheck.id.asc())
    )

    rows: list[DueDayCheckRow] = []

    for issued_check, supplier, bank_account, bank in session.execute(statement).all():
        status = _enum_value(issued_check.status)

        if not _status_matches_filter(
            check_type="ISSUED",
            status=status,
            due_date=issued_check.due_date,
            report_date=report_date,
            today=today,
            status_filter=status_filter,
        ):
            continue

        currency_code = _enum_value(issued_check.currency_code) or "TRY"
        amount = decimal_or_zero(issued_check.amount)

        rows.append(
            DueDayCheckRow(
                check_type="ISSUED",
                check_id=issued_check.id,
                party_name=supplier.name,
                bank_text=_build_issued_bank_text(
                    bank_name=bank.name,
                    bank_account_name=bank_account.account_name,
                ),
                check_number=issued_check.check_number,
                transaction_date_text=_format_date_tr(issued_check.issue_date),
                due_date_text=_format_date_tr(issued_check.due_date),
                remaining_day_text=_remaining_day_text(issued_check.due_date, today),
                amount=amount,
                currency_code=currency_code,
                amount_text=format_currency_amount(amount, currency_code),
                status=status,
                status_text=issued_status_text(status),
                status_group=_status_group("ISSUED", status),
                reference_no=issued_check.reference_no,
                description=issued_check.description,
            )
        )

    return rows


def _build_currency_lines(
    *,
    incoming_totals: dict[str, Decimal],
    outgoing_totals: dict[str, Decimal],
    net_totals: dict[str, Decimal],
) -> list[DueDayCurrencyLine]:
    currency_codes = sorted(
        set(incoming_totals.keys()) | set(outgoing_totals.keys()) | set(net_totals.keys()),
        key=_currency_sort_key,
    )

    lines: list[DueDayCurrencyLine] = []

    for currency_code in currency_codes:
        incoming_total = incoming_totals.get(currency_code, Decimal("0.00"))
        outgoing_total = outgoing_totals.get(currency_code, Decimal("0.00"))
        net_total = net_totals.get(currency_code, Decimal("0.00"))

        lines.append(
            DueDayCurrencyLine(
                currency_code=currency_code,
                incoming_total=incoming_total,
                outgoing_total=outgoing_total,
                net_total=net_total,
                incoming_total_text=format_currency_amount(incoming_total, currency_code),
                outgoing_total_text=format_currency_amount(outgoing_total, currency_code),
                net_total_text=format_currency_amount(net_total, currency_code),
            )
        )

    return lines


def _build_warnings(
    *,
    report_date: date,
    today: date,
    received_rows: list[DueDayCheckRow],
    issued_rows: list[DueDayCheckRow],
    incoming_totals: dict[str, Decimal],
    outgoing_totals: dict[str, Decimal],
    net_totals: dict[str, Decimal],
    problem_count: int,
    overdue_count: int,
) -> list[str]:
    warnings: list[str] = []

    if not received_rows and not issued_rows:
        warnings.append("Seçili gün için çek kaydı bulunmuyor.")

    if overdue_count > 0:
        warnings.append(f"{overdue_count} adet vadesi geçmiş bekleyen çek var.")

    if problem_count > 0:
        warnings.append(f"{problem_count} adet problemli / riskli çek var.")

    currency_count = len(set(incoming_totals.keys()) | set(outgoing_totals.keys()) | set(net_totals.keys()))

    if currency_count > 1:
        warnings.append(
            f"Seçili günde {currency_count} farklı para birimi etkisi var. Tutarlar kur çevrimi yapılmadan ayrı gösterilir."
        )

    if issued_rows and not received_rows:
        warnings.append("Seçili günde sadece ödeme / çıkış etkisi var.")

    if received_rows and not issued_rows:
        warnings.append("Seçili günde sadece tahsilat / giriş etkisi var.")

    if report_date < today and overdue_count == 0 and (received_rows or issued_rows):
        warnings.append("Seçili tarih geçmiş bir gündür. Sonuçlanan kayıtları ayrıca kontrol et.")

    return warnings


def _sort_report_rows(rows: list[DueDayCheckRow]) -> list[DueDayCheckRow]:
    return sorted(
        rows,
        key=lambda row: (
            row.status_group != "PROBLEM",
            row.status_group != "PENDING",
            row.party_name.lower(),
            row.check_number.lower(),
            row.check_id,
        ),
    )


def load_due_day_report_data(
    report_date: date | datetime | str,
    *,
    check_type_filter: str | None = "ALL",
    status_filter: str | None = "ALL",
) -> DueDayReportData:
    normalized_report_date = _normalize_report_date(report_date)
    normalized_check_type_filter = _normalize_check_type_filter(check_type_filter)
    normalized_status_filter = _normalize_status_filter(status_filter)
    generated_at = datetime.now()
    today = date.today()

    try:
        with session_scope() as session:
            received_rows: list[DueDayCheckRow] = []
            issued_rows: list[DueDayCheckRow] = []

            if normalized_check_type_filter in {"ALL", "RECEIVED"}:
                received_rows = _load_received_rows(
                    session=session,
                    report_date=normalized_report_date,
                    today=today,
                    status_filter=normalized_status_filter,
                )

            if normalized_check_type_filter in {"ALL", "ISSUED"}:
                issued_rows = _load_issued_rows(
                    session=session,
                    report_date=normalized_report_date,
                    today=today,
                    status_filter=normalized_status_filter,
                )

        received_rows = _sort_report_rows(received_rows)
        issued_rows = _sort_report_rows(issued_rows)

        incoming_totals: dict[str, Decimal] = {}
        outgoing_totals: dict[str, Decimal] = {}
        net_totals: dict[str, Decimal] = {}

        pending_count = 0
        closed_count = 0
        problem_count = 0
        overdue_count = 0

        for row in received_rows:
            _add_to_totals(incoming_totals, row.currency_code, row.amount)
            _add_to_totals(net_totals, row.currency_code, row.amount)

            if row.status_group == "PENDING":
                pending_count += 1

                if normalized_report_date < today:
                    overdue_count += 1
            elif row.status_group == "CLOSED":
                closed_count += 1
            elif row.status_group == "PROBLEM":
                problem_count += 1

        for row in issued_rows:
            _add_to_totals(outgoing_totals, row.currency_code, row.amount)
            _subtract_from_totals(net_totals, row.currency_code, row.amount)

            if row.status_group == "PENDING":
                pending_count += 1

                if normalized_report_date < today:
                    overdue_count += 1
            elif row.status_group == "CLOSED":
                closed_count += 1
            elif row.status_group == "PROBLEM":
                problem_count += 1

        currency_lines = _build_currency_lines(
            incoming_totals=incoming_totals,
            outgoing_totals=outgoing_totals,
            net_totals=net_totals,
        )

        warning_messages = _build_warnings(
            report_date=normalized_report_date,
            today=today,
            received_rows=received_rows,
            issued_rows=issued_rows,
            incoming_totals=incoming_totals,
            outgoing_totals=outgoing_totals,
            net_totals=net_totals,
            problem_count=problem_count,
            overdue_count=overdue_count,
        )

        return DueDayReportData(
            report_date=normalized_report_date,
            report_date_text=_format_date_tr(normalized_report_date),
            generated_at=generated_at,
            generated_at_text=_format_datetime_tr(generated_at),
            check_type_filter=normalized_check_type_filter,
            status_filter=normalized_status_filter,
            received_rows=received_rows,
            issued_rows=issued_rows,
            currency_lines=currency_lines,
            incoming_totals=incoming_totals,
            outgoing_totals=outgoing_totals,
            net_totals=net_totals,
            received_count=len(received_rows),
            issued_count=len(issued_rows),
            total_count=len(received_rows) + len(issued_rows),
            pending_count=pending_count,
            closed_count=closed_count,
            problem_count=problem_count,
            overdue_count=overdue_count,
            warning_messages=warning_messages,
            error_message=None,
        )

    except Exception as exc:
        return DueDayReportData(
            report_date=normalized_report_date,
            report_date_text=_format_date_tr(normalized_report_date),
            generated_at=generated_at,
            generated_at_text=_format_datetime_tr(generated_at),
            check_type_filter=normalized_check_type_filter,
            status_filter=normalized_status_filter,
            received_rows=[],
            issued_rows=[],
            currency_lines=[],
            incoming_totals={},
            outgoing_totals={},
            net_totals={},
            received_count=0,
            issued_count=0,
            total_count=0,
            pending_count=0,
            closed_count=0,
            problem_count=0,
            overdue_count=0,
            warning_messages=[],
            error_message=str(exc),
        )
