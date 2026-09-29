"""Independent provider discovery with durable source cursors and response batches."""
import json
import subprocess
from dataclasses import asdict

from ...core.clients.discovery_filters import metric_filter_reason
from ...core.clients.semrush_browser import normalize_keyword_row
from ...core.clients.similarweb import BrowserProxyError as SimilarwebError
from ...core.screening.screening import volume_kd_gate


def initialize(store):
    store.connection.executescript("""
        CREATE TABLE IF NOT EXISTS independent_candidates (
            keyword TEXT NOT NULL, provider TEXT NOT NULL, market TEXT NOT NULL,
            payload_json TEXT NOT NULL, accepted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(keyword,provider,market)
        );
        CREATE TABLE IF NOT EXISTS independent_provenance (
            keyword TEXT NOT NULL, provider TEXT NOT NULL, market TEXT NOT NULL,
            source TEXT NOT NULL, seed TEXT NOT NULL,
            PRIMARY KEY(keyword,provider,market,source,seed)
        );
    """)
    for provider in ("similarweb", "semrush"):
        for source in ("stripe", "toolify", "root"):
            key = f"independent:{provider}:{source}:offset"
            if not store.get_state(key):
                offset = store.get_state(f"discovery_only:{source}:offset", "0") if provider == "similarweb" else "0"
                store.set_state(key, offset)
    # Copy qualified legacy Semrush results without inventing Stripe/Toolify attribution.
    # Existing records are preserved; imports do not consume this run's new-word target.
    if store.get_state("independent:legacy_related_imported") != "1":
        with store.connection:
            for keyword, market, seed, raw in store.connection.execute(
                "SELECT keyword,database_name,parent_keyword,payload_json FROM semrush_related_candidates"
            ).fetchall():
                payload = json.loads(raw)
                if volume_kd_gate(payload.get("volume"), payload.get("kd")).decision != "保留":
                    continue
                if metric_filter_reason(payload.get("kd"), payload.get("cpc"), kd_min=0, kd_max=60, cpc_min=.01):
                    continue
                payload["validation_status"] = "semrush独立筛选通过"
                store.connection.execute(
                    "INSERT OR IGNORE INTO independent_candidates(keyword,provider,market,payload_json) VALUES (?,'semrush',?,?)",
                    (keyword, market, json.dumps(payload, ensure_ascii=False)),
                )
                store.connection.execute("INSERT OR IGNORE INTO independent_provenance VALUES (?,'semrush',?,'legacy_related',?)",
                                         (keyword, market, seed))
            _put(store.connection, "independent:legacy_related_imported", "1")


def _put(connection, name, value):
    connection.execute("INSERT INTO pipeline_state(name,value) VALUES (?,?) "
                       "ON CONFLICT(name) DO UPDATE SET value=excluded.value", (name, value))


def _rows(provider, client, seed):
    if provider == "similarweb":
        return [dict(asdict(row), volume=row.average_volume) for row in client.collect(seed)]
    response = client.query(seed)
    return [dict(normalize_keyword_row(row), market=client.database) for row in response["keywords"]]


class RepeatedSimilarwebTimeout(RuntimeError):
    pass


def _fetch_rows(provider, client, seed):
    for attempt in range(2):
        try:
            return _rows(provider, client, seed)
        except Exception as error:
            timeout = isinstance(error, (TimeoutError, subprocess.TimeoutExpired)) or (
                isinstance(error, SimilarwebError) and (
                    "timed out" in str(error).lower() or "primary JSON was not captured" in str(error)
                )
            )
            if provider != "similarweb" or not timeout:
                raise
            if attempt == 1:
                raise RepeatedSimilarwebTimeout(f"2 attempts timed out; seed skipped: {str(error)[:800]}") from error
            print(f"Similarweb {seed}: timeout, retrying once", flush=True)


def run_independent(args, store, similarweb, semrush, source_map):
    """A provider's qualifying keywords never require the other provider's approval.

    Per-run targets count new unique provider/market keywords. Responses are cached
    before consuming rows, so a partial batch needs no new browser request on resume.
    """
    if args.provider_limit < 0:
        raise ValueError("provider_limit must be nonnegative")
    limit = args.provider_limit or float("inf")
    providers = list(dict.fromkeys(args.providers.split(",")))
    if not providers or set(providers) - {"similarweb", "semrush"}:
        raise ValueError("providers must be similarweb and/or semrush")
    initialize(store)
    totals = {}
    for provider in providers:
        client = similarweb if provider == "similarweb" else semrush
        stats = totals[provider] = {"added": 0, "checked": 0, "status": "exhausted"}
        for source, incoming in source_map.items():
            prefix = f"independent:{provider}:{source}"
            snapshot = store.get_state(prefix + ":seeds")
            # Preserve the old positional cursor, including duplicate seed entries.
            seeds = json.loads(snapshot) if snapshot else list(incoming)
            known = set(seeds)
            for seed in incoming:
                if seed not in known:
                    seeds.append(seed)
                    known.add(seed)
            store.set_state(prefix + ":seeds", json.dumps(seeds, ensure_ascii=False))
            offset_text = store.get_state(prefix + ":offset")
            if not offset_text:
                # Only Similarweb traversed sources in the former cross-validation workflow.
                offset_text = store.get_state(f"discovery_only:{source}:offset", "0") if provider == "similarweb" else "0"
                store.set_state(prefix + ":offset", offset_text)
            offset = int(offset_text)
            if offset > len(seeds):
                stats.update(status="blocked", error=f"{source}: source list shorter than saved checkpoint")
                break
            while offset < len(seeds) and stats["added"] < limit:
                seed = seeds[offset]
                pending = store.get_state(prefix + ":batch")
                if pending:
                    batch = json.loads(pending)
                    if batch["seed"] != seed:
                        raise ValueError(f"{prefix}: pending seed does not match checkpoint")
                else:
                    try:
                        batch = {"seed": seed, "rows": _fetch_rows(provider, client, seed), "next": 0}
                    except RepeatedSimilarwebTimeout as error:
                        store.record_failure(f"independent:{provider}:{source}:{seed}", str(error))
                        offset += 1
                        store.set_state(prefix + ":offset", str(offset))
                        print(f"Similarweb {seed}: retry timed out; continuing with next seed", flush=True)
                        continue
                    except Exception as error:
                        store.record_failure(f"independent:{provider}:{source}:{seed}", str(error)[:1000])
                        if getattr(args, "continue_on_error", False):
                            offset += 1
                            store.set_state(prefix + ":offset", str(offset))
                            print(f"{provider} {source} seed={seed!r}: failed, continuing", flush=True)
                            continue
                        # Stop this provider, not the other one. No cursor movement on failure.
                        stats.update(status="blocked", error=str(error)[:1000])
                        break
                    store.set_state(prefix + ":batch", json.dumps(batch, ensure_ascii=False))
                while batch["next"] < len(batch["rows"]) and stats["added"] < limit:
                    row = batch["rows"][batch["next"]]
                    keyword = " ".join(str(row.get("keyword", "")).split()).lower()
                    market = row["market"]
                    gate = volume_kd_gate(row.get("volume"), row.get("kd"))
                    reason = metric_filter_reason(row.get("kd"), row.get("cpc"),
                                                  kd_min=1 if provider == "similarweb" else 0,
                                                  kd_max=60, cpc_min=.01)
                    added = 0
                    with store.connection:
                        if keyword and gate.decision == "保留" and reason is None:
                            payload = dict(row, keyword=keyword, gate_decision="保留", gate_reason=gate.reason,
                                           validation_status=f"{provider}独立筛选通过", query_filter_version="kd-cpc-v1")
                            added = store.connection.execute(
                                "INSERT OR IGNORE INTO independent_candidates(keyword,provider,market,payload_json) VALUES (?,?,?,?)",
                                (keyword, provider, market, json.dumps(payload, ensure_ascii=False)),
                            ).rowcount
                            store.connection.execute(
                                "UPDATE independent_candidates SET payload_json=? WHERE keyword=? AND provider=? AND market=?",
                                (json.dumps(payload, ensure_ascii=False), keyword, provider, market),
                            )
                            store.connection.execute("INSERT OR IGNORE INTO independent_provenance VALUES (?,?,?,?,?)",
                                                     (keyword, provider, market, source, seed))
                        batch["next"] += 1
                        _put(store.connection, prefix + ":batch", json.dumps(batch, ensure_ascii=False))
                    stats["checked"] += 1
                    stats["added"] += added
                if batch["next"] == len(batch["rows"]):
                    offset += 1
                    with store.connection:
                        _put(store.connection, prefix + ":offset", str(offset))
                        store.connection.execute("DELETE FROM pipeline_state WHERE name=?", (prefix + ":batch",))
                print(f"{provider} {source} seed={seed!r} offset={offset}/{len(seeds)} added={stats['added']} checked={stats['checked']}", flush=True)
                if stats["added"] >= limit:
                    stats["status"] = "target_reached"
                    break
            if stats["status"] in {"blocked", "target_reached"}:
                break
    return totals
