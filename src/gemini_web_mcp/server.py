"""FastMCP server registration and HTTP Bearer token ASGI authentication middleware."""

from __future__ import annotations

import hmac
import json
from typing import Any

from .browser import GeminiBrowserController
from .selectors import validate_local_files


class BearerAuthASGIMiddleware:
    """ASGI middleware protecting HTTP/SSE MCP endpoints with a static Bearer token."""

    def __init__(self, app: Any, expected_token: str) -> None:
        self.app = app
        self.expected_token = expected_token

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if path == "/healthz":
            body = json.dumps({"status": "ok", "service": "gemini-web-mcp"}).encode("utf-8")
            await send(
                {
                    "type": "http.response.start",
                    "status": 200,
                    "headers": [(b"content-type", b"application/json")],
                }
            )
            await send({"type": "http.response.body", "body": body})
            return

        if not self.expected_token:
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers") or [])
        auth_header = headers.get(b"authorization", b"").decode("utf-8", errors="ignore")
        provided = ""
        if auth_header.lower().startswith("bearer "):
            provided = auth_header[7:].strip()

        if not provided or not hmac.compare_digest(provided, self.expected_token):
            body = json.dumps({"error": "Unauthorized: invalid or missing Bearer token"}).encode(
                "utf-8"
            )
            await send(
                {
                    "type": "http.response.start",
                    "status": 401,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"www-authenticate", b"Bearer"),
                    ],
                }
            )
            await send({"type": "http.response.body", "body": body})
            return

        await self.app(scope, receive, send)


def build_mcp_server(
    controller: GeminiBrowserController,
    host: str = "127.0.0.1",
    port: int = 8765,
) -> Any:
    """Build the FastMCP instance exposing all `gemini.google.com` automation tools."""
    from mcp.server.fastmcp import FastMCP  # type: ignore[import-not-found]

    mcp = FastMCP(
        "gemini-web-mcp",
        instructions=(
            "Playwright/Patchright MCP server wrapping gemini.google.com with a "
            "persistent browser profile. Supports multi-turn chat, dynamic model "
            "switching (Flash/Thinking/Pro), recent chat discovery, and local file uploads."
        ),
        host=host,
        port=port,
    )

    @mcp.tool()
    async def gemini_setup_auth(timeout_seconds: int = 300) -> str:
        """
        Launch an interactive headed browser window (or Xvfb/noVNC session) at
        gemini.google.com/app to sign in to Google once and persist credentials.
        """
        async with controller.lock:
            res = await controller.setup_interactive_auth(timeout_seconds=timeout_seconds)
            return json.dumps(res, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def gemini_chat(
        prompt: str,
        new_chat: bool = False,
        conversation_url: str | None = None,
        model: str | None = None,
        file_paths: list[str] | None = None,
        timeout_seconds: int | None = None,
    ) -> str:
        """
        Send a prompt to gemini.google.com/app and return the full response as clean Markdown.

        Args:
            prompt: Question or instruction for Gemini.
            new_chat: Start a fresh conversation thread before sending.
            conversation_url: Specific Gemini thread URL to resume an existing conversation.
            model: Optional model name to select before sending (e.g. "Flash", "Thinking", "Pro").
            file_paths: Optional list of local file paths to upload with the prompt.
            timeout_seconds: Maximum wait time in seconds for streaming completion.
        """
        async with controller.lock:
            res = await controller.send_chat(
                prompt=prompt,
                new_chat=new_chat,
                conversation_url=conversation_url,
                model=model,
                file_paths=file_paths,
                timeout_seconds=timeout_seconds,
            )
            return json.dumps(res, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def gemini_select_model(model_name: str) -> str:
        """
        Switch the active model in the gemini.google.com mode switcher (e.g. 'Flash',
        'Fast', 'Thinking', 'Pro'). Returns available menu options if unmatched.
        """
        async with controller.lock:
            res = await controller.select_model(model_name=model_name)
            return json.dumps(res, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def gemini_upload_files(
        file_paths: list[str],
        prompt: str | None = None,
        new_chat: bool = False,
    ) -> str:
        """
        Upload one or more local files (PDF, images, code, docs, video) into Gemini Web.
        If `prompt` is provided, automatically submits the prompt once upload completes.
        """
        async with controller.lock:
            validated = validate_local_files(file_paths)
            if prompt and prompt.strip():
                res = await controller.send_chat(
                    prompt=prompt,
                    new_chat=new_chat,
                    file_paths=[str(p) for p in validated],
                )
                return json.dumps(res, ensure_ascii=False, indent=2)

            page = await controller.ensure_page()
            if new_chat:
                await page.goto(
                    controller.settings.base_url,
                    wait_until="domcontentloaded",
                    timeout=60_000,
                )
            upload_res = await controller.upload_files(validated, page=page)
            upload_res["conversation_url"] = page.url
            return json.dumps(upload_res, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def gemini_list_recent_chats(limit: int = 15) -> str:
        """List recent conversation titles and URLs from the Gemini Web sidebar."""
        async with controller.lock:
            res = await controller.list_recent_chats(limit=limit)
            return json.dumps(res, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def gemini_new_chat() -> str:
        """Open a fresh conversation thread at gemini.google.com/app."""
        async with controller.lock:
            res = await controller.start_new_chat()
            return json.dumps(res, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def gemini_status() -> str:
        """
        Inspect persistent profile authentication status, active model badge, current URL,
        and live DOM selector matches on gemini.google.com.
        """
        async with controller.lock:
            res = await controller.inspect_status()
            return json.dumps(res, ensure_ascii=False, indent=2)

    return mcp
