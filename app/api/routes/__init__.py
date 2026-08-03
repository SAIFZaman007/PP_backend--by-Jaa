"""Aggregate all versioned API routers."""
from fastapi import APIRouter

from app.api.routes import (
    admin,
    auth,
    bookings,
    messages,
    payments,
    plans,
    progress,
    users,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(plans.router)
api_router.include_router(bookings.router)
api_router.include_router(progress.router)
api_router.include_router(payments.router)
api_router.include_router(messages.router)
api_router.include_router(admin.router)
