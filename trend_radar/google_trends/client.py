"""Small client for Google Trends' public web JSON endpoints."""

from __future__ import annotations

import json
import multiprocessing as mp
import os
import random
import time
from contextlib import suppress
from queue import Empty
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
from urllib.parse import urlparse

import websocket

from playwright.sync_api import Error as PlaywrightError, sync_playwright

from product_hunt.aitdk.product.product_hunt import trusted_ssl_context

from .parsing import parse_related_queries, parse_timeline_values


BASE_URL = "https://trends.google.com/trends/api"
HEADERS = {"User-Agent": "Mozilla/5.0", "Accept-Language": "en-US,en;q=0.9"}


def _json(response: bytes) -> dict:
    return parse_trends_response(response.decode("utf-8"))


def parse_trends_response(response: str) -> dict:
    """Decode a Google Trends JSON response, including its XSSI prefix."""
    text = response.lstrip()
    if text.startswith(")]}'"):
        text = text.split("\n", 1)[1]
    return json.loads(text)


def parse_batchexecute_rpc(response: str, rpc_id: str) -> object:
    """Extract one nested JSON payload from a Google batchexecute response."""
    for line in response.lstrip().splitlines():
        if not line.startswith("["):
            continue
        for item in json.loads(line):
            if isinstance(item, list) and len(item) >= 3 and item[1] == rpc_id:
                return json.loads(item[2])
    raise ValueError(f"batchexecute response has no {rpc_id} payload")


def parse_cdp_rpc_response(response, rpc_id: str) -> object | None:
    """Read one RPC payload, tolerating a response that closes during cleanup."""
    try:
        return parse_batchexecute_rpc(response.text(), rpc_id)
    except (PlaywrightError, ValueError, json.JSONDecodeError, UnicodeDecodeError):
        return None


def is_new_trends_rpc_response(url: str) -> bool:
    """Identify the new Explore UI's batch endpoint without assuming query params.

    Google can send the RPC id in a POST body rather than as ``rpcids`` in the
    URL. The reliable discriminator is therefore the batch endpoint itself;
    ``parse_batchexecute_rpc`` then selects the requested response payload.
    """
    return "/_/TrendsUi/data/batchexecute" in url


def parse_new_rising_queries(payload: object, minimum_growth: int = 500, source_term: str | None = None) -> list[dict]:
    """Normalize the new Explore page's fXqlme Rising-query response."""
    results: list[dict] = []
    if not isinstance(payload, list):
        return results
    for outer in payload:
        if not isinstance(outer, list):
            continue
        for group in outer:
            if not isinstance(group, list) or len(group) < 2 or not isinstance(group[1], list):
                continue
            if source_term and (not isinstance(group[0], str) or group[0].lower() != source_term.lower()):
                continue
            for item in group[1]:
                if not isinstance(item, list) or len(item) < 2:
                    continue
                query, growth = str(item[0]).strip(), item[1]
                # The new UI represents BREAKOUT as growth=5000 with marker 2.
                is_breakout_marker = len(item) > 2 and item[2] == 2
                if query and (is_breakout_marker or (isinstance(growth, str) and growth.strip().lower() == "breakout")):
                    results.append({"query": query, "type": "Breakout", "growth_percent": None})
                    continue
                if query and isinstance(growth, (int, float)) and growth >= minimum_growth:
                    results.append({"query": query, "type": "rising", "growth_percent": int(growth)})
    return results


def parse_new_timeline_values(payload: object) -> dict[str, tuple[list[str], list[int]]]:
    """Normalize the new Explore page's g4kJzf time-series response."""
    series: dict[str, tuple[list[str], list[int]]] = {}

    def visit(value: object) -> None:
        if not isinstance(value, list):
            return
        if len(value) >= 5 and isinstance(value[0], str) and isinstance(value[4], list):
            times, values = [], []
            for point in value[4]:
                if not isinstance(point, list) or len(point) < 3 or not isinstance(point[2], list) or not point[2] or not isinstance(point[2][0], list) or not point[2][0]:
                    continue
                times.append(str(point[2][0][0]))
                values.append(int(point[1]) if isinstance(point[1], (int, float)) else 0)
            if times:
                series[value[0].lower()] = (times, values)
            return
        for item in value:
            visit(item)

    visit(payload)
    return series


def _process_entry(function, arguments: tuple, result_queue) -> None:
    try:
        result_queue.put(("result", function(*arguments)))
    except BaseException as error:
        result_queue.put(("error", f"{type(error).__name__}: {error}"))


def isolated_process_context():
    """Use fork locally so a CDP worker does not re-bootstrap Playwright."""
    return mp.get_context("fork")


def run_in_isolated_process(function, arguments: tuple, *, timeout_seconds: float):
    """Run one browser operation with a hard process boundary.

    Playwright can hang while closing a detached CDP target. A process timeout
    covers that cleanup path as well as page navigation and response waits.
    """
    context = isolated_process_context()
    result_queue = context.Queue()
    process = context.Process(target=_process_entry, args=(function, arguments, result_queue))
    process.start()
    process.join(timeout_seconds)
    if process.is_alive():
        process.terminate()
        process.join()
        raise RuntimeError(f"Google Trends browser operation timed out after {timeout_seconds:g}s")
    try:
        status, value = result_queue.get(timeout=1)
    except Empty as error:
        raise RuntimeError("Google Trends browser operation exited without a result") from error
    if status == "error":
        raise RuntimeError(value)
    return value


class GoogleTrendsClient:
    def _get(self, endpoint: str, params: dict) -> dict:
        request = Request(f"{BASE_URL}/{endpoint}?{urlencode(params)}", headers=HEADERS)
        with urlopen(request, timeout=30, context=trusted_ssl_context()) as response:
            return _json(response.read())

    def _explore(self, terms: list[str], timeframe: str) -> dict:
        req = {"comparisonItem": [{"keyword": term, "geo": "", "time": timeframe} for term in terms], "category": 0, "property": ""}
        return self._get("explore", {"hl": "en-US", "tz": 0, "req": json.dumps(req, separators=(",", ":"))})

    @staticmethod
    def _widget(payload: dict, identifier: str) -> dict:
        return next(widget for widget in payload.get("widgets", []) if widget.get("id") == identifier)

    def related_rising(self, term: str, timeframe: str = "today 1-m") -> list[dict]:
        widget = self._widget(self._explore([term], timeframe), "RELATED_QUERIES")
        payload = self._get("relatedsearches", {"hl": "en-US", "tz": 0, "req": json.dumps(widget["request"], separators=(",", ":")), "token": widget["token"]})
        return parse_related_queries(payload)

    def compare(self, candidate: str, baseline: str = "gpts", timeframe: str = "today 1-m") -> tuple[list[str], list[int], list[int]]:
        widget = self._widget(self._explore([candidate, baseline], timeframe), "TIMESERIES")
        payload = self._get("multiline", {"hl": "en-US", "tz": 0, "req": json.dumps(widget["request"], separators=(",", ":")), "token": widget["token"]})
        times, rows = parse_timeline_values(payload)
        return times, [row[0] for row in rows], [row[1] for row in rows]


class CdpGoogleTrendsClient:
    """Read Google Trends data through an existing tab in the local Chrome profile."""

    def __init__(self, cdp_url: str = "http://127.0.0.1:9229", timeout_ms: int = 20_000) -> None:
        self.cdp_url = cdp_url
        self.timeout_ms = timeout_ms

    @staticmethod
    def _existing_trends_page(contexts):
        """Return the already-open Google Trends page without creating a target."""
        for context in contexts:
            for page in context.pages:
                if page.url.startswith("https://trends.google.com/"):
                    return page
        raise RuntimeError("An existing Google Trends page is required for CDP collection")

    @staticmethod
    @staticmethod
    def _enable_focus_emulation(context, page) -> None:
        """Trigger focus-gated Explore modules without activating a user tab."""
        session = context.new_cdp_session(page)
        try:
            session.send("Emulation.setFocusEmulationEnabled", {"enabled": True})
        finally:
            session.detach()

    def _capture(self, url: str, fragment: str) -> list[dict]:
        raise RuntimeError("Legacy Google Trends endpoints are unavailable; use the new Explore RPC client")

    @staticmethod
    def _explore_url(terms: list[str], timeframe: str) -> str:
        return "https://trends.google.com/trends/explore?" + urlencode({"date": timeframe, "q": ",".join(terms)})

    def related_rising(self, term: str, timeframe: str = "today 1-m") -> list[dict]:
        related: list[dict] = []
        for payload in self._capture(self._explore_url([term], timeframe), "/widgetdata/relatedsearches"):
            related.extend(parse_related_queries(payload))
        return list({item["query"].lower(): item for item in related}.values())

    def compare(self, candidate: str, baseline: str = "gpts", timeframe: str = "today 1-m") -> tuple[list[str], list[int], list[int]]:
        payloads = self._capture(self._explore_url([candidate, baseline], timeframe), "/widgetdata/multiline")
        times, rows = parse_timeline_values(payloads[-1])
        return times, [row[0] for row in rows], [row[1] for row in rows]

    def compare_batch(self, candidates: list[str], baseline: str = "gpts", timeframe: str = "today 1-m") -> dict[str, tuple[list[str], list[int], list[int]]]:
        if not candidates or len(candidates) > 4:
            raise ValueError("compare_batch accepts one to four candidates")
        payloads = self._capture(self._explore_url([*candidates, baseline], timeframe), "/widgetdata/multiline")
        times, rows = parse_timeline_values(payloads[-1])
        return {
            candidate: (times, [row[index] for row in rows], [row[-1] for row in rows])
            for index, candidate in enumerate(candidates)
        }


class NewCdpGoogleTrendsClient(CdpGoogleTrendsClient):
    """Read the new ``/explore`` UI through URL parameters and bRPC responses."""

    def __init__(
        self,
        cdp_url: str = "http://127.0.0.1:9229",
        timeout_ms: int = 20_000,
        rising_timeout_ms: int = 60_000,
    ) -> None:
        super().__init__(cdp_url, timeout_ms)
        self.rising_timeout_ms = rising_timeout_ms
        self._last_request_at = 0.0
        self._consecutive_failures = 0

    def _throttle(self) -> None:
        """Spread requests to reduce Trends rate limiting and stale-page races."""
        minimum = float(os.environ.get("GOOGLE_TRENDS_MIN_INTERVAL", "2.0"))
        jitter = float(os.environ.get("GOOGLE_TRENDS_JITTER", "1.5"))
        delay = max(0.0, minimum + random.uniform(0.0, jitter) - (time.monotonic() - self._last_request_at))
        if delay:
            time.sleep(delay)
        self._last_request_at = time.monotonic()

    @staticmethod
    def _activate_related_query_source(page, term: str, timeout_ms: int) -> None:
        """Select a source term so the new UI requests related-query panels."""
        source = page.locator("button.dc3dBf").filter(has_text=term).first
        source.wait_for(state="visible", timeout=timeout_ms)
        if source.get_attribute("aria-pressed") != "true":
            source.click(timeout=timeout_ms)

    def _capture_rpc(
        self,
        terms: list[str],
        rpc_id: str,
        timeframe: str,
        *,
        timeout_ms: int | None = None,
        activate_related_term: str | None = None,
    ) -> list[object]:
        capture_timeout_ms = timeout_ms or self.timeout_ms
        self._throttle()
        url = "https://trends.google.com/explore?" + urlencode({"q": ",".join(terms), "date": timeframe, "_cdp": str(time.time_ns())})
        parsed = urlparse(self.cdp_url)
        list_url = f"{parsed.scheme}://{parsed.netloc}/json/list"
        with urlopen(f"{parsed.scheme}://{parsed.netloc}/json/version", timeout=10) as response:
            browser_info = json.load(response)
        browser_ws = websocket.create_connection(browser_info["webSocketDebuggerUrl"], timeout=3, suppress_origin=True)
        browser_ws.send(json.dumps({"id": 1, "method": "Target.createTarget", "params": {"url": url, "background": True}}))
        created = None
        while True:
            message = json.loads(browser_ws.recv())
            if message.get("id") == 1:
                created = message.get("result", {}).get("targetId")
                break
        if not created:
            browser_ws.close()
            raise RuntimeError("Chrome CDP could not create a background Trends target")
        target = None
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            with urlopen(list_url, timeout=10) as response:
                targets = json.load(response)
            target = next((item for item in targets if item.get("id") == created), None)
            if target and target.get("webSocketDebuggerUrl"):
                break
            time.sleep(0.1)
        if not target or not target.get("webSocketDebuggerUrl"):
            browser_ws.close()
            raise RuntimeError("Chrome CDP did not provide a Google Trends page target")
        ws = websocket.create_connection(target["webSocketDebuggerUrl"], timeout=2, suppress_origin=True)
        next_id = 0
        captured: list[object] = []
        pending_events: list[dict] = []
        response_ids: set[str] = set()

        def command(method: str, params: dict | None = None) -> int:
            nonlocal next_id
            next_id += 1
            ws.send(json.dumps({"id": next_id, "method": method, "params": params or {}}))
            return next_id

        def receive_until(command_id: int, deadline: float) -> dict:
            while time.monotonic() < deadline:
                ws.settimeout(max(0.1, min(1.0, deadline - time.monotonic())))
                try:
                    message = json.loads(ws.recv())
                except websocket.WebSocketTimeoutException:
                    continue
                if message.get("id") == command_id:
                    return message
                if message.get("method"):
                    pending_events.append(message)
            raise RuntimeError("Google Trends CDP command timed out")

        try:
            command("Network.enable")
            command("Page.enable")
            command("Page.reload", {"ignoreCache": True})
            deadline = time.monotonic() + capture_timeout_ms / 1000
            clicked = False
            next_source_check = time.monotonic() + 1
            while time.monotonic() < deadline and not captured:
                if activate_related_term and not clicked and time.monotonic() >= next_source_check:
                    expression = "(() => { const b=[...document.querySelectorAll('button.dc3dBf')].find(x=>x.textContent.trim().toLowerCase()===%s); if(!b)return false; if(b.getAttribute('aria-pressed')!=='true')b.click(); return true; })()" % json.dumps(activate_related_term.lower())
                    result = receive_until(command("Runtime.evaluate", {"expression": expression, "returnByValue": True}), deadline)
                    clicked = result.get("result", {}).get("result", {}).get("value") is True
                    next_source_check = time.monotonic() + 1
                ws.settimeout(max(0.1, min(1.0, deadline - time.monotonic())))
                if pending_events:
                    message = pending_events.pop(0)
                else:
                    try:
                        message = json.loads(ws.recv())
                    except websocket.WebSocketTimeoutException:
                        continue
                if message.get("method") == "Network.responseReceived":
                    response = message["params"]["response"]
                    if response.get("status") != 200 or not is_new_trends_rpc_response(response.get("url", "")):
                        continue
                    response_ids.add(message["params"]["requestId"])
                if message.get("method") == "Network.loadingFinished" and message["params"]["requestId"] in response_ids:
                    response_ids.discard(message["params"]["requestId"])
                    body_id = command("Network.getResponseBody", {"requestId": message["params"]["requestId"]})
                    body_result = receive_until(body_id, deadline)
                    body = body_result.get("result", {}).get("body")
                    if body:
                        try:
                            payload = parse_batchexecute_rpc(body, rpc_id)
                        except (ValueError, json.JSONDecodeError):
                            continue
                        captured.append(payload)
            if not captured:
                raise RuntimeError(f"New Google Trends CDP did not capture {rpc_id}")
            self._consecutive_failures = 0
            return captured
        except websocket.WebSocketException as error:
            self._consecutive_failures += 1
            if self._consecutive_failures >= 3:
                time.sleep(float(os.environ.get("GOOGLE_TRENDS_FAILURE_PAUSE", "15")))
                self._consecutive_failures = 0
            raise RuntimeError(f"Google Trends background target connection closed while capturing {rpc_id}") from error
        except RuntimeError:
            self._consecutive_failures += 1
            if self._consecutive_failures >= 3:
                time.sleep(float(os.environ.get("GOOGLE_TRENDS_FAILURE_PAUSE", "15")))
                self._consecutive_failures = 0
            raise
        else:
            self._consecutive_failures = 0
        finally:
            with suppress(Exception):
                ws.close()
            with suppress(Exception):
                browser_ws.send(json.dumps({"id": 2, "method": "Target.closeTarget", "params": {"targetId": created}}))
            with suppress(Exception):
                browser_ws.close()

    def related_rising(self, term: str, timeframe: str = "today 1-m") -> list[dict]:
        return [item for item in self.related_rising_all(term, timeframe) if item["type"] == "Breakout" or item.get("growth_percent", 0) >= 500]

    def related_rising_all(self, term: str, timeframe: str = "today 1-m") -> list[dict]:
        """Return every Rising row Google supplies (currently capped at 50)."""
        # The current Explore UI lazy-loads Rising queries only when a
        # comparison term is present. Its first response can be empty while the
        # panel finishes loading, so retry the same existing page before
        # treating the result as genuinely empty.
        for _ in range(3):
            if _:
                time.sleep(float(os.environ.get("GOOGLE_TRENDS_RISING_RETRY_DELAY", "4")) * _)
            related: list[dict] = []
            for payload in self._capture_rpc(
                [term, "gpts"],
                "fXqlme",
                timeframe,
                timeout_ms=self.rising_timeout_ms,
                activate_related_term=term,
            ):
                related.extend(parse_new_rising_queries(payload, minimum_growth=0, source_term=term))
            deduplicated = list({item["query"].lower(): item for item in related}.values())
            if deduplicated:
                return deduplicated
        return []

    def compare(self, candidate: str, baseline: str = "gpts", timeframe: str = "today 1-m") -> tuple[list[str], list[int], list[int]]:
        return self.compare_batch([candidate], baseline, timeframe)[candidate]

    def compare_batch(self, candidates: list[str], baseline: str = "gpts", timeframe: str = "today 1-m") -> dict[str, tuple[list[str], list[int], list[int]]]:
        if not candidates or len(candidates) > 4:
            raise ValueError("compare_batch accepts one to four candidates")
        data: dict[str, tuple[list[str], list[int]]] = {}
        for payload in self._capture_rpc([*candidates, baseline], "g4kJzf", timeframe):
            data.update(parse_new_timeline_values(payload))
        baseline_key = baseline.lower()
        if baseline_key not in data:
            raise RuntimeError("New Google Trends response has no gpts time series")
        times, baseline_values = data[baseline_key]
        return {
            candidate: (times, data[candidate.lower()][1], baseline_values)
            for candidate in candidates
            if candidate.lower() in data and len(data[candidate.lower()][0]) == len(times)
        }


def _run_new_cdp_operation(cdp_url: str, timeout_ms: int, rising_timeout_ms: int, operation: str, arguments: tuple):
    client = NewCdpGoogleTrendsClient(cdp_url, timeout_ms=timeout_ms, rising_timeout_ms=rising_timeout_ms)
    return getattr(client, operation)(*arguments)


class IsolatedNewCdpGoogleTrendsClient:
    """Run each new-Explore CDP operation in a killable worker process."""

    def __init__(
        self,
        cdp_url: str = "http://127.0.0.1:9229",
        timeout_ms: int = 20_000,
        rising_timeout_ms: int = 60_000,
        operation_timeout_seconds: float = 75,
    ) -> None:
        self.cdp_url = cdp_url
        self.timeout_ms = timeout_ms
        self.rising_timeout_ms = rising_timeout_ms
        self.operation_timeout_seconds = operation_timeout_seconds

    def _run(self, operation: str, arguments: tuple):
        return run_in_isolated_process(
            _run_new_cdp_operation,
            (self.cdp_url, self.timeout_ms, self.rising_timeout_ms, operation, arguments),
            timeout_seconds=self.operation_timeout_seconds,
        )

    def related_rising(self, term: str, timeframe: str = "today 1-m") -> list[dict]:
        return self._run("related_rising", (term, timeframe))

    def related_rising_all(self, term: str, timeframe: str = "today 1-m") -> list[dict]:
        return self._run("related_rising_all", (term, timeframe))

    def compare(self, candidate: str, baseline: str = "gpts", timeframe: str = "today 1-m") -> tuple[list[str], list[int], list[int]]:
        return self._run("compare", (candidate, baseline, timeframe))

    def compare_batch(self, candidates: list[str], baseline: str = "gpts", timeframe: str = "today 1-m") -> dict[str, tuple[list[str], list[int], list[int]]]:
        return self._run("compare_batch", (candidates, baseline, timeframe))
