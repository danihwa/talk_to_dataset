import sys

from agents import Agent, Runner
from agents.mcp import MCPServerStdio

from src.prompts import SYSTEM_INSTRUCTIONS


async def run_question(
    question: str, history: list | None = None
) -> tuple[str, list]:
    """Run one turn against the SQL Analyst agent.

    Spawns `src/mcp_server.py` as a subprocess and routes every tool call
    through MCP. Returns the final answer plus the updated input list to
    feed back as `history` on the next call (preserves tool calls and
    results, not just text).
    """
    async with MCPServerStdio(
        name="text-to-sql",
        # sys.executable so the subprocess uses the same interpreter as
        # the parent (works under `uv run`, plain `python`, etc.).
        params={"command": sys.executable, "args": ["-m", "src.mcp_server"]},
        cache_tools_list=True,
    ) as server:
        agent = Agent(
            name="SQL Analyst",
            instructions=SYSTEM_INSTRUCTIONS,
            mcp_servers=[server],
            model="gpt-4o-mini",
        )
        if history:
            # Runner.run accepts a bare string on the first turn, or a list of
            # input items (carrying prior tool calls/results) for follow-up turns.
            input_items = history + [{"role": "user", "content": question}]
        else:
            input_items = question
        result = await Runner.run(agent, input=input_items, max_turns=10)
        return result.final_output, result.to_input_list()
