# Milestone 4: Object storage integration

Campus Seekr is our campus lost-and-found API. For this milestone, item photos and 
user files are stored as objects in an S3-compatible store, and each one is indexed 
in Postgres. Everything runs in our own compose stack. Nothing was created 
outside our machines and no account was created anywhere.

## What is in here

| File | Deliverable |
|---|---|
| `STORAGE_DESIGN.md` | 3: key templates, content types, bucket layout. Also has the write order (1), presigned flows (2) and the versioned bucket paragraph (5) |
| `PROVIDER_SHORTLIST.md` | 4: C1–C6 for AWS, Cloudflare and Azure, our choice, and Route B |
| `COST_AND_RISK.md` | 7: lifecycle rules, versioning cost, egress |
| `architecture-diagram.png` | 6: the app, store and database, with the presigned path drawn separately |
| `app/routers/files.py` | 1: upload (single and batch), list, get, download, delete |
| `app/ports/storage.py` | 1: the only module that talks to the store |
| `app/...` (the rest) | Everything else that changed: the `files` table, error codes, the worker's stamp |
| `scripts/storage_report.py` | 5: the storage report, plus a pass over our index |
| `evidence/` | `upload.txt`, `presigned.txt`, `report-clean.txt`, `report-dirty.txt`, `teardown.txt` |
| `adapters/local.env.example` | Every store setting, with a description instead of a value |
| `sources.md` | Every URL we cited, when it was read, and who read it |

In the repo the code is at the same paths from the root. `evidence/capture.sh` regenerates all of the evidence files.

## Who wrote which part

| Part | Who |
|---|---|
| First object storage integration: RustFS in compose, the `images` table and photo endpoints | Doug Varney |
| Storage port, image worker checks and re-encode, `/files` endpoints, gateway upload limit | Parker Scott |
| Storage report (adapted from Parker's homework Part 3 script) | Parker Scott |
| `STORAGE_DESIGN.md`, architecture diagram, this guide | Parker Scott |
| `PROVIDER_SHORTLIST.md` | Parker Scott (AWS, Cloudflare), Doug Varney (AWS, Azure) |
| `COST_AND_RISK.md` | Doug Varney (lifecycle and versioning decisions), Parker Scott (storage and egress math) |
| Users and `user_id` on items | Parker Scott |
| RabbitMQ setup and the worker framework the image worker runs on (from Milestone 2) | Devon Burton |

## Setup

You need Docker with Compose v2, `curl` and `jq`. From the repo root:

```sh
cp .env.local.example .env.local  # then fill in the broker values and JWT_SECRET (see below)
cp store.env.example store.env  # the local defaults work as is
docker compose --env-file .env.local up -d --build --wait
curl -s http://localhost:8000/api/v1/health  # should print {"status":"ok"}
```

The interactive docs are at http://localhost:8000/docs.

### Environment variables

`store.env` has the store settings (each one is described in `adapters/local.env.example`) 
and `.env.local` has the broker settings. Compose sets the rest.

| Variable | Where | What goes in it |
|---|---|---|
| `RABBITMQ_TAG` | `.env.local` | RabbitMQ image tag. `.env.local.example` has the one we use |
| `BROKER_USER`, `BROKER_PASSWORD` | `.env.local` | Any username and password you want. Compose creates that RabbitMQ user and passes it to every service |
| `S3_PORT` | `.env.local` (optional) | Host port for the local store, 9000 by default. If you change it, change `S3_PUBLIC_ENDPOINT_URL` too |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | `store.env` | The store's key pair. Locally these are the RustFS keys on the `storage` service in `compose.yml`. With a provider, a key scoped to just our bucket |
| `AWS_DEFAULT_REGION` | `store.env` | The bucket's region. The local store accepts anything |
| `S3_BUCKET` | `store.env` | Bucket name. The app creates it on startup if it doesn't exist |
| `S3_ENDPOINT_URL` | `store.env` | Where the app and worker reach the store. `http://storage:9000` inside compose, or the provider's S3 endpoint |
| `S3_PUBLIC_ENDPOINT_URL` | `store.env` | The address presigned URLs get signed for, so the client has to be able to reach it. `http://localhost:9000` locally. Leave it unset if it's the same as `S3_ENDPOINT_URL` |
| `DATABASE_URL` | `compose.yml` | Postgres URL for the app and worker. You only need it by hand for `scripts/api_tester.py` (below) |
| `BROKER_HOST` | `compose.yml` | The broker's hostname, `broker` |
| `JWT_SECRET` | `.env.local` | Signs login tokens. Required; the app won't start without it. Generate one with `openssl rand -hex 32` |
| `ADMIN_DISPLAY_NAME`, `ADMIN_PASSWORD` | `.env.local` (optional) | An admin account the app creates on startup. You need one to call the admin routes below. See the Authentication section of the main README |

## Every endpoint

Run these in order on a fresh stack, since the ids assume that. Most write routes need a login token (`Authorization: Bearer ...`) and the admin routes need an admin's token; see the Authentication section of the main README. The commands below sign in first.

```sh
API=http://localhost:8000/api/v1
JSON='Content-Type: application/json'

# ADMIN_DISPLAY_NAME and ADMIN_PASSWORD are the values from .env.local
login() { curl -s -X POST $API/auth/login -d "username=$1&password=$2" | jq -r .access_token; }
ADMIN="Authorization: Bearer $(login "$ADMIN_DISPLAY_NAME" "$ADMIN_PASSWORD")"

# Makes two sample files inside the app container so you don't have to install anything
sample() { docker compose --env-file .env.local exec -T app python -c "import io, sys; from PIL import Image; b = io.BytesIO(); Image.new('RGB', (800, 600), 'teal').save(b, '$1'); sys.stdout.buffer.write(b.getvalue())"; }
sample JPEG > photo.jpg
sample PDF > receipt.pdf
```

### Health

```sh
curl -s $API/health  # API and Postgres
curl -s http://localhost:8000/healthz  # just the gateway
```

### Locations

```sh
curl -s -X POST $API/locations -H "$ADMIN" -H "$JSON" -d '{"name":"Library","coordinates":"40.19,-84.24"}'  # id 1
curl -s -X POST $API/locations -H "$ADMIN" -H "$JSON" -d '{"name":"Old Gym","coordinates":"40.20,-84.25"}'  # id 2
curl -s $API/locations
curl -s $API/locations/1
curl -s -X PATCH $API/locations/1 -H "$ADMIN" -H "$JSON" -d '{"description":"Front desk"}'
curl -s -X DELETE $API/locations/2 -H "$ADMIN"  # retire (204)
curl -s "$API/locations?include_inactive=true"
curl -s -X POST $API/locations/2/restore -H "$ADMIN"
curl -s -X DELETE $API/locations/2/hard -H "$ADMIN"  # real delete, works since no post uses it (204)
```

### Users

```sh
curl -s -X POST $API/users -H "$JSON" -d '{"display_name":"tester1","real_name":"Test User","password":"secret123"}'  # id 2 (the admin is id 1)
AUTH="Authorization: Bearer $(login tester1 secret123)"  # used for everything below that isn't an admin route
curl -s $API/auth/me -H "$AUTH"  # who the token says you are
curl -s $API/users -H "$ADMIN"  # admin only
```

### Items

```sh
curl -s -X POST $API/items -H "$JSON" -H "$AUTH" -d '{"name":"Blue keys","description":"carabiner, 3 keys","type":0,"location_id":1}'  # id 1, lost
curl -s -X POST $API/items -H "$JSON" -H "$AUTH" -d '{"name":"Keyring","type":1,"location_id":1}'  # id 2, found
curl -s "$API/items?type=1&q=key&limit=20&offset=0"
curl -s $API/items/1
curl -s -X PATCH $API/items/1 -H "$JSON" -H "$AUTH" -d '{"description":"carabiner, 3 brass keys"}'
curl -s $API/locations/1/items
```

### Matches

```sh
curl -s -X POST $API/matches -H "$JSON" -H "$AUTH" -d '{"lost_item_id":1,"found_item_id":2}'
curl -s $API/matches
curl -s $API/matches/1
curl -s $API/items/1/matches
curl -s -X PATCH $API/items/1/status -H "$JSON" -H "$AUTH" -d '{"status":"returned"}'
curl -s -X DELETE $API/matches/1 -H "$AUTH"  # item 1 stays returned, item 2 goes back to open
```

### Item photos (presigned)

The photo goes right to the store and never through the API.

```sh
UPLOAD=$(curl -s -X POST $API/items/2/images -H "$AUTH"); echo "$UPLOAD"
UPLOAD_ID=$(echo "$UPLOAD" | jq -r .upload_id)
curl -s -X PUT --upload-file photo.jpg "$(echo "$UPLOAD" | jq -r .upload_url)" -w '%{http_code}\n'
curl -s -X POST $API/items/2/images/$UPLOAD_ID/complete -H "$AUTH"  # 202, processing
curl -s $API/items/2/images/$UPLOAD_ID  # should say ready after a second
curl -s -o fetched.jpg -w '%{http_code} %{content_type}\n' "$(curl -s $API/items/2 | jq -r .photo_url)"
```

### Files (through the API)

```sh
curl -s -X POST $API/files -H "$AUTH" -F file=@receipt.pdf  # owned by the signed-in user
curl -s -X POST $API/files/batch -H "$AUTH" -F files=@receipt.pdf -F files=@photo.jpg
curl -s -H "$AUTH" "$API/files?content_type=application/pdf&name=receipt&limit=20&offset=0"
curl -s -H "$AUTH" $API/files/1
curl -s -D - -o downloaded.pdf -H "$AUTH" $API/files/1/content  # Content-Type: application/pdf
curl -s -X DELETE $API/files/1 -H "$AUTH" -w '%{http_code}\n'  # 204, the object and the row are both gone
```

### Withdrawing and deleting items

```sh
curl -s -X DELETE $API/items/2 -H "$AUTH" -w '%{http_code}\n'  # withdraw (soft delete)
curl -s -X DELETE $API/items/2/hard -H "$ADMIN" -w '%{http_code}\n'  # real delete, the photo gets deleted too
```

## Tests and evidence

With the stack running:

- `scripts/api_tests.sh` is a curl walkthrough of the main flows.
- `scripts/api_tester.py` checks every rule in the error contract. It wipes the database first. Put the Postgres password from `compose.yml` in the URL:
  ```sh
  PYTHONPATH=app JWT_SECRET=$(openssl rand -hex 32) DATABASE_URL='postgresql+psycopg2://seekr:<password>@localhost:5432/seekr' uv run --with httpx2 python scripts/api_tester.py
  ```
- `scripts/storage_report.py` lists every object, flags unstamped and off-scheme keys, and checks the store and the database against each other both ways. Exit code 0 means clean, 1 means it found something, 2 means it couldn't run:
  ```sh
  docker compose --env-file .env.local exec -T app python - < scripts/storage_report.py; echo "exit=$?"
  ```
- `milestones/milestone4/evidence/capture.sh` starts from an empty stack, regenerates all five evidence files, and ends with the teardown.

## Teardown

```sh
docker compose --env-file .env.local down --volumes
docker ps  # nothing of ours should be running
docker volume ls | grep itc531  # empty
docker volume ls | grep campus-seekr  # also empty (our compose project is named campus-seekr)
```

`--volumes` wipes the database, the queue, the logs and every stored object. We don't have migrations, so you need to do this any time a pull changes `app/database/models.py`.
