"""PATCH /users/{id}: your own names, or anyone's as an admin."""

from uuid import uuid4

import pytest
from api import app
from fastapi.testclient import TestClient

PASSWORD = "a-sufficiently-long-passphrase"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def login(client: TestClient, name: str, password: str) -> dict:
    r = client.post("/auth/login", data={"username": name, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def register(client: TestClient) -> tuple[int, str, dict]:
    name = f"user-{uuid4().hex[:12]}"
    body = {"display_name": name, "real_name": "Some Student", "password": PASSWORD}
    r = client.post("/users", json=body)
    assert r.status_code == 201, r.text
    return r.json()["id"], name, login(client, name, PASSWORD)


def test_update_user(client):
    me, my_name, mine = register(client)
    other, other_name, _ = register(client)
    admin = login(client, "test-admin", "test-admin-passphrase")  # from conftest

    r = client.patch(f"/users/{me}", json={"real_name": "New Name"}, headers=mine)
    assert r.status_code == 200, r.text
    assert (r.json()["real_name"], r.json()["display_name"]) == ("New Name", my_name)

    new_name = f"renamed-{uuid4().hex[:8]}"
    assert client.patch(f"/users/{me}", json={"display_name": new_name}, headers=mine).status_code == 200
    login(client, new_name, PASSWORD)  # sign in with the new name

    assert client.patch(f"/users/{other}", json={"real_name": "Hacked"}, headers=mine).status_code == 403
    r = client.patch(f"/users/{other}", json={"real_name": "Fixed By Admin"}, headers=admin)
    assert r.status_code == 200 and r.json()["real_name"] == "Fixed By Admin"

    def code(r):
        return r.status_code, r.json()["error"]["code"]

    assert code(client.patch("/users/999999", json={"real_name": "Nobody"}, headers=admin)) == (404, "USER_NOT_FOUND")
    assert code(client.patch(f"/users/{me}", json={"display_name": other_name}, headers=mine)) == (409, "USER_NAME_TAKEN")
    assert code(client.patch(f"/users/{me}", json={}, headers=mine)) == (422, "EMPTY_UPDATE")
    assert code(client.patch(f"/users/{me}", json={"real_name": None}, headers=mine)) == (422, "VALIDATION_ERROR")
    assert client.patch(f"/users/{me}", json={"real_name": "No Token"}).status_code == 401
