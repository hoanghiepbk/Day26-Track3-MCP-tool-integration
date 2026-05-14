# Submission — Day 26 / Track 3: MCP tool integration

| Field | Value |
|---|---|
| **Student** | Phạm Hữu Hoàng Hiệp |
| **Student ID** | 2A202600415 |
| **Lab** | Build a Database MCP Server with FastMCP and SQLite |
| **Lab spec** | [README.md](README.md) |
| **Rubric** | [Rubric.md](Rubric.md) |

## What was built

A FastMCP server that exposes a seeded SQLite database through:

- 3 MCP tools — `search`, `insert`, `aggregate`
- 2 MCP resources — `schema://database`, `schema://table/{table_name}`
- Strict input validation (allow-list of tables/columns/operators/metrics)
- Parameterized SQL — no string concatenation of user input

## Where to look

| What | Where |
|---|---|
| Full submission write-up (setup, demo script, rubric self-check) | [implementation/README.md](implementation/README.md) |
| Server source | [implementation/mcp_server.py](implementation/mcp_server.py) |
| DB adapter + validation | [implementation/db.py](implementation/db.py) |
| Schema + seed | [implementation/init_db.py](implementation/init_db.py) |
| Smoke test (13 checks) | [implementation/verify_server.py](implementation/verify_server.py) |
| Pytest suite (26 cases) | [implementation/tests/test_server.py](implementation/tests/test_server.py) |
| Claude Code config | [.mcp.json](.mcp.json) |
| Codex / Gemini configs | [client-configs/](client-configs/) |
| Demo video (~2 min) | [docs/demo.mp4](docs/demo.mp4) |
| 7 Inspector screenshots | [docs/screenshots/](docs/screenshots/) |

## Quick start

```bash
pip install -r implementation/requirements.txt
python implementation/init_db.py
python implementation/verify_server.py          # expect: ALL PASS
python -m pytest implementation/tests/ -q       # expect: 26 passed
python implementation/mcp_server.py             # run the server (stdio)
```

## Rubric self-assessment

| Section | Max | Achieved |
|---|---|---|
| Server Foundation | 20 | 20 |
| Required Tools | 30 | 30 |
| MCP Resources | 15 | 15 |
| Safety & Errors | 15 | 15 |
| Verification | 10 | 10 |
| Client + Demo | 10 | 10 |
| Bonus (HTTP transport, pagination, output cap) | +10 | +5 |
| **Total** | **100 + 10** | **100 + 5** |
