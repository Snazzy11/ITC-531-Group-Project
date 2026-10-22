# CI and deployment

**CI run:** https://github.com/Snazzy11/ITC-531-Group-Project/actions/runs/39699147286. A push to `main` at
`f5cea42`, run on 2026-10-22 00:20-00:22 UTC. Both jobs passed: `test` (lint and pytest) and `build` (image build
and smoke test). CI doesn't push the image, because the free-tier account couldn't set up OIDC (Milestone 6,
`part2.md`). Instead, `adapter_deploy` builds the same commit on the instance.

**Image reference:** `campus-seekr-app:f5cea42a4bb1b0873efe79a19a8fad3667fa4d63`, image ID
`sha256:1d02848f04a907c2ce8d20468759a1f86a141157cef5a944fe6bdf2e4506717b`.

**`adapter_deploy` output** (`adapters/aws.sh`, `DEPLOY_TARGET=ec2`). Compose's progress lines are trimmed:

```
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
