# ITC-531-Group-Project

# Technologies used

- Python package management will be done with uv
  - Make sure you run uv init and uv sync upon pulling the repo
  - Refer to section below about adding dependencies
- Refer to the requirements.txt and pyproject.toml for requirements
  - As of now these are able to fall out of sync. Will add github actions to ensure sync in the future
- Our Python version is 3.14

# Usage guide
- Use this link to see all available APIs and their shapes
  - `http://localhost:8000/docs`

# Design docs
- `docs/Error Contract.md` — response envelope, status codes, error codes
- `docs/MESSAGE_ARCHITECTURE.md` — queues, events, and the workers that consume them
- `docs/STORAGE_DESIGN.md` — object storage key scheme, content-type handling, bucket layout

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


# Setup
1. Clone the repository:
```git clone https://github.com/Snazzy11/ITC-531-Group-Project```
2. Create a `.env.local` file in the base project directory, then copy
`.env.local.example` to `.env.local`. Set `RABBITMQ_TAG` to
`3.13.7-management-alpine` and choose a `BROKER_USER` and `BROKER_PASSWORD`.
3. Copy `store.env.example` to `store.env`. The defaults point at the local
RustFS S3 server (`storage` in `compose.yml`); the file's comments say what to
change for real AWS S3.
4. Build and run the container:
```docker compose --env-file .env.local up -d --build --wait```
5. Teardown:
```docker compose --env-file .env.local down --volumes```

## Testing the Service
Start the app and check that it responds:
```sh
curl http://localhost:8000/api/v1/health
```

Open http://localhost:15672 to view RabbitMQ. Log in with the values you chose.
The matching and notification workers only log messages for now. The image
worker processes photo uploads; `docs/STORAGE_DESIGN.md` walks through the
upload flow. The local S3 API (RustFS) is at http://localhost:9000.

# Contributing Code

## Pre-requisites

* Make sure you already have git ssh and authentication set up 
* You need to be in the repo as a collaborator

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
Then, you need to sync it to requirements.txt with `uv export --format requirements-txt > requirements.txt`

# Decisions
The concept we will pursue is a lost and found system for the campus community. Users will be able to upload images of items they find around campus as well as the locations they found them out and/or descriptions of lost items and last seen locations.

We decided not to pursue features that could benefit this application such as: such as AI image recognition to identify items, a live messaging system between users, or a mobile application. While all these features would make for a better user experience and would contribute greatly to the app's usability, they remain out of scope for the purposes of this project. 