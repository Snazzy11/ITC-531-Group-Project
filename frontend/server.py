import os
from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from frontend import create_router

API_BASE = (os.getenv("SEEKR_API_BASE") or "http://localhost:8000/api/v1").rstrip("/")
app = FastAPI(title="Seekr")
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")


def call_api(method, path, params=None, payload=None):
    headers = {}
    if os.getenv("SEEKR_ADMIN_TOKEN"):
        headers["X-Admin-Token"] = os.environ["SEEKR_ADMIN_TOKEN"]
    try:
        with httpx.Client(timeout=8, trust_env=False) as client:
            result = client.request(
                method,
                f"{API_BASE}/{path.lstrip('/')}",
                params={
                    key: value
                    for key, value in (params or {}).items()
                    if value not in (None, "")
                },
                json=payload,
                headers=headers,
            )
        return result.status_code, result.json() if result.content else None
    except (httpx.HTTPError, ValueError):
        return 503, {
            "error": {
                "detail": "Service unavailable. Try again later."
            }
        }


app.include_router(create_router(call_api))
