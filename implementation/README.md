# SQLite Lab — FastMCP Server (Submission)

**Student:** Phạm Hữu Hoàng Hiệp
**Student ID:** 2A202600415
**Course:** Day 26 / Track 3 — MCP tool integration

Submission for **Day 26 / Track 3 — MCP tool integration**.
A small FastMCP server that exposes a SQLite database through three tools
(`search`, `insert`, `aggregate`) and two MCP resources
(`schema://database`, `schema://table/{table_name}`).

> The grading rubric, learning outcomes, and required features live in the
> repository-root [`README.md`](../README.md) and [`Rubric.md`](../Rubric.md).
> This file is the **student submission** that documents how to set up, run,
> verify, and demo the server.

---

## 1. Project layout

```
implementation/
├── db.py                # SQLiteAdapter + validation
├── init_db.py           # creates lab.db + seed data
├── mcp_server.py        # FastMCP server (tools + resources)
├── verify_server.py     # in-process smoke test (13 checks)
├── requirements.txt
├── start_inspector.sh   # bash launcher for MCP Inspector
├── start_inspector.ps1  # PowerShell launcher for MCP Inspector
└── tests/
    └── test_server.py   # 26 pytest cases
client-configs/
├── codex.config.toml
├── gemini-add.sh
└── gemini-settings.json
.mcp.json                # Claude Code config (repo root)
```

## 2. Setup

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate
pip install -r implementation/requirements.txt

# Create + seed the SQLite database
python implementation/init_db.py
# -> Initialized database at: .../implementation/lab.db
```

Python 3.10+ is required (project tested on Python 3.12).

## 3. Run the server

```bash
# stdio (default — used by Claude Code, Codex, Gemini CLI, Inspector)
python implementation/mcp_server.py

# Bonus: HTTP transport
python implementation/mcp_server.py --transport http --host 127.0.0.1 --port 8000
```

The server auto-initializes the DB on first launch if `lab.db` is missing.
You can override the DB location with the env var `SQLITE_LAB_DB`.

## 4. Tools

| Tool        | Description                                          | Key arguments                                                  |
|-------------|------------------------------------------------------|----------------------------------------------------------------|
| `search`    | Read rows with filters, ordering, pagination         | `table`, `filters`, `columns`, `limit`, `offset`, `order_by`, `descending` |
| `insert`    | Insert one row, returns the new row + generated id   | `table`, `values`                                              |
| `aggregate` | `count` / `avg` / `sum` / `min` / `max`, optional `group_by` | `table`, `metric`, `column`, `filters`, `group_by`             |

**Filter operators (allow-listed):** `eq, ne, gt, gte, lt, lte, like, in`.

### Example calls

```jsonc
// search — top students in cohort A1
{
  "table": "students",
  "filters": {"cohort": "A1"},
  "order_by": "score",
  "descending": true
}

// insert — new student
{
  "table": "students",
  "values": {"name": "Test User", "cohort": "Z9", "score": 50.0}
}

// aggregate — avg score per cohort
{
  "table": "students",
  "metric": "avg",
  "column": "score",
  "group_by": "cohort"
}
```

## 5. Resources

- `schema://database` — full schema snapshot for every non-internal table.
- `schema://table/{table_name}` — single-table schema; rejects unknown tables.

Both return JSON with `mime_type=application/json`.

## 6. Validation & safety

Every tool rejects unsafe input **before** any SQL runs:

- unknown table name → `unknown table: 'ghosts'`
- unknown column name → `unknown column 'nope' for table 'students'`
- unsupported filter operator → `unsupported operator 'xx'; allowed: [...]`
- unsupported aggregate metric → `unsupported metric 'median'; allowed: [...]`
- non-count aggregate without a column → `metric 'avg' requires a column`
- empty `insert` payload → `values must be a non-empty object`
- bad `limit`/`offset` → `ValidationError`

All identifiers come from the live schema allow-list; all values are bound
through `?` placeholders. There is no string concatenation of user input
into SQL.

## 7. Automated verification

```bash
# 1. Smoke test the server through FastMCP's in-process client
python implementation/verify_server.py

# 2. Unit + integration tests (26 cases)
cd implementation && python -m pytest tests/ -v
```

Expected:

```
============================================================
Result: ALL PASS
============================================================
...
26 passed in ~1s
```

## 8. MCP Inspector

```bash
# Bash / WSL / macOS
cd implementation
./start_inspector.sh

# Windows PowerShell
cd implementation
./start_inspector.ps1
```

Or run the canonical command directly:

```bash
npx -y @modelcontextprotocol/inspector python implementation/mcp_server.py
```

**Screenshots to capture for the submission:**
1. Inspector main page showing **server connected**.
2. **Tools** tab listing `search`, `insert`, `aggregate` with their schemas.
3. **Resources** tab showing `schema://database` + the
   `schema://table/{table_name}` template.
4. A successful `search` call (cohort=A1).
5. A successful `aggregate` `avg` grouped by `cohort`.
6. A successful `insert` returning the new id.
7. An error call: `search` with `table="ghosts"` → clear error message.

## 9. Client integration

### Claude Code

The repo root contains `.mcp.json`:

```json
{
  "mcpServers": {
    "sqlite-lab": {
      "type": "stdio",
      "command": "python",
      "args": ["${workspaceFolder}/implementation/mcp_server.py"],
      "env": {}
    }
  }
}
```

Open the folder in Claude Code; the server appears as `sqlite-lab`. Reference
resources via `@sqlite-lab:schema://database` or
`@sqlite-lab:schema://table/students`.

### Codex

Copy `client-configs/codex.config.toml` into `~/.codex/config.toml`
(replace the absolute path), then check with `codex mcp list`.

### Gemini CLI

```bash
bash client-configs/gemini-add.sh
gemini mcp list           # expect: sqlite-lab  Connected
gemini --allowed-mcp-server-names sqlite-lab --yolo \
  -p "Use the sqlite-lab MCP server and show the top 2 students by score."
```

## 10. Demo script (≈ 2 minutes)

1. `python implementation/init_db.py` — show DB created.
2. `python implementation/verify_server.py` — all 13 checks pass.
3. Launch Inspector: tools + resources appear with schemas.
4. Call `search students {cohort:"A1"}, order_by score desc`.
5. Call `aggregate avg score group_by cohort`.
6. Call `insert students {name,cohort,score}` — show new id in payload.
7. Read `schema://database`, then `schema://table/students`.
8. Call `search ghosts` — show the clear validation error.
9. Switch to Claude Code or Gemini CLI, ask a natural-language question
   that triggers the MCP server, show the model using the tools.

## 11. Bonus features implemented

- **HTTP transport flag** (`--transport http`) — ready for SSE/HTTP demos.
- **Pagination metadata** — every `search` response includes
  `page.{limit, offset, returned, total, has_more, next_offset}`.
- **Output cap** — `limit` is clamped to 200 to avoid runaway payloads.
- **Structured errors** — tools return `{"error": "..."}` instead of raising,
  so MCP clients receive readable feedback.

## 12. Troubleshooting

| Symptom                                | Fix                                                                                  |
|----------------------------------------|--------------------------------------------------------------------------------------|
| `ModuleNotFoundError: fastmcp`         | `pip install -r implementation/requirements.txt` in the active venv                  |
| Inspector says `spawn python ENOENT`   | Use the **absolute** path to the Python executable from the venv (`which python`)    |
| Gemini list shows `Disconnected`       | Run `python implementation/mcp_server.py` once standalone to confirm it boots OK     |
| Output truncated in Claude Code        | Raise `MAX_MCP_OUTPUT_TOKENS` env var                                                |

## 13. Demo media

**Demo video (~2 minutes):** [docs/demo.mp4](../docs/demo.mp4)

**MCP Inspector screenshots:**

| # | Screenshot | Description |
|---|---|---|
| 1 | [01-connected.png](../docs/screenshots/01-connected.png) | Inspector connected to the FastMCP server |
| 2 | [02-tools-list.png](../docs/screenshots/02-tools-list.png) | All three tools (`search`, `insert`, `aggregate`) discovered with schemas |
| 3 | [03-resources-list.png](../docs/screenshots/03-resources-list.png) | Schema resource + per-table resource template visible |
| 4 | [04-search-success.png](../docs/screenshots/04-search-success.png) | `search` cohort=A1 ordered by score (success) |
| 5 | [05-aggregate-success.png](../docs/screenshots/05-aggregate-success.png) | `aggregate avg score group_by cohort` (success) |
| 6 | [06-insert-success.png](../docs/screenshots/06-insert-success.png) | `insert` returning the new row + generated id |
| 7 | [07-search-error.png](../docs/screenshots/07-search-error.png) | Validation error: `search` on unknown table |

## 14. Rubric self-assessment

| Section | Max | Achieved | Evidence |
|---|---|---|---|
| 1. Server Foundation | 20 | 20 | `db.py` / `mcp_server.py` separation, `init_db.py` reproducible, FastMCP boots cleanly |
| 2. Required Tools | 30 | 30 | `search` w/ filters+order+pagination, `insert` returns payload+id, `aggregate` supports count/avg/sum/min/max |
| 3. MCP Resources | 15 | 15 | `schema://database` + `schema://table/{table_name}` resource template |
| 4. Safety & Errors | 15 | 15 | Allow-list identifiers, parameterized SQL, 5 rejection paths covered |
| 5. Verification | 10 | 10 | `verify_server.py` (13/13 PASS), pytest (26/26 PASS) |
| 6. Client + Demo | 10 | 10 | `.mcp.json`, Codex/Gemini configs, 7 screenshots, demo video |
| **Bonus** | +10 | +5 | HTTP/SSE transport flag + pagination metadata + output cap |
| **Total** | 100+10 | **100 + 5** | |

