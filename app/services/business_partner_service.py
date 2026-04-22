from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.business_partner import BusinessPartner
from app.models.enums import BusinessPartnerType
from app.services.audit_service import write_audit_log


class BusinessPartnerServiceError(ValueError):
    pass


def _clean_required_text(value: str, field_name: str) -> str:
    cleaned_value = (value or "").strip()

    if not cleaned_value:
        raise BusinessPartnerServiceError(f"{field_name} boş olamaz.")

    return cleaned_value


def _clean_optional_text(value: Optional[str]) -> Optional[str]:
    cleaned_value = (value or "").strip()

    if not cleaned_value:
        return None

    return cleaned_value


def _partner_to_dict(partner: BusinessPartner) -> dict[str, Any]:
    return {
        "id": partner.id,
        "name": partner.name,
        "partner_type": partner.partner_type.value,
        "tax_office": partner.tax_office,
        "tax_number": partner.tax_number,
        "authorized_person": partner.authorized_person,
        "phone": partner.phone,
        "email": partner.email,
        "address": partner.address,
        "notes": partner.notes,
        "is_active": partner.is_active,
    }


def get_business_partner_by_name(session: Session, name: str) -> Optional[BusinessPartner]:
    cleaned_name = _clean_required_text(name, "Cari adı")

    statement = select(BusinessPartner).where(BusinessPartner.name == cleaned_name)

    return session.execute(statement).scalar_one_or_none()


def create_business_partner(
    session: Session,
    *,
    name: str,
    partner_type: BusinessPartnerType,
    tax_office: Optional[str],
    tax_number: Optional[str],
    authorized_person: Optional[str],
    phone: Optional[str],
    email: Optional[str],
    address: Optional[str],
    notes: Optional[str],
    created_by_user_id: Optional[int],
) -> BusinessPartner:
    cleaned_name = _clean_required_text(name, "Cari adı")
    cleaned_tax_office = _clean_optional_text(tax_office)
    cleaned_tax_number = _clean_optional_text(tax_number)
    cleaned_authorized_person = _clean_optional_text(authorized_person)
    cleaned_phone = _clean_optional_text(phone)
    cleaned_email = _clean_optional_text(email)
    cleaned_address = _clean_optional_text(address)
    cleaned_notes = _clean_optional_text(notes)

    existing_partner = get_business_partner_by_name(session, cleaned_name)

    if existing_partner is not None:
        raise BusinessPartnerServiceError(f"Bu cari zaten kayıtlı: {cleaned_name}")

    partner = BusinessPartner(
        name=cleaned_name,
        partner_type=partner_type,
        tax_office=cleaned_tax_office,
        tax_number=cleaned_tax_number,
        authorized_person=cleaned_authorized_person,
        phone=cleaned_phone,
        email=cleaned_email,
        address=cleaned_address,
        notes=cleaned_notes,
        is_active=True,
    )

    session.add(partner)
    session.flush()

    write_audit_log(
        session,
        user_id=created_by_user_id,
        action="BUSINESS_PARTNER_CREATED",
        entity_type="BusinessPartner",
        entity_id=partner.id,
        description=f"Cari kart oluşturuldu: {partner.name}",
        old_values=None,
        new_values=_partner_to_dict(partner),
    )

    return partner