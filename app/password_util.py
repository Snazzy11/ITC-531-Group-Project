"""Password hashing. bcrypt's own API — this course does not use passlib."""
import bcrypt

COST = 10 # Intentionally low for our project since it will never be production code
MAX_PASSWORD_BYTES = 72


class PasswordTooLongError(ValueError):
    pass


def hash_password(plain: str) -> str:
    raw = plain.encode("utf-8")
    if len(raw) > MAX_PASSWORD_BYTES:
        raise PasswordTooLongError(
            f"Given password is {len(raw)} bytes, but bcrypt accepts at most {MAX_PASSWORD_BYTES}"
        )
    return bcrypt.hashpw(raw, bcrypt.gensalt(rounds=COST)).decode("utf-8")


def verify_password(plain: str, stored: str) -> bool:
    raw = plain.encode("utf-8")
    if len(raw) > MAX_PASSWORD_BYTES:
        return False
    return bcrypt.checkpw(raw, stored.encode("utf-8"))
