#!/usr/bin/env bash
set -euo pipefail

export DISPLAY="${DISPLAY:-:99}"
MCP_PORT="${MCP_PORT:-8765}"
NOVNC_PORT="${NOVNC_PORT:-6080}"
ENABLE_NOVNC="${ENABLE_NOVNC:-true}"

rm -f /tmp/.X99-lock

echo "[entrypoint] Starting Xvfb virtual display on ${DISPLAY}..." >&2
Xvfb "${DISPLAY}" -screen 0 1366x900x24 -ac +extension GLX +render -noreset &
sleep 1

fluxbox >/dev/null 2>&1 &

if [ "${ENABLE_NOVNC}" = "true" ]; then
  echo "[entrypoint] Starting x11vnc & noVNC on port ${NOVNC_PORT} for initial Google sign-in..." >&2
  x11vnc -display "${DISPLAY}" -forever -shared -nopw -rfbport 5900 -quiet &
  websockify --web=/usr/share/novnc/ "${NOVNC_PORT}" localhost:5900 >/dev/null 2>&1 &
  echo "[entrypoint] Open http://localhost:${NOVNC_PORT}/vnc.html and invoke gemini_setup_auth to sign in." >&2
fi

exec uv run --no-dev gemini-web-mcp \
  --transport streamable-http \
  --host 0.0.0.0 \
  --port "${MCP_PORT}" \
  --headed
