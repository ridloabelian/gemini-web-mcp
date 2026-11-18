#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_DIR}"

if ! command -v uv >/dev/null 2>&1; then
  echo "[bootstrap] Installing uv..." >&2
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="${HOME}/.local/bin:${PATH}"
fi

echo "[bootstrap] Syncing Python dependencies..." >&2
uv sync

echo "[bootstrap] Installing Patchright Chromium..." >&2
uv run patchright install chromium

if [ ! -f .env ]; then
  cp .env.example .env
  echo "[bootstrap] Created .env from .env.example" >&2
fi

if [ "${1:-}" != "--skip-login" ]; then
  echo "[bootstrap] Launching interactive browser for one-time Google sign-in..." >&2
  uv run gemini-web-mcp --setup-auth
fi

echo "" >&2
echo "[bootstrap] Done! Copy-paste MCP client configuration below:" >&2
uv run gemini-web-mcp --doctor
