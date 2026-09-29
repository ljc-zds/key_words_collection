from dataclasses import dataclass


@dataclass(frozen=True)
class GateResult:
    decision: str
    reason: str


def volume_kd_gate(volume: int | None, kd: int | None) -> GateResult:
    """Apply the shared volume/KD thresholds to Similarweb or Semrush data."""
    if volume is None or kd is None:
        return GateResult("淘汰", "搜索量或 KD 缺失，无法完成筛选")
    if volume >= 30_000:
        maximum_kd = 60
    elif volume >= 10_000:
        maximum_kd = 45
    elif volume >= 5_000:
        maximum_kd = 30
    else:
        return GateResult("淘汰", f"搜索量 {volume:,}，低于 5,000")
    if kd <= maximum_kd:
        return GateResult("保留", f"搜索量 {volume:,}，KD {kd}，符合该体量的 KD 上限 {maximum_kd}")
    return GateResult("淘汰", f"搜索量 {volume:,} 对应 KD 上限 {maximum_kd}，当前 KD {kd}")


def semrush_missing_gate() -> GateResult:
    """Keep a Similarweb-approved candidate when Semrush has no exact row."""
    return GateResult("保留", "Semrush US 未返回精确关键词，沿用 Similarweb 分档通过结果")


_TOOL_TERMS = (
    "generator", "calculator", "converter", "checker", "analyzer", "editor",
    "maker", "template", "planner", "tracker", "optimizer", "how much",
)
_OPPORTUNITY_MODIFIERS = ("alternative", "alternatives", "review", "reviews", " vs ", "comparison")
_PHYSICAL_PRODUCTS = (
    "air fryer", "airfryer", "airpods", "macbook", "iphone", "ipad", "dyson airwrap",
)
_RISK_TERMS = (
    "watch online", "full movie", "episode", "subtitle", "crack", "cracked",
    "serial key", "apk mod", "near me", "opening hours",
)


def keyword_quality_gate(keyword: str) -> GateResult:
    """Reject ambiguous tokens before spending paid validation credits.

    A bare number is normally a transient trend, an identifier, or an
    underspecified query. It cannot describe a stable, independently
    monetizable site opportunity without an explicit human review.
    """
    normalized = " ".join(keyword.lower().split())
    compact = normalized.replace(" ", "")
    if compact.isdecimal():
        return GateResult("淘汰", "纯数字关键词，歧义过高且通常为短期热点或编号查询")
    if len(compact) <= 2 and not any(char.isalpha() for char in compact):
        return GateResult("淘汰", "极短非字母关键词，缺少稳定可承接的搜索需求")
    return GateResult("保留", "关键词形式有效，进入数据验证")


def intent_gate(keyword: str, semrush: dict) -> GateResult:
    normalized = " ".join(keyword.lower().split())
    intent = str(semrush.get("intent", "")).lower()
    if any(term in normalized for term in _TOOL_TERMS):
        return GateResult("保留", "存在明确工具化或计算需求")
    if any(term in normalized for term in _RISK_TERMS):
        return GateResult("淘汰", "影视观看、破解下载或本地导航等高风险/低适配意图")
    if any(term in normalized for term in _PHYSICAL_PRODUCTS):
        return GateResult("淘汰", "实体商品主词，不符合精品软件工具页目标")
    if "navig" in intent and not any(term in f" {normalized} " for term in _OPPORTUNITY_MODIFIERS):
        return GateResult("淘汰", "纯品牌或网站导航意图")
    return GateResult("保留", "未命中硬淘汰规则，进入变现机会评估")
