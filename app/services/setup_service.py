from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.runtime_paths import (
    ensure_runtime_folders as ensure_core_runtime_folders,
    get_runtime_paths,
)


RUNTIME_PATHS = get_runtime_paths()

SETUP_CONFIG_FOLDER = RUNTIME_PATHS.config_folder
SETUP_CONFIG_FILE = RUNTIME_PATHS.config_folder / "app_setup.json"

SUPPORTED_SETUP_DATABASE_ENGINES = {
    "sqlite",
}


@dataclass(frozen=True)
class SetupConfig:
    setup_completed: bool
    database_engine: str

    sqlite_database_path: str

    database_host: str
    database_port: int
    database_name: str
    database_user: str
    database_password: str

    created_at: str
    updated_at: str


class SetupServiceError(ValueError):
    pass


DEFAULT_SETUP_CONFIG = SetupConfig(
    setup_completed=False,
    database_engine="sqlite",
    sqlite_database_path="data/ftm_local.db",
    database_host="",
    database_port=0,
    database_name="ftm_local",
    database_user="",
    database_password="",
    created_at="",
    updated_at="",
)


def default_setup_config_dict() -> dict[str, Any]:
    return asdict(DEFAULT_SETUP_CONFIG)


def setup_config_folder() -> Path:
    return SETUP_CONFIG_FOLDER


def setup_config_file_path() -> Path:
    return SETUP_CONFIG_FILE


def setup_config_file_exists() -> bool:
    return SETUP_CONFIG_FILE.exists()


def is_setup_completed() -> bool:
    setup_config = load_setup_config()

    return bool(setup_config.setup_completed)


def load_setup_config() -> SetupConfig:
    raw_config = load_setup_config_dict()

    return _setup_config_from_dict(raw_config)


def load_setup_config_dict() -> dict[str, Any]:
    ensure_core_runtime_folders()

    if not SETUP_CONFIG_FILE.exists():
        return normalize_setup_config_payload(default_setup_config_dict())

    try:
        with SETUP_CONFIG_FILE.open("r", encoding="utf-8-sig") as file:
            loaded_data = json.load(file)

    except json.JSONDecodeError as exc:
        broken_file = _backup_broken_setup_config_file()

        raise SetupServiceError(
            "Kurulum ayar dosyası okunamadı. "
            f"Bozuk dosya şu adla saklandı: {broken_file}"
        ) from exc

    except OSError as exc:
        raise SetupServiceError(
            f"Kurulum ayar dosyası okunamadı: {exc}"
        ) from exc

    if not isinstance(loaded_data, dict):
        raise SetupServiceError(
            "Kurulum ayar dosyası geçersiz. JSON kök değeri nesne olmalıdır."
        )

    normalized_data = normalize_setup_config_payload(loaded_data)

    if normalized_data != loaded_data:
        save_setup_config_dict(normalized_data)

    return normalized_data


def save_setup_config_dict(payload: dict[str, Any]) -> dict[str, Any]:
    normalized_data = normalize_setup_config_payload(payload)

    now_text = _now_text()

    if not normalized_data.get("created_at"):
        normalized_data["created_at"] = now_text

    normalized_data["updated_at"] = now_text

    try:
        ensure_core_runtime_folders()
        SETUP_CONFIG_FOLDER.mkdir(parents=True, exist_ok=True)

        with SETUP_CONFIG_FILE.open("w", encoding="utf-8") as file:
            json.dump(
                normalized_data,
                file,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            file.write("\n")

    except OSError as exc:
        raise SetupServiceError(
            f"Kurulum ayar dosyası kaydedilemedi: {exc}"
        ) from exc

    return normalized_data


def save_sqlite_setup_config(
    *,
    sqlite_database_path: str = "data/ftm_local.db",
    setup_completed: bool = True,
) -> SetupConfig:
    current_config = load_setup_config_dict()

    payload = {
        **current_config,
        "setup_completed": setup_completed,
        "database_engine": "sqlite",
        "sqlite_database_path": sqlite_database_path,
        "database_host": "",
        "database_port": 0,
        "database_name": "ftm_local",
        "database_user": "",
        "database_password": "",
    }

    saved_data = save_setup_config_dict(payload)

    return _setup_config_from_dict(saved_data)


def reset_setup_config() -> SetupConfig:
    saved_data = save_setup_config_dict(default_setup_config_dict())

    return _setup_config_from_dict(saved_data)


def normalize_setup_config_payload(payload: dict[str, Any]) -> dict[str, Any]:
    default_data = default_setup_config_dict()

    database_engine = _clean_database_engine(
        payload.get("database_engine", default_data["database_engine"])
    )

    setup_completed = _clean_bool(
        payload.get("setup_completed", default_data["setup_completed"])
    )

    sqlite_database_path = _clean_sqlite_database_path(
        payload.get("sqlite_database_path", default_data["sqlite_database_path"])
    )

    created_at = str(payload.get("created_at", default_data["created_at"]) or "")
    updated_at = str(payload.get("updated_at", default_data["updated_at"]) or "")

    return {
        "setup_completed": setup_completed,
        "database_engine": database_engine,
        "sqlite_database_path": sqlite_database_path,
        "database_host": "",
        "database_port": 0,
        "database_name": "ftm_local",
        "database_user": "",
        "database_password": "",
        "created_at": created_at,
        "updated_at": updated_at,
    }


def build_database_url_from_setup_config(setup_config: SetupConfig | None = None) -> str:
    config = setup_config or load_setup_config()

    if config.database_engine != "sqlite":
        raise SetupServiceError(
            "FTM artık yalnızca SQLite local desktop kurulumunu destekler. "
            f"Geçersiz veritabanı tipi: {config.database_engine}"
        )

    sqlite_path = resolve_sqlite_database_path(config.sqlite_database_path)

    return f"sqlite:///{sqlite_path.as_posix()}"


def resolve_sqlite_database_path(sqlite_database_path: str) -> Path:
    ensure_core_runtime_folders()

    cleaned_path_text = _clean_sqlite_database_path(sqlite_database_path)
    database_path = Path(cleaned_path_text).expanduser()

    if database_path.is_absolute():
        return database_path

    runtime_paths = get_runtime_paths()

    return runtime_paths.root_folder / database_path


def validate_setup_config_for_completion(payload: dict[str, Any]) -> None:
    normalized = normalize_setup_config_payload(payload)

    if not normalized["setup_completed"]:
        return

    database_engine = normalized["database_engine"]

    if database_engine != "sqlite":
        raise SetupServiceError(
            "FTM artık yalnızca SQLite local desktop kurulumunu destekler. "
            f"Geçersiz veritabanı tipi: {database_engine}"
        )

    sqlite_path = resolve_sqlite_database_path(normalized["sqlite_database_path"])

    if not sqlite_path.parent.exists():
        raise SetupServiceError(
            f"SQLite klasörü bulunamadı: {sqlite_path.parent}"
        )


def _setup_config_from_dict(data: dict[str, Any]) -> SetupConfig:
    return SetupConfig(
        setup_completed=bool(data["setup_completed"]),
        database_engine=str(data["database_engine"]),
        sqlite_database_path=str(data["sqlite_database_path"]),
        database_host=str(data["database_host"]),
        database_port=int(data["database_port"]),
        database_name=str(data["database_name"]),
        database_user=str(data["database_user"]),
        database_password=str(data["database_password"]),
        created_at=str(data["created_at"]),
        updated_at=str(data["updated_at"]),
    )


def _clean_database_engine(value: Any) -> str:
    database_engine = str(value or "").strip().lower()

    if not database_engine:
        return DEFAULT_SETUP_CONFIG.database_engine

    if database_engine not in SUPPORTED_SETUP_DATABASE_ENGINES:
        supported_values = ", ".join(sorted(SUPPORTED_SETUP_DATABASE_ENGINES))
        raise SetupServiceError(
            "FTM artık yalnızca SQLite local desktop kurulumunu destekler. "
            f"Geçersiz veritabanı tipi: {database_engine}. "
            f"Desteklenen değerler: {supported_values}"
        )

    return database_engine


def _clean_sqlite_database_path(value: Any) -> str:
    cleaned_value = str(value or "").strip().replace("\\", "/")

    if not cleaned_value:
        return DEFAULT_SETUP_CONFIG.sqlite_database_path

    path_value = Path(cleaned_value)

    if ".." in path_value.parts:
        return DEFAULT_SETUP_CONFIG.sqlite_database_path

    if path_value.name.strip() == "":
        return DEFAULT_SETUP_CONFIG.sqlite_database_path

    if path_value.suffix.lower() not in {"", ".db", ".sqlite", ".sqlite3"}:
        return DEFAULT_SETUP_CONFIG.sqlite_database_path

    return cleaned_value


def _clean_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value

    cleaned_value = str(value or "").strip().lower()

    return cleaned_value in {
        "1",
        "true",
        "yes",
        "evet",
        "on",
        "açık",
        "acik",
    }


def _now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _backup_broken_setup_config_file() -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    broken_file = SETUP_CONFIG_FILE.with_name(
        f"{SETUP_CONFIG_FILE.stem}.broken_{timestamp}{SETUP_CONFIG_FILE.suffix}"
    )

    try:
        SETUP_CONFIG_FILE.replace(broken_file)
    except OSError:
        pass

    return broken_file


__all__ = [
    "SETUP_CONFIG_FOLDER",
    "SETUP_CONFIG_FILE",
    "SUPPORTED_SETUP_DATABASE_ENGINES",
    "SetupConfig",
    "SetupServiceError",
    "default_setup_config_dict",
    "setup_config_folder",
    "setup_config_file_path",
    "setup_config_file_exists",
    "is_setup_completed",
    "load_setup_config",
    "load_setup_config_dict",
    "save_setup_config_dict",
    "save_sqlite_setup_config",
    "reset_setup_config",
    "normalize_setup_config_payload",
    "build_database_url_from_setup_config",
    "resolve_sqlite_database_path",
    "validate_setup_config_for_completion",
]