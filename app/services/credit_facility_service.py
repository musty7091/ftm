from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Optional, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import joinedload
from sqlalchemy.orm import Session

from app.models.bank import Bank, BankAccount
from app.models.credit_facility import BankAccountCreditLimit, CreditCard, CreditCardTransaction
from app.models.enums import (
    CreditCardNetwork,
    CreditCardTransactionStatus,
    CreditCardType,
    CreditLimitType,
    CreditLimitUsageMode,
    CurrencyCode,
    InterestPeriod,
)
from app.services.audit_service import write_audit_log
from app.utils.decimal_utils import money, rate


class CreditFacilityServiceError(ValueError):
    pass


EnumT = TypeVar("EnumT")


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
    "create_credit_limit",
    "update_credit_limit",
    "deactivate_credit_limit",
    "get_credit_limit_by_name",
    "list_credit_limits",
]
