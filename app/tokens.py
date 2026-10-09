"""Issue and verify JSON Web Tokens."""
import datetime as dt
import os

import jwt

SECRET = os.environ["JWT_SECRET"]     # no default. A default secret is a shared secret.
ALGORITHM = "HS256"
TOKEN_MINUTES = 30


class TokenError(Exception):
    pass


def create_access_token(subject: str) -> str:
    now = dt.datetime.now(dt.UTC)
    payload = {"sub": subject, "iat": now, "exp": now + dt.timedelta(minutes=TOKEN_MINUTES)}
    return jwt.encode(payload, SECRET, algorithm=ALGORITHM)


def read_access_token(token: str) -> dict:
    # algorithms= is a whitelist the server supplies. Passing the token's own
    # alg header here instead is the algorithm-confusion vulnerability.
    try:
        return jwt.decode(token, SECRET, algorithms=[ALGORITHM])
    except jwt.PyJWTError as exc:
        raise TokenError("invalid token") from exc


if __name__ == "__main__":                       # python tokens.py, to see one
    token = create_access_token("ada@example.edu")
    print(token)
    print("verified :", read_access_token(token))
    print("no secret:", jwt.decode(token, options={"verify_signature": False}))
