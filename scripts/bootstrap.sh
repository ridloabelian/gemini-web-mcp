#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_DIR}"

if ! command -v uv >/dev/null 2>&1; then
  echo "[bootstrap] Menginstal uv..." >&2
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="${HOME}/.local/bin:${PATH}"
fi

echo "[bootstrap] Sinkronisasi paket Python..." >&2
uv sync

echo "[bootstrap] Menginstal Chromium untuk Patchright..." >&2
uv run patchright install chromium

if [ ! -f .env ]; then
  cp .env.example .env
  echo "[bootstrap] File .env dibuat dari .env.example" >&2
fi

if [ "${1:-}" != "--skip-login" ]; then
  echo "[bootstrap] Membuka jendela login Google pertama kali..." >&2
  uv run gemini-web-mcp --setup-auth
fi

echo "" >&2
echo "[bootstrap] Selesai! Berikut konfigurasi MCP siap tempel:" >&2
uv run gemini-web-mcp --doctor
