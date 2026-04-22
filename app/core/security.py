import bcrypt


MIN_PASSWORD_LENGTH = 8
MAX_BCRYPT_PASSWORD_BYTES = 72


class PasswordValidationError(ValueError):
    pass


def normalize_username(username: str) -> str:
    cleaned_username = (username or "").strip().lower()

    if not cleaned_username:
        raise ValueError("Kullanıcı adı boş olamaz.")

    return cleaned_username


def validate_password_strength(password: str) -> None:
    if not password:
        raise PasswordValidationError("Şifre boş olamaz.")

    if len(password) < MIN_PASSWORD_LENGTH:
        raise PasswordValidationError(f"Şifre en az {MIN_PASSWORD_LENGTH} karakter olmalıdır.")

    if len(password.encode("utf-8")) > MAX_BCRYPT_PASSWORD_BYTES:
        raise PasswordValidationError(
            f"Şifre bcrypt sınırı nedeniyle en fazla {MAX_BCRYPT_PASSWORD_BYTES} byte olmalıdır."
        )

    has_letter = any(character.isalpha() for character in password)
    has_digit = any(character.isdigit() for character in password)

    if not has_letter:
        raise PasswordValidationError("Şifre en az bir harf içermelidir.")

    if not has_digit:
        raise PasswordValidationError("Şifre en az bir rakam içermelidir.")


def hash_password(password: str) -> str:
    validate_password_strength(password)

    password_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt(rounds=12)
    hashed_password = bcrypt.hashpw(password_bytes, salt)

    return hashed_password.decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    if not plain_password or not password_hash:
        return False

    try:
        plain_password_bytes = plain_password.encode("utf-8")
        password_hash_bytes = password_hash.encode("utf-8")

        return bcrypt.checkpw(plain_password_bytes, password_hash_bytes)
    except (ValueError, TypeError):
        return False