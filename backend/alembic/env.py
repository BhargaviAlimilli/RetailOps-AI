import asyncio
import sys

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context
from app.core.config import Settings
from app.db.models import Base

config = context.config
settings = Settings()
if settings.database_url is None:
    raise RuntimeError("RETAILOPS_DATABASE_URL must be set to run migrations")
url = settings.database_url.get_secret_value()


def run_migrations(connection):
    # LangGraph owns its four explicitly migrated checkpoint tables, not ORM entities.
    def include_object(obj, name, type_, reflected, compare_to):
        return not (
            type_ == "table"
            and name
            in {"checkpoint_migrations", "checkpoints", "checkpoint_blobs", "checkpoint_writes"}
        )

    context.configure(
        connection=connection,
        target_metadata=Base.metadata,
        compare_type=True,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_online():
    engine = create_async_engine(url, poolclass=pool.NullPool, connect_args={"connect_timeout": 5})
    try:
        async with engine.connect() as connection:
            await connection.run_sync(run_migrations)
    finally:
        await engine.dispose()


if context.is_offline_mode():
    context.configure(url=url, target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    loop_factory = asyncio.SelectorEventLoop if sys.platform == "win32" else None
    with asyncio.Runner(loop_factory=loop_factory) as runner:
        runner.run(run_online())
