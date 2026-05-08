from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import aliased

from app.db.session import session_scope
from app.models.bank import Bank, BankAccount
from app.models.bank_transaction import BankTransaction
from app.models.business_partner import BusinessPartner
from app.models.check import IssuedCheck, ReceivedCheck, ReceivedCheckMovement
from app.models.enums import (
    BusinessPartnerType,
    CurrencyCode,
    IssuedCheckStatus,
    ReceivedCheckMovementType,
    ReceivedCheckStatus,
)
from app.utils.decimal_utils import money


class PartnerStatementDataError(ValueError):
    pass


@dataclass(frozen=True)
class PartnerStatementFilter:
    partner_id: int
    start_date: date
    end_date: date


@dataclass(frozen=True)
class PartnerStatementPartnerInfo:
    partner_id: int
    name: str
    partner_type: str
    partner_type_text: str
    tax_number: str | None
    tax_office: str | None
    authorized_person: str | None
    phone: str | None
    email: str | None
    is_active: bool
    status_text: str


@dataclass(frozen=True)
class PartnerStatementMovementRow:
    movement_date: date
    sort_order: int
    source_type: str
    source_id: int
    movement_id: int | None
    title: str
    operation_type: str
    check_direction: str
    check_id: int
    check_number: str
    due_date: date | None
    bank_text: str
    account_text: str
    description: str
    debit_amount: Decimal
    credit_amount: Decimal
    currency_code: str
    status_text: str
    reference_no: str | None


@dataclass(frozen=True)
class PartnerStatementCurrencySummary:
    currency_code: str
    received_check_total: Decimal = Decimal("0.00")
    received_check_count: int = 0
    received_movement_count: int = 0
    issued_check_total: Decimal = Decimal("0.00")
    issued_check_count: int = 0
    issued_paid_total: Decimal = Decimal("0.00")
    issued_paid_count: int = 0
    issued_cancelled_total: Decimal = Decimal("0.00")
    issued_cancelled_count: int = 0


@dataclass(frozen=True)
class PartnerStatementData:
    report_filter: PartnerStatementFilter
    partner: PartnerStatementPartnerInfo
    rows: list[PartnerStatementMovementRow]
    currency_summaries: list[PartnerStatementCurrencySummary]
    total_row_count: int
    received_check_count: int
    received_movement_count: int
    issued_check_count: int
    issued_paid_count: int
    issued_cancelled_count: int


def _enum_value(value: Any) -> str:
    if value is None:
        return ""

    if hasattr(value, "value"):
        return str(value.value).strip().upper()

    return str(value).strip().upper()


def _safe_text(value: Any, default: str = "-") -> str:
    text = str(value or "").strip()
    return text if text else default


def _normalize_currency_code(value: Any) -> str:
    normalized_value = _enum_value(value)
    return normalized_value or "TRY"


def _validate_partner_statement_filter(report_filter: PartnerStatementFilter) -> PartnerStatementFilter:
    try:
        partner_id = int(report_filter.partner_id)
    except (TypeError, ValueError) as exc:
        raise PartnerStatementDataError("Cari ID sayısal olmalıdır.") from exc

    if partner_id <= 0:
        raise PartnerStatementDataError("Cari ID sıfırdan büyük olmalıdır.")

    if not isinstance(report_filter.start_date, date):
        raise PartnerStatementDataError("Başlangıç tarihi geçerli bir tarih olmalıdır.")

    if not isinstance(report_filter.end_date, date):
        raise PartnerStatementDataError("Bitiş tarihi geçerli bir tarih olmalıdır.")

    if report_filter.end_date < report_filter.start_date:
        raise PartnerStatementDataError("Bitiş tarihi başlangıç tarihinden önce olamaz.")

    return PartnerStatementFilter(
        partner_id=partner_id,
        start_date=report_filter.start_date,
        end_date=report_filter.end_date,
    )


def _partner_type_text(value: Any) -> str:
    normalized_value = _enum_value(value)

    if normalized_value == BusinessPartnerType.CUSTOMER.value:
        return "Müşteri"

    if normalized_value == BusinessPartnerType.SUPPLIER.value:
        return "Tedarikçi"

    if normalized_value == BusinessPartnerType.BOTH.value:
        return "Müşteri / Tedarikçi"

    if normalized_value == BusinessPartnerType.OTHER.value:
        return "Diğer"

    return normalized_value or "-"


def _issued_status_text(value: Any) -> str:
    normalized_value = _enum_value(value)

    if normalized_value == IssuedCheckStatus.PREPARED.value:
        return "Hazırlandı"

    if normalized_value == IssuedCheckStatus.GIVEN.value:
        return "Verildi"

    if normalized_value == IssuedCheckStatus.PAID.value:
        return "Ödendi"

    if normalized_value == IssuedCheckStatus.CANCELLED.value:
        return "İptal"

    if normalized_value == IssuedCheckStatus.RISK.value:
        return "Riskli"

    return normalized_value or "-"


def _received_status_text(value: Any) -> str:
    normalized_value = _enum_value(value)

    if normalized_value == ReceivedCheckStatus.PORTFOLIO.value:
        return "Portföy"

    if normalized_value == ReceivedCheckStatus.GIVEN_TO_BANK.value:
        return "Bankaya Verildi"

    if normalized_value == ReceivedCheckStatus.IN_COLLECTION.value:
        return "Tahsilde"

    if normalized_value == ReceivedCheckStatus.COLLECTED.value:
        return "Tahsil Edildi"

    if normalized_value == ReceivedCheckStatus.BOUNCED.value:
        return "Karşılıksız"

    if normalized_value == ReceivedCheckStatus.RETURNED.value:
        return "İade"

    if normalized_value == ReceivedCheckStatus.ENDORSED.value:
        return "Ciro Edildi"

    if normalized_value == ReceivedCheckStatus.DISCOUNTED.value:
        return "İskontoya Verildi"

    if normalized_value == ReceivedCheckStatus.CANCELLED.value:
        return "İptal"

    return normalized_value or "-"


def _received_movement_type_text(value: Any) -> str:
    normalized_value = _enum_value(value)

    mapping = {
        ReceivedCheckMovementType.REGISTERED.value: "Alınan Çek Kaydı",
        ReceivedCheckMovementType.SENT_TO_BANK_COLLECTION.value: "Bankaya Tahsile Verildi",
        ReceivedCheckMovementType.MARKED_IN_COLLECTION.value: "Tahsilde İşaretlendi",
        ReceivedCheckMovementType.COLLECTED.value: "Tahsil Edildi",
        ReceivedCheckMovementType.ENDORSED.value: "Ciro Edildi",
        ReceivedCheckMovementType.DISCOUNTED.value: "İskontoya Verildi / Kırdırıldı",
        ReceivedCheckMovementType.BOUNCED.value: "Karşılıksız İşaretlendi",
        ReceivedCheckMovementType.RETURNED.value: "İade Edildi",
        ReceivedCheckMovementType.CANCELLED.value: "İptal Edildi",
        ReceivedCheckMovementType.REVERSED.value: "Ters Kayıt / Geri Alındı",
    }

    return mapping.get(normalized_value, normalized_value or "-")


def _bank_account_text(bank: Bank | None, bank_account: BankAccount | None) -> tuple[str, str]:
    if bank_account is None:
        return "-", "-"

    bank_text = _safe_text(bank.name if bank else None)
    account_text = _safe_text(bank_account.account_name)

    return bank_text, account_text


def _datetime_or_none(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value

    return None


def _date_or_none(value: Any) -> date | None:
    if isinstance(value, date):
        return value

    return None


def _add_summary_amount(
    summaries: dict[str, dict[str, Any]],
    currency_code: str,
    key: str,
    amount: Decimal,
) -> None:
    normalized_currency_code = _normalize_currency_code(currency_code)

    if normalized_currency_code not in summaries:
        summaries[normalized_currency_code] = {
            "received_check_total": Decimal("0.00"),
            "received_check_count": 0,
            "received_movement_count": 0,
            "issued_check_total": Decimal("0.00"),
            "issued_check_count": 0,
            "issued_paid_total": Decimal("0.00"),
            "issued_paid_count": 0,
            "issued_cancelled_total": Decimal("0.00"),
            "issued_cancelled_count": 0,
        }

    if key.endswith("_count"):
        summaries[normalized_currency_code][key] = int(summaries[normalized_currency_code][key]) + int(amount)
        return

    summaries[normalized_currency_code][key] = (
        money(summaries[normalized_currency_code][key], field_name="Özet tutar")
        + money(amount, field_name="Özet tutar")
    )


def _summary_rows_from_dict(summaries: dict[str, dict[str, Any]]) -> list[PartnerStatementCurrencySummary]:
    priority = {"TRY": 0, "USD": 1, "EUR": 2, "GBP": 3}

    rows: list[PartnerStatementCurrencySummary] = []

    for currency_code, values in summaries.items():
        rows.append(
            PartnerStatementCurrencySummary(
                currency_code=currency_code,
                received_check_total=money(values["received_check_total"], field_name="Alınan çek toplamı"),
                received_check_count=int(values["received_check_count"]),
                received_movement_count=int(values["received_movement_count"]),
                issued_check_total=money(values["issued_check_total"], field_name="Yazılan çek toplamı"),
                issued_check_count=int(values["issued_check_count"]),
                issued_paid_total=money(values["issued_paid_total"], field_name="Ödenen yazılan çek toplamı"),
                issued_paid_count=int(values["issued_paid_count"]),
                issued_cancelled_total=money(values["issued_cancelled_total"], field_name="İptal yazılan çek toplamı"),
                issued_cancelled_count=int(values["issued_cancelled_count"]),
            )
        )

    rows.sort(key=lambda item: (priority.get(item.currency_code, 99), item.currency_code))
    return rows


def _load_partner_info(session: Any, partner_id: int) -> PartnerStatementPartnerInfo:
    partner = session.get(BusinessPartner, partner_id)

    if partner is None:
        raise PartnerStatementDataError(f"Cari kart bulunamadı. Cari ID: {partner_id}")

    return PartnerStatementPartnerInfo(
        partner_id=partner.id,
        name=partner.name,
        partner_type=_enum_value(partner.partner_type),
        partner_type_text=_partner_type_text(partner.partner_type),
        tax_number=partner.tax_number,
        tax_office=partner.tax_office,
        authorized_person=partner.authorized_person,
        phone=partner.phone,
        email=partner.email,
        is_active=bool(partner.is_active),
        status_text="Aktif" if partner.is_active else "Pasif",
    )


def _load_received_check_rows(
    session: Any,
    *,
    partner_id: int,
    start_date: date,
    end_date: date,
    summaries: dict[str, dict[str, Any]],
) -> list[PartnerStatementMovementRow]:
    collection_bank_account_alias = aliased(BankAccount)
    collection_bank_alias = aliased(Bank)

    statement = (
        select(
            ReceivedCheck,
            collection_bank_account_alias,
            collection_bank_alias,
        )
        .outerjoin(
            collection_bank_account_alias,
            ReceivedCheck.collection_bank_account_id == collection_bank_account_alias.id,
        )
        .outerjoin(
            collection_bank_alias,
            collection_bank_account_alias.bank_id == collection_bank_alias.id,
        )
        .where(
            ReceivedCheck.customer_id == partner_id,
            ReceivedCheck.received_date >= start_date,
            ReceivedCheck.received_date <= end_date,
        )
        .order_by(ReceivedCheck.received_date.asc(), ReceivedCheck.id.asc())
    )

    rows: list[PartnerStatementMovementRow] = []

    for received_check, collection_bank_account, collection_bank in session.execute(statement).all():
        currency_code = _normalize_currency_code(received_check.currency_code)
        amount = money(received_check.amount, field_name="Alınan çek tutarı")
        bank_text, account_text = _bank_account_text(collection_bank, collection_bank_account)

        _add_summary_amount(summaries, currency_code, "received_check_total", amount)
        _add_summary_amount(summaries, currency_code, "received_check_count", Decimal("1"))

        rows.append(
            PartnerStatementMovementRow(
                movement_date=received_check.received_date,
                sort_order=10,
                source_type="RECEIVED_CHECK",
                source_id=received_check.id,
                movement_id=None,
                title="Alınan Çek",
                operation_type="Alınan Çek Kaydı",
                check_direction="ALINAN",
                check_id=received_check.id,
                check_number=received_check.check_number,
                due_date=received_check.due_date,
                bank_text=_safe_text(received_check.drawer_bank_name),
                account_text=(
                    f"Tahsil Hesabı: {bank_text} / {account_text}"
                    if collection_bank_account is not None
                    else "Tahsil Hesabı: -"
                ),
                description=(
                    f"Cari tarafından verilen alınan çek kaydı. "
                    f"Keşideci banka: {_safe_text(received_check.drawer_bank_name)}. "
                    f"Durum: {_received_status_text(received_check.status)}."
                    + (f" Açıklama: {received_check.description}" if received_check.description else "")
                ),
                debit_amount=Decimal("0.00"),
                credit_amount=amount,
                currency_code=currency_code,
                status_text=_received_status_text(received_check.status),
                reference_no=received_check.reference_no,
            )
        )

    return rows


def _load_received_check_movement_rows(
    session: Any,
    *,
    partner_id: int,
    start_date: date,
    end_date: date,
    summaries: dict[str, dict[str, Any]],
) -> list[PartnerStatementMovementRow]:
    bank_account_alias = aliased(BankAccount)
    bank_alias = aliased(Bank)

    statement = (
        select(
            ReceivedCheckMovement,
            ReceivedCheck,
            bank_account_alias,
            bank_alias,
        )
        .join(ReceivedCheck, ReceivedCheckMovement.received_check_id == ReceivedCheck.id)
        .outerjoin(bank_account_alias, ReceivedCheckMovement.bank_account_id == bank_account_alias.id)
        .outerjoin(bank_alias, bank_account_alias.bank_id == bank_alias.id)
        .where(
            ReceivedCheck.customer_id == partner_id,
            ReceivedCheckMovement.movement_date >= start_date,
            ReceivedCheckMovement.movement_date <= end_date,
        )
        .order_by(ReceivedCheckMovement.movement_date.asc(), ReceivedCheckMovement.id.asc())
    )

    rows: list[PartnerStatementMovementRow] = []

    for movement, received_check, bank_account, bank in session.execute(statement).all():
        currency_code = _normalize_currency_code(movement.currency_code)
        gross_amount = money(movement.gross_amount, field_name="Alınan çek hareket tutarı")
        bank_text, account_text = _bank_account_text(bank, bank_account)
        movement_type_text = _received_movement_type_text(movement.movement_type)
        net_bank_amount = (
            money(movement.net_bank_amount, field_name="Net banka tutarı")
            if movement.net_bank_amount is not None
            else None
        )

        _add_summary_amount(summaries, currency_code, "received_movement_count", Decimal("1"))

        amount_for_row = net_bank_amount if net_bank_amount is not None else gross_amount

        if _enum_value(movement.movement_type) == ReceivedCheckMovementType.REGISTERED.value:
            # İlk alınan çek kaydı ayrı satırda zaten gösterildiği için burada tekrar finansal etki oluşturmayalım.
            debit_amount = Decimal("0.00")
            credit_amount = Decimal("0.00")
        elif _enum_value(movement.movement_type) in {
            ReceivedCheckMovementType.COLLECTED.value,
            ReceivedCheckMovementType.DISCOUNTED.value,
            ReceivedCheckMovementType.ENDORSED.value,
            ReceivedCheckMovementType.RETURNED.value,
        }:
            debit_amount = Decimal("0.00")
            credit_amount = amount_for_row
        elif _enum_value(movement.movement_type) in {
            ReceivedCheckMovementType.BOUNCED.value,
            ReceivedCheckMovementType.CANCELLED.value,
            ReceivedCheckMovementType.REVERSED.value,
        }:
            debit_amount = amount_for_row
            credit_amount = Decimal("0.00")
        else:
            debit_amount = Decimal("0.00")
            credit_amount = Decimal("0.00")

        description_parts = [
            movement.purpose_text or movement_type_text,
        ]

        if movement.counterparty_text:
            description_parts.append(f"Karşı taraf: {movement.counterparty_text}")

        if movement.description:
            description_parts.append(movement.description)

        rows.append(
            PartnerStatementMovementRow(
                movement_date=movement.movement_date,
                sort_order=20,
                source_type="RECEIVED_CHECK_MOVEMENT",
                source_id=received_check.id,
                movement_id=movement.id,
                title="Alınan Çek Hareketi",
                operation_type=movement_type_text,
                check_direction="ALINAN",
                check_id=received_check.id,
                check_number=received_check.check_number,
                due_date=received_check.due_date,
                bank_text=_safe_text(received_check.drawer_bank_name),
                account_text=(
                    f"{bank_text} / {account_text}"
                    if bank_account is not None
                    else "-"
                ),
                description=" | ".join(description_parts),
                debit_amount=debit_amount,
                credit_amount=credit_amount,
                currency_code=currency_code,
                status_text=_received_status_text(movement.to_status),
                reference_no=movement.reference_no,
            )
        )

    return rows


def _load_issued_check_rows(
    session: Any,
    *,
    partner_id: int,
    start_date: date,
    end_date: date,
    summaries: dict[str, dict[str, Any]],
) -> list[PartnerStatementMovementRow]:
    bank_account_alias = aliased(BankAccount)
    bank_alias = aliased(Bank)
    paid_transaction_alias = aliased(BankTransaction)

    statement = (
        select(
            IssuedCheck,
            bank_account_alias,
            bank_alias,
            paid_transaction_alias,
        )
        .join(bank_account_alias, IssuedCheck.bank_account_id == bank_account_alias.id)
        .join(bank_alias, bank_account_alias.bank_id == bank_alias.id)
        .outerjoin(paid_transaction_alias, IssuedCheck.paid_transaction_id == paid_transaction_alias.id)
        .where(
            IssuedCheck.supplier_id == partner_id,
            IssuedCheck.issue_date >= start_date,
            IssuedCheck.issue_date <= end_date,
        )
        .order_by(IssuedCheck.issue_date.asc(), IssuedCheck.id.asc())
    )

    rows: list[PartnerStatementMovementRow] = []

    for issued_check, bank_account, bank, paid_transaction in session.execute(statement).all():
        currency_code = _normalize_currency_code(issued_check.currency_code)
        amount = money(issued_check.amount, field_name="Yazılan çek tutarı")
        bank_text, account_text = _bank_account_text(bank, bank_account)

        _add_summary_amount(summaries, currency_code, "issued_check_total", amount)
        _add_summary_amount(summaries, currency_code, "issued_check_count", Decimal("1"))

        rows.append(
            PartnerStatementMovementRow(
                movement_date=issued_check.issue_date,
                sort_order=30,
                source_type="ISSUED_CHECK",
                source_id=issued_check.id,
                movement_id=None,
                title="Yazılan Çek",
                operation_type="Yazılan Çek Kaydı",
                check_direction="YAZILAN",
                check_id=issued_check.id,
                check_number=issued_check.check_number,
                due_date=issued_check.due_date,
                bank_text=bank_text,
                account_text=account_text,
                description=(
                    f"Cari tarafa yazılan çek kaydı. "
                    f"Banka/Hesap: {bank_text} / {account_text}. "
                    f"Durum: {_issued_status_text(issued_check.status)}."
                    + (f" Açıklama: {issued_check.description}" if issued_check.description else "")
                ),
                debit_amount=amount,
                credit_amount=Decimal("0.00"),
                currency_code=currency_code,
                status_text=_issued_status_text(issued_check.status),
                reference_no=issued_check.reference_no,
            )
        )

        paid_date = _date_or_none(getattr(paid_transaction, "transaction_date", None))
        if paid_date is not None and start_date <= paid_date <= end_date:
            _add_summary_amount(summaries, currency_code, "issued_paid_total", amount)
            _add_summary_amount(summaries, currency_code, "issued_paid_count", Decimal("1"))

            rows.append(
                PartnerStatementMovementRow(
                    movement_date=paid_date,
                    sort_order=40,
                    source_type="ISSUED_CHECK_PAYMENT",
                    source_id=issued_check.id,
                    movement_id=getattr(paid_transaction, "id", None),
                    title="Yazılan Çek Ödemesi",
                    operation_type="Yazılan Çek Ödendi",
                    check_direction="YAZILAN",
                    check_id=issued_check.id,
                    check_number=issued_check.check_number,
                    due_date=issued_check.due_date,
                    bank_text=bank_text,
                    account_text=account_text,
                    description=(
                        f"Yazılan çek ödendi. Banka/Hesap: {bank_text} / {account_text}."
                        + (f" Açıklama: {paid_transaction.description}" if getattr(paid_transaction, "description", None) else "")
                    ),
                    debit_amount=Decimal("0.00"),
                    credit_amount=amount,
                    currency_code=currency_code,
                    status_text="Ödendi",
                    reference_no=getattr(paid_transaction, "reference_no", None) or issued_check.reference_no,
                )
            )

        cancelled_at = _datetime_or_none(issued_check.cancelled_at)
        if cancelled_at is not None:
            cancel_date = cancelled_at.date()
            if start_date <= cancel_date <= end_date:
                _add_summary_amount(summaries, currency_code, "issued_cancelled_total", amount)
                _add_summary_amount(summaries, currency_code, "issued_cancelled_count", Decimal("1"))

                rows.append(
                    PartnerStatementMovementRow(
                        movement_date=cancel_date,
                        sort_order=50,
                        source_type="ISSUED_CHECK_CANCELLED",
                        source_id=issued_check.id,
                        movement_id=None,
                        title="Yazılan Çek İptali",
                        operation_type="Yazılan Çek İptal Edildi",
                        check_direction="YAZILAN",
                        check_id=issued_check.id,
                        check_number=issued_check.check_number,
                        due_date=issued_check.due_date,
                        bank_text=bank_text,
                        account_text=account_text,
                        description=(
                            "Yazılan çek iptal edildi."
                            + (f" İptal nedeni: {issued_check.cancel_reason}" if issued_check.cancel_reason else "")
                        ),
                        debit_amount=Decimal("0.00"),
                        credit_amount=amount,
                        currency_code=currency_code,
                        status_text="İptal",
                        reference_no=issued_check.reference_no,
                    )
                )

    return rows


def load_partner_statement_data(report_filter: PartnerStatementFilter) -> PartnerStatementData:
    normalized_filter = _validate_partner_statement_filter(report_filter)

    with session_scope() as session:
        partner_info = _load_partner_info(session, normalized_filter.partner_id)
        summaries: dict[str, dict[str, Any]] = {}
        rows: list[PartnerStatementMovementRow] = []

        received_check_rows = _load_received_check_rows(
            session,
            partner_id=normalized_filter.partner_id,
            start_date=normalized_filter.start_date,
            end_date=normalized_filter.end_date,
            summaries=summaries,
        )
        rows.extend(received_check_rows)

        received_movement_rows = _load_received_check_movement_rows(
            session,
            partner_id=normalized_filter.partner_id,
            start_date=normalized_filter.start_date,
            end_date=normalized_filter.end_date,
            summaries=summaries,
        )
        rows.extend(received_movement_rows)

        issued_check_rows = _load_issued_check_rows(
            session,
            partner_id=normalized_filter.partner_id,
            start_date=normalized_filter.start_date,
            end_date=normalized_filter.end_date,
            summaries=summaries,
        )
        rows.extend(issued_check_rows)

        rows.sort(
            key=lambda row: (
                row.movement_date,
                row.sort_order,
                row.check_direction,
                row.check_id,
                row.movement_id or 0,
            )
        )

        currency_summaries = _summary_rows_from_dict(summaries)

        return PartnerStatementData(
            report_filter=normalized_filter,
            partner=partner_info,
            rows=rows,
            currency_summaries=currency_summaries,
            total_row_count=len(rows),
            received_check_count=len(received_check_rows),
            received_movement_count=len(received_movement_rows),
            issued_check_count=len([
                row
                for row in issued_check_rows
                if row.source_type == "ISSUED_CHECK"
            ]),
            issued_paid_count=len([
                row
                for row in issued_check_rows
                if row.source_type == "ISSUED_CHECK_PAYMENT"
            ]),
            issued_cancelled_count=len([
                row
                for row in issued_check_rows
                if row.source_type == "ISSUED_CHECK_CANCELLED"
            ]),
        )
