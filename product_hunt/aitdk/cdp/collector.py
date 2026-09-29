import json
from dataclasses import replace
from typing import Any

from ..data.models import CollectionRecord


def parse_traffic_event(event: dict[str, Any]) -> CollectionRecord:
    """Convert a normal AITDK traffic event into the limited report record."""
    domain, data = event.get("domain"), event.get("data")
    if not isinstance(domain, str) or not isinstance(data, dict):
        raise ValueError("traffic event requires domain and data")
    return CollectionRecord.from_plugin_data(domain, data)


def parse_event_stream(text: str) -> CollectionRecord | None:
    """Return the first traffic event from a completed plugin event stream."""
    event_type: str | None = None
    whois: dict[str, Any] | None = None
    for line in text.splitlines():
        if line.startswith("event:"):
            event_type = line.removeprefix("event:").strip()
        elif line.startswith("data:"):
            payload = json.loads(line.removeprefix("data:").strip())
            if not isinstance(payload, dict):
                raise ValueError("traffic event data must be an object")
            if event_type == "whois":
                data = payload.get("data")
                if isinstance(data, dict):
                    whois = data
                continue
            if event_type != "traffic":
                continue
            try:
                return replace(parse_traffic_event(payload), whois=whois)
            except ValueError:
                # The extension may emit a loading update before the result.
                continue
    return None
