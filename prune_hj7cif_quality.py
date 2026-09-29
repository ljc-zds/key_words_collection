"""Strictly prune low-quality discovery candidates from the HJ7cif worksheet.

This intentionally preserves only keywords with a concrete, legal, repeatable
site model. It never touches the e2e503 worksheet.
"""

from __future__ import annotations

from keyword_loop.core.publishing.feishu import load_env, request_json, resolve_wiki_node, tenant_access_token
from keyword_loop.core.data.store import KeywordStore


WIKI_URL = "https://my.feishu.cn/wiki/VHnXwGzGQiGeUkkgj4tc4kpLnbh"
SHEET_ID = "HJ7cif"
DB_PATH = "output/keyword-loop.sqlite3"

# Deliberately conservative: every retained term has a direct site/product
# shape. Comparison, brand-navigation, entertainment, news and generic terms
# require a separate editorial decision before they return to the queue.
KEEP = {
    "anime vanguards codes",
    "connections hint",
    "convertir pdf a word",
    "crk codes",
    "editar pdf",
    "modifier pdf",
    "nyt connections hints today",
    "nyt strands hints",
    "pdf ke word",
    "pdf ocr",
    "pdf to word free",
    "strands hint today",
    "strands hints",
    "vocal range test",
    "wordle hint",
    "wordle hints",
    "wordle solver",
}


def main() -> None:
    env = load_env()
    token = tenant_access_token(env)
    spreadsheet = resolve_wiki_node(WIKI_URL, token)["obj_token"]
    values_url = f"https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/{spreadsheet}/values"
    existing = request_json(
        f"{values_url}/{SHEET_ID}!A1:AR5000", method="GET", token=token
    )["data"]["valueRange"].get("values", [])
    if not existing:
        raise RuntimeError("HJ7cif is empty; refusing to prune")

    header, rows = existing[0], existing[1:]
    retained = [row for row in rows if row and str(row[0]).strip().lower() in KEEP]
    removed = [str(row[0]).strip() for row in rows if row and str(row[0]).strip() and str(row[0]).strip().lower() not in KEEP]
    unexpected = {str(row[0]).strip().lower() for row in retained} - KEEP
    if unexpected or len(retained) != len(KEEP):
        missing = sorted(KEEP - {str(row[0]).strip().lower() for row in retained})
        raise RuntimeError(f"keep-list mismatch; unexpected={unexpected}, missing={missing}")

    store = KeywordStore(DB_PATH)
    for keyword in removed:
        store.record_validation(keyword.lower(), "global", "manual_prune", {
            "decision": "淘汰",
            "reason": "不符合精品可建站标准：品牌/导航、时效新闻、影视人物、泛定义、敏感领域或缺少独立且可持续的变现站点形态。",
            "sheet": SHEET_ID,
        })

    # Write the compacted table, then clear old trailing rows so deleted
    # keywords do not remain visible below the new table.
    compacted = [header] + retained
    request_json(
        f"{values_url}_batch_update",
        method="POST",
        token=token,
        payload={"valueRanges": [{"range": f"{SHEET_ID}!A1:AR{len(compacted)}", "values": compacted}]},
    )
    old_last = len(existing)
    if old_last > len(compacted):
        empty = [[""] * 44 for _ in range(old_last - len(compacted))]
        request_json(
            f"{values_url}_batch_update",
            method="POST",
            token=token,
            payload={"valueRanges": [{"range": f"{SHEET_ID}!A{len(compacted)+1}:AR{old_last}", "values": empty}]},
        )

    verified = request_json(
        f"{values_url}/{SHEET_ID}!A1:A5000", method="GET", token=token
    )["data"]["valueRange"].get("values", [])
    actual = [str(row[0]).strip().lower() for row in verified[1:] if row and row[0]]
    if set(actual) != KEEP or len(actual) != len(KEEP):
        raise RuntimeError(f"post-write verification failed: {actual}")
    print({"retained": len(actual), "removed": len(removed), "keywords": actual})


if __name__ == "__main__":
    main()
