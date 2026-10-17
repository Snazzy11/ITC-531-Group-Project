"""Test environment: SQLite in memory, no S3, no broker. Must run before any
app module is imported, because database.py and tokens.py read the environment
at import time."""
import os
import sys
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite://"
os.environ.setdefault("JWT_SECRET", "test-secret-that-is-at-least-32-bytes-long")
os.environ["ADMIN_DISPLAY_NAME"] = "test-admin"
os.environ["ADMIN_PASSWORD"] = "test-admin-passphrase"

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

import sqlalchemy  # noqa: E402
from sqlalchemy import event  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

_create_engine = sqlalchemy.create_engine


def _sqlite_engine(url, *args, **kwargs):
    kwargs["connect_args"] = {"check_same_thread": False}
    kwargs["poolclass"] = StaticPool
    kwargs.pop("pool_pre_ping", None)
    engine = _create_engine(url, *args, **kwargs)

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_conn, _):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    return engine


sqlalchemy.create_engine = _sqlite_engine

from ports import storage  # noqa: E402

storage.ensure_bucket = lambda: None

# CI installs without pillow (it is slow to build), and none of these tests
# decode an image. Stub it only when it is genuinely missing.
try:
    import PIL  # noqa: F401
    import pillow_heif  # noqa: F401
except ModuleNotFoundError:
    from unittest.mock import MagicMock

    for name in ("PIL", "PIL.Image", "PIL.ImageOps", "pillow_heif"):
        sys.modules[name] = MagicMock()
