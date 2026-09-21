#!/bin/bash

API=http://localhost:8000/api/v1
ADMIN='X-Admin-Token: dev-admin-token'
JSON='Content-Type: application/json'


# Create a location, a lost post, and a found post
curl -s -X POST $API/locations -H "$JSON" -H "$ADMIN" \
  -d '{"name":"Pearce Hall","coordinates":"40.19,-84.24"}'

curl -s -X POST $API/items -H "$JSON" \
  -d '{"name":"Blue keys","description":"carabiner, 3 keys","type":0,"location_id":1}'

curl -s -X POST $API/items -H "$JSON" \
  -d '{"name":"Keyring","description":"found by the vending machines","type":1,"location_id":1}'

# Match an item and check its ID
curl -s -X POST $API/matches -H "$JSON" -d '{"lost_item_id":1,"found_item_id":2}'
curl -s $API/items/1        # "status":"matched"

# Try exceptions
curl -s -w '\n%{http_code}\n' -X DELETE $API/items/1                    # 409 INVALID_STATUS_TRANSITION
curl -s -w '\n%{http_code}\n' -X DELETE $API/items/1/hard -H "$ADMIN"   # 409 ITEM_HAS_MATCHES
curl -s -w '\n%{http_code}\n' -X POST $API/matches -H "$JSON" \
  -d '{"lost_item_id":2,"found_item_id":1}'                             # 422 ITEM_TYPE_MISMATCH
curl -s -w '\n%{http_code}\n' -X DELETE $API/locations/1                # 401 UNAUTHENTICATED


# See fields
curl -s -X POST $API/items -H "$JSON" \
  -d '{"name":"","type":7,"location_id":1,"colour":"blue"}'


# Mark returned, unmatch, and confirm asymmetry
curl -s -X PATCH $API/items/1/status -H "$JSON" -d '{"status":"returned"}'
curl -s -X DELETE $API/matches/1
curl -s $API/items/1    # still "returned" — unmatching does not resurrect it
curl -s $API/items/2    # back to "open"


# Withdraw and confirm hidden
curl -s -X DELETE $API/items/2
curl -s "$API/items?q=Keyring"                          # []
curl -s "$API/items?q=Keyring&include_withdrawn=true"   # the withdrawn item