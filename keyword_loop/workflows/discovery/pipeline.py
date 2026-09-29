"""Similarweb and Semrush keyword-discovery orchestration."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from ...core.publishing.feishu import load_roots_from_wiki
from ...core.sources.rankings import fetch_toolify_ranking
from ...core.sources.revenue_sources import fetch_revenue_links
from ...core.screening.screening import intent_gate, keyword_quality_gate, semrush_missing_gate, volume_kd_gate
from ...core.clients.semrush_browser import normalize_keyword_row, SemrushReportLimitError
from ...core.clients.discovery_filters import metric_filter_reason
from ...core.screening.screening import GateResult


@dataclass
class DiscoveryTotals:
    stored: int = 0
    similarweb_passed: int = 0
    semrush_checked: int = 0
    semrush_passed: int = 0
    semrush_rejected: int = 0

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


def remaining_terms(store, source: str, terms: list[str]) -> list[str]:
    offset = int(store.get_state(f"discovery_only:{source}:offset", "0") or "0")
    return terms[offset:]


def collect_and_gate_source(store, collector, source: str, terms: list[str]) -> tuple[int, int]:
    """Persist Similarweb observations and count records passing its hard gates."""
    stored = passed = 0
    for term in terms:
        try:
            observations = collector.collect(term)
        except Exception as error:
            store.record_failure(f"discovery:{source}:{term}", type(error).__name__)
            continue
        for observation in observations:
            store.record(observation)
            stored += 1
            if keyword_quality_gate(observation.keyword).decision == "保留" and volume_kd_gate(
                observation.average_volume, observation.kd
            ).decision == "保留":
                passed += 1
    return stored, passed


def validate_semrush(store, provider, keyword: str, market: str):
    """Validate the queried term and retain qualifying related US candidates."""
    response = provider.query(keyword)
    related_count = 0
    for row in response.get("keywords", []):
        name = str(row.get("keyword", "")).strip().lower()
        if not name or name == keyword.strip().lower():
            continue
        related = normalize_keyword_row(row)
        gate = volume_kd_gate(related.get("volume"), related.get("kd"))
        reason = metric_filter_reason(related.get("kd"), related.get("cpc"), kd_min=0, kd_max=60, cpc_min=0.01)
        if gate.decision != "保留" or reason:
            continue
        related.update(keyword=name, gate_decision="保留", gate_reason=gate.reason,
                       validation_status="Semrush通过，待Similarweb验证")
        store.record_semrush_related(name, getattr(provider, "database", "us"), keyword.strip().lower(), related)
        related_count += 1
    exact = next(
        (row for row in response.get("keywords", []) if str(row.get("keyword", "")).lower() == keyword.lower()),
        None,
    )
    payload = {"exact_keyword_found": exact is not None, **(normalize_keyword_row(exact) if exact else {})}
    gate = volume_kd_gate(payload.get("volume"), payload.get("kd")) if exact else GateResult("淘汰", "Semrush 未返回精确关键词，跳过；不取消筛选补查")
    if exact and getattr(provider, "discovery_filters", False):
        reason = metric_filter_reason(payload.get("kd"), payload.get("cpc"), kd_min=0, kd_max=60, cpc_min=0.01)
        if reason:
            gate = GateResult("淘汰", reason)
    if getattr(provider, "discovery_filters", False):
        payload["query_filter_version"] = "kd-cpc-v1"
    payload.update(gate_decision=gate.decision, gate_reason=gate.reason)
    payload["related_candidates_retained"] = related_count
    store.record_validation(keyword, market, "semrush", payload)
    return gate


def validate_semrush_intent(store, keyword: str, market: str, semrush: dict):
    """Apply the existing intent hard gate without another provider request."""
    gate = intent_gate(keyword, semrush)
    store.record_validation(keyword, market, "intent_gate", {"decision": gate.decision, "reason": gate.reason})
    return gate


def semrush_target_reached(totals: DiscoveryTotals | dict[str, int], approved_target: int) -> bool:
    values = totals.to_dict() if isinstance(totals, DiscoveryTotals) else totals
    return values["semrush_passed"] >= approved_target


def initial_discovery_totals(approved_count: int, *, new_only: bool) -> DiscoveryTotals:
    """Start a discovery run from zero when its target is only new approvals."""
    return DiscoveryTotals(semrush_passed=0 if new_only else approved_count)


def source_terms(args: Any) -> dict[str, list[str]]:
    selected = {part.strip() for part in args.sources.split(",") if part.strip()}
    terms: dict[str, list[str]] = {}
    if "stripe" in selected:
        rows = fetch_revenue_links(args.stripe_url, "stripe", cdp_url=args.cdp_url)
        terms["stripe"] = [row.title or row.domain for row in rows][:args.source_limit or None]
    if "toolify" in selected:
        rows = fetch_toolify_ranking(args.toolify_url, cdp_url=args.cdp_url)
        terms["toolify"] = [row.name for row in rows][:args.source_limit or None]
    if "root" in selected:
        if not args.roots_feishu_url:
            raise ValueError("--roots-feishu-url is required when sources include root")
        terms["root"] = load_roots_from_wiki(args.roots_feishu_url)[:args.source_limit or None]
    unknown = selected - {"stripe", "toolify", "root"}
    if unknown:
        raise ValueError(f"unknown sources: {', '.join(sorted(unknown))}")
    return terms


def run_discovery(args: Any, store, similarweb, semrush) -> DiscoveryTotals:
    """Discover, gate, and checkpoint keywords without publication or AI calls."""
    approved_keywords = store.approved_discovery_keywords()
    source_quota = args.source_approved_limit
    totals = initial_discovery_totals(len(approved_keywords), new_only=getattr(args, "new_only", False))
    source_terms_map = source_terms(args)
    for source, terms in source_terms_map.items():
        if source_quota is not None and store.source_accepted_count(source) >= source_quota:
            continue
        if source_quota is None and semrush_target_reached(totals, args.semrush_limit):
            break
        for term in remaining_terms(store, source, terms):
            term_complete = True
            try:
                observations = similarweb.collect(term)
            except Exception as error:
                store.record_failure(f"discovery:{source}:{term}", type(error).__name__)
                continue
            for observation in observations:
                store.record(observation)
                totals.stored += 1
                if keyword_quality_gate(observation.keyword).decision != "保留":
                    continue
                if volume_kd_gate(observation.average_volume, observation.kd).decision != "保留":
                    continue
                totals.similarweb_passed += 1
                candidate_key = (observation.keyword, observation.market)
                if candidate_key in approved_keywords:
                    previous = store.validation(observation.keyword, observation.market, "semrush") or {}
                    if getattr(semrush, "discovery_filters", False) and previous.get("query_filter_version") != "kd-cpc-v1":
                        continue  # Historical approvals are not new approvals under this policy.
                    store.record_source_acceptance(source, observation.keyword, observation.market)
                    if source_quota is not None and store.source_accepted_count(source) >= source_quota:
                        term_complete = False
                        break
                    continue
                if source_quota is None and semrush_target_reached(totals, args.semrush_limit):
                    term_complete = False
                    break
                try:
                    gate = validate_semrush(store, semrush, observation.keyword, observation.market)
                except SemrushReportLimitError as error:
                    store.record_failure(f"semrush:{observation.keyword}", str(error))
                    raise  # Keep this source checkpoint; never classify quota failures as rejected words.
                except Exception as error:
                    store.record_failure(f"semrush:{observation.keyword}", type(error).__name__)
                    continue
                totals.semrush_checked += 1
                if gate.decision == "保留":
                    semrush_payload = store.validation(observation.keyword, observation.market, "semrush") or {}
                    intent_result = validate_semrush_intent(store, observation.keyword, observation.market, semrush_payload)
                    if intent_result.decision == "保留":
                        totals.semrush_passed += 1
                        approved_keywords.add(candidate_key)
                        store.record_source_acceptance(source, observation.keyword, observation.market)
                        if source_quota is not None and store.source_accepted_count(source) >= source_quota:
                            term_complete = False
                            break
                    else:
                        totals.semrush_rejected += 1
                else:
                    totals.semrush_rejected += 1
            if term_complete:
                current = int(store.get_state(f"discovery_only:{source}:offset", "0") or "0")
                store.set_state(f"discovery_only:{source}:offset", str(current + 1))
            if source_quota is None and semrush_target_reached(totals, args.semrush_limit):
                break
    return totals
