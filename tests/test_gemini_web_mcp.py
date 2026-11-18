from __future__ import annotations

import ast
import asyncio
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from gemini_web_mcp.cli import build_arg_parser
from gemini_web_mcp.config import load_settings
from gemini_web_mcp.selectors import SELECTORS, normalize_model_query, validate_local_files
from gemini_web_mcp.server import BearerAuthASGIMiddleware


class GeminiWebMcpUnitTests(unittest.TestCase):
    def test_selector_groups_complete(self) -> None:
        required = {
            "prompt_input",
            "send_button",
            "stop_generating",
            "response_containers",
            "model_switcher_button",
            "model_menu_items",
            "upload_trigger_button",
            "upload_local_menuitem",
            "upload_in_progress",
            "sidebar_conversations",
            "unauthenticated_indicators",
        }
        self.assertTrue(required.issubset(set(SELECTORS.keys())))
        for group, items in SELECTORS.items():
            self.assertGreaterEqual(len(items), 2, f"Selector group '{group}' kurang fallback")

    def test_model_query_normalization(self) -> None:
        self.assertEqual(normalize_model_query("Fast"), "flash")
        self.assertEqual(normalize_model_query("  Reasoning "), "thinking")
        self.assertEqual(normalize_model_query("Pro"), "pro")

    def test_validate_local_files(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
            resolved = validate_local_files([tmp.name])
            self.assertEqual(len(resolved), 1)
            self.assertTrue(resolved[0].is_file())

        with self.assertRaises(FileNotFoundError):
            validate_local_files(["/nonexistent_path_12345/missing.txt"])

    def test_dotenv_and_cli_parsing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / ".env"
            env_file.write_text("GEMINI_RESPONSE_TIMEOUT=240\n", encoding="utf-8")
            old_val = os.environ.pop("GEMINI_RESPONSE_TIMEOUT", None)
            try:
                settings = load_settings(env_file)
                self.assertEqual(settings.response_timeout, 240)
                parser = build_arg_parser(settings)
                args = parser.parse_args(
                    ["--transport", "streamable-http", "--port", "9100", "--headed"]
                )
                self.assertEqual(args.transport, "streamable-http")
                self.assertEqual(args.port, 9100)
                self.assertTrue(args.headed)
            finally:
                os.environ.pop("GEMINI_RESPONSE_TIMEOUT", None)
                if old_val is not None:
                    os.environ["GEMINI_RESPONSE_TIMEOUT"] = old_val

    def test_bearer_auth_middleware(self) -> None:
        async def dummy_app(scope, receive, send):
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"ok"})

        mw = BearerAuthASGIMiddleware(dummy_app, expected_token="rahasia123")

        async def call_mw(path: str, auth: str | None = None) -> tuple[int, bytes]:
            status_code = 0
            chunks: list[bytes] = []
            headers = [(b"authorization", auth.encode())] if auth else []

            async def send(msg):
                nonlocal status_code
                if msg["type"] == "http.response.start":
                    status_code = msg["status"]
                elif msg["type"] == "http.response.body":
                    chunks.append(msg.get("body", b""))

            async def receive():
                return {"type": "http.request"}

            await mw({"type": "http", "path": path, "headers": headers}, receive, send)
            return status_code, b"".join(chunks)

        code_health, body_health = asyncio.run(call_mw("/healthz"))
        self.assertEqual(code_health, 200)
        self.assertEqual(json.loads(body_health.decode())["status"], "ok")

        code_unauth, _ = asyncio.run(call_mw("/mcp"))
        self.assertEqual(code_unauth, 401)

        code_ok, body_ok = asyncio.run(call_mw("/mcp", "Bearer rahasia123"))
        self.assertEqual(code_ok, 200)
        self.assertEqual(body_ok, b"ok")

    def test_no_print_to_stdout_in_package(self) -> None:
        for py_file in SRC_DIR.rglob("*.py"):
            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "print"
                ):
                    self.fail(f"Ditemukan pemanggilan print() terlarang di {py_file}:{node.lineno}")


if __name__ == "__main__":
    unittest.main()
