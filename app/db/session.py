from contextlib import contextmanager
from typing import Any, Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    pass


def _ensure_sqlite_parent_folder() -> None:
    settings.sqlite_database_path.parent.mkdir(parents=True, exist_ok=True)


def _create_engine_kwargs() -> dict[str, Any]:
    return {
        "echo": settings.database_echo,
        "future": True,
        "pool_pre_ping": True,
        "connect_args": {
            "check_same_thread": False,
        },
    }


_ensure_sqlite_parent_folder()


engine = create_engine(
    settings.database_url,
    **_create_engine_kwargs(),
)


def _apply_sqlite_connection_pragmas(
    dbapi_connection: Any,
    connection_record: Any,
) -> None:
    cursor = dbapi_connection.cursor()

    try:
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.execute("PRAGMA busy_timeout = 10000")
        cursor.execute("PRAGMA journal_mode = WAL")
    finally:
        cursor.close()


event.listen(
    engine,
    "connect",
    _apply_sqlite_connection_pragmas,
)


SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    future=True,
)


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    session = SessionLocal()

    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _check_sqlite_connection() -> dict[str, Any]:
    with engine.connect() as connection:
        sqlite_version = connection.execute(
            text("SELECT sqlite_version() AS version_text")
        ).scalar_one()

    return {
        "database_engine": "sqlite",
        "database_name": str(settings.sqlite_database_path),
        "user_name": "local",
        "server_port": "local",
        "version_text": f"SQLite {sqlite_version}",
        "database_url": settings.database_url,
    }


def check_database_connection() -> dict[str, Any]:
    return _check_sqlite_connection()