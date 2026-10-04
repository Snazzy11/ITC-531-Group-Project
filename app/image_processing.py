"""Turns an untrusted upload into the one photo we store.

detect_type() is the gate; reencode() decodes with Pillow and writes a fresh
JPEG, so nothing but pixels survives (no EXIF/GPS, no trailing bytes).
"""

import io
import subprocess

from PIL import Image, ImageOps
from pillow_heif import register_heif_opener

register_heif_opener()

MAX_UPLOAD_BYTES = 15 * 1024 * 1024
MAX_PIXELS = 50_000_000
MAX_EDGE = 1280
JPEG_QUALITY = 80

ALLOWED_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/bmp",
    "image/x-ms-bmp",
    "image/webp",
    "image/heic",
    "image/heif",
}
DECODERS = ["JPEG", "PNG", "GIF", "BMP", "WEBP", "HEIF"]

# `file -k` falls through to this catch-all on most inputs; it says nothing
# about what the bytes are.
GENERIC_TYPES = {"application/octet-stream"}


class Rejected(Exception):
    """The upload will not be stored. The message is shown to the client."""


def check_size(data: bytes) -> None:
    if len(data) > MAX_UPLOAD_BYTES:
        raise Rejected(f"the file is larger than {MAX_UPLOAD_BYTES // 2**20} MB")


def detect_type(data: bytes) -> str:
    """Every rule `file -k` matches has to be an allowed image type. Plain
    `file` stops at the first match, which lets a polyglot (bytes that are an
    image and also something else) through. Data appended after an image
    still passes; reencode() is what drops it."""
    output = subprocess.run(
        ["file", "-k", "-b", "-r", "--mime-type", "-"],
        input=data,
        capture_output=True,
        check=True,
        timeout=10,
    ).stdout.decode()
    matches = [line.removeprefix("- ").strip() for line in output.splitlines()]
    matches = [m for m in matches if m and m not in GENERIC_TYPES]
    if not matches:
        raise Rejected("the file is not a recognized image")
    for match in matches:
        if match not in ALLOWED_TYPES:
            raise Rejected(f"{match} is not an allowed image type")
    return matches[0]


def reencode(data: bytes) -> bytes:
    try:
        with Image.open(io.BytesIO(data), formats=DECODERS) as image:
            if image.width * image.height > MAX_PIXELS:
                raise Rejected("the image dimensions are too large")
            image.thumbnail((MAX_EDGE, MAX_EDGE))
            photo = _flatten(ImageOps.exif_transpose(image))
    except Rejected:
        raise
    except Image.DecompressionBombError:
        raise Rejected("the image dimensions are too large") from None
    except Exception:
        # Decoders raise many different exception types on malformed input.
        raise Rejected("the file could not be read as an image") from None

    out = io.BytesIO()
    photo.save(out, "JPEG", quality=JPEG_QUALITY, optimize=True)
    return out.getvalue()


def _flatten(image: Image.Image) -> Image.Image:
    """JPEG has no transparency; put transparent images on white instead of
    letting convert() turn the transparent areas black."""
    if image.mode in ("RGBA", "LA", "PA") or "transparency" in image.info:
        rgba = image.convert("RGBA")
        background = Image.new("RGB", rgba.size, "white")
        background.paste(rgba, mask=rgba.getchannel("A"))
        return background
    return image.convert("RGB")
