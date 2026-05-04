from __future__ import annotations

import base64
import hashlib
import json
import platform
import uuid
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature

from app.core.runtime_paths import ensure_runtime_folders, get_runtime_paths
from app.services.license_public_key import load_license_public_key
from app.services.license_event_log_service import (
    LICENSE_EVENT_ACTIVE,
    LICENSE_EVENT_CHECK_FINISHED,
    LICENSE_EVENT_CLOCK_ROLLBACK_DETECTED,
    LICENSE_EVENT_DEVICE_MISMATCH,
    LICENSE_EVENT_EXPIRED,
    LICENSE_EVENT_EXPIRING_SOON,
    LICENSE_EVENT_FILE_INVALID,
    LICENSE_EVENT_FILE_MISSING,
    LICENSE_EVENT_FUTURE,
    LICENSE_EVENT_SIGNATURE_INVALID,
    write_license_check_result_event,
)
from app.services.license_clock_service import (
    LicenseClockServiceError,
    check_license_clock_rollback,
    record_license_clock_observation,
)


LICENSE_DATE_FORMAT = "%Y-%m-%d"
LICENSE_WARNING_DAYS = 30

SIGNED_LICENSE_VERSION = 2
SIGNED_LICENSE_ALGORITHM = "Ed25519"

DEVICE_IDENTITY_FILE_NAME = "device_identity.json"
DEVICE_CODE_ALGORITHM_VERSION = "FTM_DEVICE_CODE_STABLE_V2"

LICENSE_STATUS_MISSING = "missing"
LICENSE_STATUS_ACTIVE = "active"
LICENSE_STATUS_EXPIRING_SOON = "expiring_soon"
LICENSE_STATUS_EXPIRED = "expired"
LICENSE_STATUS_FUTURE = "future"
LICENSE_STATUS_INVALID = "invalid"
LICENSE_STATUS_SIGNATURE_INVALID = "signature_invalid"
LICENSE_STATUS_DEVICE_MISMATCH = "device_mismatch"
LICENSE_STATUS_CLOCK_ROLLBACK = "clock_rollback"

V1_LICENSE_DISABLED_MESSAGE = (
    "v1 lisans sistemi artık desteklenmiyor. "
    "FTM yalnızca version 2 Ed25519 imzalı lisansları kabul eder. "
    "Lisans üretimi için tools/create_signed_license_v2.py veya FTM Licence Maker kullanılmalıdır."
)


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
    Bu bilgisayar için stabil FTM cihaz kodu üretir.

    Yeni güvenli davranış:
        - Windows üzerinde MachineGuid kullanılır.
        - Ağ kartı, MAC adresi, Docker, WSL, VPN, bilgisayar adı ve hostname kullanılmaz.
        - Windows dışı veya MachineGuid okunamayan özel ortamlarda AppData altındaki
          kalıcı FTM device_identity.json dosyası kullanılır.

    Bu fonksiyon ham sistem kimliğini dışarı vermez.
    Kimliği SHA256 ile hash'leyip okunabilir FTM-XXXX formatına çevirir.
    """

    stable_identity_text = _get_stable_device_identity_text()
    machine_hash = hashlib.sha256(stable_identity_text.encode("utf-8")).hexdigest().upper()

    return _format_device_code(machine_hash)


def build_license_data(
    *,
    company_name: str,
    valid_days: int = 365,
    license_type: str = "annual",
    starts_at: date | None = None,
    notes: str = "",
) -> LicenseData:
    """
    Eski v1 lisans üretim fonksiyonu.

    Güvenlik kararı:
        v1 lisans üretimi tamamen kapatıldı.
        Fonksiyon adı geriye dönük import kırılmasını önlemek için korunur.
    """

    raise LicenseServiceError(V1_LICENSE_DISABLED_MESSAGE)


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
    Eski v1 lisans üretim fonksiyonu.

    Güvenlik kararı:
        v1 lisans üretimi tamamen kapatıldı.
        Fonksiyon adı geriye dönük import kırılmasını önlemek için korunur.
    """

    raise LicenseServiceError(V1_LICENSE_DISABLED_MESSAGE)


def create_license_file(
    *,
    company_name: str,
    valid_days: int = 365,
    license_type: str = "annual",
    starts_at: date | None = None,
    notes: str = "",
    overwrite: bool = False,
) -> LicenseData:
    """
    Eski v1 runtime lisans dosyası oluşturma fonksiyonu.

    Güvenlik kararı:
        v1 lisans dosyası oluşturma tamamen kapatıldı.
        Version 2 Ed25519 imzalı lisans kullanılmalıdır.
    """

    raise LicenseServiceError(V1_LICENSE_DISABLED_MESSAGE)


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
    """
    Eski v1 dış lisans dosyası oluşturma fonksiyonu.

    Güvenlik kararı:
        v1 lisans dosyası oluşturma tamamen kapatıldı.
        Version 2 Ed25519 imzalı lisans kullanılmalıdır.
    """

    raise LicenseServiceError(V1_LICENSE_DISABLED_MESSAGE)


def save_license_data(
    *,
    license_data: LicenseData,
    overwrite: bool = False,
) -> Path:
    """
    Eski v1 LicenseData yazma fonksiyonu.

    Güvenlik kararı:
        v1 formatlı LicenseData yazımı kapatıldı.
        İmzalı .ftmlic dosyaları ayrı üretici araçla oluşturulmalıdır.
    """

    raise LicenseServiceError(V1_LICENSE_DISABLED_MESSAGE)


def save_license_data_to_file(
    *,
    license_data: LicenseData,
    output_file: str | Path,
    overwrite: bool = False,
) -> Path:
    """
    Eski v1 LicenseData dosyaya yazma fonksiyonu.

    Güvenlik kararı:
        v1 formatlı LicenseData yazımı kapatıldı.
        İmzalı .ftmlic dosyaları ayrı üretici araçla oluşturulmalıdır.
    """

    raise LicenseServiceError(V1_LICENSE_DISABLED_MESSAGE)


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
    Eski v1 lisans okuma fonksiyonu.

    Güvenlik kararı:
        v1 lisans okuma artık desteklenmez.
        Aktif lisans kontrolü için check_license() kullanılmalıdır.
    """

    raise LicenseServiceError(V1_LICENSE_DISABLED_MESSAGE)


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

    clock_check_error = _clock_check_error_result(
        check_date=check_date,
        current_device_code=current_device_code,
        target_file=target_file,
    )

    if clock_check_error is not None:
        return clock_check_error

    clock_rollback_result = check_license_clock_rollback(today=check_date)

    if clock_rollback_result.rollback_detected:
        return _finalize_license_check_result(
            LicenseCheckResult(
                status=LICENSE_STATUS_CLOCK_ROLLBACK,
                status_label="Bilgisayar Tarihi Şüpheli",
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
                    "Bilgisayar tarihi önceki lisans kontrol tarihinden geride görünüyor. "
                    "Güvenlik nedeniyle lisans geçerli kabul edilmedi. "
                    "Lütfen bilgisayar tarih/saat ayarını kontrol edin ve destek ekibiyle iletişime geçin."
                ),
            ),
            details={
                "check_date": check_date.strftime(LICENSE_DATE_FORMAT),
                "clock_state_file": str(clock_rollback_result.state_file),
                "last_seen_check_date": clock_rollback_result.last_seen_check_date,
                "last_successful_check_date": clock_rollback_result.last_successful_check_date,
                "reference_date": clock_rollback_result.reference_date,
                "rollback_days": clock_rollback_result.rollback_days,
                "tolerance_days": clock_rollback_result.tolerance_days,
                "clock_message": clock_rollback_result.message,
            },
            check_date=check_date,
        )

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
            details={"error_source": "license_file_missing"},
            check_date=check_date,
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
            check_date=check_date,
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
            check_date=check_date,
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
                check_date=check_date,
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
            check_date=check_date,
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
            check_date=check_date,
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
            check_date=check_date,
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
            check_date=check_date,
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
            check_date=check_date,
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
            check_date=check_date,
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
        check_date=check_date,
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


def _get_stable_device_identity_text() -> str:
    windows_machine_guid = _read_windows_machine_guid()

    if windows_machine_guid:
        return (
            f"{DEVICE_CODE_ALGORITHM_VERSION}|"
            f"WINDOWS_MACHINE_GUID|"
            f"{windows_machine_guid}"
        )

    local_identity = _load_or_create_local_device_identity()

    return (
        f"{DEVICE_CODE_ALGORITHM_VERSION}|"
        f"FTM_LOCAL_DEVICE_IDENTITY|"
        f"{local_identity}"
    )


def _read_windows_machine_guid() -> str:
    if platform.system().strip().lower() != "windows":
        return ""

    try:
        import winreg

    except ImportError:
        return ""

    try:
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Cryptography",
        ) as registry_key:
            value, _value_type = winreg.QueryValueEx(registry_key, "MachineGuid")

    except OSError:
        return ""

    return _clean_device_identity_value(value)


def _device_identity_file_path() -> Path:
    runtime_paths = ensure_runtime_folders()

    return runtime_paths.config_folder / DEVICE_IDENTITY_FILE_NAME


def _load_or_create_local_device_identity() -> str:
    identity_file = _device_identity_file_path()

    if identity_file.exists():
        try:
            loaded_data = json.loads(identity_file.read_text(encoding="utf-8"))

        except json.JSONDecodeError as exc:
            raise LicenseServiceError(
                "FTM cihaz kimliği dosyası bozuk JSON formatında.\n"
                f"Dosya: {identity_file}\n"
                "Güvenlik nedeniyle yeni cihaz kimliği otomatik oluşturulmadı."
            ) from exc

        except OSError as exc:
            raise LicenseServiceError(
                "FTM cihaz kimliği dosyası okunamadı.\n"
                f"Dosya: {identity_file}\n"
                f"Hata: {exc}"
            ) from exc

        if not isinstance(loaded_data, dict):
            raise LicenseServiceError(
                "FTM cihaz kimliği dosyası geçersiz formatta.\n"
                f"Dosya: {identity_file}"
            )

        identity_value = _clean_device_identity_value(
            loaded_data.get("device_identity")
        )

        if not identity_value:
            raise LicenseServiceError(
                "FTM cihaz kimliği dosyasında geçerli kimlik bulunamadı.\n"
                f"Dosya: {identity_file}"
            )

        return identity_value

    identity_value = str(uuid.uuid4())

    payload = {
        "algorithm": DEVICE_CODE_ALGORITHM_VERSION,
        "device_identity": identity_value,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "note": (
            "Bu dosya yalnızca MachineGuid okunamayan özel ortamlarda "
            "FTM cihaz kodunu stabil tutmak için kullanılır."
        ),
    }

    try:
        identity_file.write_text(
            json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

    except OSError as exc:
        raise LicenseServiceError(
            "FTM cihaz kimliği dosyası oluşturulamadı.\n"
            f"Dosya: {identity_file}\n"
            f"Hata: {exc}"
        ) from exc

    return identity_value


def _clean_device_identity_value(value: Any) -> str:
    cleaned_value = str(value or "").strip().lower()
    cleaned_value = cleaned_value.strip("{}").strip()

    allowed_chars: list[str] = []

    for char in cleaned_value:
        if char.isalnum() or char in {"-", "_"}:
            allowed_chars.append(char)

    return "".join(allowed_chars).strip("-_")


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


def _clock_check_error_result(
    *,
    check_date: date,
    current_device_code: str,
    target_file: Path,
) -> LicenseCheckResult | None:
    try:
        check_license_clock_rollback(today=check_date)

    except LicenseClockServiceError as exc:
        return _finalize_license_check_result(
            LicenseCheckResult(
                status=LICENSE_STATUS_INVALID,
                status_label="Lisans Saat Kontrol Hatası",
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
                    "Lisans saat kontrol dosyası okunamadı. "
                    "Güvenlik nedeniyle veri girişi kapatıldı. "
                    f"Hata: {exc}"
                ),
            ),
            details={
                "check_date": check_date.strftime(LICENSE_DATE_FORMAT),
                "error_source": "check_license_clock_rollback",
            },
            check_date=check_date,
        )

    return None


def _record_license_clock_observation_safely(
    *,
    result: LicenseCheckResult,
    check_date: date,
) -> None:
    try:
        record_license_clock_observation(
            today=check_date,
            device_code=result.device_code,
            successful=result.is_valid,
        )

    except LicenseClockServiceError:
        return

    except Exception:
        return


def _license_event_type_for_status(status: str) -> str:
    if status == LICENSE_STATUS_MISSING:
        return LICENSE_EVENT_FILE_MISSING

    if status == LICENSE_STATUS_ACTIVE:
        return LICENSE_EVENT_ACTIVE

    if status == LICENSE_STATUS_EXPIRING_SOON:
        return LICENSE_EVENT_EXPIRING_SOON

    if status == LICENSE_STATUS_EXPIRED:
        return LICENSE_EVENT_EXPIRED

    if status == LICENSE_STATUS_FUTURE:
        return LICENSE_EVENT_FUTURE

    if status == LICENSE_STATUS_SIGNATURE_INVALID:
        return LICENSE_EVENT_SIGNATURE_INVALID

    if status == LICENSE_STATUS_DEVICE_MISMATCH:
        return LICENSE_EVENT_DEVICE_MISMATCH

    if status == LICENSE_STATUS_CLOCK_ROLLBACK:
        return LICENSE_EVENT_CLOCK_ROLLBACK_DETECTED

    return LICENSE_EVENT_FILE_INVALID


def _write_license_check_result_event_safely(
    *,
    result: LicenseCheckResult,
    details: dict[str, Any],
) -> None:
    try:
        write_license_check_result_event(
            event_type=_license_event_type_for_status(result.status),
            license_result=result,
            details=details,
        )
        write_license_check_result_event(
            event_type=LICENSE_EVENT_CHECK_FINISHED,
            license_result=result,
            details=details,
        )

    except Exception:
        return


def _finalize_license_check_result(
    result: LicenseCheckResult,
    *,
    details: dict[str, Any] | None = None,
    check_date: date | None = None,
) -> LicenseCheckResult:
    final_check_date = check_date or date.today()
    final_details = dict(details or {})

    if "check_date" not in final_details:
        final_details["check_date"] = final_check_date.strftime(LICENSE_DATE_FORMAT)

    _record_license_clock_observation_safely(
        result=result,
        check_date=final_check_date,
    )

    _write_license_check_result_event_safely(
        result=result,
        details=final_details,
    )

    return result


__all__ = [
    "LICENSE_DATE_FORMAT",
    "LICENSE_WARNING_DAYS",
    "SIGNED_LICENSE_VERSION",
    "SIGNED_LICENSE_ALGORITHM",
    "DEVICE_IDENTITY_FILE_NAME",
    "DEVICE_CODE_ALGORITHM_VERSION",
    "LICENSE_STATUS_MISSING",
    "LICENSE_STATUS_ACTIVE",
    "LICENSE_STATUS_EXPIRING_SOON",
    "LICENSE_STATUS_EXPIRED",
    "LICENSE_STATUS_FUTURE",
    "LICENSE_STATUS_INVALID",
    "LICENSE_STATUS_SIGNATURE_INVALID",
    "LICENSE_STATUS_DEVICE_MISMATCH",
    "LICENSE_STATUS_CLOCK_ROLLBACK",
    "V1_LICENSE_DISABLED_MESSAGE",
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