from datetime import datetime

from pydantic import BaseModel, Field


class WorkoutPlanCreate(BaseModel):
    client_id: int
    title: str = Field(default="Workout Plan", min_length=1, max_length=120)
    content: str = Field(min_length=1, max_length=10_000)


class WorkoutPlanUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    content: str = Field(min_length=1, max_length=10_000)


class WorkoutPlanPublic(BaseModel):
    id: int
    client_id: int
    trainer_id: int | None
    trainer_name: str
    title: str
    content: str
    created_at: datetime
    updated_at: datetime