import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.exc import OperationalError

from app.core.config import Settings
from app.db.session import Database


def make_database():
    return Database(Settings(_env_file=None, database_url=None, database_timeout_seconds=0.01))


@pytest.mark.parametrize(
    "error", [OperationalError("SELECT 1", {}, Exception("private")), OSError()]
)
def test_database_failure_returns_false_without_leaking_details(error, caplog):
    database = make_database()
    database.engine = MagicMock()
    database.engine.connect.side_effect = error
    assert asyncio.run(database.is_ready()) is False
    assert "private" not in caplog.text


def test_database_probe_has_a_deadline():
    database = make_database()
    database.engine = MagicMock()
    context = AsyncMock()
    database.engine.connect.return_value = context

    async def slow_connect():
        await asyncio.sleep(1)

    context.__aenter__.side_effect = slow_connect
    assert asyncio.run(database.is_ready()) is False


def test_database_probe_executes_a_query():
    database = make_database()
    database.engine = MagicMock()
    connection = AsyncMock()
    database.engine.connect.return_value = AsyncMock()
    database.engine.connect.return_value.__aenter__.return_value = connection
    assert asyncio.run(database.is_ready()) is True
    connection.execute.assert_awaited_once()
