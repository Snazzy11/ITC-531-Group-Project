
# Part 4
## 4b
We read the AWS billing page was on 10-18-26 11:30 PM; see `aws_billing.png` for proof of 0 cost
The cost to date is $0.00, with the full $120 of credits still remaining, so no credits have been consumed. Our Milestone 3 model predicted **$0.00**, so the variance is **$0.00**. We expect this because **[reason from your model, e.g. all resources used fall within the AWS free tier]**.

**4c: The reversal criterion**

In Milestone 3 we said we would reverse our decision to use containers if the cost of the deployment exceeded $5. Since our cost is still $0.00 the threshold did not cross, so we are keeping the container deployment.


4. Measurement and Evaluation
4a. Latency, local versus deployed
We easured the latency for /items and /auth/me, plus /health as a baseline. Both local and remote apis were measured with the same script from the same laptop (Parker's), so the only difference between them is where the service runs.
Each run sent a single warmup request to initialize the connection, followed by 500 sequential timed requests over one reused HTTP connection (with requests.Session). The p50 and p95 were calculated from the timings. 

See results in MEASUREMENTS.md

The local-to-deployed p50 difference: /items 37.6, /auth/me 35.2, /health 36.4

How much of the difference is network round trip
At the median, the deployed service is about 36 ms slower than the local stack. The size of this gap barely changes between a trivial endpoint and endpoints that query the database, which indicates that almost all of it is network round trip time, and not our application code.

Our p95 values may be noisier than our p50 values. For example, the deployed /health p95 (at 100.5 ms) exceeded the deployed /items p95 (at 73.4 ms) in single runs.

4b. Cost against the Milestone 3 model
The AWS billing page was read on 10-18-26 at 11:30 PM; see aws_billing.png. Cost to date is $0.00, and the full $120 of credits remains, so no credits have been consumed. Our Milestone 3 model predicted $0.00, so the variance is $0.00. 

4c. The reversal criterion
In Milestone 3 we said we would reverse our decision to use containers if the cost of the deployment exceeded $5 per month. The measured cost is still $0.00 with the $120 of credits untouched. The threshold did not cross, so we are keeping the container deployment.