import json
from datetime import date
from urllib.error import HTTPError, URLError
from urllib.request import Request

from product_hunt.aitdk.product.product_hunt import (
    fetch_posts_for_date,
    _read_request_json,
    load_developer_token,
    normalize_posts,
    trusted_ssl_context,
)


def test_normalize_posts_keeps_products_with_websites() -> None:
    payload = {
        "data": {
            "posts": {
                "edges": [
                    {
                        "node": {
                            "id": "1",
                            "name": "Example",
                            "tagline": "A tool",
                            "url": "https://www.producthunt.com/posts/example",
                            "website": "https://www.producthunt.com/r/ignored",
                            "productLinks": [{"type": "Website", "url": "https://www.producthunt.com/r/site"}],
                            "createdAt": "2026-08-21T00:00:00Z",
                            "votesCount": 12,
                        }
                    }
                ]
            }
        }
    }
    candidates = normalize_posts(payload)
    assert candidates[0].website_url == "https://www.producthunt.com/r/site"
    assert candidates[0].name == "Example"


def test_load_developer_token_reads_only_expected_variable(tmp_path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("PRODUCT_HUNT_DEVELOPER_TOKEN=token-value\n", encoding="utf-8")
    assert load_developer_token(env_file) == "token-value"


def test_trusted_ssl_context_requires_certificate_verification() -> None:
    assert trusted_ssl_context().verify_mode.name == "CERT_REQUIRED"


def test_fetch_posts_for_date_reads_every_cursor_page() -> None:
    pages = [
        {
            "data": {"posts": {
                "pageInfo": {"hasNextPage": True, "endCursor": "cursor-1"},
                "edges": [{"node": {
                    "id": "1", "name": "First", "tagline": "One", "url": "https://ph/1",
                    "website": "https://first.example", "productLinks": [],
                    "createdAt": "2026-08-30T01:00:00Z", "votesCount": 1,
                }}],
            }}
        },
        {
            "data": {"posts": {
                "pageInfo": {"hasNextPage": False, "endCursor": "cursor-2"},
                "edges": [{"node": {
                    "id": "2", "name": "Second", "tagline": "Two", "url": "https://ph/2",
                    "website": "https://second.example", "productLinks": [],
                    "createdAt": "2026-08-30T22:00:00Z", "votesCount": 2,
                }}],
            }}
        },
    ]
    requests = []

    def request_page(request):
        requests.append(json.loads(request.data))
        return pages.pop(0)

    products = fetch_posts_for_date("token", date(2026, 8, 30), request_page=request_page)

    assert [product.name for product in products] == ["First", "Second"]
    assert requests[0]["variables"] == {
        "first": 50,
        "after": None,
        "postedAfter": "2026-08-30T00:00:00Z",
        "postedBefore": "2026-08-31T00:00:00Z",
    }
    assert requests[1]["variables"]["after"] == "cursor-1"


def test_product_hunt_request_retries_transient_network_errors() -> None:
    attempts = 0

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self):
            return b'{"data": {}}'

    def opener(*_args, **_kwargs):
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise URLError("temporary TLS EOF")
        return Response()

    assert _read_request_json(Request("https://example.com"), opener=opener) == {"data": {}}
    assert attempts == 3


def test_product_hunt_request_waits_for_rate_limit_reset_before_retrying() -> None:
    attempts = 0
    waits = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self):
            return b'{"data": {}}'

    def opener(*_args, **_kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise HTTPError(
                "https://api.producthunt.com/v2/api/graphql", 429, "limited",
                {"X-Rate-Limit-Reset": "17"}, None,
            )
        return Response()

    assert _read_request_json(Request("https://example.com"), opener=opener, sleeper=waits.append) == {"data": {}}
    assert waits == [17]
    assert attempts == 2
