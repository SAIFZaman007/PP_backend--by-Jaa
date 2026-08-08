"""
Aggregate all versioned API routers.
"""
from fastapi import APIRouter

from app.api.routes import (
    admin,
    admin_content,
    auth,
    bookings,
    chat,
    coaching,
    content,
    messages,
    payments,
    plans,
    progress,
    role_matrix,
    uploads,
    users,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(plans.router)
api_router.include_router(chat.router)
api_router.include_router(content.router)
api_router.include_router(admin_content.router)
api_router.include_router(uploads.router)
api_router.include_router(bookings.router)
api_router.include_router(progress.router)
api_router.include_router(payments.router)
api_router.include_router(messages.router)
api_router.include_router(admin.router)
api_router.include_router(role_matrix.router)
api_router.include_router(coaching.router)