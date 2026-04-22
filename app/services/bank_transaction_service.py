from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.bank import BankAccount
from app.models.bank_transaction import BankTransaction
from app.models.enums import (
    BankTransactionStatus,
    CurrencyCode,
    FinancialSourceType,
    TransactionDirection,
)
from app.services.audit_service import write_audit_log
from app.services.permission_audit_service import require_permission_with_audit
from app.services.permission_service import Permission, PermissionServiceError
from app.utils.decimal_utils import money


class BankTransactionServiceError(ValueError):
    pass


def _clean_optional_text(value: Optional[str]) -> Optional[str]:
    cleaned_value = (value or "").strip()

    if not cleaned_value:
        return None

    return cleaned_value


def _validate_positive_money(value: object, field_name: str) -> Decimal:
    cleaned_amount = money(value, field_name=field_name)

    if cleaned_amount <= Decimal("0.00"):
        raise BankTransactionServiceError(f"{field_name} sıfırdan büyük olmalıdır.")

    return cleaned_amount


def _normalize_direction(value: TransactionDirection | str) -> TransactionDirection:
    if isinstance(value, TransactionDirection):
        return value

    try:
        return TransactionDirection(str(value).strip().upper())
    except ValueError as exc:
        raise BankTransactionServiceError(f"Geçersiz hareket yönü: {value}") from exc


def _normalize_status(value: BankTransactionStatus | str) -> BankTransactionStatus:
    if isinstance(value, BankTransactionStatus):
        return value

    try:
        return BankTransactionStatus(str(value).strip().upper())
    except ValueError as exc:
        raise BankTransactionServiceError(f"Geçersiz banka hareket durumu: {value}") from exc


def _normalize_currency(value: CurrencyCode | str) -> CurrencyCode:
    if isinstance(value, CurrencyCode):
        return value

    try:
        return CurrencyCode(str(value).strip().upper())
    except ValueError as exc:
        raise BankTransactionServiceError(f"Geçersiz para birimi: {value}") from exc


def _normalize_source_type(value: FinancialSourceType | str) -> FinancialSourceType:
    if isinstance(value, FinancialSourceType):
        return value

    try:
        return FinancialSourceType(str(value).strip().upper())
    except ValueError as exc:
        raise BankTransactionServiceError(f"Geçersiz kaynak türü: {value}") from exc


def _require_permission_if_user_given(
    acting_user: Optional[Any],
    permission: Permission,
    attempted_action: str,
    entity_type: str,
    details: Optional[dict[str, Any]] = None,
) -> Optional[int]:
    if acting_user is None:
        return None

    try:
        return require_permission_with_audit(
            acting_user=acting_user,
            permission=permission,
            attempted_action=attempted_action,
            entity_type=entity_type,
            entity_id=None,
            details=details,
        )
    except PermissionServiceError as exc:
        raise BankTransactionServiceError(str(exc)) from exc


def _bank_transaction_to_dict(bank_transaction: BankTransaction) -> dict[str, Any]:
    return {
        "id": bank_transaction.id,
        "bank_account_id": bank_transaction.bank_account_id,
        "transaction_date": bank_transaction.transaction_date.isoformat(),
        "value_date": bank_transaction.value_date.isoformat() if bank_transaction.value_date else None,
        "direction": bank_transaction.direction.value,
        "status": bank_transaction.status.value,
        "amount": str(bank_transaction.amount),
        "currency_code": bank_transaction.currency_code.value,
        "source_type": bank_transaction.source_type.value,
        "source_id": bank_transaction.source_id,
        "reference_no": bank_transaction.reference_no,
        "description": bank_transaction.description,
        "created_by_user_id": bank_transaction.created_by_user_id,
        "cancelled_by_user_id": bank_transaction.cancelled_by_user_id,
        "cancelled_at": bank_transaction.cancelled_at.isoformat() if bank_transaction.cancelled_at else None,
        "cancel_reason": bank_transaction.cancel_reason,
    }


def create_bank_transaction(
    session: Session,
    *,
    bank_account_id: int,
    transaction_date: date,
    value_date: Optional[date],
    direction: TransactionDirection | str,
    status: BankTransactionStatus | str,
    amount: object,
    currency_code: CurrencyCode | str,
    source_type: FinancialSourceType | str,
    source_id: Optional[int],
    reference_no: Optional[str],
    description: Optional[str],
    created_by_user_id: Optional[int] = None,
    acting_user: Optional[Any] = None,
) -> BankTransaction:
    permission_user_id = _require_permission_if_user_given(
        acting_user,
        Permission.BANK_TRANSACTION_CREATE,
        attempted_action="BANK_TRANSACTION_CREATE",
        entity_type="BankTransaction",
        details={
            "bank_account_id": bank_account_id,
            "transaction_date": transaction_date.isoformat(),
            "direction": str(direction),
            "status": str(status),
            "amount": str(amount),
            "source_type": str(source_type),
        },
    )

    effective_created_by_user_id = permission_user_id if permission_user_id is not None else created_by_user_id

    bank_account = session.get(BankAccount, bank_account_id)

    if bank_account is None:
        raise BankTransactionServiceError(f"Banka hesabı bulunamadı. Hesap ID: {bank_account_id}")

    if not bank_account.is_active:
        raise BankTransactionServiceError("Pasif banka hesabına hareket girilemez.")

    cleaned_direction = _normalize_direction(direction)
    cleaned_status = _normalize_status(status)
    cleaned_amount = _validate_positive_money(amount, "Banka hareket tutarı")
    cleaned_currency_code = _normalize_currency(currency_code)
    cleaned_source_type = _normalize_source_type(source_type)
    cleaned_reference_no = _clean_optional_text(reference_no)
    cleaned_description = _clean_optional_text(description)

    if cleaned_currency_code != bank_account.currency_code:
        raise BankTransactionServiceError(
            f"Hareket para birimi ile banka hesabı para birimi aynı olmalıdır. "
            f"Hareket: {cleaned_currency_code.value}, Hesap: {bank_account.currency_code.value}"
        )

    bank_transaction = BankTransaction(
        bank_account_id=bank_account.id,
        transaction_date=transaction_date,
        value_date=value_date,
        direction=cleaned_direction,
        status=cleaned_status,
        amount=cleaned_amount,
        currency_code=cleaned_currency_code,
        source_type=cleaned_source_type,
        source_id=source_id,
        reference_no=cleaned_reference_no,
        description=cleaned_description,
        created_by_user_id=effective_created_by_user_id,
    )

    session.add(bank_transaction)
    session.flush()

    write_audit_log(
        session,
        user_id=effective_created_by_user_id,
        action="BANK_TRANSACTION_CREATED",
        entity_type="BankTransaction",
        entity_id=bank_transaction.id,
        description=(
            f"Banka hareketi oluşturuldu: "
            f"{bank_transaction.direction.value} {bank_transaction.amount} {bank_transaction.currency_code.value}"
        ),
        old_values=None,
        new_values=_bank_transaction_to_dict(bank_transaction),
    )

    return bank_transaction


def cancel_bank_transaction(
    session: Session,
    *,
    bank_transaction_id: int,
    cancel_reason: str,
    cancelled_by_user_id: Optional[int] = None,
    acting_user: Optional[Any] = None,
) -> BankTransaction:
    permission_user_id = _require_permission_if_user_given(
        acting_user,
        Permission.BANK_TRANSACTION_CANCEL,
        attempted_action="BANK_TRANSACTION_CANCEL",
        entity_type="BankTransaction",
        details={
            "bank_transaction_id": bank_transaction_id,
            "cancel_reason": cancel_reason,
        },
    )

    effective_cancelled_by_user_id = permission_user_id if permission_user_id is not None else cancelled_by_user_id

    cleaned_cancel_reason = (cancel_reason or "").strip()

    if not cleaned_cancel_reason:
        raise BankTransactionServiceError("İptal nedeni boş olamaz.")

    bank_transaction = session.get(BankTransaction, bank_transaction_id)

    if bank_transaction is None:
        raise BankTransactionServiceError(f"Banka hareketi bulunamadı. Hareket ID: {bank_transaction_id}")

    if bank_transaction.status == BankTransactionStatus.CANCELLED:
        raise BankTransactionServiceError("Bu banka hareketi zaten iptal edilmiş.")

    old_values = _bank_transaction_to_dict(bank_transaction)

    bank_transaction.status = BankTransactionStatus.CANCELLED
    bank_transaction.cancelled_by_user_id = effective_cancelled_by_user_id
    bank_transaction.cancelled_at = datetime.now()
    bank_transaction.cancel_reason = cleaned_cancel_reason

    session.flush()

    write_audit_log(
        session,
        user_id=effective_cancelled_by_user_id,
        action="BANK_TRANSACTION_CANCELLED",
        entity_type="BankTransaction",
        entity_id=bank_transaction.id,
        description=f"Banka hareketi iptal edildi. Hareket ID: {bank_transaction.id}",
        old_values=old_values,
        new_values=_bank_transaction_to_dict(bank_transaction),
    )

    return bank_transaction


def get_bank_account_balance_summary(
    session: Session,
    *,
    bank_account_id: int,
) -> dict[str, Any]:
    bank_account = session.get(BankAccount, bank_account_id)

    if bank_account is None:
        raise BankTransactionServiceError(f"Banka hesabı bulunamadı. Hesap ID: {bank_account_id}")

    incoming_total_result = session.execute(
        select(func.coalesce(func.sum(BankTransaction.amount), Decimal("0.00"))).where(
            BankTransaction.bank_account_id == bank_account.id,
            BankTransaction.direction == TransactionDirection.IN,
            BankTransaction.status == BankTransactionStatus.REALIZED,
        )
    ).scalar_one()

    outgoing_total_result = session.execute(
        select(func.coalesce(func.sum(BankTransaction.amount), Decimal("0.00"))).where(
            BankTransaction.bank_account_id == bank_account.id,
            BankTransaction.direction == TransactionDirection.OUT,
            BankTransaction.status == BankTransactionStatus.REALIZED,
        )
    ).scalar_one()

    opening_balance = money(bank_account.opening_balance or Decimal("0.00"), field_name="Açılış bakiyesi")
    incoming_total = money(incoming_total_result or Decimal("0.00"), field_name="Toplam giriş")
    outgoing_total = money(outgoing_total_result or Decimal("0.00"), field_name="Toplam çıkış")
    current_balance = money(opening_balance + incoming_total - outgoing_total, field_name="Güncel bakiye")

    return {
        "bank_account_id": bank_account.id,
        "account_name": bank_account.account_name,
        "currency_code": bank_account.currency_code.value,
        "opening_balance": opening_balance,
        "incoming_total": incoming_total,
        "outgoing_total": outgoing_total,
        "current_balance": current_balance,
    }