from database.database import get_db
from fastapi import APIRouter, Depends, Response
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

router = APIRouter(tags=["meta"])


@router.get("/health")
def health(response: Response, db: Session = Depends(get_db)):
    """Check database connectivity without exposing connection details."""
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        response.status_code = 503
        return {"status": "degraded", "checks": {"database": "error"}}
    return {"status": "ok", "checks": {"database": "ok"}}
