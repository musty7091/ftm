from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from app.db.session import Base
import app.models  # noqa: F401


def test_all_models_can_create_tables_on_sqlite(tmp_path: Path) -> None:
    sqlite_file = tmp_path / "ftm_sqlite_compatibility.db"

    engine = create_engine(
        f"sqlite:///{sqlite_file.as_posix()}",
        future=True,
        connect_args={
            "check_same_thread": False,
        },
    )

    Base.metadata.create_all(bind=engine)

    inspector = inspect(engine)
    created_table_names = set(inspector.get_table_names())
    expected_table_names = set(Base.metadata.tables.keys())

    missing_tables = expected_table_names.difference(created_table_names)

    assert sqlite_file.exists()
    assert expected_table_names
    assert missing_tables == set()


def test_sqlite_database_accepts_session_creation(tmp_path: Path) -> None:
    sqlite_file = tmp_path / "ftm_sqlite_session_test.db"

    engine = create_engine(
        f"sqlite:///{sqlite_file.as_posix()}",
        future=True,
        connect_args={
            "check_same_thread": False,
        },
    )

    Base.metadata.create_all(bind=engine)

    TestSessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        future=True,
    )

    with TestSessionLocal() as session:
        result = session.execute(text("SELECT 1")).scalar_one()

    assert result == 1