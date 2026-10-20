"""Matching: scoring, the worker, what triggers it, and the two endpoints. The
broker is stubbed: jobs and events are recorded instead of sent. The database is
shared with the other test modules, so assertions only look at items the test
itself created."""

from uuid import uuid4

import matching_worker
import messaging
import pytest
from api import app
from database.database import SessionLocal
from database.models import PotentialMatch
from fastapi.testclient import TestClient
from matching import matcher
from pika.exceptions import AMQPConnectionError
from sqlalchemy import select

PASSWORD = "a-sufficiently-long-passphrase"
LOST, FOUND = 0, 1


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def login(client: TestClient, name: str, password: str) -> dict:
    r = client.post("/auth/login", data={"username": name, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="module")
def admin(client: TestClient) -> dict:
    return login(client, "test-admin", "test-admin-passphrase")  # from conftest


@pytest.fixture(scope="module")
def user(client: TestClient) -> dict:
    name = f"matcher-{uuid4().hex[:12]}"
    body = {"display_name": name, "real_name": "Match Tester", "password": PASSWORD}
    assert client.post("/users", json=body).status_code == 201
    return login(client, name, PASSWORD)


@pytest.fixture(scope="module")
def location(client: TestClient, admin: dict) -> int:
    body = {"name": f"Hall {uuid4().hex[:8]}", "coordinates": "1,2"}
    r = client.post("/locations", json=body, headers=admin)
    assert r.status_code == 201, r.text
    return r.json()["id"]


@pytest.fixture
def jobs(monkeypatch) -> list[int]:
    """Item ids the API queued for matching, in order."""
    queued: list[int] = []
    monkeypatch.setattr(messaging, "publish_matching_job", queued.append)
    return queued


@pytest.fixture
def announced(monkeypatch) -> list[dict]:
    """match.potential_found payloads the worker published, in order."""
    sent: list[dict] = []

    def record(event_type, payload, source="campus-seekr-api"):
        if event_type == "match.potential_found":
            sent.append(payload)

    monkeypatch.setattr(messaging, "publish_event", record)
    return sent


def post_item(client, user, location, item_type, description) -> int:
    body = {"name": "Thing", "description": description, "type": item_type, "location_id": location}
    r = client.post("/items", json=body, headers=user)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def suggested(client, item_id) -> list[tuple[int, int]]:
    r = client.get(f"/items/{item_id}/potential-matches")
    assert r.status_code == 200, r.text
    return [(m["lost_item_id"], m["found_item_id"]) for m in r.json()]


def test_words_ignore_punctuation_and_common_words():
    text = "Found: a Black backpack, with the red ZIPPER."
    assert matcher.words(text) == ["black", "backpack", "red", "zipper"]


def test_worker_suggests_open_items_of_the_other_type(client, user, location, announced):
    scarf = "Red wool scarf with white stripes, left on a bench by the north entrance"
    lost = post_item(client, user, location, LOST, scarf)
    best = post_item(client, user, location, FOUND, "Red wool scarf, white stripes, found on a bench by the north entrance")
    weaker = post_item(client, user, location, FOUND, "Red umbrella with a bent spoke, found leaning against a bench outside")
    unrelated = post_item(client, user, location, FOUND, "Graphing calculator with a cracked screen, found in the math lab")
    same_type = post_item(client, user, location, LOST, scarf)
    withdrawn = post_item(client, user, location, FOUND, scarf)
    assert client.delete(f"/items/{withdrawn}", headers=user).status_code == 204

    matching_worker.process(lost)

    mine = {best, weaker, unrelated, same_type, withdrawn}
    found_ids = [f for lo, f in suggested(client, lost) if f in mine]
    assert found_ids == [best, weaker]  # best first; no score-0, same-type or closed items
    assert [p["found_item_id"] for p in announced if p["found_item_id"] in mine] == [best, weaker]
    assert all(p["lost_item_id"] == lost and p["score"] > 0 for p in announced)


def test_rerun_replaces_suggestions_and_announces_only_new_pairs(client, user, location, announced):
    lost = post_item(client, user, location, LOST, "Brass trombone with a dented bell, left behind in rehearsal room 204")
    first = post_item(client, user, location, FOUND, "Brass trombone, dented bell, found in rehearsal room 204 last night")
    matching_worker.process(lost)
    assert first in [p["found_item_id"] for p in announced]

    announced.clear()
    matching_worker.process(lost)
    assert announced == []  # the same pairs again are not announced twice

    second = post_item(client, user, location, FOUND, "Trombone mouthpiece made of brass, picked up in rehearsal room 204")
    assert client.delete(f"/items/{first}", headers=user).status_code == 204  # withdraw it
    matching_worker.process(lost)
    assert [p["found_item_id"] for p in announced if p["found_item_id"] in (first, second)] == [second]

    with SessionLocal() as db:
        stored = db.scalars(
            select(PotentialMatch.found_item_id).where(PotentialMatch.lost_item_id == lost)
        ).all()
    assert first not in stored and second in stored  # the withdrawn item's pair was replaced


def test_keeps_at_most_five_suggestions(client, user, location, announced):
    lost = post_item(client, user, location, LOST, "Bright yellow kazoo, dropped during parade practice on the quad")
    for n in range(7):
        post_item(client, user, location, FOUND, f"Yellow kazoo number {n}, picked up on the quad after parade practice")
    matching_worker.process(lost)
    assert len(suggested(client, lost)) == matcher.MAX_SUGGESTIONS == 5


def test_potential_matches_hide_pairs_that_can_no_longer_be_matched(client, user, location, announced):
    lost = post_item(client, user, location, LOST, "Green ceramic mug with a chipped handle and a frog painted on the side")
    found = post_item(client, user, location, FOUND, "Green ceramic mug, chipped handle, little frog painted on it")
    matching_worker.process(lost)
    assert (lost, found) in suggested(client, found)  # visible from either item

    r = client.post("/matches", json={"lost_item_id": lost, "found_item_id": found}, headers=user)
    assert r.status_code == 201
    assert (lost, found) not in suggested(client, found)
    assert client.get("/items/999999/potential-matches").status_code == 404


def test_posting_reopening_and_unmatching_queue_matching(client, user, location, jobs):
    lost = post_item(client, user, location, LOST, "Blue denim jacket with a torn left pocket, left in the cafeteria")
    found = post_item(client, user, location, FOUND, "Blue denim jacket, torn pocket, sitting on a cafeteria chair at lunch")
    assert jobs == [lost, found]

    jobs.clear()
    assert client.delete(f"/items/{lost}", headers=user).status_code == 204  # withdraw: nothing queued
    r = client.patch(f"/items/{lost}/status", json={"status": "open"}, headers=user)
    assert r.status_code == 200
    assert jobs == [lost]

    jobs.clear()
    match = client.post("/matches", json={"lost_item_id": lost, "found_item_id": found}, headers=user)
    assert match.status_code == 201
    assert jobs == []
    assert client.delete(f"/matches/{match.json()['id']}", headers=user).status_code == 204
    assert jobs == [lost, found]  # the unmatch reopened both


def test_match_search_is_admin_only_and_queues_a_job(client, user, admin, location, jobs, monkeypatch):
    item = post_item(client, user, location, LOST, "Silver bracelet with a heart-shaped charm, dropped by the fountain")
    jobs.clear()
    url = f"/items/{item}/match-search"

    assert client.post(url).status_code == 401
    assert client.post(url, headers=user).status_code == 403
    assert client.post("/items/999999/match-search", headers=admin).status_code == 404

    r = client.post(url, headers=admin)
    assert r.status_code == 202, r.text
    assert r.json() == {"item_id": item, "status": "queued"}
    assert jobs == [item]

    def broker_down(item_id):
        raise AMQPConnectionError("broker is down")

    monkeypatch.setattr(messaging, "publish_matching_job", broker_down)
    r = client.post(url, headers=admin)
    assert r.status_code == 503
    assert r.json()["error"]["code"] == "SERVICE_UNAVAILABLE"

    assert client.delete(f"/items/{item}", headers=user).status_code == 204
    r = client.post(url, headers=admin)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "ITEM_NOT_OPEN"
