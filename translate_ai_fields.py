"""Translate historical AI-screen text fields to Simplified Chinese and republish."""
import json
from datetime import date
from urllib.request import Request, urlopen

from product_hunt.aitdk.product.product_hunt import trusted_ssl_context
from keyword_loop.core.publishing.feishu import load_env, publish_wiki
from keyword_loop.core.data.store import KeywordStore
from run_serper_batch import DB, FEISHU_URL, validations_for


def response_text(payload: dict) -> str:
    for output in payload.get("output", []):
        for content in output.get("content", []) if isinstance(output, dict) else []:
            if isinstance(content, dict) and content.get("type") == "output_text":
                return str(content.get("text", ""))
    raise RuntimeError("AI translation returned no text")


def translation_items(value: object) -> list[dict]:
    if isinstance(value, str):
        try:
            return translation_items(json.loads(value))
        except json.JSONDecodeError:
            return []
    if isinstance(value, list):
        direct = [item for item in value if isinstance(item, dict) and "keyword" in item]
        return direct or next((found for item in value if (found := translation_items(item))), [])
    if isinstance(value, dict):
        if "keyword" in value:
            return [value]
        return next((found for item in value.values() if (found := translation_items(item))), [])
    return []


def main() -> None:
    env = load_env()
    store = KeywordStore(DB)
    candidates = store.daily_accepted_candidates(date.today())
    items = []
    for candidate in candidates:
        payload = store.validation(candidate.keyword, candidate.market, "ai_screen")
        if payload:
            items.append({"keyword": candidate.keyword, "recommended_page_type": payload["recommended_page_type"], "reason": payload["reason"]})
    request_payload = {
        "model": env["AI_SCREEN_MODEL"],
        "input": [{"role": "user", "content": [{"type": "input_text", "text": json.dumps({
            "task": "Translate each recommended_page_type and reason into concise Simplified Chinese. Preserve every keyword exactly. Return JSON only as an array of objects with keyword, recommended_page_type, reason.",
            "items": items,
        }, ensure_ascii=False)}]}],
        "text": {"format": {"type": "json_object"}},
        "store": False,
    }
    base_url = env["AI_SCREEN_BASE_URL"].rstrip("/")
    endpoint = base_url + ("/responses" if base_url.endswith("/v1") else "/v1/responses")
    request = Request(endpoint, data=json.dumps(request_payload, ensure_ascii=False).encode(), headers={"Authorization": f"Bearer {env['OPENAI_API_KEY']}", "Content-Type": "application/json"}, method="POST")
    with urlopen(request, context=trusted_ssl_context(), timeout=90) as response:
        translated = json.loads(response_text(json.load(response)))
    translated_items = translation_items(translated)
    by_keyword = {str(item["keyword"]): item for item in translated_items if isinstance(item, dict)}
    for candidate in candidates:
        old = store.validation(candidate.keyword, candidate.market, "ai_screen")
        translated_item = by_keyword.get(candidate.keyword)
        if old and translated_item:
            store.record_validation(candidate.keyword, candidate.market, "ai_screen", {**old, "recommended_page_type": translated_item["recommended_page_type"], "reason": translated_item["reason"]})
    from run_ai_screen_batch import main as publish
    publish()
    print(f"translated={len(by_keyword)} published={len(candidates)}")


if __name__ == "__main__":
    main()
