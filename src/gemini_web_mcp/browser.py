"""Controller Playwright/Patchright dengan persistent browser profile untuk Gemini Web."""

from __future__ import annotations

import asyncio
import logging
import re
import time
from pathlib import Path
from typing import Any

from .config import Settings
from .selectors import (
    DOM_TO_MARKDOWN_JS,
    SELECTORS,
    normalize_model_query,
    validate_local_files,
)

logger = logging.getLogger("gemini-web-mcp.browser")


def load_playwright_backend() -> tuple[Any, str]:
    """Utamakan `patchright` (undetected Playwright fork) agar login Google aman."""
    try:
        from patchright.async_api import async_playwright  # type: ignore[import-not-found]

        return async_playwright, "patchright"
    except ImportError:
        from playwright.async_api import async_playwright  # type: ignore[import-not-found]

        return async_playwright, "playwright"


class GeminiBrowserController:
    """Mengelola lifecycle persistent browser profile dan operasi DOM `gemini.google.com`."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._lock = asyncio.Lock()
        self._pw: Any = None
        self._browser: Any = None
        self._context: Any = None
        self._page: Any = None
        self._current_headless: bool | None = None
        self._backend_name: str = "uninitialized"

    @property
    def lock(self) -> asyncio.Lock:
        return self._lock

    async def ensure_page(self, force_headed: bool = False) -> Any:
        """Pastikan browser context dan tab Gemini aktif."""
        desired_headless = False if force_headed else self.settings.headless

        if (
            self._page is not None
            and not self._page.is_closed()
            and (self.settings.cdp_url or self._current_headless == desired_headless)
        ):
            return self._page

        await self.close()

        async_playwright_fn, backend_name = load_playwright_backend()
        self._backend_name = backend_name
        self._pw = await async_playwright_fn().start()

        if self.settings.cdp_url:
            logger.info("Menghubungkan ke browser aktif via CDP: %s", self.settings.cdp_url)
            self._browser = await self._pw.chromium.connect_over_cdp(self.settings.cdp_url)
            contexts = self._browser.contexts
            self._context = contexts[0] if contexts else await self._browser.new_context()
            self._current_headless = False
        else:
            self.settings.profile_dir.mkdir(parents=True, exist_ok=True)
            launch_kwargs: dict[str, Any] = {
                "user_data_dir": str(self.settings.profile_dir),
                "headless": desired_headless,
                "viewport": {"width": 1366, "height": 900},
                "ignore_default_args": ["--enable-automation"],
                "args": [
                    "--disable-blink-features=AutomationControlled",
                    "--no-first-run",
                    "--no-default-browser-check",
                    "--disable-dev-shm-usage",
                ],
            }
            if self.settings.browser_channel:
                launch_kwargs["channel"] = self.settings.browser_channel

            try:
                logger.info(
                    "Meluncurkan %s persistent profile (dir=%s, headless=%s, channel=%s)",
                    backend_name,
                    self.settings.profile_dir,
                    desired_headless,
                    self.settings.browser_channel or "chromium",
                )
                self._context = await self._pw.chromium.launch_persistent_context(
                    **launch_kwargs
                )
            except Exception as exc:
                if self.settings.browser_channel:
                    logger.warning(
                        "Channel '%s' tidak tersedia (%s). Beralih ke Chromium bawaan.",
                        self.settings.browser_channel,
                        exc,
                    )
                    launch_kwargs.pop("channel", None)
                    self._context = await self._pw.chromium.launch_persistent_context(
                        **launch_kwargs
                    )
                else:
                    raise
            self._current_headless = desired_headless

        existing_pages = self._context.pages
        gemini_page = next(
            (p for p in existing_pages if "gemini.google.com" in (p.url or "")),
            None,
        )
        self._page = gemini_page or (
            existing_pages[0] if existing_pages else await self._context.new_page()
        )

        if "gemini.google.com" not in (self._page.url or ""):
            await self._page.goto(
                self.settings.base_url, wait_until="domcontentloaded", timeout=60_000
            )

        return self._page

    async def close(self) -> None:
        """Tutup browser context secara bersih tanpa menghapus persistent profile."""
        try:
            if self._context is not None and not self.settings.cdp_url:
                await self._context.close()
        except Exception as exc:
            logger.debug("Peringatan saat menutup context: %s", exc)
        finally:
            self._context = None
            self._browser = None
            self._page = None
            self._current_headless = None

        if self._pw is not None:
            try:
                await self._pw.stop()
            except Exception as exc:
                logger.debug("Peringatan saat menghentikan Playwright: %s", exc)
            finally:
                self._pw = None

    async def _find_first_visible(
        self, page: Any, selector_group: str, timeout_ms: int = 4_000
    ) -> tuple[Any | None, str | None]:
        candidates = SELECTORS[selector_group]
        deadline = time.monotonic() + (timeout_ms / 1000.0)

        while time.monotonic() < deadline:
            for sel in candidates:
                loc = page.locator(sel).first
                try:
                    if await loc.count() > 0 and await loc.is_visible():
                        return loc, sel
                except Exception:
                    continue
            await asyncio.sleep(0.25)

        return None, None

    async def check_authenticated(self, page: Any) -> tuple[bool, str]:
        """Pastikan sesi persistent profile benar-benar sudah login ke akun Google."""
        url = page.url or ""
        if "accounts.google.com" in url:
            return False, f"Redirect ke halaman login Google ({url})"

        input_loc, matched_sel = await self._find_first_visible(
            page, "prompt_input", timeout_ms=5_000
        )
        unauth_loc, unauth_sel = await self._find_first_visible(
            page, "unauthenticated_indicators", timeout_ms=1_000
        )

        if unauth_loc is not None:
            return (
                False,
                f"Sesi belum login ke akun Google (terdeteksi '{unauth_sel}'). "
                "Jalankan `gemini-web-mcp --setup-auth` atau panggil tool `gemini_setup_auth`.",
            )

        if input_loc is not None:
            return True, f"Autentikasi aktif (input selector: '{matched_sel}')"

        return False, f"Kotak input Gemini belum ditemukan pada URL {url}"

    async def setup_interactive_auth(self, timeout_seconds: int = 300) -> dict[str, Any]:
        """Buka jendela browser (headed / Xvfb noVNC) agar user bisa login Google."""
        page = await self.ensure_page(force_headed=True)
        await page.goto(
            self.settings.base_url, wait_until="domcontentloaded", timeout=60_000
        )
        await page.bring_to_front()

        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            is_auth, detail = await self.check_authenticated(page)
            if is_auth:
                await asyncio.sleep(2.0)
                current_url = page.url
                if self.settings.headless and not self.settings.cdp_url:
                    await self.close()
                return {
                    "authenticated": True,
                    "profile_dir": str(self.settings.profile_dir),
                    "url": current_url,
                    "detail": detail,
                }
            await asyncio.sleep(2.0)

        return {
            "authenticated": False,
            "profile_dir": str(self.settings.profile_dir),
            "url": page.url,
            "detail": (
                f"Waktu tunggu login ({timeout_seconds} detik) berakhir sebelum sesi "
                "terautentikasi di gemini.google.com."
            ),
        }

    async def get_active_model_badge(self, page: Any) -> str:
        btn, _ = await self._find_first_visible(
            page, "model_switcher_button", timeout_ms=2_500
        )
        if btn is None:
            return "unknown"
        try:
            text = (await btn.inner_text()).strip()
            return re.sub(r"\s+", " ", text) or "unknown"
        except Exception:
            return "unknown"

    async def select_model(self, model_name: str) -> dict[str, Any]:
        """Ganti model aktif pada menu mode switcher Gemini Web."""
        page = await self.ensure_page()
        is_auth, auth_msg = await self.check_authenticated(page)
        if not is_auth:
            raise RuntimeError(auth_msg)

        switcher_btn, switcher_sel = await self._find_first_visible(
            page, "model_switcher_button", timeout_ms=8_000
        )
        if switcher_btn is None:
            raise RuntimeError("Tombol pemilih model tidak ditemukan di halaman Gemini.")

        previous_badge = await self.get_active_model_badge(page)
        await switcher_btn.click()
        await asyncio.sleep(0.6)

        target_norm = normalize_model_query(model_name)
        raw_target = model_name.strip().lower()

        discovered_options: list[str] = []
        matched_locator: Any = None
        matched_label: str = ""

        for item_sel in SELECTORS["model_menu_items"]:
            items = page.locator(item_sel)
            count = await items.count()
            if count == 0:
                continue

            for idx in range(count):
                item = items.nth(idx)
                try:
                    if not await item.is_visible():
                        continue
                    label = re.sub(r"\s+", " ", (await item.inner_text()).strip())
                    if not label:
                        continue
                    discovered_options.append(label)
                    label_lower = label.lower()
                    if (
                        raw_target in label_lower or target_norm in label_lower
                    ) and matched_locator is None:
                        matched_locator = item
                        matched_label = label
                except Exception:
                    continue

            if discovered_options:
                break

        if matched_locator is None:
            await page.keyboard.press("Escape")
            return {
                "switched": False,
                "requested_model": model_name,
                "active_model": previous_badge,
                "available_models": discovered_options,
                "switcher_selector": switcher_sel,
                "message": (
                    f"Model '{model_name}' tidak ditemukan. Opsi tersedia: {discovered_options}"
                ),
            }

        await matched_locator.click()
        await asyncio.sleep(0.8)
        updated_badge = await self.get_active_model_badge(page)

        return {
            "switched": True,
            "requested_model": model_name,
            "matched_option": matched_label,
            "previous_model": previous_badge,
            "active_model": updated_badge,
            "available_models": discovered_options,
        }

    async def upload_files(self, paths: list[Path], page: Any | None = None) -> dict[str, Any]:
        """Unggah satu atau banyak file lokal ke kotak input Gemini Web."""
        if page is None:
            page = await self.ensure_page()

        is_auth, auth_msg = await self.check_authenticated(page)
        if not is_auth:
            raise RuntimeError(auth_msg)

        str_paths = [str(p) for p in paths]
        upload_method = ""

        trigger_btn, trigger_sel = await self._find_first_visible(
            page, "upload_trigger_button", timeout_ms=5_000
        )
        if trigger_btn is not None:
            try:
                async with page.expect_file_chooser(timeout=2_500) as fc_info:
                    await trigger_btn.click()
                fc = await fc_info.value
                await fc.set_files(str_paths)
                upload_method = f"direct_filechooser ({trigger_sel})"
            except Exception:
                local_item, local_sel = await self._find_first_visible(
                    page, "upload_local_menuitem", timeout_ms=4_000
                )
                if local_item is not None:
                    async with page.expect_file_chooser(timeout=6_000) as fc_info:
                        await local_item.click()
                    fc = await fc_info.value
                    await fc.set_files(str_paths)
                    upload_method = f"menu_filechooser ({local_sel})"
                else:
                    await page.keyboard.press("Escape")

        if not upload_method:
            file_inputs = page.locator("input[type='file']")
            if await file_inputs.count() > 0:
                await file_inputs.first.set_input_files(str_paths)
                upload_method = "hidden_input_file"

        if not upload_method:
            raise RuntimeError(
                "Gagal menemukan pemicu upload file maupun <input type='file'> di halaman Gemini."
            )

        await asyncio.sleep(1.0)
        upload_deadline = time.monotonic() + 60.0
        while time.monotonic() < upload_deadline:
            spinner, _ = await self._find_first_visible(
                page, "upload_in_progress", timeout_ms=600
            )
            if spinner is None:
                break
            await asyncio.sleep(0.6)

        return {
            "uploaded": [p.name for p in paths],
            "file_count": len(paths),
            "method": upload_method,
        }

    async def _count_responses(self, page: Any) -> tuple[int, str | None]:
        for sel in SELECTORS["response_containers"]:
            loc = page.locator(sel)
            cnt = await loc.count()
            if cnt > 0:
                return cnt, sel
        return 0, None

    async def _extract_latest_response_markdown(self, page: Any) -> str:
        for sel in SELECTORS["response_containers"]:
            loc = page.locator(sel)
            cnt = await loc.count()
            if cnt > 0:
                last_el = loc.nth(cnt - 1)
                try:
                    md = await last_el.evaluate(DOM_TO_MARKDOWN_JS)
                    if md and md.strip():
                        return md.strip()
                    raw_text = (await last_el.inner_text()).strip()
                    if raw_text:
                        return raw_text
                except Exception:
                    continue
        return ""

    async def _inject_prompt_text(self, page: Any, input_loc: Any, prompt: str) -> None:
        await input_loc.click()
        await page.keyboard.press("ControlOrMeta+A")
        await page.keyboard.press("Backspace")
        await asyncio.sleep(0.15)

        inserted = await input_loc.evaluate(
            """(el, text) => {
                el.focus();
                if (typeof document.execCommand === 'function') {
                    const ok = document.execCommand('insertText', false, text);
                    if (ok) return true;
                }
                return false;
            }""",
            prompt,
        )
        if not inserted:
            await page.keyboard.insert_text(prompt)
            await input_loc.dispatch_event("input")

        await asyncio.sleep(0.25)

    async def send_chat(
        self,
        prompt: str,
        new_chat: bool = False,
        conversation_url: str | None = None,
        model: str | None = None,
        file_paths: list[str] | None = None,
        timeout_seconds: int | None = None,
    ) -> dict[str, Any]:
        """Kirim pesan ke Gemini Web dan tunggu hingga streaming jawaban selesai penuh."""
        if not prompt.strip():
            raise ValueError("Parameter `prompt` tidak boleh kosong.")

        page = await self.ensure_page()

        if conversation_url:
            if page.url != conversation_url:
                await page.goto(
                    conversation_url, wait_until="domcontentloaded", timeout=60_000
                )
                await asyncio.sleep(1.0)
        elif new_chat:
            await page.goto(
                self.settings.base_url, wait_until="domcontentloaded", timeout=60_000
            )
            await asyncio.sleep(1.0)

        is_auth, auth_msg = await self.check_authenticated(page)
        if not is_auth:
            raise RuntimeError(auth_msg)

        model_info: dict[str, Any] | None = None
        if model:
            model_info = await self.select_model(model)

        upload_info: dict[str, Any] | None = None
        if file_paths:
            validated_files = validate_local_files(file_paths)
            upload_info = await self.upload_files(validated_files, page=page)

        pre_count, _ = await self._count_responses(page)

        input_loc, input_sel = await self._find_first_visible(
            page, "prompt_input", timeout_ms=10_000
        )
        if input_loc is None:
            raise RuntimeError("Kotak input Gemini tidak ditemukan saat akan mengirim pesan.")

        await self._inject_prompt_text(page, input_loc, prompt)

        send_btn, _ = await self._find_first_visible(
            page, "send_button", timeout_ms=5_000
        )
        if send_btn is not None:
            await send_btn.click()
        else:
            await page.keyboard.press("Enter")

        max_wait = timeout_seconds or self.settings.response_timeout
        deadline = time.monotonic() + max_wait

        started = False
        while time.monotonic() < deadline:
            cur_count, _ = await self._count_responses(page)
            stop_btn, _ = await self._find_first_visible(
                page, "stop_generating", timeout_ms=400
            )
            if cur_count > pre_count or stop_btn is not None:
                started = True
                break
            await asyncio.sleep(0.4)

        if not started:
            raise TimeoutError(
                "Gemini tidak mulai merespons setelah tombol kirim ditekan."
            )

        stable_rounds = 0
        last_snapshot = ""

        while time.monotonic() < deadline:
            stop_btn, _ = await self._find_first_visible(
                page, "stop_generating", timeout_ms=400
            )
            cur_count, _ = await self._count_responses(page)
            latest_md = (
                await self._extract_latest_response_markdown(page)
                if cur_count > pre_count
                else ""
            )

            if stop_btn is None and latest_md:
                if latest_md == last_snapshot:
                    stable_rounds += 1
                    if stable_rounds >= 3:
                        break
                else:
                    last_snapshot = latest_md
                    stable_rounds = 0
            else:
                last_snapshot = latest_md
                stable_rounds = 0

            await asyncio.sleep(0.65)
        else:
            raise TimeoutError(
                f"Batas waktu tunggu ({max_wait} detik) habis sebelum respons selesai."
            )

        active_model = await self.get_active_model_badge(page)
        result: dict[str, Any] = {
            "response": last_snapshot,
            "conversation_url": page.url,
            "active_model": active_model,
            "input_selector": input_sel,
        }
        if model_info is not None:
            result["model_switch"] = model_info
        if upload_info is not None:
            result["uploaded_files"] = upload_info
        return result

    async def list_recent_chats(self, limit: int = 15) -> dict[str, Any]:
        """Ambil daftar percakapan terbaru dari sidebar `gemini.google.com`."""
        page = await self.ensure_page()
        is_auth, auth_msg = await self.check_authenticated(page)
        if not is_auth:
            raise RuntimeError(auth_msg)

        conversations: list[dict[str, str]] = []
        seen_urls: set[str] = set()

        for sel in SELECTORS["sidebar_conversations"]:
            links = page.locator(sel)
            count = await links.count()
            if count == 0:
                continue
            for idx in range(count):
                if len(conversations) >= limit:
                    break
                el = links.nth(idx)
                try:
                    href = await el.get_attribute("href")
                    if not href:
                        continue
                    full_url = (
                        href
                        if href.startswith("http")
                        else f"https://gemini.google.com{href}"
                    )
                    if full_url in seen_urls or full_url.rstrip("/") == self.settings.base_url.rstrip("/"):
                        continue
                    title = re.sub(r"\s+", " ", (await el.inner_text()).strip())
                    seen_urls.add(full_url)
                    conversations.append({"title": title or "Untitled", "url": full_url})
                except Exception:
                    continue
            if conversations:
                break

        return {"count": len(conversations), "conversations": conversations}

    async def start_new_chat(self) -> dict[str, Any]:
        page = await self.ensure_page()
        await page.goto(
            self.settings.base_url, wait_until="domcontentloaded", timeout=60_000
        )
        await asyncio.sleep(1.0)
        is_auth, auth_msg = await self.check_authenticated(page)
        return {
            "authenticated": is_auth,
            "conversation_url": page.url,
            "active_model": await self.get_active_model_badge(page) if is_auth else "unknown",
            "detail": auth_msg,
        }

    async def inspect_status(self) -> dict[str, Any]:
        page = await self.ensure_page()
        is_auth, auth_msg = await self.check_authenticated(page)
        matched_selectors: dict[str, str | None] = {}
        for group in ("prompt_input", "model_switcher_button", "upload_trigger_button"):
            _, sel = await self._find_first_visible(page, group, timeout_ms=1_200)
            matched_selectors[group] = sel

        return {
            "authenticated": is_auth,
            "detail": auth_msg,
            "backend": self._backend_name,
            "headless": self._current_headless,
            "profile_dir": str(self.settings.profile_dir),
            "cdp_url": self.settings.cdp_url or None,
            "current_url": page.url,
            "active_model": await self.get_active_model_badge(page) if is_auth else "unknown",
            "matched_selectors": matched_selectors,
        }
