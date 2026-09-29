"""Google SERP annotations backed by the official Serper API."""
import json
from urllib.request import Request, urlopen

from product_hunt.aitdk.product.product_hunt import trusted_ssl_context


class SerperError(RuntimeError):
    pass


def _text_list(items: object) -> list[str]:
    if not isinstance(items, list):
        return []
    result: list[str] = []
    for item in items:
        if isinstance(item, dict):
            text = item.get("question") or item.get("query")
            if text:
                result.append(str(text))
        elif isinstance(item, str):
            result.append(item)
    return result


class SerperClient:
    def __init__(self, api_key: str, *, gl: str = "us", hl: str = "en") -> None:
        self.api_key, self.gl, self.hl = api_key, gl, hl

    def analyze(self, keyword: str) -> dict:
        request = Request(
            "https://google.serper.dev/search",
            data=json.dumps({"q": keyword, "gl": self.gl, "hl": self.hl, "num": 10}).encode(),
            headers={"X-API-KEY": self.api_key, "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, context=trusted_ssl_context(), timeout=30) as response:
                data = json.load(response)
        except Exception as error:
            raise SerperError(type(error).__name__) from error
        if not isinstance(data, dict):
            raise SerperError("invalid response")
        organic = [
            {"position": item.get("position"), "title": item.get("title", ""), "link": item.get("link", "")}
            for item in data.get("organic", [])
            if isinstance(item, dict)
        ]
        strong_sites = sum(
            1 for item in organic
            if any(host in str(item.get("link", "")).lower() for host in ("wikipedia.org", "reddit.com", "youtube.com", ".gov", ".edu"))
        )
        return {
            "organic": organic,
            "paa": _text_list(data.get("peopleAlsoAsk")),
            "related": _text_list(data.get("relatedSearches")),
            "strong_site_count": strong_sites,
        }
