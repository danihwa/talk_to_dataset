from mcp.server.fastmcp import FastMCP

from src import sql_tools
from src.cli import load_secrets

mcp = FastMCP("text-to-sql")

mcp.tool()(sql_tools.list_tables)
mcp.tool()(sql_tools.describe_table)
mcp.tool()(sql_tools.run_select_query)


def main() -> None:
    load_secrets()
    mcp.run()


if __name__ == "__main__":
    main()
