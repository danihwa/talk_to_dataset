# text-to-sql-data

A natural-language data Q&A agent built with the OpenAI Agents SDK, pointed at a **Supabase** Postgres database. Ask questions in English or Czech, and the agent inspects the schema, writes a `SELECT`, runs it via custom function tools, and replies with the answer plus the SQL it ran.

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
│  SQL Analyst agent          │   @function_tools (only read paths exist):
│  - inspects schema          │     • list_tables
│  - writes a SELECT          │     • describe_table(name)
│  - runs it via asyncpg      │     • run_select_query(sql)
│  - retries on SQL error     │
│  - formats the answer       │
└─────────────────────────────┘
     │
     ▼
   answer + SQL
```

The OpenAI Agents SDK runs an internal model-tool loop: the model decides whether to call a tool or return a final answer. If a query errors, the error goes back into the model's context and it tries again. The loop is capped by `max_turns=10` so a buggy run can't spiral.

The three tools are plain async Python functions decorated with `@function_tool`. They open a fresh `asyncpg` connection to Supabase using the read-only role's URI, run a single query against `information_schema` or the user's data, and return JSON or markdown that goes back into the model's context.

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

## Deploying

The Streamlit app runs unchanged on Streamlit Cloud, Hugging Face Spaces, or any container host. Things to know:

- **`OPENAI_API_KEY`** and **`SUPABASE_DB_URL`** — set both as host secrets. `load_secrets()` falls through to `os.environ` if neither `~/secrets/.env` nor a local `.env` is present.
- **Costs on a public deploy** — every question makes multiple LLM calls on your key. For a public URL you'd want either a "bring your own API key" input, password gating, or rate limiting. Out of scope for the demo.

## Roadmap

- Eval harness (a JSON of question/expected pairs + pass-rate report), streaming output, multi-agent handoff (router → SQL agent | viz agent).

## Tech stack

- Python 3.12, [uv](https://docs.astral.sh/uv/)
- [`openai-agents`](https://openai.github.io/openai-agents-python/) — the OpenAI Agents SDK
- `asyncpg` — direct async Postgres driver
- Supabase — hosted Postgres + the `agent_readonly` role for safety
- `streamlit` for the chat UI
- `python-dotenv` for the API key

## Project layout

```
text-to-sql-data/
├── src/
│   ├── prompts.py      # system instructions, kept separate for easy iteration
│   ├── db.py           # asyncpg connection + introspection SQL + SELECT-only guard
│   ├── agent.py        # @function_tool definitions and run_question()
│   └── cli.py          # argv -> asyncio.run(run_question(...))
├── supabase/
│   └── setup_readonly_role.sql   # one-shot role + grants for the agent
├── tests/
│   └── test_db.py      # unit tests for the SELECT-only guard
├── app.py              # Streamlit UI
├── pyproject.toml
└── .env.example
```
