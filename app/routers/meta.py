from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from database.database import get_db

router = APIRouter(tags=["meta"])


@router.get("/health")
def health(db: Session = Depends(get_db)):
    """503 if Postgres is unreachable; the OperationalError handler formats it
    and nothing from psycopg reaches the client."""
    db.execute(text("SELECT 1"))
    return {"status": "ok"}
