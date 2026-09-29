"""Bounty-derived traffic and keyword opportunity rules."""

from dataclasses import dataclass


@dataclass(frozen=True)
class FilterResult:
    passed: bool
    reasons: list[str]
    non_brand_keywords: list[str]


def evaluate_candidate(
    domain: str,
    product_name: str,
    traffic: dict,
    domain_age_days: int | None,
    keywords: list[dict],
) -> FilterResult:
    overview = traffic.get("overview", {})
    sources = traffic.get("trafficSources", {})
    reasons: list[str] = []
    if domain_age_days is None or domain_age_days > 365:
        reasons.append("domain age exceeds 365 days")
    visits = int(float(overview.get("visits", 0)))
    search_share = float(sources.get("searchOrganic", 0))
    if visits * search_share < 3_000:
        reasons.append("monthly search visits are below 3000")
    if search_share < 0.2:
        reasons.append("organic search share is below 20%")
    if float(sources.get("direct", 0)) < 0.2:
        reasons.append("direct traffic share is below 20%")

    brand_terms = {part.lower() for part in product_name.replace("-", " ").split() if len(part) > 2}
    brand_terms.add(domain.split(".")[0].lower())
    non_brand = [
        item["name"]
        for item in keywords
        if isinstance(item.get("name"), str)
        and not any(term in item["name"].lower() for term in brand_terms)
    ]
    return FilterResult(not reasons, reasons, non_brand)
