#!/usr/bin/env bash

GATEWAY_URL="http://localhost/api/endpoint" # Update to your gateway URL/path
TEST_ID="distribution-rerun-920602"

echo "=== Sending 30 Requests ==="
for i in $(seq 1 30); do
  curl -s "${GATEWAY_URL}?evidence=${TEST_ID}&request=${i}" > /dev/null
  echo -n "."
done
echo -e "\nDone!\n"

echo "=== Gateway Log Output ==="
docker compose exec -T gateway grep "evidence=${TEST_ID}&request=" /var/log/nginx/api.access.log