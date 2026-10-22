# CI run and deployment log

## The commit

`f5cea42a4bb1b0873efe79a19a8fad3667fa4d63`, the merge of pull request #38 into `main` on 2026-10-21 20:20 -0400
(2026-10-22 00:20 UTC). The whole evaluation ran against this commit.

## The CI run

https://github.com/Snazzy11/ITC-531-Group-Project/actions/runs/39699147286

Workflow `ci`, triggered by the push to `main` at `f5cea42`, ran 2026-10-22 00:20:55 to 00:22:42 UTC. Result: success.

| Job | Result | Steps |
|---|---|---|
| [test](https://github.com/Snazzy11/ITC-531-Group-Project/actions/runs/39699147286/job/119563824519) | success, 00:20:58-00:21:21 | install pinned dependencies, Ruff lint, pytest with a coverage gate |
| [build](https://github.com/Snazzy11/ITC-531-Group-Project/actions/runs/39699147286/job/119563966445) | success, 00:21:23-00:22:41 | build the `linux/amd64` image tagged `app:f5cea42...`, start the stack with throwaway settings, run `scripts/smoke_test.sh`, tear the stack down |

**What this pipeline doesn't do: push.** `.github/workflows/ci.yml` has `push: false`. Pushing to ECR from CI needs an
OIDC role, and our free-tier AWS account could not create one (Milestone 6 `part2.md`, note 4). So the image that
runs is not one CI pushed. `adapter_deploy` builds it on the instance from the same commit CI built and tested.
We report that as a deviation from "the pipeline builds and pushes; the adapter deploys". The commit is pinned,
CI checked it, and the deploy checks out exactly that SHA. The image bytes, though, come from a second build.

## The image reference

| | |
|---|---|
| Built from | `f5cea42a4bb1b0873efe79a19a8fad3667fa4d63` (checked out detached on the instance by `adapter_deploy`) |
| Tag | `campus-seekr-app:f5cea42a4bb1b0873efe79a19a8fad3667fa4d63` |
| Image id (content-addressed) | `sha256:1d02848f04a907c2ce8d20468759a1f86a141157cef5a944fe6bdf2e4506717b` |

Compose names the images it builds `campus-seekr-<service>:latest`. `adapter_deploy` adds the commit tag and prints
the image id, and that pair is the reference we cite. Every other image in `compose.yml` is pinned by version
(`postgres:16.6-alpine3.20`, `rabbitmq:3.13.7-management-alpine`, `nginx:1.27.4-alpine`, `prom/prometheus:v3.2.1`,
`grafana/grafana:11.5.2`, `rustfs/rustfs:1.0.0`), and the base image is `python:3.14.7-slim-trixie`.

## The deployment

`adapters/aws.sh` with `DEPLOY_TARGET=ec2`, run from a laptop:

```
set -a; source adapters/aws.env; set +a; source adapters/aws.sh
adapter_deploy
```

It checks out `DEPLOY_SHA` on the instance over SSH, refusing if the checkout has local changes. Then it builds the
images, starts the stack, and tags and prints the API image. Finally it checks `/health` from the laptop, and the
URL comes last. The full output is in `adapter-deploy.txt`. The first attempt failed, and the file keeps both
attempts. This is the second, with compose's per-container progress lines (Running, Recreate, Starting) trimmed:

```
$ adapter_meta
provider:        Amazon Web Services (compute) + Cloudflare R2 (object storage)
region:          us-east-2
compute service: Amazon EC2 (one c7i-flex.large running the compose stack)
storage service: Cloudflare R2 (S3 API)
auth model:      SSH key pair for deploys; R2 API token scoped to one bucket
contract check:  2026-10-22
$ adapter_deploy
deploy f5cea42a4bb1b0873efe79a19a8fad3667fa4d63 to ubuntu@18.222.255.231:ITC-531-Group-Project at 2026-10-22 02:51:17 UTC
checked out f5cea42a4bb1b0873efe79a19a8fad3667fa4d63
 Container campus-seekr-app-1  Recreated
 Container campus-seekr-app-1  Started
 Container campus-seekr-matching_worker-1  Started
 Container campus-seekr-notifier-1  Started
 Container campus-seekr-image_worker-1  Started
 Container campus-seekr-logger-1  Started
IMAGE_REF=campus-seekr-app:f5cea42a4bb1b0873efe79a19a8fad3667fa4d63
IMAGE_ID=sha256:1d02848f04a907c2ce8d20468759a1f86a141157cef5a944fe6bdf2e4506717b
SERVICE           IMAGE                               STATUS
app               campus-seekr-app                    Up 23 seconds (healthy)
broker            rabbitmq:3.13.7-management-alpine   Up 39 minutes (healthy)
db                postgres:16.6-alpine3.20            Up 39 minutes (healthy)
gateway           nginx:1.27.4-alpine                 Up 39 minutes
grafana           grafana/grafana:11.5.2              Up 39 minutes
image_worker      campus-seekr-image_worker           Up 5 seconds
logger            campus-seekr-logger                 Up 5 seconds
matching_worker   campus-seekr-matching_worker        Up 5 seconds
notifier          campus-seekr-notifier               Up 5 seconds
prometheus        prom/prometheus:v3.2.1              Up 39 minutes
storage           rustfs/rustfs:1.0.0                 Up 39 minutes (healthy)
{"status":"ok","checks":{"database":"ok"}}
http://18.222.255.231:8000
```

The service URL is `http://18.222.255.231:8000`. The API is under `/api/v1`, and the docs are at `/docs`.

**Before this deploy.** The instance was set up by hand on 2026-10-22 between 02:06 and 02:15 UTC: the repository
cloned (its `main` was at the same commit), `.env.local` written, and the stack built and started with Docker
Compose. Postgres initialised its
empty volume at 02:12:22 UTC (`01-relational-postgres.txt`, part A). At 02:40 UTC the R2 settings in `.env.local`
were corrected and the API and image worker recreated (README, "Failure modes"). `adapter_deploy` then
redeployed the same commit at 02:51 UTC, and every transcript is from after that.
