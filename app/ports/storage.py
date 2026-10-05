"""The storage port: the only module that talks to the object store. Key
layout is in milestones/milestone4/STORAGE_DESIGN.md.

The endpoint, bucket, region and credentials all come from the environment
(S3_ENDPOINT_URL, S3_BUCKET, AWS_DEFAULT_REGION, AWS_ACCESS_KEY_ID,
AWS_SECRET_ACCESS_KEY), so the same code runs against any S3-compatible store.

Presigned URLs are signed against S3_PUBLIC_ENDPOINT_URL because the client
uses them, not this container, and the host is part of the signature. Every
other call goes to S3_ENDPOINT_URL. When the app and its clients reach the
store at the same address, leave S3_PUBLIC_ENDPOINT_URL unset.

Every object written through write() is stamped with upload-id metadata. The
only objects without it are ones a client PUT to a presigned URL, which is how
scripts/storage_report.py tells them apart.
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
    """Reads at most limit + 1 bytes, so the caller can tell the object is too
    big without downloading all of it. None if there is no such object."""
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
    # Metadata travels as HTTP headers, which must be ASCII, so the name is
    # percent-encoded.
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
    """Deletes every version of every object and every delete marker, and
    returns how many it removed. list_objects_v2 only sees current versions:
    on a versioned bucket it can come back empty while old versions are still
    stored and billed, and the bucket still refuses to be deleted."""
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
