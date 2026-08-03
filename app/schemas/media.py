from pydantic import BaseModel


class MediaUploadResponse(BaseModel):
    """What the dashboard gets back after a successful image upload —
    `url` is what gets written straight into image_url/avatar_url fields."""

    url: str
    path: str
    content_type: str