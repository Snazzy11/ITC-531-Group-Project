# Provider shortlist

Candidates were assessed against the capability contract (C1–C6): Parker looked at AWS and Cloudflare, and Doug used AWS and Azure.
URLs are also in `sources.md`.

| Candidate | Assessed by | C1 | C2 | C3 | C4 | C5 | C6 |
|---|---|---|---|---|---|---|---|
| AWS | Parker, Doug | Partially meets | Meets | Meets | Meets | Meets | Meets |
| Cloudflare | Parker | Meets | Meets | Meets | Cannot determine | Cannot determine | Meets |
| Azure | Doug | Meets | **Does not meet** | Meets | Meets | Meets | Meets |

## Amazon Web Services (AWS)

We both looked at AWS. The first verdict column is the one we agreed on, and the next two are what each
of us found on our own.

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

For C2 and C6 we switched to AWS's own pages (read on 2026-10-05). At first we had used SigV4 docs for a 
different AWS service (MediaTailor) and the third-party blog.

## Cloudflare

Parker looked at Cloudflare.

| Clause | Verdict | Evidence                                                                                                                             | URL | Date read |
|---|---|--------------------------------------------------------------------------------------------------------------------------------------|---|---|
| C1 runs OCI image, HTTPS URL | Meets | Cloudflare has options to deploy containers directly.                                                                                | https://developers.cloudflare.com/containers/ | 2026-10-04 |
| C2 S3-compatible, SigV4 | Meets | The R2 service hosts S3-compatible storage.                                                                                          | https://developers.cloudflare.com/r2/ | 2026-10-04 |
| C3 scoped credentials | Meets | R2 can issue temporary credentials for a chosen scope.                                                                               | https://developers.cloudflare.com/r2/api/s3/temporary-credentials/ | 2026-10-04 |
| C4 list + delete from a script | Cannot determine | We found things about _running_ commands in a sandbox, but not listing or deleting objects.                                          | no source found | 2026-10-04 |
| C5 spend alert / hard cap | Cannot determine | The pricing page says you are only charged when free limits are exceeded, but no information about spend alert or hard cap was found | https://developers.cloudflare.com/r2/pricing/ | 2026-10-04 |
| C6 free allowance or < $5 | Meets | R2 pricing lists a free tier that appears indefinite.                                                                                | https://developers.cloudflare.com/r2/pricing/ | 2026-10-04 |

## Microsoft Azure (Blob Storage)

Doug looked at Azure.

| Clause | Verdict | Evidence | URL | Date read |
|---|---|---|---|---|
| C1 runs OCI image, HTTPS URL | Meets | Azure Container Apps run containerized applications. | https://learn.microsoft.com/en-us/azure/container-apps/quickstart-portal | 2026-10-04 |
| C2 S3-compatible, SigV4 | Does not meet | Blob Storage has no S3-compatible endpoint; data can be migrated from S3, but not accessed with the S3 API. | https://learn.microsoft.com/en-us/azure/storage/common/storage-use-azcopy-s3 | 2026-10-04 |
| C3 scoped credentials | Meets | Microsoft recommends Entra ID with managed identities to authorize access to blobs. | https://learn.microsoft.com/en-us/azure/storage/common/authorize-data-access | 2026-10-04 |
| C4 list + delete from a script | Meets | Blobs can be listed and deleted. | https://learn.microsoft.com/en-us/azure/storage/blobs/storage-blobs-list and https://learn.microsoft.com/en-us/azure/storage/blobs/storage-blob-delete | 2026-10-04 |
| C5 spend alert / hard cap | Meets | Budgets and alerts can be created to manage costs. | https://learn.microsoft.com/en-us/azure/storage/common/storage-plan-manage-costs#monitor-costs | 2026-10-04 |
| C6 free allowance or < $5 | Meets | $200 in credits for the first 30 days, and some services free for 12 months. | https://azure.microsoft.com/en-us/pricing/offers/ms-azr-0044p/ | 2026-10-04 |

## Team decision

**We choose AWS, with Cloudflare as the fallback.** What our app actually needs is pretty small:

- **Storage volume.** In Milestone 3 we estimated around 4,800 photo uploads a month at most. Each one gets re-encoded to a JPEG of at most 1280px, so storage only grows by a gigabyte or two a month, plus some small user files. Any of the free allowances (or a few dollars) covers that, so storage price didn't really decide anything.
- **Presigned uploads.** The photo flow depends on SigV4 presigned PUT and GET URLs against an S3 endpoint, and our storage port only speaks S3. So C2 is a hard requirement for us.
- **Store events.** We don't need them. We do reconciliation with a completion callback, so whether a provider has event notifications doesn't matter.
- **Egress.** Photo downloads through presigned GETs are most of our outbound traffic, around 72 GB a month by our estimate (see `COST_AND_RISK.md`). That's free on all three since AWS and Azure both include 100 GB a month and Cloudflare doesn't charge for egress at all. Past 100 GB AWS charges $0.09 per GB, so egress is the most likely thing to change our choice.

AWS meets C2 through C6 from what we found, runs the `boto3` code we already wrote without changes, and has a documented spend alert we can set up before Module 6 creates anything.

**Rejected: Azure, because of C2.** Blob Storage doesn't have an S3-compatible endpoint, so our storage port and presigned URLs wouldn't work with it without a rewrite. Even though it passes every other clause, it can't be our fallback either.

**Fallback: Cloudflare.** It passes C2, so switching would just mean changing environment variables, not code. It's not our first pick because of C5, since we couldn't find a documented spend alert or hard cap and we want that before we create anything. C4 is also still undetermined.

**What would make us switch.** We would move to Cloudflare if:
- our AWS spend alert goes off after the free tier ends
- photo egress goes over 100 GB a month (every 100 GB after that is $9 on AWS and $0 on Cloudflare)
- Cloudflare documents a spend alert or hard cap (C5), since their free tier looks permanent

Parker is watching for all three. He'll set the AWS spend alert before Module 6 and re-read both pricing pages then.

## Route B

Nobody on our team needs Route B, so we haven't made a request and we're planning on the standard route for Module 6.

Something to report: the milestone links to `reference/route-b-local-equivalence.md`, but that file isn't in the course materials we have.
