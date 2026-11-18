"""Manajemen konfigurasi berbasis environment variables dan file `.env`."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def load_dotenv_if_present(dotenv_path: Path | None = None) -> None:
    """Muat pasangan KEY=VALUE dari `.env` tanpa menimpa environment variable yang sudah ada."""
    candidate = dotenv_path or (Path.cwd() / ".env")
    if not candidate.is_file():
        return

    for raw_line in candidate.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = val


def _parse_bool(raw: str, default: bool = True) -> bool:
    val = raw.strip().lower()
    if not val:
        return default
    return val not in {"0", "false", "no", "off"}


@dataclass(slots=True)
class Settings:
    """Parameter operasional untuk `GeminiBrowserController` dan transport MCP."""

    profile_dir: Path
    headless: bool = True
    browser_channel: str = "chrome"
    cdp_url: str = ""
    base_url: str = "https://gemini.google.com/app"
    response_timeout: int = 180
    auth_token: str = ""


def load_settings(dotenv_path: Path | None = None) -> Settings:
    """Bangun objek `Settings` dari environment saat ini."""
    load_dotenv_if_present(dotenv_path)
    return Settings(
        profile_dir=Path(
            os.environ.get("GEMINI_PROFILE_DIR", "~/.gemini-web-mcp/profile")
        ).expanduser(),
        headless=_parse_bool(os.environ.get("GEMINI_HEADLESS", "true"), default=True),
        browser_channel=os.environ.get("GEMINI_BROWSER_CHANNEL", "chrome").strip(),
        cdp_url=os.environ.get("GEMINI_CDP_URL", "").strip(),
        base_url=os.environ.get("GEMINI_BASE_URL", "https://gemini.google.com/app").strip(),
        response_timeout=int(os.environ.get("GEMINI_RESPONSE_TIMEOUT", "180")),
        auth_token=os.environ.get("GEMINI_AUTH_TOKEN", "").strip(),
    )
