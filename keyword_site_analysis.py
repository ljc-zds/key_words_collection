"""Local-only Similarweb and Semrush site-opportunity analysis."""

from __future__ import annotations

import json
import math
import re
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


SERP_STATUS = "未进行实时 SERP 验证"

TOOL_PATTERNS: list[tuple[str, tuple[str, ...]]] = [
    ("计算器", ("calculator", "calculate", "estimator", "estimation", "cost calculator")),
    ("转换工具", ("converter", "convert", "conversion tool")),
    ("生成器", ("generator", "maker", "creator", "randomizer", "name ideas")),
    ("检查与分析工具", ("checker", "analyzer", "analyser", "optimizer", "validator", "tester", "scanner", "audit tool")),
    ("编辑与处理工具", ("editor", "compressor", "resizer", "cropper", "remover", "merger", "splitter", "formatter")),
    ("规划与追踪工具", ("planner", "tracker", "counter", "scheduler", "timer", "calendar tool")),
]

GAME_SIGNALS = (
    "codes", "tier list", "trade value", "trading value", "builds", "loadout",
    "stats", "database", "wiki", "items", "characters", "map", "drop rate",
)
ASSET_SIGNALS = (
    "template", "templates", "font", "fonts", "icon", "icons", "wallpaper",
    "printable", "coloring page", "worksheet", "mockup", "preset", "clipart",
)
COMPARISON_SIGNALS = ("alternative", "alternatives", " vs ", "comparison", "review", "reviews", "pricing")
LEARNING_SIGNALS = (
    "examples", "ideas", "quiz", "practice", "cheat sheet", "reference", "list of",
)
OPPORTUNITY_SIGNALS = tuple(
    signal for _, signals in TOOL_PATTERNS for signal in signals
) + GAME_SIGNALS + ASSET_SIGNALS + COMPARISON_SIGNALS + LEARNING_SIGNALS

POLICY_RISK_TERMS = (
    "watch online", "watch free", "full movie", "free movie", "free episode",
    "subtitle download", "torrent", "crack", "cracked", "serial key", "keygen",
    "apk mod", "mod apk", "onlyfans leak", "porn", "xxx", "casino bonus",
    "betting tips", "betmentor", "youtube downloader", "tiktok downloader", "instagram downloader",
    "watermark remover", "remove watermark",
    "rapidgator premium link generator", "nsfw prompt generator", "credit card generator",
)
MISSPELLED_MEDIA_PLATFORM_TERMS = (
    "yotube", "youtbe", "youtibe", "youtub", "yputube", "yourube",
)
LOCAL_NAV_TERMS = ("near me", "opening hours", "phone number", "directions", "customer service number")
PHYSICAL_PRODUCT_TERMS = (
    "air fryer", "airfryer", "airpods", "macbook", "iphone", "ipad", "vacuum cleaner",
    "running shoes", "office chair", "coffee maker", "espresso maker", "headphones", "smart watch", "fitness tracker",
)
PHYSICAL_GENERATOR_TERMS = (
    "diesel generator", "solar generator", "inverter generator", "portable generator",
    "thermoelectric generator", "atmospheric water generator", "function generator",
    "generator for home", "small generator", "generator rex", "gas generator",
    "generator repair", "generator service", "generator installation", "generator cost",
    "home generator", "house generator", "generator transfer switch", "transfer switch for generator",
    "propane generator", "dual fuel generator", "rv generator", "generator portable generators",
    "generator gas generators", "generac generator", "predator 3500 generator",
)
PHYSICAL_CONVERTER_TERMS = (
    "catalytic converter", "rust converter", "buck converter", "boost converter",
    "torque converter", "voltage converter", "standing desk converter",
    "type c to usb converter", "digital to analog converter", "converter circuit",
)
DIGITAL_MAKER_CONTEXT = (
    "online", "logo", "name", "username", "font", "text", "image", "photo", "video",
    "audio", "meme", "avatar", "character", "chart", "graph", "diagram", "timeline",
    "map", "website", "resume", "invoice", "poster", "barcode", "qr", "collage",
    "animation", "pixel", "sprite", "roblox", "music", "beat", "producer tag",
    "signature", "emoji", "icon", "thumbnail", "playlist", "quiz", "worksheet",
    "template", "genogram", "pngtuber",
)
BRANDED_CREATOR_TERMS = (
    "tyler the creator", "osmo pocket 3 creator", "lego creator", "cricut maker",
    "flashforge creator", "fortnite creator portal", "relx creator",
)
YMYL_TERMS = (
    "diagnosis", "symptom checker", "legal advice", "lawsuit", "tax advice",
    "loan approval", "credit repair", "dosage calculator",
)
CAREER_TERMS = ("jobs", "job description", "salary", "career", "certification")
PHYSICAL_TESTER_TERMS = (
    "battery tester", "diamond tester", "lan tester", "xrf analyzer", "grip strength tester",
    "compression tester", "cable tester", "voltage tester", "network cable tester", "perfumes tester",
)
BRANDED_PRODUCT_TERMS = (
    "dell optimizer", "tivoli workload scheduler", "wise memory optimizer", "adobe journey optimizer",
    "windows performance analyzer", "logitech tap scheduler", "casio calculator", "marlow crystal optimizer",
    "neuro optimizer", "curve optimizer", "hellzerg optimizer", "muon optimizer", "pdf24 creator",
    "roblox creator dashboard", "creator dashboard", "cornell scheduler", "pokemon wallpaper",
    "wallpaper pokemon wallpaper", "adobe qr code generator",
    "ramsey investment calculator", "ramsey retirement calculator", "canva pdf editor",
    "freepik ai image generator", "hello kitty", "ti 84 calculator", "ti-84 calculator",
    "casio step tracker", "ikea besta planner", "domino's tracker", "google ads editor",
)
PHYSICAL_OR_MEDIA_TRACKER_TERMS = (
    "gps tracker", "smart tracker", "bus tracker", "tracker episodes", "tracker season",
    "chevy tracker", "tracker chevrolet", "triumph tracker", "step tracker",
)
INDIA_MARKET_TERMS = (
    " india", "india ", "indian", " lakh", "crore", "rupee", "cbse", "upsc", "jee", "neet",
    "sukanya samriddhi", "yojana", "sip calculator", "step up sip", "stepup sip",
    "ppf calculator", "nps calculator", "gratuity calculator", "emi calculator",
    "lumpsum calculator", "gst calculator", "rashi calculator", "mahadasha calculator",
    "gold loan calculator", "gold rate calculator", "zerodha brokerage calculator",
    "post office monthly income scheme calculator",
)
SPORTS_MATCH_TERMS = (
    "arsenal", "chelsea", "man city", "manchester city", "southampton", "sporting",
    "crystal palace", "bournemouth", "atlético madrid", "atletico madrid", "world cup",
)
KNOWN_TOOL_ACRONYMS = {
    "bac", "bmi", "bmr", "cagr", "cgpa", "cpm", "dpi", "emi", "ffmi", "fps",
    "gst", "nps", "ppf", "rmd", "roi", "sip", "tdee", "vat", "1rm",
}
ONLINE_TOOL_CONTEXT = (
    "domain", "website", "email", "header", "seo", "keyword", "prompt", "text", "image",
    "photo", "video", "audio", "file", "url", "username", "password", "dpi", "mouse",
    "click", "keyboard", "screen", "font", "color", "contrast", "plagiarism", "grammar",
    "readability", "fantasy", "trade", "nfl", "baseball", "football", "pokemon", "genshin",
    "roblox", "minecraft", "gpu", "pc", "ram", "playlist", "bpm", "metadata", "json",
    "html", "css", "monetization", "bulk", "da pa", "age checker", "expiry checker",
)
COMPARISON_SITE_CONTEXT = (
    "adobe", "chatgpt", "claude", "elevenlabs", "heygen", "klaviyo", "lovable", "n8n",
    "openrouter", "replit", "sales navigator", "zapier", "air fryer", "blender", "food processor",
    "coffee maker", "software", "ai tool", "automation", "crm", "email marketing",
)
IMAGE_FORMATS = {"avif", "gif", "heic", "ico", "image", "img", "jfif", "jpeg", "jpg", "png", "svg", "webp"}
DOCUMENT_FORMATS = {"csv", "djvu", "doc", "docx", "epub", "excel", "html", "markdown", "md", "mobi", "odt", "pages", "pdf", "ppt", "pptx", "txt", "word", "xls", "xlsx"}
AUDIO_FORMATS = {"audio", "flac", "m4a", "mp3", "ogg", "wav"}
VIDEO_FORMATS = {"avi", "mkv", "mov", "mp4", "video", "webm"}
GAME_HINTS = (
    "roblox", "minecraft", "pokemon", "fortnite", "steam", "genshin", "valorant",
    "league of legends", "blox", "anime game", "rpg", "game",
)
STOPWORDS = {
    "a", "an", "and", "for", "free", "in", "of", "online", "the", "to", "tool",
    "best", "my", "your", "with", "without", "from", "on", "app", "website",
}
MODIFIER_WORDS = {
    "calculator", "calculate", "estimator", "converter", "generator", "maker", "creator",
    "checker", "analyzer", "analyser", "optimizer", "validator", "tester", "scanner",
    "editor", "compressor", "resizer", "cropper", "remover", "merger", "splitter",
    "formatter", "planner", "tracker", "counter", "scheduler", "timer", "template",
    "templates", "guide", "tutorial", "wiki", "codes", "code", "list", "review",
    "reviews", "alternative", "alternatives", "comparison", "pricing", "meaning",
}


def normalize_keyword(text: Any) -> str:
    value = str(text or "").strip().lower()
    value = re.sub(r"[\u2018\u2019]", "'", value)
    return " ".join(value.split())


def _contains_signal(keyword: str, signal: str) -> bool:
    pattern = r"(?<![a-z0-9])" + re.escape(signal.strip()) + r"(?![a-z0-9])"
    return re.search(pattern, keyword) is not None


def _number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _append_unique(target: list[str], values: Iterable[Any]) -> None:
    for value in values:
        clean = normalize_keyword(value)
        if clean and clean not in target:
            target.append(clean)


def merge_keyword_records(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge rows by normalized keyword without blending provider metrics."""
    merged: dict[str, dict[str, Any]] = {}
    for source in rows:
        keyword = normalize_keyword(source.get("keyword"))
        if not keyword:
            continue
        item = merged.setdefault(keyword, {
            "keyword": keyword,
            "similarweb_roots": [],
            "similarweb_result_types": [],
            "semrush_parents": [],
        })
        provider = str(source.get("provider", "")).lower()
        if provider == "similarweb":
            for field in ("volume", "kd", "intent", "retrieved_at"):
                value = source.get(field)
                if value is not None and value != "":
                    item[f"similarweb_{field}"] = value
            _append_unique(item["similarweb_roots"], source.get("roots", []) or ([source.get("root")] if source.get("root") else []))
            _append_unique(item["similarweb_result_types"], source.get("result_types", []) or ([source.get("result_type")] if source.get("result_type") else []))
        elif provider == "semrush":
            for field in ("volume", "kd", "cpc", "intent", "competitive_density", "serp_features", "retrieved_at"):
                value = source.get(field)
                key = f"semrush_{field}"
                if value is not None and value != "" and (key not in item or str(source.get("retrieved_at", "")) >= str(item.get("semrush_retrieved_at", ""))):
                    item[key] = value
            _append_unique(item["semrush_parents"], source.get("parents", []) or ([source.get("parent_keyword")] if source.get("parent_keyword") else []))
            if source.get("exact_match"):
                item["semrush_exact_match"] = True
    return list(merged.values())


def priority_for_score(score: float) -> str:
    if score >= 80:
        return "P0"
    if score >= 70:
        return "P1"
    if score >= 60:
        return "P2"
    return "淘汰"


def explain_keyword(keyword: str, site_type: str, risk_notes: str = "") -> str:
    """Create a detailed, model-friendly fallback explanation for one accepted keyword."""
    phrase = normalize_keyword(keyword)
    words = phrase.split()
    if site_type == "计算器":
        if "atar" in words:
            purpose = "估算澳大利亚高中生的大学入学排名（ATAR）"
            inputs = "输入各科成绩、科目组合和所在州的评分规则"
            output = "输出预估排名区间，并与目标大学或专业的录取要求比较"
        elif "ira" in words or "401k" in words or "retirement" in words or "pension" in words:
            purpose = "估算退休账户或养老金的长期增长"
            inputs = "输入初始余额、定期缴费、年化收益率和投资年限"
            output = "输出账户终值、累计缴费、投资收益和不同方案的对比"
        elif any(token in words for token in ("loan", "mortgage", "emi", "paycheck", "salary", "income", "tax")):
            purpose = "估算贷款、还款、收入或税务相关结果"
            inputs = "输入金额、利率、期限、收入或所在地区等参数"
            output = "输出月供、总利息、可负担额度或预计到手金额"
        elif any(token in words for token in ("score", "grade", "study", "ielts", "mcat", "ucat", "gpa")):
            purpose = "根据成绩或考试分数估算等级、排名或达标结果"
            inputs = "输入科目成绩、考试分数或评分规则"
            output = "输出总分、等级、排名区间或距离目标分数的差距"
        elif any(token in words for token in ("trade", "fantasy", "pokemon", "damage")):
            purpose = "计算游戏或幻想体育中的交易价值、伤害或方案差异"
            inputs = "输入参与对象、属性、规则和比较方案"
            output = "输出公平度、价值差、伤害结果或推荐方案"
        else:
            purpose = f"计算与“{phrase}”相关的数值结果"
            inputs = "输入该主题所需的数量、比例、时间或其他参数"
            output = "输出计算结果、过程说明和可分享的结果摘要"
        return f"用户想{purpose}。网站应支持{inputs}，并{output}。适合做成带参数表单、结果解释、方案对比和常见问题的在线工具。{risk_notes if risk_notes and risk_notes != '未发现明显硬风险' else '需要在页面中说明计算口径和结果仅供参考。'}"
    if site_type == "转换工具":
        match = re.search(r"([a-z0-9]+)\s+to\s+([a-z0-9]+)", phrase)
        if match:
            source, target = match.groups()
            purpose = f"把{source.upper()}格式转换为{target.upper()}格式"
        else:
            purpose = f"完成“{phrase}”对应的文件、单位或内容转换"
        return f"用户想{purpose}。网站应支持上传或输入原始内容，执行转换并提供预览、参数提示和结果下载。MVP 可包含单文件处理、格式校验、错误提示和下载按钮；批量处理、历史记录和隐私说明可作为后续功能。{risk_notes if risk_notes and risk_notes != '未发现明显硬风险' else '需要说明文件大小、隐私保留时间和转换质量限制。'}"
    if site_type in {"生成器", "编辑与处理工具"}:
        return f"用户想生成或处理与“{phrase}”相关的内容。网站应提供输入框或上传入口、可调整的选项、实时预览和复制或下载结果。MVP 先覆盖最常用的一种输出格式，再增加模板、批量处理和分享功能。{risk_notes if risk_notes and risk_notes != '未发现明显硬风险' else '需要明确输出内容的授权、隐私和使用限制。'}"
    if site_type == "检查与分析工具":
        return f"用户想检查或分析“{phrase}”对应的数据、文件、页面或配置。网站应让用户提交待检查内容，返回可解释的指标、问题列表和改进建议，并支持复制报告。MVP 包含输入校验、核心指标、结果解释和导出摘要。{risk_notes if risk_notes and risk_notes != '未发现明显硬风险' else '需要避免把分析结果描述成绝对结论。'}"
    if site_type == "规划与追踪工具":
        return f"用户想围绕“{phrase}”制定计划、记录进度或追踪状态。网站应支持新增目标、设置周期、记录完成情况和查看趋势。MVP 包含本地保存、提醒状态和简单统计，后续可增加账号同步和导出。{risk_notes if risk_notes and risk_notes != '未发现明显硬风险' else '需要明确数据保存和提醒机制。'}"
    if site_type == "游戏资料与辅助工具":
        return f"用户想查询或比较游戏“{phrase}”相关的角色、装备、代码、排名或交易信息。网站应提供可搜索的数据表、筛选条件、详情页和更新时间。MVP 先覆盖一个游戏和一个核心场景，再扩展版本历史、计算器和攻略页面。{risk_notes if risk_notes and risk_notes != '未发现明显硬风险' else '需要持续更新数据并核查游戏商标和平台政策。'}"
    if site_type == "模板与素材站":
        return f"用户想查找、预览或使用“{phrase}”相关的字体、模板、图标或素材。网站应提供分类、搜索、预览、授权说明和下载入口。MVP 先建立清晰的资源目录和授权信息，后续增加收藏、相似推荐和付费资源。{risk_notes if risk_notes and risk_notes != '未发现明显硬风险' else '必须核查字体、图片和品牌素材的授权范围。'}"
    if site_type == "比较与评测站":
        return f"用户想比较“{phrase}”涉及的产品、服务或替代方案，以辅助购买或选型。网站应提供功能、价格、适用人群、优缺点和选择建议。MVP 先覆盖少量明确对象并保持数据更新时间，后续增加筛选器、计算器和联盟转化。{risk_notes if risk_notes and risk_notes != '未发现明显硬风险' else '需要标注价格、评测依据和商业合作关系。'}"
    return f"用户正在查找“{phrase}”相关的教程、示例或资料。网站应提供结构化解释、步骤、示例、FAQ 和相关推荐，逐步形成主题内容集群。{risk_notes if risk_notes and risk_notes != '未发现明显硬风险' else '需要核查内容准确性和来源。'}"


def classify_site_type(keyword: str) -> tuple[str | None, int, int, str]:
    padded = f" {keyword} "
    for site_type, signals in TOOL_PATTERNS:
        if any(_contains_signal(keyword, signal) for signal in signals):
            return site_type, 20, 9, "需求可由单页交互工具直接满足"
    if re.search(r"\b[a-z0-9]+\s+to\s+(?:pdf|png|jpe?g|webp|gif|mp3|mp4|wav|csv|xlsx?|docx?|mobi|epub)\b", keyword):
        return "转换工具", 20, 9, "需求可由单页格式转换工具直接满足"
    if any(_contains_signal(keyword, signal) for signal in GAME_SIGNALS) and (
        any(_contains_signal(keyword, hint) for hint in GAME_HINTS) or any(_contains_signal(keyword, token) for token in ("tier list", "trade value", "drop rate"))
    ):
        return "游戏资料与辅助工具", 18, 9, "适合围绕游戏数据、代码或攻略形成页面集群"
    if any(_contains_signal(keyword, signal) for signal in ASSET_SIGNALS):
        return "模板与素材站", 16, 9, "适合提供可预览、筛选或下载的合规素材"
    if any(_contains_signal(padded, signal) for signal in COMPARISON_SIGNALS):
        return "比较与评测站", 15, 8, "具有明确的比较或购买决策意图"
    if any(_contains_signal(keyword, signal) for signal in LEARNING_SIGNALS):
        return "教程与资料站", 13, 7, "适合作为专题内容集群中的长尾页面"
    return None, 0, 0, "没有识别到可重复交付的网站需求"


def cluster_key(keyword: str, site_type: str) -> str:
    words = re.findall(r"[a-z0-9]+", keyword.lower())
    if site_type == "转换工具":
        match = re.search(r"\b([a-z0-9]+)\s+to\s+([a-z0-9]+)\b", keyword.lower())
        if match:
            def family(value: str) -> str:
                if value in IMAGE_FORMATS:
                    return "image"
                if value in DOCUMENT_FORMATS:
                    return "document"
                if value in AUDIO_FORMATS:
                    return "audio"
                if value in VIDEO_FORMATS:
                    return "video"
                return value
            return f"{family(match.group(1))} to {family(match.group(2))}"
    if site_type == "教程与资料站" and _contains_signal(keyword, "nail") and _contains_signal(keyword, "ideas"):
        return "nail ideas"
    if site_type == "教程与资料站" and _contains_signal(keyword, "fantasy") and _contains_signal(keyword, "cheat sheet"):
        return "fantasy sports cheat sheets"
    if site_type == "检查与分析工具" and _contains_signal(keyword, "fantasy") and _contains_signal(keyword, "trade"):
        return "fantasy trade"
    useful = [word for word in words if word not in STOPWORDS and word not in MODIFIER_WORDS]
    return " ".join(useful[:4]) or " ".join(words[:3]) or keyword


def _demand_score(volume: float) -> int:
    if volume >= 500_000:
        return 20
    if volume >= 100_000:
        return 18
    if volume >= 30_000:
        return 15
    if volume >= 10_000:
        return 11
    return 8


def _seo_score(kd: float) -> int:
    if kd <= 15:
        return 25
    if kd <= 25:
        return 22
    if kd <= 35:
        return 18
    if kd <= 45:
        return 13
    return 7


def _monetization_score(cpc: float | None, intent: str, site_type: str) -> int:
    if cpc is None:
        base = 7 if site_type in {"计算器", "检查与分析工具", "比较与评测站"} else 5
    elif cpc >= 5:
        base = 15
    elif cpc >= 2:
        base = 13
    elif cpc >= 1:
        base = 11
    elif cpc >= 0.5:
        base = 8
    elif cpc > 0:
        base = 6
    else:
        base = 3
    if any(term in intent.lower() for term in ("commercial", "transactional")):
        base += 2
    return min(15, base)


def assess_keyword(record: dict[str, Any]) -> dict[str, Any]:
    item = dict(record)
    keyword = normalize_keyword(item.get("keyword"))
    item["keyword"] = keyword
    sw_volume = _number(item.get("similarweb_volume"))
    sr_volume = _number(item.get("semrush_volume"))
    sw_kd = _number(item.get("similarweb_kd"))
    sr_kd = _number(item.get("semrush_kd"))
    volumes = [value for value in (sw_volume, sr_volume) if value is not None]
    kds = [value for value in (sw_kd, sr_kd) if value is not None]

    def reject(code: str, reason: str) -> dict[str, Any]:
        item.update(included=False, exclusion_code=code, decision_reason=reason, serp_status=SERP_STATUS)
        return item

    if not keyword or keyword.replace(" ", "").isdigit() or len(keyword.replace(" ", "")) <= 2:
        return reject("ambiguous", "关键词过短、纯数字或缺少明确含义")
    if any(term in keyword for term in POLICY_RISK_TERMS):
        return reject("policy_risk", "命中盗版、破解、成人或赌博等高风险需求")
    if (
        any(term in keyword for term in MISSPELLED_MEDIA_PLATFORM_TERMS)
        and any(_contains_signal(keyword, signal) for signal in ("converter", "convert", "mp3", "mp4", "wav", "download", "downloader"))
    ) or keyword == "link to mp3":
        return reject("policy_risk", "涉及第三方平台媒体转换或下载，存在版权与平台条款风险")
    if (any(platform in keyword for platform in ("youtube", "tiktok", "instagram", "soundcloud", "spotify", "apple music")) or re.search(r"\byt\b", keyword)) and any(
        _contains_signal(keyword, signal) for signal in ("converter", "convert", "mp3", "mp4", "wav", "download", "downloader")
    ):
        return reject("policy_risk", "涉及第三方平台媒体转换或下载，存在版权与平台条款风险")
    if any(term in keyword for term in LOCAL_NAV_TERMS):
        return reject("local_navigation", "本地导航或联系方式查询不适合作为目标网站")
    if any(_contains_signal(keyword, term) for term in CAREER_TERMS):
        return reject("career_query", "招聘、薪资或职业查询不属于目标工具/内容站机会")
    if any(_contains_signal(keyword, term) for term in PHYSICAL_TESTER_TERMS):
        return reject("physical_tool", "关键词指向实体检测设备，而非在线工具")
    if any(_contains_signal(keyword, term) for term in BRANDED_PRODUCT_TERMS):
        return reject("branded_product", "关键词更接近品牌软件或既有产品导航，而非独立建站需求")
    if any(_contains_signal(keyword, term) for term in PHYSICAL_OR_MEDIA_TRACKER_TERMS):
        return reject("physical_product", "关键词指向实体追踪设备、交通工具或影视内容，不是可独立交付的在线工具")
    padded_keyword = f" {keyword} "
    if any(term in padded_keyword for term in INDIA_MARKET_TERMS):
        return reject("india_market", "需求主要面向印度市场，不符合本次目标市场")
    if _contains_signal(keyword, "calculator") and (
        _contains_signal(keyword, "casio") or _contains_signal(keyword, "price")
    ):
        return reject("physical_product", "关键词指向计算器品牌或实体商品购买需求")
    if any(_contains_signal(keyword, term) for term in BRANDED_CREATOR_TERMS):
        return reject("branded_product", "关键词中的 creator 或 maker 指向人物、品牌或既有产品")
    if re.search(r"[^\x00-\x7f]", keyword) or (
        re.search(r"\b(?:em|para|ke|ko|ka)\b", keyword)
        and any(_contains_signal(keyword, term) for term in ("converter", "convert"))
    ):
        return reject("non_english", "关键词包含非英语转换表达，不符合本次英语站范围")
    if _contains_signal(keyword, "maker") and not any(_contains_signal(keyword, term) for term in DIGITAL_MAKER_CONTEXT):
        return reject("physical_product", "maker 指向实体商品或含义不明确，不属于在线生成工具")
    if any(_contains_signal(keyword, term) for term in PHYSICAL_GENERATOR_TERMS):
        return reject("physical_product", "generator 指向实体设备或既有作品，不属于在线生成工具")
    if any(_contains_signal(keyword, term) for term in PHYSICAL_CONVERTER_TERMS):
        return reject("physical_product", "converter 指向实体产品或电子元件，不属于在线转换工具")
    if " vs " in f" {keyword} " and (
        any(_contains_signal(keyword, term) for term in SPORTS_MATCH_TERMS)
        or re.fullmatch(r"[a-z]{2,3}\s+vs\.?\s+[a-z]{2,3}", keyword)
    ):
        return reject("sports_event", "体育比赛对阵词具有强时效性，不适合作为稳定建站主题")
    if (" vs " in f" {keyword} " or " vs. " in f" {keyword} ") and not any(
        _contains_signal(keyword, term) for term in COMPARISON_SITE_CONTEXT
    ):
        return reject("weak_comparison", "概念或事件对比更适合作为单篇内容，不能独立支撑目标网站")
    if any(_contains_signal(keyword, term) for term in ("review", "reviews")) and not any(
        _contains_signal(keyword, term) for term in COMPARISON_SITE_CONTEXT
    ):
        return reject("weak_review", "评测词缺少明确的软件、服务或可持续商业主题")
    combined_intent = "/".join(str(item.get(field, "")) for field in ("similarweb_intent", "semrush_intent"))
    if "navig" in combined_intent.lower() and not any(signal in f" {keyword} " for signal in COMPARISON_SIGNALS):
        return reject("navigational", "纯品牌或网站导航意图")
    if any(term in keyword for term in PHYSICAL_PRODUCT_TERMS) and not any(_contains_signal(keyword, signal) for signal in COMPARISON_SIGNALS):
        return reject("physical_product", "普通实体商品主词缺少独立软件或内容产品形态")
    if not volumes or not kds:
        return reject("missing_metrics", "搜索量或 KD 缺失，无法完成本地筛选")
    volume = max(volumes)
    kd = max(kds)
    if volume < 5_000:
        return reject("low_volume", f"可用搜索量 {volume:,.0f}，低于 5,000")
    if kd > 60:
        return reject("high_kd", f"保守 KD {kd:.0f}，高于 60")
    first_token = re.findall(r"[a-z0-9]+", keyword)[:1]
    if first_token and len(first_token[0]) <= 3 and first_token[0] not in KNOWN_TOOL_ACRONYMS and sr_volume is None:
        return reject("ambiguous_acronym", "短缩写只有单一来源，词义与需求不够可靠")
    if re.match(r"^(?:how|what|why|where|when|who)\b", keyword) and not _contains_signal(keyword, "calculator"):
        return reject("question_page", "单篇问答意图不足以单独支撑一个建站项目")
    if any(_contains_signal(keyword, term) for term in ("trade analyzer", "trade calculator")) and not any(
        _contains_signal(keyword, term) for term in ("fantasy", "dynasty", "nfl", "baseball", "football", "pokemon", "poe")
    ):
        return reject("ambiguous_trade", "交易分析词缺少明确的游戏、体育或金融使用场景")

    site_type, product_score, expansion_score, fit_reason = classify_site_type(keyword)
    if site_type is None:
        return reject("no_site_fit", fit_reason)
    if site_type == "检查与分析工具" and not any(_contains_signal(keyword, term) for term in ONLINE_TOOL_CONTEXT):
        return reject("unclear_tool", "分析、检测或优化词缺少明确的在线输入与结果场景")

    risk_penalty = 0
    risk_notes: list[str] = []
    if re.search(r"\b(19|20)\d{2}\b", keyword):
        risk_penalty += 5
        risk_notes.append("包含年份，需求可能衰减")
    if "free" in keyword.split():
        risk_penalty += 3
        risk_notes.append("免费意图可能降低直接付费能力")
    if any(term in keyword for term in YMYL_TERMS):
        risk_penalty += 12
        risk_notes.append("涉及健康、法律或金融高风险内容")
    if site_type == "游戏资料与辅助工具":
        risk_penalty += 4
        risk_notes.append("依赖游戏更新与平台政策")
    if site_type == "模板与素材站" and any(term in keyword for term in ("logo", "character", "wallpaper")):
        risk_penalty += 4
        risk_notes.append("需核查素材授权和商标")

    demand_score = _demand_score(volume)
    seo_score = _seo_score(kd)
    monetization_score = _monetization_score(sr_volume and _number(item.get("semrush_cpc")), combined_intent, site_type)
    has_sw = sw_volume is not None and sw_kd is not None
    has_sr = sr_volume is not None and sr_kd is not None
    data_score = 10 if has_sw and has_sr else (7 if has_sr else 6)
    score = max(0, min(100, demand_score + seo_score + product_score + monetization_score + expansion_score + data_score - risk_penalty))
    priority = priority_for_score(score)
    if priority == "淘汰":
        return reject("low_score", f"综合得分 {score:.1f}，低于 60")

    source_status = "双来源" if has_sw and has_sr else ("Semrush" if has_sr else "Similarweb")
    monetization = {
        "计算器": "广告、订阅、付费报告",
        "转换工具": "广告、订阅、批量处理",
        "生成器": "广告、订阅、高级模板",
        "检查与分析工具": "订阅、付费报告、线索获客",
        "编辑与处理工具": "订阅、批量处理",
        "规划与追踪工具": "订阅、广告",
        "游戏资料与辅助工具": "广告、会员、赞助",
        "模板与素材站": "付费素材、联盟、广告",
        "比较与评测站": "联盟、广告、线索获客",
        "教程与资料站": "广告、联盟、赞助",
    }[site_type]
    item.update(
        included=True,
        exclusion_code="",
        decision_reason=f"{fit_reason}；需求与竞争指标达到保留线",
        site_type=site_type,
        cluster_key=cluster_key(keyword, site_type),
        priority=priority,
        score=round(score, 1),
        demand_score=demand_score,
        seo_score=seo_score,
        product_score=product_score,
        monetization_score=monetization_score,
        expansion_score=expansion_score,
        data_confidence_score=data_score,
        risk_penalty=risk_penalty,
        risk_notes="；".join(risk_notes) or "未发现明显硬风险，仍需上线前人工复核",
        source_status=source_status,
        demand_volume=int(volume),
        conservative_kd=int(kd),
        monetization=monetization,
        serp_status=SERP_STATUS,
        keyword_purpose=explain_keyword(keyword, site_type, "；".join(risk_notes)),
        explanation_source="规则兜底（待低成本模型批量生成）",
    )
    return item


def _payload(row: sqlite3.Row) -> dict[str, Any]:
    try:
        value = json.loads(row["payload_json"] or "{}")
    except (TypeError, json.JSONDecodeError):
        value = {}
    return value if isinstance(value, dict) else {}


def load_local_records(database: Path) -> list[dict[str, Any]]:
    """Load only candidates that passed the collection-time metric gates."""
    uri = f"file:{database.resolve()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    try:
        provenance: dict[tuple[str, str, str], list[str]] = defaultdict(list)
        for row in connection.execute(
            "SELECT keyword,provider,market,seed FROM independent_provenance ORDER BY rowid"
        ):
            key = (row["keyword"], str(row["provider"]).lower(), row["market"])
            _append_unique(provenance[key], [row["seed"]])

        rows: list[dict[str, Any]] = []
        for row in connection.execute(
            """SELECT keyword,provider,market,payload_json,accepted_at
               FROM independent_candidates
               ORDER BY provider,keyword,market"""
        ):
            data = _payload(row)
            provider = str(row["provider"]).lower()
            seeds = provenance.get((row["keyword"], provider, row["market"]), [])
            record = {
                "keyword": row["keyword"],
                "provider": provider,
                "volume": data.get("volume", data.get("average_volume")),
                "kd": data.get("kd", data.get("difficulty")),
                "intent": data.get("intent"),
                "retrieved_at": data.get("retrieved_at") or row["accepted_at"],
            }
            if provider == "similarweb":
                record.update(
                    roots=seeds or ([data.get("root")] if data.get("root") else []),
                    result_types=[data.get("result_type")] if data.get("result_type") else [],
                )
            elif provider == "semrush":
                record.update(
                    cpc=data.get("cpc"),
                    competitive_density=data.get("competitive_density", data.get("competition_level")),
                    serp_features=data.get("serp_features"),
                    parents=seeds,
                    exact_match=bool(data.get("exact_match") or data.get("exact_keyword_found")),
                )
            rows.append(record)
        return rows
    finally:
        connection.close()


def _project_name(key: str, site_type: str) -> str:
    topic = key.title() if key else "Keyword"
    suffix = {
        "计算器": "Calculator",
        "转换工具": "Converter",
        "生成器": "Generator",
        "检查与分析工具": "Analyzer",
        "编辑与处理工具": "Editor",
        "规划与追踪工具": "Tracker",
        "游戏资料与辅助工具": "Game Hub",
        "模板与素材站": "Resources",
        "比较与评测站": "Comparison Guide",
        "教程与资料站": "Guide",
    }.get(site_type, "Site")
    return topic if suffix.lower() in topic.lower() else f"{topic} {suffix}"


def build_projects(keywords: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for item in keywords:
        groups[(item["site_type"], item["cluster_key"])].append(item)
    projects: list[dict[str, Any]] = []
    for (site_type, key), members in groups.items():
        ordered = sorted(members, key=lambda item: (-item["score"], -item["demand_volume"], item["keyword"]))
        main = ordered[0]
        breadth_bonus = min(5.0, math.log2(len(ordered) + 1) * 1.5)
        project_score = round(min(100, main["score"] + breadth_bonus), 1)
        projects.append({
            "project_name": _project_name(key, site_type),
            "cluster_key": key,
            "site_type": site_type,
            "main_keyword": main["keyword"],
            "priority": priority_for_score(project_score),
            "score": project_score,
            "keyword_count": len(ordered),
            "main_volume": main["demand_volume"],
            "main_kd": main["conservative_kd"],
            "monetization": main["monetization"],
            "risk_notes": main["risk_notes"],
            "reason": main["decision_reason"],
            "keywords": [item["keyword"] for item in ordered],
        })
    projects.sort(key=lambda item: (-item["score"], -item["keyword_count"], -item["main_volume"], item["project_name"]))
    for rank, project in enumerate(projects, 1):
        project["rank"] = rank
    return projects


def analyze_database(database: Path) -> dict[str, Any]:
    records = merge_keyword_records(load_local_records(database))
    assessed = [assess_keyword(record) for record in records]
    accepted = [item for item in assessed if item["included"]]
    accepted.sort(key=lambda item: (-item["score"], -item["demand_volume"], item["keyword"]))
    for rank, item in enumerate(accepted, 1):
        item["rank"] = rank
    projects = build_projects(accepted)
    project_lookup = {(item["site_type"], item["cluster_key"]): item for item in projects}
    for item in accepted:
        project = project_lookup[(item["site_type"], item["cluster_key"])]
        item["project_rank"] = project["rank"]
        item["project_name"] = project["project_name"]
    exclusions = Counter(item.get("exclusion_code", "unknown") for item in assessed if not item["included"])
    priorities = Counter(item["priority"] for item in accepted)
    site_types = Counter(item["site_type"] for item in accepted)
    source_statuses = Counter(item["source_status"] for item in accepted)
    retrieved_dates = [
        str(item.get(field)) for item in records
        for field in ("similarweb_retrieved_at", "semrush_retrieved_at") if item.get(field)
    ]
    return {
        "metadata": {
            "analysis_generated_at": datetime.now(timezone.utc).isoformat(),
            "database": database.name,
            "latest_source_retrieved_at": max(retrieved_dates) if retrieved_dates else None,
            "market_scope": "Similarweb Global / Semrush US",
            "serp_validation": False,
            "input_dataset": "independent_candidates",
            "method_version": "local-site-fit-v2-filtered-input",
        },
        "summary": {
            "raw_unique_keywords": len(records),
            "accepted_keywords": len(accepted),
            "excluded_keywords": len(records) - len(accepted),
            "project_count": len(projects),
            "priorities": dict(sorted(priorities.items())),
            "site_types": dict(site_types.most_common()),
            "source_statuses": dict(source_statuses.most_common()),
            "exclusion_counts": dict(exclusions.most_common()),
        },
        "projects": projects,
        "keywords": accepted,
    }
