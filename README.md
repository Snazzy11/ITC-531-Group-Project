# ITC-531-Group-Project

A campus lost-and-found API: post lost or found items with a photo, and match
lost posts with found ones.

# Running it

You need `docker compose` on your machine. Then you can do the following steps:
```sh
git clone https://github.com/Snazzy11/ITC-531-Group-Project
cd ITC-531-Group-Project
```
Copy `.env.local` and fill it in: `cp .env.local.example .env.local`

| Variable                               | What to put |
|----------------------------------------|---|
| `BROKER_USER` & `BROKER_PASSWORD`      | Any username and password; compose creates that RabbitMQ user |
| `JWT_SECRET`                           | Required. Signs login tokens. Generate one with `openssl rand -hex 32`. The app will not start without it |
| `ADMIN_DISPLAY_NAME`, `ADMIN_PASSWORD` | Needed to use any admin route (managing locations, hard deletes, listing users). The app creates this admin account on startup. Display name up to 50 characters, password up to 72 bytes. See [Authentication](#authentication) |

Copy the store env file, the defaults there will work: `cp store.env.example store.env`

Bring the container up and test it:
```sh
docker compose --env-file .env.local up -d --build --wait
curl http://localhost:8000/api/v1/health   # {"status":"ok"}
```

Stop it with `docker compose --env-file .env.local down`. Adding `--volumes`
also wipes the database, queue, and stored photos. There are no migrations, so
run that whenever a pull changes `app/database/models.py`. (The login change did
this: `users.is_admin` is gone and the `roles` tables are new.)

| URL | What |
|---|---|
| http://localhost:8000/docs | Every endpoint, with request and response shapes |
| http://localhost:8000/api/v1 | The API |
| http://localhost:15672 | RabbitMQ dashboard (log in with your broker user) |
| http://localhost:9000 | Local S3 API (RustFS), where photos are stored |

## First requests

Reading the API is almost always public. Anything that writes needs signed in account.
You must register if needed, log in for a token, and send the token with each request.
More details in [Authentication](#authentication)). `jq` is used to pull the token out.

`ADMIN_DISPLAY_NAME` and `ADMIN_PASSWORD` are the values from `.env.local`. You will 
need to export them in your shell before running this.

```sh
API=http://localhost:8000/api/v1
login() { curl -s -X POST $API/auth/login -d "username=$1&password=$2" | jq -r .access_token; }

# 1. The admin from .env.local makes a location (only admins can)
ADMIN="Authorization: Bearer $(login "$ADMIN_DISPLAY_NAME" "$ADMIN_PASSWORD")"
curl -X POST $API/locations -H "$ADMIN" -H 'Content-Type: application/json' \
  -d '{"name":"Library","coordinates":"40.19,-84.24"}'

# 2. Anyone can register; then log in
curl -X POST $API/users -H 'Content-Type: application/json' \
  -d '{"display_name":"tester1","real_name":"Test User","password":"secret123"}'
USER="Authorization: Bearer $(login tester1 secret123)"
curl $API/auth/me -H "$USER"       # shows who the token belongs to

# 3. Post an item. The poster is whoever the token belongs to; do not send a user_id
curl -X POST $API/items -H "$USER" -H 'Content-Type: application/json' \
  -d '{"name":"Blue umbrella","type":1,"location_id":1}'   # type: 0 = lost, 1 = found
```

To add a photo or upload a file, see `milestones/milestone4/README.md`, which
has a runnable command for every endpoint.

## Tests

With the stack running:

- `scripts/api_tests.sh` is a curl walkthrough of the main flows. It signs in as the admin, so run it as `ADMIN_DISPLAY_NAME=... ADMIN_PASSWORD=... scripts/api_tests.sh` on a fresh stack.
- `scripts/api_tester.py` checks every rule in the error contract. It wipes the
  database first.
  ```sh
  PYTHONPATH=app JWT_SECRET=$(openssl rand -hex 32) DATABASE_URL=postgresql+psycopg2://seekr:seekr-devonly@localhost:5432/seekr uv run --with httpx2 python scripts/api_tester.py
  ```
  It creates its own admin account and checks who is allowed to call what.

# Authentication

## How it works

1. **Registering** `POST /users` with a `display_name`, `real_name` and `password`. New accounts get the `user` role and you cant pick a different one
2. **Logging in** `POST /auth/login` with a form body: `-d 'username=...&password=...'`
    where `username` is the display name. It will return something like
   `{"access_token": "...", "token_type": "bearer", "expires_in": 1800}`. 
   1. A wrong name or a wrong password both return the same 401 and message so you cannot gain information by spamming fake logins.
      We also make sure bcrypt runs even when the account/password doesnt exist, so an unknown account is not
      responded to faster.
3. **Send back the token on every request that needs an account**
   1. `Authorization: Bearer <token>`. The token is a signed JWT (HS256 signed by `JWT_SECRET`) that lasts 30
      minutes and holds the user's **id** as 'subject'. There logout endpoint or refresh endpoint for now, just log in again when needed.
   2. The API is RESTful so you have to send the token on every request
4. **Roles** `user` applies to everyone, and `admin` should be restricted. The default admin account comes from
   the settings `.env.local` and is created every time the app starts up. 
   There is no API for making someone an admin at this time.

Passwords are stored as bcrypt hashes (`app/password_util.py`) and are never
returned by any endpoint. In this app the `cost` setting is 10 (chosen in 2026), which is low on purpose because our
app should never reach production, and it can be changed easily. 12 is the minimum recommendation for
real security.

Passwords are 6-72 characters and at most 72 **bytes** (bcrypt's limit). Longer ones are rejected with a 422, never
truncated, because truncating would make two different passwords that share their first 72 bytes verify as each other.
The schema counts characters (an early, field-level error) and `hash_password` re-checks in bytes (the unit bcrypt limits in);
the reasoning is in `app/password_util.py`. Passwords are stored exactly as typed, with no whitespace stripping.

No auth secret has a default. `JWT_SECRET` must be set, at least 32 bytes; if it is missing, empty or short the app
refuses to start with `JWT_SECRET is not set...`. The only credentials committed to the repo are the local-only dev
ones for the Postgres and RustFS containers in `compose.yml` and `store.env.example`
(`seekr-devonly`). Those services publish ports to your machine (5432 and 9000), so only run the
stack on a trusted network, and replace these credentials for any real deployment.

In `/docs`, the **Authorize** button takes the token from the login endpoint.
If it cannot log in from there, get a token with the curl above and paste it in.

## Who can call what

| Who | Endpoints |
|---|---|
| Anyone | `GET /health`, `POST /users`, `POST /auth/login`, every `GET` on items, locations, matches and item photo status |
| Any signed-in user | `POST /items`, `POST /matches`, `DELETE /matches/{id}`, `GET /auth/me`, `POST /files`, `POST /files/batch`, `GET /files` (lists only your own files) |
| The owner of the item or file, or an admin | `PATCH /items/{id}`, `PATCH /items/{id}/status`, `DELETE /items/{id}`, `POST /items/{id}/images` and `.../complete`, `GET /files/{id}`, `GET /files/{id}/content`, `DELETE /files/{id}` |
| Admins only | `POST`, `PATCH` and `DELETE` on `/locations` (including restore and hard delete), `DELETE /items/{id}/hard`, `GET /users`, and the `user_id` filter on `GET /files` |

Item posters and file owners come from the token. `POST /items` and the file
uploads no longer take a `user_id`.

Failures use the normal error envelope (see `docs/Error Contract.md`):

- **401 `UNAUTHENTICATED`**: no token, a bad or expired token, an unknown or inactive user, or a failed login.
- **403 `FORBIDDEN`**: signed in, but not allowed (not an admin, or not the owner).

A missing item is checked first, so asking for an item that doesn't exist is a
404 for everyone and a real one that isn't yours is a 403.

The old `X-Admin-Token` header and the `ADMIN_TOKEN` setting have been removed
and do nothing.

## Adding authentication to a new endpoint

Everything you need is in `app/auth.py`. Import from `auth`, never from `api`
(`api.py` imports every router, so importing it back is a circular import).

```python
# No roles needed for reading
@router.get("/things/{thing_id}")
def get_thing(thing_id: int, db: Session = Depends(get_db)): ...

# For things you need to be signed in for and you need to know ownership of entities
# Use user as paramter
@router.post("/things", status_code=201, responses=errors.errors(401, 422))
def create_thing(body: schemas.ThingCreate, user: User = Depends(current_user),
                 db: Session = Depends(get_db)):
    return crud.create_thing(db, body, owner_id=user.id)   # the owner is user.id

# For things you need to be signed in for but dont need advanced info, just use login_required
@router.post("/things/ping", dependencies=[login_required], responses=errors.errors(401))
def ping(): ...

# Admin only endpoints, depend on admin
@router.delete("/things/{thing_id}/hard", status_code=204, dependencies=[admin],
               responses=errors.errors(401, 403, 404))
def hard_delete_thing(thing_id: int, db: Session = Depends(get_db)): ...

# When you need ownership or admin role: load the row, 404 if it's missing, then check admin
@router.patch("/things/{thing_id}", responses=errors.errors(401, 403, 404))
def update_thing(thing_id: int, body: schemas.ThingUpdate,
                 user: User = Depends(current_user), db: Session = Depends(get_db)):
    thing = crud.get_thing(db, thing_id)
    if thing is None:
        raise APIError(404, errors.NOT_FOUND, "thing not found")
    require_owner_or_admin(user, thing.owner_id)
    ...
```

Rules to follow:

- **Never take the owner from the request.** No `user_id` in a request schema
  or form; use `user.id` from `current_user`. A client-supplied id lets anyone
  act as anyone.
- Add `401` (and `403` where it applies) to `responses=errors.errors(...)` so
  `/docs` shows them. Raise failures with `APIError`, not a bare `HTTPException`,
  so they use the error envelope. `current_user` and the helpers already do.
- Register the router in `app/api.py` like the others.
- **A new role:** use `require_role("moderator")` (it accepts several names; one
  match is enough), and add `get_or_create_role(db, "moderator")` to
  `crud.seed_auth` so the role exists on startup. Then decide how people get it,
  since nothing assigns roles through the API.
- A new service that checks tokens needs `JWT_SECRET` in its `compose.yml`
  entry as well; only `app` has it today.
- Add the new rules to `scripts/api_tester.py`: no token (401), the wrong user
  (403), and the right user (2xx).
- Update the **Who can call what** table above.

# Design docs
- `docs/Architecture.drawio.html` - the services, the store, and the presigned path
- `docs/Error Contract.md` - response envelope, status codes, error codes
- `docs/MESSAGE_ARCHITECTURE.md` - queues, events, and the workers that consume them
- `milestones/milestone4/STORAGE_DESIGN.md` - photo and file uploads, key scheme, content types, write order

# Contributing Code

## Pre-requisites

* Make sure you already have git ssh and authentication set up 
* You need to be in the repo as a collaborator
* Install [uv](https://docs.astral.sh/uv/) and run `uv sync` after pulling. Our Python version is 3.14.

## Instructions

1. Create a branch from main
   1. This lets you make any changes you want, without possibility of destroying main
   2. Refer to branch prefixes below. ALWAYS prefix your branch name
2. Make some changes, and commit them
   1. You should make incremental commits, so you have places to go back to if you change code
3. Feel free to push your branch at any time, but we suggest only making a pull request when it is ready or near ready.
   1. If additional changes need to be made, please mark your pull request as a DRAFT until finished.
4. Merging a pull request will always require approval from at least 1 reviewer
5. Once approved, merge the branch

### Branch Prefixes
Whenever you make a branch, use a prefix to indicate what it is for.
1. `feature/` for new features
2. `milestone<milestone_#>/` for project milestones. Like `milestone1/`
3. `fix/` for bugs and fixes
4. `docs/` for when you make only documentation changes
5. `refactor/` for when the branch is exclusively refactoring old code
6. `test/` for adding new tests
7. `chore/` for cleanup, simple config changes, etc.

### Adding dependencies
When adding new dependencies you should use `uv add <package>`
Then, you need to sync it to requirements.txt with `uv export --format requirements-txt > requirements.txt`.
The Docker image installs from requirements.txt, so a missing dependency will break the build.

# Developers

- Parker Scott 
- Devon Burton 
- Doug Varney

## Roles

Developer roles will be rotated occasionally.
The roles are: Project Lead, Backend Engineer, DevOps Engineer, Documentation Lead

Each role is NOT assigned because that person is supposed to do all that work for a given week. Everyone is always responsible for every task, and we all review each other. Instead, a role assignment just means that that individual should be “checking up on” their domain.

For week 1: These are the role assignments

- Devon
  - DevOps Engineer  
- Parker
  - Project Lead
- Doug
  - Backend Engineer
  - Documentation Lead

# Decisions
The concept we will pursue is a lost and found system for the campus community. Users will be able to upload images of items they find around campus as well as the locations they found them out and/or descriptions of lost items and last seen locations.

We decided not to pursue features that could benefit this application such as: such as AI image recognition to identify items, a live messaging system between users, or a mobile application. While all these features would make for a better user experience and would contribute greatly to the app's usability, they remain out of scope for the purposes of this project.
