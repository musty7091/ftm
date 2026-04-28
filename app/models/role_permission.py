from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Index, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.enums import UserRole


class RolePermission(Base):
    __tablename__ = "role_permissions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    role: Mapped[UserRole] = mapped_column(
        Enum(
            UserRole,
            native_enum=False,
            validate_strings=True,
            length=30,
            name="role_permission_user_role",
        ),
        nullable=False,
    )

    permission: Mapped[str] = mapped_column(String(120), nullable=False)

    is_allowed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        UniqueConstraint(
            "role",
            "permission",
            name="uq_role_permissions_role_permission",
        ),
        Index(
            "ix_role_permissions_role",
            "role",
        ),
        Index(
            "ix_role_permissions_permission",
            "permission",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<RolePermission id={self.id} "
            f"role={self.role!r} "
            f"permission={self.permission!r} "
            f"is_allowed={self.is_allowed}>"
        )