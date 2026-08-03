"""Public, read-only content endpoints for the marketing site.

All write access lives under /admin/* (staff-only) in admin.py — this
module is intentionally GET-only so it never needs auth or rate limiting
beyond what's already global.
"""
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import DbSession
from app.models.content import Service, SiteContent, Testimonial
from app.schemas.content import ServicePublic, SiteContentPublic, TestimonialPublic

router = APIRouter(tags=["content"])


@router.get("/services", response_model=list[ServicePublic])
async def list_services(db: DbSession) -> list[Service]:
    result = await db.scalars(
        select(Service).where(Service.is_active.is_(True)).order_by(Service.sort_order)
    )
    return list(result)


@router.get("/testimonials", response_model=list[TestimonialPublic])
async def list_testimonials(db: DbSession) -> list[Testimonial]:
    result = await db.scalars(
        select(Testimonial)
        .where(Testimonial.is_active.is_(True))
        .order_by(Testimonial.sort_order)
    )
    return list(result)


@router.get("/content/{section_key}", response_model=SiteContentPublic)
async def get_content(section_key: str, db: DbSession) -> SiteContent:
    row = await db.scalar(select(SiteContent).where(SiteContent.section_key == section_key))
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found")
    return row