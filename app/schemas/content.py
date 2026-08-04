from pydantic import BaseModel, ConfigDict, Field

# ── Service ──────────────────────────────────────────────────────────────


class ServicePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    icon: str
    name: str
    price_label: str
    price_suffix: str
    price_cents: int
    description: str
    image_url: str | None
    is_featured: bool
    is_purchasable: bool
    sort_order: int


class ServiceCreate(BaseModel):
    icon: str = Field(default="Dumbbell", max_length=40)
    name: str = Field(min_length=1, max_length=120)
    price_label: str = Field(min_length=1, max_length=40)
    price_suffix: str = Field(default="starting", max_length=30)
    price_cents: int = Field(default=0, ge=0)
    description: str = Field(min_length=1)
    image_url: str | None = None
    is_featured: bool = False
    is_active: bool = True
    is_purchasable: bool = True
    sort_order: int = 0


class ServiceUpdate(BaseModel):
    icon: str | None = Field(default=None, max_length=40)
    name: str | None = Field(default=None, max_length=120)
    price_label: str | None = Field(default=None, max_length=40)
    price_suffix: str | None = Field(default=None, max_length=30)
    price_cents: int | None = Field(default=None, ge=0)
    description: str | None = None
    image_url: str | None = None
    is_featured: bool | None = None
    is_active: bool | None = None
    is_purchasable: bool | None = None
    sort_order: int | None = None


# ── Testimonial ──────────────────────────────────────────────────────────


class TestimonialPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    role: str
    quote: str
    rating: int
    result_tag: str | None
    avatar_url: str | None
    sort_order: int


class TestimonialCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    role: str = Field(default="", max_length=160)
    quote: str = Field(min_length=1)
    rating: int = Field(default=5, ge=1, le=5)
    result_tag: str | None = Field(default=None, max_length=60)
    avatar_url: str | None = None
    is_active: bool = True
    sort_order: int = 0


class TestimonialUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    role: str | None = Field(default=None, max_length=160)
    quote: str | None = None
    rating: int | None = Field(default=None, ge=1, le=5)
    result_tag: str | None = Field(default=None, max_length=60)
    avatar_url: str | None = None
    is_active: bool | None = None
    sort_order: int | None = None


# ── SiteContent ──────────────────────────────────────────────────────────


class SiteContentPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    section_key: str
    data: dict


class SiteContentUpsert(BaseModel):
    data: dict