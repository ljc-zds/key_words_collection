"""Collect unfiltered Prompt Intelligence keyword clusters from both providers."""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import time
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from keyword_loop.core.clients.semrush_browser import SemrushBrowserProvider
from keyword_loop.core.clients.similarweb import SimilarwebCollector


DEFAULT_SEEDS = (
    "prompt generator",
    "image to prompt",
    "video to prompt",
    "prompt optimizer",
    "prompt enhancer",
    "prompt improver",
    "prompt library",
    "prompt templates",
    "prompt manager",
    "text to prompt",
)

MODEL_TERMS = (
    "chatgpt", "gpt", "claude", "gemini", "midjourney", "flux", "stable diffusion",
    "suno", "kling", "veo", "seedance", "comfyui", "nano banana", "dall-e", "dalle",
)
RISK_TERMS = ("nsfw", "porn", "nude", "jailbreak", "uncensored")


def cluster_keyword(keyword: str) -> str:
    value = keyword.lower()
    if any(term in value for term in RISK_TERMS):
        return "风险/成人/越狱"
    if any(term in value for term in ("video to prompt", "video prompt extractor", "extract prompt from video")):
        return "视频反推 Prompt"
    if any(term in value for term in (
        "image to prompt", "photo to prompt", "picture to prompt", "prompt from image",
        "prompt generator from image", "image prompt extractor", "reverse image prompt",
    )):
        return "图片反推 Prompt"
    if any(term in value for term in ("audio to prompt", "music to prompt", "song to prompt")):
        return "音频/音乐反推 Prompt"
    if any(term in value for term in (
        "prompt optimizer", "prompt enhancer", "prompt improver", "improve prompt", "enhance prompt",
        "optimize prompt", "prompt rewriter", "rewrite prompt", "prompt expander", "refine prompt",
    )):
        return "Prompt 优化增强"
    if any(term in value for term in (
        "prompt library", "prompt libraries", "prompt template", "prompt examples", "prompt ideas",
        "prompt database", "prompt collection", "prompt repository", "prompt marketplace",
    )):
        return "Prompt 模板与词库"
    if any(term in value for term in (
        "prompt manager", "prompt management", "manage prompts", "prompt organizer", "prompt version",
        "prompt workspace", "prompt collaboration", "prompt storage",
    )):
        return "Prompt 管理与协作"
    if any(term in value for term in MODEL_TERMS):
        return "模型专属 Prompt"
    if any(term in value for term in (
        "prompt tester", "test prompt", "prompt evaluator", "evaluate prompt", "prompt engineering",
        "prompt injection", "prompt debugging", "prompt benchmark",
    )):
        return "Prompt 工程与测试"
    if any(term in value for term in (
        "writing prompt", "art prompt", "design prompt", "marketing prompt", "seo prompt",
        "coding prompt", "code prompt", "business prompt", "roleplay prompt", "character prompt",
        "story prompt", "drawing prompt", "logo prompt", "tattoo prompt", "product photo prompt",
    )):
        return "场景化 Prompt"
    if any(term in value for term in (
        "prompt generator", "prompts generator", "prompt maker", "prompt builder", "generate prompt",
        "ai prompt", "text to prompt",
    )):
        return "通用 Prompt 生成"
    return "相关词/待人工复核"


def normalized_row(provider: str, seed: str, raw: dict) -> dict:
    keyword = " ".join(str(raw.get("keyword") or raw.get("phrase") or "").split()).lower()
    return {
        "keyword": keyword,
        "cluster": cluster_keyword(keyword),
        "provider": provider,
        "market": raw.get("market") or raw.get("database") or ("global" if provider == "similarweb" else "us"),
        "seed": seed,
        "volume": raw.get("volume", raw.get("average_volume")),
        "kd": raw.get("kd", raw.get("difficulty")),
        "cpc": raw.get("cpc"),
        "intent": raw.get("intent"),
        "leading_site": raw.get("leading_site"),
        "raw_json": json.dumps(raw, ensure_ascii=False, separators=(",", ":")),
    }


def collect_provider(provider: str, seed: str, cdp_url: str, semrush_cap: int = 0) -> list[dict]:
    if provider == "similarweb":
        client = SimilarwebCollector(cdp_url=cdp_url, per_root_cap=0, discovery_filters=False)
        return [normalized_row(provider, seed, dict(asdict(item), volume=item.average_volume)) for item in client.collect(seed)]
    client = SemrushBrowserProvider(cdp_url=cdp_url, per_root_cap=semrush_cap, discovery_filters=False)
    response = client.query(seed)
    return [normalized_row(provider, seed, row) for row in response["keywords"]]


def collect_with_retry(provider: str, seed: str, cdp_url: str, semrush_cap: int = 0) -> tuple[list[dict], str | None]:
    last_error = None
    for attempt in range(2):
        try:
            return collect_provider(provider, seed, cdp_url, semrush_cap), None
        except Exception as error:  # Browser/network failures need one clean retry.
            last_error = f"{type(error).__name__}: {error}"
            if attempt == 0:
                time.sleep(3)
    return [], last_error


def write_sqlite(path: Path, rows: list[dict], runs: list[dict]) -> None:
    with sqlite3.connect(path) as connection:
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS keyword_records (
                keyword TEXT NOT NULL, cluster TEXT NOT NULL, provider TEXT NOT NULL,
                market TEXT NOT NULL, seed TEXT NOT NULL, volume REAL, kd REAL, cpc REAL,
                intent TEXT, leading_site TEXT, raw_json TEXT NOT NULL,
                PRIMARY KEY(keyword, provider, market, seed)
            );
            CREATE TABLE IF NOT EXISTS collection_runs (
                provider TEXT NOT NULL, seed TEXT NOT NULL, row_count INTEGER NOT NULL,
                error TEXT, collected_at TEXT NOT NULL,
                PRIMARY KEY(provider, seed)
            );
        """)
        connection.executemany(
            """INSERT OR REPLACE INTO keyword_records
               (keyword,cluster,provider,market,seed,volume,kd,cpc,intent,leading_site,raw_json)
               VALUES (:keyword,:cluster,:provider,:market,:seed,:volume,:kd,:cpc,:intent,:leading_site,:raw_json)""",
            rows,
        )
        connection.executemany(
            """INSERT OR REPLACE INTO collection_runs(provider,seed,row_count,error,collected_at)
               VALUES (:provider,:seed,:row_count,:error,:collected_at)""",
            runs,
        )


def read_sqlite(path: Path) -> tuple[list[dict], list[dict]]:
    with sqlite3.connect(path) as connection:
        connection.row_factory = sqlite3.Row
        rows = [dict(row) for row in connection.execute(
            """SELECT keyword,cluster,provider,market,seed,volume,kd,cpc,intent,leading_site,raw_json
               FROM keyword_records"""
        )]
        runs = [dict(row) for row in connection.execute(
            """SELECT provider,seed,row_count,error,collected_at
               FROM collection_runs ORDER BY provider,seed"""
        )]
    return rows, runs


def best_metric_rows(rows: list[dict]) -> list[dict]:
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in rows:
        grouped[(row["keyword"], row["provider"])].append(row)
    result = []
    for values in grouped.values():
        chosen = max(values, key=lambda item: (item["volume"] is not None, item["volume"] or -1))
        result.append({key: value for key, value in chosen.items() if key != "raw_json"})
    return sorted(result, key=lambda item: (item["cluster"], -(item["volume"] or -1), item["keyword"]))


def write_csv(path: Path, rows: list[dict]) -> None:
    fields = ["keyword", "cluster", "provider", "market", "seed", "volume", "kd", "cpc", "intent", "leading_site"]
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows({field: row.get(field) for field in fields} for row in rows)


def write_report(path: Path, rows: list[dict], runs: list[dict]) -> None:
    unique = best_metric_rows(rows)
    clusters = Counter(row["cluster"] for row in unique)
    providers = Counter(row["provider"] for row in unique)
    provider_scope = "、".join(f"{provider} {'Global' if provider == 'similarweb' else 'US'}" for provider in providers)
    failed_runs = [run for run in runs if run.get("error")]
    lines = [
        "# Prompt Intelligence 未过滤关键词簇",
        "",
        f"采集时间：{datetime.now().astimezone().isoformat(timespec='seconds')}",
        "",
        f"本轮数据口径：{provider_scope}；未设置搜索量、KD、CPC 或意图过滤条件。",
        "",
    ]
    if failed_runs:
        lines.extend([
            "失败的查询不会计为 0 条，也不会混入成功结果；详细原因见采集状态。",
            "",
        ])
    lines.extend([
        f"数据库记录：{len(rows):,}；来源内去重关键词：{len(unique):,}；跨来源唯一关键词：{len({row['keyword'] for row in unique}):,}。",
        "",
        "## 采集状态",
        "",
        "| 平台 | 词根 | 返回记录 | 状态 |",
        "|---|---|---:|---|",
    ])
    for run in runs:
        lines.append(f"| {run['provider']} | `{run['seed']}` | {run['row_count']:,} | {'失败：' + run['error'] if run['error'] else '正常'} |")
    lines.extend(["", "## 关键词簇规模", "", "| 关键词簇 | 来源内去重词数 |", "|---|---:|"])
    for cluster, count in clusters.most_common():
        lines.append(f"| {cluster} | {count:,} |")
    lines.extend(["", "## 平台覆盖", "", "| 平台 | 去重关键词 |", "|---|---:|"])
    for provider, count in providers.items():
        lines.append(f"| {provider} | {count:,} |")
    lines.extend(["", "## 各簇代表词", ""])
    for cluster in clusters:
        candidates = [row for row in unique if row["cluster"] == cluster]
        candidates.sort(key=lambda item: (item["volume"] is None, -(item["volume"] or -1)))
        lines.extend([f"### {cluster}", "", "| 关键词 | 平台 | 搜索量 | KD | CPC |", "|---|---|---:|---:|---:|"])
        for row in candidates[:20]:
            lines.append(f"| `{row['keyword']}` | {row['provider']} | {row['volume'] if row['volume'] is not None else ''} | {row['kd'] if row['kd'] is not None else ''} | {row['cpc'] if row['cpc'] is not None else ''} |")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cdp-url", default="http://127.0.0.1:9222")
    parser.add_argument("--output", type=Path, default=Path("outputs") / f"prompt_intelligence_{datetime.now():%Y%m%d}")
    parser.add_argument("--seeds", default=",".join(DEFAULT_SEEDS))
    parser.add_argument("--providers", default="similarweb,semrush")
    parser.add_argument("--semrush-cap", type=int, default=0, help="Rows per Semrush seed; 0 means all pages")
    args = parser.parse_args()
    seeds = [seed.strip() for seed in args.seeds.split(",") if seed.strip()]
    providers = [provider.strip() for provider in args.providers.split(",") if provider.strip()]
    if not providers or set(providers) - {"similarweb", "semrush"}:
        raise SystemExit("--providers only accepts similarweb and/or semrush")
    if args.semrush_cap < 0:
        raise SystemExit("--semrush-cap must be nonnegative")
    args.output.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    runs: list[dict] = []
    for provider in providers:
        for seed in seeds:
            found, error = collect_with_retry(provider, seed, args.cdp_url, args.semrush_cap)
            rows.extend(found)
            run = {
                "provider": provider,
                "seed": seed,
                "row_count": len(found),
                "error": error,
                "collected_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            }
            runs.append(run)
            print(json.dumps(run, ensure_ascii=False), flush=True)
    database_path = args.output / "prompt_intelligence_keywords.sqlite3"
    write_sqlite(database_path, rows, runs)
    merged_rows, merged_runs = read_sqlite(database_path)
    compact = best_metric_rows(merged_rows)
    write_csv(args.output / "prompt_intelligence_keywords.csv", compact)
    (args.output / "prompt_intelligence_keywords.json").write_text(
        json.dumps({"runs": merged_runs, "records": merged_rows}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    write_report(args.output / "关键词簇分析.md", merged_rows, merged_runs)
    print(json.dumps({"output": str(args.output), "records": len(merged_rows), "deduplicated": len(compact)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
