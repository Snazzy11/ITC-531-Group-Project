"""End-to-end smoke test against a real Postgres.

    DATABASE_URL=postgresql+psycopg://... python test_api.py

Drops and recreates every table, then exercises each rule in the contract and
prints the status code and body.
"""
import json
import os
import sys

from fastapi.testclient import TestClient

from database import models  # noqa: F401
from database.database import Base, engine

Base.metadata.drop_all(bind=engine)

from main import app  # noqa: E402  (imported after the drop so create_all runs)

c = TestClient(app, raise_server_exceptions=False)
A = {"X-Admin-Token": os.getenv("ADMIN_TOKEN", "dev-admin-token")}
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


show("health", c.get("/health"), 200)
show("create loc no auth", c.post("/locations", json={"name": "X", "coordinates": "1,2"}), 401)
show("create loc bad token", c.post("/locations", json={"name": "X", "coordinates": "1,2"}, headers={"X-Admin-Token": "nope"}), 403)
loc = show("create loc", c.post("/locations", json={"name": "Pearce Hall", "coordinates": "40.1,-84.2"}, headers=A), 201).json()["id"]
show("dup loc name", c.post("/locations", json={"name": "Pearce Hall", "coordinates": "40.1,-84.2"}, headers=A), 409)
loc2 = c.post("/locations", json={"name": "School of Music", "coordinates": "40.3,-84.9"}, headers=A).json()["id"]

show("item bad type", c.post("/items", json={"name": "Keys", "type": 5, "location_id": loc}), 422)
show("item extra field", c.post("/items", json={"name": "Keys", "type": 0, "location_id": loc, "status": "open"}), 422)
show("item unknown loc", c.post("/items", json={"name": "Keys", "type": 0, "location_id": 9999}), 404)
lost = show("create lost item", c.post("/items", json={"name": "Blue keys", "description": "carabiner", "type": 0, "location_id": loc}), 201).json()["id"]
found = show("create found item", c.post("/items", json={"name": "Keyring", "type": 1, "location_id": loc}), 201).json()["id"]
found2 = c.post("/items", json={"name": "Wallet", "type": 1, "location_id": loc}).json()["id"]

show("list items", c.get("/items?limit=2"), 200)
show("filter type+q", c.get("/items?q=keys&type=0"), 200)
show("filter status", c.get("/items?status=open"), 200)
show("match self", c.post("/matches", json={"lost_item_id": lost, "found_item_id": lost}), 422)
show("match wrong types", c.post("/matches", json={"lost_item_id": found, "found_item_id": lost}), 422)
show("match unknown item", c.post("/matches", json={"lost_item_id": lost, "found_item_id": 4242}), 404)
m = show("create match", c.post("/matches", json={"lost_item_id": lost, "found_item_id": found}), 201).json()["id"]
show("both now matched", c.get(f"/items/{lost}"), 200)
show("match a matched item", c.post("/matches", json={"lost_item_id": lost, "found_item_id": found2}), 409)
show("matches by item", c.get(f"/items/{lost}/matches"), 200)
show("withdraw while matched", c.delete(f"/items/{lost}"), 409)
show("hard delete matched", c.delete(f"/items/{lost}/hard", headers=A), 409)
show("status -> returned", c.patch(f"/items/{lost}/status", json={"status": "returned"}), 200)
show("edit returned item", c.patch(f"/items/{lost}", json={"name": "nope"}), 409)
show("delete match", c.delete(f"/matches/{m}"), 204)
show("returned stays returned", c.get(f"/items/{lost}"), 200)
show("other back to open", c.get(f"/items/{found}"), 200)
show("bad transition", c.patch(f"/items/{found}/status", json={"status": "returned"}), 409)
show("status matched rejected", c.patch(f"/items/{found}/status", json={"status": "matched"}), 422)
show("withdraw", c.delete(f"/items/{found}"), 204)
show("withdraw is idempotent", c.delete(f"/items/{found}"), 204)
show("withdrawn hidden", c.get("/items?q=Keyring"), 200)
show("empty patch", c.patch(f"/items/{found2}", json={}), 422)
show("patch item", c.patch(f"/items/{found2}", json={"description": "brown leather"}), 200)
show("retire loc", c.delete(f"/locations/{loc2}", headers=A), 204)
show("post to retired loc", c.post("/items", json={"name": "Hat", "type": 1, "location_id": loc2}), 409)
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