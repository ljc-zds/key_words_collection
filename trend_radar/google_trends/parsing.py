"""Parse sanitized Google Trends JSON payloads."""

from __future__ import annotations

import re


def parse_related_queries(payload: dict, minimum_growth: int = 500) -> list[dict]:
    rows = payload.get("default", {}).get("rankedList", [])
    results: list[dict] = []
    for row in rows:
        for item in row.get("rankedKeyword", []):
            query, value = str(item.get("query", "")).strip(), str(item.get("value", "")).strip()
            if not query:
                continue
            if value.lower() == "breakout":
                results.append({"query": query, "type": "Breakout", "growth_percent": None})
                continue
            match = re.search(r"([\d,]+)", value)
            growth = int(match.group(1).replace(",", "")) if match else None
            if growth is not None and growth >= minimum_growth:
                results.append({"query": query, "type": "rising", "growth_percent": growth})
    return results


def parse_timeline_values(payload: dict) -> tuple[list[str], list[list[int]]]:
    timeline = payload.get("default", {}).get("timelineData", [])
    times, series = [], []
    for point in timeline:
        values = point.get("value", [])
        if not isinstance(values, list) or not values:
            continue
        times.append(str(point.get("time", "")))
        series.append([int(value) if str(value).isdigit() else 0 for value in values])
    return times, series
