# Campus Seekr: final product

A lost-and-found API that uses PostgreSQL, RabbitMQ, Cloudflare R2 (S3 API) and Prometheus/Grafana on one request
path. It was deployed to AWS EC2 (us-east-2) on 2026-10-22, measured, and torn down.

- Repository: https://github.com/Snazzy11/ITC-531-Group-Project
- Deployed commit: `f5cea42a4bb1b0873efe79a19a8fad3667fa4d63`
- Team: Parker Scott, Devon Burton, Doug Varney

## Contents

- `ARCHITECTURE.md`: the diagram, the four services, and the traced request (1g)
- `evidence/transcripts/`:
  - `01-relational-postgres.txt`: schema and constraints, CRUD
  - `02-object-storage-r2.txt`: presigned upload and download, `/files`
  - `03-messaging-rabbitmq.txt`: 202 workflow, consumer stopped and killed
  - `04-metrics-prometheus.txt`: route labels, domain metrics
  - `05-auth.txt`: 401, 403 and 200 on `GET /users`
  - `06-end-to-end-trace.txt`: the traced request
- `evidence/metrics-scrape.txt`, `evidence/dashboard-panel.png`: the deployed scrape and one panel
- `evidence/ci-and-deploy.md`: CI run, image reference, `adapter_deploy` output
- `evidence/walkthrough.md`: the recording and its index
- `EVALUATION.md`: deliverable 3
- `teardown/`: audits, teardown, residual risk
- `adapters/aws.env.example`, `sources.md`

Tokens, passwords and presigned signatures in the transcripts are `<redacted>`. Matches have no PATCH by design:
the update is DELETE then POST (`01`, part E). `PATCH /users/{id}` was added to cover the update requirement
(part F).

## Who wrote which part

TODO(team)
