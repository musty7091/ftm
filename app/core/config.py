from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote_plus
from typing import Any
import json
import os

from dotenv import load_dotenv

from app.core.runtime_paths import ensure_runtime_folders, get_runtime_paths


BASE_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BASE_DIR / ".env"
SETUP_CONFIG_FILE = BASE_DIR / "config" / "app_setup.json"

load_dotenv(ENV_FILE)


SUPPORTED_DATABASE_ENGINES = {
    "postgresql",
    "sqlite",
}


def _get_env(name: str, default: str = "") -> str:
    value = os.getenv(name)

    if value is None:
        return default

    return value.strip()


def _env_exists(name: str) -> bool:
    return bool(_get_env(name))


def _load_setup_config_data() -> dict[str, Any]:
    if not SETUP_CONFIG_FILE.exists():
        return {}

    try:
        with SETUP_CONFIG_FILE.open("r", encoding="utf-8") as file:
            loaded_data = json.load(file)
    except Exception:
        return {}

    if not isinstance(loaded_data, dict):
        return {}

    return loaded_data


SETUP_CONFIG_DATA = _load_setup_config_data()


def _get_setup_value(name: str, default: Any = "") -> Any:
    return SETUP_CONFIG_DATA.get(name, default)


def _setup_completed() -> bool:
    value = _get_setup_value("setup_completed", False)

    if isinstance(value, bool):
        return value

    return str(value or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "evet",
        "on",
        "açık",
        "acik",
    }


def _get_env_or_setup(
    *,
    env_name: str,
    setup_name: str,
    default: str = "",
) -> str:
    env_value = _get_env(env_name)

    if env_value:
        return env_value

    setup_value = _get_setup_value(setup_name, default)

    return str(setup_value or default).strip()


def _get_required_value(
    *,
    env_name: str,
    setup_name: str,
    label: str,
) -> str:
    value = _get_env_or_setup(
        env_name=env_name,
        setup_name=setup_name,
        default="",
    )

    if not value:
        raise RuntimeError(f"Zorunlu ayar eksik: {label}")

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


def _get_int_env_or_setup(
    *,
    env_name: str,
    setup_name: str,
    default: int,
) -> int:
    env_value = _get_env(env_name)

    if env_value:
        try:
            return int(env_value)
        except ValueError as exc:
            raise RuntimeError(f"{env_name} sayısal olmalıdır. Gelen değer: {env_value}") from exc

    setup_value = _get_setup_value(setup_name, default)

    try:
        return int(setup_value)
    except (TypeError, ValueError):
        return default


def _has_postgresql_env_values() -> bool:
    return (
        _env_exists("DATABASE_HOST")
        and _env_exists("DATABASE_NAME")
        and _env_exists("DATABASE_USER")
        and _env_exists("DATABASE_PASSWORD")
    )


def _clean_database_engine(value: Any) -> str:
    database_engine = str(value or "").strip().lower()

    if not database_engine:
        return ""

    if database_engine not in SUPPORTED_DATABASE_ENGINES:
        supported_values = ", ".join(sorted(SUPPORTED_DATABASE_ENGINES))
        raise RuntimeError(
            f"DATABASE_ENGINE geçersiz: {database_engine}. "
            f"Desteklenen değerler: {supported_values}"
        )

    return database_engine


def _get_database_engine() -> str:
    env_database_engine = _clean_database_engine(_get_env("DATABASE_ENGINE"))

    if env_database_engine:
        return env_database_engine

    if _setup_completed():
        setup_database_engine = _clean_database_engine(
            _get_setup_value("database_engine", "")
        )

        if setup_database_engine:
            return setup_database_engine

    if _has_postgresql_env_values():
        return "postgresql"

    return "sqlite"


def _get_sqlite_database_path() -> Path:
    ensure_runtime_folders()

    runtime_paths = get_runtime_paths()

    sqlite_database_path_text = _get_env_or_setup(
        env_name="SQLITE_DATABASE_PATH",
        setup_name="sqlite_database_path",
        default="data/ftm_local.db",
    )

    sqlite_database_path = Path(sqlite_database_path_text).expanduser()

    if sqlite_database_path.is_absolute():
        final_database_path = sqlite_database_path
    else:
        final_database_path = runtime_paths.root_folder / sqlite_database_path

    final_database_path.parent.mkdir(parents=True, exist_ok=True)

    return final_database_path


@dataclass(frozen=True)
class Settings:
    app_name: str
    app_env: str
    app_debug: bool

    database_engine: str

    database_host: str
    database_port: int
    database_name: str
    database_user: str
    database_password: str
    database_echo: bool

    sqlite_database_path: Path

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
    def is_postgresql(self) -> bool:
        return self.database_engine == "postgresql"

    @property
    def is_sqlite(self) -> bool:
        return self.database_engine == "sqlite"

    @property
    def database_url(self) -> str:
        if self.is_sqlite:
            return f"sqlite:///{self.sqlite_database_path.as_posix()}"

        user = quote_plus(self.database_user)
        password = quote_plus(self.database_password)
        host = self.database_host
        port = self.database_port
        db_name = self.database_name

        return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{db_name}"


DATABASE_ENGINE = _get_database_engine()


if DATABASE_ENGINE == "postgresql":
    DATABASE_HOST = _get_required_value(
        env_name="DATABASE_HOST",
        setup_name="database_host",
        label="PostgreSQL sunucu",
    )
    DATABASE_PORT = _get_int_env_or_setup(
        env_name="DATABASE_PORT",
        setup_name="database_port",
        default=5433,
    )
    DATABASE_NAME = _get_required_value(
        env_name="DATABASE_NAME",
        setup_name="database_name",
        label="PostgreSQL veritabanı adı",
    )
    DATABASE_USER = _get_required_value(
        env_name="DATABASE_USER",
        setup_name="database_user",
        label="PostgreSQL kullanıcı adı",
    )
    DATABASE_PASSWORD = _get_required_value(
        env_name="DATABASE_PASSWORD",
        setup_name="database_password",
        label="PostgreSQL şifre",
    )
else:
    DATABASE_HOST = ""
    DATABASE_PORT = 0
    DATABASE_NAME = "ftm_local"
    DATABASE_USER = ""
    DATABASE_PASSWORD = ""


settings = Settings(
    app_name=_get_env("APP_NAME", "FTM"),
    app_env=_get_env("APP_ENV", "development"),
    app_debug=_get_bool_env("APP_DEBUG", True),

    database_engine=DATABASE_ENGINE,

    database_host=DATABASE_HOST,
    database_port=DATABASE_PORT,
    database_name=DATABASE_NAME,
    database_user=DATABASE_USER,
    database_password=DATABASE_PASSWORD,
    database_echo=_get_bool_env("DATABASE_ECHO", False),

    sqlite_database_path=_get_sqlite_database_path(),

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