import json
import time
from unittest.mock import patch

import pytest
from playwright.sync_api import Error as PlaywrightError

from trend_radar.google_trends.client import CdpGoogleTrendsClient, GoogleTrendsClient, IsolatedNewCdpGoogleTrendsClient, NewCdpGoogleTrendsClient, isolated_process_context, is_new_trends_rpc_response, parse_batchexecute_rpc, parse_cdp_rpc_response, parse_new_rising_queries, parse_new_timeline_values, parse_trends_response, run_in_isolated_process
from trend_radar.google_trends.comparison import is_new_word
from trend_radar.google_trends.parsing import parse_related_queries
from trend_radar.pipeline import scan_roots
from trend_radar.cli import build_client, load_resume_state
from trend_radar.publish import NEW_WORD_HEADERS, build_new_word_rows


def test_google_trends_client_uses_project_ssl_context() -> None:
    response = type("Response", (), {"__enter__": lambda self: self, "__exit__": lambda self, *args: None, "read": lambda self: b"{}"})()
    with patch("trend_radar.google_trends.client.trusted_ssl_context", return_value="trusted-context") as context, patch("trend_radar.google_trends.client.urlopen", return_value=response) as opener:
        GoogleTrendsClient()._get("explore", {"hl": "en-US"})

    context.assert_called_once_with()
    assert opener.call_args.kwargs["context"] == "trusted-context"


def test_parse_trends_response_removes_xssi_prefix() -> None:
    assert parse_trends_response(")]}'\n{\"default\": {\"timelineData\": []}}") == {"default": {"timelineData": []}}


def test_parse_batchexecute_rpc_decodes_nested_rpc_payload() -> None:
    response = ")]}'\n\n72\n[[\"wrb.fr\",\"fXqlme\",\"[[[\\\"agent\\\",[[\\\"openclaw\\\",5000,8]]]]]\",null,null,null,\"generic\"]]"
    assert parse_batchexecute_rpc(response, "fXqlme") == [[["agent", [["openclaw", 5000, 8]]]]]


def test_parse_cdp_rpc_response_ignores_a_response_closed_during_page_cleanup() -> None:
    class Response:
        def text(self) -> str:
            raise PlaywrightError("Target page, context or browser has been closed")

    assert parse_cdp_rpc_response(Response(), "g4kJzf") is None


def test_new_trends_rpc_response_does_not_require_rpc_id_in_url() -> None:
    """The RPC id lives in the response body for POST batch requests."""
    assert is_new_trends_rpc_response("https://trends.google.com/_/TrendsUi/data/batchexecute") is True
    assert is_new_trends_rpc_response("https://trends.google.com/explore?q=agent") is False


def test_parse_new_rising_queries_keeps_growth_at_least_500() -> None:
    payload = [[["agent", [["openclaw", 5000, 8], ["small term", 200, 0], ["claude agent", 750, 14]]], ["gpts", [["gpts trend", 900, 1]]]]]
    assert parse_new_rising_queries(payload, source_term="agent") == [
        {"query": "openclaw", "type": "rising", "growth_percent": 5000},
        {"query": "claude agent", "type": "rising", "growth_percent": 750},
    ]


def test_parse_new_rising_queries_keeps_all_numeric_rows_in_raw_mode() -> None:
    payload = [[["agent", [["breakout", 5000, 2], ["small", 200, 0]]]]]

    assert parse_new_rising_queries(payload, source_term="agent", minimum_growth=0) == [
        {"query": "breakout", "type": "Breakout", "growth_percent": None},
        {"query": "small", "type": "rising", "growth_percent": 200},
    ]


def test_parse_new_rising_queries_keeps_breakout_rows() -> None:
    payload = [[["ac", [["ac milan vs venezia", "BREAKOUT", 8]]]]]

    assert parse_new_rising_queries(payload, source_term="ac") == [
        {"query": "ac milan vs venezia", "type": "Breakout", "growth_percent": None},
    ]


def test_parse_new_rising_queries_maps_new_ui_breakout_marker() -> None:
    payload = [[["action", [["class action settlement", 5000, 2]]]]]

    assert parse_new_rising_queries(payload, source_term="action") == [
        {"query": "class action settlement", "type": "Breakout", "growth_percent": None},
    ]


def test_parse_new_timeline_values_normalizes_terms_and_dates() -> None:
    payload = [[[
        ["openclaw", None, None, 1, [[0, 3, [[100], [200]]], [0, 6, [[200], [300]]]]],
        ["gpts", None, None, 1, [[0, 4, [[100], [200]]], [0, 5, [[200], [300]]]]],
    ]]]
    assert parse_new_timeline_values(payload) == {
        "openclaw": (["100", "200"], [3, 6]),
        "gpts": (["100", "200"], [4, 5]),
    }


def test_parse_related_queries_keeps_breakout_and_numeric_growth() -> None:
    payload = {
        "default": {"rankedList": [{"rankedKeyword": [
            {"query": "breakout term", "value": "Breakout"},
            {"query": "growing term", "value": "+750%"},
            {"query": "small term", "value": "+100%"},
        ]}]}
    }

    assert parse_related_queries(payload, minimum_growth=500) == [
        {"query": "breakout term", "type": "Breakout", "growth_percent": None},
        {"query": "growing term", "type": "rising", "growth_percent": 750},
    ]


def test_new_word_requires_baseline_below_gpts_and_recent_crossing() -> None:
    candidate = [1] * 21 + [1, 1, 12] + [1] * 6
    gpts = [5] * 21 + [5] * 9

    result = is_new_word(candidate, gpts, baseline_points=21)

    assert result["is_new_word"] is True
    assert result["first_crossing_index"] == 23
    assert result["crossing_count"] == 1


def test_scan_roots_records_every_qualified_related_query_after_comparison() -> None:
    class Client:
        def __init__(self) -> None:
            self.batches: list[list[str]] = []

        def related_rising(self, root: str) -> list[dict]:
            return [{"query": query, "type": "Breakout", "growth_percent": None} for query in ["one", "two"]]

        def compare_batch(self, candidates: list[str], baseline: str) -> dict:
            self.batches.append(candidates)
            new_series = [1] * 21 + [8] + [1] * 8
            old_series = [1] * 30
            return {
                "one": ([str(index) for index in range(30)], old_series, [5] * 30),
                "two": ([str(index) for index in range(30)], new_series, [5] * 30),
            }

    client = Client()
    records = scan_roots(["root"], client)

    assert client.batches == [["one", "two"]]
    assert {item["candidate"] for item in records} == {"one", "two"}
    assert next(item for item in records if item["candidate"] == "one")["related"] == {"query": "one", "type": "Breakout", "growth_percent": None}
    assert next(item for item in records if item["candidate"] == "one")["comparison"]["is_new_word"] is False


def test_scan_roots_recursively_expands_qualified_related_queries() -> None:
    class Client:
        def related_rising(self, term: str) -> list[dict]:
            children = {
                "agent": ["openclaw"],
                "openclaw": ["openclaw plugin"],
                "openclaw plugin": [],
            }
            return [{"query": query, "type": "Breakout", "growth_percent": None} for query in children[term]]

        def compare_batch(self, candidates: list[str], baseline: str) -> dict:
            series = [1] * 21 + [8] + [1] * 8
            return {candidate: ([str(index) for index in range(30)], series, [5] * 30) for candidate in candidates}

    records = scan_roots(["agent"], Client(), max_depth=2)

    assert [(item["candidate"], item["parent_keyword"], item["depth"])
            for item in records] == [
        ("openclaw", "agent", 1),
        ("openclaw plugin", "openclaw", 2),
    ]


def test_scan_roots_has_no_default_depth_limit_and_records_parent_rising_queries() -> None:
    class Client:
        def related_rising(self, term: str) -> list[dict]:
            children = {"root": ["one"], "one": ["two"], "two": ["three"], "three": []}
            return [{"query": query, "type": "Breakout", "growth_percent": None} for query in children[term]]

        def compare_batch(self, candidates: list[str], baseline: str) -> dict:
            return {candidate: ([str(index) for index in range(30)], [1] * 30, [2] * 30) for candidate in candidates}

    parent_rising: dict[str, dict] = {}
    records = scan_roots(["root"], Client(), parent_rising=parent_rising)

    assert [record["candidate"] for record in records] == ["one", "two", "three"]
    assert parent_rising["two"] == {
        "parent_keyword": "two",
        "root": "root",
        "depth": 2,
        "qualified_rising_count": 1,
        "qualified_rising_queries": [{"query": "three", "type": "Breakout", "growth_percent": None}],
    }


def test_scan_roots_skips_completed_parents_and_retries_unavailable_candidates() -> None:
    class Client:
        def __init__(self) -> None:
            self.related_calls: list[str] = []

        def related_rising(self, term: str) -> list[dict]:
            self.related_calls.append(term)
            return [{"query": "retry me", "type": "Breakout", "growth_percent": None}]

        def compare_batch(self, candidates: list[str], baseline: str) -> dict:
            return {"retry me": ([str(index) for index in range(30)], [1] * 21 + [8] + [1] * 8, [5] * 30)}

    client = Client()
    checkpoints: list[tuple[list[dict], set[str]]] = []
    previous = [
        {"root": "done", "parent_keyword": "done", "depth": 1, "candidate": "already done", "related": {}, "comparison": {"is_new_word": False}},
        {"root": "retry", "parent_keyword": "retry", "depth": 1, "candidate": "retry me", "related": {}, "comparison": {"is_new_word": False, "status": "unavailable"}},
    ]

    records = scan_roots(
        ["done", "retry"],
        client,
        completed_parents={"done", "already done"},
        existing_records=previous,
        max_depth=1,
        on_checkpoint=lambda items, parents: checkpoints.append((items, parents)),
    )

    assert client.related_calls == ["retry"]
    assert {item["candidate"] for item in records} == {"already done", "retry me"}
    assert records[-1]["comparison"].get("status") != "unavailable"
    assert checkpoints[-1][1] == {"done", "retry", "already done"}


def test_scan_roots_persists_and_retries_a_parent_whose_rising_query_request_failed() -> None:
    class Client:
        def __init__(self) -> None:
            self.fail_once = True

        def related_rising(self, term: str) -> list[dict]:
            if term == "child" and self.fail_once:
                self.fail_once = False
                raise RuntimeError("Google Trends timeout")
            children = {"root": ["child"], "child": ["grandchild"]}
            return [
                {"query": query, "type": "Breakout", "growth_percent": None}
                for query in children.get(term, [])
            ]

        def compare_batch(self, candidates: list[str], baseline: str) -> dict:
            return {
                candidate: ([str(index) for index in range(30)], [1] * 30, [2] * 30)
                for candidate in candidates
            }

    client = Client()
    failed_parents: dict[str, dict] = {}
    first_records = scan_roots(
        ["root"],
        client,
        max_depth=2,
        failed_parents=failed_parents,
    )

    assert [record["candidate"] for record in first_records] == ["child"]
    assert failed_parents == {
        "child": {
            "parent_keyword": "child",
            "root": "root",
            "depth": 1,
            "error": "Google Trends timeout",
        }
    }

    resumed_records = scan_roots(
        ["root"],
        client,
        max_depth=2,
        existing_records=first_records,
        completed_parents={"root"},
        failed_parents=failed_parents,
    )

    assert {record["candidate"] for record in resumed_records} == {"child", "grandchild"}
    assert failed_parents == {}


def test_scan_roots_keeps_an_unavailable_candidate_when_its_parent_has_no_new_rising_rows() -> None:
    class Client:
        def related_rising(self, term: str) -> list[dict]:
            return []

    unavailable = {
        "root": "root",
        "parent_keyword": "root",
        "depth": 1,
        "candidate": "retry me",
        "related": {"query": "retry me", "type": "Breakout", "growth_percent": None},
        "comparison": {"is_new_word": False, "status": "unavailable"},
    }

    records = scan_roots(["root"], Client(), max_depth=1, existing_records=[unavailable])

    assert records == [unavailable]


def test_scan_roots_retries_an_unavailable_candidate_from_a_completed_parent() -> None:
    class Client:
        def related_rising(self, term: str) -> list[dict]:
            return [{"query": "retry me", "type": "Breakout", "growth_percent": None}]

        def compare_batch(self, candidates: list[str], baseline: str) -> dict:
            return {"retry me": ([str(index) for index in range(30)], [1] * 30, [2] * 30)}

    unavailable = {
        "root": "root",
        "parent_keyword": "root",
        "depth": 1,
        "candidate": "retry me",
        "related": {"query": "retry me", "type": "Breakout", "growth_percent": None},
        "comparison": {"is_new_word": False, "status": "unavailable"},
    }

    records = scan_roots(
        ["root"],
        Client(),
        existing_records=[unavailable],
        completed_parents={"root"},
        max_depth=1,
    )

    assert len(records) == 1
    assert records[0]["candidate"] == "retry me"
    assert records[0]["comparison"].get("status") != "unavailable"


def test_scan_roots_checkpoints_each_comparison_batch_before_parent_completion() -> None:
    class Client:
        def related_rising(self, term: str) -> list[dict]:
            return [{"query": f"word {number}", "type": "Breakout", "growth_percent": None} for number in range(5)]

        def compare_batch(self, candidates: list[str], baseline: str) -> dict:
            return {
                candidate: ([str(index) for index in range(30)], [1] * 30, [5] * 30)
                for candidate in candidates
            }

    checkpoints: list[tuple[int, set[str]]] = []
    scan_roots(["root"], Client(), max_depth=1, on_checkpoint=lambda records, parents: checkpoints.append((len(records), set(parents))))

    assert checkpoints[0] == (4, set())
    assert checkpoints[-1] == (5, {"root"})


def test_load_resume_state_restores_failed_parents_for_retry(tmp_path) -> None:
    output = tmp_path / "trend-radar.json"
    output.write_text(json.dumps({
        "evaluated_candidates": [
            {"candidate": "done", "comparison": {"is_new_word": False}},
            {"candidate": "retry", "comparison": {"status": "unavailable", "is_new_word": False}},
        ],
        "completed_parents": ["agent"],
        "pending_parents": [{
            "parent_keyword": "openclaw",
            "root": "agent",
            "depth": 1,
            "error": "Google Trends timeout",
        }],
    }), encoding="utf-8")

    records, parents, failed_parents, parent_rising = load_resume_state(output)

    assert [record["candidate"] for record in records] == ["done", "retry"]
    assert parents == {"agent"}
    assert failed_parents == {
        "openclaw": {
            "parent_keyword": "openclaw",
            "root": "agent",
            "depth": 1,
            "error": "Google Trends timeout",
        }
    }
    assert parent_rising == {}


def test_cli_uses_browser_api_client_so_target_cleanup_always_runs() -> None:
    from trend_radar.google_trends.fallback import FallbackGoogleTrendsClient
    assert isinstance(build_client("http://127.0.0.1:9222"), FallbackGoogleTrendsClient)


def _process_returns(value):
    return value


def _process_waits(seconds):
    time.sleep(seconds)
    return "done"


def test_isolated_process_returns_result_and_terminates_stalled_work() -> None:
    assert run_in_isolated_process(_process_returns, ("ok",), timeout_seconds=2) == "ok"
    with pytest.raises(RuntimeError, match="timed out"):
        run_in_isolated_process(_process_waits, (1,), timeout_seconds=0.05)


def test_isolated_browser_operations_use_fork_on_macos() -> None:
    assert isolated_process_context().get_start_method() == "fork"


def test_cdp_client_reuses_an_existing_google_trends_page() -> None:
    other_page = type("Page", (), {"url": "https://example.com/"})()
    trends_page = type("Page", (), {"url": "https://trends.google.com/trends/explore?q=action"})()

    class Context:
        pages = [other_page, trends_page]

    assert CdpGoogleTrendsClient()._existing_trends_page([Context()]) is trends_page


def test_cdp_client_enables_focus_emulation_without_bringing_page_to_front() -> None:
    class Session:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict]] = []
            self.detached = False

        def send(self, method: str, params: dict) -> None:
            self.calls.append((method, params))

        def detach(self) -> None:
            self.detached = True

    class Context:
        def __init__(self) -> None:
            self.session = Session()

        def new_cdp_session(self, page):
            return self.session

    context = Context()
    CdpGoogleTrendsClient()._enable_focus_emulation(context, object())

    assert context.session.calls == [("Emulation.setFocusEmulationEnabled", {"enabled": True})]
    assert context.session.detached is True


def test_cdp_client_requires_an_existing_google_trends_page() -> None:
    class Context:
        pages = []

    with pytest.raises(RuntimeError, match="existing Google Trends page"):
        CdpGoogleTrendsClient()._existing_trends_page([Context()])


def test_new_cdp_client_gives_rising_queries_a_longer_rpc_window(monkeypatch) -> None:
    client = NewCdpGoogleTrendsClient(timeout_ms=20_000, rising_timeout_ms=60_000)
    captured_timeouts: list[int | None] = []
    activated_terms: list[str | None] = []
    payload = [[["ac", [["ac trend", 800, 1]]]]]

    def capture(terms: list[str], rpc_id: str, timeframe: str, *, timeout_ms: int | None = None, activate_related_term: str | None = None) -> list[object]:
        assert terms == ["ac", "gpts"]
        assert rpc_id == "fXqlme"
        captured_timeouts.append(timeout_ms)
        activated_terms.append(activate_related_term)
        return [payload]

    monkeypatch.setattr(client, "_capture_rpc", capture)

    assert client.related_rising("ac") == [{"query": "ac trend", "type": "rising", "growth_percent": 800}]
    assert captured_timeouts == [60_000]
    assert activated_terms == ["ac"]


def test_new_cdp_client_exposes_all_raw_rising_rows(monkeypatch) -> None:
    client = NewCdpGoogleTrendsClient()
    payload = [[["ac", [["large", 800, 0], ["small", 200, 0]]]]]

    monkeypatch.setattr(client, "_capture_rpc", lambda *args, **kwargs: [payload])

    assert client.related_rising_all("ac") == [
        {"query": "large", "type": "rising", "growth_percent": 800},
        {"query": "small", "type": "rising", "growth_percent": 200},
    ]


def test_new_cdp_client_retries_an_empty_rising_response(monkeypatch) -> None:
    client = NewCdpGoogleTrendsClient()
    responses = [[], [[["action", [["loaded", 700, 0]]]]]]

    monkeypatch.setattr(client, "_capture_rpc", lambda *args, **kwargs: [responses.pop(0)])

    assert client.related_rising_all("action") == [
        {"query": "loaded", "type": "rising", "growth_percent": 700},
    ]


def test_scan_roots_falls_back_to_individual_comparisons_after_batch_failure() -> None:
    class Client:
        def related_rising(self, term: str) -> list[dict]:
            return [{"query": query, "type": "Breakout", "growth_percent": None} for query in ["one", "two"]] if term == "root" else []

        def compare_batch(self, candidates: list[str], baseline: str) -> dict:
            raise RuntimeError("no multiline response")

        def compare(self, candidate: str, baseline: str):
            series = [1] * 21 + [8] + [1] * 8
            return [str(index) for index in range(30)], series, [5] * 30

    records = scan_roots(["root"], Client(), max_depth=1)
    assert {item["candidate"] for item in records} == {"one", "two"}


def test_scan_roots_marks_a_candidate_unavailable_when_batch_omits_its_series() -> None:
    class Client:
        def related_rising(self, term: str) -> list[dict]:
            return [
                {"query": "present", "type": "rising", "growth_percent": 700},
                {"query": "missing", "type": "rising", "growth_percent": 800},
            ]

        def compare_batch(self, candidates: list[str], baseline: str) -> dict:
            return {"present": ([str(index) for index in range(30)], [1] * 30, [2] * 30)}

    records = scan_roots(["root"], Client(), max_depth=1)

    missing = next(record for record in records if record["candidate"] == "missing")
    assert missing["comparison"]["status"] == "unavailable"


def test_scan_roots_expands_each_root_depth_first_before_the_next_root() -> None:
    class Client:
        def __init__(self) -> None:
            self.related_calls: list[str] = []

        def related_rising(self, term: str) -> list[dict]:
            self.related_calls.append(term)
            children = {
                "root-a": ["a-first", "a-second"],
                "a-first": ["a-first-child"],
                "a-second": ["a-second-child"],
                "root-b": ["b-first"],
                "b-first": ["b-first-child"],
            }
            return [{"query": item, "type": "rising", "growth_percent": 600} for item in children.get(term, [])]

        def compare_batch(self, candidates: list[str], baseline: str) -> dict:
            return {candidate: ([str(index) for index in range(30)], [1] * 30, [2] * 30) for candidate in candidates}

    client = Client()
    scan_roots(["root-a", "root-b"], client, max_depth=2)

    assert client.related_calls == ["root-a", "a-first", "a-second", "root-b", "b-first"]


def test_build_new_word_rows_formats_trend_and_comparison_fields() -> None:
    records = [{
        "root": "action",
        "parent_keyword": "action",
        "depth": 1,
        "candidate": "class action settlement",
        "related": {"type": "Breakout", "growth_percent": None},
        "comparison": {
            "candidate_baseline_average": 0.0,
            "gpts_baseline_average": 14.36,
            "crossing_count": 3,
            "maximum_difference": 89,
            "still_above_gpts": False,
        },
        "first_crossing_time": "1788134400",
    }]

    assert build_new_word_rows(records) == [
        NEW_WORD_HEADERS,
        ["class action settlement", "action", "action", 1, "Breakout", "Breakout", 0.0, 14.36, "2026-08-31", 3, 89, "否", "过去30天：前21天低于 gpts，后9天出现超过"],
    ]
