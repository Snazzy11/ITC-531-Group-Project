# Residual risk

`adapter_enumerate` (`DEPLOY_TARGET=ec2`) lists EC2, EBS, Elastic IPs, security groups, key pairs, load
balancers, API Gateway, ECS, ECR, RDS, log groups, SSM parameters and S3 buckets in us-east-2, plus the R2 bucket
when `OBJECT_STORE_*` is set. It does not cover:

| Blind spot | Checked by hand |
|---|---|
| Regions other than us-east-2 | TODO(team): EC2 Global View in the console |
| IAM users and access keys | TODO(team): IAM console, the course users' keys deactivated |
| R2 API tokens (Cloudflare account settings) | TODO(team): token revoked in the Cloudflare dashboard |
| Budgets and billing alarms (kept on purpose) | n/a |

`adapter_destroy` does not remove Milestone 6's ECS leftovers. If the audit lists any, delete them by hand before
the final audit.
