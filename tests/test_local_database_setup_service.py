from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Generator

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.session import Base
from app.models.enums import UserRole
from app.models.role_permission import RolePermission
from app.models.user import User
from app.services.permission_service import Permission
import app.services.local_database_setup_service as local_setup_service


@dataclass(frozen=True)
class FakeSqliteSettings:
    database_engine: str
    database_url: str
    sqlite_database_path: Path
    database_echo: bool = False

    @property
    def is_sqlite(self) -> bool:
        return self.database_engine == "sqlite"

    @property
    def is_postgresql(self) -> bool:
        return self.database_engine == "postgresql"


@dataclass(frozen=True)
class FakePostgresqlSettings:
    database_engine: str = "postgresql"
    database_url: str = "postgresql+psycopg://fake:fake@localhost:5432/fake"
    sqlite_database_path: Path = Path("data/ftm_local.db")
    database_echo: bool = False

    @property
    def is_sqlite(self) -> bool:
        return False

    @property
    def is_postgresql(self) -> bool:
        return True


def _configure_service_for_temp_sqlite(
    *,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Path:
    sqlite_file = tmp_path / "ftm_local.db"

    test_engine = create_engine(
        f"sqlite:///{sqlite_file.as_posix()}",
        future=True,
        connect_args={
            "check_same_thread": False,
        },
    )

    TestSessionLocal = sessionmaker(
        bind=test_engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        future=True,
    )

    @contextmanager
    def test_session_scope() -> Generator[Session, None, None]:
        session = TestSessionLocal()

        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    fake_settings = FakeSqliteSettings(
        database_engine="sqlite",
        database_url=f"sqlite:///{sqlite_file.as_posix()}",
        sqlite_database_path=sqlite_file,
    )

    monkeypatch.setattr(local_setup_service, "settings", fake_settings)
    monkeypatch.setattr(local_setup_service, "engine", test_engine)
    monkeypatch.setattr(local_setup_service, "session_scope", test_session_scope)

    return sqlite_file


def test_ensure_sqlite_mode_rejects_postgresql_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(local_setup_service, "settings", FakePostgresqlSettings())

    with pytest.raises(local_setup_service.LocalDatabaseSetupServiceError):
        local_setup_service.ensure_sqlite_mode()


def test_prepare_sqlite_database_creates_tables_and_role_permissions(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    sqlite_file = _configure_service_for_temp_sqlite(
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )

    status = local_setup_service.prepare_sqlite_database()

    assert sqlite_file.exists()
    assert status.database_engine == "sqlite"
    assert status.sqlite_database_file_exists is True
    assert status.table_count > 0
    assert status.missing_table_names == []
    assert status.admin_user_exists is False
    assert status.role_permission_row_count == len(UserRole) * len(Permission)
    assert status.is_ready_for_login is False


def test_create_initial_admin_user_creates_admin_and_makes_database_ready(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _configure_service_for_temp_sqlite(
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )

    result = local_setup_service.create_initial_admin_user(
        username="admin",
        full_name="Sistem Yöneticisi",
        password="123456",
        email="admin@example.com",
        must_change_password=True,
    )

    assert result.user_id > 0
    assert result.username == "admin"
    assert result.full_name == "Sistem Yöneticisi"
    assert result.email == "admin@example.com"
    assert result.role == UserRole.ADMIN.value
    assert result.must_change_password is True

    status = local_setup_service.get_local_database_setup_status()

    assert status.admin_user_exists is True
    assert status.role_permission_row_count == len(UserRole) * len(Permission)
    assert status.is_ready_for_login is True


def test_create_initial_admin_user_rejects_second_admin_creation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _configure_service_for_temp_sqlite(
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )

    local_setup_service.create_initial_admin_user(
        username="admin",
        full_name="Sistem Yöneticisi",
        password="123456",
        email="admin@example.com",
        must_change_password=False,
    )

    with pytest.raises(local_setup_service.LocalDatabaseSetupServiceError):
        local_setup_service.create_initial_admin_user(
            username="admin2",
            full_name="İkinci Admin",
            password="123456",
            email="admin2@example.com",
            must_change_password=False,
        )


def test_prepare_sqlite_database_writes_expected_admin_permissions(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _configure_service_for_temp_sqlite(
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )

    local_setup_service.prepare_sqlite_database()

    with local_setup_service.session_scope() as session:
        admin_allowed_permissions = (
            session.execute(
                select(RolePermission).where(
                    RolePermission.role == UserRole.ADMIN,
                    RolePermission.is_allowed.is_(True),
                )
            )
            .scalars()
            .all()
        )

        user_count = len(session.execute(select(User)).scalars().all())

    assert len(admin_allowed_permissions) == len(Permission)
    assert user_count == 0