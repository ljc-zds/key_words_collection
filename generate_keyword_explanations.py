#!/usr/bin/env python3
"""Generate cached keyword-purpose explanations with DashScope."""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from product_hunt.aitdk.product.product_hunt import trusted_ssl_context


ENDPOINT = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"


def parse_explanations(text: str) -> dict[str, str]:
    clean = text.strip()
    clean = re.sub(r"^```(?:json)?\s*", "", clean, flags=re.I)
    clean = re.sub(r"\s*```$", "", clean)
    try:
        payload = json.loads(clean)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", clean, flags=re.S)
        if not match:
            return {}
        try:
            payload = json.loads(match.group(0))
        except json.JSONDecodeError:
            return {}
    rows = payload.get("items", []) if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        return {}
    result: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        keyword = str(row.get("keyword", "")).strip().lower()
        explanation = " ".join(str(row.get("explanation", "")).split())
        if keyword and explanation:
            result[keyword] = explanation
    return result


def _prompt(items: list[dict[str, Any]]) -> str:
    compact = [
        {
            "keyword": item["keyword"],
            "site_type": item.get("site_type", ""),
            "risk": item.get("risk_notes", ""),
        }
        for item in items
    ]
    return json.dumps({
        "task": (
            "逐条解释英语SEO关键词的真实含义和用户需求。每条用简体中文写80-140字，必须具体说明："
            "用户想完成什么、通常输入或查看什么、网站应输出什么、适合的核心功能、必要风险。"
            "不要只说这是计算器/工具/资料站；遇到缩写要解释全称和适用国家或行业。"
            "不要虚构精确规则，不要评价搜索量或KD。保持keyword原文完全不变。"
            "只返回JSON对象，格式为 {\"items\":[{\"keyword\":\"...\",\"explanation\":\"...\"}]}。"
        ),
        "items": compact,
    }, ensure_ascii=False)


def request_batch(api_key: str, model: str, items: list[dict[str, Any]]) -> dict[str, str]:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "你是严谨的SEO关键词语义分析师，只输出有效JSON。"},
            {"role": "user", "content": _prompt(items)},
        ],
        "temperature": 0.1,
        "max_tokens": max(1200, len(items) * 220),
        "enable_thinking": False,
        "response_format": {"type": "json_object"},
    }
    request = Request(
        ENDPOINT,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, context=trusted_ssl_context(), timeout=180) as response:
        body = json.load(response)
    return parse_explanations(body["choices"][0]["message"]["content"])


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("outputs/keyword_site_analysis_20260911_local/keyword_site_analysis.json"))
    parser.add_argument("--cache", type=Path, default=Path("outputs/keyword_site_analysis_20260911_local/keyword_explanations_qwen3.6-plus.json"))
    parser.add_argument("--model", default="qwen3.6-plus")
    parser.add_argument("--batch-size", type=int, default=20)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    api_key = os.environ.get("DASHSCOPE_API_KEY")
    if not api_key:
        raise SystemExit("DASHSCOPE_API_KEY is required")

    data = json.loads(args.input.read_text(encoding="utf-8"))
    cached_payload = json.loads(args.cache.read_text(encoding="utf-8")) if args.cache.exists() else {}
    cache = cached_payload.get("explanations", {}) if isinstance(cached_payload, dict) else {}
    candidates = data.get("keywords", [])
    pending = [item for item in candidates if item["keyword"] not in cache]
    if args.limit is not None:
        pending = pending[:args.limit]
    batches = [pending[start:start + args.batch_size] for start in range(0, len(pending), args.batch_size)]
    completed = 0

    def run(batch: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, str]]:
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                return batch, request_batch(api_key, args.model, batch)
            except (HTTPError, URLError, TimeoutError, KeyError, json.JSONDecodeError) as error:
                last_error = error
                time.sleep(2 ** attempt)
        raise RuntimeError(f"batch failed after retries: {last_error}")

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = [executor.submit(run, batch) for batch in batches]
        for future in as_completed(futures):
            batch, generated = future.result()
            requested = {item["keyword"] for item in batch}
            for keyword, explanation in generated.items():
                if keyword in requested:
                    cache[keyword] = explanation
            completed += len(batch)
            _write_json(args.cache, {
                "model": args.model,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "explanations": cache,
            })
            print(f"processed={completed}/{len(pending)} cached={len(cache)}", flush=True)

    for item in candidates:
        explanation = cache.get(item["keyword"])
        if explanation:
            item["keyword_purpose"] = explanation
            item["explanation_source"] = args.model
    data.setdefault("metadata", {})["explanation_model"] = args.model
    data["metadata"]["explanation_count"] = sum(1 for item in candidates if item.get("explanation_source") == args.model)
    _write_json(args.input, data)
    print(f"updated={data['metadata']['explanation_count']} total={len(candidates)}")


if __name__ == "__main__":
    main()
