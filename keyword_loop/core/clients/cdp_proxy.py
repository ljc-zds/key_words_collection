"""Low-token CDP network response client for an already logged-in Chrome."""
from __future__ import annotations

import json
from contextlib import contextmanager, suppress
from typing import Iterator
from urllib.parse import parse_qsl, urlparse, urlunparse

from playwright.sync_api import sync_playwright


class CdpProxyError(RuntimeError):
    pass


def paginated_url(initial_url: str, page: int) -> str:
    """Build a later Similarweb grid request from its captured first-page URL."""
    parsed = urlparse(initial_url)
    query = [(key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True) if key not in {"page", "orderBy"}]
    query.extend([("orderBy", "windowVolume desc"), ("page", str(page))])
    serialized = "&".join(f"{key}={value.replace(' ', '+')}" for key, value in query)
    return urlunparse(parsed._replace(query=serialized))


class CdpBrowser:
    def __init__(self, cdp_url: str = "http://127.0.0.1:9222") -> None:
        self.cdp_url = cdp_url

    @staticmethod
    def _new_background_page(browser, context, *, timeout_ms: int):
        """Create an isolated Chrome target without activating a user tab."""
        session = browser.new_browser_cdp_session()
        try:
            with context.expect_page(timeout=timeout_ms) as page_info:
                session.send("Target.createTarget", {"url": "about:blank", "background": True})
            return page_info.value
        finally:
            with suppress(Exception):
                session.detach()

    @contextmanager
    def responses(self, url: str, fragment: str, timeout_ms: int = 30000, predicate=None) -> Iterator[list[dict]]:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.connect_over_cdp(self.cdp_url)
            except Exception as exc:
                raise CdpProxyError(f"无法连接 Chrome CDP: {self.cdp_url}") from exc
            context = browser.contexts[0] if browser.contexts else browser.new_context()
            # A shared Semrush tab can still emit responses from the previous
            # keyword while a new query starts. Use an isolated page so the
            # captured JSON belongs only to this navigation.
            page = self._new_background_page(browser, context, timeout_ms=timeout_ms)
            captured: list[dict] = []

            def on_response(response) -> None:
                if fragment not in response.url or response.status != 200:
                    return
                try:
                    body = response.json()
                except Exception:
                    return
                if isinstance(body, dict):
                    item = {"url": response.url, "status": response.status, "body": body}
                    if predicate is None or predicate(body):
                        captured.append(item)

            listening = False
            page.on("response", on_response)
            listening = True
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                page.wait_for_timeout(1000)
                deadline = timeout_ms
                while not captured and deadline > 0:
                    page.wait_for_timeout(500)
                    deadline -= 500
                if not captured:
                    raise CdpProxyError(f"未捕获目标网络响应: {fragment}")
                yield captured
            finally:
                page.remove_listener("response", on_response)
                page.close()
                browser.close()

    def paginated_responses(
        self,
        url: str,
        fragment: str,
        *,
        maximum_pages: int = 5,
        timeout_ms: int = 30000,
        predicate=None,
        url_predicate=None,
        page_query_name: str | None = None,
    ) -> list[dict]:
        """Capture the first grid response, then fetch later pages in-session."""
        with sync_playwright() as playwright:
            browser = playwright.chromium.connect_over_cdp(self.cdp_url)
            context = browser.contexts[0] if browser.contexts else browser.new_context()
            page = self._new_background_page(browser, context, timeout_ms=timeout_ms)
            def matches(response) -> bool:
                if fragment not in response.url or response.status != 200:
                    return False
                if url_predicate is not None and not url_predicate(response.url):
                    return False
                try:
                    body = response.json()
                except Exception:
                    return False
                return isinstance(body, dict) and (predicate is None or predicate(body))

            captured: list[dict] = []

            def on_response(response) -> None:
                if not matches(response):
                    return
                captured.append({"url": response.url, "status": response.status, "body": response.json()})

            listening = False
            page.on("response", on_response)
            listening = True
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                deadline = timeout_ms
                while not captured and deadline > 0:
                    page.wait_for_timeout(250)
                    deadline -= 250
                if not captured:
                    raise CdpProxyError(f"未捕获目标网络响应: {fragment}")
                # The application may prefetch extra grid requests while its
                # initial route hydrates. Only the first-page response seeds
                # this run; subsequent pages are fetched deterministically.
                first = captured[0]
                captured = [first]
                page.remove_listener("response", on_response)
                listening = False
                rows_per_page = len(first["body"].get("records", []))
                if page_query_name is None or not rows_per_page:
                    return captured
                total_records = int(first["body"].get("totalRecords", 0) or 0)
                total_pages = min(maximum_pages, max(1, (total_records + rows_per_page - 1) // rows_per_page))
                for page_number in range(2, total_pages + 1):
                    request_url = paginated_url(first["url"], page_number)
                    result = page.evaluate(
                        """async (requestUrl) => {
                            const response = await fetch(requestUrl, {method: 'POST', credentials: 'include'});
                            return {status: response.status, body: await response.json()};
                        }""",
                        request_url,
                    )
                    if result.get("status") != 200 or not isinstance(result.get("body"), dict):
                        raise CdpProxyError(f"Similarweb page {page_number} returned an invalid response")
                    captured.append({"url": request_url, "status": result["status"], "body": result["body"]})
                return captured
            finally:
                if listening:
                    page.remove_listener("response", on_response)
                page.close()
                browser.close()
