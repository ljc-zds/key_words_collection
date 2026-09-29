import re

from .models import KeywordObservation


def parse_metric(value: str) -> int | None:
    cleaned = value.strip().replace(",", "").upper()
    if cleaned in {"", "-", "N/A"}:
        return None
    match = re.fullmatch(r"(\d+(?:\.\d+)?)([KM]?)", cleaned)
    if match is None:
        return None
    multiplier = {"": 1, "K": 1_000, "M": 1_000_000}[match.group(2)]
    return int(float(match.group(1)) * multiplier)


def parse_keyword_row(
    cells: list[str], *, root: str, result_type: str, market: str, retrieved_at: str
) -> KeywordObservation | None:
    if len(cells) < 4:
        raise ValueError("keyword row requires keyword, volume, KD, and intent")
    keyword = " ".join(cells[0].split()).lower()
    if not keyword:
        return None
    kd_value = cells[2].strip()
    kd = int(kd_value) if kd_value.isdigit() and 0 <= int(kd_value) <= 100 else None
    intent = cells[3].strip().upper() or None
    return KeywordObservation(keyword, parse_metric(cells[1]), kd, intent, root, result_type, market, retrieved_at)
