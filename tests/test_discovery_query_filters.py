import base64
import gzip
import json
from types import SimpleNamespace
from unittest.mock import patch

from keyword_loop.core.clients.discovery_filters import metric_filter_reason, semrush_filter
from keyword_loop.core.clients.semrush_browser import SemrushBrowserProvider
from keyword_loop.core.clients.similarweb import SimilarwebCollector, keyword_generator_url
from keyword_loop.core.data.store import KeywordStore
from keyword_loop.workflows.discovery.pipeline import validate_semrush


def test_semrush_filter_matches_supplied_schema():
    body = json.loads(gzip.decompress(base64.b64decode(semrush_filter())))
    assert body['cpc'] == [{'inverted': False, 'operation': 5, 'value': 0.01}]
    assert body['volume'] == [{'inverted': False, 'operation': 5, 'value': 5000}]
    assert [(r['operation'], r['value']) for r in body['difficulty']] == [(5, 0), (4, 60)]


def test_metric_boundaries_and_missing_cpc():
    for kd, cpc, passes in [(1, .01, True), (60, .01, True), (0, 1, False), (61, 1, False), (5, 0, False), (5, None, False)]:
        assert (metric_filter_reason(kd, cpc, kd_min=1, kd_max=60, cpc_min=.01) is None) == passes


def test_similarweb_drops_out_of_filter_rows_and_accepts_empty_grid():
    client = SimilarwebCollector(discovery_filters=True)
    entry = {'status': 200, 'url': 'https://sim.3ue.co/api/KeywordGenerator/google/suggest?type=Broad', 'body': {'records': [
        {'keyword': 'valid', 'difficulty': 30, 'averageVolume': 9000, 'cpc': .01},
        {'keyword': 'free', 'difficulty': 20, 'averageVolume': 50000, 'cpc': 0},
        {'keyword': 'unknown', 'difficulty': 20, 'averageVolume': 50000},
        {'keyword': 'below minimum', 'difficulty': 20, 'averageVolume': 4999, 'cpc': 1},
        {'keyword': 'at minimum', 'difficulty': 20, 'averageVolume': 5000, 'cpc': 1},
    ]}}
    assert [row.keyword for row in client._parse_entries([entry], 'test')] == ['valid', 'at minimum']
    entry['body']['records'] = []
    assert client._parse_entries([entry], 'test') == []


def test_similarweb_hash_route_encodes_spaces_without_literal_plus_signs():
    url = keyword_generator_url("prompt generator")
    assert "keyword=prompt%20generator" in url
    assert "keyword=prompt+generator" not in url


def test_filtered_absence_skips_without_unfiltered_query(tmp_path):
    provider = SemrushBrowserProvider(cdp_url='http://localhost:9222', discovery_filters=True)
    provider._min_interval = 0
    outputs = [SimpleNamespace(returncode=0, stdout=json.dumps({'keywords': []})),
               SimpleNamespace(returncode=0, stdout=json.dumps({'keywords': [{'keyword': 'test', 'volume': 50000, 'difficulty': 30, 'cpc': 0}]}))]
    with patch('keyword_loop.core.clients.semrush_browser.subprocess.run', side_effect=outputs) as run:
        store = KeywordStore(tmp_path / 'test.sqlite')
        assert validate_semrush(store, provider, 'test', 'global').decision == '淘汰'
        assert run.call_args_list[0].args[0][-1]  # filtered first
        assert run.call_count == 1


def test_true_semrush_missing_is_not_accepted(tmp_path):
    provider = SemrushBrowserProvider(cdp_url='http://localhost:9222', discovery_filters=True)
    provider._min_interval = 0
    with patch('keyword_loop.core.clients.semrush_browser.subprocess.run', return_value=SimpleNamespace(returncode=0, stdout=json.dumps({'keywords': []}))):
        store = KeywordStore(tmp_path / 'test.sqlite')
        assert validate_semrush(store, provider, 'test', 'global').decision == '淘汰'


def test_filtered_low_volume_cannot_pass_as_missing(tmp_path):
    provider = SemrushBrowserProvider(cdp_url='http://localhost:9222', discovery_filters=True)
    provider._min_interval = 0
    outputs = [SimpleNamespace(returncode=0, stdout=json.dumps({'keywords': []})),
               SimpleNamespace(returncode=0, stdout=json.dumps({'keywords': [{'keyword': 'test', 'volume': 4999, 'difficulty': 20, 'cpc': 1}]}))]
    with patch('keyword_loop.core.clients.semrush_browser.subprocess.run', side_effect=outputs):
        store = KeywordStore(tmp_path / 'test.sqlite')
        assert validate_semrush(store, provider, 'test', 'global').decision == '淘汰'
