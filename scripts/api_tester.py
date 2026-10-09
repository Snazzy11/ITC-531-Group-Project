"""End-to-end smoke test against a real Postgres.

    PYTHONPATH=app JWT_SECRET=$(openssl rand -hex 32) DATABASE_URL=postgresql+psycopg2://seekr:seekr-devonly@localhost:5432/seekr uv run --with httpx2 python scripts/api_tester.py

Drops and recreates every table, creates its own admin account, then exercises
each rule in the contract (including who may call what) and prints the status
code and body.
"""
import json
import sys

from fastapi.testclient import TestClient

from database import models  # noqa: F401
from database.database import Base, engine

if engine.dialect.name == "sqlite":
    # SQLite ignores foreign keys unless asked, so without this the ON DELETE
    # RESTRICT checks (e.g. "hard delete matched item" -> 409) wrongly pass
    # as 204 and everything after them cascades into false failures.
    from sqlalchemy import event

    @event.listens_for(engine, "connect")
    def _enforce_fks(dbapi_conn, _):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

Base.metadata.drop_all(bind=engine)

from api import app  # noqa: E402  (imported after the drop so create_all runs)
import crud  # noqa: E402
from database.database import SessionLocal  # noqa: E402

ADMIN_NAME, ADMIN_PW = "test-admin", "admin-pass-1"
with SessionLocal() as db:
    crud.seed_auth(db, ADMIN_NAME, ADMIN_PW)  # the lifespan does this in the real app

c = TestClient(app, raise_server_exceptions=False)
failures = []


def show(label, r, expect):
    body = r.text
    try:
        body = json.dumps(r.json())
    except Exception:
        pass
    ok = "ok " if r.status_code == expect else "FAIL"
    if r.status_code != expect:
        failures.append(f"{label}: expected {expect}, got {r.status_code}")
    print(f"{ok} {label:34} {r.status_code}  {body[:150]}")
    return r


def login(name, password):
    r = c.post("/auth/login", data={"username": name, "password": password})
    return {"Authorization": "Bearer " + r.json()["access_token"]} if r.status_code == 200 else {}


show("health", c.get("/health"), 200)
show("login bad password", c.post("/auth/login", data={"username": ADMIN_NAME, "password": "wrong"}), 401)
show("login unknown user", c.post("/auth/login", data={"username": "nobody-here", "password": "wrong"}), 401)
A = login(ADMIN_NAME, ADMIN_PW)
show("me no token", c.get("/auth/me"), 401)
show("me garbage token", c.get("/auth/me", headers={"Authorization": "Bearer abc"}), 401)
show("me admin", c.get("/auth/me", headers=A), 200)
show("create loc no auth", c.post("/locations", json={"name": "X", "coordinates": "1,2"}), 401)
loc = show("create loc", c.post("/locations", json={"name": "Pearce Hall", "coordinates": "40.1,-84.2"}, headers=A), 201).json()["id"]
show("dup loc name", c.post("/locations", json={"name": "Pearce Hall", "coordinates": "40.1,-84.2"}, headers=A), 409)
loc2 = c.post("/locations", json={"name": "School of Music", "coordinates": "40.3,-84.9"}, headers=A).json()["id"]

uid = show("create user", c.post("/users", json={"display_name": "tester1", "real_name": "Test User", "password": "secret123"}), 201).json()["id"]
show("create user is_admin", c.post("/users", json={"display_name": "sneaky1", "real_name": "Sneaky", "password": "secret123", "is_admin": True}), 422)
show("create user long password", c.post("/users", json={"display_name": "longpw1", "real_name": "Long Pw", "password": "x" * 80}), 422)
show("dup display name", c.post("/users", json={"display_name": "tester1", "real_name": "Someone Else", "password": "secret123"}), 409)
c.post("/users", json={"display_name": "tester2", "real_name": "Other User", "password": "secret123"})
U = login("tester1", "secret123")   # the poster
V = login("tester2", "secret123")   # a different user
show("login user", c.post("/auth/login", data={"username": "tester1", "password": "secret123"}), 200)
show("list users no auth", c.get("/users"), 401)
show("list users as user", c.get("/users", headers=U), 403)
if "password" in show("list users as admin", c.get("/users", headers=A), 200).text:
    failures.append("list users: response includes the password hash")
show("create loc as user", c.post("/locations", json={"name": "X", "coordinates": "1,2"}, headers=U), 403)
show("create loc old header", c.post("/locations", json={"name": "X", "coordinates": "1,2"}, headers={"X-Admin-Token": "dev-admin-token"}), 401)
show("item no auth", c.post("/items", json={"name": "Keys", "type": 0, "location_id": loc}), 401)
show("item client user_id", c.post("/items", json={"name": "Keys", "type": 0, "location_id": loc, "user_id": uid}, headers=U), 422)

show("item bad type", c.post("/items", json={"name": "Keys", "type": 5, "location_id": loc}, headers=U), 422)
show("item extra field", c.post("/items", json={"name": "Keys", "type": 0, "location_id": loc, "status": "open"}, headers=U), 422)
show("item unknown loc", c.post("/items", json={"name": "Keys", "type": 0, "location_id": 9999}, headers=U), 404)
lost = show("create lost item", c.post("/items", json={"name": "Blue keys", "description": "carabiner", "type": 0, "location_id": loc}, headers=U), 201).json()["id"]
found = show("create found item", c.post("/items", json={"name": "Keyring", "type": 1, "location_id": loc}, headers=U), 201).json()["id"]
found2 = c.post("/items", json={"name": "Wallet", "type": 1, "location_id": loc}, headers=U).json()["id"]

show("list items", c.get("/items?limit=2"), 200)
show("filter type+q", c.get("/items?q=keys&type=0"), 200)
show("filter status", c.get("/items?status=open"), 200)
show("match self", c.post("/matches", json={"lost_item_id": lost, "found_item_id": lost}, headers=U), 422)
show("match wrong types", c.post("/matches", json={"lost_item_id": found, "found_item_id": lost}, headers=U), 422)
show("match unknown item", c.post("/matches", json={"lost_item_id": lost, "found_item_id": 4242}, headers=U), 404)
m = show("create match", c.post("/matches", json={"lost_item_id": lost, "found_item_id": found}, headers=U), 201).json()["id"]
show("both now matched", c.get(f"/items/{lost}"), 200)
show("match a matched item", c.post("/matches", json={"lost_item_id": lost, "found_item_id": found2}, headers=U), 409)
show("matches by item", c.get(f"/items/{lost}/matches"), 200)
show("withdraw as other user", c.delete(f"/items/{lost}", headers=V), 403)
show("patch as other user", c.patch(f"/items/{lost}", json={"name": "mine now"}, headers=V), 403)
show("withdraw while matched", c.delete(f"/items/{lost}", headers=U), 409)
show("hard delete as owner", c.delete(f"/items/{lost}/hard", headers=U), 403)
show("create match no auth", c.post("/matches", json={"lost_item_id": lost, "found_item_id": found}), 401)
show("hard delete matched", c.delete(f"/items/{lost}/hard", headers=A), 409)
show("status -> returned", c.patch(f"/items/{lost}/status", json={"status": "returned"}, headers=U), 200)
show("edit returned item", c.patch(f"/items/{lost}", json={"name": "nope"}, headers=U), 409)
show("delete match", c.delete(f"/matches/{m}", headers=U), 204)
show("returned stays returned", c.get(f"/items/{lost}"), 200)
show("other back to open", c.get(f"/items/{found}"), 200)
show("bad transition", c.patch(f"/items/{found}/status", json={"status": "returned"}, headers=U), 409)
show("status matched rejected", c.patch(f"/items/{found}/status", json={"status": "matched"}, headers=U), 422)
show("withdraw", c.delete(f"/items/{found}", headers=U), 204)
show("withdraw is idempotent", c.delete(f"/items/{found}", headers=U), 204)
show("withdrawn hidden", c.get("/items?q=Keyring"), 200)
show("empty patch", c.patch(f"/items/{found2}", json={}, headers=U), 422)
show("patch item", c.patch(f"/items/{found2}", json={"description": "brown leather"}, headers=U), 200)
show("retire loc", c.delete(f"/locations/{loc2}", headers=A), 204)
show("post to retired loc", c.post("/items", json={"name": "Hat", "type": 1, "location_id": loc2}, headers=U), 409)
show("items by location", c.get(f"/locations/{loc}/items"), 200)
show("hard delete loc in use", c.delete(f"/locations/{loc}/hard", headers=A), 409)
show("hard delete empty loc", c.delete(f"/locations/{loc2}/hard", headers=A), 204)
show("list locations", c.get("/locations"), 200)
show("unknown route", c.get("/nope"), 404)
show("method not allowed", c.put(f"/items/{found2}"), 405)
show("unknown item", c.get("/items/9999"), 404)
show("hard delete clean item", c.delete(f"/items/{found2}/hard", headers=A), 204)

print()
if failures:
    print(f"{len(failures)} FAILURES:")
    for f in failures:
        print("  -", f)
    sys.exit(1)
print("all checks passed")