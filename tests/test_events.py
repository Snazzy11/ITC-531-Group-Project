"""Events that end up in the logger's events.jsonl: who publishes what, and the
logger writing them. The broker is stubbed: publish_event is replaced by a
recorder, so these run without RabbitMQ."""

import json
import os
from types import SimpleNamespace
from uuid import uuid4

import crud
import image_processing
import image_worker
import logger
import messaging
import pytest
from api import app
from database.database import SessionLocal
from database.models import ImageStatus
from fastapi.testclient import TestClient
from ports import storage
from sqlalchemy.exc import OperationalError

PASSWORD = "a-sufficiently-long-passphrase"
LOST, FOUND = 0, 1


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def published(monkeypatch) -> list[tuple[str, dict, str]]:
    """Every (event_type, payload, source) published, in order."""
    sent: list[tuple[str, dict, str]] = []

    def record(event_type, payload, source="campus-seekr-api"):
        sent.append((event_type, payload, source))

    monkeypatch.setattr(messaging, "publish_event", record)
    return sent


def login(client: TestClient, name: str, password: str) -> dict:
    r = client.post("/auth/login", data={"username": name, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="module")
def user(client: TestClient) -> dict:
    name = f"events-{uuid4().hex[:12]}"
    body = {"display_name": name, "real_name": "Event Tester", "password": PASSWORD}
    assert client.post("/users", json=body).status_code == 201
    return login(client, name, PASSWORD)


@pytest.fixture(scope="module")
def location(client: TestClient) -> int:
    admin = login(client, "test-admin", "test-admin-passphrase")  # from conftest
    body = {"name": f"Annex {uuid4().hex[:8]}", "coordinates": "1,2"}
    r = client.post("/locations", json=body, headers=admin)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def post_item(client, user, location, item_type) -> int:
    body = {
        "name": "Thing",
        "description": "A plain test item with a long enough description for the API",
        "type": item_type,
        "location_id": location,
    }
    r = client.post("/items", json=body, headers=user)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def of_type(published, event_type) -> list[tuple[dict, str]]:
    return [(payload, source) for t, payload, source in published if t == event_type]


def test_confirming_a_match_publishes_match_confirmed(client, user, location, published):
    lost = post_item(client, user, location, LOST)
    found = post_item(client, user, location, FOUND)
    r = client.post("/matches", json={"lost_item_id": lost, "found_item_id": found}, headers=user)
    assert r.status_code == 201, r.text
    expected = {"match_id": r.json()["id"], "lost_item_id": lost, "found_item_id": found}
    assert of_type(published, "match.confirmed") == [(expected, "campus-seekr-api")]


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (RuntimeError("boom"), 500, "INTERNAL_ERROR"),
        (OperationalError("SELECT 1", {}, Exception("db down")), 503, "SERVICE_UNAVAILABLE"),
    ],
)
def test_server_errors_publish_request_failed(monkeypatch, published, error, status, code):
    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(crud, "get_item", fail)
    with TestClient(app, raise_server_exceptions=False) as c:
        r = c.get("/items/1")
    assert r.status_code == status
    [(payload, _source)] = of_type(published, "request.failed")
    assert payload["request_id"]  # the id the client got, so the two can be matched up
    assert payload == {
        "request_id": r.json()["error"]["request_id"],
        "method": "GET",
        "path": "/items/1",
        "status": status,
        "code": code,
        "error_type": type(error).__name__,
    }


def test_client_errors_publish_nothing(client, published):
    assert client.get("/items/999999").status_code == 404
    assert of_type(published, "request.failed") == []


@pytest.fixture
def processing_upload(client, user, location, monkeypatch) -> tuple[int, str]:
    """An item with one upload waiting for the image worker, and storage stubbed."""
    item_id = post_item(client, user, location, FOUND)
    with SessionLocal() as db:
        image = crud.create_image(db, crud.get_item(db, item_id))
        crud.set_image_status(db, image, ImageStatus.PROCESSING)
        upload_id = image.upload_id
    for name in ("write", "delete"):
        monkeypatch.setattr(storage, name, lambda *args, **kwargs: None)
    return item_id, upload_id


def test_rejected_upload_publishes_image_processed(processing_upload, monkeypatch, published):
    item_id, upload_id = processing_upload
    monkeypatch.setattr(storage, "read", lambda *args: None)  # nothing was uploaded
    image_worker.process(item_id, upload_id)
    expected = {
        "item_id": item_id,
        "upload_id": upload_id,
        "status": "rejected",
        "reject_reason": "no upload was found",
    }
    assert of_type(published, "image.processed") == [(expected, "image-worker")]


def test_accepted_upload_publishes_image_processed(processing_upload, monkeypatch, published):
    item_id, upload_id = processing_upload
    monkeypatch.setattr(storage, "read", lambda *args: b"image bytes")
    monkeypatch.setattr(image_processing, "check_size", lambda data: None)
    monkeypatch.setattr(image_processing, "detect_type", lambda data: "image/png")
    monkeypatch.setattr(image_processing, "reencode", lambda data: b"jpeg bytes")
    image_worker.process(item_id, upload_id)
    expected = {"item_id": item_id, "upload_id": upload_id, "status": "ready"}
    assert of_type(published, "image.processed") == [(expected, "image-worker")]


class FakeChannel:
    def __init__(self):
        self.calls = []

    def basic_ack(self, delivery_tag):
        self.calls.append(("ack", delivery_tag))

    def basic_reject(self, delivery_tag, requeue):
        self.calls.append(("reject", delivery_tag, requeue))


def test_logger_appends_each_event_as_a_line(tmp_path, monkeypatch):
    log_file = tmp_path / "events.jsonl"
    monkeypatch.setattr(logger, "LOG_FILE", log_file)
    channel = FakeChannel()
    event = {"event_type": "match.confirmed", "payload": {"match_id": 1}}

    logger.handle_message(
        channel, SimpleNamespace(delivery_tag=1, routing_key="match.confirmed"), None,
        json.dumps(event).encode(),
    )
    logger.handle_message(
        channel, SimpleNamespace(delivery_tag=2, routing_key="x"), None, b"not json"
    )

    lines = log_file.read_text().splitlines()
    assert [json.loads(line) for line in lines] == [
        {"routing_key": "match.confirmed", "event": event}
    ]
    assert channel.calls == [("ack", 1), ("reject", 2, False)]


@pytest.mark.skipif(os.geteuid() == 0, reason="root can write anywhere")
def test_logger_refuses_to_start_when_it_cannot_write(tmp_path, monkeypatch):
    read_only = tmp_path / "logs"
    read_only.mkdir(mode=0o500)
    monkeypatch.setattr(logger, "LOG_FILE", read_only / "events.jsonl")
    with pytest.raises(SystemExit) as exit_info:
        logger.main()
    assert exit_info.value.code == 1
