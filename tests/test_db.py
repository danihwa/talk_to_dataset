"""Unit tests for the SELECT-only guard and hidden-column constants in src/db.py.

Pure functions only — no DB connection, no API calls. Runs by default via
`uv run pytest`.
"""

import pytest

from src.db import HIDDEN_COLUMN_NAMES, HIDDEN_COLUMNS, is_select


def test_hidden_columns_includes_embedding():
    """cdramas.embedding must be in the hidden-column registry so describe_table
    and run_select_query strip it before the model sees it."""
    assert "embedding" in HIDDEN_COLUMNS.get("cdramas", set())
    assert "embedding" in HIDDEN_COLUMN_NAMES


@pytest.mark.parametrize(
    "sql",
    [
        "select 1",
        "SELECT * FROM cdramas",
        "  select id from t  ",
        "with a as (select 1) select * from a",
        "WITH x AS (SELECT 1) SELECT * FROM x;",
        "-- a comment\nselect 1",
        "/* block */ select 1",
    ],
)
def test_is_select_accepts(sql: str):
    """is_select tolerates whitespace, line/block comments, mixed case, CTEs,
    and a trailing semicolon — anything that's still one SELECT statement."""
    assert is_select(sql)


@pytest.mark.parametrize(
    "sql",
    [
        "",
        "   ",
        "update cdramas set title='x'",
        "delete from cdramas",
        "drop table cdramas",
        "insert into t values (1)",
        "select 1; drop table t",
        "select 1; select 2",
        "-- only a comment",
    ],
)
def test_is_select_rejects(sql: str):
    """is_select rejects writes, multi-statement input, and empty/comment-only SQL."""
    assert not is_select(sql)
