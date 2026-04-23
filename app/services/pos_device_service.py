from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.bank import Bank, BankAccount
from app.models.enums import CurrencyCode, PosSettlementStatus
from app.models.pos import PosDevice, PosSettlement
from app.services.audit_service import write_audit_log
from app.services.permission_audit_service import require_permission_with_audit
from app.services.permission_service import Permission, PermissionServiceError
from app.utils.decimal_utils import rate


class PosDeviceServiceError(ValueError):
    pass


def _clean_optional_text(value: Optional[str]) -> Optional[str]:
    cleaned_value = (value or "").strip()

    if not cleaned_value:
        return None

    return cleaned_value


def _clean_required_text(value: Optional[str], field_name: str) -> str:
    cleaned_value = (value or "").strip()

    if not cleaned_value:
        raise PosDeviceServiceError(f"{field_name} boş olamaz.")

    return cleaned_value


def _normalize_currency_code(value: CurrencyCode | str) -> CurrencyCode:
    if isinstance(value, CurrencyCode):
        return value

    try:
        return CurrencyCode(str(value).strip().upper())
    except ValueError as exc:
        raise PosDeviceServiceError(f"Geçersiz para birimi: {value}") from exc


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
        raise PosDeviceServiceError(str(exc)) from exc


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


def _same_name_exists_on_account(
    session: Session,
    *,
    bank_account_id: int,
    name: str,
    exclude_pos_device_id: Optional[int] = None,
) -> bool:
    statement = select(PosDevice).where(
        PosDevice.bank_account_id == bank_account_id,
        func.lower(PosDevice.name) == name.lower(),
    )

    if exclude_pos_device_id is not None:
        statement = statement.where(PosDevice.id != exclude_pos_device_id)

    return session.execute(statement).scalar_one_or_none() is not None


def _same_terminal_exists_on_account(
    session: Session,
    *,
    bank_account_id: int,
    terminal_no: Optional[str],
    exclude_pos_device_id: Optional[int] = None,
) -> bool:
    if not terminal_no:
        return False

    statement = select(PosDevice).where(
        PosDevice.bank_account_id == bank_account_id,
        func.lower(PosDevice.terminal_no) == terminal_no.lower(),
    )

    if exclude_pos_device_id is not None:
        statement = statement.where(PosDevice.id != exclude_pos_device_id)

    return session.execute(statement).scalar_one_or_none() is not None


def _has_open_settlements(
    session: Session,
    *,
    pos_device_id: int,
) -> bool:
    statement = (
        select(func.count(PosSettlement.id))
        .where(PosSettlement.pos_device_id == pos_device_id)
        .where(
            PosSettlement.status.in_(
                [
                    PosSettlementStatus.PLANNED,
                    PosSettlementStatus.MISMATCH,
                ]
            )
        )
    )

    return int(session.execute(statement).scalar_one() or 0) > 0


def create_pos_device(
    session: Session,
    *,
    bank_account_id: int,
    name: str,
    terminal_no: Optional[str],
    commission_rate: object,
    settlement_delay_days: int,
    currency_code: CurrencyCode | str,
    notes: Optional[str],
    created_by_user_id: Optional[int] = None,
    acting_user: Optional[Any] = None,
) -> PosDevice:
    permission_user_id = _require_permission_if_user_given(
        acting_user,
        Permission.POS_DEVICE_CREATE,
        attempted_action="POS_DEVICE_CREATE",
        entity_type="PosDevice",
        details={
            "bank_account_id": bank_account_id,
            "name": name,
            "terminal_no": terminal_no,
            "currency_code": str(currency_code),
        },
    )

    effective_user_id = permission_user_id if permission_user_id is not None else created_by_user_id

    bank_account = session.get(BankAccount, bank_account_id)

    if bank_account is None:
        raise PosDeviceServiceError(f"Banka hesabı bulunamadı. Hesap ID: {bank_account_id}")

    if not bank_account.is_active:
        raise PosDeviceServiceError("Pasif banka hesabına POS cihazı bağlanamaz.")

    bank = session.get(Bank, bank_account.bank_id)

    if bank is None:
        raise PosDeviceServiceError("POS cihazının bağlı olacağı banka bulunamadı.")

    if not bank.is_active:
        raise PosDeviceServiceError("Pasif bankaya POS cihazı bağlanamaz.")

    cleaned_name = _clean_required_text(name, "POS cihaz adı")
    cleaned_terminal_no = _clean_optional_text(terminal_no)
    cleaned_commission_rate = rate(commission_rate, field_name="Komisyon oranı")
    cleaned_currency_code = _normalize_currency_code(currency_code)
    cleaned_notes = _clean_optional_text(notes)

    try:
        normalized_delay_days = int(settlement_delay_days)
    except (TypeError, ValueError) as exc:
        raise PosDeviceServiceError("Valör gün sayısı sayısal olmalıdır.") from exc

    if normalized_delay_days < 0:
        raise PosDeviceServiceError("Valör gün sayısı negatif olamaz.")

    if normalized_delay_days > 60:
        raise PosDeviceServiceError("Valör gün sayısı en fazla 60 olabilir.")

    if cleaned_commission_rate < 0:
        raise PosDeviceServiceError("Komisyon oranı negatif olamaz.")

    if cleaned_commission_rate > 100:
        raise PosDeviceServiceError("Komisyon oranı 100'den büyük olamaz.")

    if cleaned_currency_code != bank_account.currency_code:
        raise PosDeviceServiceError(
            "POS cihazı para birimi, bağlı banka hesabının para birimi ile aynı olmalıdır."
        )

    if _same_name_exists_on_account(
        session,
        bank_account_id=bank_account.id,
        name=cleaned_name,
    ):
        raise PosDeviceServiceError("Bu banka hesabında aynı POS cihaz adı zaten kullanılıyor.")

    if _same_terminal_exists_on_account(
        session,
        bank_account_id=bank_account.id,
        terminal_no=cleaned_terminal_no,
    ):
        raise PosDeviceServiceError("Bu banka hesabında aynı terminal numarası zaten kullanılıyor.")

    pos_device = PosDevice(
        bank_account_id=bank_account.id,
        name=cleaned_name,
        terminal_no=cleaned_terminal_no,
        commission_rate=cleaned_commission_rate,
        settlement_delay_days=normalized_delay_days,
        currency_code=cleaned_currency_code,
        notes=cleaned_notes,
        is_active=True,
    )

    session.add(pos_device)

    try:
        session.flush()
    except IntegrityError as exc:
        raise PosDeviceServiceError("POS cihazı oluşturulamadı. Aynı terminal numarası zaten kayıtlı olabilir.") from exc

    write_audit_log(
        session,
        user_id=effective_user_id,
        action="POS_DEVICE_CREATED",
        entity_type="PosDevice",
        entity_id=pos_device.id,
        description=f"POS cihazı oluşturuldu: {pos_device.name}",
        old_values=None,
        new_values=_pos_device_to_dict(pos_device),
    )

    return pos_device


def update_pos_device(
    session: Session,
    *,
    pos_device_id: int,
    bank_account_id: int,
    name: str,
    terminal_no: Optional[str],
    commission_rate: object,
    settlement_delay_days: int,
    currency_code: CurrencyCode | str,
    notes: Optional[str],
    is_active: bool,
    updated_by_user_id: Optional[int] = None,
    acting_user: Optional[Any] = None,
) -> PosDevice:
    permission_user_id = _require_permission_if_user_given(
        acting_user,
        Permission.POS_DEVICE_UPDATE,
        attempted_action="POS_DEVICE_UPDATE",
        entity_type="PosDevice",
        entity_id=pos_device_id,
        details={
            "pos_device_id": pos_device_id,
            "bank_account_id": bank_account_id,
            "name": name,
            "terminal_no": terminal_no,
            "currency_code": str(currency_code),
            "is_active": is_active,
        },
    )

    effective_user_id = permission_user_id if permission_user_id is not None else updated_by_user_id

    pos_device = session.get(PosDevice, pos_device_id)

    if pos_device is None:
        raise PosDeviceServiceError(f"POS cihazı bulunamadı. POS ID: {pos_device_id}")

    bank_account = session.get(BankAccount, bank_account_id)

    if bank_account is None:
        raise PosDeviceServiceError(f"Banka hesabı bulunamadı. Hesap ID: {bank_account_id}")

    if not bank_account.is_active:
        raise PosDeviceServiceError("Pasif banka hesabına POS cihazı bağlanamaz.")

    bank = session.get(Bank, bank_account.bank_id)

    if bank is None:
        raise PosDeviceServiceError("POS cihazının bağlı olacağı banka bulunamadı.")

    if not bank.is_active:
        raise PosDeviceServiceError("Pasif bankaya POS cihazı bağlanamaz.")

    cleaned_name = _clean_required_text(name, "POS cihaz adı")
    cleaned_terminal_no = _clean_optional_text(terminal_no)
    cleaned_commission_rate = rate(commission_rate, field_name="Komisyon oranı")
    cleaned_currency_code = _normalize_currency_code(currency_code)
    cleaned_notes = _clean_optional_text(notes)

    try:
        normalized_delay_days = int(settlement_delay_days)
    except (TypeError, ValueError) as exc:
        raise PosDeviceServiceError("Valör gün sayısı sayısal olmalıdır.") from exc

    if normalized_delay_days < 0:
        raise PosDeviceServiceError("Valör gün sayısı negatif olamaz.")

    if normalized_delay_days > 60:
        raise PosDeviceServiceError("Valör gün sayısı en fazla 60 olabilir.")

    if cleaned_commission_rate < 0:
        raise PosDeviceServiceError("Komisyon oranı negatif olamaz.")

    if cleaned_commission_rate > 100:
        raise PosDeviceServiceError("Komisyon oranı 100'den büyük olamaz.")

    if cleaned_currency_code != bank_account.currency_code:
        raise PosDeviceServiceError(
            "POS cihazı para birimi, bağlı banka hesabının para birimi ile aynı olmalıdır."
        )

    if _same_name_exists_on_account(
        session,
        bank_account_id=bank_account.id,
        name=cleaned_name,
        exclude_pos_device_id=pos_device.id,
    ):
        raise PosDeviceServiceError("Bu banka hesabında aynı POS cihaz adı başka bir kayıtta kullanılıyor.")

    if _same_terminal_exists_on_account(
        session,
        bank_account_id=bank_account.id,
        terminal_no=cleaned_terminal_no,
        exclude_pos_device_id=pos_device.id,
    ):
        raise PosDeviceServiceError("Bu banka hesabında aynı terminal numarası başka bir kayıtta kullanılıyor.")

    old_values = _pos_device_to_dict(pos_device)

    pos_device.bank_account_id = bank_account.id
    pos_device.name = cleaned_name
    pos_device.terminal_no = cleaned_terminal_no
    pos_device.commission_rate = cleaned_commission_rate
    pos_device.settlement_delay_days = normalized_delay_days
    pos_device.currency_code = cleaned_currency_code
    pos_device.notes = cleaned_notes
    pos_device.is_active = bool(is_active)

    try:
        session.flush()
    except IntegrityError as exc:
        raise PosDeviceServiceError("POS cihazı güncellenemedi. Aynı terminal numarası zaten kullanılıyor olabilir.") from exc

    write_audit_log(
        session,
        user_id=effective_user_id,
        action="POS_DEVICE_UPDATED",
        entity_type="PosDevice",
        entity_id=pos_device.id,
        description=f"POS cihazı güncellendi: {pos_device.name}",
        old_values=old_values,
        new_values=_pos_device_to_dict(pos_device),
    )

    return pos_device


def deactivate_pos_device(
    session: Session,
    *,
    pos_device_id: int,
    deactivate_reason: str,
    deactivated_by_user_id: Optional[int] = None,
    acting_user: Optional[Any] = None,
) -> PosDevice:
    permission_user_id = _require_permission_if_user_given(
        acting_user,
        Permission.POS_DEVICE_DEACTIVATE,
        attempted_action="POS_DEVICE_DEACTIVATE",
        entity_type="PosDevice",
        entity_id=pos_device_id,
        details={
            "pos_device_id": pos_device_id,
            "deactivate_reason": deactivate_reason,
        },
    )

    effective_user_id = permission_user_id if permission_user_id is not None else deactivated_by_user_id

    cleaned_reason = _clean_required_text(deactivate_reason, "Pasifleştirme nedeni")

    if len(cleaned_reason) < 5:
        raise PosDeviceServiceError("Pasifleştirme nedeni daha açıklayıcı olmalıdır.")

    pos_device = session.get(PosDevice, pos_device_id)

    if pos_device is None:
        raise PosDeviceServiceError(f"POS cihazı bulunamadı. POS ID: {pos_device_id}")

    if not pos_device.is_active:
        raise PosDeviceServiceError("Bu POS cihazı zaten pasif durumda.")

    if _has_open_settlements(session, pos_device_id=pos_device.id):
        raise PosDeviceServiceError(
            "Açık planlanan veya fark içeren mutabakat kaydı olan POS cihazı pasifleştirilemez."
        )

    old_values = _pos_device_to_dict(pos_device)

    pos_device.is_active = False
    pos_device.notes = (
        f"{pos_device.notes}\n\nPasifleştirme nedeni: {cleaned_reason}"
        if pos_device.notes
        else f"Pasifleştirme nedeni: {cleaned_reason}"
    )

    session.flush()

    write_audit_log(
        session,
        user_id=effective_user_id,
        action="POS_DEVICE_DEACTIVATED",
        entity_type="PosDevice",
        entity_id=pos_device.id,
        description=f"POS cihazı pasifleştirildi: {pos_device.name}",
        old_values=old_values,
        new_values=_pos_device_to_dict(pos_device),
    )

    return pos_device


def reactivate_pos_device(
    session: Session,
    *,
    pos_device_id: int,
    reactivate_reason: str,
    reactivated_by_user_id: Optional[int] = None,
    acting_user: Optional[Any] = None,
) -> PosDevice:
    permission_user_id = _require_permission_if_user_given(
        acting_user,
        Permission.POS_DEVICE_REACTIVATE,
        attempted_action="POS_DEVICE_REACTIVATE",
        entity_type="PosDevice",
        entity_id=pos_device_id,
        details={
            "pos_device_id": pos_device_id,
            "reactivate_reason": reactivate_reason,
        },
    )

    effective_user_id = permission_user_id if permission_user_id is not None else reactivated_by_user_id

    cleaned_reason = _clean_required_text(reactivate_reason, "Aktifleştirme nedeni")

    if len(cleaned_reason) < 5:
        raise PosDeviceServiceError("Aktifleştirme nedeni daha açıklayıcı olmalıdır.")

    pos_device = session.get(PosDevice, pos_device_id)

    if pos_device is None:
        raise PosDeviceServiceError(f"POS cihazı bulunamadı. POS ID: {pos_device_id}")

    if pos_device.is_active:
        raise PosDeviceServiceError("Bu POS cihazı zaten aktif durumda.")

    bank_account = session.get(BankAccount, pos_device.bank_account_id)

    if bank_account is None:
        raise PosDeviceServiceError("POS cihazının bağlı olduğu banka hesabı bulunamadı.")

    if not bank_account.is_active:
        raise PosDeviceServiceError("Pasif banka hesabına bağlı POS cihazı aktifleştirilemez.")

    bank = session.get(Bank, bank_account.bank_id)

    if bank is None:
        raise PosDeviceServiceError("POS cihazının bağlı olduğu banka bulunamadı.")

    if not bank.is_active:
        raise PosDeviceServiceError("Pasif bankaya bağlı POS cihazı aktifleştirilemez.")

    old_values = _pos_device_to_dict(pos_device)

    pos_device.is_active = True
    pos_device.notes = (
        f"{pos_device.notes}\n\nAktifleştirme nedeni: {cleaned_reason}"
        if pos_device.notes
        else f"Aktifleştirme nedeni: {cleaned_reason}"
    )

    session.flush()

    write_audit_log(
        session,
        user_id=effective_user_id,
        action="POS_DEVICE_REACTIVATED",
        entity_type="PosDevice",
        entity_id=pos_device.id,
        description=f"POS cihazı tekrar aktifleştirildi: {pos_device.name}",
        old_values=old_values,
        new_values=_pos_device_to_dict(pos_device),
    )

    return pos_device