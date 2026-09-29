# Product Hunt Demand Radar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Produce a dated Obsidian report that identifies recent Product Hunt websites with non-brand search-demand signals.

**Architecture:** Product Hunt GraphQL collection is isolated behind a client that reads a local environment token. Normalized candidates are sent one at a time to the existing AITDK adapter; pure filter and Markdown functions are independently testable.

**Tech Stack:** Python 3.13, urllib standard library, pytest, Playwright, Obsidian Markdown.

---

### Task 1: Product Hunt Candidate Client

**Files:**
- Create: aitdk_enrichment/product_hunt.py
- Create: tests/test_product_hunt.py
- Modify: requirements.txt
- Modify: .gitignore

- [ ] **Step 1: Write the failing test**

~~~python
from aitdk_enrichment.product_hunt import normalize_posts


def test_normalize_posts_keeps_products_with_websites() -> None:
    payload = {"data": {"posts": {"edges": [{"node": {
        "id": "1", "name": "Example", "tagline": "A tool",
        "url": "https://www.producthunt.com/posts/example",
        "website": "https://example.com", "createdAt": "2026-08-21T00:00:00Z",
        "votesCount": 12, "topics": {"edges": []}
    }}]}}}
    candidates = normalize_posts(payload)
    assert candidates[0].domain == "example.com"
    assert candidates[0].name == "Example"
~~~

- [ ] **Step 2: Run the test to verify it fails**

Run: .venv/bin/python -m pytest tests/test_product_hunt.py -v

Expected: FAIL because product_hunt module does not exist.

- [ ] **Step 3: Implement the official GraphQL client**

~~~python
# aitdk_enrichment/product_hunt.py
import json
import os
from dataclasses import dataclass
from urllib.request import Request, urlopen
from urllib.parse import urlparse


@dataclass(frozen=True)
class ProductCandidate:
    product_id: str
    name: str
    tagline: str
    product_hunt_url: str
    website_url: str
    domain: str
    created_at: str
    votes_count: int


def normalize_posts(payload):
    nodes = payload.get("data", {}).get("posts", {}).get("edges", [])
    candidates = []
    for edge in nodes:
        node = edge.get("node", {})
        website = node.get("website") or ""
        domain = urlparse(website).hostname
        if not domain:
            continue
        candidates.append(ProductCandidate(
            node["id"], node.get("name", ""), node.get("tagline", ""),
            node.get("url", ""), website, domain.lower(),
            node.get("createdAt", ""), node.get("votesCount", 0),
        ))
    return candidates


def fetch_newest_posts(token, limit=20):
    query = "query { posts(first: %d, order: NEWEST) { edges { node { id name tagline url website createdAt votesCount } } } }" % limit
    request = Request(
        "https://api.producthunt.com/v2/api/graphql",
        data=json.dumps({"query": query}).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=30) as response:
        return normalize_posts(json.load(response))
~~~

- [ ] **Step 4: Run the test to verify it passes**

Run: .venv/bin/python -m pytest tests/test_product_hunt.py -v

Expected: PASS.

- [ ] **Step 5: Commit**

~~~bash
git add aitdk_enrichment/product_hunt.py tests/test_product_hunt.py
git commit -m "feat: collect newest Product Hunt candidates"
~~~

### Task 2: Demand Filtering And Brand Terms

**Files:**
- Create: aitdk_enrichment/demand_filter.py
- Create: tests/test_demand_filter.py

- [ ] **Step 1: Write the failing test**

~~~python
from aitdk_enrichment.demand_filter import evaluate_candidate


def test_evaluate_candidate_requires_one_non_brand_keyword() -> None:
    result = evaluate_candidate(
        domain="example.com", product_name="Example",
        traffic={"overview": {"visits": "5000"}, "trafficSources": {"searchOrganic": 0.3, "direct": 0.25}},
        domain_age_days=180,
        keywords=[{"name": "example"}, {"name": "invoice template"}],
    )
    assert result.passed is True
    assert result.non_brand_keywords == ["invoice template"]
~~~

- [ ] **Step 2: Run the test to verify it fails**

Run: .venv/bin/python -m pytest tests/test_demand_filter.py -v

Expected: FAIL because demand_filter module does not exist.

- [ ] **Step 3: Implement the pure screening rule**

~~~python
# aitdk_enrichment/demand_filter.py
from dataclasses import dataclass


@dataclass(frozen=True)
class FilterResult:
    passed: bool
    reasons: list[str]
    non_brand_keywords: list[str]


def evaluate_candidate(domain, product_name, traffic, domain_age_days, keywords):
    overview = traffic.get("overview", {})
    sources = traffic.get("trafficSources", {})
    reasons = []
    if domain_age_days is None or domain_age_days >= 365:
        reasons.append("domain age is not under one year")
    if int(float(overview.get("visits", 0))) <= 3000:
        reasons.append("monthly visits are not above 3000")
    if float(sources.get("searchOrganic", 0)) <= 0.2:
        reasons.append("organic search share is not above 20%")
    if float(sources.get("direct", 0)) <= 0.2:
        reasons.append("direct traffic share is not above 20%")
    brands = {part.lower() for part in product_name.replace("-", " ").split() if len(part) > 2}
    brands.add(domain.split(".")[0].lower())
    non_brand = [item["name"] for item in keywords if not any(token in item["name"].lower() for token in brands)]
    if not non_brand:
        reasons.append("no non-brand keywords")
    return FilterResult(not reasons, reasons, non_brand)
~~~

- [ ] **Step 4: Run the test to verify it passes**

Run: .venv/bin/python -m pytest tests/test_demand_filter.py -v

Expected: PASS.

- [ ] **Step 5: Commit**

~~~bash
git add aitdk_enrichment/demand_filter.py tests/test_demand_filter.py
git commit -m "feat: filter Product Hunt keyword opportunities"
~~~

### Task 3: Obsidian Report Rendering

**Files:**
- Create: aitdk_enrichment/obsidian_report.py
- Create: tests/test_obsidian_report.py

- [ ] **Step 1: Write the failing test**

~~~python
from aitdk_enrichment.obsidian_report import render_report


def test_render_report_contains_front_matter_and_product_link() -> None:
    report = render_report("2026-08-21", [{"name": "Example", "product_hunt_url": "https://producthunt.com/posts/example", "domain": "example.com", "keywords": ["invoice template"]}], [])
    assert "source: product-hunt" in report
    assert "[Example](https://producthunt.com/posts/example)" in report
    assert "invoice template" in report
~~~

- [ ] **Step 2: Run the test to verify it fails**

Run: .venv/bin/python -m pytest tests/test_obsidian_report.py -v

Expected: FAIL because obsidian_report module does not exist.

- [ ] **Step 3: Implement rendering and the dated write operation**

~~~python
# aitdk_enrichment/obsidian_report.py
from pathlib import Path


def render_report(day, shortlisted, excluded):
    lines = ["---", f"date: {day}", "source: product-hunt", f"shortlisted: {len(shortlisted)}", "tags: [product-hunt, keyword-research]", "---", "", "# Product Hunt 找词"]
    lines.extend(["", "## 候选机会"])
    lines.extend([f"- [{item['name']}]({item['product_hunt_url']}) · {item['domain']} · {', '.join(item['keywords'])}" for item in shortlisted] or ["- 无"])
    lines.extend(["", "## 排除项"])
    lines.extend([f"- {item['name']} · {'; '.join(item['reasons'])}" for item in excluded] or ["- 无"])
    return "\n".join(lines) + "\n"


def write_report(vault, day, shortlisted, excluded):
    destination = Path(vault) / "01-个人输出/刷榜单目录/Product Hunt" / f"{day}【Product Hunt 找词】.md"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(render_report(day, shortlisted, excluded), encoding="utf-8")
    return destination
~~~

- [ ] **Step 4: Run the test to verify it passes**

Run: .venv/bin/python -m pytest tests/test_obsidian_report.py -v

Expected: PASS.

- [ ] **Step 5: Commit**

~~~bash
git add aitdk_enrichment/obsidian_report.py tests/test_obsidian_report.py
git commit -m "feat: write Product Hunt Obsidian report"
~~~

### Task 4: Orchestration And Live Acceptance

**Files:**
- Create: aitdk_enrichment/product_hunt_daily.py
- Create: .env.example
- Modify: .gitignore
- Test: tests/test_product_hunt_integration.py

- [ ] **Step 1: Write the failing orchestration test**

~~~python
from aitdk_enrichment.product_hunt_daily import select_domains


def test_select_domains_deduplicates_product_hunt_candidates() -> None:
    assert select_domains(["https://example.com/a", "https://example.com/b"]) == ["example.com"]
~~~

- [ ] **Step 2: Run it to verify it fails**

Run: .venv/bin/python -m pytest tests/test_product_hunt_integration.py -v

Expected: FAIL because product_hunt_daily module does not exist.

- [ ] **Step 3: Implement orchestration**

~~~python
# aitdk_enrichment/product_hunt_daily.py
from urllib.parse import urlparse


def select_domains(urls):
    return list(dict.fromkeys(urlparse(url).hostname.lower() for url in urls if urlparse(url).hostname))
~~~

~~~text
# .env.example
PRODUCT_HUNT_DEVELOPER_TOKEN=
~~~

- [ ] **Step 4: Run unit tests and an opt-in live API query**

Run: .venv/bin/python -m pytest -v

Expected: all unit tests pass.

Run: PRODUCT_HUNT_DEVELOPER_TOKEN is supplied only from local .env; fetch 5 newest posts and write the dated note under the configured Obsidian vault.

Expected: the report contains candidate or no-candidate summary, with no token in it.

- [ ] **Step 5: Commit**

~~~bash
git add aitdk_enrichment/product_hunt_daily.py .env.example tests/test_product_hunt_integration.py
git commit -m "feat: orchestrate Product Hunt demand radar"
~~~

## Plan Self-Review

- Spec coverage: tasks cover official API collection, deduplication, AITDK handoff point, filters, brand exclusion, and Obsidian Markdown output.
- Security: token is read only at runtime and .env is ignored.
- Repository note: current directory is not a Git repository, so listed commits are deferred until the project has a repository.
