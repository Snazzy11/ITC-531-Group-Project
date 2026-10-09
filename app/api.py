"""Lost & Found API: app setup only. The endpoints live in routers/, one module
per concern (items, matches, locations, images, users, files, meta).

    uvicorn api:app --reload      # docs at http://127.0.0.1:8000/docs
"""

import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from database.database import Base, engine
from errors import register_error_handlers
from ports import storage
from routers import files, images, items, locations, matches, meta, users

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    storage.ensure_bucket()
    yield


app = FastAPI(title="Lost & Found API", version="0.2.0", lifespan=lifespan)

# Points every kind of failure at the handlers in errors.py, so nothing escapes
# in FastAPI's default {"detail": "..."} shape.
register_error_handlers(app)

for module in (items, matches, locations, images, users, files, meta):
    app.include_router(module.router)


@app.middleware("http")
async def attach_request_id(request: Request, call_next):
    """Tags each request so a 5xx in the log can be matched to the id the user
    saw in the response.

    The gateway sets X-Request-ID on every proxied request and always
    overwrites whatever the client sent, so adopting it here makes the nginx
    access log and the app log share one id. If you ever expose uvicorn
    directly, drop the header lookup - a client could otherwise choose its own
    id and muddy the logs."""
    request.state.request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    return response


# No migration tool by design. When a column changes, drop the database and let
# this rebuild it; create_all never ALTERs an existing table.
Base.metadata.create_all(bind=engine)
