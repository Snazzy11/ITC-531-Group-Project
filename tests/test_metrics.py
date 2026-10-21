"""The domain counters on /metrics/: items posted (lost or found) and matches
confirmed. The registry is shared by every test module, so this checks how much
each counter went up rather than its value."""

from uuid import uuid4

import pytest
from api import app
from fastapi.testclient import TestClient
from prometheus_client import REGISTRY

PASSWORD = "a-sufficiently-long-passphrase"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def login(client: TestClient, name: str, password: str) -> dict:
    r = client.post("/auth/login", data={"username": name, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def counters() -> dict[str, float]:
    def value(name, labels=None):
        return REGISTRY.get_sample_value(name, labels or {}) or 0.0

    return {
        "lost": value("seekr_items_posted_total", {"type": "lost"}),
        "found": value("seekr_items_posted_total", {"type": "found"}),
        "matches": value("seekr_matches_confirmed_total"),
    }


def test_posting_and_matching_count_on_the_metrics_endpoint(client):
    admin = login(client, "test-admin", "test-admin-passphrase")  # from conftest
    r = client.post("/locations", json={"name": f"Atrium {uuid4().hex[:8]}", "coordinates": "1,2"}, headers=admin)
    location = r.json()["id"]
    name = f"metrics-{uuid4().hex[:12]}"
    client.post("/users", json={"display_name": name, "real_name": "Metrics Tester", "password": PASSWORD})
    user = login(client, name, PASSWORD)
    description = "A plain test item with a long enough description for the API to accept"

    before = counters()
    lost, found = (
        client.post(
            "/items",
            json={"name": "Thing", "description": description, "type": t, "location_id": location},
            headers=user,
        ).json()["id"]
        for t in (0, 1)
    )
    r = client.post("/matches", json={"lost_item_id": lost, "found_item_id": found}, headers=user)
    assert r.status_code == 201, r.text
    after = counters()

    assert {k: after[k] - before[k] for k in after} == {"lost": 1, "found": 1, "matches": 1}
    scrape = client.get("/metrics/").text
    assert 'seekr_items_posted_total{type="lost"}' in scrape
    assert "seekr_matches_confirmed_total" in scrape
