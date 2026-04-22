from typing import Optional

from sqlalchemy import select

from app.db.session import session_scope
from app.models.enums import BusinessPartnerType
from app.models.user import User
from app.services.business_partner_service import (
    BusinessPartnerServiceError,
    create_business_partner,
)


def _ask_required_text(label: str, default_value: str = "") -> str:
    while True:
        if default_value:
            value = input(f"{label} [{default_value}]: ").strip() or default_value
        else:
            value = input(f"{label}: ").strip()

        if value:
            return value

        print(f"{label} boş olamaz.")


def _ask_optional_text(label: str, default_value: str = "") -> str:
    if default_value:
        return input(f"{label} [{default_value}]: ").strip() or default_value

    return input(f"{label}: ").strip()


def _select_partner_type() -> BusinessPartnerType:
    options = list(BusinessPartnerType)

    print("")
    print("Cari türü seç:")

    for index, option in enumerate(options, start=1):
        label = {
            BusinessPartnerType.CUSTOMER: "Müşteri",
            BusinessPartnerType.SUPPLIER: "Tedarikçi",
            BusinessPartnerType.BOTH: "Müşteri + Tedarikçi",
        }[option]

        print(f"{index}. {option.value} - {label}")

    while True:
        value = input("Seçim [1]: ").strip() or "1"

        if not value.isdigit():
            print("Lütfen sayı gir.")
            continue

        selected_index = int(value)

        if 1 <= selected_index <= len(options):
            return options[selected_index - 1]

        print("Geçersiz seçim.")


def _get_admin_user_id() -> Optional[int]:
    with session_scope() as session:
        user = session.execute(select(User).where(User.username == "admin")).scalar_one_or_none()

        if user is None:
            return None

        return user.id


def main() -> None:
    print("FTM cari kart oluşturma")
    print("")

    name = _ask_required_text("Cari adı")
    partner_type = _select_partner_type()
    tax_office = _ask_optional_text("Vergi dairesi")
    tax_number = _ask_optional_text("Vergi / kimlik no")
    authorized_person = _ask_optional_text("Yetkili kişi")
    phone = _ask_optional_text("Telefon")
    email = _ask_optional_text("E-posta")
    address = _ask_optional_text("Adres")
    notes = _ask_optional_text("Not")

    admin_user_id = _get_admin_user_id()

    try:
        with session_scope() as session:
            partner = create_business_partner(
                session,
                name=name,
                partner_type=partner_type,
                tax_office=tax_office,
                tax_number=tax_number,
                authorized_person=authorized_person,
                phone=phone,
                email=email,
                address=address,
                notes=notes,
                created_by_user_id=admin_user_id,
            )

            session.flush()

            print("")
            print("Cari kart başarıyla oluşturuldu.")
            print(f"Cari ID   : {partner.id}")
            print(f"Cari adı  : {partner.name}")
            print(f"Cari türü : {partner.partner_type.value}")

    except BusinessPartnerServiceError as exc:
        print("")
        print(f"Cari kart oluşturulamadı: {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()