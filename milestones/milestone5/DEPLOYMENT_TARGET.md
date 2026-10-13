## 7a. Deployment target

We chose AWS for Seekr. Our app already uses the S3 API for photos and files, so AWS fits the storage code we have.

The AWS adapter uses ECS for containers and S3 for storage in us-east-2.

## 7b. Contract requirements

- C1: runs an OCI image and returns an HTTPS URL

ECS can run the container image we push. An HTTPS load balancer can give users a secure URL for the app.

- C2: an S3-compatible object storage endpoint reachable with SigV4 credentials

Amazon S3 supports the S3 API and SigV4 authentication. This works with the signed upload and download URLs Seekr already uses.

- C3: credentials scoped narrower than account-wide, by OIDC federation or a revocable token

IAM policies let us limit credentials to the project's services and resources. Access keys can also be revoked when they are no longer needed.

- C4: a published, scriptable way to enumerate what exists and to delete it

The AWS CLI has commands for listing and deleting ECS resources, S3 objects, and buckets. We can use these commands in the adapter to find and clean up the project's resources.

- C5: a spend alert or hard cap the student can configure

AWS Budgets lets us set a $5 budget and send email alerts when spending reaches the chosen threshold.

- C6: a stated free allowance, or a cost under $5 for the term's usage profile

AWS offers $100 in signup credits for eligible new customers, with up to $100 more through qualifying activities. This gives the project a published allowance, depending on the account's eligibility and credit expiry date.

## 7c. Fallback

Cloudflare is the fallback.

Switching would mean rewriting the provider adapter and deployment settings, replacing AWS credentials, and changing the storage endpoints. We would also need a plan to move our files and database data. Keeping the S3 interface should let us reuse most of the storage code, but the compute setup would need changing.

## 7d. Spending

Our proposed ceiling is $5 total for the team's deployment over the term.

We will check AWS billing during deployment and receive the budget emails.

If spending approaches the ceiling, we will stop adding resources, check what is causing the cost, and remove resources we no longer need.