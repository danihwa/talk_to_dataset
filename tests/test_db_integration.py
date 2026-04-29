"""Live-DB safety check. The headline claim of this project is that the DB role
itself can't write — this test pins that down by attempting a real DELETE
against the live database and asserting Postgres rejects it.

Requires SUPABASE_DB_URL. Skipped (and deselected by default) otherwise.

Run with: `uv run pytest -m live_db`
"""

import os

import asyncpg
import pytest

from src.db import _connect

pytestmark = [
    pytest.mark.live_db,
    pytest.mark.skipif(
        not os.environ.get("SUPABASE_DB_URL"),
        reason="SUPABASE_DB_URL not set",
    ),
]


async def test_readonly_role_rejects_destructive_sql():
    """Layer-1 safety: the agent_readonly role can SELECT but nothing else."""
    conn = await _connect()
    try:
        row = await conn.fetchrow(
            "select table_name from information_schema.tables "
            "where table_schema='public' and table_type='BASE TABLE' limit 1"
        )
        assert row is not None, "no public-schema tables to test against"
        table = row["table_name"]
        with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
            await conn.execute(f'delete from "{table}"')
    finally:
        await conn.close()
