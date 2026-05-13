from __future__ import annotations

import argparse
import getpass
import hashlib
import os
import sys
from pathlib import Path
from typing import Optional

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)


DEFAULT_INPUT_PRIVATE_KEY_FILE = Path(
    os.environ.get(
        "FTM_LICENSE_PLAIN_PRIVATE_KEY_FILE",
        r"C:\FTM_PRIVATE_KEYS\ftm_license_ed25519_private.pem",
    )
)

DEFAULT_OUTPUT_PRIVATE_KEY_FILE = Path(
    os.environ.get(
        "FTM_LICENSE_ENCRYPTED_PRIVATE_KEY_FILE",
        r"C:\FTM_LICENSE_ADMIN\keys\ftm_license_ed25519_private_encrypted.pem",
    )
)

MIN_PASSWORD_LENGTH = 16


class PrivateKeyEncryptionError(RuntimeError):
    pass


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _resolve_path(path: Path) -> Path:
    return path.expanduser().resolve()


def _is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def _format_fingerprint(public_key: Ed25519PublicKey) -> str:
    public_key_der = public_key.public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    fingerprint = hashlib.sha256(public_key_der).hexdigest().upper()

    return "-".join(
        fingerprint[index : index + 8]
        for index in range(0, len(fingerprint), 8)
    )


def _read_file_bytes(path: Path) -> bytes:
    if not path.exists():
        raise PrivateKeyEncryptionError(f"Dosya bulunamadı: {path}")

    if not path.is_file():
        raise PrivateKeyEncryptionError(f"Bu yol bir dosya değil: {path}")

    try:
        return path.read_bytes()
    except OSError as exc:
        raise PrivateKeyEncryptionError(
            f"Dosya okunamadı: {path}\nHata: {exc}"
        ) from exc


def _load_unencrypted_ed25519_private_key(path: Path) -> Ed25519PrivateKey:
    private_key_bytes = _read_file_bytes(path)

    try:
        loaded_key = serialization.load_pem_private_key(
            private_key_bytes,
            password=None,
        )
    except TypeError as exc:
        raise PrivateKeyEncryptionError(
            "Private key zaten parolalı/encrypted görünüyor veya parola istiyor.\n"
            "Bu araç sadece mevcut şifresiz private key dosyasını encrypted PEM dosyasına dönüştürmek için kullanılır.\n"
            f"Dosya: {path}"
        ) from exc
    except ValueError as exc:
        raise PrivateKeyEncryptionError(
            "Private key PEM formatı okunamadı.\n"
            "Dosya bozuk, yanlış formatta veya Ed25519 private key olmayabilir.\n"
            f"Dosya: {path}\n"
            f"Hata: {exc}"
        ) from exc
    except Exception as exc:
        raise PrivateKeyEncryptionError(
            f"Private key okunamadı: {path}\nHata: {exc}"
        ) from exc

    if not isinstance(loaded_key, Ed25519PrivateKey):
        raise PrivateKeyEncryptionError(
            "Private key Ed25519 formatında değil.\n"
            f"Dosya: {path}\n"
            f"Okunan tip: {type(loaded_key).__name__}"
        )

    return loaded_key


def _load_encrypted_ed25519_private_key(
    *,
    path: Path,
    password: str,
) -> Ed25519PrivateKey:
    private_key_bytes = _read_file_bytes(path)

    try:
        loaded_key = serialization.load_pem_private_key(
            private_key_bytes,
            password=password.encode("utf-8"),
        )
    except TypeError as exc:
        raise PrivateKeyEncryptionError(
            "Encrypted private key açılamadı.\n"
            "Dosya parola istemiyor olabilir veya verilen parola biçimi uygun olmayabilir.\n"
            f"Dosya: {path}"
        ) from exc
    except ValueError as exc:
        raise PrivateKeyEncryptionError(
            "Encrypted private key açılamadı.\n"
            "Parola hatalı olabilir veya dosya bozuk olabilir.\n"
            f"Dosya: {path}"
        ) from exc
    except Exception as exc:
        raise PrivateKeyEncryptionError(
            f"Encrypted private key okunamadı: {path}\nHata: {exc}"
        ) from exc

    if not isinstance(loaded_key, Ed25519PrivateKey):
        raise PrivateKeyEncryptionError(
            "Encrypted private key Ed25519 formatında değil.\n"
            f"Dosya: {path}\n"
            f"Okunan tip: {type(loaded_key).__name__}"
        )

    return loaded_key


def _password_has_upper(password: str) -> bool:
    return any(character.isupper() for character in password)


def _password_has_lower(password: str) -> bool:
    return any(character.islower() for character in password)


def _password_has_digit(password: str) -> bool:
    return any(character.isdigit() for character in password)


def _password_has_special(password: str) -> bool:
    return any(not character.isalnum() for character in password)


def _validate_private_key_password(password: str) -> None:
    if not password:
        raise PrivateKeyEncryptionError("Private key parolası boş olamaz.")

    if len(password) < MIN_PASSWORD_LENGTH:
        raise PrivateKeyEncryptionError(
            f"Private key parolası en az {MIN_PASSWORD_LENGTH} karakter olmalıdır."
        )

    if "\n" in password or "\r" in password:
        raise PrivateKeyEncryptionError(
            "Private key parolası satır sonu karakteri içeremez."
        )

    if not _password_has_upper(password):
        raise PrivateKeyEncryptionError(
            "Private key parolası en az bir büyük harf içermelidir."
        )

    if not _password_has_lower(password):
        raise PrivateKeyEncryptionError(
            "Private key parolası en az bir küçük harf içermelidir."
        )

    if not _password_has_digit(password):
        raise PrivateKeyEncryptionError(
            "Private key parolası en az bir rakam içermelidir."
        )

    if not _password_has_special(password):
        raise PrivateKeyEncryptionError(
            "Private key parolası en az bir özel karakter içermelidir."
        )


def _ask_new_password() -> str:
    print("")
    print("PRIVATE KEY PAROLASI")
    print("-" * 80)
    print("Bu parola, lisans üretim private key dosyasını koruyacaktır.")
    print("Parolayı unutursan encrypted private key açılamaz.")
    print("Parolayı GitHub'a, koda, not dosyasına veya müşteri bilgisayarına yazma.")
    print("-" * 80)
    print("")

    first_password = getpass.getpass("Yeni private key parolası: ")
    second_password = getpass.getpass("Yeni private key parolası tekrar: ")

    if first_password != second_password:
        raise PrivateKeyEncryptionError("Girilen parolalar aynı değil.")

    _validate_private_key_password(first_password)

    return first_password


def _ask_existing_password() -> str:
    password = getpass.getpass("Encrypted private key parolası: ")

    if not password:
        raise PrivateKeyEncryptionError("Private key parolası boş olamaz.")

    return password


def _write_encrypted_private_key(
    *,
    private_key: Ed25519PrivateKey,
    output_file: Path,
    password: str,
    overwrite: bool,
    allow_output_inside_repo: bool,
) -> None:
    output_file = _resolve_path(output_file)
    repo_root = _project_root()

    if _is_relative_to(output_file, repo_root) and not allow_output_inside_repo:
        raise PrivateKeyEncryptionError(
            "Çıkış dosyası proje/repo klasörü içinde görünüyor.\n"
            "Private key dosyası repo içinde tutulmamalıdır.\n\n"
            f"Repo kökü : {repo_root}\n"
            f"Çıkış    : {output_file}\n\n"
            "Önerilen güvenli yol:\n"
            r"C:\FTM_LICENSE_ADMIN\keys\ftm_license_ed25519_private_encrypted.pem"
        )

    if output_file.exists() and not overwrite:
        raise PrivateKeyEncryptionError(
            "Çıkış dosyası zaten var. Üzerine yazmak istemiyorsan farklı dosya adı kullan.\n"
            "Üzerine yazmak istiyorsan --overwrite parametresini ekle.\n\n"
            f"Dosya: {output_file}"
        )

    output_file.parent.mkdir(parents=True, exist_ok=True)

    encrypted_private_key_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.BestAvailableEncryption(
            password.encode("utf-8")
        ),
    )

    try:
        output_file.write_bytes(encrypted_private_key_bytes)
    except OSError as exc:
        raise PrivateKeyEncryptionError(
            f"Encrypted private key dosyası yazılamadı: {output_file}\nHata: {exc}"
        ) from exc

    try:
        output_file.chmod(0o600)
    except OSError:
        pass


def encrypt_private_key(
    *,
    input_file: Path,
    output_file: Path,
    overwrite: bool,
    allow_output_inside_repo: bool,
) -> None:
    input_file = _resolve_path(input_file)
    output_file = _resolve_path(output_file)

    if input_file == output_file:
        raise PrivateKeyEncryptionError(
            "Giriş ve çıkış dosyası aynı olamaz.\n"
            "Şifresiz private key dosyasının üzerine doğrudan yazmak güvenli değildir."
        )

    private_key = _load_unencrypted_ed25519_private_key(input_file)
    public_key = private_key.public_key()
    fingerprint_before = _format_fingerprint(public_key)

    password = _ask_new_password()

    _write_encrypted_private_key(
        private_key=private_key,
        output_file=output_file,
        password=password,
        overwrite=overwrite,
        allow_output_inside_repo=allow_output_inside_repo,
    )

    verified_key = _load_encrypted_ed25519_private_key(
        path=output_file,
        password=password,
    )
    fingerprint_after = _format_fingerprint(verified_key.public_key())

    if fingerprint_before != fingerprint_after:
        raise PrivateKeyEncryptionError(
            "Encrypted private key doğrulaması başarısız.\n"
            "Yazılan dosyanın public key fingerprint değeri kaynak dosyayla eşleşmedi."
        )

    print("")
    print("OK - Encrypted private key başarıyla oluşturuldu.")
    print("-" * 80)
    print(f"Giriş dosyası        : {input_file}")
    print(f"Çıkış dosyası        : {output_file}")
    print(f"Public key fingerprint: {fingerprint_after}")
    print("-" * 80)
    print("")
    print("ÖNEMLİ:")
    print("- Bu adım şifresiz private key dosyasını otomatik silmez.")
    print("- Önce ADIM 2.3 ile Licence Maker encrypted key okuyacak hale getirilmelidir.")
    print("- Sonra şifresiz private key dosyası güvenli offline yedeğe alınmalı veya güvenli şekilde kaldırılmalıdır.")
    print("- Encrypted private key dosyasını müşteri bilgisayarına veya müşteri kurulum paketine koyma.")
    print("")


def verify_encrypted_private_key(*, encrypted_file: Path) -> None:
    encrypted_file = _resolve_path(encrypted_file)
    password = _ask_existing_password()

    private_key = _load_encrypted_ed25519_private_key(
        path=encrypted_file,
        password=password,
    )

    fingerprint = _format_fingerprint(private_key.public_key())

    print("")
    print("OK - Encrypted private key parola ile başarıyla açıldı.")
    print("-" * 80)
    print(f"Dosya                 : {encrypted_file}")
    print(f"Public key fingerprint: {fingerprint}")
    print("-" * 80)
    print("")


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="encrypt_license_private_key.py",
        description=(
            "FTM Ed25519 şifresiz lisans private key dosyasını "
            "parolalı/encrypted PEM dosyasına dönüştürür."
        ),
    )

    parser.add_argument(
        "--input",
        dest="input_file",
        default=str(DEFAULT_INPUT_PRIVATE_KEY_FILE),
        help=(
            "Şifresiz Ed25519 private key dosyası. "
            f"Varsayılan: {DEFAULT_INPUT_PRIVATE_KEY_FILE}"
        ),
    )

    parser.add_argument(
        "--output",
        dest="output_file",
        default=str(DEFAULT_OUTPUT_PRIVATE_KEY_FILE),
        help=(
            "Oluşturulacak parolalı/encrypted private key dosyası. "
            f"Varsayılan: {DEFAULT_OUTPUT_PRIVATE_KEY_FILE}"
        ),
    )

    parser.add_argument(
        "--verify",
        dest="verify_file",
        default="",
        help=(
            "Encrypt işlemi yapmadan mevcut encrypted private key dosyasını parola ile doğrular."
        ),
    )

    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Çıkış dosyası varsa üzerine yazar.",
    )

    parser.add_argument(
        "--allow-output-inside-repo",
        action="store_true",
        help=(
            "Çıkış dosyasının repo içinde olmasına izin verir. "
            "Normal kullanımda önerilmez."
        ),
    )

    return parser


def main() -> int:
    parser = build_argument_parser()
    args = parser.parse_args()

    try:
        verify_file_text = str(args.verify_file or "").strip()

        if verify_file_text:
            verify_encrypted_private_key(
                encrypted_file=Path(verify_file_text),
            )
            return 0

        encrypt_private_key(
            input_file=Path(str(args.input_file)),
            output_file=Path(str(args.output_file)),
            overwrite=bool(args.overwrite),
            allow_output_inside_repo=bool(args.allow_output_inside_repo),
        )
        return 0

    except PrivateKeyEncryptionError as exc:
        print("")
        print("FAIL - Private key encryption işlemi başarısız.")
        print("-" * 80)
        print(str(exc))
        print("-" * 80)
        print("", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("")
        print("İşlem kullanıcı tarafından iptal edildi.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())