import csv
import re
from pathlib import Path


def load_roots(path: Path) -> list[str]:
    with path.open(encoding="utf-8", newline="") as source:
        rows = csv.DictReader(source)
        if not rows.fieldnames or "root" not in rows.fieldnames:
            raise ValueError("root CSV requires a root column")
        roots = {
            " ".join(row["root"].split()).lower()
            for row in rows
            if row.get("root") and row.get("active", "true").strip().lower() in {"true", "1", "yes"}
        }
    return sorted(roots)


def propose_roots(keywords: list[str]) -> list[str]:
    stop_words = {"best", "for", "with", "the", "and"}
    tokens = {token for keyword in keywords for token in re.findall(r"[a-zA-Z]+", keyword.lower()) if len(token) > 1 and token not in stop_words}
    return sorted(tokens)
