# Evaluation

Everything here was measured against commit `f5cea42a4bb1b0873efe79a19a8fad3667fa4d63`, deployed by
`adapter_deploy` on 2026-10-22 at 02:51 UTC to EC2 instance `i-06fc8267b6b2af6b2` (c7i-flex.large, us-east-2),
with Cloudflare R2 for objects. Each number says how it was produced, over how many samples, and when. Items
marked `TODO(team)` still need a figure that only a teammate or the provider console can supply.

## (a) Criteria, stated first

Written down at 2026-10-22 03:01:01 UTC, before any load was put on the deployment. Wherever we had an earlier
number, the threshold comes from it.

| # | Criterion | Threshold | Source |
|---|---|---|---|
| C1 | p95 of the slowest user-visible endpoint (login, posting an item, finishing a photo upload), client outside AWS | <= 1,000 ms | Milestone 3 workload profile, API "Latency budget: 1s" |
| C2 | p95 of browsing, `GET /items` | <= 200 ms | Milestone 3 workload profile, gateway "Latency budget: 200 ms"; browsing is the scrolling case in its method note 7 |
| C3 | Server errors (5xx) | <= 1% of requests | Milestone 6 `OBSERVABILITY.md` 3b: an error rate over 1-5% must be investigated; we hold the strict end |
| C4 | Throughput | >= 10 requests/s sustained at concurrency 10, with C3 met | Milestone 3: 19,200 requests/month is about 0.007 requests/s on average; 10/s leaves three orders of magnitude for a school-hours peak |
| C5 | A photo is processed after `/complete` returns | <= 60 s | Milestone 3 workload profile, image worker: "under a minute for each image" |
| C6 | Running cost | <= $5 per month | Milestone 3 reversal criterion, restated in Milestone 6 `part4.md` 4c |

Results that don't depend on (b):

- **C3, met.** 0 server errors in 3,347 requests: every request the API answered between the deploy (02:51 UTC)
  and 03:09 UTC. That covers all six transcripts and one load run from 03:01:52 to 03:02:35 UTC. Method: the sum
  of `seekr_requests_total` over all series, and the sum over `status=~"5.."`, read from `/metrics/` at
  03:09:39 UTC. 369 of the 3,347 are the container healthcheck and Prometheus scrapes.
- **C5, met, by 12.6 s at worst.** One photo with nothing else queued: `ready` 0.45 s after its 202
  (`06-end-to-end-trace.txt`). A burst of 100 `/complete` calls in 10.5 s (the 03:02:24 load run, concurrency 5):
  53 jobs were still queued or in progress when the run ended. The last photo to finish was `ready` 47.4 s after
  its upload link was issued. Method:
  `processed_at - created_at` on the `images` row, which also counts the client's PUT to R2, so it overstates the
  time after `/complete`. Only the last row survives, because each new ready photo for an item replaces the
  previous one. The queue drained at about 1.6 jobs/s: 27 ready at 03:03:08, 0 at 03:03:25, read with
  `rabbitmqctl list_queues` every 5 s.

## (b) Latency distribution

TODO(team): a teammate is running this measurement. For each of the three most important endpoints, record:

- the tool and its exact command
- the concurrency and the request count
- the build: commit `f5cea42`, the deployment above
- the date and time (UTC)
- where the client was, and whether it was on the same continent as us-east-2

Report p50, p95 and p99 (not a mean), and say whether C1 and C2 were met and by how much. If the same run gives
an error count and a request rate, those are C3 and C4. What this kind of measurement can't separate:

- network distance from server time (a run from inside the instance, against `http://127.0.0.1:8000`, gives the
  server-side part)
- one client's path from other users' paths

`scripts/latency_test.py` is one way to run it (standard library, one kept-alive connection per thread).

| Endpoint | Requests | Concurrency | p50 | p95 | p99 | Threshold | Met? |
|---|---|---|---|---|---|---|---|
| TODO(team) | | | | | | | |
| TODO(team) | | | | | | | |
| TODO(team) | | | | | | | |

## (c) Cold start: ruled out

The compute shape is one long-running EC2 instance. On it, Docker Compose runs the API, the gateway and the workers
as long-lived containers. Nothing scales to zero, and no request is ever served by a process started for it. The
API process that served every transcript was started once, by the deploy at 02:51 UTC, and its counters ran
without a reset until 03:09 (`metrics-scrape.txt` shows one `seekr_requests_created` time per series).

Citation: TODO(team). Cite the AWS page saying an instance stays running until it is stopped or terminated, read it,
and add it to `sources.md` with the date and the reader. The EC2 instance lifecycle page in the user guide
(https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-instance-lifecycle.html) is the likely one. Also check the
c7i-flex family's own page for any CPU baseline or burst behaviour, which would slow a first burst without being a
cold start.

What restarts do cost us: every `adapter_deploy` recreates the API container, which loses its counters and its
connection pools. The deploy log shows the API `healthy` within 23 s of being recreated. We did not time how long
requests failed during that window.

## (d) Cost per thousand requests

### Actual usage this deployment produced

| Quantity | Value | How it was read |
|---|---|---|
| Instance running time | from 02:06:46 UTC (boot) to TODO(team) teardown time | `uptime -s` on the instance; the end is the `terminated` time in `teardown/cloud-down.txt` |
| Requests answered by the API | 3,347 between 02:51 and 03:09 UTC, 369 of them internal | `seekr_requests_total` |
| Bytes sent by the instance | 41,096,906 since boot (API responses, photo writes to R2, SSH) | `tx_bytes` on `enp39s0` at 03:09:39 UTC |
| Bytes received | 916,783,945 since boot, mostly image pulls and builds | `rx_bytes`, same read |
| Photos processed | 105 stored, 2 rejected (since 02:51) | image worker log |
| R2 at rest | 6 objects, 330,783 bytes | the app's `storage.list_objects()`, 03:09 UTC |
| R2 operations | TODO(team) | Cloudflare dashboard, R2, the bucket's metrics: Class A and Class B operation counts for 2026-10-22 |
| EBS | one 14 GB root volume (TODO(team): its type, from the console) | `lsblk`; the database, broker, images and 7.2 MB of container logs are all on it |

### The seven line items

All prices are TODO(team). Fill each one from the provider's pricing page for us-east-2 (AWS) or R2 (Cloudflare),
and add the page to `sources.md` with the date read. The arithmetic is per 1,000 requests answered:
`line cost for the run / requests in the run x 1,000`.

| Line item | What it is in this deployment | Usage | Price | Cost for the run | Per 1,000 requests |
|---|---|---|---|---|---|
| Per-request charge | EC2 and nginx have none. R2 charges per operation (Class A: PUT, LIST; Class B: GET, HEAD) | R2 ops: TODO(team) | TODO(team) | TODO(team) | TODO(team) |
| Compute duration | Nothing is billed per invocation; all compute is the instance, so it is under the next line | 0 | n/a | $0 | $0 |
| Idle or reserved capacity | The c7i-flex.large is billed for every second it runs, busy or idle. This is the main line | instance hours: TODO(team) | TODO(team) per hour | TODO(team) | TODO(team) |
| HTTP front door | nginx on the instance; no load balancer or API Gateway. AWS charges for the public IPv4 address by the hour (TODO(team): confirm on the VPC pricing page) | IPv4 hours = instance hours | TODO(team) | TODO(team) | TODO(team) |
| Egress | Data out from EC2 to the internet: at most the 41.1 MB above, including the photo writes to R2. R2's own egress: TODO(team), from R2's pricing page | 0.0411 GB | TODO(team) | TODO(team) | TODO(team) |
| Log ingestion and retention | No CloudWatch. Logs are Docker's json-file logs on the instance's disk (7.2 MB), deleted with it | 0 | n/a | $0 | $0 |
| Storage at rest | The 14 GB EBS volume for the hours it existed, plus 330,783 bytes in R2 | TODO(team) | TODO(team) | TODO(team) | TODO(team) |

### Prediction against the console

TODO(team): Milestone 3's model is a fixed server ($44/month for an 8 GB Lightsail-class server, `COST_MODEL.md`)
plus per-photo object, transfer and log charges. Feed it this run's usage: the instance hours, 105 photos, and the
transfer above. Then compare it with Billing and Cost Management for 2026-10-22, filtered to EC2, EBS and VPC
(public IPv4), and with Cloudflare's R2 usage for the same day. Explain the gap. Three likely parts:

- we ran a c7i-flex.large on EC2, not the server the model priced
- the account's credits: Milestone 6 read $0.00 charged with the $120 of credits untouched, so check whether the
  console shows the charge before or after credits
- R2 replaced S3 in the object lines

Write down the model's number before reading the console, and keep it even if it was wrong. Then judge C6:
convert the hourly figures to a month of continuous running.

## (e) Local run versus deployed run

The same `compose.yml` and image ran on a laptop and on the instance. The differences, service by service:

| Service | What changed | Cause | How we established it |
|---|---|---|---|
| Object storage | The first deployed config sent every object to the wrong place. The bucket still holds an empty object called `project-bucket`. The first upload link (upload `6584ff46-...` for item 11, still `awaiting_upload`) pointed at the bucket's public `r2.dev` address instead of the S3 API | `.env.local` had the bucket's name at the end of `S3_ENDPOINT_URL` and a different name in `S3_BUCKET`, with `S3_PUBLIC_ENDPOINT_URL` set to the `r2.dev` address. boto3 keeps a path that is part of `endpoint_url`, so every call went to bucket `deployed-project-bucket` with keys prefixed `project-bucket/`. The startup "create bucket" call (`ensure_bucket`) then becomes a PUT of an empty object with that name | boto3 run offline with the same settings printed `https://<acct>.r2.cloudflarestorage.com/deployed-project-bucket/project-bucket/<key>`. The empty object is in the bucket listing (`02-object-storage-r2.txt`, part C). The PUT to the `r2.dev` link was blocked by our client's own firewall before it reached Cloudflare, so we fixed the settings (02:40 UTC) without seeing how R2 would have answered. Every upload after the fix worked |
| Object storage | Each call to the store now crosses the internet over HTTPS, instead of plain HTTP to the RustFS container on the same Docker network. A 144,564-byte PUT from the client to R2 took 0.27-0.34 s | R2 is reached at a public HTTPS endpoint from us-east-2, and locally the store is one hop away. TODO(team): time the API's own `HEAD` to R2 against the same call to the local RustFS still running on the instance, to put a number on the server side | `time_total` on the PUTs in `02-object-storage-r2.txt` and `06-end-to-end-trace.txt` |
| Relational | Nothing in the path: Postgres runs next to the API on both machines. What changed is the neighbours. On the instance it shares 2 vCPU with bcrypt (cost 10) and the image worker's re-encodes | The instance size. TODO(team): check (b)'s login and post figures against a run on the instance itself | `docker stats` and `nproc` on the instance |
| Messaging | The first `adapter_deploy` failed: `container campus-seekr-image_worker-1 has no healthcheck configured` | Ubuntu's Docker Compose 2.40.3 on the instance rejects `up --wait` for containers whose healthcheck is disabled. CI's Compose did too; the README's troubleshooting section already had it for CI | `evidence/adapter-deploy.txt`, attempt 1. The adapter now waits only for services with healthchecks and checks that no worker exited |
| Messaging | Photo jobs queue up under a burst: one image worker drained about 1.6 jobs/s | One worker on 2 vCPU. Re-encoding is CPU work | Queue depth over time, (a) C5 |
| Metrics | Prometheus (9090) and Grafana (3000) can be reached from the internet, and Prometheus asks for no login | `compose.yml` publishes both ports on every interface, which on a laptop means the laptop. On the instance it means its public address, wherever the security group allows the port | `prometheus-targets.txt` was fetched from outside AWS. Grafana answered `401` without a login (`04-metrics-prometheus.txt`) |
| Metrics | Counters restart from zero on each deploy | `adapter_deploy` recreates the API container, and the counters live in its process | `seekr_requests_created` times in `metrics-scrape.txt` all fall after 02:51 UTC |
| Front door | Plain HTTP on a public IP. Logins and bearer tokens cross the internet unencrypted | No TLS terminator in front of nginx. Locally that is `localhost` | Port 443 refused connections at 02:30 UTC; the service URL is `http://` |

## (f) What we would do differently

1. **A second image worker, and queue depth as a metric.** With one worker, a burst of 100 photos left the last
   one `ready` 47.4 s after its upload link, against our 60 s ceiling (C5). The queue drained at about 1.6
   jobs/s. We would run two `image_worker` replicas, which share the queue because prefetch is 1. We would also
   export the depth of `jobs.image_processor` as a metric and alert when it passes 50, the depth this burst
   reached.
2. **Check the object store at startup the way the API checks `JWT_SECRET`.** The misconfigured endpoint passed
   the startup check: `ensure_bucket` "created" the bucket by writing an empty object, and `/health` stayed `ok`.
   We found it only by reading the upload URL. Under that config, every object the API wrote went under the wrong
   key, and the only acceptable number of those is zero. We would make startup fail unless `S3_ENDPOINT_URL` has no
   path and a presigned PUT and HEAD of a test key succeed.
3. TODO(team), from (b): tie a third change to the latency numbers. For example, if `POST /items` p95 is far above
   `GET /items`, the cause to test first is in `app/messaging.py`: each publish opens and closes its own AMQP
   connection, and posting an item publishes twice. The action would be one long-lived channel per API process.
   If login p95 misses C1, the cause is bcrypt on 2 vCPU, and the action is a larger instance or a separate auth
   worker.
