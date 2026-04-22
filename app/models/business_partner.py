from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.enums import BusinessPartnerType


class BusinessPartner(Base):
    __tablename__ = "business_partners"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True, index=True)

    partner_type: Mapped[BusinessPartnerType] = mapped_column(
        Enum(
            BusinessPartnerType,
            native_enum=False,
            validate_strings=True,
            length=20,
            name="business_partner_type",
        ),
        nullable=False,
        default=BusinessPartnerType.CUSTOMER,
        server_default=BusinessPartnerType.CUSTOMER.value,
        index=True,
    )

    tax_office: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    tax_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)

    authorized_person: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    def __repr__(self) -> str:
        return f"<BusinessPartner id={self.id} name={self.name!r} type={self.partner_type}>"