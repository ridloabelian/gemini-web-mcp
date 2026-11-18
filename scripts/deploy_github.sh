#!/usr/bin/env bash
set -euo pipefail

REPO_NAME="${1:-gemini-web-mcp}"
VISIBILITY="${2:---public}"

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_DIR}"

if ! command -v gh >/dev/null 2>&1; then
  echo "Error: GitHub CLI ('gh') belum terinstal. Instal dari https://cli.github.com/" >&2
  exit 1
fi

if [ ! -d .git ]; then
  git init -b main
fi

git add .
git commit -m "feat: initial plug-and-play Playwright MCP server for gemini.google.com" || true
gh repo create "${REPO_NAME}" "${VISIBILITY}" --source=. --remote=origin --push
