"""Object storage for item photos. Key layout is in docs/STORAGE_DESIGN.md.

Presigned URLs are signed against S3_PUBLIC_ENDPOINT_URL because the client
uses them, not this container, and the host is part of the signature. Every
other call goes to S3_ENDPOINT_URL. With real AWS S3, leave both unset.
"""

import os
from functools import cache

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

UPLOAD_URL_SECONDS = 600
PHOTO_URL_SECONDS = 3600


def pending_key(upload_id: str) -> str:
    return f"uploads/pending/{upload_id}"


def photo_key(item_id: int, upload_id: str) -> str:
    return f"items/{item_id}/{upload_id}/photo.jpg"


def item_prefix(item_id: int) -> str:
    return f"items/{item_id}/"


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
    try:
        _internal().head_object(Bucket=_bucket(), Key=key)
    except ClientError as exc:
        if _is_missing(exc):
            return False
        raise
    return True


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


def write(key: str, data: bytes, content_type: str) -> None:
    _internal().put_object(Bucket=_bucket(), Key=key, Body=data, ContentType=content_type)


def delete(key: str) -> None:
    _internal().delete_object(Bucket=_bucket(), Key=key)


def delete_prefix(prefix: str) -> None:
    pages = _internal().get_paginator("list_objects_v2").paginate(
        Bucket=_bucket(), Prefix=prefix
    )
    for page in pages:
        for obj in page.get("Contents", []):
            delete(obj["Key"])
