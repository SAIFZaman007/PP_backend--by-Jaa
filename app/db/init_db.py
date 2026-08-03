"""Create all tables (dev/simple deploys) then seed. Run: python -m app.db.init_db

For production migrations prefer Alembic (see alembic/ and README).
"""
import asyncio
import logging

from app.core.logging import configure_logging
import app.models  # noqa: F401  (registers all models on Base.metadata)
from app.db.base import Base
from app.db.seed import seed
from app.db.session import engine


async def main() -> None:
    configure_logging()
    log = logging.getLogger("peak.init")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    log.info("All tables created.")
    await seed()


if __name__ == "__main__":
    asyncio.run(main())
