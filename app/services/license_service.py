from __future__ import annotations

import base64
import hashlib
import json
import os
import platform
import socket
import uuid
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature

from app.core.runtime_paths import ensure_runtime_folders, get_runtime_paths
from app.services.license_public_key import load_license_public_key
from app.services.license_event_log_service import (
    LICENSE_EVENT_ACTIVE,
    LICENSE_EVENT_CHECK_FINISHED,
    LICENSE_EVENT_DEVICE_MISMATCH,
    LICENSE_EVENT_EXPIRED,
    LICENSE_EVENT_EXPIRING_SOON,
    LICENSE_EVENT_FILE_INVALID,
    LICENSE_EVENT_FILE_MISSING,
    LICENSE_EVENT_FUTURE,
    LICENSE_EVENT_SIGNATURE_INVALID,
    write_license_check_result_event,
)


LICENSE_DATE_FORMAT = "%Y-%m-%d"
LICENSE_WARNING_DAYS = 30

SIGNED_LICENSE_VERSION = 2
SIGNED_LICENSE_ALGORITHM = "Ed25519"

LICENSE_STATUS_MISSING = "missing"
LICENSE_STATUS_ACTIVE = "active"
LICENSE_STATUS_EXPIRING_SOON = "expiring_soon"
LICENSE_STATUS_EXPIRED = "expired"
LICENSE_STATUS_FUTURE = "future"
LICENSE_STATUS_INVALID = "invalid"
LICENSE_STATUS_SIGNATURE_INVALID = "signature_invalid"
LICENSE_STATUS_DEVICE_MISMATCH = "device_mismatch"

BASIC_LICENSE_SIGNATURE_SALT = "FTM_LOCAL_LICENSE_V1_BASIC_CHECK"


@dataclass(frozen=True)
class LicenseData:
    company_name: str
    license_type: str
    device_code: str
    starts_at: str
    expires_at: str
    issued_at: str
    notes: str
    signature: str


@dataclass(frozen=True)
class LicenseCheckResult:
    status: str
    status_label: str
    is_valid: bool
    allow_app_open: bool
    allow_data_entry: bool
    license_file: Path
    device_code: str
    company_name: str
    license_type: str
    starts_at: str
    expires_at: str
    days_remaining: int | None
    message: str


class LicenseServiceError(ValueError):
    pass


def license_file_path() -> Path:
    runtime_paths = get_runtime_paths()

    return runtime_paths.license_file


def license_file_exists() -> bool:
    return license_file_path().exists()


def get_device_code() -> str:
    """
    Bu bilgisayar için sade bir cihaz kodu üretir.

    Ham MAC adresini veya bilgisayar bilgilerini dışarı vermez.
    Bilgileri hash'leyip okunabilir kısa bir koda çevirir.
    """

    machine_parts = [
        platform.system(),
        platform.machine(),
        platform.node(),
        socket.gethostname(),
        os.getenv("COMPUTERNAME", ""),
        str(uuid.getnode()),
    ]

    machine_text = "|".join(str(part or "").strip().lower() for part in machine_parts)
    machine_hash = hashlib.sha256(machine_text.encode("utf-8")).hexdigest().upper()

    return _format_device_code(machine_hash)


def build_license_data(
    *,
    company_name: str,
    valid_days: int = 365,
    license_type: str = "annual",
    starts_at: date | None = None,
    notes: str = "",
) -> LicenseData:
    return build_license_data_for_device_code(
        company_name=company_name,
        device_code=get_device_code(),
        valid_days=valid_days,
        license_type=license_type,
        starts_at=starts_at,
        notes=notes,
    )


def build_license_data_for_device_code(
    *,
    company_name: str,
    device_code: str,
    valid_days: int = 365,
    license_type: str = "annual",
    starts_at: date | None = None,
    notes: str = "",
) -> LicenseData:
    """
    Eski version 1 lisans üretim yardımcısıdır.

    Not:
        check_license() artık bu eski formatı geçerli saymaz.
        Bu fonksiyon şimdilik geriye dönük teknik uyumluluk için korunuyor.
    """

    cleaned_company_name = _clean_required_text(company_name, "Firma adı")
    cleaned_device_code = _clean_device_code(device_code)
    cleaned_license_type = _clean_text(license_type, "annual")
    cleaned_notes = _clean_text(notes, "")

    if valid_days <= 0:
        raise LicenseServiceError("Lisans süresi en az 1 gün olmalıdır.")

    license_start_date = starts_at or date.today()
    license_expire_date = license_start_date + timedelta(days=valid_days)

    issued_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    signature_payload = {
        "company_name": cleaned_company_name,
        "license_type": cleaned_license_type,
        "device_code": cleaned_device_code,
        "starts_at": license_start_date.strftime(LICENSE_DATE_FORMAT),
        "expires_at": license_expire_date.strftime(LICENSE_DATE_FORMAT),
        "issued_at": issued_at,
        "notes": cleaned_notes,
    }

    signature = _calculate_license_signature(signature_payload)

    return LicenseData(
        company_name=cleaned_company_name,
        license_type=cleaned_license_type,
        device_code=cleaned_device_code,
        starts_at=signature_payload["starts_at"],
        expires_at=signature_payload["expires_at"],
        issued_at=issued_at,
        notes=cleaned_notes,
        signature=signature,
    )


def create_license_file(
    *,
    company_name: str,
    valid_days: int = 365,
    license_type: str = "annual",
    starts_at: date | None = None,
    notes: str = "",
    overwrite: bool = False,
) -> LicenseData:
    license_data = build_license_data(
        company_name=company_name,
        valid_days=valid_days,
        license_type=license_type,
        starts_at=starts_at,
        notes=notes,
    )

    save_license_data(
        license_data=license_data,
        overwrite=overwrite,
    )

    return license_data


def create_license_file_for_device_code(
    *,
    company_name: str,
    device_code: str,
    output_file: str | Path,
    valid_days: int = 365,
    license_type: str = "annual",
    starts_at: date | None = None,
    notes: str = "",
    overwrite: bool = False,
) -> LicenseData:
    license_data = build_license_data_for_device_code(
        company_name=company_name,
        device_code=device_code,
        valid_days=valid_days,
        license_type=license_type,
        starts_at=starts_at,
        notes=notes,
    )

    save_license_data_to_file(
        license_data=license_data,
        output_file=output_file,
        overwrite=overwrite,
    )

    return license_data


def save_license_data(
    *,
    license_data: LicenseData,
    overwrite: bool = False,
) -> Path:
    ensure_runtime_folders()

    target_file = license_file_path()

    if target_file.exists() and not overwrite:
        raise LicenseServiceError(
            f"Lisans dosyası zaten mevcut: {target_file}"
        )

    target_file.parent.mkdir(parents=True, exist_ok=True)

    payload = asdict(license_data)

    with target_file.open("w", encoding="utf-8") as file:
        json.dump(
            payload,
            file,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        file.write("\n")

    return target_file


def save_license_data_to_file(
    *,
    license_data: LicenseData,
    output_file: str | Path,
    overwrite: bool = False,
) -> Path:
    target_file = Path(output_file).expanduser()

    if target_file.exists() and not overwrite:
        raise LicenseServiceError(
            f"Lisans çıktı dosyası zaten mevcut: {target_file}"
        )

    if target_file.suffix.lower() not in {".json", ".ftmlic"}:
        raise LicenseServiceError(
            "Lisans çıktı dosyası uzantısı .json veya .ftmlic olmalıdır."
        )

    target_file.parent.mkdir(parents=True, exist_ok=True)

    payload = asdict(license_data)

    with target_file.open("w", encoding="utf-8") as file:
        json.dump(
            payload,
            file,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        file.write("\n")

    return target_file


def load_license_file_dict() -> dict[str, Any]:
    target_file = license_file_path()

    if not target_file.exists():
        raise LicenseServiceError(
            f"Lisans dosyası bulunamadı: {target_file}"
        )

    try:
        with target_file.open("r", encoding="utf-8") as file:
            loaded_data = json.load(file)

    except json.JSONDecodeError as exc:
        raise LicenseServiceError(
            f"Lisans dosyası okunamadı. JSON formatı bozuk: {target_file}"
        ) from exc

    except OSError as exc:
        raise LicenseServiceError(
            f"Lisans dosyası okunamadı: {exc}"
        ) from exc

    if not isinstance(loaded_data, dict):
        raise LicenseServiceError(
            "Lisans dosyası geçersiz. JSON kök değeri nesne olmalıdır."
        )

    return loaded_data


def load_license_data() -> LicenseData:
    """
    Eski version 1 lisans verisini okur.

    Not:
        check_license() artık bu eski formatı geçerli saymaz.
    """

    loaded_data = load_license_file_dict()

    return _license_data_from_dict(loaded_data)


def check_license(today: date | None = None) -> LicenseCheckResult:
    """
    FTM lisans kontrolü.

    Güvenlik kararı:
        Sadece version 2 Ed25519 imzalı lisanslar geçerli kabul edilir.
        Eski version 1 / imzasız lisanslar geçersizdir.
    """

    check_date = today or date.today()
    current_device_code = get_device_code()
    target_file = license_file_path()

    if not target_file.exists():
        return _finalize_license_check_result(
            LicenseCheckResult(
                status=LICENSE_STATUS_MISSING,
                status_label="Lisans Yok",
                is_valid=False,
                allow_app_open=True,
                allow_data_entry=False,
                license_file=target_file,
                device_code=current_device_code,
                company_name="",
                license_type="",
                starts_at="",
                expires_at="",
                days_remaining=None,
                message=(
                    "Lisans dosyası bulunamadı. "
                    "Uygulama açılabilir ancak veri girişi için imzalı lisans gereklidir."
                ),
            ),
        )

    try:
        license_file_data = load_license_file_dict()

    except LicenseServiceError as exc:
        return _finalize_license_check_result(
            LicenseCheckResult(
                status=LICENSE_STATUS_INVALID,
                status_label="Lisans Geçersiz",
                is_valid=False,
                allow_app_open=True,
                allow_data_entry=False,
                license_file=target_file,
                device_code=current_device_code,
                company_name="",
                license_type="",
                starts_at="",
                expires_at="",
                days_remaining=None,
                message=str(exc),
            ),
            details={"error_source": "load_license_file_dict"},
        )

    if not is_signed_license_file_data(license_file_data):
        return _finalize_license_check_result(
            LicenseCheckResult(
                status=LICENSE_STATUS_INVALID,
                status_label="Lisans Geçersiz",
                is_valid=False,
                allow_app_open=True,
                allow_data_entry=False,
                license_file=target_file,
                device_code=current_device_code,
                company_name="",
                license_type="",
                starts_at="",
                expires_at="",
                days_remaining=None,
                message=(
                    "Bu lisans dosyası eski formatta veya imzasız görünüyor. "
                    "FTM artık yalnızca version 2 Ed25519 imzalı lisansları kabul eder."
                ),
            ),
            details={"error_source": "is_signed_license_file_data"},
        )

    try:
        signed_payload = verify_signed_license_file_data(license_file_data)
        signature_text = str(license_file_data.get("signature") or "").strip()
        license_data = _license_data_from_signed_payload(
            signed_payload,
            signature_text=signature_text,
        )

    except LicenseServiceError as exc:
        error_message = str(exc)

        if "imza" in error_message.lower():
            return _finalize_license_check_result(
                LicenseCheckResult(
                    status=LICENSE_STATUS_SIGNATURE_INVALID,
                    status_label="Lisans İmzası Geçersiz",
                    is_valid=False,
                    allow_app_open=True,
                    allow_data_entry=False,
                    license_file=target_file,
                    device_code=current_device_code,
                    company_name="",
                    license_type="",
                    starts_at="",
                    expires_at="",
                    days_remaining=None,
                    message=error_message,
                ),
                details={"error_source": "verify_signed_license_file_data"},
            )

        return _finalize_license_check_result(
            LicenseCheckResult(
                status=LICENSE_STATUS_INVALID,
                status_label="Lisans Geçersiz",
                is_valid=False,
                allow_app_open=True,
                allow_data_entry=False,
                license_file=target_file,
                device_code=current_device_code,
                company_name="",
                license_type="",
                starts_at="",
                expires_at="",
                days_remaining=None,
                message=error_message,
            ),
            details={"error_source": "verify_signed_license_file_data"},
        )

    if license_data.device_code != current_device_code:
        return _finalize_license_check_result(
            LicenseCheckResult(
                status=LICENSE_STATUS_DEVICE_MISMATCH,
                status_label="Cihaz Uyumsuz",
                is_valid=False,
                allow_app_open=True,
                allow_data_entry=False,
                license_file=target_file,
                device_code=current_device_code,
                company_name=license_data.company_name,
                license_type=license_data.license_type,
                starts_at=license_data.starts_at,
                expires_at=license_data.expires_at,
                days_remaining=None,
                message=(
                    "Bu lisans dosyası bu bilgisayara ait görünmüyor. "
                    "Lisansın bağlı olduğu cihaz kodu farklı."
                ),
            ),
            details={"license_device_code": license_data.device_code},
        )

    try:
        start_date = _parse_license_date(
            license_data.starts_at,
            "Lisans başlangıç tarihi",
        )
        expire_date = _parse_license_date(
            license_data.expires_at,
            "Lisans bitiş tarihi",
        )

    except LicenseServiceError as exc:
        return _finalize_license_check_result(
            LicenseCheckResult(
                status=LICENSE_STATUS_INVALID,
                status_label="Lisans Geçersiz",
                is_valid=False,
                allow_app_open=True,
                allow_data_entry=False,
                license_file=target_file,
                device_code=current_device_code,
                company_name=license_data.company_name,
                license_type=license_data.license_type,
                starts_at=license_data.starts_at,
                expires_at=license_data.expires_at,
                days_remaining=None,
                message=str(exc),
            ),
            details={"error_source": "_parse_license_date"},
        )

    if check_date < start_date:
        days_until_start = (start_date - check_date).days

        return _finalize_license_check_result(
            LicenseCheckResult(
                status=LICENSE_STATUS_FUTURE,
                status_label="Lisans Henüz Başlamadı",
                is_valid=False,
                allow_app_open=True,
                allow_data_entry=False,
                license_file=target_file,
                device_code=current_device_code,
                company_name=license_data.company_name,
                license_type=license_data.license_type,
                starts_at=license_data.starts_at,
                expires_at=license_data.expires_at,
                days_remaining=None,
                message=f"Lisans başlangıcına {days_until_start} gün var.",
            ),
            details={"check_date": check_date.strftime(LICENSE_DATE_FORMAT)},
        )

    days_remaining = (expire_date - check_date).days

    if days_remaining < 0:
        return _finalize_license_check_result(
            LicenseCheckResult(
                status=LICENSE_STATUS_EXPIRED,
                status_label="Lisans Süresi Doldu",
                is_valid=False,
                allow_app_open=True,
                allow_data_entry=False,
                license_file=target_file,
                device_code=current_device_code,
                company_name=license_data.company_name,
                license_type=license_data.license_type,
                starts_at=license_data.starts_at,
                expires_at=license_data.expires_at,
                days_remaining=days_remaining,
                message="Lisans süresi dolmuş. Yenileme yapılması gerekiyor.",
            ),
            details={"check_date": check_date.strftime(LICENSE_DATE_FORMAT)},
        )

    if days_remaining <= LICENSE_WARNING_DAYS:
        return _finalize_license_check_result(
            LicenseCheckResult(
                status=LICENSE_STATUS_EXPIRING_SOON,
                status_label="Lisans Yakında Bitecek",
                is_valid=True,
                allow_app_open=True,
                allow_data_entry=True,
                license_file=target_file,
                device_code=current_device_code,
                company_name=license_data.company_name,
                license_type=license_data.license_type,
                starts_at=license_data.starts_at,
                expires_at=license_data.expires_at,
                days_remaining=days_remaining,
                message=f"İmzalı lisans aktif. Kalan süre: {days_remaining} gün.",
            ),
            details={"check_date": check_date.strftime(LICENSE_DATE_FORMAT)},
        )

    return _finalize_license_check_result(
        LicenseCheckResult(
            status=LICENSE_STATUS_ACTIVE,
            status_label="Lisans Aktif",
            is_valid=True,
            allow_app_open=True,
            allow_data_entry=True,
            license_file=target_file,
            device_code=current_device_code,
            company_name=license_data.company_name,
            license_type=license_data.license_type,
            starts_at=license_data.starts_at,
            expires_at=license_data.expires_at,
            days_remaining=days_remaining,
            message=f"İmzalı lisans aktif. Kalan süre: {days_remaining} gün.",
        ),
        details={"check_date": check_date.strftime(LICENSE_DATE_FORMAT)},
    )

def license_data_to_dict(license_data: LicenseData) -> dict[str, Any]:
    return asdict(license_data)


def license_check_result_to_dict(result: LicenseCheckResult) -> dict[str, Any]:
    payload = asdict(result)
    payload["license_file"] = str(result.license_file)

    return payload


def is_signed_license_file_data(data: dict[str, Any]) -> bool:
    if not isinstance(data, dict):
        return False

    try:
        version = int(data.get("version") or 0)
    except (TypeError, ValueError):
        return False

    algorithm = str(data.get("algorithm") or "").strip()

    return (
        version == SIGNED_LICENSE_VERSION
        and algorithm == SIGNED_LICENSE_ALGORITHM
        and isinstance(data.get("payload"), dict)
        and isinstance(data.get("signature"), str)
    )


def canonicalize_signed_license_payload(payload: dict[str, Any]) -> bytes:
    if not isinstance(payload, dict):
        raise LicenseServiceError("İmzalı lisans payload değeri nesne olmalıdır.")

    payload_text = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )

    return payload_text.encode("utf-8")


def verify_signed_license_file_data(data: dict[str, Any]) -> dict[str, Any]:
    """
    Version 2 imzalı lisans dosyasını public key ile doğrular.

    Başarılı olursa imzalanmış payload sözlüğünü döndürür.
    Başarısız olursa LicenseServiceError fırlatır.
    """

    if not isinstance(data, dict):
        raise LicenseServiceError("Lisans dosyası geçersiz. JSON kök değeri nesne olmalıdır.")

    try:
        version = int(data.get("version") or 0)
    except (TypeError, ValueError) as exc:
        raise LicenseServiceError("İmzalı lisans sürümü sayısal olmalıdır.") from exc

    if version != SIGNED_LICENSE_VERSION:
        raise LicenseServiceError(
            f"İmzalı lisans sürümü geçersiz. Beklenen: {SIGNED_LICENSE_VERSION}"
        )

    algorithm = str(data.get("algorithm") or "").strip()

    if algorithm != SIGNED_LICENSE_ALGORITHM:
        raise LicenseServiceError(
            f"İmzalı lisans algoritması geçersiz. Beklenen: {SIGNED_LICENSE_ALGORITHM}"
        )

    payload = data.get("payload")

    if not isinstance(payload, dict):
        raise LicenseServiceError("İmzalı lisans payload alanı eksik veya geçersiz.")

    signature_text = str(data.get("signature") or "").strip()

    if not signature_text:
        raise LicenseServiceError("İmzalı lisans imza alanı boş olamaz.")

    try:
        signature_bytes = base64.b64decode(
            signature_text.encode("ascii"),
            validate=True,
        )

    except Exception as exc:
        raise LicenseServiceError(
            "İmzalı lisans imza alanı Base64 formatında değil."
        ) from exc

    payload_bytes = canonicalize_signed_license_payload(payload)

    try:
        public_key = load_license_public_key()
        public_key.verify(signature_bytes, payload_bytes)

    except InvalidSignature as exc:
        raise LicenseServiceError(
            "Lisans imzası geçersiz. Lisans dosyası değiştirilmiş veya sahte üretilmiş olabilir."
        ) from exc

    except Exception as exc:
        raise LicenseServiceError(
            f"Lisans imzası doğrulanamadı: {exc}"
        ) from exc

    return payload


def _license_data_from_signed_payload(
    payload: dict[str, Any],
    *,
    signature_text: str,
) -> LicenseData:
    return LicenseData(
        company_name=_clean_required_text(payload.get("company_name"), "Firma adı"),
        license_type=_clean_text(payload.get("license_type"), "annual"),
        device_code=_clean_device_code(payload.get("device_code")),
        starts_at=_clean_required_text(payload.get("starts_at"), "Lisans başlangıç tarihi"),
        expires_at=_clean_required_text(payload.get("expires_at"), "Lisans bitiş tarihi"),
        issued_at=_clean_text(payload.get("issued_at"), ""),
        notes=_clean_text(payload.get("notes"), ""),
        signature=_clean_required_text(signature_text, "Lisans imzası"),
    )


def _license_data_from_dict(data: dict[str, Any]) -> LicenseData:
    return LicenseData(
        company_name=_clean_required_text(data.get("company_name"), "Firma adı"),
        license_type=_clean_text(data.get("license_type"), "annual"),
        device_code=_clean_required_text(data.get("device_code"), "Cihaz kodu"),
        starts_at=_clean_required_text(data.get("starts_at"), "Lisans başlangıç tarihi"),
        expires_at=_clean_required_text(data.get("expires_at"), "Lisans bitiş tarihi"),
        issued_at=_clean_text(data.get("issued_at"), ""),
        notes=_clean_text(data.get("notes"), ""),
        signature=_clean_required_text(data.get("signature"), "Lisans imzası"),
    )


def _validate_license_signature(license_data: LicenseData) -> str | None:
    payload = {
        "company_name": license_data.company_name,
        "license_type": license_data.license_type,
        "device_code": license_data.device_code,
        "starts_at": license_data.starts_at,
        "expires_at": license_data.expires_at,
        "issued_at": license_data.issued_at,
        "notes": license_data.notes,
    }

    expected_signature = _calculate_license_signature(payload)

    if expected_signature != license_data.signature:
        return (
            "Lisans imzası doğrulanamadı. "
            "Lisans dosyası değiştirilmiş veya bozulmuş olabilir."
        )

    return None


def _calculate_license_signature(payload: dict[str, Any]) -> str:
    normalized_payload = {
        "company_name": str(payload.get("company_name") or "").strip(),
        "license_type": str(payload.get("license_type") or "").strip(),
        "device_code": str(payload.get("device_code") or "").strip(),
        "starts_at": str(payload.get("starts_at") or "").strip(),
        "expires_at": str(payload.get("expires_at") or "").strip(),
        "issued_at": str(payload.get("issued_at") or "").strip(),
        "notes": str(payload.get("notes") or "").strip(),
        "salt": BASIC_LICENSE_SIGNATURE_SALT,
    }

    payload_text = json.dumps(
        normalized_payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )

    return hashlib.sha256(payload_text.encode("utf-8")).hexdigest()


def _parse_license_date(value: str, label: str) -> date:
    try:
        return datetime.strptime(value, LICENSE_DATE_FORMAT).date()
    except ValueError as exc:
        raise LicenseServiceError(
            f"{label} geçersiz. Beklenen format: YYYY-MM-DD"
        ) from exc


def _format_device_code(machine_hash: str) -> str:
    cleaned_hash = "".join(
        char
        for char in machine_hash.upper()
        if char.isalnum()
    )

    code_text = cleaned_hash[:20].ljust(20, "0")
    parts = [
        code_text[0:4],
        code_text[4:8],
        code_text[8:12],
        code_text[12:16],
        code_text[16:20],
    ]

    return "FTM-" + "-".join(parts)


def _clean_device_code(value: Any) -> str:
    cleaned_value = str(value or "").strip().upper()

    if not cleaned_value:
        raise LicenseServiceError("Cihaz kodu boş olamaz.")

    if not cleaned_value.startswith("FTM-"):
        raise LicenseServiceError("Cihaz kodu FTM- ile başlamalıdır.")

    parts = cleaned_value.split("-")

    if len(parts) != 6:
        raise LicenseServiceError(
            "Cihaz kodu formatı geçersiz. Beklenen format: FTM-XXXX-XXXX-XXXX-XXXX-XXXX"
        )

    if parts[0] != "FTM":
        raise LicenseServiceError(
            "Cihaz kodu formatı geçersiz. Beklenen format: FTM-XXXX-XXXX-XXXX-XXXX-XXXX"
        )

    for part in parts[1:]:
        if len(part) != 4:
            raise LicenseServiceError(
                "Cihaz kodu formatı geçersiz. Her kod bölümü 4 karakter olmalıdır."
            )

        if not part.isalnum():
            raise LicenseServiceError(
                "Cihaz kodu formatı geçersiz. Kod yalnızca harf ve rakam içermelidir."
            )

    return cleaned_value


def _clean_required_text(value: Any, field_name: str) -> str:
    cleaned_value = str(value or "").strip()

    if not cleaned_value:
        raise LicenseServiceError(f"{field_name} boş olamaz.")

    return cleaned_value


def _clean_text(value: Any, default: str = "") -> str:
    cleaned_value = str(value or "").strip()

    if not cleaned_value:
        return default

    return cleaned_value



def _finalize_license_check_result(
    result: LicenseCheckResult,
    *,
    details: dict[str, Any] | None = None,
) -> LicenseCheckResult:
    event_type = _license_event_type_for_status(result.status)

    try:
        write_license_check_result_event(
            event_type=event_type,
            license_result=result,
            details=details,
        )

    except Exception:
        pass

    return result


def _license_event_type_for_status(status: str) -> str:
    clean_status = str(status or "").strip()

    event_map = {
        LICENSE_STATUS_MISSING: LICENSE_EVENT_FILE_MISSING,
        LICENSE_STATUS_ACTIVE: LICENSE_EVENT_ACTIVE,
        LICENSE_STATUS_EXPIRING_SOON: LICENSE_EVENT_EXPIRING_SOON,
        LICENSE_STATUS_EXPIRED: LICENSE_EVENT_EXPIRED,
        LICENSE_STATUS_FUTURE: LICENSE_EVENT_FUTURE,
        LICENSE_STATUS_INVALID: LICENSE_EVENT_FILE_INVALID,
        LICENSE_STATUS_SIGNATURE_INVALID: LICENSE_EVENT_SIGNATURE_INVALID,
        LICENSE_STATUS_DEVICE_MISMATCH: LICENSE_EVENT_DEVICE_MISMATCH,
    }

    return event_map.get(clean_status, LICENSE_EVENT_CHECK_FINISHED)

__all__ = [
    "LICENSE_DATE_FORMAT",
    "LICENSE_WARNING_DAYS",
    "SIGNED_LICENSE_VERSION",
    "SIGNED_LICENSE_ALGORITHM",
    "LICENSE_STATUS_MISSING",
    "LICENSE_STATUS_ACTIVE",
    "LICENSE_STATUS_EXPIRING_SOON",
    "LICENSE_STATUS_EXPIRED",
    "LICENSE_STATUS_FUTURE",
    "LICENSE_STATUS_INVALID",
    "LICENSE_STATUS_SIGNATURE_INVALID",
    "LICENSE_STATUS_DEVICE_MISMATCH",
    "LicenseData",
    "LicenseCheckResult",
    "LicenseServiceError",
    "license_file_path",
    "license_file_exists",
    "get_device_code",
    "build_license_data",
    "build_license_data_for_device_code",
    "create_license_file",
    "create_license_file_for_device_code",
    "save_license_data",
    "save_license_data_to_file",
    "load_license_file_dict",
    "load_license_data",
    "check_license",
    "license_data_to_dict",
    "license_check_result_to_dict",
    "is_signed_license_file_data",
    "canonicalize_signed_license_payload",
    "verify_signed_license_file_data",
]