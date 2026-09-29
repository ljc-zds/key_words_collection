"""Collect Similarweb keyword JSON through the user's OpenCLI browser session."""
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, quote, urlencode, urlparse

from ..data.models import KeywordObservation
from .browser_proxy import OpenCliBrowser
from .cdp_proxy import CdpBrowser
from .discovery_filters import metric_filter_reason


class BrowserProxyError(RuntimeError):
    pass


def _json_output(output: str) -> dict:
    start = output.find("{")
    if start < 0:
        raise BrowserProxyError("OpenCLI returned no JSON response")
    try:
        return json.JSONDecoder().raw_decode(output[start:])[0]
    except json.JSONDecodeError as error:
        raise BrowserProxyError("OpenCLI returned malformed JSON") from error


def _intent(record: dict) -> str | None:
    values = [str(record.get(name, "")).strip() for name in ("primaryIntent", "secondaryIntent")]
    return "/".join(value for value in values if value) or None


def is_primary_keyword_response(url: str) -> bool:
    """Keep only the paginated keyword grid, not side-panel suggestions."""
    query = parse_qs(urlparse(url).query)
    return query.get("type", [""])[0] == "Broad" and not query.get("label")


def keyword_generator_url(root: str, *, filtered: bool = False) -> str:
    """Build the SPA route without turning spaces into literal plus signs."""
    params = {
        "searchEngine": "google",
        "keyword": root,
        "webSource": "Total",
        "isWWW": "*",
        "tab": "phraseMatch",
    }
    if filtered:
        params.update({"cpcFromValue": 0.01, "volumeFromValue": 5000, "difficultyFromValue": 1, "difficultyToValue": 60})
    return (
        "https://sim.3ue.co/#/digitalsuite/acquisition/findkeywords/"
        "keyword-generator-tool/999/28d?" + urlencode(params, quote_via=quote)
    )


class SimilarwebCollector:
    """Use network responses instead of Similarweb's slow, sometimes blocked grid."""

    def __init__(self, *, browser: Path | None = None, profile: Path | None = None, market: str = "global", per_root_cap: int = 500, cdp_url: str | None = None, opencli: str = "opencli", discovery_filters: bool = False) -> None:
        self.discovery_filters = discovery_filters
        self.market = market
        self.per_root_cap = per_root_cap
        self.opencli = opencli
        self.cdp_url = cdp_url

    def _run(self, session: str, *args: str) -> dict:
        result = subprocess.run([self.opencli, "browser", session, *args], check=False, capture_output=True, text=True, timeout=60)
        if result.returncode:
            raise BrowserProxyError(result.stderr.strip() or result.stdout.strip() or "OpenCLI command failed")
        return _json_output(result.stdout) if "{" in result.stdout else {}

    def collect(self, root: str) -> list[KeywordObservation]:
        url = keyword_generator_url(root, filtered=self.discovery_filters)
        if self.cdp_url:
            script = Path(__file__).with_name("similarweb_native_cdp.mjs")
            pages = max(1, (self.per_root_cap + 99) // 100) if self.per_root_cap else 0
            result = subprocess.run(["node", str(script), self.cdp_url, url, "/api/KeywordGenerator/google/suggest", str(pages)], capture_output=True, text=True, timeout=60 if pages else None)
            if result.returncode:
                raise BrowserProxyError(result.stderr.strip() or "Similarweb native CDP failed")
            entries = [entry for entry in json.loads(result.stdout or "[]") if is_primary_keyword_response(entry.get("url", ""))]
            return self._parse_entries(entries, root)
        with OpenCliBrowser(prefix="similarweb-keyword", executable=self.opencli) as browser:
            entries = browser.capture_after_open(url, path_fragment="/api/KeywordGenerator/google/suggest")
        return self._parse_entries(entries, root)

    def _parse_entries(self, entries: list[dict], root: str) -> list[KeywordObservation]:
        retrieved_at = datetime.now(timezone.utc).isoformat()
        observations: list[KeywordObservation] = []
        for entry in entries:
            if entry.get("status") != 200 or "/api/KeywordGenerator/google/suggest" not in entry.get("url", ""):
                continue
            result_type = parse_qs(urlparse(entry["url"]).query).get("type", ["Broad"])[0]
            for record in entry.get("body", {}).get("records", []):
                keyword = " ".join(str(record.get("keyword", "")).split()).lower()
                volume, kd = record.get("averageVolume"), record.get("difficulty")
                if not keyword or not isinstance(volume, (int, float)) or not isinstance(kd, (int, float)):
                    continue
                if self.discovery_filters and metric_filter_reason(kd, record.get("cpc"), kd_min=1, kd_max=60, cpc_min=0.01):
                    continue
                if self.discovery_filters and volume < 5000:
                    continue
                observations.append(KeywordObservation(keyword, int(volume), int(kd), _intent(record), root, result_type, self.market, retrieved_at, cpc=record.get("cpc")))
                if self.per_root_cap and len(observations) >= self.per_root_cap:
                    return observations
        if not observations and not any(is_primary_keyword_response(e.get("url", "")) and e.get("status") == 200 and isinstance(e.get("body", {}).get("records"), list) for e in entries):
            raise BrowserProxyError("Similarweb returned no keyword JSON responses")
        return observations
