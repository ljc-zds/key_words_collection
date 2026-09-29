"""Query filters matching the supplied Similarweb and Semrush URLs."""
import base64
import gzip
import json
import math


def semrush_filter(cpc_min=0.01, kd_min=0, kd_max=60, volume_min=5000):
    payload = {
        "competition_level": [],
        "cpc": [{"inverted": False, "operation": 5, "value": cpc_min}],
        "difficulty": [
            {"inverted": False, "operation": 5, "value": kd_min},
            {"inverted": False, "operation": 4, "value": kd_max},
        ],
        "phrase": [], "phrase_include_logic": 0, "results": [],
        "serp_features": [{"inverted": False, "value": []}],
        "volume": [{"inverted": False, "operation": 5, "value": volume_min}], "words_count": [],
    }
    return base64.b64encode(gzip.compress(json.dumps(payload, separators=(",", ":")).encode(), mtime=0)).decode()


def metric_filter_reason(kd, cpc, *, kd_min, kd_max, cpc_min):
    for name, value in (("KD", kd), ("CPC", cpc)):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            return f"{name} 缺失或无效，无法确认筛选条件"
    if not kd_min <= kd <= kd_max:
        return f"KD {kd} 不在 {kd_min}–{kd_max} 范围内"
    if cpc < cpc_min:
        return f"CPC {cpc} 低于 {cpc_min}"
    return None
