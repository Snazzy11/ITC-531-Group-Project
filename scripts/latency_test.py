"""Latency distribution for the final product's evaluation (EVALUATION.md, b).

Standard library only, so it runs on a laptop or on the EC2 instance itself:

    python3 scripts/latency_test.py http://HOST:8000 browse  --requests 2000 --concurrency 10
    python3 scripts/latency_test.py http://HOST:8000 login   --requests 300  --concurrency 10
    python3 scripts/latency_test.py http://HOST:8000 post    --requests 300  --concurrency 10
    python3 scripts/latency_test.py http://HOST:8000 photo   --requests 100  --concurrency 5

Each worker thread keeps one HTTP/1.1 connection open, as a browser would, and
reconnects only if the server closes it. A few untimed warm-up requests open the
connections first. Only the request that matters is timed: for "photo" the
upload link and the PUT to the object store happen beforehand, and only
POST .../complete is timed.

login, post and photo read SEEKR_USER and SEEKR_PASSWORD from the environment
(an ordinary account; the password is never printed).
"""

import argparse
import http.client
import json
import math
import os
import statistics
import threading
import time
import urllib.parse
import urllib.request
from collections import Counter

WARMUP = 5
PHOTO = b""
WORDS = ["red", "blue", "black", "grey", "green", "silver", "small", "large", "leather", "canvas", "zip", "strap", "scratched"]


class Client:
    def __init__(self, base: str):
        url = urllib.parse.urlsplit(base)
        self.host, self.port = url.hostname, url.port or 80
        self.conn = None

    def request(self, method: str, path: str, body: bytes | None = None, headers: dict | None = None):
        for attempt in (1, 2):
            if self.conn is None:
                self.conn = http.client.HTTPConnection(self.host, self.port, timeout=30)
            try:
                start = time.perf_counter()
                self.conn.request(method, path, body=body, headers=headers or {})
                response = self.conn.getresponse()
                data = response.read()
                return response.status, (time.perf_counter() - start) * 1000, data
            except (http.client.HTTPException, OSError):
                self.conn.close()
                self.conn = None
                if attempt == 2:
                    raise


def login(base: str) -> str:
    form = urllib.parse.urlencode(
        {"username": os.environ["SEEKR_USER"], "password": os.environ["SEEKR_PASSWORD"]}
    ).encode()
    with urllib.request.urlopen(f"{base}/api/v1/auth/login", data=form, timeout=30) as r:
        return json.load(r)["access_token"]


def make_job(kind: str, base: str):
    """Returns (setup, timed) for one request. setup runs untimed and returns
    what timed needs."""
    form_type = {"Content-Type": "application/x-www-form-urlencoded"}
    if kind == "browse":
        return None, lambda c, _: c.request("GET", "/api/v1/items?limit=20")
    if kind == "login":
        form = urllib.parse.urlencode(
            {"username": os.environ["SEEKR_USER"], "password": os.environ["SEEKR_PASSWORD"]}
        )
        return None, lambda c, _: c.request("POST", "/api/v1/auth/login", form.encode(), form_type)

    auth = {"Authorization": f"Bearer {login(base)}", "Content-Type": "application/json"}
    if kind == "post":
        counter = iter(range(10**9))

        def post(c, _):
            n = next(counter)
            words = " ".join(WORDS[(n + i) % len(WORDS)] for i in range(4))
            item = {
                "name": f"Load test bag {n}",
                "description": f"Load test item {n}: a {words} backpack left in a lecture hall",
                "type": n % 2,
                "location_id": 1,
            }
            return c.request("POST", "/api/v1/items", json.dumps(item).encode(), auth)

        return None, post
    if kind == "photo":
        with urllib.request.urlopen(
            urllib.request.Request(
                f"{base}/api/v1/items",
                data=json.dumps(
                    {
                        "name": "Load test photo item",
                        "description": "An item that exists only to receive photos during the latency test",
                        "type": 1,
                        "location_id": 1,
                    }
                ).encode(),
                headers=auth,
            ),
            timeout=30,
        ) as r:
            item_id = json.load(r)["id"]

        def setup(c):
            status, _, data = c.request("POST", f"/api/v1/items/{item_id}/images", b"", auth)
            assert status == 201, (status, data)
            upload = json.loads(data)
            put = urllib.request.Request(upload["upload_url"], data=PHOTO, method="PUT")
            with urllib.request.urlopen(put, timeout=30) as r:
                assert r.status == 200
            return upload["upload_id"]

        def complete(c, upload_id):
            return c.request("POST", f"/api/v1/items/{item_id}/images/{upload_id}/complete", b"", auth)

        return setup, complete
    raise SystemExit(f"unknown kind {kind}")


def percentile(values: list[float], p: float) -> float:
    """Nearest-rank percentile: the smallest sample with at least p% of samples at or below it."""
    ordered = sorted(values)
    return ordered[max(1, math.ceil(p / 100 * len(ordered))) - 1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("base", help="e.g. http://18.222.255.231:8000")
    parser.add_argument("kind", choices=["browse", "login", "post", "photo"])
    parser.add_argument("--requests", type=int, default=200)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--photo", default=None, help="file to upload for kind=photo")
    args = parser.parse_args()
    base = args.base.rstrip("/")
    global PHOTO
    if args.photo:
        with open(args.photo, "rb") as f:
            PHOTO = f.read()

    setup, timed = make_job(args.kind, base)
    lock = threading.Lock()
    remaining = [args.requests]
    samples: list[float] = []
    statuses: Counter = Counter()

    def worker():
        client = Client(base)
        for _ in range(WARMUP):  # untimed: opens the connection
            client.request("GET", "/api/v1/health")
        while True:
            with lock:
                if remaining[0] == 0:
                    return
                remaining[0] -= 1
            prepared = setup(client) if setup else None
            status, ms, _ = timed(client, prepared)
            with lock:
                samples.append(ms)
                statuses[status] += 1

    started_at = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
    wall = time.perf_counter()
    threads = [threading.Thread(target=worker) for _ in range(args.concurrency)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    wall = time.perf_counter() - wall

    server_errors = sum(n for s, n in statuses.items() if s >= 500)
    print(
        json.dumps(
            {
                "kind": args.kind,
                "base": base,
                "started": started_at,
                "requests": len(samples),
                "concurrency": args.concurrency,
                "statuses": dict(sorted(statuses.items())),
                "server_error_rate": round(server_errors / len(samples), 4),
                "p50_ms": round(percentile(samples, 50), 1),
                "p95_ms": round(percentile(samples, 95), 1),
                "p99_ms": round(percentile(samples, 99), 1),
                "max_ms": round(max(samples), 1),
                "mean_ms": round(statistics.fmean(samples), 1),
                "wall_s": round(wall, 1),
                "throughput_rps": round(len(samples) / wall, 1),
                "note": "photo timings cover only POST .../complete" if args.kind == "photo" else "",
            }
        )
    )


if __name__ == "__main__":
    main()
