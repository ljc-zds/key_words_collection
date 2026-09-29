"""Markdown reporting for the Product Hunt keyword workflow."""

from pathlib import Path


def render_report(day: str, shortlisted: list[dict], excluded: list[dict]) -> str:
    lines = [
        "---",
        f"date: {day}",
        "source: product-hunt",
        f"shortlisted: {len(shortlisted)}",
        "tags: [product-hunt, keyword-research]",
        "---",
        "",
        "# Product Hunt 找词",
        "",
        "## 候选机会",
    ]
    lines.extend(
        [f"- [{item['name']}]({item['product_hunt_url']}) · {item['domain']} · {', '.join(item['keywords'])}" for item in shortlisted]
        or ["- 无"]
    )
    lines.extend(["", "## 排除项"])
    lines.extend([f"- {item['name']} · {'; '.join(item['reasons'])}" for item in excluded] or ["- 无"])
    return "\n".join(lines) + "\n"


def write_report(vault: Path, day: str, shortlisted: list[dict], excluded: list[dict]) -> Path:
    destination = vault / "01-个人输出/刷榜单目录/Product Hunt" / f"{day}【Product Hunt 找词】.md"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(render_report(day, shortlisted, excluded), encoding="utf-8")
    return destination
