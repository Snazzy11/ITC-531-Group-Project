from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.concurrency import run_in_threadpool


PAGE_FIELDS = {"view", "q", "type", "location_id", "status", "offset"}
NOTICES = {
    "created": "Report saved.",
    "edited": "Changes saved.",
    "matched": "Match created. Both items are now matched.",
    "location-saved": "Location saved.",
    "withdraw": "Report withdrawn.",
    "expire": "Report marked expired.",
    "return": "Report marked returned.",
    "reopen": "Report reopened.",
    "remove-match": "Match removed.",
    "retire": "Location retired.",
    "restore": "Location restored.",
}
ACTIONS = {
    "withdraw": (
        "DELETE",
        "items/{id}",
        None,
        "Withdraw this report? It will disappear from active posts.",
    ),
    "expire": (
        "PATCH",
        "items/{id}/status",
        {"status": "expired"},
        "Change this report to expired?",
    ),
    "return": (
        "PATCH",
        "items/{id}/status",
        {"status": "returned"},
        "Change this report to returned?",
    ),
    "reopen": ("PATCH", "items/{id}/status", {"status": "open"}, "Reopen this report?"),
    "remove-match": (
        "DELETE",
        "matches/{id}",
        None,
        "Remove this match? Matched items will reopen.",
    ),
    "retire": (
        "DELETE",
        "locations/{id}",
        None,
        "Retire this location? Existing posts keep their location.",
    ),
    "restore": (
        "POST",
        "locations/{id}/restore",
        {},
        "Restore this location so new reports can use it?",
    ),
}


def date_label(value):
    try:
        date = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return f"{date.strftime('%b')} {date.day}, {date.year}"
    except (ValueError, AttributeError):
        return str(value)[:10]


def page_url(query):
    query = {key: value for key, value in query.items() if value not in (None, "")}
    return "/?" + urlencode(query) if query else "/"


def return_query(value):
    url = urlsplit(value)
    if url.scheme or url.netloc or url.path != "/":
        return {}
    return {key: value for key, value in parse_qsl(url.query) if key in PAGE_FIELDS}


def form_payload(values, fields, numbers=()):
    payload = {field: values.get(field, "") for field in fields}
    for field in numbers:
        try:
            payload[field] = int(payload[field])
        except (TypeError, ValueError):
            pass
    return payload


def create_router(call_api):
    router = APIRouter()
    templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
    templates.env.filters["date_label"] = date_label

    def render(request, query=None, values=None, failure=None, status_code=200):
        query = dict(request.query_params) if query is None else query
        view = query.get("view", "items")
        if view not in {"items", "matches", "locations"}:
            view = "items"
        filters = {
            key: query.get(key, "") for key in ("q", "type", "location_id", "status")
        }
        try:
            offset = max(0, int(query.get("offset", 0)))
        except ValueError:
            offset = 0
        page = {key: value for key, value in query.items() if key in PAGE_FIELDS}
        api_error = None

        def read(path, params=None, default=None):
            nonlocal api_error, status_code
            code, result = call_api("GET", path, params)
            if code >= 400:
                api_error = result.get("error", {}).get(
                    "detail", "Could not load this page."
                )
                status_code = code
                return default
            return result

        items = read("items", {**filters, "limit": 12, "offset": offset}, [])
        locations = read("locations", {"limit": 100, "include_inactive": "true"}, [])
        location_names = {location["id"]: location["name"] for location in locations}
        for item in items:
            item["location_name"] = location_names.get(
                item["location_id"], "Unknown location"
            )
        matches, all_items = [], items
        if view == "matches":
            matches = read("matches", {"limit": 100}, [])
            all_items = read("items", {"limit": 100, "include_withdrawn": "true"}, [])

        def record(resource, key):
            value = query.get(key)
            if value is None:
                return None
            if not str(value).isdigit() or int(value) < 1:
                raise HTTPException(404, "Record not found.")
            return read(f"{resource}/{int(value)}")

        item = record("items", "item")
        location = record("locations", "location")
        dialog = None
        form_action = ""
        confirmation = None
        if query.get("confirm"):
            action = query["confirm"]
            if action not in ACTIONS:
                raise HTTPException(404, "Action not found.")
            resource = ACTIONS[action][1].split("/")[0]
            target = record(resource, "record")
            if target:
                dialog = "confirm"
                confirmation = ACTIONS[action][3]
                form_action = f"/forms/actions/{action}/{target['id']}"
        elif query.get("form") == "item" and ("item" not in query or item):
            dialog = "item"
            form_action = f"/forms/items/{item['id']}" if item else "/forms/items"
        elif query.get("form") == "location" and ("location" not in query or location):
            dialog = "location"
            form_action = (
                f"/forms/locations/{location['id']}" if location else "/forms/locations"
            )
        elif item:
            dialog = "detail"

        saved_values = (
            item if dialog == "item" else location if dialog == "location" else {}
        )
        form_values = values if values is not None else saved_values or {}
        dialog_titles = {
            "item": "Edit item report" if item else "Report an item",
            "location": "Edit location" if location else "Add a location",
            "detail": "Item details",
            "confirm": "Confirm action",
        }
        details = (failure or {}).get("error", {})
        field_errors = {
            field["field"].removeprefix("body."): field["message"]
            for field in details.get("fields") or []
        }
        status_actions = {
            "open": [("expire", "Mark expired")],
            "matched": [("return", "Mark returned")],
            "withdrawn": [("reopen", "Reopen report")],
            "expired": [("reopen", "Reopen report")],
        }
        return templates.TemplateResponse(
            request=request,
            name="reports.html",
            status_code=status_code,
            context={
                "view": view,
                "items": items,
                "locations": locations,
                "matches": matches,
                "all_items": all_items,
                "item_names": {row["id"]: row["name"] for row in all_items},
                "location_names": location_names,
                "filters": filters,
                "offset": offset,
                "next_url": page_url({**page, "offset": offset + 12}),
                "previous_url": page_url({**page, "offset": max(0, offset - 12)}),
                "api_error": api_error,
                "url": lambda **changes: page_url({**page, **changes}),
                "return_to": page_url(page),
                "dialog": dialog,
                "item": item,
                "location": location,
                "form_action": form_action,
                "values": form_values,
                "form_error": details.get("detail"),
                "field_errors": field_errors,
                "confirmation": confirmation,
                "status_actions": status_actions,
                "dialog_title": dialog_titles.get(dialog),
                "notice": NOTICES.get(query.get("notice")),
            },
        )

    async def read_form(request):
        origin = request.headers.get("origin")
        if origin and origin != str(request.base_url).rstrip("/"):
            raise HTTPException(403, "Unable to submit this form. Refresh the page and try again.")
        return dict(await request.form())

    async def save(request, values, method, path, payload, notice, query):
        code, result = await run_in_threadpool(call_api, method, path, None, payload)
        if code >= 400:
            return await run_in_threadpool(render, request, query, values, result, code)
        destination = return_query(values.get("return_to", "/"))
        return RedirectResponse(
            page_url({**destination, "notice": notice}), status_code=303
        )

    @router.get("/", response_class=HTMLResponse)
    def index(request: Request):
        return render(request)

    async def save_item(request, item_id=None):
        if item_id is not None and item_id < 1:
            raise HTTPException(404, "Record not found.")
        values = await read_form(request)
        fields = ["name", "description", "location_id"]
        numbers = ["location_id"]
        if item_id is None:
            fields.append("type")
            numbers.append("type")
        payload = form_payload(values, fields, numbers)
        query = {**return_query(values.get("return_to", "/")), "form": "item"}
        if item_id is not None:
            query["item"] = item_id
        return await save(
            request,
            values,
            "PATCH" if item_id else "POST",
            f"items/{item_id}" if item_id else "items",
            payload,
            "edited" if item_id else "created",
            query,
        )

    @router.post("/forms/items")
    async def create_item(request: Request):
        return await save_item(request)

    @router.post("/forms/items/{item_id}")
    async def edit_item(item_id: int, request: Request):
        return await save_item(request, item_id)

    @router.post("/forms/matches")
    async def create_match(request: Request):
        values = await read_form(request)
        fields = ["lost_item_id", "found_item_id"]
        return await save(
            request,
            values,
            "POST",
            "matches",
            form_payload(values, fields, fields),
            "matched",
            {"view": "matches"},
        )

    async def save_location(request, location_id=None):
        if location_id is not None and location_id < 1:
            raise HTTPException(404, "Record not found.")
        values = await read_form(request)
        payload = form_payload(values, ["name", "coordinates", "description"])
        query = {"view": "locations", "form": "location"}
        if location_id is not None:
            query["location"] = location_id
        return await save(
            request,
            values,
            "PATCH" if location_id else "POST",
            f"locations/{location_id}" if location_id else "locations",
            payload,
            "location-saved",
            query,
        )

    @router.post("/forms/locations")
    async def create_location(request: Request):
        return await save_location(request)

    @router.post("/forms/locations/{location_id}")
    async def edit_location(location_id: int, request: Request):
        return await save_location(request, location_id)

    @router.post("/forms/actions/{action}/{record_id}")
    async def confirm_action(action: str, record_id: int, request: Request):
        if action not in ACTIONS or record_id < 1:
            raise HTTPException(404, "Action not found.")
        values = await read_form(request)
        method, path, payload, _ = ACTIONS[action]
        query = {
            **return_query(values.get("return_to", "/")),
            "confirm": action,
            "record": record_id,
        }
        return await save(
            request, values, method, path.format(id=record_id), payload, action, query
        )

    return router
