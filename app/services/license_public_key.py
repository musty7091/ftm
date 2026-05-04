from __future__ import annotations

import hashlib

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


LICENSE_PUBLIC_KEY_PEM = b""" -----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEA2KHyVtElLTzfdErddPKJcOXNK76QfMZDPcGRvwcV3aI=
-----END PUBLIC KEY-----
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
            f"Lisans public key okunamadı: {exc}"
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
