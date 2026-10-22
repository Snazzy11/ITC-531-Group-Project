# Local vs. AWS latency


In Milestone 3, we estimated p50 at around 50 ms and p95 at 100–150 ms. We also gave the API a 1-second latency budget.

## What was running

Image: `533267434818.dkr.ecr.us-east-2.amazonaws.com/seekr:f5cea42a4bb1b0873efe79a19a8fad3667fa4d63`.

Setup:

- Base URL: http://127.0.0.1:18080/api/v1
- API: Container running  with a 0.25 CPU limit and 512 MiB memory limit.
- Requests: HTTP through nginx:1.27.4-alpine.
- Database: PostgreSQL.

AWS setup:

- Base URL: https://tusbb8zllh.execute-api.us-east-2.amazonaws.com
- API: Fargate task with 0.25 vCPU and 512 MiB memory.
- Requests: HTTPS through API Gateway.
- Database: PostgreSQL.

## Results

500 requests for each run.

GET `/items`:

- Local: p50 10.5 ms, p95 47.8 ms, p99 68.2 ms. None over one second.
- AWS: p50 46.8 ms, p95 62.9 ms, p99 118.0 ms. None over one second.

POST `/auth/login`:

- Local: p50 358.6 ms, p95 753.8 ms, p99 1032.8 ms. None over one second.
- AWS: p50 349.8 ms, p95 565.9 ms, p99 771.6 ms. None over one second.

GET `/auth/me`:

- Local: p50 14.0 ms, p95 48.4 ms, p99 58.4 ms. None over one second.
- AWS: p50 46.8 ms, p95 70.9 ms, p99 107.9 ms. None over one second.

- GET `/items`: p50 +36.3 ms, p95 +15.0 ms, p99 +49.8 ms.
- POST `/auth/login`: p50 -8.7 ms, p95 -187.9 ms, p99 -261.1 ms.
- GET `/auth/me`: p50 +32.8 ms, p95 +22.5 ms, p99 +49.6 ms.

How AWS p95 compared to our Milestone 3 estimates:

- GET `/items`: 87.1 ms under the 150 ms estimate and 937.1 ms under the 1,000 ms budget.
- POST `/auth/login`: 415.9 ms over the 150 ms estimate and 434.1 ms under the 1,000 ms budget.
- GET `/auth/me`: 79.1 ms under the 150 ms estimate and 929.1 ms under the 1,000 ms budget.

All 3,000 requests returned a 200, so the error rate was 0%. All three AWS p95 values were under one second. Login was the slowest endpoint in both, and its AWS p95 was 415.9 ms above our 150 ms estimate. Five local login requests took over a second and None of the AWS requests did.

`/items` and `/auth/me` were slower on AWS, while login was faster on AWS. The AWS requests travel to Ohio through HTTPS, API Gateway, and the load balancer. The database is also on a separate EC2 instance.

Login checks a bcrypt password hash in `app/routers/auth.py`. `/auth/me` checks a token and looks up the user. So login has more CPU work to do.