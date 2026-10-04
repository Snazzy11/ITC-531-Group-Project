# Storage design

When we actually implement the message queue, `publish_image_job` is in `app/messaging.py` and
`image_worker` will consume `jobs.image_processor` (see more in `MESSAGE_ARCHITECTURE.md`).
No upload endpoint calls this yet. This is the design that code should
follow once we do it.

We have only one kind of object: an item's photo, re-encoded to the app's
fixed resolution. This is a destructive process, and once the new photo is
written, the original upload is erased.

In a real app we would want thumbnail size, and a high resolution photo for
inspection. This is a good balance for us, for now.

Here we use uuids for images. Any id in relation to an image is a uuid
## Key template

```
uploads/pending/{upload_id}.{ext} # The raw image uploaded, pre processing
items/{item_id}/{upload_id}/photo.{ext} # The re-encoded photo, post processing
```

- **`uploads/pending/`** - Prefix for staging items. A presigned PUT would otherwise let
  unvalidated bytes go straight into a public key. By staging them, it keeps
  content-type checking involved without making every byte go
  through our API. Nothing reads this prefix except the image worker,
  and only once.
- **`items/`** - Prefix on the permanent copy. Lets you list
  or delete every object belonging to one item (`items/{item_id}/`), which is
  what we need for cleanups. What this gives up: we can't cheaply list "every
  photo an user ever uploaded" by using the bucket, it has to go through
  `Item.user_id` in Postgres first. Since per-item walking is the more common
  case, and bulk per-user listing is rare.
- **`{item_id}`** - scopes the object to the row that references it.
- **`{upload_id}`** (the server-generated UUID, not the filename) - a
  duplicate upload gets a fresh key instead of overwriting the old one in place. The
  worker can delete the old `upload_id` only after the new photo is confirmed
  written. Filenames never appear in the key at all so they cant reveal anything.
- **`{ext}`** - derived from the verified content type (shown how we do that below), never from the
  client's filename.

Two users upload `resume.pdf` - UUIds are secure and wont collide:

Random uuids
```
items/101/5f3b1c2a-7e4b-4b0b-9c2e-2b1a6a9d6e41/photo.jpg
items/204/9a7c0e34-6b1f-4d8d-8e21-0b3a2f7b2c10/photo.jpg
```

`.jpg` because the standardized output format is fixed regardless of what
was uploaded - see below.

## Content types

To determine content type we use `file -k`. We run it on the
actual uploaded file, ignoring the `Content-Type` header and the
filename extension. They can be manipulated by attackers and be
wrong. With no arguments, the `file` command stops at the first rule that matches.
Using `-k` keeps on reading the file after that and
reports every rule satisfied. We do that because a "polyglot upload"
can be used as an attack too. That means bytes that are simultaneously 
a valid image and a valid javascript document. This can smuggle a script past 
a naive first match check. The output of our check has to fall inside the image
allowlist, or the upload is rejected immediately so it can never be stored or 
given a chance to be malicious.

The allowlist is images, with reasonable flexibility on formats
(jpeg, png, gif, bmp, webp, heic/heif are a shortlist).
Vector types and some others are excluded even though they _are_ image
formats, like svg.** It's technically stored XML, so it can embed `<script>`,
a major attack vector. Because every accepted upload is unconditionally 
decoded and re-encoded to the standardized resolution, there's no path where
script-bearing data gets into the stored object.

## Bucket layout

| Prefix | Written by | Read by |
|---|---|---|
| `uploads/pending/{upload_id}.{ext}` | API, on upload, after the `file -k` check passes | Image worker (once, to produce the standardized photo); erased by the worker once that succeeds |
| `items/{item_id}/{upload_id}/photo.{ext}` | Image worker, after decoding + resizing the pending upload | `GET /items` and `GET /items/{item_id}`, via a presigned GET returned in the response |
