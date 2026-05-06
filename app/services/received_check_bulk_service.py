from dataclasses import dataclass, field
from datetime import date
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.bank import BankAccount
from app.models.check import ReceivedCheck
from app.models.enums import ReceivedCheckMovementType, ReceivedCheckStatus
from app.services.audit_service import write_audit_log
from app.services.check_service import (
    CheckServiceError,
    _clean_optional_text,
    _clean_required_text,
    _create_received_check_movement,
    _received_check_to_dict,
    _require_permission_if_user_given,
    collect_received_check,
    send_received_check_to_bank,
)
from app.services.permission_service import Permission


@dataclass(frozen=True)
class ReceivedCheckBulkItemResult:
    received_check_id: int
    success: bool
    message: str = ""


@dataclass(frozen=True)
class ReceivedCheckBulkResult:
    action_name: str
    requested_count: int
    success_count: int
    failed_count: int
    item_results: list[ReceivedCheckBulkItemResult] = field(default_factory=list)

    @property
    def is_full_success(self) -> bool:
        return self.failed_count == 0

    def success_ids(self) -> list[int]:
        return [
            item.received_check_id
            for item in self.item_results
            if item.success
        ]

    def failed_items(self) -> list[ReceivedCheckBulkItemResult]:
        return [
            item
            for item in self.item_results
            if not item.success
        ]

    def build_user_message(self) -> str:
        lines = [
            f"İşlem: {self.action_name}",
            f"Seçilen çek: {self.requested_count}",
            f"Başarılı: {self.success_count}",
            f"Başarısız: {self.failed_count}",
        ]

        failed_items = self.failed_items()

        if failed_items:
            lines.append("")
            lines.append("Başarısız kayıtlar:")

            for item in failed_items[:20]:
                lines.append(f"- Çek ID {item.received_check_id}: {item.message}")

            if len(failed_items) > 20:
                lines.append(f"- ... {len(failed_items) - 20} kayıt daha")

        return "\n".join(lines)


class ReceivedCheckBulkServiceError(CheckServiceError):
    def __init__(
        self,
        message: str,
        *,
        result: Optional[ReceivedCheckBulkResult] = None,
    ) -> None:
        super().__init__(message)
        self.result = result


def _normalize_received_check_ids(received_check_ids: list[int]) -> list[int]:
    normalized_ids: list[int] = []
    seen_ids: set[int] = set()

    for raw_id in received_check_ids:
        try:
            received_check_id = int(raw_id)
        except (TypeError, ValueError) as exc:
            raise ReceivedCheckBulkServiceError(
                f"Geçersiz alınan çek ID değeri: {raw_id}"
            ) from exc

        if received_check_id <= 0:
            raise ReceivedCheckBulkServiceError(
                f"Geçersiz alınan çek ID değeri: {received_check_id}"
            )

        if received_check_id not in seen_ids:
            normalized_ids.append(received_check_id)
            seen_ids.add(received_check_id)

    if not normalized_ids:
        raise ReceivedCheckBulkServiceError("Toplu işlem için en az bir çek seçilmelidir.")

    return normalized_ids


def _build_bulk_result(
    *,
    action_name: str,
    requested_ids: list[int],
    item_results: list[ReceivedCheckBulkItemResult],
) -> ReceivedCheckBulkResult:
    success_count = sum(1 for item in item_results if item.success)
    failed_count = len(item_results) - success_count

    return ReceivedCheckBulkResult(
        action_name=action_name,
        requested_count=len(requested_ids),
        success_count=success_count,
        failed_count=failed_count,
        item_results=item_results,
    )


def _raise_if_bulk_failed(result: ReceivedCheckBulkResult) -> None:
    if result.failed_count <= 0:
        return

    raise ReceivedCheckBulkServiceError(
        result.build_user_message(),
        result=result,
    )


def endorse_received_check(
    session: Session,
    *,
    received_check_id: int,
    endorse_date: date,
    counterparty_text: str,
    purpose_text: str,
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
            "purpose_text": purpose_text,
            "reference_no": reference_no,
        },
    )

    effective_endorsed_by_user_id = (
        permission_user_id if permission_user_id is not None else endorsed_by_user_id
    )

    check = session.get(ReceivedCheck, received_check_id)

    if check is None:
        raise CheckServiceError(f"Alınan çek bulunamadı. Çek ID: {received_check_id}")

    if check.status != ReceivedCheckStatus.PORTFOLIO:
        raise CheckServiceError(
            "Ciro işlemi sadece PORTFOLIO durumundaki alınan çeklerde yapılabilir."
        )

    if check.collected_transaction_id is not None:
        raise CheckServiceError("Tahsil hareketi oluşmuş çek ciro edilemez.")

    cleaned_counterparty_text = _clean_required_text(counterparty_text, "Kime verildi")
    cleaned_purpose_text = _clean_required_text(purpose_text, "Kullanım amacı")
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
        bank_account_id=check.collection_bank_account_id,
        counterparty_text=cleaned_counterparty_text,
        purpose_text=cleaned_purpose_text,
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
        description=(
            f"Alınan çek ciro edildi: "
            f"{check.check_number} / {check.amount} {check.currency_code.value}"
        ),
        old_values=old_values,
        new_values=_received_check_to_dict(check),
    )

    return check


def bulk_send_received_checks_to_bank(
    session: Session,
    *,
    received_check_ids: list[int],
    collection_bank_account_id: int,
    sent_date: date,
    reference_no: Optional[str],
    description: Optional[str],
    moved_by_user_id: Optional[int] = None,
    acting_user: Optional[Any] = None,
) -> ReceivedCheckBulkResult:
    normalized_ids = _normalize_received_check_ids(received_check_ids)

    item_results: list[ReceivedCheckBulkItemResult] = []

    for received_check_id in normalized_ids:
        try:
            send_received_check_to_bank(
                session,
                received_check_id=received_check_id,
                collection_bank_account_id=collection_bank_account_id,
                sent_date=sent_date,
                reference_no=reference_no,
                description=description,
                moved_by_user_id=moved_by_user_id,
                acting_user=acting_user,
            )

            item_results.append(
                ReceivedCheckBulkItemResult(
                    received_check_id=received_check_id,
                    success=True,
                    message="Bankaya tahsile verildi.",
                )
            )
        except Exception as exc:
            item_results.append(
                ReceivedCheckBulkItemResult(
                    received_check_id=received_check_id,
                    success=False,
                    message=str(exc),
                )
            )

    result = _build_bulk_result(
        action_name="Toplu Bankaya Tahsile Ver",
        requested_ids=normalized_ids,
        item_results=item_results,
    )
    _raise_if_bulk_failed(result)

    return result


def bulk_collect_received_checks(
    session: Session,
    *,
    received_check_ids: list[int],
    collection_bank_account_id: Optional[int],
    collection_date: date,
    reference_no: Optional[str],
    description: Optional[str],
    collected_by_user_id: Optional[int] = None,
    acting_user: Optional[Any] = None,
) -> ReceivedCheckBulkResult:
    normalized_ids = _normalize_received_check_ids(received_check_ids)

    item_results: list[ReceivedCheckBulkItemResult] = []

    for received_check_id in normalized_ids:
        try:
            collect_received_check(
                session,
                received_check_id=received_check_id,
                collection_bank_account_id=collection_bank_account_id,
                collection_date=collection_date,
                reference_no=reference_no,
                description=description,
                collected_by_user_id=collected_by_user_id,
                acting_user=acting_user,
            )

            item_results.append(
                ReceivedCheckBulkItemResult(
                    received_check_id=received_check_id,
                    success=True,
                    message="Tahsil edildi.",
                )
            )
        except Exception as exc:
            item_results.append(
                ReceivedCheckBulkItemResult(
                    received_check_id=received_check_id,
                    success=False,
                    message=str(exc),
                )
            )

    result = _build_bulk_result(
        action_name="Toplu Tahsil Et",
        requested_ids=normalized_ids,
        item_results=item_results,
    )
    _raise_if_bulk_failed(result)

    return result


def bulk_endorse_received_checks(
    session: Session,
    *,
    received_check_ids: list[int],
    endorse_date: date,
    counterparty_text: str,
    purpose_text: str,
    reference_no: Optional[str],
    description: Optional[str],
    endorsed_by_user_id: Optional[int] = None,
    acting_user: Optional[Any] = None,
) -> ReceivedCheckBulkResult:
    normalized_ids = _normalize_received_check_ids(received_check_ids)

    item_results: list[ReceivedCheckBulkItemResult] = []

    for received_check_id in normalized_ids:
        try:
            endorse_received_check(
                session,
                received_check_id=received_check_id,
                endorse_date=endorse_date,
                counterparty_text=counterparty_text,
                purpose_text=purpose_text,
                reference_no=reference_no,
                description=description,
                endorsed_by_user_id=endorsed_by_user_id,
                acting_user=acting_user,
            )

            item_results.append(
                ReceivedCheckBulkItemResult(
                    received_check_id=received_check_id,
                    success=True,
                    message="Ciro edildi.",
                )
            )
        except Exception as exc:
            item_results.append(
                ReceivedCheckBulkItemResult(
                    received_check_id=received_check_id,
                    success=False,
                    message=str(exc),
                )
            )

    result = _build_bulk_result(
        action_name="Toplu Ciro Et",
        requested_ids=normalized_ids,
        item_results=item_results,
    )
    _raise_if_bulk_failed(result)

    return result
