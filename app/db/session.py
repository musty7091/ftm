from contextlib import contextmanager
from typing import Any, Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    pass


def _ensure_sqlite_parent_folder() -> None:
    if not settings.is_sqlite:
        return

    settings.sqlite_database_path.parent.mkdir(parents=True, exist_ok=True)


def _create_engine_kwargs() -> dict[str, Any]:
    engine_kwargs: dict[str, Any] = {
        "echo": settings.database_echo,
        "future": True,
        "pool_pre_ping": True,
    }

    if settings.is_sqlite:
        engine_kwargs["connect_args"] = {
            "check_same_thread": False,
        }

    return engine_kwargs


_ensure_sqlite_parent_folder()


engine = create_engine(
    settings.database_url,
    **_create_engine_kwargs(),
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


def _check_postgresql_connection() -> dict[str, Any]:
    with engine.connect() as connection:
        row = connection.execute(
            text(
                """
                SELECT
                    current_database() AS database_name,
                    current_user AS user_name,
                    inet_server_port() AS server_port,
                    version() AS version_text
                """
            )
        ).mappings().one()

    return {
        "database_engine": "postgresql",
        "database_name": row["database_name"],
        "user_name": row["user_name"],
        "server_port": row["server_port"],
        "version_text": row["version_text"],
        "database_url": settings.database_url,
    }


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
    if settings.is_sqlite:
        return _check_sqlite_connection()

    return _check_postgresql_connection()