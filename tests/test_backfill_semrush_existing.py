from backfill_semrush_existing import query_with_retry


class FlakyProvider:
    def __init__(self):
        self.calls = 0

    def query(self, keyword):
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("net::ERR_ABORTED")
        return {"keyword": keyword}


def test_query_with_retry_recovers_from_one_navigation_abort(monkeypatch) -> None:
    monkeypatch.setattr("backfill_semrush_existing.time.sleep", lambda _: None)
    provider = FlakyProvider()

    assert query_with_retry(provider, "wage calculator") == {"keyword": "wage calculator"}
    assert provider.calls == 2
