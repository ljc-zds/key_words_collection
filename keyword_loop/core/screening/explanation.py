from ..data.models import KeywordCandidate


_INTENTS = {
    "COMMERCIAL": ("商业型", "用户正在比较或评估解决方案，适合落地为订阅产品的对比、试用或功能页。"),
    "TRANSACTIONAL": ("交易型", "用户接近购买或注册，适合直接承接订阅转化。"),
    "INFORMATIONAL": ("信息型", "用户正在寻找相关内容、答案或资源，适合以内容、数据库或免费工具建立订阅漏斗。"),
    "NAVIGATIONAL": ("导航型", "用户倾向寻找特定品牌，需先排除品牌词后再评估。"),
    "LOCAL": ("本地型", "用户在寻找特定地区可获得的服务或资源；仅当产品涉及本地商家名录、预约、地图或区域获客时优先评估。"),
}

_INTENT_ALIASES = {
    "INFO": "INFORMATIONAL",
    "NAV": "NAVIGATIONAL",
    "COMM": "COMMERCIAL",
    "TRANS": "TRANSACTIONAL",
}


def explain_candidate(candidate: KeywordCandidate) -> str:
    meaning, intent, value = explanation_fields(candidate)
    return f"是什么：{meaning} 搜索意图：{intent} 商业价值：{value}"


def explanation_fields(candidate: KeywordCandidate) -> tuple[str, str, str]:
    intent = _INTENT_ALIASES.get((candidate.intent or "").upper(), (candidate.intent or "").upper())
    label, value = _INTENTS.get(intent, ("未知", "需人工判断需求和订阅价值。"))
    meaning = f"用户在寻找与“{candidate.keyword}”相关的产品、内容或解决方案。"
    return meaning, label, value
