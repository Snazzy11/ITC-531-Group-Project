#!/usr/bin/env bash
# Regenerates every evidence file in this folder. It starts by wiping the
# stack (down --volumes) so the clean report really is clean, and ends with the
# teardown. Needs .env.local and store.env at the repository root.
#
#   milestones/milestone4/evidence/capture.sh

set -uo pipefail
cd "$(dirname "$0")/../../.."

for tool in docker curl jq; do
    command -v "$tool" >/dev/null || { echo "Install $tool first."; exit 1; }
done
for env in .env.local store.env; do
    [ -f "$env" ] || { echo "Missing $env; see the Setup section of milestones/milestone4/README.md."; exit 1; }
done

OUT=milestones/milestone4/evidence
DC="docker compose --env-file .env.local"
API=http://localhost:8000/api/v1
ADMIN='X-Admin-Token: dev-admin-token'
JSON='Content-Type: application/json'
CODE='\nHTTP %{http_code}\n'
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

# Reads one command from stdin, prints it, runs it.
run() {
    local cmd
    cmd=$(cat)
    printf '$ %s\n' "$cmd"
    eval "$cmd"
    printf '\n'
}

header() {
    printf '%s\n\n' "$1"
    printf "API=%s\nADMIN='%s'\nJSON='%s'\n\n" "$API" "$ADMIN" "$JSON"
}

objects() {
    run <<'EOF'
$DC exec -T app python -c "from ports import storage; [print(size, key) for key, size in storage.list_objects()]"
EOF
}

rows() {
    run <<'EOF'
$DC exec -T db psql -U seekr -d seekr -c "SELECT id, user_id, key, original_filename, content_type, size_bytes, uploaded_at FROM files ORDER BY id"
EOF
}

report() {
    run <<'EOF'
$DC exec -T app python - < scripts/storage_report.py; echo "exit=$?"
EOF
}

# Only what the evidence touches: the app, the image worker, the gateway, and
# their dependencies (Postgres, RabbitMQ, the store).
echo "Starting from an empty stack..."
$DC down --volumes --remove-orphans >/dev/null 2>&1
if ! $DC up -d --build --wait app image_worker gateway >/dev/null 2>&1; then
    echo "The stack did not start. Container states and recent logs:"
    $DC ps -a
    $DC logs --tail 20
    exit 1
fi

sample() {
    $DC exec -T app python -c "import io, sys; from PIL import Image; b = io.BytesIO(); Image.new('RGB', (800, 600), 'teal').save(b, '$1'); sys.stdout.buffer.write(b.getvalue())"
}
sample JPEG > "$TMP/photo.jpg"
sample PDF > "$TMP/resume.pdf"
sample PDF > "$TMP/receipt.pdf"
head -c $((11 * 1024 * 1024)) /dev/zero > "$TMP/big.pdf"
printf '<html><body><script>alert(1)</script></body></html>\n' > "$TMP/not-a-photo.png"

echo "Writing upload.txt..."
{
    header "Uploads through the API: single and batch, the 413 and the 400, listing, download and delete. Sample files are in \$TMP."
    run <<'EOF'
ls -l $TMP
EOF
    run <<'EOF'
curl -s -X POST $API/locations -H "$ADMIN" -H "$JSON" -d '{"name":"Library","coordinates":"40.19,-84.24"}' -w "$CODE"
EOF
    run <<'EOF'
curl -s -X POST $API/users -H "$JSON" -d '{"display_name":"user-one","real_name":"First User","password":"not-a-secret","is_admin":false}' -w "$CODE"
EOF
    run <<'EOF'
curl -s -X POST $API/users -H "$JSON" -d '{"display_name":"user-two","real_name":"Second User","password":"not-a-secret","is_admin":false}' -w "$CODE"
EOF
    echo "# Two users upload resume.pdf: two different keys, neither containing the filename."
    run <<'EOF'
curl -s -X POST $API/files -F user_id=1 -F file=@$TMP/resume.pdf -w "$CODE"
EOF
    run <<'EOF'
curl -s -X POST $API/files -F user_id=2 -F file=@$TMP/resume.pdf -w "$CODE"
EOF
    echo "# Several files in one request."
    run <<'EOF'
curl -s -X POST $API/files/batch -F user_id=1 -F files=@$TMP/receipt.pdf -F files=@$TMP/photo.jpg -w "$CODE"
EOF
    echo "# 413: an 11 MB file; the ceiling is 10 MB."
    run <<'EOF'
curl -s -X POST $API/files -F user_id=1 -F file=@$TMP/big.pdf -w "$CODE"
EOF
    echo "# 400: HTML claiming to be a PNG. The type comes from the bytes, not the claim."
    run <<'EOF'
curl -s -X POST $API/files -F user_id=1 -F "file=@$TMP/not-a-photo.png;type=image/png" -w "$CODE"
EOF
    echo "# 400 in a batch: one bad file and nothing from the request is stored."
    run <<'EOF'
curl -s -X POST $API/files/batch -F user_id=1 -F files=@$TMP/receipt.pdf -F "files=@$TMP/not-a-photo.png;type=image/png" -w "$CODE"
EOF
    echo "# The store and the index: four objects, four rows. Nothing from the refused uploads."
    objects
    rows
    run <<'EOF'
$DC exec -T app python -c "from ports import storage; print(storage.metadata('$(curl -s $API/files/1 | jq -r .key)'))"
EOF
    echo "# Listing: paginated, filtered by content type and by part of the filename."
    run <<'EOF'
curl -s "$API/files?content_type=application/pdf" | jq -c '.[] | {id, original_filename, content_type}'
EOF
    run <<'EOF'
curl -s "$API/files?name=RESUME" | jq -c '.[] | {id, user_id, original_filename}'
EOF
    run <<'EOF'
curl -s "$API/files?limit=2&offset=0" | jq -c '.[] | {id, original_filename}'
EOF
    run <<'EOF'
curl -s "$API/files?limit=2&offset=2" | jq -c '.[] | {id, original_filename}'
EOF
    echo "# Retrieve and download: the stored content type comes back."
    run <<'EOF'
curl -s $API/files/1 -w "$CODE"
EOF
    run <<'EOF'
curl -s -D - -o $TMP/downloaded.pdf $API/files/1/content | grep -i -E '^(HTTP|content-type|content-length|content-disposition)'
EOF
    run <<'EOF'
curl -s -D - -o $TMP/downloaded.jpg $API/files/4/content | grep -i -E '^(HTTP|content-type|content-length)'
EOF
    run <<'EOF'
cmp $TMP/resume.pdf $TMP/downloaded.pdf && echo "downloaded bytes match the upload"
EOF
    echo "# Delete removes the object and the row."
    run <<'EOF'
curl -s -X DELETE $API/files/3 -w "$CODE"
EOF
    run <<'EOF'
curl -s $API/files/3 -w "$CODE"
EOF
    objects
    rows
} > "$OUT/upload.txt" 2>&1

echo "Writing presigned.txt..."
{
    header "Presigned flows: the photo goes from curl straight to the store (port 9000), and is fetched back from the store by curl, not through the API (port 8000)."
    run <<'EOF'
curl -s -X POST $API/items -H "$JSON" -d '{"name":"Blue umbrella","type":1,"location_id":1,"user_id":1}' -w "$CODE"
EOF
    echo "# 1. The API issues a presigned PUT. Note the bytes: this call sends nothing up."
    run <<'EOF'
curl -s -o $TMP/upload.json -X POST $API/items/1/images -w 'HTTP %{http_code}: %{size_upload} bytes sent to the API, %{size_download} bytes of JSON back\n'; jq . $TMP/upload.json
EOF
    UPLOAD_URL=$(jq -r .upload_url "$TMP/upload.json")
    UPLOAD_ID=$(jq -r .upload_id "$TMP/upload.json")
    echo "# 2. curl uploads the photo directly to the store."
    run <<'EOF'
curl -s -X PUT --upload-file $TMP/photo.jpg "$UPLOAD_URL" -w 'HTTP %{http_code}: %{size_upload} bytes sent to %{remote_ip}:%{remote_port}\n'
EOF
    echo "# 3. The completion callback. Again nothing is sent up."
    run <<'EOF'
curl -s -X POST $API/items/1/images/$UPLOAD_ID/complete -w '\nHTTP %{http_code}: %{size_upload} bytes sent to the API\n'
EOF
    for _ in $(seq 30); do
        [ "$(curl -s "$API/items/1/images/$UPLOAD_ID" | jq -r .status)" = processing ] || break
        sleep 1
    done
    run <<'EOF'
curl -s $API/items/1/images/$UPLOAD_ID | jq .
EOF
    echo "# The listing: the processed photo is stored and the pending upload is gone."
    objects
    echo "# The gateway's log has the API calls and no PUT: the photo never passed through it."
    run <<'EOF'
$DC exec -T gateway grep -E 'images|PUT' /var/log/nginx/api.access.log
EOF
    echo "# 4. A presigned GET, fetched by curl straight from the store."
    PHOTO_URL=$(curl -s "$API/items/1" | jq -r .photo_url)
    run <<'EOF'
echo "$PHOTO_URL"
EOF
    run <<'EOF'
curl -s -o $TMP/fetched.jpg "$PHOTO_URL" -w 'HTTP %{http_code}: %{size_download} bytes of %{content_type} from %{remote_ip}:%{remote_port}\n'
EOF
    printf '# Photo bytes that passed through the API: 0. The %s-byte upload and the download both went straight between curl and the store.\n' "$(stat -c %s "$TMP/photo.jpg")"
} > "$OUT/presigned.txt" 2>&1

echo "Writing report-clean.txt..."
{
    printf 'The storage report against our stack after upload.txt and presigned.txt.\n\n'
    report
} > "$OUT/report-clean.txt" 2>&1

echo "Writing report-dirty.txt..."
{
    printf 'The same report after two deliberate faults.\n\n'
    echo "# 1. A presigned PUT whose client never calls /complete: an unstamped object."
    run <<'EOF'
curl -s -o $TMP/abandoned.json -X POST $API/items/1/images -w 'HTTP %{http_code}\n'
EOF
    run <<'EOF'
curl -s -X PUT --upload-file $TMP/photo.jpg "$(jq -r .upload_url $TMP/abandoned.json)" -w 'HTTP %{http_code}\n'
EOF
    echo "# 2. A row removed behind the API's back: an object with no row."
    run <<'EOF'
$DC exec -T db psql -U seekr -d seekr -c "DELETE FROM files WHERE id = 2 RETURNING key"
EOF
    report
} > "$OUT/report-dirty.txt" 2>&1

echo "Writing teardown.txt..."
{
    printf 'Teardown. Our compose project is named campus-seekr, so its volumes are\nnamed campus-seekr_*; both greps are shown.\n\n'
    run <<'EOF'
$DC down --volumes
EOF
    run <<'EOF'
docker ps
EOF
    run <<'EOF'
docker volume ls | grep itc531
EOF
    run <<'EOF'
docker volume ls | grep campus-seekr
EOF
} > "$OUT/teardown.txt" 2>&1

leftovers=$(docker ps --format '{{.Names}}'; docker volume ls -q | grep -E 'itc531|campus-seekr')
if [ -n "$leftovers" ]; then
    echo "teardown.txt is not empty. These are still on this machine (probably from other"
    echo "projects); remove them, e.g. 'docker rm -f NAME' or 'docker volume rm NAME', and run again:"
    echo "$leftovers"
    exit 1
fi
echo "Done: $OUT"
