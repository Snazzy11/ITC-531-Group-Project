# Project Milestone 4: Object Storage Integration

Module 5.

This milestone moves file handling out of your application's filesystem and into
an object store reached over the S3 API: uploads and downloads through your API,
an index of every object in your relational database, presigned URLs so large
transfers do not pass through your process, and proof that you can enumerate and
clean up what you created.

Why this matters: an application that stores uploads on its own disk cannot be
scaled, cannot be redeployed without losing data, and cannot hand a 2 GB file to a
browser without paying to move every byte twice. Object storage is the answer, and
its interface is the same at every provider, which is why this is also where your
team decides *where* it is going in Module 6.

A worked example of all six milestones and the capstone, for a different project
and written by one team, is in `reference/group-project-worked-example.md`.
Its structure is worth copying; its content is not.

Nothing in this milestone creates anything outside your machines. No cloud
account, no provider sign-up. The store runs in your compose stack. Module 6 is
first cloud contact and it is gated on a spend alert.

## Design notes

Read this to understand why the milestone is scoped the way it is.

- No CDN of any kind is created, and none is reasoned about, and no deployment
  to a virtual machine. A distribution is a real resource with a real bill, and
  decisions like an instance's public IP or the caching and invalidation choices a
  CDN would require are out of scope for this course. Modules 1–5 create nothing
  outside your machines, and your evidence is your own stack.
- No provider is named, except where you cite its own documentation as a source
  in deliverable 4. Your application talks to an S3-compatible endpoint that arrives
  in an environment variable, so the same code works no matter which provider
  Module 6 ultimately picks.
- The provider shortlist (deliverable 4) and the teardown and storage report
  (deliverable 5) exist for the same reason: nothing is created that you cannot
  enumerate and destroy.

## Deliverables

Seven items, submitted as one folder.

### 1. Storage integration

Your application stores uploaded files as objects and indexes them in the database.

- Upload, single and multiple. One endpoint for one file and one for several,
  each writing the object and a row recording at minimum the key, the original
  filename, the content type, the size in bytes and the upload time. The
  tutorial's API keeps the original name in the object's user metadata and adds no
  table (tutorial 4.1); your team keeps the index too, because the final product
  requires object metadata in the relational store.
- Validation before anything is written anywhere: a size ceiling returning
  `413`, and a content-type allow-list returning `400`. An upload endpoint with no
  ceiling is a way to fill a disk from the internet. Keys come from your code,
  never from the user's filename.
- Retrieve, list, delete. Download returns the stored content type, not
  `application/octet-stream`. Listing is paginated and filterable, at minimum by
  content type and by a substring of the original filename. Delete removes both
  the object and the row. Your application is still unauthenticated at this point;
  who may touch which file is Milestone 5's work, not this one's.
- Through one port. All storage access goes through `app/ports/storage.py`, with no
  `boto3` client anywhere else, and no endpoint URL, bucket, region or credential in
  any source file. A store failure becomes a status code your API chose, not a
  stack trace.
- The write order. One paragraph: which order your upload and delete paths write
  in, and which orphan class a partial failure therefore produces (tutorial 4.1).
  There is no transaction across the two systems, so the only question is which way
  you drift.

### 2. Presigned flows

- A presigned GET, issued by your API, fetched by something that is not your
  API: a browser or a bare `curl`.
- A presigned PUT, with a client uploading directly to the store. The bytes must
  not pass through your application; say how many bytes did.
- An expiry policy for each direction, defended, plus what your client shows a
  user whose URL has expired, not a raw XML error.
- The reconciliation answer. A presigned PUT means your API does not know
  whether the upload happened. Say which of the three strategies in tutorial 5.3
  (completion callback, store event, or reconciliation sweep) you implemented or
  would implement first, and what it does not cover.

Tutorial 5.2 is the trap: a URL signed against the endpoint your *application* uses
may be unreachable from your *user's browser*, and editing the hostname does not fix
it, because the hostname is signed. Say how you handle it.

### 3. Key design and content types

A short design document, `STORAGE_DESIGN.md`:

- The key template for every kind of object, each component justified: what does
  the leading prefix let you list cheaply, and what did you give up for it? Show the
  two keys produced when two users upload `resume.pdf`.
- Content types: where yours comes from (client claim, extension, or inspection)
  and why. Name one content type that is a security problem when served back from
  a presigned URL, and say what you store instead.
- The bucket layout: every prefix in use, what writes it, and what reads it.

### 4. Provider shortlist

Each member assessed two candidates against the capability contract in the
homework; pool them into a team decision. No account is created here: it is
documentation research.

- A shortlist table covering at least two distinct candidates, with a verdict
  on each of C1–C6 and, for every verdict, a URL and the date it was read. If two
  members assessed the same candidate and disagreed, say so and say who was right.
- The team's choice and a named fallback, in one paragraph argued from *this*
  application's needs (storage volume, presigned uploads, store events, egress),
  plus, for each rejected candidate, the clause that eliminated it, and for the
  chosen one, the observation that would make you switch and who is watching for it.
- Route B. State whether any member requires Route B (see
  `reference/route-b-local-equivalence.md`) and whether the request has been made.
  This decision must be settled during this milestone, because Module 6's work
  differs between the routes, and a team that discovers this in Module 6 loses a module.

### 5. Teardown and the storage report

- The storage report: `storage_report.py` from homework Part 3, run against
  your own stack, output and exit code captured twice: one clean run, and one
  after you deliberately create a stray object (an unstamped object left by a
  presigned PUT, or a key that does not match your scheme). A team may use one
  member's script, with attribution. Add one pass over the index your team keeps and
  the tutorial's API does not (an object with no row, a row with no object), and
  show it finding one of those too.
- Teardown evidence. `docker compose down --volumes`, then `docker ps` and
  `docker volume ls | grep itc531` both empty, captured.
- The versioned-bucket paragraph. In your own words: why an "empty" versioned
  bucket is not empty, why `empty_bucket()` in the port (like `Store.empty()` in
  tutorial 2.1) pages `list_object_versions` rather than `list_objects_v2`, and what
  would go wrong in Module 8 if it did not. This is the most common teardown failure
  in this course.

### 6. Documentation

- An architecture diagram of your application, the object store, the database,
  and, as a distinct path, the presigned flow where bytes travel directly between
  client and store. A diagram that does not show that path separately is not showing
  the thing this milestone is about.
- A setup and testing guide: every environment variable and what belongs in it,
  every endpoint with a runnable command, and who wrote which part. Somebody outside
  your team must be able to follow it, because in Module 7 somebody outside your team
  will review it.

### 7. Cost and risk note

One page is plenty, and nothing here is created.

- A lifecycle proposal, including a rule aborting incomplete multipart uploads
  after N days, and the versioning decision with its storage consequence and the
  expiry rule that bounds it. If you propose a storage-class transition, show the
  minimum-billable-duration arithmetic from tutorial Part 6 first; if the arithmetic
  says no, propose no transition and show the arithmetic.
- Egress reasoning: the egress price each shortlisted candidate publishes, the
  free allowance it comes with, and which of your application's traffic would be
  billed at it, cited as in homework Part 2.2. Create nothing.

*What earns credit:* every item above, present and specific to your application.
If a required deliverable here contradicts something elsewhere, tell the instructor:
that is a defect, not an ambiguity for you to resolve.

## Submission Instructions

Upload your team's compressed `milestone4` folder as `milestone4.zip` to
Blackboard. One submission per team.

```
milestone4/
├── README.md                    what is in here, who wrote which part, how to run it
├── STORAGE_DESIGN.md            deliverable 3
├── PROVIDER_SHORTLIST.md        deliverable 4, with every URL and date read
├── COST_AND_RISK.md             deliverable 7
├── architecture-diagram.png     deliverable 6
├── app/files.py                 your storage endpoints, and whatever else changed
├── scripts/storage_report.py    deliverable 5
├── evidence/
│   ├── upload.txt               responses, object listing, database rows, the 413 and the 400
│   ├── presigned.txt            both URLs, the fetch, the direct upload, the listing
│   ├── report-clean.txt         and report-dirty.txt: both runs, exit codes shown
│   └── teardown.txt             docker compose down --volumes, docker ps, docker volume ls
└── sources.md                   every URL cited, the date read, and who read it
```

No credential appears anywhere in this ZIP, not in source, a compose file, a
screenshot, or a captured terminal session. Submit `adapters/<yours>.env.example`,
every value replaced by a description of what belongs there, never the real one. If
a credential appears in something already submitted, treat it as leaked and read
`reference/credential-incident.md` today.

## Before you submit

- [ ] Upload writes an object *and* a row, delete removes both, and the `413` and
      the `400` are in a transcript
- [ ] No `boto3` client outside `app/ports/storage.py`, and no endpoint URL, bucket,
      key or secret in any source file
- [ ] A presigned GET was fetched by something that is not your API, and a presigned
      PUT uploaded bytes that never entered your application
- [ ] Every C1–C6 verdict carries a URL and a date, each rejection names a clause, and
      the Route B position is stated
- [ ] Storage report captured clean and dirty with exit codes, and both teardown
      checks are empty
- [ ] Nothing was created outside your machines. No account was created.

## Sharing and peer review

Milestone 4 is shared and peer-reviewed in Module 6, under a separate Blackboard
item with its own deadline. Milestone 3 is peer-reviewed during Module 5, under
"Group Project: Milestone 3 Sharing & Peer Reviews (Module 5)". Reviewing another
team's deployment-shape decision while you make your storage-provider decision is
deliberate: the two constrain each other.

Every deliverable above is required, and nothing beyond it is expected. If you
find a requirement here that is unclear or appears to conflict with something
elsewhere, tell the instructor: that is a defect in this document, not an
ambiguity for you to resolve.
