"""Compare a candidate trend against the gpts baseline."""

from __future__ import annotations


def is_new_word(candidate: list[int], gpts: list[int], *, baseline_points: int) -> dict:
    if len(candidate) != len(gpts) or len(candidate) <= baseline_points:
        raise ValueError("candidate and gpts series must have equal baseline and recent windows")
    baseline_candidate = candidate[:baseline_points]
    baseline_gpts = gpts[:baseline_points]
    recent_candidate = candidate[baseline_points:]
    recent_gpts = gpts[baseline_points:]
    crossings = [baseline_points + index for index, (value, base) in enumerate(zip(recent_candidate, recent_gpts)) if value > base]
    return {
        "is_new_word": sum(baseline_candidate) / baseline_points < sum(baseline_gpts) / baseline_points and bool(crossings),
        "candidate_baseline_average": sum(baseline_candidate) / baseline_points,
        "gpts_baseline_average": sum(baseline_gpts) / baseline_points,
        "first_crossing_index": crossings[0] if crossings else None,
        "crossing_count": len(crossings),
        "maximum_difference": max((value - base for value, base in zip(recent_candidate, recent_gpts)), default=0),
        "still_above_gpts": recent_candidate[-1] > recent_gpts[-1],
    }
