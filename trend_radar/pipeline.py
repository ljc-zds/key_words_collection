"""Feed Feishu roots through Google Trends and identify new words over gpts."""

from __future__ import annotations

from collections.abc import Callable
import inspect

from .google_trends.comparison import is_new_word
from .google_trends.fallback import CollectionStopped
from .google_trends.errors import MissingTrendsData


TIMEFRAME_FALLBACKS = ("today 1-m", "now 7-d", "now 3-d", "now 2-d", "now 1-d")


def compare_with_fallbacks(client, candidate: str, baseline: str):
    """Return the first usable aligned series, retrying shorter periods."""
    failures = []
    for timeframe in TIMEFRAME_FALLBACKS:
        try:
            times, candidate_series, baseline_series = client.compare(candidate, baseline, timeframe)
        except (AttributeError, TypeError):
            try:
                times, candidate_series, baseline_series = client.compare(candidate, baseline)
            except (AttributeError, RuntimeError, TypeError) as error:
                failures.append(str(error))
                continue
        except RuntimeError as error:
            failures.append(str(error))
            continue
        if len(times) == len(candidate_series) == len(baseline_series) and len(times) >= 2:
            return timeframe, times, candidate_series, baseline_series
        failures.append(f"{timeframe}: insufficient aligned points")
    raise RuntimeError("; ".join(failures) or "no usable trend series")


def checkpoint(callback, records: list[dict], completed: set[str], failed: dict[str, dict]) -> None:
    """Support existing two-argument checkpoint callbacks during the migration."""
    if len(inspect.signature(callback).parameters) == 2:
        callback(records, completed)
        return
    callback(records, completed, failed)


def scan_roots(roots: list[str], client, **options) -> list[dict]:
    """Checkpoint and stop the entire run when both data sources fail."""
    previous = list(options.pop('existing_records', None) or [])
    records = list(previous)
    for key, default in [('completed_parents', set()), ('failed_parents', {}), ('parent_rising', {})]:
        if options.get(key) is None:
            options[key] = default
    active = {}
    try:
        return _scan_roots(roots, client, existing_records=records, _active_parent=active, **options)
    except CollectionStopped as error:
        # The scanner removes old unavailable rows before retrying a batch.
        # If that batch stops the run, keep their prior evidence in the checkpoint.
        retained = {r.get('candidate', '').lower() for r in records}
        records.extend(r for r in previous if r.get('candidate', '').lower() not in retained)
        if active:
            options['failed_parents'][active['parent_keyword'].lower()] = {**active, 'error': str(error)}
        callback = options.get('on_checkpoint')
        if callback:
            checkpoint(callback, records, options['completed_parents'], options['failed_parents'])
        raise


def _scan_roots(
    roots: list[str],
    client,
    *,
    baseline: str = "gpts",
    max_depth: int | None = None,
    existing_records: list[dict] | None = None,
    completed_parents: set[str] | None = None,
    failed_parents: dict[str, dict] | None = None,
    parent_rising: dict[str, dict] | None = None,
    on_checkpoint: Callable[[list[dict], set[str], dict[str, dict]], None] | None = None,
    _active_parent: dict | None = None,
) -> list[dict]:
    """Recursively expand qualified Rising queries and compare each one with gpts."""
    if max_depth is not None and max_depth < 1:
        raise ValueError("max_depth must be at least 1")
    # Keep unavailable comparisons in the checkpoint. A future Rising response
    # may no longer contain that word, but the historical failed result must not
    # disappear merely because the job was resumed.
    records = existing_records if existing_records is not None else []
    completed = completed_parents if completed_parents is not None else set()
    failed = failed_parents if failed_parents is not None else {}
    rising = parent_rising if parent_rising is not None else {}
    # A completed parent may contain comparisons that failed only because its
    # gpts series had not arrived. Revisit that parent while retaining every
    # successful candidate in ``seen`` below.
    completed.difference_update(
        str(record["parent_keyword"]).lower()
        for record in records
        if record.get("comparison", {}).get("status") == "unavailable" and record.get("parent_keyword")
    )
    seen = {
        str(record.get("candidate", "")).lower()
        for record in records
        if record.get("comparison", {}).get("status") != "unavailable"
    }
    pending = [
        (str(parent["parent_keyword"]), str(parent["root"]), int(parent["depth"]))
        for parent in failed.values()
        if parent.get("parent_keyword") and parent.get("root")
    ]
    pending.extend((root, root, 0) for root in roots)
    pending.extend(
        (str(record["candidate"]), str(record["root"]), int(record["depth"]))
        for record in records
        if record.get("candidate") and record.get("root") and (max_depth is None or int(record.get("depth", max_depth)) < max_depth)
    )
    # A LIFO stack keeps one branch hot: root -> first Rising child -> its
    # first Rising child, before returning to siblings or the next root.
    stack = list(reversed(pending))
    deferred = set()
    while stack:
        parent_keyword, root, parent_depth = stack.pop()
        parent_key = parent_keyword.lower()
        if (max_depth is not None and parent_depth >= max_depth) or parent_key in completed or parent_key in deferred:
            continue
        if _active_parent is not None:
            _active_parent.update(parent_keyword=parent_keyword, root=root, depth=parent_depth)
        candidates: list[tuple[str, dict]] = []
        try:
            saved_rising = rising.get(parent_key, {}).get('qualified_rising_queries')
            related_queries = saved_rising if isinstance(saved_rising, list) else client.related_rising(parent_keyword)
        except (RuntimeError, MissingTrendsData) as error:
            if isinstance(error, MissingTrendsData):
                deferred.add(parent_key)
            failed[parent_key] = {
                "parent_keyword": parent_keyword,
                "root": root,
                "depth": parent_depth,
                "error": str(error),
            }
            if on_checkpoint:
                checkpoint(on_checkpoint, records, completed, failed)
            continue
        failed.pop(parent_key, None)
        rising[parent_key] = {
            "parent_keyword": parent_keyword,
            "root": root,
            "depth": parent_depth,
            "qualified_rising_count": len(related_queries),
            "qualified_rising_queries": related_queries,
        }
        for related in related_queries:
            candidate = related["query"].lower()
            if candidate in seen or candidate == baseline:
                continue
            records[:] = [
                record for record in records
                if not (
                    str(record.get("candidate", "")).lower() == candidate
                    and record.get("comparison", {}).get("status") == "unavailable"
                )
            ]
            seen.add(candidate)
            candidates.append((candidate, related))
        parent_has_unavailable = False
        for start in range(0, len(candidates), 4):
            batch = candidates[start:start + 4]
            missing = None
            try:
                if hasattr(client, "compare_batch"):
                    comparisons = client.compare_batch([candidate for candidate, _ in batch], baseline)
                else:
                    comparisons = {candidate: client.compare(candidate, baseline) for candidate, _ in batch}
            except MissingTrendsData as error:
                missing = error
                comparisons = {}
            except RuntimeError:
                comparisons = {}
                for candidate, _ in batch:
                    try:
                        comparisons[candidate] = client.compare(candidate, baseline)
                    except (RuntimeError, MissingTrendsData) as error:
                        comparisons[candidate] = error
            for candidate, related in batch:
                candidate_missing = missing or (comparisons.get(candidate) if isinstance(comparisons.get(candidate), MissingTrendsData) else None)
                if candidate_missing is not None:
                    parent_has_unavailable = True
                    deferred.update((parent_key, candidate))
                    failed[parent_key] = {'parent_keyword': parent_keyword, 'root': root,
                                          'depth': parent_depth, 'error': str(candidate_missing)}
                    records.append({'root': root, 'parent_keyword': parent_keyword,
                                    'depth': parent_depth + 1, 'candidate': candidate, 'related': related,
                                    'comparison': {'is_new_word': False, 'status': 'unavailable'},
                                    'comparison_error': str(candidate_missing), 'first_crossing_time': None})
                    continue
                try:
                    times, candidate_series, baseline_series = comparisons[candidate]
                except (KeyError, RuntimeError, TypeError) as error:
                    try:
                        timeframe, times, candidate_series, baseline_series = compare_with_fallbacks(client, candidate, baseline)
                    except (RuntimeError, MissingTrendsData) as fallback_error:
                        parent_has_unavailable = True
                        records.append({"root": root, "parent_keyword": parent_keyword, "depth": parent_depth + 1, "candidate": candidate, "related": related, "comparison": {"is_new_word": False, "status": "unavailable"}, "comparison_error": f"{error}; {fallback_error}", "first_crossing_time": None})
                        continue
                else:
                    timeframe = "today 1-m"
                if len(candidate_series) < 30:
                    try:
                        timeframe, times, candidate_series, baseline_series = compare_with_fallbacks(client, candidate, baseline)
                    except (RuntimeError, MissingTrendsData) as error:
                        parent_has_unavailable = True
                        records.append({"root": root, "parent_keyword": parent_keyword, "depth": parent_depth + 1, "candidate": candidate, "related": related, "comparison": {"is_new_word": False, "status": "unavailable"}, "comparison_error": str(error), "first_crossing_time": None})
                        continue
                baseline_points = max(1, int(len(candidate_series) * 0.7))
                decision = is_new_word(candidate_series, baseline_series, baseline_points=baseline_points)
                records.append({
                    "root": root,
                    "parent_keyword": parent_keyword,
                    "depth": parent_depth + 1,
                    "candidate": candidate,
                    "related": related,
                    "comparison": decision,
                    "comparison_timeframe": timeframe,
                    "series_points": len(times),
                    "first_crossing_time": times[decision["first_crossing_index"]] if decision["first_crossing_index"] is not None else None,
                })
            # Persist each completed comparison batch. The parent remains out
            # of ``completed`` until all of its batches have finished.
            if on_checkpoint:
                checkpoint(on_checkpoint, records, completed, failed)
        if not parent_has_unavailable:
            completed.add(parent_key)
        else:
            failed.setdefault(parent_key, {'parent_keyword': parent_keyword, 'root': root,
                                          'depth': parent_depth, 'error': 'comparison data pending retry'})
        if on_checkpoint:
            checkpoint(on_checkpoint, records, completed, failed)
        stack.extend(reversed([
            (candidate, root, parent_depth + 1)
            for candidate, _ in candidates
        ]))
    return records
