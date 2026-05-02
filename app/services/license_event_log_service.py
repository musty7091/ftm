from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.runtime_paths import ensure_runtime_folders


LICENSE_EVENT_LOG_FILE_NAME = "license_events.jsonl"
LICENSE_EVENT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

LICENSE_EVENT_CHECK_STARTED = "license_check_started"
LICENSE_EVENT_CHECK_FINISHED = "license_check_finished"
LICENSE_EVENT_FILE_MISSING = "license_file_missing"
LICENSE_EVENT_FILE_INVALID = "license_file_invalid"
LICENSE_EVENT_SIGNATURE_INVALID = "license_signature_invalid"
LICENSE_EVENT_DEVICE_MISMATCH = "license_device_mismatch"
LICENSE_EVENT_EXPIRED = "license_expired"
LICENSE_EVENT_FUTURE = "license_future"
LICENSE_EVENT_ACTIVE = "license_active"
LICENSE_EVENT_EXPIRING_SOON = "license_expiring_soon"
LICENSE_EVENT_CLOCK_ROLLBACK_DETECTED = "license_clock_rollback_detected"
LICENSE_EVENT_LICENSE_FILE_INSTALLED = "license_file_installed"
LICENSE_EVENT_UNEXPECTED_ERROR = "license_unexpected_error"

MAX_TEXT_LENGTH = 2000


class LicenseEventLogServiceError(RuntimeError):
    pass


@dataclass(frozen=True)
class LicenseEventLogEntry:
    event_type: str
    event_time_local: str
    event_time_utc: str
    status: str
    status_label: str
    device_code: str
    company_name: str
    license_type: str
    starts_at: str
    expires_at: str
    days_remaining: int | None
    license_file: str
    message: str
    details: dict[str, Any]


def license_event_log_file_path() -> Path:
    runtime_paths = ensure_runtime_folders()

    return runtime_paths.logs_folder / LICENSE_EVENT_LOG_FILE_NAME


def write_license_event(
    *,
    event_type: str,
    status: str = "",
    status_label: str = "",
    device_code: str = "",
    company_name: str = "",
    license_type: str = "",
    starts_at: str = "",
    expires_at: str = "",
    days_remaining: int | None = None,
    license_file: str | Path = "",
    message: str = "",
    details: dict[str, Any] | None = None,
) -> LicenseEventLogEntry:
    clean_event_type = _clean_text(event_type)

    if not clean_event_type:
        raise LicenseEventLogServiceError("Lisans olay tipi boş olamaz.")

    now_local = datetime.now()
    now_utc = datetime.now(timezone.utc)

    entry = LicenseEventLogEntry(
        event_type=clean_event_type,
        event_time_local=now_local.strftime(LICENSE_EVENT_DATE_FORMAT),
        event_time_utc=now_utc.strftime("%Y-%m-%d %H:%M:%S %Z"),
        status=_clean_text(status),
        status_label=_clean_text(status_label),
        device_code=_clean_text(device_code),
        company_name=_clean_text(company_name),
        license_type=_clean_text(license_type),
        starts_at=_clean_text(starts_at),
        expires_at=_clean_text(expires_at),
        days_remaining=days_remaining,
        license_file=_clean_text(str(license_file or "")),
        message=_clean_text(message),
        details=_clean_details(details or {}),
    )

    _append_event_to_file(entry)

    return entry


def write_license_check_result_event(
    *,
    event_type: str,
    license_result: Any,
    details: dict[str, Any] | None = None,
) -> LicenseEventLogEntry:
    return write_license_event(
        event_type=event_type,
        status=str(getattr(license_result, "status", "") or ""),
        status_label=str(getattr(license_result, "status_label", "") or ""),
        device_code=str(getattr(license_result, "device_code", "") or ""),
        company_name=str(getattr(license_result, "company_name", "") or ""),
        license_type=str(getattr(license_result, "license_type", "") or ""),
        starts_at=str(getattr(license_result, "starts_at", "") or ""),
        expires_at=str(getattr(license_result, "expires_at", "") or ""),
        days_remaining=getattr(license_result, "days_remaining", None),
        license_file=str(getattr(license_result, "license_file", "") or ""),
        message=str(getattr(license_result, "message", "") or ""),
        details=details,
    )


def read_license_event_log_entries(
    *,
    limit: int = 100,
) -> list[dict[str, Any]]:
    log_file = license_event_log_file_path()

    if not log_file.exists():
        return []

    safe_limit = max(1, min(int(limit), 1000))

    try:
        lines = log_file.read_text(encoding="utf-8").splitlines()

    except OSError as exc:
        raise LicenseEventLogServiceError(
            f"Lisans olay log dosyası okunamadı: {log_file}"
        ) from exc

    selected_lines = lines[-safe_limit:]
    entries: list[dict[str, Any]] = []

    for line in selected_lines:
        clean_line = line.strip()

        if not clean_line:
            continue

        try:
            loaded = json.loads(clean_line)

        except json.JSONDecodeError:
            entries.append(
                {
                    "event_type": "log_line_invalid",
                    "message": "Lisans olay logunda bozuk satır bulundu.",
                    "raw_line": clean_line[:MAX_TEXT_LENGTH],
                }
            )
            continue

        if isinstance(loaded, dict):
            entries.append(loaded)

    return entries


def get_license_event_log_summary_lines(*, limit: int = 20) -> list[str]:
    log_file = license_event_log_file_path()
    entries = read_license_event_log_entries(limit=limit)

    lines = [
        "FTM Lisans Olay Log Özeti",
        "-" * 40,
        f"Log dosyası: {log_file}",
        f"Gösterilen kayıt sayısı: {len(entries)}",
    ]

    if not entries:
        lines.append("Henüz lisans olay kaydı yok.")
        return lines

    lines.append("")

    for entry in entries:
        event_time = str(entry.get("event_time_local") or "-")
        event_type = str(entry.get("event_type") or "-")
        status_label = str(entry.get("status_label") or "-")
        message = str(entry.get("message") or "-")

        lines.append(f"{event_time} | {event_type} | {status_label} | {message}")

    return lines


def _append_event_to_file(entry: LicenseEventLogEntry) -> None:
    log_file = license_event_log_file_path()
    payload = asdict(entry)

    try:
        with log_file.open("a", encoding="utf-8") as file:
            file.write(
                json.dumps(
                    payload,
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
            file.write("\n")

    except OSError as exc:
        raise LicenseEventLogServiceError(
            f"Lisans olay log dosyasına yazılamadı: {log_file}"
        ) from exc


def _clean_text(value: Any) -> str:
    text = str(value or "").strip()

    if len(text) > MAX_TEXT_LENGTH:
        return text[:MAX_TEXT_LENGTH] + "..."

    return text


def _clean_details(details: dict[str, Any]) -> dict[str, Any]:
    clean_payload: dict[str, Any] = {}

    for key, value in details.items():
        clean_key = _clean_text(key)

        if not clean_key:
            continue

        if isinstance(value, (str, int, float, bool)) or value is None:
            clean_payload[clean_key] = value
        else:
            clean_payload[clean_key] = _clean_text(value)

    return clean_payload


__all__ = [
    "LICENSE_EVENT_LOG_FILE_NAME",
    "LICENSE_EVENT_DATE_FORMAT",
    "LICENSE_EVENT_CHECK_STARTED",
    "LICENSE_EVENT_CHECK_FINISHED",
    "LICENSE_EVENT_FILE_MISSING",
    "LICENSE_EVENT_FILE_INVALID",
    "LICENSE_EVENT_SIGNATURE_INVALID",
    "LICENSE_EVENT_DEVICE_MISMATCH",
    "LICENSE_EVENT_EXPIRED",
    "LICENSE_EVENT_FUTURE",
    "LICENSE_EVENT_ACTIVE",
    "LICENSE_EVENT_EXPIRING_SOON",
    "LICENSE_EVENT_CLOCK_ROLLBACK_DETECTED",
    "LICENSE_EVENT_LICENSE_FILE_INSTALLED",
    "LICENSE_EVENT_UNEXPECTED_ERROR",
    "LicenseEventLogServiceError",
    "LicenseEventLogEntry",
    "license_event_log_file_path",
    "write_license_event",
    "write_license_check_result_event",
    "read_license_event_log_entries",
    "get_license_event_log_summary_lines",
]