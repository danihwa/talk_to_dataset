import pytest

from src.db import HIDDEN_COLUMN_NAMES, HIDDEN_COLUMNS, is_select


def test_hidden_columns_includes_embedding():
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
    assert not is_select(sql)
