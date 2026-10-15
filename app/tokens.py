"""Issue and verify JSON Web Tokens."""
import datetime as dt
import os

import jwt

ALGORITHM = "HS256"
TOKEN_MINUTES = 30
MIN_SECRET_BYTES = 32  # HS256 wants a key at least as long as its 256-bit hash


def _load_secret() -> str:
    # No default: a default secret is one everybody knows. A missing, empty or
    # short one stops the app from starting.
    secret = os.environ.get("JWT_SECRET")
    if not secret:
        raise RuntimeError("JWT_SECRET is not set. Generate one with: openssl rand -hex 32")
    if len(secret.encode("utf-8")) < MIN_SECRET_BYTES:
        raise RuntimeError(f"JWT_SECRET must be at least {MIN_SECRET_BYTES} bytes long")
    return secret


SECRET = _load_secret()


class TokenError(Exception):
    pass


def create_access_token(subject: str) -> str:
    now = dt.datetime.now(dt.UTC)
    payload = {"sub": subject, "iat": now, "exp": now + dt.timedelta(minutes=TOKEN_MINUTES)}
    return jwt.encode(payload, SECRET, algorithm=ALGORITHM)


def read_access_token(token: str) -> dict:
    # algorithms= is our own whitelist; trusting the token's alg header instead
    # is the algorithm-confusion bug. require= rejects a token with no exp or
    # sub (PyJWT only checks exp if it's there).
    try:
        return jwt.decode(
            token, SECRET, algorithms=[ALGORITHM], options={"require": ["exp", "sub"]}
        )
    except jwt.PyJWTError as exc:
        raise TokenError("invalid token") from exc


if __name__ == "__main__":                       # python tokens.py, to see one
    token = create_access_token("1")
    print(token)
    print("verified :", read_access_token(token))
    print("no secret:", jwt.decode(token, options={"verify_signature": False}))
