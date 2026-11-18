---
name: gemini-web-mcp
description: Orchestrate Google Gemini Web (gemini.google.com/app) via the gemini-web-mcp Playwright server. Use when the user asks to query Gemini Web, get a second opinion from Gemini Pro or Thinking models, analyze local PDFs/images/code/videos through a persistent Gemini Web session, or continue an existing gemini.google.com conversation thread without consuming paid Gemini API quota.
---

# gemini-web-mcp

**English** | [Bahasa Indonesia](SKILL.id.md)

Drive a persistent, authenticated `gemini.google.com/app` browser session through the `gemini-web-mcp` MCP server for multi-turn chat, dynamic model switching, and multi-file analysis.

## When to Use

- Delegate complex reasoning, second-opinion code reviews, or web-grounded synthesis to Gemini Web (`Flash`, `Thinking`, or `Pro` models).
- Analyze local documents, PDFs, screenshots, source files, or videos by uploading them directly into a `gemini.google.com` thread.
- Continue or inspect existing conversations from the user's Gemini Web history without requiring a paid AI Studio or Vertex AI API key.

## Steps

### 1. Verify Session Health First

Call `gemini_status` at the start of a new session or whenever a tool returns an authentication or selector error.

- Confirm `"authenticated": true` in the JSON output before sending prompts or uploading files.
- If `"authenticated": false`, call `gemini_setup_auth` so the user can complete the one-time Google sign-in in the headed browser window (or via the Xvfb/noVNC portal on a remote server).

### 2. Match the Model to the Task

Select the appropriate Gemini Web model either inline via the `model` parameter on `gemini_chat` or explicitly via `gemini_select_model`:

- Use `"Flash"` (or `"Fast"`) for quick lookups, summarization, and lightweight file extraction.
- Use `"Thinking"` or `"Pro"` for multi-step math, architecture reviews, debugging, and deep synthesis.
- If `gemini_select_model` reports `"switched": false`, inspect `"available_models"` in its response and retry with one of the exact labels listed for that Google account.

### 3. Execute Single-Turn, Multi-Turn, or Multimodal Queries

Prefer `gemini_chat` as the primary workhorse tool because it handles model selection, file attachment, prompt injection, and streaming completion in one atomic call:

```json
{
  "prompt": "Audit this architecture spec for race conditions and summarize fixes in a table.",
  "new_chat": true,
  "model": "Pro",
  "file_paths": ["/abs/path/to/architecture.pdf"]
}
```

- Capture `"conversation_url"` from the tool output whenever you plan to ask follow-up questions.
- Pass that exact `"conversation_url"` back into subsequent `gemini_chat` calls (with `"new_chat": false`) to preserve full multi-turn context.
- Set `"new_chat": true` (or call `gemini_new_chat`) when switching to an unrelated topic so prior context does not pollute the new answer.
- Use `gemini_list_recent_chats` when the user asks to resume an earlier thread from their Gemini sidebar.

## Tool Reference

| Tool | Primary Purpose | Key Parameters |
| :--- | :--- | :--- |
| `gemini_status` | Check login state, active model badge, current URL, and DOM selector health | *(none)* |
| `gemini_setup_auth` | Open headed/noVNC browser window for one-time Google login | `timeout_seconds` (default `300`) |
| `gemini_chat` | Send prompt, optionally switch model & attach files, return clean Markdown | `prompt`, `new_chat`, `conversation_url`, `model`, `file_paths`, `timeout_seconds` |
| `gemini_select_model` | Switch active Gemini Web model and list available options | `model_name` |
| `gemini_upload_files` | Stage local files in the composer, optionally submitting a prompt | `file_paths`, `prompt`, `new_chat` |
| `gemini_list_recent_chats` | Retrieve recent conversation titles and URLs from the sidebar | `limit` (default `15`) |
| `gemini_new_chat` | Navigate to a clean thread at `gemini.google.com/app` | *(none)* |

## Gotchas

- **Always pass absolute paths in `file_paths`**: The MCP server validates files on the host where `gemini-web-mcp` runs. Relative paths may resolve against the server working directory rather than your project root. Never pass local workstation paths to a remote VPS `StreamableHTTP` server unless those files exist on the remote host.
- **Increase `timeout_seconds` for `Thinking` / `Pro` and large uploads**: Deep reasoning or multi-PDF analysis on `gemini.google.com` can exceed 120 seconds. Pass `timeout_seconds: 300` on heavy requests to avoid premature timeouts.
- **Serialize calls against one profile**: A single browser profile shares one active tab lock. Issue `gemini_chat` calls sequentially rather than firing concurrent prompts against the same `gemini-web-mcp` instance unless each call explicitly passes its own `conversation_url`.
- **Handle UI rollouts gracefully**: If `gemini_status` shows `null` under `matched_selectors`, Google likely updated a DOM attribute on `gemini.google.com/app`. Inspect `src/gemini_web_mcp/selectors.py` and append the updated selector to the top of the relevant fallback list.
