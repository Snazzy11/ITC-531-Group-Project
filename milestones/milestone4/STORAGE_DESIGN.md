# Storage design

We store two kinds of objects:

- Item photos. The client uploads straight to the store with a presigned PUT, then `image_worker` checks and re-encodes it. The API never touches the photo bytes.
- User files. These are things a user keeps on hand to prove an item is theirs when they claim it, like a receipt or a picture of a serial number. These go through the API (`/files`), which checks each file before anything gets written.

The code is in `app/ports/storage.py` (the only module that talks to the store), `app/routers/files.py` (file endpoints), `app/routers/images.py` (photo endpoints), and `app/image_worker.py` / `app/image_processing.py` (photo checks and re-encoding). The diagram is `architecture-diagram.png`.

Every item photo gets re-encoded to a fixed size, a JPEG that is at most 1280px on its longest side. Each item only has one photo, and a new upload replaces it. This is destructive, since once the new photo is written the original upload is erased. In a real app we would probably want a thumbnail and a high resolution copy for inspecting, but this is a good balance for us for now.

Any id that is part of an object key is a UUID that our code generates.

## Photo upload flow

1. `POST /items/{item_id}/images` creates an `images` row (`awaiting_upload`) and returns an `upload_id` and a presigned `upload_url` that is good for 10 minutes.
2. The client PUTs the file to `upload_url`. The bytes go right to the store and never go through the gateway or the API.
3. The client calls `POST /items/{item_id}/images/{upload_id}/complete`. The API checks that the object is actually there, queues the image job, and sets the row to `processing`. Nothing is queued until the client calls this.
4. The image worker checks the upload (see Content types), writes the re-encoded photo, and sets the row to `ready`, or to `rejected` with a `reject_reason`. Then it deletes the item's old photo and the pending upload.
5. Item responses include `photo_url`, a presigned GET that lasts 1 hour. `GET /items/{item_id}/images/{upload_id}` shows the status of a single upload.

```shell
API=http://localhost:8000/api/v1
UPLOAD=$(curl -s -X POST $API/items/1/images)
curl -s -X PUT --upload-file photo.jpg "$(echo "$UPLOAD" | jq -r .upload_url)"
curl -s -X POST "$API/items/1/images/$(echo "$UPLOAD" | jq -r .upload_id)/complete"
```

## Key templates

```
uploads/pending/{upload_id}  (raw photo upload, before checks)
items/{item_id}/{upload_id}/photo.jpg  (the re-encoded photo)
users/{user_id}/files/{upload_id}.{ext}  (a file uploaded through /files)
```

- `uploads/pending/` is where photos get staged. If the presigned PUT went straight to a key we serve, unchecked bytes could end up being served to people. Staging them lets us still check the content type without making every byte go through our API. Only the image worker reads this prefix, and only once per upload.
- `items/` is the prefix for the final photo. It lets us list or delete everything for one item (`items/{item_id}/`), which is what we need for cleanup. The downside is we can't cheaply list "every photo one user ever uploaded" from the bucket. For that we have to go through `Item.user_id` in Postgres first. Walking one item is the common case and listing per user is rare, so we were fine with that.
- `users/{user_id}/` is the prefix for user files. We put the user first because "what proof do I have on file" is the question a claim asks, and with this layout it's one list call. The downside is something like "every PDF uploaded this week" would mean listing every user's prefix. We answer that with the `files` table instead, since it has `content_type` and `uploaded_at` columns and that's what `GET /files` filters on.
- `{item_id}` ties the photo to the row that points to it.
- `{upload_id}` is a UUID from the server, never the filename. A second upload gets a new key instead of overwriting the old one, so the worker can wait until the new photo is written before deleting the old one. Since filenames are never in a key, they can't leak anything or collide. The original filename is kept in the `files` table and in the object's `original-name` metadata.
- `.jpg` is fixed because the worker always re-encodes to JPEG. The pending key has no extension at all, since we don't know or trust anything about the upload until the worker has checked it.
- `.{ext}` on files is picked by our code from the type we detect in the bytes (`pdf`, `jpg`, `png`, `webp`, `heic`). It is not taken from the filename.

If two users both upload `resume.pdf` through `POST /files`, the keys are different in the user id and the UUID, which neither user picked. `resume.pdf` isn't in either key, so the second upload can't replace the first:

```
users/17/files/3f1c9e0a-6b2d-4c71-9a55-0d8e7f1b2c34.pdf
users/42/files/b7a4d2e8-1c93-4f06-8e2a-5c6d9b0f3a11.pdf
```

(A PDF couldn't be an item photo anyway, the image worker would reject it.)

## Content types

We get the content type by running `file -k` on the actual bytes. We ignore the `Content-Type` header and the file extension, because both can be faked by an attacker or just be wrong. By default `file` stops at the first rule that matches. With `-k` it keeps going and reports every rule that matches. We do this because of polyglot uploads, where the bytes are a valid image and also something else at the same time (like JavaScript), which could get a script past a check that only looks at the first match. Every match has to be in the allow-list or the upload is refused before it's stored. (Every file also matches a generic `application/octet-stream` rule. That doesn't tell us anything so we ignore it.)

`file -k` isn't perfect. It only catches a polyglot if it recognizes the second format, and for most formats it only looks at the start of the file. So data stuck on after a valid image, like a PNG followed by a ZIP or an HTML page, would pass. For photos the re-encode is what handles that. The stored photo is a brand new JPEG built from the decoded pixels, so anything after the image is gone.

Photos: the allow-list is image formats, and we're fairly flexible about which ones (jpeg, png, gif, bmp, webp, heic/heif). The re-encode uses Pillow, and we only enable decoders for those same formats. Writing a new JPEG also strips EXIF data, which includes the GPS location that most phone photos have. Uploads over 15 MB or 50 megapixels are rejected.

Files: the allow-list is JPEG, PNG, WebP, HEIC and PDF. Anything else gets a `400` and anything over 10 MB gets a `413`, both before anything is written. Files are stored as they were uploaded, and the type we detected is used as both the object's content type and the `content_type` in the `files` row. Downloads also send `Content-Disposition: attachment` and `X-Content-Type-Options: nosniff`.

The dangerous content type is `image/svg+xml`. SVG is technically an image format, but it's XML and can have a `<script>` in it. If it was served back from a presigned URL, the browser would render it like a page and run the script (`text/html` has the same problem). Neither of our allow-lists has either type, so an SVG photo upload gets rejected. What we store for every photo is `image/jpeg` from the re-encode, never whatever type the client sent.

## Bucket layout

| Prefix | Written by | Read by |
|---|---|---|
| `uploads/pending/{upload_id}` | The client, with a PUT to the presigned `upload_url` | The image worker, once. The worker deletes it whether the upload is accepted or rejected |
| `items/{item_id}/{upload_id}/photo.jpg` | The image worker, after `file -k` passes and the image is decoded and resized | The client, with a GET to the presigned `photo_url` on item responses. Deleted when a newer photo replaces it or the item is hard deleted |
| `users/{user_id}/files/{upload_id}.{ext}` | The API, from `POST /files` and `POST /files/batch`, after the size and type checks | The API, from `GET /files/{id}/content`. Deleted by `DELETE /files/{id}` |

The bucket is private. Every read or write from a client goes through the API or a presigned URL, and we never make a presigned GET for anything in `uploads/pending/`. Every object our own code writes has `upload-id` metadata. The only way to get an object without it is a client's presigned PUT, which is how `scripts/storage_report.py` finds ones that got left behind.

## Write order

There's no transaction that covers both Postgres and the store, so we write in the order where a failure halfway through leaves an object with no row, and never a row that points at nothing. `POST /files` writes the object first and then the row (and tries to delete the objects if the row fails). `DELETE /files/{id}` and the item hard delete remove the row first and then the objects. The image worker writes the new photo before it marks the row `ready`, and only deletes the old photo after that commit. An orphan object costs some storage, but users never see it and the storage report finds it. An orphan row would give out a URL that just errors. The one row we write before its object is the `awaiting_upload` row from when a photo upload link is handed out. It's only a pending record and never produces a URL, so if the upload never shows up, that row is all that's left.

## Presigned flows

Bytes through the API: for a photo, the API only handles two small JSON requests (getting the upload link, then `/complete`) and 0 bytes of the actual photo. `evidence/presigned.txt` shows the PUT going to the store's port and not the gateway's.

Expiry:

- PUT is 10 minutes. The client asks for the link right when the user picks a photo, and a phone photo under our 15 MB limit uploads in a few seconds. Keeping it short means a leaked link is only good for a few minutes, and all it can do is write one object into a staging prefix that the worker checks anyway.
- GET is 1 hour. Every item response makes a fresh `photo_url`, so if one expires, all it takes is fetching the item again. An hour is enough for someone browsing, but it limits how long a link that gets shared around keeps working.

Expired URLs: the store answers an expired URL with a `403` and an XML error. We don't have a front end yet, so this is what the client will need to do, and the API is set up for it. If an image fails to load, the client fetches `GET /items/{id}` again for a new `photo_url`, and if that fails too it shows "Photo unavailable. Refresh to try again." If a PUT fails, it asks `POST /items/{id}/images` for a new link and tries once more, and then shows "Your upload link expired. Please choose the photo again." The user never sees the XML.

Reconciliation: we implemented the completion callback. `POST /items/{item_id}/images/{upload_id}/complete` checks that the object exists before it queues the job. What it doesn't cover is a client that uploads and then never calls `/complete`, like if someone closes the tab. The API never finds out about that upload, the object sits in `uploads/pending/`, and the row stays `awaiting_upload`. The lifecycle rule in `COST_AND_RISK.md` expires that prefix after a day, and the storage report lists anything it finds there. A sweep that cleans up the stale rows would be the next thing we build.

The signed hostname: inside Docker the app reaches the store at `http://storage:9000`, which a browser can't resolve. The hostname is part of the signature, so changing it afterwards breaks the URL. To get around this the storage port has two clients. Every normal call the app makes goes to `S3_ENDPOINT_URL`, and presigned URLs are signed against `S3_PUBLIC_ENDPOINT_URL` (`http://localhost:9000` locally), which is the address the client will actually use. Signing happens locally without any network call, so the app never has to be able to reach that address itself. With a real provider both would be the same public endpoint and we'd just leave `S3_PUBLIC_ENDPOINT_URL` unset.

## Emptying a versioned bucket

In a versioned bucket, deleting an object doesn't actually remove any data. It just puts a delete marker on top, and all of the older versions are still stored and still billed. `list_objects_v2` only shows current versions, so after everything is "deleted" it returns nothing and the bucket looks empty. But trying to delete the bucket fails, because the old versions and the delete markers are all still in there. That's why `empty_bucket()` in `app/ports/storage.py` pages through `list_object_versions` and deletes every version and every delete marker by version id. If it used `list_objects_v2`, our Module 8 teardown would say it worked while every photo we ever replaced was still stored and billed. The bucket delete would fail, and those old versions would keep costing money after the course is over.
