from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.license_service import get_device_code, license_file_path  # noqa: E402


PRIVATE_KEY_FOLDER = Path(
    os.environ.get(
        "FTM_LICENSE_PRIVATE_KEY_FOLDER",
        r"C:\FTM_PRIVATE_KEYS",
    )
)

PRIVATE_KEY_FILE = PRIVATE_KEY_FOLDER / "ftm_license_ed25519_private.pem"

PUBLIC_KEY_MODULE_FILE = (
    PROJECT_ROOT
    / "app"
    / "services"
    / "license_public_key.py"
)

LICENSE_OUTPUT_FOLDER = PROJECT_ROOT / "licenses"

SIGNED_LICENSE_VERSION = 2
SIGNED_LICENSE_ALGORITHM = "Ed25519"
LICENSE_DATE_FORMAT = "%Y-%m-%d"


class SignedLicenseGeneratorError(ValueError):
    pass


def main() -> None:
    args = _parse_args()

    company_name = _clean_required_text(args.company_name, "Firma adı")
    device_code = _clean_device_code(args.device_code or get_device_code())
    license_type = _clean_required_text(args.license_type, "Lisans tipi")
    notes = str(args.notes or "").strip()
    valid_days = _parse_positive_int(args.days, "Lisans günü")
    starts_at = _parse_start_date(args.starts_at)
    expires_at = starts_at + timedelta(days=valid_days)

    private_key = _load_or_create_private_key()
    public_key = private_key.public_key()

    _write_public_key_module(public_key)

    payload = {
        "company_name": company_name,
        "license_type": license_type,
        "device_code": device_code,
        "starts_at": starts_at.strftime(LICENSE_DATE_FORMAT),
        "expires_at": expires_at.strftime(LICENSE_DATE_FORMAT),
        "issued_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "notes": notes,
    }

    signed_license_data = _build_signed_license_data(
        private_key=private_key,
        payload=payload,
    )

    output_file = _resolve_output_file(
        output_file_text=args.output,
        company_name=company_name,
        device_code=device_code,
        license_type=license_type,
    )

    _write_json_file(
        target_file=output_file,
        payload=signed_license_data,
    )

    installed_license_file: Path | None = None

    if args.install:
        installed_license_file = license_file_path()
        _write_json_file(
            target_file=installed_license_file,
            payload=signed_license_data,
        )

    print("")
    print("FTM VERSION 2 İMZALI LİSANS OLUŞTURULDU")
    print("-" * 72)
    print(f"Firma             : {company_name}")
    print(f"Cihaz kodu        : {device_code}")
    print(f"Lisans tipi       : {license_type}")
    print(f"Başlangıç         : {payload['starts_at']}")
    print(f"Bitiş             : {payload['expires_at']}")
    print(f"Gün               : {valid_days}")
    print(f"Çıktı lisans      : {output_file}")
    print(f"Private key       : {PRIVATE_KEY_FILE}")
    print(f"Public key modülü : {PUBLIC_KEY_MODULE_FILE}")
    print(f"Public fingerprint: {_public_key_fingerprint(public_key)}")

    if installed_license_file is not None:
        print(f"Runtime lisans    : {installed_license_file}")

    print("")
    print("ÖNEMLİ:")
    print("- Private key dosyasını kimseyle paylaşma.")
    print("- Private key GitHub'a konulmayacak.")
    print("- app/services/license_public_key.py uygulamanın doğrulama anahtarıdır.")
    print("- Bu public key ile üretilen lisanslar, bu private key ile imzalanır.")
    print("")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="FTM version 2 Ed25519 imzalı lisans üretici."
    )

    parser.add_argument(
        "--company-name",
        required=True,
        help="Lisansın ait olduğu firma adı.",
    )

    parser.add_argument(
        "--device-code",
        default="",
        help=(
            "Lisansın bağlanacağı cihaz kodu. "
            "Boş bırakılırsa bu bilgisayarın cihaz kodu kullanılır."
        ),
    )

    parser.add_argument(
        "--days",
        type=int,
        default=365,
        help="Lisans geçerlilik süresi. Varsayılan: 365",
    )

    parser.add_argument(
        "--license-type",
        default="annual",
        help="Lisans tipi. Örnek: annual, demo_30_days, test_7_days",
    )

    parser.add_argument(
        "--starts-at",
        default="",
        help="Başlangıç tarihi. Format: YYYY-MM-DD. Boş bırakılırsa bugün.",
    )

    parser.add_argument(
        "--notes",
        default="",
        help="Lisans notu.",
    )

    parser.add_argument(
        "--output",
        default="",
        help=(
            "Lisans çıktı dosyası. "
            "Boş bırakılırsa C:\\ftm\\licenses altına otomatik dosya adıyla yazılır."
        ),
    )

    parser.add_argument(
        "--install",
        action="store_true",
        help=(
            "Üretilen lisansı runtime license.json dosyasına da yazar. "
            "Geliştirme/test bilgisayarında hızlı deneme için kullanılır."
        ),
    )

    return parser.parse_args()


def _load_or_create_private_key() -> Ed25519PrivateKey:
    PRIVATE_KEY_FOLDER.mkdir(parents=True, exist_ok=True)

    if PRIVATE_KEY_FILE.exists():
        try:
            loaded_key = serialization.load_pem_private_key(
                PRIVATE_KEY_FILE.read_bytes(),
                password=None,
            )

        except Exception as exc:
            raise SignedLicenseGeneratorError(
                f"Private key okunamadı: {PRIVATE_KEY_FILE}\nHata: {exc}"
            ) from exc

        if not isinstance(loaded_key, Ed25519PrivateKey):
            raise SignedLicenseGeneratorError(
                f"Private key Ed25519 formatında değil: {PRIVATE_KEY_FILE}"
            )

        return loaded_key

    private_key = Ed25519PrivateKey.generate()

    private_key_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

    PRIVATE_KEY_FILE.write_bytes(private_key_pem)

    return private_key


def _write_public_key_module(public_key: Ed25519PublicKey) -> None:
    PUBLIC_KEY_MODULE_FILE.parent.mkdir(parents=True, exist_ok=True)

    public_key_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    public_key_text = public_key_pem.decode("ascii").strip()

    module_content = f'''from __future__ import annotations

import hashlib

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


LICENSE_PUBLIC_KEY_PEM = b""" {public_key_text}
""".replace(b" ", b"", 1)


class LicensePublicKeyError(ValueError):
    pass


def get_license_public_key_pem() -> bytes:
    return LICENSE_PUBLIC_KEY_PEM


def load_license_public_key() -> Ed25519PublicKey:
    try:
        loaded_key = serialization.load_pem_public_key(
            get_license_public_key_pem()
        )

    except Exception as exc:
        raise LicensePublicKeyError(
            f"Lisans public key okunamadı: {{exc}}"
        ) from exc

    if not isinstance(loaded_key, Ed25519PublicKey):
        raise LicensePublicKeyError(
            "Lisans public key Ed25519 formatında değil."
        )

    return loaded_key


def get_license_public_key_fingerprint() -> str:
    public_key = load_license_public_key()

    public_key_der = public_key.public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    fingerprint = hashlib.sha256(public_key_der).hexdigest().upper()

    return "-".join(
        fingerprint[index : index + 8]
        for index in range(0, len(fingerprint), 8)
    )


__all__ = [
    "LICENSE_PUBLIC_KEY_PEM",
    "LicensePublicKeyError",
    "get_license_public_key_pem",
    "load_license_public_key",
    "get_license_public_key_fingerprint",
]
'''

    PUBLIC_KEY_MODULE_FILE.write_text(
        module_content,
        encoding="utf-8",
    )


def _build_signed_license_data(
    *,
    private_key: Ed25519PrivateKey,
    payload: dict[str, Any],
) -> dict[str, Any]:
    payload_bytes = _canonicalize_payload(payload)
    signature_bytes = private_key.sign(payload_bytes)
    signature_text = base64.b64encode(signature_bytes).decode("ascii")

    return {
        "version": SIGNED_LICENSE_VERSION,
        "algorithm": SIGNED_LICENSE_ALGORITHM,
        "payload": payload,
        "signature": signature_text,
    }


def _canonicalize_payload(payload: dict[str, Any]) -> bytes:
    payload_text = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )

    return payload_text.encode("utf-8")


def _resolve_output_file(
    *,
    output_file_text: str,
    company_name: str,
    device_code: str,
    license_type: str,
) -> Path:
    cleaned_output_file_text = str(output_file_text or "").strip()

    if cleaned_output_file_text:
        output_file = Path(cleaned_output_file_text).expanduser()

        if output_file.suffix.lower() not in {".ftmlic", ".json"}:
            raise SignedLicenseGeneratorError(
                "Lisans çıktı dosyası .ftmlic veya .json uzantılı olmalıdır."
            )

        output_file.parent.mkdir(parents=True, exist_ok=True)

        return output_file

    LICENSE_OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)

    safe_company = _safe_file_name(company_name)
    safe_device = _safe_file_name(device_code)
    safe_license_type = _safe_file_name(license_type)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    return (
        LICENSE_OUTPUT_FOLDER
        / f"{safe_company}_{safe_license_type}_{safe_device}_{timestamp}.ftmlic"
    )


def _write_json_file(
    *,
    target_file: Path,
    payload: dict[str, Any],
) -> None:
    target_file.parent.mkdir(parents=True, exist_ok=True)

    target_file.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _public_key_fingerprint(public_key: Ed25519PublicKey) -> str:
    public_key_der = public_key.public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    fingerprint = hashlib.sha256(public_key_der).hexdigest().upper()

    return "-".join(
        fingerprint[index : index + 8]
        for index in range(0, len(fingerprint), 8)
    )


def _parse_start_date(value: str) -> date:
    cleaned_value = str(value or "").strip()

    if not cleaned_value:
        return date.today()

    try:
        return datetime.strptime(cleaned_value, LICENSE_DATE_FORMAT).date()

    except ValueError as exc:
        raise SignedLicenseGeneratorError(
            "Başlangıç tarihi geçersiz. Beklenen format: YYYY-MM-DD"
        ) from exc


def _parse_positive_int(value: Any, field_name: str) -> int:
    try:
        parsed_value = int(value)

    except (TypeError, ValueError) as exc:
        raise SignedLicenseGeneratorError(
            f"{field_name} sayısal olmalıdır."
        ) from exc

    if parsed_value <= 0:
        raise SignedLicenseGeneratorError(
            f"{field_name} sıfırdan büyük olmalıdır."
        )

    return parsed_value


def _clean_device_code(value: Any) -> str:
    cleaned_value = str(value or "").strip().upper()

    if not cleaned_value:
        raise SignedLicenseGeneratorError("Cihaz kodu boş olamaz.")

    if not cleaned_value.startswith("FTM-"):
        raise SignedLicenseGeneratorError("Cihaz kodu FTM- ile başlamalıdır.")

    parts = cleaned_value.split("-")

    if len(parts) != 6:
        raise SignedLicenseGeneratorError(
            "Cihaz kodu formatı geçersiz. Beklenen format: FTM-XXXX-XXXX-XXXX-XXXX-XXXX"
        )

    if parts[0] != "FTM":
        raise SignedLicenseGeneratorError(
            "Cihaz kodu formatı geçersiz. Beklenen format: FTM-XXXX-XXXX-XXXX-XXXX-XXXX"
        )

    for part in parts[1:]:
        if len(part) != 4:
            raise SignedLicenseGeneratorError(
                "Cihaz kodu formatı geçersiz. Her kod bölümü 4 karakter olmalıdır."
            )

        if not part.isalnum():
            raise SignedLicenseGeneratorError(
                "Cihaz kodu formatı geçersiz. Kod yalnızca harf ve rakam içermelidir."
            )

    return cleaned_value


def _clean_required_text(value: Any, field_name: str) -> str:
    cleaned_value = str(value or "").strip()

    if not cleaned_value:
        raise SignedLicenseGeneratorError(f"{field_name} boş olamaz.")

    return cleaned_value


def _safe_file_name(value: str) -> str:
    cleaned_value = str(value or "").strip()

    if not cleaned_value:
        cleaned_value = "license"

    cleaned_value = re.sub(r"[^A-Za-z0-9._-]+", "_", cleaned_value)
    cleaned_value = cleaned_value.strip("._-")

    if not cleaned_value:
        return "license"

    return cleaned_value[:80]


if __name__ == "__main__":
    main()