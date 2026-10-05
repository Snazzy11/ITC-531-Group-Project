# Provider survey: Parts 2.1 and 2.2

All information read on 2026-10-04. No account was created for this survey.
Some rows below are weaker than others: where I did not find a primary-source page I say so in the row.

## 2.1 Candidate A: Amazon Web Services

| Clause | Verdict | Evidence | URL | Date read |
|---|---|---|---|---|
| C1 runs OCI image, HTTPS URL | Partially meets | EC2 can run a container, but I only found the general EC2 page, which does not say it deploys an image and returns an HTTPS URL. | https://aws.amazon.com/ec2/ | 2026-10-04 |
| C2 S3-compatible, SigV4 | Meets | Amazon created SigV4 for AWS and S3 supports it. | https://docs.aws.amazon.com/mediatailor/latest/ug/channel-assembly-access-configuration-sigv4.html | 2026-10-04 |
| C3 scoped credentials | Meets | IAM roles can give temporary, scoped credentials. | https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_oidc.html | 2026-10-04 |
| C4 list + delete from a script | Meets | The AWS CLI is a documented way to script this. | https://docs.aws.amazon.com/cli/latest/ | 2026-10-04 |
| C5 spend alert / hard cap | Meets | You can set spend limits and notifications. | https://docs.aws.amazon.com/accounts/latest/reference/create-spend-limit.html | 2026-10-04 |
| C6 free allowance or < $5 | Partially meets | I found a free tier with a 5 GB storage allowance, but it is time-limited. | no primary source found | 2026-10-04 |

- C2 extras: endpoint URL format not determined; path-style addressing documented? Yes; same endpoint for app and browser? not determined
- C4 commands: tool = AWS CLI; list = not determined; delete = not determined

## 2.1 Candidate B: Cloudflare

| Clause | Verdict | Evidence | URL | Date read |
|---|---|---|---|---|
| C1 runs OCI image, HTTPS URL | Meets | Cloudflare has options to deploy containers directly. | https://developers.cloudflare.com/containers/ | 2026-10-04 |
| C2 S3-compatible, SigV4 | Meets | The R2 service hosts S3-compatible storage. | https://developers.cloudflare.com/r2/ | 2026-10-04 |
| C3 scoped credentials | Meets | R2 can issue temporary credentials for a chosen scope. | https://developers.cloudflare.com/r2/api/s3/temporary-credentials/ | 2026-10-04 |
| C4 list + delete from a script | Cannot determine | The page I used covers running commands in a sandbox, not listing or deleting R2 objects. | no primary source found | 2026-10-04 |
| C5 spend alert / hard cap | Cannot determine | The pricing page says you are only charged when free limits are exceeded, but I did not find a documented spend alert or hard cap. | https://developers.cloudflare.com/r2/pricing/ | 2026-10-04 |
| C6 free allowance or < $5 | Meets | R2 pricing lists a free tier. | https://developers.cloudflare.com/r2/pricing/ | 2026-10-04 |

- C2 extras: endpoint URL format not determined; path-style documented? not determined; same endpoint for app and browser? not determined
- C4 commands: tool = not determined; list = not determined; delete = not determined

## 2.2 The four questions

**AWS**
1. Perpetual or 12 months? Lasts only 6 months (read 2026-10-04).
2. Payment method at signup? Yes (hold of about $1).
3. Over the allowance? Behavior can be configured; while on the free tier you are not billed unless you choose to be.
4. Egress price? Not determined; I did not find the per-GB data-transfer-out price. The only price I noted was for compute, about $0.005/hour for small container types.

**Cloudflare**
1. Perpetual or 12 months? Appears indefinite on the free account.
2. Payment method at signup? Requires one.
3. Over the allowance? Billed at published rates; I could not find how overage or a cap is handled.
4. Egress price? Not determined; I did not find an egress price. The only price I noted was storage, $0.015 per GB-month after the first 10 GB free.
