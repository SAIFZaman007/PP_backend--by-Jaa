from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class ProgressCreate(BaseModel):
    entry_date: date
    weight_lbs: float | None = Field(default=None, ge=0, le=2000)
    body_fat_pct: float | None = Field(default=None, ge=0, le=100)
    workouts_completed: int | None = Field(default=None, ge=0, le=100)
    notes: str | None = None


class ProgressPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    entry_date: date
    weight_lbs: float | None
    body_fat_pct: float | None
    workouts_completed: int | None
    notes: str | None
    created_at: datetime
