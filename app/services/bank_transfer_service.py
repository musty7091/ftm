from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.bank import BankAccount
from app.models.bank_transfer import BankTransfer
from app.models.enums import (
    BankTransactionStatus,
    BankTransferStatus,
    FinancialSourceType,
    TransactionDirection,
)
from app.services.audit_service import write_audit_log
from app.services.bank_transaction_service import (
    BankTransactionServiceError,
    cancel_bank_transaction,
    create_bank_transaction,
    get_bank_account_balance_summary,
)
from app.services.permission_audit_service import require_permission_with_audit
from app.services.permission_service import Permission, PermissionServiceError
from app.utils.decimal_utils import money


class BankTransferServiceError(ValueError):
    pass


def _clean_optional_text(value: Optional[str]) -> Optional[str]:
    cleaned_value = (value or "").strip()

    if not cleaned_value:
        return None

    return cleaned_value


def _clean_required_text(value: str, field_name: str) -> str:
    cleaned_value = (value or "").strip()

    if not cleaned_value:
        raise BankTransferServiceError(f"{field_name} boş olamaz.")

    return cleaned_value


def _validate_positive_money(value: object, field_name: str) -> Decimal:
    cleaned_amount = money(value, field_name=field_name)

    if cleaned_amount <= Decimal("0.00"):
        raise BankTransferServiceError(f"{field_name} sıfırdan büyük olmalıdır.")

    return cleaned_amount


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
        raise BankTransferServiceError(str(exc)) from exc


def _transfer_to_dict(transfer: BankTransfer) -> dict[str, Any]:
    return {
        "id": transfer.id,
        "from_bank_account_id": transfer.from_bank_account_id,
        "to_bank_account_id": transfer.to_bank_account_id,
        "transfer_date": transfer.transfer_date.isoformat(),
        "value_date": transfer.value_date.isoformat() if transfer.value_date else None,
        "amount": str(transfer.amount),
        "currency_code": transfer.currency_code.value,
        "status": transfer.status.value,
        "outgoing_transaction_id": transfer.outgoing_transaction_id,
        "incoming_transaction_id": transfer.incoming_transaction_id,
        "reference_no": transfer.reference_no,
        "description": transfer.description,
        "created_by_user_id": transfer.created_by_user_id,
        "cancelled_by_user_id": transfer.cancelled_by_user_id,
        "cancelled_at": transfer.cancelled_at.isoformat() if transfer.cancelled_at else None,
        "cancel_reason": transfer.cancel_reason,
    }


def create_bank_transfer(
    session: Session,
    *,
    from_bank_account_id: int,
    to_bank_account_id: int,
    transfer_date: date,
    value_date: Optional[date],
    amount: object,
    status: BankTransferStatus,
    reference_no: Optional[str],
    description: Optional[str],
    created_by_user_id: Optional[int] = None,
    acting_user: Optional[Any] = None,
) -> BankTransfer:
    permission_user_id = _require_permission_if_user_given(
        acting_user,
        Permission.BANK_TRANSFER_CREATE,
        attempted_action="BANK_TRANSFER_CREATE",
        entity_type="BankTransfer",
        details={
            "from_bank_account_id": from_bank_account_id,
            "to_bank_account_id": to_bank_account_id,
            "transfer_date": transfer_date.isoformat(),
            "value_date": value_date.isoformat() if value_date else None,
            "amount": str(amount),
            "status": status.value if hasattr(status, "value") else str(status),
        },
    )

    if acting_user is not None and status == BankTransferStatus.REALIZED:
        _require_permission_if_user_given(
            acting_user,
            Permission.BANK_TRANSFER_REALIZE,
            attempted_action="BANK_TRANSFER_REALIZE",
            entity_type="BankTransfer",
            details={
                "from_bank_account_id": from_bank_account_id,
                "to_bank_account_id": to_bank_account_id,
                "transfer_date": transfer_date.isoformat(),
                "amount": str(amount),
                "status": status.value,
            },
        )

    effective_created_by_user_id = permission_user_id if permission_user_id is not None else created_by_user_id

    if from_bank_account_id == to_bank_account_id:
        raise BankTransferServiceError("Aynı banka hesabı içinde transfer yapılamaz.")

    if status == BankTransferStatus.CANCELLED:
        raise BankTransferServiceError("Transfer iptal durumunda oluşturulamaz. Önce oluşturulmalı, sonra iptal edilmelidir.")

    from_bank_account = session.get(BankAccount, from_bank_account_id)
    to_bank_account = session.get(BankAccount, to_bank_account_id)

    if from_bank_account is None:
        raise BankTransferServiceError(f"Çıkış yapılacak banka hesabı bulunamadı. Hesap ID: {from_bank_account_id}")

    if to_bank_account is None:
        raise BankTransferServiceError(f"Giriş yapılacak banka hesabı bulunamadı. Hesap ID: {to_bank_account_id}")

    if not from_bank_account.is_active:
        raise BankTransferServiceError("Çıkış yapılacak banka hesabı pasif durumda.")

    if not to_bank_account.is_active:
        raise BankTransferServiceError("Giriş yapılacak banka hesabı pasif durumda.")

    if from_bank_account.currency_code != to_bank_account.currency_code:
        raise BankTransferServiceError(
            "Transfer yapılacak hesapların para birimi aynı olmalıdır. "
            f"Çıkış hesabı: {from_bank_account.currency_code.value}, "
            f"Giriş hesabı: {to_bank_account.currency_code.value}"
        )

    cleaned_amount = _validate_positive_money(amount, "Transfer tutarı")
    cleaned_reference_no = _clean_optional_text(reference_no)
    cleaned_description = _clean_optional_text(description)

    if status == BankTransferStatus.REALIZED:
        from_balance_summary = get_bank_account_balance_summary(
            session,
            bank_account_id=from_bank_account.id,
        )

        current_balance = from_balance_summary["current_balance"]

        if current_balance < cleaned_amount:
            raise BankTransferServiceError(
                f"Çıkış hesabında yeterli bakiye yok. "
                f"Mevcut bakiye: {current_balance} {from_bank_account.currency_code.value}, "
                f"Transfer tutarı: {cleaned_amount} {from_bank_account.currency_code.value}"
            )

    transfer = BankTransfer(
        from_bank_account_id=from_bank_account.id,
        to_bank_account_id=to_bank_account.id,
        transfer_date=transfer_date,
        value_date=value_date,
        amount=cleaned_amount,
        currency_code=from_bank_account.currency_code,
        status=status,
        reference_no=cleaned_reference_no,
        description=cleaned_description,
        created_by_user_id=effective_created_by_user_id,
    )

    session.add(transfer)
    session.flush()

    transaction_status = BankTransactionStatus(status.value)

    outgoing_transaction = create_bank_transaction(
        session,
        bank_account_id=from_bank_account.id,
        transaction_date=transfer_date,
        value_date=value_date,
        direction=TransactionDirection.OUT,
        status=transaction_status,
        amount=cleaned_amount,
        currency_code=from_bank_account.currency_code,
        source_type=FinancialSourceType.BANK_TRANSFER,
        source_id=transfer.id,
        reference_no=cleaned_reference_no,
        description=f"Transfer çıkışı: {cleaned_description}" if cleaned_description else "Transfer çıkışı",
        created_by_user_id=effective_created_by_user_id,
    )

    incoming_transaction = create_bank_transaction(
        session,
        bank_account_id=to_bank_account.id,
        transaction_date=transfer_date,
        value_date=value_date,
        direction=TransactionDirection.IN,
        status=transaction_status,
        amount=cleaned_amount,
        currency_code=to_bank_account.currency_code,
        source_type=FinancialSourceType.BANK_TRANSFER,
        source_id=transfer.id,
        reference_no=cleaned_reference_no,
        description=f"Transfer girişi: {cleaned_description}" if cleaned_description else "Transfer girişi",
        created_by_user_id=effective_created_by_user_id,
    )

    transfer.outgoing_transaction_id = outgoing_transaction.id
    transfer.incoming_transaction_id = incoming_transaction.id

    session.flush()

    write_audit_log(
        session,
        user_id=effective_created_by_user_id,
        action="BANK_TRANSFER_CREATED",
        entity_type="BankTransfer",
        entity_id=transfer.id,
        description=(
            f"Banka transferi oluşturuldu: "
            f"{from_bank_account.account_name} -> {to_bank_account.account_name} "
            f"{transfer.amount} {transfer.currency_code.value}"
        ),
        old_values=None,
        new_values=_transfer_to_dict(transfer),
    )

    return transfer


def cancel_bank_transfer(
    session: Session,
    *,
    transfer_id: int,
    cancelled_by_user_id: Optional[int] = None,
    cancel_reason: str,
    acting_user: Optional[Any] = None,
) -> BankTransfer:
    permission_user_id = _require_permission_if_user_given(
        acting_user,
        Permission.BANK_TRANSFER_CANCEL,
        attempted_action="BANK_TRANSFER_CANCEL",
        entity_type="BankTransfer",
        details={
            "transfer_id": transfer_id,
            "cancel_reason": cancel_reason,
        },
    )

    effective_cancelled_by_user_id = permission_user_id if permission_user_id is not None else cancelled_by_user_id

    transfer = session.get(BankTransfer, transfer_id)

    if transfer is None:
        raise BankTransferServiceError(f"Banka transferi bulunamadı. Transfer ID: {transfer_id}")

    if transfer.status == BankTransferStatus.CANCELLED:
        raise BankTransferServiceError("Bu banka transferi zaten iptal edilmiş.")

    cleaned_cancel_reason = _clean_required_text(cancel_reason, "İptal nedeni")

    old_values = _transfer_to_dict(transfer)

    try:
        if transfer.outgoing_transaction_id is not None:
            cancel_bank_transaction(
                session,
                bank_transaction_id=transfer.outgoing_transaction_id,
                cancelled_by_user_id=effective_cancelled_by_user_id,
                cancel_reason=f"Transfer iptali: {cleaned_cancel_reason}",
            )

        if transfer.incoming_transaction_id is not None:
            cancel_bank_transaction(
                session,
                bank_transaction_id=transfer.incoming_transaction_id,
                cancelled_by_user_id=effective_cancelled_by_user_id,
                cancel_reason=f"Transfer iptali: {cleaned_cancel_reason}",
            )

    except BankTransactionServiceError as exc:
        raise BankTransferServiceError(f"Transfere bağlı banka hareketi iptal edilemedi: {exc}") from exc

    transfer.status = BankTransferStatus.CANCELLED
    transfer.cancelled_by_user_id = effective_cancelled_by_user_id
    transfer.cancelled_at = datetime.now(timezone.utc)
    transfer.cancel_reason = cleaned_cancel_reason

    session.flush()

    write_audit_log(
        session,
        user_id=effective_cancelled_by_user_id,
        action="BANK_TRANSFER_CANCELLED",
        entity_type="BankTransfer",
        entity_id=transfer.id,
        description=f"Banka transferi iptal edildi. Transfer ID: {transfer.id}",
        old_values=old_values,
        new_values=_transfer_to_dict(transfer),
    )

    return transfer