"""
Admin media uploads — lets the trainer attach real photos to services,
testimonials, and page sections straight from the dashboard instead of
having to go find and paste an image URL.

The returned URL is built from the incoming request (or PUBLIC_BASE_URL,
if set), so it's correct whether the API is reached over
http://localhost:8000 in local dev or https://api.trainpeakphysique.com
in production — no hardcoded scheme or host.
"""
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile, status

from app.api.deps import require_module
from app.core.config import settings
from app.core.rate_limit import limiter
from app.models.user import User
from app.schemas.media import MediaUploadResponse
from app.services.media_storage import media_storage

router = APIRouter(prefix="/admin/uploads", tags=["admin-media"])

# This endpoint is only ever called from the dashboard's Site Content page
# (services/testimonials/page-section images) — see ImageUploader.jsx —
# so it gates on the same "content" module as admin_content.py.
ContentAccess = Annotated[User, Depends(require_module("content"))]

# Purely organizational — keeps /media/services, /media/testimonials, etc.
# tidy on disk. Reject anything else so `folder` can't be used to write
# outside the expected tree (media_storage also independently guards this).
_ALLOWED_FOLDERS = {"services", "testimonials", "site-content", "misc"}


def _public_base(request: Request) -> str:
    if settings.PUBLIC_BASE_URL:
        return settings.PUBLIC_BASE_URL.rstrip("/")
    return str(request.base_url).rstrip("/")


@router.post("/image", response_model=MediaUploadResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute")
async def upload_image(
    request: Request,
    file: UploadFile,
    _staff: ContentAccess,
    folder: str = Form("misc"),
) -> MediaUploadResponse:
    if folder not in _ALLOWED_FOLDERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown upload folder. Use one of: {', '.join(sorted(_ALLOWED_FOLDERS))}.",
        )

    url_path, rel_path = await media_storage.save(file, folder=folder)
    return MediaUploadResponse(
        url=f"{_public_base(request)}{url_path}",
        path=rel_path,
        content_type=file.content_type or "",
    )