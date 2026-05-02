from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from app.core.runtime_paths import ensure_runtime_folders


LICENSE_CLOCK_STATE_FILE_NAME = "license_clock_state.json"
LICENSE_CLOCK_DATE_FORMAT = "%Y-%m-%d"
LICENSE_CLOCK_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"

DEFAULT_CLOCK_ROLLBACK_TOLERANCE_DAYS = 0


class LicenseClockServiceError(RuntimeError):
    pass


@dataclass(frozen=True)
class LicenseClockState:
    last_seen_check_date: str
    last_seen_check_time_local: str
    last_seen_check_time_utc: str
    last_successful_check_date: str
    last_successful_check_time_local: str
    last_successful_check_time_utc: str
    device_code: str
    updated_at_local: str
    updated_at_utc: str


@dataclass(frozen=True)
class LicenseClockCheckResult:
    state_file: Path
    state_file_exists: bool
    current_check_date: str
    last_seen_check_date: str
    last_successful_check_date: str
    reference_date: str
    rollback_detected: bool
    rollback_days: int
    tolerance_days: int
    message: str


def license_clock_state_file_path() -> Path:
    runtime_paths = ensure_runtime_folders()

    return runtime_paths.config_folder / LICENSE_CLOCK_STATE_FILE_NAME


def load_license_clock_state() -> LicenseClockState | None:
    state_file = license_clock_state_file_path()

    if not state_file.exists():
        return None

    try:
        loaded_data = json.loads(state_file.read_text(encoding="utf-8"))

    except json.JSONDecodeError as exc:
        raise LicenseClockServiceError(
            f"Lisans saat kontrol dosyası bozuk JSON formatında: {state_file}"
        ) from exc

    except OSError as exc:
        raise LicenseClockServiceError(
            f"Lisans saat kontrol dosyası okunamadı: {state_file}"
        ) from exc

    if not isinstance(loaded_data, dict):
        raise LicenseClockServiceError(
            "Lisans saat kontrol dosyası geçersiz. JSON kök değeri nesne olmalıdır."
        )

    return _state_from_dict(loaded_data)


def save_license_clock_state(state: LicenseClockState) -> None:
    state_file = license_clock_state_file_path()
    payload = asdict(state)

    try:
        state_file.write_text(
            json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )

    except OSError as exc:
        raise LicenseClockServiceError(
            f"Lisans saat kontrol dosyası yazılamadı: {state_file}"
        ) from exc


def check_license_clock_rollback(
    *,
    today: date | None = None,
    tolerance_days: int = DEFAULT_CLOCK_ROLLBACK_TOLERANCE_DAYS,
) -> LicenseClockCheckResult:
    check_date = today or date.today()
    safe_tolerance_days = max(0, int(tolerance_days))
    state_file = license_clock_state_file_path()
    state = load_license_clock_state()

    if state is None:
        return LicenseClockCheckResult(
            state_file=state_file,
            state_file_exists=False,
            current_check_date=check_date.strftime(LICENSE_CLOCK_DATE_FORMAT),
            last_seen_check_date="",
            last_successful_check_date="",
            reference_date="",
            rollback_detected=False,
            rollback_days=0,
            tolerance_days=safe_tolerance_days,
            message="Lisans saat kontrol durumu henüz oluşturulmamış.",
        )

    last_seen_date = _parse_optional_date(state.last_seen_check_date)
    last_successful_date = _parse_optional_date(state.last_successful_check_date)
    reference_date = _max_optional_date(last_seen_date, last_successful_date)

    if reference_date is None:
        return LicenseClockCheckResult(
            state_file=state_file,
            state_file_exists=True,
            current_check_date=check_date.strftime(LICENSE_CLOCK_DATE_FORMAT),
            last_seen_check_date=state.last_seen_check_date,
            last_successful_check_date=state.last_successful_check_date,
            reference_date="",
            rollback_detected=False,
            rollback_days=0,
            tolerance_days=safe_tolerance_days,
            message="Karşılaştırılacak önceki lisans kontrol tarihi bulunamadı.",
        )

    rollback_days = (reference_date - check_date).days
    rollback_detected = rollback_days > safe_tolerance_days

    if rollback_detected:
        message = (
            "Bilgisayar tarihi önceki lisans kontrol tarihinden geride görünüyor. "
            f"Geri alma farkı: {rollback_days} gün."
        )
    else:
        message = "Bilgisayar tarihi lisans saat kontrolüne göre normal görünüyor."

    return LicenseClockCheckResult(
        state_file=state_file,
        state_file_exists=True,
        current_check_date=check_date.strftime(LICENSE_CLOCK_DATE_FORMAT),
        last_seen_check_date=state.last_seen_check_date,
        last_successful_check_date=state.last_successful_check_date,
        reference_date=reference_date.strftime(LICENSE_CLOCK_DATE_FORMAT),
        rollback_detected=rollback_detected,
        rollback_days=max(0, rollback_days),
        tolerance_days=safe_tolerance_days,
        message=message,
    )


def record_license_clock_observation(
    *,
    today: date | None = None,
    device_code: str = "",
    successful: bool = False,
) -> LicenseClockState:
    check_date = today or date.today()
    now_local = datetime.now()
    now_utc = datetime.now(timezone.utc)

    existing_state = load_license_clock_state()

    existing_last_seen_date = (
        _parse_optional_date(existing_state.last_seen_check_date)
        if existing_state is not None
        else None
    )
    existing_last_successful_date = (
        _parse_optional_date(existing_state.last_successful_check_date)
        if existing_state is not None
        else None
    )

    new_last_seen_date = _max_optional_date(existing_last_seen_date, check_date) or check_date

    if successful:
        new_last_successful_date = (
            _max_optional_date(existing_last_successful_date, check_date)
            or check_date
        )
    else:
        new_last_successful_date = existing_last_successful_date

    state = LicenseClockState(
        last_seen_check_date=new_last_seen_date.strftime(LICENSE_CLOCK_DATE_FORMAT),
        last_seen_check_time_local=now_local.strftime(LICENSE_CLOCK_DATETIME_FORMAT),
        last_seen_check_time_utc=now_utc.strftime("%Y-%m-%d %H:%M:%S %Z"),
        last_successful_check_date=(
            ""
            if new_last_successful_date is None
            else new_last_successful_date.strftime(LICENSE_CLOCK_DATE_FORMAT)
        ),
        last_successful_check_time_local=(
            existing_state.last_successful_check_time_local
            if existing_state is not None
            and not successful
            else now_local.strftime(LICENSE_CLOCK_DATETIME_FORMAT)
        ),
        last_successful_check_time_utc=(
            existing_state.last_successful_check_time_utc
            if existing_state is not None
            and not successful
            else now_utc.strftime("%Y-%m-%d %H:%M:%S %Z")
        ),
        device_code=_clean_text(device_code),
        updated_at_local=now_local.strftime(LICENSE_CLOCK_DATETIME_FORMAT),
        updated_at_utc=now_utc.strftime("%Y-%m-%d %H:%M:%S %Z"),
    )

    save_license_clock_state(state)

    return state


def reset_license_clock_state_for_manual_test() -> None:
    """
    Sadece geliştirme/test amaçlı yardımcı fonksiyon.

    Normal uygulama akışında kullanılmamalıdır.
    """

    state_file = license_clock_state_file_path()

    if state_file.exists():
        try:
            state_file.unlink()

        except OSError as exc:
            raise LicenseClockServiceError(
                f"Lisans saat kontrol dosyası silinemedi: {state_file}"
            ) from exc


def get_license_clock_summary_lines() -> list[str]:
    state_file = license_clock_state_file_path()
    state = load_license_clock_state()
    rollback_result = check_license_clock_rollback()

    lines = [
        "FTM Lisans Saat Kontrol Özeti",
        "-" * 44,
        f"Durum dosyası: {state_file}",
        f"Durum dosyası var mı: {'Evet' if state is not None else 'Hayır'}",
        f"Bugünkü kontrol tarihi: {rollback_result.current_check_date}",
        f"Son görülen kontrol tarihi: {rollback_result.last_seen_check_date or '-'}",
        f"Son başarılı lisans kontrol tarihi: {rollback_result.last_successful_check_date or '-'}",
        f"Referans tarih: {rollback_result.reference_date or '-'}",
        f"Saat geri alma tespit edildi mi: {'Evet' if rollback_result.rollback_detected else 'Hayır'}",
        f"Geri alma farkı: {rollback_result.rollback_days} gün",
        f"Tolerans: {rollback_result.tolerance_days} gün",
        f"Mesaj: {rollback_result.message}",
    ]

    if state is not None:
        lines.extend(
            [
                "",
                "Kayıt Detayı:",
                f"Cihaz kodu: {state.device_code or '-'}",
                f"Son güncelleme lokal: {state.updated_at_local}",
                f"Son güncelleme UTC: {state.updated_at_utc}",
            ]
        )

    return lines


def _state_from_dict(data: dict[str, Any]) -> LicenseClockState:
    return LicenseClockState(
        last_seen_check_date=_clean_text(data.get("last_seen_check_date")),
        last_seen_check_time_local=_clean_text(data.get("last_seen_check_time_local")),
        last_seen_check_time_utc=_clean_text(data.get("last_seen_check_time_utc")),
        last_successful_check_date=_clean_text(data.get("last_successful_check_date")),
        last_successful_check_time_local=_clean_text(
            data.get("last_successful_check_time_local")
        ),
        last_successful_check_time_utc=_clean_text(
            data.get("last_successful_check_time_utc")
        ),
        device_code=_clean_text(data.get("device_code")),
        updated_at_local=_clean_text(data.get("updated_at_local")),
        updated_at_utc=_clean_text(data.get("updated_at_utc")),
    )


def _parse_optional_date(value: str) -> date | None:
    clean_value = _clean_text(value)

    if not clean_value:
        return None

    try:
        return datetime.strptime(clean_value, LICENSE_CLOCK_DATE_FORMAT).date()

    except ValueError as exc:
        raise LicenseClockServiceError(
            f"Lisans saat kontrol tarihi geçersiz formatta: {clean_value}"
        ) from exc


def _max_optional_date(first_date: date | None, second_date: date | None) -> date | None:
    if first_date is None:
        return second_date

    if second_date is None:
        return first_date

    return max(first_date, second_date)


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


__all__ = [
    "LICENSE_CLOCK_STATE_FILE_NAME",
    "LICENSE_CLOCK_DATE_FORMAT",
    "LICENSE_CLOCK_DATETIME_FORMAT",
    "DEFAULT_CLOCK_ROLLBACK_TOLERANCE_DAYS",
    "LicenseClockServiceError",
    "LicenseClockState",
    "LicenseClockCheckResult",
    "license_clock_state_file_path",
    "load_license_clock_state",
    "save_license_clock_state",
    "check_license_clock_rollback",
    "record_license_clock_observation",
    "reset_license_clock_state_for_manual_test",
    "get_license_clock_summary_lines",
]