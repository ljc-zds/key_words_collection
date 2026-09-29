"""Cross-day collection cursors for browser-assisted keyword gathering."""
import json
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class CollectionCheckpoint:
    source: str
    period: str
    source_position: int
    product: str
    root: str
    similarweb_page: int

    def serialize(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, sort_keys=True)

    @classmethod
    def deserialize(cls, value: str) -> "CollectionCheckpoint":
        payload = json.loads(value)
        return cls(
            source=str(payload["source"]),
            period=str(payload["period"]),
            source_position=int(payload["source_position"]),
            product=str(payload["product"]),
            root=str(payload["root"]),
            similarweb_page=int(payload["similarweb_page"]),
        )
