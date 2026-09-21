"""The error contract.

Routes raise errors the way you already write them, with one extra argument:

    raise APIError(404, ITEM_NOT_FOUND, "item not found")

APIError is just an HTTPException that carries a machine-readable code, so it
travels through FastAPI normally. The handler functions at the bottom of this
file turn everything - APIError, plain HTTPException, Pydantic validation
failures, database outages, and anything unexpected - into one shape:

    {
      "error": {
        "code": "ITEM_NOT_FOUND",
        "detail": "item not found",
        "fields": null,
        "request_id": "8f1c...a5c7"
      }
    }

Why it looks like this:

* `detail` is ALWAYS a string. Your draft had it be "a message, or a list of
  problems for validation errors", which forces every frontend call site to
  check the type before rendering. Field-level problems go in `fields`, which
  is null on everything except a 422.
* `fields` entries are {field, message, type}. `field` is the dotted Pydantic
  location ("body.name"), which maps straight onto a form input.
* `request_id` is also returned as the X-Request-ID header and logged with
  every 5xx, so a bug report can be traced without the response body exposing
  a stack trace, a query, or a hostname.
"""

import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.exc import InterfaceError, OperationalError, SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("lostfound")


# --- the closed set of error codes ------------------------------------------
# Plain strings, so `raise APIError(404, ITEM_NOT_FOUND, ...)` reads like the
# rest of your code.

UNAUTHENTICATED = "UNAUTHENTICATED"
FORBIDDEN = "FORBIDDEN"

NOT_FOUND = "NOT_FOUND"
ITEM_NOT_FOUND = "ITEM_NOT_FOUND"
MATCH_NOT_FOUND = "MATCH_NOT_FOUND"
LOCATION_NOT_FOUND = "LOCATION_NOT_FOUND"

METHOD_NOT_ALLOWED = "METHOD_NOT_ALLOWED"

# 409 - the values sent are fine, the current state forbids the action
ITEM_NOT_OPEN = "ITEM_NOT_OPEN"
ITEM_HAS_MATCHES = "ITEM_HAS_MATCHES"
ITEM_CLOSED = "ITEM_CLOSED"
INVALID_STATUS_TRANSITION = "INVALID_STATUS_TRANSITION"
MATCH_ALREADY_EXISTS = "MATCH_ALREADY_EXISTS"
LOCATION_INACTIVE = "LOCATION_INACTIVE"
LOCATION_IN_USE = "LOCATION_IN_USE"
LOCATION_NAME_TAKEN = "LOCATION_NAME_TAKEN"

# 422 - we cannot process the values that were sent
VALIDATION_ERROR = "VALIDATION_ERROR"
ITEM_TYPE_MISMATCH = "ITEM_TYPE_MISMATCH"
MATCH_SELF = "MATCH_SELF"
EMPTY_UPDATE = "EMPTY_UPDATE"

INTERNAL_ERROR = "INTERNAL_ERROR"
SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"


class APIError(HTTPException):
    """An HTTPException plus a machine-readable code."""

    def __init__(self, status_code: int, code: str, detail: str):
        super().__init__(status_code=status_code, detail=detail)
        self.code = code


# --- the envelope -----------------------------------------------------------

class FieldError(BaseModel):
    field: str
    message: str
    type: str


class ErrorBody(BaseModel):
    code: str
    detail: str
    fields: list[FieldError] | None = None
    request_id: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody


def errors(*status_codes: int) -> dict:
    """Use as `responses=errors.errors(404, 409)` so /docs shows the
    envelope instead of FastAPI's default {"detail": "..."}."""
    return {code: {"model": ErrorResponse} for code in status_codes}


def make_response(request: Request, status_code: int, body: ErrorBody) -> JSONResponse:
    body.request_id = getattr(request.state, "request_id", None)
    return JSONResponse(status_code=status_code, content={"error": body.model_dump()})


# --- handlers ---------------------------------------------------------------
# One function per kind of failure. register_error_handlers() at the bottom
# wires them to the app.

# Codes for HTTPExceptions raised without one (Starlette's own 404 and 405).
STATUS_TO_CODE = {
    401: UNAUTHENTICATED,
    403: FORBIDDEN,
    404: NOT_FOUND,
    405: METHOD_NOT_ALLOWED,
    409: "CONFLICT",
    422: VALIDATION_ERROR,
}

DEFAULT_DETAIL = {
    404: "that endpoint does not exist",
    405: "that method is not allowed on this endpoint",
}


async def handle_http_exception(request: Request, exc: StarletteHTTPException):
    """Covers APIError, plain HTTPException, and Starlette's 404 and 405 on
    unknown routes, so all of them come out in the envelope."""
    code = getattr(exc, "code", None)
    if code:
        detail = exc.detail
    else:
        code = STATUS_TO_CODE.get(exc.status_code, INTERNAL_ERROR)
        detail = DEFAULT_DETAIL.get(exc.status_code, "request failed")
    return make_response(request, exc.status_code, ErrorBody(code=code, detail=detail))


async def handle_validation_error(request: Request, exc: RequestValidationError):
    """FastAPI's 422. One entry per bad field."""
    fields = [
        FieldError(
            field=".".join(str(part) for part in error.get("loc", ())) or "body",
            message=error.get("msg", "invalid value"),
            type=error.get("type", "value_error"),
        )
        # error["input"] and error["ctx"] are dropped on purpose: "input"
        # echoes the submitted payload back and "ctx" can carry internal
        # repr() output.
        for error in exc.errors()
    ]
    body = ErrorBody(
        code=VALIDATION_ERROR,
        detail="the request contains invalid data",
        fields=fields,
    )
    return make_response(request, 422, body)


async def handle_db_unavailable(request: Request, exc: SQLAlchemyError):
    """psycopg raises OperationalError / InterfaceError when Postgres is down,
    the connection dropped, or the pool cannot hand out a live connection."""
    logger.error(
        "database unavailable request_id=%s path=%s",
        getattr(request.state, "request_id", None),
        request.url.path,
        exc_info=exc,
    )
    body = ErrorBody(
        code=SERVICE_UNAVAILABLE,
        detail="the service is temporarily unavailable, please try again",
    )
    return make_response(request, 503, body)


async def handle_db_error(request: Request, exc: SQLAlchemyError):
    """Any other database error. Logged in full, generic to the client."""
    logger.exception(
        "unhandled database error request_id=%s path=%s",
        getattr(request.state, "request_id", None),
        request.url.path,
    )
    body = ErrorBody(code=INTERNAL_ERROR, detail="something went wrong on our end")
    return make_response(request, 500, body)


async def handle_unexpected(request: Request, exc: Exception):
    """Last resort error"""
    logger.exception(
        "unhandled error request_id=%s path=%s",
        getattr(request.state, "request_id", None),
        request.url.path,
    )
    body = ErrorBody(code=INTERNAL_ERROR, detail="something went wrong on our end")
    return make_response(request, 500, body)


def register_error_handlers(app: FastAPI) -> None:
    """Called once from main.py"""
    app.add_exception_handler(StarletteHTTPException, handle_http_exception)
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.add_exception_handler(OperationalError, handle_db_unavailable)
    app.add_exception_handler(InterfaceError, handle_db_unavailable)
    app.add_exception_handler(SQLAlchemyError, handle_db_error)
    app.add_exception_handler(Exception, handle_unexpected)