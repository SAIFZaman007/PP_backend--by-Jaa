from datetime import datetime

from pydantic import BaseModel, Field


class NutritionPlanCreate(BaseModel):
    client_id: int
    title: str = Field(default="Nutrition Plan", min_length=1, max_length=120)
    content: str = Field(min_length=1, max_length=10_000)
    calories_target: int | None = Field(default=None, ge=0, le=20_000)
    protein_target_g: int | None = Field(default=None, ge=0, le=2_000)
    carbs_target_g: int | None = Field(default=None, ge=0, le=2_000)
    fat_target_g: int | None = Field(default=None, ge=0, le=2_000)


class NutritionPlanUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    content: str = Field(min_length=1, max_length=10_000)
    calories_target: int | None = Field(default=None, ge=0, le=20_000)
    protein_target_g: int | None = Field(default=None, ge=0, le=2_000)
    carbs_target_g: int | None = Field(default=None, ge=0, le=2_000)
    fat_target_g: int | None = Field(default=None, ge=0, le=2_000)


class NutritionPlanPublic(BaseModel):
    id: int
    client_id: int
    trainer_id: int | None
    trainer_name: str
    title: str
    content: str
    calories_target: int | None
    protein_target_g: int | None
    carbs_target_g: int | None
    fat_target_g: int | None
    created_at: datetime
    updated_at: datetime