"""Peak Physique API — application factory & entrypoint."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.routes import api_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.core.rate_limit import limiter
from app.services.media_storage import media_storage

logger = logging.getLogger("peak")


class UnhandledErrorMiddleware:

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        response_started = False

        async def _send(message):
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, receive, _send)
        except Exception:
            logger.exception("Unhandled error on %s %s", scope.get("method"), scope.get("path"))
            if response_started:
                # Response already partway sent — nothing safe to do but
                # let the connection drop; re-sending would corrupt it.
                raise
            response = JSONResponse(status_code=500, content={"detail": "Internal server error"})
            await response(scope, receive, send)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging("INFO")
    logger.info("Starting %s (env=%s)", settings.PROJECT_NAME, settings.ENVIRONMENT)
    # Zero-config convenience: auto-create tables when using SQLite for local dev.
    if settings.DATABASE_URL.startswith("sqlite"):
        import app.models  # noqa: F401
        from app.db.base import Base
        from app.db.session import engine

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("SQLite tables ensured (dev mode).")
    yield
    logger.info("Shutting down %s", settings.PROJECT_NAME)


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    openapi_url="/openapi.json",
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(UnhandledErrorMiddleware)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(api_router, prefix=settings.API_V1_PREFIX)

# Admin-uploaded media (service photos, testimonial avatars, page images).
app.mount(settings.MEDIA_URL_PATH, StaticFiles(directory=settings.MEDIA_ROOT), name="media")


@app.get("/health", tags=["meta"])
async def health() -> dict:
    return {"status": "ok", "service": settings.PROJECT_NAME}


@app.get("/", tags=["meta"])
async def root() -> dict:
    return {
        "name": settings.PROJECT_NAME,
        "docs": "/docs",
        "api": settings.API_V1_PREFIX,
    }