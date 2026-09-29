from dataclasses import dataclass


@dataclass(frozen=True)
class KeywordObservation:
    keyword: str
    average_volume: int | None
    kd: int | None
    intent: str | None
    root: str
    result_type: str
    market: str
    retrieved_at: str
    cpc: float | None = None


@dataclass(frozen=True)
class KeywordCandidate:
    keyword: str
    average_volume: int
    kd: int
    intent: str | None
    market: str
    source_roots: tuple[str, ...]
    result_types: tuple[str, ...]
    retrieved_at: str
