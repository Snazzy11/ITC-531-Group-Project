# ITC-531-Group-Project

A campus lost-and-found API: post lost or found items with a photo, and match
lost posts with found ones.

# Running it

You need Docker with Compose. Then:

```sh
git clone https://github.com/Snazzy11/ITC-531-Group-Project
cd ITC-531-Group-Project
cp .env.local.example .env.local   # choose a BROKER_USER and BROKER_PASSWORD
cp store.env.example store.env     # the defaults work locally
docker compose --env-file .env.local up -d --build --wait
curl http://localhost:8000/api/v1/health   # {"status":"ok"}
```

Stop it with `docker compose --env-file .env.local down`. Adding `--volumes`
also wipes the database, queue, and stored photos. There are no migrations, so
do that whenever a pull changes `app/database/models.py`.

| URL | What |
|---|---|
| http://localhost:8000/docs | Every endpoint, with request and response shapes |
| http://localhost:8000/api/v1 | The API |
| http://localhost:15672 | RabbitMQ dashboard (log in with your broker user) |
| http://localhost:9000 | Local S3 API (RustFS), where photos are stored |

## First requests

There is no login yet; that comes in a later module. Until then, admin routes
(managing locations, hard deletes) take the header
`X-Admin-Token: dev-admin-token`, and an item says who posted it with
`user_id`.

```sh
API=http://localhost:8000/api/v1
curl -X POST $API/locations -H 'X-Admin-Token: dev-admin-token' -H 'Content-Type: application/json' \
  -d '{"name":"Library","coordinates":"40.19,-84.24"}'
curl -X POST $API/users -H 'Content-Type: application/json' \
  -d '{"display_name":"tester1","real_name":"Test User","password":"secret123","is_admin":false}'
curl -X POST $API/items -H 'Content-Type: application/json' \
  -d '{"name":"Blue umbrella","type":1,"location_id":1,"user_id":1}'   # type: 0 = lost, 1 = found
```

To add a photo or upload a file, see `milestones/milestone4/README.md`, which
has a runnable command for every endpoint.

## Tests

With the stack running:

- `scripts/api_tests.sh` is a curl walkthrough of the main flows.
- `scripts/api_tester.py` checks every rule in the error contract. It wipes the
  database first.
  ```sh
  PYTHONPATH=app DATABASE_URL=postgresql+psycopg2://seekr:seekr-devonly@localhost:5432/seekr uv run --with httpx2 python scripts/api_tester.py
  ```

# Design docs
- `milestones/milestone4/architecture-diagram.png` — the services, the store, and the presigned path
- `docs/Error Contract.md` — response envelope, status codes, error codes
- `docs/MESSAGE_ARCHITECTURE.md` — queues, events, and the workers that consume them
- `milestones/milestone4/STORAGE_DESIGN.md` — photo and file uploads, key scheme, content types, write order

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
