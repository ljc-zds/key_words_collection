from keyword_loop.core.sources.revenue_sources import canonical_domain, parse_revenue_links, parse_revenue_ranking_domains


def test_parse_revenue_links_deduplicates_and_filters_source_domains() -> None:
    html = '''<a href="https://www.example.com/pricing">Example</a>
    <a href="https://example.com/">Example duplicate</a>
    <a href="https://www.toolify.ai/tool/foo">Toolify</a>
    <a href="/tool/bar">Relative</a>'''
    rows = parse_revenue_links(html, "https://www.toolify.ai/Best-trending-AI-Tools", "toolify")
    assert [row.domain for row in rows] == ["example.com"]
    assert rows[0].source == "toolify"


def test_canonical_domain_strips_www() -> None:
    assert canonical_domain("https://www.example.com/path") == "example.com"


def test_parse_revenue_ranking_domains_reads_rendered_rank_table_data_attributes() -> None:
    html = '''<table class="rank"><tbody>
    <tr><td>#1</td><td class="dom"><a data-d="higgsfield.ai">higgsfield.ai</a><a href="/pricing/?domain=higgsfield.ai">定价</a></td></tr>
    <tr><td>#2</td><td class="dom"><a data-d="elevenlabs.io">elevenlabs.io</a><a href="https://elevenlabs.io">↗</a></td></tr>
    </tbody></table>'''

    rows = parse_revenue_ranking_domains(html, "https://seo.web.cafe/referring/", "stripe")

    assert [(row.domain, row.url) for row in rows] == [
        ("higgsfield.ai", "https://higgsfield.ai"),
        ("elevenlabs.io", "https://elevenlabs.io"),
    ]
