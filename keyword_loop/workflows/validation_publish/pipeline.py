"""Deep keyword validation and Feishu publication orchestration."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date

from ...core.publishing.feishu import publish_wiki
from ...core.screening.screening import keyword_quality_gate, volume_kd_gate
from ...core.clients.webcafe import explain_payload, retrieved_at


@dataclass(frozen=True)
class ValidationTotals:
    queued: int
    accepted: int
    published: bool

    def to_dict(self) -> dict[str, int | bool]:
        return asdict(self)


def _number(value: object) -> int | None:
    try:
        return int(float(str(value).replace(",", "")))
    except (TypeError, ValueError):
        return None


def queue_candidates(store, run_date: date, limit: int) -> None:
    store.start_daily_run(run_date, target=limit)
    for candidate in store.daily_candidates(minimum_volume=5_000, maximum_kd=60, limit=limit * 3):
        source = candidate.source_roots[0] if candidate.source_roots else "root"
        store.queue_daily_keyword(run_date, candidate.keyword, candidate.market, source)


def validate_semrush_queue(store, run_date: date, semrush) -> list[tuple[str, str, dict]]:
    """Apply the exact-keyword Semrush gate to unresolved daily queue entries."""
    accepted: list[tuple[str, str, dict]] = []
    for queued_date, keyword, market, _source in store.unresolved_semrush_keywords():
        if queued_date != run_date.isoformat():
            continue
        quality = keyword_quality_gate(keyword)
        if quality.decision == "淘汰":
            store.record_validation(keyword, market, "keyword_quality", {"decision": quality.decision, "reason": quality.reason})
            store.record_daily_gate(run_date, keyword, market, "semrush", quality.decision, quality.reason)
            continue
        try:
            response = semrush.query(keyword)
            exact = next((row for row in response.get("keywords", []) if str(row.get("keyword", "")).lower() == keyword.lower()), None)
            baseline = store.connection.execute(
                "SELECT volume, kd FROM keywords WHERE keyword=? AND market=?", (keyword, market)
            ).fetchone()
            if exact is None and baseline:
                gate = volume_kd_gate(baseline[0], baseline[1])
                payload = {"exact_keyword_found": False}
            elif exact is not None:
                gate = volume_kd_gate(_number(exact.get("volume")), _number(exact.get("difficulty", exact.get("kd"))))
                payload = {"exact_keyword_found": True, **exact}
            else:
                gate = volume_kd_gate(None, None)
                payload = {"exact_keyword_found": False}
            payload.setdefault("kd", payload.get("difficulty"))
            payload.update(gate_decision=gate.decision, gate_reason=gate.reason)
            store.record_validation(keyword, market, "semrush", payload)
            store.record_daily_gate(run_date, keyword, market, "semrush", gate.decision, gate.reason)
            if gate.decision == "保留":
                accepted.append((keyword, market, payload))
        except Exception as error:
            store.record_validation(keyword, market, "semrush", {"error": type(error).__name__})
    return accepted


def screen_with_ai(store, items: list[tuple[str, str, dict]], ai, *, stage: str, run_date: date | None = None) -> None:
    """Persist a batch AI assessment without blocking other validation stages."""
    payload = [{"keyword": keyword, "semrush": semrush} for keyword, _market, semrush in items]
    if not payload:
        return
    try:
        results = ai.assess_batch(payload, stage=stage)
    except Exception:
        return
    for item, result in zip(items, results):
        keyword, market, _ = item
        key = "ai_initial" if stage == "initial" else "ai_screen"
        store.record_validation(keyword, market, key, result)
        if stage == "final":
            store.record_validation(keyword, market, "intent_gate", result)
            if run_date is None:
                raise ValueError("run_date is required for final AI screening")
            store.record_daily_gate(run_date, keyword, market, "intent", result["decision"], result["reason"])


def enrich_serp_and_kd(store, items: list[tuple[str, str, dict]], serper, webcafe) -> list[tuple[str, str, dict]]:
    """Populate Serper and Web.Cafe data for Semrush-approved candidates."""
    ready: list[tuple[str, str, dict]] = []
    for keyword, market, semrush in items:
        try:
            if not store.validation(keyword, market, "serper"):
                store.record_validation(keyword, market, "serper", serper.analyze(keyword))
            exists = store.connection.execute(
                "SELECT 1 FROM kd_enrichment WHERE keyword=? AND market=?", (keyword, market)
            ).fetchone()
            if not exists:
                payload = webcafe.estimate(keyword)
                store.record_enrichment(keyword, market, payload, explain_payload(keyword, payload), retrieved_at())
            ready.append((keyword, market, semrush))
        except Exception:
            continue
    return ready


def publish_accepted(store, run_date: date, results_feishu_url: str) -> bool:
    candidates = store.daily_accepted_candidates(run_date)
    if not candidates:
        return False
    validations = {}
    for candidate in candidates:
        stages = {}
        for stage in ("semrush", "serper", "ai_initial", "ai_screen"):
            value = store.validation(candidate.keyword, candidate.market, stage)
            if value is not None:
                stages[stage] = value
        validations[candidate.keyword] = stages
    enrichments, scores, payloads = {}, {}, {}
    for keyword, market, score, payload_json, explanation_json in store.connection.execute(
        "SELECT keyword, market, score, payload_json, explanation_json FROM kd_enrichment"
    ):
        enrichments[keyword] = tuple(json.loads(explanation_json))
        scores[keyword] = score
        payloads[keyword] = json.loads(payload_json)
    publish_wiki(
        results_feishu_url,
        candidates,
        enrichments=enrichments,
        gofei_scores=scores,
        gofei_payloads=payloads,
        validations=validations,
    )
    return True


def run_validation_publish(run_date: date, store, semrush, ai, serper, webcafe, results_feishu_url: str, limit: int) -> ValidationTotals:
    """Run all downstream stages and publish only candidates with complete gates."""
    queue_candidates(store, run_date, limit)
    semrush_accepted = validate_semrush_queue(store, run_date, semrush)
    screen_with_ai(store, semrush_accepted, ai, stage="initial")
    ready = enrich_serp_and_kd(store, semrush_accepted, serper, webcafe)
    screen_with_ai(store, ready, ai, stage="final", run_date=run_date)
    published = publish_accepted(store, run_date, results_feishu_url)
    status = store.daily_run_status(run_date)
    return ValidationTotals(queued=status.queued, accepted=len(store.daily_accepted_candidates(run_date)), published=published)
