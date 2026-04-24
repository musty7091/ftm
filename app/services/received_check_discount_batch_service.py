from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.bank import BankAccount
from app.models.check import (
    ReceivedCheck,
    ReceivedCheckDiscountBatch,
    ReceivedCheckDiscountBatchItem,
    ReceivedCheckMovement,
)
from app.models.enums import (
    BankTransactionStatus,
    CurrencyCode,
    FinancialSourceType,
    ReceivedCheckMovementType,
    ReceivedCheckStatus,
    TransactionDirection,
)
from app.services.audit_service import write_audit_log
from app.services.bank_transaction_service import BankTransactionServiceError, create_bank_transaction
from app.services.permission_audit_service import require_permission_with_audit
from app.services.permission_service import Permission, PermissionServiceError
from app.utils.decimal_utils import Q2, Q6, money, rate


DEFAULT_BSIV_RATE = Decimal("0.300000")


class ReceivedCheckDiscountBatchServiceError(ValueError):
    pass


@dataclass(frozen=True)
class DiscountBatchCheckInput:
    received_check_id: int
    check_number: str
    due_date: date
    gross_amount: Decimal
    currency_code: str


@dataclass(frozen=True)
class DiscountBatchItemCalculation:
    received_check_id: int
    check_number: str
    due_date: date
    gross_amount: Decimal
    days_to_due: int
    annual_interest_rate: Decimal
    day_basis: int
    interest_expense_amount: Decimal
    commission_rate: Decimal
    commission_amount: Decimal
    bsiv_rate: Decimal
    bsiv_amount: Decimal
    total_expense_amount: Decimal
    net_amount: Decimal
    currency_code: str


@dataclass(frozen=True)
class DiscountBatchCalculationResult:
    item_calculations: list[DiscountBatchItemCalculation]
    selected_check_count: int
    currency_code: str
    discount_date: date
    annual_interest_rate: Decimal
    day_basis: int
    commission_rate: Decimal
    bsiv_rate: Decimal
    total_gross_amount: Decimal
    weighted_average_days_to_due: Decimal
    total_interest_expense_amount: Decimal
    total_commission_amount: Decimal
    total_bsiv_amount: Decimal
    total_discount_expense_amount: Decimal
    net_bank_amount: Decimal


def _normalize_currency_code(value: Any) -> str:
    if value is None:
        raise ReceivedCheckDiscountBatchServiceError("Para birimi boş olamaz.")

    if hasattr(value, "value"):
        normalized_value = str(value.value).strip().upper()
    else:
        normalized_value = str(value).strip().upper()

    if not normalized_value:
        raise ReceivedCheckDiscountBatchServiceError("Para birimi boş olamaz.")

    return normalized_value


def _normalize_currency_enum(value: Any) -> CurrencyCode:
    if isinstance(value, CurrencyCode):
        return value

    try:
        return CurrencyCode(str(value).strip().upper())
    except ValueError as exc:
        raise ReceivedCheckDiscountBatchServiceError(f"Geçersiz para birimi: {value}") from exc


def _validate_received_check_id(value: Any) -> int:
    try:
        normalized_value = int(value)
    except (TypeError, ValueError) as exc:
        raise ReceivedCheckDiscountBatchServiceError("Alınan çek ID sayısal olmalıdır.") from exc

    if normalized_value <= 0:
        raise ReceivedCheckDiscountBatchServiceError("Alınan çek ID sıfırdan büyük olmalıdır.")

    return normalized_value


def _validate_day_basis(value: Any) -> int:
    try:
        normalized_value = int(value)
    except (TypeError, ValueError) as exc:
        raise ReceivedCheckDiscountBatchServiceError("Gün bazı sayısal olmalıdır.") from exc

    if normalized_value not in {360, 365}:
        raise ReceivedCheckDiscountBatchServiceError("Gün bazı sadece 360 veya 365 olabilir.")

    return normalized_value


def _validate_annual_interest_rate(value: Any) -> Decimal:
    cleaned_rate = rate(value, field_name="Yıllık faiz oranı")

    if cleaned_rate <= Decimal("0.000000"):
        raise ReceivedCheckDiscountBatchServiceError("Yıllık faiz oranı sıfırdan büyük olmalıdır.")

    if cleaned_rate >= Decimal("1000.000000"):
        raise ReceivedCheckDiscountBatchServiceError("Yıllık faiz oranı 1000'den küçük olmalıdır.")

    return cleaned_rate


def _validate_commission_rate(value: Any) -> Decimal:
    cleaned_rate = rate(value, field_name="Komisyon oranı")

    if cleaned_rate < Decimal("0.000000"):
        raise ReceivedCheckDiscountBatchServiceError("Komisyon oranı negatif olamaz.")

    if cleaned_rate >= Decimal("100.000000"):
        raise ReceivedCheckDiscountBatchServiceError("Komisyon oranı 100'den küçük olmalıdır.")

    return cleaned_rate


def _validate_bsiv_rate(value: Any) -> Decimal:
    cleaned_rate = rate(value, field_name="BSİV oranı")

    if cleaned_rate < Decimal("0.000000"):
        raise ReceivedCheckDiscountBatchServiceError("BSİV oranı negatif olamaz.")

    if cleaned_rate >= Decimal("100.000000"):
        raise ReceivedCheckDiscountBatchServiceError("BSİV oranı 100'den küçük olmalıdır.")

    return cleaned_rate


def _validate_discount_date(value: Any) -> date:
    if not isinstance(value, date):
        raise ReceivedCheckDiscountBatchServiceError("İskonto tarihi geçerli bir tarih olmalıdır.")

    return value


def _validate_due_date(value: Any) -> date:
    if not isinstance(value, date):
        raise ReceivedCheckDiscountBatchServiceError("Çek vade tarihi geçerli bir tarih olmalıdır.")

    return value


def _clean_optional_text(value: Optional[str]) -> Optional[str]:
    cleaned_value = str(value or "").strip()

    if not cleaned_value:
        return None

    return cleaned_value


def _calculate_days_to_due(*, discount_date: date, due_date: date) -> int:
    days_to_due = (due_date - discount_date).days

    if days_to_due < 0:
        raise ReceivedCheckDiscountBatchServiceError(
            "Vadesi geçmiş çek iskonto paketine eklenemez."
        )

    return days_to_due


def _calculate_interest_expense_amount(
    *,
    gross_amount: Decimal,
    annual_interest_rate: Decimal,
    days_to_due: int,
    day_basis: int,
) -> Decimal:
    calculated_amount = (
        gross_amount
        * annual_interest_rate
        / Decimal("100")
        * Decimal(str(days_to_due))
        / Decimal(str(day_basis))
    )

    return calculated_amount.quantize(Q2)


def _calculate_commission_amount(
    *,
    gross_amount: Decimal,
    commission_rate: Decimal,
) -> Decimal:
    calculated_amount = gross_amount * commission_rate / Decimal("100")

    return calculated_amount.quantize(Q2)


def _calculate_bsiv_amount(
    *,
    interest_expense_amount: Decimal,
    commission_amount: Decimal,
    bsiv_rate: Decimal,
) -> Decimal:
    calculated_amount = (
        (interest_expense_amount + commission_amount)
        * bsiv_rate
        / Decimal("100")
    )

    return calculated_amount.quantize(Q2)


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
        raise ReceivedCheckDiscountBatchServiceError(str(exc)) from exc


def _build_check_input_from_any(value: Any) -> DiscountBatchCheckInput:
    received_check_id = _validate_received_check_id(
        getattr(value, "received_check_id", None)
        if not hasattr(value, "id")
        else getattr(value, "id")
    )

    check_number = str(getattr(value, "check_number", "") or "").strip()

    if not check_number:
        raise ReceivedCheckDiscountBatchServiceError("Çek numarası boş olamaz.")

    due_date = _validate_due_date(getattr(value, "due_date", None))
    gross_amount = money(
        getattr(value, "gross_amount", None)
        if hasattr(value, "gross_amount")
        else getattr(value, "amount", None),
        field_name="Çek tutarı",
    )
    currency_code = _normalize_currency_code(getattr(value, "currency_code", None))

    return DiscountBatchCheckInput(
        received_check_id=received_check_id,
        check_number=check_number,
        due_date=due_date,
        gross_amount=gross_amount,
        currency_code=currency_code,
    )


def normalize_discount_batch_check_inputs(
    checks: list[DiscountBatchCheckInput] | list[Any],
) -> list[DiscountBatchCheckInput]:
    if not checks:
        raise ReceivedCheckDiscountBatchServiceError("İskonto paketi için en az bir çek seçilmelidir.")

    normalized_checks: list[DiscountBatchCheckInput] = []

    used_check_ids: set[int] = set()

    for check in checks:
        if isinstance(check, DiscountBatchCheckInput):
            normalized_check = DiscountBatchCheckInput(
                received_check_id=_validate_received_check_id(check.received_check_id),
                check_number=str(check.check_number or "").strip(),
                due_date=_validate_due_date(check.due_date),
                gross_amount=money(check.gross_amount, field_name="Çek tutarı"),
                currency_code=_normalize_currency_code(check.currency_code),
            )
        else:
            normalized_check = _build_check_input_from_any(check)

        if not normalized_check.check_number:
            raise ReceivedCheckDiscountBatchServiceError("Çek numarası boş olamaz.")

        if normalized_check.gross_amount <= Decimal("0.00"):
            raise ReceivedCheckDiscountBatchServiceError("Çek tutarı sıfırdan büyük olmalıdır.")

        if normalized_check.received_check_id in used_check_ids:
            raise ReceivedCheckDiscountBatchServiceError(
                f"Aynı çek pakete birden fazla kez eklenemez. Çek ID: {normalized_check.received_check_id}"
            )

        used_check_ids.add(normalized_check.received_check_id)
        normalized_checks.append(normalized_check)

    currency_codes = {check.currency_code for check in normalized_checks}

    if len(currency_codes) != 1:
        raise ReceivedCheckDiscountBatchServiceError(
            "Aynı iskonto paketinde farklı para birimlerinden çekler bulunamaz."
        )

    return normalized_checks


def calculate_received_check_discount_batch(
    *,
    checks: list[DiscountBatchCheckInput] | list[Any],
    discount_date: date,
    annual_interest_rate: Any,
    commission_rate: Any,
    day_basis: int = 365,
    bsiv_rate: Any = DEFAULT_BSIV_RATE,
) -> DiscountBatchCalculationResult:
    normalized_discount_date = _validate_discount_date(discount_date)
    normalized_annual_interest_rate = _validate_annual_interest_rate(annual_interest_rate)
    normalized_commission_rate = _validate_commission_rate(commission_rate)
    normalized_bsiv_rate = _validate_bsiv_rate(bsiv_rate)
    normalized_day_basis = _validate_day_basis(day_basis)
    normalized_checks = normalize_discount_batch_check_inputs(checks)

    item_calculations: list[DiscountBatchItemCalculation] = []

    total_gross_amount = Decimal("0.00")
    total_weighted_days_amount = Decimal("0.000000")
    total_interest_expense_amount = Decimal("0.00")
    total_commission_amount = Decimal("0.00")
    total_bsiv_amount = Decimal("0.00")
    total_discount_expense_amount = Decimal("0.00")
    net_bank_amount = Decimal("0.00")

    currency_code = normalized_checks[0].currency_code

    for check in normalized_checks:
        days_to_due = _calculate_days_to_due(
            discount_date=normalized_discount_date,
            due_date=check.due_date,
        )

        interest_expense_amount = _calculate_interest_expense_amount(
            gross_amount=check.gross_amount,
            annual_interest_rate=normalized_annual_interest_rate,
            days_to_due=days_to_due,
            day_basis=normalized_day_basis,
        )

        commission_amount = _calculate_commission_amount(
            gross_amount=check.gross_amount,
            commission_rate=normalized_commission_rate,
        )

        bsiv_amount = _calculate_bsiv_amount(
            interest_expense_amount=interest_expense_amount,
            commission_amount=commission_amount,
            bsiv_rate=normalized_bsiv_rate,
        )

        total_expense_amount = (
            interest_expense_amount
            + commission_amount
            + bsiv_amount
        ).quantize(Q2)
        net_amount = (check.gross_amount - total_expense_amount).quantize(Q2)

        if net_amount <= Decimal("0.00"):
            raise ReceivedCheckDiscountBatchServiceError(
                f"Net tutar sıfırdan büyük olmalıdır. Çek ID: {check.received_check_id}"
            )

        item_calculation = DiscountBatchItemCalculation(
            received_check_id=check.received_check_id,
            check_number=check.check_number,
            due_date=check.due_date,
            gross_amount=check.gross_amount,
            days_to_due=days_to_due,
            annual_interest_rate=normalized_annual_interest_rate,
            day_basis=normalized_day_basis,
            interest_expense_amount=interest_expense_amount,
            commission_rate=normalized_commission_rate,
            commission_amount=commission_amount,
            bsiv_rate=normalized_bsiv_rate,
            bsiv_amount=bsiv_amount,
            total_expense_amount=total_expense_amount,
            net_amount=net_amount,
            currency_code=check.currency_code,
        )

        item_calculations.append(item_calculation)

        total_gross_amount = (total_gross_amount + check.gross_amount).quantize(Q2)
        total_weighted_days_amount += check.gross_amount * Decimal(str(days_to_due))
        total_interest_expense_amount = (
            total_interest_expense_amount + interest_expense_amount
        ).quantize(Q2)
        total_commission_amount = (total_commission_amount + commission_amount).quantize(Q2)
        total_bsiv_amount = (total_bsiv_amount + bsiv_amount).quantize(Q2)
        total_discount_expense_amount = (
            total_discount_expense_amount + total_expense_amount
        ).quantize(Q2)
        net_bank_amount = (net_bank_amount + net_amount).quantize(Q2)

    if total_gross_amount <= Decimal("0.00"):
        raise ReceivedCheckDiscountBatchServiceError("Toplam çek tutarı sıfırdan büyük olmalıdır.")

    weighted_average_days_to_due = (
        total_weighted_days_amount / total_gross_amount
    ).quantize(Q6)

    return DiscountBatchCalculationResult(
        item_calculations=item_calculations,
        selected_check_count=len(item_calculations),
        currency_code=currency_code,
        discount_date=normalized_discount_date,
        annual_interest_rate=normalized_annual_interest_rate,
        day_basis=normalized_day_basis,
        commission_rate=normalized_commission_rate,
        bsiv_rate=normalized_bsiv_rate,
        total_gross_amount=total_gross_amount,
        weighted_average_days_to_due=weighted_average_days_to_due,
        total_interest_expense_amount=total_interest_expense_amount,
        total_commission_amount=total_commission_amount,
        total_bsiv_amount=total_bsiv_amount,
        total_discount_expense_amount=total_discount_expense_amount,
        net_bank_amount=net_bank_amount,
    )


def _received_check_discount_batch_to_dict(batch: ReceivedCheckDiscountBatch) -> dict[str, Any]:
    return {
        "id": batch.id,
        "bank_account_id": batch.bank_account_id,
        "bank_transaction_id": batch.bank_transaction_id,
        "discount_date": batch.discount_date.isoformat(),
        "annual_interest_rate": str(batch.annual_interest_rate),
        "day_basis": batch.day_basis,
        "commission_rate": str(batch.commission_rate),
        "bsiv_rate": str(batch.bsiv_rate),
        "total_gross_amount": str(batch.total_gross_amount),
        "total_interest_expense_amount": str(batch.total_interest_expense_amount),
        "total_commission_amount": str(batch.total_commission_amount),
        "total_bsiv_amount": str(batch.total_bsiv_amount),
        "total_discount_expense_amount": str(batch.total_discount_expense_amount),
        "net_bank_amount": str(batch.net_bank_amount),
        "currency_code": batch.currency_code.value,
        "reference_no": batch.reference_no,
        "description": batch.description,
        "created_by_user_id": batch.created_by_user_id,
    }


def _received_check_discount_batch_item_to_dict(item: ReceivedCheckDiscountBatchItem) -> dict[str, Any]:
    return {
        "id": item.id,
        "batch_id": item.batch_id,
        "received_check_id": item.received_check_id,
        "due_date": item.due_date.isoformat(),
        "gross_amount": str(item.gross_amount),
        "days_to_due": item.days_to_due,
        "annual_interest_rate": str(item.annual_interest_rate),
        "day_basis": item.day_basis,
        "interest_expense_amount": str(item.interest_expense_amount),
        "commission_rate": str(item.commission_rate),
        "commission_amount": str(item.commission_amount),
        "bsiv_rate": str(item.bsiv_rate),
        "bsiv_amount": str(item.bsiv_amount),
        "total_expense_amount": str(item.total_expense_amount),
        "net_amount": str(item.net_amount),
        "currency_code": item.currency_code.value,
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


def _create_discount_movement(
    session: Session,
    *,
    received_check: ReceivedCheck,
    movement_date: date,
    from_status: ReceivedCheckStatus,
    bank_account_id: int,
    counterparty_text: str,
    reference_no: Optional[str],
    description: Optional[str],
    gross_amount: Decimal,
    annual_interest_rate: Decimal,
    total_expense_amount: Decimal,
    net_amount: Decimal,
    created_by_user_id: Optional[int],
) -> ReceivedCheckMovement:
    movement = ReceivedCheckMovement(
        received_check_id=received_check.id,
        movement_type=ReceivedCheckMovementType.DISCOUNTED,
        movement_date=movement_date,
        from_status=from_status,
        to_status=ReceivedCheckStatus.DISCOUNTED,
        bank_account_id=bank_account_id,
        counterparty_text=_clean_optional_text(counterparty_text),
        purpose_text="Alınan çek çoklu iskonto paketi ile bankaya kırdırıldı.",
        reference_no=_clean_optional_text(reference_no),
        description=_clean_optional_text(description),
        gross_amount=gross_amount,
        currency_code=received_check.currency_code,
        discount_rate=annual_interest_rate,
        discount_expense_amount=total_expense_amount,
        net_bank_amount=net_amount,
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


def create_received_check_discount_batch(
    session: Session,
    *,
    bank_account_id: int,
    received_check_ids: list[int],
    discount_date: date,
    annual_interest_rate: Any,
    commission_rate: Any,
    day_basis: int,
    reference_no: Optional[str],
    description: Optional[str],
    bsiv_rate: Any = DEFAULT_BSIV_RATE,
    created_by_user_id: Optional[int] = None,
    acting_user: Optional[Any] = None,
) -> ReceivedCheckDiscountBatch:
    permission_user_id = _require_permission_if_user_given(
        acting_user,
        Permission.RECEIVED_CHECK_DISCOUNT,
        attempted_action="RECEIVED_CHECK_DISCOUNT_BATCH_CREATE",
        entity_type="ReceivedCheckDiscountBatch",
        details={
            "bank_account_id": bank_account_id,
            "received_check_ids": received_check_ids,
            "discount_date": discount_date.isoformat(),
            "annual_interest_rate": str(annual_interest_rate),
            "commission_rate": str(commission_rate),
            "bsiv_rate": str(bsiv_rate),
            "day_basis": day_basis,
            "reference_no": reference_no,
        },
    )

    effective_created_by_user_id = (
        permission_user_id if permission_user_id is not None else created_by_user_id
    )

    if not received_check_ids:
        raise ReceivedCheckDiscountBatchServiceError("İskonto paketi için en az bir çek seçilmelidir.")

    normalized_received_check_ids = [
        _validate_received_check_id(received_check_id)
        for received_check_id in received_check_ids
    ]

    if len(set(normalized_received_check_ids)) != len(normalized_received_check_ids):
        raise ReceivedCheckDiscountBatchServiceError("Aynı çek pakete birden fazla kez eklenemez.")

    bank_account = session.get(BankAccount, bank_account_id)

    if bank_account is None:
        raise ReceivedCheckDiscountBatchServiceError(f"Banka hesabı bulunamadı. Hesap ID: {bank_account_id}")

    if not bank_account.is_active:
        raise ReceivedCheckDiscountBatchServiceError("Pasif banka hesabına iskonto girişi yapılamaz.")

    statement = (
        select(ReceivedCheck)
        .where(ReceivedCheck.id.in_(normalized_received_check_ids))
        .with_for_update()
    )

    checks = list(session.execute(statement).scalars().all())

    found_check_ids = {check.id for check in checks}
    missing_check_ids = [
        received_check_id
        for received_check_id in normalized_received_check_ids
        if received_check_id not in found_check_ids
    ]

    if missing_check_ids:
        raise ReceivedCheckDiscountBatchServiceError(
            f"Alınan çek bulunamadı. Eksik çek ID listesi: {missing_check_ids}"
        )

    checks_by_id = {check.id: check for check in checks}
    ordered_checks = [
        checks_by_id[received_check_id]
        for received_check_id in normalized_received_check_ids
    ]

    allowed_statuses = {
        ReceivedCheckStatus.PORTFOLIO,
        ReceivedCheckStatus.GIVEN_TO_BANK,
        ReceivedCheckStatus.IN_COLLECTION,
    }

    for check in ordered_checks:
        if check.status not in allowed_statuses:
            raise ReceivedCheckDiscountBatchServiceError(
                f"Sadece PORTFOLIO, GIVEN_TO_BANK veya IN_COLLECTION durumundaki çekler iskonto paketine eklenebilir. "
                f"Çek ID: {check.id}, Durum: {check.status.value}"
            )

        if check.collected_transaction_id is not None:
            raise ReceivedCheckDiscountBatchServiceError(
                f"Banka hareketi oluşmuş çek iskonto paketine eklenemez. Çek ID: {check.id}"
            )

        if check.currency_code != bank_account.currency_code:
            raise ReceivedCheckDiscountBatchServiceError(
                f"Çek para birimi ile banka hesabı para birimi aynı olmalıdır. "
                f"Çek ID: {check.id}, Çek: {check.currency_code.value}, Hesap: {bank_account.currency_code.value}"
            )

    calculation_result = calculate_received_check_discount_batch(
        checks=ordered_checks,
        discount_date=discount_date,
        annual_interest_rate=annual_interest_rate,
        commission_rate=commission_rate,
        day_basis=day_basis,
        bsiv_rate=bsiv_rate,
    )

    batch_currency_code = _normalize_currency_enum(calculation_result.currency_code)
    cleaned_reference_no = _clean_optional_text(reference_no)
    cleaned_description = _clean_optional_text(description)

    batch = ReceivedCheckDiscountBatch(
        bank_account_id=bank_account.id,
        bank_transaction_id=None,
        discount_date=calculation_result.discount_date,
        annual_interest_rate=calculation_result.annual_interest_rate,
        day_basis=calculation_result.day_basis,
        commission_rate=calculation_result.commission_rate,
        bsiv_rate=calculation_result.bsiv_rate,
        total_gross_amount=calculation_result.total_gross_amount,
        total_interest_expense_amount=calculation_result.total_interest_expense_amount,
        total_commission_amount=calculation_result.total_commission_amount,
        total_bsiv_amount=calculation_result.total_bsiv_amount,
        total_discount_expense_amount=calculation_result.total_discount_expense_amount,
        net_bank_amount=calculation_result.net_bank_amount,
        currency_code=batch_currency_code,
        reference_no=cleaned_reference_no,
        description=cleaned_description,
        created_by_user_id=effective_created_by_user_id,
    )

    session.add(batch)
    session.flush()

    try:
        bank_transaction = create_bank_transaction(
            session,
            bank_account_id=bank_account.id,
            transaction_date=calculation_result.discount_date,
            value_date=calculation_result.discount_date,
            direction=TransactionDirection.IN,
            status=BankTransactionStatus.REALIZED,
            amount=calculation_result.net_bank_amount,
            currency_code=batch_currency_code,
            source_type=FinancialSourceType.OTHER,
            source_id=batch.id,
            reference_no=cleaned_reference_no,
            description=(
                f"Alınan çek iskonto paketi: Paket ID {batch.id} | "
                f"Brüt: {calculation_result.total_gross_amount} {batch_currency_code.value} | "
                f"Faiz: {calculation_result.total_interest_expense_amount} | "
                f"Komisyon: {calculation_result.total_commission_amount} | "
                f"BSİV: {calculation_result.total_bsiv_amount} | "
                f"Net: {calculation_result.net_bank_amount}"
                if not cleaned_description
                else (
                    f"Alınan çek iskonto paketi: Paket ID {batch.id} | "
                    f"Brüt: {calculation_result.total_gross_amount} {batch_currency_code.value} | "
                    f"Faiz: {calculation_result.total_interest_expense_amount} | "
                    f"Komisyon: {calculation_result.total_commission_amount} | "
                    f"BSİV: {calculation_result.total_bsiv_amount} | "
                    f"Net: {calculation_result.net_bank_amount} - {cleaned_description}"
                )
            ),
            created_by_user_id=effective_created_by_user_id,
        )
    except BankTransactionServiceError as exc:
        raise ReceivedCheckDiscountBatchServiceError(
            f"İskonto paketi banka hareketi oluşturulamadı: {exc}"
        ) from exc

    batch.bank_transaction_id = bank_transaction.id
    session.flush()

    calculation_by_check_id = {
        item_calculation.received_check_id: item_calculation
        for item_calculation in calculation_result.item_calculations
    }

    bank_counterparty_text = (
        f"{bank_account.bank.name} / {bank_account.account_name}"
        if bank_account.bank
        else bank_account.account_name
    )

    for check in ordered_checks:
        item_calculation = calculation_by_check_id[check.id]

        item = ReceivedCheckDiscountBatchItem(
            batch_id=batch.id,
            received_check_id=check.id,
            due_date=item_calculation.due_date,
            gross_amount=item_calculation.gross_amount,
            days_to_due=item_calculation.days_to_due,
            annual_interest_rate=item_calculation.annual_interest_rate,
            day_basis=item_calculation.day_basis,
            interest_expense_amount=item_calculation.interest_expense_amount,
            commission_rate=item_calculation.commission_rate,
            commission_amount=item_calculation.commission_amount,
            bsiv_rate=item_calculation.bsiv_rate,
            bsiv_amount=item_calculation.bsiv_amount,
            total_expense_amount=item_calculation.total_expense_amount,
            net_amount=item_calculation.net_amount,
            currency_code=_normalize_currency_enum(item_calculation.currency_code),
        )

        session.add(item)
        session.flush()

        write_audit_log(
            session,
            user_id=effective_created_by_user_id,
            action="RECEIVED_CHECK_DISCOUNT_BATCH_ITEM_CREATED",
            entity_type="ReceivedCheckDiscountBatchItem",
            entity_id=item.id,
            description=f"İskonto paketi çek satırı oluşturuldu. Paket ID: {batch.id}, Çek ID: {check.id}",
            old_values=None,
            new_values=_received_check_discount_batch_item_to_dict(item),
        )

        old_check_values = _received_check_to_dict(check)
        previous_status = check.status

        check.status = ReceivedCheckStatus.DISCOUNTED
        check.collection_bank_account_id = bank_account.id

        session.flush()

        movement_description_parts = [
            f"Paket ID: {batch.id}",
            f"Yıllık faiz oranı: %{item_calculation.annual_interest_rate}",
            f"Gün bazı: {item_calculation.day_basis}",
            f"Vadeye kalan gün: {item_calculation.days_to_due}",
            f"Faiz kesintisi: {item_calculation.interest_expense_amount}",
            f"Komisyon oranı: %{item_calculation.commission_rate}",
            f"Komisyon: {item_calculation.commission_amount}",
            f"BSİV oranı: %{item_calculation.bsiv_rate}",
            f"BSİV: {item_calculation.bsiv_amount}",
            f"Toplam kesinti: {item_calculation.total_expense_amount}",
            f"Net banka girişi: {item_calculation.net_amount}",
        ]

        if cleaned_description:
            movement_description_parts.append(cleaned_description)

        _create_discount_movement(
            session,
            received_check=check,
            movement_date=calculation_result.discount_date,
            from_status=previous_status,
            bank_account_id=bank_account.id,
            counterparty_text=bank_counterparty_text,
            reference_no=cleaned_reference_no,
            description=" | ".join(movement_description_parts),
            gross_amount=item_calculation.gross_amount,
            annual_interest_rate=item_calculation.annual_interest_rate,
            total_expense_amount=item_calculation.total_expense_amount,
            net_amount=item_calculation.net_amount,
            created_by_user_id=effective_created_by_user_id,
        )

        write_audit_log(
            session,
            user_id=effective_created_by_user_id,
            action="RECEIVED_CHECK_DISCOUNTED_IN_BATCH",
            entity_type="ReceivedCheck",
            entity_id=check.id,
            description=(
                f"Alınan çek iskonto paketi içinde kırdırıldı: "
                f"Paket ID {batch.id}, Çek {check.check_number}, "
                f"Brüt {item_calculation.gross_amount} {check.currency_code.value}, "
                f"BSİV {item_calculation.bsiv_amount}, "
                f"Net {item_calculation.net_amount}"
            ),
            old_values=old_check_values,
            new_values=_received_check_to_dict(check),
        )

    write_audit_log(
        session,
        user_id=effective_created_by_user_id,
        action="RECEIVED_CHECK_DISCOUNT_BATCH_CREATED",
        entity_type="ReceivedCheckDiscountBatch",
        entity_id=batch.id,
        description=(
            f"Çoklu alınan çek iskonto paketi oluşturuldu. "
            f"Paket ID: {batch.id}, Çek sayısı: {calculation_result.selected_check_count}, "
            f"Brüt: {calculation_result.total_gross_amount} {batch_currency_code.value}, "
            f"BSİV: {calculation_result.total_bsiv_amount} {batch_currency_code.value}, "
            f"Net: {calculation_result.net_bank_amount} {batch_currency_code.value}"
        ),
        old_values=None,
        new_values=_received_check_discount_batch_to_dict(batch),
    )

    return batch