from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Optional, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import joinedload
from sqlalchemy.orm import Session

from app.models.bank import Bank, BankAccount
from app.models.credit_facility import (
    BankAccountCreditLimit,
    BankAccountCreditLimitTransaction,
    CreditCard,
    CreditCardPayment,
    CreditCardTransaction,
)
from app.models.enums import (
    BankTransactionStatus,
    CreditCardNetwork,
    CreditCardPaymentStatus,
    CreditCardRecommendationStatus,
    CreditCardTransactionStatus,
    CreditCardType,
    CreditLimitTransactionStatus,
    CreditLimitTransactionType,
    CreditLimitType,
    CreditLimitUsageMode,
    CurrencyCode,
    FinancialSourceType,
    InterestPeriod,
    TransactionDirection,
)
from app.services.audit_service import write_audit_log
from app.services.bank_transaction_service import (
    BankTransactionServiceError,
    cancel_bank_transaction,
    create_bank_transaction,
)
from app.utils.decimal_utils import money, rate


class CreditFacilityServiceError(ValueError):
    pass


EnumT = TypeVar("EnumT")


ACTIVE_TRANSACTION_STATUSES = {
    CreditCardTransactionStatus.PENDING,
    CreditCardTransactionStatus.IN_STATEMENT,
}

ACTIVE_PAYMENT_STATUSES = {
    CreditCardPaymentStatus.RECORDED,
}

ACTIVE_CREDIT_LIMIT_TRANSACTION_STATUSES = {
    CreditLimitTransactionStatus.ACTIVE,
}

CREDIT_LIMIT_PRINCIPAL_INCREASE_TYPES = {
    CreditLimitTransactionType.USAGE,
    CreditLimitTransactionType.ADJUSTMENT,
}

CREDIT_LIMIT_DEBT_INCREASE_TYPES = {
    CreditLimitTransactionType.USAGE,
    CreditLimitTransactionType.INTEREST,
    CreditLimitTransactionType.FEE,
    CreditLimitTransactionType.ADJUSTMENT,
}


def _clean_required_text(value: str, field_name: str) -> str:
    cleaned_value = (value or "").strip()

    if not cleaned_value:
        raise CreditFacilityServiceError(f"{field_name} boş olamaz.")

    return cleaned_value


def _clean_optional_text(value: Optional[str]) -> Optional[str]:
    cleaned_value = (value or "").strip()

    if not cleaned_value:
        return None

    return cleaned_value


def _clean_positive_int(value: int, field_name: str) -> int:
    try:
        clean_value = int(value)
    except (TypeError, ValueError) as exc:
        raise CreditFacilityServiceError(f"{field_name} geçerli bir sayı olmalıdır.") from exc

    if clean_value <= 0:
        raise CreditFacilityServiceError(f"{field_name} sıfırdan büyük olmalıdır.")

    return clean_value


def _clean_optional_day(value: Optional[int], field_name: str) -> Optional[int]:
    if value is None:
        return None

    try:
        clean_value = int(value)
    except (TypeError, ValueError) as exc:
        raise CreditFacilityServiceError(f"{field_name} geçerli bir gün değeri olmalıdır.") from exc

    if clean_value < 1 or clean_value > 31:
        raise CreditFacilityServiceError(f"{field_name} 1 ile 31 arasında olmalıdır.")

    return clean_value


def _clean_last_four_digits(value: Optional[str]) -> Optional[str]:
    cleaned_value = _clean_optional_text(value)

    if cleaned_value is None:
        return None

    if len(cleaned_value) != 4 or not cleaned_value.isdigit():
        raise CreditFacilityServiceError("Kart son 4 hane alanı 4 rakamdan oluşmalıdır.")

    return cleaned_value


def _clean_enum(value: Any, enum_class: type[EnumT], field_name: str) -> EnumT:
    if isinstance(value, enum_class):
        return value

    cleaned_value = str(value or "").strip()

    if not cleaned_value:
        raise CreditFacilityServiceError(f"{field_name} boş olamaz.")

    try:
        return enum_class(cleaned_value)
    except ValueError as exc:
        allowed_values = ", ".join(item.value for item in enum_class)  # type: ignore[attr-defined]
        raise CreditFacilityServiceError(
            f"{field_name} geçersiz. Geçerli değerler: {allowed_values}"
        ) from exc


def _clean_money(value: Any, field_name: str) -> Decimal:
    clean_value = money(value, field_name=field_name)

    if clean_value < Decimal("0.00"):
        raise CreditFacilityServiceError(f"{field_name} negatif olamaz.")

    return clean_value


def _clean_rate(value: Any, field_name: str) -> Decimal:
    clean_value = rate(value, field_name=field_name)

    if clean_value < Decimal("0.000000"):
        raise CreditFacilityServiceError(f"{field_name} negatif olamaz.")

    return clean_value


def _fixed_credit_card_currency_code() -> CurrencyCode:
    """Kredi kartı modülü ürün kararı gereği her zaman TL çalışır."""
    return CurrencyCode.TRY


def _is_try_currency(value: Any) -> bool:
    if isinstance(value, CurrencyCode):
        return value == CurrencyCode.TRY

    return str(value or "").strip().upper() == CurrencyCode.TRY.value


def _safe_month_day(year: int, month: int, day: int) -> date:
    last_day = calendar.monthrange(year, month)[1]
    safe_day = min(max(int(day), 1), last_day)
    return date(year, month, safe_day)


def _add_month(year: int, month: int) -> tuple[int, int]:
    if month == 12:
        return year + 1, 1

    return year, month + 1


def _subtract_month(year: int, month: int) -> tuple[int, int]:
    if month == 1:
        return year - 1, 12

    return year, month - 1


def _statement_cut_dates(today: date, statement_cut_day: int) -> tuple[date, date]:
    current_month_cut_date = _safe_month_day(
        today.year,
        today.month,
        statement_cut_day,
    )

    if today >= current_month_cut_date:
        next_year, next_month = _add_month(today.year, today.month)
        return current_month_cut_date, _safe_month_day(next_year, next_month, statement_cut_day)

    previous_year, previous_month = _subtract_month(today.year, today.month)
    return _safe_month_day(previous_year, previous_month, statement_cut_day), current_month_cut_date


def _get_bank_or_raise(session: Session, bank_id: int) -> Bank:
    clean_bank_id = _clean_positive_int(bank_id, "Banka ID")
    bank = session.get(Bank, clean_bank_id)

    if bank is None:
        raise CreditFacilityServiceError(f"Banka bulunamadı. Banka ID: {clean_bank_id}")

    return bank


def _get_bank_account_or_raise(session: Session, bank_account_id: int) -> BankAccount:
    clean_bank_account_id = _clean_positive_int(bank_account_id, "Banka hesabı ID")
    bank_account = session.get(BankAccount, clean_bank_account_id)

    if bank_account is None:
        raise CreditFacilityServiceError(
            f"Banka hesabı bulunamadı. Banka hesabı ID: {clean_bank_account_id}"
        )

    return bank_account


def _serialize_credit_card(credit_card: CreditCard) -> dict[str, Any]:
    return {
        "id": credit_card.id,
        "bank_id": credit_card.bank_id,
        "card_name": credit_card.card_name,
        "card_type": credit_card.card_type.value,
        "card_network": credit_card.card_network.value,
        "last_four_digits": credit_card.last_four_digits,
        "currency_code": credit_card.currency_code.value,
        "credit_limit": str(credit_card.credit_limit),
        "statement_cut_day": credit_card.statement_cut_day,
        "payment_due_day": credit_card.payment_due_day,
        "default_payment_bank_account_id": credit_card.default_payment_bank_account_id,
        "notes": credit_card.notes,
        "is_active": credit_card.is_active,
    }


def _serialize_credit_card_transaction(transaction: CreditCardTransaction) -> dict[str, Any]:
    return {
        "id": transaction.id,
        "credit_card_id": transaction.credit_card_id,
        "statement_id": transaction.statement_id,
        "transaction_date": transaction.transaction_date.isoformat()
        if transaction.transaction_date
        else None,
        "merchant_name": transaction.merchant_name,
        "description": transaction.description,
        "amount": str(transaction.amount),
        "currency_code": transaction.currency_code.value,
        "installment_count": transaction.installment_count,
        "installment_no": transaction.installment_no,
        "status": transaction.status.value,
        "reference_no": transaction.reference_no,
        "notes": transaction.notes,
    }


def _serialize_credit_card_payment(payment: CreditCardPayment) -> dict[str, Any]:
    return {
        "id": payment.id,
        "credit_card_id": payment.credit_card_id,
        "statement_id": payment.statement_id,
        "payment_bank_account_id": payment.payment_bank_account_id,
        "bank_transaction_id": payment.bank_transaction_id,
        "payment_date": payment.payment_date.isoformat() if payment.payment_date else None,
        "amount": str(payment.amount),
        "status": payment.status.value,
        "reference_no": payment.reference_no,
        "notes": payment.notes,
        "created_by_user_id": payment.created_by_user_id,
        "cancelled_by_user_id": payment.cancelled_by_user_id,
        "cancelled_at": payment.cancelled_at.isoformat() if payment.cancelled_at else None,
        "cancel_reason": payment.cancel_reason,
    }


def _serialize_credit_limit(credit_limit: BankAccountCreditLimit) -> dict[str, Any]:
    return {
        "id": credit_limit.id,
        "bank_account_id": credit_limit.bank_account_id,
        "limit_name": credit_limit.limit_name,
        "limit_type": credit_limit.limit_type.value,
        "currency_code": credit_limit.currency_code.value,
        "limit_amount": str(credit_limit.limit_amount),
        "usage_mode": credit_limit.usage_mode.value,
        "manual_used_amount": str(credit_limit.manual_used_amount),
        "interest_rate": str(credit_limit.interest_rate),
        "interest_period": credit_limit.interest_period.value,
        "interest_day": credit_limit.interest_day,
        "contract_start_date": (
            credit_limit.contract_start_date.isoformat()
            if credit_limit.contract_start_date
            else None
        ),
        "contract_end_date": (
            credit_limit.contract_end_date.isoformat()
            if credit_limit.contract_end_date
            else None
        ),
        "notes": credit_limit.notes,
        "is_active": credit_limit.is_active,
    }




def _serialize_credit_limit_transaction(
    transaction: BankAccountCreditLimitTransaction,
) -> dict[str, Any]:
    return {
        "id": transaction.id,
        "credit_limit_id": transaction.credit_limit_id,
        "transaction_type": transaction.transaction_type.value,
        "transaction_date": transaction.transaction_date.isoformat()
        if transaction.transaction_date
        else None,
        "effective_date": transaction.effective_date.isoformat()
        if transaction.effective_date
        else None,
        "amount": str(transaction.amount),
        "currency_code": transaction.currency_code.value,
        "bank_transaction_id": transaction.bank_transaction_id,
        "status": transaction.status.value,
        "reference_no": transaction.reference_no,
        "description": transaction.description,
        "notes": transaction.notes,
        "created_by_user_id": transaction.created_by_user_id,
        "cancelled_by_user_id": transaction.cancelled_by_user_id,
        "cancelled_at": transaction.cancelled_at.isoformat()
        if transaction.cancelled_at
        else None,
        "cancel_reason": transaction.cancel_reason,
    }

def get_credit_card_by_name(
    session: Session,
    *,
    bank_id: int,
    card_name: str,
) -> Optional[CreditCard]:
    clean_bank_id = _clean_positive_int(bank_id, "Banka ID")
    clean_card_name = _clean_required_text(card_name, "Kart adı")

    statement = select(CreditCard).where(
        CreditCard.bank_id == clean_bank_id,
        CreditCard.card_name == clean_card_name,
    )

    return session.execute(statement).scalar_one_or_none()


def get_credit_card_by_last_four_digits(
    session: Session,
    *,
    bank_id: int,
    last_four_digits: Optional[str],
) -> Optional[CreditCard]:
    clean_bank_id = _clean_positive_int(bank_id, "Banka ID")
    clean_last_four_digits = _clean_last_four_digits(last_four_digits)

    if clean_last_four_digits is None:
        return None

    statement = select(CreditCard).where(
        CreditCard.bank_id == clean_bank_id,
        CreditCard.last_four_digits == clean_last_four_digits,
    )

    return session.execute(statement).scalar_one_or_none()


def list_credit_cards(
    session: Session,
    *,
    include_inactive: bool = False,
) -> list[CreditCard]:
    statement = select(CreditCard).order_by(CreditCard.card_name.asc())

    if not include_inactive:
        statement = statement.where(CreditCard.is_active.is_(True))

    return list(session.execute(statement).scalars().all())


def create_credit_card(
    session: Session,
    *,
    bank_id: int,
    card_name: str,
    card_type: CreditCardType,
    card_network: CreditCardNetwork,
    last_four_digits: Optional[str],
    currency_code: CurrencyCode,
    credit_limit: Decimal,
    statement_cut_day: Optional[int],
    payment_due_day: Optional[int],
    default_payment_bank_account_id: Optional[int],
    notes: Optional[str],
    created_by_user_id: Optional[int],
) -> CreditCard:
    bank = _get_bank_or_raise(session, bank_id)

    clean_card_name = _clean_required_text(card_name, "Kart adı")
    clean_card_type = _clean_enum(card_type, CreditCardType, "Kart türü")
    clean_card_network = _clean_enum(card_network, CreditCardNetwork, "Kart ağı")
    clean_last_four_digits = _clean_last_four_digits(last_four_digits)
    clean_currency_code = _fixed_credit_card_currency_code()
    clean_credit_limit = _clean_money(credit_limit, "Kart limiti")
    clean_statement_cut_day = _clean_optional_day(statement_cut_day, "Hesap kesim günü")
    clean_payment_due_day = _clean_optional_day(payment_due_day, "Son ödeme günü")
    clean_notes = _clean_optional_text(notes)

    if get_credit_card_by_name(session, bank_id=bank.id, card_name=clean_card_name) is not None:
        raise CreditFacilityServiceError(
            f"Bu bankada aynı kart adı zaten kayıtlı: {clean_card_name}"
        )

    if clean_last_four_digits is not None:
        existing_card = get_credit_card_by_last_four_digits(
            session,
            bank_id=bank.id,
            last_four_digits=clean_last_four_digits,
        )

        if existing_card is not None:
            raise CreditFacilityServiceError(
                f"Bu bankada aynı son 4 hane ile kart zaten kayıtlı: {clean_last_four_digits}"
            )

    clean_default_payment_bank_account_id: Optional[int] = None

    if default_payment_bank_account_id is not None:
        payment_account = _get_bank_account_or_raise(session, default_payment_bank_account_id)

        if not _is_try_currency(payment_account.currency_code):
            raise CreditFacilityServiceError(
                "Kredi kartı varsayılan ödeme hesabı TL olmalıdır."
            )

        clean_default_payment_bank_account_id = payment_account.id

    credit_card = CreditCard(
        bank_id=bank.id,
        card_name=clean_card_name,
        card_type=clean_card_type,
        card_network=clean_card_network,
        last_four_digits=clean_last_four_digits,
        currency_code=clean_currency_code,
        credit_limit=clean_credit_limit,
        statement_cut_day=clean_statement_cut_day,
        payment_due_day=clean_payment_due_day,
        default_payment_bank_account_id=clean_default_payment_bank_account_id,
        notes=clean_notes,
        is_active=True,
    )

    session.add(credit_card)
    session.flush()

    write_audit_log(
        session,
        user_id=created_by_user_id,
        action="CREDIT_CARD_CREATED",
        entity_type="CreditCard",
        entity_id=credit_card.id,
        description=f"Kredi kartı oluşturuldu: {bank.name} / {credit_card.card_name}",
        old_values=None,
        new_values=_serialize_credit_card(credit_card),
    )

    return credit_card


def update_credit_card(
    session: Session,
    *,
    credit_card_id: int,
    card_name: str,
    card_type: CreditCardType,
    card_network: CreditCardNetwork,
    last_four_digits: Optional[str],
    currency_code: CurrencyCode,
    credit_limit: Decimal,
    statement_cut_day: Optional[int],
    payment_due_day: Optional[int],
    default_payment_bank_account_id: Optional[int],
    notes: Optional[str],
    updated_by_user_id: Optional[int],
) -> CreditCard:
    clean_credit_card_id = _clean_positive_int(credit_card_id, "Kredi kartı ID")
    credit_card = session.get(CreditCard, clean_credit_card_id)

    if credit_card is None:
        raise CreditFacilityServiceError(
            f"Kredi kartı bulunamadı. Kredi kartı ID: {clean_credit_card_id}"
        )

    old_values = _serialize_credit_card(credit_card)

    clean_card_name = _clean_required_text(card_name, "Kart adı")
    clean_card_type = _clean_enum(card_type, CreditCardType, "Kart türü")
    clean_card_network = _clean_enum(card_network, CreditCardNetwork, "Kart ağı")
    clean_last_four_digits = _clean_last_four_digits(last_four_digits)
    clean_currency_code = _fixed_credit_card_currency_code()
    clean_credit_limit = _clean_money(credit_limit, "Kart limiti")
    clean_statement_cut_day = _clean_optional_day(statement_cut_day, "Hesap kesim günü")
    clean_payment_due_day = _clean_optional_day(payment_due_day, "Son ödeme günü")
    clean_notes = _clean_optional_text(notes)

    existing_by_name = get_credit_card_by_name(
        session,
        bank_id=credit_card.bank_id,
        card_name=clean_card_name,
    )

    if existing_by_name is not None and existing_by_name.id != credit_card.id:
        raise CreditFacilityServiceError(
            f"Bu bankada aynı kart adı zaten kayıtlı: {clean_card_name}"
        )

    if clean_last_four_digits is not None:
        existing_by_digits = get_credit_card_by_last_four_digits(
            session,
            bank_id=credit_card.bank_id,
            last_four_digits=clean_last_four_digits,
        )

        if existing_by_digits is not None and existing_by_digits.id != credit_card.id:
            raise CreditFacilityServiceError(
                f"Bu bankada aynı son 4 hane ile kart zaten kayıtlı: {clean_last_four_digits}"
            )

    clean_default_payment_bank_account_id: Optional[int] = None

    if default_payment_bank_account_id is not None:
        payment_account = _get_bank_account_or_raise(session, default_payment_bank_account_id)

        if not _is_try_currency(payment_account.currency_code):
            raise CreditFacilityServiceError(
                "Kredi kartı varsayılan ödeme hesabı TL olmalıdır."
            )

        clean_default_payment_bank_account_id = payment_account.id

    credit_card.card_name = clean_card_name
    credit_card.card_type = clean_card_type
    credit_card.card_network = clean_card_network
    credit_card.last_four_digits = clean_last_four_digits
    credit_card.currency_code = clean_currency_code
    credit_card.credit_limit = clean_credit_limit
    credit_card.statement_cut_day = clean_statement_cut_day
    credit_card.payment_due_day = clean_payment_due_day
    credit_card.default_payment_bank_account_id = clean_default_payment_bank_account_id
    credit_card.notes = clean_notes

    session.flush()

    write_audit_log(
        session,
        user_id=updated_by_user_id,
        action="CREDIT_CARD_UPDATED",
        entity_type="CreditCard",
        entity_id=credit_card.id,
        description=f"Kredi kartı güncellendi: {credit_card.card_name}",
        old_values=old_values,
        new_values=_serialize_credit_card(credit_card),
    )

    return credit_card


def deactivate_credit_card(
    session: Session,
    *,
    credit_card_id: int,
    updated_by_user_id: Optional[int],
) -> CreditCard:
    clean_credit_card_id = _clean_positive_int(credit_card_id, "Kredi kartı ID")
    credit_card = session.get(CreditCard, clean_credit_card_id)

    if credit_card is None:
        raise CreditFacilityServiceError(
            f"Kredi kartı bulunamadı. Kredi kartı ID: {clean_credit_card_id}"
        )

    old_values = _serialize_credit_card(credit_card)
    credit_card.is_active = False

    session.flush()

    write_audit_log(
        session,
        user_id=updated_by_user_id,
        action="CREDIT_CARD_DEACTIVATED",
        entity_type="CreditCard",
        entity_id=credit_card.id,
        description=f"Kredi kartı pasifleştirildi: {credit_card.card_name}",
        old_values=old_values,
        new_values=_serialize_credit_card(credit_card),
    )

    return credit_card


def activate_credit_card(
    session: Session,
    *,
    credit_card_id: int,
    updated_by_user_id: Optional[int],
) -> CreditCard:
    clean_credit_card_id = _clean_positive_int(credit_card_id, "Kredi kartı ID")
    credit_card = session.get(CreditCard, clean_credit_card_id)

    if credit_card is None:
        raise CreditFacilityServiceError(
            f"Kredi kartı bulunamadı. Kredi kartı ID: {clean_credit_card_id}"
        )

    old_values = _serialize_credit_card(credit_card)
    credit_card.is_active = True

    session.flush()

    write_audit_log(
        session,
        user_id=updated_by_user_id,
        action="CREDIT_CARD_ACTIVATED",
        entity_type="CreditCard",
        entity_id=credit_card.id,
        description=f"Kredi kartı aktifleştirildi: {credit_card.card_name}",
        old_values=old_values,
        new_values=_serialize_credit_card(credit_card),
    )

    return credit_card


def get_credit_card_or_raise(session: Session, credit_card_id: int) -> CreditCard:
    clean_credit_card_id = _clean_positive_int(credit_card_id, "Kredi kartı ID")
    credit_card = session.get(CreditCard, clean_credit_card_id)

    if credit_card is None:
        raise CreditFacilityServiceError(
            f"Kredi kartı bulunamadı. Kredi kartı ID: {clean_credit_card_id}"
        )

    return credit_card


def list_credit_card_transactions(
    session: Session,
    *,
    credit_card_id: int | None = None,
    include_cancelled: bool = True,
) -> list[CreditCardTransaction]:
    statement = (
        select(CreditCardTransaction)
        .options(joinedload(CreditCardTransaction.credit_card))
        .order_by(
            CreditCardTransaction.transaction_date.desc(),
            CreditCardTransaction.id.desc(),
        )
    )

    if credit_card_id is not None:
        clean_credit_card_id = _clean_positive_int(credit_card_id, "Kredi kartı ID")
        statement = statement.where(CreditCardTransaction.credit_card_id == clean_credit_card_id)

    if not include_cancelled:
        statement = statement.where(
            CreditCardTransaction.status != CreditCardTransactionStatus.CANCELLED
        )

    return list(session.execute(statement).scalars().all())


def create_credit_card_transaction(
    session: Session,
    *,
    credit_card_id: int,
    transaction_date: date,
    merchant_name: str,
    description: Optional[str],
    amount: Decimal,
    installment_count: int,
    reference_no: Optional[str],
    notes: Optional[str],
    created_by_user_id: Optional[int],
) -> CreditCardTransaction:
    credit_card = get_credit_card_or_raise(session, credit_card_id)

    if not credit_card.is_active:
        raise CreditFacilityServiceError(
            "Pasif kredi kartına harcama kaydı girilemez. Önce kartı aktifleştir."
        )

    clean_merchant_name = _clean_required_text(merchant_name, "İşyeri / açıklama")
    clean_description = _clean_optional_text(description)
    clean_amount = _clean_money(amount, "Harcama tutarı")
    clean_installment_count = _clean_positive_int(installment_count, "Taksit sayısı")
    clean_reference_no = _clean_optional_text(reference_no)
    clean_notes = _clean_optional_text(notes)

    if clean_amount <= Decimal("0.00"):
        raise CreditFacilityServiceError("Harcama tutarı sıfırdan büyük olmalıdır.")

    if clean_installment_count > 120:
        raise CreditFacilityServiceError("Taksit sayısı 120 değerinden büyük olamaz.")

    transaction = CreditCardTransaction(
        credit_card_id=credit_card.id,
        statement_id=None,
        transaction_date=transaction_date,
        merchant_name=clean_merchant_name,
        description=clean_description,
        amount=clean_amount,
        currency_code=_fixed_credit_card_currency_code(),
        installment_count=clean_installment_count,
        installment_no=1,
        status=CreditCardTransactionStatus.PENDING,
        reference_no=clean_reference_no,
        notes=clean_notes,
    )

    session.add(transaction)
    session.flush()

    write_audit_log(
        session,
        user_id=created_by_user_id,
        action="CREDIT_CARD_TRANSACTION_CREATED",
        entity_type="CreditCardTransaction",
        entity_id=transaction.id,
        description=(
            f"Kredi kartı harcaması oluşturuldu: "
            f"{credit_card.card_name} / {transaction.merchant_name}"
        ),
        old_values=None,
        new_values=_serialize_credit_card_transaction(transaction),
    )

    return transaction


def cancel_credit_card_transaction(
    session: Session,
    *,
    transaction_id: int,
    updated_by_user_id: Optional[int],
) -> CreditCardTransaction:
    clean_transaction_id = _clean_positive_int(transaction_id, "Harcama ID")
    transaction = session.get(CreditCardTransaction, clean_transaction_id)

    if transaction is None:
        raise CreditFacilityServiceError(
            f"Kredi kartı harcaması bulunamadı. Harcama ID: {clean_transaction_id}"
        )

    if transaction.status == CreditCardTransactionStatus.IN_STATEMENT:
        raise CreditFacilityServiceError(
            "Ekstreye bağlanmış harcama bu ekrandan iptal edilemez."
        )

    if transaction.status == CreditCardTransactionStatus.CANCELLED:
        return transaction

    active_transactions = list_credit_card_transactions(
        session,
        credit_card_id=int(transaction.credit_card_id),
        include_cancelled=False,
    )
    active_purchase_total_after_cancel = Decimal("0.00")

    for active_transaction in active_transactions:
        if int(active_transaction.id) == int(transaction.id):
            continue

        if active_transaction.status not in ACTIVE_TRANSACTION_STATUSES:
            continue

        active_purchase_total_after_cancel += money(
            active_transaction.amount or Decimal("0.00"),
            field_name="Aktif harcama tutarı",
        )

    payment_statement = select(CreditCardPayment).where(
        CreditCardPayment.credit_card_id == int(transaction.credit_card_id),
    )
    active_payments = session.execute(payment_statement).scalars().all()
    active_payment_total = Decimal("0.00")

    for payment in active_payments:
        if payment.status not in ACTIVE_PAYMENT_STATUSES:
            continue

        active_payment_total += money(
            payment.amount or Decimal("0.00"),
            field_name="Aktif ödeme tutarı",
        )

    if active_payment_total > Decimal("0.00") and active_purchase_total_after_cancel < active_payment_total:
        raise CreditFacilityServiceError(
            "Bu harcama iptal edilemez. Kartta aktif ödeme kaydı bulunduğu için "
            "bu iptal kartı fazla ödenmiş duruma düşürür. Önce ilgili kredi kartı "
            "ödeme kaydını iptal etmelisin. "
            f"İptal sonrası aktif harcama toplamı: {active_purchase_total_after_cancel} TL, "
            f"aktif ödeme toplamı: {active_payment_total} TL."
        )

    old_values = _serialize_credit_card_transaction(transaction)
    transaction.status = CreditCardTransactionStatus.CANCELLED

    session.flush()

    write_audit_log(
        session,
        user_id=updated_by_user_id,
        action="CREDIT_CARD_TRANSACTION_CANCELLED",
        entity_type="CreditCardTransaction",
        entity_id=transaction.id,
        description=f"Kredi kartı harcaması iptal edildi: {transaction.merchant_name}",
        old_values=old_values,
        new_values=_serialize_credit_card_transaction(transaction),
    )

    return transaction


def list_credit_card_payments(
    session: Session,
    *,
    credit_card_id: int | None = None,
    include_cancelled: bool = True,
) -> list[CreditCardPayment]:
    statement = (
        select(CreditCardPayment)
        .options(
            joinedload(CreditCardPayment.credit_card),
            joinedload(CreditCardPayment.payment_bank_account),
            joinedload(CreditCardPayment.bank_transaction),
        )
        .order_by(
            CreditCardPayment.payment_date.desc(),
            CreditCardPayment.id.desc(),
        )
    )

    if credit_card_id is not None:
        clean_credit_card_id = _clean_positive_int(credit_card_id, "Kredi kartı ID")
        statement = statement.where(CreditCardPayment.credit_card_id == clean_credit_card_id)

    if not include_cancelled:
        statement = statement.where(CreditCardPayment.status != CreditCardPaymentStatus.CANCELLED)

    return list(session.execute(statement).scalars().all())


def get_credit_card_debt_summary(
    session: Session,
    *,
    credit_card_id: int,
) -> dict[str, Any]:
    credit_card = get_credit_card_or_raise(session, credit_card_id)

    transactions = list_credit_card_transactions(
        session,
        credit_card_id=credit_card.id,
        include_cancelled=True,
    )
    payments = list_credit_card_payments(
        session,
        credit_card_id=credit_card.id,
        include_cancelled=True,
    )

    purchase_total = Decimal("0.00")
    cancelled_purchase_total = Decimal("0.00")

    for transaction in transactions:
        amount = money(transaction.amount or Decimal("0.00"), field_name="Harcama tutarı")

        if transaction.status in ACTIVE_TRANSACTION_STATUSES:
            purchase_total += amount
            continue

        if transaction.status == CreditCardTransactionStatus.CANCELLED:
            cancelled_purchase_total += amount

    payment_total = Decimal("0.00")
    cancelled_payment_total = Decimal("0.00")

    for payment in payments:
        amount = money(payment.amount or Decimal("0.00"), field_name="Ödeme tutarı")

        if payment.status in ACTIVE_PAYMENT_STATUSES:
            payment_total += amount
            continue

        if payment.status == CreditCardPaymentStatus.CANCELLED:
            cancelled_payment_total += amount

    credit_limit = money(credit_card.credit_limit or Decimal("0.00"), field_name="Kart limiti")
    remaining_debt = purchase_total - payment_total

    if remaining_debt < Decimal("0.00"):
        remaining_debt = Decimal("0.00")

    available_limit = credit_limit - remaining_debt

    if available_limit < Decimal("0.00"):
        available_limit = Decimal("0.00")

    return {
        "credit_card_id": credit_card.id,
        "currency_code": CurrencyCode.TRY.value,
        "credit_limit": credit_limit,
        "purchase_total": money(purchase_total, field_name="Toplam harcama"),
        "payment_total": money(payment_total, field_name="Toplam ödeme"),
        "remaining_debt": money(remaining_debt, field_name="Kalan borç"),
        "available_limit": money(available_limit, field_name="Kullanılabilir limit"),
        "cancelled_purchase_total": money(
            cancelled_purchase_total,
            field_name="İptal edilen harcama",
        ),
        "cancelled_payment_total": money(
            cancelled_payment_total,
            field_name="İptal edilen ödeme",
        ),
    }


def get_credit_card_recommendation_status(
    *,
    credit_card: CreditCard,
    available_limit: Decimal,
    minimum_amount: Decimal | None = None,
    today: date | None = None,
) -> dict[str, Any]:
    effective_today = today or date.today()
    clean_available_limit = _clean_money(available_limit, "Kullanılabilir limit")
    clean_minimum_amount = _clean_money(
        minimum_amount if minimum_amount is not None else Decimal("0.00"),
        "Tavsiye tutarı",
    )

    if not credit_card.is_active:
        return {
            "status": CreditCardRecommendationStatus.PASSIVE,
            "label": "Pasif",
            "message": "Pasif kart kullanıma önerilmez.",
            "days_until_cut": None,
            "days_since_cut": None,
            "next_cut_date": None,
            "last_cut_date": None,
        }

    if clean_minimum_amount > Decimal("0.00") and clean_available_limit < clean_minimum_amount:
        return {
            "status": CreditCardRecommendationStatus.LIMIT_INSUFFICIENT,
            "label": "Limit Yetersiz",
            "message": "Bu kart için kullanılabilir limit önerilen tutarı karşılamıyor.",
            "days_until_cut": None,
            "days_since_cut": None,
            "next_cut_date": None,
            "last_cut_date": None,
        }

    if credit_card.statement_cut_day is None:
        return {
            "status": CreditCardRecommendationStatus.DATE_MISSING,
            "label": "Tarih Yok",
            "message": "Hesap kesim günü tanımlanmadığı için tavsiye üretilemedi.",
            "days_until_cut": None,
            "days_since_cut": None,
            "next_cut_date": None,
            "last_cut_date": None,
        }

    last_cut_date, next_cut_date = _statement_cut_dates(
        effective_today,
        int(credit_card.statement_cut_day),
    )
    days_until_cut = (next_cut_date - effective_today).days
    days_since_cut = (effective_today - last_cut_date).days

    if effective_today == last_cut_date:
        return {
            "status": CreditCardRecommendationStatus.CUT_OFF_TODAY,
            "label": "Bugün Kesim",
            "message": "Hesap kesim günü bugün. İşlem tarihi bankaya göre aynı döneme düşebilir.",
            "days_until_cut": days_until_cut,
            "days_since_cut": days_since_cut,
            "next_cut_date": next_cut_date,
            "last_cut_date": last_cut_date,
        }

    if 1 <= days_until_cut <= 3:
        return {
            "status": CreditCardRecommendationStatus.NEAR_CUT_OFF,
            "label": "Kesime Yakın",
            "message": "Hesap kesimine az kaldı. Mümkünse kesimi yeni geçmiş kart tercih edilebilir.",
            "days_until_cut": days_until_cut,
            "days_since_cut": days_since_cut,
            "next_cut_date": next_cut_date,
            "last_cut_date": last_cut_date,
        }

    if 1 <= days_since_cut <= 7:
        return {
            "status": CreditCardRecommendationStatus.RECOMMENDED,
            "label": "Tavsiye Edilen",
            "message": "Hesap kesimi yakın zamanda geçmiş. Nakit akışı açısından daha avantajlı olabilir.",
            "days_until_cut": days_until_cut,
            "days_since_cut": days_since_cut,
            "next_cut_date": next_cut_date,
            "last_cut_date": last_cut_date,
        }

    return {
        "status": CreditCardRecommendationStatus.SUITABLE,
        "label": "Uygun",
        "message": "Kart kullanım için uygun görünüyor.",
        "days_until_cut": days_until_cut,
        "days_since_cut": days_since_cut,
        "next_cut_date": next_cut_date,
        "last_cut_date": last_cut_date,
    }


def get_credit_card_recommendation_summary(
    session: Session,
    *,
    credit_card_id: int,
    minimum_amount: Decimal | None = None,
    today: date | None = None,
) -> dict[str, Any]:
    credit_card = get_credit_card_or_raise(session, credit_card_id)
    debt_summary = get_credit_card_debt_summary(session, credit_card_id=credit_card.id)

    return get_credit_card_recommendation_status(
        credit_card=credit_card,
        available_limit=debt_summary["available_limit"],
        minimum_amount=minimum_amount,
        today=today,
    )


def create_credit_card_payment(
    session: Session,
    *,
    credit_card_id: int,
    payment_bank_account_id: int,
    payment_date: date,
    amount: Decimal,
    reference_no: Optional[str],
    notes: Optional[str],
    created_by_user_id: Optional[int],
) -> CreditCardPayment:
    credit_card = get_credit_card_or_raise(session, credit_card_id)
    payment_account = _get_bank_account_or_raise(session, payment_bank_account_id)

    if not _is_try_currency(credit_card.currency_code):
        raise CreditFacilityServiceError("Kredi kartı para birimi TL olmalıdır.")

    if not payment_account.is_active:
        raise CreditFacilityServiceError("Pasif banka hesabından kredi kartı ödemesi yapılamaz.")

    if not _is_try_currency(payment_account.currency_code):
        raise CreditFacilityServiceError("Kredi kartı ödemesi sadece TL banka hesabından yapılabilir.")

    clean_amount = _clean_money(amount, "Ödeme tutarı")
    clean_reference_no = _clean_optional_text(reference_no)
    clean_notes = _clean_optional_text(notes)

    if clean_amount <= Decimal("0.00"):
        raise CreditFacilityServiceError("Ödeme tutarı sıfırdan büyük olmalıdır.")

    debt_summary = get_credit_card_debt_summary(session, credit_card_id=credit_card.id)
    remaining_debt = money(debt_summary["remaining_debt"], field_name="Kalan borç")

    if remaining_debt <= Decimal("0.00"):
        raise CreditFacilityServiceError("Bu kredi kartı için ödenecek borç bulunmuyor.")

    if clean_amount > remaining_debt:
        raise CreditFacilityServiceError(
            "Ödeme tutarı mevcut kredi kartı borcundan büyük olamaz. "
            f"Mevcut borç: {remaining_debt}"
        )

    payment = CreditCardPayment(
        credit_card_id=credit_card.id,
        statement_id=None,
        payment_bank_account_id=payment_account.id,
        bank_transaction_id=None,
        payment_date=payment_date,
        amount=clean_amount,
        status=CreditCardPaymentStatus.RECORDED,
        reference_no=clean_reference_no,
        notes=clean_notes,
        created_by_user_id=created_by_user_id,
    )

    session.add(payment)
    session.flush()

    try:
        bank_transaction = create_bank_transaction(
            session,
            bank_account_id=payment_account.id,
            transaction_date=payment_date,
            value_date=payment_date,
            direction=TransactionDirection.OUT,
            status=BankTransactionStatus.REALIZED,
            amount=clean_amount,
            currency_code=CurrencyCode.TRY,
            source_type=FinancialSourceType.CREDIT_CARD_PAYMENT,
            source_id=payment.id,
            reference_no=clean_reference_no,
            description=f"Kredi kartı ödemesi: {credit_card.card_name}",
            created_by_user_id=created_by_user_id,
        )
    except BankTransactionServiceError as exc:
        raise CreditFacilityServiceError(str(exc)) from exc

    payment.bank_transaction_id = bank_transaction.id
    session.flush()

    write_audit_log(
        session,
        user_id=created_by_user_id,
        action="CREDIT_CARD_PAYMENT_CREATED",
        entity_type="CreditCardPayment",
        entity_id=payment.id,
        description=f"Kredi kartı ödemesi oluşturuldu: {credit_card.card_name} / {payment.amount} TL",
        old_values=None,
        new_values=_serialize_credit_card_payment(payment),
    )

    return payment


def cancel_credit_card_payment(
    session: Session,
    *,
    payment_id: int,
    cancel_reason: str,
    cancelled_by_user_id: Optional[int],
) -> CreditCardPayment:
    clean_payment_id = _clean_positive_int(payment_id, "Ödeme ID")
    clean_cancel_reason = _clean_required_text(cancel_reason, "İptal nedeni")
    payment = session.get(CreditCardPayment, clean_payment_id)

    if payment is None:
        raise CreditFacilityServiceError(f"Kredi kartı ödemesi bulunamadı. Ödeme ID: {clean_payment_id}")

    if payment.status == CreditCardPaymentStatus.CANCELLED:
        return payment

    old_values = _serialize_credit_card_payment(payment)

    if payment.bank_transaction_id is not None:
        try:
            cancel_bank_transaction(
                session,
                bank_transaction_id=int(payment.bank_transaction_id),
                cancel_reason=f"Kredi kartı ödeme iptali: {clean_cancel_reason}",
                cancelled_by_user_id=cancelled_by_user_id,
            )
        except BankTransactionServiceError as exc:
            raise CreditFacilityServiceError(str(exc)) from exc

    payment.status = CreditCardPaymentStatus.CANCELLED
    payment.cancelled_by_user_id = cancelled_by_user_id
    payment.cancelled_at = datetime.now()
    payment.cancel_reason = clean_cancel_reason

    session.flush()

    write_audit_log(
        session,
        user_id=cancelled_by_user_id,
        action="CREDIT_CARD_PAYMENT_CANCELLED",
        entity_type="CreditCardPayment",
        entity_id=payment.id,
        description=f"Kredi kartı ödemesi iptal edildi. Ödeme ID: {payment.id}",
        old_values=old_values,
        new_values=_serialize_credit_card_payment(payment),
    )

    return payment


def get_credit_limit_by_name(
    session: Session,
    *,
    bank_account_id: int,
    limit_name: str,
) -> Optional[BankAccountCreditLimit]:
    clean_bank_account_id = _clean_positive_int(bank_account_id, "Banka hesabı ID")
    clean_limit_name = _clean_required_text(limit_name, "Limit adı")

    statement = select(BankAccountCreditLimit).where(
        BankAccountCreditLimit.bank_account_id == clean_bank_account_id,
        BankAccountCreditLimit.limit_name == clean_limit_name,
    )

    return session.execute(statement).scalar_one_or_none()


def list_credit_limits(
    session: Session,
    *,
    include_inactive: bool = False,
) -> list[BankAccountCreditLimit]:
    statement = select(BankAccountCreditLimit).order_by(BankAccountCreditLimit.limit_name.asc())

    if not include_inactive:
        statement = statement.where(BankAccountCreditLimit.is_active.is_(True))

    return list(session.execute(statement).scalars().all())


def create_credit_limit(
    session: Session,
    *,
    bank_account_id: int,
    limit_name: str,
    limit_type: CreditLimitType,
    limit_amount: Decimal,
    usage_mode: CreditLimitUsageMode,
    manual_used_amount: Decimal,
    interest_rate: Decimal,
    interest_period: InterestPeriod,
    interest_day: Optional[int],
    contract_start_date: Optional[date],
    contract_end_date: Optional[date],
    notes: Optional[str],
    created_by_user_id: Optional[int],
) -> BankAccountCreditLimit:
    bank_account = _get_bank_account_or_raise(session, bank_account_id)

    clean_limit_name = _clean_required_text(limit_name, "Limit adı")
    clean_limit_type = _clean_enum(limit_type, CreditLimitType, "Limit tipi")
    clean_limit_amount = _clean_money(limit_amount, "Limit tutarı")
    clean_usage_mode = _clean_enum(usage_mode, CreditLimitUsageMode, "Kullanım takip şekli")
    clean_manual_used_amount = _clean_money(manual_used_amount, "Manuel kullanılan tutar")
    clean_interest_rate = _clean_rate(interest_rate, "Faiz oranı")
    clean_interest_period = _clean_enum(interest_period, InterestPeriod, "Faiz periyodu")
    clean_interest_day = _clean_optional_day(interest_day, "Faiz / ödeme günü")
    clean_notes = _clean_optional_text(notes)

    if contract_start_date and contract_end_date and contract_end_date < contract_start_date:
        raise CreditFacilityServiceError("Sözleşme bitiş tarihi başlangıç tarihinden eski olamaz.")

    if clean_manual_used_amount > clean_limit_amount:
        raise CreditFacilityServiceError("Manuel kullanılan tutar limit tutarından büyük olamaz.")

    existing_limit = get_credit_limit_by_name(
        session,
        bank_account_id=bank_account.id,
        limit_name=clean_limit_name,
    )

    if existing_limit is not None:
        raise CreditFacilityServiceError(
            f"Bu banka hesabında aynı limit adı zaten kayıtlı: {clean_limit_name}"
        )

    credit_limit = BankAccountCreditLimit(
        bank_account_id=bank_account.id,
        limit_name=clean_limit_name,
        limit_type=clean_limit_type,
        currency_code=bank_account.currency_code,
        limit_amount=clean_limit_amount,
        usage_mode=clean_usage_mode,
        manual_used_amount=clean_manual_used_amount,
        interest_rate=clean_interest_rate,
        interest_period=clean_interest_period,
        interest_day=clean_interest_day,
        contract_start_date=contract_start_date,
        contract_end_date=contract_end_date,
        notes=clean_notes,
        is_active=True,
    )

    session.add(credit_limit)
    session.flush()

    write_audit_log(
        session,
        user_id=created_by_user_id,
        action="CREDIT_LIMIT_CREATED",
        entity_type="BankAccountCreditLimit",
        entity_id=credit_limit.id,
        description=f"Kredili / limitli hesap tanımı oluşturuldu: {credit_limit.limit_name}",
        old_values=None,
        new_values=_serialize_credit_limit(credit_limit),
    )

    return credit_limit


def update_credit_limit(
    session: Session,
    *,
    credit_limit_id: int,
    limit_name: str,
    limit_type: CreditLimitType,
    limit_amount: Decimal,
    usage_mode: CreditLimitUsageMode,
    manual_used_amount: Decimal,
    interest_rate: Decimal,
    interest_period: InterestPeriod,
    interest_day: Optional[int],
    contract_start_date: Optional[date],
    contract_end_date: Optional[date],
    notes: Optional[str],
    updated_by_user_id: Optional[int],
) -> BankAccountCreditLimit:
    clean_credit_limit_id = _clean_positive_int(credit_limit_id, "Kredili hesap limiti ID")
    credit_limit = session.get(BankAccountCreditLimit, clean_credit_limit_id)

    if credit_limit is None:
        raise CreditFacilityServiceError(
            f"Kredili / limitli hesap tanımı bulunamadı. ID: {clean_credit_limit_id}"
        )

    old_values = _serialize_credit_limit(credit_limit)

    clean_limit_name = _clean_required_text(limit_name, "Limit adı")
    clean_limit_type = _clean_enum(limit_type, CreditLimitType, "Limit tipi")
    clean_limit_amount = _clean_money(limit_amount, "Limit tutarı")
    clean_usage_mode = _clean_enum(usage_mode, CreditLimitUsageMode, "Kullanım takip şekli")
    clean_manual_used_amount = _clean_money(manual_used_amount, "Manuel kullanılan tutar")
    clean_interest_rate = _clean_rate(interest_rate, "Faiz oranı")
    clean_interest_period = _clean_enum(interest_period, InterestPeriod, "Faiz periyodu")
    clean_interest_day = _clean_optional_day(interest_day, "Faiz / ödeme günü")
    clean_notes = _clean_optional_text(notes)

    if contract_start_date and contract_end_date and contract_end_date < contract_start_date:
        raise CreditFacilityServiceError("Sözleşme bitiş tarihi başlangıç tarihinden eski olamaz.")

    if clean_manual_used_amount > clean_limit_amount:
        raise CreditFacilityServiceError("Manuel kullanılan tutar limit tutarından büyük olamaz.")

    existing_limit = get_credit_limit_by_name(
        session,
        bank_account_id=credit_limit.bank_account_id,
        limit_name=clean_limit_name,
    )

    if existing_limit is not None and existing_limit.id != credit_limit.id:
        raise CreditFacilityServiceError(
            f"Bu banka hesabında aynı limit adı zaten kayıtlı: {clean_limit_name}"
        )

    credit_limit.limit_name = clean_limit_name
    credit_limit.limit_type = clean_limit_type
    credit_limit.limit_amount = clean_limit_amount
    credit_limit.usage_mode = clean_usage_mode
    credit_limit.manual_used_amount = clean_manual_used_amount
    credit_limit.interest_rate = clean_interest_rate
    credit_limit.interest_period = clean_interest_period
    credit_limit.interest_day = clean_interest_day
    credit_limit.contract_start_date = contract_start_date
    credit_limit.contract_end_date = contract_end_date
    credit_limit.notes = clean_notes

    session.flush()

    write_audit_log(
        session,
        user_id=updated_by_user_id,
        action="CREDIT_LIMIT_UPDATED",
        entity_type="BankAccountCreditLimit",
        entity_id=credit_limit.id,
        description=f"Kredili / limitli hesap tanımı güncellendi: {credit_limit.limit_name}",
        old_values=old_values,
        new_values=_serialize_credit_limit(credit_limit),
    )

    return credit_limit


def deactivate_credit_limit(
    session: Session,
    *,
    credit_limit_id: int,
    updated_by_user_id: Optional[int],
) -> BankAccountCreditLimit:
    clean_credit_limit_id = _clean_positive_int(credit_limit_id, "Kredili hesap limiti ID")
    credit_limit = session.get(BankAccountCreditLimit, clean_credit_limit_id)

    if credit_limit is None:
        raise CreditFacilityServiceError(
            f"Kredili / limitli hesap tanımı bulunamadı. ID: {clean_credit_limit_id}"
        )

    old_values = _serialize_credit_limit(credit_limit)
    credit_limit.is_active = False

    session.flush()

    write_audit_log(
        session,
        user_id=updated_by_user_id,
        action="CREDIT_LIMIT_DEACTIVATED",
        entity_type="BankAccountCreditLimit",
        entity_id=credit_limit.id,
        description=f"Kredili / limitli hesap tanımı pasifleştirildi: {credit_limit.limit_name}",
        old_values=old_values,
        new_values=_serialize_credit_limit(credit_limit),
    )

    return credit_limit


def get_credit_limit_or_raise(
    session: Session,
    credit_limit_id: int,
) -> BankAccountCreditLimit:
    clean_credit_limit_id = _clean_positive_int(credit_limit_id, "Kredili hesap limiti ID")
    credit_limit = session.get(BankAccountCreditLimit, clean_credit_limit_id)

    if credit_limit is None:
        raise CreditFacilityServiceError(
            f"Kredili / limitli hesap tanımı bulunamadı. ID: {clean_credit_limit_id}"
        )

    return credit_limit


def activate_credit_limit(
    session: Session,
    *,
    credit_limit_id: int,
    updated_by_user_id: Optional[int],
) -> BankAccountCreditLimit:
    credit_limit = get_credit_limit_or_raise(session, credit_limit_id)

    old_values = _serialize_credit_limit(credit_limit)
    credit_limit.is_active = True

    session.flush()

    write_audit_log(
        session,
        user_id=updated_by_user_id,
        action="CREDIT_LIMIT_ACTIVATED",
        entity_type="BankAccountCreditLimit",
        entity_id=credit_limit.id,
        description=f"Kredili / limitli hesap tanımı aktifleştirildi: {credit_limit.limit_name}",
        old_values=old_values,
        new_values=_serialize_credit_limit(credit_limit),
    )

    return credit_limit


def _validate_credit_limit_is_active(credit_limit: BankAccountCreditLimit) -> None:
    if not credit_limit.is_active:
        raise CreditFacilityServiceError("Pasif kredili / limitli hesap üzerinde işlem yapılamaz.")


def _credit_limit_currency_code(credit_limit: BankAccountCreditLimit) -> CurrencyCode:
    if isinstance(credit_limit.currency_code, CurrencyCode):
        return credit_limit.currency_code

    try:
        return CurrencyCode(str(credit_limit.currency_code).strip().upper())
    except ValueError as exc:
        raise CreditFacilityServiceError("Limit para birimi geçersiz.") from exc


def _credit_limit_effective_date(
    *,
    transaction_type: CreditLimitTransactionType,
    transaction_date: date,
) -> date:
    if transaction_type == CreditLimitTransactionType.PAYMENT:
        return transaction_date + timedelta(days=1)

    return transaction_date


def _clean_credit_limit_transaction_type(
    value: CreditLimitTransactionType | str,
) -> CreditLimitTransactionType:
    return _clean_enum(value, CreditLimitTransactionType, "Limit hareket tipi")


def _clean_credit_limit_transaction_status(
    value: CreditLimitTransactionStatus | str,
) -> CreditLimitTransactionStatus:
    return _clean_enum(value, CreditLimitTransactionStatus, "Limit hareket durumu")


def _credit_limit_debt_increase_amount(
    transaction: BankAccountCreditLimitTransaction,
) -> Decimal:
    if transaction.status not in ACTIVE_CREDIT_LIMIT_TRANSACTION_STATUSES:
        return Decimal("0.00")

    transaction_type = transaction.transaction_type
    amount = money(transaction.amount or Decimal("0.00"), field_name="Limit hareket tutarı")

    if transaction_type in CREDIT_LIMIT_DEBT_INCREASE_TYPES:
        return amount

    return Decimal("0.00")


def _credit_limit_payment_amount(
    transaction: BankAccountCreditLimitTransaction,
) -> Decimal:
    if transaction.status not in ACTIVE_CREDIT_LIMIT_TRANSACTION_STATUSES:
        return Decimal("0.00")

    if transaction.transaction_type != CreditLimitTransactionType.PAYMENT:
        return Decimal("0.00")

    return money(transaction.amount or Decimal("0.00"), field_name="Limit ödeme tutarı")


def _credit_limit_interest_basis_effect(
    transaction: BankAccountCreditLimitTransaction,
) -> Decimal:
    if transaction.status not in ACTIVE_CREDIT_LIMIT_TRANSACTION_STATUSES:
        return Decimal("0.00")

    amount = money(transaction.amount or Decimal("0.00"), field_name="Limit hareket tutarı")

    if transaction.transaction_type in CREDIT_LIMIT_PRINCIPAL_INCREASE_TYPES:
        return amount

    if transaction.transaction_type == CreditLimitTransactionType.PAYMENT:
        return -amount

    return Decimal("0.00")


def _monthly_interest_rate_fraction(credit_limit: BankAccountCreditLimit) -> Decimal:
    clean_rate = rate(credit_limit.interest_rate or Decimal("0.000000"), field_name="Faiz oranı")
    return clean_rate / Decimal("100")


def _daily_credit_limit_interest(
    *,
    balance: Decimal,
    credit_limit: BankAccountCreditLimit,
    current_date: date,
) -> Decimal:
    clean_balance = money(balance, field_name="Faize esas bakiye")

    if clean_balance <= Decimal("0.00"):
        return Decimal("0.00")

    clean_rate = rate(credit_limit.interest_rate or Decimal("0.000000"), field_name="Faiz oranı")

    if clean_rate <= Decimal("0.000000"):
        return Decimal("0.00")

    if credit_limit.interest_period == InterestPeriod.DAILY:
        raw_interest = clean_balance * (clean_rate / Decimal("100"))
    elif credit_limit.interest_period == InterestPeriod.YEARLY:
        raw_interest = clean_balance * (clean_rate / Decimal("100")) / Decimal("365")
    else:
        raw_interest = clean_balance * (clean_rate / Decimal("100")) / Decimal("30")

    return money(raw_interest, field_name="Günlük faiz")


def _date_range_inclusive(start_date: date, end_date: date) -> list[date]:
    if end_date < start_date:
        raise CreditFacilityServiceError("Dönem bitiş tarihi başlangıç tarihinden eski olamaz.")

    days = (end_date - start_date).days
    return [start_date + timedelta(days=offset) for offset in range(days + 1)]


def list_credit_limit_transactions(
    session: Session,
    *,
    credit_limit_id: int | None = None,
    include_cancelled: bool = True,
) -> list[BankAccountCreditLimitTransaction]:
    statement = (
        select(BankAccountCreditLimitTransaction)
        .options(
            joinedload(BankAccountCreditLimitTransaction.credit_limit),
            joinedload(BankAccountCreditLimitTransaction.bank_transaction),
        )
        .order_by(
            BankAccountCreditLimitTransaction.transaction_date.desc(),
            BankAccountCreditLimitTransaction.id.desc(),
        )
    )

    if credit_limit_id is not None:
        clean_credit_limit_id = _clean_positive_int(credit_limit_id, "Kredili hesap limiti ID")
        statement = statement.where(
            BankAccountCreditLimitTransaction.credit_limit_id == clean_credit_limit_id
        )

    if not include_cancelled:
        statement = statement.where(
            BankAccountCreditLimitTransaction.status != CreditLimitTransactionStatus.CANCELLED
        )

    return list(session.execute(statement).scalars().all())


def _credit_limit_summary_transaction_is_effective(
    transaction: BankAccountCreditLimitTransaction,
    *,
    as_of_date: date,
    apply_value_dates: bool,
) -> bool:
    if not apply_value_dates:
        return True

    movement_effective_date = transaction.effective_date or transaction.transaction_date

    if movement_effective_date is None:
        return False

    return movement_effective_date <= as_of_date


def get_credit_limit_debt_summary(
    session: Session,
    *,
    credit_limit_id: int,
    as_of_date: date | None = None,
    apply_value_dates: bool = True,
) -> dict[str, Any]:
    """
    Kredili / limitli hesap borç özetini hesaplar.

    Varsayılan hesaplama banka valör mantığını dikkate alır:
    - Limit kullanımı aynı gün borca/faize girer.
    - Limit ödemesi faize ve kullanılabilir limite ertesi gün etki eder.

    apply_value_dates=False kullanıldığında tüm aktif hareketler işlem tarihi/valör ayrımı
    yapılmadan dikkate alınır. Bu seçenek, ikinci kez ödeme gibi fazla ödeme risklerini
    servis seviyesinde engellemek için kullanılır.
    """
    credit_limit = get_credit_limit_or_raise(session, credit_limit_id)
    clean_as_of_date = as_of_date or date.today()
    transactions = list_credit_limit_transactions(
        session,
        credit_limit_id=credit_limit.id,
        include_cancelled=False,
    )

    usage_total = Decimal("0.00")
    payment_total = Decimal("0.00")
    interest_total = Decimal("0.00")
    fee_total = Decimal("0.00")
    adjustment_total = Decimal("0.00")

    booked_usage_total = Decimal("0.00")
    booked_payment_total = Decimal("0.00")
    booked_interest_total = Decimal("0.00")
    booked_fee_total = Decimal("0.00")
    booked_adjustment_total = Decimal("0.00")

    effective_transaction_count = 0

    for transaction in transactions:
        amount = money(transaction.amount or Decimal("0.00"), field_name="Limit hareket tutarı")

        if transaction.transaction_type == CreditLimitTransactionType.USAGE:
            booked_usage_total += amount
        elif transaction.transaction_type == CreditLimitTransactionType.PAYMENT:
            booked_payment_total += amount
        elif transaction.transaction_type == CreditLimitTransactionType.INTEREST:
            booked_interest_total += amount
        elif transaction.transaction_type == CreditLimitTransactionType.FEE:
            booked_fee_total += amount
        elif transaction.transaction_type == CreditLimitTransactionType.ADJUSTMENT:
            booked_adjustment_total += amount

        if not _credit_limit_summary_transaction_is_effective(
            transaction,
            as_of_date=clean_as_of_date,
            apply_value_dates=apply_value_dates,
        ):
            continue

        effective_transaction_count += 1

        if transaction.transaction_type == CreditLimitTransactionType.USAGE:
            usage_total += amount
        elif transaction.transaction_type == CreditLimitTransactionType.PAYMENT:
            payment_total += amount
        elif transaction.transaction_type == CreditLimitTransactionType.INTEREST:
            interest_total += amount
        elif transaction.transaction_type == CreditLimitTransactionType.FEE:
            fee_total += amount
        elif transaction.transaction_type == CreditLimitTransactionType.ADJUSTMENT:
            adjustment_total += amount

    principal_base = money(usage_total + adjustment_total, field_name="Kullanılan ana para")
    principal_debt = money(max(principal_base - payment_total, Decimal("0.00")), field_name="Ana para borcu")
    total_debt_before_payment = money(
        usage_total + adjustment_total + interest_total + fee_total,
        field_name="Ödeme öncesi toplam borç",
    )
    remaining_total_debt = money(
        max(total_debt_before_payment - payment_total, Decimal("0.00")),
        field_name="Toplam borç",
    )

    booked_principal_base = money(
        booked_usage_total + booked_adjustment_total,
        field_name="Kayıtlı kullanılan ana para",
    )
    booked_principal_debt = money(
        max(booked_principal_base - booked_payment_total, Decimal("0.00")),
        field_name="Kayıtlı ana para borcu",
    )
    booked_total_debt_before_payment = money(
        booked_usage_total + booked_adjustment_total + booked_interest_total + booked_fee_total,
        field_name="Kayıtlı ödeme öncesi toplam borç",
    )
    booked_total_debt = money(
        max(booked_total_debt_before_payment - booked_payment_total, Decimal("0.00")),
        field_name="Kayıtlı toplam borç",
    )

    limit_amount = money(credit_limit.limit_amount or Decimal("0.00"), field_name="Limit tutarı")
    available_limit = money(max(limit_amount - principal_debt, Decimal("0.00")), field_name="Kullanılabilir limit")
    booked_available_limit = money(
        max(limit_amount - booked_principal_debt, Decimal("0.00")),
        field_name="Kayıtlı kullanılabilir limit",
    )

    return {
        "credit_limit_id": credit_limit.id,
        "currency_code": _credit_limit_currency_code(credit_limit).value,
        "limit_amount": limit_amount,
        "summary_as_of_date": clean_as_of_date,
        "uses_value_dates": bool(apply_value_dates),
        "usage_total": money(usage_total, field_name="Toplam kullanım"),
        "payment_total": money(payment_total, field_name="Toplam ödeme"),
        "interest_total": money(interest_total, field_name="Toplam faiz"),
        "fee_total": money(fee_total, field_name="Toplam masraf"),
        "adjustment_total": money(adjustment_total, field_name="Toplam düzeltme"),
        "principal_debt": principal_debt,
        "total_debt": remaining_total_debt,
        "available_limit": available_limit,
        "booked_usage_total": money(booked_usage_total, field_name="Kayıtlı toplam kullanım"),
        "booked_payment_total": money(booked_payment_total, field_name="Kayıtlı toplam ödeme"),
        "booked_interest_total": money(booked_interest_total, field_name="Kayıtlı toplam faiz"),
        "booked_fee_total": money(booked_fee_total, field_name="Kayıtlı toplam masraf"),
        "booked_adjustment_total": money(booked_adjustment_total, field_name="Kayıtlı toplam düzeltme"),
        "booked_principal_debt": booked_principal_debt,
        "booked_total_debt": booked_total_debt,
        "booked_available_limit": booked_available_limit,
        "transaction_count": len(transactions),
        "effective_transaction_count": effective_transaction_count,
    }


def create_credit_limit_usage_transaction(
    session: Session,
    *,
    credit_limit_id: int,
    transaction_date: date,
    amount: Decimal,
    reference_no: Optional[str],
    description: Optional[str],
    notes: Optional[str],
    create_bank_account_entry: bool,
    created_by_user_id: Optional[int],
) -> BankAccountCreditLimitTransaction:
    credit_limit = get_credit_limit_or_raise(session, credit_limit_id)
    _validate_credit_limit_is_active(credit_limit)

    clean_amount = _clean_money(amount, "Limit kullanım tutarı")
    clean_reference_no = _clean_optional_text(reference_no)
    clean_description = _clean_optional_text(description)
    clean_notes = _clean_optional_text(notes)

    if clean_amount <= Decimal("0.00"):
        raise CreditFacilityServiceError("Limit kullanım tutarı sıfırdan büyük olmalıdır.")

    summary = get_credit_limit_debt_summary(session, credit_limit_id=credit_limit.id)
    available_limit = money(summary["available_limit"], field_name="Kullanılabilir limit")

    if clean_amount > available_limit:
        raise CreditFacilityServiceError(
            "Limit kullanım tutarı kullanılabilir limitten büyük olamaz. "
            f"Kullanılabilir limit: {available_limit} {_credit_limit_currency_code(credit_limit).value}"
        )

    transaction = BankAccountCreditLimitTransaction(
        credit_limit_id=credit_limit.id,
        transaction_type=CreditLimitTransactionType.USAGE,
        transaction_date=transaction_date,
        effective_date=_credit_limit_effective_date(
            transaction_type=CreditLimitTransactionType.USAGE,
            transaction_date=transaction_date,
        ),
        amount=clean_amount,
        currency_code=_credit_limit_currency_code(credit_limit),
        bank_transaction_id=None,
        status=CreditLimitTransactionStatus.ACTIVE,
        reference_no=clean_reference_no,
        description=clean_description,
        notes=clean_notes,
        created_by_user_id=created_by_user_id,
    )

    session.add(transaction)
    session.flush()

    if create_bank_account_entry:
        bank_account = _get_bank_account_or_raise(session, credit_limit.bank_account_id)

        if not bank_account.is_active:
            raise CreditFacilityServiceError("Pasif banka hesabına limit kullanım girişi oluşturulamaz.")

        if bank_account.currency_code != _credit_limit_currency_code(credit_limit):
            raise CreditFacilityServiceError("Limit para birimi ile bağlı banka hesabı para birimi aynı olmalıdır.")

        try:
            bank_transaction = create_bank_transaction(
                session,
                bank_account_id=bank_account.id,
                transaction_date=transaction_date,
                value_date=transaction_date,
                direction=TransactionDirection.IN,
                status=BankTransactionStatus.REALIZED,
                amount=clean_amount,
                currency_code=_credit_limit_currency_code(credit_limit),
                source_type=FinancialSourceType.CREDIT_LIMIT_USAGE,
                source_id=transaction.id,
                reference_no=clean_reference_no,
                description=clean_description or f"Limit kullanımı: {credit_limit.limit_name}",
                created_by_user_id=created_by_user_id,
            )
        except BankTransactionServiceError as exc:
            raise CreditFacilityServiceError(str(exc)) from exc

        transaction.bank_transaction_id = bank_transaction.id
        session.flush()

    write_audit_log(
        session,
        user_id=created_by_user_id,
        action="CREDIT_LIMIT_TRANSACTION_CREATED",
        entity_type="BankAccountCreditLimitTransaction",
        entity_id=transaction.id,
        description=f"Limit kullanım hareketi oluşturuldu: {credit_limit.limit_name} / {transaction.amount}",
        old_values=None,
        new_values=_serialize_credit_limit_transaction(transaction),
    )

    return transaction


def create_credit_limit_payment_transaction(
    session: Session,
    *,
    credit_limit_id: int,
    payment_bank_account_id: int,
    transaction_date: date,
    amount: Decimal,
    reference_no: Optional[str],
    description: Optional[str],
    notes: Optional[str],
    created_by_user_id: Optional[int],
) -> BankAccountCreditLimitTransaction:
    credit_limit = get_credit_limit_or_raise(session, credit_limit_id)
    _validate_credit_limit_is_active(credit_limit)
    payment_account = _get_bank_account_or_raise(session, payment_bank_account_id)

    if not payment_account.is_active:
        raise CreditFacilityServiceError("Pasif banka hesabından limit ödemesi yapılamaz.")

    if payment_account.currency_code != _credit_limit_currency_code(credit_limit):
        raise CreditFacilityServiceError("Limit ödemesi, limit para birimiyle aynı para birimindeki hesaptan yapılmalıdır.")

    clean_amount = _clean_money(amount, "Limit ödeme tutarı")
    clean_reference_no = _clean_optional_text(reference_no)
    clean_description = _clean_optional_text(description)
    clean_notes = _clean_optional_text(notes)

    if clean_amount <= Decimal("0.00"):
        raise CreditFacilityServiceError("Limit ödeme tutarı sıfırdan büyük olmalıdır.")

    summary = get_credit_limit_debt_summary(
        session,
        credit_limit_id=credit_limit.id,
        apply_value_dates=False,
    )
    total_debt = money(summary["booked_total_debt"], field_name="Kayıtlı toplam borç")

    if total_debt <= Decimal("0.00"):
        raise CreditFacilityServiceError("Bu limitli hesap için ödenecek borç bulunmuyor.")

    if clean_amount > total_debt:
        raise CreditFacilityServiceError(
            "Limit ödeme tutarı mevcut borçtan büyük olamaz. "
            f"Mevcut borç: {total_debt} {_credit_limit_currency_code(credit_limit).value}"
        )

    transaction = BankAccountCreditLimitTransaction(
        credit_limit_id=credit_limit.id,
        transaction_type=CreditLimitTransactionType.PAYMENT,
        transaction_date=transaction_date,
        effective_date=_credit_limit_effective_date(
            transaction_type=CreditLimitTransactionType.PAYMENT,
            transaction_date=transaction_date,
        ),
        amount=clean_amount,
        currency_code=_credit_limit_currency_code(credit_limit),
        bank_transaction_id=None,
        status=CreditLimitTransactionStatus.ACTIVE,
        reference_no=clean_reference_no,
        description=clean_description,
        notes=clean_notes,
        created_by_user_id=created_by_user_id,
    )

    session.add(transaction)
    session.flush()

    try:
        bank_transaction = create_bank_transaction(
            session,
            bank_account_id=payment_account.id,
            transaction_date=transaction_date,
            value_date=transaction_date,
            direction=TransactionDirection.OUT,
            status=BankTransactionStatus.REALIZED,
            amount=clean_amount,
            currency_code=_credit_limit_currency_code(credit_limit),
            source_type=FinancialSourceType.CREDIT_LIMIT_PAYMENT,
            source_id=transaction.id,
            reference_no=clean_reference_no,
            description=clean_description or f"Limit ödemesi: {credit_limit.limit_name}",
            created_by_user_id=created_by_user_id,
        )
    except BankTransactionServiceError as exc:
        raise CreditFacilityServiceError(str(exc)) from exc

    transaction.bank_transaction_id = bank_transaction.id
    session.flush()

    write_audit_log(
        session,
        user_id=created_by_user_id,
        action="CREDIT_LIMIT_TRANSACTION_CREATED",
        entity_type="BankAccountCreditLimitTransaction",
        entity_id=transaction.id,
        description=f"Limit ödeme hareketi oluşturuldu: {credit_limit.limit_name} / {transaction.amount}",
        old_values=None,
        new_values=_serialize_credit_limit_transaction(transaction),
    )

    return transaction


def create_credit_limit_interest_transaction(
    session: Session,
    *,
    credit_limit_id: int,
    transaction_date: date,
    amount: Decimal,
    reference_no: Optional[str],
    description: Optional[str],
    notes: Optional[str],
    created_by_user_id: Optional[int],
) -> BankAccountCreditLimitTransaction:
    credit_limit = get_credit_limit_or_raise(session, credit_limit_id)
    _validate_credit_limit_is_active(credit_limit)

    clean_amount = _clean_money(amount, "Faiz tutarı")
    clean_reference_no = _clean_optional_text(reference_no)
    clean_description = _clean_optional_text(description)
    clean_notes = _clean_optional_text(notes)

    if clean_amount <= Decimal("0.00"):
        raise CreditFacilityServiceError("Faiz tutarı sıfırdan büyük olmalıdır.")

    transaction = BankAccountCreditLimitTransaction(
        credit_limit_id=credit_limit.id,
        transaction_type=CreditLimitTransactionType.INTEREST,
        transaction_date=transaction_date,
        effective_date=transaction_date,
        amount=clean_amount,
        currency_code=_credit_limit_currency_code(credit_limit),
        bank_transaction_id=None,
        status=CreditLimitTransactionStatus.ACTIVE,
        reference_no=clean_reference_no,
        description=clean_description,
        notes=clean_notes,
        created_by_user_id=created_by_user_id,
    )

    session.add(transaction)
    session.flush()

    write_audit_log(
        session,
        user_id=created_by_user_id,
        action="CREDIT_LIMIT_TRANSACTION_CREATED",
        entity_type="BankAccountCreditLimitTransaction",
        entity_id=transaction.id,
        description=f"Limit faiz tahakkuku oluşturuldu: {credit_limit.limit_name} / {transaction.amount}",
        old_values=None,
        new_values=_serialize_credit_limit_transaction(transaction),
    )

    return transaction


def create_credit_limit_fee_transaction(
    session: Session,
    *,
    credit_limit_id: int,
    transaction_date: date,
    amount: Decimal,
    reference_no: Optional[str],
    description: Optional[str],
    notes: Optional[str],
    created_by_user_id: Optional[int],
) -> BankAccountCreditLimitTransaction:
    credit_limit = get_credit_limit_or_raise(session, credit_limit_id)
    _validate_credit_limit_is_active(credit_limit)

    clean_amount = _clean_money(amount, "Masraf tutarı")
    clean_reference_no = _clean_optional_text(reference_no)
    clean_description = _clean_optional_text(description)
    clean_notes = _clean_optional_text(notes)

    if clean_amount <= Decimal("0.00"):
        raise CreditFacilityServiceError("Masraf tutarı sıfırdan büyük olmalıdır.")

    transaction = BankAccountCreditLimitTransaction(
        credit_limit_id=credit_limit.id,
        transaction_type=CreditLimitTransactionType.FEE,
        transaction_date=transaction_date,
        effective_date=transaction_date,
        amount=clean_amount,
        currency_code=_credit_limit_currency_code(credit_limit),
        bank_transaction_id=None,
        status=CreditLimitTransactionStatus.ACTIVE,
        reference_no=clean_reference_no,
        description=clean_description,
        notes=clean_notes,
        created_by_user_id=created_by_user_id,
    )

    session.add(transaction)
    session.flush()

    write_audit_log(
        session,
        user_id=created_by_user_id,
        action="CREDIT_LIMIT_TRANSACTION_CREATED",
        entity_type="BankAccountCreditLimitTransaction",
        entity_id=transaction.id,
        description=f"Limit masraf hareketi oluşturuldu: {credit_limit.limit_name} / {transaction.amount}",
        old_values=None,
        new_values=_serialize_credit_limit_transaction(transaction),
    )

    return transaction


def cancel_credit_limit_transaction(
    session: Session,
    *,
    transaction_id: int,
    cancel_reason: str,
    cancelled_by_user_id: Optional[int],
) -> BankAccountCreditLimitTransaction:
    clean_transaction_id = _clean_positive_int(transaction_id, "Limit hareket ID")
    clean_cancel_reason = _clean_required_text(cancel_reason, "İptal nedeni")
    transaction = session.get(BankAccountCreditLimitTransaction, clean_transaction_id)

    if transaction is None:
        raise CreditFacilityServiceError(f"Limit hareketi bulunamadı. Hareket ID: {clean_transaction_id}")

    if transaction.status == CreditLimitTransactionStatus.CANCELLED:
        return transaction

    old_values = _serialize_credit_limit_transaction(transaction)

    if transaction.bank_transaction_id is not None:
        try:
            cancel_bank_transaction(
                session,
                bank_transaction_id=int(transaction.bank_transaction_id),
                cancel_reason=f"Limitli hesap hareket iptali: {clean_cancel_reason}",
                cancelled_by_user_id=cancelled_by_user_id,
            )
        except BankTransactionServiceError as exc:
            raise CreditFacilityServiceError(str(exc)) from exc

    transaction.status = CreditLimitTransactionStatus.CANCELLED
    transaction.cancelled_by_user_id = cancelled_by_user_id
    transaction.cancelled_at = datetime.now()
    transaction.cancel_reason = clean_cancel_reason

    session.flush()

    write_audit_log(
        session,
        user_id=cancelled_by_user_id,
        action="CREDIT_LIMIT_TRANSACTION_CANCELLED",
        entity_type="BankAccountCreditLimitTransaction",
        entity_id=transaction.id,
        description=f"Limitli hesap hareketi iptal edildi. Hareket ID: {transaction.id}",
        old_values=old_values,
        new_values=_serialize_credit_limit_transaction(transaction),
    )

    return transaction


def calculate_credit_limit_period_report(
    session: Session,
    *,
    credit_limit_id: int,
    period_start: date,
    period_end: date,
) -> dict[str, Any]:
    credit_limit = get_credit_limit_or_raise(session, credit_limit_id)
    _date_range_inclusive(period_start, period_end)

    transactions = list_credit_limit_transactions(
        session,
        credit_limit_id=credit_limit.id,
        include_cancelled=False,
    )

    active_transactions = [
        transaction
        for transaction in transactions
        if transaction.effective_date is not None and transaction.effective_date <= period_end
    ]
    active_transactions.sort(key=lambda item: (item.effective_date, item.id or 0))

    opening_interest_basis = Decimal("0.00")
    movements_by_effective_date: dict[date, list[BankAccountCreditLimitTransaction]] = {}
    period_movement_rows: list[dict[str, Any]] = []

    for transaction in active_transactions:
        effect = _credit_limit_interest_basis_effect(transaction)

        if transaction.effective_date < period_start:
            opening_interest_basis = max(opening_interest_basis + effect, Decimal("0.00"))
            continue

        movements_by_effective_date.setdefault(transaction.effective_date, []).append(transaction)

        if period_start <= transaction.transaction_date <= period_end:
            period_movement_rows.append(
                {
                    "id": transaction.id,
                    "transaction_type": transaction.transaction_type.value,
                    "transaction_date": transaction.transaction_date,
                    "effective_date": transaction.effective_date,
                    "amount": money(transaction.amount or Decimal("0.00"), field_name="Limit hareket tutarı"),
                    "currency_code": transaction.currency_code.value,
                    "description": transaction.description,
                    "reference_no": transaction.reference_no,
                    "status": transaction.status.value,
                }
            )

    current_interest_basis = money(opening_interest_basis, field_name="Dönem başı faize esas borç")
    daily_rows: list[dict[str, Any]] = []
    calculated_interest_total = Decimal("0.00")

    for current_day in _date_range_inclusive(period_start, period_end):
        for transaction in movements_by_effective_date.get(current_day, []):
            current_interest_basis = max(
                current_interest_basis + _credit_limit_interest_basis_effect(transaction),
                Decimal("0.00"),
            )
            current_interest_basis = money(current_interest_basis, field_name="Faize esas borç")

        daily_interest = _daily_credit_limit_interest(
            balance=current_interest_basis,
            credit_limit=credit_limit,
            current_date=current_day,
        )
        calculated_interest_total += daily_interest

        daily_rows.append(
            {
                "date": current_day,
                "interest_basis_debt": current_interest_basis,
                "daily_interest": daily_interest,
                "currency_code": _credit_limit_currency_code(credit_limit).value,
            }
        )

    period_usage_total = Decimal("0.00")
    period_payment_total = Decimal("0.00")
    period_interest_total = Decimal("0.00")
    period_fee_total = Decimal("0.00")

    for row in period_movement_rows:
        row_amount = money(row["amount"], field_name="Dönem hareket tutarı")
        row_type = row["transaction_type"]

        if row_type == CreditLimitTransactionType.USAGE.value:
            period_usage_total += row_amount
        elif row_type == CreditLimitTransactionType.PAYMENT.value:
            period_payment_total += row_amount
        elif row_type == CreditLimitTransactionType.INTEREST.value:
            period_interest_total += row_amount
        elif row_type == CreditLimitTransactionType.FEE.value:
            period_fee_total += row_amount

    ending_interest_basis = daily_rows[-1]["interest_basis_debt"] if daily_rows else current_interest_basis

    return {
        "credit_limit_id": credit_limit.id,
        "limit_name": credit_limit.limit_name,
        "bank_account_id": credit_limit.bank_account_id,
        "currency_code": _credit_limit_currency_code(credit_limit).value,
        "period_start": period_start,
        "period_end": period_end,
        "limit_amount": money(credit_limit.limit_amount or Decimal("0.00"), field_name="Limit tutarı"),
        "monthly_interest_rate": rate(credit_limit.interest_rate or Decimal("0.000000"), field_name="Faiz oranı"),
        "interest_period": credit_limit.interest_period.value,
        "opening_interest_basis_debt": money(opening_interest_basis, field_name="Dönem başı borç"),
        "period_usage_total": money(period_usage_total, field_name="Dönem kullanım toplamı"),
        "period_payment_total": money(period_payment_total, field_name="Dönem ödeme toplamı"),
        "period_recorded_interest_total": money(period_interest_total, field_name="Dönem kayıtlı faiz toplamı"),
        "period_fee_total": money(period_fee_total, field_name="Dönem masraf toplamı"),
        "calculated_interest_total": money(calculated_interest_total, field_name="Hesaplanan faiz toplamı"),
        "ending_interest_basis_debt": money(ending_interest_basis, field_name="Dönem sonu ana para borcu"),
        "movement_rows": period_movement_rows,
        "daily_rows": daily_rows,
    }


__all__ = [
    "CreditFacilityServiceError",
    "create_credit_card",
    "update_credit_card",
    "deactivate_credit_card",
    "activate_credit_card",
    "get_credit_card_by_name",
    "get_credit_card_by_last_four_digits",
    "list_credit_cards",
    "get_credit_card_or_raise",
    "list_credit_card_transactions",
    "create_credit_card_transaction",
    "cancel_credit_card_transaction",
    "list_credit_card_payments",
    "get_credit_card_debt_summary",
    "get_credit_card_recommendation_status",
    "get_credit_card_recommendation_summary",
    "create_credit_card_payment",
    "cancel_credit_card_payment",
    "create_credit_limit",
    "update_credit_limit",
    "deactivate_credit_limit",
    "activate_credit_limit",
    "get_credit_limit_by_name",
    "get_credit_limit_or_raise",
    "list_credit_limits",
    "list_credit_limit_transactions",
    "get_credit_limit_debt_summary",
    "create_credit_limit_usage_transaction",
    "create_credit_limit_payment_transaction",
    "create_credit_limit_interest_transaction",
    "create_credit_limit_fee_transaction",
    "cancel_credit_limit_transaction",
    "calculate_credit_limit_period_report",
]
