import asyncio

import structlog
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.core.config import Settings

logger = structlog.get_logger(__name__)


class Database:
    def __init__(self, settings: Settings):
        self.timeout = settings.database_timeout_seconds
        self.engine: AsyncEngine | None = None
        if settings.database_url is not None:
            url = make_url(settings.database_url.get_secret_value())
            options = str(url.query.get("options", ""))
            self.engine = create_async_engine(
                url,
                pool_pre_ping=True,
                pool_size=5,
                max_overflow=5,
                pool_timeout=self.timeout,
                connect_args={
                    "connect_timeout": max(1, int(self.timeout)),
                    "options": options + f" -cstatement_timeout={max(1, int(self.timeout * 1000))}",
                },
            )

    async def is_ready(self) -> bool:
        if self.engine is None:
            return False
        try:
            async with asyncio.timeout(self.timeout), self.engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
            return True
        except (SQLAlchemyError, OSError, TimeoutError) as error:
            # Log the category only: driver errors may contain credentials or hostnames.
            logger.warning("database_unavailable", error_type=type(error).__name__)
            return False

    async def close(self) -> None:
        if self.engine is not None:
            await self.engine.dispose()
