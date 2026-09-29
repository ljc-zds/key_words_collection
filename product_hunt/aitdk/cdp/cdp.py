"""Collect sanitized AITDK extension traffic data through an existing Chrome CDP session."""

from __future__ import annotations

import asyncio
import json
import re
from contextlib import suppress
from dataclasses import replace
from time import monotonic
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

from playwright.async_api import Response, async_playwright

from .browser import content_script_ready_delay_ms, traffic_result_timeout_ms
from .collector import parse_event_stream
from ..data.models import CollectionRecord


_BULK_PATH = "/api/v1/bulk"


class AitdkCdpError(RuntimeError):
    pass


async def resolve_redirect_via_cdp(url: str, cdp_url: str = "http://127.0.0.1:9230") -> str:
    """Follow a Product Hunt redirect in a temporary dedicated Chrome target.

    Product Hunt can reject the non-browser redirect probe even while the same
    link works in Chrome. This only returns the final URL and does not inspect
    browser storage or page content.
    """
    base_url = cdp_url.rstrip("/")

    def request_json(path: str, method: str = "GET") -> object:
        request = Request(f"{base_url}{path}", method=method)
        with urlopen(request, timeout=10) as response:
            return json.loads(response.read())

    target_id: str | None = None
    try:
        created = await asyncio.to_thread(
            request_json, f"/json/new?{quote(url, safe='')}", "PUT"
        )
        if not isinstance(created, dict) or not isinstance(created.get("id"), str):
            raise ValueError("Chrome CDP did not create a redirect target")
        target_id = created["id"]
        deadline = monotonic() + 15
        while monotonic() < deadline:
            targets = await asyncio.to_thread(request_json, "/json/list")
            if isinstance(targets, list):
                target = next((item for item in targets if isinstance(item, dict) and item.get("id") == target_id), None)
                final_url = target.get("url") if isinstance(target, dict) else None
                if isinstance(final_url, str) and final_url and final_url != url:
                    return final_url
            await asyncio.sleep(0.25)
        raise TimeoutError("Product Hunt redirect did not leave its original URL")
    except Exception as error:
        raise AitdkCdpError("Product Hunt 跳转未在规定时间内完成") from error
    finally:
        if target_id:
            try:
                await asyncio.to_thread(request_json, f"/json/close/{target_id}")
            except Exception:
                pass


def is_aitdk_bulk_url(url: str) -> bool:
    """Return whether a response belongs to the extension's traffic event stream."""
    parsed = urlparse(url)
    return parsed.scheme == "https" and parsed.path == _BULK_PATH and "aitdk" in parsed.netloc.lower()


def extract_traffic_record(url: str, response_text: str) -> CollectionRecord | None:
    """Parse only the extension bulk stream; never retain its URL or credentials."""
    return parse_event_stream(response_text) if is_aitdk_bulk_url(url) else None


def whois_created_date_from_text(text: str) -> str | None:
    """Extract the displayed creation date; an empty Whois panel returns None."""
    match = re.search(r"Created Date\s+(\d{4}-\d{2}-\d{2})", text)
    return match.group(1) if match else None


async def read_whois_created_date(frame) -> str | None:
    await frame.get_by_text("Whois", exact=True).first.click(timeout=1500)
    created = asyncio.create_task(frame.get_by_text("Created Date", exact=True).wait_for(timeout=10_000))
    empty = asyncio.create_task(frame.get_by_text("No data available", exact=True).wait_for(timeout=10_000))
    try:
        done, pending = await asyncio.wait({created, empty}, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for task in (created, empty):
            if not task.done():
                task.cancel()
        await asyncio.gather(created, empty, return_exceptions=True)
    for task in done:
        task.result()
    if empty in done:
        return None
    return whois_created_date_from_text(await frame.locator("body").inner_text())


async def collect_via_cdp(domain: str, cdp_url: str = "http://127.0.0.1:9230") -> CollectionRecord:
    """Use an installed, logged-in AITDK extension in the user's existing Chrome."""
    result: asyncio.Future[CollectionRecord] = asyncio.get_running_loop().create_future()

    async def inspect_response(response: Response) -> None:
        if not is_aitdk_bulk_url(response.url) or result.done():
            return
        try:
            record = extract_traffic_record(response.url, await response.text())
        except Exception as error:
            result.set_exception(AitdkCdpError(f"AITDK 响应无法解析: {type(error).__name__}"))
            return
        if record is not None:
            result.set_result(record)

    def on_response(response: Response) -> None:
        asyncio.create_task(inspect_response(response))

    async with async_playwright() as playwright:
        try:
            browser = await playwright.chromium.connect_over_cdp(cdp_url)
        except Exception as error:
            raise AitdkCdpError(f"无法连接 Chrome CDP: {cdp_url}") from error
        context = browser.contexts[0] if browser.contexts else await browser.new_context()
        # Use the browser-level CDP API so the extension runs in the existing
        # signed-in profile without bringing a temporary query tab to the front.
        browser_session = await browser.new_browser_cdp_session()
        async with context.expect_page(timeout=10_000) as page_info:
            await browser_session.send("Target.createTarget", {
                "url": "about:blank",
                "background": True,
            })
        page = await page_info.value
        context.on("response", on_response)
        try:
            await page.goto(f"https://{domain}", wait_until="domcontentloaded", timeout=20_000)
            iframe = page.locator("#aitdk-iframe")
            await page.wait_for_timeout(content_script_ready_delay_ms())
            await page.keyboard.press("Alt+D")
            await iframe.wait_for(state="visible", timeout=5_000)
            frame = iframe.content_frame
            if frame is None:
                raise AitdkCdpError("AITDK Traffic iframe unavailable")
            # The panel's empty state is final. Do not wait for a network event
            # that AITDK will never emit for domains without traffic coverage.
            no_traffic = asyncio.create_task(frame.get_by_text("No data available", exact=True).wait_for(timeout=30_000))
            done, pending = await asyncio.wait(
                {result, no_traffic},
                timeout=min(traffic_result_timeout_ms() / 1000, 12),
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
            if not done:
                raise TimeoutError
            if no_traffic in done and result not in done:
                no_traffic.result()
                return CollectionRecord(domain, None, None, {}, {}, [])
            record = result.result()
            try:
                created = await asyncio.wait_for(read_whois_created_date(frame), timeout=3)
                if created:
                    record = replace(record, whois={"creationDate": created})
            except Exception:
                # Traffic is already valid. Missing/blocked Whois is handled
                # by public RDAP in the pipeline, never discard the traffic.
                pass
            return record
        except TimeoutError as error:
            raise AitdkCdpError("AITDK 未在规定时间内返回流量数据；请确认扩展已安装并登录") from error
        finally:
            context.remove_listener("response", on_response)
            with suppress(Exception):
                await page.close()
            with suppress(Exception):
                await browser_session.detach()
            with suppress(Exception):
                await browser.close()


async def whois_created_date_via_cdp(domain: str, cdp_url: str = "http://127.0.0.1:9230") -> str | None:
    """Read Created Date from AITDK's separate Whois module in a background target."""
    async with async_playwright() as playwright:
        try:
            browser = await playwright.chromium.connect_over_cdp(cdp_url)
        except Exception as error:
            raise AitdkCdpError(f"无法连接 Chrome CDP: {cdp_url}") from error
        context = browser.contexts[0] if browser.contexts else await browser.new_context()
        browser_session = await browser.new_browser_cdp_session()
        async with context.expect_page(timeout=10_000) as page_info:
            await browser_session.send("Target.createTarget", {"url": "about:blank", "background": True})
        page = await page_info.value
        try:
            await page.goto(f"https://{domain}", wait_until="domcontentloaded", timeout=20_000)
            await page.wait_for_timeout(content_script_ready_delay_ms())
            await page.keyboard.press("Alt+D")
            iframe = page.locator("#aitdk-iframe")
            await iframe.wait_for(timeout=12_000)
            frame = iframe.content_frame
            if frame is None:
                raise AitdkCdpError("AITDK Whois iframe unavailable")
            return await read_whois_created_date(frame)
        except TimeoutError as error:
            raise AitdkCdpError("AITDK Whois 未在规定时间内返回创建日期") from error
        finally:
            await page.close()
            await browser_session.detach()
            await browser.close()
