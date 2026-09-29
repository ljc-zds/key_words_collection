"""Normalize rows copied from Semrush Keyword Manager."""
import re


_INTENTS = {
    "I": "Informational",
    "C": "Commercial",
    "N": "Navigational",
    "T": "Transactional",
}


def _metric(value: str) -> int | None:
    cleaned = value.replace(",", "").strip().lower()
    if cleaned in {"", "-", "不可用", "n/a"}:
        return None
    match = re.fullmatch(r"(\d+(?:\.\d+)?)(千|万|百万|k|m)?", cleaned)
    if match is None:
        return None
    number = float(match.group(1))
    multiplier = {"千": 1_000, "万": 10_000, "百万": 1_000_000, "k": 1_000, "m": 1_000_000, None: 1}[match.group(2)]
    return round(number * multiplier)


def _number(value: str) -> float | int | None:
    try:
        number = float(value)
    except ValueError:
        return None
    return int(number) if number.is_integer() else number


def _intent(value: str) -> str:
    labels = [_INTENTS[letter] for letter in value if letter in _INTENTS]
    return "/".join(labels) if labels else value


def parse_manager_cells(cells: list[str]) -> dict[str, object] | None:
    """Parse a Semrush Keyword Manager grid row into fields owned by Feishu."""
    if len(cells) < 11:
        return None
    keyword = cells[1].removesuffix("添加标签").strip()
    volume, kd = _metric(cells[4]), _metric(cells[7])
    if not keyword or volume is None or kd is None:
        return None
    return {
        "keyword": keyword,
        "intent": _intent(cells[2].strip()),
        "volume": volume,
        "kd": kd,
        "cpc": _number(cells[8]),
        "competitive_density": _number(cells[9]),
        "serp_features": _metric(cells[10]),
    }
