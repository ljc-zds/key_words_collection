from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class CollectionRecord:
    """The subset of plugin data that the demand-discovery workflow needs."""

    domain: str
    title: str | None
    description: str | None
    overview: dict[str, Any]
    traffic_sources: dict[str, Any]
    top_keywords: list[dict[str, Any]]
    whois: dict[str, Any] | None = None
    failure_reason: str | None = None

    @classmethod
    def from_plugin_data(cls, domain: str, data: dict[str, Any]) -> "CollectionRecord":
        return cls(
            domain=domain,
            title=data.get("title"),
            description=data.get("description"),
            overview=data.get("overview", {}),
            traffic_sources=data.get("trafficSources", {}),
            top_keywords=data.get("topKeywords", []),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
