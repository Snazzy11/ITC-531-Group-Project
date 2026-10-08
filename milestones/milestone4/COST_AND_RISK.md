# Cost and risk

Nothing here gets created. These are the rules we'll use when Module 6 makes the bucket. The volumes come from our Milestone 3 workload profile, which was at most around 4,800 photo uploads a month (about 160 a day).

## Lifecycle proposal

1. **Abort incomplete multipart uploads after 1 day.** Our uploads are single PUTs of 15 MB at most and they finish in seconds, so nothing real should still be uploading a day later. Abandoned parts get billed but don't show up in any listing.
2. **Expire objects under `uploads/pending/` after 1 day.** These are photos a client uploaded but never called `/complete` for (see Reconciliation in `STORAGE_DESIGN.md`). The worker deletes every completed one within a few minutes anyway.
3. **Versioning on. Non-current versions expire after 14 days, except under `uploads/pending/` where they expire after 1 day.**

### Why versioning, and what it costs

Versioning protects our photos and files from our own mistakes for two weeks, like a bug that deletes or overwrites the wrong key. The downside is that every delete keeps the old bytes around for the retention period. At steady state the extra storage is:

> deletes per day × retention days × average size

The biggest source of deletes wasn't what we expected. The worker deletes every raw upload once it's processed. The raw sizes below are our estimates.

| What gets deleted | Per day | Size | With a 14 day rule | With our rule |
|---|---|---|---|---|
| Raw uploads in `uploads/pending/` | ~160 | ~3 MB (phone photo, 15 MB cap) | ~6.7 GB | ~0.5 GB (1 day) |
| Replaced or hard-deleted photos (worst case, all of them) | up to 160 | ~0.3 MB (1280px JPEG) | up to 0.7 GB | up to 0.7 GB |

If we used one 14 day rule for everything, versioning would keep several times more deleted raw uploads than the 1-2 GB a month of photos we actually serve. The shorter rule on `uploads/pending/` keeps the whole cost of versioning to about a gigabyte.

### Storage class transition: no

Prices are AWS (our pick), US East, from the S3 pricing page (read 2026-10-05):

- S3 Standard: $0.023 per GB-month
- Standard-IA: 30 day minimum storage duration, $0.01 per 1,000 lifecycle transitions into it, $0.01 per GB retrieved, and GETs cost $0.001 per 1,000 instead of $0.0004
- Intelligent-Tiering: $0.0025 per 1,000 objects a month for monitoring (objects over 128 KB), Infrequent Access tier at $0.0125 per GB-month, no retrieval fee, $0.01 per 1,000 transitions into it

It's easiest to look at 1,000 photos at ~0.3 MB each, so 0.3 GB. In Standard they cost 0.3 × $0.023 = **$0.0069 a month**.

**Standard-IA.** Even if IA storage were free, the most we could save is that whole $0.0069 a month per 1,000 photos. Against that:

- Moving them costs $0.01, so it takes $0.01 / $0.0069 ≈ **1.5 months** of the best possible savings just to pay back the transition.
- The 30 day minimum means a photo that gets replaced or hard deleted soon after it moves is still billed for the full 30 days. With the transition fee on top, any photo that leaves within about a month and a half of moving loses money.
- Every view costs something. One view of all 1,000 photos is 0.3 GB × $0.01 = $0.003 in retrieval, plus 1,000 × ($0.001 − $0.0004) / 1,000 = $0.0006 more in GETs, so **$0.0036**. Two views a month cancels out the most we could ever save. A photo is fetched every time its item shows up in a list, so a lot of old photos would get viewed more than that.

**Intelligent-Tiering.** It has no retrieval fee, so views aren't the problem. The problem is our object size. A photo in the IA tier saves 0.3 × ($0.023 − $0.0125) = $0.00315 a month per 1,000, and monitoring costs $0.0025 per 1,000, so we'd only come out **$0.00065 ahead per 1,000 photos per month**. That's only for photos nobody looked at for 30 days, since anything viewed goes back to the frequent tier and pays monitoring without saving anything. Break even is $0.0025 / $0.0105 ≈ 0.24 GB per 1,000 photos, or **about 240 KB per photo**, and ours are only a bit over that. At $0.00065 a month it would take about 15 months to pay back the $0.01 per 1,000 transition fee.

**The whole bucket.** After a year we'd have around 4,800 × 11 = 52,800 photos older than 30 days, so ~15.8 GB. Even if all of that moved for free, the most we could save is 15.8 × $0.023 ≈ **$0.36 a month**, while moving 4,800 photos a month costs $0.048 a month in transitions before counting any retrieval fees. Also, the free plan's 5 GB covers S3 Standard, so for the first few months moving to another class would make us pay for storage that was free.

The math says no, so we're not proposing a transition. Cold classes make sense for big, long-lived files that are rarely read. Our photos are small, there are a lot of them, and they get read all the time.

## Egress

Egress is data leaving the provider to the internet. Here's what counts for us:

- **Billed at the store's egress price:** photo downloads. Every item response has a presigned `photo_url`, and the browser gets the photo straight from the store. A page of 20 items is about 6 MB. If each of the 4,800 monthly posts got viewed 50 times, that's 4,800 × 50 × 0.3 MB ≈ **72 GB a month**.
- **Not the store's egress:** file downloads (`GET /files/{id}/content`). These go through our container, so they leave from wherever Module 6 runs it.
- **Not egress at all:** presigned PUT uploads (that's ingress into the store), and the worker reading raw uploads and writing photos inside our own deployment.

Published egress price and free allowance for each candidate we shortlisted (US East / North America where it depends on region):

| Candidate | Egress price | Free allowance | Source | Date read |
|---|---|---|---|---|
| AWS | $0.09 per GB for the first 10 TB a month | First 100 GB a month, shared across all AWS services and regions | https://aws.amazon.com/s3/pricing/ | 2026-10-05 |
| Cloudflare | None, R2 doesn't charge for egress on any storage class | All egress is free. Separately, 10 GB-month of storage and 1M Class A / 10M Class B operations a month | https://developers.cloudflare.com/r2/pricing/ | 2026-10-05 |
| Azure | $0.087 per GB for the next 10 TB a month (Microsoft premium network routing) | First 100 GB a month | https://azure.microsoft.com/en-us/pricing/details/bandwidth/ | 2026-10-05 |

**What ~72 GB a month costs:** nothing on any of the three. It's under the 100 GB that AWS and Azure include, and Cloudflare never charges for egress. We'd only start paying if photo views were about 40% higher than our estimate (72 GB to 100 GB). After that every extra 100 GB is about $9 on AWS, $8.70 on Azure and $0 on Cloudflare. On AWS that 100 GB is shared with everything else we run there, including API responses and `/files` downloads, so we'd hit it sooner than the photo traffic alone suggests. That's why going over 100 GB a month is one of the switch triggers in `PROVIDER_SHORTLIST.md`.
