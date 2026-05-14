"""SQLite adapter for the MCP lab.

All identifiers (tables, columns) are validated against the live schema
before being injected into SQL. All values are bound through parameter
placeholders. Operators are restricted to a small allow-list.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Iterable


class ValidationError(Exception):
    """Raised when a request cannot be safely executed."""


ALLOWED_OPERATORS: dict[str, str] = {
    "eq":  "=",
    "ne":  "!=",
    "gt":  ">",
    "gte": ">=",
    "lt":  "<",
    "lte": "<=",
    "like": "LIKE",
    "in":  "IN",
}

ALLOWED_METRICS = {"count", "avg", "sum", "min", "max"}

MAX_LIMIT = 200


class SQLiteAdapter:
    """Safe-ish SQLite adapter exposed via MCP tools."""

    def __init__(self, db_path: str | Path):
        self.db_path = str(Path(db_path).resolve())

    # ------------------------------------------------------------------
    # connection helpers
    # ------------------------------------------------------------------
    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    # ------------------------------------------------------------------
    # schema inspection
    # ------------------------------------------------------------------
    def list_tables(self) -> list[str]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name NOT LIKE 'sqlite_%' "
                "ORDER BY name"
            ).fetchall()
        return [r["name"] for r in rows]

    def get_table_schema(self, table: str) -> list[dict[str, Any]]:
        self._assert_table(table)
        with self.connect() as conn:
            rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        return [
            {
                "cid":          r["cid"],
                "name":         r["name"],
                "type":         r["type"],
                "not_null":     bool(r["notnull"]),
                "default":      r["dflt_value"],
                "primary_key":  bool(r["pk"]),
            }
            for r in rows
        ]

    def full_schema(self) -> dict[str, list[dict[str, Any]]]:
        return {t: self.get_table_schema(t) for t in self.list_tables()}

    # ------------------------------------------------------------------
    # validation
    # ------------------------------------------------------------------
    def _assert_table(self, table: str) -> None:
        if not isinstance(table, str) or not table:
            raise ValidationError("table must be a non-empty string")
        if table not in self.list_tables():
            raise ValidationError(f"unknown table: {table!r}")

    def _column_names(self, table: str) -> set[str]:
        return {c["name"] for c in self.get_table_schema(table)}

    def _assert_columns(self, table: str, columns: Iterable[str]) -> None:
        known = self._column_names(table)
        for c in columns:
            if not isinstance(c, str) or c not in known:
                raise ValidationError(
                    f"unknown column {c!r} for table {table!r}"
                )

    # ------------------------------------------------------------------
    # search
    # ------------------------------------------------------------------
    def search(
        self,
        table: str,
        columns: list[str] | None = None,
        filters: dict[str, Any] | None = None,
        limit: int = 20,
        offset: int = 0,
        order_by: str | None = None,
        descending: bool = False,
    ) -> dict[str, Any]:
        self._assert_table(table)

        if columns:
            self._assert_columns(table, columns)
            select_clause = ", ".join(columns)
        else:
            select_clause = "*"

        where_sql, params = self._build_where(table, filters or {})

        order_sql = ""
        if order_by:
            self._assert_columns(table, [order_by])
            direction = "DESC" if descending else "ASC"
            order_sql = f" ORDER BY {order_by} {direction}"

        if not isinstance(limit, int) or limit < 1:
            raise ValidationError("limit must be a positive integer")
        if not isinstance(offset, int) or offset < 0:
            raise ValidationError("offset must be a non-negative integer")
        limit = min(limit, MAX_LIMIT)

        sql = f"SELECT {select_clause} FROM {table}{where_sql}{order_sql} LIMIT ? OFFSET ?"
        params_with_paging = (*params, limit, offset)

        with self.connect() as conn:
            rows = conn.execute(sql, params_with_paging).fetchall()
            total = conn.execute(
                f"SELECT COUNT(*) AS n FROM {table}{where_sql}", params
            ).fetchone()["n"]

        result_rows = [dict(r) for r in rows]
        return {
            "rows": result_rows,
            "page": {
                "limit":      limit,
                "offset":     offset,
                "returned":   len(result_rows),
                "total":      total,
                "has_more":   offset + len(result_rows) < total,
                "next_offset": offset + len(result_rows) if offset + len(result_rows) < total else None,
            },
        }

    def _build_where(
        self, table: str, filters: dict[str, Any]
    ) -> tuple[str, tuple[Any, ...]]:
        if not filters:
            return "", ()
        if not isinstance(filters, dict):
            raise ValidationError("filters must be an object")

        self._assert_columns(table, filters.keys())

        clauses: list[str] = []
        params: list[Any] = []

        for column, spec in filters.items():
            if isinstance(spec, dict):
                if len(spec) != 1:
                    raise ValidationError(
                        f"filter for {column!r} must have exactly one operator"
                    )
                op, value = next(iter(spec.items()))
            else:
                op, value = "eq", spec

            if op not in ALLOWED_OPERATORS:
                raise ValidationError(
                    f"unsupported operator {op!r}; allowed: {sorted(ALLOWED_OPERATORS)}"
                )

            sql_op = ALLOWED_OPERATORS[op]
            if op == "in":
                if not isinstance(value, (list, tuple)) or not value:
                    raise ValidationError(
                        f"'in' filter for {column!r} requires a non-empty list"
                    )
                placeholders = ", ".join("?" for _ in value)
                clauses.append(f"{column} IN ({placeholders})")
                params.extend(value)
            else:
                clauses.append(f"{column} {sql_op} ?")
                params.append(value)

        return " WHERE " + " AND ".join(clauses), tuple(params)

    # ------------------------------------------------------------------
    # insert
    # ------------------------------------------------------------------
    def insert(self, table: str, values: dict[str, Any]) -> dict[str, Any]:
        self._assert_table(table)
        if not isinstance(values, dict) or not values:
            raise ValidationError("values must be a non-empty object")

        self._assert_columns(table, values.keys())

        columns = list(values.keys())
        placeholders = ", ".join("?" for _ in columns)
        sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"

        with self.connect() as conn:
            cursor = conn.execute(sql, tuple(values[c] for c in columns))
            new_id = cursor.lastrowid
            conn.commit()
            row = conn.execute(
                f"SELECT * FROM {table} WHERE rowid = ?", (new_id,)
            ).fetchone()

        return {
            "table":   table,
            "id":      new_id,
            "row":     dict(row) if row else None,
        }

    # ------------------------------------------------------------------
    # aggregate
    # ------------------------------------------------------------------
    def aggregate(
        self,
        table: str,
        metric: str,
        column: str | None = None,
        filters: dict[str, Any] | None = None,
        group_by: str | None = None,
    ) -> dict[str, Any]:
        self._assert_table(table)

        if not isinstance(metric, str) or metric.lower() not in ALLOWED_METRICS:
            raise ValidationError(
                f"unsupported metric {metric!r}; allowed: {sorted(ALLOWED_METRICS)}"
            )
        metric = metric.lower()

        if metric == "count":
            if column is None:
                metric_sql = "COUNT(*)"
            else:
                self._assert_columns(table, [column])
                metric_sql = f"COUNT({column})"
        else:
            if not column:
                raise ValidationError(
                    f"metric {metric!r} requires a column"
                )
            self._assert_columns(table, [column])
            metric_sql = f"{metric.upper()}({column})"

        where_sql, params = self._build_where(table, filters or {})

        group_sql = ""
        select_group = ""
        if group_by:
            self._assert_columns(table, [group_by])
            select_group = f"{group_by}, "
            group_sql = f" GROUP BY {group_by} ORDER BY {group_by}"

        sql = (
            f"SELECT {select_group}{metric_sql} AS value FROM {table}"
            f"{where_sql}{group_sql}"
        )

        with self.connect() as conn:
            rows = conn.execute(sql, params).fetchall()

        return {
            "metric":  metric,
            "column":  column,
            "group_by": group_by,
            "rows":    [dict(r) for r in rows],
        }
