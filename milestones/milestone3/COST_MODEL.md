# Part 3: Cost model

Using function for photo processing and on-demand containers for matching and notifications. Keeping photo processing on the shared server is still the cheapest option in this model. Moving it to a function adds a small charge but does not remove the server we still need for the API, database, and broker. A function is more useful if photo processing would otherwise need its own server.

## Workload

Part 1 estimates 19,200 API requests and 4,800 photo jobs per month. The photo estimate comes from a potential campus population of 16,000 and the guess that 30% will post an item with a photo each month.

We assume four months of hosting.

API requests over the term = 19,200 x 4 = 76,800
Photo jobs over the term   = 4,800 x 4 = 19,200
100x photo volume         = 19,200 x 100 = 1,920,000

The greeting tests in Part 1 measured a warm mean of 0.329 ms for the function and 0.492 ms for the server.

- Average billed time per photo attempt: 2 seconds. 0.2-10 seconds once processing exists.
- Function memory: 512 MB.
- Attempts per photo: normally test 1-2, with 5 as a retry-heavy case.
- Original photo / thumbnail: 2 MiB / 0.2 MiB.
- Thumbnail views per photo: 5.
- Application logs / worker logs: 16 KiB per photo / 4 KiB per attempt.
- Function response: 1 KiB per attempt.
- Matching / notifier: One run each per photo, using 0.25 vCPU and 0.5 GB per container.
- Container billed time: 60 seconds per run, including image download and startup.
- Notification data out: 1 KiB per photo.
- Container image storage: 0.5 GB total.
- Retention: Photos until teardown

Uploads are spread evenly across four months, starting with an empty store. Each photo is stored for two months on average. Retried processing overwrites the same thumbnail. We do a full month of log storage per entry

## Options compared

All three options keep the API, gateway, database, broker, and logger on an 8 GB server. Matching and notifications use on-demand containers in every option

1. Shared server: photo processing also runs on the shared server.
2. Function worker: photo processing runs as an on-demand function.
3. Separate worker server: the shared server stays running and a second, 1 GB server handles photos.

For the function option, a small consumer on the shared server would read RabbitMQ jobs, invoke the function, check the result, and acknowledge successful work. The function would read and write objects without opening a database connection.

A dispatcher on the shared server would also start matching and notifier tasks when jobs arrive.

## Prices

These are AWS reference prices for US East (N. Virginia), us-east-1.

- Shared Linux server, public IPv4, 8 GB RAM, 160 GB disk, 5 TB transfer: $44/month.
- Separate Linux worker, public IPv4, 1 GB RAM, 40 GB disk, 2 TB transfer: $7/month.
- Function invocations: $0.20 per 1 million requests
- Function execution, x86, first tier: $0.0000166667 per GB-second
- Object PUT requests: $0.000005 per request
- Object GET requests: $0.0000004 per request
- Standard object storage, first tier: $0.023 per GB-month
- Internet data out, first paid tier: $0.09 per GB.
- Standard log ingestion: $0.50 per GB.
- Log storage: $0.03 per GB-month

## What each bill includes

- Per-request charges: Shared or separate server: Object reads and writes, zero extra per API or broker request. Function worker: Same, plus function invocations.
- Compute duration: All options: Matching and notifier container CPU and memory x billed seconds x rates. Function worker: Also function memory x billed seconds x rate.
- Idle capacity: Shared or separate server: $44/month shared, or $51/month with a separate worker. Function worker: $44/month for shared services. Zero idle function or on-demand container compute charge.
- HTTP front door: Shared or separate server: Zero extra. nginx uses the existing server. Function worker: Zero extra, same nginx, and the worker uses direct invocation.
- Data out / networking: All options: Thumbnail downloads, notification traffic, and task public IPv4 addresses. Other server traffic assumed within its bundle. Function worker: Same, plus a conservative charge for the 1 KiB function response.
- Log ingestion and retention: Shared or separate server: Application and worker logs, retained for 30 days. Function worker: Same.
- Storage at rest: All options: Object storage for photos and ECR storage for container images. Database and broker disk included in the server. No extra scratch-storage charge within the included 20 GB per Fargate task or 512 MB per function.

## Arithmetic and totals

R is photo jobs over the term and A is attempts per job. The starting case uses R = 19,200 and A = 1.

PUTs = R + A x R
GETs = A x R + 5 x R
Object requests = PUTs x 0.000005 + GETs x 0.0000004

Photo storage = R x (2.2 / 1024) x 2 x 0.023
Photo data out = R x (5 x 0.2 / 1024) x 0.09
Logs = R x (16 + 4 x A) / 1048576 x (0.50 + 0.03)

Function requests = A x R x 0.0000002
Function compute = A x R x 0.5 x 2 x 0.0000166667
Function response data = A x R / 1048576 x 0.09
Shared server = 4 x 44 = 176
Separate worker = 4 x 7 = 28 additional

Container runs = 2 x R
Container compute = 2 x R x 60 x (0.25 x 0.000011244 + 0.5 x 0.000001235)
Task public IPv4 = 2 x R x (60 / 3600) x 0.005
Notification data out = R / 1048576 x 0.09
Container image storage = 0.5 x 4 x 0.10 = 0.20

### Four-month cost at 19,200 jobs

Shared server:

- Per-request charges: $0.238080
- Compute duration: $7.899264
- Fixed / idle capacity: $176
- HTTP front door: $0
- Data out / networking: $4.889148
- Log ingestion and retention: $0.194092
- Storage at rest: $2.097500
- Total: $191.32

Function worker (Part 2 selection):

- Per-request charges: $0.241920
- Compute duration: $8.219265
- Fixed / idle capacity: $176
- HTTP front door: $0
- Data out / networking: $4.890796
- Log ingestion and retention: $0.194092
- Storage at rest: $2.097500
- Total: $191.64

Separate worker server:

- Per-request charges: $0.238080
- Compute duration: $7.899264
- Fixed / idle capacity: $204
- HTTP front door: $0
- Data out / networking: $4.889148
- Log ingestion and retention: $0.194092
- Storage at rest: $2.097500
- Total: $219.32

### Four-month cost at 1,920,000 jobs (100x)

Shared server:

- Per-request charges: $23.808000
- Compute duration: $789.926400
- Fixed / idle capacity: $176
- HTTP front door: $0
- Data out / networking: $488.914795
- Log ingestion and retention: $19.409180
- Storage at rest: $189.950000
- Total: $1,688.01

Function worker (Part 2 selection):

- Per-request charges: $24.192000
- Compute duration: $821.926464
- Fixed / idle capacity: $176
- HTTP front door: $0
- Data out / networking: $489.079590
- Log ingestion and retention: $19.409180
- Storage at rest: $189.950000
- Total: $1,720.56

Separate worker server

- Per-request charges: $23.808000
- Compute duration: $789.926400
- Fixed / idle capacity: $204
- HTTP front door: $0
- Data out / networking: $488.914795
- Log ingestion and retention: $19.409180
- Storage at rest: $189.950000
- Total: $1,716.01


## Break-even

With the same four-month period and one attempt per job, matching, notifications, and image storage cost the same in all three options, so they do not change the crossing point:

function_total = aR + b = 0.000804352726R + 176.20
shared_total   = cR + F = 0.000787400195R + 176.20
separate_total = cR + F = 0.000787400195R + 204.20

R* = (F - b) / (a - c)

Shared server:
R* = (176.20 - 176.20) / (0.000804352726 - 0.000787400195) = 0

Separate worker:
R* = (204.20 - 176.20) / (0.000804352726 - 0.000787400195)
   = approximately 1,651,671 photo jobs over the term

Against a separate worker server, the crossing is about 86 times the expected 19,200 jobs. And 100x volume is 1.16 times the break-even volume. Before allowances, the function is cheaper than a separate worker below this point and more expensive above it.

## What could change the answer?

The two main uncertainties for the function are billed duration and repeated attempts. Changing one at a time, while holding the other costs equal between options

- Billed time that equals the separate worker's cost: At 19,200 jobs: 174.97 seconds. At 1,920,000 jobs: 1.716 seconds.
- Attempts per job that equals the separate worker's cost, at 2 seconds: At 19,200 jobs: 86.02. At 1,920,000 jobs: 0.860.

Since every photo needs at least one attempt, 0.860 attempts per photo is impossible and means the function already costs more than the separate worker at 100× volume before free allowances.

At 100x volume, the two-second function is already more expensive. It would need to finish in under 1.716 seconds, 14.2% quicker, to become cheaper.

Matching and notifier runtime also affects the full budget. Doubling both container runtimes to 120 seconds adds about $11.10 at expected volume or $1,109.93 at 100

## Free usage and the term budget

Expected: 4,800 jobs/month = 4,800 GB-seconds/month
100x:   480,000 jobs/month = 480,000 GB-seconds/month

100x compute above the allowance = 480,000 - 400,000 = 80,000
Four-month compute charge = 4 x 80,000 x 0.0000166667 = about $5.33

The 100x case exceeds the compute allowance. The function's extra request and compute cost falls to zero at expected volume and $5.33 over the term at 100x. Including the small response-transfer allowance, that is about $5.50 extra at 100x, below the separate worker's $28. Free usage can change that

The Free Plan ends after six months or when credits run out. On a paid plan, uncovered usage is billed at normal rates.