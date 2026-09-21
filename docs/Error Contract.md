# Error contract

## Envelope

Every non-2xx response, without exception, looks like this:

```json
{
  "error": {
    "code": "ITEM_NOT_FOUND",
    "detail": "item not found",
    "fields": null,
    "request_id": "8f1c4e2a9b7d4f01a3c5e7b9d1f3a5c7"
  }
}
```

Routes stay in the shape you already write — `APIError` is an `HTTPException`
with one extra argument:

```python
raise APIError(404, errors.ITEM_NOT_FOUND, "item not found")
```

Three changes from your draft:

**`detail` is always a string.** The draft had it be "a readable message for
ordinary errors, or a list of problems for validation errors." A union type
means every frontend call site has to type-check before rendering, and someone
will eventually forget and print `[object Object]`. Field problems go in
`fields` instead, which is `null` everywhere else.

**`fields` is a list of `{field, message, type}`** on 422s. `field` is the
dotted Pydantic location (`body.name`, `query.limit`), which maps straight onto
a form input. The handler deliberately drops Pydantic's `input` and `ctx` keys:
`input` echoes the submitted value back, and `ctx` can contain `repr()` of
internal objects.

**`request_id`** is generated per request, returned in the body and the
`X-Request-ID` header, and logged with every 5xx. Someone can paste an ID into
a bug report without the response body ever exposing a stack trace, a query, or
a hostname.

## Which status code

The rule that settles the ambiguous cases:

- **422** — we cannot process the values that were sent. Malformed payload, or
  values wrong on their face regardless of what is in the database (an item
  matched with itself, a `lost_item_id` pointing at a found post).
- **409** — the values are fine; the *current state* forbids the action. The
  item is already matched, the location is retired, a row still references it.
- **404** — a resource named in the request does not exist, no matter where the
  id came from. `POST /matches` with an unknown `lost_item_id` is a 404, not a
  422, so the frontend has one rule to learn.

409 was the one genuinely missing code in the draft. Without it, "this item is
already matched" and "the name field is empty" both arrive as 422 and the
frontend cannot tell them apart — one is fixable by editing the form, the other
is not.

## Full table

| Status | Code | Raised when |
|---|---|---|
| 401 | `UNAUTHENTICATED` | Admin route, no credentials |
| 403 | `FORBIDDEN` | Signed in, not an admin |
| 404 | `NOT_FOUND` | Unknown route |
| 404 | `ITEM_NOT_FOUND` / `MATCH_NOT_FOUND` / `LOCATION_NOT_FOUND` | Referenced row missing |
| 405 | `METHOD_NOT_ALLOWED` | Wrong verb on a real path |
| 409 | `ITEM_NOT_OPEN` | Matching an item that is not `open` |
| 409 | `ITEM_HAS_MATCHES` | Hard-deleting an item that is in a match |
| 409 | `ITEM_CLOSED` | Editing a `returned` post |
| 409 | `INVALID_STATUS_TRANSITION` | e.g. `open` → `returned` |
| 409 | `MATCH_ALREADY_EXISTS` | Duplicate pair (`uq_matches_item_pair`) |
| 409 | `LOCATION_INACTIVE` | Posting to a retired location |
| 409 | `LOCATION_IN_USE` | Hard-deleting a location that has items |
| 409 | `LOCATION_NAME_TAKEN` | Duplicate location name |
| 422 | `VALIDATION_ERROR` | Pydantic rejected the payload; `fields` populated |
| 422 | `ITEM_TYPE_MISMATCH` | A match side points at the wrong `type` |
| 422 | `MATCH_SELF` | `lost_item_id == found_item_id` |
| 422 | `EMPTY_UPDATE` | PATCH body changes nothing |
| 500 | `INTERNAL_ERROR` | Anything unexpected; fixed generic message |
| 503 | `SERVICE_UNAVAILABLE` | `OperationalError` / `InterfaceError` from psycopg |

## Success codes

- **200** — retrieved or updated.
- **201** — created; body is the new resource.
- **204** — withdrawn, unmatched, or retired; no body. `DELETE /items/{id}` is
  idempotent, so withdrawing an already-withdrawn item is still a 204.

## Every constraint is checked twice

Each uniqueness and FK rule is checked in Python *and* caught as an
`IntegrityError` on commit. The Python check exists to produce a decent
message; the `try/except IntegrityError` exists because the check has a race
window between the SELECT and the INSERT. Two users matching the same pair at
the same instant both pass the check, and the loser hits the unique index —
with the except clause they still get `409 MATCH_ALREADY_EXISTS` instead of a
500.

## What never reaches the client

No exception text, SQL, table name, hostname, file path, or submitted input.
5xx bodies use a fixed string and the real error goes to the log with the
request id. The same discipline applies to the auth routes when they land:
"those credentials are not valid," never anything that reveals whether an email
is registered.