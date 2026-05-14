"""End-to-end smoke test using FastMCP's in-process Client.

Demonstrates:
    - tool discovery
    - resource discovery
    - valid tool calls
    - invalid tool calls (clear error messages)
    - reading both schema resources
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from fastmcp import Client

from mcp_server import mcp


PASS = "[PASS]"
FAIL = "[FAIL]"


def _ok(label: str, ok: bool, detail: str = "") -> bool:
    tag = PASS if ok else FAIL
    print(f"{tag} {label}" + (f" -- {detail}" if detail else ""))
    return ok


def _payload(result: Any) -> Any:
    if getattr(result, "structured_content", None):
        return result.structured_content
    if getattr(result, "data", None) is not None:
        return result.data
    return result


async def main() -> int:
    failures = 0

    async with Client(mcp) as client:
        # --- Discovery -------------------------------------------------
        tools = await client.list_tools()
        tool_names = {t.name for t in tools}
        if not _ok(
            "tool discovery: search/insert/aggregate present",
            {"search", "insert", "aggregate"}.issubset(tool_names),
            f"found={sorted(tool_names)}",
        ):
            failures += 1

        resources = await client.list_resources()
        templates = await client.list_resource_templates()
        resource_uris = {str(r.uri) for r in resources}
        template_uris = {str(t.uriTemplate) for t in templates}
        if not _ok(
            "resource discovery: schema://database",
            "schema://database" in resource_uris,
            f"found={sorted(resource_uris)}",
        ):
            failures += 1
        if not _ok(
            "resource discovery: schema://table/{table_name}",
            any("schema://table/" in u for u in template_uris),
            f"found={sorted(template_uris)}",
        ):
            failures += 1

        # --- Valid calls ----------------------------------------------
        res = await client.call_tool(
            "search",
            {"table": "students", "filters": {"cohort": "A1"}, "order_by": "score", "descending": True},
        )
        data = _payload(res)
        if not _ok(
            "search students cohort=A1 returned rows",
            isinstance(data, dict) and data.get("rows") and len(data["rows"]) >= 1,
            f"rows={len(data.get('rows', [])) if isinstance(data, dict) else 0}",
        ):
            failures += 1

        res = await client.call_tool(
            "insert",
            {"table": "students", "values": {"name": "Test User", "cohort": "Z9", "score": 50.0}},
        )
        data = _payload(res)
        if not _ok(
            "insert returns row with id",
            isinstance(data, dict) and isinstance(data.get("id"), int) and data.get("row", {}).get("name") == "Test User",
            f"payload={data}",
        ):
            failures += 1

        res = await client.call_tool(
            "aggregate",
            {"table": "students", "metric": "avg", "column": "score", "group_by": "cohort"},
        )
        data = _payload(res)
        if not _ok(
            "aggregate avg score group_by cohort",
            isinstance(data, dict) and len(data.get("rows", [])) >= 2,
            f"rows={data.get('rows') if isinstance(data, dict) else None}",
        ):
            failures += 1

        res = await client.call_tool(
            "aggregate",
            {"table": "students", "metric": "count"},
        )
        data = _payload(res)
        if not _ok(
            "aggregate count(*) returns single row",
            isinstance(data, dict) and len(data.get("rows", [])) == 1,
        ):
            failures += 1

        # --- Resources -------------------------------------------------
        full = await client.read_resource("schema://database")
        schema_text = full[0].text
        schema_doc = json.loads(schema_text)
        if not _ok(
            "schema://database lists all 3 tables",
            {"students", "courses", "enrollments"}.issubset(schema_doc.get("tables", {}).keys()),
        ):
            failures += 1

        per_table = await client.read_resource("schema://table/students")
        per_doc = json.loads(per_table[0].text)
        if not _ok(
            "schema://table/students returns columns",
            per_doc.get("table") == "students"
            and any(c["name"] == "score" for c in per_doc.get("columns", [])),
        ):
            failures += 1

        # --- Invalid calls --------------------------------------------
        res = await client.call_tool("search", {"table": "ghosts"})
        data = _payload(res)
        if not _ok(
            "search unknown table -> error",
            isinstance(data, dict) and "error" in data and "unknown table" in data["error"],
            f"error={data.get('error') if isinstance(data, dict) else data}",
        ):
            failures += 1

        res = await client.call_tool(
            "search", {"table": "students", "filters": {"name": {"xx": "Alice"}}}
        )
        data = _payload(res)
        if not _ok(
            "search bad operator -> error",
            isinstance(data, dict) and "unsupported operator" in (data.get("error") or ""),
        ):
            failures += 1

        res = await client.call_tool("insert", {"table": "students", "values": {}})
        data = _payload(res)
        if not _ok(
            "insert empty values -> error",
            isinstance(data, dict) and "non-empty" in (data.get("error") or ""),
        ):
            failures += 1

        res = await client.call_tool(
            "aggregate", {"table": "students", "metric": "median", "column": "score"}
        )
        data = _payload(res)
        if not _ok(
            "aggregate unsupported metric -> error",
            isinstance(data, dict) and "unsupported metric" in (data.get("error") or ""),
        ):
            failures += 1

        res = await client.call_tool(
            "search", {"table": "students", "columns": ["nope"]}
        )
        data = _payload(res)
        if not _ok(
            "search unknown column -> error",
            isinstance(data, dict) and "unknown column" in (data.get("error") or ""),
        ):
            failures += 1

    print()
    print("=" * 60)
    print(f"Result: {'ALL PASS' if failures == 0 else f'{failures} FAILURE(S)'}")
    print("=" * 60)
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
