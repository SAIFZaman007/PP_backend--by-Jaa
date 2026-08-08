"""Trainer coaching workspace — Notes, Nutrition Plans, and Workout Plans.

This is what replaced the revenue widget on the Trainer dashboard (see
dashboard_stats in admin.py and Overview.jsx): instead of company
financials, a Trainer's dashboard now surfaces the coaching tools they
actually use day to day. All three record types share the same shape and
the same access rules, so they live together in one file rather than
three near-identical ones:

  * Notes            — a running coaching log per client.
  * Nutrition Plans   — diet guidance + optional macro targets per client.
  * Workout Plans     — training programs per client.

Visibility mirrors the rest of the Clients area: a Trainer only ever sees
records for clients assigned to them (ensure_client_visible); an Admin
sees everyone's, for oversight. Editing/deleting is narrower than
viewing — only the staff member who authored a record (or an Admin) can
change or remove it, so one Trainer never silently rewrites another's
coaching notes on a client who was later reassigned; older entries simply
stay in the client's history as a read-only record of who did what.
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.api.deps import DbSession, ensure_client_visible, require_module
from app.models.client_note import ClientNote
from app.models.nutrition_plan import NutritionPlan
from app.models.user import User, UserRole
from app.models.workout_plan import WorkoutPlan
from app.schemas.client_note import ClientNoteCreate, ClientNotePublic, ClientNoteUpdate
from app.schemas.common import Ok
from app.schemas.nutrition_plan import (
    NutritionPlanCreate,
    NutritionPlanPublic,
    NutritionPlanUpdate,
)
from app.schemas.workout_plan import WorkoutPlanCreate, WorkoutPlanPublic, WorkoutPlanUpdate

router = APIRouter(tags=["coaching"])

# Role Matrix guards for this file — Admins always pass; Trainers default
# to open (see app/core/rbac.py) since these are their own tools.
NotesAccess = Annotated[User, Depends(require_module("notes"))]
NutritionAccess = Annotated[User, Depends(require_module("nutrition"))]
WorkoutsAccess = Annotated[User, Depends(require_module("workouts"))]


async def _get_visible_client(db: DbSession, client_id: int, staff: User) -> User:
    """Loads a client and enforces the same ownership rule used across
    the Clients area — 404 (not 403) so a Trainer probing another
    Trainer's client id can't distinguish "not mine" from "doesn't exist".
    """
    client = await db.get(User, client_id)
    if client is None or client.role != UserRole.client:
        raise HTTPException(status_code=404, detail="Client not found")
    ensure_client_visible(client, staff)
    return client


async def _author_names(db: DbSession, trainer_ids: set[int | None]) -> dict[int, str]:
    """Resolves author display names for a batch of records in one query.

    Records are returned by name rather than by trainer_id alone because a
    Trainer viewing a reassigned client's history may see entries written
    by a colleague they have no other way to look up — /role-matrix/staff
    is Admin-only, so the name has to come from here instead.
    """
    trainer_ids.discard(None)
    if not trainer_ids:
        return {}
    rows = await db.scalars(select(User).where(User.id.in_(trainer_ids)))
    return {u.id: u.full_name for u in rows}


def _ensure_author_or_admin(record_trainer_id: int | None, staff: User) -> None:
    """Edit/delete guard: the original author, or an Admin, only."""
    if staff.role == UserRole.admin:
        return
    if record_trainer_id != staff.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the coach who wrote this entry — or an Admin — can change it.",
        )


# ── Notes ────────────────────────────────────────────────────────────────


@router.get("/notes/client/{client_id}", response_model=list[ClientNotePublic])
async def list_client_notes(
    client_id: int, staff: NotesAccess, db: DbSession
) -> list[ClientNotePublic]:
    await _get_visible_client(db, client_id, staff)
    rows = list(
        await db.scalars(
            select(ClientNote)
            .where(ClientNote.client_id == client_id)
            .order_by(ClientNote.created_at.desc())
        )
    )
    names = await _author_names(db, {r.trainer_id for r in rows})
    return [
        ClientNotePublic(
            id=r.id,
            client_id=r.client_id,
            trainer_id=r.trainer_id,
            trainer_name=names.get(r.trainer_id, "Former coach"),
            content=r.content,
            created_at=r.created_at,
            updated_at=r.updated_at,
        )
        for r in rows
    ]


@router.post("/notes", response_model=ClientNotePublic, status_code=status.HTTP_201_CREATED)
async def create_client_note(
    payload: ClientNoteCreate, staff: NotesAccess, db: DbSession
) -> ClientNotePublic:
    await _get_visible_client(db, payload.client_id, staff)
    note = ClientNote(client_id=payload.client_id, trainer_id=staff.id, content=payload.content)
    db.add(note)
    await db.commit()
    await db.refresh(note)
    return ClientNotePublic(
        id=note.id,
        client_id=note.client_id,
        trainer_id=note.trainer_id,
        trainer_name=staff.full_name,
        content=note.content,
        created_at=note.created_at,
        updated_at=note.updated_at,
    )


@router.patch("/notes/{note_id}", response_model=ClientNotePublic)
async def update_client_note(
    note_id: int, payload: ClientNoteUpdate, staff: NotesAccess, db: DbSession
) -> ClientNotePublic:
    note = await db.get(ClientNote, note_id)
    if note is None:
        raise HTTPException(status_code=404, detail="Note not found")
    await _get_visible_client(db, note.client_id, staff)
    _ensure_author_or_admin(note.trainer_id, staff)
    note.content = payload.content
    await db.commit()
    await db.refresh(note)
    names = await _author_names(db, {note.trainer_id})
    return ClientNotePublic(
        id=note.id,
        client_id=note.client_id,
        trainer_id=note.trainer_id,
        trainer_name=names.get(note.trainer_id, staff.full_name),
        content=note.content,
        created_at=note.created_at,
        updated_at=note.updated_at,
    )


@router.delete("/notes/{note_id}", response_model=Ok)
async def delete_client_note(note_id: int, staff: NotesAccess, db: DbSession) -> Ok:
    note = await db.get(ClientNote, note_id)
    if note is None:
        raise HTTPException(status_code=404, detail="Note not found")
    await _get_visible_client(db, note.client_id, staff)
    _ensure_author_or_admin(note.trainer_id, staff)
    await db.delete(note)
    await db.commit()
    return Ok()


# ── Nutrition plans ─────────────────────────────────────────────────────


def _nutrition_public(row: NutritionPlan, name: str) -> NutritionPlanPublic:
    return NutritionPlanPublic(
        id=row.id,
        client_id=row.client_id,
        trainer_id=row.trainer_id,
        trainer_name=name,
        title=row.title,
        content=row.content,
        calories_target=row.calories_target,
        protein_target_g=row.protein_target_g,
        carbs_target_g=row.carbs_target_g,
        fat_target_g=row.fat_target_g,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get("/nutrition-plans/client/{client_id}", response_model=list[NutritionPlanPublic])
async def list_nutrition_plans(
    client_id: int, staff: NutritionAccess, db: DbSession
) -> list[NutritionPlanPublic]:
    await _get_visible_client(db, client_id, staff)
    rows = list(
        await db.scalars(
            select(NutritionPlan)
            .where(NutritionPlan.client_id == client_id)
            .order_by(NutritionPlan.created_at.desc())
        )
    )
    names = await _author_names(db, {r.trainer_id for r in rows})
    return [_nutrition_public(r, names.get(r.trainer_id, "Former coach")) for r in rows]


@router.post(
    "/nutrition-plans", response_model=NutritionPlanPublic, status_code=status.HTTP_201_CREATED
)
async def create_nutrition_plan(
    payload: NutritionPlanCreate, staff: NutritionAccess, db: DbSession
) -> NutritionPlanPublic:
    await _get_visible_client(db, payload.client_id, staff)
    plan = NutritionPlan(
        client_id=payload.client_id,
        trainer_id=staff.id,
        title=payload.title,
        content=payload.content,
        calories_target=payload.calories_target,
        protein_target_g=payload.protein_target_g,
        carbs_target_g=payload.carbs_target_g,
        fat_target_g=payload.fat_target_g,
    )
    db.add(plan)
    await db.commit()
    await db.refresh(plan)
    return _nutrition_public(plan, staff.full_name)


@router.patch("/nutrition-plans/{plan_id}", response_model=NutritionPlanPublic)
async def update_nutrition_plan(
    plan_id: int, payload: NutritionPlanUpdate, staff: NutritionAccess, db: DbSession
) -> NutritionPlanPublic:
    plan = await db.get(NutritionPlan, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Nutrition plan not found")
    await _get_visible_client(db, plan.client_id, staff)
    _ensure_author_or_admin(plan.trainer_id, staff)
    plan.title = payload.title
    plan.content = payload.content
    plan.calories_target = payload.calories_target
    plan.protein_target_g = payload.protein_target_g
    plan.carbs_target_g = payload.carbs_target_g
    plan.fat_target_g = payload.fat_target_g
    await db.commit()
    await db.refresh(plan)
    names = await _author_names(db, {plan.trainer_id})
    return _nutrition_public(plan, names.get(plan.trainer_id, staff.full_name))


@router.delete("/nutrition-plans/{plan_id}", response_model=Ok)
async def delete_nutrition_plan(plan_id: int, staff: NutritionAccess, db: DbSession) -> Ok:
    plan = await db.get(NutritionPlan, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Nutrition plan not found")
    await _get_visible_client(db, plan.client_id, staff)
    _ensure_author_or_admin(plan.trainer_id, staff)
    await db.delete(plan)
    await db.commit()
    return Ok()


# ── Workout plans ───────────────────────────────────────────────────────


def _workout_public(row: WorkoutPlan, name: str) -> WorkoutPlanPublic:
    return WorkoutPlanPublic(
        id=row.id,
        client_id=row.client_id,
        trainer_id=row.trainer_id,
        trainer_name=name,
        title=row.title,
        content=row.content,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get("/workout-plans/client/{client_id}", response_model=list[WorkoutPlanPublic])
async def list_workout_plans(
    client_id: int, staff: WorkoutsAccess, db: DbSession
) -> list[WorkoutPlanPublic]:
    await _get_visible_client(db, client_id, staff)
    rows = list(
        await db.scalars(
            select(WorkoutPlan)
            .where(WorkoutPlan.client_id == client_id)
            .order_by(WorkoutPlan.created_at.desc())
        )
    )
    names = await _author_names(db, {r.trainer_id for r in rows})
    return [_workout_public(r, names.get(r.trainer_id, "Former coach")) for r in rows]


@router.post(
    "/workout-plans", response_model=WorkoutPlanPublic, status_code=status.HTTP_201_CREATED
)
async def create_workout_plan(
    payload: WorkoutPlanCreate, staff: WorkoutsAccess, db: DbSession
) -> WorkoutPlanPublic:
    await _get_visible_client(db, payload.client_id, staff)
    plan = WorkoutPlan(
        client_id=payload.client_id,
        trainer_id=staff.id,
        title=payload.title,
        content=payload.content,
    )
    db.add(plan)
    await db.commit()
    await db.refresh(plan)
    return _workout_public(plan, staff.full_name)


@router.patch("/workout-plans/{plan_id}", response_model=WorkoutPlanPublic)
async def update_workout_plan(
    plan_id: int, payload: WorkoutPlanUpdate, staff: WorkoutsAccess, db: DbSession
) -> WorkoutPlanPublic:
    plan = await db.get(WorkoutPlan, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Workout plan not found")
    await _get_visible_client(db, plan.client_id, staff)
    _ensure_author_or_admin(plan.trainer_id, staff)
    plan.title = payload.title
    plan.content = payload.content
    await db.commit()
    await db.refresh(plan)
    names = await _author_names(db, {plan.trainer_id})
    return _workout_public(plan, names.get(plan.trainer_id, staff.full_name))


@router.delete("/workout-plans/{plan_id}", response_model=Ok)
async def delete_workout_plan(plan_id: int, staff: WorkoutsAccess, db: DbSession) -> Ok:
    plan = await db.get(WorkoutPlan, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Workout plan not found")
    await _get_visible_client(db, plan.client_id, staff)
    _ensure_author_or_admin(plan.trainer_id, staff)
    await db.delete(plan)
    await db.commit()
    return Ok()