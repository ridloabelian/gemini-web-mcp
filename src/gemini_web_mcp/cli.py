"""Entrypoint CLI `gemini-web-mcp` untuk mode lokal (`stdio`) maupun server (`streamable-http`)."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import shutil
import sys
from pathlib import Path

from .browser import GeminiBrowserController, load_playwright_backend
from .config import Settings, load_settings
from .server import BearerAuthASGIMiddleware, build_mcp_server

# PENTING: Jangan pernah menulis log ke stdout karena dipakai JSON-RPC pada mode stdio.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("gemini-web-mcp.cli")


def build_arg_parser(defaults: Settings) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gemini-web-mcp",
        description="Plug-and-Play Playwright/Patchright MCP Server untuk gemini.google.com",
    )
    parser.add_argument(
        "--profile-dir",
        type=Path,
        default=defaults.profile_dir,
        help=f"Direktori persistent browser profile (default: {defaults.profile_dir})",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Paksa jalankan browser dengan jendela terlihat (override GEMINI_HEADLESS=true)",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Paksa jalankan browser dalam mode headless",
    )
    parser.add_argument(
        "--channel",
        type=str,
        default=defaults.browser_channel,
        help="Browser channel Playwright: 'chrome', 'msedge', atau '' untuk Chromium bawaan",
    )
    parser.add_argument(
        "--cdp-url",
        type=str,
        default=defaults.cdp_url,
        help="Endpoint CDP Chrome aktif (contoh: http://127.0.0.1:9222)",
    )
    parser.add_argument(
        "--setup-auth",
        action="store_true",
        help="Buka browser interaktif untuk login akun Google lalu simpan persistent profile",
    )
    parser.add_argument(
        "--doctor",
        action="store_true",
        help="Cek kesiapan environment dan cetak snippet konfigurasi MCP siap pakai",
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default="stdio",
        help="Protokol transport MCP (default: stdio)",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host bind untuk transport HTTP/SSE (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Port bind untuk transport HTTP/SSE (default: 8765)",
    )
    parser.add_argument(
        "--auth-token",
        type=str,
        default=defaults.auth_token,
        help="Bearer token opsional untuk mengamankan endpoint HTTP/SSE",
    )
    return parser


def run_doctor(settings: Settings) -> int:
    """Periksa instalasi dependensi dan tampilkan contoh konfigurasi MCP ke stderr."""
    try:
        _, backend = load_playwright_backend()
    except Exception as exc:
        backend = f"missing ({exc})"

    uv_path = shutil.which("uv") or "uv"
    report = {
        "playwright_backend": backend,
        "profile_dir": str(settings.profile_dir),
        "profile_exists": settings.profile_dir.exists(),
        "headless_default": settings.headless,
        "browser_channel": settings.browser_channel or "chromium",
        "cdp_url": settings.cdp_url or None,
        "auth_token_configured": bool(settings.auth_token),
        "sample_stdio_mcp_config": {
            "mcpServers": {
                "gemini-web": {
                    "command": uv_path,
                    "args": [
                        "run",
                        "--directory",
                        str(Path.cwd()),
                        "gemini-web-mcp",
                    ],
                    "env": {
                        "GEMINI_PROFILE_DIR": str(settings.profile_dir),
                        "GEMINI_HEADLESS": "true",
                    },
                }
            }
        },
    }
    sys.stderr.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    defaults = load_settings()
    parser = build_arg_parser(defaults)
    args = parser.parse_args(argv)

    headless = defaults.headless
    if args.headed:
        headless = False
    elif args.headless:
        headless = True

    settings = Settings(
        profile_dir=args.profile_dir.expanduser(),
        headless=headless,
        browser_channel=args.channel,
        cdp_url=args.cdp_url,
        base_url=defaults.base_url,
        response_timeout=defaults.response_timeout,
        auth_token=args.auth_token,
    )

    if args.doctor:
        return run_doctor(settings)

    controller = GeminiBrowserController(settings)

    if args.setup_auth:
        logger.info("Membuka browser untuk login ke %s ...", settings.base_url)
        try:
            outcome = asyncio.run(controller.setup_interactive_auth(timeout_seconds=300))
            sys.stderr.write(json.dumps(outcome, ensure_ascii=False, indent=2) + "\n")
            return 0 if outcome.get("authenticated") else 1
        finally:
            asyncio.run(controller.close())

    mcp_server = build_mcp_server(controller, host=args.host, port=args.port)

    try:
        if args.transport in {"streamable-http", "sse"}:
            import uvicorn  # type: ignore[import-not-found]

            asgi_app = (
                mcp_server.streamable_http_app()
                if args.transport == "streamable-http"
                else mcp_server.sse_app()
            )
            wrapped_app = BearerAuthASGIMiddleware(asgi_app, settings.auth_token)
            logger.info(
                "Menjalankan %s MCP server pada http://%s:%d (Bearer auth=%s)",
                args.transport,
                args.host,
                args.port,
                "aktif" if settings.auth_token else "nonaktif",
            )
            uvicorn.run(wrapped_app, host=args.host, port=args.port, log_level="info")
        else:
            mcp_server.run(transport="stdio")
    finally:
        try:
            asyncio.run(controller.close())
        except Exception:
            pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
