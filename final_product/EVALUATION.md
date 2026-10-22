# Evaluation

Build: commit `f5cea42`, deployed 2026-10-22 02:51 UTC to EC2 `i-06fc8267b6b2af6b2` (c7i-flex.large, us-east-2)
with Cloudflare R2.

## (a) Criteria

Recorded 2026-10-22 03:01 UTC, before any measurement.

| # | Criterion | Threshold | Source |
|---|---|---|---|
| C1 | p95, slowest user-visible endpoint | <= 1,000 ms | Milestone 3 API latency budget |
| C2 | p95, `GET /items` | <= 200 ms | Milestone 3 gateway latency budget |
| C3 | 5xx rate | <= 1% | Milestone 6 error-rate threshold |
| C4 | Photo processed after `/complete` | <= 60 s | Milestone 3 image worker estimate |
| C5 | Cost | <= $5/month | Milestone 3 reversal criterion |

- **C3, met:** 0 5xx in 3,347 requests, 02:51-03:09 UTC. Method: summed `seekr_requests_total` from `/metrics/`.
- **C4, met:** a single photo was `ready` 0.45 s after its 202 (trace transcript). In a burst of 100 uploads in
  10.5 s, the last one was `ready` 47.4 s after its upload link was issued. Method: `processed_at - created_at` on
  the `images` row.

## (b) Latency distribution

TODO(team): teammate's results, for the three most important endpoints.

| Endpoint | Tool | Requests | Concurrency | p50 | p95 | p99 | Meets C1/C2? |
|---|---|---|---|---|---|---|---|
| | | | | | | | |

Client location and date: TODO(team).

## (c) Cold start: ruled out

The compute shape is one EC2 instance running long-lived containers. Nothing scales to zero, and the API process
that served every transcript started once

## (d) Cost per 1,000 requests

Usage, read on 2026-10-22: the instance ran from 02:06 UTC to teardown. The API answered 3,347 requests. The
instance sent 41.1 MB (`tx_bytes`). R2 held 330,783 bytes in 6 objects.

| Line item | This deployment | Cost                                |
|---|---|-------------------------------------|
| Per-request charge | EC2 has none; R2 per-operation charges | None accrued for this project       |
| Compute duration | None billed separately; all compute is the instance (next line) | $0                                  |
| Idle/reserved capacity | c7i-flex.large, billed per second while running | No charges accrued for this project |
| HTTP front door | nginx on the instance, so no load balancer or API Gateway | $0                                  |
| Egress | 41.1 MB out of EC2 | No charges accrued for this project)                          |
| Log ingestion/retention | No CloudWatch; Docker logs on the instance disk | $0                                  |
| Storage at rest | 14 GB EBS volume + 330 KB in R2 | No charges accrued for this project                         |

Our actual cost was $0 with the free tier

## (e) Local vs. deployed

| Service | What changed | Cause, and how we established it |
|---|---|---|
| Object storage | Local RustFS over HTTP became R2 over HTTPS across the internet. The first config also wrote objects to the wrong keys | `S3_ENDPOINT_URL` had a bucket path, which boto3 keeps. An offline boto3 run printed the wrong URL, and the bucket still has the stray empty object `project-bucket` |
| Relational | Nothing in the path: Postgres sits next to the API in both runs, but here it shares 2 vCPU | Same `compose.yml`; `nproc` on the instance |
| Messaging | The first `adapter_deploy` failed (`has no healthcheck configured`) | The instance's Compose 2.40.3 rejects `--wait` for the workers; `evidence/ci-and-deploy.md` |
| Metrics | Prometheus and Grafana are reachable from the internet | `compose.yml` publishes their ports on every interface; we fetched them from outside AWS |

## (f) What we would do differently

1. **Add a second image worker and export queue depth.** The last photo of a 100-photo burst took 47.4 s against
   our 60 s limit (C4). The queue drained at only about 1.6 jobs/s.
2. **Fail startup on a bad object-store config.** The broken endpoint passed startup and `/health`, and wrote
   objects to the wrong keys. That should be zero. Startup should presign and HEAD a test object, the way it
   already refuses a missing `JWT_SECRET`.
