import os
import re

import asyncpg

LIST_TABLES_SQL = """
select table_name
from information_schema.tables
where table_schema = 'public' and table_type = 'BASE TABLE'
order by table_name
"""

DESCRIBE_TABLE_SQL = """
select column_name, data_type, is_nullable, column_default
from information_schema.columns
where table_schema = 'public' and table_name = $1
order by ordinal_position
"""

# Columns the agent should never see — both in `describe_table` (so it
# doesn't know they exist) and stripped from `run_select_query` results
# (so `select *` can't sneak them back in). Keyed by table name.
HIDDEN_COLUMNS: dict[str, set[str]] = {
    "cdramas": {"embedding"},
}

HIDDEN_COLUMN_NAMES: set[str] = {
    name for cols in HIDDEN_COLUMNS.values() for name in cols
}


def is_select(sql: str) -> bool:
    """True if `sql` is a single SELECT/WITH statement and nothing else."""
    stripped = re.sub(r"--[^\n]*", "", sql)
    stripped = re.sub(r"/\*.*?\*/", "", stripped, flags=re.DOTALL).strip()
    if not stripped:
        return False
    if re.search(r";\s*\S", stripped):
        return False
    first = stripped.split(None, 1)[0].lower()
    return first in {"select", "with"}


async def _connect() -> asyncpg.Connection:
    url = os.environ["SUPABASE_DB_URL"]
    return await asyncpg.connect(url, statement_cache_size=0)


async def fetch(sql: str, *args: object) -> list[dict]:
    conn = await _connect()
    try:
        rows = await conn.fetch(sql, *args)
    finally:
        await conn.close()
    return [dict(r) for r in rows]
