# text-to-sql

A natural-language data Q&A agent built with the OpenAI Agents SDK, pointed at a **Supabase** Postgres database. Ask questions in English or Czech, and the agent inspects the schema, writes a `SELECT`, runs it via a local MCP server, and replies with the answer plus the SQL it ran.

The agent connects with a dedicated read-only Postgres role, so it physically cannot write to the database — even if the model misbehaves.

## Setup

Prerequisites:
- Python 3.12
- [uv](https://docs.astral.sh/uv/)
- An OpenAI API key
- A Supabase project with at least one table in the `public` schema

```bash
uv sync
cp .env.example .env
```

Then, **once per Supabase project**, create the read-only role:

1. Open your project's SQL editor in Supabase Studio.
2. Open `supabase/setup_readonly_role.sql`, replace `CHANGE_ME_BEFORE_RUNNING` with a strong password, paste, and run.
3. In Studio, click **Connect** → **Transaction pooler** and copy the URI. Replace the username with `agent_readonly.<project-ref>` and substitute the password you just set.
4. Put `OPENAI_API_KEY` and `SUPABASE_DB_URL` into `~/secrets/.env` (preferred) or the local `.env`.

## Usage

### CLI

```bash
uv run python -m src.cli "list the tables you can see"
```

One question per invocation; the answer prints to stdout with the SQL the agent ran appended in a fenced code block.

### Streamlit UI

```bash
uv run streamlit run app.py
```

The sidebar shows which Supabase project you're connected to. Type questions in the chat input.

### MCP server

The agent already uses `src/mcp_server.py` under the hood (CLI and Streamlit both spawn it), so you don't need to start it manually. But because it's a normal stdio MCP server, any other MCP client can connect to it too — useful for poking at the tools without an LLM in the loop:

```bash
uv run mcp dev src/mcp_server.py:mcp             # MCP Inspector (browser UI)
```

Or wire it into Claude Desktop via `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "text-to-sql": {
      "command": "uv",
      "args": ["--directory", "/abs/path/to/text_to_sql_data", "run", "python", "-m", "src.mcp_server"],
      "env": { "SUPABASE_DB_URL": "postgres://agent_readonly..." }
    }
  }
}
```

#### Manual smoke checklist

1. Ask "list the tables you can see" — agent calls `list_tables`, names match Supabase Studio.
2. Ask a row-count question against one of your tables — verify answer + SQL.
3. Ask a question in Czech — answer comes back in Czech.
4. Ask "what's the weather?" — agent declines without calling tools.
5. Ask "delete all rows from <table>" — nothing changes; confirm in Supabase Studio.
6. Click **Clear chat** — history empties, connection stays.

## How it works

```
your question
     │
     ▼
┌─────────────────────────────┐
│  SQL Analyst agent          │   MCP tools (only read paths exist):
│  - inspects schema          │     • list_tables
│  - writes a SELECT          │     • describe_table(name)
│  - runs it via asyncpg      │     • run_select_query(sql)
│  - retries on SQL error     │            ▲
│  - formats the answer       │            │ stdio (MCP)
└─────────────────────────────┘            │
     │                              ┌──────┴───────────┐
     ▼                              │ src/mcp_server.py│ (subprocess)
   answer + SQL                     └──────────────────┘
```

The OpenAI Agents SDK runs an internal model-tool loop: the model decides whether to call a tool or return a final answer. If a query errors, the error goes back into the model's context and it tries again. The loop is capped by `max_turns=10` so a buggy run can't spiral.

The agent doesn't import the tool functions in-process. On every turn it spawns `src/mcp_server.py` as a subprocess and consumes the three tools over the [Model Context Protocol](https://modelcontextprotocol.io/). The server is a thin FastMCP wrapper around `src/sql_tools.py`, where the actual work happens — opening a fresh `asyncpg` connection to Supabase using the read-only role's URI, running one query against `information_schema` or the user's data, and returning JSON or markdown.

## Read-only safety

Three layers, in order of who enforces what:

1. **Database role (Postgres-enforced):** the connection uses the `agent_readonly` role, which has only `SELECT` on `public`. A `DELETE` would fail with `permission denied for table` regardless of what the agent or the tool layer does.
2. **Tool layer (code-enforced):** only `list_tables`, `describe_table`, and `run_select_query` exist as tools. `run_select_query` additionally rejects anything whose first non-comment token isn't `SELECT`/`WITH`, and rejects multi-statement input.
3. **System prompt (advisory):** still tells the agent to write SELECT only and decline off-topic questions.

The bottom layer is the one that actually matters — the others just keep the model on the happy path.

## Not production-grade

This is a portfolio project. Things I'd do differently for production:

- `agent_readonly` is created with `BYPASSRLS` for simplicity. For a real multi-tenant app, drop that line and write RLS policies — otherwise the agent can read every row in every table regardless of ownership.
- Schema fits in a single prompt because the demo DB is small. At ~100 tables you'd need schema embedding + retrieval rather than dumping the whole schema.
- Result sets larger than 200 rows are truncated. A real app would paginate or summarize server-side.
- No adversarial-input hardening beyond the read-only enforcement above. Don't point this at a database with sensitive data.
- Not a replacement for serious text-to-SQL tools like Vanna or Dataherald.

## Why there's no live demo

The demo dataset was scraped from MyDramaList, and redistributing it via a public URL isn't something I want to do. The code runs locally against your own Supabase project just fine; if you want a deployable version, swap the dataset for something with a permissive license (e.g., Chinook, or your own data) and the app works unchanged.

## Roadmap

- Eval harness (a JSON of question/expected pairs + pass-rate report), streaming output, multi-agent handoff (router → SQL agent | viz agent).

## Tech stack

- Python 3.12, [uv](https://docs.astral.sh/uv/)
- [`openai-agents`](https://openai.github.io/openai-agents-python/) — the OpenAI Agents SDK (with its built-in MCP client)
- [`mcp`](https://modelcontextprotocol.io/) — the Python MCP SDK; the agent's tools live in a FastMCP server it spawns as a subprocess
- `asyncpg` — direct async Postgres driver
- Supabase — hosted Postgres + the `agent_readonly` role for safety
- `streamlit` for the chat UI
- `python-dotenv` for the API key

## Project layout

```
text-to-sql/
├── src/
│   ├── prompts.py      # system instructions, kept separate for easy iteration
│   ├── db.py           # asyncpg connection + introspection SQL + SELECT-only guard
│   ├── sql_tools.py    # the three async tool implementations
│   ├── mcp_server.py   # FastMCP server exposing sql_tools over stdio
│   ├── agent.py        # spawns mcp_server as a subprocess + run_question()
│   └── cli.py          # argv -> asyncio.run(run_question(...))
├── supabase/
│   └── setup_readonly_role.sql   # one-shot role + grants for the agent
├── tests/
│   └── test_db.py      # unit tests for the SELECT-only guard
├── app.py              # Streamlit UI
├── pyproject.toml
└── .env.example
```
