from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.bank import BankAccount
from app.models.pos import PosDevice, PosSettlement
from app.models.enums import (
    BankTransactionStatus,
    FinancialSourceType,
    PosSettlementStatus,
    TransactionDirection,
)
from app.services.audit_service import write_audit_log
from app.services.bank_transaction_service import (
    BankTransactionServiceError,
    create_bank_transaction,
)
from app.services.permission_audit_service import require_permission_with_audit
from app.services.permission_service import Permission, PermissionServiceError
from app.utils.decimal_utils import money, rate


class PosServiceError(ValueError):
    pass


def _clean_required_text(value: str, field_name: str) -> str:
    cleaned_value = (value or "").strip()

    if not cleaned_value:
        raise PosServiceError(f"{field_name} boş olamaz.")

    return cleaned_value


def _clean_optional_text(value: Optional[str]) -> Optional[str]:
    cleaned_value = (value or "").strip()

    if not cleaned_value:
        return None

    return cleaned_value


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
        raise PosServiceError(str(exc)) from exc


def _validate_commission_rate(value: object) -> Decimal:
    cleaned_rate = rate(value, field_name="Komisyon oranı")

    if cleaned_rate < Decimal("0.000000"):
        raise PosServiceError("Komisyon oranı negatif olamaz.")

    if cleaned_rate > Decimal("100.000000"):
        raise PosServiceError("Komisyon oranı 100'den büyük olamaz.")

    return cleaned_rate


def _validate_settlement_delay_days(value: object) -> int:
    try:
        delay_days = int(value)
    except (TypeError, ValueError) as exc:
        raise PosServiceError("Hesaba geçiş günü sayısal olmalıdır.") from exc

    if delay_days < 0:
        raise PosServiceError("Hesaba geçiş günü negatif olamaz.")

    return delay_days


def _validate_positive_money(value: object, field_name: str) -> Decimal:
    cleaned_amount = money(value, field_name=field_name)

    if cleaned_amount <= Decimal("0.00"):
        raise PosServiceError(f"{field_name} sıfırdan büyük olmalıdır.")

    return cleaned_amount


def calculate_pos_commission_amount(
    *,
    gross_amount: object,
    commission_rate: object,
) -> Decimal:
    cleaned_gross_amount = _validate_positive_money(gross_amount, "Brüt POS tutarı")
    cleaned_commission_rate = _validate_commission_rate(commission_rate)

    commission_amount = cleaned_gross_amount * cleaned_commission_rate / Decimal("100")

    return money(commission_amount, field_name="POS komisyon tutarı")


def calculate_pos_net_amount(
    *,
    gross_amount: object,
    commission_rate: object,
) -> Decimal:
    cleaned_gross_amount = _validate_positive_money(gross_amount, "Brüt POS tutarı")
    commission_amount = calculate_pos_commission_amount(
        gross_amount=cleaned_gross_amount,
        commission_rate=commission_rate,
    )

    net_amount = cleaned_gross_amount - commission_amount

    return money(net_amount, field_name="Net POS yatış tutarı")


def _pos_device_to_dict(pos_device: PosDevice) -> dict[str, Any]:
    return {
        "id": pos_device.id,
        "bank_account_id": pos_device.bank_account_id,
        "name": pos_device.name,
        "terminal_no": pos_device.terminal_no,
        "commission_rate": str(pos_device.commission_rate),
        "settlement_delay_days": pos_device.settlement_delay_days,
        "currency_code": pos_device.currency_code.value,
        "notes": pos_device.notes,
        "is_active": pos_device.is_active,
    }


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
        "actual_net_amount": str(pos_settlement.actual_net_amount) if pos_settlement.actual_net_amount is not None else None,
        "difference_amount": str(pos_settlement.difference_amount),
        "difference_reason": pos_settlement.difference_reason,
        "currency_code": pos_settlement.currency_code.value,
        "status": pos_settlement.status.value,
        "bank_transaction_id": pos_settlement.bank_transaction_id,
        "reference_no": pos_settlement.reference_no,
        "description": pos_settlement.description,
        "created_by_user_id": pos_settlement.created_by_user_id,
        "cancelled_by_user_id": pos_settlement.cancelled_by_user_id,
        "cancelled_at": pos_settlement.cancelled_at.isoformat() if pos_settlement.cancelled_at else None,
        "cancel_reason": pos_settlement.cancel_reason,
    }


def get_pos_device_by_name(
    session: Session,
    *,
    bank_account_id: int,
    name: str,
) -> Optional[PosDevice]:
    cleaned_name = _clean_required_text(name, "POS adı")

    statement = select(PosDevice).where(
        PosDevice.bank_account_id == bank_account_id,
        PosDevice.name == cleaned_name,
    )

    return session.execute(statement).scalar_one_or_none()


def get_pos_device_by_terminal_no(
    session: Session,
    *,
    bank_account_id: int,
    terminal_no: Optional[str],
) -> Optional[PosDevice]:
    cleaned_terminal_no = _clean_optional_text(terminal_no)

    if cleaned_terminal_no is None:
        return None

    statement = select(PosDevice).where(
        PosDevice.bank_account_id == bank_account_id,
        PosDevice.terminal_no == cleaned_terminal_no,
    )

    return session.execute(statement).scalar_one_or_none()


def create_pos_device(
    session: Session,
    *,
    bank_account_id: int,
    name: str,
    terminal_no: Optional[str],
    commission_rate: object,
    settlement_delay_days: object,
    notes: Optional[str],
    created_by_user_id: Optional[int],
) -> PosDevice:
    bank_account = session.get(BankAccount, bank_account_id)

    if bank_account is None:
        raise PosServiceError(f"Banka hesabı bulunamadı. Hesap ID: {bank_account_id}")

    if not bank_account.is_active:
        raise PosServiceError("Pasif banka hesabına POS cihazı bağlanamaz.")

    cleaned_name = _clean_required_text(name, "POS adı")
    cleaned_terminal_no = _clean_optional_text(terminal_no)
    cleaned_commission_rate = _validate_commission_rate(commission_rate)
    cleaned_settlement_delay_days = _validate_settlement_delay_days(settlement_delay_days)
    cleaned_notes = _clean_optional_text(notes)

    existing_by_name = get_pos_device_by_name(
        session,
        bank_account_id=bank_account.id,
        name=cleaned_name,
    )

    if existing_by_name is not None:
        raise PosServiceError(f"Bu banka hesabında aynı POS adı zaten kayıtlı: {cleaned_name}")

    existing_by_terminal = get_pos_device_by_terminal_no(
        session,
        bank_account_id=bank_account.id,
        terminal_no=cleaned_terminal_no,
    )

    if existing_by_terminal is not None:
        raise PosServiceError(f"Bu banka hesabında aynı terminal no zaten kayıtlı: {cleaned_terminal_no}")

    pos_device = PosDevice(
        bank_account_id=bank_account.id,
        name=cleaned_name,
        terminal_no=cleaned_terminal_no,
        commission_rate=cleaned_commission_rate,
        settlement_delay_days=cleaned_settlement_delay_days,
        currency_code=bank_account.currency_code,
        notes=cleaned_notes,
        is_active=True,
    )

    session.add(pos_device)
    session.flush()

    write_audit_log(
        session,
        user_id=created_by_user_id,
        action="POS_DEVICE_CREATED",
        entity_type="PosDevice",
        entity_id=pos_device.id,
        description=f"POS cihazı oluşturuldu: {pos_device.name}",
        old_values=None,
        new_values=_pos_device_to_dict(pos_device),
    )

    return pos_device


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
            "transaction_date": transaction_date.isoformat(),
            "gross_amount": str(gross_amount),
        },
    )

    effective_created_by_user_id = permission_user_id if permission_user_id is not None else created_by_user_id

    pos_device = session.get(PosDevice, pos_device_id)

    if pos_device is None:
        raise PosServiceError(f"POS cihazı bulunamadı. POS ID: {pos_device_id}")

    if not pos_device.is_active:
        raise PosServiceError("Pasif POS cihazına POS yatış kaydı girilemez.")

    bank_account = session.get(BankAccount, pos_device.bank_account_id)

    if bank_account is None:
        raise PosServiceError(
            f"POS cihazının bağlı olduğu banka hesabı bulunamadı. Hesap ID: {pos_device.bank_account_id}"
        )

    if not bank_account.is_active:
        raise PosServiceError("POS cihazının bağlı olduğu banka hesabı pasif durumda.")

    cleaned_gross_amount = _validate_positive_money(gross_amount, "Brüt POS tutarı")
    cleaned_commission_rate = _validate_commission_rate(pos_device.commission_rate)

    cleaned_commission_amount = calculate_pos_commission_amount(
        gross_amount=cleaned_gross_amount,
        commission_rate=cleaned_commission_rate,
    )

    cleaned_net_amount = calculate_pos_net_amount(
        gross_amount=cleaned_gross_amount,
        commission_rate=cleaned_commission_rate,
    )

    expected_settlement_date = transaction_date + timedelta(days=pos_device.settlement_delay_days)

    cleaned_reference_no = _clean_optional_text(reference_no)
    cleaned_description = _clean_optional_text(description)

    pos_settlement = PosSettlement(
        pos_device_id=pos_device.id,
        transaction_date=transaction_date,
        expected_settlement_date=expected_settlement_date,
        realized_settlement_date=None,
        gross_amount=cleaned_gross_amount,
        commission_rate=cleaned_commission_rate,
        commission_amount=cleaned_commission_amount,
        net_amount=cleaned_net_amount,
        actual_net_amount=None,
        difference_amount=Decimal("0.00"),
        difference_reason=None,
        currency_code=pos_device.currency_code,
        status=PosSettlementStatus.PLANNED,
        bank_transaction_id=None,
        reference_no=cleaned_reference_no,
        description=cleaned_description,
        created_by_user_id=effective_created_by_user_id,
    )

    session.add(pos_settlement)
    session.flush()

    write_audit_log(
        session,
        user_id=effective_created_by_user_id,
        action="POS_SETTLEMENT_CREATED",
        entity_type="PosSettlement",
        entity_id=pos_settlement.id,
        description=(
            f"POS yatış kaydı oluşturuldu: "
            f"{pos_device.name} / Brüt {pos_settlement.gross_amount} "
            f"Net {pos_settlement.net_amount} {pos_settlement.currency_code.value}"
        ),
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
        details={
            "pos_settlement_id": pos_settlement_id,
            "realized_settlement_date": realized_settlement_date.isoformat(),
            "actual_net_amount": str(actual_net_amount),
            "difference_reason": difference_reason,
        },
    )

    effective_realized_by_user_id = permission_user_id if permission_user_id is not None else realized_by_user_id

    pos_settlement = session.get(PosSettlement, pos_settlement_id)

    if pos_settlement is None:
        raise PosServiceError(f"POS yatış kaydı bulunamadı. POS yatış ID: {pos_settlement_id}")

    if pos_settlement.status == PosSettlementStatus.REALIZED:
        raise PosServiceError("Bu POS yatışı zaten gerçekleşmiş.")

    if pos_settlement.status == PosSettlementStatus.MISMATCH:
        raise PosServiceError("Bu POS yatışı zaten fark ile işlenmiş.")

    if pos_settlement.status == PosSettlementStatus.CANCELLED:
        raise PosServiceError("İptal edilmiş POS yatışı gerçekleşti yapılamaz.")

    if pos_settlement.bank_transaction_id is not None:
        raise PosServiceError("Bu POS yatışına bağlı banka hareketi zaten var.")

    pos_device = session.get(PosDevice, pos_settlement.pos_device_id)

    if pos_device is None:
        raise PosServiceError(f"POS cihazı bulunamadı. POS ID: {pos_settlement.pos_device_id}")

    bank_account = session.get(BankAccount, pos_device.bank_account_id)

    if bank_account is None:
        raise PosServiceError(
            f"POS cihazının bağlı olduğu banka hesabı bulunamadı. Hesap ID: {pos_device.bank_account_id}"
        )

    if not bank_account.is_active:
        raise PosServiceError("POS cihazının bağlı olduğu banka hesabı pasif durumda.")

    if bank_account.currency_code != pos_settlement.currency_code:
        raise PosServiceError(
            f"POS para birimi ile banka hesabı para birimi aynı olmalıdır. "
            f"POS: {pos_settlement.currency_code.value}, Hesap: {bank_account.currency_code.value}"
        )

    cleaned_actual_net_amount = _validate_positive_money(actual_net_amount, "Gerçek yatan POS tutarı")
    cleaned_reference_no = _clean_optional_text(reference_no) or pos_settlement.reference_no
    cleaned_description = _clean_optional_text(description)
    cleaned_difference_reason = _clean_optional_text(difference_reason)

    difference_amount = money(
        cleaned_actual_net_amount - pos_settlement.net_amount,
        field_name="POS yatış farkı",
    )

    if difference_amount != Decimal("0.00") and cleaned_difference_reason is None:
        raise PosServiceError("POS yatış farkı varsa fark nedeni yazılmalıdır.")

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
            reference_no=cleaned_reference_no,
            description=(
                f"POS yatışı: {pos_device.name}"
                if not cleaned_description
                else f"POS yatışı: {pos_device.name} - {cleaned_description}"
            ),
            created_by_user_id=effective_realized_by_user_id,
        )
    except BankTransactionServiceError as exc:
        raise PosServiceError(f"POS yatışı banka hareketi oluşturulamadı: {exc}") from exc

    pos_settlement.realized_settlement_date = realized_settlement_date
    pos_settlement.actual_net_amount = cleaned_actual_net_amount
    pos_settlement.difference_amount = difference_amount
    pos_settlement.difference_reason = cleaned_difference_reason
    pos_settlement.bank_transaction_id = bank_transaction.id

    if difference_amount == Decimal("0.00"):
        pos_settlement.status = PosSettlementStatus.REALIZED
    else:
        pos_settlement.status = PosSettlementStatus.MISMATCH

    session.flush()

    write_audit_log(
        session,
        user_id=effective_realized_by_user_id,
        action="POS_SETTLEMENT_REALIZED",
        entity_type="PosSettlement",
        entity_id=pos_settlement.id,
        description=(
            f"POS yatışı gerçekleşti: "
            f"{pos_device.name} / Beklenen {pos_settlement.net_amount} "
            f"Gerçek {pos_settlement.actual_net_amount} "
            f"Fark {pos_settlement.difference_amount} {pos_settlement.currency_code.value}"
        ),
        old_values=old_values,
        new_values=_pos_settlement_to_dict(pos_settlement),
    )

    return pos_settlement