#!/usr/bin/env python3
import json
import time
from pathlib import Path
from keyword_loop.core.clients.webcafe import WebCafeClient, WebCafeError
from keyword_loop.core.clients.serper import SerperClient, SerperError
from keyword_loop.core.publishing.feishu import load_env

ROOT = Path(__file__).parent
OUT = ROOT / "outputs/keyword_site_analysis_20260911_local/top10_gofei_serp_analysis.json"

data = json.loads((ROOT / "outputs/keyword_site_analysis_20260911_local/keyword_site_analysis.json").read_text())
top = [item for item in data["keywords"] if item.get("priority") == "P0"]
env = load_env()
gofei = WebCafeClient(env["SEO_WEBCAFE_TOKEN"], gl="us", hl="en", interval=7)
serper = SerperClient(env["SERPER_API_KEY"], gl="us", hl="en")
rows = []
for index, item in enumerate(top, 1):
    keyword = item["keyword"]
    row = {"rank": index, "keyword": keyword, "local": item}
    try:
        row["gofei"] = gofei.estimate(keyword)
    except Exception as exc:
        row["gofei_error"] = type(exc).__name__
    try:
        row["serp"] = serper.analyze(keyword)
        india_markers = (".in/", ".in:", "groww", "zerodha", "hdfc", "sbi", "icic", "kotak", "bajaj", "nipponindia", "razorpay", "tvscredit", "bikedekho", "bikewale", "royalsundaram")
        organic = row["serp"].get("organic", [])
        row["serp_excluding_india"] = {
            **row["serp"],
            "organic": [x for x in organic if not any(marker in str(x.get("link", "")).lower() for marker in india_markers)],
        }
        row["serp_excluding_india"]["strong_site_count"] = sum(
            1 for x in row["serp_excluding_india"]["organic"]
            if any(host in str(x.get("link", "")).lower() for host in ("wikipedia.org", "reddit.com", "youtube.com", ".gov", ".edu"))
        )
    except Exception as exc:
        row["serp_error"] = type(exc).__name__
    rows.append(row)
    print(f"completed={index}/{len(top)} keyword={keyword!r}", flush=True)
OUT.write_text(json.dumps({"market": "US", "india_sites_excluded": True, "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "rows": rows}, ensure_ascii=False, indent=2))
print(f"wrote={OUT}")
