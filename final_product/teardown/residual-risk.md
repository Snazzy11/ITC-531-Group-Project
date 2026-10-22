# Residual risk: what our audit can't see

`bash scripts/cloud-audit.sh aws` prints `CLEAN` only when `adapter_enumerate` prints nothing. With
`DEPLOY_TARGET=ec2`, `adapter_enumerate` lists these:

- **In `AWS_REGION` (us-east-2), whoever made them:**
  - EC2: instances not yet terminated, EBS volumes, our EBS snapshots, our AMIs, Elastic IPs, NAT gateways,
    security groups other than `default`, key pairs
  - load balancers, target groups, API Gateway HTTP APIs
  - ECS clusters (and ECS services, when `ECS_CLUSTER` is set)
  - ECR repositories
  - RDS instances and snapshots
  - CloudWatch log groups, SSM parameters
- **Account-wide:** S3 buckets.
- **At Cloudflare:** the R2 bucket and its object count, when `OBJECT_STORE_BUCKET` is set.

A listing the IAM user isn't allowed to make stops the audit with an error, rather than counting as empty. The list
is region-wide on purpose, so it also shows leftovers from Milestone 6's ECS deployment, which `adapter_destroy`
does not remove (see below).

## Blind spots, and how we checked each by hand

TODO(team): fill in the last two columns while doing the teardown, and keep the evidence (a console screenshot or
the CLI output) with the transcripts.

| Blind spot | Why the adapter misses it | How to check by hand | Checked by, date (UTC), result |
|---|---|---|---|
| Every region except us-east-2 | Every listing passes `--region "$AWS_REGION"` | Console, EC2 Global View: instances, volumes, security groups in all regions. Or loop `aws ec2 describe-instances --region <r>` over `aws ec2 describe-regions` | TODO(team) |
| IAM users, access keys, console passwords, policies | IAM isn't enumerated. Deleting the deploy users would end the audit's own access | IAM console, Users: for `seekr-deployer`, `seekr-doug` and `seekr-parker`, deactivate or delete course access keys and remove console passwords no longer needed. Check for leftover roles | TODO(team) |
| Budgets, billing alarms, SNS topics | Account-level. The spend alert (C5 of the contract) should stay until the bill closes | Billing and Cost Management, Budgets; CloudWatch, Alarms; SNS, Topics | TODO(team) |
| Network interfaces, VPC endpoints, non-default VPCs and subnets | Not listed. The instance's own interface goes with it, but anything created by hand would stay | VPC console: Network interfaces (status `available`), Endpoints, Your VPCs | TODO(team) |
| ECR images | Only repositories are listed; deleting a repository deletes its images | Covered once the repository is gone | n/a |
| AWS Backup | Recovery points in a backup vault are not listed | AWS Backup, Backup vaults | TODO(team) |
| The R2 bucket, if `OBJECT_STORE_*` isn't set | The audit then only warns on stderr | Cloudflare dashboard, R2: the bucket is gone, or empty and deleted | TODO(team) |
| R2 API tokens, the bucket's public `r2.dev` URL setting | Cloudflare account settings, not resources the S3 API can see | Cloudflare dashboard, R2, Manage API tokens: revoke the token the instance used | TODO(team) |
| Copies of secrets outside both clouds | The instance's `.env.local` goes when the instance terminates, but copies on laptops don't | Delete the instance's `.pem` from every laptop it was copied to. Keep `.env.local` files only where local development needs them | TODO(team) |
| GitHub Actions cache | CI caches image layers (`cache-to: type=gha`) in the repository, not in a cloud account | GitHub, Actions, Caches | TODO(team) |

## What `adapter_destroy` removes, and what it leaves

For `DEPLOY_TARGET=ec2`, `adapter_destroy` does the following in order. Each step is skipped if its resource is
already gone, and with `ADAPTER_DRY_RUN=1` it prints every change instead of making it:

1. Empties and deletes the R2 bucket, if `OBJECT_STORE_*` is set.
2. Terminates `EC2_INSTANCE_ID`. The root volume is deleted with it if it was created with the default
   delete-on-termination.
3. Releases the instance's Elastic IPs, deletes any of its volumes not set to delete on termination, and deletes
   its non-default security groups (here `launch-wizard-1`).
4. Deletes the key pair `EC2_KEY_NAME`, if it is set.

It does not remove anything it didn't deploy. Milestone 6's ECS cluster, ECR repository, load balancer, target
group, API Gateway API and Parameter Store entries may still exist. The audit before teardown lists any that do.
They have to be deleted by hand (TODO(team): record what was deleted, and when) before the audit after teardown can
print `CLEAN`.
