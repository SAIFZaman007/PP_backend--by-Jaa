"""Peak Physique API — application factory & entrypoint."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.routes import api_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.core.rate_limit import limiter

logger = logging.getLogger("peak")


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
