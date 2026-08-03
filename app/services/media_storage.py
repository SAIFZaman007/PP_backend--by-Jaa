"""
Storage abstraction for admin-uploaded media (service photos, testimonial
avatars, hero/about imagery, the training-focus strip, etc).

Ships with a local-disk implementation that's zero-config for development
and small/medium production deployments. Swapping to S3 / GCS / Azure Blob
later means adding one more class here that implements `save()` /
`delete()` — nothing in the API route or the dashboard needs to change,
since both only ever talk to the `media_storage` object below.

Security notes (why this file looks stricter than "just save the bytes"):
  - The Content-Type header the browser sends can't be trusted on its own —
    it's client-supplied. Pillow actually opening and re-encoding the file
    is what proves it's a genuine image and not, say, an HTML/SVG payload
    or a polyglot file wearing a .jpg extension.
  - Re-encoding also strips EXIF/GPS metadata and anything appended after
    the image data — a common way arbitrary bytes get smuggled through
    naive "upload" endpoints.
  - Filenames are always a fresh UUID — the original filename is never
    trusted or reused, which rules out path traversal and collisions.
  - Images are capped at MAX_DIMENSION on the long edge, keeping storage
    and page-load costs predictable regardless of what the admin uploads.
"""
from __future__ import annotations

import io
import logging
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from PIL import Image, UnidentifiedImageError

from app.core.config import settings

logger = logging.getLogger("peak.media")

# Content-Type -> (Pillow format, file extension). Deliberately small and
# explicit rather than "whatever Pillow can open" — keeps the accepted
# surface area (and therefore the re-encoder's attack surface) minimal.
_ALLOWED: dict[str, tuple[str, str]] = {
    "image/jpeg": ("JPEG", "jpg"),
    "image/png": ("PNG", "png"),
    "image/webp": ("WEBP", "webp"),
}
MAX_DIMENSION = 2000  # px, longest edge — plenty for a full-bleed hero image


class MediaStorage(ABC):
    @abstractmethod
    async def save(self, upload: UploadFile, *, folder: str) -> tuple[str, str]:
        """Validates, re-encodes, and persists an uploaded image.

        Returns (url_path, relative_path) where `url_path` is rooted at
        MEDIA_URL_PATH (e.g. "/media/services/2026/08/abc123.jpg") and
        `relative_path` is the storage-relative path used for deletion.
        """

    @abstractmethod
    def delete(self, relative_path: str) -> None: ...


class LocalMediaStorage(MediaStorage):
    """Saves to disk under MEDIA_ROOT, served back via FastAPI's
    StaticFiles at MEDIA_URL_PATH (see main.py). Good for a single-server
    deployment; for multi-instance production at real scale, add an
    `S3MediaStorage` implementing the same interface and swap it in via
    one line at the bottom of this file."""

    def __init__(self, root: str | Path, url_path: str) -> None:
        self.root = Path(root)
        self.url_path = url_path.rstrip("/")
        self.root.mkdir(parents=True, exist_ok=True)

    async def save(self, upload: UploadFile, *, folder: str) -> tuple[str, str]:
        content_type = (upload.content_type or "").lower()
        if content_type not in _ALLOWED:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="Only JPEG, PNG, or WEBP images are allowed.",
            )

        max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
        raw = await upload.read(max_bytes + 1)  # +1 so we can detect "over the limit"
        if len(raw) > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Image must be under {settings.MAX_UPLOAD_MB}MB.",
            )
        if not raw:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file.")

        # Real validation: verify() proves it decodes as an image at all;
        # we then reopen (verify() leaves the parser unusable) to actually
        # process and re-save it, which is what strips any non-image
        # payload and metadata riding along with the pixels.
        try:
            probe = Image.open(io.BytesIO(raw))
            probe.verify()
            img = Image.open(io.BytesIO(raw))
            img.load()
        except (UnidentifiedImageError, OSError) as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="That file isn't a valid image.",
            ) from exc

        fmt, ext = _ALLOWED[content_type]
        if fmt == "JPEG" and img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        elif fmt != "PNG" and img.mode == "P":
            img = img.convert("RGBA")

        img.thumbnail((MAX_DIMENSION, MAX_DIMENSION))

        today = datetime.now(timezone.utc)
        safe_folder = "".join(c for c in folder if c.isalnum() or c in ("-", "_")) or "misc"
        rel_dir = Path(safe_folder) / f"{today:%Y}" / f"{today:%m}"
        (self.root / rel_dir).mkdir(parents=True, exist_ok=True)

        filename = f"{uuid.uuid4().hex}.{ext}"
        rel_path = rel_dir / filename
        save_kwargs = {"quality": 85, "optimize": True} if fmt == "JPEG" else {"optimize": True}
        img.save(self.root / rel_path, format=fmt, **save_kwargs)

        logger.info("Stored upload %s (%d bytes -> %s)", filename, len(raw), rel_path)
        return f"{self.url_path}/{rel_path.as_posix()}", rel_path.as_posix()

    def delete(self, relative_path: str) -> None:
        target = (self.root / relative_path).resolve()
        if self.root.resolve() not in target.parents:
            return  # refuse to touch anything outside MEDIA_ROOT
        target.unlink(missing_ok=True)


# Single shared instance the routes import. Swap the class here (not the
# call sites) when moving to cloud storage.
media_storage: MediaStorage = LocalMediaStorage(settings.MEDIA_ROOT, settings.MEDIA_URL_PATH)