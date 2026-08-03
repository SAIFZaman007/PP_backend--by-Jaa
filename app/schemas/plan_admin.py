from pydantic import BaseModel, Field

from app.models.plan import BillingInterval


class PlanCreate(BaseModel):
    slug: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=80)
    tagline: str | None = Field(default=None, max_length=160)
    price_cents: int = Field(ge=0)
    interval: BillingInterval = BillingInterval.month
    features: list[str] = Field(default_factory=list)
    stripe_price_id: str | None = None
    is_featured: bool = False
    is_active: bool = True
    sort_order: int = 0


class PlanUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=80)
    tagline: str | None = Field(default=None, max_length=160)
    price_cents: int | None = Field(default=None, ge=0)
    interval: BillingInterval | None = None
    features: list[str] | None = None
    stripe_price_id: str | None = None
    is_featured: bool | None = None
    is_active: bool | None = None
    sort_order: int | None = None