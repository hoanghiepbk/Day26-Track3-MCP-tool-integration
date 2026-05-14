"""FastMCP server exposing the SQLite lab database.

Tools:
    - search(table, filters, columns, limit, offset, order_by, descending)
    - insert(table, values)
    - aggregate(table, metric, column, filters, group_by)

Resources:
    - schema://database          -> full schema snapshot
    - schema://table/{name}      -> per-table schema
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

from db import SQLiteAdapter, ValidationError
from init_db import DEFAULT_DB_PATH, create_database

DB_PATH = Path(os.environ.get("SQLITE_LAB_DB", DEFAULT_DB_PATH)).resolve()

if not DB_PATH.exists():
    create_database(DB_PATH)

adapter = SQLiteAdapter(DB_PATH)

mcp = FastMCP("SQLite Lab MCP Server")


# ----------------------------------------------------------------------
# Tools
# ----------------------------------------------------------------------
@mcp.tool(name="search")
def search(
    table: str,
    filters: dict[str, Any] | None = None,
    columns: list[str] | None = None,
    limit: int = 20,
    offset: int = 0,
    order_by: str | None = None,
    descending: bool = False,
) -> dict[str, Any]:
    """Search rows in a table.

    Args:
        table: Target table name (must exist).
        filters: Map of column -> value or column -> {op: value}.
            Supported ops: eq, ne, gt, gte, lt, lte, like, in.
        columns: Optional subset of columns to return.
        limit: Max rows to return (1..200, default 20).
        offset: Pagination offset (>=0).
        order_by: Column to sort by.
        descending: Sort descending when True.
    """
    try:
        return adapter.search(
            table=table,
            columns=columns,
            filters=filters,
            limit=limit,
            offset=offset,
            order_by=order_by,
            descending=descending,
        )
    except ValidationError as exc:
        return {"error": str(exc)}


@mcp.tool(name="insert")
def insert(table: str, values: dict[str, Any]) -> dict[str, Any]:
    """Insert a single row into a table.

    Args:
        table: Target table name.
        values: Non-empty mapping of column -> value.

    Returns the inserted row including its generated primary key.
    """
    try:
        return adapter.insert(table=table, values=values)
    except ValidationError as exc:
        return {"error": str(exc)}


@mcp.tool(name="aggregate")
def aggregate(
    table: str,
    metric: str,
    column: str | None = None,
    filters: dict[str, Any] | None = None,
    group_by: str | None = None,
) -> dict[str, Any]:
    """Run an aggregate query.

    Args:
        table: Target table name.
        metric: One of count, avg, sum, min, max.
        column: Column to aggregate (optional only for count).
        filters: Same shape as search filters.
        group_by: Optional column to group by.
    """
    try:
        return adapter.aggregate(
            table=table,
            metric=metric,
            column=column,
            filters=filters,
            group_by=group_by,
        )
    except ValidationError as exc:
        return {"error": str(exc)}


# ----------------------------------------------------------------------
# Resources
# ----------------------------------------------------------------------
@mcp.resource("schema://database", mime_type="application/json")
def database_schema() -> str:
    """Return the full database schema as JSON."""
    return json.dumps(
        {
            "database": adapter.db_path,
            "tables":   adapter.full_schema(),
        },
        indent=2,
    )


@mcp.resource("schema://table/{table_name}", mime_type="application/json")
def table_schema(table_name: str) -> str:
    """Return schema for a single table as JSON."""
    try:
        columns = adapter.get_table_schema(table_name)
    except ValidationError as exc:
        return json.dumps({"error": str(exc)}, indent=2)
    return json.dumps(
        {"table": table_name, "columns": columns},
        indent=2,
    )


# ----------------------------------------------------------------------
# Entry point
# ----------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="SQLite Lab MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http", "sse"],
        default="stdio",
        help="Transport to run. Default: stdio.",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    if args.transport == "stdio":
        mcp.run()
    else:
        mcp.run(transport=args.transport, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
