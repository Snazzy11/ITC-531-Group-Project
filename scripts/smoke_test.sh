#!/bin/bash
# Smoke test for a running stack. Checks that the gateway answers /health, that
# no service has exited, and that an item posted through the API shows up in the
# logger's events.jsonl, which proves API -> RabbitMQ -> logger -> file works.
#
# Bring the stack up first, then from the repo root:
#   docker compose --env-file .env.local up -d --build --wait
#   ADMIN_DISPLAY_NAME=... ADMIN_PASSWORD=... scripts/smoke_test.sh
# CI runs it after building the image. Needs curl and jq.
set -euo pipefail

API=${API:-http://localhost:8000/api/v1}
COMPOSE=(docker compose --env-file "${ENV_FILE:-.env.local}")
EVENTS=/app/logs/events.jsonl
JSON='Content-Type: application/json'
RUN=$(date +%s)

fail() { echo "FAIL: $*" >&2; exit 1; }
login() {
  curl -fsS -X POST "$API/auth/login" --data-urlencode "username=$1" --data-urlencode "password=$2" \
    | jq -r .access_token
}

echo "== health through the gateway"
curl -fsS "$API/health" | jq -e '.status == "ok"' >/dev/null || fail "/health is not ok"

echo "== no service has exited"
exited=$("${COMPOSE[@]}" ps --all --status exited --format '{{.Service}}')
[ -z "$exited" ] || fail "exited: $exited"

echo "== an item posted through the API reaches $EVENTS"
: "${ADMIN_DISPLAY_NAME:?set ADMIN_DISPLAY_NAME}" "${ADMIN_PASSWORD:?set ADMIN_PASSWORD}"
ADMIN="Authorization: Bearer $(login "$ADMIN_DISPLAY_NAME" "$ADMIN_PASSWORD")"
LOCATION=$(curl -fsS -X POST "$API/locations" -H "$JSON" -H "$ADMIN" \
  -d "{\"name\":\"Smoke test $RUN\",\"coordinates\":\"0,0\"}" | jq -r .id)

USER_NAME="smoke-$RUN"
curl -fsS -X POST "$API/users" -H "$JSON" \
  -d "{\"display_name\":\"$USER_NAME\",\"real_name\":\"Smoke Test\",\"password\":\"smoke-test-password\"}" >/dev/null
USER="Authorization: Bearer $(login "$USER_NAME" smoke-test-password)"
ITEM=$(curl -fsS -X POST "$API/items" -H "$JSON" -H "$USER" \
  -d "{\"name\":\"Smoke test item\",\"description\":\"Posted by scripts/smoke_test.sh to check that events reach the log file\",\"type\":0,\"location_id\":$LOCATION}" \
  | jq -r .id)

for _ in $(seq 30); do
  if "${COMPOSE[@]}" exec -T logger cat "$EVENTS" 2>/dev/null \
    | jq -e --argjson id "$ITEM" 'select(.routing_key == "item.created" and .event.payload.item_id == $id)' >/dev/null; then
    echo "item.created for item $ITEM is in $EVENTS. Latest lines:"
    "${COMPOSE[@]}" exec -T logger tail -n 3 "$EVENTS"
    echo "PASS"
    exit 0
  fi
  sleep 1
done
fail "no item.created event for item $ITEM in $EVENTS after 30s"
