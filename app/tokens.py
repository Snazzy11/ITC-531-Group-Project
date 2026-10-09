"""Issue and verify JSON Web Tokens."""
import datetime as dt
import os

import jwt

ALGORITHM = "HS256"
TOKEN_MINUTES = 30
MIN_SECRET_BYTES = 32  # HS256 wants a key at least as long as its 256-bit hash


def _load_secret() -> str:
    # No default: a default secret is a shared secret, and anyone who read the
    # source could forge a token. Missing, empty or short stops the app at startup.
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
    # algorithms= is a whitelist the server supplies. Passing the token's own
    # alg header here instead is the algorithm-confusion vulnerability.
    # "require" makes a validly signed token with no exp or sub invalid;
    # by default PyJWT only checks exp when it happens to be present.
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
