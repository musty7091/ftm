from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.bank import Bank, BankAccount
from app.models.enums import (
    BankTransactionStatus,
    FinancialSourceType,
    PosSettlementStatus,
    TransactionDirection,
)
from app.models.pos import PosDevice, PosSettlement
from app.services.audit_service import write_audit_log
from app.services.bank_transaction_service import (
    BankTransactionServiceError,
    create_bank_transaction,
)
from app.services.permission_audit_service import require_permission_with_audit
from app.services.permission_service import Permission, PermissionServiceError
from app.utils.decimal_utils import money


class PosSettlementServiceError(ValueError):
    pass


def _clean_optional_text(value: Optional[str]) -> Optional[str]:
    cleaned_value = (value or "").strip()

    if not cleaned_value:
        return None

    return cleaned_value


def _clean_required_text(value: Optional[str], field_name: str) -> str:
    cleaned_value = (value or "").strip()

    if not cleaned_value:
        raise PosSettlementServiceError(f"{field_name} boş olamaz.")

    return cleaned_value


def _require_permission_if_user_given(
    acting_user: Optional[Any],
    permission: Permission,
    attempted_action: str,
    entity_type: str,
    entity_id: Optional[int] = None,
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
            entity_id=entity_id,
            details=details,
        )
    except PermissionServiceError as exc:
        raise PosSettlementServiceError(str(exc)) from exc


def _normalize_percent_rate_to_ratio(rate_value: Decimal) -> Decimal:
    if rate_value <= Decimal("0.00"):
        return Decimal("0.00")

    if rate_value > Decimal("1.00"):
        return rate_value / Decimal("100")

    return rate_value


def _pos_settlement_to_dict(pos_settlement: PosSettlement) -> dict[str, Any]:
    return {
        "id": pos_settlement.id,
        "pos_device_id": pos_settlement.pos_device_id,
        "transaction_date": pos_settlement.transaction_date.isoformat(),
        "expected_settlement_date": pos_settlement.expected_settlement_date.isoformat(),
        "realized_settlement_date": (
            pos_settlement.realized_settlement_date.isoformat()
            if pos_settlement.realized_settlement_date
            else None
        ),
        "gross_amount": str(pos_settlement.gross_amount),
        "commission_rate": str(pos_settlement.commission_rate),
        "commission_amount": str(pos_settlement.commission_amount),
        "net_amount": str(pos_settlement.net_amount),
        "actual_net_amount": (
            str(pos_settlement.actual_net_amount)
            if pos_settlement.actual_net_amount is not None
            else None
        ),
        "difference_amount": str(pos_settlement.difference_amount),
        "difference_reason": pos_settlement.difference_reason,
        "currency_code": pos_settlement.currency_code.value,
        "status": pos_settlement.status.value,
        "bank_transaction_id": pos_settlement.bank_transaction_id,
        "reference_no": pos_settlement.reference_no,
        "description": pos_settlement.description,
        "created_by_user_id": pos_settlement.created_by_user_id,
        "cancelled_by_user_id": pos_settlement.cancelled_by_user_id,
        "cancelled_at": (
            pos_settlement.cancelled_at.isoformat()
            if pos_settlement.cancelled_at
            else None
        ),
        "cancel_reason": pos_settlement.cancel_reason,
    }


def create_pos_settlement(
    session: Session,
    *,
    pos_device_id: int,
    transaction_date: date,
    gross_amount: object,
    reference_no: Optional[str],
    description: Optional[str],
    created_by_user_id: Optional[int] = None,
    acting_user: Optional[Any] = None,
) -> PosSettlement:
    permission_user_id = _require_permission_if_user_given(
        acting_user,
        Permission.POS_SETTLEMENT_CREATE,
        attempted_action="POS_SETTLEMENT_CREATE",
        entity_type="PosSettlement",
        details={
            "pos_device_id": pos_device_id,
            "transaction_date": transaction_date.isoformat() if transaction_date else None,
            "gross_amount": str(gross_amount),
            "reference_no": reference_no,
        },
    )

    effective_user_id = permission_user_id if permission_user_id is not None else created_by_user_id

    pos_device = session.get(PosDevice, pos_device_id)

    if pos_device is None:
        raise PosSettlementServiceError(f"POS cihazı bulunamadı. POS ID: {pos_device_id}")

    if not pos_device.is_active:
        raise PosSettlementServiceError("Pasif POS cihazı için yeni yatış kaydı oluşturulamaz.")

    bank_account = session.get(BankAccount, pos_device.bank_account_id)

    if bank_account is None:
        raise PosSettlementServiceError("POS cihazının bağlı olduğu banka hesabı bulunamadı.")

    if not bank_account.is_active:
        raise PosSettlementServiceError("Pasif banka hesabına bağlı POS cihazı için kayıt oluşturulamaz.")

    bank = session.get(Bank, bank_account.bank_id)

    if bank is None:
        raise PosSettlementServiceError("POS cihazının bağlı olduğu banka bulunamadı.")

    if not bank.is_active:
        raise PosSettlementServiceError("Pasif bankaya bağlı POS cihazı için kayıt oluşturulamaz.")

    cleaned_gross_amount = money(gross_amount, field_name="POS brüt tutarı")

    if cleaned_gross_amount <= Decimal("0.00"):
        raise PosSettlementServiceError("POS brüt tutarı sıfırdan büyük olmalıdır.")

    cleaned_reference_no = _clean_optional_text(reference_no)
    cleaned_description = _clean_optional_text(description)

    normalized_ratio = _normalize_percent_rate_to_ratio(
        Decimal(str(pos_device.commission_rate))
    )

    commission_amount = money(
        cleaned_gross_amount * normalized_ratio,
        field_name="POS komisyon tutarı",
    )

    net_amount = money(
        cleaned_gross_amount - commission_amount,
        field_name="POS net tutarı",
    )

    expected_settlement_date = transaction_date.replace()
    if int(pos_device.settlement_delay_days or 0) > 0:
        from datetime import timedelta

        expected_settlement_date = transaction_date + timedelta(days=int(pos_device.settlement_delay_days or 0))

    pos_settlement = PosSettlement(
        pos_device_id=pos_device.id,
        transaction_date=transaction_date,
        expected_settlement_date=expected_settlement_date,
        realized_settlement_date=None,
        gross_amount=cleaned_gross_amount,
        commission_rate=pos_device.commission_rate,
        commission_amount=commission_amount,
        net_amount=net_amount,
        actual_net_amount=None,
        difference_amount=Decimal("0.00"),
        difference_reason=None,
        currency_code=pos_device.currency_code,
        status=PosSettlementStatus.PLANNED,
        bank_transaction_id=None,
        reference_no=cleaned_reference_no,
        description=cleaned_description,
        created_by_user_id=effective_user_id,
        cancelled_by_user_id=None,
        cancelled_at=None,
        cancel_reason=None,
    )

    session.add(pos_settlement)
    session.flush()

    write_audit_log(
        session,
        user_id=effective_user_id,
        action="POS_SETTLEMENT_CREATED",
        entity_type="PosSettlement",
        entity_id=pos_settlement.id,
        description=f"POS yatış kaydı oluşturuldu. Kayıt ID: {pos_settlement.id}",
        old_values=None,
        new_values=_pos_settlement_to_dict(pos_settlement),
    )

    return pos_settlement


def realize_pos_settlement(
    session: Session,
    *,
    pos_settlement_id: int,
    realized_settlement_date: date,
    actual_net_amount: object,
    difference_reason: Optional[str],
    reference_no: Optional[str],
    description: Optional[str],
    realized_by_user_id: Optional[int] = None,
    acting_user: Optional[Any] = None,
) -> PosSettlement:
    permission_user_id = _require_permission_if_user_given(
        acting_user,
        Permission.POS_SETTLEMENT_REALIZE,
        attempted_action="POS_SETTLEMENT_REALIZE",
        entity_type="PosSettlement",
        entity_id=pos_settlement_id,
        details={
            "pos_settlement_id": pos_settlement_id,
            "realized_settlement_date": realized_settlement_date.isoformat(),
            "actual_net_amount": str(actual_net_amount),
        },
    )

    effective_user_id = permission_user_id if permission_user_id is not None else realized_by_user_id

    pos_settlement = session.get(PosSettlement, pos_settlement_id)

    if pos_settlement is None:
        raise PosSettlementServiceError(f"POS yatış kaydı bulunamadı. Kayıt ID: {pos_settlement_id}")

    if pos_settlement.status != PosSettlementStatus.PLANNED:
        raise PosSettlementServiceError("Sadece planlanan POS yatış kayıtları gerçekleştirilebilir.")

    if pos_settlement.bank_transaction_id is not None:
        raise PosSettlementServiceError("Bu POS kaydı zaten banka hareketine bağlanmış.")

    pos_device = session.get(PosDevice, pos_settlement.pos_device_id)

    if pos_device is None:
        raise PosSettlementServiceError("Bağlı POS cihazı bulunamadı.")

    if not pos_device.is_active:
        raise PosSettlementServiceError("Pasif POS cihazına ait kayıt gerçekleştirilemez.")

    bank_account = session.get(BankAccount, pos_device.bank_account_id)

    if bank_account is None:
        raise PosSettlementServiceError("Bağlı banka hesabı bulunamadı.")

    if not bank_account.is_active:
        raise PosSettlementServiceError("Pasif banka hesabına ait POS kaydı gerçekleştirilemez.")

    bank = session.get(Bank, bank_account.bank_id)

    if bank is None:
        raise PosSettlementServiceError("Bağlı banka bulunamadı.")

    if not bank.is_active:
        raise PosSettlementServiceError("Pasif bankaya ait POS kaydı gerçekleştirilemez.")

    cleaned_actual_net_amount = money(
        actual_net_amount,
        field_name="Gerçekleşen net tutar",
    )

    if cleaned_actual_net_amount <= Decimal("0.00"):
        raise PosSettlementServiceError("Gerçekleşen net tutar sıfırdan büyük olmalıdır.")

    cleaned_reference_no = _clean_optional_text(reference_no)
    cleaned_description = _clean_optional_text(description)
    cleaned_difference_reason = _clean_optional_text(difference_reason)

    difference_amount = money(
        cleaned_actual_net_amount - Decimal(str(pos_settlement.net_amount)),
        field_name="POS fark tutarı",
    )

    if difference_amount != Decimal("0.00") and not cleaned_difference_reason:
        raise PosSettlementServiceError("Tutar farkı varsa fark açıklaması zorunludur.")

    final_status = (
        PosSettlementStatus.REALIZED
        if difference_amount == Decimal("0.00")
        else PosSettlementStatus.MISMATCH
    )

    old_values = _pos_settlement_to_dict(pos_settlement)

    try:
        bank_transaction = create_bank_transaction(
            session,
            bank_account_id=bank_account.id,
            transaction_date=realized_settlement_date,
            value_date=realized_settlement_date,
            direction=TransactionDirection.IN,
            status=BankTransactionStatus.REALIZED,
            amount=cleaned_actual_net_amount,
            currency_code=pos_settlement.currency_code,
            source_type=FinancialSourceType.POS_SETTLEMENT,
            source_id=pos_settlement.id,
            reference_no=cleaned_reference_no or pos_settlement.reference_no,
            description=cleaned_description or pos_settlement.description,
            created_by_user_id=effective_user_id,
            acting_user=acting_user,
        )
    except BankTransactionServiceError as exc:
        raise PosSettlementServiceError(str(exc)) from exc

    pos_settlement.realized_settlement_date = realized_settlement_date
    pos_settlement.actual_net_amount = cleaned_actual_net_amount
    pos_settlement.difference_amount = difference_amount
    pos_settlement.difference_reason = cleaned_difference_reason
    pos_settlement.status = final_status
    pos_settlement.bank_transaction_id = bank_transaction.id
    pos_settlement.reference_no = cleaned_reference_no or pos_settlement.reference_no
    pos_settlement.description = cleaned_description or pos_settlement.description

    session.flush()

    audit_action = (
        "POS_SETTLEMENT_REALIZED"
        if final_status == PosSettlementStatus.REALIZED
        else "POS_SETTLEMENT_MISMATCH"
    )

    audit_description = (
        f"POS yatış kaydı gerçekleştirildi. Kayıt ID: {pos_settlement.id}"
        if final_status == PosSettlementStatus.REALIZED
        else f"POS yatış kaydı fark ile gerçekleşti. Kayıt ID: {pos_settlement.id}"
    )

    write_audit_log(
        session,
        user_id=effective_user_id,
        action=audit_action,
        entity_type="PosSettlement",
        entity_id=pos_settlement.id,
        description=audit_description,
        old_values=old_values,
        new_values=_pos_settlement_to_dict(pos_settlement),
    )

    return pos_settlement


def cancel_pos_settlement(
    session: Session,
    *,
    pos_settlement_id: int,
    cancel_reason: str,
    cancelled_by_user_id: Optional[int] = None,
    acting_user: Optional[Any] = None,
) -> PosSettlement:
    permission_user_id = _require_permission_if_user_given(
        acting_user,
        Permission.POS_SETTLEMENT_CANCEL,
        attempted_action="POS_SETTLEMENT_CANCEL",
        entity_type="PosSettlement",
        entity_id=pos_settlement_id,
        details={
            "pos_settlement_id": pos_settlement_id,
            "cancel_reason": cancel_reason,
        },
    )

    effective_user_id = permission_user_id if permission_user_id is not None else cancelled_by_user_id

    pos_settlement = session.get(PosSettlement, pos_settlement_id)

    if pos_settlement is None:
        raise PosSettlementServiceError(f"POS yatış kaydı bulunamadı. Kayıt ID: {pos_settlement_id}")

    if pos_settlement.status != PosSettlementStatus.PLANNED:
        raise PosSettlementServiceError("Bu adımda sadece planlanan POS kayıtları iptal edilebilir.")

    if pos_settlement.bank_transaction_id is not None:
        raise PosSettlementServiceError("Banka hareketine bağlanmış POS kaydı bu adımda iptal edilemez.")

    cleaned_cancel_reason = _clean_required_text(cancel_reason, "İptal nedeni")

    if len(cleaned_cancel_reason) < 5:
        raise PosSettlementServiceError("İptal nedeni daha açıklayıcı olmalıdır.")

    old_values = _pos_settlement_to_dict(pos_settlement)

    pos_settlement.status = PosSettlementStatus.CANCELLED
    pos_settlement.cancel_reason = cleaned_cancel_reason
    pos_settlement.cancelled_by_user_id = effective_user_id
    pos_settlement.cancelled_at = datetime.now()

    session.flush()

    write_audit_log(
        session,
        user_id=effective_user_id,
        action="POS_SETTLEMENT_CANCELLED",
        entity_type="PosSettlement",
        entity_id=pos_settlement.id,
        description=f"POS kaydı iptal edildi. Kayıt ID: {pos_settlement.id}",
        old_values=old_values,
        new_values=_pos_settlement_to_dict(pos_settlement),
    )

    return pos_settlement