"""Public pricing plans."""
from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import DbSession
from app.models.plan import Plan
from app.schemas.plan import PlanPublic

router = APIRouter(prefix="/plans", tags=["plans"])


@router.get("", response_model=list[PlanPublic])
async def list_plans(db: DbSession) -> list[Plan]:
    result = await db.scalars(
        select(Plan).where(Plan.is_active.is_(True)).order_by(Plan.sort_order)
    )
    return list(result)
