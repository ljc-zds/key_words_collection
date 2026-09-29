"""Client for the Web.Cafe keyword difficulty API."""
import json
import time
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from product_hunt.aitdk.product.product_hunt import trusted_ssl_context


class WebCafeError(RuntimeError):
    pass


class WebCafeClient:
    def __init__(self, token: str, *, gl: str = "us", hl: str = "en", interval: float = 6.0):
        self.token, self.gl, self.hl, self.interval = token, gl, hl, interval
        self._last_request = 0.0

    def estimate(self, keyword: str) -> dict:
        delay = self.interval - (time.monotonic() - self._last_request)
        if delay > 0:
            time.sleep(delay)
        url = "https://seo.web.cafe/kd/api/v1/kd?" + urlencode({"keyword": keyword, "gl": self.gl, "hl": self.hl})
        request = Request(url, headers={
            "Authorization": "Bearer " + self.token,
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/131 Safari/537.36",
        })
        self._last_request = time.monotonic()
        try:
            with urlopen(request, context=trusted_ssl_context(), timeout=45) as response:
                payload = json.load(response)
        except Exception as error:
            raise WebCafeError(type(error).__name__) from error
        if not isinstance(payload, dict) or payload.get("error"):
            raise WebCafeError(str(payload.get("error", "invalid response")))
        return payload


def explain_payload(keyword: str, payload: dict) -> tuple[str, str, str]:
    is_brand = payload.get("keywordType") == "brand"
    return (
        f"用户在搜索与“{keyword}”相关的产品、内容或解决方案（{payload.get('level', '未知难度')}）。",
        "品牌导航型" if is_brand else "通用需求型",
        "先确认品牌授权与差异化价值，再决定是否投入" if is_brand else "适合制作工具、模板或订阅服务承接",
    )


def retrieved_at() -> str:
    return datetime.now(timezone.utc).isoformat()
