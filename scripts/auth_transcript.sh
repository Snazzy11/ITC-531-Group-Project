#!/bin/bash
# Transcript for the authentication requirements. The app doesnt need to be running
# Run from the root folder
#
#   scripts/auth_transcript.sh | tee auth_transcript.txt
set -u
cd "$(dirname "$0")/.."
export PYTHONPATH=app DATABASE_URL=sqlite:///:memory: S3_BUCKET=transcript
RUN="uv run --quiet --with httpx2 python -W ignore"

echo '### 1. JWT_SECRET missing: the application fails to start'
echo '$ (unset JWT_SECRET) python -c "import api"'
env -u JWT_SECRET $RUN -c "import api" 2>&1 | tail -2
echo "exit status: ${PIPESTATUS[0]}"
echo
echo '### 1b. JWT_SECRET empty, and too short: also refused'
JWT_SECRET= $RUN -c "import api" 2>&1 | tail -1
JWT_SECRET=short $RUN -c "import api" 2>&1 | tail -1
echo
echo '### 2. JWT_SECRET set: register -> login -> protected endpoint'
JWT_SECRET=$(openssl rand -hex 32) $RUN - <<'PY'
import time
from sqlalchemy.pool import StaticPool
import sqlalchemy
_create = sqlalchemy.create_engine
sqlalchemy.create_engine = lambda *a, **k: _create(*a, connect_args={"check_same_thread": False}, poolclass=StaticPool)
import messaging
messaging.emit = lambda *a, **k: None
from fastapi.testclient import TestClient
import api

c = TestClient(api.app)

def show(cmd, r):
    print(f"$ {cmd}\n  -> {r.status_code} {r.text[:170]}\n")
    return r

user = {"display_name": "ada-lovelace", "real_name": "Ada Lovelace", "password": "correct horse"}
show("POST /users (register)", c.post("/users", json=user))
show("POST /users (same display name again)", c.post("/users", json=user))
r = show("POST /auth/login (right password)", c.post("/auth/login", data={"username": "ada-lovelace", "password": "correct horse"}))
auth = {"Authorization": "Bearer " + r.json()["access_token"]}
show("GET /auth/me (no token)", c.get("/auth/me"))
show("GET /auth/me (with token)", c.get("/auth/me", headers=auth))

print("--- password length: 72 bytes ok, 73 bytes rejected (not truncated) ---")
show("register, 72 ASCII chars", c.post("/users", json={**user, "display_name": "len72-user", "password": "a" * 72}))
show("register, 73 ASCII chars (schema layer, characters)", c.post("/users", json={**user, "display_name": "len73-user", "password": "a" * 73}))
show("register, 40 chars = 80 bytes (hash layer, bytes)", c.post("/users", json={**user, "display_name": "bytes-user", "password": "é" * 40}))
show("login with 73 ASCII chars", c.post("/auth/login", data={"username": "len72-user", "password": "a" * 73}))
show("register, password with edge spaces", c.post("/users", json={**user, "display_name": "space-user", "password": "  spaced  "}))
show("login with the same spaces", c.post("/auth/login", data={"username": "space-user", "password": "  spaced  "}))

print("--- login: one message for both failures, similar time ---")
def timed(label, data):
    t = time.perf_counter(); r = c.post("/auth/login", data=data); dt = time.perf_counter() - t
    print(f"$ POST /auth/login ({label})\n  -> {r.status_code} {r.text[:110]}...  [{dt*1000:.0f} ms]\n")
    return r.json()["error"]["detail"], dt
d1, t1 = timed("no such user", {"username": "nobody-here", "password": "whatever1"})
d2, t2 = timed("wrong password", {"username": "ada-lovelace", "password": "wrong-pass"})
print("same message:", d1 == d2, "| time ratio no-such-user / wrong-password: %.2f" % (t1 / t2))
PY
