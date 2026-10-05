# Provider shortlist

Candidates were assessed against the capability contract (C1–C6): Parker looked at AWS and Cloudflare, and Doug used AWS and Azure.
URLs are also in `sources.md`.

| Candidate | Assessed by | C1 | C2 | C3 | C4 | C5 | C6 |
|---|---|---|---|---|---|---|---|
| AWS | Parker, Doug | Partially meets | Meets | Meets | Meets | Meets | Meets |
| Cloudflare | Parker | Meets | Meets | Meets | Cannot determine | Cannot determine | Meets |
| Azure | Doug | Meets | **Does not meet** | Meets | Meets | Meets | Meets |

## Amazon Web Services (AWS)

Assessed by both members. The pooled verdict is in the first column of
verdicts; where the two disagreed, both are shown.

| Clause | Pooled verdict | Parker | Doug | Evidence                                                                                                                                                                             | URL | Date read |
|---|---|---|---|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---|---|
| C1 runs OCI image, HTTPS URL | Partially meets | Partially meets | Meets | EC2 can run a container, but the page does not explicitly say it deploys an image and returns an HTTPS URL| https://aws.amazon.com/ec2/ | 2026-10-04 |
| C2 S3-compatible, SigV4 | Meets | Meets | Meets | S3 authenticates requests with SigV4, including presigned URLs signed in the query string. | https://docs.aws.amazon.com/AmazonS3/latest/API/sigv4-query-string-auth.html | 2026-10-05 |
| C3 scoped credentials | Meets | Meets | Meets | IAM roles can give temporary, scoped credentials. | https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_oidc.html | 2026-10-04 |
| C4 list + delete from a script | Meets | Meets | Possibly meets | The AWS CLI is a documented way to script this.                                                                                                                                      | https://docs.aws.amazon.com/cli/latest/ | 2026-10-04 |
| C5 spend alert / hard cap | Meets | Meets | Meets | Spend limits and notifications can be set.                                                                                                                                           | https://docs.aws.amazon.com/accounts/latest/reference/create-spend-limit.html | 2026-10-04 |
| C6 free allowance or < $5 | Meets | Partially meets | Meets | New customers get 5 GB of S3 Standard storage and 100 GB a month of data transfer out, plus up to $200 in credits on a free plan that lasts up to 6 months | https://aws.amazon.com/free/free-tier-faqs/ and https://aws.amazon.com/s3/pricing/ | 2026-10-05 |

**Disagreements**

- **C1:** Parker was right. Since the cited page does not explicitly say it deploys 
  an image and returns an HTTPS URL, it cannot fully say it "meets"
- **C4:** Parker was right. Doug couldnt find a source, but since parker did it overrides
- **C6:** Doug was right. The 5GB figure came from a blog and not AWS offically,
  but AWS's own pages confirm it. Parker was right that the allowance is
  time-limited, but it still meets the clause.

For C2 and C6 the pooled rows cite AWS's own pages, read on 2026-10-05. They
replace the sources we first used: SigV4 documentation for a different AWS
service (MediaTailor), and the third-party blog.

## Cloudflare

Assessed by Parker.

| Clause | Verdict | Evidence                                                                                                                             | URL | Date read |
|---|---|--------------------------------------------------------------------------------------------------------------------------------------|---|---|
| C1 runs OCI image, HTTPS URL | Meets | Cloudflare has options to deploy containers directly.                                                                                | https://developers.cloudflare.com/containers/ | 2026-10-04 |
| C2 S3-compatible, SigV4 | Meets | The R2 service hosts S3-compatible storage.                                                                                          | https://developers.cloudflare.com/r2/ | 2026-10-04 |
| C3 scoped credentials | Meets | R2 can issue temporary credentials for a chosen scope.                                                                               | https://developers.cloudflare.com/r2/api/s3/temporary-credentials/ | 2026-10-04 |
| C4 list + delete from a script | Cannot determine | We found things about _running_ commands in a sandbox, but not listing or deleting objects.                                          | no source found | 2026-10-04 |
| C5 spend alert / hard cap | Cannot determine | The pricing page says you are only charged when free limits are exceeded, but no information about spend alert or hard cap was found | https://developers.cloudflare.com/r2/pricing/ | 2026-10-04 |
| C6 free allowance or < $5 | Meets | R2 pricing lists a free tier that appears indefinite.                                                                                | https://developers.cloudflare.com/r2/pricing/ | 2026-10-04 |

## Microsoft Azure (Blob Storage)

Assessed by Doug.

| Clause | Verdict | Evidence | URL | Date read |
|---|---|---|---|---|
| C1 runs OCI image, HTTPS URL | Meets | Azure Container Apps run containerized applications. | https://learn.microsoft.com/en-us/azure/container-apps/quickstart-portal | 2026-10-04 |
| C2 S3-compatible, SigV4 | Does not meet | Blob Storage has no S3-compatible endpoint; data can be migrated from S3, but not accessed with the S3 API. | https://learn.microsoft.com/en-us/azure/storage/common/storage-use-azcopy-s3 | 2026-10-04 |
| C3 scoped credentials | Meets | Microsoft recommends Entra ID with managed identities to authorize access to blobs. | https://learn.microsoft.com/en-us/azure/storage/common/authorize-data-access | 2026-10-04 |
| C4 list + delete from a script | Meets | Blobs can be listed and deleted. | https://learn.microsoft.com/en-us/azure/storage/blobs/storage-blobs-list and https://learn.microsoft.com/en-us/azure/storage/blobs/storage-blob-delete | 2026-10-04 |
| C5 spend alert / hard cap | Meets | Budgets and alerts can be created to manage costs. | https://learn.microsoft.com/en-us/azure/storage/common/storage-plan-manage-costs#monitor-costs | 2026-10-04 |
| C6 free allowance or < $5 | Meets | $200 in credits for the first 30 days, and some services free for 12 months. | https://azure.microsoft.com/en-us/pricing/offers/ms-azr-0044p/ | 2026-10-04 |

## Team decision

**We choose AWS, with Cloudflare as the fallback.**
- **Storage volume.** Milestone 3 estimated about 4,800 photo uploads a month
  at most. Each is re-encoded to a JPEG of at most 1280px, so stored volume
  grows by roughly a gigabyte or two a month, plus small user files. Any
  candidate's allowance or a few dollars covers that, so storage price does not
  decide this.
- **Presigned uploads.** The photo flow depends on SigV4 presigned PUT and GET
  URLs against an S3 endpoint. That makes C2 a hard requirement, and the
  storage port speaks only S3.
- **Store events.** We do not need them. Reconciliation is a completion
  callback, so a provider's event notifications do not affect the choice.
- **Egress.** Photo downloads through presigned GETs are our main outbound
  traffic, about 72 GB a month at our estimate (`COST_AND_RISK.md`). That is
  free on all three: AWS and Azure each include 100 GB a month, and Cloudflare
  charges nothing for egress. Past 100 GB, AWS charges $0.09 per GB, so egress
  is what would most likely change our choice.

AWS meets C2 through C6 on the evidence we have, runs the `boto3` code we
already wrote unchanged, and has a documented spend alert we can set before
Module 6 creates anything.

**Rejected: Azure, on C2.** Blob Storage has no S3-compatible endpoint, so our
storage port and presigned SigV4 URLs would not work against it without a
rewrite. It therefore cannot be our fallback, even though it passes every
other clause.

**Fallback: Cloudflare.** It passes C2, so moving would mean changing
environment variables, not code. It is not our first choice because of C5: we
found no documented spend alert or hard cap, and we want that assurance before
anything is created. C4 is also undetermined.

**What would make us switch, and who is watching.** We would move to
Cloudflare if any of these happens:
- Our AWS spend alert fires once the time-limited free tier ends.
- Photo egress passes 100 GB a month. Every 100 GB after that is $9 on AWS
  and $0 on Cloudflare.
- Cloudflare documents a spend alert or hard cap (C5), since its free tier
  appears perpetual.

Parker watches all three. He sets the AWS spend alert before Module 6 and
re-reads both pricing pages at the same time.

## Route B

No member has asked for Route B, so no request has been made, and the team
plans to take the standard route in Module 6.

One defect to report: the milestone points to
`reference/route-b-local-equivalence.md`, but that file is not in the course
materials available to us.
