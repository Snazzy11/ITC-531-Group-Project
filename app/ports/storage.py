"""Storage port. This is the only module that should talk to the object store.
Key layout is explained in milestones/milestone4/STORAGE_DESIGN.md.

Endpoint, bucket, region and credentials all come from env vars (S3_ENDPOINT_URL,
S3_BUCKET, AWS_DEFAULT_REGION, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY) so this
works with any S3-compatible store.

Presigned URLs are signed with S3_PUBLIC_ENDPOINT_URL since the client is the one
using them and the host is part of the signature. Everything else uses
S3_ENDPOINT_URL. If both are the same address just leave the public one unset.

write() adds upload-id metadata to every object. Objects from a client's presigned
PUT won't have it, and the storage report uses that to find them.
"""

import os
from collections.abc import Iterator
from functools import cache
from urllib.parse import quote

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

UPLOAD_URL_SECONDS = 600
PHOTO_URL_SECONDS = 3600

STAMP = "upload-id"


def pending_key(upload_id: str) -> str:
    return f"uploads/pending/{upload_id}"


def photo_key(item_id: int, upload_id: str) -> str:
    return f"items/{item_id}/{upload_id}/photo.jpg"


def item_prefix(item_id: int) -> str:
    return f"items/{item_id}/"


def file_key(user_id: int, upload_id: str, extension: str) -> str:
    return f"users/{user_id}/files/{upload_id}.{extension}"


@cache
def _client(endpoint_url: str | None):
    # A session per client: boto3's shared default session is not thread-safe.
    return boto3.session.Session().client(
        "s3",
        endpoint_url=endpoint_url,
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"} if endpoint_url else {},
            request_checksum_calculation="when_required",
            response_checksum_validation="when_required",
        ),
    )


def _internal():
    return _client(os.environ.get("S3_ENDPOINT_URL"))


def _public():
    return _client(
        os.environ.get("S3_PUBLIC_ENDPOINT_URL") or os.environ.get("S3_ENDPOINT_URL")
    )


def _bucket() -> str:
    return os.environ["S3_BUCKET"]


def bucket_name() -> str:
    return _bucket()


def _is_missing(exc: ClientError) -> bool:
    return exc.response["Error"]["Code"] in ("404", "NoSuchKey", "NoSuchBucket")


def ensure_bucket() -> None:
    try:
        _internal().head_bucket(Bucket=_bucket())
    except ClientError as exc:
        if not _is_missing(exc):
            raise
        _internal().create_bucket(Bucket=_bucket())


def upload_url(key: str) -> str:
    return _public().generate_presigned_url(
        "put_object",
        Params={"Bucket": _bucket(), "Key": key},
        ExpiresIn=UPLOAD_URL_SECONDS,
    )


def download_url(key: str) -> str:
    return _public().generate_presigned_url(
        "get_object",
        Params={"Bucket": _bucket(), "Key": key},
        ExpiresIn=PHOTO_URL_SECONDS,
    )


def exists(key: str) -> bool:
    return metadata(key) is not None


def metadata(key: str) -> dict[str, str] | None:
    """The object's user metadata, or None if there is no such object."""
    try:
        response = _internal().head_object(Bucket=_bucket(), Key=key)
    except ClientError as exc:
        if _is_missing(exc):
            return None
        raise
    return response["Metadata"]


def read(key: str, limit: int) -> bytes | None:
    """Reads up to limit + 1 bytes so the caller can tell if the object is too
    big without downloading the whole thing. Returns None if it doesn't exist."""
    try:
        response = _internal().get_object(Bucket=_bucket(), Key=key)
    except ClientError as exc:
        if _is_missing(exc):
            return None
        raise
    with response["Body"] as body:
        return body.read(limit + 1)


def write(
    key: str,
    data: bytes,
    content_type: str,
    upload_id: str,
    original_name: str | None = None,
) -> None:
    # metadata gets sent as HTTP headers which have to be ASCII, so encode the name
    stamp = {STAMP: upload_id}
    if original_name is not None:
        stamp["original-name"] = quote(original_name)
    _internal().put_object(
        Bucket=_bucket(), Key=key, Body=data, ContentType=content_type, Metadata=stamp
    )


def delete(key: str) -> None:
    _internal().delete_object(Bucket=_bucket(), Key=key)


def list_objects(prefix: str = "") -> Iterator[tuple[str, int]]:
    """(key, size) for every current object under prefix, a page at a time."""
    pages = _internal().get_paginator("list_objects_v2").paginate(
        Bucket=_bucket(), Prefix=prefix
    )
    for page in pages:
        for obj in page.get("Contents", []):
            yield obj["Key"], obj["Size"]


def delete_prefix(prefix: str) -> None:
    for key, _ in list_objects(prefix):
        delete(key)


def empty_bucket() -> int:
    """Deletes every version and delete marker in the bucket and returns how
    many were removed. We can't use list_objects_v2 here because it only shows
    current versions, so on a versioned bucket it can look empty when old
    versions are still there (and still billed)."""
    removed = 0
    pages = _internal().get_paginator("list_object_versions").paginate(Bucket=_bucket())
    for page in pages:
        batch = [
            {"Key": entry["Key"], "VersionId": entry["VersionId"]}
            for entry in page.get("Versions", []) + page.get("DeleteMarkers", [])
        ]
        if batch:
            _internal().delete_objects(
                Bucket=_bucket(), Delete={"Objects": batch, "Quiet": True}
            )
            removed += len(batch)
    return removed
