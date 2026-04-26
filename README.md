# text-to-sql-data

A natural-language data Q&A agent built with the OpenAI Agents SDK and an MCP server for SQLite. Ask questions in English or Czech, and the agent inspects the database, writes a `SELECT`, runs it, and replies with the answer plus the SQL it ran.

This is the **Phase 1 MVP**: a CLI pointed at the [Chinook](https://github.com/lerocha/chinook-database) sample database. Phase 2 (Streamlit UI + CSV/XLSX upload) and Phase 3 (eval harness, streaming, multi-agent) are on the roadmap, not implemented yet.

## Setup

Prerequisites:
- Python 3.12
- [uv](https://docs.astral.sh/uv/) (we also use `uvx` to run the SQLite MCP server)
- An OpenAI API key

```bash
uv sync
cp .env.example .env
# then put your OPENAI_API_KEY into .env
```

## Usage

```bash
uv run python -m src.cli "Which 5 customers spent the most money?"
```

That's it. One question per invocation; the answer prints to stdout with the SQL the agent ran appended in a fenced code block.

## Example questions

These all work against the bundled Chinook DB:

1. `Which 5 customers spent the most money?`
2. `How many tracks are in each genre?`
3. `What's the longest track in the database?`
4. `Kolik je v databázi alb?` *(Czech: "How many albums are in the database?")*
5. `Show me employees who joined before 2003.`

If you ask the agent to delete or modify anything, it can't — see the safety section below.

## How it works

```
your question
     │
     ▼
┌─────────────────────────────┐
│  SQL Analyst agent          │   tools (whitelisted, read-only):
│  - inspects schema          │     • list_tables
│  - writes a SELECT          │     • describe_table
│  - runs it via MCP          │     • read_query
│  - retries on SQL error     │
│  - formats the answer       │
└─────────────────────────────┘
     │
     ▼
   answer + SQL
```

The OpenAI Agents SDK runs an internal model-tool loop: the model decides whether to call a tool or return a final answer. If a query errors, the error goes back into the model's context and it tries again. The loop is capped by `max_turns=10` so a buggy run can't spiral.

The actual SQL is run by [`mcp-server-sqlite`](https://github.com/modelcontextprotocol/servers-archived/tree/main/src/sqlite), spawned over stdio via `uvx`. The agent talks to it through the SDK's MCP support.

## Read-only safety

Two layers, in this order:

1. **Tool filtering** (`create_static_tool_filter` in `src/agent.py`): the agent is exposed *only* to `list_tables`, `describe_table`, and `read_query`. The MCP server's `write_query` tool is not in the agent's toolbelt at all — it can't call what it doesn't see.
2. **System prompt**: the instructions still tell the agent to only ever write `SELECT`. Belt-and-suspenders.

This is deliberate: defense in depth, not just "we asked the model nicely".

## Not production-grade

This is a portfolio project. Things I'd do differently for production:

- The SQLite MCP server is from the archived [`modelcontextprotocol/servers-archived`](https://github.com/modelcontextprotocol/servers-archived/tree/main/src/sqlite) reference repo. It still works, but is no longer actively maintained — a community alternative would be a drop-in swap.
- Schema fits in a single prompt because Chinook is small (11 tables). At ~100 tables you'd need schema embedding + retrieval rather than dumping the whole schema.
- No adversarial-input hardening beyond the read-only enforcement above. Don't point this at a database with sensitive data.
- Not a replacement for serious text-to-SQL tools like Vanna or Dataherald.

## Roadmap

- **Phase 2** — Streamlit UI, drop-in CSV/XLSX upload (pandas → fresh SQLite → same agent).
- **Phase 3** — eval harness (a JSON of question/expected pairs + pass-rate report), streaming output, conversation memory, Czech open-data dataset, multi-agent handoff for visualization.

## Tech stack

- Python 3.12, [uv](https://docs.astral.sh/uv/)
- [`openai-agents`](https://openai.github.io/openai-agents-python/) — the OpenAI Agents SDK
- `mcp-server-sqlite` (run via `uvx`)
- `python-dotenv` for the API key

## Project layout

```
text-to-sql-data/
├── data/chinook.db
├── src/
│   ├── prompts.py      # system instructions, kept separate for easy iteration
│   ├── agent.py        # MCP server setup, tool filter, run_question()
│   └── cli.py          # argv -> asyncio.run(run_question(...))
├── pyproject.toml
└── .env.example
```
