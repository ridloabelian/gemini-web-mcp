"""Definisi FastMCP server dan middleware keamanan HTTP Bearer Token."""

from __future__ import annotations

import hmac
import json
from typing import Any

from .browser import GeminiBrowserController
from .selectors import validate_local_files


class BearerAuthASGIMiddleware:
    """ASGI middleware untuk memproteksi endpoint MCP HTTP/SSE publik dengan Bearer token."""

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
    """Bangun instance `FastMCP` dengan 7 tools lengkap untuk `gemini.google.com`."""
    from mcp.server.fastmcp import FastMCP  # type: ignore[import-not-found]

    mcp = FastMCP(
        "gemini-web-mcp",
        instructions=(
            "MCP server pembungkus gemini.google.com berbasis Playwright/Patchright "
            "dengan persistent browser profile. Mendukung chat multi-turn, pemilihan "
            "model (Flash/Thinking/Pro), riwayat percakapan, dan upload file lokal."
        ),
        host=host,
        port=port,
    )

    @mcp.tool()
    async def gemini_setup_auth(timeout_seconds: int = 300) -> str:
        """
        Buka browser interaktif (headed / Xvfb noVNC) ke gemini.google.com/app untuk
        login akun Google pertama kali dan menyimpan sesi ke persistent profile.
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
        Kirim prompt ke gemini.google.com/app dan kembalikan respons dalam format Markdown bersih.

        Args:
            prompt: Teks pertanyaan atau instruksi ke Gemini.
            new_chat: Mulai percakapan baru sebelum mengirim pesan.
            conversation_url: Opsional URL thread spesifik untuk melanjutkan diskusi lama.
            model: Opsional nama model yang ingin diaktifkan lebih dulu (mis. "Flash", "Thinking", "Pro").
            file_paths: Opsional daftar path file lokal untuk dilampirkan bersama prompt.
            timeout_seconds: Batas tunggu maksimum jawaban selesai (detik).
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
        Ganti model aktif pada antarmuka web gemini.google.com (contoh: 'Flash', 'Fast',
        'Thinking', 'Pro'). Mengembalikan daftar model yang tersedia jika nama tidak cocok.
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
        Unggah satu atau beberapa file lokal (PDF, gambar, kode, dokumen, video) ke Gemini Web.
        Jika `prompt` diberikan, langsung kirim instruksi setelah proses unggah selesai.
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
        """Ambil daftar percakapan terbaru beserta URL-nya dari sidebar Gemini Web."""
        async with controller.lock:
            res = await controller.list_recent_chats(limit=limit)
            return json.dumps(res, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def gemini_new_chat() -> str:
        """Buka halaman percakapan baru yang bersih di gemini.google.com/app."""
        async with controller.lock:
            res = await controller.start_new_chat()
            return json.dumps(res, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def gemini_status() -> str:
        """
        Periksa status login persistent profile, model yang sedang aktif, URL saat ini,
        serta diagnostik kecocokan selector DOM Gemini Web.
        """
        async with controller.lock:
            res = await controller.inspect_status()
            return json.dumps(res, ensure_ascii=False, indent=2)

    return mcp
