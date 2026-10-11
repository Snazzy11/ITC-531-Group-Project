from uuid import uuid4
import datetime as dt

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from api import app
from database.database import SessionLocal
from database.models import User, Role, Location, Item
from password_util import (
    MAX_PASSWORD_BYTES,
    PasswordTooLongError,
    hash_password,
    verify_password,
)
from tokens import SECRET, ALGORITHM


PASSWORD = "a-sufficiently-long-passphrase"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c
        
def test_register_login_user(client: TestClient, password=PASSWORD):
    data = {
        "display_name": f"student-{uuid4().hex[:12]}",
        "real_name": "Test Student",
        "password": password,
    }
    register = client.post("/users", json=data)
    # Register
    assert register.status_code == 201, register.text
    assert client.post("/users", json=data).status_code == 409 
    
    # Login
    token = client.post(
        "/auth/login",
        data={"username": data["display_name"], "password": data["password"]}
    ).json()["access_token"]
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["display_name"] == data ["display_name"]

def test_login_rejects_wrong_password(client: TestClient, password=PASSWORD) -> None:
    data = {
        "display_name": f"student-{uuid4().hex[:12]}",
        "real_name": "Test Student",
        "password": password,
    }
    assert client.post("/users", json=data).status_code == 201
    response = client.post(
        "/auth/login", data={"username": data["display_name"], "password": "wrong-but-long-enough"}
    )
    assert response.status_code == 401

def test_login_unknown_user(client: TestClient):
    data = {
        "display_name": f"student-{uuid4().hex[:12]}",
        "real_name": "Unknown Student",
        "password": "Unknown Password",
    }

    response = client.post(
        "/auth/login", data={"username": data["display_name"], "password": "wrong-but-long-enough"}
    )

    assert response.status_code == 401

def test_me_rejects_missing_and_bad_tokens(client: TestClient) -> None:
    assert client.get("/auth/me").status_code == 401
    assert client.get("/auth/me", headers={"Authorization": "Bearer nonsense"}).status_code == 401

def test_no_token(client: TestClient):
    assert client.get("/users").status_code == 401

def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}

def create_token(user_id, *, exp=None, algorithm=ALGORITHM, secret=SECRET):
    now = dt.datetime.now(dt.timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": exp or now + dt.timedelta(minutes=30),
    }
    return jwt.encode(payload, secret, algorithm=algorithm)

def test_valid_token_no_role(client: TestClient):
    token = create_token(10)
    assert client.get("/users", headers=auth_headers(token)).status_code == 403

def test_admin(client: TestClient):
    token = create_token(1)
    assert client.get("/users", headers=auth_headers(token)).status_code == 200

def test_expired_token_is_rejected(client: TestClient):
    expired = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=5)
    token = create_token(1, exp=expired)

    response = client.get("/auth/me", headers=auth_headers(token))
    assert response.status_code == 401


def test_unapproved_jwt_algorithm_is_rejected(client: TestClient):
    token = create_token(
        1,
        algorithm="HS384",
        secret="an-unrelated-test-secret",
    )

    response = client.get("/auth/me", headers=auth_headers(token))
    assert response.status_code == 401

def test_password_hashing_round_trip(password=PASSWORD) -> None:
    hashed = hash_password(password)
    assert verify_password(password, hashed)
    assert not verify_password("something-else", hashed)

def extra_byte_password_rejected(client: TestClient):
    long_password = 'a' * MAX_PASSWORD_BYTES
    data = {
        "display_name": f"student-{uuid4().hex[:12]}",
        "real_name": "Long Password",
        "password": long_password,
    }
    assert client.post("/users", json=data).status_code == 403