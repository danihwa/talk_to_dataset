from pathlib import Path

from agents import Agent, Runner
from agents.mcp import MCPServerStdio, create_static_tool_filter

from src.prompts import SYSTEM_INSTRUCTIONS

DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "chinook.db"

READ_ONLY_TOOLS = ["list_tables", "describe_table", "read_query"]


def _build_mcp_server(db_path: Path) -> MCPServerStdio:
    return MCPServerStdio(
        name="sqlite",
        params={
            "command": "uvx",
            "args": ["mcp-server-sqlite", "--db-path", str(db_path)],
        },
        cache_tools_list=True,
        tool_filter=create_static_tool_filter(allowed_tool_names=READ_ONLY_TOOLS),
    )


async def run_question(question: str, db_path: Path = DEFAULT_DB) -> str:
    async with _build_mcp_server(db_path) as sqlite_mcp:
        agent = Agent(
            name="SQL Analyst",
            instructions=SYSTEM_INSTRUCTIONS,
            mcp_servers=[sqlite_mcp],
            model="gpt-4o-mini",
        )
        result = await Runner.run(agent, input=question, max_turns=10)
        return result.final_output
