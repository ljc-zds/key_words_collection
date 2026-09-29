"""Write the current Product Hunt sample batch through Feishu Sheets API."""

import json
from pathlib import Path
from urllib.request import Request, urlopen

from product_hunt.aitdk.product.product_hunt import trusted_ssl_context


SPREADSHEET_TOKEN = "O3hOwQpSDiXPJrkqcPxcVFtBnHb"
SHEET_ID = "444228"
RANGE = f"{SHEET_ID}!A1:K11"


def load_env() -> dict[str, str]:
    return {
        key: value
        for key, value in (
            line.strip().split("=", 1)
            for line in Path(".env").read_text(encoding="utf-8").splitlines()
            if "=" in line
        )
    }


def request_json(url: str, *, method: str, payload: dict | None = None, token: str | None = None) -> dict:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(payload, ensure_ascii=False).encode() if payload is not None else None
    request = Request(url, data=body, headers=headers, method=method)
    with urlopen(request, context=trusted_ssl_context(), timeout=30) as response:
        return json.load(response)


def tenant_token(env: dict[str, str]) -> str:
    data = request_json(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        method="POST",
        payload={"app_id": env["FEISHU_APP_ID"], "app_secret": env["FEISHU_APP_SECRET"]},
    )
    if data.get("code") != 0:
        raise RuntimeError("Feishu authentication failed")
    return data["tenant_access_token"]


def rows() -> list[list[str]]:
    missing = "AITDK 无数据"
    source = "Product Hunt · 2026-08-23"
    return [
        ["产品", "网站", "域名", "来源 / 日期", "总访问量", "搜索占比", "直接占比", "需求词 / 搜索访问", "注册日期", "筛选状态", "域名年龄 / 备注"],
        ["Plask", "https://plask.info", "plask.info", source, "0", "0.00%", "0.00%", "无 / 搜索访问 0", "2026-08-03", "不通过：访问量不足", "20 天"],
        ["Whelk: Private AI Platform", "https://www.getwhelk.com", "getwhelk.com", source, missing, missing, missing, missing, "2026-07-20", "AITDK 无数据", "35 天"],
        ["Utility", "https://utility-app.xyz", "utility-app.xyz", source, missing, missing, missing, missing, "2026-07-12", "AITDK 无数据", "43 天"],
        ["Primis", "https://getprimis.lovable.app", "getprimis.lovable.app", source, missing, missing, missing, missing, "待核验", "AITDK 无数据 / 子域名", "注册日期需查询 lovable.app"],
        ["Mera Form", "https://www.mera-form.com", "mera-form.com", source, missing, missing, missing, missing, "2026-08-14", "AITDK 无数据", "10 天"],
        ["Construct Computer", "https://construct.computer", "construct.computer", source, "0", "0.00%", "0.00%", "ai sub-workflow timeline / 搜索访问 0", "2026-02-20", "不通过：访问量不足", "184 天"],
        ["KanaSensei", "https://kanasensei.dev", "kanasensei.dev", source, "0", "0.00%", "0.00%", "无 / 搜索访问 0", "2026-08-04", "不通过：访问量不足", "19 天"],
        ["Built. Tested. Shipped.", "https://ankit-freelance.vercel.app", "ankit-freelance.vercel.app", source, missing, missing, missing, missing, "待核验", "AITDK 无数据 / 子域名", "注册日期需查询 vercel.app"],
        ["BigCSV", "https://www.bigcsv.app", "bigcsv.app", source, missing, missing, missing, missing, "2026-06-25", "AITDK 无数据", "60 天"],
        ["Flown", "https://apps.apple.com/us/app/flown-live-flights-trips/id6789278771", "-", source, "不适用", "不适用", "不适用", "不适用", "-", "仅 App Store", "无独立官网"],
    ]


def main() -> None:
    token = tenant_token(load_env())
    result = request_json(
        f"https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/{SPREADSHEET_TOKEN}/values",
        method="PUT",
        payload={"valueRange": {"range": RANGE, "values": rows()}},
        token=token,
    )
    if result.get("code") != 0:
        raise RuntimeError("Feishu write failed")
    print("Feishu wrote A1:K11")


if __name__ == "__main__":
    main()
