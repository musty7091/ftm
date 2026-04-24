from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.bank import BankAccount
from app.models.business_partner import BusinessPartner
from app.models.check import IssuedCheck, ReceivedCheck, ReceivedCheckMovement
from app.models.enums import (
    BankTransactionStatus,
    BusinessPartnerType,
    CurrencyCode,
    FinancialSourceType,
    IssuedCheckStatus,
    ReceivedCheckMovementType,
    ReceivedCheckStatus,
    TransactionDirection,
)
from app.services.audit_service import write_audit_log
from app.services.bank_transaction_service import (
    BankTransactionServiceError,
    create_bank_transaction,
    get_bank_account_balance_summary,
)
from app.services.permission_audit_service import require_permission_with_audit
from app.services.permission_service import Permission, PermissionServiceError
from app.utils.decimal_utils import money, rate


class CheckServiceError(ValueError):
    pass


def _clean_required_text(value: str, field_name: str) -> str:
    cleaned_value = (value or "").strip()

    if not cleaned_value:
        raise CheckServiceError(f"{field_name} boş olamaz.")

    return cleaned_value


def _clean_optional_text(value: Optional[str]) -> Optional[str]:
    cleaned_value = (value or "").strip()

    if not cleaned_value:
        return None

    return cleaned_value


def _validate_positive_money(value: object, field_name: str) -> Decimal:
    cleaned_amount = money(value, field_name=field_name)

    if cleaned_amount <= Decimal("0.00"):
        raise CheckServiceError(f"{field_name} sıfırdan büyük olmalıdır.")

    return cleaned_amount


def _validate_discount_rate(value: object, field_name: str = "İskonto oranı") -> Decimal:
    cleaned_rate = rate(value, field_name=field_name)

    if cleaned_rate <= Decimal("0.000000"):
        raise CheckServiceError(f"{field_name} sıfırdan büyük olmalıdır.")

    if cleaned_rate >= Decimal("100.000000"):
        raise CheckServiceError(f"{field_name} 100'den küçük olmalıdır.")

    return cleaned_rate


def _validate_due_date(*, start_date: date, due_date: date, start_field_name: str) -> None:
    if due_date < start_date:
        raise CheckServiceError(f"Vade tarihi, {start_field_name} tarihinden önce olamaz.")


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
        raise CheckServiceError(str(exc)) from exc


def _issued_check_to_dict(check: IssuedCheck) -> dict[str, Any]:
    return {
        "id": check.id,
        "supplier_id": check.supplier_id,
        "bank_account_id": check.bank_account_id,
        "check_number": check.check_number,
        "issue_date": check.issue_date.isoformat(),
        "due_date": check.due_date.isoformat(),
        "amount": str(check.amount),
        "currency_code": check.currency_code.value,
        "status": check.status.value,
        "paid_transaction_id": check.paid_transaction_id,
        "reference_no": check.reference_no,
        "description": check.description,
        "created_by_user_id": check.created_by_user_id,
        "cancelled_by_user_id": check.cancelled_by_user_id,
        "cancelled_at": check.cancelled_at.isoformat() if check.cancelled_at else None,
        "cancel_reason": check.cancel_reason,
    }


def _received_check_to_dict(check: ReceivedCheck) -> dict[str, Any]:
    return {
        "id": check.id,
        "customer_id": check.customer_id,
        "collection_bank_account_id": check.collection_bank_account_id,
        "drawer_bank_name": check.drawer_bank_name,
        "drawer_branch_name": check.drawer_branch_name,
        "check_number": check.check_number,
        "received_date": check.received_date.isoformat(),
        "due_date": check.due_date.isoformat(),
        "amount": str(check.amount),
        "currency_code": check.currency_code.value,
        "status": check.status.value,
        "collected_transaction_id": check.collected_transaction_id,
        "reference_no": check.reference_no,
        "description": check.description,
        "created_by_user_id": check.created_by_user_id,
        "cancelled_by_user_id": check.cancelled_by_user_id,
        "cancelled_at": check.cancelled_at.isoformat() if check.cancelled_at else None,
        "cancel_reason": check.cancel_reason,
    }


def _received_check_movement_to_dict(movement: ReceivedCheckMovement) -> dict[str, Any]:
    return {
        "id": movement.id,
        "received_check_id": movement.received_check_id,
        "movement_type": movement.movement_type.value,
        "movement_date": movement.movement_date.isoformat(),
        "from_status": movement.from_status.value if movement.from_status else None,
        "to_status": movement.to_status.value,
        "bank_account_id": movement.bank_account_id,
        "counterparty_text": movement.counterparty_text,
        "purpose_text": movement.purpose_text,
        "reference_no": movement.reference_no,
        "description": movement.description,
        "gross_amount": str(movement.gross_amount),
        "currency_code": movement.currency_code.value,
        "discount_rate": str(movement.discount_rate) if movement.discount_rate is not None else None,
        "discount_expense_amount": (
            str(movement.discount_expense_amount)
            if movement.discount_expense_amount is not None
            else None
        ),
        "net_bank_amount": str(movement.net_bank_amount) if movement.net_bank_amount is not None else None,
        "created_by_user_id": movement.created_by_user_id,
        "created_at": movement.created_at.isoformat() if movement.created_at else None,
    }


def _create_received_check_movement(
    session: Session,
    *,
    received_check: ReceivedCheck,
    movement_type: ReceivedCheckMovementType,
    movement_date: date,
    from_status: Optional[ReceivedCheckStatus],
    to_status: ReceivedCheckStatus,
    bank_account_id: Optional[int],
    counterparty_text: Optional[str],
    purpose_text: Optional[str],
    reference_no: Optional[str],
    description: Optional[str],
    gross_amount: Decimal,
    currency_code: CurrencyCode,
    discount_rate: Optional[Decimal] = None,
    discount_expense_amount: Optional[Decimal] = None,
    net_bank_amount: Optional[Decimal] = None,
    created_by_user_id: Optional[int] = None,
) -> ReceivedCheckMovement:
    movement = ReceivedCheckMovement(
        received_check_id=received_check.id,
        movement_type=movement_type,
        movement_date=movement_date,
        from_status=from_status,
        to_status=to_status,
        bank_account_id=bank_account_id,
        counterparty_text=_clean_optional_text(counterparty_text),
        purpose_text=_clean_optional_text(purpose_text),
        reference_no=_clean_optional_text(reference_no),
        description=_clean_optional_text(description),
        gross_amount=gross_amount,
        currency_code=currency_code,
        discount_rate=discount_rate,
        discount_expense_amount=discount_expense_amount,
        net_bank_amount=net_bank_amount,
        created_by_user_id=created_by_user_id,
    )

    session.add(movement)
    session.flush()

    write_audit_log(
        session,
        user_id=created_by_user_id,
        action="RECEIVED_CHECK_MOVEMENT_CREATED",
        entity_type="ReceivedCheckMovement",
        entity_id=movement.id,
        description=(
            f"Alınan çek hareketi oluşturuldu: "
            f"{movement.movement_type.value} / Çek ID: {received_check.id}"
        ),
        old_values=None,
        new_values=_received_check_movement_to_dict(movement),
    )

    return movement


def get_issued_check_by_number(
    session: Session,
    *,
    bank_account_id: int,
    check_number: str,
) -> Optional[IssuedCheck]:
    cleaned_check_number = _clean_required_text(check_number, "Çek numarası")

    statement = select(IssuedCheck).where(
        IssuedCheck.bank_account_id == bank_account_id,
        IssuedCheck.check_number == cleaned_check_number,
    )

    return session.execute(statement).scalar_one_or_none()


def get_received_check_by_number(
    session: Session,
    *,
    drawer_bank_name: str,
    check_number: str,
) -> Optional[ReceivedCheck]:
    cleaned_drawer_bank_name = _clean_required_text(drawer_bank_name, "Çeki veren banka")
    cleaned_check_number = _clean_required_text(check_number, "Çek numarası")

    statement = select(ReceivedCheck).where(
        ReceivedCheck.drawer_bank_name == cleaned_drawer_bank_name,
        ReceivedCheck.check_number == cleaned_check_number,
    )

    return session.execute(statement).scalar_one_or_none()


def create_issued_check(
    session: Session,
    *,
    supplier_id: int,
    bank_account_id: int,
    check_number: str,
    issue_date: date,
    due_date: date,
    amount: object,
    status: IssuedCheckStatus,
    reference_no: Optional[str],
    description: Optional[str],
    created_by_user_id: Optional[int] = None,
    acting_user: Optional[Any] = None,
) -> IssuedCheck:
    permission_user_id = _require_permission_if_user_given(
        acting_user,
        Permission.ISSUED_CHECK_CREATE,
        attempted_action="ISSUED_CHECK_CREATE",
        entity_type="IssuedCheck",
        details={
            "supplier_id": supplier_id,
            "bank_account_id": bank_account_id,
            "check_number": check_number,
            "issue_date": issue_date.isoformat(),
            "due_date": due_date.isoformat(),
            "amount": str(amount),
            "status": status.value if hasattr(status, "value") else str(status),
        },
    )

    effective_created_by_user_id = permission_user_id if permission_user_id is not None else created_by_user_id

    if status not in {IssuedCheckStatus.PREPARED, IssuedCheckStatus.GIVEN}:
        raise CheckServiceError("Yazılan çek ilk oluşturulurken sadece PREPARED veya GIVEN olabilir.")

    supplier = session.get(BusinessPartner, supplier_id)

    if supplier is None:
        raise CheckServiceError(f"Tedarikçi cari kartı bulunamadı. Cari ID: {supplier_id}")

    if supplier.partner_type not in {BusinessPartnerType.SUPPLIER, BusinessPartnerType.BOTH}:
        raise CheckServiceError("Seçilen cari kart tedarikçi türünde değil.")

    if not supplier.is_active:
        raise CheckServiceError("Pasif cari karta çek yazılamaz.")

    bank_account = session.get(BankAccount, bank_account_id)

    if bank_account is None:
        raise CheckServiceError(f"Banka hesabı bulunamadı. Hesap ID: {bank_account_id}")

    if not bank_account.is_active:
        raise CheckServiceError("Pasif banka hesabından çek yazılamaz.")

    cleaned_check_number = _clean_required_text(check_number, "Çek numarası")
    cleaned_amount = _validate_positive_money(amount, "Çek tutarı")
    cleaned_reference_no = _clean_optional_text(reference_no)
    cleaned_description = _clean_optional_text(description)

    _validate_due_date(
        start_date=issue_date,
        due_date=due_date,
        start_field_name="düzenleme",
    )

    existing_check = get_issued_check_by_number(
        session,
        bank_account_id=bank_account.id,
        check_number=cleaned_check_number,
    )

    if existing_check is not None:
        raise CheckServiceError(
            f"Bu banka hesabında aynı çek numarası zaten kayıtlı: {cleaned_check_number}"
        )

    check = IssuedCheck(
        supplier_id=supplier.id,
        bank_account_id=bank_account.id,
        check_number=cleaned_check_number,
        issue_date=issue_date,
        due_date=due_date,
        amount=cleaned_amount,
        currency_code=bank_account.currency_code,
        status=status,
        reference_no=cleaned_reference_no,
        description=cleaned_description,
        created_by_user_id=effective_created_by_user_id,
    )

    session.add(check)
    session.flush()

    write_audit_log(
        session,
        user_id=effective_created_by_user_id,
        action="ISSUED_CHECK_CREATED",
        entity_type="IssuedCheck",
        entity_id=check.id,
        description=f"Yazılan çek oluşturuldu: {check.check_number} / {check.amount} {check.currency_code.value}",
        old_values=None,
        new_values=_issued_check_to_dict(check),
    )

    return check


def create_received_check(
    session: Session,
    *,
    customer_id: int,
    collection_bank_account_id: Optional[int],
    drawer_bank_name: str,
    drawer_branch_name: Optional[str],
    check_number: str,
    received_date: date,
    due_date: date,
    amount: object,
    currency_code: CurrencyCode,
    status: ReceivedCheckStatus,
    reference_no: Optional[str],
    description: Optional[str],
    created_by_user_id: Optional[int] = None,
    acting_user: Optional[Any] = None,
) -> ReceivedCheck:
    permission_user_id = _require_permission_if_user_given(
        acting_user,
        Permission.RECEIVED_CHECK_CREATE,
        attempted_action="RECEIVED_CHECK_CREATE",
        entity_type="ReceivedCheck",
        details={
            "customer_id": customer_id,
            "collection_bank_account_id": collection_bank_account_id,
            "drawer_bank_name": drawer_bank_name,
            "drawer_branch_name": drawer_branch_name,
            "check_number": check_number,
            "received_date": received_date.isoformat(),
            "due_date": due_date.isoformat(),
            "amount": str(amount),
            "currency_code": currency_code.value if hasattr(currency_code, "value") else str(currency_code),
            "status": status.value if hasattr(status, "value") else str(status),
        },
    )

    effective_created_by_user_id = permission_user_id if permission_user_id is not None else created_by_user_id

    if status not in {
        ReceivedCheckStatus.PORTFOLIO,
        ReceivedCheckStatus.GIVEN_TO_BANK,
        ReceivedCheckStatus.IN_COLLECTION,
    }:
        raise CheckServiceError(
            "Alınan çek ilk oluşturulurken sadece PORTFOLIO, GIVEN_TO_BANK veya IN_COLLECTION olabilir."
        )

    customer = session.get(BusinessPartner, customer_id)

    if customer is None:
        raise CheckServiceError(f"Müşteri cari kartı bulunamadı. Cari ID: {customer_id}")

    if customer.partner_type not in {BusinessPartnerType.CUSTOMER, BusinessPartnerType.BOTH}:
        raise CheckServiceError("Seçilen cari kart müşteri türünde değil.")

    if not customer.is_active:
        raise CheckServiceError("Pasif cari karttan çek alınamaz.")

    collection_bank_account = None

    if collection_bank_account_id is not None:
        collection_bank_account = session.get(BankAccount, collection_bank_account_id)

        if collection_bank_account is None:
            raise CheckServiceError(
                f"Tahsilat banka hesabı bulunamadı. Hesap ID: {collection_bank_account_id}"
            )

        if not collection_bank_account.is_active:
            raise CheckServiceError("Pasif banka hesabı tahsilat hesabı olarak seçilemez.")

        if collection_bank_account.currency_code != currency_code:
            raise CheckServiceError(
                f"Çek para birimi ile tahsilat hesabı para birimi aynı olmalıdır. "
                f"Çek: {currency_code.value}, Hesap: {collection_bank_account.currency_code.value}"
            )

    cleaned_drawer_bank_name = _clean_required_text(drawer_bank_name, "Çeki veren banka")
    cleaned_drawer_branch_name = _clean_optional_text(drawer_branch_name)
    cleaned_check_number = _clean_required_text(check_number, "Çek numarası")
    cleaned_amount = _validate_positive_money(amount, "Çek tutarı")
    cleaned_reference_no = _clean_optional_text(reference_no)
    cleaned_description = _clean_optional_text(description)

    _validate_due_date(
        start_date=received_date,
        due_date=due_date,
        start_field_name="alış",
    )

    existing_check = get_received_check_by_number(
        session,
        drawer_bank_name=cleaned_drawer_bank_name,
        check_number=cleaned_check_number,
    )

    if existing_check is not None:
        raise CheckServiceError(
            f"Aynı banka ve çek numarasıyla alınan çek zaten kayıtlı: "
            f"{cleaned_drawer_bank_name} / {cleaned_check_number}"
        )

    check = ReceivedCheck(
        customer_id=customer.id,
        collection_bank_account_id=collection_bank_account.id if collection_bank_account else None,
        drawer_bank_name=cleaned_drawer_bank_name,
        drawer_branch_name=cleaned_drawer_branch_name,
        check_number=cleaned_check_number,
        received_date=received_date,
        due_date=due_date,
        amount=cleaned_amount,
        currency_code=currency_code,
        status=status,
        reference_no=cleaned_reference_no,
        description=cleaned_description,
        created_by_user_id=effective_created_by_user_id,
    )

    session.add(check)
    session.flush()

    _create_received_check_movement(
        session,
        received_check=check,
        movement_type=ReceivedCheckMovementType.REGISTERED,
        movement_date=received_date,
        from_status=None,
        to_status=status,
        bank_account_id=collection_bank_account.id if collection_bank_account else None,
        counterparty_text=customer.name,
        purpose_text="Alınan çek kaydı oluşturuldu.",
        reference_no=cleaned_reference_no,
        description=cleaned_description,
        gross_amount=check.amount,
        currency_code=check.currency_code,
        created_by_user_id=effective_created_by_user_id,
    )

    write_audit_log(
        session,
        user_id=effective_created_by_user_id,
        action="RECEIVED_CHECK_CREATED",
        entity_type="ReceivedCheck",
        entity_id=check.id,
        description=f"Alınan çek oluşturuldu: {check.check_number} / {check.amount} {check.currency_code.value}",
        old_values=None,
        new_values=_received_check_to_dict(check),
    )

    return check


def send_received_check_to_bank(
    session: Session,
    *,
    received_check_id: int,
    collection_bank_account_id: int,
    sent_date: date,
    reference_no: Optional[str],
    description: Optional[str],
    moved_by_user_id: Optional[int] = None,
    acting_user: Optional[Any] = None,
) -> ReceivedCheck:
    permission_user_id = _require_permission_if_user_given(
        acting_user,
        Permission.RECEIVED_CHECK_SEND_TO_BANK,
        attempted_action="RECEIVED_CHECK_SEND_TO_BANK",
        entity_type="ReceivedCheck",
        details={
            "received_check_id": received_check_id,
            "collection_bank_account_id": collection_bank_account_id,
            "sent_date": sent_date.isoformat(),
            "reference_no": reference_no,
        },
    )

    effective_moved_by_user_id = permission_user_id if permission_user_id is not None else moved_by_user_id

    check = session.get(ReceivedCheck, received_check_id)

    if check is None:
        raise CheckServiceError(f"Alınan çek bulunamadı. Çek ID: {received_check_id}")

    if check.status != ReceivedCheckStatus.PORTFOLIO:
        raise CheckServiceError("Bankaya tahsile gönderme işlemi sadece PORTFOLIO durumundaki çeklerde yapılabilir.")

    if check.collected_transaction_id is not None:
        raise CheckServiceError("Tahsil hareketi oluşmuş çek tekrar bankaya tahsile gönderilemez.")

    bank_account = session.get(BankAccount, collection_bank_account_id)

    if bank_account is None:
        raise CheckServiceError(f"Tahsilat banka hesabı bulunamadı. Hesap ID: {collection_bank_account_id}")

    if not bank_account.is_active:
        raise CheckServiceError("Pasif banka hesabına çek gönderilemez.")

    if bank_account.currency_code != check.currency_code:
        raise CheckServiceError(
            f"Çek para birimi ile banka hesabı para birimi aynı olmalıdır. "
            f"Çek: {check.currency_code.value}, Hesap: {bank_account.currency_code.value}"
        )

    cleaned_reference_no = _clean_optional_text(reference_no) or check.reference_no
    cleaned_description = _clean_optional_text(description)

    old_values = _received_check_to_dict(check)
    previous_status = check.status

    check.status = ReceivedCheckStatus.GIVEN_TO_BANK
    check.collection_bank_account_id = bank_account.id

    session.flush()

    _create_received_check_movement(
        session,
        received_check=check,
        movement_type=ReceivedCheckMovementType.SENT_TO_BANK_COLLECTION,
        movement_date=sent_date,
        from_status=previous_status,
        to_status=ReceivedCheckStatus.GIVEN_TO_BANK,
        bank_account_id=bank_account.id,
        counterparty_text=f"{bank_account.bank.name} / {bank_account.account_name}" if bank_account.bank else bank_account.account_name,
        purpose_text="Alınan çek bankaya tahsile verildi.",
        reference_no=cleaned_reference_no,
        description=cleaned_description,
        gross_amount=check.amount,
        currency_code=check.currency_code,
        created_by_user_id=effective_moved_by_user_id,
    )

    write_audit_log(
        session,
        user_id=effective_moved_by_user_id,
        action="RECEIVED_CHECK_SENT_TO_BANK",
        entity_type="ReceivedCheck",
        entity_id=check.id,
        description=f"Alınan çek bankaya tahsile verildi: {check.check_number} / {check.amount} {check.currency_code.value}",
        old_values=old_values,
        new_values=_received_check_to_dict(check),
    )

    return check


def pay_issued_check(
    session: Session,
    *,
    issued_check_id: int,
    payment_date: date,
    reference_no: Optional[str],
    description: Optional[str],
    paid_by_user_id: Optional[int] = None,
    acting_user: Optional[Any] = None,
) -> IssuedCheck:
    permission_user_id = _require_permission_if_user_given(
        acting_user,
        Permission.ISSUED_CHECK_PAY,
        attempted_action="ISSUED_CHECK_PAY",
        entity_type="IssuedCheck",
        details={
            "issued_check_id": issued_check_id,
            "payment_date": payment_date.isoformat(),
            "reference_no": reference_no,
        },
    )

    effective_paid_by_user_id = permission_user_id if permission_user_id is not None else paid_by_user_id

    check = session.get(IssuedCheck, issued_check_id)

    if check is None:
        raise CheckServiceError(f"Yazılan çek bulunamadı. Çek ID: {issued_check_id}")

    if check.status == IssuedCheckStatus.PAID:
        raise CheckServiceError("Bu çek zaten ödenmiş.")

    if check.status == IssuedCheckStatus.CANCELLED:
        raise CheckServiceError("İptal edilmiş çek ödenemez.")

    if check.paid_transaction_id is not None:
        raise CheckServiceError("Bu çekin ödeme hareketi zaten var.")

    bank_account = session.get(BankAccount, check.bank_account_id)

    if bank_account is None:
        raise CheckServiceError(f"Çekin bağlı olduğu banka hesabı bulunamadı. Hesap ID: {check.bank_account_id}")

    if not bank_account.is_active:
        raise CheckServiceError("Pasif banka hesabından çek ödenemez.")

    balance_summary = get_bank_account_balance_summary(
        session,
        bank_account_id=bank_account.id,
    )

    current_balance = balance_summary["current_balance"]

    if current_balance < check.amount:
        raise CheckServiceError(
            f"Çekin ödenmesi için hesap bakiyesi yetersiz. "
            f"Mevcut bakiye: {current_balance} {bank_account.currency_code.value}, "
            f"Çek tutarı: {check.amount} {bank_account.currency_code.value}"
        )

    cleaned_reference_no = _clean_optional_text(reference_no) or check.reference_no
    cleaned_description = _clean_optional_text(description)

    old_values = _issued_check_to_dict(check)

    try:
        payment_transaction = create_bank_transaction(
            session,
            bank_account_id=bank_account.id,
            transaction_date=payment_date,
            value_date=payment_date,
            direction=TransactionDirection.OUT,
            status=BankTransactionStatus.REALIZED,
            amount=check.amount,
            currency_code=check.currency_code,
            source_type=FinancialSourceType.ISSUED_CHECK,
            source_id=check.id,
            reference_no=cleaned_reference_no,
            description=(
                f"Yazılan çek ödemesi: {check.check_number}"
                if not cleaned_description
                else f"Yazılan çek ödemesi: {check.check_number} - {cleaned_description}"
            ),
            created_by_user_id=effective_paid_by_user_id,
        )
    except BankTransactionServiceError as exc:
        raise CheckServiceError(f"Çek ödeme banka hareketi oluşturulamadı: {exc}") from exc

    check.status = IssuedCheckStatus.PAID
    check.paid_transaction_id = payment_transaction.id

    session.flush()

    write_audit_log(
        session,
        user_id=effective_paid_by_user_id,
        action="ISSUED_CHECK_PAID",
        entity_type="IssuedCheck",
        entity_id=check.id,
        description=f"Yazılan çek ödendi: {check.check_number} / {check.amount} {check.currency_code.value}",
        old_values=old_values,
        new_values=_issued_check_to_dict(check),
    )

    return check


def collect_received_check(
    session: Session,
    *,
    received_check_id: int,
    collection_bank_account_id: Optional[int],
    collection_date: date,
    reference_no: Optional[str],
    description: Optional[str],
    collected_by_user_id: Optional[int] = None,
    acting_user: Optional[Any] = None,
) -> ReceivedCheck:
    permission_user_id = _require_permission_if_user_given(
        acting_user,
        Permission.RECEIVED_CHECK_COLLECT,
        attempted_action="RECEIVED_CHECK_COLLECT",
        entity_type="ReceivedCheck",
        details={
            "received_check_id": received_check_id,
            "collection_bank_account_id": collection_bank_account_id,
            "collection_date": collection_date.isoformat(),
            "reference_no": reference_no,
        },
    )

    effective_collected_by_user_id = permission_user_id if permission_user_id is not None else collected_by_user_id

    check = session.get(ReceivedCheck, received_check_id)

    if check is None:
        raise CheckServiceError(f"Alınan çek bulunamadı. Çek ID: {received_check_id}")

    if check.status == ReceivedCheckStatus.COLLECTED:
        raise CheckServiceError("Bu çek zaten tahsil edilmiş.")

    if check.status == ReceivedCheckStatus.CANCELLED:
        raise CheckServiceError("İptal edilmiş çek tahsil edilemez.")

    if check.status == ReceivedCheckStatus.BOUNCED:
        raise CheckServiceError("Karşılıksız durumdaki çek tahsil edilemez.")

    if check.status == ReceivedCheckStatus.RETURNED:
        raise CheckServiceError("İade edilmiş çek tahsil edilemez.")

    if check.status == ReceivedCheckStatus.ENDORSED:
        raise CheckServiceError("Ciro edilmiş çek tahsil edilemez.")

    if check.status == ReceivedCheckStatus.DISCOUNTED:
        raise CheckServiceError("İskontoya verilmiş çek tahsil edilemez.")

    if check.collected_transaction_id is not None:
        raise CheckServiceError("Bu çekin tahsilat hareketi zaten var.")

    final_collection_bank_account_id = collection_bank_account_id or check.collection_bank_account_id

    if final_collection_bank_account_id is None:
        raise CheckServiceError("Tahsilat için banka hesabı seçilmelidir.")

    bank_account = session.get(BankAccount, final_collection_bank_account_id)

    if bank_account is None:
        raise CheckServiceError(f"Tahsilat banka hesabı bulunamadı. Hesap ID: {final_collection_bank_account_id}")

    if not bank_account.is_active:
        raise CheckServiceError("Pasif banka hesabına çek tahsil edilemez.")

    if bank_account.currency_code != check.currency_code:
        raise CheckServiceError(
            f"Çek para birimi ile banka hesabı para birimi aynı olmalıdır. "
            f"Çek: {check.currency_code.value}, Hesap: {bank_account.currency_code.value}"
        )

    cleaned_reference_no = _clean_optional_text(reference_no) or check.reference_no
    cleaned_description = _clean_optional_text(description)

    old_values = _received_check_to_dict(check)
    previous_status = check.status

    try:
        collection_transaction = create_bank_transaction(
            session,
            bank_account_id=bank_account.id,
            transaction_date=collection_date,
            value_date=collection_date,
            direction=TransactionDirection.IN,
            status=BankTransactionStatus.REALIZED,
            amount=check.amount,
            currency_code=check.currency_code,
            source_type=FinancialSourceType.RECEIVED_CHECK,
            source_id=check.id,
            reference_no=cleaned_reference_no,
            description=(
                f"Alınan çek tahsilatı: {check.check_number}"
                if not cleaned_description
                else f"Alınan çek tahsilatı: {check.check_number} - {cleaned_description}"
            ),
            created_by_user_id=effective_collected_by_user_id,
        )
    except BankTransactionServiceError as exc:
        raise CheckServiceError(f"Çek tahsilat banka hareketi oluşturulamadı: {exc}") from exc

    check.status = ReceivedCheckStatus.COLLECTED
    check.collection_bank_account_id = bank_account.id
    check.collected_transaction_id = collection_transaction.id

    session.flush()

    _create_received_check_movement(
        session,
        received_check=check,
        movement_type=ReceivedCheckMovementType.COLLECTED,
        movement_date=collection_date,
        from_status=previous_status,
        to_status=ReceivedCheckStatus.COLLECTED,
        bank_account_id=bank_account.id,
        counterparty_text=f"{bank_account.bank.name} / {bank_account.account_name}" if bank_account.bank else bank_account.account_name,
        purpose_text="Alınan çek tahsil edildi.",
        reference_no=cleaned_reference_no,
        description=cleaned_description,
        gross_amount=check.amount,
        currency_code=check.currency_code,
        net_bank_amount=check.amount,
        created_by_user_id=effective_collected_by_user_id,
    )

    write_audit_log(
        session,
        user_id=effective_collected_by_user_id,
        action="RECEIVED_CHECK_COLLECTED",
        entity_type="ReceivedCheck",
        entity_id=check.id,
        description=f"Alınan çek tahsil edildi: {check.check_number} / {check.amount} {check.currency_code.value}",
        old_values=old_values,
        new_values=_received_check_to_dict(check),
    )

    return check


def discount_received_check(
    session: Session,
    *,
    received_check_id: int,
    bank_account_id: int,
    discount_date: date,
    discount_rate: object,
    reference_no: Optional[str],
    description: Optional[str],
    discounted_by_user_id: Optional[int] = None,
    acting_user: Optional[Any] = None,
) -> ReceivedCheck:
    permission_user_id = _require_permission_if_user_given(
        acting_user,
        Permission.RECEIVED_CHECK_DISCOUNT,
        attempted_action="RECEIVED_CHECK_DISCOUNT",
        entity_type="ReceivedCheck",
        details={
            "received_check_id": received_check_id,
            "bank_account_id": bank_account_id,
            "discount_date": discount_date.isoformat(),
            "discount_rate": str(discount_rate),
            "reference_no": reference_no,
        },
    )

    effective_discounted_by_user_id = (
        permission_user_id if permission_user_id is not None else discounted_by_user_id
    )

    check = session.get(ReceivedCheck, received_check_id)

    if check is None:
        raise CheckServiceError(f"Alınan çek bulunamadı. Çek ID: {received_check_id}")

    if check.status not in {
        ReceivedCheckStatus.PORTFOLIO,
        ReceivedCheckStatus.GIVEN_TO_BANK,
        ReceivedCheckStatus.IN_COLLECTION,
    }:
        raise CheckServiceError(
            "İskontoya verme işlemi sadece PORTFOLIO, GIVEN_TO_BANK veya IN_COLLECTION durumundaki çeklerde yapılabilir."
        )

    if check.collected_transaction_id is not None:
        raise CheckServiceError("Banka hareketi oluşmuş çek iskonto edilemez.")

    bank_account = session.get(BankAccount, bank_account_id)

    if bank_account is None:
        raise CheckServiceError(f"Banka hesabı bulunamadı. Hesap ID: {bank_account_id}")

    if not bank_account.is_active:
        raise CheckServiceError("Pasif banka hesabına iskonto girişi yapılamaz.")

    if bank_account.currency_code != check.currency_code:
        raise CheckServiceError(
            f"Çek para birimi ile banka hesabı para birimi aynı olmalıdır. "
            f"Çek: {check.currency_code.value}, Hesap: {bank_account.currency_code.value}"
        )

    cleaned_discount_rate = _validate_discount_rate(discount_rate)
    discount_expense_amount = money(
        (check.amount * cleaned_discount_rate) / Decimal("100.000000"),
        field_name="İskonto masrafı",
    )
    net_bank_amount = money(
        check.amount - discount_expense_amount,
        field_name="Net banka girişi",
    )

    if discount_expense_amount <= Decimal("0.00"):
        raise CheckServiceError("İskonto masrafı sıfırdan büyük olmalıdır.")

    if net_bank_amount <= Decimal("0.00"):
        raise CheckServiceError("Net banka girişi sıfırdan büyük olmalıdır.")

    cleaned_reference_no = _clean_optional_text(reference_no) or check.reference_no
    cleaned_description = _clean_optional_text(description)

    old_values = _received_check_to_dict(check)
    previous_status = check.status

    try:
        discount_transaction = create_bank_transaction(
            session,
            bank_account_id=bank_account.id,
            transaction_date=discount_date,
            value_date=discount_date,
            direction=TransactionDirection.IN,
            status=BankTransactionStatus.REALIZED,
            amount=net_bank_amount,
            currency_code=check.currency_code,
            source_type=FinancialSourceType.RECEIVED_CHECK,
            source_id=check.id,
            reference_no=cleaned_reference_no,
            description=(
                f"Alınan çek iskonto/kırdırma net banka girişi: {check.check_number} "
                f"(Brüt: {check.amount} {check.currency_code.value}, "
                f"İskonto: {discount_expense_amount} {check.currency_code.value}, "
                f"Oran: {cleaned_discount_rate}%)"
                if not cleaned_description
                else (
                    f"Alınan çek iskonto/kırdırma net banka girişi: {check.check_number} "
                    f"(Brüt: {check.amount} {check.currency_code.value}, "
                    f"İskonto: {discount_expense_amount} {check.currency_code.value}, "
                    f"Oran: {cleaned_discount_rate}%) - {cleaned_description}"
                )
            ),
            created_by_user_id=effective_discounted_by_user_id,
        )
    except BankTransactionServiceError as exc:
        raise CheckServiceError(f"Çek iskonto banka hareketi oluşturulamadı: {exc}") from exc

    check.status = ReceivedCheckStatus.DISCOUNTED
    check.collection_bank_account_id = bank_account.id
    check.collected_transaction_id = discount_transaction.id

    session.flush()

    _create_received_check_movement(
        session,
        received_check=check,
        movement_type=ReceivedCheckMovementType.DISCOUNTED,
        movement_date=discount_date,
        from_status=previous_status,
        to_status=ReceivedCheckStatus.DISCOUNTED,
        bank_account_id=bank_account.id,
        counterparty_text=f"{bank_account.bank.name} / {bank_account.account_name}" if bank_account.bank else bank_account.account_name,
        purpose_text="Alınan çek iskonto/kırdırma yoluyla bankaya aktarıldı.",
        reference_no=cleaned_reference_no,
        description=cleaned_description,
        gross_amount=check.amount,
        currency_code=check.currency_code,
        discount_rate=cleaned_discount_rate,
        discount_expense_amount=discount_expense_amount,
        net_bank_amount=net_bank_amount,
        created_by_user_id=effective_discounted_by_user_id,
    )

    write_audit_log(
        session,
        user_id=effective_discounted_by_user_id,
        action="RECEIVED_CHECK_DISCOUNTED",
        entity_type="ReceivedCheck",
        entity_id=check.id,
        description=(
            f"Alınan çek iskonto/kırdırma işlemine alındı: "
            f"{check.check_number} / Brüt: {check.amount} {check.currency_code.value} / "
            f"Masraf: {discount_expense_amount} {check.currency_code.value} / "
            f"Net: {net_bank_amount} {check.currency_code.value}"
        ),
        old_values=old_values,
        new_values=_received_check_to_dict(check),
    )

    return check


def endorse_received_check(
    session: Session,
    *,
    received_check_id: int,
    endorse_date: date,
    counterparty_text: str,
    reference_no: Optional[str],
    description: Optional[str],
    endorsed_by_user_id: Optional[int] = None,
    acting_user: Optional[Any] = None,
) -> ReceivedCheck:
    permission_user_id = _require_permission_if_user_given(
        acting_user,
        Permission.RECEIVED_CHECK_ENDORSE,
        attempted_action="RECEIVED_CHECK_ENDORSE",
        entity_type="ReceivedCheck",
        details={
            "received_check_id": received_check_id,
            "endorse_date": endorse_date.isoformat(),
            "counterparty_text": counterparty_text,
            "reference_no": reference_no,
        },
    )

    effective_endorsed_by_user_id = permission_user_id if permission_user_id is not None else endorsed_by_user_id

    check = session.get(ReceivedCheck, received_check_id)

    if check is None:
        raise CheckServiceError(f"Alınan çek bulunamadı. Çek ID: {received_check_id}")

    if check.status not in {
        ReceivedCheckStatus.PORTFOLIO,
        ReceivedCheckStatus.GIVEN_TO_BANK,
        ReceivedCheckStatus.IN_COLLECTION,
    }:
        raise CheckServiceError(
            "Ciro işlemi sadece PORTFOLIO, GIVEN_TO_BANK veya IN_COLLECTION durumundaki çeklerde yapılabilir."
        )

    if check.collected_transaction_id is not None:
        raise CheckServiceError("Banka hareketi oluşmuş çek ciro edilemez.")

    cleaned_counterparty_text = _clean_required_text(counterparty_text, "Ciro edilen kişi/kurum")
    cleaned_reference_no = _clean_optional_text(reference_no) or check.reference_no
    cleaned_description = _clean_optional_text(description)

    old_values = _received_check_to_dict(check)
    previous_status = check.status

    check.status = ReceivedCheckStatus.ENDORSED

    session.flush()

    _create_received_check_movement(
        session,
        received_check=check,
        movement_type=ReceivedCheckMovementType.ENDORSED,
        movement_date=endorse_date,
        from_status=previous_status,
        to_status=ReceivedCheckStatus.ENDORSED,
        bank_account_id=None,
        counterparty_text=cleaned_counterparty_text,
        purpose_text="Alınan çek kullanıldı / ciro edildi.",
        reference_no=cleaned_reference_no,
        description=cleaned_description,
        gross_amount=check.amount,
        currency_code=check.currency_code,
        created_by_user_id=effective_endorsed_by_user_id,
    )

    write_audit_log(
        session,
        user_id=effective_endorsed_by_user_id,
        action="RECEIVED_CHECK_ENDORSED",
        entity_type="ReceivedCheck",
        entity_id=check.id,
        description=f"Alınan çek ciro edildi: {check.check_number} / {check.amount} {check.currency_code.value}",
        old_values=old_values,
        new_values=_received_check_to_dict(check),
    )

    return check


def cancel_issued_check(
    session: Session,
    *,
    issued_check_id: int,
    cancel_reason: str,
    cancelled_by_user_id: Optional[int] = None,
    acting_user: Optional[Any] = None,
) -> IssuedCheck:
    permission_user_id = _require_permission_if_user_given(
        acting_user,
        Permission.ISSUED_CHECK_CANCEL,
        attempted_action="ISSUED_CHECK_CANCEL",
        entity_type="IssuedCheck",
        details={
            "issued_check_id": issued_check_id,
            "cancel_reason": cancel_reason,
        },
    )

    effective_cancelled_by_user_id = permission_user_id if permission_user_id is not None else cancelled_by_user_id

    cleaned_cancel_reason = _clean_required_text(cancel_reason, "İptal nedeni")

    check = session.get(IssuedCheck, issued_check_id)

    if check is None:
        raise CheckServiceError(f"Yazılan çek bulunamadı. Çek ID: {issued_check_id}")

    if check.status == IssuedCheckStatus.CANCELLED:
        raise CheckServiceError("Bu çek zaten iptal edilmiş.")

    if check.status == IssuedCheckStatus.PAID:
        raise CheckServiceError("Ödenmiş çek iptal edilemez.")

    if check.paid_transaction_id is not None:
        raise CheckServiceError("Banka ödeme hareketi oluşmuş çek iptal edilemez.")

    old_values = _issued_check_to_dict(check)

    check.status = IssuedCheckStatus.CANCELLED
    check.cancelled_by_user_id = effective_cancelled_by_user_id
    check.cancelled_at = datetime.now(timezone.utc)
    check.cancel_reason = cleaned_cancel_reason

    session.flush()

    write_audit_log(
        session,
        user_id=effective_cancelled_by_user_id,
        action="ISSUED_CHECK_CANCELLED",
        entity_type="IssuedCheck",
        entity_id=check.id,
        description=f"Yazılan çek iptal edildi: {check.check_number}",
        old_values=old_values,
        new_values=_issued_check_to_dict(check),
    )

    return check


def cancel_received_check(
    session: Session,
    *,
    received_check_id: int,
    cancel_reason: str,
    cancelled_by_user_id: Optional[int] = None,
    acting_user: Optional[Any] = None,
) -> ReceivedCheck:
    permission_user_id = _require_permission_if_user_given(
        acting_user,
        Permission.RECEIVED_CHECK_CANCEL,
        attempted_action="RECEIVED_CHECK_CANCEL",
        entity_type="ReceivedCheck",
        details={
            "received_check_id": received_check_id,
            "cancel_reason": cancel_reason,
        },
    )

    effective_cancelled_by_user_id = permission_user_id if permission_user_id is not None else cancelled_by_user_id

    cleaned_cancel_reason = _clean_required_text(cancel_reason, "İptal nedeni")

    check = session.get(ReceivedCheck, received_check_id)

    if check is None:
        raise CheckServiceError(f"Alınan çek bulunamadı. Çek ID: {received_check_id}")

    if check.status == ReceivedCheckStatus.CANCELLED:
        raise CheckServiceError("Bu çek zaten iptal edilmiş.")

    if check.status in {
        ReceivedCheckStatus.COLLECTED,
        ReceivedCheckStatus.ENDORSED,
        ReceivedCheckStatus.DISCOUNTED,
    }:
        raise CheckServiceError("Tahsil edilmiş, ciro edilmiş veya iskonto edilmiş çek iptal edilemez.")

    if check.collected_transaction_id is not None:
        raise CheckServiceError("Banka hareketi oluşmuş çek iptal edilemez.")

    old_values = _received_check_to_dict(check)
    previous_status = check.status

    check.status = ReceivedCheckStatus.CANCELLED
    check.cancelled_by_user_id = effective_cancelled_by_user_id
    check.cancelled_at = datetime.now(timezone.utc)
    check.cancel_reason = cleaned_cancel_reason

    session.flush()

    _create_received_check_movement(
        session,
        received_check=check,
        movement_type=ReceivedCheckMovementType.CANCELLED,
        movement_date=date.today(),
        from_status=previous_status,
        to_status=ReceivedCheckStatus.CANCELLED,
        bank_account_id=check.collection_bank_account_id,
        counterparty_text=None,
        purpose_text="Alınan çek iptal edildi.",
        reference_no=check.reference_no,
        description=cleaned_cancel_reason,
        gross_amount=check.amount,
        currency_code=check.currency_code,
        created_by_user_id=effective_cancelled_by_user_id,
    )

    write_audit_log(
        session,
        user_id=effective_cancelled_by_user_id,
        action="RECEIVED_CHECK_CANCELLED",
        entity_type="ReceivedCheck",
        entity_id=check.id,
        description=f"Alınan çek iptal edildi: {check.check_number}",
        old_values=old_values,
        new_values=_received_check_to_dict(check),
    )

    return check