# Cost and risk

Nothing here is created; these are the rules we will apply when Module 6
creates the bucket. Volumes come from the Milestone 3 workload profile: at
most about 4,800 photo uploads a month, roughly 160 a day.

## Lifecycle proposal

1. **Abort incomplete multipart uploads after 1 day.** Our uploads are single
   PUTs of at most 15 MB that finish in seconds, so nothing legitimate is still
   in progress a day later, and abandoned parts are billed while appearing in no
   listing.
2. **Expire objects under `uploads/pending/` after 1 day.** That is a photo a
   client uploaded but never completed (`STORAGE_DESIGN.md`, Reconciliation).
   The worker deletes every completed one within minutes.
3. **Versioning on; non-current versions expire after 14 days, except under
   `uploads/pending/`, where they expire after 1 day.**

**Why versioning, and what it costs.** Versioning protects photos and files
from our own mistakes, such as a bug that deletes or overwrites the wrong key,
for two weeks. The cost is that every delete keeps the old bytes for the
retention period. At steady state, the extra storage is:

> deletes per day × retention days × average size

The biggest source of deletes is not what we would have guessed: the worker
deletes **every raw upload** once it is processed. The raw sizes below are
our estimates.

| What is deleted | Per day | Size | 14-day retention | With the rule above |
|---|---|---|---|---|
| Raw uploads in `uploads/pending/` | ~160 | ~3 MB (phone photo; 15 MB cap) | ~6.7 GB | ~0.5 GB (1 day) |
| Replaced or hard-deleted photos (worst case: every one) | ≤160 | ~0.3 MB (1280px JPEG) | ≤0.7 GB | ≤0.7 GB |

With one blanket 14-day rule, versioning would store several times more
deleted raw uploads than the roughly 1–2 GB a month of photos we actually
serve. The shorter rule on `uploads/pending/` bounds the whole cost of
versioning to about a gigabyte.

**No storage-class transition.** Colder classes bill a minimum duration (30
days or more for the classes we looked at), often a minimum object size, and a
retrieval fee. A photo is viewed every time its item appears in a list, so a
cold photo would pay a retrieval fee on every view. Replaced photos would be
billed the full minimum anyway. The most a transition could save is:

> (standard price − colder price) × ~2 GB

That is at most a couple of gigabytes' worth of the standard price a month, so
the arithmetic says no and we propose no transition.

## Egress

Egress is bytes leaving the provider to the internet. Which of our traffic
counts:

- **Billed at the store's egress price:** photo downloads. Every item response
  carries a presigned `photo_url`, and the browser fetches the photo straight
  from the store. A page of 20 items is about 6 MB. If each of 4,800 monthly
  posts were viewed 50 times, that is 4,800 × 50 × 0.3 MB ≈ **72 GB a month**.
- **Not the store's egress:** file downloads (`GET /files/{id}/content`). These
  pass through our container, so they leave the provider from wherever Module 6
  runs it.
- **Not egress at all:** presigned PUT uploads (ingress into the store), and
  the worker reading raw uploads and writing photos inside our deployment.

Each shortlisted candidate's published egress price and free allowance, for
US East / North America where the price depends on region:

| Candidate | Egress price | Free allowance | Source | Date read |
|---|---|---|---|---|
| AWS | $0.09 per GB for the first 10 TB a month | First 100 GB a month, shared across all AWS services and regions | https://aws.amazon.com/s3/pricing/ | 2026-10-05 |
| Cloudflare | None: R2 charges nothing for egress, for any storage class | All egress is free; separately, 10 GB-month of storage and 1M Class A / 10M Class B operations a month | https://developers.cloudflare.com/r2/pricing/ | 2026-10-05 |
| Azure | $0.087 per GB for the next 10 TB a month (Microsoft premium network routing) | First 100 GB a month | https://azure.microsoft.com/en-us/pricing/details/bandwidth/ | 2026-10-05 |

**What ~72 GB a month costs.** Nothing on any of the three: it fits inside the
100 GB that AWS and Azure include, and Cloudflare never charges for egress.
Egress starts to cost money once photo views run about 40% above our estimate
(72 GB to 100 GB). From there, every extra 100 GB is about $9 on AWS, $8.70 on
Azure and $0 on Cloudflare. On AWS the 100 GB is shared with everything else
we run there, including the API's responses and `/files` downloads, so we
would reach it sooner than the photo traffic alone suggests. That is why
crossing 100 GB a month is one of the triggers in `PROVIDER_SHORTLIST.md`.
