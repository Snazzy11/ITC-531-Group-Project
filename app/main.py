"""
Lost & Found API.
Docs at:   http://127.0.0.1:8000/docs
"""

import logging

from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from database import models  # noqa: F401  - imported so create_all sees the tables
from database import database
from errors import register_error_handlers

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="Lost & Found API",
    version="0.1.0",
    description=(
        "Campus lost and found application"
    ),
)

register_error_handlers(app)

database.init_db()

@app.get("/health", tags=["meta"], summary="Liveness + database reachability")
def health():
    try:
        with database.engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except SQLAlchemyError:
        # Raise again for the 503 handler
        raise
    return {"status": "ok"}