<p align="center">
  <img src="assets/hero-banner.svg" alt="gemini-web-mcp hero banner" width="100%" />
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11%2B-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.11+" />
  <img src="https://img.shields.io/badge/Protocol-MCP-6366F1?style=flat-square" alt="Model Context Protocol" />
  <img src="https://img.shields.io/badge/Engine-Patchright%20%2F%20Playwright-2EAD33?style=flat-square&logo=playwright&logoColor=white" alt="Patchright / Playwright" />
  <img src="https://img.shields.io/badge/Docker-Xvfb%20%2B%20noVNC-2496ED?style=flat-square&logo=docker&logoColor=white" alt="Docker Xvfb + noVNC" />
  <img src="https://img.shields.io/badge/License-MIT-0EA5E9?style=flat-square" alt="MIT License" />
</p>

<p align="center">
  <strong>English</strong> | <a href="README.id.md">Bahasa Indonesia</a>
</p>

# gemini-web-mcp

A plug-and-play **Model Context Protocol (MCP)** server built on **Playwright / Patchright** that wraps [`gemini.google.com/app`](https://gemini.google.com/app) using a **persistent browser profile**.

Connect it locally (`stdio`) to **Antigravity (`agy`)**, **Claude Code / Desktop**, or **Cursor**, or deploy it as a remote **Streamable HTTP** MCP server on a headless Linux VPS / Homelab with built-in **Xvfb + noVNC** and **Bearer Token** authentication for autonomous orchestrators like **Hermes Agent**.

## Architecture Overview

<p align="center">
  <img src="assets/architecture.svg" alt="gemini-web-mcp system architecture" width="100%" />
</p>

## Key Features

- **Persistent Google Session**: Sign in once (`--setup-auth`); cookies and IndexedDB state stay persisted in your local profile directory or Docker volume.
- **Anti-Bot / Stealth Ready**: Prioritizes `patchright` alongside Chrome anti-automation flags to avoid Google's *"This browser or app may not be secure"* login block, and supports attaching to a running Chrome instance via `--cdp-url`.
- **Single-Turn & Multi-Turn Chat (`gemini_chat`)**: Resume any thread via `conversation_url`, inject multi-line prompts atomically without premature `Enter` submission, detect streaming completion via DOM stability polling, and extract clean Markdown (preserving fenced code blocks and tables).
- **Dynamic Model Switching (`gemini_select_model`)**: Switch between *Fast / Flash*, *Thinking*, *Pro*, and other models available on your Google account.
- **Multi-File Upload (`gemini_upload_files`)**: Upload local PDFs, images, source code, documents, or videos directly into a Gemini conversation.
- **Conversation History & Diagnostics (`gemini_list_recent_chats`, `gemini_new_chat`, `gemini_status`)**: List recent threads from the Gemini sidebar and inspect live DOM selector health.
- **Bundled Agent Skill (`skills/gemini-web-mcp/`)**: Ready-to-install `SKILL.md` (English default + [Bahasa Indonesia](skills/gemini-web-mcp/SKILL.id.md)) for Claude Code, Antigravity, Cursor, and Hermes Agent.

## Quick Start 1: Local Machine (Plug & Play)

Requires Python 3.11+. Clone the repository and run the one-command bootstrap script:

```bash
git clone https://github.com/ridloabelian/gemini-web-mcp.git
cd gemini-web-mcp
chmod +x scripts/bootstrap.sh
./scripts/bootstrap.sh
```

What `scripts/bootstrap.sh` does automatically:
1. Installs `uv` (if missing) and syncs all package dependencies from `pyproject.toml`.
2. Installs the Patchright Chromium binary.
3. Launches a headed browser window at `https://gemini.google.com/app` for your one-time Google sign-in.
4. Prints a ready-to-paste MCP client JSON snippet with your exact local path.

### Local MCP Client Configuration (`stdio`)

Add this entry to your MCP client configuration (`.mcp.json`, Claude Desktop, Cursor, or Antigravity):

```json
{
  "mcpServers": {
    "gemini-web": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/absolute/path/to/gemini-web-mcp",
        "gemini-web-mcp"
      ],
      "env": {
        "GEMINI_PROFILE_DIR": "~/.gemini-web-mcp/profile",
        "GEMINI_HEADLESS": "true",
        "GEMINI_BROWSER_CHANNEL": "chrome"
      }
    }
  }
}
```

Or run directly via `uvx` without keeping a local clone (once your profile directory has been authenticated with `--setup-auth`):

```json
{
  "mcpServers": {
    "gemini-web": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/ridloabelian/gemini-web-mcp.git",
        "gemini-web-mcp"
      ]
    }
  }
}
```

## Installing the Bundled Agent Skill

This repository ships with a pre-built agent skill under `skills/gemini-web-mcp/` (`SKILL.md` in English by default, plus `SKILL.id.md` in Bahasa Indonesia) teaching AI coding agents how to manage sessions, select models, and attach files reliably:

```bash
# Via Vercel / Agent Skills CLI
npx skills add ridloabelian/gemini-web-mcp

# Claude Code
cp -r skills/gemini-web-mcp ~/.claude/skills/

# Antigravity / Hermes Agent workspace
mkdir -p ~/.agent/skills && cp -r skills/gemini-web-mcp ~/.agent/skills/
```

## Quick Start 2: Headless VPS / Homelab Deployment (Docker + Xvfb + noVNC)

On headless Linux servers, the Docker image runs a real *headed* Chromium session inside an **Xvfb (`:99`)** virtual display—bypassing headless browser fingerprinting—paired with a localhost-bound **noVNC** portal for your initial Google login:

```bash
git clone https://github.com/ridloabelian/gemini-web-mcp.git
cd gemini-web-mcp
cp .env.example .env
# Set a strong secret in GEMINI_AUTH_TOKEN inside .env!
docker compose up -d --build
```

### One-Time Google Sign-In on a Remote Server:
1. Forward the noVNC port securely from your workstation over SSH:
   ```bash
   ssh -L 6080:127.0.0.1:6080 user@your-server-ip
   ```
2. Open `http://localhost:6080/vnc.html` in your local browser, click **Connect**, and complete the Google sign-in inside the Chromium window.
3. Once signed in to Gemini, your session is persisted in the `gemini_profile` Docker volume. You can disable noVNC afterward by setting `ENABLE_NOVNC=false` in `.env` and running `docker compose up -d`.

### Remote MCP Client Configuration (`StreamableHTTP`)

The server exposes `/mcp` (Streamable HTTP) and `/healthz` (unauthenticated health probe) on port `8765`. Behind a reverse proxy or Cloudflare Tunnel:

```json
{
  "mcpServers": {
    "gemini-web-remote": {
      "url": "https://your-mcp-domain.example.com/mcp",
      "headers": {
        "Authorization": "Bearer YOUR_SECRET_GEMINI_AUTH_TOKEN"
      }
    }
  }
}
```

## Available MCP Tools

| Tool Name | Description |
| :--- | :--- |
| `gemini_setup_auth` | Opens an interactive headed browser window to complete one-time Google login and persist session state. |
| `gemini_chat` | Sends a prompt (supports `new_chat`, `conversation_url`, inline `model` selection, and `file_paths` attachments) and returns clean Markdown. |
| `gemini_select_model` | Switches the active model in Gemini's mode switcher (`Flash`, `Thinking`, `Pro`, etc.) and lists available options. |
| `gemini_upload_files` | Uploads one or more local files into the active Gemini thread, with an optional follow-up `prompt`. |
| `gemini_list_recent_chats` | Scrapes recent conversation titles and URLs from the `gemini.google.com` sidebar. |
| `gemini_new_chat` | Opens a fresh conversation thread at `gemini.google.com/app`. |
| `gemini_status` | Checks authentication state, active model badge, current URL, and DOM selector health. |

## Environment Variables (`.env`)

| Variable | Default | Description |
| :--- | :--- | :--- |
| `GEMINI_PROFILE_DIR` | `~/.gemini-web-mcp/profile` | Persistent Chromium/Chrome user data directory. |
| `GEMINI_HEADLESS` | `true` | Run browser headless (`false` is recommended when running inside Docker Xvfb). |
| `GEMINI_BROWSER_CHANNEL` | `chrome` | Browser channel (`chrome`, `msedge`, or empty `""` for bundled Chromium). |
| `GEMINI_CDP_URL` | *(empty)* | Optional CDP endpoint to attach to an already-running Chrome instance (e.g., `http://127.0.0.1:9222`). |
| `GEMINI_RESPONSE_TIMEOUT` | `180` | Maximum wait time in seconds for streaming responses to complete. |
| `GEMINI_AUTH_TOKEN` | *(empty)* | Optional Bearer token protecting HTTP/SSE MCP endpoints. |

## Testing & CI

```bash
make test
```

A GitHub Actions workflow template is included at `examples/github-actions-ci.yml` (copy to `.github/workflows/ci.yml` to enable automated checks on push/PR).

## License

MIT License
