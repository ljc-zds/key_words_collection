from keyword_loop.core.clients.cdp_proxy import CdpBrowser
from keyword_loop.core.clients.cdp_proxy import paginated_url


def test_cdp_browser_creates_a_background_target() -> None:
    page = object()

    class PageWaiter:
        value = page

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

    class Context:
        def expect_page(self, timeout: int):
            assert timeout == 30_000
            return PageWaiter()

    class Session:
        def __init__(self) -> None:
            self.calls = []
            self.detached = False

        def send(self, method: str, payload: dict):
            self.calls.append((method, payload))

        def detach(self) -> None:
            self.detached = True

    class Browser:
        def __init__(self) -> None:
            self.session = Session()

        def new_browser_cdp_session(self):
            return self.session

    browser = Browser()

    assert CdpBrowser()._new_background_page(browser, Context(), timeout_ms=30_000) is page
    assert browser.session.calls == [("Target.createTarget", {"url": "about:blank", "background": True})]
    assert browser.session.detached is True


def test_paginated_url_preserves_the_captured_query_and_sets_page() -> None:
    initial = (
        "https://sim.3ue.co/api/KeywordGenerator/google/suggest?"
        "keyword=dreamg&rowsPerPage=100&type=Broad&latest=28d"
    )

    assert paginated_url(initial, 2) == (
        "https://sim.3ue.co/api/KeywordGenerator/google/suggest?"
        "keyword=dreamg&rowsPerPage=100&type=Broad&latest=28d"
        "&orderBy=windowVolume+desc&page=2"
    )
