#!/usr/bin/env bash
# Launch MCP Inspector against this lab server.
#
# Requires: Node.js >= 18 (npx).
# Usage: ./start_inspector.sh

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${PYTHON:-python}"

mkdir -p "$HERE/.npm-cache"
NPM_CONFIG_CACHE="$HERE/.npm-cache" \
  npx -y @modelcontextprotocol/inspector "$PYTHON" "$HERE/mcp_server.py"
