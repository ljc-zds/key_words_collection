"""Parse the visible AITDK Traffic panel without reading signed requests."""

import re


def _number(value: str) -> float:
    cleaned = value.replace(",", "").replace("$", "").strip()
    multiplier = 1
    if cleaned.endswith("K"):
        multiplier, cleaned = 1_000, cleaned[:-1]
    elif cleaned.endswith("M"):
        multiplier, cleaned = 1_000_000, cleaned[:-1]
    return float(cleaned) * multiplier


def _before(lines: list[str], label: str) -> str | None:
    try:
        index = lines.index(label)
    except ValueError:
        return None
    return lines[index - 1] if index else None


def parse_panel_text(text: str) -> dict:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    monthly_raw = _before(lines, "Monthly Visits")
    monthly = None
    if monthly_raw:
        try:
            monthly = int(_number(monthly_raw))
        except ValueError:
            pass
    shares = {}
    for line in lines:
        match = re.fullmatch(r"(Search|Direct):\s*([0-9.]+)%", line)
        if match:
            shares[match.group(1).lower()] = round(float(match.group(2)) / 100, 6)
    keywords: list[dict] = []
    if "Top Keywords" in lines and "Top Regions" in lines:
        start = lines.index("Top Keywords") + 5
        end = lines.index("Top Regions", start)
        values = lines[start:end]
        for index in range(0, len(values) - 3, 4):
            name, traffic, volume, cpc = values[index:index + 4]
            try:
                keywords.append({"name": name, "traffic": int(_number(traffic)), "volume": int(_number(volume)), "cpc": _number(cpc)})
            except ValueError:
                continue
    return {
        "status": "ok" if monthly is not None else "missing",
        "monthly_visits": monthly,
        "search_share": shares.get("search"),
        "direct_share": shares.get("direct"),
        "registered": _before(lines, "Domain Creation"),
        "domain_age": _before(lines, "Domain Age"),
        "keywords": keywords,
    }
