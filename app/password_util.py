"""Password hashing. bcrypt's own API, called directly: this course does not use passlib."""
import bcrypt

# Cost factor is 10, chosen in 2026. bcrypt reccomends at least 12 for real security
# but we have it set low on purpose because this is a course project that will never
# hold real accounts. So we might as well keep it fast.
COST = 10

# bcrypt only reads the first 72 bytes of its input, and a long password is
# cut off without any kind of error or warning. The problem with this is two different
# passwords that have the same first 72 bytes will produce the same hash.
# An user who has a password longer than 72 characters will be
# protected by only the first 72 bytes of them. It is better to simply reject
# it than shorten it.
#
# The two separate layers count in different ways
#   * the pydantic schema counts characters. That will throw 422 early on and report an useful error.
#   But in theory 72 characters can be up to 288 bytes in codecs like UTF-8, so we dont want it to be the last level of protection
#   * The hash_password() method counts bytes in the UTF-8 encoding, because that is the
#     unit bcrypt's limit will actually check. This is the last line that cannot be bypassed
MAX_PASSWORD_BYTES = 72

# Dummy check to cost the same cpu time regardless of if password actually exists
DUMMY_HASH = bcrypt.hashpw(b"fake-password!!", bcrypt.gensalt(rounds=COST)).decode("utf-8")


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
