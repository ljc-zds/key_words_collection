from pathlib import Path

from keyword_loop.core.data.models import KeywordObservation
from keyword_loop.core.sources.rankings import RankedProduct
from keyword_loop.core.legacy.ranking_cli import run_ranked_products
from keyword_loop.core.data.store import KeywordStore


class StubCollector:
    def collect(self, query: str) -> list[KeywordObservation]:
        return [
            KeywordObservation(
                keyword="ai video generator",
                average_volume=90_000,
                kd=42,
                intent="COMMERCIAL",
                root=query,
                result_type="phrase_match",
                market="global",
                retrieved_at="2026-08-25T00:00:00+00:00",
            )
        ]


def product(name: str, rank: int) -> RankedProduct:
    return RankedProduct(name, f"https://www.toolify.ai/tool/{name.lower()}", rank, "1M", "1K", "", "https://www.toolify.ai/Best-trending-AI-Tools")


def test_run_ranked_products_collects_by_product_and_records_consensus(tmp_path: Path) -> None:
    result = run_ranked_products(
        products=[product("Tripo AI", 1), product("Higgsfield", 2)],
        database=tmp_path / "ranking.sqlite3",
        collector=StubCollector(),
        review_limit=100,
    )

    assert result.product_count == 2
    assert result.failed_products == ()
    assert result.candidate_count == 1
    assert KeywordStore(tmp_path / "ranking.sqlite3").ranking_consensus("ai video generator") == 2
