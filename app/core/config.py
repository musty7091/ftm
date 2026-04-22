from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote_plus
import os

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BASE_DIR / ".env"

load_dotenv(ENV_FILE)


def _get_env(name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip()


def _get_required_env(name: str) -> str:
    value = _get_env(name)
    if not value:
        raise RuntimeError(f"Zorunlu ortam değişkeni eksik: {name}")
    return value


def _get_bool_env(name: str, default: bool = False) -> bool:
    value = _get_env(name)

    if not value:
        return default

    return value.lower() in {"1", "true", "yes", "evet", "on"}


def _get_int_env(name: str, default: int) -> int:
    value = _get_env(name)

    if not value:
        return default

    try:
        return int(value)
    except ValueError as exc:
        raise RuntimeError(f"{name} sayısal olmalıdır. Gelen değer: {value}") from exc


@dataclass(frozen=True)
class Settings:
    app_name: str
    app_env: str
    app_debug: bool

    database_host: str
    database_port: int
    database_name: str
    database_user: str
    database_password: str
    database_echo: bool

    backup_folder: Path
    export_folder: Path
    log_folder: Path

    mail_enabled: bool
    mail_server: str
    mail_port: int
    mail_use_tls: bool
    mail_username: str
    mail_password: str
    mail_from: str
    mail_to: str

    @property
    def database_url(self) -> str:
        user = quote_plus(self.database_user)
        password = quote_plus(self.database_password)
        host = self.database_host
        port = self.database_port
        db_name = self.database_name

        return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{db_name}"


settings = Settings(
    app_name=_get_env("APP_NAME", "FTM"),
    app_env=_get_env("APP_ENV", "development"),
    app_debug=_get_bool_env("APP_DEBUG", True),

    database_host=_get_required_env("DATABASE_HOST"),
    database_port=_get_int_env("DATABASE_PORT", 5433),
    database_name=_get_required_env("DATABASE_NAME"),
    database_user=_get_required_env("DATABASE_USER"),
    database_password=_get_required_env("DATABASE_PASSWORD"),
    database_echo=_get_bool_env("DATABASE_ECHO", False),

    backup_folder=BASE_DIR / _get_env("BACKUP_FOLDER", "backups"),
    export_folder=BASE_DIR / _get_env("EXPORT_FOLDER", "exports"),
    log_folder=BASE_DIR / _get_env("LOG_FOLDER", "logs"),

    mail_enabled=_get_bool_env("MAIL_ENABLED", False),
    mail_server=_get_env("MAIL_SERVER", "smtp.gmail.com"),
    mail_port=_get_int_env("MAIL_PORT", 587),
    mail_use_tls=_get_bool_env("MAIL_USE_TLS", True),
    mail_username=_get_env("MAIL_USERNAME", ""),
    mail_password=_get_env("MAIL_PASSWORD", ""),
    mail_from=_get_env("MAIL_FROM", ""),
    mail_to=_get_env("MAIL_TO", ""),
)