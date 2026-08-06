"""
Staff-only CRUD for everything editorial: services, testimonials, section
copy, and pricing plans. Split from admin.py (which covers clients/
bookings/payments) because this file is about *content*, not people —
keeps each module focused and easy to find.
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.api.deps import DbSession, require_module
from app.models.content import Service, SiteContent, Testimonial
from app.models.plan import Plan
from app.models.user import User
from app.schemas.content import (
    ServiceCreate,
    ServicePublic,
    ServiceUpdate,
    SiteContentPublic,
    SiteContentUpsert,
    TestimonialCreate,
    TestimonialPublic,
    TestimonialUpdate,
)
from app.schemas.plan import PlanPublic
from app.schemas.plan_admin import PlanCreate, PlanUpdate

router = APIRouter(prefix="/admin", tags=["admin-content"])

# Everything in this file — services, testimonials, page copy, pricing
# plans — is what the dashboard's single "Site Content" nav item covers,
# so it all gates on the one "content" module. Defaults closed for
# trainers (see app/core/rbac.py) per the client's explicit request.
ContentAccess = Annotated[User, Depends(require_module("content"))]


# ── Services ─────────────────────────────────────────────────────────────


@router.get("/services", response_model=list[ServicePublic])
async def admin_list_services(_staff: ContentAccess, db: DbSession) -> list[Service]:
    return list(await db.scalars(select(Service).order_by(Service.sort_order)))


@router.post("/services", response_model=ServicePublic, status_code=status.HTTP_201_CREATED)
async def create_service(payload: ServiceCreate, _staff: ContentAccess, db: DbSession) -> Service:
    row = Service(**payload.model_dump())
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


@router.patch("/services/{service_id}", response_model=ServicePublic)
async def update_service(
    service_id: int, payload: ServiceUpdate, _staff: ContentAccess, db: DbSession
) -> Service:
    row = await db.get(Service, service_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    await db.commit()
    await db.refresh(row)
    return row


@router.delete("/services/{service_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_service(service_id: int, _staff: ContentAccess, db: DbSession) -> None:
    row = await db.get(Service, service_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")
    await db.delete(row)
    await db.commit()


# ── Testimonials ─────────────────────────────────────────────────────────


@router.get("/testimonials", response_model=list[TestimonialPublic])
async def admin_list_testimonials(_staff: ContentAccess, db: DbSession) -> list[Testimonial]:
    return list(await db.scalars(select(Testimonial).order_by(Testimonial.sort_order)))


@router.post(
    "/testimonials", response_model=TestimonialPublic, status_code=status.HTTP_201_CREATED
)
async def create_testimonial(
    payload: TestimonialCreate, _staff: ContentAccess, db: DbSession
) -> Testimonial:
    row = Testimonial(**payload.model_dump())
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


@router.patch("/testimonials/{testimonial_id}", response_model=TestimonialPublic)
async def update_testimonial(
    testimonial_id: int, payload: TestimonialUpdate, _staff: ContentAccess, db: DbSession
) -> Testimonial:
    row = await db.get(Testimonial, testimonial_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Testimonial not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    await db.commit()
    await db.refresh(row)
    return row


@router.delete("/testimonials/{testimonial_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_testimonial(testimonial_id: int, _staff: ContentAccess, db: DbSession) -> None:
    row = await db.get(Testimonial, testimonial_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Testimonial not found")
    await db.delete(row)
    await db.commit()


# ── Site content (hero / about / CTA copy) ──────────────────────────────


@router.get("/content", response_model=list[SiteContentPublic])
async def admin_list_content(_staff: ContentAccess, db: DbSession) -> list[SiteContent]:
    return list(await db.scalars(select(SiteContent).order_by(SiteContent.section_key)))


@router.put("/content/{section_key}", response_model=SiteContentPublic)
async def upsert_content(
    section_key: str, payload: SiteContentUpsert, _staff: ContentAccess, db: DbSession
) -> SiteContent:
    """PUT is idempotent and creates-or-replaces — the right verb here since
    a section either exists once or doesn't; there's no meaningful partial
    update on a freeform JSON blob the trainer is editing as a whole form."""
    row = await db.scalar(select(SiteContent).where(SiteContent.section_key == section_key))
    if row is None:
        row = SiteContent(section_key=section_key, data=payload.data)
        db.add(row)
    else:
        row.data = payload.data
    await db.commit()
    await db.refresh(row)
    return row


# ── Pricing plans ────────────────────────────────────────────────────────
# (Public GET /plans already exists in plans.py; this adds the write side
# so pricing is fully editable from the dashboard as required.)


@router.get("/plans", response_model=list[PlanPublic])
async def admin_list_plans(_staff: ContentAccess, db: DbSession) -> list[Plan]:
    return list(await db.scalars(select(Plan).order_by(Plan.sort_order)))


@router.post("/plans", response_model=PlanPublic, status_code=status.HTTP_201_CREATED)
async def create_plan(payload: PlanCreate, _staff: ContentAccess, db: DbSession) -> Plan:
    existing = await db.scalar(select(Plan).where(Plan.slug == payload.slug))
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Slug already in use")
    row = Plan(**payload.model_dump())
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


@router.patch("/plans/{plan_id}", response_model=PlanPublic)
async def update_plan(plan_id: int, payload: PlanUpdate, _staff: ContentAccess, db: DbSession) -> Plan:
    row = await db.get(Plan, plan_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    await db.commit()
    await db.refresh(row)
    return row


@router.delete("/plans/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_plan(plan_id: int, _staff: ContentAccess, db: DbSession) -> None:
    row = await db.get(Plan, plan_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")
    await db.delete(row)
    await db.commit()