"""Unit tests for src/sql_tools.py.

`src.sql_tools.fetch` is monkey-patched so no real database is touched. Runs by
default via `uv run pytest`.
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

import pytest

from src import sql_tools
from src.sql_tools import MAX_ROWS, _jsonable, describe_table, run_select_query


def test_jsonable_passes_through_primitives():
    """JSON-native scalars round-trip unchanged."""
    assert _jsonable(1) == 1
    assert _jsonable(1.5) == 1.5
    assert _jsonable("x") == "x"
    assert _jsonable(True) is True
    assert _jsonable(None) is None


def test_jsonable_coerces_decimal_datetime_uuid_to_str():
    """Postgres types asyncpg returns as Python objects (Decimal, datetime, UUID)
    must become strings so json.dumps can serialize them for the model."""
    assert _jsonable(Decimal("3.5")) == "3.5"
    assert _jsonable(datetime(2026, 4, 29, 12, 0, 0)) == "2026-04-29 12:00:00"
    assert (
        _jsonable(UUID("12345678-1234-5678-1234-567812345678"))
        == "12345678-1234-5678-1234-567812345678"
    )


@pytest.fixture
def fake_fetch(monkeypatch):
    """Stub `sql_tools.fetch` to return a fixed list of rows for one test."""

    def _set(rows):
        async def _fetch(sql, *args):
            return rows

        monkeypatch.setattr(sql_tools, "fetch", _fetch)

    return _set


async def test_run_select_query_strips_hidden_columns(fake_fetch):
    """Hidden columns (e.g. cdramas.embedding) are removed from result rows even
    when the user's SELECT * pulled them back from the DB."""
    fake_fetch([{"id": 1, "title": "Drama", "embedding": [0.1, 0.2]}])
    out = await run_select_query("select * from cdramas")
    assert "embedding" not in out
    assert "Drama" in out


async def test_run_select_query_rejects_non_select():
    """The tool refuses anything that isn't a SELECT/WITH — second line of
    defense after the agent_readonly DB role."""
    out = await run_select_query("delete from cdramas")
    assert "only a single SELECT" in out


async def test_run_select_query_truncates_at_max_rows(fake_fetch):
    """Oversized result sets are capped at MAX_ROWS with a visible suffix so the
    model knows the data was truncated."""
    fake_fetch([{"id": i} for i in range(MAX_ROWS + 50)])
    out = await run_select_query("select id from t")
    assert f"(showing first {MAX_ROWS} of {MAX_ROWS + 50} rows)" in out


async def test_describe_table_hides_embedding(fake_fetch):
    """describe_table omits hidden columns from the schema markdown so the model
    never learns the embedding column exists."""
    fake_fetch(
        [
            {"column_name": "id", "data_type": "integer", "is_nullable": "NO", "column_default": None},
            {"column_name": "title", "data_type": "text", "is_nullable": "YES", "column_default": None},
            {"column_name": "embedding", "data_type": "vector", "is_nullable": "YES", "column_default": None},
        ]
    )
    out = await describe_table("cdramas")
    assert "embedding" not in out
    assert "id" in out
    assert "title" in out
