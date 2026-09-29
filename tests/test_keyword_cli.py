from keyword_loop.core.legacy.cli import run
from keyword_loop.core.data.models import KeywordObservation


class StubCollector:
    def collect(self, root: str):
        return [KeywordObservation("agent crm", 31_000, 57, "COMMERCIAL", root, "phrase_match", "global", "now")]


def test_run_dry_run_stores_candidates_without_calling_feishu(tmp_path) -> None:
    result = run(roots=["agent"], database=tmp_path / "loop.sqlite3", dry_run=True, collector=StubCollector())
    assert result.candidate_count == 1
    assert result.published is False
