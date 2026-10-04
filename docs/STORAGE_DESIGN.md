# Storage design

The API hands out upload links and queues `jobs.image_processor` (see
`MESSAGE_ARCHITECTURE.md`); `image_worker` checks and re-encodes the upload.
Code: `app/api.py` (endpoints), `app/storage.py` (S3), `app/image_worker.py`
and `app/image_processing.py` (checks and re-encoding).

We have only one kind of object: an item's photo, re-encoded to the app's
fixed resolution (a JPEG, at most 1280px on its longest side). Each item has
at most one; a new upload replaces it. This is a destructive process, and once
the new photo is written, the original upload is erased.

In a real app we would want thumbnail size, and a high resolution photo for
inspection. This is a good balance for us, for now.

Here we use uuids for images. Any id in relation to an image is a uuid

## Architecture

See Architecture.drawio.html

## Upload flow

1. `POST /items/{item_id}/images` creates an `images` row (`awaiting_upload`)
   and returns an `upload_id` and a presigned `upload_url`, valid 10 minutes.
2. The client PUTs the file to `upload_url`. The bytes go straight to the
   store and never pass through the gateway or the API.
3. `POST /items/{item_id}/images/{upload_id}/complete`. The API checks that the
   object exists, queues the image job, and sets the row to `processing`.
   Nothing is queued until the client calls this.
4. The image worker checks the upload (below), writes the re-encoded photo, and
   sets the row to `ready`, or `rejected` with a `reject_reason`. It then
   deletes the item's previous photo and the pending upload.
5. Item responses carry `photo_url`, a presigned GET valid for 1 hour.
   `GET /items/{item_id}/images/{upload_id}` shows the status of one upload.

```shell
API=http://localhost:8000/api/v1
UPLOAD=$(curl -s -X POST $API/items/1/images)
curl -s -X PUT --upload-file photo.jpg "$(echo "$UPLOAD" | jq -r .upload_url)"
curl -s -X POST "$API/items/1/images/$(echo "$UPLOAD" | jq -r .upload_id)/complete"
```

An upload that is never completed stays `awaiting_upload` and its object stays
in `uploads/pending/`. On AWS, a bucket lifecycle rule should expire that
prefix after a day; the app does not clean it up.

## Key template

```
uploads/pending/{upload_id} # The raw image uploaded, pre processing
items/{item_id}/{upload_id}/photo.jpg # The re-encoded photo, post processing
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
- **`.jpg`** - fixed, because the worker always re-encodes to JPEG. The pending
  key has no extension at all: nothing about the upload is known or trusted
  until the worker checks it.

Two users upload `resume.pdf` - UUIds are secure and wont collide:

Random uuids
```
items/101/5f3b1c2a-7e4b-4b0b-9c2e-2b1a6a9d6e41/photo.jpg
items/204/9a7c0e34-6b1f-4d8d-8e21-0b3a2f7b2c10/photo.jpg
```

`.jpg` because the standardized output format is fixed regardless of what
was uploaded - see below.

## Content types

To determine content type we use `file -k`. The image worker runs it on the
actual uploaded file, ignoring the `Content-Type` header and the
filename extension. They can be manipulated by attackers and be
wrong. With no arguments, the `file` command stops at the first rule that matches.
Using `-k` keeps on reading the file after that and
reports every rule satisfied. We do that because a "polyglot upload"
can be used as an attack too. That means bytes that are simultaneously 
a valid image and a valid javascript document. This can smuggle a script past 
a naive first match check. The output of our check has to fall inside the image
allowlist, or the upload is rejected immediately so it can never be stored or 
given a chance to be malicious. (Every image also matches a generic
`application/octet-stream` rule, which says nothing about the bytes, so that
line is ignored.)

`file -k` only catches a polyglot whose second format it recognizes. It also
looks for most formats only at the start of the file. Data appended after a
valid image, such as a PNG followed by a ZIP or an HTML page, passes the check.
The re-encode below is what removes it: the stored photo is a new JPEG built
from the decoded pixels, so nothing after the image survives.

The allowlist is images, with reasonable flexibility on formats
(jpeg, png, gif, bmp, webp, heic/heif).
Vector types and some others are excluded even though they _are_ image
formats, like svg. It's technically stored XML, so it can embed `<script>`,
a major attack vector. Because every accepted upload is unconditionally 
decoded and re-encoded to the standardized resolution, there's no path where
script-bearing data gets into the stored object.

The re-encode uses Pillow, limited to decoders for those same formats.
Writing a fresh JPEG also drops EXIF metadata, including the GPS location
most phone photos have. Uploads over 15 MB or 50 megapixels are rejected.

## Bucket layout

| Prefix | Written by | Read by |
|---|---|---|
| `uploads/pending/{upload_id}` | Client, by PUT to the presigned `upload_url` | Image worker, once; erased by the worker whether the upload is stored or rejected |
| `items/{item_id}/{upload_id}/photo.jpg` | Image worker, after `file -k` passes and the image is decoded and resized | Client, by GET to the presigned `photo_url` on item responses. Deleted when a newer photo replaces it or the item is hard-deleted |

The bucket is private. Every client read or write goes through a presigned
URL, and no presigned GET is ever made for `uploads/pending/`.
