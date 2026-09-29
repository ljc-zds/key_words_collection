from dataclasses import dataclass


DAILY_TARGET = 60
DAILY_SOURCE_QUOTAS = {"stripe": 20, "toolify": 20, "root": 20}


@dataclass(frozen=True)
class SourceAllocator:
    quotas: dict[str, int]

    def next_source(self, accepted: dict[str, int], exhausted: set[str]) -> str | None:
        for source in ("stripe", "toolify", "root"):
            if source not in exhausted and accepted.get(source, 0) < self.quotas.get(source, 0):
                return source
        if "root" not in exhausted and ({"stripe", "toolify"} & exhausted):
            return "root"
        return None

    def replenishment_needed(self, *, accepted_total: int, queued_pending: int, target: int) -> bool:
        """Keep Similarweb collection ahead of Semrush instead of waiting for a batch."""
        return accepted_total + queued_pending < target
