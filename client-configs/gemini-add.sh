#!/usr/bin/env bash
# Register the lab server with Gemini CLI.
# Edit PYTHON_BIN / REPO if your paths differ.

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$(command -v python)}"

gemini mcp add sqlite-lab \
  "$PYTHON_BIN" \
  "$REPO/implementation/mcp_server.py" \
  --description "SQLite lab FastMCP server" \
  --timeout 10000

gemini mcp list
