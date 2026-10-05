# Milestone 4: Object storage integration

Campus Seekr, a campus lost-and-found API. Item photos and user files are
stored as objects in an S3-compatible store and indexed in Postgres. Everything
here runs in our own compose stack; nothing was created outside our machines,
and no account was created.

## What is in here

| File | Deliverable |
|---|---|
| `STORAGE_DESIGN.md` | 3: key templates, content types, bucket layout. Also the write order (1), the presigned flows (2) and the versioned-bucket paragraph (5) |
| `PROVIDER_SHORTLIST.md` | 4: C1–C6 for AWS, Cloudflare and Azure, the team's choice, Route B |
| `COST_AND_RISK.md` | 7: lifecycle rules, versioning cost, egress |
| `architecture-diagram.png` | 6: the app, store and database, with the presigned path drawn separately |
| `app/files.py` | 1: upload (single and batch), list, retrieve, download, delete |
| `app/ports/storage.py` | 1: the only module that talks to the store |
| `app/…` (the rest) | Everything else that changed: the `files` table, error codes, the worker's stamp |
| `scripts/storage_report.py` | 5: the storage report, with a pass over our index |
| `evidence/` | `upload.txt`, `presigned.txt`, `report-clean.txt`, `report-dirty.txt`, `teardown.txt` |
| `adapters/local.env.example` | Every store setting, described instead of filled in |
| `sources.md` | Every URL cited, the date read, and who read it |

In the repository, the code lives at the same paths from the repository root,
and `evidence/capture.sh` regenerates every evidence file.

## Who wrote which part

| Part | Who |
|---|---|
| First object-storage integration: the RustFS service in compose, the `images` table and photo endpoints | Doug Varney |
| Storage port, image worker checks and re-encode, `/files` endpoints, gateway upload limit | Parker Scott |
| Storage report (adapted from Parker's homework Part 3 script) | Parker Scott |
| `STORAGE_DESIGN.md`, architecture diagram, this guide | Parker Scott |
| `PROVIDER_SHORTLIST.md` | Parker Scott (AWS, Cloudflare), Doug Varney (AWS, Azure) |
| `COST_AND_RISK.md` | Doug Varney (lifecycle and versioning decisions), Parker Scott (storage and egress arithmetic) |
| Users and the `user_id` on items | Parker Scott |
| The RabbitMQ setup and worker framework the image worker runs on (from Milestone 2) | Devon Burton |

## Setup

You need Docker with Compose v2, `curl` and `jq`. From the repository root:

```sh
cp .env.local.example .env.local   # then fill in the broker values (below)
cp store.env.example store.env     # the local defaults work as they are
docker compose --env-file .env.local up -d --build --wait
curl -s http://localhost:8000/api/v1/health   # {"status":"ok"}
```

The interactive docs are at http://localhost:8000/docs.

### Environment variables

`store.env` holds the store settings, `adapters/local.env.example` describes
each one, and `.env.local` holds the broker settings. Compose sets the rest.

| Variable | Where | What belongs in it |
|---|---|---|
| `RABBITMQ_TAG` | `.env.local` | The RabbitMQ image tag; `.env.local.example` has the one we use |
| `BROKER_USER`, `BROKER_PASSWORD` | `.env.local` | Any user name and password you choose; compose creates that RabbitMQ user and gives it to every service |
| `S3_PORT` | `.env.local` (optional) | Host port for the local store; defaults to 9000. Change `S3_PUBLIC_ENDPOINT_URL` to match |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | `store.env` | The store's access key pair. Locally, the RustFS keys set on the `storage` service in `compose.yml`; with a provider, a key scoped to the one bucket |
| `AWS_DEFAULT_REGION` | `store.env` | The bucket's region. The local store accepts any value |
| `S3_BUCKET` | `store.env` | The bucket name. The app creates it on startup if it does not exist |
| `S3_ENDPOINT_URL` | `store.env` | Where the app and worker reach the store: `http://storage:9000` inside compose, or the provider's S3 endpoint |
| `S3_PUBLIC_ENDPOINT_URL` | `store.env` | The address presigned URLs are signed for, which must be reachable by the client: `http://localhost:9000` locally. Leave unset when it equals `S3_ENDPOINT_URL` |
| `DATABASE_URL` | `compose.yml` | The Postgres URL for the app and worker. Only needed by hand for `scripts/api_tester.py` (below) |
| `BROKER_HOST` | `compose.yml` | The broker's host name, `broker` |
| `ADMIN_TOKEN` | optional | The value admin routes expect in `X-Admin-Token`. Defaults to `dev-admin-token` until real login exists (Milestone 5) |

## Every endpoint

Run these top to bottom on a fresh stack; the ids assume that. Admin routes
take `X-Admin-Token`. There is no login yet, so `user_id` is taken on trust.

```sh
API=http://localhost:8000/api/v1
ADMIN='X-Admin-Token: dev-admin-token'
JSON='Content-Type: application/json'

# Two sample files, made inside the app container so there is nothing to install
sample() { docker compose --env-file .env.local exec -T app python -c "import io, sys; from PIL import Image; b = io.BytesIO(); Image.new('RGB', (800, 600), 'teal').save(b, '$1'); sys.stdout.buffer.write(b.getvalue())"; }
sample JPEG > photo.jpg
sample PDF > receipt.pdf
```

**Health**

```sh
curl -s $API/health                      # the API and Postgres
curl -s http://localhost:8000/healthz    # the gateway alone
```

**Locations**

```sh
curl -s -X POST $API/locations -H "$ADMIN" -H "$JSON" -d '{"name":"Library","coordinates":"40.19,-84.24"}'   # id 1
curl -s -X POST $API/locations -H "$ADMIN" -H "$JSON" -d '{"name":"Old Gym","coordinates":"40.20,-84.25"}'   # id 2
curl -s $API/locations
curl -s $API/locations/1
curl -s -X PATCH $API/locations/1 -H "$ADMIN" -H "$JSON" -d '{"description":"Front desk"}'
curl -s -X DELETE $API/locations/2 -H "$ADMIN"              # retire (204)
curl -s "$API/locations?include_inactive=true"
curl -s -X POST $API/locations/2/restore -H "$ADMIN"
curl -s -X DELETE $API/locations/2/hard -H "$ADMIN"         # real delete; no post uses it (204)
```

**Users**

```sh
curl -s -X POST $API/users -H "$JSON" -d '{"display_name":"tester1","real_name":"Test User","password":"secret123","is_admin":false}'
curl -s $API/users
```

**Items**

```sh
curl -s -X POST $API/items -H "$JSON" -d '{"name":"Blue keys","description":"carabiner, 3 keys","type":0,"location_id":1,"user_id":1}'   # id 1, lost
curl -s -X POST $API/items -H "$JSON" -d '{"name":"Keyring","type":1,"location_id":1,"user_id":1}'                                     # id 2, found
curl -s "$API/items?type=1&q=key&limit=20&offset=0"
curl -s $API/items/1
curl -s -X PATCH $API/items/1 -H "$JSON" -d '{"description":"carabiner, 3 brass keys"}'
curl -s $API/locations/1/items
```

**Matches**

```sh
curl -s -X POST $API/matches -H "$JSON" -d '{"lost_item_id":1,"found_item_id":2}'
curl -s $API/matches
curl -s $API/matches/1
curl -s $API/items/1/matches
curl -s -X PATCH $API/items/1/status -H "$JSON" -d '{"status":"returned"}'
curl -s -X DELETE $API/matches/1        # item 1 stays returned; item 2 goes back to open
```

**Item photos (presigned)**: the photo goes straight to the store, never
through the API.

```sh
UPLOAD=$(curl -s -X POST $API/items/2/images); echo "$UPLOAD"
UPLOAD_ID=$(echo "$UPLOAD" | jq -r .upload_id)
curl -s -X PUT --upload-file photo.jpg "$(echo "$UPLOAD" | jq -r .upload_url)" -w '%{http_code}\n'
curl -s -X POST $API/items/2/images/$UPLOAD_ID/complete     # 202, processing
curl -s $API/items/2/images/$UPLOAD_ID                      # ready a moment later
curl -s -o fetched.jpg -w '%{http_code} %{content_type}\n' "$(curl -s $API/items/2 | jq -r .photo_url)"
```

**Files (through the API)**

```sh
curl -s -X POST $API/files -F user_id=1 -F file=@receipt.pdf
curl -s -X POST $API/files/batch -F user_id=1 -F files=@receipt.pdf -F files=@photo.jpg
curl -s "$API/files?content_type=application/pdf&name=receipt&limit=20&offset=0"
curl -s $API/files/1
curl -s -D - -o downloaded.pdf $API/files/1/content         # Content-Type: application/pdf
curl -s -X DELETE $API/files/1 -w '%{http_code}\n'          # 204; object and row both gone
```

**Withdrawing and deleting items**

```sh
curl -s -X DELETE $API/items/2 -w '%{http_code}\n'               # withdraw (soft delete)
curl -s -X DELETE $API/items/2/hard -H "$ADMIN" -w '%{http_code}\n'  # real delete; its photo goes too
```

## Tests and evidence

With the stack running:

- `scripts/api_tests.sh` is a curl walkthrough of the main flows.
- `scripts/api_tester.py` checks every rule in the error contract. It wipes the
  database first. Put the Postgres password from `compose.yml` in the URL:
  ```sh
  PYTHONPATH=app DATABASE_URL='postgresql+psycopg2://seekr:<password>@localhost:5432/seekr' uv run --with httpx2 python scripts/api_tester.py
  ```
- `scripts/storage_report.py` lists every object, flags unstamped and
  off-scheme keys, and checks the store against the database both ways. Exit
  code 0 is clean, 1 is a finding, 2 is could-not-run:
  ```sh
  docker compose --env-file .env.local exec -T app python - < scripts/storage_report.py; echo "exit=$?"
  ```
- `milestones/milestone4/evidence/capture.sh` starts from an empty stack,
  regenerates all five evidence files, and finishes with the teardown.

## Teardown

```sh
docker compose --env-file .env.local down --volumes
docker ps                                  # nothing of ours running
docker volume ls | grep itc531             # empty
docker volume ls | grep campus-seekr       # empty; our compose project is named campus-seekr
```

`--volumes` wipes the database, queue, logs and every stored object. There are
no migrations, so do this whenever a pull changes `app/database/models.py`.
