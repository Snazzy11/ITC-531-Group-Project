# Campus Seekr: final product evidence

Campus Seekr is a lost-and-found API for a campus. It uses four cloud services on one request path:
PostgreSQL, RabbitMQ, an S3-API object store (Cloudflare R2) and Prometheus with Grafana. It was deployed to one
AWS EC2 instance in us-east-2 on 2026-10-22, measured, and then torn down. This ZIP is the evidence. The source
stays in the repository.

| | |
|---|---|
| Repository | https://github.com/Snazzy11/ITC-531-Group-Project |
| Deployed commit | `f5cea42a4bb1b0873efe79a19a8fad3667fa4d63` (main, the merge of PR #38) |
| Team | Parker Scott, Devon Burton, Doug Varney |
| Deployed URL while it ran | `http://18.222.255.231:8000` (API under `/api/v1`, docs at `/docs`) |

## What is here

| Path | Deliverable | What it holds |
|---|---|---|
| `ARCHITECTURE.md` | 1, 1g | The diagram, the four services, design decisions, and one request traced through all four |
| `evidence/transcripts/01-relational-postgres.txt` | 1a, 1b, 2b | The schema built from an empty volume; Postgres itself refusing a bad foreign key, a RESTRICT delete and both check constraints; full CRUD on locations and items; matches, where the update is DELETE then POST; the users update. Failures with 401, 403, 404, 409 and 422 |
| `evidence/transcripts/02-object-storage-r2.txt` | 1c, 2b | Photo upload and download by presigned URL, straight to R2; a tampered signature (403 from R2); a rejected upload; `/files` upload, list, download and delete; 400, 401, 403, 404, 409 and 413; the metadata rows matched against the bucket listing |
| `evidence/transcripts/03-messaging-rabbitmq.txt` | 1d, 2b | The 202 workflow. The consumer stopped, a job published, the depth read (1), the consumer started, the depth read again (0). The consumer then killed with SIGKILL in the middle of a job, which RabbitMQ redelivered to the next one. The matching workflow, and 403, 404 and 409 |
| `evidence/transcripts/04-metrics-prometheus.txt` | 1e, 2b | Route-template labels (`/files/{file_id}` stays one series), unmatched paths in one series, the domain counters, Prometheus answering and refusing a bad query |
| `evidence/transcripts/05-auth.txt` | 1f, 2b | 401, 403 and 200 on `GET /users`; refused `alg=none` and wrong-key tokens; bcrypt hashes; roles assigned by script |
| `evidence/transcripts/06-end-to-end-trace.txt` | 1g | The raw commands and output behind the trace in `ARCHITECTURE.md` |
| `evidence/metrics-scrape.txt`, `evidence/prometheus-targets.txt` | 2c | The raw `/metrics/` output from the deployed API, and Prometheus showing the target `up` |
| `evidence/dashboard-panel.png` | 2c | One Grafana panel with this run's traffic and the time range visible |
| `evidence/ci-and-deploy.md`, `evidence/adapter-deploy.txt` | 2d | The CI run, the image reference, and `adapter_deploy`'s output ending in the URL |
| `evidence/walkthrough.md` | 2a | The recording's link and a timestamped index |
| `EVALUATION.md` | 3 | Criteria first, then the measurements against them |
| `teardown/` | 4 | The audit before, the teardown transcript, the clean audit, and the residual-risk statement |
| `adapters/aws.env.example` | 5c | Every value the adapter reads, each replaced by a description |
| `sources.md` | | Every URL cited, with the date read and who read it |

## Reading the transcripts

- **Times** are UTC. Each request has the time it was sent, the `curl` command that reproduces it, and the
  status, timing, headers and body that came back.
- **Redactions:** bearer tokens, passwords, and presigned URLs' `X-Amz-Credential` and `X-Amz-Signature` are
  replaced with `<redacted>`. The client's public IP in the nginx log is `<client-ip>`. Nothing else was edited.
- **Who sent them:** a laptop outside AWS. `ubuntu@ec2$` lines ran on the instance over SSH.
- **Accounts:** `eval-owner` and `eval-other` are ordinary users. `eval-admin` was given the admin role with the
  repository's `manage` script. All three were registered through the API for this evaluation. The demo users and
  items (`app/demo_data.py`) were loaded when the database was created.

## Who did what

TODO(team): who built and wrote each part (the deployment, the adapter, the transcripts, the evaluation, the
teardown, the recording).

## Deviations we report rather than hide

- **CI builds and tests the image but doesn't push it.** The free-tier account couldn't set up OIDC for CI.
  `adapter_deploy` builds the same commit on the instance. See `evidence/ci-and-deploy.md`.
- **No TLS.** The deployed API was plain HTTP on a public IP (`EVALUATION.md` (e)).
- **Matches have no PATCH by design.** A changed pairing is DELETE then POST, shown in
  `01-relational-postgres.txt` part E. `PATCH /users/{id}` was added as the update for this deliverable (part F).
