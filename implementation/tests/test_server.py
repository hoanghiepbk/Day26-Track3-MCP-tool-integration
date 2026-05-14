"""Unit tests for the SQLite adapter and MCP server."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Make implementation/ importable when running pytest from repo root
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from db import SQLiteAdapter, ValidationError  # noqa: E402
from init_db import create_database  # noqa: E402


@pytest.fixture()
def adapter(tmp_path):
    db_path = tmp_path / "test_lab.db"
    create_database(db_path)
    return SQLiteAdapter(db_path)


# ---------------------------------------------------------------------- search
class TestSearch:
    def test_search_no_filter_returns_all(self, adapter):
        result = adapter.search("students")
        assert result["page"]["total"] == 8
        assert len(result["rows"]) == 8

    def test_search_eq_filter(self, adapter):
        result = adapter.search("students", filters={"cohort": "A1"})
        assert all(r["cohort"] == "A1" for r in result["rows"])
        assert result["page"]["total"] == 3

    def test_search_operator_filters(self, adapter):
        result = adapter.search("students", filters={"score": {"gte": 90}})
        assert all(r["score"] >= 90 for r in result["rows"])

    def test_search_in_operator(self, adapter):
        result = adapter.search(
            "students", filters={"cohort": {"in": ["A1", "B1"]}}
        )
        assert all(r["cohort"] in {"A1", "B1"} for r in result["rows"])

    def test_search_like_operator(self, adapter):
        result = adapter.search("students", filters={"name": {"like": "A%"}})
        assert all(r["name"].startswith("A") for r in result["rows"])

    def test_search_pagination_and_order(self, adapter):
        page = adapter.search(
            "students", limit=3, offset=0, order_by="score", descending=True
        )
        assert len(page["rows"]) == 3
        assert page["rows"][0]["score"] >= page["rows"][1]["score"]
        assert page["page"]["has_more"] is True
        assert page["page"]["next_offset"] == 3

    def test_search_column_subset(self, adapter):
        result = adapter.search("students", columns=["name", "score"], limit=1)
        assert set(result["rows"][0].keys()) == {"name", "score"}

    def test_search_rejects_unknown_table(self, adapter):
        with pytest.raises(ValidationError, match="unknown table"):
            adapter.search("ghosts")

    def test_search_rejects_unknown_column(self, adapter):
        with pytest.raises(ValidationError, match="unknown column"):
            adapter.search("students", columns=["nope"])

    def test_search_rejects_unknown_operator(self, adapter):
        with pytest.raises(ValidationError, match="unsupported operator"):
            adapter.search("students", filters={"name": {"xx": "Alice"}})

    def test_search_rejects_bad_limit(self, adapter):
        with pytest.raises(ValidationError):
            adapter.search("students", limit=0)


# ---------------------------------------------------------------------- insert
class TestInsert:
    def test_insert_returns_payload_with_id(self, adapter):
        result = adapter.insert(
            "students", {"name": "Zed", "cohort": "C1", "score": 77.0}
        )
        assert isinstance(result["id"], int)
        assert result["row"]["name"] == "Zed"
        assert result["row"]["cohort"] == "C1"

    def test_insert_rejects_empty_values(self, adapter):
        with pytest.raises(ValidationError, match="non-empty"):
            adapter.insert("students", {})

    def test_insert_rejects_unknown_column(self, adapter):
        with pytest.raises(ValidationError, match="unknown column"):
            adapter.insert("students", {"nope": 1})

    def test_insert_rejects_unknown_table(self, adapter):
        with pytest.raises(ValidationError, match="unknown table"):
            adapter.insert("ghosts", {"x": 1})


# ------------------------------------------------------------------- aggregate
class TestAggregate:
    def test_count_all(self, adapter):
        result = adapter.aggregate("students", "count")
        assert result["rows"][0]["value"] == 8

    def test_avg_grouped(self, adapter):
        result = adapter.aggregate(
            "students", "avg", column="score", group_by="cohort"
        )
        cohorts = {r["cohort"]: r["value"] for r in result["rows"]}
        assert "A1" in cohorts
        assert cohorts["A1"] == pytest.approx((92.5 + 78.0 + 88.0) / 3)

    def test_sum_with_filter(self, adapter):
        result = adapter.aggregate(
            "students", "sum", column="score", filters={"cohort": "A1"}
        )
        assert result["rows"][0]["value"] == pytest.approx(92.5 + 78.0 + 88.0)

    def test_min_max(self, adapter):
        assert adapter.aggregate("students", "min", column="score")["rows"][0]["value"] == 59.5
        assert adapter.aggregate("students", "max", column="score")["rows"][0]["value"] == 95.0

    def test_aggregate_rejects_unsupported_metric(self, adapter):
        with pytest.raises(ValidationError, match="unsupported metric"):
            adapter.aggregate("students", "median", column="score")

    def test_aggregate_requires_column_for_non_count(self, adapter):
        with pytest.raises(ValidationError, match="requires a column"):
            adapter.aggregate("students", "avg")

    def test_aggregate_rejects_unknown_column(self, adapter):
        with pytest.raises(ValidationError, match="unknown column"):
            adapter.aggregate("students", "avg", column="nope")


# --------------------------------------------------------------------- schema
class TestSchema:
    def test_list_tables(self, adapter):
        assert set(adapter.list_tables()) == {"students", "courses", "enrollments"}

    def test_full_schema_shape(self, adapter):
        schema = adapter.full_schema()
        assert "students" in schema
        names = {c["name"] for c in schema["students"]}
        assert {"id", "name", "cohort", "score"}.issubset(names)

    def test_get_table_schema_rejects_unknown(self, adapter):
        with pytest.raises(ValidationError):
            adapter.get_table_schema("ghosts")


# ----------------------------------------------------------- MCP integration
@pytest.mark.asyncio
async def test_mcp_tools_via_client(tmp_path, monkeypatch):
    """Boot the FastMCP server with an isolated DB and exercise every tool."""
    db_path = tmp_path / "lab.db"
    monkeypatch.setenv("SQLITE_LAB_DB", str(db_path))

    # Re-import server with the env var pointing at the temp DB.
    for mod in ("mcp_server", "db", "init_db"):
        sys.modules.pop(mod, None)
    from fastmcp import Client  # noqa: WPS433
    import mcp_server  # noqa: WPS433

    async with Client(mcp_server.mcp) as client:
        tools = {t.name for t in await client.list_tools()}
        assert {"search", "insert", "aggregate"}.issubset(tools)

        result = await client.call_tool("search", {"table": "students", "limit": 2})
        data = result.structured_content or result.data
        assert len(data["rows"]) == 2

        bad = await client.call_tool("search", {"table": "ghosts"})
        bad_data = bad.structured_content or bad.data
        assert "error" in bad_data

        full = await client.read_resource("schema://database")
        doc = json.loads(full[0].text)
        assert "students" in doc["tables"]
