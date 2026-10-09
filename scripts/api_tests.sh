#!/bin/bash

# Needs the admin account from .env.local (ADMIN_DISPLAY_NAME / ADMIN_PASSWORD):
#   ADMIN_DISPLAY_NAME=... ADMIN_PASSWORD=... scripts/api_tests.sh
# Run on a fresh stack: the ids below assume it.
API=http://localhost:8000/api/v1
JSON='Content-Type: application/json'
login() { curl -s -X POST $API/auth/login -d "username=$1&password=$2" | jq -r .access_token; }

# Sign in as the admin and create a location
ADMIN="Authorization: Bearer $(login "$ADMIN_DISPLAY_NAME" "$ADMIN_PASSWORD")"
curl -s -X POST $API/locations -H "$JSON" -H "$ADMIN" \
  -d '{"name":"Pearce Hall","coordinates":"40.19,-84.24"}'

# Register a user, sign in, and post a lost and a found item (the poster is the signed-in user)
curl -s -X POST $API/users -H "$JSON" \
  -d '{"display_name":"tester1","real_name":"Test User","password":"secret123"}'
USER="Authorization: Bearer $(login tester1 secret123)"
curl -s $API/auth/me -H "$USER"

curl -s -X POST $API/items -H "$JSON" -H "$USER" \
  -d '{"name":"Blue keys","description":"carabiner, 3 keys","type":0,"location_id":1}'

curl -s -X POST $API/items -H "$JSON" -H "$USER" \
  -d '{"name":"Keyring","description":"found by the vending machines","type":1,"location_id":1}'

# Match an item and check its ID
curl -s -X POST $API/matches -H "$JSON" -H "$USER" -d '{"lost_item_id":1,"found_item_id":2}'
curl -s $API/items/1        # "status":"matched"

# Try exceptions
curl -s -w '\n%{http_code}\n' -X DELETE $API/items/1 -H "$USER"        # 409 INVALID_STATUS_TRANSITION
curl -s -w '\n%{http_code}\n' -X DELETE $API/items/1/hard -H "$ADMIN"   # 409 ITEM_HAS_MATCHES
curl -s -w '\n%{http_code}\n' -X POST $API/matches -H "$JSON" -H "$USER" \
  -d '{"lost_item_id":2,"found_item_id":1}'                             # 422 ITEM_TYPE_MISMATCH
curl -s -w '\n%{http_code}\n' -X DELETE $API/locations/1                # 401 UNAUTHENTICATED (no token)
curl -s -w '\n%{http_code}\n' -X DELETE $API/locations/1 -H "$USER"     # 403 FORBIDDEN (not an admin)


# See fields
curl -s -X POST $API/items -H "$JSON" -H "$USER" \
  -d '{"name":"","type":7,"location_id":1,"colour":"blue"}'


# Mark returned, unmatch, and confirm asymmetry
curl -s -X PATCH $API/items/1/status -H "$JSON" -H "$USER" -d '{"status":"returned"}'
curl -s -X DELETE $API/matches/1 -H "$USER"
curl -s $API/items/1    # still "returned" - unmatching does not resurrect it
curl -s $API/items/2    # back to "open"


# Withdraw and confirm hidden
curl -s -X DELETE $API/items/2 -H "$USER"
curl -s "$API/items?q=Keyring"                          # []
curl -s "$API/items?q=Keyring&include_withdrawn=true"   # the withdrawn item