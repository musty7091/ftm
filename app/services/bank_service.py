from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.bank import Bank, BankAccount
from app.models.enums import BankAccountType, CurrencyCode
from app.services.audit_service import write_audit_log
from app.utils.decimal_utils import money


class BankServiceError(ValueError):
    pass


def _clean_required_text(value: str, field_name: str) -> str:
    cleaned_value = (value or "").strip()

    if not cleaned_value:
        raise BankServiceError(f"{field_name} boş olamaz.")

    return cleaned_value


def _clean_optional_text(value: Optional[str]) -> Optional[str]:
    cleaned_value = (value or "").strip()

    if not cleaned_value:
        return None

    return cleaned_value


def get_bank_by_name(session: Session, bank_name: str) -> Optional[Bank]:
    cleaned_bank_name = _clean_required_text(bank_name, "Banka adı")

    statement = select(Bank).where(Bank.name == cleaned_bank_name)

    return session.execute(statement).scalar_one_or_none()


def get_bank_account_by_name(
    session: Session,
    *,
    bank_id: int,
    account_name: str,
) -> Optional[BankAccount]:
    cleaned_account_name = _clean_required_text(account_name, "Hesap adı")

    statement = select(BankAccount).where(
        BankAccount.bank_id == bank_id,
        BankAccount.account_name == cleaned_account_name,
    )

    return session.execute(statement).scalar_one_or_none()


def create_bank(
    session: Session,
    *,
    name: str,
    short_name: Optional[str],
    notes: Optional[str],
    created_by_user_id: Optional[int],
) -> Bank:
    cleaned_name = _clean_required_text(name, "Banka adı")
    cleaned_short_name = _clean_optional_text(short_name)
    cleaned_notes = _clean_optional_text(notes)

    existing_bank = get_bank_by_name(session, cleaned_name)

    if existing_bank is not None:
        raise BankServiceError(f"Bu banka zaten kayıtlı: {cleaned_name}")

    bank = Bank(
        name=cleaned_name,
        short_name=cleaned_short_name,
        notes=cleaned_notes,
        is_active=True,
    )

    session.add(bank)
    session.flush()

    write_audit_log(
        session,
        user_id=created_by_user_id,
        action="BANK_CREATED",
        entity_type="Bank",
        entity_id=bank.id,
        description=f"Banka oluşturuldu: {bank.name}",
        old_values=None,
        new_values={
            "id": bank.id,
            "name": bank.name,
            "short_name": bank.short_name,
            "notes": bank.notes,
            "is_active": bank.is_active,
        },
    )

    return bank


def get_or_create_bank(
    session: Session,
    *,
    name: str,
    short_name: Optional[str],
    notes: Optional[str],
    created_by_user_id: Optional[int],
) -> Bank:
    cleaned_name = _clean_required_text(name, "Banka adı")
    existing_bank = get_bank_by_name(session, cleaned_name)

    if existing_bank is not None:
        return existing_bank

    return create_bank(
        session,
        name=cleaned_name,
        short_name=short_name,
        notes=notes,
        created_by_user_id=created_by_user_id,
    )


def create_bank_account(
    session: Session,
    *,
    bank_id: int,
    account_name: str,
    account_type: BankAccountType,
    currency_code: CurrencyCode,
    iban: Optional[str],
    branch_name: Optional[str],
    branch_code: Optional[str],
    account_no: Optional[str],
    opening_balance: Decimal,
    opening_date: Optional[date],
    notes: Optional[str],
    created_by_user_id: Optional[int],
) -> BankAccount:
    cleaned_account_name = _clean_required_text(account_name, "Hesap adı")
    cleaned_iban = _clean_optional_text(iban)
    cleaned_branch_name = _clean_optional_text(branch_name)
    cleaned_branch_code = _clean_optional_text(branch_code)
    cleaned_account_no = _clean_optional_text(account_no)
    cleaned_notes = _clean_optional_text(notes)
    cleaned_opening_balance = money(opening_balance, field_name="Açılış bakiyesi")

    bank = session.get(Bank, bank_id)

    if bank is None:
        raise BankServiceError(f"Banka bulunamadı. Banka ID: {bank_id}")

    existing_account = get_bank_account_by_name(
        session,
        bank_id=bank.id,
        account_name=cleaned_account_name,
    )

    if existing_account is not None:
        raise BankServiceError(f"Bu bankada aynı hesap adı zaten kayıtlı: {cleaned_account_name}")

    bank_account = BankAccount(
        bank_id=bank.id,
        account_name=cleaned_account_name,
        account_type=account_type,
        currency_code=currency_code,
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
    session.flush()

    write_audit_log(
        session,
        user_id=created_by_user_id,
        action="BANK_ACCOUNT_CREATED",
        entity_type="BankAccount",
        entity_id=bank_account.id,
        description=f"Banka hesabı oluşturuldu: {bank.name} / {bank_account.account_name}",
        old_values=None,
        new_values={
            "id": bank_account.id,
            "bank_id": bank_account.bank_id,
            "bank_name": bank.name,
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
        },
    )

    return bank_account