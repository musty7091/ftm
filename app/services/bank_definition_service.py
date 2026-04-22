from datetime import date
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.bank import Bank, BankAccount
from app.models.bank_transaction import BankTransaction
from app.models.enums import BankAccountType, CurrencyCode
from app.services.audit_service import write_audit_log
from app.services.bank_transaction_service import get_bank_account_balance_summary
from app.services.permission_audit_service import require_permission_with_audit
from app.services.permission_service import Permission, PermissionServiceError
from app.utils.decimal_utils import money


class BankDefinitionServiceError(ValueError):
    pass


def _clean_optional_text(value: Optional[str]) -> Optional[str]:
    cleaned_value = (value or "").strip()

    if not cleaned_value:
        return None

    return cleaned_value


def _clean_required_text(value: Optional[str], field_name: str) -> str:
    cleaned_value = (value or "").strip()

    if not cleaned_value:
        raise BankDefinitionServiceError(f"{field_name} boş olamaz.")

    return cleaned_value


def _normalize_bank_account_type(value: BankAccountType | str) -> BankAccountType:
    if isinstance(value, BankAccountType):
        return value

    try:
        return BankAccountType(str(value).strip().upper())
    except ValueError as exc:
        raise BankDefinitionServiceError(f"Geçersiz hesap türü: {value}") from exc


def _normalize_currency_code(value: CurrencyCode | str) -> CurrencyCode:
    if isinstance(value, CurrencyCode):
        return value

    try:
        return CurrencyCode(str(value).strip().upper())
    except ValueError as exc:
        raise BankDefinitionServiceError(f"Geçersiz para birimi: {value}") from exc


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
        raise BankDefinitionServiceError(str(exc)) from exc


def _bank_to_dict(bank: Bank) -> dict[str, Any]:
    return {
        "id": bank.id,
        "name": bank.name,
        "short_name": bank.short_name,
        "notes": bank.notes,
        "is_active": bank.is_active,
    }


def _bank_account_to_dict(bank_account: BankAccount) -> dict[str, Any]:
    return {
        "id": bank_account.id,
        "bank_id": bank_account.bank_id,
        "account_name": bank_account.account_name,
        "account_type": bank_account.account_type.value,
        "currency_code": bank_account.currency_code.value,
        "iban": bank_account.iban,
        "branch_name": bank_account.branch_name,
        "branch_code": bank_account.branch_code,
        "account_no": bank_account.account_no,
        "opening_balance": str(bank_account.opening_balance),
        "opening_date": bank_account.opening_date.isoformat() if bank_account.opening_date else None,
        "notes": bank_account.notes,
        "is_active": bank_account.is_active,
    }


def _bank_has_same_name(
    session: Session,
    *,
    name: str,
    exclude_bank_id: Optional[int] = None,
) -> bool:
    statement = select(Bank).where(func.lower(Bank.name) == name.lower())

    if exclude_bank_id is not None:
        statement = statement.where(Bank.id != exclude_bank_id)

    return session.execute(statement).scalar_one_or_none() is not None


def _bank_has_same_short_name(
    session: Session,
    *,
    short_name: Optional[str],
    exclude_bank_id: Optional[int] = None,
) -> bool:
    if not short_name:
        return False

    statement = select(Bank).where(func.lower(Bank.short_name) == short_name.lower())

    if exclude_bank_id is not None:
        statement = statement.where(Bank.id != exclude_bank_id)

    return session.execute(statement).scalar_one_or_none() is not None


def _bank_account_has_same_name(
    session: Session,
    *,
    bank_id: int,
    account_name: str,
    exclude_bank_account_id: Optional[int] = None,
) -> bool:
    statement = select(BankAccount).where(
        BankAccount.bank_id == bank_id,
        func.lower(BankAccount.account_name) == account_name.lower(),
    )

    if exclude_bank_account_id is not None:
        statement = statement.where(BankAccount.id != exclude_bank_account_id)

    return session.execute(statement).scalar_one_or_none() is not None


def _iban_exists(
    session: Session,
    *,
    iban: Optional[str],
    exclude_bank_account_id: Optional[int] = None,
) -> bool:
    if not iban:
        return False

    statement = select(BankAccount).where(func.lower(BankAccount.iban) == iban.lower())

    if exclude_bank_account_id is not None:
        statement = statement.where(BankAccount.id != exclude_bank_account_id)

    return session.execute(statement).scalar_one_or_none() is not None


def _bank_account_has_transactions(
    session: Session,
    *,
    bank_account_id: int,
) -> bool:
    statement = (
        select(func.count(BankTransaction.id))
        .where(BankTransaction.bank_account_id == bank_account_id)
    )

    return int(session.execute(statement).scalar_one() or 0) > 0


def create_bank(
    session: Session,
    *,
    name: str,
    short_name: Optional[str],
    notes: Optional[str],
    created_by_user_id: Optional[int] = None,
    acting_user: Optional[Any] = None,
) -> Bank:
    permission_user_id = _require_permission_if_user_given(
        acting_user,
        Permission.BANK_CREATE,
        attempted_action="BANK_CREATE",
        entity_type="Bank",
        details={
            "name": name,
            "short_name": short_name,
        },
    )

    effective_user_id = permission_user_id if permission_user_id is not None else created_by_user_id

    cleaned_name = _clean_required_text(name, "Banka adı")
    cleaned_short_name = _clean_optional_text(short_name)
    cleaned_notes = _clean_optional_text(notes)

    if _bank_has_same_name(session, name=cleaned_name):
        raise BankDefinitionServiceError("Bu banka adı zaten kayıtlı.")

    if _bank_has_same_short_name(session, short_name=cleaned_short_name):
        raise BankDefinitionServiceError("Bu banka kısa adı zaten kayıtlı.")

    bank = Bank(
        name=cleaned_name,
        short_name=cleaned_short_name,
        notes=cleaned_notes,
        is_active=True,
    )

    session.add(bank)

    try:
        session.flush()
    except IntegrityError as exc:
        raise BankDefinitionServiceError("Banka kaydı oluşturulamadı. Aynı kayıt daha önce açılmış olabilir.") from exc

    write_audit_log(
        session,
        user_id=effective_user_id,
        action="BANK_CREATED",
        entity_type="Bank",
        entity_id=bank.id,
        description=f"Banka tanımı oluşturuldu: {bank.name}",
        old_values=None,
        new_values=_bank_to_dict(bank),
    )

    return bank


def update_bank(
    session: Session,
    *,
    bank_id: int,
    name: str,
    short_name: Optional[str],
    notes: Optional[str],
    is_active: bool,
    updated_by_user_id: Optional[int] = None,
    acting_user: Optional[Any] = None,
) -> Bank:
    permission_user_id = _require_permission_if_user_given(
        acting_user,
        Permission.BANK_UPDATE,
        attempted_action="BANK_UPDATE",
        entity_type="Bank",
        entity_id=bank_id,
        details={
            "bank_id": bank_id,
            "name": name,
            "short_name": short_name,
            "is_active": is_active,
        },
    )

    effective_user_id = permission_user_id if permission_user_id is not None else updated_by_user_id

    bank = session.get(Bank, bank_id)

    if bank is None:
        raise BankDefinitionServiceError(f"Banka bulunamadı. Banka ID: {bank_id}")

    cleaned_name = _clean_required_text(name, "Banka adı")
    cleaned_short_name = _clean_optional_text(short_name)
    cleaned_notes = _clean_optional_text(notes)

    if _bank_has_same_name(session, name=cleaned_name, exclude_bank_id=bank.id):
        raise BankDefinitionServiceError("Bu banka adı başka bir banka kaydında kullanılıyor.")

    if _bank_has_same_short_name(session, short_name=cleaned_short_name, exclude_bank_id=bank.id):
        raise BankDefinitionServiceError("Bu banka kısa adı başka bir banka kaydında kullanılıyor.")

    old_values = _bank_to_dict(bank)

    bank.name = cleaned_name
    bank.short_name = cleaned_short_name
    bank.notes = cleaned_notes
    bank.is_active = bool(is_active)

    try:
        session.flush()
    except IntegrityError as exc:
        raise BankDefinitionServiceError("Banka kaydı güncellenemedi. Tekrarlı ad veya kısa ad olabilir.") from exc

    write_audit_log(
        session,
        user_id=effective_user_id,
        action="BANK_UPDATED",
        entity_type="Bank",
        entity_id=bank.id,
        description=f"Banka tanımı güncellendi: {bank.name}",
        old_values=old_values,
        new_values=_bank_to_dict(bank),
    )

    return bank


def create_bank_account(
    session: Session,
    *,
    bank_id: int,
    account_name: str,
    account_type: BankAccountType | str,
    currency_code: CurrencyCode | str,
    iban: Optional[str],
    branch_name: Optional[str],
    branch_code: Optional[str],
    account_no: Optional[str],
    opening_balance: object,
    opening_date: Optional[date],
    notes: Optional[str],
    created_by_user_id: Optional[int] = None,
    acting_user: Optional[Any] = None,
) -> BankAccount:
    permission_user_id = _require_permission_if_user_given(
        acting_user,
        Permission.BANK_ACCOUNT_CREATE,
        attempted_action="BANK_ACCOUNT_CREATE",
        entity_type="BankAccount",
        details={
            "bank_id": bank_id,
            "account_name": account_name,
            "account_type": str(account_type),
            "currency_code": str(currency_code),
        },
    )

    effective_user_id = permission_user_id if permission_user_id is not None else created_by_user_id

    bank = session.get(Bank, bank_id)

    if bank is None:
        raise BankDefinitionServiceError(f"Banka bulunamadı. Banka ID: {bank_id}")

    if not bank.is_active:
        raise BankDefinitionServiceError("Pasif bankaya yeni hesap açılamaz.")

    cleaned_account_name = _clean_required_text(account_name, "Hesap adı")
    cleaned_account_type = _normalize_bank_account_type(account_type)
    cleaned_currency_code = _normalize_currency_code(currency_code)
    cleaned_iban = _clean_optional_text(iban)
    cleaned_branch_name = _clean_optional_text(branch_name)
    cleaned_branch_code = _clean_optional_text(branch_code)
    cleaned_account_no = _clean_optional_text(account_no)
    cleaned_opening_balance = money(opening_balance or Decimal("0.00"), field_name="Açılış bakiyesi")
    cleaned_notes = _clean_optional_text(notes)

    if _bank_account_has_same_name(
        session,
        bank_id=bank.id,
        account_name=cleaned_account_name,
    ):
        raise BankDefinitionServiceError("Bu banka içinde aynı hesap adı zaten kullanılıyor.")

    if _iban_exists(session, iban=cleaned_iban):
        raise BankDefinitionServiceError("Bu IBAN başka bir hesapta kullanılıyor.")

    bank_account = BankAccount(
        bank_id=bank.id,
        account_name=cleaned_account_name,
        account_type=cleaned_account_type,
        currency_code=cleaned_currency_code,
        iban=cleaned_iban,
        branch_name=cleaned_branch_name,
        branch_code=cleaned_branch_code,
        account_no=cleaned_account_no,
        opening_balance=cleaned_opening_balance,
        opening_date=opening_date,
        notes=cleaned_notes,
        is_active=True,
    )

    session.add(bank_account)

    try:
        session.flush()
    except IntegrityError as exc:
        raise BankDefinitionServiceError("Banka hesabı oluşturulamadı. Tekrarlı hesap adı veya IBAN olabilir.") from exc

    write_audit_log(
        session,
        user_id=effective_user_id,
        action="BANK_ACCOUNT_CREATED",
        entity_type="BankAccount",
        entity_id=bank_account.id,
        description=f"Banka hesabı oluşturuldu: {bank.name} / {bank_account.account_name}",
        old_values=None,
        new_values=_bank_account_to_dict(bank_account),
    )

    return bank_account


def update_bank_account(
    session: Session,
    *,
    bank_account_id: int,
    bank_id: int,
    account_name: str,
    account_type: BankAccountType | str,
    currency_code: CurrencyCode | str,
    iban: Optional[str],
    branch_name: Optional[str],
    branch_code: Optional[str],
    account_no: Optional[str],
    opening_balance: object,
    opening_date: Optional[date],
    notes: Optional[str],
    is_active: bool,
    updated_by_user_id: Optional[int] = None,
    acting_user: Optional[Any] = None,
) -> BankAccount:
    permission_user_id = _require_permission_if_user_given(
        acting_user,
        Permission.BANK_ACCOUNT_UPDATE,
        attempted_action="BANK_ACCOUNT_UPDATE",
        entity_type="BankAccount",
        entity_id=bank_account_id,
        details={
            "bank_account_id": bank_account_id,
            "bank_id": bank_id,
            "account_name": account_name,
            "account_type": str(account_type),
            "currency_code": str(currency_code),
            "is_active": is_active,
        },
    )

    effective_user_id = permission_user_id if permission_user_id is not None else updated_by_user_id

    bank_account = session.get(BankAccount, bank_account_id)

    if bank_account is None:
        raise BankDefinitionServiceError(f"Banka hesabı bulunamadı. Hesap ID: {bank_account_id}")

    bank = session.get(Bank, bank_id)

    if bank is None:
        raise BankDefinitionServiceError(f"Banka bulunamadı. Banka ID: {bank_id}")

    if not bank.is_active:
        raise BankDefinitionServiceError("Pasif bankaya hesap bağlanamaz.")

    cleaned_account_name = _clean_required_text(account_name, "Hesap adı")
    cleaned_account_type = _normalize_bank_account_type(account_type)
    cleaned_currency_code = _normalize_currency_code(currency_code)
    cleaned_iban = _clean_optional_text(iban)
    cleaned_branch_name = _clean_optional_text(branch_name)
    cleaned_branch_code = _clean_optional_text(branch_code)
    cleaned_account_no = _clean_optional_text(account_no)
    cleaned_opening_balance = money(opening_balance or Decimal("0.00"), field_name="Açılış bakiyesi")
    cleaned_notes = _clean_optional_text(notes)

    has_transactions = _bank_account_has_transactions(
        session,
        bank_account_id=bank_account.id,
    )

    if has_transactions and cleaned_currency_code != bank_account.currency_code:
        raise BankDefinitionServiceError(
            "Hareket görmüş banka hesabının para birimi değiştirilemez."
        )

    if _bank_account_has_same_name(
        session,
        bank_id=bank.id,
        account_name=cleaned_account_name,
        exclude_bank_account_id=bank_account.id,
    ):
        raise BankDefinitionServiceError("Bu banka içinde aynı hesap adı başka bir hesapta kullanılıyor.")

    if _iban_exists(
        session,
        iban=cleaned_iban,
        exclude_bank_account_id=bank_account.id,
    ):
        raise BankDefinitionServiceError("Bu IBAN başka bir hesapta kullanılıyor.")

    old_values = _bank_account_to_dict(bank_account)

    bank_account.bank_id = bank.id
    bank_account.account_name = cleaned_account_name
    bank_account.account_type = cleaned_account_type
    bank_account.currency_code = cleaned_currency_code
    bank_account.iban = cleaned_iban
    bank_account.branch_name = cleaned_branch_name
    bank_account.branch_code = cleaned_branch_code
    bank_account.account_no = cleaned_account_no
    bank_account.opening_balance = cleaned_opening_balance
    bank_account.opening_date = opening_date
    bank_account.notes = cleaned_notes
    bank_account.is_active = bool(is_active)

    try:
        session.flush()
    except IntegrityError as exc:
        raise BankDefinitionServiceError("Banka hesabı güncellenemedi. Tekrarlı hesap adı veya IBAN olabilir.") from exc

    write_audit_log(
        session,
        user_id=effective_user_id,
        action="BANK_ACCOUNT_UPDATED",
        entity_type="BankAccount",
        entity_id=bank_account.id,
        description=f"Banka hesabı güncellendi: {bank.name} / {bank_account.account_name}",
        old_values=old_values,
        new_values=_bank_account_to_dict(bank_account),
    )

    return bank_account


def deactivate_bank_account(
    session: Session,
    *,
    bank_account_id: int,
    deactivate_reason: str,
    deactivated_by_user_id: Optional[int] = None,
    acting_user: Optional[Any] = None,
) -> BankAccount:
    permission_user_id = _require_permission_if_user_given(
        acting_user,
        Permission.BANK_ACCOUNT_DEACTIVATE,
        attempted_action="BANK_ACCOUNT_DEACTIVATE",
        entity_type="BankAccount",
        entity_id=bank_account_id,
        details={
            "bank_account_id": bank_account_id,
            "deactivate_reason": deactivate_reason,
        },
    )

    effective_user_id = permission_user_id if permission_user_id is not None else deactivated_by_user_id

    cleaned_reason = _clean_required_text(deactivate_reason, "Pasifleştirme nedeni")

    if len(cleaned_reason) < 5:
        raise BankDefinitionServiceError("Pasifleştirme nedeni daha açıklayıcı olmalıdır.")

    bank_account = session.get(BankAccount, bank_account_id)

    if bank_account is None:
        raise BankDefinitionServiceError(f"Banka hesabı bulunamadı. Hesap ID: {bank_account_id}")

    if not bank_account.is_active:
        raise BankDefinitionServiceError("Bu banka hesabı zaten pasif durumda.")

    balance_summary = get_bank_account_balance_summary(
        session,
        bank_account_id=bank_account.id,
    )

    current_balance = money(
        balance_summary["current_balance"],
        field_name="Güncel bakiye",
    )

    if current_balance != Decimal("0.00"):
        raise BankDefinitionServiceError(
            f"Bakiyesi sıfır olmayan banka hesabı pasifleştirilemez. "
            f"Güncel bakiye: {current_balance} {bank_account.currency_code.value}"
        )

    old_values = _bank_account_to_dict(bank_account)

    bank_account.is_active = False
    bank_account.notes = (
        f"{bank_account.notes}\n\nPasifleştirme nedeni: {cleaned_reason}"
        if bank_account.notes
        else f"Pasifleştirme nedeni: {cleaned_reason}"
    )

    session.flush()

    write_audit_log(
        session,
        user_id=effective_user_id,
        action="BANK_ACCOUNT_DEACTIVATED",
        entity_type="BankAccount",
        entity_id=bank_account.id,
        description=f"Banka hesabı pasifleştirildi: {bank_account.account_name}",
        old_values=old_values,
        new_values=_bank_account_to_dict(bank_account),
    )

    return bank_account


def reactivate_bank_account(
    session: Session,
    *,
    bank_account_id: int,
    reactivate_reason: str,
    reactivated_by_user_id: Optional[int] = None,
    acting_user: Optional[Any] = None,
) -> BankAccount:
    permission_user_id = _require_permission_if_user_given(
        acting_user,
        Permission.BANK_ACCOUNT_REACTIVATE,
        attempted_action="BANK_ACCOUNT_REACTIVATE",
        entity_type="BankAccount",
        entity_id=bank_account_id,
        details={
            "bank_account_id": bank_account_id,
            "reactivate_reason": reactivate_reason,
        },
    )

    effective_user_id = permission_user_id if permission_user_id is not None else reactivated_by_user_id

    cleaned_reason = _clean_required_text(reactivate_reason, "Aktifleştirme nedeni")

    if len(cleaned_reason) < 5:
        raise BankDefinitionServiceError("Aktifleştirme nedeni daha açıklayıcı olmalıdır.")

    bank_account = session.get(BankAccount, bank_account_id)

    if bank_account is None:
        raise BankDefinitionServiceError(f"Banka hesabı bulunamadı. Hesap ID: {bank_account_id}")

    if bank_account.is_active:
        raise BankDefinitionServiceError("Bu banka hesabı zaten aktif durumda.")

    bank = session.get(Bank, bank_account.bank_id)

    if bank is None:
        raise BankDefinitionServiceError("Banka hesabının bağlı olduğu banka bulunamadı.")

    if not bank.is_active:
        raise BankDefinitionServiceError("Pasif bankaya bağlı hesap aktifleştirilemez. Önce banka aktif edilmelidir.")

    old_values = _bank_account_to_dict(bank_account)

    bank_account.is_active = True
    bank_account.notes = (
        f"{bank_account.notes}\n\nAktifleştirme nedeni: {cleaned_reason}"
        if bank_account.notes
        else f"Aktifleştirme nedeni: {cleaned_reason}"
    )

    session.flush()

    write_audit_log(
        session,
        user_id=effective_user_id,
        action="BANK_ACCOUNT_REACTIVATED",
        entity_type="BankAccount",
        entity_id=bank_account.id,
        description=f"Banka hesabı tekrar aktifleştirildi: {bank_account.account_name}",
        old_values=old_values,
        new_values=_bank_account_to_dict(bank_account),
    )

    return bank_account