from pydantic import BaseModel, ConfigDict

from app.models.plan import BillingInterval


class PlanPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    slug: str
    name: str
    tagline: str | None
    price_cents: int
    interval: BillingInterval
    features: list
    is_featured: bool
    sort_order: int
