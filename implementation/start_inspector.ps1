# PowerShell helper: launch MCP Inspector against this lab server.
# Requires: Node.js >= 18 (npx) and Python with fastmcp installed.

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = if ($env:PYTHON) { $env:PYTHON } else { "python" }

New-Item -ItemType Directory -Force "$here\.npm-cache" | Out-Null
$env:NPM_CONFIG_CACHE = "$here\.npm-cache"

npx -y @modelcontextprotocol/inspector $python "$here\mcp_server.py"
