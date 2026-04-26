import json

from agents import Agent, Runner, function_tool

from src.db import (
    DESCRIBE_TABLE_SQL,
    HIDDEN_COLUMN_NAMES,
    HIDDEN_COLUMNS,
    LIST_TABLES_SQL,
    fetch,
    is_select,
)
from src.prompts import SYSTEM_INSTRUCTIONS

MAX_ROWS = 200


@function_tool
async def list_tables() -> str:
    """List the base tables in the public schema."""
    rows = await fetch(LIST_TABLES_SQL)
    if not rows:
        return "(no tables in public schema)"
    return "\n".join(r["table_name"] for r in rows)


@function_tool
async def describe_table(name: str) -> str:
    """Describe the columns of a public-schema table.

    Args:
        name: The table name (in the public schema).
    """
    rows = await fetch(DESCRIBE_TABLE_SQL, name)
    if not rows:
        return f"Table {name!r} not found in public schema."
    hidden = HIDDEN_COLUMNS.get(name, set())
    visible = [r for r in rows if r["column_name"] not in hidden]
    header = "| column | type | nullable | default |\n| --- | --- | --- | --- |"
    body = "\n".join(
        f"| {r['column_name']} | {r['data_type']} | {r['is_nullable']} | {r['column_default'] or ''} |"
        for r in visible
    )
    return f"{header}\n{body}"


@function_tool
async def run_select_query(sql: str) -> str:
    """Run a single read-only SELECT (or WITH ... SELECT) query and return rows as JSON.

    Args:
        sql: One SELECT statement. INSERT/UPDATE/DELETE and multi-statement input are rejected.
    """
    if not is_select(sql):
        return "Error: only a single SELECT or WITH ... SELECT statement is allowed."
    try:
        rows = await fetch(sql)
    except Exception as exc:
        return f"Error: {exc}"
    truncated = len(rows) > MAX_ROWS
    payload = [
        {k: _jsonable(v) for k, v in r.items() if k not in HIDDEN_COLUMN_NAMES}
        for r in rows[:MAX_ROWS]
    ]
    out = json.dumps(payload, ensure_ascii=False, default=str)
    if truncated:
        out += f"\n(showing first {MAX_ROWS} of {len(rows)} rows)"
    return out


def _jsonable(value: object) -> object:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


async def run_question(
    question: str, history: list | None = None
) -> tuple[str, list]:
    agent = Agent(
        name="SQL Analyst",
        instructions=SYSTEM_INSTRUCTIONS,
        tools=[list_tables, describe_table, run_select_query],
        model="gpt-4o-mini",
    )
    if history:
        input_items = history + [{"role": "user", "content": question}]
    else:
        input_items = question
    result = await Runner.run(agent, input=input_items, max_turns=10)
    return result.final_output, result.to_input_list()
