"""Annotation-only AI assessment for already accepted keyword opportunities."""
import json
from urllib.request import Request, urlopen

from product_hunt.aitdk.product.product_hunt import trusted_ssl_context


class AIScreenError(RuntimeError):
    pass


_REQUIRED = ("decision", "score", "tool_page_fit", "exact_match_domain_fit", "recommended_page_type", "monetization", "reason")


def parse_screen_response(text: str) -> dict[str, object]:
    payload = json.loads(text)
    if not isinstance(payload, dict) or any(field not in payload for field in _REQUIRED):
        raise ValueError("missing AI screen field")
    if payload["decision"] not in {"保留", "淘汰"}:
        raise ValueError("AI decision must be 保留 or 淘汰")
    return {field: payload[field] for field in _REQUIRED}


def parse_response_api_payload(payload: dict) -> dict[str, object]:
    for output in payload.get("output", []):
        if not isinstance(output, dict):
            continue
        for content in output.get("content", []):
            if isinstance(content, dict) and content.get("type") == "output_text" and content.get("text"):
                return parse_screen_response(str(content["text"]))
    raise ValueError("responses payload has no output text")


class AIScreenClient:
    def __init__(self, api_key: str, *, model: str, base_url: str = "https://api.openai.com") -> None:
        self.api_key, self.model = api_key, model
        normalized = base_url.rstrip("/")
        self.endpoint = normalized + ("/responses" if normalized.endswith("/v1") else "/v1/responses")

    def assess(self, keyword: str, semrush: dict, serp: dict, *, stage: str = "final") -> dict[str, object]:
        prompt = {
            "keyword": keyword,
            "semrush": semrush,
            "serp": serp,
            "task": ("初筛：只淘汰明显没有用户需求或商业价值的关键词，不展开具体原因；" if stage == "initial" else "最终判断：结合 Semrush、Serper 和哥飞 KD，判断是否值得建设并给出详细变现方案；") + "关键词可以对应工具站、游戏站、内容站、资源目录、数据站、比较站或联盟站。Return JSON only: decision (保留|淘汰), score (0-100), tool_page_fit (low|medium|high), exact_match_domain_fit (low|medium|high), recommended_page_type, monetization, reason. 初筛淘汰时 reason 固定为‘AI初筛：明显无价值’；最终判断时 monetization 和 reason 用简体中文说明具体变现路径。",
        }
        request = Request(
            self.endpoint,
            data=json.dumps({
                "model": self.model,
                "input": [{"role": "user", "content": [{"type": "input_text", "text": json.dumps(prompt, ensure_ascii=False)}]}],
                "text": {"format": {"type": "json_object"}},
                "store": False,
            }).encode(),
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, context=trusted_ssl_context(), timeout=45) as response:
                data = json.load(response)
        except Exception as error:
            raise AIScreenError(type(error).__name__) from error
        return parse_response_api_payload(data)

    def assess_batch(self, items: list[dict], *, stage: str = "final") -> list[dict[str, object]]:
        """Assess up to 10 keywords in one model request, preserving order."""
        if not items or len(items) > 10:
            raise ValueError("AI batch size must be between 1 and 10")
        mode = "初筛：只过滤明显没有用户需求或商业价值的关键词，reason 固定为 AI初筛：明显无价值；" if stage == "initial" else "最终判断：综合全部数据给出变现路径；monetization 不超过 180 个汉字，reason 不超过 220 个汉字，recommended_page_type 不超过 50 个汉字；"
        prompt = {"task": mode + "逐条返回 JSON 数组，顺序必须与输入一致。每项包含 decision、score、tool_page_fit、exact_match_domain_fit、recommended_page_type、monetization、reason。", "items": items}
        request = Request(self.endpoint, data=json.dumps({"model": self.model, "input": [{"role": "user", "content": [{"type": "input_text", "text": json.dumps(prompt, ensure_ascii=False)}]}], "text": {"format": {"type": "json_object"}}, "store": False}).encode(), headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}, method="POST")
        try:
            with urlopen(request, context=trusted_ssl_context(), timeout=90) as response:
                data = json.load(response)
            text = next(c["text"] for o in data.get("output", []) if isinstance(o, dict) for c in o.get("content", []) if isinstance(c, dict) and c.get("type") == "output_text")
            payload = json.loads(text)
            results = payload.get("results", payload) if isinstance(payload, dict) else payload
            if not isinstance(results, list) or len(results) != len(items): raise ValueError("AI batch result count mismatch")
            return [parse_screen_response(json.dumps(item, ensure_ascii=False)) for item in results]
        except Exception as error:
            # Degrade failed batches instead of losing all their work. This
            # also handles oversized SERP payloads and occasional malformed
            # model output while preserving input order.
            if len(items) > 1:
                midpoint = len(items) // 2
                try:
                    return self.assess_batch(items[:midpoint], stage=stage) + self.assess_batch(items[midpoint:], stage=stage)
                except AIScreenError:
                    pass
            if len(items) == 1:
                return [self.assess(items[0]["keyword"], items[0].get("semrush", {}), items[0].get("serper", {}), stage=stage)]
            raise AIScreenError(type(error).__name__) from error
